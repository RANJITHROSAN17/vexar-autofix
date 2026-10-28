"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .agent import autofix
from .clients import DEFAULT_BASE_URL, MODEL_ROLES, Client, MockClient, NebiusClient


def _build_client(args: argparse.Namespace) -> Client:
    if args.provider == "mock":
        print("[rehearsal] mock provider: no network, no model. Edits are fake.\n", file=sys.stderr)
        return MockClient(rehearse_accept=args.rehearse_accept)
    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        raise SystemExit("error: NEBIUS_API_KEY is not set")
    return NebiusClient(key, os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL))


def _print_report(report: dict[str, Any], apply: bool, target: Path) -> None:
    print(f"target      {report['target']}")
    if report.get("clean"):
        print(f"result      clean already ({report['before']['score']}/100 {report['before']['grade']})")
        return

    before = report["before"]
    print(f"before      {before['score']}/100 ({before['grade']}), {before['findings']} findings")

    for v in report["triage"]:
        print(f"  {v['verdict']:<10} {v['rule_id']} @{v['line']}  {v['reason'][:66]}")

    for attempt in report["attempts"]:
        status = "ACCEPTED" if attempt["accepted"] else f"rejected: {(attempt['failure'] or '')[:52]}"
        print(
            f"  {attempt.get('rule_id', '?')} attempt {attempt['number']} "
            f"[{attempt['model_role']}] {attempt['applied']} edit(s) -> {status}"
        )

    fixed = report.get("fixed", [])
    if fixed:
        print(f"fixed       {len(fixed)} finding(s); {len(report.get('unfixed', []))} left to a human")
    if report.get("refused"):
        print(f"refused     {len(report['refused'])} finding(s) outside the autofixable rule set")

    if report.get("verified"):
        print(f"after       {report['after']['score']}/100 ({report['after']['grade']})")
        print(f"tests       {'unchanged / passing' if report['tests_ok'] in (True, None) else 'FAILED'}")
        print()
        print(report["diff"], end="")
        if apply:
            target.write_text(str(report["patch"]), encoding="utf-8")
            print(f"\napplied to {target}")
        else:
            print("\n(dry run -- pass --apply to write the patch)")
    else:
        print("not fixed   verification never passed; target file untouched")

    usage = report.get("usage", {})
    print(f"\nusage       {usage.get('calls', 0)} model calls, ~${usage.get('cost_usd', 0):.4f}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vexar-autofix",
        description="Remediate MCP server findings autonomously, and verify every patch.",
    )
    parser.add_argument("--target", required=True, type=Path, help="file to audit and patch")
    parser.add_argument("--provider", choices=("nebius", "mock"), default="nebius")
    parser.add_argument("--apply", action="store_true", help="write the verified patch back to --target")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--no-tests", action="store_true", help="skip the target's test suite")
    parser.add_argument("--json", action="store_true", help="emit the full report as JSON")
    parser.add_argument(
        "--rehearse-accept",
        action="store_true",
        help="mock only: replay a known-good patch to exercise the accept path",
    )
    parser.add_argument("--list-models", action="store_true", help="print the live model catalogue and exit")
    args = parser.parse_args(argv)

    if args.list_models:
        key = os.environ.get("NEBIUS_API_KEY")
        if not key:
            print("error: NEBIUS_API_KEY is not set", file=sys.stderr)
            return 2
        catalogue = NebiusClient(key, os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL))
        available = catalogue.models()
        for model_id in available:
            marker = " <- in use" if model_id in MODEL_ROLES.values() else ""
            print(f"{model_id}{marker}")
        missing = [m for m in MODEL_ROLES.values() if m not in available]
        if missing:
            print(f"\nwarning: routed models not in the catalogue: {', '.join(missing)}", file=sys.stderr)
            return 1
        return 0

    if not args.target.is_file():
        print(f"error: {args.target} is not a file", file=sys.stderr)
        return 2

    try:
        client: Client = _build_client(args)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2

    report = autofix(client, args.target, max_attempts=args.max_attempts, check_tests=not args.no_tests)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report.get("verified") or report.get("clean") else 1

    _print_report(report, args.apply, args.target)
    return 0 if report.get("verified") or report.get("clean") else 1


if __name__ == "__main__":
    raise SystemExit(main())
