"""SQLite database wrapper.

One file (data/assistant.db) holds chats, messages, projects and attachment
metadata. The files themselves (uploads, extracted Markdown, extracted images,
SVGs) stay on disk; rows only store their paths.

SQLite is built into Python, so there is nothing extra to install or run.
"""

import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Iterator, Optional

from .config import config


# Each entry upgrades the schema by one version; applied in order on startup.
# Never edit a released entry - add a new one instead.
MIGRATIONS: list[str] = [
    # v1: initial schema
    """
    -- Small key/value store for app state (e.g. when the JSON import ran)
    CREATE TABLE app_meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE projects (
        project_id   TEXT PRIMARY KEY,
        name         TEXT NOT NULL,
        description  TEXT NOT NULL DEFAULT '',
        instructions TEXT NOT NULL DEFAULT '',
        created_at   TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    );

    CREATE TABLE sessions (
        session_id         TEXT PRIMARY KEY,
        project_id         TEXT REFERENCES projects(project_id) ON DELETE SET NULL,
        title              TEXT NOT NULL DEFAULT 'New conversation',
        model              TEXT NOT NULL DEFAULT 'claude',
        web_search_enabled INTEGER NOT NULL DEFAULT 0,
        created_at         TEXT NOT NULL,
        updated_at         TEXT NOT NULL
    );
    CREATE INDEX idx_sessions_updated ON sessions(updated_at DESC);
    CREATE INDEX idx_sessions_project ON sessions(project_id, updated_at DESC);

    -- pk is an explicit integer key so the search index rowids stay stable
    CREATE TABLE messages (
        pk            INTEGER PRIMARY KEY,
        id            TEXT NOT NULL UNIQUE,
        session_id    TEXT NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
        role          TEXT NOT NULL,
        content       TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        svg_image_id  TEXT,
        svg_parent_id TEXT,
        svg_version   INTEGER
    );
    CREATE INDEX idx_messages_session ON messages(session_id, pk);

    -- session_id: the chat the file was uploaded in (NULL if that chat is gone)
    CREATE TABLE attachments (
        attachment_id         TEXT PRIMARY KEY,
        session_id            TEXT REFERENCES sessions(session_id) ON DELETE SET NULL,
        filename              TEXT NOT NULL,
        mime_type             TEXT NOT NULL,
        size_bytes            INTEGER NOT NULL,
        stored_path           TEXT NOT NULL,
        content_markdown_path TEXT,
        images                TEXT NOT NULL DEFAULT '[]',
        status                TEXT NOT NULL,
        created_at            TEXT NOT NULL
    );
    CREATE INDEX idx_attachments_session ON attachments(session_id);

    -- Which files were sent with which message
    CREATE TABLE message_attachments (
        message_id    TEXT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
        attachment_id TEXT NOT NULL REFERENCES attachments(attachment_id) ON DELETE CASCADE,
        position      INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (message_id, attachment_id)
    );
    CREATE INDEX idx_message_attachments_attachment ON message_attachments(attachment_id);

    -- Documents pinned to a project (sent with every message in that project)
    CREATE TABLE project_documents (
        project_id    TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
        attachment_id TEXT NOT NULL REFERENCES attachments(attachment_id) ON DELETE CASCADE,
        pinned_at     TEXT NOT NULL,
        PRIMARY KEY (project_id, attachment_id)
    );
    CREATE INDEX idx_project_documents_attachment ON project_documents(attachment_id);

    -- Full-text search over message content, kept in sync by triggers
    CREATE VIRTUAL TABLE messages_fts USING fts5(
        content, content='messages', content_rowid='pk', tokenize='porter unicode61'
    );
    CREATE TRIGGER messages_ai AFTER INSERT ON messages BEGIN
        INSERT INTO messages_fts(rowid, content) VALUES (new.pk, new.content);
    END;
    CREATE TRIGGER messages_ad AFTER DELETE ON messages BEGIN
        INSERT INTO messages_fts(messages_fts, rowid, content) VALUES ('delete', old.pk, old.content);
    END;
    CREATE TRIGGER messages_au AFTER UPDATE OF content ON messages BEGIN
        INSERT INTO messages_fts(messages_fts, rowid, content) VALUES ('delete', old.pk, old.content);
        INSERT INTO messages_fts(rowid, content) VALUES (new.pk, new.content);
    END;
    """,
]

# Tables the generic helpers may touch (search index tables are managed by triggers)
TABLES = {
    "app_meta",
    "projects",
    "sessions",
    "messages",
    "attachments",
    "message_attachments",
    "project_documents",
}

# Columns converted back to Python types when read through the generic helpers
JSON_COLUMNS = {"attachments": {"images"}}
BOOL_COLUMNS = {"sessions": {"web_search_enabled"}}

_ORDER_BY_PART = re.compile(r"^\s*(\w+)(?:\s+(ASC|DESC))?\s*$", re.IGNORECASE)


class DatabaseError(RuntimeError):
    """Raised for invalid use of the database wrapper."""


class Database:
    """
    Thin wrapper around one SQLite connection.

    - insert / insert_many / upsert / update / delete / get / find / count for
      single-table work; `where` is a dict of column -> value (None matches
      NULL, a list or tuple matches any of its values).
    - transaction() groups several writes so they all apply or none do.
    - search_messages / search_session_titles for chat search.
    - query / execute for anything the helpers don't cover (joins etc.).

    Table and column names are checked against the schema, and every value is
    passed as a parameter, so callers can't inject SQL through these helpers.

    One connection is shared and guarded by a lock. Don't `await` inside
    transaction(): other coroutines on the event loop run on the same thread
    and would slip into the open transaction.
    """

    def __init__(self, db_path: Optional[Path | str] = None):
        """Open (or create) the database and bring the schema up to date."""
        self.db_path = str(db_path or config.DB_PATH)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._tx_depth = 0
        self._columns: dict[str, set[str]] = {}

        # isolation_level=None: autocommit, transactions are managed explicitly
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA busy_timeout = 5000")
        if self.db_path != ":memory:":
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA synchronous = NORMAL")

        self._migrate()

    # ------------------------------------------------------------------ setup

    @property
    def schema_version(self) -> int:
        """Current schema version stored in the database file."""
        return self._conn.execute("PRAGMA user_version").fetchone()[0]

    def _migrate(self):
        """Apply any schema migrations the database hasn't had yet."""
        with self._lock:
            current = self.schema_version
            for version, script in enumerate(MIGRATIONS[current:], start=current + 1):
                # executescript can't run inside a Python-managed transaction,
                # so the script carries its own BEGIN/COMMIT
                try:
                    self._conn.executescript(
                        f"BEGIN IMMEDIATE;\n{script}\nPRAGMA user_version = {version};\nCOMMIT;"
                    )
                except Exception:
                    if self._conn.in_transaction:
                        self._conn.execute("ROLLBACK")
                    raise

    def close(self):
        """Close the connection."""
        with self._lock:
            self._conn.close()

    # ------------------------------------------------------------ transactions

    @contextmanager
    def transaction(self) -> Iterator["Database"]:
        """
        Run several writes atomically. Nested calls join the outer transaction.

            with db.transaction():
                db.insert("sessions", {...})
                db.insert("messages", {...})
        """
        with self._lock:
            outermost = self._tx_depth == 0
            if outermost:
                self._conn.execute("BEGIN IMMEDIATE")
            self._tx_depth += 1
            try:
                yield self
            except BaseException:
                self._tx_depth -= 1
                if outermost:
                    self._conn.execute("ROLLBACK")
                raise
            else:
                self._tx_depth -= 1
                if outermost:
                    self._conn.execute("COMMIT")

    # --------------------------------------------------------- generic helpers

    def insert(self, table: str, row: dict[str, Any], *, or_ignore: bool = False) -> int:
        """Insert one row. Returns the number of rows inserted (0 if ignored as a duplicate)."""
        columns = self._check_columns(table, row.keys())
        verb = "INSERT OR IGNORE" if or_ignore else "INSERT"
        sql = (
            f"{verb} INTO {table} ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)})"
        )
        return self._write(sql, [self._encode(row[c]) for c in columns])

    def insert_many(self, table: str, rows: list[dict[str, Any]], *, or_ignore: bool = False) -> int:
        """Insert several rows with the same columns in one transaction. Returns rows inserted."""
        if not rows:
            return 0
        columns = self._check_columns(table, rows[0].keys())
        verb = "INSERT OR IGNORE" if or_ignore else "INSERT"
        sql = (
            f"{verb} INTO {table} ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)})"
        )
        params = []
        for row in rows:
            if set(row.keys()) != set(columns):
                raise DatabaseError(f"insert_many: every row must have the columns {columns}")
            params.append([self._encode(row[c]) for c in columns])
        with self.transaction():
            before = self._conn.total_changes
            self._conn.executemany(sql, params)
            return self._conn.total_changes - before

    def upsert(self, table: str, row: dict[str, Any], key: str | list[str]) -> int:
        """Insert a row, or update the existing row with the same key column(s)."""
        keys = [key] if isinstance(key, str) else list(key)
        columns = self._check_columns(table, row.keys())
        self._check_columns(table, keys)
        missing = [k for k in keys if k not in row]
        if missing:
            raise DatabaseError(f"upsert: row is missing key column(s) {missing}")

        updates = [c for c in columns if c not in keys]
        conflict = (
            f"DO UPDATE SET {', '.join(f'{c} = excluded.{c}' for c in updates)}"
            if updates
            else "DO NOTHING"
        )
        sql = (
            f"INSERT INTO {table} ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)}) "
            f"ON CONFLICT ({', '.join(keys)}) {conflict}"
        )
        return self._write(sql, [self._encode(row[c]) for c in columns])

    def update(self, table: str, where: dict[str, Any], values: dict[str, Any]) -> int:
        """Update matching rows. Returns the number of rows changed."""
        if not values:
            return 0
        if not where:
            raise DatabaseError("update: refusing to update every row; pass a where filter")
        columns = self._check_columns(table, values.keys())
        where_sql, where_params = self._where(table, where)
        sql = f"UPDATE {table} SET {', '.join(f'{c} = ?' for c in columns)}{where_sql}"
        return self._write(sql, [self._encode(values[c]) for c in columns] + where_params)

    def delete(self, table: str, where: dict[str, Any]) -> int:
        """Delete matching rows (related rows follow the schema's ON DELETE rules). Returns rows deleted."""
        if not where:
            raise DatabaseError("delete: refusing to delete every row; pass a where filter")
        where_sql, where_params = self._where(table, where)
        return self._write(f"DELETE FROM {table}{where_sql}", where_params)

    def get(self, table: str, where: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Return the first matching row, or None."""
        rows = self.find(table, where, limit=1)
        return rows[0] if rows else None

    def find(
        self,
        table: str,
        where: Optional[dict[str, Any]] = None,
        *,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Return matching rows as dicts.

        order_by: comma-separated columns, each optionally ASC/DESC,
        e.g. "updated_at DESC, title".
        """
        where_sql, params = self._where(table, where or {})
        sql = f"SELECT * FROM {table}{where_sql}{self._order_by(table, order_by)}"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
            if offset:
                sql += " OFFSET ?"
                params.append(int(offset))
        return [self._decode(table, row) for row in self.query(sql, params)]

    def count(self, table: str, where: Optional[dict[str, Any]] = None) -> int:
        """Count matching rows."""
        where_sql, params = self._where(table, where or {})
        with self._lock:
            return self._conn.execute(f"SELECT COUNT(*) FROM {table}{where_sql}", params).fetchone()[0]

    def exists(self, table: str, where: dict[str, Any]) -> bool:
        """True if at least one row matches."""
        return self.get(table, where) is not None

    # ------------------------------------------------------------------ search

    def search_messages(
        self,
        text: str,
        *,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        limit: int = 20,
        highlight: tuple[str, str] = ("<mark>", "</mark>"),
    ) -> list[dict[str, Any]]:
        """
        Full-text search over message content, best matches first.

        Every word must appear (the last one also matches as a prefix, so
        partial typing works); "running" also finds "run". Returns message_id,
        session_id, session_title, project_id, role, created_at and a short
        snippet with matches wrapped in `highlight`.
        """
        match = self._fts_query(text)
        if not match:
            return []

        sql = """
            SELECT m.id AS message_id, m.session_id, s.title AS session_title,
                   s.project_id, m.role, m.created_at,
                   snippet(messages_fts, 0, ?, ?, '…', 16) AS snippet
            FROM messages_fts
            JOIN messages m ON m.pk = messages_fts.rowid
            JOIN sessions s ON s.session_id = m.session_id
            WHERE messages_fts MATCH ?
        """
        params: list[Any] = [highlight[0], highlight[1], match]
        if project_id is not None:
            sql += " AND s.project_id = ?"
            params.append(project_id)
        if session_id is not None:
            sql += " AND m.session_id = ?"
            params.append(session_id)
        sql += " ORDER BY bm25(messages_fts) LIMIT ?"
        params.append(int(limit))
        return self.query(sql, params)

    def search_session_titles(
        self,
        text: str,
        *,
        project_id: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Chats whose title contains every word of `text` (case-insensitive), newest first."""
        words = text.split()
        if not words:
            return []
        clauses = ["title LIKE ? ESCAPE '\\'"] * len(words)
        params: list[Any] = [f"%{self._escape_like(w)}%" for w in words]
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        sql = (
            f"SELECT * FROM sessions WHERE {' AND '.join(clauses)} "
            "ORDER BY updated_at DESC LIMIT ?"
        )
        params.append(int(limit))
        return [self._decode("sessions", row) for row in self.query(sql, params)]

    # --------------------------------------------------------------- raw access

    def query(self, sql: str, params: Optional[list | tuple | dict] = None) -> list[dict[str, Any]]:
        """Run a SELECT and return rows as dicts. Always pass values via params."""
        with self._lock:
            return [dict(row) for row in self._conn.execute(sql, params or [])]

    def execute(self, sql: str, params: Optional[list | tuple | dict] = None) -> int:
        """Run a write statement. Returns rows changed. Always pass values via params."""
        return self._write(sql, params or [])

    # -------------------------------------------------------------- maintenance

    def backup(self, target_path: Path | str) -> Path:
        """Write a consistent copy of the whole database to `target_path` (safe while in use)."""
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            dest = sqlite3.connect(str(target))
            try:
                self._conn.backup(dest)
            finally:
                dest.close()
        return target

    def backup_with_timestamp(self, backups_dir: Optional[Path] = None) -> Path:
        """Backup to <data>/backups/assistant-YYYYmmdd-HHMMSS.db."""
        backups_dir = backups_dir or config.DATA_DIR / "backups"
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        return self.backup(backups_dir / f"assistant-{stamp}.db")

    def vacuum(self):
        """Reclaim space after large deletes and optimise the search index."""
        with self._lock:
            if self._tx_depth:
                raise DatabaseError("vacuum can't run inside a transaction")
            self._conn.execute("INSERT INTO messages_fts(messages_fts) VALUES ('optimize')")
            self._conn.execute("VACUUM")

    def integrity_check(self) -> list[str]:
        """Return SQLite's integrity report (['ok'] when healthy) plus any broken foreign keys."""
        with self._lock:
            report = [row[0] for row in self._conn.execute("PRAGMA integrity_check")]
            broken = [
                f"foreign key: {row[0]} rowid {row[1]} -> {row[2]}"
                for row in self._conn.execute("PRAGMA foreign_key_check")
            ]
        return report + broken

    @staticmethod
    def disk_usage(db_path: Optional[Path] = None) -> int:
        """Bytes used by the database file and its WAL/shared-memory files."""
        path = Path(db_path or config.DB_PATH)
        return sum(
            p.stat().st_size
            for p in (path, path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm"))
            if p.exists()
        )

    # ------------------------------------------------------------------ helpers

    def _write(self, sql: str, params: list | tuple | dict) -> int:
        with self._lock:
            cursor = self._conn.execute(sql, params)
            return cursor.rowcount

    def _table_columns(self, table: str) -> set[str]:
        if table not in TABLES:
            raise DatabaseError(f"Unknown table: {table!r}")
        if table not in self._columns:
            with self._lock:
                self._columns[table] = {
                    row["name"] for row in self._conn.execute(f"PRAGMA table_info({table})")
                }
        return self._columns[table]

    def _check_columns(self, table: str, names) -> list[str]:
        names = list(names)
        if not names:
            raise DatabaseError(f"No columns given for table {table!r}")
        unknown = [n for n in names if n not in self._table_columns(table)]
        if unknown:
            raise DatabaseError(f"Unknown column(s) for {table!r}: {unknown}")
        return names

    def _where(self, table: str, where: dict[str, Any]) -> tuple[str, list[Any]]:
        if not where:
            self._table_columns(table)  # still validate the table name
            return "", []
        clauses: list[str] = []
        params: list[Any] = []
        for column in self._check_columns(table, where.keys()):
            value = where[column]
            if value is None:
                clauses.append(f"{column} IS NULL")
            elif isinstance(value, (list, tuple, set)):
                values = list(value)
                if not values:
                    clauses.append("0")  # IN () matches nothing
                else:
                    clauses.append(f"{column} IN ({', '.join('?' for _ in values)})")
                    params.extend(self._encode(v) for v in values)
            else:
                clauses.append(f"{column} = ?")
                params.append(self._encode(value))
        return " WHERE " + " AND ".join(clauses), params

    def _order_by(self, table: str, order_by: Optional[str]) -> str:
        if not order_by:
            return ""
        parts = []
        for part in order_by.split(","):
            match = _ORDER_BY_PART.match(part)
            if not match:
                raise DatabaseError(f"Invalid order_by: {order_by!r}")
            column, direction = match.group(1), (match.group(2) or "ASC").upper()
            self._check_columns(table, [column])
            parts.append(f"{column} {direction}")
        return " ORDER BY " + ", ".join(parts)

    @staticmethod
    def _encode(value: Any) -> Any:
        """Convert Python values to what SQLite stores."""
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, default=str)
        if isinstance(value, Path):
            return str(value)
        return value

    @staticmethod
    def _decode(table: str, row: dict[str, Any]) -> dict[str, Any]:
        """Turn JSON and boolean columns back into Python values."""
        for column in JSON_COLUMNS.get(table, ()):
            if isinstance(row.get(column), str):
                row[column] = json.loads(row[column])
        for column in BOOL_COLUMNS.get(table, ()):
            if column in row and row[column] is not None:
                row[column] = bool(row[column])
        return row

    @staticmethod
    def _fts_query(text: str) -> Optional[str]:
        """
        Turn free text into a safe FTS5 query: each word quoted (so characters
        like - " * : ( are never read as search syntax), all words required,
        and the last word also matches as a prefix.
        """
        words = re.findall(r"\w+", text or "")
        if not words:
            return None
        quoted = [f'"{w}"' for w in words]
        quoted[-1] += "*"
        return " ".join(quoted)

    @staticmethod
    def _escape_like(text: str) -> str:
        return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# Singleton instance
_database: Database | None = None
_database_lock = threading.Lock()


def get_database() -> Database:
    """Get the shared database connection."""
    global _database
    if _database is None:
        with _database_lock:
            if _database is None:
                _database = Database()
    return _database

