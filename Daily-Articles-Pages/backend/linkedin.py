"""Generate LinkedIn-optimised posts from magazine stories using Claude."""

import json

from config import get_settings
from llm_clients import SapCompletionAgent


async def generate_linkedin_posts(stories: list[dict]) -> list[dict]:
    """Generate a LinkedIn-ready post for each story.

    Returns a list of dicts with keys: index, headline, post.
    """
    settings = get_settings()
    agent = SapCompletionAgent(settings, "linkedin", settings.sap_anthropic_model)

    if not agent.configured:
        raise ValueError("SAP AI Core is not configured — check SAP_* env vars")

    # Build a compact stories payload to keep token usage manageable
    stories_input = []
    for i, s in enumerate(stories):
        stories_input.append({
            "index": i,
            "headline": s.get("headline", ""),
            "deck": s.get("deck", ""),
            "body": (s.get("body") or "")[:600],  # truncate long editorial bodies
            "pull_quote": s.get("pull_quote", ""),
            "category_label": s.get("category_label", ""),
            "original_url": s.get("original_url", ""),
        })

    n = len(stories_input)

    prompt = f"""You are a professional LinkedIn thought-leadership writer specialising in enterprise tech.

Transform each of the {n} tech stories below into a compelling LinkedIn post that is ready to copy-paste directly to a LinkedIn profile.

Each post MUST follow this exact structure (no section labels — just the text with blank lines between sections):

LINE 1 — HOOK: A single scroll-stopping opening line. Use a bold claim, a surprising stat, or a provocative question. This line stands alone.

BLANK LINE

BODY (3-4 bullet lines): Each bullet starts with the • symbol and delivers one crisp insight, real-world implication, or actionable takeaway from the story.

BLANK LINE

REFLECTION (1-2 sentences): A personal professional perspective, an observation about what this means for practitioners, or a call-to-action inviting readers to share their thoughts.

BLANK LINE

HASHTAGS: 5-7 hashtags on a single line. Mix broad tags (#AI #Technology) with specific ones (#LLMOps #ZeroTrust #CloudNative).

BLANK LINE

SOURCE LINE: Exactly this format → 🔗 Source: <original_url>

Writing guidelines:
- Total post length: 900–1,400 characters (LinkedIn engagement sweet spot)
- Conversational yet authoritative — no corporate jargon, no buzzword soup
- Write in first person where it feels natural ("This caught my attention…", "Here's why this matters…")
- Never start with "I"
- Newlines in the post text should use the literal \\n character in the JSON string

STORIES:
{json.dumps(stories_input, indent=2)}

Return ONLY valid JSON — an array of exactly {n} objects with NO additional keys or commentary:
[
  {{
    "index": 0,
    "headline": "<original story headline>",
    "post": "<complete LinkedIn post text ready to copy-paste, with newlines as \\n>"
  }},
  ...
]"""

    result = await agent.complete(system="", user=prompt, max_tokens=6000)
    response_text = result.content

    # Strip markdown code fences if present
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]
        response_text = response_text.rsplit("```", 1)[0]

    try:
        posts = json.loads(response_text)
    except json.JSONDecodeError:
        start = response_text.find("[")
        end = response_text.rfind("]") + 1
        if start != -1 and end > start:
            posts = json.loads(response_text[start:end])
        else:
            raise ValueError("Failed to parse LinkedIn posts from Claude response")

    return posts
