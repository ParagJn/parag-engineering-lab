from __future__ import annotations

import json

import httpx
import pytest

import scripts.live_check as live
from app.llm.providers.ica import IcaProvider

from .test_gateway import MODELS
from .test_ica_provider import AGENT, ENDPOINT, KEY, err, reply
from .test_ica_gateway import ByModel


@pytest.fixture
def cfg(make_settings):
    return make_settings(**{**MODELS, "ibm_ica_endpoint": ENDPOINT, "ibm_ica_api_key": KEY, "ibm_ica_user_agent": AGENT})


@pytest.fixture
def fake_network(monkeypatch):
    """Route every IcaProvider the script builds through a scripted fake network."""
    state = {}

    def install(plan):
        net = ByModel(plan)
        real_init = IcaProvider.__init__

        def init(self, settings, *, transport=None):
            real_init(self, settings, transport=httpx.MockTransport(net))

        monkeypatch.setattr(IcaProvider, "__init__", init)
        state["net"] = net
        return net

    return install


GOOD = {m: [reply()] for m in ("model-sonnet", "model-haiku", "model-openai", "model-gemini")}


def run_main(cfg, capsys, *argv):
    code = live.main(list(argv), settings=cfg)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_all_slots_ok_prints_a_table_and_exits_zero(cfg, fake_network, capsys):
    fake_network(GOOD)
    code, out, _ = run_main(cfg, capsys)
    assert code == 0
    assert "4/4 slots OK" in out
    for slot, model in [("sonnet", "model-sonnet"), ("haiku", "model-haiku"), ("openai", "model-openai"), ("gemini", "model-gemini")]:
        line = next(l for l in out.splitlines() if l.startswith(slot))
        assert model in line and " ok " in f" {line} "
    assert "anthropic" in out and "openai" in out and "google" in out


def test_cost_and_tokens_are_shown_and_unknown_cost_says_so(make_settings, fake_network, capsys):
    cfg = make_settings(**{**MODELS, "ibm_ica_endpoint": ENDPOINT, "ibm_ica_api_key": KEY,
                           "ibm_ica_gemini_price_input_per_mtok": "", "ibm_ica_gemini_price_output_per_mtok": ""})
    fake_network({**GOOD, "model-sonnet": [reply(usage={"prompt_tokens": 1000, "completion_tokens": 200})]})
    _, out, _ = run_main(cfg, capsys)
    sonnet = next(l for l in out.splitlines() if l.startswith("sonnet"))
    gemini = next(l for l in out.splitlines() if l.startswith("gemini"))
    assert "1000" in sonnet and "200" in sonnet and "$0.004000" in sonnet
    assert "unknown" in gemini


def test_a_failing_slot_is_reported_not_hidden_by_a_fallback(cfg, fake_network, capsys):
    net = fake_network({**GOOD, "model-openai": [err(404, message="model not found")]})
    code, out, _ = run_main(cfg, capsys)
    assert code == 1
    assert "3/4 slots OK" in out
    openai = next(l for l in out.splitlines() if l.startswith("openai"))
    assert "model_not_found" in openai and "ok" not in openai.split()[3:4]
    assert "model-sonnet" not in [m for m in net.seen if m != "model-sonnet"]  # sonnet was only asked as its own slot
    assert net.seen.count("model-sonnet") == 1  # not asked a second time as openai's fallback


def test_failure_kinds_are_named(cfg, fake_network, capsys):
    fake_network({
        "model-sonnet": [err(401, message="bad key")],
        "model-haiku": [reply("")],
        "model-openai": [err(400, message="Unsupported parameter: max_tokens")],
        "model-gemini": [err(429, message="slow down")],
    })
    code, out, _ = run_main(cfg, capsys)
    assert code == 1 and "0/4 slots OK" in out
    for slot, kind in [("sonnet", "auth"), ("haiku", "bad_response"), ("openai", "bad_request"), ("gemini", "transient")]:
        assert kind in next(l for l in out.splitlines() if l.startswith(slot)), slot
    assert "Unsupported parameter" in out  # the cleaned provider message is shown


def test_slot_filter_calls_only_that_slot(cfg, fake_network, capsys):
    net = fake_network(GOOD)
    code, out, _ = run_main(cfg, capsys, "--slot", "gemini")
    assert code == 0 and "1/1 slots OK" in out
    assert net.seen == ["model-gemini"]


def test_a_blank_model_is_reported_as_not_configured(make_settings, fake_network, capsys):
    cfg = make_settings(**{**MODELS, "ibm_ica_endpoint": ENDPOINT, "ibm_ica_api_key": KEY, "ibm_ica_haiku_model_id": ""})
    net = fake_network(GOOD)
    code, out, _ = run_main(cfg, capsys)
    assert code == 1 and "not_configured" in out and "IBM_ICA_HAIKU_MODEL_ID" in out
    assert "model-haiku" not in net.seen and net.seen.count("model-sonnet") == 1  # fallback not used


def test_it_refuses_to_run_without_credentials_and_says_which(make_settings, capsys):
    for settings, missing in [
        ({}, ["IBM_ICA_ENDPOINT", "IBM_ICA_API_KEY"]),
        ({"ibm_ica_endpoint": ENDPOINT}, ["IBM_ICA_API_KEY"]),
        ({"ibm_ica_api_key": KEY}, ["IBM_ICA_ENDPOINT"]),
    ]:
        code, out, err_out = run_main(make_settings(**MODELS, **settings), capsys)
        assert code == 2 and out == ""
        assert all(name in err_out for name in missing)
        assert KEY not in err_out


def test_it_never_prints_the_key_endpoint_or_user_agent(cfg, fake_network, capsys):
    fake_network({
        "model-sonnet": [err(401, message=f"bad key {KEY} for {ENDPOINT} via {AGENT}")],
        "model-haiku": [reply(f"echo {KEY}")],
        "model-openai": [httpx.Response(500, text=f"{KEY} {ENDPOINT}")],
        "model-gemini": [reply()],
    })
    _, out, err_out = run_main(cfg, capsys, "--shape")
    for secret in (KEY, ENDPOINT, AGENT, "example.invalid"):
        assert secret not in out and secret not in err_out, secret


def test_shape_prints_key_names_and_types_but_never_values(cfg, fake_network, capsys):
    body = reply("TOP-SECRET-REPLY-TEXT", usage={"prompt_tokens": 12345, "completion_tokens": 6789}, id="resp-abc-999")
    fake_network({**GOOD, "model-sonnet": [body]})
    _, out, _ = run_main(cfg, capsys, "--shape", "--slot", "sonnet")
    assert "Response structure" in out
    table, structure = out.split("Response structure")
    for name in ("choices", "message", "content", "finish_reason", "usage", "prompt_tokens", "completion_tokens", "id"):
        assert name in structure
    # The results table legitimately shows token counts; the structure section must show no values at all.
    for value in ("TOP-SECRET-REPLY-TEXT", "12345", "6789", "resp-abc-999"):
        assert value not in structure, value
    assert "TOP-SECRET-REPLY-TEXT" not in table  # and the reply text is not printed anywhere (length only)


def test_without_shape_no_structure_is_printed(cfg, fake_network, capsys):
    fake_network(GOOD)
    _, out, _ = run_main(cfg, capsys)
    assert "Response structure" not in out


def test_it_uses_a_throwaway_database_and_leaves_the_real_one_alone(cfg, fake_network, capsys, tmp_path):
    fake_network(GOOD)
    real = cfg.db_path
    run_main(cfg, capsys)
    assert not real.exists()  # nothing was written to the configured data folder


def test_it_goes_through_the_gateway_with_the_fixed_prompt_and_token_limit(cfg, fake_network, capsys, monkeypatch):
    sent = []
    net = fake_network(GOOD)
    original = net.__call__

    def spy(request):
        sent.append(json.loads(request.content))
        return original(request)

    monkeypatch.setattr(ByModel, "__call__", lambda self, request: spy(request))
    run_main(cfg, capsys, "--slot", "openai")
    [body] = sent
    assert body["max_tokens"] == 200 and body["messages"][-1]["content"] == live.PROMPT


def test_a_model_the_key_may_not_use_is_named_as_such_not_as_an_auth_problem(cfg, fake_network, capsys):
    """The real 2026-10-27 result: three slots fine, OpenAI denied."""
    from .test_ica_provider import REAL_MODEL_ACCESS_DENIED

    net = fake_network({**GOOD, "model-openai": [REAL_MODEL_ACCESS_DENIED]})
    code, out, _ = run_main(cfg, capsys)
    openai = next(l for l in out.splitlines() if l.startswith("openai"))
    assert code == 1 and "3/4 slots OK" in out
    assert "model_access_denied" in openai and " auth " not in f" {openai} "
    assert net.seen.count("model-sonnet") == 1  # still no silent fallback


def test_a_denied_model_prints_a_next_step_naming_the_variable_and_the_option(cfg, fake_network, capsys):
    from .test_ica_provider import REAL_MODEL_ACCESS_DENIED

    fake_network({**GOOD, "model-openai": [REAL_MODEL_ACCESS_DENIED]})
    _, out, _ = run_main(cfg, capsys)
    assert "Next step for openai" in out
    assert "IBM_ICA_OPENAI_MODEL_ID" in out and "--model openai=" in out
    assert "IBM_ICA_API_KEY" not in out  # the key works; do not point at it


def test_no_hint_when_everything_is_fine(cfg, fake_network, capsys):
    fake_network(GOOD)
    _, out, _ = run_main(cfg, capsys)
    assert "Next step" not in out


# ---- trying other model IDs without editing .env ----------------------------

def test_model_override_tries_another_id_for_one_slot(cfg, fake_network, capsys):
    net = fake_network({**GOOD, "gpt-other": [reply()]})
    code, out, _ = run_main(cfg, capsys, "--slot", "openai", "--model", "openai=gpt-other")
    assert code == 0 and net.seen == ["gpt-other"]
    line = next(l for l in out.splitlines() if l.startswith("openai"))
    assert "gpt-other" in line and "model-openai" not in line
    assert "overridden for this run only: openai=gpt-other" in out and "Your .env was not changed" in out
    assert "configured prices" in out


def test_several_overrides_and_only_the_named_slots_change(cfg, fake_network, capsys):
    net = fake_network({**GOOD, "gpt-other": [reply()], "gem-other": [reply()]})
    run_main(cfg, capsys, "--model", "openai=gpt-other", "--model", "gemini=gem-other")
    assert sorted(net.seen) == ["gem-other", "gpt-other", "model-haiku", "model-sonnet"]


def test_overrides_never_touch_the_env_file_or_the_settings_object(cfg, fake_network, capsys):
    fake_network({**GOOD, "gpt-other": [reply()]})
    run_main(cfg, capsys, "--model", "openai=gpt-other")
    assert cfg.slots["openai"].model_id == "model-openai"


@pytest.mark.parametrize("bad", ["openai", "openai=", "=gpt", "mistral=gpt-x", "openai=has space", "openai=" + "x" * 130])
def test_bad_overrides_are_refused_before_any_call(cfg, fake_network, capsys, bad):
    net = fake_network(GOOD)
    code, out, err_out = run_main(cfg, capsys, "--model", bad)
    assert code == 2 and net.seen == [] and out == ""
    assert "--model" in err_out and KEY not in err_out


def test_the_overridden_model_is_still_reported_by_family(cfg, fake_network, capsys):
    fake_network({**GOOD, "claude-something": [reply()]})
    _, out, _ = run_main(cfg, capsys, "--slot", "openai", "--model", "openai=claude-something")
    line = next(l for l in out.splitlines() if l.startswith("openai"))
    assert "openai" in line.split()[2]  # the slot's family, because the slot owns the model


# ---- helpers ---------------------------------------------------------------

def test_describe_shape_gives_names_and_types_never_values():
    shape = live.describe_shape({
        "id": "secret-id", "n": 5, "ok": True, "none": None, "items": [{"text": "hidden", "k": 1.5}], "empty": [],
        "nested": {"deep": {"leaf": "value"}},
    })
    text = json.dumps(shape)
    assert shape["id"] == "str" and shape["n"] == "int" and shape["ok"] == "bool"
    assert shape["none"] == "null" and shape["empty"] == "list(empty)"
    assert shape["items"][0] == "list of 1" and shape["items"][1] == {"text": "str", "k": "float"}
    assert shape["nested"] == {"deep": {"leaf": "str"}}
    for value in ("secret-id", "hidden", "value"):
        assert value not in text


def test_render_aligns_columns_and_counts():
    rows = [
        live.Row("sonnet", "m1", "anthropic", "ok", "stop", "1", "2", "30", "$0.000001", "reply: 'ready'"),
        live.Row("openai", "", "-", "not_configured", "-", "-", "-", "-", "-", "set it"),
    ]
    out = live.render(rows)
    lines = out.splitlines()
    assert lines[0].startswith("slot") and set(lines[1]) <= {"-", " "}
    assert "(not set)" in out and out.rstrip().endswith("1/2 slots OK")
    assert rows[0].ok and not rows[1].ok


def test_format_cost():
    assert live.format_cost(None) == "unknown"
    assert live.format_cost(0.0) == "$0.000000"
    assert live.format_cost(0.004) == "$0.004000"
