"""Messages router."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..repositories import SessionRepository
from ..services import (
    get_attachment_service,
    get_message_service,
    get_model_service,
    get_session_service,
)

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


@router.post("", response_model=ChatResponse)
async def send_message(session_id: str, request: MessageRequest):
    """Send a message and get a response."""
    session_service = get_session_service()
    message_service = get_message_service()
    model_service = get_model_service()
    attachment_service = get_attachment_service()
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
    
    # Build attachments context (for documents only, images handled by model service)
    attachments_context = None
    
    if request.attachment_ids:
        context_parts = []
        for att_id in request.attachment_ids:
            attachment = attachment_service.get_attachment(att_id)
            if attachment:
                content = attachment_service.get_attachment_content(att_id)
                if content:
                    # Include the extracted text in XML-style tags
                    context_parts.append(f"<attachment id='{att_id}' filename='{attachment.filename}'>\n{content}\n</attachment>")
        
        if context_parts:
            attachments_context = "## Attached Documents\n\n" + "\n\n".join(context_parts)
    
    try:
        # Generate response
        result = await model_service.generate(
            messages=session.messages,
            attachments_context=attachments_context,
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
    
    except Exception as e:
        # Remove failed user message
        session.messages.pop()
        raise HTTPException(status_code=500, detail=f"Failed to generate response: {str(e)}")
