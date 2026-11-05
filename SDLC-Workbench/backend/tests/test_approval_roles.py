"""S23b: a phase can be approved or sent back only by a person who holds a role that may do it. While nobody is on the Users list nothing is restricted. No model, no network.

The phases are put into 'awaiting_review' directly, so the test is about WHO may decide, not about writing documents."""
from __future__ import annotations

import httpx
import pytest

from app.access import roles as R
from app.main import create_app
from app.review.errors import NotAnApprover, PersonRequired

pytestmark = pytest.mark.anyio


@pytest.fixture
def world(make_settings):
    def build(**settings):
        app = create_app(make_settings(**settings))
        store, engine = app.state.store, app.state.engine
        project = store.projects.create(name="P", actor="system")
        engine.open_project(project.id)
        return app, store, project

    return build


def review(store, project, phase):
    """Put one phase into awaiting_review, with every required artefact given a version so approval's own guard is satisfied."""
    store.phases.ensure(project.id, phase, actor="system")
    store.phases.set_status(project.id, phase, "running", actor="system")
    for item in store_catalogue(store).phase(phase).artefacts:
        if item.required and item.enabled and not item.by_hand:
            art = store.artefacts.create(project.id, artefact_type=item.key, phase_key=phase, title=item.name, actor="system", prefix=item.id_prefix)
            store.artefacts.add_version(project.id, art.id, body="x", author="human:seed")
    store.phases.set_status(project.id, phase, "awaiting_review", actor="system")


def store_catalogue(store):
    from app.llm.routing import Routing
    from app.workflow.definitions import load_catalogue
    return load_catalogue(Routing.load().roles.keys())


def client(app, name):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"X-Actor": name})


def decision(store, project, phase):
    return [a for a in store.audit.list(project.id) if a.action == "phase.decided" and a.target_id == phase][-1]


# ---- the check itself, as a function -----------------------------------------------------------------------------------------------------------------

def test_an_architect_may_approve_requirements_and_the_role_used_is_named(world):
    app, store, _ = world(admin_name="Root")
    store.users.add("Ann", ["Architect"], actor="human:Root")
    assert app.state.human.approving_role("human:Ann", "requirements", "approved") == "Architect"


def test_a_person_without_the_role_is_refused_with_a_sentence_that_names_the_role_and_what_they_hold(world):
    app, store, _ = world(admin_name="Root")
    store.users.add("Bo", ["Project Manager", "Business Engineer"], actor="human:Root")
    with pytest.raises(NotAnApprover, match=r"^Requirements can be approved only by an Architect; Bo holds Project Manager, Business Engineer$"):
        app.state.human.approving_role("human:Bo", "requirements")
    store.users.add("Cy", [], actor="human:Root")
    with pytest.raises(NotAnApprover, match="Cy holds no role"):
        app.state.human.approving_role("human:Cy", "requirements", "approved")


def test_a_name_that_is_not_on_the_list_or_is_switched_off_is_told_to_ask_an_administrator(world):
    app, store, _ = world(admin_name="Root")
    store.users.add("Ann", ["Architect"], actor="human:Root"); store.users.set_active("Ann", False, actor="human:Root")
    for who in ("Stranger", "Ann"):
        with pytest.raises(NotAnApprover, match=rf"{who} is not on the Users list; ask an Administrator to add you"):
            app.state.human.approving_role(f"human:{who}", "requirements", "approved")


def test_each_phase_wants_its_own_role(world):
    app, store, _ = world(admin_name="Root")
    for name, role in (("Ann", "Architect"), ("Tom", "Technical Lead"), ("Dee", "Deployment Engineer"), ("Bea", "BAU Lead")):
        store.users.add(name, [role], actor="human:Root")
    ok = {"setup": "Ann", "requirements": "Ann", "design": "Ann", "architecture": "Tom", "build": "Tom", "deploy": "Dee", "handover": "Bea"}
    for phase, who in ok.items():
        assert app.state.human.approving_role(f"human:{who}", phase, "approved") is not None, phase
        others = [n for n in ("Ann", "Tom", "Dee", "Bea") if n != who]
        for other in others:
            with pytest.raises(NotAnApprover):
                app.state.human.approving_role(f"human:{other}", phase, "approved")


def test_the_administrator_role_alone_does_not_approve_but_the_seeded_one_holds_every_role_and_does(world):
    app, store, _ = world(admin_name="Root")
    store.users.add("Ad", ["Administrator"], actor="human:Root")
    with pytest.raises(NotAnApprover):
        app.state.human.approving_role("human:Ad", "requirements", "approved")
    assert app.state.human.approving_role("human:Root", "requirements", "approved") == "Architect"            # the first allowed role in the fixed order


def test_changing_who_may_approve_changes_the_answer_at_once(world):
    app, store, _ = world(admin_name="Root")
    store.users.add("Tom", ["Technical Lead"], actor="human:Root")
    with pytest.raises(NotAnApprover):
        app.state.human.approving_role("human:Tom", "requirements", "approved")
    store.users.set_approvers("requirements", ["Architect", "Technical Lead"], actor="human:Root")
    assert app.state.human.approving_role("human:Tom", "requirements", "approved") == "Technical Lead"


def test_a_person_with_two_allowed_roles_is_recorded_under_the_first_in_the_fixed_order(world):
    app, store, _ = world(admin_name="Root")
    store.users.add("Mix", ["Technical Lead", "Architect"], actor="human:Root")
    store.users.set_approvers("design", ["Technical Lead", "Architect"], actor="human:Root")
    assert app.state.human.approving_role("human:Mix", "design", "approved") == "Architect"


def test_while_nobody_is_on_the_list_nothing_is_restricted_and_no_role_is_recorded(world):
    app, store, _ = world()
    assert store.users.count_active() == 0
    assert app.state.human.approving_role("human:Anyone", "requirements", "approved") is None


def test_a_list_where_everyone_is_switched_off_is_not_in_force_so_the_app_cannot_be_locked(world):
    app, store, _ = world(admin_name="Root")
    store.users.add("Zed", ["Administrator"], actor="human:Root"); store.users.set_active("Root", False, actor="human:Zed")
    store.users.set_roles("Zed", ["Administrator"], actor="human:Root")
    with pytest.raises(Exception):
        store.users.set_active("Zed", False, actor="human:Root")                              # the last administrator cannot be switched off, so the list always has one
    assert store.users.count_active() == 1


def test_an_agent_or_the_system_can_never_approve_whatever_the_list_says(world):
    app, store, project = world()
    review(store, project, "setup")
    for actor in ("system", "agent:r@m"):
        with pytest.raises(PersonRequired):
            app.state.human.approve(project.id, "setup", actor=actor)


# ---- approving, over HTTP ---------------------------------------------------------------------------------------------------------------------------

async def test_the_wrong_person_gets_403_with_the_sentence_and_the_phase_stays_awaiting_review(world):
    app, store, project = world(admin_name="Root")
    store.users.add("Bo", ["Project Manager"], actor="human:Root")
    review(store, project, "setup")
    c = client(app, "Bo")
    r = await c.post(f"/api/projects/{project.id}/phases/setup/approve")
    assert r.status_code == 403 and r.json()["detail"] == "Setup can be approved only by an Architect; Bo holds Project Manager"
    assert store.phases.get(project.id, "setup").status == "awaiting_review"
    assert not [a for a in store.audit.list(project.id) if a.action == "phase.decided"]
    await c.aclose()


async def test_the_right_person_approves_and_the_audit_row_records_the_role_and_what_was_open(world):
    app, store, project = world(admin_name="Root")
    store.users.add("Ann", ["Architect"], actor="human:Root")
    review(store, project, "setup")
    c = client(app, "ann")
    r = await c.post(f"/api/projects/{project.id}/phases/setup/approve")
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["decided_by"] == "human:ann"
    detail = decision(store, project, "setup").detail
    assert detail["decision"] == "approve" and detail["approved_as"] == "Architect" and "open_high_findings" in detail
    await c.aclose()


async def test_a_stranger_is_told_to_ask_an_administrator_and_a_listed_person_with_the_wrong_role_is_told_what_they_hold(world):
    app, store, project = world(admin_name="Root")
    review(store, project, "setup")
    c = client(app, "Stranger")
    r = await c.post(f"/api/projects/{project.id}/phases/setup/approve")
    assert r.status_code == 403 and "Stranger is not on the Users list; ask an Administrator to add you" in r.json()["detail"]
    await c.aclose()


async def test_with_nobody_on_the_list_anyone_with_a_name_approves_as_before_and_no_role_is_recorded(world):
    app, store, project = world()
    review(store, project, "setup")
    c = client(app, "Whoever")
    assert (await c.post(f"/api/projects/{project.id}/phases/setup/approve")).status_code == 200
    assert "approved_as" not in decision(store, project, "setup").detail
    await c.aclose()


async def test_an_unknown_state_is_still_a_409_and_a_missing_name_still_a_400_the_role_check_changes_neither(world):
    app, store, project = world(admin_name="Root")
    store.users.add("Ann", ["Architect"], actor="human:Root")
    c = client(app, "Ann")
    r = await c.post(f"/api/projects/{project.id}/phases/setup/approve")                       # setup has not been finished
    assert r.status_code == 409
    bare = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    assert (await bare.post(f"/api/projects/{project.id}/phases/setup/approve")).status_code == 400
    await c.aclose(); await bare.aclose()


# ---- sending a phase back -------------------------------------------------------------------------------------------------------------------------

async def test_the_right_person_sends_a_phase_back_and_the_audit_row_records_the_role_it_was_decided_as(world):
    app, store, project = world(admin_name="Root")
    store.users.add("Ann", ["Architect"], actor="human:Root")
    review(store, project, "setup")
    art = store.artefacts.list(project.id, phase_key="setup")[0]
    c = client(app, "ann")
    r = await c.post(f"/api/projects/{project.id}/phases/setup/request-changes", json={"notes": {art.id: "please change this"}})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert decision(store, project, "setup").detail["decided_as"] == "Architect" and decision(store, project, "setup").detail["decision"] == "reject"
    await c.aclose()


async def test_sending_back_with_nobody_on_the_list_records_no_role(world):
    app, store, project = world()
    review(store, project, "setup")
    art = store.artefacts.list(project.id, phase_key="setup")[0]
    c = client(app, "Whoever")
    assert (await c.post(f"/api/projects/{project.id}/phases/setup/request-changes", json={"notes": {art.id: "x"}})).status_code == 200
    assert "decided_as" not in decision(store, project, "setup").detail
    await c.aclose()


def test_the_sentence_says_sent_back_or_approved_as_asked(world):
    app, store, _ = world(admin_name="Root")
    store.users.add("Bo", ["Project Manager"], actor="human:Root")
    with pytest.raises(NotAnApprover, match="can be approved only by"):
        app.state.human.approving_role("human:Bo", "design", "approved")
    with pytest.raises(NotAnApprover, match="can be sent back only by"):
        app.state.human.approving_role("human:Bo", "design", "sent back")
    with pytest.raises(NotAnApprover, match="can be sent back only by .*, and Stranger is not on the Users list"):
        app.state.human.approving_role("human:Stranger", "design", "sent back")


async def test_sending_a_phase_back_needs_the_same_role_and_says_send_back(world):
    app, store, project = world(admin_name="Root")
    store.users.add("Bo", ["Project Manager"], actor="human:Root"); store.users.add("Ann", ["Architect"], actor="human:Root")
    review(store, project, "setup")
    art = store.artefacts.list(project.id, phase_key="setup")[0]
    body = {"notes": {art.id: "please change this"}}
    c = client(app, "Bo")
    r = await c.post(f"/api/projects/{project.id}/phases/setup/request-changes", json=body)
    assert r.status_code == 403 and r.json()["detail"] == "Setup can be sent back only by an Architect; Bo holds Project Manager"
    assert store.phases.get(project.id, "setup").status == "awaiting_review"
    await c.aclose()
