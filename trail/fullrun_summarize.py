"""Aggregate corpus label checkpoints -> work/fullrun/corpus_summary.json.

PRIVACY: reads only label files (ids/labels/counts by construction - see
fullrun_corpus.strip_private) and usage ledgers. Emits aggregates only:
category counts, impact counts, per-project counts, status counts, coverage,
token usage. This JSON is the canonical artifact the dashboard embeds and
verify_fullrun.py independently recomputes.
"""
from __future__ import annotations

import glob
import json
import os
from collections import Counter

from fullrun_common import LANE

WORK = os.path.join(LANE, "work", "fullrun")
LABELS = os.path.join(WORK, "corpus_labels")
CENSUS = os.path.join(WORK, "corpus_census.jsonl")
USAGE = os.path.join(WORK, "usage", "corpus.jsonl")
OUT = os.path.join(WORK, "corpus_summary.json")

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
    for leaf in ALL_LEAVES:
        if c == leaf.lower() or c.replace(" ", "") == leaf.lower().replace(" ", ""):
            return leaf
    for leaf in ALL_LEAVES:
        if c.replace(" ", "") in leaf.lower().replace(" ", ""):
            return leaf
    return c


def main():
    files = sorted(glob.glob(os.path.join(LABELS, "*.json")))
    status = Counter()
    level = Counter()
    cat = Counter()
    cat_traces = Counter()  # per-trace prevalence: # traces with >=1 label of class
    impact = Counter()
    per_project_traces = Counter()
    per_project_errors = Counter()
    per_project_cat = {}
    errors_per_trace = []
    spans_total = parsed_total = lines_total = bytes_total = 0
    n_with_errors = 0
    loc_self = Counter()  # how often cited span kinds
    score_rubric = {k: [] for k in ("reliability_score", "security_score",
                                    "instruction_adherence_score", "plan_opt_score",
                                    "overall")}
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
    bad_keys = []

    ALLOWED_ERR_KEYS = {"category", "location", "impact"}
    for p in files:
        try:
            rec = json.load(open(p, encoding="utf-8"))
        except Exception:
            status["unreadable_checkpoint"] += 1
            continue
        status[rec.get("status", "?")] += 1
        per_project_traces[rec.get("project", "?")] += 1
        level[rec.get("level", "?")] += 1
        spans_total += rec.get("spans", 0) or 0
        parsed_total += rec.get("parsed", 0) or 0
        lines_total += rec.get("lines", 0) or 0
        bytes_total += rec.get("bytes", 0) or 0
        errs = rec.get("errors") or []
        trace_cats = set()
        for e in errs:
            if set(e.keys()) - ALLOWED_ERR_KEYS:
                bad_keys.append(rec.get("key"))
            cat[norm_cat(e.get("category"))] += 1
            trace_cats.add(norm_cat(e.get("category")))
            impact[str(e.get("impact", "")).upper() or "(blank)"] += 1
            per_project_errors[rec.get("project", "?")] += 1
            per_project_cat.setdefault(rec.get("project", "?"), Counter())[norm_cat(e.get("category"))] += 1
        if rec.get("status") == "ok":
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

    for k in per_project_cat:
        per_project_cat[k] = dict(per_project_cat[k].most_common())

    census = {"files": 0, "bytes": 0}
    if os.path.exists(CENSUS):
        crows = [json.loads(l) for l in open(CENSUS, encoding="utf-8")]
        census = {"files": len(crows),
                  "bytes": sum(r.get("bytes", 0) for r in crows)}

    ok_n = status.get("ok", 0)
    summary = {
        "label_files": len(files),
        "census_files": census["files"],
        "census_bytes": census["bytes"],
        "status_counts": dict(status),
        "coverage_fraction": (len(files) / census["files"]) if census["files"] else None,
        "level_counts": dict(level),
        "traces_annotated_ok": ok_n,
        "traces_with_errors": n_with_errors,
        "total_error_labels": sum(cat.values()),
        "category_counts": dict(cat.most_common()),
        "category_trace_prevalence": {k: cat_traces.get(k, 0) for k in
                                      dict(cat.most_common())},
        "category_counts_by_root": {
            root: {leaf: cat.get(leaf, 0) for leaf in leaves}
            for root, leaves in TAXONOMY_ROOTS.items()},
        "impact_counts": dict(impact),
        "errors_per_trace_mean": (sum(errors_per_trace) / len(errors_per_trace))
                                if errors_per_trace else None,
        "errors_per_trace_max": max(errors_per_trace) if errors_per_trace else 0,
        "traces_zero_error_labels": sum(1 for n in errors_per_trace if n == 0),
        "per_project_traces": dict(per_project_traces.most_common()),
        "per_project_errors": dict(per_project_errors.most_common()),
        "per_project_top_categories": {k: dict(v) for k, v in
                                       sorted(per_project_cat.items())},
        "spans_total": spans_total,
        "journal_lines_total": lines_total,
        "journal_lines_parsed_total": parsed_total,
        "bytes_total": bytes_total,
        "score_rubric_means": {k: (sum(v) / len(v)) if v else None
                               for k, v in score_rubric.items()},
        "score_rubric_n": {k: len(v) for k, v in score_rubric.items()},
        "usage": usage,
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
