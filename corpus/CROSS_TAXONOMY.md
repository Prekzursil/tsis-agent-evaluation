# Cross-taxonomy join: MAST-14 modes × TRAIL classes over the shared session corpus

Generated 2026-10-21 by `corpus/cross_taxonomy_join.py` (run from `tss/tsis-deepdive/`; all
tables below come from `corpus/cross_taxonomy_join.json`, aggregates only — no session
content, no hashes). Headline numbers were independently re-derived with a second,
minimal-dependency script before publication (both agree bit-for-bit on N, the 2×2
agreement table, the 1.5×Resource-Abuse cell, and the marginals checked).

## 1. Join definition, provenance, and coverage — read this first

Two published taxonomies were run over the same physical corpus (124,327 manifest
records, 41,877 unique content hashes; `corpus/manifest.jsonl`, `corpus/canonical_set.json`):

- **MAST-14** (`mastscope/RESULTS.md`): 14 binary failure modes in 3 categories
  (FC1 System Design/Specification 1.1–1.5, FC2 Inter-Agent Misalignment 2.1–2.6,
  FC3 Task Verification 3.1–3.3), judged session-level. Labels:
  `mastscope/fullrun/labels_full.jsonl` — 33,889 label rows, 32,540 `ok` rows,
  **30,924 unique `ok` hashes** (1,654 of the 33,889 targets are sessions exploded from
  multi-conversation containers; 18 hashes carry more than one `ok` part label, 8 of
  them inside the join).
- **TRAIL** (`trail/RESULTS.md`): the benchmark's error classes (21 canonical leaves
  in `repo/benchmarking/calculate_scores.py:113-118`, rooted in 3 roots per the paper's
  taxonomy tree, `trail/paper_text.txt:1755-1810`). Labels:
  `trail/work/fullrun/corpus2_labels/<sha16>.json` — 7,011 checkpointed files,
  **1,162 unique `ok` hashes**. **TRAIL coverage was capped by owner order
  (2026-10-20): 1,162 of 24,949 census-eligible sessions = 4.7%** (`trail/RESULTS.md:98-105`).
  That cap is the binding constraint on this join; no additional labels exist or were waited for.

**Joinable-N = 861** — every hash labeled `ok` by BOTH lanes (74.0% of TRAIL-ok,
2.8% of MAST-ok). All 861 hashes verified present in both `corpus/manifest.jsonl`
and `corpus/canonical_set.json` (join key = full sha256; 861/861 in each).

TRAIL taxonomy scope note: 20 of the 21 canonical classes occur in the corpus labels
(`Incorrect Memory Usage` has zero corpus support, as in the lane's own gold run —
`trail/RESULTS.md:49`). Throughout, "TRAIL-20" = those 20 observed canonical classes.
Raw annotator categories were normalized to the canonical list; variants seen (all
disclosed in `cross_taxonomy_join.json` → `diagnostics.category_normalizations`):
`Tool-related (fabricating…)` → `Tool-related` (39 labels corpus-wide), one truncated
`Poor Information Retrieval (…)` and one `Formatting Errors (…)` parenthesized variant,
and one `Hallucinations > Language-only` parent-path variant (the only odd label
inside the join; mapped to `Language-only`).

Why 301 TRAIL-ok hashes are NOT in the join (disclosure, not loss):
- 253 were never MAST annotation targets — the lanes' eligibility rules differ
  (MAST requires ≥1 user AND ≥1 assistant message; the TRAIL census requires ≥2
  message events OR ≥1 tool event — `mastscope/RESULTS.md:18-26`, `trail/RESULTS.md:92-93`).
- 48 were MAST targets but produced `ok=false` parse-fail responses.

Unit of analysis = the file-level session (one sha256). For the 8 multi-part hashes,
MAST part labels are OR-aggregated to hash level and `task_completed` is taken from
part 0. Both taxonomies are multi-label; every rate below is a share of N=861 sessions
unless stated otherwise.

**Selection skew of the join (must-read for interpretation).** The join is not a random
sample of either corpus. Its runtime mix is codex 27.4%, vm-backup 26.6%, grok 16.7%,
zcode-rollout 11.8%, claude-code-free 11.5% (vs the MAST corpus at ~80% claude_journal),
and it is enriched in failing sessions: MAST mode prevalences run far above their
full-corpus rates (1.3 Step Repetition 67.5% in-join vs 41.4% corpus-wide; 2.1
Conversation Reset 39.6% vs 13.0%). 83 of the 861 TRAIL labels come from the bounded
sensitivity extension (single-model `glm-5.3-flash`, queue deliberately restricted to
MAST-labeled hashes; `trail/RESULTS.md:107-110`), the remaining 778 from the
multi-model interleaved main sweep. All associations below are **within-join**
statements; none are projected onto the corpus at large.

## 2. Session-level detection agreement

"Flagged" = ≥1 of the 14 MAST modes yes (MAST) / ≥1 TRAIL error class present (TRAIL).

| | TRAIL flagged | TRAIL clean | total |
|---|---:|---:|---:|
| **MAST flagged** | 519 (60.3%) | 157 (18.2%) | 676 (78.5%) |
| **MAST clean** | 70 (8.1%) | 115 (13.4%) | 185 (21.5%) |
| **total** | 589 (68.4%) | 272 (31.6%) | 861 |

- Cohen's κ = **0.333**; φ = 0.341; χ² p = 1.5e-23; Jaccard of the flagged sets = 0.696.
- Rank correlation between #MAST modes and #TRAIL classes per session: Spearman
  **ρ = 0.376** (p = 2.2e-30). Mean 2.44 MAST modes and 1.89 TRAIL classes per session.
- Convergent validity across instruments (secondary cross-checks):
  - MAST `task_completed` → mean TRAIL `overall` score: **yes 4.26** (n=265) /
    no 3.42 (n=262) / no-verdict 3.62 (n=334).
  - TRAIL impact mix by MAST flag: MAST-flagged sessions' 1,603 error labels are
    HIGH 50.8% / LOW 10.8%; MAST-clean sessions' 136 labels are HIGH 33.8% / LOW 40.4%.

Reading: moderate, highly significant agreement — the two instruments detect largely
the same failing sessions (60% both-flagged) but each has a substantial private catchment
(18% MAST-only, 8% TRAIL-only), quantified in §7.

## 3. Co-occurrence matrix — MAST mode × TRAIL class (session counts, N=861)

Cell = #sessions where the mode is `yes` AND the class is present. Column order =
descending class marginal. Class key: IN=Instruction Non-compliance, GD=Goal Deviation,
RA=Resource Abuse, CHF=Context Handling Failures, FE=Formatting Errors,
TSE=Tool Selection Errors, RL=Rate Limiting, ESE=Environment Setup Errors,
TOM=Tool Output Misinterpretation, LO=Language-only, PIR=Poor Information Retrieval,
IPI=Incorrect Problem Identification, TI=Timeout Issues, TDI=Tool Definition Issues,
AE=Authentication Errors, RNF=Resource Not Found, TR=Tool-related, TO=Task Orchestration,
SE=Service Errors, RE=Resource Exhaustion.

| MAST mode (n) | IN | GD | RA | CHF | FE | TSE | RL | ESE | TOM | LO | PIR | IPI | TI | TDI | AE | RNF | TR | TO | SE | RE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1.1 Disobey Task Spec (78) | 38 | 28 | 14 | 20 | 11 | 7 | **0** | 7 | 8 | 14 | 7 | 15 | 7 | 3 | 2 | 1 | 8 | 2 | 1 | 0 |
| 1.2 Disobey Role Spec (8) | 5 | 4 | 0 | 2 | 0 | 1 | 0 | 2 | 1 | 1 | 0 | 3 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | 0 |
| 1.3 Step Repetition (581) | 167 | 142 | 133 | 117 | 86 | 72 | 56 | 64 | 57 | 50 | 58 | 55 | 42 | 36 | 33 | 32 | 26 | 30 | 24 | 20 |
| 1.4 Loss of Conv History (67) | 20 | 15 | 20 | 20 | 12 | 6 | 7 | 4 | 4 | 10 | 4 | 5 | 2 | 1 | 3 | 1 | 6 | 3 | 0 | 3 |
| 1.5 Unaware of Termination (108) | 53 | 51 | 56 | 50 | 14 | 14 | 9 | 6 | 10 | 8 | 5 | 8 | 4 | 1 | 2 | 2 | 8 | 19 | 0 | 1 |
| 2.1 Conversation Reset (341) | 92 | 80 | 72 | 68 | 65 | 43 | 31 | 33 | 34 | 30 | 43 | 40 | 33 | 20 | 21 | 21 | 12 | 12 | 17 | 14 |
| 2.2 Fail to Ask Clarif. (74) | 42 | 39 | 34 | 36 | 7 | 11 | 2 | 8 | 6 | 10 | 4 | 6 | 3 | 0 | 2 | 0 | 7 | 12 | 0 | 0 |
| 2.3 Task Derailment (37) | 19 | 16 | 8 | 13 | 7 | 3 | 0 | 5 | 2 | 6 | 6 | 7 | 2 | 0 | 1 | 0 | 3 | 2 | 0 | 0 |
| 2.4 Information Withholding (7) | 4 | 2 | 4 | 2 | 1 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 0 | 1 | 0 | 0 |
| 2.5 Ignored Other's Input (28) | 11 | 13 | 7 | 12 | 4 | 2 | 1 | 2 | 4 | 4 | 1 | 4 | 2 | 0 | 1 | 0 | 3 | 4 | 0 | 0 |
| 2.6 Action-Reason Mismatch (69) | 23 | 18 | 13 | 14 | 13 | 11 | 3 | 10 | 7 | 11 | 6 | 7 | 7 | 2 | 4 | 1 | 6 | 3 | 3 | 3 |
| 3.1 Premature Termination (290) | 88 | 71 | 66 | 65 | 46 | 32 | 54 | 25 | 43 | 22 | 33 | 27 | 36 | 13 | 14 | 24 | 16 | 8 | 15 | 9 |
| 3.2 Weak Verification (193) | 63 | 57 | 40 | 43 | 34 | 21 | 10 | 18 | 25 | 35 | 19 | 19 | 20 | 13 | 11 | 8 | 17 | 14 | 6 | 10 |
| 3.3 No/Incorrect Verif. (217) | 82 | 65 | 32 | 40 | 30 | 27 | 24 | 25 | 19 | 29 | 20 | 25 | 29 | 8 | 10 | 13 | 10 | 10 | 8 | 5 |
| **class marginal** | **221** | **162** | **139** | **134** | **120** | **96** | **85** | **84** | **82** | **72** | **67** | **65** | **56** | **44** | **39** | **38** | **34** | **34** | **28** | **23** |

(Mode marginals are the row headers; both taxologies are multi-label so rows/columns
do not sum to N. Bolded 0 = a significant *repulsion*, see §6.)

## 4. Per-MAST-mode top TRAIL classes

Top-3 by co-occurrence count; lift = P(class|mode) / P(class) overall; q = Benjamini-Hochberg
FDR over all 280 mode×class Fisher exact tests (52 of 53 significant pairs are positive
associations; the single significant negative one is 1.1×RL).

| MAST mode | n | top TRAIL classes (count, lift, q) |
|---|---:|---|
| 1.1 Disobey Task Spec | 78 | IN 38 (1.90, 6.8e-05) · GD 28 (1.91, 2.2e-03) · CHF 20 (1.65, 6.9e-02) |
| 1.2 Disobey Role Spec | 8 | IN 5 (2.43, ns) · GD 4 (2.66, ns) · IPI 3 (4.97, ns) — n too small |
| 1.3 Step Repetition | 581 | IN 167 (1.12, 1.8e-02) · GD 142 (1.30, 5.1e-09) · RA 133 (1.42, 5.9e-16) |
| 1.4 Loss of Conv History | 67 | CHF 20 (1.92, 1.6e-02) · RA 20 (1.85, 1.9e-02) · IN 20 (1.16, ns) |
| 1.5 Unaware of Termination | 108 | RA 56 (3.21, 1.4e-18) · IN 53 (1.91, 5.5e-07) · GD 51 (2.51, 1.9e-11) |
| 2.1 Conversation Reset | 341 | IN 92 (1.05, ns) · GD 80 (1.25, 3.2e-02) · RA 72 (1.31, 1.3e-02) |
| 2.2 Fail to Ask Clarification | 74 | IN 42 (2.21, 7.0e-08) · GD 39 (2.80, 2.2e-10) · CHF 36 (3.13, 7.9e-11) |
| 2.3 Task Derailment | 37 | IN 19 (2.00, 5.6e-03) · GD 16 (2.30, 3.6e-03) · CHF 13 (2.26, 1.5e-02) |
| 2.4 Information Withholding | 7 | IN 4 (2.23, ns) · RA 4 (3.54, ns) — n too small |
| 2.5 Ignored Other's Input | 28 | GD 13 (2.47, 5.0e-03) · CHF 12 (2.75, 3.6e-03) · IN 11 (1.53, ns) |
| 2.6 Action-Reason Mismatch | 69 | IN 23 (1.30, ns) · GD 18 (1.39, ns) · CHF 14 (1.30, ns) — diffuse |
| 3.1 Premature Termination | 290 | IN 88 (1.18, ns) · GD 71 (1.30, 1.9e-02) · RA 66 (1.41, 2.9e-03) |
| 3.2 Weak Verification | 193 | IN 63 (1.27, 7.3e-02) · GD 57 (1.57, 4.9e-04) · CHF 43 (1.43, 2.8e-02) |
| 3.3 No/Incorrect Verification | 217 | IN 82 (1.47, 6.8e-05) · GD 65 (1.59, 5.4e-05) · CHF 40 (1.18, ns) |

## 5. Per-TRAIL-class top MAST modes

Same convention, reverse direction.

| TRAIL class | n | top MAST modes (count, lift, q) |
|---|---:|---|
| Instruction Non-compliance | 221 | 1.3 167 (1.12, 1.8e-02) · 2.1 92 (1.05, ns) · 3.1 88 (1.18, ns) |
| Goal Deviation | 162 | 1.3 142 (1.30, 5.1e-09) · 2.1 80 (1.25, 3.2e-02) · 3.1 71 (1.30, 1.9e-02) |
| Resource Abuse | 139 | 1.3 133 (1.42, 5.9e-16) · 2.1 72 (1.31, 1.3e-02) · 3.1 66 (1.41, 2.9e-03) |
| Context Handling Failures | 134 | 1.3 117 (1.29, 4.7e-07) · 2.1 68 (1.28, 3.0e-02) · 3.1 65 (1.44, 1.7e-03) |
| Formatting Errors | 120 | 1.3 86 (1.06, ns) · 2.1 65 (1.37, 4.7e-03) · 3.1 46 (1.14, ns) |
| Tool Selection Errors | 96 | 1.3 72 (1.11, ns) · 2.1 43 (1.13, ns) · 3.1 32 (0.99, ns) — diffuse |
| Rate Limiting | 85 | 3.1 54 (**1.89**, 1.1e-07) · 1.3 56 (0.98, ns) · 2.1 31 (0.92, ns) |
| Environment Setup Errors | 84 | 1.3 64 (1.13, ns) · 2.1 33 (0.99, ns) · 3.1 25 (0.88, ns) — diffuse |
| Tool Output Misinterpretation | 82 | 1.3 57 (1.03, ns) · 3.1 43 (1.56, 3.0e-03) · 2.1 34 (1.05, ns) |
| Language-only | 72 | 1.3 50 (1.03, ns) · **3.2 35 (2.17, 7.4e-06)** · 2.1 30 (1.05, ns) |
| Poor Information Retrieval | 67 | 1.3 58 (1.28, 3.2e-03) · 2.1 43 (1.62, 3.4e-04) · 3.1 33 (1.46, 3.7e-02) |
| Incorrect Problem Identification | 65 | 1.3 55 (1.25, 1.5e-02) · 2.1 40 (1.55, 3.0e-03) · 3.1 27 (1.23, ns) |
| Timeout Issues | 56 | 1.3 42 (1.11, ns) · **3.1 36 (1.91, 2.7e-05)** · 2.1 33 (1.49, 1.8e-02) |
| Tool Definition Issues | 44 | 1.3 36 (1.21, ns) · 2.1 20 (1.15, ns) · 3.1 13 (0.88, ns) — diffuse |
| Authentication Errors | 39 | 1.3 33 (1.25, ns) · 2.1 21 (1.36, ns) · 3.1 14 (1.07, ns) — diffuse |
| Resource Not Found | 38 | 1.3 32 (1.25, ns) · **3.1 24 (1.88, 1.9e-03)** · 2.1 21 (1.40, ns) |
| Tool-related | 34 | 1.3 26 (1.13, ns) · **3.2 17 (2.23, 3.6e-03)** · 3.1 16 (1.40, ns) |
| Task Orchestration | 34 | 1.3 30 (1.31, 4.3e-02) · **1.5 19 (4.46, 2.0e-08)** · 3.2 14 (1.84, 5.9e-02) |
| Service Errors | 28 | 1.3 24 (1.27, ns) · 2.1 17 (1.53, ns) · 3.1 15 (1.59, ns) — diffuse |
| Resource Exhaustion | 23 | 1.3 20 (1.29, ns) · 2.1 14 (1.54, ns) · 3.2 10 (1.94, 9.1e-02) — diffuse |

## 6. Agreement / association statistics

**Pair-level tests.** 280 mode×class 2×2 Fisher exact tests (session presence/absence),
BH-FDR corrected: **53 pairs significant at q<0.05 (52 positive, 1 negative)**. Strongest
associations (by q): 1.5×Resource Abuse (OR 8.69, lift 3.21) · 1.3×Resource Abuse
(OR 13.56) · 1.5×Context Handling Failures (OR 6.87, lift 2.97) · 1.5×Goal Deviation
(OR 5.17) · 2.2×CHF (OR 6.66, lift 3.13) · 2.2×Goal Deviation (OR 6.02) ·
1.5×Task Orchestration (OR 10.50, lift 4.46) · 2.2×Instruction Non-compliance (OR 4.46) ·
3.1×Rate Limiting (OR 3.99) · 3.2×Language-only (OR 3.78). The one significant
**negative** association: 1.1 Disobey Task Specification × Rate Limiting — 0 of 78
1.1-sessions carry Rate Limiting (q=3.6e-03): spec-disobedience is a "clean-room"
cognitive failure, not something the platform provokes. Full pair table:
`cross_taxonomy_join.json → pair_stats`.

**Conditional-entropy structure.** Knowing a MAST mode barely narrows the TRAIL class
mix — the two taxonomies are near-orthogonal partitions, not re-labelings:

- H(TRAIL class | mode=yes) runs 0.70–0.94 of the max log₂20=4.32 bits, vs 0.91–0.95
  for mode=no. The strongest concentrators (with n≥28): 2.2 Fail to Ask Clarification
  (JS divergence yes-vs-no 0.134 bits), 1.5 Unaware of Termination (0.128), 2.3 Task
  Derailment (0.106); the weakest: 2.6 Action-Reason Mismatch (0.021), 3.3 (0.020),
  2.1 (0.018). Every mode raises the mean TRAIL error count per session (mode=yes
  2.18–3.09 classes vs mode=no 1.15–1.88, per-mode range) — MAST flags are severity
  markers even where the class mix stays broad.
- Reverse direction: the **System-Execution classes are the most mode-selective** —
  H(MAST modes | class=yes) is 2.39–2.61 bits for Service Errors, Resource Exhaustion,
  Resource Not Found, Rate Limiting and Tool Definition Issues vs ~3.14 for their
  complements (JS 0.067–0.097): infra errors concentrate on few modes, above all
  3.1 Premature Termination. The behavioral classes are nearly flat (JS 0.006–0.037):
  knowing the TRAIL behavioral class barely constrains the MAST mode mix.

**Category × root co-occurrence** (label-level; FC category of the mode × TRAIL root of
the class; n=5,050 co-occurring label pairs):

| | Reasoning | System Execution | Planning & Coord. | row total |
|---|---:|---:|---:|---:|
| FC1 System Design / Specification | 878 (44.3%) | 377 (19.0%) | 726 (36.6%) | 1,981 |
| FC2 Inter-Agent Misalignment | 628 (45.9%) | 255 (18.6%) | 485 (35.5%) | 1,368 |
| FC3 Task Verification | 782 (46.0%) | **408 (24.0%)** | 511 (30.0%) | 1,701 |

χ²=27.8, dof=4, p=1.4e-05, but Cramér's V=0.052 — statistically real, substantively
thin. The one visible structure: FC3 (verification) over-co-occurs with System-Execution
errors (24.0% of its pairs vs ~19% for FC1/FC2) — verification failures are
disproportionately entangled with infra errors, consistent with §5's 3.1×{RL,TI,RNF} links.

## 7. What each taxonomy catches that the other misses

**TRAIL-only catchment (MAST-clean, TRAIL-flagged): 70 sessions carrying 127 class
labels.** Drivers: Instruction Non-compliance 20, Formatting Errors 18, Tool Selection
Errors 12, Rate Limiting 10, Environment Setup 9, Tool Output Misinterpretation 9,
Goal Deviation 7, Timeout 6, Tool-related 6, Language-only 6 (rest ≤5). Two constructs
live here: (a) *quiet rule/format violations* — breaches that never disturb the
process-level behaviors MAST judges; (b) *low-grade infrastructure noise* — see next.

**MAST-only catchment (TRAIL-clean, MAST-flagged): 157 sessions carrying 419 mode
labels.** Drivers: 1.3 Step Repetition 141, 2.1 Conversation Reset 78, 3.1 Premature
Termination 44, 3.2 Weak Verification 43, 3.3 No/Incorrect Verification 36 (rest ≤16).
This is MAST's private core: *process pathologies that are not discrete error events*
— loops, resets, stopping early, and above all **verification weakness, for which TRAIL
has no class at all**. 56 join sessions are flagged exclusively by FC3 modes; 12 of them
are otherwise TRAIL-clean, i.e. pure verification failures only one instrument can see.

**Infrastructure is TRAIL's structural monopoly.** Eight TRAIL classes (Rate Limiting,
Authentication, Service Errors, Resource Not Found, Resource Exhaustion, Timeout, Tool
Definition, Environment Setup — the whole System-Execution root minus nothing) have no
MAST counterpart: MAST judges the agent, never the platform. In the join these classes
total 397 class-presences; 123 sessions (14.3%) carry *only* System-Execution errors,
and 21 of those are fully MAST-invisible. But 102 of the 123 still carry MAST behavioral
flags — infra noise usually rides along behavioral failure rather than replacing it.
Where infra stress does surface in MAST, its signature is **3.1 Premature Termination**
(lift 1.89–1.91, OR ≈ 3.6–4.0 with Rate Limiting, Timeout, Resource Not Found): when
the platform chokes, the agent stops early.

**Behavioral drift is the shared core, seen from two angles.** The densest, most
significant region of the matrix is MAST {1.1, 1.3, 1.5, 2.2, 2.3} × TRAIL
{Instruction Non-compliance, Goal Deviation, Context Handling Failures, Resource Abuse}:
both taxonomies triangulate the same underlying construct — the agent drifting off its
instructions — with MAST describing the *process shape* (didn't ask, didn't know when
to stop, derailed) and TRAIL naming the *symptom class* (non-compliance, goal deviation,
context loss, tool spam). The single best translator is **1.5 Unaware of Termination
Conditions**: it predicts the whole Planning-root error family (Resource Abuse lift 3.21,
CHF 2.97, Task Orchestration 4.46 — the largest lifts in the join). Loops that don't
know when to stop are exactly what overflows context windows and hammers tools.

**Hallucination pairs with weak verification.** TRAIL's two hallucination classes
(Language-only, Tool-related) select 3.2 Weak Verification as their top mode (lifts
2.17 and 2.23) far above chance: fabricated content survives precisely where the agent
fails to check it.

**Severity exists only on the TRAIL side; completion verdicts only on MAST.** TRAIL
attaches HIGH/MEDIUM/LOW impact and error locations; MAST attaches a task-completed
verdict. They cross-validate (§2): MAST-flagged sessions' errors are 50.8% HIGH vs
33.8% for MAST-clean ones, and MAST `task_completed=yes` sessions score 4.26 vs 3.42
on TRAIL's 0–5 overall rubric.

## 8. Limitations

1. **Joinable-N is small and selected** (861; 2.8% of the MAST corpus, 74.0% of the
   owner-capped TRAIL corpus). The runtime mix and failure enrichment of §1 mean these
   are within-join associations, not corpus-wide rates; the lane's own sensitivity
   analysis already showed corpus-wide TRAIL shares are selection-sensitive
   (`trail/fullrun/sensitivity.md`).
2. **Multi-label data, marginal tests.** Sessions carry 0–14 modes and 0–10 classes;
   the 280 Fisher tests reuse sessions and are not a joint model. BH-FDR controls the
   false-discovery rate over the pair family, not dependence between pairs.
3. **Annotator provenance differs by lane.** MAST: glm-5.3-flash volume tier + migrated
   v1 labels (flash-vs-full tier agreement 86.9% on the 50-trace cross-check,
   `mastscope/RESULTS.md:210-231`). TRAIL: multi-model volume batches (gold-agreement
   weighted F1 0.37 in the lane's own gold run, `trail/RESULTS.md:27-37`). Cross-lane
   disagreement therefore mixes taxonomy disagreement with instrument noise.
4. **Eligibility asymmetry** (§1): 253 TRAIL-ok sessions could never have joined
   because MAST's extractor requires a user+assistant pair.
5. Entropies for modes 1.2 (n=8) and 2.4 (n=7) are unstable; marked "n too small"
   in §4 and excluded from interpretation.

## 9. Reproduce

```
cd tss/tsis-deepdive
python corpus/cross_taxonomy_join.py     # reads both label stores + manifest; writes
                                         # corpus/cross_taxonomy_join.json (aggregates only)
```

Artifacts: `corpus/cross_taxonomy_join.py` (this analysis, exact script that produced
every number above), `corpus/cross_taxonomy_join.json` (all tables incl. the full
280-pair statistics, entropy blocks, misses counters, selection checks).
