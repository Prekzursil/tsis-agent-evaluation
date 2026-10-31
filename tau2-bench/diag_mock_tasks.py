"""Diagnose the mock 'Tasks were modified' resume failure (read-only)."""
import json
import sys
from pathlib import Path

LANE = Path(__file__).resolve().parent
sys.path.insert(0, str(LANE / "repo" / "src"))

from tau2.registry import registry  # noqa: E402
from tau2.utils.pydantic_utils import get_pydantic_hash  # noqa: E402
from tau2.data_model.tasks import Task  # noqa: E402

t1 = registry.get_tasks_loader("mock")()
t2 = registry.get_tasks_loader("mock")()
fresh_ids = [t.id for t in t1]
print("same ids across loads:", fresh_ids == [t.id for t in t2])

d = [a.id for a, b in zip(t1, t2) if get_pydantic_hash(a) != get_pydantic_hash(b)]
print("tasks differing across two fresh loads:", d)

ck = json.loads((LANE / "results_v2_grok" / "mock" / "results.json").read_text())
ck_tasks = {t["id"]: t for t in ck["tasks"]}
print("checkpoint task ids:", sorted(ck_tasks))
mism = []
for t in t1:
    if t.id not in ck_tasks:
        continue
    prev = Task.model_validate(ck_tasks[t.id])
    if get_pydantic_hash(prev) != get_pydantic_hash(t):
        mism.append(t.id)
print("checkpoint tasks differing from fresh load:", mism)

# show the first differing field for one mismatch
if mism:
    tid = mism[0]
    a = json.dumps(ck_tasks[tid], sort_keys=True, indent=0).splitlines()
    b = json.dumps(
        next(t for t in t1 if t.id == tid).model_dump(mode="json"),
        sort_keys=True,
        indent=0,
    ).splitlines()
    import difflib

    diff = [l for l in difflib.unified_diff(a, b, lineterm="", n=1)][:40]
    print(f"--- first diff for {tid}:")
    for l in diff:
        print(l[:160])
