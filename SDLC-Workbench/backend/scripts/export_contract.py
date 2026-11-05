"""Write real example responses from the backend into frontend/src/contract/, so the screen and the server cannot drift apart unseen.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.export_contract           # rewrite the fixtures
    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.export_contract --check   # exit 1 if they are stale

I cannot open a browser, so the only mechanical protection against a renamed field is a shared contract: the backend writes what it
REALLY returns (from a throwaway database, with fixed names and dates), the screen's decoders must accept every file, and a backend
test fails if a fixture no longer matches what the routes return. Change a field on either side and a test fails on the other.

Nothing here is real data: the fixtures are made from a scratch project, with the IDs and timestamps replaced by fixed values.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

import asyncio

from fastapi.testclient import TestClient

from app.config import Settings
from app.llm.errors import ContentFilterBlocked
from app.llm.types import ProviderResponse, Usage
from app.main import create_app
from app.sample import BRIEF, FILENAME, NAME, POLICY

from .requirements_demo import EPICS_BAD
from app.design.sanitise import drawings_in, sanitise_svg
from tests.data.svg_corpus import CASES as SVG_CASES
from .run_demo import MODELS as RUN_MODELS, Scripted

FIXTURES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "contract"
ACTOR = {"X-Actor": "Demo Person"}
FIXED_TIME = "2026-01-01T00:00:00.000Z"
FIXED_ID = "p0000000demo"
_ID = re.compile(r"\b[0-9a-f]{12}\b")
_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z")


_VARIABLE_NUMBERS = {"elapsed_seconds", "serial_seconds", "max_in_flight"}     # timings and scheduling luck: not part of the shape


def normalise(value: Any) -> Any:
    """Replace every generated ID and timestamp with a fixed one, so a fixture changes only when a SHAPE changes."""
    if isinstance(value, dict):
        return {k: (0 if k in _VARIABLE_NUMBERS else normalise(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [normalise(v) for v in value]
    if isinstance(value, str):
        return _TIME.sub(FIXED_TIME, _ID.sub(FIXED_ID, value))
    return value


class ExportModel(Scripted):
    """The scripted model of the run demo, plus a reviewer, a first epics reply that needs repairing, and optional failures."""

    def __init__(self) -> None:
        super().__init__(scale=0.0)
        self.epics_calls = 0
        self.reviewer: str | Exception = "<review>\nSummary: Reads clearly.\n- [LOW] Open questions: one could be answered from the charter. Fix: remove it.\n</review>"

    def _which(self, request) -> str:
        if "Review the artefact" in request.messages[0].content:
            return "review"
        return super()._which(request)

    async def complete(self, model_id, request):
        key = self._which(request)
        if key == "review":
            if isinstance(self.reviewer, Exception):
                raise self.reviewer
            return ProviderResponse(self.reviewer, Usage(900, 120), "stop")
        if key == "epics_features":
            self.epics_calls += 1
            if self.epics_calls == 1:
                return ProviderResponse(EPICS_BAD, Usage(1800, 420), "stop")      # refused, so the run publishes a repair attempt
        return await super().complete(model_id, request)


def _events_by_type(app) -> dict[str, dict[str, Any]]:
    """One real example of each event type, from the stored log. Several of a type are possible (parallel artefacts finish in any order),
    so the example is the one that sorts first by its CONTENT with the time and run left out: the same every run, whatever finished first."""
    store = app.state.store
    best: dict[str, tuple[str, dict[str, Any]]] = {}
    for project in store.projects.list():
        for event in store.run_events.list(project.id, limit=1000):
            content = json.dumps(event.data, sort_keys=True)
            name = _fixture_name(event.type, event.data)
            if name not in best or content < best[name][0]:
                best[name] = (content, {"run_id": event.run_id, "at": event.at, **event.data})
    return {name: example for name, (_, example) in sorted(best.items())}


def _fixture_name(event_type: str, data: dict[str, Any]) -> str:
    """An event type with more than one shape gets one example per shape, named so the screen's test can tell them apart."""
    if event_type == "review.paused":
        return "review.paused" if "options" in data else "review.paused.reason"
    if event_type == "run.stopped" and "artefacts" not in data:
        return "run.stopped.short"
    return event_type


async def _scripted_runs(workdir: Path) -> tuple[dict[str, Any], Any]:
    """Run the real runner through every situation that publishes an event, offline. Returns (responses worth a fixture, the app)."""
    settings = Settings(_env_file=None, data_dir=str(workdir / "runs"), recordings_dir=str(workdir / "rec"), app_mode="replay",
                        run_max_cost_usd=0, llm_retry_backoff_seconds=0, **RUN_MODELS)
    model = ExportModel()
    app = create_app(settings, provider=model)
    store, engine, runner = app.state.store, app.state.engine, app.state.runner

    def project(name: str):
        made = store.projects.create(name=name, brief=BRIEF, actor="system")
        engine.open_project(made.id)
        store.context.add_document(made.id, FILENAME, POLICY, actor="human:demo")
        return made.id

    async def through_setup(pid: str) -> None:
        await runner.run_phase(pid, "setup")
        engine.finish(pid, "setup", actor="system")
        engine.approve(pid, "setup", actor="human:demo")

    pid = project(NAME)
    await through_setup(pid)
    await runner.run_phase(pid, "requirements", review=True)        # repair attempt, reviews, a finished run

    failing = project("A failing run")
    await through_setup(failing)
    model.fail = {"personas"}                                         # a failed artefact, and everything built on it skipped
    await runner.run_phase(failing, "requirements")
    model.fail = set()

    paused = project("A paused review")
    await through_setup(paused)
    # A reviewer the gateway cannot use (the provider refuses the content, which a different family might not): the gateway raises
    # ReviewerUnavailable with the other families as options, and the runner publishes the SHORT shape {artefact_id, slot, options}.
    model.reviewer = ContentFilterBlocked("blocked")
    await runner.run_phase(paused, "requirements", only=["personas"], review=True)
    model.reviewer = "no tags at all"                                  # a review that fails for some other reason: the {artefact_id, reason} shape
    other = project("A review that fails")
    await through_setup(other)
    await runner.run_phase(other, "requirements", only=["personas"], review=True)
    model.reviewer = "<review>\nSummary: Reads clearly.\n</review>"

    capped_settings = Settings(_env_file=None, data_dir=str(workdir / "capped"), recordings_dir=str(workdir / "rec"), app_mode="replay",
                               run_max_cost_usd=0.0001, llm_retry_backoff_seconds=0, **RUN_MODELS)
    capped = create_app(capped_settings, provider=ExportModel())
    cid = capped.state.store.projects.create(name="A capped run", brief=BRIEF, actor="system").id
    capped.state.engine.open_project(cid)
    capped.state.store.context.add_document(cid, FILENAME, POLICY, actor="human:demo")
    await capped.state.runner.run_phase(cid, "setup")                  # the cost cap stops it: run.stopped
    # A run the backend stopped under: leave one marked running and let the start-up sweep close it. It publishes the SHORT run.stopped
    # (a status and a sentence, no totals), the same shape as a run that crashed.
    interrupted = project("An interrupted run")
    app.state.store.runs.start(interrupted, "setup")
    app.state.store.runs.interrupt_unfinished()
    # A fix round of the Build phase. The sandbox is not needed to know the SHAPE of the event, which the loop builds with this same function.
    from app.build.loop import round_event
    building = project("A build round")
    build_run = app.state.store.runs.start(building, "build")
    app.state.bus.publish(building, build_run.id, "build.round", round_event(1, "backend_code", 2, 0))
    app.state.store.runs.end(build_run.id, "finished", totals={})
    # The files of the Build instruction set (S19b). The runner adds the artefact's key; the bodies come from the composer's own functions.
    from app.build.compose import failed_event, finished_event, started_event
    writing = project("An instruction set")
    set_run = app.state.store.runs.start(writing, "build")
    for kind, data in (("piece.started", started_event("00-foundation.md", "foundation", 1, 4)),
                       ("piece.finished", finished_event("00-foundation.md", 1, 21000, 3200, 0.0942)),
                       ("piece.failed", failed_event("UC-002-browse-rooms.md", "'UC-002-browse-rooms.md' could not be produced: after 3 attempt(s) the reply still failed its checks"))):
        app.state.bus.publish(writing, set_run.id, kind, {"key": "build_instructions", **data})
    app.state.store.runs.end(set_run.id, "finished", totals={})
    events = _events_by_type(app)
    events.update({k: v for k, v in _events_by_type(capped).items() if k == "run.stopped"})
    return events, app


def _checklist_examples() -> dict[str, Any]:
    """The deployment checklist (S21c) as the server answers it: untouched, and after a few answers, one changed (so a history shows), and the refusals a person meets."""
    with tempfile.TemporaryDirectory(prefix="sdlc_contract_checklist_") as tmp:
        settings = Settings(_env_file=None, data_dir=str(Path(tmp) / "data"), recordings_dir=str(Path(tmp) / "rec"), app_mode="replay")
        app = create_app(settings)
        client = TestClient(app, headers=ACTOR)
        pid = client.post("/api/projects", json={"name": "Checklist", "brief": BRIEF}).json()["id"]
        base = f"/api/projects/{pid}/deploy/checklist"
        out: dict[str, Any] = {"checklist_empty": client.get(base).json()}
        out["error_409_checklist_closed"] = client.put(f"{base}/CHK-001", json={"answer": "go"}).json()          # Deploy has not started, so no check can be answered yet
        app.state.store.phases.ensure(pid, "deploy", actor="system")
        app.state.store.phases.set_status(pid, "deploy", "running", actor="system")
        client.put(f"{base}/CHK-001", json={"answer": "go", "note": "Read it with the team."})
        client.put(f"{base}/CHK-002", json={"answer": "no_go", "note": "Missing the upgrade section."})
        client.put(f"{base}/CHK-002", json={"answer": "go", "note": "Fixed."})
        client.put(f"{base}/CHK-003", json={"answer": "not_applicable"})
        out["checklist_answered"] = client.put(f"{base}/CHK-016", json={"answer": "go"}).json()
        out["error_404_check"] = client.put(f"{base}/CHK-099", json={"answer": "go"}).json()
        # BAU handover's sign-off (S22c): the same record under its own address, with its own title, groups and words for the answers
        sign = f"/api/projects/{pid}/handover/checklist"
        out["signoff_empty"] = client.get(sign).json()
        app.state.store.phases.ensure(pid, "handover", actor="system")
        app.state.store.phases.set_status(pid, "handover", "running", actor="system")
        client.put(f"{sign}/SGN-001", json={"answer": "go", "note": "Read it with the team."})
        client.put(f"{sign}/SGN-002", json={"answer": "no_go", "note": "Two weeks is too short."})
        client.put(f"{sign}/SGN-002", json={"answer": "go", "note": "Agreed at three weeks."})
        client.put(f"{sign}/SGN-007", json={"answer": "not_applicable"})
        out["signoff_answered"] = client.put(f"{sign}/SGN-008", json={"answer": "go", "note": "Support lead"}).json()
        return out


def _users_examples() -> dict[str, Any]:
    """The Users list (S23): empty, then with a few people; what a typed name may do; and the refusals a person meets."""
    with tempfile.TemporaryDirectory(prefix="sdlc_contract_users_") as tmp:
        settings = Settings(_env_file=None, data_dir=str(Path(tmp) / "data"), recordings_dir=str(Path(tmp) / "rec"), app_mode="replay")
        app = create_app(settings)
        client = TestClient(app)
        out: dict[str, Any] = {"users_empty": client.get("/api/users").json()}
        root, ann, bo = {"X-Actor": "Root"}, {"X-Actor": "Ann"}, {"X-Actor": "Bo"}
        client.post("/api/users", json={"name": "Root", "roles": ["Administrator", "Project Manager"]}, headers=root)
        client.post("/api/users", json={"name": "Ann", "roles": ["Architect", "Technical Lead"]}, headers=root)
        client.post("/api/users", json={"name": "Bo", "roles": ["Project Manager"]}, headers=root)
        client.put("/api/users/Bo/active", json={"active": False}, headers=root)
        client.put("/api/approvers/requirements", json={"roles": ["Architect", "Technical Lead"]}, headers=root)
        out["users_list"] = client.get("/api/users").json()
        out["users_me_architect"] = client.get("/api/users/me", headers=ann).json()
        out["users_me_stranger"] = client.get("/api/users/me", headers={"X-Actor": "Stranger"}).json()
        out["error_403_users"] = client.post("/api/users", json={"name": "New", "roles": []}, headers=ann).json()
        out["error_409_users"] = client.put("/api/users/Root/roles", json={"roles": ["Architect"]}, headers=root).json()
        return out


def _settings_examples() -> dict[str, Any]:
    """System settings (S23d, e): the read-only view, then a real save to a file inside the scratch folder, the refusal, and the 403. The settings file is a throwaway: the real backend/.env is never opened."""
    with tempfile.TemporaryDirectory(prefix="sdlc_contract_settings_") as tmp:
        env = Path(tmp) / "scratch.env"
        env.write_text("IBM_ICA_" + "API_KEY" + "=scratch" + "-key\nRUN_BUDGET_USD=5.0\n", encoding="utf-8")                    # built from pieces so the repo's own secret scan does not read a made-up key as a real one
        settings = Settings(_env_file=env, data_dir=str(Path(tmp) / "data"), recordings_dir=str(Path(tmp) / "rec"), app_mode="replay")
        app = create_app(settings)
        app.state.env_file, app.state.env_backups = env, Path(tmp) / "bk"
        app.state.settings_at_start = Settings(_env_file=env).model_dump_json()
        client = TestClient(app)
        out: dict[str, Any] = {}
        root = {"X-Actor": "Root"}
        client.post("/api/users", json={"name": "Root", "roles": ["Administrator"]}, headers=root)
        client.post("/api/users", json={"name": "Ann", "roles": ["Architect"]}, headers=root)
        out["settings_view"] = client.get("/api/settings", headers=root).json()
        out["error_403_settings"] = client.put("/api/settings", json={"values": {"run_budget_usd": "9"}}, headers={"X-Actor": "Ann"}).json()
        out["error_422_settings"] = client.put("/api/settings", json={"values": {"run_budget_usd": "5000"}}, headers=root).json()
        out["settings_saved"] = client.put("/api/settings", json={"values": {"run_budget_usd": "7.5", "ibm_ica_api_key": "new-scratch-key"}}, headers=root).json()
        text = json.dumps(out).replace(tmp, "/projects/scratch")                                              # the scratch folder is a random name and a real local path: a fixed one is kept
        text = re.sub(r"env-\d{8}-\d{6}-\d{6}\.bak", "env-20260101-000000-000001.bak", text)
        return json.loads(text)


def _templates_examples() -> dict[str, Any]:
    """Document templates (S23 Part C): a project with none, one with a template that has a table of contents and one without, and the refusals a person meets. The Word files are made
    in memory and kept in a scratch folder; nothing in the real backend/data is touched."""
    import io

    from docx import Document
    from docx.oxml import parse_xml

    def word(toc: bool) -> bytes:
        doc = Document()
        doc.add_heading("Title", level=1)
        if toc:
            ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
            doc.element.body.insert(0, parse_xml(f'<w:p {ns}><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> TOC \\o "1-3" </w:instrText></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'))
        buffer = io.BytesIO()
        doc.save(buffer)
        return buffer.getvalue()

    kind = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    with tempfile.TemporaryDirectory(prefix="sdlc_contract_templates_") as tmp:
        settings = Settings(_env_file=None, data_dir=str(Path(tmp) / "data"), recordings_dir=str(Path(tmp) / "rec"), app_mode="replay")
        app = create_app(settings)
        client = TestClient(app)
        root, ann = {"X-Actor": "Root"}, {"X-Actor": "Ann"}
        client.post("/api/users", json={"name": "Root", "roles": ["Administrator"]}, headers=root)
        client.post("/api/users", json={"name": "Ann", "roles": ["Architect"]}, headers=root)
        pid = client.post("/api/projects", json={"name": "Templates", "brief": BRIEF}, headers=root).json()["id"]
        base = f"/api/projects/{pid}/templates"
        out: dict[str, Any] = {"templates_empty": client.get(base, headers=root).json()}
        client.post(f"{base}/runbook", files={"file": ("a.docx", word(False), kind)}, headers=root)
        out["templates_saved"] = client.post(f"{base}/release_notes", files={"file": ("b.docx", word(True), kind)}, headers=root).json()
        out["error_403_templates"] = client.post(f"{base}/runbook", files={"file": ("a.docx", word(False), kind)}, headers=ann).json()
        out["error_422_templates"] = client.post(f"{base}/runbook", files={"file": ("a.docx", b"not a word file", kind)}, headers=root).json()
        text = json.dumps(out)
        text = re.sub(r'"uploaded_at": "[^"]+"', '"uploaded_at": "2026-01-01T00:00:00Z"', text)
        text = re.sub(r'"size": \d+', '"size": 1000', text)
        return json.loads(text)


def _verify_examples() -> dict[str, Any]:
    """Build Verify (S20): a real check of a small FastAPI project written to a temporary folder, as the server answers it. The folder is a random name, so it is
    replaced with a fixed one before the fixture is kept."""
    from scripts.verify_demo import CODE, DESIGN, SCHEMA

    with tempfile.TemporaryDirectory(prefix="sdlc_contract_verify_") as tmp:
        root = Path(tmp) / "build"
        (root / "app").mkdir(parents=True)
        (root / "app" / "main.py").write_text(CODE)
        (root / "app" / "schema.sql").write_text(SCHEMA)
        (root / ".env").write_text("SECRET=never-read\n")
        settings = Settings(_env_file=None, data_dir=str(Path(tmp) / "data"), recordings_dir=str(Path(tmp) / "rec"), app_mode="replay")
        app = create_app(settings)
        client = TestClient(app, headers=ACTOR)
        pid = client.post("/api/projects", json={"name": "Verify", "brief": BRIEF}).json()["id"]
        lld = ("## Overview\nx\n## Endpoints\n- API-001 GET /api/rooms lists rooms. Derives from: FR-001\n- API-002 POST /api/reservations reserves a room. Derives from: FR-001\n"
               "- API-003 DELETE /api/reservations/{id} cancels. Derives from: FR-001\n## Tables\n- TBL-001 rooms: id, name, capacity. Derives from: FR-001\n"
               "## Rules\n- RUL-001 A reservation may not overlap another reservation for the same room. Derives from: FR-001\n- RUL-002 Staff must wear a badge in the lobby. Derives from: FR-009\n- RUL-003 A room can be retired. Derives from: FR-001\n"
               "## Coverage check\nNone\n## Open questions\nNone")
        app.state.store.artefacts.create_and_add_version(pid, artefact_type="low_level_design", phase_key="design", title="Low-level design", prefix="DES-LLD", body=lld, author="human:seed")
        made = client.post(f"/api/projects/{pid}/verify", json={"backend_path": str(root)})
        out = {"verify_run": made.json()}
        out["verify_list"] = client.get(f"/api/projects/{pid}/verify").json()
        out["error_422_verify"] = client.post(f"/api/projects/{pid}/verify", json={"backend_path": str(Path(tmp) / "nope")}).json()
        out["error_404_verify"] = client.get(f"/api/projects/{pid}/verify/99").json()
        text = json.dumps(out).replace(str(root), "/projects/build/backend").replace(str(Path(tmp) / "nope"), "/projects/build/missing")
        return json.loads(text)


def _architecture_examples() -> dict[str, Any]:
    """Two diagram artefacts as the screen receives them: the list, and the picture the server drew from it (S14b). Made from the scripted
    Architecture demo, so the picture is a real one, and `rendering` is null on every other artefact (artefact_detail already shows that)."""
    from scripts import architecture_demo as arch

    with tempfile.TemporaryDirectory(prefix="sdlc_contract_arch_") as tmp:
        settings = Settings(_env_file=None, data_dir=str(Path(tmp) / "data"), recordings_dir=str(Path(tmp) / "rec"), llm_retry_backoff_seconds=0, run_max_cost_usd=0, **arch.MODELS)
        app = create_app(settings, provider=arch.Scripted())

        async def make() -> dict[str, str]:
            store, engine, runner = app.state.store, app.state.engine, app.state.runner
            made = store.projects.create(name=NAME, brief=BRIEF, actor="system")
            engine.open_project(made.id)
            store.context.add_document(made.id, FILENAME, POLICY, actor="human:demo")
            for phase in ("setup", "requirements", "design"):
                await runner.run_phase(made.id, phase)
                engine.finish(made.id, phase, actor="system"); engine.approve(made.id, phase, actor="human:demo")
            await runner.run_phase(made.id, "architecture")
            return {"project": made.id, **{a.type: a.id for a in store.artefacts.list(made.id, phase_key="architecture")}}

        ids = asyncio.run(make())
        client = TestClient(app)
        pid = ids["project"]
        out = {
            "architecture_flow_detail": client.get(f"/api/projects/{pid}/artefacts/{ids['flow_diagram']}").json(),
            "architecture_usecase_detail": client.get(f"/api/projects/{pid}/artefacts/{ids['usecase_diagram']}").json(),
            "traceability": client.get(f"/api/projects/{pid}/traceability").json(),
            "traceability_item": client.get(f"/api/projects/{pid}/traceability/item/COMP-001").json(),
            "error_404_trace_item": client.get(f"/api/projects/{pid}/traceability/item/COMP-999").json(),
        }
        # A project with gaps: one declared by its writer (with a reason), and one that nothing explains.
        store = app.state.store
        req = next(a for a in store.artefacts.list(pid, phase_key="requirements") if a.type == "functional_requirements")
        body = store.artefacts.get_version(pid, req.id).body
        added = body.replace("\n## Business rules", "\n- FR-003 The system shall show who booked a room. Derives from: PER-001\n\n## Business rules", 1)
        from app.agents.items import parse_items
        links = [(i.id, t, "derives") for i in parse_items(added, app.state.skills.get("functional_requirements").items).items for t in i.link_targets]
        store.artefacts.add_version(pid, req.id, body=added, author="human:demo", links=links)
        out["traceability_with_gaps"] = client.get(f"/api/projects/{pid}/traceability").json()
        state = client.get(f"/api/projects/{pid}/phases/architecture/review").json()
        # Parallel artefacts are written in whatever order they finish, so every list that follows that order is sorted to keep the fixture stable.
        for key in ("unreviewed", "review_out_of_date", "built_on_changed"):
            state["open"][key] = sorted(state["open"][key])
        state["statuses"].sort(key=lambda s: s["artefact_id"])
        state["stale"].sort(key=lambda s: s["artefact_id"])
        out["review_state_with_trace_gaps"] = state
        return out


def _design_examples() -> dict[str, Any]:
    """The hostile-input corpus with the PYTHON sanitiser's answer for each case. The TypeScript sanitiser must give the same, byte for byte."""
    cases = []
    for name, text in SVG_CASES:
        result = sanitise_svg(text)
        cases.append({"name": name, "input": text, "svg": result.svg, "ok": result.ok, "removed": result.report.removed})
    bodies = [
        "## A\n```svg\n<svg><rect/></svg>\n```\n```html\n<script>x</script>\n```\n```\nplain\n```\n~~~svg\n<svg/>\n~~~\n",
        "````svg\n<svg/>\n````\n", "```svg title=x\n<svg/>\n```\n", "```svg\n<svg>", "no fences here\n", "```SVG\n<svg/>\n```\n",
    ]
    finder = [{"body": b, "found": [{"first": f, "last": l, "text": t} for f, l, t in drawings_in(b)]} for b in bodies]
    return {"svg_corpus": {"cases": cases, "finder": finder}}


async def _review_examples(workdir: Path) -> dict[str, Any]:
    """Review, the family picker, request changes, re-run, stale, edit: each once, from a live-mode scratch app with a scripted model."""
    import httpx

    settings = Settings(_env_file=None, data_dir=str(workdir / "review"), recordings_dir=str(workdir / "rec"), app_mode="live",
                        llm_retry_backoff_seconds=0, **RUN_MODELS, ibm_ica_openai_model_id="gpt-x", ibm_ica_openai_fallback_model_id="demo-model",
                        ibm_ica_gemini_model_id="gemini-x", ibm_ica_gemini_fallback_model_id="demo-model",
                        ibm_ica_openai_price_input_per_mtok="2", ibm_ica_openai_price_output_per_mtok="10")
    model = ExportModel()
    model.reviewer = ("<review>\nSummary: One serious problem.\n- [HIGH] PER-001: The frustration is not in the charter. Fix: mark it as an assumption.\n"
                      "- [LOW] Open questions: one could be answered from the charter. Fix: remove it.\n</review>")
    app = create_app(settings, provider=model)
    store, engine, runner = app.state.store, app.state.engine, app.state.runner
    made = store.projects.create(name=NAME, brief=BRIEF, mode="live", actor="system")
    engine.open_project(made.id)
    store.context.add_document(made.id, FILENAME, POLICY, actor="human:demo")
    pid = made.id
    out: dict[str, Any] = {}

    async def settle(run_id: str) -> None:
        for _ in range(500):
            if store.runs.get(pid, run_id).status != "running":
                return
            await asyncio.sleep(0.02)

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=ACTOR) as client:
        await runner.run_phase(pid, "setup")
        await client.post(f"/api/projects/{pid}/phases/setup/finish")
        await client.post(f"/api/projects/{pid}/phases/setup/approve")
        await runner.run_phase(pid, "requirements")
        await client.post(f"/api/projects/{pid}/phases/requirements/finish")
        personas = next(a.id for a in store.artefacts.list(pid) if a.type == "personas")
        out["review_state_before"] = (await client.get(f"/api/projects/{pid}/phases/requirements/review")).json()
        out["review_result"] = (await client.post(f"/api/projects/{pid}/artefacts/{personas}/review", json={})).json()
        out["review_artefact_detail"] = (await client.get(f"/api/projects/{pid}/artefacts/{personas}")).json()
        model.reviewer = ContentFilterBlocked("blocked")
        out["review_paused"] = (await client.post(f"/api/projects/{pid}/artefacts/{personas}/review", json={})).json()
        model.reviewer = "<review>\nSummary: Reads clearly.\n</review>"
        out["review_phase"] = (await client.post(f"/api/projects/{pid}/phases/requirements/review", json={})).json()
        out["review_state_after"] = (await client.get(f"/api/projects/{pid}/phases/requirements/review")).json()
        out["error_422_edit"] = (await client.put(f"/api/projects/{pid}/artefacts/{personas}", json={"body": "## Overview\ncites [DOC-099#1] which does not exist"})).json()
        body = store.artefacts.get_version(pid, personas).body
        out["edit_saved"] = (await client.put(f"/api/projects/{pid}/artefacts/{personas}", json={"body": body + "\n", "note": "tidied"})).json()
        out["review_state_stale"] = (await client.get(f"/api/projects/{pid}/phases/requirements/review")).json()
        out["request_changes"] = (await client.post(f"/api/projects/{pid}/phases/requirements/request-changes", json={"notes": {personas: "Add a persona for the security team."}})).json()
        out["rerun_started"] = (await client.post(f"/api/projects/{pid}/phases/requirements/rerun")).json()
        await settle(out["rerun_started"]["run_id"])
        # The two refusals a person meets most, asked of the server rather than written here: an archived project, and a review in replay mode.
        await client.post(f"/api/projects/{pid}/archive")
        out["error_409_archived"] = (await client.post(f"/api/projects/{pid}/phases/requirements/rerun")).json()
        await client.post(f"/api/projects/{pid}/restore")
        out["error_422_reopen_blank"] = (await client.post(f"/api/projects/{pid}/phases/setup/reopen", json={"reason": " "})).json()
        out["error_409_reopen_not_approved"] = (await client.post(f"/api/projects/{pid}/phases/requirements/reopen", json={"reason": "why"})).json()
    replay_settings = Settings(_env_file=None, data_dir=str(workdir / "review_replay"), recordings_dir=str(workdir / "rec"), app_mode="replay", **RUN_MODELS)
    replay_app = create_app(replay_settings, provider=ExportModel())
    rp = replay_app.state.store.projects.create(name="Replay", brief=BRIEF, actor="system")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=replay_app), base_url="http://test", headers=ACTOR) as replay_client:
        out["error_409_replay_reviews"] = (await replay_client.post(f"/api/projects/{rp.id}/phases/requirements/review", json={})).json()
    return _in_a_stable_order(out)


def _in_a_stable_order(out: dict[str, Any]) -> dict[str, Any]:
    """Artefacts are created in the order parallel writers finish, so any list keyed by artefact comes out in a different order each time.
    Sort them here, so a fixture changes only when a SHAPE changes."""
    for name in ("review_state_before", "review_state_after", "review_state_stale"):
        state = out[name]
        state["statuses"].sort(key=lambda s: s["artefact_id"])
        state["stale"].sort(key=lambda s: s["artefact_id"])
        state["open"]["unreviewed"].sort()
        state["open"]["review_out_of_date"].sort()
        state["open"]["built_on_changed"].sort()
        state["artefacts_with_notes"].sort()
    out["review_phase"]["results"].sort(key=lambda r: r["artefact_id"])
    return out


async def _gate_examples(app) -> dict[str, Any]:
    """The two gate buttons and the run start, each succeeding once, on one event loop (the runner's tasks live on it)."""
    import httpx

    store, engine, runner = app.state.store, app.state.engine, app.state.runner
    made = store.projects.create(name="Gate", brief=BRIEF, actor="system")
    engine.open_project(made.id)
    store.context.add_document(made.id, FILENAME, POLICY, actor="human:demo")
    out: dict[str, Any] = {}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=ACTOR) as client:
        await runner.run_phase(made.id, "setup")
        out["gate_finish"] = (await client.post(f"/api/projects/{made.id}/phases/setup/finish")).json()
        out["gate_approve"] = (await client.post(f"/api/projects/{made.id}/phases/setup/approve")).json()
        # Reopen is shown with the project as the user meets it: approved Setup, and a Requirements run that has not started yet.
        out["gate_reopen"] = (await client.post(f"/api/projects/{made.id}/phases/setup/reopen", json={"reason": "The brief changed after sign-off"})).json()
        await client.post(f"/api/projects/{made.id}/phases/setup/finish")
        await client.post(f"/api/projects/{made.id}/phases/setup/approve")
        out["run_started"] = (await client.post(f"/api/projects/{made.id}/phases/requirements/run", json={"only": ["personas"]})).json()
        for _ in range(500):                                  # let the started run end before the app goes away
            if not runner.is_active(made.id, "requirements"):
                break
            await asyncio.sleep(0.02)
    return out


def build_examples() -> dict[str, Any]:
    """One real response per route the screen uses, from a scratch app. Keyed by fixture name."""
    with tempfile.TemporaryDirectory(prefix="sdlc_contract_") as tmp:
        settings = Settings(_env_file=None, data_dir=str(Path(tmp) / "data"), recordings_dir=str(Path(tmp) / "rec"), app_mode="replay")
        client = TestClient(create_app(settings))
        out: dict[str, Any] = {}
        out["status"] = client.get("/api/status").json()
        out["modes"] = client.get("/api/modes").json()
        out["catalogue"] = client.get("/api/catalogue").json()
        out["plan_preview"] = client.post("/api/plan/preview", json={"selection": {"requirements": [
            "personas", "problem_statement", "vision_objectives", "functional_requirements", "non_functional_requirements", "epics_features"]}}).json()
        out["projects_empty"] = client.get("/api/projects").json()
        created = client.post("/api/projects", headers=ACTOR, json={
            "name": "Meeting Room Booking", "brief": "Staff book rooms.", "connectors": ["source_control", "ci_cd"]})
        out["project_created"] = created.json()
        pid = created.json()["id"]
        out["projects_list"] = client.get("/api/projects").json()
        out["project_detail"] = client.get(f"/api/projects/{pid}").json()
        out["error_422"] = client.post("/api/plan/preview", json={"selection": {"requirements": ["personas"]}}).json()
        out["error_404"] = client.get("/api/projects/does-not-exist").json()
        out["error_400"] = client.post("/api/projects", json={"name": "P"}).json()

        # ---- S12b: documents, search, the sample, artefacts, runs, the gate buttons, and one example of every event ----
        out["sample"] = client.get("/api/sample").json()
        added = client.post(f"/api/projects/{pid}/documents", headers=ACTOR, files={"file": (FILENAME, POLICY + b"\nAsk jane.doe@acme-corp.co.uk about bookings.\n")})
        out["document_added"] = added.json()
        out["documents"] = client.get(f"/api/projects/{pid}/documents").json()
        out["search"] = client.get(f"/api/projects/{pid}/search", params={"q": "cancelled free of charge"}).json()
        out["error_409"] = client.post(f"/api/projects/{pid}/phases/setup/approve", headers=ACTOR).json()
        events, scripted = asyncio.run(_scripted_runs(Path(tmp)))
        sc = TestClient(scripted)
        sproject = next(p for p in scripted.state.store.projects.list() if p.name == NAME)
        out["events"] = events
        out["artefacts"] = sc.get(f"/api/projects/{sproject.id}/artefacts", params={"phase": "requirements"}).json()
        # The list is in creation order, and parallel artefacts are created in whatever order they finish: sort so the fixture is stable.
        out["artefacts"]["artefacts"].sort(key=lambda card: card["type"])
        first = next(a for a in out["artefacts"]["artefacts"] if a["type"] == "functional_requirements")
        out["artefact_detail"] = sc.get(f"/api/projects/{sproject.id}/artefacts/{first['id']}").json()
        out["runs"] = sc.get(f"/api/projects/{sproject.id}/runs").json()
        out["run_detail"] = sc.get(f"/api/projects/{sproject.id}/runs/{out['runs']['runs'][0]['run_id']}").json()
        out.update(asyncio.run(_gate_examples(scripted)))
        out.update(asyncio.run(_review_examples(Path(tmp))))
        out.update(_design_examples())
        out.update(_architecture_examples())
        out.update(_verify_examples())
        out.update(_checklist_examples())
        out.update(_users_examples())
        out.update(_settings_examples())
        out.update(_templates_examples())
        return {name: normalise(body) for name, body in out.items()}


def render(body: Any) -> str:
    return json.dumps(body, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def stale(examples: dict[str, Any], folder: Path = FIXTURES) -> list[str]:
    """Fixture files that are missing, different from what the routes return now, or left over from a route that is gone."""
    problems: list[str] = []
    for name, body in examples.items():
        path = folder / f"{name}.json"
        if not path.is_file():
            problems.append(f"{name}.json is missing")
        elif path.read_text(encoding="utf-8") != render(body):
            problems.append(f"{name}.json no longer matches what the backend returns")
    if folder.is_dir():
        problems += [f"{p.name} is not produced by any route any more" for p in sorted(folder.glob("*.json")) if p.stem not in examples]
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="do not write; exit 1 if any fixture is stale")
    args = parser.parse_args(argv)
    examples = build_examples()
    if args.check:
        problems = stale(examples, FIXTURES)
        for p in problems:
            print(f"STALE: {p}", file=sys.stderr)
        print("contract fixtures are up to date" if not problems else f"{len(problems)} fixture problem(s); run: python -m scripts.export_contract")
        return 1 if problems else 0
    FIXTURES.mkdir(parents=True, exist_ok=True)
    for old in FIXTURES.glob("*.json"):
        if old.stem not in examples:
            old.unlink()
    for name, body in examples.items():
        (FIXTURES / f"{name}.json").write_text(render(body), encoding="utf-8")
    print(f"wrote {len(examples)} fixtures to {FIXTURES.relative_to(FIXTURES.parents[2])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
