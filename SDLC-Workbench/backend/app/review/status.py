from __future__ import annotations

from ..llm.routing import Routing
from .prompt import Rubric


def review_status(routing: Routing, rubric: Rubric | None) -> dict:
    """The reviewer slot and whether the rubric loaded. No file path and no rubric text."""
    return {
        "reviewer": routing.reviewer_default,
        "alternatives": list(routing.reviewer_alternatives),
        "rubric_loaded": rubric is not None,
    }
