"""S22b: the runbook and the hypercare plan, written by a scripted model from a seeded design and a seeded Deploy phase. No real model; every reply is a fixed string.

The checks that run on every artefact (sections, order, only real IDs, no secrets, coverage) are the ones tested here, on these two skills. The sign-off is done by hand
and the other three Handover artefacts are switched off: none of them has a skill and a run never tries them."""
from __future__ import annotations

import itertools

import pytest

from app.agents.errors import NoSkill, OutputInvalid
from app.agents.runtime import AgentRuntime
from app.agents.skills import SkillLibrary
from app.llm.gateway import Gateway
from app.llm.providers.mock import MockProvider
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine

from . import _fakes as F
from .test_deploy_skills import DESIGN, MODELS, ok, reply  # noqa: F401  (the same seeded design and scripted-reply helpers)

pytestmark = pytest.mark.anyio
RUN_SECTIONS = ["Overview", "Routine care", "Starting and stopping", "When something goes wrong", "Recovery and rollback", "Contacts and tools", "Coverage check", "Open questions"]
HYP_SECTIONS = ["Overview", "Who is on hand", "What is watched", "Escalation", "Exit criteria", "Coverage check", "Open questions"]
RUN_ITEMS = {"Routine care": "- RUN-001 Check the room list opens each morning, working when rooms appear. Derives from: COMP-001, COMP-002"}
HYP_ITEMS = {"Who is on hand": "- HYP-001 Someone who can fix the product. Proposed: office hours for two weeks. Derives from: NFR-001"}
# the Deploy documents the runbook is written from
DEPLOY_DOCS = {
    "deployment_plan": "## Steps\n- DPL-001 Create the data store. Derives from: COMP-001, COMP-002\n",
    "release_notes": "## What is new\n- REL-001 You can book a room. Derives from: FR-001\n",
}


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
        library = SkillLibrary.load(catalogue)
        runtime = AgentRuntime(cfg, store, gateway, catalogue, engine, library)
        engine.open_project(project.id)
        for key, body in {**DESIGN, **DEPLOY_DOCS}.items():
            skill = library.get(key)
            store.artefacts.create_and_add_version(project.id, artefact_type=key, phase_key=skill.artefact.phase_key, title=skill.artefact.name,
                                                   prefix=skill.artefact.id_prefix, body=body, author="human:seed")
        return runtime, provider, engine, library

    return build


async def open_handover(engine, store, project):
    """Approve every phase before Handover (placeholders for what was not seeded) and start Handover: only Handover is under test."""
    catalogue = engine.catalogue
    for phase in ("setup", "requirements", "design", "architecture", "build", "deploy"):
        engine.start(project.id, phase, actor="system")
        have = {a.type for a in store.artefacts.list(project.id, phase_key=phase)}
        for item in catalogue.phase(phase).artefacts:
            if item.required and item.key not in have:
                art = store.artefacts.create(project.id, artefact_type=item.key, phase_key=phase, title=item.name, actor="system", prefix=item.id_prefix)
                store.artefacts.add_version(project.id, art.id, body="placeholder", author="human:seed")
        engine.finish(project.id, phase, actor="system")
        engine.approve(project.id, phase, actor="human:ann")
    engine.start(project.id, "handover", actor="system")


# ---- the skills as files ----------------------------------------------------------------------------------------------------------------------

def test_the_two_skills_are_for_the_handover_author_in_the_handover_phase_and_number_their_own_items(catalogue):
    library = SkillLibrary.load(catalogue)
    run, hyp = library.get("runbook"), library.get("hypercare_plan")
    assert (run.artefact.role, run.artefact.phase_key, run.artefact.id_prefix) == ("handover_author", "handover", "HND-RUN")
    assert (hyp.artefact.role, hyp.artefact.phase_key, hyp.artefact.id_prefix) == ("handover_author", "handover", "HND-HYP")
    assert [(i.prefix, i.section) for i in run.items] == [("RUN", "Routine care")] and run.covers == ("COMP",)
    assert [(i.prefix, i.section) for i in hyp.items] == [("HYP", "Who is on hand")] and hyp.covers == ("NFR",)


def test_the_runbook_reads_the_architecture_and_the_deploy_documents_and_the_hypercare_plan_also_reads_the_runbook(catalogue):
    library = SkillLibrary.load(catalogue)
    assert library.get("runbook").upstream == ("component_overview", "high_level_design", "low_level_design", "non_functional_requirements", "project_charter", "deployment_plan", "release_notes")
    assert library.get("hypercare_plan").upstream == ("functional_requirements", "non_functional_requirements", "high_level_design", "deployment_plan", "release_notes", "runbook")
    for key in ("runbook", "hypercare_plan"):
        assert "build_instructions" not in library.get(key).upstream          # about 148,000 characters: over the input limit, and support does not need it


def test_the_required_sections_are_the_ones_the_spec_names(catalogue):
    library = SkillLibrary.load(catalogue)
    assert list(library.get("runbook").required_sections) == RUN_SECTIONS and list(library.get("hypercare_plan").required_sections) == HYP_SECTIONS


@pytest.mark.parametrize("key", ["runbook", "hypercare_plan"])
def test_each_skill_keeps_the_safety_lines_every_skill_has(catalogue, key):
    skill = SkillLibrary.load(catalogue).get(key)
    assert "Cite a source that was not provided" in skill.never and "reference material" in skill.never.lower()


def test_the_runbook_says_it_comes_from_the_design_and_never_invents_a_person_a_tool_or_a_secret():
    text = open("app/phases/skills/runbook.md", encoding="utf-8").read()
    for needle in ("NOT seen the code or the running product", "that this runbook comes from the design and the plan, not from the live product", "Write a secret", "Invent a person, a phone number, a team name, a tool, a command or a time", "Claim the product was built, run, tested or monitored",
                   "refer to its steps by their IDs and do not repeat them", "as QUESTIONS", 'marked "Proposed:"'):
        assert needle in text, needle


def test_the_hypercare_plan_marks_every_number_a_proposal_and_names_roles_never_people():
    text = open("app/phases/skills/hypercare_plan.md", encoding="utf-8").read()
    for needle in ("PROPOSAL", "Proposed:", "State a number of weeks, hours or minutes, or a name of a person or team, as agreed", "Name roles, never people", "Exit criteria",
                   "in words a person can check by looking", "Claim the product was built, run, tested or monitored", "Every exit criterion is something a person can check"):
        assert needle in text, needle


# ---- writing them, with a scripted model ------------------------------------------------------------------------------------------------------

async def test_the_runbook_is_written_with_the_handover_model_and_its_entries_linked_to_the_components(rig, store, project):
    runtime, provider, engine, _ = rig()
    await open_handover(engine, store, project)
    provider.queue("m-haiku", ok(RUN_SECTIONS, {**RUN_ITEMS, "Overview": "Written from [COMP-001] and [DPL-001], not from the live product."}))
    result = await runtime.run(project.id, "runbook")
    assert (result.artefact_id, result.version, result.attempts) == ("HND-RUN-001", 1, 1) and result.author == "agent:handover_author@m-haiku"
    prompt = provider.calls[0].request.messages[0].content
    for upstream in ("COMP-001", "NFR-001", "DEP-PLN-001", "DEP-REL-001"):
        assert upstream in prompt
    assert "Booking service" in prompt
    pairs = {(l.from_id, l.to_id) for l in store.links.list(project.id)}
    assert {("RUN-001", "COMP-001"), ("RUN-001", "COMP-002")} <= pairs


async def test_the_hypercare_plan_is_written_after_the_runbook_and_is_shown_it(rig, store, project):
    runtime, provider, engine, _ = rig()
    await open_handover(engine, store, project)
    provider.queue("m-haiku", ok(RUN_SECTIONS, RUN_ITEMS), ok(HYP_SECTIONS, {**HYP_ITEMS, "Overview": "Written from [HND-RUN-001]."}))
    await runtime.run(project.id, "runbook")
    result = await runtime.run(project.id, "hypercare_plan")
    assert result.artefact_id == "HND-HYP-001" and result.attempts == 1
    assert "## [HND-RUN-001]" in provider.calls[1].request.messages[0].content and "NFR-001" in provider.calls[1].request.messages[0].content
    pairs = {(l.from_id, l.to_id) for l in store.links.list(project.id)}
    assert ("HYP-001", "NFR-001") in pairs


async def test_the_hypercare_plan_cannot_be_written_before_the_runbook_exists(rig, store, project):
    from app.agents.errors import MissingInput
    runtime, provider, engine, _ = rig()
    await open_handover(engine, store, project)
    with pytest.raises(MissingInput, match="Runbook"):
        await runtime.run(project.id, "hypercare_plan")
    assert provider.calls == []


# ---- what the checks send back ----------------------------------------------------------------------------------------------------------------

async def test_a_runbook_that_names_a_component_that_does_not_exist_is_sent_back_and_the_repair_is_saved(rig, store, project):
    runtime, provider, engine, _ = rig()
    await open_handover(engine, store, project)
    bad = {"Routine care": "- RUN-001 Check it. Derives from: COMP-001, COMP-002, COMP-009"}
    provider.queue("m-haiku", ok(RUN_SECTIONS, bad), ok(RUN_SECTIONS, RUN_ITEMS))
    result = await runtime.run(project.id, "runbook")
    [repair] = store.artefacts.get_version(project.id, "HND-RUN-001").generation["repair_reasons"]
    assert result.attempts == 2 and any("COMP-009" in p and "not in the material you were given" in p for p in repair["problems"])


async def test_a_runbook_that_leaves_a_component_out_without_saying_why_is_sent_back_naming_it(rig, store, project):
    runtime, provider, engine, _ = rig()
    await open_handover(engine, store, project)
    provider.queue("m-haiku", ok(RUN_SECTIONS, {"Routine care": "- RUN-001 Check it. Derives from: COMP-001"}), ok(RUN_SECTIONS, RUN_ITEMS))
    result = await runtime.run(project.id, "runbook")
    [repair] = store.artefacts.get_version(project.id, "HND-RUN-001").generation["repair_reasons"]
    assert result.attempts == 2 and any("COMP-002" in p for p in repair["problems"])


async def test_a_component_left_out_with_a_reason_in_the_coverage_check_is_accepted(rig, store, project):
    runtime, provider, engine, _ = rig()
    await open_handover(engine, store, project)
    items = {"Routine care": "- RUN-001 Check it. Derives from: COMP-001", "Coverage check": "- COMP-002 The room list is part of the booking service and is checked with it."}
    provider.queue("m-haiku", ok(RUN_SECTIONS, items))
    assert (await runtime.run(project.id, "runbook")).attempts == 1


async def test_a_hypercare_plan_that_leaves_a_requirement_out_is_sent_back_and_a_missing_section_is_named(rig, store, project):
    runtime, provider, engine, _ = rig()
    await open_handover(engine, store, project)
    provider.queue("m-haiku", ok(RUN_SECTIONS, RUN_ITEMS))
    await runtime.run(project.id, "runbook")
    provider.queue("m-haiku", ok([s for s in HYP_SECTIONS if s != "Exit criteria"], {"Who is on hand": "- HYP-001 Someone. Derives from: SET-CHR-001"}), ok(HYP_SECTIONS, HYP_ITEMS))
    result = await runtime.run(project.id, "hypercare_plan")
    [repair] = store.artefacts.get_version(project.id, "HND-HYP-001").generation["repair_reasons"]
    assert result.attempts == 2 and "Exit criteria" in " ".join(repair["problems"])


async def test_a_secret_in_a_runbook_is_refused_and_never_saved(rig, store, project):
    runtime, provider, engine, _ = rig()
    await open_handover(engine, store, project)
    leaky = {"Contacts and tools": f"The key is {F.AWS_KEY}", **RUN_ITEMS}
    provider.queue("m-haiku", ok(RUN_SECTIONS, leaky), ok(RUN_SECTIONS, leaky), ok(RUN_SECTIONS, leaky))
    with pytest.raises(OutputInvalid):
        await runtime.run(project.id, "runbook")
    assert store.artefacts.list(project.id, phase_key="handover", artefact_type="runbook") == []


async def test_a_person_can_edit_the_runbook_and_the_edit_goes_through_the_same_checks(rig, store, project):
    from app.review.errors import EditRefused
    from app.review.human import HumanActions
    from app.review.prompt import load_rubric
    from app.review.service import ReviewService
    runtime, provider, engine, _ = rig()
    await open_handover(engine, store, project)
    provider.queue("m-haiku", ok(RUN_SECTIONS, RUN_ITEMS))
    await runtime.run(project.id, "runbook")
    human = HumanActions(store, engine, runtime, ReviewService(runtime.settings, store, runtime.gateway, runtime, engine, load_rubric()))
    good = store.artefacts.get_version(project.id, "HND-RUN-001").body + "\n"
    assert human.edit(project.id, "HND-RUN-001", good.replace("Text for Recovery and rollback.", "Text for Recovery and rollback, edited."), actor="human:ann") == 2
    with pytest.raises(EditRefused):
        human.edit(project.id, "HND-RUN-001", good.replace("## Recovery and rollback", "## Going back"), actor="human:ann")


# ---- the sign-off is done by hand, and three artefacts are switched off: none has a skill, none is ever run -----------------------------------------------

async def test_a_run_of_handover_has_two_artefacts_to_write_and_each_has_a_skill(rig, store, project):
    runtime, provider, engine, library = rig()
    await open_handover(engine, store, project)
    plan = engine.plan_for(store.projects.get(project.id)).phase("handover")
    assert [a.key for a in plan.artefacts] == ["runbook", "hypercare_plan"] and [a.key for a in plan.by_hand] == ["handover_signoff"]
    assert [a.key for a in plan.not_enabled] == ["support_guide", "slos_alerts", "kt_pack"]
    assert [a.key for a in plan.artefacts if library.get(a.key) is None] == []                # none of the artefacts a run will try can fail with "there is no skill"


async def test_the_signoff_and_the_three_parked_artefacts_are_asked_of_no_model_and_asking_is_refused_plainly(rig, store, project):
    runtime, provider, engine, _ = rig()
    await open_handover(engine, store, project)
    for key in ("handover_signoff", "support_guide", "slos_alerts", "kt_pack"):
        with pytest.raises(NoSkill, match=f"no skill for '{key}'"):
            await runtime.run(project.id, key)
    assert provider.calls == []
