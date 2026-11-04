"""S21b: the deployment plan and the release notes, written by a scripted model from a seeded design. No real model; every reply is a fixed string.

The checks that run on every artefact (sections, order, only real IDs, no secrets, coverage) are the ones tested here, on these two skills."""
from __future__ import annotations

import itertools

import pytest

from app.agents.errors import OutputInvalid
from app.agents.runtime import AgentRuntime
from app.agents.skills import SkillLibrary
from app.llm.gateway import Gateway
from app.llm.providers.mock import MockProvider
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine

from . import _fakes as F

pytestmark = pytest.mark.anyio
MODELS = dict(
    ibm_ica_model_id="m-sonnet", ibm_ica_fallback_model_id="m-sonnet", ibm_ica_haiku_model_id="m-haiku",
    ibm_ica_openai_model_id="m-openai", ibm_ica_gemini_model_id="m-gemini",
    ibm_ica_price_input_per_mtok="2", ibm_ica_price_output_per_mtok="10",
)
PLAN_SECTIONS = ["Overview", "Environments", "Steps", "Configuration and secrets", "Data and migrations", "Rollback", "Coverage check", "Open questions"]
NOTES_SECTIONS = ["Overview", "What is new", "Known limits", "Upgrade notes", "Coverage check", "Open questions"]

DESIGN = {
    "project_charter": "## Purpose\nBook meeting rooms.\n",
    "functional_requirements": "## Requirements\n- FR-001 Staff can book a room for a time. Derives from: PER-001\n- FR-002 Staff can cancel a booking. Derives from: PER-001\n",
    "non_functional_requirements": "## Requirements\n- NFR-001 Pages load within two seconds. Derives from: SET-CHR-001\n",
    "epics_features": "## Epics\n- EPIC-001 Booking. Derives from: FR-001\n## Features\n- FEAT-001 Book a room. Derives from: EPIC-001, FR-001\n",
    "user_journey": "## Journey\n- JS-001 Staff book a room. Derives from: PER-001\n",
    "hifi_wireframes": "## Screens\n- HFS-001 Browse rooms: the page. Derives from: FR-001\n",
    "component_overview": "## Components\n- COMP-001 Booking service. Derives from: FR-001, NFR-001\n- COMP-002 Room list. Derives from: FR-002\n",
    "high_level_design": "## Decisions\n- DEC-001 Use one service. Derives from: COMP-001\n## Interfaces\n- IFC-001 Service and list. Derives from: COMP-001, COMP-002\n",
    "low_level_design": "## Endpoints\n- API-001 GET /api/rooms lists rooms. Derives from: FR-001\n## Tables\n- TBL-001 rooms: id, name. Derives from: FR-001\n## Rules\n- RUL-001 No overlap. Derives from: FR-001\n",
}


def reply(sections, items=None, extra=""):
    items = items or {}
    body = "\n".join(f"## {n}\n{items[n] if n in items else f'Text for {n}. {extra}'}" for n in sections)
    return f"<artefact>\n{body}\n</artefact>"


def ok(sections, items=None, extra="", tokens=(1000, 200)):
    return ProviderResponse(reply(sections, items, extra), Usage(*tokens), "stop")


PLAN_ITEMS = {"Steps": "- DPL-001 Create the data store before anything else, done by the release owner, working when the tables exist. Derives from: COMP-001, COMP-002"}
NOTES_ITEMS = {"What is new": "- REL-001 You can book a room for a time that suits you. Derives from: FR-001\n- REL-002 You can cancel a booking you made. Derives from: FR-002"}


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
        for key, body in DESIGN.items():
            skill = library.get(key)
            store.artefacts.create_and_add_version(project.id, artefact_type=key, phase_key=skill.artefact.phase_key, title=skill.artefact.name,
                                                   prefix=skill.artefact.id_prefix, body=body, author="human:seed")
        return runtime, provider, engine, library

    return build


async def open_deploy(engine, store, project):
    """Approve every phase before Deploy and start Deploy. The design artefacts are already saved (seeded), so each earlier phase has what it needs to be approved
    except Setup..Build's other required artefacts, which are given a placeholder version here: only Deploy is under test."""
    catalogue = engine.catalogue
    for phase in ("setup", "requirements", "design", "architecture", "build"):
        engine.start(project.id, phase, actor="system")
        have = {a.type for a in store.artefacts.list(project.id, phase_key=phase)}
        for item in catalogue.phase(phase).artefacts:
            if item.required and item.key not in have:
                art = store.artefacts.create(project.id, artefact_type=item.key, phase_key=phase, title=item.name, actor="system", prefix=item.id_prefix)
                store.artefacts.add_version(project.id, art.id, body="placeholder", author="human:seed")
        engine.finish(project.id, phase, actor="system")
        engine.approve(project.id, phase, actor="human:ann")
    engine.start(project.id, "deploy", actor="system")


# ---- the skills as files ---------------------------------------------------------------------------------------------------------------------

def test_the_two_skills_are_for_the_devops_role_in_the_deploy_phase_and_number_their_own_items(catalogue):
    library = SkillLibrary.load(catalogue)
    plan, notes = library.get("deployment_plan"), library.get("release_notes")
    assert (plan.artefact.role, plan.artefact.phase_key, plan.artefact.id_prefix) == ("devops_engineer", "deploy", "DEP-PLN")
    assert (notes.artefact.role, notes.artefact.phase_key, notes.artefact.id_prefix) == ("devops_engineer", "deploy", "DEP-REL")
    assert [(i.prefix, i.section) for i in plan.items] == [("DPL", "Steps")] and plan.covers == ("COMP",)
    assert [(i.prefix, i.section) for i in notes.items] == [("REL", "What is new")] and notes.covers == ("FR",)


def test_the_plan_reads_the_design_and_never_the_huge_instruction_set_and_the_notes_read_the_plan(catalogue):
    library = SkillLibrary.load(catalogue)
    assert library.get("deployment_plan").upstream == ("component_overview", "high_level_design", "low_level_design", "non_functional_requirements", "project_charter")
    assert "build_instructions" not in library.get("deployment_plan").upstream and "deployment_plan" in library.get("release_notes").upstream
    assert not {"build_instructions"} & set(library.get("release_notes").upstream)


def test_the_required_sections_are_the_ones_the_spec_names(catalogue):
    library = SkillLibrary.load(catalogue)
    assert list(library.get("deployment_plan").required_sections) == PLAN_SECTIONS
    assert list(library.get("release_notes").required_sections) == NOTES_SECTIONS


@pytest.mark.parametrize("key", ["deployment_plan", "release_notes"])
def test_each_skill_keeps_the_safety_lines_every_skill_has(catalogue, key):
    skill = SkillLibrary.load(catalogue).get(key)
    assert "Cite a source that was not provided" in skill.never and "reference material" in skill.never.lower()


def test_the_plan_says_it_comes_from_the_design_and_forbids_a_secret_an_invented_product_and_a_claim_it_was_built():
    text = open("app/phases/skills/deployment_plan.md", encoding="utf-8").read()
    for needle in ("NOT seen the code", "this plan comes from the design and not from the code", "Never write a secret value", "Write a secret", "Name a hosting product", "Claim the product was built, tested or run", "Do not claim the product has been tested"):
        assert needle in text, needle


def test_the_notes_say_they_describe_a_promise_not_a_shipped_thing_and_forbid_inventing_a_version_or_a_date():
    text = open("app/phases/skills/release_notes.md", encoding="utf-8").read()
    for needle in ("NOT seen the code", "never what was shipped", "Invent a version number, a date or a customer", "Describe something the design does not promise", "Known limits are stated plainly"):
        assert needle in text, needle


# ---- writing them, with a scripted model --------------------------------------------------------------------------------------------------------

async def test_the_plan_is_written_from_the_design_and_saved_as_version_one_with_its_steps_linked_to_the_components(rig, store, project):
    runtime, provider, engine, _ = rig()
    await open_deploy(engine, store, project)
    provider.queue("m-openai", ok(PLAN_SECTIONS, {**PLAN_ITEMS, "Overview": "Written from [COMP-001] and [NFR-001], not from the code."}))
    result = await runtime.run(project.id, "deployment_plan")
    assert (result.artefact_id, result.version, result.attempts) == ("DEP-PLN-001", 1, 1) and result.citations == ("COMP-001", "NFR-001") and result.author == "agent:devops_engineer@m-openai"
    prompt = provider.calls[0].request.messages[0].content
    for upstream in ("COMP-001", "IFC-001", "API-001", "NFR-001"):
        assert upstream in prompt
    assert "Booking service" in prompt
    version = store.artefacts.get_version(project.id, "DEP-PLN-001")
    assert "## Rollback" in version.body and "DPL-001" in version.body
    pairs = {(l.from_id, l.to_id) for l in store.links.list(project.id)}
    assert {("DPL-001", "COMP-001"), ("DPL-001", "COMP-002")} <= pairs


async def test_the_notes_are_written_after_the_plan_and_are_shown_it(rig, store, project):
    runtime, provider, engine, _ = rig()
    await open_deploy(engine, store, project)
    provider.queue("m-openai", ok(PLAN_SECTIONS, PLAN_ITEMS), ok(NOTES_SECTIONS, {**NOTES_ITEMS, "Overview": "Written from [DEP-PLN-001]."}))
    await runtime.run(project.id, "deployment_plan")
    result = await runtime.run(project.id, "release_notes")
    assert result.artefact_id == "DEP-REL-001" and result.attempts == 1
    assert "## [DEP-PLN-001]" in provider.calls[1].request.messages[0].content and "FR-002" in provider.calls[1].request.messages[0].content
    pairs = {(l.from_id, l.to_id) for l in store.links.list(project.id)}
    assert {("REL-001", "FR-001"), ("REL-002", "FR-002")} <= pairs


async def test_notes_cannot_be_written_before_the_plan_exists(rig, store, project):
    from app.agents.errors import MissingInput
    runtime, provider, engine, _ = rig()
    await open_deploy(engine, store, project)
    with pytest.raises(MissingInput, match="Deployment plan"):
        await runtime.run(project.id, "release_notes")
    assert provider.calls == []


# ---- what the checks send back --------------------------------------------------------------------------------------------------------------

async def test_a_plan_that_names_a_component_that_does_not_exist_is_sent_back_and_the_repair_is_saved(rig, store, project):
    runtime, provider, engine, _ = rig()
    await open_deploy(engine, store, project)
    bad = {"Steps": "- DPL-001 Start it. Derives from: COMP-001, COMP-002, COMP-009"}
    provider.queue("m-openai", ok(PLAN_SECTIONS, bad), ok(PLAN_SECTIONS, PLAN_ITEMS))
    result = await runtime.run(project.id, "deployment_plan")
    assert result.attempts == 2
    [repair] = store.artefacts.get_version(project.id, "DEP-PLN-001").generation["repair_reasons"]
    assert any("COMP-009" in p and "not in the material you were given" in p for p in repair["problems"])


async def test_a_plan_that_leaves_a_component_out_without_saying_why_is_sent_back_naming_it(rig, store, project):
    runtime, provider, engine, _ = rig()
    await open_deploy(engine, store, project)
    partial = {"Steps": "- DPL-001 Start it. Derives from: COMP-001"}
    provider.queue("m-openai", ok(PLAN_SECTIONS, partial), ok(PLAN_SECTIONS, PLAN_ITEMS))
    result = await runtime.run(project.id, "deployment_plan")
    [repair] = store.artefacts.get_version(project.id, "DEP-PLN-001").generation["repair_reasons"]
    assert result.attempts == 2 and any("COMP-002" in p for p in repair["problems"])


async def test_a_component_left_out_with_a_reason_in_the_coverage_check_is_accepted(rig, store, project):
    runtime, provider, engine, _ = rig()
    await open_deploy(engine, store, project)
    items = {"Steps": "- DPL-001 Start it. Derives from: COMP-001", "Coverage check": "- COMP-002 The room list is part of the booking service and is started with it."}
    provider.queue("m-openai", ok(PLAN_SECTIONS, items))
    assert (await runtime.run(project.id, "deployment_plan")).attempts == 1


async def test_notes_that_leave_a_requirement_out_are_sent_back_and_a_missing_section_is_named(rig, store, project):
    runtime, provider, engine, _ = rig()
    await open_deploy(engine, store, project)
    provider.queue("m-openai", ok(PLAN_SECTIONS, PLAN_ITEMS))
    await runtime.run(project.id, "deployment_plan")
    partial = {"What is new": "- REL-001 You can book a room. Derives from: FR-001"}
    provider.queue("m-openai", ok([s for s in NOTES_SECTIONS if s != "Known limits"], partial), ok(NOTES_SECTIONS, NOTES_ITEMS))
    result = await runtime.run(project.id, "release_notes")
    [repair] = store.artefacts.get_version(project.id, "DEP-REL-001").generation["repair_reasons"]
    joined = " ".join(repair["problems"])
    assert result.attempts == 2 and "Known limits" in joined and "FR-002" in joined


async def test_a_secret_in_a_plan_is_refused_and_never_saved(rig, store, project):
    runtime, provider, engine, _ = rig()
    await open_deploy(engine, store, project)
    leaky = {"Configuration and secrets": f"The key is {F.AWS_KEY}", **PLAN_ITEMS}
    provider.queue("m-openai", ok(PLAN_SECTIONS, leaky), ok(PLAN_SECTIONS, leaky), ok(PLAN_SECTIONS, leaky))
    with pytest.raises(OutputInvalid):
        await runtime.run(project.id, "deployment_plan")
    assert store.artefacts.list(project.id, phase_key="deploy", artefact_type="deployment_plan") == []


async def test_the_switched_off_artefacts_cannot_be_written(rig, store, project):
    from app.agents.errors import NoSkill
    runtime, provider, engine, _ = rig()
    await open_deploy(engine, store, project)
    for key in ("infrastructure_as_code", "cicd_pipeline", "deployment_verification"):
        with pytest.raises(NoSkill):
            await runtime.run(project.id, key)
    assert provider.calls == []


async def test_a_person_can_edit_the_plan_and_the_edit_goes_through_the_same_checks(rig, store, project):
    from app.review.errors import EditRefused
    from app.review.human import HumanActions
    from app.review.prompt import load_rubric
    from app.review.service import ReviewService
    runtime, provider, engine, _ = rig()
    await open_deploy(engine, store, project)
    provider.queue("m-openai", ok(PLAN_SECTIONS, PLAN_ITEMS))
    await runtime.run(project.id, "deployment_plan")
    human = HumanActions(store, engine, runtime, ReviewService(runtime.settings, store, runtime.gateway, runtime, engine, load_rubric()))
    good = store.artefacts.get_version(project.id, "DEP-PLN-001").body + "\n"
    assert human.edit(project.id, "DEP-PLN-001", good.replace("Text for Rollback.", "Text for Rollback, edited."), actor="human:ann") == 2
    with pytest.raises(EditRefused):
        human.edit(project.id, "DEP-PLN-001", good.replace("## Rollback", "## Going back"), actor="human:ann")


# ---- the deployment verification is done by hand: no skill, no model, never run -----------------------------------------------------------------

async def test_the_plan_has_no_verification_to_write_so_a_run_has_nothing_that_could_fail_for_want_of_a_skill(rig, store, project):
    runtime, provider, engine, library = rig()
    await open_deploy(engine, store, project)
    plan = engine.plan_for(store.projects.get(project.id)).phase("deploy")
    assert [a.key for a in plan.artefacts] == ["deployment_plan", "release_notes"] and library.get("deployment_verification") is None
    assert [a.key for a in plan.by_hand] == ["deployment_verification"]
    missing = [a.key for a in plan.artefacts if library.get(a.key) is None]
    assert missing == []                                               # every artefact a run will try has a skill, so none can fail with "there is no skill"


async def test_the_verification_is_asked_of_no_model_and_asking_for_it_is_refused_plainly(rig, store, project):
    from app.agents.errors import NoSkill
    runtime, provider, engine, _ = rig()
    await open_deploy(engine, store, project)
    with pytest.raises(NoSkill, match="no skill for 'deployment_verification'"):
        await runtime.run(project.id, "deployment_verification")
    assert provider.calls == []
