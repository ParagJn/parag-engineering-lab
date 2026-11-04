"""The agent runtime: one artefact, from skill and context to a validated, saved version.

No parallelism and no review here (S09 and S08). It runs one artefact, checks what comes back, asks for
a fix when the check fails, and saves only a reply that passed.
"""
from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass, replace
from typing import Awaitable, Callable, Mapping, Sequence

from ..config import Settings
from ..llm.gateway import Gateway
from ..llm.types import LLMRequest, LLMResult, Message
from ..models import NotFoundError, Project
from ..repos import Store
from ..workflow.definitions import Catalogue
from ..workflow.engine import WorkflowEngine
from .errors import (
    AgentError,
    RunStopped,
    ArtefactNotInPlan,
    InputTooLarge,
    MissingInput,
    NoSkill,
    OutputInvalid,
    PhaseNotRunning,
)
from ..guardrails.scan import Scanner
from .checks import check_body
from ..build.instructions import INSTRUCTIONS_KEY
from .items import Item, ItemContext, history_of, parse_items, upstream_pool
from .notes import unacted_notes
from .prompt import (
    Feedback,
    Prompt,
    Upstream,
    brief_queries,
    build_prompt,
    echo_for_repair,
    repair_message,
    select_hits,
)
from .reply import CUT_OFF_BEFORE_CLOSING, MAX_PROBLEMS, TRUNCATED_REASONS, ReplyFormatError, cited_ids, parse_reply
from .skills import Skill, SkillLibrary


@dataclass(frozen=True)
class AgentResult:
    artefact_id: str
    version: int
    author: str
    attempts: int
    tokens_in: int
    tokens_out: int
    cost_usd: float | None  # None when any attempt's cost is unknown; never a partial sum passed off as a total
    citations: tuple[str, ...]
    call_ids: tuple[str, ...]
    served_models: tuple[str, ...]
    created_artefact: bool
    items: tuple[str, ...] = ()  # item IDs the saved version holds
    links: int = 0  # derives-from links the save declared (repeats of an existing link included)
    flags: int = 0  # personal-data findings saved with the version (secrets never get this far)


MAX_LOGGED_PROBLEM_CHARS = 400   # a problem can quote a few words of the reply; the record stays bounded either way


def logged_problems(attempt: int, call_id: str, problems: Sequence[str]) -> dict:
    """One failed attempt as it is kept on the saved version: which attempt, which call, and what was wrong, in the words
    that were sent back to the model. Stored with the version (never published as an event)."""
    return {"attempt": attempt, "call_id": call_id, "problems": [p[:MAX_LOGGED_PROBLEM_CHARS] for p in problems]}


def sum_costs(costs: Sequence[float | None]) -> float | None:
    """A total is only a total if every part is known."""
    if not costs or any(c is None for c in costs):
        return None
    return sum(costs)  # type: ignore[arg-type]


class AgentRuntime:
    def __init__(
        self,
        settings: Settings,
        store: Store,
        gateway: Gateway,
        catalogue: Catalogue,
        engine: WorkflowEngine,
        skills: SkillLibrary,
    ):
        self.settings = settings
        self.store = store
        self.gateway = gateway
        self.catalogue = catalogue
        self.engine = engine
        self.skills = skills
        self.scanner = Scanner.from_settings(settings)

    # ---- the public entry point -------------------------------------------------------------

    async def run(
        self,
        project_id: str,
        artefact_key: str,
        *,
        feedback: Sequence[str] = (),
        previous_draft: str | None = None,
        run_id: str | None = None,
        overrides: Mapping[str, str] | None = None,
        on_call: Callable[[LLMResult, int, list[str]], str | None] | None = None,
        extra_check: Callable[[str], Awaitable[Sequence[str]]] | None = None,
    ) -> AgentResult:
        """Generate one artefact and save it as a new version. Raises (and saves nothing) on any failure.

        `on_call(result, attempt, problems)` is told after every model call, with the problems found in that
        reply. A phase run uses it to count cost as it happens. If it returns a reason ("budget", "time" or
        "cancelled") the artefact is dropped unsaved at once, so a repair loop cannot spend past a cap.

        `extra_check(body)` runs on a reply that passed every ordinary check, and returns more problems in plain sentences (or none). They are
        sent back exactly like any other problem, so what it finds is repaired in the same conversation and nothing bad is ever saved. A Build
        artefact uses it to really try its files (S17b). It is never called on a reply that already has problems, and None means no extra check."""
        if artefact_key == INSTRUCTIONS_KEY:
            # One reply cannot hold the whole set (the first live run wrote nothing at 8,000 tokens): it is written file by file by the Build phase run.
            raise AgentError("the Build instructions are written file by file when the Build phase is run; run the Build phase to write or rewrite them")
        project, skill = await asyncio.to_thread(self._check_runnable, project_id, artefact_key)
        prompt, item_ctx = await asyncio.to_thread(self._assemble, project, skill, feedback, previous_draft)
        calls, repair_log, body = await self.converse(
            project_id, skill, prompt, lambda result: self._check(result, skill, prompt, item_ctx, self.scanner),
            run_id=run_id, overrides=overrides, on_call=on_call, extra_check=extra_check,
        )
        return await asyncio.to_thread(self._save, project_id, skill, body, calls, prompt, run_id, item_ctx, repair_log)

    async def converse(
        self,
        project_id: str,
        skill: Skill,
        prompt: Prompt,
        check: Callable[[LLMResult], tuple[list[str], str]],
        *,
        run_id: str | None = None,
        overrides: Mapping[str, str] | None = None,
        on_call: Callable[[LLMResult, int, list[str]], str | None] | None = None,
        extra_check: Callable[[str], Awaitable[Sequence[str]]] | None = None,
        label: str | None = None,
    ) -> tuple[list[LLMResult], list[dict], str]:
        """The model conversation for ONE reply: call, check, send the problems back, up to the repair budget. Returns (the calls, what was wrong with each
        attempt that had to be repaired, the body of the accepted reply). Raises (and saves nothing) when no attempt is accepted.

        `check(result)` returns (problems, body). `label` names what is being written in the messages (default: the artefact's name); the Build instruction
        set writes one file per conversation and names the file."""
        what = label or skill.artefact.name
        calls: list[LLMResult] = []
        repair_log: list[dict] = []   # what was wrong with each attempt that had to be repaired, kept with the saved version
        messages = [Message("user", prompt.user)]
        problems: list[str] = []
        body = ""
        max_attempts = self.settings.agent_max_repairs + 1
        for attempt in range(1, max_attempts + 1):
            result = await self.gateway.complete(
                LLMRequest(
                    role=skill.artefact.role,
                    messages=tuple(messages),
                    system=prompt.system,
                    max_tokens=self.settings.output_tokens_for(skill.artefact.role),
                    temperature=self.settings.agent_temperature,
                    project_id=project_id,
                    phase_key=skill.artefact.phase_key,
                    run_id=run_id,
                ),
                overrides=overrides,
            )
            calls.append(result)
            problems, body = check(result)
            if not problems and extra_check is not None:
                problems = [str(p) for p in await extra_check(body)][:MAX_PROBLEMS]
            if problems:
                repair_log.append(logged_problems(attempt, result.call_id, problems))
            if on_call is not None:
                stop = on_call(result, attempt, problems)
                if stop is not None:
                    raise RunStopped(
                        f"'{what}' was dropped unsaved: the run was stopped ({stop}) after attempt {attempt}", stop,
                    )
            if not problems:
                break
            if attempt < max_attempts:
                messages += [Message("assistant", echo_for_repair(result.text)), Message("user", repair_message(problems))]
        else:
            raise OutputInvalid(
                f"'{what}' could not be produced: after {max_attempts} attempt(s) the reply still "
                f"failed its checks ({'; '.join(problems)}). Nothing was saved.",
                problems, max_attempts,
                cut_off=calls[-1].finish_reason in TRUNCATED_REASONS, limit=self.settings.output_tokens_for(skill.artefact.role),
            )
        return calls, repair_log, body

    def ensure_runnable(self, project_id: str, artefact_key: str) -> tuple[Project, Skill]:
        """Raise, in plain words, unless this artefact may be written now (known, has a skill, switched on, its phase running). Returns the project and skill."""
        return self._check_runnable(project_id, artefact_key)

    def save_composed(
        self, project_id: str, skill: Skill, body: str, calls: Sequence[LLMResult], upstream: Sequence[Upstream], run_id: str | None,
        item_ctx: ItemContext | None, repair_log: Sequence[dict], extra_generation: Mapping,
    ) -> AgentResult:
        """Save a body that was written in several conversations (the Build instruction set) as one version, through the same save path as every artefact."""
        prompt = Prompt(system="", user="", allowed=(), shown_chunks=(), built_on=tuple((u.artefact_id, u.version) for u in upstream))
        return self._save(project_id, skill, body, calls, prompt, run_id, item_ctx, repair_log, extra_generation)

    # ---- before any model call ------------------------------------------------------------------

    def _check_runnable(self, project_id: str, artefact_key: str) -> tuple[Project, Skill]:
        project = self.store.projects.get(project_id)  # NotFoundError for an unknown project
        known = any(a.key == artefact_key for phase in self.catalogue.phases for a in phase.artefacts)
        if not known:
            raise ArtefactNotInPlan(f"'{artefact_key}' is not an artefact in the workflow catalogue")
        skill = self.skills.get(artefact_key)
        if skill is None:
            raise NoSkill(f"there is no skill for '{artefact_key}' yet, so an agent cannot write it")
        plan = self.engine.plan_for(project)
        if not plan.phase(skill.artefact.phase_key).has(artefact_key):
            raise ArtefactNotInPlan(f"'{skill.artefact.name}' was switched off for this project")
        self._require_running(self.store.phases, project_id, skill)
        return project, skill

    @staticmethod
    def _require_running(phases, project_id: str, skill: Skill) -> None:
        try:
            status = phases.get(project_id, skill.artefact.phase_key).status
        except NotFoundError:
            status = "not_started"
        if status != "running":
            raise PhaseNotRunning(
                f"'{skill.artefact.name}' can only be written while its phase is running; "
                f"{skill.artefact.phase_key} is '{status}'"
            )

    # ---- gathering what the agent may use ---------------------------------------------------------------

    def _assemble(
        self, project: Project, skill: Skill, feedback: Sequence[str], previous_draft: str | None
    ) -> tuple[Prompt, ItemContext | None]:
        upstream = self._upstream(project.id, skill)
        self.check_upstream_size(skill, upstream)
        own = self._own_artefact_id(project.id, skill)
        hits = []
        queries = list(skill.searches) + brief_queries(project.brief, self.settings.agent_brief_queries)
        for query in queries:
            hits.extend(self.store.context.search(project.id, query, limit=10, kinds=["document", "artefact"]))
        chosen = select_hits(
            hits,
            max_chunks=self.settings.agent_context_max_chunks,
            max_chars=self.settings.agent_context_max_chars,
            min_coverage=self.settings.agent_context_min_coverage,
            exclude_artefacts=[u.artefact_id for u in upstream] + ([own] if own else []),
        )
        notes = [Feedback(text) for text in feedback if text and text.strip()]
        notes += self._memory_feedback(project.id, skill, own)
        item_ctx, upstream_items = self._item_context(project.id, skill, upstream, own)
        prompt = build_prompt(
            skill, project_name=project.name, brief=project.brief, upstream=upstream,
            feedback=notes, previous_draft=previous_draft, hits=chosen,
            item_context=item_ctx, upstream_items=upstream_items,
        )
        if item_ctx is not None:
            # "Derives from" may name anything the model was shown as a source, as well as upstream items.
            item_ctx = ItemContext(
                item_ctx.specs, item_ctx.covers, item_ctx.known | frozenset(prompt.allowed), item_ctx.pools,
                item_ctx.current, item_ctx.retired, item_ctx.highest, item_ctx.previous,
            )
        return prompt, item_ctx

    def check_upstream_size(self, skill: Skill, upstream: Sequence[Upstream]) -> None:
        """Refuse, in plain words, when the material a skill builds on is over the limit. Nothing is ever cut silently."""
        total = sum(len(u.text) for u in upstream)
        if total > self.settings.agent_upstream_max_chars:
            biggest = sorted(upstream, key=lambda u: -len(u.text))
            names = ", ".join(f"{u.title} ({len(u.text)} characters)" for u in biggest[:3])
            raise InputTooLarge(
                f"the artefacts '{skill.artefact.name}' builds on total {total} characters, over the "
                f"{self.settings.agent_upstream_max_chars} limit; the largest are {names}. Nothing is cut silently"
            )

    def _item_context(
        self, project_id: str, skill: Skill, upstream: Sequence[Upstream], own: str | None
    ) -> tuple[ItemContext | None, list[Item]]:
        """What the item checks need: upstream items, this artefact's earlier IDs, and the pools to cover."""
        if not skill.items:
            return None, []
        shown: list[Item] = []
        pairs = []
        for u in upstream:
            upstream_skill = self.skills.get(u.key)
            if upstream_skill is not None and upstream_skill.items:
                shown.extend(parse_items(u.text, upstream_skill.items).items)
                pairs.append((u.text, upstream_skill.items))
        earlier = [v.body for v in self.store.artefacts.versions(project_id, own)] if own else []
        history = history_of(earlier, skill.items)
        ctx = ItemContext(
            specs=skill.items, covers=skill.covers, known=frozenset(i.id for i in shown),
            pools=upstream_pool(pairs), current=history.current, retired=history.retired,
            highest=history.highest, previous=history.previous,
        )
        return ctx, shown

    def _own_artefact_id(self, project_id: str, skill: Skill) -> str | None:
        found = self.store.artefacts.list(project_id, phase_key=skill.artefact.phase_key, artefact_type=skill.key)
        return found[0].id if found else None

    def _upstream(self, project_id: str, skill: Skill) -> list[Upstream]:
        out: list[Upstream] = []
        for key in skill.upstream:
            phase_key = next(p.key for p in self.catalogue.phases for a in p.artefacts if a.key == key)
            found = self.store.artefacts.list(project_id, phase_key=phase_key, artefact_type=key)
            if not found or found[0].latest_version is None:
                name = next(a.name for p in self.catalogue.phases for a in p.artefacts if a.key == key)
                raise MissingInput(
                    f"'{skill.artefact.name}' builds on '{name}', which has not been written yet"
                )
            version = self.store.artefacts.get_version(project_id, found[0].id)
            out.append(Upstream(found[0].id, found[0].title, key, version.body, version.number))
        return out

    def inputs_for(self, project_id: str, skill: Skill) -> tuple[list[Upstream], ItemContext | None]:
        """The upstream artefacts a skill reads (in full, as the writer sees them) and the item rules for it.
        Used by the reviewer and by a person's edit, so both see exactly what the writer saw."""
        upstream = self._upstream(project_id, skill)
        item_ctx, _ = self._item_context(project_id, skill, upstream, self._own_artefact_id(project_id, skill))
        if item_ctx is not None:
            # The writer may derive from a whole upstream artefact as well as from its items (see _assemble).
            item_ctx = replace(item_ctx, known=item_ctx.known | frozenset(u.artefact_id for u in upstream))
        return upstream, item_ctx

    def _memory_feedback(self, project_id: str, skill: Skill, own: str | None) -> list[Feedback]:
        return [Feedback(e.text, f"MEM-{e.id:03d}") for e in unacted_notes(self.store, project_id, skill.artefact.phase_key, own)]

    # ---- checking a reply -----------------------------------------------------------------------------------

    @staticmethod
    def _check(result: LLMResult, skill: Skill, prompt: Prompt, item_ctx: ItemContext | None = None, scanner: Scanner | None = None) -> tuple[list[str], str]:
        try:
            body = parse_reply(result.text)
        except ReplyFormatError as exc:
            if result.finish_reason in TRUNCATED_REASONS:
                # The reply was cut off by the output limit BEFORE it could close its tag. "Never closed" is true but gives the model nothing to act
                # on; the cause is the length limit, and the fix is a shorter artefact. (Seen with Gemini: a reply that wrote 300 visible tokens was
                # cut off, because its hidden reasoning had used the rest of the limit.)
                return [CUT_OFF_BEFORE_CLOSING], ""
            return [str(exc)], ""
        return check_body(body, skill, prompt.allowed, item_ctx, result.finish_reason, scanner), body

    # ---- saving ---------------------------------------------------------------------------------------------------

    def _save(
        self, project_id: str, skill: Skill, body: str, calls: Sequence[LLMResult], prompt: Prompt, run_id: str | None,
        item_ctx: ItemContext | None = None, repair_log: Sequence[dict] = (), extra_generation: Mapping | None = None,
    ) -> AgentResult:
        final = calls[-1]
        author = f"agent:{skill.artefact.role}@{final.served_model}"
        citations = cited_ids(body)
        cost = sum_costs([c.cost_usd for c in calls])
        parsed = parse_items(body, skill.items)
        links = [(item.id, target, "derives") for item in parsed.items for target in item.link_targets]
        flags = [f.as_dict() for f in self.scanner.scan(body)]
        generation = {
            "guardrails": flags,
            "built_on": {artefact_id: number for artefact_id, number in prompt.built_on},
            "items": list(parsed.ids),
            "skill": skill.key,
            "run_id": run_id,
            "attempts": len(calls),
            "repairs": len(calls) - 1,
            "repair_reasons": list(repair_log),
            "tokens_in": sum(c.tokens_in for c in calls),
            "tokens_out": sum(c.tokens_out for c in calls),
            "cost_usd": cost,
            "calls": [
                {"call_id": c.call_id, "model": c.served_model, "slot": c.slot, "fallback_used": c.fallback_used,
                 "tokens_in": c.tokens_in, "tokens_out": c.tokens_out, "cost_usd": c.cost_usd}
                for c in calls
            ],
            **(extra_generation or {}),
        }

        def still_running(conn: sqlite3.Connection) -> None:
            row = conn.execute(
                "SELECT status FROM phase_runs WHERE project_id = ? AND phase_key = ?",
                (project_id, skill.artefact.phase_key),
            ).fetchone()
            status = row["status"] if row is not None else "not_started"
            if status != "running":
                raise PhaseNotRunning(
                    f"'{skill.artefact.name}' was not saved: its phase became '{status}' while the model was writing"
                )

        artefact, version = self.store.artefacts.create_and_add_version(
            project_id, artefact_type=skill.key, phase_key=skill.artefact.phase_key, title=skill.artefact.name,
            prefix=skill.artefact.id_prefix, body=body, author=author, source_chunks=citations,
            generation=generation, guard=still_running, links=links,
        )
        return AgentResult(
            artefact_id=artefact.id, version=version.number, author=author, attempts=len(calls),
            tokens_in=generation["tokens_in"], tokens_out=generation["tokens_out"], cost_usd=cost,
            citations=tuple(citations), call_ids=tuple(c.call_id for c in calls),
            served_models=tuple(dict.fromkeys(c.served_model for c in calls)),
            created_artefact=version.number == 1, items=parsed.ids, links=len(links), flags=len(flags),
        )
