import asyncio
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl

# Directory structure constants
BASE_DIR = Path(__file__).resolve().parent  # backend/app/
BACKEND_DIR = BASE_DIR.parent  # backend/
PROJECT_DIR = BACKEND_DIR.parent  # project root
GENERATED_DIR = PROJECT_DIR / "generated_articles"  # output directory

# Load environment variables from .env file
load_dotenv(BASE_DIR / ".env")


def load_app_config() -> Dict[str, Any]:
    """Load application configuration from JSON file.
    
    Reads config file path from APP_CONFIG_PATH environment variable.
    Path is resolved relative to backend directory if not absolute.
    
    Returns:
        Configuration dictionary, or empty dict if file not found.
    """
    config_path_value = os.getenv("APP_CONFIG_PATH", "app/config.json")
    config_path = Path(config_path_value)

    if not config_path.is_absolute():
        config_path = BACKEND_DIR / config_path

    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as f:
        return json.load(f)


APP_CONFIG = load_app_config()

# FastAPI application instance
app = FastAPI(title="Article Generator API", version="1.0.0")

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    """Request model for article generation.
    
    Attributes:
        urls: List of source URLs to research and generate article from.
        article_id: Optional ID for updating an existing article.
        platform: Target platform (blog, linkedin, instagram, x) for style optimization.
    """
    urls: List[HttpUrl]
    article_id: Optional[str] = None
    platform: Literal["blog", "linkedin", "instagram", "x"] = "blog"


class ApplySuggestionsRequest(BaseModel):
    """Request model for applying Claude's improvement suggestions.
    
    Attributes:
        urls: Source URLs for factual grounding.
        article: Current article text to improve.
        improvements: List of specific improvements from Claude review.
        review_summary: Optional summary from Claude's review.
        article_id: Optional ID for updating existing article.
        platform: Target platform for style optimization.
    """
    urls: List[HttpUrl]
    article: str
    improvements: List[str]
    review_summary: Optional[str] = None
    article_id: Optional[str] = None
    platform: Literal["blog", "linkedin", "instagram", "x"] = "blog"


class ManualRegenerateRequest(BaseModel):
    """Request model for manual article regeneration with user-specified changes.
    
    Attributes:
        urls: Source URLs for factual grounding.
        article: Current article text to modify.
        change_request: User's description of desired changes.
        article_id: Optional ID for updating existing article.
        platform: Target platform for style optimization.
    """
    urls: List[HttpUrl]
    article: str
    change_request: str
    article_id: Optional[str] = None
    platform: Literal["blog", "linkedin", "instagram", "x"] = "blog"


class ReviewResult(BaseModel):
    """Model for Claude's article quality review results.
    
    Attributes:
        score: Quality score from 1-10 (10 being excellent).
        summary: Brief summary of the review assessment.
        improvements: List of specific suggestions for improvement.
    """
    score: int
    summary: str
    improvements: List[str]


def sse_event(event: str, payload: Dict[str, Any]) -> str:
    """Format a Server-Sent Event (SSE) message.
    
    Args:
        event: Event type name (e.g., 'status', 'review', 'done', 'error').
        payload: Event data as dictionary to be JSON-encoded.
    
    Returns:
        Formatted SSE string ready for streaming.
    """
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


def get_config(path: str, default: Any = None) -> Any:
    """Retrieve nested configuration value using dot notation.
    
    Args:
        path: Dot-separated path to config value (e.g., 'llm.gemini.model').
        default: Value to return if path doesn't exist.
    
    Returns:
        Configuration value or default if not found.
    """
    node: Any = APP_CONFIG
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def get_runtime_settings() -> Dict[str, Any]:
    """Load all runtime settings from environment and config file.
    
    Merges settings from .env file and config.json, with environment
    variables taking precedence. Includes API keys, model configurations,
    quality thresholds, and concurrency limits.
    
    Returns:
        Dictionary containing all runtime configuration settings.
    """
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
        "claude_api_url": get_config(
            "llm.claude.api_url", "https://api.anthropic.com/v1/messages"
        ),
        "claude_model": get_config(
            "llm.claude.model", os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-latest")
        ),
        "claude_anthropic_version": get_config("llm.claude.anthropic_version", "2023-06-01"),
        "claude_temperature": float(get_config("llm.claude.temperature", 0.7)),
        "claude_max_tokens": int(get_config("llm.claude.max_tokens", 3000)),
        "request_timeout_seconds": float(get_config("llm.request_timeout_seconds", 90)),
        "min_score": int(get_config("quality.min_score", 7)),
        "max_retries": int(get_config("quality.max_retries", 2)),
        "max_parallel_articles": max(1, int(get_config("processing.max_parallel_articles", 3))),
    }


# Concurrency control: limit parallel article generations
MAX_PARALLEL_ARTICLES = max(1, int(get_config("processing.max_parallel_articles", 3)))
GENERATION_SEMAPHORE = asyncio.Semaphore(MAX_PARALLEL_ARTICLES)
GENERATION_STATE_LOCK = asyncio.Lock()
ACTIVE_GENERATIONS = 0  # Current number of active generations
WAITING_GENERATIONS = 0  # Number of generations in queue


async def acquire_generation_slot() -> Dict[str, Any]:
    """Acquire a generation slot for article processing.
    
    Manages concurrency by enforcing max_parallel_articles limit.
    Queues requests when all slots are occupied.
    
    Returns:
        Dictionary with queue status: was_queued, queue_position, active_now, waiting_now.
    """
    global ACTIVE_GENERATIONS, WAITING_GENERATIONS

    async with GENERATION_STATE_LOCK:
        was_queued = ACTIVE_GENERATIONS >= MAX_PARALLEL_ARTICLES
        queue_position = 0
        if was_queued:
            WAITING_GENERATIONS += 1
            queue_position = WAITING_GENERATIONS

    await GENERATION_SEMAPHORE.acquire()

    async with GENERATION_STATE_LOCK:
        if was_queued and WAITING_GENERATIONS > 0:
            WAITING_GENERATIONS -= 1
        ACTIVE_GENERATIONS += 1
        active_now = ACTIVE_GENERATIONS
        waiting_now = WAITING_GENERATIONS

    return {
        "was_queued": was_queued,
        "queue_position": queue_position,
        "active_now": active_now,
        "waiting_now": waiting_now,
    }


async def release_generation_slot() -> Dict[str, int]:
    """Release a generation slot after completion.
    
    Returns:
        Dictionary with current active and waiting generation counts.
    """
    global ACTIVE_GENERATIONS

    GENERATION_SEMAPHORE.release()

    async with GENERATION_STATE_LOCK:
        ACTIVE_GENERATIONS = max(0, ACTIVE_GENERATIONS - 1)
        return {
            "active_now": ACTIVE_GENERATIONS,
            "waiting_now": WAITING_GENERATIONS,
        }


def ensure_generated_dir() -> None:
    """Ensure the generated_articles directory exists."""
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def sanitize_article_id(article_id: str) -> str:
    """Sanitize article ID to prevent directory traversal.
    
    Args:
        article_id: User-provided article ID/filename.
    
    Returns:
        Safe filename with .md extension.
    """
    safe_name = Path(article_id).name
    if not safe_name.endswith(".md"):
        safe_name = f"{safe_name}.md"
    return safe_name


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug.
    
    Args:
        text: Text to slugify (typically article title).
    
    Returns:
        Lowercase slug with hyphens, max 60 characters.
    """
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
    slug = re.sub(r"[\s_-]+", "-", cleaned)
    return slug[:60] or "article"


def extract_title(article: str) -> str:
    """Extract title from markdown article.
    
    Tries to find first markdown heading (# Title), falls back to
    first non-empty line if no heading found.
    
    Args:
        article: Markdown article text.
    
    Returns:
        Extracted title (max 120 chars) or 'Generated Article' if none found.
    """
    for line in article.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()[:120] or "Generated Article"

    for line in article.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]

    return "Generated Article"


def save_article_markdown(article: str, article_id: Optional[str] = None) -> Dict[str, str]:
    """Save article as markdown file to generated_articles directory.
    
    Args:
        article: Markdown article content.
        article_id: Optional filename; if None, generates timestamp-based name.
    
    Returns:
        Dictionary with article_id (filename) and article_title.
    """
    ensure_generated_dir()
    title = extract_title(article)

    if article_id:
        safe_id = sanitize_article_id(article_id)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_id = f"{timestamp}_{slugify(title)}.md"

    path = GENERATED_DIR / safe_id
    path.write_text(article, encoding="utf-8")

    return {"article_id": safe_id, "article_title": title}


def list_saved_articles() -> List[Dict[str, str]]:
    """List all saved articles with metadata.
    
    Returns:
        List of article dictionaries sorted by updated_at (newest first).
        Each dict contains: article_id, title, updated_at.
    """
    ensure_generated_dir()
    articles: List[Dict[str, str]] = []

    for path in GENERATED_DIR.glob("*.md"):
        try:
            content = path.read_text(encoding="utf-8")
            title = extract_title(content)
            modified = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
            articles.append(
                {
                    "article_id": path.name,
                    "title": title,
                    "updated_at": modified,
                }
            )
        except OSError:
            continue

    articles.sort(key=lambda item: item["updated_at"], reverse=True)
    return articles


def read_saved_article(article_id: str) -> Dict[str, str]:
    """Read a saved article from disk.
    
    Args:
        article_id: Article filename/ID.
    
    Returns:
        Dictionary with article_id, title, content, and updated_at.
    
    Raises:
        HTTPException: 404 if article not found.
    """
    ensure_generated_dir()
    safe_id = sanitize_article_id(article_id)
    path = GENERATED_DIR / safe_id

    if not path.exists():
        raise HTTPException(status_code=404, detail="Article not found.")

    content = path.read_text(encoding="utf-8")
    modified = datetime.fromtimestamp(path.stat().st_mtime).isoformat()

    return {
        "article_id": safe_id,
        "title": extract_title(content),
        "content": content,
        "updated_at": modified,
    }


def parse_json_object(text: str) -> Dict[str, Any]:
    """Extract and parse JSON object from text (handles markdown code blocks).
    
    Args:
        text: Text containing JSON, possibly wrapped in markdown code blocks.
    
    Returns:
        Parsed JSON as dictionary.
    
    Raises:
        ValueError: If no valid JSON object found.
    """
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
    """Format Gemini API errors into user-friendly messages.
    
    Args:
        exc: Exception from Gemini API request.
    
    Returns:
        User-friendly error message with troubleshooting guidance.
    """
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
    """Format Claude API errors into user-friendly messages.
    
    Args:
        exc: Exception from Claude API request.
    
    Returns:
        User-friendly error message with troubleshooting guidance.
    """
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
    """Generate text using Google Gemini API.
    
    Args:
        client: Async HTTP client.
        api_key: Google API key.
        api_base: Gemini API base URL.
        model: Model name (e.g., 'gemini-2.0-flash').
        prompt: Generation prompt.
        temperature: Sampling temperature (0.0-1.0).
        max_output_tokens: Maximum tokens to generate.
    
    Returns:
        Generated text content.
    
    Raises:
        httpx.HTTPStatusError: On API request failure.
        ValueError: If response is empty or invalid.
    """
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
    """Review article quality using Anthropic Claude API.
    
    Args:
        client: Async HTTP client.
        api_key: Anthropic API key.
        api_url: Claude API endpoint URL.
        anthropic_version: API version string.
        model: Model name (e.g., 'claude-3-5-sonnet-latest').
        temperature: Sampling temperature.
        max_tokens: Maximum tokens for response.
        article: Article text to review.
    
    Returns:
        ReviewResult with score (1-10), summary, and improvements list.
    
    Raises:
        httpx.HTTPStatusError: On API request failure.
        ValueError: If response format is invalid.
    """
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


def normalize_platform(platform: str) -> str:
    """Normalize platform string to valid value.
    
    Args:
        platform: Platform name (case-insensitive).
    
    Returns:
        Normalized platform: 'blog', 'linkedin', 'instagram', or 'x'.
        Defaults to 'blog' if invalid.
    """
    value = (platform or "blog").strip().lower()
    if value in {"linkedin", "instagram", "x", "blog"}:
        return value
    return "blog"


def platform_instruction(platform: str) -> str:
    """Get platform-specific writing style instructions.
    
    Args:
        platform: Target platform name.
    
    Returns:
        Detailed style guide instructions for the platform.
    """
    platform = normalize_platform(platform)
    if platform == "linkedin":
        return (
            "Write for LinkedIn: professional, insight-driven, and credible. "
            "Use clear business/academic framing, structured points, and avoid slang. "
            "End with 3-5 relevant LinkedIn-friendly hashtags."
        )
    if platform == "instagram":
        return (
            "Write for Instagram: concise, engaging, audience-friendly, and visually descriptive. "
            "Keep punchy paragraphs, include an inviting hook, and finish with 6-10 relevant hashtags."
        )
    if platform == "x":
        return (
            "Write for X (Twitter): direct, high-impact, fast to scan, and trend-aware. "
            "Use short sections and include 3-6 relevant hashtags for each of the section."
            "Generate in a format that can be easily adapted into a thread of 5-10 tweets, with clear breakpoints for each tweet."
            "Avoid long paragraphs and maintain a conversational tone."
        )
    return (
        "Write as an SEO-optimized blog post: strong keyword-rich title, semantic subheadings, "
        "search-friendly phrasing, internal clarity, and readable long-form flow."
    )


def build_initial_prompt(urls: List[str], current_date: str, platform: str) -> str:
    """Build initial article generation prompt for Gemini.
    
    Args:
        urls: Source URLs to research.
        current_date: Current date for context.
        platform: Target platform for style.
    
    Returns:
        Formatted prompt string for article generation.
    """
    sources = "\n".join(f"- {url}" for url in urls)
    style_instruction = platform_instruction(platform)
    return f"""
You are an expert editor and analyst.
Today is {current_date}.

Target platform: {normalize_platform(platform)}
Platform style instruction: {style_instruction}

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
    platform: str,
) -> str:
    """Build regeneration prompt incorporating Claude's feedback.
    
    Args:
        urls: Source URLs for grounding.
        current_date: Current date.
        prior_article: Previous article version.
        review: Claude's review with score and improvements.
        attempt: Current regeneration attempt number.
        platform: Target platform.
    
    Returns:
        Formatted prompt for article regeneration.
    """
    sources = "\n".join(f"- {url}" for url in urls)
    improvement_points = "\n".join(f"- {p}" for p in review.improvements)
    style_instruction = platform_instruction(platform)

    return f"""
You previously generated an article that scored {review.score}/10 from a quality reviewer.
Today is {current_date}.
This is regeneration attempt #{attempt}.

Target platform: {normalize_platform(platform)}
Platform style instruction: {style_instruction}

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
    platform: str,
) -> str:
    """Build prompt for applying Claude's improvement suggestions.
    
    Args:
        urls: Source URLs for grounding.
        current_date: Current date.
        article: Current article text.
        review_summary: Claude's review summary.
        improvements: List of specific improvements to apply.
        platform: Target platform.
    
    Returns:
        Formatted prompt for article refinement.
    """
    sources = "\n".join(f"- {url}" for url in urls)
    improvements_text = "\n".join(f"- {item}" for item in improvements)
    style_instruction = platform_instruction(platform)

    return f"""
Today is {current_date}.
You are revising an existing article using reviewer feedback.

Target platform: {normalize_platform(platform)}
Platform style instruction: {style_instruction}

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


def build_manual_regen_prompt(
    urls: List[str],
    current_date: str,
    article: str,
    change_request: str,
    platform: str,
) -> str:
    """Build prompt for manual article regeneration.
    
    Args:
        urls: Source URLs for grounding.
        current_date: Current date.
        article: Current article text.
        change_request: User's description of desired changes.
        platform: Target platform.
    
    Returns:
        Formatted prompt for custom article revision.
    """
    sources = "\n".join(f"- {url}" for url in urls)
    style_instruction = platform_instruction(platform)
    return f"""
Today is {current_date}.
You are revising an existing article based on explicit user requests.

Target platform: {normalize_platform(platform)}
Platform style instruction: {style_instruction}

User-requested changes:
{change_request}

Task:
- Apply every requested change.
- Keep the strongest parts of the original article.
- Preserve factual grounding using the provided URLs.
- Return one complete revised article in Markdown.

Source URLs:
{sources}

Current article:
{article}
""".strip()


def validate_keys(settings: Dict[str, Any]) -> None:
    """Validate that required API keys are configured.
    
    Args:
        settings: Runtime settings dictionary.
    
    Raises:
        HTTPException: If any required API keys are missing.
    """
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
    """Health check endpoint with system status.
    
    Returns:
        System status including port configuration, API key status,
        and current generation queue state.
    """
    backend_port = int(os.getenv("PORT", get_config("backend.port", 8000)))
    frontend_port = int(os.getenv("FRONTEND_PORT", get_config("frontend.port", 5173)))
    settings = get_runtime_settings()
    return {
        "status": "ok",
        "backend_port": backend_port,
        "frontend_port": frontend_port,
        "gemini_key_configured": bool(settings["gemini_key"]),
        "claude_key_configured": bool(settings["claude_key"]),
        "max_parallel_articles": settings["max_parallel_articles"],
        "active_generations": ACTIVE_GENERATIONS,
        "waiting_generations": WAITING_GENERATIONS,
    }


@app.get("/api/articles")
async def get_articles() -> Dict[str, List[Dict[str, str]]]:
    """List all saved articles.
    
    Returns:
        Dictionary with 'articles' list containing article metadata
        (article_id, title, updated_at) sorted by modification time.
    """
    return {"articles": list_saved_articles()}


@app.get("/api/articles/{article_id}")
async def get_article(article_id: str) -> Dict[str, str]:
    """Retrieve a specific saved article.
    
    Args:
        article_id: Filename/ID of the article.
    
    Returns:
        Article data including content, title, and metadata.
    
    Raises:
        HTTPException: 404 if article not found.
    """
    return read_saved_article(article_id)


@app.delete("/api/articles/{article_id}")
async def delete_article(article_id: str) -> Dict[str, str]:
    """Delete a saved article.
    
    Args:
        article_id: Filename/ID of the article to delete.
    
    Returns:
        Dictionary with success message and deleted article_id.
    
    Raises:
        HTTPException: 404 if article not found.
    """
    ensure_generated_dir()
    safe_id = sanitize_article_id(article_id)
    path = GENERATED_DIR / safe_id

    if not path.exists():
        raise HTTPException(status_code=404, detail="Article not found.")

    path.unlink()
    return {
        "message": "Article deleted successfully.",
        "article_id": safe_id,
    }


@app.post("/api/generate-stream")
async def generate_stream(request: GenerateRequest) -> StreamingResponse:
    """Generate article with auto-retry based on quality score.
    
    Streams events via Server-Sent Events (SSE):
    - status: Generation progress updates
    - review: Claude quality review results
    - error: Error messages
    - done: Final result with article
    
    Args:
        request: Generation request with URLs and platform.
    
    Returns:
        StreamingResponse with SSE events.
    
    Raises:
        HTTPException: If URLs missing or API keys not configured.
    """
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
        acquired_slot = False

        yield sse_event(
            "status",
            {
                "step": "input_received",
                "message": f"Received {len(urls)} URL(s). Starting research and article generation.",
            },
        )

        try:
            slot_info = await acquire_generation_slot()
            acquired_slot = True

            if slot_info["was_queued"]:
                yield sse_event(
                    "status",
                    {
                        "step": "waiting_for_slot",
                        "message": (
                            f"Generation queued. Waiting for an available worker slot "
                            f"(queue position {slot_info['queue_position']})."
                        ),
                    },
                )

            yield sse_event(
                "status",
                {
                    "step": "slot_acquired",
                    "message": (
                        f"Worker slot acquired. Running jobs: {slot_info['active_now']}/"
                        f"{settings['max_parallel_articles']}."
                    ),
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
                        prompt = build_initial_prompt(urls, current_date, request.platform)
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
                            request.platform,
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
                        saved = save_article_markdown(article_text, request.article_id)
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
                                "article_id": saved["article_id"],
                                "article_title": saved["article_title"],
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
                        saved = save_article_markdown(article_text or "", request.article_id)
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
                                "article_id": saved["article_id"],
                                "article_title": saved["article_title"],
                            },
                        )
                        return
        finally:
            if acquired_slot:
                await release_generation_slot()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/apply-suggestions-stream")
async def apply_suggestions_stream(request: ApplySuggestionsRequest) -> StreamingResponse:
    """Apply Claude's improvement suggestions to regenerate article.
    
    Takes existing article and Claude's suggestions, prompts Gemini to
    revise accordingly, then reviews the result with Claude.
    
    Args:
        request: Request with article, improvements, and source URLs.
    
    Returns:
        StreamingResponse with SSE events for progress and results.
    
    Raises:
        HTTPException: If required fields missing or API keys not configured.
    """
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
        acquired_slot = False

        yield sse_event(
            "status",
            {
                "step": "apply_suggestions_start",
                "message": "Applying Claude suggestions and regenerating article with Gemini.",
            },
        )

        try:
            slot_info = await acquire_generation_slot()
            acquired_slot = True

            if slot_info["was_queued"]:
                yield sse_event(
                    "status",
                    {
                        "step": "waiting_for_slot",
                        "message": (
                            f"Refinement queued. Waiting for an available worker slot "
                            f"(queue position {slot_info['queue_position']})."
                        ),
                    },
                )

            yield sse_event(
                "status",
                {
                    "step": "slot_acquired",
                    "message": (
                        f"Worker slot acquired. Running jobs: {slot_info['active_now']}/"
                        f"{settings['max_parallel_articles']}."
                    ),
                },
            )

            prompt = build_apply_suggestions_prompt(
                urls=urls,
                current_date=current_date,
                article=request.article,
                review_summary=request.review_summary or "No summary provided.",
                improvements=request.improvements,
                platform=request.platform,
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

                saved = save_article_markdown(refined_article, request.article_id)
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
                        "article_id": saved["article_id"],
                        "article_title": saved["article_title"],
                    },
                )
        finally:
            if acquired_slot:
                await release_generation_slot()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/manual-regenerate-stream")
async def manual_regenerate_stream(request: ManualRegenerateRequest) -> StreamingResponse:
    """Regenerate article based on user's manual change request.
    
    Allows users to specify custom changes they want applied to the article.
    Gemini applies the changes, then Claude reviews the updated version.
    
    Args:
        request: Request with article, change_request, and source URLs.
    
    Returns:
        StreamingResponse with SSE events for progress and results.
    
    Raises:
        HTTPException: If required fields missing or API keys not configured.
    """
    settings = get_runtime_settings()
    validate_keys(settings)

    urls = [str(url) for url in request.urls]
    if not urls:
        raise HTTPException(status_code=400, detail="At least one URL is required.")
    if not request.article.strip():
        raise HTTPException(status_code=400, detail="Current article is required.")
    if not request.change_request.strip():
        raise HTTPException(status_code=400, detail="Change request is required.")

    async def event_stream() -> AsyncGenerator[str, None]:
        min_score = settings["min_score"]
        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        acquired_slot = False

        yield sse_event(
            "status",
            {
                "step": "manual_regen_start",
                "message": "Applying your requested changes with Gemini.",
            },
        )

        try:
            slot_info = await acquire_generation_slot()
            acquired_slot = True

            if slot_info["was_queued"]:
                yield sse_event(
                    "status",
                    {
                        "step": "waiting_for_slot",
                        "message": (
                            f"Manual regeneration queued. Waiting for an available worker slot "
                            f"(queue position {slot_info['queue_position']})."
                        ),
                    },
                )

            yield sse_event(
                "status",
                {
                    "step": "slot_acquired",
                    "message": (
                        f"Worker slot acquired. Running jobs: {slot_info['active_now']}/"
                        f"{settings['max_parallel_articles']}."
                    ),
                },
            )

            prompt = build_manual_regen_prompt(
                urls=urls,
                current_date=current_date,
                article=request.article,
                change_request=request.change_request,
                platform=request.platform,
            )

            timeout = httpx.Timeout(settings["request_timeout_seconds"])
            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    revised_article = await generate_with_gemini(
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
                            "step": "gemini_manual_error",
                            "message": format_gemini_error(exc),
                        },
                    )
                    return

                yield sse_event(
                    "status",
                    {
                        "step": "manual_regen_review",
                        "message": "Claude is reviewing the updated article.",
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
                        article=revised_article,
                    )
                except Exception as exc:  # noqa: BLE001
                    yield sse_event(
                        "error",
                        {
                            "step": "claude_manual_error",
                            "message": format_claude_error(exc),
                        },
                    )
                    return

                yield sse_event(
                    "review",
                    {
                        "step": "manual_review_complete",
                        "attempt": 1,
                        "score": review.score,
                        "summary": review.summary,
                        "improvements": review.improvements,
                    },
                )

                saved = save_article_markdown(revised_article, request.article_id)
                final_status = "success" if review.score >= min_score else "needs_more_work"
                yield sse_event(
                    "done",
                    {
                        "status": final_status,
                        "attempts_used": 1,
                        "final_score": review.score,
                        "review_summary": review.summary,
                        "article": revised_article,
                        "improvements": review.improvements,
                        "message": "Manual regeneration completed.",
                        "article_id": saved["article_id"],
                        "article_title": saved["article_title"],
                    },
                )
        finally:
            if acquired_slot:
                await release_generation_slot()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
