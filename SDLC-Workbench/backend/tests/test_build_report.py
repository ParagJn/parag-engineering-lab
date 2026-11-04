"""S18a: the test report. Written by the system from the recorded rounds, with no model; every ending worded correctly and none read as a pass."""
from __future__ import annotations

import pytest

from app.agents.skills import SkillLibrary
from app.build import report as R
from app.llm.routing import Routing
from app.models import BuildRound
from app.build import legacy

from ._build import make_body


@pytest.fixture(scope="module")
def library():
    return legacy.library()


def rnd(n, outcome="failed", *, loop="L1", id_=None, passed=0, failed=0, errors=0, skipped=0, artefact="", version=None, seconds=1.0, failures=()):
    return BuildRound(id=id_ if id_ is not None else n, project_id="p", run_id="r", loop_id=loop, round=n, artefact=artefact, version=version, outcome=outcome,
                      passed=passed, failed=failed, errors=errors, skipped=skipped, fingerprint="", failures=tuple(failures), seconds=seconds, at="t")


def fail(test="tests/test_a.py::test_one", kind="failed", message="assert 1 == 2"):
    return {"test": test, "kind": kind, "message": message}


# ---- which loop, how it ended ------------------------------------------------------------------------------------------------------------

def test_no_rounds_means_the_tests_were_never_run():
    assert R.last_loop([]) == () and R.ending_of(()) == "never_run"


def test_only_the_newest_loop_is_reported_and_its_rounds_are_in_order():
    old = [rnd(1, loop="old", id_=1), rnd(2, "passed", loop="old", id_=2)]
    new = [rnd(2, "passed", loop="new", id_=5), rnd(1, loop="new", id_=4)]
    assert [(r.loop_id, r.round) for r in R.last_loop(old + new)] == [("new", 1), ("new", 2)]


def test_the_ending_is_the_last_rounds_outcome():
    assert R.ending_of([rnd(1), rnd(2, "cap_reached")]) == "cap_reached"


# ---- the report ---------------------------------------------------------------------------------------------------------------------------

SPECS = ()


def test_a_passing_loop_says_so_with_its_counts_and_its_rounds():
    loop = [rnd(1, failed=1, artefact="backend_code", version=2, seconds=1.5), rnd(2, "passed", passed=3, seconds=2.0)]
    text = R.build_report(loop, None, SPECS, None)
    assert "All the generated tests passed." in text and "Final run: 3 passed, 0 failed, 0 errors, 0 skipped." in text
    assert "run 2 time(s)" in text and "3.5 seconds in all" in text
    assert "- Round 1: 0 passed, 1 failed, 0 errors, 0 skipped, in 1.5s. A fix was asked of the backend code (saved as version 2)." in text
    assert "- Round 2: 3 passed, 0 failed, 0 errors, 0 skipped, in 2.0s." in text and "## Failing tests\nNone." in text


@pytest.mark.parametrize("ending, words", [
    ("cap_reached", "still failing when the fix rounds ran out"), ("not_converging", "failed twice running"), ("blocked", "sandbox could not run anything"),
    ("no_tests", "No tests were found. That is not a pass."), ("invalid", "could not produce a valid fix"), ("stopped", "run was stopped"),
])
def test_every_ending_is_worded_and_none_reads_as_a_pass(ending, words):
    text = R.build_report([rnd(1, ending, failed=2, failures=[fail()])], None, SPECS, None)
    assert words in text and "All the generated tests passed." not in text


def test_an_ending_we_do_not_know_is_named_not_hidden():
    assert "ended as 'surprise'" in R.build_report([rnd(1, "surprise")], None, SPECS, None)


def test_no_rounds_says_the_tests_were_not_run_and_has_no_numbers():
    text = R.build_report([], None, SPECS, None)
    assert "have not been run yet" in text and "## Rounds\nNone." in text and "passed," not in text


def test_the_failing_tests_of_the_final_run_are_listed_with_their_first_lines_only():
    many = [fail(f"tests/test_a.py::test_{n}", message="m" * 500) for n in range(14)]
    text = R.build_report([rnd(1, "cap_reached", failed=14, failures=many)], None, SPECS, None)
    listed = [l for l in text.splitlines() if l.startswith("- tests/test_a.py::")]
    assert len(listed) == 10 and all(len(l.split(": ", 1)[1]) == 200 for l in listed)
    assert "...and 4 more not listed here." in text


def test_a_failure_count_larger_than_the_list_is_admitted_but_a_complete_list_adds_nothing():
    exact = [fail(f"t::{n}") for n in range(3)]
    assert "more not listed" not in R.build_report([rnd(1, "cap_reached", failed=3, failures=exact)], None, SPECS, None)
    assert "...and 2 more" in R.build_report([rnd(1, "cap_reached", failed=3, errors=2, failures=exact)], None, SPECS, None)


def test_a_failing_run_with_no_recorded_failure_says_so():
    assert "No failing test is recorded for the final run." in R.build_report([rnd(1, "cap_reached", failed=2)], None, SPECS, None)


@pytest.mark.parametrize("ending", ["stopped", "cap_reached", "not_converging", "blocked", "no_tests", "invalid"])
def test_only_a_pass_may_say_there_are_no_failing_tests_every_other_ending_admits_nothing_was_recorded(ending):
    text = R.build_report([rnd(1, ending, failed=0)], None, SPECS, None)
    assert "## Failing tests\nNo failing test is recorded for the final run." in text and "## Failing tests\nNone." not in text


def test_only_the_final_runs_failures_are_listed_not_an_earlier_rounds():
    early = rnd(1, failed=1, failures=[fail("tests/test_a.py::test_early")])
    late = rnd(2, "cap_reached", failed=1, failures=[fail("tests/test_a.py::test_late")])
    text = R.build_report([early, late], None, SPECS, None)
    assert "test_late" in text and "test_early" not in text


# ---- the test files and the endpoints they name ----------------------------------------------------------------------------------------

def test_the_test_files_are_listed_from_the_saved_suite(library):
    body = make_body([("tests/test_a.py", "def test_a(): pass"), ("tests/test_b.py", "def test_b(): pass")], "TSF")
    text = R.build_report([rnd(1, "passed", passed=2)], body, library.get("test_suite").items, None)
    assert "## Test files\n- tests/test_a.py\n- tests/test_b.py" in text


def test_with_no_suite_the_file_list_says_none(library):
    assert "## Test files\nNone." in R.build_report([rnd(1, "no_tests")], None, SPECS, None)


DESIGN = "## Endpoints\n- API-001 GET /a. Derives from: FR-001\n- API-002 GET /b. Derives from: FR-001\n- API-003 POST /c. Derives from: FR-001\n## Tables\n- TBL-001 t. Derives from: FR-001\n"


def test_coverage_counts_the_endpoints_a_test_file_names_and_lists_the_rest(library):
    tests = make_body([("tests/test_a.py", "x")], "TSF").replace("Derives from: TBL-001", "Derives from: API-001, API-003")
    cover = R.coverage(DESIGN, library.get("low_level_design").items, tests, library.get("test_suite").items)
    assert (cover.endpoints, cover.named, cover.unnamed) == (("API-001", "API-002", "API-003"), ("API-001", "API-003"), ("API-002",))
    text = R.build_report([rnd(1, "passed", passed=1)], tests, library.get("test_suite").items, cover)
    assert "2 of 3 endpoint(s)" in text and "Not named by any test: API-002." in text and "what the tests say about themselves" in text


def test_a_suite_that_names_every_endpoint_lists_no_gap(library):
    tests = make_body([("tests/test_a.py", "x")], "TSF").replace("Derives from: TBL-001", "Derives from: API-001, API-002, API-003")
    cover = R.coverage(DESIGN, library.get("low_level_design").items, tests, library.get("test_suite").items)
    text = R.build_report([rnd(1, "passed", passed=1)], tests, library.get("test_suite").items, cover)
    assert "3 of 3 endpoint(s)" in text and "Not named by any test" not in text


def test_a_table_or_other_item_is_not_mistaken_for_an_endpoint(library):
    tests = make_body([("tests/test_a.py", "x")], "TSF").replace("Derives from: TBL-001", "Derives from: TBL-001")
    cover = R.coverage(DESIGN, library.get("low_level_design").items, tests, library.get("test_suite").items)
    assert cover.endpoints == ("API-001", "API-002", "API-003") and cover.named == ()


def test_without_a_design_or_without_tests_nothing_is_claimed(library):
    assert R.coverage(None, library.get("low_level_design").items, "x", library.get("test_suite").items) is None
    assert R.coverage(DESIGN, library.get("low_level_design").items, None, library.get("test_suite").items) is None
    assert "nothing can be said about which endpoints" in R.build_report([rnd(1, "passed", passed=1)], None, SPECS, None)


def test_the_report_always_ends_by_saying_no_model_was_asked():
    assert "No model was asked what the tests did." in R.build_report([rnd(1, "passed", passed=1)], None, SPECS, None)


def test_the_same_rounds_give_the_same_report():
    loop = [rnd(1, failed=1, failures=[fail()]), rnd(2, "cap_reached", failed=1, failures=[fail()])]
    assert R.build_report(loop, None, SPECS, None) == R.build_report(loop, None, SPECS, None)
