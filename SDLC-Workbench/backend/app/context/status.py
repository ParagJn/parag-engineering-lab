from __future__ import annotations

from .types import DOCUMENT_KINDS, Limits


def context_status(limits: Limits) -> dict:
    """What the context store accepts. No project data: the page has no project selected yet."""
    return {
        "supported_types": list(DOCUMENT_KINDS),
        "search": "keyword (BM25 with stemming)",
        "max_file_mb": limits.max_file_bytes // (1024 * 1024),
        "max_pdf_pages": limits.max_pdf_pages,
        "max_docs_per_project": limits.max_docs_per_project,
    }
