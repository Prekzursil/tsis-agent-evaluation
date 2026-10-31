#!/usr/bin/env python3
"""Compact in-memory trajectory representation of a Claude Code session journal.

PRIVACY: the returned string is built to be SENT TO THE ANNOTATION API and is NEVER
written to disk by callers. Only counts/ids are persisted elsewhere.

Shape: one line per sampled message,
  [i] USER: <text>            (human turns, truncated)
  [i] USER(meta): <text>      (harness-injected user lines, e.g. command output)
  [i] ASSISTANT: <text>       (assistant prose, truncated)
  [i] ASSISTANT tool_use <NAME>: <input-json, truncated>
  [i] TOOL_RESULT(err): <text, truncated>
  [i] SUB <ROLE> ...          (sidechain / subagent messages)
plus a header line of aggregate counts and "[... N messages omitted ...]" when sampled.
"""
import json
import re
from pathlib import Path

MAX_MSGS = 84            # messages kept when sampling (first 18 + last 66)
HEAD_KEEP, TAIL_KEEP = 18, 66
TEXT_USER, TEXT_ASST = 230, 210     # per-message char caps
TEXT_TOOL, TEXT_RES = 150, 150
TRACE_CHAR_CAP = 12_000  # hard cap on the whole trajectory string

_WS = re.compile(r"\s+")


def _clip(s, n):
    s = _WS.sub(" ", s).strip()
    return s if len(s) <= n else s[: n - 1] + "\u2026"


def _content_str(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = []
        for b in c:
            if isinstance(b, dict):
                if b.get("type") == "text" and isinstance(b.get("text"), str):
                    parts.append(b["text"])
                elif isinstance(b.get("content"), str):
                    parts.append(b["content"])
        return " ".join(parts)
    return ""


def _flatten(o):
    """Yield (role_tag, text) for one journal line, or None to skip."""
    t = o.get("type")
    m = o.get("message")
    sub = "SUB " if o.get("isSidechain") else ""
    if not isinstance(m, dict):
        if t == "summary" and isinstance(o.get("summary"), str):
            return ("SESSION_TITLE", _clip(o["summary"], 120))
        return None
    role = m.get("role")
    c = m.get("content")
    if role == "user":
        if o.get("isMeta"):
            return (f"{sub}USER(meta)", _clip(_content_str(c), 160))
        if isinstance(c, list):
            tr = [b for b in c if isinstance(b, dict) and b.get("type") == "tool_result"]
            if tr:
                b = tr[0]
                err = "err" if b.get("is_error") else "ok"
                txt = _content_str([b]) if not isinstance(b.get("content"), str) else b["content"]
                return (f"{sub}TOOL_RESULT({err})", _clip(txt, TEXT_RES))
        return (f"{sub}USER", _clip(_content_str(c), TEXT_USER))
    if role == "assistant":
        if isinstance(c, list):
            out = []
            for b in c:
                if not isinstance(b, dict):
                    continue
                bt = b.get("type")
                if bt == "text":
                    out.append(("T", _clip(b.get("text", ""), TEXT_ASST)))
                elif bt == "tool_use":
                    try:
                        inp = json.dumps(b.get("input", {}), separators=(",", ":"))
                    except Exception:
                        inp = "?"
                    out.append(("T", f"tool_use {b.get('name','?')}: {_clip(inp, TEXT_TOOL)}"))
            if out:
                return (f"{sub}ASSISTANT", " | ".join(x for _, x in out))
        return (f"{sub}ASSISTANT", _clip(_content_str(c), TEXT_ASST))
    return None


def build_trace(path: Path, meta: dict) -> str:
    """meta = census record (counts). Returns compact trajectory text (never persisted)."""
    msgs = []  # (idx, tag, text)
    title = None
    n_parsed = 0
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                s = line.strip()
                if not s.startswith("{"):
                    continue
                try:
                    o = json.loads(s)
                except Exception:
                    continue
                if not isinstance(o, dict) or not isinstance(o.get("message"), dict):
                    if o.get("type") == "summary" and title is None:
                        title = _clip(str(o.get("summary", "")), 120)
                    continue
                n_parsed += 1
                fl = _flatten(o)
                if fl:
                    msgs.append((n_parsed, fl[0], fl[1]))
    except OSError:
        return ""
    total = len(msgs)
    if total > MAX_MSGS:
        kept = msgs[:HEAD_KEEP] + [(0, "OMIT", f"[... {total - HEAD_KEEP - TAIL_KEEP} messages omitted ...]")]
        kept += msgs[-TAIL_KEEP:]
        msgs = kept
    dur = ""
    try:
        from datetime import datetime
        t0 = datetime.fromisoformat(meta["first_ts"].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(meta["last_ts"].replace("Z", "+00:00"))
        dur = f"{(t1 - t0).total_seconds() / 60:.0f}min"
    except Exception:
        pass
    hdr = (f"SESSION file={Path(meta['rel']).name} msgs={n_parsed} span={dur} "
           f"sidechain={meta['n_sidechain']} tool_uses={meta['n_tool_use']} "
           f"tool_results={meta['n_tool_result']}")
    if title:
        hdr += f" title=\"{title}\""
    lines = [hdr]
    for idx, tag, txt in msgs:
        if tag == "SESSION_TITLE":
            continue
        if tag == "OMIT":
            lines.append(txt)
        else:
            lines.append(f"[{idx}] {tag}: {txt}")
    trace = "\n".join(lines)
    return trace[:TRACE_CHAR_CAP]
