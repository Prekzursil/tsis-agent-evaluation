"""Gold sweep FALLBACK lane (2026-10-19): the GLM coding plan is rate-
saturated (429 storms; see work/fullrun/gold_sweep2/3.log), so the ENTIRE
released gold set is ALSO annotated with the other verified top-tier model
nvidia/nemotron-3-ultra-550b-a55b into a SEPARATE output root. The glm-5.3
attempt keeps running in parallel at gentle pace; scoring reports PER-MODEL
batches (each single-model) + coverage, never a silent mix.

Output: work/fullrun/gold_outputs/nvidia-nemotron-3-ultra/<split>/<fname>
Meta:   work/fullrun/gold_meta_nv.jsonl   Usage: usage/gold_nv.jsonl
"""
from __future__ import annotations

import concurrent.futures as cf
import glob
import json
import os
import sys
import time

import fullrun_common as FC
from fullrun_common import LANE, REPO_BENCH, annotate, append_jsonl, render_capped, utcnow, _log

NV_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"
WORK = os.path.join(LANE, "work", "fullrun")
BUDGET_CHARS = 160_000
SPLITS = {
    "GAIA": os.path.join(REPO_BENCH, "data", "GAIA"),
    "SWE Bench": os.path.join(REPO_BENCH, "data", "SWE Bench"),
}
GOLD_DIRS = {
    "GAIA": os.path.join(REPO_BENCH, "processed_annotations_gaia"),
    "SWE Bench": os.path.join(REPO_BENCH, "processed_annotations_swe_bench"),
}
OUT_ROOT = os.path.join(WORK, "gold_outputs", "nvidia-nemotron-3-ultra")
META = os.path.join(WORK, "gold_meta_nv.jsonl")
USAGE = os.path.join(WORK, "usage", "gold_nv.jsonl")


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
            resp, usage = annotate(payload, NV_MODEL)
        except Exception as e:
            msg = str(e).lower()
            if "context" in msg or "maximum" in msg or "too long" in msg or "token" in msg:
                for _ in range(2):
                    budget //= 2
                    payload, level = render_capped(raw, budget)
                    try:
                        resp, usage = annotate(payload, NV_MODEL)
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
            "usage": {}, "ts": utcnow(), "model": NV_MODEL,
            "err": str(e)[:150],
        })
        return (status, base, None)
    tmp = outf + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(resp if resp else "No output produced")
    os.replace(tmp, outf)
    append_jsonl(META, {
        "file": base, "split": split, "status": status, "level": level,
        "raw_chars": len(raw), "payload_chars": len(payload),
        "budget_chars": budget, "secs": round(time.time() - t0, 1),
        "usage": usage, "ts": utcnow(), "model": NV_MODEL,
    })
    if usage:
        append_jsonl(USAGE, {"file": base, "model": NV_MODEL, **usage})
    return (status, base, usage)


def main():
    all_jobs = jobs()
    workers = int(os.environ.get("GOLD_NV_WORKERS", "6"))
    _log(f"gold-nv sweep: {len(all_jobs)} traces; model={NV_MODEL}; "
         f"budget={BUDGET_CHARS} chars; workers={workers}")
    done = skip = fail = 0
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(do_one, j) for j in all_jobs]
        for i, fut in enumerate(cf.as_completed(futs), 1):
            try:
                status, base, usage = fut.result()
            except Exception as e:
                status, base, usage = f"crash:{type(e).__name__}", "?", None
            if status == "skip":
                skip += 1
            elif status.startswith(("error", "crash")) or status == "no_gold":
                fail += 1
                _log(f"[{i}/{len(all_jobs)}] {status} {base} err")
            else:
                done += 1
            if i % 10 == 0 or i == len(all_jobs):
                _log(f"[{i}/{len(all_jobs)}] done={done} skip={skip} fail={fail} "
                     f"elapsed={time.time() - t0:.0f}s last={base}")
    _log(f"FINISHED gold-nv sweep: annotated={done} skip={skip} fail={fail} "
         f"in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
