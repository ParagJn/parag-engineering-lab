"""Which of the catalogue's artefacts have a skill yet.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.skills_report

Offline and free. It reads the catalogue and the skill files, and nothing else.
"""
from __future__ import annotations

from typing import Sequence

from app.agents.skills import SkillLibrary
from app.llm.routing import Routing
from app.workflow.definitions import Catalogue, load_catalogue


def build_rows(catalogue: Catalogue, library: SkillLibrary) -> list[tuple[str, str, str, str]]:
    rows = []
    for phase in catalogue.phases:
        for item in phase.artefacts:
            rows.append((phase.name, item.name, "required" if item.required else "optional",
                         "skill" if library.has(item.key) else "no skill yet"))
    return rows


def render(rows: Sequence[tuple[str, str, str, str]]) -> str:
    headers = ("phase", "artefact", "", "skill")
    widths = [max(len(str(c)) for c in col) for col in zip(headers, *rows)]
    lines = ["  ".join(h.ljust(w) for h, w in zip(headers, widths)).rstrip(),
             "  ".join("-" * w for w in widths)]
    lines += ["  ".join(str(c).ljust(w) for c, w in zip(row, widths)).rstrip() for row in rows]
    have = sum(1 for r in rows if r[3] == "skill")
    required_missing = sum(1 for r in rows if r[2] == "required" and r[3] != "skill")
    lines += ["", f"{have} of {len(rows)} artefacts have a skill; {required_missing} required artefacts still need one"]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    catalogue = load_catalogue(Routing.load().roles.keys())
    print(render(build_rows(catalogue, SkillLibrary.load(catalogue))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
