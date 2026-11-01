"""Running a whole phase end to end against a scripted model that answers by artefact name, after a delay."""
from __future__ import annotations

import asyncio
import itertools
import json

import pytest

from app.agents.runtime import AgentRuntime
from app.agents.skills import SkillLibrary
from app.llm.errors import ContentFilterBlocked, ReviewerUnavailable
from app.llm.gateway import Gateway
from app.llm.providers.mock import MockCall, MockProvider
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.review.prompt import load_rubric
from app.review.service import ReviewService
from app.run.errors import RunAlreadyActive, RunError, UnknownArtefact
from app.run.events import EventBus
from app.run.runner import DONE, FAILED, NOT_STARTED, SKIPPED, PhaseRunner
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine
from scripts.agent_demo import BRIEF, CHARTER, POLICY, PROBLEM
from scripts.requirements_demo import EPICS_BAD, EPICS_GOOD, FUNCTIONAL, NFR, PERSONAS, STORIES, VISION

pytestmark = pytest.mark.anyio

MODELS = dict(
    ibm_ica_model_id="m-sonnet", ibm_ica_fallback_model_id="m-sonnet", ibm_ica_haiku_model_id="m-haiku",
    ibm_ica_haiku_fallback_model_id="m-sonnet",
    ibm_ica_price_input_per_mtok="2", ibm_ica_price_output_per_mtok="10",
    ibm_ica_haiku_price_input_per_mtok="1", ibm_ica_haiku_price_output_per_mtok="2",
)
REPLIES = {
    "project_charter": CHARTER, "personas": PERSONAS, "problem_statement": PROBLEM, "vision_objectives": VISION,
    "functional_requirements": FUNCTIONAL, "non_functional_requirements": NFR, "epics_features": EPICS_GOOD, "user_stories": STORIES,
}
REVIEW_OK = "<review>\nSummary: Fine.\n</review>"


class Scripted(MockProvider):
    """Answers each request by the artefact it asks for, after `delay`, and measures how many calls overlap."""

    def __init__(self, delay=0.0, replies=None, tokens=(1000, 300)):
        super().__init__()
        self.delay, self.replies, self.tokens = delay, dict(replies or REPLIES), tokens
        self.now = self.peak = 0
        self.asked: list[str] = []
        self.started_at: dict[str, float] = {}
        self.fail: dict[str, list] = {}   # artefact key -> outcomes to give instead (exceptions or ProviderResponses), in order
        self.review_reply = REVIEW_OK
        self.review_fail: Exception | None = None

    def _which(self, request) -> str:
        text = request.messages[0].content
        if "Review the artefact" in text:
            return "review"
        for key in self.replies:
            if f"({key}) for the project" in text:
                return key
        raise RuntimeError("scripted model: unknown task")

    async def complete(self, model_id, request):
        key = self._which(request)
        self.calls.append(MockCall(model_id, request))   # so tests can read what was actually sent
        self.asked.append(key)
        self.started_at.setdefault(key, asyncio.get_running_loop().time())
        self.now += 1
        self.peak = max(self.peak, self.now)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            if key == "review":
                if self.review_fail is not None:
                    raise self.review_fail
                return ProviderResponse(self.review_reply, Usage(*self.tokens), "stop")
            queued = self.fail.get(key)
            if queued:
                outcome = queued.pop(0)
                if isinstance(outcome, BaseException):
                    raise outcome
                return outcome
            return ProviderResponse(self.replies[key], Usage(*self.tokens), "stop")
        finally:
            self.now -= 1


@pytest.fixture
def rig(make_settings, store):
    def build(delay=0.0, tokens=(1000, 300), **settings):
        cfg = make_settings(**{**MODELS, "llm_retry_backoff_seconds": 0, **settings})
        provider = Scripted(delay, tokens=tokens)
        ids = itertools.count(1)
        routing = Routing.load()
        catalogue = load_catalogue(routing.roles.keys())
        gateway = Gateway(cfg, routing, provider, store, call_id_factory=lambda: f"call{next(ids)}")
        engine = WorkflowEngine(catalogue, store)
        runtime = AgentRuntime(cfg, store, gateway, catalogue, engine, SkillLibrary.load(catalogue))
        reviews = ReviewService(cfg, store, gateway, runtime, engine, load_rubric())
        bus = EventBus(store, queue_size=cfg.run_event_queue, secrets=cfg.secret_values)
        runner = PhaseRunner(cfg, store, engine, runtime, reviews, bus)
        real_run_phase = runner.run_phase

        async def bounded(*args, **kwargs):
            """A scripted run takes about a second. Anything that takes longer is a bug (a loop, a lost wake-up), and the
            test must say so in seconds rather than hang."""
            return await asyncio.wait_for(real_run_phase(*args, **kwargs), 15)

        runner.run_phase = bounded
        project = store.projects.create(name="Room Booking", brief=BRIEF, actor="system")
        engine.open_project(project.id)
        store.context.add_document(project.id, "policy.md", POLICY, actor="human:ann")
        return runner, provider, engine, project, bus

    return build


async def through_setup(runner, engine, project):
    result = await runner.run_phase(project.id, "setup")
    assert result.by_key()["project_charter"].state == DONE   # precondition
    engine.finish(project.id, "setup", actor="system")
    engine.approve(project.id, "setup", actor="human:ann")


def states(result):
    return {o.key: o.state for o in result.outcomes}


# ---- a phase, produced ------------------------------------------------------------------------------------------------

async def test_a_whole_phase_is_produced_in_one_call_and_left_running(rig, store):
    runner, provider, engine, project, bus = rig()
    await through_setup(runner, engine, project)
    result = await runner.run_phase(project.id, "requirements")

    assert result.status == "finished" and result.stop_reason is None
    assert set(states(result).values()) == {DONE} and len(result.outcomes) == 7
    assert {a.id for a in store.artefacts.list(project.id, phase_key="requirements")} == {
        "REQ-PER-001", "REQ-PRB-001", "REQ-VIS-001", "REQ-F-001", "REQ-NF-001", "REQ-EPC-001", "REQ-US-001"}
    assert store.phases.get(project.id, "requirements").status == "running"   # not handed to review


async def test_the_phase_is_started_for_the_run_with_the_prerequisites_enforced(rig, store):
    runner, provider, engine, project, bus = rig()
    from app.workflow.gates import PrerequisiteNotMet

    assert store.phases.get(project.id, "requirements").status == "not_started"   # precondition
    with pytest.raises(PrerequisiteNotMet, match="Setup is"):
        await runner.run_phase(project.id, "requirements")
    assert provider.asked == [] and store.artefacts.list(project.id) == []
    assert not runner.is_active(project.id, "requirements")                         # the guard was never taken
    assert store.runs.list(project.id) == []                                         # refused before a run existed, so no row, no events
    assert store.run_events.list(project.id) == []


async def test_an_artefact_never_starts_before_everything_it_waits_for_has_finished(rig, store):
    runner, provider, engine, project, bus = rig(delay=0.05)
    await through_setup(runner, engine, project)
    await runner.run_phase(project.id, "requirements")
    begun = provider.started_at
    for key, waits in {"functional_requirements": ["personas", "problem_statement"], "non_functional_requirements": ["problem_statement"],
                       "vision_objectives": ["problem_statement"], "epics_features": ["functional_requirements", "non_functional_requirements"],
                       "user_stories": ["epics_features"]}.items():
        for dep in waits:
            assert begun[key] >= begun[dep] + 0.05 - 0.01, f"{key} started before {dep} could have finished"


async def test_independent_artefacts_really_run_at_the_same_time(rig, store):
    runner, provider, engine, project, bus = rig(delay=0.05)
    await through_setup(runner, engine, project)
    provider.peak = 0
    result = await runner.run_phase(project.id, "requirements")
    assert provider.peak == 3 and result.max_in_flight == 3       # the widest wave, three, and no more than the cap


async def test_more_artefacts_ready_than_the_cap_allows_never_exceeds_the_cap(rig, store):
    runner, provider, engine, project, bus = rig(delay=0.05, run_max_concurrency=2)
    await through_setup(runner, engine, project)
    provider.peak = 0
    result = await runner.run_phase(project.id, "requirements")
    assert provider.peak == 2 and result.max_in_flight == 2 and result.status == "finished"


async def test_a_cap_of_one_runs_everything_one_at_a_time_in_catalogue_order(rig, store):
    runner, provider, engine, project, bus = rig(delay=0.01, run_max_concurrency=1)
    await through_setup(runner, engine, project)
    provider.peak, provider.asked = 0, []
    await runner.run_phase(project.id, "requirements")
    assert provider.peak == 1
    assert provider.asked == ["personas", "problem_statement", "vision_objectives", "functional_requirements",
                              "non_functional_requirements", "epics_features", "user_stories"]


async def test_running_in_parallel_is_clearly_faster_than_one_at_a_time_and_close_to_the_longest_path(rig, store):
    timings = {}
    for cap in (1, 3):
        runner, provider, engine, project, bus = rig(delay=0.15, run_max_concurrency=cap)
        await through_setup(runner, engine, project)
        result = await runner.run_phase(project.id, "requirements")
        timings[cap] = result.elapsed_seconds
        if cap == 1:
            assert result.serial_seconds == pytest.approx(result.elapsed_seconds, rel=0.1)   # one at a time: the sum IS the wall clock
        else:
            assert result.serial_seconds > result.elapsed_seconds * 1.3                       # in parallel the sum clearly exceeds it
    # 7 artefacts in 4 dependency levels: serial = 7 delays, parallel = 4 delays
    # 7 artefacts in 4 dependency levels. Each artefact also costs ~50 ms of real database and search work, so compare
    # the two runs with each other (4 levels against 7 artefacts) instead of against a bare model delay.
    assert timings[3] / timings[1] == pytest.approx(4 / 7, rel=0.25)
    assert timings[3] < timings[1] * 0.75


async def test_every_artefact_saves_exactly_one_version_with_its_own_links_and_record(rig, store):
    runner, provider, engine, project, bus = rig(delay=0.02)
    await through_setup(runner, engine, project)
    result = await runner.run_phase(project.id, "requirements")
    for outcome in result.outcomes:
        assert store.artefacts.get(project.id, outcome.artefact_id).latest_version == 1
        version = store.artefacts.get_version(project.id, outcome.artefact_id)
        assert version.generation["skill"] == outcome.key and version.generation["run_id"] == result.run_id
    declared = {l.declared_in for l in store.links.list(project.id)}
    assert {"REQ-PER-001", "REQ-VIS-001", "REQ-F-001", "REQ-NF-001", "REQ-EPC-001", "REQ-US-001"} <= declared
    assert len(store.links.list(project.id)) == len({(l.from_id, l.to_id, l.kind) for l in store.links.list(project.id)})


async def test_a_parallel_run_gives_the_same_artefacts_and_links_as_a_serial_one(make_settings, tmp_path):
    from app.repos import Store

    shapes = []
    for cap in (1, 3):
        store = Store.open(tmp_path / f"s{cap}.db")
        cfg = make_settings(**{**MODELS, "run_max_concurrency": cap, "llm_retry_backoff_seconds": 0})
        provider = Scripted(0.01)
        routing = Routing.load()
        catalogue = load_catalogue(routing.roles.keys())
        gateway = Gateway(cfg, routing, provider, store)
        engine = WorkflowEngine(catalogue, store)
        runtime = AgentRuntime(cfg, store, gateway, catalogue, engine, SkillLibrary.load(catalogue))
        runner = PhaseRunner(cfg, store, engine, runtime, ReviewService(cfg, store, gateway, runtime, engine, load_rubric()), EventBus(store))
        project = store.projects.create(name="P", brief=BRIEF, actor="system")
        engine.open_project(project.id)
        store.context.add_document(project.id, "policy.md", POLICY, actor="human:ann")
        await through_setup(runner, engine, project)
        await runner.run_phase(project.id, "requirements")
        shapes.append((
            sorted((a.id, store.artefacts.get_version(project.id, a.id).body) for a in store.artefacts.list(project.id)),
            sorted((l.from_id, l.to_id, l.declared_in) for l in store.links.list(project.id)),
        ))
    assert shapes[0] == shapes[1]


# ---- failure isolation ----------------------------------------------------------------------------------------------------

async def test_a_failed_artefact_saves_nothing_skips_only_what_needs_it_and_siblings_finish(rig, store):
    runner, provider, engine, project, bus = rig(delay=0.01)
    await through_setup(runner, engine, project)
    provider.fail["non_functional_requirements"] = [ContentFilterBlocked("blocked")] * 4   # the fallback is the same model: it fails
    result = await runner.run_phase(project.id, "requirements")

    assert states(result) == {
        "personas": DONE, "problem_statement": DONE, "vision_objectives": DONE, "functional_requirements": DONE,
        "non_functional_requirements": FAILED, "epics_features": SKIPPED, "user_stories": SKIPPED}
    assert result.by_key()["epics_features"].reason == "blocked by non_functional_requirements"
    assert result.by_key()["user_stories"].reason == "blocked by non_functional_requirements"   # points at the real fault, not at the skip
    assert result.status == "failed" and result.stop_reason is None
    assert "epics_features" not in provider.asked and "user_stories" not in provider.asked          # never called the model
    assert store.artefacts.list(project.id, phase_key="requirements", artefact_type="non_functional_requirements") == []
    assert store.artefacts.get(project.id, "REQ-F-001").latest_version == 1                          # siblings kept their work


async def test_every_artefact_is_reported_exactly_once_with_a_reason_when_it_did_not_finish(rig, store):
    runner, provider, engine, project, bus = rig()
    await through_setup(runner, engine, project)
    provider.fail["personas"] = [ContentFilterBlocked("blocked")] * 4
    result = await runner.run_phase(project.id, "requirements")
    assert sorted(o.key for o in result.outcomes) == sorted(set(o.key for o in result.outcomes)) and len(result.outcomes) == 7
    for outcome in result.outcomes:
        assert outcome.state == DONE or outcome.reason, outcome
    assert states(result)["functional_requirements"] == SKIPPED and states(result)["problem_statement"] == DONE


async def test_an_artefact_that_needs_repair_is_repaired_inside_the_run_and_counted_once(rig, store):
    runner, provider, engine, project, bus = rig()
    await through_setup(runner, engine, project)
    provider.fail["epics_features"] = [ProviderResponse(EPICS_BAD, Usage(1000, 300), "stop")]
    result = await runner.run_phase(project.id, "requirements")
    assert result.by_key()["epics_features"].attempts == 2 and result.status == "finished"
    assert provider.asked.count("epics_features") == 2


async def test_an_unexpected_exception_in_one_artefact_fails_that_one_and_not_the_run(rig, store):
    runner, provider, engine, project, bus = rig()
    await through_setup(runner, engine, project)
    provider.fail["vision_objectives"] = [RuntimeError("a bug, not a provider condition")]
    result = await runner.run_phase(project.id, "requirements")
    assert states(result)["vision_objectives"] == FAILED and "RuntimeError" in result.by_key()["vision_objectives"].reason
    assert states(result)["functional_requirements"] == DONE and result.status == "failed"


# ---- budget ------------------------------------------------------------------------------------------------------------------------

async def test_a_cost_cap_stops_new_work_and_lets_what_is_already_running_finish_and_save(rig, store):
    """One call is $0.005 and the cap is two calls' worth. With two in flight, the cap can be reached while a third
    artefact has just been allowed to start (vision needs only the problem statement, so it can start while personas is
    still being written and the total is still under the cap). That overshoot is the specified behaviour, so the exact
    set of finished artefacts is timing-dependent; what is NOT timing-dependent is asserted here."""
    runner, provider, engine, project, bus = rig(delay=0.05, run_max_cost_usd=0.0099, run_max_concurrency=2)
    await through_setup(runner, engine, project)
    result = await runner.run_phase(project.id, "requirements")

    assert result.status == "stopped" and result.stop_reason == "budget"
    done = [k for k, s in states(result).items() if s == DONE]
    assert 2 <= len(done) <= 3 and done[:2] == ["personas", "problem_statement"]       # never more than cap + (concurrency - 1) calls
    assert provider.asked.count("project_charter") == 1 and len(provider.asked) - 1 == len(done)   # every call made was saved
    for key in done:
        assert store.artefacts.get(project.id, result.by_key()[key].artefact_id).latest_version == 1
    for key, state in states(result).items():
        if key not in done:
            assert state == NOT_STARTED and "the run was stopped (budget)" in result.by_key()[key].reason
            assert key not in provider.asked                                               # and the model was never asked
    assert result.totals["cost_usd"] >= 0.0099 and result.totals["over_budget_by_usd"] == pytest.approx(result.totals["cost_usd"] - 0.0099, abs=1e-6)


async def test_with_one_call_at_a_time_the_cap_stops_at_exactly_the_artefact_that_reached_it(rig, store):
    """Serial, so no artefact is ever in flight when the cap is reached: the result is exact, not a range."""
    runner, provider, engine, project, bus = rig(run_max_cost_usd=0.0099, run_max_concurrency=1)
    await through_setup(runner, engine, project)
    result = await runner.run_phase(project.id, "requirements")
    assert result.stop_reason == "budget"
    assert [k for k, s in states(result).items() if s == DONE] == ["personas", "problem_statement"]
    assert provider.asked[-2:] == ["personas", "problem_statement"] and result.totals["calls"] == 2


async def test_a_repair_loop_stops_at_the_cap_instead_of_finishing_all_its_repairs(rig, store):
    runner, provider, engine, project, bus = rig(run_max_cost_usd=0.012, run_max_concurrency=1)
    await through_setup(runner, engine, project)
    bad = ProviderResponse("no artefact block at all", Usage(1000, 300), "stop")
    provider.fail["personas"] = [bad, bad, bad]
    result = await runner.run_phase(project.id, "requirements")
    assert result.stop_reason == "budget" and provider.asked.count("personas") == 3   # 3 calls would be $0.015; the cap stopped it there
    assert states(result)["personas"] == NOT_STARTED and "dropped unsaved" in result.by_key()["personas"].reason
    assert store.artefacts.list(project.id, phase_key="requirements") == []


async def test_a_repair_loop_with_room_in_the_budget_is_allowed_to_finish_its_repairs(rig, store):
    runner, provider, engine, project, bus = rig(run_max_cost_usd=0)
    await through_setup(runner, engine, project)
    bad = ProviderResponse("no artefact block at all", Usage(1000, 300), "stop")
    provider.fail["personas"] = [bad, bad]
    result = await runner.run_phase(project.id, "requirements")
    assert result.by_key()["personas"].attempts == 3 and result.status == "finished"


async def test_zero_switches_the_cost_cap_off(rig, store):
    runner, provider, engine, project, bus = rig(run_max_cost_usd=0)
    await through_setup(runner, engine, project)
    assert (await runner.run_phase(project.id, "requirements")).status == "finished"


async def test_an_unpriced_slot_never_trips_the_cap_but_is_counted_and_reported(rig, store):
    runner, provider, engine, project, bus = rig(run_max_cost_usd=0.0001, ibm_ica_price_input_per_mtok="", ibm_ica_price_output_per_mtok="",
                                                 ibm_ica_haiku_price_input_per_mtok="", ibm_ica_haiku_price_output_per_mtok="")
    await through_setup(runner, engine, project)
    result = await runner.run_phase(project.id, "requirements")
    assert result.status == "finished"                                                   # nothing known to count against the cap
    assert result.totals["unpriced_calls"] == 7 and result.totals["cost_is_partial"] is True and result.totals["cost_usd"] == 0.0


async def test_the_totals_add_up_the_calls_tokens_and_cost_of_every_artefact(rig, store):
    runner, provider, engine, project, bus = rig(run_max_cost_usd=0)
    await through_setup(runner, engine, project)
    result = await runner.run_phase(project.id, "requirements")
    assert result.totals["calls"] == 7 and result.totals["tokens_in"] == 7000 and result.totals["tokens_out"] == 2100
    known = sum(o.cost_usd for o in result.outcomes)
    assert result.totals["cost_usd"] == pytest.approx(known)


# ---- time and cancellation -----------------------------------------------------------------------------------------------------------

async def test_a_time_cap_ends_the_run_with_the_reason_time(rig, store):
    runner, provider, engine, project, bus = rig(delay=0.2, run_max_seconds=0.25, run_max_concurrency=1)
    await through_setup(runner, engine, project)
    result = await runner.run_phase(project.id, "requirements")
    assert result.status == "stopped" and result.stop_reason == "time"
    assert 0 < len([o for o in result.outcomes if o.state == DONE]) < 7


async def test_a_run_always_ends_even_when_a_call_hangs_past_the_time_cap(rig, store):
    runner, provider, engine, project, bus = rig(delay=30, run_max_seconds=0.2, llm_timeout_seconds=0.3, llm_max_retries=0)
    await through_setup_quick(runner, engine, project, provider)
    result = await asyncio.wait_for(runner.run_phase(project.id, "requirements"), timeout=5)
    assert result.stop_reason == "time" and not runner.is_active(project.id, "requirements")


async def through_setup_quick(runner, engine, project, provider):
    provider.delay = 0
    await through_setup(runner, engine, project)
    provider.delay = 30


async def test_cancelling_lets_work_in_flight_finish_and_stops_the_rest(rig, store):
    runner, provider, engine, project, bus = rig(delay=0.1, run_max_concurrency=2)
    await through_setup(runner, engine, project)
    run_id = runner.start_phase(project.id, "requirements")
    for _ in range(500):                                   # cancel only once two calls are really in flight: no guessing at timing
        if provider.now == 2:
            break
        await asyncio.sleep(0.005)
    assert provider.now == 2                               # precondition
    assert runner.cancel(project.id, run_id) is True
    record = await wait_for_end(store, project, run_id)
    assert record.status == "stopped" and record.stop_reason == "cancelled"
    assert record.totals["artefacts"]["done"] == 2 and record.totals["artefacts"]["not_started"] == 5
    assert sorted(provider.asked[-2:]) == ["personas", "problem_statement"] and "vision_objectives" not in provider.asked


async def wait_for_end(store, project, run_id, seconds=6):
    for _ in range(int(seconds / 0.02)):
        record = store.runs.get(project.id, run_id)
        if record.status != "running":
            return record
        await asyncio.sleep(0.02)
    raise AssertionError("the run never ended")


async def test_cancelling_a_finished_or_unknown_run_is_refused_plainly(rig, store):
    from app.models import NotFoundError

    runner, provider, engine, project, bus = rig()
    result = await runner.run_phase(project.id, "setup")
    assert runner.cancel(project.id, result.run_id) is False
    with pytest.raises(NotFoundError):
        runner.cancel(project.id, "nope")


# ---- one run per phase -----------------------------------------------------------------------------------------------------------------

async def test_a_second_run_of_the_same_phase_is_refused_while_the_first_is_active(rig, store):
    runner, provider, engine, project, bus = rig(delay=0.1)
    first = runner.start_phase(project.id, "setup")
    assert runner.is_active(project.id, "setup")                       # precondition
    with pytest.raises(RunAlreadyActive, match=f"already being run \\(run {first}\\)"):
        runner.start_phase(project.id, "setup")
    await wait_for_end(store, project, first)
    assert not runner.is_active(project.id, "setup")
    assert len(store.runs.list(project.id)) == 1                         # the refused attempt left no run row


async def test_another_phase_or_another_project_is_not_blocked(rig, store):
    runner, provider, engine, project, bus = rig(delay=0.05)
    other = store.projects.create(name="Other", brief=BRIEF, actor="system")
    engine.open_project(other.id)
    store.context.add_document(other.id, "policy.md", POLICY, actor="human:ann")
    a = runner.start_phase(project.id, "setup")
    b = runner.start_phase(other.id, "setup")
    assert runner.active_count == 2
    await wait_for_end(store, project, a)
    await wait_for_end(store, other, b)


@pytest.mark.parametrize("how", ["success", "failure", "cancel", "exception"])
async def test_the_guard_is_released_whatever_the_run_did(rig, store, how):
    runner, provider, engine, project, bus = rig(delay=0.02)
    if how == "failure":
        provider.fail["project_charter"] = [ContentFilterBlocked("blocked")] * 4
    if how == "exception":
        provider.fail["project_charter"] = [RuntimeError("bug")]
    if how == "cancel":
        run_id = runner.start_phase(project.id, "setup")
        runner.cancel(project.id, run_id)
        await wait_for_end(store, project, run_id)
    else:
        await runner.run_phase(project.id, "setup")
    assert not runner.is_active(project.id, "setup") and runner.active_count == 0
    assert store.runs.list(project.id)[-1].status != "running"
    await runner.run_phase(project.id, "setup")                           # and it can be run again


# ---- what a run produces and refuses -------------------------------------------------------------------------------------------------------

async def test_by_default_only_artefacts_with_no_version_are_run(rig, store):
    runner, provider, engine, project, bus = rig()
    await through_setup(runner, engine, project)
    await runner.run_phase(project.id, "requirements", only=["personas", "problem_statement"])
    provider.asked.clear()
    result = await runner.run_phase(project.id, "requirements")
    assert sorted(provider.asked) == sorted(["vision_objectives", "functional_requirements", "non_functional_requirements", "epics_features", "user_stories"])
    assert len(result.outcomes) == 5 and store.artefacts.get(project.id, "REQ-PER-001").latest_version == 1


async def test_only_runs_the_named_artefacts_as_new_versions(rig, store):
    runner, provider, engine, project, bus = rig()
    await through_setup(runner, engine, project)
    await runner.run_phase(project.id, "requirements")
    provider.asked.clear()
    result = await runner.run_phase(project.id, "requirements", only=["personas"])
    assert provider.asked == ["personas"] and result.by_key()["personas"].version == 2
    assert store.artefacts.get(project.id, "REQ-F-001").latest_version == 1


async def test_rewrite_all_rewrites_everything_in_order(rig, store):
    runner, provider, engine, project, bus = rig()
    await through_setup(runner, engine, project)
    await runner.run_phase(project.id, "requirements")
    result = await runner.run_phase(project.id, "requirements", rewrite_all=True)
    assert {o.version for o in result.outcomes} == {2} and len(result.outcomes) == 7


async def test_a_rewrite_shows_the_artefact_its_own_previous_draft(rig, store):
    runner, provider, engine, project, bus = rig()
    await through_setup(runner, engine, project)
    await runner.run_phase(project.id, "requirements", only=["personas"])
    provider.asked.clear()
    await runner.run_phase(project.id, "requirements", only=["personas"])
    assert provider.calls, "the scripted model must record what it was sent, or this test proves nothing"
    assert "Your previous draft" in provider.calls[-1].request.messages[0].content


@pytest.mark.parametrize("options, error, message", [
    ({"only": ["gadgets"]}, UnknownArtefact, "not in the plan for requirements: gadgets"),
    ({"only": []}, RunError, "'only' names no artefacts"),
    ({"only": ["personas"], "rewrite_all": True}, RunError, "not both"),
])
async def test_a_bad_request_is_refused_before_anything_starts(rig, store, options, error, message):
    runner, provider, engine, project, bus = rig()
    await through_setup(runner, engine, project)
    calls = len(provider.asked)
    with pytest.raises(error, match=message):
        await runner.run_phase(project.id, "requirements", **options)
    assert len(provider.asked) == calls and not runner.is_active(project.id, "requirements")
    assert [r.phase_key for r in store.runs.list(project.id)] == ["setup"]   # no run row for the refused one


async def test_an_artefact_switched_off_for_the_project_is_refused_by_name(rig, store):
    runner, provider, engine, project, bus = rig()
    required = ["personas", "problem_statement", "vision_objectives", "functional_requirements", "non_functional_requirements", "epics_features"]
    store.projects.update(project.id, actor="system", selection={"requirements": required})   # user_stories is optional, so it can be off
    await through_setup(runner, engine, project)
    with pytest.raises(UnknownArtefact, match="user_stories"):
        await runner.run_phase(project.id, "requirements", only=["user_stories"])
    result = await runner.run_phase(project.id, "requirements")
    assert sorted(o.key for o in result.outcomes) == sorted(required) and "user_stories" not in provider.asked


async def test_an_unknown_phase_or_project_is_not_found(rig, store):
    from app.models import NotFoundError

    runner, provider, engine, project, bus = rig()
    with pytest.raises(NotFoundError, match="unknown phase"):
        await runner.run_phase(project.id, "nonsense")
    with pytest.raises(NotFoundError):
        await runner.run_phase("nope", "setup")


@pytest.mark.parametrize("status, message", [("approved", "is approved"), ("awaiting_review", "is awaiting review")])
async def test_a_phase_that_is_approved_or_awaiting_review_is_refused(rig, store, status, message):
    runner, provider, engine, project, bus = rig()
    await through_setup(runner, engine, project)
    await runner.run_phase(project.id, "requirements")
    if status == "awaiting_review":
        engine.finish(project.id, "requirements", actor="system")
    else:
        engine.finish(project.id, "requirements", actor="system")
        engine.approve(project.id, "requirements", actor="human:ann")
    calls = len(provider.asked)
    with pytest.raises(RunError, match=message):
        await runner.run_phase(project.id, "requirements")
    assert len(provider.asked) == calls


async def test_a_rejected_phase_is_restarted_by_a_run(rig, store):
    runner, provider, engine, project, bus = rig()
    await through_setup(runner, engine, project)
    await runner.run_phase(project.id, "requirements")
    engine.finish(project.id, "requirements", actor="system")
    engine.reject(project.id, "requirements", actor="human:ann", feedback="redo personas")
    await runner.run_phase(project.id, "requirements", only=["personas"])
    assert store.phases.get(project.id, "requirements").status == "running"


# ---- review inside a run ------------------------------------------------------------------------------------------------------------------------

async def test_review_is_off_by_default(rig, store):
    runner, provider, engine, project, bus = rig()
    await through_setup(runner, engine, project)
    result = await runner.run_phase(project.id, "requirements")
    assert "review" not in provider.asked and all(o.review is None for o in result.outcomes)


async def test_with_review_on_every_artefact_is_reviewed_after_it_is_saved_and_the_cost_counts(rig, store):
    runner, provider, engine, project, bus = rig(run_max_cost_usd=0)
    await through_setup(runner, engine, project)
    result = await runner.run_phase(project.id, "requirements", review=True)
    assert provider.asked.count("review") == 7 and result.totals["calls"] == 14
    for outcome in result.outcomes:
        assert outcome.review == {"verdict": "ok", "label": "same_family"}
        assert store.artefacts.get_version(project.id, outcome.artefact_id).review_findings["verdict"] == "ok"


async def test_a_reviewer_that_cannot_run_pauses_only_that_review_and_the_run_finishes(rig, store):
    runner, provider, engine, project, bus = rig()
    await through_setup(runner, engine, project)
    provider.review_fail = ContentFilterBlocked("blocked")
    result = await runner.run_phase(project.id, "requirements", review=True)
    assert result.status == "finished" and set(states(result).values()) == {DONE}
    assert all(o.review == {"paused": True} for o in result.outcomes)
    assert store.artefacts.get_version(project.id, "REQ-PER-001").review_findings is None


async def test_a_review_that_fails_in_some_other_way_does_not_fail_the_artefact(rig, store):
    runner, provider, engine, project, bus = rig()
    await through_setup(runner, engine, project)
    provider.review_reply = "no tags at all"
    result = await runner.run_phase(project.id, "requirements", review=True)
    assert result.status == "finished" and set(states(result).values()) == {DONE}
    assert all("failed" in o.review for o in result.outcomes)


async def test_reviews_count_toward_the_budget(rig, store):
    runner, provider, engine, project, bus = rig(run_max_cost_usd=0.021, run_max_concurrency=1)
    await through_setup(runner, engine, project)
    result = await runner.run_phase(project.id, "requirements", review=True)
    assert result.stop_reason == "budget" and provider.asked.count("review") >= 1
    assert result.totals["calls"] == len(provider.asked) - 1 or result.totals["calls"] >= 4   # the charter's call is another run's


# ---- the run record ------------------------------------------------------------------------------------------------------------------------------

async def test_the_run_is_recorded_with_its_outcome_and_totals(rig, store):
    runner, provider, engine, project, bus = rig(delay=0.01)
    await through_setup(runner, engine, project)
    result = await runner.run_phase(project.id, "requirements")
    record = store.runs.get(project.id, result.run_id)
    assert (record.status, record.stop_reason, record.phase_key) == ("finished", None, "requirements") and record.finished_at
    assert record.totals["artefacts"] == {"done": 7, "failed": 0, "skipped": 0, "not_started": 0}
    assert record.totals["serial_seconds"] >= record.totals["elapsed_seconds"] and record.totals["max_in_flight"] == 3


async def test_the_traces_of_a_run_carry_its_run_id(rig, store):
    runner, provider, engine, project, bus = rig()
    await through_setup(runner, engine, project)
    result = await runner.run_phase(project.id, "requirements")
    mine = [t for t in store.traces.list(project.id) if t.run_id == result.run_id]
    assert len(mine) == 7 and {t.phase_key for t in mine} == {"requirements"}
