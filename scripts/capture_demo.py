#!/usr/bin/env python3
"""Capture a real demo run into a static site's data file.

GitHub Pages can only serve static files, and a browser cannot hold an API key. So the demo
is split: this script performs the real model calls inside GitHub Actions, where the key is a
secret, and writes the result to `docs/data/runs.json`. Pages renders that file.

The consequence is honest and worth stating: the site shows **recorded** runs, not a live
button. Each record carries its timestamp, commit, and the models that produced it, so a
reader can see exactly when it was true and re-run the same command themselves.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from vexar_autofix import MODEL_ROLES, NebiusClient, autofix  # noqa: E402
from vexar_autofix.clients import DEFAULT_BASE_URL  # noqa: E402

FIXTURES = ("vulnerable_server.py", "helper_delegation_server.py", "clean_server.py")
OUT = ROOT / "docs" / "data" / "runs.json"


def commit_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            cwd=ROOT,
        ).stdout.strip()
    except OSError:
        return "unknown"


def main() -> int:
    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        print("NEBIUS_API_KEY is not set; refusing to write a demo file with invented data.", file=sys.stderr)
        return 2

    client = NebiusClient(key, os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL), timeout=180)
    runs = []
    for fixture in FIXTURES:
        target = ROOT / "examples" / fixture
        print(f"running {fixture} ...", file=sys.stderr, flush=True)
        report = autofix(client, target, max_attempts=3, check_tests=False)
        if report.get("clean"):
            runs.append({"fixture": fixture, "clean": True, "before": report["before"]})
            continue
        runs.append(
            {
                "fixture": fixture,
                "clean": False,
                "before": report["before"],
                "after": report.get("after"),
                "triage": report["triage"],
                "attempts": [
                    {
                        "rule_id": a.get("rule_id"),
                        "attempt": a["number"],
                        "model_role": a["model_role"],
                        "applied": a["applied"],
                        "accepted": a["accepted"],
                        "failure": a["failure"],
                    }
                    for a in report["attempts"]
                ],
                "fixed": report["fixed"],
                "unfixed": report["unfixed"],
                "skipped": report.get("skipped", []),
                "refused": report["refused"],
                "review": report.get("review", []),
                "diff": report.get("diff", ""),
                "verified": report.get("verified", False),
            }
        )

    payload = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": commit_sha(),
        "provider": "Nebius Token Factory",
        "models": MODEL_ROLES,
        "usage": client.usage.__dict__,
        "provenance": (
            "Produced by scripts/capture_demo.py inside GitHub Actions, where NEBIUS_API_KEY "
            "is a repository secret. The browser never sees a key, which is why this is a "
            "recorded demo rather than a live one."
        ),
        "runs": runs,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(runs)} fixture(s))", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
