"""Column profiling and semantic roles, computed in DuckDB.

Roles drive everything downstream:
  measure   - numeric quantity that is meaningful to sum or average
  dimension - categorical column to group / segment by
  time      - date / datetime axis
  id        - identifier (unique-ish, used for counting and joins, never summed)
  text      - free text (high-cardinality strings)
  flag      - boolean
"""

import re
from dataclasses import asdict, dataclass, field

from ingest import ColumnInfo

ID_NAME = re.compile(r"(^id$|_id$|^id_|_no$|_num$|_number$|code$|_key$|uuid|guid|^ref|_ref$|ticket$|^sku|fips|^zip|postcode|postal)")
RATE_NAME = re.compile(r"(rate|ratio|pct|percent|percentage|share|margin|score|avg|average|mean|median|index|temp|temperature|age|rating|_per_|per_|latitude|longitude|lat$|lon$|lng$|price|nps|csat|sla|discount|satisfaction|stars|grade)")
CURRENCY_NAME = re.compile(r"(revenue|sales|cost|price|amount|profit|spend|budget|income|expense|fee|(order|sale|deal|contract|invoice|gross|net|total|trade)_value|usd|aud|eur|gbp|inr|payment|salary|bill)")
DURATION_NAME = re.compile(r"(hours?|hrs|minutes?|mins|seconds?|secs|days|duration|time_to|tat|lead_time|resolution_time|handle_time)")
YEAR_NAME = re.compile(r"(^year$|_year$|^yr$|fiscal_year|^fy$)")
GEO_NAME = re.compile(r"(country|state|region|city|suburb|postcode|zip|province|territory|county|location)")


@dataclass
class ColumnProfile:
    table: str
    name: str
    label: str
    dtype: str
    role: str
    count: int
    missing: int
    missing_pct: float
    distinct: int
    unique_ratio: float
    agg: str = "sum"  # sum | avg for measures
    unit: dict = field(default_factory=lambda: {"kind": "number"})
    stats: dict = field(default_factory=dict)
    top_values: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    zeros: int = 0
    negatives: int = 0
    geo: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def profile_table(con, table: str, columns: list[ColumnInfo]) -> tuple[int, list[ColumnProfile]]:
    rows = con.execute(f"SELECT count(*) FROM {q(table)}").fetchone()[0]
    out = []
    for c in columns:
        out.append(_profile_column(con, table, c, rows))
    _code_twins(con, table, out)
    return rows, out


def _code_twins(con, table: str, cols: list[ColumnProfile]) -> None:
    """A numeric code with a text column naming the same groups (state_code ~ state) is an id, not a second dimension."""
    texts = [c for c in cols if c.dtype == "text" and c.role == "dimension"]
    for c in cols:
        if c.dtype != "number" or c.role != "dimension" or not any("numeric code" in n for n in c.notes):
            continue
        for t in texts:
            if abs(t.distinct - c.distinct) > max(1, 0.05 * c.distinct):
                continue
            pairs = con.execute(f"SELECT count(DISTINCT ({q(c.name)}, {q(t.name)})) FROM {q(table)} "
                                f"WHERE {q(c.name)} IS NOT NULL AND {q(t.name)} IS NOT NULL").fetchone()[0]
            if pairs <= max(c.distinct, t.distinct) * 1.05:
                c.role = "id"
                c.notes = [n for n in c.notes if "numeric code" not in n] + [f"code for ‘{t.label}’, which carries the names"]
                break


def _profile_column(con, table: str, c: ColumnInfo, rows: int) -> ColumnProfile:
    col = q(c.name)
    count, distinct = con.execute(f"SELECT count({col}), approx_count_distinct({col}) FROM {q(table)}").fetchone()
    distinct = min(int(distinct or 0), int(count or 0))
    if count and distinct > 0 and distinct < 50000:
        distinct = con.execute(f"SELECT count(DISTINCT {col}) FROM {q(table)}").fetchone()[0]
    missing = rows - count
    p = ColumnProfile(
        table=table, name=c.name, label=c.label, dtype=c.dtype, role="text",
        count=int(count), missing=int(missing), missing_pct=(missing / rows) if rows else 0.0,
        distinct=int(distinct), unique_ratio=(distinct / count) if count else 0.0, notes=list(c.notes),
    )
    lname = c.name.lower()

    if c.dtype == "number":
        mn, mx, mean, med, sd, q1, q3, zeros, negs, integral = con.execute(
            f"""SELECT min({col}), max({col}), avg({col}), median({col}), stddev_samp({col}),
                       quantile_cont({col}, 0.25), quantile_cont({col}, 0.75),
                       count(*) FILTER (WHERE {col} = 0), count(*) FILTER (WHERE {col} < 0),
                       count(*) FILTER (WHERE {col} = floor({col}))
                FROM {q(table)}"""
        ).fetchone()
        p.stats = {"min": mn, "max": mx, "mean": mean, "median": med, "std": sd, "q1": q1, "q3": q3}
        p.zeros, p.negatives = int(zeros), int(negs)
        all_int = count and integral == count
        if YEAR_NAME.search(lname) and all_int and mn is not None and 1900 <= mn and mx <= 2100:
            p.role = "dimension"
            p.notes.append("year number treated as a period, not summed")
        elif ID_NAME.search(lname) and all_int:
            # a numeric code is a label, never a quantity: small sets group like categories
            # (unless a text twin carries the names, see _code_twins), large ones identify
            if p.unique_ratio > 0.5 or distinct > 200:
                p.role = "id"
            else:
                p.role = "dimension"
                p.notes.append("numeric code treated as a category, not summed")
        elif all_int and p.unique_ratio > 0.98 and count > 50 and mn is not None and mn >= 0 and _looks_sequential(con, table, c.name, count):
            p.role = "id"
            p.notes.append("sequential unique integers treated as an identifier")
        elif (all_int and distinct <= 12 and mn is not None and mn >= 0 and mx <= 12 and not CURRENCY_NAME.search(lname)
              and not DURATION_NAME.search(lname) and not RATE_NAME.search(lname) and not re.search(r"(qty|quantity|units|count|num_|items)", lname)):
            p.role = "dimension"
            p.notes.append("small set of integer codes treated as categories")
        else:
            p.role = "measure"
        if p.role == "measure":
            if c.percent:
                p.unit = {"kind": "percent"}
                p.agg = "avg"
            elif c.currency:
                p.unit = {"kind": "currency", "symbol": c.currency}
            elif CURRENCY_NAME.search(lname) and not RATE_NAME.search(lname.replace("price", "")):
                p.unit = {"kind": "currency", "symbol": "$"}
            elif mn is not None and mn >= 0 and mx <= 1 and not all_int:
                p.unit = {"kind": "ratio"}
                p.agg = "avg"
            elif DURATION_NAME.search(lname):
                p.unit = {"kind": "number", "suffix": _duration_suffix(lname)}
                p.agg = "avg"
            if RATE_NAME.search(lname) or (negs and mn is not None and mn < 0 and RATE_NAME.search(lname)):
                p.agg = "avg"
            if "price" in lname:
                p.agg = "avg"
    elif c.dtype in ("date", "datetime"):
        mn, mx = con.execute(f"SELECT min({col}), max({col}) FROM {q(table)}").fetchone()
        p.stats = {"min": str(mn) if mn is not None else None, "max": str(mx) if mx is not None else None}
        p.role = "time"
        if c.date_ambiguous:
            p.stats["ambiguous_format"] = c.date_format
            p.stats["alternative_format"] = c.date_alternative
    elif c.dtype == "boolean":
        p.role = "flag"
        t = con.execute(f"SELECT count(*) FILTER (WHERE {col}) FROM {q(table)}").fetchone()[0]
        p.stats = {"true": int(t), "true_share": (t / count) if count else 0}
    else:
        avg_len = con.execute(f"SELECT avg(length({col})) FROM {q(table)}").fetchone()[0] or 0
        if c.leading_zero_ids or (ID_NAME.search(lname) and p.unique_ratio > 0.3):
            p.role = "id"
        elif p.unique_ratio > 0.9 and count > 50:
            p.role = "id" if avg_len < 40 else "text"
        elif avg_len > 60:
            p.role = "text"
        elif distinct <= max(60, int(0.2 * count)) or distinct <= 500:
            p.role = "dimension"
        else:
            p.role = "text"
        p.geo = bool(GEO_NAME.search(lname))
        p.stats = {"avg_length": avg_len}

    if p.role in ("dimension", "flag", "id", "text") and count:
        top = con.execute(
            f"SELECT {col}, count(*) n FROM {q(table)} WHERE {col} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 8"
        ).fetchall()
        p.top_values = [[_jsonable(v), int(n)] for v, n in top]
    return p


def _looks_sequential(con, table: str, col: str, count: int) -> bool:
    mn, mx = con.execute(f"SELECT min({q(col)}), max({q(col)}) FROM {q(table)}").fetchone()
    return mx is not None and (mx - mn + 1) <= count * 1.5


def _duration_suffix(name: str) -> str:
    for pat, suf in (("hour", " h"), ("hrs", " h"), ("min", " min"), ("sec", " s"), ("day", " days")):
        if pat in name:
            return suf
    return ""


def _jsonable(v):
    if v is None or isinstance(v, (int, float, str, bool)):
        return v
    return str(v)


def time_grain(con, table: str, col: str) -> dict:
    """Choose a reporting grain from the span and density of a time column."""
    mn, mx, days = con.execute(
        f"SELECT min({q(col)})::DATE, max({q(col)})::DATE, count(DISTINCT {q(col)}::DATE) FROM {q(table)}"
    ).fetchone()
    if mn is None:
        return {"grain": None}
    span = (mx - mn).days + 1
    if span <= 1:
        grain = "hour"
    elif span <= 62:
        grain = "day"
    elif span <= 26 * 7:
        grain = "week"
    elif span <= 5 * 366:
        grain = "month"
    elif span <= 12 * 366:
        grain = "quarter"
    else:
        grain = "year"
    has_hour = False
    try:
        has_hour = bool(con.execute(
            f"SELECT count(DISTINCT hour({q(col)})) > 4 FROM {q(table)} WHERE {q(col)} IS NOT NULL"
        ).fetchone()[0])
    except Exception:
        has_hour = False
    return {"grain": grain, "min": str(mn), "max": str(mx), "span_days": span, "distinct_days": int(days), "has_hour": has_hour}
