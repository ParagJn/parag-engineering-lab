from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    azure_openai_gpt54_base: str = ""
    azure_openai_gpt54_key: str = ""
    azure_openai_gpt54_version: str = "2025-04-01-preview"
    azure_openai_gpt54_deployment: str = "gpt-5.4-common"
    azure_openai_gpt54_resource_group: str = ""
    azure_openai_gpt54_region: str = ""

    azure_openai_gpt53codex_base: str = ""
    azure_openai_gpt53codex_key: str = ""
    azure_openai_gpt53codex_version: str = "2025-04-01-preview"
    azure_openai_gpt53codex_deployment: str = "gpt-5.3-codex-common"
    azure_openai_gpt53codex_resource_group: str = ""
    azure_openai_gpt53codex_region: str = ""

    sap_client_id: str = ""
    sap_client_secret: str = ""
    sap_token_url: str = ""
    sap_api_url: str = ""
    sap_resource_group: str = "genius"
    sap_model_discovery_url: str = "https://api.ai.prod.eu-central-1.aws.ml.hana.ondemand.com/v2/lm/scenarios/foundation-models/models"
    sap_anthropic_model: str = "anthropic--claude-4.7-opus"
    sap_gemini_model: str = "gemini-2.5-pro"
    sap_thinking_mode: str = "adaptive"
    sap_thinking_budget_tokens: int = 12000

    # IBM ICA (default provider). Same variable names as Daily-Articles-Pages.
    ibm_ica_endpoint: str = ""
    ibm_ica_api_key: str = ""
    ibm_ica_model_id: str = "claude-opus-5-5"
    ibm_ica_gemini_model_id: str = ""
    # Optional per-role overrides; each falls back to ibm_ica_model_id
    ibm_ica_validator_model_id: str = ""
    ibm_ica_synthesizer_model_id: str = ""
    # Retried once when the primary model's reply is blocked by the content filter
    ibm_ica_fallback_model_id: str = "claude-sonnet-5"

    upload_dir: str = "./uploads"
    max_upload_mb: int = 50
    max_images_per_document: int = 20

    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), env_file_encoding="utf-8", extra="ignore")

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
