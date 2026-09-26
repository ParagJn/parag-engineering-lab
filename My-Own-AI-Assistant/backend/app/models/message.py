"""Message model."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message role."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class MessageAttachment(BaseModel):
    """Attachment reference in a message."""
    attachment_id: str
    filename: str
    mime_type: Optional[str] = None


class Message(BaseModel):
    """Chat message."""
    id: str = Field(..., description="Unique message ID")
    role: MessageRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    attachments: list[MessageAttachment] = Field(default_factory=list)
    svg_image_id: Optional[str] = Field(default=None, description="Generated SVG image ID, if any")
    svg_parent_id: Optional[str] = Field(default=None, description="SVG image this one was edited from")
    svg_version: Optional[int] = Field(default=None, description="Version number within an SVG edit chain")
    
    class Config:
        use_enum_values = True
