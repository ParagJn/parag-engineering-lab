from __future__ import annotations

import io
import re
from pathlib import Path

import pdfplumber
from bs4 import BeautifulSoup
from docx import Document


ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".html", ".htm"}


def clean_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def parse_pdf(content: bytes) -> str:
    extracted: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            extracted.append(page.extract_text() or "")
    return clean_text("\n".join(extracted))


def parse_docx(content: bytes) -> str:
    document = Document(io.BytesIO(content))
    paragraphs = [p.text for p in document.paragraphs if p.text and p.text.strip()]
    return clean_text("\n".join(paragraphs))


def parse_html(content: bytes) -> str:
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return clean_text(soup.get_text("\n"))


def parse_file(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return ""
    if ext == ".pdf":
        return parse_pdf(content)
    if ext == ".docx":
        return parse_docx(content)
    if ext in {".html", ".htm"}:
        return parse_html(content)
    return clean_text(content.decode("utf-8", errors="ignore"))
