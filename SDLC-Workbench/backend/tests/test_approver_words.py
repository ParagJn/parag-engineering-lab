"""S23: who a phase says approves it follows the configured roles, not the fixed label in the phase definition. The user saw 'approved by the business engineer' after an Architect approved."""
from __future__ import annotations

import httpx
import pytest

from app.access.roles import DEFAULT_APPROVERS, ROLES
from app.access.who import approver_label, approvers_in_words, role_words
from app.main import create_app

pytestmark = pytest.mark.anyio


def test_a_role_reads_in_lower_case_inside_a_sentence_but_an_acronym_keeps_its_capitals():
    assert [role_words(r) for r in ROLES] == ["project manager", "architect", "business engineer", "technical lead", "deployment engineer", "BAU lead", "administrator"]


@pytest.mark.parametrize("roles, words", [
    ((), ""), (("Architect",), "architect"), (("Architect", "Technical Lead"), "architect or technical lead"),
    (("Architect", "Technical Lead", "BAU Lead"), "architect, technical lead or BAU lead"),
    (("Project Manager", "Architect", "Business Engineer", "BAU Lead"), "project manager, architect, business engineer or BAU lead"),
])
def test_several_roles_are_joined_with_commas_and_a_final_or(roles, words):
    assert approvers_in_words(roles) == words


def test_the_label_follows_the_configured_roles_and_falls_back_to_the_definitions_when_none_are_configured():
    assert approver_label("setup", "business engineer", {"setup": ("Architect",)}) == "architect"
    assert approver_label("setup", "business engineer", {"setup": ()}) == "business engineer"
    assert approver_label("setup", "business engineer", {"design": ("Architect",)}) == "business engineer"
    assert approver_label("setup", "business engineer", {}) == approver_label("setup", "business engineer", None) == "business engineer"


@pytest.fixture
def world(make_settings):
    app = create_app(make_settings(admin_name="Root"))
    project = app.state.store.projects.create(name="P", actor="system")
    app.state.engine.open_project(project.id)
    return app, project


def approver_of(app, project, phase):
    return next(p.approver for p in app.state.engine.snapshot(project.id).phases if p.key == phase)


def test_every_phase_names_the_roles_that_approve_it_by_default_and_not_the_old_labels(world):
    app, project = world
    got = {p.key: p.approver for p in app.state.engine.snapshot(project.id).phases}
    assert got == {"setup": "architect", "requirements": "architect", "design": "architect", "architecture": "technical lead", "build": "technical lead", "deploy": "deployment engineer", "handover": "BAU lead"}
    assert "business engineer" not in got.values() and "deployment engineer" in got.values()               # Deploy's old label happens to match its role; the rest were different


def test_changing_who_approves_a_phase_changes_what_the_page_says_at_once(world):
    app, project = world
    app.state.store.users.set_approvers("requirements", ["Architect", "Technical Lead"], actor="human:Root")
    assert approver_of(app, project, "requirements") == "architect or technical lead" and approver_of(app, project, "design") == "architect"


async def test_the_project_answer_carries_the_configured_words_and_the_waiting_sentence_uses_them(world):
    app, project = world
    store = app.state.store
    store.phases.ensure(project.id, "setup", actor="system"); store.phases.set_status(project.id, "setup", "running", actor="system")
    store.phases.set_status(project.id, "setup", "awaiting_review", actor="system")                    # next_action reports the first phase not yet approved
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"X-Actor": "Root"})
    body = (await c.get(f"/api/projects/{project.id}")).json()
    assert next(p for p in body["phases"] if p["key"] == "setup")["approver"] == "architect"
    assert body["next_action"] == "Setup is awaiting review by the architect"
    store.users.set_approvers("setup", ["Technical Lead", "BAU Lead"], actor="human:Root")
    assert (await c.get(f"/api/projects/{project.id}")).json()["next_action"] == "Setup is awaiting review by the technical lead or BAU lead"
    await c.aclose()


def test_the_plan_preview_before_a_project_exists_still_shows_the_definitions_label(make_settings):
    from fastapi.testclient import TestClient
    app = create_app(make_settings())
    plan = TestClient(app).post("/api/plan/preview", json={"selection": {}}).json()
    assert {p["key"]: p["approver"] for p in plan["phases"]}["setup"] == "business engineer"             # a plan is not a project: nobody has configured anything for it
