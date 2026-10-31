# -*- coding: utf-8 -*-
import json, os
d = r"C:\Users\Prekzursil\.zcode\workspace\default\tss\tsis-deepdive\mastscope\fullrun"
with open(os.path.join(d, "labels.jsonl"), "r", encoding="utf-8") as f:
    first = f.readline()
print("labels.jsonl first line:", first[:500])
print()
for fn in ["aggregates.json", "aggregates2.json", "sweep_status.json", "sweep_status2.json",
           "targets_summary.json", "crosscheck_agreement.json"]:
    with open(os.path.join(d, fn), "r", encoding="utf-8") as f:
        txt = f.read()
    try:
        j = json.loads(txt)
        print("==", fn, "OK")
        print(json.dumps(j, indent=0, default=str)[:1500])
    except Exception as e:
        print("==", fn, "PARSE FAIL:", e, "| tail:", txt[-300:])
    print()
