import json, os, collections
M = "tsis/deepdive/mastscope/fullrun"

def audit_jsonl(name):
    p = os.path.join(M, name)
    raw = open(p, "rb").read()
    lines = raw.splitlines()
    n = 0; bad = []
    recs = []
    for i, ln in enumerate(lines):
        if not ln.strip(): continue
        n += 1
        try:
            recs.append(json.loads(ln))
        except Exception as e:
            bad.append((i+1, str(e)[:80]))
    # py3.10: a backslash is not allowed inside an f-string expression part
    # (PEP 701 lifted that only in 3.12) - hoist it out, identical output.
    ends_nl = raw.endswith(b'\n') if raw else 'EMPTY'
    print(f"{name}: bytes={len(raw)} lines={n} parse_fail={len(bad)} ends_nl={ends_nl}")
    for b in bad[:5]: print("   BAD LINE:", b)
    return recs

# ---- labels.jsonl (v1)
lab = audit_jsonl("labels.jsonl")
print("expected 16,253 lines:", len(lab)==16253)
keyset = collections.Counter()
for r in lab: keyset.update(r.keys())
print("labels.jsonl key freq:", dict(keyset))
models = collections.Counter(r.get("model") or r.get("model_id") or "?" for r in lab)
print("models:", dict(models))
# id field
idfield = None
for k in ("trace_id","target_id","hash","sha256"):
    if k in lab[0]: idfield = k; break
print("id field:", idfield)
ids = [r[idfield] for r in lab]
dup = [k for k,v in collections.Counter(ids).items() if v>1]
print(f"duplicate ids: {len(dup)} (sample: {dup[:3]})")
st = collections.Counter(r.get("status","?") for r in lab)
print("statuses:", dict(st))
# mode schema on labeled records
MODES = None
sample_lab = [r for r in lab if r.get("labels")][:1]
if sample_lab: print("sample labels keys:", sorted(sample_lab[0]["labels"].keys()) if isinstance(sample_lab[0]["labels"], dict) else type(sample_lab[0]["labels"]).__name__)
nolabels = sum(1 for r in lab if not r.get("labels"))
print("records without labels:", nolabels)

print("="*60)
# ---- labels_full.jsonl (v2)
lab2 = audit_jsonl("labels_full.jsonl")
keyset2 = collections.Counter()
for r in lab2: keyset2.update(r.keys())
print("labels_full.jsonl key freq:", dict(keyset2))
idfield2 = "target_id" if "target_id" in lab2[0] else ("trace_id" if "trace_id" in lab2[0] else "?")
print("id field:", idfield2)
ids2 = [r[idfield2] for r in lab2]
dup2 = [k for k,v in collections.Counter(ids2).items() if v>1]
print(f"duplicate ids: {len(dup2)}")
st2 = collections.Counter(r.get("status","?") for r in lab2)
print("statuses:", dict(st2))
mig = sum(1 for r in lab2 if r.get("migrated_from"))
print("migrated_from count:", mig)
nolab2 = sum(1 for r in lab2 if not r.get("labels"))
print("records without labels:", nolab2)
# duplicates: check last-wins semantics if any
if dup2:
    pos = collections.defaultdict(list)
    for i,r in enumerate(lab2): pos[r[idfield2]].append(i)
    for d in dup2[:3]:
        idxs = pos[d]
        print(f"  dup {d}: lines {idxs}, statuses {[lab2[i].get('status') for i in idxs]}")
