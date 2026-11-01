"""Approved artefacts becoming searchable context, and leaving it again."""
from __future__ import annotations

import logging

import pytest

from app.llm.routing import Routing
from app.models import InvalidInput, NotFoundError
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine

PERSON = "human:ann"
CHARTER_V1 = "# Project charter\n\nThe system must prevent double bookings and respect office hours."
CHARTER_V2 = "# Project charter\n\nThe system must refuse overlapping reservations of the same room."


@pytest.fixture(scope="module")
def catalogue():
    return load_catalogue(Routing.load().roles.keys())


@pytest.fixture
def engine(catalogue, store):
    return WorkflowEngine(catalogue, store)


@pytest.fixture
def setup_phase(engine, store, project):
    """Setup running, with a charter that has one version. Returns the artefact."""
    engine.open_project(project.id)
    engine.start(project.id, "setup", actor="system")
    charter = store.artefacts.create(project.id, artefact_type="project_charter", phase_key="setup",
                                     title="Project charter", actor="system", prefix="SET-CHR")
    store.artefacts.add_version(project.id, charter.id, body=CHARTER_V1, author=PERSON)
    return charter


def found(store, project, text: str) -> list[str]:
    return [h.source_id for h in store.context.search(project.id, text, kinds=["artefact"])]


def approve(engine, project, key="setup"):
    engine.finish(project.id, key, actor="system")
    return engine.approve(project.id, key, actor=PERSON)


# ---- approval makes content searchable ----------------------------------------------------------------------------------

def test_nothing_is_searchable_until_the_phase_is_approved(engine, store, project, setup_phase):
    assert found(store, project, "double bookings") == []
    engine.finish(project.id, "setup", actor="system")
    assert found(store, project, "double bookings") == []  # awaiting review is not approved either


def test_approval_indexes_the_latest_version_with_a_versioned_source_id(engine, store, project, setup_phase):
    approve(engine, project)
    hit = store.context.search(project.id, "double bookings")[0]
    assert hit.source_id == "SET-CHR-001@v1#1" and hit.kind == "artefact"
    assert (hit.phase_key, hit.artefact_id, hit.title) == ("setup", "SET-CHR-001", "Project charter (v1)")
    assert hit.citation == "[SET-CHR-001@v1#1] Project charter (v1) > Project charter"
    assert store.context.stats(project.id)["artefact_sources"] == 1


def test_the_audit_log_records_what_was_indexed(engine, store, project, setup_phase):
    approve(engine, project)
    event = [e for e in store.audit.list(project.id) if e.action == "context.artefact_indexed"][0]
    assert event.target_id == "SET-CHR-001" and event.detail == {"version": 1, "chunks": 1}


def test_only_the_latest_version_is_indexed_when_there_are_several(engine, store, project, setup_phase):
    store.artefacts.add_version(project.id, setup_phase.id, body=CHARTER_V2, author=PERSON)
    approve(engine, project)
    assert found(store, project, "overlapping reservations") == ["SET-CHR-001@v2#1"]
    assert found(store, project, "double bookings") == []


def test_artefacts_without_content_are_skipped_and_other_phases_are_untouched(engine, store, project, setup_phase):
    store.artefacts.create(project.id, artefact_type="x", phase_key="setup", title="Empty one", actor="system", artefact_id="SET-EMP-001")
    other = store.artefacts.create(project.id, artefact_type="y", phase_key="requirements", title="Other phase", actor="system", prefix="REQ-PER")
    store.artefacts.add_version(project.id, other.id, body="Requirements text about zebras.", author=PERSON)
    approve(engine, project)
    assert found(store, project, "zebras") == []  # a different phase, not approved
    assert store.context.stats(project.id)["artefact_sources"] == 1


# ---- reingest_phase directly ------------------------------------------------------------------------------------------

def test_reingest_refuses_a_phase_that_is_not_approved(store, project, engine, setup_phase):
    with pytest.raises(InvalidInput, match="not approved"):
        store.context.reingest_phase(project.id, "setup")
    with pytest.raises(InvalidInput, match="not approved"):
        store.context.reingest_phase(project.id, "design")  # no such row at all
    with pytest.raises(NotFoundError):
        store.context.reingest_phase("nope", "setup")


def test_reingesting_is_idempotent(engine, store, project, setup_phase):
    approve(engine, project)
    again = store.context.reingest_phase(project.id, "setup")
    assert (again.indexed, again.skipped, again.chunks, again.failed) == (0, 1, 0, ())
    assert store.context.stats(project.id)["chunks"] == 1
    assert len([e for e in store.audit.list(project.id) if e.action == "context.artefact_indexed"]) == 1


def test_a_new_version_replaces_the_old_one_in_the_results_and_the_old_citation_goes_dead(engine, store, project, setup_phase):
    approve(engine, project)
    old_id = store.context.search(project.id, "double bookings")[0].source_id
    store.artefacts.add_version(project.id, setup_phase.id, body=CHARTER_V2, author=PERSON)
    result = store.context.reingest_phase(project.id, "setup")
    assert (result.indexed, result.skipped) == (1, 0)
    assert found(store, project, "double bookings") == [] and found(store, project, "overlapping reservations") == ["SET-CHR-001@v2#1"]
    assert store.context.resolve(project.id, old_id) is None  # does not silently resolve to the new text
    assert store.context.resolve(project.id, "SET-CHR-001@v2#1").text.endswith("same room.")


def test_every_chunk_of_a_multi_section_artefact_is_cited_separately(engine, store, project):
    engine.open_project(project.id)
    engine.start(project.id, "setup", actor="system")
    art = store.artefacts.create(project.id, artefact_type="project_charter", phase_key="setup", title="Charter", actor="system", prefix="SET-CHR")
    store.artefacts.add_version(project.id, art.id, body="# Scope\n\nBooking rooms.\n\n# Risks\n\nDouble bookings are a risk.", author=PERSON)
    approve(engine, project)
    assert sorted(found(store, project, "scope risks booking")) == ["SET-CHR-001@v1#1", "SET-CHR-001@v1#2"]


def test_an_artefact_that_cannot_be_indexed_is_reported_and_the_others_still_are(engine, store, project, setup_phase, monkeypatch):
    second = store.artefacts.create(project.id, artefact_type="z", phase_key="setup", title="Second", actor="system", artefact_id="SET-SEC-001")
    store.artefacts.add_version(project.id, second.id, body="Second artefact about giraffes.", author=PERSON)
    approve(engine, project)
    store.context.unindex_phase(project.id, "setup")

    real = store.context._index_artefact

    def flaky(project_id, art, actor):
        if art["id"] == "SET-CHR-001":
            raise RuntimeError("disk on fire /secret/path")
        return real(project_id, art, actor)

    monkeypatch.setattr(store.context, "_index_artefact", flaky)
    result = store.context.reingest_phase(project.id, "setup")
    assert result.indexed == 1 and result.failed == (("SET-CHR-001", "RuntimeError"),)  # type name only, never the message
    assert found(store, project, "giraffes") == ["SET-SEC-001@v1#1"] and found(store, project, "double") == []


def test_an_artefact_with_unreadable_text_is_reported_in_plain_words(engine, store, project, setup_phase):
    store.artefacts.add_version(project.id, setup_phase.id, body="​​​", author=PERSON)
    approve(engine, project)  # the approval stands even though nothing could be indexed
    assert store.phases.get(project.id, "setup").status == "approved"
    result = store.context.reingest_phase(project.id, "setup")
    assert result.indexed == 0 and result.failed and "no readable text" in result.failed[0][1]


# ---- reopening ----------------------------------------------------------------------------------------------------------

def test_reopening_removes_the_phases_artefacts_from_the_index(engine, store, project, setup_phase):
    approve(engine, project)
    assert found(store, project, "double bookings")
    engine.reopen(project.id, "setup", actor=PERSON, reason="the brief changed")
    assert found(store, project, "double bookings") == [] and store.context.stats(project.id)["artefact_sources"] == 0
    assert "context.phase_unindexed" in [e.action for e in store.audit.list(project.id)]


def test_reapproval_restores_the_content_at_its_current_version(engine, store, project, setup_phase):
    approve(engine, project)
    engine.reopen(project.id, "setup", actor=PERSON, reason="changed")
    store.artefacts.add_version(project.id, setup_phase.id, body=CHARTER_V2, author=PERSON)
    approve(engine, project)
    assert found(store, project, "overlapping reservations") == ["SET-CHR-001@v2#1"] and found(store, project, "double bookings") == []


def test_unindexing_a_phase_touches_only_that_phase_and_only_artefacts(engine, store, project, setup_phase):
    store.memory.add(project.id, "note", "Memory about giraffes.", actor=PERSON, phase_key="setup")
    approve(engine, project)
    assert store.context.unindex_phase(project.id, "setup") == 1
    assert store.context.unindex_phase(project.id, "setup") == 0  # nothing left; nothing more to remove
    assert [h.kind for h in store.context.search(project.id, "giraffes")] == ["memory"]  # memory survives


# ---- an indexing failure never undoes a human decision ------------------------------------------------------------------

def test_an_indexing_failure_leaves_the_approval_standing_and_is_audited(engine, store, project, setup_phase, monkeypatch, caplog):
    def broken(*args, **kwargs):
        raise RuntimeError("the index is on fire")

    monkeypatch.setattr(store.context, "reingest_phase", broken)
    with caplog.at_level(logging.WARNING):
        run = approve(engine, project)
    assert run.status == "approved" and run.decided_by == PERSON
    assert store.phases.get(project.id, "setup").status == "approved"
    event = [e for e in store.audit.list(project.id) if e.action == "context.index_failed"][0]
    assert event.actor == "system" and event.target_id == "setup"
    assert event.detail == {"problem": "indexing failed", "error": "RuntimeError"}
    assert "on fire" not in str(event.detail)  # the exception text is not copied into the audit log
    assert any("indexing approved phase" in r.message for r in caplog.records)


def test_a_partial_failure_is_audited_with_artefact_ids_and_reasons(engine, store, project, setup_phase, monkeypatch):
    monkeypatch.setattr(store.context, "_index_artefact", lambda *a, **k: (_ for _ in ()).throw(InvalidInput("no readable text")))
    approve(engine, project)
    event = [e for e in store.audit.list(project.id) if e.action == "context.index_failed"][0]
    assert event.detail == {"problem": "1 artefact(s) could not be indexed", "failed": [{"artefact": "SET-CHR-001", "reason": "no readable text"}]}


def test_even_a_failing_audit_write_does_not_undo_an_approval(engine, store, project, setup_phase, monkeypatch):
    monkeypatch.setattr(store.context, "reingest_phase", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(store.audit, "append", lambda **k: (_ for _ in ()).throw(RuntimeError("audit down")))
    assert approve(engine, project).status == "approved"


def test_a_failure_while_unindexing_after_a_reopen_leaves_the_reopen_standing(engine, store, project, setup_phase, monkeypatch):
    approve(engine, project)
    monkeypatch.setattr(store.context, "unindex_phase", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")))
    run = engine.reopen(project.id, "setup", actor=PERSON, reason="changed")
    assert run.status == "running"
    assert [e.detail for e in store.audit.list(project.id) if e.action == "context.index_failed"] == [
        {"problem": "could not remove the phase from the index"}
    ]


def test_a_refused_approval_indexes_nothing(engine, store, project):
    engine.open_project(project.id)
    engine.start(project.id, "setup", actor="system")
    engine.finish(project.id, "setup", actor="system")
    with pytest.raises(Exception):
        engine.approve(project.id, "setup", actor=PERSON)  # the required charter has no content
    assert store.context.stats(project.id)["chunks"] == 0
    assert not [e for e in store.audit.list(project.id) if e.action.startswith("context.")]


def test_projects_are_isolated_when_indexing_artefacts(engine, store, project, setup_phase):
    other = store.projects.create(name="Other", actor="system")
    approve(engine, project)
    assert store.context.search(other.id, "double bookings") == []
