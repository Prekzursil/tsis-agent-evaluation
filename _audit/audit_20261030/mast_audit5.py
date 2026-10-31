import json, os, collections
M = "tsis/deepdive/mastscope/fullrun"
a2 = json.load(open(os.path.join(M,"aggregates2.json"), encoding="utf-8"))
lab2 = [json.loads(l) for l in open(os.path.join(M,"labels_full.jsonl"), encoding="utf-8")]
prev = collections.Counter()
for r in lab2:
    if r.get("ok"):
        for m,v in r["modes"].items():
            if v: prev[m]+=1
bad=0
for m, entry in a2["modes"].items():
    if entry["yes"] != prev.get(m,0):
        bad+=1; print(f"MISMATCH {m}: agg={entry['yes']} rec={prev.get(m,0)}")
print(f"aggregates2 modes 'yes' reconciliation: {14-bad}/14 match, {bad} mismatch")
print("answered field == n_labeled_ok on all:", all(e['answered']==32540 for e in a2['modes'].values()))
# v1 aggregates vs labels.jsonl (expected stale)
a1 = json.load(open(os.path.join(M,"aggregates.json"), encoding="utf-8"))
lab = [json.loads(l) for l in open(os.path.join(M,"labels.jsonl"), encoding="utf-8")]
ok1 = sum(1 for r in lab if r.get("ok"))
prev1 = collections.Counter()
for r in lab:
    if r.get("ok"):
        for m,v in r["modes"].items():
            if v: prev1[m]+=1
bad1=0
for m, entry in a1["modes"].items():
    got = entry.get("yes") or entry.get("n") or entry
    if isinstance(entry,dict):
        g = entry.get("yes")
    else:
        g = entry
    if g != prev1.get(m,0): bad1+=1
print(f"aggregates.json(v1): n_labeled_ok={a1['n_labeled_ok']} vs actual labels.jsonl ok={ok1} -> {'STALE' if a1['n_labeled_ok']!=ok1 else 'current'}; modes mismatches={bad1}")
