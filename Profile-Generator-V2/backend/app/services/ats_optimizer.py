from __future__ import annotations

import re
from collections import Counter


def keyword_candidates(text: str) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z+.#/-]{2,}", text.lower())
    counts = Counter(tokens)
    ignore = {
        "the", "and", "for", "with", "from", "your", "that", "this", "are", "was", "have", "will",
        "you", "our", "but", "not", "all", "into", "their", "about", "been", "role", "team", "work",
    }
    return [token for token, c in counts.most_common(120) if c >= 2 and token not in ignore]


def compute_ats_report(
    profile: dict,
    evidence_text: str,
    target_role: str = "",
    job_description: str = "",
) -> dict:
    evidence_l = evidence_text.lower()
    base_profile_keywords = [k.lower() for k in profile.get("source_keywords", [])]

    jd_keywords = keyword_candidates(job_description)
    role_keywords = keyword_candidates(target_role)

    required = []
    for kw in jd_keywords[:25] + role_keywords[:15]:
        if kw not in required:
            required.append(kw)

    if not required:
        required = base_profile_keywords[:20]

    matched = [kw for kw in required if kw in evidence_l or kw in base_profile_keywords]
    missing = [kw for kw in required if kw not in matched]

    score = 55
    score += min(30, int((len(matched) / max(1, len(required))) * 35))
    if profile.get("summary"):
        score += 5
    if profile.get("experience_highlights"):
        score += 5
    if profile.get("project_highlights"):
        score += 5
    score = max(1, min(99, score))

    tips = [
        "Use quantified impact bullets (percentages, revenue, latency, scale) in Experience.",
        "Mirror exact role vocabulary from job description in Summary and Skills.",
        "Keep headline and title role-aligned so recruiter search filters match faster.",
    ]
    if missing:
        tips.append("Add the top missing keywords naturally across Summary and Core Skills.")

    return {
        "score": score,
        "matched_keywords": matched[:30],
        "missing_keywords": missing[:30],
        "recommended_keywords": (matched[:10] + missing[:10])[:20],
        "section_tips": tips,
    }


def enrich_profile_with_keywords(profile: dict, ats_report: dict) -> dict:
    merged_skills = list(profile.get("core_skills", []))
    for kw in ats_report.get("recommended_keywords", []):
        if kw not in merged_skills and len(merged_skills) < 20:
            merged_skills.append(kw)

    profile["core_skills"] = merged_skills

    summary = profile.get("summary", "")
    inject = [kw for kw in ats_report.get("missing_keywords", [])[:5] if kw not in summary.lower()]
    if inject:
        summary = f"{summary} Key strengths include {', '.join(inject)}."
    profile["summary"] = summary

    return profile
