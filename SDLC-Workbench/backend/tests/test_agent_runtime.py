"""The agent runtime end to end against a scripted model: gather, prompt, call, check, repair, save."""
from __future__ import annotations

import asyncio
import itertools
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.agents.errors import (
    ArtefactNotInPlan,
    InputTooLarge,
    MissingInput,
    NoSkill,
    OutputInvalid,
    PhaseNotRunning,
)
from app.agents.runtime import AgentRuntime, sum_costs
from app.agents.skills import SkillLibrary
from app.llm.errors import AuthenticationFailed, LLMCallFailed, ReplayMiss, SlotNotConfigured
from app.llm.gateway import Gateway
from app.llm.providers.mock import MockProvider
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.models import NotFoundError
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine

pytestmark = pytest.mark.anyio

PERSON = "human:ann"
MODELS = dict(
    ibm_ica_model_id="m-sonnet", ibm_ica_fallback_model_id="m-sonnet", ibm_ica_haiku_model_id="m-haiku",
    ibm_ica_openai_model_id="m-openai", ibm_ica_gemini_model_id="m-gemini",
    ibm_ica_price_input_per_mtok="2", ibm_ica_price_output_per_mtok="10",
)

CHARTER_SECTIONS = ["Purpose", "Scope", "Out of scope", "Stakeholders", "Success measures", "Constraints and assumptions", "Open questions"]
PERSONA_SECTIONS = ["Overview", "Personas", "How the personas differ", "Open questions"]
PROBLEM_SECTIONS = ["The problem", "Who is affected", "Impact today", "Why it matters now", "Evidence and assumptions"]
FR_SECTIONS = ["Overview", "Requirements", "Business rules", "Traceability notes", "Open questions"]


# Artefacts that hold numbered items need them in a reply; these are the smallest valid ones.
PERSONA_ITEMS = {"Personas": "- PER-001 Office staff member who books rooms. Derives from: SET-CHR-001"}
FR_ITEMS = {"Requirements": "- FR-001 The system shall refuse a double booking, for PER-001. Derives from: PER-001, REQ-PRB-001"}


def reply(sections: list[str], extra: str = "", items: dict[str, str] | None = None) -> str:
    """A well-formed reply. `items` replaces the filler text of the sections it names with real item lines."""
    items = items or {}
    body = "\n".join(f"## {name}\n{items[name] if name in items else f'Text for {name}. {extra}'}" for name in sections)
    return f"<artefact>\n{body}\n</artefact>"


def ok(sections: list[str], extra: str = "", tokens: tuple[int, int] = (1000, 200), items: dict[str, str] | None = None) -> ProviderResponse:
    return ProviderResponse(reply(sections, extra, items), Usage(*tokens), "stop")


@pytest.fixture(scope="module")
def catalogue():
    return load_catalogue(Routing.load().roles.keys())


@pytest.fixture
def rig(make_settings, store, project, catalogue):
    def build(**settings):
        cfg = make_settings(**{**MODELS, **settings})
        provider = MockProvider()
        ids = itertools.count(1)

        async def no_sleep(_):
            return None

        gateway = Gateway(cfg, Routing.load(), provider, store, sleep=no_sleep, call_id_factory=lambda: f"call{next(ids)}")
        engine = WorkflowEngine(catalogue, store)
        runtime = AgentRuntime(cfg, store, gateway, catalogue, engine, SkillLibrary.load(catalogue))
        engine.open_project(project.id)
        engine.start(project.id, "setup", actor="system")
        return runtime, provider, engine

    return build


def sent(provider: MockProvider, n: int = 0) -> str:
    return provider.calls[n].request.messages[0].content


# ---- the happy path ---------------------------------------------------------------------------------------

async def test_a_charter_is_written_checked_and_saved_as_version_one(rig, store, project):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    result = await runtime.run(project.id, "project_charter")

    assert (result.artefact_id, result.version, result.attempts, result.created_artefact) == ("SET-CHR-001", 1, 1, True)
    assert result.author == "agent:orchestrator@m-sonnet" and result.served_models == ("m-sonnet",)
    assert (result.tokens_in, result.tokens_out) == (1000, 200) and result.cost_usd == pytest.approx(0.004)
    version = store.artefacts.get_version(project.id, "SET-CHR-001")
    assert version.author == result.author and "## Purpose" in version.body and "<artefact>" not in version.body
    artefact = store.artefacts.get(project.id, "SET-CHR-001")
    assert (artefact.type, artefact.phase_key, artefact.title) == ("project_charter", "setup", "Project charter")


async def test_a_second_run_adds_version_two_to_the_same_artefact(rig, store, project):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS, "first"), ok(CHARTER_SECTIONS, "second"))
    first = await runtime.run(project.id, "project_charter")
    second = await runtime.run(project.id, "project_charter")
    assert (first.version, second.version, second.artefact_id, second.created_artefact) == (1, 2, "SET-CHR-001", False)
    assert len(store.artefacts.list(project.id)) == 1
    assert "second" in store.artefacts.get_version(project.id, "SET-CHR-001").body
    assert "first" in store.artefacts.get_version(project.id, "SET-CHR-001", 1).body


async def test_the_generation_record_is_stored_on_the_version_and_matches_the_result(rig, store, project):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    result = await runtime.run(project.id, "project_charter", run_id="run-7")
    gen = store.artefacts.get_version(project.id, result.artefact_id).generation
    assert (gen["skill"], gen["run_id"], gen["attempts"], gen["repairs"]) == ("project_charter", "run-7", 1, 0)
    assert (gen["tokens_in"], gen["tokens_out"], gen["cost_usd"]) == (1000, 200, pytest.approx(0.004))
    assert [c["call_id"] for c in gen["calls"]] == list(result.call_ids) and gen["calls"][0]["model"] == "m-sonnet"


async def test_every_call_is_traced_with_the_role_the_phase_and_the_run(rig, store, project):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter", run_id="run-9")
    [trace] = store.traces.list(project.id)
    assert (trace.agent, trace.slot, trace.phase_key, trace.run_id, trace.status) == ("orchestrator", "sonnet", "setup", "run-9", "ok")


async def test_the_artefact_is_written_by_the_slot_its_role_routes_to(rig, store, project, catalogue):
    runtime, provider, engine = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    assert provider.models == ["m-sonnet"]  # orchestrator -> sonnet


async def test_a_fallback_model_is_visible_in_the_author(rig, store, project):
    runtime, provider, _ = rig(ibm_ica_model_id="", ibm_ica_fallback_model_id="m-fallback")
    provider.queue("m-fallback", ok(CHARTER_SECTIONS))
    result = await runtime.run(project.id, "project_charter")
    assert result.author == "agent:orchestrator@m-fallback"
    assert store.artefacts.get_version(project.id, "SET-CHR-001").generation["calls"][0]["fallback_used"] is True


async def test_stored_citations_are_the_ids_actually_cited_in_order_of_first_use(rig, store, project):
    runtime, provider, _ = rig()
    store.context.add_document(project.id, "p.md", b"# Rules\n\nStaff may book a room for four hours at a time.\n\n# Cancel\n\nCancel free up to 24 hours before.", actor=PERSON)
    store.projects.update(project.id, actor="system", brief="Staff may book a room for four hours at a time. Cancel free up to 24 hours before.")
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS, "see [DOC-001#2] then [DOC-001#1] and again [DOC-001#2]"))
    result = await runtime.run(project.id, "project_charter")
    assert result.citations == ("DOC-001#2", "DOC-001#1")
    assert store.artefacts.get_version(project.id, "SET-CHR-001").source_chunks == ("DOC-001#2", "DOC-001#1")


async def test_audit_rows_record_the_creation_and_the_version(rig, store, project):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    actions = [(e.action, e.actor) for e in store.audit.list(project.id) if e.target_id == "SET-CHR-001"]
    assert actions == [("artefact.created", "agent:orchestrator@m-sonnet"), ("artefact.version_added", "agent:orchestrator@m-sonnet")]


# ---- repair ------------------------------------------------------------------------------------------------------

async def test_an_invented_citation_is_caught_repaired_and_the_good_version_is_what_is_saved(rig, store, project):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS, "claims [DOC-777#1]", (1000, 200)), ok(CHARTER_SECTIONS, "clean", (1100, 210)))
    result = await runtime.run(project.id, "project_charter")
    assert result.attempts == 2 and result.citations == ()
    body = store.artefacts.get_version(project.id, "SET-CHR-001").body
    assert "clean" in body and "DOC-777" not in body
    gen = store.artefacts.get_version(project.id, "SET-CHR-001").generation
    assert (gen["attempts"], gen["repairs"], gen["tokens_in"], gen["tokens_out"]) == (2, 1, 2100, 410)


async def test_the_follow_up_contains_the_bad_reply_and_the_specific_error(rig, project):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS, "claims [DOC-777#1]"), ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    follow_up = provider.calls[1].request.messages
    assert [m.role for m in follow_up] == ["user", "assistant", "user"]
    assert "DOC-777#1" in follow_up[1].content                       # the bad reply, echoed back
    assert "you cited [DOC-777#1]" in follow_up[2].content           # and what was wrong with it
    assert follow_up[0].content == provider.calls[0].request.messages[0].content  # the original task is unchanged


async def test_success_on_the_third_attempt_after_two_different_failures(rig, store, project):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", "no tags here at all", ok(CHARTER_SECTIONS[:-1]), ok(CHARTER_SECTIONS))
    result = await runtime.run(project.id, "project_charter")
    assert result.attempts == 3
    second_follow_up = provider.calls[2].request.messages[-1].content
    assert "'Open questions' is missing" in second_follow_up
    assert "no <artefact> block" in provider.calls[1].request.messages[-1].content


async def test_failure_after_the_repair_cap_saves_nothing_and_reports_the_last_problem(rig, store, project):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", *[ok(CHARTER_SECTIONS, "claims [DOC-777#1]") for _ in range(5)])
    with pytest.raises(OutputInvalid) as exc:
        await runtime.run(project.id, "project_charter")
    assert exc.value.attempts == 3 and len(provider.calls) == 3  # 1 + the default 2 repairs, never more
    assert "Nothing was saved" in str(exc.value) and "DOC-777#1" in str(exc.value)
    assert store.artefacts.list(project.id) == []


@pytest.mark.parametrize("repairs, calls_made", [(0, 1), (1, 2), (4, 5)])
async def test_the_repair_cap_is_a_setting(rig, store, project, repairs, calls_made):
    runtime, provider, _ = rig(agent_max_repairs=repairs)
    provider.queue("m-sonnet", *[ok(CHARTER_SECTIONS[:-1]) for _ in range(9)])
    with pytest.raises(OutputInvalid) as exc:
        await runtime.run(project.id, "project_charter")
    assert len(provider.calls) == calls_made == exc.value.attempts


async def test_a_truncated_reply_is_rejected_even_if_it_looks_complete(rig, store, project):
    runtime, provider, _ = rig()
    cut = ProviderResponse(reply(CHARTER_SECTIONS), Usage(1000, 8000), "length")
    provider.queue("m-sonnet", cut, ok(CHARTER_SECTIONS))
    assert (await runtime.run(project.id, "project_charter")).attempts == 2
    assert "cut off" in provider.calls[1].request.messages[-1].content


async def test_cost_and_tokens_are_summed_across_attempts(rig, project):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS, "[DOC-9#1] [DOC-777#1]", (1_000_000, 0)), ok(CHARTER_SECTIONS, "", (0, 1_000_000)))
    result = await runtime.run(project.id, "project_charter")
    assert (result.tokens_in, result.tokens_out) == (1_000_000, 1_000_000) and result.cost_usd == pytest.approx(12.0)


async def test_unknown_cost_on_any_attempt_makes_the_total_unknown_never_zero_or_partial(rig, store, project):
    runtime, provider, _ = rig(ibm_ica_price_input_per_mtok="", ibm_ica_price_output_per_mtok="")
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS, "[DOC-777#1]"), ok(CHARTER_SECTIONS))
    result = await runtime.run(project.id, "project_charter")
    assert result.cost_usd is None
    assert store.artefacts.get_version(project.id, "SET-CHR-001").generation["cost_usd"] is None


def test_sum_costs_is_a_total_only_when_every_part_is_known():
    assert sum_costs([0.1, 0.2]) == pytest.approx(0.3) and sum_costs([0.0, 0.0]) == 0.0
    assert sum_costs([0.1, None]) is None and sum_costs([None]) is None and sum_costs([]) is None


# ---- model failures ------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("failure, expected", [
    (AuthenticationFailed("401"), LLMCallFailed),
    (ReplayMiss("no recording for this request"), LLMCallFailed),
])
async def test_a_model_failure_fails_the_run_with_the_gateways_message_and_saves_nothing(rig, store, project, failure, expected):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", failure)
    with pytest.raises(expected):
        await runtime.run(project.id, "project_charter")
    assert store.artefacts.list(project.id) == []


async def test_a_slot_with_no_model_fails_before_any_call(rig, store, project):
    runtime, provider, _ = rig(ibm_ica_model_id="", ibm_ica_fallback_model_id="")
    with pytest.raises(SlotNotConfigured):
        await runtime.run(project.id, "project_charter")
    assert provider.calls == [] and store.artefacts.list(project.id) == []


# ---- refusals before any model call -----------------------------------------------------------------------------------

async def test_refusals_make_no_call_no_trace_and_save_nothing(rig, store, project):
    runtime, provider, _ = rig()
    for key, error, fragment in [
        ("gadgets", ArtefactNotInPlan, "not an artefact in the workflow catalogue"),
        ("support_guide", NoSkill, "no skill for 'support_guide'"),
        ("personas", PhaseNotRunning, "requirements is 'not_started'"),
        ("problem_statement", PhaseNotRunning, "requirements is 'not_started'"),
    ]:
        with pytest.raises(error, match=fragment):
            await runtime.run(project.id, key)
    with pytest.raises(NotFoundError):
        await runtime.run("nope", "project_charter")
    assert provider.calls == [] and store.traces.list(project.id) == [] and store.artefacts.list(project.id) == []


async def test_a_phase_that_is_approved_or_awaiting_review_refuses_to_generate(rig, store, project):
    runtime, provider, engine = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    engine.finish(project.id, "setup", actor="system")
    with pytest.raises(PhaseNotRunning, match="awaiting_review"):
        await runtime.run(project.id, "project_charter")
    engine.approve(project.id, "setup", actor=PERSON)
    with pytest.raises(PhaseNotRunning, match="approved"):
        await runtime.run(project.id, "project_charter")
    assert len(provider.calls) == 1


async def test_an_artefact_switched_off_for_this_project_is_refused_even_though_it_has_a_skill(rig, store, catalogue, tmp_path):
    """None of the four shipped skills is optional, so give 'user_stories' (optional) a skill of its own."""
    (tmp_path / "user_stories.md").write_text(
        "# Skill: User stories\n## Role\nYou write stories.\n## Inputs\n- search: stories\n"
        "## Output\nArtefact: user_stories\nRequired sections:\n- Stories\n"
        "## Method\n1. Write.\n## Quality bar\n- Clear.\n## Never\n- Invent.\n"
    )
    trimmed = store.projects.create(name="Trimmed", actor="system", selection={
        "requirements": [a.key for a in catalogue.phase("requirements").artefacts if a.required]})
    full = store.projects.create(name="Full", actor="system")
    runtime, provider, engine = rig()
    runtime.skills = SkillLibrary.load(catalogue, tmp_path)
    for p in (trimmed, full):
        engine.open_project(p.id)
        store.phases.ensure(p.id, "requirements")
    with pytest.raises(ArtefactNotInPlan, match="'User stories' was switched off for this project"):
        await runtime.run(trimmed.id, "user_stories")
    # The same skill on a project that kept the artefact gets past the plan check and stops at the next one.
    with pytest.raises(PhaseNotRunning):
        await runtime.run(full.id, "user_stories")
    assert provider.calls == []


async def test_missing_upstream_stops_the_run_and_names_what_is_missing(rig, store, project):
    runtime, provider, engine = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    engine.finish(project.id, "setup", actor="system")
    engine.approve(project.id, "setup", actor=PERSON)
    engine.start(project.id, "requirements", actor="system")
    with pytest.raises(MissingInput, match="'Functional requirements' builds on 'Personas', which has not been written yet"):
        await runtime.run(project.id, "functional_requirements")
    assert len(provider.calls) == 1  # only the charter call


async def test_an_upstream_artefact_that_exists_but_has_no_versions_counts_as_missing(rig, store, project):
    runtime, provider, engine = rig()
    store.artefacts.create(project.id, artefact_type="project_charter", phase_key="setup", title="Project charter",
                           actor="system", prefix="SET-CHR")  # created, never given a version
    with pytest.raises(MissingInput, match="'Personas' builds on 'Project charter', which has not been written yet"):
        runtime._upstream(project.id, runtime.skills.get("personas"))
    assert provider.calls == []


# ---- upstream size and the prompt it produces ------------------------------------------------------------------------

async def chain_to_requirements(runtime, provider, store, project, engine):
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS, "charter body"))
    await runtime.run(project.id, "project_charter")
    engine.finish(project.id, "setup", actor="system")
    engine.approve(project.id, "setup", actor=PERSON)
    engine.start(project.id, "requirements", actor="system")


async def test_an_upstream_artefact_is_shown_in_full_and_citable(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, "from the charter [SET-CHR-001]", items=PERSONA_ITEMS))
    result = await runtime.run(project.id, "personas")
    prompt = sent(provider, 1)
    assert "## [SET-CHR-001] Project charter" in prompt and "charter body" in prompt
    assert result.citations == ("SET-CHR-001",) and result.artefact_id == "REQ-PER-001"


async def test_the_chain_gives_each_artefact_its_own_prefix_and_number(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=PERSONA_ITEMS), ok(PROBLEM_SECTIONS),
                   ok(FR_SECTIONS, "from [REQ-PER-001] and [REQ-PRB-001]", items=FR_ITEMS))
    ids = [(await runtime.run(project.id, key)).artefact_id for key in ("personas", "problem_statement", "functional_requirements")]
    assert ids == ["REQ-PER-001", "REQ-PRB-001", "REQ-F-001"]
    fr_prompt = sent(provider, 3)
    for upstream in ("SET-CHR-001", "REQ-PER-001", "REQ-PRB-001"):
        assert f"## [{upstream}]" in fr_prompt
    assert store.artefacts.get_version(project.id, "REQ-F-001").source_chunks == ("REQ-PER-001", "REQ-PRB-001")


async def test_an_approved_upstream_artefact_is_shown_once_in_full_and_never_repeated_as_a_fenced_chunk(rig, store, project):
    """Once the charter is approved it is also in the search index. It must not reach the model twice:
    the full text is already in the prompt, and a second copy as a 'retrieved' chunk would waste the budget
    and let the model cite the same passage under two different IDs. The brief is made to match the charter
    so the chunks WOULD clear the coverage floor if nothing excluded them (found by a mutation check: no
    earlier test had this overlap, so removing the exclusion went unnoticed)."""
    brief = "Staff may book a room for up to four hours at a time during office hours."
    store.projects.update(project.id, actor="system", brief=brief)
    runtime, provider, engine = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS, brief))  # the charter repeats the brief's words in every section
    await runtime.run(project.id, "project_charter")
    engine.finish(project.id, "setup", actor="system")
    engine.approve(project.id, "setup", actor=PERSON)
    engine.start(project.id, "requirements", actor="system")

    # Precondition: the charter really is searchable and really does match the brief well enough to be retrieved.
    assert store.context.search(project.id, brief, kinds=["artefact"], min_coverage=0.5), "the test would be vacuous"

    provider.queue("m-sonnet", ok(PROBLEM_SECTIONS))
    await runtime.run(project.id, "problem_statement")
    prompt = sent(provider, 1)
    assert prompt.count("## [SET-CHR-001]") == 1                      # in full, once
    assert "[SET-CHR-001@v1#" not in prompt                            # and not again as a chunk
    assert "BEGIN UNTRUSTED" not in prompt                             # nothing else to retrieve either


async def test_a_citation_of_an_upstream_artefact_that_was_not_an_input_is_refused(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, "[REQ-PRB-001]", items=PERSONA_ITEMS), ok(PERSONA_SECTIONS, items=PERSONA_ITEMS))  # personas does not take problem_statement
    result = await runtime.run(project.id, "personas")
    # calls[0] is the charter; calls[1] is the first personas attempt; calls[2] is the repair that follows it.
    assert result.attempts == 2 and len(provider.calls) == 3
    repair = provider.calls[2].request.messages[-1].content
    assert "you cited [REQ-PRB-001]" in repair and "not provided" in repair
    assert "REQ-PRB-001" not in provider.calls[1].request.messages[0].content  # it was never shown, so citing it is invented


async def test_upstream_over_budget_refuses_and_names_the_biggest_artefacts_without_cutting(rig, store, project):
    runtime, provider, engine = rig(agent_upstream_max_chars=1000)
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS, "x" * 1500))
    await runtime.run(project.id, "project_charter")
    engine.finish(project.id, "setup", actor="system")
    engine.approve(project.id, "setup", actor=PERSON)
    engine.start(project.id, "requirements", actor="system")
    with pytest.raises(InputTooLarge, match=r"over the 1000 limit.*Project charter \(\d+ characters\).*Nothing is cut silently"):
        await runtime.run(project.id, "problem_statement")
    assert len(provider.calls) == 1


# ---- retrieval and feedback ---------------------------------------------------------------------------------------------------

async def test_retrieved_documents_appear_in_the_fenced_block_with_their_ids(rig, store, project):
    runtime, provider, _ = rig()
    store.context.add_document(project.id, "policy.md", b"# Booking rules\n\nStaff may book a room for up to four hours at a time.", actor=PERSON)
    store.projects.update(project.id, actor="system", brief="Staff may book a room for up to four hours at a time.")
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    prompt = sent(provider)
    begin, end = prompt.index("BEGIN UNTRUSTED"), prompt.index("END UNTRUSTED")
    block = prompt[begin:end]
    # The brief repeats this sentence above the fence, so look INSIDE the block rather than anywhere in the prompt.
    assert "[DOC-001#1]" in block and "four hours" in block


async def test_other_projects_documents_never_reach_the_prompt(rig, store, project):
    runtime, provider, _ = rig()
    other = store.projects.create(name="Other", actor="system")
    store.context.add_document(other.id, "secret.md", b"# Plan\n\nThe zeppelin launch is codenamed Bluebird for office staff.", actor=PERSON)
    store.projects.update(project.id, actor="system", brief="The zeppelin launch is codenamed Bluebird for office staff.")
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    assert "Bluebird" not in sent(provider).split("# Project brief")[1].split("# Sources")[0].replace("The zeppelin launch is codenamed Bluebird for office staff.", "", 1)
    assert "DOC-001" not in sent(provider)


async def test_a_weak_match_below_the_coverage_floor_is_not_shown(rig, store, project):
    runtime, provider, _ = rig()
    store.context.add_document(project.id, "policy.md", b"# Notes\n\nThe cafeteria opens early on Fridays.", actor=PERSON)
    store.projects.update(project.id, actor="system", brief="Staff book meeting rooms for focused project work.")
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    assert "cafeteria" not in sent(provider)


async def test_feedback_and_a_previous_draft_appear_only_when_supplied(rig, store, project):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS), ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    assert "# Feedback to address" not in sent(provider, 0)
    await runtime.run(project.id, "project_charter", feedback=["Add a peak-load note"], previous_draft="THE-OLD-DRAFT")
    second = sent(provider, 1)
    assert "- Add a peak-load note" in second and "THE-OLD-DRAFT" in second


async def test_memory_feedback_for_this_artefact_or_phase_is_included_and_other_artefacts_feedback_is_not(rig, store, project):
    runtime, provider, _ = rig()
    mine = store.artefacts.create(project.id, artefact_type="project_charter", phase_key="setup", title="Project charter", actor="system", prefix="SET-CHR")
    store.artefacts.add_version(project.id, mine.id, body="draft", author=PERSON)
    other = store.artefacts.create(project.id, artefact_type="x", phase_key="setup", title="Other", actor="system", artefact_id="SET-OTH-001")
    phase_wide = store.memory.add(project.id, "human_feedback", "Phase-wide note about tone.", actor=PERSON, phase_key="setup")
    for_mine = store.memory.add(project.id, "reviewer_feedback", "Mention the cost centre.", actor="agent:r@m", phase_key="setup", artefact_id=mine.id)
    store.memory.add(project.id, "reviewer_feedback", "About the OTHER artefact only.", actor="agent:r@m", phase_key="setup", artefact_id=other.id)
    store.memory.add(project.id, "note", "A plain note, not feedback.", actor=PERSON, phase_key="setup")
    store.memory.add(project.id, "human_feedback", "Feedback for a different phase.", actor=PERSON, phase_key="design")
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    prompt = sent(provider)
    assert f"[MEM-{phase_wide.id:03d}] Phase-wide note about tone." in prompt and f"[MEM-{for_mine.id:03d}] Mention the cost centre." in prompt
    for absent in ("OTHER artefact", "plain note", "different phase"):
        assert absent not in prompt


async def test_the_runs_own_earlier_versions_are_not_retrieved_back_into_it(rig, store, project):
    runtime, provider, engine = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS, "distinctive wording about rooms and staff"), ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    store.projects.update(project.id, actor="system", brief="Distinctive wording about rooms and staff.")
    await runtime.run(project.id, "project_charter")
    assert "BEGIN UNTRUSTED" not in sent(provider, 1)  # nothing to retrieve: it is not approved, and not its own output anyway


# ---- saving --------------------------------------------------------------------------------------------------------------------

async def test_a_phase_that_stops_running_while_the_model_is_thinking_saves_nothing(rig, store, project):
    runtime, provider, engine = rig()

    class Closing(MockProvider):
        async def complete(self, model_id, request):
            engine.finish(project.id, "setup", actor="system")  # the phase moves on during the call
            return await super().complete(model_id, request)

    closing = Closing()
    runtime.gateway.provider = closing
    closing.queue("m-sonnet", ok(CHARTER_SECTIONS))
    with pytest.raises(PhaseNotRunning, match="was not saved.*awaiting_review"):
        await runtime.run(project.id, "project_charter")
    assert store.artefacts.list(project.id) == []


async def test_a_failure_during_the_save_leaves_no_half_made_artefact(rig, store, project, monkeypatch):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    real = store.artefacts._append_version

    def boom(*args, **kwargs):
        raise RuntimeError("disk on fire")

    monkeypatch.setattr(store.artefacts, "_append_version", boom)
    with pytest.raises(RuntimeError):
        await runtime.run(project.id, "project_charter")
    monkeypatch.setattr(store.artefacts, "_append_version", real)
    assert store.artefacts.list(project.id) == []  # the artefact row was rolled back with the failed version
    assert not [e for e in store.audit.list(project.id) if e.action.startswith("artefact.")]


# ---- concurrency ------------------------------------------------------------------------------------------------------------------

def test_eight_threads_saving_the_same_artefact_make_one_artefact_and_eight_versions(store, project):
    def save(n):
        return store.artefacts.create_and_add_version(
            project.id, artefact_type="project_charter", phase_key="setup", title="Project charter",
            prefix="SET-CHR", body=f"body {n}", author="agent:orchestrator@m",
        )[1].number

    with ThreadPoolExecutor(max_workers=8) as pool:
        numbers = list(pool.map(save, range(8)))
    assert sorted(numbers) == list(range(1, 9)) and len(store.artefacts.list(project.id)) == 1
    assert store.artefacts.list(project.id)[0].id == "SET-CHR-001"


async def test_different_artefacts_run_side_by_side_without_interfering(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)

    class ByTask(MockProvider):
        """Answers according to WHICH artefact the request asks for, so concurrent runs cannot swap replies."""

        async def complete(self, model_id, request):
            task = request.messages[0].content
            await asyncio.sleep(0)  # yield, so the two runs genuinely interleave
            if '"Personas"' in task:
                return ok(PERSONA_SECTIONS, items=PERSONA_ITEMS)
            return ok(PROBLEM_SECTIONS)

    runtime.gateway.provider = ByTask()
    a, b = await asyncio.gather(runtime.run(project.id, "personas"), runtime.run(project.id, "problem_statement"))
    assert {a.artefact_id, b.artefact_id} == {"REQ-PER-001", "REQ-PRB-001"}
    assert {x.id for x in store.artefacts.list(project.id, phase_key="requirements")} == {"REQ-PER-001", "REQ-PRB-001"}


async def test_two_simultaneous_runs_of_the_same_artefact_never_create_two_artefacts(rig, store, project):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS, "a"), ok(CHARTER_SECTIONS, "b"))
    results = await asyncio.gather(runtime.run(project.id, "project_charter"), runtime.run(project.id, "project_charter"))
    assert sorted(r.version for r in results) == [1, 2] and len(store.artefacts.list(project.id)) == 1


# ---- the generation record is immutable ------------------------------------------------------------------------------------------

async def test_the_generation_record_cannot_be_edited_after_the_fact(rig, store, project):
    import sqlite3

    runtime, provider, _ = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        with store.db.write() as conn:
            conn.execute("UPDATE artefact_versions SET generation = '{\"cost_usd\": 0}'")


async def test_a_human_written_version_has_no_generation_record(store, project):
    store.artefacts.create(project.id, artefact_type="project_charter", phase_key="setup", title="x", actor="system", artefact_id="SET-CHR-001")
    version = store.artefacts.add_version(project.id, "SET-CHR-001", body="typed by a person", author=PERSON)
    assert version.generation is None


# ---- why a repair happened is kept with the version (S09 follow-up) ---------------------------------------------------------

from app.agents.runtime import MAX_LOGGED_PROBLEM_CHARS, logged_problems  # noqa: E402

NO_ID = {"Personas": "- the persona has no id. Derives from: SET-CHR-001"}


async def test_a_clean_first_attempt_records_no_repair_reasons(rig, store, project):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    result = await runtime.run(project.id, "project_charter")
    gen = store.artefacts.get_version(project.id, result.artefact_id).generation
    assert gen["attempts"] == 1 and gen["repair_reasons"] == []


async def test_a_repaired_attempt_records_which_attempt_which_call_and_what_was_wrong(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=NO_ID), ok(PERSONA_SECTIONS, items=PERSONA_ITEMS))
    result = await runtime.run(project.id, "personas")
    gen = store.artefacts.get_version(project.id, result.artefact_id).generation
    assert (gen["attempts"], gen["repairs"]) == (2, 1)
    [entry] = gen["repair_reasons"]
    assert entry["attempt"] == 1 and entry["call_id"] == result.call_ids[0] and entry["call_id"] != result.call_ids[1]
    assert entry["problems"] == ["a list entry under 'Personas' has no ID ('the persona has no id. Derives from: SET-CHR-001'); "
                                 "start every item with its ID, like '- PER-001 ...'",
                                 "'Personas' has no numbered items; write each one as '- PER-001 ...' with its own ID"]


async def test_the_recorded_reasons_are_exactly_what_the_model_was_told(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=NO_ID), ok(PERSONA_SECTIONS, items=PERSONA_ITEMS))
    result = await runtime.run(project.id, "personas")
    told = provider.calls[-1].request.messages[-1].content              # the repair message sent after attempt 1
    for problem in store.artefacts.get_version(project.id, result.artefact_id).generation["repair_reasons"][0]["problems"]:
        assert problem in told


async def test_every_failed_attempt_gets_its_own_entry_in_order(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    no_block = ProviderResponse("no artefact block at all", Usage(10, 10), "stop")
    provider.queue("m-sonnet", no_block, ok(PERSONA_SECTIONS, items=NO_ID), ok(PERSONA_SECTIONS, items=PERSONA_ITEMS))
    result = await runtime.run(project.id, "personas")
    entries = store.artefacts.get_version(project.id, result.artefact_id).generation["repair_reasons"]
    assert [e["attempt"] for e in entries] == [1, 2] and result.attempts == 3
    assert "no <artefact> block was found" in entries[0]["problems"][0] and "has no numbered items" in " ".join(entries[1]["problems"])
    assert [e["call_id"] for e in entries] == list(result.call_ids[:2])


def test_a_logged_problem_is_bounded_so_the_record_cannot_grow_without_limit():
    entry = logged_problems(2, "call9", ["x" * 5000, "short"])
    assert entry == {"attempt": 2, "call_id": "call9", "problems": ["x" * MAX_LOGGED_PROBLEM_CHARS, "short"]}


async def test_the_recorded_reasons_cannot_be_edited_afterwards(rig, store, project):
    import sqlite3

    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=NO_ID), ok(PERSONA_SECTIONS, items=PERSONA_ITEMS))
    await runtime.run(project.id, "personas")
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        with store.db.write() as conn:
            conn.execute("UPDATE artefact_versions SET generation = '{}' WHERE artefact_id = 'REQ-PER-001'")


async def test_a_run_that_never_produced_a_valid_artefact_saves_nothing_but_the_reasons_are_in_the_error(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", *[ok(PERSONA_SECTIONS, items=NO_ID)] * 3)
    with pytest.raises(OutputInvalid) as caught:
        await runtime.run(project.id, "personas")
    assert caught.value.attempts == 3 and any("has no numbered items" in p for p in caught.value.problems)
    assert store.artefacts.list(project.id, phase_key="requirements") == []


async def test_a_human_edit_has_no_repair_reasons_because_nothing_was_repaired(rig, store, project):
    from app.review.human import HumanActions
    from app.review.service import ReviewService
    from app.review.prompt import load_rubric

    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=PERSONA_ITEMS))
    await runtime.run(project.id, "personas")
    human = HumanActions(store, engine, runtime, ReviewService(runtime.settings, store, runtime.gateway, runtime, engine, load_rubric()))
    body = reply(PERSONA_SECTIONS, items=PERSONA_ITEMS).replace("<artefact>\n", "").replace("\n</artefact>", "")
    human.edit(project.id, "REQ-PER-001", body, actor=PERSON)
    assert "repair_reasons" not in store.artefacts.get_version(project.id, "REQ-PER-001").generation   # a person's record is a different shape
