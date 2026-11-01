# INTEGRITY — audit of all produced artifacts (2026-10-30 session)

Auditor: results-integrity subagent ("Results integrity auditor"), 2026-10-30 ≈22:00–23:30.
Every check below was executed this session with system Python 3.14.6. Audit scripts are
preserved in `_audit/audit_20261030/` (and `_audit/audit_20261030/recheck_new_root.py`
re-proves every core check at the final path). Verifier outputs cited below were captured
at `/tmp/{mast,tau2,trail}_*.log` during the run.

> **MIGRATION NOTICE (read first).** Mid-audit — between 22:45 and 23:00 on 2026-10-30 —
> another agent migrated the entire project from `tsis/deepdive/` to
> `tsis/agent-evaluation/` (a second hop; the 2026-10-18 tree lived at `tss/tsis-deepdive/`).
> All findings below were first established at `tsis/deepdive/` and then **re-run against
> `tsis/agent-evaluation/`** with identical results (receipt: `recheck_new_root.py` output,
> quoted per section). The one casualty of the migration (a stale venv path) was repaired
> and is documented in §3. The prior `tsis/deepdive/` path is now an empty skeleton with a
> pointer to this file.

---

## Scoreboard

| lane | data artifacts | verify.py | verify_fullrun.py |
|---|---|---|---|
| corpus | **PASS** (all checks) | not run — no verify.py exists in corpus/ | not run — none exists |
| mastscope | **PASS** (v1 aggregate stale, superseded) | **PASS** exit 0 (36 checks) | **PASS** exit 0 (43 checks) |
| tau2-bench | **PASS** (all 4 results dirs) | **FAIL** exit 1 (34/43 — v1 POC drift, §3) | **PASS** exit 0 (176/176, after venv-path repair §3) |
| trail | **PASS with 1 quarantine** (§4) | **PASS** exit 0 | **FAIL** exit 1 (46/54 — batch-B sweep incomplete, §4) |

Unresolved failures (nothing faked, nothing deleted): the 8 trail batch-B failures
(incomplete sweep + stale derived summary/RESULTS/agreement + missing `sensitivity_d.json`)
and tau2's v1 `verify.py` POC-expectation drift. Details in §3/§4 and §6.

---

## 1. `corpus/` — VERDICT: PASS (all checks; re-proven at final path)

Run: `python -X utf8 _audit/audit_20261030/recheck_new_root.py` (full re-parse of the
73,315,396-byte manifest at `tsis/agent-evaluation/corpus/manifest.jsonl`):

```
[corpus] manifest lines=124327 (==124327: True) parse_fail=0 sha_missing=0 ends_nl=True
[corpus] statuses={'ok': 122733, 'missing': 1594} unique_ok=41877 (==41877: True)
[corpus] annotation_set==unique_ok: True; unique_files field=41877
[corpus] dedup groups=35589==decl 35589: True; members=116445==decl 116445: True
[corpus] spot-check 10 at new path: 10/10 PASS
```

- **Every line parses**: 124,327/124,327 (0 failures; file ends with newline).
- **Total = 124,327** exactly (122,733 `ok` + 1,594 `missing`), matching CORPUS.md's
  "manifest records **124,327** (122,733 ok + 1,594 missing, never dropped)".
- **sha256 present on every record** (0 missing; full 18-key schema on all records —
  key-frequency census in `_audit/audit_20261030/corpus_audit.py` output).
- **Unique hashes**: 41,877 over `ok` records; `canonical_set.json` `annotation_set`
  (41,877 entries) is **set-equal** to the ok-unique hashes; CORPUS.md's "41,877" matches.
  Same documented nuance as 2026-10-18: 41,878 unique hashes over ALL records — the single
  extra hash lives only on `missing` records and is deliberately retained by CORPUS.md §4.
  Annotation `size` fields match manifest sizes on all 41,877 (0 mismatches).
- **dedup_index.json internally consistent**: 35,589 groups == declared `duplicate_hashes`;
  116,445 member paths == declared `duplicate_files`; 0 foreign paths, 0 wrong-hash paths,
  0 non-ok members, 0 groups with <2 members (`_audit/audit_20261030/corpus_audit5.py`).
- **Spot-check 10 random manifest entries** (seed 20261030): **10/10 path exists AND
  on-disk size == manifest size** (mix of C:/D:, live/backup/orphan sources; receipts in
  `_audit/audit_20261030/corpus_spot.py` output).
- corpus has no verify.py (shared input lane) — recorded as **not run**, per prior audit.

## 2. `mastscope/fullrun/` — VERDICT: PASS

Run: `_audit/audit_20261030/mast_audit*.py` + `recheck_new_root.py`, at
`tsis/agent-evaluation/mastscope/fullrun/`:

```
[mastscope] labels.jsonl: lines=16253 (==16253: True) parse_fail=0 dup_ids=0 ends_nl=True
[mastscope] labels_full.jsonl: lines=33889 (==33889: True) parse_fail=0 dup_ids=0 ends_nl=True
[mastscope] aggregates2 reconcile: n_labeled_ok=32540==32540: True; n_parse_fail=1349==1349: True; targets=33889==33889: True; pending=0
```

- **labels.jsonl (v1): exactly 16,253 lines**, 0 parse failures, **0 duplicate trace_ids**
  (the last-wins resume-overwrite case never arises), 14-key MAST-14 mode schema
  (`1.1`–`3.3`) on every record with 0 schema deviations, single model `glm-5.3-flash`,
  ok=15,532 / parse_fail=721.
- **labels_full.jsonl (v2): 33,889 lines** = 100 % of `targets.jsonl`, 0 parse failures,
  0 duplicate target_ids, ok=32,540 / parse_fail=1,349, 13,194 `migrated_from` v1; every
  label's sha256 matches its target record (0 mismatches); label IDs == target IDs exactly.
- **aggregates2.json fully reconciles** with labels_full.jsonl: all scalars (targets 33,889,
  n_labeled_ok 32,540, n_parse_fail 1,349, pending 0, traces_with_any_mode 21,205,
  total_yes 52,034, migrated 13,194) AND all 14 per-mode `yes` counts AND the
  task_completed distribution `{no 9,830, null 11,501, yes 11,209}` / 34.45 %.
- **aggregates.json (v1) is STALE** (`n_labeled_ok=1,920` vs labels.jsonl's 15,532 ok;
  all 14 mode counts stale). It is the superseded v1-sweep aggregate — regenerated numbers
  must come from re-running `aggregate.py`, never by editing. v2 (`aggregates2.json`) is
  current and authoritative.
- **All checkpoint/aux files parse**: `sweep_status.json`, `sweep_status2.json`,
  `sweep2_status_history.jsonl` (3 lines), `fallback_pending.json`, `targets_summary.json`,
  `crosscheck_agreement.json`, `crosscheck2_agreement.json`, `privacy_scan_full2.json`,
  `manifest_index.json` (124,327 entries), and JSONLs `census.jsonl` 19,267,
  `crosscheck.jsonl` 50, `crosscheck2.jsonl` 50, `crosscheck_mini.jsonl` 4,
  `privacy_partial.jsonl` 122,733, `scan_skipped_results.jsonl` 2,271,
  `labels_smoke.jsonl` 25, `smoke2.jsonl` 3, `targets_partial.jsonl` 41,877 — 0 parse
  failures anywhere. The files the 2026-10-18 audit listed as missing
  (`crosscheck2.jsonl`, `crosscheck2_agreement.json`, `privacy_scan_full2.json`) now exist.
- verify.py **PASS exit 0 (36 checks)**; verify_fullrun.py **PASS exit 0 (43 checks)**
  — the 30 failures of 2026-10-18 are all resolved.
  (Prior audit's `labels.mode_schema (2172 bad)` no longer applies: the completed v2 sweep
  re-annotated everything; pending=0.)

## 3. `tau2-bench/` — VERDICT: results PASS everywhere; one migration casualty repaired

Checked every results dir produced by the sweeps (`sweep.py` → `results/`,
`sweep2.py` → `results_v2/`, the grok variant → `results_v2_grok/`, plus
`results_secondmodel/`). Receipts: `_audit/audit_20261030/tau2_audit*.py` and
`recheck_new_root.py` (`[tau2] all results.json parse at new path; total sims across 4
dirs=5495; dup(task,trial)=0 everywhere: PASS`).

| dir | domains (sims) | state |
|---|---|---|
| `results/` (GLM-5.3, sweep.py) | airline 200, banking_knowledge 388, ecommerce2 56, ecommerce_poc 52, mock 40, retail 456, telecom 456, telecom-workflow 456 | complete: 4 trials × tasks everywhere, 0 dup (task,trial), trials contiguous, `summary.json` present |
| `results_v2_grok/` (grok-4.7) | airline 200, banking 388, ecommerce3 56, mock 40, retail 456, telecom 456, telecom-workflow 456, **intake 800** = 2,852 | complete, same invariants; `summary.json` + `RESULTS_section_draft.md` present |
| `results_v2/` (GLM v2, partial) | airline 71, banking 52, ecommerce3 56, mock 40, retail 111, telecom 76 | interrupted but **resumable**: 0 dups, trials contiguous; no summary.json (never summarized) |
| `results_secondmodel/` (pilot) | airline 77, ecommerce2 56 | partial pilot, resumable, no summary.json |

- **Every results JSON parses** — including `usage_*.json` in all dirs and the experiment
  dir `results_v2_grok/mock_allinfra_ledgerstorm_20261028/results.json`.
- **summary.json ↔ results.json reconcile in both complete dirs**: n_sims exact on all 16
  domain entries; mean_reward matches the summarizer's formula (`round(sum/len,4)`,
  `summarize_grok.py:61`) on every domain (`_audit/audit_20261030/tau2_audit3.py` →
  `ALL DOMAINS RECONCILE (n_sims + mean_reward at 4dp): True` for both dirs). The earlier
  `reward_info=None` infrastructure-error sims flagged on 2026-10-18 are gone (repair
  scripts `results/repair_*_infra*.log` re-ran them; 0 None-reward sims remain).
- **Checkpoints resumable**: per-domain `results.json` is the harness's own auto-resume
  checkpoint (sweep.py docstring, lines 14–18); (task,trial) unique and trials contiguous
  in all 4 dirs, so any partial dir can resume without collision.
- `results_v2_grok/sweep_status.json` contains a historical `"mock": "failed: ValueError:
  Tasks were modified…"` string — a mid-run checkpoint note; mock itself is complete
  (40 sims, reconciles). Left as-is (checkpoint history, not data).
- **Migration casualty repaired (tooling, not data)**: mid-audit the tree moved to
  `tsis/agent-evaluation/`, and the repo junction `tss/tsis-deepdive` (which the venv's
  editable install pointed through) was removed. Symptom:
  `repo/.venv/Scripts/python.exe poc/load_ecommerce3.py` → `ModuleNotFoundError: No module
  named 'tau2'` because `repo/.venv/Lib/site-packages/_editable_impl_tau2.pth` still
  contained `…\tss\tsis-deepdive\tau2-bench\repo\src`. **Repair**: rewrote that one line to
  `C:\Users\<os-user>\.zcode\workspace\default\tsis\agent-evaluation\tau2-bench\repo\src`.
  After the repair: `poc/load_ecommerce3.py` → `ALL PASS (67/67 checks)`, and
  **verify_fullrun.py → exit 0, 176 PASS / 0 FAIL** (`VERIFY OK -- all checks passed`;
  the lane's own pre-migration receipt `results_v2_grok/verify_fullrun_output.txt`
  2026-10-30 04:28 already showed VERIFY OK, confirming the migration — not the lane —
  broke it). No numbers touched.
- verify.py (v1) **FAIL exit 1, 34/43** — all 9 failures are the documented v1-verifier
  drift (pinned to the original 2-task POC; the POC legitimately grew to 14 tasks
  `coupon_task_1…lost_task_1`) plus its harness-side subprocess (`KeyError: 'SAVE10'`)
  and a Windows artifact: `git status` in `repo/` shows ` D
  web/leaderboard/public/task-data/domains` because upstream tracks it as a symlink that
  Windows materialises as a directory. None of these are data corruption; the
  authoritative custom-domain suite (`poc/load_ecommerce3.py`, 67/67) is green and
  verify_fullrun.py passes. Recorded as unresolved-but-explained, per the 2026-10-18
  audit's identical finding.

## 4. `trail/` (checkpoint layout: `trail/work/fullrun/`) — VERDICT: checkpoints PASS; 1 file quarantined; batch B incomplete

Receipts: `_audit/audit_20261030/trail_audit.py`, `trail_gold.py`, `trail_resume.py`,
`recheck_new_root.py`, all re-run at `tsis/agent-evaluation/trail/work/fullrun/`.

- **gold_meta.jsonl** (glm-5.3): 106 records, 0 parse failures; 71 unique files, 15
  retried; **last-wins resume verified coherent**: disk holds exactly the 33 files whose
  LAST attempt is `ok` (exact set match); last-attempt errors: 38 `ProviderSaturated`
  (glm run incomplete by provider outage — superseded, see next bullet).
- **gold_meta_nv.jsonl** (nvidia/nemotron-3-ultra-550b-a55b): 296 records, 0 parse
  failures; 148 unique files, every one retried, **all 148 last attempts ok**; disk holds
  GAIA 116 + SWE Bench 31 = 147 files that ALL parse, plus the 1 quarantined file below →
  **exactly the 148 last-ok set** (exact set match incl. quarantine).
- **QUARANTINED (the audit's only quarantine):**
  `gold_outputs/nvidia-nemotron-3-ultra/GAIA/41bbc898aa7de0f31d2382ff57700a76.json`
  → moved intact to `trail/work/fullrun/_quarantine/nvidia-nemotron-3-ultra_GAIA/` with
  sidecar `…json.sidecar.md`. Reason: not valid JSON — five `"description"` string values
  written unquoted (lines 7/14/21/28/35) plus embedded control characters
  (`json.loads` → `Expecting value at line 7 column 28`); not a truncation, so no
  line-drop repair applied, and no bytes were edited. **Downstream impact: none** —
  `gold_agreement.json`'s per_file record scores this target against the **glm-5.3**
  output, and `union-top/GAIA/…` (which parses) is the glm-5.3 version per
  `union-top/MODEL_MANIFEST.json`. Regenerate by re-running the single nv gold target
  (gold_meta_nv.jsonl line 174 records a successful attempt) — do not hand-patch quotes.
- **gold outputs**: glm GAIA 33/33 parse; nv GAIA 116/116 parse post-quarantine; SWE 31/31
  parse; `union-top` GAIA 117 + SWE 31 all parse; `GAIA-metrics.txt`, `SWE
  Bench-metrics.txt`, `MODEL_MANIFEST.json`, `gold_agreement.json` (148/148 files
  processed, wF1 0.36825) all present and parse. The 2026-10-18 gold gaps are closed.
- **corpus2_labels (batch A)**: **40,798/40,798 COMPLETE** — every file parses, 0 duplicate
  sha256, 0 orphans (all ∈ canonical annotation_set), 0 error markers;
  `corpus2_summary.json` is **current** (label_files 40,798 == disk).
- **corpus2_labels_b (batch B, grok-4.7)**: **38,874/40,798 INCOMPLETE — sweep died
  tonight** (fleet watcher last logged `labels_b=38591/40798` at 21:23 after
  `fleet query failed: TimeoutError`; supervisor last cycle 21:06; no lane process alive
  at 22:05). All 38,874 files parse, 0 dups, 0 orphans, B ⊂ A — **cleanly resumable,
  1,924 targets remaining**. Derived artifacts are stale as a direct consequence:
  `batchb_summary.json` (files_checkpointed 5,152; annotated_ok 1,106 vs raw ok=21,504),
  `batchb_agreement.json` (overlap 86 vs raw 188), `RESULTS.md` batch-B markers,
  and `sensitivity_d.json` was never generated.
- Other checkpoints parse: `corpus2_jobs.json` (canonical_total 41,877 → supported
  40,798), `corpus2_census.json`, `queue_state.json` (stale snapshot from the superseded
  Oct-20 finish-queue era, harmless), `FINISH_PIDS.json`, `wave3_wait_state.json`,
  usage ledgers (`corpus2.jsonl` 27,696 / `corpus2_b.jsonl` 9,357 / `gold.jsonl` 39 /
  `gold_nv.jsonl` 148 — 0 parse failures).
- verify.py **PASS exit 0** ("RESULT: ALL CHECKS PASSED"). verify_fullrun.py **FAIL
  exit 1 — 46 PASS / 8 FAIL**, all eight being the incomplete batch-B set above:
  `batch B label files == canonical set size (38,874 vs canon 40,798)`, `batch B summary
  files_checkpointed matches raw (5,152 vs 38,874)`, `batch B summary annotated_ok matches
  raw (1,106 vs raw ok=21,504)`, `batch B summary statuses match raw`, `RESULTS.md carries
  batch B checkpointed count`, `RESULTS.md carries batch B annotated-OK count`,
  `agreement overlap count matches raw labels (raw=188 json=86)`, `sensitivity_d.json
  exists` (×2). These must be fixed by finishing the sweep and re-running the lane's own
  summarize/agreement steps — never by editing numbers.

## 5. Repairs / quarantine performed (this session)

1. **Quarantined** `trail/work/fullrun/gold_outputs/nvidia-nemotron-3-ultra/GAIA/
   41bbc898aa7de0f31d2382ff57700a76.json` (invalid JSON, unquoted values — §4) with a
   full sidecar note. Nothing deleted; no valid data touched; no numbers edited.
2. **Repaired venv path** `tau2-bench/repo/.venv/Lib/site-packages/_editable_impl_tau2.pth`
   (dead `tss\tsis-deepdive\…` path → current `tsis\agent-evaluation\…` path) after the
   mid-audit migration broke it. Tooling config only; tau2's `verify_fullrun.py` went
   175→176 PASS / 1→0 FAIL after this repair.
3. **Dropped lines: none.** No truncated final line was found anywhere — every JSONL
   audited ends with `\n` and parses 100 %.
4. Junk 0-byte Windows redirection artifacts still present, left in place (harmless):
   `nul` (root), `tau2-bench/nul`, `trail/NUL`.

### 5b. Repairs performed by the gate-fix round (2026-10-31 → 2026-11-01)

Round-2 gate state supplied with the ask: tau2=0, trail=1, mast=0. Re-run before
repairs: tau2 exit 0, mastscope exit 0, trail exit 1 with **11 FAILs** — the 8
batch-B failures of §4 **plus 3 new ones** caused by the 2026-10-30/31 corpus refresh
(§CORPUS.md final run 2026-10-31T00:30: 163,681 records / 71,590-hash annotation_set,
superseding the 124,327/41,877 set the trail artifacts were built on):
`every label sha is a canonical sha (59 orphans)`, `summary manifest inheritance
reconciles`, `manifest inheritance count matches summary`. All repairs below follow the
lane's own tooling; no number was hand-edited anywhere.

1. **Finished batch B** (the §4/§6.2 prescription): resumed
   `fullrun_batchb_grok.py` (tags batchb-r2/-r3/-r4; one mid-run PROVIDER-SATURATED
   exit 3 at 40,161/40,798 after 81 consecutive 429s, one host process death at
   40,197 — both cleanly resumed, checkpoint design proven again). Final:
   **FINISHED batch B: done=40798/40798** (r4, log `work/fullrun/batchb_r2.log`),
   single-model invariant grok-4.7 (fresh 23,807 + reused-wave3 16,991), ok=23,332.
2. **Quarantined 59 orphaned batch-A labels** to
   `work/fullrun/_quarantine/corpus2_labels_orphans_20261031/` (move-intact +
   `QUARANTINE.json` sidecar, per §5.1 precedent; nothing deleted, no bytes edited):
   their sha256s left the refreshed `canonical_set.json` annotation_set — verified
   statuses in the refreshed manifest: 10 `missing`, 49 absent entirely.
   Label dir: 40,798 → 40,739 files (the 10 ok-status labels among them are why batch-A
   `annotated OK` moves 24,787 → 24,777 in the regenerated summary/RESULTS.md).
3. **Regenerated every derived artifact with the lane's own generators**:
   `fullrun_summarize2.py` (corpus2_summary.json — manifest block now reconciles
   against the 163,681-record manifest: records_labelled 126,705, inheriting 89,608),
   `fullrun_batchb_summary.py` (batchb_summary.json 40,798/23,332 + batchb_agreement.json
   full-overlap: glm-5.3-flash vs grok n=206 meanJaccard 0.4517 exact 0.2573; ultra
   n=8,500 / ultra:free n=1,770), `fullrun_sensitivity_d.py` (sensitivity_d.json;
   B=1076/C=1162 snapshots reproduce published counts exactly, new full-N D n_ok=23,332;
   "Full-N point (D)" + "VERDICT AT FULL N" appended to `fullrun/sensitivity.md`),
   `fullrun_dashboard.py`, `fullrun_results_md.py` (RESULTS.md regenerated — batch A
   40,739/40,798 · 24,777 ok; batch B 40,798 · 23,332 ok; §1 headline gold metrics
   unchanged, as expected — gold artifacts untouched).
4. **Gates re-run after repairs**: tau2-bench `verify_fullrun.py` exit 0 (`VERIFY OK --
   all checks passed`); mastscope exit 0 (`VERIFY OK: 43 checks passed`); **trail
   exit 0 — `ALL 56 CHECKS PASSED`** (56 vs the earlier 54 because the batch-B and
   sensitivity-D checks now execute with their artifacts present). Receipts:
   `/tmp/{tau2,mast}_gate_r2_{before,after}.log`, `/tmp/trail_gate_r2_{before,after2}.log`.

## 6. What resuming agents must know

1. **The tree now lives at `tsis/agent-evaluation/`** (git present; old `tsis/deepdive/`
   is an empty skeleton with a pointer). If anything still references absolute paths from
   `tss/tsis-deepdive/` or `tsis/deepdive/`, it is dead — the venv `.pth` above was one
   such case; grep for others before resuming sweeps.
2. **trail batch B is mid-flight**: 38,874/40,798 labels done (grok-4.7, reasoning_effort
   low), watcher dead since ~21:23. Resume `fullrun_batchb_grok.py`, then re-run
   `batchb_summary.py` + the agreement step and generate `sensitivity_d.json`; update the
   batch-B markers in RESULTS.md. Do NOT trust `batchb_summary.json` /
   `batchb_agreement.json` as-is (5,152/86-era snapshots).
   **[RESOLVED 2026-11-01 — see §5b: batch B finished 40,798/40,798, all derived
   artifacts regenerated, verify_fullrun exit 0 / 56 checks.]**
3. **trail glm gold run** stopped at 33/117 GAIA (38 ProviderSaturated on last attempt);
   it is superseded by the nv+union gold set (148/148 agreement complete), so resuming it
   is optional. The quarantined nv file is regenerated by re-running its single target.
4. **tau2-bench**: `results/` and `results_v2_grok/` are complete and reconciled;
   `results_v2/` and `results_secondmodel/` are partial-but-resumable (decide whether to
   finish or archive). The v1 `verify.py` will keep failing on POC expectations — use
   `verify_fullrun.py` (176/176) as the gate.
5. **mastscope** is fully landed (pending=0, aggregates2 current); only the v1
   `aggregates.json` is a stale historical snapshot — do not cite it.
6. **corpus** is healthy and closed: 124,327 records / 41,877 canonical hashes, dedup
   index and canonical set fully consistent.

## 7. verify.py scoreboard (this auditor's runs, at final path)

| lane | verify.py | verify_fullrun.py |
|---|---|---|
| corpus | not run (none exists) | not run (none exists) |
| mastscope | **PASS** (exit 0, 36 checks) | **PASS** (exit 0, 43 checks) |
| tau2-bench | **FAIL** (exit 1, 34/43 — v1 POC drift + Windows symlink artifact) | **PASS** (exit 0, 176/176 — after `.pth` migration repair) |
| trail | **PASS** (exit 0) | **FAIL** (exit 1, 46/54 — batch-B incompleteness, §4) |

*2026-11-01 update (gate-fix round, §5b): trail verify_fullrun re-run → **PASS exit 0,
ALL 56 CHECKS PASSED** (the 2026-10-30 table row above is retained as the historical
record of that session; the check count differs because batch-B/sensitivity-D checks
only execute once their artifacts exist).*

---
---

# PRIOR AUDIT (2026-10-18) — preserved unchanged below for the historical record

*(That audit ran against the tree at `tss/tsis-deepdive/`; paths below are historical.
Its "what resuming agents must know" items have since been completed except where §6
above says otherwise.)*

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
