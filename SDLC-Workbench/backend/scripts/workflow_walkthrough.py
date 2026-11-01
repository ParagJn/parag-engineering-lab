"""Walk a throwaway project through all seven phases, offline, and try three illegal moves.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.workflow_walkthrough

No model, no network, no key, no cost, and it never reads .env. Artefact content is a plain placeholder
sentence written by this script, so the table shows the lifecycle rules, not any generated text.
"""
from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from app.llm.routing import Routing
from app.models import InvalidInput
from app.repos import Store
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine

PERSON = "human:demo"
PLACEHOLDER_AUTHOR = "human:placeholder"


@dataclass(frozen=True)
class Row:
    phase: str
    status: str
    artefacts: str
    waves: str
    next_action: str


@dataclass(frozen=True)
class Refusal:
    what: str
    refused: bool
    message: str


def render_rows(rows: Sequence[Row]) -> str:
    headers = ["phase", "status", "artefacts", "waves", "what happens next"]
    body = [[r.phase, r.status, r.artefacts, r.waves, r.next_action] for r in rows]
    widths = [max(len(str(c)) for c in col) for col in zip(headers, *body)]
    lines = ["  ".join(h.ljust(w) for h, w in zip(headers, widths)).rstrip(), "  ".join("-" * w for w in widths)]
    lines += ["  ".join(str(c).ljust(w) for c, w in zip(row, widths)).rstrip() for row in body]
    return "\n".join(lines)


def walk(workdir: Path) -> tuple[list[Row], list[Refusal]]:
    store = Store.open(workdir / "walkthrough.db")
    catalogue = load_catalogue(Routing.load().roles.keys())
    engine = WorkflowEngine(catalogue, store)
    project = store.projects.create(name="Walkthrough", actor="system")
    engine.open_project(project.id)

    refusals: list[Refusal] = []

    def attempt(what: str, call: Callable[[], object]) -> None:
        try:
            call()
        except InvalidInput as exc:
            refusals.append(Refusal(what, True, str(exc)))
        else:
            refusals.append(Refusal(what, False, "this was ALLOWED, which is a bug"))

    # Three things the rules must refuse. Done at the start, when nothing has been approved yet.
    attempt("start Requirements before Setup is approved",
            lambda: engine.start(project.id, "requirements", actor="system"))
    attempt("approve Setup although it never ran",
            lambda: store.phases.record_decision(project.id, "setup", "approve", actor=PERSON))

    def ensure_running(key: str) -> None:
        # If a rule above wrongly let a phase start early, it is already running. Carry on and let the
        # summary report the failure, rather than crashing on the very bug this script exists to show.
        if store.phases.get(project.id, key).status != "running":
            engine.start(project.id, key, actor="system")

    rows: list[Row] = []
    for phase in engine.plan_for(project).phases:
        ensure_running(phase.key)
        if phase.key == "setup":
            engine.finish(project.id, phase.key, actor="system")
            attempt("approve Setup while a required artefact is empty",
                    lambda: engine.approve(project.id, "setup", actor=PERSON))
            engine.start(project.id, phase.key, actor="system")
        for item in phase.required:  # the required ones only: that is what the gate asks for
            created = store.artefacts.create(
                project.id, artefact_type=item.key, phase_key=phase.key, title=item.name,
                actor="system", prefix=item.id_prefix,
            )
            store.artefacts.add_version(
                project.id, created.id, body=f"Placeholder for {item.name}.", author=PLACEHOLDER_AUTHOR
            )
        engine.finish(project.id, phase.key, actor="system")
        engine.approve(project.id, phase.key, actor=PERSON)
        state = next(p for p in engine.snapshot(project.id).phases if p.key == phase.key)
        rows.append(
            Row(
                phase=phase.phase.name, status=state.status,
                artefacts=f"{len(phase.required)} required of {len(phase.artefacts)}",
                waves=" | ".join("+".join(a.key for a in wave) for wave in phase.waves),
                next_action=engine.next_action(project.id),
            )
        )
    return rows, refusals


def main(argv: Sequence[str] | None = None) -> int:
    with tempfile.TemporaryDirectory(prefix="sdlc_walkthrough_") as tmp:
        rows, refusals = walk(Path(tmp))

    print(render_rows(rows))
    print("\nThings the rules must refuse:")
    for item in refusals:
        print(f"  {'REFUSED' if item.refused else 'ALLOWED'}  {item.what}")
        print(f"           {item.message}")

    approved = sum(1 for r in rows if r.status == "approved")
    correct = sum(1 for r in refusals if r.refused)
    print(f"\n{approved}/{len(rows)} phases approved, {correct}/{len(refusals)} refusals correct")
    return 0 if approved == len(rows) and correct == len(refusals) else 1


if __name__ == "__main__":
    raise SystemExit(main())
