"""Project model."""

from datetime import datetime

from pydantic import BaseModel, Field


class Project(BaseModel):
    """A workspace grouping chats that share instructions and pinned documents."""
    project_id: str = Field(..., description="Unique project ID")
    name: str = Field(..., description="Project name")
    description: str = Field(default="", description="Short description shown in the UI")
    instructions: str = Field(default="", description="Instructions sent with every message in the project")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
