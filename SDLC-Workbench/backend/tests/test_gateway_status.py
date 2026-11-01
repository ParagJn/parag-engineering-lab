from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.llm.providers.mock import MockProvider
from app.llm.routing import REQUIRED_ROLES
from app.main import create_app

from .test_gateway import MODELS, SECRET_ENDPOINT, SECRET_KEY


def gateway_block(make_settings, **overrides) -> dict:
    return TestClient(create_app(make_settings(**overrides))).get("/api/status").json()["gateway"]


def test_block_shape_and_fourteen_routing_rows(make_settings):
    block = gateway_block(make_settings, **MODELS)
    assert set(block) == {"config_ok", "provider", "openai_key", "recordings", "problems", "routing", "reviewer"}
    assert [row["role"] for row in block["routing"]] == list(REQUIRED_ROLES)
    assert all(set(row) == {"role", "slot", "model", "using_fallback"} for row in block["routing"])
    by_role = {row["role"]: row for row in block["routing"]}
    assert (by_role["backend_developer"]["slot"], by_role["backend_developer"]["model"]) == ("openai", "model-openai")
    assert by_role["backlog_splitter"]["model"] == "model-haiku"
    assert block["reviewer"] == {
        "default_slot": "sonnet", "model": "model-sonnet", "alternatives": ["gemini", "openai", "haiku"],
    }
    assert block["provider"] == "replay"  # the default mode is replay, which has a real provider since S04


def test_replay_mode_needs_no_keys_and_no_models(make_settings):
    block = gateway_block(make_settings)  # nothing configured at all
    assert block["config_ok"] is True and block["problems"] == []


def test_live_mode_with_nothing_set_names_the_variables(make_settings):
    block = gateway_block(make_settings, app_mode="live")
    text = " | ".join(block["problems"])
    assert block["config_ok"] is False
    for name in ("IBM_ICA_ENDPOINT", "IBM_ICA_API_KEY", "IBM_ICA_MODEL_ID", "IBM_ICA_HAIKU_MODEL_ID",
                 "IBM_ICA_OPENAI_FALLBACK_MODEL_ID", "IBM_ICA_GEMINI_MODEL_ID"):
        assert name in text, name


def test_live_mode_fully_configured_is_ok(make_settings):
    block = gateway_block(
        make_settings, app_mode="live", ibm_ica_endpoint=SECRET_ENDPOINT, ibm_ica_api_key=SECRET_KEY, **MODELS
    )
    assert block["config_ok"] is True


def test_a_blank_haiku_model_is_covered_by_its_fallback_and_shown_as_such(make_settings):
    block = gateway_block(
        make_settings, app_mode="live", ibm_ica_endpoint=SECRET_ENDPOINT, ibm_ica_api_key=SECRET_KEY,
        **{**MODELS, "ibm_ica_haiku_model_id": ""},
    )
    assert block["config_ok"] is True
    row = next(r for r in block["routing"] if r["role"] == "backlog_splitter")
    assert (row["model"], row["using_fallback"]) == ("model-sonnet", True)


def test_a_blank_reviewer_model_is_a_problem_in_live_mode(make_settings):
    block = gateway_block(
        make_settings, app_mode="live", ibm_ica_endpoint=SECRET_ENDPOINT, ibm_ica_api_key=SECRET_KEY,
        **{**MODELS, "ibm_ica_model_id": ""},
    )
    assert any("reviewer" in p and "IBM_ICA_MODEL_ID" in p for p in block["problems"])


def test_problems_never_contain_secret_values(make_settings):
    block = gateway_block(
        make_settings, app_mode="live", ibm_ica_endpoint=SECRET_ENDPOINT, ibm_ica_api_key=SECRET_KEY
    )
    assert block["problems"]  # models are blank, so there is something to report
    text = json.dumps(block)
    assert SECRET_KEY not in text and SECRET_ENDPOINT not in text


def test_the_same_model_with_different_prices_is_flagged(make_settings):
    block = gateway_block(
        make_settings, **{**MODELS, "ibm_ica_haiku_model_id": "model-sonnet"}  # prices differ from Sonnet's
    )
    assert block["config_ok"] is False
    assert any("IBM_ICA_MODEL_ID" in p and "IBM_ICA_HAIKU_MODEL_ID" in p and "different prices" in p
               for p in block["problems"])


def test_the_same_model_with_the_same_prices_is_fine(make_settings):
    block = gateway_block(
        make_settings,
        **{**MODELS, "ibm_ica_haiku_model_id": "model-sonnet",
           "ibm_ica_haiku_price_input_per_mtok": "2", "ibm_ica_haiku_price_output_per_mtok": "10"},
    )
    assert block["problems"] == []


def test_a_custom_provider_label_is_shown(make_settings):
    app = create_app(make_settings(), provider=MockProvider())
    assert TestClient(app).get("/api/status").json()["gateway"]["provider"] == "mock"


def test_the_app_builds_its_gateway_and_exposes_it(make_settings):
    app = create_app(make_settings())
    assert app.state.gateway.routing.reviewer_default == "sonnet"
    assert app.state.gateway.store is app.state.store


# ---- the new settings --------------------------------------------------------

def test_new_setting_defaults(make_settings):
    s = make_settings()
    assert (s.llm_max_retries, s.llm_retry_backoff_seconds, s.llm_timeout_seconds) == (1, 1.0, 180)


def test_settings_bounds():
    for bad in ({"llm_max_retries": 6}, {"llm_max_retries": -1}, {"llm_retry_backoff_seconds": 31},
                {"llm_retry_backoff_seconds": -1}, {"llm_timeout_seconds": 0}, {"llm_timeout_seconds": -5}):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **bad)
    ok = Settings(_env_file=None, llm_max_retries=5, llm_retry_backoff_seconds=0, llm_timeout_seconds=0.05)
    assert (ok.llm_max_retries, ok.llm_retry_backoff_seconds, ok.llm_timeout_seconds) == (5, 0, 0.05)


def test_new_settings_read_from_a_dotenv_file(tmp_path):
    path = tmp_path / "t.env"
    path.write_text("LLM_MAX_RETRIES=2\nLLM_RETRY_BACKOFF_SECONDS=0.5\nLLM_TIMEOUT_SECONDS=30\n")
    s = Settings(_env_file=path)
    assert (s.llm_max_retries, s.llm_retry_backoff_seconds, s.llm_timeout_seconds) == (2, 0.5, 30)
