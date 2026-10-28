"""Verification.

This module is the reason the project is not a chat wrapper. It answers one question about
a candidate patch -- "is this strictly better code?" -- using the same scanner that found
the problem. No model output is ever accepted on its own authority.
"""

from __future__ import annotations

import re
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


# --------------------------------------------------------------------------------------
# Patch audit: does the patch actually implement the remedy, or did it just silence the rule?
#
# Clearing a rule is not the same as fixing the code. A model can remove a finding by
# flipping a boolean, deleting the call, or writing a validation that checks the wrong
# thing -- and the scanner, which matches patterns, will accept all three. These checks are
# deterministic and rule-specific, so they cost nothing and cannot themselves hallucinate.
#
# The bar is deliberately "would a security reviewer accept this", not "is it perfect".
# A patch that trips a check is rejected and the reason is fed back to the model, which is
# cheaper than a human catching it in review and far cheaper than shipping it.
# --------------------------------------------------------------------------------------

# Anti-patterns per rule, as (pattern, explanation). Every rule in AUTOFIXABLE has an
# entry here or in REMEDY_MARKERS below -- a fixable rule without an audit is a rule whose
# patches are accepted on the scanner's word alone. Each pattern looks only at lines the
# patch ADDED, so pre-existing code cannot trigger a rejection.
SMELLS: dict[str, tuple[tuple[str, str], ...]] = {
    "MCP005": (
        (
            r"shell\s*=\s*False",
            "keeps the shell plumbing alive by flipping shell=False while still passing the "
            "command as one string; subprocess then looks for a file literally named after "
            "the whole command, so any command with arguments fails. Pass an argv list, e.g. "
            "subprocess.run(shlex.split(cmd), check=False)",
        ),
    ),
    "MCP010": (
        (
            r"timeout\s*=\s*None",
            "timeout=None is the same as no timeout: the request can block forever. Pass a "
            "bounded number of seconds",
        ),
        (
            r"timeout\s*=\s*(float\s*\(\s*)?[\"']?inf",
            "an infinite timeout is not a timeout. Pass a bounded number of seconds",
        ),
        (
            r"timeout\s*=\s*10\s*\*\*\s*\d+|timeout\s*=\s*\d+e\d+",
            "a timeout written as a power of ten is not a bound. Pass a realistic number of seconds",
        ),
        (
            r"timeout\s*=\s*\d{5,}",
            "a timeout measured in days is indistinguishable from no timeout at all in "
            "practice. Pass a realistic number of seconds",
        ),
    ),
    "MCP007": (
        (
            r"startswith\s*\(",
            "confines the path by string prefix, so '<base>-evil' passes a check against "
            "'<base>'. Use os.path.commonpath, or Path(resolved).is_relative_to(base)",
        ),
        (
            r"abspath\s*\(\s*[\"']\.[\"']\s*\)",
            "derives the base directory from the current working directory, so the "
            "confinement boundary moves with the process. Use an explicit, fixed base",
        ),
    ),
}

# A remedy is only credible if the patch mentions the mechanism that makes it work. Absence
# is not proof of a bad patch, so these are checked only for rules where the canonical fix
# has a uniquely identifiable shape.
REMEDY_MARKERS: dict[str, tuple[str, str]] = {
    "MCP010": (
        r"timeout\s*=\s*(?!None)[A-Za-z0-9_.]+",
        "no bounded timeout found; pass an explicit number of seconds or a named constant",
    ),
    "MCP005": (
        r"(shlex\.split|\[[^\]]*\]|\.split\s*\()",
        "the command is still passed as a single string; pass an argv list "
        "(shlex.split(cmd) or [prog, *args])",
    ),
    "MCP006": (
        r"(ALLOWED_HOSTS|allowlist|allow_list|hostname\s*(not\s+)?in\s|netloc\s*(not\s+)?in\s)",
        "no host allowlist found. Validating the scheme does not prevent SSRF: "
        "http://169.254.169.254/latest/meta-data/ has a valid scheme and host",
    ),
}


def audit_patch(rule_id: str, before: str, after: str) -> list[str]:
    """Return reasons this patch should NOT be trusted, or an empty list.

    Only lines added by the patch are inspected, so existing code cannot trigger a false
    rejection. Rejection is fail-closed on purpose: a retry costs a fraction of a cent, and
    a wrong patch costs the user's trust in every other patch the tool produces.
    """
    before_lines = set(before.splitlines())
    added = "\n".join(line for line in after.splitlines() if line not in before_lines)
    if not added.strip():
        return []

    problems: list[str] = []
    for pattern, explanation in SMELLS.get(rule_id, ()):
        if re.search(pattern, added):
            problems.append(f"{rule_id} patch is not a real fix: {explanation}")
            break  # one reason per rule is enough feedback for the next attempt

    marker = REMEDY_MARKERS.get(rule_id)
    if marker and not problems:
        pattern, explanation = marker
        if not re.search(pattern, added):
            problems.append(f"{rule_id} patch does not implement the remedy: {explanation}")

    return problems


_SINK_CALL = re.compile(r"(os\.system|subprocess\.\w+|eval)\s*\(")


def review_notes(before: str, after: str) -> list[str]:
    """Non-blocking observations a human should see alongside the diff.

    Deleting a dangerous call is sometimes correct and sometimes silently drops
    functionality; no mechanical check can tell the difference, so this is reported rather
    than enforced.

    Deleting and *replacing* look identical line-by-line, so the comparison is on call-site
    counts. A sink swapped for an equivalent call is a replacement and needs no warning; a
    call site that disappeared needs a human to confirm nothing was lost.
    """
    before_calls = len(_SINK_CALL.findall(before))
    after_calls = len(_SINK_CALL.findall(after))
    if after_calls >= before_calls:
        return []

    gone = [
        line.strip()
        for line in before.splitlines()
        if line not in after.splitlines() and _SINK_CALL.search(line)
    ]
    detail = f": {gone[0][:80]}" if gone else ""
    return [
        f"{before_calls - after_calls} sink call site(s) removed entirely -- "
        f"confirm no functionality was dropped{detail}"
    ]
