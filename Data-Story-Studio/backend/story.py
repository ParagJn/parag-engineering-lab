"""LLM layer (IBM ICA): story composition, Q&A and redraw requests.

Contract with the model
  - it receives the schema and a fact sheet where every number is already formatted
  - it returns structure (which panels, order, headings) and prose that cites those facts
  - a number guard drops any sentence containing a figure that isn't in the facts
  - any SQL it writes is validated as a single read-only SELECT and run in a sandbox
Without ICA configured everything still works deterministically; only prose/Q&A degrade.
"""

import json
import re

import maps
from config import get_settings
from fmt import fmt_value, number_variants
from insights import fact_sheet
from llm import ProviderError, build_agent
from panels import CHARTS, Ctx, RecipeError, compile_panel, describe_columns
from workspace import QueryError, validate_select

NUM_RE = re.compile(r"(?<![A-Za-z_])[-+]?\$?\d[\d,]*(?:\.\d+)?")

PRINCIPLES = """You are an expert data analyst, business storyteller and dashboard designer.
Rules you never break:
- Never invent numbers. Only use figures that appear in the FACTS (copy them exactly as written).
- Distinguish observation from interpretation. Phrase possible reasons as hypotheses ("may", "could indicate").
- Never claim causation from correlation.
- Headlines are insights, not labels: "Three regions account for most of the decline", not "Regional performance".
- Be concise. Business audience. No jargon like 'r-squared' unless asked.
- You are a viewer of the data as given, not a data profiler. Report what the data shows at face value, in a confident
  business tone. Never call a result a data error, join issue, bug or quality problem, and never tell the reader to fix
  or validate the data in headlines, headings, summaries, insights or next steps.
- If a figure looks unusually extreme (e.g. a very high rate or a value with no variation), still report it as the data
  shows it, and mention it only in the separate "anomaly_notes" field: one short, neutral line suggesting a closer look
  at how the figure correlates with the rest of the data."""


def _agent():
    return build_agent(get_settings(), "dashboard")


def llm_ready() -> bool:
    return get_settings().llm_configured


# ------------------------------------------------------------------ number guard


def allowed_numbers(*texts_or_values) -> set[str]:
    ok: set[str] = set()
    for item in texts_or_values:
        if isinstance(item, (int, float)):
            ok |= number_variants(float(item))
        elif isinstance(item, str):
            for m in NUM_RE.finditer(item):
                ok.add(m.group(0).lstrip("+-$").replace(",", ""))
    # small integers are fine in prose ("top 3", "2 regions")
    ok |= {str(i) for i in range(0, 13)}
    return ok


def guard(text: str, ok: set[str]) -> tuple[str, list[str]]:
    """Drop sentences that cite a number not present in the computed facts."""
    if not text:
        return text, []
    kept, dropped = [], []
    for sent in re.split(r"(?<=[.!?])\s+", text.strip()):
        bad = [m.group(0) for m in NUM_RE.finditer(sent)
               if m.group(0).lstrip("+-$").replace(",", "") not in ok and not _is_year(m.group(0))]
        (dropped if bad else kept).append(sent)
    return " ".join(kept), dropped


def _is_year(s: str) -> bool:
    return bool(re.fullmatch(r"(19|20)\d\d", s))


# ------------------------------------------------------------------ setup questions


async def setup_brief(state: dict) -> dict:
    """Ask the LLM to phrase a short description of each file and likely goals (no decisions)."""
    if not llm_ready():
        return {}
    tables = []
    for t, cols in state["profiles"].items():
        desc = ", ".join(f"{c['label']} ({c['role']})" for c in cols[:30])
        tables.append(f"{t}: {state['rows'][t]} rows; columns: {desc}")
    prompt = ("Data files uploaded:\n" + "\n".join(tables) +
              "\n\nReturn JSON: {\"files\": {\"<table>\": \"one sentence on what this file appears to contain\"},"
              " \"purpose\": \"one sentence guess of what the data is for\","
              " \"goal_suggestions\": [\"3 short questions a dashboard could answer\"]}")
    try:
        return await _agent().complete_json(PRINCIPLES, prompt, 1500)
    except (ProviderError, ValueError) as err:
        print(f"[story] setup_brief failed: {err}", flush=True)
        return {}


# ------------------------------------------------------------------ compose


async def compose(scope: dict, cands: list[dict], default: dict, goal: str, audience: str, low_confidence: bool,
                  purpose: str = "") -> dict:
    """Pick and order panels into a narrative. Falls back to the deterministic default."""
    story = json.loads(json.dumps(default))
    story["source"] = "default"
    if not llm_ready():
        story["headline"]["summary"] = _fallback_summary(cands, default)
        story["headline"]["highlights"] = _fallback_highlights(cands, default)
        story["notice"] = "AI narrative is off (IBM ICA not configured) — titles and figures are computed directly from the data."
        return story
    ids = {c["id"] for c in cands}
    facts = fact_sheet(cands)
    sl = scope.get("slice")
    map_ids = [c["id"] for c in cands if c["chart"] == "map"]
    map_rule = (f"Include the map panel {map_ids[0]} in a section: this data has places and readers expect the geography." if map_ids else "")
    prompt = f"""DATASET: {scope['label']} — {scope['rows']} records
{('ABOUT THE DATA: ' + purpose) if purpose else ''}
{f"SLICE: only rows where {sl['label']} = {sl['value']}; every value column measures {sl['value']}." if sl else ''}
{('USER GOAL: ' + goal) if goal else 'USER GOAL: not given — find the most important story.'}
{('AUDIENCE: ' + audience) if audience else ''}
{'NOTE: the dataset is small; keep claims modest.' if low_confidence else ''}

COLUMNS:
{describe_columns(scope)}

FACTS (candidate panels already computed; ids in brackets):
{facts}

Design the dashboard as a story. Return ONLY JSON:
{{
  "headline": {{"title": "the dashboard's hero title: a short editorial name, 2-6 words, like a magazine cover line. Name the business or subject and give it an angle, e.g. 'Brightleaf Coffee: Growth, Delivered' or 'The Rush Hour Ledger'. NO digits, no full sentence, no trailing full stop",
                "finding": "the single most important finding as one sentence, 8-18 words, with its key number copied from FACTS",
                "summary": "the opening paragraph, 2-3 sentences, plain prose: scope (record count and period), the headline measure against its baseline or overall figure, and the most recent movement versus the same period a year earlier (or the prior period) when FACTS has it. Name segments and figures; no hedging here",
                "highlights": [{{"lead": "2-5 word label naming the pattern, e.g. 'Concentration' or 'Where it leads'", "text": "ONE sentence, max 26 words, one finding with its figures copied from FACTS: a concentration, a leader, a gap between groups, or an exception"}}],
                "reading": "ONE hedged sentence on what it may mean or what to check (may / could / one reading is). A hypothesis, never a cause, never a recommendation",
                "panel": "<hero panel id>"}},
  "kpis": ["2-4 kpi panel ids"],
  "sections": [{{"role": "evidence|change|drivers|patterns|detail", "heading": "insight-driven heading",
                 "panels": ["panel ids"], "note": "optional one-sentence takeaway"}}],
  "panel_titles": {{"<panel id>": "optional sharper title using only that panel's facts"}},
  "insights": [{{"title": "short", "what": "what happened", "significance": "how big",
                "evidence": "which panel/figures", "why": "why it might matter (hypothesis)",
                "next": "what to investigate or do next", "panels": ["ids"], "kind": "observation|hypothesis|recommendation"}}],
  "next_steps": ["2-3 concrete things to investigate"],
  "anomaly_notes": ["0-2 short neutral lines on figures that look unusually extreme; empty if none"]
}}
Use 4-7 non-KPI panels in total, the most significant first, no two panels telling the same story.
{map_rule}
Opening commentary: "summary" is the paragraph, "highlights" are 3-4 bullets that each add a NEW fact (never repeat the paragraph or the finding), ordered by importance and covering different panels: concentration or share, leaders and laggards, a comparison between groups, and one exception or recent turn. Every figure is copied exactly from FACTS.
KPIs: keep the cards that measure what the USER GOAL asks about; do not swap them for generic totals.
Prefer the user's goal when choosing. Skip weak findings rather than forcing them.
If the USER GOAL asks "which <places/groups> ...", the hero finding and summary must NAME the leading groups with their figures from the RANKING panels; never defer that comparison to next steps.
When a panel reports that a small share of records holds most of a total ("top 10% hold ..."), lead with that share, not the median.
Treat ordinal tiers (price range, grade) as groups to compare; report the gap between tiers, not a correlation coefficient. Mention unrated or missing records once, as a data note, never as a finding.
Insights: 3-5 items, each specific to a panel's figures; the "why" and "next" fields must be concrete, not generic."""
    try:
        out = await _agent().complete_json(PRINCIPLES, prompt, 10000)
    except (ProviderError, ValueError) as err:
        print(f"[story] compose failed, using default: {err}", flush=True)
        story["headline"]["summary"] = _fallback_summary(cands, default)
        story["headline"]["highlights"] = _fallback_highlights(cands, default)
        story["notice"] = f"AI narrative unavailable ({err}); showing the computed story."
        return story

    ok = allowed_numbers(facts, scope["rows"])
    dropped: list[str] = []

    def g(text: str) -> str:
        t, d = guard(text or "", ok)
        dropped.extend(d)
        return t

    hl = out.get("headline") or {}
    hero = hl.get("panel") if hl.get("panel") in ids else default["headline"]["panel"]
    title = g(hl.get("title", ""))
    finding = g(hl.get("finding", ""))
    if not title or re.search(r"\d", title) or len(title.split()) > 9:
        # not a name (a sentence or a figure): show it as the finding and let the dashboard name fall back
        finding = finding or title
        title = ""
    story["headline"] = {"title": title or default["headline"]["title"], "finding": finding,
                         "summary": g(hl.get("summary", "")), "panel": hero,
                         "highlights": _highlights(hl.get("highlights"), g), "reading": g(hl.get("reading", ""))}
    kpis = [k for k in out.get("kpis") or [] if k in ids and _by_id(cands, k)["chart"] == "kpi"][:4]
    story["kpis"] = kpis or default["kpis"]
    sections, used = [], set(story["kpis"])
    for s in out.get("sections") or []:
        pids = [p for p in s.get("panels") or [] if p in ids and p not in used and _by_id(cands, p)["chart"] != "kpi"]
        if not pids:
            continue
        used |= set(pids)
        sections.append({"role": s.get("role", "evidence"), "heading": g(s.get("heading", "")) or "What the data shows",
                         "panels": pids, "note": g(s.get("note", ""))})
    if sections:
        if hero and hero not in used and _by_id(cands, hero)["chart"] != "kpi":
            sections[0]["panels"].insert(0, hero)
        story["sections"] = sections
    _keep_map(story, cands)
    story["panel_titles"] = {}
    for pid, t in (out.get("panel_titles") or {}).items():
        if pid in ids:
            gt = g(t)
            if gt:
                story["panel_titles"][pid] = gt
    story["insights"] = []
    for ins in (out.get("insights") or [])[:6]:
        clean = {k: g(ins.get(k, "")) for k in ("title", "what", "significance", "evidence", "why", "next")}
        if not clean["title"] or not clean["what"]:
            continue
        clean["panels"] = [p for p in ins.get("panels") or [] if p in ids]
        clean["kind"] = ins.get("kind") if ins.get("kind") in ("observation", "hypothesis", "recommendation") else "observation"
        story["insights"].append(clean)
    story["next_steps"] = [s for s in (g(x) for x in out.get("next_steps") or []) if s][:4]
    story["anomaly_notes"] = [s for s in (g(x) for x in out.get("anomaly_notes") or []) if s][:2]
    story["source"] = "ai"
    if dropped:
        story["guarded"] = dropped
        print(f"[story] number guard dropped {len(dropped)} sentence(s): {dropped}", flush=True)
    return story


def _keep_map(story: dict, cands: list[dict]) -> None:
    """The model may leave the map out of its layout; when the data has places it still belongs on the dashboard."""
    shown = {p for s in story["sections"] for p in s["panels"]} | set(story["kpis"])
    best = next((c for c in sorted(cands, key=lambda c: -c["score"]) if c["chart"] == "map"), None)
    if not best or best["id"] in shown:
        return
    dim = best["recipe"]["dim"]
    if any(c["id"] in shown and c["recipe"]["kind"] == "breakdown" and c["recipe"].get("dim") == dim for c in cands):
        return  # bars of the same places are already there
    roomy = next((s for s in story["sections"][1:] if len(s["panels"]) < 2), None)
    if roomy:
        roomy["panels"].append(best["id"])
    else:
        story["sections"].append({"role": "patterns", "heading": best["title"], "panels": [best["id"]], "note": ""})


def _by_id(cands: list[dict], pid: str) -> dict:
    return next(c for c in cands if c["id"] == pid)


def _highlights(raw, g) -> list[dict]:
    """Bullets for the opening commentary: a short lead and one guarded sentence each."""
    out = []
    for h in raw or []:
        if isinstance(h, str):
            h = {"lead": "", "text": h}
        if not isinstance(h, dict):
            continue
        text = g(str(h.get("text", ""))).strip()
        if text:
            out.append({"lead": " ".join(str(h.get("lead", "")).split()[:6]).strip(" :.-"), "text": text})
    return out[:4]


def _fallback_summary(cands: list[dict], default: dict) -> str:
    hero = default["headline"].get("panel")
    titles = [_by_id(cands, pid)["title"] for sec in default["sections"] for pid in sec["panels"]
              if pid != hero and _by_id(cands, pid)["chart"] != "table"]
    return " ".join(f"{t}." for t in titles[:2])


def _fallback_highlights(cands: list[dict], default: dict) -> list[dict]:
    hero = default["headline"].get("panel")
    out = []
    for sec in default["sections"]:
        for pid in sec["panels"]:
            c = _by_id(cands, pid)
            if pid != hero and c["chart"] != "table":
                out.append({"lead": "", "text": c["title"].rstrip(".") + "."})
    return out[2:6]


# ------------------------------------------------------------------ Q&A


ASK_SCHEMA = """Return ONLY JSON:
{
  "sql": "one DuckDB SELECT over the table %(view)s that computes the answer (aggregate; no more than 200 rows), or null if the question can't be answered from these columns",
  "chart": "bar|column|line|area|scatter|table|kpi",
  "enc": {"x": "col", "y": "col", "series": "optional col", "cat": "col", "value": "col"},
  "title": "insight-style title WITHOUT numbers (numbers come from the result)",
  "cannot_answer": "if sql is null: explain briefly which data would be needed"
}
DuckDB tips: date_trunc('month', col), strftime(col, '%%Y-%%m'), isodow(col), hour(col), median(), quantile_cont(col, 0.9), corr(a,b),
count(*) FILTER (WHERE ...), QUALIFY row_number() OVER (...) . Quote column names with double quotes. Never write to tables."""


async def ask(ds, scope: dict, question: str, history: list[dict], filters: list) -> dict:
    if not llm_ready():
        return {"answer": "Questions need IBM ICA to be configured (IBM_ICA_ENDPOINT / IBM_ICA_API_KEY in .env).",
                "kind": "error"}
    ctx = Ctx(ds, scope, filters)
    hist = "\n".join(f"{h['role']}: {h['text']}" for h in history[-6:])
    plan_prompt = f"""TABLE {scope['view']} ({scope['rows']} rows) — {scope['label']}{f" (only {scope['slice']['label']} = {scope['slice']['value']})" if scope.get('slice') else ''}
COLUMNS:
{describe_columns(scope)}
{('Active dashboard filters (already applied): ' + json.dumps(filters)) if filters else ''}
RECENT CONVERSATION:
{hist or '(none)'}

QUESTION: {question}

{ASK_SCHEMA % {'view': scope['view']}}"""
    agent = _agent()
    try:
        plan = await agent.complete_json(PRINCIPLES, plan_prompt, 2500)
    except (ProviderError, ValueError) as err:
        return {"answer": f"I couldn't reach the AI service: {err}", "kind": "error"}
    if not plan.get("sql"):
        return {"answer": plan.get("cannot_answer") or "That can't be answered from the columns in this data.", "kind": "cannot"}

    panel, error = None, None
    for attempt in range(2):
        try:
            validate_select(ds.con, plan["sql"])
            panel = compile_panel(ctx, {"kind": "sql", "sql": plan["sql"], "chart": plan.get("chart"),
                                        "enc": plan.get("enc"), "title": plan.get("title")})
            break
        except (QueryError, RecipeError) as err:
            error = str(err)
            if attempt == 1:
                break
            try:
                plan = await agent.complete_json(
                    PRINCIPLES, plan_prompt + f"\n\nYour SQL failed: {error}\nSQL was: {plan['sql']}\nFix it.", 2500)
            except (ProviderError, ValueError):
                break
    if panel is None:
        return {"answer": f"I couldn't compute that reliably (query error: {error}).", "kind": "error",
                "sql": plan.get("sql")}

    rows = panel["data"]["rows"][:60]
    result_txt = json.dumps({"columns": panel["data"]["columns"], "rows": rows,
                             "truncated": panel["data"]["truncated"] or len(panel["data"]["rows"]) > 60}, default=str)
    explain_prompt = f"""QUESTION: {question}
QUERY RESULT (the only facts you may use):
{result_txt}

Answer in 2-4 sentences for a business reader. Quote figures exactly as they appear in the result (you may round
to 1 decimal or add thousands separators). Mark interpretations as hypotheses. If the result is empty, say so.
Return ONLY JSON: {{"answer": "...", "title": "insight-style chart title, may include figures from the result", "follow_ups": ["2 short follow-up questions"]}}"""
    try:
        exp = await agent.complete_json(PRINCIPLES, explain_prompt, 1500)
    except (ProviderError, ValueError) as err:
        exp = {"answer": f"Here is the result (explanation unavailable: {err}).", "title": panel["title"]}
    ok = allowed_numbers(result_txt, *[v for r in rows for v in r if isinstance(v, (int, float))])
    for r in rows:
        for v in r:
            if isinstance(v, (int, float)):
                ok |= {fmt_value(v).replace(",", "")}
    answer, dropped = guard(exp.get("answer", ""), ok)
    title, _ = guard(exp.get("title") or panel["title"], ok)
    panel["title"] = title or plan.get("title") or "Answer"
    panel["subtitle"] = f"Answer to: {question}"
    return {"answer": answer or "The result is shown below.", "kind": "answer", "panel": panel,
            "follow_ups": exp.get("follow_ups") or [], "guarded": dropped}


# ------------------------------------------------------------------ redraw


async def redraw(ds, scope: dict, panel: dict, instruction: str, filters: list) -> dict:
    """Rework one panel: the LLM edits the recipe (preferred) or writes SQL; we recompute."""
    ctx = Ctx(ds, scope, filters)
    recipe = panel["recipe"]
    quick = _quick_redraw(recipe, instruction, panel)
    if quick:
        return compile_panel(ctx, quick)
    if not llm_ready():
        raise RecipeError("Free-form redraw needs IBM ICA. Try a chart-type switch instead.")
    places = [g["dim"] for g in maps.detect(ds, scope)]
    map_kind = (f"- map {{measure, dim: one of {places}, chart: {CHARTS['map']}}} (choropleth of places)\n" if places else "")
    prompt = f"""TABLE {scope['view']} — {scope['label']}{f" (only {scope['slice']['label']} = {scope['slice']['value']})" if scope.get('slice') else ''}
COLUMNS:
{describe_columns(scope)}

CURRENT PANEL
title: {panel['title']}
recipe: {json.dumps(recipe)}

RECIPE KINDS (fields):
- kpi {{measure}}
- timeseries {{measure, grain?: hour|day|week|month|quarter|year, split?: dimension, top_n?, chart: {CHARTS['timeseries'] + CHARTS['timeseries_split']}}}
- breakdown {{measure, dim, top_n?, sort?: "value"|"label", chart: {CHARTS['breakdown']}}}
- change {{measure, dim, grain?, compare?: "previous"|"yoy", chart: {CHARTS['change']}}}
- heatmap {{measure, x: {{dim}}|{{part: hour|dow|month}}, y: same, chart: heatmap|sankey}}
{map_kind}- scatter {{x, y, color?}}
- distribution {{measure, bins?}}
- table {{columns, sort?, asc?, limit?}}
- sql {{sql: one SELECT over {scope['view']}, chart: {CHARTS['sql']}, enc: {{x,y,series,cat,value}}, title}}
measure = a column name or "__records" (count of records).

USER REQUEST: {instruction}

Return ONLY JSON: {{"recipe": {{...}}}} — prefer a standard kind; use "sql" only if no kind fits."""
    try:
        out = await _agent().complete_json(PRINCIPLES, prompt, 2500)
    except (ProviderError, ValueError) as err:
        raise RecipeError(f"AI service unavailable: {err}") from err
    new = out.get("recipe") or {}
    try:
        return compile_panel(ctx, new)
    except (RecipeError, QueryError) as err:
        raise RecipeError(f"Couldn't redraw that way: {err}") from err


def _quick_redraw(recipe: dict, instruction: str, panel: dict) -> dict | None:
    """Handle obvious requests without a model round-trip."""
    text = instruction.lower().strip()
    for ch in panel.get("allowed_charts") or []:
        if text in (ch, f"as {ch}", f"{ch} chart", f"show as {ch}", f"switch to {ch}", ch.replace("_", " ")):
            return {**recipe, "chart": ch}
    m = re.fullmatch(r"(by )?(hour|day|week|month|quarter|year)(ly)?", text.replace("daily", "day").replace("monthly", "month")
                     .replace("weekly", "week").replace("quarterly", "quarter").replace("yearly", "year"))
    if m and recipe.get("kind") in ("timeseries", "kpi", "change"):
        return {**recipe, "grain": m.group(2)}
    m = re.fullmatch(r"top (\d+)", text)
    if m and recipe.get("kind") in ("breakdown", "change", "timeseries"):
        return {**recipe, "top_n": int(m.group(1))}
    return None
