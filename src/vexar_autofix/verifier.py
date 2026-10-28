"""Verification.

This module is the reason the project is not a chat wrapper. It answers one question about
a candidate patch -- "is this strictly better code?" -- using the same scanner that found
the problem. No model output is ever accepted on its own authority.
"""

from __future__ import annotations

import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from .models import Edit, Finding, Verification

# Rules whose canonical remedy is mechanical enough to automate without judgement. Every
# other rule is reported but left to a human: a confidently wrong "fix" is worse than a
# known finding, and this list is small on purpose.
AUTOFIXABLE = frozenset({"MCP005", "MCP006", "MCP007", "MCP010"})


def scan(target: Path) -> list[Finding]:
    """Run the real scanner and flatten its diagnostics."""
    from mcp_doctor import ScanConfig, scan_paths

    report = scan_paths([target], ScanConfig())
    return [
        Finding(
            index=i,
            rule_id=d.rule_id,
            message=d.message,
            line=getattr(d, "line", 0),
            tool_name=getattr(d, "tool_name", None),
            severity=str(getattr(d, "severity", "")).split(".")[-1],
        )
        for i, d in enumerate(report.diagnostics)
    ]


def score_of(target: Path) -> tuple[int, str]:
    """Return the scanner's (score, grade) for a file."""
    from mcp_doctor import ScanConfig, scan_paths

    summary = scan_paths([target], ScanConfig()).summary
    return int(summary.score or 0), str(summary.grade)


def apply_edits(source: str, edits: Sequence[Edit]) -> tuple[str, int, list[str]]:
    """Apply edits as exact anchor replacements.

    No fuzzy matching, no line numbers, no whole-file rewrite. A patch either matches the
    source byte-for-byte or fails loudly, so a model cannot silently reformat, reorder, or
    delete code it was not asked to touch. Returns (patched_source, applied_count, problems).
    """
    text = source
    applied = 0
    problems: list[str] = []
    for edit in edits:
        if not edit.find:
            problems.append(f"{edit.rule_id}: empty anchor")
            continue
        count = text.count(edit.find)
        if count == 0:
            problems.append(f"{edit.rule_id}: anchor not found (model quoted code that is not in the file)")
            continue
        if count > 1:
            problems.append(f"{edit.rule_id}: anchor is ambiguous ({count} matches)")
            continue
        text = text.replace(edit.find, edit.replace, 1)
        applied += 1
    return text, applied, problems


def verify(
    before: Sequence[Finding],
    after: Sequence[Finding],
    targeted: set[tuple[str, str]],
    tests_ok: bool | None,
) -> Verification:
    """Decide whether a patch is an improvement, by comparing rule counts per tool.

    Comparison is deliberately line-shift-invariant. Matching on `(rule, tool, line)` looks
    stricter but is wrong: inserting or deleting a single line renumbers everything below
    it, so a perfect fix reads as "1 cleared, 6 new findings appeared" and is rejected.
    The question that matters is "does this tool still contain N instances of rule X",
    which survives reformatting and reordering.

    `targeted` holds (tool_name, rule_id) pairs that the attempt claimed to address. A
    targeted pair counts as fixed only when its instance count actually dropped; moving a
    sink to a different line is not remediation.
    """

    def counts(findings: Sequence[Finding]) -> Counter[tuple[str, str]]:
        return Counter((f.tool_name or "", f.rule_id) for f in findings)

    before_counts, after_counts = counts(before), counts(after)
    cleared: list[str] = []
    new: list[str] = []
    remaining: list[str] = []

    for key in before_counts | after_counts:
        tool, rule = key
        delta = after_counts[key] - before_counts[key]
        label = f"{rule} [{(tool or '<module>')[:24]}]"
        if delta < 0:
            cleared.append(f"{label} x{-delta}")
        elif delta > 0:
            new.append(f"{label} x{delta}")
        if key in targeted and after_counts[key] >= before_counts[key]:
            remaining.append(f"{label} x{after_counts[key]}")

    problems: list[str] = []
    if remaining:
        problems.append(f"targeted finding still present: {', '.join(remaining)}")
    if new:
        problems.append(f"patch introduced new findings: {', '.join(new)}")
    if tests_ok is False:
        problems.append("target test suite failed after the patch")

    return Verification(
        ok=not problems,
        cleared=cleared,
        remaining=remaining,
        new_findings=new,
        tests_ok=tests_ok,
        reason="verified" if not problems else "; ".join(problems),
    )


def run_tests(root: Path) -> bool | None:
    """Run the target project's own suite. Returns None when there is nothing to run."""
    if not any(root.rglob("test_*.py")):
        return None
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-x", "-q", str(root)],
            capture_output=True,
            check=False,
            text=True,
            timeout=600,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0


def build_diff(before: str, after: str, name: str) -> str:
    """Unified diff, so a human reviews the same artefact the verifier approved."""
    import difflib

    return "".join(
        difflib.unified_diff(
            before.splitlines(keepends=True),
            after.splitlines(keepends=True),
            f"a/{name}",
            f"b/{name}",
        )
    )
