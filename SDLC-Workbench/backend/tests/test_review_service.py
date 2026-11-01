"""Reviewing an artefact end to end against a scripted model: what is stored, the label, the picker, and refusals."""
from __future__ import annotations

import itertools

import pytest

from app.agents.runtime import AgentRuntime
from app.agents.skills import SkillLibrary
from app.llm.errors import ContentFilterBlocked, ReviewerUnavailable, TransientProviderError
from app.llm.gateway import Gateway
from app.llm.providers.mock import MockProvider
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.review.errors import NothingToReview, ReviewOutputInvalid, WrongPhaseState
from app.review.prompt import load_rubric
from app.review.service import PausedReview, ReviewResult, ReviewService, author_model_of
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine

from .test_agent_runtime import (
    CHARTER_SECTIONS,
    PERSON,
    PERSONA_ITEMS,
    PERSONA_SECTIONS,
    PROBLEM_SECTIONS,
    chain_to_requirements,
    ok,
    reply,
)

pytestmark = pytest.mark.anyio

# Slots get distinct model IDs here so a test can tell which family answered.
MODELS = dict(
    ibm_ica_model_id="m-sonnet", ibm_ica_fallback_model_id="m-sonnet", ibm_ica_haiku_model_id="claude-haiku-x",
    ibm_ica_haiku_fallback_model_id="m-sonnet",
    ibm_ica_openai_model_id="gpt-x", ibm_ica_openai_fallback_model_id="m-sonnet",
    ibm_ica_gemini_model_id="gemini-x", ibm_ica_gemini_fallback_model_id="m-sonnet",
    ibm_ica_price_input_per_mtok="2", ibm_ica_price_output_per_mtok="10",
    ibm_ica_openai_price_input_per_mtok="2", ibm_ica_openai_price_output_per_mtok="10",
    ibm_ica_gemini_price_input_per_mtok="0.75", ibm_ica_gemini_price_output_per_mtok="3.75",
)
REVIEW_CLEAN = "<review>\nSummary: Nothing is wrong.\n</review>"
REVIEW_HIGH = "<review>\nSummary: One serious problem.\n- [HIGH] PER-001: Invented detail. Fix: remove it.\n- [LOW] Overview: wordy. Fix: trim.\n</review>"


def review_reply(text: str, tokens=(2000, 150)) -> ProviderResponse:
    return ProviderResponse(text, Usage(*tokens), "stop")


@pytest.fixture
def rig(make_settings, store, project):
    def build(**settings):
        cfg = make_settings(**{**MODELS, **settings})
        provider = MockProvider()
        ids = itertools.count(1)

        async def no_sleep(_):
            return None

        routing = Routing.load()
        catalogue = load_catalogue(routing.roles.keys())
        gateway = Gateway(cfg, routing, provider, store, sleep=no_sleep, call_id_factory=lambda: f"call{next(ids)}")
        engine = WorkflowEngine(catalogue, store)
        runtime = AgentRuntime(cfg, store, gateway, catalogue, engine, SkillLibrary.load(catalogue))
        service = ReviewService(cfg, store, gateway, runtime, engine, load_rubric())
        engine.open_project(project.id)
        engine.start(project.id, "setup", actor="system")
        return service, runtime, provider, engine

    return build


async def write_personas(runtime, provider, store, project, engine, model="m-sonnet"):
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue(model, ok(PERSONA_SECTIONS, items=PERSONA_ITEMS))
    return await runtime.run(project.id, "personas")


# ---- a review is stored on the version it read ----------------------------------------------------------------

async def test_a_review_is_stored_on_the_latest_version_with_everything_needed_to_trust_it(rig, store, project):
    service, runtime, provider, engine = rig()
    written = await write_personas(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", review_reply(REVIEW_HIGH))
    result = await service.review(project.id, written.artefact_id)

    assert (result.verdict, result.version, result.attempts) == ("revise", 1, 1)
    record = store.artefacts.get_version(project.id, written.artefact_id).review_findings
    assert record["version_reviewed"] == 1 and record["verdict"] == "revise" and record["summary"] == "One serious problem."
    assert [(f["severity"], f["target"]) for f in record["findings"]] == [("high", "PER-001"), ("low", "Overview")]
    assert record["reviewer"] == {"slot": "sonnet", "model": "m-sonnet", "family": "anthropic"}
    assert (record["tokens_in"], record["tokens_out"]) == (2000, 150) and record["cost_usd"] == pytest.approx(0.0055)
    assert len(record["call_ids"]) == 1 and record["attempts"] == 1


async def test_a_clean_review_has_no_findings_and_the_verdict_ok(rig, store, project):
    service, runtime, provider, engine = rig()
    written = await write_personas(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN))
    result = await service.review(project.id, written.artefact_id)
    assert result.verdict == "ok" and result.findings == ()


async def test_the_review_is_traced_under_the_reviewer_role_and_the_reviewer_slot(rig, store, project):
    service, runtime, provider, engine = rig()
    written = await write_personas(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN))
    await service.review(project.id, written.artefact_id, run_id="run-r")
    trace = store.traces.list(project.id)[-1]
    assert (trace.agent, trace.slot, trace.phase_key, trace.run_id) == ("security_reviewer", "sonnet", "requirements", "run-r")


async def test_a_re_review_replaces_the_findings_and_is_audited_as_a_replacement(rig, store, project):
    service, runtime, provider, engine = rig()
    written = await write_personas(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", review_reply(REVIEW_HIGH), review_reply(REVIEW_CLEAN))
    await service.review(project.id, written.artefact_id)
    await service.review(project.id, written.artefact_id)
    assert store.artefacts.get_version(project.id, written.artefact_id).review_findings["verdict"] == "ok"
    events = store.audit.list(project.id, action="artefact.reviewed")
    assert [e.detail["replaced"] for e in events] == [False, True]


async def test_the_review_prompt_contains_what_the_writer_was_given_and_the_cited_text(rig, store, project):
    store.context.add_document(project.id, "policy.md", b"# Rules\n\nStaff may book a room for up to four hours at a time.", actor=PERSON)
    store.projects.update(project.id, actor="system", brief="Staff may book a room for up to four hours at a time.")
    service, runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, extra="see [DOC-001#1]", items=PERSONA_ITEMS))
    written = await runtime.run(project.id, "personas")
    assert "DOC-001#1" in written.citations  # precondition: the writer really cited the document
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN))
    await service.review(project.id, written.artefact_id)
    prompt = provider.calls[-1].request
    user = prompt.messages[0].content
    assert "[DOC-001#1]" in user and "up to four hours" in user.split("Text of the sources the artefact cites")[1]
    assert "## [SET-CHR-001]" in user and "Quality bar" in prompt.system or "quality bar" in prompt.system.lower()


# ---- independence --------------------------------------------------------------------------------------------------

async def test_sonnet_reviewing_a_sonnet_artefact_is_labelled_same_family(rig, store, project):
    service, runtime, provider, engine = rig()
    written = await write_personas(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN))
    result = await service.review(project.id, written.artefact_id)
    assert result.independence == {"verdict": "same_family", "author_family": "anthropic", "reviewer_family": "anthropic", "fell_back": False}


async def test_sonnet_reviewing_an_artefact_written_by_another_family_is_labelled_independent(rig, store, project):
    service, runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    store.artefacts.create(project.id, artefact_type="personas", phase_key="requirements", title="Personas", actor="system", prefix="REQ-PER")
    store.artefacts.add_version(project.id, "REQ-PER-001", body=reply(PERSONA_SECTIONS, items=PERSONA_ITEMS).replace("<artefact>\n", "").replace("\n</artefact>", ""),
                                author="agent:requirements_analyst@gpt-x")
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN))
    result = await service.review(project.id, "REQ-PER-001")
    assert result.independence["verdict"] == "independent" and result.independence["author_family"] == "openai"


async def test_a_version_written_by_a_person_is_independent_and_the_author_is_shown_as_human(rig, store, project):
    service, runtime, provider, engine = rig()
    written = await write_personas(runtime, provider, store, project, engine)
    body = store.artefacts.get_version(project.id, written.artefact_id).body
    store.artefacts.add_version(project.id, written.artefact_id, body=body + "\nEdited.", author=PERSON)
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN))
    result = await service.review(project.id, written.artefact_id)
    assert result.independence["verdict"] == "independent" and result.independence["author_family"] == "human"
    assert author_model_of(store.artefacts.get_version(project.id, written.artefact_id)) is None


async def test_an_author_model_nobody_recognises_is_labelled_unverified(rig, store, project):
    service, runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    store.artefacts.create(project.id, artefact_type="personas", phase_key="requirements", title="Personas", actor="system", prefix="REQ-PER")
    store.artefacts.add_version(project.id, "REQ-PER-001", body="## Personas\n- PER-001 x. Derives from: SET-CHR-001", author="agent:requirements_analyst@mystery-9")
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN))
    assert (await service.review(project.id, "REQ-PER-001")).independence["verdict"] == "unverified"


# ---- the reviewer cannot run -----------------------------------------------------------------------------------------

async def test_a_reviewer_that_cannot_run_raises_the_options_with_independent_families_first_and_stores_nothing(rig, store, project):
    service, runtime, provider, engine = rig()
    written = await write_personas(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ContentFilterBlocked("blocked"))
    with pytest.raises(ReviewerUnavailable) as caught:
        await service.review(project.id, written.artefact_id)
    options = caught.value.options
    assert [o.slot for o in options] == ["gemini", "openai", "haiku"] and options[0].independent is True and options[2].independent is False
    assert "sonnet" not in [o.slot for o in options]
    assert store.artefacts.get_version(project.id, written.artefact_id).review_findings is None


async def test_the_person_picks_a_family_and_that_review_is_labelled_for_that_family(rig, store, project):
    service, runtime, provider, engine = rig()
    written = await write_personas(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ContentFilterBlocked("blocked"))
    with pytest.raises(ReviewerUnavailable):
        await service.review(project.id, written.artefact_id)
    provider.queue("gemini-x", review_reply(REVIEW_CLEAN))
    result = await service.review(project.id, written.artefact_id, slot="gemini", exclude=["sonnet"])
    assert result.independence["verdict"] == "independent" and result.independence["reviewer_family"] == "google"
    record = store.artefacts.get_version(project.id, written.artefact_id).review_findings
    assert record["reviewer"]["slot"] == "gemini" and record["reviewer"]["model"] == "gemini-x"


async def test_no_model_is_ever_switched_without_a_choice(rig, store, project):
    service, runtime, provider, engine = rig()
    written = await write_personas(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ContentFilterBlocked("blocked"))
    before = len(provider.calls)
    with pytest.raises(ReviewerUnavailable):
        await service.review(project.id, written.artefact_id)
    assert provider.models[before:] == ["m-sonnet"]  # one attempt on the reviewer, nothing tried elsewhere


async def test_in_a_phase_review_only_the_artefact_the_reviewer_failed_on_pauses(rig, store, project):
    service, runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=PERSONA_ITEMS), ok(PROBLEM_SECTIONS))
    await runtime.run(project.id, "personas")
    await runtime.run(project.id, "problem_statement")
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN), ContentFilterBlocked("blocked"))
    results = await service.review_phase(project.id, "requirements")
    assert isinstance(results[0], ReviewResult) and results[0].artefact_id == "REQ-PER-001"
    assert isinstance(results[1], PausedReview) and results[1].artefact_id == "REQ-PRB-001"
    assert [o.slot for o in results[1].options] == ["gemini", "openai", "haiku"]
    assert store.artefacts.get_version(project.id, "REQ-PER-001").review_findings is not None
    assert store.artefacts.get_version(project.id, "REQ-PRB-001").review_findings is None


# ---- repair ---------------------------------------------------------------------------------------------------------------

async def test_a_review_that_names_an_artefact_that_does_not_exist_is_sent_back_once_and_the_fix_is_stored(rig, store, project):
    service, runtime, provider, engine = rig()
    written = await write_personas(runtime, provider, store, project, engine)
    bad = "<review>\nSummary: s\n- [HIGH] PER-099: no such item. Fix: x\n</review>"
    provider.queue("m-sonnet", review_reply(bad), review_reply(REVIEW_HIGH))
    result = await service.review(project.id, written.artefact_id)
    assert result.attempts == 2
    assert "'PER-099', which is not an item ID or a section of this artefact" in provider.calls[-1].request.messages[-1].content
    record = store.artefacts.get_version(project.id, written.artefact_id).review_findings
    assert record["attempts"] == 2 and len(record["call_ids"]) == 2 and record["tokens_in"] == 4000
    assert record["cost_usd"] == pytest.approx(0.011) and result.cost_usd == pytest.approx(0.011)  # BOTH attempts, 2 x 0.0055
    assert all(f["target"] != "PER-099" for f in record["findings"])


async def test_a_review_that_stays_invalid_fails_with_every_reason_and_stores_nothing(rig, store, project):
    service, runtime, provider, engine = rig()
    written = await write_personas(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", review_reply("no tags here"), review_reply("still no tags"))
    with pytest.raises(ReviewOutputInvalid, match="no <review> block was found") as caught:
        await service.review(project.id, written.artefact_id)
    assert caught.value.attempts == 2
    assert store.artefacts.get_version(project.id, written.artefact_id).review_findings is None


async def test_a_review_cost_is_unknown_when_any_attempt_has_no_price(rig, store, project):
    service, runtime, provider, engine = rig(ibm_ica_price_input_per_mtok="", ibm_ica_price_output_per_mtok="")
    written = await write_personas(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN))
    result = await service.review(project.id, written.artefact_id)
    assert result.cost_usd is None
    assert store.artefacts.get_version(project.id, written.artefact_id).review_findings["cost_usd"] is None


# ---- refusals ------------------------------------------------------------------------------------------------------------------

async def test_an_artefact_with_no_version_and_one_with_no_skill_cannot_be_reviewed_and_no_call_is_made(rig, store, project):
    service, runtime, provider, engine = rig()
    store.artefacts.create(project.id, artefact_type="personas", phase_key="setup", title="Personas", actor="system", prefix="REQ-PER")
    with pytest.raises(NothingToReview, match="no version yet"):
        await service.review(project.id, "REQ-PER-001")
    store.artefacts.create(project.id, artefact_type="deployment_plan", phase_key="setup", title="X", actor="system", prefix="DEP-PLN")
    store.artefacts.add_version(project.id, "DEP-PLN-001", body="x", author=PERSON)
    with pytest.raises(NothingToReview, match="no skill for 'deployment_plan'"):
        await service.review(project.id, "DEP-PLN-001")
    assert provider.calls == []


async def test_a_phase_that_is_not_running_or_awaiting_review_cannot_have_its_artefacts_reviewed(rig, store, project):
    service, runtime, provider, engine = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    engine.finish(project.id, "setup", actor="system")
    engine.approve(project.id, "setup", actor=PERSON)
    with pytest.raises(WrongPhaseState, match="setup is 'approved'"):
        await service.review(project.id, "SET-CHR-001")
    assert len(provider.calls) == 1


async def test_a_phase_awaiting_review_can_be_reviewed(rig, store, project):
    service, runtime, provider, engine = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS), review_reply(REVIEW_CLEAN))
    await runtime.run(project.id, "project_charter")
    engine.finish(project.id, "setup", actor="system")
    assert (await service.review(project.id, "SET-CHR-001")).verdict == "ok"


async def test_an_unknown_artefact_is_not_found(rig, store, project):
    from app.models import NotFoundError

    service, *_ = rig()
    with pytest.raises(NotFoundError):
        await service.review(project.id, "REQ-PER-999")


async def test_another_projects_cited_text_never_reaches_the_reviewer(rig, store, project):
    other = store.projects.create(name="Other", actor="system")
    store.context.add_document(other.id, "secret.md", b"# Plan\n\nThe zeppelin launch is codenamed Bluebird.", actor=PERSON)
    service, runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    store.artefacts.create(project.id, artefact_type="personas", phase_key="requirements", title="Personas", actor="system", prefix="REQ-PER")
    store.artefacts.add_version(project.id, "REQ-PER-001", body="## Personas\n- PER-001 x [DOC-001#1]. Derives from: SET-CHR-001", author="agent:requirements_analyst@m-sonnet")
    assert store.context.resolve(project.id, "DOC-001#1") is None  # precondition: DOC-001 exists only in the OTHER project
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN))
    await service.review(project.id, "REQ-PER-001")
    user = provider.calls[-1].request.messages[0].content
    assert "Bluebird" not in user and "DOC-001#1" in user.split("Sources you were not given")[1]


async def test_cited_text_over_the_budget_is_named_as_omitted_not_cut(rig, store, project):
    store.context.add_document(project.id, "policy.md", b"# Rules\n\nStaff may book a room for up to four hours at a time.", actor=PERSON)
    service, runtime, provider, engine = rig(review_cited_max_chars=10)
    await chain_to_requirements(runtime, provider, store, project, engine)
    store.artefacts.create(project.id, artefact_type="personas", phase_key="requirements", title="Personas", actor="system", prefix="REQ-PER")
    store.artefacts.add_version(project.id, "REQ-PER-001", body="## Personas\n- PER-001 x [DOC-001#1]. Derives from: SET-CHR-001", author="agent:requirements_analyst@m-sonnet")
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN))
    await service.review(project.id, "REQ-PER-001")
    user = provider.calls[-1].request.messages[0].content
    assert "up to four hours" not in user and "DOC-001#1" in user.split("Sources you were not given")[1]


# ---- where a review stands -------------------------------------------------------------------------------------------------------

async def test_status_moves_unreviewed_then_reviewed_then_stale_when_a_new_version_is_written(rig, store, project):
    service, runtime, provider, engine = rig()
    written = await write_personas(runtime, provider, store, project, engine)
    assert service.status_of(project.id, written.artefact_id).state == "unreviewed"
    provider.queue("m-sonnet", review_reply(REVIEW_HIGH))
    await service.review(project.id, written.artefact_id)
    status = service.status_of(project.id, written.artefact_id)
    assert (status.state, status.verdict, status.high_findings, status.reviewed_version) == ("reviewed", "revise", 1, 1)
    store.artefacts.add_version(project.id, written.artefact_id, body="## Personas\n- PER-001 edited. Derives from: SET-CHR-001", author=PERSON)
    stale = service.status_of(project.id, written.artefact_id)
    assert (stale.state, stale.reviewed_version, stale.latest_version, stale.verdict) == ("stale", 1, 2, "revise")


async def test_the_new_version_has_no_review_of_its_own_until_it_is_reviewed(rig, store, project):
    service, runtime, provider, engine = rig()
    written = await write_personas(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN))
    await service.review(project.id, written.artefact_id)
    store.artefacts.add_version(project.id, written.artefact_id, body="## Personas\n- PER-001 v2. Derives from: SET-CHR-001", author=PERSON)
    assert store.artefacts.get_version(project.id, written.artefact_id, 1).review_findings is not None
    assert store.artefacts.get_version(project.id, written.artefact_id).review_findings is None


async def test_phase_status_lists_every_artefact_that_exists(rig, store, project):
    service, runtime, provider, engine = rig()
    await write_personas(runtime, provider, store, project, engine)
    assert [(s.artefact_id, s.state) for s in service.phase_status(project.id, "requirements")] == [("REQ-PER-001", "unreviewed")]


# ---- gaps found by the S08 mutation check ---------------------------------------------------------------------------------

async def test_a_review_is_stored_on_the_version_it_read_and_an_earlier_version_is_left_alone(rig, store, project):
    service, runtime, provider, engine = rig()
    written = await write_personas(runtime, provider, store, project, engine)
    store.artefacts.add_version(project.id, written.artefact_id, body="## Personas\n- PER-001 second. Derives from: SET-CHR-001", author=PERSON)
    provider.queue("m-sonnet", review_reply("<review>\nSummary: s\n- [HIGH] PER-001: invented. Fix: remove it.\n</review>"))
    result = await service.review(project.id, written.artefact_id)
    assert result.version == 2 and result.attempts == 1
    assert store.artefacts.get_version(project.id, written.artefact_id, 1).review_findings is None
    assert store.artefacts.get_version(project.id, written.artefact_id, 2).review_findings["version_reviewed"] == 2


async def test_a_pause_on_the_first_artefact_does_not_stop_the_rest_of_the_phase_being_reviewed(rig, store, project):
    service, runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=PERSONA_ITEMS), ok(PROBLEM_SECTIONS))
    await runtime.run(project.id, "personas")
    await runtime.run(project.id, "problem_statement")
    provider.queue("m-sonnet", ContentFilterBlocked("blocked"), review_reply(REVIEW_CLEAN))
    results = await service.review_phase(project.id, "requirements")
    assert isinstance(results[0], PausedReview) and results[0].artefact_id == "REQ-PER-001"
    assert isinstance(results[1], ReviewResult) and results[1].artefact_id == "REQ-PRB-001"
    assert store.artefacts.get_version(project.id, "REQ-PER-001").review_findings is None
    assert store.artefacts.get_version(project.id, "REQ-PRB-001").review_findings is not None


async def test_an_upstream_artefact_the_writer_cited_is_shown_once_in_full_and_not_reported_as_missing(rig, store, project):
    service, runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, extra="from the charter [SET-CHR-001]", items=PERSONA_ITEMS))
    written = await runtime.run(project.id, "personas")
    assert written.citations == ("SET-CHR-001",)   # precondition: the artefact really cites a whole upstream artefact
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN))
    await service.review(project.id, written.artefact_id)
    user = provider.calls[-1].request.messages[0].content
    assert user.count("## [SET-CHR-001]") == 1
    assert "Sources you were not given" not in user and "Text of the sources the artefact cites" not in user


async def test_a_repaired_review_records_what_was_wrong_with_the_first_reply(rig, store, project):
    service, runtime, provider, engine = rig()
    written = await write_personas(runtime, provider, store, project, engine)
    bad = "<review>\nSummary: s\n- [HIGH] PER-099: no such item. Fix: x\n</review>"
    provider.queue("m-sonnet", review_reply(bad), review_reply(REVIEW_HIGH))
    result = await service.review(project.id, written.artefact_id)
    record = store.artefacts.get_version(project.id, written.artefact_id).review_findings
    assert result.attempts == 2 and record["attempts"] == 2
    [entry] = record["repair_reasons"]
    assert entry["attempt"] == 1 and entry["call_id"] == record["call_ids"][0]
    assert any("'PER-099', which is not an item ID or a section of this artefact" in p for p in entry["problems"])


async def test_each_failed_review_attempt_is_logged_against_its_own_call(make_settings, rig, store, project):
    service, runtime, provider, engine = rig(review_max_repairs=2)
    written = await write_personas(runtime, provider, store, project, engine)
    bad1 = "<review>\nSummary: s\n- [HIGH] PER-099: no such item. Fix: x\n</review>"
    bad2 = "<review>\nSummary: s\n- [LOW] Nonsense section: x. Fix: y\n</review>"
    provider.queue("m-sonnet", review_reply(bad1), review_reply(bad2), review_reply(REVIEW_CLEAN))
    await service.review(project.id, written.artefact_id)
    record = store.artefacts.get_version(project.id, written.artefact_id).review_findings
    entries = record["repair_reasons"]
    assert record["attempts"] == 3 and [e["attempt"] for e in entries] == [1, 2]
    assert [e["call_id"] for e in entries] == record["call_ids"][:2] and entries[0]["call_id"] != entries[1]["call_id"]
    assert "PER-099" in " ".join(entries[0]["problems"]) and "Nonsense section" in " ".join(entries[1]["problems"])


async def test_a_review_that_needed_no_repair_records_an_empty_list(rig, store, project):
    service, runtime, provider, engine = rig()
    written = await write_personas(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN))
    await service.review(project.id, written.artefact_id)
    assert store.artefacts.get_version(project.id, written.artefact_id).review_findings["repair_reasons"] == []
