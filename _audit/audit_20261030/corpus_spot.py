import json, os, random
C = "tsis/deepdive/corpus"
recs = []
with open(os.path.join(C,"manifest.jsonl"), encoding="utf-8") as f:
    for line in f:
        recs.append(json.loads(line))
random.seed(20261030)
sample = random.sample(range(len(recs)), 10)
ok = 0
for i in sample:
    r = recs[i]
    p = r["path"]
    exists = os.path.exists(p)
    size_ok = None
    if exists:
        size_ok = (os.path.getsize(p) == r["size"])
    verdict = "PASS" if (exists and size_ok) else ("MISSING(expected)" if r["status"]=="missing" else "FAIL")
    if verdict=="PASS" or (not exists and r["status"]=="missing"): ok += 1
    print(f"[{i}] {verdict} status={r['status']} size_manifest={r['size']} exists={exists} size_ok={size_ok} path={p[:110]}")
print(f"spot-checks ok: {ok}/10 (missing-status entries count as consistent when absent)")
