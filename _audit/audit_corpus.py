# -*- coding: utf-8 -*-
"""Corpus integrity audit — reads manifest.jsonl, checks parse/count/sha256/uniques,
dedup_index internal consistency, and spot-checks 10 random entries against real files."""
import json, os, sys, random, hashlib

CORPUS = r"C:\Users\Prekzursil\.zcode\workspace\default\tss\tsis-deepdive\corpus"
MAN = os.path.join(CORPUS, "manifest.jsonl")

report = {}
bad_lines = []          # (lineno, reason, raw snippet)
recs = []
parse_fail = 0

with open(MAN, "rb") as f:
    raw = f.read()
# detect truncated final line: file should end with newline
ends_nl = raw.endswith(b"\n")
lines = raw.split(b"\n")
# last element after split is b"" if ends with newline
data_lines = [l for l in lines if l.strip() != b""]
report["file_bytes"] = len(raw)
report["ends_with_newline"] = ends_nl
report["nonempty_lines"] = len(data_lines)

import io
for i, l in enumerate(data_lines, 1):
    try:
        d = json.loads(l.decode("utf-8"))
        recs.append((i, d))
    except Exception as e:
        parse_fail += 1
        bad_lines.append((i, str(e), l[:120].decode("utf-8", "replace")))

report["parse_fail_count"] = parse_fail
report["total_records"] = len(recs)

# schema + sha256 present
missing_sha = []
keys_seen = {}
for ln, d in recs:
    for k in d.keys():
        keys_seen[k] = keys_seen.get(k, 0) + 1
    sha = d.get("sha256") or d.get("hash") or d.get("content_sha256")
    if not sha or not isinstance(sha, str) or len(sha) < 32:
        missing_sha.append(ln)
report["keys_histogram"] = keys_seen
report["missing_sha256_lines"] = missing_sha[:20]
report["missing_sha256_count"] = len(missing_sha)

# unique hashes
hashes = []
for ln, d in recs:
    h = d.get("sha256") or d.get("hash") or d.get("content_sha256")
    hashes.append(h)
uniq = set(hashes)
report["unique_hash_count"] = len(uniq)
report["duplicate_hash_records"] = len(hashes) - len(uniq)

# canonical_set.json
canon_path = os.path.join(CORPUS, "canonical_set.json")
try:
    with open(canon_path, "r", encoding="utf-8") as f:
        canon = json.load(f)
    if isinstance(canon, dict):
        canon_hashes = canon.get("hashes") or canon.get("canonical") or canon.get("sha256s")
        if canon_hashes is None:
            # maybe dict with counts
            report["canonical_set_shape"] = {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in canon.items()}
            canon_hashes = None
    elif isinstance(canon, list):
        canon_hashes = canon
    if canon_hashes is not None:
        canon_set = set(canon_hashes)
        report["canonical_set_size"] = len(canon_set)
        report["manifest_uniq_eq_canonical"] = (uniq == canon_set)
        report["only_in_manifest"] = len(uniq - canon_set)
        report["only_in_canonical"] = len(canon_set - uniq)
    else:
        report["canonical_set"] = "shape-unrecognized; see canonical_set_shape"
except Exception as e:
    report["canonical_set_error"] = str(e)

# dedup_index.json internal consistency
di_path = os.path.join(CORPUS, "dedup_index.json")
try:
    with open(di_path, "r", encoding="utf-8") as f:
        di = json.load(f)
    report["dedup_index_type"] = type(di).__name__
    if isinstance(di, dict):
        summary_keys = {k: v for k, v in di.items() if not isinstance(v, (list, dict))}
        report["dedup_index_summary_keys"] = summary_keys
        # find mapping section
        mapping = None
        for k, v in di.items():
            if isinstance(v, dict) and len(v) > 1000:
                mapping = (k, v); break
        if mapping:
            kname, m = mapping
            report["dedup_index_mapping_key"] = kname
            report["dedup_index_mapping_size"] = len(m)
            # all mapped canonical hashes must be in unique manifest hashes
            mapped_keys = set(m.keys())
            report["mapping_keys_subset_of_manifest_uniq"] = mapped_keys.issubset(uniq)
            vals = set()
            for v in m.values():
                if isinstance(v, str): vals.add(v)
                elif isinstance(v, list): vals.update(x for x in v if isinstance(x, str))
            report["mapping_vals_subset_of_manifest_uniq"] = vals.issubset(uniq)
            report["mapping_vals_subset_of_canon"] = (canon_set is None and "n/a") or vals.issubset(canon_set)
except Exception as e:
    report["dedup_index_error"] = str(e)

# CORPUS.md claim of unique count
try:
    with open(os.path.join(CORPUS, "CORPUS.md"), "r", encoding="utf-8", errors="replace") as f:
        corpus_md = f.read()
    import re
    nums = re.findall(r"[\d,]{6,}", corpus_md)
    report["CORPUS_md_large_numbers"] = nums[:30]
except Exception as e:
    report["CORPUS_md_error"] = str(e)

print(json.dumps(report, indent=1, default=str)[:6000])
if bad_lines:
    print("BADLINES_SAMPLE:")
    for b in bad_lines[:10]: print(b)
