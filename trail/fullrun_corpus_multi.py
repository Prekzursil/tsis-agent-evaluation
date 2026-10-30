"""Phase C v3 - corpus sweep, MULTI-PROVIDER edition (2026-10-19).

The GLM coding plan is rate-saturated on its own, so the remaining canonical
jobs are split into fixed provider slices; each slice runs on ONE model end-to
-end (batch stays single-model for interpretability) with per-provider pacing
and a consecutive-429 circuit breaker (process exits on saturation instead of
burning the account; resume re-runs the slice).

Slice assignment is STABLE: job position % N_SLICES in corpus2_jobs.json
(interleaved round-robin job list -> every slice spans every runtime).

Usage: python fullrun_corpus_multi.py --slice=1 --model=nvidia/nemotron-3-super-120b-a12b \
           [--workers=6] [--interval=1.2] [--limit=500]
Reuse of fullrun_corpus2.do_job internals: loaders/extractors/trace builder are
imported from that module (offline-testable); only routing + labels differ.
Label checkpoints land in the same corpus2_labels/ dir (sha-keyed, unique).
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import sys
import time
import traceback

import fullrun_common as FC
from fullrun_common import ProviderSaturated, append_jsonl, utcnow, _log
import fullrun_corpus2 as C2

LANE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(LANE, "work", "fullrun")
LABELS = os.path.join(WORK, "corpus2_labels")
USAGE = os.path.join(WORK, "usage", "corpus2.jsonl")
JOBS = os.path.join(WORK, "corpus2_jobs.json")
N_SLICES = 4  # fixed: 0=glm-flash (after gold) 1=nv-super 2=nv-lightning 3=or-lightning


def do_job_multi(job, model: str) -> str:
    """fullrun_corpus2.do_job with model routing + saturation abort."""
    sha = job["sha256"]
    out = C2.label_path(sha)
    if os.path.exists(out):
        return "skip"
    rec = {"sha256": sha, "runtime": job["runtime"], "origin": job["origin"],
           "storage_type": job["storage_type"], "size": job.get("size"),
           "path_tail": "\\".join(str(job["path"]).split("\\")[-3:]),
           "model": model, "ts": utcnow()}
    try:
        p = job["path"]
        if not os.path.exists(p):
            rec["status"] = "gone"
            C2._write(out, rec)
            return "gone"
        try:
            if time.time() - os.stat(p).st_mtime < C2.HOT_SKIP_SECS:
                return "hot"
        except OSError:
            return "gone"
        text, note = C2.load_text(p, job["storage_type"])
        rec["load_note"] = note
        events, fmt, stats = C2.extract_events(text, job["storage_type"])
        rec["format"] = fmt
        rec["parsed_lines"] = stats["parsed"]
        rec["unparsed_lines"] = stats["unparsed"]
        rec["events"] = len(events)
        n_msg = sum(1 for e in events if e["kind"] in ("user", "assistant"))
        n_tool = sum(1 for e in events if e["kind"] == "tool_call")
        rec["msg_events"], rec["tool_events"] = n_msg, n_tool
        if n_msg < 2 and n_tool < 1:
            rec["status"] = "not_a_session"
            C2._write(out, rec)
            return "not_a_session"
        trace, spanstats = C2.build_trace(events, sha, fmt)
        rec["spans"] = 2 + len(trace["spans"][0]["child_spans"][0]["child_spans"])
        rec.update({f"span_{k}": v for k, v in spanstats.items()})
        payload, level = FC.render_capped(json.dumps(trace, indent=1), C2.BUDGET_CHARS)
        rec["level"] = level
        resp, usage = FC.annotate(payload, model)   # routes via PROVIDER_ROUTES
        rec["usage"] = usage
        try:
            pred = C2.extract_json(resp)
            errors, sc = C2.strip_private(pred)
            rec["status"] = "ok"
            rec["errors"] = errors
            rec["n_errors"] = len(errors)
            rec["scores"] = sc
        except Exception:
            rec["status"] = "unparseable_response"
            rec["n_errors"] = None
        C2._write(out, rec)  # checkpoint first...
        append_jsonl(USAGE, {"sha": sha[:16], "model": model, **usage})
    except ProviderSaturated:
        raise
    except Exception as e:
        # NO checkpoint write: label absence == retryable on the next pass
        return f"error:{type(e).__name__}"
    return rec.get("status", "error")


def main():
    slice_i = workers = limit = None
    model = None
    for a in sys.argv[1:]:
        if a.startswith("--slice="):
            slice_i = int(a.split("=")[1])
        elif a.startswith("--model="):
            model = a.split("=")[1]
        elif a.startswith("--workers="):
            workers = int(a.split("=")[1])
        elif a.startswith("--limit="):
            limit = int(a.split("=")[1])
    if slice_i is None or model is None:
        print(__doc__)
        return 2
    if model not in FC.PROVIDER_ROUTES:
        print(f"unknown model {model}; routes: {sorted(FC.PROVIDER_ROUTES)}")
        return 2
    workers = workers or 6
    FC.PROVIDER_INTERVAL[FC.PROVIDER_ROUTES[model][0]] = float(
        os.environ.get("MULTI_INTERVAL", FC.PROVIDER_INTERVAL.get(
            FC.PROVIDER_ROUTES[model][0], 3.0)))

    plan = json.load(open(JOBS, encoding="utf-8"))
    jobs = [j for i, j in enumerate(plan["jobs"]) if i % N_SLICES == slice_i]
    todo = [j for j in jobs if not os.path.exists(C2.label_path(j["sha256"]))]
    if limit:
        todo = todo[:limit]
    _log(f"slice {slice_i}/{N_SLICES} model={model}: {len(jobs)} jobs, "
         f"{len(jobs) - len(todo)} done, running {len(todo)}, workers={workers}")
    counts: dict[str, int] = {}
    t0 = time.time()
    try:
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(do_job_multi, j, model) for j in todo]
            for i, fut in enumerate(cf.as_completed(futs), 1):
                try:
                    st = fut.result()
                except ProviderSaturated:
                    st = "SATURATED"
                    # drain already-submitted futures cheaply: they will each
                    # hit the breaker fast (consec counter shared) and abort.
                except Exception:
                    traceback.print_exc()
                    st = "crash"
                counts[st] = counts.get(st, 0) + 1
                if i % 100 == 0 or i == len(todo):
                    el = time.time() - t0
                    _log(f"s{slice_i} [{i}/{len(todo)}] {el:.0f}s "
                         f"rate={i / max(el, 1) * 60:.1f}/min counts={counts}")
    except KeyboardInterrupt:
        pass
    _log(f"slice {slice_i} pass finished: {counts} in {time.time() - t0:.0f}s")
    return 0 if "SATURATED" not in counts else 3


if __name__ == "__main__":
    sys.exit(main())
