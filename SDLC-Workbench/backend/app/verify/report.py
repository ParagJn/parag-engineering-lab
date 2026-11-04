"""The result of a run, as counts and lists (S20b). Plain data in, plain data out."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from .match import DIFFERENCES, FOUND, NOT_FOUND, POSSIBLE, STATES, WEAK, Extra, Match

AREAS = ("endpoint", "table", "rule")
AREA_WORDS = {"endpoint": "Endpoints", "table": "Tables", "rule": "Rules"}
STATE_WORDS = {
    FOUND: "Found", DIFFERENCES: "Found with differences", POSSIBLE: "Possible", NOT_FOUND: "Not found", WEAK: "Weak evidence",
}
# One sentence for the screen and the download, so a person never has to decode a colour.
ADVICE = ("This shows how far the backend of the build has drifted from the design: endpoints, tables and rules. A real build always differs from its design, so this is a "
          "highlighter, not a pass or fail, and it never runs your code.")


@dataclass(frozen=True)
class AreaCounts:
    area: str
    designed: int
    found: int
    differences: int
    possible: int
    not_found: int
    weak: int
    extras: int

    @property
    def share_found(self) -> float:
        """The share of designed items that were found, with or without differences (0 when the design has none). A possible match does not count."""
        return round((self.found + self.differences) / self.designed, 3) if self.designed else 0.0


@dataclass
class Report:
    areas: list[AreaCounts] = field(default_factory=list)
    matches: list[Match] = field(default_factory=list)
    extras: list[Extra] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)                        # what could not be read, in plain words


def counts_of(matches: Sequence[Match], extras: Sequence[Extra]) -> list[AreaCounts]:
    out = []
    for area in AREAS:
        mine = [m for m in matches if m.area == area]
        n = lambda state: sum(1 for m in mine if m.state == state)           # noqa: E731
        out.append(AreaCounts(area, len(mine), n(FOUND), n(DIFFERENCES), n(POSSIBLE), n(NOT_FOUND), n(WEAK), sum(1 for e in extras if e.area == area)))
    return out


def build_report(matches: Sequence[Match], extras: Sequence[Extra], notes: Sequence[str] = ()) -> Report:
    ordered = sorted(matches, key=lambda m: (AREAS.index(m.area), m.designed))
    shown = sorted(extras, key=lambda e: (AREAS.index(e.area), e.built, e.file, e.line))
    return Report(counts_of(ordered, shown), list(ordered), list(shown), list(notes))


def markdown(report: Report, *, design_versions: dict[str, int] | None = None) -> str:
    """The report as Markdown for a person: counts first, then each item with its state in words (never only a symbol)."""
    lines = ["# Build Verify", "", ADVICE, "", "## Summary", "", "| Area | Designed | Found | With differences | Possible | Not found | Weak evidence | Built but not designed |", "|---|---|---|---|---|---|---|---|"]
    for c in report.areas:
        lines.append(f"| {AREA_WORDS[c.area]} | {c.designed} | {c.found} | {c.differences} | {c.possible} | {c.not_found} | {c.weak} | {c.extras} |")
    for area in AREAS:
        mine = [m for m in report.matches if m.area == area]
        if not mine:
            continue
        lines += ["", f"## {AREA_WORDS[area]}", ""]
        for m in mine:
            where = f" ({m.file}:{m.line})" if m.file else ""
            how = f" [matched by {m.step}, score {m.score}]" if m.step else ""
            lines.append(f"- **{m.designed}** {STATE_WORDS[m.state]}" + (f": `{m.built}`{where}{how}" if m.built else "") + (f". {m.note}" if m.note else ""))
            lines += [f"  - {d}" for d in m.differences]
    if report.extras:
        lines += ["", "## Built but not designed", ""]
        lines += [f"- {AREA_WORDS[e.area][:-1]} `{e.built}` ({e.file}:{e.line})" if e.line else f"- {AREA_WORDS[e.area][:-1]} `{e.built}` ({e.file})" for e in report.extras]
    if report.notes:
        lines += ["", "## What could not be read", ""] + [f"- {n}" for n in report.notes]
    if design_versions:
        lines += ["", "## Compared against", ""] + [f"- {k}: version {v}" for k, v in sorted(design_versions.items())]
    return "\n".join(lines) + "\n"
