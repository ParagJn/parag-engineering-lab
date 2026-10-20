from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from config import Settings
from ibm_ica_client import IBMICAClient, IBMICAError


class ProviderError(RuntimeError):
    pass


@dataclass
class AgentResult:
    agent: str
    content: str
    ok: bool = True


class SapCompletionAgent:
    def __init__(self, settings: Settings, name: str, model: str, thinking: bool = False):
        self.settings = settings
        self.name = name
        self.model = model
        self.thinking = thinking

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.sap_client_id
            and self.settings.sap_client_secret
            and self.settings.sap_token_url
            and self.settings.sap_api_url
        )

    async def _token(self) -> str:
        token_payload = {
            "grant_type": "client_credentials",
            "client_id": self.settings.sap_client_id,
            "client_secret": self.settings.sap_client_secret,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(self.settings.sap_token_url, headers=headers, data=token_payload)
            response.raise_for_status()
        return response.json()["access_token"]

    async def complete(self, system: str, user: str, max_tokens: int = 4000) -> AgentResult:
        if not self.configured:
            raise ProviderError("SAP AI Core is not configured")
        token = await self._token()
        headers = {
            "Authorization": f"Bearer {token}",
            "AI-Resource-Group": self.settings.sap_resource_group,
            "Content-Type": "application/json",
        }
        params: dict[str, Any] = {"max_tokens": max_tokens}
        if self.thinking:
            thinking: dict[str, Any] = {"type": self.settings.sap_thinking_mode}
            if self.settings.sap_thinking_mode == "enabled":
                thinking["budget_tokens"] = self.settings.sap_thinking_budget_tokens
            params["thinking"] = thinking

        template: list[dict[str, str]] = []
        if system:
            template.append({"role": "system", "content": system})
        template.append({"role": "user", "content": user})

        payload: dict[str, Any] = {
            "config": {
                "modules": {
                    "prompt_templating": {
                        "prompt": {"template": template},
                        "model": {
                            "name": self.model,
                            "params": params,
                        },
                    }
                }
            },
            "placeholder_values": {},
        }
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.post(self.settings.sap_api_url, headers=headers, json=payload)
            if response.status_code >= 400 and "thinking" in params:
                params.pop("thinking")
                response = await client.post(self.settings.sap_api_url, headers=headers, json=payload)
            if response.status_code >= 400:
                raise ProviderError(f"SAP AI Core returned {response.status_code}: {response.text[:800]}")
        data = response.json()
        content = _extract_content(data)
        return AgentResult(agent=f"{self.name} ({self.model})", content=content.strip())


class ContentFilterError(ProviderError):
    pass


class IcaCompletionAgent:
    def __init__(self, settings: Settings, name: str, model: str, fallback_model: str = ""):
        self.settings = settings
        self.name = name
        self.model = model
        self.fallback_model = fallback_model if fallback_model != model else ""

    @property
    def configured(self) -> bool:
        return bool(self.settings.ibm_ica_endpoint and self.settings.ibm_ica_api_key)

    async def complete(self, system: str, user: str, max_tokens: int = 4000) -> AgentResult:
        if not self.configured:
            raise ProviderError("IBM ICA is not configured")

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
        return AgentResult(agent=f"{self.name} ({result['model']})", content=result["text"].strip())

    async def _chat(self, model: str, messages: list[dict[str, str]], max_tokens: int) -> dict[str, Any]:
        print(
            f"[IBM_ICA] agent={self.name!r} model={model!r} "
            f"endpoint={self.settings.ibm_ica_endpoint!r}",
            flush=True,
        )
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
            print(f"[IBM_ICA] agent={self.name!r} model={model!r} BLOCKED by content_filter", flush=True)
            raise ContentFilterError(
                f"IBM ICA response from {model} was blocked by the content filter "
                "(likely a sensitive topic in today's stories). Try SAP Models or different sources."
            )
        result["model"] = model
        return result


def build_agent(settings: Settings, name: str, kind: str, provider: str = "ibm_ica"):
    """Build the completion agent for the given provider ("ibm_ica" or "sap").

    `kind` selects which model to use: "claude" or "gemini".
    """
    if provider == "sap":
        model = settings.sap_anthropic_model if kind == "claude" else settings.sap_gemini_model
        return SapCompletionAgent(settings, name, model)

    if kind == "claude":
        return IcaCompletionAgent(
            settings, name, settings.ibm_ica_model_id, settings.ibm_ica_fallback_model_id
        )
    return IcaCompletionAgent(settings, name, settings.ibm_ica_gemini_model_id)


def _extract_content(data: Any) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        parts = [_extract_content(item) for item in data]
        return "\n".join(part for part in parts if part)
    if not isinstance(data, dict):
        return str(data)

    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        if isinstance(message, dict) and message.get("content"):
            return _extract_content(message["content"])
        if isinstance(choices[0], dict) and choices[0].get("text"):
            return str(choices[0]["text"])

    for key in (
        "orchestration_result", "intermediate_results", "module_results",
        "llm", "content", "completion", "output_text", "result",
    ):
        if key in data:
            return _extract_content(data[key])

    if "text" in data:
        return str(data["text"])
    return str(data)
