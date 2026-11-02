"""Build deck.pptx — TSIS 3-in-1 course presentation (16:9, 18 slides, two presenter parts).

Blueprint: DECISION.md §11 (owner decision 2026-11-02) — one deck intermingling the
findings of all three lanes, anchored on tau2-bench. Slide order follows §11.3's
18-slide two-presenter outline; Part 1 = Andrei Mihai VISALON + Antonio LIPAN,
Part 2 = Victor MURA + Natalia MOROZ. Every measured number is quoted verbatim from
its receipt (file cited in each slide's speaker notes) and never edited.

Method follows the tss course builder: asphalt/slate/amber palette, sandwich
structure (dark cover/close, light content), rounded cards + numbered chips,
Segoe UI + Consolas pairing, source line per slide, overflow-safe text sizing
(advance width ~0.5x font size per char when estimating wrap).
"""

from __future__ import annotations

import os

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "deck.pptx")

# ---------------- palette / fonts ----------------
BG_DARK = RGBColor.from_string("141821")  # asphalt near-black
CARD_DARK = RGBColor.from_string("1E2530")
LINE_DARK = RGBColor.from_string("2A3342")
BG_LIGHT = RGBColor.from_string("FFFFFF")
PRIMARY = RGBColor.from_string("2C4A63")  # engineering slate blue
PRIM_MID = RGBColor.from_string("5C7A93")
PRIM_LT = RGBColor.from_string("9CB4C4")
CARD = RGBColor.from_string("F2F5F8")  # light slate tint
ACCENT = RGBColor.from_string("F2A61D")  # road-marking amber
ACC_TINT = RGBColor.from_string("FCEFD3")
ACC_DEEP = RGBColor.from_string("9A6A00")
TEXT = RGBColor.from_string("1D2430")
MUTED = RGBColor.from_string("66727F")
GRID = RGBColor.from_string("DDE4EA")
ON_DARK = RGBColor.from_string("F2F4F7")
MUT_DARK = RGBColor.from_string("9AA6B4")
SANS = "Segoe UI"
MONO = "Consolas"

W, H, M = 13.333, 7.5, 0.55
CW = W - 2 * M  # 12.233

# presenter split (real team, TSIS / FMI Master IS 2026-2027)
COURSE = "TSIS · FMI MASTER IS 2026-2027"
TEAM = ["Andrei Mihai VISALON", "Antonio LIPAN", "Victor MURA", "Natalia MOROZ"]
PART1 = "Andrei Mihai VISALON + Antonio LIPAN"
PART2 = "Victor MURA + Natalia MOROZ"
PART_LABEL = {
    "P1": "PART 1 · VISALON + LIPAN",
    "P2": "PART 2 · MURA + MOROZ",
    "BOTH": "PART 1 + PART 2 · FULL TEAM",
}

prs = Presentation()
prs.slide_width = Inches(W)
prs.slide_height = Inches(H)
BLANK = prs.slide_layouts[6]
prs.core_properties.title = "Evaluating Agent Evaluation - TSIS 3-in-1"
prs.core_properties.author = "VISALON · LIPAN · MURA · MOROZ (TSIS, FMI Master IS 2026-2027)"


# ---------------- helpers ----------------
def slide(bg: RGBColor = BG_LIGHT):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = bg
    return s


def notes(s, text: str) -> None:
    s.notes_slide.notes_text_frame.text = text


def para(
    t: str | None = None,
    runs: list[tuple[str, dict]] | None = None,
    size: float = 14,
    bold: bool = False,
    color: RGBColor = TEXT,
    font: str = SANS,
    align=PP_ALIGN.LEFT,
    ls: float = 1.0,
    sa: float = 0,
    sb: float = 0,
):
    return dict(
        t=t,
        runs=runs,
        size=size,
        bold=bold,
        color=color,
        font=font,
        align=align,
        ls=ls,
        sa=sa,
        sb=sb,
    )


def add_text(s, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP, wrap: bool = True):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    if isinstance(paras, dict):
        paras = [paras]
    first = True
    for pa in paras:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.alignment = pa["align"]
        p.line_spacing = pa["ls"]
        if pa["sa"]:
            p.space_after = Pt(pa["sa"])
        if pa["sb"]:
            p.space_before = Pt(pa["sb"])
        runs = pa["runs"] if pa["runs"] else [(pa.get("t") or "", {})]
        for rt, ro in runs:
            r = p.add_run()
            r.text = rt
            f = r.font
            f.size = Pt(ro.get("size", pa["size"]))
            f.bold = ro.get("bold", pa["bold"])
            f.name = ro.get("font", pa["font"])
            f.color.rgb = ro.get("color", pa["color"])
    return tb


def rect(s, x, y, w, h, fill, line=None, radius=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    sp = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid()
        sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(0.75)
    sp.shadow.inherit = False
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sp.adjustments[0] = radius
        except Exception as exc:  # best-effort styling: some shapes expose no slot
            print(f"build_deck: corner radius not applied: {exc!r}")
    return sp


def chip(s, x, y, size, label, fill=ACCENT, tcolor=BG_DARK, fsize=15, font=SANS, radius=0.28):
    sp = rect(s, x, y, size, size, fill, radius=radius)
    tf = sp.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.size = Pt(fsize)
    r.font.bold = True
    r.font.name = font
    r.font.color.rgb = tcolor
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    return sp


def hairline(s, x, y, w, color=GRID):
    rect(s, x, y, w, 0.013, color, shape=MSO_SHAPE.RECTANGLE)


def header(s, kicker, title, part, page=None, source=None, tsize=27):
    add_text(s, M, 0.4, CW - 3.4, 0.28, para(kicker, size=11, bold=True, color=PRIMARY))
    add_text(s, M, 0.7, CW - 3.4, 0.75, para(title, size=tsize, bold=True, color=TEXT))
    # presenter tag on every slide (top-right badge)
    bw = 3.15
    rect(s, W - M - bw, 0.44, bw, 0.42, CARD, radius=0.22)
    add_text(
        s,
        W - M - bw,
        0.44,
        bw,
        0.42,
        para(PART_LABEL[part], size=10.5, bold=True, color=PRIMARY, align=PP_ALIGN.CENTER),
        anchor=MSO_ANCHOR.MIDDLE,
    )
    if source:
        add_text(s, M, 7.1, 9.8, 0.26, para(source, size=9.5, color=MUTED))
    if page is not None:
        add_text(
            s,
            W - M - 0.8,
            7.1,
            0.8,
            0.26,
            para(str(page), size=10, color=MUTED, align=PP_ALIGN.RIGHT),
        )


def kv_rows(
    s,
    x,
    y,
    w,
    rows,
    lead_size: float = 14.5,
    desc_size: float = 12,
    gap: float = 0.16,
    lead_color: RGBColor = PRIMARY,
):
    """Row list: bold lead-in + muted description, hairline-separated, wrap-estimated."""
    cy = y
    for i, (lead, desc) in enumerate(rows):
        add_text(s, x, cy, w, 0.3, para(lead, size=lead_size, bold=True, color=lead_color))
        cpl = max(int(w / (desc_size * 0.5 / 72)), 1)
        lines = max(1, -(-len(desc) // cpl))
        dh = lines * desc_size * 1.26 / 72
        add_text(s, x, cy + 0.31, w, dh + 0.05, para(desc, size=desc_size, color=MUTED, ls=1.12))
        cy += 0.31 + dh + gap
        if i < len(rows) - 1:
            hairline(s, x, cy - gap / 2, w)
    return cy


def set_cell(
    c,
    text,
    size: float = 12,
    bold=False,
    color: RGBColor = TEXT,
    fill: RGBColor | None = None,
    font=SANS,
    align=PP_ALIGN.LEFT,
):
    if fill is not None:
        c.fill.solid()
        c.fill.fore_color.rgb = fill
    c.margin_left = Inches(0.1)
    c.margin_right = Inches(0.06)
    c.margin_top = Inches(0.02)
    c.margin_bottom = Inches(0.02)
    c.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf = c.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.name = font
    r.font.color.rgb = color


def stat_card(s, x, y, w, h, value, label, vcolor=PRIMARY, vsize=26, lsize=10.5, fill=CARD):
    rect(s, x, y, w, h, fill, radius=0.08)
    add_text(
        s, x + 0.18, y + 0.14, w - 0.36, 0.55, para(value, size=vsize, bold=True, color=vcolor)
    )
    cpl = max(int((w - 0.36) / (lsize * 0.5 / 72)), 1)
    lines = max(1, -(-len(label) // cpl))
    lh = lines * lsize * 1.22 / 72
    add_text(
        s,
        x + 0.18,
        y + 0.14 + vsize * 1.3 / 72,
        w - 0.36,
        lh + 0.06,
        para(label, size=lsize, color=MUTED, ls=1.1),
    )


def bullet(
    s,
    x,
    y,
    w,
    text,
    size: float = 12.5,
    color: RGBColor = TEXT,
    dot: RGBColor = ACCENT,
    ls: float = 1.12,
    hh: float = 0.62,
):
    rect(s, x, y + 0.08, 0.09, 0.09, dot, radius=0.3)
    cpl = max(int((w - 0.26) / (size * 0.5 / 72)), 1)
    lines = max(1, -(-len(text) // cpl))
    h = lines * size * 1.26 * ls / 72 + 0.04
    add_text(s, x + 0.26, y - 0.02, w - 0.26, h, para(text, size=size, color=color, ls=ls))
    return h


# ================= SLIDE 1 — title (dark, P1 opens) =================
s = slide(BG_DARK)
add_text(
    s,
    M,
    0.75,
    CW,
    0.3,
    para(
        f"{COURSE} · SEMESTER PROJECT · 3-IN-1, ANCHORED ON TAU2-BENCH",
        size=12.5,
        bold=True,
        color=ACCENT,
    ),
)
add_text(
    s, M, 1.15, CW, 1.0, para("Evaluating Agent Evaluation", size=54, bold=True, color=ON_DARK)
)
add_text(
    s,
    M,
    2.25,
    CW,
    0.6,
    para(
        "Reproducing & extending tau2-bench, auditing its judge, "
        "and cross-examining two failure taxonomies",
        size=20,
        color=PRIM_LT,
    ),
)
cards = [
    (
        "The anchor",
        "tau2-bench (tau-squared, Sierra Research) - arXiv:2506.07982, MIT. "
        "Dual-control agent-user evaluation; graded deliverables stay here.",
    ),
    (
        "The instruments",
        "TRAIL (Patronus AI, arXiv:2505.08638) - 20-class error judge. "
        "MAST-14 (arXiv:2503.13657) - 14 failure modes. Supporting evidence only.",
    ),
    (
        "The evidence base",
        "5,196 gated simulations (2,344 GLM + 2,852 grok) · 148-trace controlled "
        "judge experiment · 33,889 MAST annotation targets · aggregates only.",
    ),
]
cx = M
for t, d in cards:
    rect(s, cx, 3.25, 3.94, 1.78, CARD_DARK, line=LINE_DARK, radius=0.06)
    add_text(s, cx + 0.24, 3.47, 3.46, 0.3, para(t, size=14, bold=True, color=ACCENT))
    add_text(s, cx + 0.24, 3.82, 3.46, 1.1, para(d, size=10.5, color=MUT_DARK, ls=1.16))
    cx += 4.145
rect(s, M, 5.35, CW, 0.52, CARD_DARK, line=LINE_DARK, radius=0.14)
add_text(
    s,
    M + 0.3,
    5.35,
    CW - 0.6,
    0.52,
    para(
        runs=[
            ("TEAM - ", dict(bold=True, color=ACCENT)),
            (
                "Andrei Mihai VISALON  ·  Antonio LIPAN  ·  Victor MURA  ·  Natalia MOROZ",
                dict(color=ON_DARK),
            ),
        ],
        size=14,
    ),
    anchor=MSO_ANCHOR.MIDDLE,
)
rect(s, M, 6.02, CW, 0.78, CARD_DARK, line=LINE_DARK, radius=0.1)
add_text(
    s,
    M + 0.3,
    6.02,
    CW - 0.6,
    0.78,
    para(
        runs=[
            (
                "PART 1 (opens) - Andrei Mihai VISALON + Antonio LIPAN",
                dict(bold=True, color=ON_DARK),
            ),
            ("     |     ", dict(color=LINE_DARK)),
            ("PART 2 - Victor MURA + Natalia MOROZ", dict(bold=True, color=ON_DARK)),
        ],
        size=13.5,
    ),
    anchor=MSO_ANCHOR.MIDDLE,
)
add_text(
    s,
    M,
    6.98,
    CW,
    0.28,
    para(
        "Findings F1-F8 intermingled - every non-tau2 slide maps back to a tau2 condition",
        size=11,
        color=MUT_DARK,
    ),
)
notes(
    s,
    "Sources: DECISION.md SS11 (3-in-1 blueprint, owner decision 2026-11-02) and SS1 "
    "(verdict table). Evidence counts: tau2-bench/RESULTS.md:29 (2,344 GLM sims) and "
    ":187 (2,852 grok sims); mastscope/RESULTS.md:18,85 (33,889 annotation targets). "
    "Presenter split fixed for this deck: Part 1 = Andrei Mihai VISALON + Antonio LIPAN, "
    "Part 2 = Victor MURA + Natalia MOROZ.",
)

# ================= SLIDE 2 — the dual-control problem (P1) =================
s = slide()
header(
    s,
    "MOTIVATION · WHY THIS BENCHMARK",
    "The dual-control problem",
    "P1",
    page=2,
    source="Sources: DECISION.md SS2 (council "
    "reasoning) · research-sota dossiers (all three lanes)",
)
kv_rows(
    s,
    M,
    1.8,
    7.0,
    [
        (
            "Agents and users share one state",
            "tau2-bench scores BOTH sides of the interaction: database writes by the agent "
            "AND user-side actions (pay, apply coupon) that only the simulated user can take.",
        ),
        (
            "Half the state is invisible to the scorer",
            "A run can look perfect on the agent DB while never steering the user to the "
            "user-side write - a measured failure signature on our custom domain (F2).",
        ),
        (
            "The evaluator is part of the benchmark",
            "A literal-substring CommunicateEvaluator decides pass/fail on messaging; "
            "auditing it is a first-class contribution, not a side quest (F1, F5).",
        ),
        (
            "One asset, zero private content",
            "Unlike the other two lanes, every teammate can run and demo the whole "
            "tau2-bench stack - which is why the council anchored here.",
        ),
    ],
    lead_size=15,
    desc_size=12.5,
    gap=0.2,
)
rect(s, 7.85, 1.8, 4.93, 4.75, CARD, radius=0.05)
add_text(
    s, 8.15, 2.02, 4.35, 0.3, para("The instrument landscape", size=14.5, bold=True, color=PRIMARY)
)
kv_rows(
    s,
    8.15,
    2.45,
    4.35,
    [
        (
            "tau2-bench (anchor)",
            "Sierra Research dual-control harness, 8 domains, MIT license. GO - winner "
            "of the council vote (DECISION.md SS1).",
        ),
        (
            "TRAIL (supporting)",
            "Patronus AI 20-class error taxonomy + judge over agent traces; we reuse its "
            "public 148-trace gold set.",
        ),
        (
            "MAST-14 (supporting)",
            "14 failure modes over real agent sessions; we quote published aggregates only "
            "(privacy floor, Condition 13).",
        ),
    ],
    lead_size=13,
    desc_size=11,
    gap=0.18,
    lead_color=TEXT,
)
rect(s, 8.15, 5.72, 4.35, 0.62, ACC_TINT, radius=0.12)
add_text(
    s,
    8.35,
    5.72,
    3.95,
    0.62,
    para(
        "All three instruments audit the same thing: the agent's evaluation.",
        size=11,
        bold=True,
        color=ACC_DEEP,
        ls=1.1,
    ),
    anchor=MSO_ANCHOR.MIDDLE,
)
notes(
    s,
    "Sources: DECISION.md SS1-SS2 (verdict + council reasoning; zero-private-content "
    "argument), tau2-bench/RESULTS.md:66 (dual-control signature, finding F2). "
    "Instrument landscape: per-lane research-sota.md dossiers cited in DECISION.md SS5. "
    "Presenter: Part 1 (Andrei Mihai VISALON + Antonio LIPAN).",
)

# ================= SLIDE 3 — tau2 reproduced, gated (P1) =================
s = slide()
header(
    s,
    "THE ANCHOR LANE · REPRODUCTION",
    "tau2-bench reproduced end-to-end, gated green",
    "P1",
    page=3,
    source="Source: tau2-bench/RESULTS.md SS1 (lines 16-25), "
    "SS7.1 (lines 110-119), :29, :112, :187; gates :100, :189",
)
stat_card(
    s,
    M,
    1.72,
    3.94,
    1.28,
    "2,344",
    "GLM-5.3 agent sims - harness v1.0.1, 8 domains, k=4, seed 300",
    vsize=25,
)
stat_card(
    s,
    M + 4.145,
    1.72,
    3.94,
    1.28,
    "2,852",
    "grok-4.7 agent sims - harness v2.0.0, 8 domains, k=4 (5,196 total)",
    vsize=25,
)
stat_card(
    s,
    M + 8.29,
    1.72,
    3.94,
    1.28,
    "93 + 176 PASS",
    "verify_fullrun.py gates, both exit 0, 0 FAIL - last line VERIFY OK (covers both batches)",
    vcolor=ACC_DEEP,
    vsize=20,
)
rows = [
    ("Domain", "GLM v1.0.1 pass^4", "grok v2.0.0 pass^4"),
    ("airline", "0.86", "0.60"),
    ("retail", "0.7281", "0.5789"),
    ("telecom", "0.8421", "0.5351"),
    ("banking_knowledge", "0.1649", "0.0825"),
    ("custom e-commerce", "0.5714 (ecommerce2)", "0.7857 (ecommerce3)"),
    ("intake", "- (not in v1.0.1)", "0.195"),
]
gt = s.shapes.add_table(7, 3, Inches(M), Inches(3.28), Inches(7.1), Inches(3.15)).table
gt.first_row = True
gt.horz_banding = False
for i, wd in enumerate([2.7, 2.2, 2.2]):
    gt.columns[i].width = Inches(wd)
for ri, row in enumerate(rows):
    gt.rows[ri].height = Inches(0.45)
    for ci, val in enumerate(row):
        c = gt.cell(ri, ci)
        if ri == 0:
            set_cell(c, val, size=12, bold=True, color=BG_LIGHT, fill=PRIMARY)
        else:
            hi = "e-commerce" in val
            set_cell(
                c,
                val,
                size=12,
                bold=hi or ci == 0,
                color=ACC_DEEP if hi else (PRIMARY if ci == 0 else TEXT),
                fill=ACC_TINT if hi else (BG_LIGHT if ri % 2 == 1 else CARD),
                font=MONO if ci > 0 else SANS,
                align=PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.CENTER,
            )
add_text(
    s,
    M,
    6.55,
    7.1,
    0.5,
    para(
        "pass^k = unbiased estimator C(s,k)/C(n,k), averaged over tasks (harness metric)",
        size=10,
        color=MUTED,
    ),
)
rect(s, 7.85, 3.28, 4.93, 3.15, CARD, radius=0.05)
add_text(
    s,
    8.15,
    3.5,
    4.35,
    0.3,
    para("Read the table with its confound", size=14.5, bold=True, color=ACC_DEEP),
)
yy = 3.95
_b_confound = (
    "Rows mix two harness versions (v1.0.1 vs v2.0.0) - the confound is admitted in the "
    "source file and banned by our Condition 3: one version per comparison, ever."
)
_b_custom = (
    "The custom-domain row is the team's own rule set (momentstudio-derived): ecommerce2 "
    "on v1.0.1, its v2.0.0 port ecommerce3 - grok clears every coupon/VAT family GLM "
    "dropped, 0.5714 to 0.7857."
)
for txt in [
    _b_confound,
    _b_custom,
    "Same-version cross-model rerun with bootstrap CIs lands in weeks 3-4 (WP1).",
]:
    yy += bullet(s, 8.15, yy, 4.35, txt, size=11, ls=1.14, hh=0) + 0.14
notes(
    s,
    "Source: tau2-bench/RESULTS.md - GLM headline table SS1 (lines 16-25; 2,344 sims at "
    "line 29), grok headline table SS7.1 (lines 110-119; ecommerce3 0.7857 at line 112, "
    "2,852 sims at line 121/187), gate receipts at :100 (93 PASS / 0 FAIL, v1.0.1 batch) "
    "and :189 (176 PASS / 0 FAIL, covers BOTH batches), version-confound caveat at "
    ":123-136. Presenter: Part 1.",
)

# ================= SLIDE 4 — judge validity #1: substring artifact (P2) =================
s = slide()
header(
    s,
    "JUDGE VALIDITY I · THE SUBSTRING ARTIFACT",
    "Perfect actions, failed runs - the scorer's fault",
    "P2",
    page=4,
    source="Source: tau2-bench/RESULTS.md:51-64 (GLM 13/14), :140-148 (grok 12/12) - finding F1",
)
stat_card(
    s,
    M,
    1.78,
    3.94,
    1.5,
    "13 / 14",
    "GLM-5.3 failing units that are pure COMMUNICATE-substring misses (custom domain)",
    vsize=25,
)
stat_card(
    s,
    M + 4.145,
    1.78,
    3.94,
    1.5,
    "12 / 12",
    "grok-4.7 failing units - identical taxonomy, deterministic per task",
    vsize=25,
)
stat_card(
    s,
    M + 8.29,
    1.78,
    3.94,
    1.5,
    "0 wrong writes",
    "db_match=True and zero failed action checks on every failing unit of BOTH models",
    vcolor=ACC_DEEP,
    vsize=21,
)
kv_rows(
    s,
    M,
    3.55,
    7.0,
    [
        (
            "What the scorer does",
            "v2.0.0's CommunicateEvaluator (communicate_scoring=substring, pinned in our "
            "run) compares the agent's message to the expected output as a literal "
            "substring - wording the user would happily accept still fails.",
        ),
        (
            "What we measured",
            "Both models hold a perfect action policy against the store's rules on this "
            "domain; measured pass^4 is dominated by substring luck, not rule reasoning. "
            "The cross-model delta is entirely in communicate wording.",
        ),
        (
            "What is owed before we quote it",
            "Today the finding generalizes from one self-authored domain (n=1). Condition 2: "
            "the autopsy runs on the SHIPPED airline domain - the only 50/50 "
            "[DB, COMMUNICATE] domain - before any benchmark-validity claim.",
        ),
    ],
    lead_size=14.5,
    desc_size=12,
    gap=0.2,
)
rect(s, 7.85, 3.55, 4.93, 2.9, CARD, radius=0.05)
add_text(s, 8.15, 3.77, 4.35, 0.3, para("Why it matters", size=14.5, bold=True, color=PRIMARY))
yy = 4.2
_b_semantic = (
    "Sierra shipped a semantic scorer in v2.0.0 - our A/B quantifies what that fix was worth "
    "(WP4, on the v2.0.0 flag)."
)
for txt in [
    "A benchmark that fails correct agents on phrasing measures the evaluator, not the agent.",
    _b_semantic,
    "Demo beat: this slide plus slides 6-7 run fully offline - no key needed at defense time.",
]:
    yy += bullet(s, 8.15, yy, 4.35, txt, size=11.5, ls=1.15, hh=0) + 0.15
notes(
    s,
    "Source: tau2-bench/RESULTS.md:51-64 (GLM custom-domain autopsy, 13/14 failing units) "
    "and :140-148 (grok analyze_failures3.py over 56 ecommerce3 sims: 44 pass, 12 fail, "
    "all 12 substring misses, db_match=True, zero failed action checks). Condition 2 and "
    "the airline 50/50 fact: DECISION.md SS4 and research-sota.md SS1.4 (line 62). "
    "Presenter: Part 2 (Victor MURA + Natalia MOROZ).",
)

# ================= SLIDE 5 — TRAIL as an instrument (P2) =================
s = slide()
header(
    s,
    "SUPPORTING LANE · TRAIL",
    "TRAIL as an instrument: low agreement, loud noise floor",
    "P2",
    page=5,
    source="Sources: trail/RESULTS.md SS1 (lines 31-37) "
    "· DECISION.md SS10.1 (cross-model agreement)",
)
stat_card(
    s,
    M,
    1.78,
    3.0,
    1.45,
    "148",
    "public gold traces: 117 GAIA + 31 SWE - the benchmark half anyone can touch",
    vsize=30,
)
stat_card(
    s,
    M + 3.2,
    1.78,
    3.0,
    1.45,
    "0.0905",
    "union-148 joint accuracy of the paper-style flat judge (glm-5.3 / nemotron mix)",
    vsize=30,
)
stat_card(
    s,
    M + 6.4,
    1.78,
    3.0,
    1.45,
    "2.1x",
    "annotator noise floor: single-model location acc "
    "0.4419 (glm-5.3, n=33) vs 0.2064 (nemotron, n=147)",
    vcolor=ACC_DEEP,
    vsize=30,
)
stat_card(
    s,
    M + 9.6,
    1.78,
    2.63,
    1.45,
    "0.4517",
    "mean Jaccard, glm vs grok full-overlap labels (n=206 same-hash pairs)",
    vsize=22,
)
kv_rows(
    s,
    M,
    3.5,
    7.0,
    [
        (
            "Gold agreement is the ceiling, not the floor",
            "weighted F1 0.3683, location acc 0.2472, joint acc 0.0905 across the 148 "
            "released traces - judging agent failures is genuinely hard, even for "
            "frontier models.",
        ),
        (
            "Single-annotator labels are evidence, not truth",
            "Same-task location accuracy differs 2.1x between frontier annotators, and "
            "several cross-model kappa values are negative - which is why our semester "
            "plan adds a 2-annotator human audit (Condition 5).",
        ),
        (
            "How we use it",
            "The public gold set is our judge-validity testbed (slides 6-8): a controlled "
            "chunked-judge experiment on the same 148 traces. The private corpus half is "
            "quoted as published aggregates only.",
        ),
    ],
    lead_size=14.5,
    desc_size=12,
    gap=0.2,
)
rect(s, 7.85, 3.5, 4.93, 2.95, CARD, radius=0.05)
add_text(s, 8.15, 3.72, 4.35, 0.3, para("TRAIL in one line", size=14.5, bold=True, color=PRIMARY))
add_text(
    s,
    8.15,
    4.12,
    4.35,
    1.0,
    para(
        "A 20-class error taxonomy + LLM judge for agent traces (Patronus AI, "
        "arXiv:2505.08638). Fallback lane for the course - gated public-repo leg only.",
        size=11.5,
        color=TEXT,
        ls=1.18,
    ),
)
hairline(s, 8.15, 5.28, 4.35)
yy = 5.45
for txt in [
    "Fell back honestly: its corpus half is private journals (no teammate access).",
    "Every TRAIL number tonight is either the public gold set or a published aggregate.",
]:
    yy += bullet(s, 8.15, yy, 4.35, txt, size=11, ls=1.12, hh=0) + 0.13
notes(
    s,
    "Source: trail/RESULTS.md SS1 (lines 31-37): union-148 weighted F1 0.3683 / location "
    "0.2472 / joint 0.0905; single-model glm-5.3 (n=33) 0.3953/0.4419/0.1251 and "
    "nemotron-ultra (n=147) 0.3537/0.2064/0.0709. Cross-model Jaccard 0.4517 / exact-set "
    "0.2573 (n=206): DECISION.md SS10.1, receipts in INTEGRITY.md SS5b. Negative kappas: "
    "trail/RESULTS.md:129-131. Presenter: Part 2.",
)

# ================= SLIDE 6 — judge validity #2: controlled (P1) =================
s = slide()
header(
    s,
    "JUDGE VALIDITY II · CHUNKED JUDGING, CONTROLLED",
    "~93% of the lift is the model; location is the architecture",
    "P1",
    page=6,
    source="Source: trail/fullrun_hierarchical_judge.md "
    "SS2-SS3 (table lines 81-83; effects lines 103-104, 125)",
)
rows = [
    ("Judge configuration", "Model", "wF1", "Location", "Joint"),
    ("Flat (paper artifact)", "glm-5.3 / nemotron mix", "0.3683", "0.2472", "0.0905"),
    ("Flat control - paper prompt + flat capping", "grok-4.7 xhigh", "0.4920", "0.3858", "0.2065"),
    ("Hierarchical - windows, votes, reconcile", "grok-4.7 xhigh", "0.4489", "0.5406", "0.2190"),
]
gt = s.shapes.add_table(4, 5, Inches(M), Inches(1.85), Inches(CW), Inches(1.95)).table
gt.first_row = True
gt.horz_banding = False
for i, wd in enumerate([4.63, 3.0, 1.53, 1.53, 1.53]):
    gt.columns[i].width = Inches(wd)
for ri, row in enumerate(rows):
    gt.rows[ri].height = Inches(0.48)
    for ci, val in enumerate(row):
        c = gt.cell(ri, ci)
        if ri == 0:
            set_cell(
                c,
                val,
                size=12.5,
                bold=True,
                color=BG_LIGHT,
                fill=PRIMARY,
                align=PP_ALIGN.LEFT if ci < 2 else PP_ALIGN.CENTER,
            )
        else:
            is_hier = ri == 3
            set_cell(
                c,
                val,
                size=12.5,
                bold=(ci == 0 or ci == 4),
                color=ACC_DEEP if is_hier and ci in (3, 4) else TEXT,
                fill=ACC_TINT if is_hier else (BG_LIGHT if ri % 2 == 1 else CARD),
                align=PP_ALIGN.LEFT if ci < 2 else PP_ALIGN.CENTER,
            )
stat_card(
    s,
    M,
    4.05,
    3.94,
    1.35,
    "0.0905 - 0.2190",
    "headline joint-accuracy lift over the paper flat artifact (148-trace gold set)",
    vsize=19,
)
stat_card(
    s,
    M + 4.145,
    4.05,
    3.94,
    1.35,
    "~93% model",
    "the same-model flat control already scores 0.2065 of the 0.2190 "
    "endpoint; the architecture's residual is +0.0125 (Wilcoxon p=0.80, n=148)",
    vcolor=ACC_DEEP,
    vsize=19,
)
stat_card(
    s,
    M + 8.29,
    4.05,
    3.94,
    1.35,
    "+0.155 location",
    "0.3858 to 0.5406, +40% relative - significant, Wilcoxon p=1.1e-08 (better on 65 / worse on 9)",
    vsize=19,
)
rect(s, M, 5.62, CW, 0.95, ACC_TINT, radius=0.1)
add_text(
    s,
    M + 0.3,
    5.62,
    CW - 0.6,
    0.95,
    para(
        runs=[
            ("House rule (Condition 11): ", dict(bold=True, color=ACC_DEEP)),
            (
                "this table is never quoted without its same-model control adjacent. "
                "The chunking claim is about WHERE the error is - not that it fixes "
                "category agreement.",
                dict(),
            ),
        ],
        size=13,
        ls=1.15,
    ),
    anchor=MSO_ANCHOR.MIDDLE,
)
notes(
    s,
    "Source: trail/fullrun_hierarchical_judge.md - three-row table at lines 81-83 "
    "(wF1 / location / joint: 0.3683/0.2472/0.0905, 0.4920/0.3858/0.2065, "
    "0.4489/0.5406/0.2190), effects at lines 103-104 (location +0.1547, p=1.1e-08, "
    "65/9; joint +0.0125, p=0.80, 40/25) and line 125 (~93% model effect). Public gold "
    "set: repo/benchmarking/data/{GAIA,SWE Bench}. Condition 11: DECISION.md SS4. "
    "Presenter: Part 1.",
)

# ================= SLIDE 7 — why location improves (P1) =================
s = slide()
header(
    s,
    "JUDGE VALIDITY II · MECHANISM",
    "Windows, votes, reconcile - and why errors land in the right span",
    "P1",
    page=7,
    source="Source: trail/fullrun_hierarchical_judge.md SS2-SS3 (design + lines 90, 130-137)",
)
boxes = [
    ("Trace", "one agent trace, up to megabytes - flat judging caps it at a 160K-token budget"),
    ("Windows", "chunk into units; window payloads keep near-full unit text (12K/unit cap)"),
    ("Votes", "each window votes on error class + span id, constrained to spans it actually saw"),
    ("Reconcile", "merge votes across windows; drop only 13% of candidates"),
]
bx, by, bw, bh, gap = M, 1.85, 2.78, 1.62, 0.37
for i, (t, d) in enumerate(boxes):
    last = i == len(boxes) - 1
    rect(s, bx, by, bw, bh, ACCENT if last else CARD, radius=0.09)
    add_text(
        s,
        bx + 0.18,
        by + 0.18,
        bw - 0.36,
        0.32,
        para(t, size=15, bold=True, color=BG_DARK if last else PRIMARY),
    )
    add_text(
        s,
        bx + 0.18,
        by + 0.56,
        bw - 0.36,
        0.98,
        para(d, size=10.5, color=RGBColor.from_string("3A2E10") if last else MUTED, ls=1.14),
    )
    if not last:
        rect(
            s,
            bx + bw + 0.03,
            by + bh / 2 - 0.13,
            gap - 0.06,
            0.26,
            PRIM_LT,
            shape=MSO_SHAPE.RIGHT_ARROW,
        )
    bx += bw + gap
stat_card(
    s,
    M,
    3.75,
    3.94,
    1.32,
    "0.3858 - 0.5406",
    "location accuracy, flat control vs hierarchical (same model, same 148 traces)",
    vsize=19,
)
stat_card(
    s,
    M + 4.145,
    3.75,
    3.94,
    1.32,
    "SWE: 0.0000 - 0.0308",
    "the only configuration with non-zero SWE joint accuracy; SWE "
    "traces are the largest (median 1.58 MB) and die worst under flat capping",
    vcolor=ACC_DEEP,
    vsize=17,
)
stat_card(
    s,
    M + 8.29,
    3.75,
    3.94,
    1.32,
    "p = 1.1e-08",
    "Wilcoxon on the location effect - better on 65 traces, worse on 9",
    vsize=20,
)
rect(s, M, 5.32, CW, 1.3, CARD, radius=0.06)
add_text(
    s,
    M + 0.3,
    5.5,
    CW - 0.6,
    0.3,
    para("The mechanism, in one sentence", size=14, bold=True, color=PRIMARY),
)
add_text(
    s,
    M + 0.3,
    5.86,
    CW - 0.6,
    0.68,
    para(
        "Every window error is mechanically constrained to a span id actually shown in "
        "that window, and windows carry near-full unit text instead of a truncated "
        "budget - so the judge points at the right place in the trace even when it "
        "argues about the class label.",
        size=12.5,
        color=TEXT,
        ls=1.18,
    ),
)
notes(
    s,
    "Source: trail/fullrun_hierarchical_judge.md - design SS2 (windows -> votes -> "
    "reconcile; 12K/unit cap vs 160K flat budget), SWE split at line 90 (0.3057/0.0086/"
    "0.0000 vs 0.3888/0.0998/0.0000 vs 0.4018/0.1743/0.0308; SWE median 1.58 MB), "
    "effects at lines 130-137 (+0.155 location, p=1.1e-08, 65/9; span-id constraint). "
    "Reconciliation drop rate 13%: same file SS3. Presenter: Part 1.",
)

# ================= SLIDE 8 — the price (P2) =================
s = slide()
header(
    s,
    "JUDGE VALIDITY II · THE PRICE",
    "Chunked judging costs precision and tokens",
    "P2",
    page=8,
    source="Source: trail/fullrun_hierarchical_judge.md SS3 (findings 3-4; effects lines 103-107)",
)
stat_card(
    s,
    M,
    1.8,
    3.94,
    1.5,
    "0.4920 - 0.4489",
    "weighted F1, flat control vs hierarchical - chunking trades category precision for location",
    vsize=20,
)
stat_card(
    s,
    M + 4.145,
    1.8,
    3.94,
    1.5,
    "7.08 vs 5.68",
    "predicted errors per trace vs gold - systematic over-prediction (FP-heavy in "
    "Tool Output Misinterpretation 73 / Language-only 68 / Instruction Non-compliance 55)",
    vcolor=ACC_DEEP,
    vsize=20,
)
stat_card(
    s,
    M + 8.29,
    1.8,
    3.94,
    1.5,
    "1.62x tokens",
    "68.7K vs 42.5K tokens/trace, and 2.93 calls/trace vs 1 - the architecture is not free",
    vsize=20,
)
kv_rows(
    s,
    M,
    3.55,
    7.0,
    [
        (
            "Macro-F1 still rises",
            "0.297 to 0.391 - rare classes benefit from dedicated windows even as "
            "frequent classes over-fire.",
        ),
        (
            "When chunking is worth it",
            "When you need WHERE the failure is (debugging, triage, span-level feedback) "
            "and can afford the tokens; flat judging remains the cheaper instrument for "
            "aggregate class rates.",
        ),
        (
            "How we ship it",
            "Package the figures with the control adjacent (Condition 11) and reproduce "
            "the flat control on the public gold set over a $0 model-substituted path "
            "(WP5, ~2.0 pw).",
        ),
    ],
    lead_size=14.5,
    desc_size=12,
    gap=0.2,
)
rect(s, 7.85, 3.55, 4.93, 2.9, CARD, radius=0.05)
add_text(
    s, 8.15, 3.77, 4.35, 0.3, para("The one-line summary", size=14.5, bold=True, color=PRIMARY)
)
add_text(
    s,
    8.15,
    4.2,
    4.35,
    2.0,
    para(
        '"Chunked judging fixes LOCATION, not category agreement; ~93% of the joint '
        'gain is the model" - finding F5, quotable only with the control attached. '
        "That discipline is why the deck shows all three rows on slide 6, always.",
        size=12.5,
        color=TEXT,
        ls=1.2,
    ),
)
notes(
    s,
    "Source: trail/fullrun_hierarchical_judge.md SS3 - wF1 0.4920 -> 0.4489, predicted "
    "7.08 vs 5.68 errors/trace, FP profile (TOM 73 / Language-only 68 / INC 55), "
    "reconciliation drops only 13%, 1.62x tokens (68.7K vs 42.5K), macro-F1 0.297 -> "
    "0.391; effects table lines 103-107. F5 status + Condition 11: DECISION.md SS10.3, "
    "SS4. Presenter: Part 2.",
)

# ================= SLIDE 9 — contributions preview (P2) =================
s = slide()
header(
    s,
    "THE SEMESTER'S BUILD · PREVIEW",
    "Two measured gaps, two contributions that close them",
    "P2",
    page=9,
    source="Sources: DECISION.md SS3-SS4 (plan + conditions) · tau2-bench/RESULTS.md:66 (F2)",
)
cards = [
    (
        "Gap 1 - novelty (measured)",
        "The inherited estate is 14 hand-written custom tasks derived from our own "
        "momentstudio codebase - the council ruled they do not clear the novelty bar "
        "as a semester contribution.",
        "Contribution I - the generator",
        "Compositional {f_init, f_sol, f_assert} coupon/VAT/returns task generator with "
        "automatic solvability verification; at least 100 generated tasks passing the "
        "harness's full validation (Condition 1).",
    ),
    (
        "Gap 2 - dual-control (measured)",
        "On ecommerce_poc the agent NEVER steers the user to the user-side write - the "
        "signature failure of single-control e-commerce domains (F2, RESULTS.md:66).",
        "Contribution II - shopper-app tools",
        "User-side tools (apply coupon in cart, pay VAT difference, scan receipt, open "
        "return portal) + user_db mirroring customer-visible state - true dual control "
        "(weeks 7-8).",
    ),
]
cx = M
for g_title, g_desc, c_title, c_desc in cards:
    rect(s, cx, 1.85, 5.98, 2.15, CARD, radius=0.05)
    add_text(s, cx + 0.3, 2.07, 5.38, 0.3, para(g_title, size=14.5, bold=True, color=ACC_DEEP))
    add_text(s, cx + 0.3, 2.45, 5.38, 1.4, para(g_desc, size=12, color=TEXT, ls=1.2))
    rect(s, cx + 0.6, 4.15, 0.34, 0.34, PRIM_LT, shape=MSO_SHAPE.DOWN_ARROW)
    rect(s, cx, 4.62, 5.98, 1.75, ACC_TINT, radius=0.05)
    add_text(s, cx + 0.3, 4.82, 5.38, 0.3, para(c_title, size=14.5, bold=True, color=ACC_DEEP))
    add_text(s, cx + 0.3, 5.2, 5.38, 1.05, para(c_desc, size=11.5, color=TEXT, ls=1.18))
    cx += 6.25
notes(
    s,
    "Sources: DECISION.md SS2 (novelty-critic adjudication -> Condition 1), SS3 weeks "
    "5-8 (generator + shopper-app tools), tau2-bench/RESULTS.md:66 (dual-control "
    "signature failure on ecommerce_poc, finding F2), provenance SS6 (momentstudio "
    "derivation disclosure). Presenter: Part 2.",
)

# ================= SLIDE 10 — generator design (P1) =================
s = slide()
header(
    s,
    "CONTRIBUTION I · GENERATOR DESIGN",
    "Three functions, one verifier, at least 100 validated tasks",
    "P1",
    page=10,
    source="Sources: DECISION.md SS3 weeks 5-6 + Condition 1 · telecom "
    "manager.py:197 pattern · RESULTS.md:41 (32-check precedent)",
)
trio = [
    (
        "f_init",
        "compose the initial world: cart, catalog, VAT regime, coupon "
        "wallet - rule interactions sampled from the momentstudio-derived set",
    ),
    (
        "f_sol",
        "the reference solution: an executable plan that reaches the "
        "goal (apply coupon, place-of-supply rules, cross-border thresholds)",
    ),
    (
        "f_assert",
        "machine-checkable outcome: expected DB state, "
        "expected user-side side effects, expected communication",
    ),
]
cx = M
for t, d in trio:
    rect(s, cx, 1.85, 3.94, 1.85, CARD, radius=0.06)
    add_text(s, cx + 0.24, 2.07, 3.46, 0.35, para(t, size=17, bold=True, color=PRIMARY, font=MONO))
    add_text(s, cx + 0.24, 2.52, 3.46, 1.05, para(d, size=11, color=MUTED, ls=1.16))
    cx += 4.145
rect(s, M, 3.95, 7.1, 2.5, CARD, radius=0.05)
add_text(
    s,
    M + 0.3,
    4.15,
    6.5,
    0.3,
    para("Automatic solvability verification", size=14.5, bold=True, color=PRIMARY),
)
yy = 4.55
_b_solvable = (
    "Every generated task must pass broken-before / fixed-after / no-prefix-fix checks "
    "(the harness's own pattern at telecom manager.py:197) before it enters the set."
)
_b_fullcheck = (
    "Then the full harness validation - the 32-check precedent already proven on the "
    "inherited custom domain - gates the >= 100-task deliverable."
)
_b_datebug = (
    "Fixes an authoring bug we inherited: the current-date anchor (RESULTS.md:62) is "
    "pinned by generated fixtures."
)
for txt in [
    _b_solvable,
    _b_fullcheck,
    _b_datebug,
]:
    yy += bullet(s, M + 0.3, yy, 6.5, txt, size=12, ls=1.15, hh=0) + 0.16
rect(s, 7.85, 3.95, 4.93, 2.5, ACC_TINT, radius=0.05)
add_text(
    s, 8.15, 4.15, 4.35, 0.3, para("Why coupon/VAT/returns", size=14.5, bold=True, color=ACC_DEEP)
)
add_text(
    s,
    8.15,
    4.55,
    4.35,
    1.7,
    para(
        "grep-verified: the shipped retail policy and tools contain zero matches for "
        "coupon / VAT / tax - the interactions (stacking exclusivity, reverse charge, "
        "cross-border thresholds) are genuinely uncovered rule space, and composition "
        "gives difficulty calibration for free (#subtasks).",
        size=11.5,
        color=TEXT,
        ls=1.2,
    ),
)
notes(
    s,
    "Sources: DECISION.md SS3 weeks 5-6 and Condition 1 ({f_init, f_sol, f_assert} + "
    "solvability verification + >=100 tasks past full validation), pattern reference "
    "src/tau2/domains/telecom/tasks/manager.py:197, 32-check precedent at "
    "tau2-bench/RESULTS.md:41, current-date anchor bug at RESULTS.md:62, coupon/VAT "
    "grep verification at research-sota.md:172. Presenter: Part 1.",
)

# ================= SLIDE 11 — cross-examination I: the join (P1) =================
s = slide()
header(
    s,
    "CROSS-EXAMINATION I · MAST x TRAIL",
    "Same failing sessions, private catchments",
    "P1",
    page=11,
    source="Sources: corpus/CROSS_TAXONOMY.md:69-86 "
    "(join), :174 (associations) · HARNESS_INSIGHTS.md SS4",
)
stat_card(
    s,
    M,
    1.8,
    3.0,
    1.5,
    "60.3%",
    "both-flagged: 519 of 861 enriched sessions carry >=1 MAST mode AND >=1 TRAIL class",
    vcolor=ACC_DEEP,
    vsize=30,
)
stat_card(
    s,
    M + 3.2,
    1.8,
    3.0,
    1.5,
    "kappa 0.333",
    "Cohen's kappa between the two instruments on session-level flag/no-flag",
    vsize=24,
)
stat_card(
    s,
    M + 6.4,
    1.8,
    3.0,
    1.5,
    "1.5x",
    "Resource Abuse association with looping runtimes (OR 8.69, lift 3.21)",
    vsize=30,
)
stat_card(
    s,
    M + 9.6,
    1.8,
    2.63,
    1.5,
    "N=861",
    "enriched join sample - aggregates only, n<5 suppressed (Condition 13)",
    vsize=26,
)
rect(s, M, 3.5, 5.98, 2.95, CARD, radius=0.05)
add_text(s, M + 0.3, 3.72, 5.38, 0.3, para("The 2x2, in full", size=14.5, bold=True, color=PRIMARY))
rows = [
    ("", "TRAIL flagged", "TRAIL clean"),
    ("MAST flagged", "519 (60.3%)", "157 (18.2%)"),
    ("MAST clean", "70 (8.1%)", "115 (13.4%)"),
]
gt = s.shapes.add_table(3, 3, Inches(M + 0.3), Inches(4.15), Inches(5.38), Inches(1.5)).table
gt.first_row = True
gt.horz_banding = False
for i, wd in enumerate([1.98, 1.7, 1.7]):
    gt.columns[i].width = Inches(wd)
for ri, row in enumerate(rows):
    gt.rows[ri].height = Inches(0.5)
    for ci, val in enumerate(row):
        c = gt.cell(ri, ci)
        if ri == 0 or ci == 0:
            set_cell(
                c,
                val,
                size=11.5,
                bold=True,
                color=BG_LIGHT if ri == 0 else PRIMARY,
                fill=PRIMARY if ri == 0 else CARD,
                align=PP_ALIGN.CENTER,
            )
        else:
            hi = ri == 1 and ci == 1
            set_cell(
                c,
                val,
                size=12,
                bold=hi,
                color=ACC_DEEP if hi else TEXT,
                fill=ACC_TINT if hi else BG_LIGHT,
                align=PP_ALIGN.CENTER,
            )
add_text(
    s,
    M + 0.3,
    5.85,
    5.38,
    0.5,
    para("per-session severity correlates (Spearman rho = 0.376)", size=10.5, color=MUTED),
)
rect(s, 6.8, 3.5, 5.98, 2.95, CARD, radius=0.05)
add_text(
    s,
    7.1,
    3.72,
    5.38,
    0.3,
    para("Two instruments, two monopolies", size=14.5, bold=True, color=PRIMARY),
)
yy = 4.15
_b_infra = (
    "TRAIL monopolizes infrastructure classes (provider failures, resource exhaustion) - "
    "MAST's modes do not model them."
)
_b_process = (
    "MAST monopolizes process pathology (step repetition, premature termination) - "
    "TRAIL's classes under-represent loops."
)
_b_rankings = (
    "So neither taxonomy subsumes the other; quoting rankings (not rates) is the honest "
    "cross-examination (Condition 12)."
)
for txt in [
    _b_infra,
    _b_process,
    _b_rankings,
]:
    yy += bullet(s, 7.1, yy, 5.38, txt, size=12, ls=1.15, hh=0) + 0.15
notes(
    s,
    "Sources: corpus/CROSS_TAXONOMY.md:69-86 (2x2 join: both-flagged 519 (60.3%), "
    "MAST-only 157 (18.2%), TRAIL-only 70 (8.1%), both-clean 115 (13.4%); kappa 0.333; "
    "Spearman 0.376) and :174-177 (1.5x Resource Abuse, OR 8.69, lift 3.21; 1.5x "
    "Context Handling / Goal Deviation / Task Orchestration; 2.2x Instruction "
    "Non-compliance), restated in HARNESS_INSIGHTS.md SS4 and trail/RESULTS.md. "
    "Aggregates-only floor: DECISION.md Condition 13. Presenter: Part 1.",
)

# ================= SLIDE 12 — cross-examination II: fleet profile (P2) =================
s = slide()
header(
    s,
    "CROSS-EXAMINATION II · THE FLEET'S PROFILE",
    "One failure surface across 33,889 annotated sessions",
    "P2",
    page=12,
    source="Sources: HARNESS_INSIGHTS.md SS2-SS3, SS5 "
    "(R1-R5) · mastscope/RESULTS.md:18, :85 (33,889)",
)
stat_card(
    s, M, 1.8, 2.87, 1.42, "33,889", "MAST annotation targets (whole corpus, gated)", vsize=25
)
stat_card(
    s,
    M + 3.07,
    1.8,
    2.87,
    1.42,
    "65.2%",
    "of MAST-ok sessions carry >=1 of the 14 failure modes (mean 2.45)",
    vsize=25,
)
stat_card(
    s,
    M + 6.14,
    1.8,
    2.87,
    1.42,
    "79.5%",
    "of TRAIL-ok sessions carry >=1 error class (mean 2.22 labels)",
    vsize=25,
)
stat_card(
    s,
    M + 9.21,
    1.8,
    2.02,
    1.42,
    "34.5%",
    "task_completed=yes - two-thirds of real sessions do not land the task",
    vcolor=ACC_DEEP,
    vsize=25,
)
rect(s, M, 3.42, 5.98, 3.0, CARD, radius=0.05)
add_text(
    s, M + 0.3, 3.62, 5.38, 0.3, para("Two failure regimes", size=14.5, bold=True, color=PRIMARY)
)
yy = 4.02
_b_interactive = (
    "Interactive Claude lane: 71% completion at the fleet's lowest error density "
    "(1.91 labels/session)."
)
_b_loopregime = (
    "Vault / rollout / automation lanes: 0-42% completion with Step Repetition at "
    "72.6-91.7% - the loop regime."
)
_b_rootcause = (
    "Root cause shares: Reasoning 58.5% vs System Execution 23.0% of TRAIL labels; "
    "HIGH impact 38.9%."
)
for txt in [
    _b_interactive,
    _b_loopregime,
    _b_rootcause,
]:
    yy += bullet(s, M + 0.3, yy, 5.38, txt, size=12, ls=1.15, hh=0) + 0.16
rect(s, 6.8, 3.42, 5.98, 3.0, CARD, radius=0.05)
add_text(
    s,
    7.1,
    3.62,
    5.38,
    0.3,
    para("Top-5 ranked recommendations (R1-R5)", size=14.5, bold=True, color=PRIMARY),
)
recs = [
    ("R1", "repetition / loop circuit breaker - highest volume, every runtime"),
    ("R2", "explicit termination conditions; infra failures non-fatal"),
    ("R3", "gate 'done' behind an executed verification step"),
    ("R4", "fix tool-result consumption (TRAIL's #1 real-traffic class)"),
    ("R5", "clarify-first on under-specified tasks - biggest attached family"),
]
yy = 4.02
for tag, txt in recs:
    chip(s, 7.1, yy, 0.34, tag, fsize=11, radius=0.24)
    add_text(
        s, 7.56, yy - 0.01, 5.0, 0.34, para(txt, size=11.5, color=TEXT), anchor=MSO_ANCHOR.MIDDLE
    )
    yy += 0.47
notes(
    s,
    "Sources: HARNESS_INSIGHTS.md SS2-SS3 (65.2% / mean 2.45; 79.5% / mean 2.22; "
    "34.5% completion; two regimes 71% @ 1.91 labels/session vs 0-42% @ 72.6-91.7% "
    "Step Repetition; Reasoning 58.5% / System Execution 23.0%; HIGH impact 38.9%), "
    "SS5 lines 145-192 (R1-R5). Corpus base: mastscope/RESULTS.md:18 and :85 (33,889 "
    "annotation targets). Privacy: aggregates only, n<5 suppressed (HARNESS_INSIGHTS.md "
    "SS7 / Condition 13). Presenter: Part 2.",
)

# ================= SLIDE 13 — instrument honesty (P2) =================
s = slide()
header(
    s,
    "INSTRUMENT HONESTY",
    "Rankings, not rates - and gates that reject their own judge",
    "P2",
    page=13,
    source="Sources: trail/fullrun/sensitivity.md:161-163 · "
    "mastscope/RESULTS.md:335-336 · DECISION.md SS9, Condition 12",
)
rect(s, M, 1.85, 5.98, 2.3, CARD, radius=0.05)
add_text(
    s,
    M + 0.3,
    2.07,
    5.38,
    0.35,
    para('"STILL UNSTABLE AT FULL N"', size=16, bold=True, color=ACC_DEEP, font=MONO),
)
add_text(
    s,
    M + 0.3,
    2.55,
    5.38,
    1.45,
    para(
        "The corpus-wide TRAIL class-share verdict at full N: 5/5 top-5 class shares and "
        "3/3 impact shares fall OUTSIDE the bootstrap 95% CI of the previous snapshot "
        "(L1 distance 0.4898 vs 0.0861). Per-class rates are directional; the RANKING "
        "of top classes is the robust part.",
        size=12,
        color=TEXT,
        ls=1.2,
    ),
)
rect(s, 6.8, 1.85, 5.98, 2.3, CARD, radius=0.05)
add_text(
    s, 7.1, 2.07, 5.38, 0.35, para("A gate that rejected itself", size=16, bold=True, color=PRIMARY)
)
add_text(
    s,
    7.1,
    2.55,
    5.38,
    1.45,
    para(
        "AdaMAST head-to-head (520-session stratified sample): agreement kappa 0.315 vs "
        "the kappa >= 0.75 bar -> review_required. The comparison is reported as "
        "SELF-REJECTED - a negative result we keep, not hide. Taxonomy overlap with "
        "MAST-14: Jaccard 0.150 (their published 0.14).",
        size=12,
        color=TEXT,
        ls=1.2,
    ),
)
kv_rows(
    s,
    M,
    4.4,
    CW,
    [
        (
            "Why we report confidence intervals",
            "Every pass^k tonight is a point estimate from ONE sweep (seed 300, k=4); no "
            "cross-model delta becomes a model-ranking claim until the same-version "
            "rerun lands with bootstrap CIs (Condition 3) and the discrimination pilot "
            "(Condition 4).",
        ),
        (
            "The discipline, stated on the slide",
            "Rankings over rates (Condition 12); control adjacent (Condition 11); "
            "aggregates only with n<5 suppressed (Condition 13); no cell with n<5 may "
            "anchor a claim (SS9 small-cell scan: 142 table cells flagged).",
        ),
    ],
    lead_size=14.5,
    desc_size=12,
    gap=0.22,
)
notes(
    s,
    "Sources: trail/fullrun/sensitivity.md:161-163 ('VERDICT AT FULL N': 5/5 + 3/3 "
    "outside CI, L1(C,D)=0.4898 vs L1(B,C)=0.0861), restated in trail/RESULTS.md and "
    "README.md:13 (Condition 12). AdaMAST: mastscope/RESULTS.md SS9 (lines 329-338): "
    "kappa 0.315 / coverage 0.969 -> review_required; Jaccard 0.150 vs published 0.14. "
    "Small-cell scan + CI policy: DECISION.md SS9. Presenter: Part 2.",
)

# ================= SLIDE 14 — discrimination pilot design (P1) =================
s = slide()
header(
    s,
    "EVALUATION DESIGN · CONDITION 4",
    "The discrimination pilot: benchmarks must separate models",
    "P1",
    page=14,
    source="Sources: DECISION.md Condition 4, SS3 weeks 9-10, SS9 (statistical rigor)",
)
design = [
    (">= 2", "frontier-tier agent models - same pinned harness version for both (Condition 3)"),
    ("3", "seeds per model - pass^1 AND pass^4 reported with bootstrap CIs"),
    (
        "5,196",
        "on-disk k=4 sims (2,344 GLM + 2,852 grok) sizing "
        "the power analysis - no new sweeps needed to plan",
    ),
]
cx = M
for v, d in design:
    rect(s, cx, 1.85, 3.94, 1.9, CARD, radius=0.06)
    add_text(s, cx + 0.24, 2.1, 3.46, 0.6, para(v, size=30, bold=True, color=PRIMARY))
    add_text(s, cx + 0.24, 2.78, 3.46, 0.85, para(d, size=11.5, color=MUTED, ls=1.16))
    cx += 4.145
kv_rows(
    s,
    M,
    4.0,
    7.0,
    [
        (
            "Why a pilot first",
            "Prior-session airline/retail pass^1 of 0.87-0.89 says current models may "
            "already saturate the shipped domains (CRAB-Bench's charge). No benchmark "
            "claim is quotable until discrimination is shown.",
        ),
        (
            "The honest fallback",
            "If the new domain still saturates, we fall back to the benchmark-validity "
            "study (substring-vs-semantic A/B + airline autopsy) - never a reskin claim.",
        ),
        (
            "The human leg",
            "2-annotator user-simulator audit on the new domain (target no worse than "
            "telecom's 16%/6% critical), ~110-120 min/trace divided across all four "
            "members - the project's first human-validated label (Condition 5).",
        ),
    ],
    lead_size=14,
    desc_size=11.5,
    gap=0.18,
)
rect(s, 7.85, 4.0, 4.93, 2.5, ACC_TINT, radius=0.05)
add_text(
    s, 8.15, 4.2, 4.35, 0.3, para("Multiplicity discipline", size=14, bold=True, color=ACC_DEEP)
)
add_text(
    s,
    8.15,
    4.6,
    4.35,
    1.7,
    para(
        "Any new wave of per-domain significance tests states a correction - the "
        "cross-taxonomy engine already applies Benjamini-Hochberg FDR in CI (29-test "
        "suite). Per-domain pass^k comparisons without correction stay descriptive.",
        size=12,
        color=TEXT,
        ls=1.2,
    ),
)
notes(
    s,
    "Source: DECISION.md - Condition 4 (>=2 frontier models x 3 seeds x pass^1/pass^4 "
    "+ CIs + power analysis from on-disk k=4 data), Condition 5 (2-annotator audit, "
    "telecom 16%/6% target), Condition 3 (one version per comparison), SS3 weeks 9-10, "
    "SS9 (saturation 0.87-0.89; BH-FDR in corpus/cross_taxonomy_join.py, 29-test CI "
    "suite). Presenter: Part 1.",
)

# ================= SLIDE 15 — demo (P1) =================
s = slide()
header(
    s,
    "LIVE DEMO · CONDITION 10",
    "Demo insurance: live first, offline always",
    "P1",
    page=15,
    source="Sources: DECISION.md SS8, SS11.4 · tau2-bench SMOKE.md:159 (gold-replay 10/10)",
)
rect(s, M, 1.85, 5.98, 2.0, ACC_TINT, radius=0.06)
add_text(
    s,
    M + 0.3,
    2.07,
    5.38,
    0.3,
    para("Primary - live tau2 play", size=14.5, bold=True, color=ACC_DEEP),
)
add_text(
    s,
    M + 0.3,
    2.45,
    5.38,
    1.25,
    para(
        "A live dual-control run on the custom ecommerce3 domain (the 0.7857 pass^4 "
        "domain), pre-flighted with --dry-run plus one live probe <= 10 min before the "
        "slot - on the proven $0 free-tier path.",
        size=12.5,
        color=TEXT,
        ls=1.2,
    ),
)
rect(s, M, 4.05, 5.98, 2.4, CARD, radius=0.06)
add_text(
    s,
    M + 0.3,
    4.25,
    5.38,
    0.3,
    para("Always-offline second beat", size=14.5, bold=True, color=PRIMARY),
)
add_text(
    s,
    M + 0.3,
    4.65,
    5.38,
    1.6,
    para(
        "The judge-anatomy walk (slides 4 -> 7): one ecommerce3 trace where the DB is "
        "right and the substring scorer misses, plus the controlled three-row judge "
        "table. Zero keys, survives any outage.",
        size=12.5,
        color=TEXT,
        ls=1.2,
    ),
)
layers = [
    ("L1", "offline gold-replay - the recorded gold interaction, 10/10 PASS exit 0, zero keys"),
    ("L2", "recorded fallback - full demo video + terminal transcript, inventoried in the repo"),
    ("L3", "static artifacts - printed RESULTS tables, VERIFY OK gate receipts, pass^k slides"),
]
yy = 1.85
for tag, txt in layers:
    rect(s, 6.8, yy, 5.98, 1.38, CARD, radius=0.06)
    chip(s, 7.1, yy + 0.42, 0.52, tag, fsize=14, radius=0.26)
    add_text(
        s,
        7.82,
        yy + 0.2,
        4.7,
        1.0,
        para(txt, size=12.5, color=TEXT, ls=1.18),
        anchor=MSO_ANCHOR.MIDDLE,
    )
    yy += 1.51
rect(s, 6.8, 6.4, 5.98, 0.5, ACC_TINT, radius=0.14)
add_text(
    s,
    7.0,
    6.4,
    5.58,
    0.5,
    para(
        "Every layer rehearsed once in weeks 11-13; the live demo runs only if the probe passes.",
        size=11,
        bold=True,
        color=ACC_DEEP,
        ls=1.1,
    ),
    anchor=MSO_ANCHOR.MIDDLE,
)
notes(
    s,
    "Sources: DECISION.md SS8 (layered fallback table + rules), SS11.4 (demo plan "
    "incl. the offline judge-anatomy beat), Condition 10; gold-replay receipt "
    "tau2-bench/SMOKE.md:159 (10/10 PASS, exit 0). ecommerce3 0.7857: "
    "tau2-bench/RESULTS.md:112. Presenter: Part 1.",
)

# ================= SLIDE 16 — budget & provenance (P2) =================
s = slide()
header(
    s,
    "BUDGET & PROVENANCE · CONDITIONS 6-7",
    "A proven $0 path, priced honestly against the paper protocol",
    "P2",
    page=16,
    source="Sources: DECISION.md Conditions 6-7, SS5.4, SS6 (provenance table) · AI_USAGE.md",
)
rect(s, M, 1.85, 5.98, 2.2, CARD, radius=0.05)
add_text(
    s, M + 0.3, 2.05, 5.38, 0.3, para("The two cost paths", size=14.5, bold=True, color=PRIMARY)
)
rows = [
    ("Path", "Cost", "Scope"),
    ("$0 free-tier (proven)", "$0", "already carried the full 8-domain x k=4 GLM sweep"),
    ("Paper-protocol pilot", "~$300-400", "gpt-4.1 rates, >=2 frontier models x 3 seeds"),
]
gt = s.shapes.add_table(3, 3, Inches(M + 0.3), Inches(2.45), Inches(5.38), Inches(1.4)).table
gt.first_row = True
gt.horz_banding = False
for i, wd in enumerate([2.1, 1.1, 2.18]):
    gt.columns[i].width = Inches(wd)
for ri, row in enumerate(rows):
    gt.rows[ri].height = Inches(0.46)
    for ci, val in enumerate(row):
        c = gt.cell(ri, ci)
        if ri == 0:
            set_cell(
                c,
                val,
                size=11.5,
                bold=True,
                color=BG_LIGHT,
                fill=PRIMARY,
                align=PP_ALIGN.CENTER if ci == 1 else PP_ALIGN.LEFT,
            )
        else:
            set_cell(
                c,
                val,
                size=11,
                bold=ci <= 1,
                color=ACC_DEEP if (ri == 2 and ci == 1) else TEXT,
                fill=ACC_TINT if (ri == 2 and ci == 1) else (BG_LIGHT if ri % 2 == 1 else CARD),
                align=PP_ALIGN.CENTER if ci == 1 else PP_ALIGN.LEFT,
            )
add_text(
    s,
    M + 0.3,
    3.95,
    5.38,
    0.3,
    para(
        "budget ownership in USD by funding instrument and named payer (HUMAN-REQUIRED)",
        size=10,
        color=MUTED,
    ),
)
rect(s, 6.8, 1.85, 5.98, 2.2, CARD, radius=0.05)
add_text(s, 7.1, 2.05, 5.38, 0.3, para("Framing discipline", size=14.5, bold=True, color=PRIMARY))
yy = 2.45
_b_nokey = (
    "No funded frontier key exists today (all five provider keys failed auth probes) - "
    "so every reproduction claim stays MODEL-SUBSTITUTED until one appears."
)
_b_dryrun = (
    "Every judge / user-sim call is priced with --dry-run before committing (the "
    "flat-control path measured 42.5K tokens/trace)."
)
_b_pricemap = (
    "Litellm has no price map for glm-5.3 / grok-4.7 on our endpoints: cost is not "
    "persisted, tokens are measured and reported instead."
)
for txt in [
    _b_nokey,
    _b_dryrun,
    _b_pricemap,
]:
    yy += bullet(s, 7.1, yy, 5.38, txt, size=11.5, ls=1.15, hh=0) + 0.13
rect(s, M, 4.25, CW, 2.2, CARD, radius=0.05)
add_text(
    s,
    M + 0.3,
    4.45,
    CW - 0.6,
    0.3,
    para("Provenance pack - exists before week 3", size=14.5, bold=True, color=PRIMARY),
)
yy = 4.85
_b_aiusage = (
    "AI_USAGE.md per the lab standard: full AI-involvement inventory for every asset "
    "(harness runs, dossiers, this deck)."
)
_b_disclose = (
    "Disclosure: custom e-commerce VAT/coupon rules derive from the team's own "
    "momentstudio codebase - inherited estate, scoped TEAM-new vs inherited for the "
    "professor (Condition 7)."
)
_b_scrub = (
    "Hygiene: the 35 lane files embedding the OS username are scrubbed before any repo "
    "sharing, and the verify gate re-runs GREEN at submission - no stale artifacts "
    "(Condition 9)."
)
for txt in [
    _b_aiusage,
    _b_disclose,
    _b_scrub,
]:
    yy += bullet(s, M + 0.3, yy, CW - 0.6, txt, size=12, ls=1.15, hh=0) + 0.14
notes(
    s,
    "Sources: DECISION.md Condition 6 ($300-400 paper-protocol pilot vs proven $0 "
    "path; USD by funding instrument and named payer; --dry-run pricing), Condition 7 "
    "(provenance pack / AI_USAGE.md / momentstudio disclosure / not-presented-elsewhere "
    "check), Condition 9 (35 username files: grep -rlI receipt in SS4.9), SS5.4 "
    "($0 path carried the sweep), SS1 blockers (all five provider keys failed auth), "
    "tau2-bench/RESULTS.md:86,174 (no price map; tokens measured). Presenter: Part 2.",
)

# ================= SLIDE 17 — limitations & risks (P2) =================
s = slide()
header(
    s,
    "LIMITATIONS & RISKS",
    "What could sink this - and the mitigation on record",
    "P2",
    page=17,
    source="Sources: DECISION.md SS5.1 (threats), SS9 "
    "(rigor), SS11.5 (risk table), Conditions 3/4/13",
)
rows = [
    ("Risk", "Exposure", "Mitigation on record"),
    (
        "Saturation - shipped domains may not separate models",
        "high",
        "Condition 4 pilot first; honest fallback to the validity study, never a reskin claim",
    ),
    (
        "Misquoting the judge result",
        "high",
        "Condition 11: same-model control adjacent on "
        "the slide itself (slide 6 shows all three rows)",
    ),
    (
        "Private-content spill via taxonomy slides",
        "high",
        "Condition 13: aggregates only, n<5 suppressed, no MASTscope derived artifacts",
    ),
    (
        "Unstable class rates challenged at defense",
        "medium",
        "Condition 12: show rankings + the instability receipt (slide 13), not bare rates",
    ),
    (
        "Version confound re-entering a cross-model table",
        "medium",
        "Condition 3: one harness version per comparison; confound slide explicit (slide 3)",
    ),
    (
        "Schedule: ~55.0 pw of 56 nominal (4 students)",
        "medium",
        "Demote WP5/WP6 to appendix first (-4.5 pw); then SS7 descope candidates with sign-off",
    ),
    (
        "Demo key / provider failure",
        "low",
        "L1-L3 layers + the offline judge-anatomy beat (slide 15)",
    ),
]
gt = s.shapes.add_table(8, 3, Inches(M), Inches(1.85), Inches(CW), Inches(4.6)).table
gt.first_row = True
gt.horz_banding = False
for i, wd in enumerate([4.63, 1.53, 6.07]):
    gt.columns[i].width = Inches(wd)
for ri, row in enumerate(rows):
    gt.rows[ri].height = Inches(0.56)
    for ci, val in enumerate(row):
        c = gt.cell(ri, ci)
        if ri == 0:
            set_cell(
                c,
                val,
                size=12.5,
                bold=True,
                color=BG_LIGHT,
                fill=PRIMARY,
                align=PP_ALIGN.CENTER if ci == 1 else PP_ALIGN.LEFT,
            )
        else:
            hot = val == "high"
            set_cell(
                c,
                val,
                size=11.5,
                bold=(ci == 1),
                color=ACC_DEEP if (ci == 1 and hot) else TEXT,
                fill=ACC_TINT if (ci == 1 and hot) else (BG_LIGHT if ri % 2 == 1 else CARD),
                align=PP_ALIGN.CENTER if ci == 1 else PP_ALIGN.LEFT,
            )
add_text(
    s,
    M,
    6.62,
    CW,
    0.3,
    para(
        "Every mitigation is a numbered condition in DECISION.md SS4 - the plan and the "
        "deck share one spine.",
        size=11.5,
        color=MUTED,
    ),
)
notes(
    s,
    "Sources: DECISION.md SS11.5 risk table (verbatim exposures), SS5.1 (CRAB-Bench "
    "saturation charge, prior-session pass^1 0.87-0.89), SS9 (rigor), SS11.2 (55.0 pw "
    "vs 56 nominal; WP5/WP6 demotion -4.5 pw), Conditions 3/4/11/12/13. "
    "Presenter: Part 2.",
)

# ================= SLIDE 18 — close (dark, both parts) =================
s = slide(BG_DARK)
bw = 3.15
rect(s, W - M - bw, 0.55, bw, 0.42, CARD_DARK, line=LINE_DARK, radius=0.22)
add_text(
    s,
    W - M - bw,
    0.55,
    bw,
    0.42,
    para(PART_LABEL["BOTH"], size=10.5, bold=True, color=ACCENT, align=PP_ALIGN.CENTER),
    anchor=MSO_ANCHOR.MIDDLE,
)
add_text(s, M, 0.6, CW - 3.4, 0.3, para("CLOSE", size=12, bold=True, color=ACCENT))
add_text(
    s, M, 1.0, CW, 0.7, para("The evaluation-of-evaluation arc", size=34, bold=True, color=ON_DARK)
)
rect(s, M, 1.95, 5.98, 2.5, CARD_DARK, line=LINE_DARK, radius=0.06)
add_text(
    s,
    M + 0.3,
    2.17,
    5.38,
    0.3,
    para("What we already know (gated on disk)", size=14.5, bold=True, color=ACCENT),
)
yy = 2.58
for txt in [
    "F1 - substring evaluator artifact, two models, DB correct",
    "F4 - judge agreement is low and annotator-dependent",
    "F5 - chunking fixes location (+0.155, p=1.1e-08), not category",
    "F6 - corpus class shares STILL UNSTABLE AT FULL N",
    "F7/F8 - two taxonomies, same sessions, private catchments",
]:
    yy += (
        bullet(s, M + 0.3, yy, 5.38, txt, size=11.5, color=ON_DARK, dot=ACCENT, ls=1.1, hh=0) + 0.11
    )
rect(s, 6.8, 1.95, 5.98, 2.5, CARD_DARK, line=LINE_DARK, radius=0.06)
add_text(
    s, 7.1, 2.17, 5.38, 0.3, para("What we build this semester", size=14.5, bold=True, color=ACCENT)
)
yy = 2.58
for txt in [
    "WP1 - pinned harness, same-version rerun, gates",
    "WP2 - compositional generator, >= 100 validated tasks",
    "WP3 - dual-control shopper-app domain + demo layers",
    "WP4 - pilot + CIs + power analysis + judge A/B + audit",
    "WP5/WP6 - judge-validity + taxonomy packaging (demotable)",
]:
    yy += bullet(s, 7.1, yy, 5.38, txt, size=11.5, color=ON_DARK, dot=ACCENT, ls=1.1, hh=0) + 0.11
rect(s, M, 4.75, CW, 1.0, CARD_DARK, line=LINE_DARK, radius=0.08)
add_text(
    s,
    M + 0.3,
    4.75,
    CW - 0.6,
    1.0,
    para(
        runs=[
            (
                "Reproduce the benchmark - audit its judge two ways - cross-examine two "
                "failure taxonomies. ",
                dict(bold=True, color=ON_DARK),
            ),
            (
                "Graded deliverables stay tau2-anchored (Conditions 1-10); TRAIL/MAST ride "
                "as gated supporting evidence (11-13). Upstream errata filed as #635.",
                dict(color=MUT_DARK),
            ),
        ],
        size=13.5,
        ls=1.2,
    ),
    anchor=MSO_ANCHOR.MIDDLE,
)
add_text(s, M, 6.05, CW, 0.6, para("Thank you - questions?", size=28, bold=True, color=ON_DARK))
add_text(
    s,
    M,
    6.9,
    CW,
    0.3,
    para(
        f"{COURSE} · Team: Andrei Mihai VISALON · Antonio LIPAN · Victor MURA · Natalia MOROZ",
        size=11.5,
        color=MUT_DARK,
    ),
)
notes(
    s,
    "Sources: DECISION.md SS11.3 (outline), SS10.3 (F1-F8 status table), SS11.2 "
    "(WP1-WP6), SS11.6 (recommendation), SS6 provenance table (upstream errata #635). "
    "Presenters: Part 1 + Part 2 (full team).",
)

prs.save(OUT)
print(f"saved {OUT} slides: {len(prs.slides)}")
