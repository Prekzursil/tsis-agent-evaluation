import json, os, collections
TR = "tsis/deepdive/trail/work/fullrun"

def audit_jsonl(path, name):
    raw = open(path, "rb").read()
    lines = [l for l in raw.splitlines() if l.strip()]
    recs, bad = [], []
    for i, l in enumerate(lines):
        try:
            recs.append(json.loads(l))
        except Exception as e:
            bad.append((i + 1, str(e)[:60]))
    print(f"{name}: lines={len(lines)} parse_fail={len(bad)} ends_nl={raw.endswith(b'\n') if raw else 'EMPTY'}")
    for b in bad[:5]:
        print("   BAD:", b)
    return recs

# ---- gold checkpoints
gm = audit_jsonl(os.path.join(TR, "gold_meta.jsonl"), "gold_meta.jsonl")
gmnv = audit_jsonl(os.path.join(TR, "gold_meta_nv.jsonl"), "gold_meta_nv.jsonl")
for nm, recs in (("gold_meta", gm), ("gold_meta_nv", gmnv)):
    if not recs:
        continue
    keys = collections.Counter()
    for r in recs:
        keys.update(r.keys())
    print(f"{nm}: keys={dict(keys)}")
    st = collections.Counter(r.get("status", "?") for r in recs)
    print(f"{nm}: statuses={dict(st)}")
    models = collections.Counter(r.get("model", "?") for r in recs)
    print(f"{nm}: models={dict(models)}")
    tid = "target_id" if "target_id" in recs[0] else ("file" if "file" in recs[0] else "task_id")
    ids = collections.Counter(r.get(tid) for r in recs)
    retried = {k: v for k, v in ids.items() if v > 1}
    print(f"{nm}: id_field={tid} unique_ids={len(ids)} retried={len(retried)}")
    # last-wins coherence: last attempt status per id
    last = {}
    for r in recs:
        last[r[tid]] = r
    lastst = collections.Counter(r.get("status") for r in last.values())
    print(f"{nm}: LAST-attempt statuses={dict(lastst)}")

# ---- gold outputs on disk
GO = os.path.join(TR, "gold_outputs")
for sub in sorted(os.listdir(GO)):
    p = os.path.join(GO, sub)
    files = [f for f in os.listdir(p)]
    ok_json = 0
    bad_json = []
    for f in files:
        fp = os.path.join(p, f)
        try:
            json.load(open(fp, encoding="utf-8"))
            ok_json += 1
        except Exception as e:
            bad_json.append((f, str(e)[:50]))
    print(f"gold_outputs/{sub}: files={len(files)} parse_ok={ok_json} parse_fail={len(bad_json)}")
    for b in bad_json[:5]:
        print("   BAD:", b)

# ---- corpus2 label checkpoints (both batches)
for batch in ("corpus2_labels", "corpus2_labels_b"):
    p = os.path.join(TR, batch)
    files = [f for f in os.listdir(p) if f.endswith(".json")]
    badp, dupsha, orphan, errmarker = 0, 0, 0, 0
    shas = set()
    canon = None
    cpath = "tsis/deepdive/corpus/canonical_set.json"
    ann = json.load(open(cpath, encoding="utf-8"))["annotation_set"]
    canon = set(e["sha256"] for e in ann)
    samples = []
    for f in files:
        try:
            d = json.load(open(os.path.join(p, f), encoding="utf-8"))
        except Exception:
            badp += 1
            continue
        sha = d.get("sha256") or f[:-5]
        if sha in shas:
            dupsha += 1
        shas.add(sha)
        if sha not in canon:
            orphan += 1
        if not d.get("ok", True) or d.get("error"):
            errmarker += 1
            if len(samples) < 3:
                samples.append((f, str(d.get("error") or d.get("fail"))[:60]))
    print(f"{batch}: files={len(files)} parse_fail={badp} dup_sha={dupsha} orphan_sha(not in canonical annotation_set)={orphan} not-ok/error={errmarker}")
    for s in samples:
        print("   not-ok:", s)
    print(f"{batch}: unique shas={len(shas)} coverage_of_40798={len(shas)}")

# ---- other checkpoint jsons
for f in ("corpus2_summary.json", "corpus2_jobs.json", "corpus2_census.json",
          "batchb_summary.json", "batchb_agreement.json", "gold_agreement.json",
          "queue_state.json", "FINISH_PIDS.json", "wave3_wait_state.json",
          "usage_ledger_repair.json", "usage_ledger_backfill.json", "usage_sanitize_receipt.json",
          "probe_finish2.json", "probe_fullfinish3.json"):
    p = os.path.join(TR, f)
    if not os.path.exists(p):
        print(f"CKPT {f}: MISSING")
        continue
    try:
        d = json.load(open(p, encoding="utf-8"))
        print(f"CKPT {f}: OK bytes={os.path.getsize(p)}")
    except Exception as e:
        print(f"CKPT {f}: FAIL {e}")

# ---- usage ledgers
for u in os.listdir(os.path.join(TR, "usage")):
    audit_jsonl(os.path.join(TR, "usage", u), f"usage/{u}")
