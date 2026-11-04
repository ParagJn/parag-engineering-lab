"""S21: running the Deploy phase through the real runner with a scripted model. The verification is done by hand, so the run writes two artefacts, fails at nothing,
and the phase can be approved with the checklist still open (what was open is recorded)."""
from __future__ import annotations

import httpx
import pytest

from app.main import create_app
from app.sample import BRIEF, FILENAME, NAME, POLICY
from scripts import architecture_demo as A

from .test_deploy_skills import NOTES_ITEMS, NOTES_SECTIONS, PLAN_ITEMS, PLAN_SECTIONS, ok

pytestmark = pytest.mark.anyio
ANN = {"X-Actor": "Ann"}


class Deploy(A.Scripted):
    """The Architecture demo's scripted model (which answers every phase before Deploy), plus the two Deploy documents. It records which artefacts it was asked for."""

    def _which(self, request) -> str:
        text = request.messages[0].content
        for key in ("deployment_plan", "release_notes"):
            if f"({key}) for the project" in text:
                return key
        return super()._which(request)

    async def complete(self, model_id, request):
        key = self._which(request)
        if key == "deployment_plan":
            self.asked.append(key)
            steps = {"Steps": "- DPL-001 Create the data store before anything else. Derives from: COMP-001, COMP-002, COMP-003"}                       # the demo's design has three components
            return ok(PLAN_SECTIONS, {**steps, "Overview": "Written from [COMP-001], not from the code."}, tokens=(2000, 900))
        if key == "release_notes":
            self.asked.append(key)
            return ok(NOTES_SECTIONS, {**NOTES_ITEMS, "Overview": "Written from [DEP-PLN-001]."}, tokens=(2000, 900))
        return await super().complete(model_id, request)


@pytest.fixture
def world(make_settings):
    async def build():
        cfg = make_settings(**{**A.MODELS, "ibm_ica_openai_model_id": "gpt-x", "ibm_ica_openai_fallback_model_id": "m-sonnet", "llm_retry_backoff_seconds": 0, "run_max_cost_usd": 0})          # the DevOps role is the OpenAI slot
        provider = Deploy()
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
        return app, client, provider, project

    return build


async def test_a_deploy_run_writes_the_plan_then_the_notes_and_nothing_fails(world):
    app, client, provider, project = await world()
    result = await app.state.runner.run_phase(project.id, "deploy")
    assert {o.key: o.state for o in result.outcomes} == {"deployment_plan": "done", "release_notes": "done"}
    assert provider.asked[-2:] == ["deployment_plan", "release_notes"] and "deployment_verification" not in provider.asked
    events = [e for e in app.state.store.run_events.list(project.id) if e.run_id == result.run_id]
    assert [e.data["key"] for e in events if e.type == "artefact.finished"] == ["deployment_plan", "release_notes"]
    assert not [e for e in events if e.type in ("artefact.failed", "artefact.skipped")]
    started = next(e for e in events if e.type == "run.started")
    assert started.data["artefacts"] == ["deployment_plan", "release_notes"]
    await client.aclose()


async def test_the_phase_can_be_approved_with_the_checklist_still_open_and_the_approval_records_what_was_open(world):
    app, client, provider, project = await world()
    await app.state.runner.run_phase(project.id, "deploy")
    store = app.state.store
    store.deploy_checks.answer(project.id, "CHK-001", "go", actor="human:ann")
    store.deploy_checks.answer(project.id, "CHK-002", "no_go", actor="human:ann", note="not yet")
    app.state.engine.finish(project.id, "deploy", actor="system")
    response = await client.post(f"/api/projects/{project.id}/phases/deploy/approve")
    assert response.status_code == 200 and response.json()["status"] == "approved"
    detail = store.audit.list(project.id, action="phase.decided")[-1].detail
    assert detail["decision"] == "approve" and detail["deployment_checks"]["no_go"] == ["CHK-002"] and len(detail["deployment_checks"]["unanswered"]) == 14
    assert detail["deployment_checks"]["decision"] is None
    await client.aclose()


async def test_the_verification_never_gets_an_artefact_row_and_the_phase_counts_only_what_a_model_writes(world):
    app, client, provider, project = await world()
    await app.state.runner.run_phase(project.id, "deploy")
    types = {a.type for a in app.state.store.artefacts.list(project.id, phase_key="deploy")}
    assert types == {"deployment_plan", "release_notes"}
    body = (await client.get(f"/api/projects/{project.id}")).json()
    deploy = next(p for p in body["phases"] if p["key"] == "deploy")
    assert [a["key"] for a in deploy["artefacts"]] == ["deployment_plan", "release_notes"] and [b["key"] for b in deploy["by_hand"]] == ["deployment_verification"]
    await client.aclose()
