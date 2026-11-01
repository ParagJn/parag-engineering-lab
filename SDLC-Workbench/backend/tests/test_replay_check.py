from __future__ import annotations

import httpx
import pytest

import scripts.replay_check as check
from app.llm.providers.ica import IcaProvider

from .test_gateway import MODELS
from .test_ica_gateway import ByModel
from .test_ica_provider import AGENT, ENDPOINT, KEY, err, reply

OPENAI_KEY = "sk-OPENAI-ONLY-998877"
GOOD = {m: [reply("a perfectly fine reply")] for m in ("model-sonnet", "model-haiku", "model-openai", "model-gemini")}


@pytest.fixture
def cfg(make_settings):
    return make_settings(**{**MODELS, "ibm_ica_endpoint": ENDPOINT, "ibm_ica_api_key": KEY,
                            "ibm_ica_openai_api_key": OPENAI_KEY, "ibm_ica_user_agent": AGENT})


@pytest.fixture
def fake_network(monkeypatch):
    def install(plan):
        net = ByModel({m: list(o) * 3 for m, o in plan.items()})
        real_init = IcaProvider.__init__

        def init(self, settings, *, transport=None):
            real_init(self, settings, transport=httpx.MockTransport(net))

        monkeypatch.setattr(IcaProvider, "__init__", init)
        return net

    return install


def run_main(cfg, capsys, *argv):
    code = check.main(list(argv), settings=cfg)
    out = capsys.readouterr()
    return code, out.out, out.err


def test_four_identical_round_trips_exit_zero_and_print_the_miss_message(cfg, fake_network, capsys):
    net = fake_network(GOOD)
    code, out, _ = run_main(cfg, capsys)
    assert code == 0 and "4/4 round trips identical" in out
    for slot in ("sonnet", "haiku", "openai", "gemini"):
        line = next(l for l in out.splitlines() if l.startswith(slot))
        assert line.count("yes") == 3 and "NO" not in line
    assert "A recording that does not exist looks like this" in out
    assert "no recording for role 'orchestrator'" in out and "RECORD_LIVE_CALLS=true" in out
    assert len(net.seen) == 4  # replay made no extra network calls: only the four recorded ones


def test_replay_really_uses_no_network_provider(cfg, fake_network, capsys, monkeypatch):
    net = fake_network(GOOD)
    run_main(cfg, capsys)
    assert net.seen.count("model-sonnet") == 1  # one live call per slot, none during replay or the miss


def test_a_slot_that_fails_while_recording_is_reported_and_exits_one(cfg, fake_network, capsys):
    fake_network({**GOOD, "model-openai": [err(404, message="model not found")]})
    code, out, _ = run_main(cfg, capsys)
    assert code == 1 and "3/4 round trips identical" in out
    assert "recording failed: model_not_found" in next(l for l in out.splitlines() if l.startswith("openai"))


def test_a_mismatch_is_reported_as_no_and_exits_one():
    from app.llm.types import LLMResult

    def result(text, tokens_in, cost):
        return LLMResult(text, "c", "r", "sonnet", "m", "m", "anthropic", False, 1, tokens_in, 2, 5, cost, "stop")

    same = check.compare("sonnet", "m", result("x", 1, 0.1), result("x", 1, 0.1))
    assert same.identical and (same.same_text, same.same_tokens, same.same_cost) == ("yes", "yes", "yes")
    assert not check.compare("sonnet", "m", result("x", 1, 0.1), result("y", 1, 0.1)).identical
    assert check.compare("sonnet", "m", result("x", 1, 0.1), result("y", 1, 0.1)).same_text == "NO"
    assert check.compare("sonnet", "m", result("x", 1, 0.1), result("x", 2, 0.1)).same_tokens == "NO"
    assert check.compare("sonnet", "m", result("x", 1, 0.1), result("x", 1, 0.2)).same_cost == "NO"
    assert check.compare("sonnet", "m", result("x", 1, None), result("x", 1, None)).identical  # unknown == unknown


def test_slot_filter_checks_only_that_slot(cfg, fake_network, capsys):
    net = fake_network(GOOD)
    code, out, _ = run_main(cfg, capsys, "--slot", "gemini")
    assert code == 0 and "1/1 round trips identical" in out and net.seen == ["model-gemini"]


def test_output_never_contains_replies_keys_endpoint_or_user_agent(cfg, fake_network, capsys):
    fake_network({
        **GOOD,
        "model-sonnet": [reply(f"the secret reply with {KEY} and {OPENAI_KEY}")],
        "model-openai": [err(401, message=f"bad {OPENAI_KEY} {ENDPOINT} {AGENT}")],
    })
    code, out, err_out = run_main(cfg, capsys)
    assert code == 1
    for secret in (KEY, OPENAI_KEY, ENDPOINT, AGENT, "example.invalid", "the secret reply", "a perfectly fine reply"):
        assert secret not in out and secret not in err_out, secret


def test_the_temporary_folder_is_removed(cfg, fake_network, capsys, monkeypatch):
    import tempfile
    from pathlib import Path

    made: list[Path] = []
    real = tempfile.TemporaryDirectory

    def tracking(*a, **k):
        d = real(*a, **k)
        made.append(Path(d.name))
        return d

    monkeypatch.setattr(check.tempfile, "TemporaryDirectory", tracking)
    fake_network(GOOD)
    run_main(cfg, capsys)
    assert made and not any(p.exists() for p in made)


def test_it_never_touches_the_real_recordings_or_database(cfg, fake_network, capsys):
    fake_network(GOOD)
    run_main(cfg, capsys)
    assert not cfg.recordings_path.exists() and not cfg.db_path.exists()


def test_it_refuses_to_run_without_credentials(make_settings, capsys):
    code, out, err_out = run_main(make_settings(**MODELS), capsys)
    assert code == 2 and out == "" and "IBM_ICA_ENDPOINT" in err_out and "IBM_ICA_API_KEY" in err_out


def test_render_and_fingerprint():
    trips = [
        check.Trip("sonnet", "m", "1200", "3", "yes", "yes", "yes", "cost $0.000001"),
        check.Trip("openai", "", "-", "-", "-", "-", "-", "recording failed: auth"),
    ]
    text = check.render(trips)
    assert text.rstrip().endswith("1/2 round trips identical") and "(not set)" in text
    assert check.fingerprint("a") == check.fingerprint("a") != check.fingerprint("b")
    assert "a" not in check.fingerprint("a")[:0] + "" and len(check.fingerprint("a")) == 64
