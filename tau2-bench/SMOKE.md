# SMOKE — tau2-bench lane (session 4, 2026-10-24)

All receipts below were produced **this session** (2026-10-24) on Windows 10
(Git Bash, `uv 0.10.4`). Every command was run from the lane root
`tss/tsis-deepdive/tau2-bench/` unless noted. Prior sessions' receipts:
`SMOKE_prior_session.md` (2026-10-18, v1.0.1) and `SMOKE_prior_2026-10-19.md`.

## 1. Clone + venv + install

Old clone (v1.0.1-era `96a3ef92`, clean tree — `git status --porcelain` → 0
lines) was replaced with a fresh shallow clone, per this session's ask:

```
$ rm -rf repo && git clone --depth 1 https://github.com/sierra-research/tau2-bench repo
$ cd repo && git rev-parse HEAD
cc1df47baa1544a34bb8c8e5c4ca72ad223b96a2        # 2026-10-22, v2.0.0 "τ-bench 2.0 / τ-i18n"
$ grep -E '^version|requires-python' pyproject.toml
version = "2.0.0"
requires-python = ">=3.12,<3.14"
```

Install (core text-mode + dev extras; Python 3.12.12 picked by uv):

```
$ cd repo && uv sync --extra dev --python 3.12        # ... + tiktoken==0.12.0, typer, yarl etc.
$ .venv/Scripts/python.exe --version
Python 3.12.12
$ .venv/Scripts/python.exe -c "from importlib.metadata import version; import tau2, litellm, pydantic; print(version('tau2'), version('litellm'), pydantic.VERSION)"
tau2-bench 2.0.0 | litellm 1.81.11 | pydantic 2.13.5
```

## 2. Offline smoke

### 2.1 CLI lists domains/tasks

```
$ .venv/Scripts/tau2.exe --help
usage: tau2 [-h] {judges,tasks,factory,benchmarks,run,run-pass3,languages,intake-tasks,play,view,domain,start,worker,intro,check-data,evaluate-trajs,review,leaderboard,submit,convert-results} ...
```

Registry listing (script):

```
$ .venv/Scripts/python.exe -c "from tau2.registry import registry; print(registry.get_domains())"
['mock', 'airline', 'retail', 'telecom', 'telecom-workflow', 'banking_knowledge', 'intake']
```

Task counts via registry loaders: `mock 10 · airline 50 · retail 114 ·
telecom 114 (base split of the 2,285-task full set) · telecom-workflow 114 ·
intake 200`. `banking_knowledge` loads only with the `knowledge` extra
(`ModuleNotFoundError: No module named 'rank_bm25'` without it — expected,
optional dependency).

### 2.2 Repo's own test suite (pytest)

Full core suite, optional-extra paths excluded (they cannot even be collected
on the core install: `tests/test_voice/*` → `No module named 'scipy'`,
`tests/test_gym/*`, `tests/test_streaming/test_voice_streaming_user_simulator.py`,
`tests/test_domains/test_banking_knowledge/test_retrieval_system.py`, and
`src/` (separate `agentify_tau_bench` sub-project). Exact command, run **twice**
(second run with `--tb=no`, full log in `pytest_full.log`):

```
$ .venv/Scripts/python.exe -m pytest -q -n auto -p no:cacheprovider \
    --ignore=tests/test_voice --ignore=tests/test_gym --ignore=tests/test_streaming \
    --ignore=tests/test_domains/test_banking_knowledge/test_retrieval_system.py --ignore=src
run 1: 430 failed, 2639 passed, 83 skipped, 57 warnings, 227 errors in 1552.29s
run 2: 428 failed, 2641 passed, 83 skipped, 75 warnings, 227 errors in 1365.52s   (exit 1)
```

**Result reported as it is: the suite does NOT pass green on this Windows
host at cc1df47.** Failure classes diagnosed this session (counts from
`pytest_full.log`, `--tb=line`/`--tb=short` re-runs of the failing groups):

| Class | Evidence | Count / share |
|---|---|---|
| **Windows temp-dir file locks** — `PermissionError: [WinError 32] The process cannot access the file ... pytest-of-Prekzursil\...` raised from `pathlib.py:1342 unlink` during fixture cleanup | reproduced single-threaded (e.g. `test_factory_stage_requests.py::test_documented_draft_request_example_validates`), so NOT purely an xdist artifact | dominant cause across `tests/test_multilingual` (262 F + 78 E), `tests/test_judges` (20 E), parts of `test_task_subsets` |
| **Missing optional extras** — `ModuleNotFoundError: No module named 'rank_bm25'` from `src/tau2/knowledge/document_preprocessors/bm25_indexer.py:3` | `test_retrieval_e2e.py` alone: 99 of its 75F/26E | ~100 |
| **Upstream defect (ships broken at cc1df47): frozen task-subset SHA pins** — `ValueError: frozen subset airline_50 changed; publish a new name` from `src/tau2/task_subsets/store.py:57`. Independently proven: all 3 entries of `SHIPPED_SUBSET_SHA256` mismatch the shipped files (`airline_50 d55a20e8…≠055b5d4f…`, `retail_50 8515d84c…≠dc7490f0…`, `telecom_50 fdb9c51f…≠c6376fe2…`); `tau2 tasks list` therefore fails on a clean clone | `test_task_subsets`, `test_benchmark`, `test_voice_v2_release_domains` errors | 32+20+6 E and cascading F |
| **Live-network tests inside the suite** — 2 tests in `test_retrieval_e2e.py` call OpenRouter embeddings for real and failed `402 insufficient credits` (`Error code: 402 - {'error': {'message': 'Insufficient credits...'}}`, model `qwen/qwen3-embedding-8b`) | the repo's own suite is not fully offline by design | 2 |
| `tests/test_domains/test_intake/*` (~75), `test_benchmark` (~45) | not individually triaged this session — same groups as above (multilingual/intake/benchmark infrastructure); stated as not fully triaged | ~120 |

Working-tree `git status` stays clean apart from `data/simulations/` outputs.
The suite **as shipped cannot be made green on Windows at this commit** without
upstream fixes (subset pins) and Windows tmp-handle handling; this is recorded
as an environment/upstream finding, not silently dropped.

## 3. Real end-to-end run (one cheapest task, cap ~$1)

LLM keys present in env: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `ZAI_API_KEY`,
`OPENROUTER_API_KEY` (names only inspected; `OPENROUTER` has zero credits —
402 receipt above). Cheapest lane (prior-session discovery, re-verified this
session): **ZAI `glm-4.5-flash` — free tier** via litellm's `openai/`
provider with `api_base=https://api.z.ai/api/paas/v4`.

Connectivity probe (this session):

```
$ OPENAI_API_KEY="$ZAI_API_KEY" .venv/Scripts/python.exe -c "import litellm; r = litellm.completion(model='openai/glm-4.5-flash', api_base='https://api.z.ai/api/paas/v4', messages=[{'role':'user','content':'Reply with exactly: OK'}], temperature=0); print(r.choices[0].message.content, r.usage.prompt_tokens, r.usage.completion_tokens)"
PROBE OK: OK 10 in / 205 out
```

Plan resolved first with `--dry-run` (no provider calls; confirmed
`communicate_scoring: {scorer: substring, judge: null}`), then the real run:

```
$ cd repo && OPENAI_API_KEY="$ZAI_API_KEY" .venv/Scripts/tau2.exe run \
    --domain mock --task-ids create_task_1 --num-trials 1 \
    --max-steps 40 --max-errors 5 --timeout 900 \
    --agent-llm openai/glm-4.5-flash --agent-llm-args '{"api_base":"https://api.z.ai/api/paas/v4"}' \
    --user-llm openai/glm-4.5-flash --user-llm-args '{"api_base":"https://api.z.ai/api/paas/v4"}' \
    --communicate-scorer substring --save-to zai_smoke_v2_mock
# exit 0
```

Outcome (from `data/simulations/zai_smoke_v2_mock/results.json`, copied to lane
root `results_smoke_zai_v2_mock.json`): 1 simulation recorded, task
`create_task_1`, duration **642.26 s**, 42 messages (21 assistant / 18 user /
3 tool), `termination_reason: "max_steps"`, `reward: 0.0` (reward_info note:
"Simulation terminated prematurely. Termination reason: max_steps") — the free
model loops instead of closing the mock conversation; an earlier attempt of
the same command finished in 13.3 s with reward 0.0 (user-sim ended it
instantly), i.e. high variance on this model. The eval loop itself (agent,
user simulator, orchestrator, evaluator, results save) executed end-to-end.

**Cost: $0** — GLM-4.5-Flash is Z.AI's free-tier model (¥0/M in+out,
https://docs.bigmodel.cn/cn/guide/models/free/glm-4.5-flash; prior-session
receipt re-confirmed this session by unrestricted calls + litellm's
`This model isn't mapped yet. model=glm-4.5-flash` — the harness records
`agent_cost: None / user_cost: 0.0`). Well under the ~$1 cap.

## 4. PROOF-OF-CONTRIBUTION — `poc/ecommerce3` (2 native-format tasks, lane dir only)

Files (all in lane dir, **not** in the cloned repo): `poc/ecommerce3/`
(`__init__.py`, `data_model.py` — `EcomDB(DB)` with users/products/orders/
coupons; `tools.py` — 6 `@is_tool` agent tools: `find_user_by_email`,
`get_order_details`, `get_coupon_details` (READ) + `return_delivered_order_items`,
`apply_coupon_to_order`, `issue_vat_receipt` (WRITE); `environment.py` —
`get_environment`/`get_tasks`/`get_task_split` mirroring `src/tau2/domains/mock/
environment.py`; `data/` — `db.json`, `policy.md`, `tasks.json`,
`split_tasks.json`), plus `poc/load_ecommerce3.py` — the registration+proof
script.

The 2 tasks (`poc/ecommerce3/data/tasks.json`) are in the harness's native
`Task` JSON format (validated by `tau2.data_model.tasks.Task.model_validate`,
the same path `retail/environment.py:43-49` uses):

- **`return_coupon_001`** — customer returns one item of a delivered order;
  refund must go to the original credit card (policy). Reference trajectory:
  `find_user_by_email` → `get_order_details` → `return_delivered_order_items`;
  `reward_basis ["DB","NL_ASSERTION"]` (mirrors the shipped retail pattern,
  112/114 retail tasks use `[DB, NL_ASSERTION]` per research-sota.md §1.4).
- **`vat_invoice_002`** — B2B customer asks to apply coupon `SAVE10` (expired
  2026-09-30 — must be declined with the expiry date) and to get a VAT receipt
  with valid EU VAT ID `DE123456789`. Reference trajectory includes
  `get_coupon_details` (check) and `issue_vat_receipt` (write).

Harness-load proof (`repo/.venv/Scripts/python.exe poc/load_ecommerce3.py`,
fully offline, 10/10 PASS, exit 0):

```
PASS domain registered in tau2.registry — registry.get_domains() now contains 'ecommerce3'
PASS tasks load via registry loader (base split) — loaded 2 tasks: ['return_coupon_001', 'vat_invoice_002']
PASS environment builds via registry constructor; agent tools exposed — tools: ['apply_coupon_to_order', 'find_user_by_email', 'get_coupon_details', 'get_order_details', 'issue_vat_receipt', 'return_delivered_order_items']
PASS gold replay of reference actions mutates DB [return_coupon_001] — db hash f20b9f32.. -> b1528f5f..
PASS harness EnvironmentEvaluator scores reference trajectory DB=1.0 [return_coupon_001] — reward=1.0 breakdown={'DB': 1.0}
PASS reward_basis uses native RewardTypes [return_coupon_001] — reward_basis=['DB', 'NL_ASSERTION']
PASS gold replay of reference actions mutates DB [vat_invoice_002] — db hash f20b9f32.. -> 453a8140..
PASS harness EnvironmentEvaluator scores reference trajectory DB=1.0 [vat_invoice_002] — reward=1.0 breakdown={'DB': 1.0}
PASS reward_basis uses native RewardTypes [vat_invoice_002] — reward_basis=['DB', 'NL_ASSERTION']
PASS policy refusal is machine-checkable (expired coupon SAVE10 rejected) — apply_coupon_to_order raises; coupon stays expired; order has no coupon
```

Notes on fidelity: registration uses the documented 3-line contract
(`register_domain` + `register_tasks`, `src/tau2/registry.py:183-215`); the
evaluator call is the harness's own
`tau2.evaluator.evaluator_env.EnvironmentEvaluator.calculate_reward` with a
recorded trajectory whose tool outputs were generated by `env.get_response`
(the strict `set_state` replay compares recorded vs live outputs —
`src/tau2/environment/environment.py:380-412`). Executing these tasks against
a live agent needs an LLM key; loading/eval-machinery does not (proved above).

## 5. verify.py (offline gate)

`python verify.py` from the lane root (any ≥3.9 python; harness checks run in
the repo venv subprocess). **19/19 PASS, exit 0** this session. Covers exactly
the ask's four checks: repo cloned (origin URL + HEAD `cc1df47…` + clean
tree), venv deps import (`tau2` 2.0.0, litellm 1.81.11, pydantic 2.13.5),
task-format files parse (shipped airline 50 / retail 114 / telecom 2285 all
validate against the harness `Task` schema), POC tasks validate + registry
load + gold replay + evaluator reward 1.0 + refusal invariant. Prior gates
preserved: `verify_prior_session.py`, `verify_prior_session_ecommerce2.py`,
`verify_fullrun.py`.

## 6. Blockers / not done / caveats

- No blockers for the ask: clone/install/CLI/pytest/POC/verify all executed.
- pytest suite is **not green** on this Windows host at cc1df47 (see §2.2
  breakdown; upstream frozen-subset pin defect + Windows tmp-handle locks +
  missing optional extras + 2 live-network tests). Reported as-is.
- `tau2 tasks list` (frozen subsets) fails out of the box at cc1df47 —
  upstream defect, receipts in §2.2; does not affect `tau2 run` via registry.
- The mock end-to-end run scored reward 0.0 (model quality, not harness
  failure); a paid frontier model would be needed for a passing eval — out of
  scope under the $1 cap.
- banking_knowledge / voice / gym test paths not installed (optional extras)
  and not exercised beyond the collection-error classification above.
