from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    # IBM ICA. Same variable names as Daily-Articles-Pages and Strategy-Analyzer.
    ibm_ica_endpoint: str = ""
    ibm_ica_api_key: str = ""
    ibm_ica_model_id: str = "claude-opus-5-5"
    # Retried once when the primary model's reply is blocked by the content filter
    ibm_ica_fallback_model_id: str = "claude-sonnet-5"

    # Where the saved-comparisons database lives; empty means backend/data
    data_dir: str = ""

    max_upload_mb: int = 50
    max_pdf_pages: int = 300
    docx_paragraphs_per_section: int = 8
    # Text sent to the model per file; longer files are cut and the report says so
    max_chars_for_llm: int = 180_000
    image_max_output_tokens: int = 3000
    report_max_output_tokens: int = 7000
    report_style: str = "detailed"
    summary_top_n: int = 12

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    @property
    def db_path(self) -> Path:
        base = Path(self.data_dir) if self.data_dir else Path(__file__).resolve().parent.parent / "data"
        base.mkdir(parents=True, exist_ok=True)
        return base / "file_compare.db"


@lru_cache
def get_settings() -> Settings:
    return Settings()
