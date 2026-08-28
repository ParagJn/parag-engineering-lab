"""Attachments router."""

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from ..services import get_attachment_service

router = APIRouter(prefix="/sessions/{session_id}/attachments", tags=["attachments"])


class AttachmentResponse(BaseModel):
    """Attachment response model."""
    attachment_id: str
    filename: str
    mime_type: str
    size_bytes: int
    status: str
    markdown_available: bool


@router.post("", response_model=AttachmentResponse)
async def upload_attachment(session_id: str, file: UploadFile = File(...)):
    """Upload an attachment."""
    attachment_service = get_attachment_service()
    
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    # Read file size
    content = await file.read()
    size_bytes = len(content)
    
    # Reset file pointer
    await file.seek(0)
    
    try:
        attachment = await attachment_service.create_attachment(
            file=file.file,
            filename=file.filename,
            size_bytes=size_bytes,
        )
        
        return AttachmentResponse(
            attachment_id=attachment.attachment_id,
            filename=attachment.filename,
            mime_type=attachment.mime_type,
            size_bytes=attachment.size_bytes,
            status=attachment.status.value,
            markdown_available=attachment.content_markdown_path is not None,
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload attachment: {str(e)}")


@router.get("/{attachment_id}", response_model=AttachmentResponse)
async def get_attachment(session_id: str, attachment_id: str):
    """Get attachment metadata."""
    attachment_service = get_attachment_service()
    
    attachment = attachment_service.get_attachment(attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")
    
    return AttachmentResponse(
        attachment_id=attachment.attachment_id,
        filename=attachment.filename,
        mime_type=attachment.mime_type,
        size_bytes=attachment.size_bytes,
        status=attachment.status.value,
        markdown_available=attachment.content_markdown_path is not None,
    )
