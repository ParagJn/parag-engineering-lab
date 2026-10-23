from __future__ import annotations

import asyncio
import json
from typing import Any

from .config import Settings
from .ibm_ica_client import IBMICAClient, IBMICAError


class LLMError(RuntimeError):
    pass


class ContentFilterError(LLMError):
    pass


class IcaLLM:
    """IBM ICA chat completions with one content-filter fallback retry."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = settings.ibm_ica_model_id
        fallback = settings.ibm_ica_fallback_model_id
        self.fallback_model = fallback if fallback and fallback != self.model else ""

    @property
    def configured(self) -> bool:
        return bool(self.settings.ibm_ica_endpoint and self.settings.ibm_ica_api_key)

    async def _chat(self, model: str, messages: list[dict[str, Any]], max_tokens: int) -> dict[str, Any]:
        client = IBMICAClient(
            endpoint=self.settings.ibm_ica_endpoint,
            api_key=self.settings.ibm_ica_api_key,
            model_id=model,
        )
        try:
            result = await asyncio.to_thread(client.chat, messages, max_tokens)
        except IBMICAError as err:
            raise LLMError(f"IBM ICA error: {err}") from err
        if result.get("finish_reason") == "content_filter":
            raise ContentFilterError(f"IBM ICA response from {model} was blocked by the content filter.")
        result["model"] = model
        return result

    async def complete(self, system: str, user: str, max_tokens: int) -> dict[str, Any]:
        """Return {"text", "model", "finish_reason"}."""
        if not self.configured:
            raise LLMError("IBM ICA is not configured. Set IBM_ICA_ENDPOINT and IBM_ICA_API_KEY in backend/.env.")
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        try:
            result = await self._chat(self.model, messages, max_tokens)
        except ContentFilterError:
            if not self.fallback_model:
                raise
            result = await self._chat(self.fallback_model, messages, max_tokens)
        if not result["text"].strip():
            raise LLMError("The model returned an empty response. Try again.")
        return result

    async def complete_json(self, system: str, user: str, max_tokens: int) -> tuple[dict[str, Any], str]:
        """Ask for JSON and parse it. Returns (object, model used)."""
        result = await self.complete(system, user, max_tokens)
        if result.get("finish_reason") == "length":
            raise LLMError("The model's answer was cut off before the diagram was complete. Try a shorter document or a simpler request.")
        try:
            return extract_json(result["text"]), result["model"]
        except ValueError as err:
            raise LLMError(f"The model did not return valid JSON. {err}") from err


def extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of a model reply, tolerating code fences and chatter."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        cleaned = cleaned.rsplit("```", 1)[0]
    start = cleaned.find("{")
    if start < 0:
        raise ValueError("No JSON object found in the reply.")
    try:
        value, _ = json.JSONDecoder().raw_decode(cleaned[start:])
    except json.JSONDecodeError as err:
        raise ValueError(f"Could not parse the reply as JSON ({err.msg} at position {err.pos}).") from err
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object.")
    return value
