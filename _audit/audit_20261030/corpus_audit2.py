import json, os
C = "tsis/deepdive/corpus"
cs = json.load(open(os.path.join(C,"canonical_set.json"), encoding="utf-8"))
print("canonical keys:", list(cs.keys()))
print("unique_files:", cs.get("unique_files"))
ann = cs.get("annotation_set")
print("annotation_set type:", type(ann).__name__)
if isinstance(ann, dict):
    print("annotation_set size:", len(ann))
    k0 = next(iter(ann)); print("sample entry:", k0, "->", json.dumps(ann[k0])[:200])
    print("generated:", cs.get("generated"))
# CORPUS.md claims
import re
md = open(os.path.join(C,"CORPUS.md"), encoding="utf-8").read()
for m in re.finditer(r"(?i)^(.*41,?87\d.*)$", md, re.M):
    print("CORPUS.md:", m.group(1).strip()[:160])
for m in re.finditer(r"(?i)^(.*124,?32\d.*)$", md, re.M):
    print("CORPUS.md:", m.group(1).strip()[:160])
