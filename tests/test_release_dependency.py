"""The release must use the canonical scanner namespace and an index dependency."""

from __future__ import annotations

import ast
import re
from importlib.metadata import requires
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_scanner_dependency_is_a_release_not_a_vcs_reference() -> None:
    dependencies = requires("vexar-autofix") or []
    assert "vexar-mcp==0.3.0" in dependencies
    assert not any("git+" in d for d in dependencies)


def test_verifier_and_self_audit_use_canonical_imports() -> None:
    for path in [ROOT / "src/vexar_autofix/verifier.py", ROOT / ".github/scripts/self_audit.py"]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = [node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        assert any(m and m.startswith("vexar_mcp") for m in modules)
        assert not any(m and m.startswith("mcp_doctor") for m in modules)


def test_pr_guide_does_not_shadow_injected_github_script_context() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/code-review-bot.yml").read_text())
    scripts = [
        step["with"]["script"]
        for step in workflow["jobs"]["guide"]["steps"]
        if "actions/github-script@" in step.get("uses", "")
    ]
    assert scripts
    for script in scripts:
        assert not re.search(r"\b(?:const|let|var)\s+(?:context|github)\b", script)
        assert "context.repo" in script
        assert "roadmapContext.trim()" in script
