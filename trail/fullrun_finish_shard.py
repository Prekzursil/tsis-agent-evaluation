"""FULL-corpus finish sweep (2026-10-21 mandate) - sharded multi-lane runner.

Supersedes the 2026-10-20 freeze per the current ask ("run your annotator over
the adapter for the FULL canonical set - every UNIQUE parseable session").

Design:
- Stable shard assignment: int(sha256[:12],16) % NSHARDS. Lanes claim disjoint
  shard lists (--shards=0,1,2) so concurrent processes NEVER overlap jobs;
  checkpoint presence (corpus2_labels/<sha16>.json) makes everything resumable.
- Per-lane API key override for NVIDIA NIM account variants: --nvkey=ENV_NAME
  reads the value from the environment or Windows registry (User then
  Machine scope) and injects it as NVIDIA_API_KEY for THIS process only.
  The value is never printed or persisted.
- Reuses fullrun_corpus2 loaders/extractors/trace builder + fullrun_common
  annotate() (paper prompt verbatim, temperature 0, top_p 1, 8k completion)
  and its per-provider pacing + consecutive-429 circuit breaker.
- Rounds: after a pass over the todo list, re-scan for missing labels until
  none remain in this lane's shards (self-heals error:{...} jobs, which are
  deliberately not checkpointed).

Usage:
  python fullrun_finish_shard.py --shards=0,1,2 --model=nvidia/nemotron-3-ultra-550b-a55b \
      --nvkey=NVIDIA_API_KEY_prekzursil --workers=3 --interval=2.0 --tag=u1
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import subprocess
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
NSHARDS = 16  # FIXED for this campaign; never change mid-run


def shard_of(job) -> int:
    return int(job["sha256"][:12], 16) % NSHARDS


def _key_from_registry(name: str) -> str | None:
    for scope in ("User", "Machine"):
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 f'[Environment]::GetEnvironmentVariable("{name}","{scope}")'],
                capture_output=True, text=True, timeout=20)
            v = (r.stdout or "").strip()
            if v:
                return v
        except Exception:
            pass
    return None


def do_job(job, model: str) -> str:
    """fullrun_corpus_multi.do_job_multi logic, verbatim semantics."""
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
        resp, usage = FC.annotate(payload, model)
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
    except Exception:
        # NO checkpoint write: label absence == retryable on the next pass
        return "error"
    return rec.get("status", "error")


def main():
    shards = model = None
    workers = 3
    interval = None
    nvkey = None
    tag = "lane"
    reverse = None  # None | 'even' | 'odd'  (used with --shards=all)
    for a in sys.argv[1:]:
        if a.startswith("--shards="):
            sv = a.split("=", 1)[1]
            shards = ([int(x) for x in sv.split(",") if x != ""]
                      if sv != "all" else "all")
        elif a.startswith("--model="):
            model = a.split("=", 1)[1]
        elif a.startswith("--workers="):
            workers = int(a.split("=")[1])
        elif a.startswith("--interval="):
            interval = float(a.split("=")[1])
        elif a.startswith("--nvkey="):
            nvkey = a.split("=", 1)[1]
        elif a.startswith("--tag="):
            tag = a.split("=", 1)[1]
        elif a.startswith("--reverse="):
            reverse = a.split("=", 1)[1]
    if not shards or not model:
        print(__doc__)
        return 2
    if model not in FC.PROVIDER_ROUTES:
        print(f"unknown model {model}; routes: {sorted(FC.PROVIDER_ROUTES)}")
        return 2
    provider = FC.PROVIDER_ROUTES[model][0]
    if nvkey:
        val = os.environ.get(nvkey) or _key_from_registry(nvkey)
        if not val:
            print(f"FATAL nvkey {nvkey} not found in env or registry")
            return 4
        os.environ["NVIDIA_API_KEY"] = val  # per-process override only
        _log(f"[{tag}] injected per-lane key from {nvkey}")
    if interval is not None:
        FC.PROVIDER_INTERVAL[provider] = interval

    plan = json.load(open(JOBS, encoding="utf-8"))
    if shards == "all":
        mine = list(plan["jobs"])
    else:
        mine = [j for j in plan["jobs"] if shard_of(j) in shards]

    def order(todo):
        """Reverse+parity ordering for 'all'-shard lanes: they chew the job
        list from the tail (biggest files, reached last by forward lanes);
        even/odd parity keeps two reverse lanes off each other's jobs."""
        if reverse:
            todo = todo[::-1]
            todo = todo[0::2] if reverse == "even" else todo[1::2]
        return todo
    t0 = time.time()
    rnd = 0
    final_counts: dict[str, int] = {}
    while True:
        rnd += 1
        todo = order([j for j in mine if not os.path.exists(C2.label_path(j["sha256"]))])
        _log(f"[{tag}] round {rnd}: shards={shards} model={model} "
             f"mine={len(mine)} todo={len(todo)} workers={workers} "
             f"elapsed={time.time()-t0:.0f}s")
        if not todo:
            break
        counts: dict[str, int] = {}
        saturated = False
        try:
            with cf.ThreadPoolExecutor(max_workers=workers) as ex:
                futs = [ex.submit(do_job, j, model) for j in todo]
                for i, fut in enumerate(cf.as_completed(futs), 1):
                    try:
                        st = fut.result()
                    except ProviderSaturated:
                        st = "SATURATED"
                        saturated = True
                    except Exception:
                        st = "crash"
                    counts[st] = counts.get(st, 0) + 1
                    if i % 200 == 0 or i == len(todo):
                        el = time.time() - t0
                        _log(f"[{tag}] [{i}/{len(todo)}] {el:.0f}s "
                             f"rate={i/max(el,1)*60:.1f}/min counts={counts}")
        except KeyboardInterrupt:
            pass
        for k, v in counts.items():
            final_counts[k] = final_counts.get(k, 0) + v
        if saturated:
            _log(f"[{tag}] PROVIDER SATURATED after round {rnd}: {counts}")
            return 3
        # loop again if any labels still missing (error jobs retry); but avoid
        # infinite spins on permanently failing jobs
        still = [j for j in mine if not os.path.exists(C2.label_path(j["sha256"]))]
        if still and rnd < 12:
            _log(f"[{tag}] round {rnd} done ({counts}); {len(still)} still missing, re-rounding")
            continue
        if still:
            _log(f"[{tag}] STOP after {rnd} rounds, {len(still)} persistently missing "
                 f"(hot/unreachable files): {[j['sha256'][:8] for j in still[:5]]}")
        break
    _log(f"[{tag}] FINISHED shards={shards} model={model}: {final_counts} "
         f"in {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
