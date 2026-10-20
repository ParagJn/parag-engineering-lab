from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings
from .ibm_ica_client import IBMICAClient, IBMICAError


class ProviderError(RuntimeError):
    pass


@dataclass
class AgentResult:
    agent: str
    content: str
    ok: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"agent": self.agent, "content": self.content, "ok": self.ok}


class AzureChatAgent:
    def __init__(self, name: str, base: str, key: str, version: str, deployment: str):
        self.name = name
        self.base = base.rstrip("/")
        self.key = key
        self.version = version
        self.deployment = deployment

    @property
    def configured(self) -> bool:
        return bool(self.base and self.key and self.deployment)

    async def complete(self, system: str, user: str, max_tokens: int = 4000) -> AgentResult:
        if not self.configured:
            raise ProviderError(f"{self.name} is not configured")
        url = f"{self.base}/openai/deployments/{self.deployment}/chat/completions"
        payload = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_completion_tokens": max_tokens,
        }
        headers = {"api-key": self.key, "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, params={"api-version": self.version}, headers=headers, json=payload)
            if response.status_code >= 400 and "max_completion_tokens" in payload:
                payload["max_tokens"] = payload.pop("max_completion_tokens")
                response = await client.post(url, params={"api-version": self.version}, headers=headers, json=payload)
            response.raise_for_status()
        data = response.json()
        return AgentResult(agent=self.name, content=data["choices"][0]["message"]["content"].strip())


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

    async def list_models(self) -> dict[str, Any]:
        if not self.configured:
            raise ProviderError("SAP AI Core is not configured")
        token = await self._token()
        headers = {
            "Authorization": f"Bearer {token}",
            "AI-Resource-Group": self.settings.sap_resource_group,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(self.settings.sap_model_discovery_url, headers=headers)
            response.raise_for_status()
        return response.json()

    async def describe_image(self, image_data: str, media_type: str, location: str) -> str:
        """Call Anthropic vision via SAP AI Core to describe an image as markdown."""
        if not self.configured:
            return ""
        token = await self._token()
        headers = {
            "Authorization": f"Bearer {token}",
            "AI-Resource-Group": self.settings.sap_resource_group,
            "Content-Type": "application/json",
        }
        system_text = (
            "You are an expert document analyst with strong visual interpretation skills. "
            "Analyse the provided image and describe its content comprehensively, focusing on "
            "all text, charts, graphs, tables, diagrams, data visualisations, and any strategic "
            "or business-relevant information visible in the image. Be precise and structured."
        )
        user_content = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_data,
                },
            },
            {
                "type": "text",
                "text": (
                    f"This image is from {location} of the uploaded document. "
                    "Provide a comprehensive markdown description of everything visible: "
                    "all text, data from charts/graphs/tables, descriptions of diagrams, "
                    "and any strategic or business insights."
                ),
            },
        ]
        payload: dict[str, Any] = {
            "config": {
                "modules": {
                    "prompt_templating": {
                        "prompt": {
                            "template": [
                                {"role": "system", "content": system_text},
                                {"role": "user", "content": user_content},
                            ]
                        },
                        "model": {
                            "name": self.model,
                            "params": {"max_tokens": 1500, "temperature": 0.1},
                        },
                    }
                }
            },
            "placeholder_values": {},
        }
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(self.settings.sap_api_url, headers=headers, json=payload)
            if response.status_code >= 400:
                return ""
        data = response.json()
        return _extract_content(data).strip()

    async def complete(self, system: str, user: str, max_tokens: int = 4000) -> AgentResult:
        if not self.configured:
            raise ProviderError("SAP AI Core completion endpoint is not configured")
        token = await self._token()
        headers = {
            "Authorization": f"Bearer {token}",
            "AI-Resource-Group": self.settings.sap_resource_group,
            "Content-Type": "application/json",
        }
        params: dict[str, Any] = {"max_tokens": max_tokens, "temperature": 0.2}
        if self.thinking:
            thinking: dict[str, Any] = {"type": self.settings.sap_thinking_mode}
            if self.settings.sap_thinking_mode == "enabled":
                thinking["budget_tokens"] = self.settings.sap_thinking_budget_tokens
            params["thinking"] = thinking

        payload: dict[str, Any] = {
            "config": {
                "modules": {
                    "prompt_templating": {
                        "prompt": {
                            "template": [
                                {"role": "system", "content": system},
                                {"role": "user", "content": user},
                            ]
                        },
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
    """IBM ICA (OpenAI-compatible chat completions) agent with one content-filter fallback retry."""

    def __init__(self, settings: Settings, name: str, model: str, fallback_model: str = ""):
        self.settings = settings
        self.name = name
        self.model = model or settings.ibm_ica_model_id
        self.fallback_model = fallback_model if fallback_model and fallback_model != self.model else ""

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
            raise ProviderError(f"IBM ICA error: {err}") from err
        if result.get("finish_reason") == "content_filter":
            raise ContentFilterError(f"IBM ICA response from {model} was blocked by the content filter.")
        result["model"] = model
        return result

    async def _chat_with_fallback(self, messages: list[dict[str, Any]], max_tokens: int) -> dict[str, Any]:
        try:
            return await self._chat(self.model, messages, max_tokens)
        except ContentFilterError:
            if not self.fallback_model:
                raise
            return await self._chat(self.fallback_model, messages, max_tokens)

    async def complete(self, system: str, user: str, max_tokens: int = 4000) -> AgentResult:
        if not self.configured:
            raise ProviderError("IBM ICA is not configured")
        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        result = await self._chat_with_fallback(messages, max_tokens)
        return AgentResult(agent=f"{self.name} ({result['model']})", content=result["text"].strip())

    async def chat_messages(self, system: str, history: list[dict[str, str]], max_tokens: int = 3000) -> AgentResult:
        """Multi-turn completion: history is a list of {role, content}."""
        if not self.configured:
            raise ProviderError("IBM ICA is not configured")
        messages = ([{"role": "system", "content": system}] if system else []) + history
        result = await self._chat_with_fallback(messages, max_tokens)
        return AgentResult(agent=f"{self.name} ({result['model']})", content=result["text"].strip())

    async def describe_image(self, image_data: str, media_type: str, location: str) -> str:
        if not self.configured:
            return ""
        messages = [
            {"role": "system", "content": _VISION_SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_data}"}},
                    {"type": "text", "text": _vision_prompt(location)},
                ],
            },
        ]
        result = await self._chat_with_fallback(messages, 1500)
        return result["text"].strip()


_VISION_SYSTEM = (
    "You are an expert document analyst with strong visual interpretation skills. "
    "Analyse the provided image and describe its content comprehensively, focusing on "
    "all text, charts, graphs, tables, diagrams, data visualisations, and any strategic "
    "or business-relevant information visible in the image. Be precise and structured."
)


def _vision_prompt(location: str) -> str:
    return (
        f"This image is from {location} of the uploaded document. "
        "Provide a comprehensive markdown description of everything visible: "
        "all text, data from charts/graphs/tables, descriptions of diagrams, "
        "and any strategic or business insights."
    )


PROVIDERS = ("ibm_ica", "sap")


def normalize_provider(provider: str | None) -> str:
    return provider if provider in PROVIDERS else "ibm_ica"


def build_provider_agents(settings: Settings, provider: str, thinking_mode: bool = True) -> dict[str, Any]:
    """Return the four role agents (architect, challenger, validator, synthesizer) plus a vision agent."""
    provider = normalize_provider(provider)
    if provider == "sap":
        architect = SapCompletionAgent(settings, "Anthropic Strategy Architect", settings.sap_anthropic_model, thinking=thinking_mode)
        challenger = SapCompletionAgent(settings, "Gemini Cost and Execution Challenger", settings.sap_gemini_model)
        synthesizer = AzureChatAgent(
            "GPT-5.4 Strategy Synthesizer",
            settings.azure_openai_gpt54_base,
            settings.azure_openai_gpt54_key,
            settings.azure_openai_gpt54_version,
            settings.azure_openai_gpt54_deployment,
        )
        validator = AzureChatAgent(
            "GPT-5.3 Codex Validator",
            settings.azure_openai_gpt53codex_base,
            settings.azure_openai_gpt53codex_key,
            settings.azure_openai_gpt53codex_version,
            settings.azure_openai_gpt53codex_deployment,
        )
        vision = SapCompletionAgent(settings, "Anthropic Image Analyst", settings.sap_anthropic_model)
    else:
        primary = settings.ibm_ica_model_id
        fallback = settings.ibm_ica_fallback_model_id
        architect = IcaCompletionAgent(settings, "ICA Strategy Architect", primary, fallback)
        # Cost challenger prefers the Gemini model on ICA when one is configured
        challenger = IcaCompletionAgent(
            settings, "ICA Cost and Execution Challenger", settings.ibm_ica_gemini_model_id or primary, fallback
        )
        validator = IcaCompletionAgent(
            settings, "ICA Validator", settings.ibm_ica_validator_model_id or primary, fallback
        )
        synthesizer = IcaCompletionAgent(
            settings, "ICA Strategy Synthesizer", settings.ibm_ica_synthesizer_model_id or primary, fallback
        )
        vision = IcaCompletionAgent(settings, "ICA Image Analyst", primary, fallback)
    return {
        "architect": architect,
        "challenger": challenger,
        "validator": validator,
        "synthesizer": synthesizer,
        "vision": vision,
    }


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

    for key in ("orchestration_result", "intermediate_results", "module_results", "llm", "content", "completion", "output_text", "result"):
        if key in data:
            return _extract_content(data[key])

    if "text" in data:
        return str(data["text"])
    return str(data)
