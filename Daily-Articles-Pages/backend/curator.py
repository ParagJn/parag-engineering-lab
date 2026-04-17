"""Use Anthropic Claude to curate stories into magazine editorial content."""

import os
import json
import anthropic

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


async def curate_magazine(stories: list[dict], source_name: str, edition_date: str) -> dict:
    """Send stories to Claude and get back fully curated magazine content."""

    if not ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    stories_json = json.dumps(stories, indent=2, default=str)

    prompt = f"""You are the editor-in-chief of "Morning Edition" — a premium daily tech magazine.
Today's date: {edition_date}
Source: {source_name}

Below are 10 curated tech stories. Transform each into a compelling magazine spread.

For each story, produce:
1. "headline" — a punchy, editorial-grade headline (not the original title)
2. "deck" — a one-line subheadline / teaser
3. "body" — 3-5 paragraphs of editorial content: context, analysis, what it means for practitioners. Write like a top-tier magazine editor — vivid, opinionated, authoritative.
4. "pull_quote" — one striking quote or stat to highlight
5. "category_label" — short tag like "AI TOOLS", "SECURITY ALERT", "DEV TOOLS", "PRIVACY", "WEIRD SCIENCE", "INFRASTRUCTURE", "CREATIVE TECH"
6. "spread_style" — assign each story a DIFFERENT visual treatment from this list (use each at most once, pick 10):
   - "hero" (massive headline, light bg, bold serif)
   - "midnight" (dark bg, white text, moody)
   - "rose_alert" (rose/pink bg, stamped WARNING feel)
   - "terminal" (black bg, green monospace text, hacker aesthetic)
   - "academic" (cream bg, drop-cap, scholarly feel)
   - "big_stat" (giant statistic number as centerpiece)
   - "blueprint" (technical drawing feel, blue tones)
   - "neon" (dark bg with bright neon accent colors)
   - "editorial" (clean white, large pull-quote, classic magazine)
   - "sunset" (warm gradient, golden hour feel)
7. "applies_to_me" — boolean, true if this story directly impacts an AI/enterprise tech professional
8. "original_url" — preserve the original link
9. "numeral" — the story number formatted creatively (e.g., "01", "II", "三", "No. 4", "§5", "VI", "007", "∞", "IX", "X")

STORIES:
{stories_json}

Return ONLY valid JSON: an object with:
- "magazine_title": a creative title for today's edition
- "edition_tagline": a one-line tagline for today
- "seo_description": a compelling 150-160 character meta description for search engines, summarizing this edition's highlights
- "seo_keywords": comma-separated list of 8-12 relevant keywords/phrases for this edition (e.g. "artificial intelligence, cybersecurity, developer tools, cloud computing")
- "stories": array of 10 story objects with all fields above"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}]
    )

    response_text = message.content[0].text.strip()

    # Parse JSON from response
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1]
        response_text = response_text.rsplit("```", 1)[0]

    try:
        magazine_data = json.loads(response_text)
    except json.JSONDecodeError:
        # Try to find JSON in the response
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start != -1 and end > start:
            magazine_data = json.loads(response_text[start:end])
        else:
            raise ValueError("Failed to parse magazine content from Claude")

    return magazine_data
