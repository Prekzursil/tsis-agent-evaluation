"""Score the HIERARCHICAL judge outputs with the SAME scorer as the flat gold run.

Reuses fullrun_score verbatim functions:
  - collect()        : (gold, generated) pair loading with gold trailing-comma
                       repair + repo extract_json_from_text on the generated side
  - aggregate()      : replicates repo calculate_scores.main() aggregation
                       (crosschecked bit-exact <=1e-9 vs repo-exact in the flat
                       run, RESULTS.md line ~40)
and additionally runs the REPO scorer itself (calculate_scores.main imported
verbatim) on the same dirs for repo-exact numbers.

Flat-vs-hierarchical table data comes from work/fullrun/gold_agreement.json
(the flat run's own artifact). Writes work/fullrun/hier_agreement.json.
"""
from __future__ import annotations

import json
import os
import sys

from fullrun_common import LANE, REPO_BENCH
import calculate_scores as CS            # repo module, verbatim
import fullrun_score as FS               # same scorer functions as flat run

WORK = os.path.join(LANE, "work", "fullrun")
TAG = "grok-4.7-xhigh"
CTL_TAG = "grok-4.7-xhigh-flat"
HIER_ROOT = os.path.join(WORK, "hier_outputs", TAG, "final")
CTL_ROOT = os.path.join(WORK, "hier_outputs", CTL_TAG)
FLAT_AGREEMENT = os.path.join(WORK, "gold_agreement.json")
OUT = os.path.join(WORK, "hier_agreement.json")

HIER_SPLITS = {
    "GAIA": (os.path.join(REPO_BENCH, "processed_annotations_gaia"),
             os.path.join(HIER_ROOT, "GAIA")),
    "SWE Bench": (os.path.join(REPO_BENCH, "processed_annotations_swe_bench"),
                  os.path.join(HIER_ROOT, "SWE Bench")),
}
CTL_SPLITS = {
    "GAIA": (HIER_SPLITS["GAIA"][0], os.path.join(CTL_ROOT, "GAIA")),
    "SWE Bench": (HIER_SPLITS["SWE Bench"][0], os.path.join(CTL_ROOT, "SWE Bench")),
}


def main():
    result = {"tag": TAG, "splits": {}, "overall": None, "repo_exact": {},
              "skipped": [], "flat": None, "fallbacks": 0, "extras": {}}
    all_entries = []
    for split, (gt_dir, gen_dir) in HIER_SPLITS.items():
        entries, sk = FS.collect(gt_dir, gen_dir)
        result["splits"][split] = FS.aggregate([(a, b, c) for a, b, c, _ in entries])
        result["skipped"] += [{"split": split, **s} for s in sk]
        all_entries += entries
        # repo-exact: their scorer, their dirs, their skip behaviour
        cs = CS.main(ground_truth_dir=gt_dir, generated_dir=gen_dir)
        result["repo_exact"][split] = {
            "weighted_f1": float(cs["weighted_f1"]),
            "location_accuracy": float(cs["location_accuracy"]),
            "joint_accuracy": float(cs["joint_accuracy"]),
            "files": None,
        }
    result["overall"] = FS.aggregate([(a, b, c) for a, b, c, _ in all_entries])

    # flat-control (same model+effort, paper flat prompt, flat capping ladder)
    if all(os.path.isdir(d) for _, d in CTL_SPLITS.values()):
        ctl_entries = []
        ctl_splits = {}
        for split, (gt_dir, gen_dir) in CTL_SPLITS.items():
            entries, sk = FS.collect(gt_dir, gen_dir)
            ctl_splits[split] = FS.aggregate([(a, b, c) for a, b, c, _ in entries])
            ctl_entries += entries
        result["flatctl"] = {"tag": CTL_TAG, "splits": ctl_splits,
                             "overall": FS.aggregate([(a, b, c) for a, b, c, _ in ctl_entries])}

    # fallback count (reconciliation call failed -> mechanical verdict written)
    n_fb = 0
    for split, (_, gen_dir) in HIER_SPLITS.items():
        for f in os.listdir(gen_dir):
            try:
                obj = json.loads(open(os.path.join(gen_dir, f), encoding="utf-8").read())
            except Exception:
                continue
            if "_fallback" in obj:
                n_fb += 1
    result["fallbacks"] = n_fb

    # flat-run comparison numbers
    if os.path.exists(FLAT_AGREEMENT):
        flat = json.load(open(FLAT_AGREEMENT, encoding="utf-8"))
        result["flat"] = {
            "overall": flat["overall"], "splits": flat["splits"],
            "repo_exact": flat["repo_exact"],
        }

    # extras, same definitions as the flat run
    ex = result["extras"]
    ex["impact"] = FS.impact_agreement(all_entries)
    ex["confusion_top20"] = FS.confusion(all_entries)
    ex["traces_gold_no_errors"] = sum(1 for e in all_entries
                                      if len(e[0].get("errors", [])) == 0)
    ex["traces_pred_no_errors"] = sum(1 for e in all_entries
                                      if len(e[1].get("errors", []) or []) == 0)
    gt_counts = [len(e[0].get("errors", [])) for e in all_entries]
    gen_counts = [len(e[1].get("errors", []) or []) for e in all_entries]
    ex["mean_errors_per_trace"] = {"gold": sum(gt_counts) / len(gt_counts) if gt_counts else None,
                                   "pred": sum(gen_counts) / len(gen_counts) if gen_counts else None}
    sup_f1 = [v["f1"] for v in result["overall"]["category_metrics"].values()
              if v["support"] > 0]
    ex["macro_f1_supported"] = sum(sup_f1) / len(sup_f1) if sup_f1 else None

    per_file = []
    for gt, gen, fname, _ in all_entries:
        m = CS.calculate_metrics(gt, gen, FS.ALL_CATEGORIES)
        per_file.append({"file": fname, "location_accuracy": m["location_accuracy"],
                         "joint_accuracy": m["joint_accuracy"],
                         "n_gt_errors": len(gt.get("errors", [])),
                         "n_gen_errors": len(gen.get("errors", []) or [])})
    result["per_file"] = per_file

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print("wrote", OUT)
    o = result["overall"]
    print(f"HIER-148: files={o['files_processed']} wF1={o['weighted_f1']:.4f} "
          f"loc={o['location_accuracy']:.4f} joint={o['joint_accuracy']:.4f} "
          f"fallbacks={n_fb}")
    if result["flat"]:
        fo = result["flat"]["overall"]
        print(f"FLAT-148: files={fo['files_processed']} wF1={fo['weighted_f1']:.4f} "
              f"loc={fo['location_accuracy']:.4f} joint={fo['joint_accuracy']:.4f}")
    if "flatctl" in result:
        co = result["flatctl"]["overall"]
        print(f"FLATCTL-148 (grok-4.7 xhigh, flat prompt): files={co['files_processed']} "
              f"wF1={co['weighted_f1']:.4f} loc={co['location_accuracy']:.4f} "
              f"joint={co['joint_accuracy']:.4f}")
    for split in HIER_SPLITS:
        s = result["splits"][split]
        r = result["repo_exact"][split]
        print(f"  {split}: wF1={s['weighted_f1']:.4f} loc={s['location_accuracy']:.4f} "
              f"joint={s['joint_accuracy']:.4f} | repo-exact "
              f"wF1={r['weighted_f1']:.4f} loc={r['location_accuracy']:.4f} "
              f"joint={r['joint_accuracy']:.4f}")
    print("skipped:", result["skipped"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
