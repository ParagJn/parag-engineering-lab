"""Which saved feedback notes still need acting on.

Every note a person or a reviewer leaves is kept in project memory for good. But a writer should see a note only
until a newer version of that artefact exists: after that the note has been acted on. One function decides, so the
runtime (what the writer is shown) and the re-run (which artefacts need rewriting) can never disagree.
"""
from __future__ import annotations

from ..models import MemoryEntry
from ..repos import Store

FEEDBACK_KINDS = ("reviewer_feedback", "human_feedback")


def unacted_notes(store: Store, project_id: str, phase_key: str, artefact_id: str | None) -> list[MemoryEntry]:
    """Feedback for this artefact, and phase-wide feedback, written since the artefact's current version.

    `artefact_id` is None when the artefact does not exist yet: then only phase-wide notes apply. Notes about a
    different artefact never apply. Notes of kind `note` are not feedback.
    """
    latest_at = None
    if artefact_id is not None and store.artefacts.get(project_id, artefact_id).latest_version is not None:
        latest_at = store.artefacts.get_version(project_id, artefact_id).created_at
    out: list[MemoryEntry] = []
    for entry in store.memory.list(project_id, phase_key=phase_key):
        if entry.kind not in FEEDBACK_KINDS:
            continue
        if entry.artefact_id is not None and entry.artefact_id != artefact_id:
            continue
        if latest_at is not None and entry.created_at < latest_at:
            continue  # written before the current version existed, so it has been acted on
        out.append(entry)
    return out
