# -*- coding: utf-8 -*-
"""trail audit: gold checkpoints parse + resume state; corpus2 labels vs canonical;
corpus2_summary reconciliation; usage ledgers."""
import json, os, glob
from collections import Counter

W = r"C:\Users\Prekzursil\.zcode\workspace\default\tss\tsis-deepdive\trail\work\fullrun"
TR = r"C:\Users\Prekzursil\.zcode\workspace\default\tss\tsis-deepdive\trail"

def jload(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

# ---- gold_meta.jsonl (checkpoint ledger)
gm_path = os.path.join(W, "gold_meta.jsonl")
n = 0; bad = 0; keys = Counter(); status_c = Counter(); models = Counter()
ends_nl = True
last = None
with open(gm_path, "rb") as f:
    raw = f.read()
ends_nl = raw.endswith(b"\n")
for line in raw.split(b"\n"):
    if not line.strip():
        continue
    n += 1
    try:
        d = json.loads(line)
        keys.update(d.keys())
        status_c[str(d.get("status") or d.get("ok"))[:20]] += 1
        models.update(d.get("model") and [d.get("model")] or [])
        last = d
    except Exception:
        bad += 1
print("gold_meta.jsonl: lines", n, "parse_fail", bad, "ends_newline", ends_nl)
print("  keys:", dict(keys.most_common(15)))
print("  status/ok values:", dict(status_c.most_common(8)))
print("  models:", dict(models))
print("  last rec:", {k: str(v)[:50] for k, v in list(last.items())[:12]} if last else None)

# gold files on disk vs meta
gaia = glob.glob(os.path.join(W, "gold_outputs", "*", "GAIA", "*.json"))
swe = glob.glob(os.path.join(W, "gold_outputs", "*", "SWE Bench", "*.json"))
print("gold files: GAIA", len(gaia), "SWE", len(swe))

# gold_agreement.json?
for fn in ["gold_agreement.json"]:
    p = os.path.join(W, fn)
    print(fn, "exists:", os.path.exists(p))
    if os.path.exists(p):
        a = jload(p)
        print("  overall:", json.dumps(a.get("overall", {}), default=str)[:400])

# ---- corpus2 label checkpoints
labels = sorted(glob.glob(os.path.join(W, "corpus2_labels", "*.json")))
badl = []; shas = []; dupf = []
seen = set()
for p in labels:
    try:
        rec = jload(p)
    except Exception as e:
        badl.append((os.path.basename(p), str(e)[:60])); continue
    s = rec.get("sha256") or ""
    if s in seen: dupf.append(os.path.basename(p))
    seen.add(s)
    shas.append(s)
canon = jload(os.path.join(TR, "..", "corpus", "canonical_set.json"))["annotation_set"]
canon_shas = {r["sha256"] for r in canon}
orphans = seen - canon_shas
print("\ncorpus2_labels: files", len(labels), "parse_fail", len(badl), "dup_sha", len(dupf),
      "orphan_shas(not in canonical)", len(orphans))
if badl[:3]: print("  bad:", badl[:3])
# privacy: content keys
import re
viol = []
for p in labels:
    t = open(p, encoding="utf-8").read()
    if re.search(r'"(evidence|description|content|input\.value|output\.value|first_user_text|last_assistant_text|path)"\s*:', t):
        viol.append(os.path.basename(p))
print("  privacy key violations:", len(viol), viol[:3])

# ---- corpus2_summary.json
S = jload(os.path.join(W, "corpus2_summary.json"))
print("\ncorpus2_summary.json:", json.dumps(S, default=str)[:900])

# recompute basic counts from labels: labeled ok count, by verdict
verd = Counter()
for p in labels:
    try:
        r = jload(p)
        verd[str(r.get("verdict") or r.get("label") or r.get("ok"))[:20]] += 1
    except Exception:
        pass
print("  label verdict counts:", dict(verd.most_common(8)))

# ---- corpus2_jobs.json (resume state)
J = jload(os.path.join(W, "corpus2_jobs.json"))
if isinstance(J, dict):
    print("\ncorpus2_jobs.json keys:", list(J.keys())[:12])
    for k, v in list(J.items())[:4]:
        print("  ", k, type(v).__name__, (len(v) if isinstance(v, (list, dict)) else v))
elif isinstance(J, list):
    print("\ncorpus2_jobs.json list len", len(J), "sample:", json.dumps(J[0], default=str)[:200] if J else None)

# ---- usage ledgers
for p in glob.glob(os.path.join(W, "usage", "*.jsonl")):
    cnt = 0; badu = 0
    with open(p, "rb") as f:
        for line in f:
            if not line.strip(): continue
            cnt += 1
            try: json.loads(line)
            except Exception: badu += 1
    print("\nusage", os.path.basename(p), "lines", cnt, "parse_fail", badu)

ut = jload(os.path.join(W, "usage_total.json"))
print("usage_total.json:", json.dumps(ut, default=str)[:400])
