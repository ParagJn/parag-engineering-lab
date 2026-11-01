"""Run the Design phase for the sample project: offline with scripted drawings (free), or once for real with Gemini.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.design_demo                       # offline, free, scripted
    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.design_demo --live --record phase3   # REAL, a few cents, saved
    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.design_demo --replay phase3         # from the saved replies, free

THE OFFLINE MODE USES A SCRIPTED FAKE MODEL. Its journey and drawings are written below, in advance. It shows the checks: a drawing with a script
in it is sent back and redrawn, an uncovered persona is caught, a clean run is saved. It says nothing about how well a real model draws.

--live runs Setup, then Requirements (from the sample's own text, using whatever recording `--requirements` names, or live if none), then Design with
the REAL ux_designer model, and prints each drawing's size and anything the sanitiser had to ask to have removed. It needs your key, so you run it.
It never prints the key, the endpoint or the user-agent. The saved replies are what the viewer and the sanitiser are then tested against.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from app.agents.errors import AgentError
from app.config import Settings, get_settings
from app.design.sanitise import drawings_in, sanitise_svg
from app.llm.errors import LLMError
from app.llm.gateway import Gateway
from app.llm.providers.ica import IcaConfigError, IcaProvider
from app.llm.providers.mock import MockProvider
from app.llm.providers.recording import RecordingProvider, ReplayProvider
from app.llm.recordings import RecordingStore
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.models import InvalidInput
from app.repos import Store
from app.review.prompt import load_rubric
from app.review.service import ReviewService
from app.run.events import EventBus
from app.run.runner import PhaseRunner
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine
from app.agents.runtime import AgentRuntime
from app.agents.skills import SkillLibrary
from app.sample import BRIEF, FILENAME, NAME, POLICY

from .agent_demo import CHARTER, PROBLEM, block, money
from .requirements_demo import EPICS_GOOD, FUNCTIONAL, NFR, PERSONAS, STORIES, VISION

PERSON = "human:demo"
BANNER = (
    "*** SCRIPTED FAKE MODEL. The journey and the drawings were written in advance inside scripts/design_demo.py. ***\n"
    "*** This shows the checks on drawings, NOT how well a real model draws. Use --live for that. ***"
)
MODELS = dict(
    ibm_ica_model_id="demo-model", ibm_ica_fallback_model_id="demo-model", ibm_ica_haiku_model_id="demo-haiku", ibm_ica_haiku_fallback_model_id="demo-model",
    ibm_ica_gemini_model_id="demo-gemini", ibm_ica_gemini_fallback_model_id="demo-model",
    ibm_ica_price_input_per_mtok="2", ibm_ica_price_output_per_mtok="10", ibm_ica_haiku_price_input_per_mtok="1", ibm_ica_haiku_price_output_per_mtok="2",
    ibm_ica_gemini_price_input_per_mtok="0.75", ibm_ica_gemini_price_output_per_mtok="3.75",
)
REQUIREMENTS = {
    "project_charter": CHARTER, "personas": PERSONAS, "problem_statement": PROBLEM, "vision_objectives": VISION,
    "functional_requirements": FUNCTIONAL, "non_functional_requirements": NFR, "epics_features": EPICS_GOOD, "user_stories": STORIES,
}

JOURNEY = block({
    "Overview": "Two personas, three steps: staff find and reserve a room; the administrator maintains the room list.",
    "Journey": (
        "- JS-001 Office staff member opens the room list and sees the rooms that are free for the time they chose. Derives from: PER-001, FR-001, FEAT-001\n"
        "- JS-002 Office staff member reserves a free room and sees a confirmation, or is told the slot is taken. Derives from: PER-001, FR-001, FEAT-001\n"
        "- JS-003 Room administrator adds, renames or retires a room and sees the updated list. Derives from: PER-002, FR-002, FEAT-002"),
    "Coverage check": "None.",
    "Open questions": "How far ahead can a room be booked?",
})


def _svg(title: str, *shapes: str) -> str:
    return ('```svg\n<svg viewBox="0 0 640 400" xmlns="http://www.w3.org/2000/svg"><title>' + title + "</title>" + "".join(shapes) + "</svg>\n```")


def _box(x: int, y: int, w: int, h: int, label: str, fill: str = "none", stroke: str = "#888") -> str:
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}"/>'
            f'<text x="{x + 10}" y="{y + h // 2 + 5}" font-size="14">{label}</text>')


def lowfi(unsafe: bool = False) -> str:
    evil = '<script>alert(1)</script>' if unsafe else ""
    screens = (
        ("LFS-001", "Room list", "Shows the rooms that are free for the chosen time.", "JS-001", (_box(20, 20, 600, 40, "Room list"), _box(20, 80, 600, 40, "Time: [ chosen time ]"), _box(20, 140, 600, 60, "Room A (free)   [ Reserve ]"), _box(20, 220, 600, 60, "Room B (free)   [ Reserve ]"))),
        ("LFS-002", "Reserve a room", "Confirms a reservation or says the slot is taken.", "JS-002", (_box(20, 20, 600, 40, "Reserve a room"), _box(20, 80, 600, 80, "Room A, chosen time"), _box(20, 180, 280, 40, "[ Confirm ]"), _box(320, 180, 300, 40, "[ Cancel ]"))),
        ("LFS-003", "Manage rooms", "Lets the administrator add, rename and retire rooms.", "JS-003", (_box(20, 20, 600, 40, "Manage rooms"), _box(20, 80, 600, 50, "Room A   [ Rename ] [ Retire ]"), _box(20, 150, 600, 50, "[ Add a room ]"))),
    )
    lines = "\n\n".join(f"- {sid} {name}: {purpose} Derives from: {js}\n{_svg(f'{sid} {name}', *(shapes + ((evil,) if unsafe and sid == 'LFS-001' else ())))}" for sid, name, purpose, js, shapes in screens)
    return block({
        "Overview": "Three screens show all three journey steps.",
        "Screens": lines,
        "Coverage check": "None.",
        "Open questions": "None.",
    })


def hifi() -> str:
    def screen(sid: str, name: str, purpose: str, derives: str, *rows: tuple[str, str]) -> str:
        shapes = ['<rect x="0" y="0" width="640" height="400" fill="#f8fafc"/>', '<rect x="0" y="0" width="640" height="56" fill="#4f46e5"/>',
                  f'<text x="20" y="35" font-size="20" font-weight="bold" fill="#ffffff" font-family="sans-serif">{name}</text>']
        y = 80
        for label, kind in rows:
            fill = "#4f46e5" if kind == "button" else "#ffffff"
            ink = "#ffffff" if kind == "button" else "#0f172a"
            shapes.append(f'<rect x="20" y="{y}" width="600" height="56" rx="8" fill="{fill}" stroke="#cbd5e1"/><text x="36" y="{y + 34}" font-size="16" fill="{ink}" font-family="sans-serif">{label}</text>')
            y += 72
        return f"- {sid} {name}: {purpose} Derives from: {derives}\n" + _svg(f"{sid} {name}", *shapes)
    return block({
        "Overview": "Three screens, in indigo #4f46e5 with white and one grey, on a 14, 16 and 20 point type scale.",
        "Screens": "\n\n".join([
            screen("HFS-001", "Room list", "The room list with colour and a clear Reserve action.", "LFS-001, JS-001", ("Room A (free)", "row"), ("Room B (free)", "row"), ("Reserve Room A", "button")),
            screen("HFS-002", "Reserve a room", "The confirmation with a primary action.", "LFS-002, JS-002", ("Room A, chosen time", "row"), ("Confirm", "button")),
            screen("HFS-003", "Manage rooms", "Room administration with clear actions.", "LFS-003, JS-003", ("Room A", "row"), ("Add a room", "button")),
        ]),
        "Coverage check": "None.",
        "Open questions": "None.",
    })


REPLIES_DESIGN = {"user_journey": JOURNEY, "lowfi_wireframes": lowfi(), "hifi_wireframes": hifi()}


class Scripted(MockProvider):
    """Answers by the artefact asked for. The first low-fi reply has a script inside a drawing, so the repair can be seen once."""

    def __init__(self) -> None:
        super().__init__()
        self.lowfi_calls = 0
        self.asked: list[str] = []

    def _which(self, request) -> str:
        text = request.messages[0].content
        for key in (*REQUIREMENTS, *REPLIES_DESIGN):
            if f"({key}) for the project" in text:
                return key
        raise RuntimeError("scripted model: unknown task")

    async def complete(self, model_id, request):
        key = self._which(request)
        self.asked.append(key)
        if key == "lowfi_wireframes":
            self.lowfi_calls += 1
            return ProviderResponse(lowfi(unsafe=self.lowfi_calls == 1), Usage(2600, 1400), "stop")
        text = REQUIREMENTS.get(key) or REPLIES_DESIGN[key]
        return ProviderResponse(text, Usage(1800, 700), "stop")


def build(workdir: Path, settings: Settings, provider):
    store = Store.open(workdir / "demo.db", limits=settings.context_limits)
    routing = Routing.load()
    catalogue = load_catalogue(routing.roles.keys())
    engine = WorkflowEngine(catalogue, store)
    gateway = Gateway(settings, routing, provider, store)
    runtime = AgentRuntime(settings, store, gateway, catalogue, engine, SkillLibrary.load(catalogue))
    reviews = ReviewService(settings, store, gateway, runtime, engine, load_rubric())
    bus = EventBus(store, queue_size=settings.run_event_queue, secrets=settings.secret_values())
    runner = PhaseRunner(settings, store, engine, runtime, reviews, bus)
    project = store.projects.create(name=NAME, brief=BRIEF, actor="system")
    engine.open_project(project.id)
    store.context.add_document(project.id, FILENAME, POLICY, actor=PERSON)
    return store, engine, runner, project.id


async def through(runner, engine, pid: str, phase: str):
    result = await runner.run_phase(pid, phase)
    engine.finish(pid, phase, actor="system")
    engine.approve(pid, phase, actor=PERSON)
    return result


def describe_drawings(store: Store, pid: str) -> list[str]:
    out = []
    for artefact in store.artefacts.list(pid, phase_key="design"):
        if artefact.latest_version is None:
            continue
        body = store.artefacts.get_version(pid, artefact.id).body
        drawings = drawings_in(body)
        if not drawings:
            continue
        sizes = [len(text) for _, _, text in drawings]
        clean = sum(1 for _, _, text in drawings if sanitise_svg(text).ok and not sanitise_svg(text).changed)
        out.append(f"  {artefact.title}: {len(drawings)} drawing(s), {min(sizes)} to {max(sizes)} characters, {clean} of {len(drawings)} need nothing removed")
    return out


async def run(workdir: Path, settings: Settings, provider) -> tuple[Store, str, object]:
    store, engine, runner, pid = build(workdir, settings, provider)
    await through(runner, engine, pid, "setup")
    await through(runner, engine, pid, "requirements")
    return store, pid, await runner.run_phase(pid, "design")


def render(store: Store, pid: str, result, banner: str | None) -> list[str]:
    lines = [banner, ""] if banner else []
    counts = result.totals["artefacts"]
    lines.append(f"Design: {result.status}: {counts['done']} written, {counts['failed']} failed, {counts['skipped']} skipped; "
                 f"{result.totals['calls']} call(s), cost {money(result.totals['cost_usd'])}")
    for outcome in result.outcomes:
        lines.append(f"  {outcome.key}: {outcome.state}" + (f" ({outcome.reason})" if outcome.reason else ""))
    lines += describe_drawings(store, pid)
    for artefact in store.artefacts.list(pid, phase_key="design"):
        if artefact.latest_version is None:
            continue
        generation = store.artefacts.get_version(pid, artefact.id).generation or {}
        for repair in generation.get("repair_reasons", []):
            for problem in repair["problems"]:
                lines.append(f"  {artefact.title}: attempt {repair['attempt']} was sent back: {problem[:200]}")
    return lines


async def run_offline(workdir: Path) -> tuple[list[str], bool]:
    settings = Settings(_env_file=None, data_dir=str(workdir / "data"), recordings_dir=str(workdir / "rec"), llm_retry_backoff_seconds=0, run_max_cost_usd=0, **MODELS)
    provider = Scripted()
    store, pid, result = await run(workdir, settings, provider)
    lines = render(store, pid, result, BANNER)
    repaired = any("was sent back" in l and "script" in l for l in lines)
    good = result.status == "finished" and repaired and provider.lowfi_calls == 2
    lines.append("")
    lines.append("a drawing with a script in it was sent back and redrawn" if repaired else "THE SCRIPT IN THE DRAWING WAS NOT CAUGHT")
    return lines, good


def _clean(text: str) -> str:
    return re.sub(r"https?://\S+", "[url removed]", text)


async def run_real(workdir: Path, cfg: Settings, live: bool, name: str | None) -> tuple[Store, str, object]:
    if not live:
        folder = cfg.model_copy(update={"replay_set": name}).recordings_path
        return await run(workdir, cfg, ReplayProvider(RecordingStore(folder)))
    ica = IcaProvider(cfg)
    try:
        provider = ica
        if name:
            folder = cfg.model_copy(update={"replay_set": name}).recordings_path
            provider = RecordingProvider(ica, RecordingStore(folder), cfg)
        return await run(workdir, cfg, provider)
    finally:
        await ica.aclose()


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="run Setup, Requirements and Design with real models (a few tens of cents in all)")
    parser.add_argument("--record", metavar="NAME", help="with --live: save every reply under backend/recordings/NAME")
    parser.add_argument("--replay", metavar="NAME", help="run from backend/recordings/NAME, no network")
    args = parser.parse_args(argv)
    if args.record and not args.live:
        parser.error("--record only makes sense with --live")
    if args.live and args.replay:
        parser.error("choose --live or --replay, not both")
    name = args.record or args.replay
    if name is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
        parser.error("a recording name is letters, digits, '-' and '_' only, up to 64 characters")

    with tempfile.TemporaryDirectory(prefix="sdlc_design_demo_") as tmp:
        workdir = Path(tmp)
        if not args.live and not args.replay:
            lines, good = asyncio.run(run_offline(workdir))
            print("\n".join(lines))
            return 0 if good else 1
        cfg = settings or get_settings()
        if args.live:
            missing = [n for n, ok in (("IBM_ICA_ENDPOINT", cfg.endpoint_set), ("IBM_ICA_API_KEY", cfg.api_key_set)) if not ok]
            if missing:
                print(f"Cannot run live: {', '.join(missing)} not set in backend/.env", file=sys.stderr)
                return 2
        try:
            store, pid, result = asyncio.run(run_real(workdir, cfg, args.live, name))
        except (AgentError, LLMError, IcaConfigError, InvalidInput) as exc:
            print(f"The {'real-model' if args.live else 'replay'} run failed: {_clean(str(exc))}", file=sys.stderr)
            return 1
        header = ("REAL MODELS via IBM ICA" + (f" (recording to '{name}')" if name else "")) if args.live else f"REPLAY of recording '{name}' (no network)"
        print("\n".join(render(store, pid, result, header)))
        print("\nWhat to look for: are there drawings, and how many need nothing removed? Open the app and look at them. Do the screens show the "
              "journey steps? If a drawing keeps being sent back, the reasons are listed above.")
        return 0 if result.status == "finished" else 1


if __name__ == "__main__":
    raise SystemExit(main())
