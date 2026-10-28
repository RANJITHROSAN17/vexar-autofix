#!/usr/bin/env python3
"""Self-audit: do the claims this repository publishes still reproduce?

The README and the demo page quote specific numbers - a fixture scoring 4/100 (F), a helper
delegation server at 73/100 (C), a clean server at 100/100 (A+), and a patch audit that
refuses an absurd timeout. Every one of those is a promise made to a reader.

A product that sells verification should verify its own claims on every push. If a rule
changes, a fixture changes, or the audit is loosened, those published numbers quietly become
false and the demo keeps showing them. This script is the thing that notices.

It is deliberately a bot rather than a test suite: the same evidence should appear on the PR
that broke it, in words, not as a red X next to 46 tests.

Usage:
    python .github/scripts/self_audit.py            # human/markdown report, exit 1 on drift
    python .github/scripts/self_audit.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The published claims, as assertions loose enough to survive an improvement and tight
# enough to catch a regression. A fixture that suddenly scores 100 is as much a bug as one
# that suddenly scores 0: the demo page would be advertising a number that is no longer true.
FIXTURE_CLAIMS: tuple[tuple[str, int, int, str], ...] = (
    # file, max score, min diagnostics, why
    ("examples/vulnerable_server.py", 20, 8, "the demo's bad example must stay visibly bad"),
    ("examples/helper_delegation_server.py", 90, 1, "the middle example must stay middling"),
    ("examples/clean_server.py", 100, 0, "the clean example must stay clean"),
)

# Patches the audit must refuse regardless of what the scanner says about the result. These
# are the shortest form of the product's claim: clearing the rule is not fixing the code.
MCP010_REFUSALS: tuple[str, ...] = (
    "timeout=None",
    "timeout=float('inf')",
    "timeout=10**9",
    "timeout=1e9",
    "timeout=86400",
)
MCP010_ACCEPTS: tuple[str, ...] = ("timeout=10", "timeout=2.5", "timeout=TIMEOUT_SECONDS")

MCP010_SOURCE = "import urllib.request\n\ndef fetch(url):\n    return urllib.request.urlopen(url)\n"


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def check_fixtures() -> list[Check]:
    from mcp_doctor.engine import scan_paths

    checks: list[Check] = []
    for relative, max_score, min_diagnostics, why in FIXTURE_CLAIMS:
        path = ROOT / relative
        if not path.is_file():
            checks.append(Check(relative, False, "fixture is missing - the demo cannot run"))
            continue
        report = scan_paths([path])
        summary = report.summary
        score = summary.score if summary.score is not None else -1
        found = len(report.diagnostics)
        ok = score <= max_score and found >= min_diagnostics
        checks.append(
            Check(
                relative,
                ok,
                f"{score}/100 ({summary.grade}), {found} finding(s) - {why}",
            )
        )
    return checks


def check_audit() -> list[Check]:
    sys.path.insert(0, str(ROOT / "src"))
    from vexar_autofix.verifier import audit_patch

    checks: list[Check] = []
    for patch in MCP010_REFUSALS:
        after = MCP010_SOURCE.replace("urlopen(url)", f"urlopen(url, {patch})")
        problems = audit_patch("MCP010", MCP010_SOURCE, after)
        checks.append(
            Check(
                f"reject {patch}",
                bool(problems),
                problems[0] if problems else "ACCEPTED - the audit can be fooled",
            )
        )
    for patch in MCP010_ACCEPTS:
        after = MCP010_SOURCE.replace("urlopen(url)", f"urlopen(url, {patch})")
        problems = audit_patch("MCP010", MCP010_SOURCE, after)
        checks.append(
            Check(
                f"accept {patch}",
                not problems,
                "accepted" if not problems else problems[0],
            )
        )
    return checks


def render_markdown(checks: list[Check]) -> str:
    passed = sum(1 for c in checks if c.ok)
    lines = [
        f"**Self-audit: {passed}/{len(checks)} claims reproduce.**",
        "",
        "| Claim | Result | Detail |",
        "|---|---|---|",
    ]
    for check in checks:
        lines.append(f"| `{check.name}` | {'pass' if check.ok else 'FAIL'} | {check.detail} |")
    if passed != len(checks):
        lines.extend(
            [
                "",
                "A number on the demo page no longer reproduces. Either fix the regression or "
                "update the published figure **and** the commit it is attributed to - do not "
                "leave the page claiming something the code stopped doing.",
            ]
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify the repository's published claims.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable results.")
    parser.add_argument("--out", type=Path, default=None, help="Write the markdown report here.")
    args = parser.parse_args(argv)

    checks = check_fixtures() + check_audit()
    markdown = render_markdown(checks)
    if args.out:
        args.out.write_text(markdown + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps([check.__dict__ for check in checks], indent=2))
    else:
        print(markdown)

    return 0 if all(check.ok for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
