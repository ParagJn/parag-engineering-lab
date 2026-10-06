"""Search router: find chats by title and messages by content."""

import re

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..db import get_database

router = APIRouter(prefix="/search", tags=["search"])

# Control characters can't appear in typed text, so they safely mark matches in snippets
_MATCH_START = "\x02"
_MATCH_END = "\x03"
_SNIPPET_PARTS = re.compile(f"{_MATCH_START}(.*?){_MATCH_END}", re.S)
_HTML_TAG = re.compile(r"</?[a-zA-Z][^>]*>")
_MARKDOWN_SYMBOLS = re.compile(r"#{1,6}\s|\*{1,3}|`{1,3}|^>\s?|\[|\]", re.M)


class SnippetPart(BaseModel):
    """A piece of a snippet; match=True for the words that matched."""
    text: str
    match: bool


class MessageHit(BaseModel):
    """A message that matched."""
    message_id: str
    session_id: str
    session_title: str
    project_id: str | None
    role: str
    created_at: str
    snippet: list[SnippetPart]


class SessionHit(BaseModel):
    """A chat whose title matched."""
    session_id: str
    title: str
    project_id: str | None
    updated_at: str


class SearchResponse(BaseModel):
    """Search results."""
    query: str
    sessions: list[SessionHit]
    messages: list[MessageHit]


def _snippet_parts(snippet: str) -> list[SnippetPart]:
    """Split a highlighted snippet into plain-text parts (never HTML)."""
    parts: list[SnippetPart] = []
    position = 0
    for found in _SNIPPET_PARTS.finditer(snippet):
        if found.start() > position:
            parts.append(SnippetPart(text=snippet[position:found.start()], match=False))
        parts.append(SnippetPart(text=found.group(1), match=True))
        position = found.end()
    if position < len(snippet):
        parts.append(SnippetPart(text=snippet[position:], match=False))
    # Snippets are shown as plain text: drop HTML tags and Markdown symbols, and
    # collapse whitespace so multi-line messages read as one line
    for part in parts:
        text = part.text.replace(_MATCH_START, "").replace(_MATCH_END, "")
        text = _HTML_TAG.sub("", text)
        text = _MARKDOWN_SYMBOLS.sub("", text)
        part.text = re.sub(r"\s+", " ", text)
    return [part for part in parts if part.text]


@router.get("", response_model=SearchResponse)
async def search(
    q: str = Query("", max_length=200),
    project_id: str | None = None,
    limit: int = Query(30, ge=1, le=100),
):
    """Search chat titles and message text. Every word must match; the last one may be partial."""
    query = q.strip()
    if not query:
        return SearchResponse(query=q, sessions=[], messages=[])

    db = get_database()
    session_rows = db.search_session_titles(query, project_id=project_id, limit=10)
    message_rows = db.search_messages(
        query, project_id=project_id, limit=limit, highlight=(_MATCH_START, _MATCH_END)
    )

    return SearchResponse(
        query=q,
        sessions=[
            SessionHit(
                session_id=row["session_id"],
                title=row["title"],
                project_id=row["project_id"],
                updated_at=str(row["updated_at"]),
            )
            for row in session_rows
        ],
        messages=[
            MessageHit(
                message_id=row["message_id"],
                session_id=row["session_id"],
                session_title=row["session_title"],
                project_id=row["project_id"],
                role=row["role"],
                created_at=str(row["created_at"]),
                snippet=_snippet_parts(row["snippet"] or ""),
            )
            for row in message_rows
        ],
    )
