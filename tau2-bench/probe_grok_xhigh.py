"""GROK-LANE tau2-bench v2.0.0 run (second-model batch on ecommerce3; lane-local).

Derived from sweep2.py; endpoint/key/model swapped, results isolated to results_v2_grok/.

Session 5 (2026-10-24). Drives the harness's own batch runner
(tau2.runner.batch.run_tasks) with:

  - agent under test  : openai/glm-5.3        (full tier)
  - user simulator    : openai/glm-5.3-flash  (flash tier)

against the grown custom domain `ecommerce3` (registered at runtime from
poc/) and every shipped domain of tau2-bench v2.0.0 @ cc1df47:
mock, airline, retail, telecom, telecom-workflow, banking_knowledge,
intake. Both dual-control roles run on GLM via the OpenAI-compatible
coding-plan endpoint; the API key is read from ZAI_CODING_PLAN_KEY and
never written to disk.

Scoring fidelity: communicate_scoring=substring (the paper's original
CommunicateEvaluator semantics, and the same scorer as this lane's v1.0.1
full run in RESULTS.md §1 — controlled comparison across harness
versions). The v2.0.0 default semantic judge is deliberately not used.

NL-assertion judge (retail's 112 NL tasks; intake user-sim utilities if
any) is redirected to glm-5.3-flash on the same endpoint.

Checkpointing: each domain writes results_v2/<domain>/results.json via the
harness checkpoint machinery (auto_resume skips completed
(task, trial, seed) units), so an interrupted sweep resumes instead of
restarting. Token usage is aggregated by wrapping
tau2.utils.llm_utils.completion (every harness LLM call — agent, user,
judges — routes through that module-global symbol, incl. generate()).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

LANE_DIR = Path(__file__).resolve().parent
REPO_DIR = LANE_DIR / "repo"
POC_PARENT = LANE_DIR  # lane root -> `poc` package
RESULTS_DIR = LANE_DIR / "results_v2_grok"

sys.path.insert(0, str(POC_PARENT))

GROK_BASE = "http://127.0.0.1:8182/v1"

SHIPPED_ORDER = [
    "ecommerce3",  # grown 14-task team e-commerce domain (lane dir, runtime-registered)
    "mock",
    "airline",
    "retail",
    "telecom",  # base split (114)
    "telecom-workflow",
    "banking_knowledge",
    "intake",
]

# ---------------------------------------------------------------------------
# Token accounting (observer only): wrap the completion() symbol the harness
# itself calls (agent turns, user turns, NL-assertion judge all route here).
# ---------------------------------------------------------------------------

usage_state: dict = {"calls": [], "flush_path": None}


def _record_usage(model, response):
    try:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        usage_state["calls"].append(
            {
                "model": str(model),
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
                "ts": time.time(),
            }
        )
    except Exception:
        pass


def install_usage_wrapper():
    import tau2.utils.llm_utils as llu

    if getattr(llu, "_usage_wrapped", False):
        return
    original = llu.completion

    def counting_completion(*args, **kwargs):
        resp = original(*args, **kwargs)
        model = kwargs.get("model")
        if model is None and args:
            model = getattr(args[0], "model", "?")
        _record_usage(model or "?", resp)
        return resp

    llu.completion = counting_completion
    llu._usage_wrapped = True


def flush_usage(domain: str) -> dict:
    calls = usage_state["calls"]
    summary = {}
    for c in calls:
        s = summary.setdefault(
            c["model"],
            {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0},
        )
        s["calls"] += 1
        s["prompt_tokens"] += c["prompt_tokens"]
        s["completion_tokens"] += c["completion_tokens"]
    out = {
        "domain": domain,
        "total_calls": len(calls),
        "by_model": summary,
        "total_prompt_tokens": sum(s["prompt_tokens"] for s in summary.values()),
        "total_completion_tokens": sum(
            s["completion_tokens"] for s in summary.values()
        ),
    }
    path = RESULTS_DIR / f"usage_{domain}.json"
    path.write_text(json.dumps(out, indent=2))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domains", default="ecommerce3",
                    help="comma-separated domain list, or 'all'")
    ap.add_argument("--trials", type=int, default=2)
    ap.add_argument("--agent-model", default="openai/grok-4.7")
    ap.add_argument("--user-model", default="openai/grok-4.7")
    ap.add_argument("--max-concurrency", type=int, default=6)
    ap.add_argument("--max-steps", type=int, default=100)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--seed", type=int, default=300)
    ap.add_argument("--task-ids", default=None,
                    help="optional comma-separated task id filter")
    args = ap.parse_args()

    api_key = os.environ.get("GROK_LANE_KEY")
    if not api_key:
        import subprocess
        api_key = subprocess.run(["powershell", "-NoProfile", "-Command", "[Environment]::GetEnvironmentVariable('GROK_LANE_KEY','User')"], capture_output=True, text=True).stdout.strip()
    if not api_key:
        print("FATAL: GROK_LANE_KEY not set", file=sys.stderr)
        return 2

    RESULTS_DIR.mkdir(exist_ok=True)

    # Register the grown custom domain (poc/), then import the batch runner.
    from poc.load_ecommerce3 import register as register_ecommerce3

    register_ecommerce3()
    install_usage_wrapper()

    # Upstream defect at cc1df47 (v2.0.0): registry.py:336-338,344-349
    # registers telecom's task loader under the "telecom-workflow" alias,
    # but those tasks declare user_scenario.instructions.domain ==
    # "telecom", and the multilingual runtime validation
    # (multilingual/runtime.py:461-463, reached by EVERY run via
    # pin_language_artifacts -> load_language, which loads its own fresh
    # task copies through registry.get_tasks_loader) rejects the mismatch:
    # "task scenario domain disagrees with language binding" (reproduced in
    # isolation; the upstream test suite never runs this domain through the
    # language runtime). Lane-local accommodation, installed before any
    # run: wrap the registered telecom-workflow loader so every task copy
    # it returns carries the registered alias as its declared domain.
    # Documented deviation: StructuredUserInstructions renders this field
    # into the USER simulator's prompt ("Domain: telecom-workflow" instead
    # of "Domain: telecom" -- one word; agent prompt, tools, DB, action
    # checks and communicate checks are untouched).
    from tau2.registry import registry as _t2_registry

    _twf_loader = _t2_registry._tasks["telecom-workflow"]

    def _twf_aligned_loader(*args, **kwargs):
        loaded = _twf_loader(*args, **kwargs)
        for t in loaded:
            if t.user_scenario.instructions.domain != "telecom-workflow":
                t.user_scenario.instructions.domain = "telecom-workflow"
        return loaded

    _t2_registry._tasks["telecom-workflow"] = _twf_aligned_loader

    # Retail ships tasks with NL_ASSERTION in reward_basis. The harness's NL
    # judge defaults to an OpenAI mini model; redirect to glm-5.3-flash on the
    # same endpoint (annotators run on the flash tier; response_format is
    # required because the judge does a bare json.loads and GLM otherwise
    # wraps output in ```json fences).
    import tau2.evaluator.evaluator_nl_assertions as nle

    nle.DEFAULT_LLM_NL_ASSERTIONS = args.user_model
    nle.DEFAULT_LLM_NL_ASSERTIONS_ARGS = {
        "api_base": GROK_BASE,
        "api_key": api_key,
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "num_retries": 8,
        "retry_after": 15,
    }

    from tau2.data_model.elicitation import (
        ElicitationConfig,
        ElicitationStrategy,
    )
    from tau2.data_model.run_config import CommunicateScoring
    from tau2.data_model.semantic_communication import CommunicateScorer
    from tau2.data_model.simulation import TextRunConfig
    from tau2.registry import registry
    from tau2.runner.batch import run_tasks

    domains = (
        SHIPPED_ORDER
        if args.domains == "all"
        else [d.strip() for d in args.domains.split(",") if d.strip()]
    )

    llm_args = {
        "api_base": GROK_BASE,
        "api_key": api_key,
        "num_retries": 8,
        "retry_after": 8,
    }
    llm_args_agent = dict(llm_args, reasoning_effort="xhigh")
    llm_args_user = dict(llm_args, reasoning_effort="low")

    status = {}
    for domain in domains:
        if domain not in registry.get_domains():
            print(f"[{domain}] NOT IN REGISTRY -- skipping", flush=True)
            status[domain] = "not_registered"
            continue
        try:
            tasks = registry.get_tasks_loader(domain)()
        except Exception as e:
            print(f"[{domain}] task load failed: {type(e).__name__}: {e}", flush=True)
            status[domain] = f"task_load_error: {e}"
            continue
        if args.task_ids:
            keep = {t.strip() for t in args.task_ids.split(",")}
            tasks = [t for t in tasks if t.id in keep]
        if not tasks:
            print(f"[{domain}] no tasks to run", flush=True)
            status[domain] = "no_tasks"
            continue

        config = TextRunConfig(
            domain=domain,
            agent="llm_agent",
            user="user_simulator",
            llm_agent=args.agent_model,
            llm_args_agent=dict(llm_args_agent),
            llm_user=args.user_model,
            llm_args_user=dict(llm_args_user),
            num_trials=args.trials,
            max_steps=args.max_steps,
            max_errors=10,
            timeout=args.timeout,
            max_concurrency=args.max_concurrency,
            seed=args.seed,
            max_retries=3,
            retry_delay=5.0,
            auto_resume=True,
            # Paper-fidelity scorer: the original case-insensitive substring
            # CommunicateEvaluator (same as the v1.0.1 lane baseline).
            communicate_scoring=CommunicateScoring(
                scorer=CommunicateScorer.SUBSTRING
            ),
            # banking_knowledge: the GLM coding endpoint exposes no embedding
            # model, so embedding-based retrieval variants cannot run;
            # bm25_grep runs fully on GLM.
            **(
                {"retrieval_config": "bm25_grep"}
                if domain == "banking_knowledge"
                else {}
            ),
            # intake (v2.0.0): an elicitation domain. Its default
            # agent_directed strategy requires a VOICE run; the harness's own
            # validator directs text runs to the scaffolded ablation
            # (data_model/simulation.py:100-103: "select the scaffolded
            # strategy for the text ablation"). This is the intended text
            # path, not a workaround.
            **(
                {
                    "elicitation": ElicitationConfig(
                        strategy=ElicitationStrategy.SCAFFOLDED
                    )
                }
                if domain == "intake"
                else {}
            ),
        )

        dom_dir = RESULTS_DIR / domain
        dom_dir.mkdir(parents=True, exist_ok=True)
        save_path = dom_dir / "results.json"

        t0 = time.time()
        print(
            f"[{domain}] starting: {len(tasks)} tasks x {args.trials} trials "
            f"(agent={args.agent_model} user={args.user_model})",
            flush=True,
        )
        try:
            results = run_tasks(
                config,
                tasks,
                save_path=save_path,
                console_display=False,
            )
            sims = results.simulations if results else []
            rewards = [
                s.reward_info.reward if s.reward_info else 0.0 for s in sims
            ]
            summary = {
                "n_sims": len(sims),
                "mean_reward": (sum(rewards) / len(rewards)) if rewards else None,
                "wall_s": round(time.time() - t0, 1),
            }
            status[domain] = summary
            print(f"[{domain}] done: {json.dumps(summary)}", flush=True)
        except KeyboardInterrupt:
            usage = flush_usage(domain)
            print(
                f"[{domain}] INTERRUPTED after {round(time.time()-t0,1)}s; "
                f"checkpoint kept at {save_path}; usage so far: "
                f"{usage['total_prompt_tokens']}+{usage['total_completion_tokens']} tokens",
                flush=True,
            )
            raise
        except Exception as e:
            usage = flush_usage(domain)
            print(
                f"[{domain}] FAILED after {round(time.time()-t0,1)}s: "
                f"{type(e).__name__}: {e}\n{traceback.format_exc()}",
                flush=True,
            )
            status[domain] = f"failed: {type(e).__name__}: {e}"
            continue

        usage = flush_usage(domain)
        print(
            f"[{domain}] usage: {usage['total_calls']} calls, "
            f"{usage['total_prompt_tokens']} prompt + "
            f"{usage['total_completion_tokens']} completion tokens",
            flush=True,
        )

    (RESULTS_DIR / "sweep_status.json").write_text(json.dumps(status, indent=2))
    print("SWEEP STATUS:", json.dumps(status, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
