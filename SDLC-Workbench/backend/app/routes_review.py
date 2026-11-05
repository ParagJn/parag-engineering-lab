"""Review, request changes, re-run and edit by hand over HTTP (S12c).

The routes decide nothing about the rules: the review service, the human actions and the workflow engine do, and their sentences are
what the screen shows. What is added here is the shape of the answers, the person's name on every change, the archived check, and the
two things the screen needs and nothing else supplied: which artefacts a re-run should name, and the list of what is still open.

Review text (the summary and each finding) is model output. It is returned as text and the screen shows it as text.
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .actor import actor_from
from .archive import refuse_if_archived
from .llm.errors import ReviewerUnavailable
from .llm.types import ReviewerOption
from .models import InvalidInput, NotFoundError
from .review.errors import EditRefused, NotAnApprover, NothingToReview, ReviewError, ReviewOutputInvalid, WrongPhaseState
from .review.human import MAX_NOTE_CHARS
from .routes import _run_payload, _translate  # noqa: F401  (kept next to the run routes it mirrors)
from .routes_artefacts import KEY, ARTEFACT_ID, _valid
from .routes_review_shape import finding_payload, review_payload
from .run.errors import RunAlreadyActive
from .workflow.gates import GateNotMet, PrerequisiteNotMet

router = APIRouter(prefix="/api/projects/{project_id}")

MAX_BODY_CHARS = 200_000          # an artefact is at most 60,000 characters (S07); this leaves room and still bounds the request
MAX_SLOT_CHARS = 32


def _store(request: Request):
    return request.app.state.store


def _fail(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, NotAnApprover):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, (WrongPhaseState, PrerequisiteNotMet, GateNotMet, RunAlreadyActive)) or type(exc).__name__ == "IllegalTransition":
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


# ---- payloads, written out field by field ---------------------------------------------------------------------------------

def option_payload(option: ReviewerOption) -> dict[str, Any]:
    """One model family the person could pick to review. A price that is not known is null, never zero."""
    return {
        "slot": option.slot, "model_id": option.model_id, "family": option.family, "independent": option.independent,
        "price_input": option.price_input if option.priced else None, "price_output": option.price_output if option.priced else None,
        "priced": option.priced,
    }


def status_payload(status) -> dict[str, Any]:
    return {
        "artefact_id": status.artefact_id, "state": status.state, "verdict": status.verdict, "reviewed_version": status.reviewed_version,
        "latest_version": status.latest_version, "high_findings": status.high_findings,
    }


def stale_payload(item) -> dict[str, Any]:
    return {
        "artefact_id": item.artefact_id, "version": item.version,
        "built_on": dict(item.built_on), "now": dict(item.now),
    }


def paused_payload(artefact_id: str, error: ReviewerUnavailable) -> dict[str, Any]:
    return {"paused": True, "artefact_id": artefact_id, "slot": error.slot, "options": [option_payload(o) for o in error.options]}


def result_payload(result) -> dict[str, Any]:
    return {
        "paused": False, "artefact_id": result.artefact_id, "version": result.version, "verdict": result.verdict, "summary": result.summary,
        "findings": [finding_payload(f.as_dict()) for f in result.findings],
        "independence": {
            "label": result.independence["verdict"], "author_family": result.independence["author_family"],
            "reviewer_family": result.independence["reviewer_family"], "fell_back": bool(result.independence["fell_back"]),
        },
        "cost_usd": result.cost_usd, "attempts": result.attempts,
    }


def _reviews_available(request: Request) -> bool:
    """Reviews are model calls with a prompt no recording holds yet (S24 records them), so replay mode cannot run one."""
    return request.app.state.settings.app_mode == "live"


REPLAY_SENTENCE = "Reviews need live mode: no review has been recorded yet, so a server answering from recordings cannot run one."


def _need_live(request: Request) -> None:
    if not _reviews_available(request):
        raise HTTPException(status_code=409, detail=REPLAY_SENTENCE)


# ---- request bodies -----------------------------------------------------------------------------------------------------------

class ReviewBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot: str | None = Field(default=None, max_length=MAX_SLOT_CHARS, pattern=r"^[a-z][a-z0-9_]*$")
    exclude: list[str] = Field(default_factory=list, max_length=8)


class RequestChangesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    notes: dict[str, str] = Field(default_factory=dict, max_length=40)
    overall: str | None = Field(default=None, max_length=MAX_NOTE_CHARS)
    include_findings: list[str] = Field(default_factory=list, max_length=40)


class EditFileBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=MAX_BODY_CHARS)
    based_on: int = Field(ge=1, le=100000)
    note: str = Field(default="", max_length=1000)


class EditBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(max_length=MAX_BODY_CHARS)
    note: str = Field(default="", max_length=1000)


# ---- review one artefact, or a whole phase -----------------------------------------------------------------------------------------

@router.post("/artefacts/{artefact_id}/review")
async def review_artefact(project_id: str, artefact_id: str, body: ReviewBody, request: Request) -> dict:
    actor = actor_from(request)
    if not _valid(artefact_id, ARTEFACT_ID):
        raise HTTPException(status_code=422, detail="artefact id has unexpected characters")
    refuse_if_archived(request, project_id)
    _need_live(request)
    reviews = request.app.state.reviews
    try:
        result = await reviews.review(project_id, artefact_id, slot=body.slot, exclude=tuple(body.exclude), actor=actor)
    except ReviewerUnavailable as exc:
        return paused_payload(artefact_id, exc)          # a normal answer, not an error: the person is asked to choose
    except (NotFoundError, NothingToReview, WrongPhaseState, ReviewOutputInvalid, ReviewError, InvalidInput) as exc:
        raise _fail(exc) from exc
    return result_payload(result)


@router.post("/phases/{phase_key}/review")
async def review_phase(project_id: str, phase_key: str, body: ReviewBody, request: Request) -> dict:
    actor = actor_from(request)
    if not _valid(phase_key, KEY):
        raise HTTPException(status_code=422, detail="phase key must be lower-case letters, digits and underscores")
    refuse_if_archived(request, project_id)
    _need_live(request)
    try:
        _store(request).projects.get(project_id)
        results = await request.app.state.reviews.review_phase(project_id, phase_key, slot=body.slot, actor=actor)
    except (NotFoundError, NothingToReview, WrongPhaseState, ReviewError, InvalidInput) as exc:
        raise _fail(exc) from exc
    return {"results": [paused_payload(r.artefact_id, r.error) if hasattr(r, "error") else result_payload(r) for r in results]}


@router.get("/phases/{phase_key}/review")
def review_state(project_id: str, phase_key: str, request: Request) -> dict:
    """Everything the review panel shows, in one answer: each artefact's review standing, the stale list, what is open, and whether a
    review can be run at all on this server."""
    if not _valid(phase_key, KEY):
        raise HTTPException(status_code=422, detail="phase key must be lower-case letters, digits and underscores")
    human, reviews = request.app.state.human, request.app.state.reviews
    try:
        _store(request).projects.get(project_id)
        request.app.state.engine.catalogue.phase(phase_key)
        statuses = reviews.phase_status(project_id, phase_key)
        stale = human.stale(project_id, phase_key)
        open_items = human.open_items(project_id, phase_key)
        pending = _pending_notes(request, project_id, phase_key)
    except (NotFoundError, InvalidInput, KeyError) as exc:
        raise _fail(exc if not isinstance(exc, KeyError) else NotFoundError(f"unknown phase {phase_key!r}")) from exc
    return {
        "reviews_available": _reviews_available(request), "replay_sentence": None if _reviews_available(request) else REPLAY_SENTENCE,
        "statuses": [status_payload(s) for s in statuses], "stale": [stale_payload(s) for s in stale], "open": open_items,
        "artefacts_with_notes": pending,
    }


def _pending_notes(request: Request, project_id: str, phase_key: str) -> list[str]:
    """The artefacts a re-run would rewrite: those with an unaddressed note. The screen shows them; it never works them out."""
    return request.app.state.human.to_rewrite(project_id, phase_key)


# ---- edit one file of the Build instruction set (S19f-1) ----------------------------------------------------------------------------------------

FILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,78}\.md$")


@router.put("/artefacts/{artefact_id}/files/{file_name}")
def edit_file(project_id: str, artefact_id: str, file_name: str, body: EditFileBody, request: Request) -> dict:
    actor = actor_from(request)
    if not _valid(artefact_id, ARTEFACT_ID):
        raise HTTPException(status_code=422, detail="artefact id has unexpected characters")
    if not FILE_NAME.match(file_name):
        raise HTTPException(status_code=422, detail="file name has unexpected characters")
    refuse_if_archived(request, project_id)
    try:
        number = request.app.state.human.edit_file(project_id, artefact_id, file_name, body.text, based_on=body.based_on, actor=actor, note=body.note)
    except EditRefused as exc:
        raise HTTPException(status_code=422, detail={"message": str(exc), "problems": list(exc.problems)}) from exc
    except (NotFoundError, ReviewError, InvalidInput) as exc:
        raise _fail(exc) from exc
    return {"artefact_id": artefact_id, "file": file_name, "version": number}


# ---- send changes back, and re-run only those artefacts -------------------------------------------------------------------------------

@router.post("/phases/{phase_key}/request-changes")
def request_changes(project_id: str, phase_key: str, body: RequestChangesBody, request: Request) -> dict:
    actor = actor_from(request)
    if not _valid(phase_key, KEY):
        raise HTTPException(status_code=422, detail="phase key must be lower-case letters, digits and underscores")
    for artefact_id in [*body.notes, *body.include_findings]:
        if not _valid(artefact_id, ARTEFACT_ID):
            raise HTTPException(status_code=422, detail=f"artefact id {artefact_id[:40]!r} has unexpected characters")
    refuse_if_archived(request, project_id)
    if request.app.state.runner.is_active(project_id, phase_key):
        raise HTTPException(status_code=409, detail=f"{phase_key} is being written right now; wait for the run to end, or cancel it")
    try:
        run = request.app.state.human.request_changes(
            project_id, phase_key, actor=actor, notes=body.notes, overall=body.overall, include_findings=tuple(body.include_findings),
        )
    except (NotFoundError, ReviewError, InvalidInput) as exc:
        raise _fail(exc) from exc
    return {
        "phase": run.phase_key, "status": run.status, "decision": run.decision, "decided_by": run.decided_by,
        "feedback": run.feedback, "artefacts_with_notes": _pending_notes(request, project_id, phase_key),
    }


@router.post("/phases/{phase_key}/rerun", status_code=202)
async def rerun(project_id: str, phase_key: str, request: Request) -> dict:
    """Start a run (through the same runner as every other run: events, caps, cancel) that rewrites exactly the artefacts that have an
    unaddressed note. The list is worked out here from the notes; the screen does not choose it."""
    actor = actor_from(request)
    if not _valid(phase_key, KEY):
        raise HTTPException(status_code=422, detail="phase key must be lower-case letters, digits and underscores")
    refuse_if_archived(request, project_id)
    try:
        _store(request).projects.get(project_id)
        order = [a.key for a in request.app.state.engine.catalogue.phase(phase_key).artefacts]
        types = {a.id: a.type for a in _store(request).artefacts.list(project_id, phase_key=phase_key)}
        chosen = {types[artefact_id] for artefact_id in _pending_notes(request, project_id, phase_key)}
        if not chosen:
            raise ReviewError("no artefact has an unaddressed note, so there is nothing to re-run; send changes back with a note first")
        only = [k for k in order if k in chosen]
        run_id = request.app.state.runner.start_phase(project_id, phase_key, only=only)
    except (NotFoundError, ReviewError, InvalidInput, RunAlreadyActive) as exc:
        raise _fail(exc) from exc
    except KeyError as exc:
        raise _fail(NotFoundError(f"unknown phase {phase_key!r}")) from exc
    _store(request).audit.append(
        actor=actor, action="run.requested", target_type="run", target_id=run_id, project_id=project_id,
        detail={"phase": phase_key, "only": only, "rewrite_all": False, "review": False, "rerun_of_notes": True},
    )
    return {"run_id": run_id, "status": "running", "only": only, "events": f"/api/projects/{project_id}/events", "state": f"/api/projects/{project_id}/runs/{run_id}"}


@router.post("/phases/{phase_key}/rerun-stale", status_code=202)
async def rerun_stale(project_id: str, phase_key: str, request: Request) -> dict:
    """The person's explicit choice to rewrite the artefacts built on something that has since changed. Never done by itself."""
    actor = actor_from(request)
    if not _valid(phase_key, KEY):
        raise HTTPException(status_code=422, detail="phase key must be lower-case letters, digits and underscores")
    refuse_if_archived(request, project_id)
    try:
        _store(request).projects.get(project_id)
        order = [a.key for a in request.app.state.engine.catalogue.phase(phase_key).artefacts]
        types = {a.id: a.type for a in _store(request).artefacts.list(project_id, phase_key=phase_key)}
        chosen = {types[s.artefact_id] for s in request.app.state.human.stale(project_id, phase_key) if s.artefact_id in types}
        if not chosen:
            raise ReviewError("nothing in this phase was built on something that has changed")
        only = [k for k in order if k in chosen]
        # A phase under review cannot be run. The person's choice to re-run these IS the choice to take it back to running, so do that
        # first, as them, through the same audited move as any other (awaiting_review -> running is a legal transition).
        if request.app.state.store.phases.get(project_id, phase_key).status == "awaiting_review":
            request.app.state.engine.start(project_id, phase_key, actor=actor)
        run_id = request.app.state.runner.start_phase(project_id, phase_key, only=only)
    except (NotFoundError, ReviewError, InvalidInput, RunAlreadyActive) as exc:
        raise _fail(exc) from exc
    except KeyError as exc:
        raise _fail(NotFoundError(f"unknown phase {phase_key!r}")) from exc
    _store(request).audit.append(
        actor=actor, action="run.requested", target_type="run", target_id=run_id, project_id=project_id,
        detail={"phase": phase_key, "only": only, "rewrite_all": False, "review": False, "rerun_of_stale": True},
    )
    return {"run_id": run_id, "status": "running", "only": only, "events": f"/api/projects/{project_id}/events", "state": f"/api/projects/{project_id}/runs/{run_id}"}


# ---- edit by hand ---------------------------------------------------------------------------------------------------------------------------

@router.put("/artefacts/{artefact_id}")
def edit_artefact(project_id: str, artefact_id: str, body: EditBody, request: Request) -> dict:
    actor = actor_from(request)
    if not _valid(artefact_id, ARTEFACT_ID):
        raise HTTPException(status_code=422, detail="artefact id has unexpected characters")
    refuse_if_archived(request, project_id)
    try:
        number = request.app.state.human.edit(project_id, artefact_id, body.body, actor=actor, note=body.note)
    except EditRefused as exc:
        # The reasons are the whole point: the person fixes the text and tries again. Nothing was saved.
        raise HTTPException(status_code=422, detail={"message": str(exc), "problems": list(exc.problems)}) from exc
    except (NotFoundError, ReviewError, InvalidInput) as exc:
        raise _fail(exc) from exc
    return {"artefact_id": artefact_id, "version": number}
