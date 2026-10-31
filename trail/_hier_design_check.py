"""Design checks for the hierarchical judge (read-only analysis of gold)."""
import json, glob, re
from collections import Counter


def load_gold(p):
    txt = open(p, encoding="utf-8").read()
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return json.loads(re.sub(r",(\s*[}\]])", r"\1", txt))


dup_cat = pair_dup = traces = 0
multi_loc_cat = 0  # traces where one category sits on >1 DISTINCT location
for gd in ["repo/benchmarking/processed_annotations_gaia",
           "repo/benchmarking/processed_annotations_swe_bench"]:
    for f in sorted(glob.glob(gd + "/*.json")):
        g = load_gold(f)
        traces += 1
        errs = g.get("errors", [])
        cc = Counter(e.get("category", "") for e in errs)
        if any(v > 1 for v in cc.values()):
            dup_cat += 1
        pc = Counter((e.get("location", ""), e.get("category", "")) for e in errs)
        if any(v > 1 for v in pc.values()):
            pair_dup += 1
        cl = {}
        for e in errs:
            cl.setdefault(e.get("category", ""), set()).add(e.get("location", ""))
        if any(len(v) > 1 for v in cl.values()):
            multi_loc_cat += 1

print("traces", traces,
      "| traces w/ same category >1 entries:", dup_cat,
      "| exact (loc,cat) pair dups:", pair_dup,
      "| traces w/ same category on >1 DISTINCT locations:", multi_loc_cat)
