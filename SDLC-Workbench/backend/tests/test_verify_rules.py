"""S20f: a rule is linked to the endpoint it belongs to, and that endpoint says whether the rule has a home in the build. Never FOUND: a rule is logic, and an endpoint that
exists only shows the rule has somewhere to live. Pure functions over plain data; no files, no model."""
from __future__ import annotations

from app.verify import match as M
from app.verify.design import Design, Designed
from app.verify.readers import python_fastapi as PF


def endpoint(item_id, method, path, *, codes=(), derives=("FR-001",), text=""):
    return Designed(item_id, "endpoint", f"{method} {path}", text or f"{method} {path}", method=method, path=path, codes=tuple(codes), derives=tuple(derives))


def rule(item_id, text, derives=("FR-001",)):
    return Designed(item_id, "rule", text.split(".")[0], text, derives=tuple(derives))


BUILD = '''
from fastapi import FastAPI, HTTPException
app = FastAPI()
@app.post("/api/reservations", status_code=201)
def book():
    raise HTTPException(409)
@app.get("/api/rooms")
def rooms(): ...
'''
OVERLAP = "A reservation may not overlap another reservation for the same room."


def run(items, build=BUILD, texts=()):
    design = Design(items=list(items))
    backend = PF.read_backend([("app.py", build)])
    endpoints, _ = M.match_endpoints(design, backend)
    return {m.designed: m for m in M.match_rules(design, list(texts), endpoints, backend)}, endpoints


# ---- who a rule is kin to ----------------------------------------------------------------------------------------------------------------------

def test_a_shared_requirement_and_a_shared_word_link_a_rule_to_its_endpoint():
    ep = endpoint("API-002", "POST", "/api/reservations")
    link = M.rule_link(rule("RUL-001", OVERLAP), [endpoint("API-001", "GET", "/api/rooms", derives=("FR-002",)), ep])
    assert link and link.endpoint.id == "API-002" and link.shared_sources == ("FR-001",) and link.shared_words == ("reservation",)


def test_a_shared_requirement_alone_does_not_link():
    assert M.rule_link(rule("RUL-001", "Staff must wear a badge in the lobby."), [endpoint("API-001", "GET", "/api/rooms")]) is None          # both come from FR-001, and share no word


def test_a_shared_word_alone_does_not_link_but_three_shared_words_do():
    other = ("FR-009",)
    assert M.rule_link(rule("RUL-001", OVERLAP, derives=other), [endpoint("API-002", "POST", "/api/reservations")]) is None
    three = endpoint("API-002", "POST", "/api/reservations", text="POST /api/reservations books a room and refuses an overlap with another reservation")
    link = M.rule_link(rule("RUL-001", OVERLAP, derives=other), [three])
    assert link and link.shared_sources == () and len(link.shared_words) >= M.RULE_LINK_WORDS


def test_a_source_document_chunk_is_not_a_requirement_two_items_share():
    ep = endpoint("API-002", "POST", "/api/reservations", derives=("DOC-001#2",))
    assert M.rule_link(rule("RUL-001", OVERLAP, derives=("DOC-001#2",)), [ep]) is None


def test_exactly_two_shared_words_without_a_shared_requirement_do_not_link():
    two = endpoint("API-002", "POST", "/api/reservations", text="POST /api/reservations books a room")
    r = rule("RUL-001", "A reservation may not overlap another one for the same room.", derives=("FR-009",))
    assert len(r.words & two.words) == 2 and M.rule_link(r, [two]) is None                          # reservation and room: two is not enough, three is (RULE_LINK_WORDS)
    assert M.RULE_LINK_WORDS == 3


def test_of_two_endpoints_sharing_as_many_words_the_one_with_more_shared_requirements_wins_even_with_a_later_id():
    r = rule("RUL-001", OVERLAP, derives=("FR-001", "FR-002"))
    both = Designed("API-009", "endpoint", "POST /api/reservations", "POST /api/reservations", method="POST", path="/api/reservations", derives=("FR-001", "FR-002"))
    one = Designed("API-001", "endpoint", "POST /api/reservations", "POST /api/reservations", method="POST", path="/api/reservations", derives=("FR-001",))
    assert r.words & both.words == r.words & one.words == frozenset({"reservation"})                                # a true tie on words, and both qualify
    assert M.rule_link(r, [one]) is not None
    link = M.rule_link(r, [one, both])
    assert link.endpoint.id == "API-009" and link.shared_sources == ("FR-001", "FR-002")                            # two shared requirements settle it, though API-001 has the lower ID
    assert M.rule_link(r, [both, one]).endpoint.id == "API-009"


def test_the_endpoint_sharing_the_most_words_wins_and_a_tie_goes_to_the_lowest_id_whatever_the_order():
    a = endpoint("API-002", "POST", "/api/reservations")
    b = endpoint("API-003", "POST", "/api/reservations/overlap", text="POST /api/reservations/overlap checks an overlap")
    r = rule("RUL-001", OVERLAP)
    assert M.rule_link(r, [a, b]).endpoint.id == "API-003" == M.rule_link(r, [b, a]).endpoint.id
    c, d = endpoint("API-005", "GET", "/api/reservations"), endpoint("API-004", "GET", "/api/reservation")
    assert M.rule_link(r, [c, d]).endpoint.id == "API-004" == M.rule_link(r, [d, c]).endpoint.id


# ---- what the hint says ------------------------------------------------------------------------------------------------------------------------

def test_a_rule_whose_endpoint_is_built_and_answers_the_designed_error_is_weak_evidence_and_names_both():
    got, _ = run([endpoint("API-002", "POST", "/api/reservations", codes=(201, 409)), rule("RUL-001", OVERLAP)])
    m = got["RUL-001"]
    assert m.state == M.WEAK and m.area == "rule" and m.built == "POST /api/reservations" and m.file == "app.py" and m.line > 0
    assert "Linked to API-002 because both come from FR-001 and share the word reservation" in m.note and "answers 409" in m.note and "weak evidence" in m.note


def test_a_rule_is_never_found_by_its_endpoint_however_good_the_match():
    got, _ = run([endpoint("API-002", "POST", "/api/reservations", codes=(201, 409)), rule("RUL-001", OVERLAP)])
    assert got["RUL-001"].state not in (M.FOUND, M.DIFFERENCES)


def test_an_endpoint_with_no_error_code_in_the_design_still_gives_the_rule_a_home_and_says_it_proves_nothing():
    got, _ = run([endpoint("API-002", "POST", "/api/reservations", codes=(201,)), rule("RUL-001", OVERLAP)])
    assert got["RUL-001"].state == M.WEAK and "gives it no error code" in got["RUL-001"].note and "not proof" in got["RUL-001"].note


def test_an_endpoint_built_without_the_designed_refusal_leaves_the_rule_not_found_and_says_which_code():
    build = 'from fastapi import FastAPI\napp = FastAPI()\n@app.post("/api/reservations", status_code=201)\ndef book(): ...\n'
    got, _ = run([endpoint("API-002", "POST", "/api/reservations", codes=(201, 409)), rule("RUL-001", OVERLAP)], build=build)
    assert got["RUL-001"].state == M.NOT_FOUND and "never answers 409" in got["RUL-001"].note and got["RUL-001"].built == "POST /api/reservations"


def test_a_rule_whose_endpoint_was_not_built_is_not_found_and_says_so():
    got, endpoints = run([endpoint("API-009", "POST", "/api/reservations", codes=(409,)), rule("RUL-001", OVERLAP)], build="from fastapi import FastAPI\napp = FastAPI()\n")
    assert {m.state for m in endpoints} == {M.NOT_FOUND} and got["RUL-001"].state == M.NOT_FOUND and "API-009" in got["RUL-001"].note and "was not found in the build" in got["RUL-001"].note


def test_a_rule_whose_endpoint_was_only_a_possible_match_claims_nothing():
    got, endpoints = run([endpoint("API-002", "POST", "/api/reservation-slots-xyz", codes=(409,), text="reservation slot"), rule("RUL-001", OVERLAP)])
    if endpoints[0].state == M.POSSIBLE:
        assert got["RUL-001"].state == M.NOT_FOUND and "only a possible match" in got["RUL-001"].note


def test_a_rule_with_no_endpoint_it_belongs_to_is_not_found_and_says_it_has_no_home():
    got, _ = run([endpoint("API-001", "GET", "/api/rooms", codes=(200,)), rule("RUL-001", "Staff must wear a badge in the lobby.")])
    assert got["RUL-001"].state == M.NOT_FOUND and "no endpoint of the design is clearly where it belongs" in got["RUL-001"].note


def test_several_rules_may_share_one_endpoint():
    got, _ = run([endpoint("API-002", "POST", "/api/reservations", codes=(201, 409)), rule("RUL-001", OVERLAP), rule("RUL-002", "A reservation is at most four hours long.")])
    assert got["RUL-001"].state == got["RUL-002"].state == M.WEAK and got["RUL-001"].built == got["RUL-002"].built


# ---- the older evidence still counts, and comes first --------------------------------------------------------------------------------------------

def test_a_rule_named_in_a_comment_is_still_weak_evidence_and_the_comment_wins_over_the_endpoint():
    got, _ = run([endpoint("API-002", "POST", "/api/reservations", codes=(201, 409)), rule("RUL-001", OVERLAP)], texts=[("app.py", "# RUL-001 checked here")])
    m = got["RUL-001"]
    assert m.state == M.WEAK and "is written in a comment" in m.note and m.built == "" and m.file == "app.py"


def test_a_rule_with_neither_a_comment_nor_an_endpoint_is_not_found():
    got, _ = run([rule("RUL-001", "Staff must wear a badge in the lobby.")], texts=[("app.py", "# nothing relevant")])
    assert got["RUL-001"].state == M.NOT_FOUND


def test_the_result_does_not_depend_on_the_order_of_the_design():
    items = [endpoint("API-002", "POST", "/api/reservations", codes=(201, 409)), endpoint("API-001", "GET", "/api/rooms", codes=(200,)), rule("RUL-001", OVERLAP), rule("RUL-002", "A room can be retired.")]
    first, _ = run(items)
    second, _ = run(list(reversed(items)))
    assert {k: (v.state, v.built, v.note) for k, v in first.items()} == {k: (v.state, v.built, v.note) for k, v in second.items()}


# ---- the whole match no longer has screens ---------------------------------------------------------------------------------------------------------

def test_match_all_takes_only_the_backend_and_gives_endpoints_tables_and_rules():
    design = Design(items=[endpoint("API-002", "POST", "/api/reservations", codes=(201, 409)), rule("RUL-001", OVERLAP)])
    matched = M.match_all(design, PF.read_backend([("app.py", BUILD)]))
    assert {m.area for m in matched.matches} == {"endpoint", "rule"} and next(m for m in matched.matches if m.area == "rule").state == M.WEAK
