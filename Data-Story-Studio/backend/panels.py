"""Panel recipes -> SQL -> data -> chart encoding + an evidence-backed title.

A recipe is a small declarative description of a visual (what to measure, how to group,
which chart). The AI only ever edits recipes (or writes a validated SELECT for a custom
panel); this module turns them into SQL that runs against the scope view, so every chart
on screen has an inspectable query behind it and every number in its title is computed.
"""

import math
import re
from datetime import date, datetime, timedelta

import maps
from fmt import (MONTHS, WEEKDAYS, compact, fmt_change, fmt_pct, fmt_period, fmt_points, fmt_range,
                 fmt_value, is_num, to_date)
from model import agg_sql, dimensions, humanize, measures
from profile import q

GRAINS = ["hour", "day", "week", "month", "quarter", "year"]
CHARTS = {
    "kpi": ["kpi"],
    "timeseries": ["line", "area", "column"],
    "timeseries_split": ["line", "stacked_area", "stacked_column", "small_multiples"],
    "breakdown": ["bar", "column", "treemap", "lollipop"],
    "breakdown_avg": ["bar", "column", "lollipop"],
    "map": ["map", "bar", "lollipop"],
    "change": ["waterfall", "bar"],
    "change_avg": ["bar"],
    "heatmap": ["heatmap"],
    "heatmap_dims": ["heatmap", "sankey"],
    "scatter": ["scatter"],
    "distribution": ["histogram"],
    "table": ["table"],
    "sql": ["bar", "column", "line", "area", "scatter", "table", "kpi"],
}
TIME_PARTS = {"hour": "Hour of day", "dow": "Day of week", "month": "Month of year"}
BLANK = "(blank)"
OTHER = "Other"


class RecipeError(ValueError):
    pass


# ------------------------------------------------------------------ helpers


def lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        if not math.isfinite(v):
            raise RecipeError("non-finite number in filter")
        return repr(float(v)) if isinstance(v, float) else str(v)
    return "'" + str(v).replace("'", "''") + "'"


GENERIC_VALUES = {"low", "medium", "high", "critical", "yes", "no", "true", "false", "other", "none", "unknown", "standard",
                  "basic", "premium", "new", "old", "open", "closed", "a", "b", "c", "small", "large"}


def name_of(value, dim_label: str) -> str:
    """'Low' -> 'Low priority' so a category reads unambiguously in a sentence."""
    v = str(value)
    if v.lower() in GENERIC_VALUES or re.fullmatch(r"[\d.]+", v) or len(v) <= 2:
        return f"{v} {lc(dim_label)}" if v != BLANK else f"blank {lc(dim_label)}"
    return v


def lc(label: str) -> str:
    """Lower-case a label for mid-sentence use, keeping acronyms (NPS, SLA, kWh)."""
    if not label:
        return label
    first = label.split(" ")[0]
    if len(first) > 1 and (first.isupper() or any(ch.isupper() for ch in first[1:])):
        return label
    return label[0].lower() + label[1:]


def plural(label: str) -> str:
    low = label.lower()
    if low.endswith("s"):
        return label
    if low.endswith("y") and low[-2:-1] not in "aeiou":
        return label[:-1] + "ies"
    return label + "s"


def dim_expr(col: str, integral: bool = False) -> str:
    """The grouping expression for a dimension; whole-number codes read '216', not '216.0'."""
    inner = f"CAST(CAST({q(col)} AS BIGINT) AS VARCHAR)" if integral else f"CAST({q(col)} AS VARCHAR)"
    return f"coalesce({inner}, '{BLANK}')"


def _code_like(c: dict) -> bool:
    st = c.get("stats") or {}
    return c.get("dtype") == "number" and is_num(st.get("min")) and is_num(st.get("max")) and float(st["min"]).is_integer() and float(st["max"]).is_integer()


def add_period(d: date, grain: str, n: int = 1) -> date:
    if grain == "day":
        return d + timedelta(days=n)
    if grain == "week":
        return d + timedelta(weeks=n)
    if grain == "hour":
        return d + timedelta(hours=n)
    months = {"month": 1, "quarter": 3, "year": 12}[grain] * n
    y, m = divmod(d.month - 1 + months, 12)
    return d.replace(year=d.year + y, month=m + 1, day=1)


class Ctx:
    """Everything a recipe needs: the scope view, its columns and the active filters."""

    def __init__(self, ds, scope: dict, filters: list | None = None):
        self.ds = ds
        self.scope = scope
        self.view = scope["view"]
        self.cols = {c["name"]: c for c in scope["columns"]}
        self.measures = {m["name"]: m for m in measures(scope)}
        self.dims = {d["name"]: d for d in dimensions(scope)}
        self.time = scope.get("time")
        self.filters = filters or []

    def col(self, name: str) -> dict:
        if name not in self.cols:
            raise RecipeError(f"Unknown column: {name}")
        return self.cols[name]

    def measure(self, name: str) -> dict:
        if name in self.measures:
            return self.measures[name]
        if name in self.cols and self.cols[name]["dtype"] == "number":
            c = self.cols[name]
            return {"name": c["name"], "label": c["label"], "agg": c.get("agg", "sum"), "unit": c.get("unit") or {"kind": "number"},
                    "kind": "sum" if c.get("agg", "sum") == "sum" else "avg"}
        raise RecipeError(f"Unknown measure: {name}")

    def where(self, extra: list | None = None) -> str:
        parts = []
        for f in (self.filters + (extra or [])):
            parts.append(self._filter_sql(f))
        return " AND ".join(parts)

    def _filter_sql(self, f: dict) -> str:
        c = self.col(f["col"])
        op, vals = f.get("op", "in"), f.get("values") or []
        if c["dtype"] in ("date", "datetime"):
            cast = "TIMESTAMP"
            if op == "between" and len(vals) == 2:
                return f"{q(c['name'])} >= CAST({lit(str(vals[0]))} AS {cast}) AND {q(c['name'])} < CAST({lit(str(vals[1]))} AS {cast})"
            if op in ("gte", "lte"):
                sym = ">=" if op == "gte" else "<="
                return f"{q(c['name'])} {sym} CAST({lit(str(vals[0]))} AS {cast})"
            raise RecipeError(f"Unsupported time filter op {op}")
        if c["dtype"] == "number" and op in ("between", "gte", "lte"):
            nums = [float(v) for v in vals]
            if op == "between":
                return f"{q(c['name'])} BETWEEN {lit(nums[0])} AND {lit(nums[1])}"
            return f"{q(c['name'])} {'>=' if op == 'gte' else '<='} {lit(nums[0])}"
        if op in ("in", "not_in", "eq", "neq"):
            items = ", ".join(lit(str(v)) for v in vals)
            if not items:
                raise RecipeError("Filter needs at least one value")
            neg = "NOT " if op in ("not_in", "neq") else ""
            return f"{dim_expr(c['name'], _code_like(c))} {neg}IN ({items})"
        raise RecipeError(f"Unsupported filter op {op}")

    def base(self, extra: list | None = None) -> str:
        w = self.where(extra)
        return f"base AS (SELECT * FROM {q(self.view)}{' WHERE ' + w if w else ''})"

    def grain(self, recipe: dict) -> str:
        g = recipe.get("grain") or (self.time or {}).get("grain") or "month"
        if g not in GRAINS:
            raise RecipeError(f"Unknown grain {g}")
        if g == "hour" and (self.time or {}).get("dtype") != "datetime":
            g = "day"
        return g

    def time_col(self, recipe: dict) -> str:
        t = recipe.get("time") or (self.time or {}).get("col")
        if not t:
            raise RecipeError("This dataset has no date column for a time series")
        if self.col(t)["dtype"] not in ("date", "datetime"):
            raise RecipeError(f"{t} is not a date column")
        return t


def run(ctx: Ctx, sql: str) -> dict:
    return ctx.ds.query(sql)


def partial_flags(ctx: Ctx, periods: list, grain: str, tcol: str) -> tuple[bool, bool]:
    """Is the first / last period only partly covered by the data?"""
    if not periods or grain in ("hour", "day"):
        return False, False
    w = ctx.where()
    mn, mx = ctx.ds.query(
        f"SELECT min({q(tcol)})::DATE, max({q(tcol)})::DATE FROM {q(ctx.view)}{' WHERE ' + w if w else ''}"
    )["rows"][0]
    mn, mx = to_date(mn), to_date(mx)
    first, last = to_date(periods[0]), to_date(periods[-1])
    if not (mn and mx and first and last):
        return False, False
    last_end = add_period(last, grain) - timedelta(days=1)
    first_partial = mn > first + timedelta(days=2 if grain == "week" else 3)
    last_partial = mx < last_end - timedelta(days=1 if grain == "week" else 3)
    return first_partial, last_partial


# ------------------------------------------------------------------ compile


def compile_panel(ctx: Ctx, recipe: dict, title_override: str = "") -> dict:
    kind = recipe.get("kind")
    # chart switches between the two views of the same places change the recipe kind
    if kind == "breakdown" and recipe.get("chart") == "map":
        recipe = {"kind": "map", "measure": recipe["measure"], "dim": recipe["dim"], "chart": "map"}
        kind = "map"
    fn = {
        "kpi": _kpi, "timeseries": _timeseries, "breakdown": _breakdown, "change": _change,
        "heatmap": _heatmap, "scatter": _scatter, "distribution": _distribution, "table": _table, "sql": _sql_panel,
        "map": _map,
    }.get(kind)
    if fn is None:
        raise RecipeError(f"Unknown panel kind {kind}")
    panel = fn(ctx, dict(recipe))
    panel["recipe"] = {**recipe, "chart": panel["chart"]}
    panel.setdefault("annotations", [])
    panel.setdefault("caveats", [])
    for key in ("measure", "x", "y"):
        c = ctx.cols.get(recipe.get(key)) if isinstance(recipe.get(key), str) else None
        if c and c.get("unrated"):
            note = f"{compact(c['unrated'])} records with no {lc(c['label'])} (recorded as 0) are left out of the {lc(c['label'])} figures."
            if note not in panel["caveats"]:
                panel["caveats"].append(note)
    if ctx.filters:
        panel["filtered"] = True
    if title_override:
        panel["title"] = title_override
    return panel


def _pick_chart(recipe: dict, family: str) -> str:
    allowed = CHARTS[family]
    ch = recipe.get("chart")
    return ch if ch in allowed else allowed[0]


def _ts_sql(ctx: Ctx, m: dict, tcol: str, grain: str, extra: list | None = None) -> str:
    return (f"WITH {ctx.base(extra)}\nSELECT date_trunc('{grain}', {q(tcol)}) AS period, {agg_sql(m)} AS value, count(*) AS n\n"
            f"FROM base WHERE {q(tcol)} IS NOT NULL GROUP BY 1 ORDER BY 1")


def series_stats(values: list[float]) -> dict:
    n = len(values)
    if n < 2:
        return {}
    xs = list(range(n))
    mx, my = sum(xs) / n, sum(values) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, values))
    slope = sxy / sxx if sxx else 0
    ss_tot = sum((y - my) ** 2 for y in values)
    ss_res = sum((y - (my + slope * (x - mx))) ** 2 for x, y in zip(xs, values))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0
    fit_first, fit_last = my + slope * (0 - mx), my + slope * (n - 1 - mx)
    return {"slope": slope, "r2": r2, "mean": my, "fit_first": fit_first, "fit_last": fit_last,
            "fit_change": (fit_last - fit_first) / abs(fit_first) if fit_first else None}


def robust_anomalies(periods: list, values: list[float], threshold: float = 3.5) -> list[dict]:
    n = len(values)
    if n < 8:
        return []
    out = []
    for i, v in enumerate(values):
        lo, hi = max(0, i - 3), min(n, i + 4)
        window = sorted(values[lo:i] + values[i + 1:hi])
        if len(window) < 4:
            continue
        med = window[len(window) // 2]
        devs = sorted(abs(x - med) for x in window)
        mad = devs[len(devs) // 2] or (sum(devs) / len(devs)) or 0
        if mad == 0:
            continue
        z = 0.6745 * (v - med) / mad
        if abs(z) >= threshold and abs(v - med) / (abs(med) or 1) >= 0.25:
            out.append({"index": i, "period": periods[i], "value": v, "typical": med, "z": z,
                        "ratio": v / med if med else None})
    out.sort(key=lambda a: -abs(a["z"]))
    return out[:3]


def _kpi(ctx: Ctx, r: dict) -> dict:
    m = ctx.measure(r["measure"])
    unit = m["unit"]
    total_sql = f"WITH {ctx.base()}\nSELECT {agg_sql(m)} AS value, count(*) AS n FROM base"
    total = run(ctx, total_sql)["rows"][0]
    out = {"chart": "kpi", "unit": unit, "measure": m["name"], "measure_label": m["label"], "agg": m["agg"],
           "title": m["label"], "value": total[0], "display": fmt_value(total[0], unit), "n": total[1],
           "sql": total_sql, "basis": _basis_text(m), "polarity": polarity(m),
           "agg_tag": {"count": "Count", "rate": "Share", "avg": "Average"}.get(m["agg"], "Total")}
    if ctx.time:
        tcol, grain = ctx.time["col"], ctx.grain(r)
        sql = _ts_sql(ctx, m, tcol, grain)
        data = run(ctx, sql)
        rows = [row for row in data["rows"] if row[1] is not None]
        fp, lp = partial_flags(ctx, [row[0] for row in rows], grain, tcol)
        complete = rows[1 if fp else 0: len(rows) - (1 if lp else 0)]
        out["spark"] = [[row[0], row[1]] for row in rows]
        out["spark_partial_last"] = lp
        out["grain"] = grain
        out["sql"] = total_sql + ";\n\n-- trend\n" + sql
        if len(complete) >= 2:
            cur, prev = complete[-1], complete[-2]
            out["compare"] = _compare(m, cur[1], prev[1], f"vs {fmt_period(prev[0], grain)}")
            out["current_period"] = fmt_period(cur[0], grain)
            out["current_value"] = cur[1]
            out["current_display"] = fmt_value(cur[1], unit)
            if grain in ("month", "quarter", "week"):
                back = {"month": 12, "quarter": 4, "week": 52}[grain]
                if len(complete) > back:
                    yo = complete[-1 - back]
                    out["compare_yoy"] = _compare(m, cur[1], yo[1], f"vs {fmt_period(yo[0], grain)}")
    return out


DOWN_GOOD = re.compile(r"(cost|expense|spend|hours|minutes|days|duration|time_to|_time|wait|delay|latency|lead_time|"
                       r"reopen|churn|complaint|defect|error|fail|outage|incident|backlog|overdue|breach|loss|"
                       r"cancel|return|refund|downtime|emission|co2|absen|turnover|attrition|bounce|escalat)")
UP_GOOD = re.compile(r"(revenue|sales|profit|margin|income|satisfaction|csat|nps|score|rating|conversion|signup|"
                     r"retention|uptime|yield|generation|output|growth|visitors|users|customers|orders|units|quantity)")


def polarity(m: dict) -> str:
    """Whether 'up' is good for a measure — a naming heuristic; neutral when unsure."""
    n = f"{m['name']} {m['label']}".lower()
    if DOWN_GOOD.search(n):
        return "down_good"
    if UP_GOOD.search(n):
        return "up_good"
    return "neutral"


def _compare(m: dict, cur, prev, label: str) -> dict:
    if cur is None or prev is None:
        return {}
    unit = m["unit"]
    rate_like = unit.get("kind") in ("percent", "ratio")
    diff = cur - prev
    rel = diff / abs(prev) if prev else None
    return {"label": label, "prev": prev, "diff": diff, "rel": rel,
            "display": fmt_points(diff, unit) if rate_like else fmt_change(rel),
            "direction": "up" if diff > 0 else "down" if diff < 0 else "flat"}


def _basis_text(m: dict) -> str:
    if m["agg"] == "count":
        return "Count of records"
    if m["agg"] == "rate":
        return f"Share of records where {m['label'].removesuffix(' rate')} is true"
    if m["agg"] == "avg":
        return f"Average of {m['label']} (missing values excluded)"
    return f"Sum of {m['label']} (missing values excluded, not treated as zero)"


def _timeseries(ctx: Ctx, r: dict) -> dict:
    m = ctx.measure(r["measure"])
    tcol, grain = ctx.time_col(r), ctx.grain(r)
    split = r.get("split")
    unit = m["unit"]
    if split:
        ctx.col(split)
        top_n = int(r.get("top_n") or 5)
        order = "count(*)" if m["agg"] in ("avg", "rate") else agg_sql(m)
        d = dim_expr(split)
        sql = (f"WITH {ctx.base()},\ntop AS (SELECT {d} AS g FROM base GROUP BY 1 ORDER BY {order} DESC, 1 LIMIT {top_n})\n"
               f"SELECT date_trunc('{grain}', {q(tcol)}) AS period,\n"
               f"  CASE WHEN {d} IN (SELECT g FROM top) THEN {d} ELSE '{OTHER}' END AS series,\n"
               f"  {agg_sql(m)} AS value, count(*) AS n\nFROM base WHERE {q(tcol)} IS NOT NULL GROUP BY 1, 2 ORDER BY 1, 2")
        data = run(ctx, sql)
        periods = sorted({row[0] for row in data["rows"]})
        fp, lp = partial_flags(ctx, periods, grain, tcol)
        chart = _pick_chart(r, "timeseries_split")
        if chart == "stacked_area" and m["agg"] not in ("sum", "count"):
            chart = "line"
        panel = {"chart": chart, "sql": sql, "data": data, "unit": unit, "measure": m["name"], "measure_label": m["label"],
                 "agg": m["agg"], "enc": {"x": "period", "y": "value", "series": "series", "grain": grain, "partial_first": fp, "partial_last": lp},
                 "allowed_charts": CHARTS["timeseries_split"], "split_label": ctx.col(split)["label"]}
        panel.update(_ts_split_story(m, data, grain, fp, lp, ctx.col(split)["label"]))
        return panel
    sql = _ts_sql(ctx, m, tcol, grain)
    data = run(ctx, sql)
    rows = [row for row in data["rows"]]
    fp, lp = partial_flags(ctx, [row[0] for row in rows], grain, tcol)
    chart = _pick_chart(r, "timeseries")
    panel = {"chart": chart, "sql": sql, "data": data, "unit": unit, "measure": m["name"], "measure_label": m["label"],
             "polarity": polarity(m), "agg": m["agg"],
             "enc": {"x": "period", "y": "value", "grain": grain, "partial_first": fp, "partial_last": lp},
             "allowed_charts": CHARTS["timeseries"]}
    panel.update(_ts_story(m, rows, grain, fp, lp))
    return panel


def _complete(rows: list, fp: bool, lp: bool) -> list:
    return rows[1 if fp else 0: len(rows) - (1 if lp else 0)]


def _ts_story(m: dict, rows: list, grain: str, fp: bool, lp: bool) -> dict:
    unit = m["unit"]
    comp = [row for row in _complete(rows, fp, lp) if row[1] is not None]
    ann, caveats, facts = [], [], {}
    label = m["label"]
    if lp and rows:
        ann.append({"type": "partial", "x": rows[-1][0], "label": "Partial period"})
        caveats.append(f"{fmt_period(rows[-1][0], grain)} is incomplete and excluded from the trend.")
    if fp and rows:
        caveats.append(f"{fmt_period(rows[0][0], grain)} is incomplete and excluded from the trend.")
    if len(comp) < 3:
        title = f"{label} by {grain}"
        return {"title": title, "subtitle": f"{len(comp)} complete {grain}s", "annotations": ann, "caveats": caveats, "stats": facts}
    vals = [row[1] for row in comp]
    st = series_stats(vals)
    first, last = comp[0], comp[-1]
    peak = max(comp, key=lambda row: row[1])
    trough = min(comp, key=lambda row: row[1])
    rng = fmt_range(first[0], last[0], grain)
    rate_like = unit.get("kind") in ("percent", "ratio")
    change = (last[1] - first[1]) / abs(first[1]) if first[1] else None
    facts = {**st, "first": first[1], "last": last[1], "first_period": first[0], "last_period": last[0],
             "peak": peak[1], "peak_period": peak[0], "trough": trough[1], "trough_period": trough[0],
             "change": change, "periods": len(comp)}
    strong = st.get("r2", 0) >= 0.3 and st.get("fit_change") is not None and abs(st["fit_change"]) >= 0.05
    if strong:
        up = st["slope"] > 0
        amount = fmt_points(st["fit_last"] - st["fit_first"], unit) if rate_like else fmt_change(st["fit_change"]).lstrip("+-")
        title = f"{label} {'rose' if up else 'fell'} {amount} over {rng}" if not rate_like else f"{label} moved {amount} over {rng}"
        facts["trend"] = "up" if up else "down"
    elif st.get("fit_change") is not None and abs(st["fit_change"]) < 0.05:
        title = f"{label} held broadly steady across {rng}"
        facts["trend"] = "flat"
    else:
        title = f"{label} fluctuated across {rng} with no steady trend"
        facts["trend"] = "volatile"
    anomalies = robust_anomalies([row[0] for row in comp], vals)
    extremes = [a for a in anomalies if a["period"] in (peak[0], trough[0])]
    if extremes and facts["trend"] in ("volatile", "flat"):
        a = extremes[0]
        word = "spiked" if a["value"] > a["typical"] else "dropped"
        ratio = f" ({a['ratio']:.1f}× a typical {grain})" if a["ratio"] and a["ratio"] >= 1.5 else ""
        title = f"{label} {word} to {fmt_value(a['value'], unit)} in {fmt_period(a['period'], grain)}{ratio}"
        facts["trend"] = "spike"
    facts["anomalies"] = anomalies
    for a in anomalies:
        ratio = a["ratio"]
        what = (f"{ratio:.1f}× typical" if ratio and ratio >= 1.5 else
                f"{fmt_change(ratio - 1)} vs typical" if ratio else "unusual")
        ann.append({"type": "anomaly", "x": a["period"], "y": a["value"], "label": f"{fmt_period(a['period'], grain)}: {what}"})
    ann.append({"type": "peak", "x": peak[0], "y": peak[1], "label": f"Peak {fmt_value(peak[1], unit)}"})
    sub = f"Peak {fmt_value(peak[1], unit)} in {fmt_period(peak[0], grain)} · low {fmt_value(trough[1], unit)} in {fmt_period(trough[0], grain)}"
    return {"title": title, "subtitle": sub, "annotations": ann, "caveats": caveats, "stats": facts}


def _ts_split_story(m: dict, data: dict, grain: str, fp: bool, lp: bool, split_label: str) -> dict:
    by: dict[str, list] = {}
    for period, series, value, n in data["rows"]:
        by.setdefault(series, []).append((period, value))
    periods = sorted({row[0] for row in data["rows"]})
    comp_periods = _complete(periods, fp, lp)
    caveats = []
    if lp and periods:
        caveats.append(f"{fmt_period(periods[-1], grain)} is incomplete.")
    if len(comp_periods) < 4 or len(by) < 2:
        return {"title": f"{m['label']} by {lc(split_label)} over time", "subtitle": "", "caveats": caveats, "stats": {}}
    half = len(comp_periods) // 2
    early, late = set(comp_periods[:half]), set(comp_periods[-half:])
    growth = []
    additive = m["agg"] in ("sum", "count")
    tot_early = tot_late = 0.0
    for s, pts in by.items():
        e = [v for p, v in pts if p in early and v is not None]
        l_ = [v for p, v in pts if p in late and v is not None]
        if not e or not l_:
            continue
        ev, lv = (sum(e), sum(l_)) if additive else (sum(e) / len(e), sum(l_) / len(l_))
        tot_early += ev
        tot_late += lv
        growth.append((s, ev, lv, (lv - ev) / abs(ev) if ev else None))
    growth = [g for g in growth if g[3] is not None and g[0] != OTHER]
    if not growth:
        return {"title": f"{m['label']} by {lc(split_label)} over time", "subtitle": "", "caveats": caveats, "stats": {}}
    best = max(growth, key=lambda g: g[3])
    worst = min(growth, key=lambda g: g[3])
    stats = {"growth": growth, "best": best, "worst": worst}
    period_word = f"{grain}s"
    if additive and tot_early and tot_late:
        sh_e, sh_l = best[1] / tot_early, best[2] / tot_late
        stats["share_shift"] = (best[0], sh_e, sh_l)
    if best[3] > 0.1 and (worst[3] >= 0 or best[3] >= abs(worst[3])):
        title = f"{name_of(best[0], split_label)} grew fastest: {fmt_change(best[3])} in the latest {half} {period_word} vs the first {half}"
        hl = best[0]
    elif worst[3] < -0.1:
        title = f"{name_of(worst[0], split_label)} declined most: {fmt_change(worst[3])} in the latest {half} {period_word} vs the first {half}"
        hl = worst[0]
    else:
        title = f"Every {lc(split_label)} moved within ±10% between the first and latest {half} {period_word}"
        hl = None
    sub = f"Comparing the first {half} and latest {half} complete {period_word}"
    return {"title": title, "subtitle": sub, "highlight": hl, "caveats": caveats, "stats": stats}


def _breakdown(ctx: Ctx, r: dict) -> dict:
    m = ctx.measure(r["measure"])
    dim = r["dim"]
    dc = ctx.col(dim)
    top_n = int(r.get("top_n") or 12)
    d = dim_expr(dim, _code_like(dc))
    additive = m["agg"] in ("sum", "count")
    if r.get("min_n") or r.get("rank"):
        return _ranking(ctx, r, m, dc, d, additive)
    order = agg_sql(m) if additive else "count(*)"
    sql = (f"WITH {ctx.base()},\ng AS (SELECT {d} AS label, {agg_sql(m)} AS value, count(*) AS n FROM base GROUP BY 1),\n"
           f"ranked AS (SELECT *, row_number() OVER (ORDER BY {'value' if additive else 'n'} DESC NULLS LAST, label) AS rk FROM g)\n"
           f"SELECT CASE WHEN rk <= {top_n} THEN label ELSE '{OTHER}' END AS label,\n"
           + (f"  sum(value) AS value," if additive else f"  sum(value * n) / sum(n) AS value,")
           + f" sum(n) AS n,\n  sum(value) / (SELECT sum(value) FROM g) AS share\n"
           f"FROM ranked GROUP BY 1")
    sql = f"SELECT * FROM (\n{sql}\n) ORDER BY (label = '{OTHER}'), value DESC NULLS LAST"
    if not additive:
        sql = sql.replace("sum(value) / (SELECT sum(value) FROM g) AS share", "sum(n) / (SELECT sum(n) FROM g) AS share")
    _ = order
    data = run(ctx, sql)
    family = "breakdown" if additive else "breakdown_avg"
    chart = _pick_chart(r, family)
    if r.get("sort") == "label" or dc.get("ordinal"):
        data["rows"].sort(key=lambda row: (row[0] == OTHER, float(row[0]) if re.fullmatch(r"-?\d+(\.\d+)?", str(row[0])) else 0, str(row[0])))
    allowed = list(CHARTS[family])
    if maps.fit_dimension(ctx.ds, ctx.scope, dim):
        allowed.append("map")  # switching to it turns the recipe into a map (compile_panel)
    panel = {"chart": chart, "sql": sql, "data": data, "unit": m["unit"], "measure": m["name"], "measure_label": m["label"],
             "dim": dim, "dim_label": dc["label"], "enc": {"cat": "label", "value": "value", "n": "n", "share": "share"},
             "allowed_charts": allowed}
    panel.update(_breakdown_story(ctx, m, dc, data, additive))
    return panel


def _ranking(ctx: Ctx, r: dict, m: dict, dc: dict, d: str, additive: bool) -> dict:
    """The leaders on a measure among groups big enough to trust (min_n records with a value)."""
    top_n = int(r.get("top_n") or 10)
    min_n = int(r.get("min_n") or 1)
    mcol = "1" if m["agg"] == "count" else q(m["name"])
    sql = (f"WITH {ctx.base()},\ng AS (SELECT {d} AS label, {agg_sql(m)} AS value, count({mcol}) AS n FROM base GROUP BY 1)\n"
           f"SELECT label, value, n, n * 1.0 / (SELECT sum(n) FROM g) AS share FROM g\n"
           f"WHERE label <> '{BLANK}' AND n >= {min_n} AND value IS NOT NULL ORDER BY value DESC, label LIMIT {top_n}")
    data = run(ctx, sql)
    total_sql = f"WITH {ctx.base()}\nSELECT count(DISTINCT {d}), {agg_sql(m)} FROM base"
    groups, overall = run(ctx, total_sql)["rows"][0]
    rows = data["rows"]
    unit = m["unit"]
    panel = {"chart": "bar", "sql": sql, "data": data, "unit": unit, "measure": m["name"], "measure_label": m["label"],
             "dim": dc["name"], "dim_label": dc["label"], "enc": {"cat": "label", "value": "value", "n": "n", "share": "share"},
             "allowed_charts": ["bar", "lollipop"], "stats": {"groups": groups, "min_n": min_n, "overall": overall}}
    if not rows:
        panel.update({"title": f"{m['label']} by {lc(dc['label'])}", "subtitle": f"No {lc(dc['label'])} has {min_n}+ records"})
        return panel
    lead = rows[0]
    plural_dim = lc(plural(dc["label"]))
    if additive:
        total = overall or 0
        top_share = lead[1] / total if total else 0
        top3 = sum(row[1] for row in rows[:3]) / total if total else 0
        panel["stats"].update({"top": lead[0], "top_share": top_share, "top3_share": top3, "total": total, "distinct": groups})
        title = f"{name_of(lead[0], dc['label'])} leads on {lc(m['label'])} with {fmt_pct(top_share)} of the total"
        if len(rows) >= 3:
            title += f"; the top 3 {plural_dim} hold {fmt_pct(top3)}"
        sub = f"Top {len(rows)} of {compact(groups)} {plural_dim}"
    else:
        panel["stats"].update({"high": lead, "low": rows[-1], "spread": (lead[1] / rows[-1][1]) if rows[-1][1] else None})
        title = (f"{name_of(lead[0], dc['label'])} ranks highest on {lc(m['label'])} at {fmt_value(lead[1], unit)}, "
                 f"against {fmt_value(overall, unit)} overall")
        sub = f"Top {len(rows)} {plural_dim} with at least {min_n} records · smaller groups are not ranked"
    panel.update({"title": title, "subtitle": sub, "highlight": lead[0]})
    return panel


def _breakdown_story(ctx: Ctx, m: dict, dc: dict, data: dict, additive: bool) -> dict:
    rows = [row for row in data["rows"] if row[1] is not None]
    unit = m["unit"]
    named = [row for row in rows if row[0] != OTHER]
    if not named:
        return {"title": f"{m['label']} by {lc(dc['label'])}", "subtitle": "", "stats": {}}
    stats = {"groups": len(rows)}
    if additive:
        total = sum(row[1] for row in rows)
        top = named[0]
        share = top[1] / total if total else 0
        top3 = sum(row[1] for row in named[:3]) / total if total else 0
        cum, k80 = 0.0, 0
        for row in sorted(rows, key=lambda r_: -r_[1]):
            cum += row[1]
            k80 += 1
            if total and cum / total >= 0.8:
                break
        stats.update({"top": top[0], "top_share": share, "top3_share": top3, "k80": k80, "total": total,
                      "distinct": dc["distinct"]})
        n_groups = dc["distinct"]
        if share >= 0.3 or n_groups <= 3:
            title = f"{name_of(top[0], dc['label'])} accounts for {fmt_pct(share)} of {lc(m['label'])}"
        elif len(named) >= 4 and top3 >= 0.5:
            title = f"The top 3 {lc(plural(dc['label']))} make up {fmt_pct(top3)} of {lc(m['label'])}"
        else:
            title = f"{lc(m['label'])[:1].upper() + lc(m['label'])[1:]} is spread across {lc(plural(dc['label']))}: {name_of(top[0], dc['label'])} leads with {fmt_pct(share)}"
        sub = (f"{k80} of {n_groups} {lc(plural(dc['label']))} make up 80% of the total" if n_groups > 4 else
               f"Total {fmt_value(total, unit)}")
        return {"title": title, "subtitle": sub, "highlight": top[0], "stats": stats}
    if dc.get("ordinal") and len(named) >= 3:
        first, last = named[0], named[-1]
        overall = sum(row[1] * row[2] for row in rows) / max(sum(row[2] for row in rows), 1)
        tier = lambda row: f"{lc(dc['label'])} {row[0]}"
        direction = "rises" if last[1] > first[1] else "falls" if last[1] < first[1] else "stays flat"
        stats.update({"overall": overall, "high": max(named, key=lambda r_: r_[1]), "low": min(named, key=lambda r_: r_[1]),
                      "spread": (max(r_[1] for r_ in named) / min(r_[1] for r_ in named)) if min(r_[1] for r_ in named) else None})
        title = (f"{m['label']} {direction} with {lc(dc['label'])}: {fmt_value(first[1], unit)} at {tier(first)} to "
                 f"{fmt_value(last[1], unit)} at {tier(last)}")
        return {"title": title, "subtitle": f"Average by {lc(dc['label'])} · a pattern across groups, not proof that one causes the other",
                "highlight": last[0], "stats": stats}
    # averages / rates: compare groups with enough records against the overall
    overall = sum(row[1] * row[2] for row in rows) / max(sum(row[2] for row in rows), 1)
    solid = [row for row in named if row[2] >= 20] or named
    hi = max(solid, key=lambda r_: r_[1])
    lo = min(solid, key=lambda r_: r_[1])
    stats.update({"overall": overall, "high": hi, "low": lo, "spread": (hi[1] / lo[1]) if lo[1] else None})
    if lo[1] and hi[1] / lo[1] >= 1.15 and len(solid) >= 2:
        title = (f"{name_of(hi[0], dc['label'])} has the highest {lc(m['label'])}: {fmt_value(hi[1], unit)} vs "
                 f"{fmt_value(overall, unit)} overall")
    else:
        title = f"{m['label']} is similar across {lc(plural(dc['label']))} (all within 15%)"
    sub = f"Lowest: {name_of(lo[0], dc['label'])} at {fmt_value(lo[1], unit)} · groups with fewer than 20 records are not ranked"
    return {"title": title, "subtitle": sub, "highlight": hi[0], "stats": stats}


def _period_bounds(ctx: Ctx, r: dict) -> tuple[str, str, str, str, str]:
    """Latest complete period (B) vs previous one (A) unless explicit bounds are given."""
    tcol, grain = ctx.time_col(r), ctx.grain(r)
    if r.get("a") and r.get("b"):
        return tcol, r["a"][0], r["a"][1], r["b"][0], r["b"][1]
    m = ctx.measures.get("__records") or next(iter(ctx.measures.values()))
    data = run(ctx, _ts_sql(ctx, m, tcol, grain))
    periods = [row[0] for row in data["rows"]]
    fp, lp = partial_flags(ctx, periods, grain, tcol)
    comp = _complete(periods, fp, lp)
    if len(comp) < 2:
        raise RecipeError("Need at least two complete periods to compare")
    if r.get("compare") == "yoy" and grain in ("month", "quarter", "week"):
        back = {"month": 12, "quarter": 4, "week": 52}[grain]
        if len(comp) <= back:
            raise RecipeError("Not enough history for a year-over-year comparison")
        a = to_date(comp[-1 - back])
    else:
        a = to_date(comp[-2])
    b = to_date(comp[-1])
    return tcol, str(a), str(add_period(a, grain)), str(b), str(add_period(b, grain))


def _change(ctx: Ctx, r: dict) -> dict:
    m = ctx.measure(r["measure"])
    dim = r["dim"]
    dc = ctx.col(dim)
    grain = ctx.grain(r)
    tcol, a0, a1, b0, b1 = _period_bounds(ctx, r)
    d = dim_expr(dim)
    agg = agg_sql(m)
    fa = f"{q(tcol)} >= CAST('{a0}' AS TIMESTAMP) AND {q(tcol)} < CAST('{a1}' AS TIMESTAMP)"
    fb = f"{q(tcol)} >= CAST('{b0}' AS TIMESTAMP) AND {q(tcol)} < CAST('{b1}' AS TIMESTAMP)"
    agg_a = agg.replace("count(*)", f"count(*) FILTER (WHERE {fa})") if m["agg"] == "count" else f"{agg[:-1]}) FILTER (WHERE {fa})"
    agg_b = agg.replace("count(*)", f"count(*) FILTER (WHERE {fb})") if m["agg"] == "count" else f"{agg[:-1]}) FILTER (WHERE {fb})"
    top_n = int(r.get("top_n") or 8)
    additive = m["agg"] in ("sum", "count")
    sql = (f"WITH {ctx.base()},\ng AS (SELECT {d} AS label, {agg_a} AS before, {agg_b} AS after,\n"
           f"  count(*) FILTER (WHERE {fa}) AS n_before, count(*) FILTER (WHERE {fb}) AS n_after FROM base GROUP BY 1),\n"
           f"ranked AS (SELECT *, coalesce(after, 0) - coalesce(before, 0) AS delta,\n"
           f"  row_number() OVER (ORDER BY abs(coalesce(after, 0) - coalesce(before, 0)) DESC, label) AS rk FROM g)\n"
           f"SELECT CASE WHEN rk <= {top_n} THEN label ELSE '{OTHER}' END AS label,\n"
           + ("  sum(before) AS before, sum(after) AS after, sum(delta) AS delta,"
              if additive else
              "  sum(before * n_before) / nullif(sum(n_before), 0) AS before, sum(after * n_after) / nullif(sum(n_after), 0) AS after,\n"
              "  sum(after * n_after) / nullif(sum(n_after), 0) - sum(before * n_before) / nullif(sum(n_before), 0) AS delta,")
           + " sum(n_before) AS n_before, sum(n_after) AS n_after\n"
           f"FROM ranked GROUP BY 1")
    sql = f"SELECT * FROM (\n{sql}\n) ORDER BY (label = '{OTHER}'), delta DESC"
    data = run(ctx, sql)
    family = "change" if additive else "change_avg"
    chart = _pick_chart(r, family)
    la, lb = fmt_period(a0, grain), fmt_period(b0, grain)
    panel = {"chart": chart, "sql": sql, "data": data, "unit": m["unit"], "measure": m["name"], "measure_label": m["label"],
             "dim": dim, "dim_label": dc["label"], "period_a": la, "period_b": lb, "time_col": tcol,
             "range_a": [a0, a1], "range_b": [b0, b1], "polarity": polarity(m),
             "enc": {"cat": "label", "before": "before", "after": "after", "delta": "delta"},
             "allowed_charts": CHARTS[family]}
    rows = [row for row in data["rows"]]
    if additive:
        before = sum(row[1] or 0 for row in rows)
        after = sum(row[2] or 0 for row in rows)
    else:
        nb, na = sum(row[4] or 0 for row in rows), sum(row[5] or 0 for row in rows)
        before = sum((row[1] or 0) * (row[4] or 0) for row in rows) / nb if nb else None
        after = sum((row[2] or 0) * (row[5] or 0) for row in rows) / na if na else None
    panel["totals"] = {"before": before, "after": after}
    stats = {"before": before, "after": after, "period_a": la, "period_b": lb}
    if before is not None and after is not None:
        diff = after - before
        rel = diff / abs(before) if before else None
        stats.update({"diff": diff, "rel": rel})
        named = [row for row in rows if row[0] != OTHER and row[3] is not None]
        same_dir = [row for row in named if (row[3] > 0) == (diff > 0) and row[3] != 0]
        unit = m["unit"]
        verb = "rose" if diff > 0 else "fell" if diff < 0 else "was unchanged"
        rel_txt = f" ({fmt_change(rel)})" if rel is not None and unit.get("kind") not in ("percent", "ratio") else ""
        if additive and same_dir and diff:
            top = max(same_dir, key=lambda row: abs(row[3]))
            share = top[3] / diff
            stats.update({"driver": top[0], "driver_delta": top[3], "driver_share": share})
            panel["highlight"] = top[0]
            if share > 1.05:
                tail = f"{name_of(top[0], dc['label'])} alone moved {fmt_points(top[3], unit)}, more than the net change"
            elif share >= 0.95:
                tail = f"{name_of(top[0], dc['label'])} accounts for nearly all of the change"
            else:
                tail = f"{name_of(top[0], dc['label'])} drove {fmt_pct(share)} of it"
            panel["title"] = f"{m['label']} {verb} {fmt_points(abs(diff), unit).lstrip('+')}{rel_txt} in {lb} vs {la}; {tail}"
        elif not additive and named:
            solid = [row for row in named if (row[5] or 0) >= 10] or named
            top = max(solid, key=lambda row: abs(row[3]))
            stats.update({"driver": top[0], "driver_delta": top[3]})
            panel["highlight"] = top[0]
            panel["title"] = (f"{m['label']} {verb} from {fmt_value(before, unit)} to {fmt_value(after, unit)} in {lb}; "
                              f"biggest move: {name_of(top[0], dc['label'])} ({fmt_points(top[3], unit)})")
        else:
            panel["title"] = f"{m['label']} {verb}{rel_txt} in {lb} vs {la}"
        panel["subtitle"] = f"{fmt_value(before, unit)} in {la} → {fmt_value(after, unit)} in {lb}, by {lc(dc['label'])}"
    else:
        panel["title"] = f"{m['label']}: {lb} vs {la}"
        panel["subtitle"] = ""
    panel["stats"] = stats
    return panel


def _axis(ctx: Ctx, spec: dict, tcol: str | None) -> tuple[str, str, str]:
    """Returns (sql expression, label, kind) for a heatmap axis (dimension or time part)."""
    if spec.get("part"):
        if not tcol:
            raise RecipeError("No date column for a time-part axis")
        part = spec["part"]
        expr = {"hour": f"hour({q(tcol)})", "dow": f"isodow({q(tcol)})", "month": f"month({q(tcol)})"}.get(part)
        if not expr:
            raise RecipeError(f"Unknown time part {part}")
        return expr, TIME_PARTS[part], part
    ctx.col(spec["dim"])
    return dim_expr(spec["dim"]), ctx.col(spec["dim"])["label"], "dim"


def _part_label(kind: str, v) -> str:
    if kind == "dow" and isinstance(v, (int, float)):
        return WEEKDAYS[int(v) - 1]
    if kind == "month" and isinstance(v, (int, float)):
        return MONTHS[int(v) - 1]
    if kind == "hour" and isinstance(v, (int, float)):
        return f"{int(v):02d}:00"
    return str(v)


def _sort_key(v):
    return (0, v, "") if isinstance(v, (int, float)) else (1, 0, str(v))


def _heatmap(ctx: Ctx, r: dict) -> dict:
    m = ctx.measure(r["measure"])
    tcol = (ctx.time or {}).get("col")
    xe, xl, xk = _axis(ctx, r["x"], tcol)
    ye, yl, yk = _axis(ctx, r["y"], tcol)
    limit_dims = ""
    top = []
    for e, k, nm in ((xe, xk, "tx"), (ye, yk, "ty")):
        if k == "dim":
            top.append(f"{nm} AS (SELECT {e} AS g FROM base GROUP BY 1 ORDER BY count(*) DESC, 1 LIMIT 15)")
            limit_dims += f" AND {e} IN (SELECT g FROM {nm})"
    sql = (f"WITH {ctx.base()}{',' if top else ''}\n" + ",\n".join(top) + ("\n" if top else "")
           + f"SELECT {xe} AS x, {ye} AS y, {agg_sql(m)} AS value, count(*) AS n\nFROM base WHERE TRUE{limit_dims}"
           + (f" AND {q(tcol)} IS NOT NULL" if "part" in (r["x"].keys() | r["y"].keys()) else "")
           + "\nGROUP BY 1, 2 ORDER BY 1, 2")
    data = run(ctx, sql)
    x_order = [_part_label(xk, v) for v in sorted({row[0] for row in data["rows"]}, key=_sort_key)]
    y_order = [_part_label(yk, v) for v in sorted({row[1] for row in data["rows"]}, key=_sort_key)]
    for row in data["rows"]:
        row[0] = _part_label(xk, row[0])
        row[1] = _part_label(yk, row[1])
    additive = m["agg"] in ("sum", "count")
    family = "heatmap_dims" if xk == "dim" and yk == "dim" and additive else "heatmap"
    chart = _pick_chart(r, family)
    panel = {"chart": chart, "sql": sql, "data": data, "unit": m["unit"], "measure": m["name"], "measure_label": m["label"],
             "x_label": xl, "y_label": yl, "x_kind": xk, "y_kind": yk, "x_order": x_order, "y_order": y_order,
             "enc": {"x": "x", "y": "y", "value": "value", "n": "n"}, "allowed_charts": CHARTS[family]}
    cells = [row for row in data["rows"] if row[2] is not None and (additive or row[3] >= 10)]
    if cells:
        hot = max(cells, key=lambda row: row[2])
        vals = sorted(row[2] for row in cells)
        med = vals[len(vals) // 2]
        ratio = hot[2] / med if med else None
        stats = {"hot": hot, "median": med, "ratio": ratio}
        if xk in ("hour", "dow") or yk in ("hour", "dow"):
            title = f"{lc(m['label'])[:1].upper() + lc(m['label'])[1:]} {'peak' if m['label'].lower().endswith('s') else 'peaks'} on {hot[1] if yk == 'dow' else hot[0]} at {hot[0] if xk == 'hour' else hot[1]}" \
                if {xk, yk} == {"hour", "dow"} else f"{hot[0]} · {hot[1]} is the hotspot for {lc(m['label'])}"
        else:
            title = f"{name_of(hot[0], xl)} × {name_of(hot[1], yl)} is the hotspot for {lc(m['label'])}"
        if ratio and ratio >= 1.5:
            title += f" ({ratio:.1f}× the typical cell)"
        panel.update({"title": title, "subtitle": f"{yl} by {lc(xl)} · darker = higher {lc(m['label'])}", "stats": stats,
                      "highlight": [hot[0], hot[1]]})
    else:
        panel.update({"title": f"{m['label']} by {lc(xl)} and {lc(yl)}", "subtitle": "", "stats": {}})
    return panel


def _scatter(ctx: Ctx, r: dict) -> dict:
    x, y = ctx.col(r["x"]), ctx.col(r["y"])
    color = r.get("color")
    cols = [q(x["name"]), q(y["name"])] + ([dim_expr(color) + " AS color"] if color else [])
    w = f"{q(x['name'])} IS NOT NULL AND {q(y['name'])} IS NOT NULL"
    stat_sql = f"WITH {ctx.base()}\nSELECT corr({q(x['name'])}, {q(y['name'])}) AS r, count(*) AS n, regr_slope({q(y['name'])}, {q(x['name'])}) AS slope, regr_intercept({q(y['name'])}, {q(x['name'])}) AS intercept FROM base WHERE {w}"
    st = run(ctx, stat_sql)["rows"][0]
    sql = (f"WITH {ctx.base()}\nSELECT {', '.join(cols)} FROM base WHERE {w}\n"
           f"USING SAMPLE reservoir(1500 ROWS) REPEATABLE (7)")
    data = run(ctx, sql)
    rv, n = st[0], st[1]
    panel = {"chart": "scatter", "sql": stat_sql + ";\n\n-- points (deterministic sample of up to 1,500)\n" + sql, "data": data,
             "x_label": x["label"], "y_label": y["label"], "x_unit": x.get("unit"), "y_unit": y.get("unit"),
             "enc": {"x": x["name"], "y": y["name"], "color": "color" if color else None},
             "trend": {"slope": st[2], "intercept": st[3]} if st[2] is not None else None,
             "allowed_charts": CHARTS["scatter"], "stats": {"r": rv, "n": n}}
    if rv is None:
        panel.update({"title": f"{x['label']} vs {y['label']}", "subtitle": ""})
        return panel
    a = abs(rv)
    strength = "strongly" if a >= 0.7 else "moderately" if a >= 0.5 else "weakly" if a >= 0.3 else None
    if strength:
        rel = "rise together" if rv > 0 else "move in opposite directions"
        title = f"{x['label']} and {lc(y['label'])} {strength} {rel} (r = {rv:.2f})"
    else:
        title = f"No clear linear relationship between {lc(x['label'])} and {lc(y['label'])} (r = {rv:.2f})"
    panel.update({"title": title, "subtitle": f"Across {compact(n)} records · correlation does not imply causation"})
    return panel


def _distribution(ctx: Ctx, r: dict) -> dict:
    m = ctx.measure(r["measure"])
    if m["agg"] == "count":
        raise RecipeError("Distribution needs a numeric column")
    col = q(m["name"])
    bins = max(5, min(int(r.get("bins") or 20), 60))
    q_sql = (f"WITH {ctx.base()}\nSELECT quantile_cont({col}, 0.01), quantile_cont({col}, 0.99), median({col}),"
             f" quantile_cont({col}, 0.9), quantile_cont({col}, 0.25), quantile_cont({col}, 0.75), count({col}), min({col}), max({col}) FROM base")
    lo, hi, med, p90, q1, q3, n, mn, mx = run(ctx, q_sql)["rows"][0]
    quantile99 = hi
    if lo is None or hi is None or n == 0:
        raise RecipeError("No values to plot")
    if hi <= lo:
        hi = lo + 1
    width = (hi - lo) / bins
    sql = (f"WITH {ctx.base()}\nSELECT least(greatest(floor(({col} - {lo!r}) / {width!r}), 0), {bins - 1})::INT AS bin, count(*) AS n\n"
           f"FROM base WHERE {col} IS NOT NULL GROUP BY 1 ORDER BY 1")
    data = run(ctx, sql)
    counts = {int(row[0]): row[1] for row in data["rows"]}
    unit = m["unit"]
    rows = []
    for b in range(bins):
        a0 = lo + b * width
        a1 = a0 + width
        label = f"{fmt_value(a0, unit)}–{fmt_value(a1, unit)}"
        if b == 0 and mn < lo:
            label = f"≤{fmt_value(a1, unit)}"
        if b == bins - 1 and mx > hi:
            label = f"≥{fmt_value(a0, unit)}"
        rows.append([label, counts.get(b, 0), a0, a1])
    top10 = top1 = None
    if m["agg"] == "sum" and mn is not None and mn >= 0:
        t_sql = (f"WITH {ctx.base()}\nSELECT sum({col}) FILTER (WHERE {col} >= {p90!r}) / nullif(sum({col}), 0),"
                 f" sum({col}) FILTER (WHERE {col} >= {quantile99!r}) / nullif(sum({col}), 0) FROM base")
        top10, top1 = run(ctx, t_sql)["rows"][0]
    iqr = (q3 - q1) if q1 is not None and q3 is not None else 0
    out_sql = f"WITH {ctx.base()}\nSELECT count(*) FROM base WHERE {col} > {q3 + 3 * iqr!r} OR {col} < {q1 - 3 * iqr!r}"
    outliers = run(ctx, out_sql)["rows"][0][0] if iqr else 0
    suffix = ""
    panel = {"chart": "histogram", "sql": q_sql + ";\n\n-- bins\n" + sql + ";\n\n-- extreme outliers (beyond 3×IQR)\n" + out_sql,
             "data": {"columns": ["bin", "n", "lo", "hi"], "rows": rows, "truncated": False},
             "unit": unit, "measure": m["name"], "measure_label": m["label"], "enc": {"cat": "bin", "value": "n"},
             "allowed_charts": CHARTS["distribution"],
             "markers": [{"value": med, "label": f"Median {fmt_value(med, unit)}{suffix}"}, {"value": p90, "label": f"90th pct {fmt_value(p90, unit)}{suffix}"}],
             "stats": {"median": med, "p90": p90, "q1": q1, "q3": q3, "n": n, "outliers": outliers, "max": mx,
                       **({"top10_share": top10, "top1_share": top1} if top10 is not None else {})}}
    skewed = med and p90 and p90 > 2.5 * med
    if skewed and top10 and top10 >= 0.4:
        title = f"The top 10% of records hold {fmt_pct(top10)} of all {lc(m['label'])}; half have under {fmt_value(med, unit)}"
    elif skewed:
        title = f"{m['label']} has a long tail: half are under {fmt_value(med, unit)}{suffix}, but 1 in 10 exceed {fmt_value(p90, unit)}{suffix}"
    else:
        title = f"Most {lc(m['label'])} values fall between {fmt_value(q1, unit)}{suffix} and {fmt_value(q3, unit)}{suffix}"
    sub = f"{compact(n)} values · " + (f"{compact(outliers)} extreme outliers (max {fmt_value(mx, unit)}{suffix})" if outliers else "no extreme outliers")
    if top1 and top10 and top10 >= 0.4:
        sub += f" · the top 1% hold {fmt_pct(top1)}"
    panel.update({"title": title, "subtitle": sub})
    return panel


def _table(ctx: Ctx, r: dict) -> dict:
    cols = r.get("columns") or [c["name"] for c in ctx.scope["columns"] if c["role"] != "text"][:10]
    for c in cols:
        ctx.col(c)
    sort = r.get("sort")
    order = ""
    if sort:
        ctx.col(sort)
        order = f" ORDER BY {q(sort)} {'ASC' if r.get('asc') else 'DESC'} NULLS LAST"
    limit = max(1, min(int(r.get("limit") or 100), 1000))
    sql = f"WITH {ctx.base()}\nSELECT {', '.join(q(c) for c in cols)} FROM base{order} LIMIT {limit}"
    data = run(ctx, sql)
    labels = [ctx.col(c)["label"] for c in cols]
    title = r.get("title") or (f"Records with the highest {lc(ctx.col(sort)['label'])}" if sort else "Sample of records")
    return {"chart": "table", "sql": sql, "data": data, "labels": labels, "units": [ctx.col(c).get("unit") for c in cols],
            "title": title, "subtitle": f"Showing up to {limit} rows", "allowed_charts": CHARTS["table"]}


def _map(ctx: Ctx, r: dict) -> dict:
    """Choropleth of a dimension whose values are places (see maps.py). Can also be shown as bars or lollipops."""
    m = ctx.measure(r["measure"])
    dim = r["dim"]
    dc = ctx.col(dim)
    geo = r.get("geo")
    if not geo:
        fit = maps.fit_dimension(ctx.ds, ctx.scope, dim)
        if not fit:
            raise RecipeError(f"{dc['label']} doesn't hold places a map can show")
        geo = fit["geo"]
    if geo not in maps.keys():
        raise RecipeError(f"No map boundaries for {geo}")
    additive = m["agg"] in ("sum", "count")
    weight = "value" if additive else "n"
    sql = (f"WITH {ctx.base()},\ng AS (SELECT {dim_expr(dim)} AS label, {agg_sql(m)} AS value, count(*) AS n FROM base GROUP BY 1)\n"
           f"SELECT label, value, n, {weight} / sum({weight}) OVER () AS share FROM g ORDER BY value DESC NULLS LAST")
    data = run(ctx, sql)
    matches, unplaced = maps.match(geo, [row[0] for row in data["rows"]])
    base_total = sum(float((row[1] or 0) if additive else (row[2] or 0)) for row in data["rows"])
    acc: dict[str, dict] = {}
    for label, value, n, _ in data["rows"]:
        region = matches.get(label)
        if region is None or value is None:
            continue
        g = acc.setdefault(region, {"name": region, "labels": [], "total": 0.0, "n": 0})
        value, n = float(value), int(n or 0)
        g["labels"].append(label)
        g["n"] += n
        g["total"] += value if additive else value * n
    regions = []
    for g in acc.values():
        value = g["total"] if additive else (g["total"] / g["n"] if g["n"] else None)
        if value is None:
            continue
        share_of = g["total"] if additive else g["n"]
        regions.append({"name": g["name"], "labels": g["labels"], "value": value, "n": g["n"],
                        "share": share_of / base_total if base_total else None})
    regions.sort(key=lambda g: -g["value"])
    unit, label = m["unit"], m["label"]
    plural_, singular = ("countries", "country") if geo == maps.WORLD else ("states and provinces", "state or province")
    panel = {"chart": _pick_chart(r, "map"), "sql": sql, "data": data, "unit": unit, "measure": m["name"], "measure_label": label,
             "agg": m["agg"], "dim": dim, "dim_label": dc["label"], "enc": {"cat": "label", "value": "value", "n": "n", "share": "share"},
             "map": {"geo": geo, "regions": regions}, "allowed_charts": CHARTS["map"]}
    if not regions:
        if not ctx.filters:
            raise RecipeError("None of the values could be placed on a map")
        return {**panel, "title": f"No {plural_} to map under the current filters", "subtitle": "", "stats": {}}
    top = regions[0]
    placed = sum(g["share"] or 0 for g in regions)
    stats = {"regions": len(regions), "coverage": placed, "top": top["name"], "top_value": top["value"], "top_share": top["share"]}
    caveats = []
    unplaced = [u for u in unplaced if u != BLANK]
    if unplaced:
        shown = ", ".join(str(u) for u in unplaced[:5]) + ("…" if len(unplaced) > 5 else "")
        caveats.append(f"{len(unplaced)} value(s) couldn't be matched to a {singular} boundary, so they aren't on the map: {shown}.")
    if additive:
        if top["share"] >= 0.3 or len(regions) <= 3:
            title = f"{top['name']} accounts for {fmt_pct(top['share'])} of {lc(label)}"
        else:
            title = f"{lc(label)[:1].upper() + lc(label)[1:]} is spread across {plural_}: {top['name']} leads with {fmt_pct(top['share'])}"
        sub = f"{len(regions)} {plural_} mapped · {fmt_pct(placed)} of records placed on the map"
    else:
        all_rows = [row for row in data["rows"] if row[1] is not None]
        overall = sum(row[1] * row[2] for row in all_rows) / max(sum(row[2] or 0 for row in all_rows), 1)
        solid = [g for g in regions if g["n"] >= 20] or regions
        hi = max(solid, key=lambda g: g["value"])
        lo = min(solid, key=lambda g: g["value"])
        spread = hi["value"] / lo["value"] if lo["value"] else None
        stats.update({"overall": overall, "spread": spread})
        if spread and spread >= 1.15 and len(solid) >= 2:
            title = f"{hi['name']} has the highest {lc(label)}: {fmt_value(hi['value'], unit)} vs {fmt_value(overall, unit)} overall"
        else:
            title = f"{label} is similar across {plural_} (all within 15%)"
        sub = f"Lowest: {lo['name']} at {fmt_value(lo['value'], unit)} · regions with fewer than 20 records are not ranked"
    return {**panel, "highlight": top["labels"][0], "caveats": caveats, "title": title, "subtitle": sub, "stats": stats}


SQL_SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_ ]*$")


def _sql_panel(ctx: Ctx, r: dict) -> dict:
    """Custom panel from a validated SELECT (Q&A answers, free-form redraws)."""
    from workspace import validate_select

    sql = validate_select(ctx.ds.con, r["sql"])
    if ctx.filters:
        # shadow the scope view with a filtered version so the custom SQL respects dashboard filters
        sql = f"WITH {q(ctx.view)} AS (SELECT * FROM main.{q(ctx.view)} WHERE {ctx.where()})\n{sql}"
    data = run(ctx, sql)
    enc = dict(r.get("enc") or {})
    cols = data["columns"]
    chart = r.get("chart") if r.get("chart") in CHARTS["sql"] else "table"
    for k in ("x", "y", "series", "cat", "value"):
        if enc.get(k) and enc[k] not in cols:
            enc.pop(k)
    if chart != "table" and len(cols) >= 2:
        if chart in ("line", "area"):
            enc.setdefault("x", cols[0])
            enc.setdefault("y", next((c for c in cols[1:] if c != enc.get("series")), cols[1]))
        elif chart in ("bar", "column"):
            enc.setdefault("cat", cols[0])
            enc.setdefault("value", cols[1])
        elif chart == "scatter":
            enc.setdefault("x", cols[0])
            enc.setdefault("y", cols[1])
    elif chart == "kpi" and len(cols) >= 1 and len(data["rows"]) == 1:
        enc.setdefault("value", cols[-1])
    else:
        chart = "table"
    unit = r.get("unit") or _guess_unit(ctx, enc.get("value") or enc.get("y"))
    return {"chart": chart, "sql": sql, "data": data, "enc": enc, "unit": unit,
            "title": r.get("title") or "Custom query", "subtitle": r.get("subtitle", ""), "allowed_charts": CHARTS["sql"],
            "labels": cols}


def _guess_unit(ctx: Ctx, col: str | None) -> dict:
    if not col:
        return {"kind": "number"}
    for c in ctx.scope["columns"]:
        if c["name"] in col:
            return c.get("unit") or {"kind": "number"}
    return {"kind": "number"}


def describe_columns(scope: dict) -> str:
    """Compact schema listing for prompts."""
    lines = []
    for c in scope["columns"]:
        extra = ""
        st = c.get("stats") or {}
        if c["role"] == "measure":
            extra = (f" ({compact(c['unrated'])} unrated rows read as missing)" if c.get("unrated") else "") + f" range {compact(st.get('min')) if is_num(st.get('min')) else '?'}..{compact(st.get('max')) if is_num(st.get('max')) else '?'}, agg={c['agg']}"
        elif c["role"] == "time":
            extra = f" {st.get('min', '')[:10]}..{st.get('max', '')[:10]}"
        elif c["role"] in ("dimension", "flag"):
            extra = f" {c['distinct']} values"
        lines.append(f"- {c['name']} ({c['dtype']}, {c['role']}{extra}) label=\"{c['label']}\"" + (f" derived: {c['derived']}" if c.get("derived") else ""))
    return "\n".join(lines)


def humanize_period(p, grain: str) -> str:
    return fmt_period(p, grain)


__all__ = ["Ctx", "compile_panel", "RecipeError", "CHARTS", "describe_columns", "lc", "plural", "humanize", "series_stats",
           "datetime"]
