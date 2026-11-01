"""The Architecture diagrams (S14b): a list is read, checked, laid out and drawn by the server, in two looks. A model never draws; the pictures are derived
from the text each time they are asked for, pass the S13 sanitiser unchanged, and never raise. The layout rules (no line through a box, no two lines on one
stretch, right angles only) are checked on random designs as well as on chosen ones."""
from __future__ import annotations

import contextlib
import itertools
import random
import re
import signal
import time

import httpx
import pytest

from app.architecture import diagram as D
from app.architecture import layout as LY
from app.architecture import style as ST
from app.architecture.diagram import FLOW, MAX_LINES, MAX_NODES, USECASE, diagram_problems, edges_of, render_all, render_diagram, short_name, usecases_of
from app.architecture.layout import Edge, layout_flow, number_text
from app.design.sanitise import MAX_DIAGRAM_CHARS, MAX_OUTPUT_CHARS, drawing_problems, sanitise_svg
from app.main import create_app
from scripts import architecture_demo as A

from . import _fakes as F

pytestmark = pytest.mark.anyio
ANN = {"X-Actor": "Ann"}
KNOWN = {"COMP-001", "COMP-002", "COMP-003", "PER-001", "PER-002", "FR-001", "FR-002", "IFC-001", "IFC-002"}
LABELS = {"COMP-001": "Booking service", "COMP-002": "Room administration service", "COMP-003": "Room and booking store", "PER-001": "Office staff member", "PER-002": "Room administrator"}

GOOD_FLOW = """## Overview
Three calls.

## Flow
- FLOW-001 COMP-001 -> COMP-003: asks if a room is free. Derives from: IFC-001, COMP-001, COMP-003
- FLOW-002 COMP-003 -> COMP-001: answers free or taken. Derives from: IFC-001, COMP-001, COMP-003
- FLOW-003 COMP-002 -> COMP-003: changes the room list. Derives from: IFC-002, COMP-002, COMP-003
"""
GOOD_UC = """## Overview
Two people.

## Use cases
- UC-001 Find a free room: staff look at the rooms free for a time. Derives from: PER-001, FR-001
- UC-002 Maintain rooms: the administrator adds and retires rooms. Derives from: PER-002, FR-002
"""
REAL_PAIRS = [(1, 3), (3, 7), (7, 3), (3, 4), (4, 3), (3, 6), (6, 3), (3, 8), (8, 3), (3, 1), (1, 5), (5, 8), (8, 5), (5, 6), (6, 5), (5, 1), (1, 6), (6, 1),
              (1, 7), (2, 6), (2, 7), (6, 7), (7, 6), (6, 8)]          # the 24 calls of the first live design


@contextlib.contextmanager
def within(seconds: int, label: str):
    """Fail a test that runs far too long instead of letting it hang the suite (Unix only; elsewhere the plain time assertion still applies)."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def stop(_signum, _frame):
        raise AssertionError(f"{label}: still running after {seconds}s")

    previous = signal.signal(signal.SIGALRM, stop)
    signal.alarm(seconds)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


def calls(*pairs: tuple[str, str]) -> list[Edge]:
    return [Edge(f"FLOW-{i:03d}", a, b, "x") for i, (a, b) in enumerate(pairs, start=1)]


def flow_text(*pairs: tuple[str, str]) -> str:
    return "## Flow\n" + "\n".join(f"- FLOW-{i:03d} {a} -> {b}: x. Derives from: IFC-001" for i, (a, b) in enumerate(pairs, start=1)) + "\n"


def real_pairs() -> list[tuple[str, str]]:
    return [(f"COMP-{a:03d}", f"COMP-{b:03d}") for a, b in REAL_PAIRS]


# ---- reading --------------------------------------------------------------------------------------------------------------------------------

def test_an_arrow_line_is_read_into_who_calls_whom_and_what_is_sent():
    items = D.parse_items(GOOD_FLOW, [D.SPECS[FLOW]]).items
    edges, bad = edges_of(items)
    assert bad == [] and [(e.item_id, e.source, e.target, e.label) for e in edges] == [
        ("FLOW-001", "COMP-001", "COMP-003", "asks if a room is free."), ("FLOW-002", "COMP-003", "COMP-001", "answers free or taken."),
        ("FLOW-003", "COMP-002", "COMP-003", "changes the room list.")]


@pytest.mark.parametrize("arrow", ["->", "-->", "→", "—>"])
def test_the_arrow_may_be_written_in_the_ways_a_model_writes_it(arrow):
    body = f"## Flow\n- FLOW-001 COMP-001 {arrow} COMP-002: asks. Derives from: IFC-001\n"
    [edge], bad = edges_of(D.parse_items(body, [D.SPECS[FLOW]]).items)
    assert bad == [] and (edge.source, edge.target) == ("COMP-001", "COMP-002")


@pytest.mark.parametrize("line", [
    "FLOW-001 COMP-001 and COMP-002 talk. Derives from: IFC-001",
    "FLOW-001 COMP-001 -> COMP-002 Derives from: IFC-001",
    "FLOW-001 COMP-001 -> COMP-002: Derives from: IFC-001",
    "FLOW-001 COMP-001 -> COMP-002:    Derives from: IFC-001",
    "FLOW-001 Booking service -> Store: asks. Derives from: IFC-001",
])
def test_a_line_that_is_not_an_arrow_is_unreadable_and_is_reported_by_its_id(line):
    edges, bad = edges_of(D.parse_items(f"## Flow\n- {line}\n", [D.SPECS[FLOW]]).items)
    assert bad == ["FLOW-001"] and edges == []


def test_a_use_case_is_named_by_the_words_before_the_first_colon_and_its_actors_are_the_personas_it_derives_from():
    [a, b] = usecases_of(D.parse_items(GOOD_UC, [D.SPECS[USECASE]]).items)
    assert (a.item_id, a.name, a.actors) == ("UC-001", "Find a free room", ("PER-001",))
    assert (b.item_id, b.name, b.actors) == ("UC-002", "Maintain rooms", ("PER-002",))


def test_requirements_and_components_in_derives_from_are_not_actors():
    body = "## Use cases\n- UC-001 Reserve: x. Derives from: PER-001, PER-002, FR-001, COMP-001\n"
    [case] = usecases_of(D.parse_items(body, [D.SPECS[USECASE]]).items)
    assert case.actors == ("PER-001", "PER-002")


@pytest.mark.parametrize("text, name", [
    ("Booking service: decides if a room is free", "Booking service"),
    ("Booking service, which decides", "Booking service"),
    ("Booking service. Keeps no data.", "Booking service"),
    ("Booking service - decides", "Booking service"),
    ("A" * 60, "A" * 39 + "…"),
    ("  Spaced   out   name  : x", "Spaced out name"),
    ("Office staff member (floors two to four). Goal: x", "Office staff member"),
    ("(only brackets)", "(only brackets)"),
])
def test_a_short_name_is_the_text_up_to_its_first_break_without_brackets_and_is_cut_at_forty_characters(text, name):
    assert short_name(text) == name and len(short_name(text)) <= 40


# ---- the check ------------------------------------------------------------------------------------------------------------------------------

def test_a_good_flow_and_a_good_use_case_list_have_no_problems():
    assert diagram_problems(FLOW, GOOD_FLOW, KNOWN) == []
    assert diagram_problems(USECASE, GOOD_UC, KNOWN) == []


def test_any_other_artefact_is_never_checked_as_a_diagram():
    assert diagram_problems("personas", "## Flow\n- FLOW-001 nonsense\n", KNOWN) == []
    assert diagram_problems("", GOOD_FLOW, KNOWN) == []


def test_a_call_naming_a_component_that_does_not_exist_is_refused_and_the_sentence_names_it():
    [problem] = diagram_problems(FLOW, GOOD_FLOW.replace("COMP-003: asks", "COMP-009: asks"), KNOWN)
    assert problem == "FLOW-001 names COMP-009, which is not a component in the component overview you were given; use only COMP IDs from it"


def test_a_call_naming_something_that_is_not_a_component_at_all_is_refused():
    problems = diagram_problems(FLOW, GOOD_FLOW.replace("COMP-001 -> COMP-003: asks", "FR-001 -> COMP-003: asks"), KNOWN)
    assert any(p.startswith("FLOW-001 names FR-001") for p in problems)


def test_a_call_from_a_component_to_itself_is_refused():
    body = GOOD_FLOW.replace("COMP-001 -> COMP-003: asks", "COMP-001 -> COMP-001: asks")
    assert "FLOW-001 is a call from COMP-001 to itself; a flow shows calls between two different components" in diagram_problems(FLOW, body, KNOWN)


def test_an_unreadable_line_is_refused_with_the_shape_to_write():
    [problem] = diagram_problems(FLOW, "## Flow\n- FLOW-001 the booking service talks to the store. Derives from: IFC-001\n", KNOWN)
    assert problem.startswith("FLOW-001 is not written as an arrow; write it as 'FLOW-001 COMP-001 -> COMP-002: what is sent'")


def test_a_flow_with_more_than_twelve_components_is_refused_with_the_limit_and_twelve_is_allowed():
    ids = {f"COMP-{n:03d}" for n in range(1, 15)}

    def chain(n):
        return flow_text(*[(f"COMP-{i:03d}", f"COMP-{i + 1:03d}") for i in range(1, n)])
    assert MAX_NODES == 12 and "the flow touches 14 components; the limit is 12. Group related components or leave the minor ones out" in diagram_problems(FLOW, chain(14), ids)
    assert diagram_problems(FLOW, chain(12), ids) == []


def test_a_flow_with_more_than_twenty_four_arrows_is_refused_with_the_limit_and_twenty_four_is_allowed():
    ids = {"COMP-001", "COMP-002"}

    def many(n):
        return flow_text(*[("COMP-001", "COMP-002")] * n)
    assert MAX_LINES == 24 and "the flow has 25 arrows; the limit is 24. Keep the calls that matter most" in diagram_problems(FLOW, many(25), ids)
    assert diagram_problems(FLOW, many(24), ids) == []


def test_a_use_case_with_an_actor_that_is_not_a_persona_you_were_given_is_refused():
    assert "UC-002 names PER-009, which is not a persona you were given" in diagram_problems(USECASE, GOOD_UC.replace("PER-002, FR-002", "PER-009, FR-002"), KNOWN)


def test_a_use_case_with_no_actor_is_refused():
    problems = diagram_problems(USECASE, GOOD_UC.replace("Derives from: PER-002, FR-002", "Derives from: FR-002"), KNOWN)
    assert "UC-002 has no actor; name at least one persona (a PER ID) under 'Derives from:'" in problems


def test_a_use_case_with_no_requirement_is_refused_and_a_non_functional_one_will_do():
    assert "UC-002 names no requirement; add the FR or NFR ID it serves under 'Derives from:'" in diagram_problems(USECASE, GOOD_UC.replace("PER-002, FR-002", "PER-002"), KNOWN)
    assert diagram_problems(USECASE, "## Use cases\n- UC-001 Stay available: x. Derives from: PER-001, NFR-001\n", KNOWN | {"NFR-001"}) == []


def test_a_use_case_with_no_name_is_refused():
    assert any(p.startswith("UC-001 has no name") for p in diagram_problems(USECASE, "## Use cases\n- UC-001 : staff look. Derives from: PER-001, FR-001\n", KNOWN))


def test_a_use_case_diagram_with_more_than_twelve_boxes_is_refused_and_twelve_is_allowed():
    def build(cases: int) -> str:
        return "## Use cases\n" + "\n".join(f"- UC-{n:03d} Do thing {n}: x. Derives from: PER-001, FR-001" for n in range(1, cases + 1))
    assert diagram_problems(USECASE, build(11), KNOWN) == []                             # 1 actor + 11 use cases = 12 boxes
    assert "the diagram has 1 actors and 12 use cases, 13 boxes in all; the limit is 12. Merge related use cases" in diagram_problems(USECASE, build(12), KNOWN)


def test_the_same_problem_is_never_reported_twice():
    body = "## Flow\n- FLOW-001 COMP-009 -> COMP-009: x. Derives from: IFC-001\n" + "\n".join(f"- FLOW-{n:03d} COMP-001 -> COMP-009: x. Derives from: IFC-001" for n in range(2, 5))
    problems = diagram_problems(FLOW, body, KNOWN)
    assert len(problems) == len(set(problems))
    assert problems.count("FLOW-001 names COMP-009, which is not a component in the component overview you were given; use only COMP IDs from it") == 1


# ---- the layout: columns --------------------------------------------------------------------------------------------------------------------

def cols_of(*pairs):
    return {b.key: b.col for b in layout_flow(calls(*pairs), {}).boxes}


def test_a_chain_runs_left_to_right_one_column_a_step():
    assert cols_of(("COMP-001", "COMP-002"), ("COMP-002", "COMP-003"), ("COMP-003", "COMP-004")) == {"COMP-001": 0, "COMP-002": 1, "COMP-003": 2, "COMP-004": 3}


def test_a_reply_does_not_push_a_component_into_a_later_column():
    assert cols_of(("COMP-001", "COMP-002"), ("COMP-002", "COMP-001")) == {"COMP-001": 0, "COMP-002": 1}


def test_a_call_that_closes_a_loop_does_not_move_anything():
    assert cols_of(("COMP-001", "COMP-002"), ("COMP-002", "COMP-003"), ("COMP-003", "COMP-001")) == {"COMP-001": 0, "COMP-002": 1, "COMP-003": 2}


def test_a_component_goes_after_the_longest_path_that_reaches_it():
    assert cols_of(("COMP-001", "COMP-002"), ("COMP-002", "COMP-003"), ("COMP-001", "COMP-003"))["COMP-003"] == 2


def test_two_parts_of_a_flow_with_no_link_are_both_drawn():
    got = cols_of(("COMP-001", "COMP-002"), ("COMP-003", "COMP-004"))
    assert set(got) == {"COMP-001", "COMP-002", "COMP-003", "COMP-004"} and got["COMP-001"] == got["COMP-003"] == 0


def test_a_flow_where_every_component_is_in_a_loop_still_starts_somewhere():
    got = cols_of(("COMP-001", "COMP-002"), ("COMP-002", "COMP-003"), ("COMP-003", "COMP-001"), ("COMP-003", "COMP-002"))
    assert set(got) == {"COMP-001", "COMP-002", "COMP-003"} and min(got.values()) == 0


def test_boxes_in_a_column_follow_the_rows_of_the_boxes_they_are_joined_to():
    # COMP-001 above COMP-002; COMP-003 (written first) hangs off the LOWER one, COMP-004 off the upper one: COMP-004 must come first
    box = {b.key: b for b in layout_flow(calls(("COMP-001", "COMP-004"), ("COMP-002", "COMP-003")), {}).boxes}
    assert box["COMP-001"].y < box["COMP-002"].y and box["COMP-004"].y < box["COMP-003"].y
    flipped = {b.key: b for b in layout_flow(calls(("COMP-002", "COMP-003"), ("COMP-001", "COMP-004")), {}).boxes}
    assert flipped["COMP-002"].y < flipped["COMP-001"].y and flipped["COMP-003"].y < flipped["COMP-004"].y


def test_boxes_joined_to_the_same_box_keep_the_order_they_were_written():
    box = {b.key: b for b in layout_flow(calls(("COMP-001", "COMP-002"), ("COMP-001", "COMP-003"), ("COMP-001", "COMP-004")), {}).boxes}
    assert box["COMP-002"].y < box["COMP-003"].y < box["COMP-004"].y


def test_a_reply_to_a_call_does_not_put_the_caller_a_column_further_on():
    """COMP-002 calls COMP-004 and COMP-004 answers it. If the answer counted as a call, COMP-002 would be pushed a column to the right of COMP-004."""
    got = cols_of(("COMP-003", "COMP-004"), ("COMP-002", "COMP-004"), ("COMP-004", "COMP-002"))
    assert got == {"COMP-003": 0, "COMP-004": 1, "COMP-002": 0}


def test_when_two_boxes_are_equally_close_the_one_written_first_goes_first():
    box = {b.key: b for b in layout_flow(calls(("COMP-002", "COMP-003"), ("COMP-001", "COMP-003")), {}).boxes}
    assert box["COMP-002"].y < box["COMP-001"].y                                 # COMP-002 was written first, so it is drawn above COMP-001


def test_boxes_in_a_column_are_moved_towards_the_boxes_they_are_joined_to():
    """COMP-005 is written after COMP-003 but is joined to the box that is drawn higher up, so it must come above COMP-003, not below it."""
    pairs = [("COMP-004", "COMP-001"), ("COMP-005", "COMP-002"), ("COMP-003", "COMP-001"), ("COMP-005", "COMP-002")]
    box = {b.key: b for b in layout_flow(calls(*pairs), {}).boxes}
    assert box["COMP-004"].col == box["COMP-005"].col == box["COMP-003"].col == 0
    assert [k for k, _ in sorted(((k, b.y) for k, b in box.items() if b.col == 0), key=lambda t: t[1])] == ["COMP-004", "COMP-003", "COMP-005"]


def test_the_same_list_always_gives_the_same_layout():
    pairs = [("COMP-001", "COMP-002"), ("COMP-002", "COMP-003"), ("COMP-003", "COMP-001"), ("COMP-001", "COMP-004"), ("COMP-004", "COMP-002")]
    assert layout_flow(calls(*pairs), {}) == layout_flow(calls(*pairs), {})


# ---- the layout: lines ----------------------------------------------------------------------------------------------------------------------------------

def segs(link):
    return list(zip(link.points, link.points[1:]))


def through(box, p, q):
    x1, x2 = sorted((p[0], q[0])); y1, y2 = sorted((p[1], q[1]))
    on_edge = (p[0] == q[0] and p[0] in (box.x, box.x + box.w)) or (p[1] == q[1] and p[1] in (box.y, box.y + box.h))
    return x1 < box.x + box.w and x2 > box.x and y1 < box.y + box.h and y2 > box.y and not on_edge


def share_a_stretch(a, b):
    (p, q), (r, s) = a, b
    if p[0] == q[0] == r[0] == s[0]:
        return min(max(p[1], q[1]), max(r[1], s[1])) - max(min(p[1], q[1]), min(r[1], s[1])) > 0
    if p[1] == q[1] == r[1] == s[1]:
        return min(max(p[0], q[0]), max(r[0], s[0])) - max(min(p[0], q[0]), min(r[0], s[0])) > 0
    return False


def on_edge_of(b, pt):
    return (pt[0] in (b.x, b.x + b.w) and b.y <= pt[1] <= b.y + b.h) or (pt[1] in (b.y, b.y + b.h) and b.x <= pt[0] <= b.x + b.w)


def faults(lay) -> dict[str, int]:
    """Every way a layout can be wrong that matters, counted. All must be zero."""
    boxes = {b.key: b for b in lay.boxes}
    found = dict(diagonal=0, outside=0, through_a_box=0, shared_stretch=0, end_off_a_box=0, boxes_overlap=0, badge_on_a_box=0)
    for link in lay.links:
        for p, q in segs(link):
            found["diagonal"] += p[0] != q[0] and p[1] != q[1]
            found["outside"] += min(p[0], q[0]) < 0 or min(p[1], q[1]) < 0 or max(p[0], q[0]) > lay.width or max(p[1], q[1]) > lay.height
            found["through_a_box"] += sum(through(b, p, q) for b in boxes.values())
        found["end_off_a_box"] += not (on_edge_of(boxes[link.a], link.points[0]) and on_edge_of(boxes[link.b], link.points[-1]))
    for l1, l2 in itertools.combinations(lay.links, 2):
        found["shared_stretch"] += any(share_a_stretch(a, b) for a in segs(l1) for b in segs(l2))
    for b1, b2 in itertools.combinations(lay.boxes, 2):
        found["boxes_overlap"] += not (b1.x + b1.w <= b2.x or b2.x + b2.w <= b1.x or b1.y + b1.h <= b2.y or b2.y + b2.h <= b1.y)
    for link in lay.links:
        r = (link.badge.x, link.badge.y, link.badge.w, link.badge.h)
        found["badge_on_a_box"] += any(not (r[0] + r[2] <= b.x or b.x + b.w <= r[0] or r[1] + r[3] <= b.y or b.y + b.h <= r[1]) for b in boxes.values())
    return {k: int(v) for k, v in found.items()}


def random_design(rng: random.Random):
    n = rng.randint(2, 12)
    ids = [f"COMP-{i:03d}" for i in range(1, n + 1)]
    return [Edge(f"FLOW-{k:03d}", *rng.sample(ids, 2), "x") for k in range(1, rng.randint(n - 1, 24) + 1)]


@pytest.mark.parametrize("seed", [7, 99, 2026])
def test_on_random_designs_no_line_runs_through_a_box_along_another_or_off_at_an_angle(seed):
    rng = random.Random(seed)
    total: dict[str, int] = {}
    with within(60, "random layouts"):
        for _ in range(120):
            for key, count in faults(layout_flow(random_design(rng), {})).items():
                total[key] = total.get(key, 0) + count
    assert total == {k: 0 for k in total} and len(total) == 7, total


def test_the_real_design_from_the_first_live_run_has_none_of_these_faults():
    lay = layout_flow(calls(*real_pairs()), {})
    assert faults(lay) == {k: 0 for k in faults(lay)}
    assert len(lay.boxes) == 8 and len(lay.links) == 14                                   # 24 calls, but a call and its reply share one line


def test_a_call_and_its_reply_are_one_line_with_a_head_at_each_end():
    [link] = layout_flow(calls(("COMP-001", "COMP-002"), ("COMP-002", "COMP-001")), {}).links
    assert link.numbers == (1, 2) and link.head_a and link.head_b and link.badge.text == "1,2"


def test_a_call_with_no_reply_has_a_head_at_its_target_only():
    [link] = layout_flow(calls(("COMP-001", "COMP-002")), {}).links
    assert (link.head_a, link.head_b) == (False, True) and (link.a, link.b) == ("COMP-001", "COMP-002")


def test_a_call_that_goes_backwards_has_its_head_at_the_earlier_box():
    lay = layout_flow(calls(("COMP-001", "COMP-002"), ("COMP-003", "COMP-001"), ("COMP-002", "COMP-003")), {})
    back = next(l for l in lay.links if l.numbers == (2,))
    assert (back.a, back.b) == ("COMP-001", "COMP-003") and back.head_a and not back.head_b


def test_two_lines_between_neighbouring_columns_never_share_a_vertical_stretch():
    lay = layout_flow(calls(("COMP-001", "COMP-002"), ("COMP-003", "COMP-002"), ("COMP-001", "COMP-004"), ("COMP-003", "COMP-004")), {})
    assert faults(lay)["shared_stretch"] == 0 and len(lay.links) == 4


def test_a_line_leaving_one_box_and_a_line_arriving_at_the_next_do_not_run_along_each_other():
    """The right side of one box and the left side of the box beside it face each other across one gap, so their lines need different heights."""
    lay = layout_flow(calls(("COMP-004", "COMP-001"), ("COMP-006", "COMP-005"), ("COMP-005", "COMP-001"), ("COMP-006", "COMP-005"), ("COMP-001", "COMP-004")), {})
    assert faults(lay)["shared_stretch"] == 0


def test_no_call_ever_joins_two_boxes_in_one_column_so_every_line_runs_between_columns():
    rng = random.Random(5)
    with within(60, "columns"):
        for _ in range(300):
            lay = layout_flow(random_design(rng), {})
            col = {b.key: b.col for b in lay.boxes}
            assert all(col[l.a] < col[l.b] for l in lay.links)


def test_a_line_that_skips_a_column_goes_round_the_boxes_in_between():
    lay = layout_flow(calls(("COMP-001", "COMP-002"), ("COMP-002", "COMP-003"), ("COMP-001", "COMP-003")), {})
    skip = next(l for l in lay.links if {l.a, l.b} == {"COMP-001", "COMP-003"})
    assert len(skip.points) >= 5 and faults(lay)["through_a_box"] == 0


def test_a_box_is_tall_enough_for_every_line_to_have_its_own_place_on_its_side():
    lay = layout_flow(calls(*[("COMP-001", f"COMP-{n:03d}") for n in range(2, 8)]), {})
    first = next(b for b in lay.boxes if b.key == "COMP-001")
    starts = sorted({l.points[0][1] for l in lay.links})
    assert len(starts) == 6 and all(first.y < y < first.y + first.h for y in starts) and first.h > LY.NODE_H
    assert all(b - a >= 14 for a, b in zip(starts, starts[1:]))


def test_the_gap_between_two_columns_is_wide_enough_for_the_number_on_its_short_line():
    lay = layout_flow(calls(("COMP-001", "COMP-002"), ("COMP-002", "COMP-001"), ("COMP-002", "COMP-001")), {})
    [link] = lay.links
    assert link.numbers == (1, 2, 3) and link.badge.text == "1–3"
    box = {b.key: b for b in lay.boxes}
    assert box["COMP-002"].x - (box["COMP-001"].x + box["COMP-001"].w) >= link.badge.w + 36 and faults(lay)["badge_on_a_box"] == 0


# ---- the numbers on the lines, and the key --------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("numbers, text", [
    ([5], "5"), ([1, 2], "1,2"), ([1, 2, 3], "1–3"), ([1, 2, 3, 4, 5], "1–5"), ([2, 7, 9], "2,7,9"), ([3, 1, 2], "1–3"),
    ([1, 3, 5, 7], "1,3,5 +1"), ([1, 3, 5, 7, 9, 11], "1,3,5 +3"), ([1, 2, 3, 5, 6, 7, 9, 10, 11, 13], "1–3,5–7,9–11 +1"), ([4, 4, 4], "4"),
])
def test_the_numbers_on_a_line_are_shortened_to_runs_and_never_lose_the_count(numbers, text):
    assert number_text(numbers) == text


def test_the_key_lists_every_call_in_order_with_its_names_and_its_sentence():
    names = {"COMP-001": "Booking service", "COMP-003": "Room and booking store"}
    lay = layout_flow(calls(("COMP-001", "COMP-003"), ("COMP-003", "COMP-001"), ("COMP-002", "COMP-003")), names)
    assert [(k.number, k.source, k.target) for k in lay.key] == [(1, "Booking service", "Room and booking store"), (2, "Room and booking store", "Booking service"),
                                                                 (3, "COMP-002", "Room and booking store")]
    assert all(k.y > lay.key_top for k in lay.key) and lay.height > max(k.y for k in lay.key)
    assert len({(k.x, k.y) for k in lay.key}) == 3


def test_a_long_key_is_set_in_columns_across_the_picture():
    lay = layout_flow(calls(*[(f"COMP-{(n % 9) + 1:03d}", f"COMP-{((n + 3) % 9) + 1:03d}") for n in range(24)]), {})
    assert len({k.x for k in lay.key}) >= 2 and max(k.x for k in lay.key) + LY.KEY_COL_W <= lay.width + LY.PAD


# ---- drawing: the two looks ----------------------------------------------------------------------------------------------------------------------------------

def test_there_are_exactly_two_looks_and_they_differ_in_colour_not_in_layout():
    assert ST.STYLES == ("drawio", "notion") and ST.DEFAULT == "drawio"
    a, b = (render_diagram(FLOW, GOOD_FLOW, LABELS, s) for s in ST.STYLES)
    assert a and b and a != b
    assert re.findall(r'points="[^"]+"', a) == re.findall(r'points="[^"]+"', b)                  # the same lines in the same places
    assert re.findall(r' x="[^"]+" y="[^"]+" width', a) == re.findall(r' x="[^"]+" y="[^"]+" width', b)


def test_the_draw_io_look_is_blue_boxes_and_the_notion_look_is_soft_grey_cards():
    d = render_diagram(FLOW, GOOD_FLOW, LABELS, "drawio")
    n = render_diagram(FLOW, GOOD_FLOW, LABELS, "notion")
    assert "#dae8fc" in d and "#6c8ebf" in d and "#dae8fc" not in n
    assert "#f7f6f3" in n and "#e3e2de" in n and "#f7f6f3" not in d
    assert ST.THEMES["drawio"].box_radius < ST.THEMES["notion"].box_radius and ST.THEMES["notion"].title_weight == "bold"


def test_an_unknown_look_draws_nothing_and_the_default_is_the_draw_io_look():
    assert render_diagram(FLOW, GOOD_FLOW, LABELS, "neon") is None and render_diagram(FLOW, GOOD_FLOW, LABELS, "") is None
    assert render_diagram(FLOW, GOOD_FLOW, LABELS) == render_diagram(FLOW, GOOD_FLOW, LABELS, "drawio")
    assert ST.style_of("neon").key == "drawio" and ST.style_of(None).key == "drawio" and ST.style_of("notion").key == "notion"


def test_render_all_gives_nothing_when_even_one_look_cannot_be_drawn():
    """The screen lets the person switch looks, so it needs every look or none: half a set would leave a button that shows the wrong picture."""
    original = D.draw_flow
    try:
        D.draw_flow = lambda body, labels, style="drawio": original(body, labels, style) if style == "drawio" else ""
        assert render_diagram(FLOW, GOOD_FLOW, LABELS, "drawio") is not None and render_diagram(FLOW, GOOD_FLOW, LABELS, "notion") is None
        assert render_all(FLOW, GOOD_FLOW, LABELS) is None
    finally:
        D.draw_flow = original


def test_render_all_gives_every_look_or_nothing():
    both = render_all(FLOW, GOOD_FLOW, LABELS)
    assert set(both) == {"drawio", "notion"} and both["drawio"] != both["notion"]
    assert render_all(FLOW, "## Flow\n", LABELS) is None and render_all("personas", GOOD_FLOW, LABELS) is None


@pytest.mark.parametrize("style", ST.STYLES)
def test_the_flow_has_a_line_per_pair_a_head_per_arrival_a_number_per_line_and_a_key_row_per_call(style):
    svg = render_diagram(FLOW, GOOD_FLOW, LABELS, style)
    assert svg.count("<polyline ") == 2                                               # 1<->3 share one line; the third call has its own
    assert svg.count("<polygon ") == 3                                                # the pair has two heads, the single call one
    for sentence in ("asks if a room is free.", "answers free or taken.", "changes the room list."):
        assert sentence in svg                                                         # every call's sentence is in the key
    assert ">Calls<" in svg and ">Booking service<" in svg and ">Room and booking store<" in svg


@pytest.mark.parametrize("style", ST.STYLES)
def test_a_long_component_name_is_wrapped_on_two_lines_and_a_longer_one_ends_in_an_ellipsis(style):
    svg = render_diagram(FLOW, GOOD_FLOW, LABELS, style)
    assert ">Room administration<" in svg and ">service<" in svg
    long = render_diagram(FLOW, GOOD_FLOW, {**LABELS, "COMP-002": "An extremely long component name that cannot possibly fit in a box"}, style)
    assert long and "…" in long and "cannot possibly fit in a box" not in long


@pytest.mark.parametrize("style", ST.STYLES)
def test_a_box_shows_its_short_name_and_falls_back_to_its_id_when_the_name_is_unknown(style):
    assert ">Booking service<" in render_diagram(FLOW, GOOD_FLOW, LABELS, style)
    bare = render_diagram(FLOW, GOOD_FLOW, {}, style)
    assert bare and ">COMP-001<" in bare and "Booking service" not in bare


@pytest.mark.parametrize("style", ST.STYLES)
def test_a_long_sentence_is_clipped_in_the_key_and_the_picture_never_holds_all_of_it(style):
    long = "x" * 200
    svg = render_diagram(FLOW, f"## Flow\n- FLOW-001 COMP-001 -> COMP-002: {long}. Derives from: IFC-001\n", LABELS, style)
    assert svg and long not in svg and "…" in svg


@pytest.mark.parametrize("style", ST.STYLES)
def test_the_use_case_diagram_has_stick_figures_on_the_left_and_the_use_cases_inside_a_labelled_system_box(style):
    svg = render_diagram(USECASE, GOOD_UC, LABELS, style)
    assert svg.count("<ellipse ") == 2 and svg.count("<circle ") == 2 and ">System<" in svg and "stroke-dasharray" in svg
    assert ">Find a free room<" in svg and ">Maintain rooms<" in svg
    assert ">Office staff member<" in svg and ">Room administrator<" in svg or (">Office staff<" in svg and ">member<" in svg)
    assert svg.count("<line ") == 2 + 2 * 4                                          # two actor-to-use-case lines, and four strokes in each stick figure (body, arms, two legs)
    cx = [float(v) for v in re.findall(r"<circle cx=\"([0-9.]+)\"", svg)]
    ex = [float(v) for v in re.findall(r"<ellipse cx=\"([0-9.]+)\"", svg)]
    assert max(cx) < min(ex)


@pytest.mark.parametrize("style", ST.STYLES)
def test_a_use_case_with_two_actors_gets_a_line_from_each_and_a_long_name_wraps(style):
    body = "## Use cases\n- UC-001 Browse every room and its availability for a chosen day: both. Derives from: PER-001, PER-002, FR-001\n"
    svg = render_diagram(USECASE, body, LABELS, style)
    assert svg.count("<ellipse ") == 1 and svg.count("<line ") == 2 + 2 * 4                      # two actor-to-use-case lines, four strokes in each of the two figures
    assert ">Browse every room and its<" in svg or ">Browse every room and<" in svg


def test_actors_are_never_drawn_on_top_of_each_other():
    """Three actors who all take part in the same use case would all want the same height; each is pushed down to leave room for the one above."""
    body = "## Use cases\n- UC-001 Do one thing: x. Derives from: PER-001, PER-002, PER-003, FR-001\n"
    svg = render_diagram(USECASE, body, {"PER-001": "A", "PER-002": "B", "PER-003": "C"})
    tops = sorted(float(v) for v in re.findall(r'<circle cx="[0-9.]+" cy="([0-9.]+)"', svg))
    assert len(tops) == 3 and all(b - a >= D.ACTOR_H for a, b in zip(tops, tops[1:]))


def test_a_single_actor_and_a_single_use_case_are_drawn():
    assert render_diagram(USECASE, "## Use cases\n- UC-001 Find a room: x. Derives from: PER-001, FR-001\n", LABELS)


@pytest.mark.parametrize("kind, body", [
    (FLOW, ""), (FLOW, "## Flow\n"), (FLOW, "## Flow\n- FLOW-001 not an arrow. Derives from: IFC-001\n"), (FLOW, "nothing at all"),
    (USECASE, ""), (USECASE, "## Use cases\n"), (USECASE, "## Use cases\n- UC-001 : x. Derives from: PER-001, FR-001\n"),
    ("personas", GOOD_FLOW), ("", GOOD_FLOW),
])
def test_nothing_to_draw_gives_none_and_never_raises(kind, body):
    assert render_diagram(kind, body, LABELS) is None


@pytest.mark.parametrize("kind, body", [("personas", GOOD_UC), ("personas", GOOD_FLOW), ("", GOOD_UC), ("project_charter", GOOD_UC), ("flow_diagram ", GOOD_FLOW), ("USECASE_DIAGRAM", GOOD_UC)])
def test_only_the_two_diagram_artefacts_ever_get_a_picture_whatever_their_text_looks_like(kind, body):
    assert render_diagram(kind, body, LABELS) is None and render_all(kind, body, LABELS) is None


def test_a_flow_with_more_boxes_than_the_limit_is_not_drawn_rather_than_drawn_cramped():
    assert render_diagram(FLOW, flow_text(*[(f"COMP-{n:03d}", f"COMP-{n + 1:03d}") for n in range(1, 14)]), {}) is None
    assert render_diagram(FLOW, flow_text(*[(f"COMP-{n:03d}", f"COMP-{n + 1:03d}") for n in range(1, 12)]), {}) is not None


def test_a_use_case_diagram_over_the_box_limit_is_not_drawn_and_one_at_the_limit_is():
    def build(cases: int) -> str:
        return "## Use cases\n" + "\n".join(f"- UC-{n:03d} Do {n}: x. Derives from: PER-001, FR-001" for n in range(1, cases + 1))
    assert render_diagram(USECASE, build(11), LABELS) is not None and render_diagram(USECASE, build(12), LABELS) is None
    assert render_diagram(USECASE, build(25), LABELS) is None


@pytest.mark.parametrize("style", ST.STYLES)
def test_every_picture_passes_the_sanitiser_unchanged_so_the_viewer_shows_exactly_what_was_made(style):
    for kind, body in ((FLOW, GOOD_FLOW), (USECASE, GOOD_UC)):
        svg = render_diagram(kind, body, LABELS, style)
        cleaned = sanitise_svg(svg, MAX_DIAGRAM_CHARS)
        assert cleaned.ok and not cleaned.changed and cleaned.svg == svg


def test_a_full_size_design_is_larger_than_one_screen_so_it_needs_the_higher_limit_and_still_fits_under_it():
    svg = render_diagram(FLOW, flow_text(*real_pairs()), {f"COMP-{n:03d}": f"Component number {n}" for n in range(1, 9)})
    assert svg is not None and MAX_OUTPUT_CHARS < len(svg) < MAX_DIAGRAM_CHARS
    assert not sanitise_svg(svg).ok                                                    # a model's drawing gets the small limit and this would be refused


def test_text_in_a_label_or_a_name_cannot_inject_markup_into_the_picture():
    evil = "<script>alert(1)</script>"
    svg = render_diagram(FLOW, f"## Flow\n- FLOW-001 COMP-001 -> COMP-002: {evil}. Derives from: IFC-001\n", {"COMP-001": evil, "COMP-002": '"><img src=x onerror=1>'})
    assert svg is not None and "<script" not in svg and "<img" not in svg and "&lt;script&gt;" in svg
    assert sanitise_svg(svg, MAX_DIAGRAM_CHARS).changed is False


def test_a_use_case_name_with_markup_is_escaped_in_the_picture():
    svg = render_diagram(USECASE, '## Use cases\n- UC-001 <b>Bold</b> & "quoted": x. Derives from: PER-001, FR-001\n', LABELS)
    assert svg is not None and "<b>" not in svg and "&lt;b&gt;Bold&lt;/b&gt; &amp;" in svg


def test_a_drawing_the_sanitiser_would_alter_is_not_drawn_at_all():
    original = D.draw_flow
    try:
        D.draw_flow = lambda body, labels, style="drawio": '<svg viewBox="0 0 10 10"><script>x()</script><rect x="1" y="1" width="2" height="2"/></svg>'
        assert render_diagram(FLOW, GOOD_FLOW, LABELS) is None
    finally:
        D.draw_flow = original


def test_an_error_while_drawing_gives_no_picture_instead_of_stopping_the_artefact_opening():
    original = D.draw_usecases

    def boom(body, labels, style="drawio"):
        raise RuntimeError("boom")
    try:
        D.draw_usecases = boom
        assert render_diagram(USECASE, GOOD_UC, LABELS) is None and render_all(USECASE, GOOD_UC, LABELS) is None
    finally:
        D.draw_usecases = original


@pytest.mark.parametrize("label, kind, body", [
    ("many arrows between two", FLOW, flow_text(*[("COMP-001", "COMP-002")] * 3000)),
    ("long chain", FLOW, flow_text(*[(f"COMP-{n:03d}", f"COMP-{n + 1:03d}") for n in range(1, 2000)])),
    ("huge label", FLOW, "## Flow\n- FLOW-001 COMP-001 -> COMP-002: " + "w " * 200_000 + ". Derives from: IFC-001\n"),
    ("many use cases", USECASE, "## Use cases\n" + "\n".join(f"- UC-{n:03d} Do {n}: x. Derives from: PER-001, FR-001" for n in range(1, 3000))),
])
def test_adversarial_sizes_finish_quickly_and_do_not_raise(label, kind, body):
    started = time.perf_counter()
    with within(10, label):
        diagram_problems(kind, body, KNOWN | {f"COMP-{n:03d}" for n in range(1, 2100)})
        render_diagram(kind, body, LABELS)
    assert time.perf_counter() - started < 5, label


def test_the_layout_is_quick_on_the_largest_design_the_check_allows():
    rng = random.Random(1)
    started = time.perf_counter()
    with within(10, "largest layout"):
        for _ in range(40):
            layout_flow([Edge(f"FLOW-{k:03d}", *rng.sample([f"COMP-{i:03d}" for i in range(1, 13)], 2), "x") for k in range(1, 25)], {})
    assert time.perf_counter() - started < 5


# ---- the larger limit is for the server's own diagrams only -----------------------------------------------------------------------------------------------

def _text_drawing(texts: int) -> str:
    return '<svg viewBox="0 0 10 10">' + ('<text x="1" y="1">' + "a" * 300 + "</text>") * texts + "</svg>"


def test_the_sanitiser_default_is_still_one_screen_and_a_caller_cannot_ask_for_more_than_the_cap():
    assert (MAX_OUTPUT_CHARS, MAX_DIAGRAM_CHARS) == (12_000, 60_000)
    medium, huge = _text_drawing(45), _text_drawing(250)
    assert MAX_OUTPUT_CHARS < len(medium) < MAX_DIAGRAM_CHARS < len(huge)
    assert not sanitise_svg(medium).ok and sanitise_svg(medium, MAX_DIAGRAM_CHARS).ok
    assert not sanitise_svg(huge, MAX_DIAGRAM_CHARS).ok and not sanitise_svg(huge, 10 ** 9).ok          # asking for a billion is still held to 60,000


def test_a_model_drawing_in_an_artefact_is_still_held_to_one_screen():
    """The check every reply and every hand edit passes uses the default limit, so the larger one cannot be reached by a model."""
    problems = drawing_problems("## A\n```svg\n" + _text_drawing(45) + "\n```\n")
    assert problems and "limited to 12000 characters" in problems[0]


# ---- the route and a person's edit ----------------------------------------------------------------------------------------------------------

@pytest.fixture
def world(make_settings):
    async def build(**settings):
        cfg = make_settings(**{**A.MODELS, "llm_retry_backoff_seconds": 0, "run_max_cost_usd": 0, **settings})
        app = create_app(cfg, provider=A.Scripted())
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=ANN)
        store, engine, runner = app.state.store, app.state.engine, app.state.runner
        from app.sample import BRIEF, FILENAME, NAME, POLICY

        project = store.projects.create(name=NAME, brief=BRIEF, actor="system")
        engine.open_project(project.id)
        store.context.add_document(project.id, FILENAME, POLICY, actor="human:demo")
        for phase in ("setup", "requirements", "design"):
            await runner.run_phase(project.id, phase)
            engine.finish(project.id, phase, actor="system"); engine.approve(project.id, phase, actor="human:demo")
        await runner.run_phase(project.id, "architecture")
        arts = {a.type: a for a in store.artefacts.list(project.id, phase_key="architecture")}
        return app, client, project, arts

    return build


async def test_a_diagram_artefact_comes_with_a_picture_in_each_look_drawn_from_the_text(world):
    app, client, project, arts = await world()
    flow = (await client.get(f"/api/projects/{project.id}/artefacts/{arts['flow_diagram'].id}")).json()
    assert set(flow["renderings"]) == {"drawio", "notion"} and "rendering" not in flow
    for svg in flow["renderings"].values():
        assert svg.startswith("<svg ") and ">Booking service<" in svg and "asks if a room is free." in svg
    uc = (await client.get(f"/api/projects/{project.id}/artefacts/{arts['usecase_diagram'].id}")).json()
    assert set(uc["renderings"]) == {"drawio", "notion"}
    for svg in uc["renderings"].values():                                                       # a name that does not fit one line wraps, so look for its words
        assert ">Reserve a room<" in svg and "Office staff" in svg and ">Room administrator<" in svg
    await client.aclose()


async def test_every_other_artefact_has_no_picture(world):
    app, client, project, arts = await world()
    for key in ("component_overview", "high_level_design", "low_level_design"):
        detail = (await client.get(f"/api/projects/{project.id}/artefacts/{arts[key].id}")).json()
        assert "renderings" in detail and detail["renderings"] is None, key
    await client.aclose()


async def test_the_pictures_are_never_stored_they_follow_the_text_of_the_version_shown(world):
    app, client, project, arts = await world()
    art = arts["flow_diagram"]
    body = app.state.store.artefacts.get_version(project.id, art.id).body
    edited = body.replace("changes the room list.", "updates the rooms.")
    assert edited != body
    assert (await client.put(f"/api/projects/{project.id}/artefacts/{art.id}", json={"body": edited})).status_code == 200
    new = (await client.get(f"/api/projects/{project.id}/artefacts/{art.id}")).json()
    old = (await client.get(f"/api/projects/{project.id}/artefacts/{art.id}", params={"version": 1})).json()
    assert all("updates the rooms." in s and "changes the room list." not in s for s in new["renderings"].values())
    assert all("changes the room list." in s and "updates the rooms." not in s for s in old["renderings"].values())
    await client.aclose()


async def test_a_hand_edit_that_points_a_call_at_a_component_that_does_not_exist_is_refused_with_the_reason_and_nothing_is_saved(world):
    app, client, project, arts = await world()
    art = arts["flow_diagram"]
    body = app.state.store.artefacts.get_version(project.id, art.id).body
    response = await client.put(f"/api/projects/{project.id}/artefacts/{art.id}", json={"body": body.replace("COMP-002 -> COMP-003", "COMP-002 -> COMP-009", 1)})
    assert response.status_code == 422 and any("COMP-009" in p for p in response.json()["detail"]["problems"])
    assert app.state.store.artefacts.get(project.id, art.id).latest_version == 1
    await client.aclose()


async def test_a_hand_edit_that_renames_what_is_sent_is_saved_and_redrawn_in_both_looks(world):
    app, client, project, arts = await world()
    art = arts["usecase_diagram"]
    body = app.state.store.artefacts.get_version(project.id, art.id).body
    saved = await client.put(f"/api/projects/{project.id}/artefacts/{art.id}", json={"body": body.replace("Find a free room", "Look for a room"), "note": "renamed"})
    assert saved.status_code == 200, saved.text
    detail = (await client.get(f"/api/projects/{project.id}/artefacts/{art.id}")).json()
    assert all(">Look for a room<" in s and "Find a free room" not in s for s in detail["renderings"].values())
    await client.aclose()


async def test_a_diagram_with_nothing_to_draw_still_opens_with_its_text_and_no_picture(world):
    app, client, project, arts = await world()
    art = arts["flow_diagram"]
    app.state.store.artefacts.add_version(project.id, art.id, body="## Overview\nx\n\n## Flow\n- FLOW-001 broken. Derives from: IFC-001\n", author="human:Ann")
    detail = await client.get(f"/api/projects/{project.id}/artefacts/{art.id}")
    assert detail.status_code == 200 and detail.json()["renderings"] is None and "FLOW-001 broken" in detail.json()["body"]
    await client.aclose()


async def test_the_flow_and_use_case_items_become_links_to_the_interfaces_components_and_personas_they_show(world):
    app, client, project, arts = await world()
    pairs = {(l.from_id, l.to_id) for l in app.state.store.links.list(project.id)}
    assert {("FLOW-001", "IFC-001"), ("FLOW-001", "COMP-001"), ("FLOW-001", "COMP-003"), ("FLOW-003", "IFC-002")} <= pairs
    assert {("UC-001", "PER-001"), ("UC-001", "FR-001"), ("UC-003", "PER-002"), ("UC-003", "FR-002")} <= pairs
    await client.aclose()


async def _architecture_with(make_settings, provider):
    app = create_app(make_settings(**{**A.MODELS, "llm_retry_backoff_seconds": 0, "run_max_cost_usd": 0}), provider=provider)    # a scratch folder, never the real database
    store, engine, runner = app.state.store, app.state.engine, app.state.runner
    from app.sample import BRIEF, FILENAME, NAME, POLICY

    project = store.projects.create(name=NAME, brief=BRIEF, actor="system")
    engine.open_project(project.id)
    store.context.add_document(project.id, FILENAME, POLICY, actor="human:demo")
    for phase in ("setup", "requirements", "design"):
        await runner.run_phase(project.id, phase)
        engine.finish(project.id, phase, actor="system"); engine.approve(project.id, phase, actor="human:demo")
    return await runner.run_phase(project.id, "architecture"), store, project


async def test_a_flow_that_leaves_an_interface_out_is_sent_back_by_the_coverage_rule(make_settings):
    class Gappy(A.Scripted):
        async def complete(self, model_id, request):
            if self._which(request) == "flow_diagram":
                from app.llm.types import ProviderResponse, Usage

                self.asked.append("flow_diagram")
                gappy = A.FLOW.replace("IFC-002", "IFC-001")                                                  # nothing shows IFC-002 any more
                assert gappy != A.FLOW
                return ProviderResponse(gappy, Usage(1200, 500), "stop")
            return await super().complete(model_id, request)

    result, _, _ = await _architecture_with(make_settings, Gappy())
    flow = next(o for o in result.outcomes if o.key == "flow_diagram")
    assert flow.state == "failed" and "IFC-002" in (flow.reason or "")


async def test_a_secret_in_a_diagram_label_is_caught_by_the_same_scanner(make_settings):
    class Leaky(A.Scripted):
        async def complete(self, model_id, request):
            if self._which(request) == "flow_diagram":
                from app.llm.types import ProviderResponse, Usage

                self.asked.append("flow_diagram")
                return ProviderResponse(A.FLOW.replace("asks if a room is free.", f"sends {F.AWS_KEY}."), Usage(1200, 500), "stop")
            return await super().complete(model_id, request)

    result, _, _ = await _architecture_with(make_settings, Leaky())
    flow = next(o for o in result.outcomes if o.key == "flow_diagram")
    assert flow.state == "failed" and F.AWS_KEY not in (flow.reason or "")


async def test_the_shared_body_check_applies_the_diagram_check_to_a_reply_and_an_edit_alike():
    from app.agents.checks import check_body
    from app.agents.items import ItemContext
    from app.agents.skills import SkillLibrary
    from app.llm.routing import Routing
    from app.workflow.definitions import load_catalogue

    skill = SkillLibrary.load(load_catalogue(Routing.load().roles.keys())).get("flow_diagram")
    ctx = ItemContext(specs=skill.items, covers=(), known=frozenset({"COMP-001", "COMP-002", "COMP-003", "IFC-001", "IFC-002"}))
    good = A.FLOW.split("<artefact>\n")[1].split("\n</artefact>")[0]
    assert any("COMP-009" in p and "not a component in the component overview" in p for p in check_body(good.replace("COMP-002 -> COMP-003", "COMP-002 -> COMP-009"), skill, set(ctx.known), ctx))
    assert not any("not a component" in p for p in check_body(good, skill, set(ctx.known), ctx))


def test_names_that_cannot_be_found_leave_the_boxes_showing_their_ids_and_never_raise():
    class Broken:
        class artefacts:                                                   # noqa: N801 - a stand-in for the store's attribute
            @staticmethod
            def list(*args, **kwargs):
                raise RuntimeError("database is down")

    class Skills:
        def get(self, key):
            return type("S", (), {"items": (D.ItemSpec("COMP", "Components"),), "artefact": type("A", (), {"phase_key": "architecture"})})()
    assert D.names_for(Skills(), Broken(), "p", FLOW) == {}
    assert D.names_for(Skills(), Broken(), "p", "personas") == {}
    assert D.names_for(type("S", (), {"get": lambda self, key: None})(), Broken(), "p", FLOW) == {}
