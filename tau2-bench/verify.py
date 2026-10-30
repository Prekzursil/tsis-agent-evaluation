#!/usr/bin/env python
"""Offline, deterministic verification for the tau2-bench lane (session 4, 2026-10-24).

Checks (no network, no LLM calls, no randomness):
  1. repo cloned          - tss/tsis-deepdive/tau2-bench/repo is a git checkout
                            of sierra-research/tau2-bench at the session-4 commit.
  2. venv deps import     - repo/.venv python imports tau2 (+ version pin 2.0.0),
                            litellm and pydantic.
  3. task format parses   - the repo's own shipped domain task files are valid JSON
                            and validate against the harness Task schema.
  4. POC tasks validate   - poc/ecommerce3's 2 native-format tasks validate against
                            the harness Task schema, load via a registry-registered
                            loader, gold-replay their reference actions, and the
                            harness's own EnvironmentEvaluator scores the reference
                            trajectory reward=1.0 (DB match). Registered under a
                            temp domain name so repeat runs stay side-effect-free.

Exit 0 iff every check prints PASS. Receipts for this file's claims live in SMOKE.md.
Prior sessions' gates are preserved as verify_prior_session.py (v1.0.1 lane state)
and verify_prior_session_ecommerce2.py (ecommerce2 POC).
"""

import subprocess
import sys
from pathlib import Path

LANE = Path(__file__).resolve().parent
REPO = LANE / "repo"
VENV_PY = REPO / ".venv" / "Scripts" / "python.exe"
EXPECTED_REMOTE = "https://github.com/sierra-research/tau2-bench"
EXPECTED_COMMIT_PREFIX = "cc1df47"  # v2.0.0 main @ 2026-10-22 (session-4 shallow clone)

results = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'} {name}{(' — ' + detail) if detail else ''}")


def git(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, shell=False
    )


def check_repo_cloned() -> None:
    ok_dir = REPO.is_dir() and (REPO / ".git").exists() and (REPO / "pyproject.toml").exists()
    check("repo directory is a git clone with pyproject.toml", ok_dir, str(REPO))
    if not ok_dir:
        return
    proc = git(["remote", "get-url", "origin"])
    remote_ok = proc.returncode == 0 and EXPECTED_REMOTE in proc.stdout
    check("clone origin is the official repo", remote_ok,
          (proc.stdout or proc.stderr).strip() or EXPECTED_REMOTE)

    head = git(["rev-parse", "HEAD"])
    commit = head.stdout.strip()
    check("cloned HEAD matches session-4 commit", head.returncode == 0 and commit.startswith(EXPECTED_COMMIT_PREFIX), commit[:12])

    dirty = git(["status", "--porcelain"])
    outside_sims = [l for l in dirty.stdout.splitlines() if "data/simulations" not in l]
    check("clone working tree clean (simulation outputs ignored)", dirty.returncode == 0 and not outside_sims,
          f"{len(outside_sims)} changed path(s) outside data/simulations")


INNER = r"""
import json, sys
from pathlib import Path

LANE = Path(r"%LANE%")
REPO = LANE / "repo"
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(LANE))

ok_all = True
def check(name, ok, detail=""):
    global ok_all
    ok_all = ok_all and ok
    print(f"{'PASS' if ok else 'FAIL'} {name}{(' — ' + detail) if detail else ''}")

# ---- 2. venv deps import ---------------------------------------------------
from importlib.metadata import version
import tau2, litellm, pydantic  # noqa: E402,F401
check("venv python imports tau2 package", tau2.__file__ is not None,
      str(tau2.__file__).replace(str(REPO), 'repo'))
check("venv deps import: litellm + pydantic", True,
      f"litellm {version('litellm')}, pydantic {pydantic.VERSION}")
check("installed tau2-bench version is 2.0.0", version('tau2') == '2.0.0',
      f"tau2-bench {version('tau2')}")

# ---- 3. shipped task files parse + validate against harness schema ---------
from tau2.data_model.tasks import Task
shipped = {"airline": 50, "retail": 114, "telecom": 2285}  # telecom: full generated set; base split = 114
for dom, expected_n in shipped.items():
    path = REPO / "data" / "tau2" / "domains" / dom / "tasks.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    tasks = [Task.model_validate(t) for t in raw]
    check(f"harness Task schema validates shipped {dom}/tasks.json",
          len(tasks) == expected_n, f"{len(tasks)}/{expected_n} tasks parse+validate")

# ---- 4. POC tasks: schema + registry load + gold replay + evaluator --------
from tau2.evaluator.evaluator_env import EnvironmentEvaluator
from tau2.registry import registry
from poc.ecommerce3 import environment as ecom_env

poc_path = LANE / "poc" / "ecommerce3" / "data" / "tasks.json"
raw = json.loads(poc_path.read_text(encoding="utf-8"))
poc_tasks = [Task.model_validate(t) for t in raw]
check("POC tasks.json parses + validates against harness Task schema",
      {t.id for t in poc_tasks} == {"return_coupon_001", "vat_invoice_002"},
      f"{len(poc_tasks)} tasks: {[t.id for t in poc_tasks]}")

name = "ecommerce3_verify"
if name in registry.get_domains():
    check("POC domain registration name free", False, f"{name} already registered")
else:
    registry.register_domain(ecom_env.get_environment, name)
    registry.register_tasks(ecom_env.get_tasks, name, ecom_env.get_task_split)
    check("POC domain registers via documented registry contract",
          name in registry.get_domains() and name in registry.get_task_sets())
    loaded = registry.get_tasks_loader(name)("base")
    check("registry loader returns both POC tasks (base split)", len(loaded) == 2,
          f"{[t.id for t in loaded]}")

from tau2.data_model.message import AssistantMessage, ToolCall

for task in poc_tasks:
    gold = ecom_env.get_environment()
    before = gold.get_db_hash()
    for action in task.evaluation_criteria.actions:
        gold.make_tool_call(tool_name=action.name, requestor=action.requestor,
                            **action.arguments)
    check(f"POC reference actions gold-replay mutates DB [{task.id}]",
          before != gold.get_db_hash())

    scratch = ecom_env.get_environment()
    trajectory = []
    for a in task.evaluation_criteria.actions:
        tc = ToolCall(id=a.action_id, name=a.name, arguments=a.arguments,
                      requestor=a.requestor)
        resp = scratch.get_response(tc)
        assert not resp.error, f"{a.name} errored: {resp.content}"
        trajectory.append(AssistantMessage(role="assistant", content="", tool_calls=[tc]))
        trajectory.append(resp)
    reward_info = EnvironmentEvaluator.calculate_reward(
        environment_constructor=ecom_env.get_environment,
        task=task, full_trajectory=trajectory,
    )
    check(f"harness EnvironmentEvaluator scores POC reference trajectory reward=1.0 [{task.id}]",
          reward_info.reward == 1.0 and reward_info.db_check is not None and reward_info.db_check.db_match,
          f"reward={reward_info.reward}")

# offline policy-refusal invariant (decidable from DB state alone, no LLM)
env2 = ecom_env.get_environment()
try:
    env2.make_tool_call(tool_name="apply_coupon_to_order", requestor="assistant",
                        order_id="#E2002", coupon_id="SAVE10")
    refused = False
except Exception:
    refused = True
db = env2.tools.db
check("POC policy refusal machine-checkable (expired coupon rejected, no state change)",
      refused and db.coupons["SAVE10"].status == "expired"
      and db.orders["#E2002"].coupon_id_applied is None)

sys.exit(0 if ok_all else 1)
""".replace("%LANE%", str(LANE).replace("\\", "\\\\"))


def main() -> int:
    check_repo_cloned()

    venv_exists = VENV_PY.is_file()
    check("venv python exists (repo/.venv/Scripts/python.exe)", venv_exists, str(VENV_PY))
    if not venv_exists:
        print("\nCannot continue without the venv.")
        return 1

    proc = subprocess.run(
        [str(VENV_PY), "-c", INNER],
        capture_output=True, text=True, shell=False, cwd=str(LANE),
    )
    for line in proc.stdout.splitlines():
        if line.startswith(("PASS", "FAIL")):
            results.append(line.startswith("PASS"))
        if line:
            print(line)
    if proc.returncode != 0:
        print(proc.stderr[-2000:])
        check("harness-side verification subprocess exit code", False, f"rc={proc.returncode}")

    print(f"\n{'ALL PASS' if results and all(results) else 'FAILURES PRESENT'} ({sum(results)}/{len(results)} checks)")
    return 0 if results and all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
