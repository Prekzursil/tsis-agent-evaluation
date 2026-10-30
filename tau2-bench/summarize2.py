"""Summarize full-sweep results into results_v2/summary.json (+ printed tables).

Recomputes pass^k with the harness's own metric (tau2.metrics.agent_metrics.
get_tasks_pass_hat_k), per domain, from results/<domain>/results.json.
Usage: repo/.venv/Scripts/python.exe summarize.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

LANE = Path(__file__).resolve().parent
RESULTS = LANE / "results_v2"

sys.path.insert(0, str(LANE / "repo" / "src"))

from tau2.metrics.agent_metrics import get_tasks_pass_hat_k  # noqa: E402
from tau2.data_model.simulation import Results  # noqa: E402


def load_results(domain: str):
    p = RESULTS / domain / "results.json"
    if not p.exists():
        return None
    raw = json.loads(p.read_text())
    res = Results.model_validate(raw)
    # Repair stale info.num_trials left over when a k=4 run resumed a file
    # first created by a k=1 pilot: the harness's get_metrics_df() caps pass^k
    # at info.num_trials. The simulations themselves are authoritative (each
    # task's trial rows); raw results.json files are NOT modified.
    counts: dict[str, set] = {}
    for s in res.simulations:
        counts.setdefault(s.task_id, set()).add(s.trial)
    if counts:
        actual = min(len(v) for v in counts.values())
        if res.info.num_trials != actual:
            res.info.num_trials = actual
    return res


def summarize(domain: str) -> dict | None:
    res = load_results(domain)
    if res is None:
        return None
    sims = res.simulations
    by_task: dict[str, list[float]] = {}
    for s in sims:
        r = s.reward_info.reward if s.reward_info else 0.0
        by_task.setdefault(s.task_id, []).append(r)
    n_trials_per_task = sorted({len(v) for v in by_task.values()})
    mean_reward = sum(sum(v) for v in by_task.values()) / max(1, len(sims))
    out = {
        "domain": domain,
        "n_tasks_seen": len(by_task),
        "n_sims": len(sims),
        "trials_per_task": n_trials_per_task,
        "mean_reward": round(mean_reward, 4),
        "pass^k": {},
        "per_task": {
            t: {
                "trials": len(v),
                "successes": int(sum(v)),
                "mean": round(sum(v) / len(v), 4),
            }
            for t, v in sorted(by_task.items())
        },
        "termination_reasons": {},
    }
    for s in sims:
        tr = s.termination_reason
        out["termination_reasons"][tr] = out["termination_reasons"].get(tr, 0) + 1
    if n_trials_per_task and n_trials_per_task[0] >= 1:
        df = get_tasks_pass_hat_k(res)
        for k in range(1, (n_trials_per_task[-1] if n_trials_per_task else 1) + 1):
            col = f"pass^{k}"
            if col in df.columns:
                out["pass^k"][f"k={k}"] = round(float(df[col].mean()), 4)
    return out


def main() -> int:
    domains = sorted(
        d.name for d in RESULTS.iterdir() if (d / "results.json").exists()
    )
    summary = {}
    for d in domains:
        s = summarize(d)
        if s:
            summary[d] = s
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2))
    for d, s in summary.items():
        print(
            f"{d:20s} tasks={s['n_tasks_seen']:4d} sims={s['n_sims']:5d} "
            f"mean={s['mean_reward']:.4f} {s['pass^k']} terms={s['termination_reasons']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
