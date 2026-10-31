#!/usr/bin/env python3
"""Final pass over the 19 wedge-prone binaries scan_skipped.py could not finish
(runs 3-5 died: ProcessPoolExecutor workers broke -> BrokenProcessPool).

Design (fixes the actual failure mode):
- ONE OS subprocess per file (no shared pool): a worker death can only lose
  that single file; the parent retries it or records it honestly.
- Block-mode files (17 sqlite .vscdb) use scan_one_fast.py -- an EXACTLY
  equivalent matcher (required-literal prefilters + per-line split for the 8
  no-newline patterns + exact '@'-decomposition for the quadratic email
  pattern); equivalence proven by scan_one_fast.py verify on a FULL real file
  plus adversarial synthetic email cases.
- Line-mode file (the 4.29GB jsonl) would use the original scan_one -- but
  BOTH remaining non-sqlite files (41GB tar, 4.29GB jsonl) are GONE from disk
  since the manifest: the original scan_one records unreadable=1 for missing
  paths, and this driver does exactly that (no invented stats).
- Results appended incrementally to scan_skipped_results.jsonl in the SAME
  record shape as scan_skipped.py; then the ledger is rewritten
  (stats-preferred) and privacy_scan_full2.json regenerated with
  scan_skipped.regen_aggregate (imported unchanged).
- UNSKIPPABLE: asserts zero 'skipped' entries remain in the ledger at exit.

Usage: python scan_skipped_seq.py [--concurrency 12]
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from privacy_scan_corpus import redact  # noqa: E402
from scan_skipped import regen_aggregate  # noqa: E402 (same aggregate fn)
from privacy_scan import PATTERNS  # noqa: E402 (categories order)

CORPUS = HERE.parent.parent / "corpus"
RESULTS_PATH = HERE / "scan_skipped_results.jsonl"
TMP = HERE / "fast_tmp"
PY = sys.executable
BINARY_STORAGE = {"sqlite", "other"}
BINARY_SUFFIX = {".db", ".vscdb", ".dat", ".tar", ".pdf", ".png", ".jpg", ".zip",
                 ".exe", ".dll", ".so", ".bin", ".mp4", ".webm", ".woff2"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=12)
    args = ap.parse_args()
    TMP.mkdir(exist_ok=True)

    man = {}
    with (CORPUS / "manifest.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("status") == "ok":
                man[redact(r["path"])] = r

    entries = {}
    with (HERE / "privacy_partial.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except Exception:
                continue
            p = e["path"]
            if p in entries and "stats" in entries[p] and "stats" not in e:
                continue
            entries[p] = e

    already = set()
    if RESULTS_PATH.exists():
        with RESULTS_PATH.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    already.add(json.loads(line)["path"])
                except Exception:
                    pass

    home = Path.home().name
    todo = [p for p, e in entries.items()
            if (e.get("skipped") or "stats" not in e) and p in man
            and p not in already]
    todo.sort(key=lambda p: man[p].get("size") or 0)  # small first
    print(f"[seq] remaining skipped: {len(todo)}", flush=True)

    outf = RESULTS_PATH.open("a", encoding="utf-8")
    results = {}
    n_gone = 0
    t0 = time.time()
    running = {}  # proc -> (path, tmpjson, submitted)

    def reap(block=True):
        import subprocess as sp
        nonlocal results
        done_now = []
        for proc, (p, tmpj, ts) in list(running.items()):
            rc = proc.poll()
            if rc is None and block:
                continue
            if rc is None:
                continue
            del running[proc]
            if rc == 0 and Path(tmpj).exists():
                st = json.loads(Path(tmpj).read_text(encoding="utf-8"))
                _, _, drive, origin, runtime = (man[p].get("storage_type"),
                                                man[p].get("size"),
                                                man[p].get("drive"),
                                                man[p].get("origin"),
                                                man[p].get("runtime"))
                rec = {"path": p, "drive": drive, "origin": origin,
                       "runtime": runtime, "stats": st}
                results[p] = rec
                outf.write(json.dumps(rec, separators=(",", ":")) + "\n")
                outf.flush()
                print(f"[seq] DONE {p.replace('<USER>', '~')[-60:]} "
                      f"({time.time()-t0:.0f}s elapsed)", flush=True)
            else:
                print(f"[seq] FAILED rc={rc} {p.replace('<USER>', '~')[-60:]}",
                      flush=True)
            done_now.append(p)
        return done_now

    import subprocess as sp
    for p in todo:
        real = p.replace("<USER>", home)
        m = man[p]
        # wait for a free slot
        while len(running) >= args.concurrency:
            reap()
            if len(running) >= args.concurrency:
                time.sleep(2.0)
        drive, origin, runtime = m.get("drive"), m.get("origin"), m.get("runtime")
        storage = m.get("storage_type") or "other"
        suffix = ("." + real.rsplit(".", 1)[-1].lower()) if "." in real else ""
        block_mode = storage in BINARY_STORAGE or suffix in BINARY_SUFFIX
        import os
        if not os.path.exists(real):
            # original scan_one semantics for a missing file: unreadable=1
            st = {"files": 1, "unreadable": 1, "lines": 0, "json_lines": 0,
                  "non_json_lines": 0, "message_objects": 0, "bytes": 0,
                  "mode": "block" if block_mode else "line",
                  "cats": {c: 0 for c in PATTERNS}}
            rec = {"path": p, "drive": drive, "origin": origin,
                   "runtime": runtime, "stats": st}
            results[p] = rec
            outf.write(json.dumps(rec, separators=(",", ":")) + "\n")
            outf.flush()
            n_gone += 1
            print(f"[seq] GONE (recorded unreadable=1) {real[-60:]}", flush=True)
            continue
        tmpj = str(TMP / (p.split("\\")[-1][:40] + f".{abs(hash(p)) % 99999}.json"))
        if block_mode:
            cmd = [PY, str(HERE / "scan_one_fast.py"), "scan", real, storage, tmpj]
        else:
            # line-mode heavy file: original instrument, isolated subprocess
            code = (f"import sys,json;sys.path.insert(0,{str(HERE)!r});"
                    f"from privacy_scan_corpus import scan_one;"
                    f"st=scan_one(({real!r},{storage!r}));"
                    f"json.dump(st,open({tmpj!r},'w'))")
            cmd = [PY, "-c", code]
        proc = sp.Popen(cmd, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
        running[proc] = (p, tmpj, time.time())
        print(f"[seq] START {real[-60:]} ({len(running)} running)", flush=True)
    while running:
        reap()
        if running:
            time.sleep(2.0)
    outf.close()

    # ---- rewrite ledger + regenerate aggregate (same code path as scan_skipped)
    for p, rec in results.items():
        entries[p] = rec
    with (HERE / "privacy_partial.jsonl").open("w", encoding="utf-8") as fh:
        for p, e in entries.items():
            fh.write(json.dumps(e, separators=(",", ":")) + "\n")
    out = regen_aggregate(entries)
    (HERE / "privacy_scan_full2.json").write_text(json.dumps(out, indent=2),
                                                  encoding="utf-8")
    still = [p for p, e in entries.items() if e.get("skipped") or "stats" not in e]
    print(f"[seq] DONE: scanned={len(results)} gone={n_gone} "
          f"still_skipped={len(still)} of {len(entries)}; "
          f"aggregate files={out['files_scanned']:,} "
          f"lines={out['total_lines']:,} msgs={out['message_objects']:,}", flush=True)
    if still:
        print(f"[seq] UNSKIPPABLE VIOLATION: {still[:5]}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
