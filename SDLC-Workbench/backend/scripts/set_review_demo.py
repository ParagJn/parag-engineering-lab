"""Show the review of a Build instruction set, file by file, offline and free: a scripted writer, a scripted reviewer, the real checks. No model is called.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.set_review_demo

Everything runs in a temporary folder that is deleted afterwards. Four reviews of a small room-booking set:
  1 a clean set: one small call per file (the design index is the system's own and is not sent), nothing to report
  2 a set where one file drifts from the interface contract: the SYSTEM finds it (no model call for that), the reviewer finds something else, both appear in one review
  3 a reviewer reply that names a line that does not exist: sent back for that one file only, then accepted
  4 one file's review is cut off by the output limit every time: nothing is stored, the file is named and the setting to raise is named

The reviewer here is a script, so this shows the SYSTEM's behaviour (the calls, the targets, the merge, the all-or-nothing store). It cannot tell you how a real reviewer reads these files.
"""
from __future__ import annotations

import asyncio
import itertools
import tempfile
from pathlib import Path

from app.agents.runtime import AgentRuntime
from app.agents.skills import SkillLibrary
from app.build import compose as C
from app.build import instructions as I
from app.config import Settings
from app.llm.gateway import Gateway
from app.llm.providers.mock import MockCall, MockProvider
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.repos import Store
from app.review.errors import ReviewOutputInvalid
from app.review.prompt import load_rubric
from app.review.service import ReviewService
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine
from scripts.instructions_demo import DESIGN, MODELS, NAMES, Scripted, USE_CASES

FOUNDATION, ACCEPT = I.FOUNDATION_NAME, I.ACCEPTANCE_NAME
CLEAN = "<review>\nSummary: Nothing wrong in this file.\n</review>"


class Reviewer(MockProvider):
    """Answers a review request by the file named in its task line, from a per-file script, else with a clean review."""

    def __init__(self):
        super().__init__()
        self.script: dict[str, list] = {}
        self.asked: list[str] = []

    async def complete(self, model_id, request):
        name = request.messages[0].content.split("Review the file `", 1)[1].split("`", 1)[0]
        self.asked.append(name)
        self.calls.append(MockCall(model_id, request))
        queued = self.script.get(name)
        if queued:
            outcome = queued.pop(0)
            return outcome if isinstance(outcome, ProviderResponse) else ProviderResponse(outcome, Usage(9000, 400), "stop")
        return ProviderResponse(CLEAN, Usage(9000, 300), "stop")


def line(label: str, what: str) -> str:
    return f"  {label:<44} {what}"


async def story(workdir: Path, title: str, setup=None, drift=False, **settings):
    cfg = Settings(_env_file=None, data_dir=str(workdir / title.split()[0]), recordings_dir=str(workdir / "rec"), llm_retry_backoff_seconds=0, **{**MODELS, **settings})
    store = Store.open(workdir / f"{title.split()[0]}.db")
    routing = Routing.load()
    catalogue = load_catalogue(routing.roles.keys())
    ids = itertools.count(1)
    writer = Scripted()
    gateway = Gateway(cfg, routing, writer, store, call_id_factory=lambda: f"w{next(ids)}")
    engine = WorkflowEngine(catalogue, store)
    library = SkillLibrary.load(catalogue)
    runtime = AgentRuntime(cfg, store, gateway, catalogue, engine, library)
    project = store.projects.create(name="Room Booking", brief="A small room booking service.", actor="system")
    engine.open_project(project.id)
    store.phases.ensure(project.id, "build", actor="system")
    store.phases.set_status(project.id, "build", "running", actor="system")
    for key, text in DESIGN.items():
        skill = library.get(key)
        store.artefacts.create_and_add_version(project.id, artefact_type=key, phase_key=skill.artefact.phase_key, title=skill.artefact.name, prefix=skill.artefact.id_prefix, body=text, author="human:seed")
    await C.SetComposer(runtime, cfg, library).compose(project.id)
    art = store.artefacts.list(project.id, phase_key="build", artefact_type="build_instructions")[0].id
    if drift:
        body = store.artefacts.get_version(project.id, art).body
        store.artefacts.add_version(project.id, art, body=body.replace("Needs TBL-001.", "Needs TBL-001. Input: `begin`. Errors: 418.", 1), author="human:ann")
    reviewer = Reviewer()
    if setup:
        setup(reviewer)
    rids = itertools.count(1)
    service = ReviewService(cfg, store, Gateway(cfg, routing, reviewer, store, call_id_factory=lambda: f"r{next(rids)}"), runtime, engine, load_rubric())
    try:
        result = await service.review(project.id, art)
        error = None
    except ReviewOutputInvalid as exc:
        result, error = None, exc
    stored = store.artefacts.get_version(project.id, art).review_findings
    return result, error, reviewer, stored


def show(result, error, reviewer, stored) -> None:
    print(line("files sent to the reviewer", f"{len(reviewer.asked)}: {', '.join(reviewer.asked)}"))
    if error is not None:
        print(line("the review", "FAILED"))
        print(line("why", str(error)[:230]))
        print(line("stored", "NOTHING (all or nothing)" if stored is None else "something?!"))
        return
    print(line("verdict / calls / cost", f"{result.verdict} / {result.attempts} / ${result.cost_usd:.4f}"))
    print(line("summary", result.summary))
    for f in result.findings:
        who = "system  " if f.source == "system" else "reviewer"
        print(line(f"  [{f.severity.upper():<6}] {who}", f"{f.target}: {f.problem[:110]}"))
    print(line("stored", f"one review on the version, {len(stored['findings'])} findings, {stored['attempts']} calls, {len(stored['repair_reasons'])} corrections"))


async def main() -> None:
    with tempfile.TemporaryDirectory(prefix="sdlc_set_review_demo_") as tmp:
        work = Path(tmp)
        print("1  a clean set")
        show(*await story(work, "one clean"))

        print("\n2  one file drifts from the interface contract")
        uc2 = NAMES["UC-002"]

        def reviewer_finds(r):
            r.script[uc2] = ["<review>\nSummary: One thing to check.\n- [MEDIUM] " + uc2 + ":6: the screen is not named. Fix: name HFS-001.\n</review>"]
        show(*await story(work, "two drift", reviewer_finds, drift=True))

        print("\n3  a reviewer names a line that does not exist")

        def bad_line(r):
            r.script[NAMES["UC-001"]] = ["<review>\nSummary: x.\n- [LOW] " + NAMES["UC-001"] + ":999: nope. Fix: y.\n</review>", "<review>\nSummary: x.\n- [LOW] " + NAMES["UC-001"] + ":3: ok. Fix: y.\n</review>"]
        show(*await story(work, "three line", bad_line))

        print("\n4  one file's review is cut off every time")

        def cut(r):
            cutoff = ProviderResponse("<review>\nSummary: partly", Usage(9000, 12000), "length")
            r.script[NAMES["UC-002"]] = [cutoff, cutoff]
        show(*await story(work, "four cut", cut))

    print("\nA temporary folder held everything; it is gone. Nothing real was touched, and no model was called.")


if __name__ == "__main__":
    asyncio.run(main())
