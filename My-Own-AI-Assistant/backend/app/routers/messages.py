"""Messages router."""

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from ..repositories import SessionRepository
from ..services import (
    ModelRateLimitError,
    get_attachment_service,
    get_message_service,
    get_model_service,
    get_project_service,
    get_session_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions/{session_id}/messages", tags=["messages"])


class MessageRequest(BaseModel):
    """Message request model."""
    content: str
    attachment_ids: list[str] = []


class MessageResponse(BaseModel):
    """Message response model."""
    id: str
    role: str
    content: str
    created_at: str


class ChatResponse(BaseModel):
    """Chat response model."""
    session_id: str
    message: MessageResponse


def _build_project_context(project_id: str | None) -> tuple[dict | None, set[str]]:
    """Project instructions and pinned documents for the prompt, plus the pinned file IDs."""
    context = get_project_service().build_context(project_id)
    if not context:
        return None, set()
    pinned_ids = {a.attachment_id for a in get_project_service().repository.list_documents(project_id)}
    return {
        "name": context.project.name,
        "instructions": context.instructions,
        "documents_context": context.documents_context,
    }, pinned_ids


def _build_attachments_context(
    attachment_ids: list[str], skip_ids: set[str] | None = None
) -> tuple[str | None, list[dict]]:
    """Build attachments context (extracted text) and gather embedded images for vision analysis.

    Files in skip_ids (already pinned to the chat's project) aren't added twice.
    """
    attachment_service = get_attachment_service()
    attachments_context = None
    attachment_images: list[dict] = []
    attachment_ids = [a for a in attachment_ids if a not in (skip_ids or set())]

    if attachment_ids:
        context_parts = []
        for att_id in attachment_ids:
            attachment = attachment_service.get_attachment(att_id)
            if attachment:
                content = attachment_service.get_attachment_content(att_id)
                if content:
                    # Include the extracted text in XML-style tags
                    context_parts.append(f"<attachment id='{att_id}' filename='{attachment.filename}'>\n{content}\n</attachment>")
                attachment_images.extend(attachment_service.get_attachment_images(att_id))

        if context_parts:
            attachments_context = "## Attached Documents and Images\n\n" + "\n\n".join(context_parts)

    return attachments_context, attachment_images


@router.post("", response_model=ChatResponse)
async def send_message(session_id: str, request: MessageRequest):
    """Send a message and get a response."""
    session_service = get_session_service()
    message_service = get_message_service()
    model_service = get_model_service()
    repository = SessionRepository()

    # Get session
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Add user message
    user_message = message_service.add_user_message(
        session,
        request.content,
        request.attachment_ids,
    )

    # Update title from first message
    if len(session.messages) == 1:
        session_service.update_session_title(session, request.content)

    project_context, pinned_ids = _build_project_context(session.project_id)
    attachments_context, attachment_images = _build_attachments_context(request.attachment_ids, pinned_ids)

    try:
        # Generate response
        result = await model_service.generate(
            messages=session.messages,
            attachments_context=attachments_context,
            model=session.model,
            images=attachment_images,
            web_search_enabled=session.web_search_enabled,
            project_context=project_context,
        )
        
        # Add assistant message
        assistant_message = message_service.add_assistant_message(
            session,
            result["text"],
        )
        
        # Save session
        repository.update(session)
        
        # Handle both enum and string role values
        role_value = assistant_message.role.value if hasattr(assistant_message.role, 'value') else assistant_message.role
        
        return ChatResponse(
            session_id=session.session_id,
            message=MessageResponse(
                id=assistant_message.id,
                role=role_value,
                content=assistant_message.content,
                created_at=assistant_message.created_at.isoformat(),
            ),
        )
    
    except ModelRateLimitError:
        # Remove failed user message
        session.messages.pop()
        raise HTTPException(
            status_code=429,
            detail="Too many requests to the model provider. Please wait and try again.",
        )
    except Exception as e:
        # Remove failed user message
        session.messages.pop()
        logger.exception("Failed to generate response for session %s", session_id)
        raise HTTPException(status_code=500, detail=f"Failed to generate response: {str(e)}")


@router.post("/stream")
async def send_message_stream(session_id: str, request: MessageRequest):
    """Send a message and stream back the response as Server-Sent Events."""
    session_service = get_session_service()
    message_service = get_message_service()
    model_service = get_model_service()
    repository = SessionRepository()

    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    message_service.add_user_message(
        session,
        request.content,
        request.attachment_ids,
    )

    if len(session.messages) == 1:
        session_service.update_session_title(session, request.content)

    project_context, pinned_ids = _build_project_context(session.project_id)
    attachments_context, attachment_images = _build_attachments_context(request.attachment_ids, pinned_ids)

    stream_iter = model_service.generate_stream(
        messages=session.messages,
        attachments_context=attachments_context,
        model=session.model,
        images=attachment_images,
        web_search_enabled=session.web_search_enabled,
        project_context=project_context,
    ).__aiter__()

    # Pull the first chunk now (before returning a streaming response) so that a
    # ModelRateLimitError or any other failure on the initial call still becomes
    # a normal HTTP error, matching the non-streaming endpoint's behavior.
    try:
        first_chunk = await anext(stream_iter, None)
    except ModelRateLimitError:
        session.messages.pop()
        raise HTTPException(
            status_code=429,
            detail="Too many requests to the model provider. Please wait and try again.",
        )
    except Exception as e:
        session.messages.pop()
        logger.exception("Failed to generate response for session %s", session_id)
        raise HTTPException(status_code=500, detail=f"Failed to generate response: {str(e)}")

    async def event_stream():
        full_text = first_chunk or ""
        if first_chunk:
            yield f"event: chunk\ndata: {json.dumps({'text': first_chunk})}\n\n"

        try:
            async for delta in stream_iter:
                full_text += delta
                yield f"event: chunk\ndata: {json.dumps({'text': delta})}\n\n"
        except Exception as e:
            logger.exception("Failed while streaming response for session %s", session_id)
            session.messages.pop()
            yield f"event: error\ndata: {json.dumps({'detail': f'Failed to generate response: {e}'})}\n\n"
            return

        assistant_message = message_service.add_assistant_message(session, full_text)
        repository.update(session)

        role_value = (
            assistant_message.role.value if hasattr(assistant_message.role, 'value') else assistant_message.role
        )
        yield (
            "event: done\ndata: "
            + json.dumps({
                "session_id": session.session_id,
                "message": {
                    "id": assistant_message.id,
                    "role": role_value,
                    "content": assistant_message.content,
                    "created_at": assistant_message.created_at.isoformat(),
                },
            })
            + "\n\n"
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
