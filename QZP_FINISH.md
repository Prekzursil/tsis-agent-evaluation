# QZP Onboarding — Finish Report (`Prekzursil/tsis-agent-evaluation`)

Branch `main` @ `7a73b55` (merge commit of PR #1). All facts below were read
from this tree or via the GitHub API / `gh` CLI on 2026-10-31.

## 1. What was onboarded

Five commits: the onboarding, three gate-repair rounds (all observed on real
push/PR runs, fixed at the source), and a README badge PR:

| Commit | What |
|---|---|
| `d90c206` | The onboarding itself: `tsis-ci` + `quality` + `CodeQL` workflows, dependabot, community files, deny-by-default curated public surface, 29-test suite for `cross_taxonomy_join.py` + its 3 crash-bug fixes |
| `f9e54b4` | style: ruff-format the typed scipy cast block introduced by `d90c206` |
| `b1047f3` | Gate repairs: QZP pin bump `48e1e5c` → `0c4b8c63`, `requirements.txt` manifest, py3.10 f-string syntax fixes in `_audit/`, basedpyright `executionEnvironments` type-path config |
| `3c3543b` | Lane content-hash calls marked `usedforsecurity=False` (platform SAST weak-hash findings) |
| `f46256a` | docs: CI badge line in README — merged via **PR #1** as `7a73b55` at 2026-10-31T19:56:23Z |

### Workflows (`.github/workflows/`)

- **`ci.yml` (`tsis-ci`)** — native CI. Matrix `ubuntu-latest` +
  `windows-latest` × Python `3.10` + `3.12` (`fail-fast: false`). Installs
  `scipy>=1.11`, `pytest>=8`, `pytest-cov>=5`. Compile-checks **every
  tracked** `.py` (via `git ls-files`, one file at a time so a failure names
  itself), then `pytest --cov --cov-branch` with the 100% gate enforced by
  `pyproject.toml` (`fail_under = 100`). Coverage XML uploaded from the
  ubuntu/py3.12 leg. Actions pinned by SHA: `checkout@11d5960a` (v4),
  `setup-python@a26af69` (v5), `upload-artifact@ea165f8d` (v4).
- **`quality.yml` (`quality`)** — thin caller of
  `Prekzursil/quality-zero-platform/.github/workflows/reusable-quality.yml@0c4b8c63d3ca41fffdf70ecd36cc96f46eb5c6e1`
  with `deps-severity-floor: any` (zero tolerance). push/PR to `main` +
  `merge_group`; PR runs cancelled on supersede, default-branch runs always
  finish.
- **`codeql.yml` (`CodeQL`)** — thin caller of
  `Prekzursil/quality-zero-platform/.github/workflows/reusable-codeql.yml@0c4b8c63d3ca41fffdf70ecd36cc96f46eb5c6e1`
  (same pin). Triggers: push/PR to `main`/`master`, `merge_group`, weekly
  (`23 3 * * 1`), manual.

### QZP pins

Initially both reusable-workflow pins were
`@48e1e5c86e053b39d73277a32936213ffbb75a89` (`d90c206`). CodeQL then failed
with `KeyError: Repo Prekzursil/tsis-agent-evaluation not found in inventory`
— `reusable-codeql.yml` checks QZP out at its own pinned commit (`48e1e5c8`,
Oct 29), whose inventory predates this repo's enrollment (QZP PR #359, merged
as `0c4b8c63`). Commit `b1047f3` bumped **both** pins to the enrollment merge
commit `0c4b8c63d3ca41fffdf70ecd36cc96f46eb5c6e1` — the documented adoption
path. Gate changes happen in quality-zero-platform, never here.

### Curated public surface (the repo-specific part of the onboarding)

This repo publishes a **curated subset** of a working research tree, governed
by a deny-by-default `.gitignore` (`*` first, then explicit whitelists):
160 tracked files.

- **`poc/**` fix** — the whitelist had `!tau2-bench/poc/` alone, but `!dir/`
  does not unignore children under a blanket `*`, so the custom
  **`ecommerce3` domain was never committed**. Fixed by adding
  `!tau2-bench/poc/**` (with `__pycache__` re-denied); `git ls-files
  tau2-bench/poc/` now shows both `ecommerce2/` and `ecommerce3/` (init,
  data model, environment, tools, `data/db.json`, tasks…).
- `_audit/**` audit-receipt scripts (incl. `recheck_new_root.py` which
  re-proves the INTEGRITY.md checks at the final path), `mastscope/fullrun`
  scripts, and the lane scripts referenced by committed reports were
  whitelisted in the same pass.
- **`mastscope/annotation/try_env_keys.py` deliberately excluded** — it
  probes live env-provided API keys and stays untracked on purpose
  (`git ls-files | grep try_env_keys` → 0 matches; the blanket `*` rule
  keeps it out and CONTRIBUTING.md's research-integrity rules forbid
  force-adding it).
- Never tracked: lane state, result payloads (190 MB label data), the
  `repo/` upstream clone, `work/`, provider-claims, `.venv`.

### Community files

`LICENSE` (MIT), `SECURITY.md` (with a privacy note), `CONTRIBUTING.md`,
`INTEGRITY.md` (research-integrity audit of every produced artifact —
repo-specific), `.github/CODEOWNERS`, `.github/PULL_REQUEST_TEMPLATE.md`,
`.github/ISSUE_TEMPLATE/{bug_report,feature_request}.yml`,
`.github/dependabot.yml` (github-actions + pip, weekly, grouped patch/minor,
semver-major ignored — byte-identical config to the `tss` repo),
`codecov.yml`, `.gitleaks.toml`, root `pyproject.toml`, `requirements.txt`.

## 2. The gates and their config

| Gate | Workflow | Config highlights |
|---|---|---|
| Tests + coverage | `tsis-ci` | 2 OS × 2 Python; compile-check every tracked script; `--cov --cov-branch`; `[tool.coverage.report] fail_under = 100`, `branch = true`, `source = ["corpus"]` with `omit = ["corpus/build_corpus.py", "corpus/_probe.py"]` |
| Lint + format | `quality` (ruff) | `line-length = 100`, `target py310`, rules `E,F,W,I,UP,B`; `extend-exclude` of the frozen lane trees (`tau2-bench`, `trail`, `mastscope`, `_audit`, `repo`, `work`); per-file waivers on `corpus/build_corpus.py` (`UP031` et al. — rewriting `%d` on floats changes truncation semantics and could alter the evidence manifest; bug rules `F…` stay active) |
| Types | `quality` (basedpyright) | `typeCheckingMode = "standard"`, py3.10; same lane-tree excludes + `corpus/build_corpus.py`; `executionEnvironments = [{ root = "tests", extraPaths = ["corpus"] }]` so the suite's runtime `sys.path` insertion resolves to the **real** module — adds checking, relaxes nothing. Bar is 0 errors AND 0 warnings, which is why `requirements.txt` exists: the multi-top-level tree (corpus/, tests/, mastscope/…) cannot be built by `pip install .`, so the gate installs the manifest (`scipy>=1.11`, `pytest>=8`, `pytest-cov>=5` — exactly what `tsis-ci` installs) before the type lane |
| SAST | `quality` (opengrep) + `CodeQL` | platform default ruleset at zero tolerance — this is what forced `3c3543b`: `trail/fullrun_corpus.py` sha1/md5 16-hex content-IDs flagged by `python-weak-hash-md5-sha1`; fixed with the rule's own prescribed remediation `usedforsecurity=False` (digests byte-identical) |
| Secrets | `quality` (gitleaks) | default rules; allowlist kept empty; full tracked history clean (pinned gitleaks 8.30.1) |
| Dependencies | `quality` (osv-scanner) | `deps-severity-floor: any`; pinned osv-scanner v2.3.8 reports "No issues found" on the tracked surface |
| Coverage (Codecov) | `codecov.yml` | `range: "100...100"`, project + patch 100%, threshold 0%, `require_ci_to_pass: true`; `ignore` mirrors the coverage.py omissions plus the lane trees |

## 3. Coverage scope, stated honestly

The measured 100% line+branch scope is deliberately narrow and the boundary
is documented in two synced places:

- **`CONTRIBUTING.md` → "Coverage scope, stated honestly"** — the canonical
  human-readable statement.
- **`pyproject.toml` → `[tool.coverage.run]`** — the enforced `source`/`omit`
  split with rationale.

Measured: **`corpus/cross_taxonomy_join.py` only** — the cross-taxonomy
statistics engine (pure statistics + file-driven `main()`). Deliberately
outside: `corpus/build_corpus.py` (filesystem-walking lane driver whose
output manifest is the evidence) and the lane trees (`tau2-bench/`,
`trail/`, `mastscope/`, `_audit/`) coupled to the uncommitted harness clone,
private result data, and LLM API lanes — their published `RESULTS.md` tables
are the delivered evidence, reproduced by re-running lanes, not unit tests.

## 4. tsis-only code fixes that came with onboarding

Scope note: this report covers **`tsis-agent-evaluation`** only. The tss
repo's fixes (qa_deck path bug, gen_cfg lint, basedpyright cleanups) are a
separate report and are intentionally **not** listed here. What landed here:

1. **`tests/test_cross_taxonomy_join.py` — 29 tests at 100% line+branch on
   `corpus/cross_taxonomy_join.py`** (current run: 255 statements, 110
   branches, 0 missed). Three end-to-end fixtures drive `main()` through
   every branch — *rich* (6 join sessions, every normalization variant,
   agreement cell, miss category, decomposition counter),
   *degenerate-both-flagged* (pe == 1 kappa path, zero-cell chi2 path),
   *degenerate-all-clean* (no flags at all) — plus hand-computed units for
   the pure functions (`norm_trail`, `shannon`, `js_divergence`, `bh_fdr`).
2. **Three crash bugs in `corpus/cross_taxonomy_join.py`, found by those
   tests and fixed in `d90c206`:**
   - **`ZeroDivisionError` on an empty join** — `po = (both + neither) / N`
     and every `pct_*`/rate expression divided by `N` unconditionally; now
     guarded (`... / N if N else 0.0` — current `corpus/cross_taxonomy_join.py:267`,
     `:282`–`:287`).
   - **`log2(0)` when no classes are observed** — normalized entropy
     divided by `math.log2(k)` with `k = len(observed_classes)`; on an
     all-clean corpus `k = 0` and `math.log2(0)` raises. Now
     `logk = math.log2(k) if k else 0.0` with `H_norm = … / logk if logk else 0.0`
     (`:361`, `:369`–`:370`; mirrored for classes at `:382`, `:389`–`:390`).
   - **scipy `ValueError` on zero-margin chi²** — `stats.chi2_contingency`
     rejects tables with a zero row/column sum, not just all-zero tables.
     Both call sites guarded: the 2×2 agreement table
     (`if N and min(min(r) for r in tab) > 0` else NaN, `:261`) and the 3×3
     category×root table (`n_cr > 0` and all row/column sums nonzero,
     `:416`), each falling back to `float("nan")`.
   - Alongside: typed scipy casts (`cast(float, …)`), `zip(..., strict=False)`
     pinning, ruff/format-clean throughout.
3. **`corpus/build_corpus.py`** — dead `nonlocal_dummy` removed; style rules
   per-file-waived (`UP031`: `%d`-on-float truncation semantics could alter
   the manifest; behavior rules stay active).
4. **`_audit/audit_20261030/{mast,trail}_audit.py`** — backslash inside an
   f-string expression (SyntaxError under py3.10; PEP 701 lifted it only in
   3.12) hoisted into a variable (`b1047f3`) so the py3.10 CI legs compile.

## 5. Current status

Verified 2026-10-31 via `gh api`/`gh run list` and a local suite run.

| Item | State | Evidence |
|---|---|---|
| `main` @ `7a73b55` — `tsis-ci` | ✅ green | check-runs on the merge commit: `verify (ubuntu-latest, py3.10/3.12)` + `verify (windows-latest, py3.10/3.12)` all `success` |
| `main` @ `7a73b55` — `quality` | ✅ green | `quality / quality -> success` |
| `main` @ `7a73b55` — `CodeQL` | ✅ green | `codeql / CodeQL -> success` (analyze + resolve profile) |
| PR #1 | ✅ MERGED | README CI badge, merged 2026-10-31T19:56:23Z as `7a73b55` |
| Ruleset | ✅ active | `quality-zero-platform / tsis-agent-evaluation` (id 26286098), branch ruleset on `refs/heads/main`: PRs required (0 approvals, extra approval required for unattributed changes), 6 required status checks (4× `verify` matrix + `quality / quality` + `codeql / CodeQL`, strict policy), no force-push, no deletion, code-scanning rule |
| CodeQL alerts | ⚠️ 20 open | 19 × `py/unused-import` (severity **note**) across lane scripts (`trail/`, `mastscope/fullrun/`, `tau2-bench/`, `_audit/`); plus 1 × **high** #284 `py/weak-sensitive-data-hashing` at `trail/fullrun_corpus.py:42` — the md5 content-ID line already carries `usedforsecurity=False` (cleared the *platform* SAST rule), but CodeQL's separate sensitive-data-hashing query keys on data flow and still fires; needs an owner decision (documented exemption or digest swap) |
| Open PRs | none | no dependabot PRs open yet (weekly schedule) |
| Local suite (this checkout, `.venv` py3.14.6) | ✅ | `pytest --cov --cov-branch` → **29 passed, 100.00% line+branch** on `corpus/cross_taxonomy_join.py` (255 stmts / 110 branches, 0 missed) |

Note on the alerts: all 20 opened 19:38–19:44 UTC on 2026-10-31 — the first
CodeQL runs over the newly public curated surface (160 tracked files of
research scripts). PR #1 merged afterwards, so existing alerts on unchanged
paths did not block; but the code-scanning ruleset rule will gate any future
PR that touches a flagged file, so the note-level `unused-import` cluster and
alert #284 (high) are the open triage queue.
