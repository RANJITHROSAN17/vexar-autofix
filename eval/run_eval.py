#!/usr/bin/env python3
"""Measure the agent against ground truth, instead of asserting it works.

Each fixture declares the rules that must be present, because the fixtures were written by
hand and their contents are known. That gives a real denominator: how many confirmed
findings were queued, how many were fixed, and -- the number that matters most -- how many
patches introduced a regression.

A regression is a hard failure of the run, not a statistic. If a patch ever trades one
finding for another, the run exits non-zero and the eval is the first thing to go red.

Usage:
    python eval/run_eval.py                  # real models (needs NEBIUS_API_KEY)
    python eval/run_eval.py --provider mock  # offline rehearsal, clearly labelled fake
    python eval/run_eval.py --json           # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vexar_autofix import MockClient, NebiusClient, autofix, scan
from vexar_autofix.clients import DEFAULT_BASE_URL

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


@dataclass
class Case:
    """A fixture plus the exact rule set we know is in it, because we wrote it.

    Exact equality, not a subset: any drift in the scanner's own behaviour should surface
    here first. The fixtures are hand-written and small enough that their full rule set is
    knowable, so there is no reason to settle for a weaker claim.
    """

    name: str
    expected_rules: frozenset[str]
    note: str


CASES: tuple[Case, ...] = (
    Case(
        "vulnerable_server.py",
        frozenset({"MCP001", "MCP003", "MCP004", "MCP005", "MCP006", "MCP007", "MCP008", "MCP010", "MCP015"}),
        "4 security rules with canonical remedies + 5 contract/schema rules it must refuse",
    ),
    Case(
        "helper_delegation_server.py",
        frozenset({"MCP005", "MCP006", "MCP010"}),
        "sinks one hop away in local helpers",
    ),
    Case(
        "clean_server.py",
        frozenset(),
        "control: must produce no findings and an empty queue",
    ),
)


def evaluate(client: Any, case: Case, *, check_tests: bool, quiet: bool = False) -> dict[str, Any]:
    target = EXAMPLES / case.name
    found = scan(target)
    found_rules = {f.rule_id for f in found}

    result: dict[str, Any] = {
        "case": case.name,
        "note": case.note,
        "scanner_found": sorted(found_rules),
        "expected": sorted(case.expected_rules),
        "ground_truth_matched": found_rules == case.expected_rules,
        "unexpected_rules": sorted(found_rules - case.expected_rules),
    }

    if not case.expected_rules:
        # The control case: it must be clean, and the agent must decline to touch it.
        report = autofix(client, target, check_tests=check_tests)
        result.update(clean=bool(report.get("clean")), queued=0, fixed=0, regressions=0)
        return result

    def progress(message: str) -> None:
        if not quiet:
            print(f"  [{case.name}] {message}", file=sys.stderr, flush=True)

    report = autofix(client, target, check_tests=check_tests, progress=progress)
    regressions = 0
    if report.get("verified"):
        after_rules = {f.rule_id for f in scan(target)}
        regressions = len(after_rules - set(result["scanner_found"]))

    result.update(
        clean=False,
        queued=len(report.get("queue", [])),
        fixed=len(report.get("fixed", [])),
        refused=len(report.get("refused", [])),
        regressions=regressions,
        verified=bool(report.get("verified")),
        before_score=report.get("before", {}).get("score"),
        after_score=report.get("after", {}).get("score"),
        usage=report.get("usage", {}),
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure vexar-autofix against hand-written ground truth.")
    parser.add_argument("--provider", choices=("nebius", "mock"), default="nebius")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check-tests", action="store_true", help="include the target's test suite")
    parser.add_argument("--case", help="run a single fixture by filename, for a faster loop")
    args = parser.parse_args(argv)

    if args.provider == "mock":
        client: Any = MockClient(rehearse_accept=True)
        banner = "REHEARSAL: mock provider, no model was called. These numbers are fake."
    else:
        import os

        key = os.environ.get("NEBIUS_API_KEY")
        if not key:
            print("error: NEBIUS_API_KEY is not set (use --provider mock to rehearse)", file=sys.stderr)
            return 2
        client = NebiusClient(key, os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL))
        banner = "LIVE: numbers below come from real model calls."

    cases = [c for c in CASES if args.case is None or c.name == args.case]
    if not cases:
        print(f"error: no case named {args.case!r}. Known: {[c.name for c in CASES]}", file=sys.stderr)
        return 2
    results = [evaluate(client, case, check_tests=args.check_tests, quiet=args.json) for case in cases]

    if args.json:
        print(json.dumps({"banner": banner, "results": results}, indent=2))
        return 0 if all(r["ground_truth_matched"] and r["regressions"] == 0 for r in results) else 1

    print(banner)
    print()
    header = f"{'fixture':<32}{'found':>6}{'queued':>8}{'fixed':>7}{'refused':>9}{'regress':>9}  score"
    print(header)
    print("-" * len(header))
    for r in results:
        score = "-"
        if r.get("before_score") is not None and r.get("after_score") is not None:
            score = f"{r['before_score']} -> {r['after_score']}"
        print(
            f"{r['case']:<32}{len(r['scanner_found']):>6}{r.get('queued', 0):>8}"
            f"{r.get('fixed', 0):>7}{r.get('refused', 0):>9}{r['regressions']:>9}  {score}"
        )

    problems: list[str] = []
    for r in results:
        if not r["ground_truth_matched"]:
            missing = set(r["expected"]) - set(r["scanner_found"])
            extra = set(r["scanner_found"]) - set(r["expected"])
            problems.append(f"{r['case']}: missed {sorted(missing)}, unexpected {sorted(extra)}")
        if r["regressions"]:
            problems.append(f"{r['case']}: {r['regressions']} regression(s)")

    total_calls = sum(r.get("usage", {}).get("calls", 0) for r in results)
    total_cost = sum(r.get("usage", {}).get("cost_usd", 0.0) for r in results)
    print(f"\n{total_calls} model calls, ~${total_cost:.4f}")

    if problems:
        print("\nFAIL", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1
    print("\nOK: ground truth matched, zero regressions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
