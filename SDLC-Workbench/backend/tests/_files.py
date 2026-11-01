"""Builders for the real files the extraction tests feed in. Nothing here touches the network."""
from __future__ import annotations

import io
import zipfile

from docx import Document
from fpdf import FPDF
from pypdf import PdfReader, PdfWriter


def make_docx(blocks: list[tuple[str, str]], table: list[list[str]] | None = None) -> bytes:
    """blocks: ('h1'|'h2'|'p', text) in order; an optional table is appended at the end."""
    document = Document()
    for kind, text in blocks:
        if kind in ("h1", "h2", "h3"):
            document.add_heading(text, level=int(kind[1]))
        else:
            document.add_paragraph(text)
    if table:
        t = document.add_table(rows=len(table), cols=len(table[0]))
        for r, row in enumerate(table):
            for c, value in enumerate(row):
                t.cell(r, c).text = value
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_pdf(pages: list[str]) -> bytes:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=12)
    for text in pages:
        pdf.add_page()
        pdf.multi_cell(0, 8, text)
    # This is the older fpdf: output(dest="S") returns the document as a latin-1 string, not bytes.
    out = pdf.output(dest="S")
    return out.encode("latin-1") if isinstance(out, str) else bytes(out)


def blank_pdf(pages: int = 1) -> bytes:
    """A real PDF with no text at all: what a scanned document looks like to a text extractor."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def encrypt_pdf(data: bytes, user_password: str) -> bytes:
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(data)))
    writer.encrypt(user_password=user_password, owner_password="owner-password")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def zip_bomb_docx(uncompressed_mb: int) -> bytes:
    """A small file that expands to `uncompressed_mb` MB when opened. Not a valid Word file, on purpose:
    the size check must fire BEFORE anything tries to parse it."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"0" * (uncompressed_mb * 1024 * 1024))
    return buffer.getvalue()
