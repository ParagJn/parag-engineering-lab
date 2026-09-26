"""Attachments router."""

import re
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..config import config
from ..services import ModelRateLimitError, get_attachment_service

router = APIRouter(prefix="/sessions/{session_id}/attachments", tags=["attachments"])

# Session-independent routes, e.g. for thumbnails of images sent in chat
files_router = APIRouter(prefix="/attachments", tags=["attachments"])

ATTACHMENT_ID_PATTERN = re.compile(r"^att_[a-f0-9]{16}$")


class AttachmentResponse(BaseModel):
    """Attachment response model."""
    attachment_id: str
    filename: str
    mime_type: str
    size_bytes: int
    status: str
    markdown_available: bool
    image_count: int = 0


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
            image_count=len(attachment.images),
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ModelRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="Too many requests while reading the image. Please wait and try again.",
        )
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
        image_count=len(attachment.images),
    )


@files_router.get("/{attachment_id}/image")
async def get_attachment_image(attachment_id: str):
    """Serve an uploaded image attachment (images only) for display in the chat."""
    if not ATTACHMENT_ID_PATTERN.match(attachment_id):
        raise HTTPException(status_code=400, detail="Invalid attachment ID")

    attachment = get_attachment_service().get_attachment(attachment_id)
    if not attachment:
        raise HTTPException(status_code=404, detail="Attachment not found")

    path = Path(attachment.stored_path)
    if path.suffix.lower() not in config.IMAGE_EXTENSIONS or not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(path, media_type=attachment.mime_type)
