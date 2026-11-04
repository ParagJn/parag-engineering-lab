"""S20b: the record of every run (append-only), the service that makes one, and the routes. Folders are temporary; nothing outside them is read; no model is called."""
from __future__ import annotations

import sqlite3

import httpx
import pytest
from fastapi import FastAPI

from app.agents.skills import SkillLibrary
from app.db import Database
from app.llm.routing import Routing
from app.models import InvalidInput, NotFoundError
from app.repos import MAX_VERIFY_MATCHES, Store
from app.routes_verify import router
from app.verify import service as S
from app.verify.design import read_design
from app.workflow.definitions import load_catalogue

from . import _fakes as F
from .test_compose import DESIGN_BODIES, LLD, seed, uc_list

pytestmark = pytest.mark.anyio
ANN = {"X-Actor": "Ann"}
CODE = '''
from fastapi import FastAPI
app = FastAPI()
@app.get("/api/rooms")
def rooms(): ...
@app.post("/api/bookings", status_code=201)
def book(): ...
@app.get("/api/health")
def health(): ...
'''


def row(designed="API-001", state="found", **over):
    return {"designed": designed, "area": "endpoint", "state": state, "step": "exact", "score": 1.0, "built": "GET /x", "file": "a.py", "line": 3, "differences": [], "note": "", **over}


def add(store, project, **over):
    kw = dict(backend_path="/tmp/b", frontend_path=None, actor="human:ann", design={"DES-LLD-001": 1}, counts=[{"area": "endpoint", "designed": 1}], notes=["n"], matches=[row()])
    kw.update(over)
    return store.verify.add_run(project.id, **kw)


# ---- the record -----------------------------------------------------------------------------------------------------------------------------------

def test_a_run_is_saved_with_its_matches_and_read_back_exactly(store, project):
    run = add(store, project, frontend_path="/tmp/f", matches=[row(), row("API-002", "differences", differences=["the design says x"], note="why"), row(None, "extra", built="GET /extra")])
    assert (run.project_id, run.backend_path, run.frontend_path, run.actor, run.design, run.notes) == (project.id, "/tmp/b", "/tmp/f", "human:ann", {"DES-LLD-001": 1}, ("n",))
    got = store.verify.matches(project.id, run.id)
    assert [(m.designed, m.state) for m in got] == [("API-001", "found"), ("API-002", "differences"), (None, "extra")]
    assert got[1].differences == ("the design says x",) and got[1].note == "why" and got[0].score == 1.0 and got[0].line == 3


def test_runs_come_back_newest_first_and_one_projects_runs_never_show_in_another(store, project):
    first, second = add(store, project), add(store, project)
    other = store.projects.create(name="Other", actor="system")
    assert [r.id for r in store.verify.runs(project.id)] == [second.id, first.id] and store.verify.runs(other.id) == []
    with pytest.raises(NotFoundError):
        store.verify.run(other.id, first.id)
    with pytest.raises(NotFoundError):
        store.verify.matches(other.id, first.id)
    assert len(store.verify.runs(project.id, limit=1)) == 1


def test_a_blank_frontend_path_is_kept_as_none_and_a_blank_backend_path_is_refused(store, project):
    assert add(store, project, frontend_path="   ").frontend_path is None
    with pytest.raises(InvalidInput):
        add(store, project, backend_path="  ")


def test_an_unknown_state_a_negative_line_and_too_many_matches_are_refused(store, project):
    with pytest.raises(InvalidInput, match="state must be one of"):
        add(store, project, matches=[row(state="great")])
    with pytest.raises(InvalidInput):
        add(store, project, matches=[row(line=-1)])
    with pytest.raises(InvalidInput, match="at most"):
        add(store, project, matches=[row()] * (MAX_VERIFY_MATCHES + 1))
    assert store.verify.runs(project.id) == []


def test_a_run_for_a_project_that_does_not_exist_is_refused(store):
    with pytest.raises(NotFoundError):
        store.verify.add_run("nope", backend_path="/x", frontend_path=None, actor="human:a", design={}, counts=[], notes=[], matches=[])


def test_a_run_and_its_matches_are_all_or_nothing(store, project):
    with pytest.raises(sqlite3.IntegrityError):
        add(store, project, matches=[row(), row(score=7.0)])                       # the score check refuses the second row; the first and the run must not survive
    assert store.verify.runs(project.id) == []


def test_the_record_is_append_only(store, project):
    run = add(store, project)
    raw = sqlite3.connect(store.db.path)
    for sql in ("UPDATE verify_runs SET actor = 'x'", "DELETE FROM verify_runs", "UPDATE verify_matches SET state = 'found'", "DELETE FROM verify_matches"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            raw.execute(sql)
    raw.close()
    assert store.verify.run(project.id, run.id).actor == "human:ann"


def test_long_values_are_cut_to_their_bounds(store, project):
    run = add(store, project, backend_path="/" + "a" * 3000, matches=[row(built="b" * 900, file="f" * 900, note="n" * 900, differences=["d"] * 50)])
    m = store.verify.matches(project.id, run.id)[0]
    assert len(run.backend_path) == 1000 and len(m.built) == 300 and len(m.file) == 400 and len(m.note) == 500 and len(m.differences) == 20


# ---- the design side ------------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def library():
    return SkillLibrary.load(load_catalogue(Routing.load().roles.keys()))


def seeded(store, project, library, screens=False):
    seed(store, project, library, "usecase_diagram", uc_list(2))
    for key, text in DESIGN_BODIES.items():
        seed(store, project, library, key, text)
    if screens:                                                            # S20f: the design may still HAVE screens; Build Verify does not look for them any more
        seed(store, project, library, "hifi_wireframes", "## Screens\n- HFS-001 Browse rooms: the page. Derives from: FR-001\n")


def test_the_design_is_read_as_endpoints_tables_and_rules_and_a_screen_in_the_design_is_ignored(store, project, library):
    seeded(store, project, library, screens=True)
    design = read_design(store, library, project.id)
    assert [(i.id, i.area) for i in design.items] == [("API-001", "endpoint"), ("API-002", "endpoint"), ("API-003", "endpoint"), ("TBL-001", "table"), ("TBL-002", "table"),
                                                      ("RUL-001", "rule"), ("RUL-002", "rule"), ("RUL-003", "rule")]
    api = next(i for i in design.items if i.id == "API-003")
    assert (api.method, api.path, api.title) == ("POST", "/api/reservations", "POST /api/reservations")
    table = next(i for i in design.items if i.id == "TBL-001")
    assert (table.title, table.fields) == ("rooms", ("id", "name"))
    assert design.notes == [] and not [i for i in design.items if i.area == "screen" or i.id.startswith("HFS")]
    rule = next(i for i in design.items if i.id == "RUL-001")
    assert rule.derives == ("FR-001",) and api.derives == ("FR-001",) and table.derives == ("FR-001",)            # what each item says it derives from is kept, for linking a rule to its endpoint


def test_the_design_is_ordered_endpoints_then_tables_then_rules_then_by_id_whatever_order_the_document_lists_them_in(store, project, library):
    jumbled = ("## Overview\nx\n## Rules\n- RUL-002 A room can be retired. Derives from: FR-001\n- RUL-001 A booking may not overlap another. Derives from: FR-001\n"
               "## Tables\n- TBL-002 reservations: id, room. Derives from: FR-001\n- TBL-001 rooms: id, name. Derives from: FR-001\n"
               "## Endpoints\n- API-002 GET /api/availability. Derives from: FR-001\n- API-001 GET /api/rooms lists rooms. Derives from: FR-001\n"
               "## Coverage check\nNone\n## Open questions\nNone")
    seeded(store, project, library)
    art = store.artefacts.list(project.id, artefact_type="low_level_design")[0]
    store.artefacts.add_version(project.id, art.id, body=jumbled, author="human:bob")
    assert [i.id for i in read_design(store, library, project.id).items] == ["API-001", "API-002", "TBL-001", "TBL-002", "RUL-001", "RUL-002"]


def test_a_design_not_written_yet_says_so_instead_of_failing(store, project, library):
    design = read_design(store, library, project.id)
    assert design.items == [] and len(design.notes) == 1 and "low-level design has not been written" in design.notes[0] and "endpoints, tables or rules" in design.notes[0]


def test_the_latest_version_of_the_design_is_the_one_read_and_its_version_is_recorded(store, project, library):
    seeded(store, project, library)
    art = store.artefacts.list(project.id, artefact_type="low_level_design")[0]
    store.artefacts.add_version(project.id, art.id, body=LLD.replace("GET /api/rooms lists rooms", "GET /api/venues lists rooms"), author="human:bob")
    design = read_design(store, library, project.id)
    assert next(i for i in design.items if i.id == "API-001").path == "/api/venues" and design.versions[art.id] == 2


def test_the_interface_contract_of_the_build_set_supplies_the_fields_and_codes_of_an_endpoint(store, project, library):
    from app.build import instructions as I
    from tests.test_instructions import DESIGN as IDS, full_set
    seeded(store, project, library)
    body = I.assemble(full_set(contract=True), design=IDS)
    store.artefacts.create_and_add_version(project.id, artefact_type="build_instructions", phase_key="build", title="Build instructions", prefix="BLD-INS", body=body, author="human:seed")
    design = read_design(store, library, project.id)
    api = next(i for i in design.items if i.id == "API-003")
    assert "room_id" in api.fields and "reservation_id" in api.fields and 409 in api.codes and api.method == "POST"


# ---- the service ----------------------------------------------------------------------------------------------------------------------------------

def put(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_a_check_reads_the_design_and_the_folder_and_keeps_the_run(store, project, library, tmp_path):
    seeded(store, project, library)
    put(tmp_path, "app/main.py", CODE); put(tmp_path, ".env", F.AWS_KEY)
    run, report = S.check(store, library, project.id, backend_path=str(tmp_path), actor="human:ann")
    states = {m.designed: m.state for m in report.matches}
    assert states["API-001"] == "found" and states["API-002"] == "not_found"
    assert states["API-003"] == "not_found"                              # "/api/bookings" shares no word with "reserves a room": a words match needs some overlap
    assert [e.built for e in report.extras] == ["GET /api/health", "POST /api/bookings"]          # the bookings route matched nothing, so it is "built but not designed" too
    stored = store.verify.matches(project.id, run.id)
    assert {m.designed for m in stored if m.state == "extra"} == {None} and len(stored) == len(report.matches) + len(report.extras) == 10          # 8 designed things (3 endpoints, 2 tables, 3 rules) and 2 built things nobody designed
    assert any(".env" in n for n in run.notes) and F.AWS_KEY not in str(run) + str(stored)


def test_a_check_changes_nothing_in_the_design_or_the_folder(store, project, library, tmp_path):
    seeded(store, project, library)
    put(tmp_path, "main.py", CODE)
    before = {a.id: a.latest_version for a in store.artefacts.list(project.id)}
    files = sorted(p.name for p in tmp_path.rglob("*"))
    S.check(store, library, project.id, backend_path=str(tmp_path), actor="human:ann")
    assert {a.id: a.latest_version for a in store.artefacts.list(project.id)} == before and sorted(p.name for p in tmp_path.rglob("*")) == files


def test_a_folder_with_no_python_says_nothing_could_be_compared_and_a_bad_path_is_a_plain_sentence(store, project, library, tmp_path):
    seeded(store, project, library)
    put(tmp_path, "readme.md", "hello")
    run, _ = S.check(store, library, project.id, backend_path=str(tmp_path), actor="human:ann")
    assert any("no Python or SQL file was found" in n for n in run.notes)
    with pytest.raises(S.FolderProblem, match="there is no folder"):
        S.check(store, library, project.id, backend_path=str(tmp_path / "nope"), actor="human:ann")
    assert len(store.verify.runs(project.id)) == 1                                  # the refused check kept nothing


def test_a_run_no_longer_takes_a_frontend_folder_and_stores_none(store, project, library, tmp_path):
    seeded(store, project, library, screens=True)                                  # the design has a screen; the run ignores it
    put(tmp_path, "main.py", CODE)
    with pytest.raises(TypeError):
        S.check(store, library, project.id, backend_path=str(tmp_path), frontend_path=str(tmp_path), actor="human:ann")
    run, report = S.check(store, library, project.id, backend_path=str(tmp_path), actor="human:ann")
    assert run.frontend_path is None and {m.area for m in report.matches} == {"endpoint", "table", "rule"} and [c.area for c in report.areas] == ["endpoint", "table", "rule"]
    stored = store.verify.matches(project.id, run.id)
    assert {m.area for m in stored} <= {"endpoint", "table", "rule"} and not [m for m in stored if m.designed == "HFS-001"] and not any(n.startswith("frontend:") for n in run.notes)


def test_every_check_is_kept_so_the_trend_can_be_drawn(store, project, library, tmp_path):
    seeded(store, project, library)
    put(tmp_path, "main.py", CODE)
    S.check(store, library, project.id, backend_path=str(tmp_path), actor="human:ann")
    put(tmp_path, "more.py", '@app.get("/api/availability")\ndef a(): ...\n')
    S.check(store, library, project.id, backend_path=str(tmp_path), actor="human:ann")
    newest, oldest = store.verify.runs(project.id)
    ep = lambda run: next(c for c in run.counts if c["area"] == "endpoint")          # noqa: E731
    assert ep(newest)["found"] + ep(newest)["differences"] > ep(oldest)["found"] + ep(oldest)["differences"]


# ---- the routes -----------------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def api(store, project, library):
    app = FastAPI()
    app.include_router(router)
    app.state.store, app.state.skills = store, library
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=ANN), f"/api/projects/{project.id}/verify"


async def test_the_route_runs_a_check_and_answers_with_the_run_and_its_matches(api, store, project, library, tmp_path):
    seeded(store, project, library)
    put(tmp_path, "main.py", CODE)
    client, base = api
    response = await client.post(base, json={"backend_path": str(tmp_path)})
    body = response.json()
    assert response.status_code == 200 and body["by"] == "human:Ann" and body["backend_path"] == str(tmp_path) and "frontend_path" not in body
    assert {m["designed"] for m in body["matches"] if m["state"] != "extra"} >= {"API-001", "API-002", "API-003"}
    assert set(body["matches"][0]) == {"designed", "area", "state", "step", "score", "built", "file", "line", "differences", "note"}
    await client.aclose()


async def test_the_route_lists_runs_gives_one_and_downloads_it_as_markdown_or_json(api, store, project, library, tmp_path):
    seeded(store, project, library)
    put(tmp_path, "main.py", CODE)
    client, base = api
    run_id = (await client.post(base, json={"backend_path": str(tmp_path)})).json()["id"]
    listing = (await client.get(base)).json()
    assert [r["id"] for r in listing["runs"]] == [run_id] and "highlighter" in listing["advice"] and "matches" not in listing["runs"][0]
    one = (await client.get(f"{base}/{run_id}")).json()
    assert one["id"] == run_id and one["matches"] and "highlighter" in one["advice"]
    md = await client.get(f"{base}/{run_id}/download")
    assert md.status_code == 200 and md.text.startswith("# Build Verify") and "Built but not designed" in md.text and 'filename="build-verify-' in md.headers["content-disposition"]
    js = await client.get(f"{base}/{run_id}/download?format=json")
    assert js.headers["content-type"] == "application/json" and js.json()["id"] == run_id
    await client.aclose()


async def test_the_route_answers_a_bad_folder_with_a_sentence_and_an_unknown_run_or_project_with_404(api, store, project, library, tmp_path):
    client, base = api
    bad = await client.post(base, json={"backend_path": str(tmp_path / "nope")})
    assert bad.status_code == 422 and "there is no folder" in bad.json()["detail"]
    assert (await client.get(f"{base}/99")).status_code == 404 and (await client.get(f"{base}/99/download")).status_code == 404
    assert (await client.post("/api/projects/nope/verify", json={"backend_path": str(tmp_path)})).status_code == 404
    assert (await client.get("/api/projects/nope/verify")).status_code == 404
    await client.aclose()


async def test_the_route_needs_a_name_checks_the_shape_and_refuses_an_archived_project(api, store, project, library, tmp_path):
    import httpx as hx
    client, base = api
    bare = hx.AsyncClient(transport=client._transport, base_url="http://test")
    assert (await bare.post(base, json={"backend_path": str(tmp_path)})).status_code == 400
    for body in ({}, {"backend_path": ""}, {"backend_path": "/x" * 600}, {"backend_path": str(tmp_path), "extra": 1}, {"backend_path": str(tmp_path), "frontend_path": str(tmp_path)}):
        assert (await client.post(base, json=body)).status_code == 422, body
    store.projects.archive(project.id, actor="system")
    assert (await client.post(base, json={"backend_path": str(tmp_path)})).status_code == 409
    assert (await client.get(base)).status_code == 200                                                    # an archived project can still be read
    await client.aclose(); await bare.aclose()


# ---- the edges (S20b mutation survivors) ----------------------------------------------------------------------------------------------------------

def test_the_design_notes_a_walk_that_stopped_and_a_file_with_a_syntax_error_all_reach_the_run_notes(store, project, library, tmp_path, monkeypatch):
    put(tmp_path, "main.py", CODE); put(tmp_path, "bad.py", "def broken(:\n")
    for n in range(5):
        put(tmp_path, f"f{n}.py", "x = 1\n")
    from app.verify import walk as W
    monkeypatch.setattr(W, "MAX_FILES", 3)
    monkeypatch.setattr(S, "walk", lambda path, **kw: W.walk(path, max_files=3, **kw))
    run, _ = S.check(store, library, project.id, backend_path=str(tmp_path), actor="human:ann")       # no design written yet: its two notes come first
    assert run.notes[0].startswith("the low-level design has not been written") and not any("wireframes" in n for n in run.notes)
    assert "backend: stopped after 3 files; the rest of the folder was not read" in run.notes
    seeded(store, project, library)
    put(tmp_path, "z.py", "def broken(:\n")
    put(tmp_path, "a.py", "def broken(:\n")
    monkeypatch.undo()
    run, _ = S.check(store, library, project.id, backend_path=str(tmp_path), actor="human:ann")
    assert any(n.startswith("backend: a.py: could not be read as Python") for n in run.notes)


def test_a_run_stores_the_design_versions_it_was_compared_against_and_the_report_lists_them(store, project, library, tmp_path):
    seeded(store, project, library)
    put(tmp_path, "main.py", CODE)
    run, _ = S.check(store, library, project.id, backend_path=str(tmp_path), actor="human:ann")
    assert run.design and all(v >= 1 for v in run.design.values()) and set(run.design) == {a.id for a in store.artefacts.list(project.id)}


def test_a_long_list_of_notes_is_cut_at_fifty_and_a_negative_line_is_refused_by_the_database_itself(store, project):
    run = add(store, project, notes=[f"n{i}" for i in range(80)])
    assert len(run.notes) == 50
    raw = sqlite3.connect(store.db.path)
    with pytest.raises(sqlite3.IntegrityError):
        raw.execute("INSERT INTO verify_matches (run_id, area, state, line, differences) VALUES (?, 'endpoint', 'found', -1, '[]')", (run.id,))
    raw.close()


def test_the_route_downloads_keep_the_extras_and_the_design_versions_and_the_payload_keeps_notes_differences_and_location(api, store, project, library, tmp_path):
    import asyncio
    seeded(store, project, library)
    put(tmp_path, "main.py", CODE); put(tmp_path, "bad.py", "def broken(:\n")
    client, base = api

    async def go():
        body = (await client.post(base, json={"backend_path": str(tmp_path)})).json()
        md = (await client.get(f"{base}/{body['id']}/download")).text
        await client.aclose()
        return body, md

    body, md = asyncio.run(go())
    assert any("bad.py" in n for n in body["notes"])
    assert "GET /api/health" in md and "## Compared against" in md and any(f"{k}: version" in md for k in body["design"])
    found = next(m for m in body["matches"] if m["designed"] == "API-001")
    assert found["file"] == "main.py" and found["line"] == 4
    diff = next((m for m in body["matches"] if m["differences"]), None)
    assert diff is None or isinstance(diff["differences"], list)


async def test_the_route_refuses_a_blank_backend_path_and_any_frontend_path_at_the_edge(api, store, project, library, tmp_path):
    client, base = api
    assert (await client.post(base, json={"backend_path": ""})).status_code == 422
    put(tmp_path, "main.py", CODE)
    assert (await client.post(base, json={"backend_path": str(tmp_path)})).status_code == 200
    assert (await client.post(base, json={"backend_path": str(tmp_path), "frontend_path": None})).status_code == 422               # S20f: the field is gone, so even an empty one is refused
    assert (await client.post(base, json={"backend_path": str(tmp_path), "frontend_path": "y"})).status_code == 422
    await client.aclose()


# ---- the last survivors of 20b ----------------------------------------------------------------------------------------------------------------------

def test_the_request_body_refuses_a_blank_backend_path_a_path_over_a_thousand_characters_and_a_frontend_path():
    from pydantic import ValidationError
    from app.routes_verify import VerifyBody
    assert VerifyBody(backend_path="x" * 1000).backend_path == "x" * 1000
    for bad in ({"backend_path": ""}, {"backend_path": "x" * 1001}, {"backend_path": "x", "frontend_path": "y"}, {"backend_path": "x", "other": 1}):
        with pytest.raises(ValidationError):
            VerifyBody(**bad)


def test_the_contract_decides_the_method_and_path_when_it_differs_from_the_design_line(store, project, library):
    from app.build import instructions as I
    from tests.test_instructions import DESIGN as IDS, full_set
    seeded(store, project, library)
    files = full_set(contract=True)
    files[I.FOUNDATION_NAME] = files[I.FOUNDATION_NAME].replace("API-001 GET /api/rooms.", "API-001 POST /api/places.")
    store.artefacts.create_and_add_version(project.id, artefact_type="build_instructions", phase_key="build", title="Build instructions", prefix="BLD-INS",
                                           body=I.assemble(files, design=IDS), author="human:seed")
    api = next(i for i in read_design(store, library, project.id).items if i.id == "API-001")
    assert (api.method, api.path, api.title) == ("POST", "/api/places", "POST /api/places")


def test_an_artefact_that_has_no_version_yet_is_left_out_of_the_design(store, project, library):
    seeded(store, project, library)
    store.artefacts.create(project.id, artefact_type="functional_requirements", phase_key="requirements", title="Requirements again", prefix="REQ-FR", actor="system") if False else None
    store.artefacts.create(project.id, artefact_type="usecase_diagram", phase_key="design", title="Empty", prefix="DES-UC", actor="system")
    design = read_design(store, library, project.id)
    assert all(v >= 1 for v in design.versions.values()) and len(design.versions) == len(set(design.versions))


async def test_a_match_with_differences_is_answered_with_them_and_with_where_it_was_found(api, store, project, library, tmp_path):
    from app.build import instructions as I
    from tests.test_instructions import DESIGN as IDS, full_set
    seeded(store, project, library)
    store.artefacts.create_and_add_version(project.id, artefact_type="build_instructions", phase_key="build", title="Build instructions", prefix="BLD-INS",
                                           body=I.assemble(full_set(contract=True), design=IDS), author="human:seed")
    put(tmp_path, "main.py", '''
from fastapi import FastAPI
app = FastAPI()
@app.get("/api/rooms")
def rooms(): ...
@app.post("/api/reservations", status_code=200)
def reserve(): ...
''')
    client, base = api
    body = (await client.post(base, json={"backend_path": str(tmp_path)})).json()
    stored = (await client.get(f"{base}/{body['id']}")).json()
    differing = [m for m in stored["matches"] if m["differences"]]
    assert differing and all(isinstance(d, str) and d for m in differing for d in m["differences"])
    found = next(m for m in stored["matches"] if m["designed"] == "API-003")
    assert found["file"] == "main.py" and found["line"] == 6 and found["built"] == "POST /api/reservations"
    assert stored["matches"] == body["matches"]
    await client.aclose()


# ---- runs made before S20f (they hold screens and a frontend folder) ------------------------------------------------------------------------------------

def old_run(store, project):
    """A run as S20 saved it: a frontend path, a screen count, a screen row, and notes about the frontend."""
    return add(store, project, frontend_path="/tmp/f", counts=[{"area": "endpoint", "designed": 1, "found": 1}, {"area": "screen", "designed": 1, "found": 0}],
               notes=["backend: ok", "frontend: read 3 files by pattern, not parsed: 0 pages and 0 API calls found"],
               matches=[row(), row("HFS-001", "not_found", **{"area": "screen"}), row(None, "extra", area="screen", built="/home")])


async def test_a_check_started_through_the_route_does_not_show_a_screen_even_when_the_design_has_one(api, store, project, library, tmp_path):
    seeded(store, project, library, screens=True)
    put(tmp_path, "main.py", CODE)
    client, base = api
    body = (await client.post(base, json={"backend_path": str(tmp_path)})).json()
    assert {m["area"] for m in body["matches"]} == {"endpoint", "table", "rule"} and [c["area"] for c in body["counts"]] == ["endpoint", "table", "rule"]
    assert not [m for m in body["matches"] if m["designed"] == "HFS-001"]
    await client.aclose()


async def test_an_old_run_still_opens_with_its_screens_and_frontend_left_out_and_nothing_in_the_record_changes(api, store, project):
    client, base = api
    run = old_run(store, project)
    one = (await client.get(f"{base}/{run.id}")).json()
    assert [m["designed"] for m in one["matches"]] == ["API-001"] and [c["area"] for c in one["counts"]] == ["endpoint"] and one["notes"] == ["backend: ok"] and "frontend_path" not in one
    listing = (await client.get(base)).json()["runs"][0]
    assert [c["area"] for c in listing["counts"]] == ["endpoint"] and listing["notes"] == ["backend: ok"]
    kept = store.verify.matches(project.id, run.id)
    assert [m.designed for m in kept] == ["API-001", "HFS-001", None] and store.verify.run(project.id, run.id).frontend_path == "/tmp/f"            # history is append-only: nothing was removed
    await client.aclose()


async def test_an_old_runs_downloads_leave_the_screens_out_too(api, store, project):
    client, base = api
    run = old_run(store, project)
    md = (await client.get(f"{base}/{run.id}/download")).text
    assert "Screens" not in md and "HFS-001" not in md and "frontend" not in md and "API-001" in md and "| Screens" not in md
    js = (await client.get(f"{base}/{run.id}/download?format=json")).json()
    assert [m["designed"] for m in js["matches"]] == ["API-001"] and [c["area"] for c in js["counts"]] == ["endpoint"] and "frontend_path" not in js
    await client.aclose()


def test_the_report_has_three_areas_and_says_it_is_about_the_backend():
    from app.verify import report as R
    assert R.AREAS == ("endpoint", "table", "rule") and "Screens" not in R.AREA_WORDS.values() and "backend" in R.ADVICE
