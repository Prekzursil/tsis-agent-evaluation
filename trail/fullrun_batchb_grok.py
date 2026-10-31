"""TRAIL batch B — SINGLE-MODEL grok-4.7 (effort LOW) pass over the FULL
canonical set (owner expansion order 2026-10-21; reopened 2026-10-30).

Batch semantics (per ask):
- Batch A = the wave1-3 multi-model label set in work/fullrun/corpus2_labels/
  (glm-5.3-flash + nvidia + openrouter + grok shards of waves 1-3) — UNTOUCHED.
- Batch B = grok-4.7 effort LOW over ALL 40,798 canonical targets, stored in
  work/fullrun/corpus2_labels_b/ (one checkpoint per sha256; presence == done).
  * Hashes already labeled grok-4.7 by wave3 (16,991) are COPIED into batch B
    (field batch_b="reused-wave3") — same pipeline, same model, same params;
    copying keeps batch B single-model without re-paying ~17k calls.
  * Everything else is annotated fresh (batch_b="fresh"). not_a_session is an
    OFFLINE deterministic determination (no API call), same as batch A logic.
- 14 workers; the local bridge is the only provider. 429/503 = slot congestion
  -> 2-5s jitter requeue inside fullrun_common.annotate() (owner directive:
  never long sleeps). Usage ledger: work/fullrun/usage/corpus2_b.jsonl.

Resumable: re-running skips existing batch-B checkpoints and re-copies wave3
grok labels. Rounds re-scan until nothing remains in the queue.

Usage:
  python fullrun_batchb_grok.py --workers=14 --tag=batchb
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import sys
import time

import fullrun_common as FC
from fullrun_common import ProviderSaturated, append_jsonl, utcnow, _log
import fullrun_corpus2 as C2

LANE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(LANE, "work", "fullrun")
LABELS_A = os.path.join(WORK, "corpus2_labels")          # batch A (waves 1-3)
LABELS_B = os.path.join(WORK, "corpus2_labels_b")        # batch B (this pass)
USAGE = os.path.join(WORK, "usage", "corpus2_b.jsonl")
JOBS = os.path.join(WORK, "corpus2_jobs.json")
MODEL = "grok-4.7"          # single model for the WHOLE batch
REUSE_MODELS = {"grok-4.7"}  # wave3 labels reusable verbatim (same model+params)


def b_path(sha: str) -> str:
    return os.path.join(LABELS_B, sha[:16] + ".json")


def reuse_wave3(job) -> bool:
    """Copy a wave3 grok-4.7 label into batch B (checkpoint-preserving)."""
    sha = job["sha256"]
    src = os.path.join(LABELS_A, sha[:16] + ".json")
    if not os.path.exists(src):
        return False
    try:
        rec = json.load(open(src, encoding="utf-8"))
    except Exception:
        return False
    if rec.get("model") not in REUSE_MODELS:
        return False
    rec["batch_b"] = "reused-wave3"
    rec["batch_b_ts"] = utcnow()
    C2._write(b_path(sha), rec)
    return True


def do_job(job) -> str:
    """fullrun_finish_shard.do_job semantics, writing into LABELS_B."""
    sha = job["sha256"]
    out = b_path(sha)
    if os.path.exists(out):
        return "skip"
    if reuse_wave3(job):
        return "reused"
    rec = {"sha256": sha, "runtime": job["runtime"], "origin": job["origin"],
           "storage_type": job["storage_type"], "size": job.get("size"),
           "path_tail": "\\".join(str(job["path"]).split("\\")[-3:]),
           "model": MODEL, "batch_b": "fresh", "ts": utcnow()}
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
        payload, level = FC.render_capped(json.dumps(trace, indent=1),
                                          C2.BUDGET_CHARS)
        rec["level"] = level
        resp, usage = FC.annotate(payload, MODEL)
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
        append_jsonl(USAGE, {"sha": sha[:16], "model": MODEL, **usage})
    except ProviderSaturated:
        raise
    except Exception:
        # NO checkpoint write: label absence == retryable on the next pass
        return "error"
    return rec.get("status", "error")


def main():
    workers = 14
    tag = "batchb"
    for a in sys.argv[1:]:
        if a.startswith("--workers="):
            workers = int(a.split("=", 1)[1])
        elif a.startswith("--tag="):
            tag = a.split("=", 1)[1]
    assert MODEL in FC.PROVIDER_ROUTES
    provider = FC.PROVIDER_ROUTES[MODEL][0]
    FC.PROVIDER_INTERVAL[provider] = 0.0  # bridge: no start pacing, slot-limited

    plan = json.load(open(JOBS, encoding="utf-8"))
    jobs = list(plan["jobs"])
    os.makedirs(LABELS_B, exist_ok=True)
    _log(f"[{tag}] batch B start: model={MODEL} effort="
         f"{FC.REASONING_EFFORT[MODEL]} jobs={len(jobs)} workers={workers}")

    t0 = time.time()
    rnd = 0
    final_counts: dict[str, int] = {}
    while True:
        rnd += 1
        done = sum(1 for j in jobs if os.path.exists(b_path(j["sha256"])))
        _log(f"[{tag}] round {rnd}: batchB done={done}/{len(jobs)} "
             f"elapsed={time.time()-t0:.0f}s")
        if done >= len(jobs):
            break
        counts: dict[str, int] = {}
        saturated = False
        try:
            with cf.ThreadPoolExecutor(max_workers=workers) as ex:
                futs = [ex.submit(do_job, j) for j in jobs]
                for i, fut in enumerate(cf.as_completed(futs), 1):
                    try:
                        st = fut.result()
                    except ProviderSaturated:
                        st = "SATURATED"
                        saturated = True
                    except Exception:
                        st = "crash"
                    counts[st] = counts.get(st, 0) + 1
                    if i % 200 == 0:
                        el = time.time() - t0
                        _log(f"[{tag}] [{i}/{len(jobs)}] {el:.0f}s "
                             f"rate={i/max(el,1)*60:.1f}/min counts={counts}")
        except KeyboardInterrupt:
            pass
        for k, v in counts.items():
            final_counts[k] = final_counts.get(k, 0) + v
        if saturated:
            _log(f"[{tag}] PROVIDER SATURATED after round {rnd}: {counts}")
            return 3
        still = [j for j in jobs if not os.path.exists(b_path(j["sha256"]))]
        if still and rnd < 40:
            _log(f"[{tag}] round {rnd} done ({counts}); {len(still)} still "
                 f"missing, re-rounding")
            continue
        if still:
            _log(f"[{tag}] STOP after {rnd} rounds, {len(still)} persistently "
                 f"missing: {[j['sha256'][:8] for j in still[:5]]}")
        break
    done = sum(1 for j in jobs if os.path.exists(b_path(j["sha256"])))
    _log(f"[{tag}] FINISHED batch B: done={done}/{len(jobs)} "
         f"counts={final_counts} in {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
