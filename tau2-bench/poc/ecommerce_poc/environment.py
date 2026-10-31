"""Environment + task loading for the ecommerce_poc domain.

Follows the domain contract documented in the repo's
``src/tau2/domains/README.md`` (get_environment / get_tasks / get_tasks_split),
but lives entirely outside the cloned repo and is registered at runtime by
``poc/load_poc.py`` instead of editing the repo's ``registry.py``.
"""

from pathlib import Path
from typing import Optional

from tau2.data_model.tasks import Task
from tau2.environment.environment import Environment
from tau2.utils import load_file

from .data_model import EcommerceDB
from .tools import EcommerceTools
from .user_data_model import ShopperAppDB
from .user_tools import ShopperAppTools

DATA_DIR = Path(__file__).parent / "data"
DB_PATH = DATA_DIR / "db.json"
USER_DB_PATH = DATA_DIR / "user_db.json"
POLICY_PATH = DATA_DIR / "policy.md"
TASKS_PATH = DATA_DIR / "tasks.json"

DOMAIN_NAME = "ecommerce_poc"


def get_environment(
    db: Optional[EcommerceDB] = None,
    user_db: Optional[ShopperAppDB] = None,
    solo_mode: bool = False,
) -> Environment:
    if db is None:
        db = EcommerceDB.load(DB_PATH)
    tools = EcommerceTools(db)
    if user_db is None:
        user_db = ShopperAppDB.load(USER_DB_PATH)
    user_tools = ShopperAppTools(user_db)
    with open(POLICY_PATH, "r", encoding="utf-8") as fp:
        policy = fp.read()
    env = Environment(
        domain_name=DOMAIN_NAME,
        policy=policy,
        tools=tools,
        user_tools=user_tools,
    )
    if solo_mode:
        env.set_solo_mode(True)
    return env


def get_tasks(task_split_name: Optional[str] = None) -> list[Task]:
    tasks = load_file(TASKS_PATH)
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


def get_tasks_split() -> dict[str, list[str]]:
    split_file = DATA_DIR / f"split_{Path(TASKS_PATH).stem}.json"
    return load_file(split_file)
