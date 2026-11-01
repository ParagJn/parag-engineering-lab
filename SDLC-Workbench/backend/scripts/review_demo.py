"""Watch a review, a targeted rejection, a hand edit and an approval work, offline, and try a review once for real.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.review_demo                       # offline, free
    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.review_demo --live                # REAL calls
    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.review_demo --live --second openai

OFFLINE MODE USES A SCRIPTED FAKE MODEL, NOT A REAL ONE. The replies, including the reviewer's findings, are written
into this file. It shows the machinery (labels, the family picker, targeted rewriting, refused edits, the approval
record), not how well a real reviewer reads. That is what --live is for.

--live writes one project charter with a real model, has Sonnet review it, and optionally has a second family you name
(--second openai|gemini|haiku) review the same version too, so you see how the independence label differs. It is
2 or 3 real calls and costs cents. It prints the findings and the label, never a key, the endpoint or the user-agent.
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
from app.agents.runtime import AgentRuntime
from app.agents.skills import SkillLibrary
from app.config import Settings, get_settings
from app.llm.errors import ContentFilterBlocked, LLMError, ReviewerUnavailable
from app.llm.gateway import Gateway
from app.llm.providers.ica import IcaConfigError, IcaProvider
from app.llm.providers.mock import MockProvider
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.models import InvalidInput
from app.repos import Store
from app.review.errors import EditRefused, ReviewError
from app.review.human import HumanActions
from app.review.prompt import load_rubric
from app.review.service import ReviewService
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine

from app.sample import FILENAME, NAME
from .agent_demo import BRIEF, CHARTER, POLICY, block, money
from .requirements_demo import FUNCTIONAL, PERSONAS, PROBLEM

PERSON = "human:demo"
BANNER = (
    "*** SCRIPTED FAKE MODEL. Every reply below, including the reviewer's findings, was written in advance inside scripts/review_demo.py. ***\n"
    "*** This shows the review machinery, NOT how a real reviewer reads. Use --live for that. ***"
)
MODELS = dict(
    ibm_ica_model_id="demo-sonnet", ibm_ica_fallback_model_id="demo-sonnet",
    ibm_ica_haiku_model_id="claude-demo-haiku", ibm_ica_haiku_fallback_model_id="demo-sonnet",
    ibm_ica_openai_model_id="gpt-demo", ibm_ica_openai_fallback_model_id="demo-sonnet",
    ibm_ica_gemini_model_id="gemini-demo", ibm_ica_gemini_fallback_model_id="demo-sonnet",
    ibm_ica_price_input_per_mtok="2", ibm_ica_price_output_per_mtok="10",
    ibm_ica_openai_price_input_per_mtok="2", ibm_ica_openai_price_output_per_mtok="10",
    ibm_ica_gemini_price_input_per_mtok="0.75", ibm_ica_gemini_price_output_per_mtok="3.75",
)

REVIEW_PERSONAS = ("<review>\nSummary: The personas follow the charter. One persona states a frustration the sources do not give.\n"
                   "- [HIGH] PER-001: The frustration 'wants a free room quickly' is not in the charter or the policy. Fix: mark it as an assumption.\n"
                   "- [LOW] Open questions: one question could be answered from the charter. Fix: remove it.\n</review>")
REVIEW_FR = "<review>\nSummary: The requirements are consistent with the personas and the problem. Nothing is wrong.\n</review>"
REVIEW_CHARTER_OTHER_FAMILY = "<review>\nSummary: Reads clearly. No problems.\n</review>"
PERSONAS_V2 = block({
    "Overview": "Two personas follow, taken from the charter [SET-CHR-001].",
    "Personas": ("- PER-001 Office staff member. Assumption: they want a free room quickly. Derives from: SET-CHR-001\n"
                 "- PER-002 Room administrator, who keeps the list of rooms correct. Derives from: PER-001"),
    "How the personas differ": "Staff book and cancel; the administrator maintains the room list.",
    "Open questions": "How many rooms are there?",
})
EDIT = (
    "## Overview\nTwo personas follow, taken from the charter [SET-CHR-001].\n"
    "## Personas\n- PER-001 Office staff member. Assumption: they want a free room quickly. Derives from: SET-CHR-001\n"
    "- PER-002 Room administrator, who keeps the list of rooms correct, edited by a person. Derives from: SET-CHR-001\n"
    "## How the personas differ\nStaff book and cancel; the administrator maintains the room list.\n"
    "## Open questions\nHow many rooms are there?"
)
BAD_EDIT = EDIT.replace("PER-001 Office", "PER-007 Office").replace("SET-CHR-001\n- PER-002", "SET-CHR-999\n- PER-002")


@dataclass(frozen=True)
class Line:
    label: str
    text: str


def demo_settings(workdir: Path) -> Settings:
    return Settings(_env_file=None, data_dir=str(workdir / "data"), recordings_dir=str(workdir / "rec"), **MODELS)


def build(workdir: Path, settings: Settings, provider):
    store = Store.open(workdir / "demo.db", limits=settings.context_limits)
    routing = Routing.load()
    catalogue = load_catalogue(routing.roles.keys())
    engine = WorkflowEngine(catalogue, store)
    gateway = Gateway(settings, routing, provider, store)
    runtime = AgentRuntime(settings, store, gateway, catalogue, engine, SkillLibrary.load(catalogue))
    reviews = ReviewService(settings, store, gateway, runtime, engine, load_rubric())
    human = HumanActions(store, engine, runtime, reviews)
    project = store.projects.create(name=NAME, brief=BRIEF, actor="system")
    engine.open_project(project.id)
    store.context.add_document(project.id, FILENAME, POLICY, actor=PERSON)
    return store, runtime, reviews, human, engine, project.id


def label_of(result) -> str:
    i = result.independence
    return f"{i['verdict']} (author {i['author_family']}, reviewer {i['reviewer_family']})"


async def run_offline(workdir: Path) -> tuple[list[Line], bool]:
    settings = demo_settings(workdir)
    provider = MockProvider()
    store, runtime, reviews, human, engine, pid = build(workdir, settings, provider)
    ok = lambda text, tokens=(1800, 420): ProviderResponse(text, Usage(*tokens), "stop")  # noqa: E731
    lines: list[Line] = []
    checks: list[bool] = []

    def note(label: str, text: str, passed: bool = True) -> None:
        lines.append(Line(label, text))
        checks.append(passed)

    provider.queue("demo-sonnet", ok(CHARTER), ok(PERSONAS), ok(PROBLEM), ok(FUNCTIONAL))
    engine.start(pid, "setup", actor="system")
    await runtime.run(pid, "project_charter")
    engine.finish(pid, "setup", actor="system")
    engine.approve(pid, "setup", actor=PERSON)
    engine.start(pid, "requirements", actor="system")
    for key in ("personas", "problem_statement", "functional_requirements"):
        await runtime.run(pid, key)

    # 1. a review of Sonnet's own work: same family
    provider.queue("demo-sonnet", ok(REVIEW_PERSONAS, (2600, 180)))
    r1 = await reviews.review(pid, "REQ-PER-001")
    note("1. Sonnet reviews work written by Sonnet", f"{r1.verdict}, {len(r1.findings)} finding(s); label {label_of(r1)}",
         r1.independence["verdict"] == "same_family" and r1.verdict == "revise")

    # 2. the same, written by OpenAI: independent
    store.artefacts.create(pid, artefact_type="vision_objectives", phase_key="requirements", title="Vision and objectives", actor="system", prefix="REQ-VIS")
    store.artefacts.add_version(pid, "REQ-VIS-001", body="## Vision\nx\n## Objectives\n- OBJ-001 y. Derives from: REQ-PRB-001\n## Measures\nz\n## Out of vision\nw\n## Open questions\nv",
                                author="agent:requirements_analyst@gpt-demo")
    provider.queue("demo-sonnet", ok(REVIEW_FR, (2200, 90)))
    r2 = await reviews.review(pid, "REQ-VIS-001")
    note("2. Sonnet reviews work written by OpenAI", f"{r2.verdict}; label {label_of(r2)}", r2.independence["verdict"] == "independent")

    # 3. the reviewer cannot run: the person picks
    provider.queue("demo-sonnet", ContentFilterBlocked("blocked"))
    try:
        await reviews.review(pid, "REQ-F-001")
        note("3. The reviewer cannot run", "no pause happened", False)
    except ReviewerUnavailable as exc:
        options = ", ".join(f"{o.slot}{' (independent)' if o.independent else ''}" for o in exc.options)
        note("3. The reviewer cannot run", f"paused, nothing switched; you are offered: {options}", [o.slot for o in exc.options][0] == "gemini")
        provider.queue("gemini-demo", ok(REVIEW_CHARTER_OTHER_FAMILY, (2100, 40)))
        r3 = await reviews.review(pid, "REQ-F-001", slot="gemini", exclude=["sonnet"])
        note("   you pick Gemini", f"{r3.verdict}; label {label_of(r3)}", r3.independence["verdict"] == "independent")

    # 4. targeted rejection: only the personas are rewritten
    engine.finish(pid, "requirements", actor="system")
    human.request_changes(pid, "requirements", actor=PERSON, notes={"REQ-PER-001": "Mark the frustration as an assumption."})
    provider.queue("demo-sonnet", ok(PERSONAS_V2))
    calls_before = len(provider.calls)
    rerun = await human.rerun_rejected(pid, "requirements", actor=PERSON)
    only_one = list(rerun.rewritten) == ["REQ-PER-001"] and len(provider.calls) == calls_before + 1
    versions = {a.id: a.latest_version for a in store.artefacts.list(pid, phase_key="requirements")}
    note("4. You send the personas back", f"only {', '.join(rerun.rewritten)} rewritten (now v{versions['REQ-PER-001']}); "
         f"others unchanged: {', '.join(f'{k} v{v}' for k, v in versions.items() if k != 'REQ-PER-001')}", only_one)
    note("   what that makes out of date", f"built on the old personas, flagged but NOT re-run: {', '.join(rerun.stale_not_run) or 'none'}",
         rerun.stale_not_run == ("REQ-F-001",))
    removed = [e.target_id for e in store.audit.list(pid, action="link.removed")]
    now = sorted(f"{l.from_id}>{l.to_id}" for l in store.links.list(pid) if l.declared_in == "REQ-PER-001")
    note("   the links followed the new text", f"PER-002 now derives from PER-001; the link it had to the charter was removed and audited "
         f"({', '.join(removed) or 'nothing removed'}); links now: {', '.join(now)}",
         removed == ["PER-002>derives>SET-CHR-001"] and now == ["PER-001>SET-CHR-001", "PER-002>PER-001"])

    # 5. a hand edit that breaks the rules is refused; a good one is saved
    try:
        human.edit(pid, "REQ-PER-001", BAD_EDIT, actor=PERSON)
        note("5. A hand edit that breaks the rules", "it was SAVED, which is wrong", False)
    except EditRefused as exc:
        note("5. A hand edit that breaks the rules", f"refused with {len(exc.problems)} reason(s), nothing saved: {exc.problems[0]}", True)
    n = human.edit(pid, "REQ-PER-001", EDIT, actor=PERSON, note="added detail")
    version = store.artefacts.get_version(pid, "REQ-PER-001")
    note("   a valid hand edit", f"saved as v{n} by {version.author}; v{n - 1} kept", version.author == PERSON and n == 3)
    note("   its review", f"is now '{reviews.status_of(pid, 'REQ-PER-001').state}' (the review was of an older version)",
         reviews.status_of(pid, "REQ-PER-001").state == "stale")

    # 6. an agent cannot approve
    for who in ("agent:requirements_analyst@demo-sonnet", "system"):
        try:
            human.approve(pid, "requirements", actor=who)
            note("6. Approval", f"{who} was allowed to approve", False)
        except InvalidInput:  # PersonRequired from this layer, or the repository's own refusal of an agent
            pass
    note("6. An agent or the system tries to approve", "both refused: approval needs a person", True)

    return lines, all(checks)


async def run_live(settings: Settings, workdir: Path, second: str | None) -> list[str]:
    provider = IcaProvider(settings)
    out: list[str] = []
    try:
        store, runtime, reviews, human, engine, pid = build(workdir, settings, provider)
        engine.start(pid, "setup", actor="system")
        written = await runtime.run(pid, "project_charter")
        body = store.artefacts.get_version(pid, written.artefact_id).body
        out.append(f"Written by {written.author}: {written.artefact_id} v{written.version}, {written.attempts} attempt(s), cost {money(written.cost_usd)}")
        first = await reviews.review(pid, written.artefact_id)
        out.append(render_review("Reviewed by the Sonnet slot", first))
        if second:
            other = await reviews.review(pid, written.artefact_id, slot=second)
            out.append(render_review(f"Reviewed again by the {second} slot (replaces the first)", other))
        out.append(f"\nThe charter that was reviewed ({len(body)} characters) was written fresh for this run; it is not the one agent_demo --live printed earlier.")
    finally:
        await provider.aclose()
    return out


def render_review(heading: str, result) -> str:
    lines = [f"\n{heading}", f"  verdict: {result.verdict}   label: {label_of(result)}   cost {money(result.cost_usd)}   attempts {result.attempts}",
             f"  summary: {result.summary}"]
    for f in result.findings:
        lines.append(f"  - [{f.severity.upper()}] {f.target}: {f.problem}" + (f" Fix: {f.fix}" if f.fix else ""))
    if not result.findings:
        lines.append("  (no findings)")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live", action="store_true", help="write one charter and review it with real models (costs cents)")
    parser.add_argument("--second", choices=("openai", "gemini", "haiku"), help="with --live: review it a second time with this family")
    args = parser.parse_args(argv)
    if args.second and not args.live:
        parser.error("--second only makes sense with --live")

    with tempfile.TemporaryDirectory(prefix="sdlc_review_demo_") as tmp:
        workdir = Path(tmp)
        if not args.live:
            lines, passed = asyncio.run(run_offline(workdir))
            print(BANNER + "\n")
            for line in lines:
                print(f"{line.label}: {line.text}")
            print("\n" + ("everything behaved as specified" if passed else "SOMETHING DID NOT BEHAVE AS SPECIFIED, see above"))
            return 0 if passed else 1

        cfg = settings or get_settings()
        missing = [n for n, ok in (("IBM_ICA_ENDPOINT", cfg.endpoint_set), ("IBM_ICA_API_KEY", cfg.api_key_set)) if not ok]
        if missing:
            print(f"Cannot run live: {', '.join(missing)} not set in backend/.env", file=sys.stderr)
            return 2
        try:
            out = asyncio.run(run_live(cfg, workdir, args.second))
        except ReviewerUnavailable as exc:
            names = ", ".join(o.slot for o in exc.options)
            print(f"The reviewer slot '{exc.slot}' could not run. Nothing was switched. Choose a family and run again with --second: {names}", file=sys.stderr)
            return 1
        except (AgentError, ReviewError, LLMError, IcaConfigError) as exc:
            print(f"The real-model run failed: {exc}", file=sys.stderr)
            return 1
        print("REAL MODELS via IBM ICA\n")
        print("\n".join(out))
        print("\nWhat to look for: is each finding actually in the charter (quote a few words and check)? Does a [HIGH] finding "
              "deserve the name? Does the label match who wrote and who reviewed? Does the reviewer miss anything you can see?")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
