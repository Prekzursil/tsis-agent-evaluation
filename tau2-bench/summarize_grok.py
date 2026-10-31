"""Summarize the grok-4.7 v2.0.0 batch (results_v2_grok/) into summary.json.

Recomputes pass^k with the harness's own metric
(tau2.metrics.agent_metrics.get_tasks_pass_hat_k) — the same path as the
v1.0.1 canonical run (summarize.py) and the GLM v2 partial (summarize2.py).
Adds diagnostics: termination-reason counts, infra-error counts, per-task
reward grids.

Usage: repo/.venv/Scripts/python.exe summarize_grok.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

LANE = Path(__file__).resolve().parent
RESULTS = LANE / "results_v2_grok"

sys.path.insert(0, str(LANE / "repo" / "src"))

from tau2.metrics.agent_metrics import get_tasks_pass_hat_k  # noqa: E402
from tau2.data_model.simulation import Results  # noqa: E402


def load_results(domain: str):
    p = RESULTS / domain / "results.json"
    if not p.exists():
        return None
    raw = json.loads(p.read_text())
    res = Results.model_validate(raw)
    # Repair stale info.num_trials (same reason as summarize2.py: resumed
    # files may carry an older num_trials; the simulations are authoritative).
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
    by_task: dict[str, dict[int, float]] = {}
    for s in sims:
        r = s.reward_info.reward if s.reward_info else None
        by_task.setdefault(s.task_id, {})[s.trial] = r

    term = Counter(str(s.termination_reason.value) for s in sims)
    infra = sum(1 for v in term.items() if v[0] == "infrastructure_error" for _ in range(v[1]))

    rewards = [x for v in by_task.values() for x in v.values()]
    mean_reward = (
        round(sum(r for r in rewards if r is not None) / len(rewards), 4)
        if rewards
        else None
    )

    out = {
        "domain": domain,
        "n_tasks_seen": len(by_task),
        "n_sims": len(sims),
        "mean_reward": mean_reward,
        "termination_reasons": dict(term),
        "n_infra_errors": infra,
        "per_task": {
            t: {
                "trials": {str(k): v for k, v in sorted(v.items())},
                "n_success": sum(1 for x in v.values() if x == 1.0),
                "n_trials": len(v),
            }
            for t, v in sorted(by_task.items())
        },
        "pass^k": {},
    }
    n_trials_per_task = sorted({len(v) for v in by_task.values()})
    if n_trials_per_task and n_trials_per_task[0] >= 1:
        df = get_tasks_pass_hat_k(res)
        for k in range(1, (n_trials_per_task[-1] if n_trials_per_task else 1) + 1):
            col = f"pass^{k}"
            if col in df.columns:
                out["pass^k"][f"k={k}"] = round(float(df[col].mean()), 4)
    return out


def main() -> int:
    domains = sorted(
        d.name
        for d in RESULTS.iterdir()
        if (d / "results.json").exists() and "allinfra" not in d.name
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
            f"mean={s['mean_reward']} infra={s['n_infra_errors']} "
            f"{s['pass^k']} terms={s['termination_reasons']}"
        )
    print(f"\nwrote {RESULTS / 'summary.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
