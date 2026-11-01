"""Saved model replies: how a request is identified, what a file looks like, and how a set is loaded.

A recording is looked up by a hash of everything that changes what a model would answer (the model,
the prompt, the limits). It is deliberately NOT looked up by role, project, phase or run id, which
change on every demo reset.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from ..config import Settings
from ..repos import utc_now
from .types import LLMRequest, ProviderResponse, Usage

FORMAT = 1
KEY_PREFIX_LEN = 16
MAX_REPLAY_LATENCY_MS = 60_000


# ---- identifying a request --------------------------------------------------

def key_from_parts(
    model: str,
    system: str,
    messages: Sequence[tuple[str, str]],
    max_tokens: int,
    temperature: float | None,
) -> str:
    """SHA-256 over a canonical JSON, so the key is the same on every machine and Python version."""
    payload = {
        "model": model,
        "system": system,
        "messages": [[role, content] for role, content in messages],  # a conversation: order matters
        "max_tokens": max_tokens,
        # 1 and 1.0 are the same temperature; make them the same key.
        "temperature": None if temperature is None else float(temperature),
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))  # ASCII-escaped: safe for any text
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def request_key(model_id: str, request: LLMRequest) -> str:
    return key_from_parts(
        model_id,
        request.system,
        [(m.role, m.content) for m in request.messages],
        request.max_tokens,
        request.temperature,
    )


# ---- one recording ----------------------------------------------------------

class RecordingInvalid(ValueError):
    """A recording file cannot be used. The message never includes the file's content."""


@dataclass(frozen=True)
class Recording:
    key: str
    model: str
    role: str
    recorded_at: str
    latency_ms: int
    system: str
    messages: tuple[tuple[str, str], ...]
    max_tokens: int
    temperature: float | None
    text: str
    usage: Usage | None
    finish_reason: str | None

    @classmethod
    def from_call(
        cls, model_id: str, request: LLMRequest, response: ProviderResponse, latency_ms: int,
        recorded_at: str | None = None,
    ) -> "Recording":
        return cls(
            key=request_key(model_id, request),
            model=model_id,
            role=request.role,
            recorded_at=recorded_at or utc_now(),
            latency_ms=max(0, int(latency_ms)),
            system=request.system,
            messages=tuple((m.role, m.content) for m in request.messages),
            max_tokens=request.max_tokens,
            temperature=None if request.temperature is None else float(request.temperature),
            text=response.text,
            usage=response.usage,
            finish_reason=response.finish_reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "format": FORMAT,
            "key": self.key,
            "model": self.model,
            "role": self.role,
            "recorded_at": self.recorded_at,
            "latency_ms": self.latency_ms,
            "request": {
                "system": self.system,
                "messages": [{"role": r, "content": c} for r, c in self.messages],
                "max_tokens": self.max_tokens,
                "temperature": self.temperature,
            },
            "response": {
                "text": self.text,
                "usage": None if self.usage is None
                else {"tokens_in": self.usage.tokens_in, "tokens_out": self.usage.tokens_out},
                "finish_reason": self.finish_reason,
            },
        }

    def text_fields(self) -> list[str]:
        """Every free-text part of the recording, for the secret check."""
        return [self.system, *(content for _, content in self.messages), self.text]


def _whole(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _get(obj: Any, name: str, where: str, kinds: tuple[type, ...], *, allow_none: bool = False) -> Any:
    if not isinstance(obj, dict) or name not in obj:
        raise RecordingInvalid(f"missing field '{where}{name}'")
    value = obj[name]
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, kinds):
        raise RecordingInvalid(f"field '{where}{name}' has the wrong type")
    return value


def parse_recording(data: Any) -> Recording:
    if not isinstance(data, dict):
        raise RecordingInvalid("not a JSON object")
    if data.get("format") != FORMAT:
        raise RecordingInvalid(f"unsupported format (this version reads format {FORMAT})")

    key = _get(data, "key", "", (str,))
    model = _get(data, "model", "", (str,))
    role = _get(data, "role", "", (str,))
    recorded_at = _get(data, "recorded_at", "", (str,))
    if not model.strip():
        raise RecordingInvalid("field 'model' is empty")

    latency = data.get("latency_ms")  # old or hand-made files may omit it: treated as 0
    if latency is None:
        latency = 0
    elif not _whole(latency):
        raise RecordingInvalid("field 'latency_ms' has the wrong type")

    request = _get(data, "request", "", (dict,))
    system = _get(request, "system", "request.", (str,))
    raw_messages = _get(request, "messages", "request.", (list,))
    if not raw_messages:
        raise RecordingInvalid("field 'request.messages' is empty")
    messages: list[tuple[str, str]] = []
    for item in raw_messages:
        messages.append((_get(item, "role", "request.messages[].", (str,)),
                         _get(item, "content", "request.messages[].", (str,))))
    max_tokens = _get(request, "max_tokens", "request.", (int,))
    if max_tokens < 1:
        raise RecordingInvalid("field 'request.max_tokens' must be 1 or more")
    temperature = _get(request, "temperature", "request.", (int, float), allow_none=True)

    response = _get(data, "response", "", (dict,))
    text = _get(response, "text", "response.", (str,))
    if not text.strip():
        raise RecordingInvalid("the recorded reply is empty")
    finish_reason = _get(response, "finish_reason", "response.", (str,), allow_none=True)
    raw_usage = _get(response, "usage", "response.", (dict,), allow_none=True)
    usage = None
    if raw_usage is not None:
        if not (_whole(raw_usage.get("tokens_in")) and _whole(raw_usage.get("tokens_out"))):
            raise RecordingInvalid("field 'response.usage' needs whole-number tokens_in and tokens_out")
        usage = Usage(raw_usage["tokens_in"], raw_usage["tokens_out"])

    expected = key_from_parts(model, system, messages, max_tokens, temperature)
    if key != expected:
        # Editing the prompt text would make the file answer a question nobody asked.
        raise RecordingInvalid("the stored key does not match the stored request (the prompt was edited)")

    return Recording(
        key=key, model=model, role=role, recorded_at=recorded_at, latency_ms=latency,
        system=system, messages=tuple(messages), max_tokens=max_tokens,
        temperature=None if temperature is None else float(temperature),
        text=text, usage=usage, finish_reason=finish_reason,
    )


def leaks_secret(recording: Recording, secrets: Iterable[str]) -> bool:
    """True when the prompt or the reply contains a configured credential."""
    fields = recording.text_fields()
    return any(len(secret) >= 4 and secret in field for secret in secrets for field in fields)


# ---- a set of recordings ----------------------------------------------------

@dataclass(frozen=True)
class RecordingProblem:
    file: str
    reason: str


class RecordingStore:
    """All recordings in one folder. Loaded once; reads and saves are thread-safe."""

    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self._lock = threading.Lock()
        self._entries: dict[str, Recording] = {}
        self.problems: list[RecordingProblem] = []
        self.load()

    def load(self) -> None:
        entries: dict[str, Recording] = {}
        problems: list[RecordingProblem] = []
        if self.folder.is_dir():
            for path in sorted(self.folder.glob("*.json")):
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError):
                    problems.append(RecordingProblem(path.name, "the file could not be read"))
                    continue
                except (ValueError, RecursionError):
                    problems.append(RecordingProblem(path.name, "not valid JSON"))
                    continue
                try:
                    recording = parse_recording(data)
                except RecordingInvalid as exc:
                    problems.append(RecordingProblem(path.name, str(exc)))
                    continue
                entries[recording.key] = recording
        with self._lock:
            self._entries = entries
            self.problems = problems

    def get(self, key: str) -> Recording | None:
        with self._lock:
            return self._entries.get(key)

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)

    def count_for_model(self, model_id: str) -> int:
        with self._lock:
            return sum(1 for r in self._entries.values() if r.model == model_id)

    def save(self, recording: Recording) -> Path:
        """Write one recording atomically: a crash never leaves a half-written file behind."""
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / f"{recording.key[:KEY_PREFIX_LEN]}.json"
        payload = json.dumps(recording.to_dict(), indent=2, ensure_ascii=False) + "\n"
        fd, temp = tempfile.mkstemp(dir=self.folder, prefix=".tmp-", suffix=".part")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(temp, path)
        except BaseException:
            try:
                os.unlink(temp)
            except FileNotFoundError:
                pass
            raise
        with self._lock:
            self._entries[recording.key] = recording
        return path


# ---- which of the three modes this configuration means ----------------------

def recordings_mode(settings: Settings) -> str:
    """'replay' (serve saved replies), 'recording' (save live ones) or 'off'."""
    if settings.app_mode == "replay":
        return "replay"
    if settings.record_live_calls and settings.endpoint_set and settings.api_key_set:
        return "recording"
    return "off"
