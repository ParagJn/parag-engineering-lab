import asyncio
import time
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class SAPAIClient:
    """
    Async client for SAP AI Core API.
    Handles OAuth2 token acquisition (with caching) and chat completion requests.
    All three models (GPT, Claude, Gemini) are accessed via the same endpoint
    with the model name specified in the request body.
    """

    def __init__(self, config: dict, settings_service=None):
        full_config = config if "sap_ai_core" in config else {}
        sap_config = full_config.get("sap_ai_core", config)

        self.client_id = sap_config["client_id"]
        self.client_secret = sap_config["client_secret"]
        self.token_url = sap_config["token_url"]
        self.api_url = sap_config["api_url"]
        self.resource_group = sap_config["resource_group"]
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._refresh_buffer = sap_config.get("token_refresh_buffer_seconds", 60)
        self._request_timeout = sap_config.get("request_timeout_seconds", 120)
        self._token_timeout = sap_config.get("token_request_timeout_seconds", 30)
        self._lock = asyncio.Lock()
        self.settings_service = settings_service
        self.sap_models = full_config.get("models", {})
        self.direct_models = full_config.get("direct_models", {})
        self.direct_api = full_config.get("direct_api", {})

    async def get_access_token(self) -> str:
        """Return a valid OAuth2 bearer token, refreshing if necessary."""
        async with self._lock:
            if self._token and time.time() < self._token_expiry - self._refresh_buffer:
                return self._token

            logger.info("Refreshing SAP AI Core access token…")
            async with httpx.AsyncClient(timeout=self._token_timeout) as client:
                response = await client.post(
                    self.token_url,
                    data={
                        "grant_type": "client_credentials",
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                response.raise_for_status()
                data = response.json()
                self._token = data["access_token"]
                self._token_expiry = time.time() + data.get("expires_in", 3600)
                logger.info("Access token refreshed. Expires in %s seconds.", data.get("expires_in"))
                return self._token

    async def complete(
        self,
        model: str,
        messages: list,
        temperature: float = 0.7,
    ) -> str:
        """
        Send a chat completion request via SAP AI Core Orchestration API.

        Uses the SAP AI Core orchestration payload format:
          config.modules.prompt_templating.{prompt.template, model.{name, params}}

        Note: temperature is not passed — the SAP AI Core hosted models only
        support their default temperature value and reject custom values.

        Args:
            model: Model identifier (e.g. 'gpt-5.5', 'anthropic--claude-4.7-opus', 'gemini-2.5-pro')
            messages: OpenAI-style messages list [{"role": ..., "content": ...}]
            temperature: Accepted for API compatibility but not forwarded to SAP AI Core.

        Returns:
            The assistant's reply as a string.
        """
        settings = await self._get_settings()
        if settings.get("provider_mode") == "custom":
            return await self._complete_with_custom_provider(model, messages, temperature, settings)

        token = await self.get_access_token()

        # SAP AI Core Orchestration API format
        # Note: params dict is intentionally empty — custom temperature is unsupported
        payload = {
            "config": {
                "modules": {
                    "prompt_templating": {
                        "prompt": {
                            "template": messages,
                        },
                        "model": {
                            "name": model,
                            "version": "latest",
                            "params": {},
                        },
                    }
                }
            }
        }

        logger.debug("Calling SAP AI Core Orchestration with model=%s", model)

        async with httpx.AsyncClient(timeout=self._request_timeout) as client:
            response = await client.post(
                self.api_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "AI-Resource-Group": self.resource_group,
                },
            )
            if response.status_code >= 400:
                logger.error(
                    "SAP AI Core error %d for model=%s: %s",
                    response.status_code,
                    model,
                    response.text[:500],
                )
            response.raise_for_status()
            data = response.json()

        return data["final_result"]["choices"][0]["message"]["content"]

    async def _get_settings(self) -> dict:
        if not self.settings_service:
            return {"provider_mode": "built_in", "api_keys": {}}
        return await self.settings_service.get_settings()

    def _model_alias(self, model: str) -> str:
        for alias, configured_model in self.sap_models.items():
            if model == configured_model:
                return alias
        lowered = model.lower()
        if "claude" in lowered or "anthropic" in lowered:
            return "claude"
        if "gemini" in lowered:
            return "gemini"
        return "gpt"

    async def _complete_with_custom_provider(
        self,
        model: str,
        messages: list,
        temperature: float,
        settings: dict,
    ) -> str:
        alias = self._model_alias(model)
        api_keys = settings.get("api_keys", {})
        provider = self._provider_for_alias(alias, settings)
        logger.info("Custom AI provider selected: requested=%s provider=%s", alias, provider)

        if provider == "anthropic":
            return await self._complete_anthropic(messages, temperature, api_keys.get("anthropic"))
        if provider == "gemini":
            return await self._complete_gemini(messages, temperature, api_keys.get("gemini"))
        return await self._complete_openai(messages, temperature, api_keys.get("openai"))

    def _provider_for_alias(self, alias: str, settings: dict) -> str:
        preferred = {
            "gpt": "openai",
            "claude": "anthropic",
            "gemini": "gemini",
        }.get(alias, "openai")
        available = self._available_custom_providers(settings)
        if preferred in available:
            return preferred
        if not available:
            raise ValueError("At least one enabled API key is required when custom API keys are enabled.")
        return available[0]

    def _available_custom_providers(self, settings: dict) -> list:
        api_keys = settings.get("api_keys", {})
        enabled = settings.get("enabled_providers") or []
        if not enabled:
            enabled = [
                provider
                for provider in ("openai", "anthropic", "gemini")
                if api_keys.get(provider)
            ]
        return [
            provider
            for provider in ("openai", "anthropic", "gemini")
            if provider in enabled and api_keys.get(provider)
        ]

    async def verify_custom_providers(self, settings: dict) -> list:
        providers = self._available_custom_providers(settings)
        if not providers:
            raise ValueError("Enable at least one provider with an API key before testing.")

        tasks = [self._verify_provider(provider, settings["api_keys"].get(provider)) for provider in providers]
        return await asyncio.gather(*tasks)

    async def _verify_provider(self, provider: str, api_key: Optional[str]) -> dict:
        messages = [
            {"role": "system", "content": "You are a connectivity check."},
            {"role": "user", "content": "Reply with OK only."},
        ]
        try:
            if provider == "anthropic":
                await self._complete_anthropic(messages, 0, api_key, max_tokens=8)
            elif provider == "gemini":
                await self._complete_gemini(messages, 0, api_key, max_tokens=8)
            else:
                await self._complete_openai(messages, 0, api_key, max_tokens=8)
            return {"provider": provider, "ok": True, "message": "Connection verified."}
        except httpx.HTTPStatusError as exc:
            detail = self._safe_http_error(exc)
            return {"provider": provider, "ok": False, "message": detail}
        except Exception as exc:
            return {"provider": provider, "ok": False, "message": str(exc)}

    def _safe_http_error(self, exc: httpx.HTTPStatusError) -> str:
        status_code = exc.response.status_code
        if status_code in (401, 403):
            return "Authentication failed. Check the API key and account access."
        if status_code == 429:
            return "Provider rate limit reached. Try again later."
        if 400 <= status_code < 500:
            return f"Provider rejected the request with HTTP {status_code}."
        return f"Provider service returned HTTP {status_code}."

    async def _complete_openai(
        self,
        messages: list,
        temperature: float,
        api_key: Optional[str],
        max_tokens: Optional[int] = None,
    ) -> str:
        if not api_key:
            raise ValueError("OpenAI API key is required when custom API keys are enabled.")

        payload = {
            "model": self.direct_models.get("gpt", "gpt-4o-mini"),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.direct_api.get("max_tokens", 4096),
        }
        async with httpx.AsyncClient(timeout=self._request_timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]

    async def _complete_anthropic(
        self,
        messages: list,
        temperature: float,
        api_key: Optional[str],
        max_tokens: Optional[int] = None,
    ) -> str:
        if not api_key:
            raise ValueError("Anthropic API key is required when custom API keys are enabled.")

        system_parts = [m.get("content", "") for m in messages if m.get("role") == "system"]
        anthropic_messages = [
            {"role": "assistant" if m.get("role") == "assistant" else "user", "content": m.get("content", "")}
            for m in messages
            if m.get("role") != "system"
        ]
        payload = {
            "model": self.direct_models.get("claude", "claude-3-5-sonnet-latest"),
            "system": "\n\n".join(system_parts),
            "messages": anthropic_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or self.direct_api.get("max_tokens", 4096),
        }
        async with httpx.AsyncClient(timeout=self._request_timeout) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                json=payload,
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": self.direct_api.get("anthropic_version", "2023-06-01"),
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()
        return "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )

    async def _complete_gemini(
        self,
        messages: list,
        temperature: float,
        api_key: Optional[str],
        max_tokens: Optional[int] = None,
    ) -> str:
        if not api_key:
            raise ValueError("Gemini API key is required when custom API keys are enabled.")

        system_parts = [m.get("content", "") for m in messages if m.get("role") == "system"]
        contents = [
            {
                "role": "model" if m.get("role") == "assistant" else "user",
                "parts": [{"text": m.get("content", "")}],
            }
            for m in messages
            if m.get("role") != "system"
        ]
        payload = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens or self.direct_api.get("max_tokens", 4096),
            },
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}

        model_name = self.direct_models.get("gemini", "gemini-1.5-pro")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        async with httpx.AsyncClient(timeout=self._request_timeout) as client:
            response = await client.post(
                url,
                params={"key": api_key},
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return "".join(part.get("text", "") for part in parts)
