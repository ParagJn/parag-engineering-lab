"""Recording and replay as providers, and through the real gateway."""
from __future__ import annotations

import asyncio
import itertools
import logging

import pytest
from fastapi.testclient import TestClient

from app.llm.errors import LLMCallFailed, ReplayMiss, ReviewerUnavailable, TransientProviderError
from app.llm.gateway import Gateway
from app.llm.providers.mock import MockProvider
from app.llm.providers.recording import RecordingProvider, ReplayProvider
from app.llm.recordings import RecordingStore, request_key
from app.llm.routing import Routing
from app.llm.types import LLMRequest, ProviderResponse, Usage
from app.main import choose_provider, create_app

from .test_gateway import MODELS, SECRET_ENDPOINT, SECRET_KEY, ok

pytestmark = pytest.mark.anyio

OPENAI_KEY = "sk-OPENAI-ONLY-998877"


def req(text="hello", role="requirements_analyst", **kw) -> LLMRequest:
    return LLMRequest.user(role, text, **kw)


class Boom:
    """A provider that fails the test if it is ever touched: proves replay never uses the network."""

    label = "boom"

    async def complete(self, model_id, request):
        raise AssertionError("the network provider was used during replay")


def settings(make_settings, **kw):
    return make_settings(**{**MODELS, "ibm_ica_endpoint": SECRET_ENDPOINT, "ibm_ica_api_key": SECRET_KEY,
                            "ibm_ica_openai_api_key": OPENAI_KEY, **kw})


# ---- RecordingProvider --------------------------------------------------------

async def test_the_reply_is_returned_unchanged_and_saved_under_the_model_actually_called(make_settings, tmp_path):
    store = RecordingStore(tmp_path)
    inner = MockProvider({"model-x": [ProviderResponse("the answer", Usage(7, 3), "stop")]})
    provider = RecordingProvider(inner, store, settings(make_settings))
    got = await provider.complete("model-x", req("q?"))
    assert got == ProviderResponse("the answer", Usage(7, 3), "stop")
    saved = store.get(request_key("model-x", req("q?")))
    assert saved.model == "model-x" and saved.text == "the answer" and saved.usage == Usage(7, 3)
    assert saved.role == "requirements_analyst" and saved.latency_ms >= 0
    assert store.get(request_key("another-model", req("q?"))) is None  # only the model that answered


async def test_errors_pass_through_and_are_not_recorded(make_settings, tmp_path):
    store = RecordingStore(tmp_path)
    inner = MockProvider({"m": [TransientProviderError("503")]})
    with pytest.raises(TransientProviderError):
        await RecordingProvider(inner, store, settings(make_settings)).complete("m", req())
    assert len(store) == 0 and list(tmp_path.glob("*")) == []


async def test_a_save_failure_is_logged_and_the_reply_still_returned(make_settings, tmp_path, caplog, monkeypatch):
    store = RecordingStore(tmp_path)

    def broken(recording):
        raise OSError("disk full")

    monkeypatch.setattr(store, "save", broken)
    provider = RecordingProvider(MockProvider({"m": ["paid for"]}), store, settings(make_settings))
    with caplog.at_level(logging.WARNING):
        got = await provider.complete("m", req())
    assert got.text == "paid for"
    assert any("could not save a recording" in r.message for r in caplog.records)


async def test_saving_happens_off_the_event_loop(make_settings, tmp_path, monkeypatch):
    import threading

    store = RecordingStore(tmp_path)
    seen = []
    real = store.save
    monkeypatch.setattr(store, "save", lambda r: (seen.append(threading.current_thread()), real(r))[1])
    await RecordingProvider(MockProvider({"m": ["x"]}), store, settings(make_settings)).complete("m", req())
    assert seen and seen[0] is not threading.main_thread()


@pytest.mark.parametrize("where", ["prompt", "system", "reply"])
@pytest.mark.parametrize("secret_name", ["key", "openai", "endpoint", "agent"])
async def test_an_entry_containing_a_credential_is_not_written_and_the_value_is_not_logged(
    make_settings, tmp_path, caplog, where, secret_name
):
    secrets = {"key": SECRET_KEY, "openai": OPENAI_KEY, "endpoint": SECRET_ENDPOINT, "agent": "UA-unique-string-1234"}
    secret = secrets[secret_name]
    cfg = settings(make_settings, ibm_ica_user_agent="UA-unique-string-1234")
    store = RecordingStore(tmp_path)
    request = req(f"use {secret}" if where == "prompt" else "plain", system=f"x {secret}" if where == "system" else "")
    reply = f"echo {secret}" if where == "reply" else "fine"
    with caplog.at_level(logging.WARNING):
        got = await RecordingProvider(MockProvider({"m": [reply]}), store, cfg).complete("m", request)
    assert got.text == reply  # the live reply is unaffected
    assert len(store) == 0 and list(tmp_path.glob("*.json")) == []
    assert any("contains a configured credential" in r.message for r in caplog.records)
    assert secret not in caplog.text


async def test_an_empty_reply_is_not_recorded(make_settings, tmp_path):
    store = RecordingStore(tmp_path)
    await RecordingProvider(MockProvider({"m": [ProviderResponse("  ", None, None)]}), store, settings(make_settings)).complete("m", req())
    assert len(store) == 0


def test_the_recording_provider_labels_itself_and_closes_what_it_wraps(make_settings, tmp_path):
    class Closable(MockProvider):
        closed = False

        async def aclose(self):
            self.closed = True

    inner = Closable()
    provider = RecordingProvider(inner, RecordingStore(tmp_path), settings(make_settings))
    assert provider.label == "mock+recording"
    asyncio.run(provider.aclose())
    assert inner.closed


# ---- ReplayProvider ------------------------------------------------------------

def recorded(tmp_path, model="m", text="hello", reply="recorded reply", usage=Usage(1000, 200), latency=4000):
    from app.llm.recordings import Recording

    store = RecordingStore(tmp_path)
    store.save(Recording.from_call(model, req(text), ProviderResponse(reply, usage, "stop"), latency))
    return store


async def test_a_hit_returns_exactly_what_was_recorded(tmp_path):
    provider = ReplayProvider(recorded(tmp_path))
    got = await provider.complete("m", req())
    assert got == ProviderResponse("recorded reply", Usage(1000, 200), "stop")


async def test_a_hit_does_not_depend_on_role_or_project(tmp_path):
    provider = ReplayProvider(recorded(tmp_path))
    got = await provider.complete("m", req(role="backend_developer", project_id="brand-new-project", run_id="r2"))
    assert got.text == "recorded reply"


async def test_a_miss_is_a_clear_error_naming_role_model_and_how_to_record(tmp_path):
    provider = ReplayProvider(recorded(tmp_path))
    with pytest.raises(ReplayMiss) as exc:
        await provider.complete("m", req("a different question", role="solution_architect"))
    message = str(exc.value)
    assert "solution_architect" in message and "'m'" in message
    assert request_key("m", req("a different question"))[:12] in message
    assert "1 recording(s) exist for this model" in message
    assert "RECORD_LIVE_CALLS=true" in message
    assert "a different question" not in message  # never echo the prompt


@pytest.mark.parametrize(
    "changed",
    [
        dict(model="other-model"),
        dict(text="hello!"),
        dict(max_tokens=100),
        dict(temperature=0.7),
        dict(system="now with a system prompt"),
    ],
)
async def test_near_misses_are_misses(tmp_path, changed):
    provider = ReplayProvider(recorded(tmp_path))
    model = changed.pop("model", "m")
    text = changed.pop("text", "hello")
    with pytest.raises(ReplayMiss):
        await provider.complete(model, LLMRequest.user("r", text, **changed))


async def test_pacing_waits_a_fraction_of_the_recorded_latency(tmp_path):
    slept: list[float] = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    store = recorded(tmp_path, latency=4000)
    await ReplayProvider(store, pace=0.0, sleep=fake_sleep).complete("m", req())
    assert slept == []  # instant by default
    await ReplayProvider(store, pace=0.25, sleep=fake_sleep).complete("m", req())
    assert slept == [1.0]
    await ReplayProvider(store, pace=1.0, sleep=fake_sleep).complete("m", req())
    assert slept == [1.0, 4.0]


async def test_pacing_is_capped_and_a_zero_latency_never_sleeps(tmp_path):
    slept: list[float] = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    await ReplayProvider(recorded(tmp_path / "slow", latency=10_000_000), pace=1.0, sleep=fake_sleep).complete("m", req())
    assert slept == [60.0]
    slept.clear()
    await ReplayProvider(recorded(tmp_path / "instant", latency=0), pace=1.0, sleep=fake_sleep).complete("m", req())
    assert slept == []


async def test_a_replay_store_is_a_snapshot_taken_when_it_is_opened(tmp_path):
    """The bug the round-trip script exposed: a store loads its folder once, when it is created.
    The script opened its replay store before recording anything, so every replay missed."""
    from app.llm.recordings import Recording

    early = RecordingStore(tmp_path / "set")  # the folder does not exist yet
    provider = ReplayProvider(early)
    RecordingStore(tmp_path / "set").save(
        Recording.from_call("m", req(), ProviderResponse("later", Usage(1, 1), "stop"), 5)
    )
    with pytest.raises(ReplayMiss):
        await provider.complete("m", req())  # by design: replay never changes under a running demo
    early.load()
    assert (await provider.complete("m", req())).text == "later"
    # A store opened after recording sees it straight away, which is what the script now does.
    assert (await ReplayProvider(RecordingStore(tmp_path / "set")).complete("m", req())).text == "later"


# ---- through the gateway ---------------------------------------------------------

@pytest.fixture
def make_gateway(make_settings, store):
    def build(provider, **kw):
        cfg = settings(make_settings, **kw)
        ids = itertools.count(1)
        slept: list[float] = []

        async def no_sleep(seconds):
            slept.append(seconds)

        return Gateway(cfg, Routing.load(), provider, store, sleep=no_sleep, call_id_factory=lambda: f"c{next(ids)}"), slept

    return build


async def test_replay_through_the_gateway_recomputes_cost_at_todays_prices_and_writes_a_normal_trace(
    make_gateway, tmp_path, project, store
):
    folder = recorded(tmp_path, model="model-sonnet", usage=Usage(1_000_000, 1_000_000))
    gateway, _ = make_gateway(ReplayProvider(folder))
    result = await gateway.complete(req(project_id=project.id, phase_key="requirements"))

    assert result.text == "recorded reply" and result.served_model == "model-sonnet"
    assert result.cost_usd == pytest.approx(12.0)  # 2 + 10 per million, the *configured* prices
    assert (result.tokens_in, result.tokens_out, result.attempts, result.fallback_used) == (1_000_000, 1_000_000, 1, False)
    assert result.family == "anthropic"
    [trace] = store.traces.list(project.id)
    assert (trace.status, trace.served_model, trace.tokens_in, trace.phase_key) == ("ok", "model-sonnet", 1_000_000, "requirements")


async def test_a_price_change_between_recording_and_replay_changes_the_cost(make_gateway, tmp_path, project):
    folder = recorded(tmp_path, model="model-sonnet", usage=Usage(1_000_000, 0))
    gateway, _ = make_gateway(ReplayProvider(folder), ibm_ica_price_input_per_mtok="5")
    assert (await gateway.complete(req(project_id=project.id))).cost_usd == pytest.approx(5.0)


async def test_a_miss_is_final_and_never_tries_a_fallback_model(make_gateway, tmp_path, project, store):
    class Spy(ReplayProvider):
        asked: list[str] = []

        async def complete(self, model_id, request):
            self.asked.append(model_id)
            return await super().complete(model_id, request)

    folder = recorded(tmp_path, model="model-sonnet", text="hello")  # a recording exists for the FALLBACK model
    spy = Spy(folder)
    gateway, slept = make_gateway(spy)
    with pytest.raises(LLMCallFailed) as exc:
        await gateway.complete(req(role="backend_developer", project_id=project.id))  # OpenAI slot, falls back to Sonnet
    assert spy.asked == ["model-openai"]  # the Sonnet recording was never consulted
    assert slept == [] and len(exc.value.attempts) == 1 and exc.value.attempts[0].kind == "replay_miss"
    assert "model-openai" in str(exc.value) and "RECORD_LIVE_CALLS" in str(exc.value)
    [trace] = store.traces.list(project.id)
    assert trace.status == "error" and trace.error.startswith("replay_miss: ")
    assert exc.value.retryable_elsewhere is False


async def test_a_miss_in_the_reviewer_path_fails_with_the_message_instead_of_offering_other_families(
    make_gateway, tmp_path, project
):
    gateway, _ = make_gateway(ReplayProvider(RecordingStore(tmp_path)))
    with pytest.raises(LLMCallFailed) as exc:
        await gateway.review(req(role="security_reviewer", project_id=project.id), author_model="model-openai")
    assert not isinstance(exc.value, ReviewerUnavailable) and "recording" in str(exc.value)


# ---- record, then replay, end to end -------------------------------------------------

async def test_record_live_then_replay_gives_identical_text_tokens_and_cost_with_zero_provider_calls(
    make_settings, tmp_path, project, store
):
    cfg = settings(make_settings)
    folder = tmp_path / "set"
    live = MockProvider(default="the live answer")
    recorder = RecordingProvider(live, RecordingStore(folder), cfg)
    gateway = Gateway(cfg, Routing.load(), recorder, store)
    roles = ["requirements_analyst", "backlog_splitter", "backend_developer", "ux_designer"]
    first = [await gateway.complete(req(f"prompt for {r}", role=r, project_id=project.id)) for r in roles]
    assert len(live.calls) == 4 and len(list(folder.glob("*.json"))) == 4

    replay_gateway = Gateway(cfg, Routing.load(), ReplayProvider(RecordingStore(folder)), store)
    # A different project id and run id: replay must not care.
    second = [await replay_gateway.complete(req(f"prompt for {r}", role=r, project_id=project.id, run_id="new-run")) for r in roles]
    for a, b in zip(first, second):
        assert (a.text, a.tokens_in, a.tokens_out, a.cost_usd, a.served_model, a.slot) == (
            b.text, b.tokens_in, b.tokens_out, b.cost_usd, b.served_model, b.slot)
    assert [r.served_model for r in second] == ["model-sonnet", "model-haiku", "model-openai", "model-gemini"]
    assert len(live.calls) == 4  # unchanged: replay made no new live calls


async def test_a_fresh_app_in_replay_mode_replays_what_another_app_recorded(make_settings, tmp_path):
    folder = tmp_path / "rec"
    cfg_live = settings(make_settings, app_mode="live", record_live_calls=True, recordings_dir=str(folder), replay_set="s1")
    live = MockProvider(default="recorded in live mode")
    app_live = create_app(cfg_live, provider=RecordingProvider(live, RecordingStore(cfg_live.recordings_path), cfg_live))
    await app_live.state.gateway.complete(LLMRequest.user("orchestrator", "same prompt"))

    cfg_replay = settings(make_settings, app_mode="replay", recordings_dir=str(folder), replay_set="s1")
    app_replay = create_app(cfg_replay, provider=None)
    assert app_replay.state.gateway.provider.label == "replay"
    result = await app_replay.state.gateway.complete(LLMRequest.user("orchestrator", "same prompt"))
    assert result.text == "recorded in live mode" and len(live.calls) == 1


# ---- which provider the app uses ---------------------------------------------------------

def test_provider_selection_rows(make_settings):
    creds = dict(ibm_ica_endpoint=SECRET_ENDPOINT, ibm_ica_api_key=SECRET_KEY)
    assert choose_provider(make_settings(app_mode="replay")).label == "replay"
    assert choose_provider(make_settings(app_mode="replay", record_live_calls=True, **creds)).label == "replay"
    assert choose_provider(make_settings(app_mode="live", **creds)).label == "ica"
    assert choose_provider(make_settings(app_mode="live", record_live_calls=True, **creds)).label == "ica+recording"
    assert choose_provider(make_settings(app_mode="live", record_live_calls=True)).label.startswith("none")
    assert choose_provider(make_settings(app_mode="live")).label.startswith("none")


def test_pace_setting_reaches_the_replay_provider(make_settings):
    assert choose_provider(make_settings(app_mode="replay", replay_pace=0.25)).pace == 0.25


def test_replay_mode_needs_no_credentials_at_all(make_settings):
    app = create_app(make_settings(app_mode="replay"))
    assert TestClient(app).get("/api/status").json()["gateway"]["provider"] == "replay"


def test_the_recording_provider_is_closed_on_shutdown(make_settings):
    cfg = settings(make_settings, app_mode="live", record_live_calls=True)
    app = create_app(cfg)
    inner = app.state.gateway.provider.inner
    with TestClient(app):
        assert not inner.client.is_closed
    assert inner.client.is_closed


# ---- status ------------------------------------------------------------------------

def block(make_settings, **kw) -> dict:
    return TestClient(create_app(settings(make_settings, **kw))).get("/api/status").json()["gateway"]


def test_status_for_replay_with_no_recordings_is_ok_not_a_problem(make_settings):
    b = block(make_settings, app_mode="replay")
    assert b["recordings"] == {"mode": "replay", "set": "demo", "count": 0, "problems": []}
    assert b["config_ok"] is True and b["problems"] == []


def test_status_counts_recordings_and_names_unusable_files_without_content(make_settings, tmp_path):
    from app.llm.recordings import Recording

    cfg = settings(make_settings, app_mode="replay", replay_set="s")
    store = RecordingStore(cfg.recordings_path)
    for n in range(3):
        store.save(Recording.from_call("m", req(f"q{n}"), ProviderResponse("text", Usage(1, 1), "stop"), 5))
    (cfg.recordings_path / "broken.json").write_text('{"secret": "do-not-show"', encoding="utf-8")

    response = TestClient(create_app(cfg)).get("/api/status")
    b = response.json()["gateway"]
    assert b["recordings"]["count"] == 3 and b["recordings"]["set"] == "s"
    assert b["recordings"]["problems"] == ["broken.json: not valid JSON"]
    assert b["config_ok"] is False and any("broken.json" in p for p in b["problems"])
    assert "do-not-show" not in response.text and str(tmp_path) not in response.text


def test_status_for_recording_mode(make_settings):
    b = block(make_settings, app_mode="live", record_live_calls=True)
    assert b["recordings"]["mode"] == "recording" and b["recordings"]["count"] == 0


def test_status_for_live_without_recording_has_no_recordings_block_content(make_settings):
    b = block(make_settings, app_mode="live")
    assert b["recordings"] == {"mode": "off", "set": "demo", "count": 0, "problems": []}


def test_record_live_calls_in_replay_mode_is_listed_as_a_problem(make_settings):
    b = block(make_settings, app_mode="replay", record_live_calls=True)
    assert b["config_ok"] is False and any("RECORD_LIVE_CALLS" in p for p in b["problems"])
    assert block(make_settings, app_mode="replay")["config_ok"] is True
