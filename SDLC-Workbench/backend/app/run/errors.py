from __future__ import annotations

from ..models import ConflictError, InvalidInput


class RunError(InvalidInput):
    """A run was refused, or could not be set up. Messages are plain sentences; none contains a prompt or a reply."""


class RunAlreadyActive(ConflictError):
    """This phase of this project is already being run."""


class UnknownArtefact(RunError):
    """A key named for a run is not in the phase's plan (unknown, or switched off for this project)."""
