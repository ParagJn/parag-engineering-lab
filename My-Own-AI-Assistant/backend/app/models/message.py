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


class Message(BaseModel):
    """Chat message."""
    id: str = Field(..., description="Unique message ID")
    role: MessageRole = Field(..., description="Message role")
    content: str = Field(..., description="Message content")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    attachments: list[MessageAttachment] = Field(default_factory=list)
    
    class Config:
        use_enum_values = True
