from __future__ import annotations

from ..errors import ProviderNotWired
from ..types import LLMRequest, ProviderResponse


class UnwiredProvider:
    """Stands in until the real ICA client (S03) and replay (S04) exist."""

    label = "none (wired in S03/S04)"

    async def complete(self, model_id: str, request: LLMRequest) -> ProviderResponse:
        raise ProviderNotWired("no model provider is wired yet; the ICA client arrives in step S03")
