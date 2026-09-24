"""Model service for IBM ICA integration."""

import asyncio

from config import config
from ibm_ica_client import IBMICAClient, IBMICAError


class ModelConfigError(RuntimeError):
    """Raised when IBM ICA credentials are missing or invalid."""
    pass


class ModelRateLimitError(RuntimeError):
    """Raised when the model gateway rate-limits the request (HTTP 429)."""
    pass


class ModelService:
    """Service for interacting with the AI model via IBM ICA."""

    def __init__(self):
        """Initialize model service."""
        try:
            config.validate()
        except ValueError as e:
            raise ModelConfigError(str(e)) from e

        self.client = IBMICAClient(
            endpoint=config.IBM_ICA_ENDPOINT,
            api_key=config.IBM_ICA_API_KEY,
            model_id=config.IBM_ICA_MODEL_ID,
            timeout=config.MODEL_TIMEOUT,
            insecure_tls=config.IBM_ICA_INSECURE_TLS,
        )

    async def generate(
        self,
        prompt: str,
        platform: str,
        *,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """
        Generate a response from the model.

        Args:
            prompt: The full user prompt
            platform: Target skill platform ("anthropic", "gemini" or "chatgpt"),
                mapped to an ICA model via config.MODEL_CHOICES
            system: Optional system message
            max_tokens: Override for config.MAX_TOKENS

        Returns:
            The response text
        """
        model_id = config.MODEL_CHOICES.get(platform, config.IBM_ICA_MODEL_ID)
        messages = [{"role": "system", "content": system}] if system else []
        messages.append({"role": "user", "content": prompt})
        try:
            # Client is synchronous (urllib) — run it off the event loop
            result = await asyncio.to_thread(
                self.client.chat,
                messages,
                max_tokens=max_tokens or config.MAX_TOKENS,
                model_id=model_id,
            )
        except IBMICAError as e:
            if getattr(e, "http_code", None) == 429:
                raise ModelRateLimitError(str(e)) from e
            raise RuntimeError(f"Model generation failed: {e}") from e
        return result["text"]


# Singleton instance
_model_service: ModelService | None = None


def get_model_service() -> ModelService:
    """Get model service singleton."""
    global _model_service
    if _model_service is None:
        _model_service = ModelService()
    return _model_service
