# TRAIL chunked / hierarchical judge — full-148 gold evaluation (2026-10-31)

Generated from raw artifacts by hand this session; numbers reproducible via
`fullrun_hier_score.py` (writes `work/fullrun/hier_agreement.json`). Do not hand-edit.

- Lane `tsis/agent-evaluation/trail/`. Repo under test: patronus-ai/trail-benchmark
  (MIT), clone at `repo/`, same clone the flat runs used.
- Judge model: **grok-4.7, reasoning_effort `xhigh`**, via the local bridge
  `http://127.0.0.1:8182/v1`, key from env `GROK_LANE_KEY` (live-probe receipt this
  session: `xhigh -> 'OK' usage pt/ct: 3341/41`).
- Gold set: the SAME 148 released traces (117 GAIA + 31 SWE Bench) the flat judge
  scored (`repo/benchmarking/data/{GAIA,SWE Bench}`), against the same gold
  annotation dirs.
- Scorer: the SAME code path as the flat gold run — `fullrun_score.collect` +
  `fullrun_score.aggregate` (replicates repo `calculate_scores.main()`; that
  replication was crosschecked bit-exact ≤1e-9 vs the repo scorer in the flat run)
  plus repo-exact `calculate_scores.main()` itself per split.

## 1. Method

Implemented in `fullrun_hier_judge.py` (checkpointed, resumable; every call in the
`work/fullrun/hier_meta.jsonl` + `work/fullrun/usage/hier.jsonl` ledgers).

**Stage 0 — linearize.** Each trace JSON is walked in span-tree DFS order and
collapsed to message UNITS: one unit per LLM span (its `llm.output_messages`
assistant output, plus the newest non-system input message capped at 2,500 chars
as triggering context) and one unit per TOOL span (name + `input.value` +
`output.value`). Rationale, measured this session on the gold annotations
(`_hier_design_check.py`): gold error locations are anchored on 744 LLM + 95 TOOL
+ 2 non-span locations, so LLM+TOOL units are exactly the citable location space.
Mean 18.2 units/trace GAIA (max 121), 15.8 SWE (max 28).

**Stage 1 — window judging.** Windows of **WINDOW=15 units, STRIDE=10** (5-unit
overlap; ~15-message windows per the ask). 285 windows over 148 traces
(mean 1.93/trace, max 12; 52 traces have >1 window). Each window payload carries
the FULL text of its units (per-unit cap 12,000 chars — measured unit p99 is
5,576 chars, so truncation is rare), a global header (task text ≤4,000 chars +
the full unit-index table with span ids), and window ground rules (paper taxonomy
verbatim from `run_eval.get_prompt` imported unmodified; only the window
framing, JSON-only output contract, and first-instance/Resource-Abuse-last
location rules are added). Prompt sizes ≤68,320 chars (max measured). The judge
response is parsed with the repo's own `extract_json_from_text` shrink-repair
logic; any error whose `location` is not a span id printed in that window is
dropped mechanically.

**Stage 2 — chunk votes.** Union of window verdicts; exact (location, category)
pairs are deduplicated and stamped with `votes` = number of windows reporting
them (overlap regions are judged twice). 1,206 candidates total, 8.15/trace mean.

**Stage 3 — reconciliation pass.** One call per trace over task + unit index +
all candidates (category, location, unit, votes, evidence, description, impact):
merge overlap duplicates applying the paper's global first-instance rule
(Resource Abuse → last), drop unsupported candidates, do not add new ones, and
emit the final paper-template JSON `{"errors": [...], "scores": [...]}`. Output
files land in `work/fullrun/hier_outputs/grok-4.7-xhigh/final/<split>/<fname>`,
the same text format the flat runs used. 1,048 final errors (7.08/trace vs gold
5.68) — reconciliation dropped 13% of candidates. 0 fallbacks, 0 skipped files,
285/285 windows parsed OK.

Call params mirror `run_eval.call_litellm` / the flat pipeline (temperature 0,
top_p 1, max_completion_tokens 8000) with `reasoning_effort=xhigh` per the ask.
Totals: 433 calls (285 chunk + 148 recon), 6.04M prompt + 4.13M completion
tokens = **10.17M tokens (68.7K/trace)**.

**Controls.** Two baselines:

- **Flat (paper artifact, different model)** — the existing Union-148 run
  (`glm-5.3` 33 traces + `nvidia/nemotron-3-ultra-550b` 115; the 0.0905 joint
  figure named in the ask), numbers from its own artifact
  `work/fullrun/gold_agreement.json`.
- **Flat control (SAME model+effort)** — `fullrun_hier_flatctl.py`: the paper's
  flat one-shot prompt verbatim + the flat run's exact capping ladder
  (`fullrun_common.render_capped`, 160,000-char budget as in `fullrun_gold.py`),
  grok-4.7 xhigh, all 148 traces. This isolates the architecture effect from the
  model effect. Totals: 148 calls, 6.29M tokens (42.5K/trace).

## 2. Flat vs hierarchical — full 148 gold traces

| judge | model | calls/trace | tokens/trace | files | weighted F1 | location acc | joint acc |
|---|---|---|---|---|---|---|---|
| Flat (paper artifact) | glm-5.3 / nemotron-ultra mix | 1 | — | 148 | 0.3683 | 0.2472 | **0.0905** |
| Flat control | grok-4.7 xhigh | 1 | 42.5K | 148 | **0.4920** | 0.3858 | 0.2065 |
| **Hierarchical (this work)** | grok-4.7 xhigh | 2.93 | 68.7K | 148 | 0.4489 | **0.5406** | **0.2190** |

Per split (weighted F1 / location / joint):

| split | flat glm/ultra | flat grok-4.7 xhigh | hierarchical grok-4.7 xhigh |
|---|---|---|---|
| GAIA (117) | 0.3697 / 0.3104 / 0.1145 | 0.5081 / 0.4616 / 0.2612 | 0.4667 / **0.6376** / **0.2689** |
| SWE Bench (31) | 0.3057 / 0.0086 / 0.0000 | 0.3888 / 0.0998 / 0.0000 | 0.4018 / **0.1743** / **0.0308** |

Repo-exact crosscheck (repo scorer verbatim; GAIA processes 116 files — it
silently skips the one gold file with an illegal trailing comma, the flat run's
documented behaviour): GAIA 0.4661 / 0.6373 / 0.2695; SWE 0.4018 / 0.1743 /
0.0308 — matching my aggregator's 148-file numbers to ~1e-3 (difference is the
repaired 148th file plus the repo skip), same relationship as the flat table.

**Paired significance, hierarchical vs flat control (same model; n=148,
Wilcoxon signed-rank, computed this session):**

| metric | flat ctl mean | hier mean | mean diff | p | hier better / worse |
|---|---|---|---|---|---|
| location accuracy | 0.3858 | 0.5406 | +0.1547 | **1.1e-08** | 65 / 9 |
| joint accuracy | 0.2065 | 0.2190 | +0.0125 | 0.80 | 40 / 25 |
| per-file weighted F1 | 0.5267 | 0.5207 | −0.0060 | 0.43 | 36 / 47 |

Other diagnostics: mean predicted errors/trace — flat-glm/ultra 3.20, flat grok
4.74, hier 7.08 (gold 5.68); traces predicted error-free — 17 / 7 / 0 (gold 4);
impact agreement on matched (location, category) pairs — flat 45/58 = 0.776,
hier 115/152 = 0.757 (the hierarchical judge produces 2.6× more matched pairs);
macro-F1 over supported classes: hier 0.391 (flat glm/ultra 0.297); score
correlations (Pearson ρ) hier: reliability 0.593, instruction_adherence 0.306,
plan_optimization 0.423, overall 0.573. Largest hier confusions: FP Tool Output
Misinterpretation (73), FP Language-only (68), FP Instruction Non-compliance
(55); FN Resource Abuse (35). Best per-class F1: Goal Deviation 0.713
(recall 0.875), Formatting Errors 0.663 (recall 0.784), Language-only 0.543
(recall 0.880).

## 3. Honest verdict

**Chunking does not fix TRAIL's category agreement; it fixes location — and most
of the headline gain over the 0.0905 baseline is the model, not the
architecture.**

1. **The 0.0905 → 0.2190 joint-accuracy jump is ~93% model effect.** The same
   grok-4.7 at xhigh with the paper's flat prompt and the flat capping ladder
   already reaches 0.2065 joint — 2.3× the glm/ultra flat artifact — without any
   chunking. The hierarchical architecture adds +0.0125 joint on top, which is
   not statistically significant (Wilcoxon p=0.80, n=148).
2. **The architecture effect is real but specific: location.** +0.155 mean
   location accuracy (0.3858 → 0.5406, +40% relative), p=1.1e-08, better on 65
   of 148 files, worse on 9. Mechanism is visible in the design: window payloads
   carry near-full unit text (12K/unit cap vs the flat ladder's 160K total budget
   that skeletonizes the middle 60% of spans at L3+), and every window error is
   mechanically constrained to a span id actually shown in that window.
3. **SWE Bench is where chunking helps most** — it is the only configuration of
   the three with non-zero SWE joint accuracy (0.0308 vs 0.0000 for both flat
   runs) and location accuracy 0.1743 vs 0.0086/0.0998. SWE traces are the
   largest (median 1.58 MB) and are destroyed worst by flat capping.
4. **The cost is over-prediction.** Windows surface more candidate errors
   (7.08/trace predicted vs 5.68 gold), and the reconciliation pass drops only
   13% of them, so weighted F1 drops 0.4920 → 0.4489 (per-file n.s., p=0.43, but
   pooled −8.8% relative). FP-heavy confusions (Tool Output Misinterpretation,
   Language-only) dominate. A stricter reconciliation (e.g. votes≥2 for
   single-window candidates) is the obvious next knob — not tuned here to keep
   this an honest single-shot evaluation.
5. **Price:** 2.93 calls and 1.62× tokens per trace vs the flat control
   (68.7K vs 42.5K tokens/trace).

Paper context: the best reported GAIA judge in the paper's Table 1 (Gemini-2.5-
Pro, avg of 3 runs) reached Cat-F1 0.389 / LocAcc 0.546. The hierarchical judge's
GAIA location accuracy 0.6376 exceeds that; its GAIA weighted F1 0.4667 exceeds
the paper's best reported Cat-F1. This is a model+architecture confound against
the paper's numbers (their models and capping differ) — stated, not claimed as
a like-for-like win.

## 4. Operational record (honesty section)

- The local grok bridge's billing-ledger subsystem flapped repeatedly during the
  run (every ~15–30 min under load: `计费账本暂不可用`, receipts in
  `work/fullrun/hier_sweep2.log`…`hier_sweep6.log`). Mitigations, in order:
  no-checkpoint-on-error + retry sweeps, a `/readyz` gate before every sweep
  (`_wait_bridge_ready` in `fullrun_hier_judge.py`), and finally a restart of the
  bridge via the owner-documented scripts (`/d/opt/grok-lane/stop-grok-lane.sh`
  + `start-grok-lane.sh` after the start script itself reported the port was
  held by an untracked stale instance, pid 8024). One restart attempt produced a
  silently wedged instance (no log output, no port bind for 13 min); killed and
  restarted once more per the same documented procedure — came up healthy
  (`healthy: {"ok":true}`) and served the rest of the run.
- A mid-run session interruption (~12 h gap, 03:53Z → 16:36Z) killed the sweep
  process; all work was checkpointed and the relaunch resumed from 147/285
  windows with zero re-annotation.
- Every grok call went through `fullrun_common.annotate`'s 429-jitter requeue
  (2–5 s, per the lane's standing directive); no provider substitution was made
  at any point — the run is single-model (grok-4.7 xhigh, 433/433 calls + 148
  control calls, model id recorded per record in the meta ledger).

## 5. Commands (reproduce)

```
# smoke + full hierarchical run (285 windows + 148 reconciliation, resumable)
HIER_WORKERS=7 .venv/Scripts/python.exe fullrun_hier_judge.py all
# flat control (paper flat prompt + flat capping ladder, same model/effort)
HIER_WORKERS=7 .venv/Scripts/python.exe fullrun_hier_flatctl.py
# score BOTH against the 148 gold traces with the flat run's scorer functions
.venv/Scripts/python.exe fullrun_hier_score.py
#    -> work/fullrun/hier_agreement.json  (this file's tables)
# paired Wilcoxon hier-vs-control (as computed for §2):
#    inline script over FS.collect/CS.calculate_metrics per file, scipy.stats.wilcoxon
```

Raw artifacts: window verdicts `work/fullrun/hier_outputs/grok-4.7-xhigh/chunks/`,
final verdicts `.../final/`, flat control `work/fullrun/hier_outputs/grok-4.7-xhigh-flat/`,
call+usage ledgers `work/fullrun/hier_meta.jsonl`, `work/fullrun/usage/hier.jsonl`,
sweep logs `work/fullrun/hier_sweep1..6.log`, `work/fullrun/hier_flatctl.log`.
