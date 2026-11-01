"""Run the Architecture phase for the sample project: offline with scripted replies (free), or once for real with Sonnet.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.architecture_demo                                   # offline, free, scripted
    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.architecture_demo --live --from phase4 --record phase5  # REAL, Architecture only, saved
    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.architecture_demo --replay phase5                    # from the saved replies, free

THE OFFLINE MODE USES A SCRIPTED FAKE MODEL. Its components, decisions and endpoints are written below, in advance. It shows the checks: a high-level
design that points at a component that does not exist is sent back, a component overview that leaves a requirement unserved is caught, a clean run is
saved. It says nothing about how well a real model designs.

--live runs Setup, Requirements and Design from `--from NAME` (an earlier recording, free: the same sample project asks the same questions), then
Architecture with the REAL models (Sonnet for the three written artefacts). Only the Architecture calls cost money. `--record NAME` saves every reply
under backend/recordings/NAME, together with a copy of `--from`, so that NAME replays the whole chain from Setup to Architecture. It needs your key,
so you run it. It never prints the key, the endpoint or the user-agent.

The flow and use-case diagrams are written as plain lists by the model (Haiku) and drawn by the server; the demo checks the lists, not the pictures.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from app.agents.errors import AgentError
from app.agents.items import parse_items
from app.agents.skills import SkillLibrary
from app.config import Settings, get_settings
from app.llm.errors import LLMError, ReplayMiss
from app.llm.providers.ica import IcaConfigError, IcaProvider
from app.llm.providers.recording import RecordingProvider, ReplayProvider
from app.llm.recordings import RecordingStore
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.models import InvalidInput
from app.repos import Store
from app.workflow.definitions import load_catalogue

from .agent_demo import block, money
from .design_demo import MODELS, Scripted as DesignScripted, build, through

BANNER = (
    "*** SCRIPTED FAKE MODEL. The components, decisions and endpoints were written in advance inside scripts/architecture_demo.py. ***\n"
    "*** This shows the checks on Architecture, NOT how well a real model designs. Use --live for that. ***"
)
ARCHITECTURE = ("component_overview", "high_level_design", "low_level_design")
DIAGRAMS = ("flow_diagram", "usecase_diagram")        # optional in the catalogue; written from lists and drawn by the server (S14b)
EVERY = ARCHITECTURE + DIAGRAMS

COMPONENTS = block({
    "Overview": "Three components, divided by what changes together: the rules for booking, the rules for maintaining rooms, and the data both use.",
    "Components": (
        "- COMP-001 Booking service: decides whether a room is free for a slot and records or refuses a reservation; it keeps no data itself. Derives from: FR-001, NFR-001\n"
        "- COMP-002 Room administration service: lets the administrator add, rename and retire rooms; it takes no bookings. Derives from: FR-002, NFR-002\n"
        "- COMP-003 Room and booking store: keeps the rooms and the reservations; it holds no rules. Derives from: FR-001, FR-002"),
    "Coverage check": "None.",
    "Open questions": "Is there an existing staff directory the booking service must use to identify staff?",
})


def decisions(bad: bool = False) -> str:
    """The high-level design. `bad` makes the second interface point at a component the overview does not have."""
    second = "COMP-002, COMP-009, DEC-001" if bad else "COMP-002, COMP-003, DEC-001"
    return block({
        "Overview": "Staff reach the booking service, the administrator reaches the room administration service, and both read and write one store.",
        "Decisions": (
            "- DEC-001 Both services share one store, so a booking can never be accepted for a room that was just retired; separate stores were considered "
            "and rejected because the two would have to agree on every change. A proposal for the technical lead. Derives from: COMP-001, COMP-002, COMP-003, NFR-002\n"
            "- DEC-002 Only office staff reach the booking service; how staff are identified is open. A proposal for the technical lead. Derives from: COMP-001, NFR-002"),
        "Interfaces": (
            "- IFC-001 The booking service asks the store whether a room is free for a slot and writes the reservation; the call waits for the answer. Derives from: COMP-001, COMP-003, DEC-001\n"
            f"- IFC-002 The room administration service reads and changes the room list in the store; the call waits for the answer. Derives from: {second}"),
        "Coverage check": "None.",
        "Open questions": "How are staff identified?",
    })


LOW_LEVEL = block({
    "Overview": "Three endpoints, two tables and two rules: the booking service owns one endpoint, the room administration service owns two, and the store owns both tables.",
    "Endpoints": (
        "- API-001 POST /bookings reserves a room for a slot, or answers that the slot is taken (409). Owned by COMP-001. Derives from: COMP-001, IFC-001, FR-001\n"
        "- API-002 POST /rooms adds a room and returns it. Owned by COMP-002. Derives from: COMP-002, IFC-002, FR-002\n"
        "- API-003 PATCH /rooms/{id} renames or retires a room. Owned by COMP-002. Derives from: COMP-002, IFC-002, FR-002"),
    "Tables": (
        "- TBL-001 rooms: id (key), name, retired (yes or no). Owned by COMP-003. Derives from: COMP-003, FR-002\n"
        "- TBL-002 bookings: id (key), room id, start, end. Owned by COMP-003. Derives from: COMP-003, FR-001"),
    "Rules": (
        "- RUL-001 A booking whose room and slot overlap an existing booking is refused. Derives from: FR-001\n"
        "- RUL-002 A retired room cannot be booked. Derives from: FR-002"),
    "Coverage check": "None.",
    "Open questions": "What is the longest a booking may last?",
})

FLOW = block({
    "Overview": "Four calls between the three components: staff ask the booking service, which asks the store; the administration service changes the store.",
    "Flow": (
        "- FLOW-001 COMP-001 -> COMP-003: asks if a room is free. Derives from: IFC-001, COMP-001, COMP-003\n"
        "- FLOW-002 COMP-003 -> COMP-001: answers free or taken. Derives from: IFC-001, COMP-001, COMP-003\n"
        "- FLOW-003 COMP-002 -> COMP-003: changes the room list. Derives from: IFC-002, COMP-002, COMP-003\n"
        "- FLOW-004 COMP-003 -> COMP-002: confirms the change. Derives from: IFC-002, COMP-002, COMP-003"),
    "Coverage check": "None.",
    "Open questions": "None.",
})


def usecases(bad: bool = False) -> str:
    """The use-case diagram. `bad` gives the second use case an actor (PER-009) that is not a persona."""
    admin = "PER-009, FR-002" if bad else "PER-002, FR-002"
    return block({
        "Overview": "Two people take part in three use cases.",
        "Use cases": (
            "- UC-001 Find a free room: staff look at the rooms free for a time. Derives from: PER-001, FR-001\n"
            "- UC-002 Reserve a room: staff reserve a free room or are told the slot is taken. Derives from: PER-001, FR-001\n"
            f"- UC-003 Maintain rooms: the administrator adds, renames and retires rooms. Derives from: {admin}"),
        "Coverage check": "None.",
        "Open questions": "None.",
    })


REPLIES = {"component_overview": COMPONENTS, "high_level_design": decisions(), "low_level_design": LOW_LEVEL, "flow_diagram": FLOW, "usecase_diagram": usecases()}


class Scripted(DesignScripted):
    """Answers the earlier phases as the Design demo does, and Architecture from the replies above. The FIRST high-level design points an interface
    at a component that does not exist, so the repair can be seen once."""

    def __init__(self) -> None:
        super().__init__()
        self.hld_calls = 0
        self.uc_calls = 0

    def _which(self, request) -> str:
        text = request.messages[0].content
        for key in EVERY:
            if f"({key}) for the project" in text:
                return key
        return super()._which(request)

    async def complete(self, model_id, request):
        key = self._which(request)
        if key in EVERY:
            self.asked.append(key)
            if key == "high_level_design":
                self.hld_calls += 1
                return ProviderResponse(decisions(bad=self.hld_calls == 1), Usage(2400, 1200), "stop")
            if key == "usecase_diagram":
                self.uc_calls += 1
                return ProviderResponse(usecases(bad=self.uc_calls == 1), Usage(1200, 500), "stop")
            return ProviderResponse(REPLIES[key], Usage(2000, 900), "stop")
        return await super().complete(model_id, request)


class Layered:
    """Answers from a saved recording where it has one, and from the real provider where it does not. Lets Architecture be run for real on top of
    the free Setup, Requirements and Design replies of an earlier recording."""

    def __init__(self, replay: ReplayProvider, live) -> None:
        self.replay = replay
        self.live = live
        self.label = f"{replay.label}+{live.label}"

    async def complete(self, model_id, request):
        try:
            return await self.replay.complete(model_id, request)
        except ReplayMiss:
            return await self.live.complete(model_id, request)

    async def aclose(self) -> None:
        close = getattr(self.live, "aclose", None)
        if close is not None:
            await close()


async def run(workdir: Path, settings: Settings, provider) -> tuple[Store, str, object]:
    store, engine, runner, pid = build(workdir, settings, provider)
    for phase in ("setup", "requirements", "design"):
        await through(runner, engine, pid, phase)
    return store, pid, await runner.run_phase(pid, "architecture")


def describe(store: Store, pid: str) -> list[str]:
    """What each written artefact holds: its size and how many items of each kind, so a thin or runaway result is visible at a glance."""
    skills = SkillLibrary.load(load_catalogue(Routing.load().roles.keys()))
    out = []
    for artefact in store.artefacts.list(pid, phase_key="architecture"):
        if artefact.latest_version is None:
            continue
        body = store.artefacts.get_version(pid, artefact.id).body
        skill = skills.get(artefact.type)
        counts: dict[str, int] = {}
        for item in parse_items(body, skill.items).items if skill and skill.items else ():
            counts[item.prefix] = counts.get(item.prefix, 0) + 1
        said = ", ".join(f"{n} {prefix}" for prefix, n in counts.items())
        out.append(f"  {artefact.title}: {len(body)} characters" + (f", {said}" if said else ""))
    return out


def render(store: Store, pid: str, result, banner: str | None) -> list[str]:
    lines = [banner, ""] if banner else []
    counts = result.totals["artefacts"]
    lines.append(f"Architecture: {result.status}: {counts['done']} written, {counts['failed']} failed, {counts['skipped']} skipped; "
                 f"{result.totals['calls']} call(s), cost {money(result.totals['cost_usd'])}")
    for outcome in result.outcomes:
        lines.append(f"  {outcome.key}: {outcome.state}" + (f" ({outcome.reason})" if outcome.reason else ""))
    lines += describe(store, pid)
    for artefact in store.artefacts.list(pid, phase_key="architecture"):
        if artefact.latest_version is None:
            continue
        generation = store.artefacts.get_version(pid, artefact.id).generation or {}
        for repair in generation.get("repair_reasons", []):
            for problem in repair["problems"]:
                lines.append(f"  {artefact.title}: attempt {repair['attempt']} was sent back: {problem[:200]}")
    return lines


def written(result) -> bool:
    """All five artefacts are done: the three written ones and the two diagrams."""
    return all(o.state == "done" for o in result.outcomes if o.key in EVERY) and len([o for o in result.outcomes if o.key in EVERY]) == len(EVERY)


async def run_offline(workdir: Path) -> tuple[list[str], bool]:
    settings = Settings(_env_file=None, data_dir=str(workdir / "data"), recordings_dir=str(workdir / "rec"), llm_retry_backoff_seconds=0, run_max_cost_usd=0, **MODELS)
    provider = Scripted()
    store, pid, result = await run(workdir, settings, provider)
    lines = render(store, pid, result, BANNER)
    repaired = any("was sent back" in l and "COMP-009" in l for l in lines)
    actor_caught = any("was sent back" in l and "PER-009" in l for l in lines)
    good = written(result) and repaired and actor_caught and provider.hld_calls == 2 and provider.uc_calls == 2
    lines.append("")
    lines.append("an interface pointing at a component that does not exist was sent back and rewritten" if repaired else "THE INVENTED COMPONENT WAS NOT CAUGHT")
    lines.append("a use case with an actor that is not a persona was sent back and rewritten" if actor_caught else "THE INVENTED ACTOR WAS NOT CAUGHT")
    return lines, good


def _clean(text: str) -> str:
    return re.sub(r"https?://\S+", "[url removed]", text)


async def run_real(workdir: Path, cfg: Settings, live: bool, name: str | None, earlier: str | None) -> tuple[Store, str, object]:
    def folder(of: str) -> Path:
        return cfg.model_copy(update={"replay_set": of}).recordings_path

    if not live:
        return await run(workdir, cfg, ReplayProvider(RecordingStore(folder(name))))
    ica = IcaProvider(cfg)
    try:
        live_provider = ica
        if name:
            if earlier:
                shutil.copytree(folder(earlier), folder(name), dirs_exist_ok=True)       # NAME then replays the whole chain, not only Architecture
            live_provider = RecordingProvider(ica, RecordingStore(folder(name)), cfg)
        provider = Layered(ReplayProvider(RecordingStore(folder(earlier))), live_provider) if earlier else live_provider
        return await run(workdir, cfg, provider)
    finally:
        await ica.aclose()


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="run Architecture with real models (tens of cents); Setup to Design come from --from if given, else cost money too")
    parser.add_argument("--from", dest="earlier", metavar="NAME", help="with --live: answer Setup, Requirements and Design from backend/recordings/NAME (free)")
    parser.add_argument("--record", metavar="NAME", help="with --live: save every reply under backend/recordings/NAME")
    parser.add_argument("--replay", metavar="NAME", help="run from backend/recordings/NAME, no network")
    args = parser.parse_args(argv)
    if args.record and not args.live:
        parser.error("--record only makes sense with --live")
    if args.earlier and not args.live:
        parser.error("--from only makes sense with --live")
    if args.live and args.replay:
        parser.error("choose --live or --replay, not both")
    for label, value in (("recording", args.record or args.replay), ("--from", args.earlier)):
        if value is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value):
            parser.error(f"a {label} name is letters, digits, '-' and '_' only, up to 64 characters")
    if args.record and args.record == args.earlier:
        parser.error("--record and --from must be different names, or the copy would overwrite itself")
    name = args.record or args.replay

    with tempfile.TemporaryDirectory(prefix="sdlc_architecture_demo_") as tmp:
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
            store, pid, result = asyncio.run(run_real(workdir, cfg, args.live, name, args.earlier))
        except (AgentError, LLMError, IcaConfigError, InvalidInput) as exc:
            print(f"The {'real-model' if args.live else 'replay'} run failed: {_clean(str(exc))}", file=sys.stderr)
            return 1
        header = ("REAL MODELS via IBM ICA" + (f" for Architecture, earlier phases from '{args.earlier}'" if args.earlier else "") + (f" (recording to '{name}')" if name else "")) if args.live else f"REPLAY of recording '{name}' (no network)"
        print("\n".join(render(store, pid, result, header)))
        print("\nWhat to look for: are all five artefacts written, and in how many attempts? Does every requirement have a component? Open the app: read "
              "the components, then the endpoints and tables, then look at the two pictures and check that each arrow and each line is one you would expect.")
        return 0 if written(result) else 1


if __name__ == "__main__":
    raise SystemExit(main())
