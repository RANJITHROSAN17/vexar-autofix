"""Command line entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .agent import autofix
from .clients import (
    CANDIDATE_BASE_URLS,
    DEFAULT_BASE_URL,
    MODEL_ROLES,
    Client,
    MockClient,
    NebiusClient,
)


def _build_client(args: argparse.Namespace) -> Client:
    if args.provider == "mock":
        print("[rehearsal] mock provider: no network, no model. Edits are fake.\n", file=sys.stderr)
        return MockClient(rehearse_accept=args.rehearse_accept)
    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        raise SystemExit("error: NEBIUS_API_KEY is not set")
    return NebiusClient(key, os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL))


def _print_report(report: dict[str, Any], apply: bool, target: Path) -> None:
    print(f"target      {report['target']}")
    if report.get("clean"):
        print(f"result      clean already ({report['before']['score']}/100 {report['before']['grade']})")
        return

    before = report["before"]
    print(f"before      {before['score']}/100 ({before['grade']}), {before['findings']} findings")

    for v in report["triage"]:
        print(f"  {v['verdict']:<10} {v['rule_id']} @{v['line']}  {v['reason'][:66]}")

    for attempt in report["attempts"]:
        status = "ACCEPTED" if attempt["accepted"] else f"rejected: {(attempt['failure'] or '')[:52]}"
        print(
            f"  {attempt.get('rule_id', '?')} attempt {attempt['number']} "
            f"[{attempt['model_role']}] {attempt['applied']} edit(s) -> {status}"
        )

    fixed = report.get("fixed", [])
    if fixed:
        print(f"fixed       {len(fixed)} finding(s); {len(report.get('unfixed', []))} left to a human")
    if report.get("refused"):
        print(f"refused     {len(report['refused'])} finding(s) outside the autofixable rule set")

    if report.get("verified"):
        print(f"after       {report['after']['score']}/100 ({report['after']['grade']})")
        print(f"tests       {'unchanged / passing' if report['tests_ok'] in (True, None) else 'FAILED'}")
        print()
        print(report["diff"], end="")
        if apply:
            target.write_text(str(report["patch"]), encoding="utf-8")
            print(f"\napplied to {target}")
        else:
            print("\n(dry run -- pass --apply to write the patch)")
    else:
        print("not fixed   verification never passed; target file untouched")

    usage = report.get("usage", {})
    print(f"\nusage       {usage.get('calls', 0)} model calls, ~${usage.get('cost_usd', 0):.4f}")


def _preflight() -> int:
    """Answer three questions before anything else can fail: key valid? endpoint right? models exist?

    Wrong region and wrong key both surface as a confusing error mid-run, and at hackathon
    time that costs hours. This turns both into one clear line each.
    """
    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        print(
            "NEBIUS_API_KEY is not set.\n"
            "  1. Create an API key at https://tokenfactory.nebius.com\n"
            "  2. export NEBIUS_API_KEY=...   (do not paste it into a chat or a file)",
            file=sys.stderr,
        )
        return 2

    override = os.environ.get("NEBIUS_BASE_URL")
    candidates = (override,) if override else CANDIDATE_BASE_URLS

    print("probing endpoints...", flush=True)
    working: tuple[str, list[str]] | None = None
    for base in candidates:
        client = NebiusClient(key, base, timeout=15)
        try:
            catalogue = client.models()
        except urllib.error.HTTPError as exc:
            reason = {401: "key rejected", 403: "key lacks access", 404: "no catalogue here"}
            print(f"  {base:<52} {exc.code} {reason.get(exc.code, '')}", flush=True)
            continue
        except (urllib.error.URLError, TimeoutError) as exc:
            print(f"  {base:<52} unreachable ({type(exc).__name__})", flush=True)
            continue
        print(f"  {base:<52} OK, {len(catalogue)} model(s)", flush=True)
        working = (base, catalogue)
        break

    if working is None:
        print(
            "\nNo endpoint accepted the key. The usual causes, in order:\n"
            "  - the key is an AI Cloud / service-account key, not a Token Factory key\n"
            "  - the key was copied with whitespace or a trailing newline\n"
            "  - the key belongs to a project without Token Factory enabled",
            file=sys.stderr,
        )
        return 3

    base, catalogue = working
    print(f"\nendpoint   {base}")
    print(f"models     {len(catalogue)} available\n")

    missing: list[str] = []
    for role, model in MODEL_ROLES.items():
        present = model in catalogue
        print(f"  {'OK ' if present else 'MISSING'} {role:<9} {model}")
        if not present:
            missing.append(model)

    if missing:
        print("\nRouted models missing from the catalogue. Pick replacements and set:", file=sys.stderr)
        for role in MODEL_ROLES:
            print(f"  AUTOFIX_MODEL_{role.upper()}=<id from the list below>", file=sys.stderr)
        print("\nAvailable:", file=sys.stderr)
        for model in catalogue:
            print(f"  {model}", file=sys.stderr)
        return 1

    if not override and base != DEFAULT_BASE_URL:
        print(f"\nNote: this project answers at {base}.", file=sys.stderr)
        print(f"  export NEBIUS_BASE_URL={base}", file=sys.stderr)

    print("\nready: vexar-autofix --target examples/vulnerable_server.py")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vexar-autofix",
        description="Remediate MCP server findings autonomously, and verify every patch.",
    )
    parser.add_argument("--target", type=Path, help="file to audit and patch")
    parser.add_argument("--provider", choices=("nebius", "mock"), default="nebius")
    parser.add_argument("--apply", action="store_true", help="write the verified patch back to --target")
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--no-tests", action="store_true", help="skip the target's test suite")
    parser.add_argument("--json", action="store_true", help="emit the full report as JSON")
    parser.add_argument(
        "--rehearse-accept",
        action="store_true",
        help="mock only: replay a known-good patch to exercise the accept path",
    )
    parser.add_argument(
        "--preflight",
        "--list-models",
        dest="preflight",
        action="store_true",
        help="check the key, find the working endpoint, and confirm the routed models exist",
    )
    args = parser.parse_args(argv)

    if args.preflight:
        return _preflight()

    if args.target is None:
        parser.error("--target is required unless --preflight is used")
    if not args.target.is_file():
        print(f"error: {args.target} is not a file", file=sys.stderr)
        return 2

    try:
        client: Client = _build_client(args)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2

    report = autofix(client, args.target, max_attempts=args.max_attempts, check_tests=not args.no_tests)

    if args.json:
        print(json.dumps(report, indent=2))
        return 0 if report.get("verified") or report.get("clean") else 1

    _print_report(report, args.apply, args.target)
    return 0 if report.get("verified") or report.get("clean") else 1


if __name__ == "__main__":
    raise SystemExit(main())
