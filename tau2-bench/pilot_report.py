"""Second-model pilot report: pass^k for results_secondmodel/ + side-by-side
vs the glm-5.3 baseline in results/summary.json + custom-domain failure
autopsy (same logic as analyze_failures.py, pointed at the pilot results).

Uses the harness's own metric (tau2.metrics.agent_metrics.get_tasks_pass_hat_k),
same as summarize.py. Writes results_secondmodel/pilot_summary.json.

Usage: repo/.venv/Scripts/python.exe pilot_report.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

LANE = Path(__file__).resolve().parent
PILOT = LANE / "results_secondmodel"
BASELINE_SUMMARY = LANE / "results" / "summary.json"

sys.path.insert(0, str(LANE / "repo" / "src"))

from tau2.metrics.agent_metrics import get_tasks_pass_hat_k  # noqa: E402
from tau2.data_model.simulation import Results  # noqa: E402

FAMILY_RE = re.compile(r"^(?:ecomm_)?(coupon|vat|return|shipping|cancel|lost)")


def load_results(path: Path):
    raw = json.loads(path.read_text())
    res = Results.model_validate(raw)
    # same stale-num_trials repair as summarize.py
    counts: dict[str, set] = {}
    for s in res.simulations:
        counts.setdefault(s.task_id, set()).add(s.trial)
    if counts:
        actual = min(len(v) for v in counts.values())
        if res.info.num_trials != actual:
            res.info.num_trials = actual
    return res


def summarize(domain: str) -> dict | None:
    p = PILOT / domain / "results.json"
    if not p.exists():
        return None
    res = load_results(p)
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


def autopsy(domain: str) -> dict:
    """Failure autopsy on pilot results (same fields as analyze_failures.py)."""
    path = PILOT / domain / "results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    sims = data["simulations"]
    per_family = defaultdict(lambda: {"n_sims": 0, "n_fail": 0, "failures": []})
    for s in sims:
        tid = s["task_id"]
        fam = FAMILY_RE.match(tid)
        fam = fam.group(1) if fam else "other"
        ri = s.get("reward_info") or {}
        reward = ri.get("reward", 0.0)
        entry = per_family[fam]
        entry["n_sims"] += 1
        if reward >= 1.0:
            continue
        entry["n_fail"] += 1
        db = ri.get("db_check") or {}
        failed_actions = [
            {
                "name": (a.get("action") or {}).get("name"),
                "info": (a.get("action") or {}).get("info"),
                "type": a.get("tool_type"),
            }
            for a in (ri.get("action_checks") or [])
            if not a.get("action_match")
        ]
        failed_comm = [
            {"info": c.get("info"), "justification": c.get("justification")}
            for c in (ri.get("communicate_checks") or [])
            if not c.get("met")
        ]
        tool_calls = []
        for msg in (s.get("messages") or []):
            if msg.get("role") == "assistant":
                for tc in msg.get("tool_calls") or []:
                    fn = tc.get("function") or {}
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except Exception:
                        args = fn.get("arguments")
                    tool_calls.append(
                        f"{fn.get('name')}({json.dumps(args, ensure_ascii=False)[:120]})"
                    )
        entry["failures"].append(
            {
                "task_id": tid,
                "trial": s.get("trial"),
                "reward": reward,
                "termination": s.get("termination_reason"),
                "db_match": db.get("db_match"),
                "failed_action_checks": failed_actions,
                "failed_communicate_checks": failed_comm,
                "assistant_tool_calls": tool_calls,
            }
        )
    return {fam: v for fam, v in sorted(per_family.items())}


def main() -> int:
    baseline = json.loads(BASELINE_SUMMARY.read_text())
    out = {"second_model": {}, "side_by_side": {}, "autopsy": {}}
    for domain in sorted(
        d.name for d in PILOT.iterdir() if (d / "results.json").exists()
    ):
        s = summarize(domain)
        if not s:
            continue
        out["second_model"][domain] = s
        b = baseline.get(domain)
        if b:
            out["side_by_side"][domain] = {
                "glm53_baseline": {
                    "mean_reward": b["mean_reward"],
                    "pass^k": b["pass^k"],
                    "n_sims": b["n_sims"],
                },
                "second_model": {
                    "mean_reward": s["mean_reward"],
                    "pass^k": s["pass^k"],
                    "n_sims": s["n_sims"],
                },
            }
        if domain.startswith("ecommerce"):
            out["autopsy"][domain] = autopsy(domain)
    (PILOT / "pilot_summary.json").write_text(json.dumps(out, indent=2))
    for domain, s in out["second_model"].items():
        print(
            f"{domain:12s} tasks={s['n_tasks_seen']:3d} sims={s['n_sims']:4d} "
            f"mean={s['mean_reward']:.4f} {s['pass^k']} terms={s['termination_reasons']}"
        )
        if domain in out["side_by_side"]:
            print(f"   baseline  : {out['side_by_side'][domain]['glm53_baseline']}")
    for domain, fams in out["autopsy"].items():
        print(f"\n===== {domain} failures =====")
        for fam, v in fams.items():
            print(f"  {fam}: {v['n_fail']}/{v['n_sims']} sims failed")
            for f in v["failures"]:
                print(
                    f"    - {f['task_id']} t{f['trial']} reward={f['reward']} "
                    f"term={f['termination']} db_match={f['db_match']} "
                    f"failed_actions={[a['name'] for a in f['failed_action_checks']]} "
                    f"failed_comm={[c['info'] for c in f['failed_communicate_checks']]}"
                )
                for c in f["failed_communicate_checks"]:
                    print(f"        comm MISS [{c['info']}]: {c['justification']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
