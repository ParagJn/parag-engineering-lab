"""A new version REPLACES the links its artefact declared (the defect found after S11 closed), and the rest of the
repository changes S08 made: notes saved with a rejection, the decision detail, the settings."""
from __future__ import annotations

import sqlite3

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.models import InvalidInput

import app.repos as repos

ART = dict(artefact_type="personas", phase_key="requirements", title="Personas")


@pytest.fixture
def art(store, project):
    store.artefacts.create(project.id, actor="system", artefact_id="REQ-PER-001", **ART)
    store.artefacts.create(project.id, actor="system", artefact_id="REQ-PRB-001", artefact_type="problem_statement", phase_key="requirements", title="P")
    return store


def pairs(store, project, declared_in=None):
    return sorted((l.from_id, l.to_id) for l in store.links.list(project.id) if declared_in is None or l.declared_in == declared_in)


def save(store, project, links, body="b", artefact="REQ-PER-001", author="human:ann"):
    return store.artefacts.add_version(project.id, artefact, body=body, author=author, links=links)


# ---- the probe from S11, now fixed ------------------------------------------------------------------------------------------

def test_version_two_ends_with_exactly_the_links_version_two_declares(art, store, project):
    save(store, project, [("PER-002", "SET-CHR-001", "derives")])
    assert pairs(store, project) == [("PER-002", "SET-CHR-001")]       # precondition: version 1's link exists
    save(store, project, [("PER-002", "PER-001", "derives")])
    assert pairs(store, project) == [("PER-002", "PER-001")]            # the old link is gone, not left beside the new one


def test_a_removed_link_leaves_an_audit_row_naming_the_version_that_replaced_it(art, store, project):
    save(store, project, [("PER-002", "SET-CHR-001", "derives")])
    save(store, project, [])
    [event] = store.audit.list(project.id, action="link.removed")
    assert event.target_id == "PER-002>derives>SET-CHR-001" and event.actor == "human:ann"
    assert event.detail == {"declared_in": "REQ-PER-001", "replaced_by_version": 2}


def test_an_unchanged_link_is_kept_and_not_rewritten(art, store, project):
    save(store, project, [("PER-001", "SET-CHR-001", "derives")])
    first = store.links.list(project.id)[0]
    save(store, project, [("PER-001", "SET-CHR-001", "derives")])
    again = store.links.list(project.id)[0]
    assert (again.id, again.created_at) == (first.id, first.created_at)
    assert len(store.audit.list(project.id, action="link.added")) == 1 and store.audit.list(project.id, action="link.removed") == []


def test_links_declared_by_another_artefact_are_untouched(art, store, project):
    save(store, project, [("PER-001", "SET-CHR-001", "derives")], artefact="REQ-PRB-001")
    save(store, project, [("PER-001", "PER-002", "derives")])
    save(store, project, [])
    assert pairs(store, project, "REQ-PRB-001") == [("PER-001", "SET-CHR-001")]
    assert pairs(store, project, "REQ-PER-001") == []


def test_a_link_added_by_hand_with_no_declaring_artefact_is_never_removed(art, store, project):
    store.links.add(project.id, "DES-UJ-001", "REQ-F-001", "derives", actor="human:ann")
    save(store, project, [("PER-001", "SET-CHR-001", "derives")])
    save(store, project, [])
    assert pairs(store, project) == [("DES-UJ-001", "REQ-F-001")]


def test_leaving_links_out_touches_no_links(art, store, project):
    save(store, project, [("PER-001", "SET-CHR-001", "derives")])
    store.artefacts.add_version(project.id, "REQ-PER-001", body="no link argument at all", author="human:ann")
    assert pairs(store, project) == [("PER-001", "SET-CHR-001")]


def test_an_empty_list_removes_every_link_the_artefact_declared(art, store, project):
    save(store, project, [("PER-001", "SET-CHR-001", "derives"), ("PER-002", "SET-CHR-001", "derives")])
    save(store, project, [])
    assert pairs(store, project) == []


def test_repeats_inside_one_version_make_one_link(art, store, project):
    save(store, project, [("PER-001", "SET-CHR-001", "derives")] * 3)
    assert pairs(store, project) == [("PER-001", "SET-CHR-001")]


def test_a_failed_save_leaves_the_old_links_and_no_new_version(art, store, project, monkeypatch):
    save(store, project, [("PER-001", "SET-CHR-001", "derives")])
    real = repos._insert_link
    calls = []

    def fail_second(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise sqlite3.OperationalError("disk full")
        return real(*args, **kwargs)

    monkeypatch.setattr(repos, "_insert_link", fail_second)
    with pytest.raises(sqlite3.OperationalError):
        save(store, project, [("PER-001", "PER-002", "derives"), ("PER-001", "PER-003", "derives")])
    assert len(calls) == 2  # precondition: the first NEW link was written (and the old one deleted) before the failure
    assert pairs(store, project) == [("PER-001", "SET-CHR-001")]
    assert store.artefacts.get(project.id, "REQ-PER-001").latest_version == 1


def test_a_malformed_link_is_refused_before_anything_is_written(art, store, project):
    with pytest.raises(InvalidInput, match="is not like"):
        save(store, project, [("PER-001", "SET-CHR-001", "derives"), ("nonsense", "SET-CHR-001", "derives")])
    assert store.artefacts.get(project.id, "REQ-PER-001").latest_version is None and pairs(store, project) == []


def test_a_guard_that_raises_stops_the_save_and_touches_no_links(art, store, project):
    save(store, project, [("PER-001", "SET-CHR-001", "derives")])

    def refuse(conn):
        raise InvalidInput("no")

    with pytest.raises(InvalidInput, match="no"):
        store.artefacts.add_version(project.id, "REQ-PER-001", body="x", author="human:ann", links=[], guard=refuse)
    assert pairs(store, project) == [("PER-001", "SET-CHR-001")] and store.artefacts.get(project.id, "REQ-PER-001").latest_version == 1


def test_create_and_add_version_replaces_links_too(store, project):
    kw = dict(artefact_type="personas", phase_key="requirements", title="Personas", prefix="REQ-PER", author="agent:r@m")
    store.artefacts.create_and_add_version(project.id, body="a", links=[("PER-001", "SET-CHR-001", "derives")], **kw)
    store.artefacts.create_and_add_version(project.id, body="b", links=[("PER-001", "PER-002", "derives")], **kw)
    assert pairs(store, project) == [("PER-001", "PER-002")]


# ---- notes saved with a rejection ------------------------------------------------------------------------------------------------

@pytest.fixture
def awaiting(store, project):
    store.phases.ensure(project.id, "requirements", actor="system")
    store.phases.set_status(project.id, "requirements", "running", actor="system")
    store.phases.set_status(project.id, "requirements", "awaiting_review", actor="system")
    store.artefacts.create(project.id, actor="system", artefact_id="REQ-PER-001", **ART)
    return store


def test_notes_are_saved_in_the_same_transaction_as_the_rejection(awaiting, store, project):
    store.phases.record_decision(project.id, "requirements", "reject", actor="human:ann", feedback="redo",
                                 notes=[("REQ-PER-001", "human_feedback", "  be specific  "), (None, "human_feedback", "whole phase")])
    assert [(m.artefact_id, m.kind, m.phase_key, m.text) for m in store.memory.list(project.id)] == [
        ("REQ-PER-001", "human_feedback", "requirements", "be specific"), (None, "human_feedback", "requirements", "whole phase")]
    assert store.audit.list(project.id, action="phase.decided")[-1].detail["notes"] == 2


def test_a_rejection_that_fails_part_way_saves_no_notes_and_leaves_the_phase_as_it_was(awaiting, store, project, monkeypatch):
    real = repos._insert_memory
    calls = []

    def fail_second(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise sqlite3.OperationalError("disk full")
        return real(*args, **kwargs)

    monkeypatch.setattr(repos, "_insert_memory", fail_second)
    with pytest.raises(sqlite3.OperationalError):
        store.phases.record_decision(project.id, "requirements", "reject", actor="human:ann", feedback="redo",
                                     notes=[("REQ-PER-001", "human_feedback", "a"), (None, "human_feedback", "b")])
    assert len(calls) == 2 and store.memory.list(project.id) == []
    assert store.phases.get(project.id, "requirements").status == "awaiting_review"


@pytest.mark.parametrize("notes, message", [
    ([("REQ-PER-001", "gossip", "x")], "kind must be one of"),
    ([("REQ-PER-001", "human_feedback", "   ")], "must not be blank"),
    ([("REQ-PER-999", "human_feedback", "x")], "not found"),
])
def test_bad_notes_refuse_the_whole_rejection(awaiting, store, project, notes, message):
    with pytest.raises(Exception, match=message):
        store.phases.record_decision(project.id, "requirements", "reject", actor="human:ann", feedback="redo", notes=notes)
    assert store.phases.get(project.id, "requirements").status == "awaiting_review" and store.memory.list(project.id) == []


def test_a_note_about_an_artefact_of_another_phase_is_refused(awaiting, store, project):
    store.artefacts.create(project.id, actor="system", artefact_id="SET-CHR-001", artefact_type="project_charter", phase_key="setup", title="C")
    with pytest.raises(InvalidInput, match="belongs to phase 'setup', not 'requirements'"):
        store.phases.record_decision(project.id, "requirements", "reject", actor="human:ann", feedback="redo", notes=[("SET-CHR-001", "human_feedback", "x")])


def test_notes_cannot_travel_with_an_approval(awaiting, store, project):
    with pytest.raises(InvalidInput, match="only be saved with a rejection"):
        store.phases.record_decision(project.id, "requirements", "approve", actor="human:ann", notes=[(None, "human_feedback", "x")])
    assert store.phases.get(project.id, "requirements").status == "awaiting_review"


def test_extra_detail_is_added_to_the_decision_audit_row_without_replacing_the_standard_fields(awaiting, store, project):
    store.phases.record_decision(project.id, "requirements", "reject", actor="human:ann", feedback="redo", detail={"extra": 1})
    assert store.audit.list(project.id, action="phase.decided")[-1].detail == {"decision": "reject", "feedback": "redo", "extra": 1}


# ---- settings ----------------------------------------------------------------------------------------------------------------------------

def test_review_setting_defaults_match_the_spec():
    s = Settings(_env_file=None)
    assert (s.review_max_output_tokens, s.review_max_repairs, s.review_max_findings, s.review_cited_max_chars) == (8000, 1, 20, 8000)


@pytest.mark.parametrize("field, bad", [
    ("review_max_output_tokens", 10), ("review_max_repairs", 4), ("review_max_repairs", -1),
    ("review_max_findings", 0), ("review_cited_max_chars", -1),
])
def test_out_of_range_review_settings_are_rejected(field, bad):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: bad})
