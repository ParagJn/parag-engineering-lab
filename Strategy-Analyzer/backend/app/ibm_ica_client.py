"""
IBM ICA chat-completions client (same pattern as Daily-Articles-Pages/backend/ibm_ica_client.py).
Stdlib only; call it from async code via asyncio.to_thread.
"""

from __future__ import annotations

import json
import os
import socket
import ssl
import urllib.error
import urllib.request
from typing import Any


class IBMICAError(RuntimeError):
    pass


class IBMICAConfigError(IBMICAError):
    pass


class IBMICAAuthError(IBMICAError):
    pass


class IBMICAConnectionError(IBMICAError):
    pass


class IBMICAResponseError(IBMICAError):
    def __init__(self, message: str, http_code: int | None = None):
        super().__init__(message)
        self.http_code = http_code


class IBMICAClient:
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
        if not endpoint or not endpoint.strip():
            raise IBMICAConfigError("IBM ICA endpoint is required.")
        if not api_key or not api_key.strip():
            raise IBMICAConfigError("IBM ICA API key is required.")

        self.endpoint = endpoint.strip().rstrip("/")
        self.api_key = api_key.strip()
        self.model_id = (model_id or "").strip() or "claude-opus-5-5"
        self.timeout = timeout

        if insecure_tls is None:
            insecure_tls = (os.getenv("IBM_ICA_INSECURE_TLS") or "").strip().lower() in {"1", "true", "yes", "y"}
        self.insecure_tls = insecure_tls
        self.ssl_context = self._build_ssl_context()
        self.chat_url = self.endpoint if self.endpoint.endswith(self.CHAT_PATH) else self.endpoint + self.CHAT_PATH

    def _build_ssl_context(self) -> ssl.SSLContext:
        if self.insecure_tls:
            return ssl._create_unverified_context()
        try:
            import certifi

            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return ssl.create_default_context()

    def _call(self, url: str, payload: dict) -> str:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            },
        )
        print(f"[IBM_ICA] -> POST {url} model={payload.get('model')!r}", flush=True)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout, context=self.ssl_context) as resp:
                print(f"[IBM_ICA] <- {resp.status} {url}", flush=True)
                return resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", "replace")[:400]
            message = f"HTTP {err.code} {err.reason}" + (f": {detail}" if detail else "")
            print(f"[IBM_ICA] <- HTTPError {err.code} {url} detail={detail!r}", flush=True)
            if err.code in (401, 403):
                raise IBMICAAuthError("Authentication failed (invalid key or auth scheme).") from err
            raise IBMICAResponseError(message, err.code) from err
        except urllib.error.URLError as err:
            reason = getattr(err, "reason", err)
            if isinstance(reason, ssl.SSLCertVerificationError):
                raise IBMICAConnectionError(
                    "SSL certificate verification failed. Install certifi in your venv or set "
                    "IBM_ICA_INSECURE_TLS=true for local connectivity testing."
                ) from err
            raise IBMICAConnectionError(f"Network error: {reason}") from err
        except (TimeoutError, socket.timeout) as err:
            raise IBMICAConnectionError("Request timed out while connecting to IBM ICA.") from err

    @staticmethod
    def _extract_text(raw: str) -> str:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return raw[:500]
        try:
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, list):  # content-part arrays
                content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
            return str(content or "").strip()
        except (KeyError, IndexError, TypeError):
            pass
        try:
            return str(data["content"][0]["text"]).strip()
        except (KeyError, IndexError, TypeError):
            pass
        return json.dumps(data, indent=2)[:800]

    def chat(self, messages: list[dict], max_tokens: int = 100, model_id: str | None = None) -> dict[str, Any]:
        if not isinstance(messages, list) or not messages:
            raise IBMICAConfigError("At least one message is required.")
        payload = {"model": model_id or self.model_id, "messages": messages, "max_tokens": max_tokens}
        raw = self._call(self.chat_url, payload)
        finish_reason = None
        usage = None
        try:
            diag = json.loads(raw)
            finish_reason = (diag.get("choices") or [{}])[0].get("finish_reason")
            usage = diag.get("usage")
        except Exception:
            pass
        return {
            "text": self._extract_text(raw),
            "raw": raw,
            "url": self.chat_url,
            "finish_reason": finish_reason,
            "usage": usage,
        }


__all__ = [
    "IBMICAClient",
    "IBMICAError",
    "IBMICAConfigError",
    "IBMICAAuthError",
    "IBMICAConnectionError",
    "IBMICAResponseError",
]
