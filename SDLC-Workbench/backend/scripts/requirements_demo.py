"""Run the whole Requirements phase through the agent runtime, and see the item IDs and links it produces.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.requirements_demo                 # offline, free
    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.requirements_demo --live          # REAL calls
    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.requirements_demo --live --record phase1
    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.requirements_demo --replay phase1 # no network

OFFLINE MODE USES A SCRIPTED FAKE MODEL, NOT A REAL ONE. Its replies are written into this file. One of them
(the epics) deliberately leaves a requirement uncovered, so you can watch the runtime catch it, send it back
and save only the corrected version. It says nothing about how well a real model writes. That is what --live is for.

--live runs the project charter and then all seven Requirements artefacts for the Meeting Room Booking sample,
about 8 to 12 real calls (more if the repair loop fires), and prints the real total cost. You run it. It never
prints a key, the endpoint or the user-agent. With --record NAME every reply is saved under backend/recordings/NAME
(gitignored) so --replay NAME can run the same phase later with no network and no cost.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from app.agents.errors import AgentError
from app.agents.items import parse_items
from app.agents.runtime import AgentResult, AgentRuntime, sum_costs
from app.agents.skills import SkillLibrary
from app.config import Settings, get_settings
from app.llm.errors import LLMError
from app.llm.gateway import Gateway
from app.llm.providers.ica import IcaConfigError, IcaProvider
from app.llm.providers.mock import MockProvider
from app.llm.providers.recording import RecordingProvider, ReplayProvider
from app.llm.recordings import RecordingStore
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.repos import Store
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine

from app.sample import FILENAME, NAME
from .agent_demo import BRIEF, CHARTER, FUNCTIONAL, PERSON, POLICY, PROBLEM, block, money

BANNER = (
    "*** SCRIPTED FAKE MODEL. The replies below were written in advance inside scripts/requirements_demo.py. ***\n"
    "*** This shows the runtime's item checks, links and repairs, NOT how a real model writes. Use --live for that. ***"
)

# The order the runtime is asked for things. Each needs only artefacts earlier in this list.
CHAIN = (
    ("Project charter", "project_charter"),
    ("Personas", "personas"),
    ("Problem statement", "problem_statement"),
    ("Vision and objectives", "vision_objectives"),
    ("Functional requirements", "functional_requirements"),
    ("Non-functional requirements", "non_functional_requirements"),
    ("Epics and features", "epics_features"),
    ("User stories", "user_stories"),
)
SHOWN_IN_FULL = ("functional_requirements", "user_stories")
MODELS = dict(
    ibm_ica_model_id="demo-model", ibm_ica_fallback_model_id="demo-model", ibm_ica_haiku_model_id="demo-haiku",
    ibm_ica_price_input_per_mtok="2", ibm_ica_price_output_per_mtok="10",
    ibm_ica_haiku_price_input_per_mtok="0.1", ibm_ica_haiku_price_output_per_mtok="0.5",
)

# ---- the scripted replies ---------------------------------------------------------------------------

PERSONAS = block({
    "Overview": "Two personas follow, taken from the charter [SET-CHR-001].",
    "Personas": ("- PER-001 Office staff member, who wants a free room quickly. Derives from: SET-CHR-001\n"
                 "- PER-002 Room administrator, who keeps the list of rooms correct. Derives from: SET-CHR-001"),
    "How the personas differ": "Staff book and cancel; the administrator maintains the room list.",
    "Open questions": "How many rooms are there?",
})
VISION = block({
    "Vision": "Staff can always tell which rooms are free, and a room they have reserved is theirs.",
    "Objectives": ("- OBJ-001 No room is booked twice for the same slot. Derives from: REQ-PRB-001\n"
                   "- OBJ-002 Staff can find, reserve and cancel a room without asking anyone. Derives from: REQ-PRB-001, SET-CHR-001"),
    "Measures": "OBJ-001: the number of double bookings, which should be zero. OBJ-002: no target number is given in the sources.",
    "Out of vision": "Reporting, calendar integration and mobile apps.",
    "Open questions": "What share of bookings should need no help?",
})
NFR = block({
    "Overview": "These cover when the booking service must be usable and who may use it. Performance is left out: no source gives a figure.",
    "Requirements": ("- NFR-001 The booking service shall be usable throughout office hours. Derives from: SET-CHR-001\n"
                     "- NFR-002 Only office staff shall be able to reserve or cancel a room. Derives from: SET-CHR-001, REQ-PRB-001"),
    "Quality targets": "NFR-001: target not given. NFR-002: target not given.",
    "Open questions": "What availability does the sponsor expect, and how are staff identified?",
})
_EPICS = {
    "Overview": "Two epics and two features cover every functional and non-functional requirement.",
    "Epics": ("- EPIC-001 Staff book rooms with confidence. Derives from: PER-001\n"
              "- EPIC-002 Administrators keep the room list correct. Derives from: PER-002"),
    "Coverage check": "None.",
}
# The first epics reply forgets NFR-002: no feature derives from it and the coverage check does not mention it.
EPICS_BAD = block({**_EPICS, "Features": (
    "- FEAT-001 Reserve a free room for a slot and refuse a double booking. Derives from: EPIC-001, FR-001, NFR-001\n"
    "- FEAT-002 Add, rename and retire rooms. Derives from: EPIC-002, FR-002")})
EPICS_GOOD = block({**_EPICS, "Features": (
    "- FEAT-001 Reserve a free room for a slot and refuse a double booking. Derives from: EPIC-001, FR-001, NFR-001\n"
    "- FEAT-002 Add, rename and retire rooms. Derives from: EPIC-002, FR-002, NFR-002")})
STORIES = block({
    "Overview": "Two stories, one per feature.",
    "Stories": ("- US-001 As an office staff member, I want to reserve a free room so that I can meet without clashes. Derives from: FEAT-001, PER-001\n"
                "  - A room that is already booked for the slot cannot be reserved.\n"
                "  - A reservation outside office hours is refused.\n"
                "- US-002 As a room administrator, I want to add, rename and retire rooms so that the list stays correct. Derives from: FEAT-002, PER-002\n"
                "  - A retired room can no longer be booked."),
    "Coverage check": "None.",
    "Open questions": "What happens to future bookings when a room is retired?",
})


@dataclass(frozen=True)
class Step:
    label: str
    key: str
    result: AgentResult
    note: str


@dataclass(frozen=True)
class Outcome:
    steps: list[Step]
    items: int
    links: int
    gap_caught: bool
    saved: int
    total_cost: float | None
    bodies: dict[str, str]


def demo_settings(workdir: Path) -> Settings:
    return Settings(_env_file=None, data_dir=str(workdir / "data"), recordings_dir=str(workdir / "rec"), **MODELS)


def describe(step: Step) -> str:
    r = step.result
    items = f", {len(r.items)} item(s)" if r.items else ""
    return (f"{step.label}: {r.artefact_id} v{r.version}, {r.attempts} attempt(s), {r.tokens_in} in / {r.tokens_out} out, "
            f"cost {money(r.cost_usd)}{items}, {r.links} link(s), by {r.author.split(':', 1)[1]}")


def build(workdir: Path, settings: Settings, provider) -> tuple[Store, AgentRuntime, WorkflowEngine, str]:
    store = Store.open(workdir / "demo.db", limits=settings.context_limits)
    routing = Routing.load()
    catalogue = load_catalogue(routing.roles.keys())
    engine = WorkflowEngine(catalogue, store)
    runtime = AgentRuntime(settings, store, Gateway(settings, routing, provider, store), catalogue, engine, SkillLibrary.load(catalogue))
    project = store.projects.create(name=NAME, brief=BRIEF, actor="system")
    engine.open_project(project.id)
    store.context.add_document(project.id, FILENAME, POLICY, actor=PERSON)
    return store, runtime, engine, project.id


async def run_chain(store: Store, runtime: AgentRuntime, engine: WorkflowEngine, pid: str) -> list[tuple[str, str, AgentResult]]:
    """Setup, then the Requirements phase, one artefact at a time in catalogue order."""
    done: list[tuple[str, str, AgentResult]] = []
    engine.start(pid, "setup", actor="system")
    for index, (label, key) in enumerate(CHAIN):
        if index == 1:
            engine.finish(pid, "setup", actor="system")
            engine.approve(pid, "setup", actor=PERSON)
            engine.start(pid, "requirements", actor="system")
        done.append((label, key, await runtime.run(pid, key)))
    return done


def summarise(store: Store, pid: str, done: list[tuple[str, str, AgentResult]], notes: dict[str, str], gap_caught: bool) -> Outcome:
    bodies = {key: store.artefacts.get_version(pid, result.artefact_id).body for _, key, result in done}
    steps = [Step(label, key, result, notes.get(key, "")) for label, key, result in done]
    return Outcome(
        steps=steps, items=sum(len(s.result.items) for s in steps), links=len(store.links.list(pid)), gap_caught=gap_caught,
        saved=len(store.artefacts.list(pid)), total_cost=sum_costs([s.result.cost_usd for s in steps]), bodies=bodies,
    )


async def run_offline(workdir: Path) -> Outcome:
    settings = demo_settings(workdir)
    provider = MockProvider()
    store, runtime, engine, pid = build(workdir, settings, provider)
    for text in (CHARTER, PERSONAS, PROBLEM, VISION, FUNCTIONAL, NFR, EPICS_BAD, EPICS_GOOD):
        provider.queue("demo-model", ProviderResponse(text, Usage(1800, 420), "stop"))
    provider.queue("demo-haiku", ProviderResponse(STORIES, Usage(2400, 500), "stop"))

    done = await run_chain(store, runtime, engine, pid)
    epics = next(r for _, key, r in done if key == "epics_features")
    # What HAPPENED, read back from the calls: the repair message that went to the model, and the saved text.
    repairs = [c.request.messages[-1].content for c in provider.calls if len(c.request.messages) == 3]
    saved_epics = parse_items(store.artefacts.get_version(pid, epics.artefact_id).body, runtime.skills.get("epics_features").items)
    fixed = any("NFR-002" in item.derives for item in saved_epics.items)
    caught = epics.attempts == 2 and len(repairs) == 1 and "NFR-002" in repairs[0] and fixed
    notes = {
        "epics_features": (
            "the first reply left NFR-002 uncovered; it was refused with that reason and the corrected reply was saved"
            if caught else "the uncovered requirement was SAVED, because the coverage check did not fire"),
        "user_stories": "written by the Haiku slot (the backlog splitter role)",
        "functional_requirements": "each requirement names the personas and problem it comes from; those references were saved as links",
    }
    return summarise(store, pid, done, notes, caught)


async def run_with_provider(workdir: Path, settings: Settings, provider) -> Outcome:
    store, runtime, engine, pid = build(workdir, settings, provider)
    done = await run_chain(store, runtime, engine, pid)
    return summarise(store, pid, done, {}, gap_caught=False)


def render(outcome: Outcome, *, banner: str | None, show_full: bool, expected: int = len(CHAIN)) -> str:
    lines = [banner, ""] if banner else []
    for step in outcome.steps:
        lines.append(describe(step))
        if step.note:
            lines.append(f"    {step.note}")
    lines += ["", f"{outcome.saved}/{expected} artefacts saved, {outcome.items} items, {outcome.links} links, total cost {money(outcome.total_cost)}"]
    if show_full:
        for step in outcome.steps:
            if step.key in SHOWN_IN_FULL:
                lines += ["", f"----- {step.label} ({step.result.artefact_id}) " + "-" * 30, outcome.bodies[step.key]]
    return "\n".join(lines)


def _clean(text: str) -> str:
    return re.sub(r"https?://\S+", "[url removed]", text)


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="run the phase through IBM ICA (real calls, small cost)")
    parser.add_argument("--record", metavar="NAME", help="with --live: save every reply under backend/recordings/NAME")
    parser.add_argument("--replay", metavar="NAME", help="run the phase from backend/recordings/NAME, no network")
    args = parser.parse_args(argv)
    if args.record and not args.live:
        parser.error("--record only makes sense with --live")
    if args.live and args.replay:
        parser.error("choose --live or --replay, not both")
    name = args.record or args.replay
    if name is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
        parser.error("a recording name is letters, digits, '-' and '_' only, up to 64 characters")

    with tempfile.TemporaryDirectory(prefix="sdlc_requirements_demo_") as tmp:
        workdir = Path(tmp)
        if not args.live and not args.replay:
            outcome = asyncio.run(run_offline(workdir))
            print(render(outcome, banner=BANNER, show_full=False))
            print("\n" + ("1 coverage gap caught and repaired" if outcome.gap_caught else "the coverage gap was NOT caught"))
            return 0 if outcome.gap_caught and outcome.saved == len(CHAIN) else 1

        cfg = settings or get_settings()
        if args.live:
            missing = [n for n, ok in (("IBM_ICA_ENDPOINT", cfg.endpoint_set), ("IBM_ICA_API_KEY", cfg.api_key_set)) if not ok]
            if missing:
                print(f"Cannot run live: {', '.join(missing)} not set in backend/.env", file=sys.stderr)
                return 2
        try:
            outcome = asyncio.run(_run_real(workdir, cfg, args.live, name))
        except (AgentError, LLMError, IcaConfigError) as exc:
            print(f"The {'real-model' if args.live else 'replay'} run failed: {_clean(str(exc))}", file=sys.stderr)
            return 1
        header = ("REAL MODELS via IBM ICA" + (f" (recording to '{name}')" if name else "")) if args.live else f"REPLAY of recording '{name}' (no network)"
        print(render(outcome, banner=header, show_full=True))
        print("\nWhat to look for: attempts = 1 everywhere means the models followed the formats first time. Read the functional "
              "requirements and the user stories above: are the IDs sensible, does each requirement name a persona, "
              "does anything look invented?")
        return 0


async def _run_real(workdir: Path, cfg: Settings, live: bool, name: str | None) -> Outcome:
    if not live:
        folder = cfg.model_copy(update={"replay_set": name}).recordings_path
        return await run_with_provider(workdir, cfg, ReplayProvider(RecordingStore(folder)))
    ica = IcaProvider(cfg)
    try:
        provider = ica
        if name:
            folder = cfg.model_copy(update={"replay_set": name}).recordings_path
            provider = RecordingProvider(ica, RecordingStore(folder), cfg)
        return await run_with_provider(workdir, cfg, provider)
    finally:
        await ica.aclose()


if __name__ == "__main__":
    raise SystemExit(main())
