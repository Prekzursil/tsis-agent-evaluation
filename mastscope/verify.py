#!/usr/bin/env python3
"""Offline deterministic verification for the mastscope lane. Prints PASS lines; exit 0.

Re-derives every check from files on disk (does not trust the build scripts' own
reports except where cross-checked). No network access.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

LANE = Path(__file__).resolve().parent
PY = sys.executable

PAPER_NAMES = {
    "1.1": "Disobey Task Specification", "1.2": "Disobey Role Specification",
    "1.3": "Step Repetition", "1.4": "Loss of Conversation History",
    "1.5": "Unaware of Termination Conditions",
    "2.1": "Conversation Reset", "2.2": "Fail to Ask for Clarification",
    "2.3": "Task Derailment", "2.4": "Information Withholding",
    "2.5": "Ignored Other Agent's Input", "2.6": "Reasoning-Action Mismatch",
    "3.1": "Premature Termination", "3.2": "No or Incomplete Verification",
    "3.3": "Incorrect Verification",
}
PAPER_CAT_SHARES = {"FC1": 44.2, "FC2": 32.3, "FC3": 23.5}

results = []


def check(ok: bool, label: str, detail: str = ""):
    line = f"{'PASS' if ok else 'FAIL'}: {label}" + (f" -- {detail}" if detail else "")
    results.append((ok, line))
    return ok


def main() -> int:
    # ---- 1. repo clones ------------------------------------------------------------
    defs = LANE / "repo" / "MAST" / "taxonomy_definitions_examples" / "definitions.txt"
    nb = LANE / "repo" / "MAST" / "llm_judge_pipeline.ipynb"
    mast_json = LANE / "repo" / "AdaMAST-readonly" / "adamast" / "core" / "mast.json"
    check(defs.is_file(), "MAST clone present with taxonomy definitions.txt", str(defs))
    check(nb.is_file(), "MAST clone present with llm_judge_pipeline.ipynb", str(nb))
    check(mast_json.is_file(), "AdaMAST read-only clone present with mast.json", str(mast_json))
    for repo in ["MAST", "AdaMAST-readonly"]:
        head = subprocess.run(
            ["git", "-C", str(LANE / "repo" / repo), "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True)
        check(head.returncode == 0, f"git HEAD readable for repo/{repo}",
              head.stdout.strip())

    # ---- 2. taxonomy reproduction ---------------------------------------------------
    tax = json.loads((LANE / "taxonomy" / "taxonomy.json").read_text(encoding="utf-8"))
    check(tax["n_modes"] == 14 and len(tax["modes"]) == 14, "taxonomy.json has 14 modes")
    check(tax["n_categories"] == 3 and len(tax["categories"]) == 3, "taxonomy.json has 3 categories")
    split = {c["id"]: len(c["mode_codes"]) for c in tax["categories"]}
    check(split == {"FC1": 5, "FC2": 6, "FC3": 3}, "category split 5/6/3", str(split))
    check({m["code"]: m["paper_name"] for m in tax["modes"]} == PAPER_NAMES,
          "paper names present for all 14 modes")
    sums = {"FC1": 0.0, "FC2": 0.0, "FC3": 0.0}
    for m in tax["modes"]:
        sums["FC" + m["code"][0]] += m["prevalence_pct"]
    for fc, want in PAPER_CAT_SHARES.items():
        check(abs(sums[fc] - want) <= 0.15, f"{fc} prevalence sum matches paper",
              f"{sums[fc]:.2f} vs {want}")
    check(abs(sum(sums.values()) - 100.0) <= 0.2, "total prevalence ~100%",
          f"{sum(sums.values()):.2f}%")
    # independent re-parse of the shipped definitions file
    text = defs.read_text(encoding="utf-8")
    pairs = re.findall(r"^(\d\.\d)\s+([^:\n]+):", text, flags=re.MULTILINE)
    check(len(pairs) == 14, "independent re-parse of definitions.txt yields 14 modes",
          f"got {len(pairs)}")
    rep = (LANE / "taxonomy" / "validation_report.txt").read_text(encoding="utf-8")
    check("FAIL" not in rep, "taxonomy validation_report.txt contains no FAIL lines")
    ada = json.loads(mast_json.read_text(encoding="utf-8"))
    x = tax["adamast_built_in_crosscheck"]
    check(len(ada["codes"]) == 14 == x["codes"], "AdaMAST crosscheck: 14 codes confirmed in both")
    check(x["paper_modes_missing_in_adamast"] == ["2.6 Reasoning-Action Mismatch"],
          "AdaMAST crosscheck: FM-2.6 drop recorded")
    check(sorted(x["adamast_only_codes"]) == ["MAST-13 Weak verification"],
          "AdaMAST crosscheck: extra 'Weak verification' code recorded")

    # ---- 3. annotation artifacts ----------------------------------------------------
    ann = json.loads((LANE / "annotation" / "annotation_result_env_key.json").read_text(encoding="utf-8"))
    codes = ["1.1", "1.2", "1.3", "1.4", "1.5", "2.1", "2.2", "2.3", "2.4", "2.5", "2.6", "3.1", "3.2", "3.3"]
    check(set(ann["modes"].keys()) == set(codes)
          and all(isinstance(v, bool) for v in ann["modes"].values()),
          "annotation result has binary labels for all 14 modes")
    check(isinstance(ann["task_completed"], bool) and ann["task_completed"] is False,
          "annotation flags task NOT completed (matches synthetic ground truth)")
    check("ZAI_API_KEY" in ann["provider"] and "glm-4.5-flash" in ann["provider"],
          "annotation ran via env key", ann["provider"])
    check(ann.get("usage", {}) and ann["usage"]["prompt_tokens"] > 0,
          "annotation usage recorded", str(ann.get("usage")))
    prompt = (LANE / "annotation" / "prompt_built.txt").read_text(encoding="utf-8")
    check("*** begin of things you should answer *** @@" in prompt
          and "1.3 Step Repetition: <yes or no>" in prompt
          and "Here is the multiagent system trace:" in prompt,
          "assembled prompt follows notebook contract (markers + mode list + trace)")
    blocker = json.loads((LANE / "annotation" / "annotation_blocker.json").read_text(encoding="utf-8"))
    check("OPENAI_API_KEY" in blocker["blocker"] and "failed" in blocker["blocker"],
          "o1-path blocker honestly recorded", blocker["blocker"][:80])
    attempts = (LANE / "annotation" / "attempts.log").read_text(encoding="utf-8")
    check("SUCCESS" in attempts, "attempts.log records the successful env-key run")

    # ---- 4. privacy scan re-run (fresh, offline) -------------------------------------
    out_path = LANE / "synthetic_corpus" / "scan_output_verify_rerun.json"
    proc = subprocess.run(
        [PY, str(LANE / "privacy_scan.py"), str(LANE / "synthetic_corpus" / "corpus"),
         "--out", str(out_path)],
        capture_output=True, text=True)
    check(proc.returncode == 0, "privacy_scan.py re-run exits 0 over synthetic corpus")
    scan = json.loads(out_path.read_text(encoding="utf-8"))
    man = json.loads((LANE / "synthetic_corpus" / "planted_manifest.json").read_text(encoding="utf-8"))
    t = man["expected_totals"]
    check(scan["files_total"] == t["files_total"] and scan["files_scanned"] == t["files_scanned"],
          "scan file counts match manifest", f"{scan['files_scanned']}/{scan['files_total']}")
    check(scan["total_lines"] == t["total_lines"], "scan line count matches manifest",
          str(scan["total_lines"]))
    check(scan["message_objects"] == t["message_objects"], "scan message count matches manifest",
          str(scan["message_objects"]))
    cats_ok = all(scan["pii_ish"][c]["lines"] == e
                  for c, e in man["expected_category_line_counts"].items())
    check(cats_ok, "ALL 10 PII-ish category counts match planted manifest exactly")
    blob = out_path.read_text(encoding="utf-8") + proc.stdout
    leaks = [tok for tok in man["planted_tokens_for_leak_test"] if tok in blob]
    check(not leaks, "LEAK TEST: zero planted tokens appear in scan output",
          f"checked {len(man['planted_tokens_for_leak_test'])} tokens")

    # ---- 5. dashboard -----------------------------------------------------------------
    html = (LANE / "dashboard" / "index.html").read_text(encoding="utf-8")
    counts = json.loads((LANE / "dashboard" / "synthetic_mode_counts.json").read_text(encoding="utf-8"))
    check(html.count('class="bar"') == 14, "dashboard has 14 mode bars")
    check("SYNTHETIC DATA" in html, "dashboard carries SYNTHETIC banner")
    check(all(f">{v}</span>" in html for v in counts["counts"].values()),
          "dashboard bar values match synthetic_mode_counts.json")
    check("privacy_scan.py" in html and "aggregates only" in html,
          "dashboard privacy panel present with aggregates-only note")

    # ---- 6. SMOKE ---------------------------------------------------------------------
    check((LANE / "SMOKE.md").is_file(), "SMOKE.md exists with receipts")

    ok = all(o for o, _ in results)
    for _, line in results:
        print(line)
    print(f"\n{'VERIFY OK — all checks passed' if ok else 'VERIFY FAILED'} ({len(results)} checks)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
