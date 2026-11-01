"""Turning a person's question into a search the full-text engine cannot choke on.

SQLite's full-text search has its own query language (quotes, NEAR, AND/OR/NOT, *, -, :, parentheses).
A question typed by a person, or an artefact's own sentence, must never be handed to it raw: an unmatched
quote would crash the search and a stray AND or NOT would change its meaning. So the question is reduced
to plain words, each word is quoted, and the words are joined with OR. More matching words rank higher.
"""
from __future__ import annotations

import re

_WORD = re.compile(r"[^\W_]+", re.UNICODE)
MAX_TERMS = 32
MAX_WORD_CHARS = 64

# Dropped from the QUERY only. The index keeps every word, so nothing becomes unfindable.
STOP_WORDS = frozenset(
    """
    a an and any are as at be been being but by can could did do does doing for from had has have how i if
    in into is it its may might me my no not of on or our shall should so than that the their them then
    there these they this those to us was we were what when where which who whom why will with would you
    your about also just
    """.split()
)


def query_words(question: str) -> list[str]:
    """The distinct, lower-cased, meaningful words of a question, in order."""
    seen: set[str] = set()
    words: list[str] = []
    for raw in _WORD.findall(question or ""):
        word = raw.lower()[:MAX_WORD_CHARS]
        if word in STOP_WORDS or (len(word) == 1 and word.isalpha()) or word in seen:
            continue
        seen.add(word)
        words.append(word)
        if len(words) >= MAX_TERMS:
            break
    return words


def build_fts_query(question: str) -> str | None:
    """A safe full-text query, or None when the question has no searchable words."""
    words = query_words(question)
    if not words:
        return None
    return " OR ".join(f'"{word}"' for word in words)
