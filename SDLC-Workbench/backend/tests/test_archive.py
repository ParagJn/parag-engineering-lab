"""Archiving a project (S12b addendum 1): hidden, read-only, reversible, audited, and nothing deleted."""
from __future__ import annotations

import asyncio
import sqlite3

import httpx
import pytest

from app.archive import SENTENCE
from app.db import MIGRATIONS, SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4, SCHEMA_V5, Database, split_statements
from app.main import create_app
from app.repos import Store
from app.sample import BRIEF, FILENAME, NAME, POLICY

from .test_run_phase import MODELS, Scripted

pytestmark = pytest.mark.anyio
ANN = {"X-Actor": "Ann"}


@pytest.fixture
def world(make_settings):
    async def build(delay=0.0, **settings):
        cfg = make_settings(**{**MODELS, "llm_retry_backoff_seconds": 0, **settings})
        app = create_app(cfg, provider=Scripted(delay))
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=ANN)
        project = app.state.store.projects.create(name=NAME, brief=BRIEF, actor="system")
        app.state.engine.open_project(project.id)
        app.state.store.context.add_document(project.id, FILENAME, POLICY, actor="human:demo")
        return app, client, project

    return build


async def names(client, archived=False):
    url = "/api/projects?archived=true" if archived else "/api/projects"
    return [p["name"] for p in (await client.get(url)).json()["projects"]]


# ---- the repository ----------------------------------------------------------------------------------------------------------

def test_archiving_hides_a_project_from_the_default_list_and_shows_it_in_the_archived_list(tmp_path):
    store = Store.open(tmp_path / "a.db")
    keep, gone = store.projects.create(name="Keep", actor="system"), store.projects.create(name="Gone", actor="system")
    store.projects.archive(gone.id, actor="human:Ann")
    assert [p.name for p in store.projects.list()] == ["Keep"]
    assert [p.name for p in store.projects.list(archived=True)] == ["Gone"]
    assert store.projects.get(gone.id).archived_at is not None and store.projects.get(keep.id).archived_at is None      # still readable by id


def test_restoring_reverses_it(tmp_path):
    store = Store.open(tmp_path / "a.db")
    p = store.projects.create(name="P", actor="system")
    store.projects.archive(p.id, actor="human:Ann")
    restored = store.projects.restore(p.id, actor="human:Ann")
    assert restored.archived_at is None
    assert [x.name for x in store.projects.list()] == ["P"] and store.projects.list(archived=True) == []


def test_the_two_lists_never_overlap(tmp_path):
    store = Store.open(tmp_path / "a.db")
    ps = [store.projects.create(name=f"P{n}", actor="system") for n in range(4)]
    store.projects.archive(ps[1].id, actor="human:Ann"); store.projects.archive(ps[3].id, actor="human:Ann")
    active, archived = {p.id for p in store.projects.list()}, {p.id for p in store.projects.list(archived=True)}
    assert active == {ps[0].id, ps[2].id} and archived == {ps[1].id, ps[3].id} and not active & archived


def test_archiving_and_restoring_are_audited_with_the_persons_name(tmp_path):
    store = Store.open(tmp_path / "a.db")
    p = store.projects.create(name="P", actor="system")
    store.projects.archive(p.id, actor="human:Ann"); store.projects.restore(p.id, actor="human:Bo")
    events = [(e.action, e.actor) for e in store.audit.list(p.id) if e.action.startswith("project.") and e.action != "project.created"]
    assert events == [("project.archived", "human:Ann"), ("project.restored", "human:Bo")]


def test_repeating_either_changes_nothing_and_writes_no_second_audit_row(tmp_path):
    store = Store.open(tmp_path / "a.db")
    p = store.projects.create(name="P", actor="system")
    store.projects.restore(p.id, actor="human:Ann")                              # already active
    first = store.projects.archive(p.id, actor="human:Ann")
    again = store.projects.archive(p.id, actor="human:Bo")                         # already archived
    assert again.archived_at == first.archived_at                                  # the original time stands
    actions = [e.action for e in store.audit.list(p.id)]
    assert actions.count("project.archived") == 1 and actions.count("project.restored") == 0


def test_an_unknown_project_is_not_found_and_the_actor_is_checked(tmp_path):
    from app.models import InvalidInput, NotFoundError

    store = Store.open(tmp_path / "a.db")
    with pytest.raises(NotFoundError):
        store.projects.archive("nope", actor="human:Ann")
    with pytest.raises(NotFoundError):
        store.projects.restore("nope", actor="human:Ann")
    p = store.projects.create(name="P", actor="system")
    with pytest.raises(InvalidInput):
        store.projects.archive(p.id, actor="Ann")            # not a recognised actor form
    assert store.projects.get(p.id).archived_at is None


def test_archiving_deletes_nothing_underneath(tmp_path):
    store = Store.open(tmp_path / "a.db")
    p = store.projects.create(name="P", actor="system")
    art, _ = store.artefacts.create_and_add_version(p.id, artefact_type="personas", phase_key="requirements", title="T", prefix="REQ-PER", body="hello", author="human:Ann")
    store.context.add_document(p.id, "n.md", b"# N\n\nrooms are booked", actor="human:Ann")
    run = store.runs.start(p.id, "requirements"); store.run_events.append(p.id, run.id, "run.started", {})
    before = (len(store.artefacts.versions(p.id, art.id)), len(store.context.list_documents(p.id)), len(store.runs.list(p.id)), len(store.run_events.list(p.id)), len(store.audit.list(p.id)))
    store.projects.archive(p.id, actor="human:Ann"); store.projects.restore(p.id, actor="human:Ann")
    after = (len(store.artefacts.versions(p.id, art.id)), len(store.context.list_documents(p.id)), len(store.runs.list(p.id)), len(store.run_events.list(p.id)), len(store.audit.list(p.id)))
    assert after[:4] == before[:4] and after[4] == before[4] + 2             # only the two audit rows are new
    assert store.artefacts.get_version(p.id, art.id).body == "hello"


# ---- the routes --------------------------------------------------------------------------------------------------------------

async def test_archive_and_restore_over_http_move_a_project_between_the_two_lists(world):
    app, client, project = await world()
    archived = await client.post(f"/api/projects/{project.id}/archive")
    assert archived.status_code == 200 and archived.json()["archived_at"] is not None
    assert await names(client) == [] and await names(client, archived=True) == [NAME]
    restored = await client.post(f"/api/projects/{project.id}/restore")
    assert restored.status_code == 200 and restored.json()["archived_at"] is None
    assert await names(client) == [NAME] and await names(client, archived=True) == []
    await client.aclose()


async def test_the_archived_list_and_detail_carry_the_date(world):
    app, client, project = await world()
    await client.post(f"/api/projects/{project.id}/archive")
    [row] = (await client.get("/api/projects?archived=true")).json()["projects"]
    assert row["archived_at"] and (await client.get(f"/api/projects/{project.id}")).json()["archived_at"] == row["archived_at"]
    await client.aclose()


@pytest.mark.parametrize("action", ["archive", "restore"])
async def test_archive_and_restore_need_a_name(world, action):
    app, client, project = await world()
    response = await client.post(f"/api/projects/{project.id}/{action}", headers={"X-Actor": ""})
    assert response.status_code == 400
    bare = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    assert (await bare.post(f"/api/projects/{project.id}/{action}")).status_code == 400
    assert app.state.store.projects.get(project.id).archived_at is None
    await bare.aclose(); await client.aclose()


@pytest.mark.parametrize("action", ["archive", "restore"])
async def test_an_unknown_project_is_a_404(world, action):
    app, client, project = await world()
    assert (await client.post(f"/api/projects/nope/{action}")).status_code == 404
    await client.aclose()


async def test_repeating_over_http_is_harmless(world):
    app, client, project = await world()
    first = (await client.post(f"/api/projects/{project.id}/archive")).json()["archived_at"]
    second = await client.post(f"/api/projects/{project.id}/archive")
    assert second.status_code == 200 and second.json()["archived_at"] == first
    assert (await client.post(f"/api/projects/{project.id}/restore")).status_code == 200
    assert (await client.post(f"/api/projects/{project.id}/restore")).status_code == 200
    await client.aclose()


async def test_a_project_with_a_run_going_cannot_be_archived(world):
    app, client, project = await world(delay=0.3)
    run_id = (await client.post(f"/api/projects/{project.id}/phases/setup/run", json={})).json()["run_id"]
    for _ in range(100):
        if app.state.runner.is_active(project.id, "setup"):
            break
        await asyncio.sleep(0.01)
    refused = await client.post(f"/api/projects/{project.id}/archive")
    assert refused.status_code == 409 and "being written right now" in refused.json()["detail"]
    assert app.state.store.projects.get(project.id).archived_at is None
    for _ in range(300):
        if app.state.store.runs.get(project.id, run_id).status != "running":
            break
        await asyncio.sleep(0.02)
    assert (await client.post(f"/api/projects/{project.id}/archive")).status_code == 200          # fine once it has ended
    await client.aclose()


async def test_the_project_count_in_status_still_counts_archived_projects(world):
    app, client, project = await world()
    await client.post(f"/api/projects/{project.id}/archive")
    assert (await client.get("/api/status")).json()["db"]["projects"] == 1
    await client.aclose()


# ---- read-only ----------------------------------------------------------------------------------------------------------------

def change_calls(client, pid):
    """Every way a person can change a project over HTTP, as (label, coroutine factory)."""
    return [
        ("start a run", lambda: client.post(f"/api/projects/{pid}/phases/setup/run", json={})),
        ("add a document", lambda: client.post(f"/api/projects/{pid}/documents", files={"file": ("n.md", b"# N\n\nrooms")})),
        ("remove a document", lambda: client.delete(f"/api/projects/{pid}/documents/1")),
        ("hand to review", lambda: client.post(f"/api/projects/{pid}/phases/setup/finish")),
        ("approve", lambda: client.post(f"/api/projects/{pid}/phases/setup/approve")),
    ]


async def test_every_way_of_changing_an_archived_project_is_refused_with_the_same_sentence(world):
    app, client, project = await world()
    await client.post(f"/api/projects/{project.id}/archive")
    before = (len(app.state.store.runs.list(project.id)), len(app.state.store.context.list_documents(project.id)), len(app.state.store.audit.list(project.id)))
    for label, call in change_calls(client, project.id):
        response = await call()
        assert response.status_code == 409 and response.json()["detail"] == SENTENCE, label
    after = (len(app.state.store.runs.list(project.id)), len(app.state.store.context.list_documents(project.id)), len(app.state.store.audit.list(project.id)))
    assert after == before             # nothing was created, removed or recorded
    await client.aclose()


async def test_the_same_calls_work_again_after_a_restore(world):
    app, client, project = await world()
    await client.post(f"/api/projects/{project.id}/archive")
    await client.post(f"/api/projects/{project.id}/restore")
    response = await client.post(f"/api/projects/{project.id}/phases/setup/run", json={})
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    for _ in range(300):
        if app.state.store.runs.get(project.id, run_id).status != "running":
            break
        await asyncio.sleep(0.02)
    assert (await client.post(f"/api/projects/{project.id}/documents", files={"file": ("n.md", b"# N\n\nrooms")})).status_code == 201
    await client.aclose()


async def test_an_archived_project_can_still_be_read_in_full(world):
    app, client, project = await world()
    await app.state.runner.run_phase(project.id, "setup")
    await client.post(f"/api/projects/{project.id}/archive")
    pid = project.id
    for url in (f"/api/projects/{pid}", f"/api/projects/{pid}/documents", f"/api/projects/{pid}/artefacts", f"/api/projects/{pid}/runs",
                f"/api/projects/{pid}/search?q=booking"):
        assert (await client.get(url)).status_code == 200, url
    artefact_id = (await client.get(f"/api/projects/{pid}/artefacts")).json()["artefacts"][0]["id"]
    assert (await client.get(f"/api/projects/{pid}/artefacts/{artefact_id}")).status_code == 200
    await client.aclose()


async def test_archiving_one_project_does_not_lock_another(world):
    app, client, project = await world()
    other = app.state.store.projects.create(name="Other", brief=BRIEF, actor="system")
    app.state.engine.open_project(other.id)
    app.state.store.context.add_document(other.id, FILENAME, POLICY, actor="human:demo")
    await client.post(f"/api/projects/{project.id}/archive")
    assert (await client.post(f"/api/projects/{other.id}/phases/setup/run", json={})).status_code == 202
    for _ in range(300):
        if not app.state.runner.is_active(other.id, "setup"):
            break
        await asyncio.sleep(0.02)
    await client.aclose()


async def test_an_unknown_project_is_still_a_404_not_an_archived_message(world):
    app, client, project = await world()
    response = await client.post("/api/projects/nope/phases/setup/run", json={})
    assert response.status_code == 404
    await client.aclose()


# ---- the migration ------------------------------------------------------------------------------------------------------------

def test_a_v5_database_with_data_upgrades_to_the_latest_keeping_its_data_and_its_guards(tmp_path):
    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    for script in (SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, SCHEMA_V4, SCHEMA_V5):
        for statement in split_statements(script):
            raw.execute(statement)
    raw.execute("PRAGMA user_version = 5")
    raw.execute("INSERT INTO projects (id, name, mode, created_at, updated_at) VALUES ('p1', 'Old', 'replay', 't', 't')")
    raw.execute("INSERT INTO artefacts (project_id, id, type, phase_key, title, created_at) VALUES ('p1', 'REQ-F-001', 't', 'requirements', 'T', 't')")
    raw.execute("INSERT INTO artefact_versions (project_id, artefact_id, number, body, author, created_at) VALUES ('p1', 'REQ-F-001', 1, 'old', 'human:a', 't')")
    raw.commit(); raw.close()

    assert len(MIGRATIONS) == 10 and Database(path).migrate() == 10                     # v6 (archiving), v7 (S17b build rounds), v8 (S20b verify), v9 (S21c checklist) and v10 (S22a per-phase checklist) all apply
    store = Store.open(path)
    [old] = store.projects.list()
    assert old.name == "Old" and old.archived_at is None                      # every existing project is active
    assert store.artefacts.get_version("p1", "REQ-F-001").body == "old"
    store.projects.archive("p1", actor="human:Ann")
    assert store.projects.list() == [] and [p.id for p in store.projects.list(archived=True)] == ["p1"]
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        with Database(path).write() as conn:
            conn.execute("UPDATE artefact_versions SET body = 'x'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        with Database(path).write() as conn:
            conn.execute("DELETE FROM audit")
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        with Database(path).write() as conn:
            conn.execute("DELETE FROM artefact_versions")


def test_the_guards_still_stop_a_real_delete_of_an_archived_projects_history(tmp_path):
    """Archiving is not deletion: the database still refuses to remove a version or an audit row, archived or not."""
    store = Store.open(tmp_path / "a.db")
    p = store.projects.create(name="P", actor="system")
    store.artefacts.create_and_add_version(p.id, artefact_type="personas", phase_key="requirements", title="T", prefix="REQ-PER", body="x", author="human:Ann")
    store.projects.archive(p.id, actor="human:Ann")
    for sql in ("DELETE FROM artefact_versions", "DELETE FROM audit"):
        with pytest.raises(sqlite3.DatabaseError):
            with Database(tmp_path / "a.db").write() as conn:
                conn.execute(sql)


async def test_a_run_on_a_later_phase_also_blocks_archiving(world):
    """Not just the first phase: a run on Requirements could be spending money too."""
    app, client, project = await world()
    await app.state.runner.run_phase(project.id, "setup")
    app.state.engine.finish(project.id, "setup", actor="system"); app.state.engine.approve(project.id, "setup", actor="human:Ann")
    app.state.gateway.provider.delay = 0.3
    run_id = (await client.post(f"/api/projects/{project.id}/phases/requirements/run", json={})).json()["run_id"]
    for _ in range(100):
        if app.state.runner.is_active(project.id, "requirements"):
            break
        await asyncio.sleep(0.01)
    refused = await client.post(f"/api/projects/{project.id}/archive")
    assert refused.status_code == 409 and "requirements is being written right now" in refused.json()["detail"]
    assert app.state.store.projects.get(project.id).archived_at is None
    for _ in range(600):
        if app.state.store.runs.get(project.id, run_id).status != "running":
            break
        await asyncio.sleep(0.02)
    await client.aclose()


async def test_restoring_clears_the_date(world):
    app, client, project = await world()
    await client.post(f"/api/projects/{project.id}/archive")
    assert app.state.store.projects.get(project.id).archived_at is not None
    await client.post(f"/api/projects/{project.id}/restore")
    assert app.state.store.projects.get(project.id).archived_at is None
    await client.aclose()


async def test_the_sentence_a_person_sees_is_exactly_this_one(world):
    """Pinned as a literal on purpose. The other tests compare against app.archive.SENTENCE, which would follow any rewording."""
    app, client, project = await world()
    await client.post(f"/api/projects/{project.id}/archive")
    response = await client.post(f"/api/projects/{project.id}/phases/setup/run", json={})
    assert response.status_code == 409
    assert response.json() == {"detail": "This project is archived; restore it first."}
    assert SENTENCE == "This project is archived; restore it first."
    await client.aclose()
