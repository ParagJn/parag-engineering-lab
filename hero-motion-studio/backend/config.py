from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# .env lives one level up at the project root (hero-motion-studio/.env)
_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    ibm_ica_endpoint: str = ""
    ibm_ica_api_key: str = ""
    ibm_ica_model_id: str = "claude-opus-5-5"
    ibm_ica_gemini_model_id: str = ""

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
