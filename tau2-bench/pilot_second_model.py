"""SECOND-AGENT-MODEL pilot (lane-local; repo untouched).

Critic follow-up to the glm-5.3 full sweep (RESULTS.md): the custom-domain
claim rested on ONE agent model. This pilot re-runs the same harness with
the SAME seeds and the user simulator UNCHANGED, but swaps only the agent:

  - agent under test  : openai/nvidia/nemotron-3-ultra-550b-a55b
                        (NVIDIA NIM, https://integrate.api.nvidia.com/v1,
                         key from env NVIDIA_API_KEY)
  - user simulator    : openai/glm-5.3-flash  (unchanged from the original
                        sweep: ZAI coding plan, env ZAI_CODING_PLAN_KEY)

Batches (per the ask):
  (a) ecommerce2 -- the full custom team e-commerce domain (14 tasks)
  (b) airline    -- a fixed 50-task slice of one shipped domain; airline
                    ships exactly 50 tasks (ids "0".."49"), so the slice IS
                    the complete domain; the task-id list is recorded in
                    fullrun/second_model_pilot.md

Everything else matches the original sweep.py run: seed=300, num_trials=4
(the paper's k), max_steps=100, timeout=900s, max_errors=10, auto-resume
checkpointing (separate results dir: results_secondmodel/<domain>/).
Per-trial seeds derive deterministically from (config.seed, num_trials) in
tau2.runner.batch (random.seed(300); 4x randint), so trial seeds are
identical to the original sweep.

Usage (repo venv):
  repo/.venv/Scripts/python.exe pilot_second_model.py --domains ecommerce2
  repo/.venv/Scripts/python.exe pilot_second_model.py --domains airline \
      --max-concurrency 5
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
RESULTS_DIR = LANE_DIR / "results_secondmodel"

sys.path.insert(0, str(POC_DIR))

ZAI_BASE = "https://api.z.ai/api/coding/paas/v4"
NIM_BASE = "https://integrate.api.nvidia.com/v1"

AGENT_MODEL_DEFAULT = "openai/nvidia/nemotron-3-ultra-550b-a55b"
USER_MODEL_DEFAULT = "openai/glm-5.3-flash"

PILOT_ORDER = [
    "ecommerce2",  # (a) full custom domain, 14 tasks
    "airline",  # (b) fixed 50-task slice of one shipped domain
]


# --------------------------------------------------------------------------
# Token accounting (observer only) -- same wrapper as sweep.py.
# --------------------------------------------------------------------------

usage_state: dict = {"calls": [], "flush_path": None}

# NIM (free-credit tier, contended with a sibling lane's ultra claim) returns
# 429s under sustained load while single calls succeed in <1-12s (measured
# 2026-10-21: 15 calls at 3s spacing -> 10x200 + 5x429). NIM also strictly
# validates the request body, so litellm's `retry_after` kwarg must NOT be
# forwarded (it caused 'Unsupported parameter(s): retry_after' 400s in the
# first smoke). This wrapper adds patient adaptive backoff on 429 only; the
# harness itself (seeds, evaluation, retry policy) is untouched.
RATE_LIMIT_BACKOFF_BASE_S = 20.0
RATE_LIMIT_BACKOFF_CAP_S = 120.0
RATE_LIMIT_MAX_ATTEMPTS = 12


def _is_rate_limit_error(e: Exception) -> bool:
    name = type(e).__name__
    return "RateLimitError" in name or "429" in str(e)[:300]


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
    import random as _random

    import tau2.utils.llm_utils as llu

    if getattr(llu, "_usage_wrapped", False):
        return
    original = llu.completion

    def counting_completion(*args, **kwargs):
        model = kwargs.get("model")
        if model is None and args:
            model = getattr(args[0], "model", "?")
        backoff = RATE_LIMIT_BACKOFF_BASE_S
        last_err = None
        for attempt in range(RATE_LIMIT_MAX_ATTEMPTS):
            try:
                resp = original(*args, **kwargs)
                _record_usage(model or "?", resp)
                return resp
            except Exception as e:
                if not _is_rate_limit_error(e):
                    raise
                last_err = e
                sleep_s = min(backoff, RATE_LIMIT_BACKOFF_CAP_S)
                sleep_s *= 0.7 + 0.6 * _random.random()  # jitter
                print(
                    f"[rate-limit] attempt {attempt + 1}/"
                    f"{RATE_LIMIT_MAX_ATTEMPTS} for model={model}: "
                    f"{type(e).__name__}; backing off {sleep_s:.1f}s",
                    flush=True,
                )
                time.sleep(sleep_s)
                backoff *= 1.5
        raise last_err

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
    ap.add_argument("--domains", default="ecommerce2,airline",
                    help="comma-separated domain list")
    ap.add_argument("--trials", type=int, default=4)
    ap.add_argument("--agent-model", default=AGENT_MODEL_DEFAULT)
    ap.add_argument("--user-model", default=USER_MODEL_DEFAULT)
    ap.add_argument("--max-concurrency", type=int, default=5)
    ap.add_argument("--max-steps", type=int, default=100)
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--seed", type=int, default=300)
    ap.add_argument("--task-ids", default=None,
                    help="optional comma-separated task id filter")
    args = ap.parse_args()

    zai_key = os.environ.get("ZAI_CODING_PLAN_KEY")
    nim_key = os.environ.get("NVIDIA_API_KEY")
    if not zai_key:
        print("FATAL: ZAI_CODING_PLAN_KEY not set", file=sys.stderr)
        return 2
    if not nim_key:
        print("FATAL: NVIDIA_API_KEY not set", file=sys.stderr)
        return 2

    RESULTS_DIR.mkdir(exist_ok=True)

    # Register the custom domain (poc/), then import the batch runner.
    from load_poc import register as register_ecommerce

    register_ecommerce()

    from load_ecommerce2 import register as register_ecommerce2

    register_ecommerce2()
    install_usage_wrapper()

    # Keep the NL-assertion judge on the original glm-5.3-flash endpoint for
    # parity with the original sweep (neither ecommerce2 nor airline uses NL
    # assertions, but the redirect is kept so the harness state matches).
    import tau2.evaluator.evaluator_nl_assertions as nle

    nle.DEFAULT_LLM_NL_ASSERTIONS = args.user_model
    nle.DEFAULT_LLM_NL_ASSERTIONS_ARGS = {
        "api_base": ZAI_BASE,
        "api_key": zai_key,
        "temperature": 0.0,
        "response_format": {"type": "json_object"},
        "num_retries": 8,
        "retry_after": 15,
    }

    from tau2.data_model.simulation import TextRunConfig
    from tau2.registry import registry
    from tau2.runner.batch import run_tasks

    domains = [d.strip() for d in args.domains.split(",") if d.strip()]

    # ONLY the agent side moves to NIM; the user side is byte-identical to
    # the original sweep's llm_args. NOTE: no `retry_after` on the agent side
    # -- NIM validates the request body strictly and rejects that kwarg with
    # a 400 ('Unsupported parameter(s): retry_after', observed in the first
    # smoke). 429 patience is handled by the completion wrapper above.
    llm_args_agent = {
        "api_base": NIM_BASE,
        "api_key": nim_key,
        "num_retries": 3,
    }
    llm_args_user = {
        "api_base": ZAI_BASE,
        "api_key": zai_key,
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

    (RESULTS_DIR / "pilot_status.json").write_text(json.dumps(status, indent=2))
    print("PILOT STATUS:", json.dumps(status, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
