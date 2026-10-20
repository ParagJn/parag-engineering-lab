"""Executive deck: a 5-7 slide PowerPoint built from a dashboard, in the dashboard's own look.

Two steps, same contract as the story and the executive summary:
  1. plan  - the model defines ONE central takeaway, then picks the evidence slides (headline that states
             the point, supporting points, which panel to show), the decisions and the missing evidence.
             Every sentence goes through the number guard; without a model the plan is assembled from the
             dashboard's computed story.
  2. build - python-pptx draws the slides. Charts are native (editable in PowerPoint) and come straight
             from the panel data; the model never types a figure onto a slide.
Missing evidence is flagged on the last slide instead of being papered over.
"""

import hashlib
import io
import json
import math
import re
import time
from contextvars import ContextVar
from dataclasses import dataclass

from pptx import Presentation
from pptx.chart.data import CategoryChartData, XyChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION, XL_MARKER_STYLE, XL_TICK_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

import brief
from fmt import MONTHS, compact, fmt_period, fmt_value, is_num, to_date
from insights import fact_sheet
from llm import ProviderError
from story import PRINCIPLES, _agent, allowed_numbers, guard, llm_ready

# --- palettes and designs -----------------------------------------------------------------------
# A deck is a design (slide structure, fonts, corner style) in a palette (colours only), so the two are
# picked independently. "studio" is the dashboard's own colours (frontend/src/charts/theme.ts + index.css).
# Fonts are limited to ones PowerPoint ships with.


@dataclass(frozen=True)
class Palette:
    id: str
    name: str
    blurb: str
    # content slides
    page: str
    surface: str
    hair: str
    line: str
    ink: str
    ink2: str
    muted: str
    accent: str
    accent_soft: str  # tint behind the "so what" box
    accent_deep: str  # text on accent_soft
    on_accent: str  # text on solid accent
    bar_soft: str  # unselected bars
    negative: str
    series: tuple
    ramp: tuple  # heatmap, low -> high
    ramp_word: str  # how the legend describes "high"
    # title and closing slides
    dark: str
    dark_card: str
    dark_ink: str
    dark_text: str
    accent_light: str  # accent on dark
    deco1: str
    deco2: str
    other: str = "C3C2B7"


@dataclass(frozen=True)
class Design:
    id: str
    name: str
    blurb: str
    font_head: str
    font_body: str
    radius: float | None  # corner radius of cards in inches; None = square


PALETTES: dict[str, Palette] = {p.id: p for p in (
    Palette("studio", "Studio", "The dashboard's own blue",
            page="F4F3EF", surface="FDFDFC", hair="E1E0D9", line="C3C2B7", ink="0B0B0B", ink2="52514E", muted="898781",
            accent="2A78D6", accent_soft="E6F0FC", accent_deep="184F95", on_accent="FFFFFF", bar_soft="9EC5F4", negative="EB6834",
            series=("2A78D6", "EB6834", "1BAF7A", "EDA100", "E87BA4", "008300", "6250D6", "E34948"),
            ramp=("E6F0FC", "CDE2FB", "9EC5F4", "6DA7EC", "3987E5", "256ABF", "184F95", "0D366B"), ramp_word="Darker",
            dark="0B0B0B", dark_card="1C1C1B", dark_ink="FFFFFF", dark_text="B8B7AE", accent_light="9EC5F4",
            deco1="184F95", deco2="2A78D6"),
    Palette("boardroom", "Boardroom", "Navy and gold",
            page="FFFFFF", surface="F5F7FB", hair="DDE2EE", line="B8C0D4", ink="111827", ink2="4B5563", muted="7B8497",
            accent="1E2761", accent_soft="E8EBF7", accent_deep="1E2761", on_accent="FFFFFF", bar_soft="AEB7DD", negative="B91C1C",
            series=("1E2761", "D4A017", "2F8F9D", "9B2C2C", "6B7BB8", "3F7D4E", "8B5CF6", "7C7C7C"),
            ramp=("EEF0FA", "D5DAF0", "B3BCE3", "8E9BD2", "6676BC", "45559F", "2C3A80", "1E2761"), ramp_word="Darker",
            dark="1E2761", dark_card="2A3578", dark_ink="FFFFFF", dark_text="B8C0E6", accent_light="F2C94C",
            deco1="2A3578", deco2="D4A017"),
    Palette("midnight", "Midnight", "Dark, electric cyan",
            page="0F172A", surface="1E293B", hair="334155", line="475569", ink="F1F5F9", ink2="CBD5E1", muted="94A3B8",
            accent="38BDF8", accent_soft="12364D", accent_deep="7DD3FC", on_accent="0F172A", bar_soft="475569", negative="FB923C",
            series=("38BDF8", "FB923C", "34D399", "FACC15", "F472B6", "A78BFA", "2DD4BF", "F87171"),
            ramp=("172A45", "1E3A5F", "1D4F7F", "1F6AA5", "2A8AC9", "38A8E8", "6CC3F2", "A5DBF8"), ramp_word="Brighter",
            dark="020617", dark_card="0F172A", dark_ink="FFFFFF", dark_text="94A3B8", accent_light="7DD3FC",
            deco1="0C4A6E", deco2="0EA5E9", other="64748B"),
    Palette("evergreen", "Evergreen", "Fresh greens on sage",
            page="F3F6F3", surface="FFFFFF", hair="DCE4DC", line="B7C4B8", ink="14231A", ink2="4A5A4E", muted="7D8C80",
            accent="2C6B3A", accent_soft="E3F0E5", accent_deep="1B4527", on_accent="FFFFFF", bar_soft="A9CDB0", negative="D9622B",
            series=("2C6B3A", "E07B39", "3F8FB0", "D9A81E", "8E6BBF", "97BC62", "C2476B", "6B7A70"),
            ramp=("EAF3EB", "D2E7D5", "B2D5B8", "8CC096", "63A874", "3F8A52", "2C6B3A", "1B4527"), ramp_word="Darker",
            dark="12271A", dark_card="1C3A28", dark_ink="FFFFFF", dark_text="A9C2AF", accent_light="97BC62",
            deco1="1B4527", deco2="2C6B3A"),
)}

DESIGNS: dict[str, Design] = {d.id: d for d in (
    Design("classic", "Classic", "Rounded cards, chart left and commentary right", "Calibri", "Calibri", 0.12),
    Design("editorial", "Editorial", "Flat and airy, serif headlines, big numbers", "Cambria", "Calibri", None),
    Design("split", "Split", "Colour panel with the message, chart beside it", "Arial", "Arial", 0.08),
    Design("focus", "Focus", "Wide chart on top, takeaways in a row below", "Calibri", "Calibri", None),
)}
DEFAULT_PALETTE, DEFAULT_DESIGN = "studio", "classic"

_palette: ContextVar[Palette] = ContextVar("deck_palette", default=PALETTES[DEFAULT_PALETTE])
_design: ContextVar[Design] = ContextVar("deck_design", default=DESIGNS[DEFAULT_DESIGN])
_logo: ContextVar[bytes | None] = ContextVar("deck_logo", default=None)


class _Active:
    """T.ink, T.font_head, T.radius ... read the palette/design of the deck being built (set in build_pptx)."""

    def __getattr__(self, name):
        for src in (_palette.get(), _design.get()):
            if hasattr(src, name):
                return getattr(src, name)
        raise AttributeError(name)


T = _Active()

_PREVIEW_COLORS = ("dark", "dark_ink", "dark_text", "accent_light", "deco1", "deco2", "page", "surface", "hair", "ink", "muted",
                   "accent", "accent_soft", "bar_soft")


def deck_options() -> dict:
    """What the picker shows: designs (name, font) and palettes (name, the colours a miniature needs)."""
    return {
        "default_design": DEFAULT_DESIGN, "default_palette": DEFAULT_PALETTE,
        "designs": [{"id": d.id, "name": d.name, "blurb": d.blurb, "font": d.font_head} for d in DESIGNS.values()],
        "palettes": [{"id": p.id, "name": p.name, "blurb": p.blurb, "colors": {k: getattr(p, k) for k in _PREVIEW_COLORS}}
                     for p in PALETTES.values()],
    }


def _luma(h: str) -> float:
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


W, H = 13.333, 7.5
MX = 0.6  # side margin
MAX_EVIDENCE = 3
PLAN_VERSION = 2  # bump when the prompt or plan shape changes so cached plans are rebuilt
SKIP_CHARTS = {"kpi", "table"}


def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


# ================================================================== plan


def _signature(dash: dict) -> str:
    key = json.dumps({"v": PLAN_VERSION, "story": {k: dash["story"].get(k) for k in ("headline", "kpis", "sections", "insights", "next_steps")},
                      "panels": sorted(dash["panels"]), "t": [p.get("title") for p in dash["panels"].values()]},
                     sort_keys=True, default=str)
    return hashlib.sha1(key.encode()).hexdigest()[:12]


async def deck_plan(dash: dict, regenerate: bool = False) -> dict:
    """The slide plan for a dashboard; cached on it and rebuilt when the story or panels change."""
    sig = _signature(dash)
    cached = dash.get("deck_plan")
    if cached and cached.get("sig") == sig and not regenerate:
        return cached
    panels = brief._ordered_panels(dash)
    drawable = {p["id"] for p in panels if p["chart"] not in SKIP_CHARTS}
    plan = _fallback_plan(dash, drawable)
    plan["source"] = "computed"
    if llm_ready():
        try:
            plan.update(await _write_plan(dash, panels, drawable))
            plan["source"] = "ai"
        except (ProviderError, ValueError) as err:
            print(f"[deck] plan failed, using computed: {err}", flush=True)
            plan["notice"] = f"AI commentary unavailable ({err}); the deck uses the dashboard's computed findings."
    plan["gaps"] = _merge_gaps(plan.get("gaps") or [], _computed_gaps(dash))
    plan["sig"] = sig
    plan["generated"] = time.time()
    dash["deck_plan"] = plan
    return plan


async def _write_plan(dash: dict, panels: list[dict], drawable: set[str]) -> dict:
    story, meta = dash["story"], dash["meta"]
    facts = fact_sheet(panels)
    narrative = brief._story_text(story)
    audience = meta.get("audience") or "senior executives"
    prompt = f"""DATASET: {meta['scope_label']} — {meta['rows']} records
{('PERIOD: ' + brief._period(meta)) if meta.get('time') else ''}
{('USER GOAL: ' + meta['goal']) if meta.get('goal') else ''}
AUDIENCE: {audience}
{'NOTE: the dataset is small; keep claims modest.' if dash.get('low_confidence') else ''}

FACTS (computed from the data; ids in brackets):
{facts}

DASHBOARD NARRATIVE ALREADY WRITTEN (figures in it are verified):
{narrative}

Create a 5 to 7 slide executive presentation for {audience}, who need to understand this data better to make decisions.
{('The question to answer: ' + meta['goal']) if meta.get('goal') else 'The question to answer: what changed, what it means, and what to do about it.'}
By the end they must clearly understand the decision points and be able to decide what benefits the organisation.

HOW TO BUILD IT
1. First define the central takeaway in one sentence, then build the slide sequence around it: every slide must earn
   its place by moving the audience toward that takeaway and the decisions.
2. Cover these four things across the deck, in this order: (a) the MAIN CHANGE or headline finding, (b) the most
   relevant COMPARISON (against a prior period, a peer group, the average or a benchmark in FACTS), (c) the
   EXCEPTIONS: the segments, periods or items that break the pattern, (d) the IMPLICATIONS, which become the decisions.
   Tag each evidence slide with the one it covers ("change", "comparison" or "exception").
3. Each evidence slide: a takeaway headline that states the point (a full-sentence insight, never a topic label),
   the one panel that shows it best, and a brief interpretation. Plot only what the chosen panel already holds;
   never ask for or type a figure that is not in FACTS.
4. Keep OBSERVATIONS and EXPLANATIONS apart. Observations are what the data shows, with figures copied exactly as
   written in FACTS. The possible explanation is a separate, hedged hypothesis ("may", "could point to"), and it must
   not claim or imply causation from correlation or co-movement. Wording like "caused", "drove", "led to" or "because
   of" is not allowed unless FACTS states the mechanism.
5. Close with recommended actions (the decisions, verb-led, each tied to evidence) and concrete next steps.
   Data limitations are NOT a slide: list them in "evidence_gaps" and they go to the speaker notes only. Never invent
   evidence; say what the data does not contain that a decision would need, based on what the columns and facts cover.
7. Every evidence slide MUST carry commentary: exactly 2 observations, a possible_explanation when FACTS gives any
   basis for one, and a so_what. A slide with a chart and one line is not acceptable.
6. Plain business English; no chart talk, no panel ids in the text. Copy every figure exactly as written in FACTS.

Return ONLY JSON:
{{
  "central_takeaway": "ONE sentence, max 28 words, the message the audience must leave with",
  "glance_headline": "slide-2 headline, max 16 words: where things stand, stated as a point",
  "slides": [{{"panel": "id of the most convincing panel to show for this point (never a kpi or table)",
               "lens": "change | comparison | exception",
               "headline": "max 18 words, the takeaway, states the point",
               "observations": ["2 statements of what the data shows, each max 22 words, with figures from FACTS"],
               "possible_explanation": "max 24 words, a hedged hypothesis for why, or empty if FACTS gives no basis",
               "so_what": "one sentence, max 24 words: the implication for the decision"}}],
  "decisions": [{{"decision": "verb-led, max 18 words, something this group can actually decide",
                  "why": "max 30 words: the evidence behind it, with a figure from FACTS",
                  "panel": "optional supporting panel id"}}],
  "evidence_gaps": ["0-4 data limitations: specific things missing that would sharpen or change a decision"],
  "next_steps": ["2-3 concrete steps, verb-led, that would close those gaps or start acting"]
}}
Give 2-3 evidence slides (different panels, ordered change, comparison, exception where the data supports them) and 2-4 decisions."""
    out = await _agent().complete_json(PRINCIPLES, prompt, 5000)
    ok = allowed_numbers(facts, narrative, meta["rows"])
    dropped: list[str] = []

    def g(text) -> str:
        t, d = guard(str(text or ""), ok)
        dropped.extend(d)
        return t.strip()

    res: dict = {}
    for key, field in (("takeaway", "central_takeaway"), ("glance_headline", "glance_headline")):
        t = g(out.get(field))
        if t:
            res[key] = t
    slides, seen = [], set()
    for s in out.get("slides") or []:
        if not isinstance(s, dict) or s.get("panel") not in drawable or s["panel"] in seen:
            continue
        head = g(s.get("headline"))
        if not head:
            continue
        seen.add(s["panel"])
        obs = s.get("observations") or s.get("points") or []
        points = [x for x in (g(p) for p in obs[:2]) if x]
        why = g(s.get("possible_explanation"))
        if why:
            points.append("Possible explanation: " + why)
        slides.append({"panel": s["panel"], "headline": head, "points": points[:3], "so_what": g(s.get("so_what"))})
    if slides:
        res["slides"] = _enrich(slides[:MAX_EVIDENCE], dash)
    decisions = []
    for d in out.get("decisions") or []:
        if isinstance(d, dict) and g(d.get("decision")):
            decisions.append({"decision": g(d.get("decision")), "why": g(d.get("why")),
                              "panel": d.get("panel") if d.get("panel") in drawable else None})
    if decisions:
        res["decisions"] = decisions[:4]
    gaps = [x for x in (g(x) for x in out.get("evidence_gaps") or []) if x]
    if gaps:
        res["gaps"] = gaps[:4]
    steps = [x for x in (g(x) for x in out.get("next_steps") or []) if x]
    if steps:
        res["next_steps"] = steps[:3]
    if dropped:
        res["guarded"] = dropped
        print(f"[deck] number guard dropped {len(dropped)} sentence(s): {dropped}", flush=True)
    return res


def _enrich(slides: list[dict], dash: dict) -> list[dict]:
    """Make sure no evidence slide is a bare chart: top up thin commentary from the dashboard's own verified insights."""
    story = dash["story"]
    for sl in slides:
        mine = [i for i in story.get("insights") or [] if sl["panel"] in (i.get("panels") or [])]
        sec = next((x for x in story.get("sections") or [] if sl["panel"] in x.get("panels", [])), None)
        pts = list(sl.get("points") or [])
        for i in mine:
            for t in (i.get("what"), i.get("significance")):
                if t and len(pts) < 2 and t not in pts:
                    pts.append(t)
        if len(pts) < 2 and sec and sec.get("note") and sec["note"] not in pts:
            pts.append(sec["note"])
        sl["points"] = pts[:3]
        if not sl.get("so_what"):
            sl["so_what"] = next((i.get("next") or i.get("why") for i in mine if i.get("next") or i.get("why")), "")
    return slides


def _fallback_plan(dash: dict, drawable: set[str]) -> dict:
    """No model: the dashboard's own story, arranged as a deck."""
    story, panels = dash["story"], dash["panels"]
    hl = story["headline"]
    takeaway = hl.get("finding") or (re.split(r"(?<=[.!?])\s+", hl.get("summary", "").strip())[0] if hl.get("summary") else "") \
        or hl.get("title", "")
    slides, seen = [], set()
    for sec in story["sections"]:
        pid = next((p for p in sec["panels"] if p in drawable and p not in seen), None)
        if not pid:
            continue
        seen.add(pid)
        p = panels[pid]
        pts = [sec["note"]] if sec.get("note") else ([p["subtitle"]] if p.get("subtitle") else [])
        slides.append({"panel": pid, "headline": sec.get("heading") or p["title"], "points": pts[:3], "so_what": ""})
        if len(slides) >= MAX_EVIDENCE:
            break
    slides = _enrich(slides, dash)
    decisions = []
    for ins in story.get("insights") or []:
        if ins.get("next"):
            decisions.append({"decision": ins["next"], "why": ins.get("what", ""), "panel": None})
    if not decisions:
        decisions = [{"decision": s, "why": "", "panel": None} for s in story.get("next_steps") or []]
    return {"takeaway": takeaway, "glance_headline": hl.get("finding") or hl.get("title", ""), "slides": slides,
            "decisions": decisions[:4], "gaps": [], "next_steps": list(story.get("next_steps") or [])[:3]}


def _computed_gaps(dash: dict) -> list[str]:
    """Limits we can state from the data's own shape, so the deck never implies more than it knows."""
    meta, gaps = dash["meta"], []
    if dash.get("low_confidence"):
        gaps.append(f"The dataset is small ({compact(meta['rows'])} records), so findings are indicative rather than conclusive.")
    if not meta.get("time"):
        gaps.append("There is no date field, so change over time can't be shown.")
    names = " ".join(f"{c.get('name', '')} {c.get('label', '')}" for c in meta.get("columns") or []).lower()
    if not re.search(r"cost|budget|target|margin|profit|spend|forecast|goal", names):
        gaps.append("The data has no cost, margin or target figures, so the financial impact of each decision isn't quantified.")
    gaps.append("The data shows association, not cause; the reasons offered are hypotheses to confirm.")
    for n in dash["story"].get("anomaly_notes") or []:
        gaps.append(n)
    return gaps


def _merge_gaps(ai: list[str], computed: list[str]) -> list[str]:
    out = list(ai)
    for g in computed:
        if len(out) >= 5:
            break
        if not any(g[:30].lower() in x.lower() for x in out):
            out.append(g)
    return out[:5]


# ================================================================== text helpers


def _words(text: str, n: int) -> str:
    """Hard cap so a long sentence can't overflow its box; cuts at a word and closes with an ellipsis."""
    ws = (text or "").split()
    return text.strip() if len(ws) <= n else " ".join(ws[:n]).rstrip(",;:") + "…"


def _short_period(v, grain: str) -> str:
    d = to_date(v)
    if d is None:
        return str(v)
    if grain == "month":
        return f"{MONTHS[d.month - 1]} {str(d.year)[2:]}"
    if grain in ("day", "hour", "week"):
        return f"{d.day} {MONTHS[d.month - 1]}"
    return fmt_period(v, grain)


# ================================================================== drawing primitives


def _fill(shape, hex_: str | None):
    if hex_ is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb(hex_)


def _box(slide, x, y, w, h, fill=None, line=None, radius: float | None = None, shape=None):
    kind = shape or (MSO_SHAPE.ROUNDED_RECTANGLE if radius is not None else MSO_SHAPE.RECTANGLE)
    s = slide.shapes.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
    _fill(s, fill)
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(0.75)
    else:
        s.line.fill.background()
    if radius is not None and kind == MSO_SHAPE.ROUNDED_RECTANGLE:
        s.adjustments[0] = min(0.5, radius / min(w, h))
    s.shadow.inherit = False
    return s


def _text(slide, x, y, w, h, paras, anchor=MSO_ANCHOR.TOP):
    """paras: list of dicts {t, size, bold, color, bullet, after, align, italic} (or runs: [{t, bold, color}])."""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.alignment = p.get("align", PP_ALIGN.LEFT)
        para.space_after = Pt(p.get("after", 0))
        para.line_spacing = p.get("spacing", 1.0)
        runs = p.get("runs") or [{"t": p["t"]}]
        for r in runs:
            run = para.add_run()
            run.text = r["t"]
            f = run.font
            f.name = T.font_head if p.get("head") else T.font_body
            f.size = Pt(r.get("size", p.get("size", 14)))
            f.bold = r.get("bold", p.get("bold", False))
            f.italic = p.get("italic", False)
            f.color.rgb = rgb(r.get("color", p.get("color", T.ink)))
        if p.get("spc"):
            for run in para.runs:
                run._r.get_or_add_rPr().set("spc", str(p["spc"]))
        if p.get("bullet"):
            pPr = para._p.get_or_add_pPr()
            pPr.set("marL", str(Inches(0.2)))
            pPr.set("indent", str(-Inches(0.2)))
            clr = pPr.makeelement(qn("a:buClr"), {})
            clr.append(clr.makeelement(qn("a:srgbClr"), {"val": p.get("bullet_color", T.accent)}))
            pPr.append(clr)
            pPr.append(pPr.makeelement(qn("a:buFont"), {"typeface": "Arial"}))
            pPr.append(pPr.makeelement(qn("a:buChar"), {"char": "•"}))
    return tb


def _bg(slide, hex_: str):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = rgb(hex_)


def _new(prs, bg: str):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(s, bg)
    return s


def _logo_box(slide, x: float, y: float, max_w: float, max_h: float, dark: bool, align: str = "left") -> float:
    """Draw the company logo inside max_w x max_h, keeping its proportions; on dark slides it sits on a white chip
    so any logo stays readable. Returns the width used (0 if there is no logo)."""
    data = _logo.get()
    if not data:
        return 0.0
    try:
        from PIL import Image
        iw, ih = Image.open(io.BytesIO(data)).size
    except Exception:
        return 0.0
    pad = 0.08 if dark else 0.0
    scale = min((max_w - 2 * pad) / iw, (max_h - 2 * pad) / ih)
    w, h = iw * scale, ih * scale
    total_w = w + 2 * pad
    left = x if align == "left" else x + max_w - total_w if align == "right" else x + (max_w - total_w) / 2
    if dark:
        _box(slide, left, y, total_w, h + 2 * pad, fill="FFFFFF", radius=0.08)
    slide.shapes.add_picture(io.BytesIO(data), Inches(left + pad), Inches(y + pad), Inches(w), Inches(h))
    return total_w


def _footer(slide, left: str, n: int, dark=False, x: float = MX):
    col = T.dark_text if dark else T.muted
    used = _logo_box(slide, W - MX - 1.15 - 1.5, H - 0.62, 1.5, 0.42, dark, "right")
    _text(slide, x, H - 0.5, W - MX - 1.2 - x - (used + 0.2 if used else 0), 0.3, [{"t": left, "size": 10, "color": col}])
    _text(slide, W - MX - 1, H - 0.5, 1, 0.25, [{"t": str(n), "size": 10, "color": col, "align": PP_ALIGN.RIGHT}])


def _headline(slide, text: str, dark=False, x: float = MX, w: float | None = None, size: float = 26, y: float = 0.45,
              h: float = 1.1, color: str | None = None):
    _text(slide, x, y, w or (W - 2 * MX), h,
          [{"t": _words(text, 24), "size": size, "bold": True, "head": True,
            "color": color or (T.dark_ink if dark else T.ink), "spacing": 0.95}],
          anchor=MSO_ANCHOR.TOP)


def _label(slide, x: float, y: float, w: float, text: str, color: str):
    _text(slide, x, y, w, 0.3, [{"t": text, "size": 11, "bold": True, "color": color, "spc": 150}])


def _numbered(items, size, color, num_color, after, words, head=False):
    return [{"runs": [{"t": f"{i}  ", "bold": True, "color": num_color}, {"t": _words(t, words)}],
             "size": size, "color": color, "after": after, "head": head} for i, t in enumerate(items, 1)]


# ================================================================== charts


def _numfmt(unit: dict | None, vmax: float) -> str:
    unit = unit or {}
    kind = unit.get("kind", "number")
    if kind == "ratio":
        return "0%"
    if kind == "percent":
        return '0.0"%"'
    pre = f'"{unit["symbol"]}"' if unit.get("symbol") else ""
    suf = f'"{unit["suffix"]}"' if unit.get("suffix") else ""
    for div, core in ((1e9, '0.0,,,"B"'), (1e6, '0.0,,"M"'), (1e4, '0.0,"K"')):
        if vmax >= div:
            return pre + core + suf
    core = "#,##0" if vmax >= 100 else "#,##0.0" if vmax >= 10 else "#,##0.##"
    return pre + core + suf


def _style_axes(chart, fmt: str | None, horizontal_bars=False, labels=False):
    chart.has_title = False
    chart.font.size = Pt(11)
    chart.font.name = T.font_body
    chart.font.color.rgb = rgb(T.muted)
    cat, val = chart.category_axis, chart.value_axis
    cat.format.line.color.rgb = rgb(T.line)
    cat.has_major_gridlines = False
    cat.tick_labels.font.size = Pt(11)
    cat.tick_labels.font.color.rgb = rgb(T.ink2 if horizontal_bars else T.muted)
    val.format.line.fill.background()
    val.has_major_gridlines = not labels
    if not labels:
        val.major_gridlines.format.line.color.rgb = rgb(T.hair)
        val.major_gridlines.format.line.width = Pt(0.75)
    val.tick_labels.font.size = Pt(11)
    if fmt:
        val.tick_labels.number_format = fmt
        val.tick_labels.number_format_is_linked = False
    if labels:
        val.visible = False


def _skip_labels(chart, n: int):
    """Thin out crowded category labels (24 months -> every 3rd)."""
    if n <= 10:
        return
    ax = chart.category_axis._element
    skip = ax.makeelement(qn("c:tickLblSkip"), {"val": str(math.ceil(n / 8))})
    anchor = ax.find(qn("c:noMultiLvlLbl"))
    if anchor is not None:
        anchor.addprevious(skip)
    else:
        ax.append(skip)


def _data_labels(plot, fmt: str, pos=None, size=11):
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format = fmt
    dl.number_format_is_linked = False
    dl.font.size = Pt(size)
    dl.font.name = T.font_body
    dl.font.color.rgb = rgb(T.ink)
    if pos is not None:
        dl.position = pos


def _series_color(name: str, i: int) -> str:
    return T.other if name in ("Other", "(blank)") else T.series[i % len(T.series)]


def _col(p: dict, key: str):
    cols = (p.get("data") or {}).get("columns") or []
    name = (p.get("enc") or {}).get(key)
    return cols.index(name) if name in cols else None


def _draw_chart(slide, p: dict, x: float, y: float, w: float, h: float) -> bool:
    """Native chart for a panel, inside the box. False when the panel has no sensible slide form."""
    chart_t = p["chart"]
    rows = (p.get("data") or {}).get("rows") or []
    if not rows:
        return False
    enc, unit = p.get("enc") or {}, p.get("unit")
    X, Y, Wd, Hh = Inches(x), Inches(y), Inches(w), Inches(h)
    try:
        if chart_t in ("line", "area", "column", "stacked_area", "stacked_column", "small_multiples") and enc.get("x") == "period":
            return _draw_time(slide, p, rows, enc, unit, X, Y, Wd, Hh)
        if chart_t in ("bar", "column", "lollipop", "treemap", "map") and _col(p, "cat") is not None:
            return _draw_bars(slide, p, rows, unit, X, Y, Wd, Hh, horizontal=chart_t != "column")
        if chart_t == "histogram":
            return _draw_bars(slide, p, rows, unit, X, Y, Wd, Hh, horizontal=False, hist=True)
        if chart_t == "waterfall":
            return _draw_waterfall(slide, p, rows, unit, X, Y, Wd, Hh)
        if chart_t == "scatter":
            return _draw_scatter(slide, p, rows, X, Y, Wd, Hh)
        if chart_t == "heatmap":
            return _draw_heatmap(slide, p, rows, unit, x, y, w, h)
    except Exception as err:  # a chart that won't draw must never lose the deck
        print(f"[deck] chart {p.get('id')} ({chart_t}) skipped: {err}", flush=True)
    return False


def _draw_time(slide, p, rows, enc, unit, X, Y, Wd, Hh) -> bool:
    cols = p["data"]["columns"]
    ix, iy = cols.index(enc["x"]), cols.index(enc["y"])
    isr = cols.index(enc["series"]) if enc.get("series") in cols else None
    grain = enc.get("grain", "month")
    periods = list(dict.fromkeys(r[ix] for r in rows))
    cats = [_short_period(v, grain) for v in periods]
    cd = CategoryChartData()
    cd.categories = cats
    if isr is None:
        by = {r[ix]: r[iy] for r in rows}
        cd.add_series(p.get("measure_label") or "Value", [by.get(v) for v in periods])
        names = [p.get("measure_label") or "Value"]
    else:
        names = list(dict.fromkeys(r[isr] for r in rows))[:6]
        for nme in names:
            by = {r[ix]: r[iy] for r in rows if r[isr] == nme}
            cd.add_series(str(nme), [by.get(v) for v in periods])
    kind = p["chart"]
    stacked = isr is not None and kind in ("stacked_area", "stacked_column")
    ct = {"column": XL_CHART_TYPE.COLUMN_CLUSTERED, "area": XL_CHART_TYPE.AREA,
          "stacked_area": XL_CHART_TYPE.AREA_STACKED, "stacked_column": XL_CHART_TYPE.COLUMN_STACKED}.get(kind, XL_CHART_TYPE.LINE)
    if isr is not None and kind in ("area", "column"):
        ct = XL_CHART_TYPE.LINE
    chart = slide.shapes.add_chart(ct, X, Y, Wd, Hh, cd).chart
    totals = {}
    for r in rows:
        totals[r[ix]] = totals.get(r[ix], 0) + (r[iy] if is_num(r[iy]) else 0)
    vmax = max(totals.values()) if stacked else max((r[iy] for r in rows if is_num(r[iy])), default=0)
    _style_axes(chart, _numfmt(unit, vmax))
    _skip_labels(chart, len(cats))
    for i, s in enumerate(chart.plots[0].series):
        col = _series_color(names[i], i)
        if ct == XL_CHART_TYPE.LINE:
            s.format.line.color.rgb = rgb(col)
            s.format.line.width = Pt(2.5)
            s.smooth = False
            s.marker.style = XL_MARKER_STYLE.NONE
        else:
            s.format.fill.solid()
            s.format.fill.fore_color.rgb = rgb(col)
    if isr is not None:
        chart.has_legend = True
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(11)
        chart.legend.font.color.rgb = rgb(T.ink2)
    else:
        chart.has_legend = False
    return True


def _draw_bars(slide, p, rows, unit, X, Y, Wd, Hh, horizontal: bool, hist=False) -> bool:
    cols = p["data"]["columns"]
    ic, iv = (cols.index("bin"), cols.index("n")) if hist else (_col(p, "cat"), _col(p, "value"))
    if ic is None or iv is None:
        return False
    rows = [r for r in rows if is_num(r[iv])]
    if not hist:
        rows = sorted(rows, key=lambda r: -r[iv])[:10]
    cats = [str(r[ic]) for r in rows]
    cd = CategoryChartData()
    cd.categories = cats
    cd.add_series(p.get("measure_label") or "Value", [r[iv] for r in rows])
    chart = slide.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED,
                                   X, Y, Wd, Hh, cd).chart
    fmt = _numfmt(unit, max(r[iv] for r in rows)) if not hist else "#,##0"
    labels = not hist and len(rows) <= 12
    _style_axes(chart, fmt, horizontal_bars=horizontal, labels=labels)
    if horizontal:
        chart.category_axis.reverse_order = True
    chart.has_legend = False
    plot = chart.plots[0]
    plot.gap_width = 12 if hist else 55
    plot.vary_by_categories = False
    series = plot.series[0]
    series.invert_if_negative = False
    hl = p.get("highlight")
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = rgb(T.accent if hist else T.bar_soft)
    if not hist:
        for i, c in enumerate(cats):
            pt = series.points[i]
            pt.format.fill.solid()
            pt.format.fill.fore_color.rgb = rgb(T.accent if (c == str(hl) if hl is not None else i == 0) else T.bar_soft)
    if labels:
        _data_labels(plot, fmt, XL_LABEL_POSITION.OUTSIDE_END)
    if hist:
        _skip_labels(chart, len(cats))
    return True


def _draw_waterfall(slide, p, rows, unit, X, Y, Wd, Hh) -> bool:
    cols = p["data"]["columns"]
    ic, idl = cols.index("label"), cols.index("delta")
    rows = sorted([r for r in rows if is_num(r[idl])], key=lambda r: -abs(r[idl]))[:8]
    cd = CategoryChartData()
    cd.categories = [str(r[ic]) for r in rows]
    cd.add_series("Change", [r[idl] for r in rows])
    chart = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, X, Y, Wd, Hh, cd).chart
    base = _numfmt(unit, max(abs(r[idl]) for r in rows))
    fmt = f"+{base};-{base}"
    _style_axes(chart, fmt, labels=True)
    chart.has_legend = False
    plot = chart.plots[0]
    plot.gap_width = 55
    series = plot.series[0]
    series.invert_if_negative = False
    for i, r in enumerate(rows):
        pt = series.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = rgb(T.accent if r[idl] >= 0 else T.negative)
    _data_labels(plot, fmt, XL_LABEL_POSITION.OUTSIDE_END)
    chart.category_axis.tick_label_position = XL_TICK_LABEL_POSITION.LOW
    return True


def _draw_scatter(slide, p, rows, X, Y, Wd, Hh) -> bool:
    enc = p["enc"]
    cols = p["data"]["columns"]
    ix, iy = cols.index(enc["x"]), cols.index(enc["y"])
    ic = cols.index(enc["color"]) if enc.get("color") in cols else None
    step = max(1, len(rows) // 300)
    pts = [r for r in rows[::step] if is_num(r[ix]) and is_num(r[iy])]
    groups = list(dict.fromkeys((r[ic] if ic is not None else None) for r in pts))[:6]
    cd = XyChartData()
    for gname in groups:
        s = cd.add_series(str(gname) if gname is not None else (p.get("y_label") or "Records"))
        for r in pts:
            if (r[ic] if ic is not None else None) == gname:
                s.add_data_point(r[ix], r[iy])
    chart = slide.shapes.add_chart(XL_CHART_TYPE.XY_SCATTER, X, Y, Wd, Hh, cd).chart
    _style_axes(chart, None)
    for ax, key in ((chart.category_axis, "x"), (chart.value_axis, "y")):
        ax.has_major_gridlines = True
        ax.major_gridlines.format.line.color.rgb = rgb(T.hair)
        ax.tick_labels.font.size = Pt(11)
        lab = p.get(f"{key}_label")
        if lab:
            ax.has_title = True
            ax.axis_title.text_frame.text = str(lab)
            r = ax.axis_title.text_frame.paragraphs[0].runs[0]
            r.font.size, r.font.bold, r.font.name = Pt(11), False, T.font_body
            r.font.color.rgb = rgb(T.ink2)
    for i, s in enumerate(chart.plots[0].series):
        s.format.line.fill.background()
        s.marker.style = XL_MARKER_STYLE.CIRCLE
        s.marker.size = 6
        s.marker.format.fill.solid()
        s.marker.format.fill.fore_color.rgb = rgb(_series_color(str(groups[i]), i))
        s.marker.format.line.fill.background()
    multi = len(groups) > 1
    chart.has_legend = multi
    if multi:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(11)
        chart.legend.font.color.rgb = rgb(T.ink2)
    return True


def _draw_heatmap(slide, p, rows, unit, x, y, w, h) -> bool:
    cols = p["data"]["columns"]
    ix, iy, iv = cols.index("x"), cols.index("y"), cols.index("value")
    xs = p.get("x_order") or list(dict.fromkeys(r[ix] for r in rows))
    ys = p.get("y_order") or list(dict.fromkeys(r[iy] for r in rows))
    if len(xs) > 14 or len(ys) > 12 or len(xs) < 2 or len(ys) < 2:
        return False
    grid = {(str(r[ix]), str(r[iy])): r[iv] for r in rows if is_num(r[iv])}
    vals = list(grid.values())
    if not vals:
        return False
    lo, hi = min(vals), max(vals)
    legend_h = 0.3
    n_r, n_c = len(ys) + 1, len(xs) + 1
    row_h = min(0.5, (h - legend_h - 0.1) / n_r)
    if row_h < 0.17:
        return False
    tbl_shape = slide.shapes.add_table(n_r, n_c, Inches(x), Inches(y), Inches(w), Inches(row_h * n_r))
    tbl = tbl_shape.table
    tblPr = tbl._tbl.tblPr
    for attr in ("firstRow", "bandRow"):
        tblPr.set(attr, "0")
    first_w = 1.0
    tbl.columns[0].width = Inches(first_w)
    for c in range(1, n_c):
        tbl.columns[c].width = Inches((w - first_w) / len(xs))
    for r in range(n_r):
        tbl.rows[r].height = Inches(row_h)
    fsz = 10 if row_h >= 0.24 else 8
    show_nums = len(xs) <= 8
    fmt_u = unit or {}
    def cell(r, c, text, fill, color, bold=False, align=PP_ALIGN.CENTER):
        ce = tbl.cell(r, c)
        ce.margin_left = ce.margin_right = Inches(0.03)
        ce.margin_top = ce.margin_bottom = Inches(0.02)
        ce.vertical_anchor = MSO_ANCHOR.MIDDLE
        if fill:
            ce.fill.solid()
            ce.fill.fore_color.rgb = rgb(fill)
        else:
            ce.fill.background()
        tf = ce.text_frame
        tf.paragraphs[0].alignment = align
        run = tf.paragraphs[0].add_run()
        run.text = text
        run.font.size, run.font.name, run.font.bold = Pt(fsz), T.font_body, bold
        run.font.color.rgb = rgb(color)

    cell(0, 0, "", None, T.muted)
    for c, xv in enumerate(xs, 1):
        cell(0, c, str(xv), None, T.muted)
    for r, yv in enumerate(ys, 1):
        cell(r, 0, str(yv), None, T.ink2, bold=True, align=PP_ALIGN.LEFT)
        for c, xv in enumerate(xs, 1):
            v = grid.get((str(xv), str(yv)))
            if v is None:
                cell(r, c, "", T.surface, T.muted)
                continue
            t = 0 if hi == lo else (v - lo) / (hi - lo)
            idx = min(len(T.ramp) - 1, int(t * len(T.ramp)))
            cell(r, c, fmt_value(v, fmt_u) if show_nums else "", T.ramp[idx], "FFFFFF" if _luma(T.ramp[idx]) < 140 else "0B0B0B")
    _text(slide, x, y + row_h * n_r + 0.08, w, legend_h,
          [{"t": f"{T.ramp_word} = higher {p.get('measure_label') or 'value'}", "size": 11, "color": T.muted}])
    return True


# ================================================================== slides
# Every design draws the same five slide kinds (title, glance, evidence, decisions, gaps) from the same content,
# so the speaker notes and the content helpers below are shared.


def _note(slide, text: str):
    slide.notes_slide.notes_text_frame.text = text


def _notes_title(plan):
    return "Open with the single message: " + plan.get("takeaway", "") + "\nEverything that follows either proves it or asks the room to act on it."


def _notes_evidence(sl, panel):
    return "\n".join([sl["headline"], *(sl.get("points") or []), ("So what: " + sl["so_what"]) if sl.get("so_what") else "",
                      f"Source panel: {panel.get('title', '')}"]).strip()


def _notes_decisions(decs):
    return "\n".join(f"{i}. {d['decision']} — {d.get('why', '')}" for i, d in enumerate(decs, 1))


def _notes_gaps(plan):
    return "Data limitations (for Q&A, not a slide):\n" + "\n".join(plan.get("gaps") or []) + "\nNext steps:\n" + "\n".join(plan.get("next_steps") or [])


def _ev_parts(sl: dict, panel: dict) -> tuple[list[str], str, str]:
    """(supporting points, chart caption, so-what) with no sentence repeated on the slide."""
    pts = sl.get("points") or []
    cap = panel.get("subtitle") or panel.get("measure_label") or ""
    if cap in pts:
        cap = panel.get("measure_label") or ""
    return pts[:3], cap, sl.get("so_what") or ""


def _chart_or_note(s, panel: dict, x: float, y: float, w: float, h: float):
    if not _draw_chart(s, panel, x, y, w, h):
        _text(s, x + 0.2, y + 0.6, w - 0.4, max(h - 1.2, 0.5),
              [{"t": panel.get("title", ""), "size": 22, "bold": True, "spacing": 1.0},
               {"t": "This view works best interactively in the dashboard.", "size": 12, "color": T.muted}], anchor=MSO_ANCHOR.MIDDLE)


def _kpi_h(vsize: float, pad: float) -> float:
    return 2 * pad + 0.3 + vsize * 1.3 / 72 + 0.5


def _kpi(s, x: float, y: float, w: float, m: dict, vsize: float = 30, card: bool = True, vcolor: str | None = None) -> float:
    """One metric (label, value, recent movement); a card when `card`, otherwise bare. Returns its height."""
    pad = 0.22 if card else 0.0
    h = _kpi_h(vsize, pad)
    if card:
        _box(s, x, y, w, h, fill=T.surface, line=T.hair, radius=T.radius)
    vh = vsize * 1.3 / 72
    parts = [p.strip() for p in (m.get("change") or "").split(";") if p.strip()][:2]
    _text(s, x + pad, y + pad, w - 2 * pad, 0.28, [{"t": _words(m["label"], 5) + (f" · {m['tag'].lower()}" if m.get("tag") and m["tag"] != "Count" else ""), "size": 12, "color": T.muted}])
    _text(s, x + pad, y + pad + 0.3, w - 2 * pad, vh, [{"t": m["value"], "size": vsize, "bold": True, "head": True, "color": vcolor or T.ink}])
    _text(s, x + pad, y + pad + 0.34 + vh, w - 2 * pad, 0.45, [{"t": "; ".join(parts) or m.get("basis", ""), "size": 11, "color": T.ink2}])
    return h


def _summary(plan: dict, dash: dict) -> str:
    return dash["story"]["headline"].get("summary") or plan.get("takeaway", "")




def _classic_title(prs, plan: dict, dash: dict, ctx: str):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(s, T.dark)
    _box(s, 10.4, -1.9, 5.2, 5.2, fill=T.deco1, shape=MSO_SHAPE.OVAL)
    _box(s, 11.7, -0.9, 3.0, 3.0, fill=T.deco2, shape=MSO_SHAPE.OVAL)
    title = dash["story"]["headline"].get("title") or dash["meta"]["scope_label"]
    _logo_box(s, 0.8, 0.25, 2.4, 0.55, True)
    _text(s, 0.8, 0.9, 9, 0.3, [{"t": "EXECUTIVE BRIEFING", "size": 12, "bold": True, "color": T.accent_light, "spc": 200}])
    _text(s, 0.8, 1.3, 9.2, 1.5, [{"t": _words(title, 10), "size": 44, "bold": True, "head": True, "color": T.dark_ink, "spacing": 0.95}])
    _text(s, 0.8, 3.2, 9, 0.3, [{"t": "THE CENTRAL TAKEAWAY", "size": 12, "bold": True, "color": T.dark_text, "spc": 200}])
    _text(s, 0.8, 3.6, 9.6, 2.2, [{"t": _words(plan.get("takeaway", ""), 34), "size": 28, "head": True, "color": T.dark_ink, "spacing": 1.0}])
    _text(s, 0.8, 6.65, 11.5, 0.3, [{"t": ctx, "size": 12, "color": T.dark_text}])
    _note(s, _notes_title(plan))


def _classic_glance(prs, plan: dict, dash: dict, metrics: list[dict], footer: str, n: int):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(s, T.page)
    _headline(s, plan.get("glance_headline") or plan.get("takeaway", ""))
    top = 1.75
    cards = metrics[:4]
    if cards:
        gap = 0.3
        cw = (W - 2 * MX - gap * (len(cards) - 1)) / len(cards)
        for i, m in enumerate(cards):
            cx = MX + i * (cw + gap)
            _box(s, cx, top, cw, 1.75, fill=T.surface, line=T.hair, radius=T.radius)
            parts = [x.strip() for x in (m.get("change") or "").split(";") if x.strip()][:2]
            _text(s, cx + 0.25, top + 0.2, cw - 0.5, 0.3, [{"t": _words(m["label"], 5), "size": 12, "color": T.muted}])
            _text(s, cx + 0.25, top + 0.52, cw - 0.5, 0.65, [{"t": m["value"], "size": 36, "bold": True}])
            _text(s, cx + 0.25, top + 1.2, cw - 0.5, 0.45,
                  [{"t": "; ".join(parts) or m.get("basis", ""), "size": 11, "color": T.ink2}])
        top += 1.75 + 0.35
    bottom = H - 0.75
    summary = dash["story"]["headline"].get("summary") or plan.get("takeaway", "")
    decs = plan.get("decisions") or []
    left_w = 7.4 if decs else W - 2 * MX
    _box(s, MX, top, left_w, bottom - top, fill=T.surface, line=T.hair, radius=T.radius)
    _text(s, MX + 0.3, top + 0.25, left_w - 0.6, 0.3, [{"t": "WHAT HAPPENED", "size": 11, "bold": True, "color": T.accent, "spc": 150}])
    _text(s, MX + 0.3, top + 0.65, left_w - 0.6, bottom - top - 0.85,
          [{"t": _words(summary, 70), "size": 15 if cards else 17, "color": T.ink, "spacing": 1.08}])
    if decs:
        dx = MX + left_w + 0.3
        dw = W - MX - dx
        _box(s, dx, top, dw, bottom - top, fill=T.accent, radius=T.radius)
        _text(s, dx + 0.3, top + 0.25, dw - 0.6, 0.3, [{"t": "DECISIONS ON THE TABLE", "size": 11, "bold": True, "color": T.on_accent, "spc": 150}])
        paras = [{"runs": [{"t": f"{i}  ", "bold": True}, {"t": _words(d["decision"], 12)}],
                  "size": 12.5, "color": T.on_accent, "after": 6} for i, d in enumerate(decs[:3], 1)]
        _text(s, dx + 0.3, top + 0.65, dw - 0.6, bottom - top - 0.85, paras)
    _footer(s, footer, n)
    _note(s, summary)


def _classic_evidence(prs, sl: dict, panel: dict, footer: str, n: int):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(s, T.page)
    _headline(s, sl["headline"])
    top, bottom = 1.75, H - 0.75
    cw = 7.7
    _box(s, MX, top, cw, bottom - top, fill=T.surface, line=T.hair, radius=T.radius)
    pts = sl.get("points") or []
    cap = panel.get("subtitle") or panel.get("measure_label") or ""
    if cap in pts:  # don't say the same thing twice on one slide
        cap = panel.get("measure_label") or ""
    cap_h = 0.0
    if cap:
        _text(s, MX + 0.3, top + 0.2, cw - 0.6, 0.45, [{"t": _words(cap, 22), "size": 11, "color": T.muted}])
        cap_h = 0.5
    drawn = _draw_chart(s, panel, MX + 0.2, top + 0.15 + cap_h, cw - 0.4, bottom - top - 0.3 - cap_h)
    if not drawn:
        _text(s, MX + 0.4, top + 0.9, cw - 0.8, bottom - top - 1.4,
              [{"t": panel.get("title", ""), "size": 24, "bold": True, "spacing": 1.0},
               {"t": "This view works best interactively in the dashboard.", "size": 12, "color": T.muted}], anchor=MSO_ANCHOR.MIDDLE)
    rx = MX + cw + 0.3
    rw = W - MX - rx
    so = sl.get("so_what")
    card_h = 1.5 if so else 0
    _text(s, rx, top + 0.05, rw, 0.3, [{"t": "WHAT THE DATA SHOWS", "size": 11, "bold": True, "color": T.accent, "spc": 150}])
    area_h = bottom - top - 0.5 - (card_h + 0.25 if so else 0)
    _text(s, rx, top + 0.5, rw, area_h,
          [{"t": _words(t, 20), "size": 13, "bullet": True, "after": 8, "color": T.ink} for t in pts[:3]])
    if so:
        cy = bottom - card_h
        _box(s, rx, cy, rw, card_h, fill=T.accent_soft, radius=T.radius)
        _text(s, rx + 0.25, cy + 0.2, rw - 0.5, 0.3, [{"t": "SO WHAT", "size": 11, "bold": True, "color": T.accent_deep, "spc": 150}])
        _text(s, rx + 0.25, cy + 0.55, rw - 0.5, card_h - 0.7, [{"t": _words(so, 22), "size": 13, "bold": True, "color": T.ink}])
    _footer(s, footer, n)
    _note(s, _notes_evidence(sl, panel))


def _classic_decisions(prs, plan: dict, footer: str, n: int):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(s, T.page)
    decs = plan["decisions"][:4]
    _headline(s, "What we need this group to decide" if len(decs) > 1 else "The decision in front of us")
    top = 1.75
    gap = 0.17
    rh = min(1.15, (H - 0.75 - top - gap * (len(decs) - 1)) / len(decs))
    for i, d in enumerate(decs):
        y = top + i * (rh + gap)
        _box(s, MX, y, W - 2 * MX, rh, fill=T.surface, line=T.hair, radius=T.radius)
        c = _box(s, MX + 0.3, y + rh / 2 - 0.3, 0.6, 0.6, fill=T.accent, shape=MSO_SHAPE.OVAL)
        tf = c.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        r = tf.paragraphs[0].add_run()
        r.text = str(i + 1)
        r.font.size, r.font.bold, r.font.name = Pt(20), True, T.font_head
        r.font.color.rgb = rgb(T.on_accent)
        _text(s, MX + 1.15, y + 0.12, 5.5, rh - 0.24, [{"t": _words(d["decision"], 20), "size": 15.5, "bold": True, "spacing": 1.0}],
              anchor=MSO_ANCHOR.MIDDLE)
        ev = _words(d.get("why", ""), 34)
        _text(s, MX + 6.9, y + 0.12, W - 2 * MX - 7.2, rh - 0.24, [{"t": ev, "size": 12.5, "color": T.ink2, "spacing": 1.0}],
              anchor=MSO_ANCHOR.MIDDLE)
    _footer(s, footer, n)
    _note(s, _notes_decisions(decs))


def _classic_gaps(prs, plan: dict, footer: str, n: int):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _bg(s, T.dark)
    _headline(s, "Next steps", dark=True)
    top, bottom = 1.75, H - 0.75
    _box(s, MX, top, W - 2 * MX, bottom - top, fill=T.dark_card, radius=T.radius)
    paras = [{"runs": [{"t": f"{j}  ", "bold": True, "color": T.accent_light}, {"t": _words(t, 28)}],
              "size": 17, "color": T.dark_ink, "after": 16} for j, t in enumerate(plan.get("next_steps") or [], 1)]
    _text(s, MX + 0.5, top + 0.5, W - 2 * MX - 1.0, bottom - top - 1.0, paras)
    _footer(s, footer, n, dark=True)
    _note(s, _notes_gaps(plan))


# ------------------------------------------------------------------ design: editorial
# Flat and airy: no cards, serif headlines, large figures, plenty of white space.

TOP, BOTTOM = 1.75, H - 0.75
CW = W - 2 * MX  # content width


def _ed_title(prs, plan, dash, ctx):
    s = _new(prs, T.page)
    title = dash["story"]["headline"].get("title") or dash["meta"]["scope_label"]
    _logo_box(s, 0.9, 0.3, 2.4, 0.55, False)
    _label(s, 0.9, 1.0, 9, "EXECUTIVE BRIEFING", T.accent)
    _text(s, 0.9, 1.5, 10.5, 1.7, [{"t": _words(title, 10), "size": 50, "bold": True, "head": True, "color": T.ink, "spacing": 0.92}])
    _label(s, 0.9, 3.9, 9, "THE CENTRAL TAKEAWAY", T.muted)
    _text(s, 0.9, 4.3, 9.8, 2.0, [{"t": _words(plan.get("takeaway", ""), 34), "size": 24, "head": True, "color": T.ink2, "spacing": 1.05}])
    _text(s, 0.9, 6.65, 11.5, 0.3, [{"t": ctx, "size": 12, "color": T.muted}])
    _note(s, _notes_title(plan))


def _ed_glance(prs, plan, dash, metrics, footer, n):
    s = _new(prs, T.page)
    _headline(s, plan.get("glance_headline") or plan.get("takeaway", ""), size=28)
    y = TOP
    cards = metrics[:4]
    if cards:
        gap = 0.5
        cw = (CW - gap * (len(cards) - 1)) / len(cards)
        for i, m in enumerate(cards):
            h = _kpi(s, MX + i * (cw + gap), y, cw, m, vsize=38, card=False, vcolor=T.accent)
        y += h + 0.4
    decs = plan.get("decisions") or []
    lw = 7.2 if decs else CW
    summary = _summary(plan, dash)
    _label(s, MX, y, lw, "WHAT HAPPENED", T.accent)
    _text(s, MX, y + 0.4, lw, BOTTOM - y - 0.4, [{"t": _words(summary, 70), "size": 14.5, "color": T.ink, "spacing": 1.08}])
    if decs:
        dx = MX + lw + 0.6
        _label(s, dx, y, W - MX - dx, "DECISIONS ON THE TABLE", T.accent)
        _text(s, dx, y + 0.4, W - MX - dx, BOTTOM - y - 0.4, _numbered([d["decision"] for d in decs[:3]], 13, T.ink, T.accent, 9, 14))
    _footer(s, footer, n)
    _note(s, summary)


def _ed_evidence(prs, sl, panel, footer, n):
    s = _new(prs, T.page)
    _headline(s, sl["headline"])
    pts, cap, so = _ev_parts(sl, panel)
    cw = 8.0
    cy = TOP
    if cap:
        _text(s, MX, cy, cw, 0.4, [{"t": _words(cap, 22), "size": 11, "color": T.muted}])
        cy += 0.45
    _chart_or_note(s, panel, MX, cy, cw, BOTTOM - cy)
    rx = MX + cw + 0.5
    rw = W - MX - rx
    _label(s, rx, TOP, rw, "WHAT THE DATA SHOWS", T.accent)
    _text(s, rx, TOP + 0.45, rw, 2.9, [{"t": _words(t, 20), "size": 13, "bullet": True, "after": 8, "color": T.ink} for t in pts])
    if so:
        _label(s, rx, BOTTOM - 1.55, rw, "SO WHAT", T.accent)
        _text(s, rx, BOTTOM - 1.15, rw, 1.15, [{"t": _words(so, 22), "size": 15, "bold": True, "head": True, "color": T.ink, "spacing": 1.0}])
    _footer(s, footer, n)
    _note(s, _notes_evidence(sl, panel))


def _ed_decisions(prs, plan, footer, n):
    s = _new(prs, T.page)
    decs = plan["decisions"][:4]
    _headline(s, "What we need this group to decide" if len(decs) > 1 else "The decision in front of us")
    cols = 2 if len(decs) > 1 else 1
    rows = math.ceil(len(decs) / cols)
    gx, gy = 0.7, 0.3
    cw = (CW - gx * (cols - 1)) / cols
    ch = (BOTTOM - TOP - gy * (rows - 1)) / rows
    for i, d in enumerate(decs):
        x, y = MX + (i % cols) * (cw + gx), TOP + (i // cols) * (ch + gy)
        _text(s, x, y, 0.9, 0.8, [{"t": str(i + 1), "size": 44, "bold": True, "head": True, "color": T.accent}])
        _text(s, x + 1.0, y + 0.05, cw - 1.0, 0.9, [{"t": _words(d["decision"], 18), "size": 15.5, "bold": True, "color": T.ink, "spacing": 1.0}])
        _text(s, x + 1.0, y + 1.0, cw - 1.0, ch - 1.0, [{"t": _words(d.get("why", ""), 32), "size": 12.5, "color": T.ink2, "spacing": 1.05}])
    _footer(s, footer, n)
    _note(s, _notes_decisions(decs))


def _ed_gaps(prs, plan, footer, n):
    s = _new(prs, T.page)
    _headline(s, "Next steps")
    _text(s, MX, TOP, CW, BOTTOM - TOP, _numbered(plan.get("next_steps") or [], 17, T.ink, T.accent, 16, 28))
    _footer(s, footer, n)
    _note(s, _notes_gaps(plan))


# ------------------------------------------------------------------ design: split
# A colour panel carries the message; the evidence sits beside it.

PW = 4.4  # panel width
RX = PW + 0.45  # right area x
RW = W - MX - RX


def _panel(s, label: str | None = None):
    _box(s, 0, 0, PW, H, fill=T.dark)
    if label:
        _label(s, 0.55, 0.6, PW - 1.0, label, T.accent_light)


def _sp_title(prs, plan, dash, ctx):
    s = _new(prs, T.page)
    _box(s, 0, 0, 5.6, H, fill=T.dark)
    _box(s, 3.6, 4.6, 4.4, 4.4, fill=T.deco1, shape=MSO_SHAPE.OVAL)
    _box(s, 4.5, 5.6, 2.6, 2.6, fill=T.deco2, shape=MSO_SHAPE.OVAL)
    title = dash["story"]["headline"].get("title") or dash["meta"]["scope_label"]
    _logo_box(s, 0.7, 0.25, 2.4, 0.55, True)
    _label(s, 0.7, 0.9, 4.4, "EXECUTIVE BRIEFING", T.accent_light)
    _text(s, 0.7, 1.4, 4.6, 3.2, [{"t": _words(title, 10), "size": 38, "bold": True, "head": True, "color": T.dark_ink, "spacing": 0.95}])
    _label(s, 6.3, 1.4, 6.4, "THE CENTRAL TAKEAWAY", T.muted)
    _text(s, 6.3, 1.9, 6.4, 3.8, [{"t": _words(plan.get("takeaway", ""), 34), "size": 26, "head": True, "color": T.ink, "spacing": 1.02}])
    _text(s, 6.3, 6.65, 6.4, 0.5, [{"t": ctx, "size": 11, "color": T.muted}])
    _note(s, _notes_title(plan))


def _sp_glance(prs, plan, dash, metrics, footer, n):
    s = _new(prs, T.page)
    _panel(s, "WHAT HAPPENED")
    _text(s, 0.55, 1.05, PW - 1.0, 2.1, [{"t": _words(plan.get("glance_headline") or plan.get("takeaway", ""), 24), "size": 21, "bold": True,
                                          "head": True, "color": T.dark_ink, "spacing": 0.98}])
    _text(s, 0.55, 3.35, PW - 1.0, H - 3.35 - 0.6, [{"t": _words(_summary(plan, dash), 55), "size": 12, "color": T.dark_text, "spacing": 1.08}])
    cards = metrics[:4]
    y = 0.6
    if cards:
        gap = 0.25
        cw = (RW - gap) / 2
        for i, m in enumerate(cards):
            h = _kpi(s, RX + (i % 2) * (cw + gap), y + (i // 2) * (_kpi_h(30, 0.22) + gap), cw, m, vsize=30)
        y += math.ceil(len(cards) / 2) * (h + gap)
    decs = plan.get("decisions") or []
    if decs:
        _box(s, RX, y, RW, H - 0.6 - y, fill=T.accent, radius=T.radius)
        _label(s, RX + 0.3, y + 0.25, RW - 0.6, "DECISIONS ON THE TABLE", T.on_accent)
        _text(s, RX + 0.3, y + 0.65, RW - 0.6, H - 0.6 - y - 0.8, _numbered([d["decision"] for d in decs[:3]], 12.5, T.on_accent, T.on_accent, 6, 12))
    _footer(s, footer, n, x=RX)
    _note(s, _summary(plan, dash))


def _sp_evidence(prs, sl, panel, footer, n):
    s = _new(prs, T.page)
    pts, cap, so = _ev_parts(sl, panel)
    _panel(s, "THE EVIDENCE")
    _text(s, 0.55, 1.05, PW - 1.0, 2.4, [{"t": _words(sl["headline"], 22), "size": 20, "bold": True, "head": True, "color": T.dark_ink, "spacing": 0.98}])
    _text(s, 0.55, 3.35, PW - 1.0, 2.0,
          [{"t": _words(t, 18), "size": 12, "bullet": True, "bullet_color": T.accent_light, "color": T.dark_text, "after": 6} for t in pts])
    if so:
        _text(s, 0.55, H - 1.65, PW - 1.0, 1.1, [{"t": _words(so, 22), "size": 12.5, "bold": True, "color": T.accent_light, "spacing": 1.0}],
              anchor=MSO_ANCHOR.BOTTOM)
    top, bottom = 0.6, H - 0.75
    _box(s, RX, top, RW, bottom - top, fill=T.surface, line=T.hair, radius=T.radius)
    cy = top + 0.2
    if cap:
        _text(s, RX + 0.3, cy, RW - 0.6, 0.45, [{"t": _words(cap, 22), "size": 11, "color": T.muted}])
        cy += 0.5
    _chart_or_note(s, panel, RX + 0.2, cy, RW - 0.4, bottom - cy - 0.15)
    _footer(s, footer, n, x=RX)
    _note(s, _notes_evidence(sl, panel))


def _sp_decisions(prs, plan, footer, n):
    s = _new(prs, T.page)
    decs = plan["decisions"][:4]
    _panel(s, "THE ASK")
    _text(s, 0.55, 1.05, PW - 1.0, 3.0, [{"t": "What we need this group to decide" if len(decs) > 1 else "The decision in front of us",
                                          "size": 26, "bold": True, "head": True, "color": T.dark_ink, "spacing": 0.98}])
    top, bottom, gap = 0.6, H - 0.75, 0.18
    rh = min(1.55, (bottom - top - gap * (len(decs) - 1)) / len(decs))
    for i, d in enumerate(decs):
        y = top + i * (rh + gap)
        _box(s, RX, y, RW, rh, fill=T.surface, line=T.hair, radius=T.radius)
        c = _box(s, RX + 0.25, y + 0.25, 0.55, 0.55, fill=T.accent, shape=MSO_SHAPE.OVAL)
        tf = c.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        r = tf.paragraphs[0].add_run()
        r.text = str(i + 1)
        r.font.size, r.font.bold, r.font.name = Pt(18), True, T.font_head
        r.font.color.rgb = rgb(T.on_accent)
        _text(s, RX + 1.05, y + 0.18, RW - 1.3, rh - 0.3,
              [{"t": _words(d["decision"], 18), "size": 14.5, "bold": True, "color": T.ink, "after": 3, "spacing": 1.0},
               {"t": _words(d.get("why", ""), 30), "size": 12, "color": T.ink2, "spacing": 1.03}])
    _footer(s, footer, n, x=RX)
    _note(s, _notes_decisions(decs))


def _sp_gaps(prs, plan, footer, n):
    s = _new(prs, T.page)
    _panel(s, "WHAT HAPPENS NEXT")
    _text(s, 0.55, 1.05, PW - 1.0, 3.5, [{"t": "Next steps", "size": 26, "bold": True, "head": True, "color": T.dark_ink, "spacing": 0.98}])
    top, bottom = 0.6, H - 0.75
    _box(s, RX, top, RW, bottom - top, fill=T.surface, line=T.hair, radius=T.radius)
    _text(s, RX + 0.4, top + 0.5, RW - 0.8, bottom - top - 1.0, _numbered(plan.get("next_steps") or [], 15, T.ink, T.accent, 14, 24))
    _footer(s, footer, n, x=RX)
    _note(s, _notes_gaps(plan))


# ------------------------------------------------------------------ design: focus
# The chart gets the width; takeaways run in a row beneath it.


def _fc_title(prs, plan, dash, ctx):
    s = _new(prs, T.dark)
    _box(s, -1.8, 5.0, 4.6, 4.6, fill=T.deco1, shape=MSO_SHAPE.OVAL)
    _box(s, 10.6, -1.6, 4.0, 4.0, fill=T.deco2, shape=MSO_SHAPE.OVAL)
    title = dash["story"]["headline"].get("title") or dash["meta"]["scope_label"]
    c = PP_ALIGN.CENTER
    _logo_box(s, (W - 2.4) / 2, 0.3, 2.4, 0.55, True, "center")
    _text(s, 1.5, 1.0, W - 3, 0.3, [{"t": "EXECUTIVE BRIEFING", "size": 12, "bold": True, "color": T.accent_light, "spc": 200, "align": c}])
    _text(s, 1.5, 1.45, W - 3, 1.7, [{"t": _words(title, 10), "size": 48, "bold": True, "head": True, "color": T.dark_ink, "spacing": 0.92, "align": c}])
    _text(s, 2.0, 3.75, W - 4, 0.3, [{"t": "THE CENTRAL TAKEAWAY", "size": 12, "bold": True, "color": T.dark_text, "spc": 200, "align": c}])
    _text(s, 2.0, 4.15, W - 4, 2.1, [{"t": _words(plan.get("takeaway", ""), 34), "size": 24, "head": True, "color": T.dark_ink, "spacing": 1.02, "align": c}])
    _text(s, 1.5, 6.7, W - 3, 0.3, [{"t": ctx, "size": 11, "color": T.dark_text, "align": c}])
    _note(s, _notes_title(plan))


def _fc_glance(prs, plan, dash, metrics, footer, n):
    s = _new(prs, T.page)
    _headline(s, plan.get("glance_headline") or plan.get("takeaway", ""), size=27, h=1.0)
    summary = _summary(plan, dash)
    y = 1.6
    _text(s, MX, y, CW, 1.15, [{"t": _words(summary, 70), "size": 13.5, "color": T.ink2, "spacing": 1.05}])
    y += 1.3
    cards = metrics[:4]
    if cards:
        gap = 0.25
        cw = (CW - gap * (len(cards) - 1)) / len(cards)
        for i, m in enumerate(cards):
            h = _kpi(s, MX + i * (cw + gap), y, cw, m, vsize=28)
        y += h + 0.3
    decs = plan.get("decisions") or []
    if decs:
        _label(s, MX, y, CW, "DECISIONS ON THE TABLE", T.accent)
        y += 0.38
        k = min(3, len(decs))
        gap = 0.25
        cw = (CW - gap * (k - 1)) / k
        for i, d in enumerate(decs[:k]):
            x = MX + i * (cw + gap)
            _box(s, x, y, cw, BOTTOM + 0.05 - y, fill=T.accent_soft, radius=T.radius)
            _text(s, x + 0.25, y + 0.2, cw - 0.5, BOTTOM - y - 0.3,
                  _numbered([d["decision"]], 12.5, T.ink, T.accent_deep, 0, 16, head=False))
    _footer(s, footer, n)
    _note(s, summary)


def _fc_evidence(prs, sl, panel, footer, n):
    s = _new(prs, T.page)
    _headline(s, sl["headline"], h=1.0)
    pts, cap, so = _ev_parts(sl, panel)
    cols = len(pts) + (1 if so else 0)
    row_h = 1.7 if cols else 0
    ch_bottom = BOTTOM - (row_h + 0.25 if cols else 0)
    top = 1.6
    _box(s, MX, top, CW, ch_bottom - top, fill=T.surface, line=T.hair, radius=T.radius)
    cy = top + 0.12
    if cap:
        _text(s, MX + 0.3, cy, CW - 0.6, 0.35, [{"t": _words(cap, 24), "size": 11, "color": T.muted}])
        cy += 0.38
    _chart_or_note(s, panel, MX + 0.2, cy, CW - 0.4, ch_bottom - cy - 0.1)
    if cols:
        gap = 0.3
        cw = (CW - gap * (cols - 1)) / cols
        y = ch_bottom + 0.25
        for i, t in enumerate(pts):
            x = MX + i * (cw + gap)
            _text(s, x, y, cw, row_h, [{"t": f"{i + 1}", "size": 20, "bold": True, "head": True, "color": T.accent, "after": 2},
                                       {"t": _words(t, 20), "size": 12.5, "color": T.ink, "spacing": 1.03}])
        if so:
            x = MX + len(pts) * (cw + gap)
            _box(s, x, y, cw, row_h, fill=T.accent_soft, radius=T.radius)
            _label(s, x + 0.2, y + 0.15, cw - 0.4, "SO WHAT", T.accent_deep)
            _text(s, x + 0.2, y + 0.5, cw - 0.4, row_h - 0.6, [{"t": _words(so, 20), "size": 12.5, "bold": True, "color": T.ink, "spacing": 1.0}])
    _footer(s, footer, n)
    _note(s, _notes_evidence(sl, panel))


def _fc_decisions(prs, plan, footer, n):
    s = _new(prs, T.page)
    decs = plan["decisions"][:4]
    _headline(s, "What we need this group to decide" if len(decs) > 1 else "The decision in front of us", h=0.9)
    k = len(decs)
    gap = 0.25
    cw = (CW - gap * (k - 1)) / k
    top = 1.6
    for i, d in enumerate(decs):
        x = MX + i * (cw + gap)
        _box(s, x, top, cw, BOTTOM - top, fill=T.surface, line=T.hair, radius=T.radius)
        c = _box(s, x + 0.25, top + 0.25, 0.6, 0.6, fill=T.accent, shape=MSO_SHAPE.OVAL)
        tf = c.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        r = tf.paragraphs[0].add_run()
        r.text = str(i + 1)
        r.font.size, r.font.bold, r.font.name = Pt(20), True, T.font_head
        r.font.color.rgb = rgb(T.on_accent)
        _text(s, x + 0.25, top + 1.1, cw - 0.5, BOTTOM - top - 1.3,
              [{"t": _words(d["decision"], 18), "size": 14.5, "bold": True, "color": T.ink, "after": 8, "spacing": 1.0},
               {"t": _words(d.get("why", ""), 30), "size": 12, "color": T.ink2, "spacing": 1.05}])
    _footer(s, footer, n)
    _note(s, _notes_decisions(decs))


def _fc_gaps(prs, plan, footer, n):
    s = _new(prs, T.dark)
    _headline(s, "Next steps", dark=True, h=0.9)
    steps = plan.get("next_steps") or []
    k = max(len(steps), 1)
    gap = 0.3
    cw = (CW - gap * (k - 1)) / k
    for i, t in enumerate(steps):
        x = MX + i * (cw + gap)
        _box(s, x, 1.6, cw, BOTTOM - 1.6, fill=T.dark_card, radius=T.radius)
        _text(s, x + 0.3, 1.9, cw - 0.6, 0.9, [{"t": str(i + 1), "size": 36, "bold": True, "head": True, "color": T.accent_light}])
        _text(s, x + 0.3, 2.9, cw - 0.6, BOTTOM - 3.1, [{"t": _words(t, 26), "size": 15, "color": T.dark_ink, "spacing": 1.05}])
    _footer(s, footer, n, dark=True)
    _note(s, _notes_gaps(plan))


SLIDES = {
    "classic": dict(title=_classic_title, glance=_classic_glance, evidence=_classic_evidence, decisions=_classic_decisions, gaps=_classic_gaps),
    "editorial": dict(title=_ed_title, glance=_ed_glance, evidence=_ed_evidence, decisions=_ed_decisions, gaps=_ed_gaps),
    "split": dict(title=_sp_title, glance=_sp_glance, evidence=_sp_evidence, decisions=_sp_decisions, gaps=_sp_gaps),
    "focus": dict(title=_fc_title, glance=_fc_glance, evidence=_fc_evidence, decisions=_fc_decisions, gaps=_fc_gaps),
}


# ================================================================== build


def build_pptx(payload: dict, plan: dict, filters: list | None = None, design: str = DEFAULT_DESIGN,
               palette: str = DEFAULT_PALETTE, logo: bytes | None = None) -> bytes:
    """payload: the dashboard (panels possibly recomputed under filters); plan: from deck_plan();
    design / palette: ids from DESIGNS / PALETTES (unknown ids fall back to the defaults)."""
    d, p = DESIGNS.get(design) or DESIGNS[DEFAULT_DESIGN], PALETTES.get(palette) or PALETTES[DEFAULT_PALETTE]
    t1, t2, t3 = _design.set(d), _palette.set(p), _logo.set(logo)
    try:
        return _build(payload, plan, filters)
    finally:
        _logo.reset(t3)
        _palette.reset(t2)
        _design.reset(t1)


def _build(payload: dict, plan: dict, filters: list | None) -> bytes:
    panels = payload["panels"]
    meta = payload["meta"]
    ctx = " · ".join([meta["scope_label"], *([brief._period(meta)] if meta.get("time") else []),
                      f"{compact(meta['rows'])} records", time.strftime("%d %b %Y")])
    footer = ctx
    if filters:
        footer += "  ·  Charts filtered: " + ", ".join(f.get("label") or f.get("col", "") for f in filters) + "; commentary covers the full data"
    plan = {**plan, "decisions": [d for d in plan.get("decisions") or [] if d.get("decision")]}
    evidence = [(sl, panels[sl["panel"]]) for sl in plan.get("slides") or [] if sl["panel"] in panels and not panels[sl["panel"]].get("error")]

    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(W), Inches(H)
    prs.core_properties.title = payload["story"]["headline"].get("title") or meta["scope_label"]
    prs.core_properties.subject = "Executive briefing"

    kit = SLIDES[_design.get().id]
    n = 1
    kit["title"](prs, plan, payload, ctx)
    n += 1
    kit["glance"](prs, plan, payload, brief._metrics({**payload, "panels": panels}), footer, n)
    for sl, p in evidence:
        n += 1
        kit["evidence"](prs, sl, p, footer, n)
    if plan["decisions"]:
        n += 1
        kit["decisions"](prs, plan, footer, n)
    if plan.get("next_steps"):
        n += 1
        kit["gaps"](prs, plan, footer, n)

    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
