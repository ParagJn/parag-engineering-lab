"""Generate a LinkedIn teaser post that drives readers to the published magazine page."""

import json

from config import get_settings
from llm_clients import build_agent

LINK_PLACEHOLDER = "👉 Read the full edition: [paste link here]"
# Always appended to the hashtag line, regardless of what the model returns
REQUIRED_HASHTAG = "#AIGeneratedContent"


async def generate_linkedin_posts(
    stories: list[dict],
    provider: str = "ibm_ica",
    magazine_title: str = "Morning Edition",
    page_url: str = "",
) -> list[dict]:
    """Generate one curiosity-driven LinkedIn post promoting the whole edition.

    Returns a single-item list of dicts with keys: index, headline, post
    (kept as a list so the existing modal and HTML/PDF export work unchanged).
    """
    settings = get_settings()
    agent = build_agent(settings, "linkedin", "claude", provider)

    if not agent.configured:
        label = "SAP AI Core" if provider == "sap" else "IBM ICA"
        raise ValueError(f"{label} is not configured — check the relevant env vars")

    # Only headline-level material — the post should tease, not summarise
    stories_input = [
        {
            "headline": s.get("headline", ""),
            "deck": s.get("deck", ""),
            "pull_quote": s.get("pull_quote", ""),
            "category_label": s.get("category_label", ""),
        }
        for s in stories
    ]

    prompt = f"""You are a LinkedIn thought-leadership writer specialising in enterprise tech, AI and AI security.

Today's magazine edition is titled "{magazine_title}" and contains {len(stories_input)} stories (below).
Write ONE LinkedIn post that promotes the whole edition. The post will be published with a hyperlink to the
magazine page, and its ONLY job is to make the reader curious enough to click that link.

Structure (no section labels — plain text, blank lines between sections):

1. HOOK — one scroll-stopping line on its own. A surprising tension, a counter-intuitive claim, or a question
   the reader can't answer yet. Never start with "I".
2. SETUP — 1-2 short sentences on why today's edition matters to people building or securing AI and enterprise tech.
3. TEASERS — 3-4 lines starting with "→", each teasing a different story. Open a curiosity gap: hint at the
   surprise, the stake, or the uncomfortable question, but DO NOT reveal the answer, the key number, or the conclusion.
4. CALL TO ACTION — one line that gives a concrete reason to click now (what they'll learn or be able to do).

Writing guidelines:
- 600–1,000 characters total, excluding hashtags
- Conversational yet authoritative; no clickbait clichés ("You won't believe…"), no buzzword soup
- Pick the most intriguing stories, favouring AI, AI security and enterprise impact
- Do NOT include any URL or link — it is added separately
- Use \\n for newlines inside JSON strings

STORIES:
{json.dumps(stories_input, indent=2)}

Return ONLY valid JSON, no commentary:
{{
  "headline": "<a short internal label for this post, e.g. the hook in a few words>",
  "post": "<the post text, sections 1-4 only, newlines as \\n>",
  "hashtags": "<5-7 hashtags on one line, mixing broad (#AI) and specific (#AISecurity #LLMOps)>"
}}"""

    max_tokens = 4000 if provider == "sap" else 8000
    result = await agent.complete(system="", user=prompt, max_tokens=max_tokens)
    response_text = result.content

    # Strip markdown code fences if present
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]
        response_text = response_text.rsplit("```", 1)[0]

    try:
        data = json.loads(response_text, strict=False)
    except json.JSONDecodeError:
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start != -1 and end > start:
            data = json.loads(response_text[start:end], strict=False)
        else:
            raise ValueError("Failed to parse LinkedIn post from Claude response")

    # The link line is added here rather than by the model so it is always present
    link_line = f"👉 Read the full edition: {page_url}" if page_url else LINK_PLACEHOLDER
    parts = [(data.get("post") or "").strip(), link_line]
    hashtags = (data.get("hashtags") or "").strip()
    if REQUIRED_HASHTAG.lower() not in hashtags.lower():
        hashtags = f"{hashtags} {REQUIRED_HASHTAG}".strip()
    parts.append(hashtags)

    return [{
        "index": 0,
        "headline": data.get("headline") or magazine_title,
        "post": "\n\n".join(parts),
    }]
