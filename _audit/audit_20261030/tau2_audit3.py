import json, os
T = "tsis/deepdive/tau2-bench"
for root in ("results", "results_v2_grok"):
    sj = os.path.join(T, root, "summary.json")
    if not os.path.exists(sj):
        continue
    s = json.load(open(sj, encoding="utf-8"))
    print("=" * 50, root)
    allmatch = True
    for dom, e in s.items():
        rj = os.path.join(T, root, dom, "results.json")
        sims = json.load(open(rj, encoding="utf-8"))["simulations"]
        n_ok = e.get("n_sims") == len(sims)
        rw = [x["reward_info"]["reward"] for x in sims
              if x.get("reward_info") and x["reward_info"].get("reward") is not None]
        # summarizer: round(sum(rewards)/len(rewards), 4) over ALL reward slots (None counts in denominator)
        by_len = len(sims)
        mine = round(sum(r for r in rw) / by_len, 4) if sims else None
        mean_ok = (mine is not None and abs(mine - e.get("mean_reward", -9)) < 5.1e-5)
        if not (n_ok and mean_ok):
            allmatch = False
            print(f"  {dom}: n_match={n_ok} mean: summary={e.get('mean_reward')} recomputed(all-sims)={mine} match={mean_ok}")
    print(f"  ALL DOMAINS RECONCILE (n_sims + mean_reward at 4dp): {allmatch}")
