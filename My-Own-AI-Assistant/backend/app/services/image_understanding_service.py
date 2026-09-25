"""Image understanding service.

Pasted/uploaded images are always read by the Claude model (regardless of
the session's selected model) and converted into detailed Markdown. That
Markdown becomes the attachment's content, so whichever model the user
picked answers from a text rendition of the image.
"""

import asyncio
import base64
from pathlib import Path

from ..config import config
from ..ibm_ica_client import IBMICAError
from .model_service import ModelRateLimitError, get_model_service

IMAGE_MAX_TOKENS = 8000

IMAGE_TO_MARKDOWN_PROMPT = (
    "Convert this image into detailed Markdown. Another AI model that cannot see "
    "the image will answer the user's questions using only your Markdown, so capture "
    "everything that matters:\n"
    "- Start with a one-paragraph overview of what the image is.\n"
    "- Transcribe ALL visible text verbatim (headings, labels, captions, UI text).\n"
    "- Tables -> Markdown tables. Code or terminal output -> fenced code blocks.\n"
    "- Diagrams/flowcharts/architecture -> list every component and every connection "
    "(A -> B, with labels), plus grouping/hierarchy.\n"
    "- Charts -> chart type, axes, series, and the data values you can read.\n"
    "- Screenshots of apps/UI -> layout, sections, and the state of controls.\n"
    "- Photos/illustrations -> subjects, setting, colours, notable details.\n"
    "Respond with the Markdown only, no preamble."
)


class ImageUnderstandingService:
    """Turns an image into Markdown using the Claude model."""

    async def image_to_markdown(self, image_path: Path, mime_type: str, filename: str) -> str:
        data = base64.b64encode(image_path.read_bytes()).decode("ascii")
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": IMAGE_TO_MARKDOWN_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{data}"}},
            ],
        }]

        try:
            # The ICA client is blocking; keep the event loop free while it runs
            result = await asyncio.to_thread(
                get_model_service().client.chat,
                messages=messages,
                max_tokens=IMAGE_MAX_TOKENS,
                model_id=config.MODEL_CHOICES["claude"],
            )
        except IBMICAError as e:
            if getattr(e, "http_code", None) == 429:
                raise ModelRateLimitError(str(e)) from e
            raise RuntimeError(f"Image understanding failed: {str(e)}") from e

        markdown = f"# {filename}\n\n"
        markdown += f"**Type:** {mime_type} (image)\n\n"
        markdown += (
            "_This image was converted to Markdown by an image-reading model; "
            "you are seeing its description, not the image itself._\n\n"
        )
        markdown += "---\n\n"
        markdown += result["text"]
        return markdown


# Singleton instance
_image_understanding_service: ImageUnderstandingService | None = None


def get_image_understanding_service() -> ImageUnderstandingService:
    """Get image understanding service singleton."""
    global _image_understanding_service
    if _image_understanding_service is None:
        _image_understanding_service = ImageUnderstandingService()
    return _image_understanding_service
