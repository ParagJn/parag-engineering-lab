from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.db import MIGRATIONS, SCHEMA_V1, Database, split_statements
from app.repos import Store


def columns(db: Database, table: str) -> set[str]:
    with db.read() as conn:
        return {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}


def test_a_fresh_database_is_at_the_latest_version_and_has_the_v2_columns(tmp_path):
    db = Database(tmp_path / "x.db")
    assert db.migrate() == len(MIGRATIONS) >= 2
    assert {"call_id", "attempt"} <= columns(db, "traces")


def test_a_v1_database_with_data_migrates_and_keeps_its_rows(tmp_path):
    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    raw.executescript(SCHEMA_V1)
    raw.execute("PRAGMA user_version = 1")
    raw.execute(
        "INSERT INTO projects (id, name, mode, created_at, updated_at) VALUES ('p1', 'Old', 'replay', 't', 't')"
    )
    raw.execute(
        "INSERT INTO traces (project_id, agent, slot, requested_model, served_model, status, created_at)"
        " VALUES ('p1', 'a', 's', 'm', 'm', 'ok', 't')"
    )
    raw.commit()
    raw.close()

    db = Database(path)
    assert db.migrate() == len(MIGRATIONS)
    with db.read() as conn:
        assert conn.execute("SELECT name FROM projects").fetchone()["name"] == "Old"
        old = conn.execute("SELECT call_id, attempt FROM traces").fetchone()
    assert old["call_id"] is None and old["attempt"] == 1


def test_migrating_twice_changes_nothing(tmp_path):
    db = Database(tmp_path / "x.db")
    db.migrate()
    before = columns(db, "traces")
    assert db.migrate() == len(MIGRATIONS)
    assert columns(db, "traces") == before


def test_concurrent_migrations_on_a_fresh_file_all_succeed(tmp_path):
    """Two processes starting together must not apply ALTER TABLE twice."""
    path = tmp_path / "race.db"

    def start(_):
        return Database(path).migrate()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(start, range(8)))
    assert results == [len(MIGRATIONS)] * 8
    cols = sorted(columns(Database(path), "traces"))
    assert cols.count("call_id") == 1 and cols.count("attempt") == 1


class ScriptedConn:
    """Stands in for a connection and plays back a fixed list of outcomes for the WAL pragma."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def execute(self, sql):
        self.calls += 1
        outcome = self.outcomes.pop(0) if self.outcomes else "wal"
        if isinstance(outcome, Exception):
            raise outcome

        class Row:
            def fetchone(self_inner):
                return (outcome,)

        return Row()


def test_enabling_wal_retries_when_the_database_is_briefly_locked(monkeypatch):
    """The deterministic version of the race that used to fail about 1 run in 20."""
    monkeypatch.setattr(Database, "WAL_WAIT_SECONDS", 0)
    conn = ScriptedConn([sqlite3.OperationalError("database is locked")] * 3 + ["wal"])
    Database._enable_wal(conn)
    assert conn.calls == 4


def test_enabling_wal_gives_up_with_the_real_error_if_it_stays_locked(monkeypatch):
    monkeypatch.setattr(Database, "WAL_WAIT_SECONDS", 0)
    conn = ScriptedConn([sqlite3.OperationalError("database is locked")] * 100)
    with pytest.raises(sqlite3.OperationalError, match="locked"):
        Database._enable_wal(conn)
    assert conn.calls == Database.WAL_ATTEMPTS


def test_enabling_wal_does_not_hide_an_unrelated_error(monkeypatch):
    monkeypatch.setattr(Database, "WAL_WAIT_SECONDS", 0)
    conn = ScriptedConn([sqlite3.OperationalError("disk I/O error")])
    with pytest.raises(sqlite3.OperationalError, match="disk I/O"):
        Database._enable_wal(conn)
    assert conn.calls == 1  # not retried: only 'locked' and 'busy' are worth waiting for


def test_a_filesystem_that_cannot_do_wal_does_not_stop_the_app(monkeypatch):
    monkeypatch.setattr(Database, "WAL_WAIT_SECONDS", 0)
    conn = ScriptedConn(["delete"] * 100)  # SQLite answers with the mode it actually used
    Database._enable_wal(conn)  # returns instead of raising
    assert conn.calls == Database.WAL_ATTEMPTS


def test_many_rounds_of_concurrent_first_start_never_fail(tmp_path):
    """Statistical backstop for the race above: 40 fresh files, 8 threads each. Failed ~5% per round before."""
    for round_number in range(40):
        path = tmp_path / f"round{round_number}.db"

        def start(_):
            return Database(path).migrate()

        with ThreadPoolExecutor(max_workers=8) as pool:
            assert list(pool.map(start, range(8))) == [len(MIGRATIONS)] * 8


def test_a_failing_migration_step_rolls_back_and_leaves_the_version_alone(tmp_path, monkeypatch):
    db = Database(tmp_path / "x.db")
    db.migrate()  # now at the latest
    import app.db as dbmod

    monkeypatch.setattr(dbmod, "MIGRATIONS", [*MIGRATIONS, "CREATE TABLE ok_table (a); ALTER TABLE nope ADD COLUMN b;"])
    try:
        db.migrate()
    except sqlite3.OperationalError:
        pass
    assert db.schema_version == len(MIGRATIONS)
    with db.read() as conn:
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'ok_table'").fetchone() is None


def test_split_statements_keeps_trigger_bodies_whole():
    parts = split_statements(
        "CREATE TABLE a (x);\nCREATE TRIGGER t BEFORE UPDATE ON a\nBEGIN SELECT RAISE(ABORT, 'no'); END;\nSELECT 1;\n"
    )
    assert len(parts) == 3
    assert parts[1].startswith("CREATE TRIGGER") and parts[1].endswith("END;")


def test_split_statements_handles_several_statements_on_one_line_and_comments():
    parts = split_statements("CREATE TABLE a (x); CREATE TABLE b (y);\n-- a note; with a semicolon\nSELECT 1;\n-- trailing\n")
    assert len(parts) == 3
    assert parts[0] == "CREATE TABLE a (x);" and parts[1] == "CREATE TABLE b (y);"


def test_split_statements_refuses_an_unfinished_statement():
    import pytest

    with pytest.raises(ValueError):
        split_statements("CREATE TABLE a (x);\nSELECT 1")


def test_every_shipped_migration_splits_into_statements_that_sqlite_accepts(tmp_path):
    raw = sqlite3.connect(tmp_path / "x.db")
    for script in MIGRATIONS:
        for statement in split_statements(script):
            raw.execute(statement)
    raw.close()


def test_the_traces_repo_stores_call_id_and_attempt(tmp_path):
    store = Store.open(tmp_path / "x.db")
    t = store.traces.record(
        agent="a", slot="sonnet", requested_model="m", served_model="m", status="ok", call_id="abc", attempt=3
    )
    assert (t.call_id, t.attempt) == ("abc", 3)
    assert store.traces.record(
        agent="a", slot="sonnet", requested_model="m", served_model="m", status="ok"
    ).attempt == 1
