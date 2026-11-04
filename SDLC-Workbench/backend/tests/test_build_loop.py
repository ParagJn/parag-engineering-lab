"""S17b-3: the write -> test -> fix loop. A scripted developer, the real sandbox, a real runtime. The tests are REALLY run: a developer who claims success in
words but whose code still fails is not believed. No live model is called."""
from __future__ import annotations

import itertools

import pytest

from app.agents.runtime import AgentRuntime
from app.agents.skills import SkillLibrary
from app.build import loop as L
from app.build.inner import latest_body
from app.build.service import BuildService
from app.guardrails.scan import Scanner
from app.llm.gateway import Gateway
from app.llm.providers.mock import MockProvider
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.run.budget import Meter
from app.sandbox import profile as OS
from app.sandbox.pytest_report import Failure, RunReport
from app.sandbox.runner import Sandbox
from app.sandbox.service import SandboxService
from app.build import legacy
from app.workflow.engine import WorkflowEngine

from ._build import make_body

MODELS = dict(
    ibm_ica_model_id="m-sonnet", ibm_ica_fallback_model_id="m-sonnet", ibm_ica_haiku_model_id="m-haiku",
    ibm_ica_openai_model_id="m-openai", ibm_ica_gemini_model_id="m-gemini",
    ibm_ica_price_input_per_mtok="2", ibm_ica_price_output_per_mtok="10",
    ibm_ica_openai_price_input_per_mtok="2", ibm_ica_openai_price_output_per_mtok="10",
)
LLD = ("## Overview\nx\n## Endpoints\n- API-001 GET /notes lists notes. Derives from: FR-001\n## Tables\n- TBL-001 notes: id, text. Derives from: FR-001\n"
       "## Rules\n- RUL-001 A note has text. Derives from: FR-001\n## Coverage check\nNone\n## Open questions\nNone")
AWS = "AKIA" + "IOSFODNN7EXAMPLE"


def backend(returns: str) -> list[tuple[str, str]]:
    return [("backend/main.py", f"from fastapi import FastAPI\napp = FastAPI()\n\n@app.get('/notes')\ndef notes():\n    return {returns}\n")]


GOOD, BAD = backend("[]"), backend('{"items": []}')
BROKEN_CODE = [("backend/main.py", "def f(:\n    pass\n")]
TESTS = [("tests/test_notes.py", "from fastapi.testclient import TestClient\nfrom backend.main import app\n\n\ndef test_list_is_empty():\n    assert TestClient(app).get('/notes').json() == []\n")]
BROKEN_TESTS = [("tests/test_notes.py", "import nosuchmodule\n\n\ndef test_list_is_empty():\n    assert True\n")]


def text_of(entries, prefix):
    return make_body(entries, prefix).replace("Derives from: TBL-001", "Derives from: TBL-001, API-001")


def reply(entries, prefix, claim=""):
    return ProviderResponse(f"<artefact>\n{text_of(entries, prefix)}\n</artefact>\n{claim}", Usage(1000, 200), "stop")


def fix(entries, prefix="BEF", claim=""):
    return reply(entries, prefix, claim)


pytestmark = [pytest.mark.anyio, pytest.mark.sandbox, pytest.mark.skipif(not OS.sandbox_available(), reason="this machine has no sandbox-exec")]


@pytest.fixture(scope="module")
def catalogue():
    return legacy.catalogue()


@pytest.fixture(scope="module")
def sandbox_box():
    return Sandbox(scanner=Scanner())


@pytest.fixture
def world(make_settings, store, project, catalogue, sandbox_box):
    def build(saved_backend=BAD, saved_tests=TESTS, rounds=3, sandbox=None, **settings):
        cfg = make_settings(**{**MODELS, "build_fix_rounds": rounds, **settings})
        provider = MockProvider()
        ids = itertools.count(1)

        async def no_sleep(_):
            return None

        gateway = Gateway(cfg, Routing.load(), provider, store, sleep=no_sleep, call_id_factory=lambda: f"call{next(ids)}")
        engine = WorkflowEngine(catalogue, store)
        library = legacy.library(catalogue)
        runtime = AgentRuntime(cfg, store, gateway, catalogue, engine, library)
        engine.open_project(project.id)
        store.phases.ensure(project.id, "build", actor="system")
        store.phases.set_status(project.id, "build", "running", actor="system")
        service = SandboxService(cfg, store, Scanner(), sandbox or sandbox_box)
        builder = BuildService(service)
        for key in ("low_level_design", "high_level_design", "functional_requirements"):
            skill = library.get(key)
            store.artefacts.create_and_add_version(project.id, artefact_type=key, phase_key=skill.artefact.phase_key, title=skill.artefact.name,
                                                   prefix=skill.artefact.id_prefix, body=LLD if key == "low_level_design" else "## Overview\nx\n", author="human:seed")
        for key, prefix, entries in (("backend_code", "BEF", saved_backend), ("test_suite", "TSF", saved_tests)):
            if entries:
                skill = library.get(key)
                store.artefacts.create_and_add_version(project.id, artefact_type=key, phase_key="build", title=skill.artefact.name,
                                                       prefix=skill.artefact.id_prefix, body=text_of(entries, prefix), author="human:seed")
        loop = L.FixLoop(cfg, store, runtime, library, builder, service, new_id=lambda: "loop-1")
        return loop, provider, store, service, library

    return build


def rows(store, project):
    return store.build_rounds.list(project.id)


# ---- the pure parts ------------------------------------------------------------------------------------------------------------------

def failure(test="tests/test_a.py::test_a", kind="failed", message="assert 1 == 2"):
    return Failure(kind, test, message, "detail")


def report(*failures, status="ran", passed=0, failed=None, errors=0, exit_code=1, skipped=0, reason=""):
    failed = sum(1 for f in failures if f.kind == "failed") if failed is None else failed
    return RunReport(status, exit_code, passed, failed, errors, skipped, 0, 0, 0.5, tuple(failures), reason=reason)


def test_the_same_failing_set_gives_the_same_fingerprint_in_any_order():
    a, b = failure("t::a"), failure("t::b")
    assert L.fingerprint(report(a, b)) == L.fingerprint(report(b, a)) and len(L.fingerprint(report(a, b))) == 16


def test_a_different_failing_set_or_kind_gives_a_different_fingerprint():
    a, b = failure("t::a"), failure("t::b")
    assert L.fingerprint(report(a)) != L.fingerprint(report(b)) != L.fingerprint(report(a, b))
    assert L.fingerprint(report(failure("t::a", "failed"))) != L.fingerprint(report(failure("t::a", "error")))


def test_a_run_with_nothing_failing_has_the_empty_fingerprint_and_the_message_does_not_matter():
    assert L.fingerprint(report(passed=3, exit_code=0)) == ""
    assert L.fingerprint(report(failure(message="one"))) == L.fingerprint(report(failure(message="two")))


@pytest.mark.parametrize("rep, expected", [
    (report(failure(kind="failed")), "backend_code"),
    (report(failure(kind="error")), "test_suite"),
    (report(failure(kind="failed"), failure("t::b", kind="error")), "test_suite"),
    (report(status="collection_error", exit_code=2), "test_suite"),
    (report(status="collection_error", exit_code=2, failed=0), "test_suite"),
    (report(failed=2), "backend_code"),
    (report(errors=1, failed=0), "backend_code"),
    (report(passed=3, exit_code=0), None),
])
def test_who_is_asked_to_fix_what(rep, expected):
    assert L.route(rep) == expected


@pytest.mark.parametrize("rep, expected", [
    (report(passed=3, exit_code=0), "ok"),
    (report(failure()), "broken"),
    (report(status="unavailable", exit_code=None, reason="no protection"), "blocked"),
    (report(status="refused", exit_code=None, reason="refused"), "blocked"),
    (report(status="no_tests", exit_code=5), "no_tests"),
    (report(status="ran", exit_code=0, passed=0), "no_tests"),
    (report(status="timed_out", exit_code=None), "broken"),
    (report(status="crashed", exit_code=1), "broken"),
    (report(status="cut_off", exit_code=1), "broken"),
    (report(status="ran", exit_code=0, passed=0, skipped=2), "broken"),
])
def test_how_a_run_of_the_tests_is_read(rep, expected):
    assert L.classify(rep) == expected


def test_what_the_developer_is_told_has_the_round_the_counts_and_a_few_failures():
    many = [failure(f"tests/test_a.py::test_{n}", message="m" * 900) for n in range(25)]
    lines = L.fix_feedback(report(*many, passed=4, skipped=1), "backend_code", 2, 3)
    text = "\n".join(lines)
    assert "round 2 of 3" in text and "4 passed, 25 failed, 0 errors, 1 skipped" in text and "first 10 of 25" in text
    assert text.count("- tests/test_a.py::test_") == 10 and "test_10" not in text and "m" * 401 not in text and "m" * 400 in text
    assert lines[-1].startswith("Fix the code.")


def test_a_test_engineer_is_told_to_fix_the_tests_and_a_collection_error_says_so():
    lines = L.fix_feedback(report(status="collection_error", exit_code=2, failed=0), "test_suite", 1, 3)
    assert any("could not collect the tests" in l for l in lines) and lines[-1].startswith("Fix the tests.")


def test_an_abnormal_end_is_named_in_what_the_developer_is_told():
    text = "\n".join(L.fix_feedback(report(status="timed_out", exit_code=None, failed=0, reason="took too long"), "backend_code", 1, 3))
    assert "timed_out" in text and "took too long" in text


def test_one_failure_reads_as_a_failure_not_failures():
    assert "The failure (first 1 of 1)" in "\n".join(L.fix_feedback(report(failure()), "backend_code", 1, 3))


def test_the_record_keeps_at_most_ten_failures_as_three_fields():
    kept = L.record_failures(report(*[failure(f"t::{n}") for n in range(15)]))
    assert len(kept) == 10 and set(kept[0]) == {"test", "kind", "message"}


def test_the_seven_results_are_the_ones_the_spec_names():
    assert L.RESULTS == ("converged", "cap_reached", "not_converging", "stopped", "blocked", "no_tests", "invalid")


# ---- converging ------------------------------------------------------------------------------------------------------------------------

async def test_a_scripted_developer_fixes_the_backend_in_round_two_and_the_loop_converges(world, project):
    loop, provider, store, service, _ = world()
    provider.queue("m-openai", fix(GOOD))
    result = await loop.run(project.id, run_id="run-1")
    assert (result.result, result.ok, result.loop_id, result.calls) == ("converged", True, "loop-1", 1)
    assert [(n.number, n.artefact, n.version, n.outcome) for n in result.rounds] == [(1, "backend_code", 2, "failed"), (2, "", None, "passed")]
    assert result.rounds[0].failed == 1 and result.rounds[1].passed == 1 and result.last.all_passed
    assert "all 1 test(s) passed after 2 run(s)" in result.reason
    assert service.read_file(project.id, "backend/main.py") == GOOD[0][1]


async def test_a_project_that_already_passes_is_judged_after_one_run_and_no_model_is_called(world, project):
    loop, provider, *_ = world(saved_backend=GOOD)
    result = await loop.run(project.id)
    assert result.result == "converged" and len(result.rounds) == 1 and result.calls == 0 and provider.calls == []


async def test_the_first_run_of_the_tests_is_against_what_is_saved_not_what_an_unsaved_attempt_left(world, project):
    loop, provider, store, service, _ = world(saved_backend=GOOD)
    service.write_file(project.id, "backend/main.py", "this is not python (\n", actor="human:Ann")
    result = await loop.run(project.id)
    assert result.result == "converged" and provider.calls == []


async def test_the_fix_is_asked_of_the_backend_developer_with_the_real_failure(world, project):
    loop, provider, *_ = world()
    provider.queue("m-openai", fix(GOOD))
    await loop.run(project.id)
    request = provider.calls[0].request
    sent = request.messages[0].content
    assert request.role == "backend_developer" and "round 1 of 3" in sent and "0 passed, 1 failed" in sent
    assert "tests/test_notes.py::test_list_is_empty" in sent and "Fix the code." in sent
    assert "Your previous draft" in sent and '{"items": []}' in sent                    # the saved backend is shown, to be improved rather than rewritten


async def test_a_developer_who_claims_success_but_whose_code_still_fails_is_not_believed(world, project):
    loop, provider, *_ = world(rounds=3)
    provider.queue("m-openai", *[fix(BAD, claim="All tests pass now, I verified it.")] * 3)
    result = await loop.run(project.id)
    assert result.result != "converged" and not result.ok and result.last.failed == 1


# ---- the cap, the repeat ---------------------------------------------------------------------------------------------------------------

def three_endpoint_world():
    """Tests for /a, /b and /c; each version of the backend serves two of them, so each run fails a DIFFERENT test."""
    tests = [("tests/test_notes.py", "from fastapi.testclient import TestClient\nfrom backend.main import app\n\n\n"
                                     + "\n\n".join(f"def test_{p}():\n    assert TestClient(app).get('/{p}').status_code == 200\n" for p in "abc"))]

    def code(*served):
        routes = "\n".join(f"@app.get('/{p}')\ndef {p}():\n    return []\n" for p in served)
        return [("backend/main.py", f"from fastapi import FastAPI\napp = FastAPI()\n{routes}")]
    return tests, code("b", "c"), code("a", "c"), code("a", "b")


async def test_a_developer_who_never_gets_there_stops_at_exactly_the_cap_with_a_different_failure_each_time(world, project):
    tests, v1, v2, v3 = three_endpoint_world()
    loop, provider, *_ = world(saved_backend=v1, saved_tests=tests, rounds=2)
    provider.queue("m-openai", fix(v2), fix(v3))
    result = await loop.run(project.id)
    assert result.result == "cap_reached" and result.calls == 2 and len(provider.calls) == 2
    assert [n.outcome for n in result.rounds] == ["failed", "failed", "cap_reached"] and [n.number for n in result.rounds] == [1, 2, 3]
    assert len({n.fingerprint for n in result.rounds}) == 3
    assert "1 of 3 test(s) still failing after 2 fix round(s)" in result.reason


async def test_the_cap_is_the_setting_and_one_round_means_one_fix(world, project):
    tests, v1, v2, v3 = three_endpoint_world()
    loop, provider, *_ = world(saved_backend=v1, saved_tests=tests, rounds=1)
    provider.queue("m-openai", fix(v2), fix(v3))
    result = await loop.run(project.id)
    assert result.result == "cap_reached" and len(provider.calls) == 1 and [n.number for n in result.rounds] == [1, 2]


async def test_a_larger_setting_allows_more_fixes(world, project):
    tests, v1, v2, v3 = three_endpoint_world()
    loop, provider, *_ = world(saved_backend=v1, saved_tests=tests, rounds=5)
    provider.queue("m-openai", fix(v2), fix(v3), fix(v1), fix(v2), fix(v3))
    result = await loop.run(project.id)
    assert result.result == "cap_reached" and len(provider.calls) == 5 and [n.number for n in result.rounds] == [1, 2, 3, 4, 5, 6]


async def test_an_explicit_rounds_argument_beats_the_setting(world, project):
    tests, v1, v2, v3 = three_endpoint_world()
    loop, provider, *_ = world(saved_backend=v1, saved_tests=tests, rounds=3)
    provider.queue("m-openai", fix(v2), fix(v3))
    result = await loop.run(project.id, rounds=1)
    assert result.result == "cap_reached" and len(provider.calls) == 1 and len(result.rounds) == 2


async def test_a_larger_argument_beats_a_smaller_setting(world, project):
    tests, v1, v2, v3 = three_endpoint_world()
    loop, provider, *_ = world(saved_backend=v1, saved_tests=tests, rounds=1)
    provider.queue("m-openai", fix(v2), fix(v3))
    result = await loop.run(project.id, rounds=2)
    assert result.result == "cap_reached" and len(provider.calls) == 2 and len(result.rounds) == 3


async def test_the_same_failing_tests_twice_running_stop_one_round_early(world, project):
    loop, provider, *_ = world(rounds=3)
    provider.queue("m-openai", fix(BAD), fix(BAD), fix(BAD))
    result = await loop.run(project.id)
    assert result.result == "not_converging" and result.calls == 1 and len(provider.calls) == 1
    assert [n.outcome for n in result.rounds] == ["failed", "not_converging"] and result.rounds[0].fingerprint == result.rounds[1].fingerprint
    assert "failed twice running" in result.reason


async def test_two_broken_runs_with_nothing_to_name_are_not_mistaken_for_a_repeat(world, project, monkeypatch):
    """A run that timed out or crashed lists no failing test, so its fingerprint is empty. Two of those in a row say nothing about whether the developer is
    repeating themselves, so the loop must go on and ask for the next fix."""
    loop, provider, *_ = world(rounds=2)
    provider.queue("m-openai", fix(BAD), fix(BAD))
    blank = RunReport("crashed", 1, 0, 0, 0, 0, 0, 0, 0.1, (), reason="no summary")
    monkeypatch.setattr(loop, "_run_tests", lambda project_id: blank)
    result = await loop.run(project.id)
    assert result.result == "cap_reached" and len(provider.calls) == 2 and [n.outcome for n in result.rounds] == ["failed", "failed", "cap_reached"]
    assert {n.fingerprint for n in result.rounds} == {""}


# ---- the other endings ------------------------------------------------------------------------------------------------------------------

async def test_a_broken_test_file_goes_to_the_test_engineer_first(world, project):
    loop, provider, store, service, _ = world(saved_backend=GOOD, saved_tests=BROKEN_TESTS)
    provider.queue("m-openai", fix(TESTS, "TSF"))
    result = await loop.run(project.id)
    request = provider.calls[0].request
    assert request.role == "test_engineer" and "could not collect the tests" in request.messages[0].content and "Fix the tests." in request.messages[0].content
    assert result.result == "converged" and result.rounds[0].artefact == "test_suite"


async def test_a_project_with_no_tests_is_no_tests_and_never_a_pass(world, project):
    loop, provider, *_ = world(saved_backend=GOOD, saved_tests=[("tests/test_notes.py", "x = 1\n")])
    result = await loop.run(project.id)
    assert (result.result, result.ok, result.calls) == ("no_tests", False, 0) and provider.calls == [] and "never reported as a pass" in result.reason
    assert [n.outcome for n in result.rounds] == ["no_tests"]


async def test_a_sandbox_that_cannot_run_is_blocked_and_nothing_is_judged(world, project):
    loop, provider, *_ = world(sandbox=Sandbox(sandbox_exec="/nonexistent/sandbox-exec", scanner=Scanner()))
    result = await loop.run(project.id)
    assert (result.result, result.ok, result.calls) == ("blocked", False, 0) and provider.calls == []
    assert "no command will be run" in result.reason and [n.outcome for n in result.rounds] == ["blocked"]


async def test_a_developer_who_cannot_produce_a_valid_reply_ends_the_loop_as_invalid_and_the_saved_code_is_put_back(world, project):
    loop, provider, store, service, library = world(rounds=3)
    provider.queue("m-openai", *[fix(BROKEN_CODE)] * 3)
    result = await loop.run(project.id)
    assert result.result == "invalid" and result.calls == 3 and not result.ok
    assert [n.outcome for n in result.rounds] == ["invalid"] and result.rounds[0].artefact == "backend_code"
    assert service.read_file(project.id, "backend/main.py") == BAD[0][1]                  # the failed attempt is gone; the saved version is back
    assert latest_body(store, project.id, library.get("backend_code")).count("def f(:") == 0


async def test_the_workspace_is_put_back_to_the_saved_versions_at_the_end_whatever_the_result(world, project):
    tests, v1, v2, v3 = three_endpoint_world()
    loop, provider, store, service, library = world(saved_backend=v1, saved_tests=tests, rounds=2)
    provider.queue("m-openai", fix(v2), fix(v3))
    result = await loop.run(project.id)
    saved = latest_body(store, project.id, library.get("backend_code"))
    assert service.read_file(project.id, "backend/main.py") in saved and result.workspace["backend_code"] == "written"
    assert result.workspace["database_schema"] == "none" and result.workspace["frontend_code"] == "none"


async def test_the_workspace_is_put_back_even_when_something_unexpected_goes_wrong(world, project, monkeypatch):
    """Not only a normal ending: an error nobody foresaw must not leave an unsaved attempt lying in the workspace for the next run to find."""
    loop, provider, store, service, library = world()

    async def explode(*args, **kwargs):
        service.write_file(project.id, "backend/main.py", "an unsaved attempt (\n", actor="human:Ann")
        raise RuntimeError("something unexpected")
    monkeypatch.setattr(loop.runtime, "run", explode)
    with pytest.raises(RuntimeError, match="something unexpected"):
        await loop.run(project.id)
    assert service.read_file(project.id, "backend/main.py") == BAD[0][1]


# ---- money and the clock ---------------------------------------------------------------------------------------------------------------

async def test_a_spent_budget_stops_the_loop_before_the_next_round_and_no_further_call_is_made(world, project):
    loop, provider, *_ = world(rounds=3)
    provider.queue("m-openai", fix(GOOD), fix(GOOD))
    meter = Meter(max_cost_usd=0.001, max_seconds=0)
    result = await loop.run(project.id, meter=meter)
    assert result.result == "stopped" and len(provider.calls) == 1 and "budget" in result.reason and "before round 2" in result.reason
    assert meter.snapshot()["calls"] == 1 and [n.outcome for n in result.rounds] == ["failed"]


async def test_the_loop_adds_its_calls_to_the_runs_meter(world, project):
    loop, provider, *_ = world()
    provider.queue("m-openai", fix(GOOD))
    meter = Meter(max_cost_usd=0, max_seconds=0)
    await loop.run(project.id, meter=meter)
    snapshot = meter.snapshot()
    assert snapshot["calls"] == 1 and snapshot["tokens_in"] == 1000 and snapshot["cost_usd"] == pytest.approx(0.004)


async def test_a_cancel_before_the_start_runs_nothing_at_all(world, project):
    loop, provider, store, *_ = world()
    meter = Meter(max_cost_usd=0, max_seconds=0)
    meter.cancel()
    result = await loop.run(project.id, meter=meter)
    assert result.result == "stopped" and "cancelled" in result.reason and provider.calls == [] and result.rounds == () and rows(store, project) == []


async def test_a_time_limit_stops_the_loop(world, project):
    loop, provider, *_ = world()
    now = [0.0]
    meter = Meter(max_cost_usd=0, max_seconds=5, clock=lambda: now[0])
    now[0] = 10.0
    result = await loop.run(project.id, meter=meter)
    assert result.result == "stopped" and "time" in result.reason and provider.calls == []


async def test_a_cap_that_arrives_while_a_fix_is_still_being_repaired_drops_it_unsaved(world, project):
    loop, provider, store, service, library = world()
    provider.queue("m-openai", fix(BROKEN_CODE), fix(GOOD))
    meter = Meter(max_cost_usd=0.001, max_seconds=0)
    result = await loop.run(project.id, meter=meter)
    assert result.result == "stopped" and len(provider.calls) == 1 and [n.outcome for n in result.rounds] == ["stopped"]
    assert "def f(:" not in latest_body(store, project.id, library.get("backend_code")) and service.read_file(project.id, "backend/main.py") == BAD[0][1]


async def test_a_slot_with_no_price_makes_the_cost_unknown_and_never_zero(world, project):
    loop, provider, *_ = world(ibm_ica_openai_price_input_per_mtok="", ibm_ica_openai_price_output_per_mtok="")
    provider.queue("m-openai", fix(GOOD))
    result = await loop.run(project.id)
    assert result.result == "converged" and result.calls == 1 and result.cost_usd is None


async def test_without_a_meter_only_the_round_limit_applies_and_the_cost_is_the_sum_of_the_calls(world, project):
    loop, provider, *_ = world()
    provider.queue("m-openai", fix(GOOD))
    result = await loop.run(project.id)
    assert result.cost_usd == pytest.approx(0.004) and result.calls == 1


# ---- the record -------------------------------------------------------------------------------------------------------------------------

async def test_every_run_of_the_tests_is_one_recorded_round_with_its_counts(world, project):
    loop, provider, store, *_ = world()
    provider.queue("m-openai", fix(GOOD))
    result = await loop.run(project.id, run_id="run-1")
    recorded = rows(store, project)
    assert [(r.loop_id, r.round, r.artefact, r.version, r.outcome, r.run_id) for r in recorded] == [
        ("loop-1", 1, "backend_code", 2, "failed", "run-1"), ("loop-1", 2, "", None, "passed", "run-1")]
    assert (recorded[0].passed, recorded[0].failed, recorded[1].passed, recorded[1].failed) == (0, 1, 1, 0)
    assert recorded[0].fingerprint == result.rounds[0].fingerprint != "" and recorded[1].fingerprint == ""
    assert recorded[0].failures[0]["test"] == "tests/test_notes.py::test_list_is_empty" and recorded[0].seconds > 0


async def test_each_round_adds_one_audit_row_with_counts_and_no_contents(world, project):
    loop, provider, store, *_ = world()
    provider.queue("m-openai", fix(GOOD))
    await loop.run(project.id)
    audit = [(a.action, a.target_id, a.detail) for a in store.audit.list(project.id) if a.action == "build.round"]
    assert audit == [("build.round", "loop-1#1", {"round": 1, "artefact": "backend_code", "outcome": "failed", "passed": 0, "failed": 1, "errors": 0}),
                     ("build.round", "loop-1#2", {"round": 2, "artefact": "", "outcome": "passed", "passed": 1, "failed": 0, "errors": 0})]
    assert "FastAPI" not in repr(audit)


async def test_a_secret_a_test_prints_is_redacted_before_the_model_sees_it_or_a_row_is_written(world, project):
    printing = [("tests/test_notes.py", f"def test_leaky():\n    assert False, 'key is ' + 'AKIA' + 'IOSFODNN7EXAMPLE'\n")]
    loop, provider, store, *_ = world(saved_backend=GOOD, saved_tests=printing)
    provider.queue("m-openai", *[fix(printing, "TSF")] * 6)
    result = await loop.run(project.id)
    seen = " ".join(m.content for call in provider.calls for m in call.request.messages)
    assert provider.calls and "key is" in seen                                                  # the failure WAS shown to the model ...
    assert AWS not in seen and AWS not in repr(rows(store, project)) and AWS not in repr(store.audit.list(project.id)) and AWS not in repr(result)   # ... without the secret


async def test_a_loop_that_stops_for_any_reason_still_records_the_round_it_stopped_in(world, project):
    loop, provider, store, *_ = world()
    provider.queue("m-openai", fix(BAD))
    await loop.run(project.id)
    assert [r.outcome for r in rows(store, project)] == ["failed", "not_converging"]


async def test_the_events_callback_is_told_about_each_fix_round(world, project):
    loop, provider, *_ = world()
    provider.queue("m-openai", fix(GOOD))
    seen = []
    await loop.run(project.id, on_event=lambda kind, data: seen.append((kind, data)))
    assert seen == [("build.round", {"round": 1, "artefact": "backend_code", "failed": 1, "errors": 0})]


def test_the_default_number_of_fix_rounds_is_three_and_the_setting_is_bounded(make_settings):
    assert make_settings().build_fix_rounds == 3
    from pydantic import ValidationError
    for bad in (0, 11):
        with pytest.raises(ValidationError):
            make_settings(build_fix_rounds=bad)
    assert make_settings(build_fix_rounds=10).build_fix_rounds == 10 and make_settings(build_fix_rounds=1).build_fix_rounds == 1
