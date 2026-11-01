"""The run demo script: offline walk-through, and the live path over a fake network."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import httpx
import pytest

import scripts.run_demo as demo
from app.llm.providers.ica import IcaProvider

from .test_agent_misc import scripted_reply_for
from .test_agent_runtime import MODELS
from .test_ica_provider import ENDPOINT, KEY, reply as http_reply


def test_the_offline_run_demo_shows_all_four_behaviours_and_says_it_is_scripted(capsys):
    assert demo.main([]) == 0
    out = capsys.readouterr().out
    assert "SCRIPTED FAKE MODEL" in out.splitlines()[0] and "the delays below are made up" in out
    assert "up to 3 artefact(s)" not in out and "7 artefact(s), up to 3 at once" in out
    assert "gate.changed       requirements is now running" in out and "run.finished" in out
    assert "x faster with 3 at once" in out and "four steps deep" in out
    assert "2 done, 0 failed, 0 skipped, 5 not started" in out and "it went over the cap by $" in out
    assert "blocked by non_functional_requirements" in out
    assert "still done: personas, problem_statement, vision_objectives, functional_requirements" in out
    assert "skipped without calling the model: epics_features, user_stories" in out
    assert out.rstrip().endswith("everything behaved as specified")


def test_the_offline_run_demo_exits_one_if_a_cap_does_not_stop_the_run(monkeypatch, capsys):
    from app.run.budget import Meter

    monkeypatch.setattr(Meter, "should_stop", lambda self: None)     # the caps no longer work
    assert demo.main([]) == 1
    assert "SOMETHING DID NOT BEHAVE AS SPECIFIED" in capsys.readouterr().out


def test_the_offline_run_demo_needs_no_credentials_and_cleans_up(make_settings, monkeypatch, capsys):
    for name in ("IBM_ICA_API_KEY", "IBM_ICA_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)
    made = []
    real = tempfile.TemporaryDirectory

    def tracking(*a, **k):
        d = real(*a, **k)
        made.append(Path(d.name))
        return d

    monkeypatch.setattr(demo.tempfile, "TemporaryDirectory", tracking)
    cfg = make_settings()
    assert demo.main([]) == 0
    capsys.readouterr()
    assert made and not any(p.exists() for p in made) and not cfg.db_path.exists()


def test_the_live_run_demo_refuses_without_credentials_and_names_which(make_settings, capsys):
    assert demo.main(["--live"], settings=make_settings(**MODELS)) == 2
    err = capsys.readouterr().err
    assert "IBM_ICA_ENDPOINT" in err and "IBM_ICA_API_KEY" in err
    assert demo.main(["--live"], settings=make_settings(**MODELS, ibm_ica_endpoint=ENDPOINT)) == 2
    assert "IBM_ICA_API_KEY" in capsys.readouterr().err


def test_serial_only_makes_sense_with_live(capsys):
    with pytest.raises(SystemExit) as caught:
        demo.main(["--serial"])
    assert caught.value.code == 2


def _wire(monkeypatch, handler):
    real_init = IcaProvider.__init__
    monkeypatch.setattr(IcaProvider, "__init__", lambda self, settings, *, transport=None: real_init(self, settings, transport=httpx.MockTransport(handler)))


def _ok_handler(calls):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        task = json.loads(request.content)["messages"][1]["content"]
        return httpx.Response(200, json=http_reply(scripted_reply_for(task), usage={"prompt_tokens": 900, "completion_tokens": 300}))

    return handler


def test_a_live_run_runs_setup_then_the_phase_prints_events_and_the_real_speed_up_and_never_a_secret(make_settings, capsys, monkeypatch):
    cfg = make_settings(**MODELS, ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY, ibm_ica_user_agent="UA-secret-1234")
    calls = []
    _wire(monkeypatch, _ok_handler(calls))
    assert demo.main(["--live"], settings=cfg) == 0
    out = capsys.readouterr()
    assert len(calls) == 8                                                       # the charter, then the seven Requirements artefacts
    assert "REAL MODELS via IBM ICA (up to 3 at once;" in out.out and "run.started" in out.out and "run.finished" in out.out
    assert "finished: 7 done, 0 failed, 0 skipped, 0 not started" in out.out
    assert "on the wall clock; the artefacts' own times add up to" in out.out and "that is the real speed-up" in out.out
    for secret in (KEY, ENDPOINT, "UA-secret-1234"):
        assert secret not in out.out and secret not in out.err


def test_live_serial_says_so_and_still_finishes(make_settings, capsys, monkeypatch):
    cfg = make_settings(**MODELS, ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY)
    _wire(monkeypatch, _ok_handler([]))
    assert demo.main(["--live", "--serial"], settings=cfg) == 0
    assert "REAL MODELS via IBM ICA (one at a time;" in capsys.readouterr().out


def test_a_live_run_where_the_service_refuses_exits_one_with_a_reason_and_no_traceback_or_key(make_settings, capsys, monkeypatch):
    cfg = make_settings(**MODELS, ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY)
    _wire(monkeypatch, lambda request: httpx.Response(401, json={"error": {"message": f"bad key {KEY}"}}))
    assert demo.main(["--live"], settings=cfg) == 1
    err = capsys.readouterr().err
    assert "The real-model run failed" in err and KEY not in err and "Traceback" not in err


def test_a_live_run_that_finishes_with_a_failed_artefact_exits_one_and_says_which_and_why(make_settings, capsys, monkeypatch):
    cfg = make_settings(**MODELS, ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY)

    def handler(request: httpx.Request) -> httpx.Response:
        task = json.loads(request.content)["messages"][1]["content"]
        if "(non_functional_requirements) for the project" in task:
            return httpx.Response(200, json=http_reply("no artefact block here"))
        return httpx.Response(200, json=http_reply(scripted_reply_for(task)))

    _wire(monkeypatch, handler)
    assert demo.main(["--live"], settings=cfg) == 1
    out = capsys.readouterr().out
    assert "failed: 4 done, 1 failed, 2 skipped" in out
    assert "non_functional_requirements: failed:" in out and "epics_features: skipped: blocked by non_functional_requirements" in out
