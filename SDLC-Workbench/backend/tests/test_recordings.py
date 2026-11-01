"""The recording format: how a request is identified, what a file holds, and how a set is loaded."""
from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.llm.recordings import (
    FORMAT,
    KEY_PREFIX_LEN,
    Recording,
    RecordingInvalid,
    RecordingStore,
    key_from_parts,
    leaks_secret,
    parse_recording,
    recordings_mode,
    request_key,
)
from app.llm.types import LLMRequest, Message, ProviderResponse, Usage


def req(text="hello", *, role="requirements_analyst", **kw) -> LLMRequest:
    return LLMRequest.user(role, text, **kw)


def response(text="a reply", usage=Usage(10, 5), finish="stop") -> ProviderResponse:
    return ProviderResponse(text, usage, finish)


def rec(model="model-x", request=None, resp=None, latency=1234) -> Recording:
    return Recording.from_call(model, request or req(), resp or response(), latency, recorded_at="2026-01-01T00:00:00.000Z")


# ---- the key ----------------------------------------------------------------

def test_key_is_stable_and_a_sha256():
    key = request_key("m", req())
    assert key == request_key("m", req()) and len(key) == 64 and int(key, 16) >= 0


def test_the_key_format_is_pinned():
    """If this fails, the key recipe changed, and every saved recording would silently stop matching.
    Change the recipe only on purpose, bump FORMAT, and re-record."""
    assert key_from_parts("m", "", [("user", "hello")], 4096, None) == (
        "30beb093a4d5a46cb09fc023aaa94a4cad1911a1381332a52b8c506189b6e322"
    )
    assert key_from_parts("model-x", "be brief", [("user", "q"), ("assistant", "a")], 100, 0.5) == (
        "6977bd07f9c00e444b5b4d6d53c846cd32ffccd62c325daf9b90034d97d39cd9"
    )


@pytest.mark.parametrize(
    "a, b",
    [
        (dict(model="m1"), dict(model="m2")),
        (dict(system="a"), dict(system="b")),
        (dict(text="hello"), dict(text="hellp")),
        (dict(text="hello"), dict(text="hello ")),
        (dict(max_tokens=100), dict(max_tokens=101)),
        (dict(temperature=None), dict(temperature=0.0)),
        (dict(temperature=0.2), dict(temperature=0.3)),
    ],
)
def test_the_key_changes_with_anything_that_changes_the_answer(a, b):
    def key(model="m", system="", text="hello", max_tokens=4096, temperature=None):
        return request_key(model, LLMRequest.user("r", text, system=system, max_tokens=max_tokens, temperature=temperature))

    assert key(**a) != key(**b)


def test_message_order_matters():
    one = LLMRequest("r", (Message("user", "a"), Message("assistant", "b")))
    two = LLMRequest("r", (Message("assistant", "b"), Message("user", "a")))
    assert request_key("m", one) != request_key("m", two)
    swapped = LLMRequest("r", (Message("user", "b"), Message("assistant", "a")))
    assert request_key("m", one) != request_key("m", swapped)


def test_the_key_ignores_role_project_phase_and_run_id():
    base = request_key("m", req())
    assert base == request_key("m", req(role="other_role"))
    assert base == request_key("m", req(project_id="p1", phase_key="design", run_id="run-9"))


def test_equal_temperatures_written_differently_are_the_same_key():
    assert key_from_parts("m", "", [("user", "x")], 10, 1) == key_from_parts("m", "", [("user", "x")], 10, 1.0)


def test_unicode_and_very_long_text_are_fine_and_near_misses_do_not_collide():
    long = "é" * 200_000
    assert request_key("m", req(long)) != request_key("m", req(long + "."))
    assert request_key("m", req("日本語 ☃ \U0001f600")) == request_key("m", req("日本語 ☃ \U0001f600"))
    keys = {request_key("m", req(f"prompt {n}")) for n in range(500)}
    assert len(keys) == 500


def test_message_boundaries_cannot_be_confused():
    a = LLMRequest("r", (Message("user", "ab"), Message("user", "c")))
    b = LLMRequest("r", (Message("user", "a"), Message("user", "bc")))
    assert request_key("m", a) != request_key("m", b)


# ---- the file ---------------------------------------------------------------

def test_a_recording_round_trips_through_the_store(tmp_path):
    store = RecordingStore(tmp_path / "set")
    original = rec(request=req("question?", system="be brief", max_tokens=321, temperature=0.5))
    path = store.save(original)

    assert path.parent == tmp_path / "set" and path.name == f"{original.key[:KEY_PREFIX_LEN]}.json"
    reloaded = RecordingStore(tmp_path / "set").get(original.key)
    assert reloaded == original
    assert (reloaded.text, reloaded.usage, reloaded.finish_reason) == ("a reply", Usage(10, 5), "stop")
    assert (reloaded.role, reloaded.model, reloaded.latency_ms) == ("requirements_analyst", "model-x", 1234)
    assert (reloaded.system, reloaded.max_tokens, reloaded.temperature) == ("be brief", 321, 0.5)


def test_missing_usage_and_finish_reason_survive_the_round_trip(tmp_path):
    store = RecordingStore(tmp_path)
    original = rec(resp=ProviderResponse("text", None, None))
    store.save(original)
    again = RecordingStore(tmp_path).get(original.key)
    assert again.usage is None and again.finish_reason is None


def test_the_file_is_readable_json_with_a_format_field(tmp_path):
    store = RecordingStore(tmp_path)
    path = store.save(rec())
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["format"] == FORMAT and data["key"] and data["request"]["messages"] == [{"role": "user", "content": "hello"}]
    assert data["response"]["usage"] == {"tokens_in": 10, "tokens_out": 5}
    assert path.read_text(encoding="utf-8").endswith("\n")
    assert [p.name for p in tmp_path.iterdir()] == [path.name]  # one file per recording, nothing else


def test_non_ascii_text_is_stored_readably(tmp_path):
    store = RecordingStore(tmp_path)
    path = store.save(rec(resp=response("naïve café 日本語")))
    assert "café" in path.read_text(encoding="utf-8")
    assert RecordingStore(tmp_path).get(rec(resp=response("x")).key).text == "naïve café 日本語"


def test_recording_the_same_key_again_replaces_the_file(tmp_path):
    store = RecordingStore(tmp_path)
    store.save(rec(resp=response("first")))
    store.save(rec(resp=response("second")))
    assert len(list(tmp_path.glob("*.json"))) == 1
    assert RecordingStore(tmp_path).get(rec().key).text == "second"


# ---- saving safely -----------------------------------------------------------

def test_no_temporary_files_are_left_behind(tmp_path):
    store = RecordingStore(tmp_path)
    for n in range(10):
        store.save(rec(request=req(f"q{n}")))
    assert sorted(p.suffix for p in tmp_path.iterdir()) == [".json"] * 10


def test_a_failed_write_leaves_the_previous_file_intact_and_no_litter(tmp_path, monkeypatch):
    store = RecordingStore(tmp_path)
    path = store.save(rec(resp=response("good")))
    before = path.read_text(encoding="utf-8")

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        store.save(rec(resp=response("never lands")))
    monkeypatch.undo()
    assert path.read_text(encoding="utf-8") == before
    assert [p.name for p in tmp_path.iterdir()] == [path.name]


def test_twenty_concurrent_saves_of_different_keys_all_land(tmp_path):
    store = RecordingStore(tmp_path)

    def save(n):
        store.save(rec(request=req(f"prompt {n}")))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(save, range(20)))
    assert len(store) == 20 and len(RecordingStore(tmp_path)) == 20


def test_reading_the_store_while_another_thread_saves_never_crashes(tmp_path):
    """The lock's real job. One dict write is atomic, but counting walks the whole dict, and walking a
    dict that gains an entry mid-walk raises 'dictionary changed size during iteration'.

    Deterministic on purpose: each filler entry sleeps briefly when its model is read, so the count takes
    ~20 ms and the save below always arrives in the middle of it. (A free-running stress loop caught the
    missing lock only sometimes; this catches it every time.)"""
    import threading
    import time

    class SlowEntry:
        model = property(lambda self: (time.sleep(0.0005), "model-x")[1])

    store = RecordingStore(tmp_path)
    for n in range(40):
        store._entries[f"filler-{n}"] = SlowEntry()
    errors: list[BaseException] = []
    counting = threading.Event()

    def reader():
        try:
            counting.set()
            store.count_for_model("model-x")
        except BaseException as exc:  # noqa: BLE001 - the point is to catch anything
            errors.append(exc)

    thread = threading.Thread(target=reader)
    thread.start()
    counting.wait()
    time.sleep(0.002)  # let the count get under way
    store.save(rec())  # arrives mid-count
    thread.join()
    assert errors == []
    assert len(store) == 41


def test_twenty_concurrent_saves_of_the_same_key_leave_one_valid_file(tmp_path):
    store = RecordingStore(tmp_path)

    def save(n):
        store.save(rec(resp=response(f"reply {n}")))

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(save, range(20)))
    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1 and not list(tmp_path.glob(".tmp-*"))
    again = RecordingStore(tmp_path)
    assert again.problems == [] and again.get(rec().key).text.startswith("reply ")


# ---- loading -----------------------------------------------------------------

def test_a_missing_or_empty_set_is_fine(tmp_path):
    for folder in (tmp_path / "does-not-exist", tmp_path):
        store = RecordingStore(folder)
        assert len(store) == 0 and store.problems == []


def good_dict() -> dict:
    return rec().to_dict()


def write(folder, name, content) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")


def test_unusable_files_are_skipped_and_reported_by_name_without_content(tmp_path):
    good = good_dict()
    write(tmp_path, "good.json", good)
    write(tmp_path, "corrupt.json", '{"format": 1, "key": "SECRET-CONTENT')
    write(tmp_path, "list.json", ["a", "list"])
    write(tmp_path, "future.json", {**good, "format": 99})
    write(tmp_path, "nokey.json", {k: v for k, v in good.items() if k != "key"})
    write(tmp_path, "badusage.json", {**good, "response": {**good["response"], "usage": {"tokens_in": -1, "tokens_out": 2}}})
    write(tmp_path, "empty.json", {**good, "response": {**good["response"], "text": "   "}})
    (tmp_path / "binary.json").write_bytes(b"\xff\xfe\x00bad")

    store = RecordingStore(tmp_path)
    assert len(store) == 1
    reported = {p.file: p.reason for p in store.problems}
    assert set(reported) == {"corrupt.json", "list.json", "future.json", "nokey.json", "badusage.json", "empty.json", "binary.json"}
    assert "SECRET-CONTENT" not in " ".join(reported.values()) and "a reply" not in " ".join(reported.values())
    assert "format" in reported["future.json"] and "key" in reported["nokey.json"]


def test_a_recording_with_an_edited_prompt_is_rejected(tmp_path):
    data = good_dict()
    data["request"]["messages"][0]["content"] = "a different question"
    write(tmp_path, "edited.json", data)
    store = RecordingStore(tmp_path)
    assert len(store) == 0
    assert "prompt was edited" in store.problems[0].reason


def test_an_edited_response_is_allowed_that_is_how_a_recording_gets_scrubbed(tmp_path):
    data = good_dict()
    data["response"]["text"] = "scrubbed reply"
    write(tmp_path, "scrubbed.json", data)
    store = RecordingStore(tmp_path)
    assert store.problems == [] and store.get(data["key"]).text == "scrubbed reply"


def test_missing_latency_is_treated_as_zero_and_bad_latency_is_rejected(tmp_path):
    data = good_dict()
    del data["latency_ms"]
    assert parse_recording(data).latency_ms == 0
    data["latency_ms"] = -5
    with pytest.raises(RecordingInvalid):
        parse_recording(data)
    data["latency_ms"] = "slow"
    with pytest.raises(RecordingInvalid):
        parse_recording(data)


@pytest.mark.parametrize("bad_type", [True, "10", 1.5, None])
def test_fields_with_the_wrong_type_are_rejected(bad_type):
    data = good_dict()
    data["request"]["max_tokens"] = bad_type
    with pytest.raises(RecordingInvalid):
        parse_recording(data)


def test_count_for_model(tmp_path):
    store = RecordingStore(tmp_path)
    store.save(rec(model="a", request=req("1")))
    store.save(rec(model="a", request=req("2")))
    store.save(rec(model="b", request=req("1")))
    assert (store.count_for_model("a"), store.count_for_model("b"), store.count_for_model("c")) == (2, 1, 0)


def test_reload_picks_up_new_files(tmp_path):
    store = RecordingStore(tmp_path)
    write(tmp_path, "late.json", good_dict())
    assert len(store) == 0
    store.load()
    assert len(store) == 1


# ---- secrets -----------------------------------------------------------------

def test_leaks_secret_looks_at_prompt_system_and_reply():
    secret = "sk-SECRET-123456"
    assert leaks_secret(rec(request=req(f"my key is {secret}")), [secret])
    assert leaks_secret(rec(request=req("hi", system=f"use {secret}")), [secret])
    assert leaks_secret(rec(resp=response(f"echo {secret}")), [secret])
    assert not leaks_secret(rec(), [secret])
    assert not leaks_secret(rec(request=req("a key")), ["abc"])  # too short to be a credential: ignored
    assert not leaks_secret(rec(request=req("anything")), [])


# ---- settings ----------------------------------------------------------------

def test_defaults_and_the_recordings_folder(make_settings, tmp_path):
    s = Settings(_env_file=None)
    assert (s.replay_set, s.record_live_calls, s.replay_pace) == ("demo", False, 0.0)
    assert s.recordings_path.parts[-2:] == ("recordings", "demo")
    assert make_settings(replay_set="my-set_2").recordings_path == tmp_path / "recordings" / "my-set_2"


@pytest.mark.parametrize("bad", ["", "../x", "a/b", "a b", "x" * 65, "..", "a.b", "dé", "a\\b"])
def test_replay_set_names_cannot_escape_the_recordings_folder(bad):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, replay_set=bad)


@pytest.mark.parametrize("name", ["demo", "Demo-2", "a_b", "x" * 64, "123"])
def test_good_replay_set_names(name):
    assert Settings(_env_file=None, replay_set=name).replay_set == name


def test_pace_bounds():
    for bad in (-0.1, 1.1, 5):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, replay_pace=bad)
    assert Settings(_env_file=None, replay_pace=0.25).replay_pace == 0.25
    assert Settings(_env_file=None, replay_pace=1).replay_pace == 1


def test_new_settings_read_from_a_dotenv_file(tmp_path):
    path = tmp_path / "t.env"
    path.write_text("REPLAY_SET=night\nRECORD_LIVE_CALLS=true\nREPLAY_PACE=0.5\nRECORDINGS_DIR=/tmp/somewhere\n")
    s = Settings(_env_file=path)
    assert (s.replay_set, s.record_live_calls, s.replay_pace) == ("night", True, 0.5)
    assert str(s.recordings_path) == "/tmp/somewhere/night"


def test_recordings_mode(make_settings):
    creds = dict(ibm_ica_endpoint="https://x.invalid", ibm_ica_api_key="k")
    assert recordings_mode(make_settings(app_mode="replay")) == "replay"
    assert recordings_mode(make_settings(app_mode="replay", record_live_calls=True)) == "replay"
    assert recordings_mode(make_settings(app_mode="live", **creds)) == "off"
    assert recordings_mode(make_settings(app_mode="live", record_live_calls=True, **creds)) == "recording"
    assert recordings_mode(make_settings(app_mode="live", record_live_calls=True)) == "off"  # no credentials
