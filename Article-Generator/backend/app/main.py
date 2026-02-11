import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl

BASE_DIR = Path(__file__).resolve().parent
BACKEND_DIR = BASE_DIR.parent

# Always load backend/app/.env first.
load_dotenv(BASE_DIR / ".env")


def load_app_config() -> Dict[str, Any]:
    config_path_value = os.getenv("APP_CONFIG_PATH", "app/config.json")
    config_path = Path(config_path_value)

    if not config_path.is_absolute():
        config_path = BACKEND_DIR / config_path

    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


APP_CONFIG = load_app_config()

app = FastAPI(title="Article Generator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    urls: List[HttpUrl]


class ApplySuggestionsRequest(BaseModel):
    urls: List[HttpUrl]
    article: str
    improvements: List[str]
    review_summary: Optional[str] = None


class ReviewResult(BaseModel):
    score: int
    summary: str
    improvements: List[str]


def sse_event(event: str, payload: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def get_config(path: str, default: Any = None) -> Any:
    node: Any = APP_CONFIG
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def get_runtime_settings() -> Dict[str, Any]:
    return {
        "gemini_key": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
        "claude_key": os.getenv("ANTHROPIC_API_KEY"),
        "gemini_api_base": get_config(
            "llm.gemini.api_base",
            "https://generativelanguage.googleapis.com/v1beta/models",
        ),
        "gemini_model": get_config(
            "llm.gemini.model", os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        ),
        "gemini_temperature": float(get_config("llm.gemini.temperature", 0.7)),
        "gemini_max_output_tokens": int(get_config("llm.gemini.max_output_tokens", 3000)),
        "claude_api_url": get_config("llm.claude.api_url", "https://api.anthropic.com/v1/messages"),
        "claude_model": get_config(
            "llm.claude.model", os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-latest")
        ),
        "claude_anthropic_version": get_config("llm.claude.anthropic_version", "2023-06-01"),
        "claude_temperature": float(get_config("llm.claude.temperature", 0.7)),
        "claude_max_tokens": int(get_config("llm.claude.max_tokens", 3000)),
        "request_timeout_seconds": float(get_config("llm.request_timeout_seconds", 90)),
        "min_score": int(get_config("quality.min_score", 7)),
        "max_retries": int(get_config("quality.max_retries", 2)),
    }


def parse_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.replace("json", "", 1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Could not find JSON object in model response.")

    return json.loads(text[start : end + 1])


def format_gemini_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (400, 401, 403):
            return (
                "Gemini request failed due to authentication/authorization. "
                "Check GOOGLE_API_KEY (or GEMINI_API_KEY) in backend/app/.env."
            )
        if status == 404:
            return "Gemini model or endpoint was not found (404). Check llm.gemini.model and llm.gemini.api_base in backend/app/config.json."
        if status == 429:
            return "Gemini rate limit reached (429). Please retry after a short wait."
        return f"Gemini request failed with HTTP {status}."

    if isinstance(exc, httpx.RequestError):
        return "Gemini request failed due to network/connectivity issue from backend."

    return f"Gemini generation failed: {str(exc)}"


def format_claude_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status in (401, 403):
            return (
                "Claude request failed due to authentication/authorization. "
                "Check ANTHROPIC_API_KEY in backend/app/.env."
            )
        if status == 404:
            return "Claude model or endpoint was not found (404). Check llm.claude.model and llm.claude.api_url in backend/app/config.json."
        if status == 429:
            return "Claude rate limit reached (429). Please retry after a short wait."
        return f"Claude request failed with HTTP {status}."

    if isinstance(exc, httpx.RequestError):
        return "Claude request failed due to network/connectivity issue from backend."

    text = str(exc)
    lower_text = text.lower()
    if "api key" in lower_text or "authentication" in lower_text:
        return (
            "Claude request failed due to authentication/authorization. "
            "Check ANTHROPIC_API_KEY in backend/app/.env."
        )
    return f"Claude review failed: {text}"


async def generate_with_gemini(
    client: httpx.AsyncClient,
    api_key: str,
    api_base: str,
    model: str,
    prompt: str,
    temperature: float,
    max_output_tokens: int,
) -> str:
    endpoint = f"{api_base.rstrip('/')}/{model}:generateContent"
    response = await client.post(
        endpoint,
        params={"key": api_key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
            },
        },
    )
    response.raise_for_status()
    data = response.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini returned no candidates.")

    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts).strip()

    if not text:
        raise ValueError("Gemini returned empty content.")

    return text


async def review_with_claude(
    client: httpx.AsyncClient,
    api_key: str,
    api_url: str,
    anthropic_version: str,
    model: str,
    temperature: float,
    max_tokens: int,
    article: str,
) -> ReviewResult:
    system_prompt = (
        "You are a strict content quality reviewer. "
        "Return only valid JSON with keys: score (integer 1-10), summary (string), "
        "improvements (array of strings)."
    )

    user_prompt = (
        "Evaluate this article quality for clarity, originality, structure, factual grounding, "
        "and readability. Give score 1-10 where 10 is excellent.\n\n"
        f"Article:\n{article}"
    )

    response = await client.post(
        api_url,
        headers={
            "x-api-key": api_key,
            "anthropic-version": anthropic_version,
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        },
    )
    response.raise_for_status()

    payload = response.json()
    content = payload.get("content", [])
    text_blocks = [block.get("text", "") for block in content if block.get("type") == "text"]
    raw = "\n".join(text_blocks).strip()

    parsed = parse_json_object(raw)

    score = int(parsed.get("score", 0))
    if score < 1 or score > 10:
        raise ValueError("Claude returned invalid score range.")

    improvements = parsed.get("improvements", [])
    if not isinstance(improvements, list):
        improvements = [str(improvements)]

    return ReviewResult(
        score=score,
        summary=str(parsed.get("summary", "No summary provided.")),
        improvements=[str(item) for item in improvements],
    )


def build_initial_prompt(urls: List[str], current_date: str) -> str:
    sources = "\n".join(f"- {url}" for url in urls)
    return f"""
You are an expert editor and analyst.
Today is {current_date}.

Task:
1) Research the provided source URLs.
2) Decide one best article angle that is most relevant and useful for today.
3) Write one full high-quality article in Markdown.

Constraints:
- Use factual claims grounded in source URLs.
- Add an engaging title.
- Include sections with clear subheadings.
- Include a short conclusion.
- Keep length around 900-1400 words.

Source URLs:
{sources}
""".strip()


def build_regen_prompt(
    urls: List[str],
    current_date: str,
    prior_article: str,
    review: ReviewResult,
    attempt: int,
) -> str:
    sources = "\n".join(f"- {url}" for url in urls)
    improvement_points = "\n".join(f"- {p}" for p in review.improvements)

    return f"""
You previously generated an article that scored {review.score}/10 from a quality reviewer.
Today is {current_date}.
This is regeneration attempt #{attempt}.

Improve the article by addressing all feedback below and rewrite it fully.

Reviewer summary:
{review.summary}

Required improvements:
{improvement_points}

Keep constraints:
- Use the provided source URLs for grounding.
- Produce one final article in Markdown.
- Keep length around 900-1400 words.
- Include a clear title, section headings, and concise conclusion.

Source URLs:
{sources}

Previous article:
{prior_article}
""".strip()


def build_apply_suggestions_prompt(
    urls: List[str],
    current_date: str,
    article: str,
    review_summary: str,
    improvements: List[str],
) -> str:
    sources = "\n".join(f"- {url}" for url in urls)
    improvements_text = "\n".join(f"- {item}" for item in improvements)

    return f"""
Today is {current_date}.
You are revising an existing article using reviewer feedback.

Task:
- Apply all reviewer suggestions below.
- Improve clarity, flow, factual grounding, and readability.
- Return a fully rewritten final article in Markdown.

Reviewer summary:
{review_summary}

Suggestions to apply:
{improvements_text}

Source URLs (keep claims grounded):
{sources}

Current article:
{article}
""".strip()


def validate_keys(settings: Dict[str, Any]) -> None:
    missing_keys: List[str] = []
    if not settings["gemini_key"]:
        missing_keys.append("GOOGLE_API_KEY (or GEMINI_API_KEY)")
    if not settings["claude_key"]:
        missing_keys.append("ANTHROPIC_API_KEY")

    if missing_keys:
        raise HTTPException(
            status_code=500,
            detail=(
                "Missing required API key(s) in backend/app/.env: "
                f"{', '.join(missing_keys)}"
            ),
        )


@app.get("/api/health")
async def health() -> Dict[str, Any]:
    backend_port = int(os.getenv("PORT", get_config("backend.port", 8000)))
    frontend_port = int(os.getenv("FRONTEND_PORT", get_config("frontend.port", 5173)))
    settings = get_runtime_settings()
    return {
        "status": "ok",
        "backend_port": backend_port,
        "frontend_port": frontend_port,
        "gemini_key_configured": bool(settings["gemini_key"]),
        "claude_key_configured": bool(settings["claude_key"]),
    }


@app.post("/api/generate-stream")
async def generate_stream(request: GenerateRequest) -> StreamingResponse:
    settings = get_runtime_settings()
    validate_keys(settings)

    urls = [str(url) for url in request.urls]
    if not urls:
        raise HTTPException(status_code=400, detail="At least one URL is required.")

    async def event_stream() -> AsyncGenerator[str, None]:
        max_attempts = settings["max_retries"] + 1
        min_score = settings["min_score"]
        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        article_text: Optional[str] = None
        last_review: Optional[ReviewResult] = None

        yield sse_event(
            "status",
            {
                "step": "input_received",
                "message": f"Received {len(urls)} URL(s). Starting research and article generation.",
            },
        )

        timeout = httpx.Timeout(settings["request_timeout_seconds"])
        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(1, max_attempts + 1):
                if attempt == 1:
                    yield sse_event(
                        "status",
                        {
                            "step": "gemini_research",
                            "attempt": attempt,
                            "message": "Gemini is researching URLs and drafting the first article.",
                        },
                    )
                    prompt = build_initial_prompt(urls, current_date)
                else:
                    yield sse_event(
                        "status",
                        {
                            "step": "gemini_regenerate",
                            "attempt": attempt,
                            "message": f"Gemini is regenerating article with reviewer feedback (attempt {attempt}/{max_attempts}).",
                        },
                    )
                    prompt = build_regen_prompt(
                        urls,
                        current_date,
                        article_text or "",
                        last_review or ReviewResult(score=0, summary="", improvements=[]),
                        attempt,
                    )

                try:
                    article_text = await generate_with_gemini(
                        client=client,
                        api_key=settings["gemini_key"],
                        api_base=settings["gemini_api_base"],
                        model=settings["gemini_model"],
                        prompt=prompt,
                        temperature=settings["gemini_temperature"],
                        max_output_tokens=settings["gemini_max_output_tokens"],
                    )
                except Exception as exc:  # noqa: BLE001
                    yield sse_event(
                        "error",
                        {
                            "step": "gemini_error",
                            "attempt": attempt,
                            "message": format_gemini_error(exc),
                        },
                    )
                    return

                yield sse_event(
                    "status",
                    {
                        "step": "claude_review",
                        "attempt": attempt,
                        "message": "Claude is reviewing article quality and assigning score.",
                    },
                )

                try:
                    last_review = await review_with_claude(
                        client=client,
                        api_key=settings["claude_key"],
                        api_url=settings["claude_api_url"],
                        anthropic_version=settings["claude_anthropic_version"],
                        model=settings["claude_model"],
                        temperature=settings["claude_temperature"],
                        max_tokens=settings["claude_max_tokens"],
                        article=article_text,
                    )
                except Exception as exc:  # noqa: BLE001
                    yield sse_event(
                        "error",
                        {
                            "step": "claude_error",
                            "attempt": attempt,
                            "message": format_claude_error(exc),
                        },
                    )
                    return

                yield sse_event(
                    "review",
                    {
                        "step": "review_complete",
                        "attempt": attempt,
                        "score": last_review.score,
                        "summary": last_review.summary,
                        "improvements": last_review.improvements,
                    },
                )

                if last_review.score >= min_score:
                    yield sse_event(
                        "done",
                        {
                            "status": "success",
                            "attempts_used": attempt,
                            "final_score": last_review.score,
                            "review_summary": last_review.summary,
                            "article": article_text,
                            "improvements": last_review.improvements,
                            "message": "Article passed quality threshold.",
                        },
                    )
                    return

                if attempt < max_attempts:
                    yield sse_event(
                        "status",
                        {
                            "step": "retrying",
                            "attempt": attempt,
                            "message": (
                                f"Score was {last_review.score}/10 (<{min_score}). Regenerating with reviewer feedback."
                            ),
                        },
                    )
                else:
                    yield sse_event(
                        "done",
                        {
                            "status": "failed_quality",
                            "attempts_used": attempt,
                            "final_score": last_review.score,
                            "review_summary": last_review.summary,
                            "article": article_text,
                            "improvements": last_review.improvements,
                            "message": (
                                "Article did not pass quality threshold after max retries. "
                                "Review feedback is provided for improvement."
                            ),
                        },
                    )
                    return

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/apply-suggestions-stream")
async def apply_suggestions_stream(request: ApplySuggestionsRequest) -> StreamingResponse:
    settings = get_runtime_settings()
    validate_keys(settings)

    urls = [str(url) for url in request.urls]
    if not urls:
        raise HTTPException(status_code=400, detail="At least one URL is required.")
    if not request.article.strip():
        raise HTTPException(status_code=400, detail="Current article is required.")
    if not request.improvements:
        raise HTTPException(status_code=400, detail="At least one improvement suggestion is required.")

    async def event_stream() -> AsyncGenerator[str, None]:
        min_score = settings["min_score"]
        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        yield sse_event(
            "status",
            {
                "step": "apply_suggestions_start",
                "message": "Applying Claude suggestions and regenerating article with Gemini.",
            },
        )

        prompt = build_apply_suggestions_prompt(
            urls=urls,
            current_date=current_date,
            article=request.article,
            review_summary=request.review_summary or "No summary provided.",
            improvements=request.improvements,
        )

        timeout = httpx.Timeout(settings["request_timeout_seconds"])
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                refined_article = await generate_with_gemini(
                    client=client,
                    api_key=settings["gemini_key"],
                    api_base=settings["gemini_api_base"],
                    model=settings["gemini_model"],
                    prompt=prompt,
                    temperature=settings["gemini_temperature"],
                    max_output_tokens=settings["gemini_max_output_tokens"],
                )
            except Exception as exc:  # noqa: BLE001
                yield sse_event(
                    "error",
                    {
                        "step": "gemini_apply_error",
                        "message": format_gemini_error(exc),
                    },
                )
                return

            yield sse_event(
                "status",
                {
                    "step": "apply_suggestions_review",
                    "message": "Claude is reviewing the refined article.",
                },
            )

            try:
                review = await review_with_claude(
                    client=client,
                    api_key=settings["claude_key"],
                    api_url=settings["claude_api_url"],
                    anthropic_version=settings["claude_anthropic_version"],
                    model=settings["claude_model"],
                    temperature=settings["claude_temperature"],
                    max_tokens=settings["claude_max_tokens"],
                    article=refined_article,
                )
            except Exception as exc:  # noqa: BLE001
                yield sse_event(
                    "error",
                    {
                        "step": "claude_apply_error",
                        "message": format_claude_error(exc),
                    },
                )
                return

            yield sse_event(
                "review",
                {
                    "step": "apply_review_complete",
                    "attempt": 1,
                    "score": review.score,
                    "summary": review.summary,
                    "improvements": review.improvements,
                },
            )

            final_status = "success" if review.score >= min_score else "needs_more_work"
            yield sse_event(
                "done",
                {
                    "status": final_status,
                    "attempts_used": 1,
                    "final_score": review.score,
                    "review_summary": review.summary,
                    "article": refined_article,
                    "improvements": review.improvements,
                    "message": "Refinement completed using Claude suggestions.",
                },
            )

    return StreamingResponse(event_stream(), media_type="text/event-stream")
