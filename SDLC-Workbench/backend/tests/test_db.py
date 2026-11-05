from __future__ import annotations

import sqlite3

import pytest

from app.db import MIGRATIONS, Database, SchemaTooNewError

TABLES = {
    "projects", "phase_runs", "artefacts", "artefact_versions",
    "links", "traces", "audit", "memory",
    "context_documents", "context_chunks",  # S06
    "runs", "run_events",  # S09
    "build_rounds",  # S17b
    "verify_runs", "verify_matches",  # S20b
    "deploy_checks",  # S21c
    "users", "user_roles", "phase_approvers",  # S23a
}


def table_names(db: Database) -> set[str]:
    with db.read() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    # The full-text index is one virtual table plus several shadow tables SQLite manages itself.
    return {r["name"] for r in rows if not r["name"].startswith("context_fts")}


def test_migrate_creates_every_table(tmp_path):
    db = Database(tmp_path / "x.db")
    assert db.migrate() == len(MIGRATIONS)
    assert table_names(db) == TABLES
    assert db.schema_version == len(MIGRATIONS)


def test_migrate_is_idempotent_and_keeps_data(tmp_path):
    db = Database(tmp_path / "x.db")
    db.migrate()
    with db.write() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, mode, created_at, updated_at)"
            " VALUES ('p1', 'Keep me', 'replay', 't', 't')"
        )
    assert db.migrate() == len(MIGRATIONS)
    assert db.migrate() == len(MIGRATIONS)
    with db.read() as conn:
        assert conn.execute("SELECT name FROM projects").fetchone()["name"] == "Keep me"


def test_a_database_newer_than_the_code_is_refused(tmp_path):
    path = tmp_path / "future.db"
    raw = sqlite3.connect(path)
    raw.execute(f"PRAGMA user_version = {len(MIGRATIONS) + 1}")
    raw.close()
    with pytest.raises(SchemaTooNewError):
        Database(path).migrate()


def test_foreign_keys_are_on_for_every_connection(tmp_path):
    db = Database(tmp_path / "x.db")
    db.migrate()
    for opener in (db.read, db.write):
        with opener() as conn:
            assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_wal_mode_is_set_and_persists(tmp_path):
    db = Database(tmp_path / "x.db")
    db.migrate()
    with db.read() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_a_failed_write_rolls_back(tmp_path):
    db = Database(tmp_path / "x.db")
    db.migrate()
    with pytest.raises(RuntimeError):
        with db.write() as conn:
            conn.execute(
                "INSERT INTO projects (id, name, mode, created_at, updated_at)"
                " VALUES ('p1', 'Gone', 'replay', 't', 't')"
            )
            raise RuntimeError("boom")
    with db.read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0


def test_parent_folder_is_created(tmp_path):
    path = tmp_path / "a" / "b" / "x.db"
    Database(path).migrate()
    assert path.exists()


# ---- the database enforces its own rules, whatever the Python layer does ----

def test_children_reject_an_unknown_project(tmp_path):
    db = Database(tmp_path / "x.db")
    db.migrate()
    inserts = [
        "INSERT INTO phase_runs (project_id, phase_key, status, updated_at) VALUES ('nope', 'req', 'running', 't')",
        "INSERT INTO artefacts (project_id, id, type, phase_key, title, created_at)"
        " VALUES ('nope', 'REQ-001', 't', 'p', 'T', 't')",
        "INSERT INTO links (project_id, from_id, to_id, kind, created_at)"
        " VALUES ('nope', 'REQ-001', 'DES-001', 'derives', 't')",
        "INSERT INTO memory (project_id, kind, text, created_at) VALUES ('nope', 'note', 'x', 't')",
    ]
    for sql in inserts:
        with pytest.raises(sqlite3.IntegrityError):
            with db.write() as conn:
                conn.execute(sql)


def test_database_rejects_bad_enum_values(tmp_path):
    db = Database(tmp_path / "x.db")
    db.migrate()
    with db.write() as conn:
        conn.execute(
            "INSERT INTO projects (id, name, mode, created_at, updated_at)"
            " VALUES ('p1', 'N', 'replay', 't', 't')"
        )
    bad = [
        "INSERT INTO projects (id, name, mode, created_at, updated_at) VALUES ('p2', 'N', 'turbo', 't', 't')",
        "INSERT INTO projects (id, name, mode, created_at, updated_at) VALUES ('p3', '  ', 'live', 't', 't')",
        "INSERT INTO phase_runs (project_id, phase_key, status, updated_at) VALUES ('p1', 'a', 'flying', 't')",
        "INSERT INTO links (project_id, from_id, to_id, kind, created_at)"
        " VALUES ('p1', 'REQ-001', 'DES-001', 'friends', 't')",
        "INSERT INTO links (project_id, from_id, to_id, kind, created_at)"
        " VALUES ('p1', 'REQ-001', 'REQ-001', 'derives', 't')",
        "INSERT INTO traces (agent, slot, requested_model, served_model, status, created_at)"
        " VALUES ('a', 's', 'm', 'm', 'maybe', 't')",
        "INSERT INTO traces (agent, slot, requested_model, served_model, status, cost_usd, created_at)"
        " VALUES ('a', 's', 'm', 'm', 'ok', -1, 't')",
        "INSERT INTO memory (project_id, kind, text, created_at) VALUES ('p1', 'gossip', 'x', 't')",
    ]
    for sql in bad:
        with pytest.raises(sqlite3.IntegrityError):
            with db.write() as conn:
                conn.execute(sql)
