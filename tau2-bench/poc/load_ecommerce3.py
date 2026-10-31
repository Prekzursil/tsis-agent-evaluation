"""PROOF-OF-CONTRIBUTION loader + offline validation for the GROWN
`ecommerce3` domain (full-scale session 5, 2026-10-24).

Grows the session-4 2-task POC into the complete 14-task team e-commerce
support domain (rule set ported from the lane's validated v1.0.1
`ecommerce2` domain; policy re-anchored with today's date — the Finding-3
authoring fix from RESULTS.md). Registers the domain into tau2's registry
using the documented contract (register_domain + register_tasks) and proves,
fully offline (no LLM calls):

  1. the 14 tasks load through registry.get_tasks_loader('ecommerce3')('base')
     and the 'base' split covers every id
  2. a fresh Environment builds; all 11 agent tools are exposed
  3. every task's reference `actions` gold-replay mutates the DB cleanly
  4. the harness's own EnvironmentEvaluator scores the reference trajectory
     DB=1.0, and the empty trajectory scores 0.0 (not trivially solvable)
  5. tasks with COMMUNICATE in the basis pass CommunicateEvaluator on the
     reference message (substring scorer)
  6. machine-checkable refusal invariants for every decline task:
     expired coupon, below-minimum coupon, out-of-window return,
     final-sale item, shipped-order address change, malformed VAT ID

Run from the lane root: repo/.venv/Scripts/python.exe poc/load_ecommerce3.py
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = (HERE.parent / "repo").resolve()
sys.path.insert(0, str(HERE.parent))  # lane root -> import poc.ecommerce3

from tau2.data_model.message import AssistantMessage, ToolCall  # noqa: E402
from tau2.data_model.run_config import CommunicateScoring  # noqa: E402
from tau2.data_model.semantic_communication import CommunicateScorer  # noqa: E402
from tau2.data_model.tasks import RewardType  # noqa: E402
from tau2.evaluator.evaluator_communicate import CommunicateEvaluator  # noqa: E402
from tau2.evaluator.evaluator_env import EnvironmentEvaluator  # noqa: E402
from tau2.registry import registry  # noqa: E402

from poc.ecommerce3.environment import (  # noqa: E402
    get_environment,
    get_task_split,
    get_tasks,
)

DOMAIN_NAME = "ecommerce3"
SUBSTRING_SCORING = CommunicateScoring(scorer=CommunicateScorer.SUBSTRING)

EXPECTED_TASKS = {
    "coupon_task_1", "coupon_task_2", "coupon_task_3",
    "return_task_1", "return_task_2", "return_task_3",
    "vat_task_1", "vat_task_2", "vat_task_3",
    "shipping_task_1", "shipping_task_2", "shipping_task_3",
    "cancel_task_1", "lost_task_1",
}
FAMILY_BY_PREFIX = {
    "coupon": "coupons", "vat": "vat", "return": "returns",
    "shipping": "shipping", "cancel": "shipping", "lost": "returns",
}
EXPECTED_TOOLS = {
    "find_user_by_email", "get_customer", "get_order_details",
    "get_coupon_details", "apply_coupon_to_order", "issue_invoice_with_vat",
    "return_order_items", "refund_lost_package", "change_shipping_address",
    "upgrade_shipping_method", "cancel_order",
}


def register() -> str:
    """The documented 3-line registration contract for a custom domain."""
    registry.register_domain(get_environment, DOMAIN_NAME)
    registry.register_tasks(get_tasks, DOMAIN_NAME, get_task_split)
    return DOMAIN_NAME


def reference_trajectory(task) -> list:
    """Actions + one assistant message stating every communicate_info fact."""
    env = get_environment()
    messages = []
    for action in task.evaluation_criteria.actions:
        tc = ToolCall(
            id=action.action_id,
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
    checks = []

    def check(name, ok, detail=""):
        checks.append(ok)
        print(f"{'PASS' if ok else 'FAIL'} {name}{(' — ' + detail) if detail else ''}")

    register()
    check(
        "domain registered in tau2.registry",
        DOMAIN_NAME in registry.get_domains()
        and DOMAIN_NAME in registry.get_task_sets(),
        "registry.get_domains()/get_task_sets() contain 'ecommerce3'",
    )

    tasks = registry.get_tasks_loader(DOMAIN_NAME)("base")
    ids = {t.id for t in tasks}
    check(
        "14 grown tasks load via registry loader (base split, >=10 mandated)",
        len(tasks) >= 10 and ids == EXPECTED_TASKS,
        f"loaded {len(tasks)} tasks: {sorted(ids)}",
    )

    families = {FAMILY_BY_PREFIX[t.id.split("_task")[0]] for t in tasks}
    personas_ok = all(
        t.user_scenario.persona and t.user_scenario.instructions.reason_for_call
        for t in tasks
    )
    check(
        "all four rule families covered; every task has persona + instructions",
        families == {"coupons", "vat", "returns", "shipping"} and personas_ok,
        f"families={sorted(families)}; personas+reason_for_call on all {len(tasks)} tasks",
    )

    splits = registry.get_task_splits_loader(DOMAIN_NAME)()
    check(
        "'base' split resolves and covers every task id",
        set(splits.get("base", [])) == ids,
        f"splits={ {k: len(v) for k, v in splits.items()} }",
    )

    env = registry.get_env_constructor(DOMAIN_NAME)()
    tool_names = {t.name for t in env.get_tools()}
    check(
        "environment builds via registry constructor; all 11 agent tools exposed",
        tool_names == EXPECTED_TOOLS,
        f"tools: {sorted(tool_names)}",
    )

    READ_TOOLS = {"find_user_by_email", "get_customer", "get_order_details", "get_coupon_details"}
    for task in tasks:
        # (a) gold replay runs clean; write tasks mutate the DB, decline
        #     tasks (read-only reference trajectory) must leave it unchanged
        is_decline = all(
            a.name in READ_TOOLS for a in (task.evaluation_criteria.actions or [])
        )
        gold_env = registry.get_env_constructor(DOMAIN_NAME)()
        before = gold_env.get_db_hash()
        errors = []
        for action in task.evaluation_criteria.actions or []:
            try:
                gold_env.make_tool_call(
                    tool_name=action.name,
                    requestor=action.requestor,
                    **action.arguments,
                )
            except Exception as e:
                errors.append(f"{action.name}: {e}")
        after = gold_env.get_db_hash()
        ok = not errors and (before != after if not is_decline else before == after)
        check(
            f"gold replay {'leaves DB unchanged (decline)' if is_decline else 'mutates DB'} [{task.id}]",
            ok,
            "; ".join(errors) or f"db hash {before[:8]}.. -> {after[:8]}..",
        )

        # (b) harness evaluator: reference trajectory scores 1.0 on declared basis
        trajectory = reference_trajectory(task)
        reward_info = EnvironmentEvaluator.calculate_reward(
            environment_constructor=get_environment,
            task=task,
            full_trajectory=trajectory,
        )
        basis = {r.value for r in task.evaluation_criteria.reward_basis}
        db_ok = reward_info.db_check is not None and reward_info.db_check.db_match
        check(
            f"harness EnvironmentEvaluator DB=1.0 on reference trajectory [{task.id}]",
            db_ok and reward_info.db_check.db_reward == 1.0,
            f"db_match={db_ok}",
        )

        if "COMMUNICATE" in basis:
            comm = CommunicateEvaluator.calculate_reward(
                task=task,
                full_trajectory=[m for m in trajectory if isinstance(m, AssistantMessage)],
                scoring=SUBSTRING_SCORING,
            )
            check(
                f"CommunicateEvaluator 1.0 on reference message (substring) [{task.id}]",
                comm.reward == 1.0,
                f"communicate_reward={comm.reward} unmet={[c.info for c in (comm.communicate_checks or []) if not c.met]}",
            )

        # (c) not trivially solvable: on the DECLARED basis the empty
        #     trajectory must score < 1.0 (DB 0 for write tasks; COMMUNICATE 0
        #     for decline tasks whose only gate is the required explanation)
        empty_db = EnvironmentEvaluator.calculate_reward(
            environment_constructor=get_environment,
            task=task,
            full_trajectory=[],
        ).reward
        empty_comm = 1.0
        if "COMMUNICATE" in basis:
            empty_comm = CommunicateEvaluator.calculate_reward(
                task=task, full_trajectory=[], scoring=SUBSTRING_SCORING
            ).reward
        check(
            f"empty trajectory scores <1.0 on declared basis (not trivially solvable) [{task.id}]",
            empty_db * empty_comm < 1.0,
            f"empty db={empty_db} comm={empty_comm} product={round(empty_db * empty_comm, 3)}",
        )

    # (d) machine-checkable refusal invariants for the decline tasks
    def must_raise(desc, fn):
        try:
            fn()
            check(f"refusal invariant: {desc}", False, "tool did NOT raise")
        except Exception as e:
            check(f"refusal invariant: {desc}", True, str(e)[:110])

    e2 = registry.get_env_constructor(DOMAIN_NAME)()
    must_raise(
        "expired coupon SAVE20 rejected on #ORD-4004",
        lambda: e2.make_tool_call(
            tool_name="apply_coupon_to_order", requestor="assistant",
            order_id="#ORD-4004", coupon_code="SAVE20",
        ),
    )
    e3 = registry.get_env_constructor(DOMAIN_NAME)()
    must_raise(
        "below-minimum coupon SPRING5 rejected on #ORD-5010 (subtotal 15.90 < 20)",
        lambda: e3.make_tool_call(
            tool_name="apply_coupon_to_order", requestor="assistant",
            order_id="#ORD-5010", coupon_code="SPRING5",
        ),
    )
    e4 = registry.get_env_constructor(DOMAIN_NAME)()
    must_raise(
        "out-of-window return rejected on #ORD-6006 (delivered 2026-08-30)",
        lambda: e4.make_tool_call(
            tool_name="return_order_items", requestor="assistant",
            order_id="#ORD-6006", item_ids=["it_6006_1"],
        ),
    )
    e5 = registry.get_env_constructor(DOMAIN_NAME)()
    must_raise(
        "final-sale item rejected on #ORD-5005 (it_5005_2)",
        lambda: e5.make_tool_call(
            tool_name="return_order_items", requestor="assistant",
            order_id="#ORD-5005", item_ids=["it_5005_2"],
        ),
    )
    e6 = registry.get_env_constructor(DOMAIN_NAME)()
    must_raise(
        "address change rejected on shipped #ORD-11011",
        lambda: e6.make_tool_call(
            tool_name="change_shipping_address", requestor="assistant",
            order_id="#ORD-11011", street="Neue Str. 1", city="Berlin",
            postal_code="10115", country="DE",
        ),
    )
    e7 = registry.get_env_constructor(DOMAIN_NAME)()
    must_raise(
        "malformed VAT ID rejected (DE12)",
        lambda: e7.make_tool_call(
            tool_name="issue_invoice_with_vat", requestor="assistant",
            order_id="#ORD-3003", vat_id="DE12",
        ),
    )
    # And the state stays clean after the refused writes:
    check(
        "DB unchanged by refused writes (no coupon on #ORD-4004/#ORD-5010; #ORD-3003 invoice untouched)",
        e2.tools.db.orders["#ORD-4004"].coupon_code is None
        and e3.tools.db.orders["#ORD-5010"].coupon_code is None
        and e7.tools.db.orders["#ORD-3003"].invoice.vat_id is None
        and e7.tools.db.orders["#ORD-3003"].invoice.vat_rate == 0.19,
        "refusals left no partial state",
    )

    ok = all(checks)
    print(
        f"\n{'ALL PASS' if ok else 'FAILURES PRESENT'} "
        f"({sum(checks)}/{len(checks)} checks)"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
