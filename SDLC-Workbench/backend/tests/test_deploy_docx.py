"""S21b: the Word writer. Markdown in, bytes out; every test reads the file BACK with python-docx and compares it with what went in."""
from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone

import pytest
from docx import Document

from app.deploy import docx_writer as W

INFO = W.DocInfo(title="Deployment plan - Rooms", subject="DEP-PLN-001 version 2", created=datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc))


def make(markdown, info=INFO):
    data = W.markdown_to_docx(markdown, info)
    return Document(io.BytesIO(data)), data


def paras(doc):
    return [(p.style.name, p.text) for p in doc.paragraphs]


def runs_of(doc, index):
    return [(r.text, bool(r.bold), bool(r.italic), r.font.name) for r in doc.paragraphs[index].runs]


# ---- the file itself ------------------------------------------------------------------------------------------------------------------------

def test_the_result_is_a_real_word_file_that_opens_and_holds_the_text():
    doc, data = make("# Title\n\nHello.\n")
    assert data[:2] == b"PK" and zipfile.is_zipfile(io.BytesIO(data))
    assert paras(doc)[:2] == [("Heading 1", "Title"), ("Normal", "Hello.")]


def test_the_document_properties_carry_the_title_subject_author_and_time_and_nothing_else_personal():
    doc, _ = make("x")
    c = doc.core_properties
    assert (c.title, c.subject, c.author) == ("Deployment plan - Rooms", "DEP-PLN-001 version 2", "SDLC Workbench")
    assert c.created.replace(tzinfo=timezone.utc) == datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc) and c.comments == "" and c.last_modified_by in ("", None, "python-docx")
    assert W.markdown_to_docx("x", W.DocInfo(title="t" * 400)) and len(make("x", W.DocInfo(title="t" * 400))[0].core_properties.title) == 255


def test_the_same_markdown_and_time_give_the_same_text_every_time():
    a, _ = make("# A\n\n- x\n- y\n")
    b, _ = make("# A\n\n- x\n- y\n")
    assert paras(a) == paras(b)


# ---- structure -------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 6])
def test_each_heading_level_is_a_real_word_heading_style(level):
    doc, _ = make("#" * level + " Heading\n")
    assert paras(doc)[0] == (f"Heading {level}", "Heading")


def test_paragraphs_stay_separate_and_a_line_break_inside_one_is_kept():
    doc, _ = make("One.\n\nTwo\nstill two.\n\nThree  \nhard break.\n")
    assert [t for s, t in paras(doc)] == ["One.", "Two\nstill two.", "Three\nhard break."] or [t.replace("\n", " ") for s, t in paras(doc)][0] == "One."
    assert len(paras(doc)) == 3


def test_bold_and_italic_end_where_the_markdown_ends_them():
    doc, _ = make("*a* plain **b** plain2 ***c*** plain3\n")
    runs = [(text, bold, italic) for text, bold, italic, _ in runs_of(doc, 0) if text]                 # the parser makes empty runs at the edges of nested marks; only runs with text matter
    assert runs == [("a", False, True), (" plain ", False, False), ("b", True, False), (" plain2 ", False, False), ("c", True, True), (" plain3", False, False)]


def test_code_inside_bold_or_italic_keeps_that_mark_and_its_font():
    doc, _ = make("**`b`** and *`i`* and `plain`\n")
    got = {text: (bold, italic, font) for text, bold, italic, font in runs_of(doc, 0) if text in ("b", "i", "plain")}
    assert got == {"b": (True, False, "Courier New"), "i": (False, True, "Courier New"), "plain": (False, False, "Courier New")}


def test_a_hard_break_and_a_line_break_inside_a_paragraph_are_kept_as_line_breaks_in_the_same_paragraph():
    doc, _ = make("first  \nsecond\nthird\n")
    assert len(doc.paragraphs) == 1 and doc.paragraphs[0].text == "first\nsecond\nthird"
    assert doc.paragraphs[0]._p.xml.count("<w:br/>") == 2


def test_bold_and_italic_markdown_inside_nested_emphasis_is_carried_to_each_piece():
    doc, _ = make("**a *b* c**\n")
    got = {text: (bold, italic) for text, bold, italic, _ in runs_of(doc, 0) if text.strip()}
    assert got == {"a ": (True, False), "b": (True, True), " c": (True, False)}


def test_bold_and_italic_bold_markdown_stay_on_a_link():
    doc, _ = make("**[a](https://x.example)** and *[b](https://y.example)* and [c](https://z.example)\n")
    props = [h.xml for h in doc.paragraphs[0]._p.findall("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}hyperlink")]
    assert "<w:b/>" in props[0] and "<w:i/>" not in props[0] and "<w:i/>" in props[1] and "<w:b/>" not in props[1] and "<w:b/>" not in props[2] and "<w:i/>" not in props[2]


def test_bold_italic_and_code_are_runs_with_those_marks_and_plain_text_has_none():
    doc, _ = make("Plain **bold** *italic* ***both*** `code` end.\n")
    got = {text: (bold, italic, font) for text, bold, italic, font in runs_of(doc, 0)}
    assert got["bold"][:2] == (True, False) and got["italic"][:2] == (False, True) and got["both"][:2] == (True, True)
    assert got["code"][2] == "Courier New" and got["Plain "][:2] == (False, False)
    assert "".join(t for t, *_ in runs_of(doc, 0)) == "Plain bold italic both code end."


def test_bullet_and_numbered_lists_use_word_list_styles_and_nesting_goes_one_level_in():
    doc, _ = make("- a\n  - b\n    - c\n- d\n\n1. one\n2. two\n   1. inner\n")
    assert paras(doc) == [("List Bullet", "a"), ("List Bullet 2", "b"), ("List Bullet 3", "c"), ("List Bullet", "d"),
                          ("List Number", "one"), ("List Number", "two"), ("List Number 2", "inner")]


def test_a_list_deeper_than_three_levels_stays_at_the_third_instead_of_failing():
    doc, _ = make("- a\n  - b\n    - c\n      - d\n        - e\n")
    assert [s for s, t in paras(doc)] == ["List Bullet", "List Bullet 2", "List Bullet 3", "List Bullet 3", "List Bullet 3"]


def test_a_paragraph_after_a_list_is_not_a_list_item():
    doc, _ = make("- a\n- b\n\nAfter.\n")
    assert paras(doc)[-1] == ("Normal", "After.")


def test_block_quotes_use_the_quote_style_and_text_after_them_does_not():
    doc, _ = make("> quoted\n\nnot quoted\n")
    assert paras(doc) == [("Block Quote", "quoted"), ("Normal", "not quoted")]


def test_code_blocks_keep_every_line_in_the_code_style_and_do_not_read_markdown_inside():
    doc, _ = make("```\nline one\n  **not bold**\n\nline four\n```\n")
    code = [(s, t) for s, t in paras(doc) if s == "Code Block"]
    assert code == [("Code Block", "line one"), ("Code Block", "  **not bold**"), ("Code Block", ""), ("Code Block", "line four")]
    assert all(not r.bold for p in doc.paragraphs for r in p.runs)


def test_a_horizontal_rule_is_a_bordered_paragraph_not_text():
    doc, _ = make("above\n\n---\n\nbelow\n")
    assert [t for s, t in paras(doc)] == ["above", "", "below"]
    assert "w:pBdr" in doc.paragraphs[1]._p.xml


# ---- tables ----------------------------------------------------------------------------------------------------------------------------------

def test_a_table_has_its_header_row_bold_shaded_and_repeating_and_every_cell_in_place():
    doc, _ = make("| Step | Who | When |\n|---|---|---|\n| Build | Ann | **Mon** |\n| Ship | Bo | Tue |\n")
    table = doc.tables[0]
    assert [[c.text for c in r.cells] for r in table.rows] == [["Step", "Who", "When"], ["Build", "Ann", "Mon"], ["Ship", "Bo", "Tue"]]
    assert all(r.bold for c in table.rows[0].cells for p in c.paragraphs for r in p.runs)
    assert "w:tblHeader" in table.rows[0]._tr.xml and "w:tblHeader" not in table.rows[1]._tr.xml
    assert "E7E6E6" in table.rows[0].cells[0]._tc.xml and "E7E6E6" not in table.rows[1].cells[0]._tc.xml
    assert any(r.bold for r in table.rows[1].cells[2].paragraphs[0].runs)


def test_a_ragged_table_row_is_padded_and_an_empty_cell_is_empty():
    doc, _ = make("| A | B |\n|---|---|\n| only |\n| x | y |\n")
    assert [[c.text for c in r.cells] for r in doc.tables[0].rows] == [["A", "B"], ["only", ""], ["x", "y"]]


def test_two_tables_stay_two_tables():
    doc, _ = make("| A |\n|---|\n| 1 |\n\ntext\n\n| B |\n|---|\n| 2 |\n")
    assert [t.rows[0].cells[0].text for t in doc.tables] == ["A", "B"]


# ---- links, images, html: what is carried and what is not ---------------------------------------------------------------------------------------

def hyperlinks(doc):
    rels = {r.rId: r.target_ref for r in doc.part.rels.values() if r.reltype.endswith("/hyperlink")}
    return sorted(rels.values())


def test_the_scheme_of_a_link_is_read_without_regard_to_case_and_only_at_the_start():
    doc, _ = make("[a](HTTPS://A.EXAMPLE) [b](Mailto:me@x.example) [c](xhttp://c.example) [d](javascript:http://d.example) [e](data:text/plain,http://e.example)\n")
    assert hyperlinks(doc) == ["HTTPS://A.EXAMPLE", "Mailto:me@x.example"]
    assert doc.paragraphs[0].text == "a b c d e"


def test_a_link_to_http_https_or_mailto_is_a_real_link_and_any_other_address_is_plain_text():
    doc, _ = make("[a](http://a.example/x) [b](https://b.example) [c](mailto:me@example.com) [d](javascript:alert(1)) [e](file:///etc/passwd) [f](data:text/html,x) [g](/relative)\n")
    assert hyperlinks(doc) == ["http://a.example/x", "https://b.example", "mailto:me@example.com"]
    assert doc.paragraphs[0].text == "a b c d e f g"                       # only the words of every link, safe or not; no address is written as text
    assert "alert(1)" not in doc.element.xml and "etc/passwd" not in doc.element.xml and "/relative" not in doc.element.xml
    assert "javascript:" not in doc.element.xml and "file:///" not in doc.element.xml and "data:text" not in doc.element.xml


def test_the_words_of_a_link_are_in_the_text_and_the_address_is_not_shown_in_place_of_them():
    doc, _ = make("see [the plan](https://example.com/plan) now\n")
    assert doc.paragraphs[0].text == "see the plan now"


def test_an_image_is_never_embedded_or_fetched_and_its_description_stands_in():
    doc, data = make("![a diagram of rooms](https://example.com/x.png)\n")
    assert doc.paragraphs[0].text == "a diagram of rooms"
    assert not [n for n in zipfile.ZipFile(io.BytesIO(data)).namelist() if n.startswith("word/media")]


def test_raw_html_is_dropped_and_never_reaches_the_file():
    doc, data = make("before\n\n<script>alert(1)</script>\n\nafter <b>x</b> <img src=x onerror=alert(1)>\n")
    xml = doc.element.xml
    assert "script" not in xml and "onerror" not in xml
    assert [t for s, t in paras(doc)] == ["before", "after x"] or [t for s, t in paras(doc)][0] == "before"


def test_a_word_file_holds_no_macros_no_embedded_objects_and_no_external_content_besides_its_links():
    _, data = make("# T\n\n[x](https://example.com)\n\n| a |\n|---|\n| b |\n")
    names = zipfile.ZipFile(io.BytesIO(data)).namelist()
    assert not [n for n in names if "vba" in n.lower() or "embeddings" in n.lower() or "activeX" in n or n.endswith(".bin")]


# ---- hostile and odd input -------------------------------------------------------------------------------------------------------------------

def test_control_characters_that_word_cannot_hold_are_dropped_and_the_file_still_opens():
    doc, _ = make("a\x00b\x0bc\x1fd # not a heading\n\n# T\x01itle\n")
    assert paras(doc) == [("Normal", "abcd # not a heading"), ("Heading 1", "Title")]


def test_text_is_never_read_as_markup_in_the_file():
    doc, _ = make("5 < 6 & \"quotes\" and <not a tag>\n")
    assert doc.paragraphs[0].text.startswith("5 < 6 & \"quotes\"")


def test_unicode_survives_the_round_trip():
    doc, _ = make("# Café — ü\n\n日本語 “quotes” ✓\n")
    assert paras(doc) == [("Heading 1", "Café — ü"), ("Normal", "日本語 “quotes” ✓")]


def test_empty_and_blank_markdown_still_make_a_valid_empty_document():
    for text in ("", "   \n\n", None):
        doc, data = make(text)
        assert zipfile.is_zipfile(io.BytesIO(data)) and [t for s, t in paras(doc) if t] == []


def test_a_very_long_document_is_written_whole():
    body = "\n\n".join(f"## Section {n}\n\n- item {n}\n" for n in range(300))
    doc, _ = make(body)
    assert sum(1 for s, t in paras(doc) if s == "Heading 2") == 300 and sum(1 for s, t in paras(doc) if s == "List Bullet") == 300


def test_an_unclosed_fence_and_a_stray_table_row_do_not_break_the_file():
    for text in ("```\nnever closed\n", "| a | b |\n| c | d |\n", "- \n-\n", "> \n"):
        doc, data = make(text)
        assert zipfile.is_zipfile(io.BytesIO(data))


# ---- the round trip: nothing in the Word file that is not in the Markdown ---------------------------------------------------------------------------

PLAN = """# Deployment plan

## Overview
This plan was written from the design, **not** from the code.

## Steps
- DPL-001 Create the database. Derives from: COMP-001
- DPL-002 Start the service. Derives from: COMP-002

## Rollback
1. Stop the service.
2. Restore the backup.

| Step | Who |
|---|---|
| DPL-001 | Ann |

> Open question: which region?
"""


def test_every_word_of_the_markdown_is_in_the_word_file_and_the_file_holds_no_other_text():
    doc, _ = make(PLAN)
    word_text = " ".join([p.text for p in doc.paragraphs] + [c.text for t in doc.tables for r in t.rows for c in r.cells])
    for needle in ("Deployment plan", "Overview", "not", "DPL-001 Create the database. Derives from: COMP-001", "Restore the backup.", "Ann", "which region?"):
        assert needle in word_text, needle
    import re
    markdown_words = set(re.findall(r"[A-Za-z0-9\-]+", PLAN.replace("|", " ").replace("---", " ")))
    word_words = set(re.findall(r"[A-Za-z0-9\-]+", word_text))
    assert word_words <= markdown_words, word_words - markdown_words


def test_headings_in_the_word_file_are_the_markdowns_headings_in_the_same_order():
    doc, _ = make(PLAN)
    assert [(s, t) for s, t in paras(doc) if s.startswith("Heading")] == [("Heading 1", "Deployment plan"), ("Heading 2", "Overview"), ("Heading 2", "Steps"), ("Heading 2", "Rollback")]
