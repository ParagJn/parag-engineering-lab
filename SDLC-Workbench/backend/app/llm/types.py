from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Usage:
    tokens_in: int
    tokens_out: int


@dataclass(frozen=True)
class Message:
    role: str  # "user" or "assistant"
    content: str


@dataclass(frozen=True)
class LLMRequest:
    role: str
    messages: tuple[Message, ...]
    system: str = ""
    max_tokens: int = 4096
    temperature: float | None = None
    project_id: str | None = None
    phase_key: str | None = None
    run_id: str | None = None

    @classmethod
    def user(cls, role: str, text: str, **kwargs) -> "LLMRequest":
        return cls(role=role, messages=(Message("user", text),), **kwargs)


@dataclass(frozen=True)
class ProviderResponse:
    text: str
    usage: Usage | None = None
    finish_reason: str | None = None


@dataclass(frozen=True)
class LLMResult:
    text: str
    call_id: str
    role: str
    slot: str
    requested_model: str
    served_model: str
    family: str
    fallback_used: bool
    attempts: int
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost_usd: float | None
    finish_reason: str | None
    trace_ids: tuple[int, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ReviewerOption:
    """A model family the user could pick to review an artefact."""

    slot: str
    model_id: str
    family: str
    independent: bool | None  # None when a family is unknown
    price_input: float | None
    price_output: float | None
    priced: bool


@dataclass(frozen=True)
class Independence:
    verdict: str  # "independent" | "same_family" | "unverified"
    author_family: str
    reviewer_family: str
    fell_back: bool


@dataclass(frozen=True)
class ReviewOutcome:
    result: LLMResult
    independence: Independence
