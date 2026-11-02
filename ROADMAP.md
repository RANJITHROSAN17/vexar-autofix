# Roadmap

**Verification first.** Every item below was checked against this repository before being
scheduled. Anything already built is marked **done** and is *not* rescheduled — the point of
this document is the gap, not a wish list. Each row carries the evidence that decided it.

Companion: [`../PRODUCT.md`](../PRODUCT.md) for why the proof layer is the product, and
[`Vexar-MCP/docs/roadmap-90-days.md`](https://github.com/RANJITHROSAN17/Vexar-MCP/blob/main/docs/roadmap-90-days.md)
for the parent product.

---

## Where it actually stands (audited 2026-10-28, commit `30313a1`)

The generic "Phase 1: reliability" plan for a project like this is largely **already done
here**. Recording that honestly is what keeps the 90 days focused on real work.

| Capability | Status | Evidence |
|---|---|---|
| Closed set of fixable rules | **done** | `AUTOFIXABLE = {MCP005, MCP006, MCP007, MCP010}` in `verifier.py` |
| Rules with no remedy are refused, not attempted | **done** | `refused` bucket in `agent.py`; `test_non_autofixable_rules_are_refused_not_attempted` |
| Every finding lands in exactly one bucket | **done** | fixed / unfixed / refused / skipped; `test_every_finding_receives_a_verdict` |
| Dry run is the default | **done** | `--apply` is required to write; `test_the_target_file_is_never_modified_by_a_dry_run` |
| Three verification gates | **done** | `verify()` (rescan counts, no new findings, tests) |
| Semantic patch audit of added lines | **partial** | `audit_patch()` covers MCP005/006/007 — **MCP010 is uncovered**, see G1 |
| Parent scanner pinned for reproducibility | **done** | `pyproject.toml` → `Vexar-MCP @ dd4c07b` |
| Proof log a user can read | **partial** | `--json` emits the report; no versioned artifact schema (G3) |
| CI integration | **missing** | CLI + hosted demo only (G5) |

---

## The gaps, in priority order

Each gap states what it is, why it matters, and how completion is measured. Nothing here is
scheduled twice.

### G1 — `MCP010` has no patch audit · **P0, week 1 — DONE**

**Verified.** The audit rejects a wrong MCP005, MCP006 and MCP007. It says nothing about
MCP010, and the rescan cannot tell a real timeout from a meaningless one:

```
patch                          rule cleared?  audit says
timeout=10        (canonical)  YES            accepted
timeout=10**9     (absurd)     YES            accepted
timeout=float(inf)             YES            accepted
```

`timeout=float('inf')` removes the finding and leaves a request that can hang forever — the
exact failure mode of MCP005's `shell=False`, one rule over. This is the most important fix
in this document, because it is the product's own argument applied to itself.

**Do:** add `MCP010` to `SMELLS` (`timeout\s*=\s*None`, `float\(['"]inf`, `10\*\*\d{2,}`,
any literal > 600) and a `REMEDY_MARKERS` entry accepting a bounded numeric or named
constant. **Acceptance:** the three cases above reject; `timeout=10` and `timeout=TIMEOUT_S`
accept; `tests/test_verifier.py` gains `test_unbounded_timeout_is_not_a_fix`; the mock
rehearsal and the eval still pass.

**Shipped.** Four smells (`None`, `inf`, power-of-ten, any literal above five digits) and a
marker requiring a bounded value. The table inverts, and the canonical fix still passes:

```
patch                     rule cleared?  audit
timeout=10                YES            accepted
timeout=2.5               YES            accepted
timeout=TIMEOUT_SECONDS   YES            accepted
timeout=None              YES            REJECTED
timeout=float('inf')      YES            REJECTED
timeout=10**9             YES            REJECTED
timeout=1e9               YES            REJECTED
timeout=86400             YES            REJECTED
```

Three tests added: `test_unbounded_timeout_is_not_a_fix`, `test_bounded_timeout_is_a_fix`,
and `test_every_fixable_rule_is_covered_by_the_audit` — the last one is the structural
guard, so a future rule cannot join `AUTOFIXABLE` without either a smell or a marker.
Mock rehearsal unchanged (1 fixed, 4 to a human, 7 refused, dry run); suite 46 → 49.

### G2 — Refusals carry prose, not reason codes · P1, weeks 2–3

`refused` currently holds `{"rule_id", "line", "why": "rule has no mechanical remedy…"}`.
Prose is right for a human and wrong for a CI consumer that wants to route on the reason.

**Do:** add a `code` enum to every bucket — `no_remedy`, `not_confirmed`, `unsafe_rule`,
`ambiguous_anchor`, `verification_failed`, `tests_failed`, `model_no_edits` — keeping `why`
as the human string. **Acceptance:** a documented, stable set of codes; `--json` exposes
them; a test asserts no bucket entry can exist without a code.

### G3 — Proof artifact v1 · P1, weeks 3–4

Today the evidence is a terminal diff plus `--json`. An enterprise buyer wants a file.

**Do:** `--report PATH` writing a versioned JSON document: schema version, target hash
before/after, scanner + model versions, per-finding decision with code, the diff, the gate
results, and a `verified` boolean that is true only when all gates passed.
Ship `docs/proof-artifact.schema.json`. **Acceptance:** the file validates against the
schema; it is deterministic apart from timestamps; a golden test pins the shape.

### G4 — Fix policy flags · P2, weeks 5–6

**Do:** `--allow-rules`, `--block-rules`, `--require-approval RULES`, and a `--policy` preset
(`conservative` = MCP010 only, `default` = all four, `strict` = require approval for any
patch that deletes a sink). **Acceptance:** a blocked rule is reported, never attempted;
approval-required patches stop before writing and print the exact command to apply.

### G5 — GitHub Action: preview and gate modes · P2, weeks 6–7

**Do:** an action with three modes — `preview` (post the diff as a PR comment, never write),
`gate` (fail the job if a confirmed finding remains fixable), `apply` (commit to a branch).
**Acceptance:** usable from a workflow file with no local install; a preview run on this
repo's own fixtures is linked from the README.

### G6 — Rejection corpus benchmark · P3, weeks 8–9

The differentiator is refusing bad patches; there is no public evidence of it yet.

**Do:** `benchmarks/rejections/` — every patch the audit must reject, each with the rule,
the reason, and the expected verdict; plus the accepted canonical set. Wire it into the eval.
**Acceptance:** the corpus runs in CI; the count of rejections is published in the README and
on the demo page, and it grows with every real failure found.

### G7 — `VERIFICATION.md` · P3, weeks 9–10

**Do:** the three gates and the audit rules written as a specification another team could
reimplement, with the failure modes that motivated each one. **Acceptance:** an engineer who
has not read the source can implement a compatible verifier from the document alone.

### G8 — Cross-repo blocker: the import name is taken · **P0 dependency, not ours alone**

**Release candidate update:** the parent migration is proposed in
[RANJITHROSAN17/Vexar-MCP#76](https://github.com/RANJITHROSAN17/Vexar-MCP/pull/76).
This branch uses canonical `vexar_mcp` imports and a `vexar-mcp==0.3.0` release pin.
The original findings below describe the pre-migration state. G8 is **not done**
until the parent is published, this change merges, and both public installations
are verified. See [RELEASING.md](RELEASING.md).

**Verified.** `mcp-doctor` on PyPI is **not this project** — it belongs to another author
(`Jiansen/mcp-doctor`, v0.1.0). This repository's *import* package is `mcp_doctor`, while its
*distribution* name is `Vexar-MCP`. Publishing `Vexar-MCP` would install a top-level
`mcp_doctor` module that collides with the existing distribution.

`vexar-autofix` imports it directly (`from mcp_doctor import ScanConfig, scan_paths`), so the
rename must be sequenced across both repos:

1. Rename the import package in Vexar-MCP (`mcp_doctor/` → `vexar_mcp/`), keeping a shim.
2. Bump this repo's pinned commit and update the two import sites in `verifier.py`.
3. Only then publish to PyPI.

**Acceptance:** `pip install vexar-mcp` and `pip install vexar-autofix` coexist in one
environment with no file overlap. **Until this is done, do not publish to PyPI** — a
half-published name is worse than an unpublished one.

---

## Added 2026-11-03 — the gate-3 repair cycle (N1, N2, N3, X7)

Added after an independent review that ran the checks in this repository rather than reading
them; the full analysis is in [`docs/ROADMAP-PROPOSED.md`](docs/ROADMAP-PROPOSED.md). It
supersedes nothing above. It goes ahead of G2 because of one finding that changes the order
of everything else.

**Gate 3 does not run.** The table near the top of the README sells three gates. The third is
*"It still works — the target's own pytest suite must pass after the patch."* `agent.py` copies
only the target **file** into the temp workspace, so `run_tests()` finds no `test_*.py` and
returns `None`; `cli.py` then renders that `None` as `unchanged / passing`. A target whose own
tests fail still comes out `verified=True`. No test exercises `check_tests=True` — all twelve
tests in `tests/test_agent.py` disable it — so nothing caught this.

A proof product with one gate that is decorative is worth less than a smaller product with
none, because the discovery that one gate never ran discounts the two that did. So this cycle
repairs the claim before it adds to it.

| ID | Item | Done when |
|---|---|---|
| **N1** | Run the test suite against the materialised target root, and report `null` as "not run" | A target with a failing suite is not verified, and the word "passing" never appears for a gate that did not execute |
| **N2** | Gate matrix: the first test that runs `check_tests=True`, one rejection case per gate | Deleting the `run_tests` call makes the suite go red |
| **N3** | Reconcile the published numbers (merges **G7** and **G9**) | Every number on the demo page traces to `capture_demo.py`, and no token field contradicts `cost_usd` |
| **X7** | Bound the test gate's execution: no network, read-only outside the workspace | Tracked before N1 lands, because making the gate work turns on code execution against other people's repositories |

**Sequencing:** N1 and X7 are one decision, not two — repairing the gate is what makes the
execution boundary matter. N3 is independent and can run in parallel. N2 should land with or
immediately after N1. **G9 is absorbed into N3.** **G7 keeps only its remaining half** — the
`VERIFICATION.md` that lists the command behind every published number — because its telemetry
criterion is N3's job.

**Non-goals for this cycle:** more fixable rules, the proof artifact (G3), policy flags (G4),
the Action (G5), and any desktop/assistant surface. See E and F of the proposal for why each
is deferred rather than rejected.

---

## The 90 days

### Days 1–30 — close the holes and make the output machine-readable

| Week | Work | Done when |
|---|---|---|
| 1 | **G1** MCP010 audit + test ✅ | The absurd-timeout table above inverts: five rejects, three accepts |
| 2 | **G2** reason codes across buckets | No bucket entry without a code; documented enum |
| 3 | **G3** proof artifact + JSON schema | `--report` produces a schema-valid, golden-tested file |
| 4 | Fix the two honesty gaps flagged in the demo | `docs/data/runs.json` carries real token counts; `capture_demo.py` emits the schema the page reads |

**Metric:** a user can run the tool in dry-run and explain, without reading source, why every
finding was fixed, refused or skipped — and can machine-read that same answer.

### Days 31–60 — fit into how teams actually work

| Week | Work | Done when |
|---|---|---|
| 5 | **G4** policy flags | A blocked rule is never attempted; approval stops before writing |
| 6 | **G5** action, `preview` mode | A PR gets a diff comment with the verdicts, nothing written |
| 7 | **G5** action, `gate` + `apply` | A repo can gate merge on "no fixable confirmed finding" |
| 8 | Real-world run | The tool is run on an external MCP server repo; the outcome — including refusals — is written up |

**Metric:** a team can adopt it with under 20 minutes of setup and never be surprised by a
write it did not approve.

### Days 61–90 — make the evidence public

| Week | Work | Done when |
|---|---|---|
| 9 | **G6** rejection corpus | Corpus runs in CI; rejection count published and growing |
| 10 | **G7** `VERIFICATION.md` | Spec is implementable without reading the source |
| 11 | **G8** cross-repo rename + first PyPI release | Both packages install cleanly together |
| 12 | Public benchmark page | Scorecard: rules fixable, rules refused, patches rejected, regressions |

**Metric:** the claim "verifiably safe patch" is backed by a corpus a sceptic can run.

---

## Invariants — these must never regress

A feature that breaks one of these is not a feature. Each is already pinned by a test; new
work must keep them green.

1. A dry run never writes. (`test_the_target_file_is_never_modified_by_a_dry_run`)
2. A rule with no mechanical remedy is never attempted. (`test_non_autofixable_rules_are_refused_not_attempted`)
3. Every finding receives a verdict and a bucket. (`test_every_finding_receives_a_verdict`)
4. A patch that trades one finding for another is rejected. (`test_regression_is_rejected_even_when_the_target_is_fixed`)
5. A targeted rule must actually drop its instance count; moving a sink is not a fix. (`test_still_present_at_a_new_line_is_not_a_fix`)
6. Line shifts are never read as new findings. (`test_line_shift_is_not_a_new_finding`)
7. The working tree is untouched until verification has already passed. (`test_the_agent_never_reads_a_fixture_the_demo_can_rewrite`)

## Explicit non-goals for these 90 days

- **More fixable rules.** Coverage without a verifiable remedy produces refusals, not value.
  Four rules with full audit coverage beat fifteen with none.
- **Autonomous writes.** No unattended `--apply` on a high-risk rule, ever.
- **A hosted SaaS.** The artifact is the product; where it is produced is secondary.
- **Publishing to PyPI before G8 is resolved.**
- **A web-search dependency in the fix loop.** Considered and deferred, not rejected. The agent's
  inputs are the file, the finding and the verifier's reason - all local, all reproducible from a
  commit. A live search call would make the output a property of the afternoon rather than of the
  commit, which is the one claim the proof artifact exists to make. The defensible version, if it
  is ever built, is *advisory enrichment* on confirmed findings with the fetch time recorded in the
  artifact; it is deliberately not in these 90 days.

## How to tell whether this is working

One number that is not vanity: **the count of rejected patches in the public corpus.** It
should rise with every real failure found, because each rejection is a bug that did not reach
a user. If that number stops moving, the verifier has stopped learning.
