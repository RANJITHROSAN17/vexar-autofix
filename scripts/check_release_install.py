"""Run with a clean wheel installation to verify namespaces and dependency metadata."""

from __future__ import annotations

from importlib.metadata import distribution


def check_install() -> None:
    """Fail if the distributions overlap or the scanner is not the pinned release."""
    scanner = distribution("vexar-mcp")
    autofix = distribution("vexar-autofix")
    assert scanner.version == "0.3.0", scanner.version
    assert "vexar-mcp==0.3.0" in (autofix.requires or []), autofix.requires
    assert scanner.files and autofix.files, "distribution file lists are required"
    scanner_files = {scanner.locate_file(p).resolve() for p in scanner.files}
    autofix_files = {autofix.locate_file(p).resolve() for p in autofix.files}
    overlap = scanner_files & autofix_files
    assert not overlap, f"distribution file overlap: {overlap}"

    import vexar_mcp

    import vexar_autofix
    from vexar_autofix.verifier import scan

    assert callable(scan)
    assert callable(vexar_mcp.scan_paths)
    assert vexar_autofix.__version__ == autofix.version
    print(f"OK: Vexar-MCP {scanner.version} + vexar-autofix {autofix.version}; no file overlap")


if __name__ == "__main__":
    check_install()
