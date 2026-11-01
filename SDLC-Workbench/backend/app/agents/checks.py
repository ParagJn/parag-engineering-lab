"""The deterministic checks every version of an artefact must pass, whoever wrote it.

An agent's reply and a person's edit go through the same function, so a hand edit cannot quietly break the
section structure, the item IDs or the references that later phases depend on.
"""
from __future__ import annotations

from typing import Collection

from ..architecture.diagram import diagram_problems
from ..design.sanitise import drawing_problems
from ..guardrails.scan import Scanner
from .items import ItemContext, check_items
from .reply import MAX_PROBLEMS, validate
from .skills import Skill


def check_body(
    body: str, skill: Skill, allowed_citations: Collection[str], item_ctx: ItemContext | None, finish_reason: str | None = None,
    scanner: Scanner | None = None,
) -> list[str]:
    """Every problem with an artefact body, as plain sentences. [] means it may be saved.

    A secret in the text is a problem, listed FIRST so it can never be cut off by the limit on how many problems are
    reported: it is the one problem that must not survive a repair. Personal data is not a problem; it is flagged on save."""
    problems = validate(body, skill.required_sections, allowed_citations, finish_reason)
    # A drawing is model output the browser will DRAW. Anything the sanitiser would remove is sent back to be redrawn, never quietly altered.
    # Checked for every artefact (not only the Design ones) so a drawing cannot be smuggled into any other.
    problems = (problems + drawing_problems(body))[:MAX_PROBLEMS]
    if item_ctx is not None:
        problems = (problems + check_items(body, item_ctx))[:MAX_PROBLEMS]
        # A diagram artefact is a list the server will DRAW (S14b). Every line must point at a component or persona that exists, or it cannot be drawn.
        problems = (problems + diagram_problems(skill.key, body, item_ctx.known))[:MAX_PROBLEMS]
    if scanner is not None:
        problems = (scanner.problems(body) + problems)[:MAX_PROBLEMS]
    return problems
