"""Markdown in, a Word file out (S21b). Pure functions: no model, no network, no database, no files; the bytes are returned.

What is written, and nothing else: headings (as Word's own heading styles), paragraphs, bold, italic and inline code, bullet and numbered lists (nested), block quotes,
code blocks (in a code style), tables (with a header row), horizontal rules, and links whose address is http, https or mailto. Anything else is written as its plain text.
A Word file never holds anything the Markdown does not: no hidden text, no macros, no embedded objects, and a link to any other kind of address is plain text.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor
from docx.text.paragraph import Paragraph
from markdown_it import MarkdownIt
from markdown_it.token import Token

SAFE_LINK = re.compile(r"^(https?://|mailto:)", re.IGNORECASE)
CODE_STYLE = "Code Block"
QUOTE_STYLE = "Block Quote"
INLINE_CODE_FONT = "Courier New"
_XML_BAD = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass(frozen=True)
class DocInfo:
    """What goes in the document's properties and nowhere in its body."""
    title: str
    subject: str = ""
    author: str = "SDLC Workbench"
    created: datetime | None = None


def _clean(text: str) -> str:
    """Word's XML cannot hold control characters; they are dropped."""
    return _XML_BAD.sub("", text or "")


def _styles(doc) -> None:
    styles = doc.styles
    if CODE_STYLE not in [s.name for s in styles]:
        code = styles.add_style(CODE_STYLE, WD_STYLE_TYPE.PARAGRAPH)
        code.base_style = styles["Normal"]
        code.font.name = INLINE_CODE_FONT
        code.font.size = Pt(9)
        code.paragraph_format.left_indent = Pt(12)
        code.paragraph_format.space_after = Pt(6)
    if QUOTE_STYLE not in [s.name for s in styles]:
        quote = styles.add_style(QUOTE_STYLE, WD_STYLE_TYPE.PARAGRAPH)
        quote.base_style = styles["Normal"]
        quote.font.italic = True
        quote.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
        quote.paragraph_format.left_indent = Pt(18)


def _hyperlink(paragraph: Paragraph, text: str, url: str, bold: bool, italic: bool) -> None:
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    props = OxmlElement("w:rPr")
    style = OxmlElement("w:rStyle")
    style.set(qn("w:val"), "Hyperlink")
    props.append(style)
    colour = OxmlElement("w:color")
    colour.set(qn("w:val"), "0563C1")
    props.append(colour)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    props.append(underline)
    if bold:
        props.append(OxmlElement("w:b"))
    if italic:
        props.append(OxmlElement("w:i"))
    run.append(props)
    node = OxmlElement("w:t")
    node.text = text
    node.set(qn("xml:space"), "preserve")
    run.append(node)
    link.append(run)
    paragraph._p.append(link)


def _inline(paragraph: Paragraph, children: Iterable[Token]) -> None:
    """Write the inline tokens of one block into a paragraph, keeping bold, italic, code and safe links."""
    bold = italic = 0
    link: str | None = None
    for t in children:
        if t.type == "strong_open":
            bold += 1
        elif t.type == "strong_close":
            bold -= 1
        elif t.type == "em_open":
            italic += 1
        elif t.type == "em_close":
            italic -= 1
        elif t.type == "link_open":
            href = t.attrGet("href") or ""
            link = href if SAFE_LINK.match(href) else None
        elif t.type == "link_close":
            link = None
        elif t.type in ("softbreak", "hardbreak"):
            paragraph.add_run().add_break(WD_BREAK.LINE if t.type == "hardbreak" else WD_BREAK.LINE)
        elif t.type == "code_inline":
            run = paragraph.add_run(_clean(t.content))
            run.font.name = INLINE_CODE_FONT
            run.bold, run.italic = bool(bold) or None, bool(italic) or None
        elif t.type == "text":
            text = _clean(t.content)
            if link is not None:
                _hyperlink(paragraph, text, link, bool(bold), bool(italic))
            else:
                run = paragraph.add_run(text)
                run.bold, run.italic = bool(bold) or None, bool(italic) or None
        elif t.type == "image":
            paragraph.add_run(_clean(t.content or t.attrGet("alt") or ""))                  # an image is never embedded or fetched: its description stands in
        elif t.type in ("html_inline",):
            continue


def _shade(cell, fill: str) -> None:
    props = cell._tc.get_or_add_tcPr()
    shade = OxmlElement("w:shd")
    shade.set(qn("w:val"), "clear")
    shade.set(qn("w:color"), "auto")
    shade.set(qn("w:fill"), fill)
    props.append(shade)


def _repeat_header(row) -> None:
    props = row._tr.get_or_add_trPr()
    flag = OxmlElement("w:tblHeader")
    flag.set(qn("w:val"), "true")
    props.append(flag)


class _Writer:
    def __init__(self, doc) -> None:
        self.doc = doc
        self.list_stack: list[tuple[str, int]] = []          # (kind, depth)

    def _list_style(self) -> str:
        kind, depth = self.list_stack[-1]
        base = "List Bullet" if kind == "ul" else "List Number"
        return base if depth == 1 else f"{base} {min(depth, 3)}"

    def write(self, tokens: list[Token]) -> None:
        i = 0
        while i < len(tokens):
            i = self._block(tokens, i)

    def _block(self, tokens: list[Token], i: int) -> int:
        t = tokens[i]
        if t.type == "heading_open":
            level = int(t.tag[1])                                    # Markdown has h1 to h6 and Word has Heading 1 to 9, so no cap is needed
            para = self.doc.add_heading(level=level)
            _inline(para, tokens[i + 1].children or [])
            return i + 3
        if t.type == "paragraph_open":
            inline = tokens[i + 1]
            if self.list_stack:
                para = self.doc.add_paragraph(style=self._list_style())
            elif any(s.type == "blockquote_open" for s in tokens[:i]) and self._in_quote(tokens, i):
                para = self.doc.add_paragraph(style=QUOTE_STYLE)
            else:
                para = self.doc.add_paragraph()
            _inline(para, inline.children or [])
            return i + 3
        if t.type in ("bullet_list_open", "ordered_list_open"):
            depth = len(self.list_stack) + 1
            self.list_stack.append(("ul" if t.type == "bullet_list_open" else "ol", depth))
            return i + 1
        if t.type in ("bullet_list_close", "ordered_list_close"):
            self.list_stack.pop()
            return i + 1
        if t.type in ("list_item_open", "list_item_close", "blockquote_open", "blockquote_close"):
            return i + 1
        if t.type in ("fence", "code_block"):
            for line in _clean(t.content).rstrip("\n").split("\n") or [""]:
                self.doc.add_paragraph(line, style=CODE_STYLE)
            return i + 1
        if t.type == "hr":
            para = self.doc.add_paragraph()
            border = OxmlElement("w:pBdr")
            bottom = OxmlElement("w:bottom")
            for k, v in (("w:val", "single"), ("w:sz", "6"), ("w:space", "1"), ("w:color", "999999")):
                bottom.set(qn(k), v)
            border.append(bottom)
            para._p.get_or_add_pPr().append(border)
            return i + 1
        if t.type == "table_open":
            return self._table(tokens, i)
        if t.type == "html_block":
            return i + 1                                      # raw HTML is never carried into the Word file
        return i + 1

    @staticmethod
    def _in_quote(tokens: list[Token], i: int) -> bool:
        depth = 0
        for t in tokens[:i]:
            if t.type == "blockquote_open":
                depth += 1
            elif t.type == "blockquote_close":
                depth -= 1
        return depth > 0

    def _table(self, tokens: list[Token], i: int) -> int:
        rows: list[list[list[Token]]] = []
        header_rows = 0
        j = i + 1
        while tokens[j].type != "table_close":
            t = tokens[j]
            if t.type == "tr_open":
                rows.append([])
            elif t.type == "thead_open":
                header_rows = 1
            elif t.type in ("th_open", "td_open"):
                rows[-1].append(tokens[j + 1].children or [])
            j += 1
        width = max((len(r) for r in rows), default=0)
        if width:
            table = self.doc.add_table(rows=len(rows), cols=width)
            table.style = "Table Grid"
            for r, row in enumerate(rows):
                for c in range(width):
                    cell = table.cell(r, c)
                    para = cell.paragraphs[0]
                    if c < len(row):
                        _inline(para, row[c])
                    if r < header_rows:
                        for run in para.runs:
                            run.bold = True
                        _shade(cell, "E7E6E6")
                if r < header_rows:
                    _repeat_header(table.rows[r])
            self.doc.add_paragraph()
        return j + 1


def markdown_to_docx(markdown: str, info: DocInfo) -> bytes:
    """The Word file for a piece of Markdown, as bytes. The properties carry the title, subject, author and the time it was made."""
    doc = Document()
    _styles(doc)
    core = doc.core_properties
    core.title, core.subject, core.author = _clean(info.title)[:255], _clean(info.subject)[:255], _clean(info.author)[:255]
    core.created = core.modified = info.created or datetime.now(timezone.utc)
    core.comments = ""
    parser = MarkdownIt("commonmark").enable("table")
    parser.validateLink = lambda url: True                  # read EVERY link as a link, so our own rule (SAFE_LINK) decides alike for all: an unsafe one keeps its words, not its address
    tokens = parser.parse(_clean(markdown or ""))
    _Writer(doc).write(tokens)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()
