from __future__ import annotations

from ..models import InvalidInput


class AgentError(InvalidInput):
    """The runtime refused to run, or could not produce a valid artefact.

    A subclass of InvalidInput so callers that already catch refusals from the data layer catch these.
    The message is a plain sentence; it never contains a prompt, a model reply or a credential.
    """


class NoSkill(AgentError):
    """No skill file exists for this artefact yet."""


class ArtefactNotInPlan(AgentError):
    """The artefact was switched off for this project, or is not in the catalogue."""


class PhaseNotRunning(AgentError):
    """Artefacts are only generated while their phase is running."""


class MissingInput(AgentError):
    """An upstream artefact the skill depends on has no content yet."""


class InputTooLarge(AgentError):
    """The material for the prompt is over budget. Nothing is silently cut."""


class RunStopped(AgentError):
    """A run-wide cap or a cancel arrived while an artefact was still being repaired, so it was dropped unsaved."""

    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.reason = reason  # "budget" | "time" | "cancelled"


class OutputInvalid(AgentError):
    """The model never produced a valid artefact within the repair budget. Nothing was saved."""

    def __init__(self, message: str, problems: list[str], attempts: int):
        super().__init__(message)
        self.problems = tuple(problems)
        self.attempts = attempts
