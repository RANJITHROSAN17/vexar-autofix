"""The agent loop.

    scan -> triage -> patch -> verify -> (fail: escalate with feedback) -> verify

The working tree is never touched. Every attempt runs against a throwaway copy, and the
patch is only returned once the verifier has already approved it.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .clients import Client
from .models import Attempt, Edit, Finding, Verdict
from .prompts import PATCH_PROMPT, TRIAGE_PROMPT
from .verifier import (
    AUTOFIXABLE,
    apply_edits,
    audit_patch,
    build_diff,
    review_notes,
    run_tests,
    scan,
    score_of,
    verify,
)


def _finding_payload(findings: Sequence[Finding]) -> list[dict[str, Any]]:
    return [
        {
            "index": f.index,
            "rule_id": f.rule_id,
            "message": f.message,
            "line": f.line,
            "tool_name": f.tool_name,
        }
        for f in findings
    ]


def triage(client: Client, source: str, findings: Sequence[Finding]) -> list[Verdict]:
    """Ask the cheap model which findings are actually exploitable."""
    payload = json.dumps({"findings": _finding_payload(findings), "source": source})
    raw = client.complete(
        "triage",
        [{"role": "system", "content": TRIAGE_PROMPT}, {"role": "user", "content": payload}],
        json_mode=True,
    )
    try:
        verdicts = json.loads(raw)["verdicts"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return [Verdict(f, "unclear", "triage response was not parseable JSON") for f in findings]

    by_index = {f.index: f for f in findings}
    out: list[Verdict] = []
    for item in verdicts:
        finding = by_index.get(item.get("index"))
        if finding is None:
            continue
        out.append(Verdict(finding, str(item.get("verdict", "unclear")), str(item.get("reason", ""))))
    seen = {v.finding.index for v in out}
    out.extend(Verdict(f, "unclear", "triage skipped this finding") for f in findings if f.index not in seen)
    return out


def propose(
    client: Client,
    role: str,
    source: str,
    targets: Sequence[Finding],
    feedback: str | None,
) -> list[Edit]:
    """Ask a model for anchor edits, optionally with the reason the last attempt failed."""
    payload: dict[str, Any] = {
        "findings": _finding_payload(targets),
        "source": source,
    }
    if feedback:
        payload["previous_attempt_failed_because"] = feedback

    raw = client.complete(
        role,
        [{"role": "system", "content": PATCH_PROMPT}, {"role": "user", "content": json.dumps(payload)}],
        json_mode=True,
    )
    try:
        edits = json.loads(raw)["edits"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []
    return [
        Edit(
            rule_id=str(e.get("rule_id", "?")),
            find=str(e.get("find", "")),
            replace=str(e.get("replace", "")),
            why=str(e.get("why", "")),
        )
        for e in edits
        if isinstance(e, dict)
    ]


def autofix(
    client: Client,
    target: Path,
    *,
    max_attempts: int = 3,
    check_tests: bool = True,
) -> dict[str, Any]:
    """Remediate confirmed findings one at a time, verified at every step.

    One finding per attempt is a deliberate contract. Each accepted patch is small enough
    to review, a failure is attributable to a single change, and partial progress survives
    a finding the model cannot solve. The alternative -- one patch for every finding --
    fails as a unit, so one unsolvable rule discards all the good work with it.
    """
    original = target.read_text(encoding="utf-8")
    current = original
    findings = scan(target)
    before_score, before_grade = score_of(target)

    if not findings:
        return {
            "target": str(target),
            "clean": True,
            "before": {"score": before_score, "grade": before_grade},
        }

    verdicts = triage(client, current, findings)
    work = [v.finding for v in verdicts if v.confirmed and v.finding.rule_id in AUTOFIXABLE]

    result: dict[str, Any] = {
        "target": str(target),
        "clean": False,
        "before": {"score": before_score, "grade": before_grade, "findings": len(findings)},
        "triage": [
            {
                "rule_id": v.finding.rule_id,
                "line": v.finding.line,
                "verdict": v.verdict,
                "reason": v.reason,
            }
            for v in verdicts
        ],
        "queue": [{"rule_id": f.rule_id, "tool": f.tool_name, "line": f.line} for f in work],
        "fixed": [],
        "unfixed": [],
        "refused": [],
        "skipped": [],
        "review": [],
        "attempts": [],
        "verified": False,
    }

    # Every finding lands in exactly one bucket. Anything unaccounted for is a finding the
    # user cannot reason about, and a silently skipped finding is indistinguishable from a
    # clean one.
    for v in verdicts:
        rule = v.finding.rule_id
        if rule not in AUTOFIXABLE:
            result["refused"].append(
                {
                    "rule_id": rule,
                    "line": v.finding.line,
                    "why": "rule has no mechanical remedy; left to a human",
                }
            )
        elif not v.confirmed:
            result["skipped"].append(
                {
                    "rule_id": rule,
                    "line": v.finding.line,
                    "why": f"autofixable, but triage answered '{v.verdict}': {v.reason[:80]}",
                }
            )

    if not work:
        result["note"] = "no confirmed autofixable findings; nothing changed"
        result["usage"] = client.usage.__dict__
        return result

    with tempfile.TemporaryDirectory(prefix="vexar-autofix-") as tmp:
        workspace = Path(tmp) / target.name
        workspace.write_text(current, encoding="utf-8")

        for finding in work:
            feedback: str | None = None
            fixed_this = False

            for attempt in range(1, max_attempts + 1):
                role = "patch" if attempt == 1 else "escalate"
                edits = propose(client, role, current, [finding], feedback)
                patched, applied, problems = apply_edits(current, edits)
                record = Attempt(attempt, role, edits, applied)

                if not edits:
                    record.failure = "model emitted no edits"
                elif problems:
                    record.failure = "; ".join(problems)
                else:
                    # Does the patch implement the remedy, or did it just silence the rule?
                    # Checked before the scanner runs: a patch that clears the rule by
                    # flipping a boolean or deleting the call is worse than no patch.
                    smells = audit_patch(finding.rule_id, current, patched)
                    if smells:
                        record.failure = "; ".join(smells)
                        feedback = record.failure
                        result["attempts"].append(
                            {
                                **record.to_dict(),
                                "rule_id": finding.rule_id,
                                "tool": finding.tool_name,
                            }
                        )
                        continue

                    workspace.write_text(patched, encoding="utf-8")
                    after = scan(workspace)
                    tests_ok = run_tests(workspace.parent) if check_tests else None
                    targeted = {(finding.tool_name or "", finding.rule_id)}
                    outcome = verify(findings, after, targeted, tests_ok)
                    if outcome.ok:
                        record.accepted = True
                        result["attempts"].append(
                            {**record.to_dict(), "rule_id": finding.rule_id, "tool": finding.tool_name}
                        )
                        current = patched
                        findings = after
                        fixed_this = True
                        result["review"].extend(review_notes(current, patched))
                        result["fixed"].append(
                            {
                                "rule_id": finding.rule_id,
                                "tool": finding.tool_name,
                                "cleared": outcome.cleared,
                                "tests_ok": outcome.tests_ok,
                                "attempt": attempt,
                                "model_role": role,
                            }
                        )
                        break
                    record.failure = outcome.reason
                    feedback = outcome.reason

                result["attempts"].append(
                    {**record.to_dict(), "rule_id": finding.rule_id, "tool": finding.tool_name}
                )
                if feedback is None:
                    feedback = record.failure

            if not fixed_this:
                result["unfixed"].append({"rule_id": finding.rule_id, "tool": finding.tool_name})

        if current != original:
            workspace.write_text(current, encoding="utf-8")
            after_score, after_grade = score_of(workspace)
            result.update(
                verified=True,
                after={"score": after_score, "grade": after_grade},
                patch=current,
                diff=build_diff(original, current, target.name),
                tests_ok=run_tests(workspace.parent) if check_tests else None,
            )

    result["usage"] = client.usage.__dict__
    return result
