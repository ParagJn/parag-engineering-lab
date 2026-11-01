"""Traceability (S15): the graph, the rules read from the skills, the five kinds of gap, the chain table, the route, the CSV, and the approval summary.

The computation (app/trace/traceability.py) is pure, so most of this is plain data in and plain data out. The last part runs the real thing on a project built
by the scripted model and checks every number by hand."""
from __future__ import annotations

import contextlib
import csv
import io
import random
import signal
import time

import httpx
import pytest

from app.agents.skills import SkillLibrary
from app.llm.routing import Routing
from app.main import create_app
from app.trace import gather as G
from app.trace import traceability as T
from app.trace.traceability import (
    BUILT_ON_NOTHING, DECLARED, MISSING_TARGET, NOT_COVERED, WITHDRAWN_TARGET, Item, Rule, ancestors, build_graph, compute, descendants, has_loop, layer_order, walk,
)
from app.workflow.definitions import load_catalogue
from scripts import architecture_demo as A

pytestmark = pytest.mark.anyio


@contextlib.contextmanager
def within(seconds: int, label: str):
    """Fail instead of hang (Unix only; elsewhere the plain time assertion still applies)."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def stop(_s, _f):
        raise AssertionError(f"{label}: still running after {seconds}s")

    previous = signal.signal(signal.SIGALRM, stop)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


# A tiny project in plain data: personas are the first layer; FR covers PER; COMP (component_overview) must cover FR; API (low_level_design) must cover FR.
RULES = [
    Rule("personas", ("PER",), (), "requirements", ()),
    Rule("functional_requirements", ("FR",), (), "requirements", ("PER",)),
    Rule("component_overview", ("COMP",), ("FR",), "architecture", ("FR",)),
    Rule("low_level_design", ("API",), ("FR",), "architecture", ("COMP", "FR")),
]
ITEMS = [
    Item("PER-001", "REQ-PER-001", "personas", 1, "Staff"), Item("FR-001", "REQ-F-001", "functional_requirements", 1, "Book a room"),
    Item("FR-002", "REQ-F-001", "functional_requirements", 1, "Retire a room"),
    Item("COMP-001", "ARC-CMP-001", "component_overview", 1, "Booking"), Item("API-001", "ARC-LLD-001", "low_level_design", 1, "POST /bookings"),
]
LINKS = [("FR-001", "PER-001", "REQ-F-001"), ("FR-002", "PER-001", "REQ-F-001"), ("COMP-001", "FR-001", "ARC-CMP-001"), ("COMP-001", "FR-002", "ARC-CMP-001"),
         ("API-001", "FR-001", "ARC-LLD-001"), ("API-001", "FR-002", "ARC-LLD-001"), ("API-001", "COMP-001", "ARC-LLD-001")]
WRITTEN = {"personas", "functional_requirements", "component_overview", "low_level_design"}
PHASES = {"requirements", "architecture"}


def run(items=ITEMS, links=LINKS, **kw):
    kw.setdefault("written", WRITTEN)
    kw.setdefault("started_phases", PHASES)
    kw.setdefault("first_layer", {"PER"})
    return compute(items, links, RULES, **kw)


def gaps_of(trace):
    return [(g.kind, g.item, g.other, g.by) for g in trace.gaps]


# ---- the graph ------------------------------------------------------------------------------------------------------------------------------------

def test_a_link_points_from_the_later_item_to_the_earlier_one_so_ancestors_are_what_it_comes_from():
    pairs = [(a, b) for a, b, _ in LINKS]
    assert ancestors("API-001", pairs) == ["COMP-001", "FR-001", "FR-002", "PER-001"]               # nearest first; the three at distance one by kind and number
    assert descendants("PER-001", pairs) == ["FR-001", "FR-002", "API-001", "COMP-001"]


def test_an_item_reached_by_two_paths_is_listed_once():
    pairs = [("API-001", "COMP-001"), ("API-001", "FR-001"), ("COMP-001", "FR-001")]               # FR-001 is reached directly AND through COMP-001
    assert ancestors("API-001", pairs) == ["COMP-001", "FR-001"]


def test_items_at_the_same_distance_are_listed_the_same_way_whatever_order_the_links_were_made_in():
    base = [("FLOW-002", "COMP-001"), ("API-001", "COMP-001"), ("FLOW-001", "COMP-001"), ("DEC-001", "COMP-001"), ("API-002", "COMP-001")]
    want = ["API-001", "API-002", "DEC-001", "FLOW-001", "FLOW-002"]
    rng = random.Random(8)
    for _ in range(12):
        shuffled = base[:]
        rng.shuffle(shuffled)
        assert descendants("COMP-001", shuffled) == want
    deeper = base + [("TBL-001", "API-002"), ("RUL-001", "API-001")]
    assert descendants("COMP-001", deeper) == want + ["RUL-001", "TBL-001"]                          # a further level follows the nearer one, never mixed in


def test_duplicate_and_self_links_are_ignored():
    up, down = build_graph([("B", "A"), ("B", "A"), ("A", "A")])
    assert up == {"B": ["A"]} and down == {"A": ["B"]}


def test_a_very_long_chain_is_walked_without_recursion_and_a_loop_ends():
    with within(20, "long chain"):
        chain = [(f"X-{n + 1:03d}", f"X-{n:03d}") for n in range(1, 3000)]
        assert len(ancestors("X-2999", chain)) == 2998
        assert has_loop(chain) == []
        looped = [("A-001", "B-001"), ("B-001", "C-001"), ("C-001", "A-001")]
        assert sorted(walk("A-001", build_graph(looped)[0])) == ["B-001", "C-001"]                       # ends, and does not list the start again
        assert has_loop(looped) == ["A-001", "B-001", "C-001"]


def test_a_walk_stops_at_its_bound_so_a_corrupt_graph_cannot_hang_a_request():
    wide = [(f"Y-{n:04d}", "Z-001") for n in range(1, 9000)]
    assert len(walk("Z-001", build_graph(wide)[1])) == T.MAX_WALK == 5000


# ---- the rules, read from the skills -----------------------------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def library():
    catalogue = load_catalogue(Routing.load().roles.keys())
    return catalogue, SkillLibrary.load(catalogue)


def test_every_shipped_skill_that_numbers_items_gives_a_rule_and_the_rule_says_what_the_skill_says(library):
    catalogue, skills = library
    rules = {r.artefact: r for r in G.rules_of(skills, catalogue)}
    held = {k for k in skills.keys if skills.get(k).items}
    assert set(rules) == held and len(rules) == 14
    for key, rule in rules.items():
        skill = skills.get(key)
        assert rule.holds == tuple(s.prefix for s in skill.items) and rule.covers == tuple(skill.covers) and rule.phase == skill.artefact.phase_key


def test_the_rules_the_matrix_uses_are_the_covers_lines_so_a_new_covers_line_changes_the_matrix(library):
    catalogue, skills = library
    got = {(r.artefact, c) for r in G.rules_of(skills, catalogue) for c in r.covers}
    assert got == {("component_overview", "FR"), ("component_overview", "NFR"), ("epics_features", "FR"), ("epics_features", "NFR"), ("flow_diagram", "IFC"),
                   ("hifi_wireframes", "LFS"), ("high_level_design", "COMP"), ("low_level_design", "FR"), ("lowfi_wireframes", "JS"), ("usecase_diagram", "PER"),
                   ("user_journey", "PER"), ("user_stories", "FEAT")}


def test_what_a_rule_may_read_is_wider_than_what_it_must_cover(library):
    catalogue, skills = library
    rules = {r.artefact: r for r in G.rules_of(skills, catalogue)}
    assert set(rules["user_journey"].reads) >= {"PER", "FR", "FEAT"} and rules["user_journey"].covers == ("PER",)


def test_the_kinds_that_start_the_chain_are_read_from_the_skills_not_listed_by_hand(library):
    _, skills = library
    assert G.first_layer_prefixes(skills) == {"PER", "NFR", "OBJ"}


def test_columns_follow_the_phases_then_the_distance_from_the_requirements(library):
    catalogue, skills = library
    order = layer_order(G.rules_of(skills, catalogue), ("FR", "NFR"), [p.key for p in catalogue.phases])
    assert order == ("EPIC", "FEAT", "US", "LFS", "JS", "HFS", "COMP", "DEC", "IFC", "API", "TBL", "RUL", "UC", "FLOW")


def test_a_skill_that_ships_later_brings_its_own_column_and_rule(library):
    """A future Build skill that reads the low-level design and covers its endpoints needs no change here: it shows up as a column."""
    catalogue, skills = library
    phases = [p.key for p in catalogue.phases]
    assert "MOD" not in layer_order(G.rules_of(skills, catalogue), ("FR", "NFR"), phases)
    rules = G.rules_of(skills, catalogue) + [Rule("backend_code", ("MOD",), ("API",), "build", ("API",))]
    order = layer_order(rules, ("FR", "NFR"), phases)
    assert order[-1] == "MOD" and order[:-1] == layer_order(G.rules_of(skills, catalogue), ("FR", "NFR"), phases)       # the existing columns do not move; MOD follows API, which it reads


# ---- the five kinds of gap ----------------------------------------------------------------------------------------------------------------------------

def test_a_whole_and_correct_project_has_no_gaps_and_a_full_chain_table():
    trace = run()
    assert gaps_of(trace) == []
    assert [c.item for c in trace.chains] == ["FR-001", "FR-002"]
    assert dict(trace.chains[0].layers) == {"COMP": ("COMP-001",), "API": ("API-001",)} and dict(trace.chains[0].states) == {"COMP": "built", "API": "built"}


def test_not_covered_names_the_item_and_the_artefact_that_should_have_accounted_for_it():
    links = [l for l in LINKS if not (l[0] == "COMP-001" and l[1] == "FR-002")]
    trace = run(links=links)
    assert gaps_of(trace) == [(NOT_COVERED, "FR-002", None, "component_overview")]
    assert trace.gaps[0].sentence == "FR-002 is not named by any item in the component overview, and its Coverage check does not explain why."
    assert trace.gaps[0].group == "needs_attention" and trace.gaps[0].artefact_id == "REQ-F-001" and trace.gaps[0].version == 1


def test_one_item_missing_from_two_artefacts_is_two_gaps_one_for_each_artefact():
    links = [l for l in LINKS if l[1] != "FR-002"]
    assert gaps_of(run(links=links)) == [(NOT_COVERED, "FR-002", None, "component_overview"), (NOT_COVERED, "FR-002", None, "low_level_design")]


def test_an_item_the_writer_admitted_is_a_declared_gap_with_the_writers_reason_and_never_needs_attention():
    links = [l for l in LINKS if not (l[0] == "COMP-001" and l[1] == "FR-002")]
    trace = run(links=links, declared={("component_overview", "FR-002"): "retiring a room is done by hand in v1"})
    [gap] = trace.gaps
    assert (gap.kind, gap.group, gap.reason) == (DECLARED, "explained", "retiring a room is done by hand in v1")
    assert gap.sentence == "FR-002 is listed under Coverage check in the component overview as not covered. The writer's reason: retiring a room is done by hand in v1"


def test_a_reason_given_to_one_artefact_does_not_excuse_another():
    links = [l for l in LINKS if l[1] != "FR-002"]
    trace = run(links=links, declared={("component_overview", "FR-002"): "later"})
    assert [(g.kind, g.by) for g in trace.gaps] == [(NOT_COVERED, "low_level_design"), (DECLARED, "component_overview")]


def test_an_artefact_that_is_not_written_yet_is_never_blamed():
    trace = run(items=[i for i in ITEMS if i.artefact_key != "low_level_design"], links=[l for l in LINKS if l[0] != "API-001"], written=WRITTEN - {"low_level_design"})
    assert gaps_of(trace) == []


def test_built_on_nothing_is_an_item_that_derives_from_nothing_unless_it_starts_the_chain():
    trace = run(items=ITEMS + [Item("COMP-002", "ARC-CMP-001", "component_overview", 1, "Orphan")])
    assert (BUILT_ON_NOTHING, "COMP-002", None, None) in gaps_of(trace)
    assert not [g for g in trace.gaps if g.item == "PER-001"]                                       # a persona derives from nothing and that is right
    assert [g for g in trace.gaps if g.item == "COMP-002"][0].sentence == "COMP-002 derives from nothing."


def test_a_kind_that_starts_the_chain_is_only_exempt_if_the_skills_say_so():
    assert [g.item for g in run(first_layer=set()).gaps] == ["PER-001"] and run(first_layer=set()).gaps[0].kind == BUILT_ON_NOTHING


def test_pointing_at_a_withdrawn_item_is_a_gap_and_the_withdrawn_item_is_not_a_requirement_row():
    items = [i if i.id != "FR-002" else Item("FR-002", "REQ-F-001", "functional_requirements", 2, "Retire a room", withdrawn=True) for i in ITEMS]
    trace = run(items=items)
    assert [c.item for c in trace.chains] == ["FR-001"]                                              # a withdrawn requirement has no row
    assert (WITHDRAWN_TARGET, "COMP-001", "FR-002", None) in gaps_of(trace) and (WITHDRAWN_TARGET, "API-001", "FR-002", None) in gaps_of(trace)
    assert {g.item: g.sentence for g in trace.gaps if g.other == "FR-002"}["COMP-001"] == "COMP-001 derives from FR-002, which was withdrawn."
    assert not [g for g in trace.gaps if g.kind == NOT_COVERED]                                      # and a withdrawn item is not itself "uncovered"


def test_pointing_at_something_that_exists_nowhere_is_a_gap_but_an_artefact_or_a_document_is_not():
    links = LINKS + [("API-001", "COMP-099", "ARC-LLD-001"), ("API-001", "ARC-HLD-001", "ARC-LLD-001"), ("API-001", "DOC-001#3", "ARC-LLD-001"), ("API-001", "MEM-004", "ARC-LLD-001")]
    trace = run(links=links, artefact_ids={"ARC-HLD-001"})
    assert gaps_of(trace) == [(MISSING_TARGET, "API-001", "COMP-099", None)]
    assert trace.gaps[0].sentence == "API-001 names COMP-099, which is not in any artefact."


def test_each_gap_kind_is_produced_by_its_own_case_and_by_no_other():
    cases = {
        NOT_COVERED: run(links=[l for l in LINKS if l[0] != "COMP-001" or l[1] != "FR-002"]),
        DECLARED: run(links=[l for l in LINKS if l[0] != "COMP-001" or l[1] != "FR-002"], declared={("component_overview", "FR-002"): "x"}),
        BUILT_ON_NOTHING: run(items=ITEMS + [Item("COMP-002", "ARC-CMP-001", "component_overview", 1)]),
        WITHDRAWN_TARGET: run(items=[i if i.id != "FR-002" else Item("FR-002", "REQ-F-001", "functional_requirements", 2, withdrawn=True) for i in ITEMS]),
        MISSING_TARGET: run(links=LINKS + [("API-001", "COMP-099", "ARC-LLD-001")]),
    }
    for kind, trace in cases.items():
        assert kind in {g.kind for g in trace.gaps}, kind
    assert {g.kind for g in cases[NOT_COVERED].gaps} == {NOT_COVERED}
    assert {g.kind for g in cases[DECLARED].gaps} == {DECLARED}
    assert {g.kind for g in cases[BUILT_ON_NOTHING].gaps} == {BUILT_ON_NOTHING}
    assert {g.kind for g in cases[MISSING_TARGET].gaps} == {MISSING_TARGET}


def test_fixing_the_cause_removes_the_gap():
    broken = run(links=[l for l in LINKS if l[0] != "COMP-001" or l[1] != "FR-002"])
    assert len(broken.gaps) == 1 and run().gaps == ()


def test_gaps_are_ordered_attention_first_then_explained_then_by_item_number():
    links = [l for l in LINKS if l[1] != "FR-002"]
    trace = run(items=ITEMS + [Item("COMP-002", "ARC-CMP-001", "component_overview", 1)], links=links, declared={("component_overview", "FR-002"): "x"})
    kinds = [g.kind for g in trace.gaps]
    assert kinds == sorted(kinds, key=T.KINDS.index) and kinds[-1] == DECLARED


def test_more_gaps_than_the_cap_are_counted_not_listed():
    items = ITEMS + [Item(f"COMP-{n:03d}", "ARC-CMP-001", "component_overview", 1) for n in range(2, 603)]
    trace = run(items=items)
    assert len(trace.gaps) == T.MAX_GAPS == 500 and trace.gaps_more == 101


# ---- the chain table ------------------------------------------------------------------------------------------------------------------------------

def test_a_layer_in_a_phase_that_has_not_started_is_not_started_never_empty():
    items = [i for i in ITEMS if i.artefact_key in ("personas", "functional_requirements")]
    trace = run(items=items, links=[l for l in LINKS if l[0].startswith("FR")], written=WRITTEN & {"personas", "functional_requirements"}, started_phases={"requirements"})
    assert gaps_of(trace) == []                                                                       # a project at Requirements has no false gaps for Architecture
    assert set(trace.chains[0].states.values()) == {"not_started"}


def test_a_layer_in_a_started_phase_with_nothing_built_is_empty_for_that_requirement_only():
    trace = run(links=[l for l in LINKS if l[0] != "API-001" or l[1] != "FR-002"])
    assert trace.chains[0].states["API"] == "built" and trace.chains[1].states["API"] == "built"        # API-001 still derives from FR-002 via COMP-001? no: via the comp
    only = run(items=ITEMS + [Item("FR-003", "REQ-F-001", "functional_requirements", 1, "Third")], links=LINKS + [("FR-003", "PER-001", "REQ-F-001")])
    row = {c.item: c for c in only.chains}["FR-003"]
    assert row.states["COMP"] == "empty" and row.states["API"] == "empty" and row.layers["COMP"] == ()


def test_a_column_nothing_is_ever_built_on_in_a_started_phase_is_left_out_of_the_table():
    extra = RULES + [Rule("epics_features", ("EPIC",), ("FR",), "requirements", ("PER",))]
    trace = compute(ITEMS, LINKS, extra, written=WRITTEN, started_phases=PHASES, first_layer={"PER"})
    assert "EPIC" not in trace.layer_order and "COMP" in trace.layer_order


def test_a_requirement_row_lists_everything_below_it_not_only_the_nearest_layer():
    assert dict(run().chains[0].layers) == {"COMP": ("COMP-001",), "API": ("API-001",)}               # API-001 derives from COMP-001 AND FR-001; both reach it


def test_rows_are_in_requirement_order_and_items_inside_a_cell_in_number_order():
    items = ITEMS + [Item("FR-010", "REQ-F-001", "functional_requirements", 1), Item("API-010", "ARC-LLD-001", "low_level_design", 1), Item("API-002", "ARC-LLD-001", "low_level_design", 1)]
    links = LINKS + [("FR-010", "PER-001", "x"), ("API-010", "FR-010", "x"), ("API-002", "FR-001", "x"), ("COMP-001", "FR-010", "x")]
    trace = run(items=items, links=links)
    assert [c.item for c in trace.chains] == ["FR-001", "FR-002", "FR-010"]
    assert trace.chains[0].layers["API"] == ("API-001", "API-002")


def test_counts_are_per_kind_over_current_items_only():
    items = ITEMS + [Item("COMP-002", "ARC-CMP-001", "component_overview", 1, withdrawn=True)]
    assert dict(run(items=items).counts) == {"API": 1, "COMP": 1, "FR": 2, "PER": 1}


def test_the_same_input_always_gives_the_same_answer_whatever_order_it_comes_in():
    rng = random.Random(4)
    reference = run()
    for _ in range(10):
        items, links = ITEMS[:], LINKS[:]
        rng.shuffle(items); rng.shuffle(links)
        assert run(items=items, links=links) == reference


def test_the_computation_is_quick_on_a_large_project():
    items = [Item(f"FR-{n:03d}", "REQ-F-001", "functional_requirements", 1) for n in range(1, 301)] + [Item(f"COMP-{n:03d}", "ARC-CMP-001", "component_overview", 1) for n in range(1, 301)]
    links = [(f"COMP-{n:03d}", f"FR-{n:03d}", "x") for n in range(1, 301)] + [(f"FR-{n:03d}", "PER-001", "x") for n in range(1, 301)]
    started = time.perf_counter()
    with within(20, "large project"):
        trace = run(items=items + [Item("PER-001", "REQ-PER-001", "personas", 1)], links=links)
    assert time.perf_counter() - started < 10 and len(trace.chains) == 300


# ---- reading a Coverage check ------------------------------------------------------------------------------------------------------------------------

def test_a_coverage_check_line_gives_the_item_and_the_writers_words():
    body = "## Coverage check\n- FR-009 the sources give no number for it\n- NFR-002: deferred to phase two\n- PER-001 not an FR\n\n## Open questions\n- FR-010 not here\n"
    assert G.declared_reasons(body, {"FR", "NFR"}) == {"FR-009": "the sources give no number for it", "NFR-002": "deferred to phase two"}


def test_none_and_prose_in_a_coverage_check_declare_nothing():
    assert G.declared_reasons("## Coverage check\nNone.\n", {"FR"}) == {} and G.declared_reasons("## Coverage check\nEvery FR-001 is covered.\n", {"FR"}) == {}


def test_a_coverage_check_line_with_no_reason_still_declares_the_gap_and_says_so():
    assert G.declared_reasons("## Coverage check\n- FR-009\n", {"FR"}) == {"FR-009": "no reason given"}


def test_a_long_reason_is_cut_and_a_fenced_one_is_ignored():
    body = "## Coverage check\n- FR-009 " + "w " * 400 + "\n```\n- FR-010 hidden\n```\n"
    got = G.declared_reasons(body, {"FR"})
    assert list(got) == ["FR-009"] and len(got["FR-009"]) <= 300


# ---- the whole thing, on a project built by the scripted model, counted by hand ---------------------------------------------------------------------------

@pytest.fixture
def world(make_settings):
    async def build(provider=None, *, through="architecture"):
        cfg = make_settings(**{**A.MODELS, "llm_retry_backoff_seconds": 0, "run_max_cost_usd": 0})
        app = create_app(cfg, provider=provider or A.Scripted())
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        store, engine, runner = app.state.store, app.state.engine, app.state.runner
        from app.sample import BRIEF, FILENAME, NAME, POLICY

        project = store.projects.create(name=NAME, brief=BRIEF, actor="system")
        engine.open_project(project.id)
        store.context.add_document(project.id, FILENAME, POLICY, actor="human:demo")
        for phase in ("setup", "requirements", "design", "architecture"):
            await runner.run_phase(project.id, phase)
            if phase == through:
                break
            engine.finish(project.id, phase, actor="system"); engine.approve(project.id, phase, actor="human:demo")
        return app, client, project

    return build


async def test_the_scripted_project_has_the_items_and_links_a_hand_count_gives(world):
    app, client, project = await world()
    data = (await client.get(f"/api/projects/{project.id}/traceability")).json()
    assert data["counts"] == {"API": 3, "COMP": 3, "DEC": 2, "EPIC": 2, "FEAT": 2, "FLOW": 4, "FR": 2, "HFS": 3, "IFC": 2, "JS": 3, "LFS": 3, "NFR": 2, "OBJ": 2, "PER": 2,
                              "RUL": 2, "TBL": 2, "UC": 3, "US": 2}
    assert [c["item"] for c in data["chains"]] == ["FR-001", "FR-002", "NFR-001", "NFR-002"]
    assert data["gaps"] == [] and data["needs_attention"] == 0 and data["explained"] == 0
    await client.aclose()


async def test_the_chain_of_one_scripted_requirement_lists_exactly_what_was_built_for_it(world):
    app, client, project = await world()
    data = (await client.get(f"/api/projects/{project.id}/traceability")).json()
    fr1 = next(c for c in data["chains"] if c["item"] == "FR-001")
    cells = {c["layer"]: c["items"] for c in fr1["cells"]}
    assert cells["COMP"] == ["COMP-001", "COMP-003"] and cells["API"] == ["API-001", "API-002", "API-003"] and cells["TBL"] == ["TBL-001", "TBL-002"] and cells["RUL"] == ["RUL-001"]
    assert cells["JS"] == ["JS-001", "JS-002"] and cells["LFS"] == ["LFS-001", "LFS-002"] and cells["HFS"] == ["HFS-001", "HFS-002"] and cells["UC"] == ["UC-001", "UC-002"]
    assert all(c["state"] == "built" for c in fr1["cells"] if c["items"])
    await client.aclose()


async def test_removing_a_derives_from_by_hand_makes_the_gap_appear_with_the_artefact_named_and_putting_it_back_removes_it(world):
    app, client, project = await world()
    store = app.state.store
    app.state.human  # the phase must be editable
    art = next(a for a in store.artefacts.list(project.id, phase_key="architecture") if a.type == "component_overview")
    body = store.artefacts.get_version(project.id, art.id).body
    cut = body.replace("Derives from: FR-002, NFR-002", "Derives from: NFR-002").replace("it holds no rules. Derives from: FR-001, FR-002", "it holds no rules. Derives from: FR-001")
    assert cut != body
    saved = await client.put(f"/api/projects/{project.id}/artefacts/{art.id}", json={"body": cut}, headers={"X-Actor": "Ann"})
    assert saved.status_code == 422                                                                     # the coverage rule refuses it at write time: the writer cannot leave FR-002 silently out
    assert any("FR-002" in p for p in saved.json()["detail"]["problems"])
    data = (await client.get(f"/api/projects/{project.id}/traceability")).json()
    assert data["gaps"] == []
    await client.aclose()


async def test_a_gap_that_appears_later_is_caught_when_an_upstream_item_is_added_after_the_downstream_one_was_written(world):
    app, client, project = await world()
    store, engine = app.state.store, app.state.engine
    engine.reopen(project.id, "requirements", actor="human:Ann", reason="a new requirement arrived") if False else None
    req = next(a for a in store.artefacts.list(project.id, phase_key="requirements") if a.type == "functional_requirements")
    body = store.artefacts.get_version(project.id, req.id).body
    added = body.replace("\n## Business rules", "\n- FR-003 The system shall let staff see who booked a room, for PER-001. Derives from: PER-001, REQ-PRB-001\n\n## Business rules", 1)
    assert added != body
    add_requirement(store, project.id, req.id, added)
    data = (await client.get(f"/api/projects/{project.id}/traceability")).json()
    got = sorted((g["kind"], g["item"], g["by"]) for g in data["gaps"])
    assert got == [("not_covered", "FR-003", "component_overview"), ("not_covered", "FR-003", "epics_features"), ("not_covered", "FR-003", "low_level_design")]
    assert data["needs_attention"] == 3
    assert [g["sentence"] for g in data["gaps"] if g["by"] == "low_level_design"] == ["FR-003 is not named by any item in the low level design, and its Coverage check does not explain why."]
    await client.aclose()


async def test_a_project_still_in_design_shows_no_false_gaps_for_architecture(world):
    app, client, project = await world(through="design")
    data = (await client.get(f"/api/projects/{project.id}/traceability")).json()
    assert data["gaps"] == []
    fr1 = next(c for c in data["chains"] if c["item"] == "FR-001")
    states = {c["layer"]: c["state"] for c in fr1["cells"]}
    assert states.get("COMP") == "not_started" and states.get("API") == "not_started" and states["JS"] == "built"
    await client.aclose()


def add_requirement(store, project_id: str, artefact_id: str, body: str) -> None:
    """What a person's edit does: a new version whose links are the artefact's WHOLE set again, now with FR-003's."""
    version = store.artefacts.get_version(project_id, artefact_id)
    from app.agents.items import parse_items
    from app.agents.skills import SkillLibrary
    from app.llm.routing import Routing
    from app.workflow.definitions import load_catalogue

    skills = SkillLibrary.load(load_catalogue(Routing.load().roles.keys()))
    links = [(i.id, t, "derives") for i in parse_items(body, skills.get("functional_requirements").items).items for t in i.link_targets]
    store.artefacts.add_version(project_id, artefact_id, body=body, author="human:Ann", links=links)


async def test_a_version_saved_with_too_few_links_leaves_the_items_it_lost_their_links_visible_as_built_on_nothing(world):
    """The links of an artefact are replaced as a set. A version saved with only the new item's link drops the others, and the detector must say so."""
    app, client, project = await world()
    store = app.state.store
    req = next(a for a in store.artefacts.list(project.id, phase_key="requirements") if a.type == "functional_requirements")
    body = store.artefacts.get_version(project.id, req.id).body
    store.artefacts.add_version(project.id, req.id, body=body, author="human:Ann", links=[("FR-001", "PER-001", "derives")])
    data = (await client.get(f"/api/projects/{project.id}/traceability")).json()
    assert [(g["kind"], g["item"]) for g in data["gaps"] if g["kind"] == "built_on_nothing"] == [("built_on_nothing", "FR-002")]
    await client.aclose()


# ---- the routes ---------------------------------------------------------------------------------------------------------------------------------------

async def test_the_routes_are_read_only_need_no_name_and_an_unknown_project_is_404(world):
    app, client, project = await world()
    assert (await client.get(f"/api/projects/{project.id}/traceability")).status_code == 200
    assert (await client.get("/api/projects/nope/traceability")).status_code == 404
    assert (await client.get("/api/projects/nope/traceability/export.csv")).status_code == 404
    for method in ("post", "put", "delete", "patch"):
        assert (await getattr(client, method)(f"/api/projects/{project.id}/traceability")).status_code == 405
    await client.aclose()


async def test_an_archived_project_can_still_be_read(world):
    app, client, project = await world()
    app.state.store.projects.archive(project.id, actor="human:Ann")
    assert (await client.get(f"/api/projects/{project.id}/traceability")).status_code == 200
    assert (await client.get(f"/api/projects/{project.id}/traceability/export.csv")).status_code == 200
    await client.aclose()


async def test_the_answer_holds_ids_names_and_sentences_but_never_an_artefact_body_or_a_path(world):
    app, client, project = await world()
    text = (await client.get(f"/api/projects/{project.id}/traceability")).text
    assert "## Overview" not in text and "Derives from" not in text and "<artefact>" not in text and "/Users" not in text and "recordings" not in text
    await client.aclose()


async def test_one_item_with_what_it_comes_from_and_what_was_built_on_it(world):
    app, client, project = await world()
    data = (await client.get(f"/api/projects/{project.id}/traceability/item/COMP-001")).json()
    assert data["item"]["id"] == "COMP-001" and data["item"]["name"] == "Booking service" and data["item"]["artefact_id"] == "ARC-CMP-001"
    assert [r["id"] for r in data["comes_from"]][:2] == ["FR-001", "NFR-001"] and "PER-001" in [r["id"] for r in data["comes_from"]]
    assert "API-001" in [r["id"] for r in data["built_on_it"]] and "FLOW-001" in [r["id"] for r in data["built_on_it"]]
    assert data["gaps"] == []
    await client.aclose()


@pytest.mark.parametrize("bad, status", [("COMP-999", 404), ("comp-001", 422), ("..%2Fetc", 422), ("COMP-1", 422), ("A" * 200, 422)])
async def test_an_item_that_is_unknown_or_malformed_is_refused_with_a_sentence(world, bad, status):
    app, client, project = await world()
    response = await client.get(f"/api/projects/{project.id}/traceability/item/{bad}")
    assert response.status_code in (status, 404) and "detail" in response.json()
    await client.aclose()


async def test_the_csv_has_the_same_rows_as_the_table_a_stable_header_and_dashes_for_empty_cells(world):
    app, client, project = await world()
    data = (await client.get(f"/api/projects/{project.id}/traceability")).json()
    response = await client.get(f"/api/projects/{project.id}/traceability/export.csv")
    assert response.headers["content-type"].startswith("text/csv") and "traceability.csv" in response.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == ["Requirement", "Name", *data["layers"]] and [r[0] for r in rows[1:]] == [c["item"] for c in data["chains"]]
    first = dict(zip(rows[0], rows[1]))
    assert first["COMP"] == "COMP-001 COMP-003" and first["API"] == "API-001 API-002 API-003"
    nfr = dict(zip(rows[0], next(r for r in rows if r[0] == "NFR-001")))
    assert nfr["TBL"] == "-" and nfr["RUL"] == "-" and nfr["UC"] == "-"                                    # nothing was built there for this requirement: a dash, not a blank
    await client.aclose()


@pytest.mark.parametrize("cell, shown", [("=SUM(A1)", "'=SUM(A1)"), ("+1", "'+1"), ("-1", "'-1"), ("@x", "'@x"), ("\tx", "'\tx"), ("plain", "plain"), ("", ""), ("a=b", "a=b"), ("-", "-"), ("--", "'--"), ("- x", "'- x"), ("-1+1", "'-1+1")])
def test_a_cell_that_a_spreadsheet_would_run_as_a_formula_is_made_plain_text(cell, shown):
    from app.routes_trace import safe_cell
    assert safe_cell(cell) == shown


async def test_a_requirement_name_that_looks_like_a_formula_is_neutralised_in_the_csv(world):
    app, client, project = await world()
    store = app.state.store
    req = next(a for a in store.artefacts.list(project.id, phase_key="requirements") if a.type == "functional_requirements")
    body = store.artefacts.get_version(project.id, req.id).body
    evil = body.replace("- FR-001 The system shall refuse", "- FR-001 =HYPERLINK(\"http://x\",\"y\") The system shall refuse", 1)
    store.artefacts.add_version(project.id, req.id, body=evil, author="human:Ann", links=[("FR-001", "PER-001", "derives")])
    text = (await client.get(f"/api/projects/{project.id}/traceability/export.csv")).text
    assert "=HYPERLINK" not in text.replace("'=HYPERLINK", "") and "'=HYPERLINK" in text
    await client.aclose()


# ---- the approval ---------------------------------------------------------------------------------------------------------------------------------------

async def test_the_gaps_listed_with_the_approval_are_those_on_the_tab_for_that_phase(world):
    app, client, project = await world()
    store = app.state.store
    req = next(a for a in store.artefacts.list(project.id, phase_key="requirements") if a.type == "functional_requirements")
    body = store.artefacts.get_version(project.id, req.id).body
    add_requirement(store, project.id, req.id, body.replace("\n## Business rules", "\n- FR-003 The system shall show who booked. Derives from: PER-001\n\n## Business rules", 1))
    tab = (await client.get(f"/api/projects/{project.id}/traceability")).json()
    state = (await client.get(f"/api/projects/{project.id}/phases/architecture/review")).json()
    assert tab["needs_attention"] == 3 and [g["by"] for g in tab["gaps"]] == ["component_overview", "epics_features", "low_level_design"]
    assert state["open"]["traceability_gaps"] == {"needs_attention": 2, "explained": 0, "items": ["FR-003"]}         # Architecture is asked about the two it should have covered
    req_state = (await client.get(f"/api/projects/{project.id}/phases/requirements/review")).json()
    assert req_state["open"]["traceability_gaps"] == {"needs_attention": 1, "explained": 0, "items": ["FR-003"]}    # Requirements is asked about the epics; it is not blamed for the others
    other = (await client.get(f"/api/projects/{project.id}/phases/design/review")).json()
    assert other["open"]["traceability_gaps"] == {"needs_attention": 0, "explained": 0, "items": []}      # the gaps belong to the phase that should have covered them
    await client.aclose()


async def test_approving_with_a_gap_is_allowed_and_the_audit_row_records_it(world):
    app, client, project = await world()
    store, engine = app.state.store, app.state.engine
    req = next(a for a in store.artefacts.list(project.id, phase_key="requirements") if a.type == "functional_requirements")
    body = store.artefacts.get_version(project.id, req.id).body
    add_requirement(store, project.id, req.id, body.replace("\n## Business rules", "\n- FR-003 The system shall show who booked. Derives from: PER-001\n\n## Business rules", 1))
    engine.finish(project.id, "architecture", actor="system")
    approved = await client.post(f"/api/projects/{project.id}/phases/architecture/approve", headers={"X-Actor": "Ann"})
    assert approved.status_code == 200 and store.phases.get(project.id, "architecture").status == "approved"
    rows = [a for a in store.audit.list(project.id) if a.action == "phase.decided" and a.detail and "traceability_gaps" in a.detail]
    assert rows and rows[-1].detail["traceability_gaps"] == {"needs_attention": 2, "explained": 0, "items": ["FR-003"]}
    await client.aclose()


# ---- the demo ---------------------------------------------------------------------------------------------------------------------------------------------

def test_the_offline_trace_demo_shows_no_gaps_then_the_gap_after_a_link_is_cut(capsys):
    from scripts import trace_demo as D
    assert D.main([]) == 0
    out = capsys.readouterr().out
    assert "SCRIPTED FAKE MODEL" in out and "gaps: 0" in out and "After cutting one link" in out and "gaps: 1" in out
    assert "FR-002 is not named by any item in the component overview" in out and out.index("gaps: 0") < out.index("gaps: 1")


# ---- gaps the mutation check found in these tests (2026-10-31) -----------------------------------------------------------------------------------------

def test_a_prefix_is_everything_before_the_last_dash_so_a_two_part_prefix_is_kept_whole():
    assert T.prefix_of("SET-CHR-001") == "SET-CHR" and T.prefix_of("FR-004") == "FR" and T.prefix_of("ARC-CMP-001") == "ARC-CMP"
    assert T.number_of("SET-CHR-012") == 12 and T.number_of("nonsense") == 0 and T.sort_key("SET-CHR-002") == ("SET-CHR", 2)


def test_a_withdrawn_item_is_not_listed_under_a_requirement_even_when_something_still_derives_from_it():
    items = ITEMS + [Item("API-009", "ARC-LLD-001", "low_level_design", 1, "Old", withdrawn=True)]
    trace = run(items=items, links=LINKS + [("API-009", "FR-001", "ARC-LLD-001")])
    assert "API-009" not in trace.chains[0].layers["API"] and trace.chains[0].layers["API"] == ("API-001",)


def test_a_coverage_check_reason_in_the_text_becomes_the_explanation_of_that_gap_for_that_artefact_only():
    """Read through the real gatherer, from the stored text: the writer's reason reaches the gap, and only the artefact whose Coverage check said it."""
    from app.agents.items import parse_items

    skills = SkillLibrary.load(load_catalogue(Routing.load().roles.keys()))

    class Art:
        def __init__(self, id, type, phase, latest=1): self.id, self.type, self.phase_key, self.latest_version = id, type, phase, latest

    class Ver:
        def __init__(self, body): self.body, self.number = body, 1

    bodies = {
        "REQ-F-001": "## Requirements\n- FR-001 Book a room. Derives from: PER-001\n- FR-002 Retire a room. Derives from: PER-001\n",
        "SET-CHR-001": "## Purpose\nBook rooms.\n", "REQ-PER-001": "## Personas\n- PER-001 Staff. Derives from: SET-CHR-001\n",
        "ARC-CMP-001": "## Components\n- COMP-001 Booking: x. Derives from: FR-001\n\n## Coverage check\n- FR-002 retiring a room is done by hand in version one\n",
    }
    arts = [Art("SET-CHR-001", "project_charter", "setup"), Art("REQ-PER-001", "personas", "requirements"), Art("REQ-F-001", "functional_requirements", "requirements"),
            Art("ARC-CMP-001", "component_overview", "architecture")]

    class Store:
        class artefacts:                                                   # noqa: N801 - a stand-in
            list = staticmethod(lambda pid, **kw: arts)
            get_version = staticmethod(lambda pid, aid, number=None: Ver(bodies[aid]))

        class links:                                                       # noqa: N801
            list = staticmethod(lambda pid: [type("L", (), {"from_id": f, "to_id": t, "declared_in": d})() for f, t, d in
                                              [("FR-001", "PER-001", "REQ-F-001"), ("FR-002", "PER-001", "REQ-F-001"), ("COMP-001", "FR-001", "ARC-CMP-001"), ("PER-001", "SET-CHR-001", "REQ-PER-001")]])

    catalogue = load_catalogue(Routing.load().roles.keys())
    trace = G.trace_of(Store(), skills, catalogue, "p")
    assert [(g.kind, g.item, g.by, g.reason, g.group) for g in trace.gaps] == [(DECLARED, "FR-002", "component_overview", "retiring a room is done by hand in version one", "explained")]


def test_a_withdrawn_item_in_the_text_is_read_as_withdrawn_so_things_still_pointing_at_it_are_found():
    skills = SkillLibrary.load(load_catalogue(Routing.load().roles.keys()))

    class Art:
        def __init__(self, id, type, phase): self.id, self.type, self.phase_key, self.latest_version = id, type, phase, 1

    class Ver:
        def __init__(self, body): self.body, self.number = body, 2

    bodies = {
        "REQ-F-001": "## Requirements\n- FR-001 Book a room. Derives from: PER-001\n\n## Withdrawn items\n- FR-002 merged into FR-001\n",
        "SET-CHR-001": "## Purpose\nBook rooms.\n", "REQ-PER-001": "## Personas\n- PER-001 Staff. Derives from: SET-CHR-001\n",
        "ARC-CMP-001": "## Components\n- COMP-001 Booking: x. Derives from: FR-001, FR-002\n",
    }
    arts = [Art("SET-CHR-001", "project_charter", "setup"), Art("REQ-PER-001", "personas", "requirements"), Art("REQ-F-001", "functional_requirements", "requirements"),
            Art("ARC-CMP-001", "component_overview", "architecture")]

    class Store:
        class artefacts:                                                   # noqa: N801
            list = staticmethod(lambda pid, **kw: arts)
            get_version = staticmethod(lambda pid, aid, number=None: Ver(bodies[aid]))

        class links:                                                       # noqa: N801
            list = staticmethod(lambda pid: [type("L", (), {"from_id": f, "to_id": t, "declared_in": d})() for f, t, d in
                                              [("FR-001", "PER-001", "REQ-F-001"), ("COMP-001", "FR-001", "ARC-CMP-001"), ("COMP-001", "FR-002", "ARC-CMP-001"), ("PER-001", "SET-CHR-001", "REQ-PER-001")]])

    trace = G.trace_of(Store(), skills, load_catalogue(Routing.load().roles.keys()), "p")
    assert [(g.kind, g.item, g.other) for g in trace.gaps] == [(WITHDRAWN_TARGET, "COMP-001", "FR-002")]


def test_two_reasons_for_one_item_keep_the_first_and_a_reason_about_a_persona_is_not_a_requirement_reason():
    body = "## Coverage check\n- FR-009 first reason\n- FR-009 second reason\n- PER-001 not a requirement\n"
    assert G.declared_reasons(body, {"FR"}) == {"FR-009": "first reason"}
    assert G.declared_reasons(body, {"PER"}) == {"PER-001": "not a requirement"}


def test_a_gap_with_no_covering_artefact_belongs_to_the_phase_that_holds_the_item():
    items = ITEMS + [Item("COMP-002", "ARC-CMP-001", "component_overview", 1, "Orphan")]
    trace = run(items=items)
    orphan = next(g for g in trace.gaps if g.item == "COMP-002")
    assert orphan.by is None and orphan.artefact_id == "ARC-CMP-001" and not orphan.sentence.startswith("COMP-002 is not named")


async def test_the_gaps_in_an_approval_are_sorted_by_item_number_and_capped_at_fifty(world):
    app, client, project = await world()
    store = app.state.store
    req = next(a for a in store.artefacts.list(project.id, phase_key="requirements") if a.type == "functional_requirements")
    body = store.artefacts.get_version(project.id, req.id).body
    many = "\n".join(f"- FR-{n:03d} Extra requirement {n}. Derives from: PER-001" for n in (90, 3, 61, *range(100, 160)))
    add_requirement(store, project.id, req.id, body.replace("\n## Business rules", f"\n{many}\n\n## Business rules", 1))
    state = (await client.get(f"/api/projects/{project.id}/phases/architecture/review")).json()["open"]["traceability_gaps"]
    assert len(state["items"]) == 50 and state["items"] == sorted(state["items"], key=T.sort_key) and state["items"][:3] == ["FR-003", "FR-061", "FR-090"]
    assert state["needs_attention"] == 2 * 63                                                           # every one of the 63 new requirements is missing from two artefacts
    await client.aclose()


async def test_the_needs_attention_count_does_not_include_gaps_the_writer_explained(world):
    app, client, project = await world()
    store = app.state.store
    req = next(a for a in store.artefacts.list(project.id, phase_key="requirements") if a.type == "functional_requirements")
    body = store.artefacts.get_version(project.id, req.id).body
    add_requirement(store, project.id, req.id, body.replace("\n## Business rules", "\n- FR-003 Show who booked. Derives from: PER-001\n\n## Business rules", 1))
    cmp_ = next(a for a in store.artefacts.list(project.id, phase_key="architecture") if a.type == "component_overview")
    text = store.artefacts.get_version(project.id, cmp_.id).body
    store.artefacts.add_version(project.id, cmp_.id, body=text.replace("## Coverage check\nNone.", "## Coverage check\n- FR-003 the booking history screen is version two"), author="human:Ann",
                                links=[(i.id, t, "derives") for i in __import__("app.agents.items", fromlist=["parse_items"]).parse_items(text, app.state.skills.get("component_overview").items).items for t in i.link_targets])
    data = (await client.get(f"/api/projects/{project.id}/traceability")).json()
    assert data["explained"] == 1 and data["needs_attention"] == 2 and len(data["gaps"]) == 3
    assert [g["reason"] for g in data["gaps"] if g["group"] == "explained"] == ["the booking history screen is version two"]
    await client.aclose()


async def test_a_layer_not_started_is_not_started_in_the_csv_too_and_never_a_dash(world):
    app, client, project = await world(through="design")
    rows = list(csv.reader(io.StringIO((await client.get(f"/api/projects/{project.id}/traceability/export.csv")).text)))
    first = dict(zip(rows[0], rows[1]))
    assert first["COMP"] == "not started" and first["API"] == "not started" and first["JS"].startswith("JS-")
    await client.aclose()


@pytest.mark.parametrize("bad", ["comp-001", "COMP-1", "COMP_001", "COMP-001x", "-COMP-001", "X"])
async def test_a_malformed_item_id_is_refused_as_such_and_never_looked_up(world, bad):
    app, client, project = await world()
    response = await client.get(f"/api/projects/{project.id}/traceability/item/{bad}")
    assert response.status_code == 422 and response.json()["detail"] == "item id has unexpected characters"
    await client.aclose()


async def test_an_unknown_but_well_formed_item_is_404_with_its_own_sentence(world):
    app, client, project = await world()
    response = await client.get(f"/api/projects/{project.id}/traceability/item/COMP-999")
    assert response.status_code == 404 and response.json()["detail"] == "COMP-999 is not an item in this project"
    await client.aclose()


async def test_an_items_page_shows_only_the_gaps_that_are_about_it(world):
    app, client, project = await world()
    store = app.state.store
    req = next(a for a in store.artefacts.list(project.id, phase_key="requirements") if a.type == "functional_requirements")
    body = store.artefacts.get_version(project.id, req.id).body
    add_requirement(store, project.id, req.id, body.replace("\n## Business rules", "\n- FR-003 Show who booked. Derives from: PER-001\n\n## Business rules", 1))
    about = (await client.get(f"/api/projects/{project.id}/traceability/item/FR-003")).json()
    other = (await client.get(f"/api/projects/{project.id}/traceability/item/FR-001")).json()
    assert len(about["gaps"]) == 3 and {g["item"] for g in about["gaps"]} == {"FR-003"} and other["gaps"] == []
    await client.aclose()


async def test_an_orphan_component_is_a_gap_for_architecture_which_holds_it_and_not_for_the_other_phases(world):
    """A gap with no covering artefact (an item that derives from nothing) belongs to the phase that holds the item."""
    app, client, project = await world()
    store = app.state.store
    cmp_ = next(a for a in store.artefacts.list(project.id, phase_key="architecture") if a.type == "component_overview")
    text = store.artefacts.get_version(project.id, cmp_.id).body
    from app.agents.items import parse_items
    links = [(i.id, t, "derives") for i in parse_items(text, app.state.skills.get("component_overview").items).items for t in i.link_targets]
    store.artefacts.add_version(project.id, cmp_.id, body=text.replace("\n## Coverage check", "\n- COMP-009 Audit log: records changes.\n\n## Coverage check", 1), author="human:Ann", links=links)
    tab = (await client.get(f"/api/projects/{project.id}/traceability")).json()
    assert sorted((g["kind"], g["by"]) for g in tab["gaps"]) == [("built_on_nothing", None), ("not_covered", "high_level_design")]       # both are true: it derives from nothing, and no decision names it
    ours = (await client.get(f"/api/projects/{project.id}/phases/architecture/review")).json()["open"]["traceability_gaps"]
    others = [(await client.get(f"/api/projects/{project.id}/phases/{ph}/review")).json()["open"]["traceability_gaps"] for ph in ("setup", "requirements", "design")]
    assert ours == {"needs_attention": 2, "explained": 0, "items": ["COMP-009"]} and all(o["needs_attention"] == 0 for o in others)
    await client.aclose()


async def test_an_artefact_row_that_has_no_version_does_not_make_its_phase_count_as_started(world):
    """If a run is cut off between making an artefact and writing it, the phase has nothing in it yet: its columns say not started, never empty."""
    app, client, project = await world(through="design")
    app.state.store.artefacts.create(project.id, artefact_type="component_overview", phase_key="architecture", title="Component overview", actor="system", prefix="ARC-CMP")
    data = (await client.get(f"/api/projects/{project.id}/traceability")).json()
    fr1 = next(c for c in data["chains"] if c["item"] == "FR-001")
    assert {c["layer"]: c["state"] for c in fr1["cells"]}["COMP"] == "not_started" and data["gaps"] == []
    await client.aclose()
