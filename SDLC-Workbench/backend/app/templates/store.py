"""Storing a project's Word templates (S23 Part C). Files only: no database, no model, and no change to how any document is made.

Layout, inside the git-ignored data folder:   Templates/<project id>/<category>.docx
  * one file per category per project; a new upload for the same category REPLACES the old one (no versions);
  * the project folder is the project's ID, checked against a strict pattern, and the category is one of a fixed list, so a name can never point outside the Templates folder;
  * only .docx is accepted: it must be a real Word package (a zip with the Word parts), not over the size limit, and not carrying macros or an embedded program;
  * the bytes are stored exactly as uploaded (the "original"); nothing is rewritten.

What a template CONTAINS is read for the screen only: its original file name is not kept as a path (only the category), and whether it holds a Table of Contents, which is the one thing a
later step will need to decide whether to use it.
"""
from __future__ import annotations

import io
import os
import re
import tempfile
import zipfile
import zlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

MAX_TEMPLATE_BYTES = 5 * 1024 * 1024
MAX_UNPACKED_BYTES = 50 * 1024 * 1024              # what the package may expand to: a small zip can hold a very large file
MAX_PARTS = 2000
PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# The documents the app can already download as Word. A template belongs to one of them.
CATEGORIES: dict[str, str] = {
    "deployment_plan": "Deployment plan",
    "release_notes": "Release notes",
    "runbook": "Runbook",
    "hypercare_plan": "Hypercare plan",
    "deployment_verification": "Deployment verification report",
    "handover_signoff": "Handover sign-off report",
}

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_REQUIRED_PARTS = ("[Content_Types].xml", "word/document.xml")
# Parts that carry a program or something that reaches outside the file.
_FORBIDDEN_PREFIXES = ("word/vbaProject", "word/embeddings/", "word/activeX/", "customUI/")
_FORBIDDEN_NAMES = ("word/vbaData.xml",)


class TemplateRefused(ValueError):
    """A plain sentence a person can read: why a template was not accepted, or what was asked for that does not exist."""


class TemplateMissing(LookupError):
    """There is no template for that category in that project."""


@dataclass(frozen=True)
class TemplateInfo:
    category: str
    label: str
    size: int
    uploaded_at: str
    has_toc: bool
    has_toc_note: str


def _project_dir(root: Path, project_id: str) -> Path:
    if not PROJECT_ID.fullmatch(project_id or ""):
        raise TemplateRefused("that is not a project the templates can be kept for")
    return root / project_id


def _category(category: str) -> str:
    if category not in CATEGORIES:
        raise TemplateRefused(f"there is no document type {category!r}; the types are {', '.join(CATEGORIES)}")
    return category


def _path(root: Path, project_id: str, category: str) -> Path:
    return _project_dir(root, project_id) / f"{_category(category)}.docx"


def check_docx(data: bytes) -> None:
    """Refuse anything that is not a plain Word document. Reads the zip's list of parts only; nothing is unpacked to disk and nothing is run."""
    if not data:
        raise TemplateRefused("the file is empty")
    if len(data) > MAX_TEMPLATE_BYTES:
        raise TemplateRefused(f"this file is larger than the {MAX_TEMPLATE_BYTES // (1024 * 1024)} MB limit for a template")
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise TemplateRefused("this is not a Word document (.docx): it is not a Word package")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            if len(infos) > MAX_PARTS:
                raise TemplateRefused("this Word document has too many parts to be a template")
            if sum(i.file_size for i in infos) > MAX_UNPACKED_BYTES:
                raise TemplateRefused(f"this Word document expands to more than {MAX_UNPACKED_BYTES // (1024 * 1024)} MB when opened, which is over the limit")
            missing = [n for n in _REQUIRED_PARTS if n not in names]
            if missing:
                raise TemplateRefused("this is not a Word document (.docx): it has no document body")
            if any(n.startswith(_FORBIDDEN_PREFIXES) or n in _FORBIDDEN_NAMES for n in names):
                raise TemplateRefused("this document carries macros or embedded programs, which a template may not")
            content_types = archive.read("[Content_Types].xml")
            if b"macroEnabled" in content_types or b"vbaProject" in content_types:
                raise TemplateRefused("this is a macro-enabled document, which a template may not be")
            if b"template.main+xml" in content_types and b"document.main+xml" not in content_types:
                raise TemplateRefused("this is a Word template file (.dotx); save it as a Word document (.docx) and upload that")
            if archive.testzip() is not None:
                raise TemplateRefused("this Word document is damaged")
    except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, OSError):          # a damaged or unusual package fails while it is read; that is a refusal, not a crash
        raise TemplateRefused("this Word document is damaged or is not a readable Word package") from None


def table_of_contents(data: bytes) -> bool:
    """Does the document hold a Table of Contents? Word keeps one either as a field (TOC) in the body, or as a built-in content block. Both are recognised. Only the body is read."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile):
        return False
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return False
    for instr in root.iter(f"{_W}instrText"):
        if re.match(r"\s*TOC\b", instr.text or ""):
            return True
    for fld in root.iter(f"{_W}fldSimple"):
        if re.match(r"\s*TOC\b", fld.get(f"{_W}instr", "")):
            return True
    for gallery in root.iter(f"{_W}docPartGallery"):
        if "Table of Contents" in (gallery.get(f"{_W}val", "")):
            return True
    return False


def _info(path: Path, category: str) -> TemplateInfo:
    data = path.read_bytes()
    toc = table_of_contents(data)
    when = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    note = "It has a table of contents, so downloads of this document can use it." if toc else "No table of contents was found in this file, so downloads will use the standard layout."
    return TemplateInfo(category, CATEGORIES[category], len(data), when, toc, note)


def save(root: Path, project_id: str, category: str, data: bytes) -> TemplateInfo:
    """Check, then store the original bytes as Templates/<project>/<category>.docx, replacing any earlier one. Nothing is stored if anything is refused."""
    target = _path(root, project_id, category)
    check_docx(data)
    target.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(target.parent, 0o700)
    fd, tmp = tempfile.mkstemp(prefix=".upload-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.chmod(tmp, 0o600)
        os.replace(tmp, target)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return _info(target, category)


def listing(root: Path, project_id: str) -> list[TemplateInfo]:
    """Every category, in the fixed order, for those that have a template. A project with none gives an empty list; a missing folder is not an error."""
    folder = _project_dir(root, project_id)
    return [_info(folder / f"{c}.docx", c) for c in CATEGORIES if (folder / f"{c}.docx").is_file()]


def read(root: Path, project_id: str, category: str) -> bytes:
    path = _path(root, project_id, category)
    if not path.is_file():
        raise TemplateMissing(f"there is no template for {CATEGORIES[category]} in this project")
    return path.read_bytes()


def remove(root: Path, project_id: str, category: str) -> None:
    path = _path(root, project_id, category)
    if not path.is_file():
        raise TemplateMissing(f"there is no template for {CATEGORIES[category]} in this project")
    path.unlink()


def payload(info: TemplateInfo) -> dict[str, Any]:
    return {"category": info.category, "label": info.label, "size": info.size, "uploaded_at": info.uploaded_at, "has_toc": info.has_toc, "toc_note": info.has_toc_note}
