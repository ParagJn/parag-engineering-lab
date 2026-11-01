"""An archived project can be read but not changed (S12b addendum).

One check, used by every route that changes a project, so a hidden project can never keep running, spending money or collecting
documents. It reads the row afresh each time: the answer can change between two requests.
"""
from __future__ import annotations

from fastapi import HTTPException, Request

from .models import NotFoundError

SENTENCE = "This project is archived; restore it first."


def refuse_if_archived(request: Request, project_id: str) -> None:
    """Raise a 409 with the standard sentence if the project is archived. An unknown project is left for the route to report as a 404."""
    try:
        project = request.app.state.store.projects.get(project_id)
    except NotFoundError:
        return
    if project.archived_at is not None:
        raise HTTPException(status_code=409, detail=SENTENCE)
