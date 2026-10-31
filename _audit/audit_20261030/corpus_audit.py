import json, hashlib, os, random, sys
C = "tsis/deepdive/corpus"
fails = []
n_lines = 0; n_parse_fail = 0; n_sha_missing = 0
statuses = {}; unique_all = set(); unique_ok = set(); paths = {}
ends_nl = None
keys_seen = {}
with open(os.path.join(C,"manifest.jsonl"),"rb") as f:
    data = f.read()
ends_nl = data.endswith(b"\n")
for i, line in enumerate(data.splitlines()):
    if not line.strip(): continue
    n_lines += 1
    try:
        rec = json.loads(line)
    except Exception as e:
        n_parse_fail += 1
        if n_parse_fail <= 5: fails.append(f"line {i+1} parse error: {e}")
        continue
    sha = rec.get("sha256")
    if not sha: n_sha_missing += 1
    st = rec.get("status","?")
    statuses[st] = statuses.get(st,0)+1
    if sha:
        unique_all.add(sha)
        if st == "ok": unique_ok.add(sha)
    p = rec.get("path")
    if p: paths.setdefault(p, rec)
    for k in rec: keys_seen[k] = keys_seen.get(k,0)+1
print(f"manifest bytes={len(data)} ends_with_newline={ends_nl}")
print(f"lines={n_lines} parse_fail={n_parse_fail} sha_missing={n_sha_missing}")
print(f"statuses={statuses}")
print(f"unique_all={len(unique_all)} unique_ok={len(unique_ok)}")
print(f"keys={sorted(keys_seen.items(), key=lambda kv:-kv[1])[:20]}")

# canonical_set.json
cs = json.load(open(os.path.join(C,"canonical_set.json"), encoding="utf-8"))
ann = cs.get("annotation_set")
print(f"canonical_set.json keys={list(cs.keys())[:8]}")
if isinstance(ann, list): print(f"annotation_set size={len(ann)} setmatch_ok={set(ann)==unique_ok} setmatch_all={set(ann)==unique_all}")
elif isinstance(ann, dict): print(f"annotation_set dict size={len(ann)}")

# stats.json
st = json.load(open(os.path.join(C,"stats.json"), encoding="utf-8"))
print("stats.totals:", json.dumps(st.get("totals", st), sort_keys=True)[:600])

# dedup_index.json
di = json.load(open(os.path.join(C,"dedup_index.json"), encoding="utf-8"))
print(f"dedup_index type={type(di).__name__} topkeys={list(di.keys())[:8] if isinstance(di,dict) else 'list'}")
