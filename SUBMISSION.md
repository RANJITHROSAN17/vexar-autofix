# Devpost submission copy

Copy-paste ready. Every figure is from the recorded run at commit `30313a1`; nothing here is estimated.

---

**Project name**

vexar-autofix

**Tagline (one line)**

An MCP security agent that can prove it fixed your code.

**Track**

Coding and Agentic Engineering

**Links**

| | |
|---|---|
| Repository | https://github.com/RANJITHROSAN17/vexar-autofix |
| Live demo | https://RANJITHROSAN17.github.io/vexar-autofix/ |
| Scanner (parent project) | https://github.com/RANJITHROSAN17/Vexar-MCP |
| Video | _(paste the public YouTube or Drive link here)_ |

---

## Inspiration

MCP servers are how AI agents touch the real world — they run shell commands, fetch URLs, read and write files, query databases on an agent's behalf. A static scanner can find those sinks. It cannot fix them.

The obvious next step is to point a language model at the file and ask for a patch. We tried that first, and it produced the finding this project is built around: **the scanner accepted four patches and three of them were broken.**

- `MCP005` — the model wrote `subprocess.run(cmd, shell=False)` while still passing one string. Every command with an argument then raised `FileNotFoundError`. The rule cleared; the tool was dead.
- `MCP006` — the model validated the URL's *scheme*. `http://169.254.169.254/latest/meta-data/` has a valid scheme and a valid host, so it passed.
- `MCP007` — the model confined a path with `startswith(BASE_DIR)`. `/app-evil/secret` starts with `/app`.

The scanner was satisfied every time, because the scanner matches patterns, not intentions. A verifier that reports "finding cleared, tests green" while handing back a broken tool is worse than no verifier — it manufactures confidence.

So we built the verifier first and the agent second.

## What it does

`vexar-autofix` scans an MCP server, triages each finding, patches the ones with a canonical remedy, and then **refuses to accept its own model's work** unless three deterministic checks agree:

1. **Rescan** — the targeted rule's instance count must actually drop for that tool. Moving a sink to another line is not remediation.
2. **No new findings** — a patch that trades one finding for another is rejected.
3. **Tests** — the target's own suite must still pass.

A fourth stage audits the patch itself, reading **only the lines the patch added**, and rejects remedies that cannot work: `shell=False` on a single string, an SSRF "fix" with no host allowlist, prefix-based path confinement. It costs nothing, cannot hallucinate, and encodes the review a security engineer would do anyway.

When a patch fails, the rejection reason — not a summary of it — is fed to a stronger model on the next attempt.

And when a rule has no mechanical remedy (a tool description that is too short, a missing type annotation), the agent **refuses** and says so. A confidently wrong fix is worse than a known finding. Every finding lands in exactly one bucket — fixed, unfixed, refused, or skipped — so nothing disappears silently.

## How we built it

Five stages, three NVIDIA Nemotron models on Nebius Token Factory, each with a different job rather than the same job at a different price:

| Stage | Model | Why this tier |
|---|---|---|
| Scan | Vexar-MCP (deterministic) | No model. The oracle on both sides of the loop. |
| Triage | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | Classification, not reasoning — and it runs on every finding, so it must be cheap. |
| Patch | `nvidia/nemotron-3-super-120b-a12b` | Real code understanding at a price where trying is affordable. |
| Verify | rescan + patch audit + pytest | No model. Decides whether the patch counts. |
| Escalate | `nvidia/Nemotron-3-Ultra-550b-a55b` | Only after a *verified failure*, with the exact reason attached. |

**The routing signal is the part we are proudest of.** Tiered demos usually route on request difficulty, which cannot be measured before answering. This routes on **verified failure** — a signal that only exists because a deterministic checker is in the loop. The expensive model is never consulted on a guess.

Edits are exact anchor replacements, never line numbers or whole-file rewrites: a patch either matches the source byte-for-byte or fails loudly. Every attempt runs against a throwaway copy in a temp directory, so the working tree is untouched until a patch has already verified.

## Results

Three hand-written fixtures with a declared rule set, so the denominator is known rather than estimated:

| Fixture | Findings | Fixed | Refused | Regressions | Score |
|---|--:|--:|--:|--:|--:|
| `vulnerable_server.py` | 9 rules / 12 instances | 4 | 7 | **0** | 4 → 46 |
| `helper_delegation_server.py` | 3 rules / 3 instances | 3 | 0 | **0** | 73 → 100 |
| `clean_server.py` *(control)* | 0 | 0 | 0 | **0** | 100, untouched |

**18 model calls · $0.0226 · zero regressions.** The clean fixture is a control: if the agent can be made to "fix" something already correct, every other receipt is worthless.

We also ran the scanner against [Nebius's own MCP server](https://github.com/nebius/mcp-server) — a real Python codebase — where it scored 94/100 with no security findings. A tool that never says "this code is fine" is not a scanner, it is a sales pitch.

## Challenges we ran into

**Line-shift.** The first verifier compared findings by `(rule, tool, line)`. A patch that deleted two lines and added one renumbered everything below it, so a *perfect* fix reported "1 finding cleared, 6 new findings appeared" and was rejected. Every correct multi-line patch would have failed. It now compares rule-instance counts per tool, which survives reordering — pinned by a test.

**A review step that compared the patch with itself.** The variable had already been reassigned before the comparison, so it silently reported nothing, forever. Both bugs taught the same lesson as the product: a quiet output is not evidence of correctness.

## What we learned

The model is not the hard part. The hard part is being willing to reject it. Most of this codebase is rejection machinery — anchor matching, count deltas, semantic audits, refusal buckets — not prompting.

## What's next

- Publish the verifier's rejection corpus as an open benchmark, so "verifiably safe patch" becomes a claim others can be measured against.
- Publish the three gates as a spec another team could implement.
- Keep the scanner (`Vexar-MCP`) free and CI-first as the funnel; the proof layer is the product.

## Built with

`python` · `nvidia-nemotron` · `nebius-token-factory` · `mcp` · `static-analysis` · `sarif` · `pytest` · `github-actions` · `github-pages`
