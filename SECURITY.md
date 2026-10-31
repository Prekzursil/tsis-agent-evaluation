# Security Policy

## Supported versions

Only the latest `main` is supported.

## Reporting a vulnerability

Please report vulnerabilities privately: use
[GitHub security advisories](https://github.com/Prekzursil/tsis-agent-evaluation/security/advisories/new)
("Report a vulnerability"). Do not open a public issue for security problems.

You should receive a response within 72 hours. Please do not disclose the
issue publicly before a fix is released.

## Scope

This repository is a research-evaluation deliverable: statistics code over
label corpora, evaluation-lane drivers for the tau2-bench harness, and the
reports they produced. It runs no production service and stores no user data.

**Privacy note.** The annotated corpora derive from one team member's own
agent-session journals, processed through third-party LLM APIs as a disclosed
processing step (see `DECISION.md` → Data provenance). Only aggregate
statistics are published; no session content or content hashes ship in this
repository.

## Automated checks

- **CodeQL** runs on every push to `main`, every PR, and weekly (`.github/workflows/codeql.yml`).
- **gitleaks / opengrep / osv-scanner** run on every push and PR via the
  [quality-zero-platform](https://github.com/Prekzursil/quality-zero-platform) lean gate.
- **Dependabot** tracks GitHub Actions and pip dependencies weekly.
