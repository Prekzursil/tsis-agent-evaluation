"""Score the gold-set annotation sweep.

1. Repo-exact: calculate_scores.main() imported VERBATIM from the official
   repo and run on both splits (their behaviour: the 1 broken gold JSON is
   silently skipped -> 147 traces).
2. Full-148: same aggregation semantics, but gold files that fail json.load
   get a deterministic trailing-comma repair.
3. Crosscheck: my aggregator on the SAME 147-file entry set the repo scorer
   processed must reproduce repo-exact numbers within 1e-9 (validates the
   full-148 numbers).
4. Extras the repo does not report: per-split breakdown, macro-F1, impact
   agreement on matched (location, category) pairs, errors-per-trace, traces
   predicted error-free, top category confusions.

Writes work/fullrun/gold_agreement.json + prints the tables.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import Counter

import numpy as np
from scipy.stats import pearsonr
from sklearn.metrics import f1_score

from fullrun_common import LANE, REPO_BENCH, FULL_MODEL
import calculate_scores as CS  # repo module, imported verbatim

WORK = os.path.join(LANE, "work", "fullrun")
GEN_ROOT = os.path.join(WORK, "gold_outputs", FULL_MODEL)
OUT = os.path.join(WORK, "gold_agreement.json")

# 21-label list replicated from calculate_scores.py:115-122 (read this session)
ALL_CATEGORIES = [
    "Language-only", "Tool-related", "Poor Information Retrieval", "Incorrect Memory Usage",
    "Tool Output Misinterpretation", "Incorrect Problem Identification", "Tool Selection Errors",
    "Formatting Errors", "Instruction Non-compliance", "Tool Definition Issues",
    "Environment Setup Errors", "Rate Limiting", "Authentication Errors", "Service Errors",
    "Resource Not Found", "Resource Exhaustion", "Timeout Issues", "Context Handling Failures",
    "Resource Abuse", "Goal Deviation", "Task Orchestration"
]

SPLITS = {
    "GAIA": (os.path.join(REPO_BENCH, "processed_annotations_gaia"),
             os.path.join(GEN_ROOT, "GAIA")),
    "SWE Bench": (os.path.join(REPO_BENCH, "processed_annotations_swe_bench"),
                  os.path.join(GEN_ROOT, "SWE Bench")),
}

# 2026-10-19: GLM coding plan rate-saturated mid-run; the full set is covered
# by the second verified top-tier annotator nvidia/nemotron-3-ultra-550b-a55b.
# Scoring keeps batches single-model: per-model tables + a union batch
# (glm-5.3 preferred where present, ultra fills the rest) with per-file model
# attribution persisted for audit.
NV_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
NV_ROOT = os.path.join(WORK, "gold_outputs", "nvidia-nemotron-3-ultra")
UNION_ROOT = os.path.join(WORK, "gold_outputs", "union-top")
SPLITS_NV = {
    "GAIA": (os.path.join(REPO_BENCH, "processed_annotations_gaia"),
             os.path.join(NV_ROOT, "GAIA")),
    "SWE Bench": (os.path.join(REPO_BENCH, "processed_annotations_swe_bench"),
                  os.path.join(NV_ROOT, "SWE Bench")),
}
UNION_SPLITS = {
    "GAIA": (SPLITS["GAIA"][0], os.path.join(UNION_ROOT, "GAIA")),
    "SWE Bench": (SPLITS["SWE Bench"][0], os.path.join(UNION_ROOT, "SWE Bench")),
}


def build_union():
    """Materialize UNION_ROOT (glm-5.3 output where present, else ultra).
    Idempotent; writes MODEL_MANIFEST.json per split with file->model."""
    manifest = {}
    for split in SPLITS:
        srcs = [("glm-5.3", os.path.join(GEN_ROOT, split)),
                (NV_MODEL, os.path.join(NV_ROOT, split))]
        odir = os.path.join(UNION_ROOT, split)
        os.makedirs(odir, exist_ok=True)
        chosen = {}
        import shutil
        for f in sorted(os.listdir(srcs[0][1])):
            if not f.endswith(".json"):
                continue
            p = os.path.join(srcs[0][1], f)
            if os.path.exists(p) and os.path.getsize(p) > 0:
                shutil.copyfile(p, os.path.join(odir, f))
                chosen[f] = "glm-5.3"
        for f in sorted(os.listdir(srcs[1][1])):
            if not f.endswith(".json") or f in chosen:
                continue
            p = os.path.join(srcs[1][1], f)
            if os.path.exists(p) and os.path.getsize(p) > 0:
                shutil.copyfile(p, os.path.join(odir, f))
                chosen[f] = NV_MODEL
        manifest[split] = chosen
    with open(os.path.join(UNION_ROOT, "MODEL_MANIFEST.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    return manifest


def load_gold_repaired(path: str):
    """json.load with deterministic trailing-comma repair; returns (data, repaired)."""
    txt = open(path, "r", encoding="utf-8").read()
    try:
        return json.loads(txt), False
    except json.JSONDecodeError:
        fixed = re.sub(r",(\s*[}\]])", r"\1", txt)
        return json.loads(fixed), True


def aggregate(entries):
    """Replicates calculate_scores.main() aggregation semantics (lines 124-327)
    over preloaded entries [(gold_dict, gen_dict, fname)]."""
    n = 0
    loc_sum = joint_sum = 0.0
    y_trues, y_preds = [], []
    keys = ("reliability", "security", "instruction_adherence", "plan_optimization",
            "overall")
    gt_sc = {k: [] for k in keys}
    gen_sc = {k: [] for k in keys}
    for gt, gen, fname in entries:
        m = CS.calculate_metrics(gt, gen, ALL_CATEGORIES)
        y_trues.append(m["y_true"])
        y_preds.append(m["y_pred"])
        loc_sum += m["location_accuracy"]
        joint_sum += m["joint_accuracy"]
        g, p = m["gt_scores"], m["gen_scores"]
        if g and p:
            pairs = [("reliability", "reliability_score"), ("security", "security_score"),
                     ("instruction_adherence", "instruction_adherence_score"),
                     ("plan_optimization", "plan_opt_score"), ("overall", "overall")]
            for name, key in pairs:
                if key in g and key in p:
                    a = g.get(key, -1) if g.get(key, -1) else -1
                    b = p.get(key, -1) if p.get(key, -1) else -1
                    try:
                        a = float(a)
                        b = int(b) if (name == "reliability") else float(b)
                    except ValueError:
                        a = float(a)
                        b = -1
                    gt_sc[name].append(a)
                    gen_sc[name].append(b)
        n += 1
    res = {
        "files_processed": n,
        "location_accuracy": loc_sum / n if n else 0.0,
        "joint_accuracy": joint_sum / n if n else 0.0,
        "weighted_f1": 0.0,
        "score_correlations": {},
        "category_metrics": {},
    }
    if not n:
        return res
    yt = np.vstack(y_trues)
    yp = np.vstack(y_preds)
    res["weighted_f1"] = float(f1_score(yt, yp, average="weighted", zero_division=0))
    for i, cat in enumerate(ALL_CATEGORIES):
        tp = int(np.sum((yt[:, i] == 1) & (yp[:, i] == 1)))
        fp = int(np.sum((yt[:, i] == 0) & (yp[:, i] == 1)))
        fn = int(np.sum((yt[:, i] == 1) & (yp[:, i] == 0)))
        sup = int(np.sum(yt[:, i]))
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        res["category_metrics"][cat] = {"precision": prec, "recall": rec, "f1": f1,
                                        "support": sup}
    for k in keys:
        a, b = gt_sc[k], gen_sc[k]
        if len(a) >= 2 and len(set(a)) > 1 and len(set(b)) > 1:
            try:
                corr, p = pearsonr(a, b)
                res["score_correlations"][k] = {"correlation": float(corr),
                                                "p_value": float(p), "n": len(a)}
            except Exception:
                pass
    return res


def collect(gt_dir, gen_dir):
    """Load (gold, generated) pairs. Returns (entries, skipped).
    entries: [(gold, gen, fname, gold_was_repaired)]; skipped records reasons."""
    entries, skipped = [], []
    for gt_path in sorted(glob.glob(os.path.join(gt_dir, "*.json"))):
        base = os.path.basename(gt_path)
        gen_path = os.path.join(gen_dir, base)
        if not os.path.exists(gen_path):
            skipped.append({"file": base, "reason": "no_generated"})
            continue
        try:
            gt, repaired = load_gold_repaired(gt_path)
        except Exception as e:
            skipped.append({"file": base, "reason": f"gold_unparseable:{type(e).__name__}"})
            continue
        try:
            gen = CS.extract_json_from_text(open(gen_path, encoding="utf-8").read())
        except Exception as e:
            skipped.append({"file": base, "reason": f"gen_unparseable:{type(e).__name__}"})
            continue
        entries.append((gt, gen, base, repaired))
    return entries, skipped


def impact_agreement(entries):
    match = agree = 0
    for gt, gen, fname, _ in entries:
        gmap = {}
        for e in gt.get("errors", []):
            gmap[(str(e.get("location", "")),
                  CS.normalize_category(str(e.get("category", "")), ALL_CATEGORIES))] = \
                str(e.get("impact", "")).upper()
        for e in gen.get("errors", []):
            k = (str(e.get("location", "")),
                 CS.normalize_category(str(e.get("category", "")), ALL_CATEGORIES))
            if k in gmap:
                match += 1
                if gmap[k] == str(e.get("impact", "")).upper():
                    agree += 1
    return {"matched_pairs": match, "impact_agree": agree,
            "impact_agreement_rate": (agree / match) if match else None}


def confusion(entries):
    conf = Counter()
    for gt, gen, fname, _ in entries:
        gset = {CS.normalize_category(str(e.get("category", "")), ALL_CATEGORIES)
                for e in gt.get("errors", []) if e.get("category")}
        pset = {CS.normalize_category(str(e.get("category", "")), ALL_CATEGORIES)
                for e in gen.get("errors", []) if e.get("category")}
        for p in pset - gset:
            conf[("FP", p)] += 1
        for g in gset - pset:
            conf[("FN", g)] += 1
    return {f"{k[0]}:{k[1]}": v for k, v in conf.most_common(20)}


def main():
    manifest = build_union()
    glm_counts = {s: sum(1 for m in manifest[s].values() if m == "glm-5.3")
                  for s in manifest}
    nv_counts = {s: sum(1 for m in manifest[s].values() if m == NV_MODEL)
                 for s in manifest}
    result = {"generated_root": UNION_ROOT,
              "model_attribution": {"glm-5.3": glm_counts, NV_MODEL: nv_counts},
              "repo_exact": {}, "splits": {}, "overall": None,
              "crosscheck": {}, "extras": {}, "by_model": {}}

    # 1. repo-exact runs (their code, their dirs, their skip behaviour) on the
    #    UNION dir (single per-file annotator; attribution above)
    UNION_SPLITS = {
        "GAIA": (SPLITS["GAIA"][0], os.path.join(UNION_ROOT, "GAIA")),
        "SWE Bench": (SPLITS["SWE Bench"][0], os.path.join(UNION_ROOT, "SWE Bench")),
    }
    for split, (gt_dir, gen_dir) in UNION_SPLITS.items():
        cs = CS.main(ground_truth_dir=gt_dir, generated_dir=gen_dir)
        result["repo_exact"][split] = {
            "weighted_f1": float(cs["weighted_f1"]),
            "location_accuracy": float(cs["location_accuracy"]),
            "joint_accuracy": float(cs["joint_accuracy"]),
            "category_metrics": cs["category_metrics"],
            "score_correlations": cs["score_correlations"],
        }

    # 2. per-model batches (single-model each) + union aggregate
    def score_dirs(splits_map):
        all_entries = []
        per_split = {}
        skipped = []
        for split, (gt_dir, gen_dir) in splits_map.items():
            entries, sk = collect(gt_dir, gen_dir)
            per_split[split] = aggregate([(a, b, c) for a, b, c, _ in entries])
            skipped += [{"split": split, **s} for s in sk]
            all_entries += entries
        return {"splits": per_split, "overall": aggregate(
                    [(a, b, c) for a, b, c, _ in all_entries]),
                "skipped": skipped, "entries": all_entries}

    union = score_dirs(UNION_SPLITS)
    glm_only = score_dirs(SPLITS)
    nv_only = score_dirs(SPLITS_NV)
    result["splits"] = union["splits"]
    result["overall"] = union["overall"]
    result["skipped_files"] = union["skipped"]
    result["by_model"] = {
        "glm-5.3": {"splits": glm_only["splits"], "overall": glm_only["overall"],
                    "skipped": glm_only["skipped"]},
        NV_MODEL: {"splits": nv_only["splits"], "overall": nv_only["overall"],
                   "skipped": nv_only["skipped"]},
    }
    all_entries = union["entries"]

    # 3. crosscheck: my aggregator vs repo-exact on the SAME valid-gold entries
    diffs = []
    for split, (gt_dir, gen_dir) in UNION_SPLITS.items():
        entries, _ = collect(gt_dir, gen_dir)
        valid = [(a, b, c) for a, b, c, rep in entries if not rep]
        mine = aggregate(valid)
        repo = result["repo_exact"][split]
        for k in ("weighted_f1", "location_accuracy", "joint_accuracy"):
            if abs(mine[k] - repo[k]) > 1e-9:
                diffs.append(f"{split}.{k}: mine={mine[k]!r} repo={repo[k]!r}")
        for cat, cm in repo["category_metrics"].items():
            if abs(mine["category_metrics"][cat]["f1"] - cm["f1"]) > 1e-9:
                diffs.append(f"{split}.cat.{cat}.f1 mine={mine['category_metrics'][cat]['f1']}"
                             f" repo={cm['f1']}")
    result["crosscheck"] = {"bit_exact_within_1e-9": len(diffs) == 0, "diffs": diffs}

    # 4. extras (union batch)
    result["extras"]["impact"] = impact_agreement(all_entries)
    result["extras"]["confusion_top20"] = confusion(all_entries)
    result["extras"]["traces_gold_no_errors"] = \
        sum(1 for e in all_entries if len(e[0].get("errors", [])) == 0)
    result["extras"]["traces_pred_no_errors"] = \
        sum(1 for e in all_entries if len(e[1].get("errors", []) or []) == 0)
    gt_counts = [len(e[0].get("errors", [])) for e in all_entries]
    gen_counts = [len(e[1].get("errors", []) or []) for e in all_entries]
    result["extras"]["mean_errors_per_trace"] = {
        "gold": (sum(gt_counts) / len(gt_counts)) if gt_counts else None,
        "pred": (sum(gen_counts) / len(gen_counts)) if gen_counts else None}
    sup_f1 = [v["f1"] for v in result["overall"]["category_metrics"].values()
              if v["support"] > 0]
    result["extras"]["macro_f1_supported"] = (sum(sup_f1) / len(sup_f1)) if sup_f1 else None
    per_file = []
    for gt, gen, fname, _ in all_entries:
        m = CS.calculate_metrics(gt, gen, ALL_CATEGORIES)
        per_file.append({"file": fname,
                         "model": next((mm for s in manifest for
                                        ff, mm in manifest[s].items() if ff == fname), "?"),
                         "location_accuracy": m["location_accuracy"],
                         "joint_accuracy": m["joint_accuracy"],
                         "n_gt_errors": len(gt.get("errors", [])),
                         "n_gen_errors": len(gen.get("errors", []) or [])})
    result["per_file"] = per_file

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print("wrote", OUT)
    o = result["overall"]
    print(f"UNION-148: files={o['files_processed']} wF1={o['weighted_f1']:.4f} "
          f"loc={o['location_accuracy']:.4f} joint={o['joint_accuracy']:.4f}")
    print("attribution:", result["model_attribution"])
    for name, bm in result["by_model"].items():
        bo = bm["overall"]
        print(f"  {name}: files={bo['files_processed']} wF1={bo['weighted_f1']:.4f}")
    print("crosscheck:", result["crosscheck"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
