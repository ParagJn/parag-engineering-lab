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
- ending: 1-2 short words that replace the intro on the final frame, closing the story (e.g. "Thank you", "Built for", "Welcome to"). Max 16 characters.
- hero: the hero word or name, 1-3 words, max 18 characters. Prefer a phrase containing a lowercase "i" or "j": the animated accent dot becomes its tittle.
- stat: the single headline number, written with its sign and unit (e.g. "+22%", "-40%", "3.5x", "$1.2M").
  HARD RULE: only use a number that appears in the brief. Never invent, estimate or round up a metric.
  If the brief contains no number, return null.
- words: exactly 5 short UPPERCASE words or phrases (max 14 characters each) that orbit the dot. Themes or capabilities of the subject.
- card_title: end-card title, max 22 characters (often the hero again).
- card_subtitle: one crisp line, max 40 characters, ending with a period.
- card_footnote: a tiny punchline or fact, max 28 characters.
- problem: the pain point as one plain sentence, max 48 characters, ending with a period (story mode).
- lead: 1-2 word lead-in shown above the solution badge (e.g. "Introducing", "Meet"). Max 16 characters.
- solution: the product, team or initiative name on the badge, max 24 characters.
- proof_label: what the stat measures, lower case, max 36 characters (e.g. "faster month-end close").
- accent: optional single vivid hex colour that suits the subject, or null.

Never put numbers in any field unless that exact number is in the brief.

Return ONLY a JSON object with exactly these keys: intro, ending, hero, stat, words, card_title, card_subtitle, card_footnote, problem, lead, solution, proof_label, accent.
No markdown, no commentary."""


class SuggestRequest(BaseModel):
    brief: str = Field(min_length=3, max_length=2000)
    tone: str = Field(default="confident", max_length=40)


class SuggestResponse(BaseModel):
    intro: str
    ending: str
    hero: str
    stat: str
    words: list[str]
    card_title: str
    card_subtitle: str
    card_footnote: str
    problem: str
    lead: str
    solution: str
    proof_label: str
    accent: str | None = None
    stat_from_brief: bool  # False: the brief had no usable number, so no stat is suggested
    notes: list[str]  # warnings for the user, e.g. numbers that don't appear in the brief
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
    return _clean(data, req.brief, settings.ibm_ica_model_id)


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


_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _numbers(text: str) -> set[str]:
    return {n.replace(",", ".") for n in _NUM.findall(text or "")}


def _clean(data: dict, brief: str, model: str) -> SuggestResponse:
    hero = _clip(data.get("hero"), 18, "Your Idea")
    notes: list[str] = []
    brief_numbers = _numbers(brief)

    # Hard line: the stat must be a number that is actually in the brief.
    stat = _clip(data.get("stat"), 10)
    stat_numbers = _numbers(stat)
    stat_from_brief = bool(stat_numbers) and stat_numbers <= brief_numbers
    if not stat_from_brief:
        if stat_numbers:
            notes.append(f"Ignored the suggested stat {stat!r}: that number isn't in your brief.")
        else:
            notes.append("Your brief has no number, so the stat was left unchanged. Add the real figure.")
        stat = ""

    words = data.get("words") if isinstance(data.get("words"), list) else []
    words = [_clip(w, 14).upper() for w in words if _clip(w, 14)][:5]
    for filler in ["SPRINGS", "EASING", "KINETIC TYPE", "3D", "SOUND"]:
        if len(words) >= 5:
            break
        if filler not in words:
            words.append(filler)

    for key in ("card_title", "card_subtitle", "card_footnote", "problem", "proof_label", "hero", "solution"):
        extra = _numbers(str(data.get(key) or "")) - brief_numbers
        if extra:
            notes.append(f"Check '{key}': it mentions {', '.join(sorted(extra))}, which isn't in your brief.")

    accent = data.get("accent")
    accent = accent if isinstance(accent, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", accent) else None

    return SuggestResponse(
        intro=_clip(data.get("intro"), 14, "Meet"),
        ending=_clip(data.get("ending"), 16),
        hero=hero,
        stat=stat,
        words=words,
        card_title=_clip(data.get("card_title"), 22, hero),
        card_subtitle=_clip(data.get("card_subtitle"), 40),
        card_footnote=_clip(data.get("card_footnote"), 28),
        problem=_clip(data.get("problem"), 48),
        lead=_clip(data.get("lead"), 16, "Introducing"),
        solution=_clip(data.get("solution"), 24, hero),
        proof_label=_clip(data.get("proof_label"), 36),
        accent=accent,
        stat_from_brief=stat_from_brief,
        notes=notes,
        model=model,
    )
