"""Run a whole phase and watch the events, offline, and (optionally) once for real.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.run_demo                    # offline, free
    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.run_demo --live             # REAL calls
    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.run_demo --live --serial    # one at a time, to compare

OFFLINE MODE USES A SCRIPTED FAKE MODEL, NOT A REAL ONE. Its replies are written into scripts/requirements_demo.py and
its delays are made up (proportional to how long each artefact's output was in your real run). It shows four things:
the events as they arrive, how much faster a run is with several artefacts at once, a run stopped by a money cap, and
a failure that skips only the artefacts that needed it. It says nothing about how fast or how good a real model is.
That is what --live is for.

--live runs the Requirements phase of the sample project with real models and prints the events as they happen, how
long it really took against the sum of the individual artefacts, and what it really cost. About 8 calls, around 20
cents. It needs your key, so you run it; it never prints the key, the endpoint or the user-agent.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
import time
from pathlib import Path
from typing import Sequence

from app.agents.errors import AgentError
from app.agents.runtime import AgentRuntime
from app.agents.skills import SkillLibrary
from app.config import Settings, get_settings
from app.llm.errors import ContentFilterBlocked, LLMError
from app.llm.gateway import Gateway
from app.llm.providers.ica import IcaConfigError, IcaProvider
from app.llm.providers.mock import MockProvider
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.models import InvalidInput
from app.repos import Store
from app.review.prompt import load_rubric
from app.review.service import ReviewService
from app.run.events import EventBus
from app.run.runner import DONE, FAILED, SKIPPED, PhaseRunner, RunResult
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine

from app.sample import FILENAME, NAME
from .agent_demo import BRIEF, CHARTER, POLICY, PROBLEM, money
from .requirements_demo import EPICS_GOOD, FUNCTIONAL, NFR, PERSONAS, STORIES, VISION

PERSON = "human:demo"
BANNER = (
    "*** SCRIPTED FAKE MODEL. The replies were written in advance, and the delays below are made up. ***\n"
    "*** This shows the scheduler, the caps and the events, NOT how fast or how good a real model is. Use --live for that. ***"
)
MODELS = dict(
    ibm_ica_model_id="demo-model", ibm_ica_fallback_model_id="demo-model", ibm_ica_haiku_model_id="demo-haiku",
    ibm_ica_haiku_fallback_model_id="demo-model",
    ibm_ica_price_input_per_mtok="2", ibm_ica_price_output_per_mtok="10",
    ibm_ica_haiku_price_input_per_mtok="1", ibm_ica_haiku_price_output_per_mtok="2",
)
REPLIES = {
    "project_charter": CHARTER, "personas": PERSONAS, "problem_statement": PROBLEM, "vision_objectives": VISION,
    "functional_requirements": FUNCTIONAL, "non_functional_requirements": NFR, "epics_features": EPICS_GOOD, "user_stories": STORIES,
}
# Seconds of fake "thinking" per artefact, in proportion to the output tokens of the real Requirements run.
THINK = {"personas": 1.3, "problem_statement": 1.2, "vision_objectives": 1.3, "functional_requirements": 4.0,
         "non_functional_requirements": 2.1, "epics_features": 3.3, "user_stories": 4.7, "project_charter": 0.1}
SCALE = 0.1


class Scripted(MockProvider):
    def __init__(self, scale: float = SCALE):
        super().__init__()
        self.scale = scale
        self.fail: set[str] = set()

    def _which(self, request) -> str:
        text = request.messages[0].content
        for key in REPLIES:
            if f"({key}) for the project" in text:
                return key
        raise RuntimeError("scripted model: unknown task")

    async def complete(self, model_id, request):
        key = self._which(request)
        await asyncio.sleep(THINK[key] * self.scale)
        if key in self.fail:
            raise ContentFilterBlocked("blocked")
        return ProviderResponse(REPLIES[key], Usage(1800, 420), "stop")


def build(workdir: Path, settings: Settings, provider):
    store = Store.open(workdir / "demo.db", limits=settings.context_limits)
    routing = Routing.load()
    catalogue = load_catalogue(routing.roles.keys())
    engine = WorkflowEngine(catalogue, store)
    gateway = Gateway(settings, routing, provider, store)
    runtime = AgentRuntime(settings, store, gateway, catalogue, engine, SkillLibrary.load(catalogue))
    reviews = ReviewService(settings, store, gateway, runtime, engine, load_rubric())
    bus = EventBus(store, queue_size=settings.run_event_queue, secrets=settings.secret_values)
    runner = PhaseRunner(settings, store, engine, runtime, reviews, bus)
    project = store.projects.create(name=NAME, brief=BRIEF, actor="system")
    engine.open_project(project.id)
    store.context.add_document(project.id, FILENAME, POLICY, actor=PERSON)
    return store, engine, runner, bus, project.id


async def through_setup(runner: PhaseRunner, engine: WorkflowEngine, pid: str) -> RunResult:
    result = await runner.run_phase(pid, "setup")
    engine.finish(pid, "setup", actor="system")
    engine.approve(pid, "setup", actor=PERSON)
    return result


def describe_event(event, t0: float) -> str:
    d = event.data
    bits = {
        "run.started": lambda: f"{len(d['artefacts'])} artefact(s), up to {d['concurrency']} at once",
        "gate.changed": lambda: f"{d['phase']} is now {d['status']}",
        "artefact.started": lambda: d["key"],
        "artefact.attempt": lambda: f"{d['key']} attempt {d['attempt']}" + (" (repairing)" if d.get("will_repair") else ""),
        "artefact.finished": lambda: f"{d['key']} saved as {d['artefact_id']} v{d['version']}, {d['attempts']} attempt(s), {d['items']} item(s)",
        "artefact.failed": lambda: f"{d['key']}: {d['reason']}",
        "artefact.skipped": lambda: f"{d['key']}: {d['reason']}",
        "review.started": lambda: d["artefact_id"],
        "review.finished": lambda: f"{d['artefact_id']}: {d['verdict']} ({d['label']})",
        "review.paused": lambda: d["artefact_id"],
        "run.stopped": lambda: f"{d.get('status')}" + (f", reason {d['reason']}" if d.get("reason") else ""),
        "run.finished": lambda: f"{d['status']}, {d['artefacts']['done']} done",
    }
    text = bits[event.type]() if event.type in bits else ""
    return f"  {time.monotonic() - t0:5.2f}s  {event.type:18s} {text}"


def summarise(result: RunResult) -> str:
    counts = result.totals["artefacts"]
    return (f"{result.status}"
            f"{' (' + result.stop_reason + ')' if result.stop_reason else ''}: "
            f"{counts['done']} done, {counts['failed']} failed, {counts['skipped']} skipped, {counts['not_started']} not started; "
            f"{result.totals['calls']} call(s), cost {money(result.totals['cost_usd'])}"
            f"{' (partial: some calls had no price)' if result.totals['cost_is_partial'] else ''}; "
            f"wall {result.elapsed_seconds:.2f}s")


async def one_run(workdir: Path, settings: Settings, provider, *, prepare=None, show_events=False, **options) -> tuple[RunResult, list[str]]:
    store, engine, runner, bus, pid = build(workdir, settings, provider)
    await through_setup(runner, engine, pid)
    if prepare:
        prepare(provider)
    lines: list[str] = []
    t0 = time.monotonic()
    watcher = bus.watch(pid)
    seen_until = store.run_events.last_id(pid)

    async def watch() -> None:
        while True:
            event = await watcher.queue.get()
            if event is None:
                return
            if event.id > seen_until and show_events:
                lines.append(describe_event(event, t0))

    reader = asyncio.create_task(watch())
    try:
        result = await asyncio.wait_for(runner.run_phase(pid, "requirements", **options), 30)   # a scripted run takes a few seconds
        await asyncio.sleep(0.05)                      # let the watcher print the last events
    finally:
        reader.cancel()
        bus.unwatch(watcher)
    return result, lines


async def run_offline(workdir: Path) -> tuple[list[str], bool]:
    out: list[str] = []
    ok: list[bool] = []

    def settings(name: str, **extra) -> Settings:
        folder = workdir / name
        folder.mkdir(parents=True, exist_ok=True)
        return Settings(_env_file=None, data_dir=str(folder / "data"), recordings_dir=str(folder / "rec"), llm_retry_backoff_seconds=0, **MODELS, **extra)

    # 1. the events, with three artefacts at once
    out.append("1. A whole phase in one call, with the events as they arrive (up to 3 artefacts at once):")
    wide, lines = await one_run(workdir / "a", settings("a", run_max_cost_usd=0), Scripted(), show_events=True)
    out += lines
    out.append(f"   -> {summarise(wide)}")
    ok.append(wide.status == "finished" and wide.max_in_flight == 3)

    # 2. the speed-up, against the same phase one artefact at a time
    one, _ = await one_run(workdir / "b", settings("b", run_max_cost_usd=0, run_max_concurrency=1), Scripted())
    speed = one.elapsed_seconds / wide.elapsed_seconds
    out.append("\n2. The same phase one artefact at a time, for comparison:")
    out.append(f"   -> {summarise(one)}")
    out.append(f"   -> {speed:.2f}x faster with 3 at once. The Requirements chain (personas, then requirements, then epics, then stories)"
               " is four steps deep, so it cannot go much faster than this however many run at once.")
    ok.append(1.15 < speed < 1.8)   # a range, not a number: this is wall-clock time on whatever machine runs it

    # 3. a money cap
    capped, lines = await one_run(workdir / "c", settings("c", run_max_cost_usd=0.012, run_max_concurrency=1), Scripted(), show_events=True)
    out.append("\n3. A cap of $0.012 (about two artefacts), one at a time:")
    out += [l for l in lines if "run.stopped" in l or "artefact.finished" in l]
    out.append(f"   -> {summarise(capped)}")
    over = capped.totals["over_budget_by_usd"]
    out.append(f"   -> it went over the cap by {money(over)} (the artefact that reached the cap finished and saved); the rest never started")
    ok.append(capped.stop_reason == "budget" and over is not None)

    # 4. a failure that skips only its dependants
    def break_nfr(provider: Scripted) -> None:
        provider.fail.add("non_functional_requirements")

    failed, lines = await one_run(workdir / "d", settings("d", run_max_cost_usd=0), Scripted(), prepare=break_nfr, show_events=True)
    out.append("\n4. The non-functional requirements fail (the model refuses); who is affected:")
    out += [l for l in lines if "failed" in l or "skipped" in l]
    states = {o.key: o.state for o in failed.outcomes}
    out.append(f"   -> {summarise(failed)}")
    out.append(f"   -> still done: {', '.join(k for k, s in states.items() if s == DONE)}; "
               f"skipped without calling the model: {', '.join(k for k, s in states.items() if s == SKIPPED)}")
    ok.append(states["non_functional_requirements"] == FAILED and states["epics_features"] == SKIPPED and states["user_stories"] == SKIPPED
              and states["functional_requirements"] == DONE)
    return out, all(ok)


async def run_live(settings: Settings, workdir: Path) -> tuple[RunResult, list[str]]:
    provider = IcaProvider(settings)
    try:
        store, engine, runner, bus, pid = build(workdir, settings, provider)
        setup = await through_setup(runner, engine, pid)
        t0 = time.monotonic()
        watcher = bus.watch(pid)
        lines: list[str] = []
        last = store.run_events.last_id(pid)

        async def watch() -> None:
            while True:
                event = await watcher.queue.get()
                if event is None:
                    return
                if event.id > last:
                    line = describe_event(event, t0)
                    lines.append(line)
                    print(line, flush=True)

        reader = asyncio.create_task(watch())
        try:
            result = await runner.run_phase(pid, "requirements")
            await asyncio.sleep(0.1)
        finally:
            reader.cancel()
            bus.unwatch(watcher)
        return result, lines
    finally:
        await provider.aclose()


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="run the Requirements phase with real models (about 20 cents)")
    parser.add_argument("--serial", action="store_true", help="with --live: one artefact at a time, to compare with the default")
    args = parser.parse_args(argv)
    if args.serial and not args.live:
        parser.error("--serial only makes sense with --live")

    with tempfile.TemporaryDirectory(prefix="sdlc_run_demo_") as tmp:
        workdir = Path(tmp)
        if not args.live:
            lines, passed = asyncio.run(run_offline(workdir))
            print(BANNER + "\n")
            print("\n".join(lines))
            print("\n" + ("everything behaved as specified" if passed else "SOMETHING DID NOT BEHAVE AS SPECIFIED, see above"))
            return 0 if passed else 1

        cfg = settings or get_settings()
        missing = [n for n, ok in (("IBM_ICA_ENDPOINT", cfg.endpoint_set), ("IBM_ICA_API_KEY", cfg.api_key_set)) if not ok]
        if missing:
            print(f"Cannot run live: {', '.join(missing)} not set in backend/.env", file=sys.stderr)
            return 2
        if args.serial:
            cfg = cfg.model_copy(update={"run_max_concurrency": 1})
        print(f"REAL MODELS via IBM ICA ({'one at a time' if args.serial else f'up to {cfg.run_max_concurrency} at once'}; "
              f"cap {money(cfg.run_max_cost_usd) if cfg.run_max_cost_usd else 'off'} / {cfg.run_max_seconds:g}s)\n")
        try:
            result, _ = asyncio.run(run_live(cfg, workdir))
        except (AgentError, LLMError, IcaConfigError, InvalidInput) as exc:
            print(f"The real-model run failed: {exc}", file=sys.stderr)
            return 1
        print(f"\n{summarise(result)}")
        print(f"Time: {result.elapsed_seconds:.1f}s on the wall clock; the artefacts' own times add up to {result.serial_seconds:.1f}s "
              f"-> {result.serial_seconds / result.elapsed_seconds:.2f}x (that is the real speed-up from running some at once)")
        if result.totals["artefacts"]["done"] < len(result.outcomes):
            for o in result.outcomes:
                if o.state != DONE:
                    print(f"  {o.key}: {o.state}: {o.reason}")
        print("\nWhat to look for: how the real speed-up compares with the 1.3x to 1.4x I estimated; whether any artefact needed a "
              "repair (attempt 2 events); and whether the cost is near the $0.21 of your earlier run.")
        return 0 if result.status == "finished" else 1


if __name__ == "__main__":
    raise SystemExit(main())
