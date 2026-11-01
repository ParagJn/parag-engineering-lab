"""The first HTTP routes (S09): start a run, cancel it, read it, and follow its events.

There is no sign-in. The backend listens on 127.0.0.1 only, so these routes are reachable by whoever is on this
machine; they can spend ICA money. Every route checks that the project exists and takes no free text that reaches
a prompt: a run is described by a phase key and a few switches.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .actor import actor_from
from .archive import refuse_if_archived
from .models import ConflictError, InvalidInput, NotFoundError
from .run.errors import RunAlreadyActive
from .workflow.gates import PrerequisiteNotMet
from .run.events import DROPPED, HEARTBEAT, format_comment, format_sse

router = APIRouter(prefix="/api/projects/{project_id}")

KEY = r"^[a-z][a-z0-9_]{0,63}$"
RUN_ID = r"^[A-Za-z0-9_-]{1,64}$"


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")  # an unknown field is an error, not silently ignored

    only: list[str] | None = Field(default=None, max_length=40)
    rewrite_all: bool = False
    review: bool = False


def _runner(request: Request):
    return request.app.state.runner


def _store(request: Request):
    return request.app.state.store


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, (RunAlreadyActive, ConflictError, PrerequisiteNotMet)):   # the request is fine; the state is not
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


def _run_payload(record) -> dict:
    return {
        "run_id": record.id, "project_id": record.project_id, "phase": record.phase_key, "status": record.status,
        "stop_reason": record.stop_reason, "started_at": record.started_at, "finished_at": record.finished_at,
        "totals": record.totals,
    }


@router.post("/phases/{phase_key}/run", status_code=202)
async def start_run(project_id: str, phase_key: str, body: RunRequest, request: Request) -> dict:
    actor = actor_from(request)    # starting a run can spend money: the audit trail says who asked
    refuse_if_archived(request, project_id)
    if not _valid(phase_key, KEY):
        raise HTTPException(status_code=422, detail="phase key must be lower-case letters, digits and underscores")
    for key in body.only or ():
        if not _valid(key, KEY):
            raise HTTPException(status_code=422, detail=f"artefact key {key!r} must be lower-case letters, digits and underscores")
    try:
        run_id = _runner(request).start_phase(
            project_id, phase_key, only=body.only, rewrite_all=body.rewrite_all, review=body.review,
        )
    except (NotFoundError, ConflictError, InvalidInput) as exc:
        raise _translate(exc) from exc
    _store(request).audit.append(
        actor=actor, action="run.requested", target_type="run", target_id=run_id, project_id=project_id,
        detail={"phase": phase_key, "only": body.only, "rewrite_all": body.rewrite_all, "review": body.review},
    )
    return {
        "run_id": run_id,
        "status": "running",
        "events": f"/api/projects/{project_id}/events",
        "state": f"/api/projects/{project_id}/runs/{run_id}",
    }


@router.get("/runs/{run_id}")
def get_run(project_id: str, run_id: str, request: Request) -> dict:
    if not _valid(run_id, RUN_ID):
        raise HTTPException(status_code=422, detail="run id has unexpected characters")
    try:
        return _run_payload(_store(request).runs.get(project_id, run_id))
    except NotFoundError as exc:
        raise _translate(exc) from exc


@router.post("/runs/{run_id}/cancel")
def cancel_run(project_id: str, run_id: str, request: Request) -> dict:
    actor = actor_from(request)
    if not _valid(run_id, RUN_ID):
        raise HTTPException(status_code=422, detail="run id has unexpected characters")
    try:
        accepted = _runner(request).cancel(project_id, run_id)
    except NotFoundError as exc:
        raise _translate(exc) from exc
    if not accepted:
        raise HTTPException(status_code=409, detail="that run is not running, so there is nothing to cancel")
    _store(request).audit.append(
        actor=actor, action="run.cancel_requested", target_type="run", target_id=run_id, project_id=project_id, detail={},
    )
    return {
        "run_id": run_id,
        "requested": True,
        "note": "No new artefact will start. Artefacts already being written finish and save.",
    }


@router.get("/events")
async def events(project_id: str, request: Request, after: int = 0) -> StreamingResponse:
    """Server-Sent Events for a project's runs. `after` (or the Last-Event-ID header) resumes after an event id."""
    store, bus, settings = _store(request), request.app.state.bus, request.app.state.settings
    try:
        store.projects.get(project_id)
    except NotFoundError as exc:
        raise _translate(exc) from exc
    if after < 0:
        raise HTTPException(status_code=422, detail="'after' must be zero or more")
    header = request.headers.get("last-event-id")
    if header is not None:
        if not header.isdigit():
            raise HTTPException(status_code=422, detail="Last-Event-ID must be a whole number")
        after = max(after, int(header))

    async def stream() -> AsyncIterator[str]:
        watcher = bus.watch(project_id)  # subscribe BEFORE reading the log, so nothing falls in the gap
        try:
            last = after
            while True:  # catch up from the durable log, then go live
                batch = await asyncio.to_thread(store.run_events.list, project_id, after=last, limit=500)
                for event in batch:
                    last = event.id
                    yield format_sse(event)
                if len(batch) < 500:
                    break
            yield format_comment("live")
            while True:
                try:
                    item = await asyncio.wait_for(watcher.queue.get(), timeout=settings.run_heartbeat_seconds)
                except asyncio.TimeoutError:
                    # No check for a gone client here: the server ends this generator itself when the client leaves (it
                    # cancels it under ASGI 2.3, and the write below fails under 2.4), and `finally` frees the watcher.
                    yield format_comment(HEARTBEAT)
                    continue
                if item is None:  # this watcher fell too far behind
                    yield f"event: {DROPPED}\ndata: {{\"reason\": \"too slow; reconnect with the last id you saw\"}}\n\n"
                    return
                if item.id <= last:
                    continue  # already sent from the log
                last = item.id
                yield format_sse(item)
        finally:
            bus.unwatch(watcher)

    return StreamingResponse(
        stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


def _valid(value: str, pattern: str) -> bool:
    import re

    return bool(re.fullmatch(pattern, value))
