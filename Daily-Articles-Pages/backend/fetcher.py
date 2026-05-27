"""Fetch stories from sources using RSS feeds and SAP Gemini for enrichment."""

import httpx
import feedparser

from config import get_settings
from llm_clients import SapCompletionAgent


async def fetch_rss_stories(feed_url: str, limit: int = 30) -> list[dict]:
    """Fetch stories from an RSS feed."""
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        headers = {
            "User-Agent": "MorningEdition/1.0 (RSS Reader)"
        }
        resp = await client.get(feed_url, headers=headers)
        resp.raise_for_status()

    feed = feedparser.parse(resp.text)
    stories = []
    for entry in feed.entries[:limit]:
        stories.append({
            "title": entry.get("title", "Untitled"),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", entry.get("description", "")),
            "published": entry.get("published", ""),
        })
    return stories


async def enrich_stories_with_gemini(stories: list[dict], source_name: str) -> list[dict]:
    """Use SAP Gemini to search for additional context on each story."""
    settings = get_settings()
    agent = SapCompletionAgent(settings, "enricher", settings.sap_gemini_model)

    if not agent.configured:
        return stories

    titles = "\n".join([f"- {s['title']}" for s in stories])
    prompt = f"""You are a tech news researcher. Given these headlines from {source_name}, 
identify the top 10 stories most relevant to: AI tools, creative software, dev tools, 
privacy/security, weird science, and actionable technology news.

For each selected story, provide:
1. A 2-3 sentence summary of WHY this story matters
2. Key facts or statistics
3. Whether this directly applies to a senior tech professional working in AI/enterprise software (flag as "APPLIES_TO_ME: true/false")

Headlines:
{titles}

Return ONLY valid JSON as an array of objects with fields:
"original_title", "summary", "key_facts", "applies_to_me" (boolean), "category" (one of: AI, Security, DevTools, Privacy, Science, Creative, Infrastructure)

Return exactly 10 stories."""

    import json
    try:
        result = await agent.complete(system="", user=prompt, max_tokens=4000)
        text = result.content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        enriched = json.loads(text)
    except Exception:
        enriched = []

    # Merge enrichment back into stories
    enriched_map = {e.get("original_title", ""): e for e in enriched}
    result = []
    for story in stories:
        if story["title"] in enriched_map:
            e = enriched_map[story["title"]]
            story["ai_summary"] = e.get("summary", "")
            story["key_facts"] = e.get("key_facts", "")
            story["applies_to_me"] = e.get("applies_to_me", False)
            story["category"] = e.get("category", "Tech")
            result.append(story)

    # If matching failed, take first 10 with defaults
    if len(result) < 10:
        for story in stories:
            if story not in result:
                story["ai_summary"] = story.get("summary", "")[:200]
                story["key_facts"] = ""
                story["applies_to_me"] = False
                story["category"] = "Tech"
                result.append(story)
            if len(result) >= 10:
                break

    return result[:10]
