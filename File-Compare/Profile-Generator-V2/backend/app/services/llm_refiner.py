from __future__ import annotations

import json
import os


SYSTEM_PROMPT = (
    "You are an expert executive resume writer and ATS optimization specialist. "
    "Improve the provided structured profile for factual consistency, clarity, and recruiter relevance. "
    "Do not invent facts. Return JSON only using the same keys."
)


def _safe_profile(profile: dict) -> dict:
    profile.setdefault("name", "Candidate")
    profile.setdefault("title", "Professional Profile")
    profile.setdefault("summary", "")
    profile.setdefault("core_skills", [])
    profile.setdefault("experience_highlights", [])
    profile.setdefault("project_highlights", [])
    profile.setdefault("education_notes", "")
    profile.setdefault("certification_notes", "")
    profile.setdefault("source_keywords", [])
    return profile


async def maybe_refine_profile_with_openai(profile: dict, evidence_text: str, target_role: str = "", target_company: str = "") -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return _safe_profile(profile)

    try:
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
        payload = {
            "target_role": target_role,
            "target_company": target_company,
            "profile": profile,
            "evidence_excerpt": evidence_text[:14000],
            "instructions": [
                "Preserve factual integrity from evidence.",
                "Rewrite summary for executive clarity and measurable impact tone.",
                "Improve experience highlights to be action+impact oriented.",
                "Normalize core skills naming for ATS friendliness.",
                "Keep concise and professional.",
            ],
        }

        response = await client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content or "{}"
        refined = json.loads(content)

        # allow direct object or wrapped payload
        if "profile" in refined and isinstance(refined["profile"], dict):
            refined = refined["profile"]

        if not isinstance(refined, dict):
            return _safe_profile(profile)

        # Keep source keywords from deterministic extraction for stable ATS baseline.
        refined["source_keywords"] = profile.get("source_keywords", [])
        return _safe_profile(refined)
    except Exception:
        return _safe_profile(profile)
