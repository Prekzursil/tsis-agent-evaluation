#!/usr/bin/env python3
"""Whole-corpus privacy scan driven by manifest.jsonl (both drives, all runtimes,
backups incl. orphans). Reuses privacy_scan.py's pattern set; COUNTS AND RATIOS ONLY -
no content, no matched text, no per-file detail is emitted.

Two scan modes, documented in the output note:
  - line mode (jsonl/zst/gz/json/plain): every line; lines >64KB pattern-scan their
    first 64KB; JSON detection capped at 1MB lines.
  - block mode (sqlite and 'other' binary containers incl. the 41GB tar): 64KB blocks,
    each block counted as a line-equivalent; no JSON detection.
Checkpointed per-file into privacy_partial.jsonl; restarts skip done paths.

Usage: python privacy_scan_corpus.py [--workers N] [--out privacy_scan_full2.json]
"""
import argparse
import collections
import gzip
import io
import json
import os
import re
import sys
import time
import zstandard
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import TimeoutError as FutTimeout
from pathlib import Path

HERE = Path(__file__).resolve().parent
LANE = HERE.parent
CORPUS = LANE.parent / "corpus"   # tss/tsis-deepdive/corpus
sys.path.insert(0, str(LANE))
from privacy_scan import PATTERNS, MESSAGE_MARKERS  # noqa: E402

COMPILED = {k: re.compile(v.pattern) for k, v in PATTERNS.items()}
BLOCK = 65536
BINARY_STORAGE = {"sqlite", "other"}

# PRIVACY: persist paths username-redacted (<USER>); real paths only live in memory.
HOME_NAME = Path(os.path.expanduser("~")).name


def redact(p: str) -> str:
    return p.replace(HOME_NAME, "<USER>") if HOME_NAME else p
BINARY_SUFFIX = {".db", ".vscdb", ".dat", ".tar", ".pdf", ".png", ".jpg", ".zip",
                 ".exe", ".dll", ".so", ".bin", ".mp4", ".webm", ".woff2"}


def _open_bin(path, storage):
    """Binary file-like for any storage (caller reads chunks and splits lines)."""
    if storage == "zst" or path.endswith(".zst"):
        return zstandard.ZstdDecompressor(max_window_size=1 << 31).stream_reader(
            open(path, "rb"))
    if storage == "gz" or path.endswith(".gz"):
        return gzip.open(path, "rb")
    return open(path, "rb")


def _iter_lines(fh, cap=1_000_000, chunk=262144):
    """Yield line-equivalents from a binary stream without unbounded buffering.
    A buffer with no newline for >= cap bytes is flushed as capped segments
    (pathological base64/image payloads)."""
    buf = b""
    while True:
        try:
            c = fh.read(chunk)
        except Exception:
            break
        if not c:
            if buf:
                yield buf
            return
        buf += c
        if len(buf) > 4 * cap + chunk:   # hard memory guard
            buf = buf[-2 * cap:]
        while True:
            i = buf.find(b"\n")
            if i < 0:
                if len(buf) >= cap:
                    yield buf[:cap]
                    buf = buf[cap:]
                break
            yield buf[:i]
            buf = buf[i + 1:]


def scan_one(task):
    path, storage = task
    st = {
        "files": 1, "unreadable": 0, "lines": 0, "json_lines": 0, "non_json_lines": 0,
        "message_objects": 0, "bytes": 0, "mode": "line",
        "cats": {c: 0 for c in COMPILED},
    }
    suffix = os.path.splitext(path)[1].lower()
    block_mode = storage in BINARY_STORAGE or suffix in BINARY_SUFFIX
    if block_mode:
        st["mode"] = "block"
    try:
        fh = open(path, "rb") if block_mode else _open_bin(path, storage)
    except OSError:
        st["unreadable"] = 1
        return st
    cats = st["cats"]
    n_lines = 0
    try:
        if block_mode:
            while True:
                b = fh.read(BLOCK)
                if not b:
                    break
                n_lines += 1
                w = b.decode("utf-8", errors="replace")
                for cat, rx in COMPILED.items():
                    if rx.search(w):
                        cats[cat] += 1
        else:
            LINE_WIN = 65536
            JSON_MAX = 1_000_000
            for raw in _iter_lines(fh):
                n_lines += 1
                w = raw[:LINE_WIN].decode("utf-8", errors="replace")
                for cat, rx in COMPILED.items():
                    if rx.search(w):
                        cats[cat] += 1
                s = w.strip()
                if s.startswith("{") and len(raw) <= JSON_MAX:
                    try:
                        obj = json.loads(raw.decode("utf-8", errors="replace"))
                    except Exception:
                        obj = None
                        st["non_json_lines"] += 1
                    if isinstance(obj, dict):
                        st["json_lines"] += 1
                        t = obj.get("type")
                        if t in MESSAGE_MARKERS or (
                                isinstance(obj.get("message"), dict)
                                and obj["message"].get("role") in MESSAGE_MARKERS):
                            st["message_objects"] += 1
                elif s:
                    st["non_json_lines"] += 1
    except Exception:
        pass
    finally:
        try:
            fh.close()
        except Exception:
            pass
    st["lines"] = n_lines
    try:
        st["bytes"] = os.path.getsize(path)
    except OSError:
        pass
    return st


def merge(a, b):
    for k in ("files", "unreadable", "lines", "json_lines", "non_json_lines",
              "message_objects", "bytes"):
        a[k] += b.get(k, 0)
    for c, v in b["cats"].items():
        a["cats"][c] = a["cats"].get(c, 0) + v


def new_acc():
    return {"files": 0, "unreadable": 0, "lines": 0, "json_lines": 0,
            "non_json_lines": 0, "message_objects": 0, "bytes": 0, "cats": {}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=max(8, (os.cpu_count() or 8) - 2))
    ap.add_argument("--out", default="privacy_scan_full2.json")
    args = ap.parse_args()

    records = []
    with (CORPUS / "manifest.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("status") == "ok":
                records.append((r["path"], r.get("storage_type") or "other",
                                r.get("drive") or "?", r.get("origin") or "?",
                                r.get("runtime") or "?"))
    print(f"[privacy] manifest ok-records: {len(records)}", flush=True)

    partial = HERE / "privacy_partial.jsonl"
    done_paths = {}
    n_resumed_skipped = 0
    if partial.exists():
        with partial.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                    done_paths[redact(d["path"])] = d
                    if d.get("skipped"):
                        n_resumed_skipped += 1
                except Exception:
                    pass
        print(f"[privacy] resuming: {len(done_paths)} files already handled "
              f"({n_resumed_skipped} previously skipped by watchdog)", flush=True)

    todo = [t for t in records if redact(t[0]) not in done_paths]
    t0 = time.time()
    glob_st = new_acc()
    by_drive = collections.defaultdict(new_acc)
    by_origin = collections.defaultdict(new_acc)
    by_runtime = collections.defaultdict(new_acc)
    for d in done_paths.values():
        if d.get("skipped") or "stats" not in d:
            continue
        st = d["stats"]
        merge(glob_st, st)
        merge(by_drive[d.get("drive", "?")], st)
        merge(by_origin[d.get("origin", "?")], st)
        merge(by_runtime[d.get("runtime", "?")], st)

    n_new = 0
    skipped = []
    CHUNK_TIMEOUT = 1200.0   # s per chunk before pool rebuild
    with partial.open("a", encoding="utf-8") as pout:
        ex = ProcessPoolExecutor(max_workers=args.workers)
        try:
            CH = 500
            for i in range(0, len(todo), CH):
                chunk = todo[i:i + CH]
                futs = [(p, s, d, o, r, ex.submit(scan_one, (p, s))) for p, s, d, o, r in chunk]
                t_chunk = time.time()
                processed = set()
                wedged = False
                for p, s, d, o, r, fut in futs:
                    remaining = CHUNK_TIMEOUT - (time.time() - t_chunk)
                    try:
                        st = fut.result(timeout=max(remaining, 0.1))
                    except FutTimeout:
                        wedged = True
                        break
                    except Exception:
                        st = {"files": 1, "unreadable": 1, "lines": 0, "json_lines": 0,
                              "non_json_lines": 0, "message_objects": 0, "bytes": 0,
                              "cats": {}}
                    processed.add(p)
                    merge(glob_st, st)
                    merge(by_drive[d], st)
                    merge(by_origin[o], st)
                    merge(by_runtime[r], st)
                    pout.write(json.dumps({"path": redact(p), "drive": d, "origin": o,
                                           "runtime": r, "stats": st},
                                          separators=(",", ":")) + "\n")
                    n_new += 1
                pout.flush()
                if wedged:
                    for p2, s2, d2, o2, r2, _f in futs:
                        if p2 in processed:
                            continue
                        skipped.append(p2)
                        pout.write(json.dumps({"path": redact(p2), "drive": d2, "origin": o2,
                                               "runtime": r2, "skipped": True},
                                              separators=(",", ":")) + "\n")
                    pout.flush()
                    print(f"[privacy] WATCHDOG: pool wedged at chunk {i}; rebuilding "
                          f"({len(skipped)} files skipped so far)", flush=True)
                    ex.shutdown(wait=False, cancel_futures=True)
                    ex = ProcessPoolExecutor(max_workers=args.workers)
                if (i // CH) % 8 == 0:
                    el = time.time() - t0
                    print(f"[privacy] +{n_new}/{len(todo)} new; total files "
                          f"{glob_st['files']:,}/{len(records)} lines "
                          f"{glob_st['lines']/1e6:.1f}M GB {glob_st['bytes']/1e9:.1f} "
                          f"rate={n_new/el:.1f}/s", flush=True)
        finally:
            ex.shutdown(wait=False, cancel_futures=True)

    total_lines = max(glob_st["lines"], 1)

    def group_out(v):
        return {"files": v["files"], "lines": v["lines"], "message_objects": v["message_objects"],
                "cats": {c: {"lines": x, "line_ratio": round(x / max(v["lines"], 1), 5)}
                         for c, x in sorted(v["cats"].items(), key=lambda kv: -kv[1])}}

    out = {
        "source": "tss/tsis-deepdive/corpus/manifest.jsonl (status=ok records; both drives, "
                  "all runtimes, live+backup+orphan-backup)",
        "files_scanned": glob_st["files"],
        "unreadable_files": glob_st["unreadable"],
        "bytes_scanned": glob_st["bytes"],
        "total_lines": glob_st["lines"],
        "message_objects": glob_st["message_objects"],
        "json_line_rate": round(glob_st["json_lines"] / total_lines, 4),
        "message_object_ratio": round(glob_st["message_objects"] / total_lines, 4),
        "pii_ish": {c: {"lines": v, "line_ratio": round(v / total_lines, 5)}
                    for c, v in sorted(glob_st["cats"].items(), key=lambda kv: -kv[1])},
        "by_drive": {d: group_out(v) for d, v in by_drive.items()},
        "by_origin": {o: group_out(v) for o, v in by_origin.items()},
        "by_runtime_top": {r: group_out(v) for r, v in
                           sorted(by_runtime.items(), key=lambda kv: -kv[1]["lines"])[:25]},
        "note": "aggregate counts/ratios only; no content or matched text is emitted. "
                "Line-mode files (jsonl/zst/gz/plain): every line; each line-equivalent's "
                "first 64KB is pattern-scanned; newline-less payload runs are flushed as "
                "1MB capped segments; JSON detection capped at 1MB. "
                "Binary containers (sqlite + 'other', incl. the 41GB tar): 64KB blocks, "
                "each block counted as a line-equivalent; no JSON detection.",
        "workers": args.workers,
        "seconds": round(time.time() - t0, 1),
        "resumed_files": len(done_paths),
        "new_files": n_new,
        "skipped_by_watchdog": len(skipped) + n_resumed_skipped,
    }
    (HERE / args.out).write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("[privacy] wrote", args.out, "- files:", out["files_scanned"],
          "lines:", out["total_lines"], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
