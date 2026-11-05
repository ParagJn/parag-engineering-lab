"""Users and roles over HTTP (S23a). Users are global to the app, not per project. No sign-in: a name is a label, and the page says so.

Reading needs nothing. Changing the list needs a name (X-Actor) that is an active Administrator, or, while nobody is on the list yet, anyone, so a missing ADMIN_NAME can never lock the app.
Nothing here decides who may approve a phase; that is 23b.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from .access.decide import NotAllowed, deciding_role
from .access.roles import ADMIN, DEFAULT_APPROVERS, ROLES
from .actor import actor_from
from .models import ConflictError, InvalidInput, NotFoundError, User

router = APIRouter(prefix="/api")

NOTE = "A name is a label, not a password: this app runs on your own computer, so anyone who can open it can type any name."


class NewUser(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    roles: list[str] = Field(default_factory=list, max_length=len(ROLES))


class RolesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    roles: list[str] = Field(max_length=len(ROLES))


class ActiveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    active: bool


def user_payload(u: User) -> dict[str, Any]:
    return {"name": u.name, "active": u.active, "roles": list(u.roles), "created_by": u.created_by.removeprefix("human:"), "created_at": u.created_at}


def _store(request: Request):
    return request.app.state.store


def _require_admin(request: Request) -> str:
    """The acting name, if it may change the list: an active Administrator, or anyone while the list is empty."""
    actor = actor_from(request)
    users = _store(request).users
    if users.count_active() == 0:
        return actor
    me = users.find(actor.removeprefix("human:"))
    if me is None or not me.active or ADMIN not in me.roles:
        raise HTTPException(status_code=403, detail=f"only an {ADMIN} can change the Users list; ask one of them")
    return actor


def _plain(exc: Exception) -> HTTPException:
    code = 404 if isinstance(exc, NotFoundError) else 409 if isinstance(exc, ConflictError) else 422
    return HTTPException(status_code=code, detail=str(exc))


@router.get("/users")
def list_users(request: Request) -> dict:
    store = _store(request)
    users = store.users.list()
    return {
        "note": NOTE,
        "roles": list(ROLES),
        "users": [user_payload(u) for u in users],
        "approvers": {phase: list(roles) for phase, roles in store.users.approvers().items()},
        "defaults": {phase: list(roles) for phase, roles in DEFAULT_APPROVERS.items()},
        "empty": not any(u.active for u in users),
        "empty_hint": "Nobody is on the list yet, so nothing is restricted. Add ADMIN_NAME=<your name> to backend/.env and restart, or add the first person here.",
    }


@router.get("/users/me")
def who_am_i(request: Request) -> dict:
    """What the typed name may do: whether it is on the list, its roles, and which phases it may approve. Needs a name, changes nothing."""
    actor = actor_from(request)
    store = _store(request)
    me = store.users.find(actor.removeprefix("human:"))
    active = me is not None and me.active
    roles = me.roles if active else ()
    approvers = store.users.approvers()
    restricted = store.users.count_active() > 0
    can = [p for p, allowed in approvers.items() if not restricted or any(r in roles for r in allowed)]
    names = {p.key: p.name for p in request.app.state.engine.catalogue.phases} if hasattr(request.app.state, "engine") else {}
    why: dict[str, str] = {}
    for phase in approvers:
        if phase in can:
            continue
        try:
            deciding_role(store.users, actor, phase, names.get(phase, phase), "approved")
        except NotAllowed as exc:                                  # the same sentence the refusal itself gives
            why[phase] = str(exc)
    return {"name": actor.removeprefix("human:"), "on_list": active, "roles": list(roles), "administrator": ADMIN in roles, "list_in_force": restricted, "may_approve": can, "why_not": why}


@router.post("/users", status_code=201)
def add_user(body: NewUser, request: Request) -> dict:
    actor = _require_admin(request)
    try:
        return user_payload(_store(request).users.add(body.name, body.roles, actor=actor))
    except (InvalidInput, ConflictError, NotFoundError) as exc:
        raise _plain(exc) from exc


@router.put("/users/{name}/roles")
def set_roles(name: str, body: RolesBody, request: Request) -> dict:
    actor = _require_admin(request)
    try:
        return user_payload(_store(request).users.set_roles(name, body.roles, actor=actor))
    except (InvalidInput, ConflictError, NotFoundError) as exc:
        raise _plain(exc) from exc


@router.put("/users/{name}/active")
def set_active(name: str, body: ActiveBody, request: Request) -> dict:
    actor = _require_admin(request)
    try:
        return user_payload(_store(request).users.set_active(name, body.active, actor=actor))
    except (InvalidInput, ConflictError, NotFoundError) as exc:
        raise _plain(exc) from exc


@router.put("/approvers/{phase_key}")
def set_approvers(phase_key: str, body: RolesBody, request: Request) -> dict:
    actor = _require_admin(request)
    try:
        roles = _store(request).users.set_approvers(phase_key, body.roles, actor=actor)
    except (InvalidInput, ConflictError, NotFoundError) as exc:
        raise _plain(exc) from exc
    return {"phase": phase_key, "roles": list(roles)}
