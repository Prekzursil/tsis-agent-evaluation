"""Offline verifier for the (grown) ecommerce_poc domain.

Registers the lane-dir domain with the tau2-bench registry at runtime (the
cloned repo is NOT modified), then proves the harness loads it:

  1. registry sees domain 'ecommerce_poc' + task set 'ecommerce_poc'
  2. tasks.json parses into the harness Task schema (Task.model_validate)
  3. Environment builds; every task initial_state applies; LLM tool schemas build
  4. Paper-style solvability check (paper_text.txt:338-342 method):
     env assertions FAIL before the reference solution, PASS after
  5. The harness's own evaluators score the reference trajectory 1.0 on
     EVERY basis the task declares (DB via EnvironmentEvaluator, ENV_ASSERTION
     via EnvironmentEvaluator, COMMUNICATE via CommunicateEvaluator substring
     match against a reference assistant message, ACTION via ActionEvaluator)
     and score the empty trajectory 0.0.

Run with the repo venv:
    repo/.venv/Scripts/python.exe poc/load_poc.py
"""

import sys
from pathlib import Path

POC_DIR = Path(__file__).parent
REPO_DIR = POC_DIR.parent / "repo"
sys.path.insert(0, str(POC_DIR))

from tau2.data_model.message import (  # noqa: E402
    AssistantMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from tau2.evaluator.evaluator_action import ActionEvaluator  # noqa: E402
from tau2.evaluator.evaluator_communicate import CommunicateEvaluator  # noqa: E402
from tau2.evaluator.evaluator_env import EnvironmentEvaluator  # noqa: E402
from tau2.registry import registry  # noqa: E402

from ecommerce_poc.environment import (  # noqa: E402
    DOMAIN_NAME,
    get_environment,
    get_tasks,
    get_tasks_split,
)


def register() -> None:
    if DOMAIN_NAME in registry.get_domains():
        return
    registry.register_domain(get_environment, DOMAIN_NAME)
    registry.register_tasks(
        get_tasks, DOMAIN_NAME, get_task_splits=get_tasks_split
    )


def reference_trajectory(task) -> list:
    """Execute the reference actions on a fresh env, recording the messages,
    and append a reference assistant message that states every communicate_info
    fragment verbatim (the CommunicateEvaluator is a substring matcher)."""
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
        if tc.requestor == "assistant":
            messages.append(AssistantMessage(role="assistant", tool_calls=[tc]))
        else:
            messages.append(UserMessage(role="user", tool_calls=[tc]))
        messages.append(tm)
    comm = task.evaluation_criteria.communicate_info
    if comm:
        text = " ".join(comm)
        messages.append(AssistantMessage(role="assistant", content=text))
    return messages


def main() -> int:
    register()
    checks = 0

    # 1. Registry sees the domain
    assert DOMAIN_NAME in registry.get_domains(), "domain not registered"
    assert DOMAIN_NAME in registry.get_task_sets(), "task set not registered"
    print(f"PASS registry lists domain '{DOMAIN_NAME}' and task set '{DOMAIN_NAME}'")
    checks += 1

    # 2. Tasks parse through the harness Task schema
    tasks = registry.get_tasks_loader(DOMAIN_NAME)()
    ids = [t.id for t in tasks]
    assert len(tasks) >= 10, f"need >=10 tasks for the full domain, got {len(tasks)}"
    print(f"PASS harness loaded {len(tasks)} tasks via Task.model_validate: {ids}")
    checks += 1

    # 3. Splits resolve (base split is mandatory per domains README)
    base_tasks = registry.get_tasks_loader(DOMAIN_NAME)("base")
    base_ids = [t.id for t in base_tasks]
    assert set(base_ids) == set(ids), base_ids
    print(f"PASS task split 'base' resolves with all {len(base_ids)} ids")
    checks += 1

    # 3b. LLM-facing surfaces build (tools + user tools -> OpenAI schemas)
    env0 = get_environment()
    agent_tools = env0.get_tools()
    user_tools = env0.get_user_tools()
    assert agent_tools and user_tools
    print(
        f"PASS LLM tool surfaces build: {len(agent_tools)} agent tools, "
        f"{len(user_tools)} user tools"
    )
    checks += 1

    # 4/5. Per-task: initial_state applies, solvability both directions, and
    #      every declared reward basis scores 1.0 on the reference trajectory.
    for task in tasks:
        env_ctor = registry.get_env_constructor(DOMAIN_NAME)

        # initial_state applies cleanly
        env = env_ctor()
        env.set_state(
            initialization_data=(
                task.initial_state.initialization_data
                if task.initial_state
                else None
            ),
            initialization_actions=(
                task.initial_state.initialization_actions
                if task.initial_state
                else None
            ),
            message_history=[],
        )
        print(f"PASS [{task.id}] environment built + initial_state applied")

        # solvability: assertions must FAIL on the untouched env...
        if task.evaluation_criteria.env_assertions:
            pre = [
                env.run_env_assertion(a, raise_assertion_error=False)
                for a in task.evaluation_criteria.env_assertions
            ]
            assert not any(pre), f"{task.id}: solved before solution! {pre}"
            print(f"PASS [{task.id}] env assertions fail BEFORE solution (not trivially solved)")

        # ...and the harness evaluators give reward 1.0 to the reference
        # trajectory on every declared basis, 0.0 to doing nothing.
        traj = reference_trajectory(task)
        solved = EnvironmentEvaluator.calculate_reward(env_ctor, task, traj)
        comm_reward = CommunicateEvaluator.calculate_reward(task, traj)
        act_reward = ActionEvaluator.calculate_reward(task, traj, None)
        basis = {b.value for b in task.evaluation_criteria.reward_basis}
        overall = 1.0
        if "DB" in basis or "ENV_ASSERTION" in basis:
            assert solved.reward == 1.0, (
                f"{task.id}: env-basis reward={solved.reward} "
                f"(breakdown={solved.reward_breakdown})"
            )
            overall *= solved.reward
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
        print(
            f"PASS [{task.id}] reference trajectory scores 1.0 on basis "
            f"{sorted(basis)} (env={solved.reward} comm={comm_reward.reward} act={act_reward.reward})"
        )

        unsolved_env = EnvironmentEvaluator.calculate_reward(env_ctor, task, [])
        unsolved_comm = CommunicateEvaluator.calculate_reward(task, [])
        unsolved_act = ActionEvaluator.calculate_reward(task, [], None)
        overall_empty = 1.0
        if "DB" in basis or "ENV_ASSERTION" in basis:
            overall_empty *= unsolved_env.reward
        if "COMMUNICATE" in basis:
            overall_empty *= unsolved_comm.reward
        if "ACTION" in basis:
            overall_empty *= unsolved_act.reward
        # For positive tasks every basis should be 0; for decline tasks the
        # empty trajectory is DB-correct by construction, so only the OVERALL
        # product must be 0 (the communicate/action half fails).
        if any(
            a.name
            in {
                "return_order_items",
                "refund_lost_package",
                "apply_coupon_to_order",
                "issue_invoice_with_vat",
                "change_shipping_address",
                "upgrade_shipping_method",
            }
            for a in (task.evaluation_criteria.actions or [])
        ):
            assert unsolved_env.reward == 0.0, (
                f"{task.id}: empty traj env {unsolved_env.reward} (positive task)"
            )
        assert overall_empty == 0.0, (
            f"{task.id}: empty trajectory overall={overall_empty} "
            f"(env={unsolved_env.reward} comm={unsolved_comm.reward} act={unsolved_act.reward})"
        )
        print(
            f"PASS [{task.id}] empty trajectory overall 0.0 "
            f"(env={unsolved_env.reward} comm={unsolved_comm.reward})"
        )
        checks += 3

    print(f"\nALL {checks} DOMAIN CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
