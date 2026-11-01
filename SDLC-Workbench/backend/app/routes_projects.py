"""Projects over HTTP (S12a): preview what a selection means, create a project, list projects, read one.

The screen holds no business rules. The server says what a selection means (`/api/plan/preview`), what a person may do with each
phase (`allowed_actions`) and what went wrong, in sentences meant to be shown as they are. Changing routes need `X-Actor`
(a name for the audit trail, not a sign-in); reading needs nothing.

Payloads are written out field by field here, not taken from internal objects, so adding a field inside the application can
never change what the screen receives by accident. The shapes are pinned by the contract fixtures (scripts/export_contract.py).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .actor import actor_from
from .models import InvalidInput, NotFoundError, Project, MODES
from .workflow.plan import Plan, PlanError, build_plan

router = APIRouter(prefix="/api")

MAX_NAME_CHARS = 120
MAX_BRIEF_CHARS = 8000
MAX_PROJECTS_LISTED = 200
CONNECTORS = ("source_control", "issue_tracker", "ci_cd", "cloud_account")
KEY = r"^[a-z][a-z0-9_]{0,63}$"


class Selection(BaseModel):
    """phase key -> the artefact keys switched ON; a phase left out gets everything."""

    model_config = ConfigDict(extra="forbid")

    phases: dict[str, list[str] | None] = Field(default_factory=dict, max_length=20)

    @field_validator("phases")
    @classmethod
    def _keys(cls, value: dict[str, list[str] | None]) -> dict[str, list[str] | None]:
        import re

        for phase, keys in value.items():
            if not re.fullmatch(KEY, phase):
                raise ValueError(f"phase key {phase!r} must be lower-case letters, digits and underscores")
            for key in keys or ():
                if not re.fullmatch(KEY, key):
                    raise ValueError(f"artefact key {key!r} must be lower-case letters, digits and underscores")
            if keys is not None and len(keys) > 60:
                raise ValueError("too many artefacts listed for one phase")
        return value


class PreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selection: dict[str, list[str] | None] = Field(default_factory=dict, max_length=20)


class CreateProject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_NAME_CHARS)
    brief: str = Field(default="", max_length=MAX_BRIEF_CHARS)
    selection: dict[str, list[str] | None] = Field(default_factory=dict, max_length=20)
    connectors: list[str] = Field(default_factory=list, max_length=len(CONNECTORS))

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("the project needs a name")
        return value

    @field_validator("connectors")
    @classmethod
    def _connectors(cls, value: list[str]) -> list[str]:
        unknown = sorted(set(value) - set(CONNECTORS))
        if unknown:
            raise ValueError(f"unknown connector(s) {unknown}; the connectors are {list(CONNECTORS)}")
        return list(dict.fromkeys(value))


def _store(request: Request):
    return request.app.state.store


def _engine(request: Request):
    return request.app.state.engine


def _fail(exc: Exception) -> HTTPException:
    if isinstance(exc, NotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


# ---- payloads, written out field by field ---------------------------------------------------------------------------------

def plan_payload(plan: Plan) -> dict[str, Any]:
    return {
        "phases": [
            {
                "key": p.key, "order": p.phase.order, "name": p.phase.name, "summary": p.phase.summary, "approver": p.phase.approver,
                "artefacts": [
                    {"key": a.key, "name": a.name, "required": a.required, "description": a.description, "waits_for": list(a.after),
                     "wave": next(n for n, wave in enumerate(p.waves, start=1) if any(x.key == a.key for x in wave)),
                     "added_because_needed": a.key in p.pulled_in}
                    for a in p.artefacts
                ],
                "waves": [[a.key for a in wave] for wave in p.waves],
            }
            for p in plan.phases
        ],
        "notes": list(plan.notes),
    }


def catalogue_payload(request: Request) -> dict[str, Any]:
    """Every phase and artefact that exists, with nothing switched off: what the wizard offers to tick."""
    catalogue = request.app.state.engine.catalogue
    return {
        "phases": [
            {"key": p.key, "order": p.order, "name": p.name, "summary": p.summary, "approver": p.approver,
             "artefacts": [{"key": a.key, "name": a.name, "required": a.required, "description": a.description, "waits_for": list(a.after)}
                           for a in p.artefacts]}
            for p in catalogue.phases
        ]
    }


def project_summary(project: Project, snapshot) -> dict[str, Any]:
    done = sum(1 for p in snapshot.phases if p.status == "approved")
    active = next((p for p in snapshot.phases if p.status in ("running", "awaiting_review", "rejected")), None)
    return {
        "id": project.id, "name": project.name, "mode": project.mode, "created_at": project.created_at, "archived_at": project.archived_at,
        "phases_total": sum(1 for p in snapshot.phases if p.artefacts), "phases_approved": done,
        "active_phase": None if active is None else {"key": active.key, "name": active.name, "status": active.status},
        "next_action": snapshot.next_action,
    }


def connectors_of(store, project_id: str) -> list[str]:
    """The simulated connectors ticked in the wizard (the latest note), or none."""
    notes = store.audit.list(project_id, action="project.connectors_noted")
    return list(notes[-1].detail.get("connectors", [])) if notes else []


def project_detail(project: Project, snapshot, connectors: list[str]) -> dict[str, Any]:
    return {
        "id": project.id, "name": project.name, "brief": project.brief, "mode": project.mode, "created_at": project.created_at,
        "updated_at": project.updated_at, "archived_at": project.archived_at, "connectors": connectors, "connectors_are_simulated": True,
        "next_action": snapshot.next_action, "notes": list(snapshot.notes),
        "phases": [
            {
                "key": p.key, "order": p.order, "name": p.name, "approver": p.approver, "status": p.status, "decision": p.decision,
                "decided_by": p.decided_by, "feedback": p.feedback, "needs_review": p.needs_review, "blocked_by": p.blocked_by,
                "allowed_actions": list(p.allowed_actions),
                "artefacts": [{"key": a.key, "name": a.name, "required": a.required, "has_content": a.has_content, "wave": a.wave,
                               "waits_for": list(a.waits_for)} for a in p.artefacts],
            }
            for p in snapshot.phases
        ],
    }


# ---- routes ----------------------------------------------------------------------------------------------------------------------

@router.get("/catalogue")
def get_catalogue(request: Request) -> dict:
    return catalogue_payload(request)


@router.get("/modes")
def get_mode(request: Request) -> dict:
    """Mode is a fact about this server, not a choice (S12 decision 6)."""
    mode = request.app.state.settings.app_mode
    return {
        "mode": mode,
        "reviews_available": mode == "live",
        "meaning": ("This server answers from recordings: free, offline and repeatable." if mode == "replay"
                    else "This server calls real models through the gateway: it costs money and takes time."),
    }


@router.post("/plan/preview")
def preview_plan(body: PreviewRequest, request: Request) -> dict:
    try:
        return plan_payload(build_plan(_engine(request).catalogue, body.selection))
    except PlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/projects", status_code=201)
def create_project(body: CreateProject, request: Request) -> dict:
    actor = actor_from(request)
    engine, store = _engine(request), _store(request)
    try:
        build_plan(engine.catalogue, body.selection)   # refuse a bad selection before anything is created
        project = store.projects.create(
            name=body.name, brief=body.brief, mode=request.app.state.settings.app_mode, selection=dict(body.selection), actor=actor,
        )
        engine.open_project(project.id)
        if body.connectors:
            # Connectors are SIMULATED: ticking one is recorded in the audit trail (structured, append-only) and changes no behaviour.
            store.audit.append(
                actor=actor, action="project.connectors_noted", target_type="project", target_id=project.id, project_id=project.id,
                detail={"connectors": body.connectors, "simulated": True},
            )
        return project_detail(project, engine.snapshot(project.id), connectors_of(store, project.id))
    except (PlanError, InvalidInput) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/projects")
def list_projects(request: Request, archived: bool = False) -> dict:
    store, engine = _store(request), _engine(request)
    projects = list(reversed(store.projects.list(archived=archived)))[:MAX_PROJECTS_LISTED]
    return {"projects": [project_summary(p, engine.snapshot(p.id)) for p in projects]}


@router.get("/projects/{project_id}")
def get_project(project_id: str, request: Request) -> dict:
    engine = _engine(request)
    try:
        project = _store(request).projects.get(project_id)
        return project_detail(project, engine.snapshot(project_id), connectors_of(_store(request), project_id))
    except (NotFoundError, InvalidInput) as exc:
        raise _fail(exc) from exc


@router.post("/projects/{project_id}/archive")
def archive_project(project_id: str, request: Request) -> dict:
    """Hide a project and make it read-only. Refused while a run is going on it, because that run could still be spending money."""
    actor = actor_from(request)
    runner = request.app.state.runner
    try:
        store = _store(request)
        store.projects.get(project_id)
        for phase_key in _engine(request).catalogue.phase_keys:
            if runner.is_active(project_id, phase_key):
                raise HTTPException(status_code=409, detail=f"{phase_key} is being written right now; wait for the run to end, or cancel it, before archiving")
        project = store.projects.archive(project_id, actor=actor)
        return project_detail(project, _engine(request).snapshot(project_id), connectors_of(store, project_id))
    except (NotFoundError, InvalidInput) as exc:
        raise _fail(exc) from exc


@router.post("/projects/{project_id}/restore")
def restore_project(project_id: str, request: Request) -> dict:
    actor = actor_from(request)
    try:
        store = _store(request)
        project = store.projects.restore(project_id, actor=actor)
        return project_detail(project, _engine(request).snapshot(project_id), connectors_of(store, project_id))
    except (NotFoundError, InvalidInput) as exc:
        raise _fail(exc) from exc
