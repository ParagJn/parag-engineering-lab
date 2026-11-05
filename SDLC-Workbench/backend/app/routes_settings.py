"""System settings over HTTP (S23d read, S23e save). Anyone with a name can READ them; secrets are only ever "set" or "not set". Saving needs an active Administrator, or, while nobody is
on the Users list, anyone with a name (the same rule as the Users list, so a missing ADMIN_NAME can never lock the app).

A saved change takes effect after a restart: the app reads its settings once when it starts. "restart_pending" is worked out from the file itself (does it now read differently from
what this running process loaded?), so it is true until the app has really been restarted, even if the page is reloaded.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .actor import actor_from
from .config import Settings
from .models import InvalidInput
from .routes_users import _require_admin
from .settings_admin import save as S
from .settings_admin.view import describe

router = APIRouter(prefix="/api")

RESTART_SENTENCE = "Saved. Restart the app for this to take effect."


class SaveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: dict[str, Any] = Field(max_length=100)


class RestoreBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)


def _paths(request: Request) -> tuple[Path | None, Path | None]:
    return getattr(request.app.state, "env_file", None), getattr(request.app.state, "env_backups", None)


def _pending(request: Request) -> bool:
    """Has the settings file moved on since this process started? Compared by what the app would READ, not by the text."""
    env, _ = _paths(request)
    if env is None or not env.exists():
        return False
    try:
        now = Settings(_env_file=env).model_dump_json()
    except Exception:                                           # a file the app would not accept is a change waiting to fail on restart
        return True
    return now != request.app.state.settings_at_start


def _can_edit(request: Request) -> bool:
    env, _ = _paths(request)
    if env is None:
        return False
    store = request.app.state.store
    if store.users.count_active() == 0:
        return True
    name = request.headers.get("x-actor", "")
    me = store.users.find(name.strip()) if name.strip() else None
    return bool(me and me.active and "Administrator" in me.roles)


def _answer(request: Request) -> dict:
    body = describe(request.app.state.settings, pending=_pending(request), can_edit=_can_edit(request))
    env, backups = _paths(request)
    body["editable"] = env is not None
    body["restart_sentence"] = RESTART_SENTENCE
    body["backups"] = S.list_backups(backups) if backups is not None else []
    if env is None:
        body["note"] += " This app was started with settings given to it, not from backend/.env, so they cannot be changed here."
    return body


def _refuse(exc: S.SaveRefused) -> HTTPException:
    return HTTPException(status_code=422, detail={"message": str(exc), "problems": exc.problems})


@router.get("/settings")
def read_settings(request: Request) -> dict:
    return _answer(request)


@router.put("/settings")
def save_settings(body: SaveBody, request: Request) -> dict:
    actor = _require_admin(request)
    env, backups = _paths(request)
    if env is None or backups is None:
        raise HTTPException(status_code=409, detail="this app was started with settings given to it, not from backend/.env, so they cannot be changed here")
    audit = request.app.state.store.audit

    def record(detail: dict[str, Any]) -> None:
        audit.append(actor=actor, action="settings.changed", target_type="settings", target_id="backend/.env", detail=detail)

    try:
        saved = S.save(env, backups, body.values, record=record)
    except S.SaveRefused as exc:
        raise _refuse(exc) from exc
    except (OSError, InvalidInput) as exc:
        raise HTTPException(status_code=500, detail=f"the settings file could not be written: {type(exc).__name__}") from exc
    return {**_answer(request), "saved": {"changed": saved.changed, "backup": saved.backup, "message": RESTART_SENTENCE if saved.restart else "Nothing was different, so nothing was saved."}}


@router.post("/settings/restore")
def restore_settings(body: RestoreBody, request: Request) -> dict:
    actor = _require_admin(request)
    env, backups = _paths(request)
    if env is None or backups is None:
        raise HTTPException(status_code=409, detail="this app was started with settings given to it, not from backend/.env, so they cannot be changed here")
    audit = request.app.state.store.audit

    def record(detail: dict[str, Any]) -> None:
        audit.append(actor=actor, action="settings.restored", target_type="settings", target_id="backend/.env", detail=detail)

    try:
        saved = S.restore(env, backups, body.name, record=record)
    except S.SaveRefused as exc:
        raise _refuse(exc) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"the settings file could not be written: {type(exc).__name__}") from exc
    return {**_answer(request), "saved": {"changed": saved.changed, "backup": saved.backup, "message": RESTART_SENTENCE if saved.restart else "That backup is what the file already says."}}
