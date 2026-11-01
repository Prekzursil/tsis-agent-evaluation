# AGENTS.md

`Prekzursil/tsis-agent-evaluation` is governed by
[quality-zero-platform](https://github.com/Prekzursil/quality-zero-platform)
(QZP). These rules bind every contributor, human or automated:

- **Verify before claiming completion:** run `bash scripts/verify`. It runs
  the locally runnable lanes of the QZP lean gate with the same configs CI
  uses. A finding of any severity is a failure.
- **Never weaken a gate to pass it:** no lowered thresholds, no new
  suppressions or allowlist entries, no skipped or deleted tests. Fix the
  code, or fix the gate in QZP (see [CONTRIBUTING.md](CONTRIBUTING.md)).
- **Tests ship with the change:** 100 % line **and** branch coverage on the
  declared scope (`pyproject.toml` `[tool.coverage]`).
- **Never push to `main`:** every change lands through a pull request whose
  required checks are green.
- **Security findings go private:** follow [SECURITY.md](SECURITY.md).

## Repo-specific scope notes

- The lane trees (`tau2-bench/`, `trail/`, `mastscope/`, `_audit/`) and
  `corpus/build_corpus.py` are frozen evidence generators — see the
  research-integrity rules in [CONTRIBUTING.md](CONTRIBUTING.md) before
  touching them; measured numbers change only by re-running the producing
  lane.
- The deny-by-default `.gitignore` is the curated public surface: never
  force-add around it.
