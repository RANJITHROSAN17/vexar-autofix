"""Hosted demo (Hugging Face Spaces / any ASGI host).

Deliberately narrow: the demo only audits the three bundled fixtures. That keeps it a real
working product rather than a screenshot, while making an open endpoint useless to abuse --
a visitor cannot point it at arbitrary paths, and every run costs a known handful of cheap
model calls.

Run locally:
    pip install -e ".[demo]"
    export NEBIUS_API_KEY=...
    uvicorn demo.app:app --reload --port 8000
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse

from vexar_autofix import NebiusClient, autofix
from vexar_autofix.clients import DEFAULT_BASE_URL

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
FIXTURES = sorted(p.name for p in EXAMPLES.glob("*.py") if p.name != "__init__.py")

app = FastAPI(title="vexar-autofix demo")

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>vexar-autofix</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
 :root {{ color-scheme: dark; }}
 body {{ font: 15px/1.55 ui-monospace,SFMono-Regular,Menlo,monospace; background:#0e1116;
        color:#c9d1d9; margin:0; padding:32px 20px; }}
 .wrap {{ max-width:900px; margin:0 auto; }}
 h1 {{ font-size:20px; margin:0 0 4px; color:#e6edf3; }}
 .sub {{ color:#8b949e; margin-bottom:24px; }}
 form {{ display:flex; gap:10px; flex-wrap:wrap; margin-bottom:24px; }}
 select,button {{ font:inherit; padding:8px 12px; border-radius:6px;
        border:1px solid #30363d; background:#161b22; color:#e6edf3; }}
 button {{ background:#238636; border-color:#2ea043; cursor:pointer; }}
 button:hover {{ background:#2ea043; }}
 pre {{ background:#161b22; border:1px solid #30363d; border-radius:8px;
        padding:16px; overflow-x:auto; white-space:pre-wrap; }}
 .ok {{ color:#3fb950; }} .bad {{ color:#f85149; }} .warn {{ color:#d29922; }}
</style></head><body><div class="wrap">
<h1>vexar-autofix</h1>
<div class="sub">An MCP security agent that can prove it fixed your code.</div>
<form method="post">
  <select name="fixture">{options}</select>
  <button type="submit">Audit &amp; patch</button>
</form>
{body}
</div></body></html>"""


def _render(body: str) -> HTMLResponse:
    options = "".join(f'<option value="{name}">{name}</option>' for name in FIXTURES)
    return HTMLResponse(PAGE.format(options=options, body=body))


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return _render(
        '<div class="sub">Pick a fixture. The agent audits it, triages each finding, '
        "patches confirmed ones, and only reports a fix the scanner agrees with.</div>"
    )


@app.post("/", response_class=HTMLResponse)
def run(fixture: str = Form(...)) -> HTMLResponse:
    if fixture not in FIXTURES:
        return _render('<pre class="bad">unknown fixture</pre>')

    key = os.environ.get("NEBIUS_API_KEY")
    if not key:
        return _render('<pre class="bad">NEBIUS_API_KEY is not configured on this host.</pre>')

    target = EXAMPLES / fixture
    client = NebiusClient(key, os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL))
    report = autofix(client, target, check_tests=False)

    if report.get("clean"):
        return _render(f'<pre class="ok">{fixture}: clean. Nothing to fix.</pre>')

    lines: list[str] = [f"<pre>target      {fixture}"]
    before = report["before"]
    lines.append(f"before      {before['score']}/100 ({before['grade']}), {before['findings']} findings")
    lines.append("")
    lines.append("triage:")
    for verdict in report["triage"]:
        css = {"confirmed": "bad", "mitigated": "ok", "unclear": "warn"}.get(verdict["verdict"], "")
        lines.append(
            f'  <span class="{css}">{verdict["verdict"]:<10}</span> {verdict["rule_id"]} '
            f"@{verdict['line']}  {verdict['reason'][:70]}"
        )
    lines.append("")
    lines.append("attempts:")
    for attempt in report["attempts"]:
        status = "ACCEPTED" if attempt["accepted"] else f"rejected: {(attempt['failure'] or '')[:60]}"
        css = "ok" if attempt["accepted"] else "bad"
        lines.append(
            f"  {attempt.get('rule_id', '?')} [{attempt['model_role']}] "
            f'{attempt["applied"]} edit(s) -> <span class="{css}">{status}</span>'
        )

    if report.get("verified"):
        lines.append("")
        lines.append(
            f'<span class="ok">after       {report["after"]["score"]}/100 ({report["after"]["grade"]})</span>'
        )
        lines.append("")
        lines.append("diff:")
        escaped = report["diff"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        for diff_line in escaped.splitlines():
            css = ""
            if diff_line.startswith("+") and not diff_line.startswith("+++"):
                css = ' class="ok"'
            elif diff_line.startswith("-") and not diff_line.startswith("---"):
                css = ' class="bad"'
            lines.append(f"<span{css}>{diff_line}</span>")
    else:
        lines.append("")
        lines.append('<span class="bad">not fixed — verification never passed, file untouched</span>')

    usage = report.get("usage", {})
    lines.append("</pre>")
    lines.append(
        f'<div class="sub">{usage.get("calls", 0)} model calls, ~${usage.get("cost_usd", 0):.4f}</div>'
    )
    return _render("\n".join(lines))
