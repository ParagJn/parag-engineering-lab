from typing import Dict, List, Literal

from pydantic import BaseModel, Field


class ApiKeyUpdate(BaseModel):
    openai: str = ""
    anthropic: str = ""
    gemini: str = ""


class SettingsUpdateRequest(BaseModel):
    provider_mode: Literal["built_in", "custom"] = Field(..., description="AI provider mode")
    api_keys: ApiKeyUpdate = Field(default_factory=ApiKeyUpdate)
    enabled_providers: List[Literal["openai", "anthropic", "gemini"]] = Field(default_factory=list)


class PublicSettings(BaseModel):
    provider_mode: Literal["built_in", "custom"]
    has_keys: Dict[str, bool]
    masked_keys: Dict[str, str]
    enabled_providers: List[str]


class ProviderVerificationResult(BaseModel):
    provider: str
    ok: bool
    message: str


class SettingsVerificationResponse(BaseModel):
    ok: bool
    results: List[ProviderVerificationResult]
