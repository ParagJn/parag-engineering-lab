from __future__ import annotations

import asyncio
import itertools
import logging
from dataclasses import dataclass
from typing import Any

import pytest

from app.llm.errors import (
    AuthenticationFailed,
    BadRequest,
    ContentFilterBlocked,
    LLMCallFailed,
    ProviderNotWired,
    RoutingConfigError,
    SlotNotConfigured,
    TransientProviderError,
)
from app.llm.gateway import NOT_SET, Gateway
from app.llm.providers.mock import HANG, MockProvider, MockScriptError
from app.llm.providers.unwired import UnwiredProvider
from app.llm.routing import Routing
from app.llm.types import LLMRequest, ProviderResponse, Usage

pytestmark = pytest.mark.anyio

MODELS = dict(
    ibm_ica_model_id="model-sonnet", ibm_ica_haiku_model_id="model-haiku",
    ibm_ica_openai_model_id="model-openai", ibm_ica_gemini_model_id="model-gemini",
    ibm_ica_fallback_model_id="model-sonnet", ibm_ica_haiku_fallback_model_id="model-sonnet",
    ibm_ica_openai_fallback_model_id="model-sonnet", ibm_ica_gemini_fallback_model_id="model-sonnet",
    ibm_ica_price_input_per_mtok="2", ibm_ica_price_output_per_mtok="10",
    ibm_ica_haiku_price_input_per_mtok="0.1", ibm_ica_haiku_price_output_per_mtok="0.5",
    ibm_ica_openai_price_input_per_mtok="4", ibm_ica_openai_price_output_per_mtok="20",
    ibm_ica_gemini_price_input_per_mtok="0.75", ibm_ica_gemini_price_output_per_mtok="3.75",
)

SECRET_KEY = "sk-SECRET-123456"
SECRET_ENDPOINT = "https://ica.example.invalid"


@dataclass
class Rig:
    gateway: Gateway
    provider: MockProvider
    store: Any
    project: Any
    sleeps: list[float]

    def req(self, role: str = "requirements_analyst", text: str = "hello", **kw) -> LLMRequest:
        kw.setdefault("project_id", self.project.id)
        return LLMRequest.user(role, text, **kw)

    def traces(self):
        return self.store.traces.list(self.project.id)


@pytest.fixture
def make_rig(make_settings, store, project):
    def build(**overrides) -> Rig:
        settings = make_settings(**{**MODELS, **overrides})
        provider = MockProvider()
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        ids = itertools.count(1)
        gateway = Gateway(
            settings, Routing.load(), provider, store,
            sleep=fake_sleep, call_id_factory=lambda: f"call{next(ids)}",
        )
        return Rig(gateway, provider, store, project, sleeps)

    return build


@pytest.fixture
def rig(make_rig) -> Rig:
    return make_rig()


def ok(text: str = "answer", tokens_in: int = 1000, tokens_out: int = 200) -> ProviderResponse:
    return ProviderResponse(text, Usage(tokens_in, tokens_out), "stop")


def transient(msg: str = "HTTP 503") -> TransientProviderError:
    return TransientProviderError(msg)


# ---- happy path ------------------------------------------------------------

async def test_happy_path_result_and_trace(rig):
    rig.provider.queue("model-sonnet", ok("hello back"))
    result = await rig.gateway.complete(rig.req(phase_key="requirements", run_id="run-1"))

    assert result.text == "hello back"
    assert (result.role, result.slot) == ("requirements_analyst", "sonnet")
    assert (result.requested_model, result.served_model) == ("model-sonnet", "model-sonnet")
    assert result.family == "anthropic"
    assert result.fallback_used is False and result.attempts == 1
    assert (result.tokens_in, result.tokens_out) == (1000, 200)
    assert result.cost_usd == pytest.approx(0.004)
    assert result.finish_reason == "stop"

    [trace] = rig.traces()
    assert trace.id in result.trace_ids
    assert (trace.agent, trace.slot, trace.status) == ("requirements_analyst", "sonnet", "ok")
    assert (trace.requested_model, trace.served_model, trace.fallback_used) == ("model-sonnet", "model-sonnet", False)
    assert (trace.tokens_in, trace.tokens_out) == (1000, 200)
    assert trace.cost_usd == pytest.approx(0.004)
    assert (trace.phase_key, trace.run_id) == ("requirements", "run-1")
    assert (trace.call_id, trace.attempt) == (result.call_id, 1)
    assert trace.latency_ms >= 0


async def test_each_role_reaches_its_own_model(rig):
    rig.provider.default = ok()
    for role, model in [
        ("requirements_analyst", "model-sonnet"), ("backlog_splitter", "model-haiku"),
        ("backend_developer", "model-openai"), ("ux_designer", "model-gemini"),
    ]:
        assert (await rig.gateway.complete(rig.req(role))).served_model == model


async def test_priced_by_the_slot_that_served_it(rig):
    rig.provider.default = ok("x", 1_000_000, 1_000_000)
    assert (await rig.gateway.complete(rig.req("backend_developer"))).cost_usd == pytest.approx(24.0)
    assert (await rig.gateway.complete(rig.req("backlog_splitter"))).cost_usd == pytest.approx(0.6)
    assert (await rig.gateway.complete(rig.req("ux_designer"))).cost_usd == pytest.approx(4.5)


async def test_a_blank_price_gives_unknown_cost(make_rig):
    rig = make_rig(ibm_ica_gemini_price_input_per_mtok="", ibm_ica_gemini_price_output_per_mtok="")
    rig.provider.queue("model-gemini", ok())
    result = await rig.gateway.complete(rig.req("ux_designer"))
    assert result.cost_usd is None
    assert rig.traces()[0].cost_usd is None


async def test_no_usage_reported_means_zero_tokens_unknown_cost_and_counts_as_unpriced(rig):
    rig.provider.queue("model-sonnet", ProviderResponse("x", None, None))
    result = await rig.gateway.complete(rig.req())
    assert (result.tokens_in, result.tokens_out, result.cost_usd) == (0, 0, None)
    [row] = rig.store.traces.rollup(rig.project.id, "model")
    assert row.unpriced_calls == 1 and row.cost_usd is None


async def test_overrides_and_forced_slots(rig):
    rig.provider.default = ok()
    over = {"requirements_analyst": "gemini"}
    assert (await rig.gateway.complete(rig.req(), overrides=over)).served_model == "model-gemini"
    assert (await rig.gateway.complete(rig.req(), overrides=over, slot="openai")).served_model == "model-openai"
    with pytest.raises(RoutingConfigError):
        await rig.gateway.complete(rig.req(), overrides={"janitor": "sonnet"})
    with pytest.raises(RoutingConfigError):
        await rig.gateway.complete(rig.req("janitor"))
    with pytest.raises(SlotNotConfigured):
        await rig.gateway.complete(rig.req(), slot="mistral")


# ---- retry -----------------------------------------------------------------

async def test_transient_error_is_retried_then_succeeds(rig):
    rig.provider.queue("model-sonnet", transient(), ok())
    result = await rig.gateway.complete(rig.req())
    assert result.attempts == 2 and result.fallback_used is False
    assert rig.sleeps == [1.0]
    traces = rig.traces()
    assert [(t.attempt, t.status) for t in traces] == [(1, "error"), (2, "ok")]
    assert len({t.call_id for t in traces}) == 1
    assert traces[0].error.startswith("transient: ") and "503" in traces[0].error
    assert traces[0].tokens_in == 0 and traces[0].cost_usd is None


async def test_backoff_doubles_and_is_capped(make_rig):
    rig = make_rig(llm_max_retries=3, llm_retry_backoff_seconds=1)
    rig.provider.queue("model-sonnet", transient(), transient(), transient(), transient())
    with pytest.raises(LLMCallFailed):
        await rig.gateway.complete(rig.req())
    assert rig.sleeps == [1.0, 2.0, 4.0]

    rig = make_rig(llm_max_retries=3, llm_retry_backoff_seconds=8)
    rig.provider.queue("model-sonnet", transient(), transient(), transient(), transient())
    with pytest.raises(LLMCallFailed):
        await rig.gateway.complete(rig.req())
    assert rig.sleeps == [8.0, 10.0, 10.0]


async def test_zero_retries_means_one_attempt(make_rig):
    rig = make_rig(llm_max_retries=0)
    rig.provider.queue("model-sonnet", transient(), ok())
    with pytest.raises(LLMCallFailed) as exc:
        await rig.gateway.complete(rig.req())
    assert len(exc.value.attempts) == 1
    assert len(rig.provider.calls) == 1 and rig.sleeps == []


async def test_sonnet_slot_makes_exactly_one_plus_retries_attempts_and_never_falls_back(rig):
    rig.provider.queue("model-sonnet", transient(), transient(), ok())
    with pytest.raises(LLMCallFailed) as exc:
        await rig.gateway.complete(rig.req())
    assert rig.provider.models == ["model-sonnet", "model-sonnet"]
    assert len(exc.value.attempts) == 2
    assert all(not t.fallback_used for t in rig.traces())


# ---- fallback --------------------------------------------------------------

async def test_retries_exhausted_then_the_fallback_serves(rig):
    rig.provider.queue("model-openai", transient(), transient())
    rig.provider.queue("model-sonnet", ok("from sonnet", 1000, 200))
    result = await rig.gateway.complete(rig.req("backend_developer"))

    assert rig.provider.models == ["model-openai", "model-openai", "model-sonnet"]
    assert result.served_model == "model-sonnet" and result.fallback_used is True
    assert result.requested_model == "model-openai"
    assert result.attempts == 3
    assert result.cost_usd == pytest.approx(0.004)  # Sonnet's rates, not OpenAI's
    assert rig.sleeps == [1.0]  # backoff only between retries of the same model

    traces = rig.traces()
    assert [(t.status, t.served_model, t.fallback_used) for t in traces] == [
        ("error", "model-openai", False), ("error", "model-openai", False), ("ok", "model-sonnet", True),
    ]
    assert all(t.requested_model == "model-openai" and t.slot == "openai" for t in traces)
    assert len({t.call_id for t in traces}) == 1
    assert [t.attempt for t in traces] == [1, 2, 3]


async def test_fallback_that_also_fails_lists_every_attempt(rig):
    rig.provider.queue("model-openai", transient(), transient())
    rig.provider.queue("model-sonnet", transient("first"), transient("second"))
    with pytest.raises(LLMCallFailed) as exc:
        await rig.gateway.complete(rig.req("backend_developer"))
    assert [a.model_id for a in exc.value.attempts] == ["model-openai"] * 2 + ["model-sonnet"] * 2
    assert "4 attempt" in str(exc.value)
    assert [t.status for t in rig.traces()] == ["error"] * 4


async def test_content_filter_skips_same_model_retry_and_falls_back_at_once(rig):
    rig.provider.queue("model-openai", ContentFilterBlocked("blocked"))
    rig.provider.queue("model-sonnet", ok())
    result = await rig.gateway.complete(rig.req("backend_developer"))
    assert rig.provider.models == ["model-openai", "model-sonnet"]
    assert result.fallback_used is True and rig.sleeps == []
    assert rig.traces()[0].error.startswith("content_filter: ")


async def test_content_filter_on_the_sonnet_slot_fails_after_one_attempt(rig):
    rig.provider.queue("model-sonnet", ContentFilterBlocked("blocked"), ok())
    with pytest.raises(LLMCallFailed) as exc:
        await rig.gateway.complete(rig.req())
    assert rig.provider.models == ["model-sonnet"]
    assert exc.value.retryable_elsewhere is True


@pytest.mark.parametrize("error_type", [AuthenticationFailed, BadRequest])
async def test_auth_and_bad_request_never_retry_or_fall_back(rig, error_type):
    rig.provider.queue("model-openai", error_type("nope"), ok())
    rig.provider.queue("model-sonnet", ok())
    with pytest.raises(LLMCallFailed) as exc:
        await rig.gateway.complete(rig.req("backend_developer"))
    assert rig.provider.models == ["model-openai"]
    assert exc.value.retryable_elsewhere is False
    [trace] = rig.traces()
    assert trace.status == "error"


async def test_auth_failure_names_the_variables_and_hides_their_values(make_rig):
    rig = make_rig(ibm_ica_api_key=SECRET_KEY, ibm_ica_endpoint=SECRET_ENDPOINT)
    rig.provider.queue(
        "model-openai", AuthenticationFailed(f"401 from {SECRET_ENDPOINT} for key {SECRET_KEY}")
    )
    with pytest.raises(LLMCallFailed) as exc:
        await rig.gateway.complete(rig.req("backend_developer"))
    assert "IBM_ICA_API_KEY" in str(exc.value) and "IBM_ICA_ENDPOINT" in str(exc.value)
    everything = str(exc.value) + repr(exc.value.attempts) + " ".join(t.error for t in rig.traces())
    assert SECRET_KEY not in everything and SECRET_ENDPOINT not in everything
    assert "[redacted]" in rig.traces()[0].error


async def test_error_text_is_truncated(rig):
    rig.provider.queue("model-sonnet", BadRequest("x" * 5000))
    with pytest.raises(LLMCallFailed):
        await rig.gateway.complete(rig.req())
    assert len(rig.traces()[0].error) < 560


# ---- blank slots -----------------------------------------------------------

async def test_a_blank_model_goes_straight_to_the_fallback(make_rig):
    rig = make_rig(ibm_ica_haiku_model_id="")
    rig.provider.queue("model-sonnet", ok())
    result = await rig.gateway.complete(rig.req("backlog_splitter"))
    assert result.served_model == "model-sonnet"
    assert result.fallback_used is True and result.requested_model == NOT_SET
    assert rig.provider.models == ["model-sonnet"]
    assert rig.traces()[0].requested_model == NOT_SET


async def test_a_slot_with_no_model_and_no_fallback_fails_before_any_call_or_trace(make_rig):
    rig = make_rig(ibm_ica_haiku_model_id="", ibm_ica_haiku_fallback_model_id="")
    with pytest.raises(SlotNotConfigured, match="IBM_ICA_HAIKU_MODEL_ID|haiku"):
        await rig.gateway.complete(rig.req("backlog_splitter"))
    assert rig.provider.calls == []
    assert rig.store.traces.list() == []


# ---- timeout, cancellation, bugs -------------------------------------------

async def test_a_hang_is_cut_off_at_the_timeout_and_retried(make_rig):
    rig = make_rig(llm_timeout_seconds=0.05)
    rig.provider.queue("model-sonnet", HANG, ok())
    result = await rig.gateway.complete(rig.req())
    assert result.attempts == 2
    first, second = rig.traces()
    assert first.status == "error" and "no answer within" in first.error
    assert second.status == "ok"


async def test_cancellation_propagates_with_no_trace_and_no_retry(rig):
    rig.provider.queue("model-sonnet", HANG, ok())
    task = asyncio.ensure_future(rig.gateway.complete(rig.req()))
    await asyncio.wait_for(rig.provider.entered.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert rig.provider.models == ["model-sonnet"]
    assert rig.traces() == [] and rig.sleeps == []


async def test_an_unexpected_exception_is_traced_and_reraised_unchanged(rig):
    boom = ValueError("a bug in our code")
    rig.provider.queue("model-sonnet", boom, ok())
    with pytest.raises(ValueError) as exc:
        await rig.gateway.complete(rig.req())
    assert exc.value is boom
    assert rig.provider.models == ["model-sonnet"]
    [trace] = rig.traces()
    assert trace.status == "error" and trace.error.startswith("unexpected: ValueError")


async def test_the_unwired_provider_fails_clearly(make_settings, store, project):
    gateway = Gateway(make_settings(**MODELS), Routing.load(), UnwiredProvider(), store)
    with pytest.raises(ProviderNotWired):
        await gateway.complete(LLMRequest.user("orchestrator", "hi", project_id=project.id))


# ---- traces ----------------------------------------------------------------

async def test_a_failed_trace_write_never_loses_the_answer(rig, monkeypatch, caplog):
    def broken(**kwargs):
        raise RuntimeError("database is down")

    monkeypatch.setattr(rig.store.traces, "record", broken)
    rig.provider.queue("model-sonnet", ok("paid for"))
    with caplog.at_level(logging.WARNING):
        result = await rig.gateway.complete(rig.req())
    assert result.text == "paid for" and result.trace_ids == ()
    assert any("could not write a trace" in r.message for r in caplog.records)


async def test_five_calls_run_inside_the_provider_at_the_same_time(rig):
    rig.provider.barrier = asyncio.Barrier(5)  # a serial gateway would wait here forever
    rig.provider.default = ok()
    results = await asyncio.wait_for(
        asyncio.gather(*(rig.gateway.complete(rig.req()) for _ in range(5))), timeout=10
    )
    assert len({r.call_id for r in results}) == 5
    ids = [i for r in results for i in r.trace_ids]
    assert len(ids) == 5 == len(set(ids))
    assert len(rig.traces()) == 5


async def test_prompts_and_responses_never_reach_the_database(rig, tmp_path):
    prompt_marker, reply_marker, control = "PROMPT-SENTINEL-8841", "REPLY-SENTINEL-2207", "CONTROL-SENTINEL-5519"
    rig.provider.queue("model-sonnet", transient("oops"), ok(reply_marker))  # one failed attempt, then success
    await rig.gateway.complete(rig.req(text=f"please handle {prompt_marker}"))
    rig.store.memory.add(rig.project.id, "note", control, actor="system")  # proves the scan can find text

    blob = b""
    for path in rig.store.db.path.parent.glob(rig.store.db.path.name + "*"):  # db, -wal, -shm
        blob += path.read_bytes()
    assert control.encode() in blob
    assert prompt_marker.encode() not in blob
    assert reply_marker.encode() not in blob


# ---- the mock itself -------------------------------------------------------

async def test_mock_provider_consumes_its_script_in_order_and_records_requests(make_settings):
    provider = MockProvider({"m": ["first", ok("second")]})
    request = LLMRequest.user("orchestrator", "abcd" * 10, system="sys")
    a = await provider.complete("m", request)
    b = await provider.complete("m", request)
    assert (a.text, b.text) == ("first", "second")
    assert a.usage == Usage(11, 2)  # ceil(43/4) and ceil(5/4): a deterministic estimate
    assert provider.models == ["m", "m"] and provider.calls[0].request is request


async def test_mock_provider_complains_when_nothing_is_scripted():
    with pytest.raises(MockScriptError, match="m"):
        await MockProvider().complete("m", LLMRequest.user("orchestrator", "x"))
    assert (await MockProvider(default="fallback text").complete("m", LLMRequest.user("o", "x"))).text == "fallback text"
