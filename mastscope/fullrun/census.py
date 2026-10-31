#!/usr/bin/env python3
"""Full-corpus census of Claude session journals. METADATA ONLY - no content persisted.

For every *.jsonl under <root> (the real ~/.claude/projects corpus), stream the file and
record: line counts, per-type counts, sidechain/tool counts, first/last timestamps, and a
schema class:
  session          - has >=1 user AND >=1 assistant message line  -> a parseable TRACE
  workflow_journal - orchestration journal (launched/started/result), no messages
  other            - anything else

Output: one JSON line per file to census.jsonl + summary printed (counts only).
"""
import json
import sys
from collections import Counter
from multiprocessing import Pool
from pathlib import Path

ROOT = Path.home() / ".claude" / "projects"
OUT = Path(__file__).resolve().parent / "census.jsonl"

WORKFLOW_TYPES = {"launched", "started", "result", "finished", "agent-status"}


def census_file(path_str: str):
    p = Path(path_str)
    rec = {
        "rel": p.relative_to(ROOT).as_posix(),
        "size": 0, "lines": 0, "json_ok": 0,
        "n_user": 0, "n_asst": 0, "n_sidechain": 0,
        "n_tool_use": 0, "n_tool_result": 0, "n_meta": 0,
        "first_ts": None, "last_ts": None,
        "wf_types": 0, "err": None,
    }
    try:
        rec["size"] = p.stat().st_size
    except OSError as e:
        rec["err"] = f"stat:{type(e).__name__}"
        return rec
    types = Counter()
    try:
        with p.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                rec["lines"] += 1
                s = line.strip()
                if not s.startswith("{"):
                    continue
                try:
                    o = json.loads(s)
                except Exception:
                    continue
                if not isinstance(o, dict):
                    continue
                rec["json_ok"] += 1
                t = o.get("type")
                types[str(t)] += 1
                if o.get("isSidechain"):
                    rec["n_sidechain"] += 1
                ts = o.get("timestamp")
                if isinstance(ts, str):
                    if rec["first_ts"] is None:
                        rec["first_ts"] = ts
                    rec["last_ts"] = ts
                m = o.get("message")
                if isinstance(m, dict):
                    role = m.get("role")
                    c = m.get("content")
                    blocks = c if isinstance(c, list) else []
                    for b in blocks:
                        if not isinstance(b, dict):
                            continue
                        bt = b.get("type")
                        if bt == "tool_use":
                            rec["n_tool_use"] += 1
                        elif bt == "tool_result":
                            rec["n_tool_result"] += 1
                    if role == "user":
                        if o.get("isMeta"):
                            rec["n_meta"] += 1
                        else:
                            rec["n_user"] += 1
                    elif role == "assistant":
                        rec["n_asst"] += 1
                elif t in WORKFLOW_TYPES:
                    rec["wf_types"] += 1
    except OSError as e:
        rec["err"] = f"read:{type(e).__name__}"
    if rec["n_user"] > 0 and rec["n_asst"] > 0:
        rec["cls"] = "session"
    elif rec["wf_types"] > 0:
        rec["cls"] = "workflow_journal"
    else:
        rec["cls"] = "other"
    rec["types"] = dict(types.most_common(6))
    return rec


def main():
    files = sorted(str(p) for p in ROOT.rglob("*.jsonl"))
    print(f"census: {len(files)} jsonl files under {ROOT}", flush=True)
    n = 0
    summary = Counter()
    with Pool(8) as pool, OUT.open("w", encoding="utf-8") as out:
        for rec in pool.imap_unordered(census_file, files, chunksize=8):
            out.write(json.dumps(rec, separators=(",", ":")) + "\n")
            n += 1
            summary[rec["cls"]] += 1
            if n % 2000 == 0:
                print(f"  {n}/{len(files)}  {dict(summary)}", flush=True)
    print(f"DONE census: {n} files -> {OUT}", flush=True)
    print(f"class summary: {dict(summary)}", flush=True)


if __name__ == "__main__":
    sys.exit(main())
