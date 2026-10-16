from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).parent.parent
# .env lives one level up at the project root (Data-Story-Studio/.env)
_ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    ibm_ica_endpoint: str = ""
    ibm_ica_api_key: str = ""
    ibm_ica_model_id: str = "claude-opus-5-5"
    # Retried once when the primary model's reply is blocked by the content filter
    ibm_ica_fallback_model_id: str = "claude-sonnet-5"

    # Data-readiness gate: fewer records than this and we ask for more data
    min_rows: int = 1000
    max_upload_mb: int = 200
    # Hard cap on rows returned to the browser for any single panel / query
    max_result_rows: int = 5000

    data_dir: Path = PROJECT_ROOT / "data"
    viewer_dist: Path = PROJECT_ROOT / "frontend" / "dist-viewer"

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def llm_configured(self) -> bool:
        return bool(self.ibm_ica_endpoint and self.ibm_ica_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
