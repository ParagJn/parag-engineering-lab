"""IBM ICA completion agent (same pattern as the other lab projects) plus JSON helpers."""

import asyncio
import json
import re
from typing import Any

from config import Settings
from ibm_ica_client import IBMICAClient, IBMICAError


class ProviderError(RuntimeError):
    pass


class ContentFilterError(ProviderError):
    pass


class IcaCompletionAgent:
    def __init__(self, settings: Settings, name: str):
        self.settings = settings
        self.name = name
        self.model = settings.ibm_ica_model_id
        fallback = settings.ibm_ica_fallback_model_id
        self.fallback_model = fallback if fallback != self.model else ""

    @property
    def configured(self) -> bool:
        return self.settings.llm_configured

    async def complete(self, system: str, user: str, max_tokens: int = 8000) -> str:
        if not self.configured:
            raise ProviderError("IBM ICA is not configured (set IBM_ICA_ENDPOINT and IBM_ICA_API_KEY in .env)")

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        try:
            result = await self._chat(self.model, messages, max_tokens)
        except ContentFilterError:
            if not self.fallback_model:
                raise
            print(
                f"[IBM_ICA] agent={self.name!r} content_filter on {self.model!r}, "
                f"retrying once with fallback {self.fallback_model!r}",
                flush=True,
            )
            result = await self._chat(self.fallback_model, messages, max_tokens)
        return result["text"].strip()

    async def complete_json(self, system: str, user: str, max_tokens: int = 8000) -> Any:
        """Complete and parse a JSON reply; one repair round-trip if the reply isn't valid JSON."""
        text = await self.complete(system, user, max_tokens)
        try:
            return extract_json(text)
        except ValueError as err:
            print(f"[IBM_ICA] agent={self.name!r} invalid JSON, asking for repair: {err}", flush=True)
            repair = (
                f"{user}\n\nYour previous reply was not valid JSON ({err}). "
                "Reply again with ONLY the JSON object, no prose and no code fences."
            )
            return extract_json(await self.complete(system, repair, max_tokens))

    async def _chat(self, model: str, messages: list[dict[str, str]], max_tokens: int) -> dict[str, Any]:
        client = IBMICAClient(
            endpoint=self.settings.ibm_ica_endpoint,
            api_key=self.settings.ibm_ica_api_key,
            model_id=model,
        )
        try:
            result = await asyncio.to_thread(client.chat, messages, max_tokens)
        except IBMICAError as err:
            print(f"[IBM_ICA] agent={self.name!r} FAILED: {err!r}", flush=True)
            raise ProviderError(f"IBM ICA error: {err}") from err
        if result.get("finish_reason") == "content_filter":
            raise ContentFilterError(f"IBM ICA response from {model} was blocked by the content filter.")
        if result.get("finish_reason") == "length":
            print(f"[IBM_ICA] agent={self.name!r} reply truncated at max_tokens={max_tokens}", flush=True)
        result["model"] = model
        return result


def build_agent(settings: Settings, name: str) -> IcaCompletionAgent:
    return IcaCompletionAgent(settings, name)


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def extract_json(text: str) -> Any:
    """Pull the first JSON object/array out of an LLM reply (tolerates code fences and prose)."""
    candidates = [m.group(1) for m in _FENCE.finditer(text)] + [text]
    for cand in candidates:
        cand = cand.strip()
        start = min((i for i in (cand.find("{"), cand.find("[")) if i >= 0), default=-1)
        if start < 0:
            continue
        try:
            obj, _ = json.JSONDecoder().raw_decode(cand[start:])
            return obj
        except json.JSONDecodeError:
            continue
    raise ValueError("no JSON object found in reply")
