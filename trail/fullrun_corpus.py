"""Phase C - corpus sweep: the team's real Claude session journals
(~/.claude/projects/**/*.jsonl) converted in-memory to repo-format traces and
annotated with glm-5.3-flash (volume tier), checkpointed per trace.

PRIVACY CONTRACT (per the ask): trace CONTENT may go to the API but NEVER into
lane files. Persisted per trace: ids (file basename, project dir name, span
ids), labels (category/location-span-id/impact), counts, aggregates, token
usage. No evidence/description text, no session content, no converted traces
on disk - conversion happens in memory per file and is discarded.
"""
from __future__ import annotations

import concurrent.futures as cf
import glob
import hashlib
import json
import os
import sys
import time
import traceback

from fullrun_common import (FLASH_MODEL, annotate, append_jsonl, get_prompt,
                            render_capped, utcnow, _log)

PROJECTS_ROOT = os.path.expanduser("~/.claude/projects")
WORK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "work", "fullrun")
LABELS = os.path.join(WORK, "corpus_labels")
CENSUS = os.path.join(WORK, "corpus_census.jsonl")
USAGE = os.path.join(WORK, "usage", "corpus.jsonl")

BUDGET_CHARS = 56_000        # ~18-20K est tokens of trace payload per call
                             # (breadth over depth: corpus stats need N traces)
MAX_LINE_CHARS = 2_000_000   # single journal lines above this: skeleton only
HOT_SKIP_SECS = 300          # skip files modified <5 min ago (live sessions)


def file_key(abspath: str) -> str:
    return hashlib.sha1(abspath.encode("utf-8")).hexdigest()[:16]


def hexid(seed: str) -> str:
    return hashlib.md5(seed.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Census (offline): counts only, never content
# ---------------------------------------------------------------------------

def census():
    files = sorted(glob.glob(os.path.join(PROJECTS_ROOT, "**", "*.jsonl"),
                             recursive=True))
    _log(f"census: {len(files)} jsonl files")
    n = 0
    total_bytes = 0
    for p in files:
        try:
            st = os.stat(p)
            with open(p, "rb") as f:
                nl = sum(1 for _ in f)
            total_bytes += st.st_size
            append_jsonl(CENSUS, {
                "key": file_key(p), "project": os.path.basename(os.path.dirname(p)),
                "file": os.path.basename(p), "bytes": st.st_size, "lines": nl,
                "mtime": int(st.st_mtime),
            })
            n += 1
            if n % 2000 == 0:
                _log(f"census {n}/{len(files)} ({total_bytes / 1e9:.2f} GB)")
        except OSError as e:
            append_jsonl(CENSUS, {"key": file_key(p),
                                  "project": os.path.basename(os.path.dirname(p)),
                                  "file": os.path.basename(p), "error": str(e)[:100]})
    _log(f"census done: {n} files, {total_bytes / 1e9:.3f} GB")


# ---------------------------------------------------------------------------
# In-memory converter: Claude session journal -> repo openinference trace
# ---------------------------------------------------------------------------

def _cap(s, n):
    s = str(s)
    return s if len(s) <= n else s[:n] + f"...[TRUNC {len(s) - n}]"


def convert_journal(path: str):
    """Parse a Claude .jsonl session journal and build a repo-format trace dict.
    Returns (trace_dict, stats). Never writes anything."""
    spans = []
    stats = {"lines": 0, "parsed": 0, "unparsed": 0, "oversized": 0,
             "tool": 0, "llm": 0, "system": 0, "human": 0}
    session_key = None
    first_ts = last_ts = None
    pending_tools = {}   # tool_use_id -> span dict
    human_turns = []
    last_assistant_text = ""
    first_user_text = ""

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for idx, line in enumerate(f):
            stats["lines"] += 1
            line = line.strip()
            if not line:
                continue
            oversized = len(line) > MAX_LINE_CHARS
            if oversized:
                stats["oversized"] += 1
                # keep only leading structural fragment for type detection
                line = line[:2000]
            try:
                rec = json.loads(line)
                if not isinstance(rec, dict):
                    raise ValueError("not an object")
            except (json.JSONDecodeError, ValueError):
                if oversized:
                    stats["parsed"] += 1  # skeleton counts as parsed
                    spans.append(_mk_span(session_key or path, idx, "Internal",
                                          {"journal.line": "oversized, elided"},
                                          "OK"))
                else:
                    stats["unparsed"] += 1
                continue
            stats["parsed"] += 1
            if session_key is None:
                session_key = str(rec.get("sessionId") or
                                  os.path.basename(path).rsplit(".", 1)[0])
            ts = rec.get("timestamp")
            if ts:
                first_ts = first_ts or ts
                last_ts = ts
            t = rec.get("type")
            msg = rec.get("message") or {}
            sid = hexid(f"{session_key}:{idx}")

            if t == "assistant":
                content = msg.get("content")
                texts, tools = [], []
                if isinstance(content, str):
                    texts.append(content)
                elif isinstance(content, list):
                    for b in content:
                        if not isinstance(b, dict):
                            continue
                        if b.get("type") == "text":
                            texts.append(b.get("text", ""))
                        elif b.get("type") == "tool_use":
                            tools.append(b)
                if texts:
                    stats["llm"] += 1
                    joined = "\n".join(texts)
                    last_assistant_text = joined or last_assistant_text
                    spans.append({
                        "span_id": sid, "parent_span_id": "agent",
                        "span_name": _cap(msg.get("model") or "LLM", 60),
                        "span_kind": "Internal",
                        "span_attributes": {
                            "openinference.span.kind": "LLM",
                            "llm.model_name": _cap(msg.get("model") or "", 60),
                            "llm.output_messages.0.message.role": "assistant",
                            "llm.output_messages.0.message.content": _cap(joined, 2000),
                        },
                        "status_code": "OK", "status_message": "",
                        "timestamp": ts or "", "duration": 0,
                    })
                for b in tools:
                    stats["tool"] += 1
                    tuid = str(b.get("id") or "")
                    tsp = {
                        "span_id": hexid(f"{session_key}:{idx}:t:{tuid}"),
                        "parent_span_id": "agent",
                        "span_name": _cap(b.get("name") or "tool", 80),
                        "span_kind": "Internal",
                        "span_attributes": {
                            "openinference.span.kind": "TOOL",
                            "input.value": _cap(json.dumps(b.get("input", {}),
                                                           ensure_ascii=True), 1500),
                        },
                        "status_code": "OK", "status_message": "",
                        "timestamp": ts or "", "duration": 0,
                    }
                    spans.append(tsp)
                    if tuid:
                        pending_tools[tuid] = tsp
            elif t == "user":
                content = msg.get("content")
                results, plain = [], []
                if isinstance(content, str):
                    plain.append(content)
                elif isinstance(content, list):
                    for b in content:
                        if not isinstance(b, dict):
                            continue
                        if b.get("type") == "tool_result":
                            results.append(b)
                        elif b.get("type") == "text":
                            plain.append(b.get("text", ""))
                for b in results:
                    tuid = str(b.get("tool_use_id") or "")
                    tsp = pending_tools.pop(tuid, None)
                    out = b.get("content")
                    if isinstance(out, list):
                        out = " ".join(x.get("text", "") if isinstance(x, dict) else str(x)
                                       for x in out)
                    if tsp is not None:
                        tsp["span_attributes"]["output.value"] = _cap(out, 1500)
                        if b.get("is_error"):
                            tsp["status_code"] = "ERROR"
                            tsp["status_message"] = _cap(out, 300)
                if plain:
                    joined = "\n".join(plain)
                    if not first_user_text:
                        first_user_text = joined
                    else:
                        stats["human"] += 1
                        human_turns.append({"idx": idx, "ts": ts or "",
                                            "text": _cap(joined, 400)})
            elif t == "system":
                stats["system"] += 1
                sub = rec.get("subtype") or rec.get("event") or ""
                content = rec.get("content") or ""
                is_err = bool(rec.get("isApiErrorMessage")) or "error" in str(sub).lower()
                if is_err and content:
                    spans.append({
                        "span_id": sid, "parent_span_id": "agent",
                        "span_name": _cap(f"system:{sub}" or "system", 80),
                        "span_kind": "Internal",
                        "span_attributes": {"openinference.span.kind": "INTERNAL",
                                            "system.content": _cap(content, 600)},
                        "status_code": "ERROR",
                        "status_message": _cap(content, 300),
                        "timestamp": ts or "", "duration": 0,
                    })
            # other types (summary, queued-commands, ...) -> counted, not spanned

    trace_id = hexid(f"claude-journal:{session_key or path}")[:32]
    root = {
        "trace_id": trace_id, "span_id": hexid(f"{trace_id}:root"),
        "parent_span_id": None, "span_name": "main", "span_kind": "Internal",
        "span_attributes": {"source": "claude-code-journal",
                            "journal.file": os.path.basename(path)},
        "status_code": "OK", "status_message": "",
        "timestamp": first_ts or "", "duration": 0, "child_spans": [],
    }
    agent = {
        "trace_id": trace_id, "span_id": "agent",
        "parent_span_id": root["span_id"], "span_name": "ClaudeSession.run",
        "span_kind": "Internal",
        "span_attributes": {
            "openinference.span.kind": "AGENT",
            "input.value": _cap(first_user_text, 2000),
            "output.value": _cap(last_assistant_text, 2000),
            "journal.human_turns": len(human_turns),
        },
        "status_code": "OK", "status_message": "",
        "timestamp": first_ts or "", "duration": 0, "child_spans": spans,
    }
    root["child_spans"] = [agent]
    return {"trace_id": trace_id, "spans": [root]}, stats


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------

def extract_json(text):
    """Repo's extract_json_from_text semantics (calculate_scores.py:95-111)."""
    import re
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError("no JSON")
    s = m.group(0)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        while len(s) > 2:
            try:
                return json.loads(s)
            except json.JSONDecodeError:
                s = s[:-1]
        raise ValueError("no valid JSON")


def strip_private(pred: dict):
    """Keep labels/ids/aggregates only - drop evidence/description (privacy)."""
    errors = []
    for e in (pred.get("errors") or [])[:200]:
        if isinstance(e, dict):
            errors.append({"category": str(e.get("category", ""))[:80],
                           "location": str(e.get("location", ""))[:64],
                           "impact": str(e.get("impact", ""))[:8]})
    sc = {}
    scores = pred.get("scores") or []
    if scores and isinstance(scores[0], dict):
        for k in ("reliability_score", "security_score",
                  "instruction_adherence_score", "plan_opt_score", "overall"):
            try:
                sc[k] = float(scores[0].get(k))
            except (TypeError, ValueError):
                sc[k] = None
    return errors, sc


def do_file(path: str):
    key = file_key(path)
    out = os.path.join(LABELS, key + ".json")
    if os.path.exists(out):
        return "skip"
    try:
        mtime = os.stat(path).st_mtime
        if time.time() - mtime < HOT_SKIP_SECS:
            return "hot"
    except OSError:
        return "gone"
    rec = {"key": key, "file": os.path.basename(path),
           "project": os.path.basename(os.path.dirname(path)),
           "model": FLASH_MODEL, "ts": utcnow()}
    try:
        st = os.stat(path)
        rec["bytes"] = st.st_size
        trace, stats = convert_journal(path)
        rec.update({k: stats[k] for k in ("lines", "parsed", "unparsed", "oversized",
                                          "tool", "llm", "system", "human")})
        rec["spans"] = 2 + len(trace["spans"][0]["child_spans"][0]["child_spans"])
        if stats["parsed"] == 0:
            rec["status"] = "empty"
            _write(out, rec)
            return "empty"
        payload, level = render_capped(json.dumps(trace, indent=1), BUDGET_CHARS)
        rec["level"] = level
        resp, usage = annotate(payload, FLASH_MODEL)
        rec["usage"] = usage
        try:
            pred = extract_json(resp)
            errors, sc = strip_private(pred)
            rec["status"] = "ok"
            rec["errors"] = errors
            rec["n_errors"] = len(errors)
            rec["scores"] = sc
        except Exception:
            rec["status"] = "unparseable_response"
            rec["n_errors"] = None
        append_jsonl(USAGE, {"key": key, "model": FLASH_MODEL, **usage})
    except Exception as e:
        # transient failure: NO checkpoint -> a later pass/resume retries it
        return f"error:{type(e).__name__}"
    _write(out, rec)
    return rec.get("status", "error")


def _write(out, rec):
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=True)
    os.replace(tmp, out)


def sweep(limit=None, workers=4, passes=3):
    files = sorted(glob.glob(os.path.join(PROJECTS_ROOT, "**", "*.jsonl"),
                             recursive=True))
    if limit:
        files = files[:limit]
    _log(f"corpus sweep: {len(files)} files, model={FLASH_MODEL}, workers={workers}")
    counts = {}
    t0 = time.time()
    for p in range(max(1, passes)):
        todo = [f for f in files if not os.path.exists(
            os.path.join(LABELS, file_key(f) + ".json"))]
        if not todo:
            break
        _log(f"pass {p + 1}: {len(todo)} files to do")
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(do_file, f): f for f in todo}
            for i, fut in enumerate(cf.as_completed(futs), 1):
                try:
                    st = fut.result()
                except Exception:
                    traceback.print_exc()
                    st = "crash"
                counts[st] = counts.get(st, 0) + 1
                if i % 50 == 0 or i == len(todo):
                    _log(f"pass {p + 1} [{i}/{len(todo)}] "
                         f"elapsed={time.time() - t0:.0f}s counts={counts}")
        if not any(k.startswith("error") for k in counts):
            break
    _log(f"corpus sweep finished: {counts}")
    return counts


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "census":
        census()
    else:
        limit = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[1] == "--limit" else None
        sweep(limit=limit)
