"""Offline verifier for the (grown) `ecommerce2` team e-commerce domain.

Registers the lane-dir domain with the tau2-bench registry at runtime (the
cloned repo is NOT modified), then proves the harness loads it:

  1. registry sees domain 'ecommerce2' + task set 'ecommerce2'
  2. tasks.json parses into the harness Task schema (Task.model_validate)
     and the domain has grown to >=10 tasks covering all four rule families
     (returns, coupons, VAT, shipping), every task with a user persona
  3. the mandatory 'base' split resolves with every task id
  4. Environment builds; LLM tool schemas build
  5. Paper-style solvability check per task (paper_text.txt:338-342 method):
     the harness evaluators score the reference trajectory 1.0 on EVERY
     declared basis (DB via EnvironmentEvaluator, COMMUNICATE via
     CommunicateEvaluator substring match, ACTION via ActionEvaluator), and
     score the empty trajectory 0.0 overall. For positive (write) tasks the
     empty trajectory must also fail the DB basis; for decline tasks the DB
     target equals the untouched state by construction, so only the OVERALL
     product must be 0 (the communicate/action half fails).

Run with the repo venv from the lane root:
    repo/.venv/Scripts/python.exe poc/load_ecommerce2.py
"""

import sys
from pathlib import Path

POC_DIR = Path(__file__).parent
REPO_DIR = POC_DIR.parent / "repo"
sys.path.insert(0, str(POC_DIR))

from tau2.data_model.message import AssistantMessage, ToolCall  # noqa: E402
from tau2.evaluator.evaluator_action import ActionEvaluator  # noqa: E402
from tau2.evaluator.evaluator_communicate import CommunicateEvaluator  # noqa: E402
from tau2.evaluator.evaluator_env import EnvironmentEvaluator  # noqa: E402
from tau2.registry import registry  # noqa: E402

from ecommerce2.environment import (  # noqa: E402
    DOMAIN_NAME,
    get_environment,
    get_tasks,
    get_tasks_split,
)

# Tasks whose reference solution performs a store write: the untouched DB
# must NOT already satisfy them (generator invariant). Decline tasks are
# absent: their DB target IS the untouched state, by design.
WRITE_TOOL_TASKS = {
    "apply_coupon_to_order",
    "issue_invoice_with_vat",
    "return_order_items",
    "refund_lost_package",
    "change_shipping_address",
    "upgrade_shipping_method",
    "cancel_order",
}

RULE_FAMILY_BY_PREFIX = {
    "coupon": "coupons",
    "vat": "vat",
    "return": "returns",
    "shipping": "shipping",
    "cancel": "shipping",
    "lost": "returns",
}


def register() -> None:
    if DOMAIN_NAME in registry.get_domains():
        return
    registry.register_domain(get_environment, DOMAIN_NAME)
    registry.register_tasks(get_tasks, DOMAIN_NAME, get_task_splits=get_tasks_split)


def reference_trajectory(task) -> list:
    """Replay the reference actions on a fresh env, recording the messages,
    then append a reference assistant message stating every communicate_info
    fragment verbatim (CommunicateEvaluator is a substring matcher)."""
    env = get_environment()
    env.set_state(
        initialization_data=(
            task.initial_state.initialization_data if task.initial_state else None
        ),
        initialization_actions=(
            task.initial_state.initialization_actions
            if task.initial_state
            else None
        ),
        message_history=[],
    )
    messages: list = []
    for idx, action in enumerate(task.evaluation_criteria.actions):
        tc = ToolCall(
            id=f"call_{idx}",
            name=action.name,
            arguments=action.arguments,
            requestor=action.requestor,
        )
        tm = env.get_response(tc)
        if tm.error:
            raise RuntimeError(
                f"Reference action failed: {action.name}({action.arguments}) -> {tm.content}"
            )
        messages.append(AssistantMessage(role="assistant", tool_calls=[tc]))
        messages.append(tm)
    comm = task.evaluation_criteria.communicate_info
    if comm:
        messages.append(AssistantMessage(role="assistant", content=" ".join(comm)))
    return messages


def main() -> int:
    register()
    passed = 0

    # 1. Registry sees the domain
    assert DOMAIN_NAME in registry.get_domains(), "domain not registered"
    assert DOMAIN_NAME in registry.get_task_sets(), "task set not registered"
    print(f"PASS registry lists domain '{DOMAIN_NAME}' and task set '{DOMAIN_NAME}'")
    passed += 1

    # 2. Harness Task schema loads the tasks; grown domain invariants
    tasks = registry.get_tasks_loader(DOMAIN_NAME)()
    ids = [t.id for t in tasks]
    assert len(tasks) >= 10, f"full domain needs >=10 tasks, got {len(tasks)}: {ids}"
    families = {RULE_FAMILY_BY_PREFIX[t.id.split("_task")[0]] for t in tasks}
    assert families == {"coupons", "vat", "returns", "shipping"}, families
    for t in tasks:
        persona = t.user_scenario.persona if t.user_scenario else None
        instr = t.user_scenario.instructions if t.user_scenario else None
        assert persona, f"{t.id}: missing user persona"
        assert instr and getattr(instr, "reason_for_call", None), f"{t.id}: missing instructions"
    print(
        f"PASS harness loaded {len(tasks)} tasks via Task.model_validate across "
        f"rule families {sorted(families)}; every task has a user persona: {ids}"
    )
    passed += 1

    # 3. Mandatory 'base' split resolves with all ids
    splits = registry.get_task_splits_loader(DOMAIN_NAME)()
    base_tasks = registry.get_tasks_loader(DOMAIN_NAME)("base")
    base_ids = [t.id for t in base_tasks]
    assert "base" in splits and set(base_ids) == set(ids), (splits, base_ids)
    print(f"PASS task splits={list(splits.keys())}; 'base' resolves all {len(base_ids)} ids")
    passed += 1

    # 4. Environment + LLM tool schemas build
    env0 = get_environment()
    agent_tools = env0.get_tools()
    assert len(agent_tools) >= 8, f"expected >=8 agent tools, got {len(agent_tools)}"
    print(
        f"PASS environment builds; {len(agent_tools)} LLM tool schemas: "
        f"{sorted(t.name for t in agent_tools)}"
    )
    passed += 1

    # 5. Per-task solvability in both directions + reward-basis scoring
    env_ctor = registry.get_env_constructor(DOMAIN_NAME)
    for task in tasks:
        traj = reference_trajectory(task)
        env_reward = EnvironmentEvaluator.calculate_reward(env_ctor, task, traj)
        comm_reward = CommunicateEvaluator.calculate_reward(task, traj)
        act_reward = ActionEvaluator.calculate_reward(task, traj, None)
        basis = {b.value for b in task.evaluation_criteria.reward_basis}
        overall = 1.0
        if "DB" in basis:
            assert env_reward.reward == 1.0, (
                f"{task.id}: DB reward={env_reward.reward} "
                f"breakdown={env_reward.reward_breakdown}"
            )
            overall *= env_reward.reward
        if "COMMUNICATE" in basis:
            assert comm_reward.reward == 1.0, (
                f"{task.id}: communicate reward={comm_reward.reward} "
                f"({[c.info for c in comm_reward.communicate_checks if not c.met]})"
            )
            overall *= comm_reward.reward
        if "ACTION" in basis:
            assert act_reward.reward == 1.0, f"{task.id}: action reward={act_reward.reward}"
            overall *= act_reward.reward
        assert overall == 1.0
        is_write_task = any(
            a.name in WRITE_TOOL_TASKS for a in (task.evaluation_criteria.actions or [])
        )
        print(
            f"PASS [{task.id}] reference trajectory scores 1.0 on declared basis "
            f"{sorted(basis)} (env={env_reward.reward} comm={comm_reward.reward} "
            f"act={act_reward.reward}; {'write' if is_write_task else 'decline'} task)"
        )

        # not-solved-before-solution: empty trajectory must score 0 overall;
        # for write tasks the DB basis alone must be 0 too.
        empty_env = EnvironmentEvaluator.calculate_reward(env_ctor, task, [])
        empty_comm = CommunicateEvaluator.calculate_reward(task, [])
        empty_act = ActionEvaluator.calculate_reward(task, [], None)
        empty_overall = 1.0
        if "DB" in basis:
            empty_overall *= empty_env.reward
        if "COMMUNICATE" in basis:
            empty_overall *= empty_comm.reward
        if "ACTION" in basis:
            empty_overall *= empty_act.reward
        if is_write_task:
            assert empty_env.reward == 0.0, (
                f"{task.id}: empty trajectory DB reward={empty_env.reward} "
                "(task solved before solution — generator invariant violated)"
            )
        assert empty_overall == 0.0, f"{task.id}: empty trajectory overall={empty_overall}"
        print(
            f"PASS [{task.id}] empty trajectory scores 0.0 overall "
            f"(DB={empty_env.reward}, comm={empty_comm.reward}) — not trivially solved"
        )
        passed += 2

    print(f"\nALL {passed} CHECKS PASSED for grown domain '{DOMAIN_NAME}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
