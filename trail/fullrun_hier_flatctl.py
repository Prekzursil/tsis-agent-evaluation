"""FLAT CONTROL for the hierarchical-judge experiment: the paper's flat
one-shot prompt (run_eval.get_prompt verbatim) + the flat run's exact capping
ladder (fullrun_common.render_capped, budget 160_000 chars = fullrun_gold.py)
but with the SAME model + effort as the hierarchical judge (grok-4.7,
reasoning_effort=xhigh, local bridge). This isolates the ARCHITECTURE effect
(chunked+hierarchical vs flat) from the MODEL effect (glm-5.3/ultra vs grok).

Checkpoint: work/fullrun/hier_outputs/grok-4.7-xhigh-flat/<split>/<fname>.
"""
from __future__ import annotations

import concurrent.futures as cf
import glob
import json
import os
import sys
import time
import traceback

from fullrun_common import (LANE, REPO_BENCH, append_jsonl, render_capped,
                            utcnow, _log)
import fullrun_common as FC

WORK = os.path.join(LANE, "work", "fullrun")
MODEL = "grok-4.7"
EFFORT = "xhigh"
TAG = f"{MODEL}-xhigh-flat"
OUT_ROOT = os.path.join(WORK, "hier_outputs", TAG)
META = os.path.join(WORK, "hier_meta.jsonl")
USAGE = os.path.join(WORK, "usage", "hier.jsonl")
BUDGET_CHARS = 160_000  # identical to fullrun_gold.py line 22

SPLITS = {
    "GAIA": os.path.join(REPO_BENCH, "data", "GAIA"),
    "SWE Bench": os.path.join(REPO_BENCH, "data", "SWE Bench"),
}


def grok_call(prompt: str):
    old = FC.REASONING_EFFORT.get(MODEL)
    FC.REASONING_EFFORT[MODEL] = EFFORT
    try:
        return FC.annotate(prompt, MODEL)
    finally:
        if old is None:
            FC.REASONING_EFFORT.pop(MODEL, None)
        else:
            FC.REASONING_EFFORT[MODEL] = old


def do_one(job):
    split, src = job
    base = os.path.basename(src)
    odir = os.path.join(OUT_ROOT, split)
    os.makedirs(odir, exist_ok=True)
    outf = os.path.join(odir, base)
    if os.path.exists(outf) and os.path.getsize(outf) > 0:
        return ("skip", base, None)
    t0 = time.time()
    raw = open(src, encoding="utf-8", errors="replace").read()
    payload, level = render_capped(raw, BUDGET_CHARS)
    status = "ok"
    usage = {}
    try:
        for attempt in range(3):
            try:
                resp, usage = grok_call(payload)
                break
            except Exception as e:
                if attempt == 2:
                    raise
                time.sleep(20 + attempt * 40)
    except Exception as e:
        status = f"error:{type(e).__name__}"
        append_jsonl(META, {"stage": "flatctl", "file": base, "split": split,
                            "status": status, "level": level,
                            "secs": round(time.time() - t0, 1), "usage": {},
                            "model": MODEL, "effort": EFFORT, "ts": utcnow(),
                            "err": str(e)[:150]})
        return (status, base, None)  # no output file -> retried next sweep
    tmp = outf + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(resp if resp else "No output produced")
    os.replace(tmp, outf)
    append_jsonl(META, {"stage": "flatctl", "file": base, "split": split,
                        "status": status, "level": level,
                        "raw_chars": len(raw), "payload_chars": len(payload),
                        "secs": round(time.time() - t0, 1), "usage": usage,
                        "model": MODEL, "effort": EFFORT, "ts": utcnow()})
    if usage:
        append_jsonl(USAGE, {"stage": "flatctl", "file": base, "model": MODEL,
                             "effort": EFFORT, **usage})
    return (status, base, usage)


def main():
    FC.PROVIDER_INTERVAL["grok"] = float(os.environ.get("HIER_GROK_INTERVAL", "1.0"))
    workers = int(os.environ.get("HIER_WORKERS", "4"))
    jobs = [(s, f) for s, d in SPLITS.items()
            for f in sorted(glob.glob(os.path.join(d, "*.json")))]
    t0 = time.time()
    _log(f"flatctl: {len(jobs)} traces; model={MODEL} effort={EFFORT}; "
         f"budget={BUDGET_CHARS} chars; workers={workers}")
    for sweep in range(1, 13):
        pending = [(s, f) for s, f in jobs if not os.path.exists(
            os.path.join(OUT_ROOT, s, os.path.basename(f)))]
        if not pending:
            _log(f"flatctl sweep {sweep}: ALL CHECKPOINTED")
            break
        _log(f"flatctl sweep {sweep}: {len(pending)} pending")
        done = skip = fail = 0
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(do_one, j) for j in pending]
            for i, fut in enumerate(cf.as_completed(futs), 1):
                try:
                    status, base, usage = fut.result()
                except Exception:
                    status, base, usage = "crash", "?", None
                    traceback.print_exc()
                if status == "skip":
                    skip += 1
                elif status != "ok":
                    fail += 1
                else:
                    done += 1
                if i % 25 == 0 or i == len(pending):
                    _log(f"[f s{sweep} {i}/{len(pending)}] ok={done} skip={skip} "
                         f"fail={fail} elapsed={time.time()-t0:.0f}s")
        if fail:
            _log("flatctl cooldown 180s")
            time.sleep(180)
    _log(f"flatctl FINISHED in {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
