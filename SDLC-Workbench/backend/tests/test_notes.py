"""Which saved notes still need acting on: the one rule the writer's prompt and the re-run both depend on."""
from __future__ import annotations

import pytest

from app.agents.notes import unacted_notes
from app.repos import Store

ART = dict(artefact_type="personas", phase_key="requirements", title="Personas", prefix="REQ-PER")


def texts(store, project, artefact="REQ-PER-001"):
    return [n.text for n in unacted_notes(store, project.id, "requirements", artefact)]


def test_a_note_written_before_the_current_version_has_been_acted_on(store, project):
    store.artefacts.create(project.id, actor="system", **ART)
    store.artefacts.add_version(project.id, "REQ-PER-001", body="v1", author="human:ann")
    store.memory.add(project.id, "human_feedback", "old note", actor="human:ann", phase_key="requirements", artefact_id="REQ-PER-001")
    assert texts(store, project) == ["old note"]   # precondition: written after v1, so v1 has not acted on it
    store.artefacts.add_version(project.id, "REQ-PER-001", body="v2", author="human:ann")
    assert texts(store, project) == []


def test_a_note_written_after_the_current_version_still_needs_acting_on(store, project):
    store.artefacts.create(project.id, actor="system", **ART)
    store.artefacts.add_version(project.id, "REQ-PER-001", body="v1", author="human:ann")
    store.memory.add(project.id, "human_feedback", "new note", actor="human:ann", phase_key="requirements", artefact_id="REQ-PER-001")
    assert texts(store, project) == ["new note"]


def test_a_note_and_a_version_made_in_the_same_instant_keep_the_note_because_the_version_is_not_provably_newer(tmp_path):
    """Timestamps have millisecond resolution. If a note and a version carry the same stamp, we cannot tell which came
    first, and dropping the note would lose feedback nobody acted on. Showing it once too often is harmless."""
    store = Store.open(tmp_path / "same.db", clock=lambda: "2026-01-01T00:00:00.000Z")
    project = store.projects.create(name="P", actor="system")
    store.artefacts.create(project.id, actor="system", **ART)
    store.memory.add(project.id, "human_feedback", "same instant", actor="human:ann", phase_key="requirements", artefact_id="REQ-PER-001")
    store.artefacts.add_version(project.id, "REQ-PER-001", body="v1", author="human:ann")
    note, version = store.memory.list(project.id)[0], store.artefacts.get_version(project.id, "REQ-PER-001")
    assert note.created_at == version.created_at   # precondition: the two really are the same instant
    assert texts(store, project) == ["same instant"]


def test_a_phase_wide_note_applies_to_every_artefact_and_a_note_for_another_artefact_to_none_but_its_own(store, project):
    store.artefacts.create(project.id, actor="system", **ART)
    store.artefacts.create(project.id, actor="system", artefact_type="problem_statement", phase_key="requirements", title="P", prefix="REQ-PRB")
    store.memory.add(project.id, "human_feedback", "for everyone", actor="human:ann", phase_key="requirements")
    store.memory.add(project.id, "human_feedback", "for personas", actor="human:ann", phase_key="requirements", artefact_id="REQ-PER-001")
    assert texts(store, project, "REQ-PER-001") == ["for everyone", "for personas"]
    assert texts(store, project, "REQ-PRB-001") == ["for everyone"]


def test_an_artefact_that_does_not_exist_yet_only_gets_phase_wide_notes(store, project):
    store.artefacts.create(project.id, actor="system", **ART)
    store.memory.add(project.id, "human_feedback", "for everyone", actor="human:ann", phase_key="requirements")
    store.memory.add(project.id, "human_feedback", "for personas", actor="human:ann", phase_key="requirements", artefact_id="REQ-PER-001")
    assert texts(store, project, None) == ["for everyone"]


def test_only_feedback_kinds_count_and_other_phases_never_do(store, project):
    store.artefacts.create(project.id, actor="system", **ART)
    store.memory.add(project.id, "note", "just a note", actor="human:ann", phase_key="requirements")
    store.memory.add(project.id, "reviewer_feedback", "reviewer says", actor="agent:r@m", phase_key="requirements")
    store.memory.add(project.id, "human_feedback", "another phase", actor="human:ann", phase_key="design")
    assert texts(store, project) == ["reviewer says"]
