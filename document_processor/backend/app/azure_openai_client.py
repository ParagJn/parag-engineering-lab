"""Azure OpenAI client for making API calls."""
import logging
import os
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class AzureOpenAIClient:
    """Client for Azure OpenAI API interactions."""

    def __init__(self):
        """Initialize Azure OpenAI client with environment configuration."""
        self.enabled = os.getenv("ENABLE_AI_ENRICHMENT", "false").lower() == "true"
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
        self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate Azure OpenAI configuration."""
        logger.info(f"AI enrichment enabled: {self.enabled}")
        
        if self.enabled:
            if not self.endpoint or not self.api_key or not self.deployment:
                logger.warning("Azure OpenAI configuration incomplete - enrichment will be disabled")
                self.enabled = False
            else:
                logger.info(
                    f"Azure OpenAI configured: endpoint={self.endpoint}, "
                    f"deployment={self.deployment}, api_version={self.api_version}"
                )

    def is_enabled(self) -> bool:
        """Check if AI enrichment is enabled and properly configured."""
        return self.enabled

    def call_chat_completion(
        self,
        messages: List[Dict],
        max_tokens: int = 4000,
    ) -> Optional[str]:
        """
        Make a chat completion API call to Azure OpenAI.
        
        Args:
            messages: List of message dictionaries for the chat
            max_tokens: Maximum tokens in the response
            
        Returns:
            Response text or None if failed
        """
        if not self.enabled:
            return None

        url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version={self.api_version}"
        headers = {"api-key": self.api_key, "Content-Type": "application/json"}
        
        # Use max_completion_tokens for newer API versions
        payload = {
            "messages": messages,
            "max_completion_tokens": max_tokens,
        }

        try:
            with httpx.Client(timeout=60.0) as client:
                logger.info(f"Calling Azure OpenAI API at {self.deployment}...")
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                result = data["choices"][0]["message"]["content"].strip()
                logger.info(f"Azure OpenAI response received (length: {len(result)} chars)")
                return result
        except httpx.HTTPStatusError as e:
            error_detail = e.response.text
            logger.error(
                f"Azure OpenAI HTTP error ({e.response.status_code}): {error_detail}\n"
                f"Endpoint: {self.endpoint}\n"
                f"Deployment: {self.deployment}\n"
                f"API Version: {self.api_version}"
            )
            return None
        except httpx.TimeoutException as e:
            logger.error(f"Azure OpenAI timeout error: Request took longer than 60 seconds")
            return None
        except Exception as e:
            logger.error(f"Azure OpenAI error: {type(e).__name__}: {str(e)}")
            return None


# Global singleton instance
_azure_client = None


def get_azure_client() -> AzureOpenAIClient:
    """Get or create the global Azure OpenAI client instance."""
    global _azure_client
    if _azure_client is None:
        _azure_client = AzureOpenAIClient()
    return _azure_client
