#!/usr/bin/env python3
"""Real-data dashboard for the FULL-CORPUS (multi-runtime, both drives) MAST sweep.
Counts only. Reads aggregates2.json + privacy_scan_full2.json + crosscheck2_agreement.json
and writes dashboard_full2.html - self-contained, offline, no trace content.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MODE_NAMES = {
    "1.1": "Disobey Task Specification", "1.2": "Disobey Role Specification",
    "1.3": "Step Repetition", "1.4": "Loss of Conversation History",
    "1.5": "Unaware of Termination Conditions", "2.1": "Conversation Reset",
    "2.2": "Fail to Ask for Clarification", "2.3": "Task Derailment",
    "2.4": "Information Withholding", "2.5": "Ignored Other Agent's Input",
    "2.6": "Action-Reasoning Mismatch", "3.1": "Premature Termination",
    "3.2": "Weak Verification", "3.3": "No or Incorrect Verification",
}
# arXiv:2503.13657 (MAST) per-mode prevalence on its multi-user CrewAI/AutoGen-class
# benchmark corpus (210 traces, 7 frameworks) - extracted from the PDF text this lane.
PAPER = {"1.1": 11.8, "1.2": 1.5, "1.3": 15.7, "1.4": 2.8, "1.5": 12.4,
         "2.1": 2.2, "2.2": 6.8, "2.3": 7.4, "2.4": 0.85, "2.5": 1.9, "2.6": 13.2,
         "3.1": 6.2, "3.2": 8.2, "3.3": 9.1}
PAPER_CAT = {"FC1": 44.2, "FC2": 32.3, "FC3": 23.5}   # sum of paper per-mode prevalences
PAPER_CAT_FIG4 = {"FC1": 41.8, "FC2": 36.9, "FC3": 21.3}  # paper Fig.4 category split
CAT_OF = {**{m: "FC1" for m in list(MODE_NAMES)[:5]},
          **{m: "FC2" for m in list(MODE_NAMES)[5:11]},
          **{m: "FC3" for m in list(MODE_NAMES)[11:]}}
CAT_COLOR = {"FC1": "#e74c3c", "FC2": "#f39c12", "FC3": "#2980b9"}


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def main():
    agg = json.loads((HERE / "aggregates2.json").read_text(encoding="utf-8"))
    priv = None
    p = HERE / "privacy_scan_full2.json"
    if p.exists():
        priv = json.loads(p.read_text(encoding="utf-8"))
    xchk = agg.get("crosscheck") or {}

    modes = agg["modes"]
    n = agg["n_labeled_ok"]
    tc = agg["task_completed"]
    rows = []
    for m in sorted(MODE_NAMES):
        d = modes[m]
        rows.append({"code": m, "name": MODE_NAMES[m], "cat": CAT_OF[m],
                     "inc": d["incidence_pct"], "occ": d["occurrence_share_pct"],
                     "yes": d["yes"], "paper": PAPER[m]})
    rows_sorted = sorted(rows, key=lambda r: -r["inc"])
    max_inc = max([r["inc"] for r in rows] + [1.0])

    months = agg["monthly"]
    mo_labels = json.dumps(list(months.keys()))
    mo_n = json.dumps([months[k]["n"] for k in months])
    mo_fail = json.dumps([months[k]["any_fail_pct"] for k in months])

    cat_share = {c: agg["categories"][c]["occurrence_share_pct"] for c in CAT_COLOR}

    priv_rows = ""
    if priv:
        pr = priv["pii_ish"]
        priv_rows = "".join(
            f"<tr><td>{esc(k)}</td><td class='num'>{v['lines']:,}</td>"
            f"<td class='num'>{v['line_ratio'] * 100:.2f}%</td></tr>"
            for k, v in sorted(pr.items(), key=lambda kv: -kv[1]["lines"]))

    xchk_html = "<p class='muted'>cross-check not yet available</p>"
    if xchk.get("n_pairs"):
        xchk_html = (
            f"<p><b>{xchk['n_pairs']}</b> traces double-annotated "
            f"(flash <code>{esc(xchk['model_flash'])}</code> vs full "
            f"<code>{esc(xchk['model_full'])}</code>).</p>"
            "<table class='tbl'><tr><th>mode</th><th>agree%</th><th>yes|yes</th>"
            "<th>yes|no</th><th>no|yes</th><th>no|no</th></tr>"
            + "".join(
                f"<tr><td>{m} {esc(MODE_NAMES[m])}</td>"
                f"<td class='num'>{d['agree_pct']:.0f}%</td>"
                f"<td class='num'>{d['yy']}</td><td class='num'>{d['yn']}</td>"
                f"<td class='num'>{d['ny']}</td><td class='num'>{d['nn']}</td></tr>"
                for m, d in xchk["modes"].items())
            + f"</table><p class='muted'>task_completed agreement: "
              f"{xchk['task_agree_pct']:.0f}% &middot; mean mode-agreement: "
              f"{xchk['mean_agree_pct']:.1f}%</p>")

    mode_rows_html = "".join(
        f"<tr><td><span class='dot {CAT_OF[r['code']]}'></span>{r['code']} {esc(r['name'])}</td>"
        f"<td class='num'>{r['yes']:,}</td>"
        f"<td class='num'>{r['inc']:.1f}%</td>"
        f"<td class='num'>{r['occ']:.1f}%</td>"
        f"<td class='num muted'>{r['paper']:.2f}%</td></tr>"
        for r in rows_sorted)

    bars_html = "".join(
        f"<div class='brow'><div class='blabel'>{r['code']} {esc(r['name'])}</div>"
        f"<div class='bar'><div class='fill {CAT_OF[r['code']]}' "
        f"style='width:{max(0.6, 100 * r['inc'] / max_inc):.1f}%'></div></div>"
        f"<div class='bval'>{r['inc']:.1f}%</div></div>"
        for r in rows_sorted)

    rt_rows = ""
    for rt, v in list(agg["by_runtime"].items())[:14]:
        rt_rows += (f"<tr><td>{esc(rt)}</td><td class='num'>{v['n']:,}</td>"
                    f"<td class='num'>{v['task_completed_pct']:.0f}%</td>"
                    f"<td class='num'>{v['modes'].get(v['top_mode'], 0) if v['top_mode'] else 0:.1f}%"
                    f" ({v['top_mode'] or '-'})</td></tr>")

    fmt_rows = ""
    for f_, v in list(agg["by_format"].items())[:12]:
        fmt_rows += (f"<tr><td>{esc(f_)}</td><td class='num'>{v['n']:,}</td>"
                     f"<td class='num'>{v['task_completed_pct']:.0f}%</td>"
                     f"<td class='num'>{v['top_mode'] or '-'}</td></tr>")

    mo_rows = ""
    for k, v in agg["monthly"].items():
        mo_rows += (f"<tr><td>{esc(k)}</td><td class='num'>{v['n']:,}</td>"
                    f"<td class='num'>{v['any_fail_pct']:.1f}%</td></tr>")

    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>MASTscope — full-corpus (multi-runtime) failure-mode distribution</title>
<style>
 body{{font-family:'Segoe UI',system-ui,sans-serif;margin:0;background:#0f1420;color:#e8eaf0}}
 header{{padding:18px 28px;background:linear-gradient(90deg,#1a2340,#101728);border-bottom:1px solid #2a3550}}
 h1{{margin:0;font-size:20px}} .sub{{color:#8fa3c8;font-size:12px;margin-top:4px}}
 main{{padding:20px 28px;display:grid;grid-template-columns:1fr 1fr;gap:18px}}
 .card{{background:#161e30;border:1px solid #263250;border-radius:10px;padding:16px}}
 .card h2{{font-size:14px;margin:0 0 10px;color:#aab8d8;text-transform:uppercase;letter-spacing:.06em}}
 .wide{{grid-column:1/3}}
 table.tbl{{width:100%;border-collapse:collapse;font-size:12.5px}}
 .tbl th,.tbl td{{padding:4px 8px;border-bottom:1px solid #222c48;text-align:left}}
 .tbl th{{color:#8fa3c8;font-weight:600}}
 td.num{{text-align:right;font-variant-numeric:tabular-nums}}
 .muted{{color:#7c8db0}}
 .dot{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px}}
 .FC1{{background:#e74c3c}} .FC2{{background:#f39c12}} .FC3{{background:#2980b9}}
 .brow{{display:flex;align-items:center;gap:8px;margin:3px 0;font-size:12px}}
 .blabel{{width:270px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
 .bar{{flex:1;background:#0d1322;border-radius:4px;height:14px}}
 .fill{{height:100%;border-radius:4px}}
 .bval{{width:52px;text-align:right;font-variant-numeric:tabular-nums}}
 .kpi{{display:flex;gap:22px;flex-wrap:wrap}}
 .kpi div{{font-size:12px;color:#8fa3c8}} .kpi b{{display:block;font-size:22px;color:#e8eaf0}}
 .legend{{font-size:11px;color:#8fa3c8;margin-top:8px}}
</style></head><body>
<header>
 <h1>MASTscope — single-user, long-horizon, multi-runtime agent corpus — full MAST annotation</h1>
 <div class="sub">Rebuilt corpus: both drives, {agg['targets_total']:,} unique-hash parseable sessions across
 runtimes (Claude Code live+free, vault, Codex, grok, gemini, zcode, ChatGPT exports, VM backups)
 &middot; labels/counts only, no trace content on this page</div>
</header>
<main>
 <div class="card wide"><div class="kpi">
   <div>sessions annotated<b>{n:,}</b></div>
   <div>target set<b>{agg['targets_total']:,}</b></div>
   <div>pending<b>{agg['pending']:,}</b></div>
   <div>total failure labels<b>{agg['total_yes_labels']:,}</b></div>
   <div>traces w/ &ge;1 mode<b>{agg['traces_with_any_mode']:,}</b></div>
   <div>task completed yes/no/null<b>{tc.get('yes',0):,} / {tc.get('no',0):,} / {tc.get('null',0):,}</b></div>
 </div></div>

 <div class="card"><h2>Failure-mode incidence (% of traces)</h2>
  {bars_html}
  <div class="legend"><span class="dot FC1"></span>FC1 System/Specification
   <span class="dot FC2"></span>FC2 Inter-Agent Misalignment
   <span class="dot FC3"></span>FC3 Task Verification</div></div>

 <div class="card"><h2>Distribution table — ours vs MAST paper</h2>
  <table class='tbl'><tr><th>mode</th><th>yes</th><th>incidence</th>
   <th>occ. share</th><th>paper prev.</th></tr>{mode_rows_html}</table>
  <div class="legend">occ. share = share of all failure-label occurrences (paper-comparable);
   paper prev. = arXiv:2503.13657 multi-user benchmark corpus (CrewAI/AutoGen class)</div></div>

 <div class="card"><h2>Category shares — ours vs paper</h2>
  <table class='tbl'><tr><th>category</th><th>ours (occ)</th><th>paper (mode-sum)</th><th>paper Fig.4</th></tr>
   <tr><td><span class="dot FC1"></span>FC1 System Design / Specification</td>
    <td class='num'>{cat_share['FC1']:.1f}%</td><td class='num muted'>{PAPER_CAT['FC1']:.1f}%</td>
    <td class='num muted'>{PAPER_CAT_FIG4['FC1']:.1f}%</td></tr>
   <tr><td><span class="dot FC2"></span>FC2 Inter-Agent Misalignment</td>
    <td class='num'>{cat_share['FC2']:.1f}%</td><td class='num muted'>{PAPER_CAT['FC2']:.1f}%</td>
    <td class='num muted'>{PAPER_CAT_FIG4['FC2']:.1f}%</td></tr>
   <tr><td><span class="dot FC3"></span>FC3 Task Verification</td>
    <td class='num'>{cat_share['FC3']:.1f}%</td><td class='num muted'>{PAPER_CAT['FC3']:.1f}%</td>
    <td class='num muted'>{PAPER_CAT_FIG4['FC3']:.1f}%</td></tr></table>
  <canvas id="trend" height="240" style="width:100%;margin-top:10px"></canvas>
  <div class="legend">monthly: bar = sessions annotated, line = % sessions with &ge;1 mode</div></div>

 <div class="card"><h2>By runtime (top)</h2>
  <table class='tbl'><tr><th>runtime</th><th>n</th><th>task done</th><th>top mode</th></tr>{rt_rows}</table>
  <h2 style="margin-top:12px">By session format</h2>
  <table class='tbl'><tr><th>format</th><th>n</th><th>task done</th><th>top mode</th></tr>{fmt_rows}</table>
  <h2 style="margin-top:12px">By month</h2>
  <table class='tbl'><tr><th>month</th><th>n</th><th>%&ge;1 mode</th></tr>{mo_rows}</table></div>

 <div class="card"><h2>Privacy scan (whole rebuilt corpus, counts only)</h2>
  {"<table class='tbl'><tr><th>category</th><th>lines</th><th>line ratio</th></tr>" + priv_rows +
   "<div class='legend'>files " + format(priv.get('files_scanned', 0), ',') + ", lines " +
   format(priv.get('total_lines', 0), ',') + ", json rate " +
   str(priv.get('json_line_rate')) + ", bytes " + format(priv.get('bytes_scanned', 0), ',') +
   "</div>" if priv else "<p class='muted'>privacy scan output not present</p>"}
 </div>

 <div class="card wide"><h2>Tier agreement (flash volume vs full-tier cross-check)</h2>{xchk_html}</div>
</main>
<script>
const M={mo_labels},N={mo_n},F={mo_fail};
const c=document.getElementById('trend').getContext('2d');
const W=c.canvas.width,H=c.canvas.height;
c.canvas.width=c.canvas.offsetWidth;
const w=c.canvas.width,pad=34,bw=Math.max(4,(w-2*pad)/M.length*0.55);
c.strokeStyle='#2a3550';c.beginPath();c.moveTo(pad,10);c.lineTo(pad,H-24);c.lineTo(w-8,H-24);c.stroke();
const mx=Math.max(...N,1);
c.fillStyle='#3b4a76';
M.forEach((m,i)=>{{const x=pad+i*(w-2*pad)/M.length;const h=(H-34)*N[i]/mx;
 c.fillRect(x,H-24-h,bw,h);}});
c.strokeStyle='#3ddc84';c.lineWidth=2;c.beginPath();
M.forEach((m,i)=>{{const x=pad+i*(w-2*pad)/M.length+bw/2;const y=H-24-(H-34)*F[i]/100;
 i?c.lineTo(x,y):c.moveTo(x,y);}});c.stroke();
c.fillStyle='#8fa3c8';c.font='9px sans-serif';
M.forEach((m,i)=>{{if(M.length<=20||i%2==0){{const x=pad+i*(w-2*pad)/M.length;
 c.save();c.translate(x,H-12);c.fillText(m.slice(2),0,0);c.restore();}}}});
</script>
</body></html>"""
    out = HERE / "dashboard_full2.html"
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size} bytes), modes {len(rows)}, "
          f"traces {n}, months {len(months)}")


if __name__ == "__main__":
    main()
