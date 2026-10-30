# MAST-14 (fixed) vs AdaMAST (induced) — same 520 sessions

**Experiment:** run the actual AdaMAST toolchain (`adamast generate` + `adamast judge`, repo
`repo/AdaMAST-readonly` @ 3c83d81, v0.2.2.2) on a matched sample of sessions that already carry
MAST-14 labels from the fullrun sweep, and measure how the fixed MAST taxonomy and the
AdaMAST-induced taxonomy relate — vocabulary overlap (vs AdaMAST's published 0.14 cross-domain
Jaccard), per-session mapping agreement, and what each taxonomy sees that the other cannot.

**Verdict up front.** AdaMAST ran for real and induced a 32-code taxonomy from this corpus — and
its own agreement gate **rejected it** (final Fleiss kappa 0.315 < 0.75 target after all 5 rounds;
coverage 0.969). Judged per-session with the README's documented `--allow-review-required` escape
hatch, the two taxonomies agree on which sessions failed at only κ = 0.267, and share vocabulary at
taxonomy-level Jaccard **0.150** — statistically indistinguishable from AdaMAST's published
mean pairwise Jaccard of **0.14 between taxonomies induced for *different domains*** (their Fig. 9a).
The fixed MAST taxonomy and this corpus's induced taxonomy are, by AdaMAST's own metric, as
disjoint as two unrelated domains — while still covering the same three broad failure families.
Neither subsumes the other: they look at different failure surfaces of the same sessions.

---

## 1. What actually ran (receipts)

| stage | command / script | model | outcome |
|---|---|---|---|
| taxonomy induction | `python -m adamast generate --traces traces_sample.jsonl --output taxonomy_run --provider openai --model nvidia/nemotron-3-ultra-550b-a55b --max-output-tokens 16000` (venv `repo/.venv`, package installed editable from the clone) | nvidia/nemotron-3-ultra-550b-a55b (NIM, top tier) | draft OK (32 codes); **first agreement run wiped out by a sustained NIM 429 storm** (vendored pipeline has no backoff — every annotator call failed, kappa collapsed to 0; `generate.log` lines "[!] Alpha discovery error: … 429") |
| agreement gate re-run | `fullrun/adamast/run_agreement_tail.py` — re-invokes the same `adamast.learning.api` functions `generate_taxonomy` uses for the agreement half (`prepare_taxonomy_for_agreement` → `TaxonomyRefinerPipeline` → `build_public_taxonomy`), draft reused unchanged; only addition: throttled (≥4.5 s/call) retrying client injected through `create_provider(client=…)` (documented transport-only deviation) | same | 5/5 rounds completed: kappa 0.300 → 0.384 → 0.622 → 0.539 → **0.315 final**, coverage 0.969, 7 learned rules, 8 anchors → `status: review_required` |
| per-session judging | `fullrun/adamast/run_judge.py` — the CLI's own `SelectionTraceJudge` (mode `default`), `max_trace_chars=12000`, `allow_review_required=True`, checkpointed per trace (`foundation_cli.py`'s `_run_judge` payload schema; transport throttled) | same | **520/520 judged, 0 failures** |
| taxonomy matching | `fullrun/adamast/match_taxonomies.py` — for each of the 32 induced codes, one deterministic (temperature 0) call asking which of the 14 MAST modes is "substantially the same phenomenon"; bipartite maximum matching → Jaccard | same | 6/14 modes matched, **J = 6/(14+32−6) = 0.150** |
| per-session analysis | `fullrun/adamast/analyze_comparison.py` | — | metrics below (`comparison_metrics.json`) |

**Model discipline:** every model call in this experiment (draft, agreement gate, judge, matching)
used the single top-tier model `nvidia/nemotron-3-ultra-550b-a55b` (NVIDIA NIM), one of the four
approved top-tier ids; provider claimed in `tss/tsis-deepdive/provider-claims.json` (entry
`mastscope-adamast`, 2026-10-20T21:3xZ). Gemini was probed and rejected live (OpenAI-compatible
endpoint returns 400 INVALID_ARGUMENT for the key); GLM was left to sibling lanes per the
coordination protocol. MAST-14 labels compared against are the pre-existing fullrun labels
(glm-5.3-flash volume tier, 86.9% mean mode agreement with full tier — see RESULTS.md §5).

## 2. The matched sample

- Population: all 32,540 `ok=true` labels in `fullrun/labels_full.jsonl`.
- Deterministic stratified sample, seed 7, proportional over (session format × any-MAST-flag)
  strata (`fullrun/adamast/build_adamast_sample.py`; allocation in `sample_meta.json`): **520
  sessions, 0 extraction failures**. Composition: claude_journal 416, codex_rollout 58,
  chatgpt_export 26, openai_like 12, zcode_modelio 7, codex_web_tasks 1; 340 (65.4%) carry ≥1
  MAST flag; task_completed=yes 174 (33.5%) — mirroring the full corpus (65.2% flagged, 34.5% yes).
- Trace representation: **identical to the MAST annotation** — the same `extract2.py` +
  `trace2.py` compact trajectory (counts header + first-18/last-66 lines, 12,000-char cap; mean
  7,149 chars/session) was re-extracted per session and written as AdaMAST canonical JSONL
  (`{"problem_id", "task": "", "raw_trajectory", "metadata"}`). Metadata deliberately carries no
  MAST label information, so nothing leaked into induction. `adamast validate` report: 520 traces,
  format `adamast`, 0 empty.

## 3. The induced taxonomy (32 codes, three fixed axes)

AdaMAST inferred the domain itself from the traces: "Software Engineering & Code Quality
Assurance" with subdomains mutation testing, coverage enforcement, CI/CD — an accurate reading of
this corpus's 2026 coding-agent traffic. Full code list in `fullrun/adamast/taxonomy_run/taxonomy.json`;
names summarize the flavor:

- **A — system-level (12):** Output_Truncation_Token_Budget_Exhausted, Context_Window_Overflow,
  API_Rate_Limiting_Throttling, API_Timeout_Or_Empty_Malformed_Response,
  Structured_Output_Contract_Violation, **Repetitive_Looping_Behavior**,
  Task_Refusal_Or_Abandonment, Resource_Contention_File_Lock_Conflict,
  Pre_Execution_Hook_Interference, Inter_Agent_Communication_Loss_Or_Corruption,
  Unhandled_Runtime_Exception, **Instruction_Non_Compliance**
- **B — role-specific (10):** Solver_Incorrect_Logic, **Solver_Missed_Edge_Cases**,
  Solver_Wrong_Approach, Solver_Superficial_Verification, **Solver_Context_Ignorance**,
  Solver_Environment_Assumption, Solver_Incomplete_Deliverable, Solver_False_Positive_Claim,
  Solver_Schema_Noncompliant_Output, Solver_Factual_Inaccuracy_In_Analysis
- **C — domain-specific (10):** Mutation Testing Concept Conflation, Coverage Metric Category
  Error, Quality Gate Bypass Rationalization, CI/CD Hang Root Cause Misattribution, Repository
  Hygiene Policy Drift, Multi-Agent Protocol Violation, Harness-Tooling Contract Mismatch, Audit
  Finding Confirmation Bias, Build System Configuration Drift, Path Normalization Assumption

(Bold = the codes the matching judged substantially the same as a MAST mode.) This is a
*coding-harness operations* taxonomy: half of it (all of C, most of A) is vocabulary MAST-14
simply does not have.

## 4. Taxonomy-level overlap: J = 0.150 vs their published 0.14

Semantic matching (one temp-0 top-tier call per induced code; "substantially the same phenomenon"
criterion; one-to-one maximum matching over the equivalence edges):

| MAST mode | induced code | note |
|---|---|---|
| 1.1 Disobey Task Specification | A.12 Instruction_Non_Compliance | direct |
| 1.3 Step Repetition | A.6 Repetitive_Looping_Behavior | direct |
| 2.5 Ignored Other Agent's Input | B.5 Solver_Context_Ignorance | subagent-context variant |
| 3.1 Premature Termination | A.1 Output_Truncation_Token_Budget_Exhausted | budget-exhaustion variant |
| 3.2 Weak Verification | B.2 Solver_Missed_Edge_Cases | boundary-of-criterion |
| 3.3 No or Incorrect Verification | B.10 Solver_Factual_Inaccuracy_In_Analysis | boundary-of-criterion |

- **6 matched / 14 MAST modes / 32 induced codes → Jaccard 6/40 = 0.150.**
- AdaMAST's paper (§5.2, Fig. 9a): taxonomies induced for six *different* benchmark domains share
  codes at mean pairwise Jaccard **0.14**; projected onto a universal failure backbone it rises to
  **0.50** (Fig. 9b). Our 0.150 sits exactly in that band: by AdaMAST's own adaptivity metric, the
  fixed MAST-14 checklist and this corpus's induced vocabulary are as different as two
  unrelated domains — strong evidence the induction is genuinely adaptive rather than
  rediscovering MAST.
- Backbone analogue: the 6 matched modes span all three MAST families (FC1: 1.1, 1.3; FC2: 2.5;
  FC3: 3.1, 3.2, 3.3) — coarse family coverage 3/3, the same "families align, codes don't" shape
  as their 0.50-backbone result. 12 further induced codes were judged *related-but-not-same* to a
  MAST mode (mostly verification-family, 3.2/3.3), confirming the families-over-codes pattern.
- Unmatched: **8 of 14 MAST modes have no induced counterpart** — the entire inter-agent
  coordination cluster except 2.5 (2.1 Conversation Reset, 2.2 Clarification, 2.3 Derailment,
  2.4 Withholding, 2.6 Action-Reasoning Mismatch) plus 1.2, 1.4, 1.5; **26 of 32 induced codes have
  no MAST counterpart** (all of C, and the infrastructure A-codes: rate limits, timeouts, context
  overflow, hook interference, file-lock contention).

## 5. Per-session mapping (the same 520 sessions, both lenses)

| metric | value |
|---|---|
| sessions with ≥1 MAST mode flagged | 340 (65.4%) |
| sessions with ≥1 induced code fired | 272 (52.3%); `none_apply` on 198 (38.1%) |
| both flag / MAST-only / AdaMAST-only / neither | 212 / 128 / 60 / 120 |
| binary "did this session fail?" agreement | 63.8%; **Cohen's κ = 0.267** (fair) |
| mean per-session Jaccard (induced codes mapped into MAST ids) | 0.334 |
| mean per-session Jaccard (raw vocabularies, union label space) | 0.284 |
| mean labels per flagged session | MAST 2.45 modes vs induced 1.38 codes |

The induced judge is far more conservative than the MAST judge — it demands concrete in-trace
evidence per code (its learned codebook rules for A.7, e.g., require an explicit
INCOMPLETE/empty-deliverable verdict) — so it fires on barely half the sessions MAST flags.

**Top induced codes (incidence):** A.6 Repetitive_Looping_Behavior 22.9%, A.2
Context_Window_Overflow 7.9%, A.7 Task_Refusal 6.5%, A.12 Instruction_Non_Compliance 5.0%, A.3
Rate-Limiting 5.0%, A.4 API-Timeout 4.8%. Mirrors MAST's #1 (1.3 Step Repetition, 43.3%
in-sample) at half the rate, then pivots to infrastructure codes MAST cannot name at all.

**Category cross-tab** (sessions counted once per flagged-MAST-category × fired-induced-axis pair;
MAST category → induced axis): FC1→A 146, FC2→A 87, FC3→A 138; →B 20/15/22; →C 5/4/6. Whatever
MAST family a failure sits in, the induced taxonomy mostly answers with system-level (A) codes;
its B and especially C codes almost never fire at judge time (C: ≤1.3% incidence each) — the
domain-specific half of the induced vocabulary is largely inert on real traffic.

**What each side sees that the other doesn't:**
- 180 sessions are MAST-clean; AdaMAST still fires on 60 of them, led by A.4 API-Timeout (8),
  A.3 Rate-Limit (6), A.7 Refusal (5), A.9 Hook-Interference (3) — infrastructure failures with
  no MAST mode.
- 248 sessions fire no induced code; MAST still flags 128 of them, led by Step Repetition (85),
  Weak Verification (46), Premature Termination (44), Conversation Reset (35), No/Incorrect
  Verification (29) — process- and coordination-level failures the induced taxonomy either lacks
  (2.1) or under-fires (1.3, 3.1, 3.2, 3.3).

## 6. What this means for MASTscope's positioning

1. **The novelty threat is real but bounded.** AdaMAST genuinely induces new vocabulary rather
   than rediscovering MAST (0.150 ≈ their cross-domain 0.14), exactly as its paper claims. But
   the induced vocabulary is bound to the domain that produced it — on this corpus it became a
   coding-harness operations catalog whose 10 domain-specific codes are nearly inert and whose
   8 unmatched MAST modes (the whole inter-agent coordination cluster) are simply absent.
   MASTscope's contribution — one fixed, comparable ruler applied across 63 runtimes and 7
   session formats — is the thing induction cannot provide: cross-harness comparability.
2. **Adaptive ≠ better on messy production corpora.** Run faithfully on real single-operator
   traffic, AdaMAST's own quality gate refused its own taxonomy (kappa 0.315 vs 0.75 target,
   5 rounds, single-annotator-model diversity — a caveat their manifest itself carries). Their
   headline results come from curated benchmark domains; on this corpus the certification layer
   that distinguishes AdaMAST from "prompt an LLM for failure categories" did not pass. A fixed
   taxonomy needs no gate; an induced one is only as strong as a gate that here failed.
3. **The two are complements, not substitutes.** Failure surfaces: MAST = process/coordination/
   verification lens (24.6% of sessions are MAST-only here); induced = infrastructure +
   domain lens (11.5% are AdaMAST-only, dominated by API/timeout/hook codes MAST cannot express).
   This empirically supports AdaMAST's own "fixed axes, adaptive vocabulary" thesis — with MAST-14
   playing the stable-backbone role across the fleet, and per-domain induction as an optional
   refinement layer on top. MASTscope's write-up should cite this run: the fixed ruler survives
   contact with the adaptive alternative; the alternative doesn't cover the ruler's ground, fails
   its own gate here, and transfers across domains at the same 0.14 Jaccard that separates it
   from MAST itself.

## 7. Limitations (stated, not hidden)

- Taxonomy status is `review_required`; all judge/matching numbers describe an *uncertified*
  induced taxonomy (used via the README's `--allow-review-required`). A taxonomy that passed the
  gate might agree with MAST more (or less) — untested.
- Matching criterion is conservative ("substantially the same phenomenon", one-to-one). At the
  looser "related" threshold 12 more induced codes map to MAST modes (mostly FC3), i.e. 0.150 is
  a lower-bound-style reading of code overlap; the family-level picture (all 3 families covered)
  is threshold-robust.
- MAST labels are flash-tier (86.9% mode agreement with full tier), and the two taxonomies were
  judged by different model families (GLM vs NIM) — cross-taxonomy κ 0.267 absorbs both label
  noise and genuine lens differences; it is an upper-noise comparison, not a gold standard.
- Single annotator model for AdaMAST's 4 "independent" annotators (all NIM ultra; manifest
  records `annotator_model_diversity: single-model`, final kappa 95% CI [0.23, 0.63] over 32
  rated subjects), per the single-model-per-batch instruction — depresses measured kappa by
  design (no annotator-model diversity).
- AdaMAST's draft stage analyzes a 20-trace stratified subsample of the 520 (`Config
  .TRACES_FOR_ANALYSIS = 20`, `draft.py:53`) — their pipeline's design, not a shortcut taken here.

## 8. Artifacts

- `fullrun/adamast/traces_sample.jsonl` — 520 canonical traces (**contains session text**; local
  to the owner's machine, not for publication; regenerate via `build_adamast_sample.py`)
- `fullrun/adamast/taxonomy_run/` — `taxonomy.json` (32 codes + codebook), `manifest.json` (gate:
  kappa 0.315, coverage 0.969, review_required), `taxonomy.draft.json`, agreement artifacts,
  `taxonomy.html`
- `fullrun/adamast/judgments.json` + `judgments_ckpt.jsonl` — 520 per-session diagnoses (code,
  evidence, confidence, severity per fired code)
- `fullrun/adamast/code_matching.json` — per-code matching edges, matching, Jaccard 0.15
- `fullrun/adamast/comparison_metrics.json` — all §5 tables
- `fullrun/adamast/build_adamast_sample.py`, `run_agreement_tail.py`, `run_judge.py`,
  `match_taxonomies.py`, `analyze_comparison.py`, `generate.log`, `agreement_tail.log`,
  `judge.log`, `match.log`
- Note: `repo/.venv` was recreated for this run (per the recreation commands recorded in
  `repo/venv-removed-2026-10-19.txt`); remove it again before publishing the repo folder.
