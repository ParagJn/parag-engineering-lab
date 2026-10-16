"""Insight discovery: compute candidate panels, score them by significance, pick the story.

Deterministic — the same data always gives the same candidates, scores and default layout.
The LLM (story.py) may re-order, re-title within the facts, or drop panels, but cannot add
numbers that weren't computed here.
"""

import itertools
import json

from fmt import compact, fmt_change, fmt_pct, fmt_value
from model import BOUND_NAME, dimensions, measures
from panels import Ctx, RecipeError, compile_panel
from profile import q

MAX_CANDIDATES = 26


def discover(ds, scope: dict, goal: str = "") -> dict:
    ctx = Ctx(ds, scope)
    ms = list(ctx.measures.values())
    ds_ = dimensions(scope)
    primary = ms[0]
    t = scope.get("time")
    cands: list[dict] = []

    def add(recipe: dict, base_score: float):
        try:
            p = compile_panel(ctx, recipe)
        except (RecipeError, Exception) as err:  # a failed candidate never blocks the dashboard
            print(f"[insights] skipped {recipe}: {err}", flush=True)
            return
        if not p.get("data", {"rows": [1]}).get("rows") and p["chart"] != "kpi":
            return
        p["score"] = round(base_score * _significance(p), 3)
        p["id"] = f"p{len(cands) + 1}"
        cands.append(p)

    # KPIs: primary, record count, up to 2 more measures
    # KPI row: the headline measure, the record count, then quality-style averages/rates for contrast
    rest = [m for m in ms if m is not primary and not m.get("lookup")]
    records = next((m for m in rest if m["agg"] == "count"), None)
    contrast = [m for m in rest if m["kind"] == "avg" and not BOUND_NAME.search(m["name"])]
    others = [m for m in rest if m is not records and m not in contrast and not BOUND_NAME.search(m["name"])]
    kpi_ms = [primary] + ([records] if records else []) + (contrast + others)[: 3 - (1 if records else 0)]
    for m in kpi_ms:
        add({"kind": "kpi", "measure": m["name"]}, 1.0)

    if t:
        for m in ms[:3]:
            add({"kind": "timeseries", "measure": m["name"]}, 1.0 if m is primary else 0.7)
        for d in ds_[:3]:
            if d["distinct"] <= 30:
                add({"kind": "timeseries", "measure": primary["name"], "split": d["name"], "top_n": 5,
                     "chart": "stacked_area" if primary["agg"] in ("sum", "count") else "line"}, 0.8)
        for d in ds_[:3]:
            add({"kind": "change", "measure": primary["name"], "dim": d["name"]}, 0.9)
        if t.get("has_hour"):
            add({"kind": "heatmap", "measure": primary["name"], "x": {"part": "hour"}, "y": {"part": "dow"}}, 0.85)
        elif t.get("span_days", 0) >= 28:
            if t.get("span_days", 0) >= 365 and t["grain"] in ("month", "quarter", "week"):
                add({"kind": "heatmap", "measure": primary["name"], "x": {"part": "month"},
                     "y": {"dim": ds_[0]["name"]} if ds_ else {"part": "dow"}}, 0.6)
            else:
                add({"kind": "heatmap", "measure": primary["name"], "x": {"part": "dow"},
                     "y": {"dim": ds_[0]["name"]} if ds_ else {"part": "month"}}, 0.6)

    for d in ds_[:4]:
        add({"kind": "breakdown", "measure": primary["name"], "dim": d["name"],
             "chart": "treemap" if d["distinct"] > 15 and primary["agg"] in ("sum", "count") else "bar"}, 0.85)
    avg_ms = [m for m in ms if m["kind"] == "avg" and not BOUND_NAME.search(m["name"])][:2]
    for m in avg_ms:
        for d in ds_[:2]:
            add({"kind": "breakdown", "measure": m["name"], "dim": d["name"]}, 0.75)
    if len(ds_) >= 2 and ds_[0]["distinct"] <= 15 and ds_[1]["distinct"] <= 15:
        add({"kind": "heatmap", "measure": primary["name"], "x": {"dim": ds_[0]["name"]}, "y": {"dim": ds_[1]["name"]}}, 0.55)

    numeric = [m for m in ms if m["agg"] != "count" and m["agg"] != "rate"]
    numeric = [m for m in numeric if not m.get("lookup")] + [m for m in numeric if m.get("lookup")]
    pairs = []
    for a, b in itertools.combinations(numeric[:6], 2):
        if BOUND_NAME.search(a["name"]) or BOUND_NAME.search(b["name"]):
            continue  # an estimate and its own interval bounds always move together
        r = ds.scalar(f"SELECT corr({q(a['name'])}, {q(b['name'])}) FROM {q(scope['view'])}")
        if r is not None and r == r:
            pairs.append((abs(r), a, b))
    pairs.sort(key=lambda p: -p[0])
    for r, a, b in pairs[:2]:
        if r >= 0.3:
            add({"kind": "scatter", "x": a["name"], "y": b["name"],
                 "color": ds_[0]["name"] if ds_ and ds_[0]["distinct"] <= 3 else None}, 0.7)
    for m in [m for m in numeric if not m.get("lookup")][:2]:
        add({"kind": "distribution", "measure": m["name"]}, 0.5)

    sort_col = next((m["name"] for m in ms if m["agg"] != "count"), None)
    cols = [c["name"] for c in scope["columns"] if c["role"] in ("id", "time", "dimension", "measure", "flag")][:9]
    add({"kind": "table", "columns": cols, "sort": sort_col, "limit": 100}, 0.2)

    cands = cands[: MAX_CANDIDATES + 8]
    return {"candidates": cands, "default": default_story(scope, cands, primary)}


def _significance(p: dict) -> float:
    """Business significance multiplier from the panel's computed stats (0.3 .. 2.0)."""
    s = p.get("stats") or {}
    ch = p["chart"]
    if ch == "kpi":
        c = p.get("compare") or {}
        return 1.0 + min(abs(c.get("rel") or 0), 0.8)
    if p["recipe"]["kind"] == "timeseries" and not p["recipe"].get("split"):
        trend = s.get("trend")
        base = {"up": 1.4, "down": 1.5, "flat": 0.8, "volatile": 0.9}.get(trend, 0.6)
        base += 0.2 * len(s.get("anomalies") or [])
        base += min(abs(s.get("fit_change") or 0), 1.0) * 0.5 * (s.get("r2") or 0)
        return min(base, 2.0)
    if p["recipe"]["kind"] == "timeseries":
        best = s.get("best")
        worst = s.get("worst")
        spread = (best[3] - worst[3]) if best and worst else 0
        return min(0.6 + abs(spread), 1.8)
    if p["recipe"]["kind"] == "change":
        rel = abs(s.get("rel") or 0)
        drv = abs(s.get("driver_share") or 0)
        return min(0.6 + rel * 2 + (0.4 if 0.4 <= drv <= 1 else 0), 2.0)
    if p["recipe"]["kind"] == "breakdown":
        if "top_share" in s:
            return 0.6 + min(s["top_share"], 0.8) + (0.2 if s.get("top3_share", 0) >= 0.6 else 0)
        spread = s.get("spread") or 1
        return min(0.5 + (spread - 1) * 2, 1.8)
    if ch == "heatmap" or ch == "sankey":
        ratio = s.get("ratio") or 1
        return min(0.5 + (ratio - 1) * 0.4, 1.7)
    if ch == "scatter":
        return 0.4 + abs(s.get("r") or 0) * 1.4
    if ch == "histogram":
        skew = (s.get("p90") or 0) / (s.get("median") or 1) if s.get("median") else 1
        return 0.5 + min(max(skew - 1.5, 0), 1.0) * 0.6 + (0.2 if s.get("outliers") else 0)
    return 1.0


def default_story(scope: dict, cands: list[dict], primary: dict) -> dict:
    """Deterministic fallback layout (also the starting point the LLM edits)."""
    kpis = [c for c in cands if c["chart"] == "kpi"][:4]
    rest = sorted([c for c in cands if c["chart"] not in ("kpi", "table")], key=lambda c: -c["score"])
    # variety: one plain trend, at most two of any chart family, no repeated dimension per kind
    picked, seen, families = [], set(), {}
    for c in rest:
        r = c["recipe"]
        if r["kind"] == "timeseries" and not r.get("split"):
            key = ("trend",)
        else:
            key = (r["kind"], r.get("dim") or r.get("split") or json.dumps(r.get("x")) or r.get("measure"))
        fam = r["kind"] + ("_split" if r.get("split") else "")
        if key in seen or families.get(fam, 0) >= 2:
            continue
        seen.add(key)
        families[fam] = families.get(fam, 0) + 1
        picked.append(c)
        if len(picked) >= 6:
            break
    table = next((c for c in cands if c["chart"] == "table"), None)
    hero = picked[0] if picked else (kpis[0] if kpis else None)
    sections = []
    if picked:
        sections.append({"role": "evidence", "heading": "What the data shows", "panels": [p["id"] for p in picked[:2]]})
    if len(picked) > 2:
        sections.append({"role": "drivers", "heading": "Where it comes from", "panels": [p["id"] for p in picked[2:4]]})
    if len(picked) > 4:
        sections.append({"role": "detail", "heading": "Patterns worth a closer look", "panels": [p["id"] for p in picked[4:]]})
    if table:
        sections.append({"role": "detail", "heading": "The records behind it", "panels": [table["id"]]})
    return {
        "headline": {"title": hero["title"] if hero else scope["label"], "summary": "", "panel": hero["id"] if hero else None},
        "kpis": [k["id"] for k in kpis],
        "sections": sections,
        "insights": [],
    }


def fact_sheet(cands: list[dict]) -> str:
    """Plain-text facts per candidate for the LLM — every number pre-formatted."""
    out = []
    for c in cands:
        line = f"[{c['id']}] {c['chart']} · {c['recipe']['kind']} · score {c['score']}\n  computed title: {c['title']}"
        if c.get("subtitle"):
            line += f"\n  detail: {c['subtitle']}"
        if c["chart"] == "kpi":
            line += f"\n  value: {c['display']} ({c.get('basis', '')})"
            if c.get("compare"):
                line += f"; latest {c.get('current_period')}: {c.get('current_display')} ({c['compare'].get('display')} {c['compare'].get('label')})"
            if c.get("compare_yoy"):
                line += f"; {c['compare_yoy'].get('display')} {c['compare_yoy'].get('label')}"
        for cav in c.get("caveats") or []:
            line += f"\n  caveat: {cav}"
        for a in c.get("annotations") or []:
            if a["type"] == "anomaly":
                line += f"\n  anomaly: {a['label']}"
        s = c.get("stats") or {}
        if c["recipe"]["kind"] == "breakdown" and "top_share" in s:
            line += f"\n  top 3 share {fmt_pct(s['top3_share'])}; {s['k80']} groups make 80%"
        if c["recipe"]["kind"] == "change" and s.get("rel") is not None:
            line += f"\n  total change {fmt_change(s['rel'])}"
        if c["chart"] == "scatter" and s.get("n"):
            line += f"\n  n={compact(s['n'])}"
        out.append(line)
    return "\n".join(out)


__all__ = ["discover", "fact_sheet", "default_story", "fmt_value"]
