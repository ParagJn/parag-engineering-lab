from __future__ import annotations

import asyncio
import shutil
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .analyzer import analyze_document, chat_about_analysis
from .config import get_settings
from .document_parser import extract_images, parse_document
from .llm_clients import SapCompletionAgent
from .visuals import create_visual_summary


app = FastAPI(title="Strategy Analyzer API")
settings = get_settings()
documents: dict[str, dict] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    document_id: str
    mode: str
    prompt: str = ""
    thinking_mode: bool = True


class ChatRequest(BaseModel):
    document_id: str
    analysis: str
    question: str


class VisualRequest(BaseModel):
    analysis: str


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/models/sap")
async def sap_models() -> dict:
    agent = SapCompletionAgent(settings, name="SAP Model Discovery", model=settings.sap_anthropic_model)
    return await agent.list_models()


async def _enrich_with_images(parsed: dict, path: Path) -> None:
    """Extract images from the document, describe each via Anthropic vision, and
    append the markdown descriptions to parsed["text"] in-place."""
    images = extract_images(path)
    if not images:
        return
    vision_agent = SapCompletionAgent(
        settings,
        name="Anthropic Image Analyst",
        model=settings.sap_anthropic_model,
        thinking=False,
    )
    if not vision_agent.configured:
        return

    async def _safe_describe(img: dict) -> str:
        try:
            return await vision_agent.describe_image(
                img["data"], img["media_type"], img["location"]
            )
        except Exception:
            return ""

    descriptions = await asyncio.gather(*[_safe_describe(img) for img in images])

    image_sections: list[str] = []
    for img, desc in zip(images, descriptions):
        if desc:
            image_sections.append(
                f"\n\n---\n**[IMAGE: {img['location']}]**\n\n{desc}\n\n---"
            )

    if image_sections:
        parsed["text"] = parsed["text"] + "\n" + "".join(image_sections)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx", ".pptx"}:
        raise HTTPException(status_code=400, detail="Upload a .pdf, .docx, or .pptx document.")
    document_id = str(uuid.uuid4())
    safe_name = f"{document_id}{suffix}"
    target = settings.upload_path / safe_name
    with target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    try:
        parsed = parse_document(target)
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Could not parse document: {exc}") from exc

    # Enrich document text with Anthropic-generated image descriptions
    await _enrich_with_images(parsed, target)

    documents[document_id] = {
        "id": document_id,
        "filename": file.filename,
        "path": str(target),
        "parsed": parsed,
    }
    return {
        "document_id": document_id,
        "filename": file.filename,
        "kind": parsed["kind"],
        "pages": parsed["pages"][:40],
        "preview_url": f"/api/documents/{document_id}/file",
        "characters": len(parsed["text"]),
    }


@app.get("/api/documents/{document_id}/file")
def get_file(document_id: str):
    item = documents.get(document_id)
    if not item:
        raise HTTPException(status_code=404, detail="Document not found")
    return FileResponse(item["path"], filename=item["filename"])


@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest) -> dict:
    item = documents.get(request.document_id)
    if not item:
        raise HTTPException(status_code=404, detail="Document not found")
    return await analyze_document(settings, request.mode, request.prompt, item["parsed"]["text"], request.thinking_mode)


@app.post("/api/chat")
async def chat(request: ChatRequest) -> dict:
    item = documents.get(request.document_id)
    if not item:
        raise HTTPException(status_code=404, detail="Document not found")
    return await chat_about_analysis(settings, request.question, item["parsed"]["text"], request.analysis)


@app.post("/api/visual")
async def visual(request: VisualRequest) -> dict:
    path = create_visual_summary(settings, request.analysis)
    return {"url": f"/api/visual/{path.name}", "filename": path.name}


@app.get("/api/visual/{filename}")
def get_visual(filename: str):
    path = settings.upload_path / "visuals" / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Visual not found")
    return FileResponse(path, media_type="image/png", filename=filename)
