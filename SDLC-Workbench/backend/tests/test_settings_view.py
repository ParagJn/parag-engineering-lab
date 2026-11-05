"""S23d: the settings catalogue and the read-only view. Every setting of the app is listed once, in words; a secret is only ever 'set' or 'not set'. No file is read."""
from __future__ import annotations

import json

import httpx
import pytest

from app.config import Settings
from app.main import create_app
from app.settings_admin import catalogue as C
from app.settings_admin import view as V

pytestmark = pytest.mark.anyio
SECRETS = {"ibm_ica_endpoint": "https://gateway.example/secret-path-9", "ibm_ica_api_key": "KEY-SHARED-12345", "ibm_ica_openai_api_key": "KEY-OPENAI-67890", "ibm_ica_user_agent": "UA-LABEL-ABCDE"}


# ---- the catalogue --------------------------------------------------------------------------------------------------------------------------------

def test_every_setting_of_the_app_is_in_the_catalogue_exactly_once_and_nothing_else():
    assert C.check_complete() == []
    assert sorted(s.key for s in C.SETTINGS) == sorted(Settings.model_fields)


def test_a_new_setting_added_to_the_app_would_be_caught(monkeypatch):
    monkeypatch.setattr(C, "SETTINGS", C.SETTINGS[:-1])
    assert any("is a setting of the app but is not in the catalogue" in p for p in C.check_complete())


def test_an_invented_setting_a_repeat_an_unknown_group_or_kind_and_a_secret_mismatch_are_caught(monkeypatch):
    extra = (C.Setting("not_a_setting", "mode", "x", "x", "text"), C.SETTINGS[0], C.Setting("run_budget_usd", "nowhere", "x", "x", "banana"),
             C.Setting("data_dir", "advanced", "x", "x", "text", secret=True), C.Setting("replay_set", "advanced", "x", "x", "secret"), C.Setting("record_live_calls", "mode", "x", "x", "choice"))
    monkeypatch.setattr(C, "SETTINGS", C.SETTINGS + extra)
    text = " | ".join(C.check_complete())
    for needle in ("not_a_setting is in the catalogue but the app has no such setting", "app_mode is listed twice", "unknown group 'nowhere'", "unknown kind 'banana'",
                   "data_dir is a secret but its kind is 'text'", "replay_set has kind 'secret' but is not marked secret", "record_live_calls is a choice with no choices"):
        assert needle in text, needle


def test_the_four_secrets_the_app_already_guards_are_exactly_the_four_marked_secret():
    marked = {s.key for s in C.SETTINGS if s.secret}
    assert marked == set(SECRETS)
    guarded = Settings(_env_file=None, **{k: v for k, v in SECRETS.items()}).secret_values()
    assert sorted(guarded) == sorted(SECRETS.values())                              # the app's own list of things that must never be printed is the same four


def test_the_env_variable_name_is_the_field_name_in_upper_case():
    assert C.BY_KEY["run_budget_usd"].env_name == "RUN_BUDGET_USD" and C.BY_KEY["ibm_ica_haiku_model_id"].env_name == "IBM_ICA_HAIKU_MODEL_ID"


def test_every_group_has_a_title_and_a_sentence_and_at_least_one_setting():
    keys = [g[0] for g in C.GROUPS]
    assert len(keys) == len(set(keys)) and all(t and h for _, t, h in C.GROUPS)
    assert all(any(s.group == k for s in C.SETTINGS) for k in keys)


def test_every_setting_has_a_label_and_a_sentence_of_help_and_a_choice_has_its_choices():
    for s in C.SETTINGS:
        assert s.label.strip() and len(s.help) > 20, s.key
    assert C.BY_KEY["app_mode"].choices == ("replay", "live")


def test_the_four_model_slots_each_have_a_model_a_fallback_and_two_prices():
    for group in ("sonnet", "haiku", "openai", "gemini"):
        keys = [s.key for s in C.SETTINGS if s.group == group]
        assert len(keys) == 4 and {k.rsplit("_", 1)[-1] for k in keys} >= {"id", "mtok"}


# ---- the view -------------------------------------------------------------------------------------------------------------------------------------

def view(**over):
    return V.describe(Settings(_env_file=None, **over))


def entries(body):
    return {s["key"]: s for g in body["groups"] for s in g["settings"]}


def test_the_view_has_every_group_in_order_and_every_setting_once():
    body = view()
    assert [g["key"] for g in body["groups"]] == [g[0] for g in C.GROUPS]
    assert sorted(entries(body)) == sorted(Settings.model_fields) and sum(len(g["settings"]) for g in body["groups"]) == len(Settings.model_fields)


def test_a_secret_is_only_set_or_not_set_and_its_value_is_nowhere_in_the_answer():
    body = view(**SECRETS)
    text = json.dumps(body)
    for value in SECRETS.values():
        assert value not in text and value.split("//")[-1] not in text
    e = entries(body)
    for key in SECRETS:
        assert e[key]["secret"] is True and e[key]["is_set"] is True and "value" not in e[key] and "default" not in e[key], key


def test_a_secret_that_is_blank_is_not_set_and_one_of_only_spaces_is_not_set():
    e = entries(view(ibm_ica_api_key="   ", ibm_ica_openai_api_key=""))
    assert e["ibm_ica_api_key"]["is_set"] is False and e["ibm_ica_openai_api_key"]["is_set"] is False and e["ibm_ica_endpoint"]["is_set"] is False


def test_a_changed_value_shows_what_it_is_what_the_default_is_and_that_it_changed():
    e = entries(view(run_budget_usd=7, run_max_concurrency=3, app_mode="live"))
    assert (e["run_budget_usd"]["value"], e["run_budget_usd"]["default"], e["run_budget_usd"]["changed"]) == ("7.0", "5.0", True)
    assert e["run_max_concurrency"]["changed"] is False and e["app_mode"]["value"] == "live" and e["app_mode"]["default"] == "replay" and e["app_mode"]["changed"] is True


def test_values_are_shown_as_text_a_yes_no_as_true_or_false_and_nothing_as_blank():
    e = entries(view(record_live_calls=True, ibm_ica_haiku_price_input_per_mtok=0.8))
    assert e["record_live_calls"]["value"] == "true" and e["ibm_ica_insecure_tls"]["value"] == "false"
    assert e["ibm_ica_haiku_price_input_per_mtok"]["value"] == "0.8" and e["ibm_ica_price_input_per_mtok"]["value"] == "" and e["agent_temperature"]["value"] == ""


def test_the_defaults_are_the_apps_own_not_what_is_in_the_environment(monkeypatch):
    import importlib
    monkeypatch.setenv("RUN_BUDGET_USD", "99")
    try:
        reloaded = importlib.reload(V)                                  # the defaults are made once, when the module loads: load it again with the variable set
        assert reloaded.DEFAULTS["run_budget_usd"] == "5.0"
        assert entries(reloaded.describe(Settings(_env_file=None)))["run_budget_usd"]["default"] == "5.0"
    finally:
        monkeypatch.delenv("RUN_BUDGET_USD")
        importlib.reload(V)


def test_a_setting_marked_hidden_is_not_offered_on_the_screen(monkeypatch):
    hidden = C.Setting("replay_set", "mode", "Recording set", "Which folder of recorded replies replay mode uses.", "text", hidden=True)
    monkeypatch.setattr(C, "SETTINGS", tuple(hidden if s.key == "replay_set" else s for s in C.SETTINGS))
    monkeypatch.setattr(V, "SETTINGS", C.SETTINGS)
    assert "replay_set" not in entries(view()) and "run_budget_usd" in entries(view())


def test_each_entry_says_its_kind_unit_choices_and_the_name_it_has_in_the_env_file():
    e = entries(view())
    assert e["run_budget_usd"]["kind"] == "number" and e["run_budget_usd"]["unit"] == "USD" and e["run_budget_usd"]["env_name"] == "RUN_BUDGET_USD"
    assert e["app_mode"]["kind"] == "choice" and e["app_mode"]["choices"] == ["replay", "live"] and e["context_max_file_mb"]["kind"] == "whole"


def test_the_flags_default_to_nothing_pending_and_nobody_may_edit_yet():
    body = view()
    assert body["restart_pending"] is False and body["can_edit"] is False and "never shown" in body["note"]


def test_the_view_reads_the_loaded_settings_and_never_opens_a_file(monkeypatch):
    import builtins
    real = builtins.open
    opened: list[str] = []
    monkeypatch.setattr(builtins, "open", lambda f, *a, **k: (opened.append(str(f)), real(f, *a, **k))[1])
    view(**SECRETS)
    assert not [f for f in opened if f.endswith(".env")]


# ---- over HTTP --------------------------------------------------------------------------------------------------------------------------------------

async def test_the_route_needs_no_name_answers_with_the_groups_and_never_a_secret(make_settings):
    app = create_app(make_settings(**SECRETS, run_budget_usd=7))
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    r = await c.get("/api/settings")
    assert r.status_code == 200 and len(r.json()["groups"]) == len(C.GROUPS)
    for value in SECRETS.values():
        assert value not in r.text
    assert entries(r.json())["run_budget_usd"]["value"] == "7.0"
    await c.aclose()


async def test_reading_changes_nothing_and_a_post_delete_or_patch_is_not_allowed(make_settings):
    app = create_app(make_settings())
    c = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"X-Actor": "Anyone"})
    before = app.state.settings.model_dump()
    for method in ("POST", "DELETE", "PATCH"):
        assert (await c.request(method, "/api/settings", json={"values": {"run_budget_usd": 99}})).status_code == 405
    assert (await c.put("/api/settings", json={"values": {"run_budget_usd": 99}})).status_code == 409                      # an app given its settings has no file to write
    assert app.state.settings.model_dump() == before
    await c.aclose()
