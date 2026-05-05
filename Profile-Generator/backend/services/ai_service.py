"""
AI Service — two-stage pipeline:
  Stage 1: Gemini 1.5 Pro extracts a structured profile JSON from raw document text.
  Stage 2: Claude generates the final HTML outputs (CV + LinkedIn) from the structured data.
"""
import json
import logging
import os
import re
import httpx
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# STAGE 1 — Gemini: structured extraction
# ─────────────────────────────────────────────

EXTRACTION_PROMPT = """
You are an expert resume analyst. Analyze ALL the text below (from one or more uploaded documents 
and/or public profile links) and extract a comprehensive, structured JSON profile.

Return ONLY valid JSON — no markdown, no code fences, no explanation.

The JSON must follow this exact schema:
{{
  "name": "full name",
  "title": "current professional title",
  "email": "email address",
  "phone": "phone number",
  "location": "city, country",
  "linkedin": "LinkedIn URL",
  "github": "GitHub URL",
  "website": "personal website URL",
  "summary": "3-5 sentence executive summary highlighting unique value proposition, specialization, and impact",
  "tagline": "one-line professional tagline, punchy",
  "years_experience": "total years of experience as a number",
  "current_employer": "current company name",
  "core_competencies": ["list", "of", "key", "competencies"],
  "tech_stack": {{
    "ai_ml": ["AI/ML technologies used"],
    "languages": ["programming languages"],
    "frameworks": ["frameworks and libraries"],
    "cloud_platforms": ["cloud/infra platforms"],
    "tools": ["other key tools"]
  }},
  "experience": [
    {{
      "company": "company name",
      "role": "job title",
      "duration": "e.g. 2021 – Present",
      "location": "city, country",
      "highlights": ["bullet point achievement 1", "bullet point achievement 2"],
      "is_current": true
    }}
  ],
  "projects": [
    {{
      "name": "project name",
      "tagline": "one sentence description",
      "description": "2-3 sentence detailed description",
      "tech": ["tech1", "tech2"],
      "impact": "quantified business/technical impact",
      "url": "link if available",
      "status": "Production | Building Now | Completed | Open Source",
      "icon": "single relevant emoji"
    }}
  ],
  "education": [
    {{
      "degree": "degree name",
      "institution": "university/college",
      "year": "graduation year",
      "honors": "any honors or distinction"
    }}
  ],
  "certifications": [
    {{
      "name": "cert name",
      "issuer": "issuing body",
      "year": "year"
    }}
  ],
  "achievements": ["achievement 1", "achievement 2"],
  "languages_spoken": ["English", "Hindi"],
  "value_proposition": "3-4 sentences on unique value delivered to employers/clients"
}}

---
RAW CONTENT FROM DOCUMENTS AND LINKS:
{content}
---

Remember: return ONLY the JSON object. No markdown fences. No extra text.
"""


async def extract_profile_with_gemini(combined_text: str) -> dict:
    """Use Gemini 1.5 Pro to extract structured profile data from raw text."""
    import google.generativeai as genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.5-pro")

    prompt = EXTRACTION_PROMPT.format(content=combined_text[:50000])  # safety cap

    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.2,
            max_output_tokens=8192,
        ),
    )

    raw = response.text.strip()

    # Strip markdown code fences if model adds them
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Gemini returned invalid JSON: {e}\nRaw: {raw[:500]}")
        # Return minimal fallback
        return {"name": "Professional", "title": "", "summary": combined_text[:500]}


# ─────────────────────────────────────────────
# STAGE 2 — Claude: HTML generation
# ─────────────────────────────────────────────

CV_HTML_SYSTEM = """You are an expert front-end developer and technical resume writer. 
You create beautiful, animated, print-ready single-file HTML resumes that stand out.
Your output is ONLY the complete HTML file — no explanation, no markdown, no code fences."""

CV_HTML_PROMPT = """
Create a stunning, production-quality single-file HTML resume for the person described below.

DESIGN REQUIREMENTS:
- Full dark gradient header: background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%)
- CSS variables: --primary: #0f172a; --accent: #2563eb; --accent2: #10b981; --text: #1e293b; --light: #f8fafc
- Google Font: Inter (import from fonts.googleapis.com)
- Font Awesome 6.5.1 icons via CDN (kit.fontawesome.com/6c5b1e7d55.js OR cdnjs)
- Scroll-reveal animations using IntersectionObserver (fade-in + slide-up, 0.6s ease)
- Tech badges: pill shape, gradient backgrounds, Font Awesome icons
- Project cards: glassmorphism, hover lift (translateY -4px), colored left border
- Status badges: "Production" (green), "Building Now" (amber pulsing), "Open Source" (blue)
- Timeline for work history with colored dots
- Responsive: max-width 1100px, centered, good mobile layout
- Print CSS: keep dark gradient header (print-color-adjust: exact), disable animations, 2-column print layout
- A4 PAGE LAYOUT: The main content wrapper must use class "page" with width: 210mm, min-height: 297mm, padding: 0.5in (all four sides), margin: 0 auto, box-sizing: border-box. This ensures pixel-perfect A4 output with 0.5-inch margins on all sides when printed or exported to PDF.

SECTIONS (in order):
1. Header: name (3rem bold white), title, contact row with FA icons (email, phone, location, LinkedIn, GitHub)
2. Executive Summary: italic, slightly larger text
3. Core Competencies + Tech Stack side-by-side grid
4. Current Role + Key Achievements
5. Featured Professional Assets (project cards, 3-column grid)
6. Career Timeline
7. Certifications & Honors
8. Education
9. Value Proposition footer block (dark background)
10. Copyright footer: a <footer class="cv-footer"> element OUTSIDE the dark value-proposition block, containing a full-width horizontal rule followed by centered text: © Parag Jain | Parag.Jn@GMail.com | 2026  — use small, muted (#64748b) font at 0.78rem.

PRINT/PDF CSS:
```
@media print {{
  * {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }}
  .header {{ background: linear-gradient(135deg, #0f172a 0%, #1e3a5f 50%, #0f172a 100%) !important; }}
  .reveal {{ opacity: 1 !important; transform: none !important; }}
  @page {{ size: A4; margin: 0; }}
  .page {{ padding: 0.5in !important; }}
  .cv-footer {{ border-top: 1px solid #cbd5e1 !important; padding-top: 10px !important; text-align: center !important; font-size: 0.78rem !important; color: #64748b !important; }}
}}
```

PROFILE DATA:
{profile_json}

Output the complete HTML file. Start with <!DOCTYPE html>. No code fences. No explanation.
"""

LINKEDIN_HTML_SYSTEM = """You are a LinkedIn profile optimization expert and front-end developer.
You create clean, LinkedIn-blue styled copy-paste tools for professionals.
Output ONLY the complete HTML file."""

LINKEDIN_HTML_PROMPT = """
Create a LinkedIn profile copy-paste helper HTML page for the person below.

DESIGN:
- LinkedIn blue palette: #0a66c2 primary, #057642 secondary, white background
- Clean card-based layout, full-width sections
- Each section has a "Copy" button (uses navigator.clipboard.writeText)
- Character counter below each textarea (warns at 85% of limit, red if over)
- Sticky navigation bar with section jumps
- Section cards have a colored left border

SECTIONS WITH CHARACTER LIMITS:
1. Headline — 220 chars
2. About / Summary — 2600 chars
3. Current Position Description — 2000 chars
4. Each project/experience entry — 2000 chars each (one card per project)
5. Skills block 1 (top 10 technical skills) — plain list
6. Skills block 2 (AI/ML specializations) — plain list
7. Certifications — plain list
8. Featured section note (instructions to add portfolio link)

JavaScript for copy buttons:
```javascript
function copyText(id) {{
  const el = document.getElementById(id);
  navigator.clipboard.writeText(el.value).then(() => {{
    const btn = el.parentElement.querySelector('.copy-btn');
    btn.textContent = '✅ Copied!';
    btn.style.background = '#057642';
    setTimeout(() => {{ btn.textContent = 'Copy'; btn.style.background = '#0a66c2'; }}, 2000);
  }});
}}
function updateCounter(id, limit) {{
  const el = document.getElementById(id);
  const counter = document.getElementById(id + '_count');
  const len = el.value.length;
  counter.textContent = len + ' / ' + limit;
  counter.style.color = len > limit ? '#dc2626' : len > limit * 0.85 ? '#d97706' : '#64748b';
}}
```

PROFILE DATA:
{profile_json}

Output the complete HTML file starting with <!DOCTYPE html>. No code fences. No explanation.
"""


async def generate_cv_outputs_with_claude(profile_data: dict) -> dict:
    """Use Claude to generate the HTML CV and LinkedIn HTML."""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")

    client = anthropic.Anthropic(api_key=api_key)
    profile_json = json.dumps(profile_data, indent=2)

    # Generate CV HTML
    cv_response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=16000,
        system=CV_HTML_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": CV_HTML_PROMPT.format(profile_json=profile_json),
            }
        ],
    )
    cv_html = cv_response.content[0].text.strip()
    cv_html = re.sub(r"^```(?:html)?\s*", "", cv_html, flags=re.MULTILINE)
    cv_html = re.sub(r"\s*```$", "", cv_html, flags=re.MULTILINE)

    # Generate LinkedIn HTML
    li_response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=12000,
        system=LINKEDIN_HTML_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": LINKEDIN_HTML_PROMPT.format(profile_json=profile_json),
            }
        ],
    )
    linkedin_html = li_response.content[0].text.strip()
    linkedin_html = re.sub(r"^```(?:html)?\s*", "", linkedin_html, flags=re.MULTILINE)
    linkedin_html = re.sub(r"\s*```$", "", linkedin_html, flags=re.MULTILINE)

    return {"cv_html": cv_html, "linkedin_html": linkedin_html}


# ─────────────────────────────────────────────
# GitHub link enrichment
# ─────────────────────────────────────────────

async def fetch_github_profile(username: str) -> str:
    """Fetch public GitHub profile + top repos as text."""
    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    lines = []
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get(
                f"https://api.github.com/users/{username}", headers=headers
            )
            if r.status_code == 200:
                u = r.json()
                lines.append(f"GitHub Profile: {u.get('name', username)}")
                lines.append(f"Bio: {u.get('bio', '')}")
                lines.append(f"Location: {u.get('location', '')}")
                lines.append(f"Company: {u.get('company', '')}")
                lines.append(f"Public repos: {u.get('public_repos', 0)}")
                lines.append(f"Followers: {u.get('followers', 0)}")
        except Exception as e:
            logger.warning(f"GitHub user fetch failed: {e}")

        try:
            r = await client.get(
                f"https://api.github.com/users/{username}/repos?sort=stars&per_page=10",
                headers=headers,
            )
            if r.status_code == 200:
                repos = r.json()
                lines.append("\nTop GitHub Repositories:")
                for repo in repos:
                    desc = repo.get("description") or ""
                    lang = repo.get("language") or ""
                    stars = repo.get("stargazers_count", 0)
                    lines.append(
                        f"  - {repo['name']}: {desc} [lang:{lang}, stars:{stars}]"
                    )
        except Exception as e:
            logger.warning(f"GitHub repos fetch failed: {e}")

    return "\n".join(lines)


def extract_github_username(url: str) -> Optional[str]:
    """Extract GitHub username from a URL like https://github.com/username."""
    match = re.search(r"github\.com/([^/\s?#]+)", url)
    return match.group(1) if match else None


# ─────────────────────────────────────────────
# STAGE 3 — Claude: HTML refinement
# ─────────────────────────────────────────────

REFINE_CV_PROMPT = """You are given an existing HTML resume and user-requested changes to apply.

USER INSTRUCTIONS:
{instructions}

PROFILE DATA (for reference when adding or updating content):
{profile_json}

EXISTING CV HTML:
{cv_html}

Apply the user's requested changes to the HTML above.
- Style changes (colors, fonts, layout): update the CSS/HTML accordingly.
- Content changes (add certs, update summary, etc.): update the relevant sections using profile data as the source.
- Keep everything else exactly as it is.
Output ONLY the complete updated HTML file starting with <!DOCTYPE html>. No code fences. No explanation."""

REFINE_LINKEDIN_PROMPT = """You are given an existing LinkedIn profile helper HTML page and user-requested changes to apply.

USER INSTRUCTIONS:
{instructions}

PROFILE DATA (for reference when adding or updating content):
{profile_json}

EXISTING LINKEDIN HTML:
{linkedin_html}

Apply the user's requested changes to the HTML above. Keep everything else exactly as it is.
Output ONLY the complete updated HTML file starting with <!DOCTYPE html>. No code fences. No explanation."""


async def refine_outputs_with_claude(
    profile_data: dict, cv_html: str, linkedin_html: str, instructions: str
) -> dict:
    """Use Claude to refine existing CV and LinkedIn HTML based on user instructions."""
    import anthropic

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment")

    client = anthropic.Anthropic(api_key=api_key)
    profile_json = json.dumps(profile_data, indent=2)

    # Refine CV HTML
    cv_response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=16000,
        system="You are an expert front-end developer and resume writer. You refine existing HTML resumes based on user feedback. Output ONLY the complete updated HTML file — no explanation, no markdown, no code fences.",
        messages=[{
            "role": "user",
            "content": REFINE_CV_PROMPT.format(
                instructions=instructions,
                profile_json=profile_json,
                cv_html=cv_html[:40000],
            ),
        }],
    )
    new_cv = cv_response.content[0].text.strip()
    new_cv = re.sub(r"^```(?:html)?\s*", "", new_cv, flags=re.MULTILINE)
    new_cv = re.sub(r"\s*```$", "", new_cv, flags=re.MULTILINE)

    # Refine LinkedIn HTML
    li_response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=12000,
        system="You are a LinkedIn profile optimization expert and front-end developer. You refine existing LinkedIn helper pages based on user feedback. Output ONLY the complete updated HTML file — no explanation, no markdown, no code fences.",
        messages=[{
            "role": "user",
            "content": REFINE_LINKEDIN_PROMPT.format(
                instructions=instructions,
                profile_json=profile_json,
                linkedin_html=linkedin_html[:30000],
            ),
        }],
    )
    new_li = li_response.content[0].text.strip()
    new_li = re.sub(r"^```(?:html)?\s*", "", new_li, flags=re.MULTILINE)
    new_li = re.sub(r"\s*```$", "", new_li, flags=re.MULTILINE)

    return {"cv_html": new_cv, "linkedin_html": new_li}
