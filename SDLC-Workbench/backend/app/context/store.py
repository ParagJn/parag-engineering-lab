"""The context store: documents, approved artefacts and project memory, searchable with citable source IDs.

Everything is per project. Every query filters on project_id inside the SQL, including the full-text
match, so one project's text can never be returned for another project's question.
"""
from __future__ import annotations

import hashlib
import logging
import re
import sqlite3
from dataclasses import replace
from typing import Any, Callable, Iterable, Sequence

from ..db import Database
from ..models import ConflictError, InvalidInput, NotFoundError
from ..repos import _Repo, _require_project, check_actor, write_audit
from .chunking import Chunk, chunk_sections, sections_from_markdown
from .extract import clean_filename, extract
from .query import build_fts_query, query_words
from .types import SOURCE_KINDS, DocumentInfo, DocumentRefused, Hit, Limits, ReingestResult

log = logging.getLogger(__name__)

MAX_SEARCH_LIMIT = 50

_DOC_ID = re.compile(r"DOC-\d{3,}#[1-9]\d*")
_ARTEFACT_ID = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3,}@v[1-9]\d*#[1-9]\d*")
_MEMORY_ID = re.compile(r"MEM-\d{3,}")


def valid_source_id(source_id: Any) -> bool:
    return isinstance(source_id, str) and any(
        p.fullmatch(source_id) for p in (_DOC_ID, _ARTEFACT_ID, _MEMORY_ID)
    )


def _citation(source_id: str, title: str, heading: str, page: int | None) -> str:
    text = f"[{source_id}] {title}"
    if heading and heading != title:
        text += f" > {heading}"
    if page:
        text += f", page {page}"
    return text


def _hit(
    row: sqlite3.Row, *, score: float | None = None, relevance: float | None = None, coverage: float | None = None
) -> Hit:
    return Hit(
        source_id=row["source_id"],
        kind=row["kind"],
        title=row["title"],
        heading_path=row["heading_path"],
        text=row["text"],
        score=score,
        relevance=relevance,
        coverage=coverage,
        phase_key=row["phase_key"],
        artefact_id=row["artefact_id"],
        page=row["page"],
        citation=_citation(row["source_id"], row["title"], row["heading_path"], row["page"]),
    )


def _counts(findings: Sequence[Any]) -> dict[str, int]:
    """Rule names and how many times each fired: the only thing about a finding that is audited."""
    out: dict[str, int] = {}
    for f in findings:
        out[f.rule] = out.get(f.rule, 0) + 1
    return dict(sorted(out.items()))


def _info(row: sqlite3.Row, already_added: bool = False) -> DocumentInfo:
    return DocumentInfo(
        number=row["number"], filename=row["filename"], kind=row["kind"], sha256=row["sha256"],
        size_bytes=row["size_bytes"], chars=row["chars"], chunk_count=row["chunk_count"],
        added_by=row["added_by"], created_at=row["created_at"], removed_at=row["removed_at"],
        already_added=already_added,
    )


class ContextStore(_Repo):
    def __init__(
        self, db: Database, clock: Callable[[], str], ids: Callable[[], str], limits: Limits | None = None
    ):
        super().__init__(db, clock, ids)
        self.limits = limits or Limits()
        self.scanner: Any = None   # set by the app; a bare store in a unit test scans nothing

    # ---- documents -------------------------------------------------------------------

    def add_document(self, project_id: str, filename: str, data: bytes, *, actor: str) -> DocumentInfo:
        """Extract, chunk and index a file. The same bytes added twice return the existing document."""
        check_actor(actor)
        extracted, chunks, digest = self._prepare(filename, data)  # CPU work, done before taking the lock
        name = clean_filename(filename)
        findings = self._scan(extracted)
        with self.db.write() as conn:
            _require_project(conn, project_id)
            existing = self._live_by_hash(conn, project_id, digest)
            if existing is not None:
                return replace(_info(existing, already_added=True), findings=findings)
            return replace(self._insert_document(conn, project_id, name, extracted.kind, digest, len(data),
                                                  extracted.chars, chunks, actor, findings), findings=findings)

    def replace_document(
        self, project_id: str, number: int, filename: str, data: bytes, *, actor: str
    ) -> DocumentInfo:
        """Swap a document for a new version. The replacement gets a NEW number, so an old citation
        resolves to nothing instead of silently pointing at different text."""
        check_actor(actor)
        extracted, chunks, digest = self._prepare(filename, data)
        name = clean_filename(filename)
        findings = self._scan(extracted)
        with self.db.write() as conn:
            _require_project(conn, project_id)
            old = self._live_by_number(conn, project_id, number)
            if old["sha256"] == digest:
                return replace(_info(old, already_added=True), findings=findings)  # identical bytes: nothing to replace
            self._delete_document(conn, project_id, old, actor, action="document.replaced")
            existing = self._live_by_hash(conn, project_id, digest)
            if existing is not None:
                return replace(_info(existing, already_added=True), findings=findings)
            return replace(self._insert_document(conn, project_id, name, extracted.kind, digest, len(data),
                                                  extracted.chars, chunks, actor, findings), findings=findings)

    def remove_document(self, project_id: str, number: int, *, actor: str) -> None:
        check_actor(actor)
        with self.db.write() as conn:
            _require_project(conn, project_id)
            row = self._live_by_number(conn, project_id, number)
            self._delete_document(conn, project_id, row, actor, action="document.removed")

    def list_documents(self, project_id: str, *, include_removed: bool = False) -> list[DocumentInfo]:
        sql = "SELECT * FROM context_documents WHERE project_id = ?"
        if not include_removed:
            sql += " AND removed_at IS NULL"
        with self.db.read() as conn:
            _require_project(conn, project_id)
            rows = conn.execute(sql + " ORDER BY number", (project_id,)).fetchall()
        return [_info(r) for r in rows]

    def _scan(self, extracted: Any) -> tuple:
        """Guardrail findings for an upload. Flagged, never blocked: a document is the person's own material."""
        if self.scanner is None:
            return ()
        return tuple(self.scanner.scan_sections([(s.heading_path, s.text) for s in extracted.sections]))

    def _prepare(self, filename: str, data: bytes) -> tuple[Any, list[Chunk], str]:
        if not isinstance(data, (bytes, bytearray)):
            raise InvalidInput("a document must be given as bytes")
        data = bytes(data)
        extracted = extract(filename, data, self.limits)
        chunks = chunk_sections(extracted.sections, self.limits)
        if not chunks:
            raise DocumentRefused("this file contains no readable text")
        if len(chunks) > self.limits.max_chunks_per_document:
            raise DocumentRefused(
                f"this document would need {len(chunks)} chunks; the limit is {self.limits.max_chunks_per_document}"
            )
        return extracted, chunks, hashlib.sha256(data).hexdigest()

    @staticmethod
    def _live_by_hash(conn: sqlite3.Connection, project_id: str, digest: str) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT * FROM context_documents WHERE project_id = ? AND sha256 = ? AND removed_at IS NULL"
            " ORDER BY number LIMIT 1", (project_id, digest),
        ).fetchone()

    @staticmethod
    def _live_by_number(conn: sqlite3.Connection, project_id: str, number: int) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM context_documents WHERE project_id = ? AND number = ? AND removed_at IS NULL",
            (project_id, number),
        ).fetchone()
        if row is None:
            raise NotFoundError(f"document {number} not found in project {project_id!r}")
        return row

    def _insert_document(
        self, conn: sqlite3.Connection, project_id: str, name: str, kind: str, digest: str,
        size: int, chars: int, chunks: Sequence[Chunk], actor: str, findings: Sequence[Any] = (),
    ) -> DocumentInfo:
        live = conn.execute(
            "SELECT COUNT(*) FROM context_documents WHERE project_id = ? AND removed_at IS NULL", (project_id,)
        ).fetchone()[0]
        if live >= self.limits.max_docs_per_project:
            raise DocumentRefused(
                f"this project already has {live} documents; the limit is {self.limits.max_docs_per_project}"
            )
        number = conn.execute(
            "SELECT COALESCE(MAX(number), 0) + 1 FROM context_documents WHERE project_id = ?", (project_id,)
        ).fetchone()[0]
        now = self._clock()
        owner = f"DOC-{number:03d}"
        conn.execute(
            "INSERT INTO context_documents (project_id, number, filename, kind, sha256, size_bytes, chars,"
            " chunk_count, added_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, number, name, kind, digest, size, chars, len(chunks), actor, now),
        )
        conn.executemany(
            "INSERT INTO context_chunks (project_id, source_id, kind, owner, ordinal, heading_path, text,"
            " page, title) VALUES (?, ?, 'document', ?, ?, ?, ?, ?, ?)",
            [
                (project_id, f"{owner}#{i}", owner, i, c.heading_path, c.text, c.page, name)
                for i, c in enumerate(chunks, start=1)
            ],
        )
        write_audit(
            conn, now, actor, "document.added", "document", owner, project_id=project_id,
            detail={"filename": name, "kind": kind, "size_bytes": size, "chunks": len(chunks),
                    **({"guardrail_flags": _counts(findings)} if findings else {})},
        )
        row = conn.execute(
            "SELECT * FROM context_documents WHERE project_id = ? AND number = ?", (project_id, number)
        ).fetchone()
        return _info(row)

    def _delete_document(
        self, conn: sqlite3.Connection, project_id: str, row: sqlite3.Row, actor: str, *, action: str
    ) -> None:
        owner = f"DOC-{row['number']:03d}"
        conn.execute(
            "DELETE FROM context_chunks WHERE project_id = ? AND kind = 'document' AND owner = ?",
            (project_id, owner),
        )
        now = self._clock()
        conn.execute(
            "UPDATE context_documents SET removed_at = ? WHERE project_id = ? AND number = ?",
            (now, project_id, row["number"]),
        )
        write_audit(
            conn, now, actor, action, "document", owner, project_id=project_id,
            detail={"filename": row["filename"]},
        )

    # ---- approved artefacts: the re-ingest loop ----------------------------------------

    def reingest_phase(self, project_id: str, phase_key: str, *, actor: str = "system") -> ReingestResult:
        """Index the latest version of every artefact of an APPROVED phase, replacing older versions.

        Each artefact is its own transaction, so one that cannot be indexed is reported without
        stopping the others. Idempotent: an artefact already indexed at its current version is skipped.
        """
        check_actor(actor)
        with self.db.read() as conn:
            _require_project(conn, project_id)
            phase = conn.execute(
                "SELECT status FROM phase_runs WHERE project_id = ? AND phase_key = ?", (project_id, phase_key)
            ).fetchone()
            if phase is None or phase["status"] != "approved":
                raise InvalidInput(
                    f"phase '{phase_key}' is not approved, and only approved content becomes searchable context"
                )
            artefacts = conn.execute(
                "SELECT a.id, a.title, a.phase_key, v.number, v.body FROM artefacts a"
                " JOIN artefact_versions v ON v.project_id = a.project_id AND v.artefact_id = a.id"
                " WHERE a.project_id = ? AND a.phase_key = ?"
                "   AND v.number = (SELECT MAX(number) FROM artefact_versions"
                "                   WHERE project_id = a.project_id AND artefact_id = a.id)"
                " ORDER BY a.rowid", (project_id, phase_key),
            ).fetchall()

        indexed = skipped = total_chunks = 0
        failed: list[tuple[str, str]] = []
        for art in artefacts:
            try:
                made = self._index_artefact(project_id, art, actor)
            except Exception as exc:  # one artefact must not stop the rest
                log.warning("could not index artefact %s", art["id"], exc_info=True)
                failed.append((art["id"], str(exc) if isinstance(exc, (InvalidInput, DocumentRefused)) else type(exc).__name__))
                continue
            if made is None:
                skipped += 1
            else:
                indexed += 1
                total_chunks += made
        return ReingestResult(indexed, skipped, total_chunks, tuple(failed))

    def _index_artefact(self, project_id: str, art: sqlite3.Row, actor: str) -> int | None:
        """Returns the number of chunks written, or None if this version was already indexed."""
        owner = f"{art['id']}@v{art['number']}"
        chunks = chunk_sections(sections_from_markdown(art["body"]), self.limits)
        if not chunks:
            raise InvalidInput(f"artefact {art['id']} has no readable text")
        if len(chunks) > self.limits.max_chunks_per_document:
            raise InvalidInput(
                f"artefact {art['id']} would need {len(chunks)} chunks; the limit is {self.limits.max_chunks_per_document}"
            )
        with self.db.write() as conn:
            current = {
                r[0] for r in conn.execute(
                    "SELECT DISTINCT owner FROM context_chunks WHERE project_id = ? AND kind = 'artefact'"
                    " AND artefact_id = ?", (project_id, art["id"]),
                )
            }
            if current == {owner}:
                return None
            # Drop every earlier version of this artefact, so a search can never return stale text.
            conn.execute(
                "DELETE FROM context_chunks WHERE project_id = ? AND kind = 'artefact' AND artefact_id = ?",
                (project_id, art["id"]),
            )
            title = f"{art['title']} (v{art['number']})"
            conn.executemany(
                "INSERT INTO context_chunks (project_id, source_id, kind, owner, ordinal, heading_path, text,"
                " page, title, phase_key, artefact_id) VALUES (?, ?, 'artefact', ?, ?, ?, ?, NULL, ?, ?, ?)",
                [
                    (project_id, f"{owner}#{i}", owner, i, c.heading_path, c.text, title, art["phase_key"], art["id"])
                    for i, c in enumerate(chunks, start=1)
                ],
            )
            write_audit(
                conn, self._clock(), actor, "context.artefact_indexed", "artefact", art["id"],
                project_id=project_id, detail={"version": art["number"], "chunks": len(chunks)},
            )
            return len(chunks)

    def unindex_phase(self, project_id: str, phase_key: str, *, actor: str = "system") -> int:
        """Take a phase's artefacts out of the index, e.g. when it is reopened. Returns chunks removed."""
        check_actor(actor)
        with self.db.write() as conn:
            _require_project(conn, project_id)
            cursor = conn.execute(
                "DELETE FROM context_chunks WHERE project_id = ? AND kind = 'artefact' AND phase_key = ?",
                (project_id, phase_key),
            )
            removed = cursor.rowcount
            if removed:
                write_audit(
                    conn, self._clock(), actor, "context.phase_unindexed", "phase", phase_key,
                    project_id=project_id, detail={"chunks": removed},
                )
            return removed

    # ---- search ----------------------------------------------------------------------------

    def search(
        self,
        project_id: str,
        query: str,
        *,
        limit: int = 8,
        kinds: Iterable[str] | None = None,
        phase_key: str | None = None,
        min_relevance: float | None = None,
        min_coverage: float | None = None,
    ) -> list[Hit]:
        """The best-matching chunks for a question, most relevant first.

        Three numbers say how good a hit is, and they answer different questions:
          score      raw BM25, higher is better; tiny and nearly flat on small corpora.
          relevance  0 to 1 against the best hit of THIS search. The best hit is always 1.0, even when it
                     is poor, so it ranks hits against each other but cannot say whether any is good.
          coverage   0 to 1: the share of the question's words the chunk contains. Absolute, so
                     `min_coverage=0.5` means "at least half of what was asked about is in the chunk".
        Filters are applied before `limit`, so you get the top `limit` hits that meet the bar.
        """
        wanted = None
        if kinds is not None:
            wanted = list(dict.fromkeys(kinds))
            bad = [k for k in wanted if k not in SOURCE_KINDS]
            if bad:
                raise InvalidInput(f"unknown kind(s) {bad}; kinds are {list(SOURCE_KINDS)}")
        for name, value in (("min_relevance", min_relevance), ("min_coverage", min_coverage)):
            if value is not None and not (
                isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value <= 1
            ):
                raise InvalidInput(f"{name} must be between 0 and 1")
        limit = max(1, min(int(limit), MAX_SEARCH_LIMIT))
        # With a quality bar, look at more candidates than `limit` so the bar is applied BEFORE the cut.
        fetch = MAX_SEARCH_LIMIT if (min_relevance is not None or min_coverage is not None) else limit

        words = query_words(query)
        match = build_fts_query(query)
        with self.db.read() as conn:
            _require_project(conn, project_id)
            if match is None:
                return []
            sql = (
                "SELECT c.*, bm25(context_fts) AS rank FROM context_fts"
                " JOIN context_chunks c ON c.id = context_fts.rowid"
                " WHERE context_fts MATCH ? AND c.project_id = ?"
            )
            args: list[Any] = [match, project_id]
            if wanted is not None:
                if not wanted:
                    return []
                sql += f" AND c.kind IN ({','.join('?' * len(wanted))})"
                args += wanted
            if phase_key is not None:
                sql += " AND c.phase_key = ?"
                args.append(phase_key)
            # Ties break by source and position, so the same question always returns the same order.
            sql += " ORDER BY rank, c.source_id, c.ordinal LIMIT ?"
            args.append(fetch)
            rows = conn.execute(sql, args).fetchall()
            matched = self._words_matched(conn, [r["id"] for r in rows], words)

        if not rows:
            return []
        scores = [-r["rank"] for r in rows]  # BM25 reports lower-is-better; flip once, here
        top = max(scores)
        hits: list[Hit] = []
        for row, score in zip(rows, scores):
            relevance = (score / top) if top > 0 else 1.0
            coverage = matched.get(row["id"], 0) / len(words)
            if min_relevance is not None and relevance < min_relevance:
                continue
            if min_coverage is not None and coverage < min_coverage:
                continue
            hits.append(_hit(row, score=score, relevance=relevance, coverage=coverage))
            if len(hits) == limit:
                break
        return hits

    @staticmethod
    def _words_matched(conn: sqlite3.Connection, chunk_ids: Sequence[int], words: Sequence[str]) -> dict[int, int]:
        """For each chunk, how many of the question's words it contains.

        Asks the full-text index itself, one word at a time, so stemming and accents behave exactly as
        they do in the search ('booking' counts as present in a chunk that says 'booked').
        """
        counts: dict[int, int] = {cid: 0 for cid in chunk_ids}
        if not chunk_ids:
            return counts
        marks = ",".join("?" * len(chunk_ids))
        for word in words:
            found = conn.execute(
                f"SELECT rowid FROM context_fts WHERE context_fts MATCH ? AND rowid IN ({marks})",
                (f'"{word}"', *chunk_ids),
            ).fetchall()
            for (rowid,) in found:
                counts[rowid] += 1
        return counts

    def resolve(self, project_id: str, source_id: str) -> Hit | None:
        """The chunk a citation points at, or None. Another project's ID, an unknown ID, a malformed ID,
        and the ID of a superseded artefact version all give None, never other text."""
        if not valid_source_id(source_id):
            return None
        with self.db.read() as conn:
            _require_project(conn, project_id)
            row = conn.execute(
                "SELECT * FROM context_chunks WHERE project_id = ? AND source_id = ?", (project_id, source_id)
            ).fetchone()
        return _hit(row) if row is not None else None

    def stats(self, project_id: str) -> dict[str, int]:
        with self.db.read() as conn:
            _require_project(conn, project_id)
            by_kind = dict(conn.execute(
                "SELECT kind, COUNT(*) FROM context_chunks WHERE project_id = ? GROUP BY kind", (project_id,)
            ).fetchall())
            docs = conn.execute(
                "SELECT COUNT(*) FROM context_documents WHERE project_id = ? AND removed_at IS NULL", (project_id,)
            ).fetchone()[0]
            arts = conn.execute(
                "SELECT COUNT(DISTINCT owner) FROM context_chunks WHERE project_id = ? AND kind = 'artefact'",
                (project_id,),
            ).fetchone()[0]
        return {
            "documents": docs,
            "artefact_sources": arts,
            "memory": by_kind.get("memory", 0),
            "chunks": sum(by_kind.values()),
        }
