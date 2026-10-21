from __future__ import annotations

import difflib
import json
import re
from itertools import zip_longest
from typing import Any

Section = dict[str, str]


def quick_text_diff(a: str, b: str, top_n: int = 12) -> dict[str, Any]:
    a_lines = [line.strip() for line in a.splitlines() if line.strip()]
    b_lines = [line.strip() for line in b.splitlines() if line.strip()]

    matcher = difflib.SequenceMatcher(None, a_lines, b_lines)
    changes: list[dict[str, str]] = []
    added = removed = replaced = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            added += j2 - j1
        elif tag == "delete":
            removed += i2 - i1
        elif tag == "replace":
            replaced += max(i2 - i1, j2 - j1)
        changes.append(
            {
                "type": tag,
                "file_a_excerpt": " ".join(a_lines[i1:i2])[:260],
                "file_b_excerpt": " ".join(b_lines[j1:j2])[:260],
                "file_a_lines": f"{i1 + 1}-{i2}",
                "file_b_lines": f"{j1 + 1}-{j2}",
            }
        )

    return {
        "similarity_ratio": matcher.ratio(),
        "added_lines_estimate": added,
        "removed_lines_estimate": removed,
        "replaced_lines_estimate": replaced,
        "top_changes": changes[:top_n],
    }


def _normalize_title(title: str) -> str:
    cleaned = re.sub(r"\s+", " ", (title or "").strip().lower())
    return re.sub(r"[^a-z0-9 ]", "", cleaned)


def quick_section_diff(sections_a: list[Section], sections_b: list[Section], top_n: int = 12) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    matched = missing_a = missing_b = 0

    for left, right in zip_longest(sections_a, sections_b, fillvalue=None):
        title_a = (left or {}).get("title", "[Missing]")
        title_b = (right or {}).get("title", "[Missing]")
        content_a = (left or {}).get("content", "")
        content_b = (right or {}).get("content", "")

        if left is None:
            missing_a += 1
            similarity, status = 0.0, "missing_in_a"
        elif right is None:
            missing_b += 1
            similarity, status = 0.0, "missing_in_b"
        else:
            same_title = _normalize_title(title_a) == _normalize_title(title_b)
            similarity = difflib.SequenceMatcher(None, content_a, content_b).ratio()
            status = "matched_title" if same_title else "aligned_by_position"
            matched += 1

        rows.append(
            {
                "section_a": title_a,
                "section_b": title_b,
                "status": status,
                "similarity": round(similarity, 4),
                "len_a": len(content_a),
                "len_b": len(content_b),
            }
        )

    average = sum(r["similarity"] for r in rows) / len(rows) if rows else 0.0
    return {
        "sections_in_a": len(sections_a),
        "sections_in_b": len(sections_b),
        "matched_sections": matched,
        "missing_in_a": missing_a,
        "missing_in_b": missing_b,
        "section_similarity_avg": round(average, 4),
        "top_section_differences": sorted(rows, key=lambda r: r["similarity"])[:top_n],
    }


def _wording(type_a: str, type_b: str) -> dict[str, str]:
    image_a = type_a == "image-markdown"
    image_b = type_b == "image-markdown"
    if image_a and image_b:
        return {
            "role": "meticulous visual comparison analyst",
            "unit": "visual element",
            "instruction": "Compare two images (represented as markdown extracted from visual content) and produce a precise, element-by-element comparison report in markdown.",
            "req2": "2) Element-by-Element Comparison (for each visual region/component)",
            "req5": "5) Missing visual elements/components from either image",
            "table": "Element/Region | File A | File B | Severity | Notes",
            "detail_table": "Element A | Element B | Similarity | Status",
            "title": "Detailed Image Comparison Report",
        }
    if image_a != image_b:
        return {
            "role": "meticulous content comparison analyst",
            "unit": "content section",
            "instruction": "Compare an image (represented as markdown) and a document, producing a precise, content-by-content comparison report in markdown.",
            "req2": "2) Content-by-Content Comparison (for each aligned content area)",
            "req5": "5) Missing content areas/topics from either file",
            "table": "Content Area | File A | File B | Severity | Notes",
            "detail_table": "Content A | Content B | Similarity | Status",
            "title": "Detailed Content Comparison Report",
        }
    return {
        "role": "meticulous document comparison analyst",
        "unit": "section",
        "instruction": "Compare two documents and produce a precise, section-by-section report in markdown.",
        "req2": "2) Section-by-Section Comparison (for each aligned section)",
        "req5": "5) Missing sections/topics from either document",
        "table": "Section | File A | File B | Severity | Notes",
        "detail_table": "Section A | Section B | Similarity | Status",
        "title": "Detailed Section-by-Section Report",
    }


def report_title(type_a: str, type_b: str) -> str:
    return _wording(type_a, type_b)["title"]


def build_prompt(
    *,
    name_a: str,
    name_b: str,
    type_a: str,
    type_b: str,
    text_a: str,
    text_b: str,
    quick_diff: dict[str, Any],
    section_diff: dict[str, Any],
    report_style: str,
) -> str:
    w = _wording(type_a, type_b)
    return f"""
You are a {w['role']}.
{w['instruction']}

Report requirements:
1) Executive Summary
{w['req2']}
3) Similarities
4) Differences (major first)
{w['req5']}
6) Final verdict with confidence score (0-100)

Formatting requirements:
- Use markdown headings and bullet points.
- Use a table for high-priority differences with columns:
  {w['table']}
- Include a separate {w['unit']}-level table with columns:
  {w['detail_table']}
- Be specific and quote short snippets when needed.
- If content seems truncated, mention that clearly.
- Output must be concise but detailed and actionable.

Comparison context:
- Report style: {report_style}
- File A: {name_a} ({type_a})
- File B: {name_b} ({type_b})
- If a file type is image-markdown, treat its content as markdown extracted from the image's visual content.
- Quick line diff summary: {json.dumps(quick_diff, ensure_ascii=True)}
- Quick section diff summary: {json.dumps(section_diff, ensure_ascii=True)}

===== FILE A CONTENT START =====
{text_a}
===== FILE A CONTENT END =====

===== FILE B CONTENT START =====
{text_b}
===== FILE B CONTENT END =====
""".strip()
