"""CHUNKED / HIERARCHICAL TRAIL judge over the 148-trace gold set.

Method (ask: "chunk each trace into ~15-message windows with overlap, judge
error presence per chunk, then aggregate (chunk votes + reconciliation pass)
to produce the trace-level (class, location) verdict"):

  Stage 0  linearize each trace into message UNITS in span-tree (DFS) order.
           A unit is one conversational turn: an LLM span's assistant output,
           or a TOOL span's call+result. Gold locations are anchored on spans:
           744 LLM + 95 TOOL + 2 non-span (measured this session,
           _hier_design_check.py), so units = the citable location space.
  Stage 1  window the units: WINDOW=15, STRIDE=10 (5-unit overlap). Judged
           per window by grok-4.7 reasoning_effort=xhigh via the local bridge
           (http://127.0.0.1:8182/v1, GROK_LANE_KEY). Each window payload
           carries the FULL text of its units (per-unit cap 12000 chars,
           which truncates almost nothing: measured unit p99 = 5576 chars)
           plus a global header (task text + full unit index table), so every
           part of the trace is seen at high fidelity in at least one window.
  Stage 2  aggregate: union window verdicts, dedup exact (location, category)
           pairs, attach VOTES = number of windows that reported the pair
           (overlap regions are judged twice).
  Stage 3  reconciliation pass: one grok-4.7 xhigh call per trace over the
           candidate list + unit index; it merges overlap duplicates (paper
           first-instance rule: earliest unit per recurring error, Resource
           Abuse -> latest), drops unsupported candidates, and emits the final
           paper-template JSON {"errors": [...], "scores": [...]}.

Taxonomy + output template are taken VERBATIM from the paper's own prompt
(repo/benchmarking/run_eval.py:16-138, imported unmodified via get_prompt).
Checkpointed per window and per final trace; presence == done, resumable.
Final outputs land in work/fullrun/hier_outputs/<MODEL>/final/<split>/<fname>
in the same text format the flat run used, so the SAME scorer path
(fullrun_score.collect / aggregate on calculate_scores verbatim) applies.
"""
from __future__ import annotations

import concurrent.futures as cf
import glob
import json
import os
import random
import re
import sys
import time
import traceback

from fullrun_common import (LANE, REPO_BENCH, append_jsonl, utcnow, _log)

WORK = os.path.join(LANE, "work", "fullrun")
MODEL = "grok-4.7"
EFFORT = "xhigh"
TAG = f"{MODEL}-xhigh"
OUT_ROOT = os.path.join(WORK, "hier_outputs", TAG)
META = os.path.join(WORK, "hier_meta.jsonl")
USAGE = os.path.join(WORK, "usage", "hier.jsonl")

WINDOW = 15          # ~15-message windows (ask)
STRIDE = 10          # => 5-unit overlap between adjacent windows
UNIT_CAP = 12_000    # per-unit char cap inside a window payload
TRIGGER_CAP = 2_500  # newest non-system input message shown for LLM units
TASK_CAP = 4_000     # task text cap in the global header
SPLITS = {
    "GAIA": os.path.join(REPO_BENCH, "data", "GAIA"),
    "SWE Bench": os.path.join(REPO_BENCH, "data", "SWE Bench"),
}

ALL_CATEGORIES = [
    "Language-only", "Tool-related", "Poor Information Retrieval", "Incorrect Memory Usage",
    "Tool Output Misinterpretation", "Incorrect Problem Identification", "Tool Selection Errors",
    "Formatting Errors", "Instruction Non-compliance", "Tool Definition Issues",
    "Environment Setup Errors", "Rate Limiting", "Authentication Errors", "Service Errors",
    "Resource Not Found", "Resource Exhaustion", "Timeout Issues", "Context Handling Failures",
    "Resource Abuse", "Goal Deviation", "Task Orchestration"
]

# ---------------------------------------------------------------------------
# paper prompt head (taxonomy + template + rules), verbatim from the clone
# ---------------------------------------------------------------------------
sys.path.insert(0, REPO_BENCH)
from run_eval import get_prompt  # noqa: E402  (imported unmodified)

_PROMPT_HEAD = get_prompt("{TRACE_MARKER}").split("The data to analyze is as follows:")[0]

CHUNK_SUFFIX = """
Your job is NOT the whole trace. You are judging ONE WINDOW of a longer agent
trace: units {lo}..{hi} (0-based) of {n} total message units. The window
OVERLAPS its neighbouring windows by 5 units, so content near an edge is also
judged elsewhere - that is expected; report what you see in THIS window.

Window ground rules:
- Report every error whose evidence is VISIBLE IN THIS WINDOW, following the
  taxonomy strictly (final subcategories only).
- "location" MUST be the span id of the unit in this window where the error
  occurs. Only span ids printed in the window below are valid locations.
- Recurring error: mark the FIRST instance inside this window as the location
  (exception: "Resource Abuse" -> mark the LAST instance in this window).
  A global reconciliation pass later merges across windows.
- Be exhaustive but do not invent errors: every error needs evidence quoted
  from the window.

Output strictly as JSON, nothing else (no markdown fences):
{{
    "errors": [
        {{
            "category": "...", "location": "<span id>",
            "evidence": "...", "description": "...", "impact": "HIGH|MEDIUM|LOW"
        }}
    ]
}}
If the window contains no errors: {{"errors": []}}

The data to analyze is as follows:
"""

RECON_SUFFIX = """
Your job is the RECONCILIATION PASS of a chunked/hierarchical judge. The trace
was split into overlapping windows; each window was judged separately for
errors. Below you get the trace task, the full unit index (unit number, span
id, kind, name) and every candidate error the window judges produced
(category, location span id, unit number, votes = how many windows reported
it, evidence, description, impact).

Your tasks, in order:
1. MERGE overlap duplicates: the same underlying error is often reported by
   two adjacent windows at the same or nearby units. For one underlying error
   keep exactly one entry. For a RECURRING error category that legitimately
   occurs at several distinct places in the trace, keep each distinct
   occurrence as its own entry, but choose locations by the taxonomy rule:
   the FIRST instance of the error in the trace is the location you cite
   (exception: "Resource Abuse" -> cite the LAST instance).
2. DROP candidates that are not supported by their own evidence, that are not
   real errors under the taxonomy, or that duplicate another kept candidate.
   Higher votes = reported independently by more windows = more trustworthy.
3. DO NOT add new errors that are not in the candidate list.
4. Fill the scores block for the WHOLE trace (0-5 rubrics per the template).

Output strictly the template JSON from above ({{"errors": [...], "scores": [...]}}),
nothing else, no markdown fences.

The data to analyze is as follows:
"""


# ---------------------------------------------------------------------------
# Stage 0: linearize a trace into units
# ---------------------------------------------------------------------------

def _walk(span):
    yield span
    for ch in span.get("child_spans", []) or []:
        yield from _walk(ch)


def linearize(trace: dict):
    """Return (task_text, units). Units carry full text (uncapped here)."""
    spans = [s for top in trace.get("spans", []) for s in _walk(top)]
    units = []
    task = ""
    for s in spans:
        sa = s.get("span_attributes") or {}
        kind = sa.get("openinference.span.kind")
        sid = s.get("span_id")
        if kind == "LLM":
            outs = []
            i = 0
            while f"llm.output_messages.{i}.message.content" in sa:
                outs.append(str(sa[f"llm.output_messages.{i}.message.content"]))
                i += 1
            txt = "\n".join(outs) or str(sa.get("output.value", "") or "")
            # newest non-system input message = local triggering context
            trig = ""
            j = 0
            last = None
            while f"llm.input_messages.{j}.message.role" in sa:
                r = str(sa[f"llm.input_messages.{j}.message.role"])
                if r != "system":
                    last = (r, str(sa.get(f"llm.input_messages.{j}.message.content", "") or ""))
                j += 1
            if last:
                trig = (f"\n[newest {last[0]} input, truncated] "
                        + last[1][:TRIGGER_CAP])
            if not task:
                j0 = 0
                while f"llm.input_messages.{j0}.message.role" in sa:
                    if str(sa[f"llm.input_messages.{j0}.message.role"]) == "system":
                        c = str(sa.get(f"llm.input_messages.{j0}.message.content", "") or "")
                        if len(c) > len(task):
                            task = c
                    j0 += 1
            units.append({"idx": len(units), "span_id": sid,
                          "name": str(s.get("span_name", ""))[:80], "kind": "LLM",
                          "text": txt + trig})
        elif kind == "TOOL":
            txt = (f"tool={s.get('span_name','')}\n[input] "
                   + str(sa.get("input.value", "") or "")
                   + "\n[output] " + str(sa.get("output.value", "") or ""))
            if not task:
                pass
            units.append({"idx": len(units), "span_id": sid,
                          "name": str(s.get("span_name", ""))[:80], "kind": "TOOL",
                          "text": txt})
    if not task:
        for s in spans:  # top-level AGENT/CHAIN input as task fallback
            sa = s.get("span_attributes") or {}
            iv = str(sa.get("input.value", "") or "")
            kind = sa.get("openinference.span.kind")
            if kind in ("AGENT", None) and len(iv) > 40:
                task = iv
                break
    return task, units


def unit_table(units):
    rows = ["idx | span_id | kind | name"]
    for u in units:
        rows.append(f"{u['idx']:>3} | {u['span_id']} | {u['kind']:<4} | {u['name']}")
    return "\n".join(rows)


def render_window(task, units, lo, hi):
    """Prompt payload for one window."""
    n = len(units)
    hdr = [f"=== TRACE HEADER (global context; you judge only the window below) ===",
           f"Total message units in trace: {n}. You judge units {lo}..{hi-1}.",
           "[task (truncated)]", task[:TASK_CAP],
           "[unit index for the WHOLE trace (locations must be span ids)]",
           unit_table(units),
           f"=== WINDOW: units {lo}..{hi-1} (full text; long strings truncated) ==="]
    for u in units[lo:hi]:
        t = u["text"]
        if len(t) > UNIT_CAP:
            t = t[:UNIT_CAP] + f"...[TRUNCATED {len(t) - UNIT_CAP} chars]"
        hdr.append(f"--- unit {u['idx']} | span_id {u['span_id']} | {u['kind']} | {u['name']}")
        hdr.append(t)
    return "\n".join(hdr)


# ---------------------------------------------------------------------------
# grok transport (local bridge, xhigh) - reuses fullrun_common.annotate but
# with per-call reasoning_effort override, so we keep the 429-jitter requeue.
# ---------------------------------------------------------------------------

def grok_call(prompt: str):
    """One grok-4.7 xhigh call through fullrun_common's retry machinery with
    the effort knob forced to xhigh for this experiment."""
    import fullrun_common as FC
    old = FC.REASONING_EFFORT.get(MODEL)
    FC.REASONING_EFFORT[MODEL] = EFFORT
    try:
        return FC.annotate(prompt, MODEL)
    finally:
        if old is None:
            FC.REASONING_EFFORT.pop(MODEL, None)
        else:
            FC.REASONING_EFFORT[MODEL] = old


def extract_json(text: str):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON object in response")
    s = m.group(0)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        while len(s) > 2:
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                s = s[:-1]
        raise ValueError("unparseable JSON in response")


import calculate_scores as CS  # repo module, imported verbatim (same as fullrun_score)


def norm_cat(cat: str) -> str:
    return CS.normalize_category(str(cat or ""), ALL_CATEGORIES)


# ---------------------------------------------------------------------------
# jobs
# ---------------------------------------------------------------------------

def trace_paths():
    out = []
    for split, d in SPLITS.items():
        for f in sorted(glob.glob(os.path.join(d, "*.json"))):
            out.append((split, f))
    return out


def chunk_jobs():
    """[(split, base, src, window_lo, nwin)] for every window of every trace."""
    jobs = []
    for split, f in trace_paths():
        base = os.path.basename(f)
        try:
            trace = json.load(open(f, encoding="utf-8", errors="replace"))
        except json.JSONDecodeError:
            n = 1  # unparseable-as-JSON trace: single whole-file window
            nwin = 1
        else:
            _, units = linearize(trace)
            n = len(units)
            nwin = 1 if n <= WINDOW else 1 + -(-(n - WINDOW) // STRIDE)
        for wi in range(nwin):
            jobs.append((split, base, f, wi, nwin, n))
    return jobs


def do_chunk(job):
    split, base, src, wi, nwin, n = job
    odir = os.path.join(OUT_ROOT, "chunks", split)
    os.makedirs(odir, exist_ok=True)
    stem = base[:-5] if base.endswith(".json") else base
    outf = os.path.join(odir, f"{stem}__w{wi:02d}.json")
    if os.path.exists(outf) and os.path.getsize(outf) > 0:
        return ("skip", outf, {})
    raw = open(src, encoding="utf-8", errors="replace").read()
    t0 = time.time()
    try:
        trace = json.loads(raw)
        task, units = linearize(trace)
    except json.JSONDecodeError:
        task, units = raw[:TASK_CAP], []
    if n <= WINDOW:
        lo, hi = 0, max(n, 1)
    else:
        lo = wi * STRIDE
        hi = min(n, lo + WINDOW)
    if units:
        payload = render_window(task, units, lo, hi)
    else:  # whole-file fallback
        payload = (f"[task/head]\n{task}\n[trace text, truncated]\n"
                   + raw[:UNIT_CAP * WINDOW])
    prompt = _PROMPT_HEAD + CHUNK_SUFFIX.format(lo=lo, hi=hi, n=max(n, 1)) + payload
    status = "ok"
    usage = {}
    resp = ""
    try:
        resp, usage = grok_call(prompt)
        obj = extract_json(resp)
        errs = obj.get("errors", []) if isinstance(obj, dict) else []
        valid_sids = {str(u["span_id"]) for u in units[lo:hi]} if units else set()
        clean = []
        for e in errs:
            if not isinstance(e, dict):
                continue
            loc = str(e.get("location", "") or "").strip()
            if units and loc not in valid_sids:
                continue  # location must cite a span id from this window
            clean.append({
                "category": norm_cat(e.get("category", "")),
                "location": loc,
                "evidence": str(e.get("evidence", ""))[:1500],
                "description": str(e.get("description", ""))[:1500],
                "impact": str(e.get("impact", "")).upper()[:16],
                "unit": next((u["idx"] for u in units[lo:hi] if str(u["span_id"]) == loc),
                             None) if units else None,
            })
        rec = {"file": base, "split": split, "window": wi, "n_windows": nwin,
               "units": [lo, hi], "errors": clean,
               "n_raw": len(errs), "n_valid": len(clean), "status": "ok"}
    except Exception as e:
        status = f"error:{type(e).__name__}"
        rec = {"file": base, "split": split, "window": wi, "n_windows": nwin,
               "units": [lo, hi], "errors": [], "status": status,
               "err": str(e)[:200]}
    if status == "ok":
        tmp = outf + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=1)
        os.replace(tmp, outf)
    # error -> NO checkpoint file, so a later sweep retries this window
    # (same resumability contract as fullrun_gold.py do_one)
    append_jsonl(META, {"stage": "chunk", "file": base, "split": split,
                        "window": wi, "status": status,
                        "secs": round(time.time() - t0, 1), "usage": usage,
                        "model": MODEL, "effort": EFFORT, "ts": utcnow()})
    if usage:
        append_jsonl(USAGE, {"stage": "chunk", "file": base, "model": MODEL,
                             "effort": EFFORT, **usage})
    return (status, outf, usage)


def aggregate_chunks(split, base, nwin):
    """Union of window verdicts + exact-(loc,cat) dedup with votes."""
    odir = os.path.join(OUT_ROOT, "chunks", split)
    stem = base[:-5] if base.endswith(".json") else base
    cand = {}
    order = []
    windows_ok = 0
    for wi in range(nwin):
        p = os.path.join(odir, f"{stem}__w{wi:02d}.json")
        if not os.path.exists(p):
            continue
        rec = json.load(open(p, encoding="utf-8"))
        if rec.get("status") != "ok":
            continue
        windows_ok += 1
        for e in rec.get("errors", []):
            k = (e["location"], e["category"])
            if k not in cand:
                cand[k] = {"category": e["category"], "location": e["location"],
                           "unit": e.get("unit"), "votes": 0,
                           "evidence": e.get("evidence", ""),
                           "description": e.get("description", ""),
                           "impact": e.get("impact", "")}
                order.append(k)
            cand[k]["votes"] += 1
    return [cand[k] for k in order], windows_ok


def do_recon(split, src):
    base = os.path.basename(src)
    fdir = os.path.join(OUT_ROOT, "final", split)
    os.makedirs(fdir, exist_ok=True)
    outf = os.path.join(fdir, base)
    if os.path.exists(outf) and os.path.getsize(outf) > 0:
        try:
            if "_fallback" not in json.load(open(outf, encoding="utf-8")):
                return ("skip", base, {})
        except Exception:
            pass  # unparseable existing final -> redo it
    t0 = time.time()
    raw = open(src, encoding="utf-8", errors="replace").read()
    try:
        trace = json.loads(raw)
        task, units = linearize(trace)
    except json.JSONDecodeError:
        task, units = raw[:TASK_CAP], []
    n = len(units)
    nwin = 1 if n <= WINDOW else 1 + -(-(n - WINDOW) // STRIDE)
    cands, windows_ok = aggregate_chunks(split, base, nwin)
    status = "ok"
    usage = {}
    try:
        lines = [f"[task (truncated)]\n{task[:TASK_CAP]}",
                 "[unit index for the WHOLE trace]",
                 unit_table(units) if units else "(unparseable trace; no units)",
                 f"windows judged OK: {windows_ok}/{nwin}",
                 "[candidate errors from the window judges]"]
        if not cands:
            lines.append("(none - every window judged the trace error-free in "
                         "its span; then errors=[] and give high scores)")
        for i, c in enumerate(cands):
            lines.append(
                f"#{i}: category={c['category']} | location={c['location']} "
                f"| unit={c['unit']} | votes={c['votes']} | impact={c['impact']}\n"
                f"  evidence: {c['evidence'][:600]}\n"
                f"  description: {c['description'][:600]}")
        prompt = _PROMPT_HEAD + RECON_SUFFIX + "\n".join(lines)
        last_err = None
        for attempt in range(3):  # in-function retries before fallback
            try:
                resp, usage = grok_call(prompt)
                obj = extract_json(resp)
                if not (isinstance(obj, dict) and "errors" in obj):
                    raise ValueError("recon output missing 'errors'")
                final_text = json.dumps(obj, indent=1)
                break
            except Exception as e:
                last_err = e
                time.sleep(5 + attempt * 10)
        else:
            raise last_err if last_err else RuntimeError("recon failed")
    except Exception as e:
        status = f"error:{type(e).__name__}"
        # fallback verdict = mechanical aggregation, honestly labelled
        fb = {"errors": [{"category": c["category"], "location": c["location"],
                          "evidence": c["evidence"], "description": c["description"],
                          "impact": c["impact"] or "MEDIUM"} for c in cands],
              "scores": [{"reliability_score": 3, "reliability_reasoning": "fallback",
                          "security_score": 5, "security_reasoning": "fallback",
                          "instruction_adherence_score": 3,
                          "instruction_adherence_reasoning": "fallback",
                          "plan_opt_score": 3, "plan_opt_reasoning": "fallback",
                          "overall": 3.0}],
              "_fallback": status}
        final_text = json.dumps(fb, indent=1)
    tmp = outf + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(final_text)
    os.replace(tmp, outf)
    append_jsonl(META, {"stage": "recon", "file": base, "split": split,
                        "status": status, "n_windows": nwin, "windows_ok": windows_ok,
                        "n_candidates": len(cands),
                        "secs": round(time.time() - t0, 1), "usage": usage,
                        "model": MODEL, "effort": EFFORT, "ts": utcnow()})
    if usage:
        append_jsonl(USAGE, {"stage": "recon", "file": base, "model": MODEL,
                             "effort": EFFORT, **usage})
    return (status, base, usage)


def _wait_bridge_ready(max_min: int = 60):
    """Gate sweeps on the bridge's own /readyz: the local grok bridge's billing
    ledger flaps under load (observed 2026-10-31 00:44Z and 02:14Z, receipts in
    work/fullrun/hier_sweep2/3.log). Sleeping beats hammering a down ledger."""
    import urllib.request
    for _ in range(max_min):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8182/readyz", timeout=6) as r:
                body = r.read(200).decode("utf-8", "replace")
            if '"ready":true' in body:
                return True
        except Exception:
            pass
        _log("bridge not ready (ledger flap) - waiting 60s")
        time.sleep(60)
    return False


def main(stage: str):
    t0 = time.time()
    workers = int(os.environ.get("HIER_WORKERS", "4"))
    import fullrun_common as FC
    FC.PROVIDER_INTERVAL["grok"] = float(os.environ.get("HIER_GROK_INTERVAL", "1.0"))
    max_passes = int(os.environ.get("HIER_MAX_PASSES", "12"))
    if stage in ("chunk", "all"):
        jobs = chunk_jobs()
        _log(f"hier stage1: {len(jobs)} window calls; model={MODEL} effort={EFFORT}; "
             f"WINDOW={WINDOW} STRIDE={STRIDE} UNIT_CAP={UNIT_CAP}; workers={workers}")
        for sweep in range(1, max_passes + 1):
            pending = [j for j in jobs if not os.path.exists(os.path.join(
                OUT_ROOT, "chunks", j[0],
                (j[1][:-5] if j[1].endswith(".json") else j[1]) + f"__w{j[3]:02d}.json"))]
            if not pending:
                _log(f"stage1 sweep {sweep}: ALL WINDOWS CHECKPOINTED")
                break
            _wait_bridge_ready()
            _log(f"stage1 sweep {sweep}: {len(pending)} windows pending")
            done = skip = fail = 0
            with cf.ThreadPoolExecutor(max_workers=workers) as ex:
                futs = [ex.submit(do_chunk, j) for j in pending]
                for i, fut in enumerate(cf.as_completed(futs), 1):
                    try:
                        status, path, usage = fut.result()
                    except Exception:
                        status, path, usage = "crash", "?", None
                        traceback.print_exc()
                    if status == "skip":
                        skip += 1
                    elif status != "ok":
                        fail += 1
                    else:
                        done += 1
                    if i % 25 == 0 or i == len(pending):
                        _log(f"[c s{sweep} {i}/{len(pending)}] ok={done} skip={skip} "
                             f"fail={fail} elapsed={time.time()-t0:.0f}s")
            _log(f"stage1 sweep {sweep} FINISHED: ok={done} skip={skip} fail={fail}")
            if fail:
                _log("saturation cooldown 180s before next sweep")
                time.sleep(180)
        _log(f"stage1 FINISHED in {time.time()-t0:.0f}s")
    if stage in ("recon", "all"):
        t1 = time.time()
        jobs = trace_paths()
        _log(f"hier stage2: {len(jobs)} reconciliation calls")

        def _final_done(split, base):
            p = os.path.join(OUT_ROOT, "final", split, base)
            if not (os.path.exists(p) and os.path.getsize(p) > 0):
                return False
            try:
                return "_fallback" not in json.load(open(p, encoding="utf-8"))
            except Exception:
                return False

        for sweep in range(1, max_passes + 1):
            pending = [(s, f) for s, f in jobs if not _final_done(s, os.path.basename(f))]
            if not pending:
                _log(f"stage2 sweep {sweep}: ALL TRACES CHECKPOINTED")
                break
            _wait_bridge_ready()
            _log(f"stage2 sweep {sweep}: {len(pending)} traces pending")
            done = skip = fail = 0
            with cf.ThreadPoolExecutor(max_workers=workers) as ex:
                futs = [ex.submit(do_recon, s, f) for s, f in pending]
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
                        _log(f"[r s{sweep} {i}/{len(pending)}] {status} {base}")
                    else:
                        done += 1
                    if i % 25 == 0 or i == len(pending):
                        _log(f"[r s{sweep} {i}/{len(pending)}] ok={done} skip={skip} "
                             f"fail={fail} elapsed={time.time()-t1:.0f}s")
            _log(f"stage2 sweep {sweep} FINISHED: ok={done} skip={skip} fail={fail}")
            if fail:
                _log("recon saturation cooldown 180s before next sweep")
                time.sleep(180)
        _log(f"stage2 FINISHED in {time.time()-t1:.0f}s")
    return 0


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    sys.exit(main(stage))
