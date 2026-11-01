"""Run events: a fixed vocabulary, a durable log, and a bounded fan-out to anyone watching.

The log (the `run_events` table) is the truth: a watcher that connects late, or falls behind, reads it. The live
fan-out is only a convenience so a watcher does not have to poll. Two rules keep the run safe from its audience:
a watcher can never slow the run down (a full queue drops the watcher, not the event), and an event carries only
IDs, names, counts, costs and short plain reasons, never prompt text, a model reply, document text or a credential.
"""
from __future__ import annotations

import asyncio
import logging
import re
import threading
from dataclasses import dataclass
from typing import Any, Callable, Iterable

from ..models import RunEvent
from ..repos import Store

log = logging.getLogger(__name__)

# The whole vocabulary. S12 relies on it, so it lives in one place and a test pins it.
EVENT_TYPES = (
    "run.started",
    "artefact.started",
    "artefact.attempt",
    "artefact.finished",
    "artefact.failed",
    "artefact.skipped",
    "review.started",
    "review.finished",
    "review.paused",
    "gate.changed",
    "run.stopped",
    "run.finished",
)
HEARTBEAT = "heartbeat"  # sent to watchers when idle; never stored
DROPPED = "dropped"  # the last thing a watcher that fell too far behind is told; never stored

MAX_REASON_CHARS = 300
_URL = re.compile(r"https?://\S+")


def clean_reason(text: str, secrets: Iterable[str] = ()) -> str:
    """A reason fit to publish: one line, no URLs, no configured secret, bounded."""
    out = " ".join(str(text).split())
    for secret in secrets:
        if secret:
            out = out.replace(secret, "[removed]")
    out = _URL.sub("[url removed]", out)
    return out[:MAX_REASON_CHARS]


def event_reason(exc: BaseException, secrets: Iterable[str] = ()) -> str:
    """What an event may say about a failure. A reply that failed its checks is described by counts only, because the
    checks' own messages can quote a few words of the model's reply; any other unexpected error by its class name only."""
    from ..agents.errors import AgentError, OutputInvalid
    from ..llm.errors import LLMError
    from ..models import InvalidInput
    from ..review.errors import ReviewOutputInvalid

    if isinstance(exc, (OutputInvalid, ReviewOutputInvalid)):
        return f"the reply failed its checks after {exc.attempts} attempt(s) ({len(exc.problems)} problem(s))"
    if isinstance(exc, (AgentError, LLMError, InvalidInput)):
        return clean_reason(str(exc), secrets)
    return f"unexpected error ({type(exc).__name__})"


@dataclass(frozen=True)
class Watcher:
    """One live listener. `queue` holds events not yet delivered; `dropped` is set if it fell behind."""

    queue: "asyncio.Queue[RunEvent | None]"
    project_id: str
    loop: asyncio.AbstractEventLoop
    state: dict  # {"dropped": bool}


class EventBus:
    """Writes events to the log, then offers them to live watchers without ever waiting for one."""

    def __init__(self, store: Store, *, queue_size: int = 200, secrets: Callable[[], Iterable[str]] = lambda: ()):
        self.store = store
        self.queue_size = queue_size
        self._secrets = secrets
        self._watchers: list[Watcher] = []
        self._lock = threading.Lock()

    # ---- publishing ------------------------------------------------------------------------------------

    def publish(self, project_id: str, run_id: str, type_: str, data: dict[str, Any] | None = None) -> RunEvent:
        """Store an event and deliver it to every live watcher of the project. Safe to call from any thread."""
        if type_ not in EVENT_TYPES:
            raise ValueError(f"unknown event type {type_!r}; the vocabulary is {EVENT_TYPES}")
        event = self.store.run_events.append(project_id, run_id, type_, data or {})
        self._deliver(event)
        return event

    def _deliver(self, event: RunEvent) -> None:
        with self._lock:
            targets = [w for w in self._watchers if w.project_id == event.project_id and not w.state["dropped"]]
        for watcher in targets:
            try:
                watcher.loop.call_soon_threadsafe(self._offer, watcher, event)
            except RuntimeError:  # the watcher's loop has closed; it is gone
                self._remove(watcher)

    def _offer(self, watcher: Watcher, event: RunEvent) -> None:
        if watcher.state["dropped"]:
            return  # offers are scheduled before a drop and can land after it; nothing may follow the marker
        try:
            watcher.queue.put_nowait(event)
        except asyncio.QueueFull:
            # Never block the run for a slow watcher. Mark it dropped and tell it so; it catches up from the log.
            watcher.state["dropped"] = True
            self._remove(watcher)
            while not watcher.queue.empty():
                watcher.queue.get_nowait()
            watcher.queue.put_nowait(None)

    # ---- watching ------------------------------------------------------------------------------------------

    def watch(self, project_id: str) -> Watcher:
        watcher = Watcher(asyncio.Queue(maxsize=self.queue_size), project_id, asyncio.get_running_loop(), {"dropped": False})
        with self._lock:
            self._watchers.append(watcher)
        return watcher

    def unwatch(self, watcher: Watcher) -> None:
        self._remove(watcher)

    def _remove(self, watcher: Watcher) -> None:
        with self._lock:
            if watcher in self._watchers:
                self._watchers.remove(watcher)

    @property
    def watcher_count(self) -> int:
        with self._lock:
            return len(self._watchers)


def format_sse(event: RunEvent) -> str:
    """One Server-Sent Event: id, event name and a single JSON data line."""
    import json

    return f"id: {event.id}\nevent: {event.type}\ndata: {json.dumps({'run_id': event.run_id, 'at': event.at, **event.data}, sort_keys=True)}\n\n"


def format_comment(text: str) -> str:
    """An SSE comment line: ignored by the browser, but keeps a proxy from closing an idle connection."""
    return f": {text}\n\n"
