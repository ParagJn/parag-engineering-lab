"""S22c: the handover sign-off. A list of statements support accepts or does not accept, answered by a named person; no model is involved anywhere, and a
"Not accepted" never blocks approval. Run through the real runner with a scripted model for the two documents."""
from __future__ import annotations

import io

import httpx
import pytest
from docx import Document

from app.deploy import checklist as CL
from app.deploy import checks as C
from app.main import create_app
from app.review.errors import PersonRequired, WrongPhaseState
from app.sample import BRIEF, FILENAME, NAME, POLICY
from scripts import architecture_demo as A

from .test_deploy_skills import NOTES_ITEMS, NOTES_SECTIONS, PLAN_ITEMS, PLAN_SECTIONS, ok
from .test_handover_skills import HYP_ITEMS, HYP_SECTIONS, RUN_SECTIONS

pytestmark = pytest.mark.anyio
ANN = {"X-Actor": "Ann"}
WORDS = {"go": "Accept", "no_go": "Not accepted", "not_applicable": "Not applicable"}


def open_handover(store, project):
    store.phases.ensure(project.id, "handover", actor="system")
    store.phases.set_status(project.id, "handover", "running", actor="system")
    return project


# ---- the list itself ---------------------------------------------------------------------------------------------------------------------------

def test_there_are_eight_statements_in_three_groups_each_with_a_stable_id():
    spec = C.definition_of("handover")
    assert [c.id for c in spec.checks] == [f"SGN-{n:03d}" for n in range(1, 9)]
    assert {g: len(spec.of_group(g)) for g in spec.groups} == {"given": 3, "can": 4, "decision": 1} and spec.groups == ("given", "can", "decision")
    assert [spec.group_title[g] for g in spec.groups] == ["What support has been given", "What support can do", "The decision"]
    assert all(c.question.endswith(".") and len(c.question) > 30 for c in spec.checks) and len({c.question for c in spec.checks}) == 8


def test_the_decision_is_the_last_statement_and_the_only_one_in_its_group():
    spec = C.definition_of("handover")
    assert spec.decision_id == "SGN-008" and spec.checks[-1].id == "SGN-008" and spec.of_group("decision") == (spec.checks[-1],) and spec.checks[-1].question.startswith("Overall: accept.")


def test_the_list_words_the_answers_as_accept_and_not_accepted_but_keeps_them_as_go_and_no_go():
    spec = C.definition_of("handover")
    assert spec.answer_words == WORDS and spec.title == "Handover sign-off" and spec.report_title == "Handover sign-off" and spec.open_items_key == "handover_signoff"
    assert C.ANSWERS == ("go", "no_go", "not_applicable")                                  # the stored values are the same for every list


def test_its_statements_never_share_an_id_or_a_question_with_the_deploy_list():
    handover, deploy = C.definition_of("handover"), C.definition_of("deploy")
    assert not {c.id for c in handover.checks} & {c.id for c in deploy.checks} and not {c.question for c in handover.checks} & {c.question for c in deploy.checks}


def test_the_statements_that_come_from_a_document_say_which_in_words():
    spec = C.definition_of("handover")
    assert spec.by_id["SGN-001"].from_where == "the runbook" and spec.by_id["SGN-002"].from_where == "the hypercare plan" and spec.by_id["SGN-006"].from_where == "the deployment plan"
    assert spec.by_id["SGN-007"].from_where == ""


def test_deploys_list_is_untouched_by_adding_this_one():
    assert [c.id for c in C.CHECKS] == [f"CHK-{n:03d}" for n in range(1, 17)] and C.DEPLOY.answer_words["go"] == "Go" and C.DEPLOY.open_items_key == "deployment_checks"


# ---- answering ----------------------------------------------------------------------------------------------------------------------------------

def test_an_answer_is_saved_in_a_persons_name_for_handover_and_not_for_deploy(store, project):
    open_handover(store, project)
    saved = CL.answer(store, project.id, "SGN-001", "go", actor="human:ann", note="read it", phase="handover")
    assert (saved.phase, saved.check_id, saved.answer, saved.actor) == ("handover", "SGN-001", "go", "human:ann")
    assert CL.build(store, project.id, "handover").go == 1 and CL.build(store, project.id, "deploy").go == 0 and store.deploy_checks.history(project.id, "deploy") == []


def test_changing_your_mind_keeps_both_lines_and_the_latest_counts(store, project):
    open_handover(store, project)
    CL.answer(store, project.id, "SGN-004", "no_go", actor="human:ann", note="not yet", phase="handover")
    CL.answer(store, project.id, "SGN-004", "go", actor="human:ann", note="walked through it", phase="handover")
    row = next(r for r in CL.build(store, project.id, "handover").rows if r.check.id == "SGN-004")
    assert [h.answer for h in row.history] == ["no_go", "go"] and row.latest.note == "walked through it"


@pytest.mark.parametrize("actor", ["agent:handover_author@m", "system", "ann", ""])
def test_an_agent_or_the_system_may_not_sign(store, project, actor):
    open_handover(store, project)
    with pytest.raises(PersonRequired):
        CL.answer(store, project.id, "SGN-001", "go", actor=actor, phase="handover")
    assert store.deploy_checks.history(project.id, "handover") == []


def test_a_deploy_statement_is_refused_in_the_handover_list_and_the_reverse(store, project):
    open_handover(store, project)
    store.phases.ensure(project.id, "deploy", actor="system"); store.phases.set_status(project.id, "deploy", "running", actor="system")
    with pytest.raises(Exception, match="there is no check 'CHK-001'"):
        CL.answer(store, project.id, "CHK-001", "go", actor="human:ann", phase="handover")
    with pytest.raises(Exception, match="there is no check 'SGN-001'"):
        CL.answer(store, project.id, "SGN-001", "go", actor="human:ann", phase="deploy")
    assert store.deploy_checks.history(project.id, "handover") == [] and store.deploy_checks.history(project.id, "deploy") == []


def test_a_phase_that_is_not_open_refuses_a_signature(store, project):
    with pytest.raises(WrongPhaseState, match="handover is 'not_started'"):
        CL.answer(store, project.id, "SGN-001", "go", actor="human:ann", phase="handover")
    open_handover(store, project)
    store.phases.set_status(project.id, "handover", "awaiting_review", actor="system")
    CL.answer(store, project.id, "SGN-001", "go", actor="human:ann", phase="handover")                    # awaiting review is still open
    store.phases.record_decision(project.id, "handover", "approve", actor="human:ann")
    with pytest.raises(WrongPhaseState, match="handover is 'approved'"):
        CL.answer(store, project.id, "SGN-002", "go", actor="human:ann", phase="handover")


def test_the_decision_is_what_the_person_recorded_and_never_worked_out(store, project):
    open_handover(store, project)
    for n in range(1, 8):
        CL.answer(store, project.id, f"SGN-00{n}", "go", actor="human:ann", phase="handover")
    cl = CL.build(store, project.id, "handover")
    assert cl.decision is None and cl.complete is False and cl.go == 7                                      # seven accepts do not make an overall accept
    CL.answer(store, project.id, "SGN-008", "no_go", actor="human:ann", note="Support lead, awaiting access", phase="handover")
    cl = CL.build(store, project.id, "handover")
    assert cl.decision == "no_go" and cl.complete is True and cl.go == 7 and cl.no_go == 1


# ---- the report ----------------------------------------------------------------------------------------------------------------------------------

def test_the_report_uses_the_handover_wording_and_lists_every_statement(store, project):
    open_handover(store, project)
    CL.answer(store, project.id, "SGN-001", "go", actor="human:ann", note="read it", phase="handover")
    CL.answer(store, project.id, "SGN-002", "no_go", actor="human:ann", note="weeks too short", phase="handover")
    CL.answer(store, project.id, "SGN-008", "go", actor="human:ann", note="Support lead", phase="handover")
    text = CL.report_markdown(CL.build(store, project.id, "handover"), "Rooms")
    assert text.startswith("# Handover sign-off: Rooms") and "**Overall decision:** Accept" in text
    assert "3 of 8 checks answered: 2 Accept, 1 Not accepted, 0 Not applicable, 5 not answered." in text and "This record was filled in by hand. No model was used." in text
    for check in C.definition_of("handover").checks:
        assert f"| {check.id} | {check.question} |" in text, check.id
    for title in ("What support has been given", "What support can do", "The decision"):
        assert f"## {title}" in text
    assert "Not accepted" in text and "weeks too short" in text and "Go" not in text.replace("Going", "") and "No-go" not in text


@pytest.fixture
def api(store, project):
    from fastapi import FastAPI
    from app.routes_deploy import router
    app = FastAPI(); app.include_router(router); app.state.store = store
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=ANN), f"/api/projects/{project.id}/handover/checklist"


async def test_the_routes_serve_the_signoff_and_its_report_in_both_formats(api, store, project):
    client, base = api
    open_handover(store, project)
    first = (await client.get(base)).json()
    assert first["phase"] == "handover" and first["title"] == "Handover sign-off" and first["answer_words"] == WORDS and first["totals"]["total"] == 8 and first["decision_check"] == "SGN-008"
    assert [g["title"] for g in first["groups"]] == ["What support has been given", "What support can do", "The decision"]
    body = (await client.put(f"{base}/SGN-001", json={"answer": "go", "note": "ok"})).json()
    assert body["totals"]["go"] == 1 and body["groups"][0]["checks"][0]["latest"]["by"] == "human:Ann"
    md = await client.get(f"{base}/report")
    assert md.status_code == 200 and md.headers["content-disposition"] == 'attachment; filename="handover-sign-off.md"' and md.text.startswith("# Handover sign-off: ")
    word = await client.get(f"{base}/report", params={"format": "docx"})
    assert word.status_code == 200 and word.headers["content-disposition"] == 'attachment; filename="handover-sign-off.docx"'
    doc = Document(io.BytesIO(word.content))
    assert doc.core_properties.title.startswith("Handover sign-off - ") and any("SGN-001" in c.text for t in doc.tables for r in t.rows for c in r.cells)
    assert (await client.get(f"/api/projects/{project.id}/deploy/checklist")).json()["totals"]["go"] == 0                      # Deploy's list is a separate record
    await client.aclose()


async def test_a_wrong_statement_or_a_closed_phase_gets_a_plain_answer_through_the_route(api, store, project):
    client, base = api
    closed = await client.put(f"{base}/SGN-001", json={"answer": "go"})
    assert closed.status_code == 409 and "a check can be answered only while the phase is running or awaiting_review" in closed.json()["detail"]
    open_handover(store, project)
    wrong = await client.put(f"{base}/CHK-001", json={"answer": "go"})
    assert wrong.status_code == 404 and "there is no check 'CHK-001'" in wrong.json()["detail"]
    await client.aclose()


# ---- the phase: documents written, sign-off by hand, approval records what was open ----------------------------------------------------------------

class Handover(A.Scripted):
    """The Architecture demo's scripted model plus the two Deploy documents and the two Handover ones. It records which artefacts it was asked for."""

    def _which(self, request) -> str:
        text = request.messages[0].content
        for key in ("deployment_plan", "release_notes", "runbook", "hypercare_plan"):
            if f"({key}) for the project" in text:
                return key
        return super()._which(request)

    async def complete(self, model_id, request):
        key = self._which(request)
        if key == "deployment_plan":
            self.asked.append(key)
            return ok(PLAN_SECTIONS, {"Steps": "- DPL-001 Create the data store. Derives from: COMP-001, COMP-002, COMP-003", "Overview": "Written from [COMP-001], not from the code."}, tokens=(2000, 900))
        if key == "release_notes":
            self.asked.append(key)
            return ok(NOTES_SECTIONS, {**NOTES_ITEMS, "Overview": "Written from [DEP-PLN-001]."}, tokens=(2000, 900))
        if key == "runbook":
            self.asked.append(key)
            return ok(RUN_SECTIONS, {"Routine care": "- RUN-001 Check the room list opens each morning. Derives from: COMP-001, COMP-002, COMP-003", "Overview": "Written from [COMP-001], not from the live product."}, tokens=(2000, 900))
        if key == "hypercare_plan":
            self.asked.append(key)
            items = {"Who is on hand": "- HYP-001 Someone who can fix the product. Proposed: office hours for two weeks. Derives from: NFR-001, NFR-002"}                    # the demo's design has two non-functional requirements
            return ok(HYP_SECTIONS, {**items, "Overview": "Written from [HND-RUN-001]."}, tokens=(2000, 900))
        return await super().complete(model_id, request)


@pytest.fixture
def world(make_settings):
    async def build():
        cfg = make_settings(**{**A.MODELS, "ibm_ica_openai_model_id": "gpt-x", "ibm_ica_openai_fallback_model_id": "m-sonnet", "llm_retry_backoff_seconds": 0, "run_max_cost_usd": 0})
        provider = Handover()
        app = create_app(cfg, provider=provider)
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=ANN)
        store, engine, runner = app.state.store, app.state.engine, app.state.runner
        project = store.projects.create(name=NAME, brief=BRIEF, actor="system")
        engine.open_project(project.id)
        store.context.add_document(project.id, FILENAME, POLICY, actor="human:demo")
        for phase in ("setup", "requirements", "design", "architecture"):
            await runner.run_phase(project.id, phase)
            engine.finish(project.id, phase, actor="system"); engine.approve(project.id, phase, actor="human:demo")
        engine.start(project.id, "build", actor="system")
        art = store.artefacts.create(project.id, artefact_type="build_instructions", phase_key="build", title="Build instructions", actor="system", prefix="BLD-INS")
        store.artefacts.add_version(project.id, art.id, body="x", author="human:seed")
        engine.finish(project.id, "build", actor="system"); engine.approve(project.id, "build", actor="human:demo")
        await runner.run_phase(project.id, "deploy")
        engine.finish(project.id, "deploy", actor="system"); engine.approve(project.id, "deploy", actor="human:demo")
        return app, client, provider, project

    return build


async def test_a_handover_run_writes_the_runbook_then_the_hypercare_plan_and_nothing_fails(world):
    app, client, provider, project = await world()
    result = await app.state.runner.run_phase(project.id, "handover")
    assert {o.key: o.state for o in result.outcomes} == {"runbook": "done", "hypercare_plan": "done"}
    assert provider.asked[-2:] == ["runbook", "hypercare_plan"]
    events = [e for e in app.state.store.run_events.list(project.id) if e.run_id == result.run_id]
    assert [e.data["key"] for e in events if e.type == "artefact.finished"] == ["runbook", "hypercare_plan"] and not [e for e in events if e.type in ("artefact.failed", "artefact.skipped")]
    assert {a.type for a in app.state.store.artefacts.list(project.id, phase_key="handover")} == {"runbook", "hypercare_plan"}                   # the sign-off never gets an artefact row
    await client.aclose()


async def test_the_phase_can_be_approved_with_the_signoff_open_and_the_approval_records_what_was_open(world):
    app, client, provider, project = await world()
    await app.state.runner.run_phase(project.id, "handover")
    store = app.state.store
    store.deploy_checks.answer(project.id, "SGN-001", "go", actor="human:ann", phase="handover")
    store.deploy_checks.answer(project.id, "SGN-004", "no_go", actor="human:ann", note="not yet", phase="handover")
    app.state.engine.finish(project.id, "handover", actor="system")
    response = await client.post(f"/api/projects/{project.id}/phases/handover/approve")
    assert response.status_code == 200 and response.json()["status"] == "approved"
    detail = store.audit.list(project.id, action="phase.decided")[-1].detail
    assert detail["decision"] == "approve" and detail["handover_signoff"]["no_go"] == ["SGN-004"] and len(detail["handover_signoff"]["unanswered"]) == 6 and detail["handover_signoff"]["decision"] is None
    assert "deployment_checks" not in detail
    await client.aclose()


async def test_deploys_approval_record_does_not_carry_the_signoff_and_the_open_items_follow_each_phase(world):
    app, client, provider, project = await world()
    store = app.state.store
    deploy_detail = store.audit.list(project.id, action="phase.decided")[-1].detail
    assert "handover_signoff" not in deploy_detail
    await app.state.runner.run_phase(project.id, "handover")
    human = app.state.human
    assert set(human.open_items(project.id, "handover")["handover_signoff"]) == {"no_go", "unanswered", "decision"} and "deployment_checks" not in human.open_items(project.id, "handover")
    assert "handover_signoff" not in human.open_items(project.id, "deploy")
    await client.aclose()
