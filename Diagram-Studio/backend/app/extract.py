"""Turn an uploaded .md / .txt / .docx file into plain markdown-ish text for the planner."""

from __future__ import annotations

import io
import re
from pathlib import Path

ALLOWED_SUFFIXES = {".md", ".markdown", ".txt", ".docx"}


def extract_text(name: str, data: bytes) -> str:
    suffix = Path(name).suffix.lower()
    if suffix == ".docx":
        text = docx_to_markdown(data)
    elif suffix in {".md", ".markdown", ".txt"}:
        text = data.decode("utf-8-sig", errors="replace")
    else:
        raise ValueError(f"Unsupported file type '{suffix or name}'. Use .md, .txt or .docx.")
    return normalize(text)


def normalize(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    return re.sub(r"\n{4,}", "\n\n\n", text).strip()


def docx_to_markdown(data: bytes) -> str:
    """Walk the body in order so headings, lists and tables keep their place."""
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = Document(io.BytesIO(data))
    out: list[str] = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = Paragraph(child, doc)
            text = para.text.strip()
            if not text:
                continue
            out.append(_format_paragraph(para, text))
        elif tag == "tbl":
            table_md = _format_table(Table(child, doc))
            if table_md:
                out.append(table_md)
    return "\n\n".join(out)


def _format_paragraph(para, text: str) -> str:
    style = (para.style.name if para.style is not None else "") or ""
    lowered = style.lower()
    if lowered == "title":
        return f"# {text}"
    if lowered.startswith("heading"):
        digits = "".join(ch for ch in lowered if ch.isdigit())
        level = min(max(int(digits), 1), 6) if digits else 1
        return f"{'#' * level} {text}"
    if "list number" in lowered:
        return f"1. {text}"
    if lowered.startswith("list"):
        return f"- {text}"
    return text


def _format_table(table) -> str:
    rows: list[list[str]] = []
    for row in table.rows:
        cells: list[str] = []
        previous = None
        for cell in row.cells:
            # Merged cells are repeated by python-docx; keep one copy.
            if cell._tc is previous:
                continue
            previous = cell._tc
            cells.append(cell.text.strip().replace("\n", " ").replace("|", "/"))
        rows.append(cells)
    rows = [r for r in rows if any(r)]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    lines = ["| " + " | ".join(rows[0]) + " |", "| " + " | ".join(["---"] * width) + " |"]
    lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
    return "\n".join(lines)


def truncate_for_llm(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit], True
