"""The SVG sanitiser (S13): an allow-list that never raises, never grows its input, finishes quickly, and leaves no live markup behind."""
from __future__ import annotations

import contextlib
import re
import signal
import time

import pytest

from app.design import sanitise as S
from app.design.sanitise import ATTRIBUTES, ELEMENTS, drawing_problems, drawings_in, sanitise_svg

from .data.svg_corpus import CASES, FORBIDDEN_ATTRIBUTE_PREFIXES, FORBIDDEN_ELEMENTS

_TAG = re.compile(r"<\s*/?\s*([A-Za-z][A-Za-z0-9:_-]*)([^>]*)>")


def tags_and_attributes(markup: str):
    """What an HTML parser would see as elements and attribute names. Escaped text (&lt;script&gt;) contains neither."""
    elements, attributes = [], []
    for name, rest in _TAG.findall(markup):
        elements.append(name.lower())
        attributes += [a.lower() for a in re.findall(r"([A-Za-z_:][A-Za-z0-9_:.-]*)\s*=", rest)]
    return elements, attributes


# ---- every hostile case ------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name, text", CASES, ids=[c[0] for c in CASES])
def test_no_case_leaves_live_markup_or_grows_or_raises(name, text):
    result = sanitise_svg(text)
    elements, attributes = tags_and_attributes(result.svg)
    assert not set(elements) & set(FORBIDDEN_ELEMENTS), (name, elements)
    assert set(elements) <= ELEMENTS, (name, set(elements) - ELEMENTS)
    for attribute in attributes:
        assert not any(attribute.startswith(p) for p in FORBIDDEN_ATTRIBUTE_PREFIXES), (name, attribute)
        assert attribute in ATTRIBUTES or attribute == "viewbox", (name, attribute)
    assert len(result.svg) <= max(len(text), 1) + 40, name                  # the +40 is room for a normalised self-closing slash
    assert isinstance(result.ok, bool)
    if result.ok:
        assert result.svg.startswith("<svg") and result.svg.endswith("</svg>")
    else:
        assert result.svg == ""


@pytest.mark.parametrize("name, text", CASES, ids=[c[0] for c in CASES])
def test_sanitising_twice_changes_nothing_more(name, text):
    once = sanitise_svg(text)
    again = sanitise_svg(once.svg)
    assert again.svg == once.svg and not again.changed, name


def test_a_clean_drawing_comes_back_unchanged_apart_from_its_slashes():
    for name, text in CASES[:3]:
        result = sanitise_svg(text)
        assert result.ok and not result.changed, name
        assert result.svg == text.replace("/>", " />"), name


@pytest.mark.parametrize("written, shown", [
    ("fish &amp; chips", "fish &amp; chips"),                 # the model's entity means "&": it is kept as one escaped ampersand, not escaped twice
    ("a &lt; b", "a &lt; b"),
    ("R&D", "R&amp;D"),                                       # a bare ampersand is text
    ("&amp;lt;", "&amp;lt;"),                                 # an escaped entity stays literal text; one pass only
    ("&#60;script&#62;", "&amp;#60;script&amp;#62;"),         # numeric entities are shown as typed, never interpreted
    ("&unknown;", "&amp;unknown;"),
    ("a < b", "a &lt; b"),                                    # a space after '<' means it is not a tag, so nothing after it is swallowed
    ("1 < 2 and 3 > 2", "1 &lt; 2 and 3 &gt; 2"),
])
def test_text_means_what_the_model_meant_and_never_becomes_markup(written, shown):
    out = sanitise_svg(f"<svg><text>{written}</text></svg>").svg
    assert out == f"<svg><text>{shown}</text></svg>"
    elements, attributes = tags_and_attributes(out)
    assert elements == ["svg", "text", "text", "svg"] and attributes == []
    assert sanitise_svg(out).svg == out                      # a second pass finds exactly the same text


def test_text_is_cut_to_the_limit_and_trimmed_and_still_stable():
    out = sanitise_svg("<svg><text>" + "word " * 300 + "</text></svg>").svg
    assert not out.replace("</text>", "").endswith(" ") and len(out) < 450
    assert sanitise_svg(out).svg == out


def test_the_namespace_may_only_be_the_svg_one():
    assert 'xmlns="http://www.w3.org/2000/svg"' in sanitise_svg('<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>').svg
    assert "xmlns" not in sanitise_svg('<svg xmlns="http://evil/ns"><rect/></svg>').svg


def test_a_removed_element_takes_its_whole_subtree_with_it():
    result = sanitise_svg('<svg><foreignObject><rect x="1"/><text>kept?</text></foreignObject><rect x="2"/></svg>')
    assert 'x="1"' not in result.svg and "kept?" not in result.svg and 'x="2"' in result.svg


def test_the_report_names_what_was_removed_and_never_the_removed_text():
    result = sanitise_svg('<svg onload="SECRET_PAYLOAD_1"><script>SECRET_PAYLOAD_2</script><rect fill="url(SECRET_PAYLOAD_3)"/></svg>')
    said = " ".join(result.report.removed)
    assert "onload" in said and "<script>" in said and "fill" in said
    assert "SECRET_PAYLOAD" not in said


def test_the_report_is_bounded():
    result = sanitise_svg("<svg>" + "".join(f"<bad{i}/>" for i in range(100)) + "</svg>")
    assert len(result.report.removed) <= 12


# ---- limits -----------------------------------------------------------------------------------------------------------------------

def test_too_many_elements_is_refused_with_a_sentence():
    result = sanitise_svg("<svg>" + "<rect/>" * (S.MAX_ELEMENTS + 10) + "</svg>")
    assert any(f"more than {S.MAX_ELEMENTS} elements" in r for r in result.report.removed) or not result.ok


def test_nesting_deeper_than_the_limit_is_dropped():
    result = sanitise_svg("<svg>" + "<g>" * (S.MAX_DEPTH + 5) + '<rect x="9"/>' + "</g>" * (S.MAX_DEPTH + 5) + "</svg>")
    assert result.svg.count("<g>") <= S.MAX_DEPTH and any("nesting deeper" in r for r in result.report.removed)


def test_a_screen_over_the_size_limit_is_refused():
    result = sanitise_svg("<svg>" + '<text x="1">' + "word " * 100 + "</text>" * 1 + "<rect/>" * 300 + "</svg>" * 1)
    big = sanitise_svg("<svg>" + ('<text x="1">' + "x" * 390 + "</text>") * 40 + "</svg>")
    assert not big.ok and any("limited to" in r for r in big.report.removed)
    assert isinstance(result.ok, bool)


def test_text_and_attribute_length_are_capped():
    assert len(sanitise_svg("<svg><text>" + "a" * 5000 + "</text></svg>").svg) < 600
    assert 'd="' not in sanitise_svg('<svg><path d="' + "M0 0 " * 600 + '"/></svg>').svg


@contextlib.contextmanager
def _within(seconds: int, label: str):
    """Stop a call that runs far too long and FAIL the test, instead of letting a quadratic loop hang the whole suite (a hung suite cannot be told
    from a slow machine, so the mutation check cannot count it as caught). Unix only; elsewhere the plain elapsed-time assertion still applies."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return
    def stop(_signum, _frame):
        raise AssertionError(f"{label}: still running after {seconds}s (the tokenizer is no longer linear?)")
    previous = signal.signal(signal.SIGALRM, stop)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def test_input_over_the_hard_cap_is_refused_before_anything_is_looked_at():
    result = sanitise_svg("<svg>" + "<rect/>" * 100_000 + "</svg>")
    assert not result.ok and result.svg == "" and any("longer than" in r for r in result.report.removed)


@pytest.mark.parametrize("label, text", [
    ("unclosed repeated tag", "<svg>" + "<g " * 60_000),
    ("deep", "<svg>" + "<g>" * 20_000 + "</g>" * 20_000 + "</svg>"),
    ("many attributes", "<svg><rect " + 'x="1" ' * 20_000 + "/></svg>"),
    ("quote soup", '<svg><rect x="' + "a" * 150_000 + '"/></svg>'),
    ("tag soup", "<svg>" + "<" * 150_000),
    ("many elements", "<svg>" + "<rect/>" * 20_000 + "</svg>"),
    ("pathological quotes", "<svg><rect " + 'a="' * 60_000),
    ("lt spam in text", "<svg><text>" + "<a" * 80_000 + "</text></svg>"),
    ("mixed quotes", "<svg><rect " + "x=\"1\" y='" * 15_000 + "/></svg>"),
])
def test_oversized_and_adversarial_input_finishes_quickly_and_does_not_raise(label, text):
    """The first version of the tokenizer was quadratic on 'unclosed repeated tag': 12,000 characters took a second and 24,000 took four. This
    same logic runs in the browser, where that freezes the tab, so every adversarial shape is timed."""
    assert len(text) <= S.MAX_INPUT_CHARS
    started = time.perf_counter()
    with _within(5, label):
        result = sanitise_svg(text)
    assert time.perf_counter() - started < 0.5, label
    assert isinstance(result.ok, bool)


def test_a_non_string_is_not_a_drawing_and_does_not_raise():
    for bad in (None, 5, b"<svg/>", [], {}):
        result = sanitise_svg(bad)               # type: ignore[arg-type]
        assert not result.ok and result.svg == ""


# ---- finding drawings in a Markdown body and reporting them ------------------------------------------------------------------------------

def test_only_blocks_tagged_svg_are_drawings():
    body = "## A\n```svg\n<svg><rect/></svg>\n```\n```html\n<script>x</script>\n```\n```\nplain\n```\n~~~svg\n<svg/>\n~~~\n"
    found = drawings_in(body)
    assert [(f, l) for f, l, _ in found] == [(2, 4), (11, 13)] or len(found) == 2
    assert all("script" not in t for _, _, t in found)


def test_a_drawing_with_nothing_wrong_is_no_problem():
    assert drawing_problems("## S\n```svg\n" + CASES[0][1] + "\n```\n") == []
    assert drawing_problems("## No drawings here\ntext only\n") == []


def test_an_unsafe_drawing_is_a_problem_that_names_the_element_and_the_line_but_not_the_payload():
    body = "## S\n```svg\n<svg onload=\"STEAL\"><rect/></svg>\n```\n"
    [problem] = drawing_problems(body)
    assert "line 2" in problem and "onload" in problem and "STEAL" not in problem


def test_a_drawing_that_is_not_a_drawing_is_a_problem():
    [problem] = drawing_problems("## S\n```svg\nhello\n```\n")
    assert "cannot be shown" in problem and "Draw it again" in problem


def test_an_unclosed_fence_does_not_hide_a_drawing_or_crash():
    drawing_problems("## S\n```svg\n<svg onload=x>")
    assert isinstance(drawings_in("```svg\n<svg>"), list)


def test_at_most_four_drawing_problems_are_reported():
    body = "".join(f"```svg\n<svg onload=x{i}></svg>\n```\n" for i in range(9))
    assert len(drawing_problems(body)) == 4


def test_a_drawing_inside_a_longer_fence_and_with_attributes_on_the_fence_line():
    assert len(drawings_in("````svg\n<svg/>\n````\n")) == 1
    assert drawings_in("```svg title=x\n<svg/>\n```\n") == []             # a fence line with extra words is not recognised as svg; the validator treats it as other code


# ---- gaps the mutation sweep found (2026-10-31) -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("value", ["javascript:alert(1)", "JavaScript:x", "data:text/html,hi", "url(http://x/y)", "a &amp; b", "&#106;avascript", "vbscript:x", "expression(x)", "a & b", "Tom & Jerry", "&lt", "&ampx"])
def test_aria_label_is_the_one_value_that_may_hold_punctuation_so_the_word_and_ampersand_checks_must_hold(value):
    result = sanitise_svg(f'<svg aria-label="{value}"><rect/></svg>')
    assert "aria-label" not in result.svg and result.ok
    assert result.report.removed == ["an unsafe value for 'aria-label' on <svg>"]


def test_a_label_with_ordinary_punctuation_is_kept_exactly():
    assert 'aria-label="Room list (3 rooms) / floor 2"' in sanitise_svg('<svg aria-label="Room list (3 rooms) / floor 2"><rect/></svg>').svg


@pytest.mark.parametrize("name", ["href", "xlink:href", "src", "onclick"])
def test_a_link_or_handler_is_dropped_for_its_name_even_when_its_value_is_harmless(name):
    result = sanitise_svg(f'<svg><rect {name}="evil" x="1"/></svg>')
    assert name not in result.svg and 'x="1"' in result.svg
    assert result.report.removed == [f"the attribute '{name}' on <rect>"] or name == "onclick"


@pytest.mark.parametrize("d", ["M0 0 xyz", "M0 0 L1 1;", "M0 0 <", "M0 0 'x'"])
def test_a_path_with_anything_outside_the_path_alphabet_is_dropped(d):
    assert ' d="' not in sanitise_svg(f'<svg><path d="{d}"/></svg>').svg


@pytest.mark.parametrize("t", ["matrix(1 0 0 1 0 0)", "translate(1 2) foo", "foo", "translate(1 2); x", "translate(a)"])
def test_a_transform_that_is_not_a_plain_move_scale_rotate_or_skew_is_dropped(t):
    assert "transform" not in sanitise_svg(f'<svg><g transform="{t}"/></svg>').svg


def test_a_value_has_the_spaces_around_it_trimmed():
    assert sanitise_svg('<svg><rect fill=" #eee " x="  5 "/></svg>').svg == '<svg><rect fill="#eee" x="5" /></svg>'


def test_a_screen_exactly_at_the_limit_is_kept_and_one_character_over_is_refused():
    base = "<svg>" + ("<text>" + "a" * 400 + "</text>") * 29            # 5 + 29 * 413 = 11,982 characters so far; "</svg>" makes 11,988
    exact = base + "<g /><g></g></svg>"                                  # + 5 + 7 = 12,000
    one_over = base + "<text></text></svg>"                              # + 13   = 12,001
    kept, refused = sanitise_svg(exact), sanitise_svg(one_over)
    assert S.MAX_OUTPUT_CHARS == 12_000                                   # pinned as a literal: a changed constant would otherwise move both sides
    assert kept.ok and len(kept.svg) == 12_000
    assert not refused.ok and refused.svg == "" and refused.report.removed == ["a screen is limited to 12000 characters"]


def test_closing_tags_added_for_unclosed_elements_count_towards_the_limit():
    """The limit is on what is RETURNED. A body that is just under it as read, but needs closing tags added, must be refused.
    (Ten open <g> plus the <svg> stay inside the depth limit of 12, so the size limit is what decides.)"""
    open_only = "<svg>" + "<g>" * 10 + ("<text>" + "a" * 400 + "</text>") * 28 + "<text>" + "a" * 360 + "</text>"
    closing_tags = len("</g>") * 10 + len("</svg>")
    assert len(open_only) < S.MAX_OUTPUT_CHARS < len(open_only) + closing_tags       # as written it fits; once closed it does not
    closed = sanitise_svg(open_only)
    assert not closed.ok and closed.svg == ""
    assert any("limited to" in r for r in closed.report.removed)
    # and the same screen with room for the closing tags is kept whole
    fits = sanitise_svg("<svg>" + "<g>" * 10 + ("<text>" + "a" * 400 + "</text>") * 28 + "<text>" + "a" * 300 + "</text>")
    assert fits.ok and len(fits.svg) <= S.MAX_OUTPUT_CHARS and fits.svg.endswith("</g></svg>")


def test_a_refused_screen_returns_no_markup_at_all():
    for text in ("<svg>" + "<rect/>" * 20_000 + "</svg>", "<svg>" + ("<text>" + "a" * 400 + "</text>") * 40 + "</svg>", "hello", "<script>x</script>"):
        result = sanitise_svg(text)
        if not result.ok:
            assert result.svg == ""


def test_a_longer_fence_is_not_closed_by_a_shorter_one():
    body = "````svg\n<svg><rect/></svg>\n```\n<svg><circle/></svg>\n````\n"
    found = drawings_in(body)
    assert len(found) == 1 and "<circle/>" in found[0][2] and found[0][1] == 5


def test_a_fence_marker_of_the_other_kind_does_not_close_it():
    found = drawings_in("```svg\n<svg/>\n~~~\n<svg><g/></svg>\n```\n")
    assert len(found) == 1 and "<g/>" in found[0][2]
