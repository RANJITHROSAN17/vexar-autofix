"""Tests for the repository bots.

A bot is code that acts with write access to the issue tracker, and a wrong bot is worse than
no bot: it opens duplicate issues, closes live ones, or comments on every push until people
mute it. These tests pin the decisions worth getting wrong.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / ".github" / "scripts"


def load(name: str) -> ModuleType:
    """Import a script by path so the tests do not need it to be a package."""
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def roadmap() -> dict:
    return json.loads((ROOT / ".github" / "roadmap.json").read_text(encoding="utf-8"))


# ── the manifest ────────────────────────────────────────────────────────────────────────────


def test_manifest_ids_are_unique_and_labels_exist() -> None:
    bot = load("sync_roadmap_issues")
    data = roadmap()
    ids = [item["id"] for item in data["items"]]
    assert len(ids) == len(set(ids))
    known = {label["name"] for label in data["labels"]}
    for item in data["items"]:
        assert set(item["labels"]).issubset(known), f"{item['id']} uses an undefined label"
        assert f"<!-- roadmap-id: {item['id']} -->" in bot.render_issue_body(item, data)


def test_every_queued_item_is_actionable() -> None:
    """An issue with no acceptance criteria cannot be agreed to be done."""
    for item in roadmap()["items"]:
        if item.get("status") == "shipped":
            continue
        assert item.get("acceptance_criteria"), f"{item['id']} has no acceptance criteria"
        assert item.get("files"), f"{item['id']} names no files"


def test_shipped_items_record_where_they_shipped() -> None:
    for item in roadmap()["items"]:
        if item.get("status") == "shipped":
            assert item.get("shipped_in"), f"{item['id']} shipped nowhere"


def test_plan_document_exists() -> None:
    """The status issue links the plan; a dead link in a bot comment is still a dead link."""
    plan = roadmap().get("plan_doc", "ROADMAP.md")
    assert (ROOT / plan).is_file()


# ── curator ─────────────────────────────────────────────────────────────────────────────────


def test_curator_opens_only_unseen_queued_items() -> None:
    bot = load("sync_roadmap_issues")
    data = {
        "max_open_roadmap_issues": 2,
        "items": [
            {"id": "A", "title": "a", "summary": "s", "motivation": "m"},
            {"id": "B", "title": "b", "summary": "s", "motivation": "m"},
            {"id": "C", "title": "c", "summary": "s", "motivation": "m", "status": "shipped"},
        ],
    }
    existing = [{"state": "closed", "body": "<!-- roadmap-id: A -->\ndone"}]
    opened = bot.select_items_to_open(data, existing)
    assert [item["id"] for item in opened] == ["B"], "shipped or seen items must not reopen"


def test_curator_honours_the_count_limit() -> None:
    bot = load("sync_roadmap_issues")
    data = {
        "max_open_roadmap_issues": 10,
        "items": [
            {"id": "A", "title": "a", "summary": "s", "motivation": "m"},
            {"id": "B", "title": "b", "summary": "s", "motivation": "m"},
        ],
    }
    assert len(bot.select_items_to_open(data, [], limit=1)) == 1


def test_curator_closes_shipped_items_only() -> None:
    bot = load("sync_roadmap_issues")
    data = {
        "items": [
            {"id": "A", "title": "a", "summary": "s", "motivation": "m", "status": "shipped"},
            {"id": "B", "title": "b", "summary": "s", "motivation": "m"},
        ]
    }
    issues = [
        {"number": 1, "state": "open", "body": "<!-- roadmap-id: A -->"},
        {"number": 2, "state": "open", "body": "<!-- roadmap-id: B -->"},
    ]
    assert [number for number, _ in bot.select_shipped_issues_to_close(data, issues)] == [1]


def test_curator_refreshes_a_body_that_drifted() -> None:
    bot = load("sync_roadmap_issues")
    data = roadmap()
    item = next(i for i in data["items"] if i.get("status") != "shipped")
    issue = {
        "number": 7,
        "state": "open",
        "title": item["title"],
        "body": f"<!-- roadmap-id: {item['id']} -->\nstale text",
    }
    assert [number for number, _ in bot.select_issues_to_refresh(data, [issue])] == [7]


# ── status ──────────────────────────────────────────────────────────────────────────────────


def test_status_picks_priority_before_manifest_order() -> None:
    mod = load("roadmap_status")
    data = {
        "items": [
            {"id": "LOW", "title": "low", "labels": []},
            {"id": "P0", "title": "urgent", "labels": ["priority/p0"]},
        ]
    }
    assert [item["id"] for item in mod.pick_next(data, [])] == ["P0", "LOW"]


def test_status_does_not_recommend_work_already_claimed() -> None:
    mod = load("roadmap_status")
    data = {"items": [{"id": "A", "title": "a"}, {"id": "B", "title": "b"}]}
    issues = [{"state": "open", "body": "<!-- roadmap-id: A -->"}]
    assert [item["id"] for item in mod.pick_next(data, issues)] == ["B"]


def test_status_reports_a_version_that_was_never_released() -> None:
    mod = load("roadmap_status")
    assert mod.version_drift("0.2.6", "v0.2.1") is not None
    assert mod.version_drift("0.2.6", "v0.2.6") is None
    assert mod.version_drift(None, "v0.2.1") is None


def test_status_flags_a_plan_pointing_at_a_deleted_file(tmp_path: Path) -> None:
    mod = load("roadmap_status")
    data = {"items": [{"id": "A", "title": "a", "files": ["src/gone.py"]}]}
    assert mod.file_drift(data, tmp_path), "a missing file must be reported"
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "gone.py").write_text("")
    assert not mod.file_drift(data, tmp_path)


def test_status_treats_a_directory_to_be_created_as_a_plan_not_drift(tmp_path: Path) -> None:
    mod = load("roadmap_status")
    data = {"items": [{"id": "A", "title": "a", "files": ["benchmarks/rejections/"]}]}
    assert not mod.file_drift(data, tmp_path)


def test_status_body_is_marked_and_lists_the_plan() -> None:
    mod = load("roadmap_status")
    body = mod.render_status(roadmap(), [], root=ROOT, version=None, tag=None)
    assert body.startswith(mod.STATUS_MARKER), "the marker is how the issue is found again"
    assert ROADMAP_LINK in body


ROADMAP_LINK = "ROADMAP.md"


# ── PR context ──────────────────────────────────────────────────────────────────────────────


def test_pr_context_matches_a_named_file() -> None:
    mod = load("pr_context")
    data = {"items": [{"id": "G2", "title": "codes", "files": ["src/vexar_autofix/agent.py"]}]}
    matches = mod.match_items(data, ["src/vexar_autofix/agent.py"])
    assert [item["id"] for item, _, _ in matches] == ["G2"]


def test_pr_context_matches_a_sibling_test_file() -> None:
    """A PR that adds the test for a named module is working on the same item."""
    mod = load("pr_context")
    data = {"items": [{"id": "G3", "title": "proof", "files": ["src/vexar_autofix/report.py"]}]}
    assert mod.match_items(data, ["tests/test_report.py"])[0][0]["id"] == "G3"


def test_pr_context_refuses_to_guess_when_nothing_matches() -> None:
    mod = load("pr_context")
    text = mod.render_context(
        {"items": [{"id": "G1", "title": "t", "files": ["src/x.py"]}]}, ["README.md"], ""
    )
    assert "No roadmap item matches" in text


def test_pr_context_notices_a_missing_closes_reference() -> None:
    mod = load("pr_context")
    data = {"items": [{"id": "G2", "title": "t", "files": ["a.py"], "acceptance_criteria": ["it works"]}]}
    assert "Closes #N" in mod.render_context(data, ["a.py"], "just a change")
    assert "Closes #N" not in mod.render_context(data, ["a.py"], "Closes #42")


# ── self-audit ──────────────────────────────────────────────────────────────────────────────


def test_every_published_fixture_exists() -> None:
    mod = load("self_audit")
    for relative, _, _, _ in mod.FIXTURE_CLAIMS:
        assert (ROOT / relative).is_file(), f"{relative} is quoted in the README but missing"


def test_the_audit_refuses_every_absurd_timeout_and_accepts_the_real_ones() -> None:
    """This is the product's claim, asserted by the repository that makes it."""
    mod = load("self_audit")
    checks = mod.check_audit()
    failed = [check.name for check in checks if not check.ok]
    assert not failed, f"the published claim no longer holds: {failed}"


def test_self_audit_exit_code_reflects_a_failure(monkeypatch) -> None:
    mod = load("self_audit")
    monkeypatch.setattr(mod, "check_fixtures", lambda: [mod.Check("x", False, "drifted")])
    monkeypatch.setattr(mod, "check_audit", lambda: [])
    assert mod.main([]) == 1


def test_every_workflow_is_valid() -> None:
    """A malformed workflow fails as a run with no jobs, which looks like a broken bot."""
    validator = load("validate_workflows")
    problems: list[str] = []
    for path in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
        problems.extend(validator.validate_workflow(path))
    assert not problems, "\n".join(problems)


def test_no_workflow_is_a_placeholder() -> None:
    """A workflow that only echoes a description of itself is not a bot."""
    import yaml

    offenders: list[str] = []
    for path in sorted((ROOT / ".github" / "workflows").glob("*.y*ml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for name, job in (doc.get("jobs") or {}).items():
            steps = job.get("steps") or []
            echo_only = 0
            for step in steps:
                run = step.get("run")
                if not run:
                    continue
                body = [
                    line.strip()
                    for line in str(run).splitlines()
                    if line.strip() and not line.strip().startswith("#")
                ]
                if body and all(line.startswith("echo ") for line in body):
                    echo_only += 1
            # A conditional "nothing to do" note is fine; a job that only ever narrates is not.
            if steps and echo_only == len(steps):
                offenders.append(f"{path.name}: job '{name}' only echoes")
    assert not offenders, "\n".join(offenders)
