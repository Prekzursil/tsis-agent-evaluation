# DECISION — TS/IS deep-dive council verdict (semester project topic)

Date: 2026-10-30. This memo supersedes the 2026-10-19 DECISION.md (that round's
TRAIL-NO-GO / MASTscope-GO ordering is obsolete: TRAIL has since completed its full run and
gate — RESULTS.md generated 2026-10-24 — and MASTscope's gate was subsequently shown to be a
false pass on derived-artifact leakage). Inputs: the council decision record and lane result
objects supplied with the ask; lane dossiers `tss/tsis-deepdive/tau2-bench/research-sota.md`,
`tss/tsis-deepdive/trail/research-sota.md`, `tss/tsis-deepdive/mastscope/research-sota.md`
(dossier spot-checks re-read this session, see below); per-lane `RESULTS.md` read in full this
session (all three) with headline real metrics reproduced in §5.

---

## 1. Verdict table (council's own one-line reasons)

| Topic | Verdict | One-line reason |
|---|---|---|
| **tau2-bench** (τ²-bench, Sierra Research — arXiv:2506.07982, MIT, github.com/sierra-research/tau2-bench) | **GO-WITH-CONDITIONS → WINNER** | Only lane where every course deliverable is evidenced by gated runs the council re-verified first-hand (`python -I verify_fullrun.py` → `VERIFY OK -- all checks passed`, exit 0, covering the 2,344-sim GLM v1.0.1 and 2,852-sim grok v2.0.0 batches); zero private content so all 3–4 teammates touch and demo everything; every improve-leg gap the critics named is buildable in one semester; measured demo-scale cost with a proven $0 free-tier path. |
| **TRAIL** (Patronus AI — arXiv:2505.08638) | **GO-WITH-CONDITIONS** (viable fallback, not winner) | Benchmark reproduction leg is genuinely team-executable and gated (council re-ran `verify_fullrun.py` → ALL 43 CHECKS PASSED, exit 0; gold pass measured cheap at 148 calls / 4.4M tokens / 1645s) and TRAIL-1.1 hygiene is citable — but the novelty critic's strong verdict rests on the 24,787-session corpus half, which is one member's PRIVATE journals (untouchable by teammates, unanalyzed private-text egress to grok/NVIDIA/OpenRouter, 10,331 label files embedding the OS username), sits at the lane's own demonstrated annotator-noise floor (single-model location acc 0.4419 vs 0.2064), and its SWE split structurally needs a ≥1M-context funded key that failed auth in every recorded probe; the flagship "beat official joint accuracy" leg is unattempted and research-risky by a semester deadline. |
| **MASTscope** (MAST — arXiv:2503.13657) | **NO-GO** | Not a team course project: the flagship corpus is one member's private journals (banned from the graded demo by the lane's own protocol, no teammate access, o1/κ=0.77 headline reproduction never ran — OPENAI key 401 blocker on disk), the tooling space is occupied by the same org's AdaMAST/ATLAS, repo code is unlicensed — and the council verified first-hand that `mastscope/fullrun/adamast/judgments.json` contains verbatim private-trace content (owner project names, "20 findings A-01..A-20, 19 patches P0-P3") that PASSED the 43-check gate, i.e. the gate is a false pass on derived-artifact leakage; salvageable pieces (AdaMAST head-to-head) are owner-solo prior work, not team-rebuildable. |

---

## 2. Winner and the council's reasoning

**Winner: tau2-bench (τ²-bench, Sierra Research — arXiv:2506.07982, MIT,
github.com/sierra-research/tau2-bench).**

The council's selection logic, in its own terms (ask: council decision, ranking entry 1):

1. **Every course deliverable is already evidenced by gated runs.** The council re-verified
   first-hand this session: `python -I verify_fullrun.py` → `VERIFY OK -- all checks passed`,
   exit 0, covering BOTH batches on disk — the 2,344-sim GLM (v1.0.1 @ 96a3ef9) batch
   (receipt: RESULTS.md:100, `results/verify_fullrun_output.txt`, 93 PASS / 0 FAIL) and the
   2,852-sim grok-4.7 (v2.0.0 @ cc1df47) batch (receipt: RESULTS.md:189,
   `results_v2_grok/verify_fullrun_output.txt`, 176 PASS / 0 FAIL). Gate receipts read this
   session at the cited lines; the exit-0 runs themselves are the council's verification,
   not re-run for this memo.
2. **Zero private content → full team access.** No other lane has this property: all 3–4
   teammates can touch and demo the entire asset. (Contrast: TRAIL's corpus half is private
   journals; MASTscope's flagship corpus is private AND its lane currently leaks derived
   private-trace content past a green gate — §5.3.)
3. **Every improve-leg gap the critics named is buildable in one semester.** (a) Airline
   COMMUNICATE autopsy — airline is the only 50/50 `[DB, COMMUNICATE]` domain
   (research-sota.md:62, §1.4 correction, re-read this session); (b) compositional
   coupon/VAT generator on grep-verified-uncovered rules — 0 matches for coupon/VAT/tax in
   shipped retail policy and tools (research-sota.md:172, re-verified on the v2.0.0 clone);
   (c) same-version cross-model rerun (de-confounding RESULTS.md:123-136); (d)
   substring-vs-semantic judge A/B on one v2.0.0 flag (RESULTS.md:104 pins
   `communicate_scoring=substring`).
4. **Cost is measured, with a proven $0 path.** Demo-scale run: 56 sims / 1906.6s / 481
   calls (RESULTS.md:95); the free-tier GLM path already carried a full 8-domain × k=4
   sweep. Paper-protocol frontier pricing is budgeted explicitly in Condition 6.

### Where critics disagreed, and how each dispute was adjudicated

| Dispute | Critic position | Adjudication (binding condition) |
|---|---|---|
| Do the inherited 14 hand-written custom tasks clear the novelty bar? | Novelty critic: no — the hand-written tasks don't clear it (council ranking, entry 1). | **Condition 1**: the semester must BUILD the compositional {f_init, f_sol, f_assert} generator with automatic solvability verification, ≥100 generated tasks passing the harness's full validation (32-check precedent at RESULTS.md:41). |
| Is the evaluator-artifact finding a benchmark-validity claim yet? | Validity critics: today it generalizes from n=1 self-authored domain (the custom e-commerce autopsy, RESULTS.md:51-64 and §7.3). | **Condition 2**: run the COMMUNICATE-substring autopsy on the SHIPPED airline domain (only 50/50 [DB, COMMUNICATE] domain, research-sota.md:62) BEFORE quoting the finding; report raw-vs-semantic side by side if confirmed. |
| Is the cross-model table a model-ranking claim? | Statistics critic: no — it mixes v1.0.1 (GLM) and v2.0.0 (grok) rows in one table (RESULTS.md:123-136, confound admitted in the file itself). | **Condition 3**: one harness version per comparison, ever; re-run the losing arm so both models share one version; CIs on every pass^k. |
| Can the new domain support a benchmark claim despite the saturation charge (CRAB-Bench)? | Saturation critics: prior-session airline/retail pass^1 0.87-0.89 says current models already saturate. | **Condition 4**: discrimination pilot (≥2 frontier models × 3 seeds × pass^1/pass^4 with CIs + power analysis sized from the existing per-task k=4 data: 2,344 + 2,852 sims on disk); if it still saturates, fall back honestly to the benchmark-validity study — never a reskin claim. |
| Is a "reproduction" claimable without frontier keys? | Reproduction/budget critics: paper-protocol gpt-4.1 is paywalled; all frontier keys failed auth in recorded probes. | **Condition 6**: budget ownership in USD by funding instrument and named payer (~$300-400 pilot vs proven $0 path); if no funded key, all reproduction claims are framed model-substituted. |
| Whose data may the team touch? | Privacy critic: TRAIL's corpus half and MASTscope's flagship corpus are one member's private journals (TRAIL: unanalyzed private-text egress + 10,331 label files embedding the OS username; MASTscope: banned from graded demo by its own protocol). | Winner selection itself — tau2's zero-private-content lane wins the joint criterion; TRAIL kept as fallback on its gated public-repo leg only (Condition set + §5.2); MASTscope NO-GO. |
| Is MASTscope's green gate proof of a clean lane? | Privacy/integrity critic: no — verbatim private-trace content in `fullrun/adamast/judgments.json` PASSED the 43-check gate (council, first-hand). | **NO-GO**. This memo re-verified the artifact this session: the file exists and contains the verbatim string `20 findings A-01..A-20` (grep, §5.3) — the gate is a false pass on derived-artifact leakage; salvageable pieces are owner-solo prior work. |
| Is the inherited AI estate the team's work? | Provenance critic: no — e-commerce VAT/coupon rules derive from the team's own momentstudio codebase (tss/lab/pricing.py overlap); no AI_USAGE.md exists today (verified by find across tsis-deepdive, per the council). | **Condition 5**: provenance pack before week 3 — AI_USAGE.md per the tss/lab standard, momentstudio derivation disclosure, TEAM-new vs inherited scoping, and a "not presented in another course" check vs the TSS-lab pricing/VAT module. |
| Environment: whose pytest is truth? | Environment critic: v2.0.0 @ cc1df47 ships with 430 pytest failures on Windows (SMOKE.md §2.2, line 67: `run 1: 430 failed, 2639 passed, 83 skipped, 57 warnings, 227 errors`). | **Condition 8**: day-1 standardization — WSL/Linux or a pinned green commit; v1.0.1 for the reproduce leg vs v2.0.0 for the audit/A-B leg decided explicitly. |
| Demo risk at defense time. | Course critic: every lane hit provider failures mid-run (ledger storm, 429s, host kills — RESULTS.md §7.4, trail RESULTS.md §1/§3 caveats). | **Condition 10**: demo insurance — offline gold-replay (10/10 PASS, exit 0; SMOKE.md:159) plus a recorded fallback inventoried in advance; no graded demo depends on a live key. |

---

## 3. 14-week milestone plan (council-issued)

| Weeks | Milestone |
|---|---|
| **1–2** | Pin, environment, disclosure, team split: pin v1.0.1 @ 96a3ef9 for the reproduce leg and v2.0.0 @ cc1df47 (substring + semantic communicate_scorer arms) for the validity/A-B leg; standardize on WSL/Linux (v2.0.0 pytest not green on Windows — 430 failures, SMOKE.md §2.2); write AI_USAGE.md + momentstudio-derived-rules disclosure + team-new-vs-inherited scoping + "not presented in another course" check vs TSS-lab; every member re-runs the 10-task pilot on the proven free-tier/$0 path; assign 4 workstreams — (A) harness/repro+gates, (B) compositional generator, (C) dual-control domain+demo, (D) evaluation/statistics+human audit+budget (owner named, USD per leg). |
| **3–4** | Reproduce leg frozen + de-confound + airline autopsy: same-version cross-model rerun (both models on ONE harness version, fixing the v1.0.1-vs-v2.0.0 confound admitted at RESULTS.md:123-136); regenerate pass^k tables with bootstrap CIs; run the substring-artifact autopsy on SHIPPED airline (the only 50/50 [DB, COMMUNICATE] domain) to lift the finding beyond the team's own 14 tasks; verify gate green on the team repo. |
| **5–6** | Contribution I (the generator): compositional {f_init, f_sol, f_assert} task generator over coupon/VAT/returns rule interactions (place-of-supply, reverse charge, stacking exclusivity, cross-border thresholds) with automatic solvability verification on the telecom manager.py:197 pattern; ≥100 tasks, all passing the harness's full validation (32-check precedent: RESULTS.md:41); fix the current-date anchor authoring bug (RESULTS.md:62). |
| **7–8** | Contribution II (dual-control + difficulty): user-side shopper-app tools (apply coupon in cart, pay VAT difference, scan receipt, open return portal) + user_db mirroring customer-visible state; difficulty calibration (difficulty = #subtasks) until at least one frontier model sits in a discriminating band (no domain >~85% pass^1); discrimination pilot v1 (2 models × 3 seeds). |
| **9–10** | Rigorous evaluation: full discrimination pilot (≥2 frontier models × ≥3 seeds, pass^1/pass^4 with CIs) plus statistical-power analysis sized from the existing per-task k=4 data (2,344 GLM + 2,852 grok sims already gated on disk); substring-vs-semantic-judge A/B on one harness version (v2.0.0 flag, RESULTS.md:104) quantifying the validity fix Sierra shipped; 2-annotator user-simulator audit on a task sample (person-hours divided across all members); failure taxonomy including the dual-control signature (agent never steers user to user-side write — RESULTS.md:66). |
| **11–12** | Analysis, writeup, demo hardening: unconfounded cross-model deltas, evaluator-era comparison table, per-model cost accounting; live tau2 play demo of the new domain + offline gold-replay fallback (10/10 proven, SMOKE.md §4) + recorded-fallback inventory; upstream contributions (evaluator/errata PR) finalized; final-report tables drafted. |
| **13–14** | Defense + release: reproduction-vs-paper table with model-substitution caveat explicit; contribution release (generator + domain + evaluator analysis); limitations (saturation risk, judge dependence); demo rehearsal; scrub the 35 username-embedding files before any repo sharing; verify gate re-run GREEN at submission (no stale artifacts). |

---

## 4. Hard conditions (all binding on the tau2-bench GO)

1. **BUILD the contribution this semester** — compositional {f_init, f_sol, f_assert}
   coupon/VAT/returns task generator with automatic solvability verification
   (broken-before/fixed-after/no-prefix-fix, pattern at
   `src/tau2/domains/telecom/tasks/manager.py:197`) — at least 100 generated tasks passing
   the harness's full validation. The inherited 14 hand-written tasks do not clear the
   novelty bar.
2. **Run the COMMUNICATE-substring autopsy on the SHIPPED airline domain** (the only 50/50
   [DB, COMMUNICATE] domain — research-sota.md §1.4 correction, line 62) BEFORE quoting the
   evaluator-artifact finding as a benchmark-validity claim — today it generalizes from n=1
   self-authored domain; if airline shows the same artifact, report raw-vs-semantic side by
   side.
3. **One harness version per comparison, ever** — never mix v1.0.1 and v2.0.0 rows in one
   cross-model table (RESULTS.md:123-136 confound); re-run the losing arm so both models
   share one version before any model-ranking claim, and report confidence intervals on
   every pass^k.
4. **Discrimination pilot before any benchmark claim** — at least 2 frontier-tier models ×
   3 seeds × pass^1/pass^4 with CIs, plus a power analysis sized from the existing per-task
   k=4 data (2,344 + 2,852 sims already on disk); if the new domain still saturates, fall
   back honestly to the benchmark-validity study, never a reskin claim.
5. **Human validation leg** — 2-annotator user-simulator error audit on the new domain
   (target no worse than telecom's 16%/6% critical), with the ~110-120 min/trace
   person-hours scheduled and divided across team members in the project plan — no lane
   currently has a single human-validated label.
6. **Budget ownership in USD**, classified by funding instrument and named payer: ~$300-400
   at paper gpt-4.1 rates for the discrimination pilot vs the proven $0 free-tier path;
   reconcile paper-protocol USD pricing with measured reality, and price all judge/user-sim
   calls with --dry-run before committing. If no funded frontier key, all reproduction
   claims are framed model-substituted.
7. **Provenance pack BEFORE week 3** (does not exist today — verified by find across
   tsis-deepdive, per the council): AI_USAGE.md per the tss/lab standard, disclosure that
   e-commerce VAT/coupon rules derive from the team's own momentstudio codebase (tss/lab/
   pricing.py overlap), professor-visible scoping of TEAM-new vs inherited AI estate, and an
   explicit "not presented in another course" check against the TSS-lab pricing/VAT module.
8. **Environment standardization on day 1** — v2.0.0 @ cc1df47 ships with 430 pytest
   failures on Windows (SMOKE.md §2.2, line 67): the team runs WSL/Linux or a pinned green
   commit, and the graded pin is stated once and used identically by every member (decide
   v1.0.1 for the reproduce leg vs v2.0.0 for the audit/A-B leg explicitly).
9. **Privacy hygiene on the winner** before any sharing or publication: scrub the 35 tau2-bench
   files embedding the OS username (grep-verified this session — count independently
   reproduced for this memo: `grep -rlI "Prekzursil" . | wc -l` → **35**), keep the lane at
   zero private content, and re-run the verify gate GREEN at submission — no stale-artifact
   end state.
10. **Demo insurance** — the live tau2 play demo always has the offline gold-replay (10/10
    proven, SMOKE.md §4/line 159) plus a recorded fallback inventoried in advance; no graded
    demo depends on a single live API key.

---

## 5. Per-lane appendix

### 5.1 tau2-bench (WINNER) — `tss/tsis-deepdive/tau2-bench/`

**Gate/audit status:** verify gate GREEN for BOTH batches — v1.0.1 GLM batch: exit 0,
93 PASS / 0 FAIL, last line `VERIFY OK -- all checks passed` (RESULTS.md:100; receipt
`results/verify_fullrun_output.txt`); grok-4.7 v2.0.0 batch: exit 0, 176 PASS / 0 FAIL
covering BOTH batches (RESULTS.md:189; receipt `results_v2_grok/verify_fullrun_output.txt`).
Lane record: `gateGreen: true, auditVerified: true, auditFailures: []`. The exit-0 runs are
the council's first-hand verification (ask); receipts read at the cited lines this session.

**Ran end-to-end:** YES, complete (`fullRun.completed: true, partial: false`).
- GLM-5.3 (agent) + glm-5.3-flash (user), harness v1.0.1 @ 96a3ef9, seed=300, k=4: full
  8-domain sweep, 2,344 sims, zero infra-error sims after repair passes; 68,963 counted
  calls, 768.0M prompt + 13.9M completion tokens (RESULTS.md:82).
- grok-4.7 xhigh (agent) + grok-4.7 low (user), harness v2.0.0 @ cc1df47,
  `communicate_scoring=substring` pinned (RESULTS.md:104): 8 domains × k=4 = 2,852 sims,
  0 infra errors, 0 duplicate units; 44,265 counted calls (lower bound), 368.4M prompt +
  6.5M completion tokens (RESULTS.md:172). Resumed via the harness's own auto-resume
  checkpoints after three owner/host process deaths — no work redone (RESULTS.md:106).

**Headline REAL metrics** (RESULTS.md §1 lines 16-25 = GLM v1.0.1 pass^4; §7.1 lines
110-119 = grok v2.0.0 pass^4):

| Domain | GLM v1.0.1 pass^4 | grok v2.0.0 pass^4 |
|---|---|---|
| mock | 0.60 | 0.80 |
| airline | 0.86 | 0.60 |
| retail | 0.7281 | 0.5789 |
| telecom | 0.8421 | 0.5351 |
| telecom-workflow | 0.8333 | 0.6053 |
| banking_knowledge | 0.1649 | 0.0825 |
| custom e-commerce | 0.5714 (ecommerce2, 14 tasks) | 0.7857 (ecommerce3, 14 tasks) |
| intake | — (not in v1.0.1) | 0.195 |

Cross-model table is version-confounded (v1.0.1 vs v2.0.0) — admitted at RESULTS.md:123-136
and made a hard condition (§4.3). Custom-domain autopsy, both models: ALL failures are
COMMUNICATE-substring misses with DB correct and zero wrong writes (GLM: 13/14 failing
units, RESULTS.md:51-64; grok: 12/12, RESULTS.md:140-148) — the evaluator-artifact finding
behind Condition 2. Dual-control signature failure (agent never steers user to user-side
write) measured on ecommerce_poc: RESULTS.md:66.

**Blockers:** none recorded (`blockers: []`). Environment notes: litellm has no price map
for glm-5.3/grok-4.7 on these endpoints, so cost is not persisted (measured tokens only,
RESULTS.md:86,174); Windows save collisions + mock auto-resume upstream defect + ledger
storm documented at RESULTS.md §7.4; 35 lane files still embed the OS username (§4.9).

**Key competitor threats** (full list: `tss/tsis-deepdive/tau2-bench/research-sota.md`):
CRAB-Bench + RUSE (arXiv:2606.01815) — strongest 2026 attack, argues τ/τ² user sims are
cooperative templates and benchmarks "largely saturated"; MM-tau-p2 (arXiv:2603.09643) —
persona-adaptive multimodal dual-control BUILT ON τ² telecom+retail (overlaps the
expert-novice-gap angle); UserProxyBench (arXiv:2609.38043) — user-proxy choice alone moves
reward ~15pts, 24.4% of successful episodes violate user spec; UserBench (2507.22034);
VitaBench (2509.26490 — its own table credits τ² as the only full dual-control prior);
official τ³/τ-i18n line in-repo (τ-Voice 2603.13686, τ-Knowledge 2603.04370, v2.0
i18n+intake) closes voice/RAG/multilingual/entity ground; plus τ-bench (2406.12045),
ToolSandbox, IntellAgent/FlowBench/APIGen-MT, Toloka extension (single-control, no code).

### 5.2 TRAIL (fallback) — `tss/tsis-deepdive/trail/`

**Gate/audit status:** verify gate GREEN — council re-ran `verify_fullrun.py` → ALL 43
CHECKS PASSED, exit 0 (ask: council ranking entry 2); RESULTS.md §4 lists the exact
command (`.venv/Scripts/python.exe verify_fullrun.py`, "exit 0 required", line 302). Lane
record: `gateGreen: true, auditVerified: true, auditFailures: []`. Not re-run for this memo.

**Ran end-to-end:** YES, complete (`fullRun.completed: true, partial: false`). Gold set:
all 148 released traces (117 GAIA + 31 SWE) annotated with the paper's own prompt — glm-5.3
33 traces before plan saturation, nvidia/nemotron-3-ultra-550b 115 completing 148/148 in
1645s (RESULTS.md:23). Corpus: 40,798/40,798 unique files checkpointed; 24,787/24,949
eligible sessions annotated OK (99.4%); 15,849 not_a_session; 161 unparseable + 1 gone
counted honestly (RESULTS.md:104-110, 177-182). 27,883 calls, 432.2M prompt + 83.4M
completion tokens (RESULTS.md:312).

**Headline REAL metrics** (RESULTS.md §1, lines 31-37): union-148 gold agreement —
weighted F1 **0.3683**, location acc **0.2472**, joint acc **0.0905** (GAIA 0.3697/0.3104/
0.1145; SWE 0.3057/0.0086/0.0000); single-model glm-5.3 (33): 0.3953 / **0.4419** / 0.1251;
nemotron-ultra (147): 0.3537 / **0.2064** / 0.0709 — the two single-model batches differ by
2.1× on location accuracy, the lane's own annotator-noise floor the council cites. Corpus
distribution: Tool Output Misinterpretation #1 (6,718 labels, 24.9% of traces), Formatting
5,993, Instruction Non-compliance 5,986 (23.4%); by root Reasoning 58.5% / System Execution
23.0% / Planning 18.5%; HIGH impact 38.9%; 79.5% of sessions carry ≥1 label; mean 2.22
labels/session (RESULTS.md:137-191). Repo-scorer crosscheck bit-exact ≤1e-9 PASS
(RESULTS.md:42-43).

**Blockers:** all five provider keys failed auth/credit checks in the lane's recorded
session — openai 401, gemini API_KEY_INVALID, openrouter 402 insufficient credits,
anthropic invalid x-api-key, z.ai token expired (lane record: blockers); paper-parity SWE
annotation structurally needs a ≥1M-context funded key. Structural course blockers: corpus
half is private journals (no teammate access, 10,331 label files embedding the OS username,
unanalyzed private-text egress — council record); flagship "beat official joint accuracy"
leg unattempted.

**Key competitor threats** (full list: `tss/tsis-deepdive/trail/research-sota.md`): MAST
(arXiv:2503.13657, NeurIPS 2025) — cited baseline; **AdaMAST (arXiv:2607.16387)** and
**ATLAS (same org's repo)** — occupy adaptive taxonomies + runtime diagnosis, ATLAS claims
κ=0.725 vs TRAIL expert annotations; Agentic CLEAR (IBM, ACL 2026, `pip clear-eval`) —
already ships OTel ingestion + multi-level judge + dashboard, closing ~70% of the
runner+dashboard idea; Who&When (2505.00212, ICML 2025) + AgenTracer/AgentDebugX/DCFA;
AgentDebug (2509.25370); Agent-as-a-Judge (2410.10934); GLIDER; Percival/AlphaEval/Potato/
Phoenix-Langfuse. AlphaArena recorded as NOT an arXiv paper (API 0 hits) — earlier "not
found" dossier line corrected.

### 5.3 MASTscope (NO-GO) — `tss/tsis-deepdive/mastscope/`

**Gate/audit status:** verify gate GREEN on paper — `verify_fullrun.py` VERIFY OK, 43
checks passed, exit 0 (RESULTS.md:344-346; lane record `gateGreen: true`) — **but
`auditVerified: false`**, and the council verified first-hand this session that
`fullrun/adamast/judgments.json` contains verbatim private-trace content that PASSED that
gate (a false pass on derived-artifact leakage). **Re-verified for this memo**: the file
exists and `grep` finds the verbatim string `20 findings A-01..A-20` in it (run this
session). Residual auditFailures (lane record): 4/33,889 targets z.ai-content-filter-blocked
(ids named); 222/122,733 privacy-scan records (0.18%, giant binaries) unscanned but
resumable via `scan_skipped.py`; `__pycache__` regenerable local caches excluded by the
gate's suffix set; `sweep_status2.json` last-writer-wins with cumulative accounting moved to
`sweep2_status_history.jsonl`.

**Ran end-to-end:** YES, complete (`fullRun.completed: true, partial: false`). 33,889/
33,889 annotation targets done: 32,540 ok (13,194 migrated v1 by content hash + 19,342
fresh glm-5.3-flash + 4 NVIDIA failover) + 1,349 parse-fail counted as annotated, 0 pending
(RESULTS.md §3, lines 81-98); whole-corpus privacy scan 122,511/122,733 records (99.8%,
219.4 GB) (RESULTS.md:61). Plus a real AdaMAST comparison run: 520-session stratified
sample, single model nemotron-3-ultra-550b, gate κ=0.315/coverage 0.969 → review_required;
taxonomy overlap with MAST-14 Jaccard 0.150 vs their published 0.14; per-session detection
κ=0.267 (RESULTS.md §9, lines 329-338).

**Headline REAL metrics** (RESULTS.md §4, lines 102-125): top modes — 1.3 Step Repetition
**43.14%** incidence (paper 15.7%), 3.1 Premature Termination **29.15%** (paper 6.2%), 3.2
Weak Verification 19.23%, 3.3 No/Incorrect Verification 19.00%, 2.1 Conversation Reset
14.89%; category occurrence FC1 37.2% / FC2 20.6% / FC3 42.1% vs paper Fig.4 41.8/36.9/21.3
— verification failures overtake inter-agent misalignment in a single-harness fleet;
task_completed=yes 11,209 (34.5%); 21,205 traces (65.2%) carry ≥1 flagged mode; mean 2.45
modes/flagged trace; 52,034 total yes-labels. Tier agreement glm-5.3 vs glm-5.3-flash (49
pairs): 86.9% mean mode agreement, task_completed 95.5% (RESULTS.md §5, line 231).

**Blockers:** the paper's exact judge model (o1, temp 1.0) NOT RUN — OPENAI key 401,
`annotate_trace.py` exit 3 recorded in `annotation/annotation_blocker.json`; κ=0.77
headline unreproduced (annotation executed on glm-4.5-flash/GLM tiers). Structural course
blockers (council): flagship corpus is one member's private journals — banned from the
graded demo by the lane's own protocol, no teammate access; repo code unlicensed;
salvageable pieces are owner-solo prior work.

**Key competitor threats** (full list: `tss/tsis-deepdive/mastscope/research-sota.md`):
**AdaMAST (arXiv:2607.16387, same org; Apache-2.0; PyPI `adamast`) — the killer**: adaptive
per-system taxonomies + agreement gate κ≥0.75 + dashboard + live Claude Code/Codex hooks +
7-format trace loader — kills the adaptive-annotator, dashboard, harness-ingestion,
regression-tracking, best-of-N and MAST-as-prior angles; **ATLAS repo (same org;
Apache-2.0)** hosts the paper pipeline + eval artifacts (OfficeQA 44.4→51.9, Circle-Packing
0.997 of AlphaEvolve, TB2.0 judge 89.9% — headline numbers not recomputable from repo
alone). Also: Who&When (2505.00212), FAMAS (2509.13782), AgentTracer, TRAIL-as-yardstick,
AgentDebug (2509.25370), hugomn/mast-taxonomy-production-telemetry (direct prior art for
"MAST on real private logs", 23.6k production runs), SyFI TraceLab (2606.30560),
MPIsaac-Per/claude-code-ops-audit.

### 5.4 xlsx-ready lines (winner)

```
Paper link     | https://arxiv.org/abs/2506.07982 (τ²-bench, Sierra Research — MIT, github.com/sierra-research/tau2-bench)
Idea (1 line)  | Reproduce the dual-control τ²-bench agent-user evaluation on one pinned harness version and extend it with a compositional auto-verified coupon/VAT/returns task generator (>=100 tasks), user-side shopper-app tools for true dual-control e-commerce, a >=2-frontier-model x 3-seed discrimination pilot with CIs and a power analysis, and a benchmark-validity study (COMMUNICATE substring-vs-semantic judge A/B + shipped-airline autopsy).
```

---

*Provenance: verdicts, one-line reasons, conditions, plan and lane statuses from the council
decision + lane records supplied with the ask. Read this session: all three lane RESULTS.md
files in full (cited by line); tau2-bench SMOKE.md §2.2 (430 pytest failures, line 67) and
gold-replay 10/10 (line 159) via grep; tau2-bench research-sota.md §1.4 airline correction
(line 62) and coupon/VAT grep-verification (line 172) via grep. Run this session:
`grep` confirming verbatim private-trace content `20 findings A-01..A-20` in
`mastscope/fullrun/adamast/judgments.json`; `grep -rlI "Prekzursil" . | wc -l` → 35 files
in the tau2-bench lane. Not re-run for this memo (reported as recorded, with receipts): all
lane verify-gate exit-0 runs, API-key 401 probes, and council first-hand re-verifications
cited above. This file supersedes the 2026-10-19 DECISION.md.*
