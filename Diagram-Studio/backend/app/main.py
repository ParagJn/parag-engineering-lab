from __future__ import annotations

import asyncio
import re
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import get_settings
from .extract import ALLOWED_SUFFIXES, extract_text, truncate_for_llm
from .llm import IcaLLM, LLMError
from .anim import default_plan, describe, finalize, is_static, sanitize_plan
from .prompts import ANIM_SYSTEM, DIAGRAM_SYSTEM, PLAN_SYSTEM, anim_prompt, diagram_prompt, plan_prompt
from .spec import normalize_type, sanitize
from .store import ProjectStore

app = FastAPI(title="Diagram Studio API")
settings = get_settings()
llm = IcaLLM(settings)
store = ProjectStore(settings.db_path)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5250", "http://127.0.0.1:5250"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/status")
def status() -> dict:
    """Lets the UI warn up front when IBM ICA credentials are missing."""
    return {
        "configured": llm.configured,
        "model": settings.ibm_ica_model_id,
        "max_upload_mb": settings.max_upload_mb,
        "accepted": sorted(ALLOWED_SUFFIXES),
        "max_diagrams": settings.max_diagrams,
    }


async def _read_upload(upload: UploadFile) -> bytes:
    name = upload.filename or ""
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{suffix or name}'. Use .md, .txt or .docx.")
    limit = settings.max_upload_mb * 1024 * 1024
    chunks: list[bytes] = []
    written = 0
    while chunk := await upload.read(1024 * 1024):
        written += len(chunk)
        if written > limit:
            raise HTTPException(status_code=413, detail=f"The file is larger than {settings.max_upload_mb} MB.")
        chunks.append(chunk)
    if written == 0:
        raise HTTPException(status_code=400, detail="The file is empty.")
    return b"".join(chunks)


@app.post("/api/plan")
async def plan(file: UploadFile | None = File(None), text: str = Form("")) -> dict:
    """Read the document and decide which diagrams it supports. Returns the text used so later calls can reuse it."""
    if not llm.configured:
        raise HTTPException(status_code=503, detail="IBM ICA is not configured. Set IBM_ICA_ENDPOINT and IBM_ICA_API_KEY in backend/.env and restart.")

    source_name = "Pasted text"
    if file is not None and file.filename:
        source_name = file.filename
        data = await _read_upload(file)
        try:
            document = await asyncio.to_thread(extract_text, source_name, data)
        except Exception as err:
            raise HTTPException(status_code=400, detail=f"Could not read '{source_name}'. {err}") from err
    else:
        document = text.strip()
    if len(document) < 40:
        raise HTTPException(status_code=422, detail="There is not enough text to draw from. Paste or upload a longer document.")

    document, truncated = truncate_for_llm(document, settings.max_chars_for_llm)
    try:
        result, model = await llm.complete_json(PLAN_SYSTEM, plan_prompt(document, settings.max_diagrams), settings.plan_max_output_tokens)
    except LLMError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err

    diagrams = []
    raw_items = result.get("diagrams")
    for index, raw in enumerate(raw_items if isinstance(raw_items, list) else []):
        if not isinstance(raw, dict):
            continue
        diagrams.append(
            {
                "id": f"d{index + 1}",
                "type": normalize_type(raw.get("type")),
                "title": re.sub(r"\s+", " ", str(raw.get("title") or "")).strip()[:80] or f"Diagram {index + 1}",
                "summary": re.sub(r"\s+", " ", str(raw.get("summary") or "")).strip()[:300],
                "focus": re.sub(r"\s+", " ", str(raw.get("focus") or "")).strip()[:500],
            }
        )
    diagrams = diagrams[: settings.max_diagrams]

    title = re.sub(r"\s+", " ", str(result.get("document_title") or "")).strip()[:100] or Path(source_name).stem or "Document"

    # Saved before any diagram is drawn, so closing the tab mid-run keeps the project. A failed save must not cost the user the plan.
    project_id = None
    try:
        project_id = await asyncio.to_thread(
            store.create, title=title, source_name=source_name, text=document, truncated=truncated, model=model, diagrams=diagrams
        )
    except Exception:
        pass
    return {
        "id": project_id,
        "saved": project_id is not None,
        "source_name": source_name,
        "title": title,
        "text": document,
        "chars": len(document),
        "truncated": truncated,
        "diagrams": diagrams,
        "model": model,
    }


class PlanItem(BaseModel):
    id: str = Field(max_length=40)
    type: str = Field(max_length=40)
    title: str = Field(default="", max_length=120)
    summary: str = Field(default="", max_length=400)
    focus: str = Field(default="", max_length=600)


class DiagramRequest(BaseModel):
    text: str = Field(min_length=1)
    item: PlanItem
    # Optional plain-language change to apply when redrawing, e.g. "split the backend into two groups"
    instruction: str = Field(default="", max_length=500)
    # When set, the finished diagram is saved into this project
    project_id: str = Field(default="", max_length=64)


@app.post("/api/diagram")
async def diagram(request: DiagramRequest) -> dict:
    """Draw one diagram from the document as a validated spec."""
    kind = normalize_type(request.item.type)
    item = {**request.item.model_dump(), "type": kind}
    if request.instruction.strip():
        item["focus"] = f"{item['focus']}\nAlso apply this change requested by the user: {request.instruction.strip()}".strip()
    try:
        raw, model = await llm.complete_json(DIAGRAM_SYSTEM, diagram_prompt(request.text, item), settings.diagram_max_output_tokens)
        spec = sanitize(raw, kind, item["title"] or "Diagram")
    except LLMError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err
    except ValueError as err:
        raise HTTPException(status_code=422, detail=f"The model's diagram could not be used. {err} Try drawing it again.") from err

    saved = False
    if request.project_id:
        try:
            saved = await asyncio.to_thread(store.save_spec, request.project_id, item["id"], spec)
        except Exception:
            saved = False
    return {"id": item["id"], "spec": spec, "model": model, "saved": saved}


class ElementRef(BaseModel):
    id: str = Field(max_length=60)
    label: str = Field(default="", max_length=80)
    # True for the diagram's own highlighted parts (what a plain "pulse" lands on)
    focal: bool = False


class AnimationRequest(BaseModel):
    type: str = Field(max_length=40)
    title: str = Field(default="", max_length=120)
    # What the user asked for, in their own words. Empty means "build the best animation for this diagram".
    instruction: str = Field(default="", max_length=500)
    # Parts of the diagram the user may single out ("make the database pulse")
    elements: list[ElementRef] = Field(default_factory=list, max_length=40)


@app.post("/api/animation")
async def animation(request: AnimationRequest) -> dict:
    """Turn a request (or nothing) into an animation plan. The browser renders the plan; no drawing happens here."""
    kind = normalize_type(request.type)
    instruction = request.instruction.strip()
    note = ""
    model = None
    elements = [e.model_dump() for e in request.elements]

    if not instruction:
        plan = default_plan(kind)
    else:
        try:
            raw, model = await llm.complete_json(
                ANIM_SYSTEM, anim_prompt(kind, request.title, instruction, elements), settings.animation_max_output_tokens
            )
        except LLMError as err:
            raise HTTPException(status_code=502, detail=str(err)) from err
        plan = sanitize_plan(raw, kind, {e["id"] for e in elements})
        note = " ".join(str(raw.get("note") or "").split())[:200]
        if is_static(plan):
            plan = default_plan(kind)
            note = note or "That would have produced no animation, so the best default was used instead."

    adjusted = finalize(plan, any(e["focal"] for e in elements))
    if adjusted and instruction and not note:
        note = adjusted
    plan["summary"] = describe(plan, kind)
    return {"plan": plan, "note": note, "model": model}


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


@app.get("/api/projects")
def list_projects(q: str = "") -> dict:
    return {"items": store.list(q)}


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict:
    project = store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found. It may have been deleted.")
    return project


@app.patch("/api/projects/{project_id}")
def rename_project(project_id: str, request: RenameRequest) -> dict:
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Title cannot be empty.")
    if not store.rename(project_id, title):
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"id": project_id, "title": title}


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str) -> dict:
    if not store.delete(project_id):
        raise HTTPException(status_code=404, detail="Project not found.")
    return {"ok": True}
