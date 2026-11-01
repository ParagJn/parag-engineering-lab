from __future__ import annotations

import json
import re
import ssl
from typing import Any

import httpx

from ...config import Settings
from ..credentials import api_key_for_model
from ..errors import (
    AuthenticationFailed,
    BadRequest,
    BadResponse,
    ContentFilterBlocked,
    ModelAccessDenied,
    ModelNotFound,
    TlsVerificationFailed,
    TransientProviderError,
)
from ..types import LLMRequest, ProviderResponse, Usage

CHAT_PATH = "/v1/chat/completions"
CONNECT_TIMEOUT = 10.0
MAX_CONNECTIONS = 20
MAX_ERROR_CHARS = 300

TRANSIENT_STATUSES = {408, 429, 500, 502, 503, 504, 529}
_FILTER_WORDS = re.compile(r"content[ _-]?(filter|policy|management)|safety|moderation", re.IGNORECASE)
# A 403 that is about one model, not about the key. ICA answers this way when the key works
# elsewhere but this team cannot use the model (seen live: "team_model_access_denied").
_MODEL_DENIED_WORDS = re.compile(
    r"model_access|model[ _-]?access[ _-]?denied|team_model"
    r"|not (available|authori[sz]ed|permitted|allowed|entitled)[^.]{0,40}\bmodel"
    r"|\bmodel\b[^.]{0,60}not (available|authori[sz]ed|permitted|allowed|entitled)(?! for this API key)"
    r"|model[^.]{0,60}not available for this API key",
    re.IGNORECASE,
)
_MISSING_MODEL_WORDS = re.compile(
    r"model[^.]{0,60}(not found|does not exist|unknown|unavailable|not supported)"
    r"|(unknown|invalid|unsupported) model|no such model",
    re.IGNORECASE,
)


class IcaConfigError(ValueError):
    """The endpoint or key is missing, so a provider cannot be built."""


def chat_url(endpoint: str) -> str:
    """Where chat completions live for this endpoint, tolerating the usual ways people write it."""
    base = endpoint.strip().rstrip("/")
    if base.endswith(CHAT_PATH):
        return base
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + CHAT_PATH


def build_messages(request: LLMRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if request.system:
        messages.append({"role": "system", "content": request.system})
    messages.extend({"role": m.role, "content": m.content} for m in request.messages)
    return messages


def _whole_number(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def parse_usage(data: dict) -> Usage | None:
    raw = data.get("usage")
    if not isinstance(raw, dict):
        return None
    for in_key, out_key in (("prompt_tokens", "completion_tokens"), ("input_tokens", "output_tokens")):
        tokens_in, tokens_out = _whole_number(raw.get(in_key)), _whole_number(raw.get(out_key))
        if tokens_in is not None and tokens_out is not None:
            return Usage(tokens_in, tokens_out)
    return None


def _first_choice(data: dict) -> dict:
    choices = data.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        return choices[0]
    return {}


def parse_text(data: dict) -> str:
    message = _first_choice(data).get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):  # content-part arrays
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    if content is None:
        alt = data.get("content")  # the other shape: {"content": [{"text": ...}]}
        if isinstance(alt, list) and alt and isinstance(alt[0], dict):
            content = alt[0].get("text")
    return content.strip() if isinstance(content, str) else ""


def error_text(response: httpx.Response) -> str:
    """A short description built only from the parsed error fields, never from the raw body."""
    parts: list[str] = []
    try:
        body = response.json()
    except ValueError:
        body = None
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        for field in ("code", "type", "message"):
            value = error.get(field)
            if isinstance(value, (str, int)) and str(value).strip():
                parts.append(str(value).strip())
    elif isinstance(error, str):
        parts.append(error.strip())
    elif isinstance(body, dict) and isinstance(body.get("message"), str):
        parts.append(body["message"].strip())
    detail = " - ".join(dict.fromkeys(parts))
    text = f"HTTP {response.status_code}" + (f": {detail}" if detail else "")
    return " ".join(text.split())[:MAX_ERROR_CHARS]


def build_ssl_context(insecure: bool) -> ssl.SSLContext | bool:
    if insecure:
        return False
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


class IcaProvider:
    """Calls IBM ICA's chat-completions endpoint and maps every outcome to a typed error."""

    label = "ica"

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        endpoint = settings.ibm_ica_endpoint.strip()
        if not endpoint:
            raise IcaConfigError("IBM_ICA_ENDPOINT is not set")
        if not settings.api_key_set:
            raise IcaConfigError("IBM_ICA_API_KEY is not set")  # the shared key is always required
        self._settings = settings
        self._url = chat_url(endpoint)
        self._base_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": settings.ibm_ica_user_agent,
        }
        self.insecure_tls = settings.ibm_ica_insecure_tls
        timeout = settings.llm_timeout_seconds
        self._client = httpx.AsyncClient(
            transport=transport,
            verify=build_ssl_context(self.insecure_tls),
            timeout=httpx.Timeout(timeout, connect=CONNECT_TIMEOUT),
            limits=httpx.Limits(max_connections=MAX_CONNECTIONS, max_keepalive_connections=MAX_CONNECTIONS),
        )

    @property
    def client(self) -> httpx.AsyncClient:
        return self._client

    def headers_for(self, model_id: str) -> dict[str, str]:
        """Request headers, with the key that belongs to the model being called."""
        return {**self._base_headers, "Authorization": f"Bearer {api_key_for_model(self._settings, model_id)}"}

    async def aclose(self) -> None:
        await self._client.aclose()

    async def complete(self, model_id: str, request: LLMRequest) -> ProviderResponse:
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": build_messages(request),
            "max_tokens": request.max_tokens,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        try:
            response = await self._client.post(self._url, json=payload, headers=self.headers_for(model_id))
        except httpx.ConnectError as exc:
            if _is_certificate_failure(exc):
                raise TlsVerificationFailed("the service's certificate could not be verified") from None
            raise TransientProviderError(f"could not connect ({type(exc).__name__})") from None
        except httpx.TimeoutException as exc:
            raise TransientProviderError(f"timed out ({type(exc).__name__})") from None
        except httpx.TransportError as exc:
            raise TransientProviderError(f"connection problem ({type(exc).__name__})") from None

        status = response.status_code
        if status >= 400:
            self._raise_for_status(response)

        try:
            data = response.json()
        except ValueError:
            raise BadResponse("the service answered with something that is not JSON") from None
        if not isinstance(data, dict) or not _first_choice(data):
            if isinstance(data, dict) and isinstance(data.get("content"), list):
                pass  # the alternative shape, handled by parse_text
            else:
                raise BadResponse("the service answered without any choices")

        finish = _first_choice(data).get("finish_reason")
        finish = finish if isinstance(finish, str) else None
        if finish == "content_filter":
            raise ContentFilterBlocked("the reply was blocked by the content filter")

        text = parse_text(data)
        if not text:
            hint = (
                "; the model may have used its whole token budget thinking, so raise max_tokens"
                if finish == "length" else ""
            )
            raise BadResponse(f"the model returned an empty reply (finish reason: {finish or 'none'}){hint}")
        return ProviderResponse(text=text, usage=parse_usage(data), finish_reason=finish)

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        status = response.status_code
        text = error_text(response)
        # Only a 403 can mean "this model is off limits to you"; a 401 is always the credentials.
        if status == 403 and _MODEL_DENIED_WORDS.search(text):
            raise ModelAccessDenied(text)
        if status in (401, 403):
            raise AuthenticationFailed(text)
        if status == 404 or _MISSING_MODEL_WORDS.search(text):
            raise ModelNotFound(text)
        if _FILTER_WORDS.search(text):
            raise ContentFilterBlocked(text)
        if status in TRANSIENT_STATUSES or status >= 500:
            raise TransientProviderError(text)
        raise BadRequest(text)


def _is_certificate_failure(exc: BaseException) -> bool:
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ssl.SSLCertVerificationError):
            return True
        current = current.__cause__ or current.__context__
    return "CERTIFICATE_VERIFY_FAILED" in str(exc)
