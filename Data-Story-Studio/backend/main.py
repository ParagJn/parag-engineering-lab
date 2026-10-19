"""Data Story Studio API.

Flow: upload files -> readiness report -> setup (goal, links) -> dashboard -> explore / ask / redraw / export
"""

import json
import re
import shutil
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from config import get_settings
import brief
import deck
import maps
from export import ExportError, build_html, build_pdf, print_pdf, safe_filename
from panels import Ctx, RecipeError, compile_panel
from pipeline import apply_setup, dashboard_meta, generate_dashboard, get_scope, ingest_all, recompute
import history
from story import ask, llm_ready, redraw, setup_brief
from workspace import QueryError, registry, validate_select

app = FastAPI(title="Data Story Studio")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5190", "http://127.0.0.1:5190"],
                   allow_methods=["*"], allow_headers=["*"])

ALLOWED = {".csv", ".tsv", ".txt", ".xlsx", ".xlsm", ".xls"}


def _ds(ds_id: str):
    try:
        return registry.get(ds_id)
    except KeyError:
        raise HTTPException(404, "Dataset not found")


def _fail(err: Exception, code: int = 400):
    raise HTTPException(code, str(err))


def _summary(ds) -> dict:
    st = ds.state
    return {
        "id": ds.id,
        "files": st.get("files", []),
        "readiness": st.get("readiness"),
        "profiles": st.get("profiles"),
        "rows": st.get("rows"),
        "sources": st.get("sources"),
        "brief": st.get("brief"),
        "setup": st.get("setup"),
        "scopes": [{k: s[k] for k in ("id", "label", "rows", "tables", "joins", "time")} for s in st.get("scopes") or []],
        "dashboards": list((st.get("dashboards") or {}).keys()),
        "min_rows": get_settings().min_rows,
        "example": bool(st.get("example")),
    }


@app.get("/api/health")
def health():
    return {"ok": True, "llm": llm_ready(), "model": get_settings().ibm_ica_model_id if llm_ready() else None,
            "min_rows": get_settings().min_rows}


@app.get("/api/geo/{key}")
def geo_boundaries(key: str):
    """Map boundaries (GeoJSON) for map panels; static, so the browser may cache them."""
    try:
        geo = maps.boundaries(key)
    except KeyError:
        raise HTTPException(404, "Unknown map")
    return Response(json.dumps(geo, separators=(",", ":")), media_type="application/json",
                    headers={"Cache-Control": "public, max-age=86400"})


@app.get("/api/datasets")
def list_datasets():
    return registry.list()


@app.post("/api/datasets")
async def create_dataset(files: list[UploadFile] = File(...)):
    ds = registry.create()
    try:
        await _store(ds, files)
        with ds.lock:
            ingest_all(ds)
    except HTTPException:
        registry.delete(ds.id)
        raise
    ds.state["brief"] = await setup_brief(ds.state)
    ds.save()
    return _summary(ds)


EXAMPLE_FILES = ["orders.csv", "products.csv", "stores.xlsx", "feedback.csv"]
EXAMPLE_BRIEF = {
    "purpose": "Guided example: two years of orders from Brightleaf Coffee Co., a fictional six-store coffee chain.",
    "files": {
        "orders": "One row per order: when, which store and product, sales channel, quantity, discount and revenue.",
        "products": "The menu: product name, category and list price.",
        "stores": "The six stores: name, Australian state, area and format (Excel file).",
        "feedback": "Customer survey answers for about a third of orders: rating, wait time and whether they'd recommend us.",
    },
    "goal_suggestions": [
        "How are sales growing, and which channels and stores drive it?",
        "What makes customers rate us lower?",
        "When are our busiest hours, and how long do people wait?",
    ],
}


@app.post("/api/example")
def create_example():
    """Load the built-in guided example (data/Example) as a fresh dataset."""
    src = get_settings().data_dir / "Example"
    missing = [f for f in EXAMPLE_FILES if not (src / f).exists()]
    if missing:
        raise HTTPException(500, f"Example data missing ({', '.join(missing)}). Run: python scripts/make_example.py")
    ds = registry.create()
    ds.state["files"] = []
    for name in EXAMPLE_FILES:
        stored = f"example_{name}"
        shutil.copy(src / name, ds.files_dir / stored)
        ds.state["files"].append({"name": name, "stored": stored, "size": (src / name).stat().st_size, "uploaded": time.time()})
    ds.state["example"] = True
    with ds.lock:
        ingest_all(ds)
    ds.state["brief"] = EXAMPLE_BRIEF
    ds.save()
    return _summary(ds)


@app.post("/api/datasets/{ds_id}/files")
async def add_files(ds_id: str, files: list[UploadFile] = File(...)):
    ds = _ds(ds_id)
    await _store(ds, files)
    with ds.lock:
        ingest_all(ds)
    ds.state["brief"] = await setup_brief(ds.state)
    ds.save()
    return _summary(ds)


@app.delete("/api/datasets/{ds_id}/files/{stored}")
def remove_file(ds_id: str, stored: str):
    ds = _ds(ds_id)
    files = ds.state.get("files", [])
    match = next((f for f in files if f["stored"] == stored), None)
    if not match:
        raise HTTPException(404, "File not found")
    (ds.files_dir / match["stored"]).unlink(missing_ok=True)
    ds.state["files"] = [f for f in files if f is not match]
    with ds.lock:
        ingest_all(ds)
    return _summary(ds)


async def _store(ds, files: list[UploadFile]):
    limit = get_settings().max_upload_mb * 1024 * 1024
    ds.state.setdefault("files", [])
    for up in files:
        name = Path(up.filename or "file").name
        ext = Path(name).suffix.lower()
        if ext not in ALLOWED:
            raise HTTPException(400, f"{name}: only CSV and Excel files are supported")
        stored = f"{uuid.uuid4().hex[:8]}_{re.sub(r'[^A-Za-z0-9._-]+', '_', name)}"
        dest = ds.files_dir / stored
        size = 0
        with dest.open("wb") as fh:
            while chunk := await up.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    fh.close()
                    dest.unlink(missing_ok=True)
                    raise HTTPException(413, f"{name} is larger than {get_settings().max_upload_mb} MB")
                fh.write(chunk)
        if size == 0:
            dest.unlink(missing_ok=True)
            raise HTTPException(400, f"{name} is empty")
        ds.state["files"].append({"name": name, "stored": stored, "size": size, "uploaded": time.time()})


@app.get("/api/datasets/{ds_id}")
def get_dataset(ds_id: str):
    return _summary(_ds(ds_id))


@app.delete("/api/datasets/{ds_id}")
def delete_dataset(ds_id: str):
    _ds(ds_id)
    registry.delete(ds_id)
    return {"ok": True}


@app.get("/api/datasets/{ds_id}/tables/{table}/preview")
def preview_table(ds_id: str, table: str, offset: int = 0, limit: int = 100, sort: str = "", desc: bool = False, search: str = ""):
    """A page of an ingested table as it will be analysed (typed, cleaned), for the data previewer."""
    ds = _ds(ds_id)
    cols = (ds.state.get("profiles") or {}).get(table)
    if cols is None:
        raise HTTPException(404, "Unknown table")
    names = [c["name"] for c in cols]
    if sort and sort not in names:
        raise HTTPException(400, f"Unknown column {sort}")
    qt = lambda n: '"' + n.replace('"', '""') + '"'
    where, params = "", []
    if search.strip():
        where = "WHERE concat_ws(' ', " + ", ".join(f"CAST({qt(n)} AS VARCHAR)" for n in names) + ") ILIKE ?"
        params = [f"%{search.strip()}%"]
    order = f"ORDER BY {qt(sort)} {'DESC' if desc else 'ASC'} NULLS LAST" if sort else ""
    limit = max(1, min(limit, 500))
    try:
        total = ds.scalar(f"SELECT count(*) FROM {qt(table)} {where}", params)
        page = ds.query(f"SELECT * FROM {qt(table)} {where} {order} LIMIT {limit} OFFSET {max(0, offset)}", params, limit=limit)
    except QueryError as err:
        _fail(err)
    return {**page, "total": int(total), "offset": max(0, offset)}


class FixReq(BaseModel):
    action: str  # dedupe | date_format
    table: str
    column: str = ""
    format: str = ""


@app.post("/api/datasets/{ds_id}/fix")
def apply_fix(ds_id: str, req: FixReq):
    ds = _ds(ds_id)
    st = ds.state
    if req.table not in (st.get("profiles") or {}):
        raise HTTPException(400, "Unknown table")
    if req.action == "dedupe":
        st["dedupe"] = sorted(set(st.get("dedupe") or []) | {req.table})
    elif req.action == "date_format":
        if not req.column or not req.format.startswith("%"):
            raise HTTPException(400, "Column and format required")
        st.setdefault("overrides", {}).setdefault(req.table, {})[req.column] = {"date_format": req.format}
    else:
        raise HTTPException(400, "Unknown fix")
    with ds.lock:
        ingest_all(ds)
    return _summary(ds)


class Link(BaseModel):
    left: str
    left_col: str
    right: str
    right_col: str


class SetupReq(BaseModel):
    goal: str = ""
    audience: str = ""
    mode: str = "auto"  # auto | separate
    manual_links: list[Link] = Field(default_factory=list)
    rejected_links: list[dict] = Field(default_factory=list)
    override_low_volume: bool = False
    override_unlinked: bool = False


@app.post("/api/datasets/{ds_id}/setup")
def setup(ds_id: str, req: SetupReq):
    ds = _ds(ds_id)
    rd = ds.state.get("readiness") or {}
    blocks = {i["id"] for i in rd.get("issues", []) if i["severity"] == "block"}
    unresolved = set(blocks)
    if req.override_low_volume:
        unresolved.discard("low_volume")
    if req.mode == "separate" or req.manual_links or req.override_unlinked:
        unresolved.discard("unrelated_files")
    if unresolved:
        raise HTTPException(409, "Resolve the blocking readiness issues first: " + ", ".join(sorted(unresolved)))
    profiles = ds.state.get("profiles") or {}
    links = []
    for l in req.manual_links:
        for t, c in ((l.left, l.left_col), (l.right, l.right_col)):
            if t not in profiles or c not in {p["name"] for p in profiles[t]}:
                raise HTTPException(400, f"Unknown column {t}.{c}")
        lu = {p["name"]: p for p in profiles[l.left]}[l.left_col]
        ru = {p["name"]: p for p in profiles[l.right]}[l.right_col]
        card = {(False, True): "many-to-one", (True, False): "one-to-many", (True, True): "one-to-one",
                (False, False): "many-to-many"}[(lu["distinct"] == lu["count"], ru["distinct"] == ru["count"])]
        links.append({"kind": "join", "left": l.left, "left_col": l.left_col, "right": l.right, "right_col": l.right_col,
                      "cardinality": card, "confidence": "strong"})
    with ds.lock:
        scopes = apply_setup(ds, {**req.model_dump(exclude={"manual_links"}), "manual_links": links})
    return {**_summary(ds), "scopes": [{k: s[k] for k in ("id", "label", "rows", "tables", "joins", "time")} for s in scopes]}


@app.post("/api/datasets/{ds_id}/dashboards/{scope_id}")
async def make_dashboard(ds_id: str, scope_id: str):
    ds = _ds(ds_id)
    try:
        return await generate_dashboard(ds, scope_id)
    except (RecipeError, QueryError) as err:
        _fail(err)


@app.get("/api/datasets/{ds_id}/dashboards/{scope_id}")
def get_dashboard(ds_id: str, scope_id: str):
    ds = _ds(ds_id)
    dash = (ds.state.get("dashboards") or {}).get(scope_id)
    if not dash:
        raise HTTPException(404, "Dashboard not generated yet")
    return dash


class FilterReq(BaseModel):
    filters: list[dict] = Field(default_factory=list)


@app.post("/api/datasets/{ds_id}/dashboards/{scope_id}/filter")
def filter_dashboard(ds_id: str, scope_id: str, req: FilterReq):
    ds = _ds(ds_id)
    if scope_id not in (ds.state.get("dashboards") or {}):
        raise HTTPException(404, "Dashboard not generated yet")
    try:
        return {"panels": recompute(ds, scope_id, req.filters)}
    except (RecipeError, QueryError) as err:
        _fail(err)


class AskReq(BaseModel):
    question: str
    history: list[dict] = Field(default_factory=list)
    filters: list[dict] = Field(default_factory=list)
    session_id: str = ""


@app.post("/api/datasets/{ds_id}/dashboards/{scope_id}/ask")
async def ask_question(ds_id: str, scope_id: str, req: AskReq):
    ds = _ds(ds_id)
    scope = _scope(ds, scope_id)
    if not req.question.strip():
        raise HTTPException(400, "Ask a question")
    question = req.question.strip()
    result = await ask(ds, scope, question, req.history, req.filters)
    if history.valid_session(req.session_id):
        history.record(ds, req.session_id, scope_id, question, result)
    return result


@app.get("/api/datasets/{ds_id}/dashboards/{scope_id}/ask/sessions")
def ask_sessions(ds_id: str, scope_id: str):
    ds = _ds(ds_id)
    _scope(ds, scope_id)
    return {"sessions": history.sessions(ds, scope_id)}


@app.get("/api/datasets/{ds_id}/ask/sessions/{session_id}")
def ask_session(ds_id: str, session_id: str):
    if not history.valid_session(session_id):
        raise HTTPException(400, "Bad session id")
    return {"messages": history.messages(_ds(ds_id), session_id)}


@app.delete("/api/datasets/{ds_id}/ask/sessions/{session_id}")
def ask_session_delete(ds_id: str, session_id: str):
    if not history.valid_session(session_id):
        raise HTTPException(400, "Bad session id")
    history.delete_session(_ds(ds_id), session_id)
    return {"ok": True}


class RedrawReq(BaseModel):
    instruction: str = ""
    recipe: dict | None = None  # direct recipe edit (chart switch, grain) from the UI
    filters: list[dict] = Field(default_factory=list)


@app.post("/api/datasets/{ds_id}/dashboards/{scope_id}/panels/{panel_id}/redraw")
async def redraw_panel(ds_id: str, scope_id: str, panel_id: str, req: RedrawReq):
    ds = _ds(ds_id)
    scope = _scope(ds, scope_id)
    dash = ds.state["dashboards"].get(scope_id)
    if not dash or panel_id not in dash["panels"]:
        raise HTTPException(404, "Panel not found")
    old = dash["panels"][panel_id]
    try:
        if req.recipe:
            new = compile_panel(Ctx(ds, scope, req.filters), {**old["recipe"], **req.recipe})
        else:
            new = await redraw(ds, scope, old, req.instruction, req.filters)
    except (RecipeError, QueryError, KeyError, ValueError, TypeError) as err:
        _fail(err)
    new.update({"id": panel_id, "score": old.get("score", 0)})
    if not req.filters:
        new.setdefault("history", []).extend((old.get("history") or []) + [{k: old[k] for k in ("title", "recipe")}])
        new["history"] = new["history"][-5:]
        dash["panels"][panel_id] = new
        ds.save()
    return new


@app.post("/api/datasets/{ds_id}/dashboards/{scope_id}/panels/{panel_id}/undo")
def undo_panel(ds_id: str, scope_id: str, panel_id: str):
    ds = _ds(ds_id)
    scope = _scope(ds, scope_id)
    dash = ds.state["dashboards"].get(scope_id)
    p = (dash or {}).get("panels", {}).get(panel_id)
    if not p or not p.get("history"):
        raise HTTPException(400, "Nothing to undo")
    prev = p["history"][-1]
    new = compile_panel(Ctx(ds, scope), prev["recipe"], prev["title"])
    new.update({"id": panel_id, "score": p.get("score", 0), "history": p["history"][:-1]})
    dash["panels"][panel_id] = new
    ds.save()
    return new


class AddPanelReq(BaseModel):
    panel: dict  # a panel returned by /ask, pinned to the dashboard
    section: int = -1


@app.post("/api/datasets/{ds_id}/dashboards/{scope_id}/panels")
def add_panel(ds_id: str, scope_id: str, req: AddPanelReq):
    ds = _ds(ds_id)
    scope = _scope(ds, scope_id)
    dash = ds.state["dashboards"].get(scope_id)
    if not dash:
        raise HTTPException(404, "Dashboard not generated yet")
    recipe = req.panel.get("recipe") or {}
    try:
        if recipe.get("kind") == "sql":
            validate_select(ds.con, recipe.get("sql", ""))
        p = compile_panel(Ctx(ds, scope), recipe, req.panel.get("title", ""))
    except (RecipeError, QueryError) as err:
        _fail(err)
    pid = f"p{dash.get('next_id', len(dash['panels']) + 1)}"
    dash["next_id"] = int(pid[1:]) + 1
    p.update({"id": pid, "score": 0, "subtitle": req.panel.get("subtitle", p.get("subtitle", ""))})
    dash["panels"][pid] = p
    secs = dash["story"]["sections"]
    if not secs or req.section >= len(secs):
        secs.append({"role": "detail", "heading": "Your questions", "panels": []})
    target = secs[req.section] if 0 <= req.section < len(secs) else next(
        (s for s in secs if s["heading"] == "Your questions"), None)
    if target is None:
        target = {"role": "detail", "heading": "Your questions", "panels": []}
        secs.append(target)
    target["panels"].append(pid)
    ds.save()
    return dash


class LayoutReq(BaseModel):
    story: dict


@app.put("/api/datasets/{ds_id}/dashboards/{scope_id}/layout")
def save_layout(ds_id: str, scope_id: str, req: LayoutReq):
    """Persist edits to section order / headings / removed panels (no new numbers allowed)."""
    ds = _ds(ds_id)
    dash = ds.state["dashboards"].get(scope_id)
    if not dash:
        raise HTTPException(404, "Dashboard not generated yet")
    ids = set(dash["panels"])
    st = req.story
    for s in st.get("sections", []):
        s["panels"] = [p for p in s.get("panels", []) if p in ids]
    st["kpis"] = [k for k in st.get("kpis", []) if k in ids]
    dash["story"] = {**dash["story"], **{k: st[k] for k in ("sections", "kpis") if k in st}}
    ds.save()
    return dash


class SqlReq(BaseModel):
    sql: str


@app.post("/api/datasets/{ds_id}/dashboards/{scope_id}/sql")
def run_sql(ds_id: str, scope_id: str, req: SqlReq):
    """Run a user-edited SELECT (the 'view query' panel lets people tweak and re-run)."""
    ds = _ds(ds_id)
    _scope(ds, scope_id)
    try:
        return ds.query(validate_select(ds.con, req.sql), limit=1000)
    except QueryError as err:
        _fail(err)


class ExportReq(BaseModel):
    filters: list[dict] = Field(default_factory=list)
    panels: dict | None = None  # current (possibly filtered) panels from the UI


def _export_payload(ds, scope_id: str, req: ExportReq) -> tuple[dict, str]:
    dash = (ds.state.get("dashboards") or {}).get(scope_id)
    if not dash:
        raise HTTPException(404, "Dashboard not generated yet")
    scope = get_scope(ds, scope_id)
    panels = recompute(ds, scope_id, req.filters) if req.filters else dash["panels"]
    payload = {**dash, "panels": panels, "filters": req.filters, "meta": dashboard_meta(ds, scope),
               "exported": time.time(), "static": True, "geo": maps.used_boundaries(panels)}
    title = dash["story"]["headline"].get("title") or scope["label"]
    return payload, title


@app.post("/api/datasets/{ds_id}/dashboards/{scope_id}/export/html")
def export_html(ds_id: str, scope_id: str, req: ExportReq):
    ds = _ds(ds_id)
    payload, title = _export_payload(ds, scope_id, req)
    try:
        doc = build_html(payload, title)
    except ExportError as err:
        _fail(err, 500)
    return Response(doc, media_type="text/html",
                    headers={"Content-Disposition": f'attachment; filename="{safe_filename(title, "html")}"'})


@app.post("/api/datasets/{ds_id}/dashboards/{scope_id}/export/pdf")
async def export_pdf(ds_id: str, scope_id: str, req: ExportReq):
    ds = _ds(ds_id)
    payload, title = _export_payload(ds, scope_id, req)
    try:
        pdf = await build_pdf(build_html({**payload, "print": True}, title))
    except ExportError as err:
        _fail(err, 500)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{safe_filename(title, "pdf")}"'})


@app.get("/api/deck/themes")
def deck_themes():
    return deck.deck_options()


@app.post("/api/datasets/{ds_id}/dashboards/{scope_id}/export/pptx")
async def export_pptx(ds_id: str, scope_id: str, req: ExportReq, regenerate: bool = False,
                      design: str = deck.DEFAULT_DESIGN, palette: str = deck.DEFAULT_PALETTE):
    """Executive deck (5-7 slides) in the dashboard's theme; the slide plan is cached on the dashboard."""
    if design not in deck.DESIGNS:
        raise HTTPException(400, f"Unknown design '{design}'")
    if palette not in deck.PALETTES:
        raise HTTPException(400, f"Unknown palette '{palette}'")
    ds = _ds(ds_id)
    payload, title = _export_payload(ds, scope_id, req)
    dash = _dash(ds, scope_id)
    cached = bool(dash.get("deck_plan")) and not regenerate
    plan = await deck.deck_plan(dash, regenerate)
    if plan is not dash.get("deck_plan") or not cached:
        ds.save()
    try:
        data = deck.build_pptx(payload, plan, req.filters, design, palette)
    except Exception as err:
        print(f"[deck] build failed: {err!r}", flush=True)
        _fail(RuntimeError(f"Couldn't build the presentation ({err})"), 500)
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    headers={"Content-Disposition": f'attachment; filename="{safe_filename(title, "pptx")}"'})


def _dash(ds, scope_id: str) -> dict:
    dash = (ds.state.get("dashboards") or {}).get(scope_id)
    if not dash:
        raise HTTPException(404, "Dashboard not generated yet")
    return dash


@app.post("/api/datasets/{ds_id}/dashboards/{scope_id}/summary")
async def exec_summary(ds_id: str, scope_id: str, regenerate: bool = False):
    """Executive commentary for the dashboard; cached on it, so reopening doesn't call the model."""
    ds = _ds(ds_id)
    dash = _dash(ds, scope_id)
    cached = bool(dash.get("exec_summary")) and not regenerate
    summary = await brief.executive_summary(dash, regenerate)
    if not cached:
        ds.save()
    return summary


@app.get("/api/datasets/{ds_id}/dashboards/{scope_id}/summary/{kind}")
async def exec_summary_file(ds_id: str, scope_id: str, kind: str):
    ds = _ds(ds_id)
    s = _dash(ds, scope_id).get("exec_summary")
    if not s:
        raise HTTPException(404, "Generate the executive summary first")
    if kind == "md":
        return Response(brief.to_markdown(s), media_type="text/markdown; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{brief.filename(s, "md")}"'})
    if kind != "pdf":
        raise HTTPException(400, "Unknown format")
    try:
        pdf = await print_pdf(brief.to_html(s))
    except ExportError as err:
        _fail(err, 500)
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{brief.filename(s, "pdf")}"'})


def _scope(ds, scope_id: str) -> dict:
    try:
        return get_scope(ds, scope_id)
    except RecipeError as err:
        raise HTTPException(400, str(err))
