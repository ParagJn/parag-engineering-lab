from __future__ import annotations

import json
import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Iterable, Mapping, Sequence

import sqlite3

from .db import Database
from .models import (
    DECISIONS,
    LINK_KINDS,
    MEMORY_KINDS,
    MODES,
    PHASE_STATUSES,
    TRACE_STATUSES,
    Artefact,
    ArtefactVersion,
    AuditEvent,
    PHASE_TRANSITIONS,
    ConflictError,
    BuildRound,
    RunEvent,
    RunRecord,
    IllegalTransition,
    InvalidInput,
    Link,
    MemoryEntry,
    NotFoundError,
    PhaseRun,
    Project,
    RollupRow,
    Trace,
    VerifyMatch,
    VerifyRun,
)

_UNSET: Any = object()

# Runs inside a phase transaction and raises to refuse the move. Used by the workflow engine so
# its checks and the status change happen under one lock, with no gap for a second caller.
Guard = Callable[[sqlite3.Connection, "PhaseRun"], None]

# Who did it: the system, a person, or an agent running on a model.
_ACTOR_RE = re.compile(r"system|human:\S.*|agent:[^@\s]+@\S+")
# Stable artefact and item ids such as REQ-F-012, DES-UJ-001, ARC-HLD-001.
ID_RE = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3,}")
PREFIX_RE = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*")

_ROLLUP_COLUMNS = {
    "model": "served_model",
    "phase": "phase_key",
    "agent": "agent",
    "slot": "slot",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


# ---- validation helpers ----------------------------------------------------

def check_actor(actor: str) -> str:
    if not isinstance(actor, str) or not _ACTOR_RE.fullmatch(actor):
        raise InvalidInput(
            "actor must be 'system', 'human:<name>' or 'agent:<role>@<model>', got %r" % (actor,)
        )
    return actor


def _check_author(author: str) -> str:
    check_actor(author)
    if author == "system":
        raise InvalidInput("a version's author must be a human or an agent, not 'system'")
    return author


def _text(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidInput(f"{what} must not be blank")
    return value.strip()


def _check_mode(mode: str) -> str:
    if mode not in MODES:
        raise InvalidInput(f"mode must be one of {MODES}, got {mode!r}")
    return mode


def _dump(value: Any, what: str) -> str:
    try:
        return json.dumps(value, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise InvalidInput(f"{what} must be JSON-serialisable") from exc


def _dump_object(value: Any, what: str) -> str:
    if not isinstance(value, dict):
        raise InvalidInput(f"{what} must be an object")
    return _dump(value, what)


def _count(value: Any, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidInput(f"{what} must be a whole number, zero or more")
    return value


# ---- audit -----------------------------------------------------------------

def write_audit(
    conn: sqlite3.Connection,
    at: str,
    actor: str,
    action: str,
    target_type: str,
    target_id: str,
    *,
    project_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> int:
    """Append one audit row inside the caller's transaction, so a change and its record commit together."""
    check_actor(actor)
    cursor = conn.execute(
        "INSERT INTO audit (project_id, at, actor, action, target_type, target_id, detail)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (project_id, at, actor, action, target_type, target_id, _dump(detail or {}, "detail")),
    )
    return cursor.lastrowid


# ---- row mappers -----------------------------------------------------------

def _project(r: sqlite3.Row) -> Project:
    return Project(
        id=r["id"],
        name=r["name"],
        brief=r["brief"],
        mode=r["mode"],
        selection=json.loads(r["selection"]),
        routing_overrides=json.loads(r["routing_overrides"]),
        context_id=r["context_id"],
        created_at=r["created_at"],
        updated_at=r["updated_at"],
        archived_at=r["archived_at"],
    )


def _phase(r: sqlite3.Row) -> PhaseRun:
    return PhaseRun(
        project_id=r["project_id"],
        phase_key=r["phase_key"],
        status=r["status"],
        started_at=r["started_at"],
        finished_at=r["finished_at"],
        decision=r["decision"],
        decided_by=r["decided_by"],
        feedback=r["feedback"],
        updated_at=r["updated_at"],
    )


def _artefact(r: sqlite3.Row) -> Artefact:
    return Artefact(
        project_id=r["project_id"],
        id=r["id"],
        type=r["type"],
        phase_key=r["phase_key"],
        title=r["title"],
        created_at=r["created_at"],
        latest_version=r["latest_version"],
    )


def _version(r: sqlite3.Row) -> ArtefactVersion:
    findings = r["review_findings"]
    generation = r["generation"]
    return ArtefactVersion(
        project_id=r["project_id"],
        artefact_id=r["artefact_id"],
        number=r["number"],
        body=r["body"],
        author=r["author"],
        source_chunks=tuple(json.loads(r["source_chunks"])),
        review_findings=None if findings is None else json.loads(findings),
        created_at=r["created_at"],
        generation=None if generation is None else json.loads(generation),
    )


def _link(r: sqlite3.Row) -> Link:
    return Link(
        id=r["id"],
        project_id=r["project_id"],
        from_id=r["from_id"],
        to_id=r["to_id"],
        kind=r["kind"],
        declared_in=r["declared_in"],
        created_at=r["created_at"],
    )


def _trace(r: sqlite3.Row) -> Trace:
    return Trace(
        id=r["id"],
        project_id=r["project_id"],
        run_id=r["run_id"],
        agent=r["agent"],
        phase_key=r["phase_key"],
        slot=r["slot"],
        requested_model=r["requested_model"],
        served_model=r["served_model"],
        fallback_used=bool(r["fallback_used"]),
        status=r["status"],
        error=r["error"],
        tokens_in=r["tokens_in"],
        tokens_out=r["tokens_out"],
        latency_ms=r["latency_ms"],
        cost_usd=r["cost_usd"],
        created_at=r["created_at"],
        call_id=r["call_id"],
        attempt=r["attempt"],
    )


def _audit_event(r: sqlite3.Row) -> AuditEvent:
    return AuditEvent(
        id=r["id"],
        project_id=r["project_id"],
        at=r["at"],
        actor=r["actor"],
        action=r["action"],
        target_type=r["target_type"],
        target_id=r["target_id"],
        detail=json.loads(r["detail"]),
    )


def _memory(r: sqlite3.Row) -> MemoryEntry:
    return MemoryEntry(
        id=r["id"],
        project_id=r["project_id"],
        kind=r["kind"],
        phase_key=r["phase_key"],
        artefact_id=r["artefact_id"],
        text=r["text"],
        created_at=r["created_at"],
    )


_ARTEFACT_SELECT = (
    "SELECT a.*, (SELECT MAX(v.number) FROM artefact_versions v"
    " WHERE v.project_id = a.project_id AND v.artefact_id = a.id) AS latest_version"
    " FROM artefacts a"
)


# ---- existence checks (clear NotFoundError instead of a raw foreign-key error) ----

def _require_project(conn: sqlite3.Connection, project_id: str) -> None:
    if conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() is None:
        raise NotFoundError(f"project {project_id!r} not found")


def _require_artefact(conn: sqlite3.Connection, project_id: str, artefact_id: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM artefacts WHERE project_id = ? AND id = ?", (project_id, artefact_id)
    ).fetchone()
    if row is None:
        raise NotFoundError(f"artefact {artefact_id!r} not found in project {project_id!r}")


def phase_runs_in(conn: sqlite3.Connection, project_id: str) -> list[PhaseRun]:
    """Every phase row of a project, read inside the caller's transaction."""
    rows = conn.execute(
        "SELECT * FROM phase_runs WHERE project_id = ? ORDER BY rowid", (project_id,)
    ).fetchall()
    return [_phase(r) for r in rows]


def artefact_types_with_content_in(conn: sqlite3.Connection, project_id: str) -> set[tuple[str, str]]:
    """(phase_key, artefact type) for every artefact that has at least one version."""
    rows = conn.execute(
        "SELECT DISTINCT a.phase_key, a.type FROM artefacts a"
        " JOIN artefact_versions v ON v.project_id = a.project_id AND v.artefact_id = a.id"
        " WHERE a.project_id = ?",
        (project_id,),
    ).fetchall()
    return {(r["phase_key"], r["type"]) for r in rows}


class _Repo:
    def __init__(self, db: Database, clock: Callable[[], str], ids: Callable[[], str]):
        self.db = db
        self._clock = clock
        self._ids = ids


# ---- projects --------------------------------------------------------------

class ProjectRepo(_Repo):
    def create(
        self,
        *,
        name: str,
        actor: str,
        brief: str = "",
        mode: str = "replay",
        selection: dict[str, Any] | None = None,
        routing_overrides: dict[str, Any] | None = None,
        context_id: str | None = None,
    ) -> Project:
        check_actor(actor)
        name = _text(name, "name")
        _check_mode(mode)
        selection_json = _dump_object({} if selection is None else selection, "selection")
        routing_json = _dump_object(
            {} if routing_overrides is None else routing_overrides, "routing_overrides"
        )
        project_id = self._ids()
        with self.db.write() as conn:
            now = self._clock()
            conn.execute(
                "INSERT INTO projects (id, name, brief, mode, selection, routing_overrides,"
                " context_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, name, brief, mode, selection_json, routing_json, context_id, now, now),
            )
            write_audit(
                conn, now, actor, "project.created", "project", project_id,
                project_id=project_id, detail={"name": name, "mode": mode},
            )
            return _project(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())

    def get(self, project_id: str) -> Project:
        with self.db.read() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            raise NotFoundError(f"project {project_id!r} not found")
        return _project(row)

    def list(self, *, archived: bool = False) -> list[Project]:
        """Active projects by default; `archived=True` lists the archived ones instead. Never both together."""
        where = "archived_at IS NOT NULL" if archived else "archived_at IS NULL"
        with self.db.read() as conn:
            rows = conn.execute(f"SELECT * FROM projects WHERE {where} ORDER BY rowid").fetchall()
        return [_project(r) for r in rows]

    def archive(self, project_id: str, *, actor: str) -> Project:
        """Hide a project and make it read-only. Nothing is deleted. Archiving an archived project changes nothing and writes no audit row."""
        return self._set_archived(project_id, actor, archive=True)

    def restore(self, project_id: str, *, actor: str) -> Project:
        return self._set_archived(project_id, actor, archive=False)

    def _set_archived(self, project_id: str, actor: str, *, archive: bool) -> Project:
        check_actor(actor)
        with self.db.write() as conn:
            _require_project(conn, project_id)
            row = conn.execute("SELECT archived_at FROM projects WHERE id = ?", (project_id,)).fetchone()
            if (row["archived_at"] is not None) != archive:
                now = self._clock()
                conn.execute("UPDATE projects SET archived_at = ? WHERE id = ?", (now if archive else None, project_id))
                write_audit(
                    conn, now, actor, "project.archived" if archive else "project.restored", "project", project_id, project_id=project_id, detail={},
                )
            return _project(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())

    def count(self) -> int:
        with self.db.read() as conn:
            return conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]

    def update(
        self,
        project_id: str,
        *,
        actor: str,
        name: Any = _UNSET,
        brief: Any = _UNSET,
        mode: Any = _UNSET,
        selection: Any = _UNSET,
        routing_overrides: Any = _UNSET,
        context_id: Any = _UNSET,
    ) -> Project:
        """Change only the fields passed. Pass context_id=None to clear it."""
        check_actor(actor)
        changes: dict[str, Any] = {}
        if name is not _UNSET:
            changes["name"] = _text(name, "name")
        if brief is not _UNSET:
            changes["brief"] = brief
        if mode is not _UNSET:
            changes["mode"] = _check_mode(mode)
        if selection is not _UNSET:
            changes["selection"] = _dump_object(selection, "selection")
        if routing_overrides is not _UNSET:
            changes["routing_overrides"] = _dump_object(routing_overrides, "routing_overrides")
        if context_id is not _UNSET:
            changes["context_id"] = context_id
        if not changes:
            return self.get(project_id)

        with self.db.write() as conn:
            _require_project(conn, project_id)
            now = self._clock()
            changes["updated_at"] = now
            columns = ", ".join(f"{column} = ?" for column in changes)  # keys are fixed above
            conn.execute(f"UPDATE projects SET {columns} WHERE id = ?", (*changes.values(), project_id))
            write_audit(
                conn, now, actor, "project.updated", "project", project_id, project_id=project_id,
                detail={"changed": sorted(k for k in changes if k != "updated_at")},
            )
            return _project(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())


# ---- phase runs ------------------------------------------------------------

class PhaseRepo(_Repo):
    """Records where each phase stands. Whether a move is *allowed* is the workflow engine's job (S05)."""

    def _row(self, conn: sqlite3.Connection, project_id: str, phase_key: str) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM phase_runs WHERE project_id = ? AND phase_key = ?", (project_id, phase_key)
        ).fetchone()
        if row is None:
            raise NotFoundError(f"phase {phase_key!r} not found in project {project_id!r}")
        return row

    def ensure(self, project_id: str, phase_key: str, *, actor: str = "system") -> PhaseRun:
        check_actor(actor)
        phase_key = _text(phase_key, "phase_key")
        with self.db.write() as conn:
            _require_project(conn, project_id)
            existing = conn.execute(
                "SELECT * FROM phase_runs WHERE project_id = ? AND phase_key = ?", (project_id, phase_key)
            ).fetchone()
            if existing is not None:
                return _phase(existing)
            now = self._clock()
            conn.execute(
                "INSERT INTO phase_runs (project_id, phase_key, status, updated_at)"
                " VALUES (?, ?, 'not_started', ?)",
                (project_id, phase_key, now),
            )
            write_audit(
                conn, now, actor, "phase.created", "phase", phase_key, project_id=project_id,
            )
            return _phase(self._row(conn, project_id, phase_key))

    def get(self, project_id: str, phase_key: str) -> PhaseRun:
        with self.db.read() as conn:
            return _phase(self._row(conn, project_id, phase_key))

    def list(self, project_id: str) -> list[PhaseRun]:
        with self.db.read() as conn:
            rows = conn.execute(
                "SELECT * FROM phase_runs WHERE project_id = ? ORDER BY rowid", (project_id,)
            ).fetchall()
        return [_phase(r) for r in rows]

    @staticmethod
    def _check_move(current: str, wanted: str, phase_key: str) -> None:
        if wanted in PHASE_TRANSITIONS.get(current, ()) and current != "approved":
            return
        if current == "approved":
            hint = "use reopen() to change an approved phase"
        else:
            allowed = list(PHASE_TRANSITIONS.get(current, ()))
            hint = f"from '{current}' it can go to {allowed}" if allowed else f"'{current}' is final"
        raise IllegalTransition(f"phase '{phase_key}' cannot go from '{current}' to '{wanted}': {hint}")

    def set_status(
        self,
        project_id: str,
        phase_key: str,
        status: str,
        *,
        actor: str,
        guard: Guard | None = None,
    ) -> PhaseRun:
        """Move to not_started, running or awaiting_review, if the state machine allows it.

        Approval goes through record_decision and leaving 'approved' through reopen. `guard`, if
        given, runs inside the same transaction once the move is known to be legal and may raise to
        refuse it. That is how the workflow engine checks prerequisites without a gap for a race.
        """
        check_actor(actor)
        if status in ("approved", "rejected"):
            raise InvalidInput("approved and rejected are reached only through record_decision")
        if status not in PHASE_STATUSES:
            raise InvalidInput(f"status must be one of {PHASE_STATUSES}, got {status!r}")

        with self.db.write() as conn:
            before = self._row(conn, project_id, phase_key)
            self._check_move(before["status"], status, phase_key)
            if guard is not None:
                guard(conn, _phase(before))
            now = self._clock()
            if status == "running":
                # A fresh run, for example after a rejection: forget the previous decision.
                fields = dict(started_at=now, finished_at=None, decision=None, decided_by=None, feedback=None)
            elif status == "awaiting_review":
                fields = dict(finished_at=now)
            else:  # not_started
                fields = dict(started_at=None, finished_at=None, decision=None, decided_by=None, feedback=None)
            fields.update(status=status, updated_at=now)
            columns = ", ".join(f"{column} = ?" for column in fields)
            conn.execute(
                f"UPDATE phase_runs SET {columns} WHERE project_id = ? AND phase_key = ?",
                (*fields.values(), project_id, phase_key),
            )
            write_audit(
                conn, now, actor, "phase.status", "phase", phase_key, project_id=project_id,
                detail={"from": before["status"], "to": status},
            )
            return _phase(self._row(conn, project_id, phase_key))

    def record_decision(
        self,
        project_id: str,
        phase_key: str,
        decision: str,
        *,
        actor: str,
        feedback: str | None = None,
        guard: Guard | None = None,
        notes: Sequence[tuple[str | None, str, str]] = (),
        detail: dict[str, Any] | None = None,
    ) -> PhaseRun:
        """A person (or the system) approves or rejects a phase that is awaiting review.

        Agents never decide a gate, and a phase that is not awaiting review cannot be decided at all.
        `guard` runs inside the transaction before an approval is written and may raise to refuse it.
        `notes` are (artefact_id or None, memory kind, text) rows saved to project memory in the SAME
        transaction as a rejection, so a rejection can never exist without its notes or the reverse.
        `detail` is extra audit information about the decision (for example what was open at approval).
        """
        check_actor(actor)
        if actor.startswith("agent:"):
            raise InvalidInput("an agent cannot decide a gate; a person must")
        if decision not in DECISIONS:
            raise InvalidInput(f"decision must be one of {DECISIONS}, got {decision!r}")
        feedback = (feedback or "").strip() or None
        if decision == "reject" and feedback is None:
            raise InvalidInput("a rejection needs written feedback")
        notes = [tuple(n) for n in notes]
        if notes and decision != "reject":
            raise InvalidInput("notes can only be saved with a rejection")
        for _, kind, text in notes:
            if kind not in MEMORY_KINDS:
                raise InvalidInput(f"kind must be one of {MEMORY_KINDS}, got {kind!r}")
            _text(text, "note text")

        status = "approved" if decision == "approve" else "rejected"
        with self.db.write() as conn:
            before = self._row(conn, project_id, phase_key)
            self._check_move(before["status"], status, phase_key)
            if guard is not None and decision == "approve":
                guard(conn, _phase(before))
            now = self._clock()
            for artefact_id, _, _ in notes:
                if artefact_id is None:
                    continue
                _require_artefact(conn, project_id, artefact_id)
                where = conn.execute(
                    "SELECT phase_key FROM artefacts WHERE project_id = ? AND id = ?", (project_id, artefact_id)
                ).fetchone()["phase_key"]
                if where != phase_key:
                    raise InvalidInput(f"artefact {artefact_id!r} belongs to phase {where!r}, not {phase_key!r}")
            conn.execute(
                "UPDATE phase_runs SET status = ?, decision = ?, decided_by = ?, feedback = ?,"
                " finished_at = COALESCE(finished_at, ?), updated_at = ?"
                " WHERE project_id = ? AND phase_key = ?",
                (status, decision, actor, feedback, now, now, project_id, phase_key),
            )
            for artefact_id, kind, text in notes:
                _insert_memory(conn, self._clock(), project_id, kind, text.strip(), actor, phase_key, artefact_id)
            audit_detail = {"decision": decision, "feedback": feedback, **(detail or {})}
            if notes:
                audit_detail["notes"] = len(notes)
            write_audit(
                conn, now, actor, "phase.decided", "phase", phase_key, project_id=project_id, detail=audit_detail,
            )
            return _phase(self._row(conn, project_id, phase_key))

    def reopen(
        self, project_id: str, phase_key: str, *, actor: str, reason: str, guard: Guard | None = None
    ) -> PhaseRun:
        """Take an approved phase back to running. Needs a person and a written reason."""
        check_actor(actor)
        if not actor.startswith("human:"):
            raise InvalidInput("reopening an approved phase needs a person, not an agent or the system")
        reason = (reason or "").strip()
        if not reason:
            raise InvalidInput("reopening an approved phase needs a written reason")
        with self.db.write() as conn:
            before = self._row(conn, project_id, phase_key)
            if before["status"] != "approved":
                raise IllegalTransition(
                    f"phase '{phase_key}' is '{before['status']}'; only an approved phase can be reopened"
                )
            if guard is not None:
                guard(conn, _phase(before))
            now = self._clock()
            conn.execute(
                "UPDATE phase_runs SET status = 'running', started_at = ?, finished_at = NULL,"
                " decision = NULL, decided_by = NULL, feedback = NULL, updated_at = ?"
                " WHERE project_id = ? AND phase_key = ?",
                (now, now, project_id, phase_key),
            )
            write_audit(
                conn, now, actor, "phase.reopened", "phase", phase_key, project_id=project_id,
                detail={"reason": reason, "was_approved_by": before["decided_by"]},
            )
            return _phase(self._row(conn, project_id, phase_key))


# ---- artefacts and versions ------------------------------------------------

class ArtefactRepo(_Repo):
    # Set by the app at start-up. A version containing a high-confidence secret is refused whatever called the repository.
    # None means no backstop (a bare Store in a unit test); the app always sets one.
    backstop: Any = None

    def _refuse_secrets(self, body: str) -> None:
        if self.backstop is None:
            return
        from .guardrails.scan import BACKSTOP_RULES, SecretRefused, describe

        found = self.backstop.scan(body, only=BACKSTOP_RULES)   # BACKSTOP_RULES holds secret rules only
        if found:
            raise SecretRefused(
                f"this version was not saved: {describe(found[0])}" + (f" (and {len(found) - 1} more)" if len(found) > 1 else "")
            )

    def create(
        self,
        project_id: str,
        *,
        artefact_type: str,
        phase_key: str,
        title: str,
        actor: str,
        artefact_id: str | None = None,
        prefix: str | None = None,
    ) -> Artefact:
        """Give an explicit id, or a prefix such as 'REQ-F' to be allocated the next free number."""
        check_actor(actor)
        if (artefact_id is None) == (prefix is None):
            raise InvalidInput("give exactly one of artefact_id or prefix")
        if artefact_id is not None and not ID_RE.fullmatch(artefact_id):
            raise InvalidInput(f"artefact id {artefact_id!r} is not like 'REQ-F-012'")
        if prefix is not None and not PREFIX_RE.fullmatch(prefix):
            raise InvalidInput(f"prefix {prefix!r} is not like 'REQ-F'")
        artefact_type = _text(artefact_type, "artefact_type")
        phase_key = _text(phase_key, "phase_key")
        title = _text(title, "title")

        with self.db.write() as conn:  # the write lock makes allocation race-free
            _require_project(conn, project_id)
            if prefix is not None:
                artefact_id = f"{prefix}-{self._next_number(conn, project_id, prefix):03d}"
            elif conn.execute(
                "SELECT 1 FROM artefacts WHERE project_id = ? AND id = ?", (project_id, artefact_id)
            ).fetchone():
                raise ConflictError(f"artefact {artefact_id!r} already exists in project {project_id!r}")
            now = self._clock()
            conn.execute(
                "INSERT INTO artefacts (project_id, id, type, phase_key, title, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, artefact_id, artefact_type, phase_key, title, now),
            )
            write_audit(
                conn, now, actor, "artefact.created", "artefact", artefact_id, project_id=project_id,
                detail={"type": artefact_type, "phase_key": phase_key, "title": title},
            )
            return _artefact(
                conn.execute(
                    _ARTEFACT_SELECT + " WHERE a.project_id = ? AND a.id = ?", (project_id, artefact_id)
                ).fetchone()
            )

    @staticmethod
    def _next_number(conn: sqlite3.Connection, project_id: str, prefix: str) -> int:
        pattern = re.compile(re.escape(prefix) + r"-(\d+)")
        top = 0
        for row in conn.execute(
            "SELECT id FROM artefacts WHERE project_id = ? AND id LIKE ?", (project_id, prefix + "-%")
        ):
            match = pattern.fullmatch(row["id"])  # 'REQ' must not count 'REQ-F-012'
            if match:
                top = max(top, int(match.group(1)))
        return top + 1

    def get(self, project_id: str, artefact_id: str) -> Artefact:
        with self.db.read() as conn:
            row = conn.execute(
                _ARTEFACT_SELECT + " WHERE a.project_id = ? AND a.id = ?", (project_id, artefact_id)
            ).fetchone()
        if row is None:
            raise NotFoundError(f"artefact {artefact_id!r} not found in project {project_id!r}")
        return _artefact(row)

    def list(
        self, project_id: str, *, phase_key: str | None = None, artefact_type: str | None = None
    ) -> list[Artefact]:
        sql = _ARTEFACT_SELECT + " WHERE a.project_id = ?"
        args: list[Any] = [project_id]
        if phase_key is not None:
            sql += " AND a.phase_key = ?"
            args.append(phase_key)
        if artefact_type is not None:
            sql += " AND a.type = ?"
            args.append(artefact_type)
        with self.db.read() as conn:
            rows = conn.execute(sql + " ORDER BY a.rowid", args).fetchall()
        return [_artefact(r) for r in rows]

    def add_version(
        self,
        project_id: str,
        artefact_id: str,
        *,
        body: str,
        author: str,
        source_chunks: Iterable[str] = (),
        generation: Any = None,
        links: Iterable[tuple[str, str, str]] | None = None,
        guard: Callable[[sqlite3.Connection], None] | None = None,
    ) -> ArtefactVersion:
        """Append a new immutable version. The author is also the audit actor.

        `links` are (from_id, to_id, kind) triples this version declares. When given (even empty), they REPLACE
        the links this artefact declared before, in the same transaction; leave it out to touch no links.
        `guard` runs first inside the transaction and may raise to refuse the save.
        """
        _check_author(author)
        body = _text(body, "body")
        chunks = list(source_chunks)
        if not all(isinstance(c, str) and c for c in chunks):
            raise InvalidInput("source_chunks must be non-empty strings")
        generation_json = None if generation is None else _dump(generation, "generation")
        link_list = None if links is None else [tuple(link) for link in links]
        for from_id, to_id, kind in link_list or ():
            _check_link(from_id, to_id, kind)
        self._refuse_secrets(body)
        with self.db.write() as conn:
            if guard is not None:
                guard(conn)
            version = self._append_version(conn, project_id, artefact_id, body, author, chunks, generation_json)
            if link_list is not None:
                _sync_links(conn, self._clock, project_id, artefact_id, link_list, author, version.number)
            return version

    def _append_version(
        self, conn: sqlite3.Connection, project_id: str, artefact_id: str, body: str, author: str,
        chunks: list[str], generation_json: str | None,
    ) -> ArtefactVersion:
        """Write a version inside the caller's transaction, so it can commit together with other changes."""
        _require_artefact(conn, project_id, artefact_id)
        number = conn.execute(
            "SELECT COALESCE(MAX(number), 0) + 1 FROM artefact_versions"
            " WHERE project_id = ? AND artefact_id = ?",
            (project_id, artefact_id),
        ).fetchone()[0]
        now = self._clock()
        conn.execute(
            "INSERT INTO artefact_versions (project_id, artefact_id, number, body, author,"
            " source_chunks, created_at, generation) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, artefact_id, number, body, author, _dump(chunks, "source_chunks"), now, generation_json),
        )
        write_audit(
            conn, now, author, "artefact.version_added", "artefact", artefact_id,
            project_id=project_id, detail={"number": number},
        )
        return _version(self._version_row(conn, project_id, artefact_id, number))

    def create_and_add_version(
        self,
        project_id: str,
        *,
        artefact_type: str,
        phase_key: str,
        title: str,
        prefix: str,
        body: str,
        author: str,
        source_chunks: Iterable[str] = (),
        generation: Any = None,
        guard: Callable[[sqlite3.Connection], None] | None = None,
        links: Iterable[tuple[str, str, str]] | None = None,
    ) -> tuple[Artefact, ArtefactVersion]:
        """Find this project's artefact of this type, creating it if it does not exist, and add a version.

        One transaction: the lookup, the creation and the version commit together, so two simultaneous
        runs cannot create two artefacts, and a failure leaves neither a half-made artefact nor a
        version without its artefact. Used by the agent runtime, where 'one artefact per catalogue key'
        is a rule. `guard`, if given, runs first inside the same transaction and may raise to refuse the
        save: that is how a run is stopped from saving into a phase that stopped being open while the
        model was thinking. `links` are (from_id, to_id, kind) triples declared by this version; when given (even
        empty) they REPLACE the links this artefact declared before, in the same transaction, so a version and
        the links it declares appear together or not at all, and a link the new text dropped goes away.
        """
        _check_author(author)
        body = _text(body, "body")
        artefact_type = _text(artefact_type, "artefact_type")
        phase_key = _text(phase_key, "phase_key")
        title = _text(title, "title")
        if not PREFIX_RE.fullmatch(prefix):
            raise InvalidInput(f"prefix {prefix!r} is not like 'REQ-F'")
        chunks = list(source_chunks)
        if not all(isinstance(c, str) and c for c in chunks):
            raise InvalidInput("source_chunks must be non-empty strings")
        generation_json = None if generation is None else _dump(generation, "generation")
        link_list = None if links is None else [tuple(link) for link in links]
        for from_id, to_id, kind in link_list or ():
            _check_link(from_id, to_id, kind)
        self._refuse_secrets(body)
        with self.db.write() as conn:
            _require_project(conn, project_id)
            if guard is not None:
                guard(conn)
            row = conn.execute(
                _ARTEFACT_SELECT + " WHERE a.project_id = ? AND a.type = ? AND a.phase_key = ? ORDER BY a.rowid LIMIT 1",
                (project_id, artefact_type, phase_key),
            ).fetchone()
            if row is None:
                artefact_id = f"{prefix}-{self._next_number(conn, project_id, prefix):03d}"
                now = self._clock()
                conn.execute(
                    "INSERT INTO artefacts (project_id, id, type, phase_key, title, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (project_id, artefact_id, artefact_type, phase_key, title, now),
                )
                write_audit(
                    conn, now, author, "artefact.created", "artefact", artefact_id, project_id=project_id,
                    detail={"type": artefact_type, "phase_key": phase_key, "title": title},
                )
            else:
                artefact_id = row["id"]
            version = self._append_version(conn, project_id, artefact_id, body, author, chunks, generation_json)
            if link_list is not None:
                _sync_links(conn, self._clock, project_id, artefact_id, link_list, author, version.number)
            artefact = _artefact(conn.execute(
                _ARTEFACT_SELECT + " WHERE a.project_id = ? AND a.id = ?", (project_id, artefact_id)
            ).fetchone())
            return artefact, version

    @staticmethod
    def _version_row(
        conn: sqlite3.Connection, project_id: str, artefact_id: str, number: int | None
    ) -> sqlite3.Row:
        if number is None:
            row = conn.execute(
                "SELECT * FROM artefact_versions WHERE project_id = ? AND artefact_id = ?"
                " ORDER BY number DESC LIMIT 1",
                (project_id, artefact_id),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM artefact_versions WHERE project_id = ? AND artefact_id = ? AND number = ?",
                (project_id, artefact_id, number),
            ).fetchone()
        if row is None:
            which = "any version" if number is None else f"version {number}"
            raise NotFoundError(f"{which} of artefact {artefact_id!r} not found in project {project_id!r}")
        return row

    def get_version(self, project_id: str, artefact_id: str, number: int | None = None) -> ArtefactVersion:
        """One version, or the latest when number is omitted."""
        with self.db.read() as conn:
            return _version(self._version_row(conn, project_id, artefact_id, number))

    def versions(self, project_id: str, artefact_id: str) -> list[ArtefactVersion]:
        with self.db.read() as conn:
            _require_artefact(conn, project_id, artefact_id)
            rows = conn.execute(
                "SELECT * FROM artefact_versions WHERE project_id = ? AND artefact_id = ? ORDER BY number",
                (project_id, artefact_id),
            ).fetchall()
        return [_version(r) for r in rows]

    def set_review_findings(
        self, project_id: str, artefact_id: str, number: int, findings: Any, *, actor: str
    ) -> ArtefactVersion:
        """Attach reviewer findings. The only field of a version that may change after it is written."""
        check_actor(actor)
        findings_json = _dump(findings, "findings")
        with self.db.write() as conn:
            before = self._version_row(conn, project_id, artefact_id, number)
            now = self._clock()
            conn.execute(
                "UPDATE artefact_versions SET review_findings = ?"
                " WHERE project_id = ? AND artefact_id = ? AND number = ?",
                (findings_json, project_id, artefact_id, number),
            )
            write_audit(
                conn, now, actor, "artefact.reviewed", "artefact", artefact_id, project_id=project_id,
                detail={"number": number, "replaced": before["review_findings"] is not None},
            )
            return _version(self._version_row(conn, project_id, artefact_id, number))


def _check_link(from_id: str, to_id: str, kind: str) -> None:
    for what, value in (("from_id", from_id), ("to_id", to_id)):
        if not isinstance(value, str) or not ID_RE.fullmatch(value):
            raise InvalidInput(f"{what} {value!r} is not like 'REQ-F-012'")
    if from_id == to_id:
        raise InvalidInput("a link cannot point at itself")
    if kind not in LINK_KINDS:
        raise InvalidInput(f"kind must be one of {LINK_KINDS}, got {kind!r}")


def _sync_links(
    conn: sqlite3.Connection, clock: Callable[[], str], project_id: str, artefact_id: str,
    wanted: Sequence[tuple[str, str, str]], actor: str, version: int,
) -> None:
    """Make the links declared by `artefact_id` exactly the links its newest version declares.

    A link the new version no longer states is deleted (and the deletion audited, because the audit log is
    append-only and keeps the history). A link it still states is left alone, and a new one is added. Links
    declared by other artefacts, or added by hand with no declaring artefact, are never touched.
    """
    keep = set(wanted)
    existing = conn.execute(
        "SELECT id, from_id, to_id, kind FROM links WHERE project_id = ? AND declared_in = ?",
        (project_id, artefact_id),
    ).fetchall()
    for row in existing:
        if (row["from_id"], row["to_id"], row["kind"]) in keep:
            continue
        conn.execute("DELETE FROM links WHERE id = ?", (row["id"],))
        write_audit(
            conn, clock(), actor, "link.removed", "link", f"{row['from_id']}>{row['kind']}>{row['to_id']}",
            project_id=project_id, detail={"declared_in": artefact_id, "replaced_by_version": version},
        )
    for from_id, to_id, kind in dict.fromkeys(wanted):
        _insert_link(conn, project_id, from_id, to_id, kind, artefact_id, actor, clock())


def _insert_link(
    conn: sqlite3.Connection, project_id: str, from_id: str, to_id: str, kind: str, declared_in: str | None,
    actor: str, now: str,
) -> tuple[Link, bool]:
    """Write one link inside the caller's transaction. (link, created); a repeat returns the first link."""
    existing = conn.execute(
        "SELECT * FROM links WHERE project_id = ? AND from_id = ? AND to_id = ? AND kind = ?",
        (project_id, from_id, to_id, kind),
    ).fetchone()
    if existing is not None:
        return _link(existing), False
    cursor = conn.execute(
        "INSERT INTO links (project_id, from_id, to_id, kind, declared_in, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (project_id, from_id, to_id, kind, declared_in, now),
    )
    write_audit(
        conn, now, actor, "link.added", "link", f"{from_id}>{kind}>{to_id}", project_id=project_id,
        detail={"declared_in": declared_in},
    )
    return _link(conn.execute("SELECT * FROM links WHERE id = ?", (cursor.lastrowid,)).fetchone()), True


# ---- traceability links ----------------------------------------------------

class LinkRepo(_Repo):
    def add(
        self,
        project_id: str,
        from_id: str,
        to_id: str,
        kind: str,
        *,
        actor: str,
        declared_in: str | None = None,
    ) -> Link:
        """Record that from_id relates to to_id. Adding the same link twice returns the first."""
        check_actor(actor)
        _check_link(from_id, to_id, kind)

        with self.db.write() as conn:
            _require_project(conn, project_id)
            if declared_in is not None:
                _require_artefact(conn, project_id, declared_in)
            link, _ = _insert_link(conn, project_id, from_id, to_id, kind, declared_in, actor, self._clock())
            return link

    def list(
        self,
        project_id: str,
        *,
        from_id: str | None = None,
        to_id: str | None = None,
        kind: str | None = None,
    ) -> list[Link]:
        sql = "SELECT * FROM links WHERE project_id = ?"
        args: list[Any] = [project_id]
        for column, value in (("from_id", from_id), ("to_id", to_id), ("kind", kind)):
            if value is not None:
                sql += f" AND {column} = ?"
                args.append(value)
        with self.db.read() as conn:
            rows = conn.execute(sql + " ORDER BY id", args).fetchall()
        return [_link(r) for r in rows]


# ---- traces ----------------------------------------------------------------

class TraceRepo(_Repo):
    """One row per model call. Traces are a log, not state, so they do not write audit rows."""

    def record(
        self,
        *,
        agent: str,
        slot: str,
        requested_model: str,
        served_model: str,
        status: str,
        project_id: str | None = None,
        run_id: str | None = None,
        phase_key: str | None = None,
        fallback_used: bool = False,
        error: str | None = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        latency_ms: int = 0,
        cost_usd: float | None = None,
        call_id: str | None = None,
        attempt: int = 1,
    ) -> Trace:
        """cost_usd=None means the price is unknown. It is stored as NULL and never as zero.

        One row per attempt: call_id groups the attempts of one logical model call.
        """
        agent = _text(agent, "agent")
        slot = _text(slot, "slot")
        requested_model = _text(requested_model, "requested_model")
        served_model = _text(served_model, "served_model")
        if status not in TRACE_STATUSES:
            raise InvalidInput(f"status must be one of {TRACE_STATUSES}, got {status!r}")
        tokens_in = _count(tokens_in, "tokens_in")
        tokens_out = _count(tokens_out, "tokens_out")
        latency_ms = _count(latency_ms, "latency_ms")
        if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
            raise InvalidInput("attempt must be a whole number, 1 or more")
        if cost_usd is not None:
            if isinstance(cost_usd, bool) or not isinstance(cost_usd, (int, float)):
                raise InvalidInput("cost_usd must be a number or None")
            if not math.isfinite(cost_usd) or cost_usd < 0:
                raise InvalidInput("cost_usd must be zero or more, or None when unknown")
            cost_usd = float(cost_usd)

        with self.db.write() as conn:
            if project_id is not None:
                _require_project(conn, project_id)
            cursor = conn.execute(
                "INSERT INTO traces (project_id, run_id, agent, phase_key, slot, requested_model,"
                " served_model, fallback_used, status, error, tokens_in, tokens_out, latency_ms,"
                " cost_usd, created_at, call_id, attempt)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    project_id, run_id, agent, phase_key, slot, requested_model, served_model,
                    1 if fallback_used else 0, status, error, tokens_in, tokens_out, latency_ms,
                    cost_usd, self._clock(), call_id, attempt,
                ),
            )
            return _trace(conn.execute("SELECT * FROM traces WHERE id = ?", (cursor.lastrowid,)).fetchone())

    def list(
        self, project_id: str | None = None, *, agent: str | None = None, phase_key: str | None = None
    ) -> list[Trace]:
        sql = "SELECT * FROM traces WHERE 1 = 1"
        args: list[Any] = []
        for column, value in (("project_id", project_id), ("agent", agent), ("phase_key", phase_key)):
            if value is not None:
                sql += f" AND {column} = ?"
                args.append(value)
        with self.db.read() as conn:
            rows = conn.execute(sql + " ORDER BY id", args).fetchall()
        return [_trace(r) for r in rows]

    def rollup(self, project_id: str, by: str) -> list[RollupRow]:
        """Totals per model, phase, agent or slot.

        cost_usd is None when no call in the group had a price. unpriced_calls counts successful
        calls with an unknown cost; failed calls are not counted there because they cost nothing.
        """
        column = _ROLLUP_COLUMNS.get(by)
        if column is None:
            raise InvalidInput(f"by must be one of {sorted(_ROLLUP_COLUMNS)}, got {by!r}")
        with self.db.read() as conn:
            _require_project(conn, project_id)
            rows = conn.execute(
                f"SELECT {column} AS grp, COUNT(*) AS calls,"  # column comes from the fixed map above
                " SUM(status = 'error') AS errors, SUM(fallback_used) AS fallbacks,"
                " SUM(tokens_in) AS tokens_in, SUM(tokens_out) AS tokens_out,"
                " SUM(cost_usd) AS cost_usd,"
                " SUM(status = 'ok' AND cost_usd IS NULL) AS unpriced_calls"
                f" FROM traces WHERE project_id = ? GROUP BY {column} ORDER BY {column}",
                (project_id,),
            ).fetchall()
        return [
            RollupRow(
                key=r["grp"],
                calls=r["calls"],
                errors=r["errors"],
                fallbacks=r["fallbacks"],
                tokens_in=r["tokens_in"],
                tokens_out=r["tokens_out"],
                cost_usd=r["cost_usd"],
                unpriced_calls=r["unpriced_calls"],
            )
            for r in rows
        ]


# ---- audit -----------------------------------------------------------------

class AuditRepo(_Repo):
    """Read access plus a public append for layers that audit things this module does not own."""

    def append(
        self,
        *,
        actor: str,
        action: str,
        target_type: str,
        target_id: str,
        project_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> AuditEvent:
        check_actor(actor)
        action = _text(action, "action")
        target_type = _text(target_type, "target_type")
        target_id = _text(target_id, "target_id")
        with self.db.write() as conn:
            row_id = write_audit(
                conn, self._clock(), actor, action, target_type, target_id,
                project_id=project_id, detail=detail,
            )
            return _audit_event(conn.execute("SELECT * FROM audit WHERE id = ?", (row_id,)).fetchone())

    def list(
        self,
        project_id: str | None = None,
        *,
        actor: str | None = None,
        action: str | None = None,
        target_id: str | None = None,
        limit: int | None = None,
    ) -> list[AuditEvent]:
        sql = "SELECT * FROM audit WHERE 1 = 1"
        args: list[Any] = []
        for column, value in (
            ("project_id", project_id), ("actor", actor), ("action", action), ("target_id", target_id),
        ):
            if value is not None:
                sql += f" AND {column} = ?"
                args.append(value)
        sql += " ORDER BY id"
        if limit is not None:
            sql += " LIMIT ?"
            args.append(_count(limit, "limit"))
        with self.db.read() as conn:
            rows = conn.execute(sql, args).fetchall()
        return [_audit_event(r) for r in rows]


# ---- project memory --------------------------------------------------------

def _insert_memory(
    conn: sqlite3.Connection, now: str, project_id: str, kind: str, text: str, actor: str,
    phase_key: str | None, artefact_id: str | None,
) -> MemoryEntry:
    """Write one memory row and its audit row inside the caller's transaction."""
    cursor = conn.execute(
        "INSERT INTO memory (project_id, kind, phase_key, artefact_id, text, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (project_id, kind, phase_key, artefact_id, text, now),
    )
    write_audit(
        conn, now, actor, "memory.added", "memory", str(cursor.lastrowid), project_id=project_id,
        detail={"kind": kind, "phase_key": phase_key, "artefact_id": artefact_id},
    )
    return _memory(conn.execute("SELECT * FROM memory WHERE id = ?", (cursor.lastrowid,)).fetchone())


class MemoryRepo(_Repo):
    def add(
        self,
        project_id: str,
        kind: str,
        text: str,
        *,
        actor: str,
        phase_key: str | None = None,
        artefact_id: str | None = None,
    ) -> MemoryEntry:
        check_actor(actor)
        if kind not in MEMORY_KINDS:
            raise InvalidInput(f"kind must be one of {MEMORY_KINDS}, got {kind!r}")
        text = _text(text, "text")
        with self.db.write() as conn:
            _require_project(conn, project_id)
            if artefact_id is not None:
                _require_artefact(conn, project_id, artefact_id)
            return _insert_memory(conn, self._clock(), project_id, kind, text, actor, phase_key, artefact_id)

    def list(
        self,
        project_id: str,
        *,
        kind: str | None = None,
        phase_key: str | None = None,
        artefact_id: str | None = None,
    ) -> list[MemoryEntry]:
        sql = "SELECT * FROM memory WHERE project_id = ?"
        args: list[Any] = [project_id]
        for column, value in (("kind", kind), ("phase_key", phase_key), ("artefact_id", artefact_id)):
            if value is not None:
                sql += f" AND {column} = ?"
                args.append(value)
        with self.db.read() as conn:
            rows = conn.execute(sql + " ORDER BY id", args).fetchall()
        return [_memory(r) for r in rows]


# ---- runs and their events -----------------------------------------------

RUN_STATUSES = ("running", "finished", "stopped", "failed", "interrupted")
STOP_REASONS = ("budget", "time", "cancelled")
MAX_EVENT_BYTES = 20_000


def _run(r: sqlite3.Row) -> RunRecord:
    totals = r["totals"]
    return RunRecord(
        id=r["id"], project_id=r["project_id"], phase_key=r["phase_key"], status=r["status"],
        stop_reason=r["stop_reason"], started_at=r["started_at"], finished_at=r["finished_at"],
        totals=None if totals is None else json.loads(totals),
    )


def _run_event(r: sqlite3.Row) -> RunEvent:
    return RunEvent(
        id=r["id"], project_id=r["project_id"], run_id=r["run_id"], at=r["at"], type=r["type"], data=json.loads(r["data"]),
    )


class RunRepo(_Repo):
    """One row per run of a phase. A run is a record of what happened; the artefacts it made are the real output."""

    def start(self, project_id: str, phase_key: str, *, run_id: str | None = None) -> RunRecord:
        phase_key = _text(phase_key, "phase_key")
        run_id = run_id or self._ids()
        with self.db.write() as conn:
            _require_project(conn, project_id)
            conn.execute(
                "INSERT INTO runs (id, project_id, phase_key, status, started_at) VALUES (?, ?, ?, 'running', ?)",
                (run_id, project_id, phase_key, self._clock()),
            )
            return _run(conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone())

    def end(self, run_id: str, status: str, *, stop_reason: str | None = None, totals: Any = None) -> RunRecord:
        """Close a running run. A run that has already ended cannot be ended again."""
        if status not in RUN_STATUSES or status == "running":
            raise InvalidInput(f"an ended run's status must be one of {RUN_STATUSES[1:]}, got {status!r}")
        if stop_reason is not None and stop_reason not in STOP_REASONS:
            raise InvalidInput(f"stop_reason must be one of {STOP_REASONS}, got {stop_reason!r}")
        totals_json = None if totals is None else _dump(totals, "totals")
        with self.db.write() as conn:
            row = conn.execute("SELECT status FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row is None:
                raise NotFoundError(f"run {run_id!r} not found")
            if row["status"] != "running":
                raise ConflictError(f"run {run_id!r} has already ended ({row['status']})")
            conn.execute(
                "UPDATE runs SET status = ?, stop_reason = ?, finished_at = ?, totals = ? WHERE id = ?",
                (status, stop_reason, self._clock(), totals_json, run_id),
            )
            return _run(conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone())

    def get(self, project_id: str, run_id: str) -> RunRecord:
        with self.db.read() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id = ? AND project_id = ?", (run_id, project_id)).fetchone()
        if row is None:
            raise NotFoundError(f"run {run_id!r} not found in project {project_id!r}")
        return _run(row)

    def list(self, project_id: str, *, phase_key: str | None = None, status: str | None = None) -> list[RunRecord]:
        sql, args = "SELECT * FROM runs WHERE project_id = ?", [project_id]
        for column, value in (("phase_key", phase_key), ("status", status)):
            if value is not None:
                sql += f" AND {column} = ?"
                args.append(value)
        with self.db.read() as conn:
            rows = conn.execute(sql + " ORDER BY started_at, rowid", args).fetchall()
        return [_run(r) for r in rows]

    def interrupt_unfinished(self) -> int:
        """At start-up: every run still marked running belongs to a process that no longer exists. Returns how many."""
        with self.db.write() as conn:
            rows = conn.execute("SELECT id, project_id FROM runs WHERE status = 'running'").fetchall()
            now = self._clock()
            for row in rows:
                conn.execute(
                    "UPDATE runs SET status = 'interrupted', finished_at = ?, totals = ? WHERE id = ?",
                    (now, _dump({"note": "the backend stopped while this run was in progress"}, "totals"), row["id"]),
                )
                _insert_run_event(
                    conn, now, row["project_id"], row["id"], "run.stopped",
                    {"status": "interrupted", "reason": "the backend stopped while this run was in progress"},
                )
            return len(rows)


def _insert_run_event(conn: sqlite3.Connection, at: str, project_id: str, run_id: str, type_: str, data: Any) -> int:
    payload = _dump(data, "event data")
    if len(payload.encode("utf-8")) > MAX_EVENT_BYTES:
        raise InvalidInput(f"an event is limited to {MAX_EVENT_BYTES} bytes")
    cursor = conn.execute(
        "INSERT INTO run_events (project_id, run_id, at, type, data) VALUES (?, ?, ?, ?, ?)",
        (project_id, run_id, at, type_, payload),
    )
    return cursor.lastrowid


class RunEventRepo(_Repo):
    """The append-only log a screen reads to catch up. Events carry IDs, names, counts and costs: never text."""

    def append(self, project_id: str, run_id: str, type_: str, data: Any = None) -> RunEvent:
        type_ = _text(type_, "type")
        with self.db.write() as conn:
            row = conn.execute("SELECT project_id FROM runs WHERE id = ?", (run_id,)).fetchone()
            if row is None or row["project_id"] != project_id:
                raise NotFoundError(f"run {run_id!r} not found in project {project_id!r}")
            event_id = _insert_run_event(conn, self._clock(), project_id, run_id, type_, data if data is not None else {})
            return _run_event(conn.execute("SELECT * FROM run_events WHERE id = ?", (event_id,)).fetchone())

    def list(
        self, project_id: str, *, after: int = 0, run_id: str | None = None, limit: int = 1000
    ) -> list[RunEvent]:
        """Events with an id greater than `after`, oldest first. This is what a late or reconnecting watcher reads."""
        after = _count(after, "after")
        limit = _count(limit, "limit")
        sql, args = "SELECT * FROM run_events WHERE project_id = ? AND id > ?", [project_id, after]
        if run_id is not None:
            sql += " AND run_id = ?"
            args.append(run_id)
        with self.db.read() as conn:
            _require_project(conn, project_id)
            rows = conn.execute(sql + " ORDER BY id LIMIT ?", [*args, limit]).fetchall()
        return [_run_event(r) for r in rows]

    def last_id(self, project_id: str) -> int:
        with self.db.read() as conn:
            return conn.execute("SELECT COALESCE(MAX(id), 0) FROM run_events WHERE project_id = ?", (project_id,)).fetchone()[0]


# ---- build rounds ----------------------------------------------------------------------------------------------------------

MAX_ROUND_FAILURES = 10
MAX_FAILURE_TEXT = 400
ROUND_OUTCOMES = ("passed", "failed", "no_tests", "blocked", "stopped", "invalid", "not_converging", "cap_reached")


def _build_round(r: sqlite3.Row) -> BuildRound:
    return BuildRound(
        id=r["id"], project_id=r["project_id"], run_id=r["run_id"], loop_id=r["loop_id"], round=r["round"], artefact=r["artefact"],
        version=r["version"], outcome=r["outcome"], passed=r["passed"], failed=r["failed"], errors=r["errors"], skipped=r["skipped"],
        fingerprint=r["fingerprint"], failures=tuple(json.loads(r["failures"])), seconds=r["seconds"], at=r["at"],
    )


class BuildRoundRepo(_Repo):
    """The permanent record of the fix loop, one row per round. Append-only: a round is a fact. Never file contents, never a full output."""

    def append(
        self, project_id: str, loop_id: str, round_: int, *, artefact: str, outcome: str, version: int | None = None, run_id: str | None = None,
        passed: int = 0, failed: int = 0, errors: int = 0, skipped: int = 0, fingerprint: str = "", failures: Sequence[Mapping[str, Any]] = (),
        seconds: float = 0.0,
    ) -> BuildRound:
        loop_id = _text(loop_id, "loop_id")
        if isinstance(round_, bool) or not isinstance(round_, int) or round_ < 1:
            raise InvalidInput("round must be a whole number, one or more")
        if outcome not in ROUND_OUTCOMES:
            raise InvalidInput(f"outcome must be one of {ROUND_OUTCOMES}, got {outcome!r}")
        if version is not None:
            version = _count(version, "version")
        counts = [_count(n, name) for n, name in ((passed, "passed"), (failed, "failed"), (errors, "errors"), (skipped, "skipped"))]
        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds < 0:
            raise InvalidInput("seconds must be a number, zero or more")
        kept = [
            {"test": str(f.get("test", ""))[:MAX_FAILURE_TEXT], "kind": str(f.get("kind", ""))[:40], "message": str(f.get("message", ""))[:MAX_FAILURE_TEXT]}
            for f in list(failures)[:MAX_ROUND_FAILURES]
        ]
        with self.db.write() as conn:
            _require_project(conn, project_id)
            cursor = conn.execute(
                "INSERT INTO build_rounds (project_id, run_id, loop_id, round, artefact, version, outcome, passed, failed, errors, skipped,"
                " fingerprint, failures, seconds, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, run_id, loop_id, round_, artefact, version, outcome, *counts, str(fingerprint)[:200], _dump(kept, "failures"), float(seconds), self._clock()),
            )
            return _build_round(conn.execute("SELECT * FROM build_rounds WHERE id = ?", (cursor.lastrowid,)).fetchone())

    def list(self, project_id: str, *, loop_id: str | None = None, limit: int = 1000) -> list[BuildRound]:
        """Rounds oldest first, for a project or one loop."""
        limit = _count(limit, "limit")
        sql, args = "SELECT * FROM build_rounds WHERE project_id = ?", [project_id]
        if loop_id is not None:
            sql += " AND loop_id = ?"
            args.append(loop_id)
        with self.db.read() as conn:
            _require_project(conn, project_id)
            rows = conn.execute(sql + " ORDER BY id LIMIT ?", [*args, limit]).fetchall()
        return [_build_round(r) for r in rows]


# ---- build verify ----------------------------------------------------------

MAX_VERIFY_MATCHES = 5000
VERIFY_STATES = ("found", "differences", "possible", "not_found", "weak", "extra")


def _verify_run(r: sqlite3.Row) -> VerifyRun:
    return VerifyRun(id=r["id"], project_id=r["project_id"], backend_path=r["backend_path"], frontend_path=r["frontend_path"], actor=r["actor"], design=json.loads(r["design"]),
                     counts=json.loads(r["counts"]), notes=tuple(json.loads(r["notes"])), at=r["at"])


def _verify_match(r: sqlite3.Row) -> VerifyMatch:
    return VerifyMatch(id=r["id"], run_id=r["run_id"], designed=r["designed"], area=r["area"], state=r["state"], step=r["step"], score=r["score"], built=r["built"], file=r["file"],
                       line=r["line"], differences=tuple(json.loads(r["differences"])), note=r["note"])


class VerifyRepo(_Repo):
    """The permanent record of every Build Verify run. Append-only: a run is a fact about a folder at a moment."""

    def add_run(self, project_id: str, *, backend_path: str, frontend_path: str | None, actor: str, design: Mapping[str, int], counts: Sequence[Mapping[str, Any]],
                notes: Sequence[str], matches: Sequence[Mapping[str, Any]]) -> VerifyRun:
        backend_path = _text(backend_path, "backend_path")
        if frontend_path is not None and not str(frontend_path).strip():
            frontend_path = None
        if len(matches) > MAX_VERIFY_MATCHES:
            raise InvalidInput(f"a run holds at most {MAX_VERIFY_MATCHES} matches")
        rows = []
        for m in matches:
            if m.get("state") not in VERIFY_STATES:
                raise InvalidInput(f"state must be one of {VERIFY_STATES}, got {m.get('state')!r}")
            rows.append((m.get("designed"), str(m["area"])[:20], m["state"], str(m.get("step", ""))[:20], float(m.get("score", 0)), str(m.get("built", ""))[:300], str(m.get("file", ""))[:400],
                         _count(int(m.get("line", 0)), "line"), _dump(list(m.get("differences", ()))[:20], "differences"), str(m.get("note", ""))[:500]))
        with self.db.write() as conn:
            _require_project(conn, project_id)
            cursor = conn.execute(
                "INSERT INTO verify_runs (project_id, backend_path, frontend_path, actor, design, counts, notes, at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (project_id, backend_path[:1000], None if frontend_path is None else str(frontend_path)[:1000], _text(actor, "actor"), _dump(dict(design), "design"),
                 _dump(list(counts), "counts"), _dump(list(notes)[:50], "notes"), self._clock()),
            )
            run_id = cursor.lastrowid
            conn.executemany(
                "INSERT INTO verify_matches (run_id, designed, area, state, step, score, built, file, line, differences, note) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [(run_id, *row) for row in rows],
            )
            return _verify_run(conn.execute("SELECT * FROM verify_runs WHERE id = ?", (run_id,)).fetchone())

    def runs(self, project_id: str, *, limit: int = 100) -> list[VerifyRun]:
        """Runs, newest first."""
        limit = _count(limit, "limit")
        with self.db.read() as conn:
            _require_project(conn, project_id)
            rows = conn.execute("SELECT * FROM verify_runs WHERE project_id = ? ORDER BY id DESC LIMIT ?", (project_id, limit)).fetchall()
        return [_verify_run(r) for r in rows]

    def run(self, project_id: str, run_id: int) -> VerifyRun:
        with self.db.read() as conn:
            _require_project(conn, project_id)
            row = conn.execute("SELECT * FROM verify_runs WHERE project_id = ? AND id = ?", (project_id, run_id)).fetchone()
        if row is None:
            raise NotFoundError(f"verify run {run_id!r} not found in this project")
        return _verify_run(row)

    def matches(self, project_id: str, run_id: int) -> list[VerifyMatch]:
        self.run(project_id, run_id)
        with self.db.read() as conn:
            rows = conn.execute("SELECT * FROM verify_matches WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
        return [_verify_match(r) for r in rows]


# ---- the store -------------------------------------------------------------

class Store:
    """All repositories over one database. The clock and id factory can be replaced in tests."""

    def __init__(
        self,
        db: Database,
        *,
        clock: Callable[[], str] = utc_now,
        id_factory: Callable[[], str] = new_id,
        limits: Any = None,
    ):
        self.db = db
        db.migrate()
        self.projects = ProjectRepo(db, clock, id_factory)
        self.phases = PhaseRepo(db, clock, id_factory)
        self.artefacts = ArtefactRepo(db, clock, id_factory)
        self.links = LinkRepo(db, clock, id_factory)
        self.traces = TraceRepo(db, clock, id_factory)
        self.audit = AuditRepo(db, clock, id_factory)
        self.memory = MemoryRepo(db, clock, id_factory)
        self.runs = RunRepo(db, clock, id_factory)
        self.run_events = RunEventRepo(db, clock, id_factory)
        self.build_rounds = BuildRoundRepo(db, clock, id_factory)
        self.verify = VerifyRepo(db, clock, id_factory)
        # Imported here, not at the top: the context store builds on this module's helpers.
        from .context.store import ContextStore

        self.context = ContextStore(db, clock, id_factory, limits)

    @classmethod
    def open(cls, path: Any, **kwargs: Any) -> "Store":
        return cls(Database(path), **kwargs)
