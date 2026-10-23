from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # IBM ICA. Same variable names as the other lab projects.
    ibm_ica_endpoint: str = ""
    ibm_ica_api_key: str = ""
    ibm_ica_model_id: str = "claude-opus-5-5"
    # Retried once when the primary model's reply is blocked by the content filter
    ibm_ica_fallback_model_id: str = "claude-sonnet-5"

    # Where the saved-projects database lives; empty means backend/data
    data_dir: str = ""

    max_upload_mb: int = 20
    # Document text sent to the model; longer documents are cut and the UI says so
    max_chars_for_llm: int = 150_000
    # Upper bound on how many diagrams the planner may propose
    max_diagrams: int = 8
    plan_max_output_tokens: int = 3000
    diagram_max_output_tokens: int = 6000
    animation_max_output_tokens: int = 700

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    @property
    def db_path(self) -> Path:
        base = Path(self.data_dir) if self.data_dir else Path(__file__).resolve().parent.parent / "data"
        base.mkdir(parents=True, exist_ok=True)
        return base / "diagram_studio.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
