import json, os, collections, glob
T = "tsis/deepdive/tau2-bench"
def audit_results_dir(root):
    print("="*70)
    print("RESULTS DIR:", root)
    domdirs = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root,d)) and not d.startswith("mock_allinfra") and d!="intake")
    for dom in domdirs:
        rj = os.path.join(root, dom, "results.json")
        if not os.path.exists(rj):
            print(f"  [{dom}] results.json MISSING"); continue
        try:
            data = json.load(open(rj, encoding="utf-8"))
        except Exception as e:
            print(f"  [{dom}] results.json PARSE FAIL: {e}"); continue
        sims = data.get("simulations", data if isinstance(data, list) else [])
        if isinstance(data, dict) and "simulations" not in data:
            print(f"  [{dom}] keys={list(data.keys())[:6]} (no simulations key)")
            sims = []
        n = len(sims)
        pairs = collections.Counter((s.get("task_id") or s.get("task",{}).get("id") if isinstance(s.get("task"),dict) else s.get("task_id"), s.get("trial_index", s.get("trial"))) for s in sims)
        dups = {k:v for k,v in pairs.items() if v>1}
        trials = collections.Counter(s.get("trial_index", s.get("trial")) for s in sims)
        tasks = set(p[0] for p in pairs)
        nonereward = sum(1 for s in sims if s.get("reward_info") is None)
        # contiguous trials check
        tset = set(trials)
        contiguous = tset == set(range(0, max(tset)+1)) if tset else True
        print(f"  [{dom}] sims={n} tasks={len(tasks)} trials={dict(sorted(trials.items()))} dup(task,trial)={len(dups)} contiguous_trials={contiguous} reward_info_None={nonereward}")
        if dups: print(f"      dups sample: {list(dups.items())[:3]}")
    # summary.json
    sj = os.path.join(root, "summary.json")
    if os.path.exists(sj):
        try:
            s = json.load(open(sj, encoding="utf-8"))
            print(f"  summary.json OK; domains={list(s.keys()) if isinstance(s,dict) else '?'}")
            if isinstance(s, dict):
                for dom, e in list(s.items())[:12]:
                    if isinstance(e, dict):
                        print(f"    {dom}: n={e.get('n_simulations') or e.get('n_sims')} mean={e.get('mean') or e.get('mean_reward')} keys={sorted(e.keys())[:8]}")
        except Exception as e:
            print(f"  summary.json PARSE FAIL: {e}")
    else:
        print("  summary.json MISSING")
    # sweep_status
    ss = os.path.join(root, "sweep_status.json")
    if os.path.exists(ss):
        try:
            st = json.load(open(ss, encoding="utf-8"))
            print(f"  sweep_status.json OK: {json.dumps(st)[:240]}")
        except Exception as e:
            print(f"  sweep_status.json PARSE FAIL: {e}")
    # usage files
    for uf in sorted(glob.glob(os.path.join(root, "usage_*.json"))):
        try:
            u = json.load(open(uf, encoding="utf-8"))
            tot = u.get("total_calls") or u.get("calls") or sum(v.get("calls",0) for v in u.values() if isinstance(v,dict)) or "n/a"
            print(f"  {os.path.basename(uf)}: OK (total~{tot})")
        except Exception as e:
            print(f"  {os.path.basename(uf)}: PARSE FAIL {e}")

for r in ("results","results_v2","results_v2_grok","results_secondmodel"):
    audit_results_dir(os.path.join(T,r))
