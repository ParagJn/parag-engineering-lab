from __future__ import annotations

import importlib
import sys

from fastapi.testclient import TestClient

import app.config as config
from app.db import MIGRATIONS
from app.main import create_app

SLOT_FIELDS = {"slot", "model_id", "fallback_model_id", "price_input", "price_output", "priced"}


def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_status_shape(make_settings):
    s = make_settings(
        ibm_ica_endpoint="https://ica.example.invalid",
        ibm_ica_api_key="sk-TEST-SECRET",
        ibm_ica_model_id="model-sonnet",
        ibm_ica_price_input_per_mtok="2.00",
        ibm_ica_price_output_per_mtok="10.00",
    )
    body = TestClient(create_app(s)).get("/api/status").json()
    assert set(body) == {"mode", "endpoint_set", "api_key_set", "slots", "db", "gateway", "workflow", "context", "skills", "review", "run", "guardrails"}
    assert body["mode"] == "replay"
    assert body["endpoint_set"] is True
    assert body["api_key_set"] is True
    assert [slot["slot"] for slot in body["slots"]] == ["sonnet", "haiku", "openai", "gemini"]
    assert all(set(slot) == SLOT_FIELDS for slot in body["slots"])
    sonnet = body["slots"][0]
    assert sonnet["model_id"] == "model-sonnet"
    assert sonnet["price_input"] == 2.0
    assert sonnet["price_output"] == 10.0
    assert sonnet["priced"] is True


def test_status_reports_nothing_set_on_a_blank_config(client):
    body = client.get("/api/status").json()
    assert body["endpoint_set"] is False
    assert body["api_key_set"] is False


def test_status_never_returns_the_key_or_the_endpoint(make_settings):
    s = make_settings(
        ibm_ica_endpoint="https://ica.example.invalid",
        ibm_ica_api_key="sk-TEST-SECRET",
    )
    text = TestClient(create_app(s)).get("/api/status").text
    assert "sk-TEST-SECRET" not in text
    assert "example.invalid" not in text


def test_status_unpriced_slot_is_null_not_zero(make_settings):
    s = make_settings(ibm_ica_gemini_model_id="model-gemini")
    gemini = next(
        slot for slot in TestClient(create_app(s)).get("/api/status").json()["slots"]
        if slot["slot"] == "gemini"
    )
    assert gemini["priced"] is False
    assert gemini["price_input"] is None
    assert gemini["price_output"] is None


def test_status_reports_the_database_without_a_path(make_settings, tmp_path):
    app = create_app(make_settings())
    client = TestClient(app)
    first = client.get("/api/status")
    assert first.json()["db"] == {"schema_version": len(MIGRATIONS), "projects": 0}
    app.state.store.projects.create(name="One", actor="system")
    assert client.get("/api/status").json()["db"]["projects"] == 1
    assert str(tmp_path) not in first.text
    assert "sdlc_workbench" not in first.text


def test_data_dir_is_respected_and_defaults_under_backend_data(make_settings, tmp_path):
    custom = make_settings(data_dir=str(tmp_path / "custom"))
    assert custom.db_path == tmp_path / "custom" / "sdlc_workbench.db"
    create_app(custom)
    assert custom.db_path.exists()

    default = make_settings(data_dir="")
    assert default.db_path.name == "sdlc_workbench.db"
    assert default.db_path.parent.name == "data"
    assert default.db_path.parent.parent.name == "backend"


def test_status_mode_follows_config(make_settings):
    for mode in ("replay", "live"):
        body = TestClient(create_app(make_settings(app_mode=mode))).get("/api/status").json()
        assert body["mode"] == mode


def test_cors_allows_the_frontend_origin_and_no_other(client):
    allowed = client.get("/api/health", headers={"Origin": "http://localhost:5270"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5270"

    blocked = client.get("/api/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in blocked.headers


def test_importing_the_app_module_does_not_read_settings(monkeypatch):
    calls: list[int] = []
    # Scoped so the stub is gone before the autouse fixture's teardown calls cache_clear().
    with monkeypatch.context() as patch:
        patch.setattr(config, "get_settings", lambda: calls.append(1))
        patch.delitem(sys.modules, "app.main", raising=False)
        importlib.import_module("app.main")
    assert calls == []
