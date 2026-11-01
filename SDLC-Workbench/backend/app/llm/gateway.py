from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import replace
from typing import Any, Awaitable, Callable, Iterable, Mapping

from ..config import Settings, SlotConfig
from ..repos import Store
from .errors import (
    AttemptError,
    AuthenticationFailed,
    BadRequest,
    ContentFilterBlocked,
    LLMCallFailed,
    ProviderError,
    ReplayMiss,
    ReviewerUnavailable,
    SlotNotConfigured,
    TlsVerificationFailed,
    TransientProviderError,
)
from .credentials import key_variable_for_model
from .families import SLOT_FAMILY, UNKNOWN, fallback_env, family_of_model, model_env, owner_slot_name
from .pricing import cost_usd, pricing_slot
from .providers.base import Provider
from .routing import Routing
from .types import (
    Independence,
    LLMRequest,
    LLMResult,
    ProviderResponse,
    ReviewerOption,
    ReviewOutcome,
)

log = logging.getLogger(__name__)

NOT_SET = "(not set)"
MAX_BACKOFF_SECONDS = 10.0
MAX_ERROR_CHARS = 500


class Gateway:
    """The one place models are called from. Agents give a role; the gateway does the rest."""

    def __init__(
        self,
        settings: Settings,
        routing: Routing,
        provider: Provider,
        store: Store,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        call_id_factory: Callable[[], str] = lambda: uuid.uuid4().hex[:12],
    ):
        self.settings = settings
        self.routing = routing
        self.provider = provider
        self.store = store
        self._sleep = sleep
        self._call_id = call_id_factory

    # ---- slots, families, models -------------------------------------------

    @property
    def slots(self) -> Mapping[str, SlotConfig]:
        return self.settings.slots

    def family_of(self, model_id: str) -> str:
        return family_of_model(model_id, self.slots)

    def _models_for(self, slot: str, allow_fallback: bool) -> tuple[str, list[str]]:
        """(requested model for the trace, ordered list of models to try)."""
        cfg = self.slots[slot]
        primary = cfg.model_id.strip()
        fallback = cfg.fallback_model_id.strip()
        requested = primary or NOT_SET
        chain: list[str] = []
        if primary:
            chain.append(primary)
        if allow_fallback and fallback and fallback not in chain:
            chain.append(fallback)
        if not chain:
            raise SlotNotConfigured(
                f"slot '{slot}' has no model: set its model ID"
                + (" or fallback" if allow_fallback else "")
                + " in backend/.env"
            )
        return requested, chain

    # ---- the call -----------------------------------------------------------

    async def complete(
        self,
        request: LLMRequest,
        *,
        slot: str | None = None,
        overrides: Mapping[str, str] | None = None,
        allow_fallback: bool = True,
    ) -> LLMResult:
        if slot is None:
            slot = self.routing.slot_for(request.role, overrides)
        elif slot not in self.slots:
            raise SlotNotConfigured(f"unknown slot {slot!r}")
        requested_model, chain = self._models_for(slot, allow_fallback)
        primary_used = chain[0] == self.slots[slot].model_id.strip() and requested_model != NOT_SET

        call_id = self._call_id()
        failures: list[AttemptError] = []
        trace_ids: list[int] = []
        attempt_no = 0

        for model_index, model_id in enumerate(chain):
            fallback_used = not (primary_used and model_index == 0)
            retries_left = self.settings.llm_max_retries
            retry_number = 0
            while True:
                attempt_no += 1
                started = time.perf_counter()
                try:
                    response = await asyncio.wait_for(
                        self.provider.complete(model_id, request), self.settings.llm_timeout_seconds
                    )
                except asyncio.CancelledError:
                    raise  # never retried, never traced, never swallowed
                except asyncio.TimeoutError:
                    error: ProviderError | Exception = TransientProviderError(
                        f"no answer within {self.settings.llm_timeout_seconds:g}s"
                    )
                except ProviderError as exc:
                    error = exc
                except Exception as exc:
                    # A bug, not a provider condition: record it, then let it surface unchanged.
                    await self._trace_error(
                        request, slot, call_id, attempt_no, requested_model, model_id, fallback_used,
                        started, "unexpected", self._clean(f"{type(exc).__name__}: {exc}"), trace_ids,
                    )
                    raise
                else:
                    return await self._succeed(
                        request, slot, call_id, attempt_no, requested_model, model_id, fallback_used,
                        started, response, trace_ids,
                    )

                kind = getattr(error, "kind", "error")
                message = self._clean(str(error))
                failures.append(AttemptError(model_id, kind, message))
                await self._trace_error(
                    request, slot, call_id, attempt_no, requested_model, model_id, fallback_used,
                    started, kind, message, trace_ids,
                )

                # A replay miss is final too: a fallback model would only miss again, or hit a
                # recording made for a different model and make the demo look like it worked.
                if isinstance(error, (AuthenticationFailed, BadRequest, TlsVerificationFailed, ReplayMiss)):
                    raise LLMCallFailed(
                        self._final_message(slot, failures, key_variable_for_model(self.settings, model_id)),
                        failures,
                    ) from error
                if isinstance(error, TransientProviderError) and retries_left > 0:
                    retries_left -= 1
                    retry_number += 1
                    await self._sleep(self._backoff(retry_number))
                    continue
                break  # retries used up, or a content-filter block: try the next model

        raise LLMCallFailed(self._final_message(slot, failures), failures)

    async def _succeed(
        self, request, slot, call_id, attempt_no, requested_model, model_id, fallback_used,
        started, response: ProviderResponse, trace_ids,
    ) -> LLMResult:
        latency_ms = self._elapsed_ms(started)
        usage = response.usage
        cost = cost_usd(pricing_slot(model_id, self.slots), usage)
        tokens_in = usage.tokens_in if usage else 0
        tokens_out = usage.tokens_out if usage else 0
        await self._record(
            trace_ids, request=request, slot=slot, call_id=call_id, attempt=attempt_no,
            requested_model=requested_model, served_model=model_id, fallback_used=fallback_used,
            status="ok", tokens_in=tokens_in, tokens_out=tokens_out, latency_ms=latency_ms, cost_usd=cost,
        )
        return LLMResult(
            text=response.text,
            call_id=call_id,
            role=request.role,
            slot=slot,
            requested_model=requested_model,
            served_model=model_id,
            family=self.family_of(model_id),
            fallback_used=fallback_used,
            attempts=attempt_no,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=cost,
            finish_reason=response.finish_reason,
            trace_ids=tuple(trace_ids),
        )

    async def _trace_error(
        self, request, slot, call_id, attempt_no, requested_model, model_id, fallback_used,
        started, kind, message, trace_ids,
    ) -> None:
        await self._record(
            trace_ids, request=request, slot=slot, call_id=call_id, attempt=attempt_no,
            requested_model=requested_model, served_model=model_id, fallback_used=fallback_used,
            status="error", error=f"{kind}: {message}", latency_ms=self._elapsed_ms(started),
        )

    async def _record(self, trace_ids: list[int], *, request: LLMRequest, slot: str, **fields: Any) -> None:
        """Write one trace row off the event loop. A failed write never loses a paid-for answer."""
        try:
            trace = await asyncio.to_thread(
                self.store.traces.record,
                agent=request.role,
                slot=slot,
                project_id=request.project_id,
                run_id=request.run_id,
                phase_key=request.phase_key,
                **fields,
            )
            trace_ids.append(trace.id)
        except Exception:
            log.warning("could not write a trace row for role %s", request.role, exc_info=True)

    # ---- helpers ------------------------------------------------------------

    @staticmethod
    def _elapsed_ms(started: float) -> int:
        return max(0, round((time.perf_counter() - started) * 1000))

    @staticmethod
    def _backoff_for(base: float, retry_number: int) -> float:
        return min(base * 2 ** (retry_number - 1), MAX_BACKOFF_SECONDS)

    def _backoff(self, retry_number: int) -> float:
        return self._backoff_for(self.settings.llm_retry_backoff_seconds, retry_number)

    def _clean(self, text: str) -> str:
        """Strip every key, the endpoint and the user-agent before text reaches a trace or an exception."""
        for secret in self.settings.secret_values():
            if len(secret) >= 4:
                text = text.replace(secret, "[redacted]")
        text = " ".join(text.split())
        return text[:MAX_ERROR_CHARS]

    @staticmethod
    def _final_message(slot: str, failures: list[AttemptError], key_variable: str = "IBM_ICA_API_KEY") -> str:
        last = failures[-1]
        if last.kind == "replay_miss":
            return last.message  # already says what is missing and how to record it
        if last.kind == "auth":
            return (
                f"authentication failed for slot '{slot}': check {key_variable} and "
                "IBM_ICA_ENDPOINT in backend/.env"
            )
        if last.kind in ("model_access_denied", "model_not_found") and len({f.model_id for f in failures}) >= 1:
            models = ", ".join(dict.fromkeys(f.model_id for f in failures))
            return (
                f"this API key has no access to model {models} (slot '{slot}'), and no fallback worked: "
                f"set a model your key can use in {model_env(slot)} or {fallback_env(slot)} in backend/.env"
            )
        if last.kind == "tls":
            return (
                f"the service's certificate was rejected for slot '{slot}': install certifi, or set "
                "IBM_ICA_INSECURE_TLS=true in backend/.env for local testing only"
            )
        return (
            f"model call failed for slot '{slot}' after {len(failures)} attempt(s); "
            f"last error ({last.kind}): {last.message}"
        )

    # ---- review: independence, options, and asking the user ------------------

    def independence(self, author_model: str, result: LLMResult) -> Independence:
        author_family = self.family_of(author_model)
        reviewer_family = result.family
        if author_family == UNKNOWN or reviewer_family == UNKNOWN:
            verdict = "unverified"
        elif author_family == reviewer_family:
            verdict = "same_family"
        else:
            verdict = "independent"
        return Independence(verdict, author_family, reviewer_family, result.fallback_used)

    def review_options(self, author_model: str, *, exclude: Iterable[str] = ()) -> list[ReviewerOption]:
        """Slots the user could pick to review: independent families first, then the rest."""
        author_family = self.family_of(author_model)
        excluded = set(exclude)
        # A slot sharing a model with an excluded slot would fail the same way, so drop it too.
        excluded_models = {self.slots[s].model_id.strip() for s in excluded if s in self.slots}
        excluded_models.discard("")

        order = [self.routing.reviewer_default, *self.routing.reviewer_alternatives]
        options: list[ReviewerOption] = []
        for slot in order:
            cfg = self.slots[slot]
            model = cfg.model_id.strip()
            if slot in excluded or not model or model in excluded_models:
                continue
            family = self.family_of(model)
            if UNKNOWN in (family, author_family):
                independent: bool | None = None
            else:
                independent = family != author_family
            options.append(
                ReviewerOption(
                    slot=slot, model_id=model, family=family, independent=independent,
                    price_input=cfg.price_input, price_output=cfg.price_output, priced=cfg.priced,
                )
            )
        rank = {True: 0, None: 1, False: 2}
        return sorted(options, key=lambda o: rank[o.independent])  # stable: keeps the configured order

    async def review(
        self,
        request: LLMRequest,
        *,
        author_model: str,
        slot: str | None = None,
        exclude: Iterable[str] = (),
    ) -> ReviewOutcome:
        """Run a review on Sonnet (or the slot the user picked). Never changes model on its own.

        If the reviewer cannot run, raises ReviewerUnavailable with the choices; the caller asks
        the user, then calls review() again with slot=<their choice> and exclude=<slots that failed>.
        """
        chosen = slot or self.routing.reviewer_default
        exclude = tuple(exclude)
        try:
            result = await self.complete(request, slot=chosen, allow_fallback=False)
        except SlotNotConfigured as exc:
            raise ReviewerUnavailable(
                chosen, self.review_options(author_model, exclude=(*exclude, chosen)), exc
            ) from exc
        except LLMCallFailed as exc:
            if not exc.retryable_elsewhere:
                raise
            raise ReviewerUnavailable(
                chosen, self.review_options(author_model, exclude=(*exclude, chosen)), exc
            ) from exc
        return ReviewOutcome(result=result, independence=self.independence(author_model, result))
