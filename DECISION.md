# DECISION — TS/IS deep-dive council verdict (semester project topic)

Date: 2026-10-30. This memo supersedes the 2026-10-19 DECISION.md (that round's
TRAIL-NO-GO / MASTscope-GO ordering is obsolete: TRAIL has since completed its full run and
gate — RESULTS.md generated 2026-10-24 — and MASTscope's gate was subsequently shown to be a
false pass on derived-artifact leakage). Inputs: the council decision record and lane result
objects supplied with the ask; lane dossiers `tss/tsis-deepdive/tau2-bench/research-sota.md`,
`tss/tsis-deepdive/trail/research-sota.md`, `tss/tsis-deepdive/mastscope/research-sota.md`
(dossier spot-checks re-read this session, see below); per-lane `RESULTS.md` read in full this
session (all three) with headline real metrics reproduced in §5.

**Final form (2026-11-02):** this revision appends the **extension round** (§10 —
anchor-lane grok sweep closed at **2,852/2,852** and gated; the TRAIL
hierarchical-judge experiment with a same-model flat control on the public 148-trace
gold set; findings status; insights pointer), records the owner's **DECISION on a
3-in-1 combined presentation, anchored on tau2-bench** (§11 — integrated blueprint,
18-slide two-presenter outline, demo plan, feasibility, risks, recommendation,
xlsx-ready lines for both the 3-in-1 and the single-topic registration), and
**refreshes the hard conditions** (§4 → Conditions 1–13). Sections 1–3, 5–9 stand as
previously written; §5.2's gate-reconciliation note (2026-11-01) is folded into §10.

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

**Extension-round additions (2026-11-02; binding exactly like 1–10):**

11. **Quote the judge result with its control, always.** The hierarchical-judge headline
    (§10.2) is NOT a chunking claim: the 0.0905 → 0.2190 joint-accuracy lift is ~93% model
    effect — the same-model flat control (grok-4.7 xhigh, paper prompt + flat capping
    ladder) already scores 0.2065 of the 0.2190 endpoint, and the architecture's residual
    +0.0125 is not significant (Wilcoxon p=0.80, n=148). Chunking's real, significant
    effect is **location accuracy** (+0.155, 0.3858 → 0.5406, Wilcoxon p=1.1e-08), at the
    cost of weighted F1 (0.4920 → 0.4489, over-prediction: 7.08 vs 5.68 errors/trace) and
    1.62× tokens/trace. No slide, table, or report quotes any of these numbers without the
    same-model control adjacent. Receipt: `trail/fullrun_hierarchical_judge.md` §2–§3.
12. **Corpus-wide TRAIL class shares are unstable — quote rankings, not rates.** The
    full-N sensitivity verdict is **"STILL UNSTABLE AT FULL N"** (5/5 top-5 class shares
    and 3/3 impact shares at C fall OUTSIDE D's bootstrap 95% CI; L1(C,D)=0.4898 vs
    L1(B,C)=0.0861 — `trail/fullrun/sensitivity.md` §"VERDICT AT FULL N", lines 161-163;
    restated in the regenerated trail RESULTS.md and README.md:13, superseding the earlier
    "classes STABLE, severity INCONCLUSIVE"). Per-class corpus rates are directional; the
    *ranking* of top classes is the robust part (same discipline as
    HARNESS_INSIGHTS.md §6).
13. **3-in-1 presentation privacy floor.** The combined deck (§11) shows ONLY published
    aggregates derived from the private corpus (counts/shares/ratios of published
    aggregates; no session content, no paths, no hashes, no per-session timestamps; n<5
    suppressed — the HARNESS_INSIGHTS.md §7 model). No MASTscope derived private-trace
    artifact (e.g. `mastscope/fullrun/adamast/judgments.json`, §5.3's false-pass evidence)
    is ever shown or quoted. Graded deliverables stay tau2-anchored, so Conditions 1–10
    remain the binding floor and the supporting lanes never add teammate exposure to
    private content.

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

> **2026-11-01 gate reconciliation (post-council):** the numbers above are the council's
> 2026-10-30 quotes. Since then (INTEGRITY.md §5b): the 2026-10-31 corpus refresh
> orphaned 59 batch-A labels (10 missing + 49 dropped hashes — quarantined intact with
> sidecar), so the regenerated RESULTS.md reads batch A **40,739/40,798 checkpointed,
> 24,777 OK (99.3%)** vs the refreshed 163,681-record manifest; batch B (single-model
> grok-4.7) was **completed 40,798/40,798 (23,332 OK)** and `sensitivity_d.json`
> generated — and the full-N sensitivity verdict is **restated: "STILL UNSTABLE AT FULL
> N"** (5/5 top-5 class shares and 3/3 impact shares at C fall OUTSIDE D's bootstrap 95%
> CI; L1(C,D)=0.4898 vs L1(B,C)=0.0861; quote from `trail/fullrun/sensitivity.md`,
> "VERDICT AT FULL N" section) — superseding the "classes STABLE, severity INCONCLUSIVE"
> wording quoted in §1/README below, which described the pre-full-N A/B/C snapshots.
> Gold-set
> headline metrics (§1 above) are unchanged — gold artifacts were untouched. Lane gate:
> `verify_fullrun.py` **exit 0, ALL 56 CHECKS PASSED** (was 46/54 FAIL on 2026-10-30).

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

## 6. Data provenance (disclosure — Condition 5/7 companion; written 2026-10-31)

The council's provenance critic (§2, row "Is the inherited AI estate the team's work?")
required this section before week 3. Full AI-involvement inventory: `AI_USAGE.md`.

| Asset | Origin | Processing / AI involvement | Team access | Course-use status |
|---|---|---|---|---|
| 124,327-session corpus (final refresh 163,681 records; `corpus/`) | **One member's private agent-session history** (both drives, ~81 runtimes — CORPUS.md §2) | Deterministic read-only builder (no LLM calls); sha256 identity, atomic writes, zero-loss (INTEGRITY.md §1 audit) | Owner-only for raw content; counts/structure published | Private; NOT presented as team deliverable; MASTscope NO-GO partly on this |
| Private-journal API processing (trail corpus half, mastscope corpus) | The same private journals | **Private text was sent to external APIs**: z.ai GLM tiers, grok-4.7 via local bridge, NVIDIA NIM nemotron family, OpenRouter :free (trail RESULTS.md:100-102, 136-153; provider-claims.json). This egress was **unanalyzed** at send time (privacy critic, §2) and is irreversible | None beyond owner | Disclosed as a structural course blocker (§1, §5.2/§5.3); lanes that depend on it are NO-GO / fallback-only |
| Custom e-commerce VAT/coupon rules (`poc/ecommerce*`) | **Derived from the team's own momentstudio codebase** (`tss/lab/pricing.py` overlap — §2 provenance-critic row) | Authored/extended by the AI workflow into 14 hand-written tasks | Full | **Inherited estate, not TEAM-new** — Condition 1 requires the team to BUILD the generator this semester |
| τ²/MAST/TRAIL upstream code + papers | Third-party (Sierra Research; MAST org; Patronus AI) | Pinned clones (commits named in each RESULTS.md); never modified in-tree | Full (MIT/two unlicensed — see §5.3) | Standard citation; errata filed upstream (#635) |
| All results tables, dossiers, this memo | AI workflow (ZCode/GLM-5.3 + grok-4.7 + NVIDIA NIM; AI_USAGE.md) | Generated from gated runs; verified offline per lane | Full | AI-produced; professor-visible scoping in AI_USAGE.md §3 |

- **HUMAN-REQUIRED:** the explicit "not presented in another course" check vs the
  TSS-lab pricing/VAT module, and professor sign-off on the TEAM-new vs inherited
  scoping (Condition 5/7) — an AI cannot make either attestation.
- Privacy-hygiene record (this session, 2026-10-31): all `.md` files scanned for
  username-in-path disclosure; 4 filesystem-path/account occurrences masked to
  `<os-user>` (`tau2-bench/SMOKE.md:77`, `tau2-bench/UPSTREAM_DOCS_ERRATA.md:65`,
  `corpus/CORPUS.md:215`, `INTEGRITY.md:141`). Intentionally NOT masked: GitHub
  owner identifiers (README.md:3 badges; SECURITY.md:10/32; CONTRIBUTING.md:10;
  QZP_FINISH.md:1/30/35/43 — repo title, two functional CI workflow pins that must
  keep the owner name to resolve, and one error-message receipt) and the two
  grep-command receipts (§4.9 and the provenance footer), which quote the literal
  search string that produced the count 35 — masking them would break receipt
  reproducibility. **HUMAN-REQUIRED:** confirm this split before any public release;
  Condition 9's full 35-file scrub (all file types) remains a semester task.

## 7. Person-week decomposition (3–4 students, weeks 1–14)

Planning estimate for the §3 milestone plan, expressed in person-weeks (pw). Roles are
the four workstreams named in §3 weeks 1–2. Assumption: ~1 FTE-equivalent per student
per week net of coursework; totals are plan figures, not measurements.

| Weeks | A — harness/repro + gates (S1) | B — compositional generator (S2) | C — dual-control domain + demo (S3) | D — evaluation/statistics + human audit + budget (S4) |
|---|---|---|---|---|
| **1–2** | Pin v1.0.1/v2.0.0, WSL standardization, every-member 10-task pilot re-run (2.0 pw) | Rule-interaction inventory from momentstudio-derived set; generator spec (2.0 pw) | Domain v0 ownership; disclosure pack support (1.0 pw) | AI_USAGE.md upkeep, USD budget ledger by payer, audit protocol draft (1.5 pw) |
| **3–4** | Same-version cross-model rerun + bootstrap CIs (2.0 pw) | Generator skeleton + solvability checker (2.0 pw) | Airline-autopsy support (1.0 pw) | Autopsy statistics; power analysis v0 from on-disk k=4 data (2.0 pw) |
| **5–6** | Wire generator output into harness full validation (32-check precedent) (1.5 pw) | Generator v1 → ≥100 tasks passing validation (2.5 pw) | Shopper-app tools v0 + user_db mirror (2.0 pw) | Sampled QA of generated tasks (1.0 pw) |
| **7–8** | user_db + dual-control harness wiring (1.5 pw) | Difficulty calibration to a discriminating band (2.0 pw) | User-simulator polish + task authoring freeze (2.0 pw) | Discrimination pilot v1 (2 models × 3 seeds) (2.0 pw) |
| **9–10** | Gate green on team repo; repo hygiene (1.0 pw) | Task-set freeze + docs (1.5 pw) | Demo build (live path) (2.0 pw) | Full pilot + judge A/B + **2-annotator human audit** (all members annotate; D leads) (2.5 pw) |
| **11–12** | Upstream PR finalize (errata/evaluator) (1.5 pw) | Release packaging (1.0 pw) | Demo hardening + fallback recording (§8) (2.0 pw) | Cost accounting; final-report tables (2.0 pw) |
| **13–14** | Verify gate re-run GREEN; scrub the 35 username files (1.5 pw) | Release final (1.0 pw) | Defense demo + rehearsal (1.5 pw) | Report, limitations, defense prep (2.0 pw) |
| **Role total** | **12.0 pw** | **12.0 pw** | **13.5 pw** | **13.0 pw** |

- **4-student plan total ≈ 50.5 pw** over a 56 pw (4 × 14) nominal capacity — ~10%
  slack for exam weeks. The ~110–120 min/trace human-audit hours (Condition 5) are
  scheduled inside weeks 9–10 and divided across ALL members, D leading.
- **3-student fallback — honest arithmetic:** 3 students give 42 nominal pw against the
  same 50.5 pw plan, and merging A into D naively stacks 25 pw on one person. The
  binding Conditions 1–10 set a floor that does **not** fit 3 students at 1 FTE each.
  A 3-student team must redistribute A+D tasks across all three members AND descope
  ~5-8 pw with professor sign-off (candidates: demote the judge A/B from core to
  appendix −2.0, halve the audit sample −1.25, drop the upstream-PR stretch −1.5,
  trim demo layers to L1+L2 −1.0), landing at ≈44-46 pw ≈ 5-10% over-subscribed —
  absorbed only by weeks 9–12 overflow or owner absorption of the D lane. **Recommend
  4 students**; with 3, the descope decision is itself a week-1 agenda item.
- **HUMAN-REQUIRED:** real names→roles assignment (team decision), the named budget
  payer per leg in USD (Condition 6), and the human annotation shifts — an AI cannot
  hold budget ownership or produce the human-validated labels.

## 8. Demo-failure fallback plan (Condition 10, made concrete)

Layered insurance so no graded outcome depends on a live API key or a green laptop:

| Failure at demo time | Detection | Response (fallback layer) |
|---|---|---|
| Live key 429 / auth failure / provider outage mid-demo | Pre-flight `--dry-run` + one live probe ≤10 min before the slot | **L1 — offline gold-replay**: replay the recorded gold interaction, proven 10/10 PASS exit 0 (SMOKE.md:159), zero keys needed |
| Harness or environment crash (Windows/WSL drift, pytest-not-green trap — Condition 8) | Demo rehearsal in the defense room's conditions, week 13 | **L2 — recorded fallback**: full demo video + terminal transcript, inventoried in advance (list in the repo before the defense, not improvised) |
| Room has no compute / projection-only slot | Inventory check at rehearsal | **L3 — static artifacts**: printed RESULTS tables, verify-gate receipts (`VERIFY OK` tails), the pass^k slides |
| Judge/evaluator dispute from the audience | — | Show the substring-vs-semantic A/B data (Condition 3/4 output) rather than re-litigating live |

Rules: the live demo is attempted first only if the pre-flight probe passes; every
fallback layer is rehearsed at least once (weeks 11–12 hardening, week 13–14
rehearsal); the fallback inventory lives in the repo and is linked from the defense
slides. **HUMAN-REQUIRED:** record the video, run the rehearsal, and re-run the verify
gate GREEN at submission (Condition 9) — these are physical acts with deadlines, not
documentation.

## 9. Statistical-rigor note

What the current numbers do and do not support — read before quoting any table:

1. **No confidence intervals yet.** Every pass^k in the headline tables is a point
   estimate from ONE sweep at seed=300, k=4 per task. The cross-model table additionally
   mixes harness versions (v1.0.1 GLM vs v2.0.0 grok — confound admitted at
   RESULTS.md:123-136, banned by Condition 3). No cross-model delta may be quoted as a
   model-ranking claim until the same-version rerun lands with bootstrap CIs (§3 weeks
   3–4) and the ≥2-model × ≥3-seed discrimination pilot with a power analysis sized
   from the on-disk per-task k=4 data (Condition 4).
2. **Small cells (n<5).** A 2026-10-31 scan of every project-authored `.md` found
   **142 table cells and 14 genuine inline mentions reporting counts <5** (scanner:
   bare-integer cell parser + count-noun regex over 46 files; the raw inline regex also
   produced 9 taxonomy-label artifacts such as "2.3 Task Derailment", excluded),
   concentrated in: `corpus/CROSS_TAXONOMY.md`
   per-mode×class cross-tab (lines 101-111), `mastscope/RESULTS.md` month buckets
   (lines 134-138, incl. one n=1 month) and agreement matrix (216-229), and
   `trail/RESULTS.md` per-class gold tables (67-72), annotator table (148), and
   per-runtime coverage (237-253). These are counts of machine sessions in the owner's
   OWN private corpus — not third-party human subjects — so standard human-subject
   small-cell suppression does not strictly apply, and per this repo's rule ("never edit
   measured numbers") none were altered. They remain flagged: (a) statistically, no cell
   with n<5 may anchor a claim (percentages on n=1-4, e.g. "100.0%" on n=1, are noise);
   (b) privacy-wise, fine-grained intersections over a private corpus leak its
   structure. **HUMAN-REQUIRED:** owner decision, before any public release, whether to
   suppress n<5 cells (e.g. "n<5") in public tables — suppression is a publication-time
   editorial act on measured numbers that this pass deliberately did not perform.
3. **Annotator noise floor is measured, not assumed.** Same-task annotation differs by
   2.1× on location accuracy between frontier models (0.4419 vs 0.2064, trail §1); several
   cross-model κ values are negative (trail RESULTS.md:129-131). Single-annotator
   (single-model) labels are evidence, not ground truth; the 2-annotator human audit
   (Condition 5) is the first human-validated label in the project.
4. **Multiplicity.** Any new wave of per-domain/per-class significance tests must state
   a correction (the cross-taxonomy engine already applies Benjamini-Hochberg FDR —
   `corpus/cross_taxonomy_join.py` `bh_fdr`, 29-test suite in CI); per-domain pass^k
   comparisons without correction are descriptive only.
5. **Framing.** All agent/judge results are model-substituted (no paper-protocol
   gpt-4.1/o1 keys — §1 blockers); reproduction claims stay framed model-substituted
   unless a funded key appears (Condition 6). Saturation risk on shipped domains
   (pass^1 0.87-0.89 prior-session) means benchmark claims route through the
   discrimination pilot or fall back to the validity study (Condition 4).
6. **HUMAN-REQUIRED:** choosing the significance conventions (α, CI method, one- vs
   two-sided) for the semester's claims, and signing off that quoted tables respect
   rules 1-2 above.

---

## 10. Extension round (2026-10-30 → 2026-11-01; recorded in final form 2026-11-02)

Work performed after the council memo, recorded here because it changes what the
project can claim (Conditions 11–13) and feeds the 3-in-1 presentation (§11).

### 10.1 Grok sweep complete — 2,852/2,852 (tau2-bench, anchor lane)

The anchor lane's grok-4.7 v2.0.0 batch closed at full coverage and was gated:

- **SWEEP COMPLETE 04:16** (2026-10-30; final domain intake 800/800) —
  `tau2-bench/RESULTS.md:186`.
- Final audit 04:21, `python repair_grok_gaps.py`: **all 8 domains OK — 2,852 sims,
  full k=4 coverage, 0 infrastructure_error, 0 duplicate (task,trial) pairs** —
  RESULTS.md:187.
- Offline gate, 2026-10-30 04:3x: `python verify_fullrun.py` → **exit 0, 176 PASS /
  0 FAIL**, last line `VERIFY OK -- all checks passed`, covering BOTH batches
  (RESULTS.md:189; receipt `results_v2_grok/verify_fullrun_output.txt`).

Gate receipts re-read this session at the cited lines; the exit-0 runs are the
recorded lane verification, not re-run for this memo. The cross-model table built on
this sweep stays version-confounded (v1.0.1 vs v2.0.0) — Condition 3 unchanged.

Same window, TRAIL-side grok sweep also closed (context for §10.3, receipts in
INTEGRITY.md §5b): corpus batch B — single-model grok-4.7 over every canonical
target — finished **40,798/40,798 checkpointed, 23,332 OK** (fresh 23,807 +
reused-wave3 16,991); all derived artifacts regenerated with the lane's own
generators; `verify_fullrun.py` re-run → **exit 0, ALL 56 CHECKS PASSED**
(receipts `/tmp/trail_gate_r2_{before,after2}.log`). Full-overlap cross-model
agreement on same-hash pairs: glm-5.3-flash vs grok-4.7 mean Jaccard 0.4517 /
exact-set 0.2573 (n=206); nvidia-ultra corroboration n=8,500 and n=1,770.

### 10.2 Judge result — hierarchical chunked judge vs same-model flat control (148-trace gold set)

Controlled experiment on the **public** 148-trace TRAIL gold set (117 GAIA + 31 SWE,
`repo/benchmarking/data/{GAIA,SWE Bench}`), judge model grok-4.7 `xhigh` via the
local bridge. Read in full this session: `trail/fullrun_hierarchical_judge.md`
(design, ledgers, operational record); scored artifact
`trail/work/fullrun/hier_agreement.json` verified this session by loading it
(GAIA location 0.6376 / joint 0.2689 / weighted-F1 0.4667 — matches the table).

| judge | model | calls/trace | tokens/trace | weighted F1 | location acc | joint acc |
|---|---|---|---|---|---|---|
| Flat (paper artifact) | glm-5.3 / nemotron-ultra mix | 1 | — | 0.3683 | 0.2472 | **0.0905** |
| Flat control (paper prompt + flat capping ladder) | grok-4.7 xhigh | 1 | 42.5K | **0.4920** | 0.3858 | 0.2065 |
| **Hierarchical (windows → votes → reconcile)** | grok-4.7 xhigh | 2.93 | 68.7K | 0.4489 | **0.5406** | **0.2190** |

The finding, as the ask's material and the artifact state it:

1. **~93% of the joint-accuracy gain is the model, not the chunking.** The 0.0905 →
   0.2190 lift is headline-real, but the same-model flat control already scores
   0.2065 of the 0.2190 endpoint; the architecture's residual is +0.0125 joint,
   **not significant** (Wilcoxon p=0.80, n=148; better on 40 / worse on 25 files).
2. **Chunking's real, significant effect is location accuracy**: +0.155
   (0.3858 → 0.5406, +40% relative), **Wilcoxon p=1.1e-08**, better on 65 / worse
   on 9 files. Mechanism is visible in the design: window payloads carry near-full
   unit text (12K/unit cap vs the flat ladder's 160K total budget), and every
   window error is mechanically constrained to a span id actually shown in that
   window.
3. **The cost is over-prediction**: weighted F1 0.4920 → 0.4489 (predicted 7.08
   errors/trace vs 5.68 gold; the reconciliation pass drops only 13% of
   candidates; FP-heavy in Tool Output Misinterpretation 73 / Language-only 68 /
   Instruction Non-compliance 55) and **1.62× tokens per trace** (68.7K vs 42.5K).
   Macro-F1 rises 0.297 → 0.391.
4. **SWE split**: the only configuration of the three with non-zero SWE joint
   accuracy (0.0308 vs 0.0000 for both flat runs; location 0.1743 vs
   0.0086/0.0998) — SWE traces are the largest (median 1.58 MB) and are destroyed
   worst by flat capping.
5. Paper context (confound stated, not claimed as like-for-like): the paper's best
   reported GAIA judge (Gemini-2.5-Pro) reached Cat-F1 0.389 / LocAcc 0.546; this
   judge's GAIA location 0.6376 and weighted-F1 0.4667 exceed both — different
   models and capping, so it is a model+architecture confound against the paper.

Run record: 433 calls (285 windows + 148 reconciliation) + 148 control calls;
single-model invariant (model id per record in the meta ledger); checkpointed and
resumable (one 12 h interruption resumed at 147/285 windows with zero re-annotation);
bridge ledger flaps documented and mitigated (`hier_sweep1..6.log`,
fullrun_hierarchical_judge.md §4). Not re-run for this memo; quoting is governed by
Condition 11.

### 10.3 Findings status (what is quotable, and under what gate)

| # | Finding | Evidence (receipt) | Status after the extension round |
|---|---|---|---|
| F1 | τ² COMMUNICATE-substring evaluator artifact: on the custom e-commerce domain ALL failures of BOTH models are substring misses with DB correct and zero wrong writes | GLM 13/14 failing units (tau2 RESULTS.md:51-64); grok 12/12 (RESULTS.md:140-148, identical taxonomy, deterministic per task) | Evidenced on two models — still n=1 self-authored domain; NOT quotable as benchmark-validity until the shipped-airline autopsy lands (Condition 2) |
| F2 | Dual-control signature failure (agent never steers user to the user-side write) | tau2 RESULTS.md:66 (ecommerce_poc) | Measured; feeds Contribution II (§3 weeks 7–8) |
| F3 | Cross-model τ² table is version-confounded | tau2 RESULTS.md:123-136 (confound admitted in-file) | Banned by Condition 3; same-version rerun still owed (weeks 3–4) |
| F4 | TRAIL gold agreement is low and annotator-model-dependent (noise floor: single-model location acc 0.4419 vs 0.2064) | trail RESULTS.md §1; several cross-model κ negative | STRENGTHENED: flat control 0.3858 (grok) sits between; full-overlap batch-B agreement mean Jaccard 0.4517 / exact 0.2573 (n=206, §10.1) |
| F5 | Chunked judging fixes LOCATION, not category agreement; ~93% of the joint gain is the model | §10.2 (p=1.1e-08 location; p=0.80 joint residual) | NEW this round; quotable only with the control attached (Condition 11) |
| F6 | Corpus-wide TRAIL class shares STILL UNSTABLE AT FULL N | `trail/fullrun/sensitivity.md:161-163`; regenerated trail RESULTS.md; README.md:13 | RESTATED — supersedes the pre-full-N "classes STABLE, severity INCONCLUSIVE" (Condition 12) |
| F7 | MAST×TRAIL join: same failing sessions, private catchments (both-flagged 60.3%, κ=0.333; TRAIL monopolizes infra classes, MAST monopolizes process pathology) | `corpus/CROSS_TAXONOMY.md` (via HARNESS_INSIGHTS.md §4) | Quotable as within-join statements (N=861, enriched sample), aggregate-only |
| F8 | Harness-level failure profile + 5 ranked recommendations (R1 repetition circuit breaker … R5 clarify-first) | HARNESS_INSIGHTS.md (§10.4) | Quotable as aggregates with instrument-reliability caveats attached (its §6) |

### 10.4 Insights pointer

**`HARNESS_INSIGHTS.md`** (repo root; generated 2026-11-01, read in full this
session) is the cross-lane synthesis the 3-in-1 deck draws its taxonomy slides from:
65.2% of MAST-ok sessions carry ≥1 of the 14 failure modes (mean 2.45); 79.5% of
TRAIL-ok sessions carry ≥1 error class (mean 2.22); task_completed=yes only 34.5%;
Reasoning-root 58.5% of labels vs System Execution 23.0%; HIGH impact 38.9%. Two
failure regimes: the interactive Claude lane completes 71% at the fleet's lowest
error density (1.91 labels/session) while vault/rollout/automation lanes complete
0–42% with Step Repetition at 72.6–91.7%. Five ranked, numbers-attached
recommendations (R1–R5). Privacy model: **aggregates only, n<5 suppressed** (its
§7) — the template Condition 13 imposes on the combined deck.

---

## 11. 3-in-1 combined presentation — integrated blueprint (owner decision)

**Decision (owner, recorded 2026-11-02, given with this ask): the semester
presentation is 3-IN-1 COMBINED, anchored on tau2-bench.** One deck intermingles the
findings of all three lanes; the graded deliverables and the binding floor remain
tau2's (Conditions 1–10), with the TRAIL/MASTscope material entering as
already-gated supporting evidence under Conditions 11–13. This §11 is the blueprint;
§§1–9 (plan, conditions, person-weeks, fallback, rigor) carry over unchanged except
as noted.

### 11.1 Title

**Recommended:** *"Evaluating Agent Evaluation: Reproducing and Extending τ²-bench,
Auditing Its Judge, and Cross-Examining Two Failure Taxonomies."*
Alternate (shorter): *"One Benchmark, Three Instruments: a τ²-bench-Centered Study
of Agent Evaluation and Its Failure Taxonomies."*

### 11.2 Work packages

WP1–WP4 are §7's workstreams A–D unchanged (12.0 + 12.0 + 13.5 + 13.0 = 50.5 pw).
WP5–WP6 are the 3-in-1 integration packages — they ride on ALREADY-GATED evidence,
so no new private-corpus work and no new teammate exposure:

| WP | Content | Owner (§7 role) | Estimate |
|---|---|---|---|
| WP1 | Harness pin + same-version cross-model rerun + gates (Conditions 3, 8) | A (S1) | 12.0 pw (§7) |
| WP2 | Compositional {f_init, f_sol, f_assert} generator, ≥100 validated tasks (Condition 1) | B (S2) | 12.0 pw (§7) |
| WP3 | Dual-control shopper-app domain + live demo + fallbacks (Conditions 2, 10; §8) | C (S3) | 13.5 pw (§7) |
| WP4 | Discrimination pilot + CIs + power analysis + substring-vs-semantic A/B + 2-annotator audit + budget (Conditions 4–6) | D (S4) | 13.0 pw (§7) |
| **WP5 (new)** | Judge-validity leg: reproduce the flat control on the public 148-trace gold set over a $0 model-substituted path; package §10.2 figures with the control adjacent (Condition 11); the A/B on the τ² v2.0.0 flag stays in WP4 | D leads, any member can run the public-gold reproduction | ≈2.0 pw |
| **WP6 (new)** | Taxonomy-aggregates packaging: slides from HARNESS_INSIGHTS.md + CROSS_TAXONOMY.md aggregates only (Condition 13); joint two-part rehearsal | C leads | ≈2.5 pw |

**Total ≈ 55.0 pw** vs 56 nominal (4 students) — the 3-in-1 consumes §7's ~10%
slack. If time squeezes, WP5/WP6 are demoted to appendix material FIRST (−4.5 pw)
without touching Conditions 1–10; the §7 descope candidates remain the next tier.

### 11.3 Slide outline — 18 slides, two presenter parts, findings intermingled

P1 = workstreams A+B (harness, generator), P2 = C+D (domain, evaluation). Part
assignment to real people is HUMAN-REQUIRED (§7). Every non-τ² slide carries its
receipt and maps back to a τ² decision.

| # | Part | Slide | Content (receipt anchors) |
|---|---|---|---|
| 1 | P1 | Title + verdict map | Three lanes, one decision; anchor τ² GO; F1–F8 in one figure (§1, §10.3) |
| 2 | P1 | The dual-control problem | τ²'s agent-user split; why user-side writes matter; MAST/TRAIL as the instrument landscape (research-sota dossiers) |
| 3 | P1 | τ² reproduced, gated | 2,344 GLM + 2,852 grok sims; 93 + 176 PASS / 0 FAIL gates; headline pass^k table (§5.1) |
| 4 | P2 | Judge validity #1: the substring artifact | Both models: 13/14 and 12/12 failures are substring misses, DB correct, zero wrong writes (F1; Condition 2 autopsy owed) |
| 5 | P2 | TRAIL as an instrument | 148-trace public gold; agreement 0.0905 joint; annotator noise floor 0.4419 vs 0.2064; cross-model Jaccard 0.4517 (F4) |
| 6 | P1 | Judge validity #2: chunked judging, controlled | The §10.2 three-row table, control adjacent — "~93% is the model; location is the architecture" (F5; Condition 11) |
| 7 | P1 | Why location improves | Windows→votes→reconcile diagram; near-full unit text; span-id-constrained errors; SWE split 0.0308 vs 0.0000 |
| 8 | P2 | The price | wF1 0.492→0.449 (over-prediction 7.08 vs 5.68); 1.62× tokens; macro-F1 0.297→0.391; when chunking is worth it |
| 9 | P2 | Contributions preview | Generator (Condition 1) + shopper-app dual-control tools (Contribution II) close the two measured gaps (F2) |
| 10 | P1 | Generator design | {f_init, f_sol, f_assert} + automatic solvability verification; ≥100 tasks past the 32-check validation (§3 weeks 5–6) |
| 11 | P1 | Cross-examination I: the join | MAST×TRAIL κ=0.333; both-flag 60.3%; infra is TRAIL's monopoly, process pathology MAST's (F7; aggregates only) |
| 12 | P2 | Cross-examination II: the fleet's profile | 65.2% / 79.5% / 34.5% completion; two failure regimes; R1–R5 (F8; HARNESS_INSIGHTS.md) |
| 13 | P2 | Instrument honesty | STILL UNSTABLE AT FULL N (F6); rankings not rates; κ noise floor; why we report CIs (Condition 12, §9) |
| 14 | P1 | Discrimination pilot design | ≥2 frontier models × 3 seeds × pass^1/pass^4 + power analysis sized from on-disk k=4 data (Condition 4) |
| 15 | P1 | Demo | Live τ² play on ecommerce3; L1 gold-replay / L2 recorded / L3 static fallbacks (§8) |
| 16 | P2 | Budget & provenance | $0 proven path vs ~$300–400 paper-protocol pilot; model-substituted framing; AI_USAGE + team-new vs inherited (Conditions 6–7) |
| 17 | P2 | Limitations & risks | Saturation (CRAB-Bench), judge dependence, version confound owed, aggregate-only floor (§5.1 threats; §11.5) |
| 18 | P1+P2 | Close | What we build vs what we already know; upstream errata #635; the evaluation-of-evaluation arc |

### 11.4 Demo plan

Primary: live τ² play demo on the custom ecommerce3 domain (owner machine or the
team's $0 free-tier path), pre-flighted with `--dry-run` + one live probe ≤10 min
before the slot (§8). Fallbacks in order: **L1** offline gold-replay (10/10 PASS,
exit 0, SMOKE.md:159 — zero keys), **L2** recorded video + terminal transcript
(inventoried in the repo before the defense), **L3** static artifacts (RESULTS
tables, `VERIFY OK` gate receipts, pass^k slides). 3-in-1 addition: a second,
always-offline beat — the judge-anatomy walk (slide 4→7): one ecommerce3 trace
where the DB is right and the substring misses (RESULTS.md:142-148 table) plus the
§10.2 control table; it needs no key and survives any outage. Every fallback layer
rehearsed once in weeks 11–13 (§8 rules).

### 11.5 Feasibility and risks

**Feasibility.** The supporting legs ride on evidence already gated on disk: the
judge experiment (§10.2), the taxonomy aggregates (HARNESS_INSIGHTS.md,
CROSS_TAXONOMY.md), the sweeps (§10.1). Marginal 3-in-1 cost over §7 is ≈4.5 pw of
packaging + a cheap public-gold reproduction (148 traces × 1 flat call — the flat
control measured 42.5K tokens/trace; the nemotron gold pass ran 148 calls / 4.4M
tokens / 1645s, §1) — affordable on the $0 path, model-substituted (Condition 6).
Team access is clean: τ² repo (MIT), TRAIL public gold set (MIT repo), published
aggregates only — zero private content (Condition 13). Headcount arithmetic: 4
students → ≈55.0 pw of 56 nominal (slack consumed; WP5/WP6 demotable first); 3
students → the §7 descope decision applies unchanged.

| Risk | Exposure | Mitigation |
|---|---|---|
| Narrative overload — 3 lanes in 18 slides | high | Anchor discipline: τ² is the graded core; every supporting slide carries a receipt and maps to a τ² condition; slides 5–8 and 11–13 are the only non-τ² core |
| Misquoting the judge result ("chunking fixes TRAIL") | high | Condition 11 — control adjacent on the slide itself (slide 6 shows all three rows) |
| Private-content spill via taxonomy slides | high | Condition 13 — aggregates only, n<5 suppressed, no MASTscope derived artifacts; deck reviewed against HARNESS_INSIGHTS.md §7 before release |
| Unstable class rates challenged at defense | medium | Condition 12 — show rankings + the instability receipt on slide 13, not bare rates |
| Version confound re-entering a cross-model table | medium | Condition 3 — one harness version per comparison; confound slide explicit (slide 17) |
| Schedule: ≈55 pw vs 56 capacity | medium | Demote WP5/WP6 to appendix first; then §7 descope candidates with professor sign-off |
| Demo key/provider failure | low | §8 L1–L3 layers + the offline judge-anatomy beat (§11.4) |

### 11.6 Recommendation

Proceed with the 3-in-1 as the owner decided: it converts three lanes into one
coherent *evaluating-agent-evaluation* arc — reproduce the benchmark, audit its
judge two ways (substring artifact F1 + controlled chunked judge F5), and
cross-examine with two failure taxonomies (F7/F8) — while the graded deliverables
stay tau2-anchored so nothing in Conditions 1–10 loosens. Register with the 3-in-1
xlsx line below; keep the single-topic line ready as the fallback registration if
the professor rejects the combined scope. WP5/WP6 are the first demotion
candidates under time pressure. **HUMAN-REQUIRED:** professor sign-off on the
combined scope, presenter-part assignment (P1/P2) to real team members, and the
§11.2/§7 budget-owner confirmations.

### 11.7 xlsx-ready lines (both options)

3-in-1 (recommended registration):

```
Paper link     | Anchor: https://arxiv.org/abs/2506.07982 (τ²-bench, Sierra Research — MIT, github.com/sierra-research/tau2-bench); supporting: https://arxiv.org/abs/2505.08638 (TRAIL, Patronus AI — MIT) and https://arxiv.org/abs/2503.13657 (MAST)
Idea (1 line)  | "Evaluating agent evaluation": reproduce the dual-control τ²-bench on one pinned harness version (2,344 GLM + 2,852 grok sims, both gated) and extend it with a compositional auto-verified coupon/VAT/returns task generator (>=100 tasks), user-side shopper-app dual-control tools, and a >=2-frontier-model x 3-seed discrimination pilot with CIs — cross-examined by a controlled chunked-judge experiment on TRAIL's public 148-trace gold set (location +0.155, Wilcoxon p=1.1e-08; ~93% of the joint-accuracy gain is the model, not chunking) and aggregate-only MAST×TRAIL failure-taxonomy findings from a 124k-session corpus.
```

Single-topic (fallback registration; identical to §5.4):

```
Paper link     | https://arxiv.org/abs/2506.07982 (τ²-bench, Sierra Research — MIT, github.com/sierra-research/tau2-bench)
Idea (1 line)  | Reproduce the dual-control τ²-bench agent-user evaluation on one pinned harness version and extend it with a compositional auto-verified coupon/VAT/returns task generator (>=100 tasks), user-side shopper-app tools for true dual-control e-commerce, a >=2-frontier-model x 3-seed discrimination pilot with CIs and a power analysis, and a benchmark-validity study (COMMUNICATE substring-vs-semantic judge A/B + shipped-airline autopsy).
```

---

*Provenance: verdicts, one-line reasons, conditions, plan and lane statuses from the council
decision + lane records supplied with the ask (council-memo session, 2026-10-30). Read that
session: all three lane RESULTS.md files in full (cited by line); tau2-bench SMOKE.md §2.2
(430 pytest failures, line 67) and gold-replay 10/10 (line 159) via grep; tau2-bench
research-sota.md §1.4 airline correction (line 62) and coupon/VAT grep-verification
(line 172) via grep. Run that session: `grep` confirming verbatim private-trace content
`20 findings A-01..A-20` in `mastscope/fullrun/adamast/judgments.json`;
`grep -rlI "Prekzursil" . | wc -l` → 35 files in the tau2-bench lane.*

*Final-form session (2026-11-02). Read in full this session: `trail/
fullrun_hierarchical_judge.md` (all §10.2 numbers); `HARNESS_INSIGHTS.md` (§10.4);
`README.md`; `QZP_FINISH.md` §1; `tau2-bench/RESULTS.md` §7–8 (lines 95–189 — sweep
completion, final audit, gate receipts for §10.1); `trail/RESULTS.md` working copy
(regenerated 2026-11-01 headline + batch-B sections, via `git diff`); `INTEGRITY.md`
§5b gate-fix round (via `git diff`); `trail/fullrun/sensitivity.md` §"VERDICT AT FULL N"
(lines 161–163, via grep). Run this session: `python -c` loading
`trail/work/fullrun/hier_agreement.json` → GAIA location 0.6376 / joint 0.2689 /
weighted-F1 0.4667, matching §10.2. Owner decision on 3-in-1 combined (anchor =
tau2-bench) given with the ask. Not re-run for this memo (reported as recorded, with
receipts): the judge experiment and its Wilcoxon tests, all lane verify-gate exit-0
runs (tau2 176/176, trail 56/56, mastscope 43 checks — INTEGRITY.md §5b), the batch-B
sweep, API-key 401 probes, and council first-hand re-verifications cited above.
This file supersedes the 2026-10-19 DECISION.md and is the final form of the
2026-10-30 council memo.*
