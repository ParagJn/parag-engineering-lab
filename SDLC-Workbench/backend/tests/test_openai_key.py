"""The OpenAI slot has its own API key. The right key must go to the right model, and neither may leak."""
from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

import scripts.live_check as live
from app.config import Settings
from app.llm.credentials import api_key_for_model, key_variable_for_model
from app.llm.errors import LLMCallFailed
from app.llm.gateway import Gateway
from app.llm.providers.ica import IcaConfigError, IcaProvider
from app.llm.routing import Routing
from app.llm.types import LLMRequest
from app.main import choose_provider, create_app

from .test_gateway import MODELS
from .test_ica_gateway import ByModel
from .test_ica_provider import ENDPOINT, KEY, REAL_MODEL_ACCESS_DENIED, err, reply

pytestmark = pytest.mark.anyio

OPENAI_KEY = "sk-OPENAI-ONLY-998877"


class Capture(ByModel):
    """Answers by model, and remembers which Authorization header each model's request carried."""

    def __init__(self, plan):
        super().__init__(plan)
        self.auth: list[tuple[str, str]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.auth.append((json.loads(request.content)["model"], request.headers["authorization"]))
        return super().__call__(request)


def settings_with(make_settings, **kw) -> Settings:
    base = {**MODELS, "ibm_ica_endpoint": ENDPOINT, "ibm_ica_api_key": KEY, "ibm_ica_openai_api_key": OPENAI_KEY}
    return make_settings(**{**base, **kw})


GOOD = {m: [reply()] for m in ("model-sonnet", "model-haiku", "model-openai", "model-gemini")}


def provider_over(cfg: Settings, plan=None) -> tuple[IcaProvider, Capture]:
    net = Capture(plan or GOOD)
    return IcaProvider(cfg, transport=httpx.MockTransport(net)), net


# ---- which key for which model ----------------------------------------------

def test_openai_models_get_the_openai_key_and_everything_else_the_shared_one(make_settings):
    cfg = settings_with(make_settings)
    assert api_key_for_model(cfg, "model-openai") == OPENAI_KEY
    for model in ("model-sonnet", "model-haiku", "model-gemini"):
        assert api_key_for_model(cfg, model) == KEY, model


def test_a_model_no_slot_owns_is_keyed_by_its_family(make_settings):
    # e.g. a GPT model set as some slot's fallback: nobody lists it as a primary model.
    cfg = settings_with(make_settings)
    assert api_key_for_model(cfg, "gpt-5.4-mini") == OPENAI_KEY
    assert api_key_for_model(cfg, "o3-mini") == OPENAI_KEY
    assert api_key_for_model(cfg, "claude-opus-5") == KEY
    assert api_key_for_model(cfg, "gemini-2.5-pro") == KEY
    assert api_key_for_model(cfg, "mystery-model") == KEY


def test_a_blank_or_missing_openai_key_means_the_shared_key(make_settings):
    for blank in ("", "   "):
        cfg = settings_with(make_settings, ibm_ica_openai_api_key=blank)
        assert api_key_for_model(cfg, "model-openai") == KEY
        assert key_variable_for_model(cfg, "model-openai") == "IBM_ICA_API_KEY"
        assert cfg.openai_key_is_own is False
    assert settings_with(make_settings).openai_key_is_own is True


def test_the_variable_name_reported_matches_the_key_actually_used(make_settings):
    cfg = settings_with(make_settings)
    assert key_variable_for_model(cfg, "model-openai") == "IBM_ICA_OPENAI_API_KEY"
    assert key_variable_for_model(cfg, "model-sonnet") == "IBM_ICA_API_KEY"


def test_the_new_key_is_read_from_a_dotenv_file_and_never_printed(tmp_path):
    path = tmp_path / "t.env"
    path.write_text(f"IBM_ICA_OPENAI_API_KEY={OPENAI_KEY}\nIBM_ICA_API_KEY={KEY}\n")
    cfg = Settings(_env_file=path)
    assert cfg.openai_key_is_own
    for text in (repr(cfg), str(cfg), str(cfg.model_dump()), cfg.model_dump_json()):
        assert OPENAI_KEY not in text and KEY not in text


def test_the_secret_list_used_for_redaction_covers_every_credential(make_settings):
    values = settings_with(make_settings, ibm_ica_user_agent="UA-xyz-1234").secret_values()
    assert {KEY, OPENAI_KEY, ENDPOINT, "UA-xyz-1234"} <= set(values)
    assert "" not in values


# ---- the wire ---------------------------------------------------------------

async def test_each_request_carries_the_key_for_its_own_model(make_settings):
    provider, net = provider_over(settings_with(make_settings))
    for model in ("model-sonnet", "model-openai", "model-haiku", "model-gemini"):
        await provider.complete(model, LLMRequest.user("orchestrator", "hi"))
    assert dict(net.auth) == {
        "model-sonnet": f"Bearer {KEY}", "model-haiku": f"Bearer {KEY}",
        "model-gemini": f"Bearer {KEY}", "model-openai": f"Bearer {OPENAI_KEY}",
    }


async def test_without_an_openai_key_every_model_uses_the_shared_one(make_settings):
    provider, net = provider_over(settings_with(make_settings, ibm_ica_openai_api_key=""))
    await provider.complete("model-openai", LLMRequest.user("orchestrator", "hi"))
    assert net.auth == [("model-openai", f"Bearer {KEY}")]


async def test_the_shared_key_is_still_required_to_build_a_provider(make_settings):
    with pytest.raises(IcaConfigError, match="IBM_ICA_API_KEY"):
        IcaProvider(make_settings(ibm_ica_endpoint=ENDPOINT, ibm_ica_openai_api_key=OPENAI_KEY))
    cfg = make_settings(app_mode="live", ibm_ica_endpoint=ENDPOINT, ibm_ica_openai_api_key=OPENAI_KEY)
    assert choose_provider(cfg).label.startswith("none")  # not enough to go live on


# ---- through the gateway ----------------------------------------------------

def gateway_for(cfg, plan, store):
    provider, net = provider_over(cfg, plan)

    async def no_sleep(_):
        return None

    return Gateway(cfg, Routing.load(), provider, store, sleep=no_sleep), net


def req(project, role="backend_developer") -> LLMRequest:
    return LLMRequest.user(role, "hi", project_id=project.id)


async def test_a_fallback_to_sonnet_never_carries_the_openai_key(make_settings, store, project):
    gateway, net = gateway_for(
        settings_with(make_settings),
        {"model-openai": [REAL_MODEL_ACCESS_DENIED], "model-sonnet": [reply("from sonnet")]},
        store,
    )
    result = await gateway.complete(req(project))
    assert result.served_model == "model-sonnet" and result.fallback_used is True
    assert net.auth == [("model-openai", f"Bearer {OPENAI_KEY}"), ("model-sonnet", f"Bearer {KEY}")]


async def test_the_openai_roles_work_end_to_end_with_their_own_key(make_settings, store, project):
    gateway, net = gateway_for(
        settings_with(make_settings),
        {"model-openai": [reply("done", usage={"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000})]},
        store,
    )
    result = await gateway.complete(req(project))
    assert result.served_model == "model-openai" and result.fallback_used is False
    assert result.cost_usd == pytest.approx(24.0)
    assert net.auth == [("model-openai", f"Bearer {OPENAI_KEY}")]


async def test_a_rejected_openai_key_names_the_openai_variable(make_settings, store, project):
    gateway, _ = gateway_for(settings_with(make_settings), {"model-openai": [err(401, message="invalid key")]}, store)
    with pytest.raises(LLMCallFailed) as exc:
        await gateway.complete(req(project))
    assert "IBM_ICA_OPENAI_API_KEY" in str(exc.value)


async def test_a_rejected_shared_key_still_names_the_shared_variable(make_settings, store, project):
    gateway, _ = gateway_for(settings_with(make_settings), {"model-sonnet": [err(401, message="invalid key")]}, store)
    with pytest.raises(LLMCallFailed) as exc:
        await gateway.complete(req(project, "requirements_analyst"))
    assert "IBM_ICA_API_KEY" in str(exc.value) and "IBM_ICA_OPENAI_API_KEY" not in str(exc.value)


async def test_the_openai_key_is_redacted_from_errors_and_traces(make_settings, store, project):
    echo = err(401, message=f"bad key {OPENAI_KEY} and also {KEY} at {ENDPOINT}")
    gateway, _ = gateway_for(settings_with(make_settings), {"model-openai": [echo]}, store)
    with pytest.raises(LLMCallFailed) as exc:
        await gateway.complete(req(project))
    everything = str(exc.value) + repr(exc.value.attempts) + " ".join(t.error or "" for t in store.traces.list(project.id))
    for secret in (OPENAI_KEY, KEY, ENDPOINT):
        assert secret not in everything, secret


# ---- the page ---------------------------------------------------------------

def gateway_block(make_settings, **kw) -> tuple[dict, str]:
    response = TestClient(create_app(settings_with(make_settings, **kw))).get("/api/status")
    return response.json()["gateway"], response.text


def test_the_status_page_says_whether_openai_uses_its_own_key_and_hides_it(make_settings):
    block, text = gateway_block(make_settings)
    assert block["openai_key"] == "own"
    assert OPENAI_KEY not in text and KEY not in text
    assert gateway_block(make_settings, ibm_ica_openai_api_key="")[0]["openai_key"] == "shared"


# ---- the live-check script --------------------------------------------------

@pytest.fixture
def fake_network(monkeypatch):
    def install(plan):
        net = Capture(plan)
        real_init = IcaProvider.__init__

        def init(self, settings, *, transport=None):
            real_init(self, settings, transport=httpx.MockTransport(net))

        monkeypatch.setattr(IcaProvider, "__init__", init)
        return net

    return install


def test_the_live_check_sends_each_model_its_own_key_and_prints_neither(make_settings, fake_network, capsys):
    net = fake_network(GOOD)
    code = live.main(["--shape"], settings=settings_with(make_settings))
    out = capsys.readouterr()
    assert code == 0
    assert dict(net.auth)["model-openai"] == f"Bearer {OPENAI_KEY}"
    assert all(auth == f"Bearer {KEY}" for model, auth in net.auth if model != "model-openai")
    assert len(net.auth) == 8  # four checks plus four --shape probes: the probes pick keys the same way
    assert OPENAI_KEY not in out.out + out.err and KEY not in out.out + out.err


def test_the_live_check_says_which_credentials_the_openai_slot_used(make_settings, fake_network, capsys):
    fake_network(GOOD)
    live.main([], settings=settings_with(make_settings))
    assert "OpenAI slot uses its own key (IBM_ICA_OPENAI_API_KEY)" in capsys.readouterr().out

    fake_network(GOOD)
    live.main([], settings=settings_with(make_settings, ibm_ica_openai_api_key=""))
    assert "OpenAI slot uses its own key" not in capsys.readouterr().out


def test_that_credentials_note_is_skipped_when_openai_is_not_being_checked(make_settings, fake_network, capsys):
    fake_network(GOOD)
    live.main(["--slot", "gemini"], settings=settings_with(make_settings))
    assert "OpenAI slot uses its own key" not in capsys.readouterr().out


def test_a_model_override_for_the_openai_slot_still_uses_the_openai_key(make_settings, fake_network, capsys):
    net = fake_network({**GOOD, "gpt-other": [reply()]})
    live.main(["--slot", "openai", "--model", "openai=gpt-other"], settings=settings_with(make_settings))
    capsys.readouterr()
    assert net.auth == [("gpt-other", f"Bearer {OPENAI_KEY}")]
