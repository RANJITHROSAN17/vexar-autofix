"""Agent loop tests. Offline: the MockClient stands in for a model.

These test the control flow, not model quality. Model quality is measured by `eval/run_eval.py`
against real responses, because a test that asserts what a model "should" say goes red the
moment the model is upgraded and teaches nobody anything.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vexar_autofix import MockClient, autofix

FIXTURE = Path(__file__).resolve().parent.parent / "examples" / "vulnerable_server.py"


@pytest.fixture
def target(tmp_path: Path) -> Path:
    """A copy of the fixture, so a test can never modify the repository's own examples."""
    destination = tmp_path / FIXTURE.name
    destination.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    return destination


class TestPipeline:
    def test_a_model_that_emits_nothing_changes_nothing(self, target: Path) -> None:
        before = target.read_bytes()
        report = autofix(MockClient(), target, max_attempts=1, check_tests=False)
        assert report["verified"] is False
        assert "patch" not in report
        assert target.read_bytes() == before

    def test_failure_reasons_are_recorded_for_every_attempt(self, target: Path) -> None:
        report = autofix(MockClient(), target, max_attempts=2, check_tests=False)
        assert len(report["attempts"]) >= 2
        assert all(a["failure"] for a in report["attempts"])
        assert all(not a["accepted"] for a in report["attempts"])

    def test_accept_path_produces_a_verified_patch_and_a_score_delta(self, target: Path) -> None:
        report = autofix(MockClient(rehearse_accept=True), target, max_attempts=1, check_tests=False)
        assert report["verified"] is True
        assert report["after"]["score"] > report["before"]["score"]
        assert "shell=True" not in str(report["patch"])
        assert report["diff"].startswith("--- a/")

    def test_the_target_file_is_never_modified_by_a_dry_run(self, target: Path) -> None:
        before = target.read_bytes()
        autofix(MockClient(rehearse_accept=True), target, max_attempts=1, check_tests=False)
        assert target.read_bytes() == before, "a dry run wrote to the user's working tree"

    def test_escalation_is_used_only_after_a_failure(self, target: Path) -> None:
        report = autofix(MockClient(), target, max_attempts=2, check_tests=False)
        roles = [a["model_role"] for a in report["attempts"]]
        assert roles[0] == "patch", "the first attempt must not burn the expensive model"
        assert "escalate" in roles, "a failed verification must trigger escalation"


class TestTriage:
    def test_non_autofixable_rules_are_refused_not_attempted(self, target: Path) -> None:
        report = autofix(MockClient(), target, max_attempts=1, check_tests=False)
        refused = {r["rule_id"] for r in report["refused"]}
        attempted = {q["rule_id"] for q in report["queue"]}
        assert refused, "the fixture contains contract/schema findings"
        assert not (refused & attempted), "a refused rule must never enter the work queue"

    def test_only_confirmed_findings_are_queued(self, target: Path) -> None:
        report = autofix(MockClient(), target, max_attempts=1, check_tests=False)
        confirmed = {v["rule_id"] for v in report["triage"] if v["verdict"] == "confirmed"}
        assert {q["rule_id"] for q in report["queue"]} <= confirmed

    def test_every_finding_receives_a_verdict(self, target: Path) -> None:
        # A triage response that drops or reorders findings must still leave none unclassified.
        report = autofix(MockClient(), target, max_attempts=1, check_tests=False)
        assert len(report["triage"]) == report["before"]["findings"]

    def test_unparseable_triage_degrades_to_unclear(self, target: Path) -> None:
        class Garbage:
            usage = type("U", (), {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "calls": 1})()

            def complete(self, role, messages, *, json_mode=False):
                return "I think it is probably fine?"

        report = autofix(Garbage(), target, max_attempts=1, check_tests=False)
        assert all(v["verdict"] == "unclear" for v in report["triage"])
        assert report["queue"] == [], "unparseable triage must not queue any work"
        assert report["verified"] is False


class TestReport:
    def test_json_report_is_serialisable(self, target: Path) -> None:
        report = autofix(MockClient(rehearse_accept=True), target, max_attempts=1, check_tests=False)
        assert json.loads(json.dumps(report))["verified"] is True

    def test_report_prices_the_run(self, target: Path) -> None:
        report = autofix(MockClient(), target, max_attempts=1, check_tests=False)
        assert {"calls", "cost_usd"} <= set(report["usage"])
