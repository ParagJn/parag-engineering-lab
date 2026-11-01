"""Reading text out of uploaded files, and refusing the ones that cannot be read."""
from __future__ import annotations

import pytest

from app.context.extract import NO_TEXT_PDF, clean_filename, extract, kind_from_name
from app.context.types import DocumentRefused, Limits

from ._files import blank_pdf, encrypt_pdf, make_docx, make_pdf, zip_bomb_docx


def text_of(result) -> str:
    return "\n".join(s.text for s in result.sections)


# ---- plain text and markdown ------------------------------------------------------------------------

def test_utf8_text():
    result = extract("notes.txt", "Café — naïve 日本語\n\nSecond paragraph.".encode("utf-8"))
    assert result.kind == "txt" and "Café — naïve 日本語" in text_of(result) and result.chars > 0


def test_utf8_with_a_byte_order_mark_has_no_stray_character():
    result = extract("notes.txt", b"\xef\xbb\xbfHello world")
    assert text_of(result) == "Hello world"


def test_utf16_with_a_byte_order_mark_is_read():
    result = extract("notes.txt", "Hello wörld".encode("utf-16"))
    assert text_of(result) == "Hello wörld"


def test_latin1_style_bytes_fall_back_instead_of_failing():
    result = extract("old.txt", b"caf\xe9 au lait")  # not valid UTF-8
    assert "caf" in text_of(result) and "au lait" in text_of(result)


def test_markdown_headings_become_sections():
    result = extract("rules.md", b"# Booking\n\nUp to four hours.\n\n## Cancellation\n\n24 hours notice.")
    assert result.kind == "md" and [s.heading_path for s in result.sections] == ["Booking", "Booking > Cancellation"]


def test_extension_aliases_and_case():
    assert kind_from_name("NOTES.TXT") == "txt" and kind_from_name("a.markdown") == "md" and kind_from_name("a.text") == "txt"
    assert kind_from_name("C:\\Users\\x\\Report.DOCX") == "docx" and kind_from_name("/tmp/a/b.pdf") == "pdf"


@pytest.mark.parametrize("name", ["virus.exe", "sheet.xlsx", "deck.pptx", "page.html", "noextension", "archive.tar.gz", ".txt.exe", "a.pdf.exe"])
def test_unsupported_types_are_refused_with_the_supported_list(name):
    with pytest.raises(DocumentRefused, match=r"not a supported file type.*\.txt, \.md, \.docx, \.pdf"):
        extract(name, b"content")


def test_binary_data_named_as_text_is_refused():
    with pytest.raises(DocumentRefused, match="not plain text"):
        extract("data.txt", b"\x00\x01\x02binary\x00")


def test_a_zero_byte_file_says_it_is_empty():
    """Not just 'refused': the specific message, which is more useful than 'no readable text'."""
    with pytest.raises(DocumentRefused) as exc:
        extract("blank.txt", b"")
    assert str(exc.value) == "this file is empty"


@pytest.mark.parametrize("data", [b"   \n\n\t ", b"\xef\xbb\xbf"])
def test_blank_files_are_refused_as_having_no_readable_text(data):
    with pytest.raises(DocumentRefused) as exc:
        extract("blank.txt", data)
    assert str(exc.value) == "this file contains no readable text"


def test_an_oversize_file_is_refused_with_both_sizes():
    with pytest.raises(DocumentRefused, match=r"2\.0 MB; the limit is 1 MB"):
        extract("big.txt", b"a" * (2 * 1024 * 1024), Limits(max_file_bytes=1024 * 1024))


# ---- Word ---------------------------------------------------------------------------------------------------

def test_docx_headings_paragraphs_and_tables():
    data = make_docx(
        [("h1", "Room policy"), ("p", "Rooms are booked for up to four hours."), ("h2", "Cancellation"),
         ("p", "Cancel free up to 24 hours before.")],
        table=[["Room", "Seats"], ["Atlas", "8"]],
    )
    result = extract("policy.docx", data)
    assert result.kind == "docx"
    assert [s.heading_path for s in result.sections] == ["Room policy", "Room policy > Cancellation"]
    body = text_of(result)
    assert "four hours" in body and "Cancel free" in body and "Room | Seats" in body and "Atlas | 8" in body


def test_docx_merged_cells_do_not_repeat_their_text():
    from docx import Document
    import io

    document = Document()
    table = document.add_table(rows=1, cols=3)
    table.cell(0, 0).merge(table.cell(0, 1)).text = "Merged"
    table.cell(0, 2).text = "Other"
    buffer = io.BytesIO()
    document.save(buffer)
    assert text_of(extract("t.docx", buffer.getvalue())).count("Merged") == 1


def test_docx_with_no_text_is_refused():
    with pytest.raises(DocumentRefused, match="no readable text"):
        extract("empty.docx", make_docx([]))


def test_a_file_named_docx_that_is_not_a_zip_is_refused():
    with pytest.raises(DocumentRefused, match="not a Word document"):
        extract("fake.docx", b"just some text")


def test_a_corrupt_docx_is_refused_without_a_traceback_or_content():
    data = make_docx([("p", "SECRET-CONTENT")])
    for broken in (data[: len(data) // 2], data[:100] + b"\x00" * 50 + data[150:], b"PK\x03\x04" + b"garbage" * 10):
        with pytest.raises(DocumentRefused) as exc:
            extract("broken.docx", broken)
        assert "SECRET-CONTENT" not in str(exc.value) and "Traceback" not in str(exc.value)


def test_a_decompression_bomb_is_refused_before_it_is_opened():
    bomb = zip_bomb_docx(uncompressed_mb=40)
    assert len(bomb) < 100_000  # tiny on disk
    with pytest.raises(DocumentRefused, match="expands to more than"):
        extract("bomb.docx", bomb, Limits(max_file_bytes=2 * 1024 * 1024, max_uncompressed_factor=6))


# ---- PDF ---------------------------------------------------------------------------------------------------------

def test_pdf_text_keeps_page_numbers():
    result = extract("policy.pdf", make_pdf(["Page one. Cancellation is free up to 24 hours.", "Page two. Equipment is reported to facilities."]))
    assert result.kind == "pdf" and [s.page for s in result.sections] == [1, 2]
    assert "Cancellation" in result.sections[0].text and "Equipment" in result.sections[1].text


def test_a_blank_page_is_skipped_but_the_rest_are_kept():
    import io
    from pypdf import PdfReader, PdfWriter

    text_pdf = make_pdf(["Real text on page one."])
    writer = PdfWriter(clone_from=PdfReader(io.BytesIO(text_pdf)))
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    result = extract("mixed.pdf", buffer.getvalue())
    assert [s.page for s in result.sections] == [1]


def test_a_scanned_pdf_is_refused_with_the_ocr_message():
    with pytest.raises(DocumentRefused) as exc:
        extract("scan.pdf", blank_pdf(3))
    assert str(exc.value) == NO_TEXT_PDF and "OCR" in str(exc.value)


def test_a_password_protected_pdf_is_refused():
    with pytest.raises(DocumentRefused, match="password-protected"):
        extract("locked.pdf", encrypt_pdf(make_pdf(["Secret page."]), "s3cret"))


def test_a_pdf_encrypted_with_an_empty_password_opens():
    assert "Open page" in text_of(extract("open.pdf", encrypt_pdf(make_pdf(["Open page."]), "")))


def test_too_many_pages_are_refused_with_the_count_and_limit():
    with pytest.raises(DocumentRefused, match=r"has 5 pages; the limit is 3"):
        extract("long.pdf", make_pdf([f"Page {n} has text." for n in range(5)]), Limits(max_pdf_pages=3))


def test_a_file_named_pdf_that_is_not_one_is_refused():
    with pytest.raises(DocumentRefused, match="not a PDF"):
        extract("fake.pdf", b"plain text pretending")


def test_a_truncated_or_corrupt_pdf_is_refused_cleanly():
    data = make_pdf(["Some real text here."])
    for broken in (data[: len(data) // 3], b"%PDF-1.4\n" + b"\x00garbage" * 20):
        with pytest.raises(DocumentRefused) as exc:
            extract("broken.pdf", broken)
        assert "Traceback" not in str(exc.value)


# ---- filenames in messages and audit rows ------------------------------------------------------------------------------

def test_clean_filename_drops_paths_control_characters_and_length():
    assert clean_filename("C:\\Users\\bob\\secret plan.docx") == "secret plan.docx"
    assert clean_filename("/etc/passwd") == "passwd"
    assert clean_filename("a\x00b\nc.txt") == "abc.txt"
    assert clean_filename("") == "unnamed" and clean_filename("   ") != ""
    assert len(clean_filename("x" * 500 + ".txt")) <= 120


def test_a_refusal_message_never_contains_the_file_content_or_a_full_path():
    with pytest.raises(DocumentRefused) as exc:
        extract("/home/bob/private/report.exe", b"SECRET-CONTENT")
    assert "SECRET-CONTENT" not in str(exc.value) and "/home/bob" not in str(exc.value) and "report.exe" in str(exc.value)
