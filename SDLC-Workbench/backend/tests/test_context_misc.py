"""Migration to v3, the status block, settings, and the offline demo script."""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import scripts.context_demo as demo
from app.config import Settings
from app.context.types import Limits
from app.db import MIGRATIONS, SCHEMA_V1, SCHEMA_V2, Database, split_statements
from app.main import create_app
from app.repos import Store


def build_v2(path) -> None:
    raw = sqlite3.connect(path)
    for script in (SCHEMA_V1, SCHEMA_V2):
        for statement in split_statements(script):
            raw.execute(statement)
    raw.execute("PRAGMA user_version = 2")
    raw.execute("INSERT INTO projects (id, name, mode, created_at, updated_at) VALUES ('p1', 'Old', 'replay', 't', 't')")
    raw.execute("INSERT INTO artefacts (project_id, id, type, phase_key, title, created_at) VALUES ('p1', 'REQ-F-001', 't', 'requirements', 'T', 't')")
    raw.execute("INSERT INTO artefact_versions (project_id, artefact_id, number, body, author, created_at) VALUES ('p1', 'REQ-F-001', 1, 'body', 'human:a', 't')")
    raw.execute("INSERT INTO traces (project_id, agent, slot, requested_model, served_model, status, created_at) VALUES ('p1', 'a', 's', 'm', 'm', 'ok', 't')")
    raw.execute("INSERT INTO audit (project_id, at, actor, action, target_type, target_id) VALUES ('p1', 't', 'system', 'x.y', 'x', '1')")
    raw.execute("INSERT INTO memory (project_id, kind, text, created_at) VALUES ('p1', 'note', 'Remember the refund rule.', 't')")
    raw.commit()
    raw.close()


# ---- migration -----------------------------------------------------------------------------------------------

def test_a_fresh_database_is_at_the_latest_version_and_has_the_context_tables(tmp_path):
    db = Database(tmp_path / "x.db")
    assert db.migrate() == len(MIGRATIONS) >= 3
    with db.read() as conn:
        names = {r["name"] for r in conn.execute("SELECT name FROM sqlite_master")}
    assert {"context_documents", "context_chunks", "context_fts"} <= names


def test_a_v2_database_with_data_upgrades_and_every_row_survives(tmp_path):
    path = tmp_path / "old.db"
    build_v2(path)
    assert Database(path).migrate() == len(MIGRATIONS)
    with Database(path).read() as conn:
        counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                  for t in ("projects", "artefacts", "artefact_versions", "traces", "audit", "memory")}
    assert counts == {"projects": 1, "artefacts": 1, "artefact_versions": 1, "traces": 1, "audit": 1, "memory": 1}


def test_existing_memory_becomes_searchable_after_the_upgrade(tmp_path):
    path = tmp_path / "old.db"
    build_v2(path)
    store = Store.open(path)
    hit = store.context.search("p1", "refund rule")[0]
    assert hit.source_id == "MEM-001" and hit.kind == "memory"


def test_upgrading_twice_does_not_duplicate_the_backfilled_memory(tmp_path):
    path = tmp_path / "old.db"
    build_v2(path)
    Database(path).migrate()
    Database(path).migrate()
    assert len(Store.open(path).context.search("p1", "refund")) == 1


def test_concurrent_upgrades_of_a_v2_file_all_succeed_and_backfill_once(tmp_path):
    path = tmp_path / "race.db"
    build_v2(path)

    def go(_):
        return Database(path).migrate()

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(go, range(8))) == [len(MIGRATIONS)] * 8
    with Database(path).read() as conn:
        assert conn.execute("SELECT COUNT(*) FROM context_chunks WHERE kind = 'memory'").fetchone()[0] == 1


def test_new_memory_and_deleted_memory_stay_in_step_with_the_index(store, project):
    entry = store.memory.add(project.id, "note", "Giraffes need tall doors.", actor="system")
    assert store.context.resolve(project.id, f"MEM-{entry.id:03d}") is not None
    with store.db.write() as conn:
        conn.execute("DELETE FROM memory WHERE id = ?", (entry.id,))
    assert store.context.resolve(project.id, f"MEM-{entry.id:03d}") is None
    assert store.context.search(project.id, "giraffes") == []


def test_the_index_passes_sqlites_own_integrity_check_after_mixed_activity(store, project):
    for n in range(20):
        store.context.add_document(project.id, f"d{n}.txt", f"document number {n} about booking\n".encode(), actor="system")
    for n in (1, 5, 9):
        store.context.remove_document(project.id, n, actor="system")
    store.memory.add(project.id, "note", "extra", actor="system")
    with store.db.write() as conn:
        conn.execute("INSERT INTO context_fts(context_fts) VALUES('integrity-check')")  # raises if index and table disagree


# ---- settings --------------------------------------------------------------------------------------------------

def test_defaults_map_to_the_limits_object():
    limits = Settings(_env_file=None).context_limits
    assert limits == Limits()  # the shipped defaults are the spec's defaults
    assert (limits.max_file_bytes, limits.max_pdf_pages, limits.max_docs_per_project, limits.chunk_target_chars) == (10 * 1024 * 1024, 200, 500, 900)


def test_settings_are_read_from_a_dotenv_file_and_reach_the_limits(tmp_path):
    path = tmp_path / "t.env"
    path.write_text("CONTEXT_MAX_FILE_MB=2\nCONTEXT_MAX_PDF_PAGES=7\nCONTEXT_MAX_DOCS_PER_PROJECT=9\nCONTEXT_CHUNK_TARGET_CHARS=400\n")
    limits = Settings(_env_file=path).context_limits
    assert (limits.max_file_bytes, limits.max_pdf_pages, limits.max_docs_per_project, limits.chunk_target_chars) == (2 * 1024 * 1024, 7, 9, 400)


@pytest.mark.parametrize("field, bad", [
    ("context_max_file_mb", 0), ("context_max_file_mb", 101), ("context_max_pdf_pages", 0),
    ("context_max_docs_per_project", 0), ("context_chunk_target_chars", 100), ("context_chunk_target_chars", 1500),
])
def test_out_of_range_settings_are_rejected(field, bad):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: bad})


def test_the_app_builds_its_store_with_the_configured_limits(make_settings):
    app = create_app(make_settings(context_max_pdf_pages=11))
    assert app.state.store.context.limits.max_pdf_pages == 11


# ---- status --------------------------------------------------------------------------------------------------------

def test_the_context_status_block_describes_what_is_accepted_and_nothing_else(make_settings):
    response = TestClient(create_app(make_settings(context_max_file_mb=3))).get("/api/status")
    block = response.json()["context"]
    assert block == {"supported_types": ["txt", "md", "docx", "pdf"], "search": "keyword (BM25 with stemming)",
                     "max_file_mb": 3, "max_pdf_pages": 200, "max_docs_per_project": 500}
    assert "/Users" not in response.text and ".db" not in response.text


# ---- the demo script --------------------------------------------------------------------------------------------------

def test_the_demo_answers_five_questions_from_the_right_source(capsys):
    assert demo.main([]) == 0
    out = capsys.readouterr().out
    assert "5/5 questions answered from the right source, isolation OK" in out
    assert out.count("[ok ]") == 5 and "WRONG" not in out


def test_the_demo_shows_citations_relevance_and_coverage(capsys):
    demo.main([])
    out = capsys.readouterr().out
    assert "[DOC-001#3]" in out and "[SET-CHR-001@v1#1]" in out and "[MEM-001]" in out
    assert "relevance 1.00" in out and "coverage " in out and "How to read the numbers" in out


def test_the_demo_shows_replacement_and_isolation(capsys):
    demo.main([])
    out = capsys.readouterr().out
    assert "SET-CHR-001@v2#1" in out and "no longer found" in out
    assert "found 0 results" in out and "found nothing" in out


def test_the_demo_uses_a_temporary_database_and_never_the_real_one(make_settings, capsys):
    cfg = make_settings()
    demo.main([])
    capsys.readouterr()
    assert not cfg.db_path.exists()


def test_the_demo_needs_no_credentials_and_removes_its_folder(monkeypatch, capsys):
    import tempfile
    from pathlib import Path

    for name in ("IBM_ICA_API_KEY", "IBM_ICA_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)
    made: list[Path] = []
    real = tempfile.TemporaryDirectory

    def tracking(*a, **k):
        d = real(*a, **k)
        made.append(Path(d.name))
        return d

    monkeypatch.setattr(demo.tempfile, "TemporaryDirectory", tracking)
    assert demo.main([]) == 0
    capsys.readouterr()
    assert made and not any(p.exists() for p in made)


def test_the_demo_exits_one_when_a_top_hit_comes_from_the_wrong_source(monkeypatch, capsys):
    wrong = tuple(demo.Question(q.text, "DOC-999#", q.note) for q in demo.QUESTIONS)
    monkeypatch.setattr(demo, "QUESTIONS", wrong)
    assert demo.main([]) == 1
    assert "WRONG" in capsys.readouterr().out


def test_the_demo_exits_one_if_isolation_is_broken(monkeypatch, capsys):
    """Break isolation for real: make resolve() ignore which project is asking. The demo's own check
    ('a second project asking for DOC-001#1 must find nothing') has to notice and fail."""
    from app.context.store import ContextStore, _hit

    def leaky_resolve(self, project_id, source_id):
        with self.db.read() as conn:
            row = conn.execute("SELECT * FROM context_chunks WHERE source_id = ? LIMIT 1", (source_id,)).fetchone()
        return _hit(row) if row is not None else None

    monkeypatch.setattr(ContextStore, "resolve", leaky_resolve)
    assert demo.main([]) == 1
    out = capsys.readouterr().out
    assert "FAILED" in out and "TEXT, which is a bug" in out
