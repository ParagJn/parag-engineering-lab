"""Show a whole Build phase through the phase runner, offline and free: scripted developers, the REAL sandbox, the REAL generated tests. No model is called.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.build_phase_demo

Three runs, each in a temporary project that is deleted afterwards (your real workspaces and database are not touched):
  1 everything goes right, except the backend returns the wrong shape; the loop fixes it in round 2
  2 the backend does not compile three times running; the tests and the loop are skipped, and the reason is named
  3 the money cap is reached after the first wave; the tests are not run, and the run says it was stopped
"""
from __future__ import annotations

import asyncio
import itertools
import tempfile
from pathlib import Path

from app.agents.runtime import AgentRuntime
from app.agents.skills import SkillLibrary
from app.build.loop import FixLoop
from app.build.phase import BuildHooks
from app.build.service import BuildService
from app.config import Settings
from app.guardrails.scan import Scanner
from app.llm.gateway import Gateway
from app.llm.providers.mock import MockProvider
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.repos import Store
from app.review.prompt import load_rubric
from app.review.service import ReviewService
from app.run.events import EventBus
from app.run.runner import PhaseRunner
from app.sandbox.runner import Sandbox
from app.sandbox.service import SandboxService
from app.build import legacy
from app.workflow.engine import WorkflowEngine
from scripts.fix_loop_demo import BROKEN_TESTS, GOOD, LLD, MODELS, TESTS, WRONG, body  # noqa: F401 - the same small project the fix-loop demo uses

SCHEMA = "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, text TEXT NOT NULL);\n"
INIT = ("import os, sqlite3\nhere = os.path.dirname(os.path.abspath(__file__))\nc = sqlite3.connect(os.path.join(here, 'app.db'))\n"
        "c.executescript(open(os.path.join(here, 'schema.sql')).read())\nc.commit()\nprint('ok')\n")
DB = [("db/schema.sql", SCHEMA), ("db/init_db.py", INIT)]
FE = [("frontend/index.html", "<!doctype html><html><body><ul id=\"n\"></ul><script src=\"app.js\"></script></body></html>"),
      ("frontend/app.js", "fetch('/notes').then(r => r.json()).then(rows => { document.title = rows.length + ' notes'; });")]
BROKEN = [("backend/main.py", "def f(:\n    pass\n")]
PRICES = {**MODELS, "ibm_ica_haiku_price_input_per_mtok": "2", "ibm_ica_haiku_price_output_per_mtok": "10",
          "ibm_ica_gemini_price_input_per_mtok": "2", "ibm_ica_gemini_price_output_per_mtok": "10"}
FOUR = ["database_schema", "backend_code", "frontend_code", "test_suite"]


def reply(entries, prefix) -> ProviderResponse:
    text = body(entries, prefix)
    return ProviderResponse(f"<artefact>\n{text}\n</artefact>", Usage(1000, 200), "stop")


def line(label: str, what: str) -> str:
    return f"  {label:<46} {what}"


async def story(workdir: Path, name: str, replies: dict[str, list], **settings):
    cfg = Settings(_env_file=None, data_dir=str(workdir / name / "data"), recordings_dir=str(workdir / name / "rec"), llm_retry_backoff_seconds=0, **{**PRICES, **settings})
    store = Store.open(workdir / name / "demo.db", limits=cfg.context_limits)
    project = store.projects.create(name=name, brief="", actor="system")
    catalogue = legacy.catalogue()
    library = legacy.library(catalogue)
    provider = MockProvider()
    ids = itertools.count(1)
    gateway = Gateway(cfg, Routing.load(), provider, store, call_id_factory=lambda: f"call{next(ids)}")
    engine = WorkflowEngine(catalogue, store)
    runtime = AgentRuntime(cfg, store, gateway, catalogue, engine, library)
    service = SandboxService(cfg, store, Scanner.from_settings(cfg), Sandbox())
    builder = BuildService(service)
    hooks = BuildHooks(FixLoop(cfg, store, runtime, library, builder, service), builder, store, library, cfg)
    bus = EventBus(store, queue_size=cfg.run_event_queue, secrets=cfg.secret_values)
    runner = PhaseRunner(cfg, store, engine, runtime, ReviewService(cfg, store, gateway, runtime, engine, load_rubric()), bus, build=hooks)
    engine.open_project(project.id)
    store.phases.ensure(project.id, "build", actor="system")
    store.phases.set_status(project.id, "build", "running", actor="system")
    for key in ("low_level_design", "high_level_design", "functional_requirements", "hifi_wireframes", "user_journey"):
        skill = library.get(key)
        store.artefacts.create_and_add_version(project.id, artefact_type=key, phase_key=skill.artefact.phase_key, title=skill.artefact.name,
                                               prefix=skill.artefact.id_prefix, body=LLD if key == "low_level_design" else "## Overview\nx\n", author="human:demo")
    for model, items in replies.items():
        provider.queue(model, *items)
    result = await runner.run_phase(project.id, "build", only=FOUR)
    return result, provider, store, project, service


def states(result) -> str:
    return ", ".join(f"{o.key.split('_')[0]}:{o.state}" for o in result.outcomes)


async def demo(workdir: Path) -> list[str]:
    out = ["BUILD PHASE DEMO (scripted developers; the generated tests are really run in the sandbox)", ""]
    problem = Sandbox().availability()
    out.append(line("operating-system protection", "ready" if not problem else f"NOT AVAILABLE: {problem}"))
    if problem:
        return out + ["", "Nothing can be run without it, which is the point."]

    out += ["", "1  all four written together; the backend returns the wrong shape and the loop fixes it"]
    result, provider, store, project, service = await story(
        workdir, "one", {"m-haiku": [reply(DB, "DBF")], "m-gemini": [reply(FE, "FEF")], "m-openai": [reply(WRONG, "BEF"), reply(TESTS, "TSF"), reply(GOOD, "BEF")]})
    out += [line("  artefacts", states(result)), line("  most at once", str(result.max_in_flight)),
            line("  the loop", f"{result.build.result.upper()}: {result.build.reason[:58]}"),
            line("  model calls / cost", f"{result.totals['calls']} / ${result.totals['cost_usd']:.4f}"),
            line("  events", ", ".join(dict.fromkeys(e.type for e in store.run_events.list(project.id, run_id=result.run_id)))[:80]),
            line("  files in the workspace", ", ".join(sorted(p for p in service.list_files(project.id) if not p.endswith("app.db"))))]

    out += ["", "2  the backend does not compile, three tries running"]
    result, provider, store, project, service = await story(
        workdir, "two", {"m-haiku": [reply(DB, "DBF")], "m-gemini": [reply(FE, "FEF")], "m-openai": [reply(BROKEN, "BEF")] * 3})
    out += [line("  artefacts", states(result)), line("  the loop", f"{result.build.result.upper()}: {result.build.reason[:70]}"),
            line("  backend files left behind", str([p for p in service.list_files(project.id) if p.startswith('backend/')]))]

    out += ["", "3  the money cap is reached after the first wave"]
    result, provider, store, project, service = await story(
        workdir, "three", {"m-haiku": [reply(DB, "DBF")], "m-gemini": [reply(FE, "FEF")], "m-openai": [reply(GOOD, "BEF"), reply(TESTS, "TSF")]}, run_max_cost_usd=0.012)
    out += [line("  run", f"{result.status.upper()} ({result.stop_reason})"), line("  the loop", f"{result.build.result.upper()}: {result.build.reason[:62]}"),
            line("  model calls", str(len(provider.calls)))]
    return out


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sdlc_build_phase_demo_") as folder:
        print("\n".join(asyncio.run(demo(Path(folder)))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
