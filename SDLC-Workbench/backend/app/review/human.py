"""What a person does with a phase under review: ask for changes, have only those artefacts rewritten, edit by hand, approve.

An agent can do none of this. The repository already refuses an agent as the actor of a gate; the actions here
also refuse the system, because each one is a human decision that must be attributable to a person.
"""
from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import dataclass, field, replace
from typing import Mapping, Sequence

from ..agents.checks import check_body
from ..agents.errors import AgentError
from ..agents.items import ItemContext, history_of, parse_items
from ..agents.notes import unacted_notes
from ..agents.reply import cited_ids
from ..build import instructions as I
from ..agents.runtime import AgentResult, AgentRuntime
from ..models import InvalidInput, NotFoundError
from ..repos import Store
from ..workflow.engine import WorkflowEngine
from ..trace.gather import gaps_for_phase
from .errors import EditRefused, PersonRequired, ReviewError, WrongPhaseState
from .service import ReviewService

EDITABLE_PHASE_STATES = ("running", "awaiting_review")


def _design_text(upstream, library) -> dict[str, str]:
    """ID -> the design's own text for every item in the saved design the set was built on (for the titles in the design index)."""
    found: dict[str, str] = {}
    for u in upstream:
        skill = library.get(u.key)
        if skill is None or not skill.items:
            continue
        for item in parse_items(u.text, skill.items).items:
            found.setdefault(item.id, item.text)
    return found
MAX_NOTE_CHARS = 4000


def require_person(actor: str, what: str) -> None:
    if not isinstance(actor, str) or not actor.startswith("human:"):
        raise PersonRequired(f"{what} is a human decision; it needs a person ('human:<name>'), not an agent or the system")


@dataclass(frozen=True)
class RerunResult:
    rewritten: dict[str, AgentResult] = field(default_factory=dict)
    failed: dict[str, str] = field(default_factory=dict)  # artefact ID -> plain reason; the old version stands
    stale_not_run: tuple[str, ...] = ()  # built on something that changed; left for the person to choose


@dataclass(frozen=True)
class StaleArtefact:
    artefact_id: str
    version: int
    built_on: Mapping[str, int]  # upstream artefact -> the version it was built on
    now: Mapping[str, int]  # the upstream artefacts that have since moved on -> their current version


class HumanActions:
    def __init__(self, store: Store, engine: WorkflowEngine, runtime: AgentRuntime, reviews: ReviewService):
        self.store = store
        self.engine = engine
        self.runtime = runtime
        self.reviews = reviews

    # ---- ask for changes -------------------------------------------------------------------------------------------

    def request_changes(
        self, project_id: str, phase_key: str, *, actor: str, notes: Mapping[str, str], overall: str | None = None,
        include_findings: Sequence[str] = (),
    ):
        """Send a phase under review back, naming the artefacts to rewrite and what is wrong with each.

        The decision and every note are saved in one transaction. `include_findings` names artefacts whose latest
        review findings should also be saved as notes for the writer; findings are never passed on unless asked.
        """
        require_person(actor, "asking for changes")
        named = {k: (v or "").strip() for k, v in notes.items()}
        if not named:
            raise ReviewError("name at least one artefact to send back, with a note saying what to change")
        blank = [k for k, v in named.items() if not v]
        if blank:
            raise ReviewError(f"each artefact sent back needs a note; missing for {', '.join(sorted(blank))}")
        too_long = [k for k, v in named.items() if len(v) > MAX_NOTE_CHARS]
        if too_long or len((overall or "")) > MAX_NOTE_CHARS:
            raise ReviewError(f"a note is limited to {MAX_NOTE_CHARS} characters")
        unknown = [k for k in include_findings if k not in named]
        if unknown:
            raise ReviewError(f"findings can only be passed on for artefacts you are sending back; not named: {', '.join(unknown)}")
        self._require_phase_state(project_id, phase_key, ("awaiting_review",), "changes can be requested")

        rows: list[tuple[str | None, str, str]] = []
        for artefact_id, text in named.items():
            self._artefact_in_phase(project_id, artefact_id, phase_key)
            rows.append((artefact_id, "human_feedback", text))
        for artefact_id in include_findings:
            record = self._latest_findings(project_id, artefact_id)
            for finding in (record or {}).get("findings", []):
                line = f"Reviewer ({finding['severity'].upper()}) about {finding['target']}: {finding['problem']}"
                if finding.get("fix"):
                    line += f" Fix: {finding['fix']}"
                rows.append((artefact_id, "reviewer_feedback", line[:MAX_NOTE_CHARS]))
        if (overall or "").strip():
            rows.append((None, "human_feedback", overall.strip()))

        summary = "; ".join(f"{k}: {v}" for k, v in named.items())
        return self.engine.reject(project_id, phase_key, actor=actor, feedback=summary[:MAX_NOTE_CHARS], notes=tuple(rows))

    # ---- rewrite only what was sent back ------------------------------------------------------------------------------

    def to_rewrite(self, project_id: str, phase_key: str) -> list[str]:
        """The artefacts a re-run rewrites: those with an unacted note ABOUT THEM. A phase-wide note is shown to every artefact that is
        rewritten, but it never selects one, so one overall remark cannot turn "rewrite these two" into "rewrite everything".

        One rule, used by the re-run here and by the route that names the list to the screen, so the two cannot disagree."""
        return [
            artefact.id for artefact in self.store.artefacts.list(project_id, phase_key=phase_key)
            if artefact.latest_version is not None
            and any(n.artefact_id == artefact.id for n in unacted_notes(self.store, project_id, phase_key, artefact.id))
        ]

    async def rerun_rejected(
        self, project_id: str, phase_key: str, *, actor: str, also: Sequence[str] = (), run_id: str | None = None,
    ) -> RerunResult:
        """Restart a rejected phase and rewrite the artefacts that have an unacted note, plus any in `also`.

        Artefacts are rewritten in catalogue order, because later ones read earlier ones. One that fails keeps its
        old version, the others carry on, and the phase is left running for the person to hand back to review.
        """
        require_person(actor, "re-running a rejected phase")
        self._require_phase_state(project_id, phase_key, ("rejected",), "a rejected phase can be re-run")
        order = {a.key: i for i, a in enumerate(self.engine.catalogue.phase(phase_key).artefacts)}
        todo: dict[str, str] = {a.id: a.type for a in self.store.artefacts.list(project_id, phase_key=phase_key) if a.id in set(self.to_rewrite(project_id, phase_key))}
        for artefact_id in also:
            todo[artefact_id] = self._artefact_in_phase(project_id, artefact_id, phase_key).type
        if not todo:
            raise ReviewError("no artefact has an unaddressed note, and none was named to re-run")

        await asyncio.to_thread(self.engine.start, project_id, phase_key, actor=actor)
        result = RerunResult()
        for artefact_id, key in sorted(todo.items(), key=lambda kv: order.get(kv[1], 999)):
            previous = self.store.artefacts.get_version(project_id, artefact_id).body
            try:
                result.rewritten[artefact_id] = await self.runtime.run(
                    project_id, key, previous_draft=previous, run_id=run_id,
                )
            except (AgentError, ReviewError, InvalidInput) as exc:
                result.failed[artefact_id] = str(exc)
            except Exception as exc:  # noqa: BLE001 - one artefact failing must not lose the others
                result.failed[artefact_id] = f"{type(exc).__name__}: {exc}"
        stale = {s.artefact_id for s in self.stale(project_id, phase_key)} - set(result.rewritten) - set(result.failed)
        return RerunResult(result.rewritten, result.failed, tuple(sorted(stale)))

    # ---- built on something that has changed ---------------------------------------------------------------------------

    def stale(self, project_id: str, phase_key: str | None = None) -> list[StaleArtefact]:
        """Artefacts whose latest version was built on an upstream version that is no longer the latest.

        A version written before this was recorded, or by a person, has no record, so it is not reported."""
        out: list[StaleArtefact] = []
        for artefact in self.store.artefacts.list(project_id, phase_key=phase_key):
            if artefact.latest_version is None:
                continue
            version = self.store.artefacts.get_version(project_id, artefact.id)
            built_on = (version.generation or {}).get("built_on") if isinstance(version.generation, dict) else None
            if not built_on:
                continue
            moved = {}
            for upstream_id, number in built_on.items():
                try:
                    current = self.store.artefacts.get(project_id, upstream_id).latest_version
                except NotFoundError:
                    continue
                if current is not None and current != number:
                    moved[upstream_id] = current
            if moved:
                out.append(StaleArtefact(artefact.id, version.number, dict(built_on), moved))
        return out

    # ---- edit by hand -----------------------------------------------------------------------------------------------------

    def edit(self, project_id: str, artefact_id: str, body: str, *, actor: str, note: str = "") -> int:
        """Save a person's text as a new version, if it passes every check an agent's reply must pass.

        Returns the new version number. Raises EditRefused with the reasons, saving nothing, if it fails."""
        require_person(actor, "editing an artefact")
        artefact = self.store.artefacts.get(project_id, artefact_id)
        if artefact.latest_version is None:
            raise ReviewError(f"{artefact_id} has no version yet; let an agent write the first one")
        self._require_phase_state(project_id, artefact.phase_key, EDITABLE_PHASE_STATES, "an artefact can be edited")
        skill = self.runtime.skills.get(artefact.type)
        if skill is None:
            raise ReviewError(f"there is no skill for '{artefact.type}', so its structure cannot be checked and it cannot be edited here yet")
        body = (body or "").strip()
        if not body:
            raise EditRefused("the edited text is empty", ["the edited text is empty"])

        upstream, item_ctx = self.runtime.inputs_for(project_id, skill)
        upstream_ids = {u.artefact_id for u in upstream}
        # The writer was shown the upstream artefacts AND their items (JS-001, PER-002...), and could cite either. `known` holds both.
        citable = upstream_ids | (item_ctx.known if item_ctx is not None else frozenset())
        resolved = self._resolvable_citations(project_id, citable, body)
        if item_ctx is not None:
            item_ctx = replace(item_ctx, known=item_ctx.known | frozenset(resolved))  # upstream is already in `known`
        problems = check_body(body, skill, citable | resolved, item_ctx, scanner=self.runtime.scanner)
        if problems:
            raise EditRefused(f"the edit was not saved: {'; '.join(problems)}", problems)

        previous = self.store.artefacts.get_version(project_id, artefact_id)
        parsed = parse_items(body, skill.items)
        links = [(item.id, target, "derives") for item in parsed.items for target in item.link_targets]
        generation = {
            "human_edit": True, "based_on": previous.number, "note": (note or "").strip()[:1000] or None,
            "built_on": {u.artefact_id: u.version for u in upstream}, "items": list(parsed.ids),
            "guardrails": [f.as_dict() for f in self.runtime.scanner.scan(body)],
        }

        def still_open(conn: sqlite3.Connection) -> None:
            row = conn.execute(
                "SELECT status FROM phase_runs WHERE project_id = ? AND phase_key = ?", (project_id, artefact.phase_key)
            ).fetchone()
            status = row["status"] if row is not None else "not_started"
            if status not in EDITABLE_PHASE_STATES:
                raise WrongPhaseState(f"the edit was not saved: its phase became '{status}' while it was being checked")

        saved = self.store.artefacts.add_version(
            project_id, artefact_id, body=body, author=actor, source_chunks=cited_ids(body), generation=generation,
            links=links, guard=still_open,
        )
        return saved.number

    def edit_file(self, project_id: str, artefact_id: str, file_name: str, text: str, *, based_on: int, actor: str, note: str = "") -> int:
        """Change ONE file of the Build instruction set and save the set as a new version (S19f-1). Returns the new version number.

        Only the named file's text changes; every other file is kept as it was, every file keeps its item number, and the design index, file list and coverage check are rebuilt
        (no model is called). The file must pass its own checks, and the edit may not introduce a problem into the set; a problem that was already there does not block it.
        `based_on` is the version the person was looking at: if the set has moved on since, nothing is saved. Raises EditRefused with the reasons."""
        require_person(actor, "editing a file")
        artefact = self.store.artefacts.get(project_id, artefact_id)
        if artefact.type != I.INSTRUCTIONS_KEY:
            raise ReviewError(f"{artefact_id} is not a set of instruction files, so it has no files to edit one at a time")
        if artefact.latest_version is None:
            raise ReviewError(f"{artefact_id} has no version yet; let an agent write the first one")
        self._require_phase_state(project_id, artefact.phase_key, EDITABLE_PHASE_STATES, "a file can be edited")
        previous = self.store.artefacts.get_version(project_id, artefact_id)
        if based_on != previous.number:
            raise EditRefused(
                f"the edit was not saved: the set is at version {previous.number} now and you were editing version {based_on}; reload the page and make the change again",
                [f"the set is at version {previous.number} now and you were editing version {based_on}; reload the page and make the change again"],
            )
        skill = self.runtime.skills.get(artefact.type)
        if skill is None:
            raise ReviewError(f"there is no skill for '{artefact.type}', so its structure cannot be checked and it cannot be edited here yet")
        upstream, item_ctx = self.runtime.inputs_for(project_id, skill)
        design = I.DesignIds(frozenset(item_ctx.known), tuple(sorted((i, I.design_title(t)) for i, t in _design_text(upstream, self.runtime.skills).items())))
        files, _ = I.split_set(previous.body)
        if file_name not in files:
            raise NotFoundError(f"{artefact_id} version {previous.number} has no file '{file_name}'; the files are: {', '.join(sorted(files)[:10])}")
        highest = int(item_ctx.highest.get(I.ITEM_PREFIX, 0)) if item_ctx is not None else 0
        try:
            body, _ = I.splice_file(previous.body, file_name, text, design, require_ui=I.ui_expected(files, design), highest=highest)
        except I.FileEditRefused as exc:
            raise EditRefused(str(exc), list(exc.problems)) from exc
        # The artefact's own checks over the whole saved text. A problem the set ALREADY had (in another file) does not block this edit; only one the edit adds does.
        already = set(check_body(previous.body, skill, set(), item_ctx, scanner=self.runtime.scanner))
        problems = [p for p in check_body(body, skill, set(), item_ctx, scanner=self.runtime.scanner) if p not in already]
        if problems:
            raise EditRefused(f"the edit was not saved: {'; '.join(problems)}", problems)

        parsed = parse_items(body, skill.items)
        links = [(item.id, target, "derives") for item in parsed.items for target in item.link_targets]
        generation = {
            "human_edit": True, "edited_file": file_name, "based_on": previous.number, "note": (note or "").strip()[:1000] or None,
            "built_on": {u.artefact_id: u.version for u in upstream}, "items": list(parsed.ids),
            "guardrails": [f.as_dict() for f in self.runtime.scanner.scan(body)],
        }

        def still_open(conn: sqlite3.Connection) -> None:
            row = conn.execute("SELECT status FROM phase_runs WHERE project_id = ? AND phase_key = ?", (project_id, artefact.phase_key)).fetchone()
            status = row["status"] if row is not None else "not_started"
            if status not in EDITABLE_PHASE_STATES:
                raise WrongPhaseState(f"the edit was not saved: its phase became '{status}' while it was being checked")
            latest = conn.execute("SELECT MAX(number) AS n FROM artefact_versions WHERE project_id = ? AND artefact_id = ?", (project_id, artefact_id)).fetchone()["n"]
            if latest != previous.number:
                raise EditRefused("the edit was not saved: the set changed while it was being checked; reload the page and make the change again", ["the set changed while it was being checked"])

        saved = self.store.artefacts.add_version(
            project_id, artefact_id, body=body, author=actor, source_chunks=cited_ids(body), generation=generation, links=links, guard=still_open,
        )
        return saved.number

    def _resolvable_citations(self, project_id: str, upstream_ids: set[str], body: str) -> set[str]:
        """The citations in a person's text that point at a real source in THIS project (a document or memory chunk).

        A whole upstream artefact is not looked up here: it is allowed because the writer was shown it too."""
        return {c for c in cited_ids(body) if c not in upstream_ids and self.store.context.resolve(project_id, c) is not None}

    def _flagged(self, project_id: str, phase_key: str) -> dict[str, dict[str, int]]:
        """Artefacts whose latest version carries personal-data flags: {artefact ID: {rule: count}}. Counts only, never values."""
        from ..guardrails.scan import counts_by_rule, Finding

        out: dict[str, dict[str, int]] = {}
        for artefact in self.store.artefacts.list(project_id, phase_key=phase_key):
            if artefact.latest_version is None:
                continue
            record = self.store.artefacts.get_version(project_id, artefact.id).generation
            found = [f for f in (record or {}).get("guardrails", []) if f.get("class") == "personal"]
            if found:
                out[artefact.id] = dict(sorted({r: sum(1 for f in found if f["rule"] == r) for r in {f["rule"] for f in found}}.items()))
        return out

    def _latest_findings(self, project_id: str, artefact_id: str):
        for version in reversed(self.store.artefacts.versions(project_id, artefact_id)):
            if isinstance(version.review_findings, dict) and "findings" in version.review_findings:
                return version.review_findings
        return None

    # ---- approve ----------------------------------------------------------------------------------------------------------

    def open_items(self, project_id: str, phase_key: str) -> dict:
        """What is still open in a phase: the one list the screen shows BEFORE approving and the audit row records AT approving.

        One function builds both, so what a person was shown and what was recorded cannot differ."""
        highs, unreviewed, stale_reviews = 0, [], []
        for artefact in self.store.artefacts.list(project_id, phase_key=phase_key):
            if artefact.latest_version is None:
                continue
            status = self.reviews.status_of(project_id, artefact.id)
            # A retired artefact's status is "retired" with no verdict and no findings, so it falls into neither list below: it is not "never reviewed" and adds no findings.
            if status.state == "unreviewed":
                unreviewed.append(artefact.id)
            else:
                highs += status.high_findings
                if status.state == "stale":
                    stale_reviews.append(artefact.id)
        return {
            "open_high_findings": highs, "unreviewed": unreviewed, "review_out_of_date": stale_reviews,
            "built_on_changed": [s.artefact_id for s in self.stale(project_id, phase_key)],
            "guardrail_flags": self._flagged(project_id, phase_key),
            # S15: links that should exist and do not. From the same computation as the Traceability tab, so the two cannot disagree.
            "traceability_gaps": gaps_for_phase(self.store, self.runtime.skills, self.engine.catalogue, project_id, phase_key),
        }

    def approve(self, project_id: str, phase_key: str, *, actor: str):
        """Approve a phase under review, recording in the audit row what was still open when the person approved."""
        require_person(actor, "approving a phase")
        return self.engine.approve(project_id, phase_key, actor=actor, detail=self.open_items(project_id, phase_key))

    # ---- shared checks ------------------------------------------------------------------------------------------------------

    def _require_phase_state(self, project_id: str, phase_key: str, allowed: Sequence[str], what: str) -> None:
        try:
            status = self.store.phases.get(project_id, phase_key).status
        except NotFoundError:
            status = "not_started"
        if status not in allowed:
            raise WrongPhaseState(f"{what} only while the phase is {' or '.join(allowed)}; {phase_key} is '{status}'")

    def _artefact_in_phase(self, project_id: str, artefact_id: str, phase_key: str):
        artefact = self.store.artefacts.get(project_id, artefact_id)
        if artefact.phase_key != phase_key:
            raise ReviewError(f"{artefact_id} belongs to phase '{artefact.phase_key}', not '{phase_key}'")
        return artefact
