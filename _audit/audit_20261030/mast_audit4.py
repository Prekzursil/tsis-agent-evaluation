import json, os, collections
M = "tsis/deepdive/mastscope/fullrun"
a2 = json.load(open(os.path.join(M,"aggregates2.json"), encoding="utf-8"))
lab2 = [json.loads(l) for l in open(os.path.join(M,"labels_full.jsonl"), encoding="utf-8")]
# recompute mode prevalence and compare to aggregates2['modes']
prev = collections.Counter(); tc = 0; anymode = 0; yes = 0
for r in lab2:
    if r.get("ok"):
        tc += 1
        flagged = False
        for m,v in r["modes"].items():
            if v: prev[m]+=1; yes+=1; flagged=True
        if flagged: anymode += 1
print("recompute: ok=",tc,"traces_with_any_mode=",anymode,"total_yes=",yes)
print("agg2 says:", a2["n_labeled_ok"], a2["traces_with_any_mode"], a2["total_yes_labels"])
modes_ag = a2["modes"]
print("agg2 modes type:", type(modes_ag).__name__)
if isinstance(modes_ag, dict):
    k0 = list(modes_ag.keys())[:3]
    print("agg2 modes sample:", {k: modes_ag[k] for k in k0})
    # compare counts
    bad = 0
    for m, entry in modes_ag.items():
        want = prev.get(m,0)
        got = entry.get("n") if isinstance(entry, dict) else entry
        if got != want:
            bad += 1
            if bad <= 5: print(f"  MISMATCH mode {m}: agg={got} recomputed={want}")
    print("mode-count mismatches:", bad, "of", len(modes_ag))
# task_completed
tcv = collections.Counter(r.get("task_completed") for r in lab2 if r.get("ok"))
print("task_completed dist:", dict(tcv))
print("agg2 task_completed:", a2.get("task_completed"), "pct:", a2.get("task_completed_yes_pct"))
# checkpoints
for f in ("sweep_status.json","sweep_status2.json","fallback_pending.json","targets_summary.json","crosscheck2_agreement.json","crosscheck_agreement.json","privacy_scan_full2.json","sweep2_status_history.jsonl"):
    p = os.path.join(M,f)
    try:
        raw = open(p, "rb").read()
        if f.endswith(".jsonl"):
            ls = [l for l in raw.splitlines() if l.strip()]
            for l in ls: json.loads(l)
            print(f"CHECKPOINT {f}: OK jsonl lines={len(ls)}")
        else:
            json.loads(raw)
            print(f"CHECKPOINT {f}: OK bytes={len(raw)}")
    except Exception as e:
        print(f"CHECKPOINT {f}: FAIL {e}")
# census + crosschecks + privacy partial + scan_skipped_results
for f in ("census.jsonl","crosscheck.jsonl","crosscheck2.jsonl","crosscheck_mini.jsonl","privacy_partial.jsonl","scan_skipped_results.jsonl","labels_smoke.jsonl","smoke2.jsonl","targets_partial.jsonl"):
    p = os.path.join(M,f); n=0; bad=0
    for l in open(p, encoding="utf-8"):
        if not l.strip(): continue
        n+=1
        try: json.loads(l)
        except Exception: bad+=1
    print(f"JSONL {f}: lines={n} parse_fail={bad}")
