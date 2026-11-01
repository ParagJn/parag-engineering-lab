from __future__ import annotations

from typing import Protocol

from ..types import LLMRequest, ProviderResponse


class Provider(Protocol):
    """Talks to a model. Raises the typed errors in llm.errors so the gateway can react."""

    label: str

    async def complete(self, model_id: str, request: LLMRequest) -> ProviderResponse: ...
