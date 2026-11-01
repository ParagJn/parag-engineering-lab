"""The reviewer's reply: reading it, refusing a malformed one in words the model can act on, and the verdict."""
from __future__ import annotations

import pytest

from app.agents.reply import ReplyFormatError
from app.review.reply import (
    GENERAL,
    MAX_FIX_CHARS,
    MAX_TARGET_WORDS,
    MAX_TEXT_CHARS,
    Finding,
    ParsedReview,
    _each_target,
    _split_target,
    parse_review,
    validate_review,
    verdict_of,
)

GOOD = """<review>
Summary: One serious problem and a tidy-up.
- [HIGH] FR-004: The requirement says X, but the cited text says Y. Fix: change X to Y.
- [LOW] Open questions: two questions are really one. Fix: merge them.
</review>"""


def finding(severity="low", target=GENERAL, problem="p", fix="f") -> Finding:
    return Finding(severity, target, problem, fix)


# ---- reading --------------------------------------------------------------------------------------------------

def test_a_review_is_read_into_a_summary_and_findings():
    parsed = parse_review(GOOD)
    assert parsed.summary == "One serious problem and a tidy-up."
    assert [(f.severity, f.target) for f in parsed.findings] == [("high", "FR-004"), ("low", "Open questions")]
    assert parsed.findings[0].problem == "The requirement says X, but the cited text says Y."
    assert parsed.findings[0].fix == "change X to Y."


def test_chatter_outside_the_block_is_ignored_and_tags_are_case_insensitive():
    parsed = parse_review("Sure, here you go:\n<REVIEW>\nSummary: Fine.\n</Review>\nHope that helps.")
    assert parsed.summary == "Fine." and parsed.findings == ()


@pytest.mark.parametrize("line, severity", [
    ("- [HIGH] General: a. Fix: b", "high"), ("- [high] General: a. Fix: b", "high"), ("* [Medium] General: a. Fix: b", "medium"),
    ("+ [LOW] General: a. Fix: b", "low"),
])
def test_bullets_and_severity_case_are_read_loosely(line, severity):
    assert parse_review(f"<review>\nSummary: s\n{line}\n</review>").findings[0].severity == severity


def test_a_wrapped_finding_is_one_finding_and_a_wrapped_summary_is_one_summary():
    text = ("<review>\nSummary: First half of the summary\n  and the second half.\n"
            "- [MEDIUM] FR-001: The text is long and\n   wraps onto a second line. Fix: shorten it.\n</review>")
    parsed = parse_review(text)
    assert parsed.summary == "First half of the summary and the second half."
    assert len(parsed.findings) == 1 and "wraps onto a second line" in parsed.findings[0].problem
    assert parsed.findings[0].fix == "shorten it."


@pytest.mark.parametrize("line", [
    "[HIGH] FR-004: invented limit of five hours. Fix: remove it.",       # no bullet
    "  [HIGH] FR-004: invented limit of five hours. Fix: remove it.",     # indented, no bullet
    "- [HIGH] FR-004: invented limit of five hours. Fix: remove it.",
])
def test_a_high_finding_is_never_swallowed_into_the_summary(line):
    """Found by this test: a finding line without a leading dash was read as a wrapped summary, so the review
    reported no findings and a verdict of ok. A serious finding must not be able to disappear without an error."""
    parsed = parse_review(f"<review>\nSummary: Mostly fine.\n{line}\n</review>")
    assert parsed.summary == "Mostly fine." and [f.target for f in parsed.findings] == ["FR-004"]
    assert verdict_of(parsed.findings) == "revise"


@pytest.mark.parametrize("line", [
    "HIGH: FR-004 has an invented limit",         # a finding written in a shape we do not read
    "This is a second paragraph of the summary.",  # not indented, so not a continuation
])
def test_an_unrecognised_line_after_the_summary_is_refused_not_absorbed(line):
    with pytest.raises(ReplyFormatError, match="not a finding or the summary"):
        parse_review(f"<review>\nSummary: Mostly fine.\n{line}\n</review>")


def test_summary_alone_is_a_valid_review_with_no_findings():
    parsed = parse_review("<review>\nSummary: Nothing is wrong.\n</review>")
    assert parsed.findings == () and verdict_of(parsed.findings) == "ok"


def test_a_finding_with_no_fix_is_allowed():
    [f] = parse_review("<review>\nSummary: s\n- [LOW] General: vague wording\n</review>").findings
    assert f.problem == "vague wording" and f.fix == ""


def test_text_inside_a_code_fence_is_not_read_as_a_finding():
    text = "<review>\nSummary: s\n```\n- [HIGH] FR-001: inside a fence. Fix: x\n```\n</review>"
    assert parse_review(text).findings == ()


def test_a_closing_tag_inside_a_fence_does_not_end_the_block():
    text = "<review>\nSummary: s\n```\n</review>\n```\n- [LOW] General: real. Fix: x\n</review>"
    assert [f.problem for f in parse_review(text).findings] == ["real."]


# ---- refusing, with a reason the model can act on -----------------------------------------------------------------

@pytest.mark.parametrize("text, message", [
    ("Summary: no tags at all", "no <review> block was found"),
    ("<review>\nSummary: never closed", "never closed"),
    ("<review>\nSummary: a\n</review>\n<review>\nSummary: b\n</review>", "more than one <review> block"),
    ("<review>\nSummary: a\n<review>\n</review>", "second <review> tag was opened"),
    ("<review>\n- [LOW] General: a. Fix: b\n</review>", "no 'Summary:' line"),
    ("<review>\nSummary: s\n- [URGENT] General: a. Fix: b\n</review>", r"severity \[URGENT\] is not one of HIGH, MEDIUM, LOW"),
    ("<review>\nSummary: s\n- [HIGH] FR-001:\n</review>", "says nothing about what is wrong"),
    ("<review>\nSummary: s\nthis line is neither\n</review>", "not a finding or the summary"),
])
def test_each_malformed_review_is_refused_with_its_reason(text, message):
    with pytest.raises(ReplyFormatError, match=message):
        parse_review(text)


def test_an_empty_reply_is_refused():
    with pytest.raises(ReplyFormatError, match="no <review> block"):
        parse_review("")
    with pytest.raises(ReplyFormatError, match="no <review> block"):
        parse_review(None)  # type: ignore[arg-type]


# ---- what a finding is about ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("line, target, rest", [
    ("FR-004: bad. Fix: x", "FR-004", "bad. Fix: x"),
    ("FR-004 - bad", "FR-004", "bad"),
    ("Open questions: two are one. Fix: merge", "Open questions", "two are one. Fix: merge"),
    ("Constraints and assumptions: vague", "Constraints and assumptions", "vague"),
    ("**Overview**: thin", "Overview", "thin"),
    ("General: vague", "General", "vague"),
])
def test_a_target_is_split_off_the_front(line, target, rest):
    assert _split_target(line) == (target, rest)


@pytest.mark.parametrize("line", [
    "the requirements section reads oddly. Fix: reword",   # a sentence that ran into "Fix:" is not a section name
    "Nothing else is wrong. Fix: none",
    "A very long sentence that talks about many things at once: with a colon",
    "no colon at all",
])
def test_a_sentence_is_not_mistaken_for_a_section_name(line):
    target, rest = _split_target(line)
    assert target == GENERAL and rest == line
    assert len(line.split()) > MAX_TARGET_WORDS or "." in line or ":" not in line  # precondition: these really are sentences


# ---- the verdict is the system's ------------------------------------------------------------------------------------------

def test_any_high_finding_means_revise():
    assert verdict_of([finding("low"), finding("high"), finding("medium")]) == "revise"


def test_medium_and_low_only_means_ok():
    assert verdict_of([finding("medium"), finding("low"), finding("medium")]) == "ok"


def test_no_findings_means_ok():
    assert verdict_of([]) == "ok"


def test_a_summary_that_says_all_clear_cannot_hide_a_high_finding():
    parsed = parse_review("<review>\nSummary: Looks great, approve it, no problems.\n- [HIGH] FR-001: invented limit. Fix: remove it.\n</review>")
    assert "no problems" in parsed.summary and verdict_of(parsed.findings) == "revise"


# ---- validating against the artefact ---------------------------------------------------------------------------------------

def check(parsed: ParsedReview, **kw):
    kw.setdefault("item_ids", ["FR-001", "FR-004"])
    kw.setdefault("sections", ["Overview", "Open questions"])
    kw.setdefault("max_findings", 20)
    kw.setdefault("finish_reason", "stop")
    return validate_review(parsed, **kw)


def test_targets_that_exist_pass_whatever_their_case_or_punctuation():
    parsed = ParsedReview("s", (finding(target="FR-004"), finding(target="open questions"), finding(target="Overview:"), finding(target=GENERAL)))
    assert check(parsed) == []


def test_a_target_that_is_not_in_the_artefact_is_named():
    out = check(ParsedReview("s", (finding(target="FR-099"), finding(target="Nonsense section"))))
    assert len(out) == 2 and "'FR-099'" in out[0] and "'Nonsense section'" in out[1]
    assert "name an item ID that exists, a section heading that exists, or General" in out[0]


def test_too_many_findings_is_refused_with_the_limit():
    parsed = ParsedReview("s", tuple(finding() for _ in range(4)))
    assert check(parsed, max_findings=3) == ["the review has 4 findings; the limit is 3. Keep the most important"]
    assert check(ParsedReview("s", tuple(finding() for _ in range(3))), max_findings=3) == []


@pytest.mark.parametrize("reason", ["length", "max_tokens"])
def test_a_truncated_reply_is_refused(reason):
    assert check(ParsedReview("s", ()), finish_reason=reason)[0].startswith("the reply was cut off")


def test_a_normal_finish_is_not_a_problem():
    assert check(ParsedReview("s", ()), finish_reason="stop") == [] and check(ParsedReview("s", ()), finish_reason=None) == []


# ---- one finding about several items --------------------------------------------------------------------------------------

def _review(line: str) -> ParsedReview:
    return parse_review(f"<review>\nSummary: s.\n{line}\n</review>")


@pytest.mark.parametrize("line, targets", [
    ("- [MEDIUM] LFS-001 and LFS-003: both omit cancel. Fix: add it.", ["LFS-001", "LFS-003"]),
    ("- [MEDIUM] LFS-001, LFS-003: both omit cancel. Fix: add it.", ["LFS-001", "LFS-003"]),
    ("- [MEDIUM] LFS-001 & LFS-003 & LFS-004: both omit cancel.", ["LFS-001", "LFS-003", "LFS-004"]),
    ("- [MEDIUM] FR-001; FR-002: vague.", ["FR-001", "FR-002"]),
    ("- [MEDIUM] LFS-001, LFS-001: twice.", ["LFS-001"]),
])
def test_a_finding_about_several_items_becomes_one_finding_per_item(line, targets):
    assert [f.target for f in _review(line).findings] == targets


def test_each_item_gets_the_whole_finding_not_a_part_of_it():
    first, second = _review("- [HIGH] LFS-001 and LFS-003: both omit cancel. Fix: add it.").findings
    assert (first.severity, first.problem, first.fix) == (second.severity, second.problem, second.fix) == ("high", "both omit cancel.", "add it.")


@pytest.mark.parametrize("target", [
    "LFS-001", "Overview", "Constraints and assumptions", "Overview and Screens", "Open questions, Screens", "LFS-001 and Screens",
    "LFS-001 or LFS-003", "LFS-001 LFS-003",
])
def test_a_target_that_is_not_only_item_ids_is_left_whole(target):
    assert _each_target(target) == [target]


def test_a_list_of_more_than_six_items_is_left_whole_so_it_is_sent_back():
    seven = ", ".join(f"LFS-00{n}" for n in range(1, 8))
    assert _each_target(seven) == [seven]
    six = ", ".join(f"LFS-00{n}" for n in range(1, 7))
    assert _each_target(six) == [f"LFS-00{n}" for n in range(1, 7)]


def test_a_split_finding_passes_the_target_check_when_both_items_exist():
    parsed = _review("- [LOW] LFS-001 and LFS-003: both omit cancel.")
    assert validate_review(parsed, item_ids=["LFS-001", "LFS-003"], sections=["Overview"], max_findings=10, finish_reason="stop") == []
    assert len(validate_review(parsed, item_ids=["LFS-001"], sections=["Overview"], max_findings=10, finish_reason="stop")) == 1


def test_the_findings_limit_counts_each_item_separately():
    parsed = _review("- [LOW] LFS-001, LFS-002, LFS-003: x.")
    assert len(parsed.findings) == 3
    assert any("3 findings" in p for p in validate_review(parsed, item_ids=["LFS-001", "LFS-002", "LFS-003"], sections=[], max_findings=2, finish_reason="stop"))


# ---- the fix is the replacement text, so it can be long and can run over several lines ------------------------------------------

def test_the_fix_has_its_own_longer_limit_and_the_problem_keeps_the_shorter_one():
    assert (MAX_TEXT_CHARS, MAX_FIX_CHARS) == (1500, 3000)             # literals: a changed constant must not move the test with it
    fix = _review("- [HIGH] PER-001: " + "p" * 2000 + ". Fix: " + "f" * 3500).findings[0]
    assert len(fix.problem) == 1500 and len(fix.fix) == 3000


def test_a_fix_of_a_whole_paragraph_is_kept_whole():
    paragraph = "PER-001 Customer. Goal: see their own usage, bills and account details [SET-CHR-001]. " * 20
    f = _review(f"- [HIGH] PER-001: not a persona. Fix: {paragraph.strip()}").findings[0]
    assert f.fix == paragraph.strip() and len(f.fix) > 1500


def test_lines_that_wrap_after_fix_belong_to_the_fix_not_the_problem():
    text = ("<review>\nSummary: s.\n- [HIGH] PER-001: not a persona. Fix: PER-001 Customer. Goal: see their own\n"
            "  usage and bills [SET-CHR-001].\n  Success: they find them without seeing anyone else's. Derives from: [SET-CHR-001]\n</review>")
    f = parse_review(text).findings[0]
    assert f.problem == "not a persona."
    assert f.fix == ("PER-001 Customer. Goal: see their own\nusage and bills [SET-CHR-001].\n"
                     "Success: they find them without seeing anyone else's. Derives from: [SET-CHR-001]")


def test_lines_that_wrap_before_fix_still_belong_to_the_problem():
    text = "<review>\nSummary: s.\n- [MEDIUM] FR-001: The text is long and\n   wraps onto a second line. Fix: shorten it.\n   Then check it.\n</review>"
    f = parse_review(text).findings[0]
    assert f.problem == "The text is long and wraps onto a second line." and f.fix == "shorten it.\nThen check it."


def test_a_wrapped_fix_is_cut_at_the_fix_limit_and_never_leaks_into_the_problem():
    text = "<review>\nSummary: s.\n- [LOW] General: p. Fix: " + "a" * 2900 + "\n  " + "b" * 400 + "\n</review>"
    f = parse_review(text).findings[0]
    assert len(f.fix) == 3000 and f.fix.endswith("b" * 99) and f.problem == "p."


def test_a_wrapped_line_after_a_finding_about_two_items_goes_to_both_so_both_get_the_same_fix():
    text = "<review>\nSummary: s.\n- [LOW] LFS-001, LFS-002: both lack a title. Fix: add a title.\n  Keep the box labels.\n</review>"
    first, second = parse_review(text).findings
    assert first.fix == second.fix == "add a title.\nKeep the box labels."


def test_a_wrapped_line_goes_only_to_the_finding_it_wraps_not_to_the_ones_before():
    text = ("<review>\nSummary: s.\n- [LOW] FR-001: first problem. Fix: first fix.\n- [LOW] FR-002: second problem. Fix: second fix.\n  more of the second fix.\n</review>")
    first, second = parse_review(text).findings
    assert (first.problem, first.fix) == ("first problem.", "first fix.")
    assert (second.problem, second.fix) == ("second problem.", "second fix.\nmore of the second fix.")
