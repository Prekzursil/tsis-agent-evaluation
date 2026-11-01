"""Tests for corpus/cross_taxonomy_join.py — the cross-taxonomy statistics engine.

Three end-to-end fixtures drive main() through every branch:
  * rich        — 6 join sessions exercising every normalization variant,
                  agreement cell, miss category, and decomposition counter
  * both-flag   — degenerate agreement (both flags always set): pe == 1 kappa
                  path, zero-cell chi2 path
  * all-clean   — no flags at all: previously crashed on log2(0) and on a
                  zero-margin chi2_contingency (fixed during onboarding)

Pure functions (norm_trail, shannon, js_divergence, bh_fdr) are unit-tested
against hand-computed values.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CORPUS = REPO / "corpus"
if str(CORPUS) not in sys.path:
    sys.path.insert(0, str(CORPUS))

import cross_taxonomy_join as ctj  # noqa: E402

# ── fixture builders ────────────────────────────────────────────────────────


def write_manifest(path: Path, shas: list[str]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for s in shas:
            f.write(json.dumps({"sha256": s}) + "\n")


def write_canonical(path: Path, shas: list[str]) -> None:
    with open(path, "w") as f:
        json.dump({"annotation_set": [{"sha256": s} for s in shas]}, f)


def write_mast(path: Path, rows: list[dict], blanks: int = 1) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
        for _ in range(blanks):
            f.write("\n")


def write_trail(dirp: Path, files: dict[str, dict]) -> None:
    dirp.mkdir(parents=True, exist_ok=True)
    for name, d in files.items():
        with open(dirp / name, "w") as f:
            json.dump(d, f)


def point_module(tmp: Path, monkeypatch, mast_rows, trail_files, manifest, canon):
    root = tmp / "run"
    root.mkdir(exist_ok=True)
    (root / "corpus").mkdir(exist_ok=True)
    monkeypatch.setattr(ctj, "BASE", str(root))
    monkeypatch.setattr(ctj, "MAST_LABELS", str(root / "mast" / "labels.jsonl"))
    monkeypatch.setattr(ctj, "TRAIL_DIR", str(root / "trail_labels"))
    monkeypatch.setattr(ctj, "MANIFEST", str(root / "corpus" / "manifest.jsonl"))
    monkeypatch.setattr(ctj, "CANONICAL", str(root / "corpus" / "canonical_set.json"))
    monkeypatch.setattr(ctj, "OUT", str(root / "corpus" / "cross_taxonomy_join.json"))
    Path(ctj.MAST_LABELS).parent.mkdir(parents=True, exist_ok=True)
    write_mast(Path(ctj.MAST_LABELS), mast_rows)
    write_trail(Path(ctj.TRAIL_DIR), trail_files)
    write_manifest(Path(ctj.MANIFEST), manifest)
    write_canonical(Path(ctj.CANONICAL), canon)
    return Path(ctj.OUT)


def mastrow(sha, ok, modes, target="p0", tc=True):
    return {"sha256": sha, "ok": ok, "target_id": target, "modes": modes, "task_completed": tc}


def trailfile(sha, errors, *, status="ok", **extra):
    d = {"sha256": sha, "status": status, "errors": errors}
    d.update(extra)
    return d


# ── pure functions ──────────────────────────────────────────────────────────


class TestNormTrail:
    def test_canonical_passthrough(self):
        assert ctj.norm_trail("Rate Limiting") == ("Rate Limiting", "")

    def test_parenthesized_tool_related(self):
        assert ctj.norm_trail("Tool-related (db lookup)") == (
            "Tool-related",
            "parenthesized-variant",
        )

    def test_hallucination_parent_path(self):
        cat, why = ctj.norm_trail("Hallucinations > Task Orchestration")
        assert cat == "Task Orchestration"
        assert why == "parent-path-variant"

    def test_head_with_parens(self):
        assert ctj.norm_trail("Task Orchestration (high)") == (
            "Task Orchestration",
            "parenthesized-variant",
        )

    def test_off_taxonomy(self):
        assert ctj.norm_trail("Not A Real Class") == (None, "off-taxonomy")


class TestShannon:
    def test_empty_is_zero(self):
        assert ctj.shannon([]) == 0.0

    def test_all_zero_counts_is_zero(self):
        assert ctj.shannon([0, 0, 0]) == 0.0

    def test_uniform_two_is_one_bit(self):
        assert ctj.shannon([2, 2]) == 1.0

    def test_single_nonzero_is_zero(self):
        assert ctj.shannon([4]) == 0.0

    def test_quarter_split(self):
        # H(1/4, 3/4) = 0.811278...
        assert ctj.shannon([1, 3]) == pytest.approx(0.8112781244591328)


class TestJsDivergence:
    def test_identical_is_zero(self):
        assert ctj.js_divergence([0.5, 0.5], [0.5, 0.5]) == pytest.approx(0.0)

    def test_disjoint_is_one(self):
        assert ctj.js_divergence([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)

    def test_zeros_skipped_not_crash(self):
        v = ctj.js_divergence([0.0, 1.0], [0.0, 1.0])
        assert v == pytest.approx(0.0)


class TestBhFdr:
    def test_known_example(self):
        assert ctj.bh_fdr([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.04, 0.04])

    def test_empty(self):
        assert ctj.bh_fdr([]) == []

    def test_single(self):
        assert ctj.bh_fdr([0.05]) == pytest.approx([0.05])

    def test_monotone_across_sort(self):
        qs = ctj.bh_fdr([0.9, 0.001, 0.5])
        assert qs[1] <= qs[2] <= qs[0]


# ── end-to-end: rich fixture ────────────────────────────────────────────────


@pytest.fixture()
def rich_out(tmp_path, monkeypatch, capsys):
    rows = [
        mastrow("h1", True, {"1.1": True, "2.3": False, "3.2": False}, tc=True),
        mastrow("h2", True, {"2.3": True}, target="p0", tc=False),
        mastrow("h2", True, {"2.3": False, "3.1": False}, target="p1", tc=False),
        mastrow("h3", True, {"1.1": False, "2.3": False, "3.2": False}, tc=True),
        mastrow("h4", True, {"3.2": True}, tc=False),
        mastrow("h5", True, {"1.1": True}, tc=True),  # mast-only
        mastrow("h6", False, {"1.1": False}),  # parsefail
        mastrow("h11", True, {"2.3": True}, tc=False),
        mastrow("h12", True, {"1.1": False, "2.3": False}, tc=True),
        mastrow("h13", True, {"3.2": True}, tc=True),  # mast-flagged (verify-only), trail-clean
        mastrow("h14", True, {"1.1": False}, tc=True),  # mast-clean, infra-only
    ]
    tf = {
        "a.json": trailfile(
            "h1",
            [{"category": "Tool-related (db)", "impact": "HIGH"}],
            n_errors=1,
            scores={"overall": 4},
            model="glm",
            runtime="claude",
        ),
        "b.json": trailfile(
            "h2",
            [
                {"category": "Hallucinations > Task Orchestration", "impact": "HIGH"},
                {"category": "Rate Limiting", "impact": "LOW"},
                {"category": "Not A Real Class", "impact": "LOW"},
            ],
            ext="sensitivity-ext",
            runtime="codex",
        ),
        "c.json": trailfile("h3", [], runtime="grok"),
        "d.json": trailfile(
            "h4",
            [{"category": "Task Orchestration (high)", "impact": "MEDIUM"}],
            scores={"overall": None},
            runtime="claude",
        ),
        "f.json": trailfile("h6", [{"category": "Formatting Errors", "impact": "LOW"}]),
        "g.json": trailfile("h7", [], status="error"),
        "h.json": trailfile("h8", [{"category": "Tool-related", "impact": "LOW"}]),
        "j.json": trailfile("h10", [{"category": "Timeout Issues", "impact": "LOW"}]),
        "k.json": trailfile("h11", [{"category": "Service Errors", "impact": "LOW"}]),
        "l.json": trailfile("h12", [{"category": "Formatting Errors", "impact": "LOW"}]),
        "m.json": trailfile("h13", []),
        "n.json": trailfile("h14", [{"category": "Service Errors", "impact": "LOW"}]),
    }
    out = point_module(
        tmp_path,
        monkeypatch,
        rows,
        tf,
        manifest=["h1", "h2", "h3", "h4", "h5", "h6"],
        canon=["h1", "h2", "h3"],
    )
    ctj.main()
    printed = capsys.readouterr().out
    with open(out) as f:
        return json.load(f), printed


def test_rich_diagnostics(rich_out):
    out, _ = rich_out
    d = out["diagnostics"]
    assert d["mast_ok_hashes"] == 9  # h1..h5,h11..h14
    assert d["trail_label_files"] == 12  # 12 files globbed
    assert d["trail_status"] == {"ok": 11, "error": 1}
    assert d["trail_ok_hashes"] == 11
    assert d["join_n"] == 8  # h1,h2,h3,h4,h11..h14
    assert d["join_in_manifest"] == 4  # h11..h14 not in manifest
    assert d["join_in_canonical"] == 3  # h1,h2,h3
    assert d["trail_ok_not_mast_ok"] == 3  # h6,h8,h10
    assert d["join_multipart_hashes"] == 1  # h2
    assert d["join_trail_ext_labels"] == 1  # h2
    assert d["trail_ok_not_mast_ok__was_mast_target_parsefail"] == 1  # h6
    assert d["trail_ok_not_mast_ok__never_mast_target"] == 2  # h8,h10
    assert "parenthesized-variant:Tool-related (db)" in d["category_normalizations"]
    assert "parent-path-variant:Hallucinations > Task Orchestration" in d["category_normalizations"]
    assert "parenthesized-variant:Task Orchestration (high)" in d["category_normalizations"]
    assert "off-taxonomy:Not A Real Class" in d["category_normalizations"]


def test_rich_agreement_all_cells_positive(rich_out):
    out, _ = rich_out
    a = out["agreement_anyflag"]
    assert (a["both"], a["mast_only"], a["trail_only"], a["neither"]) == (4, 1, 2, 1)
    assert a["n"] == 8
    assert math.isfinite(a["chi2"])  # all cells > 0 -> real chi2
    assert math.isfinite(a["kappa"])  # pe < 1
    assert math.isfinite(a["phi"])
    assert a["mast_any_rate"] == pytest.approx(5 / 8)
    assert a["trail_any_rate"] == pytest.approx(6 / 8)
    assert a["jaccard_anyflag"] == pytest.approx(4 / 7)


def test_rich_multipart_mode_or_and_part0_task(rich_out):
    out, _ = rich_out
    # h2: part0 says 2.3=True, part1 False -> OR-true; task_completed from part0
    cooc = out["cooccurrence"]["2.3"]
    assert cooc["Rate Limiting"] == 1
    assert out["continuous"]["tc_overall_scores"]["False"]["n"] == 3


def test_rich_observed_classes_only_from_join(rich_out):
    out, _ = rich_out
    # h6/h8/h10 classes are outside the join -> not observed
    assert set(out["observed_classes"]) == {
        "Tool-related",
        "Task Orchestration",
        "Rate Limiting",
        "Service Errors",
        "Formatting Errors",
    }
    assert out["class_marginals"]["Formatting Errors"] == 1  # h12 only
    assert out["class_marginals"]["Service Errors"] == 2  # h11 + h14
    assert out["class_marginals"]["Task Orchestration"] == 2  # h2 + h4
    # h1 is the only join session with 1.1 flagged (h5 is mast-only)
    assert out["mode_marginals"]["1.1"] == 1
    assert out["mode_marginals"]["2.3"] == 2  # h2 + h11
    assert out["mode_marginals"]["3.2"] == 2  # h4 + h13


def test_rich_misses(rich_out):
    out, _ = rich_out
    m = out["misses"]
    assert m["trail_flagged_mast_clean_n"] == 2  # h12, h14
    assert m["classes_in_trail_flagged_mast_clean"] == {"Formatting Errors": 1, "Service Errors": 1}
    assert m["mast_flagged_trail_clean_n"] == 1  # h13
    assert m["modes_in_mast_flagged_trail_clean"] == {"3.2": 1}
    assert m["infra_only_sessions_n"] == 2  # h11, h14
    assert m["infra_only_mast_flagged"] == 1  # h11 flagged, h14 clean
    assert m["verify_only_sessions_n"] == 2  # h4 (has cats), h13 (none)
    assert m["verify_only_trail_flagged"] == 1
    assert m["trail_class_labels_in_mast_clean_sessions"] == 2
    assert m["mast_mode_labels_in_trail_clean_sessions"] == 1


def test_rich_entropy_and_pairs(rich_out):
    out, _ = rich_out
    # mode 1.1 fires once; modes that never fire -> H_norm 0, mean nan
    em = out["entropy_by_mode"]["1.1"]
    assert em["n_yes"] == 1
    em0 = out["entropy_by_mode"]["1.3"]
    assert em0["H_norm_yes"] == 0.0 and math.isnan(em0["mean_errs_yes"])
    ec = out["entropy_by_class"]["Tool-related"]
    assert ec["n_yes"] == 1
    # every pair carries BH q-values
    assert len(out["pair_stats"]) == len(ctj.MAST_MODES) * len(out["observed_classes"])
    assert all("q_bh" in ps for ps in out["pair_stats"])


def test_rich_continuous_and_selection(rich_out):
    out, _ = rich_out
    c = out["continuous"]
    assert math.isfinite(c["spearman_nmodes_nerrs"])
    # tc=True group: h1 (4.0) + three score-less -> one non-None value
    assert c["tc_overall_scores"]["True"] == {"n": 5, "mean_overall": pytest.approx(4.0)}
    assert c["tc_overall_scores"]["False"]["n"] == 3
    im = c["impact_mix_by_mastflag"]
    assert im["mast_flagged"]["HIGH"] == 2
    assert im["mast_flagged"]["MEDIUM"] == 1
    assert im["mast_clean"]["LOW"] == 2
    # h2's off-taxonomy error still carries an impact label -> 6 not 5
    assert im["mast_flagged"]["total"] == 6
    s = out["selection_check"]["1.1"]
    assert s["join_rate"] == pytest.approx(1 / 8)
    assert s["full_rate"] == pytest.approx(2 / 9)
    assert out["n_full_mast_ok_hashes"] == 9
    rt = out["runtime_mix"]
    assert rt["join"]["claude"] == 2
    assert rt["trail_ok"]["codex"] == 1


def test_rich_category_root_matrix(rich_out):
    out, _ = rich_out
    m = out["category_root_matrix"]["matrix"]
    assert m["FC1 System Design / Specification"]["Reasoning Errors"] == 1  # h1
    assert m["FC2 Inter-Agent Misalignment"]["Planning and Coordination Errors"] == 1  # h2
    assert m["FC2 Inter-Agent Misalignment"]["System Execution Errors"] == 2  # h2 + h11
    assert m["FC3 Task Verification"]["Planning and Coordination Errors"] == 1  # h4
    assert out["category_root_matrix"]["n_labels"] == 5


def test_rich_console_summary(rich_out):
    _, printed = rich_out
    assert "JOIN N=8" in printed
    assert "wrote" in printed


# ── end-to-end: degenerate fixtures ────────────────────────────────────────


def test_both_flagged_degenerate(tmp_path, monkeypatch, capsys):
    """Every session flagged by both: pe==1 -> kappa/phi/chi2 nan, mean_*_no nan."""
    rows = [
        mastrow("a", True, {"1.1": True}),
        mastrow("b", True, {"1.1": True}),
    ]
    tf = {
        "a.json": trailfile("a", [{"category": "Tool-related", "impact": "LOW"}]),
        "b.json": trailfile("b", [{"category": "Tool-related", "impact": "LOW"}]),
    }
    out_p = point_module(tmp_path, monkeypatch, rows, tf, ["a", "b"], ["a"])
    ctj.main()
    capsys.readouterr()
    with open(out_p) as f:
        out = json.load(f)
    a = out["agreement_anyflag"]
    assert (a["both"], a["mast_only"], a["trail_only"], a["neither"]) == (2, 0, 0, 0)
    assert math.isnan(a["kappa"]) and math.isnan(a["chi2"]) and math.isnan(a["phi"])
    assert a["jaccard_anyflag"] == pytest.approx(1.0)
    # mode fires in ALL sessions -> no-session complement is empty -> mean nan
    assert math.isnan(out["entropy_by_mode"]["1.1"]["mean_errs_no"])
    # class fires in ALL sessions
    assert math.isnan(out["entropy_by_class"]["Tool-related"]["mean_modes_no"])


def test_all_clean_degenerate(tmp_path, monkeypatch, capsys):
    """Zero flags anywhere: pre-fix this crashed (log2(0), zero-margin chi2)."""
    rows = [mastrow("c", True, {"1.1": False})]
    tf = {"c.json": trailfile("c", [])}
    out_p = point_module(tmp_path, monkeypatch, rows, tf, ["c"], ["c"])
    ctj.main()  # must not raise
    printed = capsys.readouterr().out
    with open(out_p) as f:
        out = json.load(f)
    a = out["agreement_anyflag"]
    assert (a["both"], a["mast_only"], a["trail_only"], a["neither"]) == (0, 0, 0, 1)
    assert math.isnan(a["kappa"])
    assert out["observed_classes"] == []
    assert out["pair_stats"] == []
    assert out["entropy_by_mode"]["1.1"]["H_norm_yes"] == 0.0
    cr = out["category_root_matrix"]
    assert cr["n_labels"] == 0 and math.isnan(cr["chi2"])
    assert "JOIN N=1" in printed


def test_mast_only_never_in_join(tmp_path, monkeypatch, capsys):
    """A MAST-ok hash with no TRAIL file joins nothing but still counts in selection."""
    rows = [mastrow("z", True, {"2.2": True})]
    tf = {}  # no trail files at all
    out_p = point_module(tmp_path, monkeypatch, rows, tf, ["z"], ["z"])
    ctj.main()
    capsys.readouterr()
    with open(out_p) as f:
        out = json.load(f)
    assert out["diagnostics"]["join_n"] == 0
    assert out["agreement_anyflag"]["n"] == 0
    assert out["n_full_mast_ok_hashes"] == 1
