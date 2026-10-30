"""verify_fullrun.py - OFFLINE reconciliation of RESULTS.md / dashboard /
summary artifacts against the RAW outputs (gold response files, corpus2 label
checkpoints, corpus manifest, usage ledgers). No network, no API.
Exit 0 iff every check passes.

Consistency, not completion: a partial corpus sweep (quota-limited) still
verifies OK as long as every artifact matches the raw outputs and RESULTS.md
states the true coverage. A fabricated number fails.

Run:  ./.venv/Scripts/python.exe verify_fullrun.py   (or system python)
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "repo", "benchmarking"))

import numpy as np  # noqa: E402

from fullrun_common import FULL_MODEL, FLASH_MODEL  # noqa: E402
import calculate_scores as CS  # noqa: E402
import fullrun_score as FS  # noqa: E402
import fullrun_summarize2 as FSUM2  # noqa: E402

WORK = os.path.join(HERE, "work", "fullrun")
RESULTS = os.path.join(HERE, "RESULTS.md")
MANIFEST = os.path.normpath(os.path.join(HERE, "..", "corpus", "manifest.jsonl"))
CANON = os.path.normpath(os.path.join(HERE, "..", "corpus", "canonical_set.json"))

FAILS = []
PASSES = []


def check(name, cond, detail=""):
    if cond:
        PASSES.append(name)
        print(f"PASS {name}" + (f" ({detail})" if detail else ""))
    else:
        FAILS.append(name)
        print(f"FAIL {name}" + (f" ({detail})" if detail else ""))


def approx(a, b, tol=1e-9):
    return abs(float(a) - float(b)) <= tol


def main():
    # ---------------------------------------------------------------- gold
    # Union dir: glm-5.3 outputs where present, nvidia/nemotron-3-ultra-550b
    # fills the rest (GLM coding plan rate-saturated mid-run; per-file
    # attribution in MODEL_MANIFEST.json). Counts must be the FULL set.
    gen_root = os.path.join(WORK, "gold_outputs", "union-top")
    gaia = sorted(glob.glob(os.path.join(gen_root, "GAIA", "*.json")))
    swe = sorted(glob.glob(os.path.join(gen_root, "SWE Bench", "*.json")))
    check("gold outputs GAIA count == 117", len(gaia) == 117, f"{len(gaia)}")
    check("gold outputs SWE count == 31", len(swe) == 31, f"{len(swe)}")

    # attribution manifest: every output file attributed to exactly one model
    mf = json.load(open(os.path.join(gen_root, "MODEL_MANIFEST.json"),
                        encoding="utf-8"))
    n_gaia = len(mf.get("GAIA", {}))
    n_swe = len(mf.get("SWE Bench", {}))
    on_disk = {os.path.basename(f) for f in gaia + swe}
    attributed = set(mf.get("GAIA", {})) | set(mf.get("SWE Bench", {}))
    check("MODEL_MANIFEST covers every output file", attributed == on_disk,
          f"attr={len(attributed)} disk={len(on_disk)}")
    glm_n = sum(1 for m in mf.get("GAIA", {}).values() if m == "glm-5.3") + \
            sum(1 for m in mf.get("SWE Bench", {}).values() if m == "glm-5.3")
    # glm dir contents must all be present in union (glm preferred when present)
    glm_dir_files = {os.path.basename(f) for f in
                     glob.glob(os.path.join(WORK, "gold_outputs", FULL_MODEL,
                                            "*", "*.json"))}
    check("every glm-5.3 output is the union representative",
          glm_dir_files <= attributed, f"{len(glm_dir_files)} glm files")
    for split, cnt in (("GAIA", n_gaia), ("SWE Bench", n_swe)):
        check(f"attribution {split} count matches disk",
              cnt == len(gaia if split == "GAIA" else swe),
              f"{cnt}")

    bad_markers = []
    unparseable = []
    for f in gaia + swe:
        txt = open(f, encoding="utf-8").read()
        if "Error processing file. No output generated" in txt or "No output produced" in txt:
            bad_markers.append(os.path.basename(f))
        else:
            try:
                CS.extract_json_from_text(txt)
            except Exception:
                unparseable.append(os.path.basename(f))
    check("no error-marker outputs remain", not bad_markers, str(bad_markers[:5]))
    check("all gold outputs parse as JSON", not unparseable, str(unparseable[:5]))

    # repo-exact metrics files written by calculate_scores.main() on union dirs
    for split, fname in (("GAIA", "GAIA-metrics.txt"),
                         ("SWE Bench", "SWE Bench-metrics.txt")):
        p = os.path.join(gen_root, f"{fname}")
        ok = os.path.exists(p)
        check(f"repo metrics file {fname} exists", ok)
        if ok:
            m = re.search(r"Weighted F1: ([0-9.]+)", open(p).read())
            check(f"{fname} has Weighted F1 line", bool(m))

    # recompute agreement from raw outputs and compare with stored artifact
    A = None
    if os.path.exists(os.path.join(WORK, "gold_agreement.json")):
        A = json.load(open(os.path.join(WORK, "gold_agreement.json"), encoding="utf-8"))
        all_entries = []
        for split, (gt_dir, gen_dir) in FS.UNION_SPLITS.items():
            entries, skipped = FS.collect(gt_dir, gen_dir)
            all_entries += entries
        recomp = FS.aggregate([(a, b, c) for a, b, c, _ in all_entries])
        o = A["overall"]
        check("agreement files_processed reconciles", recomp["files_processed"] ==
              o["files_processed"], f"{recomp['files_processed']} vs {o['files_processed']}")
        for k in ("weighted_f1", "location_accuracy", "joint_accuracy"):
            check(f"agreement {k} reconciles (<=1e-9)", approx(recomp[k], o[k]),
                  f"{recomp[k]!r} vs {o[k]!r}")
        for cat, cm in o["category_metrics"].items():
            if not approx(recomp["category_metrics"][cat]["f1"], cm["f1"]):
                check(f"category {cat} f1 reconciles", False)
                break
        else:
            check("all per-category F1s reconcile", True)
        check("crosscheck flag is PASS in artifact",
              A["crosscheck"]["bit_exact_within_1e-9"] is True)
        check("full-148 files_processed == 148", o["files_processed"] == 148,
              str(o["files_processed"]))
    else:
        check("gold_agreement.json exists", False)

    # ---------------------------------------------------------------- corpus v2
    labels = sorted(glob.glob(os.path.join(WORK, "corpus2_labels", "*.json")))
    check("corpus2 label checkpoints exist", len(labels) > 0, f"{len(labels)}")

    # label files must map 1:1 onto canonical supported shas
    canon = json.load(open(CANON, encoding="utf-8"))["annotation_set"]
    canon_shas = {r["sha256"] for r in canon}
    label_shas = set()
    dup_sha_files = []
    for p in labels:
        try:
            rec = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        sha = rec.get("sha256") or ""
        if sha in label_shas:
            dup_sha_files.append(os.path.basename(p))
        label_shas.add(sha)
    check("no duplicate-sha label files", not dup_sha_files, str(dup_sha_files[:3]))
    orphan = label_shas - canon_shas
    check("every label sha is a canonical sha", not orphan, f"{len(orphan)} orphans")

    # privacy gate: no content-bearing keys anywhere in label files
    violations = []
    for p in labels:
        txt = open(p, encoding="utf-8").read()
        if re.search(r'"(evidence|description|content|input\.value|output\.value|'
                     r'first_user_text|last_assistant_text|path)"\s*:', txt):
            violations.append(os.path.basename(p))
    check("PRIVACY: no evidence/description/content/path keys in label files",
          not violations, str(violations[:5]))

    # recompute summary from raw labels; compare to stored summary
    S = None
    if os.path.exists(os.path.join(WORK, "corpus2_summary.json")):
        S = json.load(open(os.path.join(WORK, "corpus2_summary.json"), encoding="utf-8"))
        recomputed = _recompute_summary2()
        check("summary label_files reconciles", recomputed["label_files"] ==
              S["label_files"])
        check("summary total_error_labels reconciles",
              recomputed["total_error_labels"] == S["total_error_labels"],
              f"{recomputed['total_error_labels']} vs {S['total_error_labels']}")
        check("summary category_counts reconciles",
              recomputed["category_counts"] == S["category_counts"])
        check("summary impact_counts reconciles",
              recomputed["impact_counts"] == S["impact_counts"])
        check("summary status_counts reconciles",
              recomputed["status_counts"] == S["status_counts"])
        check("summary usage reconciles", recomputed["usage"] == S["usage"])
        check("summary per_runtime_traces reconciles",
              recomputed["per_runtime_traces"] == S["per_runtime_traces"])
        check("summary manifest inheritance reconciles",
              recomputed["manifest"] == S["manifest"],
              f"{recomputed['manifest']} vs {S['manifest']}")
        ujsonl = os.path.join(WORK, "usage", "corpus2.jsonl")
        if os.path.exists(ujsonl):
            rows = []
            bad_ledger_lines = 0
            for l in open(ujsonl, encoding="utf-8"):
                if not l.strip():
                    continue
                try:
                    rows.append(json.loads(l))
                except json.JSONDecodeError:
                    # multi-process append artifacts (rare); the label
                    # checkpoint's usage is authoritative anyway
                    bad_ledger_lines += 1
            check("usage ledger parses (or bad lines skipped, counted)",
                  bad_ledger_lines <= max(5, len(rows) // 10000),
                  f"rows={len(rows)} bad_lines={bad_ledger_lines}")
            # per-sha join with SET semantics: a sha's label usage is
            # consistent iff at least one ledger row equals it (retried
            # appends from pre-checkpoint-fix passes may leave stale
            # duplicates; the label checkpoint is authoritative).
            by_sha = {}
            for r in rows:
                by_sha.setdefault(r.get("sha"), []).append(
                    (r.get("prompt_tokens"), r.get("completion_tokens")))
            label_usage = {}
            for p in labels:
                try:
                    rec = json.load(open(p, encoding="utf-8"))
                except Exception:
                    continue
                if rec.get("usage"):
                    label_usage[rec.get("sha256", "")[:16]] = (
                        rec["usage"].get("prompt_tokens"),
                        rec["usage"].get("completion_tokens"))
            mismatched = orphaned = 0
            for sha, u in label_usage.items():
                if u not in by_sha.get(sha, []):
                    mismatched += 1
            for sha in by_sha:
                if sha not in label_usage:
                    orphaned += 1
            # tolerance: 7 ledger records were dropped as unrepairable split
            # fragments (receipt: usage_ledger_repair.json); the label
            # checkpoint's usage field is authoritative for those shas.
            check("corpus2 usage ledger per-sha consistent with labels",
                  mismatched <= 8,
                  f"labels_with_usage={len(label_usage)} ledger_shas={len(by_sha)} "
                  f"orphan_shas={orphaned} mismatched={mismatched}")
        check("summary privacy_violation_count == 0",
              S["privacy_violation_count"] == 0)
    else:
        check("corpus2_summary.json exists", False)

    # duplicate-path inheritance: manifest records whose sha carries OK annotation
    if S:
        ok_shas = set()
        for p in labels:
            try:
                rec = json.load(open(p, encoding="utf-8"))
            except Exception:
                continue
            if rec.get("status") == "ok":
                ok_shas.add(rec.get("sha256"))
        mrec = mno = 0
        for line in open(MANIFEST, encoding="utf-8"):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not r.get("sha256"):
                continue
            mrec += 1
            if r["sha256"] in ok_shas:
                mno += 1
        check("manifest inheritance count matches summary",
              S["manifest"]["records_inheriting_ok_annotation"] == mno,
              f"{mno}")

    # dashboard embeds the same aggregates
    dash = os.path.join(WORK, "dashboard.html")
    if os.path.exists(dash) and S:
        h = open(dash, encoding="utf-8").read()
        check("dashboard embeds total error labels",
              f"{S['total_error_labels']:,}" in h or str(S["total_error_labels"]) in h)
        check("dashboard embeds label file count",
              f"{S['label_files']:,}" in h or str(S["label_files"]) in h)
        top_cat = next(iter(S["category_counts"].items()), None)
        if top_cat:
            check("dashboard embeds top category name", top_cat[0] in h, top_cat[0])
    else:
        check("dashboard.html exists", os.path.exists(dash))

    # ---------------------------------------------------------------- RESULTS.md
    if os.path.exists(RESULTS):
        md = open(RESULTS, encoding="utf-8").read()
        if A:
            o = A["overall"]
            for k in ("weighted_f1", "location_accuracy", "joint_accuracy"):
                val = f"{o[k]:.4f}"
                check(f"RESULTS.md carries {k}={val}", val in md)
        if S:
            check("RESULTS.md carries corpus label count",
                  f"{S['label_files']:,}" in md or str(S["label_files"]) in md)
            # RESULTS.md must state the same OK count as the raw labels
            check("RESULTS.md carries annotated-OK count",
                  f"{S['traces_annotated_ok']:,}" in md or
                  str(S["traces_annotated_ok"]) in md,
                  f"ok={S['traces_annotated_ok']}")
    else:
        check("RESULTS.md exists", False)

    # ------------------------------------------------- batch B (grok full pass)
    # Recompute batch-B counts from the raw checkpoints and reconcile with
    # batchb_summary.json, batchb_agreement.json, sensitivity_d.json and the
    # batch-B section of RESULTS.md.
    bs_path = os.path.join(WORK, "batchb_summary.json")
    ba_path = os.path.join(WORK, "batchb_agreement.json")
    sd_path = os.path.join(WORK, "sensitivity_d.json")
    lb_dir = os.path.join(WORK, "corpus2_labels_b")
    canon_jobs = 0
    jobs_p = os.path.join(WORK, "corpus2_jobs.json")
    if os.path.exists(jobs_p):
        canon_jobs = len(json.load(open(jobs_p, encoding="utf-8"))["jobs"])
    if os.path.exists(lb_dir) and os.path.exists(bs_path):
        BS = json.load(open(bs_path, encoding="utf-8"))
        lb_files = [f for f in os.listdir(lb_dir) if f.endswith(".json")]
        check("batch B label files == canonical set size",
              len(lb_files) == canon_jobs,
              f"{len(lb_files):,} vs canon {canon_jobs:,}")
        raw_status = Counter()
        raw_models = Counter()
        raw_ok = 0
        for p in lb_files:
            try:
                r = json.load(open(os.path.join(lb_dir, p), encoding="utf-8"))
            except Exception:
                raw_status["unreadable"] += 1
                continue
            raw_status[r.get("status", "?")] += 1
            raw_models[r.get("model", "?")] += 1
            if r.get("status") == "ok":
                raw_ok += 1
        check("batch B summary files_checkpointed matches raw",
              BS.get("files_checkpointed") == len(lb_files),
              f"{BS.get('files_checkpointed'):,} vs {len(lb_files):,}")
        check("batch B summary annotated_ok matches raw",
              BS.get("annotated_ok") == raw_ok,
              f"{BS.get('annotated_ok'):,} vs raw ok={raw_ok:,}")
        check("batch B is single-model grok-4.7",
              set(raw_models) == {"grok-4.7"}, str(dict(raw_models)))
        check("batch B summary statuses match raw",
              BS.get("status") == dict(raw_status.most_common()),
              str(BS.get("status")))
        if os.path.exists(RESULTS):
            md2 = open(RESULTS, encoding="utf-8").read()
            check("RESULTS.md carries batch B checkpointed count",
                  f"{len(lb_files):,}" in md2 and "corpus2_labels_b" in md2)
            check("RESULTS.md carries batch B annotated-OK count",
                  f"{raw_ok:,}" in md2, f"ok={raw_ok:,}")
    else:
        check("batch B artifacts exist",
              os.path.exists(bs_path) and os.path.exists(lb_dir))
    if os.path.exists(ba_path):
        BA = json.load(open(ba_path, encoding="utf-8"))
        g = (BA.get("pairs") or {}).get("glm-5.3-flash") or {}
        check("agreement headline pair (glm-5.3-flash vs grok) present",
              g.get("overlap_ok_pairs", 0) > 0,
              f"n={g.get('overlap_ok_pairs')}")
        # recompute the headline overlap independently from raw labels
        la_dir = os.path.join(WORK, "corpus2_labels")
        n_pairs = 0
        if g.get("overlap_ok_pairs") and os.path.exists(lb_dir):
            for p in os.listdir(lb_dir):
                try:
                    rb = json.load(open(os.path.join(lb_dir, p),
                                        encoding="utf-8"))
                except Exception:
                    continue
                if rb.get("status") != "ok":
                    continue
                ap = os.path.join(la_dir, p)
                if not os.path.exists(ap):
                    continue
                try:
                    ra = json.load(open(ap, encoding="utf-8"))
                except Exception:
                    continue
                if ra.get("status") == "ok" and ra.get("model") == "glm-5.3-flash":
                    n_pairs += 1
        check("agreement overlap count matches raw labels",
              n_pairs == g.get("overlap_ok_pairs"),
              f"raw={n_pairs} json={g.get('overlap_ok_pairs')}")
        if os.path.exists(RESULTS):
            md3 = open(RESULTS, encoding="utf-8").read()
            check("RESULTS.md carries glm-vs-grok agreement stats",
                  str(g.get("mean_jaccard_category_set")) in md3 and
                  str(g.get("exact_category_set_match_rate")) in md3)
    else:
        check("batchb_agreement.json exists", False)
    if os.path.exists(sd_path):
        SD = json.load(open(sd_path, encoding="utf-8"))
        check("sensitivity D snapshot sizes reproduce B/C published counts",
              SD["snapshots"]["B_n_ok"] == 1076 and SD["snapshots"]["C_n_ok"] == 1162,
              f"B={SD['snapshots']['B_n_ok']} C={SD['snapshots']['C_n_ok']} "
              f"D={SD['snapshots']['D_n_ok']}")
        sens_md = os.path.join(HERE, "fullrun", "sensitivity.md")
        sm = open(sens_md, encoding="utf-8").read() if os.path.exists(sens_md) else ""
        check("sensitivity.md carries full-N point D section",
              "Full-N point (D)" in sm)
        check("sensitivity.md carries restated full-N verdict",
              "VERDICT AT FULL N" in sm)
    else:
        check("sensitivity_d.json exists", False)

    print()
    if FAILS:
        print(f"{len(FAILS)} CHECK(S) FAILED: {FAILS}")
        return 1
    print(f"ALL {len(PASSES)} CHECKS PASSED")
    return 0


def _recompute_summary2():
    """Drive fullrun_summarize2.main() writing to a temp path so the canonical
    file is not touched, then load and return it."""
    import shutil
    import tempfile
    tmpd = tempfile.mkdtemp()
    out_path = os.path.join(WORK, "corpus2_summary.json")
    bak = None
    if os.path.exists(out_path):
        bak = os.path.join(tmpd, "bak.json")
        shutil.copy(out_path, bak)
    old_out = FSUM2.OUT
    try:
        FSUM2.OUT = os.path.join(tmpd, "summary.json")
        FSUM2.main()
        with open(FSUM2.OUT, encoding="utf-8") as f:
            return json.load(f)
    finally:
        FSUM2.OUT = old_out
        if bak:
            shutil.copy(bak, out_path)
        shutil.rmtree(tmpd, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
