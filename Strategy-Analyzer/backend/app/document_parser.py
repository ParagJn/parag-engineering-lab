import base64
from pathlib import Path
from typing import Any

from docx import Document
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pypdf import PdfReader


MAX_EXTRACTED_CHARS = 120_000
# Anthropic image size limit is ~5 MB base64; keep raw bytes under 3.5 MB
_MAX_IMAGE_BYTES = 3_500_000
# Skip icons/bullets/logos that carry no information
_MIN_IMAGE_BYTES = 4_000


def _clean(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _detect_media_type(data: bytes) -> str:
    """Return MIME type based on magic bytes."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:2] == b"\xff\xd8":
        return "image/jpeg"
    if data[:4] == b"GIF8":
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return ""


def _image_entry(data: bytes, location: str, page: int, seen: set[int]) -> dict[str, Any] | None:
    """Return a dict suitable for vision processing, or None if image should be skipped."""
    if not (_MIN_IMAGE_BYTES <= len(data) <= _MAX_IMAGE_BYTES):
        return None
    media_type = _detect_media_type(data)
    if not media_type:  # EMF/WMF/TIFF etc. are not accepted by vision endpoints
        return None
    digest = hash(data)
    if digest in seen:  # repeated logos / backgrounds
        return None
    seen.add(digest)
    return {
        "data": base64.b64encode(data).decode("utf-8"),
        "media_type": media_type,
        "location": location,
        "page": page,
    }


def extract_images_from_pdf(path: Path) -> list[dict[str, Any]]:
    reader = PdfReader(str(path))
    images: list[dict[str, Any]] = []
    seen: set[int] = set()
    for page_num, page in enumerate(reader.pages, start=1):
        try:
            for img_obj in page.images:
                entry = _image_entry(img_obj.data, f"Page {page_num}", page_num, seen)
                if entry:
                    images.append(entry)
        except Exception:
            pass
    return images


def extract_images_from_docx(path: Path) -> list[dict[str, Any]]:
    doc = Document(str(path))
    images: list[dict[str, Any]] = []
    seen: set[int] = set()
    try:
        for rel in doc.part.rels.values():
            if "image" in rel.reltype:
                try:
                    entry = _image_entry(rel.target_part.blob, "Document", 1, seen)
                    if entry:
                        images.append(entry)
                except Exception:
                    pass
    except Exception:
        pass
    return images


def _iter_shapes(shapes):
    """Yield shapes, descending into groups."""
    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _iter_shapes(shape.shapes)
        else:
            yield shape


def extract_images_from_pptx(path: Path) -> list[dict[str, Any]]:
    deck = Presentation(str(path))
    images: list[dict[str, Any]] = []
    seen: set[int] = set()
    for slide_num, slide in enumerate(deck.slides, start=1):
        for shape in _iter_shapes(slide.shapes):
            if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                try:
                    entry = _image_entry(shape.image.blob, f"Slide {slide_num}", slide_num, seen)
                    if entry:
                        images.append(entry)
                except Exception:
                    pass
    return images


def extract_images(path: Path) -> list[dict[str, Any]]:
    """Dispatch image extraction based on file type."""
    suffix = path.suffix.lower()
    try:
        if suffix == ".pdf":
            return extract_images_from_pdf(path)
        if suffix == ".docx":
            return extract_images_from_docx(path)
        if suffix == ".pptx":
            return extract_images_from_pptx(path)
    except Exception:
        return []
    return []


def build_text(kind: str, pages: list[dict[str, Any]]) -> str:
    """Join pages into one analysis string with explicit [Page N]/[Slide N] markers.

    Image descriptions (page["images"]) are placed inside the page they belong to, so they
    are never the first thing lost to truncation.
    """
    label = {"pdf": "Page", "pptx": "Slide"}.get(kind)
    parts: list[str] = []
    for page in pages:
        chunks = [page.get("text", "")]
        for desc in page.get("images", []):
            chunks.append(f"[Image on {label or 'document'} {page['number']}]\n{desc}")
        body = _clean("\n".join(c for c in chunks if c))
        if label:
            parts.append(f"[{label} {page['number']}]\n{body}" if body else f"[{label} {page['number']}]")
        elif body:
            parts.append(body)
    return "\n\n".join(parts)[:MAX_EXTRACTED_CHARS]


def parse_pdf(path: Path) -> dict[str, Any]:
    reader = PdfReader(str(path))
    pages = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        pages.append({"number": index, "title": f"Page {index}", "text": text.strip()})
    return {"kind": "pdf", "pages": pages, "text": build_text("pdf", pages)}


def parse_docx(path: Path) -> dict[str, Any]:
    doc = Document(str(path))
    blocks = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for table in doc.tables:
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                blocks.append(" | ".join(cells))
    pages = [{"number": 1, "title": "Document", "text": _clean("\n".join(blocks))}]
    return {"kind": "docx", "pages": pages, "text": build_text("docx", pages)}


def _shape_lines(shape) -> list[str]:
    lines: list[str] = []
    if getattr(shape, "has_table", False) and shape.has_table:
        for row in shape.table.rows:
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if cells:
                lines.append(" | ".join(cells))
    elif getattr(shape, "has_text_frame", False) and shape.has_text_frame:
        text = shape.text_frame.text.strip()
        if text:
            lines.append(text)
    return lines


def parse_pptx(path: Path) -> dict[str, Any]:
    deck = Presentation(str(path))
    slides = []
    for index, slide in enumerate(deck.slides, start=1):
        lines: list[str] = []
        for shape in _iter_shapes(slide.shapes):
            lines.extend(_shape_lines(shape))
        title = lines[0].splitlines()[0][:80] if lines else f"Slide {index}"
        text = "\n".join(lines)
        try:
            if slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    text += f"\n[Speaker notes]\n{notes}"
        except Exception:
            pass
        slides.append({"number": index, "title": title, "text": text})
    return {"kind": "pptx", "pages": slides, "text": build_text("pptx", slides)}


def parse_document(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return parse_pdf(path)
    if suffix == ".docx":
        return parse_docx(path)
    if suffix == ".pptx":
        return parse_pptx(path)
    raise ValueError("Unsupported file type. Upload a .pdf, .docx, or .pptx file.")
