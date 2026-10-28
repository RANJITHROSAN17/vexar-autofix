# Product position

Two repositories, one promise.

| | [Vexar-MCP](https://github.com/RANJITHROSAN17/Vexar-MCP) | [vexar-autofix](https://github.com/RANJITHROSAN17/vexar-autofix) |
|---|---|---|
| Role | **Parent.** The engine: 15 rules (MCP001–MCP015), TypeScript loader, schema and token-budget checks, SARIF + HTML reporters, baselines, policy presets, GitHub Action | **Child.** The proof layer: remediates 4 of those rules and refuses to report a fix the scanner cannot confirm |
| Interface | `vexar-mcp scan` | `vexar-autofix fix` (pins the parent at a commit sha) |
| Status | v0.2.1, MIT | Unreleased prototype, MIT |

The parent/child structure is correct and should not change. What follows is the argument for **which half carries the promise**, because getting that wrong changes how both are sold.

---

## The thesis

> **The scanner is the commodity on-ramp. The proof loop is the moat.**

Most of the analysis written about these two repos ranks the scanner layer as the stronger long-term position: bigger category, enterprise-friendly, easier to monetise, harder to copy. The first three are true. The last one is not, and it is the one that decides where the defensible value sits.

### Rules are not a moat

Fifteen rules over a Python AST is a weekend for a competent engineer. Everything else in Vexar-MCP — SARIF output, baselines, policy presets, CI gates — has been shipped by Semgrep, Snyk, CodeQL and Bandit for a decade. In the MCP-specific segment there are already well-funded entrants: Invariant's MCP-Scan, mcp-shield, Semgrep's MCP rulesets, plus the larger vendors' agent-security offerings.

A single-maintainer scanner competes on rule coverage against teams who ship rules weekly. That is a race that cannot be won by adding rules; it can only be won by making a claim they cannot make.

### The claim they cannot make

The scanner accepted **four patches. Three of them were broken.**

That number is not marketing. It came out of the eval in this repository: patch MCP005 flipped `shell=False` while still passing one string, and every command with an argument then raised `FileNotFoundError`; MCP006 validated a URL's *scheme*, which the link-local metadata endpoint passes; MCP007 confined a path by string prefix, which `/app-evil` walks straight through. The scanner was satisfied every time, because the scanner matches patterns.

So the finding that justifies this entire product line is empirical, and it is *against the scanner*:

> **A pattern scanner cannot deliver safe code. It can only deliver "pattern gone."**

Nobody else in this space can make that claim with a receipt, because making the receipt requires the thing they do not have: a verifier that refuses to trust the model's own output. That is the moat. It is not the rules — it is the **discipline of refusal**, and the audit trail it leaves.

Vexar-MCP's own documentation is the argument for it. It reports severity, not safety. `vexar-autofix` is the only member of the suite that answers the question a security reviewer actually asks: *"is it still the same program, and does it still work?"*

---

## The three statements

**One line**
> Vexar-MCP finds the finding. vexar-autofix proves the fix.

**Mission**
> Make every automated fix carry evidence, so a security team can accept it without re-reading it.

**Investor paragraph**
> MCP servers are how agents touch real systems, and the scanners that audit them now ship as rules — a commodity. Detection is crowded and getting cheaper. The unsolved problem is the step after detection: an LLM can produce a patch that clears a rule and breaks the tool, and most tooling will report that as a fix. We built the verifier first and the agent second. Our remediation layer accepts a patch only when a deterministic re-scan shows the targeted rule's instances dropped, no new finding appeared, and the target's tests still pass — and it refuses rules where no mechanical remedy exists rather than guessing at intent. In our own eval the scanner accepted four patches and three were broken; the verifier caught all three. The scanner is the on-ramp. Proof of repair is the product.

---

## What the moat actually is, concretely

Not "we have many rules". These four, in order of defensibility:

1. **A verification protocol others could adopt.** A published spec for "what makes a patch verifiably safe" — count must drop per rule and per tool, no new findings, tests green, and a semantic audit of added lines. If outside tools implement it, we define the category. If they don't, we are the only compliant implementation.
2. **An adversarial patch corpus.** Every patch the verifier rejects, published with the reason. This is a benchmark nobody else is building, it compounds with every run, and it is the evidence base for the claim above.
3. **The refusal discipline.** Refusing rules with no mechanical remedy, and bucketing every finding as fixed / unfixed / refused / skipped, is a product decision competitors optimising for "fix rate" cannot copy without tanking their own numbers.
4. **The audit trail.** The deliverable for an enterprise is not the patch. It is the record proving the patch was checked.

Rule count is not on this list on purpose.

---

## Roadmap

**0–3 months — make the prototype undeniable**

- Keep Vexar-MCP free, CI-first, MIT. It is the funnel, not the product.
- Ship the verifier's rejection corpus as a public benchmark: patch, rule, reason, verdict.
- Publish `VERIFICATION.md`: the three gates and the patch-audit rules, written so another team could reimplement them.
- Close the honesty gaps flagged in this repo: real token counts in `docs/data/runs.json`, and `scripts/capture_demo.py` emitting the same schema the demo page reads.

**3–12 months — turn the loop into a product**

- `vexar-autofix --policy strict-prod` inside customer CI: dry-run by default, human approval for deletion-class patches, a signed report per run.
- Price per verified remediation, not per seat. The output is an artifact a reviewer signs off on, which is what a security budget actually buys.
- Grow rule coverage only where a canonical remedy exists. Coverage without a remedy produces refusals, and refusals are not the product.

**Explicitly not doing**

- Chasing Semgrep on rule count.
- Letting autofix run unattended on high-risk rules.
- Reporting a "fix rate" that hides the refusals.

---

## Objections, answered

| Objection | Answer |
|---|---|
| "Snyk / Semgrep / CodeQL will add MCP rules and eat the scanner." | They will, and that is the argument: the scanner is the commodity layer. The verifier is not a rules file; it is a re-scan plus a semantic audit plus an escalation policy, and it only works if the scanner sits on both sides. |
| "Why not just use Cursor or Copilot to fix the finding?" | Because it reports success. Show the `FileNotFoundError`. The whole point is that the model's confidence is not evidence. |
| "Autofix is dangerous." | Agreed. That is why it is dry-run by default, one finding per attempt, fail-closed on any rejection, anchor-only edits, and it refuses 11 of its 15 parent rules outright. |
| "Only 4 of 15 rules are fixable — that's a small product." | It is a deliberate scope. A fixer that guesses at intent fails in exactly the way this project exists to prevent. |
| "What stops someone cloning this?" | Nothing in the code, and that is fine — it is MIT. What is hard to clone is the corpus of rejections and the discipline of publishing them. |
| "Who pays?" | Whoever currently spends reviewer hours re-reading AI diffs. The purchase is the evidence, not the patch. |

---

## What is not proven yet

Stated plainly, because a positioning document that only lists strengths is the kind of document this project exists to argue against:

- **No users.** 1 star, 2 forks, 8 open issues, two days old. Demand is a hypothesis, not a measurement.
- **No willingness-to-pay evidence.** The pricing claim above is a model of how security budgets work, not a validated price.
- **The moat is a plan, not a fact.** The corpus, the protocol and the benchmark do not exist yet. Until they do, this is a good open-source tool with a sharp idea, which is not the same thing as a business.
- **The evidence is one eval, three fixtures, one model family.** It demonstrates the failure mode is real; it does not quantify how often it happens in the wild.

The next honest milestone is not a feature. It is **one external user who ran it on their own repository and reported what broke.**

---

<sub>Written 2026-10-28, alongside commit `30313a1` of vexar-autofix and `dd4c07b` of Vexar-MCP. Figures verified against both repositories, not estimated.</sub>
