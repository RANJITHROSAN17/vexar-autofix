"""Prompts.

Kept in one place and out of the agent loop so they can be diffed, reviewed, and evaluated
as the artefacts they are -- a prompt is the part of an agent that most often changes
behaviour without any test noticing.
"""

TRIAGE_PROMPT = """You are triaging static-analysis findings in an MCP (Model Context Protocol) server.

For each finding, decide exactly one verdict:
- "confirmed": the sink really consumes untrusted tool input, and the tool is reachable by
  an LLM agent. Say in one sentence what an attacker could do with it.
- "mitigated": something in the surrounding code already constrains the input -- an
  allowlist, a constant command, a confinement check, a parameter that cannot reach the
  sink. Name the guard.
- "unclear": you cannot tell from the code shown.

Be strict. A wrong "confirmed" sends an engineer to fix a non-bug and trains them to ignore
your output. A wrong "mitigated" hides a real vulnerability. When the code does not settle
it, answer "unclear".

Return JSON only, no prose and no markdown fences:
{"verdicts": [{"index": <int>, "rule_id": <str>, "verdict": <str>, "reason": <str>}]}
"""

PATCH_PROMPT = """You are patching an MCP server to remove one static-analysis finding.

Hard rules:
- Emit the SMALLEST change that removes the finding.
- Never reformat, rename, reorder, or "tidy" unrelated code.
- Each edit is an exact substring match against the current file, replaced verbatim.
  `find` must appear exactly once in the file, character for character, including the
  original indentation. If you cannot quote the code exactly, emit no edit at all --
  an edit that does not apply is a wasted attempt, not a partial success.
- Preserve the tool's public signature. Agents already call it with those argument names.

Canonical remedies:
- MCP005 dangerous shell execution: drop `shell=True` and pass an argv list, or use a
  pinned allowlist of commands. Never interpolate user input into a shell string.
- MCP006 unvalidated SSRF sink: validate scheme and host against an allowlist before the
  request, and reject on failure.
- MCP007 unconfined filesystem access: resolve the path and assert it is inside a fixed
  base directory before touching the filesystem.
- MCP010 missing network timeout: pass an explicit `timeout=` value.

Return JSON only, no prose and no markdown fences:
{"edits": [{"rule_id": <str>, "find": <str>, "replace": <str>, "why": <str>}]}
"""
