from __future__ import annotations

import json
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import get_settings
from llm_clients import ProviderError, build_agent

app = FastAPI(title="Hero Motion Studio API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5180", "http://127.0.0.1:5180"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SYSTEM_PROMPT = """You write copy for a short kinetic-typography hero animation used on a presentation slide.

The animation has fixed scenes, and you fill the text slots:
- intro: 1-2 short words shown before the hero word on a UI toggle, then they bend away (e.g. "Meet", "Introducing", "Say hello to"). Max 14 characters.
- hero: the hero word or name, 1-3 words, max 18 characters. Prefer a phrase containing a lowercase "i" or "j": the animated accent dot becomes its tittle.
- stat: one signed percentage that a spring graph overshoots to, e.g. "+22%". Between 5 and 60.
- words: exactly 5 short UPPERCASE words or phrases (max 14 characters each) that orbit the dot. Themes or capabilities of the subject.
- card_title: end-card title, max 22 characters (often the hero again).
- card_subtitle: one crisp line, max 40 characters, ending with a period.
- card_footnote: a tiny punchline or fact, max 28 characters.
- accent: optional single vivid hex colour that suits the subject, or null.

Return ONLY a JSON object with exactly these keys: intro, hero, stat, words, card_title, card_subtitle, card_footnote, accent.
No markdown, no commentary."""


class SuggestRequest(BaseModel):
    brief: str = Field(min_length=3, max_length=2000)
    tone: str = Field(default="confident", max_length=40)


class SuggestResponse(BaseModel):
    intro: str
    hero: str
    stat: str
    words: list[str]
    card_title: str
    card_subtitle: str
    card_footnote: str
    accent: str | None = None
    model: str


@app.get("/api/health")
def health():
    settings = get_settings()
    return {
        "ok": True,
        "ai_configured": bool(settings.ibm_ica_endpoint and settings.ibm_ica_api_key),
        "model": settings.ibm_ica_model_id,
    }


@app.post("/api/suggest", response_model=SuggestResponse)
async def suggest(req: SuggestRequest):
    settings = get_settings()
    agent = build_agent(settings, "hero-copywriter")
    if not agent.configured:
        raise HTTPException(503, "IBM ICA is not configured. Add the IBM_ICA_* keys to hero-motion-studio/.env")

    user = f"Slide brief:\n{req.brief.strip()}\n\nTone: {req.tone.strip() or 'confident'}"
    try:
        result = await agent.complete(SYSTEM_PROMPT, user, max_tokens=800)
    except ProviderError as err:
        raise HTTPException(502, str(err)) from err

    data = _parse_json(result.content)
    if data is None:
        raise HTTPException(502, f"Model did not return JSON: {result.content[:300]}")
    return _clean(data, settings.ibm_ica_model_id)


def _parse_json(text: str) -> dict | None:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


def _clip(value: object, limit: int, fallback: str = "") -> str:
    text = " ".join(str(value or "").split())
    return text[:limit].strip() or fallback


def _clean(data: dict, model: str) -> SuggestResponse:
    hero = _clip(data.get("hero"), 18, "Your Idea")

    stat = _clip(data.get("stat"), 8)
    match = re.search(r"\d+(?:\.\d+)?", stat)
    pct = min(60.0, max(5.0, float(match.group(0)))) if match else 22.0
    sign = "-" if stat.startswith("-") else "+"
    stat = f"{sign}{pct:g}%"

    words = data.get("words") if isinstance(data.get("words"), list) else []
    words = [_clip(w, 14).upper() for w in words if _clip(w, 14)][:5]
    for filler in ["SPRINGS", "EASING", "KINETIC TYPE", "3D", "SOUND"]:
        if len(words) >= 5:
            break
        if filler not in words:
            words.append(filler)

    accent = data.get("accent")
    accent = accent if isinstance(accent, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", accent) else None

    return SuggestResponse(
        intro=_clip(data.get("intro"), 14, "Meet"),
        hero=hero,
        stat=stat,
        words=words,
        card_title=_clip(data.get("card_title"), 22, hero),
        card_subtitle=_clip(data.get("card_subtitle"), 40),
        card_footnote=_clip(data.get("card_footnote"), 28),
        accent=accent,
        model=model,
    )
