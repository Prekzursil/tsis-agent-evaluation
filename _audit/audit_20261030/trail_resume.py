import json, os, collections
TR = "tsis/deepdive/trail/work/fullrun"

# corpus2_summary.json vs disk
cs = json.load(open(os.path.join(TR, "corpus2_summary.json"), encoding="utf-8"))
print("corpus2_summary.json keys:", sorted(cs.keys()))
scals = {k: v for k, v in cs.items() if not isinstance(v, (dict, list))}
print("corpus2_summary scalars:", scals)
diskA = len([f for f in os.listdir(os.path.join(TR, "corpus2_labels")) if f.endswith(".json")])
print("corpus2_labels on disk:", diskA, "-> summary", "CURRENT" if cs.get("label_files") == diskA else f"STALE (summary says {cs.get('label_files')})")

# batchb_summary.json vs disk
bs = json.load(open(os.path.join(TR, "batchb_summary.json"), encoding="utf-8"))
print("\nbatchb_summary.json:", json.dumps(bs)[:500])
diskB = len([f for f in os.listdir(os.path.join(TR, "corpus2_labels_b")) if f.endswith(".json")])
print("corpus2_labels_b on disk:", diskB)

# batchb_agreement
ba = json.load(open(os.path.join(TR, "batchb_agreement.json"), encoding="utf-8"))
print("\nbatchb_agreement keys:", sorted(ba.keys()))
print("batchb_agreement scalars:", {k: v for k, v in ba.items() if not isinstance(v, (dict, list))})

# corpus2_jobs: canonical totals & job state
cj = json.load(open(os.path.join(TR, "corpus2_jobs.json"), encoding="utf-8"))
if isinstance(cj, dict):
    sc = {k: v for k, v in cj.items() if not isinstance(v, (list, dict))}
    print("\ncorpus2_jobs scalars:", sc)
    jobs = None
    for k, v in cj.items():
        if isinstance(v, list) and len(v) > 1000:
            jobs = v
    if jobs:
        stc = collections.Counter(j.get("status", "?") for j in jobs)
        print("corpus2_jobs job statuses:", dict(stc))

# which shas are missing in batch B vs the batch-A supported set (40,798)
canon = json.load(open("tsis/deepdive/corpus/canonical_set.json", encoding="utf-8"))["annotation_set"]
canon_set = set(e["sha256"] for e in canon)
shasA = {f[:-5] for f in os.listdir(os.path.join(TR, "corpus2_labels")) if f.endswith(".json")}
shasB = {f[:-5] for f in os.listdir(os.path.join(TR, "corpus2_labels_b")) if f.endswith(".json")}
print("\nshasA:", len(shasA), "shasB:", len(shasB), "A==supported(40798)?", len(shasA) == 40798)
print("B missing vs A:", len(shasA - shasB))
# queue_state
qs = json.load(open(os.path.join(TR, "queue_state.json"), encoding="utf-8"))
print("queue_state:", json.dumps(qs)[:200])
