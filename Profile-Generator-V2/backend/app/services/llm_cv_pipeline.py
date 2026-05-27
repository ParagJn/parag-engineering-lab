from __future__ import annotations

import asyncio
import json
import re


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json|markdown)?\\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\\s*```$", "", text)
    return text.strip()


def _extract_json(text: str) -> dict:
    cleaned = _strip_fences(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


GEMINI_RESEARCH_PROMPT = """
You are a senior talent intelligence researcher and resume strategist.
Analyze the candidate evidence and build a factual, high-signal, ATS-oriented profile model.

Return ONLY valid JSON with this exact structure:
{
  "research_summary": "5-10 sentence summary of career narrative and strongest positioning",
  "targeting_strategy": "how profile should be positioned for the target role/company",
  "ats_keywords": ["keyword1", "keyword2"],
  "profile_json": {
    "name": "",
    "title": "",
    "email": "",
    "phone": "",
    "location": "",
    "linkedin": "",
    "github": "",
    "website": "",
    "summary": "",
    "core_skills": [""],
    "experience_highlights": [""],
    "project_highlights": [""],
    "education_notes": "",
    "certification_notes": "",
    "source_keywords": [""]
  }
}

Rules:
- Use only evidence from provided input context.
- Do not fabricate employers, dates, or credentials.
- Keep achievements concise and impact-oriented.
- Ensure ATS keywords align with target role/job description if available.
""".strip()


ANTHROPIC_CV_PROMPT = """
You are an elite executive resume writer.
Build a completely new, professional CV in markdown from the provided evidence and research profile.

Return ONLY valid JSON with exactly:
{
  "cv_markdown": "full markdown CV",
  "profile_json": {
    "name": "",
    "title": "",
    "email": "",
    "phone": "",
    "location": "",
    "linkedin": "",
    "github": "",
    "website": "",
    "summary": "",
    "core_skills": [""],
    "experience_highlights": [""],
    "project_highlights": [""],
    "education_notes": "",
    "certification_notes": "",
    "source_keywords": [""]
  }
}

CV Requirements:
- Premium professional tone, concise and recruiter-friendly.
- Strong keyword coverage for ATS without stuffing.
- Sections in markdown: Header, Professional Summary, Core Skills, Experience Highlights, Project Highlights, Education, Certifications.
- Use measurable impact phrasing where evidence supports it.
- Do not invent facts beyond evidence/research payload.
""".strip()


def _gemini_generate_sync(api_key: str, payload: dict) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=[GEMINI_RESEARCH_PROMPT, json.dumps(payload, ensure_ascii=False)],
        config=types.GenerateContentConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json",
        ),
    )

    text = (response.text or "").strip()
    data = _extract_json(text)
    if not isinstance(data, dict) or "profile_json" not in data:
        raise ValueError("Gemini returned invalid research payload.")
    return data


async def run_gemini_research(
    evidence_text: str,
    links: list[str],
    target_role: str,
    target_company: str,
    job_description: str,
) -> dict:
    from app.config import settings

    api_key = (settings.gemini_api_key or "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing in environment.")

    payload = {
        "target_role": target_role,
        "target_company": target_company,
        "links": links,
        "job_description": job_description,
        "evidence_excerpt": evidence_text[:80000],
    }

    return await asyncio.to_thread(_gemini_generate_sync, api_key, payload)


def _anthropic_generate_sync(prompt_payload: dict, api_key: str) -> dict:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-opus-4-1-20250805",
        max_tokens=8000,
        temperature=0.2,
        system="Return valid JSON only.",
        messages=[
            {
                "role": "user",
                "content": f"{ANTHROPIC_CV_PROMPT}\n\nINPUT:\n{json.dumps(prompt_payload, ensure_ascii=False)}",
            }
        ],
    )

    text_blocks: list[str] = []
    for block in message.content:
        if getattr(block, "type", "") == "text":
            text_blocks.append(block.text)

    raw_text = "\n".join(text_blocks).strip()
    data = _extract_json(raw_text)
    if not isinstance(data, dict) or "cv_markdown" not in data or "profile_json" not in data:
        raise ValueError("Anthropic returned invalid CV payload.")
    return data


async def run_anthropic_cv_rebuild(
    gemini_payload: dict,
    evidence_text: str,
    target_role: str,
    target_company: str,
    job_description: str,
) -> dict:
    from app.config import settings

    api_key = (settings.anthropic_api_key or "").strip()
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is missing in environment.")

    prompt_payload = {
        "target_role": target_role,
        "target_company": target_company,
        "job_description": job_description,
        "gemini_payload": gemini_payload,
        "evidence_excerpt": evidence_text[:70000],
    }

    return await asyncio.to_thread(_anthropic_generate_sync, prompt_payload, api_key)
