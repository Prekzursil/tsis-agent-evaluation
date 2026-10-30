"""Failure analysis for the custom e-commerce domains (ecommerce2, ecommerce_poc).

For every simulation whose final reward < 1.0, extract:
  - the rule family (parsed from the task id: coupon_/vat_/return_/shipping_/
    cancel_/lost_/ecomm_<family>_),
  - which reward components failed (DB hash, which action checks, which
    COMMUNICATE checks -- with the evaluator's justification strings),
  - the assistant tool calls made during the simulation,
and aggregate per family. Writes results/failures_custom.json and prints a
human-readable report.

Usage: repo/.venv/Scripts/python.exe analyze_failures.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

LANE = Path(__file__).resolve().parent
RESULTS = LANE / "results"

FAMILY_RE = re.compile(r"^(?:ecomm_)?(coupon|vat|return|shipping|cancel|lost)")


def family_of(task_id: str) -> str:
    m = FAMILY_RE.match(task_id)
    return m.group(1) if m else "other"


def analyze(domain: str) -> dict:
    path = RESULTS / domain / "results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    sims = data["simulations"] if isinstance(data, dict) and "simulations" in data else data
    per_family = defaultdict(lambda: {"n_sims": 0, "n_fail": 0, "failures": []})
    for s in sims:
        tid = s["task_id"]
        fam = family_of(tid)
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
                "args": (a.get("action") or {}).get("arguments"),
                "info": (a.get("action") or {}).get("info"),
                "type": a.get("tool_type"),
            }
            for a in (ri.get("action_checks") or [])
            if not a.get("action_match")
        ]
        ok_actions = [((a.get("action") or {}).get("name")) for a in (ri.get("action_checks") or []) if a.get("action_match")]
        failed_comm = [
            {"info": c.get("info"), "justification": c.get("justification")}
            for c in (ri.get("communicate_checks") or [])
            if not c.get("met")
        ]
        # collect assistant tool calls from the trajectory
        tool_calls = []
        for msg in (s.get("messages") or []):
            role = msg.get("role")
            if role == "assistant":
                for tc in msg.get("tool_calls") or []:
                    fn = tc.get("function") or {}
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except Exception:
                        args = fn.get("arguments")
                    tool_calls.append(f"{fn.get('name')}({json.dumps(args, ensure_ascii=False)[:120]})")
        entry["failures"].append(
            {
                "task_id": tid,
                "trial": s.get("trial"),
                "reward": reward,
                "termination": s.get("termination_reason"),
                "db_match": db.get("db_match"),
                "db_reward": db.get("db_reward"),
                "failed_action_checks": failed_actions,
                "passed_action_checks": ok_actions,
                "failed_communicate_checks": failed_comm,
                "assistant_tool_calls": tool_calls,
            }
        )
    return {fam: v for fam, v in sorted(per_family.items())}


def main() -> int:
    out = {}
    for domain in ("ecommerce2", "ecommerce_poc"):
        p = RESULTS / domain / "results.json"
        if not p.exists():
            print(f"SKIP {domain}: no results yet")
            continue
        out[domain] = analyze(domain)
    (RESULTS / "failures_custom.json").write_text(json.dumps(out, indent=2))
    for domain, fams in out.items():
        print(f"\n===== {domain} =====")
        for fam, v in fams.items():
            print(f"  {fam}: {v['n_fail']}/{v['n_sims']} sims failed")
            for f in v["failures"]:
                db = f["db_match"]
                print(
                    f"    - {f['task_id']} t{f['trial']} reward={f['reward']} "
                    f"term={f['termination']} db_match={db} "
                    f"failed_actions={[a['name'] for a in f['failed_action_checks']]} "
                    f"failed_comm={[c['info'] for c in f['failed_communicate_checks']]}"
                )
                for c in f["failed_communicate_checks"]:
                    print(f"        comm MISS [{c['info']}]: {c['justification']}")
                for a in f["failed_action_checks"]:
                    print(f"        action MISS: {a['name']} {a['info']} type={a['type']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
