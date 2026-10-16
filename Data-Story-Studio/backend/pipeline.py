"""Upload -> ingest -> profile -> readiness, and setup -> scopes -> dashboard."""

import time

from config import get_settings
from ingest import read_file, write_duckdb
from insights import discover
from model import build_scopes
from panels import Ctx, RecipeError, compile_panel
from profile import profile_table, q
from readiness import assess, find_relationships
from story import compose


def ingest_all(ds) -> dict:
    """(Re)build every table from the uploaded files, then profile and assess readiness."""
    st = ds.state
    con = ds.con
    for (name, kind) in con.execute(
        "SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = 'main'"
    ).fetchall():
        con.execute(f"DROP {'VIEW' if kind == 'VIEW' else 'TABLE'} IF EXISTS {q(name)}")
    overrides = st.get("overrides") or {}
    dedupe = set(st.get("dedupe") or [])
    existing: set[str] = set()
    profiles, rows, info, sources, errors = {}, {}, {}, {}, []
    for f in st.get("files", []):
        try:
            tables = read_file(ds.files_dir / f["stored"], existing, overrides, f["name"])
        except Exception as err:  # unreadable file -> reported, others continue
            errors.append({"file": f["name"], "error": str(err)})
            continue
        f["tables"] = [t.name for t in tables]
        for t in tables:
            write_duckdb(con, t)
            removed = 0
            if t.name in dedupe:
                before = con.execute(f"SELECT count(*) FROM {q(t.name)}").fetchone()[0]
                con.execute(f"CREATE OR REPLACE TABLE {q(t.name)} AS SELECT DISTINCT * FROM {q(t.name)}")
                removed = before - con.execute(f"SELECT count(*) FROM {q(t.name)}").fetchone()[0]
            n, cols = profile_table(con, t.name, t.columns)
            profiles[t.name] = cols
            rows[t.name] = n
            sources[t.name] = t.source
            info[t.name] = {
                "skipped_lines": t.skipped_lines, "header_row": t.header_row, "dropped_empty_rows": t.dropped_empty_rows,
                "unparsed": {c.name: c.unparsed for c in t.columns if c.unparsed}, "deduped": removed,
            }
    rels = find_relationships(con, profiles, rows) if len(profiles) > 1 else []
    readiness = assess(con, profiles, rows, info, rels, get_settings().min_rows)
    for e in errors:
        readiness["issues"].insert(0, {"id": f"read_{e['file']}", "severity": "block" if not profiles else "warn",
                                       "title": f"Couldn't read {e['file']}", "detail": e["error"], "suggestion": "",
                                       "table": "", "column": "", "fix": None})
    if errors and not profiles:
        readiness["status"] = "block"
    st.update({
        "profiles": {t: [c.to_dict() for c in cols] for t, cols in profiles.items()},
        "rows": rows, "ingest": info, "sources": sources, "readiness": readiness,
        "scopes": None, "dashboards": {}, "ingested": time.time(),
    })
    ds.save()
    return readiness


def apply_setup(ds, setup: dict) -> list[dict]:
    st = ds.state
    st["setup"] = setup
    scopes = build_scopes(ds.con, st, setup)
    st["scopes"] = scopes
    st["dashboards"] = {}
    ds.save()
    return scopes


def get_scope(ds, scope_id: str | None) -> dict:
    scopes = ds.state.get("scopes") or []
    if not scopes:
        raise RecipeError("Confirm the data setup first")
    if not scope_id:
        return scopes[0]
    for s in scopes:
        if s["id"] == scope_id:
            return s
    raise RecipeError(f"Unknown analysis scope {scope_id}")


async def generate_dashboard(ds, scope_id: str | None) -> dict:
    scope = get_scope(ds, scope_id)
    setup = ds.state.get("setup") or {}
    found = discover(ds, scope, setup.get("goal", ""))
    cands = found["candidates"]
    low_conf = scope["rows"] < get_settings().min_rows
    story = await compose(scope, cands, found["default"], setup.get("goal", ""), setup.get("audience", ""), low_conf)
    for pid, t in (story.pop("panel_titles", None) or {}).items():
        for c in cands:
            if c["id"] == pid:
                c["computed_title"] = c["title"]
                c["title"] = t
    used = set(story["kpis"]) | {p for s in story["sections"] for p in s["panels"]}
    if story["headline"].get("panel"):
        used.add(story["headline"]["panel"])
    panels = {c["id"]: c for c in cands}
    dash = {
        "scope": scope_id or scope["id"],
        "story": story,
        "panels": panels,
        "unused": [c["id"] for c in cands if c["id"] not in used],
        "generated": time.time(),
        "low_confidence": low_conf,
        "meta": dashboard_meta(ds, scope),
        "next_id": len(cands) + 1,
    }
    ds.state.setdefault("dashboards", {})[scope["id"]] = dash
    ds.save()
    return dash


def dashboard_meta(ds, scope: dict) -> dict:
    st = ds.state
    files = [f for f in st.get("files", []) if set(f.get("tables") or []) & set(scope["tables"])]
    return {
        "scope_label": scope["label"],
        "rows": scope["rows"],
        "files": [{"name": f["name"], "size": f["size"], "uploaded": f["uploaded"]} for f in files],
        "joins": scope.get("joins") or [],
        "time": scope.get("time"),
        "goal": (st.get("setup") or {}).get("goal", ""),
        "audience": (st.get("setup") or {}).get("audience", ""),
        "columns": scope["columns"],
    }


def recompute(ds, scope_id: str, filters: list) -> dict:
    """Recompute every panel of a dashboard under the given filters (computed titles)."""
    scope = get_scope(ds, scope_id)
    dash = ds.state["dashboards"][scope["id"]]
    ctx = Ctx(ds, scope, filters)
    out = {}
    for pid, p in dash["panels"].items():
        try:
            np = compile_panel(ctx, p["recipe"])
        except Exception as err:
            out[pid] = {**p, "error": str(err)}
            continue
        np.update({"id": pid, "score": p.get("score", 0)})
        if not filters and p.get("title") and p.get("computed_title"):
            np["title"] = p["title"]
        if p.get("pinned_question"):
            np["pinned_question"] = p["pinned_question"]
        out[pid] = np
    return out
