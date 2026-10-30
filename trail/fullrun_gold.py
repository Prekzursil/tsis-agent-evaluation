"""Phase B - run the paper's LLM-annotator over the ENTIRE released gold set
(148 traces: GAIA 117 + SWE Bench 31) with glm-5.3 (full tier).

Checkpoint: work/fullrun/gold_outputs/<model>/<split>/<fname> (one response
file per trace, repo process_file layout). Presence == done -> resumable.
Meta ledger: work/fullrun/gold_meta.jsonl (sizes/caps/usage/status only).
"""
from __future__ import annotations

import concurrent.futures as cf
import glob
import json
import os
import sys
import time
import traceback

from fullrun_common import (LANE, REPO_BENCH, FULL_MODEL,
                            annotate, append_jsonl, render_capped, utcnow, _log)

WORK = os.path.join(LANE, "work", "fullrun")
BUDGET_CHARS = 160_000  # ~57K est tokens; well inside a 128K context
SPLITS = {
    "GAIA": os.path.join(REPO_BENCH, "data", "GAIA"),
    "SWE Bench": os.path.join(REPO_BENCH, "data", "SWE Bench"),
}
GOLD_DIRS = {
    "GAIA": os.path.join(REPO_BENCH, "processed_annotations_gaia"),
    "SWE Bench": os.path.join(REPO_BENCH, "processed_annotations_swe_bench"),
}
OUT_ROOT = os.path.join(WORK, "gold_outputs", FULL_MODEL)
META = os.path.join(WORK, "gold_meta.jsonl")
USAGE = os.path.join(WORK, "usage", "gold.jsonl")


def jobs():
    out = []
    for split, d in SPLITS.items():
        odir = os.path.join(OUT_ROOT, split)
        os.makedirs(odir, exist_ok=True)
        for f in sorted(glob.glob(os.path.join(d, "*.json"))):
            base = os.path.basename(f)
            outf = os.path.join(odir, base)
            gold = os.path.join(GOLD_DIRS[split], base)
            out.append((split, f, outf, gold))
    return out


def do_one(job):
    split, src, outf, gold = job
    base = os.path.basename(src)
    if os.path.exists(outf) and os.path.getsize(outf) > 0:
        return ("skip", base, None)
    if not os.path.exists(gold):
        return ("no_gold", base, None)
    t0 = time.time()
    raw = open(src, "r", encoding="utf-8", errors="replace").read()
    budget = BUDGET_CHARS
    payload, level = render_capped(raw, budget)
    status = "ok"
    usage = {}
    try:
        try:
            resp, usage = annotate(payload, FULL_MODEL)
        except Exception as e:
            msg = str(e).lower()
            if "context" in msg or "maximum" in msg or "too long" in msg or "token" in msg:
                for _ in range(2):
                    budget //= 2
                    payload, level = render_capped(raw, budget)
                    try:
                        resp, usage = annotate(payload, FULL_MODEL)
                        break
                    except Exception:
                        continue
                else:
                    raise
            else:
                raise
    except Exception as e:
        status = f"error:{type(e).__name__}"
        append_jsonl(META, {
            "file": base, "split": split, "status": status, "level": level,
            "raw_chars": len(raw), "payload_chars": len(payload),
            "budget_chars": budget, "secs": round(time.time() - t0, 1),
            "usage": {}, "ts": utcnow(), "model": FULL_MODEL,
            "err": str(e)[:150],
        })
        return (status, base, None)  # NO output file -> resume retries it
    tmp = outf + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(resp if resp else "No output produced")
    os.replace(tmp, outf)
    meta = {
        "file": base, "split": split, "status": status, "level": level,
        "raw_chars": len(raw), "payload_chars": len(payload),
        "budget_chars": budget, "secs": round(time.time() - t0, 1),
        "usage": usage, "ts": utcnow(), "model": FULL_MODEL,
    }
    append_jsonl(META, meta)
    if usage:
        append_jsonl(USAGE, {"file": base, "model": FULL_MODEL, **usage})
    return (status, base, usage)


def main():
    all_jobs = jobs()
    workers = int(os.environ.get("GOLD_WORKERS", "3"))
    _log(f"gold sweep: {len(all_jobs)} traces; model={FULL_MODEL}; budget={BUDGET_CHARS} chars; workers={workers}")
    done = skip = fail = 0
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(do_one, j) for j in all_jobs]
        for i, fut in enumerate(cf.as_completed(futs), 1):
            try:
                status, base, usage = fut.result()
            except Exception:
                status, base, usage = "crash", "?", None
                traceback.print_exc()
            if status == "skip":
                skip += 1
            elif status.startswith("error") or status in ("crash", "no_gold"):
                fail += 1
                _log(f"[{i}/{len(all_jobs)}] {status} {base}")
                if status.startswith("error:RateLimit"):
                    # saturated account: do not churn the job list - cool down
                    _log("rate-saturated: cooling down 300s before next file")
                    time.sleep(300)
            else:
                done += 1
            if i % 10 == 0 or i == len(all_jobs):
                _log(f"[{i}/{len(all_jobs)}] done={done} skip={skip} fail={fail} "
                     f"elapsed={time.time() - t0:.0f}s last={base} "
                     f"usage={usage if usage else ''}")
    _log(f"FINISHED gold sweep: annotated={done} resumed-skip={skip} fail={fail} "
         f"in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
