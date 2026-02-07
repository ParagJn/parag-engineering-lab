from typing import Any
import httpx

from app import config


class LLMError(Exception):
    pass


async def call_gemini(prompt: str) -> str:
    if not config.GOOGLE_API_KEY:
        return "Gemini API key missing. Set GOOGLE_API_KEY in .env."

    url = (
        f"{config.GEMINI['api_base']}/"
        f"{config.GEMINI['model']}:generateContent?key={config.GOOGLE_API_KEY}"
    )

    payload: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": config.GEMINI["temperature"],
            "maxOutputTokens": config.GEMINI["max_output_tokens"]
        }
    }

    async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(url, json=payload)

    if response.status_code >= 400:
        raise LLMError(f"Gemini error {response.status_code}: {response.text}")

    data = response.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError):
        raise LLMError(f"Unexpected Gemini response shape: {data}")


async def call_claude(prompt: str) -> str:
    if not config.ANTHROPIC_API_KEY:
        return "Anthropic API key missing. Set ANTHROPIC_API_KEY in .env."

    url = config.CLAUDE["api_url"]
    headers = {
        "x-api-key": config.ANTHROPIC_API_KEY,
        "anthropic-version": config.CLAUDE["anthropic_version"],
        "content-type": "application/json"
    }
    payload: dict[str, Any] = {
        "model": config.CLAUDE["model"],
        "max_tokens": config.CLAUDE["max_tokens"],
        "temperature": config.CLAUDE["temperature"],
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.post(url, headers=headers, json=payload)

    if response.status_code >= 400:
        raise LLMError(f"Claude error {response.status_code}: {response.text}")

    data = response.json()
    try:
        blocks = data.get("content", [])
        text_blocks = [b.get("text", "") for b in blocks if b.get("type") == "text"]
        return "\n".join([t for t in text_blocks if t]).strip()
    except Exception as exc:  # noqa: BLE001
        raise LLMError(f"Unexpected Claude response shape: {data}") from exc
