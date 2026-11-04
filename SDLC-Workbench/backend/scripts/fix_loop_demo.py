"""Show the write -> test -> fix loop working, offline and free: scripted developers, the REAL sandbox and the REAL generated tests. No model is called.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.fix_loop_demo

Five small stories, each in a temporary project that is deleted afterwards (your real workspaces and database are not touched):
  1 a developer fixes the backend in round 2          -> converged
  2 a developer who says "all tests pass" but doesn't -> not believed, stops
  3 a developer who never gets there                  -> cap_reached, after exactly the cap
  4 a broken test file                                -> goes to the test engineer first
  5 a spent budget                                    -> stopped before the next round, no further call
"""
from __future__ import annotations

import asyncio
import itertools
import tempfile
from pathlib import Path

from app.agents.runtime import AgentRuntime
from app.agents.skills import SkillLibrary
from app.build.loop import FixLoop
from app.build.service import BuildService
from app.config import Settings
from app.guardrails.scan import Scanner
from app.llm.gateway import Gateway
from app.llm.providers.mock import MockProvider
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.repos import Store
from app.run.budget import Meter
from app.sandbox.runner import Sandbox
from app.sandbox.service import SandboxService
from app.build import legacy
from app.workflow.engine import WorkflowEngine

MODELS = dict(
    ibm_ica_model_id="m-sonnet", ibm_ica_fallback_model_id="m-sonnet", ibm_ica_haiku_model_id="m-haiku",
    ibm_ica_openai_model_id="m-openai", ibm_ica_gemini_model_id="m-gemini",
    ibm_ica_price_input_per_mtok="2", ibm_ica_price_output_per_mtok="10",
    ibm_ica_openai_price_input_per_mtok="2", ibm_ica_openai_price_output_per_mtok="10",
)
LLD = ("## Overview\nx\n## Endpoints\n- API-001 GET /notes lists notes. Derives from: FR-001\n## Tables\n- TBL-001 notes: id, text. Derives from: FR-001\n"
       "## Rules\n- RUL-001 A note has text. Derives from: FR-001\n## Coverage check\nNone\n## Open questions\nNone")


def code(returns: str) -> list[tuple[str, str]]:
    return [("backend/main.py", f"from fastapi import FastAPI\napp = FastAPI()\n\n@app.get('/notes')\ndef notes():\n    return {returns}\n")]


GOOD, WRONG = code("[]"), code('{"items": []}')
TESTS = [("tests/test_notes.py", "from fastapi.testclient import TestClient\nfrom backend.main import app\n\n\ndef test_list_is_empty():\n    assert TestClient(app).get('/notes').json() == []\n")]
BROKEN_TESTS = [("tests/test_notes.py", "import nosuchmodule\n\n\ndef test_list_is_empty():\n    assert True\n")]


def body(entries: list[tuple[str, str]], prefix: str) -> str:
    lines = ["## Overview", "Scripted.", "", "## Files"]
    lines += [f"- {prefix}-{n:03d} {path}: file. Derives from: TBL-001, API-001" for n, (path, _) in enumerate(entries, start=1)]
    lines += ["", "## Code"]
    for path, text in entries:
        lines += [f"File: {path}", "```python", text.rstrip("\n"), "```", ""]
    lines += ["## Coverage check", "None", "", "## Open questions", "None"]
    return "\n".join(lines)


def reply(entries, prefix, claim: str = "") -> ProviderResponse:
    return ProviderResponse(f"<artefact>\n{body(entries, prefix)}\n</artefact>\n{claim}", Usage(1000, 200), "stop")


def line(label: str, what: str) -> str:
    return f"  {label:<46} {what}"


async def story(workdir: Path, name: str, saved_backend, saved_tests, replies, rounds=3, meter=None):
    settings = Settings(_env_file=None, data_dir=str(workdir / name / "data"), recordings_dir=str(workdir / name / "rec"), build_fix_rounds=rounds, **MODELS)
    store = Store.open(workdir / name / "demo.db", limits=settings.context_limits)
    project = store.projects.create(name=name, brief="", actor="system")
    catalogue = legacy.catalogue()
    library = legacy.library(catalogue)
    provider = MockProvider()
    ids = itertools.count(1)

    async def no_sleep(_):
        return None

    gateway = Gateway(settings, Routing.load(), provider, store, sleep=no_sleep, call_id_factory=lambda: f"call{next(ids)}")
    engine = WorkflowEngine(catalogue, store)
    runtime = AgentRuntime(settings, store, gateway, catalogue, engine, library)
    engine.open_project(project.id)
    store.phases.ensure(project.id, "build", actor="system")
    store.phases.set_status(project.id, "build", "running", actor="system")
    service = SandboxService(settings, store, Scanner.from_settings(settings), Sandbox())
    for key in ("low_level_design", "high_level_design", "functional_requirements"):
        skill = library.get(key)
        store.artefacts.create_and_add_version(project.id, artefact_type=key, phase_key=skill.artefact.phase_key, title=skill.artefact.name,
                                               prefix=skill.artefact.id_prefix, body=LLD if key == "low_level_design" else "## Overview\nx\n", author="human:demo")
    for key, prefix, entries in (("backend_code", "BEF", saved_backend), ("test_suite", "TSF", saved_tests)):
        skill = library.get(key)
        store.artefacts.create_and_add_version(project.id, artefact_type=key, phase_key="build", title=skill.artefact.name, prefix=skill.artefact.id_prefix,
                                               body=body(entries, prefix), author="human:demo")
    provider.queue("m-openai", *replies)
    loop = FixLoop(settings, store, runtime, library, BuildService(service), service)
    result = await loop.run(project.id, meter=meter)
    return result, provider, store, project


def describe(result) -> str:
    return f"{result.result.upper()}: {result.reason[:70]}"


def rounds_of(result) -> str:
    return " -> ".join(f"{n.outcome}({n.passed}p/{n.failed}f)" + (f" fix:{n.artefact}" if n.artefact else "") for n in result.rounds)


async def demo(workdir: Path) -> list[str]:
    out = ["FIX LOOP DEMO (scripted developers; the generated tests are really run in the sandbox)", ""]
    problem = Sandbox().availability()
    out.append(line("operating-system protection", "ready" if not problem else f"NOT AVAILABLE: {problem}"))
    if problem:
        return out + ["", "Nothing can be run without it, which is the point."]

    out += ["", "1  the backend returns the wrong shape; the developer fixes it in round 2"]
    result, provider, store, project = await story(workdir, "one", WRONG, TESTS, [reply(GOOD, "BEF")])
    out += [line("  result", describe(result)), line("  rounds", rounds_of(result)), line("  model calls", str(len(provider.calls)))]
    rows = store.build_rounds.list(project.id)
    out.append(line("  recorded rounds / audit rows", f"{len(rows)} / {len([a for a in store.audit.list(project.id) if a.action == 'build.round'])}"))

    out += ["", "2  the developer says every test passes, but the code is still wrong"]
    result, provider, *_ = await story(workdir, "two", WRONG, TESTS, [reply(WRONG, "BEF", "All tests pass now, I checked.")] * 3)
    out += [line("  result", describe(result)), line("  rounds", rounds_of(result))]

    out += ["", "3  a developer who never gets there: each fix breaks a different endpoint (cap 2)"]
    tests = [("tests/test_notes.py", "from fastapi.testclient import TestClient\nfrom backend.main import app\n\n\n"
                                     + "\n\n".join(f"def test_{p}():\n    assert TestClient(app).get('/{p}').status_code == 200\n" for p in "abc"))]

    def serving(*paths):
        return [("backend/main.py", "from fastapi import FastAPI\napp = FastAPI()\n" + "\n".join(f"@app.get('/{p}')\ndef {p}():\n    return []\n" for p in paths))]
    result, provider, *_ = await story(workdir, "three", serving("b", "c"), tests, [reply(serving("a", "c"), "BEF"), reply(serving("a", "b"), "BEF")], rounds=2)
    out += [line("  result", describe(result)), line("  rounds", rounds_of(result)), line("  model calls (the cap is 2)", str(len(provider.calls)))]

    out += ["", "4  a test file that cannot even be imported goes to the test engineer, not the backend developer"]
    result, provider, *_ = await story(workdir, "four", GOOD, BROKEN_TESTS, [reply(TESTS, "TSF")])
    out += [line("  who was asked", provider.calls[0].request.role), line("  result", describe(result))]

    out += ["", "5  the run's budget is spent after the first fix"]
    result, provider, *_ = await story(workdir, "five", WRONG, TESTS, [reply(GOOD, "BEF"), reply(GOOD, "BEF")], meter=Meter(max_cost_usd=0.001, max_seconds=0))
    out += [line("  result", describe(result)), line("  model calls", str(len(provider.calls)))]
    return out


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sdlc_fix_loop_demo_") as folder:
        print("\n".join(asyncio.run(demo(Path(folder)))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
