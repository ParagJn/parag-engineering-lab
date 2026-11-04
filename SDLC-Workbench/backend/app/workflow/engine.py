"""The lifecycle rules that span phases: order, prerequisites, gates and where a project stands.

No model calls and no I/O of its own. Status changes go through PhaseRepo, with the checks passed in
as guards so they run in the same transaction as the change.
"""
from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from typing import Any

from ..models import InvalidInput, NotFoundError, PhaseRun, Project
from ..repos import Store, artefact_types_with_content_in, phase_runs_in
from .definitions import Catalogue
from .gates import check_can_approve, check_can_start, missing_required
from .plan import PhasePlan, Plan, PlanError, build_plan

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArtefactState:
    key: str
    name: str
    required: bool
    has_content: bool
    wave: int  # 1-based position in the phase's parallel waves
    waits_for: tuple[str, ...]


@dataclass(frozen=True)
class NotEnabledState:
    """An artefact of the phase that is part of the design but switched off (S21a): shown with its reason, never run, never required."""
    key: str
    name: str
    reason: str


@dataclass(frozen=True)
class ByHandState:
    """An artefact of the phase that a person does by hand (S21): it is never run or required, and the screen shows a card that points at the checklist."""
    key: str
    name: str
    description: str


@dataclass(frozen=True)
class PhaseState:
    key: str
    order: int
    name: str
    approver: str
    status: str
    decision: str | None
    decided_by: str | None
    feedback: str | None
    artefacts: tuple[ArtefactState, ...]
    needs_review: bool  # approved, but an earlier phase has been reopened since
    blocked_by: str | None  # name of the earlier phase that must be approved first
    allowed_actions: tuple[str, ...] = ()  # what a person may do now; the screen shows these and decides nothing itself
    not_enabled: tuple[NotEnabledState, ...] = ()  # S21a: switched off in the definition, with the reason
    by_hand: tuple[ByHandState, ...] = ()  # S21: done by a person, not written by an agent


@dataclass(frozen=True)
class Snapshot:
    project_id: str
    phases: tuple[PhaseState, ...]
    notes: tuple[str, ...]
    next_action: str


# What a person may do with a phase, by its status. One table, so the screen never re-implements the state machine.
#   run       produce the phase's artefacts (starts the phase if it has not started)
#   rewrite   run a running phase again and rewrite EVERY artefact in it, even those already written (each becomes a new version; the old ones are kept).
#             Offered only once something has been written: before that it would be the same as run.
#   finish    hand a running phase to review
#   approve   a person approves a phase under review
#   request_changes   send a phase under review back, naming the artefacts to rewrite
#   reopen   take an approved phase back to running, with a written reason; later phases are not changed (they show that they stand on a reopened one)
ACTIONS_BY_STATUS: dict[str, tuple[str, ...]] = {
    "not_started": ("run",),
    "running": ("run", "rewrite", "finish"),
    "awaiting_review": ("approve", "request_changes"),
    "rejected": ("run",),
    # An approved phase can be taken back to running by a person with a written reason (2026-10-31). Listed for EVERY phase, so a phase added later
    # gets the button with no further work: the screen shows exactly what this table says.
    "approved": ("reopen",),
}


def allowed_actions(status: str, has_artefacts: bool, blocked_by: str | None, has_content: bool = True) -> tuple[str, ...]:
    """The actions open to a person for one phase. A phase with nothing in the plan, or one an earlier unapproved phase blocks
    (and which has not started), offers none. A phase already under way is never blocked: it cannot have started if it was."""
    if not has_artefacts:
        return ()
    if status == "not_started" and blocked_by is not None:
        return ()
    actions = ACTIONS_BY_STATUS.get(status, ())
    return actions if has_content else tuple(a for a in actions if a != "rewrite")      # nothing written yet: a rewrite would be exactly a run


def selection_of(project: Project) -> dict[str, Any]:
    """The wizard's choices as stored on the project. An empty selection means everything."""
    return dict(project.selection or {})


class WorkflowEngine:
    """Convention the gate relies on: an artefact's stored `type` is its catalogue key (for example
    'personas'), and its `phase_key` is the catalogue phase. Whatever creates artefacts (S07 onwards)
    must follow it, or the approval gate will see the phase as empty."""

    def __init__(self, catalogue: Catalogue, store: Store):
        self.catalogue = catalogue
        self.store = store

    # ---- plan ---------------------------------------------------------------

    def plan_for(self, project: Project) -> Plan:
        try:
            return build_plan(self.catalogue, selection_of(project))
        except PlanError as exc:
            raise InvalidInput(f"project '{project.id}' has an invalid selection: {exc}") from exc

    def _phase_plan(self, project_id: str, phase_key: str) -> tuple[Project, PhasePlan, Plan]:
        project = self.store.projects.get(project_id)
        plan = self.plan_for(project)
        try:
            return project, plan.phase(phase_key), plan
        except KeyError:
            raise NotFoundError(f"unknown phase {phase_key!r}; phases are {list(self.catalogue.phase_keys)}") from None

    def open_project(self, project_id: str, *, actor: str = "system") -> Plan:
        """Create a row for every phase in the plan, so a new project starts with a full lifecycle."""
        project = self.store.projects.get(project_id)
        plan = self.plan_for(project)
        for phase in plan.phases:
            self.store.phases.ensure(project_id, phase.key, actor=actor)
        return plan

    # ---- moving a phase -----------------------------------------------------

    def start(self, project_id: str, phase_key: str, *, actor: str) -> PhaseRun:
        """Start (or restart) a phase. Earlier phases must be approved, checked under the same lock."""
        _, _, plan = self._phase_plan(project_id, phase_key)
        self.store.phases.ensure(project_id, phase_key, actor="system")

        def guard(conn: sqlite3.Connection, _: PhaseRun) -> None:
            check_can_start(plan, phase_runs_in(conn, project_id), phase_key)

        return self.store.phases.set_status(project_id, phase_key, "running", actor=actor, guard=guard)

    def finish(self, project_id: str, phase_key: str, *, actor: str) -> PhaseRun:
        """Hand a running phase to review."""
        self._phase_plan(project_id, phase_key)
        return self.store.phases.set_status(project_id, phase_key, "awaiting_review", actor=actor)

    def approve(self, project_id: str, phase_key: str, *, actor: str, detail: dict[str, Any] | None = None) -> PhaseRun:
        """Approve a phase under review. Every required artefact must have content, checked under the lock.

        `detail` is extra information for the audit row of the decision (for example what was open)."""
        _, phase_plan, _ = self._phase_plan(project_id, phase_key)

        def guard(conn: sqlite3.Connection, _: PhaseRun) -> None:
            check_can_approve(phase_plan, artefact_types_with_content_in(conn, project_id))

        run = self.store.phases.record_decision(project_id, phase_key, "approve", actor=actor, guard=guard, detail=detail)
        self._index_approved(project_id, phase_key)
        return run

    def _index_approved(self, project_id: str, phase_key: str) -> None:
        """Make an approved phase's artefacts searchable. The approval is a human decision and stands
        whatever happens here: a failure is logged and audited, never raised and never undone."""
        try:
            result = self.store.context.reingest_phase(project_id, phase_key)
            problem = f"{len(result.failed)} artefact(s) could not be indexed" if result.failed else None
            detail = {"failed": [{"artefact": a, "reason": r} for a, r in result.failed]} if result.failed else None
        except Exception as exc:  # noqa: BLE001 - anything at all must leave the approval standing
            log.warning("indexing approved phase %s failed", phase_key, exc_info=True)
            problem, detail = "indexing failed", {"error": type(exc).__name__}
        if problem is not None:
            try:
                self.store.audit.append(
                    actor="system", action="context.index_failed", target_type="phase", target_id=phase_key,
                    project_id=project_id, detail={"problem": problem, **(detail or {})},
                )
            except Exception:  # noqa: BLE001 - even the audit write must not undo an approval
                log.error("could not record an indexing failure for phase %s", phase_key, exc_info=True)

    def reject(
        self, project_id: str, phase_key: str, *, actor: str, feedback: str,
        notes: tuple[tuple[str | None, str, str], ...] = (),
    ) -> PhaseRun:
        """Send a phase back. `notes` (artefact ID or None, memory kind, text) are saved with the rejection."""
        self._phase_plan(project_id, phase_key)
        return self.store.phases.record_decision(
            project_id, phase_key, "reject", actor=actor, feedback=feedback, notes=notes,
        )

    def reopen(self, project_id: str, phase_key: str, *, actor: str, reason: str) -> PhaseRun:
        self._phase_plan(project_id, phase_key)
        run = self.store.phases.reopen(project_id, phase_key, actor=actor, reason=reason)
        # Content under review is not "validated, approved context" until it is approved again.
        try:
            self.store.context.unindex_phase(project_id, phase_key)
        except Exception:  # noqa: BLE001 - the reopen stands; stale index entries are audited below
            log.warning("could not unindex phase %s after reopening", phase_key, exc_info=True)
            try:
                self.store.audit.append(
                    actor="system", action="context.index_failed", target_type="phase", target_id=phase_key,
                    project_id=project_id, detail={"problem": "could not remove the phase from the index"},
                )
            except Exception:  # noqa: BLE001
                log.error("could not record an unindexing failure for phase %s", phase_key, exc_info=True)
        return run

    # ---- where a project stands ---------------------------------------------

    def snapshot(self, project_id: str) -> Snapshot:
        project = self.store.projects.get(project_id)
        plan = self.plan_for(project)
        rows = {r.phase_key: r for r in self.store.phases.list(project_id)}
        with self.store.db.read() as conn:
            content = artefact_types_with_content_in(conn, project_id)
        reopened_at = self._latest_reopen_times(project_id)

        states: list[PhaseState] = []
        for phase in plan.phases:
            row = rows.get(phase.key)
            status = row.status if row else "not_started"
            wave_of = {a.key: n for n, wave in enumerate(phase.waves, start=1) for a in wave}
            artefacts = tuple(
                ArtefactState(
                    key=a.key, name=a.name, required=a.required,
                    has_content=(phase.key, a.key) in content,
                    wave=wave_of[a.key], waits_for=a.after,
                )
                for a in phase.artefacts
            )
            states.append(
                PhaseState(
                    key=phase.key, order=phase.phase.order, name=phase.phase.name, approver=phase.phase.approver,
                    status=status,
                    decision=row.decision if row else None, decided_by=row.decided_by if row else None,
                    feedback=row.feedback if row else None,
                    artefacts=artefacts,
                    needs_review=self._needs_review(plan, rows, reopened_at, phase),
                    blocked_by=self._blocked_by(plan, list(rows.values()), phase),
                    allowed_actions=allowed_actions(status, bool(phase.artefacts), self._blocked_by(plan, list(rows.values()), phase), any(a.has_content for a in artefacts)),
                    not_enabled=tuple(NotEnabledState(a.key, a.name, a.disabled_reason) for a in phase.not_enabled),
                    by_hand=tuple(ByHandState(a.key, a.name, a.description) for a in phase.by_hand),
                )
            )
        return Snapshot(project_id, tuple(states), plan.notes, self._next_action(states))

    def next_action(self, project_id: str) -> str:
        return self.snapshot(project_id).next_action

    # ---- helpers --------------------------------------------------------------

    def _latest_reopen_times(self, project_id: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for event in self.store.audit.list(project_id, action="phase.reopened"):
            out[event.target_id] = event.at  # events come oldest first, so the last one wins
        return out

    @staticmethod
    def _needs_review(plan: Plan, rows: dict[str, PhaseRun], reopened_at: dict[str, str], phase: PhasePlan) -> bool:
        """True when this phase is approved but an EARLIER phase was reopened after this one was approved."""
        row = rows.get(phase.key)
        if row is None or row.status != "approved":
            return False
        for earlier in plan.phases:
            if earlier.key == phase.key:
                break
            when = reopened_at.get(earlier.key)
            if when is not None and when > row.updated_at:
                return True
        return False

    @staticmethod
    def _blocked_by(plan: Plan, rows: list[PhaseRun], phase: PhasePlan) -> str | None:
        from .gates import blocking_phase

        blocker = blocking_phase(plan, rows, phase.key)
        return blocker.phase.name if blocker is not None else None

    @staticmethod
    def _next_action(states: list[PhaseState]) -> str:
        for state in states:
            if not state.artefacts:
                continue
            if state.status == "approved":
                continue
            if state.status == "not_started":
                if state.blocked_by is None:
                    return f"{state.name} can start"
                return f"{state.name} is waiting for {state.blocked_by} to be approved"
            if state.status == "running":
                waiting = [a.name for a in state.artefacts if a.required and not a.has_content]
                tail = f" ({len(waiting)} required artefact(s) still empty)" if waiting else ""
                return f"{state.name} is running{tail}"
            if state.status == "awaiting_review":
                return f"{state.name} is awaiting review by the {state.approver}"
            if state.status == "rejected":
                return f"{state.name} was rejected and needs to be re-run"
        return "All phases are approved"
