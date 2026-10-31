#!/usr/bin/env python
"""Cross-taxonomy join: MAST-14 (mastscope) x TRAIL (trail) on sha256.

Joins every content hash labeled OK by BOTH lanes:
  - MAST:   mastscope/fullrun/labels_full.jsonl  (ok=true rows; multi-part
            container hashes OR-aggregated to hash level)
  - TRAIL:  trail/work/fullrun/corpus2_labels/<sha16>.json (status=="ok";
            categories normalized to the 21-class scorer list)
Key provenance is verified against corpus/manifest.jsonl and
corpus/canonical_set.json.

Outputs aggregates-only JSON to corpus/cross_taxonomy_join.json (counts,
ratios, p-values; no session content, no hashes).
Run: python cross_taxonomy_join.py   (from the repo root, tsis-agent-evaluation)
"""

import collections
import glob
import json
import math
from typing import cast

from scipy import stats

BASE = "."
MAST_LABELS = f"{BASE}/mastscope/fullrun/labels_full.jsonl"
TRAIL_DIR = f"{BASE}/trail/work/fullrun/corpus2_labels"
MANIFEST = f"{BASE}/corpus/manifest.jsonl"
CANONICAL = f"{BASE}/corpus/canonical_set.json"
OUT = f"{BASE}/corpus/cross_taxonomy_join.json"

MAST_MODES = [
    ("1.1", "Disobey Task Specification"),
    ("1.2", "Disobey Role Specification"),
    ("1.3", "Step Repetition"),
    ("1.4", "Loss of Conversation History"),
    ("1.5", "Unaware of Termination Conditions"),
    ("2.1", "Conversation Reset"),
    ("2.2", "Fail to Ask for Clarification"),
    ("2.3", "Task Derailment"),
    ("2.4", "Information Withholding"),
    ("2.5", "Ignored Other Agent's Input"),
    ("2.6", "Action-Reasoning Mismatch"),
    ("3.1", "Premature Termination"),
    ("3.2", "Weak Verification"),
    ("3.3", "No or Incorrect Verification"),
]
MAST_CAT = {  # mode -> FC category
    **{m: "FC1 System Design / Specification" for m in ["1.1", "1.2", "1.3", "1.4", "1.5"]},
    **{m: "FC2 Inter-Agent Misalignment" for m in ["2.1", "2.2", "2.3", "2.4", "2.5", "2.6"]},
    **{m: "FC3 Task Verification" for m in ["3.1", "3.2", "3.3"]},
}
# TRAIL canonical classes (repo/benchmarking/calculate_scores.py all_categories)
TRAIL_CLASSES = [
    "Language-only",
    "Tool-related",
    "Poor Information Retrieval",
    "Incorrect Memory Usage",
    "Tool Output Misinterpretation",
    "Incorrect Problem Identification",
    "Tool Selection Errors",
    "Formatting Errors",
    "Instruction Non-compliance",
    "Tool Definition Issues",
    "Environment Setup Errors",
    "Rate Limiting",
    "Authentication Errors",
    "Service Errors",
    "Resource Not Found",
    "Resource Exhaustion",
    "Timeout Issues",
    "Context Handling Failures",
    "Resource Abuse",
    "Goal Deviation",
    "Task Orchestration",
]
TRAIL_ROOT = {  # class -> root (paper appendix taxonomy, trail/paper_text.txt:1755-1810)
    "Language-only": "Reasoning Errors",
    "Tool-related": "Reasoning Errors",
    "Poor Information Retrieval": "Reasoning Errors",
    "Incorrect Memory Usage": "Reasoning Errors",
    "Tool Output Misinterpretation": "Reasoning Errors",
    "Incorrect Problem Identification": "Reasoning Errors",
    "Tool Selection Errors": "Reasoning Errors",
    "Formatting Errors": "Reasoning Errors",
    "Instruction Non-compliance": "Reasoning Errors",
    "Tool Definition Issues": "System Execution Errors",
    "Environment Setup Errors": "System Execution Errors",
    "Rate Limiting": "System Execution Errors",
    "Authentication Errors": "System Execution Errors",
    "Service Errors": "System Execution Errors",
    "Resource Not Found": "System Execution Errors",
    "Resource Exhaustion": "System Execution Errors",
    "Timeout Issues": "System Execution Errors",
    "Context Handling Failures": "Planning and Coordination Errors",
    "Resource Abuse": "Planning and Coordination Errors",
    "Goal Deviation": "Planning and Coordination Errors",
    "Task Orchestration": "Planning and Coordination Errors",
}


def norm_trail(cat: str):
    """Normalize an annotator-emitted category to the canonical class list."""
    if cat in TRAIL_CLASSES:
        return cat, ""
    if cat.startswith("Tool-related ("):
        return "Tool-related", "parenthesized-variant"
    if cat.startswith("Hallucinations > "):
        return cat.split("> ", 1)[1].strip(), "parent-path-variant"
    head = cat.split(" (", 1)[0].strip()
    if head in TRAIL_CLASSES:
        return head, "parenthesized-variant"
    return None, "off-taxonomy"


def shannon(counts):
    tot = sum(counts)
    if tot == 0:
        return 0.0
    h = 0.0
    for c in counts:
        if c:
            p = c / tot
            h -= p * math.log2(p)
    return h


def js_divergence(p, q):
    """Jensen-Shannon divergence, base 2 (bounded by 1)."""
    m = [(a + b) / 2 for a, b in zip(p, q, strict=False)]

    def kl(x, y):
        s = 0.0
        for a, b in zip(x, y, strict=False):
            if a > 0 and b > 0:
                s += a * math.log2(a / b)
        return s

    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def bh_fdr(pvals):
    """Benjamini-Hochberg q-values."""
    n = len(pvals)
    order = sorted(range(n), key=lambda i: pvals[i])
    qs = [0.0] * n
    prev = 1.0
    for rank, idx in enumerate(reversed(order), start=1):
        i = n - rank  # rank from largest p down
        val = min(prev, pvals[idx] * n / (i + 1))
        qs[idx] = val
        prev = val
    return qs


def main():
    # ---------- load + verify provenance ----------
    manifest_sha = set()
    for line in open(MANIFEST, encoding="utf-8"):
        manifest_sha.add(json.loads(line)["sha256"])
    canon = json.load(open(CANONICAL, encoding="utf-8"))
    canon_sha = set(e["sha256"] for e in canon["annotation_set"])

    mast = collections.defaultdict(list)
    n_mast_rows = n_mast_ok_rows = 0
    for line in open(MAST_LABELS, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        n_mast_rows += 1
        if d.get("ok"):
            n_mast_ok_rows += 1
            mast[d["sha256"]].append(d)

    trail = {}
    trail_status = collections.Counter()
    norm_log = collections.Counter()
    for fp in glob.glob(f"{TRAIL_DIR}/*.json"):
        d = json.load(open(fp, encoding="utf-8"))
        trail_status[d["status"]] += 1
        if d["status"] != "ok":
            continue
        cats = set()
        for e in d.get("errors", []):
            nc, why = norm_trail(e["category"])
            if nc is None:
                norm_log["off-taxonomy:" + e["category"]] += 1
                continue
            if why:
                norm_log[why + ":" + e["category"]] += 1
            cats.add(nc)
        d["_cats"] = cats
        trail[d["sha256"]] = d

    join = set(mast) & set(trail)
    diag = {
        "mast_label_rows": n_mast_rows,
        "mast_ok_rows": n_mast_ok_rows,
        "mast_ok_hashes": len(mast),
        "trail_label_files": sum(trail_status.values()),
        "trail_status": dict(trail_status),
        "trail_ok_hashes": len(trail),
        "join_n": len(join),
        "join_in_manifest": sum(1 for h in join if h in manifest_sha),
        "join_in_canonical": sum(1 for h in join if h in canon_sha),
        "trail_ok_not_mast_ok": sum(1 for h in trail if h not in mast),
        "join_multipart_hashes": sum(1 for h in join if len(mast[h]) > 1),
        "join_trail_ext_labels": sum(1 for h in join if trail[h].get("ext") == "sensitivity-ext"),
        "category_normalizations": dict(norm_log),
    }
    # decompose trail_ok \ mast_ok
    mast_any_row = collections.defaultdict(list)
    for line in open(MAST_LABELS, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        mast_any_row[d["sha256"]].append(d.get("ok"))
    tnm = [h for h in trail if h not in mast]
    diag["trail_ok_not_mast_ok__was_mast_target_parsefail"] = sum(
        1 for h in tnm if h in mast_any_row
    )
    diag["trail_ok_not_mast_ok__never_mast_target"] = sum(1 for h in tnm if h not in mast_any_row)

    # ---------- session-level join ----------
    sessions = []
    for h in join:
        rows = sorted(mast[h], key=lambda r: r["target_id"])
        modes = {m: any(r["modes"].get(m) for r in rows) for m, _ in MAST_MODES}
        tc = rows[0].get("task_completed")  # part 0
        t = trail[h]
        sessions.append(
            {
                "modes": modes,
                "task_completed": tc,
                "cats": t["_cats"],
                "n_err_raw": t.get("n_errors", len(t.get("errors", []))),
                "impacts": collections.Counter(e["impact"] for e in t.get("errors", [])),
                "scores": t.get("scores", {}),
                "model": t.get("model"),
                "ext": t.get("ext") == "sensitivity-ext",
                "runtime": t.get("runtime"),
            }
        )
    N = len(sessions)

    {m: name for m, name in MAST_MODES}
    observed_classes = [c for c in TRAIL_CLASSES if any(c in s["cats"] for s in sessions)]

    # ---------- 1. any-flag agreement ----------
    mast_any = [any(s["modes"].values()) for s in sessions]
    trail_any = [len(s["cats"]) > 0 for s in sessions]
    both = sum(1 for a, b in zip(mast_any, trail_any, strict=False) if a and b)
    m_only = sum(1 for a, b in zip(mast_any, trail_any, strict=False) if a and not b)
    t_only = sum(1 for a, b in zip(mast_any, trail_any, strict=False) if not a and b)
    neither = sum(1 for a, b in zip(mast_any, trail_any, strict=False) if not a and not b)
    tab = [[both, m_only], [t_only, neither]]
    chi2: float
    p_chi: float
    if N and min(min(r) for r in tab) > 0:
        _c2, _p, _dof, _ = stats.chi2_contingency(tab)
        chi2, p_chi = float(cast(float, _c2)), float(cast(float, _p))
    else:  # guard: empty join (N=0) or a zero agreement cell
        chi2, p_chi = float("nan"), float("nan")
    # kappa
    po = (both + neither) / N if N else 0.0
    pe = (
        ((both + m_only) * (both + t_only) + (t_only + neither) * (m_only + neither)) / (N * N)
        if N
        else 1.0
    )
    kappa = (po - pe) / (1 - pe) if pe < 1 else float("nan")
    phi = math.sqrt(chi2 / N) if chi2 == chi2 and N else float("nan")

    agreement = {
        "n": N,
        "both": both,
        "mast_only": m_only,
        "trail_only": t_only,
        "neither": neither,
        "pct_both": both / N if N else 0.0,
        "pct_mast_only": m_only / N if N else 0.0,
        "pct_trail_only": t_only / N if N else 0.0,
        "pct_neither": neither / N if N else 0.0,
        "mast_any_rate": (both + m_only) / N if N else 0.0,
        "trail_any_rate": (both + t_only) / N if N else 0.0,
        "kappa": kappa,
        "chi2": chi2,
        "p_chi2": p_chi,
        "phi": phi,
        "jaccard_anyflag": both / (both + m_only + t_only)
        if (both + m_only + t_only)
        else float("nan"),
    }

    # ---------- 2. co-occurrence matrix ----------
    cooc = {m: {c: 0 for c in observed_classes} for m, _ in MAST_MODES}
    mode_yes = {m: 0 for m, _ in MAST_MODES}
    class_yes = {c: 0 for c in observed_classes}
    for s in sessions:
        for m, _ in MAST_MODES:
            if s["modes"][m]:
                mode_yes[m] += 1
                for c in s["cats"]:
                    # defensive: observed_classes is derived from these very
                    # sessions, so the membership is always true
                    if c in cooc[m]:  # pragma: no branch
                        cooc[m][c] += 1
        for c in s["cats"]:
            if c in class_yes:  # pragma: no branch (same invariant)
                class_yes[c] += 1

    # ---------- 3. per-mode x class stats ----------
    pair_stats = []
    for m, mname in MAST_MODES:
        for c in observed_classes:
            a = cooc[m][c]
            b = mode_yes[m] - a
            cc = class_yes[c] - a
            d = N - a - b - cc
            table = [[a, b], [cc, d]]
            try:
                orv, pf = stats.fisher_exact(table)
            except Exception:  # pragma: no cover - defensive: scipy rejects
                orv, pf = float("nan"), float("nan")  # degenerate tables only
            lift = (
                (a / mode_yes[m]) / (class_yes[c] / N)
                if mode_yes[m] and class_yes[c]
                else float("nan")
            )
            pair_stats.append(
                {
                    "mode": m,
                    "mode_name": mname,
                    "cls": c,
                    "a": a,
                    "b": b,
                    "c": cc,
                    "d": d,
                    "odds_ratio": orv,
                    "p_fisher": pf,
                    "lift": lift,
                    "p_mode": mode_yes[m] / N,
                    "p_cls": class_yes[c] / N,
                    "p_both": a / N,
                }
            )
    qs = bh_fdr([ps["p_fisher"] for ps in pair_stats])
    for ps, q in zip(pair_stats, qs, strict=False):
        ps["q_bh"] = q

    # entropy per mode: distribution over TRAIL classes among mode=yes vs mode=no
    entropy_modes = {}
    for m, mname in MAST_MODES:
        yes_c = [cooc[m][c] for c in observed_classes]
        no_c = [class_yes[c] - cooc[m][c] for c in observed_classes]
        py = [v / sum(yes_c) if sum(yes_c) else 0 for v in yes_c]
        pn = [v / sum(no_c) if sum(no_c) else 0 for v in no_c]
        k = len(observed_classes)
        logk = math.log2(k) if k else 0.0  # guard: no observed classes -> H_norm 0
        entropy_modes[m] = {
            "mode_name": mname,
            "n_yes": mode_yes[m],
            "err_labels_yes": sum(yes_c),
            "err_labels_no": sum(no_c),
            "H_cls_given_yes_bits": shannon(yes_c),
            "H_cls_given_no_bits": shannon(no_c),
            "H_norm_yes": shannon(yes_c) / logk if logk else 0.0,
            "H_norm_no": shannon(no_c) / logk if logk else 0.0,
            "JS_yes_no_bits": js_divergence(py, pn),
            "mean_errs_yes": sum(yes_c) / mode_yes[m] if mode_yes[m] else float("nan"),
            "mean_errs_no": sum(no_c) / (N - mode_yes[m]) if N > mode_yes[m] else float("nan"),
        }
    entropy_classes = {}
    for c in observed_classes:
        yes_m = [cooc[m][c] for m, _ in MAST_MODES]
        no_m = [mode_yes[m] - cooc[m][c] for m, _ in MAST_MODES]
        py = [v / sum(yes_m) if sum(yes_m) else 0 for v in yes_m]
        pn = [v / sum(no_m) if sum(no_m) else 0 for v in no_m]
        k = len(MAST_MODES)
        logk = math.log2(k) if k else 0.0
        entropy_classes[c] = {
            "n_yes": class_yes[c],
            "mode_labels_yes": sum(yes_m),
            "mode_labels_no": sum(no_m),
            "H_modes_given_yes_bits": shannon(yes_m),
            "H_modes_given_no_bits": shannon(no_m),
            "H_norm_yes": shannon(yes_m) / logk if logk else 0.0,
            "H_norm_no": shannon(no_m) / logk if logk else 0.0,
            "JS_yes_no_bits": js_divergence(py, pn),
            "mean_modes_yes": sum(yes_m) / class_yes[c] if class_yes[c] else float("nan"),
            "mean_modes_no": sum(no_m) / (N - class_yes[c]) if N > class_yes[c] else float("nan"),
        }

    # ---------- 4. category x root matrix ----------
    cats3 = [
        "FC1 System Design / Specification",
        "FC2 Inter-Agent Misalignment",
        "FC3 Task Verification",
    ]
    roots3 = ["Reasoning Errors", "System Execution Errors", "Planning and Coordination Errors"]
    catroot = {fc: {r: 0 for r in roots3} for fc in cats3}
    for s in sessions:
        for m, _ in MAST_MODES:
            if s["modes"][m]:
                for c in s["cats"]:
                    catroot[MAST_CAT[m]][TRAIL_ROOT[c]] += 1
    # chi2 on 3x3 (label-level); guard: scipy raises ValueError on tables with
    # a zero row/column sum (degenerate joins), not just on all-zero tables
    table = [[catroot[fc][r] for r in roots3] for fc in cats3]
    n_cr = sum(sum(r) for r in table)
    chi2_cr = p_cr = dof_cr = cramers_v = float("nan")
    exp = None
    if (
        n_cr > 0
        and all(sum(r) for r in table)
        and all(sum(table[i][j] for i in range(3)) for j in range(3))
    ):
        _c2, _p, _dof, exp = stats.chi2_contingency(table)
        chi2_cr, p_cr, dof_cr = (
            float(cast(float, _c2)), float(cast(float, _p)), float(cast(float, _dof))
        )
        cramers_v = math.sqrt(chi2_cr / (n_cr * (min(3, 3) - 1)))

    # ---------- 5. misses / blind spots ----------
    infra_classes = [c for c in TRAIL_CLASSES if TRAIL_ROOT[c] == "System Execution Errors"]
    verify_modes = ["3.1", "3.2", "3.3"]
    m_clean_t_flag = [s for s in sessions if not any(s["modes"].values()) and s["cats"]]
    t_clean_m_flag = [s for s in sessions if any(s["modes"].values()) and not s["cats"]]
    misses = {
        "trail_flagged_mast_clean_n": len(m_clean_t_flag),
        "classes_in_trail_flagged_mast_clean": collections.Counter(
            c for s in m_clean_t_flag for c in s["cats"]
        ),
        "infra_only_sessions_n": 0,
        "infra_only_mast_flagged": 0,
        "mast_flagged_trail_clean_n": len(t_clean_m_flag),
        "modes_in_mast_flagged_trail_clean": collections.Counter(
            m for s in t_clean_m_flag for m, v in s["modes"].items() if v
        ),
        "verify_only_sessions_n": 0,
        "verify_only_trail_flagged": 0,
    }
    for s in sessions:
        if s["cats"] and all(c in infra_classes for c in s["cats"]):
            misses["infra_only_sessions_n"] += 1
            if any(s["modes"].values()):
                misses["infra_only_mast_flagged"] += 1
        flagged = [m for m, v in s["modes"].items() if v]
        if flagged and all(m in verify_modes for m in flagged):
            misses["verify_only_sessions_n"] += 1
            if s["cats"]:
                misses["verify_only_trail_flagged"] += 1

    # class-labels occurring only in sessions where the other taxonomy is clean
    # (= labels invisible to the other instrument at session level)
    misses["trail_class_labels_in_mast_clean_sessions"] = sum(
        len(s["cats"]) for s in m_clean_t_flag
    )
    misses["mast_mode_labels_in_trail_clean_sessions"] = sum(
        sum(1 for v in s["modes"].values() if v) for s in t_clean_m_flag
    )

    # ---------- 6. cross-instrument continuous ----------
    nmodes = [sum(1 for v in s["modes"].values() if v) for s in sessions]
    nerrs = [len(s["cats"]) for s in sessions]
    rho, rho_p = stats.spearmanr(nmodes, nerrs)
    tc_groups = collections.defaultdict(list)
    for s in sessions:
        tc_groups[s["task_completed"]].append(s["scores"].get("overall"))
    tc_overall = {
        str(k): {
            "n": len(v),
            "mean_overall": sum(x for x in v if x is not None)
            / max(1, sum(1 for x in v if x is not None)),
        }
        for k, v in tc_groups.items()
    }
    # impact mix by mast any-flag
    imp_mix = {}
    for flagname, flag in [("mast_flagged", True), ("mast_clean", False)]:
        cnt = collections.Counter()
        tot = 0
        for s, ma in zip(sessions, mast_any, strict=False):
            if ma == flag:
                cnt.update(s["impacts"])
                tot += sum(s["impacts"].values())
        imp_mix[flagname] = {
            "HIGH": cnt["HIGH"],
            "MEDIUM": cnt["MEDIUM"],
            "LOW": cnt["LOW"],
            "total": tot,
        }

    # selection check: MAST mode prevalence in join vs full MAST-ok corpus
    full_mode_yes = collections.Counter()
    n_full = 0
    seen = set()
    for line in open(MAST_LABELS, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        if d.get("ok") and d["sha256"] not in seen:
            seen.add(d["sha256"])
            n_full += 1
            for m, v in d["modes"].items():
                if v:
                    full_mode_yes[m] += 1
    selection = {
        m: {
            "join_rate": mode_yes[m] / N if N else 0.0,
            "full_rate": full_mode_yes[m] / n_full if n_full else 0.0,
        }
        for m, _ in MAST_MODES
    }

    # runtime mix of the join vs the TRAIL-ok set (selection disclosure)
    join_runtime = collections.Counter(s["runtime"] for s in sessions)
    trail_runtime = collections.Counter(t.get("runtime") for t in trail.values())

    out = {
        "diagnostics": diag,
        "agreement_anyflag": agreement,
        "mode_marginals": {m: mode_yes[m] for m, _ in MAST_MODES},
        "class_marginals": {c: class_yes[c] for c in observed_classes},
        "observed_classes": observed_classes,
        "cooccurrence": cooc,
        "pair_stats": pair_stats,
        "entropy_by_mode": entropy_modes,
        "entropy_by_class": entropy_classes,
        "category_root_matrix": {
            "matrix": catroot,
            "chi2": chi2_cr,
            "p": p_cr,
            "dof": dof_cr,
            "cramers_v": cramers_v,
            "n_labels": n_cr,
        },
        "misses": {
            k: (dict(v) if isinstance(v, collections.Counter) else v) for k, v in misses.items()
        },
        "continuous": {
            "spearman_nmodes_nerrs": rho,
            "spearman_p": rho_p,
            "mean_nmodes": sum(nmodes) / N if N else float("nan"),
            "mean_nclasses": sum(nerrs) / N if N else float("nan"),
            "tc_overall_scores": tc_overall,
            "impact_mix_by_mastflag": imp_mix,
        },
        "selection_check": selection,
        "runtime_mix": {"join": dict(join_runtime), "trail_ok": dict(trail_runtime)},
        "n_full_mast_ok_hashes": n_full,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=float)

    # ---------- console summary ----------
    print(f"JOIN N={N}  both={both} mast_only={m_only} trail_only={t_only} neither={neither}")
    print(f"kappa={kappa:.3f} phi={phi:.3f} chi2p={p_chi:.2e}")
    print(f"spearman(nmodes,nerrs)={rho:.3f} p={rho_p:.2e}")
    print(f"catroot chi2={chi2_cr:.1f} p={p_cr:.3e} V={cramers_v:.3f}")
    print("top pairs by count:")
    for ps in sorted(pair_stats, key=lambda x: -x["a"])[:12]:
        print(
            f"  {ps['mode']} x {ps['cls']}: a={ps['a']} lift={ps['lift']:.2f} "
            f"p={ps['p_fisher']:.1e} q={ps['q_bh']:.1e}"
        )
    print("misses:", {k: v for k, v in out["misses"].items() if not isinstance(v, dict)})
    print("wrote", OUT)


if __name__ == "__main__":
    main()
