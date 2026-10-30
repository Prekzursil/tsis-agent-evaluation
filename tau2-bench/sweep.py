"""GLM-driven full-scale tau2-bench sweep (lane-local; repo untouched).

Drives the harness's own batch runner (tau2.runner.batch.run_tasks) with:

  - agent under test  : openai/glm-5.3        (full tier)
  - user simulator    : openai/glm-5.3-flash  (flash tier)

against the custom domains (registered at runtime from poc/: the grown
14-task `ecommerce2` team e-commerce domain and the prior `ecommerce_poc`)
and every shipped domain. Both dual-control roles run on GLM via the
OpenAI-compatible coding-plan endpoint; the API key is read from the
ZAI_CODING_PLAN_KEY environment variable and never written to disk.

Checkpointing: each domain writes results/<domain>/results.json through the
harness's own checkpoint machinery (auto-resume skips completed
(task, trial, seed) units), so an interrupted sweep resumes instead of
restarting. Token usage is aggregated by a litellm success callback into
results/usage_<domain>.json after each domain.

Usage (repo venv):
  repo/.venv/Scripts/python.exe sweep.py --domains ecommerce_poc --trials 1
  repo/.venv/Scripts/python.exe sweep.py --domains all --trials 4 \
      --agent-model openai/glm-5.3 --user-model openai/glm-5.3-flash
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
POC_DIR = LANE_DIR / "poc"
RESULTS_DIR = LANE_DIR / "results"

sys.path.insert(0, str(POC_DIR))

ZAI_BASE = "https://api.z.ai/api/coding/paas/v4"

SHIPPED_ORDER = [
    "ecommerce2",  # grown 14-task team e-commerce domain (lane dir, runtime-registered)
    "ecommerce_poc",  # prior custom domain (registered at runtime)
    "mock",
    "airline",
    "retail",
    "telecom",  # base split (114), same as CLI default task set 'telecom'
    "telecom-workflow",
    "banking_knowledge",
]


# --------------------------------------------------------------------------
# Token accounting (observer only).
# tau2.utils.llm_utils resets litellm.success_callback at import time, so a
# litellm callback never fires; instead we wrap the completion() symbol the
# harness itself calls and read usage off every ModelResponse.
# --------------------------------------------------------------------------

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
    """Wrap tau2.utils.llm_utils.completion so every harness LLM call is counted."""
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
    ap.add_argument("--domains", default="all",
                    help="comma-separated domain list, or 'all'")
    ap.add_argument("--trials", type=int, default=4)
    ap.add_argument("--agent-model", default="openai/glm-5.3")
    ap.add_argument("--user-model", default="openai/glm-5.3-flash")
    ap.add_argument("--max-concurrency", type=int, default=4)
    ap.add_argument("--max-steps", type=int, default=100)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--seed", type=int, default=300)
    ap.add_argument("--task-ids", default=None,
                    help="optional comma-separated task id filter")
    args = ap.parse_args()

    api_key = os.environ.get("ZAI_CODING_PLAN_KEY")
    if not api_key:
        print("FATAL: ZAI_CODING_PLAN_KEY not set", file=sys.stderr)
        return 2

    RESULTS_DIR.mkdir(exist_ok=True)

    # Register the custom domain (poc/), then import the batch runner.
    from load_poc import register as register_ecommerce

    register_ecommerce()

    from load_ecommerce2 import register as register_ecommerce2

    register_ecommerce2()
    install_usage_wrapper()

    # Retail ships 112/114 tasks with NL_ASSERTION in reward_basis (40 with
    # non-empty assertion lists). The harness's NL judge hardcodes a default
    # OpenAI model; per the sweep's model plan annotators run on the flash
    # tier, so redirect the judge to glm-5.3-flash on the same endpoint
    # (response_format is required because the judge does a bare json.loads
    # and GLM otherwise wraps output in ```json fences).
    import tau2.evaluator.evaluator_nl_assertions as nle

    nle.DEFAULT_LLM_NL_ASSERTIONS = args.user_model
    nle.DEFAULT_LLM_NL_ASSERTIONS_ARGS = {
        "api_base": ZAI_BASE,
        "api_key": api_key,
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "num_retries": 8,
        "retry_after": 15,
    }

    from tau2.data_model.simulation import TextRunConfig
    from tau2.registry import registry
    from tau2.runner.batch import run_tasks

    domains = (
        SHIPPED_ORDER
        if args.domains == "all"
        else [d.strip() for d in args.domains.split(",") if d.strip()]
    )

    llm_args = {
        "api_base": ZAI_BASE,
        "api_key": api_key,
        "num_retries": 8,
        "retry_after": 15,
    }

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
            llm_args_agent=dict(llm_args),
            llm_user=args.user_model,
            llm_args_user=dict(llm_args),
            num_trials=args.trials,
            max_steps=args.max_steps,
            max_errors=10,
            timeout=args.timeout,
            max_concurrency=args.max_concurrency,
            seed=args.seed,
            max_retries=3,
            retry_delay=5.0,
            auto_resume=True,
            # banking_knowledge: the GLM coding endpoint exposes no embedding
            # model (GET /models lists chat models only), so the default
            # 'alltools' variant cannot be used; bm25_grep runs fully on GLM.
            **(
                {"retrieval_config": "bm25_grep"}
                if domain == "banking_knowledge"
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
                console_display=True,
            )
            sims = results.simulations if results else []
            rewards = [s.reward_info.reward if s.reward_info else 0.0 for s in sims]
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
