"""Verifier tests. No network, no key, no model.

The verifier is the only component whose correctness decides whether a patch is kept, so
it is tested against the cases that would silently corrupt a repository rather than only
against the happy path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vexar_autofix import Edit, Finding, apply_edits, verify

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "vulnerable_server.py"


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


class TestPatchAudit:
    """The audit is tested against the patches a real model actually produced.

    On the first live run, three of four accepted patches were wrong: MCP005 flipped
    `shell=False` and broke every command with arguments, MCP006 validated the scheme (which
    does nothing for SSRF), and MCP007 confined by string prefix (`/app-evil` passes `/app`).
    The scanner accepted all three. These are those patches.
    """

    SOURCE = (
        "import subprocess, os\n"
        "import urllib.request\n"
        "\n"
        "def run(cmd):\n"
        "    subprocess.run(cmd, shell=True, check=False)\n"
        "    os.system(cmd)\n"
        "\n"
        "def fetch(target_url):\n"
        "    with urllib.request.urlopen(target_url) as resp:\n"
        "        return resp.read()\n"
        "\n"
        "def save(output_path, data):\n"
        "    with open(output_path, 'w') as fh:\n"
        "        fh.write(data)\n"
    )

    def test_shell_false_with_a_string_is_rejected(self) -> None:
        from vexar_autofix import audit_patch

        after = self.SOURCE.replace(
            "    subprocess.run(cmd, shell=True, check=False)\n    os.system(cmd)\n",
            "    subprocess.run(cmd, shell=False, check=False)\n",
        )
        problems = audit_patch("MCP005", self.SOURCE, after)
        assert problems, "a patch that breaks the tool must not be accepted"
        assert "shell" in problems[0].lower()

    def test_argv_form_is_accepted(self) -> None:
        from vexar_autofix import audit_patch

        after = self.SOURCE.replace(
            "    subprocess.run(cmd, shell=True, check=False)\n    os.system(cmd)\n",
            "    subprocess.run(shlex.split(cmd), check=False)\n",
        )
        assert audit_patch("MCP005", self.SOURCE, after) == []

    def test_scheme_only_validation_is_not_an_ssrf_fix(self) -> None:
        from vexar_autofix import audit_patch

        after = self.SOURCE.replace(
            "    with urllib.request.urlopen(target_url) as resp:",
            "    parsed = urlparse(target_url)\n"
            "    if parsed.scheme not in ('http', 'https'):\n"
            "        raise ValueError('bad scheme')\n"
            "    with urllib.request.urlopen(target_url) as resp:",
        )
        problems = audit_patch("MCP006", self.SOURCE, after)
        assert problems, "http://169.254.169.254/ has a valid scheme; this fixes nothing"
        assert "allowlist" in problems[0].lower()

    def test_host_allowlist_is_accepted(self) -> None:
        from vexar_autofix import audit_patch

        after = self.SOURCE.replace(
            "    with urllib.request.urlopen(target_url) as resp:",
            "    host = urlparse(target_url).hostname\n"
            "    if host not in ALLOWED_HOSTS:\n"
            "        raise ValueError('host not allowed')\n"
            "    with urllib.request.urlopen(target_url) as resp:",
        )
        assert audit_patch("MCP006", self.SOURCE, after) == []

    def test_prefix_confinement_is_rejected(self) -> None:
        from vexar_autofix import audit_patch

        after = self.SOURCE.replace(
            "    with open(output_path, 'w') as fh:",
            "    resolved = os.path.abspath(output_path)\n"
            "    if not resolved.startswith(BASE_DIR):\n"
            "        raise ValueError('traversal')\n"
            "    with open(resolved, 'w') as fh:",
        )
        problems = audit_patch("MCP007", self.SOURCE, after)
        assert problems, "'/app-evil/x' passes a startswith('/app') check"
        assert "commonpath" in problems[0]

    def test_cwd_relative_base_is_rejected(self) -> None:
        from vexar_autofix import audit_patch

        after = self.SOURCE.replace(
            "    with open(output_path, 'w') as fh:",
            "    resolved = str(Path(output_path).resolve())\n"
            "    if not resolved.startswith(BASE_DIR):\n"
            "        raise ValueError('traversal')\n"
            "    with open(resolved, 'w') as fh:",
        )
        assert audit_patch("MCP007", self.SOURCE, after)

    def test_relative_to_confinement_is_accepted(self) -> None:
        from vexar_autofix import audit_patch

        after = self.SOURCE.replace(
            "    with open(output_path, 'w') as fh:",
            "    resolved = Path(output_path).resolve()\n"
            "    if not resolved.is_relative_to(BASE_DIR):\n"
            "        raise ValueError('traversal')\n"
            "    with open(resolved, 'w') as fh:",
        )
        assert audit_patch("MCP007", self.SOURCE, after) == []

    def test_preexisting_code_cannot_trigger_a_rejection(self) -> None:
        # The audit reads only added lines. A file that already contains `shell=True`
        # somewhere else must not poison an unrelated MCP006 patch.
        from vexar_autofix import audit_patch

        after = self.SOURCE.replace(
            "    with urllib.request.urlopen(target_url) as resp:",
            "    if urlparse(target_url).hostname not in ALLOWED_HOSTS:\n"
            "        raise ValueError('host')\n"
            "    with urllib.request.urlopen(target_url) as resp:",
        )
        assert audit_patch("MCP006", self.SOURCE, after) == []

    def test_sink_deletion_is_reported_but_not_blocked(self) -> None:
        # Deleting a dangerous call is sometimes right and sometimes drops functionality.
        # No mechanical check can tell, so it is surfaced to the human rather than enforced.
        from vexar_autofix import review_notes

        after = self.SOURCE.replace(
            "    subprocess.run(cmd, shell=True, check=False)\n    os.system(cmd)\n", ""
        )
        notes = review_notes(self.SOURCE, after)
        assert notes and "removed" in notes[0]


class TestReviewNotesAccuracy:
    """A replaced sink is not a deleted sink, and the note must not conflate them.

    The first version reported "removed entirely" for lines the model had swapped for an
    equivalent call (one live run replaced `os.system(cmd)` with a second
    `subprocess.run(shlex.split(cmd))`). Telling a reviewer a call was deleted when it was
    replaced sends them looking for missing functionality that is still there -- and, worse,
    hides the duplicate execution that actually happened.
    """

    def test_replacement_is_not_reported_as_a_deletion(self) -> None:
        from vexar_autofix import review_notes

        before = "def f(cmd):\n    os.system(cmd)\n"
        after = "def f(cmd):\n    subprocess.run(shlex.split(cmd), check=False)\n"
        assert review_notes(before, after) == []

    def test_deletion_is_reported_with_a_count(self) -> None:
        from vexar_autofix import review_notes

        before = "def f(cmd):\n    os.system(cmd)\n    subprocess.run(cmd, shell=True)\n"
        after = "def f(cmd):\n    return 1\n"
        notes = review_notes(before, after)
        assert notes and "2 sink call site(s) removed" in notes[0]

    def test_adding_a_call_is_not_a_review_note(self) -> None:
        from vexar_autofix import review_notes

        before = "def f(cmd):\n    return 1\n"
        after = "def f(cmd):\n    return subprocess.run(cmd)\n"
        assert review_notes(before, after) == []


def test_the_agent_never_reads_a_fixture_the_demo_can_rewrite() -> None:
    """Tests must not depend on `examples/`, which `--apply` legitimately rewrites.

    This was a live foot-gun: `--apply` half-fixed examples/vulnerable_server.py and the
    suite went red on ground truth rather than on a real defect.
    """
    for name in ("test_verifier.py", "test_agent.py"):
        source = (Path(__file__).resolve().parent / name).read_text(encoding="utf-8")
        for line in source.splitlines():
            if line.lstrip().startswith("FIXTURE ="):
                assert "examples" not in line, f"{name} points FIXTURE at the demo playground"
