"""The real IcaProvider driven through the real Gateway, over a fake network."""
from __future__ import annotations

import asyncio
import itertools

import httpx
import pytest
from fastapi.testclient import TestClient

from app.llm.errors import LLMCallFailed, ReviewerUnavailable
from app.llm.gateway import Gateway
from app.llm.providers.ica import IcaProvider
from app.llm.routing import Routing
from app.llm.types import LLMRequest
from app.main import choose_provider, create_app

from .test_gateway import MODELS
from .test_ica_provider import ENDPOINT, KEY, AGENT, Recorder, err, reply

pytestmark = pytest.mark.anyio


class ByModel:
    """A fake network that answers by the model named in the request body."""

    def __init__(self, plan: dict):
        self.plan = {model: list(outcomes) for model, outcomes in plan.items()}
        self.seen: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        import json

        model = json.loads(request.content)["model"]
        self.seen.append(model)
        queue = self.plan[model]
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome if isinstance(outcome, httpx.Response) else httpx.Response(200, json=outcome)


@pytest.fixture
def build(make_settings, store, project):
    def make(plan: dict, **settings):
        net = ByModel(plan)
        cfg = make_settings(
            **{**MODELS, "ibm_ica_endpoint": ENDPOINT, "ibm_ica_api_key": KEY, "ibm_ica_user_agent": AGENT, **settings}
        )
        provider = IcaProvider(cfg, transport=httpx.MockTransport(net))
        slept: list[float] = []

        async def fake_sleep(seconds):
            slept.append(seconds)

        ids = itertools.count(1)
        gateway = Gateway(cfg, Routing.load(), provider, store, sleep=fake_sleep, call_id_factory=lambda: f"c{next(ids)}")
        return gateway, net, slept

    return make


def req(project, role="backend_developer", text="hi") -> LLMRequest:
    return LLMRequest.user(role, text, project_id=project.id)


async def test_a_missing_openai_model_falls_back_to_sonnet_and_is_priced_as_sonnet(build, store, project):
    gateway, net, slept = build({
        "model-openai": [err(404, message="model not found")],
        "model-sonnet": [reply("from sonnet", usage={"prompt_tokens": 1000, "completion_tokens": 200})],
    })
    result = await gateway.complete(req(project))
    assert net.seen == ["model-openai", "model-sonnet"] and slept == []  # 404 is not retried on the same model
    assert result.served_model == "model-sonnet" and result.fallback_used is True
    assert result.cost_usd == pytest.approx(0.004)
    traces = store.traces.list(project.id)
    assert [(t.status, t.served_model) for t in traces] == [("error", "model-openai"), ("ok", "model-sonnet")]
    assert traces[0].error.startswith("model_not_found: ")


async def test_a_model_the_key_may_not_use_falls_back_instead_of_blaming_the_key(build, store, project):
    """The real live-check failure: 403 team_model_access_denied for one model, while other models work."""
    from .test_ica_provider import REAL_MODEL_ACCESS_DENIED

    gateway, net, slept = build({
        "model-openai": [REAL_MODEL_ACCESS_DENIED],
        "model-sonnet": [reply("from sonnet", usage={"prompt_tokens": 1000, "completion_tokens": 200})],
    })
    result = await gateway.complete(req(project))
    assert net.seen == ["model-openai", "model-sonnet"] and slept == []  # no retry of a model that is off limits
    assert result.fallback_used is True and result.served_model == "model-sonnet"
    assert result.cost_usd == pytest.approx(0.004)
    first = store.traces.list(project.id)[0]
    assert first.error.startswith("model_access_denied: ") and "auth" not in first.error.split(":")[0]


async def test_if_nothing_works_the_message_points_at_the_model_not_the_key(build, project):
    from .test_ica_provider import REAL_MODEL_ACCESS_DENIED

    gateway, _, _ = build({"model-openai": [REAL_MODEL_ACCESS_DENIED], "model-sonnet": [REAL_MODEL_ACCESS_DENIED]})
    with pytest.raises(LLMCallFailed) as exc:
        await gateway.complete(req(project))
    message = str(exc.value)
    assert "no access to model" in message
    assert "IBM_ICA_OPENAI_MODEL_ID" in message and "IBM_ICA_OPENAI_FALLBACK_MODEL_ID" in message  # the slot's own names
    assert "model-openai" in message and "model-sonnet" in message  # both models that were tried
    assert "IBM_ICA_API_KEY" not in message  # the key is fine; do not send the user hunting for it


async def test_a_reviewer_the_key_may_not_use_asks_the_user(build, project):
    from .test_ica_provider import REAL_MODEL_ACCESS_DENIED

    gateway, _, _ = build({"model-openai": [REAL_MODEL_ACCESS_DENIED]})
    with pytest.raises(ReviewerUnavailable) as exc:
        await gateway.review(
            LLMRequest.user("security_reviewer", "review", project_id=project.id),
            author_model="model-sonnet", slot="openai",
        )
    assert exc.value.slot == "openai" and "openai" not in [o.slot for o in exc.value.options]


async def test_a_bad_key_stops_at_once_and_hides_every_secret(build, store, project):
    gateway, net, _ = build({"model-openai": [err(401, message=f"bad key {KEY} at {ENDPOINT}")], "model-sonnet": [reply()]})
    with pytest.raises(LLMCallFailed) as exc:
        await gateway.complete(req(project))
    assert net.seen == ["model-openai"]
    stored = " ".join(t.error for t in store.traces.list(project.id))
    for secret in (KEY, ENDPOINT):
        assert secret not in stored and secret not in str(exc.value) and secret not in repr(exc.value.attempts)
    assert "IBM_ICA_API_KEY" in str(exc.value)


async def test_a_certificate_failure_stops_at_once_with_advice(build, project):
    gateway, net, _ = build({"model-openai": [httpx.ConnectError("[SSL: CERTIFICATE_VERIFY_FAILED] bad")], "model-sonnet": [reply()]})
    with pytest.raises(LLMCallFailed, match="IBM_ICA_INSECURE_TLS|certifi"):
        await gateway.complete(req(project))
    assert net.seen == ["model-openai"]


async def test_an_empty_reply_falls_back(build, store, project):
    gateway, net, _ = build({"model-openai": [reply("")], "model-sonnet": [reply("real answer")]})
    result = await gateway.complete(req(project))
    assert result.text == "real answer" and net.seen == ["model-openai", "model-sonnet"]
    assert store.traces.list(project.id)[0].error.startswith("bad_response: ")


async def test_a_503_then_a_200_is_retried_on_the_same_model(build, project):
    gateway, net, slept = build({"model-openai": [err(503), reply("fine")]})
    result = await gateway.complete(req(project))
    assert net.seen == ["model-openai", "model-openai"] and result.fallback_used is False and slept == [1.0]


async def test_cost_is_computed_from_the_parsed_usage_end_to_end(build, project):
    gateway, _, _ = build({"model-openai": [reply("x", usage={"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000})]})
    assert (await gateway.complete(req(project))).cost_usd == pytest.approx(24.0)


async def test_missing_usage_end_to_end_means_unknown_cost(build, project):
    gateway, _, _ = build({"model-openai": [{"choices": [{"message": {"content": "x"}, "finish_reason": "stop"}]}]})
    result = await gateway.complete(req(project))
    assert (result.tokens_in, result.tokens_out, result.cost_usd) == (0, 0, None)


async def test_a_reviewer_whose_model_is_not_found_asks_the_user(build, project):
    gateway, _, _ = build({"model-sonnet": [err(404, message="model not found")]})
    with pytest.raises(ReviewerUnavailable) as exc:
        await gateway.review(LLMRequest.user("security_reviewer", "review", project_id=project.id), author_model="model-openai")
    assert exc.value.slot == "sonnet" and exc.value.options


async def test_six_calls_are_in_flight_through_the_real_provider_at_once(make_settings, store, project):
    barrier = asyncio.Barrier(6)

    async def handler(request: httpx.Request) -> httpx.Response:
        await barrier.wait()  # a provider that serialised calls would hang here
        return httpx.Response(200, json=reply())

    cfg = make_settings(**{**MODELS, "ibm_ica_endpoint": ENDPOINT, "ibm_ica_api_key": KEY})
    provider = IcaProvider(cfg, transport=httpx.MockTransport(handler))
    gateway = Gateway(cfg, Routing.load(), provider, store)
    results = await asyncio.wait_for(
        asyncio.gather(*(gateway.complete(req(project, "requirements_analyst")) for _ in range(6))), timeout=10
    )
    assert len({r.call_id for r in results}) == 6


# ---- wiring ----------------------------------------------------------------

def test_provider_choice(make_settings):
    both = dict(ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY)
    assert isinstance(choose_provider(make_settings(app_mode="live", **both)), IcaProvider)
    for cfg in (
        make_settings(app_mode="live"),
        make_settings(app_mode="live", ibm_ica_endpoint=ENDPOINT),
        make_settings(app_mode="live", ibm_ica_api_key=KEY),
    ):
        assert choose_provider(cfg).label.startswith("none")  # live without credentials stays unwired
    # Replay is a real provider now (S04) and needs no credentials, whether or not any are set.
    assert choose_provider(make_settings(app_mode="replay", **both)).label == "replay"
    assert choose_provider(make_settings(app_mode="replay")).label == "replay"


def test_the_page_reports_the_ica_provider_in_live_mode(make_settings):
    app = create_app(make_settings(app_mode="live", ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY, **MODELS))
    with TestClient(app) as client:  # runs startup and shutdown
        assert client.get("/api/status").json()["gateway"]["provider"] == "ica"


def test_shutdown_closes_the_http_client(make_settings):
    app = create_app(make_settings(app_mode="live", ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY))
    provider = app.state.gateway.provider
    with TestClient(app):
        assert not provider.client.is_closed
    assert provider.client.is_closed


def test_insecure_tls_is_a_problem_in_live_mode_only(make_settings):
    live = create_app(make_settings(
        app_mode="live", ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY, ibm_ica_insecure_tls=True, **MODELS))
    problems = TestClient(live).get("/api/status").json()["gateway"]["problems"]
    assert any("IBM_ICA_INSECURE_TLS" in p for p in problems)
    replay = create_app(make_settings(ibm_ica_insecure_tls=True))
    assert TestClient(replay).get("/api/status").json()["gateway"]["problems"] == []
