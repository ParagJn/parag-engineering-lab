"""Write docs/08-workflow-catalogue.md from the phase YAML, so the document you review is never out of date.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.render_catalogue          # rewrite the file
    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.render_catalogue --check  # exit 1 if stale

A test runs the same check, so editing a YAML file without regenerating the document fails the suite.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Sequence

from app.llm.routing import Routing
from app.workflow.definitions import Catalogue, load_catalogue
from app.workflow.plan import build_plan

DOC_PATH = Path(__file__).resolve().parents[2] / "docs" / "08-workflow-catalogue.md"

HEADER = """\
# 08 · Workflow catalogue

> Generated from `backend/app/phases/definitions/*.yaml` by `scripts/render_catalogue.py`. **Do not edit by hand:**
> change the YAML, then run the script. A test fails if this file and the YAML disagree.

The lifecycle has {phases} phases and {artefacts} artefacts, {required} of them required. A **required**
artefact cannot be switched off in the wizard and must have content before its phase can be approved. An
artefact in a later **wave** waits for the ones in earlier waves; everything inside a wave runs in parallel.
Deploy and BAU Handover are this prototype's own design; the source material stops at Code & Test.
"""


def _row(cells: Sequence[str]) -> str:
    return "| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |"


def render(catalogue: Catalogue) -> str:
    plan = build_plan(catalogue, None)
    out = [HEADER.format(phases=len(catalogue.phases), artefacts=catalogue.artefact_count, required=catalogue.required_count)]
    out.append("## At a glance\n")
    out.append(_row(["#", "Phase", "Approver", "Artefacts", "Required", "Parallel waves"]))
    out.append(_row(["---"] * 6))
    for phase in plan.phases:
        out.append(_row([
            str(phase.phase.order), phase.phase.name, phase.phase.approver,
            str(len(phase.artefacts)), str(len(phase.required)), str(len(phase.waves)),
        ]))

    for phase in plan.phases:
        wave_of = {a.key: n for n, wave in enumerate(phase.waves, start=1) for a in wave}
        out.append(f"\n## {phase.phase.order} · {phase.phase.name}\n")
        out.append(f"{phase.phase.summary}  \nApproved by: **{phase.phase.approver}**.\n")
        out.append(_row(["Artefact", "Required", "Wave", "Waits for", "Agent role", "ID prefix", "What it is"]))
        out.append(_row(["---"] * 7))
        names = {a.key: a.name for a in phase.artefacts}
        for item in phase.artefacts:
            out.append(_row([
                item.name, "yes" if item.required else "no", str(wave_of[item.key]),
                ", ".join(names[d] for d in item.after) or "-", item.role, item.id_prefix, item.description,
            ]))
    out.append("")
    return "\n".join(out)


def build() -> str:
    return render(load_catalogue(Routing.load().roles.keys()))


def main(argv: Sequence[str] | None = None) -> int:
    check = "--check" in (argv if argv is not None else sys.argv[1:])
    text = build()
    if check:
        current = DOC_PATH.read_text(encoding="utf-8") if DOC_PATH.exists() else ""
        if current != text:
            print(f"{DOC_PATH.name} is out of date; run: python -m scripts.render_catalogue", file=sys.stderr)
            return 1
        print(f"{DOC_PATH.name} is up to date")
        return 0
    DOC_PATH.write_text(text, encoding="utf-8")
    print(f"wrote {DOC_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
