"""Cutting text into chunks: the pieces that get retrieved and cited.

A chunk is meant to be one idea. Text is split on headings first, then on blank lines, then packed up
to a target size. No chunk exceeds the hard cap, and no text is lost: joining a section's chunks and
removing whitespace gives back the section's text with whitespace removed.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable, Sequence

from .types import Limits

# (heading level, text) for a heading, (None, text) for an ordinary line.
Block = tuple["int | None", str]

_HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)(?:[ \t]+#+)?[ \t]*$")
_FENCE = re.compile(r"^(```|~~~)")
_PARAGRAPH_BREAK = re.compile(r"\n[ \t]*\n")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)
_LINE_BREAKS = {ord(c): "\n" for c in "\x0b\x0c \x85"}


@dataclass(frozen=True)
class Section:
    heading_path: str
    text: str
    page: int | None = None


@dataclass(frozen=True)
class Chunk:
    heading_path: str
    text: str
    page: int | None = None


def normalise(text: str) -> str:
    """Make text uniform without changing what it says.

    Line endings become \\n, invisible and control characters go, non-breaking spaces become spaces,
    and runs of blank lines collapse to one.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.translate(_LINE_BREAKS).replace(" ", "\n\n").replace(" ", " ").replace("\t", " ")
    text = text.translate(_ZERO_WIDTH)
    text = "".join(ch for ch in text if ch == "\n" or unicodedata.category(ch) != "Cc")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# ---- turning text into headed sections -----------------------------------------------

def markdown_blocks(text: str) -> list[Block]:
    """Lines of Markdown as blocks. A heading inside a code fence is not a heading."""
    blocks: list[Block] = []
    fence: str | None = None
    for line in normalise(text).split("\n"):
        stripped = line.lstrip()
        indent = len(line) - len(stripped)
        fence_match = _FENCE.match(stripped) if indent <= 3 else None
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            blocks.append((None, line))
            continue
        if fence is None:
            heading = _HEADING.match(line)
            if heading and heading.group(2).strip():
                blocks.append((len(heading.group(1)), heading.group(2).strip()))
                continue
        blocks.append((None, line))
    return blocks


def build_sections(blocks: Iterable[Block], page: int | None = None) -> list[Section]:
    """Group blocks into sections, each carrying its heading path ('Rules > Cancellation').

    A heading with no body of its own is carried forward into the next section, so no heading text is
    lost and no tiny heading-only chunk is created.
    """
    sections: list[Section] = []
    stack: list[tuple[int, str]] = []
    path = ""
    lines: list[str] = []
    carry: list[str] = []
    has_heading = False

    def has_body() -> bool:
        return any(line.strip() for line in (lines[1:] if has_heading else lines))

    def flush(final: bool = False) -> None:
        nonlocal lines, carry
        if has_body() or final:
            text = "\n".join(carry + lines).strip()
            if text:
                sections.append(Section(path, text, page))
            carry = []
        else:
            carry = carry + lines
        lines = []

    for level, text in blocks:
        if level is None:
            lines.append(text)
            continue
        flush()
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, text))
        path = " > ".join(title for _, title in stack)
        lines = [text]
        has_heading = True
    flush(final=True)
    return sections


def sections_from_markdown(text: str) -> list[Section]:
    return build_sections(markdown_blocks(text))


def plain_sections(text: str, page: int | None = None) -> list[Section]:
    """Text with no structure: one section."""
    cleaned = normalise(text)
    return [Section("", cleaned, page)] if cleaned else []


# ---- cutting sections into chunks ---------------------------------------------------------

def _hard_split(text: str, cap: int) -> list[str]:
    """Last resort for one unbroken run longer than the cap: cut at whitespace if there is any."""
    out: list[str] = []
    text = text.strip()
    while len(text) > cap:
        cut = text.rfind(" ", cap // 2, cap)
        cut = cut if cut > 0 else cap
        piece, text = text[:cut].strip(), text[cut:].strip()
        if piece:
            out.append(piece)
    if text:
        out.append(text)
    return out


def _split_long(paragraph: str, limits: Limits) -> list[str]:
    """A paragraph over the cap: pack its sentences, hard-splitting any single sentence that is too long."""
    out: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(paragraph):
        sentence = sentence.strip()
        if not sentence:
            continue
        if len(sentence) > limits.chunk_cap_chars:
            if current:
                out.append(current)
                current = ""
            out.extend(_hard_split(sentence, limits.chunk_cap_chars))
        elif not current:
            current = sentence
        elif len(current) + 1 + len(sentence) <= limits.chunk_target_chars:
            current += " " + sentence
        else:
            out.append(current)
            current = sentence
    if current:
        out.append(current)
    return out


def _pieces(text: str, limits: Limits) -> list[str]:
    pieces: list[str] = []
    for paragraph in _PARAGRAPH_BREAK.split(text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) <= limits.chunk_cap_chars:
            pieces.append(paragraph)
        else:
            pieces.extend(_split_long(paragraph, limits))
    return pieces


def _pack(pieces: Sequence[str], limits: Limits) -> list[str]:
    chunks: list[str] = []
    current = ""
    for piece in pieces:
        if not current:
            current = piece
        elif len(current) + 2 + len(piece) <= limits.chunk_target_chars:
            current += "\n\n" + piece
        else:
            chunks.append(current)
            current = piece
    if current:
        chunks.append(current)
    if (
        len(chunks) >= 2
        and len(chunks[-1]) < limits.min_tail_chars
        and len(chunks[-2]) + 2 + len(chunks[-1]) <= limits.chunk_cap_chars
    ):
        chunks[-2:] = [chunks[-2] + "\n\n" + chunks[-1]]
    return chunks


def chunk_sections(sections: Iterable[Section], limits: Limits | None = None) -> list[Chunk]:
    """Cut each section into chunks. A chunk never spans two sections or two pages."""
    limits = limits or Limits()
    chunks: list[Chunk] = []
    for section in sections:
        for text in _pack(_pieces(section.text, limits), limits):
            chunks.append(Chunk(section.heading_path, text, section.page))
    return chunks
