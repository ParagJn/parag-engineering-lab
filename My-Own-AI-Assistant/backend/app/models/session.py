"""Session model."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from .message import Message


class Session(BaseModel):
    """Chat session."""
    session_id: str = Field(..., description="Unique session ID")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    title: str = Field(default="New conversation", description="Session title")
    model: str = Field(default="claude", description="Model provider: claude or gemini")
    web_search_enabled: bool = Field(default=False, description="Whether the web search tool is enabled")
    messages: list[Message] = Field(default_factory=list)
    attachment_ids: list[str] = Field(default_factory=list)
