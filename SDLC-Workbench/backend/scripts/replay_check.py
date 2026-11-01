"""Prove that record -> replay works with REAL ICA replies.

Run it yourself (it makes four tiny live calls, a fraction of a cent):

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.replay_check

1. Makes the same four calls as live_check, through a RecordingProvider, into a temporary folder.
2. Replays them from that folder with no network provider in the process.
3. Prints, per slot, whether text, tokens and cost came back identical, and how long each took.
4. Makes one deliberate miss and prints the message, so you can see what a stale recording looks like.

It never prints replies, keys, the endpoint or the user-agent, and it deletes its temporary folder.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from app.config import Settings, get_settings
from app.llm.errors import LLMError
from app.llm.families import SLOT_NAMES
from app.llm.gateway import Gateway
from app.llm.providers.ica import IcaConfigError, IcaProvider
from app.llm.providers.recording import RecordingProvider, ReplayProvider
from app.llm.recordings import RecordingStore
from app.llm.routing import Routing
from app.llm.types import LLMRequest, LLMResult
from app.repos import Store

from .live_check import MAX_TOKENS, PROMPT, format_cost, preflight

MISS_PROMPT = "This sentence was never recorded."


@dataclass(frozen=True)
class Trip:
    slot: str
    model: str
    live_ms: str
    replay_ms: str
    same_text: str
    same_tokens: str
    same_cost: str
    note: str

    @property
    def identical(self) -> bool:
        return self.same_text == self.same_tokens == self.same_cost == "yes"


def fingerprint(text: str) -> str:
    """Enough to compare two replies without ever printing one."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def yes_no(value: bool) -> str:
    return "yes" if value else "NO"


def compare(slot: str, model: str, live: LLMResult, replayed: LLMResult) -> Trip:
    return Trip(
        slot=slot, model=model,
        live_ms=str(live.latency_ms), replay_ms=str(replayed.latency_ms),
        same_text=yes_no(fingerprint(live.text) == fingerprint(replayed.text)),
        same_tokens=yes_no((live.tokens_in, live.tokens_out) == (replayed.tokens_in, replayed.tokens_out)),
        same_cost=yes_no(live.cost_usd == replayed.cost_usd),
        note=f"cost {format_cost(replayed.cost_usd)}",
    )


def failed_trip(slot: str, model: str, stage: str, exc: BaseException) -> Trip:
    kind = getattr(exc, "attempts", None)
    detail = kind[-1].kind if kind else type(exc).__name__
    return Trip(slot, model, "-", "-", "-", "-", "-", f"{stage} failed: {detail}")


def render(trips: Sequence[Trip]) -> str:
    headers = ["slot", "model", "live ms", "replay ms", "same text", "same tokens", "same cost", "note"]
    body = [[t.slot, t.model or "(not set)", t.live_ms, t.replay_ms, t.same_text, t.same_tokens, t.same_cost, t.note]
            for t in trips]
    widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *body)]
    lines = ["  ".join(h.ljust(w) for h, w in zip(headers, widths)).rstrip(),
             "  ".join("-" * w for w in widths)]
    lines += ["  ".join(str(c).ljust(w) for c, w in zip(row, widths)).rstrip() for row in body]
    good = sum(t.identical for t in trips)
    lines += ["", f"{good}/{len(trips)} round trips identical"]
    return "\n".join(lines)


async def run(settings: Settings, slots: Sequence[str], workdir: Path) -> tuple[list[Trip], str]:
    folder = workdir / "recordings"
    ica = IcaProvider(settings)
    live_gateway = Gateway(
        settings, Routing.load(),
        RecordingProvider(ica, RecordingStore(folder), settings),
        Store.open(workdir / "live.db"),
    )

    trips: list[Trip] = []
    try:
        # Phase 1: record. Every live call happens here, before replay exists.
        live_results: dict[str, LLMResult | BaseException] = {}
        for slot in slots:
            request = LLMRequest.user("orchestrator", PROMPT, max_tokens=MAX_TOKENS)
            try:
                live_results[slot] = await live_gateway.complete(request, slot=slot, allow_fallback=False)
            except (LLMError, ValueError) as exc:
                live_results[slot] = exc

        # Phase 2: replay from a store opened AFTER recording, with NO network provider at all.
        replay_gateway = Gateway(
            settings, Routing.load(), ReplayProvider(RecordingStore(folder)), Store.open(workdir / "replay.db"),
        )
        for slot in slots:
            model = settings.slots[slot].model_id.strip()
            live = live_results[slot]
            if isinstance(live, BaseException):
                trips.append(failed_trip(slot, model, "recording", live))
                continue
            request = LLMRequest.user("orchestrator", PROMPT, max_tokens=MAX_TOKENS)
            try:
                replayed = await replay_gateway.complete(request, slot=slot, allow_fallback=False)
            except (LLMError, ValueError) as exc:
                trips.append(failed_trip(slot, model, "replay", exc))
                continue
            trips.append(compare(slot, model, live, replayed))

        miss_message = ""
        try:
            await replay_gateway.complete(
                LLMRequest.user("orchestrator", MISS_PROMPT, max_tokens=MAX_TOKENS), slot=slots[0], allow_fallback=False
            )
            miss_message = "UNEXPECTED: the deliberate miss was served"
        except LLMError as exc:
            miss_message = str(exc)
    finally:
        await ica.aclose()
    return trips, miss_message


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--slot", choices=SLOT_NAMES, help="check only this slot")
    args = parser.parse_args(argv)

    cfg = settings or get_settings()
    problems = preflight(cfg)
    if problems:
        print("Cannot run the replay check:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 2

    slots = [args.slot] if args.slot else list(SLOT_NAMES)
    with tempfile.TemporaryDirectory(prefix="sdlc_replay_check_") as tmp:
        try:
            trips, miss = asyncio.run(run(cfg, slots, Path(tmp)))
        except IcaConfigError as exc:
            print(f"Cannot run the replay check: {exc}", file=sys.stderr)
            return 2

    print(render(trips))
    print("\nA recording that does not exist looks like this:")
    print(f"  {miss}")
    return 0 if trips and all(t.identical for t in trips) else 1


if __name__ == "__main__":
    raise SystemExit(main())
