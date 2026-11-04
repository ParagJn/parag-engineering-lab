"""Build Verify over HTTP (S20b). It reads the person's own folders on THIS computer, as text, and never runs anything in them.

The answer holds item IDs, short labels, file paths relative to the folder named, line numbers and counts. It never holds source text, and a path the person typed is
returned only as typed.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from .actor import actor_from
from .archive import refuse_if_archived
from .models import NotFoundError, VerifyMatch, VerifyRun
from .verify import report as R
from .verify.service import FolderProblem, check

router = APIRouter(prefix="/api/projects/{project_id}/verify")
MAX_PATH_CHARS = 1000


class VerifyBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    backend_path: str = Field(min_length=1, max_length=MAX_PATH_CHARS)


AREAS = set(R.AREAS)


def run_payload(run: VerifyRun) -> dict[str, Any]:
    """A run as the screen gets it. Runs made before S20f also hold screens (and a frontend folder); they stay in the record, but they are not shown or counted."""
    return {"id": run.id, "backend_path": run.backend_path, "by": run.actor, "at": run.at, "design": run.design,
            "counts": [c for c in run.counts if c.get("area") in AREAS], "notes": [n for n in run.notes if not n.startswith("frontend:")]}


def shown(matches: list[VerifyMatch]) -> list[VerifyMatch]:
    return [m for m in matches if m.area in AREAS]


def match_payload(m: VerifyMatch) -> dict[str, Any]:
    return {"designed": m.designed, "area": m.area, "state": m.state, "step": m.step, "score": m.score, "built": m.built, "file": m.file, "line": m.line,
            "differences": list(m.differences), "note": m.note}


@router.post("")
def run_check(project_id: str, body: VerifyBody, request: Request) -> dict:
    actor = actor_from(request)
    refuse_if_archived(request, project_id)
    store = request.app.state.store
    try:
        store.projects.get(project_id)
        run, _report = check(store, request.app.state.skills, project_id, backend_path=body.backend_path, actor=actor)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FolderProblem as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {**run_payload(run), "matches": [match_payload(m) for m in store.verify.matches(project_id, run.id)]}          # a new run never holds a screen, so there is nothing to hide


@router.get("")
def list_runs(project_id: str, request: Request) -> dict:
    try:
        runs = request.app.state.store.verify.runs(project_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"advice": R.ADVICE, "runs": [run_payload(r) for r in runs]}


@router.get("/{run_id}")
def one_run(project_id: str, run_id: int, request: Request) -> dict:
    store = request.app.state.store
    try:
        run = store.verify.run(project_id, run_id)
        matches = store.verify.matches(project_id, run_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {**run_payload(run), "advice": R.ADVICE, "matches": [match_payload(m) for m in shown(matches)]}


@router.get("/{run_id}/download")
def download(project_id: str, run_id: int, request: Request, format: str = "md") -> Response:
    store = request.app.state.store
    try:
        run = store.verify.run(project_id, run_id)
        matches = shown(store.verify.matches(project_id, run_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if format == "json":
        import json
        text = json.dumps({**run_payload(run), "advice": R.ADVICE, "matches": [match_payload(m) for m in matches]}, indent=2, sort_keys=True)
        return Response(text, media_type="application/json", headers={"Content-Disposition": f'attachment; filename="build-verify-{run_id}.json"'})
    from .verify.match import Extra, Match
    designed = [Match(m.designed, m.area, m.state, m.step, m.score, m.built, m.file, m.line, m.differences, m.note) for m in matches if m.state != "extra"]
    extras = [Extra(m.area, m.built, m.file, m.line) for m in matches if m.state == "extra"]
    text = R.markdown(R.build_report(designed, extras, run_payload(run)["notes"]), design_versions=run.design)
    return Response(text, media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="build-verify-{run_id}.md"'})
