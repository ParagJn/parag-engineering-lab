from __future__ import annotations

import asyncio
import uuid
from collections import OrderedDict
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .analyzer import analyze_document, chat_about_analysis
from .config import get_settings
from .document_parser import build_text, extract_images, parse_document
from .llm_clients import SapCompletionAgent, build_provider_agents, normalize_provider
from .visuals import create_visual_summary


app = FastAPI(title="Strategy Analyzer API")
settings = get_settings()

# In-memory store, capped so a long-running server doesn't grow without bound.
MAX_DOCUMENTS = 50
documents: "OrderedDict[str, dict]" = OrderedDict()

IMAGE_CONCURRENCY = 4
IMAGE_TIMEOUT_SECONDS = 90
ALLOWED_SUFFIXES = {".pdf", ".docx", ".pptx"}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5220", "http://127.0.0.1:5220"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    document_id: str
    mode: str
    prompt: str = ""
    thinking_mode: bool = True
    provider: str = "ibm_ica"


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    document_id: str
    analysis: str
    question: str = Field(min_length=1)
    history: list[ChatMessage] = []
    provider: str = "ibm_ica"


class VisualRequest(BaseModel):
    analysis: str


def _get_document(document_id: str) -> dict:
    item = documents.get(document_id)
    if not item:
        raise HTTPException(status_code=404, detail="Document not found (the server may have restarted - please upload again).")
    documents.move_to_end(document_id)
    return item


def _remember(item: dict) -> None:
    documents[item["id"]] = item
    while len(documents) > MAX_DOCUMENTS:
        _, old = documents.popitem(last=False)
        Path(old["path"]).unlink(missing_ok=True)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/providers")
def providers() -> dict:
    """Which providers have credentials, so the UI can flag unconfigured ones."""
    ica = bool(settings.ibm_ica_endpoint and settings.ibm_ica_api_key)
    sap = bool(settings.sap_client_id and settings.sap_client_secret and settings.sap_token_url and settings.sap_api_url)
    return {"ibm_ica": ica, "sap": sap}


@app.get("/api/models/sap")
async def sap_models() -> dict:
    agent = SapCompletionAgent(settings, name="SAP Model Discovery", model=settings.sap_anthropic_model)
    try:
        return await agent.list_models()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


async def _enrich_with_images(parsed: dict, path: Path, provider: str) -> int:
    """Describe embedded images with a vision model and attach each description to its page.

    Bounded: at most `max_images_per_document` images, a few concurrent calls, a timeout per call.
    Failures are silent per image - the text analysis never depends on them.
    """
    images = await asyncio.to_thread(extract_images, path)
    if not images:
        return 0
    images = images[: settings.max_images_per_document]
    vision_agent = build_provider_agents(settings, provider)["vision"]
    if not vision_agent.configured:
        return 0

    semaphore = asyncio.Semaphore(IMAGE_CONCURRENCY)

    async def _describe(img: dict) -> tuple[int, str]:
        async with semaphore:
            try:
                desc = await asyncio.wait_for(
                    vision_agent.describe_image(img["data"], img["media_type"], img["location"]),
                    timeout=IMAGE_TIMEOUT_SECONDS,
                )
            except Exception:
                return img["page"], ""
        return img["page"], desc

    described = 0
    pages_by_number = {p["number"]: p for p in parsed["pages"]}
    for page_number, desc in await asyncio.gather(*[_describe(img) for img in images]):
        page = pages_by_number.get(page_number)
        if desc and page is not None:
            page.setdefault("images", []).append(desc)
            described += 1
    if described:
        parsed["text"] = build_text(parsed["kind"], parsed["pages"])
    return described


@app.post("/api/upload")
async def upload(file: UploadFile = File(...), provider: str = Form("ibm_ica")) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=400, detail="Upload a .pdf, .docx, or .pptx document.")
    provider = normalize_provider(provider)
    document_id = str(uuid.uuid4())
    target = settings.upload_path / f"{document_id}{suffix}"

    limit = settings.max_upload_mb * 1024 * 1024
    written = 0
    try:
        with target.open("wb") as handle:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > limit:
                    raise HTTPException(status_code=413, detail=f"File is larger than {settings.max_upload_mb} MB.")
                handle.write(chunk)
        if written == 0:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")
        try:
            parsed = await asyncio.to_thread(parse_document, target)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Could not parse document: {exc}") from exc
    except HTTPException:
        target.unlink(missing_ok=True)
        raise

    images_described = 0
    try:
        images_described = await _enrich_with_images(parsed, target, provider)
    except Exception:
        pass  # image enrichment is best-effort

    warning = ""
    if not parsed["text"].strip() or len("".join(p["text"] for p in parsed["pages"]).strip()) == 0:
        warning = "No extractable text was found (scanned or image-only document?). Analysis quality will be poor."

    _remember(
        {
            "id": document_id,
            "filename": file.filename,
            "path": str(target),
            "parsed": parsed,
        }
    )
    return {
        "document_id": document_id,
        "filename": file.filename,
        "kind": parsed["kind"],
        "pages": parsed["pages"][:40],
        "page_count": len(parsed["pages"]),
        "preview_url": f"/api/documents/{document_id}/file",
        "characters": len(parsed["text"]),
        "images_described": images_described,
        "warning": warning,
    }


@app.get("/api/documents/{document_id}/file")
def get_file(document_id: str):
    item = _get_document(document_id)
    return FileResponse(item["path"], filename=item["filename"])


@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest) -> dict:
    item = _get_document(request.document_id)
    return await analyze_document(
        settings,
        request.mode,
        request.prompt,
        item["parsed"]["text"],
        request.thinking_mode,
        request.provider,
    )


@app.post("/api/chat")
async def chat(request: ChatRequest) -> dict:
    item = _get_document(request.document_id)
    return await chat_about_analysis(
        settings,
        request.question,
        item["parsed"]["text"],
        request.analysis,
        [m.model_dump() for m in request.history],
        request.provider,
    )


@app.post("/api/visual")
async def visual(request: VisualRequest) -> dict:
    path = await asyncio.to_thread(create_visual_summary, settings, request.analysis)
    return {"url": f"/api/visual/{path.name}", "filename": path.name}


@app.get("/api/visual/{filename}")
def get_visual(filename: str):
    visuals_dir = (settings.upload_path / "visuals").resolve()
    path = (visuals_dir / filename).resolve()
    if path.parent != visuals_dir or not path.is_file():
        raise HTTPException(status_code=404, detail="Visual not found")
    return FileResponse(path, media_type="image/png", filename=path.name)
