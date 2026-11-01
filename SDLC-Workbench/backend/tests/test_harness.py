from __future__ import annotations

import asyncio

import pytest

import app.config as config
from ._hermetic import scrub


def test_harness_is_hermetic_against_the_outer_environment(monkeypatch, tmp_path):
    # Simulate a developer shell that has real values exported, then run the same scrub
    # the autouse fixture runs before every test.
    monkeypatch.setenv("IBM_ICA_API_KEY", "real-looking-key")
    monkeypatch.setenv("IBM_ICA_MODEL_ID", "real-model")
    monkeypatch.setenv("APP_MODE", "live")
    scrub(monkeypatch, tmp_path / "no-such.env")

    s = config.get_settings()
    assert s.api_key_set is False
    assert s.slots["sonnet"].model_id == ""
    assert s.app_mode == "replay"


def test_harness_does_not_read_the_real_env_file():
    assert config.ENV_FILE.name == "no-such.env"
    assert not config.ENV_FILE.exists()
    assert config.get_settings().api_key_set is False


@pytest.mark.anyio
async def test_async_tests_run_under_the_anyio_plugin():
    await asyncio.sleep(0)
    assert True


def test_live_tests_are_excluded_by_default(request):
    assert "not live" in request.config.getini("addopts")


@pytest.mark.live
def test_live_marker_placeholder_must_never_run_by_default():
    pytest.fail("a test marked live ran without -m live")
