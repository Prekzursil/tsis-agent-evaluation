"""Environment + task loading for the ecommerce3 POC domain.

Mirrors src/tau2/domains/mock/environment.py and
src/tau2/domains/retail/environment.py (tau2-bench v2.0.0 @ cc1df47).
"""

from pathlib import Path
from typing import Optional

from tau2.data_model.tasks import Task
from tau2.environment.environment import Environment
from tau2.utils import load_file

from .data_model import ECOM_DB_PATH, ECOM_POLICY_PATH, ECOM_TASK_SET_PATH, EcomDB
from .tools import EcommerceTools


def get_environment(
    db: Optional[EcomDB] = None,
    solo_mode: bool = False,
) -> Environment:
    if solo_mode:
        raise ValueError("ecommerce3 POC domain does not support solo mode")
    if db is None:
        db = EcomDB.load(str(ECOM_DB_PATH))
    else:
        db = db.model_copy(deep=True)
    tools = EcommerceTools(db)
    with open(ECOM_POLICY_PATH, "r", encoding="utf-8") as fp:
        policy = fp.read()
    return Environment(
        domain_name="ecommerce3",
        policy=policy,
        tools=tools,
    )


def get_tasks(task_split_name: Optional[str] = None) -> list[Task]:
    tasks = load_file(str(ECOM_TASK_SET_PATH))
    tasks = [Task.model_validate(task) for task in tasks]
    if task_split_name is None:
        return tasks
    task_splits = get_task_split()
    if task_split_name not in task_splits:
        raise ValueError(
            f"Invalid task split name: {task_split_name}. Valid splits are: {task_splits.keys()}"
        )
    return [task for task in tasks if task.id in task_splits[task_split_name]]


def get_task_split() -> dict[str, list[str]]:
    split_file = (
        Path(ECOM_TASK_SET_PATH).parent
        / f"split_{Path(ECOM_TASK_SET_PATH).stem}.json"
    )
    return load_file(str(split_file))
