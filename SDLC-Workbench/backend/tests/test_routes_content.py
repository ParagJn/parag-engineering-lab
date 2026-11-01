"""Documents, search, artefacts, the two gate actions and the list of runs over HTTP (S12b)."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.llm.providers.mock import MockProvider
from app.llm.recordings import Recording, RecordingStore
from app.llm.providers.recording import RecordingProvider, ReplayProvider
from app.main import create_app
from app.sample import BRIEF, FILENAME, NAME, POLICY

from . import _fakes as F
from .test_run_phase import MODELS, Scripted

pytestmark = pytest.mark.anyio
ANN = {"X-Actor": "Ann"}


@pytest.fixture
def world(make_settings):
    async def build(**settings):
        cfg = make_settings(**{**MODELS, "llm_retry_backoff_seconds": 0, **settings})
        app = create_app(cfg, provider=Scripted(0.0))
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        project = app.state.store.projects.create(name=NAME, brief=BRIEF, actor="system")
        app.state.engine.open_project(project.id)
        return app, client, project

    return build


def upload(client, pid, name="notes.md", data=b"# Notes\n\nStaff book rooms for meetings.", headers=ANN):
    return client.post(f"/api/projects/{pid}/documents", files={"file": (name, data)}, headers=headers)


async def run_to_end(app, client, pid, phase, **body):
    if not app.state.store.context.list_documents(pid):      # the scripted charter cites the policy; without it the citation check refuses it
        app.state.store.context.add_document(pid, FILENAME, POLICY, actor="human:demo")
    response = await client.post(f"/api/projects/{pid}/phases/{phase}/run", json=body, headers=ANN)
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]
    for _ in range(600):
        if app.state.store.runs.get(pid, run_id).status != "running":
            return run_id
        await asyncio.sleep(0.02)
    raise AssertionError("the run never ended")


async def through_setup(app, client, pid):
    await run_to_end(app, client, pid, "setup")
    assert (await client.post(f"/api/projects/{pid}/phases/setup/finish", headers=ANN)).status_code == 200
    assert (await client.post(f"/api/projects/{pid}/phases/setup/approve", headers=ANN)).status_code == 200


# ---- the sample project ------------------------------------------------------------------------------------------------

async def test_the_sample_is_exactly_the_text_the_recordings_were_made_with(world):
    app, client, _ = await world()
    body = (await client.get("/api/sample")).json()
    assert (body["name"], body["brief"]) == (NAME, BRIEF)
    assert body["document"] == {"filename": FILENAME, "text": POLICY.decode("utf-8")}
    assert body["document"]["text"].encode("utf-8") == POLICY      # the bytes the screen uploads are the bytes the recording saw
    await client.aclose()


async def test_the_demo_scripts_use_the_same_text_as_the_sample():
    import scripts.agent_demo as demo

    assert (demo.BRIEF, demo.POLICY, demo.NAME, demo.FILENAME) == (BRIEF, POLICY, NAME, FILENAME)


# ---- documents ---------------------------------------------------------------------------------------------------------

async def test_an_upload_is_listed_and_returns_what_was_flagged_by_rule_and_line_never_the_text(world):
    app, client, project = await world()
    secret_line = f"Contact {F.EMAIL} about bookings."
    response = await upload(client, project.id, "contacts.md", f"# Contacts\n\n{secret_line}\n".encode())
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "contacts.md" and body["source_id"] == "DOC-001" and body["added_by"] == "human:Ann"
    assert body["already_added"] is False
    assert [(f["rule"], f["class"]) for f in body["flags"]] == [("email", "personal")]
    assert body["flags"][0]["line"] == 3
    assert F.EMAIL not in response.text and "jane.doe" not in response.text
    listed = (await client.get(f"/api/projects/{project.id}/documents")).json()["documents"]
    assert [d["number"] for d in listed] == [1] and "flags" not in listed[0]        # flags are for the upload result only
    await client.aclose()


async def test_the_same_bytes_twice_say_already_added_and_do_not_add_another(world):
    app, client, project = await world()
    assert (await upload(client, project.id)).json()["already_added"] is False
    second = await upload(client, project.id)
    assert second.status_code == 201 and second.json()["already_added"] is True and second.json()["number"] == 1
    assert len((await client.get(f"/api/projects/{project.id}/documents")).json()["documents"]) == 1
    await client.aclose()


@pytest.mark.parametrize("name, data, fragment", [
    ("notes.exe", b"hello", "not a supported file type"),
    ("empty.txt", b"", "this file is empty"),
    ("blank.txt", b"   \n\n  ", "no readable text"),
])
async def test_a_file_that_cannot_be_used_is_a_422_with_the_servers_sentence_and_nothing_is_stored(world, name, data, fragment):
    app, client, project = await world()
    response = await upload(client, project.id, name, data)
    assert response.status_code == 422 and fragment in response.json()["detail"]
    assert (await client.get(f"/api/projects/{project.id}/documents")).json() == {"documents": []}
    await client.aclose()


async def test_a_file_over_the_limit_is_refused_without_reading_all_of_it(world):
    app, client, project = await world()
    limit = app.state.store.context.limits.max_file_bytes
    response = await upload(client, project.id, "big.txt", b"a " * (limit // 2 + 10))
    assert response.status_code == 422 and "limit" in response.json()["detail"]
    await client.aclose()


async def test_an_upload_with_no_file_part_is_a_422(world):
    app, client, project = await world()
    response = await client.post(f"/api/projects/{project.id}/documents", headers=ANN)
    assert response.status_code == 422
    await client.aclose()


async def test_changing_documents_needs_a_name_and_reading_does_not(world):
    app, client, project = await world()
    assert (await upload(client, project.id, headers={})).status_code == 400
    assert (await client.delete(f"/api/projects/{project.id}/documents/1")).status_code == 400
    assert (await client.get(f"/api/projects/{project.id}/documents")).status_code == 200
    assert (await client.get(f"/api/projects/{project.id}/search?q=rooms")).status_code == 200
    await client.aclose()


async def test_removing_a_document_takes_it_out_of_the_list_and_the_search_and_is_audited(world):
    app, client, project = await world()
    await upload(client, project.id, "a.md", b"# A\n\nZebrafish are striped.")
    assert (await client.get(f"/api/projects/{project.id}/search?q=zebrafish")).json()["hits"]
    removed = await client.delete(f"/api/projects/{project.id}/documents/1", headers=ANN)
    assert removed.status_code == 200 and removed.json() == {"removed": 1}
    assert (await client.get(f"/api/projects/{project.id}/documents")).json() == {"documents": []}
    assert (await client.get(f"/api/projects/{project.id}/search?q=zebrafish")).json()["hits"] == []
    event = next(e for e in app.state.store.audit.list(project.id) if e.action == "document.removed")
    assert event.actor == "human:Ann"
    await client.aclose()


@pytest.mark.parametrize("number, status", [(99, 404), (0, 422), (-1, 422), (1000001, 422)])
async def test_removing_a_document_that_is_not_there_or_a_bad_number(world, number, status):
    app, client, project = await world()
    assert (await client.delete(f"/api/projects/{project.id}/documents/{number}", headers=ANN)).status_code == status
    await client.aclose()


async def test_an_unknown_project_is_a_404_on_every_new_content_route(world):
    app, client, project = await world()
    for call in (client.get("/api/projects/nope/documents"), upload(client, "nope"), client.get("/api/projects/nope/search?q=a"),
                 client.delete("/api/projects/nope/documents/1", headers=ANN), client.get("/api/projects/nope/artefacts"),
                 client.get("/api/projects/nope/runs")):
        assert (await call).status_code == 404
    await client.aclose()


# ---- search ------------------------------------------------------------------------------------------------------------

async def test_a_search_returns_the_passage_where_it_came_from_and_the_id_to_cite(world):
    app, client, project = await world()
    await upload(client, project.id, FILENAME, POLICY)
    body = (await client.get(f"/api/projects/{project.id}/search?q=cancelled free of charge")).json()
    assert body["query"] == "cancelled free of charge"
    hit = body["hits"][0]
    assert hit["source_id"].startswith("DOC-001#") and hit["kind"] == "document" and "24 hours" in hit["text"]
    assert hit["heading_path"] and hit["citation"] and 0 < hit["relevance"] <= 1 and 0 < hit["coverage"] <= 1
    await client.aclose()


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
async def test_an_empty_search_is_refused_with_a_sentence(world, query):
    app, client, project = await world()
    response = await client.get(f"/api/projects/{project.id}/search", params={"q": query})
    assert response.status_code == 422 and "type a word" in response.json()["detail"]
    await client.aclose()


async def test_a_long_search_is_refused_and_the_limit_is_bounded(world):
    app, client, project = await world()
    assert (await client.get(f"/api/projects/{project.id}/search", params={"q": "a " * 150})).status_code == 422
    assert (await client.get(f"/api/projects/{project.id}/search", params={"q": "a" * 500})).status_code == 422
    for limit in (0, 21, -1):
        assert (await client.get(f"/api/projects/{project.id}/search", params={"q": "rooms", "limit": limit})).status_code == 422
    await client.aclose()


async def test_the_limit_cuts_the_hits_and_a_long_passage_is_shortened(world):
    app, client, project = await world()
    long_text = "# Long\n\n" + "\n\n".join(f"Rooms paragraph {n} " + "word " * 120 for n in range(6))
    await upload(client, project.id, "long.md", long_text.encode())
    two = (await client.get(f"/api/projects/{project.id}/search", params={"q": "rooms", "limit": 2})).json()["hits"]
    assert len(two) == 2 and all(len(h["text"]) <= 901 for h in two)
    assert len((await client.get(f"/api/projects/{project.id}/search", params={"q": "rooms", "limit": 20})).json()["hits"]) > 2
    await client.aclose()


async def test_a_search_with_odd_characters_does_not_crash(world):
    app, client, project = await world()
    await upload(client, project.id)
    for q in ['"', "NEAR(", "a AND", "*", "' OR 1=1 --", "rooms)", "😀"]:
        assert (await client.get(f"/api/projects/{project.id}/search", params={"q": q})).status_code == 200
    await client.aclose()


async def test_search_never_shows_another_projects_documents(world):
    app, client, project = await world()
    other = app.state.store.projects.create(name="Other", brief="x", actor="system")
    app.state.engine.open_project(other.id)
    await upload(client, other.id, "secret.md", b"# Other\n\nThe zebrafish password policy.")
    assert (await client.get(f"/api/projects/{project.id}/search?q=zebrafish")).json()["hits"] == []
    await client.aclose()


# ---- artefacts ---------------------------------------------------------------------------------------------------------

async def test_before_a_run_artefacts_are_not_listed_and_after_it_each_has_a_card(world):
    app, client, project = await world()
    assert (await client.get(f"/api/projects/{project.id}/artefacts")).json() == {"artefacts": []}
    await upload(client, project.id, FILENAME, POLICY)
    await run_to_end(app, client, project.id, "setup")
    [card] = (await client.get(f"/api/projects/{project.id}/artefacts?phase=setup")).json()["artefacts"]
    assert card["type"] == "project_charter" and card["phase_key"] == "setup" and card["latest_version"] == 1
    assert card["author"].startswith("agent:") and card["models"] and card["attempts"] == 1
    assert card["cost_usd"] is not None and card["flags"] == 0
    assert set(card) == {"id", "type", "phase_key", "title", "latest_version", "author", "created_at", "models", "cost_usd", "attempts", "item_count", "flags"}
    assert (await client.get(f"/api/projects/{project.id}/artefacts?phase=requirements")).json() == {"artefacts": []}
    await client.aclose()


async def test_an_artefact_detail_has_the_body_how_it_was_made_its_sources_and_its_versions(world):
    app, client, project = await world()
    await upload(client, project.id, FILENAME, POLICY)
    await run_to_end(app, client, project.id, "setup")
    artefact_id = (await client.get(f"/api/projects/{project.id}/artefacts")).json()["artefacts"][0]["id"]
    body = (await client.get(f"/api/projects/{project.id}/artefacts/{artefact_id}")).json()
    assert body["version"] == 1 and body["is_latest"] is True and "<artefact>" not in body["body"] and body["body"].strip()
    generation = body["generation"]
    assert generation["skill"] == "project_charter" and generation["human_edit"] is False and generation["attempts"] == 1
    assert generation["models"] and generation["cost_usd"] is not None and isinstance(generation["repair_reasons"], list)
    assert body["versions"] == [{"number": 1, "author": body["author"], "created_at": body["created_at"], "human_edit": False}]
    assert body["links"] == {"derived_from": [], "used_by": []}
    assert body["sources"], "precondition: the scripted charter cites the policy"
    for source in body["sources"]:
        assert source["available"] is True and source["text"] and source["source_id"].startswith("DOC-001#")
    await client.aclose()


async def test_a_cited_source_that_is_no_longer_available_says_so_and_shows_no_other_text(world):
    app, client, project = await world()
    await upload(client, project.id, FILENAME, POLICY)
    await run_to_end(app, client, project.id, "setup")
    artefact_id = (await client.get(f"/api/projects/{project.id}/artefacts")).json()["artefacts"][0]["id"]
    cited = (await client.get(f"/api/projects/{project.id}/artefacts/{artefact_id}")).json()["sources"]
    assert cited, "precondition: the charter cites the policy"
    await client.delete(f"/api/projects/{project.id}/documents/1", headers=ANN)
    after = (await client.get(f"/api/projects/{project.id}/artefacts/{artefact_id}")).json()["sources"]
    assert [s["source_id"] for s in after] == [s["source_id"] for s in cited]
    assert all(s["available"] is False and s["text"] is None for s in after)
    await client.aclose()


@pytest.mark.parametrize("path, status", [("nope", 404), ("bad%20id", 422), ("x" * 65, 422), ("a/b", 404)])
async def test_an_unknown_or_malformed_artefact_id(world, path, status):
    app, client, project = await world()
    assert (await client.get(f"/api/projects/{project.id}/artefacts/{path}")).status_code == status
    await client.aclose()


async def test_an_unknown_version_and_a_bad_version_number(world):
    app, client, project = await world()
    await run_to_end(app, client, project.id, "setup")
    artefact_id = (await client.get(f"/api/projects/{project.id}/artefacts")).json()["artefacts"][0]["id"]
    base = f"/api/projects/{project.id}/artefacts/{artefact_id}"
    assert (await client.get(base, params={"version": 1})).status_code == 200
    assert (await client.get(base, params={"version": 7})).status_code == 404
    for bad in (0, -1, "x"):
        assert (await client.get(base, params={"version": bad})).status_code == 422
    await client.aclose()


async def test_an_older_version_is_shown_as_not_the_latest(world):
    app, client, project = await world()
    await run_to_end(app, client, project.id, "setup")
    artefact_id = (await client.get(f"/api/projects/{project.id}/artefacts")).json()["artefacts"][0]["id"]
    app.state.store.artefacts.add_version(project.id, artefact_id, body="## Overview\nA person rewrote this.", author="human:Ann",
                                          generation={"human_edit": True, "based_on": 1})
    base = f"/api/projects/{project.id}/artefacts/{artefact_id}"
    latest, first = (await client.get(base)).json(), (await client.get(base, params={"version": 1})).json()
    assert latest["version"] == 2 and latest["is_latest"] is True and latest["generation"]["human_edit"] is True
    assert first["version"] == 1 and first["is_latest"] is False and first["body"] != latest["body"]
    assert [v["human_edit"] for v in latest["versions"]] == [False, True]
    await client.aclose()


async def test_the_links_of_an_artefact_show_what_it_was_derived_from_and_what_is_built_on_it(world):
    app, client, project = await world()
    store = app.state.store
    first = store.artefacts.create_and_add_version(project.id, artefact_type="problem_statement", phase_key="requirements", title="P", prefix="REQ-PRB", body="x", author="human:Ann")[0].id
    second = store.artefacts.create_and_add_version(project.id, artefact_type="personas", phase_key="requirements", title="Q", prefix="REQ-PER", body="y", author="human:Ann")[0].id
    store.links.add(project.id, first, second, "derives", actor="human:Ann")
    one = (await client.get(f"/api/projects/{project.id}/artefacts/{first}")).json()["links"]
    two = (await client.get(f"/api/projects/{project.id}/artefacts/{second}")).json()["links"]
    assert one["derived_from"] == [{"from": first, "to": second, "kind": "derives"}] and one["used_by"] == []
    assert two["used_by"] == [{"from": first, "to": second, "kind": "derives"}] and two["derived_from"] == []
    await client.aclose()


async def test_a_version_with_a_flag_shows_the_rule_and_line_and_never_the_value(world):
    app, client, project = await world()
    store = app.state.store
    created = store.artefacts.create_and_add_version(
        project.id, artefact_type="personas", phase_key="requirements", title="P", prefix="REQ-PER",
        body=f"## Overview\nAsk {F.EMAIL}", author="human:Ann", generation={"guardrails": [{"rule": "email", "class": "personal", "line": 2, "heading": "Overview", "length": 22}]},
    )
    artefact_id = created[0].id
    card = (await client.get(f"/api/projects/{project.id}/artefacts")).json()["artefacts"][0]
    assert card["flags"] == 1
    detail = (await client.get(f"/api/projects/{project.id}/artefacts/{artefact_id}")).json()
    assert detail["generation"]["guardrails"] == [{"rule": "email", "class": "personal", "line": 2, "heading": "Overview", "length": 22}]
    await client.aclose()


# ---- the two gate actions ----------------------------------------------------------------------------------------------

async def test_a_phase_goes_from_running_to_review_to_approved_by_the_two_buttons(world):
    app, client, project = await world()
    await run_to_end(app, client, project.id, "setup")
    status_of = lambda key: next(p.status for p in app.state.engine.snapshot(project.id).phases if p.key == key)      # noqa: E731
    assert status_of("setup") == "running"
    finished = await client.post(f"/api/projects/{project.id}/phases/setup/finish", headers=ANN)
    assert finished.status_code == 200 and finished.json()["status"] == "awaiting_review"
    approved = await client.post(f"/api/projects/{project.id}/phases/setup/approve", headers=ANN)
    assert approved.status_code == 200 and approved.json() == {"phase": "setup", "status": "approved", "decision": "approve", "decided_by": "human:Ann"}
    detail = (await client.get(f"/api/projects/{project.id}")).json()
    assert {p["key"]: p["allowed_actions"] for p in detail["phases"]}["requirements"] == ["run"]
    await client.aclose()


async def test_approving_records_what_was_still_open_so_an_unreviewed_approval_is_visible(world):
    app, client, project = await world()
    await through_setup(app, client, project.id)
    event = next(e for e in app.state.store.audit.list(project.id) if e.action == "phase.decided")
    assert event.actor == "human:Ann" and event.detail["unreviewed"] and event.detail["open_high_findings"] == 0
    await client.aclose()


@pytest.mark.parametrize("action", ["finish", "approve"])
async def test_a_gate_action_needs_a_name(world, action):
    app, client, project = await world()
    await run_to_end(app, client, project.id, "setup")
    assert (await client.post(f"/api/projects/{project.id}/phases/setup/{action}")).status_code == 400
    assert app.state.engine.snapshot(project.id).phases[0].status == "running"
    await client.aclose()


async def test_a_gate_action_that_the_state_does_not_allow_is_a_409_with_the_engines_sentence(world):
    app, client, project = await world()
    refused = await client.post(f"/api/projects/{project.id}/phases/setup/approve", headers=ANN)        # not started
    assert refused.status_code == 409 and "setup" in refused.json()["detail"]
    blocked = await client.post(f"/api/projects/{project.id}/phases/requirements/finish", headers=ANN)
    assert blocked.status_code == 409
    await client.aclose()


async def test_a_phase_cannot_be_approved_while_a_required_artefact_has_no_content(world):
    app, client, project = await world()
    app.state.engine.start(project.id, "setup", actor="system")
    app.state.engine.finish(project.id, "setup", actor="system")
    refused = await client.post(f"/api/projects/{project.id}/phases/setup/approve", headers=ANN)
    assert refused.status_code == 409 and "cannot be approved" in refused.json()["detail"]
    assert app.state.engine.snapshot(project.id).phases[0].status == "awaiting_review"
    await client.aclose()


async def test_a_phase_that_is_being_written_cannot_be_handed_to_review(world):
    app, client, project = await world()
    provider = app.state.gateway.provider
    provider.delay = 0.3
    response = await client.post(f"/api/projects/{project.id}/phases/setup/run", json={}, headers=ANN)
    run_id = response.json()["run_id"]
    for _ in range(100):
        if app.state.runner.is_active(project.id, "setup"):
            break
        await asyncio.sleep(0.01)
    refused = await client.post(f"/api/projects/{project.id}/phases/setup/finish", headers=ANN)
    assert refused.status_code == 409 and "being written" in refused.json()["detail"]
    for _ in range(300):
        if app.state.store.runs.get(project.id, run_id).status != "running":
            break
        await asyncio.sleep(0.02)
    await client.aclose()


@pytest.mark.parametrize("path, status", [("Setup", 422), ("no-such", 422), ("nonsense", 404)])
async def test_a_bad_phase_key_on_a_gate_action(world, path, status):
    app, client, project = await world()
    assert (await client.post(f"/api/projects/{project.id}/phases/{path}/approve", headers=ANN)).status_code == status
    await client.aclose()


# ---- starting and cancelling a run now name the person ---------------------------------------------------------------------

async def test_starting_a_run_needs_a_name_and_is_recorded_in_the_audit_trail(world):
    app, client, project = await world()
    assert (await client.post(f"/api/projects/{project.id}/phases/setup/run", json={})).status_code == 400
    assert app.state.store.runs.list(project.id) == []
    run_id = await run_to_end(app, client, project.id, "setup")
    event = next(e for e in app.state.store.audit.list(project.id) if e.action == "run.requested")
    assert event.actor == "human:Ann" and event.target_id == run_id and event.detail["phase"] == "setup"
    await client.aclose()


async def test_cancelling_a_run_needs_a_name_and_is_recorded(world):
    app, client, project = await world()
    app.state.gateway.provider.delay = 0.3
    run_id = (await client.post(f"/api/projects/{project.id}/phases/setup/run", json={}, headers=ANN)).json()["run_id"]
    assert (await client.post(f"/api/projects/{project.id}/runs/{run_id}/cancel")).status_code == 400
    assert (await client.post(f"/api/projects/{project.id}/runs/{run_id}/cancel", headers=ANN)).status_code == 200
    event = next(e for e in app.state.store.audit.list(project.id) if e.action == "run.cancel_requested")
    assert event.actor == "human:Ann" and event.target_id == run_id
    for _ in range(300):
        if app.state.store.runs.get(project.id, run_id).status != "running":
            break
        await asyncio.sleep(0.02)
    await client.aclose()


async def test_reading_a_run_and_the_events_still_need_no_name(world):
    app, client, project = await world()
    run_id = await run_to_end(app, client, project.id, "setup")
    assert (await client.get(f"/api/projects/{project.id}/runs/{run_id}")).status_code == 200
    await client.aclose()


# ---- listing runs ----------------------------------------------------------------------------------------------------------

async def test_the_runs_of_a_project_are_listed_newest_first_and_can_be_filtered_by_phase(world):
    app, client, project = await world()
    first = await run_to_end(app, client, project.id, "setup")
    await client.post(f"/api/projects/{project.id}/phases/setup/finish", headers=ANN)
    await client.post(f"/api/projects/{project.id}/phases/setup/approve", headers=ANN)
    second = await run_to_end(app, client, project.id, "requirements")
    runs = (await client.get(f"/api/projects/{project.id}/runs")).json()["runs"]
    assert [r["run_id"] for r in runs] == [second, first] and runs[0]["phase"] == "requirements" and runs[0]["status"] == "finished"
    only = (await client.get(f"/api/projects/{project.id}/runs?phase=setup")).json()["runs"]
    assert [r["run_id"] for r in only] == [first]
    assert (await client.get(f"/api/projects/{project.id}/runs?phase=Bad")).status_code == 422
    await client.aclose()


async def test_no_runs_is_an_empty_list_not_an_error(world):
    app, client, project = await world()
    assert (await client.get(f"/api/projects/{project.id}/runs")).json() == {"runs": []}
    await client.aclose()


# ---- what a response may contain -------------------------------------------------------------------------------------------

async def test_no_new_response_contains_a_prompt_a_key_the_endpoint_or_a_path(world):
    secret, endpoint = F.join("sk-test-", "own-", "ica-key-9999"), "https://ica.example-internal.test/api"
    app, client, project = await world(ibm_ica_api_key=secret, ibm_ica_endpoint=endpoint)
    await upload(client, project.id, FILENAME, POLICY)
    run_id = await run_to_end(app, client, project.id, "setup")
    artefact_id = (await client.get(f"/api/projects/{project.id}/artefacts")).json()["artefacts"][0]["id"]
    urls = [f"/api/sample", f"/api/projects/{project.id}/documents", f"/api/projects/{project.id}/search?q=booking",
            f"/api/projects/{project.id}/artefacts", f"/api/projects/{project.id}/artefacts/{artefact_id}",
            f"/api/projects/{project.id}/runs", f"/api/projects/{project.id}/runs/{run_id}"]
    for url in urls:
        text = (await client.get(url)).text
        for forbidden in (secret, endpoint, "/Users", "BEGIN UNTRUSTED", "<artefact>", ".db", "Traceback", "system prompt"):
            assert forbidden not in text, (url, forbidden)
    await client.aclose()


# ---- replay: a recording made one at a time must answer a parallel run -------------------------------------------------------

async def test_a_recording_made_one_artefact_at_a_time_replays_through_the_parallel_runner_with_no_miss(make_settings, tmp_path):
    """Why this exists: the live recording is made by running the chain serially, but the browser runs a phase in parallel waves. A
    prompt depends only on its upstream artefacts, so the two should ask identical questions; this proves it, with no money spent."""
    from app.agents.runtime import AgentRuntime  # noqa: F401  (documenting what is exercised)

    cfg = make_settings(**{**MODELS, "llm_retry_backoff_seconds": 0, "recordings_dir": str(tmp_path / "rec"), "replay_set": "t"})
    recordings = RecordingStore(cfg.recordings_path)

    # 1. record: run the phase SERIALLY (concurrency 1) through a recording wrapper around the scripted model
    serial_cfg = make_settings(**{**MODELS, "llm_retry_backoff_seconds": 0, "recordings_dir": str(tmp_path / "rec"), "replay_set": "t",
                                  "run_max_concurrency": 1, "data_dir": str(tmp_path / "d1")})
    recorder = RecordingProvider(Scripted(0.0), recordings, serial_cfg)
    app1 = create_app(serial_cfg, provider=recorder)
    p1 = app1.state.store.projects.create(name=NAME, brief=BRIEF, actor="system")
    app1.state.engine.open_project(p1.id)
    app1.state.store.context.add_document(p1.id, FILENAME, POLICY, actor="human:demo")
    await asyncio.wait_for(app1.state.runner.run_phase(p1.id, "setup"), 20)
    app1.state.engine.finish(p1.id, "setup", actor="system")
    app1.state.engine.approve(p1.id, "setup", actor="human:demo")
    result = await asyncio.wait_for(app1.state.runner.run_phase(p1.id, "requirements"), 20)
    assert result.max_in_flight == 1 and result.status == "finished"
    assert len(list(tmp_path.glob("rec/t/*.json"))) == 8      # precondition: the charter and all seven Requirements artefacts were recorded

    # 2. replay: a NEW project from the sample button's values, run in PARALLEL (concurrency 3), answered only from the recordings
    replay_cfg = make_settings(**{**MODELS, "llm_retry_backoff_seconds": 0, "recordings_dir": str(tmp_path / "rec"), "replay_set": "t",
                                  "app_mode": "replay", "run_max_concurrency": 3, "data_dir": str(tmp_path / "d2")})
    app2 = create_app(replay_cfg)
    p2 = app2.state.store.projects.create(name=NAME, brief=BRIEF, actor="system")
    app2.state.engine.open_project(p2.id)
    app2.state.store.context.add_document(p2.id, FILENAME, POLICY, actor="human:demo")
    setup = await asyncio.wait_for(app2.state.runner.run_phase(p2.id, "setup"), 20)
    assert setup.status == "finished", [o.reason for o in setup.outcomes]
    app2.state.engine.finish(p2.id, "setup", actor="system")
    app2.state.engine.approve(p2.id, "setup", actor="human:demo")
    replayed = await asyncio.wait_for(app2.state.runner.run_phase(p2.id, "requirements"), 20)
    assert replayed.status == "finished", [(o.key, o.reason) for o in replayed.outcomes]
    assert replayed.max_in_flight > 1                       # it really did run in waves, not one at a time
    assert all(o.state == "done" for o in replayed.outcomes)
    bodies = lambda app, pid: {a.type: app.state.store.artefacts.get_version(pid, a.id).body for a in app.state.store.artefacts.list(pid)}      # noqa: E731
    assert bodies(app2, p2.id) == bodies(app1, p1.id)         # the same text came back, artefact by artefact


async def test_a_project_with_a_different_name_misses_the_recording_and_says_so_without_the_prompt(make_settings, tmp_path):
    cfg = make_settings(**{**MODELS, "llm_retry_backoff_seconds": 0, "recordings_dir": str(tmp_path / "rec"), "replay_set": "t"})
    recordings = RecordingStore(cfg.recordings_path)
    serial = make_settings(**{**MODELS, "llm_retry_backoff_seconds": 0, "recordings_dir": str(tmp_path / "rec"), "replay_set": "t", "data_dir": str(tmp_path / "d1")})
    app1 = create_app(serial, provider=RecordingProvider(Scripted(0.0), recordings, serial))
    p1 = app1.state.store.projects.create(name=NAME, brief=BRIEF, actor="system")
    app1.state.engine.open_project(p1.id)
    app1.state.store.context.add_document(p1.id, FILENAME, POLICY, actor="human:demo")
    await asyncio.wait_for(app1.state.runner.run_phase(p1.id, "setup"), 20)

    replay = make_settings(**{**MODELS, "llm_retry_backoff_seconds": 0, "recordings_dir": str(tmp_path / "rec"), "replay_set": "t", "app_mode": "replay", "data_dir": str(tmp_path / "d2")})
    app2 = create_app(replay)
    p2 = app2.state.store.projects.create(name="Demo Project", brief=BRIEF, actor="system")
    app2.state.engine.open_project(p2.id)
    app2.state.store.context.add_document(p2.id, FILENAME, POLICY, actor="human:demo")
    result = await asyncio.wait_for(app2.state.runner.run_phase(p2.id, "setup"), 20)
    assert result.status == "failed"
    reason = result.outcomes[0].reason
    assert "no recording" in reason and "Meeting Room" not in reason and BRIEF[:30] not in reason


# ---- gaps the first break-one-thing sweep found ----------------------------------------------------------------------------

async def test_an_unknown_project_is_a_404_before_the_file_is_looked_at(world):
    """The project is checked first, so a bad file for a missing project is 'not found', not 'unsupported type'."""
    app, client, project = await world()
    response = await upload(client, "nope", "notes.exe", b"x")
    assert response.status_code == 404 and "not found" in response.json()["detail"]
    await client.aclose()


async def test_a_file_whose_name_is_only_spaces_is_refused_as_having_no_name(world):
    app, client, project = await world()
    response = await upload(client, project.id, "   ", b"hello")
    assert response.status_code == 422 and "has no name" in response.json()["detail"]
    await client.aclose()


async def test_an_oversize_file_is_refused_by_the_route_with_its_own_sentence(world):
    app, client, project = await world()
    limit = app.state.store.context.limits.max_file_bytes
    response = await upload(client, project.id, "big.txt", b"a " * (limit // 2 + 10))
    assert response.status_code == 422 and "larger than the" in response.json()["detail"]
    assert (await client.get(f"/api/projects/{project.id}/documents")).json() == {"documents": []}
    await client.aclose()


async def test_a_file_exactly_at_the_limit_is_not_refused_for_size(world):
    app, client, project = await world()
    limit = app.state.store.context.limits.max_file_bytes
    response = await upload(client, project.id, "edge.txt", (b"word " * (limit // 5 + 1))[:limit])
    assert "larger than the" not in response.text      # whatever else the store says about it, the route's size rule did not fire
    await client.aclose()


def test_a_long_passage_is_cut_at_the_limit_and_says_so():
    from types import SimpleNamespace

    from app.routes_content import MAX_HIT_CHARS, hit_payload

    base = dict(source_id="DOC-001#1", kind="document", title="t", heading_path="h", page=None, citation="c", phase_key=None, artefact_id=None, relevance=1.0, coverage=1.0)
    long_hit = hit_payload(SimpleNamespace(text="word " * 400, **base))
    assert len(long_hit["text"]) <= MAX_HIT_CHARS + 1 and long_hit["text"].endswith("…")
    exact = hit_payload(SimpleNamespace(text="x" * MAX_HIT_CHARS, **base))
    assert exact["text"] == "x" * MAX_HIT_CHARS            # a passage exactly at the limit is shown whole, with no ellipsis
    assert hit_payload(SimpleNamespace(text="short", **base))["text"] == "short"


async def test_the_search_reports_the_query_as_it_was_tidied(world):
    app, client, project = await world()
    body = (await client.get(f"/api/projects/{project.id}/search", params={"q": "  cancel    free \t of charge "})).json()
    assert body["query"] == "cancel free of charge"
    await client.aclose()


@pytest.mark.parametrize("url", ["/artefacts?phase=Bad", "/artefacts?phase=has%20space", "/runs?phase=Bad"])
async def test_a_malformed_phase_filter_is_refused_with_a_sentence(world, url):
    app, client, project = await world()
    response = await client.get(f"/api/projects/{project.id}{url}")
    assert response.status_code == 422 and "lower-case letters" in response.json()["detail"]
    await client.aclose()


async def test_an_artefact_with_no_version_yet_says_it_has_not_been_written(world):
    app, client, project = await world()
    empty = app.state.store.artefacts.create(project.id, artefact_type="project_charter", phase_key="setup", title="Charter", actor="system", prefix="SET-CHR")
    response = await client.get(f"/api/projects/{project.id}/artefacts/{empty.id}")
    assert response.status_code == 404 and "has not been written yet" in response.json()["detail"]
    listed = (await client.get(f"/api/projects/{project.id}/artefacts")).json()["artefacts"]
    assert listed[0]["latest_version"] is None and listed[0]["author"] is None and listed[0]["cost_usd"] is None
    await client.aclose()


async def test_a_file_one_byte_over_the_limit_is_refused_by_the_route(world):
    app, client, project = await world()
    limit = app.state.store.context.limits.max_file_bytes
    data = (b"word " * (limit // 5 + 2))[: limit + 1]
    assert len(data) == limit + 1          # precondition: exactly one byte over
    response = await upload(client, project.id, "edge.txt", data)
    assert response.status_code == 422 and "larger than the" in response.json()["detail"]
    await client.aclose()


async def test_a_cited_source_is_looked_up_in_the_artefacts_own_project_never_another(world):
    """Project A (the oldest) holds DOC-001. Project B cites DOC-001#1 but has no such document: B must see 'no longer available'."""
    app, client, a = await world()
    await upload(client, a.id, FILENAME, POLICY)
    b = app.state.store.projects.create(name="Second", brief="b", actor="system")
    app.state.engine.open_project(b.id)
    made = app.state.store.artefacts.create_and_add_version(
        b.id, artefact_type="personas", phase_key="requirements", title="P", prefix="REQ-PER", body="x", author="human:Ann", source_chunks=["DOC-001#1"],
    )
    sources = (await client.get(f"/api/projects/{b.id}/artefacts/{made[0].id}")).json()["sources"]
    assert [s["source_id"] for s in sources] == ["DOC-001#1"]
    assert sources[0]["available"] is False and sources[0]["text"] is None      # A's policy text must not leak into B
    assert "Staff may book" not in json.dumps(sources)
    await client.aclose()


async def test_no_more_than_forty_sources_are_returned_for_one_artefact(world):
    app, client, project = await world()
    many = [f"DOC-001#{n}" for n in range(1, 56)]
    made = app.state.store.artefacts.create_and_add_version(
        project.id, artefact_type="personas", phase_key="requirements", title="P", prefix="REQ-PER", body="x", author="human:Ann", source_chunks=many,
    )
    sources = (await client.get(f"/api/projects/{project.id}/artefacts/{made[0].id}")).json()["sources"]
    assert len(many) > 40 and len(sources) == 40
    assert [s["source_id"] for s in sources] == many[:40]      # the first forty, in the order they were cited
    await client.aclose()


async def test_a_cost_that_is_not_known_stays_unknown_on_the_card_and_the_detail_and_is_never_zero(world):
    app, client, project = await world()
    unpriced = app.state.store.artefacts.create_and_add_version(
        project.id, artefact_type="personas", phase_key="requirements", title="P", prefix="REQ-PER", body="x", author="agent:requirements_analyst@m",
        generation={"cost_usd": None, "attempts": 1, "calls": [{"model": "m", "fallback_used": False}], "items": [], "guardrails": [], "repair_reasons": []},
    )
    priced = app.state.store.artefacts.create_and_add_version(
        project.id, artefact_type="problem_statement", phase_key="requirements", title="Q", prefix="REQ-PRB", body="y", author="agent:requirements_analyst@m",
        generation={"cost_usd": 0.0, "attempts": 1, "calls": [], "items": [], "guardrails": [], "repair_reasons": []},
    )
    cards = {c["id"]: c for c in (await client.get(f"/api/projects/{project.id}/artefacts")).json()["artefacts"]}
    assert cards[unpriced[0].id]["cost_usd"] is None
    assert cards[priced[0].id]["cost_usd"] == 0.0            # a genuinely free call is zero; an unpriced one is not
    detail = (await client.get(f"/api/projects/{project.id}/artefacts/{unpriced[0].id}")).json()
    assert detail["cost_usd"] is None and detail["generation"]["cost_usd"] is None
    await client.aclose()


# ---- gaps the second break-one-thing sweep found --------------------------------------------------------------------------------

async def test_why_a_first_attempt_was_refused_reaches_the_reader_as_the_problems_and_nothing_else(world):
    app, client, project = await world()
    reasons = [
        {"attempt": 1, "call_id": "call-secret-1", "problems": ["you cited DOC-009#1, which was not provided", "a section is missing"]},
        {"attempt": 2, "call_id": "call-secret-2", "problems": ["one item has no source"]},
    ]
    made = app.state.store.artefacts.create_and_add_version(
        project.id, artefact_type="personas", phase_key="requirements", title="P", prefix="REQ-PER", body="x", author="agent:requirements_analyst@m",
        generation={"attempts": 3, "repairs": 2, "repair_reasons": reasons, "calls": [], "items": [], "guardrails": []},
    )
    response = await client.get(f"/api/projects/{project.id}/artefacts/{made[0].id}")
    assert response.json()["generation"]["repair_reasons"] == [
        {"attempt": 1, "problems": ["you cited DOC-009#1, which was not provided", "a section is missing"]},
        {"attempt": 2, "problems": ["one item has no source"]},
    ]
    assert "call-secret" not in response.text            # the call ids stay in the database
    await client.aclose()


async def test_an_artefacts_links_leave_out_the_links_between_its_own_items(world):
    """FR-001 derives from FR-002 inside one artefact: that is not 'derived from' something upstream, nor 'built on'."""
    app, client, project = await world()
    store = app.state.store
    made = store.artefacts.create_and_add_version(
        project.id, artefact_type="functional_requirements", phase_key="requirements", title="F", prefix="REQ-F", body="x", author="human:Ann",
        generation={"items": ["FR-001", "FR-002"], "calls": [], "guardrails": [], "repair_reasons": []},
    )
    artefact_id = made[0].id
    store.links.add(project.id, "FR-001", "FR-002", "derives", actor="human:Ann")          # inside the artefact
    store.links.add(project.id, "FR-001", "PER-001", "derives", actor="human:Ann")         # upstream
    store.links.add(project.id, "FEAT-001", "FR-002", "derives", actor="human:Ann")        # built on it
    links = (await client.get(f"/api/projects/{project.id}/artefacts/{artefact_id}")).json()["links"]
    assert links["derived_from"] == [{"from": "FR-001", "to": "PER-001", "kind": "derives"}]
    assert links["used_by"] == [{"from": "FEAT-001", "to": "FR-002", "kind": "derives"}]
    await client.aclose()


async def test_the_run_list_is_cut_at_twenty_and_keeps_the_newest(world):
    app, client, project = await world()
    store = app.state.store
    ids = []
    for _ in range(25):
        run = store.runs.start(project.id, "setup")
        store.runs.end(run.id, "finished", totals={"artefacts": {"done": 1, "failed": 0, "skipped": 0, "not_started": 0}})
        ids.append(run.id)
    listed = [r["run_id"] for r in (await client.get(f"/api/projects/{project.id}/runs")).json()["runs"]]
    assert len(listed) == 20
    assert listed == list(reversed(ids))[:20]              # the newest twenty, newest first
    assert ids[0] not in listed                            # the oldest has dropped off
    await client.aclose()


async def test_the_audit_row_for_a_run_names_the_phase_and_the_options_that_were_asked_for(world):
    app, client, project = await world()
    await through_setup(app, client, project.id)
    run_id = await run_to_end(app, client, project.id, "requirements", only=["personas"])
    event = next(e for e in app.state.store.audit.list(project.id) if e.action == "run.requested" and e.target_id == run_id)
    assert event.detail == {"phase": "requirements", "only": ["personas"], "rewrite_all": False, "review": False}
    await client.aclose()
