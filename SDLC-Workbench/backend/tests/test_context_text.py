"""Query building and chunking: the two pure pieces under the context store."""
from __future__ import annotations

import random
import re
import sqlite3

import pytest

from app.context.chunking import (
    Section,
    build_sections,
    chunk_sections,
    markdown_blocks,
    normalise,
    plain_sections,
    sections_from_markdown,
)
from app.context.query import MAX_TERMS, STOP_WORDS, build_fts_query, query_words
from app.context.types import Limits

LIMITS = Limits()


def squash(text: str) -> str:
    return re.sub(r"\s+", "", text)


def without_heading_markers(text: str) -> str:
    return re.sub(r"(?m)^ {0,3}#{1,6}[ \t]+", "", normalise(text))


# ---- the full-text engine is really there ------------------------------------------------------------

def test_this_python_has_fts5_with_the_porter_tokenizer():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE VIRTUAL TABLE t USING fts5(body, tokenize='porter unicode61 remove_diacritics 2')")
    conn.execute("INSERT INTO t(body) VALUES ('the bookings were cancelled at the café')")
    for word in ("booking", "cancel", "cafe", "BOOKINGS"):
        assert conn.execute("SELECT 1 FROM t WHERE t MATCH ?", (f'"{word}"',)).fetchone(), word


# ---- query building -------------------------------------------------------------------------------------

def test_a_question_becomes_its_meaningful_words_in_order_without_repeats():
    assert query_words("How late can I cancel a booking? Cancel it NOW!") == ["late", "cancel", "booking", "now"]


def test_stop_words_and_single_letters_are_dropped_from_the_query_only():
    assert query_words("what is the of and a I") == []
    assert query_words("room x 7") == ["room", "7"]  # a digit is a real term, a lone letter is not
    assert "the" in STOP_WORDS


def test_the_query_is_quoted_words_joined_with_or():
    assert build_fts_query("cancel booking") == '"cancel" OR "booking"'


@pytest.mark.parametrize("question", [None, "", "   ", "the and of", "?!.,;:", "---", "***", "​‌"])
def test_a_question_with_nothing_searchable_gives_no_query(question):
    assert build_fts_query(question) is None


HOSTILE = [
    '"unclosed quote', 'cancel* AND NOT booking', 'NEAR(a b)', 'NEAR/3 x y', 'a:b -c', "it's (a) test", "((()))",
    "'; DROP TABLE context_chunks; --", 'text MATCH "x"', "col:value", "-leading", "OR OR OR", "NOT", '""', "\\",
    "日本語 café naïve", "x" * 5000, "word " * 5000, "a" * 70 + " " + "b" * 70, "\x00null\x00byte", "emoji \U0001f600 test",
]


@pytest.mark.parametrize("question", HOSTILE)
def test_hostile_input_never_raises_in_the_real_engine(question):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE VIRTUAL TABLE t USING fts5(body, tokenize='porter unicode61 remove_diacritics 2')")
    conn.execute("INSERT INTO t(body) VALUES ('a booking can be cancelled up to 24 hours before')")
    query = build_fts_query(question)
    if query is not None:
        conn.execute("SELECT 1 FROM t WHERE t MATCH ?", (query,)).fetchall()  # must not raise


def test_operators_in_a_question_are_just_words():
    assert query_words("NEAR(a b) cancel* AND NOT booking") == ["near", "cancel", "booking"]
    assert '"' not in build_fts_query('say "hello" now').replace('"hello"', "").replace('"say"', "").replace('"now"', "")


def test_the_number_and_length_of_terms_are_bounded():
    assert len(query_words(" ".join(f"term{n}" for n in range(500)))) == MAX_TERMS
    assert all(len(w) <= 64 for w in query_words("x" * 5000))


def test_more_matching_words_rank_higher_under_or():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE VIRTUAL TABLE t USING fts5(body, tokenize='porter unicode61 remove_diacritics 2')")
    docs = ["cancel only", "cancel booking policy here", "unrelated filler text number %d" % 1] + [f"filler {i} words" for i in range(10)]
    conn.executemany("INSERT INTO t(body) VALUES (?)", [(d,) for d in docs])
    ranked = [r[0] for r in conn.execute(
        "SELECT body FROM t WHERE t MATCH ? ORDER BY bm25(t)", (build_fts_query("cancel booking policy"),))]
    assert ranked[0] == "cancel booking policy here"


# ---- normalise ---------------------------------------------------------------------------------------------

def test_normalise_unifies_line_endings_and_blank_runs():
    assert normalise("a\r\nb\rc\n\n\n\n\nd") == "a\nb\nc\n\nd"


def test_normalise_removes_invisible_and_control_characters_but_keeps_meaning():
    assert normalise("co​op­era﻿tion") == "cooperation"
    assert normalise("a\x00b\x07c") == "abc"
    assert normalise("a b\tc") == "a b c"
    assert normalise("line one line two") == "line one\nline two"
    assert normalise("Café — naïve 日本語 \U0001f600") == "Café — naïve 日本語 \U0001f600"


def test_normalise_strips_trailing_spaces_and_edges():
    assert normalise("  a  \n  b   \n\n") == "a\n  b"


# ---- sections and headings --------------------------------------------------------------------------------------

DOC = """\
# Booking rules

Staff may book a room for up to four hours.

## Cancellation

Cancel free up to 24 hours before.

### Late cancellation

After that the room is charged.

# Admin

Admins manage rooms.
"""


def test_nested_headings_build_a_path():
    paths = [s.heading_path for s in sections_from_markdown(DOC)]
    assert paths == [
        "Booking rules", "Booking rules > Cancellation",
        "Booking rules > Cancellation > Late cancellation", "Admin",
    ]


def test_a_heading_with_no_body_is_carried_into_the_next_section_not_lost():
    sections = sections_from_markdown("# Parent\n\n## Child\n\nBody text here.")
    assert len(sections) == 1
    assert sections[0].heading_path == "Parent > Child"
    assert "Parent" in sections[0].text and "Child" in sections[0].text and "Body text here." in sections[0].text


def test_a_heading_inside_a_code_fence_is_not_a_heading():
    text = "# Real\n\nIntro.\n\n```\n# not a heading\nprint(1)\n```\n\nAfter."
    sections = sections_from_markdown(text)
    assert [s.heading_path for s in sections] == ["Real"]
    assert "# not a heading" in sections[0].text


def test_closing_hashes_and_deep_levels_and_indented_headings():
    assert [s.heading_path for s in sections_from_markdown("## Title ##\n\nbody")] == ["Title"]
    assert [s.heading_path for s in sections_from_markdown("###### Deep\n\nbody")] == ["Deep"]
    assert sections_from_markdown("####### Seven hashes is not a heading\n\nbody")[0].heading_path == ""
    assert sections_from_markdown("#Nospace\n\nbody")[0].heading_path == ""


def test_a_level_can_be_skipped_and_the_path_still_makes_sense():
    assert [s.heading_path for s in sections_from_markdown("# A\n\nx\n\n### C\n\ny")] == ["A", "A > C"]


def test_text_before_the_first_heading_has_an_empty_path():
    sections = sections_from_markdown("Preamble line.\n\n# First\n\nBody.")
    assert [s.heading_path for s in sections] == ["", "First"]


def test_plain_text_is_one_section_and_empty_text_is_none():
    assert [s.text for s in plain_sections("hello\n\nworld")] == ["hello\n\nworld"]
    assert plain_sections("   \n\n  ") == [] and sections_from_markdown("") == []
    assert plain_sections("x", page=3)[0].page == 3


# ---- chunking -------------------------------------------------------------------------------------------------------

def test_short_paragraphs_in_one_section_are_packed_together_up_to_the_target():
    section = Section("S", "\n\n".join(f"Paragraph number {n} with some words." for n in range(6)))
    chunks = chunk_sections([section], LIMITS)
    assert len(chunks) == 1 and all(len(c.text) <= LIMITS.chunk_target_chars for c in chunks)


def test_packing_stops_at_the_target_and_starts_a_new_chunk():
    paragraph = "word " * 60  # 300 chars
    chunks = chunk_sections([Section("S", "\n\n".join([paragraph.strip()] * 8))], LIMITS)
    assert len(chunks) > 1 and all(len(c.text) <= LIMITS.chunk_target_chars for c in chunks)


def test_a_chunk_never_spans_two_sections_or_two_pages():
    chunks = chunk_sections([Section("A", "alpha text", 1), Section("B", "beta text", 2)], LIMITS)
    assert [(c.heading_path, c.page) for c in chunks] == [("A", 1), ("B", 2)]


def test_an_overlong_paragraph_is_split_at_sentences_within_the_cap():
    sentence = "This is a perfectly ordinary sentence about booking rooms. "
    chunks = chunk_sections([Section("", (sentence * 80).strip())], LIMITS)
    assert len(chunks) > 1
    assert all(len(c.text) <= LIMITS.chunk_cap_chars for c in chunks)
    assert all(c.text.endswith(".") for c in chunks)  # cut at sentence ends, not mid-word


def test_one_unbroken_run_is_hard_split_and_still_capped():
    for run in ("x" * 4000, ("longword" * 10 + " ") * 100, "日本語" * 2000):
        chunks = chunk_sections([Section("", run)], LIMITS)
        assert chunks and all(len(c.text) <= LIMITS.chunk_cap_chars for c in chunks)
        assert squash("".join(c.text for c in chunks)) == squash(run)


def test_a_tiny_last_chunk_is_merged_into_the_one_before():
    big = "word " * 170  # ~850 chars, fits a chunk by itself
    chunks = chunk_sections([Section("", big.strip() + "\n\n" + "tail.")], LIMITS)
    assert len(chunks) == 1 and chunks[0].text.endswith("tail.")


def test_a_tiny_last_chunk_is_not_merged_when_that_would_break_the_cap():
    near_cap = "w" * 1480  # 1480 + 2 + 49 = 1531, over the 1500 cap, so the tail must stay separate
    chunks = chunk_sections([Section("", near_cap + "\n\n" + "tail " * 10)], LIMITS)
    assert len(chunks) == 2 and all(len(c.text) <= LIMITS.chunk_cap_chars for c in chunks)
    # ...and 1400 + 2 + 49 = 1451 does fit, so there the tail IS merged (the boundary the test above relies on).
    merged = chunk_sections([Section("", "w" * 1400 + "\n\n" + "tail " * 10)], LIMITS)
    assert len(merged) == 1 and len(merged[0].text) <= LIMITS.chunk_cap_chars


def test_empty_and_whitespace_sections_make_no_chunks():
    assert chunk_sections([], LIMITS) == []
    assert chunk_sections([Section("S", "  \n\n  ")], LIMITS) == []


def test_chunking_is_deterministic():
    sections = sections_from_markdown(DOC * 30)
    assert chunk_sections(sections, LIMITS) == chunk_sections(sections, LIMITS)


def test_the_limits_can_be_tightened():
    tight = Limits(chunk_target_chars=200, chunk_cap_chars=300, min_tail_chars=20)
    chunks = chunk_sections([Section("", "\n\n".join("sentence number %d here." % n for n in range(40)))], tight)
    assert len(chunks) > 3 and all(len(c.text) <= 300 for c in chunks)


def test_no_text_is_lost_or_duplicated_across_awkward_random_documents():
    random.seed(11)
    words = "alpha beta gamma delta booking room policy cancel hours rule".split()

    def para(n: int) -> str:
        return " ".join(random.choice(words) for _ in range(n)) + "."

    for _ in range(300):
        parts = []
        for _ in range(random.randint(1, 8)):
            roll = random.random()
            if roll < 0.2:
                parts.append("#" * random.randint(1, 4) + " " + para(random.randint(1, 4)))
            elif roll < 0.3:
                parts.append(para(random.randint(200, 600)))
            elif roll < 0.35:
                parts.append("x" * random.randint(1600, 4000))
            else:
                parts.append(para(random.randint(3, 60)))
        text = "\n\n".join(parts)
        chunks = chunk_sections(sections_from_markdown(text), LIMITS)
        assert squash("".join(c.text for c in chunks)) == squash(without_heading_markers(text))
        assert all(len(c.text) <= LIMITS.chunk_cap_chars for c in chunks)
        assert all(c.text.strip() for c in chunks)


def test_line_ending_styles_give_the_same_chunks():
    unix = chunk_sections(sections_from_markdown(DOC), LIMITS)
    windows = chunk_sections(sections_from_markdown(DOC.replace("\n", "\r\n")), LIMITS)
    old_mac = chunk_sections(sections_from_markdown(DOC.replace("\n", "\r")), LIMITS)
    assert unix == windows == old_mac


def test_build_sections_keeps_the_page_number():
    assert build_sections([(None, "text")], page=7)[0].page == 7


def test_markdown_blocks_mark_headings_and_plain_lines():
    assert markdown_blocks("# H\nline") == [(1, "H"), (None, "line")]
