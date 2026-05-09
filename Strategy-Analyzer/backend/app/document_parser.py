from pathlib import Path
from typing import Any

from docx import Document
from pptx import Presentation
from pypdf import PdfReader


MAX_EXTRACTED_CHARS = 120_000


def _trim(text: str) -> str:
    cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    return cleaned[:MAX_EXTRACTED_CHARS]


def parse_pdf(path: Path) -> dict[str, Any]:
    reader = PdfReader(str(path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        pages.append({"number": index, "title": f"Page {index}", "text": text.strip()})
    return {"kind": "pdf", "pages": pages, "text": _trim("\n\n".join(p["text"] for p in pages))}


def parse_docx(path: Path) -> dict[str, Any]:
    doc = Document(str(path))
    blocks = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                blocks.append(" | ".join(cells))
    text = _trim("\n".join(blocks))
    return {"kind": "docx", "pages": [{"number": 1, "title": "Document", "text": text}], "text": text}


def parse_pptx(path: Path) -> dict[str, Any]:
    deck = Presentation(str(path))
    slides = []
    for index, slide in enumerate(deck.slides, start=1):
        lines = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                lines.append(shape.text.strip())
        title = lines[0].splitlines()[0][:80] if lines else f"Slide {index}"
        slides.append({"number": index, "title": title, "text": "\n".join(lines)})
    return {"kind": "pptx", "pages": slides, "text": _trim("\n\n".join(s["text"] for s in slides))}


def parse_document(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix == ".docx":
        return parse_docx(path)
    if suffix == ".pptx":
        return parse_pptx(path)
    raise ValueError("Unsupported file type. Upload a .pdf, .docx, or .pptx file.")
