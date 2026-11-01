from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MODES = ("live", "replay")
PHASE_STATUSES = ("not_started", "running", "awaiting_review", "approved", "rejected")
DECISIONS = ("approve", "reject")
LINK_KINDS = ("derives", "implements", "verifies", "deploys")
MEMORY_KINDS = ("reviewer_feedback", "human_feedback", "note")
TRACE_STATUSES = ("ok", "error")


class NotFoundError(LookupError):
    """A project, phase, artefact or version that was asked for does not exist."""


class InvalidInput(ValueError):
    """The caller passed a value the data layer will not store."""


class IllegalTransition(InvalidInput):
    """A phase was asked to move somewhere its current status does not allow.

    A subclass of InvalidInput, so callers written before the state machine existed still catch it.
    """


# Where a phase may go next. Approved phases are left only through reopen(), never set_status().
PHASE_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "not_started": ("running",),
    "running": ("awaiting_review", "not_started"),
    "awaiting_review": ("approved", "rejected", "running"),
    "rejected": ("running",),
    "approved": ("running",),  # reachable only through PhaseRepo.reopen
}


class ProjectArchived(InvalidInput):
    """The project is archived, so nothing in it can be changed until it is restored."""


class ConflictError(ValueError):
    """The write would duplicate something that must be unique."""


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    brief: str
    mode: str
    selection: dict[str, Any]
    routing_overrides: dict[str, Any]
    context_id: str | None
    created_at: str
    updated_at: str
    # When it was archived, or None for an active project. An archived project can be read but not changed.
    archived_at: str | None = None


@dataclass(frozen=True)
class PhaseRun:
    project_id: str
    phase_key: str
    status: str
    started_at: str | None
    finished_at: str | None
    decision: str | None
    decided_by: str | None
    feedback: str | None
    updated_at: str


@dataclass(frozen=True)
class Artefact:
    project_id: str
    id: str
    type: str
    phase_key: str
    title: str
    created_at: str
    latest_version: int | None


@dataclass(frozen=True)
class ArtefactVersion:
    project_id: str
    artefact_id: str
    number: int
    body: str
    author: str
    source_chunks: tuple[str, ...]
    review_findings: Any
    created_at: str
    # How this version was made. For an agent: models, calls, tokens, cost and the upstream versions it was
    # built on. For a human edit: {'human_edit': True, 'based_on': n, ...}. None only for versions written
    # directly through the repository (and for versions that predate the record).
    generation: Any = None


@dataclass(frozen=True)
class Link:
    id: int
    project_id: str
    from_id: str
    to_id: str
    kind: str
    declared_in: str | None
    created_at: str


@dataclass(frozen=True)
class Trace:
    id: int
    project_id: str | None
    run_id: str | None
    agent: str
    phase_key: str | None
    slot: str
    requested_model: str
    served_model: str
    fallback_used: bool
    status: str
    error: str | None
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost_usd: float | None
    created_at: str
    call_id: str | None = None
    attempt: int = 1


@dataclass(frozen=True)
class AuditEvent:
    id: int
    project_id: str | None
    at: str
    actor: str
    action: str
    target_type: str
    target_id: str
    detail: dict[str, Any]


@dataclass(frozen=True)
class RunRecord:
    id: str
    project_id: str
    phase_key: str
    status: str  # running | finished | stopped | failed | interrupted
    stop_reason: str | None  # budget | time | cancelled
    started_at: str
    finished_at: str | None
    totals: Any  # a JSON object once the run has ended


@dataclass(frozen=True)
class RunEvent:
    id: int
    project_id: str
    run_id: str
    at: str
    type: str
    data: Any


@dataclass(frozen=True)
class RollupRow:
    """Totals for one model, phase, agent or slot. cost_usd is None when nothing in the group was priced."""

    key: str | None
    calls: int
    errors: int
    fallbacks: int
    tokens_in: int
    tokens_out: int
    cost_usd: float | None
    unpriced_calls: int


@dataclass(frozen=True)
class MemoryEntry:
    id: int
    project_id: str
    kind: str
    phase_key: str | None
    artefact_id: str | None
    text: str
    created_at: str
