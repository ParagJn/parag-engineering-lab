"""The checks that decide whether a phase may start or be approved.

Each check takes the phase rows and the artefact types that have content, both read inside the same
transaction as the status change, so the answer cannot go stale between checking and acting.
"""
from __future__ import annotations

from typing import Iterable

from ..models import InvalidInput, PhaseRun
from .plan import PhasePlan, Plan


class PrerequisiteNotMet(InvalidInput):
    """An earlier phase has not been approved yet."""


class GateNotMet(InvalidInput):
    """The phase is missing something it needs before it can be approved."""


def _status_of(rows: Iterable[PhaseRun], phase_key: str) -> str:
    for row in rows:
        if row.phase_key == phase_key:
            return row.status
    return "not_started"  # a phase with no row yet has not started


def blocking_phase(plan: Plan, rows: Iterable[PhaseRun], phase_key: str) -> PhasePlan | None:
    """The nearest earlier phase in the plan that is not approved, or None if the way is clear.

    A phase with no artefacts in the plan is skipped, not blocking.
    """
    rows = list(rows)
    for phase in plan.phases:
        if phase.key == phase_key:
            return None
        if phase.artefacts and _status_of(rows, phase.key) != "approved":
            return phase
    raise KeyError(phase_key)


def check_can_start(plan: Plan, rows: Iterable[PhaseRun], phase_key: str) -> None:
    blocker = blocking_phase(plan, rows, phase_key)
    if blocker is not None:
        wanted = plan.phase(phase_key).phase.name
        raise PrerequisiteNotMet(
            f"{wanted} cannot start yet: {blocker.phase.name} is '{_status_of(list(rows), blocker.key)}' "
            "and must be approved first"
        )


def missing_required(phase: PhasePlan, content: set[tuple[str, str]]) -> list[str]:
    """Names of required, enabled artefacts that have no version yet."""
    return [a.name for a in phase.required if (phase.key, a.key) not in content]


def check_can_approve(phase: PhasePlan, content: set[tuple[str, str]]) -> None:
    missing = missing_required(phase, content)
    if missing:
        raise GateNotMet(
            f"{phase.phase.name} cannot be approved: required artefact(s) with no content yet: "
            + ", ".join(missing)
        )
