from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.models import ConflictError, InvalidInput, NotFoundError

AGENT = "agent:requirements-analyst@model-sonnet"


def make(store, project, **kw):
    kw.setdefault("artefact_type", "functional_requirements")
    kw.setdefault("phase_key", "requirements")
    kw.setdefault("title", "Functional requirements")
    kw.setdefault("actor", AGENT)
    return store.artefacts.create(project.id, **kw)


def test_explicit_id_round_trip(store, project):
    a = make(store, project, artefact_id="REQ-F-012")
    assert a.id == "REQ-F-012"
    assert a.latest_version is None
    assert store.artefacts.get(project.id, "REQ-F-012") == a


@pytest.mark.parametrize("bad", ["req-f-012", "REQ-F-12", "REQ", "REQ-F-", "REQ F 012", "", "REQ-F-012 "])
def test_malformed_ids_are_rejected(store, project, bad):
    with pytest.raises(InvalidInput):
        make(store, project, artefact_id=bad)


def test_exactly_one_of_id_or_prefix(store, project):
    with pytest.raises(InvalidInput):
        make(store, project)
    with pytest.raises(InvalidInput):
        make(store, project, artefact_id="REQ-F-001", prefix="REQ-F")


def test_bad_prefix_is_rejected(store, project):
    for bad in ("req-f", "REQ-", "REQ F", ""):
        with pytest.raises(InvalidInput):
            make(store, project, prefix=bad)


def test_prefix_allocates_sequential_numbers(store, project):
    ids = [make(store, project, prefix="REQ-F").id for _ in range(3)]
    assert ids == ["REQ-F-001", "REQ-F-002", "REQ-F-003"]


def test_prefix_numbering_is_per_project(store, project):
    other = store.projects.create(name="Other", actor="system")
    make(store, project, prefix="REQ-F")
    make(store, project, prefix="REQ-F")
    assert make(store, other, prefix="REQ-F").id == "REQ-F-001"


def test_prefix_does_not_count_longer_prefixes(store, project):
    make(store, project, prefix="REQ-F")
    make(store, project, prefix="REQ-F")
    assert make(store, project, prefix="REQ").id == "REQ-001"


def test_prefix_continues_after_an_explicit_id(store, project):
    make(store, project, artefact_id="DES-UJ-007")
    assert make(store, project, prefix="DES-UJ").id == "DES-UJ-008"


def test_duplicate_explicit_id_is_refused(store, project):
    make(store, project, artefact_id="REQ-F-001")
    with pytest.raises(ConflictError):
        make(store, project, artefact_id="REQ-F-001")


def test_the_same_id_may_exist_in_two_projects(store, project):
    other = store.projects.create(name="Other", actor="system")
    make(store, project, artefact_id="REQ-F-001")
    make(store, other, artefact_id="REQ-F-001")


def test_unknown_project_and_blank_fields(store, project):
    with pytest.raises(NotFoundError):
        store.artefacts.create(
            "nope", artefact_type="t", phase_key="p", title="T", actor=AGENT, prefix="REQ-F"
        )
    for field in ("artefact_type", "phase_key", "title"):
        with pytest.raises(InvalidInput):
            make(store, project, prefix="REQ-F", **{field: "  "})


def test_versions_number_from_one(store, project):
    make(store, project, artefact_id="REQ-F-001")
    v1 = store.artefacts.add_version(project.id, "REQ-F-001", body="first", author=AGENT)
    v2 = store.artefacts.add_version(project.id, "REQ-F-001", body="second", author="human:ann")
    assert (v1.number, v2.number) == (1, 2)
    assert [v.number for v in store.artefacts.versions(project.id, "REQ-F-001")] == [1, 2]


def test_latest_version_is_tracked_and_default(store, project):
    make(store, project, artefact_id="REQ-F-001")
    store.artefacts.add_version(project.id, "REQ-F-001", body="first", author=AGENT)
    store.artefacts.add_version(project.id, "REQ-F-001", body="second", author="human:ann")
    assert store.artefacts.get(project.id, "REQ-F-001").latest_version == 2
    assert store.artefacts.get_version(project.id, "REQ-F-001").body == "second"
    assert store.artefacts.get_version(project.id, "REQ-F-001", 1).body == "first"


def test_missing_artefact_or_version(store, project):
    with pytest.raises(NotFoundError):
        store.artefacts.get(project.id, "REQ-F-001")
    with pytest.raises(NotFoundError):
        store.artefacts.add_version(project.id, "REQ-F-001", body="x", author=AGENT)
    with pytest.raises(NotFoundError):
        store.artefacts.versions(project.id, "REQ-F-001")
    make(store, project, artefact_id="REQ-F-001")
    with pytest.raises(NotFoundError):
        store.artefacts.get_version(project.id, "REQ-F-001")  # no versions yet
    with pytest.raises(NotFoundError):
        store.artefacts.get_version(project.id, "REQ-F-001", 5)


def test_author_must_be_a_person_or_an_agent(store, project):
    make(store, project, artefact_id="REQ-F-001")
    for author in ("system", "ann", "agent:no-model", ""):
        with pytest.raises(InvalidInput):
            store.artefacts.add_version(project.id, "REQ-F-001", body="x", author=author)
    assert store.artefacts.get(project.id, "REQ-F-001").latest_version is None


def test_blank_body_is_refused(store, project):
    make(store, project, artefact_id="REQ-F-001")
    for body in ("", "   ", None):
        with pytest.raises(InvalidInput):
            store.artefacts.add_version(project.id, "REQ-F-001", body=body, author=AGENT)


def test_source_chunks_round_trip_in_order(store, project):
    make(store, project, artefact_id="REQ-F-001")
    v = store.artefacts.add_version(
        project.id, "REQ-F-001", body="x", author=AGENT, source_chunks=["doc1#3", "doc2#1"]
    )
    assert v.source_chunks == ("doc1#3", "doc2#1")
    assert store.artefacts.get_version(project.id, "REQ-F-001", 1).source_chunks == ("doc1#3", "doc2#1")
    with pytest.raises(InvalidInput):
        store.artefacts.add_version(project.id, "REQ-F-001", body="y", author=AGENT, source_chunks=[""])


def test_review_findings_change_only_the_findings(store, project):
    make(store, project, artefact_id="REQ-F-001")
    before = store.artefacts.add_version(project.id, "REQ-F-001", body="x", author=AGENT)
    assert before.review_findings is None
    findings = {"verdict": "fail", "items": [{"severity": "high", "text": "no NFR for peak load"}]}
    after = store.artefacts.set_review_findings(
        project.id, "REQ-F-001", 1, findings, actor="agent:reviewer@model-openai"
    )
    assert after.review_findings == findings
    assert (after.body, after.author, after.number, after.source_chunks, after.created_at) == (
        before.body, before.author, before.number, before.source_chunks, before.created_at
    )
    with pytest.raises(NotFoundError):
        store.artefacts.set_review_findings(project.id, "REQ-F-001", 9, findings, actor="system")


def test_the_database_itself_refuses_to_change_or_delete_a_version(store, project):
    make(store, project, artefact_id="REQ-F-001")
    store.artefacts.add_version(project.id, "REQ-F-001", body="original", author=AGENT)
    for column, value in (
        ("body", "tampered"),
        ("author", "human:mallory"),
        ("number", 7),
        ("source_chunks", '["x"]'),
        ("created_at", "yesterday"),
    ):
        with pytest.raises(sqlite3.DatabaseError, match="immutable"):
            with store.db.write() as conn:
                conn.execute(f"UPDATE artefact_versions SET {column} = ?", (value,))
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        with store.db.write() as conn:
            conn.execute("DELETE FROM artefact_versions")
    assert store.artefacts.get_version(project.id, "REQ-F-001", 1).body == "original"


def test_twenty_concurrent_creates_get_unique_ids(store, project):
    def create(_):
        return store.artefacts.create(
            project.id, artefact_type="t", phase_key="p", title="T", actor=AGENT, prefix="REQ-F"
        ).id

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(create, range(20)))
    assert len(set(ids)) == 20
    assert sorted(ids) == [f"REQ-F-{n:03d}" for n in range(1, 21)]


def test_ten_concurrent_versions_get_unique_numbers(store, project):
    make(store, project, artefact_id="REQ-F-001")

    def add(n):
        return store.artefacts.add_version(project.id, "REQ-F-001", body=f"v{n}", author=AGENT).number

    with ThreadPoolExecutor(max_workers=8) as pool:
        numbers = list(pool.map(add, range(10)))
    assert sorted(numbers) == list(range(1, 11))
    assert len(store.artefacts.versions(project.id, "REQ-F-001")) == 10


def test_listing_filters_and_order(store, project):
    make(store, project, artefact_id="REQ-F-001", phase_key="requirements", artefact_type="functional")
    make(store, project, artefact_id="DES-UJ-001", phase_key="design", artefact_type="user_journey")
    make(store, project, artefact_id="REQ-F-002", phase_key="requirements", artefact_type="functional")
    ids = lambda items: [a.id for a in items]
    assert ids(store.artefacts.list(project.id)) == ["REQ-F-001", "DES-UJ-001", "REQ-F-002"]
    assert ids(store.artefacts.list(project.id, phase_key="requirements")) == ["REQ-F-001", "REQ-F-002"]
    assert ids(store.artefacts.list(project.id, artefact_type="user_journey")) == ["DES-UJ-001"]
    assert ids(store.artefacts.list(project.id, phase_key="design", artefact_type="functional")) == []


def test_the_author_is_the_audit_actor(store, project):
    make(store, project, artefact_id="REQ-F-001", actor="system")
    store.artefacts.add_version(project.id, "REQ-F-001", body="x", author=AGENT)
    store.artefacts.add_version(project.id, "REQ-F-001", body="y", author="human:ann")
    events = [e for e in store.audit.list(project.id) if e.action == "artefact.version_added"]
    assert [e.actor for e in events] == [AGENT, "human:ann"]
    assert [e.detail["number"] for e in events] == [1, 2]
