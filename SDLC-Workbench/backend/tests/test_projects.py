from __future__ import annotations

import pytest

import app.repos as repos
from app.models import InvalidInput, NotFoundError


def test_create_get_list_count_round_trip(store):
    a = store.projects.create(name="Alpha", actor="human:ann", brief="A brief", mode="live")
    b = store.projects.create(name="Beta", actor="system")
    assert store.projects.get(a.id) == a
    assert [p.id for p in store.projects.list()] == [a.id, b.id]
    assert store.projects.count() == 2
    assert (a.name, a.brief, a.mode) == ("Alpha", "A brief", "live")


def test_defaults(store):
    p = store.projects.create(name="  Padded  ", actor="system")
    assert p.name == "Padded"
    assert p.mode == "replay"
    assert p.brief == ""
    assert p.selection == {} and p.routing_overrides == {}
    assert p.context_id is None
    assert p.created_at == p.updated_at


def test_json_fields_round_trip(store):
    selection = {"requirements": ["personas", "epics"], "design": {"wireframes": True}}
    overrides = {"ux_designer": "gemini"}
    p = store.projects.create(
        name="J", actor="system", selection=selection, routing_overrides=overrides
    )
    got = store.projects.get(p.id)
    assert got.selection == selection
    assert got.routing_overrides == overrides


@pytest.mark.parametrize("name", ["", "   ", None])
def test_blank_name_is_rejected(store, name):
    with pytest.raises(InvalidInput):
        store.projects.create(name=name, actor="system")


def test_bad_mode_and_bad_json_are_rejected(store):
    with pytest.raises(InvalidInput):
        store.projects.create(name="N", actor="system", mode="turbo")
    with pytest.raises(InvalidInput):
        store.projects.create(name="N", actor="system", selection=["not", "an", "object"])
    with pytest.raises(InvalidInput):
        store.projects.create(name="N", actor="system", selection={"x": object()})
    assert store.projects.count() == 0


def test_invalid_actor_is_rejected(store):
    for actor in ("", "bob", "agent:no-model", "human:", "agent:@m"):
        with pytest.raises(InvalidInput):
            store.projects.create(name="N", actor=actor)
    assert store.projects.count() == 0


def test_unknown_project(store):
    with pytest.raises(NotFoundError):
        store.projects.get("nope")
    with pytest.raises(NotFoundError):
        store.projects.update("nope", actor="system", name="X")


def test_update_changes_only_what_is_given_and_bumps_updated_at(store, project):
    updated = store.projects.update(project.id, actor="human:ann", brief="New brief")
    assert updated.brief == "New brief"
    assert updated.name == project.name
    assert updated.mode == project.mode
    assert updated.created_at == project.created_at
    assert updated.updated_at > project.updated_at


def test_update_can_clear_context_id(store):
    p = store.projects.create(name="C", actor="system", context_id="ctx-1")
    assert store.projects.update(p.id, actor="system", context_id="ctx-2").context_id == "ctx-2"
    assert store.projects.update(p.id, actor="system", context_id=None).context_id is None


def test_update_with_nothing_to_change_is_a_no_op(store, project):
    before = len(store.audit.list(project.id))
    assert store.projects.update(project.id, actor="system") == project
    assert len(store.audit.list(project.id)) == before


def test_update_rejects_bad_values(store, project):
    with pytest.raises(InvalidInput):
        store.projects.update(project.id, actor="system", name="  ")
    with pytest.raises(InvalidInput):
        store.projects.update(project.id, actor="system", mode="turbo")
    assert store.projects.get(project.id) == project


def test_create_and_update_write_audit_rows(store):
    p = store.projects.create(name="Audited", actor="human:ann")
    store.projects.update(p.id, actor="human:bob", name="Renamed")
    events = store.audit.list(p.id)
    assert [(e.action, e.actor) for e in events] == [
        ("project.created", "human:ann"),
        ("project.updated", "human:bob"),
    ]
    assert events[1].detail == {"changed": ["name"]}


def test_a_failed_audit_write_rolls_the_change_back(store, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("audit down")

    monkeypatch.setattr(repos, "write_audit", broken)
    with pytest.raises(RuntimeError):
        store.projects.create(name="Never saved", actor="system")
    assert store.projects.count() == 0
