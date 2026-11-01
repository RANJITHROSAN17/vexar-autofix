"""The release must use the canonical scanner namespace and an index dependency."""

from __future__ import annotations

import ast
from importlib.metadata import requires
from pathlib import Path

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
