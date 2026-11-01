"""Ask the context store five questions and show what it finds, offline.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.context_demo

No model, no network, no key, no cost, and it never reads .env. Everything it searches is invented: a
made-up meeting-room office policy, a short charter and a feedback note. The point is for YOU to look at
the ranked results and judge whether they are sensible, which a test can only check on a fixed example.
"""
from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from app.llm.routing import Routing
from app.repos import Store
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine

PERSON = "human:demo"

POLICY = """\
# Meeting Room Policy

This note describes how staff use the meeting rooms on floors two to four. It is a fictional policy
written for this demonstration.

## Booking rules

Any member of staff may book a room for up to four hours at a time. Rooms can be booked only during
office hours, which are 08:00 to 18:00 on weekdays. A room cannot be booked twice for the same slot:
the second request is refused and the person is shown the next free time.

## Cancellation

A booking can be cancelled free of charge up to 24 hours before it starts. A cancellation made later
than that still counts as used, and the cost centre of the person who booked is charged for the slot.
Bookings that nobody attends within 15 minutes of the start are released automatically.

## Equipment

Every room has a display and a speakerphone. The Atlas room on floor three also has a video-conference
camera. Faulty equipment should be reported to the facilities desk, never fixed by staff.

## Peak periods

Monday mornings and Thursday afternoons are the busiest times. During peak periods a booking is limited
to two hours so that more teams can use the rooms.
"""

CHARTER = """\
# Project charter

The Meeting Room Booking system lets staff find a free room, reserve it, and cancel it. It must prevent
double bookings and must respect office hours. The first release covers floors two to four only.

## Success measures

Fewer than one double booking per month, and at least 90 percent of bookings made without help.
"""

FEEDBACK = "Add a non-functional requirement for peak load: the system must stay responsive on Monday mornings."


@dataclass(frozen=True)
class Question:
    text: str
    expect_prefix: str  # the top hit's source ID must start with this
    note: str


QUESTIONS = (
    Question("How late can I cancel a booking without being charged?", "DOC-001#", "from the policy note"),
    Question("What equipment is in the Atlas room?", "DOC-001#", "from the policy note"),
    Question("Can the system allow two bookings of the same room?", "SET-CHR-001@v1#", "from the approved charter"),
    Question("How should the system behave on Monday mornings?", "MEM-", "from the feedback note"),
    Question("Who fixes a broken speakerphone?", "DOC-001#", "from the policy note"),
)


@dataclass(frozen=True)
class Answer:
    question: Question
    top: str
    ok: bool
    lines: tuple[str, ...]


def one_line(text: str, width: int = 100) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= width else flat[: width - 1] + "…"


def build(workdir: Path) -> tuple[Store, str, str, int]:
    """A throwaway project holding the policy, an approved charter and a feedback note."""
    store = Store.open(workdir / "demo.db")
    engine = WorkflowEngine(load_catalogue(Routing.load().roles.keys()), store)
    project = store.projects.create(name="Context demo", actor="system")
    other = store.projects.create(name="Some other project", actor="system")
    engine.open_project(project.id)

    document = store.context.add_document(project.id, "meeting-room-policy.md", POLICY.encode(), actor=PERSON)

    engine.start(project.id, "setup", actor="system")
    charter = store.artefacts.create(
        project.id, artefact_type="project_charter", phase_key="setup", title="Project charter",
        actor="system", prefix="SET-CHR",
    )
    store.artefacts.add_version(project.id, charter.id, body=CHARTER, author=PERSON)
    engine.finish(project.id, "setup", actor="system")
    engine.approve(project.id, "setup", actor=PERSON)

    store.memory.add(project.id, "human_feedback", FEEDBACK, actor=PERSON, phase_key="requirements")
    return store, project.id, other.id, document.chunk_count


def ask(store: Store, project_id: str, question: Question) -> Answer:
    hits = store.context.search(project_id, question.text, limit=3)
    lines = [
        f"    {i}. relevance {h.relevance:.2f}  coverage {h.coverage:.2f}  {h.citation}\n       {one_line(h.text)}"
        for i, h in enumerate(hits, start=1)
    ]
    top = hits[0].source_id if hits else "(nothing found)"
    return Answer(question, top, bool(hits) and top.startswith(question.expect_prefix), tuple(lines))


def run(workdir: Path) -> tuple[list[Answer], bool, list[str]]:
    store, project_id, other_id, chunks = build(workdir)
    notes = [f"Policy note split into {chunks} chunks; charter approved and indexed; one feedback note recorded."]
    answers = [ask(store, project_id, q) for q in QUESTIONS]

    # A revised artefact replaces its old version in the results.
    charter = store.artefacts.list(project_id)[0]
    store.artefacts.add_version(
        project_id, charter.id, author=PERSON,
        body="# Project charter\n\nThe system must refuse overlapping reservations of the same room.",
    )
    from app.workflow.definitions import load_catalogue as _lc  # noqa: F401  (kept local: demo only)
    store.context.reingest_phase(project_id, "setup")
    old = store.context.search(project_id, "double bookings", kinds=["artefact"])
    new = store.context.search(project_id, "overlapping reservations", kinds=["artefact"])
    replaced = not old and bool(new) and new[0].source_id.startswith("SET-CHR-001@v2#")
    notes.append(
        "Revised charter: its new wording is found as "
        f"{new[0].source_id if new else '(nothing)'}, and the old wording ('double bookings') "
        f"{'is no longer found' if not old else 'is STILL FOUND, which is a bug'}."
    )

    # Another project must see none of it.
    leaks = [store.context.search(other_id, q.text) for q in QUESTIONS]
    isolated = not any(leaks) and store.context.resolve(other_id, "DOC-001#1") is None
    notes.append(
        "A second project asking the same five questions found "
        f"{sum(len(x) for x in leaks)} results; asking for DOC-001#1 directly found "
        f"{'nothing' if store.context.resolve(other_id, 'DOC-001#1') is None else 'TEXT, which is a bug'}."
    )
    return answers, replaced and isolated, notes


def main(argv: Sequence[str] | None = None) -> int:
    with tempfile.TemporaryDirectory(prefix="sdlc_context_demo_") as tmp:
        answers, behaviours_ok, notes = run(Path(tmp))

    for number, answer in enumerate(answers, start=1):
        mark = "ok " if answer.ok else "WRONG"
        print(f"Q{number}. {answer.question.text}")
        print(f"    expected: top hit {answer.question.expect_prefix}…  ({answer.question.note})   [{mark}]")
        print("\n".join(answer.lines) if answer.lines else "    (no results)")
        print()
    for note in notes:
        print(f"* {note}")
    print(
        "* How to read the numbers: relevance compares hits with each other (the best is always 1.00, even "
        "when it is poor). Coverage is the share of the question's words a chunk contains, so it is the one "
        "to trust when asking 'is this hit actually any good?'."
    )

    right = sum(a.ok for a in answers)
    print(f"\n{right}/{len(answers)} questions answered from the right source, "
          f"{'isolation OK' if behaviours_ok else 'isolation or replacement FAILED'}")
    return 0 if right == len(answers) and behaviours_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
