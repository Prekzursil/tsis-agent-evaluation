# -*- coding: utf-8 -*-
"""Corpus cross-check part 2: exact reconciliation manifest <-> dedup_index <-> canonical_set,
canonical-choice rule verification, and 10 random on-disk spot checks."""
import json, os, random, hashlib

CORPUS = r"C:\Users\Prekzursil\.zcode\workspace\default\tss\tsis-deepdive\corpus"
recs = []
with open(os.path.join(CORPUS, "manifest.jsonl"), "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line:
            recs.append(json.loads(line))

ok = [r for r in recs if r["status"] == "ok"]
missing = [r for r in recs if r["status"] == "missing"]
print("total", len(recs), "ok", len(ok), "missing", len(missing))

from collections import Counter, defaultdict
hash_all = Counter(r["sha256"] for r in recs)
hash_ok = Counter(r["sha256"] for r in ok)
uniq_all = set(hash_all)
uniq_ok = set(hash_ok)
print("uniq_all", len(uniq_all), "uniq_ok", len(uniq_ok))
only_in_all = uniq_all - uniq_ok   # hashes whose every copy is missing
print("hashes_only_in_missing", len(only_in_all), list(only_in_all)[:5])
for h in list(only_in_all)[:3]:
    for r in recs:
        if r["sha256"] == h:
            print("  example missing-only rec:", r["status"], r["path"])
            break

canon = json.load(open(os.path.join(CORPUS, "canonical_set.json"), encoding="utf-8"))
ann = canon["annotation_set"]
ann_hashes = set(e["sha256"] for e in ann)
print("annotation_set size", len(ann), "unique ann hashes", len(ann_hashes))
print("ann == uniq_ok:", ann_hashes == uniq_ok)
print("ann == uniq_all:", ann_hashes == uniq_all)

di = json.load(open(os.path.join(CORPUS, "dedup_index.json"), encoding="utf-8"))
groups = di["groups"]
print("dedup groups", len(groups), "declared duplicate_hashes", di.get("duplicate_hashes"),
      "declared duplicate_files", di.get("duplicate_files"))
dup_ok = {h for h, c in hash_ok.items() if c > 1}
dup_all = {h for h, c in hash_all.items() if c > 1}
print("groups keys == dup_all:", set(groups.keys()) == dup_all, "| == dup_ok:", set(groups.keys()) == dup_ok)

# path->record map (path should be unique per record? check duplicate paths)
path_count = Counter(r["path"] for r in recs)
dup_paths = [p for p, c in path_count.items() if c > 1]
print("manifest paths appearing >1 time:", len(dup_paths))
by_path = {}
for r in recs:
    by_path.setdefault(r["path"], []).append(r)

# group internal consistency + member sum
member_sum = 0
inconsistent = []
for h, paths in groups.items():
    if not isinstance(paths, list) or len(paths) < 2:
        inconsistent.append((h, "group size <2 or not list", paths))
        continue
    if paths != sorted(paths):
        inconsistent.append((h, "paths not sorted", paths[:3]))
    for p in paths:
        rr = by_path.get(p)
        if not rr:
            inconsistent.append((h, "path not in manifest", p)); continue
        if not any(x["sha256"] == h for x in rr):
            inconsistent.append((h, "path in manifest but different hash", p))
    member_sum += len(paths)
print("groups member sum", member_sum, "(declared duplicate_files", di.get("duplicate_files"), ")")
print("inconsistent groups:", len(inconsistent))
for x in inconsistent[:5]: print("  ", x)

# dup statistics reconciliation
ok_recs_with_duphash = sum(c for h, c in hash_ok.items() if c > 1)
print("ok records sharing a dup hash (first+extra):", ok_recs_with_duphash,
      "-> extra ok copies:", ok_recs_with_duphash - len(dup_ok))
missing_recs_with_duphash = sum(1 for r in missing if hash_ok.get(r["sha256"], 0) > 0 or hash_all[r["sha256"]] > 1)
print("missing records whose hash is dup somewhere:", missing_recs_with_duphash)

# canonical choice rule: for each dup hash, chosen path should be the ok record with
# newest mtime, tie larger size, tie lex smallest path. Check across ALL groups (also
# verifies singletons: chosen path must be the only ok record for the hash).
ann_by_hash = {e["sha256"]: e for e in ann}
bad_choice = []
for h in uniq_ok:
    cands = [r for r in ok if r["sha256"] == h]
    if h not in ann_by_hash:
        bad_choice.append((h, "missing from annotation_set", None)); continue
    best = sorted(cands, key=lambda r: (-r["mtime"], -r["size"], r["path"]))[0]
    if ann_by_hash[h]["path"] != best["path"]:
        bad_choice.append((h, ann_by_hash[h]["path"], best["path"]))
print("canonical-choice rule violations:", len(bad_choice))
for x in bad_choice[:5]: print("  ", x)

# stats.json reconciliation
try:
    st = json.load(open(os.path.join(CORPUS, "stats.json"), encoding="utf-8"))
    print("stats.json:", json.dumps(st, default=str)[:1500])
except Exception as e:
    print("stats.json error:", e)

# 10 random spot checks: path exists + size matches
random.seed(20261018)
sample = random.sample(recs, 10)
print("SPOT CHECKS:")
for r in sample:
    p = r["path"]
    exists = os.path.exists(p)
    sz = os.path.getsize(p) if exists else None
    size_match = (sz == r["size"]) if exists else False
    print(f"  [{r['status']:7s}] exists={exists} size_match={size_match} rec_size={r['size']} disk={sz} {p[:110]}")
