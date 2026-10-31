# Contributing to `tsis-agent-evaluation`

Thank you for improving this repository. It is a graded course deliverable
(FMI Master IS, TSIS 2026–2027) with a research-integrity layer on top of
normal open-source hygiene.

## The gates (all must be green)

Every push to `main` and every PR runs, via
[quality-zero-platform](https://github.com/Prekzursil/quality-zero-platform)
and native CI:

| Gate | What it enforces | Where |
|---|---|---|
| `tsis-ci` | tests + **100% line AND branch coverage** on the measured scope, on ubuntu + windows, py3.10 + 3.12, compile-check of every tracked script | `.github/workflows/ci.yml` |
| `quality` | ruff lint+format (corpus/ + tests/), basedpyright (standard), coverage re-asserted, opengrep SAST, gitleaks, osv-scanner — **zero tolerance** (`deps-severity-floor: any`) | `.github/workflows/quality.yml` |
| `CodeQL` | code scanning, on push/PR/weekly | `.github/workflows/codeql.yml` |

Run locally before pushing:

```bash
python -m pip install "scipy>=1.11" "pytest>=8" "pytest-cov>=5" ruff
python -m pytest --cov --cov-branch   # must end at 100.00% and 0 failures
python -m ruff check .
python -m ruff format --check .
```

## Coverage scope, stated honestly

Measured at **100% line+branch** (enforced, not aspirational):

- `corpus/cross_taxonomy_join.py` — the cross-taxonomy statistics engine
  (pure statistics + a file-driven `main()`; exercised end-to-end on three
  synthetic fixtures: rich, degenerate-both-flagged, degenerate-all-clean)

Deliberately **outside** the measured scope — lane drivers coupled to the
uncommitted tau2-bench harness clone, private result data, and LLM API lanes;
their published `RESULTS.md` tables are the delivered evidence:

- `corpus/build_corpus.py`, `tau2-bench/*`, `trail/*`, `mastscope/*`, `_audit/*`

The same freeze rationale applies to ruff/basedpyright scoping in
`pyproject.toml`: `corpus/` and `tests/` are fully gated; the lane trees are
excluded because they import the harness via runtime `sys.path` insertion and
are reproduced by re-running lanes, not by unit tests.

## Research-integrity rules

- **Never edit a measured number.** Numbers in `RESULTS.md`,
  `CROSS_TAXONOMY.md`, `DECISION.md`, `INTEGRITY.md` come from lane runs; a
  PR may only change them by re-running the producing script and showing the
  command + output.
- **Deny-by-default `.gitignore`.** The whitelist admits curated deliverables
  only. Never force-add lane state, API keys, result payloads, or the
  `repo/` upstream clone. `mastscope/annotation/try_env_keys.py` stays
  untracked on purpose (it probes live env-provided keys).
- **Privacy.** Aggregate statistics only; no session content, no content
  hashes, nothing with n<5 without disclosure.

## Commits & PRs

- Branch from `main`; open a PR; both `quality` and `CodeQL` must be green.
- Conventional-ish subjects (`corpus: …`, `tau2: …`, `trail: …`, `ci: …`).
- Fill the PR template — every claim needs a command + its output.

## Reporting bugs

See `SECURITY.md` for vulnerabilities, `.github/ISSUE_TEMPLATE/` for bugs.

## AI-tooling disclosure

This evaluation was produced by an AI workflow (GLM-5.3 + grok-4.7 + NVIDIA
NIM lanes); usage and validation are documented in `DECISION.md` and the
per-lane reports.
