import json, os
T = "tsis/deepdive/tau2-bench"
for root in ("results","results_v2_grok"):
    sj = os.path.join(T,root,"summary.json")
    if not os.path.exists(sj): continue
    s = json.load(open(sj, encoding="utf-8"))
    print("="*50, root)
    for dom, e in s.items():
        rj = os.path.join(T,root,dom,"results.json")
        if not os.path.exists(rj):
            print(f"  {dom}: summary n={e.get('n_sims')} but results.json MISSING"); continue
        sims = json.load(open(rj, encoding="utf-8"))["simulations"]
        match = e.get("n_sims")==len(sims)
        # recompute mean reward
        import statistics
        rw = [x["reward_info"]["reward"] for x in sims if x.get("reward_info") and x["reward_info"].get("reward") is not None]
        mean_ok = None
        if rw: mean_ok = abs((sum(rw)/len(rw)) - e.get("mean_reward", -9)) < 1e-9
        print(f"  {dom}: summary_n={e.get('n_sims')} results_n={len(sims)} match={match} mean_recompute_match={mean_ok} (n_rewarded={len(rw)})")
# stray dir checks
for extra in ("results_v2_grok/mock_allinfra_ledgerstorm_20261028",):
    for f in os.listdir(os.path.join(T,extra)):
        if f.endswith(".json"):
            try:
                d = json.load(open(os.path.join(T,extra,f), encoding="utf-8"))
                print(f"EXTRA {extra}/{f}: OK type={type(d).__name__}")
            except Exception as e:
                print(f"EXTRA {extra}/{f}: FAIL {e}")
