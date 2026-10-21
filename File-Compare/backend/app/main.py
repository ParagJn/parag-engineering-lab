from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .compare import build_prompt, quick_section_diff, quick_text_diff, report_title
from .config import get_settings
from .diffview import build_diff
from .documents import (
    ALLOWED_SUFFIXES,
    extract_document,
    image_media_type,
    is_image,
    split_markdown_sections,
    truncate_for_llm,
)
from .llm import IcaLLM, LLMError
from .store import ComparisonStore

app = FastAPI(title="File Compare API")
settings = get_settings()
llm = IcaLLM(settings)
store = ComparisonStore(settings.db_path)
PREVIEW_CHARS = 5000

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5240", "http://127.0.0.1:5240"],
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
    }


class RenameRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


def _with_preview(item: dict) -> dict:
    texts = store.texts(item["id"])
    text_a, text_b = texts if texts else ("", "")
    return {**item, "preview": {"a": text_a[:PREVIEW_CHARS], "b": text_b[:PREVIEW_CHARS]}}


def _require(comparison_id: str) -> dict:
    item = store.get(comparison_id)
    if not item:
        raise HTTPException(status_code=404, detail="Comparison not found. It may have been deleted.")
    return item


@app.get("/api/comparisons")
def list_comparisons(q: str = "") -> dict:
    return {"items": store.list(q)}


@app.get("/api/comparisons/{comparison_id}")
def get_comparison(comparison_id: str) -> dict:
    return _with_preview(_require(comparison_id))


@app.patch("/api/comparisons/{comparison_id}")
def rename_comparison(comparison_id: str, request: RenameRequest) -> dict:
    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Title cannot be empty.")
    if not store.rename(comparison_id, title):
        raise HTTPException(status_code=404, detail="Comparison not found.")
    return {"id": comparison_id, "title": title}


@app.delete("/api/comparisons/{comparison_id}")
def delete_comparison(comparison_id: str) -> dict:
    if not store.delete(comparison_id):
        raise HTTPException(status_code=404, detail="Comparison not found.")
    return {"ok": True}


@app.get("/api/comparisons/{comparison_id}/diff")
def comparison_diff(comparison_id: str) -> dict:
    texts = store.texts(comparison_id)
    if not texts:
        raise HTTPException(status_code=404, detail="Comparison not found.")
    return build_diff(*texts)


async def _read_upload(upload: UploadFile, label: str) -> bytes:
    name = upload.filename or ""
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail=f"{label}: unsupported file type '{suffix or name}'. Use PDF, DOCX, PNG, JPG or WEBP.")
    limit = settings.max_upload_mb * 1024 * 1024
    chunks: list[bytes] = []
    written = 0
    while chunk := await upload.read(1024 * 1024):
        written += len(chunk)
        if written > limit:
            raise HTTPException(status_code=413, detail=f"{label} is larger than {settings.max_upload_mb} MB.")
        chunks.append(chunk)
    if written == 0:
        raise HTTPException(status_code=400, detail=f"{label} is empty.")
    return b"".join(chunks)


async def _extract(label: str, name: str, data: bytes) -> dict[str, Any]:
    """Turn one upload into text + sections. Images go through the vision model first."""
    if is_image(name):
        try:
            markdown = await llm.image_to_markdown(data, image_media_type(name))
        except LLMError as err:
            raise HTTPException(status_code=502, detail=f"{label}: image could not be read. {err}") from err
        sections = split_markdown_sections(markdown)
        return {"text": markdown, "sections": sections, "units": len(sections), "units_label": "sections", "type": "image-markdown"}
    try:
        return await asyncio.to_thread(
            extract_document,
            name,
            data,
            markers=True,
            max_pages=settings.max_pdf_pages,
            paragraphs_per_section=settings.docx_paragraphs_per_section,
        )
    except Exception as err:
        raise HTTPException(status_code=400, detail=f"{label}: could not read '{name}'. {err}") from err


@app.post("/api/compare")
async def compare(file_a: UploadFile = File(...), file_b: UploadFile = File(...)) -> dict:
    if not llm.configured:
        raise HTTPException(status_code=503, detail="IBM ICA is not configured. Set IBM_ICA_ENDPOINT and IBM_ICA_API_KEY in backend/.env and restart.")

    name_a = file_a.filename or "File A"
    name_b = file_b.filename or "File B"
    data_a = await _read_upload(file_a, "File A")
    data_b = await _read_upload(file_b, "File B")

    a, b = await asyncio.gather(_extract("File A", name_a, data_a), _extract("File B", name_b, data_b))
    if not a["text"].strip() or not b["text"].strip():
        raise HTTPException(
            status_code=422,
            detail="Could not extract text from one or both files. Scanned PDFs need OCR; try uploading the pages as images instead.",
        )

    top_n = settings.summary_top_n
    quick_diff = await asyncio.to_thread(quick_text_diff, a["text"], b["text"], top_n)
    section_diff = await asyncio.to_thread(quick_section_diff, a["sections"], b["sections"], top_n)

    text_a, truncated_a = truncate_for_llm(a["text"], settings.max_chars_for_llm)
    text_b, truncated_b = truncate_for_llm(b["text"], settings.max_chars_for_llm)
    prompt = build_prompt(
        name_a=name_a,
        name_b=name_b,
        type_a=a["type"],
        type_b=b["type"],
        text_a=text_a,
        text_b=text_b,
        quick_diff=quick_diff,
        section_diff=section_diff,
        report_style=settings.report_style,
    )
    try:
        report, model = await llm.report(prompt)
    except LLMError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err

    result = {
        "report": report,
        "report_title": report_title(a["type"], b["type"]),
        "model": model,
        "files": {
            "a": {"name": name_a, "type": a["type"], "units": a["units"], "units_label": a["units_label"], "chars": len(a["text"]), "truncated": truncated_a},
            "b": {"name": name_b, "type": b["type"], "units": b["units"], "units_label": b["units_label"], "chars": len(b["text"]), "truncated": truncated_b},
        },
        "stats": {
            "line_similarity": quick_diff["similarity_ratio"],
            "section_similarity": section_diff["section_similarity_avg"],
            "missing_sections": section_diff["missing_in_a"] + section_diff["missing_in_b"],
            "added_lines": quick_diff["added_lines_estimate"],
            "removed_lines": quick_diff["removed_lines_estimate"],
            "replaced_lines": quick_diff["replaced_lines_estimate"],
        },
        "section_differences": section_diff["top_section_differences"],
        "line_changes": quick_diff["top_changes"],
    }

    # Saving must never cost the user a finished (and paid-for) report.
    try:
        saved = await asyncio.to_thread(store.save, name_a=name_a, name_b=name_b, result=result, text_a=a["text"], text_b=b["text"])
        return {**saved, "saved": True, "preview": {"a": a["text"][:PREVIEW_CHARS], "b": b["text"][:PREVIEW_CHARS]}}
    except Exception:
        return {
            **result,
            "id": None,
            "title": f"{name_a} vs {name_b}",
            "saved": False,
            "preview": {"a": a["text"][:PREVIEW_CHARS], "b": b["text"][:PREVIEW_CHARS]},
        }
