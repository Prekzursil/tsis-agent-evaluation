# Draft issue for sierra-research/tau2-bench (ready to file on owner approval)

**Title:** docs: `evaluation.md` reward_basis claims contradict the shipped v1.0.1 task data (retail/telecom), and ACTION *is* used in telecom

**Body:**

While reproducing τ²-bench evaluations (v1.0.1, commit 96a3ef9) we found two places where the docs contradict the data shipped in the same tree. Both are still present on `main` as of 2026-10-18.

## 1. `docs/evaluation.md` — "The default `reward_basis` for the airline, retail, and telecom domains is `["DB", "COMMUNICATE"]`"

This is true only as the pydantic schema default (`src/tau2/data_model/tasks.py:435`, applied when `reward_basis` is omitted) and for airline's data. The shipped task files carry explicit values that diverge from it:

| domain | tasks | actual `evaluation_criteria.reward_basis` distribution |
|---|---|---|
| airline | 50 | 50 × `[DB, COMMUNICATE]` |
| retail | 114 | 112 × `[DB, NL_ASSERTION]`, 2 × `[DB]` — 0 use `COMMUNICATE` |
| telecom | 2285 | 2253 × `[ENV_ASSERTION]`, 32 × `[ENV_ASSERTION, ACTION]` — 0 use `COMMUNICATE` |

(Counts from `data/tau2/domains/{airline,retail,telecom}/tasks.json`.)

Suggested fix: either state that the sentence describes the schema default only, or list the per-domain actual bases.

## 2. `src/tau2/data_model/tasks.py:257-258` (RewardType.ACTION docstring) — "not used in airline/retail/telecom"

32 telecom tasks include `ACTION` in `reward_basis` (all `[ENV_ASSERTION, ACTION]`), e.g. `[service_issue]lock_sim_card_pin[PERSONA:Hard]`, `[service_issue]contract_end_suspension[PERSONA:Hard]`. 20 of the 32 are in the 114-task `base` evaluation split, so even "telecom uses only env assertions" holds for 94/114 base tasks, not all.

Reproduction:

```python
import json, collections
for dom in ["airline", "retail", "telecom"]:
    tasks = json.load(open(f"data/tau2/domains/{dom}/tasks.json"))
    print(dom, len(tasks), collections.Counter(
        tuple(t["evaluation_criteria"].get("reward_basis", [])) for t in tasks))
```

**Value:** anyone implementing evaluation, computing cross-domain comparability, or asserting on reward components from the docs alone will get retail/telecom wrong.

---

*Filing notes (not part of the issue body):* adjacent-but-different open issues checked, no duplicate: #81 (2025-11) is about the schema default not including ACTION; #599 is banking_knowledge data disagreements. Verify once more against HEAD before filing (checked 2026-10-18: both quoted lines present on main).
