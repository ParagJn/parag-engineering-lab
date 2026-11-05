from __future__ import annotations

from ..models import InvalidInput


class ReviewError(InvalidInput):
    """A review or a human action was refused, or the reviewer never produced a valid review.

    A subclass of InvalidInput so callers that already catch refusals from the data layer catch these.
    Messages are plain sentences; they never contain a prompt, a model reply or a credential.
    """


class NothingToReview(ReviewError):
    """The artefact has no version yet."""


class ReviewOutputInvalid(ReviewError):
    """The reviewer never produced a valid review within the repair budget. Nothing was stored."""

    def __init__(self, message: str, problems: list[str], attempts: int):
        super().__init__(message)
        self.problems = tuple(problems)
        self.attempts = attempts


class PersonRequired(ReviewError):
    """This action is a human decision. An agent or the system may not take it."""


class NotAnApprover(ReviewError):
    """The person is not allowed to take this decision: they hold none of the roles that may approve this phase (S23b). A permission, not a state of the phase."""


class WrongPhaseState(ReviewError):
    """The phase is not in a state where this action is allowed."""


class EditRefused(ReviewError):
    """A human edit failed the checks every version must pass. `problems` says why, in plain words."""

    def __init__(self, message: str, problems: list[str]):
        super().__init__(message)
        self.problems = tuple(problems)
