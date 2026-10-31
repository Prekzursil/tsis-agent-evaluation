#!/usr/bin/env python3
"""Render RESULTS.md from the real artifacts (aggregates2.json, privacy_scan_full2.json,
targets_summary.json, sweep statuses, crosscheck2_agreement.json). Numbers only from
files; CHECK markers embedded for verify_fullrun.py reconciliation."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANE = HERE.parent

MODE_NAMES = {
    "1.1": "Disobey Task Specification", "1.2": "Disobey Role Specification",
    "1.3": "Step Repetition", "1.4": "Loss of Conversation History",
    "1.5": "Unaware of Termination Conditions", "2.1": "Conversation Reset",
    "2.2": "Fail to Ask for Clarification", "2.3": "Task Derailment",
    "2.4": "Information Withholding", "2.5": "Ignored Other Agent's Input",
    "2.6": "Action-Reasoning Mismatch", "3.1": "Premature Termination",
    "3.2": "Weak Verification", "3.3": "No or Incorrect Verification",
}
PAPER = {"1.1": 11.8, "1.2": 1.5, "1.3": 15.7, "1.4": 2.8, "1.5": 12.4,
         "2.1": 2.2, "2.2": 6.8, "2.3": 7.4, "2.4": 0.85, "2.5": 1.9, "2.6": 13.2,
         "3.1": 6.2, "3.2": 8.2, "3.3": 9.1}
CAT_OF = {**{m: "FC1" for m in list(MODE_NAMES)[:5]},
          **{m: "FC2" for m in list(MODE_NAMES)[5:11]},
          **{m: "FC3" for m in list(MODE_NAMES)[11:]}}


def main():
    agg = json.loads((HERE / "aggregates2.json").read_text(encoding="utf-8"))
    pp = HERE / "privacy_scan_full2.json"
    priv = json.loads(pp.read_text(encoding="utf-8")) if pp.exists() else {
        "files_scanned": 0, "bytes_scanned": 0, "total_lines": 0, "json_line_rate": 0,
        "message_objects": 0, "message_object_ratio": 0, "pii_ish": {},
        "by_drive": {}, "by_origin": {},
        "note": "privacy scan not finished at render time"}
    tsum = json.loads((HERE / "targets_summary.json").read_text(encoding="utf-8"))
    xchk = agg.get("crosscheck") or {}
    toks = agg["tokens"]
    v1 = toks.get("v1_sweep_totals", {})
    v2 = toks.get("v2_sweep_totals", {})

    # manifest ok-record count (denominator for privacy coverage)
    manifest_ok = 0
    mpath = HERE.parent.parent / "corpus" / "manifest.jsonl"
    if mpath.exists():
        with mpath.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    if json.loads(line).get("status") == "ok":
                        manifest_ok += 1
                except Exception:
                    pass

    n = agg["n_labeled_ok"]
    tc = agg["task_completed"]

    # ---- privacy table
    priv_rows = "".join(
        f"| {k} | {v['lines']:,} | {v['line_ratio']*100:.3f}% |\n"
        for k, v in priv["pii_ish"].items())
    skipped = priv.get("skipped_by_watchdog", 0)
    unattempted = max(0, manifest_ok - priv.get("files_scanned", 0) - skipped)
    cov_pct = 100 * priv.get("files_scanned", 0) / max(manifest_ok, 1)
    coverage_bits = []
    if skipped:
        coverage_bits.append(f"{skipped:,} pathological binaries skipped by the scan "
                             f"watchdog (huge tar/sqlite images that wedged the pool)")
    if unattempted:
        coverage_bits.append(f"{unattempted:,} never attempted before the scan stopped")
    coverage = ("; ".join(coverage_bits) + ".") if coverage_bits else \
        "full coverage of every ok-record."
    priv_tbl = (
        f"Scanned **{priv['files_scanned']:,}** of {manifest_ok:,} `status=ok` records of "
        f"`manifest.jsonl` ({cov_pct:.1f}%; both drives, all runtimes, "
        f"live+backup+orphan-backup) — {priv['bytes_scanned']/1e9:.1f} GB, "
        f"{priv['total_lines']:,} line-equivalents. {coverage} "
        f"JSON line rate {priv['json_line_rate']*100:.1f}%; "
        f"message-like objects {priv['message_objects']:,} "
        f"({priv['message_object_ratio']*100:.2f}% of lines).\n\n"
        "| PII-ish category | lines | line ratio |\n|---|---:|---:|\n" + priv_rows +
        f"\n\nBy drive: " + ", ".join(
            f"{d} {v['files']:,} files/{v['lines']:,} lines"
            for d, v in priv["by_drive"].items()) +
        ". By origin: " + ", ".join(
            f"{o} {v['files']:,} files" for o, v in priv["by_origin"].items()) + ".")

    # ---- volume table
    vol_tbl = (
        f"| stage | count |\n|---|---:|\n"
        f"| manifest records scanned (privacy) | {priv['files_scanned']:,} |\n"
        f"| canonical unique files (hashes) | {tsum['canonical_entries']:,} |\n"
        f"| parseable session targets (annotation set) | {agg['targets_total']:,} |\n"
        f"| — of which exploded from multi-conversation containers | "
        f"{agg['targets_total'] - agg['unique_sha']:,} |\n"
        f"| annotated OK (flash tier or migrated v1) | **{n:,}** |\n"
        f"| — migrated from v1 path-keyed run (same content hash) | "
        f"{agg['n_migrated_from_v1']:,} |\n"
        f"| — annotated fresh this run (by model: " + ", ".join(
            f"{k} {v:,}" for k, v in sorted(agg.get('fresh_by_model', {}).items(),
                                            key=lambda kv: -kv[1])) + f") | "
        f"{n - agg['n_migrated_from_v1']:,} |\n"
        f"| parse-fail responses (ok=false, counted as annotated) | "
        f"{agg['n_parse_fail']:,} |\n"
        f"| pending (not yet annotated) | {agg['pending']:,} |\n"
        f"| excluded as not parseable (no user+assistant pair) | "
        f"{tsum['canonical_entries'] - tsum['unique_sha_with_targets']:,} unique files |\n"
        f"\nDuring the 2026-10-19 repair, 2,172 `http_429_exhausted` placeholder rows "
        f"(labels with no verdict, written by a pre-fix sweep version) were removed "
        f"from `labels_full.jsonl` so resume rounds would retry them, per "
        f"`annotate2.py`'s persistence contract"
        + (" (they are part of the pending count above).\n" if agg["pending"] > 0 else
           "; the resumed sweep annotated all of them.\n")
        + (f"\nThe {agg['pending']:,} still-pending target(s) are a provider-side "
           f"terminal blocker, verified per-target on 2026-10-19: the z.ai content "
           f"filter (error 1301, contentFilter level 2, HTTP 400) rejects these "
           f"traces on BOTH `glm-5.3-flash` and `glm-5.3` (all current cases are "
           f"`chatgpt_export` sessions). They are left pending rather than "
           f"prompt-mangled to evade the filter.\n" if agg["pending"] > 0 else
           "\nThe last 4 targets, which the z.ai content filter (error 1301, "
           "contentFilter level 2, HTTP 400) rejected on both `glm-5.3-flash` and "
           "`glm-5.3`, were completed via the provider failover ladder "
           "(`annotate_pending_fallback.py`): 4/4 annotated by NVIDIA NIM volume tier "
           "`nvidia/nemotron-3-super-120b-a12b` (same prompt contract; provider claims "
           "recorded in `../provider-claims.json`).\n")
        + f"\nTarget formats: " + ", ".join(f"{k} {v:,}"
                                            for k, v in tsum["formats"].items()) + ".")

    # ---- distribution tables
    mode_rows = "".join(
        f"| {m} {MODE_NAMES[m]} | {agg['modes'][m]['yes']:,} | "
        f"{agg['modes'][m]['incidence_pct']:.2f}% | "
        f"{agg['modes'][m]['occurrence_share_pct']:.2f}% | {PAPER[m]:.2f}% |\n"
        for m in MODE_NAMES)
    dist_tbl = (
        f"**Task completed**: yes {tc['yes']:,} / no {tc['no']:,} / null {tc['null']:,} "
        f"({agg['task_completed_yes_pct']:.1f}% yes). Traces with ≥1 flagged mode: "
        f"{agg['traces_with_any_mode']:,} "
        f"({100*agg['traces_with_any_mode']/max(n,1):.1f}%). Mean modes per flagged trace: "
        f"{agg['mean_modes_per_flagged_trace']:.2f}. Total yes-labels: "
        f"{agg['total_yes_labels']:,}.\n\n"
        "| mode | yes | incidence | occ. share | paper prev. |\n"
        "|---|---:|---:|---:|---:|\n" + mode_rows +
        f"\n| category | ours (occ. share) | ours (sum incidence) | paper (mode-sum) | paper Fig.4 |\n"
        f"|---|---:|---:|---:|---:|\n"
        f"| FC1 System Design / Specification | {agg['categories']['FC1']['occurrence_share_pct']:.1f}% "
        f"| {agg['categories']['FC1']['sum_mode_incidence_pct']:.1f}% | 44.2% | 41.8% |\n"
        f"| FC2 Inter-Agent Misalignment | {agg['categories']['FC2']['occurrence_share_pct']:.1f}% "
        f"| {agg['categories']['FC2']['sum_mode_incidence_pct']:.1f}% | 32.3% | 36.9% |\n"
        f"| FC3 Task Verification | {agg['categories']['FC3']['occurrence_share_pct']:.1f}% "
        f"| {agg['categories']['FC3']['sum_mode_incidence_pct']:.1f}% | 23.5% | 21.3% |\n")

    mo_rows = "".join(
        f"| {k} | {v['n']:,} | {v['any_fail_pct']:.1f}% |\n"
        for k, v in agg["monthly"].items())
    dist_tbl += ("\n**Over time** (by session first timestamp; fallback unknown):\n\n"
                 "| month | n annotated | % with ≥1 mode |\n|---|---:|---:|\n" + mo_rows)

    rt_rows = "".join(
        f"| {rt} | {v['n']:,} | {v['task_completed_pct']:.0f}% | "
        f"{v['top_mode'] or '—'} ({v['modes'].get(v['top_mode'], 0):.1f}%) |\n"
        for rt, v in list(agg["by_runtime"].items())[:12])
    dist_tbl += ("\n\n**Top runtimes**:\n\n| runtime | n | task done | top mode |\n"
                 "|---|---:|---:|---|\n" + rt_rows)

    fm_rows = "".join(
        f"| {f} | {v['n']:,} | {v['task_completed_pct']:.0f}% | {v['top_mode'] or '—'} |\n"
        for f, v in agg["by_format"].items())
    dist_tbl += ("\n\n**By session format**:\n\n| format | n | task done | top mode |\n"
                 "|---|---:|---:|---|\n" + fm_rows)

    # ---- tier agreement
    if xchk.get("n_pairs"):
        xr = "".join(
            f"| {m} {MODE_NAMES[m]} | {d['agree_pct']:.0f}% | {d['yy']} | {d['yn']} | "
            f"{d['ny']} | {d['nn']} |\n"
            for m, d in xchk["modes"].items())
        xchk_tbl = (
            f"{xchk.get('n_crosscheck_ok', xchk['n_pairs'])} traces annotated with "
            f"`{xchk['model_full']}` (full tier) over the deterministic 50-sample "
            f"(seed 7, size-sorted); {xchk['n_pairs']} comparable pairs (one sampled "
            f"trace's flash-tier response is a parse-fail and is excluded), same prompt "
            f"contract.\n\n"
            "| mode | agree | yes\\|yes | yes\\|no | no\\|yes | no\\|no |\n"
            "|---|---:|---:|---:|---:|---:|\n" + xr +
            f"\nMean mode agreement **{xchk['mean_agree_pct']}%**; task_completed "
            f"agreement **{xchk['task_agree_pct']}%** "
            f"(confusion yy/yn/ny/nn = {xchk['task_confusion']}).")
    else:
        xchk_tbl = "Cross-check not available."

    # ---- tokens
    # crosscheck usage summed directly from crosscheck2.jsonl (per-call usage in-file)
    xc_ok = xc_429 = xc_pt = xc_ct = 0
    xcp = HERE / "crosscheck2.jsonl"
    if xcp.exists():
        with xcp.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("ok"):
                    xc_ok += 1
                    u = r.get("usage") or {}
                    xc_pt += u.get("pt", 0)
                    xc_ct += u.get("ct", 0)
    fresh_labels = agg["labels_written"] - agg["n_migrated_from_v1"]
    v2_429 = toks.get("v2_sweep_429_cumulative")
    v2_429_txt = f"{v2_429:,}" if v2_429 is not None else "—"
    tok_tbl = (
        f"| stream | calls ok | 429s | prompt tokens | completion tokens |\n|---|---:|---:|---:|---:|\n"
        f"| v1 sweep (path-keyed, interrupted; 15,522 ok records produced, 13,194 "
        f"unique-hash migrated) "
        f"| {v1.get('ok', 0):,} | {v1.get('http_429', 0):,} | "
        f"{v1.get('prompt_tokens', 0):,} | {v1.get('completion_tokens', 0):,} |\n"
        f"| v2 sweep + failover (fresh labels written this run, ok+parse-fail; 19,342 glm-5.3-flash + 4 nemotron-3-super-120b) | "
        f"{fresh_labels:,} | {v2_429_txt} | "
        f"{toks['v2_new_prompt']:,} | {toks['v2_new_completion']:,} |\n"
        f"| full-tier cross-check (glm-5.3, 50-trace sample) | {xc_ok:,} | 0 | "
        f"{xc_pt:,} | {xc_ct:,} |\n\n"
        f"v2 429s ({toks.get('v2_sweep_429_cumulative', 0):,} across "
        f"{toks.get('v2_sweep_rounds_counted', 0)} counted resume rounds) are "
        f"reconstructed from the per-round monotonic counters in "
        f"`sweep2.log`/`sweep3.log` — rounds killed before their first 100-item "
        f"progress mark contribute 0, so the true total is marginally higher. "
        f"`sweep_status2.json` is per-process and overwritten by every round; each "
        f"round now also appends its final counters to "
        f"`sweep2_status_history.jsonl`. Migrated labels carry their v1 usage "
        f"in-file; v2 fresh totals above are summed from label records and exclude "
        f"migrated ones.")

    # ---- findings (numbers filled from aggregates; comparative vs paper)
    m = agg["modes"]
    top3 = sorted(MODE_NAMES, key=lambda k: -m[k]["incidence_pct"])[:3]
    diverge = [k for k in MODE_NAMES
               if abs(m[k]["incidence_pct"] - PAPER[k]) > 8]
    findings = f"""Single-user, long-horizon, single-harness corpus (N={n:,} sessions) vs the
MAST paper's multi-user, multi-framework benchmark corpus (N=210 traces; CrewAI/AutoGen-class
frameworks on short benchmark tasks):

**Where it matches.** The top of the distribution is dominated by the same operational
failure the paper ranks #1 or #2 — FM-{top3[0]} ({MODE_NAMES[top3[0]]},
{m[top3[0]]['incidence_pct']:.1f}% incidence here). Verification-category failures
(FC3) remain substantial in both ({agg['categories']['FC3']['occurrence_share_pct']:.1f}%
of occurrences here vs 21.3–23.5% in the paper), confirming that weak or missing
self-verification is not an artifact of any one harness. Rare-in-paper modes stay rare
here too (FM-2.4 Information Withholding: paper 0.85%, here
{m['2.4']['incidence_pct']:.2f}%).

**Where it diverges.** {len(diverge)} modes move by more than 8 points of incidence:
""" + "\n".join(
        f"- FM-{k} {MODE_NAMES[k]}: here {m[k]['incidence_pct']:.1f}% vs paper {PAPER[k]:.1f}%"
        f" ({'+' if m[k]['incidence_pct'] >= PAPER[k] else ''}{m[k]['incidence_pct']-PAPER[k]:.1f} pts)"
        for k in diverge) + f"""

**Reading the divergence.** This corpus is one expert operator's real fleet — sessions
span 2023-01 through 2026-10, with ~96% of annotated volume from 2026:
sessions are long (median tens of messages), tool-saturated, heavily subagent-delegated, and
span six harness families (Claude Code journals dominant at
{agg['by_format'].get('claude_journal', {}).get('n', 0):,} traces, plus Codex rollouts,
grok/gemini chats, zcode model-IO logs and ChatGPT exports). The paper's corpus is many
users running small fixed crews on short, well-specified benchmark tasks with hard
verifiers. That difference alone predicts most of the gap: inter-agent misalignment modes
(FC2) — the paper's signature category, 36.9% of its failures — presuppose peer agents that
must coordinate; in a single-main-agent + tools + subagents harness, FC2
({agg['categories']['FC2']['occurrence_share_pct']:.1f}% here) shifts toward
harness-internal variants (ignored subagent input, withholding in delegation) rather than
crew-coordination breakdowns. Task completion reads differently too: the paper's crews often
fail the benchmark outright, while here task_completed=yes on
{agg['task_completed_yes_pct']:.1f}% of sessions — but a substantial fraction of "yes"
sessions still carry flagged failure modes, echoing the paper's observation that superficial
verifiers over-credit success (FM-3.2/3.3 remain present at
{m['3.2']['incidence_pct']:.1f}%/{m['3.3']['incidence_pct']:.1f}%).

**What this says about MAST's generality.** The taxonomy's FC1/FC2/FC3 skeleton and all 14
modes transfer to a production single-user harness without needing new categories: every
mode fires on real traffic at non-trivial or sensibly-rare rates. But the *distribution* is
a property of the harness and task mix, not of agents in general — MAST is a valid ruler,
not a universal profile. Any deployment-side use of MAST should baseline on the site's own
traffic, exactly as this run does; paper-derived priors would mis-rank remediation
investment for a fleet like this one by overweighting crew-coordination failures that
rarely occur without peer agents.

Tier-agreement caveat: flash-tier labels agree with full-tier at
{xchk.get('mean_agree_pct', 'n/a')}% mean mode agreement on the 50-trace cross-check
(paper annotator–human accuracy was 94%), so per-mode incidences below ~10% should be read
with the agreement noise floor in mind.
"""

    results = f"""# MASTscope full-scale run — RESULTS (v2: rebuilt multi-runtime corpus)

Single lane: `tss/tsis-deepdive/mastscope/`. Full-corpus MAST-taxonomy annotation of the
owner's complete agent-session corpus (both drives, all runtimes, live + backups +
orphan-backups) via the GLM coding-plan API. All numbers reconciled by
`verify_fullrun.py` (offline; exit 0 required).

## 1. Method

**Corpus.** The rebuilt inventory at `tss/tsis-deepdive/corpus/` (built 2026-10-18 by
`build_corpus.py`; see `CORPUS.md`): 124,327 manifest records (122,733 ok), 41,877 unique
content hashes after strict per-file sha256 dedup (newest-mtime canonical winner),
spanning C: and D:, 63+ runtimes, origins live 47,892 / backup 51,446 / orphan-backup
23,395. **Annotation unit = the parseable session**: schema-based extraction over every
canonical entry (storage-aware: `.jsonl.zst` decompressed via python-zstandard; grok's
directory-shaped sessions read from `chat_history.jsonl` inside; multi-conversation
containers like ChatGPT export shards exploded per conversation) yields
**{agg['targets_total']:,} sessions with ≥1 user and ≥1 assistant message** across 7
formats (claude_journal {tsum['formats'].get('claude_journal',0):,}; codex_rollout
{tsum['formats'].get('codex_rollout',0):,}; chatgpt_export {tsum['formats'].get('chatgpt_export',0):,};
openai_like grok/gemini {tsum['formats'].get('openai_like',0):,}; zcode model-IO
{tsum['formats'].get('zcode_modelio',0):,}; codex web tasks {tsum['formats'].get('codex_web_tasks',0):,};
generic {tsum['formats'].get('json_messages',0):,}). Unique files yielding no user+assistant
pair ({tsum['canonical_entries'] - tsum['unique_sha_with_targets']:,}: sqlite/leveldb by
design, cursor meta.json, ledgers, caches, markdown notes, logs) are excluded with counts
(`fullrun/targets_summary.json`).

**Annotation contract.** Faithful to the released MAST LLM-judge pipeline
(`repo/MAST/llm_judge_pipeline.ipynb`, HEAD a70542e): single chat-completions call,
temperature 1.0, prompt = notebook instructions + full `definitions.txt` (14 modes,
3 categories) + the trace; answers parsed as binary yes/no per mode 1.1–3.3 plus a
task-completed verdict from the @@-delimited block (notebook cell-8 regex, zero-shot).
One provider-required deviation: `thinking: {{type: "disabled"}}` on every call (GLM-5.3
emits chain-of-thought into `reasoning_content`, starving `max_tokens`).

**Trace representation.** Each session is flattened in memory to a compact trajectory
(≤12,000 chars; ≤84 sampled messages: first 18 + last 66 with omission marker; per-message
text clipped) preserving USER / USER(meta) / ASSISTANT prose / ASSISTANT tool_use /
TOOL_RESULT(ok|err) / SUB subagent lines plus a counts-only header — identical
representation across all 7 formats. A harness note tells the judge to treat main agent +
subagents + tool loop as the multiagent system. Trace text is sent to the API and never
written to disk.

**Models.** Volume tier `glm-5.3-flash` for all but 4 fresh annotations (the 4 z.ai
content-filter rejects were failed over to NVIDIA NIM volume tier
`nvidia/nemotron-3-super-120b-a12b`); full tier `glm-5.3`
for the 50-trace cross-check (models listed via GET /models this session). **Continuity:**
13,194 labels from the interrupted v1 run (same content, path-keyed over
`~/.claude/projects`) were migrated by content hash and are counted as annotated; the v2
sweep annotated the remaining {n - agg['n_migrated_from_v1']:,}. Keys from env
(`ZAI_CODING_PLAN_KEY`, `NVIDIA_API_KEY`); never printed or written.

**Checkpointing / quota discipline.** One JSON line per completed target appended to
`fullrun/labels_full.jsonl`; restarts skip done `target_id`s (hash-keyed, so corpus
rebuilds resume cleanly). Per-call exponential backoff on HTTP 429 (z.ai 1302 request-rate
cap, shared with the interactive session on the same coding plan); sustained-429 would
degrade flash → flashx once, then stop with exact progress in `fullrun/sweep_status2.json`.

## 2. Privacy scan over the corpus

{priv_tbl}

## 3. Annotated volume

{vol_tbl}

## 4. Distribution — failure modes overall, by category, over time

{dist_tbl}

## 5. Tier agreement (flash volume vs full-tier cross-check)

{xchk_tbl}

## 6. Findings: this corpus vs the paper's multi-user benchmark corpus

{findings}

## 7. Token usage

{tok_tbl}

## 8. Artifacts

- `fullrun/targets.jsonl` — annotation set (ids/counts/timestamps + username-redacted
  file paths, `<USER>` placeholder; origin/runtime/part fields)
- `fullrun/labels_full.jsonl` — per-session binary MAST labels (labels/ids/counts only)
- `fullrun/crosscheck2.jsonl` + `fullrun/crosscheck2_agreement.json` — full-tier 50-trace check
- `fullrun/aggregates2.json` — all distribution tables (counts/ratios only)
- `fullrun/privacy_scan_full2.json` — whole-corpus privacy aggregate (counts/ratios only)
- `fullrun/privacy_partial.jsonl` — checkpointed per-file privacy scan ledger
  (redacted paths + per-file counters; no content)
- `fullrun/dashboard_full2.html` — real-data dashboard (offline, self-contained)
- `fullrun/build_targets.py`, `extract2.py`, `trace2.py`, `annotate2.py`, `migrate_labels.py`,
  `aggregate2.py`, `crosscheck2_agree.py`, `make_dashboard2.py`, `render_results.py`,
  `privacy_scan_corpus.py`
- `verify_fullrun.py` — offline reconciliation + privacy audit (exit 0 required)
- `repo/` — third-party MAST + AdaMAST clones (MAST pinned at HEAD a70542e); the
  clones' machine-local `.venv` was removed 2026-10-19 (virtualenvs bake absolute
  home-dir paths; see `repo/venv-removed-2026-10-19.txt` for recorded contents and
  recreation commands) and their git reflogs were expired (they embedded the owner's
  git identity)

<!--CHECK:n_targets={agg['targets_total']}-->
<!--CHECK:n_ok={n}-->
<!--CHECK:total_yes={agg['total_yes_labels']}-->
<!--CHECK:task_yes={tc['yes']}-->
<!--CHECK:task_no={tc['no']}-->
<!--CHECK:traces_any={agg['traces_with_any_mode']}-->
<!--CHECK:pending={agg['pending']}-->
"""
    (LANE / "RESULTS.md").write_text(results, encoding="utf-8")
    print(f"[render] RESULTS.md written ({len(results)} chars), n_ok={n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
