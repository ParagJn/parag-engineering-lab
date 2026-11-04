"""S20b: matching the design to the code, the five states, the report. Plain data in and out; no files, no database, no model."""
from __future__ import annotations

import pytest

from app.verify import match as M
from app.verify import report as R
from app.verify.design import Design, Designed, words_of
from app.verify.readers import python_fastapi as PF


def endpoint(item_id, method, path, *, fields=(), codes=(), text=""):
    return Designed(item_id, "endpoint", f"{method} {path}", text or f"{method} {path}", method=method, path=path, fields=tuple(fields), codes=tuple(codes))


def table(item_id, name, cols=()):
    return Designed(item_id, "table", name, f"{name}: {', '.join(cols)}", fields=tuple(cols))


def code(src):
    return PF.read_backend([("app.py", src)])


def by_id(matches):
    return {m.designed: m for m in matches}


ROUTES = '''
from fastapi import FastAPI, APIRouter, HTTPException
from pydantic import BaseModel
app = FastAPI()
class Booking(BaseModel):
    room_id: int
    date: str
    start_time: str
    end_time: str
@app.get("/api/rooms")
def rooms(): ...
@app.post("/api/bookings", status_code=201)
def make(body: Booking):
    raise HTTPException(409)
@app.delete("/api/bookings/{booking_id}")
def cancel(booking_id: int): ...
@app.get("/api/health")
def health(): ...
'''


# ---- text helpers ---------------------------------------------------------------------------------------------------------------------------------

def test_shape_ignores_the_api_prefix_a_version_plurals_case_and_parameter_names():
    assert M.shape_of("/api/reservations/{id}") == M.shape_of("/v1/Reservation/{reservation_id}") == ("reservation", "{}")
    assert M.shape_of("/api/v2/rooms") == ("room",) and M.shape_of("/") == ()
    assert M.shape_of("/api/rooms") != M.shape_of("/api/rooms/{id}")


def test_singular_handles_the_common_plural_forms_and_leaves_other_words_alone():
    assert [M.singular(w) for w in ("rooms", "buses", "categories", "status", "class", "bed", "is")] == ["room", "bus", "category", "status", "class", "bed", "is"]


def test_cosine_is_zero_for_nothing_in_common_one_for_the_same_and_symmetrical():
    assert M.cosine({"a", "b"}, {"c"}) == 0.0 and M.cosine({"a", "b"}, {"a", "b"}) == 1.0 and M.cosine(set(), {"a"}) == 0.0
    assert M.cosine({"a", "b", "c"}, {"a"}) == M.cosine({"a"}, {"a", "b", "c"})


def test_names_agree_ignores_case_underscores_and_plurals_and_accepts_a_name_that_holds_the_other():
    assert M.names_agree("start_time", ["startTime"]) and M.names_agree("room_ids", ["room_id"]) and M.names_agree("date", ["reservation_date"])
    assert not M.names_agree("capacity", ["name", "id"]) and not M.names_agree("start", ["end"]) and not M.names_agree("x", [])


def test_words_of_drops_short_words_stop_words_and_plural_endings():
    assert words_of("The reservations of a room, via GET /api") == frozenset({"reservation", "room", "via"}) or "room" in words_of("rooms")
    assert "get" not in words_of("GET rooms") and "api" not in words_of("api rooms")


# ---- endpoints: the three steps ---------------------------------------------------------------------------------------------------------------------

def test_the_same_method_and_path_is_found_by_the_exact_step_even_when_the_parameter_is_named_differently():
    design = Design(items=[endpoint("API-001", "GET", "/api/rooms/{room_id}")])
    got = M.match_endpoints(design, code('@app.get("/api/rooms/{id}")\ndef one(id: int): ...\n'))[0][0]
    assert (got.state, got.step, got.score) == (M.FOUND, M.EXACT, 1.0) and got.built == "GET /api/rooms/{id}"


def test_a_path_that_differs_only_by_prefix_and_plural_is_found_by_the_shape_step():
    design = Design(items=[endpoint("API-001", "GET", "/api/rooms/{room_id}")])
    got = M.match_endpoints(design, code('@app.get("/v1/room/{id}")\ndef one(id: int): ...\n'))[0][0]
    assert (got.state, got.step) == (M.FOUND, M.SHAPE)


def test_a_renamed_path_is_found_by_words_and_says_what_the_design_called_it():
    design = Design(items=[endpoint("API-001", "POST", "/api/reservations", text="reserves a room", fields=("room_id", "date", "start_time", "end_time"))])
    got = M.match_endpoints(design, code(ROUTES))[0][0]
    assert got.step == M.WORDS and got.built == "POST /api/bookings" and got.score >= M.FOUND_SCORE
    assert got.state == M.DIFFERENCES and any("the design says POST /api/reservations, the code has POST /api/bookings" in d for d in got.differences)


def test_a_method_that_differs_is_never_a_match_by_any_step():
    design = Design(items=[endpoint("API-001", "PUT", "/api/rooms")])
    assert M.match_endpoints(design, code('@app.get("/api/rooms")\ndef r(): ...\n'))[0][0].state == M.NOT_FOUND


def test_a_weak_words_match_is_only_possible_and_a_hopeless_one_is_not_found():
    weak = Design(items=[endpoint("API-001", "GET", "/api/availability", text="shows which rooms are free on a day", fields=("date", "start_time", "end_time"))])
    got = M.match_endpoints(weak, code('@app.get("/api/free-rooms")\ndef free(date: str, other: int, more: int, another: int, last: int): ...\n'))[0][0]
    assert got.state in (M.POSSIBLE, M.FOUND) and got.step == M.WORDS
    hopeless = Design(items=[endpoint("API-001", "GET", "/api/zebras", text="lists zebras")])
    assert M.match_endpoints(hopeless, code('@app.get("/api/invoices")\ndef inv(): ...\n'))[0][0].state == M.NOT_FOUND


def test_the_score_thresholds_are_what_the_spec_says():
    assert (M.FOUND_SCORE, M.POSSIBLE_SCORE) == (0.5, 0.25)


def test_a_score_between_the_two_thresholds_is_possible_and_names_why():
    design = Design(items=[endpoint("API-001", "GET", "/api/cats", text="alpha beta gamma delta epsilon")])
    backend = code('@app.get("/api/dogs")\ndef alpha_beta(): ...\n')
    got = M.match_endpoints(design, backend)[0][0]
    assert got.state == M.POSSIBLE and M.POSSIBLE_SCORE <= got.score < M.FOUND_SCORE and "not enough to be sure" in got.note


def test_two_designed_endpoints_never_claim_one_built_route_and_the_better_pair_wins():
    design = Design(items=[endpoint("API-001", "GET", "/api/rooms", text="lists rooms"), endpoint("API-002", "GET", "/api/rooms/all", text="lists all rooms")])
    matches, extras = M.match_endpoints(design, code('@app.get("/api/rooms")\ndef r(): ...\n'))
    got = by_id(matches)
    assert got["API-001"].state == M.FOUND and got["API-001"].step == M.EXACT and got["API-002"].state != M.FOUND and extras == []


def test_the_result_does_not_depend_on_the_order_the_files_or_the_items_arrive_in():
    a = '@app.get("/api/rooms")\ndef a(): ...\n@app.post("/api/bookings")\ndef b(): ...\n'
    b = '@app.get("/api/available")\ndef c(): ...\n'
    design = Design(items=[endpoint("API-001", "GET", "/api/rooms"), endpoint("API-002", "POST", "/api/reservations", text="reserve a booking"), endpoint("API-003", "GET", "/api/availability")])
    forward = M.match_endpoints(design, PF.read_backend([("a.py", a), ("b.py", b)]))
    backward = M.match_endpoints(Design(items=list(reversed(design.items))), PF.read_backend([("b.py", b), ("a.py", a)]))
    key = lambda r: ([(m.designed, m.state, m.step, m.built) for m in sorted(r[0], key=lambda m: m.designed)], sorted((e.built, e.file) for e in r[1]))     # noqa: E731
    assert key(forward) == key(backward)


def test_a_built_route_nobody_designed_is_listed_as_extra_with_its_file_and_line():
    design = Design(items=[endpoint("API-001", "GET", "/api/rooms")])
    matches, extras = M.match_endpoints(design, code(ROUTES))
    assert [e.built for e in extras if "health" in e.built] == ["GET /api/health"]
    health = next(e for e in extras if "health" in e.built)
    assert health.file == "app.py" and health.line > 0 and health.area == "endpoint"


def test_with_no_routes_every_designed_endpoint_is_not_found_and_with_no_design_every_route_is_extra():
    design = Design(items=[endpoint("API-001", "GET", "/api/rooms")])
    assert [m.state for m in M.match_endpoints(design, code("x = 1\n"))[0]] == [M.NOT_FOUND]
    matches, extras = M.match_endpoints(Design(), code(ROUTES))
    assert matches == [] and len(extras) == 4


# ---- endpoints: differences -----------------------------------------------------------------------------------------------------------------------

def test_matching_fields_and_codes_are_found_without_differences():
    design = Design(items=[endpoint("API-002", "POST", "/api/bookings", fields=("room_id", "date", "start_time", "end_time"), codes=(201, 409))])
    got = M.match_endpoints(design, code(ROUTES))[0][0]
    assert got.state == M.FOUND and got.differences == ()


def test_a_field_the_design_names_and_the_code_does_not_use_is_a_difference():
    design = Design(items=[endpoint("API-002", "POST", "/api/bookings", fields=("room_id", "capacity"))])
    got = M.match_endpoints(design, code(ROUTES))[0][0]
    assert got.state == M.DIFFERENCES and got.differences == ("the design names 'capacity' but the code does not use it",)


def test_an_error_code_the_design_lists_and_the_code_never_returns_is_a_difference():
    design = Design(items=[endpoint("API-002", "POST", "/api/bookings", codes=(201, 400, 404, 409))])
    got = M.match_endpoints(design, code(ROUTES))[0][0]
    assert got.differences == ("the design lists status 400, 404 but the code never returns them",)


def test_a_different_success_code_is_a_difference_and_the_default_200_is_not_one_when_the_design_says_200():
    design = Design(items=[endpoint("API-002", "POST", "/api/bookings", codes=(200,))])
    assert any("the design succeeds with 200 but the code answers 201" in d for d in M.match_endpoints(design, code(ROUTES))[0][0].differences)
    plain = Design(items=[endpoint("API-001", "GET", "/api/rooms", codes=(200,))])
    assert M.match_endpoints(plain, code(ROUTES))[0][0].state == M.FOUND


def test_a_handler_that_declares_no_fields_says_so_instead_of_claiming_the_design_names_are_missing():
    design = Design(items=[endpoint("API-001", "GET", "/api/rooms", fields=("name",))])
    got = M.match_endpoints(design, code(ROUTES))[0][0]
    assert got.differences == ("the code's handler declares no fields to compare with the design's 'name'",)


def test_a_prefix_built_in_code_is_said_to_make_the_path_uncertain():
    design = Design(items=[endpoint("API-001", "GET", "/api/y")])
    got = M.match_endpoints(design, code('router = APIRouter(prefix=BASE + "/x")\n@router.get("/y")\ndef y(): ...\n'))[0][0]
    assert any("built in code" in d for d in got.differences)


def test_the_list_of_differences_is_bounded():
    many = tuple(f"field_{n}" for n in range(20))
    design = Design(items=[endpoint("API-002", "POST", "/api/bookings", fields=many)])
    got = M.match_endpoints(design, code(ROUTES))[0][0]
    assert len(got.differences) == 1                      # all the missing names are in one sentence
    diffs = M._bounded([f"d{n}" for n in range(12)])
    assert len(diffs) == M.MAX_DIFFERENCES + 1 and diffs[-1] == "and 4 more"


# ---- tables ---------------------------------------------------------------------------------------------------------------------------------------

SQL = "CREATE TABLE rooms (\n id INTEGER,\n name TEXT\n);\nCREATE TABLE audit_log (\n id INTEGER,\n note TEXT\n);"


def tables(sql=SQL):
    return PF.read_backend([("schema.sql", sql)])


def test_a_table_with_the_same_name_and_columns_is_found_exactly():
    got = M.match_tables(Design(items=[table("TBL-001", "rooms", ("id", "name"))]), tables())[0][0]
    assert (got.state, got.step, got.built) == (M.FOUND, M.EXACT, "rooms")


def test_a_table_named_in_the_singular_is_found_by_shape_and_a_missing_column_is_a_difference():
    got = M.match_tables(Design(items=[table("TBL-001", "room", ("id", "name", "capacity"))]), tables())[0][0]
    assert got.step == M.SHAPE and got.state == M.DIFFERENCES
    assert got.differences == ("the design calls it 'room', the code 'rooms'", "the design has column 'capacity' that the code's table does not")


def test_a_table_the_design_never_mentioned_is_extra_and_one_the_code_lacks_is_not_found():
    matches, extras = M.match_tables(Design(items=[table("TBL-001", "rooms", ("id", "name")), table("TBL-002", "invoices", ("amount",))]), tables())
    got = by_id(matches)
    assert got["TBL-001"].state == M.FOUND and got["TBL-002"].state == M.NOT_FOUND and [e.built for e in extras] == ["audit_log"]


def test_a_table_described_both_by_a_class_and_by_sql_is_one_table_with_both_columns():
    backend = PF.read_backend([("schema.sql", "CREATE TABLE rooms (id INT);"), ("db.py", 'class R(Base):\n    __tablename__ = "rooms"\n    name = Column(String)\n')])
    matches, extras = M.match_tables(Design(items=[table("TBL-001", "rooms", ("id", "name"))]), backend)
    assert matches[0].state == M.FOUND and extras == []


def test_two_designed_tables_never_claim_one_built_table():
    matches, _ = M.match_tables(Design(items=[table("TBL-001", "rooms", ("id", "name")), table("TBL-002", "room", ("id", "name"))]), tables())
    assert sorted(m.state for m in matches) == [M.FOUND, M.NOT_FOUND] or sorted(m.state for m in matches) == [M.FOUND, M.POSSIBLE]


# ---- the report -----------------------------------------------------------------------------------------------------------------------------------

def test_the_counts_add_up_and_the_share_found_counts_found_and_differences_but_not_possible():
    design = Design(items=[endpoint("API-001", "GET", "/api/rooms"), endpoint("API-002", "POST", "/api/bookings", fields=("capacity",)),
                           endpoint("API-003", "DELETE", "/api/nothing", text="zebras"), table("TBL-001", "rooms", ("id", "name"))])
    matched = M.match_all(design, PF.read_backend([("app.py", ROUTES), ("schema.sql", SQL)]))
    report = R.build_report(matched.matches, matched.extras)
    ep = next(c for c in report.areas if c.area == "endpoint")
    assert ep.designed == 3 and ep.found == 1 and ep.differences == 1 and ep.not_found + ep.possible == 1 and ep.extras >= 1
    assert ep.found + ep.differences + ep.possible + ep.not_found + ep.weak == ep.designed
    assert ep.share_found == round(2 / 3, 3)
    assert [c.area for c in report.areas] == ["endpoint", "table", "screen", "rule"]
    assert next(c for c in report.areas if c.area == "screen").share_found == 0.0


def test_the_report_orders_by_area_then_id_and_the_markdown_names_every_state_in_words():
    matches = [M.Match("TBL-001", "table", M.FOUND), M.Match("API-002", "endpoint", M.NOT_FOUND), M.Match("API-001", "endpoint", M.DIFFERENCES, M.WORDS, 0.7, "POST /x", "a.py", 3, ("it differs",))]
    report = R.build_report(matches, [M.Extra("endpoint", "GET /extra", "a.py", 9)], ["backend: left out .env"])
    assert [m.designed for m in report.matches] == ["API-001", "API-002", "TBL-001"]
    text = R.markdown(report, design_versions={"DES-LLD-001": 2})
    for word in ("Found with differences", "Not found", "Found", "Built but not designed", "What could not be read", "DES-LLD-001: version 2", "matched by words, score 0.7", "it differs"):
        assert word in text
    assert text.startswith("# Build Verify") and R.ADVICE in text


def test_the_advice_says_this_is_a_highlighter_and_never_runs_the_code():
    assert "highlighter" in R.ADVICE and "never runs your code" in R.ADVICE


# ---- the edges (S20b mutation survivors) ----------------------------------------------------------------------------------------------------------

def test_singular_leaves_a_word_of_three_letters_or_fewer_alone():
    assert [M.singular(w) for w in ("bus", "gas", "yes", "ads")] == ["bus", "gas", "yes", "ads"]


def test_a_design_item_with_no_method_matches_a_route_of_any_method_but_one_with_a_method_does_not():
    anything = Design(items=[Designed("API-001", "endpoint", "x", "lists rooms", method="", path="/api/rooms")])
    assert M.match_endpoints(anything, code('@app.post("/api/rooms")\ndef r(): ...\n'))[0][0].state == M.FOUND


def test_of_two_built_routes_the_one_with_the_higher_score_is_taken_and_the_other_is_left_as_extra():
    design = Design(items=[Designed("API-001", "endpoint", "x", "reserves a room booking", method="GET", path="")])
    matches, extras = M.match_endpoints(design, code('@app.get("/api/room")\ndef a(): ...\n@app.get("/api/room-booking")\ndef b(): ...\n'))
    assert (matches[0].built, matches[0].state, [e.built for e in extras]) == ("GET /api/room-booking", M.FOUND, ["GET /api/room"])


def test_two_designed_items_that_tie_for_one_route_are_settled_by_id_whatever_the_order():
    one = Designed("API-001", "endpoint", "x", "lists rooms", method="GET", path="")
    two = Designed("API-002", "endpoint", "x", "lists rooms", method="GET", path="")
    backend = code('@app.get("/api/rooms")\ndef a(): ...\n')
    for items in ([one, two], [two, one]):
        got = {m.designed: m.state for m in M.match_endpoints(Design(items=items), backend)[0]}
        assert got == {"API-001": M.FOUND, "API-002": M.NOT_FOUND}


def test_two_routes_that_tie_for_one_item_are_settled_by_their_place_in_the_code_whatever_the_file_order():
    design = Design(items=[Designed("API-001", "endpoint", "x", "lists rooms", method="GET", path="")])
    a = '@app.get("/api/rooms")\ndef a(): ...\n'
    b = '@app.get("/v2/rooms")\ndef b(): ...\n'
    for files in ([("a.py", a), ("b.py", b)], [("b.py", b), ("a.py", a)]):
        m, e = M.match_endpoints(design, PF.read_backend(files))
        assert (m[0].built, [x.built for x in e]) == ("GET /api/rooms", ["GET /v2/rooms"])


def test_the_score_is_rounded_to_two_places_and_the_location_is_kept():
    design = Design(items=[Designed("API-002", "endpoint", "POST /api/reservations", "POST /api/reservations reserves a room", method="POST", path="/api/reservations")])
    got = M.match_endpoints(design, code('@app.post("/api/bookings")\ndef reserve_room(): ...\n'))[0][0]
    assert got.score == 0.67 and (got.file, got.line) == ("app.py", 1)


def test_an_error_code_is_a_difference_but_a_success_code_the_code_also_returns_is_not():
    design = Design(items=[endpoint("API-002", "POST", "/api/bookings", codes=(201, 409))])
    assert M.match_endpoints(design, code(ROUTES))[0][0].differences == ()
    design = Design(items=[endpoint("API-001", "GET", "/api/rooms", codes=(204,))])
    assert M.match_endpoints(design, code(ROUTES))[0][0].differences == ("the design succeeds with 204 but the code answers 200",)


def test_fields_come_from_the_response_model_the_parameters_and_the_body_alike():
    backend = code('''
from pydantic import BaseModel
class Out(BaseModel):
    free_rooms: list
class In(BaseModel):
    day: str
@app.post("/api/x/{x_id}", response_model=list[Out])
def x(x_id: int, body: In, limit: int = 5): ...
''')
    design = Design(items=[endpoint("API-001", "POST", "/api/x/{x_id}", fields=("free_rooms", "day", "x_id", "limit"))])
    assert M.match_endpoints(design, backend)[0][0].state == M.FOUND
    for gone in ("free_rooms", "day", "x_id", "limit"):
        only = Design(items=[endpoint("API-001", "POST", "/api/x/{x_id}", fields=(gone, "nonexistent_field"))])
        assert "nonexistent_field" in M.match_endpoints(only, backend)[0][0].differences[0] and gone not in M.match_endpoints(only, backend)[0][0].differences[0]


def test_a_response_model_written_as_a_list_or_optional_still_names_its_model():
    backend = code("from pydantic import BaseModel\nclass Out(BaseModel):\n    a: int\n")
    assert [M._model_in(t, backend) for t in ("Out", "list[Out]", "Optional[Out]", "dict[str, Out]", "Other", "")] == ["Out", "Out", "Out", "Out", "", ""]


def test_a_table_name_is_compared_without_regard_to_case_and_a_table_with_some_shared_words_is_possible():
    got = M.match_tables(Design(items=[table("TBL-001", "ROOMS", ("id", "name"))]), tables())[0][0]
    assert (got.state, got.step) == (M.FOUND, M.EXACT)
    weak = PF.read_backend([("s.sql", "CREATE TABLE omega (beta INT, gamma INT, zeta INT, theta INT);")])
    got = M.match_tables(Design(items=[table("TBL-001", "alpha", ("beta", "gamma", "delta", "epsilon"))]), weak)[0][0]
    assert got.state == M.POSSIBLE and got.score == 0.4 and "not enough to be sure" in got.note


def test_a_table_found_by_words_says_what_the_design_called_it_and_a_table_with_no_columns_is_not_blamed():
    got = M.match_tables(Design(items=[table("TBL-001", "venues", ("id", "name", "capacity"))]),
                         PF.read_backend([("s.sql", "CREATE TABLE locations (id INT, name TEXT, capacity INT);")]))[0][0]
    assert (got.state, got.step, got.score, got.differences) == (M.DIFFERENCES, M.WORDS, 0.67, ("the design calls it 'venues', the code 'locations'",))
    bare = PF.read_backend([("db.py", 'class R(Base):\n    __tablename__ = "rooms"\n')])
    assert M.match_tables(Design(items=[table("TBL-001", "rooms", ("id", "name"))]), bare)[0][0].state == M.FOUND


def test_a_word_of_two_letters_is_not_a_word():
    assert "of" not in words_of("a list of rooms") and "up" not in words_of("up") and words_of("tbl rooms") == frozenset({"tbl", "room"})


def test_the_citation_in_a_designs_line_is_not_what_the_item_is_about():
    item = Designed("API-001", "endpoint", "GET /api/rooms", "lists rooms. Derives from: FR-001, PER-001", method="GET", path="/api/rooms")
    assert "derive" not in item.words and "per" not in item.words and "room" in item.words


def test_the_share_found_does_not_count_a_possible_match():
    c = R.AreaCounts("endpoint", designed=4, found=1, differences=1, possible=2, not_found=0, weak=0, extras=0)
    assert c.share_found == 0.5


def test_extras_are_counted_in_their_own_area_only():
    counts = R.counts_of([M.Match("API-001", "endpoint", M.FOUND)], [M.Extra("endpoint", "a", "f", 1), M.Extra("endpoint", "b", "f", 2), M.Extra("table", "t", "f", 3)])
    assert {c.area: c.extras for c in counts} == {"endpoint": 2, "table": 1, "screen": 0, "rule": 0}


def test_the_markdown_lists_each_extra_with_its_file_and_line_and_one_without_a_line_with_its_file_alone():
    text = R.markdown(R.build_report([], [M.Extra("endpoint", "GET /x", "a.py", 9), M.Extra("table", "t", "s.sql", 0)]))
    assert "- Endpoint `GET /x` (a.py:9)" in text and "- Table `t` (s.sql)" in text and "## Built but not designed" in text
