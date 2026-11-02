# Pinch product roadmap proposal (repo-grounded)

## Summary

The repository currently does not implement the product direction described for Pinch. The codebase in `main` is a Python CLI for MCP security patch verification (`vexar-autofix`), not a local-first Windows personal assistant. It has a CLI, mock/offline rehearsal, optional Nebius provider, fixed rule set, and verification gates, but it lacks a Windows tray/widget, voice stack, local model runtime, memory system, app/file/system integrations, and a user-facing assistant experience.

This proposal therefore treats the repository as a product-architecture evidence source, not as proof that the Pinch product exists. The recommended direction is to keep the product vision aligned with the requested Pinch principles: local-first defaults, explicit approvals, honest reporting, lightweight maintainable design, and no cloud dependency for core control flow. The near-term roadmap should validate a minimal “desktop agent” shell that can run local tasks transparently, while preserving the repo’s verification discipline as the highest-value technical moat.

## A. Executive summary

Current strengths:
- Strong evidence of disciplined engineering around verification and safety: `verifier.py`, `agent.py`, `tests/test_verifier.py`, `ci.yml`, `SECURITY.md`, and `ROADMAP.md` show a concrete safety protocol rather than a casual demo.
- Dry-run-first behavior and fail-closed rules are explicit in the CLI and product docs.
- The repo already has a mock/offline rehearsal path and CI gates for lint, type-checking, tests, and eval.
- There are clear product claims and explicit honesty about unknowns; the code and docs avoid pretending an unrealistic release has happened.

Major gaps versus the requested Pinch direction:
- No Windows/desktop companion or startup recovery path is present in the repository evidence.
- No local voice/wake-word or microphone consent flow appears in code or docs.
- No task memory, preferences, schedule/reminder system, clipboard integration, or app/file/system orchestration wrapper is visible.
- The “model” story is currently external-provider driven (`nebius`/`mock`), not local-model-first.
- There is no evidence of real user onboarding, uninstall/update flows, accessibility review, or Windows-specific support.
- The codebase is a security tool and not a general-purpose local assistant; the product still needs a market and architecture pivot if it is to become Pinch.

Recommended direction:
- Keep the repo’s verification discipline as the core “trust” layer; do not convert it into a generic chat web app.
- Build a minimal Pinch shell around a local-first task loop: local agent runtime, explicit permission gate, file/app context access, clipboard and reminder tasks, and transparent action logs.
- Treat model choice and always-on availability as optional and user-controlled; cloud-only audio is explicitly disallowed by product direction.

## B. Evidence-backed current-state matrix

| Area | Repo evidence | Status | Assessment |
|---|---|---|---|
| Product type | `README.md`, `PRODUCT.md`, `src/vexar_autofix/cli.py` | Implemented but mismatched to Pinch | This is a security verifier/CLI tool, not a Windows personal assistant. |
| CLI | `src/vexar_autofix/cli.py` | Implemented | Good dry-run CLI; supports mock and Nebius; explicit `--preflight`, `--target`, `--apply`, `--json`. |
| Verification rules | `src/vexar_autofix/verifier.py` | Implemented and tested | Strong safety protocol and audit rules; MCP010 fix is evidence-based. |
| Mock/offline rehearsal | `README.md`, `cli.py`, `eval/` | Implemented | Useful for safe development and demos. |
| CI | `.github/workflows/ci.yml` | Implemented | Lint, typecheck, tests, mock eval, workflow validation. |
| Security posture | `SECURITY.md` | Implemented | Clear vulnerability and verifier bypass reporting path. |
| Release process | `RELEASING.md`, `.github/workflows/publish-pypi.yml` | Partially implemented | Publish pipeline exists, but public release remains gated by parent package publication and maintainer setup. |
| Windows app/tray | No evidence under `src/` or repo root | Not implemented | Missing direct evidence of Windows shell, service, startup recovery, tray integration. |
| Local voice | No `voice`, `wake`, `microphone`, `speech`, or Windows accessibility code found in root listing | Not implemented | Not evidence-backed for mic consent or local speech. |
| Memory/preferences | Not found in repo tree and docs | Not implemented | No persisted personal memory schema or settings store. |
| Files/apps/system tasks | Not found in repo tree and docs | Not implemented | No app automation or OS task model present. |
| Local model support | `--provider {nebius,mock}` only; no local model runtime or LLM selection | Not implemented | Not aligned with “local-model default” requirement. |
| Privacy controls | `README.md` and CLI caution about secrets; CLI warns on secret patterns | Partially implemented | Good docs on secret handling; no user-visible consent matrix for microphone, actions, or app permissions. |
| Accessibility | No evidence in repo | Unknown / not implemented | No accessibility or non-technical-user UX work visible. |
| Product trust model | `PRODUCT.md` | Implemented as a documented strategy | This is the strongest repo-specific product argument: verification layer as moat, not generic AI assistant UX. |

## C. Existing roadmap reconciliation table

| Existing item | Current implementation status | Assessment | Recommendation |
|---|---|---|---|
| G1: MCP010 audit | Implemented in `main` and documented in `ROADMAP.md` | Verified as shipped in main | Complete; keep as security invariant |
| G2: reason codes for refusals | Open issue `#3` | Not implemented in main | Keep in stack; it is useful but not the next strategic product priority for Pinch |
| G3: proof artifact | Open issue `#4` | Not implemented | Valuable for enterprise trust; keep but scope to core trust model |
| G4: fix-policy flags | Open issue `#5` | Not implemented | Keep; relevant to approval and bounded action controls |
| G5: GitHub Action preview/gate/apply | Open issue `#8` | Open but not implemented | Keep; useful operationally but not equivalent to Pinch assistant UX |
| G6: rejection corpus benchmark | Roadmap item only | Not implemented | Useful but later; not a core Pinch product milestone |
| G7: VERIFICATION.md | Roadmap item only | Not implemented | Worthy spec work; add after core trust docs |
| G8: package rename/release blocker | Merged to main, not yet public release; docs explicitly say pending-release | Implemented in main, release not complete | Distinguish release state: merged but not hardware-validated and not yet a public release |

Observations:
- The roadmap and repo are internally consistent about the security verifier product, but they do not map to the requested Pinch direction.
- “Closed” issues are not the same as “released”, especially in the PyPI case described in `RELEASING.md`.
- The repository is evidence-rich about safety, governance, and verification. It is weakly evidenced on the assistant/desktop hardware UX required for Pinch.

## D. Prioritized NOW / NEXT / LATER roadmap

### NOW

1. Product definition reset: local-first Pinch shell
- User problem: Users need a continuously available assistant that works locally and is visibly under user control.
- Supporting evidence: There is no Windows shell, no tray app, no local agent runtime, no voice consent flow, and no local model default in repo evidence.
- Current implementation state: Not implemented.
- Proposed scope: define the minimum viable local Pinch shell and task model; broad shell, local task loop, permission gate, plain-language action log, no cloud dependency for core features.
- Non-goals: full web app, chatbot landing page, cloud voice, broad app automation without approval.
- Priority: P0
- Dependencies: product decision on local-model path; local desktop runtime design; simple action permission model.
- Acceptance criteria: On a local machine, the user can start the assistant, see a visible status indicator, approve sensitive actions, and inspect a plain-language action log; no action executes without explicit approval.
- Security/privacy: explicit approval for file/app/system actions; local data defaults; no automatic mic access; no credential storage by default.
- Effort: 3–6 weeks, assuming a small single-engineer + design validation loop.
- Success measure: a user can install, run, and complete a small task without reading technical docs.

2. Safe local task loop and approval gate
- User problem: The assistant can do tasks but must not act without permission.
- Evidence: current repo strongly enforces dry-run and approval-like semantics for code fixes, which maps well to Pinch’s explicit signing requirement.
- Current implementation state: Verified safety pattern exists in `verifier.py` and `agent.py`; not yet adapted to desktop/local tasks.
- Proposed scope: permission model, command preview, file write preview, clipboard read/write gating, reminders and schedule actions with confirmation.
- Non-goals: autonomous destructive operations, remote execution without consent.
- Priority: P0
- Acceptance criteria: a task preview is shown before any sensitive action, and a user can approve or reject before execution.
- Security/privacy: explicit action approval; least-privilege boundaries; hidden access logs; no silent network usage.
- Effort: 2–4 weeks.
- Success measure: zero action executes without explicit confirmation in core task flows.

3. Local data, memory, and settings model
- User problem: Users need personal data to remain local and portable without unexpected cloud sync.
- Evidence: no memory or settings system exists in repo evidence.
- Current implementation state: Not implemented.
- Proposed scope: local SQLite/JSON settings store, explicit user preferences, portable export/import, minimal retrieval model for recent tasks and files.
- Non-goals: cloud sync, cross-device identity system, training on personal content.
- Priority: P1
- Acceptance criteria: user can export/import settings and data; assistant can recall local context without uploading content.
- Security/privacy: local-by-default storage, encryption at rest optional, no automatic remote sync.
- Effort: 2–5 weeks.
- Success measure: settings survive reinstall and can be inspected by the user.

### NEXT

4. Optional local voice and wake activation
- User problem: Users want a convenient hands-free interaction mode without cloud audio dependence.
- Evidence: repo has no voice architecture or consent flow; this must be added from scratch.
- Scope: optional local microphone permission gate, wake-word or push-to-talk, spoken responses when user opts in, clear indicator when mic is active.
- Non-goals: always-on background capture, remote transcription, cloud audio-only design.
- Priority: P1
- Acceptance criteria: voice activation is opt-in, visible, and interruptible; the user can disable it at any time.
- Privacy: microphone indication, consent, local transcript retention controls, explicit off state.
- Effort: 3–6 weeks.
- Success measure: voice workflow completes a defined task without hidden recording.

5. File and app integration boundaries
- User problem: Users need assistant help with files and apps but want safe boundaries.
- Evidence: repo has a file-target CLI and verification loop, which is a strong base for bounded file access; no app integration exists.
- Scope: file read/write allowlists, app launch boundaries, clipboard read/write approvals, browser/task activation only when explicitly approved.
- Non-goals: unrestricted arbitrary shell execution or full desktop takeover.
- Priority: P1
- Acceptance criteria: user can see which files/apps are being touched and approve scope.
- Privacy/security: strict manifest of allowed actions; no credential leakage to logs.
- Effort: 3–5 weeks.
- Success measure: every integration action is explainable and user-approved.

6. Local-model runtime and hardware honesty
- User problem: Users want Pinch to work without cloud dependency, but realistic inference constraints must be stated honestly.
- Evidence: repo currently prefers a mock or Nebius provider; no local model runtime is present.
- Scope: define local model tiers, default behavior, constrained tasks, and fallback messages when hardware is insufficient.
- Non-goals: claiming real Windows/GPU validation without hardware proof.
- Priority: P1
- Acceptance criteria: a local-mode path is documented with known performance constraints and a failure message when CPU/GPU is insufficient.
- Security/privacy: all local inference stays on-device; clear disclosure when cloud is used.
- Effort: 2–4 weeks.
- Success measure: local-mode fallback works for constrained tasks and does not silently become cloud-only.

### LATER

7. Windows desktop companion and startup resilience
- User problem: “Always available on Windows” requires a visible desktop presence, a resumable process, and recoverable state.
- Evidence: repo has no desktop runtime or startup logic.
- Scope: Windows service/session startup, tray or widget, state restoration, low-friction launch, clear status in background.
- Non-goals: full app store packaging before task loop is proven.
- Priority: P2
- Acceptance criteria: app starts on login or user request; if it crashes, it can recover and report state.
- Security/privacy: user-visible running state, no silent networking, explicit local state permissions.
- Effort: 4–8 weeks.
- Success measure: a user can start, pause, and recover the assistant without technical setup.

8. Cross-device portability and export/import
- User problem: Users need to preserve their assistant’s preferences and data without being locked to one machine.
- Scope: configuration bundles, export/import, restore points, data portability plan.
- Non-goals: cloud sync or identity federation.
- Priority: P2
- Acceptance criteria: data can be exported and re-imported safely.
- Effort: 2–4 weeks.

9. Release and packaging maturity
- User problem: quality and trust need to coexist with shipping.
- Evidence: repo has packaging, CI, and release docs; they are stronger than a typical prototype but still not a polished product release.
- Scope: packaging, update/install flow, uninstall path, first-run onboarding, health checks.
- Non-goals: broad feature additions before onboarding is smooth.
- Priority: P2
- Acceptance criteria: installation, update, and uninstall are documented and tested.
- Effort: 3–6 weeks.

### DEFER / DO NOT BUILD

10. General-purpose chatbot web app frontend
- Reason: not aligned with Pinch product direction; would turn the product into a generic website rather than a personal local assistant.
- Non-goals: competitor imitation, cloud-only chat UI, broad social features.

11. Cloud audio by default / remote transcription
- Reason: explicitly against the requested product direction; would compromise privacy and local-first posture.

12. Heavy app automation without user trust boundaries
- Reason: unsafe and misaligned; only safe, bounded actions should be allowed.

13. Feature list expansion without solved trust loop
- Reason: the repo’s strongest pattern is verification, not broad surface area. Growth should follow trust and usability, not feature count.

## E. Top five risks and release/validation gates

1. Local-first promise is mis-sold as “works everywhere”
- Risk: if the product claims ambient availability while requiring cloud or specialized hardware, trust fails.
- Gate: every feature doc must state whether it runs fully local, optionally local, or cloud-assisted.

2. Silent destructive actions
- Risk: file, app, or command actions can execute without user oversight.
- Gate: no action executes without an explicit summary and approval; logs show what was requested and what was performed.

3. Mic and audio misuse
- Risk: unconsented audio capture or harsh wake-word behavior.
- Gate: mic permission is explicit, visible, and reversible; all audio processing is opt-in; no always-on background record.

4. Trust model is unsupported by evidence
- Risk: strong UI claims without actual measured performance or reliable local model behavior.
- Gate: every high-level claim must have one user-observable test or documented limitation.

5. Feature growth outruns architecture
- Risk: robust local-first product is diluted by a broad feature list.
- Gate: no new feature ships without a user problem, evidence, scope, non-goals, and security review.

## F. The first three actionable GitHub issue drafts

1. Issue: “feat(desktop): local-first assistant shell with visible status and approval gate”
- Problem: no local assistant process exists; users cannot see the agent state or approve actions.
- Acceptance criteria: install and run local process; status indicator shown; sensitive actions require preview and approval; logs are visible.
- Files: `src/`, `docs/`, `README.md`

2. Issue: “feat(security): explicit permission model for file, clipboard, and app actions”
- Problem: the product needs safe trust boundaries, not open-ended automation.
- Acceptance criteria: read/write allowlists, app boundary manifest, clipboard approval flow, logs for permission decisions.

3. Issue: “feat(voice): opt-in local microphone workflow with consent and interruption handling”
- Problem: users need optional voice control without cloud audio dependence.
- Acceptance criteria: user-visible mic status, clear on/off control, interruption support, no background listening.

## G. Unknowns and questions requiring maintainer decisions

- Is the current repository being intentionally repurposed toward Pinch, or should a new repo be created for a personal assistant product?
- Which tasks are truly core for day-1 value: reminders, clipboard, file helper, app launcher, or personal knowledge recall?
- Is the default model path local inference, cloud inference, or hybrid depending on user choice?
- What is the minimum supported Windows environment (Windows 10/11, ARM/x64, virtualization assumptions)?
- Are local task memory and reminders required in v1, or is v1 limited to visible commands and user-approved actions?
- How much app/file automation is acceptable in v1 versus later?
- What is the privacy policy for local logs, microphone activity, and settings export/import?
- Is the repo’s strongest technical moat (verification logic) meant to remain a distinct product or be integrated into the Pinch local agent?

## H. Checks run, exact results and checks not performed

Because this session has no terminal or shell execution capability in the available tools, I could not run the repository’s Python checks locally. I was limited to repository inspection via GitHub API and file reads. I therefore report repository-informed evidence instead of local test execution.

Repository evidence reviewed:
- `README.md`
- `ROADMAP.md`
- `.github/roadmap.json`
- `pyproject.toml`
- `.github/workflows/ci.yml`
- `src/vexar_autofix/cli.py`
- `src/vexar_autofix/agent.py`
- `src/vexar_autofix/verifier.py`
- `tests/test_verifier.py`
- `SECURITY.md`
- `PRODUCT.md`
- `RELEASING.md`

What I attempted to validate:
- GitHub Actions log lookup via workflow path `ci` failed: `Failed to fetch runs for the given workflow path ci`.
- This means there is no reliable action-run evidence available from this session, so I am not claiming hardware or Windows validation.

Checks not performed because unavailable:
- `python -m pip install -e ".[dev]"`
- `ruff check .`
- `mypy src --strict`
- `pytest`
- `python eval/run_eval.py --provider mock`
- real Windows, microphone, or GPU validation

This is a deliberate limitation. The repo’s own docs and CI configuration describe those checks as intended, but they are not verified in this session.

## Roadmap note

The evidence is clear that the repo is a safety-focused autonomous patch-verification tool, not a desktop assistant product. The product direction described for Pinch is valid but must be built as a new product architecture, not treated as the current repo’s implementation. The roadmap above translates that direction into a realistic product plan while preserving the repo’s strongest strengths: explicit approval, local-by-default design, honest limitations, and maintainable architecture.

## Appendix: repo-grounded product judgment

If this must be stated in one sentence: the repo is a strong prototype for a trust and verification layer, and it is a weak fit for the “Pinch” personal assistant product as described; the first product milestone should therefore be a minimal local desktop shell with explicit action approval and local data boundaries, not a chat website or a broad AI feature list.

---

This file is a proposal, not a mutation of the existing roadmap.

