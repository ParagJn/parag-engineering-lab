from __future__ import annotations

import asyncio
import math
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from ..types import LLMRequest, ProviderResponse, Usage


class MockScriptError(Exception):
    """The test asked for a model call nobody scripted."""


class _Hang:
    def __repr__(self) -> str:
        return "HANG"


HANG = _Hang()  # an outcome that never answers, to exercise the timeout


@dataclass(frozen=True)
class MockCall:
    model_id: str
    request: LLMRequest


def estimate_tokens(text: str) -> int:
    return math.ceil(len(text) / 4)


class MockProvider:
    """Answers from a script. Each outcome is a string, a ProviderResponse, an exception or HANG."""

    label = "mock"

    def __init__(self, script: Mapping[str, Iterable[Any]] | None = None, default: Any = None):
        self._script: dict[str, deque] = defaultdict(deque)
        for model_id, outcomes in (script or {}).items():
            self._script[model_id].extend(outcomes)
        self.default = default
        self.calls: list[MockCall] = []
        self.entered = asyncio.Event()  # set as soon as the first call arrives
        self.barrier: asyncio.Barrier | None = None  # set to make N calls wait for each other

    def queue(self, model_id: str, *outcomes: Any) -> None:
        self._script[model_id].extend(outcomes)

    @property
    def models(self) -> list[str]:
        return [call.model_id for call in self.calls]

    async def complete(self, model_id: str, request: LLMRequest) -> ProviderResponse:
        self.calls.append(MockCall(model_id, request))
        self.entered.set()
        if self.barrier is not None:
            await self.barrier.wait()

        queue = self._script[model_id]
        if queue:
            outcome = queue.popleft()
        elif self.default is not None:
            outcome = self.default
        else:
            raise MockScriptError(f"no scripted outcome left for model {model_id!r}")

        if outcome is HANG:
            await asyncio.sleep(3600)
        if isinstance(outcome, BaseException):
            raise outcome
        if isinstance(outcome, ProviderResponse):
            return outcome
        text = str(outcome)
        prompt = request.system + "".join(m.content for m in request.messages)
        return ProviderResponse(text, Usage(estimate_tokens(prompt), estimate_tokens(text)), "stop")
