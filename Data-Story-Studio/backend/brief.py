"""Executive summary: board-ready commentary on a built dashboard, as Markdown and PDF.

Same contract as the story: the model writes prose from the dashboard's computed facts, the number
guard drops any sentence citing a figure that isn't in them, and the metrics table is built
directly from the KPI panels (the model never types a value). Saved on the dashboard so reopening
it doesn't call the model again.
"""

import html
import re
import time

from fmt import compact, fmt_range
from insights import fact_sheet
from llm import ProviderError
from story import PRINCIPLES, _agent, allowed_numbers, guard, llm_ready

SECTIONS = (("highlights", "What happened"), ("risks", "Risks to watch"), ("opportunities", "Opportunities"),
            ("actions", "Recommended actions"))


async def executive_summary(dash: dict, regenerate: bool = False) -> dict:
    if dash.get("exec_summary") and not regenerate:
        return dash["exec_summary"]
    story, meta = dash["story"], dash["meta"]
    panels = _ordered_panels(dash)
    facts = fact_sheet(panels)
    narrative = _story_text(story)
    summary = {
        "title": story["headline"].get("title") or meta["scope_label"],
        "context": _context(dash),
        "metrics": _metrics(dash),
        "notes": _notes(dash),
        "generated": time.time(),
    }
    if not llm_ready():
        summary.update(_fallback(story))
        summary["source"] = "computed"
    else:
        try:
            summary.update(await _write(meta, facts, narrative, dash.get("low_confidence")))
            summary["source"] = "ai"
        except (ProviderError, ValueError) as err:
            print(f"[brief] executive summary failed, using computed: {err}", flush=True)
            summary.update(_fallback(story))
            summary["source"] = "computed"
            summary["notice"] = f"AI commentary unavailable ({err}); showing the computed findings."
    summary["markdown"] = to_markdown(summary)
    dash["exec_summary"] = summary
    return summary


async def _write(meta: dict, facts: str, narrative: str, low_conf: bool) -> dict:
    audience = meta.get("audience") or "senior leadership"
    prompt = f"""DATASET: {meta['scope_label']} — {meta['rows']} records
{('PERIOD: ' + _period(meta)) if meta.get('time') else ''}
{('USER GOAL: ' + meta['goal']) if meta.get('goal') else ''}
AUDIENCE: {audience}
{'NOTE: the dataset is small; keep claims modest.' if low_conf else ''}

FACTS (computed from the data; ids in brackets):
{facts}

DASHBOARD NARRATIVE ALREADY WRITTEN (figures in it are verified):
{narrative}

Write an executive summary an executive can paste into a board pack or monthly report.
Plain business English, no chart talk ("the bar chart shows"), no panel ids, no jargon.
Lead with the "so what". Each bullet one or two sentences and at most one or two figures, copied exactly from FACTS.
Phrase possible causes as hypotheses. Skip a section rather than pad it.
Return ONLY JSON:
{{
  "bottom_line": "2-3 sentences: the single most important message and why it matters",
  "highlights": [{{"heading": "3-6 words", "text": "what happened and how big"}}],
  "risks": ["0-3 risks or watch items"],
  "opportunities": ["0-3 opportunities"],
  "actions": ["2-4 concrete recommended actions, each starting with a verb"]
}}
Give 3-5 highlights, ordered by business importance."""
    out = await _agent().complete_json(PRINCIPLES, prompt, 3000)
    ok = allowed_numbers(facts, narrative, meta["rows"])
    dropped: list[str] = []

    def g(text) -> str:
        t, d = guard(str(text or ""), ok)
        dropped.extend(d)
        return t.strip()

    res = {"bottom_line": g(out.get("bottom_line"))}
    res["highlights"] = [h for h in ({"heading": g(x.get("heading")), "text": g(x.get("text"))}
                                     for x in (out.get("highlights") or [])[:6] if isinstance(x, dict)) if h["text"]]
    for key in ("risks", "opportunities", "actions"):
        res[key] = [s for s in (g(x) for x in (out.get(key) or [])[:5]) if s]
    if dropped:
        res["guarded"] = dropped
        print(f"[brief] number guard dropped {len(dropped)} sentence(s): {dropped}", flush=True)
    return res


def _ordered_panels(dash: dict) -> list[dict]:
    """Panels the story uses first (they carry the narrative), then the rest, without tables."""
    story, panels = dash["story"], dash["panels"]
    order = list(story["kpis"]) + [p for s in story["sections"] for p in s["panels"]]
    order += [p for p in panels if p not in order]
    out = []
    for pid in dict.fromkeys(order):
        p = panels.get(pid)
        if p and p.get("chart") != "table" and p.get("recipe") and not p.get("error"):
            out.append({**p, "id": pid, "score": p.get("score", 0)})
    return out[:30]


def _story_text(story: dict) -> str:
    lines = [story["headline"].get("title", ""), story["headline"].get("summary", "")]
    for s in story["sections"]:
        lines += [s.get("heading", ""), s.get("note", "")]
    for ins in story.get("insights") or []:
        lines += [ins.get(k, "") for k in ("title", "what", "significance", "why", "next")]
    lines += story.get("next_steps") or []
    return "\n".join(x for x in lines if x)


def _period(meta: dict) -> str:
    t = meta.get("time") or {}
    return fmt_range(t.get("min"), t.get("max"), "month" if t.get("grain") in ("hour", "day", "week", "month") else t.get("grain", "month"))


def _context(dash: dict) -> str:
    meta = dash["meta"]
    bits = [meta["scope_label"]]
    if meta.get("time"):
        bits.append(_period(meta))
    bits.append(f"{compact(meta['rows'])} records")
    return " · ".join(bits)


def _metrics(dash: dict) -> list[dict]:
    out = []
    for pid in dash["story"]["kpis"]:
        p = dash["panels"].get(pid)
        if not p or p.get("chart") != "kpi":
            continue
        changes = []
        if p.get("current_display") and p.get("current_period"):
            changes.append(f"{p['current_display']} in {p['current_period']}")
        for c in (p.get("compare_yoy"), p.get("compare")):
            if c and c.get("display"):
                changes.append(f"{c['display']} {c.get('label', '')}".strip())
        out.append({"label": p.get("measure_label") or p.get("title"), "value": p.get("display", "—"),
                    "basis": p.get("basis", ""), "change": "; ".join(changes)})
    return out


def _notes(dash: dict) -> list[str]:
    meta, notes = dash["meta"], []
    files = ", ".join(f["name"] for f in meta.get("files") or [])
    if files:
        notes.append(f"Source: {files}" + (f", joined on {', '.join(j['on'] for j in meta['joins'])}" if meta.get("joins") else "") + ".")
    if dash.get("low_confidence"):
        notes.append("The dataset is small, so treat these findings as indicative rather than conclusive.")
    for pid in dash["story"]["kpis"]:
        for cav in (dash["panels"].get(pid) or {}).get("caveats") or []:
            if cav not in notes:
                notes.append(cav)
    notes.append("All figures are computed directly from the data; interpretations are hypotheses to confirm.")
    return notes


def _fallback(story: dict) -> dict:
    """No model: the dashboard's own computed findings, arranged in the same shape."""
    hl = []
    for s in story["sections"]:
        if s.get("heading") and s["heading"] != "More views":
            hl.append({"heading": "", "text": s["heading"].rstrip(".") + "." + (" " + s["note"] if s.get("note") else "")})
    return {
        "bottom_line": story["headline"].get("summary") or story["headline"].get("title", ""),
        "highlights": hl[:5],
        "risks": [],
        "opportunities": [],
        "actions": list(story.get("next_steps") or []),
    }


# ------------------------------------------------------------------ rendering


def to_markdown(s: dict) -> str:
    md = [f"# Executive summary: {s['title']}", "", f"*{s['context']} · prepared {time.strftime('%d %b %Y', time.localtime(s['generated']))}*", ""]
    if s.get("bottom_line"):
        md += [f"**Bottom line.** {s['bottom_line']}", ""]
    if s["metrics"]:
        md += ["## Key metrics", "", "| Metric | Value | Recent movement |", "|---|---:|---|"]
        md += [f"| {_cell(m['label'])} | {_cell(m['value'])} | {_cell(m['change'] or '—')} |" for m in s["metrics"]]
        md.append("")
    for key, heading in SECTIONS:
        items = s.get(key) or []
        if not items:
            continue
        md += [f"## {heading}", ""]
        for i, it in enumerate(items, 1):
            if isinstance(it, dict):
                md.append(f"- **{it['heading']}.** {it['text']}" if it.get("heading") else f"- {it['text']}")
            else:
                md.append(f"{i}. {it}" if key == "actions" else f"- {it}")
        md.append("")
    if s.get("notes"):
        md += ["## About the data", ""] + [f"- {n}" for n in s["notes"]] + [""]
    return "\n".join(md)


def _cell(v) -> str:
    return str(v).replace("|", "\\|")


def to_html(s: dict) -> str:
    e = html.escape
    parts = [f"<div class='eyebrow'>Executive summary</div><h1>{e(s['title'])}</h1>",
             f"<p class='meta'>{e(s['context'])} · prepared {time.strftime('%d %b %Y', time.localtime(s['generated']))}</p>"]
    if s.get("bottom_line"):
        parts.append(f"<div class='bottom'><b>Bottom line.</b> {e(s['bottom_line'])}</div>")
    if s["metrics"]:
        rows = "".join(f"<tr><td>{e(m['label'])}</td><td class='num'>{e(m['value'])}</td><td>{e(m['change'] or '—')}</td></tr>"
                       for m in s["metrics"])
        parts.append(f"<h2>Key metrics</h2><table><thead><tr><th>Metric</th><th class='num'>Value</th><th>Recent movement</th></tr></thead><tbody>{rows}</tbody></table>")
    for key, heading in SECTIONS:
        items = s.get(key) or []
        if not items:
            continue
        tag = "ol" if key == "actions" else "ul"
        lis = "".join(
            f"<li><b>{e(it['heading'])}.</b> {e(it['text'])}</li>" if isinstance(it, dict) and it.get("heading")
            else f"<li>{e(it['text'] if isinstance(it, dict) else it)}</li>" for it in items)
        parts.append(f"<h2>{e(heading)}</h2><{tag}>{lis}</{tag}>")
    if s.get("notes"):
        parts.append("<h2>About the data</h2><ul class='notes'>" + "".join(f"<li>{e(n)}</li>" for n in s["notes"]) + "</ul>")
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(s['title'])}</title>
<style>
@page {{ size: A4; margin: 18mm 18mm 16mm; }}
body {{ font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; color: #1b1b18; font-size: 10.5pt; line-height: 1.5; margin: 0; }}
.eyebrow {{ font-size: 8.5pt; letter-spacing: .08em; text-transform: uppercase; color: #7a786f; font-weight: 600; }}
h1 {{ font-size: 19pt; line-height: 1.2; margin: 4pt 0 4pt; letter-spacing: -.01em; }}
.meta {{ color: #7a786f; font-size: 9pt; margin: 0 0 14pt; }}
.bottom {{ background: #f4f3ee; border-left: 3pt solid #1b1b18; padding: 10pt 12pt; margin: 0 0 6pt; font-size: 11pt; }}
h2 {{ font-size: 11.5pt; margin: 16pt 0 6pt; padding-bottom: 3pt; border-bottom: 1px solid #e3e1d9; }}
ul, ol {{ margin: 0; padding-left: 16pt; }} li {{ margin: 0 0 5pt; }}
table {{ width: 100%; border-collapse: collapse; font-size: 9.5pt; }}
th, td {{ text-align: left; padding: 5pt 6pt; border-bottom: 1px solid #e3e1d9; vertical-align: top; }}
th {{ color: #55534c; font-weight: 600; }} .num {{ text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }}
td.num {{ font-weight: 600; }}
.notes {{ color: #55534c; font-size: 9pt; }}
h2, li, tr {{ break-inside: avoid; }}
</style></head><body>{''.join(parts)}</body></html>"""


def filename(s: dict, ext: str) -> str:
    base = re.sub(r"[^A-Za-z0-9]+", "-", s["title"]).strip("-")[:50] or "summary"
    return f"Executive-summary-{base}-{time.strftime('%Y%m%d')}.{ext}"


