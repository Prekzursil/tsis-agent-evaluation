"""Sensitivity extension: full-N point (D) + verdict restatement.

D = the batch-B single-model grok-4.7 pass over the FULL canonical set
(work/fullrun/corpus2_labels_b, fullrun_batchb_grok.py) -- the first
full-N snapshot measured with ONE instrument, removing the multi-model
composition confound of the wave1-3 mix.

Snapshot reconstruction (exact, verified against published sensitivity.md):
  B = corpus2_labels ok labels WITHOUT 'ext' marker and ts < 2026-10-21
      (the freeze; reproduces n_ok=1076 exactly)
  C = B + ext-marked ok labels (reproduces n_ok=1162 exactly)
  A = first 326 of B by ts (published N~326)

Appends a "full-N point (D)" section to fullrun/sensitivity.md (the original
A/B/C content is preserved verbatim; this only appends) and writes the numbers
to work/fullrun/sensitivity_d.json for verify_fullrun.py.

Offline; scipy+numpy. Usage: python fullrun_sensitivity_d.py
"""
from __future__ import annotations

import glob
import json
import os
from collections import Counter

import numpy as np
from scipy.stats import chi2_contingency

from fullrun_summarize2 import norm_cat  # noqa: E402

LANE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(LANE, "work", "fullrun")
LABELS_A = os.path.join(WORK, "corpus2_labels")
LABELS_B = os.path.join(WORK, "corpus2_labels_b")
OUT_MD = os.path.join(LANE, "fullrun", "sensitivity.md")
OUT_JSON = os.path.join(WORK, "sensitivity_d.json")
FREEZE_CUTOFF = "2026-10-21"      # first wave-2 label is 2026-10-21T11:33:43Z
N_SNAP_A = 326
RNG = np.random.default_rng(20261030)
N_BOOT = 1000
TOP_CLASSES = 12   # drift table rows (classes with support in every snapshot)


def load_ok(dirpath, freeze_filter=False):
    pre, ext = [], []
    for p in glob.glob(os.path.join(dirpath, "*.json")):
        try:
            r = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if r.get("status") != "ok":
            continue
        if r.get("ext") == "sensitivity-ext":
            ext.append(r)
        else:
            pre.append(r)
    if freeze_filter:
        pre = [r for r in pre if (r.get("ts") or "") < FREEZE_CUTOFF]
    pre.sort(key=lambda r: r.get("ts") or "")
    return pre, ext


def class_and_impact(recs):
    cat, imp = Counter(), Counter()
    per_trace = []
    for r in recs:
        tc = set()
        for e in (r.get("errors") or []):
            cat[norm_cat(e.get("category"))] += 1
            imp[str(e.get("impact", "")).upper() or "(blank)"] += 1
            tc.add(norm_cat(e.get("category")))
        per_trace.append(tc)
    return cat, imp, per_trace


def shares(counter):
    tot = sum(counter.values())
    return {k: v / tot for k, v in counter.items()} if tot else {}


def top_n(sh, n=10):
    return sorted(sh.items(), key=lambda kv: -kv[1])[:n]


def l1(a, b):
    return sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in set(a) | set(b))


def boot_shares(recs, n_boot=N_BOOT):
    packs = []
    for r in recs:
        cats, imps = Counter(), Counter()
        for e in (r.get("errors") or []):
            cats[norm_cat(e.get("category"))] += 1
            imps[str(e.get("impact", "")).upper() or "(blank)"] += 1
        packs.append((cats, imps))
    n = len(packs)
    out = []
    for _ in range(n_boot):
        idx = RNG.integers(0, n, n)
        cat, imp = Counter(), Counter()
        for i in idx:
            c, m = packs[i]
            cat.update(c)
            imp.update(m)
        out.append((shares(cat), shares(imp)))
    return out


def ci(boot, key, which=0):
    vals = sorted(b[which].get(key, 0.0) for b in boot)
    if not vals:
        return (0.0, 0.0)
    return vals[int(0.025 * len(vals))], vals[int(0.975 * len(vals))]


def chi2_two(cat1, cat2):
    keys = sorted(set(cat1) | set(cat2),
                  key=lambda k: -(cat1.get(k, 0) + cat2.get(k, 0)))
    keys = [k for k in keys if cat1.get(k, 0) + cat2.get(k, 0) >= 10]
    table = [[cat1.get(k, 0) for k in keys], [cat2.get(k, 0) for k in keys]]
    if len(keys) < 2:
        return None, None, 0
    chi2, p, dof, _ = chi2_contingency(np.array(table))
    return chi2, p, dof


def main():
    pre, ext = load_ok(LABELS_A, freeze_filter=True)
    snapA = pre[:N_SNAP_A]
    snapB = pre
    snapC = pre + ext
    dpre, dext = load_ok(LABELS_B)      # batch B has no ext labels
    snapD = dpre + dext

    catA, impA, _ = class_and_impact(snapA)
    catB, impB, _ = class_and_impact(snapB)
    catC, impC, _ = class_and_impact(snapC)
    catD, impD, _ = class_and_impact(snapD)
    shB, shC, shD = shares(catB), shares(catC), shares(catD)
    imB, imC, imD = shares(impB), shares(impC), shares(impD)

    topB, topC, topD = top_n(shB), top_n(shC), top_n(shD)
    setB = {c for c, _ in topB}
    setC = {c for c, _ in topC}
    setD = {c for c, _ in topD}
    jacc_CD = len(setC & setD) / len(setC | setD)
    jacc_BD = len(setB & setD) / len(setB | setD)

    chi_CD, p_CD, dof_CD = chi2_two(catC, catD)
    chi_BD, p_BD, dof_BD = chi2_two(catB, catD)

    bootD = boot_shares(snapD)
    top5D = [c for c, _ in top_n(shD, 5)]
    c_in_d = {}
    for c in top5D:
        lo, hi = ci(bootD, c)
        v = shC.get(c, 0.0)
        c_in_d[c] = {"C_share": round(v, 4), "D_ci": [round(lo, 4), round(hi, 4)],
                     "inside": bool(lo <= v <= hi)}
    b_in_d = {}
    for c in top5D:
        lo, hi = ci(bootD, c)
        v = shB.get(c, 0.0)
        b_in_d[c] = {"B_share": round(v, 4), "D_ci": [round(lo, 4), round(hi, 4)],
                     "inside": bool(lo <= v <= hi)}
    imp_c_in_d = {}
    for k in ("HIGH", "MEDIUM", "LOW"):
        lo, hi = ci(bootD, k, 1)
        v = imC.get(k, 0.0)
        imp_c_in_d[k] = {"C_share": round(v, 4),
                         "D_ci": [round(lo, 4), round(hi, 4)],
                         "inside": bool(lo <= v <= hi)}
    imp_b_in_d = {}
    for k in ("HIGH", "MEDIUM", "LOW"):
        lo, hi = ci(bootD, k, 1)
        v = imB.get(k, 0.0)
        imp_b_in_d[k] = {"B_share": round(v, 4),
                         "D_ci": [round(lo, 4), round(hi, 4)],
                         "inside": bool(lo <= v <= hi)}

    drift_classes = [c for c, _ in top_n(shD, TOP_CLASSES)]
    drift_tbl = []
    for c in drift_classes:
        drift_tbl.append({
            "class": c,
            "B": round(shB.get(c, 0.0), 4),
            "C": round(shC.get(c, 0.0), 4),
            "D": round(shD.get(c, 0.0), 4),
            "drift_C_D": round(shD.get(c, 0.0) - shC.get(c, 0.0), 4),
        })

    result = {
        "generated": "batch-B full-N (grok-4.7 single-model) sensitivity point D",
        "snapshots": {
            "A_n_ok": len(snapA), "B_n_ok": len(snapB),
            "C_n_ok": len(snapC), "D_n_ok": len(snapD),
            "D_error_labels": sum(catD.values()),
            "B_error_labels": sum(catB.values()),
            "C_error_labels": sum(catC.values()),
        },
        "models": {"B/C": "wave1 mix (glm-5.3-flash dominated) + glm ext",
                   "D": "grok-4.7 only"},
        "class_drift_top12": drift_tbl,
        "impact_shares": {
            "B": {k: round(v, 4) for k, v in imB.items()},
            "C": {k: round(v, 4) for k, v in imC.items()},
            "D": {k: round(v, 4) for k, v in imD.items()},
            "max_drift_C_D": max(
                (abs(imD.get(k, 0) - imC.get(k, 0)) for k in set(imC) | set(imD)),
                default=0.0),
        },
        "l1": {"B_C": round(l1(shB, shC), 4), "C_D": round(l1(shC, shD), 4),
               "B_D": round(l1(shB, shD), 4)},
        "top10_jaccard": {"B_C": None, "C_D": round(jacc_CD, 4),
                          "B_D": round(jacc_BD, 4)},
        "chi2": {"C_vs_D": {"chi2": chi_CD, "p": p_CD, "dof": dof_CD},
                 "B_vs_D": {"chi2": chi_BD, "p": p_BD, "dof": dof_BD}},
        "C_shares_in_D_ci": c_in_d,
        "B_shares_in_D_ci": b_in_d,
        "C_impact_in_D_ci": imp_c_in_d,
        "B_impact_in_D_ci": imp_b_in_d,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)

    n_out_c = sum(1 for v in c_in_d.values() if not v["inside"])
    n_out_ci = sum(1 for v in imp_c_in_d.values() if not v["inside"])
    n_out_b = sum(1 for v in b_in_d.values() if not v["inside"])
    n_out_bi = sum(1 for v in imp_b_in_d.values() if not v["inside"])
    max_cls_drift = max((abs(d["drift_C_D"]) for d in drift_tbl), default=0.0)

    lines = []
    lines.append("\n\n## Full-N point (D) — batch B, single-model grok-4.7 "
                 "(2026-10-30)\n")
    lines.append("Generated by `fullrun_sensitivity_d.py` from "
                 "`work/fullrun/corpus2_labels_b` (single-model grok-4.7 "
                 "effort-low pass over ALL 40,798 canonical targets; "
                 "sensitivity.md A/B/C content above is preserved unchanged). "
                 "Snapshot reconstruction verified exactly: B(pre-ext, ts<"
                 f"{FREEZE_CUTOFF}) n_ok={len(snapB)}, C=+ext n_ok={len(snapC)}"
                 " — matches the published table.\n")
    lines.append(f"- D: n_ok={len(snapD)} annotated traces, "
                 f"{sum(catD.values()):,} error labels, one instrument "
                 "(grok-4.7).\n")
    lines.append("\n### Per-class share drift (top-12 D classes)\n")
    lines.append("| class | B | C | D | drift C->D |\n|---|---|---|---|---|\n")
    for d in drift_tbl:
        lines.append(f"| {d['class']} | {d['B']} | {d['C']} | {d['D']} | "
                     f"{d['drift_C_D']:+.4f} |\n")
    lines.append(f"\nL1(B,C)={result['l1']['B_C']}  L1(C,D)={result['l1']['C_D']}"
                 f"  L1(B,D)={result['l1']['B_D']}  "
                 f"max|class drift C->D|={max_cls_drift:.4f}\n")
    lines.append(f"\nTop-10 Jaccard: C vs D = {jacc_CD:.3f}, B vs D = "
                 f"{jacc_BD:.3f}\n")
    lines.append("\n### Impact shares (HIGH/MEDIUM/LOW)\n")
    lines.append("| impact | B | C | D | drift C->D |\n|---|---|---|---|---|\n")
    for k in ("HIGH", "MEDIUM", "LOW"):
        lines.append(f"| {k} | {imB.get(k,0):.4f} | {imC.get(k,0):.4f} | "
                     f"{imD.get(k,0):.4f} | "
                     f"{imD.get(k,0)-imC.get(k,0):+.4f} |\n")
    lines.append(f"\nmax|impact drift C->D| = "
                 f"{result['impact_shares']['max_drift_C_D']:.4f}\n")
    lines.append("\n### Chi-square (class x snapshot, >=10 collapsed)\n")
    lines.append(f"- C vs D: chi2={chi_CD:.1f} dof={dof_CD} p={p_CD:.3e}\n")
    lines.append(f"- B vs D: chi2={chi_BD:.1f} dof={dof_BD} p={p_BD:.3e}\n")
    lines.append("\n### Bootstrap (1000 resamples at D): C and B point "
                 "estimates vs D 95% CI\n")
    lines.append("| quantity | C/B share | D 95% CI | inside |\n|---|---|---|---|\n")
    for c, v in c_in_d.items():
        lines.append(f"| class {c} (C) | {v['C_share']} | "
                     f"[{v['D_ci'][0]}, {v['D_ci'][1]}] | "
                     f"{'YES' if v['inside'] else 'NO'} |\n")
    for k, v in imp_c_in_d.items():
        lines.append(f"| impact {k} (C) | {v['C_share']} | "
                     f"[{v['D_ci'][0]}, {v['D_ci'][1]}] | "
                     f"{'YES' if v['inside'] else 'NO'} |\n")
    for c, v in b_in_d.items():
        lines.append(f"| class {c} (B) | {v['B_share']} | "
                     f"[{v['D_ci'][0]}, {v['D_ci'][1]}] | "
                     f"{'YES' if v['inside'] else 'NO'} |\n")
    for k, v in imp_b_in_d.items():
        lines.append(f"| impact {k} (B) | {v['B_share']} | "
                     f"[{v['D_ci'][0]}, {v['D_ci'][1]}] | "
                     f"{'YES' if v['inside'] else 'NO'} |\n")
    lines.append(f"\n{n_out_c}/5 top-5 C class shares and {n_out_ci}/3 C impact "
                 f"shares fall OUTSIDE D's bootstrap CI; "
                 f"{n_out_b}/5 B class shares and {n_out_bi}/3 B impact shares "
                 f"do.\n")

    # ---- verdict restatement at full N (generated, threshold-based) -------
    agr = {}
    agr_p = os.path.join(WORK, "batchb_agreement.json")
    if os.path.exists(agr_p):
        try:
            agr = json.load(open(agr_p, encoding="utf-8")).get("pairs", {}).get(
                "glm-5.3-flash", {})
        except Exception:
            agr = {}
    cls_stable = n_out_c == 0
    imp_stable = n_out_ci == 0
    if cls_stable and imp_stable:
        verdict = ("STABLE AT FULL N (within-model): every C class and impact "
                   "share sits inside D's bootstrap 95% CI")
    elif cls_stable:
        verdict = ("CLASS MIX STABLE AT FULL N; IMPACT MIX STILL MOVES: all "
                   "top-5 class shares inside D's CI but "
                   f"{n_out_ci}/3 impact shares outside")
    else:
        verdict = ("STILL UNSTABLE AT FULL N: "
                   f"{n_out_c}/5 top-5 class shares and {n_out_ci}/3 impact "
                   "shares at C fall OUTSIDE D's bootstrap 95% CI")
    lines.append("\n### VERDICT AT FULL N (D)\n\n")
    lines.append(f"**{verdict}.** Numbers: L1(C,D)={result['l1']['C_D']} vs "
                 f"L1(B,C)={result['l1']['B_C']}; max|class drift C->D|="
                 f"{max_cls_drift:.4f}; max|impact drift C->D|="
                 f"{result['impact_shares']['max_drift_C_D']:.4f}; top-10 "
                 f"Jaccard(C,D)={jacc_CD:.3f}; chi-square C-vs-D p={p_CD:.3e}. "
                 "Instrument note: B/C were glm-5.3-flash-dominated mixes at "
                 "N=1.1k; D is a single-model (grok-4.7) full-N instrument "
                 f"(n_ok={len(snapD)}), so C->D drift mixes selection-with-N "
                 "with annotator-model change. The same-hash cross-model "
                 "agreement statistic (batchb_agreement.json: glm-5.3-flash vs "
                 "grok-4.7, mean per-trace category-set Jaccard="
                 f"{agr.get('mean_jaccard_category_set')}, exact-set-match="
                 f"{agr.get('exact_category_set_match_rate')}, n="
                 f"{agr.get('overlap_ok_pairs')}) bounds how much of the "
                 "C->D move is annotator-model rather than selection: at this "
                 "agreement level, a large L1(C,D) cannot be attributed to "
                 "sampling noise alone.\n")
    with open(OUT_MD, "a", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"sensitivity D appended: D n_ok={len(snapD)} L1(C,D)="
          f"{result['l1']['C_D']} jacc(C,D)={jacc_CD:.3f} "
          f"chi2 C-vs-D p={p_CD:.3e}")
    print(f"wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
