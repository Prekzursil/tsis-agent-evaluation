# -*- coding: utf-8 -*-
"""tau2 audit part 2: telecom/telecom-workflow summary staleness vs raw; mtimes;
sim reward-detail for telecom missing rewards; RESULTS.md domain rows."""
import json, os, datetime

R = r"C:\Users\Prekzursil\.zcode\workspace\default\tss\tsis-deepdive\tau2-bench\results"
summary = json.load(open(os.path.join(R, "summary.json"), encoding="utf-8"))

def mt(p):
    return datetime.datetime.fromtimestamp(os.path.getmtime(p)).strftime("%Y-%m-%d %H:%M:%S")

for f in ["summary.json", "sweep_status.json", "sweep_full.log"] + \
         [os.path.join(d, "results.json") for d in sorted(os.listdir(R)) if os.path.isdir(os.path.join(R, d))]:
    p = os.path.join(R, f)
    if os.path.exists(p):
        print(f"{mt(p)}  {os.path.getsize(p):>12,}  {f}")

print()
print("summary[telecom]:", json.dumps(summary.get("telecom"), indent=1))
print("summary[telecom-workflow]:", summary.get("telecom-workflow"))

d = json.load(open(os.path.join(R, "telecom", "results.json"), encoding="utf-8"))
sims = d["simulations"]
n = len(sims)
none_r = [s for s in sims if (s.get("reward_info") or {}).get("reward") is None]
print("telecom raw: sims", n, "reward-None", len(none_r))
for s in none_r[:3]:
    print("  None-reward sim:", {k: s.get(k) for k in ("task_id", "trial", "seed", "termination_reason")},
          "| reward_info:", str(s.get("reward_info"))[:160])
# if reward None counted as 0:
vals = [float((s.get("reward_info") or {}).get("reward") or 0.0) for s in sims]
print("mean (None->0):", round(sum(vals)/n, 4), "| mean (skip None):",
      round(sum(v for v in vals if v is not None or True)/n, 4))
# maybe summary computed on completed subset only (trials 0..3):
from collections import defaultdict
bt = defaultdict(dict)
for s in sims:
    bt[s["task_id"]][s.get("trial")] = float((s.get("reward_info") or {}).get("reward") or 0.0)
print("tasks:", len(bt), "trial-set sizes:", sorted({len(v) for v in bt.values()}))
# try summary numbers on first-4-trials subset
sub = {t: dict(list(v.items())[:4]) for t, v in bt.items()}
nsub = sum(len(v) for v in sub.values())
mean_sub = sum(x for v in sub.values() for x in v.values()) / nsub
print("subset-first4: sims", nsub, "tasks", len(sub), "mean", round(mean_sub, 4))

dw = json.load(open(os.path.join(R, "telecom-workflow", "results.json"), encoding="utf-8"))
sw = dw["simulations"]
nw = [s for s in sw if (s.get("reward_info") or {}).get("reward") is None]
print("\ntelecom-workflow raw: sims", len(sw), "tasks", len({s['task_id'] for s in sw}), "reward-None", len(nw))
print("  trial values present:", sorted({s.get('trial') for s in sw})[:10])
for s in nw[:3]:
    print("  None-reward:", {k: s.get(k) for k in ("task_id", "trial", "seed", "termination_reason")},
          "| ri:", str(s.get("reward_info"))[:140])

# RESULTS.md rows
mdp = r"C:\Users\Prekzursil\.zcode\workspace\default\tss\tsis-deepdive\tau2-bench\RESULTS.md"
if os.path.exists(mdp):
    txt = open(mdp, encoding="utf-8").read()
    for ln in txt.splitlines():
        if ln.strip().startswith("|") and any(dm in ln for dm in
           ("airline", "ecommerce_poc", "mock", "retail", "telecom", "banking")):
            print("MD:", ln.strip()[:160])
else:
    print("RESULTS.md MISSING for tau2 lane")
