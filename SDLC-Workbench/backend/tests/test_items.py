"""Numbered items inside an artefact: reading them leniently, checking them strictly, and what the checks say."""
from __future__ import annotations

import pytest

from app.agents.items import (
    Item,
    ItemContext,
    check_items,
    format_id,
    history_of,
    parse_items,
    split_id,
    upstream_pool,
)
from app.agents.skills import ItemSpec

FR = (ItemSpec("FR", "Requirements"),)
EPICS = (ItemSpec("EPIC", "Epics"), ItemSpec("FEAT", "Features"))


def fr_body(*lines: str, extra: str = "") -> str:
    return "## Overview\nText.\n## Requirements\n" + "\n".join(lines) + "\n" + extra


def ctx(specs=FR, **kw) -> ItemContext:
    kw.setdefault("known", frozenset({"PER-001", "PER-002", "REQ-PRB-001"}))
    return ItemContext(specs=specs, **kw)


GOOD = fr_body(
    "- FR-001 The system shall refuse a double booking. Derives from: PER-001, REQ-PRB-001",
    "- FR-002 The system shall let an administrator retire a room. Derives from: PER-002",
)


# ---- reading --------------------------------------------------------------------------------------------------

def test_items_are_read_with_their_id_text_and_derives_from():
    [a, b] = parse_items(GOOD, FR).items
    assert (a.id, a.section, a.derives, a.has_source) == ("FR-001", "Requirements", ("PER-001", "REQ-PRB-001"), True)
    assert a.text.startswith("The system shall refuse a double booking.")
    assert (b.id, b.derives) == ("FR-002", ("PER-002",))


@pytest.mark.parametrize("line", [
    "- FR-001 text. Derives from: PER-001",
    "* FR-001 text. Derives from: PER-001",
    "+ FR-001 text. Derives from: PER-001",
    "1. FR-001 text. Derives from: PER-001",
    "2) FR-001 text. Derives from: PER-001",
    "- **FR-001** text. Derives from: PER-001",
    "- FR-001: text. Derives from: PER-001",
    "- FR-001 - text. Derives from: PER-001",
    "- FR-001 text. DERIVES FROM: PER-001",
    "- FR-001 text. derives from : PER-001",
])
def test_the_usual_ways_a_model_formats_a_list_line_are_all_read(line):
    [item] = parse_items(fr_body(line), FR).items
    assert item.id == "FR-001" and item.derives == ("PER-001",), line


def test_a_wrapped_line_is_one_item_and_its_derives_from_is_found_on_the_second_line():
    body = fr_body("- FR-001 The system shall refuse a double booking for the same slot,", "  whatever the person's role. Derives from: PER-001")
    [item] = parse_items(body, FR).items
    assert item.derives == ("PER-001",) and "whatever the person's role" in item.text


def test_a_nested_bullet_belongs_to_the_item_above_and_is_not_an_item_or_a_stray_entry():
    body = fr_body("- FR-001 First. Derives from: PER-001", "  - a nested criterion that mentions FR-009", "- FR-002 Second. Derives from: PER-001")
    parsed = parse_items(body, FR)
    assert parsed.ids == ("FR-001", "FR-002") and parsed.stray == () and parsed.misplaced == ()
    assert parsed.items[0].derives == ("PER-001",)  # the nested line's FR-009 is not read into the item above


def test_a_derives_from_in_a_nested_line_is_not_taken_for_the_parents():
    body = fr_body("- FR-001 First, no source here.", "  - Derives from: PER-001")
    [item] = parse_items(body, FR).items
    assert item.has_source is False and item.derives == ()


def test_ids_in_prose_code_fences_and_other_sections_are_not_items():
    body = ("## Overview\n- FR-050 in the overview.\n## Requirements\nFR-051 is mentioned in a sentence.\n"
            "```\n- FR-052 inside a fence\n```\n- FR-001 Real. Derives from: PER-001\n## Business rules\n- FR-053 elsewhere\n")
    assert parse_items(body, FR).ids == ("FR-001",)


def test_a_list_entry_with_no_id_is_reported_as_stray_with_a_snippet():
    parsed = parse_items(fr_body("- The system shall do something. Derives from: PER-001"), FR)
    assert parsed.items == () and parsed.stray == (("Requirements", "The system shall do something. Derives from: PER-001"),)


def test_an_id_with_the_wrong_prefix_for_its_section_is_misplaced_not_an_item():
    parsed = parse_items(fr_body("- NFR-001 wrong place. Derives from: PER-001"), FR)
    assert parsed.items == () and parsed.misplaced == (("NFR-001", "Requirements"),)


def test_two_prefixes_in_two_sections_are_each_read_from_their_own_section():
    body = "## Epics\n- EPIC-001 One. Derives from: PER-001\n## Features\n- FEAT-001 Two. Derives from: EPIC-001\n- EPIC-002 wrong\n"
    parsed = parse_items(body, EPICS)
    assert parsed.ids == ("EPIC-001", "FEAT-001") and parsed.misplaced == (("EPIC-002", "Features"),)


def test_section_names_are_matched_loosely_and_a_repeated_section_is_read_in_full():
    body = "## requirements:\n- FR-001 a. Derives from: PER-001\n## Other\nx\n## REQUIREMENTS\n- FR-002 b. Derives from: PER-001\n"
    assert parse_items(body, FR).ids == ("FR-001", "FR-002")


def test_an_artefact_with_no_item_specs_has_no_items_whatever_it_contains():
    assert parse_items(GOOD, ()).items == ()


def test_derives_from_stops_at_the_end_of_the_sentence_and_ignores_brackets():
    [item] = parse_items(fr_body("- FR-001 text. Derives from: PER-001, PER-002. See also PER-009 [DOC-001#1]"), FR).items
    assert item.derives == ("PER-001", "PER-002")


def test_a_bracketed_source_alone_counts_as_a_source_but_is_not_a_derives_target():
    [item] = parse_items(fr_body("- FR-001 text. Derives from: [DOC-001#2]"), FR).items
    assert item.has_source is True and item.derives == ()


def test_an_unbracketed_document_source_is_a_source_but_never_a_link():
    [item] = parse_items(fr_body("- FR-001 text. Derives from: DOC-001#2, MEM-003, PER-001"), FR).items
    assert item.derives == ("DOC-001#2", "MEM-003", "PER-001") and item.link_targets == ("PER-001",)


def test_a_repeated_target_is_listed_once():
    [item] = parse_items(fr_body("- FR-001 t. Derives from: PER-001, PER-001, PER-002"), FR).items
    assert item.derives == ("PER-001", "PER-002")


def test_withdrawn_ids_are_read_from_their_section_and_only_with_the_right_prefix():
    body = GOOD + "## Withdrawn items\n- FR-007 no longer needed\n- NFR-001 not ours\n- not an id\n"
    assert parse_items(body, FR).withdrawn == ("FR-007",)


def test_id_helpers_round_trip():
    assert split_id("REQ-F-012") == ("REQ-F", 12) and format_id("FR", 7) == "FR-007" and format_id("FR", 1234) == "FR-1234"


# ---- checking: one test per rule -------------------------------------------------------------------------------------

def problems(body, context=None):
    return check_items(body, context or ctx())


def test_a_well_formed_first_draft_has_no_problems():
    assert problems(GOOD) == []


def test_an_item_in_the_wrong_section_is_named_with_the_prefix_that_belongs():
    out = problems(fr_body("- NFR-001 x. Derives from: PER-001", "- FR-001 y. Derives from: PER-001"))
    assert out == ["NFR-001 is under 'Requirements', where items must start with FR-"]


def test_a_list_entry_without_an_id_tells_the_model_how_to_write_one():
    out = problems(fr_body("- FR-001 y. Derives from: PER-001", "- The system shall be fast."))
    assert out == ["a list entry under 'Requirements' has no ID ('The system shall be fast.'); start every item with its ID, like '- FR-001 ...'"]


def test_a_section_with_no_items_at_all_says_so_for_each_prefix():
    out = problems("## Epics\nText\n## Features\nText\n", ctx(EPICS))
    assert "'Epics' has no numbered items; write each one as '- EPIC-001 ...' with its own ID" in out
    assert "'Features' has no numbered items; write each one as '- FEAT-001 ...' with its own ID" in out


def test_the_same_id_twice_is_reported_once_per_extra_use():
    out = problems(fr_body("- FR-001 a. Derives from: PER-001", "- FR-001 b. Derives from: PER-001"))
    assert out == ["FR-001 appears more than once; every item needs its own ID"]


def test_a_first_draft_that_skips_a_number_is_told_where_numbering_must_start():
    out = problems(fr_body("- FR-001 a. Derives from: PER-001", "- FR-003 b. Derives from: PER-001"))
    assert out == ["new FR items must be numbered FR-001 onward without gaps; found FR-001, FR-003"]


def test_a_first_draft_that_starts_above_one_is_refused():
    assert problems(fr_body("- FR-002 a. Derives from: PER-001")) == ["new FR items must be numbered FR-001 onward without gaps; found FR-002"]


def test_a_missing_derives_from_is_named_per_item():
    out = problems(fr_body("- FR-001 a.", "- FR-002 b. Derives from: PER-001"))
    assert out == ["FR-001 has no 'Derives from:'; end the line with 'Derives from:' and the IDs it comes from, or a source in square brackets"]


def test_an_empty_derives_from_does_not_count():
    assert any("FR-001 has no 'Derives from:'" in p for p in problems(fr_body("- FR-001 a. Derives from:")))


def test_a_derives_from_an_id_the_model_was_never_shown_is_refused_by_name():
    out = problems(fr_body("- FR-001 a. Derives from: PER-001, PER-009"))
    assert out == ["FR-001 derives from PER-009, which is not in the material you were given"]


def test_an_item_may_derive_from_an_earlier_item_of_its_own_artefact():
    body = "## Epics\n- EPIC-001 a. Derives from: PER-001\n## Features\n- FEAT-001 b. Derives from: EPIC-001\n"
    assert problems(body, ctx(EPICS)) == []


def test_an_item_may_not_derive_from_itself():
    assert problems(fr_body("- FR-001 a. Derives from: FR-001")) == ["FR-001 cannot derive from itself"]


def test_a_bracketed_source_satisfies_the_derives_from_rule():
    assert problems(fr_body("- FR-001 a. Derives from: [DOC-001#2]")) == []


# ---- regeneration ---------------------------------------------------------------------------------------------------------

V1 = fr_body(
    "- FR-001 a. Derives from: PER-001",
    "- FR-002 b. Derives from: PER-001",
    "- FR-003 c. Derives from: PER-001",
)


def after(*bodies: str, **kw) -> ItemContext:
    h = history_of(list(bodies), FR)
    return ctx(current=h.current, retired=h.retired, highest=h.highest, previous=h.previous, **kw)


def test_history_precondition_three_items_were_current_and_none_retired():
    h = history_of([V1], FR)
    assert h.current == {"FR-001", "FR-002", "FR-003"} and h.retired == frozenset() and h.highest == {"FR": 3}
    assert [i.id for i in h.previous] == ["FR-001", "FR-002", "FR-003"]


def test_keeping_every_id_and_adding_the_next_number_passes():
    body = V1 + "- FR-004 d. Derives from: PER-001\n"
    assert problems(body, after(V1)) == []


def test_dropping_an_id_without_withdrawing_it_is_refused_by_name():
    body = fr_body("- FR-001 a. Derives from: PER-001", "- FR-003 c. Derives from: PER-001")
    assert problems(body, after(V1)) == ["FR-002 was in the previous version and is now missing; keep it, or list it under 'Withdrawn items' with a reason"]


def test_withdrawing_an_id_with_a_reason_passes():
    body = fr_body("- FR-001 a. Derives from: PER-001", "- FR-003 c. Derives from: PER-001", extra="## Withdrawn items\n- FR-002 replaced by FR-003\n")
    assert problems(body, after(V1)) == []


def test_a_withdrawn_id_cannot_come_back_in_a_later_version():
    v2 = fr_body("- FR-001 a. Derives from: PER-001", "- FR-003 c. Derives from: PER-001", extra="## Withdrawn items\n- FR-002 gone\n")
    v3 = fr_body("- FR-001 a. Derives from: PER-001", "- FR-002 back again. Derives from: PER-001", "- FR-003 c. Derives from: PER-001")
    context = after(V1, v2)
    assert context.retired == {"FR-002"}  # precondition: FR-002 really is retired by now
    assert problems(v3, context) == [
        "FR-002 was in an earlier version and is no longer in use, so it cannot be used again; give a new item the next free number"]


def test_new_numbers_continue_after_the_highest_ever_used_including_withdrawn_ones():
    v2 = fr_body("- FR-001 a. Derives from: PER-001", "- FR-002 b. Derives from: PER-001", extra="## Withdrawn items\n- FR-003 gone\n")
    context = after(V1, v2)
    assert context.next_number("FR") == 4  # FR-003 was withdrawn, so the next free number is still 4
    reuses = fr_body("- FR-001 a. Derives from: PER-001", "- FR-002 b. Derives from: PER-001", "- FR-003 new. Derives from: PER-001")
    assert any("FR-003" in p for p in problems(reuses, context))
    assert problems(fr_body("- FR-001 a. Derives from: PER-001", "- FR-002 b. Derives from: PER-001", "- FR-004 new. Derives from: PER-001"), context) == []


def test_an_id_that_is_both_an_item_and_withdrawn_is_refused():
    body = V1 + "## Withdrawn items\n- FR-002 gone\n"
    assert problems(body, after(V1)) == ["FR-002 is both an item and listed under 'Withdrawn items'; it can only be one"]


def test_withdrawing_an_id_that_was_never_in_the_previous_version_is_refused():
    body = V1 + "## Withdrawn items\n- FR-009 never existed\n"
    assert problems(body, after(V1)) == ["FR-009 is listed under 'Withdrawn items' but was not in the previous version"]


def test_listing_an_already_retired_id_again_under_withdrawn_is_harmless():
    v2 = fr_body("- FR-001 a. Derives from: PER-001", "- FR-003 c. Derives from: PER-001", extra="## Withdrawn items\n- FR-002 gone\n")
    v3 = v2.replace("- FR-002 gone", "- FR-002 gone\n")
    assert problems(v3, after(V1, v2)) == []


def test_a_first_draft_may_omit_the_withdrawn_section():
    assert "Withdrawn items" not in GOOD and problems(GOOD) == []


def test_history_of_no_versions_is_empty():
    h = history_of([], FR)
    assert (h.current, h.retired, dict(h.highest), h.previous) == (frozenset(), frozenset(), {}, ())


# ---- coverage ---------------------------------------------------------------------------------------------------------------

POOL = {"FR": ("FR-001", "FR-002"), "NFR": ("NFR-001",)}


def epics_body(feature_line: str, coverage: str = "None.") -> str:
    return f"## Epics\n- EPIC-001 e. Derives from: PER-001\n## Features\n{feature_line}\n## Coverage check\n{coverage}\n"


def covering() -> ItemContext:
    return ctx(EPICS, covers=("FR", "NFR"), pools=POOL, known=frozenset({"PER-001", "FR-001", "FR-002", "NFR-001"}))


def test_coverage_precondition_a_feature_naming_every_requirement_passes():
    assert problems(epics_body("- FEAT-001 f. Derives from: EPIC-001, FR-001, FR-002, NFR-001"), covering()) == []


def test_an_uncovered_requirement_not_mentioned_anywhere_is_refused_by_name():
    out = problems(epics_body("- FEAT-001 f. Derives from: EPIC-001, FR-001, NFR-001"), covering())
    assert out == ["FR-002 is not named in any item's 'Derives from:', and 'Coverage check' does not list it; cover it, or list it under 'Coverage check'"]


def test_an_uncovered_requirement_listed_in_the_coverage_check_is_accepted():
    out = problems(epics_body("- FEAT-001 f. Derives from: EPIC-001, FR-001, NFR-001", "- FR-002 out of scope for now"), covering())
    assert out == []


def test_listing_a_covered_requirement_as_uncovered_is_refused():
    out = problems(epics_body("- FEAT-001 f. Derives from: EPIC-001, FR-001, FR-002, NFR-001", "- FR-002 forgotten"), covering())
    assert out == ["'Coverage check' lists FR-002 as not covered, but it is covered, or not among the items you were given; list only the ones no item derives from"]


def test_listing_an_id_that_was_never_a_requirement_in_the_coverage_check_is_refused():
    out = problems(epics_body("- FEAT-001 f. Derives from: EPIC-001, FR-001, FR-002, NFR-001", "- FR-099 invented"), covering())
    assert len(out) == 1 and "FR-099" in out[0]


def test_several_uncovered_requirements_are_reported_together_in_order():
    out = problems(epics_body("- FEAT-001 f. Derives from: EPIC-001"), covering())
    assert len(out) == 1 and out[0].startswith("FR-001, FR-002, NFR-001 are not named")


def test_the_coverage_check_is_not_applied_when_the_skill_covers_nothing():
    assert problems(epics_body("- FEAT-001 f. Derives from: EPIC-001"), ctx(EPICS)) == []


def test_upstream_pool_collects_item_ids_by_prefix_without_repeats():
    pool = upstream_pool([(GOOD, FR), (GOOD, FR)])
    assert pool == {"FR": ("FR-001", "FR-002")}


# ---- limits ---------------------------------------------------------------------------------------------------------------------

def test_a_large_body_with_hundreds_of_items_is_read_in_reasonable_time():
    import time

    body = "## Requirements\n" + "\n".join(f"- FR-{n:03d} item {n}. Derives from: PER-001" for n in range(1, 801))
    started = time.perf_counter()
    parsed = parse_items(body, FR)
    assert len(parsed.items) == 800 and time.perf_counter() - started < 2.0
    assert check_items(body, ctx()) == []


def test_pathological_text_does_not_hang_the_reader():
    import time

    hostile = "## Requirements\n- FR-001 " + "Derives from: " * 5000 + "PER-001\n- " + "A-" * 5000 + "\n" + "FR-" * 5000
    started = time.perf_counter()
    parse_items(hostile, FR)
    assert time.perf_counter() - started < 2.0


def test_item_is_a_plain_value():
    item = Item("FR-001", "Requirements", "t", (), False)
    assert item.prefix == "FR" and item.link_targets == ()


def test_a_retired_id_stays_retired_after_a_later_version_stops_listing_it_as_withdrawn():
    """The prompt says to leave the Withdrawn heading out when nothing is withdrawn, so version 3 will not
    mention FR-002 at all. Reusing it in version 4 would still point old links at a different requirement."""
    v2 = fr_body("- FR-001 a. Derives from: PER-001", "- FR-003 c. Derives from: PER-001", extra="## Withdrawn items\n- FR-002 gone\n")
    v3 = fr_body("- FR-001 a. Derives from: PER-001", "- FR-003 c. Derives from: PER-001")
    context = after(V1, v2, v3)
    assert "FR-002" not in v3 and context.retired == {"FR-002"}  # preconditions: v3 never mentions it, yet it is retired
    v4 = fr_body("- FR-001 a. Derives from: PER-001", "- FR-002 sneaks back. Derives from: PER-001", "- FR-003 c. Derives from: PER-001")
    assert any("FR-002 was in an earlier version and is no longer in use" in p for p in problems(v4, context))
