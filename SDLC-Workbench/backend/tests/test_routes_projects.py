"""The project routes (S12a): preview, create, list, read; the X-Actor rule; allowed actions; and what a response may contain."""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.actor import MAX_NAME_CHARS, actor_from
from app.main import create_app
from app.workflow.engine import ACTIONS_BY_STATUS, allowed_actions
from app.workflow.plan import build_plan

from . import _fakes as F

ACTOR = {"X-Actor": "Parag"}
REQUIRED_REQUIREMENTS = ["personas", "problem_statement", "vision_objectives", "functional_requirements", "non_functional_requirements", "epics_features"]


@pytest.fixture
def client(make_settings):
    app = create_app(make_settings())
    return TestClient(app)


def create(client, **body):
    body.setdefault("name", "Meeting Room Booking")
    return client.post("/api/projects", json=body, headers=ACTOR)


# ---- the catalogue and the mode: facts, not choices ----------------------------------------------------------------------------

def test_the_catalogue_lists_every_phase_and_artefact_the_wizard_can_offer(client):
    body = client.get("/api/catalogue").json()
    assert [p["key"] for p in body["phases"]] == ["setup", "requirements", "design", "architecture", "build", "deploy", "handover"]
    assert sum(len(p["artefacts"]) for p in body["phases"]) == 33
    reqs = next(p for p in body["phases"] if p["key"] == "requirements")
    assert {a["key"]: a["required"] for a in reqs["artefacts"]}["user_stories"] is False
    assert set(reqs["artefacts"][0]) == {"key", "name", "required", "description", "waits_for"}


@pytest.mark.parametrize("mode, fragment", [("replay", "recordings"), ("live", "real models")])
def test_the_mode_is_reported_as_a_fact_about_this_server_with_a_plain_meaning(make_settings, mode, fragment):
    body = TestClient(create_app(make_settings(app_mode=mode))).get("/api/modes").json()
    assert body["mode"] == mode and fragment in body["meaning"]


# ---- plan preview --------------------------------------------------------------------------------------------------------------------

SELECTIONS = [
    {},
    {"requirements": REQUIRED_REQUIREMENTS},
    {"requirements": REQUIRED_REQUIREMENTS + ["user_stories"]},
    {"design": ["user_journey", "lowfi_wireframes"]},
    {"requirements": ["personas", "problem_statement", "vision_objectives", "functional_requirements", "non_functional_requirements", "epics_features"], "design": None},
]


@pytest.mark.parametrize("selection", SELECTIONS)
def test_the_preview_equals_what_build_plan_makes_of_the_same_selection(client, selection):
    catalogue = client.app.state.engine.catalogue
    try:
        expected = build_plan(catalogue, selection)
    except Exception:
        assert client.post("/api/plan/preview", json={"selection": selection}).status_code == 422
        return
    body = client.post("/api/plan/preview", json={"selection": selection}).json()
    assert [p["key"] for p in body["phases"]] == [p.key for p in expected.phases]
    for sent, truth in zip(body["phases"], expected.phases):
        assert [a["key"] for a in sent["artefacts"]] == [a.key for a in truth.artefacts]
        assert sent["waves"] == [[a.key for a in wave] for wave in truth.waves]
    assert body["notes"] == list(expected.notes)


def test_the_preview_reports_the_wave_of_each_artefact_and_what_it_waits_for(client):
    reqs = next(p for p in client.post("/api/plan/preview", json={}).json()["phases"] if p["key"] == "requirements")
    waves = {a["key"]: a["wave"] for a in reqs["artefacts"]}
    assert waves["personas"] == waves["problem_statement"] == 1 and waves["functional_requirements"] == 2 and waves["epics_features"] == 3
    assert next(a for a in reqs["artefacts"] if a["key"] == "epics_features")["waits_for"] == ["functional_requirements", "non_functional_requirements"]


def test_a_selection_that_needs_an_unticked_artefact_adds_it_and_says_so_in_a_sentence(client, monkeypatch):
    from app.workflow.definitions import ArtefactDef, Catalogue, PhaseDef

    chain = (
        ArtefactDef("base", "Base", "T-BASE", "orchestrator", True, "", (), "t"),
        ArtefactDef("mid", "Mid", "T-MID", "orchestrator", False, "", ("base",), "t"),
        ArtefactDef("leaf", "Leaf", "T-LEAF", "orchestrator", False, "", ("mid",), "t"),
    )
    monkeypatch.setattr(client.app.state.engine, "catalogue", Catalogue((PhaseDef("t", 0, "Test phase", "", "x", chain),)))
    body = client.post("/api/plan/preview", json={"selection": {"t": ["base", "leaf"]}}).json()    # mid was left out but leaf needs it
    assert body["notes"] == ["Test phase: 'Mid' was added because 'Leaf' needs it"]
    flags = {a["key"]: a["added_because_needed"] for a in body["phases"][0]["artefacts"]}
    assert flags == {"base": False, "mid": True, "leaf": False}


def test_a_dependency_that_was_not_ticked_is_added_and_the_reason_is_a_sentence(client):
    selection = {"requirements": REQUIRED_REQUIREMENTS}
    # user_stories is optional; ticking it adds nothing missing. Leave a REQUIRED one out to be refused instead:
    refused = client.post("/api/plan/preview", json={"selection": {"requirements": ["personas"]}})
    assert refused.status_code == 422 and "required and cannot be switched off" in refused.json()["detail"]
    ok = client.post("/api/plan/preview", json={"selection": selection}).json()
    assert ok["notes"] == [] and all(a["added_because_needed"] is False for p in ok["phases"] for a in p["artefacts"])


@pytest.mark.parametrize("selection, fragment", [
    ({"nonsense": ["x"]}, "unknown phase"),
    ({"requirements": ["gadgets"]}, "no artefact"),
    ({"requirements": "personas"}, ""),
    ({"Requirements": []}, "unknown phase"),
])
def test_a_bad_selection_is_a_422_with_the_servers_own_sentence(client, selection, fragment):
    response = client.post("/api/plan/preview", json={"selection": selection})
    assert response.status_code == 422 and fragment in json.dumps(response.json())


def test_the_preview_needs_no_actor_and_creates_nothing(client):
    assert client.post("/api/plan/preview", json={}).status_code == 200
    assert client.get("/api/projects").json() == {"projects": []}


# ---- creating a project ----------------------------------------------------------------------------------------------------------------

def test_creating_a_project_opens_all_seven_phases_and_returns_the_project(client):
    response = create(client, brief="Staff book rooms.")
    assert response.status_code == 201
    body = response.json()
    assert (body["name"], body["brief"], body["mode"]) == ("Meeting Room Booking", "Staff book rooms.", "replay")
    assert [p["key"] for p in body["phases"]] == ["setup", "requirements", "design", "architecture", "build", "deploy", "handover"]
    assert {p["status"] for p in body["phases"]} == {"not_started"} and body["next_action"] == "Setup can start"
    assert client.get("/api/projects").json()["projects"][0]["id"] == body["id"]


def test_creating_a_project_stores_a_row_for_every_phase_of_its_plan(client):
    pid = create(client).json()["id"]
    stored = client.app.state.store.phases.list(pid)
    assert [r.phase_key for r in stored] == ["setup", "requirements", "design", "architecture", "build", "deploy", "handover"]
    assert {r.status for r in stored} == {"not_started"}


def test_the_project_takes_the_servers_mode_whatever_the_client_says(make_settings):
    live = TestClient(create_app(make_settings(app_mode="live")))
    assert create(live).json()["mode"] == "live"
    assert create(live, mode="replay").status_code == 422        # there is no mode field to send: mode is not a client choice


def test_the_audit_row_carries_the_named_person(client):
    pid = create(client).json()["id"]
    [event] = [e for e in client.app.state.store.audit.list(pid) if e.action == "project.created"]
    assert event.actor == "human:Parag"


@pytest.mark.parametrize("body", [
    {"name": ""}, {"name": "   "}, {"name": "x" * 121}, {"name": "ok", "brief": "x" * 8001}, {"name": "ok", "surprise": 1},
    {"name": "ok", "selection": []}, {"name": "ok", "selection": {"requirements": 5}}, {"name": "ok", "connectors": ["teleporter"]},
    {"name": "ok", "connectors": ["source_control"] * 5}, {}, {"name": 7},
])
def test_an_invalid_request_is_refused_and_nothing_is_created(client, body):
    response = client.post("/api/projects", json=body, headers=ACTOR)
    assert response.status_code == 422
    assert client.get("/api/projects").json() == {"projects": []}


def test_a_selection_that_leaves_out_a_required_artefact_is_refused_before_anything_is_created(client):
    response = create(client, selection={"requirements": ["personas"]})
    assert response.status_code == 422 and "required and cannot be switched off" in response.json()["detail"]
    assert client.get("/api/projects").json() == {"projects": []}


def test_a_selection_with_an_optional_artefact_left_out_is_planned_without_it(client):
    detail = create(client, selection={"requirements": REQUIRED_REQUIREMENTS}).json()
    reqs = next(p for p in detail["phases"] if p["key"] == "requirements")
    assert "user_stories" not in [a["key"] for a in reqs["artefacts"]] and len(reqs["artefacts"]) == 6


def test_the_name_is_tidied_and_connectors_are_remembered_as_simulated(client):
    body = create(client, name="  Meeting   Room  ", connectors=["ci_cd", "source_control", "ci_cd"]).json()
    assert body["name"] == "Meeting Room" and body["connectors"] == ["ci_cd", "source_control"] and body["connectors_are_simulated"] is True
    assert client.get(f"/api/projects/{body['id']}").json()["connectors"] == ["ci_cd", "source_control"]
    event = next(e for e in client.app.state.store.audit.list(body["id"]) if e.action == "project.connectors_noted")
    assert event.detail == {"connectors": ["ci_cd", "source_control"], "simulated": True}


def test_no_connectors_ticked_means_none_remembered_and_no_audit_note(client):
    body = create(client).json()
    assert body["connectors"] == [] and not [e for e in client.app.state.store.audit.list(body["id"]) if e.action == "project.connectors_noted"]


# ---- listing and reading ------------------------------------------------------------------------------------------------------------------

def test_projects_are_listed_newest_first_with_a_summary_of_where_each_stands(client):
    first, second = create(client, name="First").json(), create(client, name="Second").json()
    listed = client.get("/api/projects").json()["projects"]
    assert [p["name"] for p in listed] == ["Second", "First"]
    top = listed[0]
    assert set(top) == {"id", "name", "mode", "created_at", "archived_at", "phases_total", "phases_approved", "active_phase", "next_action"}
    assert top["archived_at"] is None
    assert (top["phases_total"], top["phases_approved"], top["active_phase"]) == (7, 0, None)
    assert first["id"] != second["id"]


def test_the_list_is_cut_at_the_cap_and_keeps_the_newest(client, monkeypatch):
    from app import routes_projects

    monkeypatch.setattr(routes_projects, "MAX_PROJECTS_LISTED", 3)
    for n in range(5):
        create(client, name=f"P{n}")
    assert [p["name"] for p in client.get("/api/projects").json()["projects"]] == ["P4", "P3", "P2"]


def test_the_real_cap_is_a_few_hundred_not_unlimited():
    from app import routes_projects

    assert 1 <= routes_projects.MAX_PROJECTS_LISTED <= 500


def test_a_summary_names_the_phase_that_is_under_way(client):
    pid = create(client).json()["id"]
    client.app.state.engine.start(pid, "setup", actor="system")
    top = client.get("/api/projects").json()["projects"][0]
    assert top["active_phase"] == {"key": "setup", "name": "Setup", "status": "running"} and "Setup is running" in top["next_action"]


def test_an_unknown_project_is_a_404_with_a_sentence(client):
    response = client.get("/api/projects/does-not-exist")
    assert response.status_code == 404 and "not found" in response.json()["detail"]


def test_reading_a_project_needs_no_actor(client):
    pid = create(client).json()["id"]
    assert client.get(f"/api/projects/{pid}").status_code == 200 and client.get("/api/projects").status_code == 200


def test_a_project_whose_stored_selection_is_broken_is_a_plain_error_not_a_crash(client):
    pid = create(client).json()["id"]
    with client.app.state.store.db.write() as conn:
        conn.execute("UPDATE projects SET selection = '{\"nonsense\": []}' WHERE id = ?", (pid,))
    response = client.get(f"/api/projects/{pid}")
    assert response.status_code == 422 and "invalid selection" in response.json()["detail"]


# ---- allowed actions: the screen decides nothing -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("status, expected", [
    ("not_started", ("run",)), ("running", ("run", "finish")), ("awaiting_review", ("approve", "request_changes")),
    ("rejected", ("run",)), ("approved", ("reopen",)),
])
def test_each_status_offers_exactly_these_actions(status, expected):
    assert allowed_actions(status, True, None) == expected == ACTIONS_BY_STATUS[status]


def test_a_phase_with_nothing_in_the_plan_offers_nothing():
    for status in ACTIONS_BY_STATUS:
        assert allowed_actions(status, False, None) == ()


def test_a_phase_that_has_not_started_and_is_blocked_offers_nothing_but_one_under_way_is_never_blocked():
    assert allowed_actions("not_started", True, "Setup") == ()
    assert allowed_actions("running", True, "Setup") == ("run", "finish")


def test_an_unknown_status_offers_nothing_rather_than_guessing():
    assert allowed_actions("exploded", True, None) == ()


def test_a_new_project_offers_run_for_setup_only_because_the_rest_are_blocked(client):
    phases = {p["key"]: p for p in create(client).json()["phases"]}
    assert phases["setup"]["allowed_actions"] == ["run"] and phases["setup"]["blocked_by"] is None
    for key in ("requirements", "design", "architecture", "build", "deploy", "handover"):
        assert phases[key]["allowed_actions"] == [] and phases[key]["blocked_by"] == "Setup"


def test_the_actions_follow_a_phase_through_its_life(client):
    pid = create(client).json()["id"]
    engine = client.app.state.engine
    def actions(key="setup"):
        return next(p for p in client.get(f"/api/projects/{pid}").json()["phases"] if p["key"] == key)["allowed_actions"]
    assert actions() == ["run"]
    engine.start(pid, "setup", actor="system");                     assert actions() == ["run", "finish"]
    engine.finish(pid, "setup", actor="system");                    assert actions() == ["approve", "request_changes"]
    engine.reject(pid, "setup", actor="human:ann", feedback="redo"); assert actions() == ["run"]
    engine.start(pid, "setup", actor="system"); engine.finish(pid, "setup", actor="system")
    client.app.state.store.artefacts.create(pid, artefact_type="project_charter", phase_key="setup", title="C", actor="system", prefix="SET-CHR")
    client.app.state.store.artefacts.add_version(pid, "SET-CHR-001", body="x", author="human:ann")
    engine.approve(pid, "setup", actor="human:ann");                assert actions() == ["reopen"]   # S12 follow-up: an approved phase can be taken back
    assert actions("requirements") == ["run"]                      # approving Setup unblocks the next phase


# ---- the X-Actor header ------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("headers, fragment", [
    ({}, "needs a name"), ({"X-Actor": ""}, "blank"), ({"X-Actor": "   "}, "blank"), ({"X-Actor": "x" * (MAX_NAME_CHARS + 1)}, "longer than"),
    ({"X-Actor": "system"}, "reserved"), ({"X-Actor": "System"}, "reserved"), ({"X-Actor": "human:ann"}, "reserved"), ({"X-Actor": "agent:r@m"}, "reserved"),
])
def test_a_changing_route_refuses_a_missing_blank_oversize_or_reserved_name(client, headers, fragment):
    response = client.post("/api/projects", json={"name": "P"}, headers=headers)
    assert response.status_code == 400 and fragment in response.json()["detail"]
    assert client.get("/api/projects").json() == {"projects": []}


def test_a_name_with_a_control_character_is_refused():
    from types import SimpleNamespace

    from fastapi import HTTPException

    for raw in ("Pa\x00rag", "Pa\x07rag", "Pa\x7frag"):
        with pytest.raises(HTTPException) as caught:
            actor_from(SimpleNamespace(headers={"x-actor": raw}))
        assert caught.value.status_code == 400 and "not allowed" in caught.value.detail


@pytest.mark.parametrize("name", ["Parag", "Parag Jain", "O'Brien-Smith", "José", "李雷", "a" * MAX_NAME_CHARS])
def test_ordinary_names_are_accepted_and_become_a_human_actor(name):
    from types import SimpleNamespace

    from app.repos import check_actor

    actor = actor_from(SimpleNamespace(headers={"x-actor": name}))
    assert actor == f"human:{name}" and check_actor(actor) == actor


def test_the_name_is_tidied_before_it_is_used():
    from types import SimpleNamespace

    assert actor_from(SimpleNamespace(headers={"x-actor": "  Parag    Jain  "})) == "human:Parag Jain"


# ---- what a response may contain ------------------------------------------------------------------------------------------------------------------

def test_no_response_contains_a_path_a_key_the_endpoint_or_a_prompt(make_settings):
    secret, endpoint = F.join("sk-test-", "own-", "ica-key-9999"), "https://ica.example-internal.test/api"
    client = TestClient(create_app(make_settings(ibm_ica_api_key=secret, ibm_ica_endpoint=endpoint)))
    pid = create(client, brief="Staff book rooms.", connectors=["ci_cd"]).json()["id"]
    texts = [client.get("/api/catalogue").text, client.get("/api/modes").text, client.post("/api/plan/preview", json={}).text,
             client.get("/api/projects").text, client.get(f"/api/projects/{pid}").text]
    for text in texts:
        for forbidden in (secret, endpoint, "/Users", "BEGIN UNTRUSTED", "<artefact>", ".db", "Traceback"):
            assert forbidden not in text, forbidden


def test_a_server_error_never_shows_a_traceback(client, monkeypatch):
    monkeypatch.setattr(client.app.state.engine, "snapshot", lambda pid: (_ for _ in ()).throw(RuntimeError("PLANTED-INTERNAL-DETAIL")))
    pid = client.app.state.store.projects.create(name="P", actor="system").id
    client_no_raise = TestClient(client.app, raise_server_exceptions=False)
    response = client_no_raise.get(f"/api/projects/{pid}")
    assert response.status_code == 500 and "PLANTED-INTERNAL-DETAIL" not in response.text and "Traceback" not in response.text


def test_the_new_routes_are_exactly_these(client):
    paths = client.app.openapi()["paths"]
    added = sorted((m.upper(), p) for p, ops in paths.items() for m in ops if p in ("/api/catalogue", "/api/modes", "/api/plan/preview", "/api/projects", "/api/projects/{project_id}"))
    assert added == [("GET", "/api/catalogue"), ("GET", "/api/modes"), ("GET", "/api/projects"), ("GET", "/api/projects/{project_id}"),
                     ("POST", "/api/plan/preview"), ("POST", "/api/projects")]
