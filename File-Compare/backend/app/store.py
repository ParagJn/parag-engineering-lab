from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Saved comparisons keep the report, stats and extracted text, never the uploaded files.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS comparisons (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    name_a TEXT NOT NULL,
    name_b TEXT NOT NULL,
    report TEXT NOT NULL,
    report_title TEXT NOT NULL,
    model TEXT NOT NULL,
    files TEXT NOT NULL,
    stats TEXT NOT NULL,
    section_differences TEXT NOT NULL,
    line_changes TEXT NOT NULL,
    text_a TEXT NOT NULL,
    text_b TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_comparisons_created ON comparisons(created_at DESC);
"""

_JSON_FIELDS = ("files", "stats", "section_differences", "line_changes")
_DETAIL_COLUMNS = (
    "id, title, created_at, name_a, name_b, report, report_title, model, "
    "files, stats, section_differences, line_changes"
)


class ComparisonStore:
    def __init__(self, path: Path):
        self.path = path
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        # One short-lived connection per call: calls arrive from worker threads.
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    @staticmethod
    def _detail(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        for field in _JSON_FIELDS:
            item[field] = json.loads(item[field])
        return item

    def save(self, *, name_a: str, name_b: str, result: dict[str, Any], text_a: str, text_b: str) -> dict[str, Any]:
        comparison_id = uuid.uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        title = f"{name_a} vs {name_b}"
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO comparisons (id, title, created_at, name_a, name_b, report, report_title, model, "
                "files, stats, section_differences, line_changes, text_a, text_b) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    comparison_id, title, created_at, name_a, name_b,
                    result["report"], result["report_title"], result["model"],
                    json.dumps(result["files"]), json.dumps(result["stats"]),
                    json.dumps(result["section_differences"]), json.dumps(result["line_changes"]),
                    text_a, text_b,
                ),
            )
        return self.get(comparison_id)  # type: ignore[return-value]

    def get(self, comparison_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(f"SELECT {_DETAIL_COLUMNS} FROM comparisons WHERE id = ?", (comparison_id,)).fetchone()
        return self._detail(row) if row else None

    def texts(self, comparison_id: str) -> tuple[str, str] | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT text_a, text_b FROM comparisons WHERE id = ?", (comparison_id,)).fetchone()
        return (row["text_a"], row["text_b"]) if row else None

    def list(self, query: str = "", limit: int = 200) -> list[dict[str, Any]]:
        sql = "SELECT id, title, created_at, name_a, name_b, stats, files FROM comparisons"
        params: list[Any] = []
        if query.strip():
            like = "%" + query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            sql += " WHERE title LIKE ? ESCAPE '\\' OR name_a LIKE ? ESCAPE '\\' OR name_b LIKE ? ESCAPE '\\' OR report LIKE ? ESCAPE '\\'"
            params += [like, like, like, like]
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with closing(self._connect()) as conn:
            rows = conn.execute(sql, params).fetchall()
        items = []
        for row in rows:
            stats = json.loads(row["stats"])
            files = json.loads(row["files"])
            items.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "created_at": row["created_at"],
                    "name_a": row["name_a"],
                    "name_b": row["name_b"],
                    "type_a": files["a"]["type"],
                    "type_b": files["b"]["type"],
                    "line_similarity": stats["line_similarity"],
                    "section_similarity": stats["section_similarity"],
                }
            )
        return items

    def rename(self, comparison_id: str, title: str) -> bool:
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute("UPDATE comparisons SET title = ? WHERE id = ?", (title, comparison_id))
            return cursor.rowcount > 0

    def delete(self, comparison_id: str) -> bool:
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute("DELETE FROM comparisons WHERE id = ?", (comparison_id,))
            return cursor.rowcount > 0
