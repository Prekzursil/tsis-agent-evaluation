# -*- coding: utf-8 -*-
"""mastscope audit part 2: duplicate ids (last-wins rule), ok/fail counts,
aggregates.json vs labels.jsonl, aggregates2.json vs labels_full.jsonl."""
import json, os
from collections import Counter

D = r"C:\Users\Prekzursil\.zcode\workspace\default\tss\tsis-deepdive\mastscope\fullrun"

def load(fn):
    out = []
    with open(os.path.join(D, fn), "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out

# ---- labels.jsonl (v1)
v1 = load("labels.jsonl")
print("labels.jsonl lines:", len(v1))
ok1 = sum(1 for r in v1 if r.get("ok"))
print("  ok:", ok1, "not-ok:", len(v1) - ok1)
fail_reasons = Counter(r.get("fail") for r in v1 if not r.get("ok"))
print("  fail reasons:", dict(fail_reasons))
models = Counter(r.get("model") for r in v1)
print("  models:", dict(models))
tid = [r["trace_id"] for r in v1]
dup_t = {k: v for k, v in Counter(tid).items() if v > 1}
print("  duplicate trace_ids:", len(dup_t), "| extra lines:", sum(dup_t.values()) - len(dup_t))
# last-wins check: for duplicated trace_id, is the LAST line the one with ok=true more often / a resume overwrite?
n_dup_last_ok = 0; n_dup_any_ok = 0
by_tid = {}
for i, r in enumerate(v1):
    by_tid.setdefault(r["trace_id"], []).append(i)
weird = []
for t, idxs in by_tid.items():
    if len(idxs) > 1:
        if v1[idxs[-1]].get("ok"): n_dup_last_ok += 1
        if any(v1[i].get("ok") for i in idxs): n_dup_any_ok += 1
        if len(weird) < 3:
            weird.append((t, [(i, v1[i].get("ok"), v1[i].get("attempts"), str(v1[i].get("fail"))[:30]) for i in idxs]))
print("  dup groups:", len(dup_t), "last-is-ok:", n_dup_last_ok, "any-ok:", n_dup_any_ok)
for w in weird: print("   ", w)
# after last-wins dedup:
last = {}
for r in v1: last[r["trace_id"]] = r
print("  unique trace_ids (last-wins):", len(last), "ok among them:", sum(1 for r in last.values() if r.get("ok")))
# schema sanity: every record has hash-ish? v1 has no sha; has sid; modes dict of 14
MODES = ["1.1","1.2","1.3","1.4","1.5","2.1","2.2","2.3","2.4","2.5","2.6","3.1","3.2","3.3"]
bad_modes = sum(1 for r in v1 if set(r.get("modes", {})) != set(MODES))
print("  records with wrong mode schema:", bad_modes)

# ---- aggregates.json vs labels.jsonl (report-only; both are v1 artifacts)
agg1 = json.load(open(os.path.join(D, "aggregates.json"), encoding="utf-8"))
print("\naggregates.json: n_labeled_ok", agg1.get("n_labeled_ok"), "trace_set_total", agg1.get("trace_set_total"),
      "fail lines", agg1.get("n_label_fail_lines"))
# recompute what aggregates.json would say about the CURRENT labels.jsonl (last-wins):
n_ok_now = sum(1 for r in last.values() if r.get("ok"))
print("current labels.jsonl last-wins ok:", n_ok_now, "-> aggregates.json matches?", agg1.get("n_labeled_ok") == n_ok_now)

# ---- labels_full.jsonl (v2)
v2 = load("labels_full.jsonl")
print("\nlabels_full.jsonl lines:", len(v2))
have_labels = [r for r in v2 if "modes" in r]
no_labels = [r for r in v2 if "modes" not in r]
print("  with labels:", len(have_labels), "without (fail-only):", len(no_labels))
t2 = [r["target_id"] for r in v2]
dup2 = {k: v for k, v in Counter(t2).items() if v > 1}
print("  duplicate target_ids:", len(dup2), "| extra:", sum(dup2.values()) - len(dup2))
last2 = {}
for r in v2: last2[r["target_id"]] = r
ok2 = sum(1 for r in last2.values() if r.get("ok") and "modes" in r)
print("  unique target_ids:", len(last2), "ok labeled (last-wins):", ok2)
bad2 = sum(1 for r in have_labels if set(r.get("modes", {})) != set(MODES))
print("  bad mode schema:", bad2)
models2 = Counter(r.get("model") for r in have_labels)
print("  models:", dict(models2))
mfail = Counter(str(r.get("fail"))[:40] for r in no_labels)
print("  fail-only reasons:", dict(mfail.most_common(6)))

# ---- aggregates2.json vs current labels_full
agg2 = json.load(open(os.path.join(D, "aggregates2.json"), encoding="utf-8"))
print("\naggregates2.json: labels_written", agg2.get("labels_written"), "n_labeled_ok", agg2.get("n_labeled_ok"),
      "pending", agg2.get("pending"), "n_parse_fail", agg2.get("n_parse_fail"))
targets = {}
for line in open(os.path.join(D, "targets.jsonl"), encoding="utf-8"):
    line = line.strip()
    if line:
        t = json.loads(line); targets[t["target_id"]] = t
pending_now = len(targets) - len(set(t2))
print("current pending:", pending_now, "| current ok-labeled:", ok2)
print("aggregates2 stale vs current labels_full.jsonl:",
      (agg2.get("n_labeled_ok") != ok2) or (agg2.get("pending") != pending_now))
