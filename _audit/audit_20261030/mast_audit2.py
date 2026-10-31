import json, os, collections
M = "tsis/deepdive/mastscope/fullrun"
lab = [json.loads(l) for l in open(os.path.join(M,"labels.jsonl"), encoding="utf-8")]
ok1 = sum(1 for r in lab if r.get("ok")); pf1 = sum(1 for r in lab if r.get("fail"))
print(f"v1 labels.jsonl: ok={ok1} fail={pf1} total={len(lab)}")
MODE_KEYS=None; bad=0
for r in lab:
    if r.get("ok") and isinstance(r.get("modes"), dict):
        ks=frozenset(r["modes"].keys())
        if MODE_KEYS is None: MODE_KEYS=ks
        elif ks!=MODE_KEYS: bad+=1
print("v1 mode keys:", sorted(MODE_KEYS) if MODE_KEYS else None, "deviating:", bad)
print("v1 ok-but-no-modes:", sum(1 for r in lab if r.get('ok') and not isinstance(r.get('modes'),dict)))
print("v1 fail sample:", json.dumps([r for r in lab if r.get('fail')][0])[:300])

lab2 = [json.loads(l) for l in open(os.path.join(M,"labels_full.jsonl"), encoding="utf-8")]
ok2 = sum(1 for r in lab2 if r.get("ok")); fail2 = sum(1 for r in lab2 if r.get("fail"))
print(f"v2 labels_full.jsonl: ok={ok2} fail={fail2} other={len(lab2)-ok2-fail2} total={len(lab2)}")
MODE2=None; bad2=0
for r in lab2:
    if r.get("ok") and isinstance(r.get("modes"), dict):
        ks=frozenset(r["modes"].keys())
        if MODE2 is None: MODE2=ks
        elif ks!=MODE2: bad2+=1
print("v2 mode keys:", sorted(MODE2) if MODE2 else None, "deviating:", bad2)
print("v2 ok-but-no-modes:", sum(1 for r in lab2 if r.get('ok') and not isinstance(r.get('modes'),dict)))
nonok=[r for r in lab2 if not r.get("ok")]
print("v2 non-ok count:", len(nonok))
if nonok: print("v2 non-ok sample:", json.dumps(nonok[0])[:300])
failtypes = collections.Counter(type(r.get("fail")).__name__ + ":" + str(r.get("fail"))[:60] for r in lab2 if r.get("fail"))
print("v2 fail reasons:", dict(list(failtypes.items())[:6]))

tg=[json.loads(l) for l in open(os.path.join(M,"targets.jsonl"), encoding="utf-8")]
print(f"targets.jsonl lines={len(tg)} keys={sorted(tg[0].keys())[:10]}")
tids=set(r["target_id"] for r in tg); lids=set(r["target_id"] for r in lab2)
print("labels==targets ids:", lids==tids, "targets-labels:", len(tids-lids), "labels-targets:", len(lids-tids))
# sha256 linkage label->target
tsha = {r["target_id"]: r.get("sha256") for r in tg}
mismatch = sum(1 for r in lab2 if tsha.get(r["target_id"]) and r.get("sha256") and tsha[r["target_id"]] != r["sha256"])
print("sha mismatches label vs target:", mismatch)
