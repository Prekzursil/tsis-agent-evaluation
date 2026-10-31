## What & why

<!-- One-paragraph summary: what changes and the reason. -->

## Verification

<!-- How you proved it. Every claim needs a command + result. -->

- [ ] `python -m pytest --cov --cov-branch` — 100% line+branch on the measured scope, all green
- [ ] `ruff check .` and `ruff format --check .` — clean (corpus/ + tests/)
- [ ] `quality` workflow green on this PR
- [ ] `CodeQL` workflow green on this PR

## Scope discipline

- [ ] No changes to measured numbers in RESULTS.md / CROSS_TAXONOMY.md / DECISION.md
      unless the underlying data is re-run and the diff is justified
- [ ] No lane-internal state, keys, or result payloads committed (whitelist
      `.gitignore` discipline: deny-by-default)
- [ ] Docs updated alongside any script change
