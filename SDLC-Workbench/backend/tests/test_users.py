"""S23a: users, their roles and which roles may approve which phase. Nothing is enforced at approval yet (23b). No model, no network."""
from __future__ import annotations

import sqlite3

import httpx
import pytest
from fastapi import FastAPI

from app.access import roles as R
from app.db import MIGRATIONS, Database
from app.models import ConflictError, InvalidInput, NotFoundError
from app.repos import Store
from app.routes_users import router

pytestmark = pytest.mark.anyio
ANN = {"X-Actor": "Ann"}


# ---- the rules, as pure functions ------------------------------------------------------------------------------------------------------------------

def test_there_are_seven_roles_in_a_fixed_order_and_administrator_is_one_of_them():
    assert R.ROLES == ("Project Manager", "Architect", "Business Engineer", "Technical Lead", "Deployment Engineer", "BAU Lead", "Administrator") and R.ADMIN in R.ROLES


def test_the_default_approver_of_every_phase_is_a_real_role_and_the_three_early_phases_need_an_architect():
    assert set(R.DEFAULT_APPROVERS) == {"setup", "requirements", "design", "architecture", "build", "deploy", "handover"}
    assert all(r in R.ROLES for roles in R.DEFAULT_APPROVERS.values() for r in roles) and all(R.DEFAULT_APPROVERS.values())
    assert [R.DEFAULT_APPROVERS[p] for p in ("setup", "requirements", "design")] == [("Architect",)] * 3
    assert R.DEFAULT_APPROVERS["architecture"] == R.DEFAULT_APPROVERS["build"] == ("Technical Lead",)
    assert R.DEFAULT_APPROVERS["deploy"] == ("Deployment Engineer",) and R.DEFAULT_APPROVERS["handover"] == ("BAU Lead",)


@pytest.mark.parametrize("raw, clean", [("Ann", "Ann"), ("  Ann   Lee ", "Ann Lee"), ("Zoë", "Zoë")])
def test_a_name_is_tidied(raw, clean):
    assert R.clean_name(raw) == clean


@pytest.mark.parametrize("raw", ["", "   ", "x" * 61, "a\x00b", "a\nb", "System", "system", "human:ann", "Agent:x@y"])
def test_a_blank_long_odd_or_reserved_name_is_refused_with_a_sentence(raw):
    with pytest.raises(R.RoleError):
        R.clean_name(raw)


def test_roles_come_back_in_their_fixed_order_once_each_and_an_unknown_one_is_refused_by_name():
    assert R.clean_roles(["Administrator", "Architect", "Architect"]) == ("Architect", "Administrator") and R.clean_roles([]) == ()
    with pytest.raises(R.RoleError, match="unknown role 'Wizard'.*Project Manager"):
        R.clean_roles(["Architect", "Wizard"])


def test_names_match_without_regard_to_case_or_spaces():
    assert R.same_person("ann lee", " Ann  LEE") and not R.same_person("Ann", "Anna")


# ---- the migration ---------------------------------------------------------------------------------------------------------------------------------

def test_the_migration_adds_three_tables_and_a_database_at_v10_upgrades_keeping_its_data(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    for sql in MIGRATIONS[:10]:
        conn.executescript(sql)
    conn.execute("PRAGMA user_version = 10")
    conn.commit(); conn.close()
    assert len(MIGRATIONS) == 11 and Database(path).migrate() == 11
    names = {r[0] for r in sqlite3.connect(path).execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "user_roles", "phase_approvers"} <= names


def test_a_person_can_never_be_deleted_from_the_database(store):
    store.users.add("Ann", ["Architect"], actor="human:Root")
    raw = sqlite3.connect(store.db.path)
    with pytest.raises(sqlite3.DatabaseError, match="switched off, never deleted"):
        raw.execute("DELETE FROM users")
    raw.close()


# ---- the list --------------------------------------------------------------------------------------------------------------------------------------

def test_a_person_is_added_with_several_roles_in_a_fixed_order_and_the_change_is_audited(store):
    u = store.users.add("  Ann  Lee ", ["Technical Lead", "Architect"], actor="human:Root")
    assert (u.name, u.active, u.roles, u.created_by) == ("Ann Lee", True, ("Architect", "Technical Lead"), "human:Root")
    [event] = [a for a in store.audit.list() if a.action == "user.added"]
    assert event.actor == "human:Root" and event.target_id == "Ann Lee" and event.detail == {"roles": ["Architect", "Technical Lead"]}


def test_a_name_already_on_the_list_is_refused_in_any_case(store):
    store.users.add("Ann", ["Architect"], actor="human:Root")
    for again in ("Ann", "ann", " ANN "):
        with pytest.raises(ConflictError, match="Ann is already on the list"):
            store.users.add(again, [], actor="human:Root")
    assert len(store.users.list()) == 1


def test_a_bad_name_an_unknown_role_and_a_bad_actor_are_refused_and_nothing_is_saved(store):
    for name, roles, actor in (("", [], "human:Root"), ("Ann", ["Wizard"], "human:Root"), ("Ann", [], "nobody")):
        with pytest.raises(InvalidInput):
            store.users.add(name, roles, actor=actor)
    assert store.users.list() == [] and not [a for a in store.audit.list() if a.action.startswith("user.")]


def test_find_matches_a_name_in_any_case_and_an_unknown_name_is_none(store):
    store.users.add("Ann Lee", [], actor="human:Root")
    assert store.users.find("ann  lee").name == "Ann Lee" and store.users.find("Bob") is None and store.users.find("") is None


def test_roles_are_replaced_audited_with_before_and_after_and_an_unknown_person_is_not_found(store):
    store.users.add("Ann", ["Architect"], actor="human:Root")
    store.users.add("Root", ["Administrator"], actor="human:Root")
    after = store.users.set_roles("ann", ["Technical Lead", "BAU Lead"], actor="human:Root")
    assert after.roles == ("Technical Lead", "BAU Lead")
    ev = [a for a in store.audit.list() if a.action == "user.roles_changed"][-1]
    assert ev.detail == {"before": ["Architect"], "after": ["Technical Lead", "BAU Lead"]}
    with pytest.raises(NotFoundError, match="'Bob' is not on the list"):
        store.users.set_roles("Bob", [], actor="human:Root")
    with pytest.raises(InvalidInput):
        store.users.set_roles("Ann", ["Wizard"], actor="human:Root")
    assert store.users.find("Ann").roles == ("Technical Lead", "BAU Lead")


def test_the_last_administrator_can_be_neither_demoted_nor_switched_off_but_another_can(store):
    store.users.add("Root", ["Administrator"], actor="human:Root")
    with pytest.raises(ConflictError, match="last Administrator"):
        store.users.set_roles("Root", ["Architect"], actor="human:Root")
    with pytest.raises(ConflictError, match="last Administrator"):
        store.users.set_active("Root", False, actor="human:Root")
    store.users.add("Zed", ["Administrator"], actor="human:Root")
    store.users.set_roles("Root", ["Architect"], actor="human:Root")                        # Zed is still an Administrator
    with pytest.raises(ConflictError, match="last Administrator"):
        store.users.set_active("Zed", False, actor="human:Root")
    assert store.users.find("Zed").active and store.users.find("Root").roles == ("Architect",)


def test_a_switched_off_administrator_does_not_count_as_one(store):
    store.users.add("Root", ["Administrator"], actor="human:Root")
    store.users.add("Zed", ["Administrator"], actor="human:Root")
    store.users.set_active("Zed", False, actor="human:Root")
    with pytest.raises(ConflictError, match="last Administrator"):
        store.users.set_roles("Root", [], actor="human:Root")


def test_a_person_is_switched_off_and_on_never_deleted_and_adding_them_again_switches_them_on_with_the_new_roles(store):
    store.users.add("Root", ["Administrator"], actor="human:Root")
    store.users.add("Ann", ["Architect"], actor="human:Root")
    off = store.users.set_active("Ann", False, actor="human:Root")
    assert not off.active and off.roles == ("Architect",) and store.users.count_active() == 1 and len(store.users.list()) == 2
    back = store.users.add("ann", ["BAU Lead"], actor="human:Root")
    assert back.active and back.roles == ("BAU Lead",) and back.name == "Ann" and len(store.users.list()) == 2          # the first spelling is kept
    assert [a.action for a in store.audit.list() if a.target_id in ("Ann",)] == ["user.added", "user.switched_off", "user.reactivated"]


def test_the_list_is_in_name_order_and_counts_only_the_active(store):
    for n in ("Cy", "Ann", "Bo"):
        store.users.add(n, [], actor="human:Root")
    store.users.set_active("Bo", False, actor="human:Root")
    assert [u.name for u in store.users.list()] == ["Ann", "Bo", "Cy"] and store.users.count_active() == 2


# ---- the first administrator -----------------------------------------------------------------------------------------------------------------------

def test_the_first_administrator_gets_every_role_and_is_made_by_the_system(store):
    u = store.users.seed_admin("Parag")
    assert u.roles == R.ROLES and u.created_by == "system"


def test_seeding_does_nothing_when_the_name_is_blank_or_anyone_is_already_on_the_list(store):
    assert store.users.seed_admin("") is None and store.users.seed_admin("   ") is None and store.users.list() == []
    store.users.add("Ann", [], actor="human:Root")
    assert store.users.seed_admin("Parag") is None and [u.name for u in store.users.list()] == ["Ann"]


def test_seeding_twice_adds_nobody_new(store):
    store.users.seed_admin("Parag"); store.users.seed_admin("Parag"); store.users.seed_admin("Other")
    assert [u.name for u in store.users.list()] == ["Parag"]


def test_a_switched_off_only_user_still_counts_as_a_list_so_seeding_does_not_add_a_second_administrator(store):
    store.users.seed_admin("Parag")
    store.users.add("Zed", ["Administrator"], actor="human:Parag"); store.users.set_active("Parag", False, actor="human:Parag")
    assert store.users.seed_admin("Parag") is None and store.users.count_active() == 1


# ---- who may approve which phase -------------------------------------------------------------------------------------------------------------------

def test_with_nothing_saved_every_phase_has_its_default_approvers(store):
    assert store.users.approvers() == R.DEFAULT_APPROVERS


def test_the_approvers_of_a_phase_can_be_changed_audited_and_only_that_phase_changes(store):
    got = store.users.set_approvers("requirements", ["Technical Lead", "Architect"], actor="human:Root")
    assert got == ("Architect", "Technical Lead") and store.users.approvers()["requirements"] == ("Architect", "Technical Lead")
    assert store.users.approvers()["design"] == ("Architect",)
    ev = [a for a in store.audit.list() if a.action == "phase.approvers_changed"][-1]
    assert ev.target_id == "requirements" and ev.detail == {"before": ["Architect"], "after": ["Architect", "Technical Lead"]}


def test_changing_one_phase_leaves_every_other_phase_as_it_was(store):
    store.users.set_approvers("deploy", ["BAU Lead"], actor="human:Root"); store.users.set_approvers("build", ["Architect"], actor="human:Root")
    store.users.set_approvers("deploy", ["Technical Lead"], actor="human:Root")
    got = store.users.approvers()
    assert got["deploy"] == ("Technical Lead",) and got["build"] == ("Architect",)                               # the second save of deploy did not undo build
    assert got["requirements"] == R.DEFAULT_APPROVERS["requirements"]


def test_a_blank_name_is_refused_by_the_list_with_the_sentence_a_name_is_needed(store):
    for blank in ("", "   ", "\t"):
        with pytest.raises(InvalidInput, match="a name is needed|characters that are not allowed"):
            store.users.add(blank, [], actor="human:Root")
    with pytest.raises(R.RoleError, match="^a name is needed$"):
        R.clean_name("    ")


def test_a_phase_must_keep_at_least_one_approving_role_and_an_unknown_phase_or_role_is_refused(store):
    with pytest.raises(InvalidInput, match="at least one role"):
        store.users.set_approvers("requirements", [], actor="human:Root")
    with pytest.raises(NotFoundError, match="there is no phase 'nope'"):
        store.users.set_approvers("nope", ["Architect"], actor="human:Root")
    with pytest.raises(InvalidInput, match="unknown role"):
        store.users.set_approvers("requirements", ["Wizard"], actor="human:Root")
    assert store.users.approvers() == R.DEFAULT_APPROVERS


def test_saving_a_phase_again_replaces_its_roles(store):
    store.users.set_approvers("deploy", ["BAU Lead"], actor="human:Root"); store.users.set_approvers("deploy", ["Architect"], actor="human:Root")
    assert store.users.approvers()["deploy"] == ("Architect",)


# ---- over HTTP -------------------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def api(store):
    app = FastAPI(); app.include_router(router); app.state.store = store
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def h(name):
    return {"X-Actor": name}


async def test_reading_the_list_needs_no_name_and_says_a_name_is_a_label_not_a_password(api):
    body = (await api.get("/api/users")).json()
    assert body["roles"] == list(R.ROLES) and body["users"] == [] and body["empty"] is True and "not a password" in body["note"] and "ADMIN_NAME" in body["empty_hint"]
    assert body["approvers"] == {p: list(r) for p, r in R.DEFAULT_APPROVERS.items()} == body["defaults"]
    await api.aclose()


async def test_while_the_list_is_empty_anyone_with_a_name_can_add_the_first_person_but_a_request_without_a_name_cannot(api):
    assert (await api.post("/api/users", json={"name": "Root", "roles": ["Administrator"]})).status_code == 400
    made = await api.post("/api/users", json={"name": "Root", "roles": ["Administrator"]}, headers=h("Someone"))
    assert made.status_code == 201 and made.json()["roles"] == ["Administrator"] and made.json()["created_by"] == "Someone"
    assert (await api.get("/api/users")).json()["empty"] is False
    await api.aclose()


async def test_once_someone_is_on_the_list_only_an_active_administrator_can_change_it(api, store):
    store.users.add("Root", ["Administrator"], actor="human:x"); store.users.add("Ann", ["Architect"], actor="human:x"); store.users.add("Off", ["Administrator"], actor="human:x")
    store.users.set_active("Off", False, actor="human:Root")
    for who in ("Ann", "Stranger", "Off"):
        r = await api.post("/api/users", json={"name": "New", "roles": []}, headers=h(who))
        assert r.status_code == 403 and "only an Administrator" in r.json()["detail"], who
    assert (await api.post("/api/users", json={"name": "New", "roles": []}, headers=h("root"))).status_code == 201
    assert [u.name for u in store.users.list()].count("New") == 1
    await api.aclose()


async def test_every_change_route_is_closed_to_a_non_administrator_and_open_to_one(api, store):
    store.users.add("Root", ["Administrator"], actor="human:x"); store.users.add("Ann", ["Architect"], actor="human:x")
    calls = [("PUT", "/api/users/Ann/roles", {"roles": ["BAU Lead"]}), ("PUT", "/api/users/Ann/active", {"active": False}), ("PUT", "/api/approvers/deploy", {"roles": ["Architect"]})]
    for method, url, body in calls:
        assert (await api.request(method, url, json=body, headers=h("Ann"))).status_code == 403, url
    assert store.users.find("Ann").roles == ("Architect",) and store.users.find("Ann").active and store.users.approvers()["deploy"] == ("Deployment Engineer",)
    for method, url, body in calls:
        assert (await api.request(method, url, json=body, headers=h("Root"))).status_code == 200, url
    await api.aclose()


async def test_the_routes_answer_a_refusal_in_a_plain_sentence_with_the_right_status(api, store):
    store.users.add("Root", ["Administrator"], actor="human:x")
    r = await api.post("/api/users", json={"name": "Root", "roles": []}, headers=h("Root"))
    assert r.status_code == 409 and "already on the list" in r.json()["detail"]
    r = await api.post("/api/users", json={"name": "Bo", "roles": ["Wizard"]}, headers=h("Root"))
    assert r.status_code == 422 and "unknown role 'Wizard'" in r.json()["detail"]
    r = await api.put("/api/users/Nobody/roles", json={"roles": []}, headers=h("Root"))
    assert r.status_code == 404 and "not on the list" in r.json()["detail"]
    r = await api.put("/api/users/Root/roles", json={"roles": ["Architect"]}, headers=h("Root"))
    assert r.status_code == 409 and "last Administrator" in r.json()["detail"]
    r = await api.put("/api/approvers/nope", json={"roles": ["Architect"]}, headers=h("Root"))
    assert r.status_code == 404
    r = await api.put("/api/approvers/deploy", json={"roles": []}, headers=h("Root"))
    assert r.status_code == 422 and "at least one role" in r.json()["detail"]
    await api.aclose()


async def test_a_request_with_an_unexpected_field_or_too_many_roles_is_refused_at_the_edge(api, store):
    store.users.add("Root", ["Administrator"], actor="human:x")
    assert (await api.post("/api/users", json={"name": "Bo", "extra": 1}, headers=h("Root"))).status_code == 422
    assert (await api.post("/api/users", json={"name": "Bo", "roles": list(R.ROLES) + ["x"]}, headers=h("Root"))).status_code == 422
    assert (await api.post("/api/users", json={"name": "", "roles": []}, headers=h("Root"))).status_code == 422
    await api.aclose()


async def test_who_am_i_says_whether_the_typed_name_is_on_the_list_its_roles_and_the_phases_it_may_approve(api, store):
    me = (await api.get("/api/users/me", headers=h("Ann"))).json()
    assert me["on_list"] is False and me["list_in_force"] is False and me["may_approve"] == list(R.DEFAULT_APPROVERS)        # nobody on the list: nothing is restricted
    store.users.add("Root", ["Administrator"], actor="human:x"); store.users.add("Ann", ["Architect", "BAU Lead"], actor="human:x")
    ann = (await api.get("/api/users/me", headers=h("ann"))).json()
    assert ann["on_list"] and ann["roles"] == ["Architect", "BAU Lead"] and ann["administrator"] is False and ann["list_in_force"]
    assert ann["may_approve"] == ["setup", "requirements", "design", "handover"]
    stranger = (await api.get("/api/users/me", headers=h("Stranger"))).json()
    assert stranger["on_list"] is False and stranger["roles"] == [] and stranger["may_approve"] == [] and stranger["list_in_force"]
    root = (await api.get("/api/users/me", headers=h("Root"))).json()
    assert root["administrator"] and root["may_approve"] == []                                                                  # only the Administrator role, which approves no phase by default
    assert (await api.get("/api/users/me")).status_code == 400
    await api.aclose()


async def test_who_am_i_gives_the_reason_for_every_phase_that_cannot_be_approved_in_the_words_the_refusal_would_use(api, store):
    store.users.add("Root", ["Administrator"], actor="human:x"); store.users.add("Bo", ["Project Manager"], actor="human:x")
    bo = (await api.get("/api/users/me", headers=h("Bo"))).json()
    assert bo["may_approve"] == [] and set(bo["why_not"]) == set(R.DEFAULT_APPROVERS)
    assert bo["why_not"]["requirements"] == "requirements can be approved only by an Architect; Bo holds Project Manager"            # a bare app has no catalogue, so the key stands for the name
    assert bo["why_not"]["deploy"] == "deploy can be approved only by a Deployment Engineer; Bo holds Project Manager"
    stranger = (await api.get("/api/users/me", headers=h("Stranger"))).json()
    assert "Stranger is not on the Users list; ask an Administrator to add you" in stranger["why_not"]["setup"]
    store.users.add("Ann", ["Architect"], actor="human:x")
    ann = (await api.get("/api/users/me", headers=h("Ann"))).json()
    assert set(ann["why_not"]) == {"architecture", "build", "deploy", "handover"} and "setup" not in ann["why_not"]
    await api.aclose()


async def test_with_nobody_on_the_list_there_is_nothing_to_explain(api):
    assert (await api.get("/api/users/me", headers=h("Ann"))).json()["why_not"] == {}
    await api.aclose()


async def test_a_switched_off_person_is_treated_as_not_on_the_list(api, store):
    store.users.add("Root", ["Administrator"], actor="human:x"); store.users.add("Ann", ["Architect"], actor="human:x"); store.users.set_active("Ann", False, actor="human:Root")
    me = (await api.get("/api/users/me", headers=h("Ann"))).json()
    assert me["on_list"] is False and me["roles"] == [] and me["may_approve"] == []
    await api.aclose()


async def test_the_payload_never_holds_a_secret_or_a_path_and_names_are_returned_as_stored(api, store):
    store.users.add("Ann Lee", ["Architect"], actor="human:x")
    text = (await api.get("/api/users")).text
    assert "Ann Lee" in text and "/Users" not in text and ".env" not in text.replace("backend/.env", "")
    await api.aclose()


# ---- start-up ----------------------------------------------------------------------------------------------------------------------------------------

def test_the_app_seeds_the_first_administrator_from_admin_name_at_start_up_and_not_twice(make_settings):
    from fastapi.testclient import TestClient
    from app.main import create_app
    cfg = make_settings(admin_name="Parag")
    first = create_app(cfg)
    assert [(u.name, u.roles == R.ROLES) for u in first.state.store.users.list()] == [("Parag", True)]
    again = create_app(cfg)
    assert [u.name for u in again.state.store.users.list()] == ["Parag"]
    assert TestClient(again).get("/api/users").json()["users"][0]["name"] == "Parag"


def test_a_blank_admin_name_seeds_nobody_and_a_bad_one_stops_start_up_with_a_sentence(make_settings):
    from app.main import create_app
    assert create_app(make_settings(admin_name="")).state.store.users.list() == []
    with pytest.raises(SystemExit, match="ADMIN_NAME in backend/.env cannot be used"):
        create_app(make_settings(admin_name="System"))


def test_admin_name_is_documented_in_the_example_file_and_blank_by_default():
    from app.config import Settings
    assert Settings(_env_file=None).admin_name == ""
    assert "\nADMIN_NAME=\n" in open(".env.example", encoding="utf-8").read()
