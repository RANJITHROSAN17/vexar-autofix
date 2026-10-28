"""Reference secure, token-efficient MCP server scoring 100/100 (A+)."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path("/srv/workspace").resolve()
ALLOWED_HOSTS = {"api.github.com", "pypi.org"}


class _StubMCP:
    def tool(self, name: str | None = None, description: str | None = None):  # type: ignore[no-untyped-def]
        def _wrap(fn):  # type: ignore[no-untyped-def]
            return fn

        return _wrap


mcp = _StubMCP()


@mcp.tool()
def read_workspace_note(relative_path: str, max_lines: int = 100) -> str:
    """Read a UTF-8 text note inside the confined workspace directory.

    Args:
        relative_path: Relative path to the note file inside `/srv/workspace`.
        max_lines: Maximum number of lines to return (capped at 500).
    """
    safe_limit = min(max_lines, 500)
    candidate = (BASE_DIR / relative_path).resolve()
    if not candidate.is_relative_to(BASE_DIR):
        raise ValueError("Path escapes workspace root")
    with open(candidate, encoding="utf-8") as fh:
        lines = [fh.readline() for _ in range(safe_limit)]
    return "".join(lines)


@mcp.tool()
def check_package_metadata(package_url: str) -> str:
    """Validate an HTTPS package metadata URL against the allowlist before fetching.

    Args:
        package_url: HTTPS URL on `api.github.com` or `pypi.org`.
    """
    import urllib.request

    parsed = urlparse(package_url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError("Disallowed URL target")
    with urllib.request.urlopen(package_url, timeout=5) as resp:
        return str(resp.status)
