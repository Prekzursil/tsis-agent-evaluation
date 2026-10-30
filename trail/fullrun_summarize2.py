"""Aggregate corpus2 label checkpoints -> work/fullrun/corpus2_summary.json.

Reads ONLY label files (ids/labels/counts by construction - privacy contract)
plus the corpus manifest for duplicate-path inheritance accounting. Emits
aggregates only: category/impact counts, per-runtime breakdowns, status counts,
coverage vs the offline census, token usage. This JSON is what the dashboard
embeds and verify_fullrun.py independently recomputes.
"""
from __future__ import annotations

import glob
import json
import os
from collections import Counter

from fullrun_common import LANE

WORK = os.path.join(LANE, "work", "fullrun")
LABELS = os.path.join(WORK, "corpus2_labels")
USAGE = os.path.join(WORK, "usage", "corpus2.jsonl")
CENSUS = os.path.join(WORK, "corpus2_census.json")
JOBS = os.path.join(WORK, "corpus2_jobs.json")
MANIFEST = os.path.normpath(os.path.join(LANE, "..", "corpus", "manifest.jsonl"))
OUT = os.path.join(WORK, "corpus2_summary.json")

TAXONOMY_ROOTS = {
    "Reasoning Errors": ["Language-only", "Tool-related", "Poor Information Retrieval",
                         "Tool Output Misinterpretation", "Incorrect Problem Identification",
                         "Tool Selection Errors", "Formatting Errors",
                         "Instruction Non-compliance"],
    "System Execution Errors": ["Tool Definition Issues", "Environment Setup Errors",
                                "Rate Limiting", "Authentication Errors", "Service Errors",
                                "Resource Not Found", "Resource Exhaustion", "Timeout Issues"],
    "Planning and Coordination Errors": ["Context Handling Failures", "Resource Abuse",
                                         "Goal Deviation", "Task Orchestration"],
}
ALL_LEAVES = [c for v in TAXONOMY_ROOTS.values() for c in v]


def norm_cat(c: str) -> str:
    c = (c or "").strip().lower()
    if not c:
        return "(blank)"
    # annotators sometimes emit "leaf (parenthetical qualifier)" - e.g.
    # "tool-related (fabricating tool outputs/capabilities)" for the paper's
    # "Tool-related" leaf. Try the bare stem as a separate pass.
    stem = c.split("(")[0].strip()
    for cand in (c, stem):
        for leaf in ALL_LEAVES:
            if cand == leaf.lower() or cand.replace(" ", "") ==                     leaf.lower().replace(" ", ""):
                return leaf
    for cand in (c, stem):
        for leaf in ALL_LEAVES:
            if cand.replace(" ", "") and cand.replace(" ", "") in                     leaf.lower().replace(" ", ""):
                return leaf
    return c


def main():
    files = sorted(glob.glob(os.path.join(LABELS, "*.json")))
    status = Counter()
    level = Counter()
    fmt = Counter()
    cat = Counter()
    cat_traces = Counter()
    impact = Counter()
    per_rt_traces = Counter()
    per_rt_ok = Counter()
    per_rt_errors = Counter()
    per_rt_cat = {}
    per_model_traces = Counter()
    per_model_ok = Counter()
    errors_per_trace = []
    spans_total = events_total = 0
    n_with_errors = 0
    score_rubric = {k: [] for k in ("reliability_score", "security_score",
                                    "instruction_adherence_score", "plan_opt_score",
                                    "overall")}
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
    bad_keys = []
    ok_shas = set()
    labelled_shas = set()

    ALLOWED_ERR_KEYS = {"category", "location", "impact"}
    for p in files:
        try:
            rec = json.load(open(p, encoding="utf-8"))
        except Exception:
            status["unreadable_checkpoint"] += 1
            continue
        sha = rec.get("sha256") or ""
        labelled_shas.add(sha)
        rt = rec.get("runtime", "?")
        mdl = rec.get("model", "?")
        per_model_traces[mdl] += 1
        status[rec.get("status", "?")] += 1
        per_rt_traces[rt] += 1
        level[rec.get("level", "?")] += 1
        fmt[rec.get("format", "?")] += 1
        spans_total += rec.get("spans", 0) or 0
        events_total += rec.get("events", 0) or 0
        errs = rec.get("errors") or []
        trace_cats = set()
        for e in errs:
            if set(e.keys()) - ALLOWED_ERR_KEYS:
                bad_keys.append(sha[:12])
            cat[norm_cat(e.get("category"))] += 1
            trace_cats.add(norm_cat(e.get("category")))
            impact[str(e.get("impact", "")).upper() or "(blank)"] += 1
            per_rt_errors[rt] += 1
            per_rt_cat.setdefault(rt, Counter())[norm_cat(e.get("category"))] += 1
        if rec.get("status") == "ok":
            ok_shas.add(sha)
            per_rt_ok[rt] += 1
            per_model_ok[mdl] += 1
            for c in trace_cats:
                cat_traces[c] += 1
            errors_per_trace.append(len(errs))
            if errs:
                n_with_errors += 1
            for k in score_rubric:
                v = (rec.get("scores") or {}).get(k)
                if v is not None:
                    score_rubric[k].append(v)
        u = rec.get("usage") or {}
        usage["prompt_tokens"] += u.get("prompt_tokens", 0) or 0
        usage["completion_tokens"] += u.get("completion_tokens", 0) or 0
        if u:
            usage["calls"] += 1

    for k in per_rt_cat:
        per_rt_cat[k] = dict(per_rt_cat[k].most_common())

    # duplicate-path inheritance: manifest records whose sha has a label
    manifest_records = 0
    manifest_records_inheriting_ok = 0
    manifest_records_labelled = 0
    sha_multiplicity = Counter()
    if os.path.exists(MANIFEST):
        for line in open(MANIFEST, encoding="utf-8"):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            sha = r.get("sha256")
            if not sha:
                continue
            manifest_records += 1
            sha_multiplicity[sha] += 1
            if sha in labelled_shas:
                manifest_records_labelled += 1
                if sha in ok_shas:
                    manifest_records_inheriting_ok += 1

    census = {}
    if os.path.exists(CENSUS):
        census = json.load(open(CENSUS, encoding="utf-8"))

    ok_n = status.get("ok", 0)
    summary = {
        "label_files": len(files),
        "canonical_supported_jobs": census.get("jobs"),
        "census_eligible_sessions": census.get("eligible_sessions"),
        "status_counts": dict(status),
        "format_counts": dict(fmt),
        "level_counts": dict(level),
        "traces_annotated_ok": ok_n,
        "traces_with_errors": n_with_errors,
        "total_error_labels": sum(cat.values()),
        "category_counts": dict(cat.most_common()),
        "category_trace_prevalence": dict(cat_traces.most_common()),
        "category_counts_by_root": {
            root: {leaf: cat.get(leaf, 0) for leaf in leaves}
            for root, leaves in TAXONOMY_ROOTS.items()},
        "impact_counts": dict(impact),
        "errors_per_trace_mean": (sum(errors_per_trace) / len(errors_per_trace))
                                if errors_per_trace else None,
        "errors_per_trace_max": max(errors_per_trace) if errors_per_trace else 0,
        "traces_zero_error_labels": sum(1 for n in errors_per_trace if n == 0),
        "per_runtime_traces": dict(per_rt_traces.most_common()),
        "per_model_traces": dict(per_model_traces.most_common()),
        "per_model_ok": dict(per_model_ok.most_common()),
        "per_runtime_ok": dict(per_rt_ok.most_common()),
        "per_runtime_errors": dict(per_rt_errors.most_common()),
        "per_runtime_eligible": census.get("eligible_by_runtime", {}),
        "per_runtime_top_categories": {k: dict(v) for k, v in
                                       sorted(per_rt_cat.items())},
        "spans_total": spans_total,
        "events_total": events_total,
        "score_rubric_means": {k: (sum(v) / len(v)) if v else None
                               for k, v in score_rubric.items()},
        "score_rubric_n": {k: len(v) for k, v in score_rubric.items()},
        "usage": usage,
        "manifest": {
            "records": manifest_records,
            "records_labelled": manifest_records_labelled,
            "records_inheriting_ok_annotation": manifest_records_inheriting_ok,
            "labelled_sha_mean_path_multiplicity":
                (sum(sha_multiplicity[s] for s in labelled_shas) / len(labelled_shas))
                if labelled_shas else None,
        },
        "privacy_violations": bad_keys[:10],
        "privacy_violation_count": len(bad_keys),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print("wrote", OUT)
    print("labels:", len(files), "| ok:", ok_n, "| error labels:", sum(cat.values()))
    print("top categories:", cat.most_common(8))
    print("privacy violations:", len(bad_keys))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
