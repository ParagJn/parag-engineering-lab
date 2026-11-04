"""S18b: two model reviewers (Sonnet and GPT) read the saved code through the real gateway with a scripted provider. No live model is called.

They run together, once each. The colour of each check is decided by the system from the findings. Both results are saved as ONE artefact, each in its own record,
so neither overwrites the other."""
from __future__ import annotations

import asyncio
import itertools

import pytest

from app.agents.runtime import AgentRuntime
from app.agents.skills import SkillLibrary
from app.build import code_review as C
from app.build import review_store as S
from app.build.loop import FixLoop
from app.build.phase import BuildHooks
from app.build.service import BuildService
from app.guardrails.scan import Scanner
from app.llm.gateway import Gateway
from app.llm.providers.mock import MockProvider
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.review.prompt import load_rubric
from app.review.service import ReviewService
from app.run.budget import Meter
from app.run.events import EventBus
from app.run.runner import PhaseRunner
from app.sandbox import profile as OS
from app.sandbox.runner import Sandbox
from app.sandbox.service import SandboxService
from app.build import legacy
from app.workflow.engine import WorkflowEngine

from . import _fakes as F
from ._build import make_body
from .test_build_phase import DB, FE, GOOD, LLD, MODELS, TESTS, WRONG, reply as build_reply

pytestmark = [pytest.mark.anyio]

CLEAN = "<review>\nSummary: The code does what its files say; nothing to flag.\n</review>"
AMBER = "<review>\nSummary: Mostly fine.\n- [MEDIUM] backend/main.py: binds to every address. Fix: bind to 127.0.0.1.\n- [LOW] General: no comments. Fix: add some.\n</review>"
RED = "<review>\nSummary: One serious problem.\n- [HIGH] backend/main.py: builds SQL from text. Fix: use a placeholder.\n</review>"
WRONG_FILE = "<review>\nSummary: x\n- [LOW] backend/nothere.py: a problem. Fix: a fix.\n</review>"
NOT_A_REVIEW = "this is not a review at all"
SECRET_REVIEW = f"<review>\nSummary: found {F.AWS_KEY} in the file.\n</review>"


def text(body):
    return ProviderResponse(body, Usage(2000, 300), "stop")


@pytest.fixture(scope="module")
def catalogue():
    return legacy.catalogue()


@pytest.fixture
def parts(make_settings, store, project, catalogue):
    cfg = make_settings(**{**MODELS, "llm_retry_backoff_seconds": 0, "review_max_repairs": 1,
                           "ibm_ica_price_input_per_mtok": "2", "ibm_ica_price_output_per_mtok": "10"})
    provider = MockProvider()
    ids = itertools.count(1)
    gateway = Gateway(cfg, Routing.load(), provider, store, call_id_factory=lambda: f"call{next(ids)}")
    library = legacy.library(catalogue)
    for key in ("low_level_design", "high_level_design", "functional_requirements"):
        skill = library.get(key)
        store.artefacts.create_and_add_version(project.id, artefact_type=key, phase_key=skill.artefact.phase_key, title=skill.artefact.name,
                                               prefix=skill.artefact.id_prefix, body=LLD if key == "low_level_design" else "## Overview\nx\n", author="human:seed")
    return cfg, provider, gateway, library


def code_input():
    return C.gather_code({"backend_code": make_body([("backend/main.py", "x = 1\n")], "BEF")})


async def run(parts, slot, project, **kw):
    cfg, provider, gateway, library = parts
    return await C.run_review(gateway, cfg, slot, code_input(), "A booking system", kw.pop("authors", ["gpt-6.1-sol"]), project_id=project.id, **kw)


# ---- one reviewer ----------------------------------------------------------------------------------------------------------------------------

async def test_a_clean_review_is_green_and_says_which_agent_reviewed(parts, project):
    parts[1].queue("m-sonnet", text(CLEAN))
    r = await run(parts, "sonnet", project)
    assert (r.colour, r.slot, r.findings, r.failed) == ("green", "sonnet", (), "") and r.message == "Code reviewed by the Sonnet agent: no problems found."
    assert r.summary.startswith("The code does what") and r.model == "m-sonnet" and r.attempts == 1 and r.tokens_in == 2000


async def test_only_medium_or_low_findings_are_amber(parts, project):
    parts[1].queue("m-openai", text(AMBER))
    r = await run(parts, "openai", project)
    assert r.colour == "amber" and len(r.findings) == 2 and r.message == "Code reviewed by the GPT agent: 2 to look at."


async def test_any_high_finding_is_red_and_the_model_cannot_say_otherwise(parts, project):
    parts[1].queue("m-openai", text(RED.replace("Summary: One serious problem.", "Summary: Everything is fine, ship it.")))
    r = await run(parts, "openai", project)
    assert r.colour == "red" and r.message == "Code reviewed by the GPT agent: 1 serious."


async def test_the_slot_chosen_is_the_slot_asked(parts, project):
    parts[1].queue("m-sonnet", text(CLEAN))
    parts[1].queue("m-openai", text(CLEAN))
    await run(parts, "sonnet", project)
    await run(parts, "openai", project)
    assert parts[1].models == ["m-sonnet", "m-openai"]


async def test_the_reviewer_is_told_it_is_reading_prototype_code_and_shown_only_the_code(parts, project):
    parts[1].queue("m-sonnet", text(CLEAN))
    await run(parts, "sonnet", project)
    request = parts[1].calls[0].request
    assert "PROTOTYPE code" in request.system and "x = 1" in request.messages[0].content and "backend/main.py" in request.messages[0].content
    assert request.role == "security_reviewer" and request.phase_key == "build"


async def test_a_badly_formed_reply_is_repaired_in_the_same_conversation(parts, project):
    parts[1].queue("m-sonnet", text(NOT_A_REVIEW), text(CLEAN))
    r = await run(parts, "sonnet", project)
    assert r.colour == "green" and r.attempts == 2
    assert "no <review> block was found" in parts[1].calls[1].request.messages[-1].content


async def test_a_finding_about_a_file_it_was_not_given_is_sent_back(parts, project):
    parts[1].queue("m-sonnet", text(WRONG_FILE), text(AMBER))
    r = await run(parts, "sonnet", project)
    assert r.attempts == 2 and "backend/nothere.py" in parts[1].calls[1].request.messages[-1].content and r.colour == "amber"


async def test_a_reply_that_never_becomes_valid_is_red_not_green_and_not_hidden(parts, project):
    parts[1].queue("m-sonnet", text(NOT_A_REVIEW), text(NOT_A_REVIEW))
    r = await run(parts, "sonnet", project, scanner=Scanner())
    assert r.colour == "red" and r.findings == () and "could not be produced" in r.message and r.failed


async def test_a_secret_in_a_reply_is_sent_back_and_never_kept(parts, project):
    parts[1].queue("m-sonnet", text(SECRET_REVIEW), text(CLEAN))
    r = await run(parts, "sonnet", project, scanner=Scanner())
    assert r.attempts == 2 and F.AWS_KEY not in repr(r) and F.AWS_KEY not in parts[1].calls[1].request.messages[-1].content


async def test_a_model_call_that_fails_is_red_and_does_not_raise(parts, project):
    """Whatever goes wrong inside a reviewer, it becomes a red result that names the reviewer, and nothing is raised into the run."""
    parts[1].queue("m-sonnet", RuntimeError("provider exploded"))
    r = await run(parts, "sonnet", project)
    assert r.colour == "red" and "stopped unexpectedly (RuntimeError)" in r.failed and r.message.startswith("Code review by the Sonnet agent could not be produced")
    assert "provider exploded" not in repr(r)                                                         # the error's own words are not stored


async def test_an_llm_error_from_the_gateway_is_red_with_its_own_wording(parts, project):
    from app.llm.errors import LLMError

    class Broken:
        async def review(self, *args, **kwargs):
            raise LLMError("the service said no")
    cfg, provider, gateway, library = parts
    r = await C.run_review(Broken(), cfg, "sonnet", code_input(), "", [], project_id=project.id)
    assert r.colour == "red" and r.failed.startswith("the model call failed: the service said no")


async def test_an_unavailable_reviewer_is_grey_did_not_run_never_green(parts, project):
    cfg, provider, gateway, library = parts
    cfg2 = cfg.model_copy(update={"ibm_ica_openai_model_id": ""})
    broken = Gateway(cfg2, Routing.load(), provider, parts[0] and None)
    r = await C.run_review(broken, cfg2, "openai", code_input(), "", ["gpt-6.1-sol"], project_id=project.id)
    assert r.colour == "grey" and r.message == "Code not reviewed by the GPT agent yet." and "not available" in r.failed


async def test_no_code_means_nothing_to_review_and_no_model_call(parts, project):
    cfg, provider, gateway, library = parts
    r = await C.run_review(gateway, cfg, "sonnet", C.gather_code({}), "", [], project_id=project.id)
    assert r.colour == "grey" and "no code to review" in r.failed and provider.calls == []


# ---- the independence label --------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("slot, authors, label", [
    ("sonnet", ["gpt-6.1-sol"], "independent"), ("sonnet", ["gemini-x"], "independent"), ("sonnet", ["claude-haiku-5-5"], "same_family"),
    ("openai", ["gpt-6.1-sol"], "same_family"), ("openai", ["claude-haiku-5-5"], "independent"), ("openai", ["gemini-x", "claude-haiku-5-5"], "independent"),
    ("openai", ["claude-haiku-5-5", "gpt-6.1-sol"], "same_family"),
])
async def test_the_label_follows_the_family_of_the_code_it_read_not_a_guess(parts, project, slot, authors, label):
    cfg, provider, gateway, library = parts
    provider.queue({"sonnet": "m-sonnet", "openai": "m-openai"}[slot], text(CLEAN))
    code = C.gather_code({"backend_code": make_body([("backend/main.py", "x = 1\n")], "BEF")})
    r = await C.run_review(gateway, cfg, slot, code, "", authors, project_id=project.id)
    assert r.label == label


# ---- both together -----------------------------------------------------------------------------------------------------------------------------

async def test_both_reviewers_run_together_and_each_keeps_its_own_result(parts, project):
    cfg, provider, gateway, library = parts
    provider.queue("m-sonnet", text(CLEAN))
    provider.queue("m-openai", text(RED))
    both = await C.run_both(gateway, cfg, code_input(), "", ["gpt-6.1-sol"], project_id=project.id)
    assert list(both) == ["sonnet", "openai"] and both["sonnet"].colour == "green" and both["openai"].colour == "red"


async def test_they_are_really_in_flight_at_the_same_moment(parts, project):
    cfg, provider, gateway, library = parts
    provider.queue("m-sonnet", text(CLEAN))
    provider.queue("m-openai", text(CLEAN))
    seen = {"now": 0, "peak": 0}
    real = provider.complete

    async def slow(model_id, request):
        seen["now"] += 1
        seen["peak"] = max(seen["peak"], seen["now"])
        await asyncio.sleep(0.2)
        try:
            return await real(model_id, request)
        finally:
            seen["now"] -= 1
    provider.complete = slow
    await C.run_both(gateway, cfg, code_input(), "", [], project_id=project.id)
    assert seen["peak"] == 2


async def test_one_reviewer_failing_never_stops_the_other(parts, project):
    cfg, provider, gateway, library = parts
    provider.queue("m-sonnet", text(NOT_A_REVIEW), text(NOT_A_REVIEW))
    provider.queue("m-openai", text(CLEAN))
    both = await C.run_both(gateway, cfg, code_input(), "", ["claude-haiku-5-5"], project_id=project.id)
    assert both["sonnet"].colour == "red" and both["openai"].colour == "green"


async def test_the_money_cap_counts_every_call_and_a_stop_leaves_a_reviewer_unfinished_not_green(parts, project):
    cfg, provider, gateway, library = parts
    provider.queue("m-sonnet", text(NOT_A_REVIEW), text(CLEAN))
    provider.queue("m-openai", text(CLEAN))
    meter = Meter(max_cost_usd=0.0001, max_seconds=0)

    def on_call(result, attempt, problems):
        meter.add_call(result.cost_usd, result.tokens_in, result.tokens_out)
        return meter.should_stop()
    both = await C.run_both(gateway, cfg, code_input(), "", ["claude-haiku-5-5"], project_id=project.id, on_call=on_call)
    assert both["sonnet"].colour == "grey" and "stopped (budget)" in both["sonnet"].failed          # needed a second call, so it was dropped
    assert both["openai"].colour == "green"                                                          # already valid when the cap hit, so it is kept
    assert meter.snapshot()["calls"] == 2                                                            # Sonnet's first (a bad reply, then stopped: no second call) and GPT's one
    assert sum(1 for c in provider.calls if c.model_id == "m-sonnet") == 1


# ---- saving both as one artefact ---------------------------------------------------------------------------------------------------------------

def save_code(store, project, library):
    for key, entries, prefix in (("database_schema", DB, "DBF"), ("backend_code", GOOD, "BEF"), ("frontend_code", FE, "FEF"), ("test_suite", TESTS, "TSF")):
        skill = library.get(key)
        store.artefacts.create_and_add_version(project.id, artefact_type=key, phase_key="build", title=skill.artefact.name, prefix=skill.artefact.id_prefix,
                                               body=make_body(entries, prefix), author="agent:backend_developer@gpt-6.1-sol")


def review_of(colour, slot="sonnet"):
    return C.CodeReview(slot, colour, "s", (), C.message_for(slot, colour, ()), False, (), ("backend/main.py",), label="independent", model="m")


async def test_the_two_results_are_saved_as_one_artefact_each_in_its_own_record(parts, project, store):
    save_code(store, project, parts[3])
    number = S.save(store, parts[3], project.id, {"sonnet": review_of("green"), "openai": review_of("red", "openai")})
    record = S.latest_record(store, project.id)
    assert number == 1 and record["artefact_id"].startswith("BLD-REV") and set(record["reviews"]) == {"sonnet", "openai"}
    assert record["reviews"]["sonnet"]["colour"] == "green" and record["reviews"]["openai"]["colour"] == "red"
    assert record["read_versions"] == {"database_schema": 1, "backend_code": 1, "frontend_code": 1, "test_suite": 1}


async def test_the_artefact_text_is_plain_words_for_both_reviewers_and_says_prototype(parts, project, store):
    save_code(store, project, parts[3])
    S.save(store, parts[3], project.id, {"sonnet": review_of("green"), "openai": review_of("grey", "openai")})
    body = store.artefacts.get_version(project.id, S.latest_record(store, project.id)["artefact_id"]).body
    assert "PROTOTYPE code" in body and "not that it is ready for production" in body
    assert "## Reviewed by the Sonnet agent\nCode reviewed by the Sonnet agent: no problems found." in body
    assert "## Reviewed by the GPT agent\nCode not reviewed by the GPT agent yet." in body


async def test_a_rerun_of_one_reviewer_keeps_the_others_latest_result_and_adds_a_new_version(parts, project, store):
    save_code(store, project, parts[3])
    S.save(store, parts[3], project.id, {"sonnet": review_of("green"), "openai": review_of("red", "openai")})
    S.save(store, parts[3], project.id, {"openai": review_of("green", "openai")})
    record = S.latest_record(store, project.id)
    assert record["version"] == 2 and record["ran"] == ["openai"]
    assert record["reviews"]["sonnet"]["colour"] == "green" and record["reviews"]["openai"]["colour"] == "green"
    first = store.artefacts.get_version(project.id, record["artefact_id"], 1).generation["reviews"]
    assert first["openai"]["colour"] == "red"                                                         # the earlier version still says what it said


async def test_the_record_holds_findings_and_names_but_never_the_code(parts, project, store):
    save_code(store, project, parts[3])
    cr = C.CodeReview("sonnet", "red", "s", (C.Finding("high", "backend/main.py", "bad", "fix"),), "m", False, (), ("backend/main.py",))
    S.save(store, parts[3], project.id, {"sonnet": cr})
    stored = repr(store.artefacts.get_version(project.id, S.latest_record(store, project.id)["artefact_id"]).generation)
    assert "bad" in stored and "FastAPI" not in stored and "x = 1" not in stored


async def test_no_review_has_ever_been_saved(parts, project, store):
    assert S.latest_record(store, project.id) is None and S.is_current(store, project.id, None) is False


async def test_a_review_is_current_until_a_code_artefact_gets_a_new_version(parts, project, store):
    save_code(store, project, parts[3])
    S.save(store, parts[3], project.id, {"sonnet": review_of("green")})
    record = S.latest_record(store, project.id)
    assert S.is_current(store, project.id, record) is True
    skill = parts[3].get("backend_code")
    store.artefacts.create_and_add_version(project.id, artefact_type="backend_code", phase_key="build", title="x", prefix=skill.artefact.id_prefix,
                                           body=make_body(GOOD, "BEF"), author="human:Ann")
    assert S.is_current(store, project.id, record) is False


# ---- through the real runner ------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def world(make_settings, store, project, catalogue):
    if not OS.sandbox_available():
        pytest.skip("this machine has no sandbox-exec")

    def build(slots=C.SLOTS, **settings):
        cfg = make_settings(**{**MODELS, "llm_retry_backoff_seconds": 0, **settings})
        provider = MockProvider()
        ids = itertools.count(1)
        gateway = Gateway(cfg, Routing.load(), provider, store, call_id_factory=lambda: f"call{next(ids)}")
        engine = WorkflowEngine(catalogue, store)
        library = legacy.library(catalogue)
        runtime = AgentRuntime(cfg, store, gateway, catalogue, engine, library)
        service = SandboxService(cfg, store, Scanner(), Sandbox(scanner=Scanner()))
        builder = BuildService(service)
        loop_ids = itertools.count(1)
        hook = BuildHooks(FixLoop(cfg, store, runtime, library, builder, service, new_id=lambda: f"loop-{next(loop_ids)}"), builder, store, library, cfg, review_slots=slots)
        bus = EventBus(store, queue_size=cfg.run_event_queue, secrets=cfg.secret_values)
        runner = PhaseRunner(cfg, store, engine, runtime, ReviewService(cfg, store, gateway, runtime, engine, load_rubric()), bus, build=hook)
        engine.open_project(project.id)
        store.phases.ensure(project.id, "build", actor="system")
        store.phases.set_status(project.id, "build", "running", actor="system")
        for key in ("low_level_design", "high_level_design", "functional_requirements", "hifi_wireframes", "user_journey"):
            skill = library.get(key)
            store.artefacts.create_and_add_version(project.id, artefact_type=key, phase_key=skill.artefact.phase_key, title=skill.artefact.name,
                                                   prefix=skill.artefact.id_prefix, body=LLD if key == "low_level_design" else "## Overview\nx\n", author="human:seed")
        return runner, provider, hook, library
    return build


FOUR = ["database_schema", "backend_code", "frontend_code", "test_suite"]


def script(provider, fixes=(), sonnet=(), openai=()):
    provider.queue("m-haiku", build_reply(DB, "DBF"))
    provider.queue("m-gemini", build_reply(FE, "FEF"))
    provider.queue("m-openai", build_reply(WRONG, "BEF"), build_reply(TESTS, "TSF"), *[build_reply(f, "BEF") for f in fixes])
    provider.queue("m-sonnet", *[text(t) for t in sonnet])
    provider.queue("m-openai", *[text(t) for t in openai])


async def test_a_build_run_ends_with_both_reviewers_having_read_the_final_code(world, project, store):
    runner, provider, hook, library = world()
    script(provider, fixes=[GOOD], sonnet=[CLEAN], openai=[AMBER])
    result = await runner.run_phase(project.id, "build", only=FOUR)
    record = S.latest_record(store, project.id)
    assert record["reviews"]["sonnet"]["colour"] == "green" and record["reviews"]["openai"]["colour"] == "amber"
    assert S.is_current(store, project.id, record)
    assert result.build.calls == 1 + 2                                                            # one fix, plus two reviews
    seen = [c.request.messages[0].content for c in provider.calls if c.request.role == "security_reviewer"]
    assert len(seen) == 2 and all("return []" in m and "return {" not in m.split("# The code to review")[1].split("Files in it")[0] for m in seen)    # the FIXED backend, not the first one


async def test_the_reviewers_calls_count_against_the_runs_money(world, project, store):
    runner, provider, *_ = world()
    script(provider, fixes=[GOOD], sonnet=[CLEAN], openai=[CLEAN])
    result = await runner.run_phase(project.id, "build", only=FOUR)
    assert result.totals["calls"] == 7 and result.totals["cost_usd"] > 0


async def test_a_run_whose_code_did_not_all_get_written_runs_no_reviewer(world, project, store):
    runner, provider, *_ = world()
    provider.queue("m-haiku", build_reply(DB, "DBF"))
    provider.queue("m-gemini", *[build_reply([("frontend/index.html", "<html></html>"), ("frontend/app.js", "function (\n")], "FEF")] * 3)
    provider.queue("m-openai", build_reply(GOOD, "BEF"), build_reply(TESTS, "TSF"))
    await runner.run_phase(project.id, "build", only=FOUR)
    assert S.latest_record(store, project.id) is None and not [c for c in provider.calls if c.request.role == "security_reviewer"]


async def test_a_stopped_run_runs_no_reviewer(world, project, store):
    runner, provider, *_ = world(run_max_cost_usd=0.012)
    script(provider, fixes=[GOOD], sonnet=[CLEAN], openai=[CLEAN])
    await runner.run_phase(project.id, "build", only=FOUR)
    assert S.latest_record(store, project.id) is None


async def test_with_no_reviewers_configured_none_run(world, project, store):
    runner, provider, *_ = world(slots=())
    script(provider, fixes=[GOOD])
    await runner.run_phase(project.id, "build", only=FOUR)
    assert S.latest_record(store, project.id) is None


async def test_a_reviewer_that_breaks_never_fails_the_build_run(world, project, store, monkeypatch):
    runner, provider, hook, _ = world()
    script(provider, fixes=[GOOD], sonnet=[CLEAN], openai=[CLEAN])

    async def explode(*args, **kwargs):
        raise RuntimeError("something unexpected inside a reviewer")
    monkeypatch.setattr(C, "_run_review", explode)
    result = await runner.run_phase(project.id, "build", only=FOUR)
    assert result.status == "finished" and result.build.result == "converged"
    record = S.latest_record(store, project.id)
    assert record["reviews"]["sonnet"]["colour"] == "red" and "unexpectedly" in record["reviews"]["sonnet"]["failed"]


async def test_a_second_run_adds_a_second_version_of_the_review(world, project, store):
    runner, provider, *_ = world()
    script(provider, fixes=[GOOD], sonnet=[CLEAN], openai=[CLEAN])
    await runner.run_phase(project.id, "build", only=FOUR)
    provider.queue("m-openai", build_reply(TESTS, "TSF"), text(CLEAN))
    provider.queue("m-sonnet", text(RED))
    await runner.run_phase(project.id, "build", only=["test_suite"])
    record = S.latest_record(store, project.id)
    assert record["version"] == 2 and record["reviews"]["sonnet"]["colour"] == "red" and record["reviews"]["openai"]["colour"] == "green"


# ---- gaps the mutation sweep found --------------------------------------------------------------------------------------------------------------------

async def test_a_file_too_big_is_left_out_whole_and_never_cut():
    body = make_body([("backend/a.py", "a" * 59), ("backend/b.py", "b" * 5000)], "BEF")
    code = C.gather_code({"backend_code": body}, limit=100)
    assert code.paths == ("backend/a.py",) and code.left_out == ("backend/b.py",) and all(len(t) == 60 for _, t in code.files)


async def test_the_code_a_reviewer_is_shown_stays_under_the_limit_on_what_an_agent_may_be_shown():
    assert C.MAX_CODE_CHARS == 90_000 and C.MAX_CODE_CHARS < 100_000


async def test_a_cancel_is_not_swallowed_by_the_reviewer_guard(parts, project):
    cfg, provider, gateway, library = parts

    class Cancelling:
        async def review(self, *args, **kwargs):
            raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await C.run_review(Cancelling(), cfg, "sonnet", code_input(), "", [], project_id=project.id)


async def test_when_a_price_is_unknown_the_cost_is_unknown_never_a_partial_sum(parts, project):
    cfg, provider, gateway, library = parts
    unpriced = cfg.model_copy(update={"ibm_ica_price_input_per_mtok": None, "ibm_ica_price_output_per_mtok": None})
    gw = Gateway(unpriced, Routing.load(), provider, parts[2].store if hasattr(parts[2], "store") else None)
    provider.queue("m-sonnet", text(CLEAN))
    r = await C.run_review(gw, unpriced, "sonnet", code_input(), "", [], project_id=project.id)
    assert r.colour == "green" and r.cost_usd is None


async def test_the_findings_and_a_partial_notice_appear_in_the_artefact_text(parts, project, store):
    save_code(store, project, parts[3])
    cr = C.CodeReview("sonnet", "red", "one problem", (C.Finding("high", "backend/main.py", "builds SQL from text", "use a placeholder"),),
                      "Code reviewed by the Sonnet agent: 1 serious.", True, ("backend/big.py", "tests/test_big.py"), ("backend/main.py",), label="same_family")
    S.save(store, parts[3], project.id, {"sonnet": cr})
    body = store.artefacts.get_version(project.id, S.latest_record(store, project.id)["artefact_id"]).body
    assert "- [HIGH] backend/main.py: builds SQL from text Fix: use a placeholder" in body and "Summary: one problem" in body
    assert "This review is partial. Not shown to it: backend/big.py, tests/test_big.py." in body and "Independence: same family." in body


async def test_a_version_that_holds_no_reviews_does_not_count_and_the_earlier_one_is_still_found(parts, project, store):
    """A person may edit the review text. That version has no reviewer records; the last real results must not vanish."""
    save_code(store, project, parts[3])
    S.save(store, parts[3], project.id, {"sonnet": review_of("green"), "openai": review_of("red", "openai")})
    artefact_id = S.latest_record(store, project.id)["artefact_id"]
    store.artefacts.add_version(project.id, artefact_id, body="edited by a person", author="human:Ann", generation={"human_edit": True})
    record = S.latest_record(store, project.id)
    assert record["version"] == 1 and record["reviews"]["openai"]["colour"] == "red"
    store.artefacts.add_version(project.id, artefact_id, body="edited again", author="human:Ann")                          # a version with no generation at all
    assert S.latest_record(store, project.id)["version"] == 1


async def test_a_persons_edit_of_the_code_does_not_make_the_review_same_family_or_unverified(parts, project):
    cfg, provider, gateway, library = parts
    provider.queue("m-sonnet", text(CLEAN))
    r = await C.run_review(gateway, cfg, "sonnet", code_input(), "", [C.HUMAN], project_id=project.id)
    assert r.label == "independent"
    provider.queue("m-openai", text(CLEAN))
    r2 = await C.run_review(gateway, cfg, "openai", code_input(), "", ["gpt-6.1-sol", C.HUMAN], project_id=project.id)
    assert r2.label == "same_family"                                                                                        # the model-written part still counts


async def test_the_authors_come_from_the_saved_versions_and_a_persons_edit_is_a_person(parts, project, store):
    from app.build.phase import _authors
    save_code(store, project, parts[3])
    skill = parts[3].get("backend_code")
    store.artefacts.create_and_add_version(project.id, artefact_type="backend_code", phase_key="build", title="x", prefix=skill.artefact.id_prefix,
                                           body=make_body(GOOD, "BEF"), author="human:Ann")
    authors = _authors(store, project.id, parts[3])
    assert authors == ["gpt-6.1-sol", C.HUMAN, "gpt-6.1-sol", "gpt-6.1-sol"]                      # database, backend (edited by a person), frontend, tests


async def test_the_reviewers_are_told_who_wrote_the_code_so_the_label_is_real(world, project, store):
    runner, provider, hook, library = world()
    script(provider, fixes=[GOOD], sonnet=[CLEAN], openai=[CLEAN])
    await runner.run_phase(project.id, "build", only=FOUR)
    record = S.latest_record(store, project.id)
    assert record["reviews"]["sonnet"]["label"] in ("independent", "same_family") and record["reviews"]["openai"]["label"] in ("independent", "same_family")
    assert record["reviews"]["openai"]["label"] == "same_family"                                   # GPT reviewing code that GPT wrote
    assert record["reviews"]["sonnet"]["label"] in ("independent", "same_family")


async def test_the_review_is_written_after_the_report_in_the_same_run(world, project, store):
    runner, provider, *_ = world()
    script(provider, fixes=[GOOD], sonnet=[CLEAN], openai=[CLEAN])
    await runner.run_phase(project.id, "build", only=FOUR)
    report = store.artefacts.list(project.id, phase_key="build", artefact_type="test_report")[0]
    review = store.artefacts.list(project.id, phase_key="build", artefact_type="code_security_review")[0]
    assert report.id < review.id or store.artefacts.get_version(project.id, report.id).created_at <= store.artefacts.get_version(project.id, review.id).created_at


async def test_a_stop_before_the_reviewers_start_runs_none_and_saves_nothing(world, project, store):
    runner, provider, hook, library = world()
    save_code(store, project, library)                                                      # there IS code to review, so only the stop can be what prevents it
    provider.queue("m-sonnet", text(CLEAN))
    provider.queue("m-openai", text(CLEAN))
    done = {"backend_code", "frontend_code", "test_suite"}
    live = Meter(max_cost_usd=0, max_seconds=0)
    stopped = Meter(max_cost_usd=0, max_seconds=0)
    stopped.cancel()
    assert await hook.review_code(project.id, "run-1", done, stopped) == 0
    assert S.latest_record(store, project.id) is None and not [c for c in provider.calls if c.request.role == "security_reviewer"]
    assert await hook.review_code(project.id, "run-1", done, live) == 2                       # the same code, a meter that has not stopped: both reviewers run
    assert S.latest_record(store, project.id) is not None


async def test_the_hook_names_both_artefacts_it_writes(world):
    _, _, hook, _ = world()
    assert hook.writes("build") == ("test_report", "code_security_review")


async def test_the_reviewers_calls_are_counted_by_the_hook_and_reported(world, project, store):
    runner, provider, hook, library = world()
    script(provider, fixes=[GOOD], sonnet=[CLEAN], openai=[CLEAN])
    result = await runner.run_phase(project.id, "build", only=FOUR)
    assert result.build.calls == 3                                                                 # one fix and two reviews: the number is in the run's own result
