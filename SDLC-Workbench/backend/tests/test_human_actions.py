"""What a person does with a phase under review: request changes, targeted re-run, edit, approve, and stale detection."""
from __future__ import annotations

import sqlite3

import pytest

from app.review.errors import EditRefused, PersonRequired, ReviewError, WrongPhaseState
from app.review.human import HumanActions
from app.review.prompt import load_rubric
from app.review.service import ReviewService

from .test_agent_runtime import (
    FR_ITEMS,
    FR_SECTIONS,
    PERSON,
    PERSONA_ITEMS,
    PERSONA_SECTIONS,
    PROBLEM_SECTIONS,
    chain_to_requirements,
    ok,
    reply,
)
from .test_review_service import REVIEW_CLEAN, REVIEW_HIGH, rig as _rig, review_reply  # noqa: F401  (rig is a fixture)

pytestmark = pytest.mark.anyio

NFR_SECTIONS = ["Overview", "Requirements", "Quality targets", "Open questions"]


@pytest.fixture
def world(_rig, store, project):
    """A project with Setup approved, Requirements running, and three artefacts written: personas, problem, FR."""

    async def build(**settings):
        service, runtime, provider, engine = _rig(**settings)
        human = HumanActions(store, engine, runtime, service)
        await chain_to_requirements(runtime, provider, store, project, engine)
        provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=PERSONA_ITEMS), ok(PROBLEM_SECTIONS), ok(FR_SECTIONS, items=FR_ITEMS))
        for key in ("personas", "problem_statement", "functional_requirements"):
            await runtime.run(project.id, key)
        return service, runtime, provider, engine, human

    return build


def to_review(engine, project):
    engine.finish(project.id, "requirements", actor="system")


# ---- only a person ----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("actor", ["system", "agent:r@m", "", "ann"])
async def test_every_human_action_refuses_an_agent_the_system_and_a_bare_name(world, store, project, actor):
    service, runtime, provider, engine, human = await world()
    to_review(engine, project)
    with pytest.raises(PersonRequired):
        human.request_changes(project.id, "requirements", actor=actor, notes={"REQ-PER-001": "x"})
    with pytest.raises(PersonRequired):
        human.edit(project.id, "REQ-PER-001", "## Personas\n- PER-001 x. Derives from: SET-CHR-001", actor=actor)
    with pytest.raises(PersonRequired):
        human.approve(project.id, "requirements", actor=actor)
    with pytest.raises(PersonRequired):
        await human.rerun_rejected(project.id, "requirements", actor=actor)
    assert store.phases.get(project.id, "requirements").status == "awaiting_review"


# ---- request changes ----------------------------------------------------------------------------------------------

async def test_changes_are_requested_with_the_decision_and_the_notes_saved_together(world, store, project):
    service, runtime, provider, engine, human = await world()
    to_review(engine, project)
    run = human.request_changes(project.id, "requirements", actor=PERSON, notes={"REQ-F-001": "FR-005 is too vague"}, overall="Tighten the wording")
    assert run.status == "rejected" and run.decision == "reject" and run.decided_by == PERSON
    notes = store.memory.list(project.id, phase_key="requirements")
    assert [(n.kind, n.artefact_id, n.text) for n in notes] == [
        ("human_feedback", "REQ-F-001", "FR-005 is too vague"), ("human_feedback", None, "Tighten the wording")]
    decided = store.audit.list(project.id, action="phase.decided")[-1]
    assert decided.detail["decision"] == "reject" and decided.detail["notes"] == 2


async def test_a_failure_while_saving_a_note_leaves_the_phase_awaiting_review_and_no_notes(world, store, project, monkeypatch):
    service, runtime, provider, engine, human = await world()
    to_review(engine, project)
    import app.repos as repos

    real = repos._insert_memory
    calls = []

    def second_note_fails(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise sqlite3.OperationalError("disk full")
        return real(*args, **kwargs)

    monkeypatch.setattr(repos, "_insert_memory", second_note_fails)
    with pytest.raises(sqlite3.OperationalError):
        human.request_changes(project.id, "requirements", actor=PERSON, notes={"REQ-F-001": "a"}, overall="b")
    assert len(calls) == 2  # precondition: the first note WAS written before the second failed
    assert store.phases.get(project.id, "requirements").status == "awaiting_review"
    assert store.memory.list(project.id) == []


@pytest.mark.parametrize("notes, message", [
    ({}, "name at least one artefact"),
    ({"REQ-F-001": "   "}, "each artefact sent back needs a note"),
    ({"REQ-F-001": "x" * 4001}, "limited to 4000"),
])
async def test_a_request_without_a_named_artefact_or_with_a_blank_or_huge_note_is_refused(world, store, project, notes, message):
    service, runtime, provider, engine, human = await world()
    to_review(engine, project)
    with pytest.raises(ReviewError, match=message):
        human.request_changes(project.id, "requirements", actor=PERSON, notes=notes)
    assert store.phases.get(project.id, "requirements").status == "awaiting_review"


async def test_changes_cannot_be_requested_on_a_phase_that_is_not_awaiting_review(world, store, project):
    service, runtime, provider, engine, human = await world()
    with pytest.raises(WrongPhaseState, match="requirements is 'running'"):
        human.request_changes(project.id, "requirements", actor=PERSON, notes={"REQ-F-001": "x"})


async def test_an_artefact_from_another_phase_cannot_be_named(world, store, project):
    service, runtime, provider, engine, human = await world()
    to_review(engine, project)
    with pytest.raises(ReviewError, match="SET-CHR-001 belongs to phase 'setup', not 'requirements'"):
        human.request_changes(project.id, "requirements", actor=PERSON, notes={"SET-CHR-001": "x"})
    with pytest.raises(Exception, match="not found"):
        human.request_changes(project.id, "requirements", actor=PERSON, notes={"REQ-F-999": "x"})
    assert store.memory.list(project.id) == []


async def test_reviewer_findings_reach_the_writer_only_when_the_person_asks(world, store, project):
    service, runtime, provider, engine, human = await world()
    provider.queue("m-sonnet", review_reply("<review>\nSummary: s\n- [HIGH] FR-001: invented limit. Fix: remove it.\n</review>"))
    await service.review(project.id, "REQ-F-001")
    to_review(engine, project)
    human.request_changes(project.id, "requirements", actor=PERSON, notes={"REQ-F-001": "see the review"})
    assert [n.kind for n in store.memory.list(project.id, artefact_id="REQ-F-001")] == ["human_feedback"]  # not passed on by default

    engine.start(project.id, "requirements", actor="system")
    engine.finish(project.id, "requirements", actor="system")
    human.request_changes(project.id, "requirements", actor=PERSON, notes={"REQ-F-001": "again"}, include_findings=["REQ-F-001"])
    texts = [n.text for n in store.memory.list(project.id, kind="reviewer_feedback")]
    assert texts == ["Reviewer (HIGH) about FR-001: invented limit. Fix: remove it."]


async def test_findings_cannot_be_passed_on_for_an_artefact_that_is_not_being_sent_back(world, store, project):
    service, runtime, provider, engine, human = await world()
    to_review(engine, project)
    with pytest.raises(ReviewError, match="not named: REQ-PER-001"):
        human.request_changes(project.id, "requirements", actor=PERSON, notes={"REQ-F-001": "x"}, include_findings=["REQ-PER-001"])


# ---- rewrite only what was sent back -------------------------------------------------------------------------------------

async def reject_fr(world, store, project, note="Make FR-001 more specific"):
    service, runtime, provider, engine, human = await world()
    to_review(engine, project)
    human.request_changes(project.id, "requirements", actor=PERSON, notes={"REQ-F-001": note})
    return service, runtime, provider, engine, human


async def test_only_the_named_artefact_is_rewritten_and_the_others_keep_their_version(world, store, project):
    service, runtime, provider, engine, human = await reject_fr(world, store, project)
    provider.queue("m-sonnet", ok(FR_SECTIONS, extra="reworded", items=FR_ITEMS))
    before = len(provider.calls)
    result = await human.rerun_rejected(project.id, "requirements", actor=PERSON)

    assert list(result.rewritten) == ["REQ-F-001"] and result.failed == {} and len(provider.calls) == before + 1
    assert store.artefacts.get(project.id, "REQ-F-001").latest_version == 2
    assert store.artefacts.get(project.id, "REQ-PER-001").latest_version == 1
    assert store.artefacts.get(project.id, "REQ-PRB-001").latest_version == 1
    assert store.phases.get(project.id, "requirements").status == "running"  # left for the person to hand back


async def test_the_writer_sees_the_note_and_its_own_previous_draft(world, store, project):
    service, runtime, provider, engine, human = await reject_fr(world, store, project)
    previous = store.artefacts.get_version(project.id, "REQ-F-001").body
    provider.queue("m-sonnet", ok(FR_SECTIONS, items=FR_ITEMS))
    await human.rerun_rejected(project.id, "requirements", actor=PERSON)
    prompt = provider.calls[-1].request.messages[0].content
    assert "Make FR-001 more specific" in prompt and previous.split("\n")[0] in prompt and "# Feedback to address" in prompt


async def test_a_phase_wide_note_reaches_every_rewritten_artefact(world, store, project):
    service, runtime, provider, engine, human = await world()
    to_review(engine, project)
    human.request_changes(project.id, "requirements", actor=PERSON, notes={"REQ-F-001": "a", "REQ-PER-001": "b"}, overall="Use plainer words everywhere")
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=PERSONA_ITEMS), ok(FR_SECTIONS, items=FR_ITEMS))
    result = await human.rerun_rejected(project.id, "requirements", actor=PERSON)
    assert set(result.rewritten) == {"REQ-F-001", "REQ-PER-001"}
    assert all("Use plainer words everywhere" in c.request.messages[0].content for c in provider.calls[-2:])


async def test_a_note_about_one_artefact_never_reaches_another(world, store, project):
    service, runtime, provider, engine, human = await world()
    to_review(engine, project)
    human.request_changes(project.id, "requirements", actor=PERSON, notes={"REQ-F-001": "ONLY-FOR-FR", "REQ-PER-001": "ONLY-FOR-PERSONAS"})
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=PERSONA_ITEMS), ok(FR_SECTIONS, items=FR_ITEMS))
    await human.rerun_rejected(project.id, "requirements", actor=PERSON)
    personas_prompt, fr_prompt = (c.request.messages[0].content for c in provider.calls[-2:])
    assert "ONLY-FOR-PERSONAS" in personas_prompt and "ONLY-FOR-FR" not in personas_prompt
    assert "ONLY-FOR-FR" in fr_prompt and "ONLY-FOR-PERSONAS" not in fr_prompt


async def test_a_note_is_shown_until_a_newer_version_exists_and_then_never_again_but_stays_in_memory(world, store, project):
    service, runtime, provider, engine, human = await reject_fr(world, store, project, note="NOTE-ONE")
    provider.queue("m-sonnet", ok(FR_SECTIONS, items=FR_ITEMS), ok(FR_SECTIONS, items=FR_ITEMS))
    await human.rerun_rejected(project.id, "requirements", actor=PERSON)
    assert "NOTE-ONE" in provider.calls[-1].request.messages[0].content  # shown to the rewrite it asked for
    await runtime.run(project.id, "functional_requirements")  # a later, unrelated run
    assert "NOTE-ONE" not in provider.calls[-1].request.messages[0].content  # acted on, so no longer shown
    assert [n.text for n in store.memory.list(project.id, artefact_id="REQ-F-001")] == ["NOTE-ONE"]  # but kept for good
    assert store.context.search(project.id, "NOTE-ONE", kinds=["memory"])  # and still searchable


async def test_a_note_that_was_acted_on_does_not_cause_another_rewrite(world, store, project):
    service, runtime, provider, engine, human = await reject_fr(world, store, project)
    provider.queue("m-sonnet", ok(FR_SECTIONS, items=FR_ITEMS))
    await human.rerun_rejected(project.id, "requirements", actor=PERSON)
    engine.finish(project.id, "requirements", actor="system")
    human.request_changes(project.id, "requirements", actor=PERSON, notes={"REQ-PER-001": "second round"})
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=PERSONA_ITEMS))
    result = await human.rerun_rejected(project.id, "requirements", actor=PERSON)
    assert list(result.rewritten) == ["REQ-PER-001"]  # not FR again: its note was already acted on


async def test_one_artefact_failing_keeps_its_old_version_and_the_others_still_run(world, store, project):
    service, runtime, provider, engine, human = await world()
    to_review(engine, project)
    human.request_changes(project.id, "requirements", actor=PERSON, notes={"REQ-PER-001": "a", "REQ-F-001": "b"})
    bad = ok(PERSONA_SECTIONS, items={"Personas": "- no id here"})
    provider.queue("m-sonnet", bad, bad, bad, ok(FR_SECTIONS, items=FR_ITEMS))
    result = await human.rerun_rejected(project.id, "requirements", actor=PERSON)
    assert list(result.rewritten) == ["REQ-F-001"] and list(result.failed) == ["REQ-PER-001"]
    assert "could not be produced" in result.failed["REQ-PER-001"]
    assert store.artefacts.get(project.id, "REQ-PER-001").latest_version == 1 and store.artefacts.get(project.id, "REQ-F-001").latest_version == 2


async def test_artefacts_are_rewritten_in_catalogue_order_even_when_the_person_adds_an_earlier_one_after_a_later_one(world, store, project):
    """Later artefacts read earlier ones, so the personas must be rewritten before the requirements built on them.
    Only FR has a note; the person adds the personas through `also`, so a plain 'in the order found' would run FR first."""
    service, runtime, provider, engine, human = await world()
    to_review(engine, project)
    human.request_changes(project.id, "requirements", actor=PERSON, notes={"REQ-F-001": "tighten"})
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, extra="PERSONAS-V2", items=PERSONA_ITEMS), ok(FR_SECTIONS, items=FR_ITEMS))
    result = await human.rerun_rejected(project.id, "requirements", actor=PERSON, also=["REQ-PER-001"])
    assert list(result.rewritten) == ["REQ-PER-001", "REQ-F-001"] and result.failed == {}
    assert "PERSONAS-V2" in provider.calls[-1].request.messages[0].content   # FR was written from the rewritten personas


async def test_re_running_with_nothing_to_do_is_refused_and_the_phase_stays_rejected(world, store, project):
    service, runtime, provider, engine, human = await reject_fr(world, store, project)
    provider.queue("m-sonnet", ok(FR_SECTIONS, items=FR_ITEMS))
    await human.rerun_rejected(project.id, "requirements", actor=PERSON)
    engine.finish(project.id, "requirements", actor="system")
    store.phases.record_decision(project.id, "requirements", "reject", actor=PERSON, feedback="vague, no notes")
    with pytest.raises(ReviewError, match="no artefact has an unaddressed note"):
        await human.rerun_rejected(project.id, "requirements", actor=PERSON)
    assert store.phases.get(project.id, "requirements").status == "rejected"


async def test_a_phase_that_is_not_rejected_cannot_be_re_run(world, store, project):
    service, runtime, provider, engine, human = await world()
    with pytest.raises(WrongPhaseState, match="requirements is 'running'"):
        await human.rerun_rejected(project.id, "requirements", actor=PERSON)


async def test_a_stale_artefact_can_be_added_to_the_re_run_by_the_person_and_reads_the_rewritten_upstream(world, store, project):
    service, runtime, provider, engine, human = await world()
    to_review(engine, project)
    human.request_changes(project.id, "requirements", actor=PERSON, notes={"REQ-PER-001": "reword the personas"})
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, extra="PERSONAS-V2", items=PERSONA_ITEMS), ok(FR_SECTIONS, items=FR_ITEMS))
    result = await human.rerun_rejected(project.id, "requirements", actor=PERSON, also=["REQ-F-001"])
    assert list(result.rewritten) == ["REQ-PER-001", "REQ-F-001"] and result.stale_not_run == ()
    assert "PERSONAS-V2" in provider.calls[-1].request.messages[0].content  # FR was written from the NEW personas
    assert store.artefacts.get_version(project.id, "REQ-F-001").generation["built_on"]["REQ-PER-001"] == 2
    assert human.stale(project.id) == []


async def test_an_artefact_added_to_the_re_run_must_belong_to_the_phase(world, store, project):
    service, runtime, provider, engine, human = await world()
    to_review(engine, project)
    human.request_changes(project.id, "requirements", actor=PERSON, notes={"REQ-PER-001": "x"})
    with pytest.raises(ReviewError, match="SET-CHR-001 belongs to phase 'setup'"):
        await human.rerun_rejected(project.id, "requirements", actor=PERSON, also=["SET-CHR-001"])
    assert store.phases.get(project.id, "requirements").status == "rejected"


# ---- built on something that has changed ---------------------------------------------------------------------------------

async def test_the_generation_record_names_the_upstream_versions_an_artefact_was_built_on(world, store, project):
    service, runtime, provider, engine, human = await world()
    assert store.artefacts.get_version(project.id, "REQ-F-001").generation["built_on"] == {"SET-CHR-001": 1, "REQ-PER-001": 1, "REQ-PRB-001": 1}
    assert store.artefacts.get_version(project.id, "REQ-PRB-001").generation["built_on"] == {"SET-CHR-001": 1}


async def test_rewriting_an_artefact_makes_exactly_the_artefacts_built_on_its_old_version_stale(world, store, project):
    service, runtime, provider, engine, human = await world()
    assert human.stale(project.id) == []   # precondition: nothing is stale before anything changes
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, extra="v2", items=PERSONA_ITEMS))
    await runtime.run(project.id, "personas")
    stale = human.stale(project.id)
    assert [(s.artefact_id, dict(s.now)) for s in stale] == [("REQ-F-001", {"REQ-PER-001": 2})]
    assert stale[0].built_on["REQ-PER-001"] == 1
    assert human.stale(project.id, "setup") == []


async def test_an_artefact_rewritten_after_its_upstream_is_no_longer_stale(world, store, project):
    service, runtime, provider, engine, human = await world()
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, extra="v2", items=PERSONA_ITEMS), ok(FR_SECTIONS, extra="v2", items=FR_ITEMS))
    await runtime.run(project.id, "personas")
    await runtime.run(project.id, "functional_requirements")
    assert human.stale(project.id) == []


async def test_a_version_with_no_built_on_record_is_not_reported_as_stale(world, store, project):
    service, runtime, provider, engine, human = await world()
    store.artefacts.add_version(project.id, "REQ-F-001", body="## Requirements\n- FR-001 x. Derives from: PER-001", author=PERSON)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, extra="v2", items=PERSONA_ITEMS))
    await runtime.run(project.id, "personas")
    assert human.stale(project.id) == []


async def test_stale_artefacts_are_flagged_but_never_re_run_behind_the_persons_back(world, store, project):
    service, runtime, provider, engine, human = await world()
    to_review(engine, project)
    human.request_changes(project.id, "requirements", actor=PERSON, notes={"REQ-PER-001": "reword"})
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, extra="v2", items=PERSONA_ITEMS))
    calls = len(provider.calls)
    result = await human.rerun_rejected(project.id, "requirements", actor=PERSON)
    assert list(result.rewritten) == ["REQ-PER-001"] and result.stale_not_run == ("REQ-F-001",)
    assert len(provider.calls) == calls + 1 and store.artefacts.get(project.id, "REQ-F-001").latest_version == 1


# ---- a human edit ----------------------------------------------------------------------------------------------------------------

GOOD_PERSONAS = reply(PERSONA_SECTIONS, items={"Personas": "- PER-001 Staff member, edited. Derives from: SET-CHR-001"}).replace("<artefact>\n", "").replace("\n</artefact>", "")


async def test_a_valid_edit_is_saved_as_a_human_version_with_the_earlier_one_kept(world, store, project):
    service, runtime, provider, engine, human = await world()
    number = human.edit(project.id, "REQ-PER-001", GOOD_PERSONAS, actor=PERSON, note="clarified the persona")
    assert number == 2
    latest = store.artefacts.get_version(project.id, "REQ-PER-001")
    assert latest.author == PERSON and "edited" in latest.body and "edited" not in store.artefacts.get_version(project.id, "REQ-PER-001", 1).body
    assert latest.generation["human_edit"] is True and latest.generation["based_on"] == 1 and latest.generation["note"] == "clarified the persona"
    assert latest.generation["items"] == ["PER-001"] and latest.generation["built_on"] == {"SET-CHR-001": 1}


async def test_a_refused_edit_leaves_the_links_alone(world, store, project):
    service, runtime, provider, engine, human = await world()
    assert [(l.from_id, l.to_id) for l in store.links.list(project.id) if l.declared_in == "REQ-PER-001"] == [("PER-001", "SET-CHR-001")]
    body = GOOD_PERSONAS.replace("Derives from: SET-CHR-001", "Derives from: REQ-PRB-001")
    # the personas skill only reads the charter, so REQ-PRB-001 was never shown to it: this edit must be refused
    with pytest.raises(EditRefused, match="derives from REQ-PRB-001"):
        human.edit(project.id, "REQ-PER-001", body, actor=PERSON)
    assert [(l.from_id, l.to_id) for l in store.links.list(project.id) if l.declared_in == "REQ-PER-001"] == [("PER-001", "SET-CHR-001")]


async def test_an_edit_that_breaks_a_rule_is_refused_with_plain_reasons_and_saves_nothing(world, store, project):
    service, runtime, provider, engine, human = await world()
    cases = {
        "a required section is missing": (GOOD_PERSONAS.replace("## How the personas differ", "## Something else"), "How the personas differ"),
        "an ID with the wrong prefix": (GOOD_PERSONAS.replace("PER-001 Staff", "FR-001 Staff"), "FR-001 is under 'Personas'"),
        "a derives-from to something never shown": (GOOD_PERSONAS.replace("SET-CHR-001", "SET-CHR-099"), "SET-CHR-099"),
        "no derives-from": (GOOD_PERSONAS.replace(" Derives from: SET-CHR-001", ""), "has no 'Derives from:'"),
        "a citation that does not resolve": (GOOD_PERSONAS.replace("edited.", "edited [DOC-009#1]."), "DOC-009#1"),
        "numbering that skips": (GOOD_PERSONAS.replace("PER-001", "PER-003"), "PER-001"),
    }
    for name, (body, fragment) in cases.items():
        with pytest.raises(EditRefused) as caught:
            human.edit(project.id, "REQ-PER-001", body, actor=PERSON)
        assert fragment in str(caught.value) and caught.value.problems, name
    assert store.artefacts.get(project.id, "REQ-PER-001").latest_version == 1


async def test_an_edit_cannot_reuse_an_id_that_was_withdrawn_earlier(world, store, project):
    service, runtime, provider, engine, human = await world()
    two = GOOD_PERSONAS.replace("- PER-001 Staff member, edited.", "- PER-001 A. Derives from: SET-CHR-001\n- PER-002 B.")
    human.edit(project.id, "REQ-PER-001", two, actor=PERSON)
    withdrawn = GOOD_PERSONAS + "\n## Withdrawn items\n- PER-002 merged into PER-001"
    human.edit(project.id, "REQ-PER-001", withdrawn, actor=PERSON)
    back = two  # PER-002 returns
    with pytest.raises(EditRefused, match="PER-002 was in an earlier version and is no longer in use"):
        human.edit(project.id, "REQ-PER-001", back, actor=PERSON)


async def test_an_empty_edit_is_refused(world, store, project):
    service, runtime, provider, engine, human = await world()
    with pytest.raises(EditRefused, match="empty"):
        human.edit(project.id, "REQ-PER-001", "   ", actor=PERSON)


async def test_an_edit_is_refused_when_the_phase_is_approved_or_not_started(world, store, project):
    service, runtime, provider, engine, human = await world()
    store.artefacts.create(project.id, artefact_type="user_journey", phase_key="design", title="J", actor="system", prefix="DES-UJ")
    store.artefacts.add_version(project.id, "DES-UJ-001", body="x", author=PERSON)
    with pytest.raises(WrongPhaseState, match="design is 'not_started'"):
        human.edit(project.id, "DES-UJ-001", "x", actor=PERSON)
    with pytest.raises(WrongPhaseState, match="setup is 'approved'"):
        human.edit(project.id, "SET-CHR-001", "x", actor=PERSON)


async def test_an_edit_is_allowed_while_the_phase_is_awaiting_review(world, store, project):
    service, runtime, provider, engine, human = await world()
    to_review(engine, project)
    assert human.edit(project.id, "REQ-PER-001", GOOD_PERSONAS, actor=PERSON) == 2


async def test_an_edit_of_an_artefact_with_no_version_or_no_skill_is_refused(world, store, project):
    service, runtime, provider, engine, human = await world()
    store.artefacts.create(project.id, artefact_type="vision_objectives", phase_key="requirements", title="V", actor="system", prefix="REQ-VIS")
    with pytest.raises(ReviewError, match="has no version yet"):
        human.edit(project.id, "REQ-VIS-001", "x", actor=PERSON)
    store.artefacts.create(project.id, artefact_type="support_guide", phase_key="requirements", title="H", actor="system", prefix="HND-SUP")
    store.artefacts.add_version(project.id, "HND-SUP-001", body="x", author=PERSON)
    with pytest.raises(ReviewError, match="no skill for 'support_guide'"):
        human.edit(project.id, "HND-SUP-001", "x", actor=PERSON)


async def test_an_edit_makes_an_earlier_review_stale(world, store, project):
    service, runtime, provider, engine, human = await world()
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN))
    await service.review(project.id, "REQ-PER-001")
    assert service.status_of(project.id, "REQ-PER-001").state == "reviewed"
    human.edit(project.id, "REQ-PER-001", GOOD_PERSONAS, actor=PERSON)
    assert service.status_of(project.id, "REQ-PER-001").state == "stale"


async def test_editing_an_upstream_artefact_makes_what_is_built_on_it_stale(world, store, project):
    service, runtime, provider, engine, human = await world()
    human.edit(project.id, "REQ-PER-001", GOOD_PERSONAS, actor=PERSON)
    assert [s.artefact_id for s in human.stale(project.id)] == ["REQ-F-001"]


async def test_a_phase_that_closes_while_an_edit_is_being_checked_does_not_save_it(world, store, project, monkeypatch):
    service, runtime, provider, engine, human = await world()
    import app.agents.checks as checks

    real = checks.check_body

    def check_then_close(*args, **kwargs):
        out = real(*args, **kwargs)
        with store.db.write() as conn:  # the phase closes after the checks passed and before the save
            conn.execute("UPDATE phase_runs SET status = 'approved' WHERE project_id = ? AND phase_key = 'requirements'", (project.id,))
        return out

    monkeypatch.setattr("app.review.human.check_body", check_then_close)
    with pytest.raises(WrongPhaseState, match="became 'approved'"):
        human.edit(project.id, "REQ-PER-001", GOOD_PERSONAS, actor=PERSON)
    assert store.artefacts.get(project.id, "REQ-PER-001").latest_version == 1


# ---- approve ------------------------------------------------------------------------------------------------------------------------

def nfr_ready(store, project):
    pass


async def approvable(world, store, project):
    """Requirements needs six artefacts to be approvable; write the rest directly so the test can focus on approval."""
    service, runtime, provider, engine, human = await world()
    for key, prefix, name in (("vision_objectives", "REQ-VIS", "Vision"), ("non_functional_requirements", "REQ-NF", "NFR"), ("epics_features", "REQ-EPC", "Epics")):
        store.artefacts.create(project.id, artefact_type=key, phase_key="requirements", title=name, actor="system", prefix=prefix)
        store.artefacts.add_version(project.id, f"{prefix}-001", body="x", author=PERSON)
    to_review(engine, project)
    return service, runtime, provider, engine, human


async def test_approval_records_what_was_still_open(world, store, project):
    service, runtime, provider, engine, human = await approvable(world, store, project)
    provider.queue("m-sonnet", review_reply(REVIEW_HIGH))
    await service.review(project.id, "REQ-PER-001")
    run = human.approve(project.id, "requirements", actor=PERSON)
    assert run.status == "approved"
    detail = store.audit.list(project.id, action="phase.decided")[-1].detail
    assert detail["decision"] == "approve" and detail["open_high_findings"] == 1
    assert "REQ-PER-001" not in detail["unreviewed"] and "REQ-F-001" in detail["unreviewed"] and len(detail["unreviewed"]) == 5
    assert detail["review_out_of_date"] == [] and detail["built_on_changed"] == []


async def test_approving_a_phase_with_an_out_of_date_review_or_stale_artefact_says_so(world, store, project):
    service, runtime, provider, engine, human = await approvable(world, store, project)
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN))
    await service.review(project.id, "REQ-PER-001")
    engine.start(project.id, "requirements", actor="system")
    human.edit(project.id, "REQ-PER-001", GOOD_PERSONAS, actor=PERSON)
    engine.finish(project.id, "requirements", actor="system")
    human.approve(project.id, "requirements", actor=PERSON)
    detail = store.audit.list(project.id, action="phase.decided")[-1].detail
    assert detail["review_out_of_date"] == ["REQ-PER-001"] and detail["built_on_changed"] == ["REQ-F-001"]


async def test_the_gate_rules_are_unchanged_an_incomplete_phase_still_cannot_be_approved(world, store, project):
    service, runtime, provider, engine, human = await world()
    to_review(engine, project)
    from app.workflow.gates import GateNotMet

    with pytest.raises(GateNotMet, match="required artefact"):
        human.approve(project.id, "requirements", actor=PERSON)
    assert store.phases.get(project.id, "requirements").status == "awaiting_review"
    assert store.audit.list(project.id, action="phase.decided", target_id="requirements") == []


# ---- gaps found by the S08 mutation check ----------------------------------------------------------------------------------------

async def test_an_edit_replaces_the_links_so_the_table_matches_the_text(world, store, project):
    service, runtime, provider, engine, human = await world()

    def mine():
        return sorted((l.from_id, l.to_id) for l in store.links.list(project.id) if l.declared_in == "REQ-PER-001")

    assert mine() == [("PER-001", "SET-CHR-001")]   # precondition: the agent's version declared this one link
    two = GOOD_PERSONAS.replace("- PER-001 Staff member, edited. Derives from: SET-CHR-001",
                                "- PER-001 A. Derives from: SET-CHR-001\n- PER-002 B. Derives from: PER-001")
    human.edit(project.id, "REQ-PER-001", two, actor=PERSON)
    assert mine() == [("PER-001", "SET-CHR-001"), ("PER-002", "PER-001")]
    human.edit(project.id, "REQ-PER-001", GOOD_PERSONAS + "\n## Withdrawn items\n- PER-002 merged into PER-001", actor=PERSON)
    assert mine() == [("PER-001", "SET-CHR-001")]
    [removed] = store.audit.list(project.id, action="link.removed")
    assert (removed.target_id, removed.actor) == ("PER-002>derives>PER-001", PERSON)
    assert removed.detail == {"declared_in": "REQ-PER-001", "replaced_by_version": 3}


async def test_an_edit_may_derive_from_a_whole_upstream_artefact_exactly_as_the_writer_could(world, store, project):
    """The personas skill reads the charter, so SET-CHR-001 is a valid thing to derive from. The edit path must offer the
    same targets the writer was offered, not a narrower set."""
    service, runtime, provider, engine, human = await world()
    assert "Derives from: SET-CHR-001" in GOOD_PERSONAS
    assert human.edit(project.id, "REQ-PER-001", GOOD_PERSONAS, actor=PERSON) == 2


# ---- an edit may cite what the writer was shown: the upstream artefacts AND the items inside them ------------------------------

async def test_an_edit_may_cite_an_item_of_an_upstream_artefact_as_the_writer_could(world, store, project):
    service, runtime, provider, engine, human = await world()
    body = reply(FR_SECTIONS, items=FR_ITEMS, extra="Built on [PER-001].").replace("<artefact>\n", "").replace("\n</artefact>", "")
    assert human.edit(project.id, "REQ-F-001", body, actor=PERSON) == 2


async def test_an_edit_may_not_cite_an_item_that_no_upstream_artefact_has(world, store, project):
    service, runtime, provider, engine, human = await world()
    body = reply(FR_SECTIONS, items=FR_ITEMS, extra="Built on [PER-099].").replace("<artefact>\n", "").replace("\n</artefact>", "")
    with pytest.raises(EditRefused, match=r"\[PER-099\]"):
        human.edit(project.id, "REQ-F-001", body, actor=PERSON)
    assert store.artefacts.get(project.id, "REQ-F-001").latest_version == 1


async def test_an_edit_may_not_cite_its_own_artefact(world, store, project):
    service, runtime, provider, engine, human = await world()
    body = reply(FR_SECTIONS, items=FR_ITEMS, extra="See [REQ-F-001].").replace("<artefact>\n", "").replace("\n</artefact>", "")
    with pytest.raises(EditRefused, match=r"\[REQ-F-001\]"):
        human.edit(project.id, "REQ-F-001", body, actor=PERSON)


# ---- S19e-1: a retired artefact is not 'never reviewed' ----------------------------------------------------------------------------------------

async def test_a_retired_artefact_is_not_listed_as_never_reviewed_and_does_not_block_or_change_the_open_list(world, store, project):
    service, runtime, provider, engine, human = await world()
    store.artefacts.create(project.id, artefact_type="backend_code", phase_key="requirements", title="Backend code", actor="system", prefix="BLD-BE")
    store.artefacts.add_version(project.id, "BLD-BE-001", body="old", author=PERSON)
    store.artefacts.create(project.id, artefact_type="support_guide", phase_key="requirements", title="H", actor="system", prefix="HND-SUP")
    store.artefacts.add_version(project.id, "HND-SUP-001", body="x", author=PERSON)
    open_ = human.open_items(project.id, "requirements")
    assert "BLD-BE-001" not in open_["unreviewed"]                  # retired: not part of the phase's work any more
    assert "HND-SUP-001" in open_["unreviewed"]                      # in the catalogue, just not reviewable yet: still counted as never reviewed


async def test_a_retired_artefact_with_findings_or_a_stale_review_adds_nothing_to_what_is_open(world, store, project):
    service, runtime, provider, engine, human = await world()
    before = human.open_items(project.id, "requirements")
    store.artefacts.create(project.id, artefact_type="backend_code", phase_key="requirements", title="Backend code", actor="system", prefix="BLD-BE")
    store.artefacts.add_version(project.id, "BLD-BE-001", body="old", author=PERSON)
    store.artefacts.set_review_findings(project.id, "BLD-BE-001", 1, {"version_reviewed": 1, "verdict": "revise", "summary": "s", "findings": [
        {"severity": "high", "target": "General", "problem": "p", "fix": "f"}, {"severity": "high", "target": "General", "problem": "q", "fix": "g"}]}, actor="system")
    store.artefacts.add_version(project.id, "BLD-BE-001", body="older edit", author=PERSON)           # the review is now of an older version: it would be 'stale'
    open_ = human.open_items(project.id, "requirements")
    for key in ("open_high_findings", "unreviewed", "review_out_of_date"):
        assert open_[key] == before[key], key                       # exactly what it was before the retired artefact was added
