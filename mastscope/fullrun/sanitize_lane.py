"""2026-10-21 lane privacy sanitization (post-AdaMAST-run audit remediation).

The AdaMAST comparison run (2026-10-20/21) wrote two raw-corpus-content artifacts
into the lane and left the OS username in absolute paths across its logs/metadata.
The lane contract is: lane files hold labels/counts/ids exclusively; no raw
content; no username. This script:
  1. records + deletes the two raw-content files,
  2. redacts C:\\Users\\<name> -> C:\\Users\\<USER> (both separators) in every
     lane text file that contains the username,
  3. prints a receipt of every action.
Idempotent; run from mastscope/.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOME_NAME = Path.home().name

# --- 1. raw-content files to remove (recorded, then deleted)
RAW = [
    HERE / "adamast" / "traces_sample.jsonl",
    HERE / "adamast" / "taxonomy_run" / "artifacts" / "inputs" / "traces.normalized.jsonl",
]

receipt = []
for p in RAW:
    if p.exists():
        n_bytes = p.stat().st_size
        p.unlink()
        receipt.append(f"DELETED raw-content artifact {p.relative_to(HERE)} ({n_bytes:,} bytes)")
    else:
        receipt.append(f"already absent {p.relative_to(HERE)}")

# --- 2. username redaction across lane text files
SUFFIXES = {".json", ".jsonl", ".log", ".md", ".txt", ".html", ".py", ".sh", ".js"}
CORPUS = HERE.parent.parent / "corpus"
pat = re.compile(r"Users[\\/]" + re.escape(HOME_NAME) + r"(?=[\\/'\"])")
bare = HOME_NAME
for q in sorted(HERE.rglob("*")):
    if not q.is_file() or q.suffix.lower() not in SUFFIXES:
        continue
    if CORPUS in q.parents or "__pycache__" in q.parts:
        continue
    try:
        blob = q.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    if HOME_NAME not in blob:
        continue
    new = pat.sub("Users/<USER>", blob)
    # any leftover bare occurrences (outside Users\ path context)
    leftover = new.count(HOME_NAME)
    new = new.replace(HOME_NAME, "<USER>")
    q.write_text(new, encoding="utf-8")
    receipt.append(f"REDACTED {q.relative_to(HERE)} (path-form + {leftover} other)")

print("\n".join(receipt))
print(f"\ntotal actions: {len(receipt)}")
