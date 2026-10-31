#!/usr/bin/env python3
"""Multi-runtime session extractor for the rebuilt corpus (canonical_set.json).

Schema-based detection (runtime labels are NOT trusted for parsing): one pass over
each file's lines, normalized to per-session summaries that carry COUNTS + a sampled
head/tail of flattened message lines. PRIVACY: summaries are built to be sent to the
annotation API and are NEVER persisted by callers; only counts/ids are written out.

Supported formats (detected by line shape, storage-aware decompression):
  claude_journal  - JSONL {message:{role,content}}, isSidechain, timestamp   (claude-code,
                    claude-code-free, vault copies, vm-backup copies, skills-claude-web ...)
  codex_rollout   - JSONL(.zst) {type:response_item|event_msg, payload}      (codex, archived)
  openai_like     - JSONL {type:user|assistant|model|tool_result|reasoning}  (grok chat_history,
                    gemini-cli chats)
  vault_transcript- JSONL {role, text}                                      (vault stores)
  zcode_modelio   - JSONL {request:{body:{messages}}, response}             (zcode rollout)
  chatgpt_export  - whole-file JSON array of conversations with mapping     (ai-exports shards)
  codex_web_tasks - whole-file JSON array {turns:[{role, input_items}]}     (codex.json)

Everything else (sqlite, ledgers, caches, markdown, html, logs) -> no format -> excluded.
"""
import gzip
import io
import json
import re
import zstandard

HEAD_KEEP, TAIL_KEEP = 18, 66
TEXT_USER, TEXT_ASST, TEXT_TOOL, TEXT_RES, TEXT_META = 230, 210, 150, 150, 160
DETECT_WINDOW = 2000  # parsed dict lines scanned before giving up

_WS = re.compile(r"\s+")


def _clip(s, n):
    s = _WS.sub(" ", s).strip()
    return s if len(s) <= n else s[: n - 1] + "\u2026"


def _content_str(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        if all(isinstance(x, str) for x in c):
            return " ".join(x for x in c if x)
        parts = []
        for b in c:
            if isinstance(b, str):
                parts.append(b)
                continue
            if isinstance(b, dict):
                if isinstance(b.get("text"), str):
                    parts.append(b["text"])
                elif isinstance(b.get("content"), str):
                    parts.append(b["content"])
                elif isinstance(b.get("parts"), list):
                    parts.extend(p if isinstance(p, str) else "" for p in b["parts"])
        return " ".join(x for x in parts if x)
    return ""


class SessionAcc:
    """Accumulates counts + sampled flattened lines for one session."""

    def __init__(self, fmt):
        self.fmt = fmt
        self.n_user = 0
        self.n_asst = 0
        self.n_tool_use = 0
        self.n_tool_result = 0
        self.n_sidechain = 0
        self.n_msg = 0
        self.first_ts = None
        self.last_ts = None
        self.title = None
        self.head = []          # first HEAD_KEEP flattened lines
        self.tail = []          # rolling last TAIL_KEEP
        self._n_tail_dropped = 0

    def ts(self, t):
        if not t:
            return
        t = str(t)[:40]
        if self.first_ts is None:
            self.first_ts = t
        self.last_ts = t

    def add(self, tag, text):
        self.n_msg += 1
        if len(self.head) < HEAD_KEEP:
            self.head.append((tag, text))
        if len(self.tail) >= TAIL_KEEP:
            self.tail.pop(0)
            self._n_tail_dropped += 1
        self.tail.append((tag, text))

    def summary(self, extra_hdr):
        return {
            "format": self.fmt,
            "n_user": self.n_user, "n_asst": self.n_asst,
            "n_tool_use": self.n_tool_use, "n_tool_result": self.n_tool_result,
            "n_sidechain": self.n_sidechain, "n_msg": self.n_msg,
            "first_ts": self.first_ts, "last_ts": self.last_ts,
            "title": self.title, "head": self.head, "tail": list(self.tail),
            "n_tail_dropped": self._n_tail_dropped,
            "extra_hdr": extra_hdr,
        }


# ---------------------------------------------------------------- claude journal
def feed_claude(acc, o):
    t = o.get("type")
    sub = "SUB " if o.get("isSidechain") else ""
    if sub:
        acc.n_sidechain += 1
    ts = o.get("timestamp")
    if ts:
        acc.ts(ts)
    if t == "summary" and acc.title is None and isinstance(o.get("summary"), str):
        acc.title = _clip(o["summary"], 120)
        return
    m = o.get("message")
    if not isinstance(m, dict):
        return
    role = m.get("role")
    c = m.get("content")
    if role == "user":
        if o.get("isMeta"):
            acc.n_user += 1
            acc.add(f"{sub}USER(meta)", _clip(_content_str(c), TEXT_META))
            return
        if isinstance(c, list):
            tr = [b for b in c if isinstance(b, dict) and b.get("type") == "tool_result"]
            if tr:
                b = tr[0]
                err = "err" if b.get("is_error") else "ok"
                txt = b["content"] if isinstance(b.get("content"), str) else _content_str([b])
                acc.n_tool_result += 1
                acc.add(f"{sub}TOOL_RESULT({err})", _clip(txt, TEXT_RES))
                return
        acc.n_user += 1
        acc.add(f"{sub}USER", _clip(_content_str(c), TEXT_USER))
        return
    if role == "assistant":
        acc.n_asst += 1
        if isinstance(c, list):
            out = []
            for b in c:
                if not isinstance(b, dict):
                    continue
                bt = b.get("type")
                if bt == "text":
                    out.append(_clip(b.get("text", ""), TEXT_ASST))
                elif bt == "tool_use":
                    try:
                        inp = json.dumps(b.get("input", {}), separators=(",", ":"))
                    except Exception:
                        inp = "?"
                    acc.n_tool_use += 1
                    out.append(f"tool_use {b.get('name', '?')}: {_clip(inp, TEXT_TOOL)}")
            acc.add(f"{sub}ASSISTANT", " | ".join(out))
        else:
            acc.add(f"{sub}ASSISTANT", _clip(_content_str(c), TEXT_ASST))


# ---------------------------------------------------------------- codex rollout
def feed_codex(acc, o):
    t = o.get("type")
    ts = o.get("timestamp")
    if ts:
        acc.ts(ts)
    p = o.get("payload")
    if not isinstance(p, dict):
        return
    pt = p.get("type")
    if t == "response_item":
        if pt == "message":
            role = p.get("role")
            txt = _content_str(p.get("content"))
            if role == "user":
                acc.n_user += 1
                acc.add("USER", _clip(txt, TEXT_USER))
            elif role == "assistant":
                acc.n_asst += 1
                acc.add("ASSISTANT", _clip(txt, TEXT_ASST))
        elif pt == "function_call":
            acc.n_tool_use += 1
            acc.add("ASSISTANT tool_call",
                    f"{p.get('name', '?')}: {_clip(str(p.get('arguments', '')), TEXT_TOOL)}")
        elif pt == "function_call_output":
            acc.n_tool_result += 1
            acc.add("TOOL_RESULT(ok)", _clip(str(p.get("output", "")), TEXT_RES))
        elif pt == "reasoning":
            summ = p.get("summary")
            txt = _content_str(summ) if isinstance(summ, list) else ""
            if txt:
                acc.add("ASSISTANT(reasoning)", _clip(txt, 120))
        elif pt == "reasoning_encrypted":
            acc.add("ASSISTANT(reasoning)", "(encrypted)")
    elif t == "event_msg":
        if pt == "user_message":
            acc.n_user += 1
            acc.add("USER", _clip(str(p.get("message", "")), TEXT_USER))
        elif pt == "agent_message":
            acc.n_asst += 1
            acc.add("ASSISTANT", _clip(str(p.get("message", "")), TEXT_ASST))


# ------------------------------------------------------- openai-like (grok/gemini)
def feed_openai_like(acc, o):
    t = o.get("type")
    ts = o.get("timestamp") or o.get("createTime")
    if ts:
        acc.ts(ts)
    if t == "user":
        acc.n_user += 1
        meta = " (synthetic)" if o.get("synthetic_reason") else ""
        acc.add("USER" + meta, _clip(_content_str(o.get("content")), TEXT_USER))
    elif t in ("assistant", "model", "gemini"):
        acc.n_asst += 1
        txt = _content_str(o.get("content"))
        tcs = o.get("tool_calls")
        parts = [_clip(txt, TEXT_ASST)] if txt else []
        if isinstance(tcs, list):
            for tc in tcs:
                if isinstance(tc, dict):
                    fn = tc.get("function", {}) or {}
                    acc.n_tool_use += 1
                    parts.append(f"tool_use {fn.get('name', '?')}: "
                                 f"{_clip(str(fn.get('arguments', '')), TEXT_TOOL)}")
        acc.add("ASSISTANT", " | ".join(x for x in parts if x) or "(empty)")
    elif t == "tool_result":
        acc.n_tool_result += 1
        acc.add("TOOL_RESULT(ok)", _clip(_content_str(o.get("content")), TEXT_RES))
    elif t == "reasoning":
        summ = o.get("summary")
        txt = _content_str(summ) if isinstance(summ, list) else str(summ or "")
        if txt:
            acc.add("ASSISTANT(reasoning)", _clip(txt, 120))


# ---------------------------------------------------------------- vault transcript
def feed_vault_transcript(acc, o):
    role = o.get("role")
    txt = o.get("text") if isinstance(o.get("text"), str) else _content_str(o.get("content"))
    if role == "user":
        acc.n_user += 1
        acc.add("USER", _clip(txt, TEXT_USER))
    elif role == "assistant":
        acc.n_asst += 1
        acc.add("ASSISTANT", _clip(txt, TEXT_ASST))


# ---------------------------------------------------------------- zcode model-io
def feed_zcode_modelio(acc, o, state):
    """Track the LAST request carrying body.messages; that is the full history."""
    req = o.get("request")
    if isinstance(req, dict) and isinstance(req.get("body"), dict) \
            and isinstance(req["body"].get("messages"), list):
        state["last_messages"] = req["body"]["messages"]
    ts = o.get("startedAt") or o.get("completedAt")
    if ts:
        acc.ts(ts)


def finish_zcode_modelio(acc, state):
    msgs = state.get("last_messages") or []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        c = m.get("content")
        if role == "user":
            if isinstance(c, list):
                tr = [b for b in c if isinstance(b, dict) and b.get("type") == "tool_result"]
                if tr:
                    b = tr[0]
                    acc.n_tool_result += 1
                    acc.add("TOOL_RESULT(ok)", _clip(_content_str([b]), TEXT_RES))
                    continue
            acc.n_user += 1
            acc.add("USER", _clip(_content_str(c), TEXT_USER))
        elif role == "assistant":
            acc.n_asst += 1
            if isinstance(c, list):
                out = []
                for b in c:
                    if not isinstance(b, dict):
                        continue
                    if b.get("type") == "text":
                        out.append(_clip(b.get("text", ""), TEXT_ASST))
                    elif b.get("type") == "tool_use":
                        try:
                            inp = json.dumps(b.get("input", {}), separators=(",", ":"))
                        except Exception:
                            inp = "?"
                        acc.n_tool_use += 1
                        out.append(f"tool_use {b.get('name', '?')}: {_clip(inp, TEXT_TOOL)}")
                acc.add("ASSISTANT", " | ".join(out))
            else:
                acc.add("ASSISTANT", _clip(_content_str(c), TEXT_ASST))


# ---------------------------------------------------------------- detection
def detect_format(sample_dicts):
    """Decide format from a sample of parsed dicts (first lines of the file)."""
    has_claude = has_codex = has_openai = has_vault = has_zcode = 0
    for o in sample_dicts:
        if not isinstance(o, dict):
            continue
        m = o.get("message")
        if isinstance(m, dict) and m.get("role") in ("user", "assistant"):
            has_claude += 1
            continue
        if o.get("type") in ("response_item", "event_msg", "turn_context", "session_meta",
                             "compacted"):
            has_codex += 1
            continue
        if o.get("type") in ("user", "assistant", "model", "gemini", "tool_result",
                             "reasoning") and "content" in o:
            has_openai += 1
            continue
        if o.get("role") in ("user", "assistant") and ("text" in o or "content" in o):
            has_vault += 1
            continue
        if ("request" in o and isinstance(o["request"], dict)) or \
                ("response" in o and isinstance(o["response"], dict)):
            has_zcode += 1
    if has_claude:
        return "claude_journal"
    if has_codex:
        return "codex_rollout"
    if has_openai:
        return "openai_like"
    if has_vault:
        return "vault_transcript"
    if has_zcode:
        return "zcode_modelio"
    return None


def _open_lines(path, storage_type):
    """Yield decoded text lines for jsonl/zst/gz/plain files."""
    if storage_type == "zst" or str(path).endswith(".zst"):
        with open(path, "rb") as raw:
            dctx = zstandard.ZstdDecompressor(max_window_size=1 << 31)
            with dctx.stream_reader(raw) as rdr:
                yield from io.TextIOWrapper(rdr, encoding="utf-8", errors="replace")
    elif storage_type == "gz" or str(path).endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            yield from fh
    else:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            yield from fh


def extract_path(path, storage_type, size_hint=0):
    """Extract session summaries from one file. Returns (format, [summaries]) or (None, [])."""
    # whole-file JSON containers (chatgpt export shards / codex web tasks)
    if storage_type == "json" or str(path).endswith(".json"):
        try:
            if size_hint and size_hint > 80_000_000:
                return None, []
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                obj = json.load(fh)
        except Exception:
            obj = None
        if isinstance(obj, list) and obj and isinstance(obj[0], dict) \
                and "mapping" in obj[0]:
            return "chatgpt_export", _chatgpt_shard(obj)
        if isinstance(obj, list) and obj and isinstance(obj[0], dict) \
                and "turns" in obj[0]:
            return "codex_web_tasks", _codex_web(obj)
        # generic {messages:[...]} container
        if isinstance(obj, dict) and isinstance(obj.get("messages"), list):
            acc = SessionAcc("json_messages")
            for m in obj["messages"]:
                feed_vault_transcript(acc, m if isinstance(m, dict) else {})
            if acc.n_user and acc.n_asst:
                return "json_messages", [acc.summary("")]
            return None, []
        if isinstance(obj, list):
            return None, []
        if isinstance(obj, dict):
            return None, []

    # JSONL-family: detect on a sample, then feed all lines
    sample = []
    fmt = None
    try:
        it = _open_lines(path, storage_type)
        state = {}
        acc = SessionAcc("?")
        n_dict = 0
        for line in it:
            s = line.strip()
            if not s.startswith("{") and not s.startswith("["):
                continue
            if fmt == "zcode_modelio" and '"messages"' not in s:
                continue  # speed: only conversation-bearing request lines matter
            try:
                o = json.loads(s)
            except Exception:
                continue
            if not isinstance(o, dict):
                continue
            n_dict += 1
            if fmt is None:
                sample.append(o)
                if len(sample) >= 60 or n_dict >= DETECT_WINDOW:
                    fmt = detect_format(sample)
                    if fmt is None:
                        return None, []
                    acc = SessionAcc(fmt)
                    for so in sample:
                        _feed(acc, fmt, so, state)
                continue
            _feed(acc, fmt, o, state)
            if n_dict >= 2_000_000:
                break
        if fmt is None:
            if sample:
                fmt = detect_format(sample)
                if fmt is None:
                    return None, []
                acc = SessionAcc(fmt)
                state = {}
                for so in sample:
                    _feed(acc, fmt, so, state)
            else:
                return None, []
        if fmt == "zcode_modelio":
            finish_zcode_modelio(acc, state)
        if acc.n_user and acc.n_asst:
            return fmt, [acc.summary("")]
        return None, []
    except OSError:
        return None, []
    except zstandard.ZstdError:
        return None, []


def _feed(acc, fmt, o, state):
    if fmt == "claude_journal":
        feed_claude(acc, o)
    elif fmt == "codex_rollout":
        feed_codex(acc, o)
    elif fmt == "openai_like":
        feed_openai_like(acc, o)
    elif fmt == "vault_transcript":
        feed_vault_transcript(acc, o)
    elif fmt == "zcode_modelio":
        feed_zcode_modelio(acc, o, state)


def extract_directory(path):
    """Directory-shaped session (grok): prefer chat_history.jsonl inside."""
    import os
    try:
        names = os.listdir(path)
    except OSError:
        return None, []
    for cand in ("chat_history.jsonl", "updates.jsonl"):
        if cand in names:
            fmt, summ = extract_path(os.path.join(path, cand), "jsonl")
            if summ:
                return ("grok_dir_" + fmt) if fmt else None, summ
            return None, []
    return None, []


# ---------------------------------------------------------- chatgpt export shard
def _chatgpt_shard(convs):
    out = []
    for ci, conv in enumerate(convs):
        acc = SessionAcc("chatgpt_export")
        acc.title = _clip(str(conv.get("title") or ""), 120)
        msgs = []
        for node in (conv.get("mapping") or {}).values():
            if not isinstance(node, dict):
                continue
            m = node.get("message")
            if not isinstance(m, dict):
                continue
            role = (m.get("author") or {}).get("role")
            if role not in ("user", "assistant"):
                continue
            ct = (m.get("content") or {})
            txt = _content_str(ct.get("parts")) if ct.get("parts") else _content_str(ct)
            ct_time = m.get("create_time")
            if not txt:
                continue
            msgs.append((ct_time or 0, role, txt))
        msgs.sort(key=lambda x: (x[0] if isinstance(x[0], (int, float)) else 0))
        for t, role, txt in msgs:
            acc.ts(t)
            if role == "user":
                acc.n_user += 1
                acc.add("USER", _clip(txt, TEXT_USER))
            else:
                acc.n_asst += 1
                acc.add("ASSISTANT", _clip(txt, TEXT_ASST))
        if acc.n_user and acc.n_asst:
            out.append(acc.summary(""))
    return out


def _codex_web(tasks):
    out = []
    for task in tasks:
        acc = SessionAcc("codex_web_tasks")
        acc.title = _clip(str(task.get("title") or ""), 120)
        for turn in task.get("turns") or []:
            if not isinstance(turn, dict):
                continue
            role = turn.get("role")
            items = turn.get("input_items")
            if not items and role != "user":
                items = turn.get("output_items")
            texts = []
            for it in items or []:
                if isinstance(it, dict):
                    texts.append(_content_str(it.get("content")))
            txt = " ".join(x for x in texts if x)
            if not txt:
                continue
            if role in ("user", "developer", "system"):
                acc.n_user += 1
                acc.add("USER", _clip(txt, TEXT_USER))
            else:
                acc.n_asst += 1
                acc.add("ASSISTANT", _clip(txt, TEXT_ASST))
        if acc.n_user and acc.n_asst:
            out.append(acc.summary(""))
    return out
