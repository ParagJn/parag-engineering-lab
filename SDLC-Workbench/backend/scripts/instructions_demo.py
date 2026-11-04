"""Show the Build phase writing its instruction set in pieces, offline and free: a scripted model, the real runner, the real checks. No model is called.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.instructions_demo

Everything runs in a temporary folder that is deleted afterwards (your real database and workspaces are not touched). Five runs on a small room-booking project:
  1 the happy path: the foundation, one file for each of three use cases (written together), then the acceptance tests; saved as ONE version
  5 the same project WITH two hi-fi screens: the foundation, the UI guide, then the use cases and the two screen files together, then the acceptance tests
  2 one file is wrong twice (a missing section, then an invented endpoint) and is sent back ALONE; the others are not asked again
  3 one reply is cut off by the output limit on every attempt: the run says so, names the limit to raise, and saves NOTHING
  4 the money cap is reached after the first file: no further file is started and nothing is saved

The model here is a script, so this shows the SYSTEM's behaviour (the order, the repairs, the checks, the events, the all-or-nothing save). It cannot tell you how a
real model writes these files or how a coding tool follows them.
"""
from __future__ import annotations

import asyncio
import itertools
import tempfile
from pathlib import Path

from app.agents.runtime import AgentRuntime
from app.agents.skills import SkillLibrary
from app.build import instructions as I
from app.build.compose import SetComposer
from app.build.phase import BuildHooks
from app.config import Settings
from app.llm.gateway import Gateway
from app.llm.providers.mock import MockCall, MockProvider
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.repos import Store
from app.review.prompt import load_rubric
from app.review.service import ReviewService
from app.run.events import EventBus
from app.run.runner import PhaseRunner
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine

MODELS = dict(
    ibm_ica_model_id="m-sonnet", ibm_ica_fallback_model_id="m-sonnet", ibm_ica_haiku_model_id="m-haiku", ibm_ica_openai_model_id="m-openai", ibm_ica_gemini_model_id="m-gemini",
    ibm_ica_price_input_per_mtok="3", ibm_ica_price_output_per_mtok="15",
)

USE_CASES = [("UC-001", "Find a free room", "Staff look at the rooms free for a time."), ("UC-002", "Reserve a room", "Staff reserve a free room, or are told the slot is taken."),
             ("UC-003", "Maintain rooms", "The administrator adds, renames and retires rooms.")]
DESIGN = {
    "personas": "## Personas\n- PER-001 Office staff. Derives from: SET-CHR-001\n",
    "user_journey": "## Journey\n- JS-001 Staff look for a room. Derives from: PER-001\n",
    "usecase_diagram": "## Use cases\n" + "\n".join(f"- {i} {t}: {d} Derives from: PER-001, FR-001" for i, t, d in USE_CASES) + "\n## Coverage check\nNone.\n",
    "low_level_design": ("## Overview\nx\n## Endpoints\n- API-001 GET /api/rooms lists rooms. Derives from: FR-001\n- API-002 GET /api/availability. Derives from: FR-001\n"
                         "- API-003 POST /api/reservations reserves a room. Derives from: FR-001\n## Tables\n- TBL-001 rooms: id, name. Derives from: FR-001\n"
                         "- TBL-002 reservations: id, room, start, end. Derives from: FR-001\n## Rules\n- RUL-001 A booking may not overlap another. Derives from: FR-001\n"
                         "## Coverage check\nNone\n## Open questions\nNone"),
    "functional_requirements": "## Requirements\n- FR-001 The system shall allow booking. Derives from: PER-001\n",
    "component_overview": "## Components\n- COMP-001 Booking service. Derives from: FR-001\n",
    "high_level_design": "## Interfaces\n- IFC-001 Booking API. Derives from: COMP-001\n",
    "hifi_wireframes": "## Screens\nNo screens in this design.\n",
    "non_functional_requirements": "## Overview\nx\n",
}

NAMES = {"UC-001": "UC-001-find-a-free-room.md", "UC-002": "UC-002-reserve-a-room.md", "UC-003": "UC-003-maintain-rooms.md"}
BUILDS = {"UC-001": "- API-001 GET /api/rooms and API-002 GET /api/availability. Needs TBL-001.",
          "UC-002": "- API-003 POST /api/reservations. Needs TBL-002.", "UC-003": "- API-001 GET /api/rooms lists the rooms. Needs TBL-001."}


CONTRACT = (
    "- API-001 GET /api/rooms. Request: none. Response 200: object with rooms (list of room_id (integer), name (string)). Errors: 500.\n"
    "- API-002 GET /api/availability. Request: date (string YYYY-MM-DD), start_time (string HH:MM), end_time (string HH:MM). Response 200: object with free (list), reserved (list). Errors: 400.\n"
    "- API-003 POST /api/reservations. Request: room_id (integer), date (string YYYY-MM-DD), start_time (string HH:MM), end_time (string HH:MM). Response 201: object with reservation_id (integer). Errors: 400, 401, 404, 409, 422."
)


def foundation() -> str:
    return ("# Foundation\n\n## Goal\nA small room booking service.\n\n## Stack and layout\nPython and FastAPI with SQLite; one `app.py`; a `static/` folder for the pages.\n\n"
            f"## Interface contract\n{CONTRACT}\n\n"
            "## Tables\n- TBL-001 rooms: id, name\n- TBL-002 reservations: id, room, start, end\n\n## Shared rules\n- RUL-001 A booking may not overlap another.\n\n"
            "## How to run it\nRun `uvicorn app:app`.\n\n## Do not\n- Do not add login.\n\n## Traceability\nDerives from: TBL-001, TBL-002, RUL-001\n")


def use_case(uc: str) -> str:
    title = next(t for i, t, _ in USE_CASES if i == uc)
    return (f"# {title}\n\n## Goal\nLet office staff: {title.lower()}.\n\n## Read first\nRead 00-foundation.md first.\n\n## What to build\n{BUILDS[uc]}\n\n"
            "## Business rules that apply\n- RUL-001 A booking may not overlap another.\n\n## Done when\n- The page shows the result\n- A bad request is refused\n\n"
            f"## Do not\n- Do not add accounts or payments.\n\n## Traceability\nDerives from: {uc}, API-001, RUL-001\n")


SCREENS = {"HFS-001": ("Browse rooms", "UI-HFS-001-browse-rooms.md"), "HFS-002": ("Notices", "UI-HFS-002-notices.md")}


def ui_guide() -> str:
    parts = {
        "Goal": "One look and one way of behaving for every page.", "Layout and navigation": "A top bar with the page names; the page content under it.",
        "States": "Loading shows a short message; an empty list says so; an error shows the server's reason.",
        "Forms and messages": "Every input has a label; a refused request shows the reason beside the form.",
        "Shared components": "The notice box and the room row are used on every page.",
        "Accessibility": "Every control can be reached from the keyboard; a message is never shown by colour alone.",
        "Do not": "- Do not add a second colour scheme.", "Traceability": "Derives from: HFS-001, HFS-002",
    }
    return "# UI guidelines\n\n" + "\n\n".join(f"## {k}\n{v}" for k, v in parts.items()) + "\n"


def screen(screen_id: str) -> str:
    title = SCREENS[screen_id][0]
    parts = {
        "Goal": f"Let staff use the {title.lower()} page.", "Read first": "Read 00-foundation.md and 01-ui-guidelines.md first.",
        "What is on the screen": "Top to bottom: the date and time inputs, a Check button, then a table of rooms with a Free or Reserved marker.",
        "Components and their states": "- The Check button is disabled while the inputs are empty.\n- A room row shows Free or Reserved.",
        "What the person can do": "- Choose a date and a time, press Check.", "Calls it makes": "- API-002 is called when Check is pressed.",
        "Messages and the rules behind them": "- A refused request shows the reason the server gives (RUL-001).",
        "Done when": "- The table shows every room with its state\n- An empty result says so", "Do not": "- Do not add accounts.",
        "Traceability": f"Derives from: {screen_id}, API-002, RUL-001",
    }
    return f"# {title}\n\n" + "\n\n".join(f"## {k}\n{v}" for k, v in parts.items()) + "\n"


def acceptance() -> str:
    return ("# Acceptance tests\n\n## Goal\nProve the service behaves as designed.\n\n## How to run the tests\nRun `pytest tests` against the running service.\n\n"
            "## What the tests check\n- API-001 lists rooms\n- API-003 refuses a clash (RUL-001)\n\n"
            "```python\nimport os, urllib.request\nBASE = os.environ.get('APP_BASE_URL', 'http://127.0.0.1:8000')\n\n\ndef test_lists_rooms_API_001():\n"
            "    assert urllib.request.urlopen(BASE + '/api/rooms').status == 200\n```\n\n"
            "## Do not\n- Do not change the tests to make them pass.\n\n## Traceability\nDerives from: API-001, API-003, RUL-001\n")


def good_files() -> dict[str, str]:
    return {I.FOUNDATION_NAME: foundation(), **{NAMES[u]: use_case(u) for u, _, _ in USE_CASES}, I.ACCEPTANCE_NAME: acceptance(),
            I.UI_GUIDE_NAME: ui_guide(), **{name: screen(sid) for sid, (_, name) in SCREENS.items()}}


class Scripted(MockProvider):
    """Answers by the file named in the request, from a per-file script, else with a good file."""

    def __init__(self):
        super().__init__()
        self.files = good_files()
        self.script: dict[str, list] = {}
        self.asked: list[str] = []

    async def complete(self, model_id, request):
        name = request.messages[0].content.split("Write the file `", 1)[1].split("`", 1)[0]
        self.asked.append(name)
        self.calls.append(MockCall(model_id, request))
        queued = self.script.get(name)
        if queued:
            outcome = queued.pop(0)
            return outcome if isinstance(outcome, ProviderResponse) else ProviderResponse(f"<artefact>\n{outcome}\n</artefact>", Usage(21000, 3000), "stop")
        return ProviderResponse(f"<artefact>\n{self.files[name]}\n</artefact>", Usage(21000, 3000), "stop")


def line(label: str, what: str) -> str:
    return f"  {label:<44} {what}"


async def story(workdir: Path, title: str, setup=None, screens: bool = False, **settings):
    cfg = Settings(_env_file=None, data_dir=str(workdir / title.split()[0]), recordings_dir=str(workdir / "rec"), llm_retry_backoff_seconds=0, **{**MODELS, **settings})
    store = Store.open(workdir / f"{title.split()[0]}.db")
    provider = Scripted()
    ids = itertools.count(1)
    routing = Routing.load()
    catalogue = load_catalogue(routing.roles.keys())
    gateway = Gateway(cfg, routing, provider, store, call_id_factory=lambda: f"call{next(ids)}")
    engine = WorkflowEngine(catalogue, store)
    library = SkillLibrary.load(catalogue)
    runtime = AgentRuntime(cfg, store, gateway, catalogue, engine, library)
    hooks = BuildHooks(None, None, store, library, cfg, composer=SetComposer(runtime, cfg, library))
    bus = EventBus(store, queue_size=cfg.run_event_queue, secrets=cfg.secret_values)
    runner = PhaseRunner(cfg, store, engine, runtime, ReviewService(cfg, store, gateway, runtime, engine, load_rubric()), bus, build=hooks)
    project = store.projects.create(name="Room Booking", brief="A small room booking service.", actor="system")
    engine.open_project(project.id)
    store.phases.ensure(project.id, "build", actor="system")
    store.phases.set_status(project.id, "build", "running", actor="system")
    design = dict(DESIGN)
    if screens:
        design["hifi_wireframes"] = "## Screens\n" + "\n".join(f"- {sid} {title}: the page. Derives from: FR-001" for sid, (title, _) in SCREENS.items()) + "\n"
    for key, text in design.items():
        skill = library.get(key)
        store.artefacts.create_and_add_version(project.id, artefact_type=key, phase_key=skill.artefact.phase_key, title=skill.artefact.name, prefix=skill.artefact.id_prefix, body=text, author="human:seed")
    if setup:
        setup(provider)
    result = await runner.run_phase(project.id, "build")
    events = [(e.type, e.data) for e in store.run_events.list(project.id, run_id=result.run_id) if e.type.startswith("piece.") or e.type.startswith("artefact.")]
    found = store.artefacts.list(project.id, phase_key="build", artefact_type="build_instructions")
    version = store.artefacts.get_version(project.id, found[0].id) if found else None
    return result, provider, events, version


def show(result, provider, events, version) -> None:
    outcome = result.outcomes[0]
    # What the screen is told: the event's own sentence (short, and it names the limit to raise), not the longer stored reason, which is cut at 300 characters.
    told = next((d["reason"] for k, d in events if k == "artefact.failed"), outcome.reason)
    print(line("run", f"{result.status}" + (f" ({result.stop_reason})" if result.stop_reason else "")))
    print(line("the artefact", f"{outcome.state}" + (f", version {outcome.version}" if outcome.version else "") + (f" - {told}" if told else "")))
    print(line("files asked for, in order", ", ".join(provider.asked)))
    for kind, data in events:
        if kind.startswith("piece."):
            extra = f" attempts={data['attempts']}" if "attempts" in data else (f" - {data['reason'][:90]}" if "reason" in data else f" ({data['index']} of {data['of']}, {data['stage']})")
            print(line(f"  {kind}", f"{data['file']}{extra}"))
    if version is None:
        print(line("saved", "NOTHING (all or nothing)"))
        return
    files, _ = I.split_set(version.body)
    print(line("saved", f"one version holding {len(files)} files: {', '.join(files)}"))
    gaps = version.generation.get("gaps") or []
    print(line("gaps left open", ", ".join(gaps) if gaps else "none"))
    print(line("calls / repairs / cost", f"{len(version.generation['calls'])} / {version.generation['repairs']} / ${version.generation['cost_usd']:.4f}"))


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sdlc_instructions_demo_") as tmp:
        work = Path(tmp)
        print("1  the happy path")
        show(*await story(work, "one happy"))

        print("\n2  one file is wrong twice and is repaired alone")

        def wrong_twice(provider):
            no_done = use_case("UC-002").replace("## Done when", "## Something else")
            invented = use_case("UC-002").replace("API-003", "API-777")
            provider.script[NAMES["UC-002"]] = [no_done, invented]
        show(*await story(work, "two repaired", wrong_twice))

        print("\n3  one reply is cut off by the output limit on every attempt")

        def cut_off(provider):
            cut = ProviderResponse("<artefact>\n# Foundation\n\n## Goal\nA small", Usage(21000, 16000), "length")
            provider.script[I.FOUNDATION_NAME] = [cut, cut, cut]
        result, provider, events, version = await story(work, "three cut", cut_off)
        show(result, provider, events, version)

        print("\n4  the money cap is reached after the first file")
        show(*await story(work, "four capped", run_max_cost_usd=0.05))

        print("\n5  the same project with two hi-fi screens")
        show(*await story(work, "five screens", screens=True))

    print("\nA temporary folder held everything; it is gone. Nothing real was touched, and no model was called.")


if __name__ == "__main__":
    asyncio.run(main())
