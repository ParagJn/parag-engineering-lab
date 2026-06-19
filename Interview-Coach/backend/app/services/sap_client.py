import asyncio
import time
import logging

import httpx

logger = logging.getLogger(__name__)


class SAPAIClient:
    """
    Async client for SAP AI Core API.
    Handles OAuth2 token acquisition (with caching) and chat completion requests.
    All three models (GPT, Claude, Gemini) are accessed via the same endpoint
    with the model name specified in the request body.
    """

    def __init__(self, config: dict):
        self.client_id = config["client_id"]
        self.client_secret = config["client_secret"]
        self.token_url = config["token_url"]
        self.api_url = config["api_url"]
        self.resource_group = config["resource_group"]
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0
        self._refresh_buffer = config.get("token_refresh_buffer_seconds", 60)
        self._request_timeout = config.get("request_timeout_seconds", 120)
        self._token_timeout = config.get("token_request_timeout_seconds", 30)
        self._lock = asyncio.Lock()

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
