#!/usr/bin/env python3
"""Offline reconciliation + privacy audit for the full-corpus MAST run (v2, rebuilt
multi-runtime corpus). NO API calls. Exit 0 required.

Checks:
 1. Coverage: labels_full.jsonl (+parse_fails) + pending == targets.jsonl; ids valid,
    unique; every label has 14 mode entries.
 2. Reconciliation: aggregates2.json numbers recomputed INDEPENDENTLY from
    labels_full.jsonl + targets.jsonl must match exactly; RESULTS.md CHECK markers
    must match the same recomputation.
 3. Privacy: (a) per-record whitelisted key sets in lane JSONL artifacts;
    (b) verbatim-content probe - random long substrings of real session text sampled
    at verify time from the target files must appear in NO lane artifact;
    (c) the API-key value appears in no lane artifact;
    (d) the OS username appears in no lane text artifact (paths are stored
    redacted with a <USER> placeholder; un-redacted only in memory).

Usage: python verify_fullrun.py  -> PASS/FAIL lines, exit 0 iff all PASS.
"""
import json
import os
import random
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent          # lane root (mastscope/)
FULLRUN = HERE / "fullrun"
CORPUS = HERE.parent / "corpus"                  # tss/tsis-deepdive/corpus
MODE_CODES = ["1.1", "1.2", "1.3", "1.4", "1.5",
              "2.1", "2.2", "2.3", "2.4", "2.5", "2.6",
              "3.1", "3.2", "3.3"]
LABEL_KEYS = {"target_id", "sha256", "ok", "task_completed", "modes", "n_answered",
              "model", "migrated_from", "usage", "attempts", "runtime", "origin",
              "format", "n_user", "n_asst", "n_msg", "n_sidechain", "first_ts", "fail"}
TARGET_KEYS = {"target_id", "sha256", "part", "n_parts", "path", "runtime", "origin",
               "storage_type", "size", "format", "n_user", "n_asst", "n_msg",
               "n_tool_use", "n_tool_result", "n_sidechain", "first_ts", "last_ts"}
CAT_OF = {**{m: "FC1" for m in MODE_CODES[:5]},
          **{m: "FC2" for m in MODE_CODES[5:11]},
          **{m: "FC3" for m in MODE_CODES[11:]}}

failures = []
notes = []


def check(name, cond, detail=""):
    if cond:
        notes.append(f"PASS {name}" + (f" ({detail})" if detail else ""))
    else:
        failures.append(f"FAIL {name}" + (f" ({detail})" if detail else ""))
    return cond


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


def main():
    # ---------------- load artifacts
    targets = {}
    with (FULLRUN / "targets.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                t = json.loads(line)
                targets[t["target_id"]] = t
            except Exception:
                pass
    labels = []
    with (FULLRUN / "labels_full.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                labels.append(json.loads(line))
            except Exception:
                pass
    agg = json.loads((FULLRUN / "aggregates2.json").read_text(encoding="utf-8"))
    check("artifacts.targets", len(targets) > 0, f"{len(targets)} targets")
    check("artifacts.labels", len(labels) > 0, f"{len(labels)} labels")

    # ---------------- 1. coverage + schema
    ids = [r["target_id"] for r in labels]
    dup = [k for k, v in Counter(ids).items() if v > 1]
    check("labels.unique_ids", not dup, f"{len(dup)} dups")
    bad_ids = [i for i in ids if i not in targets]
    check("labels.ids_in_targets", not bad_ids, f"{len(bad_ids)} unknown")
    bad_modes = [r["target_id"][:12] for r in labels
                 if "modes" not in r or set(r["modes"]) != set(MODE_CODES)]
    check("labels.mode_schema", not bad_modes, f"{len(bad_modes)} bad")
    ok_labels = [r for r in labels if r.get("ok")]
    n_ok = len(ok_labels)
    n_fail = len(labels) - n_ok
    pending = len(targets) - len(set(ids))
    check("coverage.sum", n_ok + n_fail + pending == len(targets),
          f"ok={n_ok} fail={n_fail} pending={pending} total={len(targets)}")
    check("coverage.matches_agg", agg.get("pending") == pending,
          f"agg.pending={agg.get('pending')} vs {pending}")

    # ---------------- 2. reconciliation (independent recompute)
    mode_yes = Counter()
    task = Counter()
    cat_yes = Counter()
    monthly = Counter()
    runtime_n = Counter()
    for r in ok_labels:
        for m, v in r["modes"].items():
            if v:
                mode_yes[m] += 1
                cat_yes[CAT_OF[m]] += 1
        task["yes" if r.get("task_completed") is True else
             "no" if r.get("task_completed") is False else "null"] += 1
        t = targets.get(r["target_id"], {})
        mo = norm_month(r.get("first_ts") or t.get("first_ts")) or "unknown"
        monthly[mo] += 1
        runtime_n[t.get("runtime", "?")] += 1
    total_yes = sum(mode_yes.values())
    check("recon.n_ok", agg["n_labeled_ok"] == n_ok, f"{agg['n_labeled_ok']} vs {n_ok}")
    check("recon.total_yes", agg["total_yes_labels"] == total_yes,
          f"{agg['total_yes_labels']} vs {total_yes}")
    for m in MODE_CODES:
        a = agg["modes"][m]["yes"]
        check(f"recon.mode_{m}", a == mode_yes[m], f"{a} vs {mode_yes[m]}")
    for c in ("FC1", "FC2", "FC3"):
        a = agg["categories"][c]["yes"]
        check(f"recon.cat_{c}", a == cat_yes[c], f"{a} vs {cat_yes[c]}")
    check("recon.task", agg["task_completed"] == dict(task),
          f"{agg['task_completed']} vs {dict(task)}")
    check("recon.monthly_n", {k: v["n"] for k, v in agg["monthly"].items()} == dict(monthly),
          "monthly ns differ")
    top_rt = list(agg["by_runtime"].items())[0][0] if agg["by_runtime"] else None
    if runtime_n:
        check("recon.top_runtime", top_rt == runtime_n.most_common(1)[0][0],
              f"{top_rt} vs {runtime_n.most_common(1)[0][0]}")

    # RESULTS.md CHECK markers
    results_md = (HERE / "RESULTS.md").read_text(encoding="utf-8")
    markers = dict(re.findall(r"<!--CHECK:([a-z_0-9]+)=([0-9]+)-->", results_md))
    expected = {
        "n_ok": n_ok, "n_targets": len(targets), "total_yes": total_yes,
        "task_yes": task["yes"], "task_no": task["no"],
        "traces_any": sum(1 for r in ok_labels if any(r["modes"].values())),
        "pending": pending,
    }
    for k, v in expected.items():
        got = markers.get(k)
        check(f"results.marker_{k}", got == str(v), f"RESULTS.md {got} vs {v}")

    # dashboard KPI consistency (spot)
    dash = FULLRUN / "dashboard_full2.html"
    if dash.exists():
        html = dash.read_text(encoding="utf-8")
        check("dashboard.kpi_n", f"{n_ok:,}" in html, "n_ok KPI present")
        check("dashboard.kpi_targets", f"{len(targets):,}" in html, "targets KPI present")
    else:
        check("dashboard.exists", False, "dashboard_full2.html missing")

    # ---------------- 3a. key whitelists
    bad_keys = []
    for r in labels[:5000] + labels[-5000:]:
        extra = set(r.keys()) - LABEL_KEYS
        if extra:
            bad_keys.append((r["target_id"][:12], sorted(extra)))
    check("privacy.label_keys", not bad_keys, f"{len(bad_keys)} bad")
    bad_tkeys = []
    for tid, t in list(targets.items())[:5000]:
        extra = set(t.keys()) - TARGET_KEYS
        if extra:
            bad_tkeys.append((tid[:12], sorted(extra)))
    check("privacy.target_keys", not bad_tkeys, f"{len(bad_tkeys)} bad")

    # ---------------- 3b. verbatim content probe
    rng = random.Random(11)
    home_name = Path.home().name
    parseable = [t for t in targets.values()
                 if t.get("storage_type") in ("jsonl", "json", "zst", "gz", "directory")]
    probes = []
    tries = 0
    while len(probes) < 60 and tries < 400:
        tries += 1
        t = rng.choice(parseable)
        try:
            p = Path(t["path"].replace("<USER>", home_name))
            if t["storage_type"] == "directory":
                cands = list(p.glob("*.jsonl"))
                if not cands:
                    continue
                p = cands[0]
            if t["storage_type"] == "zst" or p.suffix == ".zst":
                import zstandard
                with open(p, "rb") as raw:
                    with zstandard.ZstdDecompressor(max_window_size=1 << 31).stream_reader(raw) as rdr:
                        text = rdr.read(3_000_000).decode("utf-8", errors="replace")
            elif t["storage_type"] == "gz" or p.suffix == ".gz":
                import gzip
                with gzip.open(p, "rt", encoding="utf-8", errors="replace") as fh:
                    text = fh.read(3_000_000)
            else:
                with open(p, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read(3_000_000)
        except Exception:
            continue
        mm = re.findall(r'"text"\s*:\s*"([^"\\]{80,240})"', text)
        if not mm:
            mm = re.findall(r'([A-Za-z,;: ]{100,240})', text)
        if not mm:
            continue
        s = rng.choice(mm).strip()
        if len(s) < 60 or p.name in s or p.stem in s:
            continue
        probes.append(s)

    lane_files = [q for q in HERE.rglob("*") if q.is_file()
                  and CORPUS not in q.parents and q.suffix in
                  {".jsonl", ".json", ".md", ".html", ".py", ".log", ".txt", ".js", ".sh"}]
    leaks = []
    for q in lane_files:
        try:
            blob = q.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for s in probes:
            if s in blob:
                leaks.append((str(q.relative_to(HERE)), s[:50]))
        if len(leaks) > 5:
            break
    check("privacy.no_content_leak", not leaks, f"{len(leaks)} leaks, probes={len(probes)}")

    # API key never in lane files
    key = os.environ.get("ZAI_CODING_PLAN_KEY", "")
    key_hits = []
    if key:
        for q in lane_files:
            try:
                blob = q.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if key in blob:
                key_hits.append(str(q.relative_to(HERE)))
    check("privacy.no_api_key", not key_hits, f"{key_hits[:3]}")

    # ---------------- 3d. OS username never appears in lane text artifacts
    # (paths in targets.jsonl/manifest_index.json/privacy_partial.jsonl are stored
    #  redacted as <USER>; repo/'s machine-local .venv was removed 2026-10-19 and
    #  the clone reflogs expired, so repo/ is held to the same standard)
    if home_name:
        user_hits = []
        for q in lane_files:
            if "__pycache__" in q.parts:
                continue
            try:
                blob = q.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if home_name in blob:
                user_hits.append(str(q.relative_to(HERE)))
        check("privacy.no_username", not user_hits, f"{user_hits[:3]}")
    else:
        check("privacy.no_username", True, "home dir name empty; skipped")

    # ---------------- report
    print("\n".join(notes))
    if failures:
        print("\n".join(failures))
        print(f"\nVERIFY FAILED: {len(failures)} failure(s), {len(notes)} passed")
        return 1
    print(f"\nVERIFY OK: {len(notes)} checks passed (probes={len(probes)}, "
          f"lane files scanned={len(lane_files)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
