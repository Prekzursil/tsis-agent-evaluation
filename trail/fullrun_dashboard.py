"""Build work/fullrun/dashboard.html - corpus-wide failure-class distribution
(ALL runtimes, canonical deduplicated set) + gold-agreement tables.
Self-contained offline HTML (no external JS/CSS); data embedded as JSON
aggregates ONLY (labels/counts/ids - privacy contract).
"""
from __future__ import annotations

import json
import os

from fullrun_common import LANE, FULL_MODEL, FLASH_MODEL

WORK = os.path.join(LANE, "work", "fullrun")
SUMMARY = os.path.join(WORK, "corpus2_summary.json")
AGREEMENT = os.path.join(WORK, "gold_agreement.json")
OUT = os.path.join(WORK, "dashboard.html")

ROOT_COLORS = {
    "Reasoning Errors": "#e05d5d",
    "System Execution Errors": "#4f86e0",
    "Planning and Coordination Errors": "#3fa46a",
}


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def bars(items, max_val, unit="labels"):
    out = []
    for label, val, extra, color in items:
        pct = (val / max_val * 100) if max_val else 0
        out.append(f"""
        <div class="barrow"><div class="barlab">{esc(label)}</div>
          <div class="bartrack"><div class="barfill" style="width:{pct:.1f}%;background:{color}"></div></div>
          <div class="barval">{val:,} {esc(extra or unit)}</div></div>""")
    return "".join(out)


def main():
    S = json.load(open(SUMMARY, encoding="utf-8"))
    A = json.load(open(AGREEMENT, encoding="utf-8")) if os.path.exists(AGREEMENT) else None

    cats = S["category_counts"]
    prev = S.get("category_trace_prevalence", {})
    ok_n = S["traces_annotated_ok"]
    by_root = S["category_counts_by_root"]

    root_of = {}
    for root, leaves in by_root.items():
        for l in leaves:
            root_of[l] = root
    ordered = []
    for root, leaves in by_root.items():
        for leaf in leaves:
            if cats.get(leaf, 0) or prev.get(leaf, 0):
                ordered.append((leaf, cats.get(leaf, 0), prev.get(leaf, 0),
                                ROOT_COLORS[root], root))
    ordered.sort(key=lambda x: -x[1])
    offtax = [(c, n, prev.get(c, 0), "#888") for c, n in cats.items() if c not in root_of]

    max_lab = max([n for _, n, *_ in ordered] + [1])
    cat_bars = bars([(f"{l}", n, f"({p} traces)", col) for l, n, p, col, r in ordered],
                    max_lab)
    offtax_html = bars([(f"{c} [off-taxonomy]", n, f"({p} traces)", col)
                        for c, n, p, col in offtax], max_lab) or "<p>(none)</p>"
    imp = S["impact_counts"]
    imp_bars = bars([(k, imp[k], "", "#8e6fbf") for k in
                     sorted(imp, key=imp.get, reverse=True)], max(imp.values()) or 1)

    # per-runtime coverage table
    rt_tr = S.get("per_runtime_traces", {})
    rt_ok = S.get("per_runtime_ok", {})
    rt_el = S.get("per_runtime_eligible", {})
    rt_err = S.get("per_runtime_errors", {})
    rt_rows = "".join(
        f"<tr><td>{esc(k)}</td><td class='n'>{v:,}</td>"
        f"<td class='n'>{rt_el.get(k, 0):,}</td>"
        f"<td class='n'>{rt_ok.get(k, 0):,}</td>"
        f"<td class='n'>{(100.0 * rt_ok.get(k, 0) / rt_el[k]) if rt_el.get(k) else 0:.1f}%</td>"
        f"<td class='n'>{rt_err.get(k, 0):,}</td>"
        f"<td class='n'>{(rt_err.get(k, 0) / rt_ok.get(k, 0)) if rt_ok.get(k, 0) else 0:.2f}</td></tr>"
        for k, v in sorted(rt_tr.items(), key=lambda kv: -kv[1]))

    rub = S.get("score_rubric_means", {})
    rub_rows = "".join(
        f"<tr><td>{esc(k.replace('_', ' '))}</td><td class='n'>{v:.2f}</td></tr>"
        for k, v in rub.items() if v is not None)

    st = S.get("status_counts", {})
    st_rows = "".join(f"<tr><td>{esc(k)}</td><td class='n'>{v:,}</td></tr>"
                      for k, v in sorted(st.items(), key=lambda kv: -kv[1]))
    pm_tr = S.get("per_model_traces", {})
    pm_ok = S.get("per_model_ok", {})
    model_rows_html = "<table><tr><th>annotator model</th><th>files processed</th>"         "<th>annotated OK</th></tr>" + "".join(
        f"<tr><td>{esc(k)}</td><td class='n'>{v:,}</td>"
        f"<td class='n'>{pm_ok.get(k, 0):,}</td></tr>"
        for k, v in sorted(pm_tr.items(), key=lambda kv: -kv[1])) + "</table>"

    gold_html = "<p>(gold agreement not yet available)</p>"
    if A:
        o = A["overall"]
        rows = [
            ("Overall (FULL-148, union of top-tier annotators)", o),
            ("GAIA split", A["splits"].get("GAIA")),
            ("SWE Bench split", A["splits"].get("SWE Bench")),
            ("Repo-exact GAIA (their scorer verbatim)", A["repo_exact"].get("GAIA")),
            ("Repo-exact SWE (their scorer verbatim)", A["repo_exact"].get("SWE Bench")),
        ]
        for mname, bm in A.get("by_model", {}).items():
            if bm["overall"]["files_processed"]:
                rows.append((f"Batch: {mname} (single-model)", bm["overall"]))
        trs = []
        for name, r in rows:
            if not r:
                continue
            trs.append(f"<tr><td>{esc(name)}</td><td class='n'>{r.get('files_processed', '-')}</td>"
                       f"<td class='n'>{r['weighted_f1']:.4f}</td>"
                       f"<td class='n'>{r['location_accuracy']:.4f}</td>"
                       f"<td class='n'>{r['joint_accuracy']:.4f}</td></tr>")
        gold_html = f"""<table class="metrics"><tr><th>Run</th><th>files</th>
            <th>weighted F1</th><th>loc acc</th><th>joint acc</th></tr>{''.join(trs)}</table>
            <p class="note">Crosscheck vs repo scorer (bit-exact &le;1e-9):
            {'PASS' if A['crosscheck']['bit_exact_within_1e-9'] else 'FAIL ' + str(A['crosscheck']['diffs'][:3])}</p>"""
        cm = o["category_metrics"]
        cat_metric_rows = "".join(
            f"<tr><td>{esc(c)}</td><td class='n'>{m['support']}</td>"
            f"<td class='n'>{m['precision']:.3f}</td><td class='n'>{m['recall']:.3f}</td>"
            f"<td class='n'>{m['f1']:.3f}</td></tr>"
            for c, m in sorted(cm.items(), key=lambda kv: -kv[1]["support"])
            if m["support"] > 0)
        gold_html += f"""<h3>Per-error-class agreement (FULL-148)</h3>
        <table class="metrics"><tr><th>error class</th><th>gold support</th>
            <th>precision</th><th>recall</th><th>F1</th></tr>{cat_metric_rows}</table>"""

    u = S["usage"]
    elig = S.get("census_eligible_sessions") or 0
    cov = (ok_n / elig) if elig else 0
    man = S.get("manifest", {})
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>TRAIL x GLM - single-user agent-harness failure dashboard</title>
<style>
 body{{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#0f1216;color:#dde3ea}}
 header{{padding:24px 32px;background:linear-gradient(120deg,#1a2332,#101820);border-bottom:2px solid #2c3a4d}}
 h1{{margin:0 0 6px;font-size:22px}} h2{{font-size:17px;margin:28px 0 10px;color:#9fc1e8;border-bottom:1px solid #2c3a4d;padding-bottom:6px}}
 h3{{font-size:14px;margin:18px 0 8px;color:#b7c9dd}}
 .sub{{color:#8494a8;font-size:13px}}
 .wrap{{padding:8px 32px 48px;max-width:1100px}}
 .cards{{display:flex;gap:14px;flex-wrap:wrap;margin:18px 0}}
 .card{{background:#161c24;border:1px solid #2c3a4d;border-radius:10px;padding:14px 18px;min-width:150px}}
 .card .v{{font-size:24px;font-weight:600;color:#e8f0fa}} .card .k{{font-size:11px;color:#8494a8;text-transform:uppercase;letter-spacing:.06em}}
 .barrow{{display:flex;align-items:center;margin:4px 0;font-size:12.5px}}
 .barlab{{width:270px;color:#c6d2e0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
 .bartrack{{flex:1;background:#1c2430;border-radius:4px;height:16px;overflow:hidden}}
 .barfill{{height:100%;border-radius:4px 0 0 4px}}
 .barval{{width:200px;text-align:right;color:#8494a8;font-size:11.5px}}
 table{{border-collapse:collapse;width:100%;font-size:12.5px;margin:8px 0}}
 th,td{{padding:6px 10px;border-bottom:1px solid #232d3a;text-align:left}}
 th{{color:#9fc1e8;font-weight:600;background:#141a22}} td.n{{text-align:right;font-variant-numeric:tabular-nums}}
 .note{{color:#8494a8;font-size:11.5px}} .legend span{{display:inline-block;margin-right:14px;font-size:12px}}
 .dot{{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:middle}}
 footer{{padding:18px 32px;color:#5c6b7d;font-size:11px;border-top:1px solid #2c3a4d}}
</style></head><body>
<header>
 <h1>What breaks in a single-user, long-horizon coding-agent harness</h1>
 <div class="sub">TRAIL taxonomy (patronus-ai/trail-benchmark) &times; GLM annotators &mdash; gold-set agreement + multi-runtime session-journal corpus (canonical deduplicated set)</div>
 <div class="sub">Annotators (gold, top tier, per-file attribution in MODEL_MANIFEST.json): <b>glm-5.3</b> + <b>nvidia/nemotron-3-ultra-550b-a55b</b> &middot; Annotators (corpus, single-model batches): <b>{esc(', '.join(S.get('per_model_ok', {}).keys()) or FLASH_MODEL)}</b> &middot; paper prompt <code>run_eval.get_prompt()</code> verbatim</div>
</header><div class="wrap">

<div class="cards">
 <div class="card"><div class="v">{S['label_files']:,}</div><div class="k">unique canonical files processed</div></div>
 <div class="card"><div class="v">{elig:,}</div><div class="k">eligible unique sessions (census)</div></div>
 <div class="card"><div class="v">{(cov * 100) if cov else 0:.1f}%</div><div class="k">eligible-set annotation coverage</div></div>
 <div class="card"><div class="v">{ok_n:,}</div><div class="k">annotated OK</div></div>
 <div class="card"><div class="v">{S['total_error_labels']:,}</div><div class="k">error labels</div></div>
 <div class="card"><div class="v">{S['traces_with_errors']:,}</div><div class="k">sessions with &ge;1 error</div></div>
 <div class="card"><div class="v">{S['errors_per_trace_mean'] or 0:.1f}</div><div class="k">mean errors / annotated session</div></div>
 <div class="card"><div class="v">{man.get('records_inheriting_ok_annotation', 0):,}</div><div class="k">manifest paths inheriting OK annotation</div></div>
 <div class="card"><div class="v">{S['spans_total']:,}</div><div class="k">spans ingested</div></div>
 <div class="card"><div class="v">{u['prompt_tokens'] / 1e6:.1f}M</div><div class="k">corpus prompt tokens</div></div>
</div>

<h2>Corpus-wide failure-class distribution</h2>
<div class="legend">{''.join(f'<span><i class="dot" style="background:{c}"></i>{esc(r)}</span>' for r, c in ROOT_COLORS.items())}<span><i class="dot" style="background:#888"></i>off-taxonomy</span></div>
{cat_bars}
<h3>Off-taxonomy labels emitted by the annotator</h3>
{offtax_html}
<h3>Impact distribution</h3>
{imp_bars}

<h2>Per-runtime coverage (unique-file basis; duplicates inherit their hash)</h2>
<table><tr><th>runtime</th><th>processed</th><th>eligible (census)</th><th>annotated OK</th>
 <th>OK coverage</th><th>error labels</th><th>labels/OK session</th></tr>{rt_rows}</table>

<h2>Sweep status counts (every canonical file accounted for)</h2>
<table><tr><th>status</th><th>files</th></tr>{st_rows}</table>

<h2>Corpus batches by annotator model (single-model batches)</h2>
{model_rows_html}

<h2>Rubric score means over annotated sessions (0&ndash;5)</h2>
<table><tr><th>rubric</th><th>mean</th></tr>{rub_rows}</table>

<h2>Gold-set agreement (released TRAIL benchmark, ENTIRE set)</h2>
{gold_html}

</div>
<footer>Generated by fullrun_dashboard.py from corpus2_summary.json + gold_agreement.json (labels/counts/aggregates only - no session content). Repo: patronus-ai/trail-benchmark @ 0ffbed9.</footer>
</body></html>"""
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(html)
    print("wrote", OUT, f"({len(html):,} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
