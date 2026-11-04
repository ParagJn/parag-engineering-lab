"""Reopening an approved phase (2026-10-31): the action every approved phase offers, the route that does it, and what it leaves alone."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.workflow.engine import ACTIONS_BY_STATUS, allowed_actions
from app.main import create_app
from app.sample import BRIEF, FILENAME, NAME, POLICY
from scripts import design_demo as D

pytestmark = pytest.mark.anyio
ANN = {"X-Actor": "Ann"}
SENTENCE = "This project is archived; restore it first."


# ---- the action table: one rule for every phase ---------------------------------------------------------------------------------------

def test_an_approved_phase_offers_reopen_and_nothing_else():
    assert ACTIONS_BY_STATUS["approved"] == ("reopen",)
    assert allowed_actions("approved", True, None) == ("reopen",)


@pytest.mark.parametrize("status", ["not_started", "running", "awaiting_review", "rejected"])
def test_no_other_status_offers_reopen(status):
    assert "reopen" not in allowed_actions(status, True, None)
    assert "reopen" not in ACTIONS_BY_STATUS[status]


def test_a_phase_with_nothing_in_the_plan_offers_no_reopen_either():
    assert allowed_actions("approved", False, None) == ()


def test_an_unknown_status_still_offers_nothing():
    assert allowed_actions("exploded", True, None) == ()


def test_every_phase_the_catalogue_has_gets_the_button_with_no_further_work(world_sync=None):
    """The server's snapshot builds each phase's actions from the one table, so a phase added later is covered. Proven for all seven now."""
    import tempfile

    from app.llm.routing import Routing
    from app.repos import Store
    from app.workflow.definitions import load_catalogue
    from app.workflow.engine import WorkflowEngine

    with tempfile.TemporaryDirectory() as t:
        store = Store.open(t + "/x.db")
        engine = WorkflowEngine(load_catalogue(Routing.load().roles.keys()), store)
        project = store.projects.create(name="P", actor="system")
        engine.open_project(project.id)
        with store.db.write() as conn:
            conn.execute("UPDATE phase_runs SET status = 'approved' WHERE project_id = ?", (project.id,))
        phases = engine.snapshot(project.id).phases
        assert [p.key for p in phases] == ["setup", "requirements", "design", "architecture", "build", "deploy", "handover"]
        assert all(p.allowed_actions == ("reopen",) for p in phases)


# ---- the route --------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def world(make_settings):
    async def build(**settings):
        cfg = make_settings(**{**D.MODELS, "llm_retry_backoff_seconds": 0, "run_max_cost_usd": 0, **settings})
        app = create_app(cfg, provider=D.Scripted())
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=ANN)
        store, engine, runner = app.state.store, app.state.engine, app.state.runner
        project = store.projects.create(name=NAME, brief=BRIEF, actor="system")
        engine.open_project(project.id)
        store.context.add_document(project.id, FILENAME, POLICY, actor="human:demo")
        for phase in ("setup", "requirements"):
            await runner.run_phase(project.id, phase)
            engine.finish(project.id, phase, actor="system"); engine.approve(project.id, phase, actor="human:demo")
        return app, client, project

    return build


def status_of(app, pid, key):
    return next(p.status for p in app.state.engine.snapshot(pid).phases if p.key == key)


async def test_reopening_takes_an_approved_phase_back_to_running_and_records_who_and_why(world):
    app, client, project = await world()
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/reopen", json={"reason": "  The brief   changed after sign-off  "})
    assert response.status_code == 200
    assert response.json() == {"phase": "requirements", "status": "running", "decision": None, "decided_by": None}
    event = next(e for e in app.state.store.audit.list(project.id) if e.action == "phase.reopened")
    assert event.actor == "human:Ann" and event.target_id == "requirements"
    assert event.detail == {"reason": "The brief changed after sign-off", "was_approved_by": "human:demo"}          # tidied, and who had approved it
    await client.aclose()


async def test_the_reopened_phase_can_be_reviewed_edited_and_handed_back_again(world):
    app, client, project = await world()
    assert (await client.post(f"/api/projects/{project.id}/phases/requirements/reopen", json={"reason": "to review again"})).status_code == 200
    state = next(p for p in (await client.get(f"/api/projects/{project.id}")).json()["phases"] if p["key"] == "requirements")
    assert state["status"] == "running" and state["allowed_actions"] == ["run", "rewrite", "finish"]      # the reopened phase has content, so a rewrite is offered
    assert (await client.post(f"/api/projects/{project.id}/phases/requirements/finish")).status_code == 200
    assert status_of(app, project.id, "requirements") == "awaiting_review"
    assert (await client.post(f"/api/projects/{project.id}/phases/requirements/approve")).status_code == 200
    assert status_of(app, project.id, "requirements") == "approved"
    await client.aclose()


async def test_a_phase_that_is_not_approved_cannot_be_reopened_and_the_sentence_says_why(world):
    app, client, project = await world()
    response = await client.post(f"/api/projects/{project.id}/phases/design/reopen", json={"reason": "no"})
    assert response.status_code == 409 and "only an approved phase can be reopened" in response.json()["detail"]
    assert status_of(app, project.id, "design") == "not_started"
    await client.aclose()


@pytest.mark.parametrize("body", [{"reason": ""}, {"reason": "   "}, {"reason": "\n\t "}])
async def test_a_blank_reason_is_refused_and_nothing_changes(world, body):
    app, client, project = await world()
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/reopen", json=body)
    assert response.status_code == 422 and "say why you are reopening" in response.json()["detail"]
    assert status_of(app, project.id, "requirements") == "approved"
    assert not [e for e in app.state.store.audit.list(project.id) if e.action == "phase.reopened"]
    await client.aclose()


@pytest.mark.parametrize("body", [{}, {"reason": 5}, {"reason": "ok", "surprise": 1}, {"reason": "x" * 1001}])
async def test_a_malformed_request_is_refused_and_nothing_changes(world, body):
    app, client, project = await world()
    assert (await client.post(f"/api/projects/{project.id}/phases/requirements/reopen", json=body)).status_code == 422
    assert status_of(app, project.id, "requirements") == "approved"
    await client.aclose()


async def test_a_reason_exactly_at_the_limit_is_accepted(world):
    app, client, project = await world()
    assert (await client.post(f"/api/projects/{project.id}/phases/requirements/reopen", json={"reason": "r" * 1000})).status_code == 200
    await client.aclose()


async def test_reopening_needs_a_name(world):
    app, client, project = await world()
    bare = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    assert (await bare.post(f"/api/projects/{project.id}/phases/requirements/reopen", json={"reason": "x"})).status_code == 400
    assert status_of(app, project.id, "requirements") == "approved"
    await bare.aclose(); await client.aclose()


async def test_an_archived_project_cannot_be_reopened(world):
    app, client, project = await world()
    await client.post(f"/api/projects/{project.id}/archive")
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/reopen", json={"reason": "x"})
    assert response.status_code == 409 and response.json()["detail"] == SENTENCE
    assert status_of(app, project.id, "requirements") == "approved"
    await client.aclose()


@pytest.mark.parametrize("path, status", [("nonsense", 404), ("Bad", 422), ("a%20b", 422), ("x" * 65, 422)])      # unknown = 404; not shaped like a key = 422
async def test_an_unknown_or_malformed_phase_key(world, path, status):
    app, client, project = await world()
    assert (await client.post(f"/api/projects/{project.id}/phases/{path}/reopen", json={"reason": "x"})).status_code == status
    await client.aclose()


async def test_an_unknown_project_is_a_404(world):
    app, client, project = await world()
    assert (await client.post("/api/projects/nope/phases/requirements/reopen", json={"reason": "x"})).status_code == 404
    await client.aclose()


async def test_reopening_one_phase_works_while_another_phase_is_being_written(world):
    """An approved phase has no run of its own, so there is nothing to refuse; this proves the route does not trip over a run on ANOTHER phase."""
    app, client, project = await world()
    started = await client.post(f"/api/projects/{project.id}/phases/design/run", json={})
    assert started.status_code == 202
    run_id = started.json()["run_id"]
    reopened = await client.post(f"/api/projects/{project.id}/phases/requirements/reopen", json={"reason": "while design runs"})
    assert reopened.status_code == 200 and status_of(app, project.id, "requirements") == "running"
    for _ in range(600):
        if app.state.store.runs.get(project.id, run_id).status != "running":
            break
        await asyncio.sleep(0.02)
    await client.aclose()


# ---- what reopening leaves alone -----------------------------------------------------------------------------------------------------------

async def test_reopening_changes_nothing_after_it_but_every_later_phase_shows_it_stands_on_a_reopened_one(world):
    app, client, project = await world()
    await app.state.runner.run_phase(project.id, "design")
    app.state.engine.finish(project.id, "design", actor="system"); app.state.engine.approve(project.id, "design", actor="human:demo")
    before = {p["key"]: (p["status"], p["decision"], p["decided_by"]) for p in (await client.get(f"/api/projects/{project.id}")).json()["phases"]}
    await client.post(f"/api/projects/{project.id}/phases/setup/reopen", json={"reason": "the charter was wrong"})
    after = {p["key"]: p for p in (await client.get(f"/api/projects/{project.id}")).json()["phases"]}
    for key in ("requirements", "design"):
        assert (after[key]["status"], after[key]["decision"], after[key]["decided_by"]) == before[key]       # still approved, by the same person, untouched
        assert after[key]["needs_review"] is True and after[key]["allowed_actions"] == ["reopen"]
        assert after[key]["blocked_by"] == "Setup"
    assert after["setup"]["status"] == "running" and after["setup"]["needs_review"] is False
    assert after["architecture"]["allowed_actions"] == []                      # a phase that never started stays blocked behind the reopened one
    await client.aclose()


async def test_the_flag_clears_when_the_reopened_phase_is_approved_again(world):
    app, client, project = await world()
    await client.post(f"/api/projects/{project.id}/phases/setup/reopen", json={"reason": "again"})
    requirements = lambda: next(p for p in app.state.engine.snapshot(project.id).phases if p.key == "requirements")      # noqa: E731
    assert requirements().needs_review is True
    await client.post(f"/api/projects/{project.id}/phases/setup/finish")
    await client.post(f"/api/projects/{project.id}/phases/setup/approve")
    assert requirements().needs_review is True          # it still stands on a Setup that changed AFTER it was approved: that is the point of the flag
    await client.post(f"/api/projects/{project.id}/phases/requirements/reopen", json={"reason": "checked it"})
    await client.post(f"/api/projects/{project.id}/phases/requirements/finish")
    await client.post(f"/api/projects/{project.id}/phases/requirements/approve")
    assert requirements().needs_review is False         # approving it again, after the change, is what clears it
    await client.aclose()


async def test_reopening_removes_the_phases_artefacts_from_the_search_until_it_is_approved_again(world):
    app, client, project = await world()
    before = (await client.get(f"/api/projects/{project.id}/search", params={"q": "personas"})).json()["hits"]
    assert any(h["kind"] == "artefact" for h in before), "precondition: approved artefacts are searchable"
    await client.post(f"/api/projects/{project.id}/phases/requirements/reopen", json={"reason": "reviewing"})
    during = (await client.get(f"/api/projects/{project.id}/search", params={"q": "personas"})).json()["hits"]
    assert not [h for h in during if h["kind"] == "artefact" and h["phase_key"] == "requirements"]
    await client.aclose()


async def test_reopening_twice_in_a_row_is_refused_the_second_time(world):
    app, client, project = await world()
    assert (await client.post(f"/api/projects/{project.id}/phases/requirements/reopen", json={"reason": "first"})).status_code == 200
    again = await client.post(f"/api/projects/{project.id}/phases/requirements/reopen", json={"reason": "second"})
    assert again.status_code == 409 and "only an approved phase can be reopened" in again.json()["detail"]
    assert len([e for e in app.state.store.audit.list(project.id) if e.action == "phase.reopened"]) == 1
    await client.aclose()


async def test_the_audit_trail_keeps_every_reopen_with_its_own_reason(world):
    app, client, project = await world()
    for reason in ("first reason", "second reason"):
        await client.post(f"/api/projects/{project.id}/phases/requirements/reopen", json={"reason": reason})
        await client.post(f"/api/projects/{project.id}/phases/requirements/finish")
        await client.post(f"/api/projects/{project.id}/phases/requirements/approve")
    reasons = [e.detail["reason"] for e in app.state.store.audit.list(project.id) if e.action == "phase.reopened"]
    assert reasons == ["first reason", "second reason"]
    await client.aclose()


async def test_a_response_never_contains_a_path_or_a_key(world):
    app, client, project = await world()
    text = (await client.post(f"/api/projects/{project.id}/phases/requirements/reopen", json={"reason": "x"})).text
    for forbidden in ("/Users", ".db", "Traceback", "sk-"):
        assert forbidden not in text
    await client.aclose()
