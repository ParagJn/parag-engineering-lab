"""Per-dataset question history (data/<id>/history.sqlite), grouped by chat session."""

import json
import re
import sqlite3
from datetime import datetime, timezone

from workspace import jsonable

_SID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


def valid_session(sid: str) -> bool:
    return bool(_SID_RE.match(sid or ""))


def _con(ds) -> sqlite3.Connection:
    con = sqlite3.connect(ds.root / "history.sqlite")
    con.row_factory = sqlite3.Row
    con.execute(
        """CREATE TABLE IF NOT EXISTS ask_history (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             session_id TEXT NOT NULL,
             asked_at TEXT NOT NULL,
             scope_id TEXT NOT NULL,
             question TEXT NOT NULL,
             answer TEXT NOT NULL,
             kind TEXT NOT NULL,
             result_json TEXT NOT NULL)"""
    )
    con.execute("CREATE INDEX IF NOT EXISTS ix_hist_session ON ask_history(session_id, id)")
    return con


def record(ds, session_id: str, scope_id: str, question: str, result: dict) -> None:
    with ds.lock:
        con = _con(ds)
        try:
            with con:
                con.execute(
                    "INSERT INTO ask_history (session_id, asked_at, scope_id, question, answer, kind, result_json) VALUES (?,?,?,?,?,?,?)",
                    (session_id, datetime.now(timezone.utc).isoformat(timespec="seconds"), scope_id, question,
                     result.get("answer", ""), result.get("kind", "answer"), json.dumps(result, default=jsonable)),
                )
        finally:
            con.close()


def sessions(ds, scope_id: str, limit: int = 50) -> list[dict]:
    with ds.lock:
        con = _con(ds)
        try:
            rows = con.execute(
                """SELECT session_id, MIN(asked_at) AS started, MAX(asked_at) AS last, COUNT(*) AS n,
                          (SELECT question FROM ask_history h2 WHERE h2.session_id = h.session_id ORDER BY id LIMIT 1) AS first_q
                   FROM ask_history h WHERE scope_id = ? GROUP BY session_id ORDER BY last DESC LIMIT ?""",
                (scope_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            con.close()


def messages(ds, session_id: str) -> list[dict]:
    with ds.lock:
        con = _con(ds)
        try:
            rows = con.execute(
                "SELECT asked_at, question, result_json FROM ask_history WHERE session_id = ? ORDER BY id", (session_id,)
            ).fetchall()
            return [{"asked_at": r["asked_at"], "question": r["question"], "result": json.loads(r["result_json"])} for r in rows]
        finally:
            con.close()


def delete_session(ds, session_id: str) -> None:
    with ds.lock:
        con = _con(ds)
        try:
            with con:
                con.execute("DELETE FROM ask_history WHERE session_id = ?", (session_id,))
        finally:
            con.close()
