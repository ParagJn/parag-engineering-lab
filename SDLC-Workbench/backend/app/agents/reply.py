"""Reading a model's reply, and checking it before anything is saved.

The reply is Markdown inside <artefact> tags. Parsing is forgiving about the usual mess (a code fence
around everything, chatter before or after) and strict about what matters: exactly one block, closed,
with content. Validation then checks the sections and, above all, the citations: every source ID in the
text must be one that was actually shown to the model in this prompt.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Collection, Iterable

from .skills import normalise_heading

MAX_BODY_CHARS = 60_000
MAX_PROBLEMS = 8
TRUNCATED_REASONS = frozenset({"length", "max_tokens"})
CUT_OFF_BEFORE_CLOSING = (
    "the reply was cut off by the output limit before the artefact was finished; write a shorter artefact (fewer or smaller parts) "
    "that still has every required section, and end it with </artefact>"
)

_OPEN = re.compile(r"^\s*<artefact>\s*$", re.IGNORECASE)
_CLOSE = re.compile(r"^\s*</artefact>\s*$", re.IGNORECASE)
_FENCE = re.compile(r"^\s{0,3}(```|~~~)")
_HEADING = re.compile(r"^\s{0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
_BRACKET = re.compile(r"\[([^\[\]\n]{1,300})\]")
# The shapes a citation can take:
#   DOC-003#4         a chunk of a document
#   MEM-017           a feedback note
#   REQ-PER-001       a whole upstream artefact (these are shown in full, so the artefact is the unit)
#   REQ-F-012@v2#3    a chunk of an approved artefact
# A bare DOC-003 (no chunk) is deliberately NOT accepted: it points at a whole document, which is never
# shown as one piece, and accepting it would let a model cite something it was not given.
_SOURCE_ID = re.compile(
    r"(?:DOC-\d{3,}#[1-9]\d*"
    r"|MEM-\d{3,}"
    r"|(?!DOC-)[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3,}(?:@v[1-9]\d*#[1-9]\d*)?)"
)


class ReplyFormatError(ValueError):
    """The reply has no usable <artefact> block. The message tells the model how to fix it."""


def parse_reply(text: str) -> str:
    """The Markdown between the <artefact> tags.

    Tags must sit on their own lines and are matched case-insensitively. A tag that appears inside a code
    fence within the body is part of the body, not a tag. Anything outside the block is ignored.
    """
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    body: list[str] = []
    state = "before"  # before -> inside -> after
    fence: str | None = None
    for line in lines:
        if state == "before":
            if _OPEN.match(line):
                state = "inside"
            continue
        if state == "inside":
            fence_match = _FENCE.match(line)
            if fence_match:
                marker = fence_match.group(1)
                fence = marker if fence is None else (None if marker == fence else fence)
                body.append(line)
                continue
            if fence is None and _CLOSE.match(line):
                state = "after"
                continue
            if fence is None and _OPEN.match(line):
                raise ReplyFormatError("a second <artefact> tag was opened before the first was closed; write exactly one block")
            body.append(line)
            continue
        if _OPEN.match(line):  # state == "after"
            raise ReplyFormatError("the reply contains more than one <artefact> block; write exactly one")
    if state == "before":
        raise ReplyFormatError("no <artefact> block was found; put the whole artefact between <artefact> and </artefact>, each tag on its own line")
    if state == "inside":
        raise ReplyFormatError("the <artefact> block is never closed; end it with </artefact> on its own line")
    result = "\n".join(body).strip()
    if not result:
        raise ReplyFormatError("the <artefact> block is empty")
    return result


# ---- sections ------------------------------------------------------------------------------------

@dataclass(frozen=True)
class _Heading:
    level: int
    name: str
    line: int


def _headings(body: str) -> tuple[list[str], list[_Heading]]:
    lines = body.split("\n")
    found: list[_Heading] = []
    fence: str | None = None
    for number, line in enumerate(lines):
        fence_match = _FENCE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            fence = marker if fence is None else (None if marker == fence else fence)
            continue
        if fence is None:
            match = _HEADING.match(line)
            if match:
                found.append(_Heading(len(match.group(1)), match.group(2).strip(), number))
    return lines, found


def section_text(lines: list[str], headings: list[_Heading], index: int) -> str:
    """Everything under a heading, sub-sections included, up to the next heading of the same or higher level."""
    start = headings[index].line + 1
    end = len(lines)
    for later in headings[index + 1:]:
        if later.level <= headings[index].level:
            end = later.line
            break
    return "\n".join(lines[start:end]).strip()


def section_bodies(body: str, name: str) -> list[str]:
    """The text under every heading called `name` (case and punctuation ignored), sub-sections included.

    Empty when there is no such heading. Two headings with the same name give two entries.
    """
    lines, headings = _headings(body)
    wanted = normalise_heading(name)
    return [section_text(lines, headings, i) for i, h in enumerate(headings) if normalise_heading(h.name) == wanted]


def unfenced_lines(text: str) -> list[str]:
    """The lines of `text` that are not inside a code fence. The fence lines themselves are dropped."""
    out: list[str] = []
    fence: str | None = None
    for line in text.split("\n"):
        fence_match = _FENCE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            fence = marker if fence is None else (None if marker == fence else fence)
            continue
        if fence is None:
            out.append(line)
    return out


def section_names(body: str) -> list[str]:
    """Every heading in the body (outside code fences), in order."""
    return [h.name for h in _headings(body)[1]]


def missing_sections(body: str, required: Iterable[str]) -> list[str]:
    """Required sections that are absent or have nothing under them. Matching ignores case and punctuation."""
    lines, headings = _headings(body)
    present: dict[str, bool] = {}
    for index, heading in enumerate(headings):
        key = normalise_heading(heading.name)
        present[key] = present.get(key, False) or bool(section_text(lines, headings, index))
    return [name for name in required if not present.get(normalise_heading(name), False)]


# ---- citations --------------------------------------------------------------------------------------

def cited_ids(body: str) -> list[str]:
    """Source IDs cited in square brackets, in order of first use, without repeats.

    `[DOC-001#2, DOC-001#3]` cites both. Brackets that are not ID-shaped ("[1]", "[note]") are not
    citations and are ignored. Text inside code fences is not scanned: code may legitimately contain brackets.
    """
    found: list[str] = []
    fence: str | None = None
    for line in body.split("\n"):
        fence_match = _FENCE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            fence = marker if fence is None else (None if marker == fence else fence)
            continue
        if fence is not None:
            continue
        for bracket in _BRACKET.finditer(line):
            for part in re.split(r"[,;]", bracket.group(1)):
                part = part.strip()
                if _SOURCE_ID.fullmatch(part) and part not in found:
                    found.append(part)
    return found


def unknown_citations(body: str, allowed: Collection[str]) -> list[str]:
    return [c for c in cited_ids(body) if c not in allowed]


# ---- the whole check ----------------------------------------------------------------------------------

def validate(
    body: str, required_sections: Iterable[str], allowed_citations: Collection[str], finish_reason: str | None, max_chars: int = MAX_BODY_CHARS,
) -> list[str]:
    """Every problem with a reply, as plain sentences that can be sent back to the model. [] means valid."""
    problems: list[str] = []
    if finish_reason in TRUNCATED_REASONS:
        problems.append("the reply was cut off by the output limit; write a shorter artefact that still has every required section")
    if len(body) > max_chars:
        problems.append(f"the artefact is {len(body)} characters long; the limit is {max_chars}")
    for name in missing_sections(body, required_sections):
        problems.append(f"the required section '{name}' is missing or empty; add a heading named '{name}' with text under it")
    invented = unknown_citations(body, allowed_citations)
    if invented:
        listed = ", ".join(f"[{c}]" for c in invented[:5])
        problems.append(
            f"you cited {listed}, which {'was' if len(invented) == 1 else 'were'} not provided to you; "
            "cite only the IDs listed under 'Sources you may cite', or cite nothing"
        )
    return problems[:MAX_PROBLEMS]
