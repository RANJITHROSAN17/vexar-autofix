# Security Policy

## Reporting a Vulnerability or Verifier Bypass

`vexar-autofix` is a security remediation and patch-verification agent. Two classes of security reports matter here:

1. **Vulnerabilities in `vexar-autofix` itself** (arbitrary code execution during dry-run/verification, path traversal outside target root, or secret exposure).
2. **Verifier bypasses** — a patch that clears an `AUTOFIXABLE` rule and passes `audit_patch()` while leaving the underlying vulnerability exploitable (for example, the `timeout=float('inf')` bypass closed in `G1`).

Please report vulnerabilities privately via **[GitHub Security Advisories](https://github.com/RANJITHROSAN17/vexar-autofix/security/advisories/new)** rather than opening a public issue if an active exploit is involved. Non-sensitive bad-patch test cases for the rejection corpus (`G6`) can use the **Verifier Bypass / Rejection Corpus Case** issue template.

We acknowledge reports within **72 hours**.
