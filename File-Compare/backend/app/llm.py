from __future__ import annotations

import asyncio
import io
from typing import Any

from .config import Settings
from .ibm_ica_client import IBMICAClient, IBMICAError


class LLMError(RuntimeError):
    pass


class ContentFilterError(LLMError):
    pass


# Keep raw image bytes under ~3.5 MB so the base64 payload stays inside vision limits.
_MAX_IMAGE_BYTES = 3_500_000

_VISION_INSTRUCTION = (
    "Convert this image into structured markdown. "
    "Preserve visible text exactly where possible, and organize output into sections "
    "using markdown headings. Include tables/lists when visible. "
    "If a region is unclear, mark it as [unclear]. Output markdown only."
)

_REPORT_SYSTEM = "You produce accurate comparison reports with clear structure and detailed analysis."


def shrink_image(data: bytes, media_type: str) -> tuple[bytes, str]:
    """Downscale/re-encode oversized images so the vision call is accepted."""
    if len(data) <= _MAX_IMAGE_BYTES:
        return data, media_type
    from PIL import Image

    image = Image.open(io.BytesIO(data)).convert("RGB")
    side = 2400
    while True:
        copy = image.copy()
        copy.thumbnail((side, side))
        buffer = io.BytesIO()
        copy.save(buffer, format="JPEG", quality=85)
        if buffer.tell() <= _MAX_IMAGE_BYTES or side <= 600:
            return buffer.getvalue(), "image/jpeg"
        side = int(side * 0.75)


class IcaLLM:
    """IBM ICA chat completions with one content-filter fallback retry."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model = settings.ibm_ica_model_id
        fallback = settings.ibm_ica_fallback_model_id
        self.fallback_model = fallback if fallback and fallback != self.model else ""

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
            raise LLMError(f"IBM ICA error: {err}") from err
        if result.get("finish_reason") == "content_filter":
            raise ContentFilterError(f"IBM ICA response from {model} was blocked by the content filter.")
        result["model"] = model
        return result

    async def _chat_with_fallback(self, messages: list[dict[str, Any]], max_tokens: int) -> dict[str, Any]:
        if not self.configured:
            raise LLMError("IBM ICA is not configured. Set IBM_ICA_ENDPOINT and IBM_ICA_API_KEY in backend/.env.")
        try:
            result = await self._chat(self.model, messages, max_tokens)
        except ContentFilterError:
            if not self.fallback_model:
                raise
            result = await self._chat(self.fallback_model, messages, max_tokens)
        if not result["text"].strip():
            raise LLMError("The model returned an empty response. Try again, or raise the output token limit.")
        return result

    async def report(self, prompt: str) -> tuple[str, str]:
        """Return (markdown, model used)."""
        messages = [
            {"role": "system", "content": _REPORT_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        result = await self._chat_with_fallback(messages, self.settings.report_max_output_tokens)
        return result["text"].strip(), result["model"]

    async def image_to_markdown(self, data: bytes, media_type: str) -> str:
        import base64

        data, media_type = await asyncio.to_thread(shrink_image, data, media_type)
        encoded = base64.b64encode(data).decode("ascii")
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _VISION_INSTRUCTION},
                    {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{encoded}"}},
                ],
            }
        ]
        result = await self._chat_with_fallback(messages, self.settings.image_max_output_tokens)
        return result["text"].strip()
