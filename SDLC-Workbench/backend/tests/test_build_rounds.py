"""S17b-2: the permanent record of the write -> test -> fix loop. Append-only, bounded, and never holding file contents or a full output."""
from __future__ import annotations

import sqlite3

import pytest

from app.db import MIGRATIONS, SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4, SCHEMA_V5, SCHEMA_V6, Database, split_statements
from app.models import InvalidInput, NotFoundError
from app.repos import MAX_FAILURE_TEXT, MAX_ROUND_FAILURES, ROUND_OUTCOMES, Store


@pytest.fixture
def rounds(store, project):
    return store.build_rounds, project


def failure(n: int = 1, message: str = "assert 1 == 2") -> dict:
    return {"test": f"tests/test_a.py::test_{n}", "kind": "failed", "message": message}


# ---- appending and reading ---------------------------------------------------------------------------------------------------------

def test_a_round_is_saved_with_everything_it_was_given(rounds):
    repo, project = rounds
    saved = repo.append(project.id, "loop-1", 1, artefact="backend_code", outcome="failed", version=2, run_id="run-1", passed=3, failed=2, errors=1, skipped=4,
                        fingerprint="abc123", failures=[failure(1), failure(2)], seconds=1.5)
    assert (saved.project_id, saved.loop_id, saved.round, saved.artefact, saved.version, saved.run_id) == (project.id, "loop-1", 1, "backend_code", 2, "run-1")
    assert (saved.outcome, saved.passed, saved.failed, saved.errors, saved.skipped, saved.fingerprint, saved.seconds) == ("failed", 3, 2, 1, 4, "abc123", 1.5)
    assert [f["test"] for f in saved.failures] == ["tests/test_a.py::test_1", "tests/test_a.py::test_2"] and saved.at and saved.id >= 1


def test_the_optional_things_may_be_left_out(rounds):
    repo, project = rounds
    saved = repo.append(project.id, "loop-1", 1, artefact="", outcome="passed", passed=5)
    assert (saved.version, saved.run_id, saved.failed, saved.failures, saved.fingerprint, saved.seconds) == (None, None, 0, (), "", 0.0)


def test_rounds_come_back_oldest_first_and_can_be_limited_to_one_loop(rounds):
    repo, project = rounds
    repo.append(project.id, "loop-1", 1, artefact="a", outcome="failed")
    repo.append(project.id, "loop-2", 1, artefact="b", outcome="failed")
    repo.append(project.id, "loop-1", 2, artefact="a", outcome="passed")
    assert [(r.loop_id, r.round) for r in repo.list(project.id)] == [("loop-1", 1), ("loop-2", 1), ("loop-1", 2)]
    assert [(r.loop_id, r.round) for r in repo.list(project.id, loop_id="loop-1")] == [("loop-1", 1), ("loop-1", 2)]
    assert len(repo.list(project.id, limit=2)) == 2


def test_one_projects_rounds_never_show_in_another(store, rounds):
    repo, project = rounds
    other = store.projects.create(name="Other", actor="human:tester")
    repo.append(project.id, "loop-1", 1, artefact="a", outcome="failed")
    assert repo.list(other.id) == []


def test_an_unknown_project_is_refused_on_write_and_on_read(rounds):
    repo, _ = rounds
    with pytest.raises(NotFoundError):
        repo.append("nosuch", "loop-1", 1, artefact="a", outcome="failed")
    with pytest.raises(NotFoundError):
        repo.list("nosuch")


# ---- bounds ------------------------------------------------------------------------------------------------------------------------

def test_only_the_first_ten_failures_are_kept(rounds):
    repo, project = rounds
    saved = repo.append(project.id, "loop-1", 1, artefact="a", outcome="failed", failures=[failure(n) for n in range(25)])
    assert MAX_ROUND_FAILURES == 10 and len(saved.failures) == 10 and saved.failures[-1]["test"].endswith("test_9")


def test_a_failure_message_is_cut_at_four_hundred_characters(rounds):
    repo, project = rounds
    saved = repo.append(project.id, "loop-1", 1, artefact="a", outcome="failed", failures=[failure(1, "x" * 900)])
    assert MAX_FAILURE_TEXT == 400 and len(saved.failures[0]["message"]) == 400


def test_a_very_long_test_name_is_cut_too(rounds):
    repo, project = rounds
    saved = repo.append(project.id, "loop-1", 1, artefact="a", outcome="failed", failures=[{"test": "t" * 900, "kind": "failed", "message": "m"}])
    assert len(saved.failures[0]["test"]) == 400


def test_a_kind_is_cut_at_forty_characters(rounds):
    repo, project = rounds
    saved = repo.append(project.id, "loop-1", 1, artefact="a", outcome="failed", failures=[{"test": "t", "kind": "k" * 90, "message": "m"}])
    assert len(saved.failures[0]["kind"]) == 40


def test_a_failure_keeps_only_the_three_fields_so_nothing_else_can_be_smuggled_in(rounds):
    repo, project = rounds
    saved = repo.append(project.id, "loop-1", 1, artefact="a", outcome="failed", failures=[{**failure(1), "output": "FULL OUTPUT", "text": "FILE CONTENTS"}])
    assert set(saved.failures[0]) == {"test", "kind", "message"} and "FULL OUTPUT" not in repr(saved) and "FILE CONTENTS" not in repr(saved)


def test_the_fingerprint_is_cut_to_two_hundred_characters(rounds):
    repo, project = rounds
    assert len(repo.append(project.id, "loop-1", 1, artefact="a", outcome="failed", fingerprint="f" * 500).fingerprint) == 200


# ---- what is refused -----------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kwargs, message", [
    ({"round_": 0}, "round must be"), ({"round_": -1}, "round must be"), ({"round_": True}, "round must be"), ({"round_": "1"}, "round must be"),
    ({"outcome": "great"}, "outcome must be one of"), ({"outcome": ""}, "outcome must be one of"),
    ({"passed": -1}, "passed must be"), ({"failed": -1}, "failed must be"), ({"errors": -1}, "errors must be"), ({"skipped": -1}, "skipped must be"),
    ({"passed": True}, "passed must be"), ({"version": -1}, "version must be"), ({"seconds": -0.1}, "seconds must be"), ({"seconds": "1"}, "seconds must be"),
    ({"loop_id": ""}, "loop_id"),
])
def test_a_bad_value_is_refused_with_a_sentence(rounds, kwargs, message):
    repo, project = rounds
    args = {"loop_id": "loop-1", "round_": 1, "artefact": "a", "outcome": "failed", **kwargs}
    loop_id, round_ = args.pop("loop_id"), args.pop("round_")
    with pytest.raises(InvalidInput, match=message):
        repo.append(project.id, loop_id, round_, **args)
    assert repo.list(project.id) == []


def test_every_outcome_the_loop_can_report_is_accepted(rounds):
    repo, project = rounds
    for n, outcome in enumerate(ROUND_OUTCOMES, start=1):
        assert repo.append(project.id, "loop-1", n, artefact="a", outcome=outcome).outcome == outcome


# ---- append-only -----------------------------------------------------------------------------------------------------------------------

def test_a_round_cannot_be_changed_or_deleted_by_the_database(store, rounds):
    repo, project = rounds
    repo.append(project.id, "loop-1", 1, artefact="a", outcome="failed", failed=2)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        with store.db.write() as conn:
            conn.execute("UPDATE build_rounds SET failed = 0")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        with store.db.write() as conn:
            conn.execute("DELETE FROM build_rounds")
    assert repo.list(project.id)[0].failed == 2


def test_the_database_itself_refuses_a_negative_count_or_a_round_of_zero(store, rounds):
    repo, project = rounds
    for column, value in (("passed", -1), ("failed", -1), ("errors", -1), ("skipped", -1), ("round", 0)):
        row = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0, "round": 1, column: value}
        with pytest.raises(sqlite3.IntegrityError):
            with store.db.write() as conn:
                conn.execute("INSERT INTO build_rounds (project_id, loop_id, round, artefact, outcome, passed, failed, errors, skipped, fingerprint, failures, at)"
                             " VALUES (?, 'l', ?, 'a', 'failed', ?, ?, ?, ?, '', '[]', 't')", (project.id, row["round"], row["passed"], row["failed"], row["errors"], row["skipped"]))


# ---- the migration -----------------------------------------------------------------------------------------------------------------------

def test_a_v6_database_upgrades_to_v7_keeping_its_data(tmp_path):
    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    for script in (SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4, SCHEMA_V5, SCHEMA_V6):
        for statement in split_statements(script):
            raw.execute(statement)
    raw.execute("PRAGMA user_version = 6")
    raw.execute("INSERT INTO projects (id, name, mode, created_at, updated_at) VALUES ('p1', 'Old', 'replay', 't', 't')")
    raw.commit(); raw.close()
    assert len(MIGRATIONS) == 10 and Database(path).migrate() == 10
    store = Store.open(path)
    assert [p.name for p in store.projects.list()] == ["Old"] and store.build_rounds.list("p1") == []
    store.build_rounds.append("p1", "loop-1", 1, artefact="a", outcome="passed", passed=1)
    assert len(store.build_rounds.list("p1")) == 1
