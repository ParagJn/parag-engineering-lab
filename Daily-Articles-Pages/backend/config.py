from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives one level up at the project root (Daily-Articles-Pages/.env)
_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    sap_client_id: str = ""
    sap_client_secret: str = ""
    sap_token_url: str = ""
    sap_api_url: str = ""
    sap_resource_group: str = "genius"
    sap_model_discovery_url: str = ""
    sap_anthropic_model: str = "anthropic--claude-4.7-opus"
    sap_gemini_model: str = "gemini-2.5-pro"
    sap_thinking_mode: str = "adaptive"
    sap_thinking_budget_tokens: int = 12000

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
