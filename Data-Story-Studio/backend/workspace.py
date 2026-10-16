"""Dataset workspaces: uploaded files, the DuckDB database and the JSON state per dataset.

  data/<id>/files/       original uploads
  data/<id>/db.duckdb    typed tables + analysis views
  data/<id>/state.json   profiles, readiness, setup answers, dashboards
"""

import json
import re
import shutil
import threading
import time
import uuid
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

from config import get_settings

_ID_RE = re.compile(r"^[a-f0-9]{12}$")
QUERY_TIMEOUT_S = 20


class QueryError(RuntimeError):
    pass


def jsonable(v: Any) -> Any:
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return v if v == v and v not in (float("inf"), float("-inf")) else None
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, datetime):
        return v.isoformat(sep=" ") if (v.hour or v.minute or v.second) else v.date().isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if hasattr(v, "item"):
        return jsonable(v.item())
    return str(v)


class Dataset:
    def __init__(self, ds_id: str, root: Path):
        self.id = ds_id
        self.root = root
        self.files_dir = root / "files"
        self.state_path = root / "state.json"
        self.lock = threading.RLock()
        self.state: dict = json.loads(self.state_path.read_text()) if self.state_path.exists() else {"id": ds_id}
        self._con: duckdb.DuckDBPyConnection | None = None

    @property
    def con(self) -> duckdb.DuckDBPyConnection:
        if self._con is None:
            # External access off: SQL (including AI-written SQL) cannot read or write files.
            self._con = duckdb.connect(
                str(self.root / "db.duckdb"),
                config={"enable_external_access": False, "autoinstall_known_extensions": False,
                        "autoload_known_extensions": False},
            )
        return self._con

    def save(self) -> None:
        with self.lock:
            tmp = self.state_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.state, default=jsonable, indent=1))
            tmp.replace(self.state_path)

    def close(self) -> None:
        if self._con is not None:
            self._con.close()
            self._con = None

    # ------------------------------------------------------------ querying

    def query(self, sql: str, params: list | None = None, limit: int | None = None) -> dict:
        """Run a SELECT on a fresh cursor with a timeout; return JSON-ready columns + rows."""
        limit = limit or get_settings().max_result_rows
        cur = self.con.cursor()
        timer = threading.Timer(QUERY_TIMEOUT_S, cur.interrupt)
        timer.start()
        try:
            res = cur.execute(f"SELECT * FROM ({sql}) LIMIT {limit + 1}", params or [])
            cols = [d[0] for d in res.description]
            types = [str(t) for t in res.dtypes] if hasattr(res, "dtypes") else []
            rows = res.fetchall()
        except duckdb.InterruptException as err:
            raise QueryError(f"Query took longer than {QUERY_TIMEOUT_S}s and was stopped") from err
        except duckdb.Error as err:
            raise QueryError(str(err).split("\n")[0]) from err
        finally:
            timer.cancel()
            cur.close()
        truncated = len(rows) > limit
        rows = rows[:limit]
        return {
            "columns": cols,
            "types": types,
            "rows": [[jsonable(v) for v in r] for r in rows],
            "truncated": truncated,
        }

    def scalar(self, sql: str, params: list | None = None) -> Any:
        cur = self.con.cursor()
        try:
            return cur.execute(sql, params or []).fetchone()[0]
        finally:
            cur.close()


def validate_select(con: duckdb.DuckDBPyConnection, sql: str) -> str:
    """Accept exactly one read-only SELECT statement (AI-written or user-written SQL)."""
    sql = sql.strip().rstrip(";").strip()
    if not sql:
        raise QueryError("Empty query")
    try:
        stmts = con.extract_statements(sql)
    except duckdb.Error as err:
        raise QueryError(f"SQL could not be parsed: {str(err).splitlines()[0]}") from err
    if len(stmts) != 1:
        raise QueryError("Only a single SELECT statement is allowed")
    if stmts[0].type != duckdb.StatementType.SELECT:
        raise QueryError(f"Only SELECT queries are allowed (got {stmts[0].type.name})")
    return sql


class Registry:
    def __init__(self):
        self._items: dict[str, Dataset] = {}
        self._lock = threading.Lock()

    @property
    def root(self) -> Path:
        r = get_settings().data_dir
        r.mkdir(parents=True, exist_ok=True)
        return r

    def create(self) -> Dataset:
        ds_id = uuid.uuid4().hex[:12]
        root = self.root / ds_id
        (root / "files").mkdir(parents=True)
        ds = Dataset(ds_id, root)
        ds.state.update({"id": ds_id, "created": time.time()})
        ds.save()
        with self._lock:
            self._items[ds_id] = ds
        return ds

    def get(self, ds_id: str) -> Dataset:
        if not _ID_RE.match(ds_id or ""):
            raise KeyError(ds_id)
        with self._lock:
            if ds_id in self._items:
                return self._items[ds_id]
            root = self.root / ds_id
            if not (root / "state.json").exists():
                raise KeyError(ds_id)
            ds = Dataset(ds_id, root)
            self._items[ds_id] = ds
            return ds

    def list(self) -> list[dict]:
        out = []
        for p in sorted(self.root.glob("*/state.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                st = json.loads(p.read_text())
            except json.JSONDecodeError:
                continue
            dash = next(iter((st.get("dashboards") or {}).values()), None)
            out.append({
                "id": st.get("id"), "created": st.get("created"),
                "files": [f["name"] for f in st.get("files", [])],
                "rows": (st.get("readiness") or {}).get("total_rows"),
                "title": ((dash.get("story") or {}).get("headline") or {}).get("title") if dash else None,
                "stage": "dashboard" if dash else "readiness" if st.get("readiness") else "upload",
                "example": bool(st.get("example")),
            })
        return out

    def delete(self, ds_id: str) -> None:
        ds = self.get(ds_id)
        with self._lock:
            ds.close()
            self._items.pop(ds_id, None)
        shutil.rmtree(ds.root, ignore_errors=True)


registry = Registry()
