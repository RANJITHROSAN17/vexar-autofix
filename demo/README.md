---
title: vexar-autofix
emoji: 🛡️
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: An MCP security agent that can prove it fixed your code
---

# vexar-autofix demo

An agent that fixes MCP server vulnerabilities and verifies every fix with the same
deterministic scanner that found the problem.

The demo audits three bundled fixtures and shows the full pipeline: triage, patch,
verification, and the before/after score. It will not touch any file outside `/app/examples`,
so the public endpoint cannot be pointed at arbitrary paths.

Source and documentation: https://github.com/RANJITHROSAN17/vexar-autofix

## Deploying this Space

1. Create a Docker Space on Hugging Face.
2. Upload the repository contents (or connect the GitHub repo, with `demo/` as the build
   context note below).
3. In **Settings → Variables and secrets**, add `NEBIUS_API_KEY` as a **secret**. Never as
   a variable — secrets are not exposed in logs or to viewers.
4. The Space builds via `demo/Dockerfile`.

If you connect the GitHub repo directly rather than uploading files, set the Dockerfile path
in the Space's README frontmatter to `demo/Dockerfile` and keep the build context at the
repository root, since the image needs `src/`, `examples/`, and `pyproject.toml`.

## Why the demo is deliberately narrow

A public endpoint that spends money per request is a liability. Restricting it to the three
fixtures keeps each run at a known handful of cheap model calls and makes abuse pointless —
a visitor cannot use it as a free general-purpose code-fixing service.
