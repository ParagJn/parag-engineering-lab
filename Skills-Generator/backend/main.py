"""
Skills Generator API.

API only — the Vite frontend (http://localhost:5173) proxies /api here.
Run from the project root:  uvicorn main:app --app-dir backend --port 8000

Generation, regeneration and testing stream progress as Server-Sent Events.
"""

import json
import logging

from fastapi import APIRouter, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import generator
import skill_store
from config import config

# INFO-level logging so IBM ICA client diagnostics show up in the console
logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

config.ensure_directories()

app = FastAPI(title="Skills Generator")
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
router = APIRouter(prefix=config.API_PREFIX)


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class GenerateOptions(BaseModel):
    invocation: str = "auto"       # auto | slash-only | background
    scripts: str = "auto"          # auto | yes | no
    script_language: str = "python"  # python | bash | node


class GenerateRequest(BaseModel):
    thought: str = Field(min_length=1)
    platform: str  # anthropic | gemini | chatgpt
    options: GenerateOptions = GenerateOptions()


class RegenerateRequest(BaseModel):
    options: GenerateOptions | None = None


class UpdateFileRequest(BaseModel):
    content: str = Field(min_length=1)


class InstallRequest(BaseModel):
    overwrite: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sse(events) -> StreamingResponse:
    async def stream():
        async for event in events:
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _get_or_404(skill_id: str) -> dict:
    try:
        return skill_store.get_skill(skill_id)
    except skill_store.SkillNotFound:
        raise HTTPException(status_code=404, detail="Skill not found")


def _store_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except skill_store.SkillNotFound:
        raise HTTPException(status_code=404, detail="Not found")
    except skill_store.InstallConflict as e:
        raise HTTPException(
            status_code=409,
            detail=f"{e.path} already exists and was not installed by this app. Overwrite it?",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/models")
async def models():
    """Which ICA model generates each platform's skills (for UI labels)."""
    return config.MODEL_CHOICES


@router.post("/generate")
async def generate_skill(req: GenerateRequest):
    if req.platform not in config.MODEL_CHOICES:
        raise HTTPException(status_code=400, detail=f"Invalid platform: {req.platform}")
    return _sse(generator.generate_events(req.platform, req.thought.strip(), req.options.model_dump()))


@router.get("/skills")
async def list_skills():
    return skill_store.list_skills()


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str):
    return _get_or_404(skill_id)


@router.delete("/skills/{skill_id}")
async def delete_skill(skill_id: str):
    _store_call(skill_store.delete_skill, skill_id)
    return {"status": "deleted"}


@router.post("/skills/{skill_id}/archive")
async def archive_skill(skill_id: str):
    _store_call(skill_store.archive_skill, skill_id)
    return {"status": "archived"}


@router.post("/skills/{skill_id}/regenerate")
async def regenerate_skill(skill_id: str, req: RegenerateRequest | None = None):
    """Also the "Upgrade to full bundle" action for older single-file skills (same id)."""
    m = _get_or_404(skill_id)
    options = req.options.model_dump() if req and req.options else m.get("options")
    # Generate first; the old version is only replaced once the new one exists
    return _sse(generator.generate_events(m["platform"], m["thought"], options, skill_id))


@router.put("/skills/{skill_id}/files/{path:path}")
async def update_file(skill_id: str, path: str, req: UpdateFileRequest):
    return _store_call(skill_store.update_file, skill_id, path, req.content)


@router.delete("/skills/{skill_id}/files/{path:path}")
async def delete_file(skill_id: str, path: str):
    return _store_call(skill_store.delete_file, skill_id, path)


@router.post("/skills/{skill_id}/validate")
async def validate_skill(skill_id: str):
    return _store_call(skill_store.revalidate, skill_id)


@router.post("/skills/{skill_id}/install")
async def install_skill(skill_id: str, req: InstallRequest | None = None):
    return _store_call(skill_store.install_personal, skill_id, bool(req and req.overwrite))


@router.delete("/skills/{skill_id}/install")
async def uninstall_skill(skill_id: str):
    return _store_call(skill_store.uninstall_personal, skill_id)


@router.get("/skills/{skill_id}/download")
async def download_skill(skill_id: str):
    name, data = _store_call(skill_store.zip_bundle, skill_id)
    return Response(
        content=data,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{name}.zip"'},
    )


@router.post("/skills/{skill_id}/test")
async def test_skill(skill_id: str):
    _get_or_404(skill_id)
    return _sse(generator.test_events(skill_id))


app.include_router(router)
