from typing import Dict
from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    operation: str = Field(..., description="Operation key")
    niche: str = Field(..., description="User niche")
    platform: str = Field(default="Instagram", description="Primary social platform")
    audience: str = Field(default="", description="Audience description")
    metrics: str = Field(default="", description="Analytics stats")
    extra_context: str = Field(default="", description="Additional context and constraints")


class GenerateResponse(BaseModel):
    operation: str
    prompt_preview: str
    gemini_output: str
    claude_output: str
    synthesized_output: str
    metadata: Dict[str, str]
