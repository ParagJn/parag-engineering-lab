"""Running a whole phase: artefacts start as soon as what they wait for has finished, several at once, under caps.

One call, `PhaseRunner.run_phase`, does the work and returns a `RunResult`. The same work can be started in the
background with `start_phase`, which returns at once with a run ID so a screen can follow the events.

Why this is safe with the code that already exists: `AgentRuntime.run` is one coroutine per artefact that does its
database work in short transactions and saves in one, so artefacts cannot corrupt each other. The scheduler's own
shared state is a handful of dicts touched only on the event loop (no await between a read and its write), and the
`Meter`, which is locked because model calls report from different tasks.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Sequence

from ..agents.errors import AgentError, RunStopped
from ..agents.runtime import AgentResult, AgentRuntime
from ..config import Settings
from ..llm.errors import LLMError, ReviewerUnavailable
from ..llm.types import LLMResult
from ..models import InvalidInput, NotFoundError
from ..repos import Store
from ..review.service import PausedReview, ReviewResult, ReviewService
from ..workflow.engine import WorkflowEngine
from ..workflow.gates import check_can_start
from .budget import STOP_CANCELLED, Meter, blocked_by, ready, wanted_keys
from .errors import RunAlreadyActive, RunError, UnknownArtefact
from .events import EventBus, clean_reason, event_reason

log = logging.getLogger(__name__)

# Final state of each artefact in a run.
DONE, FAILED, SKIPPED, NOT_STARTED = "done", "failed", "skipped", "not_started"


MAX_STORED_PROBLEMS = 5       # the last attempt's problems kept with a failed artefact, so a person can see WHY it failed afterwards


@dataclass
class ArtefactOutcome:
    key: str
    state: str  # done | failed | skipped | not_started
    reason: str | None = None
    why: list = field(default_factory=list)   # the checks' own sentences for a reply that failed them (bounded, cleaned)
    cut_off: bool = False                     # the last reply stopped because it hit the output limit
    artefact_id: str | None = None
    version: int | None = None
    attempts: int = 0
    cost_usd: float | None = None
    review: dict | None = None  # {"verdict", "label"} or {"paused": True}


@dataclass
class RunResult:
    run_id: str
    project_id: str
    phase_key: str
    status: str  # finished | stopped | failed
    stop_reason: str | None
    outcomes: list[ArtefactOutcome]
    totals: dict
    serial_seconds: float  # the sum of each artefact's own elapsed time: what a one-at-a-time run would have taken
    elapsed_seconds: float
    max_in_flight: int
    build: Any = None  # a BuildOutcome when the Build phase ran its fix loop (or said why it did not), else None

    def by_key(self) -> dict[str, ArtefactOutcome]:
        return {o.key: o for o in self.outcomes}


class PhaseRunner:
    def __init__(
        self, settings: Settings, store: Store, engine: WorkflowEngine, runtime: AgentRuntime,
        reviews: ReviewService, bus: EventBus,
        clock: Callable[[], float] = time.monotonic, build: Any = None,
    ):
        self.settings = settings
        self.store = store
        self.engine = engine
        self.runtime = runtime
        self.reviews = reviews
        self.bus = bus
        self.clock = clock
        self.build = build                  # BuildHooks, or None: every phase but Build runs with none and is exactly as it was
        self._active: dict[tuple[str, str], str] = {}  # (project, phase) -> run id
        self._meters: dict[str, Meter] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    # ---- starting ---------------------------------------------------------------------------------------

    def start_phase(self, project_id: str, phase_key: str, **options: Any) -> str:
        """Begin a run in the background and return its ID at once. Must be called from inside the event loop."""
        run_id = self._begin(project_id, phase_key, options)
        task = asyncio.get_running_loop().create_task(self._run_guarded(run_id, project_id, phase_key, options))
        self._tasks[run_id] = task

        def finished(done: asyncio.Task, rid: str = run_id) -> None:
            self._tasks.pop(rid, None)
            if not done.cancelled() and done.exception() is not None:   # reading it marks it retrieved
                log.warning("background run %s ended with an error (recorded on the run)", rid)

        task.add_done_callback(finished)
        return run_id

    async def run_phase(self, project_id: str, phase_key: str, **options: Any) -> RunResult:
        """Run a phase and wait for the result."""
        run_id = self._begin(project_id, phase_key, options)
        return await self._run_guarded(run_id, project_id, phase_key, options)

    def cancel(self, project_id: str, run_id: str) -> bool:
        """Ask a running run to stop starting new work. Returns False if it was not running. A request, not a kill."""
        self.store.runs.get(project_id, run_id)  # NotFoundError for an unknown run
        meter = self._meters.get(run_id)
        if meter is None:
            return False
        meter.cancel()
        return True

    def is_active(self, project_id: str, phase_key: str) -> bool:
        return (project_id, phase_key) in self._active

    @property
    def active_count(self) -> int:
        return len(self._active)

    # ---- the guard: one run per phase ----------------------------------------------------------------------------

    def _begin(self, project_id: str, phase_key: str, options: dict) -> str:
        """Check everything that can be checked before spending money, then claim the phase and record the run."""
        self._validate(project_id, phase_key, options)
        key = (project_id, phase_key)
        if key in self._active:
            raise RunAlreadyActive(
                f"{phase_key} is already being run (run {self._active[key]}); wait for it to finish or cancel it"
            )
        record = self.store.runs.start(project_id, phase_key)
        self._active[key] = record.id
        self._meters[record.id] = Meter(self.settings.run_max_cost_usd, self.settings.run_max_seconds, self.clock)
        return record.id

    def _validate(self, project_id: str, phase_key: str, options: dict) -> None:
        project = self.store.projects.get(project_id)
        plan = self.engine.plan_for(project)
        try:
            phase = plan.phase(phase_key)
        except KeyError:
            raise NotFoundError(f"unknown phase {phase_key!r}") from None
        known = {a.key for a in phase.artefacts}
        only = options.get("only")
        if only is not None:
            unknown = [k for k in only if k not in known]
            if unknown:
                raise UnknownArtefact(
                    f"not in the plan for {phase_key}: {', '.join(unknown)}; the plan has {', '.join(sorted(known))}"
                )
            if not only:
                raise RunError("'only' names no artefacts")
        if only is not None and options.get("rewrite_all"):
            raise RunError("use 'only' or 'rewrite_all', not both")
        status = self._phase_status(project_id, phase_key)
        if status in ("not_started", "rejected"):
            check_can_start(plan, self.store.phases.list(project_id), phase_key)   # PrerequisiteNotMet, before any money is spent
        if status == "approved":
            raise RunError(f"{phase_key} is approved; reopen it before running it again")
        if status == "awaiting_review":
            raise RunError(f"{phase_key} is awaiting review; send it back for changes before running it again")

    def _phase_status(self, project_id: str, phase_key: str) -> str:
        try:
            return self.store.phases.get(project_id, phase_key).status
        except NotFoundError:
            return "not_started"

    # ---- the run itself ---------------------------------------------------------------------------------------------

    async def _run_guarded(self, run_id: str, project_id: str, phase_key: str, options: dict) -> RunResult:
        meter = self._meters[run_id]
        try:
            return await self._execute(run_id, project_id, phase_key, options, meter)
        except BaseException as exc:
            # Whatever went wrong, the run row must not stay "running" and the phase must be free again.
            reason = event_reason(exc, self.settings.secret_values())
            try:
                self.store.runs.end(run_id, "failed", totals={**meter.snapshot(), "error": reason})
                self.bus.publish(project_id, run_id, "run.stopped", {"status": "failed", "reason": reason})
            except Exception:  # noqa: BLE001 - the original error matters more than a failure to record it
                log.error("could not record the failure of run %s", run_id, exc_info=True)
            raise
        finally:
            self._active.pop((project_id, phase_key), None)
            self._meters.pop(run_id, None)

    async def _execute(self, run_id: str, project_id: str, phase_key: str, options: dict, meter: Meter) -> RunResult:
        wall_start = self.clock()
        project = self.store.projects.get(project_id)
        phase = self.engine.plan_for(project).phase(phase_key)
        order = [a.key for a in phase.artefacts]
        after = {a.key: tuple(a.after) for a in phase.artefacts}
        existing = {a.type: a for a in self.store.artefacts.list(project_id, phase_key=phase_key)}
        has_version = {k: (k in existing and existing[k].latest_version is not None) for k in order}
        wanted = wanted_keys(order, has_version, only=options.get("only"), rewrite_all=bool(options.get("rewrite_all")))
        # What the phase's hook writes itself AFTER the artefacts (S18: the Build test report and review) is not scheduled here as model work.
        hook_writes = set(self.build.writes(phase_key)) if self.build is not None else set()
        wanted = [k for k in wanted if k not in hook_writes]
        review = bool(options.get("review"))

        self.bus.publish(project_id, run_id, "run.started", {
            "phase": phase_key, "artefacts": wanted, "concurrency": self.settings.run_max_concurrency, "review": review,
            "max_cost_usd": self.settings.run_max_cost_usd or None, "max_seconds": self.settings.run_max_seconds or None,
        })
        # Start the phase if it needs starting. Prerequisites were checked up front and are enforced again here, under the
        # database lock, exactly as for a person: the answer can change between the two.
        status = self._phase_status(project_id, phase_key)
        if status in ("not_started", "rejected"):
            await asyncio.to_thread(self.engine.start, project_id, phase_key, actor="system")
            self.bus.publish(project_id, run_id, "gate.changed", {"phase": phase_key, "status": "running"})

        outcomes: dict[str, ArtefactOutcome] = {k: ArtefactOutcome(k, NOT_STARTED) for k in wanted}
        # Artefacts the run is not producing still count as "done" for ordering when they already have content.
        done: set[str] = {k for k in order if k not in wanted and has_version[k]}
        started: set[str] = set(done)
        failed: dict[str, str] = {}
        skipped: dict[str, str] = {}
        elapsed: dict[str, float] = {}
        running: dict[asyncio.Task, str] = {}
        stop_reason: str | None = None
        max_in_flight = 0
        cap = self.settings.run_max_concurrency

        def skip_blocked() -> None:
            for key, cause in blocked_by(wanted, after, failed, skipped).items():
                if key in started or key in skipped:
                    continue
                reason = f"blocked by {cause}"
                skipped[key] = reason
                started.add(key)
                outcomes[key] = ArtefactOutcome(key, SKIPPED, reason)
                self.bus.publish(project_id, run_id, "artefact.skipped", {"key": key, "reason": reason})

        # Artefacts we are not running but that have no content are a problem for anything that needs them.
        for key in wanted:
            for dep in after[key]:
                if dep in order and dep not in wanted and not has_version[dep]:
                    failed.setdefault(dep, "has no content and is not part of this run")
        skip_blocked()

        while True:
            stop_reason = stop_reason or meter.should_stop()
            if stop_reason is None:
                for key in ready(wanted, after, done, started):  # the FULL list: a dependency that is running must still block
                    if len(running) >= cap:
                        break
                    if key in started:  # cannot happen; if it ever did, an artefact would be written over and over, so stop at once
                        raise RuntimeError(f"scheduler fault: {key} was offered to start a second time")
                    started.add(key)
                    task = asyncio.create_task(self._one(run_id, project_id, phase_key, key, review, meter, outcomes, elapsed))
                    running[task] = key
                    max_in_flight = max(max_in_flight, len(running))
            if not running:
                break
            finished, _ = await asyncio.wait(running, return_when=asyncio.FIRST_COMPLETED, timeout=self._poll_seconds(meter))
            for task in finished:
                key = running.pop(task)
                outcome = outcomes[key]
                if outcome.state == DONE:
                    done.add(key)
                elif outcome.state == FAILED:
                    failed[key] = outcome.reason or "failed"
                elif outcome.state == NOT_STARTED:
                    pass  # dropped unsaved because the run was stopped; recorded below
                skip_blocked()

        stop_reason = stop_reason or meter.should_stop()
        build_outcome = None
        if self.build is not None and self.build.wants(phase_key):
            build_outcome = await self._build_loop(run_id, project_id, done, failed, skipped, meter, stop_reason)
            stop_reason = stop_reason or meter.should_stop()
        # Anything never started is reported honestly; if the run was stopped, say why.
        for key in wanted:
            outcome = outcomes[key]
            if outcome.state == NOT_STARTED and outcome.reason is None:
                outcome.reason = f"the run was stopped ({stop_reason})" if stop_reason else "never started"

        counts = {s: sum(1 for o in outcomes.values() if o.state == s) for s in (DONE, FAILED, SKIPPED, NOT_STARTED)}
        status = "stopped" if stop_reason else ("failed" if counts[FAILED] else "finished")
        totals = {**meter.snapshot(), "artefacts": counts}
        # What went wrong with each failed artefact, kept with the run so it can be read afterwards (the event only has a short sentence). Bounded and cleaned.
        failures = {k: {"reason": o.reason, "problems": o.why, "cut_off": o.cut_off} for k, o in outcomes.items() if o.state == FAILED}
        if failures:
            totals["failures"] = failures
        if build_outcome is not None:
            totals["build"] = {"result": build_outcome.result, "reason": clean_reason(build_outcome.reason, self.settings.secret_values()), "rounds": build_outcome.rounds}
        serial = round(sum(elapsed.values()), 3)
        wall = round(self.clock() - wall_start, 3)
        totals.update({"serial_seconds": serial, "elapsed_seconds": wall, "max_in_flight": max_in_flight})
        self.store.runs.end(run_id, status if status != "failed" else "failed", stop_reason=stop_reason, totals=totals)
        event = "run.stopped" if stop_reason else "run.finished"
        # The failure DETAILS live in the stored run record only. An event is bounded (20,000 bytes) and a run with many failed artefacts could pass that,
        # which would raise here and turn a finished run into a failed one. The event keeps its short sentence per artefact (`artefact.failed`).
        self.bus.publish(project_id, run_id, event, {"status": status, "reason": stop_reason, **{k: v for k, v in totals.items() if k != "failures"}})
        return RunResult(
            run_id, project_id, phase_key, status, stop_reason, [outcomes[k] for k in wanted], totals, serial, wall, max_in_flight, build_outcome,
        )

    async def _build_loop(self, run_id, project_id, done, failed, skipped, meter, stop_reason):
        """The Build phase's one extra step: really run the generated tests and ask for fixes. The hook decides whether it can, and puts the workspace back."""
        return await self.build.after_artefacts(
            project_id, run_id, done, failed, skipped, meter, lambda kind, data: self.bus.publish(project_id, run_id, kind, data), stop_reason,
        )

    def _poll_seconds(self, meter: Meter) -> float | None:
        """How long to wait for a task before looking at the clock again: so a time cap is honoured even if a call hangs."""
        return 0.25 if meter.max_seconds > 0 else None

    # ---- one artefact ----------------------------------------------------------------------------------------------------

    async def _one(
        self, run_id: str, project_id: str, phase_key: str, key: str, review: bool, meter: Meter,
        outcomes: dict[str, ArtefactOutcome], elapsed: dict[str, float],
    ) -> None:
        outcome = outcomes[key]
        began = self.clock()
        secrets = self.settings.secret_values()
        self.bus.publish(project_id, run_id, "artefact.started", {"key": key})

        def on_call(result: LLMResult, attempt: int, problems: list[str]) -> str | None:
            meter.add_call(result.cost_usd, result.tokens_in, result.tokens_out)
            if attempt > 1 or problems or result.attempts > 1 or result.fallback_used:
                self.bus.publish(project_id, run_id, "artefact.attempt", {
                    "key": key, "attempt": attempt, "model_attempts": result.attempts, "fell_back": result.fallback_used,
                    "will_repair": bool(problems), "problems": len(problems),
                })
            # A cap or a cancel may drop an artefact only when it still needs ANOTHER call. A reply that is already
            # valid is saved: its money is spent, and dropping it would waste that and break "in flight finishes".
            return meter.should_stop() if problems else None

        previous = None
        if key in {a.type for a in self.store.artefacts.list(project_id, phase_key=phase_key)}:
            existing = next(a for a in self.store.artefacts.list(project_id, phase_key=phase_key) if a.type == key)
            if existing.latest_version is not None:
                previous = self.store.artefacts.get_version(project_id, existing.id).body
        try:
            if self.build is not None and self.build.composes(phase_key, key):
                # Written in small pieces by the phase's own hook (S19b); every piece event carries this artefact's key so the screen can file it under its row.
                result: AgentResult = await self.build.compose(
                    project_id, run_id, meter, lambda kind, data: self.bus.publish(project_id, run_id, kind, {"key": key, **data}),
                )
            else:
                result = await self.runtime.run(
                    project_id, key, previous_draft=previous, run_id=run_id, on_call=on_call,
                    extra_check=self.build.extra_check(phase_key, key, project_id) if self.build is not None else None,
                )
        except RunStopped as exc:
            outcome.state, outcome.reason = NOT_STARTED, f"dropped unsaved: the run was stopped ({exc.reason})"
            self.bus.publish(project_id, run_id, "artefact.failed", {"key": key, "reason": outcome.reason, "saved": False})
            elapsed[key] = self.clock() - began
            return
        except asyncio.CancelledError:
            raise
        except (AgentError, LLMError, InvalidInput) as exc:
            outcome.state, outcome.reason = FAILED, clean_reason(str(exc), secrets)   # the full reason stays in the result
            outcome.why = [clean_reason(p, secrets) for p in list(getattr(exc, "problems", ()))[:MAX_STORED_PROBLEMS]]
            outcome.cut_off = bool(getattr(exc, "cut_off", False))
            self.bus.publish(project_id, run_id, "artefact.failed", {"key": key, "reason": event_reason(exc, secrets), "saved": False})
            elapsed[key] = self.clock() - began
            return
        except Exception as exc:  # noqa: BLE001 - one artefact's bug must not take the others down
            log.warning("artefact %s failed unexpectedly", key, exc_info=True)
            outcome.state, outcome.reason = FAILED, clean_reason(f"{type(exc).__name__}: {exc}", secrets)
            self.bus.publish(project_id, run_id, "artefact.failed", {"key": key, "reason": event_reason(exc, secrets), "saved": False})
            elapsed[key] = self.clock() - began
            return

        outcome.state = DONE
        outcome.artefact_id, outcome.version, outcome.attempts, outcome.cost_usd = (
            result.artefact_id, result.version, result.attempts, result.cost_usd,
        )
        self.bus.publish(project_id, run_id, "artefact.finished", {
            "key": key, "artefact_id": result.artefact_id, "version": result.version, "attempts": result.attempts,
            "tokens_in": result.tokens_in, "tokens_out": result.tokens_out, "cost_usd": result.cost_usd,
            "items": len(result.items), "links": result.links, "flags": result.flags, "author": result.author,
        })
        if review and meter.should_stop() is None:
            await self._review(run_id, project_id, result.artefact_id, outcome, meter)
        elapsed[key] = self.clock() - began

    async def _review(self, run_id: str, project_id: str, artefact_id: str, outcome: ArtefactOutcome, meter: Meter) -> None:
        self.bus.publish(project_id, run_id, "review.started", {"artefact_id": artefact_id})
        try:
            result = await self.reviews.review(project_id, artefact_id, run_id=run_id)
        except ReviewerUnavailable as exc:
            outcome.review = {"paused": True}
            self.bus.publish(project_id, run_id, "review.paused", {
                "artefact_id": artefact_id, "slot": exc.slot, "options": [o.slot for o in exc.options],
            })
            return
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - a review that fails must not fail the artefact it was reviewing
            outcome.review = {"failed": clean_reason(f"{type(exc).__name__}: {exc}", self.settings.secret_values())}
            self.bus.publish(project_id, run_id, "review.paused", {
                "artefact_id": artefact_id, "reason": event_reason(exc, self.settings.secret_values()),
            })
            return
        meter.add_call(result.cost_usd, result.tokens_in, result.tokens_out)
        outcome.review = {"verdict": result.verdict, "label": result.independence["verdict"]}
        self.bus.publish(project_id, run_id, "review.finished", {
            "artefact_id": artefact_id, "verdict": result.verdict, "findings": len(result.findings),
            "label": result.independence["verdict"], "cost_usd": result.cost_usd,
        })
