#!/usr/bin/env python3
"""Fast, EXACTLY-equivalent block matcher for the 19 wedge-prone binaries.

Why: privacy_scan_corpus.scan_one's block mode runs all 10 PII regexes over
each whole 64KB-decoded block; the email pattern backtracks quadratically on
long alnum runs (measured 1.3 MB/s per process; the 19 remaining files are
~46 GB total -> days serial). Runs 3/4/5 of scan_skipped.py died trying
(BrokenProcessPool after worker deaths).

Exactness argument (verified empirically below):
  1. Required-literal prefilters: a pattern whose regex necessarily contains
     a literal L cannot match a block not containing L. Prefilters used:
       email '@' | openai_key 'sk-' | aws_key 'AKIA' | github_token 'gh'
       bearer_token 'Bearer' | url 'http'
  2. Per-line split for the 8 patterns whose character classes contain no
     newline (email, openai_key, aws_key, github_token, url, ipv4, abs_path,
     entropy_blob): a match cannot span '\n', so rx.search(block) is True iff
     rx.search(line) for some line of block.split('\n'). bearer_token and
     secret_assignment use '\s' (which matches '\n') and stay block-wide.
  3. Counting semantics identical to scan_one: each 64KB block counts ONCE
     per category whose regex matches anywhere in the block.

Equivalence check: scan_eq() samples N blocks from a real file and asserts
the fast matcher's per-block category hit-set equals scan_one's on every
sampled block.

Usage:
  python scan_one_fast.py verify          # run the equivalence check
  python scan_one_fast.py scan PATH STORAGE OUT_JSON   # one file -> JSON stats
"""
import json
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from privacy_scan import PATTERNS  # noqa: E402

BLOCK = 65536
BINARY_STORAGE = {"sqlite", "other"}
BINARY_SUFFIX = {".db", ".vscdb", ".dat", ".tar", ".pdf", ".png", ".jpg", ".zip",
                 ".exe", ".dll", ".so", ".bin", ".mp4", ".webm", ".woff2"}

COMPILED = {k: re.compile(v.pattern) for k, v in PATTERNS.items()}
# patterns safe to run per-line (no class matches '\n')
PER_LINE = ["email", "openai_key", "aws_key", "github_token", "url", "ipv4",
            "abs_path", "entropy_blob"]
BLOCK_WIDE = ["bearer_token", "secret_assignment"]

# ---------------------------------------------------------------------------
# Exact fast-path for the email pattern (75% of runtime; quadratic backtracking
# on 64KB no-newline binary lines). Decomposition of
#   [A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}
# A match exists iff there is an '@' at i with:
#   (a) w[i-1] in LCL  (greedy local part run then literal '@' -- starting at
#       the run start always reaches the '@'; existence needs just one LCL
#       char adjacent), and
#   (b) some '.' at d with i+2 <= d, w[i+1..d-1] all in DOM, and w[d+1],w[d+2]
#       both in LTR (>=2 letters; no trailing boundary in the pattern).
# Every valid d lies inside the maximal DOM run from i+1 (dots are IN the DOM
# class, so all dots of candidate domains are walked). Classes are ASCII by
# construction, identical to the regex's.
_LCL = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._%+-")
_DOM = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.-")
_LTR = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz")


def has_email(w: str) -> bool:
    find = w.find
    n = len(w)
    i = find("@")
    while i != -1:
        j = i - 1
        if j >= 0 and w[j] in _LCL:
            d = i + 1
            while d < n and w[d] in _DOM:
                if d >= i + 2 and w[d] == "." and d + 2 < n \
                        and w[d + 1] in _LTR and w[d + 2] in _LTR:
                    return True
                d += 1
        i = find("@", i + 1)
    return False

PREFILTER = {
    "email": lambda w: "@" in w,
    "openai_key": lambda w: "sk-" in w,
    "aws_key": lambda w: "AKIA" in w,
    "github_token": lambda w: "gh" in w,
    "bearer_token": lambda w: "Bearer" in w,
    "secret_assignment": None,  # word prefilter needs case-fold; cheap enough raw
    "url": lambda w: "http" in w,
    "ipv4": None,
    "abs_path": None,
    "entropy_blob": None,
}
SECRET_WORDS = ("api_key", "apikey", "secret", "password", "passwd", "token")


def block_cats(w: str) -> set:
    """Category hit-set for one decoded 64KB block (same semantics as scan_one:
    a category is 'hit' if its regex matches anywhere in the block)."""
    hits = set()
    lines = w.split("\n")
    # email: exact fast decomposition (see has_email docstring); '@' prefilter
    if "@" in w and any(has_email(ln) for ln in lines):
        hits.add("email")
    for cat in PER_LINE:
        if cat == "email":
            continue
        pf = PREFILTER.get(cat)
        if pf is not None and not pf(w):
            continue
        rx = COMPILED[cat]
        for ln in lines:
            if rx.search(ln):
                hits.add(cat)
                break
    for cat in BLOCK_WIDE:
        pf = PREFILTER.get(cat)
        if pf is not None and not pf(w):
            continue
        if COMPILED[cat].search(w):
            hits.add(cat)
    return hits


def scan_one_fast(path: str, storage: str, progress_every: int = 0) -> dict:
    """Same output contract as privacy_scan_corpus.scan_one (block mode)."""
    st = {"files": 1, "unreadable": 0, "lines": 0, "json_lines": 0,
          "non_json_lines": 0, "message_objects": 0, "bytes": 0,
          "mode": "block", "cats": {c: 0 for c in COMPILED}}
    suffix = os.path.splitext(path)[1].lower()
    block_mode = storage in BINARY_STORAGE or suffix in BINARY_SUFFIX
    assert block_mode, "scan_one_fast is only for block-mode files"
    try:
        fh = open(path, "rb")
    except OSError:
        st["unreadable"] = 1
        return st
    cats = st["cats"]
    n = 0
    t0 = time.time()
    try:
        while True:
            b = fh.read(BLOCK)
            if not b:
                break
            n += 1
            for cat in block_cats(b.decode("utf-8", errors="replace")):
                cats[cat] += 1
            if progress_every and n % progress_every == 0:
                mb = n * BLOCK / 2**20
                print(f"[fast] {mb:.0f}MB {mb/max(time.time()-t0,1e-9):.1f}MB/s "
                      f"cats={ {k: v for k, v in cats.items() if v} }",
                      flush=True)
    finally:
        fh.close()
    st["lines"] = n
    try:
        st["bytes"] = os.path.getsize(path)
    except OSError:
        pass
    return st


def verify(path=None, full_file: bool = True):
    """Equivalence check against privacy_scan_corpus's category logic.
    1. adversarial synthetic email cases (original regex vs has_email)
    2. whole-file block-by-block hit-set equality (all categories)."""
    from privacy_scan_corpus import COMPILED as REF
    rx_email = COMPILED["email"]
    synth = [
        "a@b.cc", "a@b.c", "ab@c.dd", "x.y+z%A1@sub.example.co.uk",
        "@" + "a" * 5000, "a" * 5000 + "@", "a" * 5000 + "@" + "b" * 5000,
        "a" * 5000 + "@" + "b" * 5000 + ".cc", "no-at-here",
        "a@.cc", "a@b..cc", ".a@b.cc", "-@b.cc", "+@x.yy", "_@x.yy",
        "%@x.yy", "@@x.yy", "a@x.yz", "a@x.yZ9", "a@x.zz more", "za@xb.",
        "a" * 100 + "@" + "b." * 200 + "com", "user@127.0.0.1",
        "user@example.com.", "user@ex%ample.com", "user@ex_ample.com",
        "ünïcode@exämple.com", "a@b.c" + "d" * 10, "trailing a@b.cc",
        "sk-proj-abcdefghij1234567890@example.com",
        "a@" + "b" * 64 + ".c" + "c" * 64, "a@b" + "." * 3 + "cc",
    ]
    mism = 0
    for s in synth:
        if bool(rx_email.search(s)) != has_email(s):
            mism += 1
            print(f"SYNTH MISMATCH on len={len(s)}: ref={bool(rx_email.search(s))} "
                  f"fast={has_email(s)}")
    print(f"verify synth: {len(synth)} cases, {mism} mismatches")
    if path is None:
        path = (r"D:\agent-sessions-vault\stores\cowork-private"
                r"\cursor-desktop-auth-backup_2026-08-24\cursor-globalStorage"
                r"\state.vscdb")
    n_checked = 0
    mismatches = 0
    with open(path, "rb") as fh:
        while True:
            b = fh.read(BLOCK)
            if not b:
                break
            w = b.decode("utf-8", errors="replace")
            ref_hits = {c for c, rx in REF.items() if rx.search(w)}
            fast_hits = block_cats(w)
            if ref_hits != fast_hits:
                mismatches += 1
                print(f"MISMATCH block {n_checked}: ref={ref_hits} fast={fast_hits}")
            n_checked += 1
    print(f"verify file: {n_checked} blocks checked (FULL FILE), "
          f"{mismatches} mismatches")
    return mism == 0 and mismatches == 0


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "verify":
        ok = verify()
        sys.exit(0 if ok else 1)
    if cmd == "scan":
        path, storage, out_json = sys.argv[2], sys.argv[3], sys.argv[4]
        st = scan_one_fast(path, storage, progress_every=2000)
        with open(out_json, "w", encoding="utf-8") as fh:
            json.dump(st, fh)
        print(f"[fast] DONE {path} -> {out_json} lines={st['lines']}")
        sys.exit(0)
    print(__doc__)
    sys.exit(2)
