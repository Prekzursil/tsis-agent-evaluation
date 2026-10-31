# -*- coding: utf-8 -*-
"""tau2-bench audit: every results JSON parses; per-domain/per-trial consistency;
checkpoint resumability (simulation_index vs sims); summary.json reconciliation."""
import json, os, math
from collections import Counter

R = r"C:\Users\Prekzursil\.zcode\workspace\default\tss\tsis-deepdive\tau2-bench\results"

summary = json.load(open(os.path.join(R, "summary.json"), encoding="utf-8"))
print("summary.json domains:", list(summary.keys()))
status = json.load(open(os.path.join(R, "sweep_status.json"), encoding="utf-8"))
print("sweep_status.json:", json.dumps(status, indent=1, default=str)[:1200])

for dom in sorted(os.listdir(R)):
    p = os.path.join(R, dom)
    if not os.path.isdir(p):
        continue
    fp = os.path.join(p, "results.json")
    try:
        with open(fp, "rb") as f:
            raw = f.read()
        data = json.loads(raw)
    except Exception as e:
        print(f"[{dom}] results.json PARSE FAIL: {e}")
        continue
    sims = data.get("simulations", [])
    idx = data.get("simulation_index") or []
    pairs = [(s.get("task_id"), s.get("trial")) for s in sims]
    dup = [k for k, v in Counter(pairs).items() if v > 1]
    by_task = {}
    missing_reward = 0; missing_seed = 0; missing_term = 0
    for s in sims:
        by_task.setdefault(s.get("task_id"), set()).add(s.get("trial"))
        ri = s.get("reward_info") or {}
        if ri.get("reward") is None: missing_reward += 1
        if s.get("seed") is None: missing_seed += 1
        if not s.get("termination_reason"): missing_term += 1
    contiguous = all(tset == set(range(len(tset))) for tset in by_task.values())
    idx_pairs = [(e.get("task_id"), e.get("trial")) for e in idx]
    idx_ok = (not idx) or (len(set(idx_pairs)) == len(idx_pairs) and set(idx_pairs) == set(pairs))
    # summary reconciliation (independent math)
    s = summary.get(dom)
    rec = {}
    if s:
        vals = {}
        for (t, tr) in pairs:
            sim = next(x for x in sims if x.get("task_id") == t and x.get("trial") == tr)
            vals.setdefault(t, {})[tr] = float((sim.get("reward_info") or {}).get("reward") or 0.0)
        mean_r = sum(x for v in vals.values() for x in v.values()) / max(1, len(sims))
        rec["mean_ok"] = abs(s["mean_reward"] - round(mean_r, 4)) < 5e-4
        rec["n_sims_ok"] = s["n_sims"] == len(sims)
        rec["n_tasks_ok"] = s["n_tasks_seen"] == len(by_task)
    print(f"[{dom}] sims={len(sims)} tasks={len(by_task)} dup_pairs={len(dup)} contiguous_trials={contiguous} "
          f"missing_reward={missing_reward} missing_seed={missing_seed} missing_term={missing_term} "
          f"idx_entries={len(idx)} idx_consistent={idx_ok} summary_rec={rec}")
    top_keys = list(data.keys())
    print(f"    results.json top-level keys: {top_keys}")

# usage files
for f in sorted(os.listdir(R)):
    if f.startswith("usage_") and f.endswith(".json"):
        try:
            u = json.load(open(os.path.join(R, f), encoding="utf-8"))
            print(f"[{f}] OK calls={u.get('total_calls')} ptok={u.get('total_prompt_tokens')} ctok={u.get('total_completion_tokens')}")
        except Exception as e:
            print(f"[{f}] PARSE FAIL: {e}")
