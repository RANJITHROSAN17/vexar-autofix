"""Verifier tests. No network, no key, no model.

The verifier is the only component whose correctness decides whether a patch is kept, so
it is tested against the cases that would silently corrupt a repository rather than only
against the happy path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vexar_autofix import Edit, Finding, apply_edits, verify

FIXTURE = Path(__file__).resolve().parent.parent / "examples" / "vulnerable_server.py"


def finding(index: int, rule: str, line: int, tool: str = "svc") -> Finding:
    return Finding(index=index, rule_id=rule, message="m", line=line, tool_name=tool, severity="error")


class TestAnchorEdits:
    def test_exact_anchor_applies_once(self) -> None:
        out, applied, problems = apply_edits("a = 1\nb = 2\n", [Edit("MCP005", "a = 1", "a = 9", "w")])
        assert (out, applied, problems) == ("a = 9\nb = 2\n", 1, [])

    def test_missing_anchor_fails_loudly_instead_of_guessing(self) -> None:
        # The model quoted code that is not in the file. Applying "something similar" would
        # silently edit the wrong thing, so this must be a hard failure.
        _, applied, problems = apply_edits("a = 1\n", [Edit("MCP005", "a =  1", "a = 9", "w")])
        assert applied == 0
        assert "anchor not found" in problems[0]

    def test_ambiguous_anchor_is_rejected(self) -> None:
        _, applied, problems = apply_edits("x = 1\nx = 1\n", [Edit("MCP005", "x = 1", "x = 2", "w")])
        assert applied == 0
        assert "ambiguous" in problems[0]

    def test_empty_anchor_is_rejected(self) -> None:
        # An empty string occurs everywhere; without this guard it would "apply" and corrupt.
        _, applied, problems = apply_edits("a = 1\n", [Edit("MCP005", "", "x", "w")])
        assert applied == 0
        assert "empty anchor" in problems[0]

    def test_unrelated_code_is_untouched(self) -> None:
        source = 'import os\n\ndef f():\n    os.system(x)\n\nKEEP = "yes"\n'
        out, _, _ = apply_edits(source, [Edit("MCP005", "    os.system(x)", "    run([x])", "w")])
        assert out.startswith("import os\n\ndef f():\n")
        assert out.endswith('KEEP = "yes"\n')


class TestVerifier:
    def test_a_clean_fix_is_accepted(self) -> None:
        before = [finding(0, "MCP005", 26), finding(1, "MCP001", 20)]
        after = [finding(0, "MCP001", 20)]
        result = verify(before, after, {("svc", "MCP005")}, True)
        assert result.ok, result.reason

    def test_line_shift_is_not_a_new_finding(self) -> None:
        # Deleting two lines and adding one renumbers everything below. A line-sensitive
        # comparison would call all of it "new findings" and reject a perfect patch.
        before = [finding(0, "MCP005", 25), finding(1, "MCP006", 33), finding(2, "MCP010", 33)]
        after = [finding(0, "MCP006", 32), finding(1, "MCP010", 32)]
        result = verify(before, after, {("svc", "MCP005")}, True)
        assert result.ok, result.reason
        assert result.new_findings == []

    def test_still_present_at_a_new_line_is_not_a_fix(self) -> None:
        # Moving a sink without removing it is not remediation.
        before = [finding(0, "MCP005", 25)]
        after = [finding(0, "MCP005", 40)]
        result = verify(before, after, {("svc", "MCP005")}, True)
        assert not result.ok
        assert "still present" in result.reason

    def test_regression_is_rejected_even_when_the_target_is_fixed(self) -> None:
        # Swapping shell=True for yaml.load would "fix" the rule and make things worse.
        before = [finding(0, "MCP005", 25)]
        after = [finding(0, "MCP013", 25)]
        result = verify(before, after, {("svc", "MCP005")}, True)
        assert not result.ok
        assert "introduced new findings" in result.reason

    def test_duplicate_instances_are_counted_not_deduped(self) -> None:
        # Two sinks in one tool are two queue entries, so clearing one is progress on that
        # entry. A set of rule ids would report "MCP005 gone" and stop hunting the second.
        before = [finding(0, "MCP005", 25), finding(1, "MCP005", 26)]
        after = [finding(0, "MCP005", 25)]
        result = verify(before, after, {("svc", "MCP005")}, True)
        assert result.ok
        assert result.cleared == ["MCP005 [svc] x1"]

    def test_zero_progress_is_rejected(self) -> None:
        before = [finding(0, "MCP005", 25), finding(1, "MCP005", 26)]
        result = verify(before, before, {("svc", "MCP005")}, True)
        assert not result.ok
        assert "still present" in result.reason

    def test_failing_tests_reject_a_rule_clean_patch(self) -> None:
        before = [finding(0, "MCP005", 25)]
        result = verify(before, [], {("svc", "MCP005")}, False)
        assert not result.ok
        assert "test suite failed" in result.reason

    def test_unknown_test_status_does_not_block_a_clean_fix(self) -> None:
        # A target with no test suite must not be treated as a failing one.
        before = [finding(0, "MCP005", 25)]
        assert verify(before, [], {("svc", "MCP005")}, None).ok


@pytest.mark.skipif(not FIXTURE.is_file(), reason="fixture not present")
class TestAgainstTheRealScanner:
    def test_fixture_reports_the_expected_rules(self) -> None:
        from vexar_autofix import scan

        rules = {f.rule_id for f in scan(FIXTURE)}
        assert {"MCP005", "MCP006", "MCP007", "MCP010"} <= rules

    def test_clean_fixture_is_clean(self) -> None:
        from vexar_autofix import scan, score_of

        clean = FIXTURE.parent / "clean_server.py"
        assert scan(clean) == []
        assert score_of(clean)[0] == 100
