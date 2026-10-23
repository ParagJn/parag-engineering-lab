from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# A project is one document plus the diagrams drawn from it. The document text is kept so a diagram can be redrawn later;
# the uploaded file itself is never stored. Each diagram is its own row, so diagrams finishing in parallel never overwrite each other.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    model TEXT NOT NULL,
    chars INTEGER NOT NULL,
    truncated INTEGER NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_created ON projects(created_at DESC);

CREATE TABLE IF NOT EXISTS diagrams (
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    id TEXT NOT NULL,
    position INTEGER NOT NULL,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    focus TEXT NOT NULL,
    spec TEXT,
    PRIMARY KEY (project_id, id)
);
"""


class ProjectStore:
    def __init__(self, path: Path):
        self.path = path
        with closing(self._connect()) as conn, conn:
            conn.executescript(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        # One short-lived connection per call: calls arrive from worker threads.
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def create(
        self,
        *,
        title: str,
        source_name: str,
        text: str,
        truncated: bool,
        model: str,
        diagrams: list[dict[str, Any]],
    ) -> str:
        project_id = uuid.uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO projects (id, title, source_name, created_at, model, chars, truncated, text) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, title, source_name, created_at, model, len(text), int(truncated), text),
            )
            conn.executemany(
                "INSERT INTO diagrams (project_id, id, position, type, title, summary, focus, spec) VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
                [(project_id, d["id"], i, d["type"], d["title"], d["summary"], d["focus"]) for i, d in enumerate(diagrams)],
            )
        return project_id

    def save_spec(self, project_id: str, diagram_id: str, spec: dict[str, Any]) -> bool:
        with closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "UPDATE diagrams SET spec = ? WHERE project_id = ? AND id = ?",
                (json.dumps(spec, ensure_ascii=False), project_id, diagram_id),
            )
            return cursor.rowcount > 0

    def get(self, project_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT id, title, source_name, created_at, model, chars, truncated, text FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            if not row:
                return None
            rows = conn.execute(
                "SELECT id, type, title, summary, focus, spec FROM diagrams WHERE project_id = ? ORDER BY position",
                (project_id,),
            ).fetchall()
        project = dict(row)
        project["truncated"] = bool(project["truncated"])
        project["diagrams"] = [{**dict(r), "spec": json.loads(r["spec"]) if r["spec"] else None} for r in rows]
        return project

    def list(self, query: str = "", limit: int = 200) -> list[dict[str, Any]]:
        sql = (
            "SELECT p.id, p.title, p.source_name, p.created_at, "
            "COUNT(d.id) AS diagram_count, COALESCE(SUM(d.spec IS NOT NULL), 0) AS drawn_count "
            "FROM projects p LEFT JOIN diagrams d ON d.project_id = p.id"
        )
        params: list[Any] = []
        if query.strip():
            like = "%" + query.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            sql += (
                " WHERE p.title LIKE ? ESCAPE '\\' OR p.source_name LIKE ? ESCAPE '\\' OR p.text LIKE ? ESCAPE '\\'"
                " OR EXISTS (SELECT 1 FROM diagrams x WHERE x.project_id = p.id AND x.title LIKE ? ESCAPE '\\')"
            )
            params += [like, like, like, like]
        sql += " GROUP BY p.id ORDER BY p.created_at DESC LIMIT ?"
        params.append(limit)
        with closing(self._connect()) as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def rename(self, project_id: str, title: str) -> bool:
        with closing(self._connect()) as conn, conn:
            return conn.execute("UPDATE projects SET title = ? WHERE id = ?", (title, project_id)).rowcount > 0

    def delete(self, project_id: str) -> bool:
        with closing(self._connect()) as conn, conn:
            return conn.execute("DELETE FROM projects WHERE id = ?", (project_id,)).rowcount > 0
