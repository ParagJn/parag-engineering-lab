"""Attachment model."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AttachmentStatus(str, Enum):
    """Attachment processing status."""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class AttachmentImage(BaseModel):
    """An image extracted from an attachment."""
    filename: str = Field(..., description="Image filename")
    mime_type: str = Field(..., description="Image MIME type")
    stored_path: str = Field(..., description="Path to the stored image file")


class Attachment(BaseModel):
    """File attachment."""
    attachment_id: str = Field(..., description="Unique attachment ID")
    session_id: Optional[str] = Field(None, description="Chat the file was uploaded in")
    filename: str = Field(..., description="Original filename")
    mime_type: str = Field(..., description="MIME type")
    size_bytes: int = Field(..., description="File size in bytes")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    stored_path: str = Field(..., description="Path to stored file")
    content_markdown_path: Optional[str] = Field(None, description="Path to extracted Markdown")
    images: list[AttachmentImage] = Field(default_factory=list, description="Embedded images extracted from the document")
    status: AttachmentStatus = Field(default=AttachmentStatus.UPLOADED)

    class Config:
        use_enum_values = True
