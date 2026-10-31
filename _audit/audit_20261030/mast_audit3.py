import json, os, collections
M = "tsis/deepdive/mastscope/fullrun"
a1 = json.load(open(os.path.join(M,"aggregates.json"), encoding="utf-8"))
a2 = json.load(open(os.path.join(M,"aggregates2.json"), encoding="utf-8"))
print("aggregates.json keys:", sorted(a1.keys()))
print("aggregates2.json keys:", sorted(a2.keys()))
for name, a in (("v1",a1),("v2",a2)):
    scal = {k:v for k,v in a.items() if not isinstance(v,(dict,list))}
    print(f"{name} scalars:", scal)
lab = [json.loads(l) for l in open(os.path.join(M,"labels.jsonl"), encoding="utf-8")]
lab2 = [json.loads(l) for l in open(os.path.join(M,"labels_full.jsonl"), encoding="utf-8")]
ok1 = sum(1 for r in lab if r.get("ok")); ok2 = sum(1 for r in lab2 if r.get("ok"))
print(f"actual: v1 ok={ok1}  v2 ok={ok2}  v2 total={len(lab2)} v2 fail={sum(1 for r in lab2 if r.get('fail'))}")
# per-mode prevalence recompute for v2
modeprev = collections.Counter(); n=0
for r in lab2:
    if r.get("ok"):
        n+=1
        for m,v in r["modes"].items():
            if v: modeprev[m]+=1
print("v2 recompute n_ok:", n, "top modes:", modeprev.most_common(5))
# find matching structure inside aggregates2
for k,v in a2.items():
    if isinstance(v,dict) and any(str(ok2)==str(x) or str(len(lab2))==str(x) for x in _flat(v)[:0]):
        pass
def findnum(obj, targets, path=""):
    out=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            out += findnum(v, targets, path+"/"+str(k))
    elif isinstance(obj,(int,float)) and obj in targets:
        out.append((path,obj))
    return out
hits = findnum(a2, {ok2, len(lab2), sum(1 for r in lab2 if r.get('fail'))})
print("aggregates2 fields equal to actual counts:", hits[:10])
