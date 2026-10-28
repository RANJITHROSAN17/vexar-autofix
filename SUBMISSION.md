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

---

## Nemotron & Nebius feedback form

The ratings below are marked **[your call]** — they are opinions, and they should be yours.
Everything factual is drawn from the repository and is reproducible at commit `30313a1`.

**Demo URL**

```
https://ranjithrosan17.github.io/vexar-autofix/
```

**Which model(s) did you use, and why did you choose that size/variant?**

Three Nemotron tiers, routed by the job rather than by convenience:

- `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` — **triage**, one call per *finding*. This is the
  highest-volume decision in the system and it is classification, not reasoning, so it runs on
  the cheapest tier.
- `nvidia/nemotron-3-super-120b-a12b` — **patch authoring**, one call per *queued finding*
  (only what triage marked mechanically fixable). It needs real code understanding, priced so
  that attempting a patch is affordable.
- `nvidia/Nemotron-3-Ultra-550b-a55b` — **escalation**, only after a verification has already
  failed, and it receives the rejected patch plus the reason it was rejected.

The unit of work is a single finding. If a model call per finding is not affordable, you have to
batch findings, and batching loses the per-finding verdict that the whole tool exists to produce.
That constraint is what picked the sizes, not a benchmark.

**How would you rate Nemotron's output quality for your use case?**

8/10 **[your call]**

What worked: instruction-following on structured output shape was reliable enough to parse without
retries, and the Ultra tier used the failure reason productively — given a rejected patch and the
verifier's explanation, it produced the fix the cheaper tier had missed.

What fell short, stated plainly because it is the product's whole premise: on our **first live run,
three of four patches the scanner accepted were wrong**. Nano/Super produced a `shell=False` flip
that broke every command with arguments, an MCP006 patch that validated the URL scheme (which does
nothing for SSRF), and an MCP007 patch confining by string prefix, so `/app-evil` passed a check
against `/app`. A second, smaller failure mode: the model sometimes quotes code that is not
verbatim in the file, so the edit anchor does not match and the patch is rejected as
`anchor not found`.

None of that is a reason to distrust the model — it is the reason the verifier exists.

**Did you fine-tune, prompt-engineer, or use Nemotron out of the box?**

Out of the box. No fine-tuning, no LoRA, no distillation. Prompt engineering is deliberately
minimal: each tier gets a task-shaped prompt containing the file, the finding, and — for
escalation — the previously rejected patch and the verifier's rejection reason. The leverage in
this project is in the routing and the verifier, not in prompt text; if the prompt had to be
clever, the architecture would be doing the wrong job.

**How did Nemotron's performance compare to other models you've used for similar tasks?**

We did not run a controlled head-to-head, so we are not publishing a comparison we did not measure.
Qualitatively: the failure mode — a patch that clears the scanner and leaves the vulnerability — is
the same class of failure we would expect from any frontier model on this task, which is exactly
why the product is the verifier rather than the model. CI runs against a scripted mock provider
precisely so that model comparisons can never contaminate reproducibility.

**Which Nebius platform capabilities were most valuable?**

Token Factory's OpenAI-compatible endpoint, reached over plain serverless API access. One endpoint,
one `NEBIUS_API_KEY`, three models behind it, and a stdlib `urllib` client — no SDK to install.

- **No GPU instances, no deployment, no autoscaling to configure.** For a two-day build that is
  the whole value: there was no infrastructure to stand up, only a key to set.
- **Model selection by ID at runtime**, so the tier can be overridden per run
  (`AUTOFIX_MODEL_TRIAGE`, `AUTOFIX_MODEL_PATCH`, `AUTOFIX_MODEL_ESCALATE`).
- **Per-token pricing low enough to call a model per finding**, which is what makes the
  three-tier design viable rather than aspirational.

We added `--preflight` because a wrong key and a wrong endpoint both present as the same confusing
failure mid-run, and that difference costs hours when the clock is running.

**How likely are you to recommend running Nemotron on Nebius to other developers?**

9/10 **[your call]** — one key, one endpoint, three model sizes, and prices that survive a
per-item call pattern. The friction we hit was finding the exact model IDs, which is why the tool
ships a preflight check.

**Experience running Nemotron on Nebius compared to previous cloud or local environments**

9/10 **[your call]** — there was no environment to build. No CUDA, no model download, no cold
start, no GPU queue; the first working call came from a stdlib client in minutes. The only rough
edge was model-ID/region discovery.

**What additional features would have made the experience more effective?**

1. A machine-readable model catalogue — IDs, context window, price, and per-region availability —
   so a preflight check does not have to be hand-built against a docs page.
2. Structured/JSON-mode output, or a response schema enforced server-side, for the patch payload.
   This is the single change that would most reduce our anchor-mismatch failures.
3. Error codes that distinguish *invalid key* from *unknown model* from *quota exceeded*.
4. Documented determinism — seed and temperature guarantees — for reproducible runs.

**What do you most hope to see from the Nemotron team next?**

A Nemotron variant tuned for code *editing* rather than code generation — emitting search/replace
blocks or unified diffs under a schema — because anchor fidelity, not reasoning, is what fails in
an agentic fix loop. After that: a mid-size model with enough effective context for whole-file
edits at the Super tier's price.

**Did you use Tavily in your project?**

No. The project makes no Tavily API call at runtime, so it is not eligible for that prize, and we
would rather say so than claim a call we do not make.

**Builders & Brews — IRL Events City**

Not applicable. Not attending any of the listed events.
