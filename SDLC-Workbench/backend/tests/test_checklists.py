"""S22a: the checklist made general. A list per phase, its answers kept apart, Deploy's behaviour unchanged. A second list is built here for the tests (a phase called
'handover' with its own checks) so the general code is proved before BAU handover's real list exists."""
from __future__ import annotations

import sqlite3

import httpx
import pytest
from fastapi import FastAPI

from app.db import MIGRATIONS, Database, split_statements
from app.deploy import checklist as CL
from app.deploy import checks as C
from app.models import NotFoundError
from app.review.errors import PersonRequired, WrongPhaseState
from app.routes_deploy import router

pytestmark = pytest.mark.anyio
ANN = {"X-Actor": "Ann"}


def other_list() -> C.ChecklistDef:
    checks = (
        C.Check("SGN-001", "given", "The runbook has been read and can be used.", "the runbook"),
        C.Check("SGN-002", "given", "The people who will support the product know who to ask.", ""),
        C.Check("SGN-003", "decision", "Overall: support accepts the product.", ""),
    )
    return C.ChecklistDef(phase="handover", title="Sign-off", report_title="Handover sign-off", groups=("given", "decision"),
                          group_title={"given": "What support has been given", "decision": "The decision"}, decision_id="SGN-003", checks=checks,
                          open_items_key="handover_signoff", answer_words={"go": "Accept", "no_go": "Not accepted", "not_applicable": "Not applicable"})


@pytest.fixture
def two_lists(monkeypatch):
    monkeypatch.setitem(C.LISTS, "handover", other_list())


def open_phase(store, project, phase):
    store.phases.ensure(project.id, phase, actor="system")
    store.phases.set_status(project.id, phase, "running", actor="system")


# ---- a list checks itself when it is made ------------------------------------------------------------------------------------------------------------

def make(**over):
    base = dict(phase="x", title="T", report_title="R", groups=("g", "decision"), group_title={"g": "G", "decision": "D"}, decision_id="ABC-002",
                checks=(C.Check("ABC-001", "g", "q one."), C.Check("ABC-002", "decision", "q two.")), open_items_key="k", answer_words=dict(C.ANSWER_WORDS))
    return C.ChecklistDef(**{**base, **over})


def test_a_well_formed_list_is_accepted_and_exposes_its_checks_by_id_and_group():
    spec = make()
    assert [c.id for c in spec.checks] == ["ABC-001", "ABC-002"] and spec.by_id["ABC-001"].question == "q one." and [c.id for c in spec.of_group("g")] == ["ABC-001"]


@pytest.mark.parametrize("over,word", [
    ({"checks": (C.Check("ABC-001", "g", "a."), C.Check("ABC-001", "decision", "b."))}, "used twice"),
    ({"checks": (C.Check("abc-1", "g", "a."), C.Check("ABC-002", "decision", "b."))}, "looks like ABC-001"),
    ({"checks": (C.Check("ABC-001", "nope", "a."), C.Check("ABC-002", "decision", "b."))}, "a group the list does not have"),
    ({"group_title": {"g": "G"}}, "every group needs a title"),
    ({"answer_words": {"go": "Go"}}, "every answer a word"),
    ({"decision_id": "ABC-009"}, "the decision must be"),
    ({"decision_id": "ABC-001"}, "the decision must be"),
    ({"checks": (C.Check("ABC-002", "decision", "b."), C.Check("ABC-001", "g", "a."))}, "the decision must be"),
    ({"checks": (C.Check("ABC-001", "decision", "a."), C.Check("ABC-002", "decision", "b."))}, "the decision must be"),
])
def test_a_broken_list_cannot_be_made(over, word):
    with pytest.raises(ValueError, match=word):
        make(**over)


def test_the_registry_has_the_deploy_list_and_the_handover_list_and_names_the_phases_that_have_one_when_asked_for_another():
    assert sorted(C.LISTS) == ["deploy", "handover"] and C.definition_of("deploy") is C.DEPLOY and C.definition_of("handover") is C.HANDOVER
    with pytest.raises(KeyError, match=r"'build' has no checklist; the phases that do are \['deploy', 'handover'\]"):
        C.definition_of("build")


def test_deploys_list_is_unchanged_under_its_old_names():
    assert C.CHECKS is C.DEPLOY.checks and C.BY_ID == C.DEPLOY.by_id and C.GROUPS == C.DEPLOY.groups and C.DECISION_ID == "CHK-016" and len(C.CHECKS) == 16
    assert C.DEPLOY.title == "Deployment checklist" and C.DEPLOY.report_title == "Deployment verification" and C.DEPLOY.open_items_key == "deployment_checks"


# ---- two phases' answers stay apart ------------------------------------------------------------------------------------------------------------------

def test_an_answer_for_one_phase_never_shows_in_another_phases_checklist(store, project, two_lists):
    open_phase(store, project, "deploy"); open_phase(store, project, "handover")
    CL.answer(store, project.id, "CHK-001", "go", actor="human:ann")
    CL.answer(store, project.id, "SGN-001", "no_go", actor="human:bo", phase="handover")
    deploy, handover = CL.build(store, project.id, "deploy"), CL.build(store, project.id, "handover")
    assert (deploy.go, deploy.no_go, deploy.total) == (1, 0, 16) and (handover.go, handover.no_go, handover.total) == (0, 1, 3)
    assert [h.phase for h in store.deploy_checks.history(project.id, "deploy")] == ["deploy"] and [h.phase for h in store.deploy_checks.history(project.id, "handover")] == ["handover"]
    assert set(store.deploy_checks.latest(project.id, "handover")) == {"SGN-001"} and set(store.deploy_checks.latest(project.id)) == {"CHK-001"}


def test_a_check_of_one_list_is_refused_in_the_other_and_nothing_is_saved(store, project, two_lists):
    open_phase(store, project, "deploy"); open_phase(store, project, "handover")
    with pytest.raises(NotFoundError, match="there is no check 'SGN-001'; the checks are CHK-001 to CHK-016"):
        CL.answer(store, project.id, "SGN-001", "go", actor="human:ann")
    with pytest.raises(NotFoundError, match="there is no check 'CHK-001'; the checks are SGN-001 to SGN-003"):
        CL.answer(store, project.id, "CHK-001", "go", actor="human:ann", phase="handover")
    assert store.deploy_checks.history(project.id, "deploy") == [] and store.deploy_checks.history(project.id, "handover") == []


def test_each_phase_is_open_for_answers_only_while_its_own_phase_is(store, project, two_lists):
    open_phase(store, project, "deploy")                                                       # Deploy is open; handover has not started
    CL.answer(store, project.id, "CHK-001", "go", actor="human:ann")
    with pytest.raises(WrongPhaseState, match="handover is 'not_started'"):
        CL.answer(store, project.id, "SGN-001", "go", actor="human:ann", phase="handover")
    open_phase(store, project, "handover")
    CL.answer(store, project.id, "SGN-001", "go", actor="human:ann", phase="handover")
    store.phases.set_status(store_project := project.id, "deploy", "awaiting_review", actor="system")
    store.phases.record_decision(store_project, "deploy", "approve", actor="human:ann")
    with pytest.raises(WrongPhaseState, match="deploy is 'approved'"):
        CL.answer(store, project.id, "CHK-002", "go", actor="human:ann")
    CL.answer(store, project.id, "SGN-002", "go", actor="human:ann", phase="handover")         # handover is still open


@pytest.mark.parametrize("actor", ["system", "agent:r@m", "", "ann"])
def test_a_non_person_may_not_answer_in_any_phase(store, project, two_lists, actor):
    open_phase(store, project, "handover")
    with pytest.raises(PersonRequired):
        CL.answer(store, project.id, "SGN-001", "go", actor=actor, phase="handover")
    assert store.deploy_checks.history(project.id, "handover") == []


def test_an_unknown_phase_has_no_checklist_to_build_or_answer(store, project):
    with pytest.raises(KeyError, match="has no checklist"):
        CL.build(store, project.id, "build")
    with pytest.raises(KeyError):
        CL.answer(store, project.id, "CHK-001", "go", actor="human:ann", phase="build")


# ---- the second list is worded its own way ----------------------------------------------------------------------------------------------------------

def test_the_decision_totals_and_open_items_follow_each_phases_own_list(store, project, two_lists):
    open_phase(store, project, "handover")
    for cid in ("SGN-001", "SGN-002"):
        CL.answer(store, project.id, cid, "go", actor="human:ann", phase="handover")
    CL.answer(store, project.id, "SGN-003", "go", actor="human:ann", phase="handover")
    cl = CL.build(store, project.id, "handover")
    assert cl.complete and cl.decision == "go" and cl.total == 3 and cl.open_items() == {"no_go": [], "unanswered": [], "decision": "go"}
    assert CL.build(store, project.id, "deploy").decision is None                                 # recording handover's decision does not record Deploy's


def test_the_report_uses_the_lists_own_title_group_names_and_answer_words(store, project, two_lists):
    open_phase(store, project, "handover")
    CL.answer(store, project.id, "SGN-001", "go", actor="human:ann", phase="handover", note="read it")
    CL.answer(store, project.id, "SGN-002", "no_go", actor="human:ann", phase="handover")
    CL.answer(store, project.id, "SGN-003", "go", actor="human:ann", phase="handover")
    text = CL.report_markdown(CL.build(store, project.id, "handover"), "Rooms")
    assert text.startswith("# Handover sign-off: Rooms") and "**Overall decision:** Accept" in text and "## What support has been given" in text and "## The decision" in text
    assert "| SGN-001 | The runbook has been read and can be used. | Accept |" in text and "| SGN-002 | The people who will support the product know who to ask. | Not accepted |" in text
    assert "Deployment verification" not in text and "CHK-" not in text and "Go" not in text.split("**Overall decision:**")[1].split("\n")[0]


# ---- the migration ------------------------------------------------------------------------------------------------------------------------------------

def test_a_v9_database_keeps_its_deploy_answers_as_deploy_answers_after_the_upgrade_and_they_stay_protected(tmp_path):
    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    for script in MIGRATIONS[:9]:
        for statement in split_statements(script):
            raw.execute(statement)
    raw.execute("PRAGMA user_version = 9")
    raw.execute("INSERT INTO projects (id, name, mode, created_at, updated_at) VALUES ('p1', 'Old', 'replay', 't', 't')")
    raw.execute("INSERT INTO deploy_checks (project_id, check_id, answer, note, actor, at) VALUES ('p1', 'CHK-001', 'go', 'ok', 'human:a', 't')")
    raw.commit(); raw.close()
    assert len(MIGRATIONS) == 11 and Database(path).migrate() == 11
    from app.repos import Store
    store = Store.open(path)
    [kept] = store.deploy_checks.history("p1")
    assert (kept.check_id, kept.answer, kept.note, kept.phase) == ("CHK-001", "go", "ok", "deploy") and store.deploy_checks.history("p1", "handover") == []
    check = sqlite3.connect(path)
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        check.execute("UPDATE deploy_checks SET phase = 'handover'")
    check.close()


def test_the_phase_is_part_of_every_new_row(store, project):
    store.deploy_checks.answer(project.id, "CHK-001", "go", actor="human:ann")
    store.deploy_checks.answer(project.id, "XYZ-001", "go", actor="human:ann", phase="elsewhere")
    assert [(a.check_id, a.phase) for a in store.deploy_checks.history(project.id, "deploy")] == [("CHK-001", "deploy")]
    assert [(a.check_id, a.phase) for a in store.deploy_checks.history(project.id, "elsewhere")] == [("XYZ-001", "elsewhere")]
    with pytest.raises(Exception, match="must not be blank"):
        store.deploy_checks.answer(project.id, "CHK-001", "go", actor="human:ann", phase=" ")


# ---- the routes ----------------------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def api(store, project, two_lists):
    open_phase(store, project, "deploy"); open_phase(store, project, "handover")
    app = FastAPI()
    app.include_router(router)
    app.state.store = store
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=ANN), f"/api/projects/{project.id}"


async def test_deploys_addresses_work_as_before_and_the_new_address_serves_the_other_phase(api):
    client, base = api
    deploy = (await client.get(f"{base}/deploy/checklist")).json()
    other = (await client.get(f"{base}/handover/checklist")).json()
    assert deploy["phase"] == "deploy" and deploy["title"] == "Deployment checklist" and deploy["totals"]["total"] == 16 and deploy["decision_check"] == "CHK-016"
    assert other["phase"] == "handover" and other["title"] == "Sign-off" and other["totals"]["total"] == 3 and other["decision_check"] == "SGN-003"
    assert [g["title"] for g in other["groups"]] == ["What support has been given", "The decision"] and other["answer_words"] == {"go": "Accept", "no_go": "Not accepted", "not_applicable": "Not applicable"}
    assert deploy["answer_words"]["go"] == "Go"
    await client.aclose()


async def test_an_answer_goes_to_the_phase_named_in_the_address_and_comes_back_as_that_phases_checklist(api, store, project):
    client, base = api
    body = (await client.put(f"{base}/handover/checklist/SGN-001", json={"answer": "go", "note": "ok"})).json()
    assert body["phase"] == "handover" and body["totals"]["go"] == 1 and body["groups"][0]["checks"][0]["latest"]["by"] == "human:Ann"
    assert (await client.get(f"{base}/deploy/checklist")).json()["totals"]["go"] == 0
    old = (await client.put(f"{base}/deploy/checklist/CHK-001", json={"answer": "no_go"})).json()
    assert old["phase"] == "deploy" and old["totals"]["no_go"] == 1 and (await client.get(f"{base}/handover/checklist")).json()["totals"]["no_go"] == 0
    await client.aclose()


async def test_a_phase_without_a_checklist_is_a_404_that_names_the_ones_that_have_one(api):
    client, base = api
    for call in (client.get(f"{base}/build/checklist"), client.get(f"{base}/build/checklist/report"), client.put(f"{base}/build/checklist/CHK-001", json={"answer": "go"})):
        r = await call
        assert r.status_code == 404 and "has no checklist" in r.json()["detail"] and "deploy" in r.json()["detail"] and "handover" in r.json()["detail"]
    await client.aclose()


async def test_a_check_of_the_wrong_list_a_bad_id_and_a_closed_phase_get_plain_answers(api, store, project):
    client, base = api
    assert (await client.put(f"{base}/handover/checklist/CHK-001", json={"answer": "go"})).status_code == 404
    assert (await client.put(f"{base}/handover/checklist/bad", json={"answer": "go"})).status_code == 422
    store.phases.set_status(project.id, "handover", "awaiting_review", actor="system")
    store.phases.record_decision(project.id, "handover", "approve", actor="human:ann")
    closed = await client.put(f"{base}/handover/checklist/SGN-001", json={"answer": "go"})
    assert closed.status_code == 409 and "handover is 'approved'" in closed.json()["detail"]
    await client.aclose()


async def test_each_phases_report_has_its_own_title_and_file_name_in_both_formats(api):
    import io
    from docx import Document
    client, base = api
    await client.put(f"{base}/handover/checklist/SGN-001", json={"answer": "go"})
    md = await client.get(f"{base}/handover/checklist/report")
    assert md.headers["content-disposition"] == 'attachment; filename="handover-sign-off.md"' and md.text.startswith("# Handover sign-off: ") and "Accept" in md.text
    word = await client.get(f"{base}/handover/checklist/report", params={"format": "docx"})
    doc = Document(io.BytesIO(word.content))
    assert word.headers["content-disposition"] == 'attachment; filename="handover-sign-off.docx"' and doc.core_properties.title.startswith("Handover sign-off - ")
    deploy = await client.get(f"{base}/deploy/checklist/report")
    assert deploy.headers["content-disposition"] == 'attachment; filename="deployment-verification.md"' and deploy.text.startswith("# Deployment verification: ")
    await client.aclose()


async def test_the_approval_record_of_each_phase_carries_its_own_open_items_under_its_own_name(store, project, two_lists):
    from app.agents.runtime import AgentRuntime
    from app.agents.skills import SkillLibrary
    from app.config import Settings
    from app.llm.gateway import Gateway
    from app.llm.providers.mock import MockProvider
    from app.llm.routing import Routing
    from app.review.human import HumanActions
    from app.review.prompt import load_rubric
    from app.review.service import ReviewService
    from app.workflow.definitions import load_catalogue
    from app.workflow.engine import WorkflowEngine
    from tests.test_deploy_skills import MODELS
    cfg = Settings(_env_file=None, **MODELS)
    catalogue = load_catalogue(Routing.load().roles.keys())
    engine = WorkflowEngine(catalogue, store)
    runtime = AgentRuntime(cfg, store, Gateway(cfg, Routing.load(), MockProvider(), store), catalogue, engine, SkillLibrary.load(catalogue))
    human = HumanActions(store, engine, runtime, ReviewService(cfg, store, runtime.gateway, runtime, engine, load_rubric()))
    open_phase(store, project, "deploy"); open_phase(store, project, "handover")
    CL.answer(store, project.id, "SGN-001", "no_go", actor="human:ann", phase="handover")
    assert human.open_items(project.id, "handover")["handover_signoff"]["no_go"] == ["SGN-001"] and "deployment_checks" not in human.open_items(project.id, "handover")
    assert human.open_items(project.id, "deploy")["deployment_checks"]["no_go"] == [] and "handover_signoff" not in human.open_items(project.id, "deploy")
    for phase in ("setup", "requirements", "design", "architecture", "build"):
        items = human.open_items(project.id, phase)
        assert "deployment_checks" not in items and "handover_signoff" not in items, phase
