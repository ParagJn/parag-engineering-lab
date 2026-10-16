"""Data-readiness gate: decides pass / warn / block from computed numbers before any dashboard.

Checks
  - volume: fewer than MIN_ROWS records -> ask for more data (override: "analyse anyway")
  - relationships: with several files, find joins (shared keys with value overlap) or unions
    (same columns); unrelated files -> ask how they link or keep them separate
  - quality: mostly-missing columns, duplicate rows, nothing to trend or measure,
    ambiguous / mixed dates, numeric-looking IDs, rows that failed to parse
  - shape: "long" tables where a column names the measure each row holds -> one scope per measure
"""

import re
from dataclasses import asdict, dataclass, field

from fmt import compact, fmt_pct
from profile import ColumnProfile, q


@dataclass
class Issue:
    id: str
    severity: str  # block | warn | info
    title: str
    detail: str
    suggestion: str = ""
    table: str = ""
    column: str = ""
    fix: dict | None = None  # optional one-click fix the UI can offer

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Relationship:
    kind: str  # join | union
    left: str
    right: str
    left_col: str = ""
    right_col: str = ""
    left_match: float = 0.0  # share of left rows whose key exists on the right
    right_match: float = 0.0
    cardinality: str = ""  # many-to-one | one-to-one | one-to-many | many-to-many
    confidence: str = ""  # strong | weak
    shared_columns: list = field(default_factory=list)
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _key_candidates(cols: list[ColumnProfile]) -> list[ColumnProfile]:
    return [c for c in cols if c.role in ("id", "dimension") and c.count > 0 and c.dtype in ("text", "number")]


def _norm_key(name: str, table: str) -> set[str]:
    """Name variants so that orders.region_id ~ regions.id ~ regions.region_id."""
    n = name.lower()
    out = {n}
    t = table.lower().rstrip("s")
    if n in ("id", "code", "key"):
        out |= {f"{t}_{n}", f"{t}{n}", f"{table.lower()}_{n}"}
    for suf in ("_id", "_code", "_key", "id"):
        if n.endswith(suf) and len(n) > len(suf):
            out.add(n[: -len(suf)])
    return out


def find_relationships(con, tables: dict[str, list[ColumnProfile]], rows: dict[str, int]) -> list[Relationship]:
    names = list(tables)
    rels: list[Relationship] = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ca = {c.name: c for c in tables[a]}
            cb = {c.name: c for c in tables[b]}
            # union: (almost) the same column set -> the files are parts of one dataset
            shared = set(ca) & set(cb)
            if shared and len(shared) >= 0.8 * max(len(ca), len(cb)) and len(shared) >= 2:
                same_types = all(ca[s].dtype == cb[s].dtype for s in shared)
                rels.append(Relationship(
                    kind="union", left=a, right=b, shared_columns=sorted(shared),
                    confidence="strong" if same_types else "weak",
                    detail=f"{len(shared)} of {max(len(ca), len(cb))} columns match by name"
                           + ("" if same_types else " (some types differ)"),
                ))
                continue
            best: Relationship | None = None
            for ka in _key_candidates(tables[a]):
                for kb in _key_candidates(tables[b]):
                    if ka.dtype != kb.dtype:
                        continue
                    if not (_norm_key(ka.name, a) & _norm_key(kb.name, b)):
                        continue
                    rel = _measure_join(con, a, ka, b, kb, rows)
                    if rel and (best is None or (rel.left_match + rel.right_match) > (best.left_match + best.right_match)):
                        best = rel
            if best is None:
                # no name match: try value overlap on the most key-like columns only
                for ka in [c for c in _key_candidates(tables[a]) if c.role == "id" or c.unique_ratio > 0.5][:4]:
                    for kb in [c for c in _key_candidates(tables[b]) if c.role == "id" or c.unique_ratio > 0.5][:4]:
                        if ka.dtype != kb.dtype:
                            continue
                        rel = _measure_join(con, a, ka, b, kb, rows)
                        if rel and rel.confidence == "strong" and (best is None or rel.left_match > best.left_match):
                            best = rel
            if best:
                rels.append(best)
    return rels


def _measure_join(con, a: str, ka: ColumnProfile, b: str, kb: ColumnProfile, rows: dict[str, int]) -> Relationship | None:
    la, lb = q(ka.name), q(kb.name)
    left_match, right_match = con.execute(f"""
        SELECT
          (SELECT count(*) FROM {q(a)} x WHERE x.{la} IN (SELECT y.{lb} FROM {q(b)} y)) ,
          (SELECT count(*) FROM {q(b)} y WHERE y.{lb} IN (SELECT x.{la} FROM {q(a)} x))
    """).fetchone()
    lm = left_match / rows[a] if rows[a] else 0
    rm = right_match / rows[b] if rows[b] else 0
    if lm == 0 and rm == 0:
        return None
    a_unique = ka.distinct == ka.count
    b_unique = kb.distinct == kb.count
    card = {
        (False, True): "many-to-one", (True, False): "one-to-many",
        (True, True): "one-to-one", (False, False): "many-to-many",
    }[(a_unique, b_unique)]
    strong = max(lm, rm) >= 0.8 and card != "many-to-many"
    return Relationship(
        kind="join", left=a, right=b, left_col=ka.name, right_col=kb.name,
        left_match=lm, right_match=rm, cardinality=card, confidence="strong" if strong else "weak",
        detail=f"{a}.{ka.name} ↔ {b}.{kb.name}: {fmt_pct(lm)} of {a} rows and {fmt_pct(rm)} of {b} rows match ({card})",
    )


def assess(con, tables: dict[str, list[ColumnProfile]], rows: dict[str, int], ingest_info: dict,
           relationships: list[Relationship], min_rows: int) -> dict:
    issues: list[Issue] = []
    total_rows = sum(rows.values())

    # ---- volume (fact table = the largest one; lookups don't add analysable records)
    fact = max(rows, key=rows.get) if rows else ""
    union_rows = _union_rows(relationships, rows, fact)
    analysable = union_rows or rows.get(fact, 0)
    if analysable < min_rows:
        issues.append(Issue(
            id="low_volume", severity="block",
            title=f"Only {compact(analysable)} records — more data recommended",
            detail=(f"The main dataset has {compact(analysable)} rows; reliable trends, outliers and "
                    f"correlations need at least {compact(min_rows)}. With this little data, patterns "
                    "are easily noise."),
            suggestion=_volume_suggestion(tables.get(fact, []), ingest_info),
        ))

    # ---- relationships between files
    if len(tables) > 1:
        linked = set()
        for r in relationships:
            if r.confidence == "strong":
                linked |= {r.left, r.right}
        unlinked = [t for t in tables if t not in linked]
        weak = [r for r in relationships if r.confidence == "weak"]
        if unlinked:
            issues.append(Issue(
                id="unrelated_files", severity="block",
                title=(f"{len(unlinked)} file{'s' if len(unlinked) > 1 else ''} not clearly linked to the others"),
                detail=("No shared key column with matching values was found for: "
                        + ", ".join(unlinked) + "."
                        + (" Weak candidates: " + "; ".join(r.detail for r in weak) + "." if weak else "")),
                suggestion="Tell us which columns link the files, or analyse each file separately.",
            ))
        for r in relationships:
            if r.kind == "join" and r.confidence == "strong" and min(r.left_match, r.right_match) < 0.95:
                issues.append(Issue(
                    id=f"partial_join_{r.left}_{r.right}", severity="warn",
                    title=f"Not every {r.left} row finds a match in {r.right}",
                    detail=r.detail + ". Unmatched rows are kept but have no value for the linked columns.",
                    suggestion="Check for missing reference rows or differently formatted keys.",
                ))

    # ---- per-table quality
    long_format = {}
    for t, cols in tables.items():
        lf = detect_long_format(con, t, cols) if rows[t] else None
        if lf:
            long_format[t] = lf
            shown = ", ".join(lf["values"][:4]) + (f" and {len(lf['values']) - 4} more" if len(lf["values"]) > 4 else "")
            issues.append(Issue(
                id=f"long_{t}", severity="info", table=t, column=lf["column"],
                title=f"‘{lf['label']}’{' in ' + t if len(tables) > 1 else ''} holds {lf['total']} different measures — each gets its own dashboard",
                detail=(f"Each row records one measure ({shown}) and the values are on very different scales "
                        f"(typical values differ {compact(lf['spread'])}×), so adding them together would mix units."
                        + (f" The {MAX_SLICES} largest are analysed." if lf["total"] > MAX_SLICES else "")),
            ))
        n = rows[t]
        where = f" in {t}" if len(tables) > 1 else ""
        info = ingest_info.get(t, {})
        if info.get("skipped_lines"):
            issues.append(Issue(
                id=f"bad_lines_{t}", severity="warn", table=t,
                title=f"{info['skipped_lines']} malformed lines skipped in {t}",
                detail="These lines had a different number of fields than the header.",
                suggestion="Check for unquoted commas inside values.",
            ))
        if n:
            dups = n - con.execute(f"SELECT count(*) FROM (SELECT DISTINCT * FROM {q(t)})").fetchone()[0]
            if dups:
                issues.append(Issue(
                    id=f"dupes_{t}", severity="warn" if dups / n > 0.01 else "info", table=t,
                    title=f"{compact(dups)} duplicate rows in {t} ({fmt_pct(dups / n, 1)})",
                    detail="Rows that are identical in every column. They inflate counts and totals.",
                    suggestion="Remove exact duplicates before analysis.",
                    fix={"action": "dedupe", "table": t},
                ))
        measures = [c for c in cols if c.role == "measure"]
        times = [c for c in cols if c.role == "time"]
        dims = [c for c in cols if c.role in ("dimension", "flag")]
        if not times:
            issues.append(Issue(
                id=f"no_time_{t}", severity="info", table=t,
                title=f"No date column in {t}",
                detail="Trends over time can't be shown; the dashboard will focus on composition and comparison.",
            ))
        if not measures and not dims and not times:
            issues.append(Issue(
                id=f"nothing_{t}", severity="block", table=t,
                title=f"{t} has nothing to analyse",
                detail="No numeric measures, categories or dates were detected — only identifiers or free text.",
                suggestion="Check the file has a header row and is a data table, not a report.",
            ))
        for c in cols:
            if c.missing_pct >= 0.5 and c.missing_pct < 1:
                issues.append(Issue(
                    id=f"missing_{t}_{c.name}", severity="warn", table=t, column=c.name,
                    title=f"‘{c.label}’{where} is {fmt_pct(c.missing_pct)} empty",
                    detail="Missing values are excluded from calculations (not treated as zero).",
                ))
            elif c.missing_pct == 1:
                issues.append(Issue(
                    id=f"empty_{t}_{c.name}", severity="info", table=t, column=c.name,
                    title=f"‘{c.label}’ is completely empty and will be ignored", detail="",
                ))
            if c.stats.get("ambiguous_format"):
                alt = c.stats["alternative_format"]
                issues.append(Issue(
                    id=f"ambiguous_date_{t}_{c.name}", severity="warn", table=t, column=c.name,
                    title=f"Dates in ‘{c.label}’ could be day-first or month-first",
                    detail=(f"No value has a day above 12, so the order can't be detected. "
                            f"Currently read as {_fmt_name(c.stats['ambiguous_format'])} "
                            f"({c.stats.get('min')} → {c.stats.get('max')})."),
                    suggestion=f"Switch to {_fmt_name(alt)} if that's how your dates are written.",
                    fix={"action": "date_format", "table": t, "column": c.name, "format": alt,
                         "label": f"Read as {_fmt_name(alt)}"},
                ))
            if any("several different formats" in nt for nt in c.notes):
                issues.append(Issue(
                    id=f"mixed_date_{t}_{c.name}", severity="warn", table=t, column=c.name,
                    title=f"‘{c.label}’ mixes several date formats",
                    detail="Dates were parsed individually; ambiguous values like 03/04 may be misread.",
                    suggestion="Export dates in one format (ISO YYYY-MM-DD is safest).",
                ))
            unparsed = _unparsed(info, c.name)
            if unparsed and c.count:
                issues.append(Issue(
                    id=f"unparsed_{t}_{c.name}", severity="warn" if unparsed / max(n, 1) > 0.01 else "info",
                    table=t, column=c.name,
                    title=f"{compact(unparsed)} values in ‘{c.label}’ couldn't be read as {c.dtype}",
                    detail="They are treated as missing.",
                ))
            if any("leading zeros" in nt for nt in c.notes):
                issues.append(Issue(
                    id=f"idcodes_{t}_{c.name}", severity="info", table=t, column=c.name,
                    title=f"‘{c.label}’{where} looks like codes, kept as text",
                    detail="Values have leading zeros, so they're identifiers rather than numbers.",
                ))
            if c.role == "id" and c.dtype == "number":
                issues.append(Issue(
                    id=f"numid_{t}_{c.name}", severity="info", table=t, column=c.name,
                    title=f"‘{c.label}’{where} treated as an identifier",
                    detail="It's a numeric code, so it is used for grouping and linking, never summed or averaged.",
                ))
        if measures and not times and not dims:
            issues.append(Issue(
                id=f"flat_{t}", severity="warn", table=t,
                title=f"{t} has numbers but nothing to group them by",
                detail="Only distributions and correlations can be shown.",
            ))

    order = {"block": 0, "warn": 1, "info": 2}
    issues.sort(key=lambda i: order[i.severity])
    status = "block" if any(i.severity == "block" for i in issues) else "warn" if any(i.severity == "warn" for i in issues) else "pass"
    return {
        "status": status,
        "total_rows": total_rows,
        "analysable_rows": analysable,
        "fact_table": fact,
        "min_rows": min_rows,
        "issues": [i.to_dict() for i in issues],
        "relationships": [r.to_dict() for r in relationships],
        "long_format": long_format,
    }


METRIC_NAME = re.compile(r"(measure|metric|indicator|variable|kpi|series|attribute|parameter|statistic|^item)")
MAX_SLICES = 20


def detect_long_format(con, table: str, cols: list[ColumnProfile]) -> dict | None:
    """A text column naming what each row measures, whose values put the numbers on very different scales.

    Summing or averaging across those rows mixes units, so each measure is analysed on its own.
    """
    values = [c for c in cols if c.role == "measure"]
    if not values:
        return None
    for mc in cols:
        if mc.dtype != "text" or mc.role != "dimension" or not 2 <= mc.distinct <= 60 or not METRIC_NAME.search(mc.name):
            continue
        m = q(mc.name)
        spread = 0.0
        for v in values:
            meds = [r[0] for r in con.execute(
                f"SELECT median(abs({q(v.name)})) FROM {q(table)} WHERE {m} IS NOT NULL AND {q(v.name)} IS NOT NULL "
                f"GROUP BY {m} HAVING count(*) >= 5").fetchall() if r[0]]
            if len(meds) >= 2:
                spread = max(spread, max(meds) / min(meds))
        if spread < 20:
            continue
        groups = con.execute(f"SELECT {m}, count(*) FROM {q(table)} WHERE {m} IS NOT NULL GROUP BY 1 ORDER BY 2 DESC, 1").fetchall()
        return {"column": mc.name, "label": mc.label, "values": [str(g[0]) for g in groups[:MAX_SLICES]],
                "rows": {str(g[0]): int(g[1]) for g in groups[:MAX_SLICES]}, "spread": spread, "total": len(groups)}
    return None


def _union_rows(rels: list[Relationship], rows: dict[str, int], fact: str) -> int:
    group = {fact}
    changed = True
    while changed:
        changed = False
        for r in rels:
            if r.kind == "union" and r.confidence == "strong" and (r.left in group) != (r.right in group):
                group |= {r.left, r.right}
                changed = True
    return sum(rows[t] for t in group) if len(group) > 1 else 0


def _volume_suggestion(cols: list[ColumnProfile], info: dict) -> str:
    times = [c for c in cols if c.role == "time"]
    dims = [c for c in cols if c.role == "dimension"]
    tips = []
    if times:
        t = times[0]
        tips.append(f"add more history (‘{t.label}’ currently covers {t.stats.get('min', '?')[:10]} to {t.stats.get('max', '?')[:10]})")
    if dims:
        tips.append(f"include all values of ‘{dims[0].label}’ rather than a filtered extract")
    tips.append("export the detailed records rather than a summary")
    return "Try to " + "; ".join(tips) + "."


def _unparsed(info: dict, col: str) -> int:
    return int((info.get("unparsed") or {}).get(col, 0))


def _fmt_name(fmt: str) -> str:
    if fmt.startswith("%d"):
        return "day-first (DD/MM)"
    if fmt.startswith("%m"):
        return "month-first (MM/DD)"
    return fmt
