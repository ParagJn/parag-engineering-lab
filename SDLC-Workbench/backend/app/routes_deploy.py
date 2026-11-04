"""Deploy over HTTP (S21b): the plan and the release notes as downloadable files.

Read-only: it changes nothing, so it needs no name, and an archived project can still be read. The Markdown is the saved text byte for byte; the Word file is made from
that same text, on the server, with no model. Only the two documents a person is meant to hand on can be downloaded here.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from .deploy.docx_writer import DocInfo, markdown_to_docx
from .models import InvalidInput, NotFoundError

router = APIRouter(prefix="/api/projects/{project_id}")

DOWNLOADABLE = ("deployment_plan", "release_notes", "runbook", "hypercare_plan")
ARTEFACT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MD_TYPE = "text/markdown; charset=utf-8"


def _when(text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return None


@router.get("/artefacts/{artefact_id}/download")
def download_artefact(project_id: str, artefact_id: str, request: Request, format: str = Query(default="md"), version: int | None = Query(default=None, ge=1, le=100000)) -> Response:
    if not ARTEFACT_ID.fullmatch(artefact_id):
        raise HTTPException(status_code=422, detail="artefact id has unexpected characters")
    if format not in ("md", "docx"):
        raise HTTPException(status_code=422, detail="format must be 'md' or 'docx'")
    store = request.app.state.store
    try:
        project = store.projects.get(project_id)
        artefact = store.artefacts.get(project_id, artefact_id)
        if artefact.type not in DOWNLOADABLE:
            raise InvalidInput(f"{artefact.title} cannot be downloaded as a file here; the deployment plan, the release notes, the runbook and the hypercare plan can")
        if artefact.latest_version is None:
            raise NotFoundError(f"{artefact_id} has not been written yet, so there is nothing to download")
        shown = store.artefacts.get_version(project_id, artefact_id, version)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except InvalidInput as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    name = f"{artefact_id}-v{shown.number}"
    if format == "md":
        return Response(shown.body, media_type=MD_TYPE, headers={"Content-Disposition": f'attachment; filename="{name}.md"'})
    data = markdown_to_docx(shown.body, DocInfo(title=f"{artefact.title} - {project.name}", subject=f"{artefact_id} version {shown.number}", created=_when(shown.created_at)))
    return Response(data, media_type=DOCX_TYPE, headers={"Content-Disposition": f'attachment; filename="{name}.docx"'})


# ---- the deployment checklist (S21c) --------------------------------------------------------------------------------------------------------

from typing import Any  # noqa: E402

from fastapi import Request as _Request  # noqa: E402,F401
from pydantic import BaseModel, ConfigDict, Field  # noqa: E402

from .actor import actor_from  # noqa: E402
from .archive import refuse_if_archived  # noqa: E402
from .deploy import checklist as CL  # noqa: E402
from .deploy import checks as CK  # noqa: E402
from .review.errors import PersonRequired, WrongPhaseState  # noqa: E402


class AnswerBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str = Field(max_length=20)
    note: str = Field(default="", max_length=CK.MAX_NOTE_CHARS)


def answer_payload(a) -> dict[str, Any]:
    return {"answer": a.answer, "note": a.note, "by": a.actor, "at": a.at}


def checklist_payload(checklist: CL.Checklist) -> dict[str, Any]:
    spec = checklist.spec
    return {
        "groups": [{"key": g, "title": spec.group_title[g], "checks": [
            {"id": r.check.id, "question": r.check.question, "from": r.check.from_where,
             "latest": answer_payload(r.latest) if r.latest else None, "history": [answer_payload(h) for h in r.history]}
            for r in checklist.rows if r.check.group == g]} for g in spec.groups],
        "totals": {"total": checklist.total, "go": checklist.go, "no_go": checklist.no_go, "not_applicable": checklist.not_applicable, "unanswered": checklist.unanswered},
        "decision": checklist.decision, "complete": checklist.complete, "decision_check": spec.decision_id,
        "phase": spec.phase, "title": spec.title, "answer_words": spec.answer_words,
    }


def _spec_or_404(phase: str):
    """The checklist of a phase, or a 404 naming the phases that have one."""
    try:
        return CK.definition_of(phase)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=exc.args[0]) from exc


def _checklist(phase: str, project_id: str, request: Request) -> dict:
    _spec_or_404(phase)
    try:
        return checklist_payload(CL.build(request.app.state.store, project_id, phase))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _report(phase: str, project_id: str, request: Request, format: str) -> Response:
    """The checklist as a one-page report to file: Markdown, or Word made from the same Markdown. Read-only; the latest answer of each check, who and when."""
    spec = _spec_or_404(phase)
    if format not in ("md", "docx"):
        raise HTTPException(status_code=422, detail="format must be 'md' or 'docx'")
    store = request.app.state.store
    try:
        project = store.projects.get(project_id)
        text = CL.report_markdown(CL.build(store, project_id, phase), project.name)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    name = spec.report_title.lower().replace(" ", "-")
    if format == "md":
        return Response(text, media_type=MD_TYPE, headers={"Content-Disposition": f'attachment; filename="{name}.md"'})
    data = markdown_to_docx(text, DocInfo(title=f"{spec.report_title} - {project.name}", subject=f"{spec.report_title} checklist"))
    return Response(data, media_type=DOCX_TYPE, headers={"Content-Disposition": f'attachment; filename="{name}.docx"'})


def _answer(phase: str, project_id: str, check_id: str, body: AnswerBody, request: Request) -> dict:
    actor = actor_from(request)
    spec = _spec_or_404(phase)
    if not spec.by_id.get(check_id) and not CK.CHECK_ID.fullmatch(check_id):
        raise HTTPException(status_code=422, detail="a check ID looks like CHK-001")
    refuse_if_archived(request, project_id)
    store = request.app.state.store
    try:
        CL.answer(store, project_id, check_id, body.answer, actor=actor, note=body.note, phase=phase)
        return checklist_payload(CL.build(store, project_id, phase))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WrongPhaseState as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (PersonRequired, InvalidInput) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# Deploy's addresses, exactly as they were.
@router.get("/deploy/checklist")
def get_checklist(project_id: str, request: Request) -> dict:
    return _checklist("deploy", project_id, request)


@router.get("/deploy/checklist/report")
def checklist_report(project_id: str, request: Request, format: str = Query(default="md")) -> Response:
    return _report("deploy", project_id, request, format)


@router.put("/deploy/checklist/{check_id}")
def answer_check(project_id: str, check_id: str, body: AnswerBody, request: Request) -> dict:
    return _answer("deploy", project_id, check_id, body, request)


# Every other phase that has a checklist (S22a): the same three routes under its own name. A phase without one is a 404 that names the phases that do.
@router.get("/{phase}/checklist")
def get_phase_checklist(project_id: str, phase: str, request: Request) -> dict:
    return _checklist(phase, project_id, request)


@router.get("/{phase}/checklist/report")
def phase_checklist_report(project_id: str, phase: str, request: Request, format: str = Query(default="md")) -> Response:
    return _report(phase, project_id, request, format)


@router.put("/{phase}/checklist/{check_id}")
def answer_phase_check(project_id: str, phase: str, check_id: str, body: AnswerBody, request: Request) -> dict:
    return _answer(phase, project_id, check_id, body, request)
