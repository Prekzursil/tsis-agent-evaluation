# τ²-bench — SOTA Deep-Dive Dossier

**Topic:** tau2-bench (Sierra Research) — "τ²-Bench: Evaluating Conversational Agents in a Dual-Control Environment" (2025)
**Generated:** 2026-10-18 · **Updated:** 2026-10-19 (session 2: independent re-verification of repo/paper claims; competitor sweep extended with CRAB-Bench, MM-tau-p2, Toloka τ-bench extension; prior-session measured runs summarized in §4.1) · **Updated:** 2026-10-24 (session 3: repo cloned at `cc1df47` — **main is now v2.0.0 "τ-bench 2.0 / τ-i18n"**, superseding the v1.0.1 state described below; version caveat, §2.2, §4 and receipts updated; retail no-coupon/no-VAT claim independently re-verified) · **Analyst:** tau2-bench researcher (workflow subagent)
**Paper:** arXiv:2506.07982 (v1, 2025-06-09) — also published as ICML 2026, PMLR v306 pp. 6736–6782. Authors: Victor Barres*, Honghua Dong* (Sierra / UToronto / Vector), Soham Ray, Xujie Si, Karthik Narasimhan.
**Repo:** https://github.com/sierra-research/tau2-bench (verified live via `gh api` this session)
**Team angle:** author ~10 e-commerce support tasks (returns / coupons / VAT) modeled on a real store's rules; assess whether the harness supports custom domains cleanly.

> **Version caveat (load-bearing, updated 2026-10-24):** the repo has moved on twice since the paper. Releases: v0.1.0–v0.1.3 (2025, paper era) → v0.2.0 (2025-10-06) → v1.0.0 "τ³-bench" (2026-03-18: voice, `banking_knowledge`, 75+ SABER task fixes) → v1.0.1 (2026-07-15 per `CHANGELOG.md:301`) → **v2.0.0 "τ-bench 2.0 / τ-i18n" (2026-10-19)**, which is current `main` (commit `cc1df47`, pushed 2026-10-22, session-3 clone). 2.0 adds: six languages (en/es/pt/hi/zh/ko) for airline+retail+telecom in text **and** full-duplex voice; a new `intake` domain (τ-Entity, 200 tasks, entity elicitation); post-hoc **judges** (naturalness/speech fidelity/tool use) that don't change reward; semantic LLM communication checks replacing 1.x substring matching; frozen released benchmarks (`text-v1` = 900 calls at 1 trial, `voice-v2` = 900, `voice-v1` = 278) [repo: `README.md` §"τ-bench 2.0" + benchmark table; `docs/running-the-benchmark.md`]. README states 2.0 English runs are **not input-identical to v1.0.1** (50 reviewed task replacements in retail/telecom, prompt language clause, persona block in text user sim, judge swaps) and directs 1.x-comparable numbers to the **`v1.0.1` release tag**. Reproducing the *paper's* numbers still requires a 2025 tag (v0.1.x era).

---

## 1. The paper (read from the actual PDF, 47 pp.)

Downloaded `arxiv.org/pdf/2506.07982` → `tau2bench_paper.pdf`; extracted with pypdf to `paper_text.txt` (2,783 lines). All citations below are `paper_text.txt:<line>` into that extraction.

### 1.1 Dual-control formalism (Dec-POMDP)

§3.1 (`paper_text.txt:211-256`). Dual-control interaction is formalized as a **Decentralitized POMDP** with tuple `(S, {Aᵢ}, {Oᵢ}, T, R, U, M)`, players `i ∈ {agent, user}`:

- **M** message space — NL messages between agent and user (`:222-224`).
- **S** = `S_world ⊗ S_history`, where `S_world = S_db,agent ⊗ S_db,user` — **two separate databases** (agent CRM vs. mocked user device) plus an interaction-history log (`:225-228`).
- **Aᵢ** — each player's action is either a **tool call** (into its own DB) or a message; only one player acts per turn (`:229-232`).
- **Oᵢ** — observations are tool returns or the other player's message (`:233-237`).
- **T** — tool calls mutate `S_world`; messages route to the other player (`:238-244`).
- **R: S → [0,1]** — global reward over final DB + history state; in telecom, reward = "user's issue fixed, as verified by the **user's** database state" (`:245-247`).
- **U** — instruction space: user scenario instructions + agent domain policy (`:248-249`).

Key design principle — **"complexity asymmetry"**: user tools must yield only human-readable outputs, user planning stays reactive (only call tools the agent requests), and the environment constrains behavior, so the user simulator stays *less capable* than the agent (intro, `:7` region of PDF p.2 and Figure 1 discussion; user-sim guidelines at `:1285-1334` enforce "Only call a tool if the agent has requested it", `:1312-1313`).

### 1.2 Domains shipped

Table 1 (`paper_text.txt:296-298`):

| | retail | airline | telecom (new) |
|---|---|---|---|
| Agent DB | 500 users, 50 products, 1,000 orders | 500 users, 300 flights, 2,000 reservations | 5 plans, 9 lines, 4 customers |
| Agent tools | 7 write / 6 read | 6 write / 6 read | 6 write / 7 read |
| User tools | **—** | **—** | **15 write / 15 read** |
| Tasks | 115 | 50 | 114 (full generated set: 2,285) |

Retail + airline are the **verified, migrated τ-bench domains** (single-control: user has no tools); **telecom is the new dual-control domain**. Current repo counts (this session): airline 50, retail 114, telecom `base` split 114 / `full` 2,285 (`telecom/split_tasks.json` → `{small:20, train:74, test:40, full:2285, base:114}`); retail's paper-count 115 vs repo 114 reflects later task edits.

### 1.3 Task format & compositional generator

§3.2 five-stage domain creation (`paper_text.txt:300-359`):
1. LLM-drafted PRD → agent DB schema + tools + unit tests, manually refined.
2. Same for the **user** DB/tools (e.g., mocked phone).
3. **Programmatic task creation**: each *atomic subtask* `t = ({f_init}, {f_sol}, {f_assert})` — initialization functions (any DB function, e.g. `set_airplane_mode(True)`), solution functions (must be agent/user **tools**), assertion functions (final-state checks). Mutually-exclusive subtasks are grouped; a composite task picks ≤1 per group and concatenates. **Correctness is verified automatically**: apply init → solution → assert; also verify the task is *not* solved before all solution steps are applied (`:338-342`). Telecom: 15 atomic-subtask groups × 3 intents (`service_issue`, `mobile_data_issue`, `mms_issue`) → 2,285 tasks, subsampled to 114 balanced over intents × #subtasks (Table 3, `:934-945`); #subtasks is the difficulty dial.
4. Policy authored (LLM-assisted) from tasks/solutions.
5. Manual joint refinement.

**Personas** (`:354-359`, `:954-976`): each task optionally carries a persona — `None` / `Easy` (41-y-o office admin, average skills) / `Hard` (64-y-o retired librarian, tech-anxious, volunteers nothing).

**Task JSON schema** (verified from `data/tau2/domains/airline/tasks.json[0]` and paper Appendix A.2 `:977-1038`): `id`, `description{purpose, relevant_policies, notes}`, `user_scenario{persona, instructions{task_instructions, domain, reason_for_call, known_info, unknown_info}}`, `initial_state` (initialization data + initialization actions w/ `env_type: assistant|user`), `evaluation_criteria{actions[], communicate_info[], env_assertions[], nl_assertions[], reward_basis[]}`, `annotations`.

### 1.4 Evaluation & pass^k

§3.3 (`paper_text.txt:360-370`): five criteria families — DB check, status (environment) assertions, NL assertions (LLM-judged), communication-info check, action matching; each task opts into a subset via `reward_basis`. Repo doc `docs/evaluation.md` (fetched this session) makes the semantics precise: **final reward = product of components listed in `reward_basis`**; `evaluation_criteria.actions` is **one reference trajectory replayed on a fresh "gold" env to derive the target DB end-state, compared by DB hash** — the agent is *not* required to follow it (path-independence is deliberate; see repo issues #224 / #129 referenced in that doc); the agent must match `actions` **only** when `RewardType.ACTION` is in `reward_basis`.

> **Correction (2026-10-18, after data-level audit):** this section previously contained two claims propagated from the repo's own stale docs, now fixed against the shipped v1.0.1 data (re-parsed this session from `repo/data/tau2/domains/*/tasks.json`):
> 1. ~~"default for airline/retail/telecom is `["DB","COMMUNICATE"]`"~~ — true only as the **schema default**, not the data. `src/tau2/data_model/tasks.py:435` sets `default_factory=lambda: [RewardType.DB, RewardType.COMMUNICATE]` (applied only when `reward_basis` is omitted), and the `docs/evaluation.md` TL;DR repeats it — but that TL;DR is stale vs the shipped data: **airline 50/50 `[DB, COMMUNICATE]`; retail 0/114 use COMMUNICATE (112 `[DB, NL_ASSERTION]`, 2 `[DB]`); telecom 0/2285 use COMMUNICATE (2253 `[ENV_ASSERTION]`, 32 `[ENV_ASSERTION, ACTION]`)**. Telecom's 114-task `base` split = 94 `[ENV_ASSERTION]` + 20 `[ENV_ASSERTION, ACTION]`, so the paper-era "telecom uses only env assertions" holds for 94/114 base tasks, not all.
> 2. ~~"`RewardType.ACTION` exists but is unused in the three core domains"~~ — **false in v1.0.1 data**: 32 telecom tasks include ACTION in `reward_basis` (first ids: `[service_issue]lock_sim_card_pin[PERSONA:Hard]`, `[service_issue]contract_end_suspension[PERSONA:Hard]`, `[service_issue]airplane_mode_on|lock_sim_card_pin[PERSONA:Easy]`). The repo's own `tasks.py:257-258` docstring ("Used in a few `banking_knowledge` tasks; not used in airline/retail/telecom") and `docs/evaluation.md` TL;DR carry the same stale statements; the dossier originally repeated them without checking the data.

**pass^k** (inherited from τ-bench, `:456-464`): fraction of tasks that succeed in *all k* independent runs (each task run 4×, temperature 0). Reliability metric — scores decay with k.

### 1.5 User simulator design

- LLM function-calling agent given: global **User Simulation Guidelines** prompt (Appendix C.2, `paper_text.txt:1285-1334`) + task-specific scenario (`reason_for_call` / `known_info` / `unknown_info` / `task_instructions`) + (telecom) user tools. Guardrails: one action per turn, never invent unknown info, ground replies in tool returns, disclose progressively, only call tools when the agent asks, end tokens `###STOP###` / `###TRANSFER###` / `###OUT-OF-SCOPE###`.
- **Reliability results** (Table 2, `:791-797`): human-annotated error rates — airline 47% total (13% critical), retail 40% (12% critical), **telecom 16% (6% critical)** — attributed to tool-constrained design.
- In code (v1.0.1 `src/tau2/user/user_simulator.py`, fetched this session): guidelines live in `data/tau2/user_simulator/simulation_guidelines[_tools|_voice...].md`; docstring states persona is controlled in **three places** (global guidelines, task-baked `UserScenario.persona`, runtime `PersonaConfig`) — relevant for anyone adding personas.

### 1.6 Headline results

- gpt-4.1 pass^1: retail 74%, airline 56%, **telecom 34%**; o4-mini 42%, claude-3.7-sonnet 49%, gpt-4.1-mini ~50% on telecom (`:456-464`).
- **Dual-control ablation** (`:465-486`, `:563-566`): no-user → default drops pass^1 by 18% (gpt-4.1) / 25% (o4-mini) — coordination/communication is a distinct bottleneck from reasoning. Oracle-plan mode isolates collaboration-only performance (73%/96% pass^1).
- Performance → ~0 beyond ~7 actions in default mode (`:576-586`); Hard persona hurts (Fig. 7, `:702-790`).
- Agent settings (`:372-380`): LiteLLM for all API calls; agents and user sim are function-calling agents; tools in OpenAI format; temperature 0; 4 runs/task.
- **Cost** (`:453-455`): gpt-4.1 agent/user = **$0.086 / $0.059 per task**; **~$40 for all domains × 1 trial**.

### 1.7 Stated limitations (paper's own, Conclusion `:822-837`)

1. User simulator still imperfect; tool-augmentation not yet applied back to airline/retail.
2. **Domain extension "still heavily relies on human experts"**; automating domain curation is open.
3. Does **not model the expert-novice gap** (adapting explanations to the user's mental model).

---

## 2. Repo verification (github.com/sierra-research/tau2-bench)

`gh api repos/sierra-research/tau2-bench` (session 3, 2026-10-24): **exists**, MIT license, Python, **2,307★ / 604 forks, 298 open issues**, created 2025-06-09, **pushed 2026-10-22** (actively maintained), default branch `main`, not archived. Full tree fetched (session 1: 1,615 files → `repo_tree.txt`; session 3: shallow clone at `cc1df47`, 2,194 files).

| Fact | Value | Receipt |
|---|---|---|
| License | **MIT** | `gh api` `.license.spdx_id`; `LICENSE` ("Copyright (c) 2025 Sierra Research") |
| Python | **>=3.12,<3.14** (both v1.0.1 and v2.0.0) | `pyproject.toml` fetched at both tags (session 3 via `gh api .../contents/pyproject.toml?ref=v1.0.1` + clone); v0.1.0 (paper era) required `>=3.13` (session 1) |
| Version | **2.0.0 (τ-i18n)** on main; 1.0.1 (τ³) tag = 1.x-comparable | `pyproject.toml` in clone (`version = "2.0.0"`); CHANGELOG `## [2.0.0] - 2026-10-19` |
| Install | `uv sync` (+extras: voice, knowledge, gym, dev) | README:61-76 |
| LLM providers | **Any LiteLLM model string** — `--agent-llm` / `--user-llm` accept `anthropic/...`, `openai/...`, Azure, Ollama, etc.; keys via `.env` (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`; voice adds ElevenLabs/Deepgram; knowledge adds OpenRouter) | DeepWiki Q&A on repo + `.env.example` fetched this session; `litellm>=1.80.15,<1.82.7` pinned in `pyproject.toml:22`; paper §4.1 "All LLM API calls are implemented using the Litellm package" |
| CLI | `tau2 run --domain airline --agent-llm gpt-4.1 --user-llm gpt-4.1 --num-trials 1 --num-tasks 5` | README:88-91 |
| Parallelism | `--workers 0` → in-process ThreadPoolExecutor with `--max-concurrency`; `--workers N>0` → controller/worker (FastAPI lease queue), `--provider-limit openai=40,gemini=20` | DeepWiki Q&A on repo (Runner Framework page) |
| Ablations | `--no-user-mode`, oracle-plan flags built into CLI | `docs/cli-reference.md:322-346` (fetched) |
| Domains | `mock` · `airline` · `retail` · `telecom` · `banking_knowledge` · **`intake`** (new in 2.0) | `src/tau2/domains/README.md` "Available Domains" table (session-3 clone) |

### 2.1 How domains/tasks are defined in code

`src/tau2/domains/README.md` (fetched, `domains_readme.md`): a domain = folder with `data_model.py` (subclass of `DB` from `tau2/environment/db.py`), optional `user_data_model.py` (user-side DB — this is what makes dual-control), `tools.py` (subclass of `ToolKitBase`), optional `user_tools.py`, `environment.py` (`get_environment()`, `get_tasks()`, `get_tasks_split()`), `utils.py`. **Data** lives in `data/tau2/domains/<name>/`: `tasks.json`, `split_tasks.json` (must define a `base` split), `policy.md`, `db.json|toml`, optional `user_db.json|toml`. **Registration** = 3 lines in `registry.py` (`register_domain` + `register_tasks`, domains README:80-92). Telecom additionally ships the **generator** (`src/tau2/domains/telecom/tasks/*.py`) — verified in `service_issues.py`: atomic helpers returning `EnvFunctionCall(env_type="user"|"assistant", func_name, arguments)` and `EnvAssertion(...)` lists plus `is_fixed(env)` checkers; compose via `TaskManager`/`SelectionSet`.

Tools are plain Python functions decorated `@is_tool(ToolType.READ|WRITE)` with docstrings surfaced to the LLM (paper Fig. 1); the `docstring-parser` dep parses them into OpenAI tool schemas.

### 2.2 Repo evolution relevant to us

- README:35 backward-compat note: for **agent evaluation** use the `base` task split (full task set matching original τ-bench structure).
- README:26 v1.0.1 grading warning: `banking_knowledge` scores not comparable across 1.0.1; other domains unaffected.
- The 75+ SABER task fixes (v1.0.0) mean **current airline/retail/telecom scores ≠ paper Table numbers**; pin `pre-v1.0.1` tag or older to reproduce the paper.
- **v2.0.0 (2026-10-19, session-3 additions):** 2.0 replaced 50 English retail+telecom tasks, switched communication checks to a semantic LLM judge (gpt-5.5, `--communicate-scorer substring` restores 1.x), moved the NL-assertion judge to `gpt-5.4-mini-2026-03-17`, and defaults the released-benchmark user simulator to `openai/gpt-5.5` (custom runs still default `gpt-4.1-2025-04-14`, temperature 0 — paper defaults) [repo: `README.md` §"Comparing with v1.0.1"; `docs/running-the-benchmark.md` "Defaults" table]. `OPENAI_API_KEY` is therefore **mandatory in practice even for non-OpenAI agents** (user sim + both judges are OpenAI models). New `tau2 run-pass3` subcommand computes pass^3 directly. Judge cost can be previewed: `tau2 judges suite --dry-run` prints an upper bound on judge requests.
- **The repo's own cost/runtime doc is an explicit TODO** as of 2.0: `docs/running-the-benchmark.md` §"Cost and time" says "add rough API cost and wall-clock time … The repository has no recorded full runs to derive these from" — so §4's paper-era figures remain the only sourced cost anchor.

---

## 3. Competitor sweep (2024-2026)

| Benchmark | What it is | What it lacks vs τ²-bench |
|---|---|---|
| **τ-bench** (Sierra, arXiv:2406.12045, 2024) | Original single-control Tool-Agent-User benchmark; retail+airline; pass^k; user = passive info provider constrained only by NL instructions | No user-side tools/actions; user-sim error 40%/12% critical on retail (τ² paper Table 2) |
| **UserBench** (Salesforce, arXiv:2507.22034, Jul 2025) | Gym environment for user-centric agents; users start with **underspecified goals**, reveal preferences incrementally; tests proactive preference discovery (<30% uncovered by top LLMs) | 5 tools, no tool complexity, no dual-control (user never acts on the world); no policy-compliance axis |
| **SOTOPIA** (arXiv:2310.11667, ICLR'24; sotopia.world) | Open-ended social-interaction arena between LLM agents; goal-following, relationship, secrecy dimensions; LLM/human judges | No tools/DB state, no verifiable programmatic reward (judge-based), not customer-service/policy grounded |
| **ToolSandbox** (Apple, NAACL 2025 Findings) | Stateful tools, implicit state dependencies, built-in user simulator, milestone-based dynamic eval | User is conversational only — no user-side state-changing tools; no pass^k reliability axis |
| **VitaBench** (arXiv:2509.26490, 2025) | 66 tools across delivery / in-store / travel; 100 cross-scenario + 300 single-scenario tasks; rubric-based sliding-window evaluator; **deliberately removes domain policies** | User simulator follows τ-bench style (no user tools); no dual-control; rubric/LLM judging instead of DB-hash/assertion verification. Its own comparison table credits τ²-bench as the only prior benchmark with full dual-control ("Tool Complexity ✓ / Behavior Attributes ✓") |
| **NCUser** (arXiv:2509.23124, 2025) | Non-collaborative user simulators (unavailable requests, digressions, impatience, incomplete utterances) on MultiWOZ + τ-bench | An adversarial-user layer, not a benchmark; no dual-control state |
| **CRAB-Bench + RUSE** (CMU, arXiv:2606.01815, 2026; added 2026-10-19) | Constraint-graph task generation (CSP-solver seed solutions, distractor-populated DB) + **human-aligned user simulation** (RUSE: 4 behavioral dimensions from human-subject studies, 3 personas); state-based verifiers (concrete + abstract). Best frontier model 61% pass@1; switching to RUSE users drops scores up to 57%. **Explicitly argues τ-bench/τ²-bench "use cooperative, template-like user simulators and rigid ground-truth evaluation, and have already been largely saturated."** | The most direct 2026 attack on τ²'s design assumptions: it concedes τ²'s dual-control but replaces the user sim with human-behavior-grounded ones and loosens single-solution ground truth to multi-solution constraint verification. No voice/knowledge axes; not domain-policy grounded the way τ²'s policy.md is |
| **MM-tau-p2** (Sprinklr, arXiv:2603.09643, 2026; added 2026-10-19) | Persona-adaptive **multimodal** (text+voice) dual-control evaluation over τ²'s telecom+retail domains; 12 LLM-as-judge metrics; explicitly targets the expert-novice gap τ² lists as a limitation | LLM-judge metrics (not programmatic DB-hash verification); builds *on* τ² rather than replacing it — confirms the harness is the community substrate, but its "persona adaptation" angle overlaps with extension idea (3) in §5 |
| **Toloka τ-bench extension** (blog, Sep 2025; added 2026-10-19) | Domain-agnostic framework for generating **fully auto-evaluable policy-adherence test cases** on any corporate policy (task completion *and* correct refusal), human-in-the-loop validated, deterministic DB-state pass/fail | Single-control (agent tools only — no user-side tools); no public code found on the blog; demonstrated on security/account/orders/financial-transfers failure cases, not e-commerce coupon/VAT mechanics |
| **UserProxyBench** (arXiv:2609.38043, 2026) | Evaluates the **user simulators themselves** over the τ-bench family; User Fidelity Score; finds 24.4% of successful episodes contain user-spec violations; premature disclosure dominates | Meta-evaluation layer, not a competitor domain; complements τ² |
| FlowBench / IntellAgent / APIGen-MT / ToolTalk / MINT / IN3 / DialogTool | τ-bench follow-ups (workflow injection, policy-graph synthetic suites, data-gen for fine-tuning, predefined trajectories, feedback, intent detection, role-play) | Per τ² related work (§2): none give the user state-changing ability; mostly single-control or non-verifiable |
| **τ³ extensions in-repo** (2026) | τ-Voice (full-duplex voice, arXiv:2603.13686), τ-Knowledge (`banking_knowledge` RAG domain, arXiv:2603.04370) | Same org — these are the official extensions, so novelty claims must clear them |

**Gap confirmed by four independent sources (updated 2026-10-19):** no 2025-2026 benchmark outside the τ-family combines (a) user-side tools over a shared mutable world, (b) programmatic DB-hash/assertion verification, and (c) pass^k reliability — VitaBench's own comparison table (arxiv.org/html/2509.26490v2), UserProxyBench's framing ("τ²-bench extends this to dual-control settings where the user can also act on a shared environment"), and CRAB-Bench's related-work positioning all treat τ² as *the* dual-control reference — the 2026 challengers attack its user-sim realism and evaluation rigidity (CRAB-Bench/RUSE) or extend it (MM-tau-p2, UserProxyBench) rather than replace the dual-control substrate. **However**, the CRAB-Bench saturation charge is now the strongest published argument that a *plain new domain* on this harness is not enough: a contribution must add either (i) a structurally new control/compliance axis, (ii) human-aligned user realism, or (iii) automated domain-curation methodology (see §5).

---

## 4. Reproduction needs

- **Software:** `git clone` + `uv sync` (core, text mode). Python 3.12–3.13. No GPU, no local models required.
- **API provider:** any LiteLLM-supported provider. Cheapest faithful path: OpenAI key (`OPENAI_API_KEY`) and `--agent-llm gpt-4.1 --user-llm gpt-4.1` (paper's default user sim). Anthropic works via `anthropic/claude-...` strings (`ANTHROPIC_API_KEY`).
- **Cost (paper, `paper_text.txt:453-455`):** $0.086 (agent) + $0.059 (user) per task with gpt-4.1 ⇒ **~$40 for all 3 domains × 1 trial**; the paper's pass^4 protocol (4 trials) ⇒ **~$160 full-table reproduction**; single telecom pass^4 ≈ 114 × $0.145 × 4 ≈ **$66**; single domain pass^1 ≈ $10–17. A 10-task pilot ≈ **$1.5/trial**.
- **Runtime:** not stated in the paper (not found in the PDF text — checked). Bounded by LLM latency, not compute: conversations are ~30-80 turns (VitaBench table), serialized per conversation but parallel across tasks (`--max-concurrency`, default ThreadPool mode; distributed `--workers` mode available). Plan hours, not days, at concurrency ~10-40.
- **Pin for paper parity:** a 2025 tag (v0.1.x) — the 2026 SABER task fixes change scores (README:26-37, CHANGELOG); for 1.x-leaderboard parity use the `v1.0.1` tag; **2.0 frozen `text-v1` is a different object** (900 calls: 3 domains × 50 frozen tasks × 6 languages) whose cost is undocumented (repo TODO, §2.2) — price it with `--dry-run` + `tau2 judges suite --dry-run` before running.
- **Verification tooling shipped:** `tau2 check-data` (data config validation), `tau2 view` (results browser), `tau2 play` (interactive debugging), per-domain pytest suites (`tests/test_domains/test_<domain>`).

### 4.1 Measured runs already on disk (prior session, 2026-10-18 — not re-run this session)

The prior session of this lane actually cloned the repo (`repo/`, @ `96a3ef92`, v1.0.1), installed with `uv sync --extra dev` (+ a required `uv pip install "websockets>=13.0"` fix — README's core install is broken for the CLI on v1.0.1; receipts in `SMOKE.md`), passed the repo's own test suite, and executed sweeps. Results in `results/`:

| Run (from `results/summary.json`) | sims | pass^1 | pass^4 |
|---|---|---|---|
| airline (50 tasks × 4 trials) | 200 | 0.890 | 0.860 |
| retail (114 tasks × 4 trials) | 456 | 0.871 | 0.728 |
| ecommerce_poc (13 tasks, this lane's POC domain) | 52 | 0.942 | 0.846 |
| mock (control) | 40 | 0.725 | 0.600 |

- Measured token usage (`results/usage_retail.json`): 7,863 LLM calls / 36.98M prompt / 1.65M completion tokens for retail ×4 trials; `usage_telecom.json`: 26,710 calls / 154.2M prompt / 4.33M completion for the telecom sweep (`sweep_full.log`; telecom rows absent from `summary.json` — 0 sims recorded there, so telecom per-domain scores from that run are **not** summarized here).
- Wall-clock sample (`sweep_status.json`): ecommerce_poc 13 sims in 239.9 s (~18 s/sim serialized) — the only measured runtime datum on disk; scale by concurrency for planning.
- **These numbers are prior-session artifacts, cited as found; I did not execute them this session.** This session's checks were source-level (gh api / raw fetches / PDF re-extraction), documented in the receipts index.

---

## 5. Novelty space — what counts as a real contribution vs. trivial reskin

The paper's own limits section (`paper_text.txt:822-837`) names the openings: (1) applying tool-augmented user simulation beyond telecom, (2) **automating domain curation** ("extending domain coverage still heavily relies on human experts"), (3) modeling the expert-novice gap. The official line has since taken voice (τ-Voice), knowledge-RAG (τ-Knowledge), task-QA (SABER fixes), and — as of v2.0 — multilingual + entity elicitation (`intake`) — so those are closed too. A **text e-commerce domain with dual-control user actions remains open ground** (session-3 re-check: no e-commerce/coupon/VAT domain exists in the 2.0 tree; `retail` still has none — grep receipts below).

**Trivial reskin** (would not survive review): an e-commerce domain that is structurally retail/airline — agent-only tools, hand-written tasks.json, policy.md with return windows, no user-side state. That is exactly what the "115 hand-written retail tasks" already are (actual shipped reward_basis: 112×`[DB, NL_ASSERTION]` + 2×`[DB]`, per the §1.4 correction — retail uses `[DB, COMMUNICATE]` in 0/114 tasks); swapping product names adds nothing. **Prior-art check on the exact rule categories (done 2026-10-19; independently re-verified 2026-10-24 on the v2.0.0 clone):** the shipped retail domain already covers returns, exchanges, cancellations and refund routing (incl. gift-card balance rules) — `retail_policy.md:86-136` (sections "Cancel pending order" / "Modify pending order" / "Return delivered order" / "Exchange delivered order") and tools `cancel_pending_order`, `exchange_delivered_order_items`, `return_delivered_order_items`, `modify_pending_order_*` (session-3 re-check: `src/tau2/domains/retail/tools.py:191` `cancel_pending_order`, `:240` `exchange_delivered_order_items`, `:709` `return_delivered_order_items`, `:456-590` `modify_pending_order_*`) — but has **no coupon tools and no VAT/tax logic anywhere** (session-3 re-check: `grep -icE "coupon|vat|value.added|tax" data/tau2/domains/retail/policy.md` → **0**; `grep -icE "coupon|vat\b|value.added" src/tau2/domains/retail/tools.py` → **0**). So "e-commerce returns" alone is a reskin; **coupons and VAT are genuinely uncovered rule families**, and VAT in particular (place-of-supply, reverse charge, receipt splitting) is more combinatorial than telecom's device flags — that is the defensible core of the team's angle.

**Legitimate extension** for the team's ~10-task e-commerce angle, in increasing strength:

1. **Dual-control e-commerce** (moderate): give the *user* side tools — e.g., a mocked shopper device/app (`view_order_page`, `open_return_portal`, `scan_receipt`, `screenshot_checkout_error`, `re-enter_VAT_number`) with a `user_db` mirroring what the customer actually sees (order status, saved coupons, address book, VAT ID). Returns/coupons/VAT have natural user-side state: the customer's view of their cart/coupon ledger can diverge from the store DB (selective information hiding), and some fixes must be performed by the user in their own account. This mirrors the telecom asymmetry design and directly answers paper-limitation (1) outside telecom. Target user-sim error ≤ telecom's 16%/6% and report it with the same 2-annotator protocol.
2. **Compositional task generator for e-commerce rules** (stronger): encode the real store's return/coupon/VAT rules as atomic subtasks `{f_init, f_sol, f_assert}` groups (e.g., *coupon expired* × *item final-sale* × *VAT-ID-mismatch* × *cross-border threshold*) with automatic solvability verification (init → solution → assert, and not-solved-before-all-steps, `paper_text.txt:338-342`). ~10 curated tasks then scales to hundreds, with difficulty = #subtasks. This is the paper's contribution (2) applied to a genuinely rule-dense commercial domain — VAT interaction rules (place-of-supply, reverse charge, receipt splitting) are *more* combinatorial than telecom's device flags, which is a defensible claim.
3. **Persona × policy friction** (bonus): model the expert-novice gap (paper-limitation 3) via the existing 3-layer persona control (global guidelines / task persona / runtime `PersonaConfig` — `user_simulator.py` docstring) — e.g., a user who misreads VAT-inclusive pricing, or who insists on a coupon the policy excludes.

**Harness support for custom domains — assessment: clean.** Receipts: domain contract is fully documented (`domains_readme.md:5-36`); dual-control is a first-class, optional feature (`user_data_model.py`, `user_tools.py`, `user_db.toml` are declared optional files); registration is 3 lines in `registry.py` (`domains_readme.md:80-92`); the `mock` domain exists explicitly "for unit testing" of the core loop (paper B.1 `:1241-1244`); evaluation is path-independent (DB-hash target derived by replaying reference actions — `docs/evaluation.md`), so partial tool-surface differences don't break scoring; CLI exposes `--no-user-mode`/oracle-plan for ablation, and `tau2 check-data` + pytest patterns give a validation path. **Effort estimate for the team's 10 tasks:** dominated by authoring `db.json` fixtures + policy.md + writing env-assertion functions; the harness itself imposes ~6 boilerplate files (4 of which can be copied from `mock`/`retail` and trimmed). One real dependency: user tools must produce *human-readable* outputs only and stay reactive to preserve complexity asymmetry (paper design constraint) — that's authoring discipline, not framework friction. Caveat: pin a version (v1.0.1 vs pre-1.0.1 grading) and state it, given the repo's grading churn.

---

## 6. Risks

1. **Benchmark is a moving target.** 6+ releases in 17 months; v1.0.0 changed task definitions (75+ fixes), v1.0.1 changed grading, and v2.0.0 again replaced 50 tasks and swapped the communication check to a semantic judge — three protocol breaks since the paper. Any comparison must pin commits; leaderboard parity work is already non-trivial (README warnings, session 3).
1b. **"Largely saturated" charge (added 2026-10-19).** CRAB-Bench (arXiv:2606.01815) explicitly frames τ/τ² as saturated with cooperative template users and rigid ground truth; UserProxyBench shows the user proxy itself moves reward ~15 points. A new domain published without (a) a current-frontier-model pilot showing it is *not* trivially solved and (b) a user-simulator error audit will be dismissed on these grounds. The measured runs on disk reinforce this: prior-session airline/retail sweeps scored 0.87-0.89 pass^1 (paper-era gpt-4.1: 0.56-0.74) — the current model generation already scores far higher than the paper table, so task difficulty must be re-calibrated (more subtasks, harder personas) before any claim of a discriminating benchmark.
2. **Saturation drift.** Paper-era SOTA was 34-49% pass^1 on telecom; current leaderboard (taubench.com) scores newer models substantially higher (per CHANGELOG mentions of GPT-5.x runs). A new domain must pilot-test against ≥2 current frontier models to confirm it isn't trivially solved — the paper's own difficulty dial (#subtasks) should be tuned accordingly.
3. **User-simulator noise floor.** Even the best telecom design has 16% error / 6% critical; UserProxyBench (2026) shows 24.4% of *successful* τ-family episodes contain user-spec violations and that user-proxy choice alone moves reward ~15 points. Budget for the 2-annotator error audit, or the domain's scores are confounded.
4. **Dual-control is the moat and the trap.** If the e-commerce domain ends up effectively single-control (user tools decorative), it collapses into "retail reskin" (see §5). Conversely, too-empowered user tools break complexity asymmetry and the user sim degrades to an autonomous solver.
5. **Rule-grounding burden.** "Modeled on a real store's rules" — VAT/coupon/return rules must be *consistent and verifiable* (assertions must be decidable from DB state). Real-world policies are famously self-contradictory; expect a manual-refinement loop like the paper's Stage 5, and the SABER experience shows even Sierra's own hand-written tasks contained 75+ defects.
6. **License/attribution:** MIT — permissive for derivative domains; cite both τ² (2506.07982) and τ-bench (2406.12045) per README citation block. No data-license issue for code-authored domains.
7. **Cost/runtime risk is low** (~$66 for a telecom-scale pass^4; ~$1.5 for a 10-task pilot trial) but non-zero at k=4 with frontier pricing; OpenRouter/local routes exist via LiteLLM if budget-constrained, at fidelity cost.

---

## Receipts index

**Paper (downloaded + pypdf-extracted this session; `tss/tsis-deepdive/tau2-bench/`):**
- `tau2bench_paper.pdf` (47 pp.) ← `curl -sL https://arxiv.org/pdf/2506.07982`
- `paper_text.txt` — Dec-POMDP `:217-256`; Table 1 `:296-298`; 5-stage creation `:300-359`; eval criteria `:360-370`; settings+cost `:372-455`; results `:456-464`; ablation `:465-486,563-566`; reliability/Table 2 `:693-819`; conclusion/limits `:822-837`; task dist. `:934-953`; personas `:954-976`; example task `:977-1038`; agent prompt `:1269-1284`; user prompt `:1285-1334`; user-instruction examples `:1335-1374`.
- ICML 2026 publication: proceedings.mlr.press/v306/barres26a.html (PMLR v306 pp. 6736-6782).

**Repo (all fetched via `gh api` this session, saved under the same dir):**
- `gh api repos/sierra-research/tau2-bench` → MIT / Python / 2251★ / pushed 2026-10-16.
- `repo_readme.md` (218 lines) — install, CLI, domains, version notes; `repo_tree.txt` (1,615 paths).
- `domains_readme.md` (93 lines) — domain structure & registration contract.
- `pyproject.toml` — v1.0.1, `requires-python = ">=3.12,<3.14"`, `litellm>=1.80.15,<1.82.7`.
- `cli_reference.md` — run/play/check-data/no-user/oracle-plan flags.
- `docs/evaluation.md` (repo) — reward product, DB-hash semantics, ACTION gating. **Caveat (2026-10-18): its TL;DR ("default `reward_basis` for airline/retail/telecom is `[DB, COMMUNICATE]`") and ACTION-usage note are stale vs the shipped v1.0.1 data — see the correction in §1.4 and `UPSTREAM_DOCS_ERRATA.md`; reported upstream as [issue #635](https://github.com/sierra-research/tau2-bench/issues/635) (filed 2026-10-18, open).**
- `data/tau2/domains/{airline,retail,telecom}/tasks.json` (cloned repo, re-parsed 2026-10-18) — reward_basis distributions: airline 50×`[DB, COMMUNICATE]`; retail 112×`[DB, NL_ASSERTION]` + 2×`[DB]`; telecom 2253×`[ENV_ASSERTION]` + 32×`[ENV_ASSERTION, ACTION]` (20 of the ACTION tasks in the `base` split). Also `src/tau2/data_model/tasks.py:435` (schema default_factory) and `:257-258` (stale docstring).
- `src/tau2/user/user_simulator.py` (head 120 lines) — 3-layer persona control, guidelines files.
- `src/tau2/domains/telecom/tasks/service_issues.py` (head 100 lines) — generator pattern.
- `data/tau2/domains/airline/tasks.json[0]` — task JSON schema instance.
- Task counts: airline 50 / retail 114 (contents API); telecom 2,285 + splits `{base:114,...}` (raw fetch + split_tasks.json).
- Releases: v0.1.0(2025)→v1.0.1(2026-07-22); CHANGELOG head (grading warnings).
- DeepWiki Q&A (sierra-research/tau2-bench): parallelism (`--workers`, `--max-concurrency`, `--provider-limit`) + LiteLLM provider config.

**Web:** arXiv abs/PDF 2506.07982; sierra.ai blog (dual-control modes); UserBench arXiv:2507.22034; VitaBench arXiv:2509.26490 (comparison table); SOTOPIA arXiv:2310.11667; ToolSandbox ACL 2025.findings-naacl.65; NCUser arXiv:2509.23124; UserProxyBench arXiv:2609.38043; RealUserSim arXiv:2605.20204.

**Session 3 (2026-10-24) — all commands run this session:**
- Skills loaded first per ask: `search-first`, `deep-research`, `research-ops`, `gem-hunt` (`.zcode/skills/*/SKILL.md`, read in full). exa/deepwiki MCPs named in the ask were **absent** from this session's toolset — substituted WebSearch/WebFetch/`gh api`/arXiv API (recorded as a substitution, §"Not done").
- Paper re-verified: `curl -sL https://export.arxiv.org/api/query?id_list=2506.07982` → title/authors/pubdate match; PDF re-downloaded (1,243,001 bytes, PDF 1.5, 47 pp via pypdf), pages 1–20 read in full (abstract, intro, related work, formalism §3.1, task creation §3.2, eval §3.3, experiments §4 incl. cost line, reliability Table 2, conclusion §5, Appendices A–B). Facts in §1 cross-checked — no discrepancies with sessions 1–2. τ-bench (`2406.12045`) and UserBench (`2507.22034`) arXiv records verified via the same API.
- Repo: `gh api repos/sierra-research/tau2-bench` (2,307★/604 forks/298 issues/pushed 2026-10-22, MIT); `git clone --depth 1` @ `cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2` (2026-10-22, "Merge pull request #675"); read: `README.md` (τ-bench 2.0 banner, benchmark table, v1.0.1-comparability section), `pyproject.toml` (v2.0.0, `requires-python = ">=3.12,<3.14"`, `litellm>=1.80.15,<1.82.7`), `LICENSE` (MIT 2025 Sierra Research), `CHANGELOG.md` release headers (incl. `## [2.0.0] - 2026-10-19`, `## [1.0.1] - 2026-07-15`), `docs/running-the-benchmark.md` (benchmarks table, defaults table, cost-and-time TODO, run-pass3), `docs/evaluation.md` (reward product, DB-hash semantics, ACTION gating), `src/tau2/domains/README.md` (full domain contract + registration snippet), `src/tau2/data_model/tasks.py` (`Task` @ 560, `EvaluationCriteria` @ 366, `RewardType` enum, `StructuredUserInstructions`, `EnvFunctionCall`/`EnvAssertion`), `src/tau2/registry.py` (domain/task registration imports), `src/tau2/domains/telecom/tasks/create_tasks.py` + `manager.py` (`TaskManager`, `verify_task` @ `manager.py:197` — broken-before/fixed-after/no-prefix-fixes assertions), `src/tau2/utils/llm_utils.py` (`import litellm` @ :14, `completion(...)` @ :677), `src/tau2/user/user_simulator_base.py` (STOP/TRANSFER/OUT-OF-SCOPE tokens, user state), `data/tau2/domains/retail/tasks.json` (task `id:"0"` exchange task, `reward_basis: ["DB","NL_ASSERTION"]`), `ls tests/test_domains/` (6 domain test dirs).
- v1.0.1 parity check: `gh api repos/sierra-research/tau2-bench/contents/pyproject.toml?ref=v1.0.1` → also `>=3.12,<3.14`, MIT, v1.0.1.
- Retail coupon/VAT absence re-verified: `grep -icE "coupon|vat|value.added|tax" data/tau2/domains/retail/policy.md` → 0; `grep -icE "coupon|vat\b|value.added" src/tau2/domains/retail/tools.py` → 0; return/exchange/modify tool line numbers captured (`tools.py:191,240,456,500,590,709`).
- Web (session 3): WebSearch — UserBench (arXiv:2507.22034 + OpenReview QtyRFfLD4U), SOTOPIA status (active; Sotopia-RL arXiv:2508.03905; sotopia.world), τ-bench alternatives (BFCL V4 / AppWorld / RealUserSim / SWE-Together landscape), τ²-bench ICML 2026 oral + ~547 citations (openreview.net/forum?id=OC2z7iSQKa, icml.cc/virtual/2026/oral/71171). WebSearch rate-limited (−429) intermittently; affected queries were retried successfully except one raw sweep whose landscape was covered by the other queries.

**Session 2 (2026-10-19) — all commands run this session, artifacts in the same dir:**
- Paper re-downloaded independently (`curl -sL https://arxiv.org/pdf/2506.07982` → `tau2bench.pdf`, 47 pp., valid PDF 1.5) and re-extracted with pypdf 6.14.2 → `paper_full.txt` + `pages.json`; formalism (pp. 2-4), task generator (pp. 5-6), results/ablations (pp. 7-8), reliability Table 2 (p. 10), conclusion/limitations (p. 11) re-read. All §1 content cross-checked — no discrepancies with session 1.
- ICML 2026 venue re-confirmed by fetching `proceedings.mlr.press/v306/barres26a.html` (PMLR v306:6736-6782, "Proceedings of the 43rd International Conference on Machine Learning").
- `gh api repos/sierra-research/tau2-bench` → MIT / Python / 2,258★ / 585 forks / 274 open issues / pushed 2026-10-16 / homepage taubench.com.
- `gh api repos/sierra-research/tau2-bench/releases` → v0.1.2 (2025-07-17), v0.1.3 (2025-08-26), v0.2.0 (2025-10-06), v1.0.0 "τ³" (2026-03-18), v1.0.1 (2026-07-22) — matches session 1.
- `pyproject.toml` (fetched → `pyproject.toml`): `version = "1.0.1"`, `requires-python = ">=3.12,<3.14"`, `litellm>=1.80.15,<1.82.7`, MIT.
- README (fetched → `readme_main.md`): τ³ banner, 5 domains (`mock · airline · retail · telecom · banking_knowledge`), `uv sync` + extras, `tau2 run` quickstart, Python badge 3.12+, LiteLLM "any supported provider works", citation block (τ² 2506.07982; τ-bench 2406.12045; τ-Knowledge 2603.04370; τ-Voice 2603.13686; SABER ICLR'26 workshop).
- `src/tau2/domains/README.md` (fetched → `src_tau2_domains_README.md`): domain-folder contract + `registry.py` registration snippet (`:80-92`) + `banking_knowledge` specifics.
- `docs/evaluation.md` (fetched → `docs_evaluation.md`): reward-product semantics, DB-hash replay, ACTION gating, worked airline task-1 example.
- `docs/cli-reference.md` (fetched → `docs_cli.md`): `--num-trials`, `--max-concurrency` (default 3), `--timeout`, `--agent-llm`/`--user-llm`(+`-args`).
- `.env.example` (fetched → `env_example.txt`): `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `DEEPGRAM_API_KEY`, `PINE_API_KEY`, `OPENROUTER_API_KEY`.
- `mock` domain `environment.py` (fetched): full `get_environment`/`get_tasks` implementation — copyable template.
- Task data re-verified from raw fetches: `telecom/tasks.json` = **2,285** tasks (ids like `[mobile_data_issue]user_abroad_roaming_disabled_on[PERSONA:Easy]`, persona + `known_info`/`unknown_info` + grounding instructions in `user_scenario`); `telecom/split_tasks.json` = `{small:20, train:74, test:40, full:2285, base:114}`; `airline/tasks.json` = 50; `retail/tasks.json` = 114 (task 0 reward_basis `[DB, NL_ASSERTION]`, agent tools incl. `exchange_delivered_order_items`).
- Retail prior-art grep (this session): `retail_policy.md` sections Cancel/Modify/Return/Exchange (`:86-136`); `retail_tools.py` — 15 `@is_tool` functions, **no coupon/VAT/tax tool** (only generic `calculate` at `:140`).
- Competitor fetches (this session): CRAB-Bench abstract (arxiv.org/html/2606.01815 — saturation quote, RUSE, 61% pass@1, 57% drop); MM-tau-p2 abstract (arxiv.org/html/2603.09643v4 — expert-novice gap framing, 12 LLM-judge metrics); UserProxyBench abstract (arxiv.org/html/2609.38043 — UFS, 15.2-point swing, 24.4% violations, premature disclosure); UserBench abs page (arxiv.org/abs/2507.22034 — gym for user-centric agents, ~20% full-intent match); SOTOPIA abs page (arxiv.org/abs/2310.11667 — confirmed LLM-judged social interaction, no tools/DB); Toloka blog (toloka.ai/blog/tau-bench-extension-... — policy-adherence test generation, single-control, no code link).
- Prior-session artifacts read as-found (not re-run): `SMOKE.md` (clone/install/websockets-fix/test-suite receipts, repo @ 96a3ef92), `results/summary.json` (airline/retail/ecommerce_poc/mock pass^k), `results/usage_*.json` (token counts), `results/sweep_status.json` (wall-clock), `poc/ecommerce_poc/` (working custom domain).

**Not done / not found:** wallclock runtime is not stated anywhere in the paper PDF or repo docs I read — flagged as such in §4 rather than estimated from thin air (the only measured datum is the prior-session 239.9 s / 13 ecommerce_poc sims in §4.1); as of v2.0.0 the repo's own cost/time section remains an explicit TODO (session-3 receipt, §2.2). No public code found for the Toloka extension. Telecom per-task results from the prior session's full sweep are not summarized in `summary.json` (0 sims recorded there despite `usage_telecom.json` showing 26,710 calls) — left unreported rather than reconstructed. **Session-3 tooling gaps (recorded, not blocking):** the exa and deepwiki MCP tools named in the task brief were not present in this session's toolset (substituted as noted above); the arXiv API over plain http returned empty bodies (https worked); WebSearch intermittently returned −429 rate limits (retried).
