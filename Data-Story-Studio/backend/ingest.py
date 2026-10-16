"""File ingest: CSV / Excel -> typed pandas frames -> DuckDB tables.

Everything is read as text first and typed by our own inference so we can report exactly
what happened to each column (null tokens, currency symbols stripped, ambiguous dates...).
"""

import csv
import re
import warnings
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

NULL_TOKENS = {"", "na", "n/a", "nan", "null", "none", "-", "--", "#n/a", "nil", "missing", "#value!", "#ref!"}
BOOL_TRUE = {"true", "yes", "y", "t"}
BOOL_FALSE = {"false", "no", "n", "f"}
CURRENCY_RE = re.compile(r"[$€£¥₹]")
DATE_FORMATS = [
    "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f", "%Y/%m/%d", "%Y/%m/%d %H:%M:%S",
    "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%d.%m.%Y",
    "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S",
    "%d/%m/%y", "%m/%d/%y", "%d %b %Y", "%b %d %Y", "%d-%b-%Y", "%d-%b-%y", "%b %d, %Y", "%B %d, %Y",
    "%d %B %Y", "%Y-%m", "%b %Y", "%B %Y", "%b-%y", "%Y%m%d",
]
# Day-first / month-first twins: when both parse every value the date order is ambiguous
DATE_TWINS = {
    "%d/%m/%Y": "%m/%d/%Y", "%d-%m-%Y": "%m-%d-%Y", "%d/%m/%Y %H:%M": "%m/%d/%Y %H:%M",
    "%d/%m/%Y %H:%M:%S": "%m/%d/%Y %H:%M:%S", "%d/%m/%y": "%m/%d/%y",
}
DATE_TWINS.update({v: k for k, v in list(DATE_TWINS.items())})


@dataclass
class ColumnInfo:
    name: str  # snake_case identifier used in SQL
    label: str  # original header as the user wrote it
    dtype: str  # number | date | datetime | boolean | text
    notes: list[str] = field(default_factory=list)
    currency: str = ""
    percent: bool = False
    date_format: str = ""
    date_ambiguous: bool = False
    date_alternative: str = ""
    date_mixed: bool = False
    unparsed: int = 0  # non-empty values that failed to parse and became missing
    null_tokens: int = 0  # explicit NA/null/- tokens
    leading_zero_ids: bool = False


@dataclass
class TableData:
    name: str
    source: str  # file name (+ sheet)
    frame: pd.DataFrame
    columns: list[ColumnInfo]
    skipped_lines: int = 0
    header_row: int = 0
    dropped_empty_rows: int = 0


def snake(text: str) -> str:
    s = re.sub(r"[^0-9a-zA-Z]+", "_", str(text).strip()).strip("_").lower()
    if not s:
        s = "col"
    if s[0].isdigit():
        s = f"c_{s}"
    return s


ACRONYMS = {"id", "csat", "nps", "sla", "kpi", "usd", "aud", "eur", "gbp", "inr", "sku", "kwh", "mwh", "gwh", "gst", "vat",
            "roi", "url", "ip", "uk", "us", "eu", "fy", "yoy", "mom", "aht", "fcr", "co2"}


def pretty_label(header: str) -> str:
    """'order_date' -> 'Order date', 'csat' -> 'CSAT'; headers already written for humans are kept."""
    h = header.strip()
    if not re.fullmatch(r"[a-z0-9_.\- ]+", h):
        return h
    words = [w for w in re.split(r"[_.\- ]+", h) if w]
    words = [w.upper() if w in ACRONYMS else w for w in words]
    if not words:
        return h
    if words[0] == words[0].lower():
        words[0] = words[0][:1].upper() + words[0][1:]
    return " ".join(words)


def unique_names(names: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    out = []
    for n in names:
        if n in seen:
            seen[n] += 1
            n = f"{n}_{seen[n]}"
        seen.setdefault(n, 0)
        out.append(n)
    return out


def table_name_for(stem: str, existing: set[str]) -> str:
    base = snake(stem)
    name, i = base, 2
    while name in existing:
        name, i = f"{base}_{i}", i + 1
    return name


# ---------------------------------------------------------------- readers


def _decode_sample(raw: bytes) -> tuple[str, str]:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", "replace"), "latin-1"


def read_csv_raw(path: Path) -> tuple[pd.DataFrame, int]:
    """Read every cell as text with no header (header detection happens later)."""
    with path.open("rb") as fh:
        sample, enc = _decode_sample(fh.read(65536))
    try:
        delim = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delim = ","
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        df = pd.read_csv(
            path, sep=delim, header=None, dtype=str, keep_default_na=False,
            encoding=enc, on_bad_lines="warn", engine="c",
        )
    skipped = sum(str(w.message).count("Skipping line") for w in caught)
    return df, skipped


def _cell_text(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and np.isnan(v):
        return ""
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.isoformat(sep=" ") if (v.hour or v.minute or v.second) else v.strftime("%Y-%m-%d")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def read_excel_raw(path: Path) -> list[tuple[str, pd.DataFrame]]:
    sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object)
    out = []
    for sheet, df in sheets.items():
        df = df.map(_cell_text)
        if (df != "").to_numpy().sum() == 0:
            continue
        out.append((str(sheet), df))
    return out


def apply_header(raw: pd.DataFrame) -> tuple[pd.DataFrame, list[str], int, int]:
    """Find the header row (skips title rows above a table), drop empty rows / columns."""
    raw = raw.astype(object).fillna("")
    filled = (raw.map(lambda v: str(v).strip() != ""))
    raw = raw.loc[:, filled.any(axis=0)]
    filled = filled.loc[:, raw.columns]
    counts = filled.sum(axis=1).to_numpy()
    if len(counts) == 0:
        return pd.DataFrame(), [], 0, 0
    widest = counts[: min(len(counts), 200)].max()
    header_idx = 0
    for i, c in enumerate(counts[:20]):
        if c >= max(2, 0.6 * widest) or (widest == 1 and c == 1):
            header_idx = i
            break
    headers = [str(v).strip() for v in raw.iloc[header_idx].tolist()]
    labels = [pretty_label(h) if h else f"Column {i + 1}" for i, h in enumerate(headers)]
    body = raw.iloc[header_idx + 1:].copy()
    body.columns = range(body.shape[1])
    non_empty = body.map(lambda v: str(v).strip() != "").any(axis=1)
    dropped = int((~non_empty).sum())
    body = body.loc[non_empty].reset_index(drop=True)
    return body, labels, header_idx, dropped


# ---------------------------------------------------------------- type inference


def _try_formats(sample: pd.Series, formats: list[str]) -> list[tuple[str, float]]:
    scores = []
    for fmt in formats:
        parsed = pd.to_datetime(sample, format=fmt, errors="coerce")
        scores.append((fmt, float(parsed.notna().mean())))
    return sorted(scores, key=lambda t: -t[1])


def infer_column(values: pd.Series, info: ColumnInfo, forced_date_format: str = "") -> pd.Series:
    s = values.astype(object).map(lambda v: str(v).strip())
    lower = s.str.lower()
    null_mask = lower.isin(NULL_TOKENS)
    info.null_tokens = int((null_mask & (s != "")).sum())
    s = s.where(~null_mask, None)
    present = s.dropna()
    n = len(present)
    if n == 0:
        info.dtype = "text"
        info.notes.append("column is entirely empty")
        return pd.Series([None] * len(s), dtype=object)

    uniq_lower = set(present.str.lower().unique()[:5])
    if len(uniq_lower) <= 2 and uniq_lower <= (BOOL_TRUE | BOOL_FALSE):
        info.dtype = "boolean"
        return s.map(lambda v: None if v is None else v.lower() in BOOL_TRUE).astype(object)

    if forced_date_format:
        return _as_date(s, present, info, forced_date_format)

    # numbers: tolerate thousands separators, currency symbols, %, (negatives)
    cleaned = present.str.replace(r"[,\s]", "", regex=True)
    has_cur = cleaned.str.contains(CURRENCY_RE)
    has_pct = cleaned.str.endswith("%")
    cleaned = cleaned.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    cleaned = cleaned.str.replace(r"[$€£¥₹%]", "", regex=True)
    nums = pd.to_numeric(cleaned, errors="coerce")
    ok = float(nums.notna().mean())
    looks_dateish = present.str.contains(r"^\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}", regex=True).mean() > 0.5
    if ok >= 0.95 and not looks_dateish:
        integral = present.str.fullmatch(r"\d+")
        if integral.mean() > 0.95 and present.str.match(r"^0\d").mean() > 0.02:
            info.dtype = "text"
            info.leading_zero_ids = True
            info.notes.append("numeric-looking codes with leading zeros kept as text")
            return s
        if has_cur.mean() > 0.5:
            info.currency = cleaned.index.size and present[has_cur].str.extract(f"({CURRENCY_RE.pattern})")[0].mode().iat[0]
            info.notes.append(f"currency symbol '{info.currency}' stripped")
        if has_pct.mean() > 0.5:
            info.percent = True
            info.notes.append("percent signs stripped (values are percentage points)")
        info.unparsed = int(nums.isna().sum())
        info.dtype = "number"
        out = pd.Series(np.nan, index=s.index, dtype="float64")
        out.loc[nums.index] = nums.astype("float64")
        return out

    # dates
    if present.str.contains(r"\d").mean() > 0.9 and present.str.len().max() <= 40:
        sample = pd.Series(present.unique()[:2000])
        scores = _try_formats(sample, DATE_FORMATS)
        best_fmt, best = scores[0]
        if best >= 0.95:
            return _as_date(s, present, info, best_fmt, scores)
        mixed = pd.to_datetime(sample, format="mixed", errors="coerce")
        if mixed.notna().mean() >= 0.95 and present.str.contains(r"[-/.: ]").mean() > 0.9:
            info.date_mixed = True
            info.notes.append("dates were written in several different formats")
            return _as_date(s, present, info, "mixed")

    info.dtype = "text"
    return s


def _as_date(s: pd.Series, present: pd.Series, info: ColumnInfo, fmt: str,
             scores: list[tuple[str, float]] | None = None) -> pd.Series:
    twin = DATE_TWINS.get(fmt)
    if scores and twin:
        twin_score = dict(scores).get(twin, 0.0)
        if twin_score >= 0.95:
            # both orders parse: no day > 12 anywhere, so the order cannot be told from the data
            month_first = fmt.startswith("%m")
            if not month_first:
                fmt, twin = twin, fmt
            info.date_ambiguous = True
            info.date_alternative = twin
            info.notes.append("day/month order is ambiguous; assumed month-first (MM/DD)")
    parsed = pd.to_datetime(present, format=fmt, errors="coerce")
    info.unparsed = int(parsed.isna().sum())
    info.date_format = fmt
    has_time = bool(((parsed.dt.hour != 0) | (parsed.dt.minute != 0)).fillna(False).any())
    info.dtype = "datetime" if has_time else "date"
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[us]")
    out.loc[parsed.index] = parsed.astype("datetime64[us]")
    return out


def build_table(name: str, source: str, raw: pd.DataFrame, skipped: int = 0,
                overrides: dict | None = None) -> TableData:
    body, labels, header_idx, dropped = apply_header(raw)
    names = unique_names([snake(lbl) for lbl in labels])
    overrides = overrides or {}
    cols: list[ColumnInfo] = []
    data = {}
    for i, (nm, lbl) in enumerate(zip(names, labels)):
        info = ColumnInfo(name=nm, label=lbl, dtype="text")
        forced = (overrides.get(nm) or {}).get("date_format", "")
        col = body[i] if i in body.columns else pd.Series([""] * len(body))
        data[nm] = infer_column(col, info, forced)
        cols.append(info)
    frame = pd.DataFrame(data)
    return TableData(name=name, source=source, frame=frame, columns=cols,
                     skipped_lines=skipped, header_row=header_idx, dropped_empty_rows=dropped)


def read_file(path: Path, existing_names: set[str], overrides: dict | None = None,
              display_name: str = "") -> list[TableData]:
    """Read one uploaded file into one table (CSV) or one table per non-empty sheet (Excel)."""
    overrides = overrides or {}
    suffix = path.suffix.lower()
    shown = Path(display_name or path.name)
    out: list[TableData] = []
    if suffix in (".csv", ".tsv", ".txt"):
        raw, skipped = read_csv_raw(path)
        name = table_name_for(shown.stem, existing_names)
        existing_names.add(name)
        out.append(build_table(name, shown.name, raw, skipped, overrides.get(name)))
    elif suffix in (".xlsx", ".xlsm", ".xls"):
        sheets = read_excel_raw(path)
        for sheet, raw in sheets:
            stem = shown.stem if len(sheets) == 1 else f"{shown.stem}_{sheet}"
            name = table_name_for(stem, existing_names)
            existing_names.add(name)
            out.append(build_table(name, f"{shown.name} › {sheet}", raw, 0, overrides.get(name)))
    else:
        raise ValueError(f"Unsupported file type: {shown.name} (use CSV or Excel)")
    return out


def write_duckdb(con, table: TableData) -> None:
    """Materialise a typed frame as a DuckDB table with explicit column types."""
    frame = table.frame.copy()
    casts = []
    for c in table.columns:
        if c.dtype == "text":
            frame[c.name] = frame[c.name].astype(object)
        casts.append(f'CAST("{c.name}" AS {_duck_type(c.dtype)}) AS "{c.name}"')
    con.register("_ingest_df", frame)
    try:
        con.execute(f'CREATE OR REPLACE TABLE "{table.name}" AS SELECT {", ".join(casts)} FROM _ingest_df')
    finally:
        con.unregister("_ingest_df")


def _duck_type(dtype: str) -> str:
    return {"number": "DOUBLE", "date": "DATE", "datetime": "TIMESTAMP", "boolean": "BOOLEAN"}.get(dtype, "VARCHAR")
