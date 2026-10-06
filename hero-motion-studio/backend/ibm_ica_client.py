"""
Reusable IBM ICA (IBM watsonx Code Assistant) client for chat completions.
Supports multiple endpoint paths, SSL configuration, and comprehensive error handling.
"""

import json
import os
import socket
import ssl
import urllib.error
import urllib.request
from typing import Any


class IBMICAError(RuntimeError):
    """Base exception for IBM ICA client errors."""
    pass


class IBMICAConfigError(IBMICAError):
    """Configuration or validation error."""
    pass


class IBMICAAuthError(IBMICAError):
    """Authentication failure."""
    pass


class IBMICAConnectionError(IBMICAError):
    """Network or connection error."""
    pass


class IBMICAResponseError(IBMICAError):
    """HTTP response error."""
    def __init__(self, message: str, http_code: int | None = None):
        super().__init__(message)
        self.http_code = http_code


class IBMICAClient:
    """
    Client for IBM ICA chat completions API.
    
    Usage:
        client = IBMICAClient(
            endpoint="https://your-ibm-ica-url",
            api_key="your-api-key",
            model_id="claude-opus-5-5"
        )
        
        result = client.chat([
            {"role": "user", "content": "Hello!"}
        ], max_tokens=100)
        
        print(result["text"])
    """
    
    TIMEOUT = 180
    CHAT_PATH = "/v1/chat/completions"

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model_id: str = "claude-opus-5-5",
        timeout: int = TIMEOUT,
        insecure_tls: bool | None = None,
    ):
        """
        Initialize IBM ICA client.
        
        Args:
            endpoint: Base URL of the IBM ICA endpoint
            api_key: API key for authentication
            model_id: Model identifier (default: claude-opus-5-5)
            timeout: Request timeout in seconds
            insecure_tls: Skip SSL verification (for testing only)
        """
        if not endpoint or not endpoint.strip():
            raise IBMICAConfigError("IBM ICA endpoint is required.")
        if not api_key or not api_key.strip():
            raise IBMICAConfigError("IBM ICA API key is required.")

        self.endpoint = endpoint.strip().rstrip("/")
        self.api_key = api_key.strip()
        self.model_id = model_id.strip() or "claude-opus-5-5"
        self.timeout = timeout
        
        # Allow override or read from environment
        if insecure_tls is None:
            insecure_tls = (os.getenv("IBM_ICA_INSECURE_TLS") or "").strip().lower() in {
                "1", "true", "yes", "y"
            }
        self.insecure_tls = insecure_tls
        
        self.ssl_context = self._build_ssl_context()
        base = self.endpoint
        self.chat_url = base if base.endswith(self.CHAT_PATH) else base + self.CHAT_PATH

    def _build_ssl_context(self) -> ssl.SSLContext:
        """Build SSL context with certificate verification."""
        if self.insecure_tls:
            return ssl._create_unverified_context()

        try:
            import certifi
            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return ssl.create_default_context()

    def _call(self, url: str, payload: dict) -> tuple[int, str]:
        """Make HTTP POST request to the API."""
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            },
        )
        print(
            f"[IBM_ICA] -> POST {url} model={payload.get('model')!r} "
            f"key_prefix={self.api_key[:8]}... key_len={len(self.api_key)}",
            flush=True,
        )

        try:
            with urllib.request.urlopen(
                req, timeout=self.timeout, context=self.ssl_context
            ) as resp:
                print(f"[IBM_ICA] <- {resp.status} {url}", flush=True)
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", "replace")[:400]
            message = f"HTTP {err.code} {err.reason}"
            if detail:
                message = f"{message}: {detail}"
            print(f"[IBM_ICA] <- HTTPError {err.code} {url} detail={detail!r}", flush=True)

            if err.code in (401, 403):
                raise IBMICAAuthError(
                    "Authentication failed (invalid key or auth scheme)."
                ) from err
            raise IBMICAResponseError(message, err.code) from err
        except urllib.error.URLError as err:
            reason = getattr(err, "reason", err)
            print(f"[IBM_ICA] <- URLError {url} reason={reason!r}", flush=True)
            if isinstance(reason, ssl.SSLCertVerificationError):
                raise IBMICAConnectionError(
                    "SSL certificate verification failed. "
                    "Install certifi in your venv or set IBM_ICA_INSECURE_TLS=true "
                    "for local connectivity testing."
                ) from err
            raise IBMICAConnectionError(f"Network error: {reason}") from err
        except (TimeoutError, socket.timeout) as err:
            print(f"[IBM_ICA] <- Timeout {url}", flush=True)
            raise IBMICAConnectionError(
                "Request timed out while connecting to IBM ICA."
            ) from err

    @staticmethod
    def _extract_text(raw: str) -> str:
        """Extract text content from API response."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw[:500]

        # OpenAI-style response
        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError):
            pass

        # Anthropic-style response
        try:
            return str(data["content"][0]["text"]).strip()
        except (KeyError, IndexError, TypeError):
            pass

        return json.dumps(data, indent=2)[:800]

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Rough token estimate (4 chars ≈ 1 token)."""
        return max(1, len(text) // 4)

    @staticmethod
    def _extract_usage(
        raw: str, payload_messages: list[dict], reply_text: str
    ) -> tuple[int, int, int, bool]:
        """
        Extract token usage from response.
        
        Returns:
            (prompt_tokens, completion_tokens, total_tokens, is_estimated)
        """
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}

        usage = data.get("usage") if isinstance(data, dict) else None
        if isinstance(usage, dict):
            prompt_tokens = usage.get("prompt_tokens") or usage.get("input_tokens")
            completion_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
            total_tokens = usage.get("total_tokens")

            if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
                if not isinstance(total_tokens, int):
                    total_tokens = prompt_tokens + completion_tokens
                return prompt_tokens, completion_tokens, total_tokens, False

        # Fallback to estimation
        context_text = "\n".join(
            f"{msg.get('role', '')}: {msg.get('content', '')}"
            for msg in payload_messages
            if isinstance(msg, dict)
        )
        prompt_tokens_est = IBMICAClient._estimate_tokens(context_text)
        completion_tokens_est = IBMICAClient._estimate_tokens(reply_text)
        total_tokens_est = prompt_tokens_est + completion_tokens_est
        return prompt_tokens_est, completion_tokens_est, total_tokens_est, True

    def chat(
        self,
        messages: list[dict],
        max_tokens: int = 100,
        model_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Send chat completion request.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            max_tokens: Maximum tokens to generate
            model_id: Override model ID for this request
            
        Returns:
            Dictionary with keys:
                - text: Extracted text response
                - raw: Full JSON response
                - url: Endpoint URL used
                - prompt_tokens: Input tokens
                - completion_tokens: Output tokens
                - total_tokens: Sum of input + output
                - estimated: Whether token counts are estimates
        """
        if not isinstance(messages, list) or not messages:
            raise IBMICAConfigError("At least one message is required.")

        payload = {
            "model": model_id or self.model_id,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        print(f"[IBM_ICA] chat() url={self.chat_url!r}", flush=True)

        _, raw = self._call(self.chat_url, payload)
        try:
            _diag = json.loads(raw)
            _finish = _diag.get("choices", [{}])[0].get("finish_reason")
            print(
                f"[IBM_ICA] chat() finish_reason={_finish!r} usage={_diag.get('usage')!r} "
                f"reply_len={len(raw)}",
                flush=True,
            )
        except Exception:
            pass
        reply = self._extract_text(raw)
        prompt_tokens, completion_tokens, total_tokens, estimated = self._extract_usage(
            raw, messages, reply
        )

        return {
            "text": reply,
            "raw": raw,
            "url": self.chat_url,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "estimated": estimated,
        }


__all__ = [
    "IBMICAClient",
    "IBMICAError",
    "IBMICAConfigError",
    "IBMICAAuthError",
    "IBMICAConnectionError",
    "IBMICAResponseError",
]