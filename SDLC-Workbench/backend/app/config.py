from __future__ import annotations

import re

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The only place that points at the real .env. Tests repoint this at a missing file.
ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

# Slot name -> prefix of its variables. Sonnet keeps the lab's unprefixed IBM_ICA_MODEL_ID.
_SLOT_PREFIX = {
    "sonnet": "ibm_ica",
    "haiku": "ibm_ica_haiku",
    "openai": "ibm_ica_openai",
    "gemini": "ibm_ica_gemini",
}
_PRICE_FIELDS = tuple(
    f"{prefix}_price_{direction}_per_mtok"
    for prefix in _SLOT_PREFIX.values()
    for direction in ("input", "output")
)


@dataclass(frozen=True)
class SlotConfig:
    """One model family's settings. Holds no credentials."""

    name: str
    model_id: str
    fallback_model_id: str
    price_input: float | None
    price_output: float | None

    @property
    def priced(self) -> bool:
        return self.price_input is not None and self.price_output is not None


class Settings(BaseSettings):
    # Shared IBM ICA access: one endpoint and key serve every model.
    ibm_ica_endpoint: str = ""
    ibm_ica_api_key: SecretStr = SecretStr("")
    # GPT models use this key instead. Blank means the shared key above is used for them too.
    ibm_ica_openai_api_key: SecretStr = SecretStr("")

    # Prices are USD per million tokens. Blank means unknown, never zero.
    ibm_ica_model_id: str = ""
    ibm_ica_fallback_model_id: str = ""
    ibm_ica_price_input_per_mtok: float | None = None
    ibm_ica_price_output_per_mtok: float | None = None

    ibm_ica_haiku_model_id: str = ""
    ibm_ica_haiku_fallback_model_id: str = ""
    ibm_ica_haiku_price_input_per_mtok: float | None = None
    ibm_ica_haiku_price_output_per_mtok: float | None = None

    ibm_ica_openai_model_id: str = ""
    ibm_ica_openai_fallback_model_id: str = ""
    ibm_ica_openai_price_input_per_mtok: float | None = None
    ibm_ica_openai_price_output_per_mtok: float | None = None

    ibm_ica_gemini_model_id: str = ""
    ibm_ica_gemini_fallback_model_id: str = ""
    ibm_ica_gemini_price_input_per_mtok: float | None = None
    ibm_ica_gemini_price_output_per_mtok: float | None = None

    app_mode: Literal["replay", "live"] = "replay"
    # `.env.example` has always documented this name as the per-run spending limit, but nothing read it: the cap the runner enforces is `run_max_cost_usd`. A person who set this
    # one (as the example file tells them to) still ran under the built-in $5. It now sets the cap, unless RUN_MAX_COST_USD is given too (that one wins).
    run_budget_usd: float = Field(default=5.0, ge=0, le=1000)
    llm_timeout_seconds: float = Field(default=180, gt=0)
    llm_max_retries: int = Field(default=1, ge=0, le=5)
    llm_retry_backoff_seconds: float = Field(default=1.0, ge=0, le=30)

    # Guardrails (S10): rule names to switch off, comma-separated. `configured_credential` and `private_key` cannot be.
    guardrails_disabled_rules: str = ""

    # Running a whole phase (S09). 0 switches a cap off.
    run_max_concurrency: int = Field(default=3, ge=1, le=8)
    run_max_cost_usd: float = Field(default=5.0, ge=0, le=1000)      # raised from 2.0 on 2026-10-31 at the user's request: a real project costs more than the sample
    run_max_seconds: float = Field(default=1800, ge=0, le=86400)
    run_event_queue: int = Field(default=200, ge=10, le=10000)
    run_heartbeat_seconds: float = Field(default=15, gt=0, le=300)

    # Where the SQLite file lives; empty means backend/data.
    data_dir: str = ""

    # Record and replay. A set is a folder of saved model replies; letters, digits, - and _ only,
    # so the name can never point outside the recordings folder.
    replay_set: str = Field(default="demo", pattern=r"^[A-Za-z0-9_-]{1,64}$")
    recordings_dir: str = ""  # empty means backend/recordings
    record_live_calls: bool = False  # in live mode, save every successful reply into the set
    replay_pace: float = Field(default=0.0, ge=0, le=1)  # fraction of the recorded latency to wait

    # Context store limits. The hard caps (1,500 characters a chunk, 2,000 chunks a document) are constants.
    context_max_file_mb: int = Field(default=10, ge=1, le=100)
    context_max_pdf_pages: int = Field(default=200, ge=1, le=2000)
    context_max_docs_per_project: int = Field(default=500, ge=1, le=10000)
    context_chunk_target_chars: int = Field(default=900, ge=200, le=1400)

    # Agent runtime. How much goes into a prompt and how hard the runtime tries to get a valid artefact.
    agent_max_repairs: int = Field(default=2, ge=0, le=5)
    agent_max_output_tokens: int = Field(default=8000, ge=256, le=64000)
    # Roles that need a larger output limit than the rest, as "role=tokens" pairs separated by commas. The default carries Gemini's UX designer:
    # its wireframe sets are ~4,000 tokens of reply, but the model also spends output tokens on reasoning it never shows (measured on the user's
    # real run: 300 visible tokens billed as 7,996), so 8,000 was a coin toss and 24,000 is room for both.
    # Real code is long, and some models spend part of the limit thinking before they write: at 8,000 a real frontend and a real test suite were cut off
    # (2026-11-03). The database schema is short and keeps the general limit.
    agent_output_tokens_by_role: str = "ux_designer=24000,frontend_developer=24000,test_engineer=24000,backend_developer=16000,solution_architect=16000"
    agent_upstream_max_chars: int = Field(default=100000, ge=1000, le=400000)
    agent_context_max_chunks: int = Field(default=6, ge=0, le=30)
    agent_context_max_chars: int = Field(default=6000, ge=0, le=60000)
    agent_context_min_coverage: float = Field(default=0.5, ge=0, le=1)
    agent_brief_queries: int = Field(default=8, ge=0, le=20)  # extra searches, one per sentence of the brief
    review_max_output_tokens: int = Field(default=8000, ge=256, le=32000)
    # The review of ONE FILE of the Build instruction set (S19e). Larger than the general limit because the reviewer spends part of its limit thinking before it writes: at 8,000 the
    # first reviews of the set came back EMPTY (finish_reason=length). Used only for a file-review call; every other review keeps REVIEW_MAX_OUTPUT_TOKENS.
    review_file_max_output_tokens: int = Field(default=12000, ge=256, le=32000)
    review_max_repairs: int = Field(default=1, ge=0, le=3)
    review_max_findings: int = Field(default=20, ge=1, le=100)
    review_cited_max_chars: int = Field(default=8000, ge=0, le=100000)  # cited source text shown to a reviewer
    # Sandbox (S16): where generated code is written and run, and how much it may use. Every limit is a plain refusal when exceeded, never a crash.
    sandbox_command_seconds: int = Field(default=60, ge=1, le=600)
    sandbox_test_seconds: int = Field(default=120, ge=1, le=1800)
    sandbox_output_bytes: int = Field(default=256 * 1024, ge=1024, le=8 * 1024 * 1024)
    sandbox_file_bytes: int = Field(default=1024 * 1024, ge=1024, le=16 * 1024 * 1024)
    sandbox_max_files: int = Field(default=500, ge=1, le=20000)
    sandbox_total_bytes: int = Field(default=50 * 1024 * 1024, ge=1024, le=2 * 1024 * 1024 * 1024)
    sandbox_max_processes: int = Field(default=64, ge=4, le=1024)
    sandbox_memory_mb: int = Field(default=1024, ge=64, le=16384)
    # Build (S17b): how many times the generated tests are run and the failures sent back for a fix. Worst case is rounds x (1 call + agent_max_repairs).
    build_fix_rounds: int = Field(default=3, ge=1, le=10)
    # Left unset by default: some newer models reject the parameter, which would fail the call with no fallback.
    agent_temperature: float | None = Field(default=None, ge=0, le=2)

    # Turn certificate checking off. For local connectivity testing only.
    ibm_ica_insecure_tls: bool = False
    # Some gateways reject the default Python client label. The sibling lab apps send this one.
    ibm_ica_user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # No env_file here: get_settings() is the only code that names the real .env.
    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="ignore")

    @model_validator(mode="after")
    def _the_budget_sets_the_run_cap(self) -> "Settings":
        given = self.model_fields_set
        if "run_budget_usd" in given and "run_max_cost_usd" not in given:
            self.run_max_cost_usd = self.run_budget_usd
        return self

    @field_validator(*_PRICE_FIELDS, mode="before")
    @classmethod
    def _blank_price_is_none(cls, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError("price must be a number (USD per million tokens) or blank") from None
        if not math.isfinite(number) or number < 0:
            raise ValueError("price must be zero or more")
        return number

    @field_validator("agent_output_tokens_by_role", mode="after")
    @classmethod
    def _role_limits_are_pairs_of_a_name_and_a_sensible_number(cls, value: str) -> str:
        cls._parse_role_limits(value)          # raises with a sentence if a pair is malformed
        return value

    @staticmethod
    def _parse_role_limits(value: str) -> dict[str, int]:
        out: dict[str, int] = {}
        for part in (value or "").split(","):
            part = part.strip()
            if not part:
                continue
            role, sep, number = part.partition("=")
            role, number = role.strip(), number.strip()
            if not sep or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", role) or not number.isdigit():
                raise ValueError(f"AGENT_OUTPUT_TOKENS_BY_ROLE entries look like 'ux_designer=24000'; got {part!r}")
            if not 256 <= int(number) <= 64000:
                raise ValueError(f"the output limit for {role!r} must be between 256 and 64000; got {number}")
            if role in out:
                raise ValueError(f"AGENT_OUTPUT_TOKENS_BY_ROLE lists {role!r} twice")
            out[role] = int(number)
        return out

    def output_tokens_for(self, role: str) -> int:
        """The most output tokens a call for this agent role may use: its own limit if one is set, else the general one."""
        return self._parse_role_limits(self.agent_output_tokens_by_role).get(role, self.agent_max_output_tokens)

    @field_validator("guardrails_disabled_rules", mode="after")
    @classmethod
    def _known_guardrail_rules(cls, value: str) -> str:
        from .guardrails.scan import parse_disabled

        parse_disabled(value)   # raises with the list of valid rules if a name is unknown or may not be switched off
        return value

    @property
    def guardrails_disabled(self) -> frozenset[str]:
        from .guardrails.scan import parse_disabled

        return parse_disabled(self.guardrails_disabled_rules)

    @field_validator("agent_temperature", mode="before")
    @classmethod
    def _blank_temperature_is_unset(cls, value: Any) -> Any:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("app_mode", mode="before")
    @classmethod
    def _normalise_mode(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value

    @property
    def workspaces_path(self) -> Path:
        """Where each project's generated code lives: beside the database, in the git-ignored data folder. One folder per project."""
        return self.db_path.parent / "workspaces"

    @property
    def db_path(self) -> Path:
        base = Path(self.data_dir) if self.data_dir.strip() else Path(__file__).resolve().parent.parent / "data"
        return base / "sdlc_workbench.db"

    @property
    def context_limits(self):
        from .context.types import Limits

        return Limits(
            max_file_bytes=self.context_max_file_mb * 1024 * 1024,
            max_pdf_pages=self.context_max_pdf_pages,
            max_docs_per_project=self.context_max_docs_per_project,
            chunk_target_chars=self.context_chunk_target_chars,
        )

    @property
    def recordings_path(self) -> Path:
        base = (
            Path(self.recordings_dir)
            if self.recordings_dir.strip()
            else Path(__file__).resolve().parent.parent / "recordings"
        )
        return base / self.replay_set

    @property
    def endpoint_set(self) -> bool:
        return bool(self.ibm_ica_endpoint.strip())

    @property
    def api_key_set(self) -> bool:
        return bool(self.ibm_ica_api_key.get_secret_value().strip())

    @property
    def openai_key_is_own(self) -> bool:
        """True when GPT models use their own key rather than the shared one."""
        return bool(self.ibm_ica_openai_api_key.get_secret_value().strip())

    def secret_values(self) -> list[str]:
        """Everything that must never appear in an error, a trace or printed output."""
        values = [
            self.ibm_ica_api_key.get_secret_value(),
            self.ibm_ica_openai_api_key.get_secret_value(),
            self.ibm_ica_endpoint,
            self.ibm_ica_user_agent,
        ]
        return [v.strip() for v in values if v and v.strip()]

    @property
    def slots(self) -> dict[str, SlotConfig]:
        return {
            name: SlotConfig(
                name=name,
                model_id=getattr(self, f"{prefix}_model_id"),
                fallback_model_id=getattr(self, f"{prefix}_fallback_model_id"),
                price_input=getattr(self, f"{prefix}_price_input_per_mtok"),
                price_output=getattr(self, f"{prefix}_price_output_per_mtok"),
            )
            for name, prefix in _SLOT_PREFIX.items()
        }


@lru_cache
def get_settings() -> Settings:
    return Settings(_env_file=ENV_FILE)
