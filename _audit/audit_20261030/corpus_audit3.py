import json, os
C = "tsis/deepdive/corpus"
cs = json.load(open(os.path.join(C,"canonical_set.json"), encoding="utf-8"))
ann = cs["annotation_set"]
e0 = ann[0]
print("annotation entry keys:", sorted(e0.keys()))
# find hash field
hf = None
for k in ("sha256","hash","content_hash"):
    if k in e0: hf = k; break
print("hash field:", hf)
ann_hashes = set(e[hf] for e in ann)
print("annotation_set unique hashes:", len(ann_hashes))
# manifest unique-ok recompute
unique_ok = set(); manifest_by_hash = {}
with open(os.path.join(C,"manifest.jsonl"), encoding="utf-8") as f:
    for line in f:
        rec = json.loads(line)
        if rec.get("sha256"):
            manifest_by_hash.setdefault(rec["sha256"], []).append(rec)
            if rec.get("status")=="ok": unique_ok.add(rec["sha256"])
print("manifest unique_ok:", len(unique_ok))
print("annotation_set == manifest unique_ok:", ann_hashes == unique_ok)
print("ann-minus-ok:", len(ann_hashes-unique_ok), "ok-minus-ann:", len(unique_ok-ann_hashes))
# verify 'unique_files' count field
print("declared unique_files:", cs["unique_files"], "== len(ann):", cs["unique_files"]==len(ann))
# annotation size fields vs manifest
mism = 0; checked = 0
for e in ann:
    h = e[hf]
    recs = manifest_by_hash.get(h)
    if not recs: print("MISSING from manifest:", h); continue
    okrecs = [r for r in recs if r["status"]=="ok"]
    if not okrecs: continue
    sizes = {r["size"] for r in okrecs}
    if e.get("size") is not None and e["size"] not in sizes: mism += 1
    checked += 1
print(f"annotation size check: checked={checked} mismatch={mism}")
