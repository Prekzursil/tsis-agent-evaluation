"""Phase C v2 - corpus sweep over the FULL canonical (deduplicated) set from
tss/tsis-deepdive/corpus/ (manifest.jsonl + canonical_set.json), ALL runtimes,
annotated with glm-5.3-flash. Checkpointed per content-hash; duplicate paths
inherit their hash's annotation (verify_fullrun.py reconciles via manifest).

Multi-runtime adapter (this file, offline-testable without any API):
  loaders     : jsonl / json / zst (zstandard) / gz / directory (grok session dirs)
  extractors  : claude_journal, codex_rollout, openai_chat_lines (grok),
                zcode_modelio, generic_json (ai-exports / cline / cyberstrike ...)
  trace build : normalized events -> repo openinference span tree (root->agent->children)
  eligibility : >=2 message events or >=1 tool event, else checkpointed not_a_session

PRIVACY CONTRACT: trace content may go to the API but NEVER into lane files.
Persisted per hash: ids (sha256, runtime, origin, storage), event/span counts,
labels (category/location-span-id/impact), rubric scores, token usage.
"""
from __future__ import annotations

import concurrent.futures as cf
import glob
import gzip
import hashlib
import io
import json
import os
import sys
import time
import traceback
import zstandard

import fullrun_common as FC
from fullrun_common import FLASH_MODEL, annotate, append_jsonl, render_capped, utcnow, _log

LANE = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.normpath(os.path.join(LANE, "..", "corpus"))
WORK = os.path.join(LANE, "work", "fullrun")
LABELS = os.path.join(WORK, "corpus2_labels")
USAGE = os.path.join(WORK, "usage", "corpus2.jsonl")
JOBS = os.path.join(WORK, "corpus2_jobs.json")

BUDGET_CHARS = 56_000       # trace payload chars per call (~18-20K tokens)
MAX_READ_BYTES = 64 << 20   # cap any source file at 64 MB (annotation ladder
                            # caps far below this anyway; preserves head)
HOT_SKIP_SECS = 300
SUPPORTED_ST = {"jsonl", "json", "zst", "gz", "directory"}

MSG_ROLES = {"user", "assistant", "system", "developer", "tool", "human", "model", "bot"}


# ---------------------------------------------------------------------------
# Loaders: path -> (text | None, note)
# ---------------------------------------------------------------------------

def load_text(path: str, st: str) -> tuple[str | None, str]:
    try:
        if st == "zst":
            dctx = zstandard.ZstdDecompressor()
            with open(path, "rb") as f:
                with dctx.stream_reader(f, read_size=1 << 20) as sr:
                    data = sr.read(MAX_READ_BYTES)
            return data.decode("utf-8", "replace"), "zst"
        if st == "gz":
            with gzip.open(path, "rb") as f:
                data = f.read(MAX_READ_BYTES)
            return data.decode("utf-8", "replace"), "gz"
        if st == "directory":
            # grok session dir: chat_history.jsonl is the conversation
            for name in ("chat_history.jsonl", "updates.jsonl"):
                p = os.path.join(path, name)
                if os.path.exists(p):
                    with open(p, "rb") as f:
                        data = f.read(MAX_READ_BYTES)
                    return data.decode("utf-8", "replace"), f"dir:{name}"
            return None, "dir:no_history"
        with open(path, "rb") as f:
            data = f.read(MAX_READ_BYTES)
        return data.decode("utf-8", "replace"), "raw"
    except OSError as e:
        return None, f"io:{type(e).__name__}"


# ---------------------------------------------------------------------------
# Event extractors -> list of normalized events
#   {i, ts, kind: user|assistant|system|tool_call|tool_result, name, text,
#    input, output, err, call_id}
# ---------------------------------------------------------------------------

def _mk(i, ts, kind, name="", text="", input_="", output="", err=False, call_id=""):
    return {"i": i, "ts": ts or "", "kind": kind, "name": str(name or "")[:80],
            "text": text or "", "input": input_ or "", "output": output or "",
            "err": bool(err), "call_id": str(call_id or "")}


def _content_texts(content) -> tuple[str, list]:
    """OpenAI/anthropic-ish content -> (joined_text, tool_blocks)."""
    if isinstance(content, str):
        return content, []
    texts, tools = [], []
    if isinstance(content, list):
        for b in content:
            if not isinstance(b, dict):
                texts.append(str(b))
                continue
            t = b.get("type", "")
            if t in ("text", "input_text", "output_text", "thinking") or \
                    (not t and "text" in b):
                texts.append(str(b.get("text", "")))
            elif t == "tool_use":
                tools.append(("call", str(b.get("id", "")), str(b.get("name", "tool")),
                              json.dumps(b.get("input", {}), ensure_ascii=True)[:4000]))
            elif t == "tool_result":
                out = b.get("content")
                if isinstance(out, list):
                    out = " ".join(x.get("text", "") if isinstance(x, dict) else str(x)
                                   for x in out)
                tools.append(("result", str(b.get("tool_use_id", "")), "",
                              str(out)[:4000]))
    return "\n".join(texts), tools


def ev_claude_journal(lines, stats):
    ev = []
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line[:2_000_000])
        except json.JSONDecodeError:
            stats["unparsed"] += 1
            continue
        if not isinstance(rec, dict):
            stats["unparsed"] += 1
            continue
        stats["parsed"] += 1
        ts = rec.get("timestamp") or ""
        t = rec.get("type")
        msg = rec.get("message") or {}
        if t == "assistant" and isinstance(msg, dict):
            text, tools = _content_texts(msg.get("content"))
            if text:
                ev.append(_mk(len(ev), ts, "assistant",
                              name=str(msg.get("model") or "llm"), text=text[:6000]))
            for kind, cid, nm, payload in tools:
                if kind == "call":
                    ev.append(_mk(len(ev), ts, "tool_call", name=nm,
                                  input_=payload, call_id=cid))
        elif t == "user":
            text, tools = _content_texts(msg.get("content") if isinstance(msg, dict)
                                         else rec.get("content"))
            got = False
            for kind, cid, nm, payload in tools:
                if kind == "result":
                    ev.append(_mk(len(ev), ts, "tool_result", output=payload,
                                  call_id=cid))
                    got = True
            if text and not got:
                ev.append(_mk(len(ev), ts, "user", text=text[:4000]))
        elif t == "system":
            sub = str(rec.get("subtype") or rec.get("event") or "")
            content = rec.get("content") or ""
            if (rec.get("isApiErrorMessage") or "error" in sub.lower()) and content:
                ev.append(_mk(len(ev), ts, "system", name=f"system:{sub}"[:80],
                              text=str(content)[:800], err=True))
    return ev


def ev_codex_rollout(lines, stats):
    ev = []
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line[:2_000_000])
        except json.JSONDecodeError:
            stats["unparsed"] += 1
            continue
        if not isinstance(rec, dict):
            continue
        stats["parsed"] += 1
        ts = rec.get("timestamp") or ""
        rt = rec.get("type")
        p = rec.get("payload") or {}
        if rt == "session_meta":
            instr = p.get("instructions") or ""
            ev.append(_mk(len(ev), ts, "user", name="session_instructions",
                          text=str(instr)[:4000]))
        elif rt == "response_item" and isinstance(p, dict):
            pt = p.get("type")
            if pt == "message":
                text, _ = _content_texts(p.get("content"))
                role = str(p.get("role") or "assistant")
                if role in ("user", "developer", "system"):
                    role = "user" if role == "user" else "system"
                ev.append(_mk(len(ev), ts, role if role in ("user", "system", "assistant")
                              else "assistant", name="codex-msg", text=text[:6000]))
            elif pt in ("function_call", "custom_tool_call", "local_shell_call",
                        "web_search_call", "apply_patch_call", "custom_apply_patch_call"):
                ev.append(_mk(len(ev), ts, "tool_call",
                              name=p.get("name") or pt,
                              input_=str(p.get("arguments") or p.get("action") or "")[:4000],
                              call_id=str(p.get("call_id") or p.get("id") or "")))
            elif pt in ("function_call_output", "custom_tool_call_output",
                        "local_shell_call_output", "web_search_call_output"):
                ev.append(_mk(len(ev), ts, "tool_result",
                              output=str(p.get("output") or "")[:4000],
                              call_id=str(p.get("call_id") or "")))
        elif rt == "event_msg" and isinstance(p, dict):
            et = p.get("type")
            if et == "agent_message":
                ev.append(_mk(len(ev), ts, "assistant", name="agent_message",
                              text=str(p.get("message") or "")[:6000]))
            elif et in ("error", "stream_error", "turn_aborted", "background_event"):
                msg = p.get("message") or json.dumps(p, ensure_ascii=True)[:300]
                ev.append(_mk(len(ev), ts, "system", name=f"event:{et}",
                              text=str(msg)[:600], err=True))
    return ev


def ev_openai_chat_lines(lines, stats):
    """grok chat_history.jsonl: {type: system|user|assistant, content}."""
    ev = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line[:2_000_000])
        except json.JSONDecodeError:
            stats["unparsed"] += 1
            continue
        if not isinstance(rec, dict):
            continue
        stats["parsed"] += 1
        role = rec.get("role") or rec.get("type")
        if role not in ("user", "assistant", "system", "developer", "tool"):
            continue
        text, tools = _content_texts(rec.get("content"))
        for kind, cid, nm, payload in tools:
            if kind == "call":
                ev.append(_mk(len(ev), rec.get("ts") or "", "tool_call", name=nm,
                              input_=payload, call_id=cid))
            else:
                ev.append(_mk(len(ev), rec.get("ts") or "", "tool_result",
                              output=payload, call_id=cid))
        if text:
            ev.append(_mk(len(ev), rec.get("ts") or rec.get("timestamp") or "",
                          role if role != "tool" else "user", name="chat",
                          text=text[:6000]))
    return ev


def ev_zcode_modelio(lines, stats):
    """zcode rollout model-io jsonl: {request:{body:{messages}}, response}. """
    ev = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line[:2_000_000])
        except json.JSONDecodeError:
            stats["unparsed"] += 1
            continue
        if not isinstance(rec, dict):
            continue
        stats["parsed"] += 1
        ts = rec.get("completedAt") or ""
        body = ((rec.get("request") or {}).get("body") or {})
        sysmsg = body.get("system")
        if isinstance(sysmsg, str) and sysmsg.strip():
            ev.append(_mk(len(ev), ts, "system", name="system_prompt",
                          text=sysmsg[:2000]))
        for m in body.get("messages") or []:
            if not isinstance(m, dict):
                continue
            role = m.get("role")
            if role not in MSG_ROLES:
                continue
            text, tools = _content_texts(m.get("content"))
            for kind, cid, nm, payload in tools:
                if kind == "call":
                    ev.append(_mk(len(ev), ts, "tool_call", name=nm, input_=payload,
                                  call_id=cid))
            if text:
                ev.append(_mk(len(ev), ts, "user" if role in ("user", "tool") else
                              ("system" if role in ("system", "developer") else "assistant"),
                              name="modelio-in", text=text[:4000]))
        resp = rec.get("response") or {}
        out = ""
        try:
            ch = (resp.get("choices") or [{}])[0]
            out = ch.get("message", {}).get("content") or ch.get("text") or ""
        except Exception:
            pass
        out = out or resp.get("text") or ""
        if out:
            ev.append(_mk(len(ev), ts, "assistant",
                          name=str((rec.get("model") or {}).get("modelId") or "llm"),
                          text=str(out)[:6000]))
        for tc in resp.get("toolCalls") or []:
            if isinstance(tc, dict):
                args = tc.get("args") or tc.get("arguments") or {}
                ev.append(_mk(len(ev), ts, "tool_call",
                              name=tc.get("toolName") or tc.get("name") or "tool",
                              input_=json.dumps(args, ensure_ascii=True)[:4000],
                              call_id=str(tc.get("toolCallId") or tc.get("id") or "")))
    return ev


def ev_gemini_patch(lines, stats):
    """gemini-cli chats: header line + {"$set":{"messages":[...]}} patch lines."""
    ev = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line[:2_000_000])
        except json.JSONDecodeError:
            stats["unparsed"] += 1
            continue
        if not isinstance(rec, dict):
            continue
        stats["parsed"] += 1
        for m in (rec.get("$set") or {}).get("messages") or []:
            r = _msg_event(m, 0, "")
            if r:
                role, name, text, tools, mts = r
                for kind, cid, nm, payload in tools:
                    if kind == "call":
                        ev.append(_mk(len(ev), mts, "tool_call", name=nm,
                                      input_=payload, call_id=cid))
                    else:
                        ev.append(_mk(len(ev), mts, "tool_result", output=payload,
                                      call_id=cid))
                if text:
                    ev.append(_mk(len(ev), m.get("timestamp") or "",
                                  role if role in ("user", "assistant", "system")
                                  else "user", name=name, text=text[:6000]))
    return ev


# --- generic JSON -----------------------------------------------------------

def _msg_event(m, i, ts):
    if not isinstance(m, dict):
        return None
    role = m.get("role") or m.get("type") or m.get("speaker") or m.get("from")
    if role is not None:
        role = str(role).lower()
    if role in ("tool", "function"):
        role = "tool_result" if (m.get("tool_result") or m.get("output") is not None) \
            else "tool_call"
    if role in MSG_ROLES or role in ("tool_call", "tool_result"):
        text, tools = _content_texts(m.get("content") if "content" in m else
                                     (m.get("text") or m.get("message") or ""))
        name = m.get("name") or m.get("tool") or ""
        return (role, name, text, tools,
                str(m.get("ts") or m.get("timestamp") or ts or ""))
    return None


def _generic_walk(obj, ev, ts, depth=0):
    """Find conversation arrays anywhere in a JSON tree (depth-limited)."""
    if depth > 6:
        return
    if isinstance(obj, list):
        # a bare list of messages?
        hits = 0
        for m in obj:
            r = _msg_event(m, 0, ts)
            if r:
                role, name, text, tools, mts = r
                for kind, cid, nm, payload in tools:
                    if kind == "call":
                        ev.append(_mk(len(ev), mts, "tool_call", name=nm,
                                      input_=payload, call_id=cid))
                    else:
                        ev.append(_mk(len(ev), mts, "tool_result", output=payload,
                                      call_id=cid))
                if text:
                    ev.append(_mk(len(ev), mts,
                                  role if role in ("user", "assistant", "system")
                                  else "user", name=name, text=text[:6000]))
                hits += 1
            elif isinstance(m, dict):
                _generic_walk(m, ev, ts, depth + 1)
        if not hits:
            for m in obj:
                if isinstance(m, dict):
                    _generic_walk(m, ev, ts, depth + 1)
    elif isinstance(obj, dict):
        # ChatGPT export mapping trees: {mapping: {nodeId: {message: {author:{role},
        #   content:{parts:[...]}}, create_time}}}
        mapping = obj.get("mapping")
        if isinstance(mapping, dict) and mapping:
            nodes = []
            for node in mapping.values():
                if not isinstance(node, dict):
                    continue
                msg = node.get("message")
                if not isinstance(msg, dict):
                    continue
                ct = msg.get("create_time") or node.get("create_time") or 0
                try:
                    ct = float(ct)
                except (TypeError, ValueError):
                    ct = 0
                nodes.append((ct, msg))
            nodes.sort(key=lambda x: x[0])
            for ct, msg in nodes:
                role = str(((msg.get("author") or {}).get("role")) or "").lower()
                content = msg.get("content") or {}
                parts = content.get("parts") if isinstance(content, dict) else None
                text = " ".join(str(p) for p in (parts or [])
                                if isinstance(p, (str, int, float))) \
                    if parts is not None else (content if isinstance(content, str) else "")
                if role in MSG_ROLES and text and text.strip():
                    ev.append(_mk(len(ev), "", role if role != "tool" else "user",
                                  name="chatgpt", text=text[:6000]))
            if ev:
                return
        for key in ("messages", "turns", "conversation", "chat_history", "history",
                    "chat", "bubbles", "thread"):
            v = obj.get(key)
            if isinstance(v, list) and v:
                _generic_walk(v, ev, ts, depth + 1)
        for v in obj.values():
            if isinstance(v, (dict, list)) and len(ev) < 4000:
                _generic_walk(v, ev, ts, depth + 1)


def ev_generic_json_obj(obj, stats):
    ev = []
    _generic_walk(obj, ev, "")
    stats["parsed"] += 1
    return ev


# ---------------------------------------------------------------------------
# Dispatch: text -> (events, format_name, stats)
# ---------------------------------------------------------------------------

def extract_events(text: str | None, st: str) -> tuple[list, str, dict]:
    stats = {"parsed": 0, "unparsed": 0}
    if not text or not text.strip():
        return [], "empty", stats
    lines = text.splitlines()
    # sniff first non-empty line
    first = next((l for l in lines if l.strip()), "")
    fmt = "?"
    ev: list = []
    head = None
    try:
        head = json.loads(first[:1_000_000]) if first else None
    except json.JSONDecodeError:
        head = None
    if isinstance(head, dict):
        if "payload" in head and "type" in head:
            fmt, ev = "codex_rollout", ev_codex_rollout(lines, stats)
        elif "message" in head and "type" in head:
            fmt, ev = "claude_journal", ev_claude_journal(lines, stats)
        elif ("request" in head and "response" in head):
            fmt, ev = "zcode_modelio", ev_zcode_modelio(lines, stats)
        elif "$set" in head or ("sessionId" in head and
                                ("projectHash" in head or "kind" in head)):
            fmt, ev = "gemini_patch", ev_gemini_patch(lines, stats)
        elif ("type" in head and head.get("type") in
              ("user", "assistant", "system", "developer", "tool")) or \
                ("role" in head and "content" in head):
            fmt, ev = "openai_chat_lines", ev_openai_chat_lines(lines, stats)
    if not ev and fmt == "?":
        # whole-file JSON (pretty-printed arrays/objects, single records, exports)
        try:
            obj = json.loads(text[:16_000_000])
            fmt, ev = "generic_json", ev_generic_json_obj(obj, stats)
        except json.JSONDecodeError:
            if isinstance(head, dict) and "seq" in head and "kind" in head:
                fmt = "event_ledger"  # operational ledger, not a conversation
            else:
                fmt = "unrecognized"
    return ev, fmt, stats


# ---------------------------------------------------------------------------
# Trace builder: events -> repo-format span tree (ids derive from file sha)
# ---------------------------------------------------------------------------

def _hexid(seed: str) -> str:
    return hashlib.md5(seed.encode("utf-8")).hexdigest()[:16]


def _cap(s, n):
    s = str(s)
    return s if len(s) <= n else s[:n] + f"...[TRUNC {len(s) - n}]"


def build_trace(events: list, sha: str, src_note: str):
    trace_id = sha[:32]
    root_id = _hexid(f"{sha}:root")
    spans = []
    pending = {}
    first_user = ""
    last_assistant = ""
    queue_user = ""  # user text awaiting the next LLM span as input
    n_tool = n_llm = n_err = 0
    for e in events:
        sid = _hexid(f"{sha}:e:{e['i']}")
        ts = e["ts"]
        if e["kind"] == "assistant":
            n_llm += 1
            last_assistant = e["text"] or last_assistant
            attrs = {"openinference.span.kind": "LLM",
                     "llm.model_name": _cap(e["name"] or "llm", 60),
                     "llm.output_messages.0.message.role": "assistant",
                     "llm.output_messages.0.message.content": _cap(e["text"], 2000)}
            if queue_user:
                attrs["llm.input_messages.0.message.role"] = "user"
                attrs["llm.input_messages.0.message.content"] = _cap(queue_user, 1500)
                queue_user = ""
            spans.append({"span_id": sid, "parent_span_id": "agent",
                          "span_name": _cap(e["name"] or "LLM", 60),
                          "span_kind": "Internal", "span_attributes": attrs,
                          "status_code": "OK", "status_message": "",
                          "timestamp": ts, "duration": 0})
        elif e["kind"] == "tool_call":
            n_tool += 1
            tsp = {"span_id": sid, "parent_span_id": "agent",
                   "span_name": _cap(e["name"] or "tool", 80), "span_kind": "Internal",
                   "span_attributes": {"openinference.span.kind": "TOOL",
                                       "input.value": _cap(e["input"], 1500)},
                   "status_code": "OK", "status_message": "",
                   "timestamp": ts, "duration": 0}
            spans.append(tsp)
            if e["call_id"]:
                pending[e["call_id"]] = tsp
        elif e["kind"] == "tool_result":
            tsp = pending.pop(e["call_id"], None)
            if tsp is not None:
                tsp["span_attributes"]["output.value"] = _cap(e["output"], 1500)
                if e["err"]:
                    tsp["status_code"] = "ERROR"
                    tsp["status_message"] = _cap(e["output"], 300)
            else:
                n_tool += 1
                spans.append({"span_id": sid, "parent_span_id": "agent",
                              "span_name": _cap(e["name"] or "tool_result", 80),
                              "span_kind": "Internal",
                              "span_attributes": {"openinference.span.kind": "TOOL",
                                                  "output.value": _cap(e["output"], 1500)},
                              "status_code": "ERROR" if e["err"] else "OK",
                              "status_message": _cap(e["output"], 300) if e["err"] else "",
                              "timestamp": ts, "duration": 0})
        elif e["kind"] == "user":
            if not first_user:
                first_user = e["text"]
            else:
                queue_user = e["text"]
        elif e["kind"] == "system":
            if e["err"]:
                n_err += 1
                spans.append({"span_id": sid, "parent_span_id": "agent",
                              "span_name": _cap(e["name"] or "system", 80),
                              "span_kind": "Internal",
                              "span_attributes": {"openinference.span.kind": "INTERNAL",
                                                  "system.content": _cap(e["text"], 600)},
                              "status_code": "ERROR",
                              "status_message": _cap(e["text"], 300),
                              "timestamp": ts, "duration": 0})
    root = {"trace_id": trace_id, "span_id": root_id, "parent_span_id": None,
            "span_name": "main", "span_kind": "Internal",
            "span_attributes": {"source": "trail-corpus-adapter", "adapter.note": src_note},
            "status_code": "OK", "status_message": "", "timestamp":
                (events[0]["ts"] if events else ""), "duration": 0, "child_spans": []}
    agent = {"trace_id": trace_id, "span_id": "agent", "parent_span_id": root_id,
             "span_name": "AgentSession.run", "span_kind": "Internal",
             "span_attributes": {"openinference.span.kind": "AGENT",
                                 "input.value": _cap(first_user, 2000),
                                 "output.value": _cap(last_assistant, 2000)},
             "status_code": "OK", "status_message": "",
             "timestamp": (events[0]["ts"] if events else ""), "duration": 0,
             "child_spans": spans}
    root["child_spans"] = [agent]
    return {"trace_id": trace_id, "spans": [root]}, \
        {"llm": n_llm, "tool": n_tool, "syserr": n_err}


# ---------------------------------------------------------------------------
# Response parsing (repo semantics) + privacy strip
# ---------------------------------------------------------------------------

def extract_json(text):
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


# ---------------------------------------------------------------------------
# Job plan (offline): canonical_set -> interleaved job list
# ---------------------------------------------------------------------------

def build_jobs():
    canon = json.load(open(os.path.join(CORPUS_DIR, "canonical_set.json"),
                           encoding="utf-8"))["annotation_set"]
    buckets: dict[str, list] = {}
    excluded = {}
    for r in canon:
        st = r["storage_type"]
        if st not in SUPPORTED_ST:
            excluded[st] = excluded.get(st, 0) + 1
            continue
        buckets.setdefault(r["runtime"], []).append(r)
    order = []
    iters = {k: iter(sorted(v, key=lambda r: (r.get("size") or 0))) for k, v in buckets.items()}
    keys = sorted(iters, key=lambda k: -len(buckets[k]))
    while True:
        advanced = False
        for k in keys:  # round-robin, biggest bucket first each cycle
            try:
                order.append(next(iters[k]))
                advanced = True
            except StopIteration:
                continue
        if not advanced:
            break
    plan = {"built": utcnow(), "canonical_total": len(canon),
            "supported": len(order), "excluded_by_storage": excluded,
            "bucket_sizes": {k: len(v) for k, v in sorted(buckets.items())},
            "jobs": order}
    with open(JOBS, "w", encoding="utf-8") as f:
        json.dump(plan, f)
    _log(f"jobs: canonical={len(canon)} supported={len(order)} excluded={excluded}")
    return plan


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------

def label_path(sha: str) -> str:
    return os.path.join(LABELS, sha[:16] + ".json")


def do_job(job) -> str:
    sha = job["sha256"]
    out = label_path(sha)
    if os.path.exists(out):
        return "skip"
    rec = {"sha256": sha, "runtime": job["runtime"], "origin": job["origin"],
           "storage_type": job["storage_type"], "size": job.get("size"),
           "path_tail": "\\".join(str(job["path"]).split("\\")[-3:]),
           "model": FLASH_MODEL, "ts": utcnow()}
    try:
        p = job["path"]
        if not os.path.exists(p):
            rec["status"] = "gone"
            _write(out, rec)
            return "gone"
        try:
            if time.time() - os.stat(p).st_mtime < HOT_SKIP_SECS:
                return "hot"
        except OSError:
            return "gone"
        text, note = load_text(p, job["storage_type"])
        rec["load_note"] = note
        events, fmt, stats = extract_events(text, job["storage_type"])
        rec["format"] = fmt
        rec["parsed_lines"] = stats["parsed"]
        rec["unparsed_lines"] = stats["unparsed"]
        rec["events"] = len(events)
        n_msg = sum(1 for e in events if e["kind"] in ("user", "assistant"))
        n_tool = sum(1 for e in events if e["kind"] == "tool_call")
        rec["msg_events"], rec["tool_events"] = n_msg, n_tool
        if n_msg < 2 and n_tool < 1:
            rec["status"] = "not_a_session"
            _write(out, rec)
            return "not_a_session"
        trace, spanstats = build_trace(events, sha, fmt)
        rec["spans"] = 2 + len(trace["spans"][0]["child_spans"][0]["child_spans"])
        rec.update({f"span_{k}": v for k, v in spanstats.items()})
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
        _write(out, rec)  # checkpoint FIRST...
        append_jsonl(USAGE, {"sha": sha[:16], "model": FLASH_MODEL, **usage})
    except Exception as e:
        return f"error:{type(e).__name__}"
    _write(out, rec)
    return rec.get("status", "error")


def _write(out, rec):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=True)
    os.replace(tmp, out)


def census_job(job):
    """Offline eligibility check (no API, no writes)."""
    try:
        p = job["path"]
        if not os.path.exists(p):
            return {"runtime": job["runtime"], "st": job["storage_type"],
                    "fmt": "gone", "n_msg": 0, "n_tool": 0}
        text, note = load_text(p, job["storage_type"])
        events, fmt, stats = extract_events(text, job["storage_type"])
        n_msg = sum(1 for e in events if e["kind"] in ("user", "assistant"))
        n_tool = sum(1 for e in events if e["kind"] == "tool_call")
        return {"runtime": job["runtime"], "st": job["storage_type"], "fmt": fmt,
                "n_msg": n_msg, "n_tool": n_tool}
    except Exception as e:
        return {"runtime": job["runtime"], "st": job["storage_type"],
                "fmt": f"err:{type(e).__name__}", "n_msg": 0, "n_tool": 0}


def run_census():
    plan = json.load(open(JOBS, encoding="utf-8")) if os.path.exists(JOBS) else build_jobs()
    jobs = plan["jobs"]
    _log(f"census: {len(jobs)} jobs (offline, no API)")
    from collections import Counter
    fmt_c, rt_ok, rt_tot = Counter(), Counter(), Counter()
    elig = 0
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        for i, r in enumerate(ex.map(census_job, jobs), 1):
            fmt_c[r["fmt"]] += 1
            rt_tot[r["runtime"]] += 1
            if r["n_msg"] >= 2 or r["n_tool"] >= 1:
                elig += 1
                rt_ok[r["runtime"]] += 1
            if i % 4000 == 0:
                _log(f"census {i}/{len(jobs)} eligible={elig} elapsed={time.time()-t0:.0f}s")
    out = {"generated": utcnow(), "jobs": len(jobs), "eligible_sessions": elig,
           "by_format": dict(fmt_c), "eligible_by_runtime": dict(rt_ok),
           "total_by_runtime": dict(rt_tot)}
    with open(os.path.join(WORK, "corpus2_census.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    _log(f"census done: eligible={elig}/{len(jobs)} in {time.time()-t0:.0f}s")
    print(json.dumps(out["by_format"], indent=1))
    print("eligible:", elig)


def sweep(workers=None, limit=None):
    if os.path.exists(JOBS):
        plan = json.load(open(JOBS, encoding="utf-8"))
    else:
        plan = build_jobs()
    jobs = plan["jobs"]
    if limit:
        jobs = jobs[:limit]
    workers = workers or int(os.environ.get("CORPUS_WORKERS", "6"))
    FC.MIN_START_INTERVAL = float(os.environ.get("CORPUS_MIN_INTERVAL", "3"))
    _log(f"corpus2 sweep: {len(jobs)} canonical jobs, workers={workers}, "
         f"interval={FC.MIN_START_INTERVAL}s, model={FLASH_MODEL}")
    counts = {}
    t0 = time.time()
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(do_job, j): j for j in jobs}
        for i, fut in enumerate(cf.as_completed(futs), 1):
            try:
                st = fut.result()
            except Exception:
                traceback.print_exc()
                st = "crash"
            counts[st] = counts.get(st, 0) + 1
            if i % 100 == 0 or i == len(jobs):
                _log(f"[{i}/{len(jobs)}] elapsed={time.time() - t0:.0f}s counts={counts}")
    _log(f"corpus2 pass finished: {counts}")
    return counts


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "plan":
        build_jobs()
    elif len(sys.argv) > 1 and sys.argv[1] == "census":
        run_census()
    elif len(sys.argv) > 1 and sys.argv[1] == "probe":
        # offline adapter self-test on one MEDIAN-size job per runtime bucket (no API)
        plan = json.load(open(JOBS, encoding="utf-8")) if os.path.exists(JOBS) else build_jobs()
        buckets = {}
        for j in plan["jobs"]:
            buckets.setdefault(j["runtime"], []).append(j)
        for rt, js in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
            js_sorted = sorted(js, key=lambda r: (r.get("size") or 0))
            j = js_sorted[len(js_sorted) // 2]
            text, note = load_text(j["path"], j["storage_type"])
            events, fmt, stats = extract_events(text, j["storage_type"])
            n_msg = sum(1 for e in events if e["kind"] in ("user", "assistant"))
            n_tool = sum(1 for e in events if e["kind"] == "tool_call")
            print(f"{rt:24s} {j['storage_type']:9s} fmt={fmt:18s} "
                  f"events={len(events):5d} msg={n_msg:5d} tool={n_tool:5d} note={note}")
    else:
        limit = None
        workers = None
        for a in sys.argv[1:]:
            if a.startswith("--limit="):
                limit = int(a.split("=")[1])
            if a.startswith("--workers="):
                workers = int(a.split("=")[1])
        sweep(workers=workers, limit=limit)
