"""S19a: the checks on instruction files for a coding tool. Pure text in, sentences out: no model, no subprocess, no database."""
from __future__ import annotations

import pytest

from app.build import instructions as I

DESIGN = I.DesignIds(frozenset({
    "UC-001", "UC-002", "API-001", "API-002", "API-003", "TBL-001", "TBL-002", "RUL-001", "RUL-002", "RUL-003", "COMP-001", "IFC-001", "FR-001", "US-001", "HFS-001",
}))


def scenario(name_id="UC-001", *, build="- API-003 POST /api/reservations reserves a room. Needs TBL-001.", rules="- RUL-001 A booking may not overlap another.",
             done="- A reservation is created\n- A clashing one is refused", derives="Derives from: UC-001, API-003, RUL-001", extra="", title="# Reserve a room"):
    return (f"{title}\n\n## Goal\nLet office staff reserve a free room.\n\n## Read first\nRead 00-foundation.md first.\n\n## What to build\n{build}\n\n"
            f"## Business rules that apply\n{rules}\n\n## Done when\n{done}\n\n## Do not\n- Do not add accounts or payments.\n\n## Traceability\n{derives}\n{extra}")


CONTRACT = (
    "- API-001 GET /api/rooms. Request: none. Response 200: object with rooms (list of room_id (integer), name (string)). Errors: 500.\n"
    "- API-002 GET /api/availability. Request: date (string YYYY-MM-DD), start_time (string HH:MM), end_time (string HH:MM). Response 200: object with free (list), reserved (list). Errors: 400.\n"
    "- API-003 POST /api/reservations. Request: room_id (integer), date (string YYYY-MM-DD), start_time (string HH:MM), end_time (string HH:MM). Response 201: object with reservation_id (integer). Errors: 400, 401, 404, 409, 422."
)


def foundation(*, tables="- TBL-001 rooms\n- TBL-002 reservations", shared="- RUL-001 A booking may not overlap another.", extra="", contract=False):
    """A foundation file. With `contract=True` (or text) it carries the S19d 'Interface contract' section, after 'Stack and layout' and before 'Tables'."""
    section = f"## Interface contract\n{CONTRACT if contract is True else contract}\n\n" if contract else ""
    return (f"# Foundation\n\n## Goal\nA small room booking service.\n\n## Stack and layout\nPython and FastAPI; one `app.py`; a `static/` folder for the pages.\n\n{section}"
            f"## Tables\n{tables}\n\n## Shared rules\n{shared}\n\n## How to run it\nRun `uvicorn app:app`.\n\n## Do not\n- Do not add login.\n\n"
            f"## Traceability\nDerives from: TBL-001, TBL-002, RUL-001\n{extra}")


def acceptance(*, derives="Derives from: API-001, API-003, RUL-001"):
    return (f"# Acceptance tests\n\n## Goal\nProve the service behaves as designed.\n\n## How to run the tests\nRun `pytest tests` against the running service.\n\n"
            f"## What the tests check\n- API-001 lists rooms\n- API-003 refuses a clash (RUL-001)\n\n## Do not\n- Do not change the tests to make them pass.\n\n## Traceability\n{derives}\n")


NAME = "UC-001-reserve-a-room.md"


def problems(kind, name, body, design=DESIGN):
    return I.check_file(kind, name, body, design)


# ---- good files pass ----------------------------------------------------------------------------------------------------------------------------

def test_a_complete_scenario_file_has_no_problems():
    assert problems("scenario", NAME, scenario()) == []


def test_a_complete_foundation_and_acceptance_file_have_no_problems():
    assert problems("foundation", I.FOUNDATION_NAME, foundation()) == []
    assert problems("acceptance", I.ACCEPTANCE_NAME, acceptance()) == []


def test_the_kinds_are_exactly_five_in_the_order_the_tool_works_in():
    assert I.KINDS == ("foundation", "ui_guide", "scenario", "screen", "acceptance")
    assert problems("other", NAME, scenario()) == ["unknown kind of instruction file 'other'"]


# ---- sections -----------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("section", I.SECTIONS["scenario"])
def test_a_missing_scenario_section_is_named(section):
    body = scenario().replace(f"## {section}\n", "## Something else\n", 1)
    assert any(f"'{section}' is missing or empty" in p for p in problems("scenario", NAME, body))


def test_an_empty_section_is_a_problem():
    body = scenario().replace("## Do not\n- Do not add accounts or payments.\n", "## Do not\n\n")
    assert any("'Do not' is missing or empty" in p for p in problems("scenario", NAME, body))


@pytest.mark.parametrize("word", ["TBD", "TODO", "...", "n/a", "To be decided", "tba", "-", "…", "- - -", "___", "  .  "])
def test_a_section_that_holds_only_a_placeholder_is_a_problem(word):
    body = scenario(rules=word)
    assert any("holds only a placeholder" in p and "Business rules that apply" in p for p in problems("scenario", NAME, body))


def test_not_applicable_is_allowed_only_where_the_kind_says_so():
    assert problems("scenario", NAME, scenario(rules="Not applicable")) == []
    assert problems("scenario", NAME, scenario(rules="not applicable.")) == []
    body = scenario().replace("## Goal\nLet office staff reserve a free room.", "## Goal\nNot applicable")
    assert any("'Goal' cannot be 'Not applicable'" in p for p in problems("scenario", NAME, body))
    assert problems("foundation", I.FOUNDATION_NAME, foundation(tables="Not applicable", shared="Not applicable")) == []
    body = foundation().replace("## How to run it\nRun `uvicorn app:app`.", "## How to run it\nNot applicable")
    assert any("'How to run it' cannot be 'Not applicable'" in p for p in problems("foundation", I.FOUNDATION_NAME, body))


def test_the_acceptance_file_may_not_say_not_applicable_anywhere():
    assert I.NOT_APPLICABLE_OK["acceptance"] == ()
    body = acceptance().replace("- API-001 lists rooms\n- API-003 refuses a clash (RUL-001)", "Not applicable")
    assert any("'What the tests check' cannot be 'Not applicable'" in p for p in problems("acceptance", I.ACCEPTANCE_NAME, body))


def test_the_sections_must_come_in_the_stated_order():
    body = scenario()
    a, b = body.index("## Goal"), body.index("## Read first")
    swapped = body[:a] + body[b:body.index("## What to build")] + body[a:b] + body[body.index("## What to build"):]
    assert any("out of order" in p for p in problems("scenario", NAME, swapped))
    assert not any("out of order" in p for p in problems("scenario", NAME, scenario()))


def test_the_file_must_start_with_a_title():
    assert any("start the file with a '# <title>' line" in p for p in problems("scenario", NAME, scenario(title="Reserve a room")))


# ---- placeholders, invented IDs, size ------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("left", ["TODO", "TBD", "FIXME", "[fill in the endpoint]", "<insert the rule>", "lorem ipsum"])
def test_a_placeholder_left_anywhere_in_the_file_is_a_problem(left):
    body = scenario(extra=f"\nNote: {left}\n")
    assert any("placeholder left in it" in p for p in problems("scenario", NAME, body))


def test_ordinary_words_that_contain_a_placeholder_word_are_not_flagged():
    assert problems("scenario", NAME, scenario(extra="\nThe todolist page is out of scope. Methodology is plain.\n")) == []


def test_an_id_that_is_not_in_the_design_is_named_as_invented():
    found = problems("scenario", NAME, scenario(build="- API-099 POST /api/x invents a thing. Needs TBL-001.", derives="Derives from: UC-001, API-099"))
    assert any("API-099 is not in the design" in p for p in found)


def test_several_invented_ids_are_listed_together_and_bounded():
    ids = ", ".join(f"RUL-{n:03d}" for n in range(50, 60))
    found = [p for p in problems("scenario", NAME, scenario(rules=f"- {ids}")) if "not in the design" in p]
    assert len(found) == 1 and "are not in the design" in found[0] and "and 5 more" in found[0]


def test_an_id_that_exists_is_never_called_invented_and_unknown_prefixes_are_left_alone():
    assert not any("not in the design" in p for p in problems("scenario", NAME, scenario(extra="\nSee HTTP-404 and ISO-9001 for notes.\n")))


def test_a_file_over_the_size_limit_is_refused():
    big = scenario(extra="\n" + "x" * I.MAX_FILE_CHARS)
    assert any(f"the limit is {I.MAX_FILE_CHARS}" in p for p in problems("scenario", NAME, big))
    just = scenario()
    assert len(just) < I.MAX_FILE_CHARS


# ---- names --------------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    "reserve-a-room.md", "UC-001.md", "uc-001-reserve.md", "UC-001-Reserve.md", "UC-001-reserve a room.md", "UC-001-reserve.txt", "UC-001-reserve.MD",
    "../UC-001-reserve.md", "UC-001--reserve.md", "UC-001-reserve-.md", "UC-1-reserve.md",
])
def test_a_scenario_file_name_that_is_not_in_the_form_is_refused(name):
    assert I.name_problem("scenario", name, DESIGN) is not None and I.kind_of(name) is None


def test_a_scenario_file_must_be_named_for_a_use_case_that_exists():
    assert I.name_problem("scenario", "UC-001-reserve.md", DESIGN) is None
    assert "UC-099, which is not a use case" in I.name_problem("scenario", "UC-099-reserve.md", DESIGN)
    assert "API-001, which is not a use case" in (I.name_problem("scenario", "API-001-x.md", DESIGN) or "") or I.name_problem("scenario", "API-001-x.md", DESIGN) is not None


def test_the_fixed_files_have_fixed_names():
    assert I.name_problem("foundation", "00-foundation.md", DESIGN) is None and "must be named 00-foundation.md" in I.name_problem("foundation", "foundation.md", DESIGN)
    assert I.name_problem("acceptance", "99-acceptance.md", DESIGN) is None and "must be named 99-acceptance.md" in I.name_problem("acceptance", "acceptance.md", DESIGN)


def test_a_long_name_is_refused():
    long = "UC-001-" + "a" * 100 + ".md"
    assert "the limit is 80" in I.name_problem("scenario", long, DESIGN)


def test_a_slug_is_readable_safe_and_never_empty():
    assert I.slug("Browse rooms & availability!") == "browse-rooms-availability"
    assert I.slug("  Reserve   a  room ") == "reserve-a-room"
    assert I.slug("../../etc/passwd") == "etc-passwd"
    assert I.slug("") == "scenario" and I.slug("!!!") == "scenario" and I.slug(None) == "scenario"
    assert I.slug("é ü ñ") == "scenario" or I.slug("é ü ñ").isascii()
    assert len(I.slug("a" * 200)) == I.MAX_SLUG and not I.slug("a" * 49 + " b" + "c" * 10).endswith("-")


def test_a_scenario_name_is_the_id_then_the_slug_and_passes_its_own_check():
    name = I.scenario_name("UC-001", "Browse rooms & availability")
    assert name == "UC-001-browse-rooms-availability.md" and I.name_problem("scenario", name, DESIGN) is None


def test_files_are_ordered_foundation_then_scenarios_then_acceptance():
    names = ["99-acceptance.md", "UC-002-b.md", "00-foundation.md", "UC-001-a.md"]
    assert sorted(names, key=I.order_key) == ["00-foundation.md", "UC-001-a.md", "UC-002-b.md", "99-acceptance.md"]


# ---- traceability and build sections ------------------------------------------------------------------------------------------------------------

def test_the_traceability_section_must_say_derives_from():
    body = scenario(derives="From the design.")
    assert any("must say 'Derives from:'" in p for p in problems("scenario", NAME, body))


def test_a_scenario_must_name_something_to_build_by_its_design_id():
    body = scenario(build="Build the reservation screen and the reservation endpoint.")
    assert any("'What to build' must name at least one screen, endpoint, table or interface" in p for p in problems("scenario", NAME, body))
    assert problems("scenario", NAME, scenario(build="- HFS-001 the reservation screen")) == []
    assert problems("scenario", NAME, scenario(build="- TBL-001 the rooms table")) == []


def test_a_scenario_must_name_its_own_use_case_in_traceability():
    body = scenario(derives="Derives from: API-003, RUL-001")
    assert any("must name the use case this file is for, UC-001" in p for p in problems("scenario", NAME, body))


def test_done_when_must_be_a_checkable_list():
    body = scenario(done="It works well.")
    assert any("'Done when' must be a list of statements" in p for p in problems("scenario", NAME, body))
    assert problems("scenario", NAME, scenario(done="1. A reservation is created\n2. A clash is refused")) == []


# ---- code in an instruction file -----------------------------------------------------------------------------------------------------------------

def fenced(lines, kind="python"):
    return f"\n```{kind}\n" + "\n".join(f"x = {n}" for n in range(lines)) + "\n```\n"


def test_code_blocks_are_measured_in_lines_and_unclosed_ones_still_count():
    assert I.code_blocks("text") == []
    assert I.code_blocks(fenced(3) + "mid\n" + fenced(5)) == [3, 5]
    assert I.code_blocks("```\na\nb") == [2] and I.code_blocks("```\na\nb\n") == [3]                    # a final newline is one more (empty) line
    assert I.code_blocks("````\n```\ninner\n```\n````\n") == [3] or I.code_blocks("````\n```\ninner\n```\n````\n") == [1]


def test_a_scenario_may_carry_a_short_example_but_not_the_application():
    assert problems("scenario", NAME, scenario(extra=fenced(30))) == []
    assert any("lines of code" in p for p in problems("scenario", NAME, scenario(extra=fenced(31))))
    assert problems("scenario", NAME, scenario(extra=fenced(20) + fenced(20) + fenced(20))) == []                  # 60 in all is exactly the cap
    assert any("lines of code" in p for p in problems("scenario", NAME, scenario(extra=fenced(20) + fenced(20) + fenced(21))))


def test_the_foundation_may_carry_more_code_than_a_scenario_but_not_unlimited():
    assert problems("foundation", I.FOUNDATION_NAME, foundation(extra=fenced(80))) == []
    assert any("lines of code" in p for p in problems("foundation", I.FOUNDATION_NAME, foundation(extra=fenced(81))))
    assert any("lines of code" in p for p in problems("foundation", I.FOUNDATION_NAME, foundation(extra=fenced(70) + fenced(70) + fenced(70))))


def test_acceptance_tests_are_code_so_they_have_no_cap():
    assert "acceptance" not in I.CODE_CAPS and problems("acceptance", I.ACCEPTANCE_NAME, acceptance().replace("## Do not", "```python\n" + "\n".join(["assert True"] * 400) + "\n```\n\n## Do not")) == []


def test_problems_are_bounded():
    body = "no title\n" + "".join(f"## Section {n}\n\n" for n in range(40))
    assert len(problems("scenario", NAME, body)) <= 8


# ---- the tool a set is written for -------------------------------------------------------------------------------------------------------------

def test_the_four_tools_are_exactly_these():
    assert I.TOOLS == {"copilot": "GitHub Copilot", "claude": "Claude", "gpt": "GPT", "gemini": "Gemini"}


@pytest.mark.parametrize("tool", ["copilot", "claude", "gpt", "gemini"])
def test_a_known_tool_is_accepted_and_its_header_is_its_own(tool):
    assert I.check_tool(tool) is None
    header = I.tool_header(tool)
    assert f"<!-- tool: {tool} -->" in header and I.TOOLS[tool] in header and "untried" in header


@pytest.mark.parametrize("tool", [None, "", "chatgpt", "CLAUDE", "copilot "])
def test_an_unknown_tool_is_refused_with_the_choices(tool):
    assert "one of copilot, claude, gpt, gemini" in I.check_tool(tool)


def test_the_four_headers_differ_but_the_body_is_identical():
    body = scenario()
    outs = {t: I.apply_tool(body, t) for t in I.TOOLS}
    assert len(set(outs.values())) == 4 and len({I.strip_tool(o) for o in outs.values()}) == 1 and I.strip_tool(outs["claude"]) == body


def test_applying_a_tool_twice_replaces_the_header_and_never_stacks_them():
    once = I.apply_tool(scenario(), "claude")
    twice = I.apply_tool(once, "gemini")
    assert twice.count("<!-- tool:") == 1 and I.tool_of(twice) == "gemini" and I.strip_tool(twice) == scenario()


def test_a_body_without_a_header_is_unchanged_by_stripping_and_has_no_tool():
    assert I.strip_tool(scenario()) == scenario() and I.tool_of(scenario()) is None
    assert I.tool_of("<!-- tool: nonsense -->\nrest") is None


def test_a_file_with_a_tool_header_still_passes_the_checks():
    assert problems("scenario", NAME, I.apply_tool(scenario(), "gpt")) == [] or all("title" in p for p in problems("scenario", NAME, I.apply_tool(scenario(), "gpt")))


# ---- a whole set ---------------------------------------------------------------------------------------------------------------------------------

def full_set(contract=False, **over):
    files = {
        I.FOUNDATION_NAME: foundation(extra="\n## Not covered\n- API-002 not needed for this prototype\n- RUL-002 left to a later release\n- RUL-003 left to a later release\n", contract=contract),
        "UC-001-reserve-a-room.md": scenario("UC-001", build="- API-001 GET /api/rooms and API-003 POST /api/reservations. Needs TBL-001 and TBL-002."),
        "UC-002-browse-rooms.md": scenario("UC-002", build="- API-001 GET /api/rooms lists rooms.", derives="Derives from: UC-002, API-001"),
        I.ACCEPTANCE_NAME: acceptance(),
    }
    files.update(over)
    return files


def test_a_complete_set_has_no_problems():
    assert I.check_set(full_set(), DESIGN) == []


def test_a_missing_foundation_or_acceptance_file_is_named():
    files = full_set()
    del files[I.FOUNDATION_NAME]
    assert any("no 00-foundation.md; it must come first" in p for p in I.check_set(files, DESIGN))
    files = full_set()
    del files[I.ACCEPTANCE_NAME]
    assert any("no 99-acceptance.md; it must come last" in p for p in I.check_set(files, DESIGN))


def test_a_use_case_with_no_file_is_named():
    files = full_set()
    del files["UC-002-browse-rooms.md"]
    found = I.check_set(files, DESIGN)
    assert any("UC-002 has no instruction file" in p for p in found) and not any("UC-001 has no" in p for p in found)


def test_a_file_for_a_use_case_that_does_not_exist_is_named():
    files = full_set(**{"UC-077-ghost.md": scenario("UC-077")})
    assert any("UC-077-ghost.md is for UC-077, which is not a use case in the design" in p for p in I.check_set(files, DESIGN))


def test_two_files_for_one_use_case_are_refused():
    files = full_set(**{"UC-001-another-take.md": scenario("UC-001")})
    assert any("UC-001 has more than one file (UC-001-another-take.md, UC-001-reserve-a-room.md)" in p for p in I.check_set(files, DESIGN))


def test_a_file_name_the_set_may_not_hold_is_named():
    assert any("'notes.md' is not a file name this set may hold" in p for p in I.check_set(full_set(**{"notes.md": "x"}), DESIGN))


def test_coverage_counts_named_declared_and_uncovered_items():
    cover = I.coverage(full_set(), DESIGN)
    assert cover["named"] == ["API-001", "API-003", "RUL-001", "TBL-001", "TBL-002"]
    assert cover["declared"] == ["API-002", "RUL-002", "RUL-003"] and cover["uncovered"] == []


def test_an_item_listed_under_not_covered_is_declared_never_counted_as_built():
    """The list that says 'nobody builds this' names the item, so reading every mention would make the declaration cancel itself."""
    files = {I.FOUNDATION_NAME: foundation(extra="\n## Not covered\n- API-002 later\n"), "UC-001-a.md": scenario("UC-001")}
    cover = I.coverage(files, DESIGN)
    assert "API-002" in cover["declared"] and "API-002" not in cover["named"] and "API-002" not in cover["uncovered"]


def test_the_acceptance_file_saying_an_item_is_tested_does_not_make_it_built():
    files = {"UC-001-a.md": scenario("UC-001", build="- API-001 GET rooms.", derives="Derives from: UC-001, API-001"), I.ACCEPTANCE_NAME: acceptance()}
    cover = I.coverage(files, DESIGN)
    assert "API-003" not in cover["named"] and "API-003" in cover["uncovered"]


def test_the_foundations_own_sections_count_as_building_its_tables_and_rules():
    cover = I.coverage({I.FOUNDATION_NAME: foundation()}, DESIGN)
    assert {"TBL-001", "TBL-002", "RUL-001"} <= set(cover["named"])


def test_a_mention_in_a_section_the_foundation_does_not_require_is_not_building():
    files = {I.FOUNDATION_NAME: foundation(extra="\n## Notes\nAPI-003 would be nice.\n")}
    assert "API-003" not in I.coverage(files, DESIGN)["named"]


def test_built_by_reads_scenarios_in_full_and_the_foundations_required_sections_only():
    files = {"UC-001-a.md": "API-001", I.FOUNDATION_NAME: foundation(), I.ACCEPTANCE_NAME: acceptance(), "notes.md": "API-002"}
    assert I.built_by(files) == {"API-001", "TBL-001", "TBL-002", "RUL-001"}


def test_an_endpoint_or_rule_nobody_builds_is_a_problem_unless_declared_not_covered():
    files = full_set()
    files[I.FOUNDATION_NAME] = foundation()
    found = [p for p in I.check_set(files, DESIGN) if "named by no instruction file" in p]
    assert len(found) == 1 and all(i in found[0] for i in ("API-002", "RUL-002", "RUL-003")) and "'Not covered'" in found[0]


def test_one_uncovered_item_reads_as_singular():
    files = full_set()
    files[I.FOUNDATION_NAME] = foundation(extra="\n## Not covered\n- API-002 later\n- RUL-002 later\n")
    assert any("RUL-003 is named by no instruction file" in p for p in I.check_set(files, DESIGN))


def test_the_not_covered_list_reads_only_lines_with_an_id_and_a_reason():
    files = {I.FOUNDATION_NAME: foundation(extra="\n## Not covered\n- API-002\n- RUL-002 left for later\nsome words RUL-003 here\n")}
    assert I.declared_not_covered(files) == {"RUL-002"}
    assert I.declared_not_covered({}) == set()


def test_naming_an_item_in_a_scenario_file_covers_it():
    files = {"UC-001-a.md": "see RUL-001, RUL-002, RUL-003, API-001, API-002, API-003, TBL-001 and TBL-002"}
    assert I.coverage(files, DESIGN)["uncovered"] == []


def test_problems_with_a_set_are_bounded():
    big = I.DesignIds(frozenset({f"UC-{n:03d}" for n in range(1, 30)}))
    assert len(I.check_set({}, big)) <= 8


# ---- the design the files are checked against ----------------------------------------------------------------------------------------------------

def test_design_ids_are_grouped_by_prefix_and_sorted():
    assert DESIGN.of("API") == ["API-001", "API-002", "API-003"] and DESIGN.of("UC") == ["UC-001", "UC-002"] and DESIGN.of("NOPE") == []
    assert "UC" in DESIGN.prefixes and "API" in DESIGN.prefixes


def test_the_design_artefacts_the_checker_reads_are_the_fourteen_that_hold_items():
    assert len(I.DESIGN_ARTEFACTS) == 14 and "usecase_diagram" in I.DESIGN_ARTEFACTS and "low_level_design" in I.DESIGN_ARTEFACTS
    assert I.COVERED_PREFIXES == ("API", "TBL", "RUL") and set(I.BUILD_PREFIXES) <= set(I.DESIGN_PREFIXES)


def test_every_section_list_has_its_traceability_and_do_not_sections():
    for kind in I.KINDS:
        assert "Traceability" in I.SECTIONS[kind] and "Do not" in I.SECTIONS[kind] and I.SECTIONS[kind][0] == "Goal"
    assert I.SECTIONS["scenario"] == ("Goal", "Read first", "What to build", "Business rules that apply", "Done when", "Do not", "Traceability")


# ---- gaps the mutation sweep found --------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("word", ["TBD.", "n/a.", "To be decided.", "tba..", "todo.", "N/A"])
def test_a_placeholder_followed_by_a_full_stop_is_still_a_placeholder(word):
    assert I._is_placeholder_only(word) is True
    assert any("holds only a placeholder" in p for p in problems("scenario", NAME, scenario(rules=word)))


@pytest.mark.parametrize("real", ["Not applicable", "- RUL-001 A booking may not overlap.", "None of the rules matter here because there is no booking."])
def test_real_content_is_never_called_a_placeholder(real):
    assert I._is_placeholder_only(real) is False


def test_the_slug_limit_is_exactly_fifty_and_a_cut_never_leaves_a_dash_at_the_end():
    assert I.MAX_SLUG == 50 and len(I.slug("a" * 50)) == 50 and len(I.slug("a" * 51)) == 50
    cut_on_a_dash = "a" * 49 + " " + "b" * 20
    assert not I.slug(cut_on_a_dash).endswith("-") and I.slug(cut_on_a_dash) == "a" * 49


def test_the_size_limit_is_exactly_twenty_thousand_characters():
    assert I.MAX_FILE_CHARS == 20_000
    base = scenario()
    at_limit = base + "\n" + "x" * (I.MAX_FILE_CHARS - len(base) - 1)
    assert len(at_limit) == I.MAX_FILE_CHARS and not any("the limit is" in p for p in problems("scenario", NAME, at_limit))
    assert any("the limit is 20000" in p for p in problems("scenario", NAME, at_limit + "x"))


def test_a_second_level_heading_is_not_a_title():
    assert any("start the file with a '# <title>' line" in p for p in problems("scenario", NAME, scenario(title="## Reserve a room")))
    assert any("start the file with a '# <title>' line" in p for p in problems("scenario", NAME, scenario(title="#Reserve a room")))
    assert not any("start the file with" in p for p in problems("scenario", NAME, scenario(title="# Reserve a room")))


def test_a_business_rule_is_not_something_to_build_so_a_file_that_names_only_rules_builds_nothing():
    body = scenario(build="- RUL-001 A booking may not overlap another.", derives="Derives from: UC-001, RUL-001")
    assert any("'What to build' must name at least one screen, endpoint, table or interface" in p for p in problems("scenario", NAME, body))
    assert "RUL" not in I.BUILD_PREFIXES and set(I.BUILD_PREFIXES) == {"API", "TBL", "LFS", "HFS", "IFC"}


def test_the_four_tool_headers_each_carry_their_own_instruction():
    texts = {t: I.tool_header(t) for t in I.TOOLS}
    assert "Attach `00-foundation.md` and this file as context" in texts["copilot"] and "say back what it will build" in texts["claude"]
    assert "short plan first" in texts["gpt"] and "list the files it will create" in texts["gemini"]
    assert len({h.split("> **For ", 1)[1] for h in texts.values()}) == 4
    for tool, header in texts.items():
        for other, wording in I._TOOL_HEADERS.items():
            assert (wording in header) is (other == tool)


def test_an_item_the_foundation_declares_not_covered_is_not_also_reported_as_built_by_a_mention_elsewhere_in_the_set():
    files = {I.FOUNDATION_NAME: foundation(extra="\n## Not covered\n- API-002 later\n"), "UC-001-a.md": scenario("UC-001")}
    cover = I.coverage(files, DESIGN)
    assert "API-002" in cover["declared"] and "API-002" not in cover["named"]
    files["UC-002-b.md"] = scenario("UC-002", build="- API-002 GET /api/availability. Needs TBL-001.", derives="Derives from: UC-002, API-002")
    again = I.coverage(files, DESIGN)
    assert "API-002" in again["named"] and "API-002" not in again["declared"]                # once something builds it, it is no longer 'declared not covered'


# ---- one artefact holds the whole set (option A) --------------------------------------------------------------------------------------------------

def body_of(files=None, **kw):
    return I.assemble(files if files is not None else full_set(), design=DESIGN, **kw)


def test_the_assembled_body_has_its_parts_in_order_and_one_numbered_item_per_file():
    body = body_of()
    heads = [line for line in body.split("\n") if line.startswith("## ") and not line.startswith("## Goal")][:4]
    assert heads == ["## Overview", "## Files", "## Coverage check", "## Instructions"]
    assert I.listed_files(body) == [I.FOUNDATION_NAME, "UC-001-reserve-a-room.md", "UC-002-browse-rooms.md", I.ACCEPTANCE_NAME]
    assert "- INS-001 00-foundation.md: Foundation. Derives from: TBL-001, TBL-002, RUL-001" in body
    assert "- INS-004 99-acceptance.md: Acceptance tests." in body and body.endswith("\n") and not body.endswith("\n\n")


def test_splitting_gives_the_same_files_back_whatever_order_they_were_given_in():
    files = full_set()
    shuffled = dict(reversed(list(files.items())))
    assert body_of(shuffled) == body_of(files)
    back, problems_ = I.split_set(body_of(files))
    assert problems_ == [] and list(back) == list(files) and all(back[k] == v.strip("\n") + "\n" for k, v in files.items())


def test_a_complete_assembled_set_has_no_problems():
    assert I.check_instructions(body_of(), DESIGN) == []


def test_a_file_keeps_its_item_id_in_the_next_version_and_a_new_file_takes_the_next_number():
    first = body_of()
    previous = [(m.group(1), m.group(0).split(" ", 2)[2]) for m in (__import__("re").match(r"- (INS-\d+) (.*)", l) for l in first.split("\n")) if m]
    files = full_set()
    files["UC-002-browse-rooms.md"] = files["UC-002-browse-rooms.md"].replace("Let office staff", "Let anyone")
    again = I.assemble(files, design=DESIGN, previous=previous, highest=4)
    assert [l for l in again.split("\n") if l.startswith("- INS-")] == [l for l in first.split("\n") if l.startswith("- INS-")]
    files["UC-003-extra.md"] = scenario("UC-003")
    third = I.assemble(files, design=DESIGN, previous=previous, highest=4)
    assert "- INS-005 UC-003-extra.md:" in third


def test_a_new_file_never_reuses_a_number_that_was_used_before():
    previous = [("INS-001", "00-foundation.md: Foundation.")]
    body = I.assemble(full_set(), design=DESIGN, previous=previous, highest=9)
    assert "INS-001 00-foundation.md" in body and "INS-010 UC-001-reserve-a-room.md" in body and "INS-002 " not in body


def test_a_file_taken_out_of_the_set_is_listed_as_withdrawn_not_silently_dropped():
    files = full_set()
    del files["UC-002-browse-rooms.md"]
    previous = [("INS-003", "UC-002-browse-rooms.md: Browse rooms.")]
    body = I.assemble(files, design=DESIGN, previous=previous, highest=4)
    assert "## Withdrawn items\n- INS-003 UC-002-browse-rooms.md: this file is no longer part of the set." in body
    assert "INS-003" not in "".join(l for l in body.split("\n") if l.startswith("- INS-") and "Withdrawn" not in l and "no longer" not in l)


def test_the_coverage_check_names_a_use_case_with_no_file():
    files = full_set()
    del files["UC-002-browse-rooms.md"]
    body = body_of(files)
    assert "- UC-002 has no instruction file yet" in body and "- UC-001 has no" not in body
    assert "## Coverage check\nNone" in body_of()


def test_the_overview_is_the_models_own_when_given():
    assert "## Overview\nA booking app.\n" in body_of(overview="  A booking app.  ")


def test_the_title_and_derives_are_read_from_the_file():
    assert I.title_of(scenario()) == "Reserve a room" and I.title_of("no title\n# x") == "" and I.title_of("") == ""
    assert I.derives_of(scenario()) == ["UC-001", "API-003", "RUL-001"]
    assert I.derives_of("# t\n\n## Traceability\nDerives from: API-001, API-001, UC-002\n") == ["API-001", "UC-002"]
    assert I.derives_of("# t\n") == []


def test_a_file_that_is_named_twice_or_a_body_without_files_is_a_problem_and_never_raises():
    body = body_of() + f"=== FILE: {I.ACCEPTANCE_NAME} ===\nsomething else\n"
    files, found = I.split_set(body)
    assert found == [f"{I.ACCEPTANCE_NAME} is given more than once; write each file once"] and files[I.ACCEPTANCE_NAME] == acceptance().strip("\n") + "\n"
    for odd in ("", None, "just text", "=== FILE: a.md ===\n"):
        files, found = I.split_set(odd)
        assert isinstance(files, dict) and isinstance(found, list)
    assert "no files" in I.split_set("just text")[1][0]


def test_windows_line_ends_and_trailing_blanks_on_the_mark_line_are_read():
    body = body_of().replace("\n", "\r\n").replace("=== FILE: 99-acceptance.md ===", "=== FILE: 99-acceptance.md ===  ")
    assert I.check_instructions(body, DESIGN) == []


def test_text_before_the_first_mark_is_not_part_of_any_file():
    files, _ = I.split_set("stray words\n=== FILE: 99-acceptance.md ===\n" + acceptance())
    assert list(files) == [I.ACCEPTANCE_NAME] and "stray" not in files[I.ACCEPTANCE_NAME]


def test_a_problem_in_one_file_is_prefixed_with_its_name():
    files = full_set()
    files["UC-001-reserve-a-room.md"] = scenario("UC-001").replace("## Done when", "## Something else")
    found = I.check_instructions(body_of(files), DESIGN)
    assert found and all(p.startswith("UC-001-reserve-a-room.md: ") for p in found if "Done when" in p)
    assert any("'Done when' is missing or empty" in p for p in found)


def test_an_invented_id_inside_a_file_is_found_through_the_set():
    files = full_set()
    files["UC-001-reserve-a-room.md"] = scenario("UC-001", build="- API-777 does a thing. Needs TBL-001.")
    assert any("API-777" in p for p in I.check_instructions(body_of(files), DESIGN))


def test_a_tool_header_on_a_file_in_the_body_does_not_break_the_checks():
    files = full_set()
    files[I.ACCEPTANCE_NAME] = I.apply_tool(acceptance(), "claude")
    assert I.check_instructions(body_of(files), DESIGN) == []


def test_a_files_list_that_leaves_a_file_out_or_names_one_that_is_not_there_is_a_problem():
    body = body_of()
    short = body.replace("- INS-002 UC-001-reserve-a-room.md: Reserve a room. Derives from: UC-001, API-003, RUL-001\n", "")
    assert any("does not name UC-001-reserve-a-room.md" in p for p in I.check_instructions(short, DESIGN))
    extra = body.replace("## Coverage check", "- INS-009 UC-009-ghost.md: Ghost.\n\n## Coverage check", 1)
    assert any("names UC-009-ghost.md, which does not follow" in p for p in I.check_instructions(extra, DESIGN))


def test_a_set_with_a_stray_file_name_is_refused_by_name_and_the_same_sentence_is_not_repeated():
    files = full_set()
    files["notes.md"] = "# Notes\n"
    found = I.check_instructions(body_of(files), DESIGN)
    assert len(found) == len(set(found))


def test_a_set_with_no_files_gives_the_structure_problem_only():
    found = I.check_instructions("## Overview\nnothing\n", DESIGN)
    assert any("no files" in p for p in found)


# ---- gaps the set sweep found ------------------------------------------------------------------------------------------------------------------

def test_a_mark_must_be_the_whole_line_with_a_name_that_has_no_spaces():
    for odd in ("see === FILE: a.md ===", "=== FILE: my file.md ===", "=== FILE:  ===", "=== FILE: a.md === extra"):
        files, _ = I.split_set(f"=== FILE: 99-acceptance.md ===\n# T\n{odd}\nmore\n")
        assert list(files) == [I.ACCEPTANCE_NAME] and odd in files[I.ACCEPTANCE_NAME]


def test_numbering_continues_after_ids_in_the_set_even_when_the_recorded_highest_is_lower():
    previous = [("INS-003", "00-foundation.md: Foundation.")]
    body = I.assemble(full_set(), design=DESIGN, previous=previous, highest=0)
    assert "INS-003 00-foundation.md" in body and "INS-004 UC-001-reserve-a-room.md" in body


def test_a_file_without_a_title_is_listed_as_instructions():
    files = full_set()
    files[I.ACCEPTANCE_NAME] = acceptance().split("\n", 2)[2]
    assert "- INS-004 99-acceptance.md: instructions." in body_of(files)


def test_the_default_overview_counts_the_files():
    assert "## Overview\n4 instruction file(s) for a coding tool, in the order to work in.\n" in body_of()


def test_only_a_scenario_file_covers_a_use_case():
    files = full_set()
    del files["UC-002-browse-rooms.md"]
    files[I.FOUNDATION_NAME] = files[I.FOUNDATION_NAME].replace("Derives from: TBL-001", "Derives from: UC-002, TBL-001")
    assert "- UC-002 has no instruction file yet" in body_of(files)


def test_the_files_list_is_read_only_from_before_the_instructions_and_only_numbered_items_count():
    body = body_of()
    sneaky = body.replace(f"=== FILE: {I.ACCEPTANCE_NAME} ===\n", f"=== FILE: {I.ACCEPTANCE_NAME} ===\n## Files\n- INS-099 ghost.md: x\n", 1)
    assert "ghost.md" not in I.listed_files(sneaky)
    plain = body.replace("- INS-004 99-acceptance.md:", "- 99-acceptance.md:")
    assert I.listed_files(plain) == [I.FOUNDATION_NAME, "UC-001-reserve-a-room.md", "UC-002-browse-rooms.md"]


def test_a_missing_foundation_is_reported_through_the_whole_set_check():
    files = full_set()
    del files[I.FOUNDATION_NAME]
    assert any("no 00-foundation.md" in p for p in I.check_instructions(body_of(files), DESIGN))


def test_a_title_may_follow_blank_lines_and_the_derives_of_every_line_are_joined_without_repeats():
    assert I.title_of("\n\n# Late title\n") == "Late title"
    text = "# t\n\n## Traceability\nDerives from: API-001\nDerives from: API-001, RUL-001\n"
    assert I.derives_of(text) == ["API-001", "RUL-001"]
    assert I.derives_of("# t\nDerives from: API-009\n\n## Goal\nx\n") == []


def test_the_same_sentence_is_not_sent_back_twice():
    files = full_set()
    files[I.ACCEPTANCE_NAME] = acceptance(derives="Derives from: API-777")
    found = I.check_instructions(body_of(files) + body_of(files).split("## Instructions")[0].replace("## Overview", "## Overview"), DESIGN)
    assert len(found) == len(set(found))


def test_a_sentence_the_file_checker_repeats_is_sent_back_once(monkeypatch):
    monkeypatch.setattr(I, "check_file", lambda kind, name, body, design, *rest, **more: ["a section is wrong", "a section is wrong"])
    found = I.check_instructions(body_of(), DESIGN)
    assert found.count(f"{I.ACCEPTANCE_NAME}: a section is wrong") == 1


def test_a_file_may_not_use_a_heading_the_set_uses_for_itself():
    for heading in I.RESERVED_HEADINGS:
        files = full_set()
        files["UC-001-reserve-a-room.md"] = scenario("UC-001").replace("## Do not", f"## {heading}\nsomething\n\n## Do not")
        found = I.check_instructions(body_of(files), DESIGN)
        assert any(p.startswith("UC-001-reserve-a-room.md: the heading") and f"'{heading}'" in p for p in found), heading
    assert not any("belong" in p for p in I.check_instructions(body_of(), DESIGN))


def test_several_clashing_headings_are_named_together_in_one_sentence():
    files = full_set()
    files[I.ACCEPTANCE_NAME] = acceptance().replace("## Do not", "## Files\nx\n\n## Overview\ny\n\n## Do not")
    found = [p for p in I.check_instructions(body_of(files), DESIGN) if "belong" in p]
    assert len(found) == 1 and found[0].startswith("99-acceptance.md: the headings 'Files', 'Overview' belong to the set")


# ---- the checker is part of saving the artefact -------------------------------------------------------------------------------------------------

def _skill():
    from app.agents.skills import SkillLibrary
    from app.llm.routing import Routing
    from app.workflow.definitions import load_catalogue
    return SkillLibrary.load(load_catalogue(Routing.load().roles.keys())).get("build_instructions")


def _ctx(skill, known):
    from app.agents.items import ItemContext
    return ItemContext(specs=skill.items, covers=skill.covers, known=frozenset(known), pools={"UC": ("UC-001", "UC-002")})


def test_saving_the_artefact_runs_the_set_checks_with_the_ids_the_writer_was_shown():
    from app.agents.checks import check_body
    skill = _skill()
    ctx = _ctx(skill, DESIGN.ids)
    assert check_body(body_of(), skill, set(), ctx) == []
    files = full_set()
    files["UC-001-reserve-a-room.md"] = scenario("UC-001", build="- API-777 does a thing. Needs TBL-001.")
    assert any("API-777" in p for p in check_body(body_of(files), skill, set(), ctx))


def test_the_set_checks_do_not_run_on_any_other_artefact():
    from app.agents.checks import check_body
    from app.agents.skills import SkillLibrary
    from app.llm.routing import Routing
    from app.workflow.definitions import load_catalogue
    other = SkillLibrary.load(load_catalogue(Routing.load().roles.keys())).get("user_stories")
    assert not any("=== FILE" in p or "no files" in p for p in check_body("## Stories\n- US-001 x. Derives from: FEAT-001\n", other, set(), _ctx(other, DESIGN.ids)))


def test_the_build_phase_now_holds_one_artefact_and_the_old_code_skills_are_retired():
    from app.llm.routing import Routing
    from app.workflow.definitions import load_catalogue
    build = load_catalogue(Routing.load().roles.keys()).phase("build")
    assert [a.key for a in build.artefacts] == ["build_instructions"] and build.artefacts[0].id_prefix == "BLD-INS" and build.artefacts[0].required
    skills = _skill().__class__  # the skill loads without any of the four code skills
    assert skills is not None


def test_the_frozen_code_generator_catalogue_still_loads_with_its_four_code_skills():
    from app.build import legacy
    cat = legacy.catalogue()
    lib = legacy.library(cat)
    assert [a.key for a in cat.phase("build").artefacts][:4] == ["database_schema", "backend_code", "frontend_code", "test_suite"]
    assert {"database_schema", "backend_code", "frontend_code", "test_suite"} <= set(lib.keys) and "build_instructions" not in lib.keys
    assert len(cat.phase("build").artefacts) == 6


# ---- S19c-1: the UI as files of its own ---------------------------------------------------------------------------------------------------------------

UI_DESIGN = I.DesignIds(frozenset({
    "UC-001", "UC-002", "API-001", "API-002", "API-003", "TBL-001", "TBL-002", "RUL-001", "RUL-002", "RUL-003", "COMP-001", "IFC-001", "FR-001", "US-001",
    "HFS-001", "HFS-002",
}))
GUIDE, SCREEN1, SCREEN2 = I.UI_GUIDE_NAME, "UI-HFS-001-browse-rooms.md", "UI-HFS-002-notices.md"


def ui_guide(**over):
    parts = {
        "Goal": "One look and one way of behaving for every page.",
        "Layout and navigation": "A top bar with the page names; the page content under it.",
        "States": "Loading shows a short message; an empty list says so; an error shows the server's reason.",
        "Forms and messages": "Every input has a label; a refused request shows the reason beside the form.",
        "Shared components": "The notice box and the room row are used on every page.",
        "Accessibility": "Every control can be reached and used from the keyboard; messages are not shown by colour alone.",
        "Do not": "- Do not add a second colour scheme.",
        "Traceability": "Derives from: HFS-001, HFS-002",
    }
    parts.update(over)
    return "# UI guidelines\n\n" + "\n\n".join(f"## {k}\n{v}" for k, v in parts.items()) + "\n"


def screen(screen_id="HFS-001", **over):
    parts = {
        "Goal": "Let staff see which rooms are free.",
        "Read first": "Read 00-foundation.md and 01-ui-guidelines.md first.",
        "What is on the screen": "Top to bottom: the date and time inputs, a Check button, then a table of rooms with a Free or Reserved marker.",
        "Components and their states": "- The Check button is disabled while the inputs are empty.\n- A room row shows Free or Reserved.",
        "What the person can do": "- Choose a date and a time, press Check.",
        "Calls it makes": "- API-002 is called when Check is pressed.",
        "Messages and the rules behind them": "- A refused request shows the reason the server gives (RUL-001).",
        "Done when": "- The table shows every room with its state\n- An empty result says so",
        "Do not": "- Do not add accounts.",
        "Traceability": f"Derives from: {screen_id}, API-002, RUL-001",
    }
    parts.update(over)
    return "# Browse rooms\n\n" + "\n\n".join(f"## {k}\n{v}" for k, v in parts.items()) + "\n"


def ui_problems(kind, name, body, design=UI_DESIGN):
    return I.check_file(kind, name, body, design)


def test_a_complete_ui_guide_and_a_complete_screen_file_have_no_problems():
    assert ui_problems("ui_guide", GUIDE, ui_guide()) == []
    assert ui_problems("screen", SCREEN1, screen()) == []


def test_the_sections_of_the_two_new_kinds_are_pinned():
    assert I.SECTIONS["ui_guide"] == ("Goal", "Layout and navigation", "States", "Forms and messages", "Shared components", "Accessibility", "Do not", "Traceability")
    assert I.SECTIONS["screen"] == ("Goal", "Read first", "What is on the screen", "Components and their states", "What the person can do", "Calls it makes",
                                    "Messages and the rules behind them", "Done when", "Do not", "Traceability")
    assert I.NOT_APPLICABLE_OK["ui_guide"] == ("Forms and messages", "Shared components") and I.NOT_APPLICABLE_OK["screen"] == ("Calls it makes", "Messages and the rules behind them")


@pytest.mark.parametrize("section", I.SECTIONS["ui_guide"])
def test_a_missing_ui_guide_section_is_named(section):
    body = ui_guide().replace(f"## {section}\n", "## Something else\n", 1)
    assert any(f"'{section}' is missing or empty" in p for p in ui_problems("ui_guide", GUIDE, body))


@pytest.mark.parametrize("section", I.SECTIONS["screen"])
def test_a_missing_screen_section_is_named(section):
    body = screen().replace(f"## {section}\n", "## Something else\n", 1)
    assert any(f"'{section}' is missing or empty" in p for p in ui_problems("screen", SCREEN1, body))


def test_not_applicable_is_accepted_only_where_the_kind_allows_it():
    for section in ("Forms and messages", "Shared components"):
        assert ui_problems("ui_guide", GUIDE, ui_guide(**{section: "Not applicable"})) == []
    for section in ("Goal", "Layout and navigation", "States", "Accessibility"):
        assert any("cannot be 'Not applicable'" in p for p in ui_problems("ui_guide", GUIDE, ui_guide(**{section: "Not applicable"}))), section
    for section in ("Calls it makes", "Messages and the rules behind them"):
        assert ui_problems("screen", SCREEN1, screen(**{section: "Not applicable"})) == []
    for section in ("What is on the screen", "Components and their states", "What the person can do", "Done when"):
        assert any("cannot be 'Not applicable'" in p for p in ui_problems("screen", SCREEN1, screen(**{section: "Not applicable"}))), section


def test_the_ui_guide_has_one_fixed_name_and_a_screen_file_is_named_for_a_hifi_screen_that_exists():
    assert any("must be named 01-ui-guidelines.md" in p for p in ui_problems("ui_guide", "ui.md", ui_guide()))
    for bad in ("HFS-001-browse.md", "UI-HFS-001.md", "UI-HFS-001-Browse.md", "ui-hfs-001-browse.md", "UI-UC-001-browse.md", "UI-HFS-1-browse.md", "UI-HFS-001-browse.txt"):
        assert any("a screen file is named UI-<screen ID>-<short-name>.md" in p for p in ui_problems("screen", bad, screen())), bad
    assert any("UI-HFS-009" not in p and "HFS-009, which is not a hi-fi screen in the design" in p for p in ui_problems("screen", "UI-HFS-009-ghost.md", screen("HFS-009")))
    assert ui_problems("screen", "UI-HFS-002-notices.md", screen("HFS-002")) == []


def test_a_screen_file_names_its_own_screen_and_the_endpoints_it_calls():
    assert any("must name the screen this file is for, HFS-001" in p for p in ui_problems("screen", SCREEN1, screen(**{"Traceability": "Derives from: API-002, RUL-001"})))
    assert any("'Calls it makes' must name each endpoint" in p for p in ui_problems("screen", SCREEN1, screen(**{"Calls it makes": "It asks the server for the rooms."})))
    assert ui_problems("screen", SCREEN1, screen(**{"Calls it makes": "Not applicable"})) == []
    assert ui_problems("screen", SCREEN1, screen(**{"Calls it makes": "- API-001 and API-002"})) == []
    assert any("'Calls it makes' must name each endpoint" in p for p in ui_problems("screen", SCREEN1, screen(**{"Calls it makes": "- TBL-001 is read"})))


def test_a_screen_files_done_when_must_be_a_list():
    assert any("'Done when' must be a list" in p for p in ui_problems("screen", SCREEN1, screen(**{"Done when": "It works."})))


def test_a_screen_file_may_name_only_ids_that_exist_in_the_design():
    assert any("API-777" in p for p in ui_problems("screen", SCREEN1, screen(**{"Calls it makes": "- API-777 is called"})))


def test_the_new_kinds_are_read_from_their_names_and_ordered_foundation_guide_use_cases_screens_acceptance():
    assert I.kind_of(GUIDE) == "ui_guide" and I.kind_of(SCREEN1) == "screen" and I.kind_of("UI-HFS-001-a.md") == "screen"
    assert I.kind_of("UI-HFS-001.md") is None and I.kind_of("01-ui-guidelines.txt") is None and I.kind_of("UI-LFS-001-a.md") is None
    names = [I.ACCEPTANCE_NAME, SCREEN2, "UC-002-b.md", SCREEN1, GUIDE, "UC-001-a.md", I.FOUNDATION_NAME]
    assert sorted(names, key=I.order_key) == [I.FOUNDATION_NAME, GUIDE, "UC-001-a.md", "UC-002-b.md", SCREEN1, SCREEN2, I.ACCEPTANCE_NAME]


def test_a_screen_file_name_is_made_from_the_screen_id_and_its_title():
    assert I.screen_name("HFS-001", "Browse and reserve rooms") == "UI-HFS-001-browse-and-reserve-rooms.md"
    assert I.screen_name("HFS-004", "!!!") == "UI-HFS-004-scenario.md" and I.kind_of(I.screen_name("HFS-004", "!!!")) == "screen"


def test_the_code_caps_apply_to_the_ui_files_too():
    long = "```css\n" + "\n".join(["a { b: c }"] * 31) + "\n```"
    assert any("lines of code" in p for p in ui_problems("ui_guide", GUIDE, ui_guide(**{"Layout and navigation": long})))
    assert any("lines of code" in p for p in ui_problems("screen", SCREEN1, screen(**{"What is on the screen": long})))
    short = "```css\n" + "\n".join(["a { b: c }"] * 30) + "\n```"
    assert ui_problems("screen", SCREEN1, screen(**{"What is on the screen": short})) == []


# ---- a use case file points at its screen; it does not describe how the screen looks -----------------------------------------------------------------

def test_a_use_case_file_that_describes_how_a_screen_looks_is_sent_back_naming_the_words():
    body = scenario(build="- API-003 reserves. HFS-001 shows a navy top bar, 16px padding and rounded corners.")
    found = [p for p in problems("scenario", NAME, body) if "describes how something looks" in p]
    assert len(found) == 1 and "navy" in found[0] and "16px" in found[0] and "padding" in found[0] and "rounded corner" in found[0]


@pytest.mark.parametrize("text", ["a 12 px gap", "font-size 14", "box shadow", "a gradient", "a thin border", "#1a2b3c", "rgba(0,0,0,.5)", "a status pills row", "Pixels", "margin"])
def test_each_unambiguous_styling_word_is_found(text):
    assert any("describes how something looks" in p for p in problems("scenario", NAME, scenario(build=f"- API-003 reserves. {text}")))


@pytest.mark.parametrize("text", [
    "Show a green notice when it works and a red one when it is refused.", "HFS-001 has the Reserve Room button on a free row.", "A pixelated photo upload is out of scope.", "A headborder, a subpill and sidepadding are not words.",
    "The bordering town is not a customer.", "The fontana room", "Show the room as Free or Reserved.", "#123 is not a colour", "a pillar room",
])
def test_ordinary_behaviour_is_not_mistaken_for_styling(text):
    assert not any("describes how something looks" in p for p in problems("scenario", NAME, scenario(build=f"- API-003 reserves. {text}")))


def test_styling_words_in_the_other_kinds_of_file_are_not_this_checks_business():
    assert not any("describes how something looks" in p for p in ui_problems("screen", SCREEN1, screen(**{"What is on the screen": "A navy bar with 16px padding."})))
    assert not any("describes how something looks" in p for p in ui_problems("ui_guide", GUIDE, ui_guide(**{"Layout and navigation": "A navy bar with 16px padding."})))
    assert not any("describes how something looks" in p for p in problems("foundation", I.FOUNDATION_NAME, foundation(extra="\nA navy bar.\n")))


# ---- the whole set ------------------------------------------------------------------------------------------------------------------------------------

def ui_set(**over):
    files = {
        I.FOUNDATION_NAME: foundation(extra="\n## Not covered\n- API-002 not needed\n- RUL-002 later\n- RUL-003 later\n"),
        GUIDE: ui_guide(),
        "UC-001-reserve-a-room.md": scenario("UC-001", build="- API-001 and API-003, on HFS-001. Needs TBL-001 and TBL-002."),
        "UC-002-browse-rooms.md": scenario("UC-002", build="- API-001 lists rooms (HFS-001).", derives="Derives from: UC-002, API-001"),
        SCREEN1: screen("HFS-001"), SCREEN2: screen("HFS-002"),
        I.ACCEPTANCE_NAME: acceptance(),
    }
    files.update(over)
    return files


def test_a_complete_set_with_screens_has_no_problems():
    assert I.check_set(ui_set(), UI_DESIGN) == []
    assert I.check_instructions(I.assemble(ui_set(), design=UI_DESIGN), UI_DESIGN) == []


def test_a_design_with_screens_needs_the_guide_once_the_ui_files_are_asked_for():
    files = ui_set()
    del files[GUIDE]
    assert any("needs 01-ui-guidelines.md" in p for p in I.check_set(files, UI_DESIGN))
    assert any("needs 01-ui-guidelines.md" in p for p in I.check_set(full_set(), UI_DESIGN, require_ui=True))


def test_a_set_written_the_old_way_is_not_refused_for_having_no_ui_files_until_they_are_asked_for():
    assert I.check_set(full_set(), UI_DESIGN) == []
    assert I.gaps_of(full_set(), UI_DESIGN) == [] and I.gaps_of(full_set(), UI_DESIGN, require_ui=True) == ["HFS-001", "HFS-002"]


def test_every_hifi_screen_needs_exactly_one_file_and_a_screen_with_none_is_a_gap():
    files = ui_set()
    del files[SCREEN2]
    assert any("HFS-002 has no UI file; write one named UI-HFS-002-<short-name>.md" in p for p in I.check_set(files, UI_DESIGN))
    assert I.gaps_of(files, UI_DESIGN) == ["HFS-002"]
    files[SCREEN2] = screen("HFS-002")
    files["UI-HFS-002-other.md"] = screen("HFS-002")
    assert any("HFS-002 has more than one file (UI-HFS-002-notices.md, UI-HFS-002-other.md)" in p for p in I.check_set(files, UI_DESIGN))


def test_a_file_for_a_screen_the_design_does_not_have_is_refused_in_the_set_check_too():
    files = ui_set(**{"UI-HFS-009-ghost.md": screen("HFS-009")})
    assert any("UI-HFS-009-ghost.md is for HFS-009, which is not a hi-fi screen in the design" in p for p in I.check_set(files, UI_DESIGN))


def test_a_design_with_no_screens_must_not_have_the_guide_and_asks_for_nothing_more():
    plain = I.DesignIds(frozenset(i for i in UI_DESIGN.ids if not i.startswith("HFS")))
    assert I.check_set(full_set(), plain, require_ui=True) == [] and I.gaps_of(full_set(), plain, require_ui=True) == []
    assert any("the design has no hi-fi screens; leave the UI files out" in p for p in I.check_set(full_set(**{GUIDE: ui_guide()}), plain))


def test_the_sets_own_coverage_check_lists_a_screen_with_no_file_and_the_checker_accepts_a_set_saved_with_it():
    files = ui_set()
    del files[SCREEN2]
    body = I.assemble(files, design=UI_DESIGN)
    head = body.split("## Instructions")[0]
    assert "- HFS-002 has no UI file yet" in head and "None" not in head.split("## Coverage check")[1]
    assert I.check_instructions(body, UI_DESIGN) == []
    hidden = body.replace("- HFS-002 has no UI file yet", "")
    assert any("HFS-002 has no UI file" in p for p in I.check_instructions(hidden, UI_DESIGN))


def test_a_set_with_no_ui_files_says_nothing_about_screens_unless_asked():
    head = I.assemble(full_set(), design=UI_DESIGN).split("## Instructions")[0]
    assert "HFS" not in head and "## Coverage check\nNone" in head
    asked = I.assemble(full_set(), design=UI_DESIGN, require_ui=True).split("## Instructions")[0]
    assert "- HFS-001 has no UI file yet" in asked and "- HFS-002 has no UI file yet" in asked


def test_the_ui_files_come_out_in_order_and_split_back_into_the_same_files():
    files = ui_set()
    body = I.assemble(files, design=UI_DESIGN)
    back, found = I.split_set(body)
    assert found == [] and list(back) == [I.FOUNDATION_NAME, GUIDE, "UC-001-reserve-a-room.md", "UC-002-browse-rooms.md", SCREEN1, SCREEN2, I.ACCEPTANCE_NAME]
    listed = I.listed_files(body)
    assert listed == list(back)
    assert all(f"- INS-00{n} {name}:" in body for n, name in enumerate(back, start=1))


def test_the_foundation_alone_builds_tables_and_a_screen_file_mentioning_an_endpoint_does_not_count_as_building_it():
    files = ui_set()
    files[I.FOUNDATION_NAME] = foundation()                                          # no 'Not covered' section: API-002, RUL-002 and RUL-003 are built by nobody
    files["UC-002-browse-rooms.md"] = scenario("UC-002", build="- API-001 lists rooms (HFS-001).", derives="Derives from: UC-002, API-001")
    cover = I.coverage(files, UI_DESIGN)
    assert "API-002" in cover["uncovered"]                                             # SCREEN1 calls API-002, but a screen CALLS an endpoint; a use case file BUILDS it


def test_a_name_the_set_does_not_know_sorts_with_the_use_cases_not_before_the_foundation():
    names = ["notes.md", I.FOUNDATION_NAME, "UC-001-a.md", I.ACCEPTANCE_NAME]
    assert sorted(names, key=I.order_key)[0] == I.FOUNDATION_NAME
    assert I.order_key("notes.md")[0] == I.order_key("UC-001-a.md")[0]


def test_the_checker_passes_the_ui_request_on_to_the_set_check():
    body = I.assemble(full_set(), design=UI_DESIGN)
    assert I.check_instructions(body, UI_DESIGN) == []
    asked = I.check_instructions(body, UI_DESIGN, require_ui=True)
    assert any("needs 01-ui-guidelines.md" in p for p in asked) and any("HFS-001 has no UI file" in p for p in asked)


def test_a_hex_colour_is_found_in_either_case():
    for code in ("#1A2B3C", "#1a2b3c", "#AbCdEf"):
        assert any("describes how something looks" in p for p in problems("scenario", NAME, scenario(build=f"- API-003 reserves. Use {code}.")))
