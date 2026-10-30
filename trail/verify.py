#!/usr/bin/env python
"""TRAIL lane — offline deterministic verification (2026-10-21 session).

Checks (ALL offline: no network, no LLM, no git fetch):
  1. Official repo clone present at repo/ — correct remote
     (github.com/patronus-ai/trail-benchmark), pinned HEAD 0ffbed9, tracked
     files unmodified.
  2. Imports work in the lane venv: repo dependencies (litellm, tiktoken,
     numpy, sklearn, scipy, dotenv, tqdm) and the repo's own run_eval +
     calculate_scores modules.
  3. Raw + gold data parse with the expected counts (recounted this session):
       raw traces: 117 GAIA + 31 SWE Bench, each parses as JSON, span objects
         carry the 19-key OTel contract (checked on every span of a sample)
       gold: 148 files; 147 strict-parse OK; exactly 1 invalid
         (a96c6811716c0473b86a23321db79c34.json, trailing comma);
         836 errors in parseable files; 31 distinct category strings;
         4 files contain duplicate (location, category) pairs;
         Formatting Errors=196 / Instruction Non-compliance=152;
         exactly 2 occurrences of off-taxonomy "Incorrect Memory Usage".
  4. Adapter output validates: the 30-step synthetic session log composed this
     session (synthetic30.py) -> repo raw-trace format with exactly 30 step
     spans (32 spans total incl. root+agent), unique 16-hex span ids, parent
     linkage intact; all 6 planted gold locations resolve to real span ids.
  5. Pipeline acceptance (pipeline30.py in a subprocess): repo
     run_eval.get_prompt builds the taxonomy prompt with the adapted trace
     inlined; the exact litellm params for the boundary are constructed;
     repo calculate_scores.main() round-trips (gold, perfect-output) at
     F1=Location=Joint=1.0000; prints "PIPELINE ACCEPTANCE: PASS".

Run:  .venv/Scripts/python.exe verify.py   (any cwd; paths are __file__-relative)
Exit: 0 iff every check prints PASS.
"""
from __future__ import annotations

import glob
import importlib.util
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "repo")
BENCH = os.path.join(REPO, "benchmarking")
VENV_PY = os.path.join(HERE, ".venv", "Scripts", "python.exe")
PY = sys.executable if not os.path.isfile(VENV_PY) else VENV_PY

sys.path.insert(0, HERE)

FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    line = f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else "")
    print(line)
    if not cond:
        FAILURES.append(name)


def check_eq(name: str, got, want) -> None:
    check(name, got == want, f"got={got!r} want={want!r}")


# --- 1. clone present --------------------------------------------------------
def check_clone() -> None:
    ok = os.path.isdir(os.path.join(REPO, ".git"))
    check("clone: repo/.git exists", ok)
    if not ok:
        return
    head = subprocess.run(["git", "-C", REPO, "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    check_eq("clone: HEAD pinned to 0ffbed9 (latest upstream commit)",
             head, "0ffbed9db859b4a66250dc783fa4dccf86869595")
    remote = subprocess.run(["git", "-C", REPO, "remote", "get-url", "origin"],
                            capture_output=True, text=True).stdout.strip()
    check_eq("clone: origin remote", remote, "https://github.com/patronus-ai/trail-benchmark")
    dirty = subprocess.run(
        ["git", "-C", REPO, "diff", "--quiet", "HEAD"]).returncode
    check("clone: tracked files unmodified (git diff --quiet HEAD)", dirty == 0)


# --- 2. imports ---------------------------------------------------------------
def check_imports() -> None:
    code = ("import litellm, tiktoken, numpy, sklearn, scipy; "
            "from dotenv import load_dotenv, find_dotenv; from tqdm import tqdm; "
            "import sys; sys.path.insert(0, r'%s'); "
            "import run_eval, calculate_scores; print('IMPORTS_OK')"
            % BENCH.replace("\\", "/"))
    r = subprocess.run([PY, "-c", code], capture_output=True, text=True, timeout=180)
    check("imports: repo deps + run_eval + calculate_scores in lane venv",
          r.returncode == 0 and "IMPORTS_OK" in r.stdout,
          detail=(r.stderr or r.stdout).strip().splitlines()[-1][:120] if r.returncode or "IMPORTS_OK" not in r.stdout else "")


# --- 3. data counts -----------------------------------------------------------
SPAN_KEYS = {
    "child_spans", "duration", "events", "links", "logs", "parent_span_id",
    "resource_attributes", "scope_name", "scope_version", "service_name",
    "span_attributes", "span_id", "span_kind", "span_name", "status_code",
    "status_message", "timestamp", "trace_id", "trace_state",
}


def check_data() -> None:
    gaia = glob.glob(os.path.join(BENCH, "data", "GAIA", "*.json"))
    swe = glob.glob(os.path.join(BENCH, "data", "SWE Bench", "*.json"))
    check_eq("data: raw GAIA traces = 117", len(gaia), 117)
    check_eq("data: raw SWE Bench traces = 31", len(swe), 31)
    for f in (gaia + swe):
        try:
            json.load(open(f, encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            check(f"data: every raw trace parses ({os.path.basename(f)})", False, str(e)[:80])
            return
    check("data: all 148 raw traces parse as JSON", True)

    # span contract on the smallest trace (every span, recursively)
    def spans(sp):
        yield sp
        for c in sp.get("child_spans", []):
            yield from spans(c)
    sample = json.load(open(min(gaia, key=os.path.getsize), encoding="utf-8"))
    n_spans = 0
    bad = None
    for sp in spans(sample["spans"][0]):
        n_spans += 1
        if set(sp.keys()) != SPAN_KEYS:
            bad = sorted(set(sp.keys()) ^ SPAN_KEYS)
            break
    check(f"data: span 19-key OTel contract on every span of smallest trace ({n_spans} spans)",
          bad is None, detail=f"delta={bad}" if bad else "exact match")

    total_files = parsed = total_errors = dup_files = mem_usage = 0
    cats: dict[str, int] = {}
    for split in ("gaia", "swe_bench"):
        for f in glob.glob(os.path.join(BENCH, f"processed_annotations_{split}", "*.json")):
            total_files += 1
            try:
                g = json.load(open(f, encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            parsed += 1
            errs = g.get("errors", [])
            total_errors += len(errs)
            pairs = [(e.get("location", ""), e.get("category", "")) for e in errs]
            if len(pairs) != len(set(pairs)):
                dup_files += 1
            for e in errs:
                c = e.get("category", "")
                cats[c] = cats.get(c, 0) + 1
                if c == "Incorrect Memory Usage":
                    mem_usage += 1
    check_eq("gold: 148 gold files", total_files, 148)
    check_eq("gold: 147 strict-parse OK (1 known-invalid)", parsed, 147)
    known_bad = os.path.join(BENCH, "processed_annotations_gaia",
                             "a96c6811716c0473b86a23321db79c34.json")
    try:
        json.load(open(known_bad, encoding="utf-8"))
        check("gold: the 1 invalid file is a96c6811... (trailing comma)", False, "it parsed!")
    except json.JSONDecodeError as e:
        check("gold: the 1 invalid file is a96c6811... (trailing comma)", True, str(e)[:50])
    check_eq("gold: 836 errors in parseable files", total_errors, 836)
    check_eq("gold: 31 distinct category strings", len(cats), 31)
    check_eq("gold: Formatting Errors = 196", cats.get("Formatting Errors"), 196)
    check_eq("gold: Instruction Non-compliance = 152", cats.get("Instruction Non-compliance"), 152)
    check_eq("gold: 4 files with duplicate (location, category) pairs", dup_files, 4)
    check_eq("gold: off-taxonomy 'Incorrect Memory Usage' occurs exactly 2x", mem_usage, 2)


# --- 4 + 5. adapter & pipeline acceptance -------------------------------------
def check_adapter_and_pipeline() -> None:
    import adapter
    import synthetic30

    lines = synthetic30.build_lines()
    n_steps = sum(1 for ln in lines
                  if json.loads(ln).get("type") in ("llm_call", "tool_call"))
    check_eq("adapter: synthetic session log has exactly 30 step records", n_steps, 30)

    trace = adapter.adapt_session_log(lines)
    report = adapter.validate_adapted_trace(trace, expect_steps=30)
    check_eq("adapter: 30 step spans emitted", report["step_spans"], 30)
    check_eq("adapter: 32 spans total (root + agent + 30 steps)", report["total_spans"], 32)

    span_ids = set()

    def collect(sp):
        span_ids.add(sp["span_id"])
        for c in sp["child_spans"]:
            collect(c)
    collect(trace["spans"][0])
    gold = synthetic30.build_gold()
    resolved = sum(1 for e in gold["errors"] if e["location"] in span_ids)
    check_eq("adapter: all 6 planted gold locations resolve to span ids", resolved, 6)
    check("adapter: trace_id is md5(session) 32-hex",
          len(trace["trace_id"]) == 32
          and trace["trace_id"] == "50c5988815e5dad5f78375488e504d96",
          detail=trace["trace_id"])

    r = subprocess.run([PY, os.path.join(HERE, "pipeline30.py")],
                       capture_output=True, text=True, cwd=HERE)
    out = r.stdout
    if r.returncode != 0:
        tail = (r.stderr or r.stdout).strip().splitlines()[-1][:140]
        check("pipeline: pipeline30.py exit 0", False, detail=tail)
        return
    check("pipeline: pipeline30.py exit 0", True)
    check("pipeline: repo get_prompt builds taxonomy prompt with adapted trace inlined",
          "OK B prompt:" in out)
    check("pipeline: litellm boundary params constructed, completion() not called",
          "OK C llm-boundary:" in out)
    check("pipeline: repo scorer round-trip F1=Location=Joint=1.0000",
          "Weighted F1=1.0000 Location=1.0000 Joint=1.0000" in out)
    check("pipeline: PIPELINE ACCEPTANCE: PASS", "PIPELINE ACCEPTANCE: PASS" in out)


def main() -> int:
    print(f"verify.py — TRAIL lane offline checks ({os.path.basename(PY)})")
    check_clone()
    check_imports()
    check_data()
    check_adapter_and_pipeline()
    print("-" * 72)
    if FAILURES:
        print(f"RESULT: FAIL ({len(FAILURES)} failed: {', '.join(FAILURES)})")
        return 1
    print("RESULT: ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
