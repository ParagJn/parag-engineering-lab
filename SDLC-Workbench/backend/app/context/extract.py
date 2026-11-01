"""Reading text out of uploaded files.

Every file is untrusted. Each reader checks size and shape before it trusts the content, refuses with a
plain reason when it cannot read the file, and returns only extracted text, never the original bytes.
Error messages name the problem and the limit, and never include the file's content.
"""
from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import PurePath

from .chunking import Section, build_sections, markdown_blocks, normalise, plain_sections
from .types import DOCUMENT_KINDS, DocumentRefused, Limits

NO_TEXT_PDF = (
    "this PDF has no extractable text. It is probably a scan, and scanned documents need OCR, "
    "which this prototype does not do"
)


@dataclass(frozen=True)
class Extracted:
    kind: str
    sections: list[Section]
    chars: int


def kind_from_name(filename: str) -> str:
    name = PurePath(filename.replace("\\", "/")).name
    suffix = PurePath(name).suffix.lower().lstrip(".")
    aliases = {"markdown": "md", "text": "txt"}
    kind = aliases.get(suffix, suffix)
    if kind not in DOCUMENT_KINDS:
        raise DocumentRefused(
            f"'{_safe_name(name)}' is not a supported file type; supported types are "
            f"{', '.join('.' + k for k in DOCUMENT_KINDS)}"
        )
    return kind


def _safe_name(name: str) -> str:
    """A filename fit to put in a message or an audit row: no path, no control characters, bounded."""
    name = PurePath(str(name).replace("\\", "/")).name
    name = "".join(ch for ch in name if ch.isprintable())
    return (name or "unnamed")[:120]


def clean_filename(filename: str) -> str:
    return _safe_name(filename)


def _decode(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        return data[3:].decode("utf-8", errors="replace")
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def _looks_binary(data: bytes) -> bool:
    sample = data[:4096]
    return b"\x00" in sample and not sample.startswith((b"\xff\xfe", b"\xfe\xff"))


def _read_text(data: bytes, kind: str) -> list[Section]:
    if _looks_binary(data):
        raise DocumentRefused(f"this file is not plain text, so it cannot be read as .{kind}")
    text = _decode(data)
    if kind == "md":
        return build_sections(markdown_blocks(text))
    return plain_sections(text)


def _read_docx(data: bytes, limits: Limits) -> list[Section]:
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise DocumentRefused("this file is not a Word document (.docx) even though its name says so")
    # Bound what decompression can produce before python-docx expands the archive.
    max_total = limits.max_file_bytes * limits.max_uncompressed_factor
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            total = sum(info.file_size for info in archive.infolist())
            if total > max_total:
                raise DocumentRefused(
                    f"this Word document expands to more than {max_total // (1024 * 1024)} MB when opened, "
                    "which is over the limit"
                )
            if len(archive.infolist()) > 5000:
                raise DocumentRefused("this Word document contains too many internal files")
    except zipfile.BadZipFile:
        raise DocumentRefused("this Word document is corrupt and cannot be opened") from None

    try:
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        document = Document(io.BytesIO(data))
    except DocumentRefused:
        raise
    except Exception:
        raise DocumentRefused("this Word document is corrupt or not valid and cannot be read") from None

    blocks = []
    body = document.element.body
    for child in body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            paragraph = Paragraph(child, document)
            text = paragraph.text.strip()
            if not text:
                blocks.append((None, ""))
                continue
            style = (paragraph.style.name if paragraph.style is not None else "") or ""
            heading = re.match(r"(?i)heading\s*(\d)", style)
            if heading:
                blocks.append((max(1, min(int(heading.group(1)), 6)), text))
            elif re.match(r"(?i)title\b", style):
                blocks.append((1, text))
            else:
                blocks.append((None, text))
                blocks.append((None, ""))
        elif tag == "tbl":
            table = Table(child, document)
            for row in table.rows:
                cells = []
                for cell in row.cells:
                    text = " ".join(cell.text.split())
                    if text and (not cells or cells[-1] != text):  # merged cells repeat; keep one
                        cells.append(text)
                if cells:
                    blocks.append((None, " | ".join(cells)))
            blocks.append((None, ""))
    return build_sections(blocks)


def _read_pdf(data: bytes, limits: Limits) -> list[Section]:
    if not data.lstrip()[:5] == b"%PDF-":
        raise DocumentRefused("this file is not a PDF even though its name says so")
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")  # many "encrypted" PDFs open with no password
            except Exception:
                unlocked = 0
            if not unlocked:
                raise DocumentRefused("this PDF is password-protected and cannot be read")
        pages = list(reader.pages)
    except DocumentRefused:
        raise
    except Exception:
        raise DocumentRefused("this PDF is corrupt or not valid and cannot be read") from None

    if len(pages) > limits.max_pdf_pages:
        raise DocumentRefused(f"this PDF has {len(pages)} pages; the limit is {limits.max_pdf_pages}")

    sections: list[Section] = []
    for number, page in enumerate(pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""  # one unreadable page should not sink the document; the empty check below still applies
        cleaned = normalise(text)
        if cleaned:
            sections.append(Section("", cleaned, number))
    if not sections:
        raise DocumentRefused(NO_TEXT_PDF)
    return sections


def extract(filename: str, data: bytes, limits: Limits | None = None) -> Extracted:
    limits = limits or Limits()
    kind = kind_from_name(filename)
    if not data:
        raise DocumentRefused("this file is empty")
    if len(data) > limits.max_file_bytes:
        raise DocumentRefused(
            f"this file is {len(data) / (1024 * 1024):.1f} MB; the limit is {limits.max_file_bytes // (1024 * 1024)} MB"
        )
    if kind in ("txt", "md"):
        sections = _read_text(data, kind)
    elif kind == "docx":
        sections = _read_docx(data, limits)
    else:
        sections = _read_pdf(data, limits)
    sections = [s for s in sections if s.text.strip()]
    chars = sum(len(s.text) for s in sections)
    if chars == 0:
        raise DocumentRefused("this file contains no readable text")
    return Extracted(kind, sections, chars)
