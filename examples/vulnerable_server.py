"""Intentionally flawed MCP server showcasing MCP001-MCP008 detections."""

from __future__ import annotations

import os
import subprocess
import urllib.request
from typing import Any


class _StubMCP:
    def tool(self, name: str | None = None, description: str | None = None):  # type: ignore[no-untyped-def]
        def _wrap(fn):  # type: ignore[no-untyped-def]
            return fn

        return _wrap


mcp = _StubMCP()


@mcp.tool()
def run(cmd, limit: int = 1000) -> str:  # type: ignore[no-untyped-def]
    ""
    subprocess.run(cmd, shell=True, check=False)
    os.system(cmd)
    return str(limit)


@mcp.tool()
def fetch_and_save_remote_blob(target_url: str, output_path: str, payload: Any) -> str:
    """Fetch any remote URL and write its response straight to disk without validation."""
    with urllib.request.urlopen(target_url) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write(body)
    return str(payload)
