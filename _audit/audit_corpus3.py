# -*- coding: utf-8 -*-
"""Corpus cross-check part 3: canonical choice rule (mtime is ISO string), stats.json
reconciliation, unsorted-group diagnosis, and 10 random on-disk spot checks."""
import json, os, random
from collections import Counter

CORPUS = r"C:\Users\Prekzursil\.zcode\workspace\default\tss\tsis-deepdive\corpus"
recs = []
with open(os.path.join(CORPUS, "manifest.jsonl"), "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            recs.append(json.loads(line))
ok = [r for r in recs if r["status"] == "ok"]

canon = json.load(open(os.path.join(CORPUS, "canonical_set.json"), encoding="utf-8"))
ann_by_hash = {e["sha256"]: e for e in canon["annotation_set"]}

by_hash = {}
for r in ok:
    by_hash.setdefault(r["sha256"], []).append(r)

def mt_key(r):
    m = r["mtime"]
    if isinstance(m, (int, float)):
        return (0, -float(m))          # numeric epoch (descending)
    return (1, [-ord(c) for c in str(m)])  # ISO string, descending lexicographic

str_vs_num = Counter(isinstance(r["mtime"], str) for r in ok)
print("mtime string-vs-numeric among ok records:", dict(str_vs_num))

bad_choice = 0; bad_examples = []
for h, cands in by_hash.items():
    if h not in ann_by_hash:
        bad_choice += 1; bad_examples.append((h, "absent from annotation_set", None)); continue
    best = sorted(cands, key=lambda r: (mt_key(r), -r["size"], r["path"]))[0]
    if ann_by_hash[h]["path"] != best["path"]:
        bad_choice += 1
        if len(bad_examples) < 5: bad_examples.append((h, ann_by_hash[h]["path"], best["path"]))
print("canonical-choice violations (newest mtime / larger size / lex-min path):", bad_choice)
for x in bad_examples: print("  ", x)
# annotation entries' size/mtime should equal the chosen record's
meta_mismatch = 0
for h, e in ann_by_hash.items():
    r = next((x for x in by_hash.get(h, []) if x["path"] == e["path"]), None)
    if r is None or r.get("size") != e.get("size"):
        meta_mismatch += 1
print("annotation size mismatches vs manifest:", meta_mismatch)

# unsorted-group diagnosis
di = json.load(open(os.path.join(CORPUS, "dedup_index.json"), encoding="utf-8"))
groups = di["groups"]
unsorted_groups = []
for h, paths in groups.items():
    if paths != sorted(paths):
        unsorted_groups.append((h, paths))
print("groups not sorted by plain sorted():", len(unsorted_groups))
case_insens_ok = sum(1 for h, p in unsorted_groups if p == sorted(p, key=str.lower))
print("  of those, sorted case-insensitively:", case_insens_ok)
for h, p in unsorted_groups[:3]:
    print("  group", h[:12], "len", len(p))
    sp = sorted(p)
    for a, b in zip(p, sp):
        if a != b:
            print("    first divergence:\n      file:", a, "\n      py-sorted:", b)
            break

# stats.json
st = json.load(open(os.path.join(CORPUS, "stats.json"), encoding="utf-8"))
print("stats.json top:", json.dumps(st, default=str)[:1200])

# 10 random spot checks
random.seed(20261018)
sample = random.sample(recs, 10)
print("SPOT CHECKS (seed 20261018):")
for r in sample:
    p = r["path"]
    exists = os.path.exists(p)
    sz = os.path.getsize(p) if exists else None
    size_match = (sz == r["size"]) if exists else False
    print(f"  [{r['status']:7s}] exists={exists} size_match={size_match} rec_size={r['size']} disk={sz} {p[:110]}")
