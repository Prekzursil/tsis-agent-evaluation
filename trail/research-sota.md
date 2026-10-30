# TRAIL Deep-Dive: SOTA Due-Diligence Dossier (v2)

**Topic:** TRAIL — Trace Reasoning and Agentic Issue Localization (agent-trace debugging benchmark)
**Compiled:** 2026-10-21, v2 — merges the earlier v1 dossier at this path with a fresh full re-verification pass (paper PDF re-read, repo re-cloned/re-run, competitor sweep redone). **v2 changes:** ATLAS *found* (v1 said "not found" — wrong); **Agentic CLEAR** added (partially closes what v1 called "the open gap"); AdaMAST arXiv id + results pinned; all v1 receipts re-verified or re-run. · **Team angle:** run TRAIL-style issue localization over their own single-harness agent session traces.

---

## 0. Corrections to the assignment premise (load-bearing)

1. **TRAIL is NOT a Google paper.** It is from **Patronus AI** — all six authors (Darshan Deshpande, Varun Gangal, Hersh Mehta, Jitin Krishnan, Anand Kannappan, Rebecca Qian), title-page affiliation "Patronus AI", emails `@patronus.ai`. **arXiv:2505.08638** (v1 2025-05-13, v2 2025-05-19, v3 2025-06-23 current). Receipts: arXiv abs page fetched this session; PDF p.1 header (25-page PDF, 2.6 MB, downloaded to `trail_paper.pdf`, text in `paper_text.txt`). Likely confusion source: the best-scoring *evaluated model* is Google's Gemini-2.5-Pro.
2. **There is no `github.com/google/trail`.** `gh api repos/google/trail` → HTTP 404 (run this session). Official repo: **`github.com/patronus-ai/trail-benchmark`** (verified this session: MIT, 24★, main, created & last-pushed **2025-05-14**, 3 open issues, no releases — a one-shot release, effectively unmaintained).
3. **No LLM-as-annotator exists in TRAIL.** Gold labels are **human-annotated** (4 experts + 4 verification rounds; agreement reported as span-revision rates 5.31–5.63%; **no κ number anywhere in the paper** — grep of `paper_text.txt` for kappa/Krippendorff: 0 hits). The "LLM-as-annotator with reported accuracy" premise resolves to **MAST** (arXiv:2503.13657): o1 few-shot judge **94% accuracy / κ=0.77** (zero-shot 0.89/0.58), human–human κ=0.88 — all re-fetched from arXiv HTML v2 this session. In TRAIL, LLMs are the *evaluated subjects*.

Session artifacts: `tss/tsis-deepdive/trail/` — `trail_paper.pdf`, `paper_text.txt`, `repo/` (clone @ `0ffbed9db859b4a66250dc783fa4dccf86869595`).

---

## 1. The paper, read from the actual PDF

### 1.1 Error taxonomy — how many issue classes

Three-level hierarchy (paper §3, PDF pp.4–5; canonical tree verbatim in `repo/benchmarking/run_eval.py:19-51`): 3 top-level areas → 9 mid-level groups → leaves.

| Top-level | Mid groups | Leaf categories |
|---|---|---|
| Reasoning Errors | Hallucinations; Information Processing; Decision Making; Output Generation | Language-only; Tool-related; Poor Information Retrieval; Tool Output Misinterpretation; Incorrect Problem Identification; Tool Selection Errors; Formatting Errors; Instruction Non-compliance |
| System Execution Errors | Configuration; API Issues; Resource Management | Tool Definition Issues; Environment Setup Errors; Rate Limiting; Authentication Errors; Service Errors; Resource Not Found; Resource Exhaustion; Timeout Issues |
| Planning & Coordination Errors | Context Management; Task Management | Context Handling Failures; Resource Abuse; Goal Deviation; Task Orchestration |

**Leaf-count is 20 in the released eval prompt, 21 in the paper's appendix prompt — a verified three-way inconsistency:**
- **Repo eval prompt: 20 fixed leaves** — counted from the tree at `run_eval.py:20-51` (this session's clone).
- **Paper appendix prompt (§A.11, `paper_text.txt:1814`): 21 nodes** — adds an open-ended `Domain Specific Errors` leaf. Repo HEAD `0ffbed9` ("Update eval prompt and clean code", 2025-05-14) removed exactly that node.
- **Scorer's hardcoded list: 21 with a *different* extra** — `"Incorrect Memory Usage"` at `calculate_scores.py:115-122`, present in **neither** prompt (and present 2× in gold data).
- **Gold data: 31 distinct category strings** (my count over all 148 gold files, this session) — the canonical 20 plus typo/case variants (`"Instruction non complience"`, `"Task Orchestration Errors"`, `"Goal deviation"`, `"Language-Only"`, `"Tool Selection"`, …) and 2 off-taxonomy `"Incorrect Memory Usage"`. Since joint accuracy does exact (location, category) pair-set matching with only partial normalization (`calculate_scores.py:12-30, 49-54`), variants that fail to normalize silently cap achievable scores.
- `Rate Limiting` has **0** gold instances (19 of 20 leaves instantiated). Patronus blog's "over 20 agentic errors" = leaves + open-ended/parent nodes.

### 1.2 Gold dataset — size and sources

| Fact | Value | Receipt |
|---|---|---|
| Traces | **148** — repo ships 117 GAIA + 31 SWE-Bench (`ls` counts this session); paper Table 5 says 118 GAIA + 31 SWE (=149); HF card says 118+30. **Counts don't reconcile across sources; the repo's 148 files / 841 errors is the release's ground truth.** | repo listing; `paper_text.txt:1508`; HF card |
| Total errors | **841**, avg 5.68/trace — **verified exactly by my count script this session** (117 GAIA files → 585 errors; 31 SWE → 256; Table 5's 579/256 split again doesn't reconcile) | `paper_text.txt` §4; count output |
| Spans | 1,987 *annotatable* OTel spans; 575 with ≥1 error. My recursive count of raw trace trees (spans nest via `child_spans`): **4,626 total spans** (3,579 GAIA + 1,047 SWE) — explains repo issue #2 ("I got 3K+ spans… can't match Table 5") | paper p.2; my `count_tree` run; issue #2 body |
| Sources | **GAIA** (open-world IR, text-only) + **SWE-Bench-Lite** (repo bug fixing) | `paper_text.txt:496-499` |
| Trace generation | GAIA: HF **OpenDeepResearch** manager+search-agent hierarchy, o3-mini-2025-01-31 backbone. SWE: **CodeAct** + sandboxed Python + gitingest, claude-3-7-sonnet-20250219; errors introduced "organically" via prompt constraints (length limits, forced exploration; §A.12) | `paper_text.txt:520-546` |
| Tracing standard | OpenTelemetry via **openinference** (Arize) — deliberately compatible with real observability stacks | `paper_text.txt:548-553` |
| Token scale | input mean 287K–728K (by tokenizer), **max 8.25M**; output mean 1.1–1.9K, max ≈5.4K | Table 2, `paper_text.txt:666-676` |
| License | **MIT** (repo LICENSE © 2025 patronus-ai; HF card). HF out-of-scope clause: must not *train* systems that automate human evaluation on it | LICENSE:1-3; HF card |

### 1.3 Annotation approach — human, not LLM

- **4 human annotators** (SE + log-debugging expertise) + **4 independent verification rounds with ML researchers** (§4.2, §A.7).
- Per-span: span ID, category, evidence quote, description, impact Low/Med/High. Per-trace: four 1–5 Likert scores (reliability, security, instruction adherence, plan optimality) + overall (rubric §A.7.1; mirrored in the model-facing template `run_eval.py:70-81`).
- Effort/cost: ~30 min (GAIA) / 40 min (SWE) + 20 min verification → **≈110–120 min/trace**; **$12.66/trace**; 18+, CS-expertise selection; PII screened (Ethics §, `paper_text.txt:761-765`).
- **Agreement:** separate **63-trace review set** (30 SWE/444 spans → **5.63%** spans modified; 33 GAIA/697 spans → **5.31%** revised) → "high inter-annotator agreement." **No κ/F1 agreement number reported.** The 63-trace subset is not released.

### 1.4 LLM-as-judge results (the "reported accuracy")

Task: read the whole raw trace JSON, output *all* errors + 4 trace scores, JSON-only, first-instance-only location rule (`run_eval.py:136`). Reasoning models run with reasoning_effort="high" (`run_eval.py:144-162`). Metrics (`calculate_scores.py`): binarized weighted **category F1**, **location accuracy** (span-id set overlap), **location-category joint accuracy** (pair-set overlap / gold), Pearson ρ for the 4 scores. 3-run averages.

| Model | GAIA Cat-F1 | GAIA Loc | GAIA Joint | SWE Joint |
|---|---|---|---|---|
| **Gemini-2.5-Pro-Preview-05-06** | 0.389 | 0.546 | **0.183** | **0.050** |
| Gemini-2.5-Flash | 0.337 | 0.372 | 0.100 | 0.000 |
| o3 (high) | 0.296 | 0.535 | 0.092 | CLE |
| Claude-3.7-Sonnet | 0.254 | 0.204 | 0.047 | CLE |
| o1 | 0.138 | 0.040 | 0.013 | CLE |
| GPT-4.1 | 0.218 | 0.107 | 0.028 | 0.000 |
| Llama-4-Maverick / Scout | 0.122 / 0.041 | 0.023 / 0 | 0 / 0 | 0 / 0 |

(Table 1, PDF p.7; SWE Cat/Loc for Gemini-Pro: 0.148/0.238.)
- Headline: best ≈ **11% combined joint accuracy**; **3 of 8 models hit CLE** (context-length failure) on SWE.
- All metrics **anti-correlate with input length** (Spearman −0.51 loc, −0.35 joint; Table 3). Reasoning effort helps: o3 joint 0.092 (high) → 0.071 (low) (Table 4). Hardest category: **Context Handling Failures** (F1≈0.00 for nearly all; Claude-3.7 0.18).
- Rubric correlations: Claude-3.7 ρ=0.738 (GAIA), Gemini-2.5-Pro ρ=0.817 (SWE) (§A.8).
- Imbalance: Formatting Errors (196) + Instruction Non-compliance (153+variants) = 353/841 ≈ **42%**; System Execution errors rare but catastrophic (paper's stated motivation for the fine-grained taxonomy). ~44% of Output-Generation errors are Low impact.
- Limitations (paper conclusion § + HF card): text-only; many tail classes with <10 examples; paper calls for synthetic data for high-impact low-frequency categories; "**a new framework is needed**."

---

## 2. Official repo — verified, cloned, and run

`gh api repos/patronus-ai/trail-benchmark` (this session): MIT, Python, 24★, 1 fork, main, created & pushed 2025-05-14, 3 open issues, archived=false.

Inventory (clone @ `0ffbed9`):
```
README.md · LICENSE (MIT) · requirements.txt (tiktoken, dotenv, litellm, numpy, scikit-learn, scipy)
benchmarking/run_eval.py           # litellm eval loop + taxonomy prompt (any litellm model id)
benchmarking/calculate_scores.py   # metrics
benchmarking/data/GAIA (117) · data/SWE Bench (31)                  # raw OTel span-tree JSONs
benchmarking/processed_annotations_gaia (117) · ..._swe_bench (31)  # gold annotations
benchmarking/results/outputs-gold-{gaia,swe_bench}/                 # shipped gold outputs + metrics
benchmarking/testresults/ · arxiv_alphaarena.xml (empty arXiv query result — 0 entries)
```
Raw trace format: `{trace_id, spans[]}` with OTel fields (`span_id`, `parent_span_id`, `span_kind`, `span_attributes`, `events`, `child_spans`…) — a recursive tree. Gold: `{errors:[{category, location(span_id), evidence, description, impact}], scores:{4 Likert + overall}}`.

**Runnable or read-only? — Runnable as a benchmark; read-only as a pipeline.**
- I ran the scorer this session, gold-vs-gold: `python calculate_scores.py --results_dir=results` → GAIA **F1 1.0000 / Loc-Joint 0.9741**, SWE **F1 1.0000 / 0.9677**, security-corr `nan` (constant gold). **Even a perfect annotator cannot score 1.0:** 4/148 gold traces contain duplicate (location, category) pairs (set-dedup at `calculate_scores.py:53-54` — count script this session), and 1 gold file is invalid JSON (`processed_annotations_gaia/a96c6811716c0473b86a23321db79c34.json`, trailing comma) which the scorer **silently skips** (`except: continue`, `calculate_scores.py:242-244`).
- `run_eval.py` (the model half) not run this session — needs an API key; code-path reviewed instead.
- **No trace-generation runner, no log ingestion, no annotation UI, no dashboard, no converters.** Open issue **#1** ("Code for generating SWE-bench data", 2025-05-23, unanswered): asks for "opentelemetry logging with CodeAct Agent" code. Issue **#3** (2026-07-22, open, unanswered): "Three bugs in `calculate_scores.py` that silently corrupt the reported TRAIL correlation table. Each is PoC-confirmed" — (1) `gen = int(gen)` floors reliability (`calculate_scores.py:180`) while other scores use `float()`; (2) JSON extraction; (3) sentinel `-1` handling. Issue **#2**: span-counting confusion (matches my 4,626 recursive vs paper's 1,987 annotatable).
- Windows bug: `run_eval.py:204` `file_path.split('/')[-1]` breaks output names on Windows paths. `requirements.txt` lists `dotenv` (abandoned pkg) but code imports `load_dotenv` (needs `python-dotenv`) — flagged, not install-tested.
- HF dataset `PatronusAI/TRAIL`: MIT, 241 MB parquet, **gated** (accept conditions; no resharing; no training auto-evaluators). GitHub repo carries the traces, so the gate doesn't block reproduction.

**Bottom line:** reproducing the *benchmark numbers* is fully supported (data + gold + runner + scorer). Reproducing *dataset creation* is not — nothing released for it.

---

## 3. Competitor sweep (2025–2026) and the daylight

| Work | What it is (receipt) | Daylight vs TRAIL |
|---|---|---|
| **MAST** — "Why Do Multi-Agent LLM Systems Fail?" arXiv:2503.13657 (Cemri et al.; NeurIPS 2025; repo `multi-agent-systems-failure-taxonomy/MAST`) | **14 failure modes / 3 categories** (spec/design, inter-agent misalignment, verification) from 150 dev traces; MAST-Data 1600+ annotated traces, 7 frameworks; **LLM-as-judge scaling: o1 few-shot 94% acc / κ=0.77** (zero-shot 0.89/0.58), human–human κ=0.88. Receipts: abs + HTML v2 fetched this session. | TRAIL's cited baseline. TRAIL is finer-grained (20 vs 14), adds **system-execution** errors (API 429/401/500/404, resource exhaustion, timeouts), OTel/openinference traces **beyond context windows** (max 8.25M tok), single- AND multi-agent, and exhaustive span-level localization (best 11–18% joint) vs MAST's coarse tagging (judge 94% agreement). TRAIL explicitly positions against it (`paper_text.txt:104-120`). |
| **AdaMAST** — "Fantastic Adaptive Taxonomies and How to Use Them", arXiv:**2607.16387** (Cemri et al., Berkeley+Apple, Jul 2026; repo `multi-agent-systems-failure-taxonomy/AdaMAST`; site multi-agent-systems-failure-taxonomy.github.io/AdaMAST) | **Induces a per-system failure taxonomy from the system's own traces** (3 fixed axes — system/role/domain — all codes induced, agreement-gated, no human per-trace annotation); taxonomy feedback raises SWE-agent 60%→70% on SWE-bench Verified Mini, **Claude Code 64.0%→70.7% as a runtime skill**; AdaMAST-Judge +8–15 pts best-of-5 on Terminal-Bench 2.0. Receipts: arXiv HTML + repo/site fetched this session. | Kills "we'll invent our own taxonomy" novelty. TRAIL's fixed 20 remain valuable as the *gold reference* others validate against. |
| **ATLAS** — runtime-skill packaging of the above (repo `multi-agent-systems-failure-taxonomy/ATLAS`, mirror `UMich-FATML/ATLAS`; paper "Adaptive Failure Taxonomies as Feedback for LLM-Agent Improvement Procedures") | **Diagnostic feedback layer for your own coding-agent sessions**: checkpoints at task boundaries, records evidence, learns a project-specific taxonomy (starts from a 14-code MAST adaptation), supports Codex/Claude Code. **README claims induced codes align with TRAIL expert annotations at Cohen's κ = 0.725**; ATLAS-Judge 89.9% on Terminal-Bench 2.0. Receipts: both GitHub READMEs fetched this session. ⚠️ **v1 of this dossier said "ATLAS: not found" — that was wrong; found and verified this session.** | Already does "run failure analysis over your own harness traces," live. Caveat: κ=0.725 is *code-alignment*, **not** the official TRAIL joint-accuracy metric — the official leaderboard metric remains publicly unbeaten. |
| **Agentic CLEAR** (IBM Research; ACL 2026; `pip install clear-eval`; ibm.github.io/CLEAR) | **Ingests OTel-compatible traces from MLflow/Langfuse/CSV (LangGraph, CrewAI), LLM-judge at system/node/trace level, surfaces recurring failure patterns with no predefined taxonomy, interactive dashboard** (System/Node/Trace views, path analysis); validates generated issues against TRAIL's 12 reasoning/planning categories (GPT-5 covers all 12). Receipts: project site fetched this session. ⚠️ New in v2 — v1's "no open pipeline ships this" claim is now partially outdated. | **The "runner+dashboard over arbitrary agent logs" idea, already shipped** — but: no single-harness coding-agent log ingestion, abandons the fixed TRAIL taxonomy, doesn't use the official TRAIL metrics, and its own README notes headline numbers aren't independently recomputable from the repo. |
| **Who&When** — "Which Agent Causes Task Failures and When?" arXiv:2505.00212 (ICML 2025; github `ag2ai/Agents_Failure_Attribution`) | Automated **failure attribution** (which agent, when) via counterfactual simulation; 127 MAS failure logs. Follow-ups: AgenTracer (2509.03312), AgentDebugX (2607.18754), DCFA (2609.04749) — active lane. | Attribution ≠ taxonomy-graded exhaustive localization; MAS-only. Complementary. |
| **AgentDebug** — "Where LLM Agents Fail and How They Can Learn From It" arXiv:2509.25370 (UIUC; github `ulab-uiuc/AgentDebug`) | AgentErrorBench (ALFWorld, **GAIA**, WebShop trajectories); root-cause ID + backtrack/forward debugging; +24% all-correct. | Goes beyond diagnosis into **repair/learning** — TRAIL never enters that territory. A "better diagnosis" project must position against this line. |
| **Agent-as-a-Judge** arXiv:2410.10934 (Meta/KAUST) | Agentic judge w/ intermediate feedback; DevAI; 90% vs 70% human agreement. | Framework inspiration for beating one-shot-prompt judges. |
| **GLIDER** arXiv:2412.14140 (Patronus, same team) | 3B open judge, span highlighting, 91.3% human agreement. | Cheap judge candidate to evaluate ON TRAIL. |
| **Percival** (Patronus product, patronus.ai/agents) | Commercial "AI debugger… detecting 20+ failure modes in agentic traces." | Closed productization of TRAIL's taxonomy. |
| **AlphaArena** (named in the tasking) | **No arXiv paper exists** — arXiv API query `all:"AlphaArena" AND all:"agentic"` returns 0 entries (run this session); the TRAIL repo bundles an empty arXiv query result for it. It is a Patronus combat-style agentic-eval product/blog; the only other "Alpha Arena" is a crypto-trading competition site. | Not trace-localization prior art; treat the tasking mention as a mislabel. |
| **AlphaEval** arXiv:2604.12162 (2026) | Production-grounded benchmark (94 tasks, 7 companies) evaluating agent *products*. | Different scope. |
| Observability/tooling adjacent: **Arize Phoenix / openinference** (the exact standard TRAIL traces use; trace-level eval cookbook), **Langfuse** (error-analysis cookbook — manual open-coding), **Potato** annotator (`trajectory_eval` schema "based on TRAIL and AgentRewardBench" + **15 trace converters**: OpenAI, Anthropic, LangChain, Langfuse, OTel, MCP, CrewAI, AutoGen, LangGraph, Claude Code, Aider, SWE-Agent…) | Trace collection + UI + generic judges + annotation. | **None ship fixed-TRAIL-taxonomy localization with the official metric as an open pipeline.** CLEAR is closest (dynamic taxonomy, dashboard, no official metric); ATLAS induces codes (κ-alignment only). Potato converts formats for *annotation*, not for TRAIL-metric evaluation. |

### Daylight summary (what is genuinely NOT done, v2)

1. **Nobody publicly beats the official TRAIL metric.** Public numbers on TRAIL are the original Table 1 (≤18.3%/5.0% joint) or non-official measures (ATLAS κ=0.725; CLEAR's coverage/macro-F1 vs 12 categories). A hierarchical/span-chunked/agentic judge that lifts Cat-F1/Loc/Joint on `calculate_scores.py`'s exact metric is open — the paper's own conclusion demands it.
2. **Fixed-TRAIL-taxonomy localization over arbitrary single-harness logs** (Claude Code / Codex / SWE-agent / Aider session JSONL → OTel span trees → 20-leaf localization → official scoring). CLEAR/ATLAS/Potato each hold one piece; the combination + official metric + gold-anchored validation is unclaimed.
3. **Multimodal TRAIL** — stated limitation, no extension exists.
4. **Gold hygiene + scorer v2** — 31 strings / invalid JSON / dup-pair ceiling / issue-#3 bugs are unpublished; a cleaned TRAIL-1.1 is a small citable contribution.
5. **LLM-as-annotator agreement for the 20 TRAIL classes** — MAST has 94%/κ0.77 for its 14; no equivalent exists for TRAIL's taxonomy.

---

## 4. Exact reproduction needs

**A. Reproduce the benchmark eval (feasible):**
1. Clone repo; install deps — **fix `dotenv`→`python-dotenv` first** (requirements bug, not install-tested); Python-only, no GPU.
2. **API key** for any litellm-compatible model; 1M-context class (Gemini-2.5) needed to avoid CLE on SWE.
3. **Cost:** GAIA ~300K mean × 117 + SWE ~650K mean × 31 ≈ **55M+ input tokens per full pass**; ×3 runs (paper averages 3) ≈ **165M+ per model**; ×8 models for the whole table. Student path: GAIA-only, 1–2 models, cheap judge (GLIDER) for development.
4. Patch scorer first (issue #3: int-cast, sentinel, JSON extraction) + handle invalid-JSON gold + dup-pair ceiling, or numbers won't match paper semantics.
5. Gold-vs-gold sanity: `calculate_scores.py --results_dir=results` → F1 1.0000 (run this session ✓).

**B. Reproduce dataset creation (NOT supported — new work):**
- Trace generation code (OpenDeepResearch + CodeAct with openinference OTel) not released (issue #1 unanswered). For own-harness traces, write the OTel bridge yourself (Potato's 15 converters are a starting point for formats).
- Human annotation ≈110–120 min/trace; no annotation UI released. Alternative: MAST-style validated LLM-judge transfer (measure agreement vs a small human set — no such number exists for TRAIL's 20 classes; measuring it is itself a contribution).

---

## 5. Novelty space for a 3–4 student team (own agent session traces)

The repo has **no runner beyond its own 148 traces, no ingestion, no dashboard** (verified inventory; issue #1 confirms generation code absent). But the ecosystem moved: **CLEAR ships ingestion+dashboard (dynamic taxonomy), ATLAS ships own-trace adaptive taxonomy live in Codex/Claude Code**. Ranked by defensibility given that:

1. **Beat the official TRAIL joint accuracy** with a structured judge (map-reduce over spans / hierarchical two-pass / span-retrieval / Agent-as-a-Judge tooling), incl. a fresh 2026 baseline sweep (paper's models are 2025-era; 11% is likely beatable by current flagships — establishing that alone is a contribution). Success = strictly higher F1/Loc/Joint on both splits via the repaired scorer.
2. **TRAIL-Runner for single-harness coding-agent logs**: convert own session traces → TRAIL-format OTel trees; fixed 20-leaf localization; official metrics; dashboard with gold-vs-predicted span overlays. Improvement bar vs prior art (must be stated): vs CLEAR (no fixed taxonomy/official metric/coding-harness ingestion), vs ATLAS (induced codes, κ-alignment not official metric), vs Potato (annotation, not eval). Validate with dual-human re-annotation of ~20–30 own traces **with reported κ** (TRAIL never reported one) + per-category transfer analysis.
3. **Fix-and-extend the benchmark** (TRAIL-1.1): repair gold typos/invalid JSON, dedup-safe metric, issue-#3 bugs, 117-vs-118 reconciliation. Small, citable, de-risks everything else.
4. **LLM-as-annotator for the 20 classes** (MAST methodology transfer; report judge-vs-human κ per category). License guardrail: don't fine-tune on TRAIL (HF out-of-scope clause).
5. **Dashboard with a measured claim** — engineering-only unless paired with e.g. "localization + dashboard cuts human debug time X%" (nobody measures that).

**Already done — do not claim:** adaptive taxonomies (AdaMAST/ATLAS); who/when attribution (Who&When, AgenTracer); repair loops (AgentDebug); interactive code debugging (debug-gym arXiv:2503.21557); trace UIs (Phoenix/Langfuse); ingestion+dashboard with dynamic issues (Agentic CLEAR).

---

## 6. Risks

- **The "runner+dashboard" idea is ~70% already built** (CLEAR + ATLAS + Potato). A team shipping only "ingest logs + show errors" is re-shipping CLEAR with a fixed taxonomy. The defensible frame is **fixed-taxonomy + official-metric + single-harness coding logs + human-validated agreement**.
- **Is the runner already in the repo?** No — `run_eval.py` runs only the 148 shipped TRAIL traces (verified). But it IS a runner for the benchmark; extension, not creation, is the work.
- **Benchmark aging:** 2026 models unmeasured on TRAIL publicly; if flagships already score high, contribution #1 shrinks to a baseline report. Run the cheap baseline first.
- **Metric/gold defects** (invalid JSON ×1, dup-pairs ×4, 31 raw strings, off-taxonomy ×2, scorer bugs #3, 20-vs-21 prompt/scorer mismatch) — patch and disclose before comparing any numbers.
- **Repo is a one-shot** (one day, 3 commits, 1 contributor; issues unanswered since May 2025 / Feb 2026 / Jul 2026) — students own their fixes; also an easy-PR opportunity.
- **Small imbalanced gold** (841 errors; 42% in two classes; many <10 examples) → high variance; paper needed 3-run averaging.
- **Attribution hazard:** citing "Google 2025" / `github.com/google/trail` (404) would be a fabricated-source error (§0).
- **API cost** is the main practical blocker for full-table reproduction; GAIA subset + 1–2 models.
- **Dataset-use clause** (no training auto-evaluators on TRAIL) must be carried into any project README.

---

## Receipts index (all verified this session 2026-10-21 unless noted)

| Claim | Receipt |
|---|---|
| arXiv id/versions/Patronus affiliation | arxiv.org/abs/2505.08638 fetched; `trail_paper.pdf` p.1 (downloaded this session); `paper_text.txt` |
| `google/trail` 404; repo meta (MIT, 24★, pushed 2025-05-14) | `gh api repos/google/trail` → 404; `gh api repos/patronus-ai/trail-benchmark` |
| 20-leaf repo prompt / 21-node paper prompt / 21-entry scorer list | `run_eval.py:20-51`; `paper_text.txt:1814` (Domain Specific Errors); `calculate_scores.py:115-122` |
| 148 files / 841 errors / 31 category strings / 1 invalid-JSON gold / 4 dup-pair traces / 4,626 recursive spans / 0× Rate Limiting | count scripts over `repo/benchmarking/` (run this session) |
| Scorer smoke test: F1 1.0000, joint 0.9741/0.9677, security corr nan | `python calculate_scores.py --results_dir=results` gold-vs-gold (run this session) |
| Issues #1/#2/#3 incl. bodies & dates | `gh api repos/patronus-ai/trail-benchmark/issues` (this session) |
| Human annotation: 4 annotators, $12.66/trace, 110–120 min, 5.31/5.63% revision, no κ; 63-trace agreement set | PDF §4.2 + §A.7 (`paper_text.txt`); grep kappa = 0 hits |
| Judge results: Gemini-2.5-Pro 0.183/0.050 joint; 11% headline; 3×CLE; length anti-correlation; o3 effort ablation | PDF Tables 1–4 (`paper_text.txt:588-676`), abstract, §5.1 |
| MAST 14 modes / 1600+ traces / judge 94% κ0.77 (zero-shot 0.89/0.58) / human κ0.88 | arxiv.org/abs/2503.13657 + HTML v2 §3.4 Table 2 (both fetched this session) |
| AdaMAST arXiv 2607.16387; axes; SWE-agent 60→70%, Claude Code 64→70.7%; repo | arxiv.org/html/2607.16387 + github.com/multi-agent-systems-failure-taxonomy/AdaMAST (fetched) |
| **ATLAS found** (v1 correction): runtime skill, Codex/Claude Code, starts from 14-code MAST, **κ=0.725 vs TRAIL**, ATLAS-Judge 89.9% TB2.0 | github.com/multi-agent-systems-failure-taxonomy/ATLAS README + UMich-FATML/ATLAS README (fetched this session) |
| Agentic CLEAR: MLflow/Langfuse/CSV ingestion, 3-level judge, dashboard, validated vs TRAIL 12 categories | ibm.github.io/CLEAR (fetched this session) |
| Who&When 2505.00212 (ICML 2025); AgentDebug 2509.25370; AgenTracer 2509.03312; debug-gym 2503.21557; Agent-as-a-Judge 2410.10934; GLIDER 2412.14140; AlphaEval 2604.12162 | arXiv/GitHub fetches this session |
| AlphaArena: no arXiv paper | `curl "https://export.arxiv.org/api/query?search_query=all:'AlphaArena' AND all:'agentic'"` → 0 entries (this session); repo's bundled `arxiv_alphaarena.xml` = empty result |
| HF dataset gated / MIT / 241 MB; out-of-scope clause | huggingface.co/datasets/PatronusAI/TRAIL card (fetched this session) |
| Potato trajectory_eval (TRAIL-based) + 15 converters; Phoenix trace-level eval cookbook; Langfuse error-analysis cookbook | fetched this session |
| Not run/verified: `run_eval.py` with a live model (no API budget); `pip install -r requirements.txt` (dotenv bug flagged); 63-trace agreement subset (unreleased); TRAIL citation-graph completeness beyond competitors above | stated as such |
