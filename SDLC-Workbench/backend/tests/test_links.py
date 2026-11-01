from __future__ import annotations

import pytest

from app.models import InvalidInput, NotFoundError


def test_add_and_list(store, project):
    link = store.links.add(project.id, "DES-UJ-001", "REQ-F-001", "derives", actor="system")
    assert (link.from_id, link.to_id, link.kind, link.declared_in) == (
        "DES-UJ-001", "REQ-F-001", "derives", None
    )
    assert store.links.list(project.id) == [link]


def test_adding_the_same_link_twice_gives_one_row(store, project):
    first = store.links.add(project.id, "DES-UJ-001", "REQ-F-001", "derives", actor="system")
    again = store.links.add(project.id, "DES-UJ-001", "REQ-F-001", "derives", actor="human:ann")
    assert first == again
    assert len(store.links.list(project.id)) == 1
    added = [e for e in store.audit.list(project.id) if e.action == "link.added"]
    assert len(added) == 1


def test_same_pair_with_a_different_kind_is_a_different_link(store, project):
    store.links.add(project.id, "TST-001", "REQ-F-001", "verifies", actor="system")
    store.links.add(project.id, "TST-001", "REQ-F-001", "implements", actor="system")
    assert len(store.links.list(project.id)) == 2


def test_filters(store, project):
    store.links.add(project.id, "DES-001", "REQ-F-001", "derives", actor="system")
    store.links.add(project.id, "ARC-001", "REQ-F-001", "implements", actor="system")
    store.links.add(project.id, "ARC-001", "REQ-F-002", "implements", actor="system")
    ids = lambda links: [(l.from_id, l.to_id) for l in links]
    assert ids(store.links.list(project.id, to_id="REQ-F-001")) == [("DES-001", "REQ-F-001"), ("ARC-001", "REQ-F-001")]
    assert ids(store.links.list(project.id, from_id="ARC-001")) == [("ARC-001", "REQ-F-001"), ("ARC-001", "REQ-F-002")]
    assert ids(store.links.list(project.id, kind="derives")) == [("DES-001", "REQ-F-001")]


def test_links_are_per_project(store, project):
    other = store.projects.create(name="Other", actor="system")
    store.links.add(project.id, "DES-001", "REQ-F-001", "derives", actor="system")
    assert store.links.list(other.id) == []


def test_bad_links_are_refused(store, project):
    with pytest.raises(InvalidInput):
        store.links.add(project.id, "REQ-F-001", "REQ-F-001", "derives", actor="system")
    with pytest.raises(InvalidInput):
        store.links.add(project.id, "DES-001", "REQ-F-001", "friends", actor="system")
    for bad in ("req-1", "REQ-1", "", "free text"):
        with pytest.raises(InvalidInput):
            store.links.add(project.id, bad, "REQ-F-001", "derives", actor="system")
        with pytest.raises(InvalidInput):
            store.links.add(project.id, "DES-001", bad, "derives", actor="system")
    assert store.links.list(project.id) == []


def test_unknown_project(store):
    with pytest.raises(NotFoundError):
        store.links.add("nope", "DES-001", "REQ-F-001", "derives", actor="system")


def test_declared_in_must_exist_and_is_stored(store, project):
    with pytest.raises(NotFoundError):
        store.links.add(project.id, "DES-001", "REQ-F-001", "derives", actor="system", declared_in="DES-UJ-001")
    store.artefacts.create(
        project.id, artefact_type="user_journey", phase_key="design", title="Journey",
        actor="system", artefact_id="DES-UJ-001",
    )
    link = store.links.add(
        project.id, "DES-001", "REQ-F-001", "derives", actor="system", declared_in="DES-UJ-001"
    )
    assert link.declared_in == "DES-UJ-001"
