"""The first HTTP routes: start, cancel, read a run, and the event stream. Streams are read through httpx's ASGI transport,
which delivers a response incrementally and closes the server's generator when the client stops reading."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.main import create_app
from app.llm.providers.mock import MockProvider
from app.llm.types import ProviderResponse, Usage

from .test_run_phase import BRIEF, MODELS, POLICY, REPLIES, Scripted

pytestmark = pytest.mark.anyio


@pytest.fixture
def world(make_settings):
    """A real app, a scripted model, a project with Setup done, and an HTTP client talking to it in-process."""

    async def build(delay=0.0, **settings):
        cfg = make_settings(**{**MODELS, "llm_retry_backoff_seconds": 0, **settings})
        provider = Scripted(delay)
        app = create_app(cfg, provider=provider)
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"X-Actor": "Ann"})   # S12b: starting and cancelling need a name
        client.asgi_app = app      # lets read_events talk to the app directly, for streams
        store, engine, runner = app.state.store, app.state.engine, app.state.runner
        project = store.projects.create(name="Room Booking", brief=BRIEF, actor="system")
        engine.open_project(project.id)
        store.context.add_document(project.id, "policy.md", POLICY, actor="human:ann")
        return app, client, provider, project

    return build


async def finish_setup(app, project):
    runner = app.state.runner
    await asyncio.wait_for(runner.run_phase(project.id, "setup"), 15)
    app.state.engine.finish(project.id, "setup", actor="system")
    app.state.engine.approve(project.id, "setup", actor="human:ann")


async def wait_for_end(app, project, run_id, seconds=6):
    for _ in range(int(seconds / 0.02)):
        record = app.state.store.runs.get(project.id, run_id)
        if record.status != "running":
            return record
        await asyncio.sleep(0.02)
    raise AssertionError("the run never ended")


async def read_events(client, url, *, until, headers=None, limit=200, spec="2.0"):
    """Collect (id, event, data) frames from an event stream until `until(frames)` is true, then disconnect.

    This drives the app through the ASGI protocol directly, because httpx's ASGI transport buffers a whole response
    before returning and so can never see an endless stream. Here the client really does stay connected, receives
    frames as they are sent, and then delivers a real `http.disconnect`, so the server's clean-up is exercised.
    """
    app = client.asgi_app
    path, _, query = url.partition("?")
    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": spec}, "http_version": "1.1", "method": "GET", "scheme": "http",
        "path": path, "raw_path": path.encode(), "query_string": query.encode(), "server": ("test", 80), "client": ("127.0.0.1", 1),
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    inbox: asyncio.Queue = asyncio.Queue()
    disconnect = asyncio.Event()
    requested = False

    async def receive():
        nonlocal requested
        if not requested:
            requested = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        await inbox.put(message)

    server = asyncio.create_task(app(scope, receive, send))
    frames: list[dict] = []
    status = content_type = cache = None
    buffer = ""
    try:
        while True:
            message = await asyncio.wait_for(inbox.get(), 6)
            if message["type"] == "http.response.start":
                status = message["status"]
                head = {k.decode(): v.decode() for k, v in message["headers"]}
                content_type, cache = head.get("content-type"), head.get("cache-control")
                continue
            buffer += message.get("body", b"").decode()
            while "\n\n" in buffer:
                raw, buffer = buffer.split("\n\n", 1)
                current: dict = {}
                for line in raw.split("\n"):
                    if line.startswith(":"):
                        current.setdefault("comments", []).append(line[1:].strip())
                    elif line:
                        name, _, value = line.partition(": ")
                        current[name] = json.loads(value) if name == "data" else value
                frames.append(current)
            if until(frames) or len(frames) >= limit or (message["type"] == "http.response.body" and not message.get("more_body", False)):
                break
    finally:
        disconnect.set()
        try:
            await asyncio.wait_for(server, 5)       # the server must notice the disconnect and finish by itself
        except asyncio.TimeoutError:
            server.cancel()
            raise AssertionError("the stream did not end after the client disconnected")
    return status, content_type, cache, frames


# ---- start a run -------------------------------------------------------------------------------------------------

async def test_starting_a_run_returns_at_once_with_a_run_id_and_the_work_happens_in_the_background(world):
    app, client, provider, project = await world(delay=0.2)
    await finish_setup(app, project)
    started = asyncio.get_running_loop().time()
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/run", json={})
    took = asyncio.get_running_loop().time() - started

    assert response.status_code == 202 and took < 0.15                      # the run itself takes ~1 s: we did not wait for it
    body = response.json()
    assert body["status"] == "running" and body["events"] == f"/api/projects/{project.id}/events"
    assert body["state"] == f"/api/projects/{project.id}/runs/{body['run_id']}"
    record = await wait_for_end(app, project, body["run_id"])
    assert record.status == "finished" and record.totals["artefacts"]["done"] == 7
    await client.aclose()


async def test_the_run_state_endpoint_reports_a_running_then_a_finished_run(world):
    app, client, provider, project = await world(delay=0.1)
    await finish_setup(app, project)
    run_id = (await client.post(f"/api/projects/{project.id}/phases/requirements/run", json={})).json()["run_id"]
    mid = (await client.get(f"/api/projects/{project.id}/runs/{run_id}")).json()
    assert mid["status"] == "running" and mid["totals"] is None and mid["phase"] == "requirements"
    await wait_for_end(app, project, run_id)
    end = (await client.get(f"/api/projects/{project.id}/runs/{run_id}")).json()
    assert end["status"] == "finished" and end["stop_reason"] is None and end["totals"]["cost_usd"] > 0
    await client.aclose()


async def test_request_options_are_passed_through_and_unknown_fields_are_refused(world):
    app, client, provider, project = await world()
    await finish_setup(app, project)
    refused = await client.post(f"/api/projects/{project.id}/phases/requirements/run", json={"only": ["personas"], "surprise": 1})
    assert refused.status_code == 422                                          # extra="forbid": nothing is silently ignored
    run_id = (await client.post(f"/api/projects/{project.id}/phases/requirements/run", json={"only": ["personas"]})).json()["run_id"]
    record = await wait_for_end(app, project, run_id)
    assert record.totals["artefacts"]["done"] == 1 and provider.asked.count("personas") == 1
    await client.aclose()


@pytest.mark.parametrize("path, body, status, fragment", [
    ("/api/projects/NOPE/phases/requirements/run", {}, 404, "not found"),
    ("/api/projects/{p}/phases/nonsense/run", {}, 404, "unknown phase"),
    ("/api/projects/{p}/phases/Requirements/run", {}, 422, "lower-case"),
    ("/api/projects/{p}/phases/requirements/run", {"only": ["gadgets"]}, 422, "not in the plan"),
    ("/api/projects/{p}/phases/requirements/run", {"only": ["Bad Key!"]}, 422, "lower-case"),
    ("/api/projects/{p}/phases/requirements/run", {"only": []}, 422, "names no artefacts"),
    ("/api/projects/{p}/phases/requirements/run", {"only": ["personas"], "rewrite_all": True}, 422, "not both"),
    ("/api/projects/{p}/phases/requirements/run", {"review": "maybe"}, 422, ""),
    ("/api/projects/{p}/phases/requirements/run", {"only": ["a"] * 41}, 422, ""),
])
async def test_a_bad_start_is_refused_with_a_plain_message_and_nothing_runs(world, path, body, status, fragment):
    app, client, provider, project = await world()
    await finish_setup(app, project)
    before = len(provider.asked)
    response = await client.post(path.replace("{p}", project.id), json=body)
    assert response.status_code == status
    if fragment:
        assert fragment in json.dumps(response.json())
    assert len(provider.asked) == before and app.state.runner.active_count == 0
    await client.aclose()


async def test_a_second_start_for_a_running_phase_is_a_409_not_a_queue(world):
    app, client, provider, project = await world(delay=0.2)
    await finish_setup(app, project)
    first = await client.post(f"/api/projects/{project.id}/phases/requirements/run", json={})
    second = await client.post(f"/api/projects/{project.id}/phases/requirements/run", json={})
    assert first.status_code == 202 and second.status_code == 409 and "already being run" in second.json()["detail"]
    await wait_for_end(app, project, first.json()["run_id"])
    await client.aclose()


async def test_starting_a_phase_whose_prerequisite_is_not_met_is_refused_at_once_with_the_reason_and_costs_nothing(world):
    app, client, provider, project = await world()
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/run", json={})
    assert response.status_code == 409 and "Setup is 'not_started' and must be approved first" in response.json()["detail"]
    assert provider.asked == [] and app.state.store.runs.list(project.id) == [] and app.state.runner.active_count == 0
    await client.aclose()


# ---- cancel and read --------------------------------------------------------------------------------------------------------

async def test_cancel_stops_new_work_and_says_in_flight_work_finishes(world):
    app, client, provider, project = await world(delay=0.1, run_max_concurrency=2)
    await finish_setup(app, project)
    run_id = (await client.post(f"/api/projects/{project.id}/phases/requirements/run", json={})).json()["run_id"]
    for _ in range(500):
        if provider.now == 2:
            break
        await asyncio.sleep(0.005)
    response = await client.post(f"/api/projects/{project.id}/runs/{run_id}/cancel")
    assert response.status_code == 200 and response.json()["requested"] is True and "finish and save" in response.json()["note"]
    record = await wait_for_end(app, project, run_id)
    assert record.status == "stopped" and record.stop_reason == "cancelled"
    await client.aclose()


async def test_cancelling_a_finished_run_is_a_409_and_an_unknown_one_a_404(world):
    app, client, provider, project = await world()
    result = await app.state.runner.run_phase(project.id, "setup")
    done = await client.post(f"/api/projects/{project.id}/runs/{result.run_id}/cancel")
    assert done.status_code == 409 and "nothing to cancel" in done.json()["detail"]
    assert (await client.post(f"/api/projects/{project.id}/runs/nope/cancel")).status_code == 404
    assert (await client.post(f"/api/projects/{project.id}/runs/bad%20id/cancel")).status_code == 422
    await client.aclose()


async def test_a_run_is_only_visible_through_its_own_project(world):
    app, client, provider, project = await world()
    result = await app.state.runner.run_phase(project.id, "setup")
    other = app.state.store.projects.create(name="Other", actor="system")
    assert (await client.get(f"/api/projects/{other.id}/runs/{result.run_id}")).status_code == 404
    assert (await client.post(f"/api/projects/{other.id}/runs/{result.run_id}/cancel")).status_code == 404
    assert (await client.get(f"/api/projects/{project.id}/runs/{result.run_id}")).status_code == 200
    await client.aclose()


# ---- the event stream ----------------------------------------------------------------------------------------------------------

async def test_the_stream_has_the_right_headers_and_framing_and_ends_with_the_run(world):
    app, client, provider, project = await world()
    await finish_setup(app, project)
    run_id = (await client.post(f"/api/projects/{project.id}/phases/requirements/run", json={"only": ["personas"]})).json()["run_id"]
    status, content_type, cache, frames = await read_events(
        client, f"/api/projects/{project.id}/events?after=0", until=lambda f: any(x.get("event") == "run.finished" and x["data"]["run_id"] == run_id for x in f))
    assert status == 200 and content_type.startswith("text/event-stream") and cache == "no-cache"
    mine = [f for f in frames if "event" in f and f["data"]["run_id"] == run_id]
    assert [f["event"] for f in mine] == ["run.started", "gate.changed", "artefact.started", "artefact.finished", "run.finished"]
    assert next(f for f in mine if f["event"] == "gate.changed")["data"]["status"] == "running"
    assert all(f["id"].isdigit() for f in mine) and [int(f["id"]) for f in mine] == sorted(int(f["id"]) for f in mine)
    await client.aclose()


async def test_a_late_joiner_gets_the_whole_run_from_the_log_then_live_events(world):
    app, client, provider, project = await world()
    await finish_setup(app, project)
    result = await app.state.runner.run_phase(project.id, "requirements")
    _, _, _, frames = await read_events(client, f"/api/projects/{project.id}/events", until=lambda f: sum(1 for x in f if x.get("event") == "run.finished") >= 2)
    mine = [f["event"] for f in frames if "event" in f and f["data"]["run_id"] == result.run_id]
    assert mine[0] == "run.started" and mine[-1] == "run.finished" and mine.count("artefact.finished") == 7
    await client.aclose()


async def test_after_and_last_event_id_resume_with_no_gap_and_no_repeat(world):
    app, client, provider, project = await world()
    await finish_setup(app, project)
    await app.state.runner.run_phase(project.id, "requirements")
    stored = [e.id for e in app.state.store.run_events.list(project.id)]
    cut = stored[len(stored) // 2]
    for url, headers in ((f"/api/projects/{project.id}/events?after={cut}", None), (f"/api/projects/{project.id}/events", {"Last-Event-ID": str(cut)})):
        _, _, _, frames = await read_events(client, url, headers=headers, until=lambda f, n=len([i for i in stored if i > cut]): len([x for x in f if "id" in x]) >= n)
        got = [int(f["id"]) for f in frames if "id" in f]
        assert got == [i for i in stored if i > cut]
    await client.aclose()


async def test_a_watcher_connected_before_the_run_starts_receives_it_live(world):
    app, client, provider, project = await world(delay=0.05)
    await finish_setup(app, project)
    watching = asyncio.create_task(read_events(client, f"/api/projects/{project.id}/events?after={app.state.store.run_events.last_id(project.id)}",
                                               until=lambda f: any(x.get("event") == "run.finished" for x in f)))
    for _ in range(200):
        if app.state.bus.watcher_count:
            break
        await asyncio.sleep(0.01)
    assert app.state.bus.watcher_count == 1                                    # precondition: it is connected and waiting
    run_id = (await client.post(f"/api/projects/{project.id}/phases/requirements/run", json={})).json()["run_id"]
    _, _, _, frames = await asyncio.wait_for(watching, 20)
    events = [f["event"] for f in frames if "event" in f]
    assert events[0] == "run.started" and events[-1] == "run.finished" and events.count("artefact.finished") == 7
    await wait_for_end(app, project, run_id)
    await client.aclose()


async def test_two_watchers_both_receive_the_same_events(world):
    app, client, provider, project = await world(delay=0.02)
    await finish_setup(app, project)
    last = app.state.store.run_events.last_id(project.id)
    done = lambda f: any(x.get("event") == "run.finished" for x in f)   # noqa: E731
    a = asyncio.create_task(read_events(client, f"/api/projects/{project.id}/events?after={last}", until=done))
    b = asyncio.create_task(read_events(client, f"/api/projects/{project.id}/events?after={last}", until=done))
    for _ in range(200):
        if app.state.bus.watcher_count == 2:
            break
        await asyncio.sleep(0.01)
    await client.post(f"/api/projects/{project.id}/phases/requirements/run", json={"only": ["personas", "problem_statement"]})
    (_, _, _, fa), (_, _, _, fb) = await asyncio.wait_for(asyncio.gather(a, b), 20)
    assert [f["id"] for f in fa if "id" in f] == [f["id"] for f in fb if "id" in f] and len(fa) >= 6
    await client.aclose()


async def test_an_idle_stream_sends_a_heartbeat_that_is_not_stored(world):
    app, client, provider, project = await world(run_heartbeat_seconds=0.1)
    before = app.state.store.run_events.last_id(project.id)
    _, _, _, frames = await read_events(client, f"/api/projects/{project.id}/events", until=lambda f: any("heartbeat" in x.get("comments", []) for x in f))
    assert any("heartbeat" in f.get("comments", []) for f in frames)
    assert app.state.store.run_events.last_id(project.id) == before
    await client.aclose()


async def test_the_stream_releases_its_watcher_when_the_client_goes_away(world):
    app, client, provider, project = await world(run_heartbeat_seconds=0.1)
    await read_events(client, f"/api/projects/{project.id}/events", until=lambda f: any("heartbeat" in x.get("comments", []) for x in f))
    for _ in range(100):
        if app.state.bus.watcher_count == 0:
            break
        await asyncio.sleep(0.02)
    assert app.state.bus.watcher_count == 0
    await client.aclose()


@pytest.mark.parametrize("url, headers, status", [
    ("/api/projects/NOPE/events", None, 404),
    ("/api/projects/{p}/events?after=-1", None, 422),
    ("/api/projects/{p}/events?after=abc", None, 422),
    ("/api/projects/{p}/events", {"Last-Event-ID": "abc"}, 422),
])
async def test_a_bad_stream_request_is_refused_before_a_stream_opens(world, url, headers, status):
    app, client, provider, project = await world()
    response = await client.get(url.replace("{p}", project.id), headers=headers)
    assert response.status_code == status and response.headers["content-type"].startswith("application/json")
    assert app.state.bus.watcher_count == 0
    await client.aclose()


# ---- what the stream may carry ---------------------------------------------------------------------------------------------------------------

async def test_no_event_carries_prompt_text_a_model_reply_a_document_or_a_credential(make_settings):
    secret, endpoint = "sk-SECRET-VALUE-1234", "https://ica.example.invalid"
    cfg = make_settings(**{**MODELS, "ibm_ica_api_key": secret, "ibm_ica_endpoint": endpoint, "llm_retry_backoff_seconds": 0})
    provider = Scripted()
    replies = dict(REPLIES)
    replies["personas"] = replies["personas"].replace("Two personas follow", "PLANTED-REPLY-TEXT-4711 two personas follow")
    provider.replies = replies
    provider.fail["epics_features"] = [ProviderResponse("<artefact>\n## Overview\nPLANTED-BAD-REPLY-9921\n</artefact>", Usage(10, 10), "stop")] * 3
    app = create_app(cfg, provider=provider)
    store, engine, runner = app.state.store, app.state.engine, app.state.runner
    project = store.projects.create(name="Room Booking", brief=BRIEF, actor="system")
    engine.open_project(project.id)
    store.context.add_document(project.id, "policy.md", POLICY + b"\nPLANTED-DOCUMENT-TEXT-5580\n", actor="human:ann")
    await finish_setup(app, project)
    await runner.run_phase(project.id, "requirements", review=True)
    text = json.dumps([e.data for e in store.run_events.list(project.id)])
    for planted in ("PLANTED-REPLY-TEXT-4711", "PLANTED-BAD-REPLY-9921", "PLANTED-DOCUMENT-TEXT-5580", secret, endpoint,
                    "Staff may book a room", "Meeting Room Booking is a web application", "<artefact>", "<review>"):
        assert planted not in text, planted
    assert "artefact.failed" in {e.type for e in store.run_events.list(project.id)}          # precondition: a failure was published
    assert any("failed its checks after 3 attempt(s)" in (e.data.get("reason") or "") for e in store.run_events.list(project.id))


async def test_the_four_routes_s09_added_are_still_there_unchanged(world):
    """S09's four routes must still exist with the same method and path. Later slices add routes below a project (S12b: documents,
    search, artefacts, gate actions, list runs), so this no longer says 'only these'; test_routes_content pins the added set."""
    app, client, provider, project = await world()
    paths = app.openapi()["paths"]
    below_a_project = {(method.upper(), path) for path, operations in paths.items() if path.startswith("/api/projects/{project_id}/") for method in operations}
    assert {
        ("GET", "/api/projects/{project_id}/events"),
        ("GET", "/api/projects/{project_id}/runs/{run_id}"),
        ("POST", "/api/projects/{project_id}/phases/{phase_key}/run"),
        ("POST", "/api/projects/{project_id}/runs/{run_id}/cancel"),
    } <= below_a_project
    await client.aclose()


# ---- start-up, status and settings --------------------------------------------------------------------------------------------------------------

async def test_runs_left_running_by_a_previous_process_are_marked_interrupted_when_the_app_starts(make_settings):
    cfg = make_settings(**MODELS)
    first = create_app(cfg, provider=MockProvider())
    project = first.state.store.projects.create(name="P", actor="system")
    orphan = first.state.store.runs.start(project.id, "requirements")        # as if the process died mid-run
    second = create_app(cfg, provider=MockProvider())
    record = second.state.store.runs.get(project.id, orphan.id)
    assert record.status == "interrupted" and "backend stopped" in record.totals["note"]
    assert [e.type for e in second.state.store.run_events.list(project.id)] == ["run.stopped"]


async def test_the_status_block_shows_limits_and_counts_and_nothing_else(world):
    app, client, provider, project = await world(delay=0.1)
    idle = (await client.get("/api/status")).json()["run"]
    assert idle == {"max_concurrency": 3, "max_cost_usd": 5.0, "max_seconds": 1800.0, "active_runs": 0, "event_watchers": 0}
    await finish_setup(app, project)
    run_id = (await client.post(f"/api/projects/{project.id}/phases/requirements/run", json={})).json()["run_id"]
    assert (await client.get("/api/status")).json()["run"]["active_runs"] == 1
    await wait_for_end(app, project, run_id)
    assert "/Users" not in (await client.get("/api/status")).text
    await client.aclose()


async def test_a_zero_cap_is_reported_as_off_not_as_zero(world):
    app, client, provider, project = await world(run_max_cost_usd=0, run_max_seconds=0)
    block = (await client.get("/api/status")).json()["run"]
    assert block["max_cost_usd"] is None and block["max_seconds"] is None
    await client.aclose()


def test_run_setting_defaults_match_the_spec():
    from app.config import Settings

    s = Settings(_env_file=None)
    assert (s.run_max_concurrency, s.run_max_cost_usd, s.run_max_seconds, s.run_event_queue, s.run_heartbeat_seconds) == (3, 5.0, 1800, 200, 15)      # the cost cap was raised from 2.0 to 5.0 on 2026-10-31 at the user's request


@pytest.mark.parametrize("field, bad", [
    ("run_max_concurrency", 0), ("run_max_concurrency", 9), ("run_max_cost_usd", -1), ("run_max_seconds", -1),
    ("run_event_queue", 5), ("run_heartbeat_seconds", 0),
])
def test_out_of_range_run_settings_are_rejected(field, bad):
    from pydantic import ValidationError

    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: bad})


# ---- schema v5 -----------------------------------------------------------------------------------------------------------------------------------

def test_a_v4_database_with_data_upgrades_to_v5_and_keeps_its_data_and_its_guards(tmp_path):
    import sqlite3

    from app.db import MIGRATIONS, SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4, Database, split_statements
    from app.repos import Store

    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    for script in (SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4):
        for statement in split_statements(script):
            raw.execute(statement)
    raw.execute("PRAGMA user_version = 4")
    raw.execute("INSERT INTO projects (id, name, mode, created_at, updated_at) VALUES ('p1', 'Old', 'replay', 't', 't')")
    raw.execute("INSERT INTO artefacts (project_id, id, type, phase_key, title, created_at) VALUES ('p1', 'REQ-F-001', 't', 'requirements', 'T', 't')")
    raw.execute("INSERT INTO artefact_versions (project_id, artefact_id, number, body, author, created_at) VALUES ('p1', 'REQ-F-001', 1, 'old', 'human:a', 't')")
    raw.commit()
    raw.close()

    assert len(MIGRATIONS) >= 5 and Database(path).migrate() == len(MIGRATIONS)      # v5 data upgrades to whatever is latest (v6 added archiving)
    store = Store.open(path)
    store.projects.create(name="New", actor="system")                      # writes an audit row, so the trigger has something to guard
    assert store.artefacts.get_version("p1", "REQ-F-001").body == "old"
    assert store.runs.list("p1") == [] and store.run_events.list("p1") == []
    run = store.runs.start("p1", "requirements")
    store.run_events.append("p1", run.id, "run.started", {})
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        with Database(path).write() as conn:
            conn.execute("UPDATE artefact_versions SET body = 'x'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        with Database(path).write() as conn:
            conn.execute("DELETE FROM audit")


def test_concurrent_first_starts_of_a_v4_file_all_succeed_at_the_latest_version(tmp_path):
    import sqlite3
    from concurrent.futures import ThreadPoolExecutor

    from app.db import SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4, Database, split_statements

    path = tmp_path / "race.db"
    raw = sqlite3.connect(path)
    for script in (SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4):
        for statement in split_statements(script):
            raw.execute(statement)
    raw.execute("PRAGMA user_version = 4")
    raw.commit()
    raw.close()
    with ThreadPoolExecutor(max_workers=8) as pool:
        from app.db import MIGRATIONS
        assert list(pool.map(lambda _: Database(path).migrate(), range(8))) == [len(MIGRATIONS)] * 8
    with Database(path).read() as conn:
        assert {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")} >= {"runs", "run_events"}


# ---- gaps found by the S09 mutation check -----------------------------------------------------------------------------------------

class OpenStream:
    """A stream held open by hand, so a test can publish at an exact moment and read frames one at a time."""

    def __init__(self, app, url, headers=None, spec="2.0"):
        path, _, query = url.partition("?")
        self.scope = {
            "type": "http", "asgi": {"version": "3.0", "spec_version": spec}, "http_version": "1.1", "method": "GET", "scheme": "http",
            "path": path, "raw_path": path.encode(), "query_string": query.encode(), "server": ("test", 80), "client": ("127.0.0.1", 1),
            "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        }
        self.app, self.inbox, self.gone, self.sent_request, self.buffer = app, asyncio.Queue(), asyncio.Event(), False, ""
        self.task = None

    async def _receive(self):
        if not self.sent_request:
            self.sent_request = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await self.gone.wait()
        return {"type": "http.disconnect"}

    async def __aenter__(self):
        self.task = asyncio.create_task(self.app(self.scope, self._receive, self.inbox.put))
        return self

    async def frame(self, seconds=3):
        """The next complete frame, as a dict, or None if nothing arrives in time."""
        while "\n\n" not in self.buffer:
            try:
                message = await asyncio.wait_for(self.inbox.get(), seconds)
            except asyncio.TimeoutError:
                return None
            self.buffer += message.get("body", b"").decode() if message["type"] == "http.response.body" else ""
        raw, self.buffer = self.buffer.split("\n\n", 1)
        out = {}
        for line in raw.split("\n"):
            if line.startswith(":"):
                out.setdefault("comments", []).append(line[1:].strip())
            elif line:
                name, _, value = line.partition(": ")
                out[name] = json.loads(value) if name == "data" else value
        return out

    async def event_frame(self, seconds=3):
        """The next frame that is an event (skips comments such as 'live' and heartbeats)."""
        while True:
            f = await self.frame(seconds)
            if f is None or "event" in f:
                return f

    async def finished_within(self, seconds):
        try:
            await asyncio.wait_for(asyncio.shield(self.task), seconds)
            return True
        except asyncio.TimeoutError:
            return False

    async def __aexit__(self, *exc):
        self.gone.set()
        try:
            await asyncio.wait_for(self.task, 5)
        except (asyncio.TimeoutError, Exception):
            self.task.cancel()


async def test_an_event_published_in_the_gap_between_reading_the_log_and_going_live_is_not_lost(world, monkeypatch):
    """The stream must subscribe BEFORE it reads the log. Here an event is published exactly while the log is being read:
    it is too late for that read and the live queue must catch it. Subscribing afterwards would lose it."""
    app, client, provider, project = await world()
    store, bus = app.state.store, app.state.bus
    run = store.runs.start(project.id, "requirements")
    first = bus.publish(project.id, run.id, "run.started", {"phase": "requirements"})
    real_list, injected = store.run_events.list, {}

    def list_then_publish(*args, **kwargs):
        rows = real_list(*args, **kwargs)
        if "event" not in injected:                      # only during the first read
            injected["event"] = bus.publish(project.id, run.id, "artefact.started", {"key": "personas"})
        return rows

    monkeypatch.setattr(store.run_events, "list", list_then_publish)
    async with OpenStream(app, f"/api/projects/{project.id}/events?after=0") as stream:
        seen = [await stream.event_frame(), await stream.event_frame()]
    assert [f["event"] for f in seen] == ["run.started", "artefact.started"]
    assert int(seen[1]["id"]) == injected["event"].id > first.id
    await client.aclose()


async def test_an_event_that_was_already_sent_from_the_log_is_not_sent_again_from_the_live_queue(world, monkeypatch):
    app, client, provider, project = await world()
    store, bus = app.state.store, app.state.bus
    run = store.runs.start(project.id, "requirements")
    real_list = store.run_events.list

    def list_then_publish_twice(*args, **kwargs):
        rows = real_list(*args, **kwargs)
        if not getattr(list_then_publish_twice, "done", False):
            list_then_publish_twice.done = True
            bus.publish(project.id, run.id, "run.started", {})          # lands in the log AND in the live queue
            rows = real_list(*args, **kwargs)                            # ...and this read already includes it
        return rows

    monkeypatch.setattr(store.run_events, "list", list_then_publish_twice)
    async with OpenStream(app, f"/api/projects/{project.id}/events?after=0") as stream:
        first = await stream.event_frame()
        bus.publish(project.id, run.id, "run.finished", {})
        second = await stream.event_frame()
    assert (first["event"], second["event"]) == ("run.started", "run.finished")   # run.started appears once, not twice
    await client.aclose()


@pytest.mark.parametrize("spec", ["2.0", "2.3"])
async def test_the_stream_ends_and_frees_its_watcher_when_the_client_disconnects_while_idle(world, spec):
    app, client, provider, project = await world(run_heartbeat_seconds=0.1)
    stream = OpenStream(app, f"/api/projects/{project.id}/events", spec=spec)
    async with stream:
        heartbeat = None
        for _ in range(10):
            heartbeat = await stream.frame(1)
            if heartbeat and "heartbeat" in heartbeat.get("comments", []):
                break
        assert heartbeat and "heartbeat" in heartbeat["comments"] and app.state.bus.watcher_count == 1     # precondition: connected and idle
        stream.gone.set()                                                        # the client goes away
        assert await stream.finished_within(2.0), "the server kept an idle stream open after the client left"
    assert app.state.bus.watcher_count == 0
    await client.aclose()


async def test_a_run_id_with_unexpected_characters_is_refused_before_it_reaches_the_store(world):
    app, client, provider, project = await world()
    calls = []
    real_get = app.state.store.runs.get
    app.state.store.runs.get = lambda *a, **k: (calls.append(a), real_get(*a, **k))[1]
    for bad in ("bad%20id", "a%3Bb", "x" * 65):
        response = await client.get(f"/api/projects/{project.id}/runs/{bad}")
        assert response.status_code == 422 and "unexpected characters" in response.json()["detail"], bad
    assert calls == []                                                          # refused by the route, not looked up
    assert (await client.get(f"/api/projects/{project.id}/runs/ok_id-1")).status_code == 404   # a well-formed unknown id reaches the store
    assert len(calls) == 1
    await client.aclose()


async def test_an_unexpected_error_marks_the_run_failed_frees_the_phase_and_says_so_without_leaking_its_message(make_settings):
    cfg = make_settings(**MODELS, llm_retry_backoff_seconds=0)
    app = create_app(cfg, provider=Scripted())
    store, runner = app.state.store, app.state.runner
    project = store.projects.create(name="P", brief=BRIEF, actor="system")
    app.state.engine.open_project(project.id)

    def explode(*a, **k):
        raise RuntimeError("PLANTED-INTERNAL-DETAIL-7342 /Users/someone/secret/path")

    runner._execute = explode                                   # a bug somewhere in the scheduler itself
    with pytest.raises(RuntimeError):
        await runner.run_phase(project.id, "setup")
    [record] = store.runs.list(project.id)
    assert record.status == "failed" and record.finished_at                    # NOT left 'running'
    assert not runner.is_active(project.id, "setup")
    [event] = store.run_events.list(project.id)
    assert event.type == "run.stopped" and event.data["status"] == "failed"
    assert event.data["reason"] == "unexpected error (RuntimeError)"
    assert "PLANTED-INTERNAL-DETAIL-7342" not in json.dumps(event.data) and "/Users" not in json.dumps(event.data)
    assert record.totals["error"] == "unexpected error (RuntimeError)"          # the stored reason leaks nothing either


async def test_a_background_run_that_hits_an_unexpected_error_still_ends_the_run_row(make_settings):
    cfg = make_settings(**MODELS, llm_retry_backoff_seconds=0)
    app = create_app(cfg, provider=Scripted())
    store, runner = app.state.store, app.state.runner
    project = store.projects.create(name="P", brief=BRIEF, actor="system")
    app.state.engine.open_project(project.id)
    runner._execute = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    run_id = runner.start_phase(project.id, "setup")
    record = await wait_for_end(app, project, run_id)
    assert record.status == "failed" and record.totals["error"] == "unexpected error (RuntimeError)"
    assert runner.active_count == 0


async def test_the_scheduler_refuses_to_start_the_same_artefact_twice_instead_of_looping(make_settings, monkeypatch):
    import app.run.runner as runner_module

    cfg = make_settings(**MODELS, llm_retry_backoff_seconds=0)
    provider = Scripted()
    app = create_app(cfg, provider=provider)
    store, runner = app.state.store, app.state.runner
    project = store.projects.create(name="P", brief=BRIEF, actor="system")
    app.state.engine.open_project(project.id)
    store.context.add_document(project.id, "policy.md", POLICY, actor="human:ann")
    monkeypatch.setattr(runner_module, "ready", lambda order, after, done, started: list(order))   # a broken ready(): offers started ones too
    with pytest.raises(RuntimeError, match="scheduler fault: project_charter was offered to start a second time"):
        await asyncio.wait_for(runner.run_phase(project.id, "setup", rewrite_all=True), 10)
    assert provider.asked.count("project_charter") <= 1
    assert store.runs.list(project.id)[-1].status == "failed"


async def test_repair_reasons_are_kept_on_the_version_and_never_published_in_an_event(make_settings):
    cfg = make_settings(**MODELS, llm_retry_backoff_seconds=0)
    provider = Scripted()
    marker = "PLANTED-REPLY-WORDS-8842"
    provider.fail["personas"] = [ProviderResponse(f"<artefact>\n## Overview\n{marker}\n## Personas\n- {marker} no id here\n</artefact>", Usage(10, 10), "stop")]
    app = create_app(cfg, provider=provider)
    store, runner = app.state.store, app.state.runner
    project = store.projects.create(name="Room Booking", brief=BRIEF, actor="system")
    app.state.engine.open_project(project.id)
    store.context.add_document(project.id, "policy.md", POLICY, actor="human:ann")
    await finish_setup(app, project)
    await runner.run_phase(project.id, "requirements", only=["personas"])

    gen = store.artefacts.get_version(project.id, "REQ-PER-001").generation
    assert gen["attempts"] == 2 and gen["repair_reasons"]                                    # precondition: a repair really happened and was recorded
    kept = json.dumps(gen["repair_reasons"])
    assert "has no numbered items" in kept
    published = json.dumps([e.data for e in store.run_events.list(project.id)])
    assert "repair_reasons" not in published and "has no numbered items" not in published   # only a COUNT of problems may be published
    attempt_events = [e for e in store.run_events.list(project.id) if e.type == "artefact.attempt"]
    assert attempt_events and all(isinstance(e.data["problems"], int) for e in attempt_events)
