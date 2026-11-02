# Roadmap proposal: `vexar-autofix`

**Status:** proposal for maintainer review. Nothing in this document has been applied to the repository.
**Repository analysed:** `RANJITHROSAN17/vexar-autofix` @ `6aa548e` (default branch `main`, 40 commits, 2026-11-02).
**Author of this analysis:** independent review performed in a Linux sandbox against a fresh clone, 2026-11-03.
**Companion to:** `ROADMAP.md` (existing, unchanged) and `.github/roadmap.json` (existing, unchanged).

**Evidence labels used throughout**

| Label | Meaning |
|---|---|
| **[V]** | Verified in this session — command run or file read, result quoted |
| **[I]** | Inferred from code/docs — a reasoned conclusion, not directly executed |
| **[U]** | Unverified — no evidence available in this session, or requires the maintainer/hardware |

---

## 0. A framing problem that must be resolved before this roadmap is prioritised

The brief this analysis was commissioned against describes **"Pinch": a local-first personal assistant for Windows, with optional local voice, reminders, clipboard, file and app assistance.** The repository does not contain that product, and never has.

What `main` contains is a Python CLI — `vexar-autofix` — that remediates four static-analysis rules in MCP servers and refuses to report a fix the scanner cannot confirm. **[V]** Every source file, workflow, test and doc was read; there is no tray process, no audio capture, no speech, no memory store, no OS action layer, no Windows-specific code, and no local model runtime. The only providers are `nebius` (remote Token Factory) and `mock` (offline rehearsal), per `src/vexar_autofix/clients.py:36-40` and `cli.py:177`.

The honesty section of the brief says to report this rather than paper over it, so: **this document is a roadmap for the product that exists**, and §G records the decision the maintainer has to make about whether "Pinch" is a separate codebase. Inventing a 90-day Windows-assistant plan for a codebase with no desktop surface would produce the exact artefact the brief forbids — a plausible-looking roadmap with no evidence under it.

One useful thing survives the framing problem. The repository's central discipline — *never accept a model's output on its own authority; gate it on a deterministic check and record the verdict* — is precisely the discipline a personal assistant needs before it touches a file, a clipboard or an inbox. If Pinch is ever built, this repo is its trust layer, not its UI. That is also how §B2 treats the competitive question: what is worth porting is verification and reporting machinery, not assistant features.

---

## A. Executive summary

### What is genuinely strong

1. **The verification core is real, small and test-pinned.** `verifier.py` (301 lines) answers one question — *is this patch strictly better code?* — and it answers it with rules a reviewer can audit: targeted rule count must drop per `(tool, rule)`, no rule may gain instances, exact-anchor edits only, and a rule-specific `audit_patch` that rejects remedies which cannot work (e.g. `timeout=float('inf')`). **[V]** 31 tests in `tests/test_verifier.py`; the MCP010 bypass table reproduces 5 rejects / 3 accepts via `.github/scripts/self_audit.py` (**11/11 claims reproduce**).
2. **The determination is line-shift invariant and it is documented as such.** `verify()` compares rule-instance counts and explicitly explains why `(rule, tool, line)` matching rejects perfect multi-line fixes (`verifier.py:83-94`). That is a bug found and articulated, not a default.
3. **The published receipt reproduces, exactly.** **[V]** The scanner half re-derives byte-identically: `vulnerable_server.py 12 findings 4/100 9 rules`, `helper_delegation_server.py 3 findings 73/100 3 rules`, `clean_server.py 0 findings 100/100 0 rules`. This is the single most valuable asset in the repository — a claim a sceptic can re-run.
4. **The engineering hygiene is above the norm for a hackathon-derived project.** **[V]** `ruff check .` clean, `mypy src --strict` clean (7 files), `pytest` 76/76 pass offline, `eval/run_eval.py --provider mock` passes its ground-truth assertion, `validate_workflows.py` reports 10 valid workflow files, and every workflow declares least-privilege `permissions:` (the only write surfaces are `contents: write` on `demo-capture` and `issues/PR write` on the bots).
5. **The refusal discipline is the product and it is honestly reported.** Seven findings are refused because no mechanical remedy exists, and the README refuses to hide that to make the score look better. That is a rare and defensible position.

### What is actually wrong

1. **One of the three advertised verification gates does not run.** The README's table states *"It still works — the target's own pytest suite must pass after the patch."* **[V]** It never does. `agent.py:200-202` copies **only the target file** into a temp dir, and `agent.py:246` then calls `run_tests(workspace.parent)`. `run_tests` returns `None` when the directory contains no `test_*.py` (`verifier.py:135-136`), which is every real invocation. Measured: a project whose tests **fail** (`run_tests(proj) → False`) still produced `tests_ok = None` and `verified = True`. **[V]**
2. **The failure is presented to the user as a pass.** `cli.py:67` prints `tests {'unchanged / passing' if report['tests_ok'] in (True, None) else 'FAILED'}` — `None` is silently mapped onto the word *passing*. A user reading the report cannot distinguish "tests passed" from "tests were never run". **[V]**
3. **No test exercises the gate at all.** All 12 tests in `tests/test_agent.py` pass `check_tests=False`; `grep -rn "tests_ok\|run_tests\|no-tests" tests/` returns **nothing**. The `--no-tests` flag, the `tests_ok` field and the gate itself have zero coverage. **[V]** So the repo's own invariant list ("Each is already pinned by a test") does not cover gate 3.
4. **Published telemetry is internally inconsistent.** `docs/data/runs.json` reports `input_tokens: 0, output_tokens: 0` alongside `cost_usd: 0.0226`. `clients.py:_record` populates all three together. Zero tokens with non-zero cost means the cost was not derived from the recorded response. **[V]** — this is roadmap item G9, and it is a direct hit on the product's core claim.
5. **"Closed" is being read as "shipped", and the automation cannot see it.** **[V]** Issue #2 (G8) is `closed / completed`; `vexar-mcp==0.3.0` **is** on PyPI and imports as `vexar_mcp`; but `vexar-autofix` returns 404 on PyPI, there are **no tags and no releases**, and `RELEASING.md` steps 4–5 are unperformed. G8's stated acceptance criterion ("both packages install cleanly together") is therefore **unmet**. `roadmap_status.py --dry-run` prints *"Drift: None. The plan, the queue and the tree agree."* — it cannot detect closed-but-not-shipped. `roadmap.json` still queues G8 as open work, while its issue is closed and will never be reopened by the bot.
6. **Documentation drift on basic facts.** `README.md:461` says "46 tests"; the suite is **76** **[V]**. `PRODUCT.md` describes the parent as *"v0.2.1 … pins the parent at a commit sha"*; `pyproject.toml` pins `vexar-mcp==0.3.0` **[V]**. Small, but the product's entire pitch is that its numbers are checkable.

### Direction

**Do not expand the product this cycle. Repair the claim.** The differentiator is not "an agent that fixes MCP findings" — it is "a fix you can accept without re-reading it". Three of the five deficits above are cases where the evidence layer says something that is not true. A proof product with one unenforced gate and one inconsistent telemetry file is worth less than a smaller product with none. The next cycle should be **one gate, its tests, and the honesty of the published numbers** — a cycle small enough to finish and verifiable without a Nebius key. Feature work (proof artifact, policy flags, SARIF) follows, and must be admitted on the same terms.

---

## B. Evidence-backed current-state matrix

| # | Area | Evidence (file:symbol) | State | Finding | Label |
|---|---|---|---|---|---|
| 1 | Verification core | `verifier.py:verify`, `audit_patch`, `SMELLS`, `REMEDY_MARKERS` | Implemented, tested | Line-shift-invariant count comparison; 4 audited rules; structural guard `test_every_fixable_rule_is_covered_by_the_audit` | [V] |
| 2 | Patch application | `verifier.py:apply_edits` (51-74) | Implemented, tested | Exact-anchor only; empty / missing / ambiguous anchors rejected loudly. Matches the SEARCH/REPLACE primitive the wider ecosystem converged on | [V] |
| 3 | Gate 1 — targeted rule drops | `verifier.py:112-117` | Implemented, tested | Correct, and rejects "moved the sink to another line" | [V] |
| 4 | Gate 2 — no new findings | `verifier.py:118-119` | Implemented, tested | Correct, per `(tool, rule)`; scoped to the single target file only | [V] |
| 5 | **Gate 3 — target tests pass** | `agent.py:200-202,246,291`; `verifier.py:133-147` | **Present but non-functional** | Runs against a temp dir containing only the patched file ⇒ `tests_ok` is `None` in every real invocation. A failing target suite still yields `verified=True` | **[V]** |
| 6 | Gate-3 reporting | `cli.py:67` | **Incorrect** | `None` is rendered as "unchanged / passing" | **[V]** |
| 7 | Gate-3 test coverage | `tests/test_agent.py` (12 tests, all `check_tests=False`) | **Absent** | Zero coverage of `tests_ok`, `run_tests`, `--no-tests` | **[V]** |
| 8 | Dry-run immutability | `agent.py` returns `patch`; write happens only in `cli.py:86` under `--apply` | Implemented, tested | Invariant 1 holds; pinned by `test_the_target_file_is_never_modified_by_a_dry_run` | [V] |
| 9 | Bucket accounting | `agent.py:176-198` | Implemented, tested | Every finding lands in exactly one of fixed/unfixed/refused/skipped; pinned by `test_every_finding_receives_a_verdict` | [V] |
| 10 | Reason codes for refusals | `agent.py:179-193` — prose in `why` | Not implemented | G2 is real: no machine-routable code | [V] |
| 11 | Triage | `agent.py:triage`, `prompts.py:TRIAGE_PROMPT` | Implemented, tested | One cheap call for all findings; unparseable output degrades to `unclear`. **Precision/recall never measured** — no labelled set | [V]/[U] |
| 12 | Model routing | `clients.py:MODEL_ROLES`, `agent.py:211` | Implemented | Escalation only after a verified failure — the genuinely novel routing signal | [V] |
| 13 | Mock / offline rehearsal | `clients.py:MockClient`, `--rehearse-accept` | Implemented | Hermetic CI with no key; clearly labelled fake | [V] |
| 14 | Eval harness | `eval/run_eval.py` | Implemented | Ground-truth assertion + regression gate; `--case` for one fixture. **Exits non-zero only on ground-truth/regression mismatch** | [V] |
| 15 | Published receipt | `docs/data/runs.json`, `docs/index.html` | Implemented, **partly inconsistent** | Token counts zero with non-zero cost; page reads `.runs/.usage/.cost_usd/.calls` which `capture_demo.py` does emit — so the file predates token capture (G9) | **[V]** |
| 16 | Reproducibility of the scanner half | `docs/data/scan.json` + the README snippet | Implemented, **reproduces exactly** | Re-derived identical counts and scores in this session | **[V]** |
| 17 | CLI surface | `cli.py:176-193` | Implemented | `--target/--provider/--apply/--max-attempts/--no-tests/--json/--rehearse-accept/--preflight`. No `--report`, `--sarif`, `--policy`, `--allow-rules` | [V] |
| 18 | Preflight | `cli.py:_preflight` | Implemented | Key + endpoint + model-ID probe with actionable failure text. Not exercised here (no key) | [V]/[U] |
| 19 | Packaging | `pyproject.toml`, `publish-pypi.yml` (tag `v*.*.*`), `check_release_install.py` | Implemented, **never released** | `vexar-autofix` 404 on PyPI; 0 tags; 0 GitHub releases; OIDC + `pypi` environment not proven | **[V]** |
| 20 | Parent dependency | `pyproject.toml` → `vexar-mcp==0.3.0` | Implemented, published | Install resolves; `import vexar_mcp` works; `mcp_doctor` absent ⇒ no namespace collision | **[V]** |
| 21 | CI | `.github/workflows/ci.yml` | Implemented | 4 Python versions × (workflow-validate, ruff, ruff-format, mypy strict, pytest, mock eval, CLI smoke, credential-shape scan). `contents: read` | [V] |
| 22 | Automation / bots | 6 bot workflows + `.github/scripts/*.py` (1,400 lines) | Implemented, tested | 24 tests in `tests/test_bots.py`; queue cap of 4 open roadmap issues honoured (4 open + 1 status issue) | [V] |
| 23 | "Closed = shipped" detection | `roadmap_status.py`, `sync_roadmap_issues.py` | **Gap** | Drift check compares manifest↔issue, never issue-state↔acceptance. Reported "Drift: None" while G8's acceptance is unmet | **[V]** |
| 24 | Test-suite execution safety | `verifier.py:run_tests` → `subprocess.run([sys.executable,'-m','pytest',...])` | Implemented, **unsandboxed** | Executes the target's code with the caller's privileges and the caller's CWD. Documented in the README warning; not enforced in code. Latent today only because of defect #5 | [V]/[I] |
| 25 | Throughput / latency | `agent.py:205-281` — sequential; whole file in every payload | Implemented, **unmeasured** | `O(findings × attempts)` model calls, each carrying the full source (measured 1.3–2.8 KB per attempt on the fixtures). Local overhead is negligible: full mock eval = **0.24 s** ⇒ latency is entirely provider-bound | **[V]** for payload/size; **[U]** for real latency |
| 26 | Security posture docs | `SECURITY.md` | Implemented | Two report classes (tool vulns, verifier bypasses); 72 h ack; private advisory path; dedicated bypass issue template | [V] |
| 27 | Doc/claim drift | `README.md:461` (46 vs 76 tests), `PRODUCT.md` (v0.2.1 / commit-sha pin) | **Inconsistent** | The repo's selling point is checkable numbers; two are stale | **[V]** |
| 28 | Windows / voice / memory / OS actions | nothing under `src/`, `docs/`, `pyproject.toml` | **Not implemented** | As expected for this product; recorded only so the Pinch brief is answered explicitly | **[V]** |

---

## B2. Benchmark against the top-starred adjacent projects

The user-facing instruction attached to this analysis asked to compare against the best-starred related projects and port their strengths in **speed, security and usage**. That is done below, with the brief's own rule applied first: *a competitor feature is worth copying only if its value is established.* Star counts are as reported by the cited third-party pages, not measured here.

| Project | Reported scale | What it does | Feature with established value | Port it? |
|---|---|---|---|---|
| **semgrep/semgrep** | ~17.4k stars [1] | Pattern-based SAST, 30+ languages, CI-native | **SARIF + machine-readable CI output**; and *publishing a measured triage agreement rate* (vendor-reported ~80–95% human agreement [2][3]) — i.e. the tool publishes how often its AI judgements are right | **Yes, both.** SARIF = roadmap G10 (adoption path into Code Scanning). The agreement-rate idea is cheap here and directly strengthens our differentiator: we already produce verdicts, we just never measure them |
| **Semgrep autofix / AI remediation** | — | Deterministic rule-linked fixes | Deterministic *rule→remedy* mapping before any LLM is involved | **Already done better.** Our `REMEDY_MARKERS` + `audit_patch` is the same idea plus a rejection path |
| **aider** (edit-format benchmarks) | — | AI pair programmer with benchmarked edit formats | **SEARCH/REPLACE beats unified diffs** for model reliability (GPT-4 26%→59% on the laziness benchmark [4][5]); unified diffs cause indentation/line-math failures; **duplicate anchors are the known failure mode, fixed by widening the anchor context** [6] | **Primitive: keep ours** (exact anchor = same primitive; do not switch to unified diffs). **Gap to close: duplicate-anchor disambiguation** — we reject `count > 1` with a generic message instead of telling the model how to widen the anchor. Cheap, measurable win |
| **invariantlabs mcp-scan → snyk/agent-scan** | ~2,000+ stars [7] | MCP-specific: tool poisoning, rug pulls via **hash-based tool pinning**, cross-origin escalation | **Integrity pinning over time**: hash what you validated, re-check on change | **Adapt, don't copy.** Their object is a tool manifest; ours is a source file. The transferable part is *pin the inputs* — scanner version + target hash + model IDs — which is exactly roadmap G3's proof artifact |
| **OpenHands / SWE-agent class agent harnesses** | — | Agentic repo editing in a sandbox, gated on tests | Sandboxed execution + test-gated patches | **Yes — and this is the security lesson of §A.** Their patches run where breaking things is contained; our gate-3, once it actually runs, would execute target code unsandboxed in the user's tree. Fix the gate *and* the boundary together. [U] for their exact implementation details — not verified this session |
| **CodeQL / Copilot Autofix** | — | Query-based analysis + suggested fixes in the PR | Fix surfaced where the reviewer already is (PR annotation) | **Later** (roadmap G5, preview mode). Value established; requires the Action |

**What the comparison says about our three axes**

- **Security** — we are genuinely ahead of the named projects on one narrow axis: no other tool in this list publishes a *rejection* mechanism with rule-specific, deterministic audits. That advantage is **entirely wasted** while gate 3 is decorative, because a reviewer who discovers one gate never ran will discount the other two.
- **Speed** — we are not slow because of Python (0.24 s of local work per full eval); we are slow because of call count: `findings × attempts`, sequential, each with the whole file. The two cheapest levers, both grounded in the comparisons above: (a) widen anchors rather than re-sending the file for a retry, (b) triage once and cache verdicts across attempts (already partly true). Neither requires a rewrite; both are measurable.
- **Usage** — the gap is not features, it is **entry points**: no PyPI package, no GitHub Action, no proof file. A team cannot adopt this today even if they wanted to.

---

## C. Existing roadmap reconciliation

Every item in `.github/roadmap.json` plus the process issues that surround it. "Delivered vs acceptance" is judged against the item's own `acceptance_criteria`, not against whether a commit exists.

| Item | Implementation & issue/PR state | Delivered vs acceptance criteria | Recommendation |
|---|---|---|---|
| **G1** MCP010 audit | In `main` (`SMELLS["MCP010"]`, 4 patterns) + 31 verifier tests. Manifest `status: shipped`, `shipped_in: "main (unreleased)"`. No issue open. **[V]** | **Met.** Self-audit reproduces 5 rejects (None, inf, 10\*\*9, 1e9, 86400) and 3 accepts (10, 2.5, TIMEOUT_SECONDS) **[V]** | **Complete.** Keep `shipped` but correct the label: `shipped_in` should read "main, unreleased" *and* the item should not appear under "Shipped" in the status issue until a tag exists. Minor: change to `shipped_in: "unreleased @ main"` to stop implying a release |
| **G2** reason codes | Not implemented — `agent.py:179-193` writes prose into `why`. Open issue **#3**, labels `good first issue`/`difficulty/easy`. **[V]** | **Not met** (no `code` enum anywhere) | **Complete as scoped, and sequence it next.** It is the vocabulary G3's artifact must publish, so building G3 first means inventing it inside the artifact. Also: it is the only item small enough to be a genuine first contribution |
| **G3** proof artifact | Not implemented: no `src/vexar_autofix/report.py`, no `docs/proof-artifact.schema.json`. Open issue **#4**. **[V]** | **Not met** | **Keep, but revise the title.** "**signed** proof artifact" overclaims — no signing key, trust model or verification path exists in the repo, and `report.py` is not named in the criteria. Either rename to "versioned proof artifact" or add the signing decision to §G. Revise: artifact must record `tests_ok` **including `null`**, otherwise it will certify the defect in §A as a pass |
| **G4** fix-policy flags | Not implemented (`cli.py` has 8 flags, none of them policy). Open issue **#5**. **[V]** | **Not met** | **Keep, split.** `--allow-rules/--block-rules` are trivial (the rule set is already a `frozenset`) and defensible from `PRODUCT.md`'s adoption argument. `--require-approval` + `strict` presets are a different feature (interactive stop-and-apply) and belong in NEXT, not the same PR |
| **G5** GitHub Action | Not implemented: no `action.yml`, no `docs/action.md`. Open issue **#8**. **[V]** | **Not met** | **Keep in LATER, with one correction.** The item says "there is no way to use this from CI without a local install **and a key in the job**" — but `--provider mock` already gives keyless CI, and CI itself runs it. Rewrite the motivation around *reviewable output in the PR* (which needs G2+G3 first), or the item will be read as already partly done |
| **G6** rejection corpus | Not implemented: no `benchmarks/` directory. No issue (queue cap). **[V]** | **Not met** | **Keep — this is the highest-value proof item after the §A repair.** Reframe: it measures the *verifier*, which is the moat, and it is the one benchmark a competitor cannot copy from a README. Note it can start small: `SMELLS` already encodes ~10 named bad fixes that can become cases the same day |
| **G7** `VERIFICATION.md` | Not implemented: no `VERIFICATION.md`. No issue. **[V]** | **Not met** | **Promote into NOW's third item.** Its acceptance criterion ("token and cost fields populated from the provider response, not assembled by hand") is the *same defect* as G9. Two roadmap items for one bug is the kind of duplication the brief asks to flag — merge them |
| **G8** rename + publish | Issue **#2 `closed/completed`**; parent `vexar-mcp==0.3.0` on PyPI with `vexar_mcp` import **[V]**; `vexar-autofix` **404 on PyPI**, **0 tags, 0 releases** **[V]**; `RELEASING.md` steps 4–5 (PyPI pending publisher, `v0.1.0` tag) unperformed. Manifest: no `status` ⇒ treated as open work | **Partially met.** Criterion 1 (parent renames, shim) ✅; 2 (imports move) ✅; 3 (pin moves to a published version) ✅; 4 (**both install cleanly**) ❌ | **Split and re-open the remainder as a real item.** Do not accept the closed issue as completion. Recommended: mark the rename half `shipped`; add **G8b "first tagged release of vexar-autofix"** with the unsatisfied criterion verbatim. This is the clearest instance in the repo of *closed ≠ done*, and the automation cannot catch it |
| **G9** real token usage | Not implemented: `docs/data/runs.json` has `input_tokens: 0, output_tokens: 0, cost_usd: 0.0226` **[V]**. No issue. | **Not met — and the file is live on the demo page today** | **Keep, and make it NOW.** It is a public, machine-readable inconsistency in the artefact that carries the product's central claim. Cheapest possible fix: re-capture, or mark the run as pre-token-capture and stop rendering token counts until recaptured |
| **G10** SARIF | Not implemented: no `--sarif`. No issue. **[V]** | **Not met** | **Verify for duplication before building.** `PRODUCT.md` states the **parent** ships "SARIF + HTML reporters". So SARIF already exists in the suite — the child's version is about carrying *verifier verdicts*, not producing SARIF. Rewrite the item that way or drop it in favour of reusing the parent's reporter. As written it risks two SARIF emitters with different semantics |
| **Issue #1** "Roadmap status" | Open, bot-maintained, edited in place **[V]** | n/a | **Keep.** It is the correct pattern: one status artefact, never reopened |
| **Process: queue cap** | `max_open_roadmap_issues: 4` honoured — 4 open roadmap issues + 1 status issue **[V]** | Met | **Keep.** This is the mechanism that prevents the issue spam the brief warns about; document it in `CONTRIBUTING.md` so the cap is not read as neglect |
| **Process: drift detection** | `roadmap_status.py` prints "Drift: None… the plan, the queue and the tree agree" while G8's acceptance is unmet **[V]** | **Gap** | **Extend the drift check** to compare each open item's *acceptance criteria* against a declared evidence pointer (`shipped_in`, or a `blocked_on` field). Without this, every future "closed" will be read as "done" |

**Stale statuses / duplicates / broken evidence links, flagged explicitly**

- `README.md:461` — "46 tests" vs **76** actual. **[V]**
- `PRODUCT.md` — parent "v0.2.1", "pins the parent at a commit sha" vs `vexar-mcp==0.3.0` in `pyproject.toml`. **[V]**
- `README.md` — the "three properties that make this safe on a real repository" list omits the test gate it advertises in the table above it; the claim table and the enforcement table disagree about gate 3. **[V]**
- **Duplicate items:** G7 and G9 are the same defect from two angles (hand-assembled telemetry). Merge.
- **Evidence link at risk:** the README receipt cites `commit 30313a1`, which is **not in the current 40-commit history** (shallow-cloned history reaches `b0f9742`; `30313a1` is not reachable in the clone). **[U]** — the commit may exist on a deeper history; the demo page's provenance should cite a reachable commit or the run's own `generated_at` + `runs.json` git object.

---

## D. Prioritised roadmap

Sequencing principle: **the product's claim must be true before it is enlarged.** NOW contains one defect, its guard, and the honesty repair — small enough to finish in one cycle and verifiable with no API key. Everything that adds surface area is NEXT or later.

Effort ranges assume a single maintainer already familiar with the codebase, no new runtime dependencies, and a Nebius key available only for the final smoke run. They are judgement, not measurement — confidence is stated per item.

---

### NOW — the next delivery cycle (one gate, its guard, the honest numbers)

#### N1 — Make gate 3 real: run the target's tests against a materialised copy of the target root

- **User problem.** The tool tells the user "it still works — the target's test suite passes". It does not run that suite. A patch that breaks the tool is reported as verified. This is the one failure mode the whole product exists to prevent, so it is not a feature gap — it is the product being wrong.
- **Evidence.** `agent.py:200-202` (only the target file is copied), `agent.py:246` and `:291` (`run_tests(workspace.parent)`), `verifier.py:133-136` (`return None` when no `test_*.py` present), `cli.py:67` (`None` → "unchanged / passing"). Measured: target project with a deliberately failing suite → `tests_ok = None`, `verified = True`. **[V]**
- **Current state.** Gate 1 and gate 2 implemented and tested. Gate 3 present, unreachable in practice, untested.
- **Proposed scope.**
  1. Copy **the target's root** (parent directory, minus `.git`, `node_modules`, `.venv`, `__pycache__`) into the throwaway workspace, not the single file — so the patched module is what the tests import.
  2. Pass the **root**, not `workspace.parent`, and resolve the module by its path inside the copy.
  3. Represent the outcome honestly as a three-state result: `True` (ran, passed), `False` (ran, failed), `None` (could not run — no tests found, timeout, or interpreter error), with a `tests_detail` string saying which.
  4. Report `null` as `tests: not run (no test suite found in <root>)` — never as "passing" — in both `--json` and human output.
  5. Add an explicit `--tests-root PATH` override and a size/time cap, so a monorepo cannot turn a dry run into a 10-minute pytest run.
- **Non-goals.** Sandboxing/isolation (separate decision, see risks), test selection/ordering, per-test reporting, coverage, making tests a *hard* block on `--apply` (that is a policy question for G4), and any change to the scanner or the model prompts.
- **Priority.** P0. It is the difference between a verification product and a product that says it verifies.
- **Dependencies / sequence.** Depends on the sandbox decision (§E risk 2) being recorded — see the note below. Must land **before** G3, because the artifact will otherwise certify `tests_ok: null` as a pass.
- **Acceptance criteria (observable from user behaviour).**
  - Given a target whose test suite fails after the patch, the run is **not** verified, the patch is not applied under `--apply`, and the report says the tests failed.
  - Given a target with no tests, the report says tests were **not run** and does not use the word "passing".
  - Given a target whose tests pass after the patch, the run verifies as before.
  - `--json` carries `tests_ok` ∈ {true,false,null} plus `tests_detail`; `null` is never rendered as a pass.
  - The existing 76 tests still pass; `--no-tests` still skips the gate and is visibly recorded as skipped.
- **Automated tests.** New fixture package `tests/fixtures/project_with_failing_tests/` (module + `test_*.py` that fails *after* the canonical patch; plus a passing variant, plus a no-tests variant). Assert the three states end-to-end through `autofix(..., check_tests=True)`. Unit-test `run_tests` on each fixture root.
- **Manual / hardware validation.** Run once against a real, non-fixture MCP server repo with a genuine test suite, in a disposable clone, with `--apply` **off**; confirm the report's claim matches the suite's actual result. Record the repo and the outcome in the PR.
- **Security / privacy.** Copying the root must not copy `.git`, credentials, `.env` or venvs — enumerate an allowlist of file types rather than a denylist of directories. **Fixing this gate activates previously dormant code execution:** `run_tests` runs the target's tests with the caller's privileges and CWD (`verifier.py:137-144`). Sequence: land the visible `--no-tests`/`tests: not run` reporting first, land the copy+run second, and add a prominent one-line warning to `--help` and the report header. The safe long-term boundary (container/subprocess with no network, read-only bind) is a **separate NEXT item**, deliberately not bundled here.
- **Effort.** 1–2 days for the copy+run+reporting; +0.5 day for the three fixtures. **Confidence: high** on the defect and the fix shape; **medium** on the "copy the root" edge cases (monorepos, symlinks, huge trees).
- **Success measure.** On the failing-tests fixture, `verified` is `false` and the CLI never prints "passing"; measured by the new test. Secondary: zero occurrences of the string "unchanged / passing" when `tests_ok` is `null` (grep-able in tests).

#### N2 — Pin gate 3: the first test that runs `check_tests=True`, and a guard against silent gate removal

- **User problem.** A user cannot distinguish "the gate passed" from "the gate was quietly broken", because nothing in the suite exercises it. Every one of the 12 agent tests disables it.
- **Evidence.** `tests/test_agent.py` — all 12 call `check_tests=False`; `grep -rn "tests_ok\|run_tests\|no-tests" tests/` → **no matches** **[V]**.
- **Current state.** Absent. The README's invariant list claims "Each is already pinned by a test"; gate 3 is not.
- **Proposed scope.** (a) Add the fixtures from N1. (b) Add a `tests/test_gates.py` that asserts each of the three gates independently rejects a bad patch — a "gate matrix" so one gate cannot rot unnoticed. (c) Add a documentation-invariant test that fails if the README's gate table and the code's gate set disagree (parse the table, compare against a declared `GATES` constant).
- **Non-goals.** Rewriting existing tests, chasing coverage percentages, testing the model client.
- **Priority.** P0 — the same change set as N1, and the reason N1 will not silently regress.
- **Dependencies.** Sibling of N1; the (c) sub-item depends on introducing a `GATES` constant in `verifier.py`/`agent.py`.
- **Acceptance criteria.** Deleting the `run_tests` call, or reverting `workspace.parent`→`workspace`, makes the suite fail. `pytest -q` count rises from 76.
- **Automated tests.** This item *is* the tests. Mutation check documented in the PR: comment out the gate, watch the suite go red, restore.
- **Manual validation.** None beyond CI on 3.10–3.13.
- **Security / privacy.** None directly; it is the guard that keeps N1 from being undone.
- **Effort.** 0.5–1 day. **Confidence: high.**
- **Success measure.** The mutation check in the PR: gate removed ⇒ suite fails.

#### N3 — Make the published evidence internally consistent (merge G9 + G7's telemetry criterion)

- **User problem.** The demo page and README are the receipt. Today one file on it reports zero tokens and a non-zero cost, and the README's test count is stale. A sceptic who checks the cheapest number finds an inconsistency, and then discounts the expensive ones.
- **Evidence.** `docs/data/runs.json` → `input_tokens: 0, output_tokens: 0, cost_usd: 0.0226, calls: 18` **[V]**; `clients.py:_record` always increments all three together, so a live capture cannot produce that shape **[V]**; `README.md:461` "46 tests" vs 76 **[V]**; `PRODUCT.md` v0.2.1/commit-sha drift **[V]**.
- **Current state.** G9 and G7 both open in the manifest; no issues filed (queue cap). One bug, two roadmap items.
- **Proposed scope.** (a) Re-capture with a key, **or** — if no key is available — mark the committed run as `"telemetry": "pre-token-capture (2026-10-28)"` and stop rendering token fields the page cannot substantiate. (b) Add a schema test asserting `usage.input_tokens + output_tokens > 0 ⇒ cost_usd > 0` and that mock runs carry explicit `null`s. (c) Correct the two doc drifts and add a test that the README's stated test count matches `pytest --collect-only`. (d) Merge G7 into G9 in `roadmap.json` so the manifest stops double-counting one defect.
- **Non-goals.** A full `VERIFICATION.md` (that is G7's remaining half, and belongs in NEXT once all numbers are single-sourced); re-recording the demo video; changing the scanner data (`scan.json` already reproduces perfectly).
- **Priority.** P1 — it protects the asset that makes everything else credible.
- **Dependencies.** None. Independent of N1/N2, so it can run in parallel or be taken by a second contributor.
- **Acceptance criteria.** Every number rendered on the demo page is emitted by `capture_demo.py` and validated by a test; no token field contradicts `cost_usd`; README's test count equals the collected count.
- **Automated tests.** `tests/test_demo_data.py` — parses `docs/data/runs.json`, asserts internal consistency and that its key set matches what `docs/index.html` reads (the page's keys are known: `.runs`, `.usage`, `.cost_usd`, `.calls` **[V]**).
- **Manual validation.** Load the Pages demo and confirm every number on screen traces to `runs.json`.
- **Security / privacy.** A live re-capture sends `examples/*.py` (public fixtures) to Nebius and costs ~$0.02. Do not capture against any private repository.
- **Effort.** 0.5 day if a key is available; 0.25 day for the "mark as pre-capture + add test" path. **Confidence: high.**
- **Success measure.** The consistency test exists and passes; a reader can trace every on-page number to one file.

**Why NOW stops here.** Three items, one dependency chain, all verifiable without hardware, and together they convert the README's central table from *mostly true* to *true*. Adding G2 to NOW would be reasonable (it is easy and unblocks G3); it is listed as NEXT-1 so this cycle stays finishable.

---

### NEXT — after NOW succeeds

#### X1 — G2: stable reason codes on every bucket entry
- **Problem.** A CI consumer cannot route on prose; `why` is a human string (`agent.py:179-193`).
- **State.** Not implemented; issue #3 open, `good first issue`.
- **Scope.** Closed enum `no_remedy | not_confirmed | unsafe_rule | ambiguous_anchor | verification_failed | tests_failed | model_no_edits`; keep `why`; expose in `--json`; test that no bucket entry can exist without a code.
- **Non-goals.** Localisation, coded messages for the *triage* verdicts (separate vocabulary), changing any existing string.
- **Priority.** P1. It is the vocabulary the proof artifact publishes, so it must precede X2.
- **Deps / sequence.** After N1 (so a new code `tests_unavailable` exists rather than being bolted on later). **Effort** 0.5–1 day, confidence high.
- **Acceptance.** Every entry in all four buckets carries a documented code in `--json`; the enum is documented in `VERIFICATION.md`/README.
- **Tests.** Property-style test over all fixtures: every bucket entry has a code; codes ⊆ enum.
- **Security.** None. **Success measure.** A consumer can branch on codes without string matching (demonstrated by a test that routes on `code`).

#### X2 — G3: versioned proof artifact (`--report PATH`)
- **Problem.** Evidence today is a terminal diff plus `--json`; a security team needs a file to attach, diff between releases, and keep after uninstall.
- **State.** Not implemented; issue #4 open. No `report.py`, no schema.
- **Scope.** Versioned JSON: schema version, target hash before/after, scanner version, model IDs, per-finding decision **with code**, the diff, each gate's result — **including `tests_ok: null` with `tests_detail`** — and `verified: true` only when all three gates returned pass. Publish `docs/proof-artifact.schema.json`; golden test for determinism excluding timestamps.
- **Non-goals.** **Signing** (rename the item: no key/trust model exists; a "signed" artifact with no verification path is worse than none), storage, upload, HTML rendering.
- **Priority.** P1 — the moat made portable.
- **Deps.** X1 (codes), N1 (honest gate state). **Effort** 3–5 days, confidence medium (schema design is where over-reach happens).
- **Acceptance.** File validates against the schema; deterministic apart from timestamps; `verified` false whenever any gate is `false` **or `null`-where-required**.
- **Tests.** Golden file; schema validation in CI; a test that asserts an artifact can never claim `verified` while any gate is not `true`.
- **Security.** The artifact embeds source diffs — document that it can contain secrets from the target file, and never auto-publish it.
- **Success measure.** An artifact from a real run is attached to a PR and a reviewer accepts or rejects the patch from it without opening the terminal.

#### X3 — G4a: bound what may be touched (`--allow-rules`, `--block-rules`)
- **Problem.** The fixable set is global; a team cannot say "timeouts only".
- **State.** Not implemented; issue #5 (split). **Scope.** Two flags over the existing `AUTOFIXABLE` frozenset; blocked rules reported, never attempted.
- **Non-goals.** `--require-approval`, `strict` presets (interactive flow — separate item).
- **Priority.** P1. **Deps.** None (N1-independent). **Effort** 0.5–1 day, confidence high.
- **Acceptance.** A blocked rule appears in `refused` with a `blocked_by_policy` code and is never sent to the model.
- **Tests.** Assert zero model calls for a fully blocked rule set (`MockClient.usage.calls == 1`, triage only — or 0).
- **Security.** Reduces blast radius; this is the cheapest safety control in the list. **Success measure.** A reviewer can state the tool's exact write surface in one flag.

#### X4 — G6 (small): turn the existing `SMELLS` table into the first rejection-corpus cases
- **Problem.** The differentiator is refusing bad patches; there is no public evidence of how often it refuses, and no regression protection for the audits themselves.
- **State.** No `benchmarks/`. But `SMELLS`/`REMEDY_MARKERS` already encode ~10 named bad fixes **[V]** — the corpus is 80% written, just not extracted.
- **Scope.** `benchmarks/rejections/` with one case per named bad fix (rule, added-lines fragment, expected verdict, expected reason substring) plus the accepted canonical set; run in CI; publish the count in README and on the demo page.
- **Non-goals.** A model-in-the-loop benchmark, real-world repo harvesting (that is the larger G6).
- **Priority.** P1 for the *differentiator's evidence*; cheapest high-credibility item in the whole plan.
- **Deps.** N3 (so the published count is trustworthy). **Effort** 1–2 days, confidence high.
- **Acceptance.** Corpus runs in CI; count is published; a new audit rule cannot be added without a case (test enforces `len(cases) ≥ len(SMELLS patterns)`).
- **Security.** None. **Success measure.** The published rejection count exists and only ever rises.

#### X5 — Duplicate-anchor disambiguation (speed × reliability)
- **Problem.** When the model quotes an anchor that appears twice, we reject with "anchor is ambiguous (2 matches)" (`verifier.py:69-71`) and burn an attempt. The model is not told *how* to fix it. This is the known failure mode of search/replace editing, and the ecosystem's answer is to widen the context [6].
- **State.** Rejection implemented; guidance absent. **[V]**
- **Scope.** Change the message to an instruction (include surrounding context so the anchor is unique; show the two candidate lines), and let the retry send **only the anchor region** rather than the whole file.
- **Non-goals.** Fuzzy matching, line-number patching, a new edit format (the comparison in §B2 argues *against* unified diffs).
- **Priority.** P2. **Deps.** None. **Effort** 1 day, confidence medium-high.
- **Acceptance.** On a fixture with a duplicated anchor, attempt 2 succeeds instead of exhausting `--max-attempts`; measured token payload for the retry drops materially versus re-sending the file.
- **Tests.** Duplicate-anchor fixture: assert the second attempt's payload excludes the full source and the run verifies.
- **Security.** None. **Success measure.** Fewer attempts per fixed finding (observable in `report["attempts"]`), lower cost per run.

#### X6 — Triage quality measurement (adopt from Semgrep's published-agreement practice)
- **Problem.** Triage sends "confirmed" verdicts to the patch queue, and its accuracy is unknown; a wrong "confirmed" wastes money and a wrong "mitigated" hides a vulnerability (`prompts.py` says exactly this, then never measures it).
- **State.** Implemented, unmeasured **[U]**. **Scope.** Label the three fixtures' 15 findings by hand (exploitable / mitigated / unclear) as ground truth in `eval/`; compute and publish triage agreement; fail CI on regression.
- **Non-goals.** Model shopping, prompt-engineering competitions, any cloud dependency.
- **Priority.** P2 — it converts an unmeasured LLM step into a number, which is the same discipline as the scanner gates.
- **Deps.** N3. **Effort** 2–3 days, confidence medium.
- **Acceptance.** A published agreement rate with its fixture basis, and CI red when it drops.
- **Tests.** Offline with `MockClient` (which is deterministic by construction); live rate recorded, not gated, without a key.
- **Security.** None. **Success measure.** One number in the README that a sceptic can recompute.

#### X7 — Execution boundary for the test gate (the security counterpart to N1)
- **Problem.** N1 activates real code execution (`verifier.py:137-144`); the target's tests run with the user's privileges, network and CWD.
- **Scope.** Run the gate in a subprocess with: no network (or an explicit `--allow-network`), read-only bind of the target root except the workspace copy, a wall-clock cap, and a clear statement in `--help` and the report header.
- **Non-goals.** Full container orchestration, Windows-specific sandboxing, gVisor/Firecracker.
- **Priority.** P1 *sequenced immediately after N1* — the gate should not run unsandboxed on other people's code for long.
- **Deps.** N1. **Effort** 2–3 days, confidence medium (portability across Linux/macOS/Windows is the risk).
- **Acceptance.** With the boundary on, a test that writes outside the workspace or opens a socket fails; documented fallback for platforms without the primitive.
- **Tests.** Adversarial fixture: a test that tries to write to `../` and to open a socket; assert the run reports the gate as failed/blocked rather than passing.
- **Security.** This *is* the security item. **Success measure.** The documented, enforced statement: "the gate cannot modify anything outside the throwaway workspace."

---

### LATER — valuable, but needs prerequisites

| Item | Why later | Prerequisite |
|---|---|---|
| **G5 GitHub Action** (preview → gate → apply) | Highest adoption value, but a preview comment is only worth posting once verdicts carry codes (X1) and a proof artifact (X2) | X1, X2 |
| **G8b first tagged release** (`v0.1.0`) | Blocks adoption entirely; needs a PyPI pending publisher owned by the maintainer's PyPI account — not a code task | Maintainer action; `publish-pypi.yml` already correct |
| **G7 `VERIFICATION.md`** (remaining half) | Only meaningful once every published number is single-sourced (N3) | N3 |
| **G6 (full) real-world runs** | Requires the gate to be trustworthy first, plus a disposable external repo and a write-up including refusals | N1, X7 |
| **G4b `--require-approval` / `strict` presets** | Interactive approval flow is a UX design task, not a flag | X3, and a decision on whether approval is a prompt or an exit code |
| **Speed: batch/parallel patching** | Real latency is provider-bound (`O(findings × attempts)` sequential calls **[V]**); parallelism changes the failure-attribution contract that makes one-finding-per-attempt reviewable | X5 first (fewer attempts), and a cost/attribution decision |
| **Multi-file / repo-wide remediation** | Every gate is scoped to one file today; the cross-file story is a different product | Proof artifact + policy flags |

### DEFER / DO NOT BUILD

| Idea | Verdict | Reason |
|---|---|---|
| **Rebuild the repo as the "Pinch" Windows assistant** | **Defer to an explicit maintainer decision (§G1)** | No desktop/audio/memory surface exists; doing it here would be a rewrite, not an upgrade, and would strand the verification asset |
| More fixable rules (5th, 6th, 15th) | **Do not build now** | `ROADMAP.md` already says four audited rules beat fifteen unaudited ones; §A shows the audit is the claim, and one gate is currently decorative. Coverage without remedy is refusals |
| Web search inside the fix loop | **Do not build** | Already a recorded non-goal, and correctly reasoned: it makes the output a property of the afternoon rather than of the commit |
| Hosted SaaS / dashboard | **Do not build** | The artifact is the product; a hosted surface adds a data-residency problem to a tool whose claim is local reproducibility |
| Editing format rewrite (unified diffs, whole-file rewrites) | **Do not build** | The exact-anchor primitive is the one the ecosystem's own benchmarks converged on [4][5][6]; unified diffs reintroduce line arithmetic and laziness failures |
| LLM-as-judge for patch acceptance | **Do not build** | Accepting model output on model authority is precisely what the product argues against |
| A second SARIF emitter | **Do not build** | The parent already ships SARIF **[V, per PRODUCT.md]**; the child's job is verdicts, not serialisation |
| PyPI publish before the pending publisher exists / tagging a branch | **Do not build** | `RELEASING.md` already forbids it; a half-published name is worse than an unpublished one |

---

## E. Top five risks, and the gates they impose

**1. The receipt is wrong in one place, so it is trusted nowhere.**
Gate 3 never runs, its `null` is rendered as "passing", and the demo telemetry reports zero tokens with a non-zero cost. A proof product caught overstating is finished — the argument that "the scanner can be fooled, we cannot" depends on us not being the ones who were fooled.
*Gate:* no item may claim a gate is enforced unless a test fails when that gate is removed. N2's mutation check is a release blocker. The README's gate table must be generated from, or tested against, a `GATES` constant (N2c).

**2. Fixing gate 3 turns on unaccounted code execution.**
`run_tests` executes the target's test suite with the caller's privileges, network and CWD. Today the defect hides this. After N1 it is live.
*Gate:* N1 may not merge without (a) the visible "tests not run" path, and (b) an explicit, documented statement of the execution boundary plus a tracked follow-up (X7) with an owner. No `--apply` release until X7 lands.

**3. Adoption is impossible for structural reasons, and no amount of verification fixes it.**
`vexar-autofix` is not installable from any index (PyPI 404, zero tags), has no CI entry point, and its evidence is a terminal transcript. Every NEXT item assumes someone can obtain the tool.
*Gate:* G8b (first tag) requires the maintainer's PyPI pending publisher. Until then, "release readiness" must be reported as **blocked**, not "shipped in main".

**4. The verifier's authority is unmeasured.**
Triage accuracy is unknown **[U]**; the rejection corpus does not exist; the audit's own coverage is asserted by a test but its *precision* (false rejections of good patches) is unmeasured. The moat is the verifier, and the verifier has no public scorecard of its own.
*Gate:* X4 and X6 produce the first two numbers. Any external claim of "verifier accuracy" before then is unverified by definition.

**5. Automation is strong enough to create false confidence.**
Ten workflows, six bots, a status issue, a drift check — all reporting health, and all blind to the one discrepancy that matters (issue #2 closed while its acceptance criterion is unmet **[V]**). A monitoring system that reports "Drift: None" is a risk in itself, because it discourages the manual check that would have caught this.
*Gate:* extend the drift check to compare issue state against a declared evidence pointer (§C). Any future closure of a roadmap item must name the evidence (commit, tag, test) that satisfies each acceptance criterion.

---

## F. First three GitHub issue drafts

> Drafts only. Nothing has been filed. Each is written to be pasted as-is, and each is scoped so that its acceptance criteria are observable rather than aspirational.

---

**Issue 1**

**Title:** `fix(agent): run the target's test suite against the target root — gate 3 currently never runs`

**Labels:** `type/security`, `priority/p0`, `area/agent`, `difficulty/medium`

**Body:**

Gate 3 of the README's verification table — *"It still works — the target's own pytest suite must pass after the patch"* — does not run on any real invocation.

`agent.py:200-202` copies **only the target file** into the temp workspace, then `agent.py:246` calls `run_tests(workspace.parent)`. `run_tests` returns `None` when the directory contains no `test_*.py` (`verifier.py:135-136`), which is every non-fixture target. The CLI then renders that `None` as `tests unchanged / passing` (`cli.py:67`).

Reproduction (offline, no key): build a project at `proj/` containing `vulnerable_server.py` as `server.py` plus a `test_server.py` that asserts `False`.
- `run_tests(proj)` → `False`
- `autofix(MockClient(rehearse_accept=True), proj/"server.py", check_tests=True)` → `tests_ok = None`, `verified = True`, `fixed = 1`

So a patch that breaks the tool's tests is reported as verified.

**Acceptance criteria**
- [ ] The workspace is materialised from the target's **root** (excluding `.git`, venvs, `__pycache__`, `node_modules`), so the patched module is what the tests import.
- [ ] `run_tests` is called with the **root**, not `workspace.parent`.
- [ ] `tests_ok` is `True` / `False` / `null` with a `tests_detail` string; `--json` exposes both.
- [ ] `null` is never rendered as "passing" in human output; no test suite ⇒ "tests not run", not a pass.
- [ ] A `--tests-root PATH` override and a wall-clock cap exist.
- [ ] Existing 76 tests pass; `--no-tests` still skips and is visibly recorded.

**Out of scope:** sandboxing (tracked separately — see #X7), per-test reporting, coverage, making tests a hard block on `--apply`.

**Security note:** this change activates dormant code execution (`verifier.py:137-144`). Ship the honest reporting first, then the real run, and add the boundary warning to `--help`. This must not merge before the execution-boundary follow-up is filed.

---

**Issue 2**

**Title:** `test(agent): pin the three gates with a gate matrix — the first test that runs check_tests=True`

**Labels:** `type/security`, `priority/p0`, `area/agent`, `difficulty/easy`

**Body:**

All 12 tests in `tests/test_agent.py` pass `check_tests=False`, and `grep -rn "tests_ok\|run_tests\|no-tests" tests/` returns nothing. The test gate — and the `--no-tests` flag — have zero coverage, which is why the defect in the previous issue survived review and why the README's "each invariant is pinned by a test" is currently untrue for gate 3.

**Scope**
- [ ] `tests/fixtures/project_with_failing_tests/` — module + `test_*.py` that fails after the canonical patch. `project_with_passing_tests/`, `project_with_no_tests/` alongside it.
- [ ] `tests/test_gates.py` — a three-gate matrix: for each gate, a fixture patch that clear gate 1 and 2 and fails only that gate must be rejected.
- [ ] A documentation invariant: parse the gate table in `README.md` and assert it matches a `GATES` constant, so the docs cannot claim a gate the code does not enforce.
- [ ] Mutation check recorded in the PR: comment out the `run_tests` call, confirm the suite goes red, restore.

**Acceptance criteria**
- [ ] Deleting the gate, or reverting the workspace-copy change, makes `pytest` fail.
- [ ] Test count rises above 76 and every gate has at least one dedicated test.
- [ ] No test needs an API key or a network.

---

**Issue 3**

**Title:** `fix(proof): docs/data/runs.json reports zero tokens with a non-zero cost — reconcile with capture_demo.py`

**Labels:** `type/proof`, `priority/p1`, `area/cli`, `difficulty/easy`, `good first issue`

**Body:**

`docs/data/runs.json` — the file behind the live demo page — reports:

```json
"usage": { "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0226, "calls": 18 }
```

`clients.py:_record` increments input tokens, output tokens and cost together, so a live capture cannot produce that shape. The cost was therefore not derived from the recorded provider response, which contradicts the file's own `provenance` field ("copied from that terminal output, not estimated").

Related drift found during review: `README.md:461` says "46 tests"; the suite collects 76. `PRODUCT.md` lists the parent as "v0.2.1" and a commit-sha pin; `pyproject.toml` pins `vexar-mcp==0.3.0`.

**Acceptance criteria**
- [ ] Either re-capture with a key, or mark the 2026-10-28 run as `"telemetry": "pre-token-capture"` and stop rendering token fields the data cannot substantiate.
- [ ] `tests/test_demo_data.py` asserts: `input_tokens + output_tokens > 0 ⇒ cost_usd > 0`; mock runs carry explicit `null`s; the key set matches what `docs/index.html` reads (`.runs`, `.usage`, `.cost_usd`, `.calls`).
- [ ] A test asserts the test count quoted in `README.md` equals `pytest --collect-only -q` output.
- [ ] `roadmap.json` merges G7 and G9, which describe this same defect from two angles.

**Out of scope:** a full `VERIFICATION.md` (G7's remaining half), re-recording the demo video, `docs/data/scan.json` (which reproduces correctly).

---

## G. Unknowns and decisions only the maintainer can make

1. **Is "Pinch" this repository?** The brief describes a Windows local-first assistant; this is an MCP remediation CLI. Either Pinch is a separate product (and this roadmap stands alone), or the intent is to reuse the verification layer inside a new assistant surface (in which case a new repository is the cheaper path — the two share no runtime code today). **This decision changes everything below it and cannot be inferred from the repo.**
2. **Is the "signed" in G3's title intended?** No key, trust model, or verification path exists. Signing implies a publisher identity and a consumer that checks it; that is a design problem, not a flag.
3. **Who owns the PyPI pending publisher?** `RELEASING.md` step 4 requires the maintainer's PyPI account. Repository access is insufficient. Until it exists, G8b is blocked, not "in progress".
4. **What is the acceptable execution boundary for the test gate?** Options: (a) run in the user's tree with a warning (current posture, after N1 — cheapest, least safe), (b) subprocess with no network and a read-only bind (X7), (c) container required (safest, worst onboarding for Windows users). This is a product decision about who the user is.
5. **Is `--apply` allowed to run unattended in CI at all?** `ROADMAP.md` says "no unattended `--apply` on a high-risk rule, ever" — does that mean `apply` mode in G5 is prohibited by policy, or merely gated?
6. **What counts as "hardware validated" here?** For a pure-Python CLI the analogue is "validated against a real external repository". No such run is recorded anywhere in the repo **[U]**. Does the maintainer accept fixture-only validation as release-worthy?
7. **Is the demo-capture workflow's `contents: write` + scheduled commit to `main` acceptable long-term?** It is currently the only way the receipt refreshes, and it means a scheduled job can rewrite the evidence file on the default branch.
8. **Which commit is `30313a1`?** The README receipt cites it; it is not reachable in a shallow clone **[U]**. Is it on `main`'s history?

---

## H. Checks run, exact results, and what was not checked

**Environment:** Linux sandbox, Python 3.13.16, fresh `git clone --depth 50` of `main` @ `6aa548e`. No API key present. No microphone, GPU or Windows host available.

| # | Command | Result |
|---|---|---|
| 1 | `git clone https://github.com/RANJITHROSAN17/vexar-autofix` | Success; 40 commits; branches: `main` only |
| 2 | `pip install -e ".[dev]"` | Success; resolved **`vexar-mcp==0.3.0` from PyPI** (159 kB wheel) + mypy/ruff/pytest |
| 3 | `import vexar_mcp` / `import mcp_doctor` | `vexar_mcp` imports **OK** from site-packages; `mcp_doctor` **not installed** ⇒ no namespace collision **[V]** |
| 4 | `ruff check .` | **All checks passed** |
| 5 | `mypy src --strict` | **Success: no issues found in 7 source files** |
| 6 | `python -m pytest -q` | **76 passed** (test_verifier 31, test_bots 24, test_agent 12, test_cli 6, test_release_dependency 3) |
| 7 | README receipt reproduction (inline scanner script) | `vulnerable_server 12 findings 4/100 9 rules` · `helper_delegation 3 findings 73/100 3 rules` · `clean_server 0 findings 100/100 0 rules` — **matches README exactly** |
| 8 | `python .github/scripts/self_audit.py` | **11/11 claims reproduce** (3 fixture scores + 5 MCP010 rejects + 3 accepts) |
| 9 | `python .github/scripts/validate_workflows.py` | **10 workflow file(s) valid** |
| 10 | `python .github/scripts/sync_roadmap_issues.py --dry-run` | Validated 10 items / 27 labels; would open **4** issues (G8, G2, G3, G4); 1 marked shipped — cap of 4 honoured |
| 11 | `python .github/scripts/roadmap_status.py --dry-run` | "1/10 items shipped"; **"Drift: None. The plan, the queue and the tree agree."** — contradicts the G8 finding below |
| 12 | `python eval/run_eval.py --provider mock` | Ground truth matched, zero regressions; 48 calls, ~$0.0000; **0.24 s wall clock** for the whole 3-fixture eval |
| 13 | **Gate-3 probe** (custom script) | `run_tests(real_proj_with_failing_test)` → **`False`**; agent workspace contains only `['server.py']`; `run_tests(workspace)` → **`None`**; `autofix(..., check_tests=True)` → **`tests_ok=None`, `verified=True`, fixed=1`** |
| 14 | `grep -rn "tests_ok\|run_tests\|no-tests" tests/` | **no matches** — gate 3 untested |
| 15 | `grep -n add_argument src/vexar_autofix/cli.py` | 8 flags; **no** `--report`, `--sarif`, `--policy`, `--allow-rules` |
| 16 | `ls src/vexar_autofix/` / `ls benchmarks` | 7 modules (no `report.py`); **no `benchmarks/`** |
| 17 | GitHub REST: `issues?state=all` | 10 items: **4 open roadmap issues (#3,#4,#5,#8)**, 1 open status issue (#1), **#2 closed/completed (G8)**, 4 merged Dependabot/docs PRs (#6,#7,#9,#10) |
| 18 | GitHub REST: `releases`, `tags` | **No releases, no tags** |
| 19 | PyPI JSON API | `vexar-autofix` → **404 Not Found**; `vexar-mcp` → versions **['0.3.0']** |
| 20 | Payload sizing probe | per-attempt patch payload: vulnerable 1,279 B / helper 2,829 B / clean 1,797 B; triage payload 1.8–3.4 KB (full source each time) |
| 21 | `git status --porcelain` after all checks | clean — **the analysis did not modify the repository** |

**Deliberately not performed** (and therefore **not claimed**)

- **Any live-provider run.** No `NEBIUS_API_KEY`. Every real-model number in the README (18 calls, $0.0226, 7 verified fixes, 4→46, 73→100) is **unverified in this session** — I verified only the deterministic scanner half of the receipt, which does reproduce.
- **`--preflight` against a live endpoint** (needs a key).
- **Windows, tray, microphone, GPU, audio, local-model inference** — no such code exists and no hardware was available. Nothing in this document is a claim about them.
- **Hardware/OS validation of any kind.** No claim of "validated on a real MCP repository" is made; the repository records none.
- **GitHub Actions run logs** — not fetched; workflow *definitions* were read and validated, not their execution history. Whether CI is currently green on `main` is **[U]**.
- **Dependency audit** (`pip-audit`, `osv-scanner`) — not run; supply-chain status of `vexar-mcp==0.3.0` is **[U]**.
- **Mutation testing** on the verifier — the N2 mutation check is proposed, not executed.
- Older history beyond the 50-commit shallow clone (relevant to the `30313a1` provenance question).

**Sources for §B2 comparisons** (third-party, not measured here): [1] star-history.com/semgrep/semgrep · [2] github.com/semgrep/semgrep · [3] theairankings.com/best-ai-code-review · [4] notes.aimodels.fyi (aider unified-diff/SEARCH-REPLACE benchmark) · [5] agentpatterns.ai/tool-engineering/llm-edit-format-selection · [6] kondasamy.com (search-replace failure modes, duplicate matches) · [7] practical-devsecops.com/top-mcp-security-tools.

---

## Appendix — one-paragraph version

`vexar-autofix` has a real, small, tested verification core and a receipt that reproduces byte-for-byte, and it has one gate that never runs, is reported as passing, and has no test — in a product whose only claim is that its gates are real. The correct next move is not more features and not a pivot to a desktop assistant the repository does not contain: it is to fix gate 3, pin all three gates so they cannot rot, and make the published numbers internally consistent. After that, the existing roadmap's own next items (reason codes → proof artifact → policy flags → rejection corpus) are the right ones, in that order, because each one turns the verification discipline into something a stranger can check without reading the source.
