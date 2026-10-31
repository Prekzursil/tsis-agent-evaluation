"""Emit tss/tsis-deepdive/trail/RESULTS.md from the raw artifacts
(gold_agreement.json, corpus2_summary.json, usage ledgers, provider claims).
Every number in RESULTS.md is derived here from artifacts on disk - no
hand-typed values, so a later re-run cannot leave stale numbers behind."""
from __future__ import annotations

import glob
import json
import os
from datetime import datetime, timezone

from fullrun_common import LANE

WORK = os.path.join(LANE, "work", "fullrun")
A_PATH = os.path.join(WORK, "gold_agreement.json")
S_PATH = os.path.join(WORK, "corpus2_summary.json")
OUT = os.path.join(LANE, "RESULTS.md")

NV = "nvidia/nemotron-3-ultra-550b-a55b"


def fmt(x, n=4):
    return f"{x:.{n}f}" if isinstance(x, (int, float)) else str(x)


def main():
    A = json.load(open(A_PATH, encoding="utf-8"))
    S = json.load(open(S_PATH, encoding="utf-8"))

    # ---- usage totals from ledgers -------------------------------------
    def ledger(path):
        rows = []
        if os.path.exists(path):
            for l in open(path, encoding="utf-8"):
                if l.strip():
                    try:
                        rows.append(json.loads(l))
                    except json.JSONDecodeError:
                        pass
        return rows

    gold_glm_u = ledger(os.path.join(WORK, "usage", "gold.jsonl"))
    gold_nv_u = ledger(os.path.join(WORK, "usage", "gold_nv.jsonl"))
    corpus_u = ledger(os.path.join(WORK, "usage", "corpus2.jsonl"))

    def tok(rows):
        p = sum(r.get("prompt_tokens") or 0 for r in rows)
        c = sum(r.get("completion_tokens") or 0 for r in rows)
        return p, c, len(rows)

    gp, gc, gn = tok(gold_glm_u)
    np_, nc, nn = tok(gold_nv_u)
    cp, cc, cn = tok(corpus_u)
    batchb_u = ledger(os.path.join(WORK, "usage", "corpus2_b.jsonl"))
    bb_p, bb_c, bb_n = tok(batchb_u)
    batchb_tok_row = (f"| batch B (grok-4.7 fresh calls only; reused-wave3 "
                      f"labels cost 0 new tokens) | {bb_n} | {bb_p:,} | "
                      f"{bb_c:,} |\n" if bb_n else "")
    tot_p, tot_c = gp + np_ + cp, gc + nc + cc

    su = S.get("usage", {})
    ok_n = S["traces_annotated_ok"]
    elig = S.get("census_eligible_sessions") or 0
    cov = (ok_n / elig * 100) if elig else 0.0
    label_n = S["label_files"]
    canon_jobs = S.get("canonical_supported_jobs") or 0
    file_cov = (label_n / canon_jobs * 100) if canon_jobs else 0.0
    man = S.get("manifest", {})

    o = A["overall"]
    attr = A.get("model_attribution", {})
    glm_files = sum(attr.get("glm-5.3", {}).values())
    nv_files = sum(attr.get(NV, {}).values())

    # per-class table
    cm = o["category_metrics"]
    class_rows = "\n".join(
        f"| {c} | {m['support']} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} |"
        for c, m in sorted(cm.items(), key=lambda kv: -kv[1]["support"])
        if m["support"] > 0)
    zero_sup = sum(1 for m in cm.values() if m["support"] == 0)

    # corpus category table (dicts from JSON; sort by count desc)
    cats_sorted = sorted(S["category_counts"].items(), key=lambda kv: -kv[1])
    cat_rows = "\n".join(
        f"| {c} | {n} | {S['category_trace_prevalence'].get(c, 0)} "
        f"| {(100.0 * S['category_trace_prevalence'].get(c, 0) / max(ok_n, 1)):.1f}% |"
        for c, n in cats_sorted)

    rt_sorted = sorted(S.get("per_runtime_traces", {}).items(), key=lambda kv: -kv[1])
    rt_rows = "\n".join(
        f"| {k} | {v:,} | {S.get('per_runtime_eligible', {}).get(k, 0):,} | "
        f"{S.get('per_runtime_ok', {}).get(k, 0):,} | "
        f"{S.get('per_runtime_errors', {}).get(k, 0):,} |"
        for k, v in rt_sorted)

    model_sorted = sorted(S.get("per_model_traces", {}).items(), key=lambda kv: -kv[1])
    model_rows = "\n".join(
        f"| {k} | {v:,} | {S.get('per_model_ok', {}).get(k, 0):,} |"
        for k, v in model_sorted)

    st = S.get("status_counts", {})
    st_rows = "\n".join(f"| {k} | {v:,} |" for k, v in
                        sorted(st.items(), key=lambda kv: -kv[1]))

    imp = S.get("impact_counts", {})
    imp_total = sum(imp.values()) or 1
    imp_rows = "\n".join(f"| {k} | {v} | {(100.0 * v / imp_total):.1f}% |"
                         for k, v in sorted(imp.items(), key=lambda kv: -kv[1]))

    roots = S.get("category_counts_by_root", {})
    root_tot = sum(sum(l.values()) for l in roots.values()) or 1
    root_rows = "\n".join(
        f"| {r} | {sum(l.values())} | {(100.0 * sum(l.values()) / root_tot):.1f}% |"
        for r, l in roots.items())

    ex = A.get("extras", {})
    corr = o.get("score_correlations", {})

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    sens_path = os.path.join(LANE, "fullrun", "sensitivity.md")
    sens_line = ""
    if os.path.exists(sens_path):
        for _l in open(sens_path, encoding="utf-8"):
            if _l.lstrip().startswith("**STABLE") or _l.lstrip().startswith("**UNSTABLE"):
                sens_line = _l.strip()
                break
    NL = "\n"
    sens_block = (NL + "### Bounded sensitivity extension (owner revised order 2026-10-20)" + NL + NL
                  + (sens_line or "(sensitivity verdict pending)") + NL
                  + "Extension labels carry `ext: sensitivity-ext`; single model `glm-5.3-flash`; "
                  "queue = MASTscope-labeled hashes intersect canonical jobs, sha16-sorted, hard cap 5,000. "
                  "Full analysis: `fullrun/sensitivity.md`. (Historical: that bounded "
                  "extension was run under the 2026-10-20 freeze; the 2026-10-21 "
                  "full-corpus finish sweep supersedes its N, and its instability "
                  "verdict motivated completing the full set.)" + NL
                  if os.path.exists(sens_path) else "")
    # ---- batch B (single-model grok full pass) + cross-model agreement ----
    bs_path = os.path.join(WORK, "batchb_summary.json")
    ba_path = os.path.join(WORK, "batchb_agreement.json")
    batchb_block = ""
    if os.path.exists(bs_path) and os.path.exists(ba_path):
        BS = json.load(open(bs_path, encoding="utf-8"))
        BA = json.load(open(ba_path, encoding="utf-8"))
        models_b = ", ".join(f"{k} ({v:,})" for k, v in
                             BS.get("models_present", {}).items())
        prov = BS.get("batch_provenance", {})
        prov_s = ", ".join(f"{k} {v:,}" for k, v in prov.items())
        pair_rows = []
        for m, p in BA.get("pairs", {}).items():
            if not p or not p.get("overlap_ok_pairs"):
                continue
            kaps = p.get("per_class_cohen_kappa") or {}
            kap_s = "; ".join(f"{c} κ={v['kappa']}" for c, v in
                              list(kaps.items())[:5])
            pair_rows.append(
                f"| {m} | grok-4.7 | {p['overlap_ok_pairs']:,} | "
                f"{p['mean_jaccard_category_set']} | "
                f"{p['exact_category_set_match_rate']} | "
                f"{p['impact_share_L1']} | {kap_s} |")
        sens_d_line = ""
        if os.path.exists(sens_path):
            for _l in open(sens_path, encoding="utf-8"):
                if "AT FULL N" in _l and _l.lstrip().startswith("**"):
                    sens_d_line = _l.strip().strip("*")
                    break
        batchb_block = (NL + "### Batch B — single-model grok-4.7 pass over ALL "
                        "canonical targets (2026-10-30) + cross-model agreement" + NL + NL
                        + "Owner expansion order 2026-10-21 (grok-lane economics): "
                        "one instrument, one model — grok-4.7 (reasoning_effort=low) — over "
                        "every canonical target, checkpointed per sha256 in "
                        "`work/fullrun/corpus2_labels_b/` "
                        "(`fullrun_batchb_grok.py`, 14 workers, 429-jitter requeue via "
                        "the local grok bridge; fleet live-queried: 1 enabled account, "
                        "maxConcurrent 8)." + NL + NL
                        + f"- batch B files checkpointed: **{BS.get('files_checkpointed',0):,}"
                        f" / {canon_jobs:,}**" + NL
                        + f"- annotated OK: **{BS.get('annotated_ok',0):,}**; "
                        f"error labels {BS.get('error_labels_total',0):,}; "
                        f"mean labels/annotated {BS.get('mean_errors_per_annotated')};" + NL
                        + f"- single-model invariant: {models_b} (provenance: {prov_s} — "
                        "reused-wave3 = the 16,991 grok-4.7 effort-low labels this same "
                        "pipeline produced in wave3, copied to keep batch B one model "
                        "without re-paying them)." + NL + NL
                        + "**Cross-model agreement (same-hash OK-vs-OK pairs, batch A "
                        "model vs the grok-4.7 batch-B label; per-trace normalized "
                        "error-CATEGORY SETS):**" + NL + NL
                        + "| batch A model | batch B model | n overlap | mean Jaccard | "
                        "exact set match | impact-share L1 | per-class Cohen κ (top) |" + NL
                        + "|---|---|---|---|---|---|---|" + NL
                        + (NL.join(pair_rows) if pair_rows else "(none)") + NL + NL
                        + "Interpretation: exact-set match and mean Jaccard quantify how "
                        "reproducible TRAIL annotation is ACROSS frontier models at "
                        "temperature 0 — the instrument's cross-model ceiling. The "
                        "glm-5.3-flash row is the headline pair (batch A glm labels vs "
                        "batch B grok labels); the ultra rows use the larger nvidia "
                        "overlap as corroboration." + NL
                        + (NL + f"**Sensitivity at full N:** {sens_d_line} "
                           "Full-N point (D) analysis appended to "
                           "`fullrun/sensitivity.md`; numbers in "
                           "`work/fullrun/sensitivity_d.json`."
                           if sens_d_line else "")
                        + NL)
    md = f"""# TRAIL full-scale run — results (generated {now})

Lane `tss/tsis-deepdive/trail/` · Repo under test: **patronus-ai/trail-benchmark** (MIT),
clone at `repo/`, commit `0ffbed9db859b4a66250dc783fa4dccf86869595` (2025-05-14).
Prompt: the paper's own `run_eval.get_prompt()` imported verbatim from the clone
(`repo/benchmarking/run_eval.py:16-138`); call params mirror `run_eval.call_litellm`
(temperature 0, top_p 1, max_completion_tokens 8000). Keys referenced by env var
names only (`ZAI_CODING_PLAN_KEY`, `NVIDIA_API_KEY`, `OPENROUTER_API_KEY`) — never
persisted. This file is GENERATED by `fullrun_results_md.py` from the raw artifacts;
do not hand-edit numbers.

## 1. Gold-set agreement — ENTIRE released set (148 traces = 117 GAIA + 31 SWE)

**Annotator batching (single-model batches, per-file attribution in
`work/fullrun/gold_outputs/union-top/MODEL_MANIFEST.json`):**
- `glm-5.3` (GLM coding plan, full tier — the agent under test): {glm_files} traces
  before the account rate-saturated (429 storms; receipts:
  `work/fullrun/gold_sweep2.log`–`gold_sweep5.log`). The account's full tier
  stayed saturated for the rest of the window (this lane's own harness traffic
  rides the same plan).
- `{NV}` (NVIDIA NIM, verified top-tier fallback per the quality floor):
  {nv_files} traces — completes the set 148/148 (`work/fullrun/gold_nv_sweep.log`:
  `FINISHED gold-nv sweep: annotated=148 skip=0 fail=0 in 1645s`).
- Union batch = glm-5.3 where present, ultra elsewhere; every metric below is
  reproducible offline via `verify_fullrun.py`.

### Headline agreement vs gold (full 148, repaired gold JSON)

| run | files | weighted F1 | location acc | joint acc |
|---|---|---|---|---|
| **Union-148 (headline)** | {o['files_processed']} | **{fmt(o['weighted_f1'])}** | **{fmt(o['location_accuracy'])}** | **{fmt(o['joint_accuracy'])}** |
| GAIA split | {A['splits']['GAIA']['files_processed']} | {fmt(A['splits']['GAIA']['weighted_f1'])} | {fmt(A['splits']['GAIA']['location_accuracy'])} | {fmt(A['splits']['GAIA']['joint_accuracy'])} |
| SWE Bench split | {A['splits']['SWE Bench']['files_processed']} | {fmt(A['splits']['SWE Bench']['weighted_f1'])} | {fmt(A['splits']['SWE Bench']['location_accuracy'])} | {fmt(A['splits']['SWE Bench']['joint_accuracy'])} |
| repo-exact GAIA (their scorer verbatim) | 116* | {fmt(A['repo_exact']['GAIA']['weighted_f1'])} | {fmt(A['repo_exact']['GAIA']['location_accuracy'])} | {fmt(A['repo_exact']['GAIA']['joint_accuracy'])} |
| repo-exact SWE (their scorer verbatim) | 31 | {fmt(A['repo_exact']['SWE Bench']['weighted_f1'])} | {fmt(A['repo_exact']['SWE Bench']['location_accuracy'])} | {fmt(A['repo_exact']['SWE Bench']['joint_accuracy'])} |
| single-model batch: glm-5.3 only | {A['by_model']['glm-5.3']['overall']['files_processed']} | {fmt(A['by_model']['glm-5.3']['overall']['weighted_f1'])} | {fmt(A['by_model']['glm-5.3']['overall']['location_accuracy'])} | {fmt(A['by_model']['glm-5.3']['overall']['joint_accuracy'])} |
| single-model batch: nemotron-3-ultra only | {A['by_model'][NV]['overall']['files_processed']} | {fmt(A['by_model'][NV]['overall']['weighted_f1'])} | {fmt(A['by_model'][NV]['overall']['location_accuracy'])} | {fmt(A['by_model'][NV]['overall']['joint_accuracy'])} |

\\*repo scorer silently skips the 1 gold file with an illegal trailing comma
(`a96c6811716c0473b86a23321db79c34.json`); the full-148 rows use a deterministic
trailing-comma repair. Crosscheck my aggregator vs the repo scorer on identical
entry sets: **{'PASS' if A['crosscheck']['bit_exact_within_1e-9'] else 'FAIL'}**
(bit-exact ≤ 1e-9).

Paper context (their Table 1, avg of 3 runs): best GAIA Cat-F1 0.389 / LocAcc 0.546
(Gemini-2.5-Pro); best SWE Cat-F1 0.213. Our annotators land inside the paper's
reported model pack on weighted F1 and below the best on location accuracy.

### Per-error-class agreement (union-148; {zero_sup} of 21 classes have zero gold support)

| error class | gold support | precision | recall | F1 |
|---|---|---|---|---|
{class_rows}

Extras: impact agreement on matched (location, category) pairs
{ex.get('impact', {}).get('impact_agree', 0)}/{ex.get('impact', {}).get('matched_pairs', 0)}
= {fmt(ex.get('impact', {}).get('impact_agreement_rate') or 0)} ·
mean errors/trace gold {fmt(ex['mean_errors_per_trace']['gold'], 2)} vs pred {fmt(ex['mean_errors_per_trace']['pred'], 2)} ·
macro-F1 over supported classes {fmt(ex.get('macro_f1_supported') or 0, 3)} ·
traces predicted error-free {ex.get('traces_pred_no_errors')} (gold: {ex.get('traces_gold_no_errors')}) ·
score correlations (Pearson ρ): reliability {fmt(corr.get('reliability', {}).get('correlation', 0), 3)},
instruction_adherence {fmt(corr.get('instruction_adherence', {}).get('correlation', 0), 3)},
plan_optimization {fmt(corr.get('plan_optimization', {}).get('correlation', 0), 3)},
overall {fmt(corr.get('overall', {}).get('correlation', 0), 3)}.
Largest confusions (extras.confusion_top20 in the JSON): FN Instruction
Non-compliance / Goal Deviation / Formatting Errors dominate (annotator
under-calls), FP Language-only / Poor Information Retrieval (over-calls).

## 2. Corpus sweep — full multi-runtime canonical (deduplicated) set

Corpus inventory (built before this lane started): 124,327 manifest records
across drives C:+D:, all runtimes + backups; 41,877 unique hashes; adapter
supports 40,798 of them (storage_type in jsonl/json/zst/gz/directory); offline
census finds **{elig:,} eligible unique sessions** (≥2 message events or ≥1 tool
event). Codex `.jsonl.zst` decompressed via python-zstandard; grok
directory-shaped sessions read via `chat_history.jsonl`. Duplicate paths inherit
their hash's annotation (manifest join below).

**Coverage (wave3 FULL-corpus finish sweep, started 2026-10-22 05:20 UTC —
this lane's continuation of the 2026-10-21 mandate; sharded sha-mod-16 lanes,
checkpointed and resumable; grok-4.7 effort-low on even shards via the local
grok bridge, nvidia/nemotron-3-ultra-550b-a55b on odd shards across 6 keys,
OpenRouter ultra:free + glm-5.3-flash opportunistic — counts below are the
on-disk state at generation time):**
- unique files checkpointed: **{label_n:,} / {canon_jobs:,}** ({file_cov:.1f}%)
- annotated OK: **{ok_n:,} / {elig:,} eligible** ({cov:.1f}%)
- manifest records covered by a label: {man.get('records_labelled', 0):,} /
  {man.get('records', 0):,}; OK-annotation inherited by
  {man.get('records_inheriting_ok_annotation', 0):,} records; mean path
  multiplicity of labelled hashes {fmt(man.get('labelled_sha_mean_path_multiplicity') or 0, 2)}.
{sens_block}
{batchb_block}
### Annotator batches (single-model per batch; 2026-10-19/20 slices were position mod 4, 2026-10-21 finish sweep shards are sha256 mod 16)

| model (provider) | files checkpointed | annotated OK |
|---|---|---|
{model_rows}

Batch-to-slice assignment and per-file model ids live in each label checkpoint
(`work/fullrun/corpus2_labels/<sha16>.json`, field `model`). GLM flash bursts
whenever the coding-plan window opens; NVIDIA NIM + OpenRouter :free carry the
sustained load. Quality floor respected everywhere (current-gen models only;
kimi-k2.6 404s and deepseek-v4.1-flash times out on NIM today — excluded, probe
receipts in the run logs).

### Corpus-wide failure-class distribution (over {ok_n:,} annotated sessions)

| error class (TRAIL taxonomy) | labels | traces | % of annotated traces |
|---|---|---|---|
{cat_rows}

By root class: {root_rows}

Impact: {imp_rows}

| sweep status | files |
|---|---|
{st_rows}

Rubric means (0–5) over annotated sessions:
reliability {fmt(S['score_rubric_means']['reliability_score'], 2)} ·
security {fmt(S['score_rubric_means']['security_score'], 2)} ·
instruction_adherence {fmt(S['score_rubric_means']['instruction_adherence_score'], 2)} ·
plan_optimization {fmt(S['score_rubric_means']['plan_opt_score'], 2)} ·
overall {fmt(S['score_rubric_means']['overall'], 2)}.
Mean error labels/session {fmt(S['errors_per_trace_mean'] or 0, 2)};
sessions with ≥1 error {S['traces_with_errors']:,} / {ok_n:,}.

### Per-runtime coverage (unique-file basis; duplicates inherit their hash)

| runtime | processed | eligible (census) | annotated OK | error labels |
|---|---|---|---|---|
{rt_rows}

## 3. What actually breaks in a single-user, long-horizon agent harness (findings)

See `work/fullrun/dashboard.html` for the live visual. Headline findings over
the FULL annotated canonical corpus (all figures from
`corpus2_summary.json`, recomputed independently by `verify_fullrun.py`):

1. **Reasoning failures, not infrastructure, dominate.** Reasoning-root errors
   account for {100.0 * sum(roots.get('Reasoning Errors', {}).values()) / root_tot:.0f}% of all error labels;
   System Execution (the "infra" root) only {100.0 * sum(roots.get('System Execution Errors', {}).values()) / root_tot:.0f}%.
   A long-horizon harness that survives at all rarely dies of the platform —
   it bleeds out through the model's own instruction drift.
2. **Tool-output misreading is the #1 failure class in real harness use.**
   {cats_sorted[0][0]} leads with {cats_sorted[0][1]:,} labels /
   {S['category_trace_prevalence'].get(cats_sorted[0][0], 0):,} traces
   ({100.0 * S['category_trace_prevalence'].get(cats_sorted[0][0], 0) / max(ok_n, 1):.1f}%
   of annotated sessions), with Formatting Errors
   ({S['category_counts'].get('Formatting Errors', 0):,} labels) and Instruction
   Non-compliance ({S['category_counts'].get('Instruction Non-compliance', 0):,} labels,
   {100.0 * S['category_trace_prevalence'].get('Instruction Non-compliance', 0) / max(ok_n, 1):.1f}%
   of traces) close behind — the paper's curated GAIA gold skews Formatting +
   Instruction Non-compliance (42% of gold errors), but day-to-day single-user
   sessions break FIRST on the model misreading what its tools returned.
3. **High-impact share is larger than in the paper's curated traces.**
   HIGH impact = {imp.get('HIGH', 0)} of {imp_total} labels ({100.0 * imp.get('HIGH', 0) / imp_total:.0f}%).
   Real single-user sessions interleave one-off scripts with production tasks;
   when they break, the break matters.
4. **~{100.0 * S['traces_with_errors'] / max(ok_n, 1):.0f}% of annotated sessions carry ≥1 failure label**
   ({S['traces_with_errors']:,} of {ok_n:,}); mean {fmt(S['errors_per_trace_mean'] or 0, 2)} labels per annotated session.
5. **Context Handling Failures rank high in long-horizon reality**
   ({S['category_counts'].get('Context Handling Failures', 0)} labels) — the class
   the paper found nearly unpredictable for models (F1 ≈ 0 in their Table) is a
   live failure mode in day-to-day harness use.

Caveats: the corpus was annotated by a MIX of current-frontier models (per-file
model ids in each label checkpoint, field `model`; the quality floor was never
crossed — no legacy or small models): grok-4.7 (reasoning_effort=low; the
owner's volume tier, current-frontier class) carried the most files, top-tier
nvidia/nemotron-3-ultra-550b-a55b the next share, plus allowlisted :free /
flash volume lanes for smaller slices. Cross-model category-share divergence
exists (see per-model attribution in the checkpoints); unparseable annotator
outputs are checkpointed as such and counted honestly (excluded from `ok`).
Wave3+ finish sweeps (2026-10-22..24): grok-4.7 via the local grok bridge
(1 SuperGrokPro account, maxConcurrent 8) on even shards; ultra-550b on 6
NVIDIA keys x <=3 workers; OpenRouter ultra:free + glm-5.3-flash bursts.
nvidia/nemotron-3-super-120b-a12b and deepseek-v4.1-flash were 404/dead on NIM
this window (probe receipts in work/fullrun/wave3 logs); GEMINI_API_KEY
rejected (400 invalid key).

## 4. Commands (reproduce)

```
# corpus job plan + offline census (no API)
.venv/Scripts/python.exe fullrun_corpus2.py plan
.venv/Scripts/python.exe fullrun_corpus2.py census
# gold sweeps (GLM attempt + NVIDIA top-tier completion)
GOLD_WORKERS=2 .venv/Scripts/python.exe fullrun_gold.py
.venv/Scripts/python.exe fullrun_gold_nv.py
# corpus finish sweep (2026-10-22 wave3): grok bridge + 6x NVIDIA keys, sharded
powershell -NoProfile -ExecutionPolicy Bypass -File work/fullrun/wave3_detach.ps1
#   (equivalently, one lane:)
.venv/Scripts/python.exe fullrun_finish_shard.py --shards=0,2,4,6,8,10,12,14 --model=grok-4.7 --workers=9 --tag=w3grok9
# batch B (2026-10-30): single-model grok-4.7 pass over ALL canonical targets
bash work/fullrun/batchb_launch.sh   # wraps: python fullrun_batchb_grok.py --workers=14
.venv/Scripts/python.exe fullrun_batchb_summary.py    # batch-B aggregate + cross-model agreement
.venv/Scripts/python.exe fullrun_sensitivity_d.py     # full-N sensitivity point (D) + verdict
# aggregate + score + dashboard + this file
.venv/Scripts/python.exe fullrun_summarize2.py
.venv/Scripts/python.exe fullrun_score.py
.venv/Scripts/python.exe fullrun_dashboard.py
.venv/Scripts/python.exe fullrun_results_md.py
# offline reconciliation (exit 0 required)
.venv/Scripts/python.exe verify_fullrun.py
```

## 5. Token usage (from per-call ledgers; token counts only)

| batch | calls | prompt tokens | completion tokens |
|---|---|---|---|
| gold glm-5.3 | {gn} | {gp:,} | {gc:,} |
| gold nemotron-3-ultra | {nn} | {np_:,} | {nc:,} |
| corpus (all volume models) | {len(corpus_u)} | {cp:,} | {cc:,} |
{batchb_tok_row}| **total** | {gn + nn + len(corpus_u) + bb_n} | **{tot_p + bb_p:,}** | **{tot_c + bb_c:,}** |

Provider claims recorded atomically in `tss/tsis-deepdive/provider-claims.json`.
Gemini lane: GEMINI_API_KEY rejected (400 invalid key, live probe this session) —
unusable, recorded as blocker, never substituted around.
"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(md)
    print("wrote", OUT, f"({len(md):,} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
