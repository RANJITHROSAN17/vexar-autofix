#!/usr/bin/env python3
"""Route newly opened human issues to vexar-autofix domain and type labels."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

AREA_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("area/verifier", re.compile(r"\b(verifier|audit_patch|smells|remedy_markers|mcp0\d\d|bypass)\b", re.I)),
    ("area/agent", re.compile(r"\b(agent|bucket|refused|reason code|retry|nemotron|nebius|prompt)\b", re.I)),
    ("area/cli", re.compile(r"\b(cli|--report|--policy|--allow-rules|--block-rules|--json|sarif)\b", re.I)),
    ("area/ci", re.compile(r"\b(workflow|github action|action\.yml|self-audit|ci)\b", re.I)),
    ("area/release", re.compile(r"\b(pypi|pyproject|vexar_mcp|mcp_doctor|package|version)\b", re.I)),
    ("area/docs", re.compile(r"\b(readme|roadmap\.md|verification\.md|docs/|documentation)\b", re.I)),
)


def classify(title: str, body: str) -> list[str]:
    """Return high-confidence area/* and type/* labels from issue text."""
    text = f"{title or ''}\n{body or ''}"
    labels: list[str] = []
    for name, pattern in AREA_PATTERNS:
        if pattern.search(text):
            labels.append(name)
    if re.search(r"\b(bypass|smell|exploit|unsafe|vulnerability)\b", text, re.I):
        labels.append("type/security")
    elif re.search(r"\b(proof|corpus|artifact|reproduc)\b", text, re.I):
        labels.append("type/proof")
    elif re.search(r"\b(bug|crash|regression|error|traceback|broken)\b", text, re.I):
        labels.append("type/bug")
    elif re.search(r"\b(feat|feature|enhancement|proposal|support)\b", text, re.I):
        labels.append("type/feature")
    return labels


class GitHubClient:
    """Minimal REST client for adding labels without clobbering existing ones."""

    def __init__(self, repo: str, token: str) -> None:
        self.base_url = f"https://api.github.com/repos/{repo}"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "vexar-autofix-labeler",
        }

    def request(self, method: str, path: str, payload: object = None) -> object:
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=self.headers, method=method)
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else None

    def apply_labels(self, number: int, labels: list[str]) -> list[str]:
        issue = self.request("GET", f"/issues/{number}") or {}
        existing = {
            entry["name"]
            for entry in (issue.get("labels", []) if isinstance(issue, dict) else [])
            if isinstance(entry, dict)
        }
        to_add = [label for label in labels if label not in existing]
        if to_add:
            self.request("POST", f"/issues/{number}/labels", {"labels": to_add})
        return to_add


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Label a new issue from its text.")
    parser.add_argument("--event", type=Path, default=None)
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    event_path = args.event or os.environ.get("GITHUB_EVENT_PATH")
    if not event_path or not Path(event_path).is_file():
        print("error: no event JSON available", file=sys.stderr)
        return 2

    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    issue = event.get("issue") or {}
    if not issue.get("number") or "pull_request" in issue:
        return 0

    body = issue.get("body") or ""
    if "<!-- roadmap-id:" in body or "<!-- roadmap-status -->" in body:
        return 0

    labels = classify(issue.get("title") or "", body)
    if not labels:
        print("[labeler] no confident match; leaving unlabelled")
        return 0
    if args.dry_run:
        print(f"[dry-run] #{issue['number']} -> {', '.join(labels)}")
        return 0

    token = os.environ.get("GITHUB_TOKEN", "")
    if not args.repo or not token:
        print("error: GITHUB_REPOSITORY and GITHUB_TOKEN must be set", file=sys.stderr)
        return 2
    try:
        added = GitHubClient(args.repo, token).apply_labels(int(issue["number"]), labels)
    except urllib.error.HTTPError as exc:
        print(f"GitHub API error ({exc.code}): {exc.read().decode('utf-8', 'replace')}")
        return 1
    print(f"[labeler] #{issue['number']} added: {', '.join(added) or 'nothing new'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
