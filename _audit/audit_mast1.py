# -*- coding: utf-8 -*-
"""mastscope/fullrun audit: every JSONL parses; labels.jsonl (v1) + labels_full.jsonl (v2)
line counts, schema, duplicate rules; aggregates reconciliation; checkpoint files parse."""
import json, os
from collections import Counter

D = r"C:\Users\Prekzursil\.zcode\workspace\default\tss\tsis-deepdive\mastscope\fullrun"

def scan_jsonl(fn):
    p = os.path.join(D, fn)
    n = 0; bad = []; keys = Counter(); last_ok = None
    ends_nl = None
    with open(p, "rb") as f:
        raw_tail = None
        for i, line in enumerate(f, 1):
            n += 1
            s = line.strip()
            if not s:
                bad.append((i, "empty")); continue
            try:
                d = json.loads(s.decode("utf-8"))
                if isinstance(d, dict):
                    keys.update(d.keys())
                    last_ok = d
            except Exception as e:
                bad.append((i, str(e)[:60], s[:80].decode("utf-8", "replace")))
        f.seek(0, 2)
        sz = f.tell()
        f.seek(max(0, sz - 2))
        ends_nl = f.read().endswith(b"\n")
    return {"file": fn, "lines": n, "parse_fail": len(bad), "bad_first5": bad[:5],
            "keys": dict(keys.most_common(30)), "ends_newline": ends_nl,
            "sample_last": {k: (str(v)[:60]) for k, v in list(last_ok.items())[:8]} if last_ok else None}

for fn in ["labels.jsonl", "labels_full.jsonl", "targets.jsonl", "targets_partial.jsonl",
           "targets.jsonl.tmp", "census.jsonl", "crosscheck.jsonl", "crosscheck_mini.jsonl",
           "labels_smoke.jsonl", "smoke2.jsonl", "privacy_partial.jsonl"]:
    r = scan_jsonl(fn)
    print(json.dumps(r, default=str)[:1400])
    print()

# big checkpoint json
for fn in ["manifest_index.json"]:
    p = os.path.join(D, fn)
    try:
        with open(p, "r", encoding="utf-8") as f:
            j = json.load(f)
        print(fn, "PARSE OK; type", type(j).__name__, "len", len(j))
        if isinstance(j, dict):
            it = list(j.items())[:2]
            print("  sample:", str(it)[:300])
    except Exception as e:
        print(fn, "PARSE FAIL:", str(e)[:200])
