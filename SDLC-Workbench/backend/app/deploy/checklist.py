"""A phase's checklist as a person sees it (S21c, S22a): every check with its latest answer, who and when, the history, and the totals. Reading and one write; no model.

A check with no answer is "not answered". The overall decision is the list's decision check. It is complete when every check has an answer and the decision is recorded; a
No-go anywhere is shown and counted, but it never stops the phase being approved (approval is the person's decision, and what was open is recorded with it).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import CheckAnswer, NotFoundError
from ..review.errors import PersonRequired, WrongPhaseState
from . import checks as C

OPEN_STATES = ("running", "awaiting_review")
PHASE = "deploy"                                  # the original phase; every function below takes `phase` and defaults to it, so Deploy's code is unchanged


@dataclass(frozen=True)
class Row:
    check: C.Check
    latest: CheckAnswer | None
    history: tuple[CheckAnswer, ...]          # every answer to this check, oldest first, the latest included


@dataclass
class Checklist:
    rows: list[Row] = field(default_factory=list)
    spec: C.ChecklistDef = C.DEPLOY

    def count(self, answer: str | None) -> int:
        return sum(1 for r in self.rows if (r.latest.answer if r.latest else None) == answer)

    @property
    def total(self) -> int:
        return len(self.rows)

    @property
    def unanswered(self) -> int:
        return self.count(None)

    @property
    def go(self) -> int:
        return self.count("go")

    @property
    def no_go(self) -> int:
        return self.count("no_go")

    @property
    def not_applicable(self) -> int:
        return self.count("not_applicable")

    @property
    def decision(self) -> str | None:
        """The overall answer, if it has been given: go, no_go or not_applicable. Never inferred from the others."""
        row = next(r for r in self.rows if r.check.id == self.spec.decision_id)
        return row.latest.answer if row.latest else None

    @property
    def complete(self) -> bool:
        return self.unanswered == 0

    def open_items(self) -> dict[str, Any]:
        """What was open, for the approval record: counts and the IDs of the checks concerned. Advice only."""
        return {
            "no_go": [r.check.id for r in self.rows if r.latest and r.latest.answer == "no_go"],
            "unanswered": [r.check.id for r in self.rows if r.latest is None],
            "decision": self.decision,
        }


def build(store: Any, project_id: str, phase: str = PHASE) -> Checklist:
    spec = C.definition_of(phase)
    history = store.deploy_checks.history(project_id, phase)
    by_check: dict[str, list[CheckAnswer]] = {}
    for a in history:
        by_check.setdefault(a.check_id, []).append(a)
    rows = []
    for check in spec.checks:
        mine = tuple(by_check.get(check.id, ()))
        rows.append(Row(check, mine[-1] if mine else None, mine))
    return Checklist(rows, spec)


def answer(store: Any, project_id: str, check_id: str, value: str, *, actor: str, note: str = "", phase: str = PHASE) -> CheckAnswer:
    """Save one answer in a person's name. Refused for an agent or the system, for a check that is not in THIS phase's list, and while that phase is not open."""
    spec = C.definition_of(phase)
    if not isinstance(actor, str) or not actor.startswith("human:"):
        raise PersonRequired("answering a check is a human decision; it needs a person ('human:<name>'), not an agent or the system")
    if check_id not in spec.by_id:
        raise NotFoundError(f"there is no check {check_id!r}; the checks are {spec.checks[0].id} to {spec.checks[-1].id}")
    try:
        status = store.phases.get(project_id, phase).status
    except NotFoundError:
        status = "not_started"
    if status not in OPEN_STATES:
        raise WrongPhaseState(f"a check can be answered only while the phase is {' or '.join(OPEN_STATES)}; {phase} is '{status}'")
    return store.deploy_checks.answer(project_id, check_id, value, actor=actor, note=note, phase=phase)


# ---- the one-page report (S21c) -------------------------------------------------------------------------------------------------------------

def report_markdown(checklist: Checklist, project_name: str) -> str:
    spec = checklist.spec
    words = spec.answer_words
    """The checklist as a Markdown page that can be filed: the totals, the overall decision, then every check with its latest answer, who answered, when, and the note.
    Plain text in, plain text out: the Word version is made from this same text, so the two can never differ."""
    decision = words[checklist.decision] if checklist.decision else "not recorded yet"
    lines = [
        f"# {spec.report_title}: {project_name}", "",
        f"**Overall decision:** {decision}", "",
        f"{checklist.total - checklist.unanswered} of {checklist.total} checks answered: {checklist.go} {words['go']}, {checklist.no_go} {words['no_go']}, {checklist.not_applicable} {words['not_applicable']}, {checklist.unanswered} not answered.", "",
        "This record was filled in by hand. No model was used.", "",
    ]
    for group in spec.groups:
        rows = [r for r in checklist.rows if r.check.group == group]
        lines += [f"## {spec.group_title[group]}", "", "| Check | Question | Answer | By | When | Note |", "|---|---|---|---|---|---|"]
        for r in rows:
            a = r.latest
            cells = [r.check.id, r.check.question, words[a.answer] if a else "Not answered", a.actor.removeprefix("human:") if a else "", a.at if a else "", a.note if a else ""]
            lines.append("| " + " | ".join(c.replace("|", "\\|").replace("\n", " ") for c in cells) + " |")
        lines.append("")
    changed = [r for r in checklist.rows if len(r.history) > 1]
    if changed:
        lines += ["## Answers that were changed", ""]
        for r in changed:
            lines.append(f"- **{r.check.id}**: " + "; ".join(f"{words[h.answer]} ({h.actor.removeprefix('human:')}, {h.at})" for h in r.history))
        lines.append("")
    return "\n".join(lines)
