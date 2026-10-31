#!/usr/bin/env python3
"""Migrate the prior run's path-keyed labels (labels.jsonl, ~/.claude/projects corpus)
to hash-keyed records in labels_full.jsonl, via the manifest path->sha256 index.

Only ok=true records migrate (parse_fails are re-annotated fresh). Idempotent.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = str(Path.home() / ".claude" / "projects")

# manifest_index.json keys are username-redacted (<USER>); match that form here.
HOME_NAME = Path.home().name


def redact(p: str) -> str:
    return p.replace(HOME_NAME, "<USER>") if HOME_NAME else p


def main():
    idx = json.loads((HERE / "manifest_index.json").read_text(encoding="utf-8"))
    old = []
    with (HERE / "labels.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                old.append(json.loads(line))
            except Exception:
                pass
    done = set()
    outp = HERE / "labels_full.jsonl"
    if outp.exists():
        with outp.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    done.add(json.loads(line)["target_id"])
                except Exception:
                    pass

    n_ok = n_migrated = n_nomap = 0
    sha_by_hash = {}
    for r in old:
        if not r.get("ok"):
            continue
        n_ok += 1
        abs_path = redact(ROOT + "\\" + r["trace_id"].replace("/", "\\"))
        sha = idx.get(abs_path)
        if not sha:
            n_nomap += 1
            continue
        if sha in sha_by_hash:
            continue  # duplicate content annotated twice in v1; keep first
        sha_by_hash[sha] = r

    # only migrate hashes that appear as single-part targets
    target_shas = {}
    with (HERE / "targets.jsonl").open(encoding="utf-8") as fh:
        for line in fh:
            try:
                t = json.loads(line)
            except Exception:
                continue
            if t["n_parts"] == 1:
                target_shas.setdefault(t["sha256"], t)

    with outp.open("a", encoding="utf-8") as out:
        for sha, r in sha_by_hash.items():
            t = target_shas.get(sha)
            if not t or t["target_id"] in done:
                continue
            rec = {
                "target_id": t["target_id"], "sha256": sha, "ok": True,
                "task_completed": r.get("task_completed"),
                "modes": r.get("modes"), "n_answered": r.get("n_answered", 14),
                "model": "glm-5.3-flash", "migrated_from": "v1_path_labels",
                "usage": r.get("usage", {"pt": 0, "ct": 0}), "attempts": r.get("attempts", 1),
                "runtime": t["runtime"], "origin": t["origin"], "format": t["format"],
                "n_user": t["n_user"], "n_asst": t["n_asst"], "n_msg": t["n_msg"],
                "n_sidechain": t["n_sidechain"], "first_ts": t.get("first_ts"),
            }
            out.write(json.dumps(rec, separators=(",", ":")) + "\n")
            n_migrated += 1
    print(f"[migrate] v1 ok-records={n_ok} unique-sha={len(sha_by_hash)} "
          f"no-manifest-map={n_nomap} migrated_now={n_migrated} "
          f"labels_full_total={sum(1 for _ in outp.open(encoding='utf-8'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
