#!/usr/bin/env python3
"""Assemble the compact trajectory string sent to the annotation API (never persisted).

Same representation contract as the smoke-stage trace_repr.py: counts header +
first-18/last-66 sampled flattened message lines, hard 12,000-char cap.
"""
from datetime import datetime

TRACE_CHAR_CAP = 12_000


def build_trace(sess, file_label):
    n_total = sess["n_msg"]
    lines = []
    dur = ""
    try:
        t0 = datetime.fromisoformat(str(sess["first_ts"]).replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(str(sess["last_ts"]).replace("Z", "+00:00"))
        dur = f"{(t1 - t0).total_seconds() / 60:.0f}min"
    except Exception:
        pass
    hdr = (f"SESSION file={file_label} fmt={sess['format']} msgs={n_total} span={dur} "
           f"user={sess['n_user']} assistant={sess['n_asst']} "
           f"sidechain={sess['n_sidechain']} tool_uses={sess['n_tool_use']} "
           f"tool_results={sess['n_tool_result']}")
    if sess.get("title"):
        hdr += f' title="{sess["title"]}"'
    if sess.get("extra_hdr"):
        hdr += " " + sess["extra_hdr"]
    lines.append(hdr)
    omitted = n_total - len(sess["head"]) - len(sess["tail"])
    for tag, txt in sess["head"]:
        lines.append(f"{tag}: {txt}")
    if omitted > 0:
        lines.append(f"[... {omitted} messages omitted ...]")
    for tag, txt in sess["tail"]:
        lines.append(f"{tag}: {txt}")
    return "\n".join(lines)[:TRACE_CHAR_CAP]
