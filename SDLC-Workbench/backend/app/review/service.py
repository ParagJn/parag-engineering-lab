"""Reviewing an artefact: one review per call, stored on the version it read.

Sonnet reviews by default (routing.yaml). The gateway labels every review `independent`, `same_family` or
`unverified`, and when the reviewer cannot run it raises ReviewerUnavailable with the other families to choose
from. This module never chooses for the person: it passes that error up, and a later call carries their choice.
"""
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from ..agents.items import parse_items
from ..agents.reply import ReplyFormatError, cited_ids, section_names
from ..agents.runtime import AgentRuntime, logged_problems, sum_costs
from ..agents.prompt import echo_for_repair
from ..config import Settings
from ..llm.errors import ReviewerUnavailable
from ..llm.gateway import Gateway
from ..llm.types import LLMRequest, LLMResult, Message
from ..models import ArtefactVersion, NotFoundError
from ..repos import Store
from ..workflow.engine import WorkflowEngine
from .errors import NothingToReview, ReviewOutputInvalid, WrongPhaseState
from .prompt import CitedSource, Rubric, build_review_prompt, repair_message, select_cited
from .reply import Finding, ParsedReview, parse_review, validate_review, verdict_of
from ..agents.reply import MAX_PROBLEMS

REVIEW_ROLE = "security_reviewer"  # routing.yaml sends this role to the reviewer slot; see Gateway.review
REVIEWABLE_PHASE_STATES = ("running", "awaiting_review")
HUMAN = "human"
_AUTHOR = re.compile(r"agent:[^@\s]+@(?P<model>\S+)")


@dataclass(frozen=True)
class ReviewResult:
    artefact_id: str
    version: int
    verdict: str
    summary: str
    findings: tuple[Finding, ...]
    independence: dict
    cost_usd: float | None
    attempts: int
    tokens_in: int = 0
    tokens_out: int = 0


@dataclass(frozen=True)
class PausedReview:
    """The reviewer could not run for this artefact. The person picks one of `options` and the review is run again."""
    artefact_id: str
    error: ReviewerUnavailable

    @property
    def options(self):
        return self.error.options


@dataclass(frozen=True)
class ReviewStatus:
    artefact_id: str
    state: str  # "unreviewed" | "reviewed" | "stale"
    verdict: str | None = None
    reviewed_version: int | None = None
    latest_version: int | None = None
    high_findings: int = 0


def author_model_of(version: ArtefactVersion) -> str | None:
    """The model that wrote a version, or None when a person did."""
    match = _AUTHOR.fullmatch(version.author)
    return match.group("model") if match else None


class ReviewService:
    def __init__(
        self, settings: Settings, store: Store, gateway: Gateway, runtime: AgentRuntime, engine: WorkflowEngine, rubric: Rubric
    ):
        self.settings = settings
        self.store = store
        self.gateway = gateway
        self.runtime = runtime
        self.engine = engine
        self.rubric = rubric

    # ---- reviewing one artefact -----------------------------------------------------------------------

    async def review(
        self, project_id: str, artefact_id: str, *, slot: str | None = None, exclude: Iterable[str] = (),
        run_id: str | None = None, actor: str = "system",
    ) -> ReviewResult:
        """Review the latest version of an artefact and store the findings on it.

        Raises ReviewerUnavailable (with the options) if the reviewer cannot run; nothing is stored then. Pass the
        person's choice back as `slot`, and the slots that already failed as `exclude`.
        """
        prepared = await asyncio.to_thread(self._prepare, project_id, artefact_id)
        version, prompt, author_model = prepared

        messages = [Message("user", prompt.user)]
        calls: list[LLMResult] = []
        repair_log: list[dict] = []
        independence = None
        problems: list[str] = []
        parsed: ParsedReview | None = None
        max_attempts = self.settings.review_max_repairs + 1
        for attempt in range(1, max_attempts + 1):
            outcome = await self.gateway.review(
                LLMRequest(
                    role=REVIEW_ROLE, messages=tuple(messages), system=prompt.system,
                    max_tokens=self.settings.review_max_output_tokens, temperature=self.settings.agent_temperature,
                    project_id=project_id, phase_key=self._phase_of(project_id, artefact_id), run_id=run_id,
                ),
                author_model=author_model, slot=slot, exclude=exclude,
            )
            calls.append(outcome.result)
            independence = outcome.independence
            parsed, problems = self._check(outcome.result, prompt)
            if problems:
                repair_log.append(logged_problems(attempt, outcome.result.call_id, problems))
            if not problems:
                break
            if attempt < max_attempts:
                messages += [Message("assistant", echo_for_repair(outcome.result.text)), Message("user", repair_message(problems))]
        else:
            raise ReviewOutputInvalid(
                f"the review of {artefact_id} could not be produced: after {max_attempts} attempt(s) the reply still failed "
                f"its checks ({'; '.join(problems)}). Nothing was stored.", problems, max_attempts,
            )
        assert parsed is not None and independence is not None
        return await asyncio.to_thread(
            self._store, project_id, artefact_id, version, parsed, independence, calls, actor, author_model, repair_log
        )

    # ---- everything the reviewer is shown ----------------------------------------------------------------

    def _phase_of(self, project_id: str, artefact_id: str) -> str:
        return self.store.artefacts.get(project_id, artefact_id).phase_key

    def _prepare(self, project_id: str, artefact_id: str):
        artefact = self.store.artefacts.get(project_id, artefact_id)
        if artefact.latest_version is None:
            raise NothingToReview(f"{artefact_id} has no version yet, so there is nothing to review")
        skill = self.runtime.skills.get(artefact.type)
        if skill is None:
            raise NothingToReview(f"there is no skill for '{artefact.type}', so its quality bar is unknown and it cannot be reviewed yet")
        try:
            status = self.store.phases.get(project_id, artefact.phase_key).status
        except NotFoundError:
            status = "not_started"
        if status not in REVIEWABLE_PHASE_STATES:
            raise WrongPhaseState(f"{artefact_id} can be reviewed while its phase is running or awaiting review; {artefact.phase_key} is '{status}'")

        version = self.store.artefacts.get_version(project_id, artefact_id)
        project = self.store.projects.get(project_id)
        upstream, _ = self.runtime.inputs_for(project_id, skill)
        total = sum(len(u.text) for u in upstream)
        if total > self.settings.agent_upstream_max_chars:
            biggest = sorted(upstream, key=lambda u: -len(u.text))
            names = ", ".join(f"{u.title} ({len(u.text)} characters)" for u in biggest[:3])
            raise NothingToReview(
                f"the artefacts '{skill.artefact.name}' builds on total {total} characters, over the "
                f"{self.settings.agent_upstream_max_chars} limit; the largest are {names}. Nothing is cut silently"
            )
        shown_in_full = {u.artefact_id for u in upstream}
        cited, omitted = select_cited(
            [self._resolve(project_id, c) for c in cited_ids(version.body) if c not in shown_in_full],
            self.settings.review_cited_max_chars,
        )
        prompt = build_review_prompt(
            skill, rubric=self.rubric, artefact_id=artefact_id, version=version.number, body=version.body,
            item_ids=parse_items(version.body, skill.items).ids, sections=section_names(version.body),
            upstream=upstream, cited=cited, omitted=omitted, brief=project.brief,
        )
        author_model = author_model_of(version) or HUMAN
        return version, prompt, author_model

    def _resolve(self, project_id: str, citation: str):
        """A cited source as a CitedSource, or (id, None) when it cannot be shown.

        A document, memory or approved-artefact chunk is looked up by ID in this project only. (A whole upstream
        artefact is cited by its artefact ID; those are already shown in full, so the caller leaves them out.)
        """
        hit = self.store.context.resolve(project_id, citation)
        if hit is None:
            return (citation, None)
        return CitedSource(citation, hit.title, hit.text)

    # ---- checking and storing ---------------------------------------------------------------------------------

    def _check(self, result: LLMResult, prompt) -> tuple[ParsedReview | None, list[str]]:
        try:
            parsed = parse_review(result.text)
        except ReplyFormatError as exc:
            return None, [str(exc)]
        problems = validate_review(
            parsed, item_ids=prompt.item_ids, sections=prompt.sections,
            max_findings=self.settings.review_max_findings, finish_reason=result.finish_reason,
        )
        # A review is stored for good and quotes from the artefact and its sources, so a secret in it is sent back too.
        text = "\n".join([parsed.summary, *(f"{f.target} {f.problem} {f.fix}" for f in parsed.findings)])
        problems = (self.runtime.scanner.problems(text) + problems)[:MAX_PROBLEMS]
        return (None if problems else parsed), problems

    def _store(
        self, project_id: str, artefact_id: str, reviewed: ArtefactVersion, parsed: ParsedReview, independence, calls: Sequence[LLMResult],
        actor: str, author_model: str, repair_log: Sequence[dict] = (),
    ) -> ReviewResult:
        final = calls[-1]
        cost = sum_costs([c.cost_usd for c in calls])
        author_family = "human" if author_model == HUMAN else independence.author_family
        label = "independent" if author_model == HUMAN else independence.verdict
        record = {
            "version_reviewed": reviewed.number,
            "verdict": verdict_of(parsed.findings),
            "summary": parsed.summary,
            "findings": [f.as_dict() for f in parsed.findings],
            "reviewer": {"slot": final.slot, "model": final.served_model, "family": final.family},
            "independence": {
                "verdict": label, "author_family": author_family,
                "reviewer_family": independence.reviewer_family, "fell_back": independence.fell_back,
            },
            "tokens_in": sum(c.tokens_in for c in calls), "tokens_out": sum(c.tokens_out for c in calls),
            "cost_usd": cost, "call_ids": [c.call_id for c in calls], "attempts": len(calls),
            "repair_reasons": list(repair_log),
        }
        self.store.artefacts.set_review_findings(project_id, artefact_id, reviewed.number, record, actor=actor)
        return ReviewResult(
            artefact_id, reviewed.number, record["verdict"], parsed.summary, parsed.findings, record["independence"],
            cost, len(calls), record["tokens_in"], record["tokens_out"],
        )

    # ---- a whole phase --------------------------------------------------------------------------------------------

    async def review_phase(
        self, project_id: str, phase_key: str, *, slot: str | None = None, run_id: str | None = None, actor: str = "system"
    ) -> list[ReviewResult | PausedReview]:
        """Review every artefact in a phase that has a version, one after another.

        A reviewer that cannot run pauses only the artefact it failed on, and the rest are still tried with the
        same slot. Nothing is switched without a person's choice, so a paused artefact is reported with its options.
        """
        out: list[ReviewResult | PausedReview] = []
        for artefact in self.store.artefacts.list(project_id, phase_key=phase_key):
            if artefact.latest_version is None:
                continue
            try:
                out.append(await self.review(project_id, artefact.id, slot=slot, run_id=run_id, actor=actor))
            except ReviewerUnavailable as exc:
                out.append(PausedReview(artefact.id, exc))
        return out

    # ---- where an artefact's review stands -------------------------------------------------------------------------------

    def status_of(self, project_id: str, artefact_id: str) -> ReviewStatus:
        artefact = self.store.artefacts.get(project_id, artefact_id)
        latest = artefact.latest_version
        if latest is None:
            return ReviewStatus(artefact_id, "unreviewed", latest_version=None)
        for version in reversed(self.store.artefacts.versions(project_id, artefact_id)):
            record = version.review_findings
            if isinstance(record, dict) and "verdict" in record:
                highs = sum(1 for f in record.get("findings", []) if f.get("severity") == "high")
                state = "reviewed" if version.number == latest else "stale"
                return ReviewStatus(artefact_id, state, record["verdict"], version.number, latest, highs)
        return ReviewStatus(artefact_id, "unreviewed", None, None, latest)

    def phase_status(self, project_id: str, phase_key: str) -> list[ReviewStatus]:
        return [self.status_of(project_id, a.id) for a in self.store.artefacts.list(project_id, phase_key=phase_key)]
