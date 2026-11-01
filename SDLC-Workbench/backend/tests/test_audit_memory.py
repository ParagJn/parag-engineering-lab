from __future__ import annotations

import sqlite3

import pytest

from app.models import InvalidInput, NotFoundError


# ---- audit -----------------------------------------------------------------

def test_append_and_list_in_order(store, project):
    store.audit.append(actor="human:ann", action="note.a", target_type="x", target_id="1", project_id=project.id)
    store.audit.append(actor="system", action="note.b", target_type="x", target_id="2", project_id=project.id,
                       detail={"k": "v"})
    events = [e for e in store.audit.list(project.id) if e.action.startswith("note.")]
    assert [e.action for e in events] == ["note.a", "note.b"]
    assert events[1].detail == {"k": "v"}
    assert [e.id for e in events] == sorted(e.id for e in events)


def test_audit_filters(store, project):
    store.audit.append(actor="human:ann", action="a.one", target_type="x", target_id="T1", project_id=project.id)
    store.audit.append(actor="human:bob", action="a.two", target_type="x", target_id="T2", project_id=project.id)
    assert [e.action for e in store.audit.list(project.id, actor="human:bob")] == ["a.two"]
    assert [e.action for e in store.audit.list(project.id, action="a.one")] == ["a.one"]
    assert [e.action for e in store.audit.list(project.id, target_id="T2")] == ["a.two"]
    assert len(store.audit.list(project.id, limit=1)) == 1


def test_audit_rows_cannot_be_updated_or_deleted(store, project):
    event = store.audit.append(actor="system", action="x.y", target_type="x", target_id="1", project_id=project.id)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        with store.db.write() as conn:
            conn.execute("UPDATE audit SET actor = 'human:mallory' WHERE id = ?", (event.id,))
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        with store.db.write() as conn:
            conn.execute("DELETE FROM audit WHERE id = ?", (event.id,))
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        with store.db.write() as conn:
            conn.execute("DELETE FROM audit")
    assert store.audit.list(project.id)[-1] == event


def test_audit_validates_its_input(store, project):
    with pytest.raises(InvalidInput):
        store.audit.append(actor="somebody", action="x", target_type="x", target_id="1")
    with pytest.raises(InvalidInput):
        store.audit.append(actor="system", action=" ", target_type="x", target_id="1")


def test_a_full_flow_leaves_the_expected_trail(store):
    p = store.projects.create(name="Flow", actor="human:ann")
    store.phases.ensure(p.id, "requirements")
    store.phases.set_status(p.id, "requirements", "running", actor="system")
    store.artefacts.create(
        p.id, artefact_type="functional", phase_key="requirements", title="FR",
        actor="agent:analyst@model-sonnet", prefix="REQ-F",
    )
    store.artefacts.add_version(p.id, "REQ-F-001", body="text", author="agent:analyst@model-sonnet")
    store.artefacts.set_review_findings(
        p.id, "REQ-F-001", 1, {"verdict": "pass"}, actor="agent:reviewer@model-openai"
    )
    store.phases.set_status(p.id, "requirements", "awaiting_review", actor="system")
    store.memory.add(p.id, "human_feedback", "Add peak-load NFR", actor="human:ann", phase_key="requirements")
    store.phases.record_decision(p.id, "requirements", "approve", actor="human:ann")

    trail = [(e.action, e.actor) for e in store.audit.list(p.id)]
    assert trail == [
        ("project.created", "human:ann"),
        ("phase.created", "system"),
        ("phase.status", "system"),
        ("artefact.created", "agent:analyst@model-sonnet"),
        ("artefact.version_added", "agent:analyst@model-sonnet"),
        ("artefact.reviewed", "agent:reviewer@model-openai"),
        ("phase.status", "system"),
        ("memory.added", "human:ann"),
        ("phase.decided", "human:ann"),
    ]


def test_audit_ids_never_repeat_after_more_writes(store, project):
    first = [e.id for e in store.audit.list(project.id)]
    store.audit.append(actor="system", action="x.y", target_type="x", target_id="1", project_id=project.id)
    ids = [e.id for e in store.audit.list(project.id)]
    assert ids[: len(first)] == first
    assert len(set(ids)) == len(ids)


# ---- memory ----------------------------------------------------------------

def test_memory_add_and_list(store, project):
    m = store.memory.add(project.id, "reviewer_feedback", "  Peak load missing  ", actor="agent:rev@m",
                         phase_key="requirements")
    assert m.text == "Peak load missing"
    assert (m.kind, m.phase_key, m.artefact_id) == ("reviewer_feedback", "requirements", None)
    assert store.memory.list(project.id) == [m]


def test_memory_is_scoped_per_project(store, project):
    other = store.projects.create(name="Other", actor="system")
    store.memory.add(project.id, "note", "mine", actor="system")
    store.memory.add(other.id, "note", "theirs", actor="system")
    assert [m.text for m in store.memory.list(project.id)] == ["mine"]
    assert [m.text for m in store.memory.list(other.id)] == ["theirs"]


def test_memory_filters(store, project):
    store.artefacts.create(
        project.id, artefact_type="t", phase_key="requirements", title="T", actor="system", artefact_id="REQ-F-001"
    )
    store.memory.add(project.id, "note", "n1", actor="system", phase_key="requirements")
    store.memory.add(project.id, "human_feedback", "h1", actor="human:ann", phase_key="design")
    store.memory.add(project.id, "human_feedback", "h2", actor="human:ann", artefact_id="REQ-F-001")
    assert [m.text for m in store.memory.list(project.id, kind="human_feedback")] == ["h1", "h2"]
    assert [m.text for m in store.memory.list(project.id, phase_key="design")] == ["h1"]
    assert [m.text for m in store.memory.list(project.id, artefact_id="REQ-F-001")] == ["h2"]


def test_memory_input_checks(store, project):
    for text in ("", "  ", None):
        with pytest.raises(InvalidInput):
            store.memory.add(project.id, "note", text, actor="system")
    with pytest.raises(InvalidInput):
        store.memory.add(project.id, "gossip", "x", actor="system")
    with pytest.raises(NotFoundError):
        store.memory.add("nope", "note", "x", actor="system")
    with pytest.raises(NotFoundError):
        store.memory.add(project.id, "note", "x", actor="system", artefact_id="REQ-F-404")
    assert store.memory.list(project.id) == []
