"""Every way the sandbox says no, each with the sentence a person or an agent reads (S16).

One class per kind of refusal, so the Build loop (S17) can react to the right one: a path it may fix, a program it may not use, a limit it hit, or a
sandbox that is not there at all. The sentences never contain the workspace's real location on disk: paths are shown as they are INSIDE the workspace.
"""
from __future__ import annotations


class SandboxError(Exception):
    """Base class. `str(error)` is always a plain sentence, safe to show."""


class PathRefused(SandboxError):
    """A file path that is not allowed."""


class LimitExceeded(SandboxError):
    """A size, count or time limit."""

    def __init__(self, message: str, limit: str):
        super().__init__(message)
        self.limit = limit


class ContentRefused(SandboxError):
    """File content that is not allowed (a secret, or not text)."""


class CommandRefused(SandboxError):
    """A program or argument list that is not on the allow-list."""


class SandboxUnavailable(SandboxError):
    """The operating-system protection is not there, or failed its self-test. Nothing is run."""
