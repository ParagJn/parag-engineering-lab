"""The Requirements phase end to end: item checks inside the repair loop, regeneration, links, the chain, replay."""
from __future__ import annotations

import sqlite3

import pytest

from app.agents.errors import OutputInvalid
from app.agents.items import parse_items
from app.llm.providers.mock import MockProvider
from app.llm.providers.recording import RecordingProvider, ReplayProvider
from app.llm.recordings import RecordingStore
from app.llm.types import ProviderResponse, Usage
from app.repos import Store
from app.workflow.definitions import load_catalogue
from app.llm.routing import Routing

from .test_agent_misc import runtime_over
from .test_agent_runtime import (  # noqa: F401  (rig is a fixture the tests below use)
    CHARTER_SECTIONS,
    FR_ITEMS,
    FR_SECTIONS,
    MODELS,
    PERSON,
    PERSONA_ITEMS,
    PERSONA_SECTIONS,
    PROBLEM_SECTIONS,
    catalogue,
    chain_to_requirements,
    ok,
    reply,
    rig,
    sent,
)

pytestmark = pytest.mark.anyio

VISION_SECTIONS = ["Vision", "Objectives", "Measures", "Out of vision", "Open questions"]
NFR_SECTIONS = ["Overview", "Requirements", "Quality targets", "Open questions"]
EPIC_SECTIONS = ["Overview", "Epics", "Features", "Coverage check"]
STORY_SECTIONS = ["Overview", "Stories", "Coverage check", "Open questions"]
VISION_ITEMS = {"Objectives": "- OBJ-001 No double bookings. Derives from: REQ-PRB-001"}
NFR_ITEMS = {"Requirements": "- NFR-001 Usable in office hours. Derives from: SET-CHR-001"}


def epics(features: str, coverage: str = "None.") -> ProviderResponse:
    items = {"Epics": "- EPIC-001 Book rooms. Derives from: PER-001", "Features": features, "Coverage check": coverage}
    return ok(EPIC_SECTIONS, items=items)


FEATURE_OK = "- FEAT-001 Reserve a room. Derives from: EPIC-001, FR-001, NFR-001"


async def to_epics(runtime, provider, store, project, engine):
    """Everything the epics skill reads, written by the scripted model: personas, problem, FR, NFR."""
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue(
        "m-sonnet",
        ok(PERSONA_SECTIONS, items={"Personas": "- PER-001 Staff. Derives from: SET-CHR-001"}),
        ok(PROBLEM_SECTIONS),
        ok(FR_SECTIONS, items={"Requirements": "- FR-001 The system shall refuse a double booking, for PER-001. Derives from: PER-001, REQ-PRB-001"}),
        ok(NFR_SECTIONS, items=NFR_ITEMS),
    )
    for key in ("personas", "problem_statement", "functional_requirements", "non_functional_requirements"):
        await runtime.run(project.id, key)


# ---- item checks sit inside the repair loop ------------------------------------------------------------------------

async def test_a_reply_with_a_wrong_prefix_is_sent_back_with_the_reason_and_the_fix_is_what_gets_saved(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    bad = ok(PERSONA_SECTIONS, items={"Personas": "- FR-001 Staff. Derives from: SET-CHR-001"})
    provider.queue("m-sonnet", bad, ok(PERSONA_SECTIONS, items=PERSONA_ITEMS))
    result = await runtime.run(project.id, "personas")
    assert result.attempts == 2 and result.items == ("PER-001",)
    repair = provider.calls[2].request.messages[-1].content
    assert "FR-001 is under 'Personas', where items must start with PER-" in repair
    assert "FR-001" not in store.artefacts.get_version(project.id, result.artefact_id).body


async def test_three_bad_replies_fail_with_every_reason_and_save_nothing(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", *[ok(PERSONA_SECTIONS, items={"Personas": "- The persona has no id."})] * 3)
    with pytest.raises(OutputInvalid, match="'Personas' has no numbered items") as caught:
        await runtime.run(project.id, "personas")
    assert caught.value.attempts == 3 and store.artefacts.list(project.id, phase_key="requirements") == []
    assert store.links.list(project.id) == []


async def test_a_derives_from_an_id_that_was_not_shown_is_refused_like_an_invented_citation(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue(
        "m-sonnet",
        ok(PERSONA_SECTIONS, items={"Personas": "- PER-001 Staff. Derives from: SET-CHR-001, PER-099"}),
        ok(PERSONA_SECTIONS, items=PERSONA_ITEMS),
    )
    result = await runtime.run(project.id, "personas")
    assert result.attempts == 2
    assert "PER-001 derives from PER-099, which is not in the material you were given" in provider.calls[2].request.messages[-1].content
    assert [(l.from_id, l.to_id) for l in store.links.list(project.id)] == [("PER-001", "SET-CHR-001")]


async def test_the_prompt_tells_the_model_the_item_rules_and_where_numbering_starts(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=PERSONA_ITEMS))
    await runtime.run(project.id, "personas")
    prompt = provider.calls[1].request
    assert "Numbered items:" in prompt.system and "PER item" in prompt.system and "Derives from:" in prompt.system
    assert "# Numbering\n- PER: start at PER-001" in prompt.messages[0].content


async def test_an_artefact_with_no_items_gets_no_item_rules_and_no_item_checks(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PROBLEM_SECTIONS))
    result = await runtime.run(project.id, "problem_statement")
    assert result.items == () and result.links == 0
    assert "Numbered items:" not in provider.calls[1].request.system and "# Numbering" not in sent(provider, 1)


# ---- items become citable sources for the artefacts built on them ---------------------------------------------------

async def test_upstream_item_ids_are_listed_as_sources_the_next_artefact_may_cite(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=PERSONA_ITEMS), ok(PROBLEM_SECTIONS), ok(FR_SECTIONS, items=FR_ITEMS))
    for key in ("personas", "problem_statement", "functional_requirements"):
        await runtime.run(project.id, key)
    listing = sent(provider, 3).split("# Sources you may cite")[1]
    assert "- PER-001" in listing and "- REQ-PER-001" in listing and "- SET-CHR-001" in listing


async def test_an_item_id_that_only_a_different_artefact_holds_is_not_available(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    # personas does not read problem_statement, so nothing from it (and no FR) is shown to the personas skill
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items={"Personas": "- PER-001 Staff. Derives from: FR-001"}), ok(PERSONA_SECTIONS, items=PERSONA_ITEMS))
    result = await runtime.run(project.id, "personas")
    assert result.attempts == 2 and "FR-001, which is not in the material" in provider.calls[2].request.messages[-1].content


# ---- regeneration --------------------------------------------------------------------------------------------------------

async def two_personas_then(runtime, provider, store, project, engine, second):
    await chain_to_requirements(runtime, provider, store, project, engine)
    first = ok(PERSONA_SECTIONS, items={"Personas": "- PER-001 Staff. Derives from: SET-CHR-001\n- PER-002 Admin. Derives from: SET-CHR-001"})
    provider.queue("m-sonnet", first, second)
    await runtime.run(project.id, "personas")


async def test_a_regeneration_is_shown_the_previous_ids_and_told_where_new_numbers_start(rig, store, project):
    runtime, provider, engine = rig()
    second = ok(PERSONA_SECTIONS, items={"Personas": "- PER-001 Staff. Derives from: SET-CHR-001\n- PER-002 Admin. Derives from: SET-CHR-001"})
    await two_personas_then(runtime, provider, store, project, engine, second)
    result = await runtime.run(project.id, "personas")
    prompt = sent(provider, 2)
    assert result.version == 2 and result.attempts == 1
    assert "# Items in the previous version" in prompt and "- PER-001 Staff." in prompt and "- PER-002 Admin." in prompt
    assert "# Numbering\n- PER: start at PER-003" in prompt


async def test_a_regeneration_that_drops_an_id_silently_is_repaired(rig, store, project):
    runtime, provider, engine = rig()
    dropped = ok(PERSONA_SECTIONS, items={"Personas": "- PER-001 Staff. Derives from: SET-CHR-001"})
    kept = ok(PERSONA_SECTIONS, items={"Personas": "- PER-001 Staff. Derives from: SET-CHR-001"}, extra="x")
    withdrawn = reply(PERSONA_SECTIONS, items={"Personas": "- PER-001 Staff. Derives from: SET-CHR-001"}).replace(
        "</artefact>", "## Withdrawn items\n- PER-002 merged into PER-001\n</artefact>")
    await two_personas_then(runtime, provider, store, project, engine, dropped)
    provider.queue("m-sonnet", ProviderResponse(withdrawn, Usage(1, 1), "stop"))
    result = await runtime.run(project.id, "personas")  # consumes `dropped`, is refused, then `withdrawn` is accepted
    assert result.attempts == 2 and result.version == 2
    assert "PER-002 was in the previous version and is now missing" in provider.calls[3].request.messages[-1].content
    assert "## Withdrawn items" in store.artefacts.get_version(project.id, result.artefact_id).body


async def test_ids_are_stable_across_versions_so_a_link_made_to_version_one_still_points_at_a_live_item(rig, store, project):
    runtime, provider, engine = rig()
    same = ok(PERSONA_SECTIONS, items={"Personas": "- PER-001 Staff, reworded. Derives from: SET-CHR-001\n- PER-002 Admin. Derives from: SET-CHR-001"})
    await two_personas_then(runtime, provider, store, project, engine, same)
    await runtime.run(project.id, "personas")
    v1 = parse_items(store.artefacts.get_version(project.id, "REQ-PER-001", 1).body, runtime.skills.get("personas").items).ids
    v2 = parse_items(store.artefacts.get_version(project.id, "REQ-PER-001", 2).body, runtime.skills.get("personas").items).ids
    assert v1 == v2 == ("PER-001", "PER-002")


# ---- links ---------------------------------------------------------------------------------------------------------------------

async def test_derives_from_references_are_saved_as_derives_links_declared_in_the_artefact(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items={"Personas": "- PER-001 A. Derives from: SET-CHR-001\n- PER-002 B. Derives from: SET-CHR-001"}))
    result = await runtime.run(project.id, "personas")
    links = store.links.list(project.id, kind="derives")
    assert [(l.from_id, l.to_id, l.declared_in) for l in links] == [
        ("PER-001", "SET-CHR-001", "REQ-PER-001"), ("PER-002", "SET-CHR-001", "REQ-PER-001")]
    assert result.links == 2


async def test_regenerating_does_not_duplicate_links(rig, store, project):
    runtime, provider, engine = rig()
    same = ok(PERSONA_SECTIONS, items=PERSONA_ITEMS)
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", same, same)
    await runtime.run(project.id, "personas")
    await runtime.run(project.id, "personas")
    assert len(store.links.list(project.id)) == 1


async def test_a_failed_save_leaves_no_artefact_no_version_and_no_links(rig, store, project, monkeypatch):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items={"Personas": "- PER-001 A. Derives from: SET-CHR-001\n- PER-002 B. Derives from: SET-CHR-001"}))
    import app.repos as repos

    real = repos._insert_link
    calls = []

    def second_link_fails(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise sqlite3.OperationalError("disk full")
        return real(*args, **kwargs)

    monkeypatch.setattr(repos, "_insert_link", second_link_fails)
    with pytest.raises(sqlite3.OperationalError):
        await runtime.run(project.id, "personas")
    assert len(calls) == 2  # precondition: the first link WAS written before the second failed
    assert store.artefacts.list(project.id, phase_key="requirements") == []
    assert store.links.list(project.id) == []


async def test_a_unbracketed_document_source_is_a_source_but_never_a_link(rig, store, project):
    runtime, provider, engine = rig()
    store.context.add_document(project.id, "p.md", b"# Rules\n\nStaff may book a room for up to four hours at a time.", actor=PERSON)
    store.projects.update(project.id, actor="system", brief="Staff may book a room for up to four hours at a time.")
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items={"Personas": "- PER-001 A. Derives from: SET-CHR-001, DOC-001#1"}))
    await runtime.run(project.id, "personas")
    assert [l.to_id for l in store.links.list(project.id)] == ["SET-CHR-001"]


def test_the_links_the_store_accepts_have_the_same_shape_as_every_item_id(store, project):
    """The scheme depends on item IDs passing the existing link check unchanged."""
    for item_id in ("PER-001", "FR-012", "NFR-003", "EPIC-001", "FEAT-007", "US-021", "OBJ-001"):
        store.links.add(project.id, item_id, "SET-CHR-001", "derives", actor="system")
    assert len(store.links.list(project.id)) == 7


def test_no_item_prefix_equals_or_begins_an_artefact_prefix(catalogue):
    from app.agents.skills import SkillLibrary

    library = SkillLibrary.load(catalogue)
    artefact_prefixes = {a.id_prefix for p in catalogue.phases for a in p.artefacts}
    first_segments = {p.split("-")[0] for p in artefact_prefixes}
    prefixes = [spec.prefix for key in library.keys for spec in library.get(key).items]
    assert prefixes and len(prefixes) == len(set(prefixes))
    assert not set(prefixes) & (artefact_prefixes | first_segments | {"DOC", "MEM"})


# ---- coverage --------------------------------------------------------------------------------------------------------------------

async def test_epics_that_leave_a_requirement_uncovered_are_sent_back_naming_it(rig, store, project):
    runtime, provider, engine = rig()
    await to_epics(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", epics("- FEAT-001 Reserve. Derives from: EPIC-001, FR-001"), epics(FEATURE_OK))
    result = await runtime.run(project.id, "epics_features")
    assert result.attempts == 2
    message = provider.calls[-1].request.messages[-1].content
    assert "NFR-001 is not named in any item's 'Derives from:'" in message


async def test_epics_that_list_the_gap_in_the_coverage_check_are_accepted_first_time(rig, store, project):
    runtime, provider, engine = rig()
    await to_epics(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", epics("- FEAT-001 Reserve. Derives from: EPIC-001, FR-001", "- NFR-001 deferred to a later release"))
    assert (await runtime.run(project.id, "epics_features")).attempts == 1


async def test_the_epics_prompt_lists_the_requirements_it_must_cover(rig, store, project):
    runtime, provider, engine = rig()
    await to_epics(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", epics(FEATURE_OK))
    await runtime.run(project.id, "epics_features")
    sources = sent(provider, len(provider.calls) - 1).split("# Sources you may cite")[1]
    assert "- FR-001" in sources and "- NFR-001" in sources and "- PER-001" in sources
    assert "Every FR and NFR item you were given must appear" in provider.calls[-1].request.system


# ---- the whole phase, in order ---------------------------------------------------------------------------------------------------

async def test_the_seven_requirements_artefacts_run_in_catalogue_order_and_get_their_prefixes(rig, store, project):
    runtime, provider, engine = rig()
    await to_epics(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(VISION_SECTIONS, items=VISION_ITEMS), epics(FEATURE_OK))
    provider.queue("m-haiku", ok(STORY_SECTIONS, items={
        "Stories": "- US-001 As staff, I want a room. Derives from: FEAT-001, PER-001\n  - A taken room is refused.", "Coverage check": "None."}))
    ids = []
    for key in ("vision_objectives", "epics_features", "user_stories"):
        ids.append((await runtime.run(project.id, key)).artefact_id)
    assert ids == ["REQ-VIS-001", "REQ-EPC-001", "REQ-US-001"]
    assert {a.id for a in store.artefacts.list(project.id, phase_key="requirements")} == {
        "REQ-PER-001", "REQ-PRB-001", "REQ-F-001", "REQ-NF-001", "REQ-VIS-001", "REQ-EPC-001", "REQ-US-001"}


async def test_user_stories_are_written_by_the_haiku_slot_through_the_backlog_splitter_role(rig, store, project):
    runtime, provider, engine = rig()
    await to_epics(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", epics(FEATURE_OK))
    await runtime.run(project.id, "epics_features")
    provider.queue("m-haiku", ok(STORY_SECTIONS, items={
        "Stories": "- US-001 As staff, I want a room. Derives from: FEAT-001, PER-001", "Coverage check": "None."}))
    result = await runtime.run(project.id, "user_stories")
    assert result.author == "agent:backlog_splitter@m-haiku" and provider.models[-1] == "m-haiku"


async def test_a_story_with_nested_acceptance_criteria_is_one_item_and_a_feature_without_a_story_is_refused(rig, store, project):
    runtime, provider, engine = rig()
    await to_epics(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", epics("- FEAT-001 Reserve. Derives from: EPIC-001, FR-001, NFR-001\n- FEAT-002 Cancel. Derives from: EPIC-001, FR-001"))
    await runtime.run(project.id, "epics_features")
    story = "- US-001 As staff, I want a room. Derives from: FEAT-001, PER-001\n  - A taken room is refused.\n  - Outside hours is refused."
    provider.queue("m-haiku",
                   ok(STORY_SECTIONS, items={"Stories": story, "Coverage check": "None."}),
                   ok(STORY_SECTIONS, items={"Stories": story + "\n- US-002 As staff, I want to cancel. Derives from: FEAT-002, PER-001", "Coverage check": "None."}))
    result = await runtime.run(project.id, "user_stories")
    assert result.attempts == 2 and result.items == ("US-001", "US-002")
    assert "FEAT-002 is not named in any item's 'Derives from:'" in provider.calls[-1].request.messages[-1].content


async def test_each_artefact_sees_only_its_declared_upstream(rig, store, project):
    runtime, provider, engine = rig()
    await to_epics(runtime, provider, store, project, engine)
    vision_prompt_index = len(provider.calls)
    provider.queue("m-sonnet", ok(VISION_SECTIONS, items=VISION_ITEMS))
    await runtime.run(project.id, "vision_objectives")
    shown = sent(provider, vision_prompt_index)
    assert "## [REQ-PRB-001]" in shown and "## [SET-CHR-001]" in shown
    assert "## [REQ-F-001]" not in shown and "## [REQ-NF-001]" not in shown and "## [REQ-PER-001]" not in shown


async def test_the_generation_record_lists_the_items_a_version_holds(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items={"Personas": "- PER-001 A. Derives from: SET-CHR-001\n- PER-002 B. Derives from: SET-CHR-001"}))
    result = await runtime.run(project.id, "personas")
    assert store.artefacts.get_version(project.id, result.artefact_id).generation["items"] == ["PER-001", "PER-002"]


# ---- replay ----------------------------------------------------------------------------------------------------------------------------

async def test_a_recorded_requirements_run_replays_with_a_new_project_id_and_makes_no_network_call(make_settings, tmp_path):
    from .test_agent_misc import open_charter_project

    settings = make_settings(**MODELS, replay_set="reqs")
    folder = settings.recordings_path
    live = Store.open(tmp_path / "live.db", limits=settings.context_limits)
    scripted = MockProvider()
    scripted.queue("m-sonnet", ok(CHARTER_SECTIONS), ok(PERSONA_SECTIONS, items=PERSONA_ITEMS))
    runtime, engine = runtime_over(settings, RecordingProvider(scripted, RecordingStore(folder), settings), live)
    pid = open_charter_project(live, engine).id
    await runtime.run(pid, "project_charter")
    engine.finish(pid, "setup", actor="system")
    engine.approve(pid, "setup", actor=PERSON)
    engine.start(pid, "requirements", actor="system")
    first = await runtime.run(pid, "personas")
    assert len(scripted.calls) == 2

    class Boom(MockProvider):
        async def complete(self, model_id, request):
            raise AssertionError("the network was used during replay")

    again = Store.open(tmp_path / "again.db", limits=settings.context_limits)
    replay_runtime, replay_engine = runtime_over(settings, ReplayProvider(RecordingStore(folder)), again)
    pid2 = open_charter_project(again, replay_engine).id
    await replay_runtime.run(pid2, "project_charter")
    replay_engine.finish(pid2, "setup", actor="system")
    replay_engine.approve(pid2, "setup", actor=PERSON)
    replay_engine.start(pid2, "requirements", actor="system")
    second = await replay_runtime.run(pid2, "personas", run_id="another-run")
    assert (second.items, second.links, second.cost_usd) == (first.items, first.links, first.cost_usd)
    assert [(l.from_id, l.to_id) for l in again.links.list(pid2)] == [(l.from_id, l.to_id) for l in live.links.list(pid)]


# ---- the S11 probe, through the runtime (S08 decision 6) ---------------------------------------------------------------------

async def test_regenerating_an_artefact_replaces_its_links_so_the_table_matches_the_text(rig, store, project):
    """The probe that found the defect: version 1 derives PER-002 from the charter, version 2 from PER-001.
    Before the fix the table held both. Now it holds exactly what the newest version says."""
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    v1 = {"Personas": "- PER-001 A. Derives from: SET-CHR-001\n- PER-002 B. Derives from: SET-CHR-001"}
    v2 = {"Personas": "- PER-001 A. Derives from: SET-CHR-001\n- PER-002 B. Derives from: PER-001"}
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=v1), ok(PERSONA_SECTIONS, items=v2))
    await runtime.run(project.id, "personas")
    assert sorted((l.from_id, l.to_id) for l in store.links.list(project.id)) == [("PER-001", "SET-CHR-001"), ("PER-002", "SET-CHR-001")]
    await runtime.run(project.id, "personas")
    assert sorted((l.from_id, l.to_id) for l in store.links.list(project.id)) == [("PER-001", "SET-CHR-001"), ("PER-002", "PER-001")]
    assert [e.target_id for e in store.audit.list(project.id, action="link.removed")] == ["PER-002>derives>SET-CHR-001"]
