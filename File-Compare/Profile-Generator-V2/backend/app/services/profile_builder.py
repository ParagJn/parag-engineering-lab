from __future__ import annotations

import re
from collections import Counter


SECTION_HINTS = {
    "experience": ["experience", "work history", "employment", "professional experience"],
    "education": ["education", "academic", "degree", "university", "college"],
    "skills": ["skills", "tools", "technologies", "tech stack", "competencies"],
    "projects": ["projects", "portfolio", "case study"],
    "certifications": ["certification", "certificate", "credential"],
}

COMMON_STOPWORDS = {
    "the", "and", "for", "with", "that", "from", "have", "this", "your", "you", "into",
    "over", "will", "was", "are", "our", "their", "using", "within", "across", "to", "of", "in",
}

HIGH_SIGNAL_KEYWORDS = {
    "python", "fastapi", "react", "node.js", "node", "typescript", "javascript", "aws", "azure",
    "gcp", "docker", "kubernetes", "postgresql", "mongodb", "redis", "microservices", "api",
    "machine learning", "ai", "llm", "rag", "data engineering", "ci/cd", "devops", "terraform",
    "system design", "leadership", "stakeholder management", "product strategy", "agile",
}


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}")
URL_RE = re.compile(r"https?://[^\s)]+")


def split_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def guess_name(lines: list[str]) -> str:
    for line in lines[:12]:
        if 2 <= len(line.split()) <= 5 and line.replace(" ", "").isalpha():
            return line
    return "Candidate"


def extract_contact(text: str) -> dict[str, str]:
    email_match = EMAIL_RE.search(text)
    phone_match = PHONE_RE.search(text)
    urls = URL_RE.findall(text)

    linkedin = ""
    github = ""
    website = ""
    for url in urls:
        low = url.lower()
        if "linkedin.com" in low and not linkedin:
            linkedin = url
        elif "github.com" in low and not github:
            github = url
        elif not website:
            website = url

    return {
        "email": email_match.group(0) if email_match else "",
        "phone": phone_match.group(0) if phone_match else "",
        "linkedin": linkedin,
        "github": github,
        "website": website,
    }


def extract_keywords(text: str, max_items: int = 35) -> list[str]:
    lowered = text.lower()
    selected = [kw for kw in HIGH_SIGNAL_KEYWORDS if kw in lowered]

    tokens = re.findall(r"[a-zA-Z][a-zA-Z+.#/-]{2,}", lowered)
    freq = Counter(tok for tok in tokens if tok not in COMMON_STOPWORDS and len(tok) >= 3)

    fallback = [token for token, count in freq.most_common(80) if count >= 2]
    merged: list[str] = []
    for item in selected + fallback:
        if item not in merged:
            merged.append(item)
        if len(merged) >= max_items:
            break
    return merged


def extract_section_block(text: str, section: str) -> str:
    lines = split_lines(text)
    hints = SECTION_HINTS.get(section, [])

    start_idx = None
    for idx, line in enumerate(lines):
        low = line.lower()
        if any(h in low for h in hints):
            start_idx = idx
            break

    if start_idx is None:
        return ""

    block_lines: list[str] = []
    for line in lines[start_idx + 1 : start_idx + 40]:
        low = line.lower()
        if any(any(h in low for h in SECTION_HINTS[key]) for key in SECTION_HINTS if key != section):
            break
        block_lines.append(line)

    return "\n".join(block_lines).strip()


def build_profile(evidence_text: str, target_role: str = "", target_company: str = "") -> dict:
    lines = split_lines(evidence_text)
    contact = extract_contact(evidence_text)
    keywords = extract_keywords(evidence_text)

    summary_sentences = []
    if target_role:
        summary_sentences.append(
            f"Results-driven professional aligned to {target_role} responsibilities with strong delivery ownership."
        )
    if target_company:
        summary_sentences.append(
            f"Prepared to contribute to {target_company} through measurable execution and cross-functional collaboration."
        )
    summary_sentences.append(
        "Builds high-impact solutions, communicates clearly with stakeholders, and consistently improves product and engineering outcomes."
    )

    skills_top = keywords[:14]
    projects_raw = extract_section_block(evidence_text, "projects")
    project_lines = [ln for ln in split_lines(projects_raw) if len(ln) > 18][:6]

    experience_raw = extract_section_block(evidence_text, "experience")
    experience_lines = [ln for ln in split_lines(experience_raw) if len(ln) > 18][:8]
    if not experience_lines:
        experience_lines = [
            "Delivered production-grade features with measurable business impact.",
            "Collaborated across product, engineering, and operations to accelerate delivery.",
            "Improved reliability, usability, and maintainability through structured execution.",
        ]

    profile = {
        "name": guess_name(lines),
        "title": target_role or "Professional Profile",
        "location": "",
        **contact,
        "summary": " ".join(summary_sentences),
        "headline": f"{target_role or 'Technology Professional'} | Outcome-focused | ATS-optimized profile",
        "core_skills": skills_top,
        "experience_highlights": experience_lines,
        "project_highlights": project_lines,
        "education_notes": extract_section_block(evidence_text, "education")[:1200],
        "certification_notes": extract_section_block(evidence_text, "certifications")[:800],
        "source_keywords": keywords,
    }
    return profile
