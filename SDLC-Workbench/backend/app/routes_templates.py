"""Word templates over HTTP (S23 Part C). Each project keeps at most one template per document type, as a .docx file in the git-ignored data folder.

Reading and downloading need no name and no role. Uploading, replacing and removing need a name that is an active Project Manager or Administrator, or any name while nobody is on the
Users list yet (the same rule as the rest of Configuration, so a missing ADMIN_NAME can never lock the app). An archived project is read-only.

This only STORES templates. It does not change how any document is downloaded.
"""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response

from .actor import actor_from
from .archive import refuse_if_archived
from .models import NotFoundError
from .templates import store as T

router = APIRouter(prefix="/api/projects/{project_id}/templates")

ALLOWED_ROLES = ("Project Manager", "Administrator")
DOCX = T.DOCX_TYPE


def _root(request: Request):
    root = getattr(request.app.state, "templates_root", None)
    if root is None:
        raise HTTPException(status_code=409, detail="this app has no place to keep templates")
    return root


def _project(request: Request, project_id: str) -> None:
    try:
        request.app.state.store.projects.get(project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def may_change(request: Request) -> bool:
    users = request.app.state.store.users
    if users.count_active() == 0:
        return True
    name = request.headers.get("x-actor", "").strip()
    me = users.find(name) if name else None
    return bool(me and me.active and any(r in me.roles for r in ALLOWED_ROLES))


def _require_change(request: Request) -> str:
    actor = actor_from(request)
    if not may_change(request):
        raise HTTPException(status_code=403, detail="only a Project Manager or an Administrator can change a project's templates; ask one of them")
    return actor


def _refuse(exc: Exception) -> HTTPException:
    code = 404 if isinstance(exc, T.TemplateMissing) else 422
    return HTTPException(status_code=code, detail=str(exc))


def _answer(request: Request, project_id: str) -> dict[str, Any]:
    root = _root(request)
    have = {t.category: t for t in T.listing(root, project_id)}
    return {
        "categories": [{"category": c, "label": label, "template": T.payload(have[c]) if c in have else None} for c, label in T.CATEGORIES.items()],
        "can_change": may_change(request),
        "max_mb": T.MAX_TEMPLATE_BYTES // (1024 * 1024),
        "note": "A template is a Word file (.docx) that gives a document its look: styles, page and header and footer. A new upload replaces the old one. It is used only if it has a table of contents.",
    }


@router.get("")
def list_templates(project_id: str, request: Request) -> dict:
    _project(request, project_id)
    try:
        return _answer(request, project_id)
    except T.TemplateRefused as exc:
        raise _refuse(exc) from exc


@router.post("/{category}", status_code=201)
async def upload_template(project_id: str, category: str, request: Request, file: UploadFile = File(...)) -> dict:
    actor = _require_change(request)
    _project(request, project_id)
    refuse_if_archived(request, project_id)
    name = (file.filename or "").strip()
    if not name.lower().endswith(".docx"):
        raise HTTPException(status_code=422, detail="a template must be a Word document with the name ending .docx")
    data = await file.read(T.MAX_TEMPLATE_BYTES + 1)          # one byte over the limit is enough to refuse it, without reading all of a huge upload
    root = _root(request)
    try:
        info = await asyncio.to_thread(T.save, root, project_id, category, data)
    except T.TemplateRefused as exc:
        raise _refuse(exc) from exc
    request.app.state.store.audit.append(actor=actor, action="template.uploaded", target_type="template", target_id=f"{project_id}/{category}", project_id=project_id,
                                         detail={"category": category, "size": info.size, "has_toc": info.has_toc})
    return {**_answer(request, project_id), "saved": T.payload(info)}


@router.delete("/{category}")
def remove_template(project_id: str, category: str, request: Request) -> dict:
    actor = _require_change(request)
    _project(request, project_id)
    refuse_if_archived(request, project_id)
    try:
        T.remove(_root(request), project_id, category)
    except (T.TemplateRefused, T.TemplateMissing) as exc:
        raise _refuse(exc) from exc
    request.app.state.store.audit.append(actor=actor, action="template.removed", target_type="template", target_id=f"{project_id}/{category}", project_id=project_id,
                                         detail={"category": category})
    return _answer(request, project_id)


@router.get("/{category}/download")
def download_template(project_id: str, category: str, request: Request) -> Response:
    _project(request, project_id)
    try:
        data = T.read(_root(request), project_id, category)
    except (T.TemplateRefused, T.TemplateMissing) as exc:
        raise _refuse(exc) from exc
    return Response(data, media_type=DOCX, headers={"Content-Disposition": f'attachment; filename="{category}-template.docx"'})
