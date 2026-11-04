"""S19d-1: the interface contract (one name for each thing, declared once in the foundation), the check of every later file against it, and the design index
the system writes. Pure text: no model, no database."""
from __future__ import annotations

import pytest

from app.agents.skills import SkillLibrary
from app.build import compose as C
from app.build import contract as K
from app.build import instructions as I
from app.llm.routing import Routing
from app.workflow.definitions import load_catalogue

from .test_instructions import CONTRACT, DESIGN, GUIDE, SCREEN1, acceptance, foundation, full_set, scenario, screen, ui_guide

API_DESIGN = I.DesignIds(frozenset({
    "UC-001", "UC-002", "API-001", "API-002", "API-003", "TBL-001", "TBL-002", "RUL-001", "RUL-002", "RUL-003", "COMP-001", "IFC-001", "FR-001", "US-001", "HFS-001", "HFS-002",
}))


def contract_of(text: str = CONTRACT):
    return K.parse_contract(f"# F\n\n## Interface contract\n{text}\n\n## Tables\n| room_id | integer |\n| name | text |\n")


# ---- reading the contract -------------------------------------------------------------------------------------------------------------------------------

def test_each_line_gives_method_path_fields_response_fields_and_codes():
    c = contract_of()
    assert [(e.api, e.method, e.path) for e in c.endpoints] == [("API-001", "GET", "/api/rooms"), ("API-002", "GET", "/api/availability"), ("API-003", "POST", "/api/reservations")]
    one, two, three = c.endpoints
    assert one.request == frozenset() and one.response == {"rooms", "room_id", "name"} and one.codes == {200, 500}
    assert two.request == {"date", "start_time", "end_time"} and two.response == {"free", "reserved"} and two.codes == {200, 400}
    assert three.request == {"room_id", "date", "start_time", "end_time"} and three.response == {"reservation_id"} and three.codes == {201, 400, 401, 404, 409, 422}


def test_a_path_parameter_counts_as_a_request_field_and_needs_no_other():
    c = contract_of("- API-004 DELETE /api/reservations/{reservation_id}. Request: reservation_id in the path. Response 200: object with reservation_id (integer). Errors: 400.")
    [e] = c.endpoints
    assert "reservation_id" in e.request and e.problems == ()
    only_path = contract_of("- API-004 DELETE /api/reservations/{reservation_id}. Request: the id in the path. Response 200: object with ok (boolean). Errors: 404.")
    assert only_path.endpoints[0].problems == ()                                      # the path parameter is the request, so no field list is demanded


def test_the_names_the_foundation_declares_include_its_tables_json_and_backticked_words():
    f = ("# F\n\n## Interface contract\n- API-001 GET /api/rooms. Request: none. Response 200: object with rooms (list). Errors: 500.\n\n## Tables\n"
         "| Column | Type |\n|---|---|\n| room_id | integer |\n| status | text |\n\nTBL-001 rooms\n\nA refusal is `{\"refused\": true, \"reason\": \"...\"}`; keep `requester_id` out of the page.\n")
    names = K.parse_contract(f).names
    assert {"rooms", "room_id", "status", "refused", "reason", "requester_id"} <= names


def test_types_and_methods_are_never_taken_for_field_names():
    f = "# F\n\n## Interface contract\n- API-001 GET /api/rooms. Request: none. Response 200: object with rooms (list). Errors: 500.\n\nUse `json`, `string`, `get` and `list`.\n"
    assert not ({"json", "string", "get", "list", "object"} & K.parse_contract(f).names)


def test_the_status_codes_are_the_ones_the_whole_foundation_lists():
    f = foundation(contract=True, extra="\n- A refusal returns 400 for bad input, 404 when missing, and 422 for the rest.\n| 409 | the slot is taken |\n")
    assert {200, 201, 400, 401, 404, 409, 422, 500} <= K.parse_contract(f).codes


def test_the_routes_are_stored_with_every_parameter_written_the_same_way():
    c = contract_of("- API-004 DELETE /api/reservations/{reservation_id}. Request: reservation_id in the path. Response 200: object with ok (boolean). Errors: 404.")
    assert c.routes == {("DELETE", "/api/reservations/{}")}
    assert K.norm_path("/api/reservations/{reservation_id}") == K.norm_path("/api/reservations/%s") == K.norm_path("/api/reservations/7") == K.norm_path("/api/reservations/<id>") == "/api/reservations/{}"
    assert K.norm_path("/api/rooms/") == "/api/rooms" and K.norm_path("/") == "/" and K.norm_path("/api/rooms.") == "/api/rooms"


def test_a_foundation_without_the_section_has_no_contract_and_the_check_stays_quiet():
    assert K.parse_contract(foundation()) is None and K.parse_contract(None) is None and K.parse_contract("") is None
    assert I.check_file("scenario", "UC-001-reserve-a-room.md", scenario(), DESIGN, None) == []


def test_not_applicable_is_a_valid_contract_only_for_a_design_with_no_endpoints():
    c = K.parse_contract("# F\n\n## Interface contract\nNot applicable\n")
    assert c.not_applicable and c.endpoints == ()
    assert K.foundation_problems("# F\n\n## Interface contract\nNot applicable\n", []) == []
    assert any("cannot be 'Not applicable'" in p for p in K.foundation_problems("# F\n\n## Interface contract\nNot applicable\n", ["API-001"]))


# ---- the contract section itself ----------------------------------------------------------------------------------------------------------------------

def problems_of(text, apis=("API-001", "API-002", "API-003")):
    return K.foundation_problems(f"# F\n\n## Interface contract\n{text}\n", apis)


def test_a_complete_contract_has_no_problems():
    assert problems_of(CONTRACT) == []


@pytest.mark.parametrize("line, fragment", [
    ("- API-001 /api/rooms. Request: none. Response 200: object with rooms (list). Errors: 500.", "has no method and path"),
    ("- API-001 GET /api/rooms. Response 200: object with rooms (list). Errors: 500.", "no 'Request:' part"),
    ("- API-001 GET /api/rooms. Request: none. Errors: 500.", "no 'Response 200:' part"),
    ("- API-001 GET /api/rooms. Request: none. Response: object with rooms (list).", "no status code"),
    ("- API-001 GET /api/rooms. Request: stuff. Response 200: object with rooms (list). Errors: 500.", "'Request:' lists no field names"),
    ("- API-001 GET /api/rooms. Request: none. Response 200: something. Errors: 500.", "lists no field names"),
])
def test_each_missing_part_of_an_endpoint_line_is_named_with_its_endpoint(line, fragment):
    rest = "\n".join(CONTRACT.split("\n")[1:])
    found = problems_of(line + "\n" + rest)
    assert any(fragment in p and "API-001" in p for p in found), found


def test_an_endpoint_with_two_lines_or_no_line_is_named():
    twice = problems_of(CONTRACT + "\n" + CONTRACT.split("\n")[0])
    assert any("API-001 has more than one line" in p for p in twice)
    none = problems_of("\n".join(CONTRACT.split("\n")[:2]))
    assert any("has no line for API-003" in p for p in none)
    declared = K.foundation_problems(f"# F\n\n## Interface contract\n" + "\n".join(CONTRACT.split("\n")[:2]) + "\n", ["API-001", "API-002", "API-003"], ["API-003"])
    assert declared == []                                                                # a line under 'Not covered' excuses it


def test_a_section_with_no_endpoint_at_all_is_told_the_shape():
    found = problems_of("Nothing yet.")
    assert len(found) == 1 and "lists no endpoint" in found[0] and "- API-002 GET /api/availability." in found[0]


def test_an_empty_or_placeholder_section_is_the_ordinary_missing_section_problem():
    body = foundation().replace("## Tables", "## Interface contract\n\n## Tables")
    assert any("'Interface contract' is missing or empty" in p for p in I.check_file("foundation", I.FOUNDATION_NAME, body, API_DESIGN, require_contract=True))


# ---- the foundation as a kind of file -----------------------------------------------------------------------------------------------------------------

def test_a_foundation_with_the_contract_passes_and_the_sections_are_in_order():
    body = foundation(contract=True)
    assert I.check_file("foundation", I.FOUNDATION_NAME, body, API_DESIGN, require_contract=True) == []
    assert I.FOUNDATION_WITH_CONTRACT == ("Goal", "Stack and layout", "Interface contract", "Tables", "Shared rules", "How to run it", "Do not", "Traceability")
    assert I.sections_for("foundation") == I.SECTIONS["foundation"] and I.sections_for("foundation", True) == I.FOUNDATION_WITH_CONTRACT
    assert I.sections_for("scenario", True) == I.SECTIONS["scenario"]                  # only the foundation has a contract section


def test_the_composer_asks_for_the_section_so_a_foundation_without_it_is_sent_back():
    found = I.check_file("foundation", I.FOUNDATION_NAME, foundation(), API_DESIGN, require_contract=True)
    assert any("'Interface contract' is missing or empty" in p for p in found)
    assert I.check_file("foundation", I.FOUNDATION_NAME, foundation(), API_DESIGN) == []         # a foundation written before S19d is not refused


def test_a_foundation_that_carries_the_section_is_held_to_it_even_when_nobody_asked():
    body = foundation(contract="- API-001 /api/rooms. Request: none. Response 200: object with rooms (list). Errors: 500.")
    assert any("has no method and path" in p for p in I.check_file("foundation", I.FOUNDATION_NAME, body, API_DESIGN))


def test_the_foundation_may_not_leave_the_section_out_of_order():
    body = foundation(contract=True).replace("## Interface contract", "## Zzz", 1)
    assert any("missing or empty" in p for p in I.check_file("foundation", I.FOUNDATION_NAME, body, API_DESIGN, require_contract=True))
    swapped = foundation(contract=True).replace("## Tables", "## TMP").replace("## Interface contract", "## Tables").replace("## TMP", "## Interface contract")
    assert any("out of order" in p for p in I.check_file("foundation", I.FOUNDATION_NAME, swapped, API_DESIGN, require_contract=True))


def test_the_contract_may_say_not_applicable_for_a_design_with_no_endpoints_and_for_no_other_design():
    no_api = I.DesignIds(frozenset(i for i in API_DESIGN.ids if not i.startswith("API")))
    body = foundation(contract="Not applicable")
    assert I.check_file("foundation", I.FOUNDATION_NAME, body, no_api, require_contract=True) == []
    found = I.check_file("foundation", I.FOUNDATION_NAME, body, API_DESIGN, require_contract=True)
    assert any("cannot be 'Not applicable': the design has endpoints (API-001, API-002, API-003)" in p for p in found)
    assert "Interface contract" in I.NOT_APPLICABLE_OK["foundation"]


def test_an_endpoint_the_foundation_lists_under_not_covered_needs_no_contract_line():
    extra = "\n## Not covered\n- API-003 later\n"
    body = foundation(contract="\n".join(CONTRACT.split("\n")[:2]), extra=extra)
    assert I.check_file("foundation", I.FOUNDATION_NAME, body, API_DESIGN, require_contract=True) == []


# ---- a file against the contract ----------------------------------------------------------------------------------------------------------------------

def uc(build, **kw):
    return scenario("UC-001", build=build, **kw)


def file_problems(body, kind="scenario", name="UC-001-reserve-a-room.md"):
    return I.check_file(kind, name, body, API_DESIGN, contract_of())


def test_a_file_that_uses_only_the_contracts_names_codes_and_routes_has_no_problems():
    body = uc("- API-003 POST /api/reservations. Input: `room_id`, `date`, `start_time`, `end_time`. Output: `reservation_id`. Errors: 400, 404, 409.\n"
              "```json\n{\"room_id\": 1, \"date\": \"2026-10-12\", \"start_time\": \"08:00\", \"end_time\": \"09:00\"}\n```")
    assert file_problems(body) == []


def test_an_undeclared_name_is_sent_back_with_the_name_to_use():
    found = file_problems(uc("- API-002 GET /api/availability. Input: `date`, `start`, `end`. Output: `free`, `reserved`."))
    [one] = [p for p in found if "field name" in p]
    assert "'start' (the contract has 'start_time')" in one and "'end' (the contract has 'end_time')" in one and "00-foundation.md" in one


def test_a_name_with_no_close_match_is_listed_without_a_guess():
    [one] = [p for p in file_problems(uc("- Input: `zzqqxx`")) if "field name" in p]
    assert "'zzqqxx'" in one and "the contract has" not in one


def test_json_keys_are_checked_wherever_they_appear():
    body = uc("- API-003 POST /api/reservations.\n```json\n{\"room_id\": 1, \"when\": \"2026-10-12\"}\n```")
    assert any("'when'" in p for p in file_problems(body))


def test_a_backticked_word_outside_an_input_or_output_line_is_not_taken_for_a_field():
    body = uc("- API-003 POST /api/reservations. Build it in `reservations.py`; use `sqlite3` and the `identity` module. Needs TBL-001.")
    assert not any("field name" in p for p in file_problems(body))


def test_the_lines_under_an_input_item_are_read_as_fields_but_the_next_section_is_not():
    body = uc("- Input (JSON):\n  - `date`\n  - `begin`\n- Notes: use `helper` here.")
    found = [p for p in file_problems(body) if "field name" in p]
    assert len(found) == 1 and "'begin'" in found[0] and "'helper'" not in found[0]


@pytest.mark.parametrize("word", ["extra", "ignored", "spoofed", "unknown", "unexpected", "hostile"])
def test_a_line_that_says_its_name_is_extra_or_ignored_is_not_checked(word):
    body = uc(f"- API-003 POST /api/reservations.\n- Input: a {word} field `requester` in the body\n")
    assert not any("field name" in p for p in file_problems(body))


def test_many_undeclared_names_are_one_sentence_naming_the_first_five():
    names = ", ".join(f"`bad{c}`" for c in "abcdefg")
    [one] = [p for p in file_problems(uc(f"- Input: {names}")) if "field name" in p]
    assert "'bada', 'badb', 'badc', 'badd', 'bade' and 2 more" in one                    # the first five IN THE ORDER WRITTEN, the same on every run


def test_an_undeclared_status_code_is_sent_back_and_a_declared_one_is_not():
    bad = [p for p in file_problems(uc("- Errors: 400, 418 and 503.")) if "status code" in p]
    assert len(bad) == 1 and "418, 503" in bad[0] and "use only the codes it lists" in bad[0]
    assert not any("status code" in p for p in file_problems(uc("- Errors: 400, 404, 409, 422.")))


@pytest.mark.parametrize("text", [
    "returns 418", "status 418", "status code 418", "responds 418", "HTTP 418", "| 418 |", "- 418 the teapot", "assert r.status == 418", "Success: 418", "Errors: 418",
    "assert status in (200, 418)",
])
def test_every_way_of_writing_a_status_code_is_found(text):
    assert any("418" in p for p in file_problems(uc(f"- API-003 POST /api/reservations.\n{text}\n")) if "status code" in p), text


@pytest.mark.parametrize("text", ["on 2026-10-12", "08:00 to 18:00", "at most 4 hours", "room 404 of the building", "port 8000", "RUL-418", "the 500th reservation"])
def test_a_number_that_is_not_a_status_code_is_left_alone(text):
    assert not any("status code" in p for p in file_problems(uc(f"- API-003 POST /api/reservations. {text}")))


def test_a_route_the_contract_does_not_declare_is_sent_back_with_the_list_of_routes():
    [one] = [p for p in file_problems(uc("- Call GET /api/nope and PATCH /api/rooms.")) if "not in the" in p]
    assert "GET /api/nope" in one and "PATCH /api/rooms" in one and "GET /api/availability" in one and "POST /api/reservations" in one


def test_a_declared_route_with_a_number_or_a_template_in_it_matches_its_parameter():
    c = K.parse_contract("# F\n\n## Interface contract\n- API-004 DELETE /api/reservations/{reservation_id}. Request: reservation_id in the path. Response 200: object with ok (boolean). Errors: 404.\n")
    for path in ("/api/reservations/{reservation_id}", "/api/reservations/7", "/api/reservations/%s", "/api/reservations/<id>"):
        assert c.route_known("DELETE", path), path
    assert not c.route_known("GET", "/api/reservations/7") and not c.route_known("DELETE", "/api/reservations")


def test_a_path_built_up_in_code_matches_any_route_beneath_it():
    c = K.parse_contract("# F\n\n## Interface contract\n- API-004 DELETE /api/reservations/{reservation_id}. Request: reservation_id in the path. Response 200: object with ok (boolean). Errors: 404.\n")
    assert c.route_known("DELETE", "/api/reservations/") and not c.route_known("DELETE", "/api/rooms/")


def test_a_method_on_the_wrong_path_is_a_different_route():
    [one] = [p for p in file_problems(uc("- Call DELETE /api/rooms.")) if "not in the" in p]
    assert "DELETE /api/rooms" in one


def test_the_three_kinds_of_problem_are_separate_sentences():
    found = file_problems(uc("- Input: `begin`. Errors: 418. Call GET /api/nope."))
    assert sum("field name" in p for p in found) == 1 and sum("status code" in p for p in found) == 1 and sum("not in the" in p for p in found) == 1


def test_the_check_applies_to_use_case_screen_and_acceptance_files_and_not_to_the_guide_or_foundation():
    bad = "\n- Input: `begin`. Errors: 418.\n"
    for kind, name, body in (("scenario", "UC-001-a.md", uc(bad)), ("screen", SCREEN1, screen("HFS-001", **{"Calls it makes": "- API-002 with `begin`. Errors: 418."})),
                             ("acceptance", I.ACCEPTANCE_NAME, acceptance().replace("## Do not", f"{bad}\n## Do not"))):
        assert any("status code" in p for p in I.check_file(kind, name, body, API_DESIGN, contract_of())), kind
    guide = ui_guide(**{"States": "An error shows the code 418 and `begin`."})
    assert not any("status code" in p or "field name" in p for p in I.check_file("ui_guide", GUIDE, guide, API_DESIGN, contract_of()))


def test_the_whole_set_check_finds_a_drift_in_any_file_and_names_the_file():
    files = full_set(contract=True)
    files["UC-002-browse-rooms.md"] = scenario("UC-002", build="- API-001 GET /api/rooms. Input: `begin`.", derives="Derives from: UC-002, API-001")
    found = I.check_set(files, API_DESIGN)
    assert not found                                                       # check_set is about the set's SHAPE
    body = I.assemble(files, design=API_DESIGN)
    problems = I.check_instructions(body, API_DESIGN)
    assert any(p.startswith("UC-002-browse-rooms.md: it uses field name") and "'begin'" in p for p in problems)


def test_a_set_written_before_s19d_is_checked_exactly_as_before():
    files = full_set()
    files["UC-002-browse-rooms.md"] = scenario("UC-002", build="- API-001 GET /api/rooms. Input: `begin`. Errors: 418.", derives="Derives from: UC-002, API-001")
    assert I.check_instructions(I.assemble(files, design=API_DESIGN), API_DESIGN) == []


def test_a_persons_edit_goes_through_the_same_contract_check():
    from app.agents.checks import check_body
    from app.agents.skills import SkillLibrary
    from app.agents.items import ItemContext
    from app.llm.routing import Routing
    from app.workflow.definitions import load_catalogue
    files = full_set(contract=True)
    good = I.assemble(files, design=API_DESIGN)
    skill = SkillLibrary.load(load_catalogue(Routing.load().roles.keys())).get("build_instructions")
    ctx = ItemContext(specs=skill.items, covers=skill.covers, known=frozenset(API_DESIGN.ids), pools={"UC": ("UC-001", "UC-002")})
    assert check_body(good, skill, (), ctx) == []
    edited = good.replace("Needs TBL-001 and TBL-002.", "Needs TBL-001 and TBL-002. Input: `roomId`.", 1)
    assert edited != good
    found = check_body(edited, skill, (), ctx)
    assert any("it uses field name" in p and "'roomId'" in p for p in found), found


# ---- the design index ---------------------------------------------------------------------------------------------------------------------------------

TITLED = I.DesignIds(API_DESIGN.ids, tuple(sorted((i, f"Title of {i}") for i in API_DESIGN.ids)))


def test_the_index_lists_each_design_id_the_other_files_name_with_the_designs_title_and_how_many_files_use_it():
    files = full_set(contract=True)
    text = I.build_index(files, TITLED)
    assert text.startswith("# Design index") and "## Use cases" in text and "## Endpoints" in text and "## Business rules" in text
    assert "- UC-001 Title of UC-001 (used in 1 file)" in text and "- API-001 Title of API-001 (used in 4 files)" in text
    assert "- RUL-001 Title of RUL-001 (used in" in text and "## Goal" in text and "## Traceability" in text
    assert text.endswith("\n") and not text.endswith("\n\n")


def test_the_index_names_only_ids_that_exist_in_the_design_and_never_invents_a_title():
    files = full_set(contract=True)
    files["UC-001-reserve-a-room.md"] = scenario("UC-001", build="- API-001 and API-999. HFS-777.")
    text = I.build_index(files, I.DesignIds(API_DESIGN.ids))
    assert "API-999" not in text and "HFS-777" not in text and "(title not available)" in text
    assert "Title of" not in text


def test_the_index_does_not_count_itself_and_is_the_same_every_time():
    files = full_set(contract=True)
    first = I.build_index(files, TITLED)
    files[I.INDEX_NAME] = first
    assert I.build_index(files, TITLED) == first


def test_a_set_whose_files_name_no_design_id_gets_a_plain_note():
    text = I.build_index({"UC-001-a.md": "# T\n\nNothing here.\n"}, TITLED)
    assert "No design IDs are named by the other files." in text


def test_the_index_is_a_kind_of_file_of_its_own_and_sorts_after_the_ui_guide_and_before_the_use_cases():
    assert I.kind_of(I.INDEX_NAME) == "index" and I.INDEX_NAME == "02-design-index.md" and "index" not in I.KINDS
    names = [I.ACCEPTANCE_NAME, "UC-001-a.md", I.INDEX_NAME, GUIDE, I.FOUNDATION_NAME, SCREEN1]
    assert sorted(names, key=I.order_key) == [I.FOUNDATION_NAME, GUIDE, I.INDEX_NAME, "UC-001-a.md", SCREEN1, I.ACCEPTANCE_NAME]


def test_the_design_index_in_a_set_is_checked_only_for_its_name_and_real_ids():
    text = I.build_index(full_set(contract=True), TITLED)
    assert I.check_file("index", I.INDEX_NAME, text, API_DESIGN) == []
    assert any("must be named 02-design-index.md" in p for p in I.check_file("index", "index.md", text, API_DESIGN))
    assert any("API-999" in p and "not in the design" in p for p in I.check_file("index", I.INDEX_NAME, text + "\n- API-999 x\n", API_DESIGN))


def test_a_set_with_its_index_has_no_problems_and_the_index_is_listed_like_any_other_file():
    files = full_set(contract=True)
    files[I.INDEX_NAME] = I.build_index(files, TITLED)
    body = I.assemble(files, design=API_DESIGN)
    assert "- INS-002 02-design-index.md:" in body and I.check_instructions(body, API_DESIGN) == []
    assert I.split_set(body)[0][I.INDEX_NAME] == files[I.INDEX_NAME].strip("\n") + "\n"


def test_a_design_id_that_only_the_index_names_does_not_count_as_built_or_covered():
    files = full_set(contract=True)
    files[I.INDEX_NAME] = "# Design index\n\n## Goal\nx\n\n## Endpoints\n- API-002 x\n- RUL-002 x\n- RUL-003 x\n\n## Traceability\nDerives from: API-002\n"
    cover = I.coverage(files, API_DESIGN)
    assert "API-002" in cover["declared"] and "API-002" not in cover["named"]          # the foundation says it is not covered; the index naming it does not undo that
    assert "RUL-003" in cover["declared"]
    bare = {k: v for k, v in files.items() if k not in (I.INDEX_NAME,)}
    bare[I.FOUNDATION_NAME] = foundation(contract=True)                              # no 'Not covered' now
    bare[I.INDEX_NAME] = files[I.INDEX_NAME]
    assert "API-002" in I.coverage(bare, API_DESIGN)["uncovered"]                    # and the index alone does not make it built
    assert I.built_by(files) == I.built_by({k: v for k, v in files.items() if k != I.INDEX_NAME})


def test_titles_are_kept_from_the_design_and_cut_to_a_readable_line():
    assert I.design_title("Browse rooms: staff see the rooms. Derives from: PER-001") == "Browse rooms"
    assert I.design_title("**Reserve** a `room`. Then more. Derives from: UC-001") == "Reserve a room"
    assert I.design_title("") == "(no title)" and I.design_title("   ") == "(no title)"
    assert len(I.design_title("x" * 300)) <= 91 and I.design_title("x" * 300).endswith("…")
    assert I.design_title("line one\nline two: more") == "line one line two"


def test_a_label_in_the_middle_of_a_line_makes_the_names_after_it_fields_but_not_the_names_before_it():
    body = uc("- API-002 GET /api/availability, built in `availability.py`. Input: `date`, `start`. Output: `free`.")
    [one] = [p for p in file_problems(body) if "field name" in p]
    assert "'start'" in one and "availability" not in one and "'date'" not in one


def test_the_names_come_back_in_the_order_written_and_the_same_sentence_every_time():
    body = uc("- Input: `zeta`, `alpha`, `mid`\n```json\n{\"beta\": 1}\n```")
    sentences = {tuple(p for p in file_problems(body) if "field name" in p) for _ in range(20)}
    assert len(sentences) == 1
    [one] = list(sentences)[0]
    assert one.index("'zeta'") < one.index("'alpha'") < one.index("'mid'")


def test_status_codes_are_listed_in_numeric_order():
    [one] = [p for p in file_problems(uc("- Errors: 503, 418, 599.")) if "status code" in p]
    assert "418, 503, 599" in one


@pytest.mark.parametrize("label", ["Input", "Inputs", "Output", "Outputs", "Request", "Response", "Query parameters", "Fields", "Input (JSON)", "Output (200)", "Request body"])
def test_each_label_word_works_in_the_middle_of_a_line(label):
    assert any("'zzqqxx'" in p for p in file_problems(uc(f"- API-003 POST /api/reservations. {label}: `zzqqxx`.")))


# ---- gaps the 19d-1 sweep found -------------------------------------------------------------------------------------------------------------------------

def test_a_list_line_that_is_not_an_api_line_is_not_an_endpoint():
    c = K.parse_contract("# F\n\n## Interface contract\n- TBL-001 GET /api/x. Request: none. Response 200: object with a (list). Errors: 500.\n- Note: GET /api/y. Request: none.\n"
                         "- API-001 GET /api/rooms. Request: none. Response 200: object with rooms (list). Errors: 500.\n")
    assert [e.api for e in c.endpoints] == ["API-001"]


@pytest.mark.parametrize("method", ["get", "FETCH", "Post", "HEAD", "OPTIONS"])
def test_the_method_must_be_one_of_the_five(method):
    c = K.parse_contract(f"# F\n\n## Interface contract\n- API-001 {method} /api/rooms. Request: none. Response 200: object with rooms (list). Errors: 500.\n")
    assert any("has no method and path" in p for p in c.endpoints[0].problems)


@pytest.mark.parametrize("path", ["api/rooms", "rooms", "-", ""])
def test_the_path_must_start_with_a_slash(path):
    c = K.parse_contract(f"# F\n\n## Interface contract\n- API-001 GET {path}. Request: none. Response 200: object with rooms (list). Errors: 500.\n")
    assert any("has no method and path" in p for p in c.endpoints[0].problems)


def test_a_full_stop_that_ends_the_sentence_is_not_part_of_the_path():
    [e] = K.parse_contract("# F\n\n## Interface contract\n- API-001 GET /api/rooms. Request: none. Response 200: object with rooms (list). Errors: 500.\n").endpoints
    assert e.path == "/api/rooms"
    [e2] = K.parse_contract("# F\n\n## Interface contract\n- API-001 GET /api/rooms, then more. Request: none. Response 200: object with rooms (list). Errors: 500.\n").endpoints
    assert e2.path == "/api/rooms"


def test_the_words_json_string_and_get_are_never_declared_as_names_even_when_ticked():
    f = "# F\n\n## Interface contract\n- API-001 GET /api/rooms. Request: none. Response 200: object with rooms (list). Errors: 500.\n\nUse `string`, `get`, `post`, `put`, `patch`, `delete`, `enum`, `any`, `text`, `html`, `css`, `null`.\n"
    assert not ({"string", "get", "post", "put", "patch", "delete", "enum", "any", "text", "html", "css", "null"} & K.parse_contract(f).names)
    assert K.fields_in("`string` (string), `json` (object), `real_name` (integer)") == {"real_name"}


def test_the_name_after_a_table_id_is_declared():
    f = "# F\n\n## Interface contract\n- API-001 GET /api/rooms. Request: none. Response 200: object with rooms (list). Errors: 500.\n\nTBL-001 reservations\nTBL-002 `audit_rows`\n"
    assert {"reservations", "audit_rows"} <= K.parse_contract(f).names
    assert "reservations" in K.declared_names("TBL-001 reservations") and "audit_rows" in K.declared_names("TBL-002 `audit_rows`")


def test_every_endpoints_own_response_and_request_fields_are_declared_even_if_the_foundation_never_repeats_them():
    f = "# F\n\n## Interface contract\n- API-001 GET /api/rooms. Request: filter_by (string). Response 200: object with only_here (list). Errors: 500.\n"
    assert {"filter_by", "only_here"} <= K.parse_contract(f).names


def test_the_codes_in_a_foundation_come_from_every_form_it_may_use():
    assert K.codes_in("status 301") == {301} and K.codes_in("returns 302 and responds 303") == {302, 303}
    assert K.codes_in("assert r != 304") == {304} and K.codes_in("| 305 | x |") == {305} and K.codes_in("- 306 text") == {306}
    assert K.codes_in("Errors: 307, 308") == {307, 308} and K.codes_in("x in (309, 310)") == {309, 310}
    assert K.codes_in("a 600 or 99 or 1000") == set()
    assert K.codes_in("status 100 and returns 599") == {100, 599}


def test_names_before_an_inline_label_are_not_fields_but_names_after_it_are():
    body = uc("- Built in `rooms_module`: Input: `real_field`.")
    names = K.names_used(body)
    assert "real_field" in names and "rooms_module" not in names


def test_a_heading_a_blank_line_and_a_plain_line_each_end_the_input_context():
    base = "- Input:\n  - `inside`\n"
    assert "inside" in K.names_used(base)
    assert "after" not in K.names_used(base + "\nPlain `after`\n")                  # a blank line ends it
    assert "after" not in K.names_used(base + "## Next\n`after`\n")                  # a heading ends it
    assert "after" not in K.names_used(base + "Plain `after`\n")                      # a plain line ends it
    assert "nested" in K.names_used(base + "  - `nested`\n")                         # a nested line stays inside it
    assert "second" not in K.names_used("- Input: `first`\n- Notes: `second`\n")     # the next top bullet replaces the context


def test_the_nearest_name_prefers_a_suffix_then_a_prefix_then_the_closest_spelling():
    pool = ["reservation_date", "start_time", "end_time", "room_id"]
    assert K.nearest("date", pool) == "reservation_date"                               # the declared name ENDS with it
    assert K.nearest("start", pool) == "start_time"                                    # the declared name BEGINS with it
    assert K.nearest("end_tim", pool) == "end_time"                                    # a close spelling
    assert K.nearest("roomid", pool) == "room_id"
    assert K.nearest("zzzzzz", pool) is None
    assert K.nearest("x", []) is None


def test_a_suffix_match_and_a_prefix_match_each_work_on_their_own():
    assert K.nearest("id", ["room_id"]) == "room_id"                                   # suffix only
    assert K.nearest("room", ["room_id"]) == "room_id"                                 # prefix only
    assert K.nearest("room_id_extra", ["room_id"]) == "room_id"                        # the candidate is the start of the name


def test_a_close_but_not_identical_spelling_is_guessed_and_a_far_one_is_not():
    assert K.nearest("reservaton_id", ["reservation_id"]) == "reservation_id"
    assert K.nearest("qqq", ["reservation_id"]) is None


def test_a_prefix_path_matches_only_routes_of_its_own_method():
    c = K.parse_contract("# F\n\n## Interface contract\n- API-004 DELETE /api/reservations/{reservation_id}. Request: reservation_id in the path. Response 200: object with ok (boolean). Errors: 404.\n")
    assert c.route_known("DELETE", "/api/reservations/")
    assert not c.route_known("GET", "/api/reservations/")


@pytest.mark.parametrize("quote", ['"', "'", "`", ""])
def test_a_route_written_inside_code_is_found_with_any_quote_or_none(quote):
    assert K.routes_in(f'call({quote}GET{quote}, {quote}/api/rooms{quote})') == [("GET", "/api/rooms")] or K.routes_in(f"GET /api/rooms") == [("GET", "/api/rooms")]
    assert K.routes_in(f'call("GET", "/api/rooms")') == [("GET", "/api/rooms")]
    assert K.routes_in(f"call('POST', '/api/reservations')") == [("POST", "/api/reservations")]
    assert K.routes_in("GET /api/rooms") == [("GET", "/api/rooms")]


def test_every_distinct_route_in_a_file_is_returned_once_in_order():
    text = "GET /api/a then GET /api/a and POST /api/b and GET /api/c"
    assert K.routes_in(text) == [("GET", "/api/a"), ("POST", "/api/b"), ("GET", "/api/c")]


def test_a_route_only_counts_when_it_is_an_api_route():
    assert K.routes_in("GET /static/app.js and GET /api/rooms") == [("GET", "/api/rooms")]


def test_a_foundation_with_no_contract_section_reports_nothing_about_the_contract():
    assert K.foundation_problems(foundation(), ["API-001", "API-002"]) == []
    assert K.foundation_problems("", ["API-001"]) == []


def test_titles_stay_with_the_ids_they_belong_to_when_artefacts_repeat_an_id():
    d = I.DesignIds(frozenset({"UC-001"}), (("UC-001", "First"),))
    assert d.title("UC-001") == "First" and d.title("UC-002") is None


def test_the_index_is_grouped_in_the_readers_order_with_use_cases_before_endpoints_before_rules():
    text = I.build_index(full_set(contract=True), TITLED)
    assert text.index("## Use cases") < text.index("## Endpoints") < text.index("## Tables") < text.index("## Business rules") < text.index("## Traceability")


def test_the_index_ignores_a_file_whose_name_the_set_does_not_know():
    files = full_set(contract=True)
    files["notes.md"] = "# Notes\n\nSee COMP-001 and IFC-001.\n"
    text = I.build_index(files, TITLED)
    assert "COMP-001" not in text and "IFC-001" not in text


def test_the_index_is_in_the_same_order_whatever_order_the_files_are_given_in():
    files = full_set(contract=True)
    assert I.build_index(dict(reversed(list(files.items()))), TITLED) == I.build_index(files, TITLED)


def test_the_skill_describes_the_contract_the_rule_to_follow_it_and_how_to_write_fields():
    from app.agents.skills import SkillLibrary
    from app.llm.routing import Routing
    from app.workflow.definitions import load_catalogue
    method = SkillLibrary.load(load_catalogue(Routing.load().roles.keys())).get("build_instructions").method
    for phrase in ("the sections are: Goal, Stack and layout, Interface contract, Tables, Shared rules, How to run it, Do not, Traceability",
                   "The Interface contract is the ONE place names and codes are fixed", "choose one name for each thing",
                   "In every file after the foundation, use the contract's names, codes and routes exactly",
                   "write it in backticks after \"Input:\" or \"Output:\"", "how the framework's own errors", "The contract does not give X; ask the person"):
        assert phrase in method, phrase


def test_the_undeclared_codes_are_sorted_even_when_the_set_hands_them_back_in_another_order():
    """Small ints come out of a set in a fixed order today, so the break that removed `sorted` is only visible with codes that do not: 407 and 408 here come out 408 then 407."""
    c = K.parse_contract("# F\n\n## Interface contract\n- API-001 GET /api/rooms. Request: none. Response 200: object with rooms (list). Errors: 500.\n")
    [one] = [p for p in K.file_problems("- Errors: 408, 407.", c) if "status code" in p]
    assert "407, 408" in one and "408, 407" not in one


def test_a_line_of_only_spaces_ends_the_input_context_like_an_empty_line():
    assert "after" not in K.names_used("- Input:\n  - `inside`\n   \n  `after`\n")
    assert "inside" in K.names_used("- Input:\n  - `inside`\n   \n  `after`\n")


def test_an_indented_heading_ends_the_input_context():
    names = K.names_used("- Input:\n  - `inside`\n    ## Next\n    `after`\n")
    assert "inside" in names and "after" not in names


def test_an_artefact_that_holds_no_items_adds_no_titles_even_when_its_text_looks_like_items(catalogue):
    from app.agents.prompt import Upstream
    library = SkillLibrary.load(catalogue)
    assert library.get("project_charter").items == ()
    up = [Upstream("A3", "Charter", "project_charter", "## Purpose\n- UC-777 Looks like an item. Derives from: PER-001\n"), Upstream("A9", "Unknown", "no_such_key", "- UC-888 x")]
    assert C._titles(up, library) == ()


@pytest.fixture(scope="module")
def catalogue():
    return load_catalogue(Routing.load().roles.keys())
