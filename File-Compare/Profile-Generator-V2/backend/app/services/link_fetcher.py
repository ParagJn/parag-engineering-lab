from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup


def normalize_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


async def fetch_link_text(url: str) -> str:
    timeout = httpx.Timeout(12.0)
    headers = {
        "User-Agent": "ProfileGeneratorV2Bot/1.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
    except Exception:
        return f"Could not fetch content from {url}."

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type:
        return normalize_text(response.text[:12000])

    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    title = (soup.title.string or "").strip() if soup.title else ""
    body_text = normalize_text(soup.get_text("\n"))
    body_text = body_text[:16000]

    if title:
        return f"Title: {title}\n\n{body_text}"
    return body_text
