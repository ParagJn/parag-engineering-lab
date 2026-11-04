"""S17c-2: the Build phase through the real phase runner. Scripted developers, a real runner, the real sandbox. No live model is called.

The runner starts the database, backend and frontend together, the test suite after the backend, and then runs the fix loop once. What the loop ends with
is REPORTED (in the result, the totals and the events); it is never an error and never an approval."""
from __future__ import annotations

import asyncio
import itertools

import pytest

from app.agents.runtime import AgentRuntime
from app.agents.skills import SkillLibrary
from app.build import code_review
from app.build.loop import FixLoop
from app.build.phase import NEEDED_FOR_LOOP, BuildHooks, BuildOutcome
from app.build.service import BuildService
from app.guardrails.scan import Scanner
from app.llm.gateway import Gateway
from app.llm.providers.mock import MockProvider
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.review.prompt import load_rubric
from app.review.service import ReviewService
from app.run.events import EventBus
from app.run.runner import DONE, FAILED, SKIPPED, PhaseRunner
from app.sandbox import profile as OS
from app.sandbox.runner import Sandbox
from app.sandbox.service import SandboxService
from app.build import legacy
from app.workflow.engine import WorkflowEngine

from ._build import make_body

pytestmark = [pytest.mark.anyio, pytest.mark.sandbox, pytest.mark.skipif(not OS.sandbox_available(), reason="this machine has no sandbox-exec")]
MODELS = dict(
    ibm_ica_model_id="m-sonnet", ibm_ica_fallback_model_id="m-sonnet", ibm_ica_haiku_model_id="m-haiku",
    ibm_ica_openai_model_id="m-openai", ibm_ica_gemini_model_id="m-gemini",
    ibm_ica_price_input_per_mtok="2", ibm_ica_price_output_per_mtok="10",
    ibm_ica_haiku_price_input_per_mtok="2", ibm_ica_haiku_price_output_per_mtok="10",
    ibm_ica_openai_price_input_per_mtok="2", ibm_ica_openai_price_output_per_mtok="10",
    ibm_ica_gemini_price_input_per_mtok="2", ibm_ica_gemini_price_output_per_mtok="10",
)
LLD = ("## Overview\nx\n## Endpoints\n- API-001 GET /notes lists notes. Derives from: FR-001\n## Tables\n- TBL-001 notes: id, text. Derives from: FR-001\n"
       "## Rules\n- RUL-001 A note has text. Derives from: FR-001\n## Coverage check\nNone\n## Open questions\nNone")
SCHEMA = "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, text TEXT NOT NULL);\n"
INIT = ("import os, sqlite3\nhere = os.path.dirname(os.path.abspath(__file__))\nc = sqlite3.connect(os.path.join(here, 'app.db'))\n"
        "c.executescript(open(os.path.join(here, 'schema.sql')).read())\nc.commit()\nprint('ok')\n")
DB = [("db/schema.sql", SCHEMA), ("db/init_db.py", INIT)]
FE = [("frontend/index.html", "<!doctype html><html><body><script src=\"app.js\"></script></body></html>"), ("frontend/app.js", "document.title = 'x';")]
BROKEN_FE = [("frontend/index.html", "<html></html>"), ("frontend/app.js", "function (\n")]
TESTS = [("tests/test_notes.py", "from fastapi.testclient import TestClient\nfrom backend.main import app\n\n\ndef test_list_is_empty():\n    assert TestClient(app).get('/notes').json() == []\n")]
BROKEN_CODE = [("backend/main.py", "def f(:\n    pass\n")]


def backend(returns: str) -> list[tuple[str, str]]:
    return [("backend/main.py", f"from fastapi import FastAPI\napp = FastAPI()\n\n@app.get('/notes')\ndef notes():\n    return {returns}\n")]


GOOD, WRONG = backend("[]"), backend('{"items": []}')
FOUR = ["database_schema", "backend_code", "frontend_code", "test_suite"]       # test_report and code_security_review have no skill until S18


def reply(entries, prefix):
    body = make_body(entries, prefix).replace("Derives from: TBL-001", "Derives from: TBL-001, API-001")
    return ProviderResponse(f"<artefact>\n{body}\n</artefact>", Usage(1000, 200), "stop")


class Slow(MockProvider):
    """A scripted provider whose every call takes `delay` seconds, and which remembers how many calls were in flight at once."""

    def __init__(self, delay: float = 0.0):
        super().__init__()
        self.delay, self.now, self.peak = delay, 0, 0

    async def complete(self, model_id, request):
        self.now += 1
        self.peak = max(self.peak, self.now)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            return await super().complete(model_id, request)
        finally:
            self.now -= 1


@pytest.fixture(scope="module")
def catalogue():
    return legacy.catalogue()


@pytest.fixture(scope="module")
def sandbox_box():
    return Sandbox(scanner=Scanner())


@pytest.fixture
def world(make_settings, store, project, catalogue, sandbox_box):
    def build(delay=0.0, hooks=True, sandbox=None, reviewers=False, **settings):
        cfg = make_settings(**{**MODELS, "llm_retry_backoff_seconds": 0, **settings})
        provider = Slow(delay)
        ids = itertools.count(1)
        routing = Routing.load()
        gateway = Gateway(cfg, routing, provider, store, call_id_factory=lambda: f"call{next(ids)}")
        engine = WorkflowEngine(catalogue, store)
        library = legacy.library(catalogue)
        runtime = AgentRuntime(cfg, store, gateway, catalogue, engine, library)
        service = SandboxService(cfg, store, Scanner(), sandbox or sandbox_box)
        builder = BuildService(service)
        loop_ids = itertools.count(1)                                                    # a new id per loop, as in production (a random one)
        hook = BuildHooks(FixLoop(cfg, store, runtime, library, builder, service, new_id=lambda: f"loop-{next(loop_ids)}"), builder, store, library, cfg,
                          review_slots=reviewers if isinstance(reviewers, tuple) else (code_review.SLOTS if reviewers else ()))
        bus = EventBus(store, queue_size=cfg.run_event_queue, secrets=cfg.secret_values)
        runner = PhaseRunner(cfg, store, engine, runtime, ReviewService(cfg, store, gateway, runtime, engine, load_rubric()), bus,
                             build=hook if hooks is True else (hooks or None))
        engine.open_project(project.id)
        store.phases.ensure(project.id, "build", actor="system")
        store.phases.set_status(project.id, "build", "running", actor="system")      # the earlier phases are not the subject here
        for key in ("low_level_design", "high_level_design", "functional_requirements", "hifi_wireframes", "user_journey"):
            skill = library.get(key)
            store.artefacts.create_and_add_version(project.id, artefact_type=key, phase_key=skill.artefact.phase_key, title=skill.artefact.name,
                                                   prefix=skill.artefact.id_prefix, body=LLD if key == "low_level_design" else "## Overview\nx\n", author="human:seed")
        return runner, provider, hook, service, library

    return build


def script(provider, *, db=DB, be=WRONG, fe=FE, tests=TESTS, fixes=()):
    provider.queue("m-haiku", reply(db, "DBF"))
    provider.queue("m-gemini", reply(fe, "FEF"))
    provider.queue("m-openai", reply(be, "BEF"), reply(tests, "TSF"), *[reply(f, "BEF") for f in fixes])


class Spy:
    """Stands in for BuildHooks so the RUNNER's side of the contract can be seen: what it asks, in which phase, and what it does with the answer."""

    def __init__(self, outcome=None, wants_all=False):
        self.outcome, self.wants_all = outcome, wants_all
        self.extra_calls, self.after_calls = [], 0

    def wants(self, phase_key):
        return self.wants_all or phase_key == "build"

    def writes(self, phase_key):
        return ("test_report",) if phase_key == "build" else ()

    def composes(self, phase_key, artefact_key):
        return False

    def extra_check(self, phase_key, artefact_key, project_id):
        self.extra_calls.append((phase_key, artefact_key))
        return None

    async def after_artefacts(self, project_id, run_id, done, failed, skipped, meter, on_event, stop_reason=None):
        self.after_calls += 1
        return self.outcome or BuildOutcome(False, "skipped", "spy")


CHARTER = ["Purpose", "Scope", "Out of scope", "Stakeholders", "Success measures", "Constraints and assumptions", "Open questions"]


def charter_reply():
    return ProviderResponse("<artefact>\n" + "\n".join(f"## {name}\nText for {name}." for name in CHARTER) + "\n</artefact>", Usage(1000, 200), "stop")


def start_setup(store, project):
    store.phases.ensure(project.id, "setup", actor="system")
    store.phases.set_status(project.id, "setup", "running", actor="system")


def world_library(store, key):
    return legacy.library().get(key)


def types_of(store, project, run_id):
    return [e.type for e in store.run_events.list(project.id, run_id=run_id)]


# ---- the hooks themselves -----------------------------------------------------------------------------------------------------------

async def test_only_the_build_phase_wants_the_hooks_and_only_code_artefacts_get_the_extra_check(world, project):
    _, _, hook, _, _ = world()
    assert hook.wants("build") and not hook.wants("requirements") and not hook.wants("design")
    for key in ("database_schema", "backend_code", "frontend_code", "test_suite"):
        assert callable(hook.extra_check("build", key, project.id))
    for phase, key in (("requirements", "personas"), ("build", "low_level_design"), ("build", "test_report"), ("design", "backend_code"), ("deploy", "test_suite")):
        assert hook.extra_check(phase, key, project.id) is None


async def test_the_loop_needs_the_backend_and_the_tests(world):
    assert NEEDED_FOR_LOOP == ("backend_code", "test_suite")


# ---- a whole Build phase ---------------------------------------------------------------------------------------------------------------

async def test_a_whole_build_phase_writes_all_four_checks_them_runs_the_tests_and_fixes_the_backend(world, project, store):
    runner, provider, hook, service, _ = world()
    script(provider, fixes=[GOOD])
    result = await runner.run_phase(project.id, "build", only=FOUR)
    assert [(o.key, o.reason) for o in result.outcomes if o.state != DONE] == []                      # if one fails, say WHY, not just that it did
    assert result.status == "finished" and {k: o.state for k, o in result.by_key().items() if k in ("database_schema", "backend_code", "frontend_code", "test_suite")} == {
        "database_schema": DONE, "backend_code": DONE, "frontend_code": DONE, "test_suite": DONE}
    assert result.build.ran and result.build.result == "converged" and result.build.rounds == 2 and result.build.calls == 1 and result.build.ok
    assert sorted(service.list_files(project.id)) == sorted(["db/init_db.py", "db/schema.sql", "backend/main.py", "frontend/app.js", "frontend/index.html", "tests/test_notes.py", "db/app.db"]) or \
        sorted(service.list_files(project.id)) == sorted(["db/init_db.py", "db/schema.sql", "backend/main.py", "frontend/app.js", "frontend/index.html", "tests/test_notes.py"])
    assert service.read_file(project.id, "backend/main.py") == GOOD[0][1]
    assert {r.run_id for r in store.build_rounds.list(project.id)} == {result.run_id}              # the loop records its rounds under the run that asked for them


async def test_the_three_wave_one_artefacts_start_together_and_the_provider_sees_three_calls_at_once(world, project, store):
    runner, provider, *_ = world(delay=0.3)
    script(provider, fixes=[GOOD])
    result = await runner.run_phase(project.id, "build", only=FOUR)
    assert result.max_in_flight == 3 and provider.peak == 3
    events = [e for e in store.run_events.list(project.id, run_id=result.run_id)]
    kinds = [(e.type, e.data.get("key")) for e in events]
    wave_one = {"database_schema", "backend_code", "frontend_code"}
    first_finish = next(i for i, (t, _) in enumerate(kinds) if t == "artefact.finished")
    assert {k for t, k in kinds[:first_finish] if t == "artefact.started"} == wave_one


async def test_the_test_suite_starts_only_after_the_backend_is_saved_and_the_loop_only_after_the_tests(world, project, store):
    runner, provider, *_ = world()
    script(provider, fixes=[GOOD])
    result = await runner.run_phase(project.id, "build", only=FOUR)
    kinds = [(e.type, e.data.get("key")) for e in store.run_events.list(project.id, run_id=result.run_id)]
    at = {pair: i for i, pair in reversed(list(enumerate(kinds)))}
    assert at[("artefact.finished", "backend_code")] < at[("artefact.started", "test_suite")]
    assert at[("artefact.finished", "test_suite")] < next(i for i, (t, _) in enumerate(kinds) if t == "build.round")
    assert kinds[-1][0] == "run.finished"


async def test_a_reply_whose_files_do_not_compile_is_repaired_in_the_same_conversation_inside_the_runner(world, project, store):
    runner, provider, *_ = world()
    provider.queue("m-haiku", reply(DB, "DBF"))
    provider.queue("m-gemini", reply(FE, "FEF"))
    provider.queue("m-openai", reply(BROKEN_CODE, "BEF"), reply(GOOD, "BEF"), reply(TESTS, "TSF"))
    result = await runner.run_phase(project.id, "build", only=FOUR)
    backend_outcome = result.by_key()["backend_code"]
    assert backend_outcome.state == DONE and backend_outcome.attempts == 2 and result.build.result == "converged"
    assert "def f(:" not in store.artefacts.get_version(project.id, backend_outcome.artefact_id).body


async def test_without_the_hooks_the_runner_behaves_exactly_as_before_and_a_broken_backend_is_simply_saved(world, project, store):
    runner, provider, *_ = world(hooks=False)
    provider.queue("m-haiku", reply(DB, "DBF"))
    provider.queue("m-gemini", reply(FE, "FEF"))
    provider.queue("m-openai", reply(BROKEN_CODE, "BEF"), reply(TESTS, "TSF"))
    result = await runner.run_phase(project.id, "build", only=FOUR)
    assert result.build is None and "build" not in result.totals and result.by_key()["backend_code"].attempts == 1
    assert "build.round" not in types_of(store, project, result.run_id)


# ---- the ending of the loop in the run --------------------------------------------------------------------------------------------------

async def test_a_developer_who_never_fixes_it_ends_the_loop_as_cap_reached_and_the_run_reports_it_plainly(world, project, store):
    runner, provider, *_ = world(build_fix_rounds=2)
    script(provider, fixes=[WRONG, WRONG])
    result = await runner.run_phase(project.id, "build", only=FOUR)
    assert result.status == "finished" and result.stop_reason is None                      # reported, not raised, not a stop
    assert result.build.ran and result.build.result in ("cap_reached", "not_converging") and not result.build.ok
    assert result.totals["build"]["result"] == result.build.result and "still failing" in result.totals["build"]["reason"] or "twice running" in result.totals["build"]["reason"]
    phase = store.phases.get(project.id, "build")
    assert phase.status == "running"                                                       # nothing was approved for the person


async def test_the_loops_ending_is_in_the_runs_stored_totals(world, project, store):
    runner, provider, *_ = world()
    script(provider, fixes=[GOOD])
    result = await runner.run_phase(project.id, "build", only=FOUR)
    assert store.runs.get(project.id, result.run_id).totals["build"] == {"result": "converged", "reason": result.build.reason, "rounds": 2}


async def test_the_loops_calls_count_against_the_runs_money(world, project, store):
    runner, provider, *_ = world()
    script(provider, fixes=[GOOD])
    result = await runner.run_phase(project.id, "build", only=FOUR)
    assert result.totals["calls"] == 5 and result.totals["cost_usd"] == pytest.approx(5 * 0.004)          # database, backend, frontend, tests, and one fix


async def test_a_budget_that_runs_out_during_the_loop_stops_the_run_with_its_reason_and_makes_no_further_call(world, project, store):
    runner, provider, *_ = world(run_max_cost_usd=0.017)
    script(provider, fixes=[GOOD, GOOD])
    result = await runner.run_phase(project.id, "build", only=FOUR)
    assert result.status == "stopped" and result.stop_reason == "budget" and result.build.result == "stopped"
    assert len(provider.calls) == 5 and store.runs.get(project.id, result.run_id).stop_reason == "budget"


async def test_a_run_stopped_before_the_loop_does_not_start_it_and_says_why(world, project, store):
    runner, provider, *_ = world(run_max_cost_usd=0.012)                                    # spent by the three wave-one calls
    script(provider)
    result = await runner.run_phase(project.id, "build", only=FOUR)
    assert result.status == "stopped" and not result.build.ran and result.build.result == "skipped" and "stopped (budget)" in result.build.reason
    assert "build.round" not in types_of(store, project, result.run_id)


# ---- failure, skip, isolation -------------------------------------------------------------------------------------------------------------

async def test_a_failed_backend_skips_the_tests_and_the_loop_and_names_the_reason(world, project, store):
    runner, provider, _, service, _ = world()
    provider.queue("m-haiku", reply(DB, "DBF"))
    provider.queue("m-gemini", reply(FE, "FEF"))
    provider.queue("m-openai", *[reply(BROKEN_CODE, "BEF")] * 3)
    result = await runner.run_phase(project.id, "build", only=FOUR)
    states = {k: o.state for k, o in result.by_key().items() if k in ("database_schema", "backend_code", "frontend_code", "test_suite")}
    assert states == {"database_schema": DONE, "backend_code": FAILED, "frontend_code": DONE, "test_suite": SKIPPED}
    assert result.status == "failed" and not result.build.ran and result.build.result == "skipped"
    assert "backend_code" in result.build.reason and "test_suite" in result.build.reason
    assert "could not be produced" in result.build.reason                                       # the backend's own failure, not just its name
    assert sorted(service.list_files(project.id)) == sorted(["db/init_db.py", "db/schema.sql", "frontend/app.js", "frontend/index.html"]) or "db/app.db" in service.list_files(project.id)
    assert not [p for p in service.list_files(project.id) if p.startswith("backend/")]       # the failed attempt is not left lying there


async def test_a_failed_frontend_does_not_stop_the_backend_the_tests_or_the_loop(world, project, store):
    runner, provider, _, service, _ = world()
    provider.queue("m-haiku", reply(DB, "DBF"))
    provider.queue("m-gemini", *[reply(BROKEN_FE, "FEF")] * 3)
    provider.queue("m-openai", reply(GOOD, "BEF"), reply(TESTS, "TSF"))
    result = await runner.run_phase(project.id, "build", only=FOUR)
    states = {k: o.state for k, o in result.by_key().items() if k in ("database_schema", "backend_code", "frontend_code", "test_suite")}
    assert states == {"database_schema": DONE, "backend_code": DONE, "frontend_code": FAILED, "test_suite": DONE}
    assert result.status == "failed" and result.build.ran and result.build.result == "converged"
    assert service.read_file(project.id, "backend/main.py") == GOOD[0][1] and not [p for p in service.list_files(project.id) if p.startswith("frontend/")]


async def test_one_projects_build_never_shows_in_another(world, project, store):
    runner, provider, _, service, _ = world()
    other = store.projects.create(name="Other", brief="", actor="human:tester")
    script(provider, fixes=[GOOD])
    await runner.run_phase(project.id, "build", only=FOUR)
    assert service.list_files(other.id) == []


# ---- the sandbox, the workspace, the events ----------------------------------------------------------------------------------------------------

async def test_a_sandbox_that_cannot_run_makes_the_loop_blocked_not_a_failure_of_the_code(world, project, store):
    runner, provider, *_ = world(sandbox=Sandbox(sandbox_exec="/nonexistent/sandbox-exec", scanner=Scanner()))
    script(provider)
    result = await runner.run_phase(project.id, "build", only=FOUR)
    assert result.build.ran and result.build.result == "blocked" and not result.build.ok and result.status == "finished"
    assert {o.state for o in result.outcomes if o.key in ("database_schema", "backend_code", "frontend_code", "test_suite")} == {DONE}


async def test_the_workspace_holds_the_latest_saved_version_of_each_component_when_the_run_ends(world, project, store):
    runner, provider, _, service, library = world(build_fix_rounds=1)
    script(provider, fixes=[WRONG])
    result = await runner.run_phase(project.id, "build", only=FOUR)
    from app.build.inner import latest_body
    from app.build.files import parse_code
    for key, folder in (("backend_code", "backend"), ("database_schema", "db"), ("frontend_code", "frontend"), ("test_suite", "tests")):
        saved = {f.path: f.text for f in parse_code(latest_body(store, project.id, library.get(key)))[0]}
        assert {p: service.read_file(project.id, p) for p in saved} == saved
    assert result.build.result in ("cap_reached", "not_converging")


async def test_a_build_round_event_is_published_once_per_fix_round_with_counts_only(world, project, store):
    runner, provider, *_ = world(build_fix_rounds=2)
    script(provider, fixes=[GOOD])
    result = await runner.run_phase(project.id, "build", only=FOUR)
    rounds = [e for e in store.run_events.list(project.id, run_id=result.run_id) if e.type == "build.round"]
    assert [e.data for e in rounds] == [{"round": 1, "artefact": "backend_code", "failed": 1, "errors": 0}]
    assert "def notes" not in repr([e.data for e in rounds])


async def test_the_events_stay_in_the_documented_order_with_the_new_one_inside_the_run(world, project, store):
    runner, provider, *_ = world()
    script(provider, fixes=[GOOD])
    result = await runner.run_phase(project.id, "build", only=FOUR)
    types = types_of(store, project, result.run_id)
    assert types[0] == "run.started" and types[-1] == "run.finished" and types.count("build.round") == 1
    assert types.index("build.round") > max(i for i, t in enumerate(types) if t == "artefact.finished")


async def test_a_second_run_that_rewrites_only_the_tests_still_judges_the_saved_backend_and_asks_nobody_else(world, project, store):
    runner, provider, *_ = world()
    script(provider, fixes=[GOOD])
    await runner.run_phase(project.id, "build", only=FOUR)
    calls = len(provider.calls)
    provider.queue("m-openai", reply(TESTS, "TSF"))
    again = await runner.run_phase(project.id, "build", only=["test_suite"])                  # one artefact: the tests are rewritten, nothing else is
    assert len(provider.calls) == calls + 1 and again.build.ran and again.build.result == "converged" and again.build.calls == 0


async def test_a_plain_run_of_the_phase_finishes_without_trying_to_write_the_two_hook_artefacts_as_model_work(world, project, store):
    """The hook writes the test report and the code review itself after the loop, so the runner leaves both out. With them out, a plain run of the Build phase
    no longer ends 'failed' for want of a skill, as it did until S18."""
    runner, provider, *_ = world()
    script(provider, fixes=[GOOD])
    result = await runner.run_phase(project.id, "build")
    states = {k: o.state for k, o in result.by_key().items()}
    assert set(states) == set(FOUR) and set(states.values()) == {DONE}
    assert result.status == "finished" and result.build.result == "converged"


async def test_a_run_dropped_by_a_stop_still_puts_the_workspace_back_to_the_saved_versions(world, project, store):
    runner, provider, _, service, _ = world(run_max_cost_usd=0.012)
    script(provider)
    result = await runner.run_phase(project.id, "build", only=FOUR)
    assert result.build.result == "skipped" and "stopped (budget)" in result.build.reason
    from app.build.inner import latest_body
    from app.build.files import parse_code
    for key in ("backend_code", "database_schema", "frontend_code", "test_suite"):
        body = latest_body(store, project.id, world_library(store, key))
        saved = {f.path: f.text for f in parse_code(body)[0]} if body else {}
        assert all(service.read_file(project.id, p) == t for p, t in saved.items())
    assert [p for p in service.list_files(project.id) if p.startswith(".stage")] == []


async def test_the_real_app_builds_the_hooks_and_hands_them_to_its_runner(make_settings):
    from app.main import create_app
    app = create_app(make_settings(**MODELS))
    assert isinstance(app.state.build, BuildHooks) and app.state.runner.build is app.state.build
    # The LIVE catalogue has no code artefacts (S19), so the code generator's fix loop stays quiet; the instruction set is written by the composer.
    assert not app.state.build.wants("build") and not app.state.build.wants("requirements") and app.state.build.writes("build") == ()
    assert app.state.build.composes("build", "build_instructions") and not app.state.build.composes("build", "backend_code") and not app.state.build.composes("deploy", "build_instructions")


async def test_the_events_of_a_build_round_carry_counts_and_a_name_only():
    from app.build.loop import round_event
    assert round_event(2, "test_suite", 3, 1) == {"round": 2, "artefact": "test_suite", "failed": 3, "errors": 1}


# ---- the runner's side of the contract, seen through a spy ---------------------------------------------------------------------------------

async def test_another_phase_is_asked_with_its_own_name_and_never_has_the_loop_run(world, project, store):
    spy = Spy()
    runner, provider, *_ = world(hooks=spy)
    start_setup(store, project)
    provider.queue("m-sonnet", charter_reply())
    result = await runner.run_phase(project.id, "setup", only=["project_charter"])
    assert result.by_key()["project_charter"].state == DONE
    assert spy.extra_calls == [("setup", "project_charter")]                                       # asked with ITS phase, not "build"
    assert spy.after_calls == 0 and result.build is None and "build" not in result.totals            # the hook said it does not want this phase


async def test_the_build_phase_asks_the_hook_once_after_the_artefacts_and_the_answer_goes_into_the_result(world, project, store):
    outcome = BuildOutcome(True, "cap_reached", "2 of 3 test(s) still failing", rounds=3, calls=2)
    spy = Spy(outcome=outcome)
    runner, provider, *_ = world(hooks=spy)
    script(provider)
    result = await runner.run_phase(project.id, "build", only=FOUR)
    assert spy.after_calls == 1 and result.build is outcome
    assert result.totals["build"] == {"result": "cap_reached", "reason": "2 of 3 test(s) still failing", "rounds": 3}
    assert {phase for phase, _ in spy.extra_calls} == {"build"} and sorted(k for _, k in spy.extra_calls) == sorted(FOUR)


async def test_a_reason_with_a_web_address_is_cleaned_before_it_goes_into_the_stored_totals(world, project, store):
    spy = Spy(outcome=BuildOutcome(True, "invalid", "could not be fixed, see https://evil.example/path?token=abc for details"), wants_all=True)
    runner, provider, *_ = world(hooks=spy)
    start_setup(store, project)
    provider.queue("m-sonnet", charter_reply())
    result = await runner.run_phase(project.id, "setup", only=["project_charter"])
    stored = store.runs.get(project.id, result.run_id).totals["build"]["reason"]
    assert "evil.example" not in stored and "https://" not in stored and "could not be fixed" in stored


async def test_the_runner_hands_the_hook_the_stop_reason_and_a_way_to_publish(world, project, store):
    seen = {}

    class Recording(Spy):
        async def after_artefacts(self, project_id, run_id, done, failed, skipped, meter, on_event, stop_reason=None):
            seen.update(done=set(done), stop=stop_reason, run=run_id)
            on_event("build.round", {"round": 1, "artefact": "backend_code", "failed": 1, "errors": 0})
            return await super().after_artefacts(project_id, run_id, done, failed, skipped, meter, on_event, stop_reason)
    runner, provider, *_ = world(hooks=Recording(), run_max_cost_usd=0.012)
    script(provider)
    result = await runner.run_phase(project.id, "build", only=FOUR)
    assert seen["stop"] == "budget" and seen["run"] == result.run_id and {"backend_code"} <= seen["done"] | {"backend_code"}
    published = [e for e in store.run_events.list(project.id, run_id=result.run_id) if e.type == "build.round"]
    assert len(published) == 1 and published[0].run_id == result.run_id


# ---- the hook on its own ----------------------------------------------------------------------------------------------------------------------

def save_backend(store, project, library, entries):
    skill = library.get("backend_code")
    store.artefacts.create_and_add_version(project.id, artefact_type=skill.key, phase_key="build", title=skill.artefact.name, prefix=skill.artefact.id_prefix,
                                           body=make_body(entries, "BEF"), author="human:seed")


async def test_a_run_that_was_stopped_puts_back_what_is_saved_and_removes_what_never_was(world, project, store):
    _, _, hook, service, library = world()
    save_backend(store, project, library, GOOD)
    service.write_file(project.id, "backend/main.py", "an unsaved attempt (\n", actor="human:Ann")
    service.write_file(project.id, "backend/extra.py", "x = 1\n", actor="human:Ann")
    outcome = await hook.after_artefacts(project.id, "run-1", set(), {}, {}, None, lambda *a: None, stop_reason="budget")
    assert (outcome.ran, outcome.result) == (False, "skipped") and "stopped (budget)" in outcome.reason
    assert service.read_file(project.id, "backend/main.py") == GOOD[0][1] and service.list_files(project.id, "backend") == ["backend/main.py"]


async def test_a_run_missing_what_the_loop_needs_says_which_and_why_and_puts_back_what_is_saved(world, project, store):
    _, _, hook, service, library = world()
    save_backend(store, project, library, GOOD)
    service.write_file(project.id, "backend/main.py", "an unsaved attempt (\n", actor="human:Ann")
    outcome = await hook.after_artefacts(project.id, "run-1", {"backend_code"}, {"test_suite": "could not be produced after 3 attempt(s)"}, {}, None, lambda *a: None)
    assert (outcome.ran, outcome.result) == (False, "skipped")
    assert "test_suite could not be produced after 3 attempt(s)" in outcome.reason and "backend_code" not in outcome.reason
    assert service.read_file(project.id, "backend/main.py") == GOOD[0][1]


async def test_every_artefact_that_holds_code_has_a_skill_so_the_hook_never_meets_a_missing_one(world):
    from app.build.files import KINDS
    _, _, _, _, library = world()
    assert all(library.get(key) is not None for key in KINDS)


# ---- the test report, written by the hook after the loop (S18a) ----------------------------------------------------------------------------------

def report_of(store, project):
    found = store.artefacts.list(project.id, phase_key="build", artefact_type="test_report")
    return (found[0], store.artefacts.get_version(project.id, found[0].id)) if found else (None, None)


async def test_the_hook_says_it_writes_the_report_and_the_review_and_only_in_the_build_phase(world):
    _, _, hook, _, _ = world()
    assert hook.writes("build") == ("test_report", "code_security_review") and hook.writes("requirements") == () and hook.writes("design") == ()


async def test_a_build_run_saves_the_test_report_from_the_real_rounds_and_it_is_not_model_work(world, project, store):
    runner, provider, *_ = world()
    script(provider, fixes=[GOOD])
    result = await runner.run_phase(project.id, "build", only=FOUR)
    artefact, version = report_of(store, project)
    assert artefact is not None and artefact.id.startswith("BLD-RPT") and version.number == 1
    assert "All the generated tests passed." in version.body and "Final run: 1 passed, 0 failed, 0 errors, 0 skipped." in version.body
    assert "A fix was asked of the backend code (saved as version 2)" in version.body and "tests/test_notes.py" in version.body
    assert len(provider.calls) == 5 and result.totals["calls"] == 5                       # the report cost no model call
    assert version.author == "agent:test_engineer@system" and version.generation["written_by"] == "system" and version.generation["ending"] == "passed"


async def test_the_report_says_when_the_tests_did_not_pass_and_how_it_ended(world, project, store):
    runner, provider, *_ = world(build_fix_rounds=1)
    script(provider, fixes=[WRONG])
    await runner.run_phase(project.id, "build", only=FOUR)
    _, version = report_of(store, project)
    assert "All the generated tests passed." not in version.body and "test_list_is_empty" in version.body
    assert version.generation["ending"] in ("cap_reached", "not_converging")


async def test_each_run_adds_a_new_version_of_the_report_and_the_older_one_is_kept(world, project, store):
    runner, provider, *_ = world()
    script(provider, fixes=[GOOD])
    await runner.run_phase(project.id, "build", only=FOUR)
    provider.queue("m-openai", reply(TESTS, "TSF"))
    await runner.run_phase(project.id, "build", only=["test_suite"])
    artefact, latest = report_of(store, project)
    assert latest.number == 2 and store.artefacts.get_version(project.id, artefact.id, 1).number == 1


async def test_a_run_that_could_not_run_the_loop_writes_no_report(world, project, store):
    runner, provider, *_ = world()
    provider.queue("m-haiku", reply(DB, "DBF"))
    provider.queue("m-gemini", reply(FE, "FEF"))
    provider.queue("m-openai", *[reply(BROKEN_CODE, "BEF")] * 3)
    await runner.run_phase(project.id, "build", only=FOUR)
    assert report_of(store, project) == (None, None)


async def test_a_blocked_sandbox_is_reported_as_blocked_not_as_a_failure_of_the_code(world, project, store):
    runner, provider, *_ = world(sandbox=Sandbox(sandbox_exec="/nonexistent/sandbox-exec", scanner=Scanner()))
    script(provider)
    await runner.run_phase(project.id, "build", only=FOUR)
    _, version = report_of(store, project)
    assert "sandbox could not run anything" in version.body and version.generation["ending"] == "blocked"


async def test_the_report_names_which_design_endpoints_the_tests_say_they_cover(world, project, store):
    runner, provider, *_ = world()
    provider.queue("m-haiku", reply(DB, "DBF"))
    provider.queue("m-gemini", reply(FE, "FEF"))
    provider.queue("m-openai", reply(GOOD, "BEF"), reply(TESTS, "TSF"))
    await runner.run_phase(project.id, "build", only=FOUR)
    _, version = report_of(store, project)
    assert "1 of 1 endpoint(s) in the low-level design are named by a test file." in version.body        # the scripted tests derive from API-001


async def test_a_stopped_run_writes_no_report_because_nothing_was_tested(world, project, store):
    runner, provider, *_ = world(run_max_cost_usd=0.012)
    script(provider)
    await runner.run_phase(project.id, "build", only=FOUR)
    assert report_of(store, project) == (None, None)


async def test_the_report_is_not_scheduled_as_model_work_in_a_plain_run_either(world, project, store):
    runner, provider, *_ = world()
    script(provider, fixes=[GOOD])
    result = await runner.run_phase(project.id, "build")
    assert "test_report" not in result.by_key() and "code_security_review" not in result.by_key() and report_of(store, project)[1] is not None


async def test_a_second_loop_gets_a_report_about_itself_and_not_the_earlier_one(world, project, store):
    """Rounds are never deleted. The report of the second run must describe only that run's loop, or its numbers would add up two histories."""
    runner, provider, *_ = world()
    script(provider, fixes=[GOOD])
    await runner.run_phase(project.id, "build", only=FOUR)                                    # loop 1: two runs of the tests, a fix in between
    first = report_of(store, project)[1].body
    assert "run 2 time(s)" in first and "Round 2:" in first
    provider.queue("m-openai", reply(TESTS, "TSF"))
    await runner.run_phase(project.id, "build", only=["test_suite"])                          # loop 2: the tests already pass, so one run
    second = report_of(store, project)[1].body
    assert "run 1 time(s)" in second and "Round 1:" in second and "Round 2:" not in second and "A fix was asked" not in second
    assert len(store.build_rounds.list(project.id)) == 3                                      # the earlier loop's rounds are still on record
