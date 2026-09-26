"""SVG image generation API (all models).

The ICA gateway only returns text, but every model writes SVG markup well.
This router asks the session's model for SVG code, saves it under
data/svg_images/, records the prompt + result as a chat turn, and serves the
file for inline display or download.

Edits: passing `base_svg_image_id` revises an existing image. The model gets
the chain of prompts that led to it plus the current SVG code, and the new
image is stored as the next version in that chain.
"""

import asyncio
import logging
import re
import uuid

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .config import config
from .ibm_ica_client import IBMICAError
from .models import Message, Session
from .repositories import SessionRepository
from .services import get_message_service, get_model_service, get_session_service
from .svg_export import ExportFormat, SvgExportError, export_svg

logger = logging.getLogger(__name__)

router = APIRouter(tags=["svg-images"])

SVG_ID_PATTERN = re.compile(r"^svg_[a-f0-9]{16}$")
SVG_MAX_TOKENS = 16000

SVG_SYSTEM_PROMPT = (
    "You are an expert SVG illustrator. Turn the user's description into a single, "
    "self-contained, visually polished SVG image.\n"
    "Rules:\n"
    "- Respond with ONLY the raw SVG markup, starting with <svg and ending with </svg>.\n"
    "- Include xmlns=\"http://www.w3.org/2000/svg\" and a viewBox.\n"
    "- Use a white / light background by default (a full-size white <rect> as the "
    "first element). Only use a dark background if the user explicitly asks for one.\n"
    "- No markdown fences, no explanation, no <script>, no external resources.\n"
    "- If the user asks for animation or motion, animate with SMIL (<animate>, "
    "<animateTransform>) or CSS @keyframes in a <style> block, looping seamlessly "
    "with cycles of 10 seconds or less. Never use JavaScript.\n"
    "- When asked to edit an existing SVG, return the COMPLETE revised SVG, keeping "
    "everything the user didn't ask to change.\n"
    "- For charts, diagrams, maps or anything factual, use the labels, numbers and facts "
    "the user supplied. Don't invent data values, statistics, names or relationships; if "
    "something needed is missing, use an obvious placeholder label (e.g. \"Value A\", "
    "\"TBD\") rather than a made-up figure."
)


class SvgImageRequest(BaseModel):
    """SVG generation request."""
    prompt: str
    base_svg_image_id: str | None = None


class SvgMessageResponse(BaseModel):
    """Assistant message holding the generated SVG."""
    id: str
    role: str
    content: str
    created_at: str
    svg_image_id: str
    svg_parent_id: str | None = None
    svg_version: int


class SvgImageResponse(BaseModel):
    """SVG generation response."""
    session_id: str
    svg_image_id: str
    message: SvgMessageResponse


def _extract_svg(text: str) -> str | None:
    """Pull the <svg>...</svg> block out of the model's reply."""
    match = re.search(r"<svg\b.*?</svg>", text, re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    svg = match.group(0)
    # Browsers won't render an SVG file via <img> without the namespace
    if "xmlns=" not in svg[:500]:
        svg = svg.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    return svg


def _sanitize_svg(svg: str) -> str:
    """Strip active content so the saved file is safe to open directly."""
    svg = re.sub(r"<script\b.*?</script\s*>", "", svg, flags=re.DOTALL | re.IGNORECASE)
    svg = re.sub(r"<foreignObject\b.*?</foreignObject\s*>", "", svg, flags=re.DOTALL | re.IGNORECASE)
    svg = re.sub(r"\son[a-z]+\s*=\s*(\"[^\"]*\"|'[^']*')", "", svg, flags=re.IGNORECASE)
    svg = re.sub(r"(href\s*=\s*[\"'])\s*javascript:[^\"']*", r"\1#", svg, flags=re.IGNORECASE)
    return svg


def _generate_svg_id() -> str:
    return f"svg_{uuid.uuid4().hex[:16]}"


def _svg_path(svg_image_id: str):
    return config.SVG_IMAGES_DIR / f"{svg_image_id}.svg"


def _edit_chain(session: Session, svg_image_id: str) -> list[tuple[str, Message]]:
    """
    Walk svg_parent_id links back from `svg_image_id` and return
    [(prompt, assistant_message), ...] oldest first. Each SVG assistant message
    directly follows the user message holding its prompt.
    """
    index_by_svg = {
        m.svg_image_id: i for i, m in enumerate(session.messages) if m.svg_image_id
    }
    chain: list[tuple[str, Message]] = []
    current = svg_image_id
    while current and current in index_by_svg:
        i = index_by_svg[current]
        message = session.messages[i]
        prompt = session.messages[i - 1].content if i > 0 else ""
        chain.append((prompt, message))
        current = message.svg_parent_id
    chain.reverse()
    return chain


def _build_edit_messages(chain: list[tuple[str, Message]], base_svg: str, prompt: str) -> list[dict]:
    """Conversation for an edit: earlier prompts as context, then the current SVG + new request."""
    messages: list[dict] = [{"role": "system", "content": SVG_SYSTEM_PROMPT}]
    for step_prompt, step_message in chain[:-1]:
        messages.append({"role": "user", "content": step_prompt})
        messages.append({
            "role": "assistant",
            "content": f"[SVG version {step_message.svg_version or 1} generated]",
        })
    messages.append({"role": "user", "content": chain[-1][0]})
    messages.append({"role": "assistant", "content": base_svg})
    messages.append({
        "role": "user",
        "content": f"Revise the SVG above with this change:\n{prompt}\n\nReturn the complete updated SVG.",
    })
    return messages


@router.post("/sessions/{session_id}/svg-images", response_model=SvgImageResponse)
async def generate_svg_image(session_id: str, request: SvgImageRequest):
    """Generate an SVG image from a prompt (or edit an existing one) using the session's model."""
    session_service = get_session_service()
    message_service = get_message_service()
    model_service = get_model_service()
    repository = SessionRepository()

    prompt = request.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is required")

    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    parent_id = request.base_svg_image_id
    version = 1
    if parent_id:
        if not SVG_ID_PATTERN.match(parent_id) or not _svg_path(parent_id).exists():
            raise HTTPException(status_code=404, detail="SVG image to edit not found")
        chain = _edit_chain(session, parent_id)
        if not chain:
            raise HTTPException(status_code=404, detail="SVG image to edit is not part of this session")
        version = (chain[-1][1].svg_version or len(chain)) + 1
        base_svg = _svg_path(parent_id).read_text(encoding="utf-8")
        model_messages = _build_edit_messages(chain, base_svg, prompt)
    else:
        model_messages = [
            {"role": "system", "content": SVG_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

    try:
        # The ICA client is blocking; keep the event loop free while it runs
        result = await asyncio.to_thread(
            model_service.client.chat,
            messages=model_messages,
            max_tokens=SVG_MAX_TOKENS,
            model_id=config.MODEL_CHOICES.get(session.model, config.IBM_ICA_MODEL_ID),
        )
    except IBMICAError as e:
        if getattr(e, "http_code", None) == 429:
            raise HTTPException(
                status_code=429,
                detail="Too many requests to the model provider. Please wait and try again.",
            )
        logger.exception("SVG generation failed for session %s", session_id)
        raise HTTPException(status_code=502, detail=f"SVG generation failed: {str(e)}")

    svg = _extract_svg(result["text"])
    if not svg:
        raise HTTPException(status_code=502, detail="The model did not return valid SVG markup. Try rephrasing the prompt.")

    svg_image_id = _generate_svg_id()
    _svg_path(svg_image_id).write_text(_sanitize_svg(svg), encoding="utf-8")

    # Record the turn in the conversation so it survives reloads
    message_service.add_user_message(session, prompt)
    if len(session.messages) == 1:
        session_service.update_session_title(session, prompt)
    content = (
        f"Edited SVG image (v{version}): *{prompt}*" if parent_id
        else f"Generated SVG image for: *{prompt}*"
    )
    assistant_message = message_service.add_assistant_message(
        session,
        content,
        svg_image_id=svg_image_id,
        svg_parent_id=parent_id,
        svg_version=version,
    )
    repository.update(session)

    role_value = assistant_message.role.value if hasattr(assistant_message.role, 'value') else assistant_message.role

    return SvgImageResponse(
        session_id=session.session_id,
        svg_image_id=svg_image_id,
        message=SvgMessageResponse(
            id=assistant_message.id,
            role=role_value,
            content=assistant_message.content,
            created_at=assistant_message.created_at.isoformat(),
            svg_image_id=svg_image_id,
            svg_parent_id=parent_id,
            svg_version=version,
        ),
    )


@router.get("/svg-images/{svg_image_id}")
async def get_svg_image(svg_image_id: str, download: bool = Query(False)):
    """Serve a saved SVG, inline for display or as an attachment for download."""
    if not SVG_ID_PATTERN.match(svg_image_id):
        raise HTTPException(status_code=400, detail="Invalid SVG image ID")

    path = _svg_path(svg_image_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="SVG image not found")

    return FileResponse(
        path,
        media_type="image/svg+xml",
        filename=f"{svg_image_id}.svg" if download else None,
        content_disposition_type="attachment" if download else "inline",
        headers={"Content-Security-Policy": "script-src 'none'"},
    )


@router.get("/svg-images/{svg_image_id}/export")
async def export_svg_image(svg_image_id: str, fmt: ExportFormat = Query(..., alias="format")):
    """Experimental: render the SVG (including its animations) to MP4 or GIF for download."""
    if not SVG_ID_PATTERN.match(svg_image_id):
        raise HTTPException(status_code=400, detail="Invalid SVG image ID")

    path = _svg_path(svg_image_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="SVG image not found")

    try:
        out_path = await export_svg(path, fmt)
    except SvgExportError as e:
        logger.warning("SVG export (%s) failed for %s: %s", fmt, svg_image_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    return FileResponse(
        out_path,
        media_type="video/mp4" if fmt == "mp4" else "image/gif",
        filename=f"{svg_image_id}.{fmt}",
    )
