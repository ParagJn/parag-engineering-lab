"""Analysis scopes: the DuckDB views that dashboards query.

After setup, each scope is one analysable dataset:
  - union groups (files with the same columns) are stacked, with a `source_file` column
  - lookup tables are LEFT JOINed onto the fact table on confirmed many-to-one keys
  - files with no link become their own scope (own dashboard tab)
  - date pairs (created → resolved) yield a derived duration measure
  - "long" tables (a column naming the measure each row holds) split into one scope per measure
"""

import re

from profile import ColumnProfile, q, time_grain

BOUND_NAME = re.compile(r"(lower|upper|_bound|confidence|_ci_|^ci_|_ci$|margin_of_error|_moe$|std_?err)")
TIME_PREF = re.compile(r"(^date$|created|opened|order_date|start|logged|reported|timestamp|^time$|_date$|date_|month|period|day)")
COORD_NAME = re.compile(r"(^|_)(latitude|longitude|lat|lng|lon)($|_)")
RATING_NAME = re.compile(r"(rating|stars)")
END_PREF = re.compile(r"(resolved|closed|completed|end|finished|shipped|delivered|updated)")


def humanize(name: str) -> str:
    s = re.sub(r"[_\s]+", " ", name).strip()
    return s[:1].upper() + s[1:] if s else name


def _singular_title(table: str) -> str:
    t = humanize(table)
    return t


def build_scopes(con, state: dict, setup: dict) -> list[dict]:
    profiles: dict[str, list[ColumnProfile]] = {
        t: [ColumnProfile(**c) for c in cols] for t, cols in state["profiles"].items()
    }
    rows: dict[str, int] = dict(state["rows"])
    rels = [r for r in state["readiness"]["relationships"] if r["confidence"] == "strong"]
    rels += setup.get("manual_links") or []
    rejected = {(r["left"], r["right"]) for r in setup.get("rejected_links") or []}
    rels = [r for r in rels if (r["left"], r["right"]) not in rejected]
    separate = setup.get("mode") == "separate"

    # 1) union groups
    groups: list[list[str]] = []
    if not separate:
        for r in rels:
            if r["kind"] != "union":
                continue
            ga = next((g for g in groups if r["left"] in g), None)
            gb = next((g for g in groups if r["right"] in g), None)
            if ga and gb and ga is not gb:
                ga.extend(gb)
                groups.remove(gb)
            elif ga:
                ga.append(r["right"]) if r["right"] not in ga else None
            elif gb:
                gb.append(r["left"]) if r["left"] not in gb else None
            else:
                groups.append([r["left"], r["right"]])
    grouped = {t for g in groups for t in g}
    units: list[dict] = []
    for g in groups:
        name = "u_" + g[0]
        parts = " UNION ALL BY NAME ".join(f"SELECT *, '{t}' AS source_file FROM {q(t)}" for t in g)
        con.execute(f"CREATE OR REPLACE VIEW {q(name)} AS {parts}")
        cols = _merge_union_profiles([profiles[t] for t in g])
        cols.append(ColumnProfile(table=name, name="source_file", label="Source file", dtype="text", role="dimension",
                                  count=sum(rows[t] for t in g), missing=0, missing_pct=0, distinct=len(g), unique_ratio=0))
        units.append({"name": name, "tables": g, "rows": sum(rows[t] for t in g), "cols": cols})
    for t in profiles:
        if t not in grouped:
            units.append({"name": t, "tables": [t], "rows": rows[t], "cols": profiles[t]})

    # 2) joins: attach lookups (many-to-one from the fact side) to the biggest units
    units.sort(key=lambda u: -u["rows"])
    unit_of = {t: u for u in units for t in u["tables"]}
    used_as_lookup: set[str] = set()
    joins: dict[str, list[tuple[dict, str, str]]] = {}
    if not separate:
        for r in [r for r in rels if r["kind"] == "join"]:
            ua, ub = unit_of.get(r["left"]), unit_of.get(r["right"])
            if not ua or not ub or ua is ub:
                continue
            card = r.get("cardinality", "many-to-one")
            if card in ("many-to-one", "one-to-one") and ua["rows"] >= ub["rows"]:
                fact, lk, fk, lkcol = ua, ub, r["left_col"], r["right_col"]
            elif card in ("one-to-many", "one-to-one"):
                fact, lk, fk, lkcol = ub, ua, r["right_col"], r["left_col"]
            else:
                continue
            if lk["name"] in used_as_lookup or lk["name"] in joins:
                continue
            joins.setdefault(fact["name"], []).append((lk, fk, lkcol))
            used_as_lookup.add(lk["name"])

    scopes = []
    for u in units:
        if u["name"] in used_as_lookup:
            continue
        view = f"scope_{u['name']}"
        unrated = _unrated_zeros(con, u)
        select = [f"NULLIF(f.{q(c.name)}, 0) AS {q(c.name)}" if c.name in unrated else f"f.{q(c.name)}" for c in u["cols"]]
        cols = [_col_meta(c, u["tables"][0]) for c in u["cols"]]
        for meta in cols:
            if meta["name"] in unrated:
                meta.update(unrated[meta["name"]])
        have = {c.name for c in u["cols"]}
        from_sql = f"{q(u['name'])} f"
        fact_cols = {c.name: c for c in u["cols"]}
        for i, (lk, fk, lkcol) in enumerate(joins.get(u["name"], [])):
            alias = f"l{i}"
            # unique key on the fact side = per-record attributes (e.g. survey answers), not a lookup
            per_record = fk in fact_cols and fact_cols[fk].unique_ratio >= 0.95
            from_sql += f" LEFT JOIN {q(lk['name'])} {alias} ON f.{q(fk)} = {alias}.{q(lkcol)}"
            for c in lk["cols"]:
                if c.name == lkcol:
                    continue
                out = c.name if c.name not in have else f"{lk['name']}_{c.name}"
                have.add(out)
                select.append(f"{alias}.{q(c.name)} AS {q(out)}")
                meta = _col_meta(c, lk["name"])
                meta["name"] = out
                if out != c.name:
                    meta["label"] = f"{humanize(lk['name'])} {c.label}"
                # lookup attributes repeat per fact row: describe, don't sum
                if meta["role"] == "measure" and not per_record:
                    meta["agg"] = "avg"
                    meta["lookup_attr"] = True
                cols.append(meta)
        # foreign keys whose lookup was joined in are identifiers now (the lookup brings the names)
        fks = {fk for _, fk, _ in joins.get(u["name"], [])}
        for meta in cols:
            if meta["name"] in fks:
                meta["role"] = "id"
        derived = _derived_durations(con, from_sql, cols)
        for d in derived:
            select.append(f"{d['expr']} AS {q(d['name'])}")
            cols.append(d["meta"])
        lf = (state["readiness"].get("long_format") or {}).get(u["tables"][0]) if len(u["tables"]) == 1 else None
        if lf:
            scopes.extend(_long_scopes(con, u, lf, select, from_sql, cols, joins.get(u["name"], [])))
            continue
        con.execute(f"CREATE OR REPLACE VIEW {q(view)} AS SELECT {', '.join(select)} FROM {from_sql}")
        n = con.execute(f"SELECT count(*) FROM {q(view)}").fetchone()[0]
        scope = {
            "id": u["name"], "view": view, "label": _scope_label(u, joins.get(u["name"], [])),
            "tables": u["tables"] + [lk["name"] for lk, _, _ in joins.get(u["name"], [])],
            "joins": [{"table": lk["name"], "on": f"{fk} = {lkcol}"} for lk, fk, lkcol in joins.get(u["name"], [])],
            "rows": int(n), "columns": cols,
            "record_label": humanize(u["tables"][0] if len(u["tables"]) == 1 else u["tables"][0]),
        }
        scope["time"] = _pick_time(con, view, cols)
        scopes.append(scope)
    return scopes


def _unrated_zeros(con, u: dict) -> dict:
    """A rating that is 0 on a 1+ scale means 'not rated', not 'rated zero': read it as missing so averages,
    correlations and histograms describe real ratings only. Returns {column: meta overrides}."""
    out = {}
    for c in u["cols"]:
        if not (c.dtype == "number" and c.role == "measure" and RATING_NAME.search(c.name.lower()) and c.zeros):
            continue
        col = q(c.name)
        n, z, pos_min = con.execute(f"SELECT count({col}), count(*) FILTER (WHERE {col} = 0), min({col}) FILTER (WHERE {col} > 0) "
                                    f"FROM {q(u['name'])}").fetchone()
        if not n or pos_min is None or pos_min < 1 or not 0.01 <= z / n <= 0.6:
            continue  # zero is a real value here, or the scale has no gap before it
        mn, mx, mean, med = con.execute(f"SELECT min({col}), max({col}), avg({col}), median({col}) FROM {q(u['name'])} WHERE {col} > 0").fetchone()
        out[c.name] = {"unrated": int(z), "missing_pct": (c.missing + z) / u["rows"] if u["rows"] else 0,
                       "stats": {"min": mn, "max": mx, "mean": mean, "median": med}}
    return out


SUMMABLE = re.compile(r"(numerator|denominator|count|total|population|sum|amount|qty|quantity|volume|cases|deaths|events|sales|revenue)")


def _long_scopes(con, u: dict, lf: dict, select: list[str], from_sql: str, cols: list[dict], joins: list) -> list[dict]:
    """One scope per measure of a long table: a filtered view, with column stats recomputed on the slice."""
    mcol = lf["column"]
    keep = [(sql, c) for sql, c in zip(select, cols) if c["name"] != mcol]
    out, used = [], set()
    for value in lf["values"]:
        slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:40] or "measure"
        while slug in used:
            slug += "_"
        used.add(slug)
        sid = f"{u['name']}__{slug}"
        view = f"scope_{sid}"
        lit = "'" + value.replace("'", "''") + "'"
        con.execute(f"CREATE OR REPLACE VIEW {q(view)} AS SELECT {', '.join(sql for sql, _ in keep)} "
                    f"FROM {from_sql} WHERE f.{q(mcol)} = {lit}")
        n = con.execute(f"SELECT count(*) FROM {q(view)}").fetchone()[0]
        scols = [_slice_meta(con, view, dict(c), n) for _, c in keep]
        scope = {
            "id": sid, "view": view, "label": value,
            "tables": u["tables"] + [lk["name"] for lk, _, _ in joins],
            "joins": [{"table": lk["name"], "on": f"{fk} = {lkcol}"} for lk, fk, lkcol in joins],
            "rows": int(n), "columns": scols, "record_label": humanize(u["tables"][0]),
            "slice": {"column": mcol, "label": lf["label"], "value": value},
        }
        scope["time"] = _pick_time(con, view, scols)
        out.append(scope)
    return out


def _slice_meta(con, view: str, c: dict, n: int) -> dict:
    col = q(c["name"])
    count, distinct = con.execute(f"SELECT count({col}), count(DISTINCT {col}) FROM {q(view)}").fetchone()
    c["missing_pct"] = 1 - count / n if n else 1
    c["distinct"] = int(distinct)
    if c["role"] == "measure":
        mn, mx, mean, med, integral = con.execute(
            f"SELECT min({col}), max({col}), avg({col}), median({col}), count(*) FILTER (WHERE {col} = floor({col})) FROM {q(view)}"
        ).fetchone()
        c["stats"] = {"min": mn, "max": mx, "mean": mean, "median": med}
        # one measure per entity and period: values are levels or rates, so average them unless clearly additive
        if not SUMMABLE.search(c["name"].lower()):
            c["agg"] = "avg"
        if c["unit"].get("kind") == "number" and mn is not None and mn >= 0 and mx <= 1 and integral < count:
            c["unit"] = {"kind": "ratio"}
            c["agg"] = "avg"
    return c


def _merge_union_profiles(lists: list[list[ColumnProfile]]) -> list[ColumnProfile]:
    by_name: dict[str, ColumnProfile] = {}
    for cols in lists:
        for c in cols:
            if c.name not in by_name:
                by_name[c.name] = c
    return list(by_name.values())


def _col_meta(c: ColumnProfile, table: str) -> dict:
    return {
        "name": c.name, "label": c.label, "dtype": c.dtype, "role": c.role, "agg": c.agg, "unit": c.unit,
        "distinct": c.distinct, "missing_pct": c.missing_pct, "source": table, "geo": c.geo,
        "ordinal": any("ordinal tier" in n for n in c.notes),
        "stats": {k: v for k, v in c.stats.items() if k in ("min", "max", "mean", "median", "true_share")},
    }


def _derived_durations(con, from_sql: str, cols: list[dict]) -> list[dict]:
    times = [c for c in cols if c["role"] == "time"]
    if len(times) < 2:
        return []
    starts = [c for c in times if not END_PREF.search(c["name"])] or times
    ends = [c for c in times if END_PREF.search(c["name"])]
    out = []
    for e in ends[:2]:
        s = next((c for c in starts if c["name"] != e["name"]), None)
        if not s:
            continue
        a, b = f"f.{q(s['name'])}" if s["source"] == cols[0]["source"] else q(s["name"]), q(e["name"])
        a, b = q(s["name"]), q(e["name"])
        try:
            ok, total, med_hours = con.execute(
                f"SELECT count(*) FILTER (WHERE {b} >= {a}), count(*) FILTER (WHERE {a} IS NOT NULL AND {b} IS NOT NULL),"
                f" median(date_diff('minute', {a}::TIMESTAMP, {b}::TIMESTAMP)) / 60.0 FROM {from_sql}"
            ).fetchone()
        except Exception:
            continue
        if not total or ok / total < 0.9:
            continue
        use_hours = (s["dtype"] == "datetime" or e["dtype"] == "datetime") and (med_hours or 0) < 72
        unit = "hour" if use_hours else "day"
        name = f"{e['name']}_{unit}s"
        expr = (f"CASE WHEN {b} >= {a} THEN date_diff('minute', {a}::TIMESTAMP, {b}::TIMESTAMP) / "
                f"{60.0 if use_hours else 1440.0} END")
        label = _duration_label(s["label"], e["label"], "Hours" if use_hours else "Days")
        out.append({
            "name": name, "expr": expr,
            "meta": {"name": name, "label": label, "dtype": "number", "role": "measure", "agg": "avg",
                     "unit": {"kind": "number", "suffix": " h" if use_hours else " days"}, "distinct": 0,
                     "missing_pct": 1 - total / max(total, 1), "source": "derived", "geo": False, "stats": {},
                     "derived": f"{e['label']} minus {s['label']}"},
        })
    return out


_VERBS = {"resolved": "resolve", "closed": "close", "completed": "complete", "shipped": "ship", "delivered": "deliver",
          "finished": "finish", "ended": "end", "end": "end", "updated": "update"}


def _duration_label(start: str, end: str, unit: str) -> str:
    first = re.split(r"[\s_]+", end.strip().lower())[0]
    verb = _VERBS.get(first)
    return f"{unit} to {verb}" if verb else f"{unit} from {start} to {end}"


def _pick_time(con, view: str, cols: list[dict]) -> dict | None:
    times = [c for c in cols if c["role"] == "time" and c["missing_pct"] < 0.5]
    if not times:
        return None
    times.sort(key=lambda c: (0 if TIME_PREF.search(c["name"]) and not END_PREF.search(c["name"]) else 1, c["missing_pct"]))
    t = times[0]
    g = time_grain(con, view, t["name"])
    if not g.get("grain"):
        return None
    return {"col": t["name"], "label": t["label"], "dtype": t["dtype"], **g}


def _scope_label(u: dict, joins: list) -> str:
    base = " + ".join(humanize(t) for t in u["tables"]) if len(u["tables"]) <= 3 else f"{len(u['tables'])} files"
    if joins:
        base += " (with " + ", ".join(humanize(lk["name"]) for lk, _, _ in joins) + ")"
    return base


_GENERIC_TABLE_WORDS = {"dataset", "data", "table", "records", "record", "file", "sheet", "export", "report", "list", "sample",
                        "synthetic", "demo", "test", "raw", "clean", "cleaned", "master", "final", "new", "old", "behavior", "behaviour"}
_ENTITIES = {"customer", "order", "restaurant", "patient", "student", "employee", "transaction", "claim", "ticket", "user",
             "account", "loan", "scheme", "fund", "product", "store", "vehicle", "household", "booking", "visit", "session",
             "invoice", "case", "incident", "shipment", "subscriber", "member", "listing", "property", "flight", "trip",
             "campaign", "lead", "client", "supplier", "school", "hospital", "district", "village", "device", "sale"}


def _plural(w: str) -> str:
    if w.endswith("s"):
        return w
    if w.endswith("y") and w[-2:-1] not in "aeiou":
        return w[:-1] + "ies"
    return w + "es" if w.endswith(("x", "ch", "sh")) else w + "s"


def record_noun(label: str) -> str:
    """'Synthetic credit card customer behavior dataset' -> 'Customers'; 'Orders' stays 'Orders'. Falls back to the
    cleaned name so nothing is lost when no recognisable entity is in the file name."""
    words = re.findall(r"[A-Za-z0-9]+", label)
    if len(words) <= 2:
        return label if label.lower().endswith("s") else f"{label} records"
    ents = [w for w in words if w.lower().rstrip("s") in _ENTITIES]
    if ents:
        return _plural(ents[-1].lower()).capitalize()
    kept = [w for w in words if w.lower() not in _GENERIC_TABLE_WORDS] or words
    return " ".join(kept[-2:]).capitalize() + " records"


def measures(scope: dict) -> list[dict]:
    """Analysable measures for a scope, ranked by how likely they are the headline metric."""
    out = [{
        "name": "__records", "label": record_noun(scope["record_label"]),
        "agg": "count", "unit": {"kind": "number"}, "kind": "count",
    }]
    for c in scope["columns"]:
        if c["role"] == "measure" and c["missing_pct"] < 0.9 and not COORD_NAME.search(c["name"].lower()):
            out.append({"name": c["name"], "label": c["label"], "agg": c["agg"], "unit": c["unit"],
                        "kind": "sum" if c["agg"] == "sum" else "avg", "derived": c.get("derived"),
                        "lookup": bool(c.get("lookup_attr"))})
        elif c["role"] == "flag" and c["missing_pct"] < 0.9:
            out.append({"name": c["name"], "label": f"{c['label']} rate", "agg": "rate", "unit": {"kind": "ratio"},
                        "kind": "avg"})

    def rank(m):
        n = m["name"].lower()
        if m.get("lookup") or BOUND_NAME.search(n):
            return 6
        if scope.get("slice") and re.search(r"(^|_)(value|values|estimate|result|amount|score|rate)$", n):
            return -1  # the reading of the sliced measure itself
        if m["kind"] == "sum" and m["unit"].get("kind") == "currency":
            return 0
        if re.search(r"(?:^|_)(revenue|sales|amount|profit|volume|quantity|units|count|total|consumption|usage|generation|kwh|mwh|visitors|users|sessions|signups)", n):
            return 1
        if m.get("derived"):
            return 2
        if m["kind"] == "sum":
            return 3
        if m["agg"] == "rate" or re.search(r"(rating|score|satisf|csat|nps|wait|delay|duration|time|hours|days|minutes)", n):
            return 4
        return 5
    first, rest = out[:1], sorted(out[1:], key=rank)
    # a strong sum measure (or a slice's own reading) leads; otherwise record count leads
    if rest and rank(rest[0]) <= 1:
        return rest[:1] + first + rest[1:]
    return first + rest


def dimensions(scope: dict) -> list[dict]:
    out = []
    for c in scope["columns"]:
        if c["role"] in ("dimension", "flag") and 2 <= c["distinct"] <= 200 and c["missing_pct"] < 0.8:
            out.append({"name": c["name"], "label": c["label"], "distinct": c["distinct"], "dtype": c["dtype"],
                        "geo": c.get("geo", False), "ordinal": c.get("ordinal", False)})
    out.sort(key=lambda d: (0 if 3 <= d["distinct"] <= 25 else 1 if d["distinct"] <= 60 else 2, d["distinct"]))
    return out


def agg_sql(m: dict, alias: str = "") -> str:
    p = f"{alias}." if alias else ""
    if m["agg"] == "count":
        return "count(*)"
    if m["agg"] == "rate":
        return f"avg(CAST({p}{q(m['name'])} AS DOUBLE))"
    if m["agg"] == "avg":
        return f"avg({p}{q(m['name'])})"
    return f"sum({p}{q(m['name'])})"
