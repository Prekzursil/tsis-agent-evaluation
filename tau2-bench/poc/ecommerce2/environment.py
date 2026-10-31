"""Environment wiring for the `ecommerce2` proof-of-contribution domain.

Follows the domain contract from src/tau2/domains/README.md: a folder with
data_model.py, tools.py, environment.py exposing get_environment(),
get_tasks() and get_tasks_split(), plus a data/ folder holding db.json,
tasks.json, split_tasks.json and policy.md. Data files resolve relative to
this file so the domain lives entirely in the lane directory — the cloned
repo is never modified. Registration happens at runtime (see
poc/load_ecommerce2.py), mirroring the 3-line registration documented in
the domains README.
"""

from pathlib import Path
from typing import Optional

from tau2.data_model.tasks import Task
from tau2.environment.environment import Environment
from tau2.utils import load_file

from .data_model import EcommerceDB
from .tools import EcommerceTools

DOMAIN_NAME = "ecommerce2"

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = str(DATA_DIR / "db.json")
TASK_SET_PATH = str(DATA_DIR / "tasks.json")
POLICY_PATH = str(DATA_DIR / "policy.md")


def get_environment(
    db: Optional[EcommerceDB] = None, solo_mode: bool = False
) -> Environment:
    if solo_mode:
        raise ValueError("ecommerce2 domain does not support solo mode")
    if db is None:
        db = EcommerceDB.load(DB_PATH)
    tools = EcommerceTools(db)
    with open(POLICY_PATH, "r", encoding="utf-8") as fp:
        policy = fp.read()
    return Environment(
        domain_name=DOMAIN_NAME,
        policy=policy,
        tools=tools,
    )


def get_tasks_split() -> dict[str, list[str]]:
    return load_file(str(DATA_DIR / "split_tasks.json"))


def get_tasks(task_split_name: Optional[str] = None) -> list[Task]:
    tasks = load_file(TASK_SET_PATH)
    tasks = [Task.model_validate(task) for task in tasks]
    if task_split_name is None:
        return tasks
    task_splits = get_tasks_split()
    if task_split_name not in task_splits:
        raise ValueError(
            f"Invalid task split name: {task_split_name}. "
            f"Valid splits are: {list(task_splits.keys())}"
        )
    return [task for task in tasks if task.id in task_splits[task_split_name]]
