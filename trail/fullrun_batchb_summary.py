"""Batch B aggregation + cross-model agreement (glm vs grok, same hash).

Batch B = the single-model grok-4.7 (effort low) pass over ALL canonical
targets, checkpoints in work/fullrun/corpus2_labels_b/ (fullrun_batchb_grok.py).
Batch A = the wave1-3 multi-model set in work/fullrun/corpus2_labels/.

Outputs:
  work/fullrun/batchb_summary.json    - batch B distribution (same fields the
                                        RESULTS corpus table uses)
  work/fullrun/batchb_agreement.json  - cross-model agreement on the same-hash
                                        overlap between batch A models and the
                                        grok-4.7 batch-B label:
    * headline: mean per-trace Jaccard of the normalized error-category SETS,
      and exact-set-match rate (both traces OK-annotated)
    * error-free agreement (both zero-error vs mixed)
    * per-class Cohen's kappa (presence/absence, top classes by union support)
    * impact-mix shares per side + L1 distance (label level)
  Offline; no API. Recomputable: python fullrun_batchb_summary.py
"""
from __future__ import annotations

import glob
import json
import os
from collections import Counter

from fullrun_summarize2 import norm_cat

LANE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(LANE, "work", "fullrun")
LABELS_A = os.path.join(WORK, "corpus2_labels")
LABELS_B = os.path.join(WORK, "corpus2_labels_b")
OUT_SUM = os.path.join(WORK, "batchb_summary.json")
OUT_AGR = os.path.join(WORK, "batchb_agreement.json")


def load_labels(d):
    out = {}
    for p in glob.glob(os.path.join(d, "*.json")):
        try:
            rec = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        sha = rec.get("sha256")
        if sha:
            out[sha] = rec
    return out


def cats_of(rec):
    return {norm_cat(e.get("category")) for e in (rec.get("errors") or [])}


def cohen_kappa(a, b):
    """a, b: parallel boolean lists."""
    n = len(a)
    if not n:
        return None
    po = sum(1 for x, y in zip(a, b) if x == y) / n
    pa = sum(a) / n
    pb = sum(b) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    if pe >= 1.0:
        return None
    return (po - pe) / (1 - pe)


def agreement(b_recs: dict, a_recs: dict, a_model: str):
    """All same-hash OK-vs-OK pairs where batch A's model == a_model."""
    pairs = []
    for sha, rb in b_recs.items():
        if rb.get("status") != "ok":
            continue
        ra = a_recs.get(sha)
        if ra and ra.get("status") == "ok" and ra.get("model") == a_model:
            pairs.append((ra, rb))
    if not pairs:
        return {"a_model": a_model, "overlap_ok_pairs": 0}
    jaccs, exact, both_zero, one_zero = [], 0, 0, 0
    imp_a, imp_b = Counter(), Counter()
    per_class = {}  # class -> [a_present, b_present]
    for ra, rb in pairs:
        ca, cb = cats_of(ra), cats_of(rb)
        u = ca | cb
        j = len(ca & cb) / len(u) if u else 1.0
        jaccs.append(j)
        if ca == cb:
            exact += 1
        if not ca and not cb:
            both_zero += 1
        elif not ca or not cb:
            one_zero += 1
        for e in (ra.get("errors") or []):
            imp_a[str(e.get("impact", "")).upper() or "(blank)"] += 1
        for e in (rb.get("errors") or []):
            imp_b[str(e.get("impact", "")).upper() or "(blank)"] += 1
        for c in u:
            per_class.setdefault(c, ([], []))
            per_class[c][0].append(c in ca)
            per_class[c][1].append(c in cb)
    kappas = {}
    for c, (av, bv) in per_class.items():
        if sum(av) + sum(bv) >= 20:  # classes with meaningful union support
            k = cohen_kappa(av, bv)
            if k is not None:
                kappas[c] = {"kappa": round(k, 4),
                             "a_support": sum(av), "b_support": sum(bv)}
    ta = sum(imp_a.values()) or 1
    tb = sum(imp_b.values()) or 1
    imp_share_a = {k: v / ta for k, v in imp_a.items()}
    imp_share_b = {k: v / tb for k, v in imp_b.items()}
    l1_imp = sum(abs(imp_share_a.get(k, 0) - imp_share_b.get(k, 0))
                 for k in set(imp_share_a) | set(imp_share_b))
    return {
        "a_model": a_model, "b_model": "grok-4.7",
        "overlap_ok_pairs": len(pairs),
        "mean_jaccard_category_set": round(sum(jaccs) / len(jaccs), 4),
        "exact_category_set_match_rate": round(exact / len(pairs), 4),
        "both_error_free": both_zero, "exactly_one_error_free": one_zero,
        "mean_errors_per_trace_a": round(
            sum(len(r.get("errors") or []) for r, _ in pairs) / len(pairs), 3),
        "mean_errors_per_trace_b": round(
            sum(len(r.get("errors") or []) for _, r in pairs) / len(pairs), 3),
        "impact_mix_a": {k: round(v, 4) for k, v in sorted(imp_share_a.items())},
        "impact_mix_b": {k: round(v, 4) for k, v in sorted(imp_share_b.items())},
        "impact_share_L1": round(l1_imp, 4),
        "per_class_cohen_kappa": dict(sorted(
            kappas.items(), key=lambda kv: -(kv[1]["a_support"] + kv[1]["b_support"]))),
    }


def main():
    b = load_labels(LABELS_B)
    status = Counter()
    per_batch = Counter()
    cat = Counter()
    cat_traces = Counter()
    impact = Counter()
    errors_per_trace = []
    n_with_errors = 0
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
    ok_shas = set()
    for rec in b.values():
        status[rec.get("status", "?")] += 1
        per_batch[rec.get("batch_b", "?")] += 1
        mdl = rec.get("model", "?")
        per_batch[f"model:{mdl}"] += 1
        trace_cats = set()
        for e in (rec.get("errors") or []):
            cat[norm_cat(e.get("category"))] += 1
            trace_cats.add(norm_cat(e.get("category")))
            impact[str(e.get("impact", "")).upper() or "(blank)"] += 1
        if rec.get("status") == "ok":
            ok_shas.add(rec.get("sha256"))
            for c in trace_cats:
                cat_traces[c] += 1
            errors_per_trace.append(len(rec.get("errors") or []))
            if rec.get("errors"):
                n_with_errors += 1
        u = rec.get("usage") or {}
        usage["prompt_tokens"] += u.get("prompt_tokens", 0) or 0
        usage["completion_tokens"] += u.get("completion_tokens", 0) or 0
        if u:
            usage["calls"] += 1
    summary = {
        "batch": "B", "model": "grok-4.7 (reasoning_effort=low)",
        "labels_dir": "work/fullrun/corpus2_labels_b",
        "files_checkpointed": len(b),
        "status": dict(status.most_common()),
        "batch_provenance": {k: v for k, v in per_batch.most_common()
                             if not k.startswith("model:")},
        "models_present": {k.split(":", 1)[1]: v for k, v in per_batch.items()
                           if k.startswith("model:")},
        "annotated_ok": status.get("ok", 0),
        "error_labels_total": sum(cat.values()),
        "category_counts": {k: [v, cat_traces.get(k, 0)] for k, v in
                            cat.most_common()},
        "impact_counts": dict(impact.most_common()),
        "mean_errors_per_annotated": (round(sum(errors_per_trace)
                                            / max(len(errors_per_trace), 1), 4)),
        "annotated_with_ge1_error": n_with_errors,
        "usage": usage,
    }
    with open(OUT_SUM, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print(f"batch B summary: files={summary['files_checkpointed']} "
          f"ok={summary['annotated_ok']} models={summary['models_present']}")

    a = load_labels(LABELS_A)
    a_models = Counter(r.get("model") for r in a.values() if r.get("status") == "ok")
    agr = {"b_model": "grok-4.7",
           "batch_a_ok_by_model": dict(a_models.most_common()),
           "pairs": {}}
    for m in ("glm-5.3-flash", "nvidia/nemotron-3-ultra-550b-a55b",
              "nvidia/nemotron-3-ultra-550b-a55b:free"):
        agr["pairs"][m] = agreement(b, a, m)
    with open(OUT_AGR, "w", encoding="utf-8") as f:
        json.dump(agr, f, indent=1)
    for m, p in agr["pairs"].items():
        if p.get("overlap_ok_pairs"):
            print(f"agreement {m} vs grok-4.7: n={p['overlap_ok_pairs']} "
                  f"meanJaccard={p['mean_jaccard_category_set']} "
                  f"exact={p['exact_category_set_match_rate']}")


if __name__ == "__main__":
    main()
