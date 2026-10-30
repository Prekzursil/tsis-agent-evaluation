# MASTscope full-scale run — RESULTS (v2: rebuilt multi-runtime corpus)

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
**33,889 sessions with ≥1 user and ≥1 assistant message** across 7
formats (claude_journal 26,999; codex_rollout
3,871; chatgpt_export 1,596;
openai_like grok/gemini 823; zcode model-IO
514; codex web tasks 76;
generic 10). Unique files yielding no user+assistant
pair (9,642: sqlite/leveldb by
design, cursor meta.json, ledgers, caches, markdown notes, logs) are excluded with counts
(`fullrun/targets_summary.json`).

**Annotation contract.** Faithful to the released MAST LLM-judge pipeline
(`repo/MAST/llm_judge_pipeline.ipynb`, HEAD a70542e): single chat-completions call,
temperature 1.0, prompt = notebook instructions + full `definitions.txt` (14 modes,
3 categories) + the trace; answers parsed as binary yes/no per mode 1.1–3.3 plus a
task-completed verdict from the @@-delimited block (notebook cell-8 regex, zero-shot).
One provider-required deviation: `thinking: {type: "disabled"}` on every call (GLM-5.3
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
sweep annotated the remaining 19,346. Keys from env
(`ZAI_CODING_PLAN_KEY`, `NVIDIA_API_KEY`); never printed or written.

**Checkpointing / quota discipline.** One JSON line per completed target appended to
`fullrun/labels_full.jsonl`; restarts skip done `target_id`s (hash-keyed, so corpus
rebuilds resume cleanly). Per-call exponential backoff on HTTP 429 (z.ai 1302 request-rate
cap, shared with the interactive session on the same coding plan); sustained-429 would
degrade flash → flashx once, then stop with exact progress in `fullrun/sweep_status2.json`.

## 2. Privacy scan over the corpus

Scanned **122,733** of 122,733 `status=ok` records of `manifest.jsonl` (100.0%; both drives, all runtimes, live+backup+orphan-backup) — 301.6 GiB, 59,792,923 line-equivalents. UNSKIPPABLE COMPLETE (2026-10-30): the 222 pathological binaries the watchdog had skipped are now all resolved — 221 scanned for real (203 in run2 + 18 more via `fullrun/scan_skipped_seq.py` with the exactly-equivalent fast matcher `scan_one_fast.py`, equivalence verified 0 mismatches on 32 adversarial email cases + all 11,842 blocks of a real wedge-file), and the 41 GB `codex-sessions-seed-20260315.tar` is gone from disk since the manifest (recorded `unreadable=1`, the scanner's semantics for a missing path). `skipped_by_watchdog` = 0. JSON line rate 79.9%; message-like objects 8,124,213 (13.59% of lines).

| PII-ish category | lines | line ratio |
|---|---:|---:|
| abs_path | 17,314,238 | 28.957% |
| entropy_blob | 10,067,477 | 16.837% |
| url | 2,250,536 | 3.764% |
| ipv4 | 659,702 | 1.103% |
| email | 434,906 | 0.727% |
| secret_assignment | 11,994 | 0.020% |
| openai_key | 8,593 | 0.014% |
| github_token | 6,232 | 0.010% |
| bearer_token | 6,848 | 0.011% |
| aws_key | 4,793 | 0.008% |


By drive: C: 51,643 files/19,361,070 lines, D: 71,090 files/40,431,853 lines. By origin: live 47,892 files, backup 51,446 files, orphan-backup 23,395 files.

## 3. Annotated volume

| stage | count |
|---|---:|
| manifest records scanned (privacy) | 122,733 |
| canonical unique files (hashes) | 41,877 |
| parseable session targets (annotation set) | 33,889 |
| — of which exploded from multi-conversation containers | 1,654 |
| annotated OK (flash tier or migrated v1) | **32,540** |
| — migrated from v1 path-keyed run (same content hash) | 13,194 |
| — annotated fresh this run (by model: glm-5.3-flash 19,342, nvidia/nemotron-3-super-120b-a12b 4) | 19,346 |
| parse-fail responses (ok=false, counted as annotated) | 1,349 |
| pending (not yet annotated) | 0 |
| excluded as not parseable (no user+assistant pair) | 9,642 unique files |

During the 2026-10-19 repair, 2,172 `http_429_exhausted` placeholder rows (labels with no verdict, written by a pre-fix sweep version) were removed from `labels_full.jsonl` so resume rounds would retry them, per `annotate2.py`'s persistence contract; the resumed sweep annotated all of them.

The last 4 targets, which the z.ai content filter (error 1301, contentFilter level 2, HTTP 400) rejected on both `glm-5.3-flash` and `glm-5.3`, were completed via the provider failover ladder (`annotate_pending_fallback.py`): 4/4 annotated by NVIDIA NIM volume tier `nvidia/nemotron-3-super-120b-a12b` (same prompt contract; provider claims recorded in `../provider-claims.json`).

Target formats: claude_journal 26,999, codex_rollout 3,871, chatgpt_export 1,596, openai_like 823, zcode_modelio 514, codex_web_tasks 76, json_messages 10.

## 4. Distribution — failure modes overall, by category, over time

**Task completed**: yes 11,209 / no 9,830 / null 11,501 (34.5% yes). Traces with ≥1 flagged mode: 21,205 (65.2%). Mean modes per flagged trace: 2.45. Total yes-labels: 52,034.

| mode | yes | incidence | occ. share | paper prev. |
|---|---:|---:|---:|---:|
| 1.1 Disobey Task Specification | 2,504 | 7.70% | 4.81% | 11.80% |
| 1.2 Disobey Role Specification | 72 | 0.22% | 0.14% | 1.50% |
| 1.3 Step Repetition | 14,038 | 43.14% | 26.98% | 15.70% |
| 1.4 Loss of Conversation History | 1,071 | 3.29% | 2.06% | 2.80% |
| 1.5 Unaware of Termination Conditions | 1,695 | 5.21% | 3.26% | 12.40% |
| 2.1 Conversation Reset | 4,844 | 14.89% | 9.31% | 2.20% |
| 2.2 Fail to Ask for Clarification | 2,576 | 7.92% | 4.95% | 6.80% |
| 2.3 Task Derailment | 842 | 2.59% | 1.62% | 7.40% |
| 2.4 Information Withholding | 172 | 0.53% | 0.33% | 0.85% |
| 2.5 Ignored Other Agent's Input | 455 | 1.40% | 0.87% | 1.90% |
| 2.6 Action-Reasoning Mismatch | 1,839 | 5.65% | 3.53% | 13.20% |
| 3.1 Premature Termination | 9,486 | 29.15% | 18.23% | 6.20% |
| 3.2 Weak Verification | 6,256 | 19.23% | 12.02% | 8.20% |
| 3.3 No or Incorrect Verification | 6,184 | 19.00% | 11.88% | 9.10% |

| category | ours (occ. share) | ours (sum incidence) | paper (mode-sum) | paper Fig.4 |
|---|---:|---:|---:|---:|
| FC1 System Design / Specification | 37.2% | 59.6% | 44.2% | 41.8% |
| FC2 Inter-Agent Misalignment | 20.6% | 33.0% | 32.3% | 36.9% |
| FC3 Task Verification | 42.1% | 67.4% | 23.5% | 21.3% |

**Over time** (by session first timestamp; fallback unknown):

| month | n annotated | % with ≥1 mode |
|---|---:|---:|
| 2023-01 | 13 | 100.0% |
| 2023-02 | 11 | 81.8% |
| 2023-03 | 7 | 85.7% |
| 2023-04 | 2 | 50.0% |
| 2023-05 | 5 | 100.0% |
| 2023-06 | 4 | 50.0% |
| 2023-07 | 2 | 100.0% |
| 2023-08 | 1 | 100.0% |
| 2023-09 | 17 | 100.0% |
| 2023-10 | 34 | 94.1% |
| 2023-11 | 125 | 96.8% |
| 2023-12 | 64 | 92.2% |
| 2024-01 | 37 | 97.3% |
| 2024-02 | 16 | 93.8% |
| 2024-03 | 23 | 100.0% |
| 2024-04 | 5 | 100.0% |
| 2024-05 | 12 | 91.7% |
| 2024-06 | 32 | 93.8% |
| 2024-07 | 18 | 83.3% |
| 2024-08 | 36 | 83.3% |
| 2024-09 | 37 | 86.5% |
| 2024-10 | 41 | 82.9% |
| 2024-11 | 81 | 81.5% |
| 2024-12 | 115 | 92.2% |
| 2025-01 | 94 | 91.5% |
| 2025-02 | 46 | 95.7% |
| 2025-03 | 72 | 88.9% |
| 2025-04 | 102 | 94.1% |
| 2025-05 | 48 | 93.8% |
| 2025-06 | 36 | 91.7% |
| 2025-07 | 33 | 97.0% |
| 2025-08 | 49 | 83.7% |
| 2025-09 | 42 | 88.1% |
| 2025-10 | 54 | 90.7% |
| 2025-11 | 53 | 98.1% |
| 2025-12 | 46 | 84.8% |
| 2026-01 | 77 | 93.5% |
| 2026-02 | 538 | 81.0% |
| 2026-03 | 1,056 | 91.7% |
| 2026-04 | 518 | 85.3% |
| 2026-05 | 3,466 | 71.8% |
| 2026-06 | 10,255 | 74.3% |
| 2026-07 | 8,280 | 43.0% |
| 2026-08 | 2,899 | 33.3% |
| 2026-09 | 2,186 | 81.1% |
| 2026-10 | 988 | 82.2% |
| unknown | 864 | 90.3% |


**Top runtimes**:

| runtime | n | task done | top mode |
|---|---:|---:|---|
| claude-code-free | 16,725 | 71% | 3.1 (21.4%) |
| agent-sessions-vault | 9,550 | 24% | 1.3 (72.6%) |
| codex | 2,208 | 39% | 1.3 (74.2%) |
| ai-exports | 1,634 | 35% | 1.3 (76.3%) |
| vm-backup | 1,489 | 66% | 1.3 (73.1%) |
| zcode-rollout | 494 | 14% | 1.3 (85.8%) |
| grok | 392 | 42% | 1.3 (82.9%) |
| zcode-workspace | 24 | 0% | 1.3 (91.7%) |
| codex-archived | 11 | 71% | 1.3 (90.9%) |
| gemini-cli | 8 | 60% | 1.3 (75.0%) |
| cline | 5 | 67% | 1.3 (80.0%) |


**By session format**:

| format | n | task done | top mode |
|---|---:|---:|---|
| claude_journal | 25,942 | 58% | 1.3 |
| codex_rollout | 3,673 | 35% | 1.3 |
| chatgpt_export | 1,559 | 36% | 1.3 |
| openai_like | 784 | 47% | 1.3 |
| zcode_modelio | 499 | 15% | 1.3 |
| codex_web_tasks | 75 | 30% | 1.3 |
| json_messages | 8 | 40% | 1.3 |


## 5. Tier agreement (flash volume vs full-tier cross-check)

50 traces annotated with `glm-5.3` (full tier) over the deterministic 50-sample (seed 7, size-sorted); 49 comparable pairs (one sampled trace's flash-tier response is a parse-fail and is excluded), same prompt contract.

| mode | agree | yes\|yes | yes\|no | no\|yes | no\|no |
|---|---:|---:|---:|---:|---:|
| 1.1 Disobey Task Specification | 92% | 0 | 2 | 2 | 45 |
| 1.2 Disobey Role Specification | 100% | 1 | 0 | 0 | 48 |
| 1.3 Step Repetition | 53% | 13 | 21 | 2 | 13 |
| 1.4 Loss of Conversation History | 96% | 2 | 2 | 0 | 45 |
| 1.5 Unaware of Termination Conditions | 88% | 1 | 3 | 3 | 42 |
| 2.1 Conversation Reset | 78% | 2 | 9 | 2 | 36 |
| 2.2 Fail to Ask for Clarification | 88% | 1 | 2 | 4 | 42 |
| 2.3 Task Derailment | 98% | 1 | 1 | 0 | 47 |
| 2.4 Information Withholding | 98% | 0 | 0 | 1 | 48 |
| 2.5 Ignored Other Agent's Input | 94% | 0 | 3 | 0 | 46 |
| 2.6 Action-Reasoning Mismatch | 94% | 0 | 2 | 1 | 46 |
| 3.1 Premature Termination | 65% | 5 | 4 | 13 | 27 |
| 3.2 Weak Verification | 86% | 4 | 3 | 4 | 38 |
| 3.3 No or Incorrect Verification | 88% | 2 | 0 | 6 | 41 |

Mean mode agreement **86.9%**; task_completed agreement **95.5%** (confusion yy/yn/ny/nn = {'yy': 9, 'yn': 1, 'ny': 0, 'nn': 12}).

## 6. Findings: this corpus vs the paper's multi-user benchmark corpus

Single-user, long-horizon, single-harness corpus (N=32,540 sessions) vs the
MAST paper's multi-user, multi-framework benchmark corpus (N=210 traces; CrewAI/AutoGen-class
frameworks on short benchmark tasks):

**Where it matches.** The top of the distribution is dominated by the same operational
failure the paper ranks #1 or #2 — FM-1.3 (Step Repetition,
43.1% incidence here). Verification-category failures
(FC3) remain substantial in both (42.1%
of occurrences here vs 21.3–23.5% in the paper), confirming that weak or missing
self-verification is not an artifact of any one harness. Rare-in-paper modes stay rare
here too (FM-2.4 Information Withholding: paper 0.85%, here
0.53%).

**Where it diverges.** 5 modes move by more than 8 points of incidence:
- FM-1.3 Step Repetition: here 43.1% vs paper 15.7% (+27.4 pts)
- FM-2.1 Conversation Reset: here 14.9% vs paper 2.2% (+12.7 pts)
- FM-3.1 Premature Termination: here 29.1% vs paper 6.2% (+22.9 pts)
- FM-3.2 Weak Verification: here 19.2% vs paper 8.2% (+11.0 pts)
- FM-3.3 No or Incorrect Verification: here 19.0% vs paper 9.1% (+9.9 pts)

**Reading the divergence.** This corpus is one expert operator's real fleet — sessions
span 2023-01 through 2026-10, with ~96% of annotated volume from 2026:
sessions are long (median tens of messages), tool-saturated, heavily subagent-delegated, and
span six harness families (Claude Code journals dominant at
25,942 traces, plus Codex rollouts,
grok/gemini chats, zcode model-IO logs and ChatGPT exports). The paper's corpus is many
users running small fixed crews on short, well-specified benchmark tasks with hard
verifiers. That difference alone predicts most of the gap: inter-agent misalignment modes
(FC2) — the paper's signature category, 36.9% of its failures — presuppose peer agents that
must coordinate; in a single-main-agent + tools + subagents harness, FC2
(20.6% here) shifts toward
harness-internal variants (ignored subagent input, withholding in delegation) rather than
crew-coordination breakdowns. Task completion reads differently too: the paper's crews often
fail the benchmark outright, while here task_completed=yes on
34.5% of sessions — but a substantial fraction of "yes"
sessions still carry flagged failure modes, echoing the paper's observation that superficial
verifiers over-credit success (FM-3.2/3.3 remain present at
19.2%/19.0%).

**What this says about MAST's generality.** The taxonomy's FC1/FC2/FC3 skeleton and all 14
modes transfer to a production single-user harness without needing new categories: every
mode fires on real traffic at non-trivial or sensibly-rare rates. But the *distribution* is
a property of the harness and task mix, not of agents in general — MAST is a valid ruler,
not a universal profile. Any deployment-side use of MAST should baseline on the site's own
traffic, exactly as this run does; paper-derived priors would mis-rank remediation
investment for a fleet like this one by overweighting crew-coordination failures that
rarely occur without peer agents.

Tier-agreement caveat: flash-tier labels agree with full-tier at
86.9% mean mode agreement on the 50-trace cross-check
(paper annotator–human accuracy was 94%), so per-mode incidences below ~10% should be read
with the agreement noise floor in mind.


## 7. Token usage

| stream | calls ok | 429s | prompt tokens | completion tokens |
|---|---:|---:|---:|---:|
| v1 sweep (path-keyed, interrupted; 15,522 ok records produced, 13,194 unique-hash migrated) | 15,522 | 20,267 | 100,087,185 | 6,225,991 |
| v2 sweep + failover (fresh labels written this run, ok+parse-fail; 19,342 glm-5.3-flash + 4 nemotron-3-super-120b) | 20,695 | 62,080 | 95,111,288 | 7,663,917 |
| full-tier cross-check (glm-5.3, 50-trace sample) | 50 | 0 | 264,170 | 15,255 |

v2 429s (62,080 across 10 counted resume rounds) are reconstructed from the per-round monotonic counters in `sweep2.log`/`sweep3.log` — rounds killed before their first 100-item progress mark contribute 0, so the true total is marginally higher. `sweep_status2.json` is per-process and overwritten by every round; each round now also appends its final counters to `sweep2_status_history.jsonl`. Migrated labels carry their v1 usage in-file; v2 fresh totals above are summed from label records and exclude migrated ones.

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

<!--CHECK:n_targets=33889-->
<!--CHECK:n_ok=32540-->
<!--CHECK:total_yes=52034-->
<!--CHECK:task_yes=11209-->
<!--CHECK:task_no=9830-->
<!--CHECK:traces_any=21205-->
<!--CHECK:pending=0-->


## 9. AdaMAST comparison run (2026-10-20/21)

The AdaMAST threat was run for real (repo/AdaMAST-readonly @ 3c83d81, v0.2.2.2, `adamast
generate` + `adamast judge`) on a 520-session stratified sample (seed 7) of the labeled corpus.
**Single model for the whole batch: `nvidia/nemotron-3-ultra-550b-a55b` (NVIDIA NIM, top tier)**
— draft, agreement gate, judge, and taxonomy matching; provider claimed in
`../provider-claims.json` (lane `mastscope-adamast`). Gate outcome: kappa 0.315 / coverage
0.969 -> `review_required`; judged via `--allow-review-required`. Taxonomy-level overlap with
MAST-14: Jaccard 0.150 (vs their published 0.14 cross-domain); per-session detection agreement
kappa 0.267. Full write-up: `fullrun/adamast_comparison.md`; artifacts under `fullrun/adamast/`.

**2026-10-21 lane privacy remediation (post-AdaMAST audit).** The AdaMAST run had
written two raw-session-content artifacts into the lane (`fullrun/adamast/traces_sample.jsonl`,
`taxonomy_run/artifacts/inputs/traces.normalized.jsonl` — 4.02 + 4.03 MB of embedded
trajectories) and left the OS username in absolute paths across its logs/metadata, plus a
recreated `repo/.venv`. All were remediated in-session and `verify_fullrun.py` re-run to
**VERIFY OK: 43 checks passed, exit 0** (content-leak probes 60/60 clean, username sweep
clean): the two raw-content files were deleted with a regeneration note
(`fullrun/adamast/CONTENT_REMOVED-2026-10-21.md`; both are deterministic functions of
corpus + labels, which remain), usernames redacted to `Users/<USER>` in 9 adamast files
(`fullrun/sanitize_lane.py`), and `repo/.venv` removed again
(`repo/venv-removed-2026-10-21.txt`). Kept adamast artifacts are labels/counts/ids only.
