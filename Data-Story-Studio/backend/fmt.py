"""Number / date formatting shared by facts, narratives and panel metadata.

Every number the dashboard shows in text is produced here from a computed value, so the
LLM never has to (and is never allowed to) type a figure itself.
"""

import math
from datetime import date, datetime
from typing import Any

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def compact(v: float, decimals: int | None = None) -> str:
    """1,284 / 12.9K / 4.2M / 1.3B — auto-compact from 10,000 up."""
    if not is_num(v):
        return "—"
    a = abs(v)
    for div, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= max(div, 1e4):
            x = v / div
            d = 1 if decimals is None else decimals
            if abs(x) >= 100:
                d = 0
            return f"{x:,.{d}f}".rstrip("0").rstrip(".") + suffix if d else f"{x:,.0f}{suffix}"
    if decimals is None:
        if a == 0 or float(v).is_integer():
            decimals = 0
        elif a >= 100:
            decimals = 0
        elif a >= 10:
            decimals = 1
        else:
            decimals = 2
    out = f"{v:,.{decimals}f}"
    if "." in out:
        out = out.rstrip("0").rstrip(".")
    return out


def fmt_value(v: Any, unit: dict | None = None) -> str:
    """Format a measure value according to its unit spec {kind, symbol}."""
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "—"
    if not is_num(v):
        return str(v)
    kind = (unit or {}).get("kind", "number")
    if kind == "currency":
        sym = unit.get("symbol") or ""
        s = compact(abs(v), 2 if abs(v) < 100 and not float(v).is_integer() else None)
        return f"-{sym}{s}" if v < 0 else f"{sym}{s}"
    if kind == "percent":  # value already in percentage points (45 -> 45%)
        return f"{compact(v, 1)}%"
    if kind == "ratio":  # 0..1 -> 45%
        return f"{compact(v * 100, 1)}%"
    return compact(v) + (unit or {}).get("suffix", "")


def fmt_change(rel: float | None) -> str:
    """Signed relative change: +23.4% / -5.1%."""
    if rel is None or not is_num(rel):
        return "—"
    pct = rel * 100
    d = 0 if abs(pct) >= 100 else 1
    return f"{'+' if pct > 0 else ''}{pct:,.{d}f}%"


def fmt_pct(share: float | None, decimals: int = 0) -> str:
    """Unsigned share 0..1 -> 42%."""
    if share is None or not is_num(share):
        return "—"
    pct = share * 100
    if decimals == 0 and 0 < pct < 1:
        return "<1%"
    return f"{pct:.{decimals}f}%"


def fmt_points(diff: float, unit: dict | None) -> str:
    """Absolute difference, used for rates where relative change is misleading."""
    kind = (unit or {}).get("kind")
    if kind in ("ratio", "percent"):
        pts = compact(abs(diff) * (100 if kind == "ratio" else 1), 1)
        return f"{'+' if diff > 0 else '-' if diff < 0 else ''}{pts} pts"
    s = fmt_value(abs(diff), unit)
    return f"{'+' if diff > 0 else '-' if diff < 0 else ''}{s}"


def to_date(v: Any) -> date | None:
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str):
        try:
            return datetime.fromisoformat(v).date()
        except ValueError:
            return None
    return None


def fmt_period(v: Any, grain: str) -> str:
    d = to_date(v)
    if d is None:
        return str(v)
    if grain == "year":
        return str(d.year)
    if grain == "quarter":
        return f"Q{(d.month - 1) // 3 + 1} {d.year}"
    if grain == "month":
        return f"{MONTHS[d.month - 1]} {d.year}"
    if grain == "week":
        return f"week of {d.day} {MONTHS[d.month - 1]} {d.year}"
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def fmt_range(a: Any, b: Any, grain: str) -> str:
    sa, sb = fmt_period(a, grain), fmt_period(b, grain)
    return sa if sa == sb else f"{sa} – {sb}"


def number_variants(v: float) -> set[str]:
    """Strings a correctly-cited number might appear as in prose (for the number guard)."""
    out: set[str] = set()
    if not is_num(v):
        return out
    for x in (v, v * 100):
        a = abs(x)
        out.add(compact(a))
        out.add(compact(a, 0))
        out.add(compact(a, 1))
        out.add(compact(a, 2))
        out.add(f"{a:,.0f}")
        out.add(f"{a:.0f}")
        out.add(f"{a:,.1f}")
        out.add(f"{a:.1f}")
        out.add(f"{a:,.2f}")
    return {s.replace(",", "") for s in out}
