"""One tiny real call per model slot, to find out what ICA actually does.

Run it yourself (it uses your key and costs a fraction of a cent):

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.live_check
    ... --slot openai          only one slot
    ... --shape                also print the NAMES of the keys in each reply (never values)
    ... --model openai=NAME    try another model ID for a slot, for this run only (repeatable).
                               Your .env is never changed. Use it to find an ID your key can use.

It goes through the real gateway with fallback switched off, so a broken slot is reported as
broken instead of being quietly replaced by Sonnet, and it uses a throwaway database.
It never prints the API key, the endpoint or the user-agent.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import httpx

from app.config import Settings, get_settings
from app.llm.errors import LLMCallFailed, LLMError, SlotNotConfigured
from app.llm.families import SLOT_NAMES, model_env
from app.llm.gateway import Gateway
from app.llm.providers.ica import IcaConfigError, IcaProvider, build_messages, chat_url
from app.llm.routing import Routing
from app.llm.types import LLMRequest
from app.repos import Store

PROMPT = "Reply with the single word: ready"
MAX_TOKENS = 200


@dataclass(frozen=True)
class Row:
    slot: str
    model: str
    family: str
    outcome: str  # "ok" or a failure kind
    finish: str
    tokens_in: str
    tokens_out: str
    latency_ms: str
    cost: str
    note: str

    @property
    def ok(self) -> bool:
        return self.outcome == "ok"


def describe_shape(value: Any, depth: int = 0) -> Any:
    """The structure of a JSON value: key names and types, never the values themselves."""
    if isinstance(value, dict):
        return {key: describe_shape(item, depth + 1) for key, item in value.items()}
    if isinstance(value, list):
        if not value:
            return "list(empty)"
        return [f"list of {len(value)}", describe_shape(value[0], depth + 1)]
    if value is None:
        return "null"
    return type(value).__name__


def format_cost(cost: float | None) -> str:
    return "unknown" if cost is None else f"${cost:.6f}"


def row_from_result(slot: str, model: str, result: Any) -> Row:
    return Row(
        slot=slot, model=model, family=result.family, outcome="ok",
        finish=result.finish_reason or "-", tokens_in=str(result.tokens_in), tokens_out=str(result.tokens_out),
        latency_ms=str(result.latency_ms), cost=format_cost(result.cost_usd),
        # Length only: what a model says is not ours to print, and this output gets pasted around.
        note=f"reply of {len(result.text)} characters",
    )


def row_from_failure(slot: str, model: str, family: str, exc: BaseException) -> Row:
    if isinstance(exc, LLMCallFailed):
        last = exc.attempts[-1]
        outcome, note = last.kind, last.message
    elif isinstance(exc, SlotNotConfigured):
        outcome, note = "not_configured", str(exc)
    else:
        outcome, note = type(exc).__name__, str(exc)
    return Row(slot, model, family, outcome, "-", "-", "-", "-", "-", " ".join(note.split())[:200])


def render(rows: Sequence[Row]) -> str:
    headers = ["slot", "model", "family", "result", "finish", "in", "out", "ms", "cost", "note"]
    body = [
        [r.slot, r.model or "(not set)", r.family, r.outcome, r.finish, r.tokens_in, r.tokens_out,
         r.latency_ms, r.cost, r.note]
        for r in rows
    ]
    widths = [max(len(str(cell)) for cell in column) for column in zip(headers, *body)]
    lines = ["  ".join(h.ljust(w) for h, w in zip(headers, widths)).rstrip()]
    lines.append("  ".join("-" * w for w in widths))
    lines += ["  ".join(str(c).ljust(w) for c, w in zip(row, widths)).rstrip() for row in body]
    good = sum(r.ok for r in rows)
    lines.append("")
    lines.append(f"{good}/{len(rows)} slots OK")
    return "\n".join(lines)


def parse_overrides(items: Sequence[str]) -> dict[str, str]:
    """`--model slot=NAME` pairs. Raises ValueError with a plain message on anything malformed."""
    overrides: dict[str, str] = {}
    for item in items:
        slot, sep, name = item.partition("=")
        slot, name = slot.strip(), name.strip()
        if not sep or not slot or not name:
            raise ValueError(f"--model needs slot=NAME, got {item!r}")
        if slot not in SLOT_NAMES:
            raise ValueError(f"--model: unknown slot {slot!r}; slots are {', '.join(SLOT_NAMES)}")
        if len(name) > 120 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]*", name):
            raise ValueError(f"--model: {name[:40]!r} does not look like a model ID")
        overrides[slot] = name
    return overrides


def with_overrides(settings: Settings, overrides: dict[str, str]) -> Settings:
    """A copy of the settings with some slots' model IDs swapped. The original is untouched."""
    if not overrides:
        return settings
    fields = {
        f"{'ibm_ica' if slot == 'sonnet' else f'ibm_ica_{slot}'}_model_id": name
        for slot, name in overrides.items()
    }
    return settings.model_copy(update=fields)


def preflight(settings: Settings) -> list[str]:
    problems = []
    if not settings.endpoint_set:
        problems.append("IBM_ICA_ENDPOINT is not set in backend/.env")
    if not settings.api_key_set:
        problems.append("IBM_ICA_API_KEY is not set in backend/.env")
    return problems


async def probe_shape(settings: Settings, model: str) -> Any:
    """One raw call to show the response structure (key names only)."""
    provider = IcaProvider(settings)
    try:
        response = await provider.client.post(
            chat_url(settings.ibm_ica_endpoint),
            json={"model": model, "messages": build_messages(LLMRequest.user("orchestrator", PROMPT)),
                  "max_tokens": MAX_TOKENS},
            headers=provider.headers_for(model),
        )
        try:
            return {"http_status": response.status_code, "body_shape": describe_shape(response.json())}
        except ValueError:
            return {"http_status": response.status_code, "body_shape": "not JSON"}
    except httpx.HTTPError as exc:
        return {"error": type(exc).__name__}
    finally:
        await provider.aclose()


async def run(settings: Settings, slots: Sequence[str], shape: bool, db_dir: Path) -> tuple[list[Row], dict]:
    provider = IcaProvider(settings)
    store = Store.open(db_dir / "live_check.db")
    gateway = Gateway(settings, Routing.load(), provider, store)
    rows: list[Row] = []
    shapes: dict[str, Any] = {}
    try:
        for slot in slots:
            model = settings.slots[slot].model_id.strip()
            family = gateway.family_of(model) if model else "-"
            request = LLMRequest.user("orchestrator", PROMPT, max_tokens=MAX_TOKENS)
            try:
                result = await gateway.complete(request, slot=slot, allow_fallback=False)
                rows.append(row_from_result(slot, model, result))
            except (LLMError, ValueError) as exc:
                rows.append(row_from_failure(slot, model, family, exc))
            if shape and model:
                shapes[slot] = await probe_shape(settings, model)
    finally:
        await provider.aclose()
    return rows, shapes


def main(argv: Sequence[str] | None = None, settings: Settings | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--slot", choices=SLOT_NAMES, help="check only this slot")
    parser.add_argument("--shape", action="store_true", help="also print response key names (no values)")
    parser.add_argument("--model", action="append", default=[], metavar="SLOT=NAME",
                        help="try another model ID for a slot, this run only (repeatable)")
    args = parser.parse_args(argv)

    try:
        overrides = parse_overrides(args.model)
    except ValueError as exc:
        print(f"Cannot run the live check: {exc}", file=sys.stderr)
        return 2

    cfg = with_overrides(settings or get_settings(), overrides)
    problems = preflight(cfg)
    if problems:
        print("Cannot run the live check:\n  " + "\n  ".join(problems), file=sys.stderr)
        return 2

    slots = [args.slot] if args.slot else list(SLOT_NAMES)
    with tempfile.TemporaryDirectory(prefix="sdlc_live_check_") as tmp:
        try:
            rows, shapes = asyncio.run(run(cfg, slots, args.shape, Path(tmp)))
        except IcaConfigError as exc:
            print(f"Cannot run the live check: {exc}", file=sys.stderr)
            return 2

    print(render(rows))
    if cfg.openai_key_is_own and any(r.slot == "openai" for r in rows):
        print("\nThe OpenAI slot uses its own key (IBM_ICA_OPENAI_API_KEY); the other slots use IBM_ICA_API_KEY.")
    if overrides:
        names = ", ".join(f"{slot}={name}" for slot, name in overrides.items())
        print(f"\nModel IDs overridden for this run only: {names}. Your .env was not changed.")
        print("Cost uses the slot's configured prices, which may not match an overridden model's.")
    if shapes:
        print("\nResponse structure (key names and types only):")
        print(json.dumps(shapes, indent=2))
    for row in rows:
        if row.outcome in ("model_access_denied", "model_not_found"):
            print(
                f"\nNext step for {row.slot}: this key cannot use '{row.model}'. Your key itself works. "
                f"Try another model with:  --slot {row.slot} --model {row.slot}=<model-id>  "
                f"then put the one that works in {model_env(row.slot)} in backend/.env."
            )
    missing = [model_env(r.slot) for r in rows if r.outcome == "not_configured"]
    if missing:
        print("\nNot configured: " + ", ".join(missing))
    return 0 if all(r.ok for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
