from __future__ import annotations

import logging
from io import BytesIO
from pathlib import Path
from typing import Any

from docx import Document
from pypdf import PdfReader

logger = logging.getLogger(__name__)

IMAGE_SUFFIXES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
DOCUMENT_SUFFIXES = {".pdf", ".docx"}
ALLOWED_SUFFIXES = set(IMAGE_SUFFIXES) | DOCUMENT_SUFFIXES

Section = dict[str, str]


def is_image(file_name: str) -> bool:
    return Path(file_name).suffix.lower() in IMAGE_SUFFIXES


def image_media_type(file_name: str) -> str:
    return IMAGE_SUFFIXES.get(Path(file_name).suffix.lower(), "application/octet-stream")


def _join_sections(sections: list[Section], markers: bool) -> str:
    if markers:
        return "\n".join(f"\n\n--- {s['title']} ---\n{s['content']}" for s in sections).strip()
    return "\n".join(s["content"] for s in sections).strip()


def extract_pdf(data: bytes, markers: bool, max_pages: int) -> tuple[str, list[Section], int]:
    reader = PdfReader(BytesIO(data))
    count = min(len(reader.pages), max_pages)
    sections: list[Section] = []
    for index in range(count):
        try:
            text = (reader.pages[index].extract_text() or "").strip()
        except Exception:
            text = ""
        sections.append({"title": f"Page {index + 1}", "content": text})
    return _join_sections(sections, markers), sections, count


def _looks_like_heading(text: str, style_name: str) -> bool:
    if not text:
        return False
    if (style_name or "").lower().startswith("heading"):
        return True
    return len(text) <= 90 and text.endswith(":")


def extract_docx(data: bytes, markers: bool, paragraphs_per_section: int) -> tuple[str, list[Section], int]:
    doc = Document(BytesIO(data))
    sections: list[Section] = []
    title = "Introduction"
    lines: list[str] = []

    for para in doc.paragraphs:
        text = (para.text or "").strip()
        if not text:
            continue
        style_name = para.style.name if para.style else ""
        if _looks_like_heading(text, style_name):
            if lines:
                sections.append({"title": title, "content": "\n".join(lines).strip()})
            title, lines = text, []
            continue
        lines.append(text)
    if lines:
        sections.append({"title": title, "content": "\n".join(lines).strip()})

    if not sections:
        # No headings found: fall back to fixed-size paragraph blocks.
        paragraphs = [p.text.strip() for p in doc.paragraphs if (p.text or "").strip()]
        size = max(1, paragraphs_per_section)
        for start in range(0, len(paragraphs), size):
            sections.append(
                {"title": f"Section Block {start // size + 1}", "content": "\n".join(paragraphs[start : start + size])}
            )

    return _join_sections(sections, markers), sections, len(sections)


def split_markdown_sections(markdown: str) -> list[Section]:
    sections: list[Section] = []
    title = "Visual Overview"
    lines: list[str] = []
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            if lines:
                sections.append({"title": title, "content": "\n".join(lines).strip()})
            title = stripped.lstrip("#").strip() or "Untitled Section"
            lines = []
            continue
        lines.append(line)
    if lines:
        sections.append({"title": title, "content": "\n".join(lines).strip()})
    return sections or [{"title": "Visual Overview", "content": markdown.strip()}]


def extract_document(file_name: str, data: bytes, *, markers: bool, max_pages: int, paragraphs_per_section: int) -> dict[str, Any]:
    """Extract a PDF or DOCX. Images are handled separately because they need the vision model."""
    suffix = Path(file_name).suffix.lower()
    if suffix == ".pdf":
        text, sections, count = extract_pdf(data, markers, max_pages)
        return {"text": text, "sections": sections, "units": count, "units_label": "pages", "type": "pdf"}
    if suffix == ".docx":
        text, sections, count = extract_docx(data, markers, paragraphs_per_section)
        return {"text": text, "sections": sections, "units": count, "units_label": "sections", "type": "docx"}
    raise ValueError(f"Unsupported file type: {suffix or '(none)'}. Use .pdf, .docx, .png, .jpg, .jpeg or .webp.")


def truncate_for_llm(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    logger.warning("Text truncated from %s to %s chars", len(text), max_chars)
    return text[:max_chars] + "\n\n[TRUNCATED DUE TO LENGTH]", True
