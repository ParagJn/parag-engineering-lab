from __future__ import annotations

import pathlib

import pytest
from pydantic import ValidationError

import app.config as config
from app.config import Settings

SLOT_NAMES = ["sonnet", "haiku", "openai", "gemini"]

# Shaped like the real .env today: Gemini's prices are blank on purpose.
FULL_ENV = """\
IBM_ICA_ENDPOINT=https://ica.example.invalid
IBM_ICA_API_KEY=sk-TEST-SECRET
IBM_ICA_MODEL_ID=model-sonnet
IBM_ICA_FALLBACK_MODEL_ID=model-sonnet
IBM_ICA_PRICE_INPUT_PER_MTOK=2.00
IBM_ICA_PRICE_OUTPUT_PER_MTOK=10.00
IBM_ICA_HAIKU_MODEL_ID=model-haiku
IBM_ICA_HAIKU_FALLBACK_MODEL_ID=model-sonnet
IBM_ICA_HAIKU_PRICE_INPUT_PER_MTOK=0.10
IBM_ICA_HAIKU_PRICE_OUTPUT_PER_MTOK=0.50
IBM_ICA_OPENAI_MODEL_ID=model-openai
IBM_ICA_OPENAI_FALLBACK_MODEL_ID=model-sonnet
IBM_ICA_OPENAI_PRICE_INPUT_PER_MTOK=4.00
IBM_ICA_OPENAI_PRICE_OUTPUT_PER_MTOK=20.00
IBM_ICA_GEMINI_MODEL_ID=model-gemini
IBM_ICA_GEMINI_FALLBACK_MODEL_ID=model-sonnet
IBM_ICA_GEMINI_PRICE_INPUT_PER_MTOK=
IBM_ICA_GEMINI_PRICE_OUTPUT_PER_MTOK=
APP_MODE=replay
RUN_BUDGET_USD=5.00
LLM_TIMEOUT_SECONDS=180
"""


def from_file(tmp_path, text: str) -> Settings:
    path = tmp_path / "test.env"
    path.write_text(text)
    return Settings(_env_file=path)


def test_defaults_with_no_env_and_a_clean_environment(make_settings):
    s = make_settings()
    assert s.app_mode == "replay"
    assert s.run_budget_usd == 5.0
    assert s.llm_timeout_seconds == 180
    assert not s.endpoint_set
    assert not s.api_key_set
    assert list(s.slots) == SLOT_NAMES
    for slot in s.slots.values():
        assert slot.model_id == ""
        assert slot.fallback_model_id == ""
        assert slot.price_input is None
        assert slot.price_output is None
        assert slot.priced is False


def test_reads_an_env_file(tmp_path):
    s = from_file(tmp_path, FULL_ENV)
    assert s.endpoint_set and s.api_key_set
    assert s.app_mode == "replay"
    models = {name: slot.model_id for name, slot in s.slots.items()}
    assert models == {
        "sonnet": "model-sonnet",
        "haiku": "model-haiku",
        "openai": "model-openai",
        "gemini": "model-gemini",
    }
    assert all(slot.fallback_model_id == "model-sonnet" for slot in s.slots.values())


def test_sonnet_uses_the_unprefixed_variable_names(tmp_path):
    s = from_file(tmp_path, "IBM_ICA_MODEL_ID=only-sonnet\n")
    assert s.slots["sonnet"].model_id == "only-sonnet"
    for other in ("haiku", "openai", "gemini"):
        assert s.slots[other].model_id == ""

    s = from_file(tmp_path, "IBM_ICA_HAIKU_MODEL_ID=only-haiku\n")
    assert s.slots["haiku"].model_id == "only-haiku"
    assert s.slots["sonnet"].model_id == ""


def test_blank_price_is_none_not_zero(tmp_path):
    s = from_file(tmp_path, FULL_ENV)
    gemini = s.slots["gemini"]
    assert gemini.price_input is None
    assert gemini.price_output is None
    assert gemini.priced is False
    assert s.slots["sonnet"].priced is True


def test_prices_round_trip_as_numbers(tmp_path):
    s = from_file(tmp_path, FULL_ENV)
    sonnet = s.slots["sonnet"]
    assert sonnet.price_input == 2.0 and isinstance(sonnet.price_input, float)
    assert sonnet.price_output == 10.0
    assert s.slots["haiku"].price_input == 0.10
    assert s.slots["openai"].price_output == 20.0


def test_zero_price_is_allowed_and_distinct_from_unknown(make_settings):
    s = make_settings(ibm_ica_price_input_per_mtok="0", ibm_ica_price_output_per_mtok="0")
    assert s.slots["sonnet"].price_input == 0.0
    assert s.slots["sonnet"].priced is True


def test_half_priced_slot_is_not_priced(make_settings):
    s = make_settings(ibm_ica_haiku_price_input_per_mtok="0.10")
    assert s.slots["haiku"].price_input == 0.10
    assert s.slots["haiku"].priced is False


@pytest.mark.parametrize("bad", ["abc", "-1", "nan", "inf"])
def test_bad_prices_are_rejected_and_name_the_field(tmp_path, bad):
    with pytest.raises(ValidationError) as exc:
        from_file(tmp_path, f"IBM_ICA_GEMINI_PRICE_INPUT_PER_MTOK={bad}\n")
    assert "ibm_ica_gemini_price_input_per_mtok" in str(exc.value).lower()


def test_bad_mode_is_rejected(tmp_path):
    with pytest.raises(ValidationError) as exc:
        from_file(tmp_path, "APP_MODE=foo\n")
    assert "app_mode" in str(exc.value).lower()


def test_mode_is_case_and_space_tolerant(tmp_path):
    assert from_file(tmp_path, "APP_MODE= LIVE \n").app_mode == "live"


def test_api_key_never_appears_in_any_output(tmp_path):
    s = from_file(tmp_path, FULL_ENV)
    secret = "sk-TEST-SECRET"
    assert s.api_key_set
    assert secret not in repr(s)
    assert secret not in str(s)
    assert secret not in str(s.model_dump())
    assert secret not in s.model_dump_json()
    for slot in s.slots.values():
        assert secret not in repr(slot)
        assert secret not in str(slot)


def test_get_settings_reads_the_env_file_it_is_pointed_at(monkeypatch, tmp_path):
    path = tmp_path / "pointed.env"
    path.write_text("IBM_ICA_MODEL_ID=from-pointed-file\n")
    monkeypatch.setattr(config, "ENV_FILE", path)
    config.get_settings.cache_clear()
    assert config.get_settings().slots["sonnet"].model_id == "from-pointed-file"


def test_get_settings_is_cached(monkeypatch, tmp_path):
    path = tmp_path / "cached.env"
    path.write_text("IBM_ICA_MODEL_ID=first\n")
    monkeypatch.setattr(config, "ENV_FILE", path)
    config.get_settings.cache_clear()
    first = config.get_settings()
    path.write_text("IBM_ICA_MODEL_ID=second\n")
    assert config.get_settings() is first
    assert config.get_settings().slots["sonnet"].model_id == "first"


def test_unknown_env_lines_are_ignored(tmp_path):
    s = from_file(tmp_path, "SOMETHING_ELSE=1\nBACKEND_PORT=9999\n")
    assert s.app_mode == "replay"


# ---- the per-run spending limit (2026-11-04) -----------------------------------------------------------------------------------------------------------
# `.env.example` told people to set RUN_BUDGET_USD, but the cap the runner enforces is run_max_cost_usd, so the limit they set was never used and every run stayed at $5.

def test_the_budget_a_person_sets_is_the_cap_a_run_is_stopped_at(tmp_path):
    assert from_file(tmp_path, "RUN_BUDGET_USD=8.00\n").run_max_cost_usd == 8.0
    assert from_file(tmp_path, "RUN_BUDGET_USD=8.00\n").run_budget_usd == 8.0


def test_with_neither_set_the_cap_is_the_built_in_five_dollars(tmp_path):
    s = from_file(tmp_path, "APP_MODE=replay\n")
    assert s.run_max_cost_usd == 5.0 and s.run_budget_usd == 5.0


def test_the_more_specific_name_wins_when_both_are_given_in_either_order(tmp_path):
    assert from_file(tmp_path, "RUN_BUDGET_USD=8.00\nRUN_MAX_COST_USD=3.00\n").run_max_cost_usd == 3.0
    assert from_file(tmp_path, "RUN_MAX_COST_USD=3.00\nRUN_BUDGET_USD=8.00\n").run_max_cost_usd == 3.0
    assert from_file(tmp_path, "RUN_MAX_COST_USD=12.00\n").run_max_cost_usd == 12.0


def test_the_specific_name_alone_does_not_move_the_budget_and_zero_still_switches_the_cap_off(tmp_path):
    s = from_file(tmp_path, "RUN_MAX_COST_USD=12.00\n")
    assert s.run_budget_usd == 5.0 and s.run_max_cost_usd == 12.0
    assert from_file(tmp_path, "RUN_BUDGET_USD=0\n").run_max_cost_usd == 0.0


def test_a_budget_outside_the_allowed_range_is_still_refused_at_start_up(tmp_path):
    with pytest.raises(Exception):
        from_file(tmp_path, "RUN_BUDGET_USD=5000\n")                        # the cap is limited to 1000, and the budget is copied into it


def test_a_name_the_app_does_not_know_is_still_ignored(tmp_path):
    assert from_file(tmp_path, "RUN_MAX=8.00\n").run_max_cost_usd == 5.0


def test_the_example_file_says_which_name_wins():
    text = (pathlib.Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    assert "RUN_BUDGET_USD=5.00" in text and "RUN_MAX_COST_USD" in text


def test_a_budget_that_was_never_given_leaves_the_cap_alone_whether_the_cap_was_given_or_not(tmp_path):
    assert from_file(tmp_path, "APP_MODE=replay\n").run_max_cost_usd == 5.0                        # neither given: the built-in cap
    assert from_file(tmp_path, "RUN_MAX_COST_USD=2.50\n").run_max_cost_usd == 2.5                  # only the cap given: the cap, not the budget's default
    assert from_file(tmp_path, "RUN_MAX_COST_USD=2.50\n").run_budget_usd == 5.0
    assert from_file(tmp_path, "RUN_MAX_COST_USD=0\n").run_max_cost_usd == 0.0
