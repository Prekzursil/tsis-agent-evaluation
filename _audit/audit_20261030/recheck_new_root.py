"""Re-run all core audit checks against the NEW post-migration root tsis/agent-evaluation/.
Every check here was already run pre-migration on the same bytes at tsis/deepdive/;
this re-run proves the move itself broke nothing."""
import json, os, hashlib, random, collections

R = "tsis/agent-evaluation"
ok = lambda b: "PASS" if b else "FAIL"

# ---------- 1. corpus ----------
C = os.path.join(R, "corpus")
n = pf = shamis = 0
statuses = {}
unique_ok = set()
ends_nl = None
with open(os.path.join(C, "manifest.jsonl"), "rb") as f:
    data = f.read()
ends_nl = data.endswith(b"\n")
for line in data.splitlines():
    if not line.strip():
        continue
    n += 1
    try:
        rec = json.loads(line)
    except Exception:
        pf += 1
        continue
    if not rec.get("sha256"):
        shamis += 1
    statuses[rec["status"]] = statuses.get(rec["status"], 0) + 1
    if rec["status"] == "ok":
        unique_ok.add(rec["sha256"])
print(f"[corpus] manifest lines={n} (==124327: {n==124327}) parse_fail={pf} sha_missing={shamis} ends_nl={ends_nl}")
print(f"[corpus] statuses={statuses} unique_ok={len(unique_ok)} (==41877: {len(unique_ok)==41877})")
cs = json.load(open(os.path.join(C, "canonical_set.json"), encoding="utf-8"))
ann = set(e["sha256"] for e in cs["annotation_set"])
print(f"[corpus] annotation_set==unique_ok: {ann==unique_ok}; unique_files field={cs['unique_files']}")
di = json.load(open(os.path.join(C, "dedup_index.json"), encoding="utf-8"))
g = di["groups"]
mt = sum(len(v) for v in g.values())
print(f"[corpus] dedup groups={len(g)}==decl {di['duplicate_hashes']}: {len(g)==di['duplicate_hashes']}; members={mt}==decl {di['duplicate_files']}: {mt==di['duplicate_files']}")

# spot check 10 (re-run at new path, same seed)
recs = [json.loads(l) for l in data.splitlines() if l.strip()]
random.seed(20261030)
spot_ok = 0
for i in random.sample(range(len(recs)), 10):
    r = recs[i]
    ex = os.path.exists(r["path"])
    sz = os.path.getsize(r["path"]) == r["size"] if ex else False
    if ex and sz:
        spot_ok += 1
print(f"[corpus] spot-check 10 at new path: {spot_ok}/10 PASS")

# ---------- 2. mastscope ----------
M = os.path.join(R, "mastscope", "fullrun")
for fn, expect in (("labels.jsonl", 16253), ("labels_full.jsonl", 33889)):
    raw = open(os.path.join(M, fn), "rb").read()
    lines = [l for l in raw.splitlines() if l.strip()]
    bad = 0
    ids = set()
    for l in lines:
        try:
            r = json.loads(l)
            ids.add(r.get("trace_id") or r.get("target_id"))
        except Exception:
            bad += 1
    print(f"[mastscope] {fn}: lines={len(lines)} (=={expect}: {len(lines)==expect}) parse_fail={bad} dup_ids={len(lines)-len(ids)} ends_nl={raw.endswith(bytes([10]))}")
a2 = json.load(open(os.path.join(M, "aggregates2.json"), encoding="utf-8"))
lab2 = [json.loads(l) for l in open(os.path.join(M, "labels_full.jsonl"), encoding="utf-8")]
okc = sum(1 for r in lab2 if r.get("ok"))
pfail = sum(1 for r in lab2 if r.get("fail"))
print(f"[mastscope] aggregates2 reconcile: n_labeled_ok={a2['n_labeled_ok']}=={okc}: {a2['n_labeled_ok']==okc}; n_parse_fail={a2['n_parse_fail']}=={pfail}: {a2['n_parse_fail']==pfail}; targets={a2['targets_total']}=={len(lab2)}: {a2['targets_total']==len(lab2)}; pending={a2['pending']}")
a1 = json.load(open(os.path.join(M, "aggregates.json"), encoding="utf-8"))
lab1 = [json.loads(l) for l in open(os.path.join(M, "labels.jsonl"), encoding="utf-8")]
ok1 = sum(1 for r in lab1 if r.get("ok"))
print(f"[mastscope] aggregates.json(v1) n_labeled_ok={a1['n_labeled_ok']} vs labels.jsonl ok={ok1} -> {'current' if a1['n_labeled_ok']==ok1 else 'STALE (v1 superseded by aggregates2)'}")

# ---------- 3. tau2 ----------
T = os.path.join(R, "tau2-bench")
tally = 0
for root in ("results", "results_v2", "results_v2_grok", "results_secondmodel"):
    rd = os.path.join(T, root)
    for dom in sorted(os.listdir(rd)):
        rj = os.path.join(rd, dom, "results.json")
        if not os.path.exists(rj):
            continue
        sims = json.load(open(rj, encoding="utf-8"))["simulations"]
        def tid(s): return s.get("task_id") or (s.get("task", {}).get("id") if isinstance(s.get("task"), dict) else None)
        def tri(s): return s.get("trial_index", s.get("trial"))
        pairs = collections.Counter((tid(s), tri(s)) for s in sims)
        dups = sum(1 for v in pairs.values() if v > 1)
        tally += len(sims)
        assert dups == 0, (root, dom)
print(f"[tau2] all results.json parse at new path; total sims across 4 dirs={tally}; dup(task,trial)=0 everywhere: PASS")

# ---------- 4. trail ----------
TR = os.path.join(R, "trail", "work", "fullrun")
gm = [json.loads(l) for l in open(os.path.join(TR, "gold_meta.jsonl"), encoding="utf-8")]
gmnv = [json.loads(l) for l in open(os.path.join(TR, "gold_meta_nv.jsonl"), encoding="utf-8")]
def lastmap(recs):
    last = {}
    for r in recs:
        last[r["file"]] = r
    return last
lmA, lmN = lastmap(gm), lastmap(gmnv)
diskA = set(os.listdir(os.path.join(TR, "gold_outputs", "glm-5.3", "GAIA")))
diskN = set(os.listdir(os.path.join(TR, "gold_outputs", "nvidia-nemotron-3-ultra", "GAIA")))
okA = {f for f, r in lmA.items() if r["status"] == "ok"}
okN = {f for f, r in lmN.items() if r["status"] == "ok"}
print(f"[trail] gold_meta parse: {len(gm)}+{len(gmnv)} records 0 fail")
print(f"[trail] glm last-wins: ok={len(okA)} disk={len(diskA)} exact-match={okA==diskA}")
print(f"[trail] nv  last-wins: ok(last)={len(okN)} disk={len(diskN)} disk+quarantined={len(diskN)+1} match={okN==diskN|{'41bbc898aa7de0f31d2382ff57700a76.json'}}")
nA = len([f for f in os.listdir(os.path.join(TR, "corpus2_labels")) if f.endswith(".json")])
nB = len([f for f in os.listdir(os.path.join(TR, "corpus2_labels_b")) if f.endswith(".json")])
print(f"[trail] corpus2_labels={nA}/40798 (complete: {nA==40798}); corpus2_labels_b={nB}/40798 (remaining={40798-nB})")
csu = json.load(open(os.path.join(TR, "corpus2_summary.json"), encoding="utf-8"))
print(f"[trail] corpus2_summary label_files={csu['label_files']} current: {csu['label_files']==nA}")
q = os.path.join(TR, "_quarantine", "nvidia-nemotron-3-ultra_GAIA")
print(f"[trail] quarantine present at new path: {os.path.exists(os.path.join(q, '41bbc898aa7de0f31d2382ff57700a76.json'))} + sidecar: {os.path.exists(os.path.join(q, '41bbc898aa7de0f31d2382ff57700a76.json.sidecar.md'))}")
print("DONE")
