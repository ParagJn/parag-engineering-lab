from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings


class ProviderError(RuntimeError):
    pass


@dataclass
class AgentResult:
    agent: str
    content: str
    ok: bool = True


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
