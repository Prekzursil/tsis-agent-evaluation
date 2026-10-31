#!/usr/bin/env python3
"""Aggregate the hash-keyed full-run labels into all distribution tables.

Reads targets.jsonl + labels_full.jsonl (+ sweep_status2.json, crosscheck2.jsonl,
crosscheck2_agreement.json, privacy_scan_full2.json when present) and writes
aggregates2.json - counts/ratios only, no content.
"""
import collections
import json
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODE_CODES = ["1.1", "1.2", "1.3", "1.4", "1.5",
              "2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
              "3.1", "3.2", "3.3"]
CAT_OF = {**{m: "FC1" for m in MODE_CODES[:5]},
          **{m: "FC2" for m in MODE_CODES[5:11]},
          **{m: "FC3" for m in MODE_CODES[11:]}}


def norm_month(ts):
    if not ts:
        return None
    try:
        if isinstance(ts, (int, float)) or (isinstance(ts, str) and ts.replace(".", "").isdigit()):
            dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        else:
            s = str(ts).replace("Z", "+00:00")
            dt = datetime.fromisoformat(s[:26])
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m")
    except Exception:
        return None


def v2_429_from_logs():
    """Cumulative v2-sweep 429 count reconstructed from per-round sweep logs
    (sweep2.log + sweep3.log). Each round's segment starts with a
    '[sweep2] targets=... model=...' line; counters inside a segment are
    monotonic, so the max '429=' value per segment is that round's total.
    Rounds killed before their first 100-item progress mark contribute 0
    (slight undercount, stated in RESULTS.md). Full-tier (non-flash) segments,
    e.g. cross-check runs, are excluded."""
    import re
    total = 0
    rounds = 0
    for name in ("sweep2.log", "sweep3.log"):
        p = HERE / name
        if not p.exists():
            continue
        seg_max = 0
        in_flash = False
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"\[sweep2\] targets=\d+ already_done=\d+ todo_now=\d+ "
                         r"model=(\S+)", line)
            if m:
                if in_flash:
                    total += seg_max
                    rounds += 1
                in_flash = m.group(1).endswith("flash")   # flash / flashx family
                seg_max = 0
                continue
            m429 = re.search(r"429=(\d+)", line)
            if m429 and in_flash:
                seg_max = max(seg_max, int(m429.group(1)))
        if in_flash:
            total += seg_max
            rounds += 1
    return total, rounds


def main():
    targets = {}
    with (HERE / "targets.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                t = json.loads(line)
                targets[t["target_id"]] = t
            except Exception:
                pass

    labels = []
    with (HERE / "labels_full.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                labels.append(json.loads(line))
            except Exception:
                pass
    lab_by_id = {r["target_id"]: r for r in labels}
    ok_labels = [r for r in labels if r.get("ok")]
    parse_fail = [r for r in labels if not r.get("ok")]

    n_ok = len(ok_labels)
    mode_yes = collections.Counter()
    mode_answered = collections.Counter()
    task = collections.Counter()
    n_migrated = 0
    fresh_by_model = collections.Counter()
    tok_new_pt = tok_new_ct = 0
    tok_mig_pt = tok_mig_ct = 0
    monthly = collections.defaultdict(lambda: {"n": 0, "yes": collections.Counter(),
                                               "task_yes": 0, "task_no": 0})
    by_runtime = collections.defaultdict(lambda: {"n": 0, "yes": collections.Counter(),
                                                  "task_yes": 0, "task_no": 0})
    by_format = collections.defaultdict(lambda: {"n": 0, "yes": collections.Counter(),
                                                 "task_yes": 0, "task_no": 0})
    by_origin = collections.defaultdict(lambda: {"n": 0, "yes": collections.Counter(),
                                                 "task_yes": 0, "task_no": 0})
    msg_hist = collections.Counter()
    sidechain_flag = collections.Counter()

    for r in ok_labels:
        t = targets.get(r["target_id"], {})
        if r.get("migrated_from"):
            n_migrated += 1
            tok_mig_pt += r.get("usage", {}).get("pt", 0)
            tok_mig_ct += r.get("usage", {}).get("ct", 0)
        else:
            fresh_by_model[r.get("model", "?")] += 1
            tok_new_pt += r.get("usage", {}).get("pt", 0)
            tok_new_ct += r.get("usage", {}).get("ct", 0)
        for m, v in r["modes"].items():
            mode_answered[m] += 1
            if v:
                mode_yes[m] += 1
        task["yes" if r.get("task_completed") is True else
              "no" if r.get("task_completed") is False else "null"] += 1
        mo = norm_month(r.get("first_ts") or t.get("first_ts"))
        groups = [(monthly, mo or "unknown"), (by_runtime, t.get("runtime", "?")),
                  (by_format, t.get("format", "?")), (by_origin, t.get("origin", "?"))]
        for d, k in groups:
            d[k]["n"] += 1
            d[k]["task_yes" if r.get("task_completed") else "task_no"] += 1 \
                if r.get("task_completed") is not None else 0
            for m, v in r["modes"].items():
                if v:
                    d[k]["yes"][m] += 1
        nm = r.get("n_msg") or 0
        bucket = ("<10" if nm < 10 else "10-49" if nm < 50 else "50-199" if nm < 200
                  else "200-999" if nm < 1000 else ">=1000")
        msg_hist[bucket] += 1
        sidechain_flag["with_subagents" if (r.get("n_sidechain") or 0) > 0 else "solo"] += 1

    total_yes = sum(mode_yes.values()) or 1

    def mode_table():
        out = {}
        for m in MODE_CODES:
            out[m] = {
                "yes": mode_yes[m],
                "answered": mode_answered[m],
                "incidence_pct": round(100 * mode_yes[m] / max(n_ok, 1), 2),
                "occurrence_share_pct": round(100 * mode_yes[m] / total_yes, 2),
            }
        return out

    cat_yes = collections.Counter()
    for m, v in mode_yes.items():
        cat_yes[CAT_OF[m]] += v
    cat_total = sum(cat_yes.values()) or 1

    def grp_out(d):
        res = {}
        for k, v in sorted(d.items(), key=lambda kv: -kv[1]["n"]):
            res[k] = {
                "n": v["n"],
                "task_completed_pct": round(100 * v["task_yes"] / max(v["task_yes"] + v["task_no"], 1), 1),
                "modes": {m: round(100 * v["yes"][m] / max(v["n"], 1), 1) for m in MODE_CODES},
                "top_mode": max(v["yes"], key=v["yes"].get) if v["yes"] else None,
            }
        return res

    # sweep status v1 (original run, path-keyed) for token accounting
    v1 = {}
    p = HERE / "sweep_status.json"
    if p.exists():
        try:
            v1 = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    v2 = {}
    p = HERE / "sweep_status2.json"
    if p.exists():
        try:
            v2 = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    xchk = {}
    p = HERE / "crosscheck2_agreement.json"
    if p.exists():
        try:
            xchk = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass

    t429, t429_rounds = v2_429_from_logs()

    out = {
        "targets_total": len(targets),
        "unique_sha": len({t["sha256"] for t in targets.values()}),
        "labels_written": len(labels),
        "n_labeled_ok": n_ok,
        "n_parse_fail": len(parse_fail),
        "n_migrated_from_v1": n_migrated,
        "fresh_by_model": dict(fresh_by_model),
        "pending": max(0, len(targets) - len(lab_by_id)),
        "task_completed": dict(task),
        "task_completed_yes_pct": round(100 * task["yes"] / max(n_ok, 1), 2),
        "traces_with_any_mode": sum(1 for r in ok_labels if any(r["modes"].values())),
        "total_yes_labels": total_yes if total_yes > 1 else sum(mode_yes.values()),
        "mean_modes_per_flagged_trace": round(
            sum(mode_yes.values()) / max(sum(1 for r in ok_labels if any(r["modes"].values())), 1), 2),
        "modes": mode_table(),
        "categories": {
            c: {"yes": cat_yes[c],
                "occurrence_share_pct": round(100 * cat_yes[c] / cat_total, 2),
                "sum_mode_incidence_pct": round(sum(
                    100 * mode_yes[m] / max(n_ok, 1) for m in MODE_CODES if CAT_OF[m] == c), 2)}
            for c in ("FC1", "FC2", "FC3")},
        "monthly": {k: {"n": v["n"],
                        "any_fail_pct": round(100 * sum(1 for _ in [1]) , 1)}
                    for k, v in sorted(monthly.items())},
        "monthly_detail": {k: {"n": v["n"], "yes": dict(v["yes"]),
                               "task_yes": v["task_yes"], "task_no": v["task_no"]}
                           for k, v in sorted(monthly.items())},
        "by_runtime": grp_out(by_runtime),
        "by_format": grp_out(by_format),
        "by_origin": grp_out(by_origin),
        "by_msg_count_bucket": dict(msg_hist.most_common()),
        "by_sidechain": dict(sidechain_flag),
        "tokens": {
            "v2_new_prompt": tok_new_pt, "v2_new_completion": tok_new_ct,
            "migrated_v1_prompt": tok_mig_pt, "migrated_v1_completion": tok_mig_ct,
            "v2_sweep_429_cumulative": t429,
            "v2_sweep_rounds_counted": t429_rounds,
            "v1_sweep_totals": {k: v1.get(k) for k in
                                ("ok", "prompt_tokens", "completion_tokens", "http_429")},
            "v2_sweep_totals": {k: v2.get(k) for k in
                                ("ok", "parse_fail", "http_429", "prompt_tokens",
                                 "completion_tokens", "stop_reason", "model")},
        },
        "crosscheck": xchk,
    }
    # fix monthly any_fail_pct properly
    for k, v in monthly.items():
        any_fail = sum(1 for r in ok_labels
                       if (norm_month(r.get("first_ts") or targets.get(r["target_id"], {}).get("first_ts")) or "unknown") == k
                       and any(r["modes"].values()))
        out["monthly"][k]["any_fail_pct"] = round(100 * any_fail / max(v["n"], 1), 1)
        out["monthly"][k]["any_fail_n"] = any_fail

    (HERE / "aggregates2.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"[agg2] targets={len(targets)} ok={n_ok} parse_fail={len(parse_fail)} "
          f"migrated={n_migrated} pending={out['pending']} "
          f"task_yes={task['yes']} total_yes={sum(mode_yes.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
