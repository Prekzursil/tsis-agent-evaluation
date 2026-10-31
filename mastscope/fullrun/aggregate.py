#!/usr/bin/env python3
"""Aggregate per-trace MAST labels into counts-only distribution tables.

Inputs:  fullrun/labels.jsonl (per-trace binary labels), fullrun/census.jsonl (per-file metadata)
Output:  fullrun/aggregates.json  — counts/ratios ONLY (no content, no summaries)

Semantics:
  incidence[m]  = traces with modes[m]==True / N_ok          (per-trace rate)
  occurrence share = yes-counts[m] / total_yes                (paper-style, sums to 1
                    across 14 modes — comparable to MAST paper Fig/prevalences)
  category share   = sum of yes-counts of category modes / total_yes
"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODE_CODES = ["1.1", "1.2", "1.3", "1.4", "1.5",
              "2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
              "3.1", "3.2", "3.3"]
CAT_OF = {**{m: "FC1" for m in MODE_CODES[:5]},
          **{m: "FC2" for m in MODE_CODES[5:11]},
          **{m: "FC3" for m in MODE_CODES[11:]}}


def month_of(ts):
    return ts[:7] if isinstance(ts, str) and len(ts) >= 7 else None


def _path_split(recs):
    """Main-session files (project-dir/<uuid>.jsonl) vs delegated subagent transcripts
    (nested under subagents/ or agent-named workflow dirs). Counts only."""
    main_c = sub_c = 0
    main_yes, sub_yes = Counter(), Counter()
    for r in recs:
        rel = r["trace_id"]
        parts = rel.split("/")
        is_main = len(parts) == 2 and not parts[1].startswith("agent-")
        tgt, cnt = (main_yes, "main") if is_main else (sub_yes, "sub")
        if is_main:
            main_c += 1
        else:
            sub_c += 1
        for m in MODE_CODES:
            if r["modes"].get(m) is True:
                tgt[m] += 1
    return {"n_main": main_c, "n_sub": sub_c,
            "main_yes": dict(main_yes), "sub_yes": dict(sub_yes)}


def census_composition():
    """Label-independent corpus composition (counts only)."""
    import statistics
    sizes, msgses, months, side = [], [], Counter(), 0
    n = err = 0
    with (HERE / "census.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if r.get("cls") != "session":
                continue
            n += 1
            sizes.append(r.get("size") or 0)
            msgses.append((r.get("n_user") or 0) + (r.get("n_asst") or 0))
            if (r.get("n_sidechain") or 0) > 0:
                side += 1
            mo = (r.get("first_ts") or "")[:7]
            if mo:
                months[mo] += 1
            if r.get("err"):
                err += 1
    msgses.sort()
    def pct(p):
        i = min(len(msgses) - 1, int(p * len(msgses)))
        return msgses[i]
    return {
        "n_sessions": n,
        "n_with_read_errors": err,
        "n_sidechain_sessions": side,
        "msgs_pct": {"p50": pct(0.50), "p75": pct(0.75), "p90": pct(0.90), "p99": pct(0.99)},
        "size_gb_total": round(sum(sizes) / 2**30, 2),
        "months": dict(sorted(months.items())),
    }


def main():
    census = {}
    with (HERE / "census.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            census[r["rel"]] = r

    recs, fails = [], Counter()
    with (HERE / "labels.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                fails["bad_json"] += 1
                continue
            if r.get("ok"):
                recs.append(r)
            else:
                fails[r.get("fail", "?")] += 1

    n = len(recs)
    yes = Counter()
    n_modes_hist = Counter()
    task_yes = task_no = task_null = 0
    months = defaultdict(lambda: {"n": 0, "any_fail": 0, "yes": Counter(),
                                  "task_no": 0, "side": 0})
    split_side = {"multi": Counter(), "solo": Counter()}
    n_multi = n_solo = 0
    for r in recs:
        k = sum(1 for m in MODE_CODES if r["modes"].get(m) is True)
        n_modes_hist[k] += 1
        for m in MODE_CODES:
            if r["modes"].get(m) is True:
                yes[m] += 1
        if r.get("task_completed") is True:
            task_yes += 1
        elif r.get("task_completed") is False:
            task_no += 1
        else:
            task_null += 1
        mo = month_of(r.get("first_ts"))
        if mo:
            months[mo]["n"] += 1
            months[mo]["any_fail"] += 1 if k else 0
            months[mo]["task_no"] += 1 if r.get("task_completed") is False else 0
            for m in MODE_CODES:
                if r["modes"].get(m) is True:
                    months[mo]["yes"][m] += 1
        multi = (r.get("n_sidechain") or 0) > 0
        tgt = split_side["multi"] if multi else split_side["solo"]
        if multi:
            n_multi += 1
        else:
            n_solo += 1
        for m in MODE_CODES:
            if r["modes"].get(m) is True:
                tgt[m] += 1

    total_yes = sum(yes.values()) or 1
    cat_yes = Counter()
    for m, c in yes.items():
        cat_yes[CAT_OF[m]] += c
    total_cat = sum(cat_yes.values()) or 1

    out = {
        "n_labeled_ok": n,
        "n_label_fail_lines": dict(fails),
        "trace_set_total": sum(1 for v in census.values() if v.get("cls") == "session"),
        "task_completed": {"yes": task_yes, "no": task_no, "null": task_null},
        "modes_per_trace_hist": {str(k): v for k, v in sorted(n_modes_hist.items())},
        "modes": {
            m: {
                "yes": yes[m],
                "incidence_pct": round(100 * yes[m] / max(n, 1), 2),
                "occurrence_share_pct": round(100 * yes[m] / total_yes, 2),
                "category": CAT_OF[m],
            } for m in MODE_CODES
        },
        "categories": {
            c: {"yes": cat_yes[c], "occurrence_share_pct": round(100 * cat_yes[c] / total_cat, 2)}
            for c in ("FC1", "FC2", "FC3")
        },
        "total_yes_labels": total_yes,
        "traces_with_any_mode": n_modes_hist and sum(v for k, v in n_modes_hist.items() if k > 0),
        "monthly": {
            mo: {
                "n": v["n"],
                "any_fail": v["any_fail"],
                "task_no": v["task_no"],
                "yes": dict(v["yes"]),
            } for mo, v in sorted(months.items())
        },
        "split_sidechain": {
            "n_multi_subagent_traces": n_multi,
            "n_solo_traces": n_solo,
            "multi_yes": dict(split_side["multi"]),
            "solo_yes": dict(split_side["solo"]),
        },
        "split_pathclass": _path_split(recs),
        "note": "counts and ratios only; no trace content or model summaries persisted",
        "census_composition": census_composition(),
    }
    (HERE / "aggregates.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"aggregated {n} ok labels -> aggregates.json "
          f"(total_yes={total_yes}, task yes/no={task_yes}/{task_no})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
