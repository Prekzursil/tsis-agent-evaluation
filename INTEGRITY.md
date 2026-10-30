# INTEGRITY — audit of all produced artifacts under `tss/tsis-deepdive/`

Auditor: results-integrity subagent, 2026-10-18. Every check below was executed this
session with system Python 3.14.6 (scripts preserved in `tss/tsis-deepdive/_audit/`,
raw verifier outputs in `_audit/out_*.txt`). **Nothing was quarantined and no line was
dropped: zero corrupt or truncated files were found anywhere.** Every failure below is
staleness or incompleteness of derived/checkpoint artifacts, which must be fixed by
re-running the lane's own summarize/aggregate/resume steps — never by editing numbers.

---

## 1. `corpus/` — VERDICT: PASS (all checks)

| check | command run | result |
|---|---|---|
| manifest.jsonl parses | `_audit/audit_corpus.py` — full-file line-by-line `json.loads` | 124,327/124,327 lines parse, 0 failures; file ends with newline (73,315,396 bytes) |
| total = 124,327 | same | PASS (ok 122,733 + missing 1,594 = 124,327; matches CORPUS.md §1 and stats.json exactly) |
| sha256 on every record | same | PASS — `sha256` present on 124,327/124,327; full 18-key schema on every record |
| unique-hash vs canonical_set.json & CORPUS.md | `_audit/audit_corpus2.py` | PASS with a documented nuance: unique hashes over ALL records = **41,878**; over ok records = **41,877**; `canonical_set.json` `annotation_set` = 41,877 = exactly the ok-unique set. The single extra hash (`4859836d422ae21e…`) exists only on `missing` records (vault churn, `D:\agent-sessions-vault\stores\claude-code\…496d5175….jsonl`) — CORPUS.md §4 explicitly retains missing-record hashes. CORPUS.md's 41,877 claim is correct for the annotation set. |
| dedup_index.json internally consistent | same | PASS — 35,589 groups = exactly the hashes duplicated among ok records; group-member sum 116,445 = declared `duplicate_files` = recomputed ok records sharing a dup hash; every member path exists in manifest with that exact hash (0 foreign/mismatched paths); 27/35,589 groups are not plain-`sorted()` but are all sorted case-insensitively (Windows collation) — cosmetic only |
| canonical choice rule (newest mtime → larger size → lex-min path) | `_audit/audit_corpus3.py` | 29/41,877 divergences vs manifest-second-precision mtimes; verified against full-precision `os.stat` on 2 pairs (e.g. `.350796` chosen over `.224399`): the builder used sub-second `st_mtime` while the manifest stores whole-second ISO strings. Explained, not corruption. Annotation `size` fields match manifest on all 41,877. |
| stats.json reconciliation | same | PASS — every totals/by_* number matches independent recomputation (records 124,327; ok 122,733; missing 1,594; unique 41,877; dup 116,445/35,589; parsed 68,633; deferred 51,548; bytes 371,673,156,809; messages 35,885,450; C: 51,643 / D: 71,090; live 47,892 / backup 51,446 / orphan 23,395) |
| spot-check 10 random manifest entries | same, seed 20261018 | **10/10: path exists AND on-disk size == manifest size** (mix of C:/D:, live/backup/orphan) |
| corpus verify.py | — | **NOT RUN — no verify.py exists in corpus/** (shared input lane, not a sweep lane) |

---

## 2. `mastscope/fullrun/` — VERDICT: data artifacts PASS; derived aggregates/RESULTS/dashboard STALE

Raw data (all parse, all end with newline, zero corrupt lines):

| file | lines | parse | notes |
|---|---:|---|---|
| `labels.jsonl` (v1) | **16,253** (exactly as expected) | 16,253/16,253 | ok=15,532, parse_fail=721; **0 duplicate trace_ids** (no overwrite question arises); all records have the 14-mode schema; single model `glm-5.3-flash` |
| `labels_full.jsonl` (v2) | 31,631 | 31,631/31,631 | 0 duplicate target_ids; 29,459 labeled (28,224 ok, 1,235 parse_fail) + 2,172 fail-only checkpoints (`http_429_exhausted`); 13,194 migrated_from v1 (= aggregates2 claim) |
| `targets.jsonl` | 33,889 | 33,889/33,889 | every label target_id ∈ targets; coverage.sum: ok 28,224 + fail 3,407 + pending 2,258 = 33,889 ✔ |
| `sweep_status.json` / `sweep_status2.json` | — | parse | v1 status ok=15,522 (≈ labels.jsonl 15,532, snapshot drift); v2 done_total=31,551 (≈ 31,631, same) |
| `manifest_index.json` | 124,327 entries | parse | path→hash index, complete |
| `census.jsonl` 19,267 · `crosscheck.jsonl` 50 · `crosscheck_mini.jsonl` 4 · `labels_smoke.jsonl` 25 · `smoke2.jsonl` 3 · `privacy_partial.jsonl` 111,157 · `targets_partial.jsonl` 41,877 · `targets.jsonl.tmp` 32,663 | all | all | zero parse failures anywhere |

STALE (unresolved — the sweep continued after these were last generated):

- `aggregates.json` (v1): n_labeled_ok **1,920** vs labels.jsonl's current 15,532 ok.
- `aggregates2.json`: n_labeled_ok **14,341** / pending **19,403** vs current labels_full.jsonl **28,224** ok / **2,258** pending. Same staleness propagates to `RESULTS.md` CHECK markers (n_ok 14341, pending 19403, …) and `dashboard_full2.html` KPIs.
- `RESULTS.md` §8 lists `fullrun/crosscheck2.jsonl`, `crosscheck2_agreement.json`, `privacy_scan_full2.json` — **none exist**; §5 honestly says "Cross-check not available"; §2 privacy table is zeroed/empty while `privacy_partial.jsonl` holds 111,157 partial per-file records.
- `targets.jsonl.tmp` is a leftover atomic-write temp (superseded by the complete 33,889-line `targets.jsonl`); it parses fully — harmless, left in place.

verify runs: `verify.py` (synthetic smoke) **PASS exit 0 (36 checks)** · `verify_fullrun.py`
**FAIL exit 1 — 12 pass / 30 fail** (all recon.* mismatches = staleness above, plus
`labels.mode_schema (2172 bad)` = the intentional label-less `http_429_exhausted`
checkpoint lines, plus dashboard KPI). Full output: `_audit/out_mast_verify_fullrun.txt`.

---

## 3. `tau2-bench/results/` (where sweep.py writes) — VERDICT: raw results PASS & resumable; summary/RESULTS/usage INCOMPLETE

Raw per-domain results (single-file checkpoint format with `simulation_index`):

| domain | sims | tasks | trials | dup (task,trial) | contiguous | seeds | notes |
|---|---:|---:|---|---|---|---|---|
| airline | 200 | 50 | 0..3 | 0 | ✔ | all | reconciles with summary.json (mean/pass^k/counts) |
| ecommerce_poc | 52 | 13 | 0..3 | 0 | ✔ | all | reconciles |
| mock | 40 | 10 | 0..3 | 0 | ✔ | all | reconciles |
| retail | 456 | 114 | 0..3 | 0 | ✔ | all | reconciles |
| telecom | 456 | 114 | 0..3 | 0 | ✔ | all | 37 sims `reward_info=None` w/ `termination_reason=infrastructure_error` (real API errors, retained); **summary.json entry is an empty stub (0 sims)** — stale |
| telecom-workflow | 86 | 86 | {0} only | 0 | ✔ | all | 1 of 4 trials done (interrupted); 14 infrastructure_error sims; **no summary.json entry at all** |
| banking_knowledge | — | — | — | — | — | — | in sweep.py SHIPPED_ORDER but **never run** (no results dir) |

- Checkpoints resumable: YES — (task,trial) pairs unique everywhere, trials contiguous
  0..k-1, per-domain results.json is the harness's own auto-resume checkpoint.
- `summary.json` (mtime 09:52) predates `telecom/results.json` (17:57) and
  `telecom-workflow/results.json` (20:28) — never re-summarized after the sweep continued.
- `sweep_status.json` is the old pilot checkpoint (ecommerce_poc n_sims 13 vs final 52).
- `RESULTS.md` **does not exist** for this lane.
- Usage: `usage_retail.json` (7,863 calls) and `usage_telecom.json` (26,710 calls) real;
  `usage_airline/mock/ecommerce_poc.json` parse but are all-zero (observer didn't fire);
  **`usage_telecom-workflow.json` missing**.

verify runs: `verify.py` (v1 smoke) **FAIL exit 1 — 3 fails**
(`poc-tasks-file-parses`, `poc-split-file-parses`, `poc-validates-harness-schema`: the
verifier pins the original 2-task POC; the POC legitimately grew to 13 tasks
`ecomm_return_001…ecomm_shipping_003` for the full run — the POC itself validates:
verify_fullrun's `custom-domain-offline-suite` PASSes with "ALL 43 DOMAIN CHECKS PASSED")
· `verify_fullrun.py` **FAIL exit 1 — 9 fails** (`results-domains-present` 6<7,
telecom mean/pass^k/counts vs stub, `summary-present[telecom-workflow]`,
`sim-fields[telecom|telecom-workflow]` = the None-reward infrastructure_error sims,
`results-md-table-reconciles` RESULTS.md missing, `usage-files-present` telecom-workflow).
Outputs: `_audit/out_tau2_verify*.txt`.

---

## 4. `trail/work/fullrun/` — VERDICT: checkpoints PASS & coherent; run INCOMPLETE; corpus2_summary STALE

- `gold_meta.jsonl`: 66 attempt records, 0 parse failures, ends with newline; 35 unique
  GAIA files attempted; 12 retried; **last-wins resume pattern verified coherent**:
  disk holds exactly the 32 files with ≥1 `ok` attempt; every retried file's LAST attempt
  is `ok`; the 3 files whose last attempt errored correctly have NO output on disk;
  statuses: 38 ok / 14 InternalServerError / 14 RateLimitError; model `glm-5.3`.
- Gold outputs on disk: **GAIA 32/117 · SWE Bench 0/31** → verify expects 117/31 →
  run incomplete. `GAIA-metrics.txt` / `SWE Bench-metrics.txt` / `gold_agreement.json`
  absent (never generated). All 32 existing outputs parse; no error-marker outputs.
- `corpus2_labels/`: 297 files, **0 parse failures, 0 duplicate sha256, 0 orphan shas**
  (all ∈ canonical_set annotation_set), 0 privacy key violations.
- `corpus2_summary.json` STALE: built at `label_files: 94` (status_counts 87+7) vs **297
  label files on disk now** — the corpus2 sweep continued past the last summarize.
- `corpus2_jobs.json` parses (canonical_total 41,877 → supported 40,798); usage ledgers
  parse (corpus2 71 lines, gold 38 lines); 4 usage-ledger rows mismatch retried labels
  (stale ledger rows vs last-wins label overwrites); `usage_total.json` parses.

verify runs: `verify.py` **PASS exit 0** (with lane `.venv`) · `verify_fullrun.py`
**FAIL exit 1 — 16 fails** (gold GAIA 32≠117, SWE 0≠31, metrics+agreement files missing,
6 `summary … reconciles` failures = stale corpus2_summary, usage-ledger mismatch ×4,
RESULTS.md label count stale). Output: `_audit/out_trail_verify_fullrun.txt`.

---

## 5. Repairs / quarantine performed

- **Quarantined: NOTHING.** No file under any lane failed to parse; no JSONL has a
  truncated final line (all end with `\n` and parse 100%); no numbers were edited.
- Dropped lines: none.
- Junk noted (left in place, 0 bytes each, Windows redirection artifacts):
  `tsis-deepdive/nul`, `mastscope/NUL`, `mastscope/fullrun/nul`, `tau2-bench/nul`,
  `trail/NUL`.

## 6. What resuming agents must know

1. **mastscope**: `labels_full.jsonl` (31,631 lines) is AHEAD of `aggregates2.json`,
   `RESULTS.md`, and `dashboard_full2.html`. Re-run `aggregate2.py` →
   `render_results.py`/`make_dashboard2.py` → `verify_fullrun.py` after the sweep ends.
   The 2,172 `http_429_exhausted` label-less checkpoint lines will keep failing
   `labels.mode_schema` until those targets are re-annotated (2,258 still pending).
   `crosscheck2.jsonl` / `privacy_scan_full2.json` promised in RESULTS.md §8 were never
   produced; `targets.jsonl.tmp` is a stale atomic-write leftover.
2. **tau2-bench**: re-run the summarizer to regenerate `summary.json` (telecom currently
   a 0-stub; telecom-workflow absent), write the lane `RESULTS.md`, flush
   `usage_telecom-workflow.json`, finish telecom-workflow trials 1–3, and decide
   whether `banking_knowledge` runs (it is in SHIPPED_ORDER but has no results).
   The v1 smoke `verify.py` POC expectations (2 tasks) are outdated vs the 13-task POC —
   trust `verify_fullrun.py`'s `custom-domain-offline-suite` for the POC.
   The 37+14 `infrastructure_error` sims carry `reward_info:null` by design (real API
   errors retained); do not delete them.
3. **trail**: resume the gold run (85 GAIA remaining incl. 3 errored files: retry by
   target id — checkpoint ledger is last-wins coherent; SWE Bench 31 not started), then
   run the repo metrics + agreement steps to produce `*-metrics.txt` /
   `gold_agreement.json`. Re-run `fullrun_summarize2` — `corpus2_summary.json` is from
   the 94-label era while 297 label checkpoints exist. 4 corpus2 usage-ledger rows are
   stale vs retried labels.
4. **corpus**: healthy; nothing to resume. (The 41,878-vs-41,877 unique-hash nuance is
   by design — one hash lives only on missing records.)

## 7. verify.py scoreboard (this auditor's runs)

| lane | verify.py | verify_fullrun.py |
|---|---|---|
| corpus | not run (none exists) | not run (none exists) |
| mastscope | **PASS** (exit 0, 36 checks) | **FAIL** (exit 1, 30 failed / 12 passed) |
| tau2-bench | **FAIL** (exit 1, 3 failed — stale POC expectations) | **FAIL** (exit 1, 9 failed) |
| trail | **PASS** (exit 0) | **FAIL** (exit 1, 16 failed) |
