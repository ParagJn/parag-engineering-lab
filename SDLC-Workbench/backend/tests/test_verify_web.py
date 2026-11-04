"""S20c: the frontend reader (by pattern), the weak-evidence check for rules, and the matching of screens to pages. Plain text in and plain data out."""
from __future__ import annotations

import pytest

from app.verify import match as M
from app.verify.design import Design, Designed
from app.verify.readers import python_fastapi as PF
from app.verify.readers import web as W


def read(**files):
    return W.read_frontend([(name.replace("__", "/").replace("_tsx", ".tsx").replace("_jsx", ".jsx").replace("_vue", ".vue").replace("_ts", ".ts"), text) for name, text in files.items()])


def pages(f):
    return sorted((p.name, p.kind) for p in f.pages)


def calls(f):
    return sorted((c.method, c.path) for c in f.calls)


# ---- pages ---------------------------------------------------------------------------------------------------------------------------------------

def test_react_router_routes_are_found_in_both_the_jsx_and_the_object_form():
    f = read(src__App_tsx='''
<Routes>
  <Route path="/rooms" element={<Rooms/>} />
  <Route path={"/rooms/:id"} element={<Room/>} />
  <Route path="*" element={<NotFound/>} />
</Routes>
const router = createBrowserRouter([{ path: "/reservations", element: <R/> }, { path: '/admin', children: [] }])
''')
    assert pages(f) == [("/admin", "route"), ("/reservations", "route"), ("/rooms", "route"), ("/rooms/:id", "route")]


def test_vue_router_routes_are_found():
    f = read(src__router_ts="export default [{ path: '/rooms', component: Rooms }, { path: '/rooms/:id', name: 'room', component: Room }]")
    assert pages(f) == [("/rooms", "route"), ("/rooms/:id", "route")]


@pytest.mark.parametrize("rel,name", [
    ("pages/rooms/index.tsx", "rooms"), ("pages/rooms/[id].tsx", "rooms/:id"), ("pages/Reservations.jsx", "Reservations"), ("app/rooms/page.tsx", "rooms"),
    ("app/rooms/[id]/page.tsx", "rooms/:id"), ("app/(admin)/rooms/page.tsx", "rooms"), ("src/routes/rooms.vue", "rooms"), ("pages/index.tsx", "home"),
    ("src/views/Browse.vue", "Browse"), ("pages/[...slug].tsx", ":slug"),
])
def test_file_based_pages_are_named_by_their_folder_and_file(rel, name):
    assert W.file_page_name(rel) == name


@pytest.mark.parametrize("rel", ["pages/_app.tsx", "pages/_document.tsx", "pages/api/rooms.ts", "app/rooms/layout.tsx", "app/rooms/loading.tsx", "src/components/Button.tsx",
                                 "pages/rooms.test.tsx", "pages/rooms.spec.ts", "README.md", "pages/readme.md", "x.tsx", "app/rooms/route.ts"])
def test_files_that_are_not_pages_are_not_made_into_pages(rel):
    assert W.file_page_name(rel) is None


# ---- API calls ---------------------------------------------------------------------------------------------------------------------------------

def test_fetch_axios_and_client_helpers_give_a_method_and_a_path():
    f = read(src__api_ts='''
fetch("/api/rooms")
fetch(`/api/rooms/${id}`, { method: "PUT", body: x })
fetch('/api/x', { method: 'delete' })
axios.get("/api/availability", { params })
axios.post(`/api/reservations`, body)
api.patch('/api/reservations/1')
http.delete("/api/reservations/" + id)
''')
    assert calls(f) == [("DELETE", "/api/reservations/"), ("DELETE", "/api/x"), ("GET", "/api/availability"), ("GET", "/api/rooms"), ("PATCH", "/api/reservations/1"),
                        ("POST", "/api/reservations"), ("PUT", "/api/rooms/{}")]


def test_a_template_value_becomes_a_parameter_and_each_calls_options_belong_to_that_call_only():
    f = read(src__a_ts='fetch(`/api/a/${x}/b/${y}`); fetch("/api/c", { method: "POST" }); fetch("/api/d")')
    assert calls(f) == [("GET", "/api/a/{}/b/{}"), ("GET", "/api/d"), ("POST", "/api/c")]


def test_a_call_to_something_that_is_not_a_path_is_ignored_and_a_full_url_is_kept():
    f = read(src__a_ts='fetch(url); fetch("relative/path"); fetch("/"); axios.get(base + "/x"); fetch("https://example.com/api/x")')
    assert calls(f) == [("GET", "https://example.com/api/x")]


def test_where_each_call_is_in_the_file_is_recorded():
    f = read(src__a_ts='\n\nfetch("/api/x")\n')
    assert (f.calls[0].file, f.calls[0].line) == ("src/a.ts", 3)


def test_the_calls_of_a_file_are_grouped_by_file():
    f = read(src__a_ts='fetch("/api/x"); fetch("/api/y")', src__b_ts='fetch("/api/z")')
    assert f.calls_by_file() == {"src/a.ts": frozenset({"/api/x", "/api/y"}), "src/b.ts": frozenset({"/api/z"})}


# ---- fields, texts and the unreadable -----------------------------------------------------------------------------------------------------------

def test_form_field_names_are_found_in_inputs_register_calls_and_form_data():
    f = read(src__Form_tsx='''
<input name="start_time" /> <select name="room_id"></select> <TextField name="note"/>
const { register } = useForm(); register("end_time"); data.append("x"); formData.append("date", d)
''')
    assert f.fields == {"src/Form.tsx": ["start_time", "room_id", "note", "end_time", "date"]}


def test_comments_and_test_names_are_collected_for_the_rule_check():
    f = read(src__a_ts='''
// RUL-001 no overlap
/* RUL-002 four hours at most */
<!-- RUL-003 retired rooms -->
it("refuses a booking that overlaps", () => {}); test(`handles a retired room`, () => {})
const url = "http://example.com//not-a-comment"
''')
    texts = [t for _, t in f.texts]
    assert "RUL-001 no overlap" in texts and "RUL-002 four hours at most" in texts and "RUL-003 retired rooms" in texts
    assert "refuses a booking that overlaps" in texts and "handles a retired room" in texts and not any("not-a-comment" in t for t in texts)


def test_a_frontend_the_patterns_cannot_make_sense_of_says_so_instead_of_returning_nothing_quietly():
    f = read(src__a_ts="export const x = 1\n")
    assert f.files_read == 1 and f.notes == ["no page route or API call was recognised; this version reads React Router, Vue router, file-based pages and fetch/axios calls by pattern"]
    assert read().notes == []                                                                                     # no files at all: nothing to complain about


def test_files_that_are_not_frontend_code_are_not_read():
    f = W.read_frontend([("notes.md", "fetch('/api/x')"), ("data.json", "{}"), ("src/a.ts", "fetch('/api/y')")])
    assert f.files_read == 1 and calls(f) == [("GET", "/api/y")]


def test_the_result_does_not_depend_on_the_order_of_the_files():
    a, b = ("src/a.ts", 'fetch("/api/a")'), ("src/b.ts", 'fetch("/api/b")')
    assert calls(W.read_frontend([a, b])) == calls(W.read_frontend([b, a])) and pages(W.read_frontend([a, b])) == pages(W.read_frontend([b, a]))


# ---- rules: weak evidence only -----------------------------------------------------------------------------------------------------------------

RULE = Designed("RUL-001", "rule", "A booking may not overlap another", "A booking may not overlap another booking of the same room. Derives from: FR-001")


def rule_match(*texts, rule=RULE):
    return M.match_rules(Design(items=[rule]), list(texts))[0]


def test_a_rule_whose_id_is_written_in_a_comment_is_weak_evidence_and_never_found():
    got = rule_match(("app.py", "RUL-001 checked here"))
    assert (got.state, got.file) == (M.WEAK, "app.py") and "weak evidence" in got.note and "enforced" in got.note and got.state != M.FOUND


def test_an_id_that_only_looks_similar_is_not_the_rule():
    for text in ("RUL-0011 is another", "XRUL-001", "RUL-001a", "MYRUL-001", "rul-001"):
        assert rule_match(("app.py", text)).state == M.NOT_FOUND


def test_a_rule_quoted_in_its_own_words_is_weak_evidence_when_enough_of_them_appear_together():
    got = rule_match(("tests/t.py", "a booking may not overlap another one"))
    assert got.state == M.WEAK and "words appear together" in got.note
    assert rule_match(("t.py", "a booking is made")).state == M.NOT_FOUND                    # only one word in common
    assert rule_match(("t.py", "booking"), ("u.py", "overlap"), ("v.py", "another")).state == M.NOT_FOUND          # the words are spread over three places


def test_a_rule_nothing_mentions_is_not_found_and_says_so():
    got = rule_match()
    assert got.state == M.NOT_FOUND and got.note == "no comment, test or message in the code mentions this rule"


def test_the_id_wins_over_the_words_and_the_first_file_in_name_order_is_named():
    got = rule_match(("z.py", "RUL-001 in z"), ("a.py", "a booking may not overlap another"), ("b.py", "RUL-001 in b"))
    assert (got.file, "written in a comment" in got.note) == ("b.py", True)


def test_the_python_reader_collects_comments_docstrings_test_names_and_error_messages():
    b = PF.read_backend([("app.py", '''
"""Module notes RUL-001."""
# RUL-002 four hours
def test_cancelling_a_retired_room():
    """RUL-003 docs"""
@app.post("/x")
def x():
    raise HTTPException(409, "RUL-004 slot taken")
    raise HTTPException(status_code=422, detail="RUL-005 too long")
x = "# not a comment"
''')])
    texts = [t for _, t in b.texts]
    for want in ("Module notes RUL-001.", "RUL-002 four hours", "cancelling a retired room", "RUL-003 docs", "RUL-004 slot taken", "RUL-005 too long"):
        assert any(want in t for t in texts), want
    assert not any(t == "not a comment" for t in texts)


# ---- screens -------------------------------------------------------------------------------------------------------------------------------------

def screen(item_id, title, text=""):
    return Designed(item_id, "screen", title, text or f"{title}: the page. Derives from: FR-001")


def endpoint_match(item_id, built, state=M.FOUND):
    return M.Match(item_id, "endpoint", state, M.EXACT, 1.0, built, "app.py", 1)


def test_a_screen_is_found_on_the_page_that_shares_its_words_and_says_which_endpoints_the_page_calls():
    got, extras = M.match_screens(Design(items=[screen("HFS-001", "Browse rooms")]), [("/rooms", "src/pages/BrowseRooms.tsx", 4), ("/admin", "src/pages/Admin.tsx", 1)],
                                  {"src/pages/BrowseRooms.tsx": frozenset({"/api/rooms"})}, [])
    assert (got[0].state, got[0].built, got[0].file, got[0].line, got[0].note) == (M.FOUND, "/rooms", "src/pages/BrowseRooms.tsx", 4, "calls /api/rooms")
    assert [e.built for e in extras] == ["/admin"] and extras[0].area == "screen"


def test_a_screen_with_no_page_like_it_is_not_found_and_a_weak_page_is_only_possible():
    pages_ = [("/settings", "src/Settings.tsx", 1)]
    assert M.match_screens(Design(items=[screen("HFS-001", "Browse rooms")]), pages_, {}, [])[0][0].state == M.NOT_FOUND
    weak = M.match_screens(Design(items=[screen("HFS-001", "Browse rooms and reservations calendar view")]), [("/rooms", "src/Rooms.tsx", 1)], {}, [])[0][0]
    assert (weak.state, weak.step, weak.score) == (M.POSSIBLE, M.WORDS, 0.45) and "not enough to be sure" in weak.note


def test_two_screens_never_claim_one_page_and_the_better_pair_is_taken_first():
    design = Design(items=[screen("HFS-001", "Browse rooms"), screen("HFS-002", "Browse rooms and reserve")])
    got, extras = M.match_screens(design, [("/rooms", "src/BrowseRooms.tsx", 1)], {}, [])
    states = {m.designed: m.state for m in got}
    assert sorted(states.values()) == [M.FOUND, M.NOT_FOUND] and extras == []


def test_a_found_screen_whose_page_never_calls_the_endpoint_it_is_about_has_a_difference():
    design = Design(items=[screen("HFS-001", "Browse rooms"), Designed("API-001", "endpoint", "GET /api/rooms", "lists rooms", method="GET", path="/api/rooms")])
    page = [("/rooms", "src/BrowseRooms.tsx", 1)]
    quiet = M.match_screens(design, page, {"src/BrowseRooms.tsx": frozenset({"/api/other"})}, [endpoint_match("API-001", "GET /api/rooms")])[0][0]
    assert quiet.state == M.DIFFERENCES and quiet.differences == ("the screen is about API-001, but its page never calls it",)
    calls_it = M.match_screens(design, page, {"src/BrowseRooms.tsx": frozenset({"/api/rooms"})}, [endpoint_match("API-001", "GET /api/rooms")])[0][0]
    assert calls_it.state == M.FOUND and calls_it.differences == ()
    not_built = M.match_screens(design, page, {}, [endpoint_match("API-001", "", M.NOT_FOUND)])[0][0]
    assert not_built.state == M.FOUND                                                          # an endpoint the code does not have cannot be blamed on the page


def test_a_parameter_in_a_called_path_still_counts_as_the_call():
    design = Design(items=[screen("HFS-001", "Room details"), Designed("API-001", "endpoint", "GET /api/rooms/{id}", "room details", method="GET", path="/api/rooms/{id}")])
    got = M.match_screens(design, [("/rooms/:id", "src/RoomDetails.tsx", 1)], {"src/RoomDetails.tsx": frozenset({"/api/rooms/{}"})}, [endpoint_match("API-001", "GET /api/rooms/{id}")])[0][0]
    assert got.state == M.FOUND


def test_without_a_frontend_every_screen_says_why_it_could_not_be_looked_for():
    design = Design(items=[screen("HFS-001", "Browse rooms")])
    matched = M.match_all(design, PF.read_backend([("app.py", "x = 1\n")]))
    got = next(m for m in matched.matches if m.area == "screen")
    assert got.state == M.NOT_FOUND and "no frontend folder was given" in got.note


def test_match_all_looks_for_endpoints_tables_screens_and_rules_together():
    design = Design(items=[Designed("API-001", "endpoint", "GET /api/rooms", "lists rooms", method="GET", path="/api/rooms"), screen("HFS-001", "Browse rooms"),
                           Designed("RUL-001", "rule", "no overlap", "A booking may not overlap another. Derives from: FR-001")])
    backend = PF.read_backend([("app.py", '# RUL-001 here\n@app.get("/api/rooms")\ndef r(): ...\n')])
    front = W.read_frontend([("src/pages/BrowseRooms.tsx", 'fetch("/api/rooms")'), ("src/pages/Other.tsx", "x")])
    got = {m.designed: m.state for m in M.match_all(design, backend, front).matches}
    assert got == {"API-001": M.FOUND, "HFS-001": M.FOUND, "RUL-001": M.WEAK}


# ---- the edges (S20c mutation survivors) ----------------------------------------------------------------------------------------------------------

def test_a_route_is_placed_at_its_own_line():
    f = read(src__a_tsx='\n\n<Route path="/x" element={<A/>}/>\n<Route path="/y" element={<B/>}/>')
    assert [(p.name, p.line) for p in f.pages] == [("/x", 3), ("/y", 4)]


@pytest.mark.parametrize("rel", ["pages/Makefile", "pages/noextension", "pages/_helpers.tsx", "pages/_x.vue", "pages/layout.tsx", "pages/error.tsx", "views/loading.vue", "routes/404.tsx", "pages/main.tsx"])
def test_more_files_that_are_not_pages(rel):
    assert W.file_page_name(rel) is None


def test_the_search_for_the_end_of_a_calls_brackets_stops_at_its_limit_and_at_the_closing_bracket():
    assert len(W._call_arguments("x" * 1000, 0)) == 400 and len(W._call_arguments("x" * 1000, 0, limit=10)) == 10
    assert W._call_arguments(', { method: "PUT" }); fetch("/b")', 0) == ', { method: "PUT" })'
    far = 'fetch("/api/a", { ' + "body: 1, " * 80 + 'method: "DELETE" })'
    assert calls(read(src__a_ts=far)) == [("GET", "/api/a")]                                 # the option is past the limit: the bound is documented, not hidden


def test_calls_and_pages_come_out_in_one_order_and_a_file_given_twice_is_listed_once():
    f = W.read_frontend([("b.ts", 'fetch("/api/z"); fetch("/api/a")'), ("a.ts", '<Route path="/z" element={<Z/>}/> <Route path="/a" element={<A/>}/>')])
    assert [c.path for c in f.calls] == ["/api/a", "/api/z"] and [p.name for p in f.pages] == ["/a", "/z"]
    twice = W.read_frontend([("a.ts", 'fetch("/api/x")'), ("a.ts", 'fetch("/api/x")')])
    assert len(twice.calls) == 1 and twice.files_read == 2


def test_a_field_named_twice_is_listed_once_in_the_order_first_seen():
    f = read(src__F_tsx='<input name="b"/> <input name="a"/> <input name="b"/> register("a") register("c")')
    assert f.fields == {"src/F.tsx": ["b", "a", "c"]}


def test_an_empty_comment_is_not_kept_and_does_not_swallow_the_comment_after_it():
    f = read(src__a_ts='//\n// real one\n/**/\n/* a block */\nfetch("/api/x")')
    assert [t for _, t in f.texts] == ["real one", "a block"]
    b = PF.read_backend([("a.py", "#\n# second\nx = 1\n")])
    assert [t for _, t in b.texts] == ["second"]


def test_the_quiet_note_is_only_for_a_frontend_with_neither_a_page_nor_a_call():
    assert read(src__App_tsx='<Route path="/x" element={<A/>}/>').notes == [] and read(src__a_ts='fetch("/api/x")').notes == []


def test_a_file_name_in_capital_letters_is_still_frontend_code():
    assert W.read_frontend([("src/APP.TSX", 'fetch("/api/x")')]).files_read == 1


def test_a_hash_inside_a_string_and_a_function_that_is_not_a_test_are_not_rule_evidence():
    b = PF.read_backend([("a.py", 'x = "# not a comment"\ndef helper_for_tests(): ...\ndef test_one(): ...\n')])
    texts = [t for _, t in b.texts]
    assert not any("not a comment" in t for t in texts) and not any("helper" in t for t in texts) and "test one" in texts


# ---- screens and rules, the edges -------------------------------------------------------------------------------------------------------------

def test_a_rule_written_only_in_the_frontend_is_found_there():
    design = Design(items=[Designed("RUL-001", "rule", "no overlap", "A booking may not overlap another. Derives from: FR-001")])
    front = W.read_frontend([("src/Form.tsx", "// RUL-001 the form checks this first")])
    got = M.match_all(design, PF.read_backend([("app.py", "x = 1\n")]), front).matches[0]
    assert (got.state, got.file) == (M.WEAK, "src/Form.tsx")
    assert M.match_all(design, PF.read_backend([("app.py", "x = 1\n")])).matches[0].state == M.NOT_FOUND


def test_of_two_pages_the_screen_takes_the_one_with_the_higher_score():
    design = Design(items=[screen("HFS-001", "Browse rooms")])
    got, extras = M.match_screens(design, [("/r", "src/Rooms.tsx", 1), ("/browse-rooms", "src/BrowseRooms.tsx", 1)], {}, [])
    assert (got[0].built, [e.built for e in extras]) == ("/browse-rooms", ["/r"])


def test_a_called_path_with_a_named_parameter_counts_as_the_call_of_a_path_with_another_name():
    design = Design(items=[screen("HFS-001", "Room details"), Designed("API-001", "endpoint", "GET /api/rooms/{id}", "room details", method="GET", path="/api/rooms/{id}")])
    got = M.match_screens(design, [("/rooms/:id", "src/RoomDetails.tsx", 1)], {"src/RoomDetails.tsx": frozenset({"/api/rooms/{room_id}", "/api/other"})}, [endpoint_match("API-001", "GET /api/rooms/{id}")])[0][0]
    assert got.state == M.FOUND


def test_only_endpoints_that_were_found_are_held_against_a_page():
    design = Design(items=[screen("HFS-001", "Browse rooms"), Designed("API-001", "endpoint", "GET /api/rooms", "lists rooms", method="GET", path="/api/rooms")])
    page = [("/rooms", "src/BrowseRooms.tsx", 1)]
    for state in (M.POSSIBLE, M.NOT_FOUND):
        assert M.match_screens(design, page, {}, [endpoint_match("API-001", "GET /api/rooms", state)])[0][0].state == M.FOUND
    assert M.match_screens(design, page, {}, [endpoint_match("API-001", "GET /api/rooms", M.DIFFERENCES)])[0][0].state == M.DIFFERENCES


def test_a_page_that_calls_one_of_the_endpoints_its_screen_is_about_is_not_faulted_for_the_other():
    design = Design(items=[screen("HFS-001", "Browse rooms"), Designed("API-001", "endpoint", "GET /api/rooms", "lists rooms", method="GET", path="/api/rooms"),
                           Designed("API-002", "endpoint", "GET /api/rooms/free", "free rooms", method="GET", path="/api/rooms/free")])
    built = [endpoint_match("API-001", "GET /api/rooms"), endpoint_match("API-002", "GET /api/rooms/free")]
    got = M.match_screens(design, [("/rooms", "src/BrowseRooms.tsx", 1)], {"src/BrowseRooms.tsx": frozenset({"/api/rooms"})}, built)[0][0]
    assert got.state == M.FOUND and got.differences == ()
    none = M.match_screens(design, [("/rooms", "src/BrowseRooms.tsx", 1)], {}, built)[0][0]
    assert none.differences == ("the screen is about API-001, API-002, but its page never calls them",)


def test_a_page_is_not_faulted_for_an_endpoint_its_screen_is_not_about():
    design = Design(items=[screen("HFS-001", "Browse rooms"), Designed("API-009", "endpoint", "GET /api/invoices", "invoices", method="GET", path="/api/invoices")])
    got = M.match_screens(design, [("/rooms", "src/BrowseRooms.tsx", 1)], {}, [endpoint_match("API-009", "GET /api/invoices")])[0][0]
    assert got.state == M.FOUND and got.differences == ()
