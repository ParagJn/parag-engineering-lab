from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


class SchemaTooNewError(RuntimeError):
    """The database was written by a newer version of the code than this one."""


# Statements are idempotent (IF NOT EXISTS) so a repeated or racing migrate is harmless.
SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS projects (
  id                TEXT PRIMARY KEY,
  name              TEXT NOT NULL CHECK (length(trim(name)) > 0),
  brief             TEXT NOT NULL DEFAULT '',
  mode              TEXT NOT NULL CHECK (mode IN ('live', 'replay')),
  selection         TEXT NOT NULL DEFAULT '{}',
  routing_overrides TEXT NOT NULL DEFAULT '{}',
  context_id        TEXT,
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS phase_runs (
  project_id  TEXT NOT NULL REFERENCES projects(id),
  phase_key   TEXT NOT NULL,
  status      TEXT NOT NULL CHECK (status IN
                ('not_started', 'running', 'awaiting_review', 'approved', 'rejected')),
  started_at  TEXT,
  finished_at TEXT,
  decision    TEXT CHECK (decision IN ('approve', 'reject')),
  decided_by  TEXT,
  feedback    TEXT,
  updated_at  TEXT NOT NULL,
  PRIMARY KEY (project_id, phase_key)
);

CREATE TABLE IF NOT EXISTS artefacts (
  project_id TEXT NOT NULL REFERENCES projects(id),
  id         TEXT NOT NULL,
  type       TEXT NOT NULL,
  phase_key  TEXT NOT NULL,
  title      TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (project_id, id)
);
CREATE INDEX IF NOT EXISTS idx_artefacts_phase ON artefacts (project_id, phase_key);

CREATE TABLE IF NOT EXISTS artefact_versions (
  project_id      TEXT NOT NULL,
  artefact_id     TEXT NOT NULL,
  number          INTEGER NOT NULL CHECK (number >= 1),
  body            TEXT NOT NULL,
  author          TEXT NOT NULL,
  source_chunks   TEXT NOT NULL DEFAULT '[]',
  review_findings TEXT,
  created_at      TEXT NOT NULL,
  PRIMARY KEY (project_id, artefact_id, number),
  FOREIGN KEY (project_id, artefact_id) REFERENCES artefacts (project_id, id)
);

CREATE TABLE IF NOT EXISTS links (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id  TEXT NOT NULL REFERENCES projects(id),
  from_id     TEXT NOT NULL,
  to_id       TEXT NOT NULL,
  kind        TEXT NOT NULL CHECK (kind IN ('derives', 'implements', 'verifies', 'deploys')),
  declared_in TEXT,
  created_at  TEXT NOT NULL,
  CHECK (from_id <> to_id),
  UNIQUE (project_id, from_id, to_id, kind),
  FOREIGN KEY (project_id, declared_in) REFERENCES artefacts (project_id, id)
);
CREATE INDEX IF NOT EXISTS idx_links_to ON links (project_id, to_id);

CREATE TABLE IF NOT EXISTS traces (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id      TEXT REFERENCES projects(id),
  run_id          TEXT,
  agent           TEXT NOT NULL,
  phase_key       TEXT,
  slot            TEXT NOT NULL,
  requested_model TEXT NOT NULL,
  served_model    TEXT NOT NULL,
  fallback_used   INTEGER NOT NULL DEFAULT 0 CHECK (fallback_used IN (0, 1)),
  status          TEXT NOT NULL CHECK (status IN ('ok', 'error')),
  error           TEXT,
  tokens_in       INTEGER NOT NULL DEFAULT 0 CHECK (tokens_in >= 0),
  tokens_out      INTEGER NOT NULL DEFAULT 0 CHECK (tokens_out >= 0),
  latency_ms      INTEGER NOT NULL DEFAULT 0 CHECK (latency_ms >= 0),
  cost_usd        REAL CHECK (cost_usd IS NULL OR cost_usd >= 0),
  created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_traces_project ON traces (project_id);

CREATE TABLE IF NOT EXISTS audit (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id  TEXT,
  at          TEXT NOT NULL,
  actor       TEXT NOT NULL,
  action      TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id   TEXT NOT NULL,
  detail      TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_audit_project ON audit (project_id);

CREATE TABLE IF NOT EXISTS memory (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id  TEXT NOT NULL REFERENCES projects(id),
  kind        TEXT NOT NULL CHECK (kind IN ('reviewer_feedback', 'human_feedback', 'note')),
  phase_key   TEXT,
  artefact_id TEXT,
  text        TEXT NOT NULL CHECK (length(trim(text)) > 0),
  created_at  TEXT NOT NULL,
  FOREIGN KEY (project_id, artefact_id) REFERENCES artefacts (project_id, id)
);
CREATE INDEX IF NOT EXISTS idx_memory_project ON memory (project_id);

CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;

CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit
BEGIN SELECT RAISE(ABORT, 'audit log is append-only'); END;

-- review_findings is deliberately not listed: the reviewer runs after the version exists.
CREATE TRIGGER IF NOT EXISTS version_immutable
BEFORE UPDATE OF project_id, artefact_id, number, body, author, source_chunks, created_at
ON artefact_versions
BEGIN SELECT RAISE(ABORT, 'artefact versions are immutable'); END;

CREATE TRIGGER IF NOT EXISTS version_no_delete BEFORE DELETE ON artefact_versions
BEGIN SELECT RAISE(ABORT, 'artefact versions are immutable'); END;
"""

SCHEMA_V2 = """
ALTER TABLE traces ADD COLUMN call_id TEXT;
ALTER TABLE traces ADD COLUMN attempt INTEGER NOT NULL DEFAULT 1;
CREATE INDEX IF NOT EXISTS idx_traces_call ON traces (call_id);
"""

SCHEMA_V3 = """
CREATE TABLE IF NOT EXISTS context_documents (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id  TEXT NOT NULL REFERENCES projects(id),
  number      INTEGER NOT NULL CHECK (number >= 1),
  filename    TEXT NOT NULL,
  kind        TEXT NOT NULL CHECK (kind IN ('txt', 'md', 'docx', 'pdf')),
  sha256      TEXT NOT NULL,
  size_bytes  INTEGER NOT NULL CHECK (size_bytes >= 0),
  chars       INTEGER NOT NULL CHECK (chars >= 0),
  chunk_count INTEGER NOT NULL CHECK (chunk_count >= 0),
  added_by    TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  removed_at  TEXT,
  UNIQUE (project_id, number)
);
CREATE INDEX IF NOT EXISTS idx_ctx_docs_hash ON context_documents (project_id, sha256);

CREATE TABLE IF NOT EXISTS context_chunks (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id   TEXT NOT NULL REFERENCES projects(id),
  source_id    TEXT NOT NULL,
  kind         TEXT NOT NULL CHECK (kind IN ('document', 'artefact', 'memory')),
  owner        TEXT NOT NULL,
  ordinal      INTEGER NOT NULL CHECK (ordinal >= 1),
  heading_path TEXT NOT NULL DEFAULT '',
  text         TEXT NOT NULL,
  page         INTEGER,
  title        TEXT NOT NULL DEFAULT '',
  phase_key    TEXT,
  artefact_id  TEXT,
  UNIQUE (project_id, source_id)
);
CREATE INDEX IF NOT EXISTS idx_ctx_chunks_owner ON context_chunks (project_id, owner);
CREATE INDEX IF NOT EXISTS idx_ctx_chunks_artefact ON context_chunks (project_id, artefact_id);

CREATE VIRTUAL TABLE IF NOT EXISTS context_fts USING fts5(
  text, heading_path,
  content = 'context_chunks', content_rowid = 'id',
  tokenize = 'porter unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS ctx_chunks_ai AFTER INSERT ON context_chunks BEGIN
  INSERT INTO context_fts (rowid, text, heading_path) VALUES (new.id, new.text, new.heading_path);
END;

CREATE TRIGGER IF NOT EXISTS ctx_chunks_ad AFTER DELETE ON context_chunks BEGIN
  INSERT INTO context_fts (context_fts, rowid, text, heading_path)
  VALUES ('delete', old.id, old.text, old.heading_path);
END;

CREATE TRIGGER IF NOT EXISTS ctx_chunks_au AFTER UPDATE ON context_chunks BEGIN
  INSERT INTO context_fts (context_fts, rowid, text, heading_path)
  VALUES ('delete', old.id, old.text, old.heading_path);
  INSERT INTO context_fts (rowid, text, heading_path) VALUES (new.id, new.text, new.heading_path);
END;

CREATE TRIGGER IF NOT EXISTS ctx_memory_ai AFTER INSERT ON memory BEGIN
  INSERT INTO context_chunks
    (project_id, source_id, kind, owner, ordinal, heading_path, text, title, phase_key, artefact_id)
  VALUES
    (new.project_id, 'MEM-' || printf('%03d', new.id), 'memory', 'MEM-' || printf('%03d', new.id), 1,
     new.kind, new.text, new.kind, new.phase_key, new.artefact_id);
END;

CREATE TRIGGER IF NOT EXISTS ctx_memory_ad AFTER DELETE ON memory BEGIN
  DELETE FROM context_chunks
  WHERE project_id = old.project_id AND owner = 'MEM-' || printf('%03d', old.id);
END;

INSERT INTO context_chunks
  (project_id, source_id, kind, owner, ordinal, heading_path, text, title, phase_key, artefact_id)
SELECT project_id, 'MEM-' || printf('%03d', id), 'memory', 'MEM-' || printf('%03d', id), 1,
       kind, text, kind, phase_key, artefact_id
FROM memory;
"""

SCHEMA_V4 = """
ALTER TABLE artefact_versions ADD COLUMN generation TEXT;

DROP TRIGGER IF EXISTS version_immutable;
-- review_findings is deliberately not listed: the reviewer runs after the version exists.
-- generation (how the version was made) is immutable like the rest of it.
CREATE TRIGGER version_immutable
BEFORE UPDATE OF project_id, artefact_id, number, body, author, source_chunks, created_at, generation
ON artefact_versions
BEGIN SELECT RAISE(ABORT, 'artefact versions are immutable'); END;
"""

# Append new schema steps here. Never edit an earlier entry once it has shipped.
# v5 (S09): one row per run of a phase, and an append-only log of what happened during runs. Nothing existing changes.
# `run_events` ids are global and strictly increasing, so "everything after event 41" is one indexed query.
SCHEMA_V5 = """
CREATE TABLE runs (
  id          TEXT PRIMARY KEY,
  project_id  TEXT NOT NULL REFERENCES projects(id),
  phase_key   TEXT NOT NULL,
  status      TEXT NOT NULL CHECK (status IN ('running', 'finished', 'stopped', 'failed', 'interrupted')),
  stop_reason TEXT CHECK (stop_reason IS NULL OR stop_reason IN ('budget', 'time', 'cancelled')),
  started_at  TEXT NOT NULL,
  finished_at TEXT,
  totals      TEXT
);
CREATE INDEX idx_runs_project ON runs (project_id, started_at);

CREATE TABLE run_events (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id TEXT NOT NULL REFERENCES projects(id),
  run_id     TEXT NOT NULL REFERENCES runs(id),
  at         TEXT NOT NULL,
  type       TEXT NOT NULL,
  data       TEXT NOT NULL
);
CREATE INDEX idx_run_events_project ON run_events (project_id, id);
CREATE INDEX idx_run_events_run ON run_events (run_id, id);

CREATE TRIGGER run_events_no_update BEFORE UPDATE ON run_events BEGIN SELECT RAISE(ABORT, 'run events are append-only'); END;
CREATE TRIGGER run_events_no_delete BEFORE DELETE ON run_events BEGIN SELECT RAISE(ABORT, 'run events are append-only'); END;
"""

# v6 (S12b addendum): a project can be archived. Archiving hides it and makes it read-only; nothing is deleted, so every
# immutability and append-only guard above is untouched. NULL means active.
SCHEMA_V6 = """
ALTER TABLE projects ADD COLUMN archived_at TEXT;
"""

# v7 (S17b): one row per round of the write -> test -> fix loop, so a report can say what each round found. Append-only like `run_events`:
# a round is a fact about what happened and is never edited. Rows hold counts and short failure lines, never file contents or a command's full output.
SCHEMA_V7 = """
CREATE TABLE build_rounds (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id  TEXT NOT NULL REFERENCES projects(id),
  run_id      TEXT,
  loop_id     TEXT NOT NULL,
  round       INTEGER NOT NULL CHECK (round >= 1),
  artefact    TEXT NOT NULL,
  version     INTEGER,
  outcome     TEXT NOT NULL,
  passed      INTEGER NOT NULL DEFAULT 0 CHECK (passed >= 0),
  failed      INTEGER NOT NULL DEFAULT 0 CHECK (failed >= 0),
  errors      INTEGER NOT NULL DEFAULT 0 CHECK (errors >= 0),
  skipped     INTEGER NOT NULL DEFAULT 0 CHECK (skipped >= 0),
  fingerprint TEXT NOT NULL,
  failures    TEXT NOT NULL,
  seconds     REAL NOT NULL DEFAULT 0,
  at          TEXT NOT NULL
);
CREATE INDEX idx_build_rounds_project ON build_rounds (project_id, id);
CREATE INDEX idx_build_rounds_loop ON build_rounds (loop_id, round);

CREATE TRIGGER build_rounds_no_update BEFORE UPDATE ON build_rounds BEGIN SELECT RAISE(ABORT, 'build rounds are append-only'); END;
CREATE TRIGGER build_rounds_no_delete BEFORE DELETE ON build_rounds BEGIN SELECT RAISE(ABORT, 'build rounds are append-only'); END;
"""

# v8 (S20b): Build Verify. One row per run, one row per designed item compared in it, and one per built thing the design never mentioned. Append-only like the other
# records of what happened: a run is a fact about a folder at a moment, and is never edited. Rows hold item IDs, short labels, file paths relative to the folder the
# person named, line numbers and counts; never source text.
SCHEMA_V8 = """
CREATE TABLE verify_runs (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id    TEXT NOT NULL REFERENCES projects(id),
  backend_path  TEXT NOT NULL,
  frontend_path TEXT,
  actor         TEXT NOT NULL,
  design        TEXT NOT NULL,
  counts        TEXT NOT NULL,
  notes         TEXT NOT NULL,
  at            TEXT NOT NULL
);
CREATE INDEX idx_verify_runs_project ON verify_runs (project_id, id);

CREATE TABLE verify_matches (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id      INTEGER NOT NULL REFERENCES verify_runs(id),
  designed    TEXT,
  area        TEXT NOT NULL,
  state       TEXT NOT NULL CHECK (state IN ('found', 'differences', 'possible', 'not_found', 'weak', 'extra')),
  step        TEXT NOT NULL DEFAULT '',
  score       REAL NOT NULL DEFAULT 0 CHECK (score >= 0 AND score <= 1),
  built       TEXT NOT NULL DEFAULT '',
  file        TEXT NOT NULL DEFAULT '',
  line        INTEGER NOT NULL DEFAULT 0 CHECK (line >= 0),
  differences TEXT NOT NULL,
  note        TEXT NOT NULL DEFAULT ''
);
CREATE INDEX idx_verify_matches_run ON verify_matches (run_id, id);

CREATE TRIGGER verify_runs_no_update BEFORE UPDATE ON verify_runs BEGIN SELECT RAISE(ABORT, 'verify runs are append-only'); END;
CREATE TRIGGER verify_runs_no_delete BEFORE DELETE ON verify_runs BEGIN SELECT RAISE(ABORT, 'verify runs are append-only'); END;
CREATE TRIGGER verify_matches_no_update BEFORE UPDATE ON verify_matches BEGIN SELECT RAISE(ABORT, 'verify matches are append-only'); END;
CREATE TRIGGER verify_matches_no_delete BEFORE DELETE ON verify_matches BEGIN SELECT RAISE(ABORT, 'verify matches are append-only'); END;
"""

MIGRATIONS = [SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4, SCHEMA_V5, SCHEMA_V6, SCHEMA_V7, SCHEMA_V8]


def split_statements(script: str) -> list[str]:
    """Split a script into single statements. Trigger bodies contain ';', so rely on SQLite to decide."""
    statements: list[str] = []
    buffer = ""
    for char in script:
        buffer += char
        # Only a ';' can end a statement, and SQLite says whether it ends one (not inside a trigger body).
        if char == ";" and sqlite3.complete_statement(buffer):
            statements.append(buffer.strip())
            buffer = ""
    leftover = "\n".join(
        line for line in buffer.splitlines() if line.strip() and not line.strip().startswith("--")
    )
    if leftover:
        raise ValueError("migration script ends in an incomplete statement")
    return statements


class Database:
    """A SQLite file. Each unit of work gets its own connection, so threads never share one."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        # isolation_level=None: we issue BEGIN/COMMIT ourselves.
        conn = sqlite3.connect(self.path, timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """One transaction. BEGIN IMMEDIATE takes the write lock up front, so writers queue."""
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")
        finally:
            conn.close()

    @property
    def schema_version(self) -> int:
        with self.read() as conn:
            return conn.execute("PRAGMA user_version").fetchone()[0]

    def migrate(self) -> int:
        """Bring the file up to the latest schema and return its version."""
        latest = len(MIGRATIONS)
        conn = self._connect()
        try:
            current = conn.execute("PRAGMA user_version").fetchone()[0]
            self._refuse_newer(current)
            if current == latest:
                return current
            if current == 0:
                self._enable_wal(conn)
            conn.execute("BEGIN IMMEDIATE")
            try:
                # Another process may have migrated while we waited for the write lock. Look again.
                current = conn.execute("PRAGMA user_version").fetchone()[0]
                self._refuse_newer(current)
                for number in range(current + 1, latest + 1):
                    for statement in split_statements(MIGRATIONS[number - 1]):
                        conn.execute(statement)
                    conn.execute(f"PRAGMA user_version = {number}")
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")
            return conn.execute("PRAGMA user_version").fetchone()[0]
        finally:
            conn.close()

    WAL_ATTEMPTS = 40
    WAL_WAIT_SECONDS = 0.05

    @classmethod
    def _enable_wal(cls, conn: sqlite3.Connection) -> None:
        """Switch the file to write-ahead logging, which persists in the file.

        Changing the journal mode needs a lock that SQLite's normal busy-wait does not always honour: when
        several processes open a brand-new file at once, one can get 'database is locked' straight away
        (found by a test that failed about 1 run in 20). So retry briefly. Another process winning the
        race is fine: the mode is already WAL, which is all we wanted.
        """
        for attempt in range(cls.WAL_ATTEMPTS):
            try:
                mode = conn.execute("PRAGMA journal_mode = WAL").fetchone()[0]
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                    raise
                if attempt == cls.WAL_ATTEMPTS - 1:
                    raise
                time.sleep(cls.WAL_WAIT_SECONDS)
                continue
            if str(mode).lower() == "wal":
                return
            if attempt == cls.WAL_ATTEMPTS - 1:
                return  # a filesystem that cannot do WAL (some network drives): carry on in the default mode
            time.sleep(cls.WAL_WAIT_SECONDS)

    @staticmethod
    def _refuse_newer(current: int) -> None:
        if current > len(MIGRATIONS):
            raise SchemaTooNewError(
                f"database is schema v{current} but this code only knows v{len(MIGRATIONS)}"
            )
