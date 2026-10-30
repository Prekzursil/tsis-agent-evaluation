# MAST SOTA Due-Diligence — "Why Do Multi-Agent LLM Systems Fail?" (Cemri et al.)

Generated: 2026-10-18 · Agent: MASTscope researcher · Methods: arXiv PDF read (pypdf 6.14.2), `gh api`, HF API, PyPI API, WebSearch + Exa
Confidence: High on all primary-source claims (paper PDFs + repos fetched this session); Medium where noted.
Note: this file supersedes an earlier partial draft of this dossier from an interrupted run of the same lane; category prevalences corrected to the v3 Figure-4 values (41.8 / 36.9 / 21.3 — cross-checked against the Berkeley blog's 41.77 / 36.94 / 21.30).

---

## 0. Corrections to the ask (verified this session)

| Ask said | Reality | Receipt |
|---|---|---|
| arXiv 2504.xxxx, verify id | **arXiv:2503.13657** (v1 2025-03-17; v2 2025-04-22; v3 2025-10-26) | arxiv.org/abs/2503.13657; PDF footer `arXiv:2503.13657v3 [cs.AI] 26 Oct 2025` |
| NeurIPS 2025 | Confirmed: **NeurIPS 2025 Datasets & Benchmarks track** (poster 121528; OpenReview fAjbYBmonr) | PDF p.1 footer "39th Conference on Neural Information Processing Systems (NeurIPS 2025) Track on Datasets and Benchmarks"; neurips.cc/virtual/2025/poster/121528 |
| "14 failure modes … (6 categories?)" | 14 modes in **3 categories** (FC1/FC2/FC3), not 6 | PDF p.1 abstract, p.2 Fig. 1, p.7 §4 |
| "1,642 gold traces" | 1,642 = **MAST-Data total (LLM-annotated)**; the human-"gold" is **MAST-Data-human = 21 traces × 3 human experts** (IAA studies) + 210 HE+HA traces. Not all 1,642 are human-gold. | PDF p.2, p.3 Table 1 |
| Frameworks "CrewAI/AutoGen" | MAST-Data frameworks: **ChatDev, MetaGPT, HyperAgent, AppWorld, AG2(MathChat)=AutoGen lineage, Magentic-One, OpenManus**. **CrewAI is NOT included anywhere.** Manus evaluated (60% human-eval success on ProgramDev) but EXCLUDED from MAST-Data — no trace access. | PDF p.3 Table 1; p.20 |

---

## 1. The paper, read (arXiv:2503.13657v3, 47 pp.; v2 39 pp. also read for deltas)

### 1.1 Taxonomy structure — 3 categories / 14 modes (PDF p.1-2, §4 p.7-8; repo `taxonomy_definitions_examples/definitions.txt`)

**FC1 System Design Issues (41.8% of annotated failures)** — flaws in pre-execution design (architecture, prompts, state):
| Mode | Name | Prevalence |
|---|---|---|
| FM-1.1 | Disobey Task Specification | 11.8% |
| FM-1.2 | Disobey Role Specification | 1.5% |
| FM-1.3 | Step Repetition | 15.7% |
| FM-1.4 | Loss of Conversation History | 2.80% |
| FM-1.5 | Unaware of Termination Conditions | 12.4% |

**FC2 Inter-Agent Misalignment (36.9%)** — coordination breakdowns:
| Mode | Name | Prevalence |
|---|---|---|
| FM-2.1 | Unexpected Conversation Reset | 2.20% |
| FM-2.2 | Wrong Assumption / proceeding without clarification | 6.80% |
| FM-2.3 | Task Derailment | 7.40% |
| FM-2.4 | Information Withholding | 0.85% |
| FM-2.5 | Ignored Other Agent's Input | 1.90% |
| FM-2.6 | Reasoning-Action Mismatch | 13.2% |

**FC3 Task Verification (21.3%)** — output quality control:
| Mode | Name | Prevalence |
|---|---|---|
| FM-3.1 | Premature Termination | (v2 running text: 7.82%) |
| FM-3.2 | No or Incomplete Verification | (v2: 6.82%) |
| FM-3.3 | Incorrect Verification | (v2: 6.66%) |

Mode-level percentages are from the v3 §4 running text; category totals from the Figure 4 caption (p.8: "System Design Issues (41.8%) Inter-Agent Misalignment (36.9%) Task Verification (21.3%)"), computed on the **210 human-annotated core traces** (Fig. 4: "total 210 traces … first 30 traces for each system"). Built via **Grounded Theory** over an initial **150 traces** (p.6, p.10). Modes map to execution stages (Pre-Execution / Execution / Post-Execution).

### 1.2 MAST-Data: 1,642 traces — arithmetic verified (PDF p.2-3, Table 1 p.3)

| Block | Configs | Annotation | # |
|---|---|---|---|
| 7-framework core | ChatDev ProgramDev GPT-4o; MetaGPT ProgramDev GPT-4o; HyperAgent SWE-Bench-Lite Claude-3.7-Sonnet; AppWorld Test-C GPT-4o; AG2(MathChat) GSM-Plus GPT-4; Magentic-One GAIA GPT-4o; OpenManus ProgramDev GPT-4o | HE+HA+LA | 7×30 = **210** |
| ProgramDev-v2 sweeps | ChatDev×{GPT-4o, Qwen2.5-Coder-32B, CodeLlama-7b}, MetaGPT×{GPT-4o, Claude-3.7, Qwen2.5-Coder-32B, CodeLlama-7b} (7 combos) | LA | 7×100 = **700** |
| Scaling block | AG2 OlympiadBench GPT-4o (206); AG2 GSM-Plus Claude-3.7 (193); AG2 MMLU GPT-4o-mini (168); Magentic-One GAIA GPT-4o (165) | HE+LA | **732** |
| **Total** | | | **1,642** ✓ (210+700+732) |

HE = human-evaluated success · HA = human-annotated failure modes · LA = LLM-annotated. So human failure labels exist only on the 210-trace core; **MAST-Data-human** (released separately) = 21 traces × 3 annotators from the IAA rounds (p.2, p.6). Models: GPT-4/-4o/-4o-mini, Claude-3.7-Sonnet, Qwen2.5-Coder-32B-Instruct, CodeLlama-7b-Instruct. Failure rates observed: 41%-86.7% across the 7 systems (p.2, Fig. 5/App. B).

### 1.3 LLM-as-annotator: prompt design & reported agreement (PDF p.6 §3.3 + Table 2 p.6; notebook `llm_judge_pipeline.ipynb` cell 0)

- **Human IAA:** 3 annotators independently + iteratively labeled **15 traces** until κ stabilized; final Cohen's κ = **0.88** (p.6). Out-of-domain re-validation (OpenManus + Magentic-One on MMLU/GAIA, post-finalization): κ = **0.79** (p.6).
- **Judge implementation (read from the released notebook):** OpenAI **o1** via chat-completions, `temperature=1.0`, single user message: [instructions] + [trace] + `definitions.txt` (14 definitions) + few-shot `examples.txt`; asks (A) freeform evidence-citing summary, (B) task-success yes/no, (C) **binary yes/no per failure mode** ("Only mark a failure mode if you can provide an example of it in the trace"); output parsed between `@@` delimiters.
- **Judge numbers (Table 2, p.6):** o1 zero-shot: acc 0.89 / recall 0.62 / precision 0.68 / F1 0.64 / κ 0.58. o1 **few-shot**: acc 0.94 / recall 0.77 / precision 0.833 / F1 0.80 / **κ 0.77** — calibrated on a held-out set from the IAA studies.
- Shipped as a library: **`pip install agentdash`** (p.2 §C).

### 1.4 MAST's own stated limitations (quotes from the PDF)

1. "We do not claim it covers every potential failure pattern" / "we do not claim MAST is exhaustive" (p.2, p.7).
2. Scope deliberately excludes failures attributable purely to base-LLM limits (hallucination, instruction-following); targets design-improvable patterns (p.7).
3. **Closed-source systems excluded**: Manus only human-evaluated (60% on ProgramDev); "the absence of comprehensive trace data prevents their inclusion in the primary MAST-Data" (p.20).
4. Cross-MAS comparison caveat: Fig. 4 (p.8) "intended to illustrate system-specific failure profiles rather than to serve as a performance comparison across MAS" — tasks differ per system.
5. Judge imperfect (few-shot κ 0.77, recall 0.77; zero-shot κ 0.58); validated on a small held-out IAA set.
6. Base-model study limited to 4 families incl. weak CodeLlama-7b; taxonomy prevalences computed on the 210-trace human core only.
7. Interventions demonstrated on ChatDev only (+9.4% role-spec fix; +15.6% added verification step; App. H) — no cross-framework intervention evidence.
8. (v3 adds) MAST-Data is LLM-annotated at scale, human-annotated at the core — "gold" is a spectrum, not a property of all 1,642.

---

## 2. Official repo + dataset: license & reusability (the CRITICAL check)

| Artifact | Where | License (verified) | Verdict |
|---|---|---|---|
| Code+data repo | github.com/multi-agent-systems-failure-taxonomy/MAST · 425★ · created 2025-03-11 · last push 2025-07-23 | **NONE** — `gh api repos/…/MAST` → `"license": null`; no LICENSE file in the git tree | Repo content is all-rights-reserved by default. Contains: `llm_judge_pipeline.ipynb`, `taxonomy_definitions_examples/{definitions.txt, examples.txt}`, `traces/` (raw + `*_human.json` annotations + AG2 experiment sweeps), `inter_annotator_agreement_annotations/` (4 PDFs), assets. |
| Dataset | huggingface.co/datasets/mcemri/MAST-Data (aka MAD; 1,507 downloads; lastModified 2026-08-13) | **CC-BY-4.0** (HF cardData `license: cc-by-4.0`) | **Released & reusable with attribution.** Configs: `default` → `MAD_full_dataset.json` (the 1,642), `human_labelled` → `MAD_human_labelled_dataset.json`. (Repo README also references `mcemri/MAD` repo id.) |
| Annotator library | pypi.org/project/agentdash v0.1.0 | **MIT** — "MAST Research Team", homepage = the MAST GitHub repo | The sanctioned, legally-clean way to run the MAST judge. |
| AdaMAST | github.com/…/AdaMAST (27★, created 2026-07-09, push 2026-08-27) + PyPI `adamast` v0.2.2.2 | **Apache-2.0** | Fully reusable code + runtime. |
| ATLAS | github.com/…/ATLAS (21★, created 2026-05-27, push 2026-07-21) | **Apache-2.0** | Fully reusable; hosts the `paper-pipeline` branch (original research pipeline) and `runs/` eval artifacts. |

**Bottom line:** the **dataset is genuinely released and reusable** (CC-BY-4.0). The **annotation code is released and reusable via MIT `agentdash`**; the identical notebook inside the GitHub MAST repo carries **no license** — use the PyPI package + HF dataset as clean provenance and do not copy unlicensed repo code into redistributed artifacts. Org inventory = exactly 3 repos (MAST, AdaMAST, ATLAS).

---

## 3. Competitor sweep — DEPTH on the same org's AdaMAST & ATLAS

### 3.1 AdaMAST (arXiv 2607.16387, "Fantastic Adaptive Taxonomies and How to Use Them" — Cemri, Cojocaru, Pan, Liu, Agarwal, Krentsel, Tang, Ramchandran, Gonzalez, Zaharia, Dimakis, Stoica; UC Berkeley + Apple + Bespoke Labs; 39-pp. PDF read)

**What it is:** induces a **target-system-specific failure taxonomy** from that system's own traces — named failure codes on 3 fixed axes (⚙️ system-level / 🎭 role-specific / 🧪 domain-specific); all code content (names, definitions, role labels, evidence patterns) induced, **no hand-authored codes, no per-trace human annotation**.

**Pipeline & gate (paper §3.1, App. B.1-B.2):** 8-step induction (draft → consolidation) → **deployment gate**: 4 independent LLM annotators label stratified held-out traces under a 5-phase deliberation protocol, up to 5 rounds × 5 traces; accepted only at mean pairwise area-level **κ ≥ 0.75 with coverage floor 0.70**; failed rounds trigger merge/add/relabel edits → **online refinement** as the system evolves.

**Reported results (paper):**
- Taxonomy-coded diagnoses beat free-form reflection in agent-system search on **all 5 benchmarks**.
- Runtime: SWE-agent on SWE-bench Verified Mini **60% (Reflexion) → 68% (fixed MAST) → 70% (AdaMAST)**.
- **Claude Code 64.0% → 70.7%** deployed as a runtime skill.
- AdaMAST-Judge best-of-5 on Terminal-Bench 2.0: **+8.1–14.9 pp over Pass@1**; +3.4/+4.5 pp over the fixed MAST vocabulary on the two non-saturated harnesses (89.9% judge accuracy per ATLAS README).
- Human-faithful: **κ 0.682 (induced) vs 0.516 (TRAIL's hand-crafted vocab)** on TRAIL expert labels under a matched panel. (ATLAS README separately cites κ 0.725 — different config; the paper number governs.)
- Compact: ~18× compression, 89% unique code signatures; genuinely adaptive: mean cross-domain code Jaccard **0.14** across 6 domains.
- Search replication under Gemini-3-flash-preview: non-negative gaps on all benchmarks (App. C.4).

**Product surface (repos, Apache-2.0):** CLI (`adamast validate | normalize | generate | judge | view | find | import-traces | register-taxonomy | doctor | status | dashboard | traces | single-run | claude/codex install`), **local dashboard** (`adamast/dashboard/`: dashboard.html, taxonomy_viewer.html, codex_monitor.html, webview), evidence export, `core/redaction.py`, lineage/reflection modules, **live Claude Code + Codex plugins/hooks** (session_start/stop, post_tool_use(+failure), subagent_stop, task_completed; checkpoints at episode boundaries; taxonomy proposal via native subagent + review-subagent approval; first generation at 5 eligible traces, refinement at +10 then every 20), ships a **built-in 14-code MAST adaptation** as the starting taxonomy. Loader auto-detects **7 trace formats**: AdaMAST native, string trajectory, chat-messages, **MAD/MAST-Data envelope**, tau-bench, **Codex CLI session JSONL**, generic event log. Providers: OpenAI (default), Anthropic, Google, Bedrock. Use cases explicitly marketed: error analysis, **regression tracking across versions**, **best-of-N selection**, optimizer feedback, live runtime.

### 3.2 ATLAS repo — the research-pipeline + integrations home of the same system

Created 2026-05-27, before the AdaMAST repo (2026-07-09); branch `feat/adamast-rename` records the rename; README now titled "AdaMAST". Deltas: hosts the **`paper-pipeline` branch** (original research code), `runs/` = {OfficeQA (44.4%→51.9% official scorer, same 133-question harness), Circle-Packing (0.997 of AlphaEvolve record in 20 evals), README}, `AdaMAST_as_a_Judge/` checks, `adamast_integration/` (claude_code/, codex/, interactive/, single_llm/), runtime loop "Observe → Correlate → Map → Decide" with `none apply` valid. **Honest reproducibility gap, stated in its own README:** "Per-question rows and raw scorer output are not included, so the headline numbers below cannot be independently recomputed from this repository alone."

### 3.3 Team's planned "improvements" — already-exists vs remaining daylight

| Planned improvement | Status | Where |
|---|---|---|
| Adaptive / self-updating annotator (learn taxonomy from target traces) | **EXISTS — this IS AdaMAST** | arXiv 2607.16387 §3; `adamast generate` |
| Stronger LLM-annotator agreement gating | **EXISTS** (4-annotator κ≥0.75+coverage gate vs MAST's calibrated single judge κ 0.77) | AdaMAST App. B.2 |
| Dashboard | **EXISTS** — local, single-user, read-only (taxonomy viewer + checkpoint monitor) | `adamast/dashboard/` |
| Claude Code / Codex harness ingestion | **EXISTS** — live hooks + transcript adapters + Codex JSONL loader | AdaMAST runtime integration; TRACE_FORMATS.md |
| Single-user real-session analysis (mechanism) | **EXISTS** — learns from your own conversations; MAST built-in as prior | AdaMAST live mode |
| Cross-framework comparison (benchmark MAS) | **PARTLY** — MAST-Data covers 7 frameworks (incl. AG2 = AutoGen lineage); AdaMAST ingests the MAD envelope. **CrewAI, LangGraph, OpenAI Agents SDK, Claude-Code-subagent teams studied nowhere.** | MAST Table 1; AdaMAST docs |
| Longitudinal failure-evolution study (months, real work, published) | **OPEN** — AdaMAST refines online but publishes no longitudinal study; MAST-Data is benchmark runs. Closest (non-academic) prior: hugomn/mast-taxonomy-production-telemetry | §3.4 |
| Attribution (which agent/step) | **NOT MAST/AdaMAST's job** — separate unsolved line (best step-level 14.2-29.4%) | §3.4 |
| Team/org multi-user rollup, trend alerting | **OPEN** — AdaMAST dashboard is local & single-user | — |
| Privacy protocol for personal session journals | **OPEN** — only a redaction module + one checklist line | AdaMAST core/redaction.py |

### 3.4 Wider competitor set (all fetched this session)

- **Who&When** (arXiv 2505.00212, Zhang et al., ICML 2025 — mlr.press v267): failure-attribution benchmark; 127 MAS, 184 failure logs; best method 53.5% agent / **14.2% step** accuracy; o1/R1 not practically usable.
- **FAMAS** (arXiv 2509.13782, Nanjing): spectrum-based fault localization for MAS; 29.35% action-level on Who&When (+49% over prior SOTA).
- **AgentTracer**: fine-tuned LLM for failure attribution (cited in FAMAS §7).
- **TRAIL** (Google): expert-annotated GAIA traces, finer hand-crafted taxonomy (reasoning/planning/coordination/system execution); AdaMAST's human-faithfulness yardstick.
- **AgentDebug / AgentErrorTaxonomy / AgentErrorBench** (arXiv 2509.25370): modular single-agent taxonomy (memory/reflection/planning/action/system), root-cause isolation, +24% all-correct accuracy.
- **AGDebugger**: interactive MAS debugging via message-history editing.
- **Agent GPA**: LLM-generated domain criteria under a fixed rubric — post-hoc eval, not a persistent vocabulary (per AdaMAST related-work).
- **hugomn/mast-taxonomy-production-telemetry**: MAST applied to a closed-alpha platform's production telemetry — 23,624 runs / 639,381 steps / 5 months; LLM judge κ 0.797 (is_failure) / 71.8% primary-mode match vs a 39-run gold set; failure share 14%→0.4% as platform matured; aggregates-only publication. **Direct prior art for "MAST on real private logs" — must cite.**
- **SyFI TraceLab** (UW, arXiv 2606.30520-class — fetched via project site + mirror; ~4,300 real Claude Code + Codex sessions, 350k LLM steps, 430k tool calls, public release incl. collection pipeline): proves responsible public release of real single-user coding-agent corpora is possible — but analyzes serving/workloads, **not failure taxonomies**.
- **MPIsaac-Per/claude-code-ops-audit** (MIT): DuckDB methodology for auditing your own Claude Code JSONLs (~245k tool calls, single operator), verification-debt rubric, LLM audit prompts — single-operator methodology prior art.
- Name check: **"MASTScope" does not exist** as a published tool/paper (searched; no collision) — free to use, though "AdaMAST" naming adjacency is a discoverability hazard.

---

## 4. Reproduction needs

**Tier 1 — reuse MAST assets (days, cheap):**
1. HF `mcemri/MAST-Data` (CC-BY-4.0): both configs (`MAD_full_dataset.json`, `MAD_human_labelled_dataset.json`).
2. `pip install agentdash` (MIT) — the released annotator; or the notebook (unlicensed-repo caveat).
3. OpenAI API access to an **o1-class reasoning model**. ⚠️ Paper used o1 specifically; if unavailable on the tenant, κ 0.77 is not directly reproducible — recalibrate against the 21-trace human set and report the new κ honestly.
4. `definitions.txt` + `examples.txt` for the exact prompt.
5. κ re-verification needs ≥2 humans on the 21 gold traces (traces average >15,000 lines — budget hours per trace per annotator).

**Tier 2 — regenerate MAST-Data (weeks, $$, probably unnecessary):** stand up the 7 frameworks (ChatDev, MetaGPT, HyperAgent, AppWorld, AG2, Magentic-One, OpenManus); benchmarks ProgramDev(+v2), SWE-Bench Lite, GSM-Plus, OlympiadBench, MMLU, GAIA, AppWorld Test-C; ~1,642 paid runs across GPT-4o / Claude-3.7-Sonnet / Qwen2.5-Coder-32B / CodeLlama-7b (last two can be local); human eval of ~942 runs + human annotation of 210.

**Tier 3 — AdaMAST reproduction (days):** `pip install adamast` (Apache-2.0), one provider key; `adamast generate/judge` on your own traces; research pipeline on ATLAS `paper-pipeline` branch. ⚠️ Headline numbers not recomputable from the repo alone (ATLAS README states this).

**Tier 4 — the team's 19k-journal corpus:** AdaMAST has a Codex-CLI JSONL loader but Claude Code sessions currently enter via its hook/transcript runtime, not the file loader — expect to write a Claude-Code-JSONL → (chat-messages | generic event log) normalizer. Schema reference: TraceLab §3.1 (metadata / user messages / reasoning (encrypted for Claude & Codex) / output / tool calls / tool results, all timestamped with token usage).

---

## 5. Novelty space GIVEN AdaMAST exists

Defensible:
1. **Longitudinal single-user failure evolution on real session corpora.** 19k private Claude journals is a corpus class neither MAST (benchmarks) nor AdaMAST (benchmarks + unpublished live use) has studied in a published longitudinal analysis. AdaMAST's own cross-domain Jaccard 0.14 finding *predicts* real-session taxonomies diverge from benchmark ones — that's the hypothesis, not the contribution gap.
2. **Cross-harness MAST/AdaMAST comparison on identical tasks for modern harnesses** — CrewAI, LangGraph, OpenAI Agents SDK, Claude-Code subagent teams (MAST-Data's 7 are 2024-era; CrewAI absent from every dataset found).
3. **Team/multi-user aggregation layer** — org-level rollups, trend alerting, cross-user privacy-preserving aggregation on top of `adamast` (whose dashboard is local, single-user, read-only). Natural positioning: "AgentDash/AdaMAST for fleets".
4. **A published privacy/screening protocol for personal agent journals** — no such protocol exists in any of the surveyed work; TraceLab + hugomn aggregates show the two responsible extremes (consented release vs aggregate-only).
5. **Attribution fusion** — MAST-mode × who/when on real traces; step-level attribution remains barely solved (14.2-29.4%).

Dead on arrival (AdaMAST already shipped or published it): adaptive taxonomy generation; agreement-gated annotation; evidence-quoted codes; judging + regression tracking; best-of-N with failure codes; optimizer feedback; runtime reflection; local dashboard; Claude Code/Codex live integration; MAST-as-prior.

Honesty note: prior art *hugomn* already did "MAST on production telemetry" at platform level — the team's differentiation must be the **single-user longitudinal** angle (evolution of one person's failure modes over 19k sessions) and/or modern-harness comparison, not "MAST on real logs" per se.

---

## 6. Risks — incl. privacy of the 19k private Claude session journals

**Legal/reuse:** MAST GitHub repo has NO license — never copy its code into redistributed artifacts; rely on `agentdash` (MIT) + HF dataset (CC-BY-4.0, attribution). AdaMAST/ATLAS Apache-2.0 — fine.

**Privacy (gating item for teammates/demo):** the journals are single-user production data likely containing API keys/tokens, absolute file paths, client/third-party code and names, personal communications; reasoning summaries are present even where raw reasoning is encrypted (TraceLab §3.1). Required before any teammate or graded demo touches the corpus:
1. **Consent & scope:** confirm the corpus is solely the operator's own sessions; any other humans appearing (mentions, quoted messages, shared projects) need consent or removal. A graded demo must run on public MAST-Data or synthetic traces — never raw journals.
2. **Secret scan:** regex + entropy scan for keys/tokens/passwords; rotate anything found (assume compromise once shared).
3. **PII scrub:** de-identify names/emails/paths; publish only aggregates (the hugomn pattern: "no trajectory text, only de-identified aggregates … verified by exhaustive scan of every file and the full git history").
4. **Egress control:** LLM judging sends trace text to a provider — **redact before any API call** (AdaMAST checklist mandates exactly this); prefer local models for sensitive slices; never commit journals or per-trace derived text.
5. **ToS:** self-analysis of one's own Claude logs is consistent with consumer self-use, but redistribution/publication of derived datasets needs TraceLab-style consent+scrubbing; the account-type-specific Anthropic policy text was NOT verified this session — flag to the run owner.
6. **Retention boundary:** local processing mart, private outputs out of any public repo (pattern: claude-code-ops-audit `docs/PERSISTENCE.md`).

**Scientific risks:** judge-calibration drift (o1 unavailability → κ no longer 0.77; recalibrate on the 21 gold traces); single-rater gold for your own corpus (mirror MAST's 15-trace × 3-annotator IAA protocol before trusting your labels); benchmark-taxonomy bias (MAST built on benchmark MAS — coverage gaps on real sessions are expected; frame as a finding); **priority risk** — the Berkeley org is actively shipping into this exact space (ATLAS push 2026-07-21, AdaMAST push 2026-08-27); re-check both repos immediately before freezing any novelty claim.

---

## 7. Receipts (everything fetched/run this session)

1. `curl -sL -o mast2503.13657v3.pdf https://arxiv.org/pdf/2503.13657v3` (47 pp.) and `…v2.pdf` (39 pp.) → extracted with pypdf 6.14.2 to `v3_full.txt` / `v2_full.txt` (===PAGE n=== markers; all p.N citations above map to these).
2. `gh api repos/multi-agent-systems-failure-taxonomy/MAST` → `"license": null`, 425★, created 2025-03-11, pushed 2025-07-23.
3. `gh api orgs/multi-agent-systems-failure-taxonomy/repos` → 3 repos: MAST (null), ATLAS (Apache-2.0, 21★), AdaMAST (Apache-2.0, 27★).
4. `gh api repos/…/MAST/git/trees/main?recursive=1` → README, `llm_judge_pipeline.ipynb` (15,195 B), `taxonomy_definitions_examples/{definitions,examples}.txt`, `traces/**` (incl. `*_human.json`), IAA PDFs; **no LICENSE file**.
5. `llm_judge_pipeline.ipynb` cell 0 (contents API): o1, temperature 1.0, definitions+few-shot prompt, `@@`-delimited binary per-mode output (quoted in §1.3).
6. HF API `mcemri/MAST-Data` → `license: cc-by-4.0`, configs `default`/`human_labelled`, 1,507 downloads, lastModified 2026-08-13.
7. PyPI API: `agentdash` 0.1.0 MIT (author "MAST Research Team", homepage = MAST repo); `adamast` 0.2.2.2 "Adaptive failure-mode taxonomy runtime for Codex, Claude Code, and custom agent harnesses".
8. AdaMAST README + `docs/TRACE_FORMATS.md` + ATLAS README via contents API (saved locally: `adamast_readme.md`, `atlas_readme.md`); ATLAS branch list (incl. `paper-pipeline`, `feat/adamast-rename`); `runs/` = {Circle-Packing, OfficeQA, README.md}.
9. AdaMAST paper PDF `adamast_paper.pdf` (39 pp., pre-existing in this dir) → `adamast_full.txt`; quoted numbers in §3.1 (gate κ≥0.75/0.70 coverage, TRAIL 0.682 vs 0.516, 60/68/70 SWE-bench VM, Claude Code 64.0→70.7, TB2.0 +8.1-14.9 pp, Jaccard 0.14, ~18× compression, Gemini replication).
10. Exa/WebSearch: arXiv 2503.13657 metadata & versions; NeurIPS 2025 poster 121528 + OpenReview fAjbYBmonr; Who&When 2505.00212 (ICML 2025); AgentDebug 2509.25370; FAMAS 2509.13782; hugomn/mast-taxonomy-production-telemetry README; TraceLab (tracelab.cs.washington.edu + arXiv mirror 2606.30560); MPIsaac-Per/claude-code-ops-audit README; "MASTScope" collision check → no existing tool/paper by that name.

**Not done / not verifiable this session:** Anthropic ToS text for the team's specific account type (flagged §6.5); o1 availability on the team's OpenAI tenant; full download + per-record inspection of the 1,642 HF payloads (metadata only); AdaMAST paper's arXiv abs page fetched only via Exa mirror + local PDF (id 2607.16387 consistent across README badge, ATLAS README, and PDF header).
