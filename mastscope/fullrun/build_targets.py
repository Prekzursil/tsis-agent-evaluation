#!/usr/bin/env python3
"""Build the annotation target set from the rebuilt corpus canonical_set.json.

For every canonical (unique-hash) entry, run schema-based extraction; entries that
yield >=1 user AND >=1 assistant message become annotation targets (one per session;
multi-conversation containers explode into per-conversation targets keyed
"<sha16>#<k>"). Everything else is tallied into an exclusion table by reason.

PRIVACY: targets.jsonl stores ids/counts/timestamps + username-redacted file paths
(<USER> placeholder for the OS home dir) - never message text.
Also writes manifest_index.json (redacted path -> sha256) for migrating the prior run's
path-keyed labels to hash keys, and prints an exclusion summary.

Usage: python build_targets.py [--workers N]
"""
import argparse
import collections
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
CORPUS = HERE.parent.parent / "corpus"

sys.path.insert(0, str(HERE))


OTHER_OK_EXT = {".jsonl", ".json", ".ndjson", ".txt", ".log", ".md", ".yaml", ".yml"}
OTHER_SIZE_CAP = 1_000_000_000  # 1GB

# PRIVACY: never persist the OS username inside paths; redact to <USER> on write.
# Consumers (annotate2.py, verify_fullrun.py) un-redact with Path.home().name.
HOME_NAME = Path(os.path.expanduser("~")).name


def redact(p: str) -> str:
    return p.replace(HOME_NAME, "<USER>") if HOME_NAME else p


def one_entry(task):
    import extract2
    sha, path, runtime, origin, storage, size = task
    try:
        if storage == "directory":
            fmt, summ = extract2.extract_directory(path)
        elif storage == "sqlite":
            fmt, summ = None, []
        elif storage == "other":
            ext = os.path.splitext(path)[1].lower()
            if ext not in OTHER_OK_EXT or size > OTHER_SIZE_CAP:
                fmt, summ = None, []
            else:
                fmt, summ = extract2.extract_path(path, storage, size)
        else:
            fmt, summ = extract2.extract_path(path, storage, size)
    except Exception:
        return {"sha": sha, "ok": False, "reason": "extract_error", "runtime": runtime,
                "storage": storage}
    if not summ:
        return {"sha": sha, "ok": False, "reason": "not_parseable", "runtime": runtime,
                "storage": storage, "format": fmt}
    out = []
    for k, s in enumerate(summ):
        tid = sha if len(summ) == 1 else f"{sha[:16]}#{k}"
        out.append({
            "target_id": tid, "sha256": sha, "part": k, "n_parts": len(summ),
            "path": redact(path), "runtime": runtime, "origin": origin,
            "storage_type": storage, "size": size, "format": s["format"],
            "n_user": s["n_user"], "n_asst": s["n_asst"], "n_msg": s["n_msg"],
            "n_tool_use": s["n_tool_use"], "n_tool_result": s["n_tool_result"],
            "n_sidechain": s["n_sidechain"], "first_ts": s["first_ts"],
            "last_ts": s["last_ts"],
        })
    return {"sha": sha, "ok": True, "targets": out, "runtime": runtime, "storage": storage}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max(8, (os.cpu_count() or 8) - 2))
    args = ap.parse_args()

    canon = json.loads((CORPUS / "canonical_set.json").read_text(encoding="utf-8"))
    aset = canon["annotation_set"]
    print(f"[targets] canonical entries: {len(aset)}", flush=True)

    tasks = [(e["sha256"], e["path"], e["runtime"], e["origin"], e["storage_type"],
              e.get("size") or 0) for e in aset]

    # resume support: replay per-sha results from a partial file
    partial = HERE / "targets_partial.jsonl"
    results = {}
    if partial.exists():
        with partial.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                results[r["sha"]] = r
        print(f"[targets] resumed from partial: {len(results)} shas already done", flush=True)
    tasks = [t for t in tasks if t[0] not in results]

    t0 = time.time()
    n_new = 0
    with partial.open("a", encoding="utf-8") as pout:
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(one_entry, t): t for t in tasks}
            for fut in as_completed(futs):
                r = fut.result()
                results[r["sha"]] = r
                n_new += 1
                pout.write(json.dumps(r, separators=(",", ":")) + "\n")
                if n_new % 2000 == 0:
                    pout.flush()
                    el = time.time() - t0
                    n_tg = sum(len(r.get("targets") or []) for r in results.values())
                    print(f"[targets] +{n_new}/{len(tasks)} new this run; "
                          f"total sha={len(results)} targets={n_tg} "
                          f"rate={n_new/el:.1f}/s", flush=True)

    targets = []
    excluded = collections.Counter()
    excl_by_runtime = collections.Counter()
    fmt_counter = collections.Counter()
    for r in results.values():
        if r["ok"]:
            for trec in r["targets"]:
                targets.append(trec)
                fmt_counter[trec["format"]] += 1
        else:
            excluded[f'{r["reason"]}:{r["storage"]}'] += 1
            excl_by_runtime[r["runtime"]] += 1

    with (HERE / "targets.jsonl").open("w", encoding="utf-8") as out:
        for trec in targets:
            out.write(json.dumps(trec, separators=(",", ":")) + "\n")

    # manifest path->sha256 index (for migrating prior path-keyed labels)
    print("[targets] building path->sha index from manifest...", flush=True)
    idx = {}
    with (CORPUS / "manifest.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("sha256"):
                idx[redact(r["path"])] = r["sha256"]
    (HERE / "manifest_index.json").write_text(json.dumps(idx), encoding="utf-8")

    summary = {
        "canonical_entries": len(aset),
        "targets": len(targets),
        "unique_sha_with_targets": len({t["sha256"] for t in targets}),
        "formats": dict(fmt_counter.most_common()),
        "excluded_by_reason_storage": dict(excluded.most_common()),
        "excluded_by_runtime_top": dict(excl_by_runtime.most_common(25)),
        "workers": args.workers,
        "seconds": round(time.time() - t0, 1),
        "new_this_run": n_new,
        "resumed_total_shas": len(results),
    }
    (HERE / "targets_summary.json").write_text(json.dumps(summary, indent=2),
                                               encoding="utf-8")
    print(json.dumps(summary, indent=2)[:3000], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
