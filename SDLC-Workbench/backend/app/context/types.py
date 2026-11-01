from __future__ import annotations

from dataclasses import dataclass

from ..models import InvalidInput

SOURCE_KINDS = ("document", "artefact", "memory")
DOCUMENT_KINDS = ("txt", "md", "docx", "pdf")


class DocumentRefused(InvalidInput):
    """A document was refused for a reason the user can act on. The message never includes its content."""


@dataclass(frozen=True)
class Limits:
    """What the context store will accept and how it cuts text up. Defaults need no configuration."""

    max_file_bytes: int = 10 * 1024 * 1024
    max_pdf_pages: int = 200
    max_docs_per_project: int = 500
    max_chunks_per_document: int = 2000
    chunk_target_chars: int = 900
    chunk_cap_chars: int = 1500  # no chunk is ever longer than this
    min_tail_chars: int = 120  # a shorter last chunk is merged into the one before it
    max_uncompressed_factor: int = 6  # a .docx may expand to this many times the file limit


@dataclass(frozen=True)
class DocumentInfo:
    number: int
    filename: str
    kind: str
    sha256: str
    size_bytes: int
    chars: int
    chunk_count: int
    added_by: str
    created_at: str
    removed_at: str | None = None
    already_added: bool = False  # True when the same bytes were already in the project
    findings: tuple = ()  # guardrail findings (rule, class, line, heading, length), flagged and never blocked; never the values

    @property
    def source_prefix(self) -> str:
        return f"DOC-{self.number:03d}"


@dataclass(frozen=True)
class Hit:
    """One retrieved chunk. `citation` is the text an agent quotes; `source_id` is how it is looked up."""

    source_id: str
    kind: str
    title: str
    heading_path: str
    text: str
    score: float | None  # raw BM25, flipped so higher is better; None when looked up by ID
    relevance: float | None  # 0..1 against the best hit of THIS search; the best hit is always 1.0
    coverage: float | None  # 0..1: the share of the question's words this chunk contains (absolute, unlike relevance)
    phase_key: str | None
    artefact_id: str | None
    page: int | None
    citation: str


@dataclass(frozen=True)
class ReingestResult:
    indexed: int  # artefacts (re)indexed
    skipped: int  # artefacts already indexed at their current version
    chunks: int
    failed: tuple[tuple[str, str], ...] = ()  # (artefact id, plain reason)
