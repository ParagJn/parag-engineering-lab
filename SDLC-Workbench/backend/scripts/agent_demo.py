"""Watch the agent runtime work, offline, and (optionally) try it once against a real model.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.agent_demo          # offline, free
    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.agent_demo --live   # ONE real call

OFFLINE MODE USES A SCRIPTED FAKE MODEL, NOT A REAL ONE. Its replies are written into this file, and one of
them is deliberately wrong (it cites a source that was never provided) so you can see the runtime catch it,
send it back, and save only the corrected version. Nothing here says anything about how well a real model
writes. That is what --live is for.

--live runs ONE artefact (the project charter, on the Sonnet slot) through IBM ICA from the sample brief
below. It costs a fraction of a cent. It needs your key, so you run it; it never prints the key, the
endpoint or the user-agent.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from app.agents.errors import AgentError
from app.agents.runtime import AgentResult, AgentRuntime
from app.agents.skills import SkillLibrary
from app.config import Settings, get_settings
from app.llm.errors import LLMError
from app.llm.gateway import Gateway
from app.llm.providers.ica import IcaConfigError, IcaProvider
from app.llm.providers.mock import MockProvider
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.repos import Store
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine

PERSON = "human:demo"
BANNER = (
    "*** SCRIPTED FAKE MODEL. The replies below were written in advance inside scripts/agent_demo.py. ***\n"
    "*** This shows the runtime's checking and repairing, NOT how a real model writes. Use --live for that. ***"
)

from app.sample import BRIEF, FILENAME, NAME, POLICY  # noqa: E402  (one copy; the recordings depend on every word)

MODELS = dict(
    ibm_ica_model_id="demo-model", ibm_ica_fallback_model_id="demo-model",
    ibm_ica_price_input_per_mtok="2", ibm_ica_price_output_per_mtok="10",
)


def block(sections: dict[str, str]) -> str:
    body = "\n".join(f"## {name}\n{text}" for name, text in sections.items())
    return f"<artefact>\n{body}\n</artefact>"


# The scripted replies, in the order the runtime will ask for them.
CHARTER = block({
    "Purpose": "Let office staff find, reserve and cancel meeting rooms without double bookings [DOC-001#1].",
    "Scope": "Browsing rooms, reserving a slot, cancelling a reservation, and room administration.",
    "Out of scope": "Reporting, calendar integration and mobile apps.",
    "Stakeholders": "Office staff; the administrator who manages rooms.",
    "Success measures": "No room is ever booked twice for the same slot.",
    "Constraints and assumptions": "Office hours are eight to six on weekdays. Assumption: floors two to four only.",
    "Open questions": "What happens to a booking when a room is retired?",
})
PROBLEM = block({
    "The problem": "Staff cannot tell which rooms are free, so people double-book or give up.",
    "Who is affected": "Office staff on floors two to four.",
    "Impact today": "Time is lost finding a room and meetings collide. No figures were provided.",
    "Why it matters now": "Not stated in the sources.",
    "Evidence and assumptions": "Assumption: double bookings happen today. The charter [SET-CHR-001] states the goal.",
})
PERSONAS_BAD = block({  # cites an ID that was never provided: the runtime must refuse this
    "Overview": "Two personas follow.",
    "Personas": ("- PER-001 Office staff member, who wants a free room quickly [DOC-777#1]. Derives from: SET-CHR-001\n"
                 "- PER-002 Room administrator, who keeps the list correct. Derives from: SET-CHR-001"),
    "How the personas differ": "Staff book; the administrator maintains.",
    "Open questions": "How many rooms are there?",
})
PERSONAS_GOOD = block({
    "Overview": "Two personas follow, taken from the charter [SET-CHR-001].",
    "Personas": ("- PER-001 Office staff member, who wants a free room quickly. Derives from: SET-CHR-001\n"
                 "- PER-002 Room administrator, who keeps the list correct. Derives from: SET-CHR-001"),
    "How the personas differ": "Staff book; the administrator maintains.",
    "Open questions": "How many rooms are there?",
})
FUNCTIONAL = block({
    "Overview": "These requirements cover booking, cancelling and room administration.",
    "Requirements": ("- FR-001 The system shall refuse a booking for a slot that is already taken, for PER-001. Derives from: PER-001, REQ-PRB-001\n"
                     "- FR-002 The system shall let a room administrator add, rename and retire rooms. Derives from: PER-002, SET-CHR-001"),
    "Business rules": "Bookings last up to four hours and only within office hours [DOC-001#1].",
    "Traceability notes": "Derived from the charter [SET-CHR-001], the personas [REQ-PER-001] and the problem [REQ-PRB-001].",
    "Open questions": "Is there a limit on how far ahead a room can be booked?",
})


@dataclass(frozen=True)
class Step:
    label: str
    result: AgentResult | None
    note: str


@dataclass(frozen=True)
class Outcome:
    steps: list[Step]
    invented_caught: bool
    saved: int


def demo_settings(workdir: Path) -> Settings:
    return Settings(_env_file=None, data_dir=str(workdir / "data"), recordings_dir=str(workdir / "rec"), **MODELS)


def money(cost: float | None) -> str:
    return "unknown" if cost is None else f"${cost:.5f}"


def describe(result: AgentResult) -> str:
    return (f"{result.artefact_id} v{result.version}, {result.attempts} attempt(s), "
            f"{result.tokens_in} in / {result.tokens_out} out, cost {money(result.cost_usd)}, "
            f"cited {list(result.citations) or 'nothing'}")


def build(workdir: Path, settings: Settings, provider) -> tuple[Store, AgentRuntime, WorkflowEngine, str, MockProvider | None]:
    store = Store.open(workdir / "demo.db", limits=settings.context_limits)
    routing = Routing.load()
    catalogue = load_catalogue(routing.roles.keys())
    engine = WorkflowEngine(catalogue, store)
    runtime = AgentRuntime(settings, store, Gateway(settings, routing, provider, store), catalogue, engine, SkillLibrary.load(catalogue))
    project = store.projects.create(name=NAME, brief=BRIEF, actor="system")
    engine.open_project(project.id)
    store.context.add_document(project.id, FILENAME, POLICY, actor=PERSON)
    return store, runtime, engine, project.id, provider if isinstance(provider, MockProvider) else None


async def run_offline(workdir: Path) -> Outcome:
    settings = demo_settings(workdir)
    provider = MockProvider()
    store, runtime, engine, pid, _ = build(workdir, settings, provider)
    for text in (CHARTER, PROBLEM, PERSONAS_BAD, PERSONAS_GOOD, FUNCTIONAL):
        provider.queue("demo-model", ProviderResponse(text, Usage(1800, 420), "stop"))

    steps: list[Step] = []
    engine.start(pid, "setup", actor="system")
    steps.append(Step("Project charter", await runtime.run(pid, "project_charter"), "grounded in the policy note"))
    engine.finish(pid, "setup", actor="system")
    engine.approve(pid, "setup", actor=PERSON)
    engine.start(pid, "requirements", actor="system")

    steps.append(Step("Problem statement", await runtime.run(pid, "problem_statement"), "builds on the charter, shown in full"))
    personas = await runtime.run(pid, "personas")
    # The note describes what HAPPENED, not what the script expects: if the check fails to fire, it says so.
    steps.append(Step("Personas", personas, (
        "first reply cited a source that was never provided; it was refused and a corrected reply was saved"
        if personas.attempts == 2 and "DOC-777#1" not in personas.citations
        else "the reply citing a source that was never provided was SAVED, because the check did not fire"
    )))
    steps.append(Step("Functional requirements", await runtime.run(pid, "functional_requirements"), "sees the charter, personas and problem in full"))

    invented = any("DOC-777#1" in c.request.messages[-1].content for c in provider.calls)
    saved_bodies = " ".join(store.artefacts.get_version(pid, a.id).body for a in store.artefacts.list(pid))
    return Outcome(steps, invented and "DOC-777" not in saved_bodies and personas.attempts == 2, len(store.artefacts.list(pid)))


def render_offline(outcome: Outcome) -> str:
    lines = [BANNER, ""]
    for step in outcome.steps:
        assert step.result is not None
        lines.append(f"{step.label}: {describe(step.result)}")
        lines.append(f"    {step.note}")
    lines += ["", f"{outcome.saved}/4 artefacts saved, "
              f"{'1 invented citation caught and repaired' if outcome.invented_caught else 'the invented citation was NOT caught'}"]
    return "\n".join(lines)


async def run_live(settings: Settings, workdir: Path) -> tuple[AgentResult, str]:
    provider = IcaProvider(settings)
    try:
        store, runtime, engine, pid, _ = build(workdir, settings, provider)
        engine.start(pid, "setup", actor="system")
        result = await runtime.run(pid, "project_charter")
        return result, store.artefacts.get_version(pid, result.artefact_id).body
    finally:
        await provider.aclose()


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="run ONE real artefact through ICA (costs a fraction of a cent)")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="sdlc_agent_demo_") as tmp:
        workdir = Path(tmp)
        if not args.live:
            outcome = asyncio.run(run_offline(workdir))
            print(render_offline(outcome))
            return 0 if outcome.invented_caught and outcome.saved == 4 else 1

        cfg = settings or get_settings()
        missing = [name for name, ok in (("IBM_ICA_ENDPOINT", cfg.endpoint_set), ("IBM_ICA_API_KEY", cfg.api_key_set)) if not ok]
        if missing:
            print(f"Cannot run live: {', '.join(missing)} not set in backend/.env", file=sys.stderr)
            return 2
        try:
            result, body = asyncio.run(run_live(cfg, workdir))
        except (AgentError, LLMError, IcaConfigError) as exc:
            print(f"The real-model run failed: {exc}", file=sys.stderr)
            return 1
        print("REAL MODEL via IBM ICA (one call, project charter)\n")
        print(describe(result))
        print(f"written by: {result.author}")
        print("\n" + "-" * 70 + "\n" + body + "\n" + "-" * 70)
        print("\nWhat to look for: attempts = 1 means the model followed the reply format first time. "
              "Check the charter reads sensibly and that anything it cites really is in the policy note [DOC-001#n].")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
