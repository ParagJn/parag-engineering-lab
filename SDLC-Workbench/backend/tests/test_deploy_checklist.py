"""S21c: the deployment checklist. A person's answers are kept in their name and never erased; no model is involved anywhere."""
from __future__ import annotations

import sqlite3

import httpx
import pytest
from fastapi import FastAPI

from app.deploy import checklist as CL
from app.deploy import checks as C
from app.models import InvalidInput, NotFoundError
from app.repos import MAX_CHECK_NOTE
from app.review.errors import PersonRequired, WrongPhaseState
from app.routes_deploy import router

pytestmark = pytest.mark.anyio
ANN = {"X-Actor": "Ann"}


@pytest.fixture
def open_deploy(store, project):
    store.phases.ensure(project.id, "deploy", actor="system")
    store.phases.set_status(project.id, "deploy", "running", actor="system")
    return project


# ---- the list itself --------------------------------------------------------------------------------------------------------------------------

def test_there_are_sixteen_checks_in_four_groups_each_with_a_stable_id_and_one_question():
    assert [c.id for c in C.CHECKS] == [f"CHK-{n:03d}" for n in range(1, 17)]
    assert {g: len(C.of_group(g)) for g in C.GROUPS} == {"ready": 4, "before": 4, "after": 7, "decision": 1}
    assert [c.group for c in C.CHECKS] == ["ready"] * 4 + ["before"] * 4 + ["after"] * 7 + ["decision"]
    assert all(c.question.endswith(".") and len(c.question) > 30 and "?" not in c.question[:5] for c in C.CHECKS)
    assert len({c.question for c in C.CHECKS}) == 16


def test_the_decision_is_the_last_check_and_the_only_one_in_its_group():
    assert C.DECISION_ID == "CHK-016" and C.CHECKS[-1].id == C.DECISION_ID and C.of_group("decision") == (C.CHECKS[-1],) and C.CHECKS[-1].question.startswith("Overall: go.")


def test_the_groups_have_titles_and_the_answers_have_words():
    assert [C.GROUP_TITLE[g] for g in C.GROUPS] == ["Ready to go", "Before the release", "After the release", "The decision"]
    assert C.ANSWERS == ("go", "no_go", "not_applicable") and C.ANSWER_WORDS == {"go": "Go", "no_go": "No-go", "not_applicable": "Not applicable"}


def test_the_checks_say_where_they_come_from_in_words_where_there_is_a_source():
    assert C.BY_ID["CHK-005"].from_where == "Build Verify" and C.BY_ID["CHK-004"].from_where == "the rollback section of the plan"
    assert C.BY_ID["CHK-012"].from_where == ""


# ---- the record -------------------------------------------------------------------------------------------------------------------------------

def test_an_answer_is_saved_in_a_persons_name_with_its_note_and_time(store, project):
    saved = store.deploy_checks.answer(project.id, "CHK-001", "go", actor="human:ann", note="  read it twice  ")
    assert (saved.check_id, saved.answer, saved.note, saved.actor, saved.project_id) == ("CHK-001", "go", "read it twice", "human:ann", project.id) and saved.at and saved.id >= 1


def test_changing_your_mind_adds_a_line_and_the_latest_counts_and_the_history_keeps_both(store, project):
    store.deploy_checks.answer(project.id, "CHK-001", "go", actor="human:ann")
    store.deploy_checks.answer(project.id, "CHK-002", "go", actor="human:ann")
    store.deploy_checks.answer(project.id, "CHK-001", "no_go", actor="human:bo", note="found a problem")
    assert [(a.check_id, a.answer) for a in store.deploy_checks.history(project.id)] == [("CHK-001", "go"), ("CHK-002", "go"), ("CHK-001", "no_go")]
    latest = store.deploy_checks.latest(project.id)
    assert (latest["CHK-001"].answer, latest["CHK-001"].actor, latest["CHK-001"].note) == ("no_go", "human:bo", "found a problem") and latest["CHK-002"].answer == "go"


def test_a_bad_answer_a_long_note_a_blank_check_and_a_non_person_are_refused(store, project):
    for bad, words in ((dict(answer="maybe"), "answer must be one of"), (dict(answer="go", note="n" * (MAX_CHECK_NOTE + 1)), "at most 1000"), (dict(answer="go", check_id=" "), "must not be blank")):
        with pytest.raises(InvalidInput, match=words):
            store.deploy_checks.answer(project.id, bad.get("check_id", "CHK-001"), bad["answer"], actor="human:ann", note=bad.get("note", ""))
    with pytest.raises(InvalidInput):
        store.deploy_checks.answer(project.id, "CHK-001", "go", actor="ann")
    assert store.deploy_checks.history(project.id) == []


def test_an_answer_for_an_unknown_project_is_refused_and_one_projects_answers_stay_apart(store, project):
    with pytest.raises(NotFoundError):
        store.deploy_checks.answer("nope", "CHK-001", "go", actor="human:ann")
    other = store.projects.create(name="Other", actor="system")
    store.deploy_checks.answer(project.id, "CHK-001", "go", actor="human:ann")
    assert store.deploy_checks.history(other.id) == [] and store.deploy_checks.latest(other.id) == {}


def test_the_record_is_append_only(store, project):
    store.deploy_checks.answer(project.id, "CHK-001", "go", actor="human:ann")
    raw = sqlite3.connect(store.db.path)
    for sql in ("UPDATE deploy_checks SET answer = 'no_go'", "DELETE FROM deploy_checks"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            raw.execute(sql)
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute("INSERT INTO deploy_checks (project_id, check_id, answer, actor, at) VALUES (?, 'CHK-001', 'great', 'human:a', 't')", (project.id,))
    raw.close()
    assert store.deploy_checks.latest(project.id)["CHK-001"].answer == "go"


# ---- the checklist as a person sees it -------------------------------------------------------------------------------------------------------

def test_a_new_checklist_has_every_check_unanswered_and_is_not_complete(store, project):
    cl = CL.build(store, project.id)
    assert cl.total == 16 and cl.unanswered == 16 and (cl.go, cl.no_go, cl.not_applicable) == (0, 0, 0) and not cl.complete and cl.decision is None
    assert cl.open_items() == {"no_go": [], "unanswered": [c.id for c in C.CHECKS], "decision": None}


def test_the_totals_follow_the_latest_answers_and_add_up(store, project):
    for cid, value in (("CHK-001", "go"), ("CHK-002", "no_go"), ("CHK-003", "not_applicable"), ("CHK-002", "go"), ("CHK-004", "no_go")):
        store.deploy_checks.answer(project.id, cid, value, actor="human:ann")
    cl = CL.build(store, project.id)
    assert (cl.go, cl.no_go, cl.not_applicable, cl.unanswered) == (2, 1, 1, 12) and cl.go + cl.no_go + cl.not_applicable + cl.unanswered == cl.total
    assert cl.open_items()["no_go"] == ["CHK-004"] and cl.open_items()["unanswered"][0] == "CHK-005"


def test_it_is_complete_only_when_every_check_has_an_answer_and_the_decision_is_what_was_recorded_last_never_worked_out(store, project):
    for c in C.CHECKS[:-1]:
        store.deploy_checks.answer(project.id, c.id, "no_go" if c.id == "CHK-003" else "go", actor="human:ann")
    cl = CL.build(store, project.id)
    assert not cl.complete and cl.decision is None and cl.unanswered == 1                      # a No-go and 14 Gos do not make a decision
    store.deploy_checks.answer(project.id, C.DECISION_ID, "go", actor="human:ann")
    cl = CL.build(store, project.id)
    assert cl.complete and cl.decision == "go" and cl.no_go == 1                                # the person decided Go in spite of one No-go; the page shows both
    store.deploy_checks.answer(project.id, C.DECISION_ID, "no_go", actor="human:ann")
    assert CL.build(store, project.id).decision == "no_go"


def test_each_row_keeps_its_own_history_in_order(store, project):
    for value in ("go", "no_go", "go"):
        store.deploy_checks.answer(project.id, "CHK-005", value, actor="human:ann")
    row = next(r for r in CL.build(store, project.id).rows if r.check.id == "CHK-005")
    assert [h.answer for h in row.history] == ["go", "no_go", "go"] and row.latest is row.history[-1]


# ---- who may answer, and when -----------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("actor", ["system", "agent:r@m", "", "ann"])
def test_an_agent_the_system_or_a_bare_name_may_not_answer(store, open_deploy, actor):
    with pytest.raises(PersonRequired):
        CL.answer(store, open_deploy.id, "CHK-001", "go", actor=actor)
    assert store.deploy_checks.history(open_deploy.id) == []


@pytest.mark.parametrize("status", ["not_started", "approved"])
def test_a_check_cannot_be_answered_before_the_phase_opens_or_after_it_is_approved(store, project, status):
    store.phases.ensure(project.id, "deploy", actor="system")
    if status == "approved":
        store.phases.set_status(project.id, "deploy", "running", actor="system")
        store.phases.set_status(project.id, "deploy", "awaiting_review", actor="system")
        store.phases.record_decision(project.id, "deploy", "approve", actor="human:ann")
    with pytest.raises(WrongPhaseState, match="a check can be answered only while the phase is running or awaiting_review"):
        CL.answer(store, project.id, "CHK-001", "go", actor="human:ann")
    assert store.deploy_checks.history(project.id) == []


def test_a_check_can_be_answered_while_the_phase_runs_and_while_it_awaits_review(store, open_deploy):
    CL.answer(store, open_deploy.id, "CHK-001", "go", actor="human:ann")
    store.phases.set_status(open_deploy.id, "deploy", "awaiting_review", actor="system")
    CL.answer(store, open_deploy.id, "CHK-002", "no_go", actor="human:ann")
    assert len(store.deploy_checks.history(open_deploy.id)) == 2


def test_an_unknown_check_is_not_found_and_nothing_is_saved(store, open_deploy):
    with pytest.raises(NotFoundError, match="there is no check 'CHK-099'"):
        CL.answer(store, open_deploy.id, "CHK-099", "go", actor="human:ann")
    assert store.deploy_checks.history(open_deploy.id) == []


# ---- the routes -------------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def api(store, open_deploy):
    app = FastAPI()
    app.include_router(router)
    app.state.store = store
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=ANN), f"/api/projects/{open_deploy.id}/deploy/checklist"


async def test_the_checklist_is_read_with_its_groups_checks_totals_and_nothing_answered_yet(api):
    client, base = api
    body = (await client.get(base)).json()
    assert [g["key"] for g in body["groups"]] == ["ready", "before", "after", "decision"] and [g["title"] for g in body["groups"]][0] == "Ready to go"
    assert [len(g["checks"]) for g in body["groups"]] == [4, 4, 7, 1]
    first = body["groups"][0]["checks"][0]
    assert set(first) == {"id", "question", "from", "latest", "history"} and first["id"] == "CHK-001" and first["latest"] is None and first["history"] == []
    assert body["totals"] == {"total": 16, "go": 0, "no_go": 0, "not_applicable": 0, "unanswered": 16} and body["decision"] is None and body["complete"] is False and body["decision_check"] == "CHK-016"
    await client.aclose()


async def test_an_answer_is_saved_in_the_callers_name_and_the_whole_checklist_comes_back(api):
    client, base = api
    body = (await client.put(f"{base}/CHK-001", json={"answer": "go", "note": "read it"})).json()
    latest = body["groups"][0]["checks"][0]["latest"]
    assert latest["answer"] == "go" and latest["note"] == "read it" and latest["by"] == "human:Ann" and latest["at"] and body["totals"]["go"] == 1 and body["totals"]["unanswered"] == 15
    again = (await client.put(f"{base}/CHK-001", json={"answer": "no_go"})).json()
    check = again["groups"][0]["checks"][0]
    assert check["latest"]["answer"] == "no_go" and [h["answer"] for h in check["history"]] == ["go", "no_go"] and again["totals"]["no_go"] == 1 and again["totals"]["go"] == 0
    await client.aclose()


async def test_the_decision_is_reported_when_it_is_recorded(api):
    client, base = api
    body = (await client.put(f"{base}/CHK-016", json={"answer": "go"})).json()
    assert body["decision"] == "go" and body["complete"] is False
    await client.aclose()


async def test_bad_requests_get_plain_answers_and_save_nothing(api, store, open_deploy):
    client, base = api
    assert (await client.put(f"{base}/CHK-099", json={"answer": "go"})).status_code == 404
    assert (await client.put(f"{base}/bad", json={"answer": "go"})).status_code == 422
    assert (await client.put(f"{base}/CHK-001", json={"answer": "maybe"})).status_code == 422
    assert (await client.put(f"{base}/CHK-001", json={"answer": "go", "note": "n" * 1001})).status_code == 422
    assert (await client.put(f"{base}/CHK-001", json={"answer": "go", "extra": 1})).status_code == 422
    assert (await client.put(f"{base}/CHK-001", json={})).status_code == 422
    assert store.deploy_checks.history(open_deploy.id) == []
    await client.aclose()


async def test_a_name_is_needed_a_closed_phase_and_an_archived_project_are_refused_and_reading_still_works(api, store, open_deploy):
    client, base = api
    bare = httpx.AsyncClient(transport=client._transport, base_url="http://test")
    assert (await bare.put(f"{base}/CHK-001", json={"answer": "go"})).status_code == 400
    store.phases.set_status(open_deploy.id, "deploy", "awaiting_review", actor="system")
    store.phases.record_decision(open_deploy.id, "deploy", "approve", actor="human:ann")
    refused = await client.put(f"{base}/CHK-001", json={"answer": "go"})
    assert refused.status_code == 409 and "a check can be answered only while the phase is running or awaiting_review" in refused.json()["detail"]
    store.projects.archive(open_deploy.id, actor="system")
    assert (await client.put(f"{base}/CHK-001", json={"answer": "go"})).status_code == 409
    assert (await client.get(base)).status_code == 200
    assert (await client.get("/api/projects/nope/deploy/checklist")).status_code == 404
    await client.aclose(); await bare.aclose()


# ---- what approval records ---------------------------------------------------------------------------------------------------------------------

async def test_the_open_items_of_the_deploy_phase_list_the_checks_that_are_no_go_and_the_ones_not_answered_and_no_other_phase_has_them(store, open_deploy):
    from app.agents.runtime import AgentRuntime
    from app.review.human import HumanActions
    from tests.test_deploy_skills import MODELS
    from app.agents.skills import SkillLibrary
    from app.llm.gateway import Gateway
    from app.llm.providers.mock import MockProvider
    from app.llm.routing import Routing
    from app.review.prompt import load_rubric
    from app.review.service import ReviewService
    from app.workflow.definitions import load_catalogue
    from app.workflow.engine import WorkflowEngine
    from app.config import Settings
    cfg = Settings(_env_file=None, **MODELS)
    catalogue = load_catalogue(Routing.load().roles.keys())
    engine = WorkflowEngine(catalogue, store)
    runtime = AgentRuntime(cfg, store, Gateway(cfg, Routing.load(), MockProvider(), store), catalogue, engine, SkillLibrary.load(catalogue))
    human = HumanActions(store, engine, runtime, ReviewService(cfg, store, runtime.gateway, runtime, engine, load_rubric()))
    CL.answer(store, open_deploy.id, "CHK-002", "no_go", actor="human:ann")
    CL.answer(store, open_deploy.id, "CHK-001", "go", actor="human:ann")
    CL.answer(store, open_deploy.id, "CHK-016", "go", actor="human:ann")
    items = human.open_items(open_deploy.id, "deploy")
    got = items["deployment_checks"]
    assert got["no_go"] == ["CHK-002"] and got["decision"] == "go" and "CHK-001" not in got["unanswered"] and "CHK-002" not in got["unanswered"] and len(got["unanswered"]) == 13
    for phase in ("setup", "requirements", "design", "architecture", "build"):
        assert "deployment_checks" not in human.open_items(open_deploy.id, phase), phase


# ---- the one-page report ------------------------------------------------------------------------------------------------------------------------

def test_the_report_has_the_decision_the_totals_every_check_and_says_no_model_was_used(store, project):
    store.deploy_checks.answer(project.id, "CHK-001", "go", actor="human:ann", note="read | twice")
    store.deploy_checks.answer(project.id, "CHK-002", "no_go", actor="human:bo")
    store.deploy_checks.answer(project.id, "CHK-002", "go", actor="human:bo", note="fixed")
    store.deploy_checks.answer(project.id, "CHK-016", "go", actor="human:ann")
    text = CL.report_markdown(CL.build(store, project.id), "Rooms")
    assert text.startswith("# Deployment verification: Rooms") and "**Overall decision:** Go" in text and "3 of 16 checks answered: 3 Go, 0 No-go, 0 Not applicable, 13 not answered." in text
    assert "This record was filled in by hand. No model was used." in text
    for check in C.CHECKS:
        assert f"| {check.id} | {check.question} |" in text, check.id
    for title in C.GROUP_TITLE.values():
        assert f"## {title}" in text
    assert "| CHK-001 |" in text and "read \\| twice" in text and "| Not answered |" in text
    assert "## Answers that were changed" in text and "**CHK-002**: No-go (bo, " in text and "Go (bo, " in text.split("**CHK-002**")[1]


def test_a_report_with_no_decision_and_no_changes_says_so_and_has_no_changed_section(store, project):
    text = CL.report_markdown(CL.build(store, project.id), "Rooms")
    assert "**Overall decision:** not recorded yet" in text and "0 of 16 checks answered" in text and "Answers that were changed" not in text


def test_a_name_with_markup_or_a_pipe_in_a_note_cannot_break_the_table(store, project):
    store.deploy_checks.answer(project.id, "CHK-003", "go", actor="human:ann", note="line one\nline | two <b>x</b>")
    text = CL.report_markdown(CL.build(store, project.id), "A | B")
    row = next(l for l in text.split("\n") if l.startswith("| CHK-003 |"))
    assert "\n" not in row and row.count(" | ") == 5 and "line one line \\| two <b>x</b>" in row


async def test_the_report_downloads_as_markdown_and_as_a_word_file_made_from_the_same_text(api, store, open_deploy):
    import io
    from docx import Document
    client, base = api
    await client.put(f"{base}/CHK-001", json={"answer": "go", "note": "ok"})
    md = await client.get(f"{base}/report")
    assert md.status_code == 200 and md.headers["content-disposition"] == 'attachment; filename="deployment-verification.md"' and md.headers["content-type"] == "text/markdown; charset=utf-8"
    assert md.text.startswith("# Deployment verification: ") and "| CHK-001 |" in md.text
    word = await client.get(f"{base}/report", params={"format": "docx"})
    assert word.status_code == 200 and word.headers["content-disposition"] == 'attachment; filename="deployment-verification.docx"'
    doc = Document(io.BytesIO(word.content))
    assert doc.core_properties.title.startswith("Deployment verification - ") and doc.core_properties.subject == "Deployment verification checklist"
    cells = [c.text for t in doc.tables for r in t.rows for c in r.cells]
    assert "CHK-001" in cells and "Go" in cells and "ok" in cells and len(doc.tables) == 4
    assert [p.text for p in doc.paragraphs if p.style.name == "Heading 2"] == ["Ready to go", "Before the release", "After the release", "The decision"]
    await client.aclose()


async def test_the_report_refuses_a_bad_format_and_an_unknown_project_and_changes_nothing(api, store, open_deploy):
    client, base = api
    for fmt in ("pdf", "", "MD"):
        assert (await client.get(f"{base}/report", params={"format": fmt})).status_code == 422, fmt
    assert (await client.get("/api/projects/nope/deploy/checklist/report")).status_code == 404
    assert store.deploy_checks.history(open_deploy.id) == []
    store.projects.archive(open_deploy.id, actor="system")
    assert (await client.get(f"{base}/report")).status_code == 200                 # an archived project can still be read
    await client.aclose()


# ---- the edges (S21c mutation survivors) ------------------------------------------------------------------------------------------------------------

def test_the_note_limit_is_one_number_in_the_list_and_in_the_record():
    assert C.MAX_NOTE_CHARS == MAX_CHECK_NOTE == 1000


async def test_the_checklist_can_be_read_without_giving_a_name(api):
    client, base = api
    bare = httpx.AsyncClient(transport=client._transport, base_url="http://test")
    assert (await bare.get(base)).status_code == 200 and (await bare.get(f"{base}/report")).status_code == 200
    await client.aclose(); await bare.aclose()


async def test_an_archived_project_refuses_an_answer_even_while_its_phase_is_open(api, store, open_deploy):
    client, base = api
    store.projects.archive(open_deploy.id, actor="system")
    refused = await client.put(f"{base}/CHK-001", json={"answer": "go"})
    assert refused.status_code == 409 and "archived" in refused.json()["detail"].lower() and store.deploy_checks.history(open_deploy.id) == []
    await client.aclose()


async def test_a_note_over_the_limit_is_refused_before_it_reaches_the_record_and_one_at_the_limit_is_kept(api, store, open_deploy):
    client, base = api
    too_long = await client.put(f"{base}/CHK-001", json={"answer": "go", "note": "n" * 1001})
    assert too_long.status_code == 422 and isinstance(too_long.json()["detail"], list)               # refused by the request's own check, not later by the record
    ok = await client.put(f"{base}/CHK-001", json={"answer": "go", "note": "n" * 1000})
    assert ok.status_code == 200 and store.deploy_checks.latest(open_deploy.id)["CHK-001"].note == "n" * 1000
    await client.aclose()


def test_the_report_names_the_person_without_the_human_mark(store, project):
    store.deploy_checks.answer(project.id, "CHK-001", "go", actor="human:Ann Lee")
    text = CL.report_markdown(CL.build(store, project.id), "Rooms")
    row = next(l for l in text.split("\n") if l.startswith("| CHK-001 |"))
    assert "| Go | Ann Lee |" in row and "human:" not in text

