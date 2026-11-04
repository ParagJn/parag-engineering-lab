"""Shared by the S17a tests: a Build artefact body made from (path, text) pairs."""
from __future__ import annotations


def make_body(entries: list[tuple[str, str]], prefix: str, *, listed: list[str] | None = None, fence: str = "```") -> str:
    """A Build artefact body: `Files` lists the paths in `listed` (default: all), `Code` holds a block per entry."""
    listed = [p for p, _ in entries] if listed is None else listed
    lines = ["## Overview", "Two files.", "", "## Files"]
    for number, path in enumerate(listed, start=1):
        lines.append(f"- {prefix}-{number:03d} {path}: what it does. Derives from: TBL-001")
    lines += ["", "## Code"]
    for path, text in entries:
        lines += [f"File: {path}", f"{fence}python", text.rstrip("\n"), fence, ""]
    lines += ["## Coverage check", "None", "", "## Open questions", "None"]
    return "\n".join(lines)


DB_FILES = [("db/schema.sql", "CREATE TABLE IF NOT EXISTS t (id INTEGER PRIMARY KEY);"), ("db/init_db.py", "print(1)")]
