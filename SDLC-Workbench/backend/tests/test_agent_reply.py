"""Reading a model's reply and checking it: the last gate before anything is saved."""
from __future__ import annotations

import pytest

from app.agents.reply import (
    MAX_BODY_CHARS,
    ReplyFormatError,
    cited_ids,
    missing_sections,
    parse_reply,
    unknown_citations,
    validate,
)


def wrap(body: str) -> str:
    return f"<artefact>\n{body}\n</artefact>"


# ---- parsing -----------------------------------------------------------------------------------------

def test_a_clean_reply_gives_its_body():
    assert parse_reply(wrap("## A\nbody")) == "## A\nbody"


@pytest.mark.parametrize(
    "text",
    [
        "Sure, here you go!\n<artefact>\n## A\nbody\n</artefact>\nHope that helps.",
        "```markdown\n<artefact>\n## A\nbody\n</artefact>\n```",
        "<ARTEFACT>\r\n## A\r\nbody\r\n</ARTEFACT>",
        "<artefact>\r## A\rbody\r</artefact>",
        "  <artefact>  \n## A\nbody\n  </artefact>  ",
        "<Artefact>\n## A\nbody\n</ARTEFACT>",
    ],
)
def test_the_usual_mess_around_the_block_is_tolerated(text):
    assert parse_reply(text) == "## A\nbody"


def test_a_closing_tag_inside_a_code_block_is_part_of_the_body_not_the_end():
    text = "<artefact>\n## A\n```\n</artefact>\n```\nmore text\n</artefact>"
    assert parse_reply(text) == "## A\n```\n</artefact>\n```\nmore text"


def test_a_tilde_fence_works_the_same_way():
    assert "more" in parse_reply("<artefact>\n~~~\n</artefact>\n~~~\nmore\n</artefact>")


@pytest.mark.parametrize(
    "text, fragment",
    [
        ("## A\nbody", "no <artefact> block"),
        ("", "no <artefact> block"),
        (None, "no <artefact> block"),
        ("<artefact>\n## A\nbody", "never closed"),
        ("<artefact>\nx\n</artefact>\n<artefact>\ny\n</artefact>", "more than one"),
        ("<artefact>\nx\n<artefact>\ny\n</artefact>", "second <artefact> tag"),
        ("<artefact>\n\n  \n</artefact>", "empty"),
        ("<artefact>## A body</artefact>", "no <artefact> block"),
        ("</artefact>\n<artefact>\nbody", "never closed"),
    ],
)
def test_unusable_replies_are_refused_with_an_instruction_the_model_can_follow(text, fragment):
    with pytest.raises(ReplyFormatError, match=fragment):
        parse_reply(text)


# ---- sections -------------------------------------------------------------------------------------------

BODY = "# Title\n## Overview\ntext\n## Personas\n### Alice\ndetail\n## Open questions\n\n## Notes\nx"


def test_missing_and_empty_sections_are_found():
    assert missing_sections(BODY, ["Overview", "Personas", "Open questions", "Risks"]) == ["Open questions", "Risks"]


def test_a_section_with_only_subsections_counts_as_filled():
    assert missing_sections(BODY, ["Personas"]) == []


@pytest.mark.parametrize("heading", ["## open QUESTIONS:", "##  Open   questions  ", "## Open-questions", "### Open questions ###"])
def test_heading_matching_ignores_case_punctuation_and_level(heading):
    assert missing_sections(f"{heading}\nsomething", ["Open questions"]) == []


def test_a_heading_inside_a_code_fence_does_not_count():
    assert missing_sections("```\n## Overview\ntext\n```", ["Overview"]) == ["Overview"]


def test_text_that_merely_mentions_a_section_name_is_not_a_section():
    assert missing_sections("We should add an Overview later.", ["Overview"]) == ["Overview"]


def test_a_nested_section_ends_at_the_next_heading_of_the_same_or_higher_level():
    body = "## A\n### A1\nstuff\n## B\n"
    assert missing_sections(body, ["A", "B"]) == ["B"]  # B has no text of its own


# ---- citations ----------------------------------------------------------------------------------------------

def test_every_shape_of_source_id_is_recognised_once_in_order_of_first_use():
    body = ("Rules [DOC-001#2] and [REQ-PER-001, SET-CHR-001@v2#1]; memory [MEM-017]; "
            "again [DOC-001#2]; semicolon list [DOC-003#1; DOC-004#2].")
    assert cited_ids(body) == ["DOC-001#2", "REQ-PER-001", "SET-CHR-001@v2#1", "MEM-017", "DOC-003#1", "DOC-004#2"]


@pytest.mark.parametrize("text", ["[1]", "[note]", "[REQ-F]", "[doc-001#1]", "[DOC-1#1]", "[see above]", "[]", "[DOC-001]", "[x](http://a)"])
def test_brackets_that_are_not_source_ids_are_not_citations(text):
    assert cited_ids(f"A claim {text}.") == []


def test_citations_inside_code_fences_are_not_scanned():
    assert cited_ids("```\nlist[DOC-001#1] = 3\n```\nreal [DOC-002#1]") == ["DOC-002#1"]


def test_unknown_citations_are_exactly_the_ones_not_allowed():
    body = "[DOC-001#1] [DOC-002#1] [REQ-PER-001]"
    assert unknown_citations(body, {"DOC-001#1", "REQ-PER-001"}) == ["DOC-002#1"]
    assert unknown_citations(body, set(body.replace("[", "").replace("]", "").split())) == []
    assert unknown_citations("no citations here", set()) == []


# ---- the whole check ---------------------------------------------------------------------------------------------

def test_a_good_reply_has_no_problems():
    assert validate("## Overview\nfine [DOC-001#1]", ["Overview"], {"DOC-001#1"}, "stop") == []


def test_every_kind_of_problem_is_reported_in_words_the_model_can_act_on():
    problems = validate("## Overview\nHi [DOC-777#1] [DOC-778#1].", ["Overview", "Risks"], {"DOC-001#1"}, "length")
    text = " | ".join(problems)
    assert "cut off" in text and "'Risks' is missing" in text and "[DOC-777#1], [DOC-778#1]" in text and "were not provided" in text
    assert len(problems) == 3


@pytest.mark.parametrize("reason", ["length", "max_tokens"])
def test_a_reply_cut_off_by_the_output_limit_is_rejected(reason):
    assert any("cut off" in p for p in validate("## A\nx", ["A"], set(), reason))


@pytest.mark.parametrize("reason", ["stop", None, "end_turn"])
def test_a_normal_ending_is_fine(reason):
    assert validate("## A\nx", ["A"], set(), reason) == []


def test_a_single_invented_citation_uses_the_singular():
    (problem,) = validate("## A\n[DOC-9#1] [DOC-009#1]", ["A"], set(), "stop")
    assert "which was not provided" in problem


def test_an_oversize_body_is_rejected():
    big = "## A\n" + "x" * (MAX_BODY_CHARS + 1)
    assert any("limit is" in p for p in validate(big, ["A"], set(), "stop"))


def test_a_real_id_that_was_not_shown_is_rejected_the_same_as_an_invented_one():
    """The point of 'shown in this prompt': a model must not cite from memory of an earlier run."""
    allowed = {"DOC-001#1"}
    assert validate("## A\n[DOC-002#1]", ["A"], allowed, "stop")  # exists somewhere, was not shown
    assert not validate("## A\n[DOC-001#1]", ["A"], allowed, "stop")
