import json, os
C = "tsis/deepdive/corpus"
di = json.load(open(os.path.join(C,"dedup_index.json"), encoding="utf-8"))
print("dedup_index top type:", type(di).__name__)
if isinstance(di, dict):
    meta = {k:v for k,v in di.items() if not isinstance(v,(list,dict))}
    print("scalar meta:", meta)
    groups = None; gkey=None
    for k,v in di.items():
        if isinstance(v, dict) and len(v)>1000: groups=v; gkey=k
        elif isinstance(v, list) and len(v)>1000: groups=v; gkey=k
    print("groups container key:", gkey, "type:", type(groups).__name__ if groups is not None else None)
    if isinstance(groups, dict):
        print("n groups:", len(groups))
        k0 = next(iter(groups)); print("sample group:", k0, "->", json.dumps(groups[k0])[:300])
