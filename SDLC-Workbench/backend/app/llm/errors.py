from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class LLMError(Exception):
    """Base for everything the gateway raises on purpose."""


# ---- raised by providers; the gateway decides what each one means ----------

class ProviderError(LLMError):
    kind = "error"


class TransientProviderError(ProviderError):
    """Timeout, rate limit or server error: worth retrying."""

    kind = "transient"


class ContentFilterBlocked(ProviderError):
    """The provider refused this prompt. The same model will refuse it again."""

    kind = "content_filter"


class AuthenticationFailed(ProviderError):
    """The credentials were rejected. One key serves every model, so no fallback helps."""

    kind = "auth"


class BadRequest(ProviderError):
    """The provider rejected the request itself: a bug on our side."""

    kind = "bad_request"


class ReplayMiss(ProviderError):
    """Replay mode has no recording for this exact request. Another model would miss too."""

    kind = "replay_miss"


class ModelAccessDenied(ProviderError):
    """The key is fine, but it may not use this particular model. Another model may still work."""

    kind = "model_access_denied"


class ModelNotFound(ProviderError):
    """The service does not know this model ID. Another model may still work."""

    kind = "model_not_found"


class BadResponse(ProviderError):
    """The service answered, but with nothing usable (not JSON, no reply, or an empty reply)."""

    kind = "bad_response"


class TlsVerificationFailed(ProviderError):
    """The service's certificate was rejected. A different model would be rejected the same way."""

    kind = "tls"


class ProviderNotWired(LLMError):
    """No real provider is connected yet."""


# ---- raised by the gateway --------------------------------------------------

class RoutingConfigError(ValueError):
    """routing.yaml, a project override or a slot name is wrong."""


class SlotNotConfigured(LLMError):
    """The slot has neither a model nor a fallback, so there is nothing to call."""


@dataclass(frozen=True)
class AttemptError:
    model_id: str
    kind: str
    message: str


class LLMCallFailed(LLMError):
    def __init__(self, message: str, attempts: list[AttemptError]):
        super().__init__(message)
        self.attempts = tuple(attempts)

    @property
    def retryable_elsewhere(self) -> bool:
        """True when a different model might succeed where this one failed."""
        return bool(self.attempts) and self.attempts[-1].kind in (
            "transient", "content_filter", "model_not_found", "model_access_denied", "bad_response",
        )


class ReviewerUnavailable(LLMError):
    """The reviewer could not run. The user picks another model family from `options`."""

    def __init__(self, slot: str, options: list[Any], cause: BaseException | None = None):
        super().__init__(f"reviewer slot '{slot}' is unavailable; choose another model family")
        self.slot = slot
        self.options = tuple(options)
        self.cause = cause
