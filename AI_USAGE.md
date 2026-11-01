# AI_USAGE — disclosure of AI involvement in this deep-dive

Written 2026-10-31 to satisfy DECISION.md Condition 5/7 (provenance pack before week 3).
Standard: tss/lab AI-usage disclosure. Every row below cites a receipt in this repo.

**Headline disclosure: the entire deep-dive in this repository — all three lanes
(tau2-bench, MASTscope, TRAIL), the corpus build, the council decision memo, the SOTA
dossiers, the verification/audit tooling and the reports — was produced by an AI
workflow.** The driving harness is ZCode's dynamic-workflow engine (driver agent plus
specialized subagents); the models involved are the ZCode/GLM lane (GLM-5.3 /
glm-5.3-flash, plus a v1 glm-4.5-flash batch), grok-4.7 (local bridge), and the NVIDIA
NIM nemotron family, with OpenRouter and one Gemini probe in minor supporting roles
(`provider-claims.json` is the per-provider ledger). The human owner launched and
supervised the runs, owns the private corpus, and is the only human author of record;
no human other than the owner contributed content to this tree.

## 1. Major AI uses, purpose, and validation method

| # | AI use (model / system) | Where | Purpose | Validation method (receipt) |
|---|---|---|---|---|
| 1 | ZCode dynamic-workflow orchestration (driver + subagents: topic council, critics, "Results integrity auditor", lane workers) | whole repo; drafts/runs in `.zcode/workflow-runs/`, audit trail in `_audit/audit_20261030/` | Plan and execute the 3-lane deep-dive: corpus build, benchmark sweeps, annotation runs, verdict memo | Independent post-hoc audit: INTEGRITY.md (auditor subagent re-ran every check with scripts preserved in `_audit/audit_20261030/`, incl. `recheck_new_root.py` re-proof at the final path); every claim in DECISION.md carries a file:line or command receipt (DECISION.md footer) |
| 2 | GLM-5.3 (full tier, agent under test) + glm-5.3-flash (user simulator + NL-assertion judge) — z.ai coding plan | `tau2-bench/RESULTS.md` §1 | τ²-bench full 8-domain sweep, harness v1.0.1, 2,344 sims | Offline verify gate: `python -I verify_fullrun.py` → exit 0, 93 PASS / 0 FAIL (RESULTS.md:100; receipt `results/verify_fullrun_output.txt`); metrics computed by the harness's own `pass_hat_k` estimator |
| 3 | grok-4.7 (xhigh agent + low user + judge) via local bridge | `tau2-bench/RESULTS.md` §7 | Second-model batch, harness v2.0.0, 2,852 sims (cross-model + evaluator-A/B leg) | Offline verify gate: exit 0, 176 PASS / 0 FAIL covering BOTH batches (RESULTS.md:189; receipt `results_v2_grok/verify_fullrun_output.txt`); 0 infra-error / 0 duplicate units audited by `repair_grok_gaps.py` (RESULTS.md §7) |
| 4 | GLM-5.3 (33 traces) then nvidia/nemotron-3-ultra-550b-a55b (115 traces) | `trail/RESULTS.md` §1 | TRAIL gold-set annotation, 148/148 released traces, paper's own prompt verbatim (`repo/benchmarking/run_eval.py:16-138`) | Offline verify gate ALL 43 CHECKS PASSED exit 0 (RESULTS.md §4, line 302); repo-scorer crosscheck bit-exact ≤1e-9 PASS (RESULTS.md:42-43); single-model batches reported separately so the annotator-noise floor is visible (0.4419 vs 0.2064 location acc) |
| 5 | Multi-model corpus annotation: grok-4.7 (waves 3 + batch B), nvidia/nemotron-3-ultra / ultra:free / super-120b / 3.5-lightning, glm-5.3-flash, OpenRouter :free | `trail/RESULTS.md` (annotator batches table, lines 136-153) | TRAIL labels over the owner's private-journal corpus (24,787 sessions OK) | Per-file model attribution in every label checkpoint (field `model`); cross-model agreement quantified on same-hash pairs (Jaccard / exact-set / κ, RESULTS.md:125-133); offline verify scripts |
| 6 | glm-5.3-flash (19,342 fresh) + 13,194 migrated v1 labels (v1 run was glm-4.5-flash — `mastscope/annotation/ANNOTATION_NOTES.md:8`) + 4 NVIDIA nemotron-3-super-120b failovers | `mastscope/RESULTS.md` §3 | MAST-14 annotation of 33,889 sessions (100% of the dedup corpus) | MAST released-pipeline contract kept (`repo/MAST/llm_judge_pipeline.ipynb`); verify gate 43 checks exit 0 (RESULTS.md:344-346); tier-agreement crosscheck glm-5.3 vs glm-5.3-flash on 49 pairs (86.9% mean mode agreement, RESULTS.md:231); failover receipts in `provider-claims.json` |
| 7 | nvidia/nemotron-3-ultra-550b (single model) | `mastscope/fullrun/adamast_comparison.md`, RESULTS.md §9 | AdaMAST head-to-head on a 520-session stratified sample | AdaMAST's OWN agreement gate (κ≥0.75) evaluated and reported: κ=0.315 → the induced taxonomy was **self-rejected** (review_required); overlap Jaccard 0.150 reported against their published 0.14 |
| 8 | AI-written statistics & verification code: per-lane `verify*.py`, `corpus/cross_taxonomy_join.py`, `_audit/**` scripts | `corpus/`, `_audit/`, lane dirs | Offline validation of every measured number | `corpus/cross_taxonomy_join.py` has a 29-test suite at 100% line+branch coverage enforced in CI (QZP_FINISH.md §4; `tests/test_cross_taxonomy_join.py`); CROSS_TAXONOMY.md headline numbers independently re-derived by a second minimal script, bit-for-bit agreement (CROSS_TAXONOMY.md header); 3 crash bugs the tests found were fixed (QZP_FINISH.md §4.2) |
| 9 | AI-authored research dossiers and reports (research-sota.md ×3, RESULTS.md generators, DECISION.md, SMOKE.md, errata) | all lane dirs | Literature/competitor scans, results write-ups, council memo, upstream errata (filed as sierra-research/tau2-bench#635) | Every number traces to a gate receipt or generated artifact; DECISION.md footer lists what was read vs re-run this session; upstream errata independently verifiable against the pinned commits named in `UPSTREAM_DOCS_ERRATA.md` |
| 10 | AI-driven corpus builder (deterministic script, no LLM calls in the builder itself) | `corpus/build_corpus.py`, `CORPUS.md` | Read-only inventory/dedup of the owner's 124,327-record (final refresh: 163,681) multi-runtime session corpus | Zero-corruption audit: read-only on every source (atomic writes, checkpointed state); INTEGRITY.md §1 re-parsed the full manifest (0 parse failures, hash/schema census, 10/10 spot-check PASS) |

Minor / attempted uses (ledger only): OpenRouter `nemotron-3.5-lightning:free` sustained
trail corpus load; one Gemini `gemini-3.5-flash` fallback attempt for 4 mastscope
targets, superseded by NVIDIA (`provider-claims.json` entries 1-2).

## 2. What was NOT produced by AI

- **The corpus itself.** The 124,327-record (refresh: 163,681) corpus is the owner's
  real, historical agent-session data harvested read-only from their machines — it is
  *input* data, not generated content (CORPUS.md header; INTEGRITY.md §1).
- **The momentstudio codebase.** The custom e-commerce VAT/coupon rules derive from the
  team's own earlier momentstudio code (`tss/lab/pricing.py` overlap — DECISION.md:66,
  Condition 5); that is human/team prior work, disclosed as inherited estate in
  DECISION.md §6.
- **The evaluated papers and upstream code** (τ²-bench, MAST, TRAIL and their repos) —
  third-party artifacts, pinned by commit everywhere.

## 3. TEAM-new vs inherited AI estate (professor-visible scoping)

- **Inherited AI estate (pre-semester, owner-solo):** everything currently in this
  repository — lanes, corpus, tooling, results, this memo's underlying runs. The 14
  hand-written custom τ² tasks and the momentstudio-derived rule set are part of this
  inherited estate and do **not** clear the novelty bar on their own (DECISION.md
  Condition 1).
- **TEAM-new work (semester plan):** the Condition-1 compositional generator, the
  airline autopsy, same-version cross-model rerun with CIs, dual-control shopper tools,
  discrimination pilot, judge A/B, human 2-annotator audit — i.e., everything in the
  §3 milestone plan of DECISION.md, executed by the 3-4 student team.
- **HUMAN-REQUIRED** (cannot be done or signed by AI): the professor-visible scoping
  confirmation of the split above, and the explicit "not presented in another course"
  check against the TSS-lab pricing/VAT module (Condition 5/7).

## 4. Known limits of the AI-produced evidence

- The paper's exact judge models were never run (τ² paper uses gpt-4.1; MAST paper uses
  o1) — all annotation/agent results are model-substituted and labeled as such
  (DECISION.md §5.3 blockers; RESULTS.md "Paper anchor" caveat).
- Annotator-noise floor is measured, not eliminated: 2.1× spread on location accuracy
  between single-model gold batches (trail RESULTS.md §1); cross-model corpus agreement
  κ is negative for several classes (trail RESULTS.md:129-131).
- The MASTscope gate passed while derived private content leaked into a published
  artifact — a false pass caught only by human-directed audit (DECISION.md §5.3). Gates
  verify what they are told to verify; they are necessary, not sufficient.
- **HUMAN-REQUIRED:** the first human-validated labels in this project (Condition 5:
  2-annotator user-simulator audit) — no lane currently has any.
