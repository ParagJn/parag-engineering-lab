"""
AI Service — two-stage pipeline via SAP AI Core Generative AI Hub:
  Stage 1: gemini-2.5-pro  — extracts a structured profile JSON from raw document text.
  Stage 2: anthropic--claude-4.7-opus — generates the final HTML outputs (CV + LinkedIn).
  Stage 3: anthropic--claude-4.7-opus — refines existing outputs based on user feedback.

Authentication: OAuth 2.0 client-credentials flow → bearer token cached in-process.
"""
import json
import logging
import os
import re
import time
import httpx
import requests as _requests_lib   # sync, only for token fetch
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# SAP AI Core — OAuth token + chat helper
# ─────────────────────────────────────────────

_SAP_MODEL_GEMINI  = "gemini-2.5-pro"
_SAP_MODEL_CLAUDE  = "anthropic--claude-4.7-opus"

_sap_token_cache: dict = {"token": None, "expires_at": 0.0}


def _get_sap_access_token() -> str:
    """Return a cached (or freshly generated) SAP AI Core OAuth bearer token."""
    now = time.time()
    if _sap_token_cache["token"] and now < _sap_token_cache["expires_at"] - 60:
        return _sap_token_cache["token"]

    client_id     = os.getenv("SAP_CLIENT_ID", "").strip().strip('"')
    client_secret = os.getenv("SAP_CLIENT_SECRET", "").strip().strip('"')
    token_url     = os.getenv("SAP_TOKEN_URL", "").strip().strip('"')

    if not all([client_id, client_secret, token_url]):
        raise EnvironmentError(
            "SAP_CLIENT_ID, SAP_CLIENT_SECRET, and SAP_TOKEN_URL must be set in .env"
        )

    resp = _requests_lib.post(
        token_url,
        data={
            "grant_type":    "client_credentials",
            "client_id":     client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    token      = data["access_token"]
    expires_in = int(data.get("expires_in", 3600))
    _sap_token_cache["token"]      = token
    _sap_token_cache["expires_at"] = now + expires_in
    logger.info(f"SAP AI Core token refreshed — expires in {expires_in}s")
    return token


def _sap_chat_url() -> str:
    """Return the SAP AI Core orchestration completion URL directly from env."""
    api_url = os.getenv("SAP_API_URL", "").strip().strip('"')
    if not api_url:
        raise ValueError("SAP_API_URL not set in .env")
    return api_url


async def _sap_chat(
    model: str,
    system: str,
    user: str,
    max_tokens: int = 16000,
    temperature: float = 0.3,
) -> str:
    """Send a chat request via SAP AI Core Orchestration and return the reply text."""
    token          = _get_sap_access_token()
    url            = _sap_chat_url()
    resource_group = os.getenv("SAP_RESOURCE_GROUP", "default").strip().strip('"')

    payload = {
        "config": {
            "modules": {
                "prompt_templating": {
                    "prompt": {
                        "template": [
                            {"role": "system", "content": system},
                            {"role": "user",   "content": user},
                        ]
                    },
                    "model": {
                        "name":    model,
                        "version": "latest",
                        "params": {
                            "temperature": temperature,
                            # max_tokens not supported in SAP AI Core orchestration params
                        },
                    },
                }
            }
        }
    }
    headers = {
        "Authorization":    f"Bearer {token}",
        "Content-Type":     "application/json",
        "ai-resource-group": resource_group,
    }

    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
        return data["final_result"]["choices"][0]["message"]["content"]


# ─────────────────────────────────────────────
# STAGE 1 — Gemini (via SAP AI Core): structured extraction
# ─────────────────────────────────────────────

EXTRACTION_SYSTEM = "You are an expert resume analyst. Return ONLY valid JSON — no markdown, no code fences, no explanation."

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
    """Use gemini-2.5-pro (via SAP AI Core) to extract structured profile data from raw text."""
    prompt = EXTRACTION_PROMPT.format(content=combined_text[:50000])  # safety cap
    raw = await _sap_chat(
        model=_SAP_MODEL_GEMINI,
        system=EXTRACTION_SYSTEM,
        user=prompt,
        max_tokens=8192,
        temperature=0.2,
    )
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Gemini (SAP) returned invalid JSON: {e}\nRaw: {raw[:500]}")
        return {"name": "Professional", "title": "", "summary": combined_text[:500]}


# ─────────────────────────────────────────────
# STAGE 2 — Claude (via SAP AI Core): HTML generation
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
    """Use anthropic--claude-4.7-opus (via SAP AI Core) to generate CV and LinkedIn HTML."""
    profile_json = json.dumps(profile_data, indent=2)

    # Generate CV HTML
    cv_html = await _sap_chat(
        model=_SAP_MODEL_CLAUDE,
        system=CV_HTML_SYSTEM,
        user=CV_HTML_PROMPT.format(profile_json=profile_json),
        max_tokens=16000,
    )
    cv_html = cv_html.strip()
    cv_html = re.sub(r"^```(?:html)?\s*", "", cv_html, flags=re.MULTILINE)
    cv_html = re.sub(r"\s*```$", "", cv_html, flags=re.MULTILINE)

    # Generate LinkedIn HTML
    linkedin_html = await _sap_chat(
        model=_SAP_MODEL_CLAUDE,
        system=LINKEDIN_HTML_SYSTEM,
        user=LINKEDIN_HTML_PROMPT.format(profile_json=profile_json),
        max_tokens=12000,
    )
    linkedin_html = linkedin_html.strip()
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
    """Use anthropic--claude-4.7-opus (via SAP AI Core) to refine CV and LinkedIn HTML."""
    profile_json = json.dumps(profile_data, indent=2)

    # Refine CV HTML
    new_cv = await _sap_chat(
        model=_SAP_MODEL_CLAUDE,
        system="You are an expert front-end developer and resume writer. You refine existing HTML resumes based on user feedback. Output ONLY the complete updated HTML file — no explanation, no markdown, no code fences.",
        user=REFINE_CV_PROMPT.format(
            instructions=instructions,
            profile_json=profile_json,
            cv_html=cv_html[:40000],
        ),
        max_tokens=16000,
    )
    new_cv = new_cv.strip()
    new_cv = re.sub(r"^```(?:html)?\s*", "", new_cv, flags=re.MULTILINE)
    new_cv = re.sub(r"\s*```$", "", new_cv, flags=re.MULTILINE)

    # Refine LinkedIn HTML
    new_li = await _sap_chat(
        model=_SAP_MODEL_CLAUDE,
        system="You are a LinkedIn profile optimization expert and front-end developer. You refine existing LinkedIn helper pages based on user feedback. Output ONLY the complete updated HTML file — no explanation, no markdown, no code fences.",
        user=REFINE_LINKEDIN_PROMPT.format(
            instructions=instructions,
            profile_json=profile_json,
            linkedin_html=linkedin_html[:30000],
        ),
        max_tokens=12000,
    )
    new_li = new_li.strip()
    new_li = re.sub(r"^```(?:html)?\s*", "", new_li, flags=re.MULTILINE)
    new_li = re.sub(r"\s*```$", "", new_li, flags=re.MULTILINE)

    return {"cv_html": new_cv, "linkedin_html": new_li}
