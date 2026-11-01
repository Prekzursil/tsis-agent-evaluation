# HARNESS INSIGHTS — what the annotations say about the owner's harness

Generated 2026-11-01. Sources, all read in full this session:

- `tsis/agent-evaluation/mastscope/RESULTS.md` — MAST-14 annotation, 32,540 ok-labeled sessions
- `tsis/agent-evaluation/trail/RESULTS.md` — TRAIL annotation, 24,777 ok-labeled sessions
- `tsis/agent-evaluation/corpus/CROSS_TAXONOMY.md` — MAST×TRAIL join over the shared corpus, N=861

Both lanes annotated the same physical corpus (124,327 manifest records, 41,877 unique
content hashes, drives C:+D:, live + backup + orphan-backup;
`corpus/CROSS_TAXONOMY.md:11-12`) under different eligibility rules, so their Ns overlap
but do not match. **Privacy: aggregates only — counts, shares, and ratios derived from
published aggregates. No session content, no paths, no hashes, no per-session timestamps.
Runtimes/cells with n<5 are suppressed** (§7 lists every suppression).

---

## 1. The harness in one profile

Single expert operator, long-horizon, tool-saturated, subagent-delegated fleet; ~96% of
annotated volume from 2026; six harness families with Claude Code journals dominant
(mastscope/RESULTS.md:255-261). 33,889 sessions were parseable across 7 session formats
(mastscope/RESULTS.md:18-23). This is a production single-user harness, not a benchmark
crew — and the failure distribution is a property of that harness, not of agents in
general (mastscope/RESULTS.md:274-281).

## 2. Headline numbers

- **65.2% of MAST-ok sessions carry ≥1 of the 14 failure modes** (21,205 of 32,540);
  mean 2.45 modes per flagged session (mastscope/RESULTS.md:102).
- **79.5% of TRAIL-ok sessions carry ≥1 error class** (19,698 of 24,777); mean 2.22
  error labels/session (trail/RESULTS.md:211-213).
- **Task completed = yes on only 34.5%** of MAST-ok sessions (11,209 yes / 9,830 no /
  11,501 null) (mastscope/RESULTS.md:102).
- **Reasoning failures, not infrastructure, dominate**: Reasoning-root errors are 58.5%
  of TRAIL labels vs System Execution 23.0% / Planning & Coordination 18.5%
  (trail/RESULTS.md:189-191). A harness that survives rarely dies of the platform — it
  bleeds through model behavior.
- **When it breaks, the break matters**: HIGH impact = 38.9% of TRAIL labels (21,371 of
  54,977), MEDIUM 43.8%, LOW 17.3%, CRITICAL n=5 (0.01%, minimum reportable)
  (trail/RESULTS.md:193-196).
- Top MAST modes: 1.3 Step Repetition 43.1%, 3.1 Premature Termination 29.2%, 3.2 Weak
  Verification 19.2%, 3.3 No/Incorrect Verification 19.0%, 2.1 Conversation Reset 14.9%
  (mastscope/RESULTS.md:106-119). Top TRAIL classes: Tool Output Misinterpretation 24.9%
  of traces, Instruction Non-compliance 23.4%, Formatting Errors 20.6%, Language-only
  16.7%, Goal Deviation 14.2% (trail/RESULTS.md:160-171).

## 3. Per-runtime failure-mode distribution

### 3.1 MAST-14 per runtime (n≥5; all source rows already ≥5)

Source: mastscope/RESULTS.md:184-194.

| runtime | n sessions | task done | top mode (share of runtime's sessions) |
|---|---:|---:|---|
| claude-code-free | 16,725 | 71% | **3.1 Premature Termination (21.4%)** |
| agent-sessions-vault | 9,550 | 24% | 1.3 Step Repetition (72.6%) |
| codex | 2,208 | 39% | 1.3 (74.2%) |
| ai-exports | 1,634 | 35% | 1.3 (76.3%) |
| vm-backup | 1,489 | 66% | 1.3 (73.1%) |
| zcode-rollout | 494 | 14% | 1.3 (85.8%) |
| grok | 392 | 42% | 1.3 (82.9%) |
| zcode-workspace | 24 | 0% | 1.3 (91.7%) |
| codex-archived | 11 | 71% | 1.3 (90.9%) |
| gemini-cli | 8 | 60% | 1.3 (75.0%) |
| cline | 5 (min. reportable) | 67% | 1.3 (80.0%) |

The one structural split: **claude-code-free is the only runtime whose top mode is not
Step Repetition** — it tops out at Premature Termination 21.4% (so its 1.3 share is
≤21.4%), while every other runtime tops at 1.3 between 72.6% and 91.7%. Loop collapse is
a non-Claude-runtimes disease in this fleet; Claude's failure surface is stopping early.

### 3.2 TRAIL per runtime (annotated-ok n≥5; derived density = error labels ÷ annotated)

Source counts: trail/RESULTS.md:216-252. Labels/session is derived here as the ratio of
the two published aggregates. Unit caveat: MAST counts sessions, TRAIL counts unique
files/hashes — same corpus, different eligibility; treat cross-lane per-runtime numbers
as directional.

| runtime | annotated ok | error labels | labels/session (derived) |
|---|---:|---:|---:|
| claude-code-free | 16,209 | 30,980 | 1.91 |
| agent-sessions-vault | 3,587 | 9,212 | 2.57 |
| codex | 2,582 | 6,883 | 2.67 |
| vm-backup | 1,385 | 4,476 | 3.23 |
| zcode-rollout | 484 | 1,922 | 3.97 |
| grok | 463 | 1,297 | 2.80 |
| zcode-workspace | 24 | 71 | 2.96 |
| codex-archived | 19 | 40 | 2.11 |
| ai-exports | 18 | 67 | 3.72 |
| cline | 5 (min. reportable) | 29 | 5.80 |

Suppressed: gemini-cli (annotated ok n=1, below threshold). 24 further runtimes in the
TRAIL table (cursor-chats, other:vscode, other:pplx, …) yielded 0 census-eligible
sessions — no failure distribution exists to report (trail/RESULTS.md:222-252).

### 3.3 What the per-runtime split says

1. **Two failure regimes.** The interactive Claude lane completes 71% of tasks with the
   fleet's lowest error density (1.91 labels/session); the vault/rollout/automation
   lanes complete 0–42% (except vm-backup at 66%) with Step Repetition at 72.6–91.7%.
2. **Worst offenders to audit first: zcode-rollout** (14% completion, 85.8% step
   repetition, 3.97 labels/session — worst on all three axes), **agent-sessions-vault**
   (24% completion, 9,550 sessions of volume), and **zcode-workspace** (0/24 completed,
   91.7% step repetition; small n, at threshold).
3. **vm-backup is the "completes anyway" outlier**: 66% completion despite 73.1% step
   repetition and 3.23 labels/session — a retry-heavy pattern that eventually lands the
   task while burning tool calls (consistent with 1.3×Resource Abuse, §5 R1).
4. Completion and loop-share move inversely across runtimes: the lane with ≤21.4%
   possible 1.3 (claude-code-free) completes 71%; lanes with ≥82% 1.3 (zcode-rollout,
   zcode-workspace, codex-archived, grok) complete 0–71% — codex-archived (n=11) being a
   small-n exception.

## 4. One failure surface, two instruments (join, N=861)

The two taxonomies detect largely the same failing sessions but keep private catchments
(`corpus/CROSS_TAXONOMY.md:69-86`): both-flagged 519 (60.3%), MAST-only 157 (18.2%),
TRAIL-only 70 (8.1%), both-clean 115 (13.4%); Cohen's κ = 0.333; per-session severity
correlates (Spearman ρ = 0.376).

- **MAST's private core is process pathology TRAIL cannot name**: of the 157 MAST-only
  sessions, drivers are 1.3 (141), 2.1 Conversation Reset (78), 3.1 (44), 3.2 (43),
  3.3 (36) — loops, resets, early stops, and verification weakness, **for which TRAIL
  has no class at all**; 56 join sessions are FC3-only and 12 of them are otherwise
  fully clean (`corpus/CROSS_TAXONOMY.md:224-230`).
- **TRAIL's structural monopoly is infrastructure**: 8 System-Execution classes (Rate
  Limiting, Authentication, Service, Resource Not Found, Resource Exhaustion, Timeout,
  Tool Definition, Environment Setup) have no MAST counterpart; 123 join sessions
  (14.3%) carry only infra errors and 21 of those are fully MAST-invisible — but 102 of
  the 123 still carry MAST behavioral flags: infra noise rides along behavioral failure
  (`corpus/CROSS_TAXONOMY.md:233-239`). Where infra stress surfaces in MAST, its
  signature is 3.1 Premature Termination (lifts 1.89–1.91, OR ≈ 3.6–4.0 with Rate
  Limiting / Timeout / Resource Not Found; `corpus/CROSS_TAXONOMY.md:239-241`).
- **Hallucination survives weak verification**: TRAIL's Language-only and Tool-related
  hallucination classes select MAST 3.2 Weak Verification as top mode (lifts 2.17 /
  2.23; `corpus/CROSS_TAXONOMY.md:254-257`).
- **Every MAST mode is a severity marker**: mode=yes sessions carry 2.18–3.09 TRAIL
  classes on average vs 1.15–1.88 for mode=no (`corpus/CROSS_TAXONOMY.md:190-193`); and
  MAST-flagged sessions' errors are 50.8% HIGH impact vs 33.8% for MAST-clean ones
  (`corpus/CROSS_TAXONOMY.md:81-83`). MAST task_completed=yes ↔ mean TRAIL overall 4.26
  vs 3.42 for no (`corpus/CROSS_TAXONOMY.md:79-80`).

## 5. Top 5 actionable recommendations (numbers attached)

**R1 — Install a repetition/loop circuit breaker. (highest volume, every runtime)**
Step Repetition is the #1 mode fleet-wide at 43.1% (14,038 of 32,540;
mastscope/RESULTS.md:108) and the top mode in 10 of 11 reportable runtimes at 72.6–91.7%
(§3.1) — 27.4 pts above the MAST paper's 15.7% multi-user benchmark rate, i.e. a harness
property, not a model property (mastscope/RESULTS.md:249). Loops also burn the platform:
1.3×Resource Abuse is the strongest positive pair in the join (OR 13.56;
`corpus/CROSS_TAXONOMY.md:175-176`). *Action:* harness-level detector on near-identical
consecutive tool calls that interrupts and forces a plan restatement; roll out first on
zcode-rollout and agent-sessions-vault (85.8% / 72.6% incidence, combined 10,044
sessions).

**R2 — Make termination conditions explicit and infra failures non-fatal.**
3.1 Premature Termination is 29.2% (9,486) and the top mode of the dominant runtime
(claude-code-free, 21.4%) (mastscope/RESULTS.md:117, :184). 1.5 Unaware of Termination
is only 5.2% (1,695) but is the join's best predictor of the Planning-root error family:
Resource Abuse lift 3.21 (OR 8.69), Task Orchestration lift 4.46 (OR 10.50), Context
Handling Failures lift 2.97 (OR 6.87) (`corpus/CROSS_TAXONOMY.md:132, :174-178`). Infra
errors convert into early stops: 3.1 pairs with Rate Limiting OR 3.99, Timeout lift 1.91,
Resource Not Found lift 1.88 (`corpus/CROSS_TAXONOMY.md:155, :161, :164, :239-241`), and
TRAIL infra classes are visible on real traffic (Rate Limiting 5.5% of traces, Timeout
8.3%, Resource Not Found 5.6%; trail/RESULTS.md:172-175). *Action:* write explicit stop
conditions into task prompts; add retry-with-backoff plus session-resume on 429/timeout
so platform hiccups stop ending tasks prematurely.

**R3 — Gate "done" behind an executed verification step.**
3.2 Weak Verification 19.2% (6,256) + 3.3 No/Incorrect Verification 19.0% (6,184); FC3
Task Verification is the largest category at 42.1% of all flagged occurrences
(mastscope/RESULTS.md:117-125). Verification weakness is invisible to the TRAIL side of
the fleet's tooling (no class; 56 join sessions FC3-only, 12 otherwise clean —
`corpus/CROSS_TAXONOMY.md:228-230`), and it is exactly where hallucinations survive
(lifts 2.17/2.23 onto 3.2; §4). Meanwhile only 34.5% of sessions end task_completed=yes
and a substantial fraction of "yes" sessions still carry flagged modes
(mastscope/RESULTS.md:102, :269-272). *Action:* refuse completion claims without a
tool-executed check (tests / lint / diff read-back); one question — "what did you
verify, and by which tool?" — attacks both FC3 and hallucination survival.

**R4 — Fix tool-result consumption. (TRAIL's #1 real-traffic class)**
Tool Output Misinterpretation leads the corpus at 6,713 labels / 6,160 traces = 24.9% of
24,777 annotated sessions, with Tool Selection Errors at 10.0% and Tool-related 4.6%
(trail/RESULTS.md:160-176). The curated GAIA gold skews Formatting + Instruction
Non-compliance instead — day-to-day single-user sessions break first on the model
misreading what its tools returned (trail/RESULTS.md:265-275). Gold-run recall on this
family was low (TOM F1 0.231, Tool-related 0.098; trail/RESULTS.md:59, :63), so 24.9% is
if anything conservative. *Action:* structured/JSON tool outputs where possible, a
mandatory "restate the tool result before acting" step, and explicit truncation markers
so the model knows when it saw a partial result.

**R5 — Enforce clarify-first on under-specified tasks. (smallest surface, biggest attached family)**
Fail to Ask for Clarification is only 7.9% (2,576; mastscope/RESULTS.md:112) but is the
join's strongest behavioral predictor: Instruction Non-compliance OR 4.46 (lift 2.21,
q=7.0e-08), Goal Deviation OR 6.02 (lift 2.80), Context Handling Failures OR 6.66 (lift
3.13) (`corpus/CROSS_TAXONOMY.md:134, :174-178`), and the strongest entropy concentrator
of any mode (JS 0.134 bits; `corpus/CROSS_TAXONOMY.md:190-192`). The downstream classes
it feeds are the fleet's biggest behavioral ones — IN 23.4% of traces (5,807), GD 14.2%
(3,513) (trail/RESULTS.md:164-167). *Action:* harness rule blocking the first tool call
until the agent restates the spec and lists ambiguities (or explicitly asserts none);
7.9% of sessions touched, largest error family gated.

## 6. Instrument reliability — how hard to lean on these numbers

- **MAST**: flash-tier labels agree with full-tier at 86.9% mean mode agreement on the
  50-trace cross-check (task_completed agreement 95.5%); per-mode incidences below ~10%
  sit near the agreement noise floor — the headline modes used here (1.3 43.1%, 3.1
  29.2%, 3.2 19.2%, 3.3 19.0%, 2.1 14.9%) are far above it; rare modes (1.2, 2.4, 2.5)
  were not used for recommendations (mastscope/RESULTS.md:212-231, :283-286).
- **TRAIL**: the instrument itself is weak — gold agreement weighted F1 0.3683 /
  location acc 0.2472 (union batch; glm-5.3-only 0.3953/0.4419) (trail/RESULTS.md:31-37);
  cross-model same-hash agreement mean Jaccard 0.32–0.45 and exact set match 0.14–0.26
  (trail/RESULTS.md:127-131); and corpus-wide class shares were formally UNSTABLE at
  full N (5/5 top-5 class shares outside bootstrap CI; L1(C,D)=0.4898; top-10 Jaccard
  0.818) (trail/RESULTS.md:113, :135). Per-class TRAIL rates in §2/§4 are therefore
  directional; the *ranking* of top classes is the robust part.
- **Join**: N=861 is small and selected — runtime mix codex 27.4%, vm-backup 26.6%,
  grok 16.7%, zcode-rollout 11.8%, claude-code-free 11.5% (vs ~80% claude_journal in the
  full MAST corpus), enriched in failing sessions; all §4/§5 associations are
  within-join statements, not corpus-wide rates (`corpus/CROSS_TAXONOMY.md:54-63,
  :267-272`). Annotator provenance differs by lane, so cross-lane disagreement mixes
  taxonomy disagreement with instrument noise (`corpus/CROSS_TAXONOMY.md:275-279`).
- One temporal note used nowhere above: flagged share collapsed 2026-06→08 (74.3% →
  43.0% → 33.3%) then returned to 81.1% in 2026-09 on large n (mastscope/RESULTS.md:171-175)
  — a real shift in the traffic (model/harness change), not a steady improvement.

## 7. Privacy & suppression statement

- Aggregates only: every number is a count/share published in the three source files, or
  a ratio of two published aggregates (§3.2 labels/session; derived ratios marked).
  No session content, prompts, paths, usernames, hashes, or per-session timestamps.
- Suppression rule n<5 applied: TRAIL per-runtime gemini-cli (n=1) suppressed; TRAIL
  class-table variants with <5 traces (four hallucination sub-variants, n=1 each, and
  `configuration` n=2) not carried into this document; MAST rare modes (1.2 n=72, 2.4
  n=172, 2.5 n=455) are above threshold but excluded from recommendations on
  instrument-noise grounds (§6), not privacy grounds. Cells at exactly n=5 (cline
  runtime; CRITICAL impact) are the minimum reportable and are flagged inline.
- Runtime names and taxonomy labels are fleet metadata, not session content; they appear
  in the source aggregates (mastscope/RESULTS.md:184-194; trail/RESULTS.md:216-252).
