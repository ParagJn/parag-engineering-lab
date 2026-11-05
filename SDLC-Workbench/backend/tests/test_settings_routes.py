"""S23e: saving settings over HTTP. The app is given an env file inside tmp_path by hand; the real backend/.env is never opened. Who may save, what is refused, the restart message and the audit row."""
from __future__ import annotations

import json
import os

import httpx
import pytest

from app.config import Settings
from app.main import create_app
from app.settings_admin import save as S

pytestmark = pytest.mark.anyio
SAMPLE = "IBM_ICA_API_KEY=old-key\nIBM_ICA_ENDPOINT=https://gateway.example/p\nRUN_BUDGET_USD=5.0\nADMIN_NAME=Root\n"


@pytest.fixture
def world(make_settings, tmp_path):
    """An app whose settings file is a file in tmp_path. Nothing here can reach the real one: the app only gets a path to write when the test hands it one."""
    env = tmp_path / "work.env"
    env.write_text(SAMPLE, encoding="utf-8")
    os.chmod(env, 0o600)
    app = create_app(make_settings(admin_name="Root", ibm_ica_api_key="old-key", ibm_ica_endpoint="https://gateway.example/p"))
    app.state.env_file, app.state.env_backups = env, tmp_path / "bk"
    app.state.settings_at_start = Settings(_env_file=env).model_dump_json()
    return app, env


def client(app, name=None):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"X-Actor": name} if name else {})


# ---- an app that was given its settings cannot write a file --------------------------------------------------------------------------------------

async def test_an_app_started_with_given_settings_has_no_file_to_write_and_says_so(make_settings):
    app = create_app(make_settings())
    assert app.state.env_file is None and app.state.env_backups is None
    c = client(app, "Root")
    body = (await c.get("/api/settings")).json()
    assert body["editable"] is False and body["can_edit"] is False and "cannot be changed here" in body["note"]
    r = await c.put("/api/settings", json={"values": {"run_budget_usd": "9"}})
    assert r.status_code == 409 and "cannot be changed here" in r.json()["detail"]
    assert (await c.post("/api/settings/restore", json={"name": "env-x.bak"})).status_code == 409
    await c.aclose()


def test_only_an_app_that_loaded_the_real_file_itself_is_given_a_path_to_it(monkeypatch, tmp_path):
    import app.config as config
    import importlib
    import sys
    sys.modules.pop("app.main", None)                                                                         # another test imports app.main again with get_settings stubbed; start from a clean copy
    main = importlib.import_module("app.main")
    fake = tmp_path / "pretend.env"
    fake.write_text(f"DATA_DIR={tmp_path / 'db'}\nRECORDINGS_DIR={tmp_path / 'rec'}\nRUN_BUDGET_USD=6\n")        # the database and recordings are pointed at tmp_path by the file itself
    monkeypatch.setattr(config, "ENV_FILE", fake); monkeypatch.setattr(main, "ENV_FILE", fake); config.get_settings.cache_clear()
    try:
        app = main.create_app()
        assert app.state.env_file == fake and app.state.env_backups == tmp_path / "db" / "env-backups" and app.state.settings.run_budget_usd == 6.0
    finally:
        config.get_settings.cache_clear()                                                                      # the cached settings of this test must not reach the next one


# ---- reading -------------------------------------------------------------------------------------------------------------------------------------

async def test_the_answer_says_whether_it_can_be_edited_whether_a_restart_is_waiting_the_sentence_and_the_backups(world):
    app, env = world
    c = client(app, "Root")
    body = (await c.get("/api/settings")).json()
    assert body["editable"] is True and body["can_edit"] is True and body["restart_pending"] is False and body["backups"] == []
    assert body["restart_sentence"] == "Saved. Restart the app for this to take effect."
    await c.aclose()


async def test_a_save_needs_a_name_and_while_nobody_is_on_the_list_any_name_will_do(world):
    app, env = world
    bare = client(app)
    assert (await bare.put("/api/settings", json={"values": {"run_budget_usd": "9"}})).status_code == 400
    await bare.aclose()
    empty = create_app(Settings(_env_file=None, data_dir=str(env.parent / "d2"), recordings_dir=str(env.parent / "r2")))
    empty.state.env_file, empty.state.env_backups = env, env.parent / "bk"
    empty.state.settings_at_start = Settings(_env_file=env).model_dump_json()
    assert empty.state.store.users.count_active() == 0
    c = client(empty, "Anyone")
    assert (await c.get("/api/settings")).json()["can_edit"] is True and (await c.put("/api/settings", json={"values": {"run_budget_usd": "6"}})).status_code == 200
    await c.aclose()


# ---- who may save ----------------------------------------------------------------------------------------------------------------------------------

async def test_only_an_administrator_can_save_once_there_is_a_list(world):
    app, env = world
    app.state.store.users.add("Ann", ["Architect"], actor="human:Root")
    before = env.read_bytes()
    for who in ("Ann", "Stranger"):
        c = client(app, who)
        r = await c.put("/api/settings", json={"values": {"run_budget_usd": "9"}})
        assert r.status_code == 403 and "only an Administrator" in r.json()["detail"], who
        assert (await c.get("/api/settings")).json()["can_edit"] is False
        assert (await c.post("/api/settings/restore", json={"name": "env-20260101-000000-000001.bak"})).status_code == 403
        await c.aclose()
    assert env.read_bytes() == before
    admin = client(app, "root")
    assert (await admin.get("/api/settings")).json()["can_edit"] is True and (await admin.put("/api/settings", json={"values": {"run_budget_usd": "9"}})).status_code == 200
    await admin.aclose()


async def test_a_switched_off_administrator_cannot_save_and_the_page_is_told_so(world):
    app, env = world
    app.state.store.users.add("Zed", ["Administrator"], actor="human:Root"); app.state.store.users.set_active("Root", False, actor="human:Zed")
    c = client(app, "Root")
    assert (await c.get("/api/settings")).json()["can_edit"] is False
    assert (await c.put("/api/settings", json={"values": {"run_budget_usd": "9"}})).status_code == 403
    await c.aclose()


# ---- saving ----------------------------------------------------------------------------------------------------------------------------------------

async def test_a_save_writes_the_file_backs_up_the_old_one_says_to_restart_and_records_who_did_it(world):
    app, env = world
    c = client(app, "Root")
    r = await c.put("/api/settings", json={"values": {"run_budget_usd": "7.5", "app_mode": "live"}})
    body = r.json()
    assert r.status_code == 200 and body["saved"]["changed"] == ["APP_MODE", "RUN_BUDGET_USD"] and body["saved"]["message"] == "Saved. Restart the app for this to take effect."
    assert body["restart_pending"] is True and [b["name"] for b in body["backups"]] == [body["saved"]["backup"]]
    assert Settings(_env_file=env).run_budget_usd == 7.5
    assert app.state.settings.run_budget_usd == 5.0                                                  # the running app keeps what it started with, until it is restarted
    [event] = [a for a in app.state.store.audit.list() if a.action == "settings.changed"]
    assert event.actor == "human:Root" and event.target_type == "settings" and event.detail["variables"] == ["APP_MODE", "RUN_BUDGET_USD"]
    assert event.detail["values"]["RUN_BUDGET_USD"] == {"before": "5.0", "after": "7.5"}
    await c.aclose()


async def test_a_secret_is_replaced_without_being_shown_or_logged_anywhere(world):
    app, env = world
    c = client(app, "Root")
    r = await c.put("/api/settings", json={"values": {"ibm_ica_api_key": "BRAND-NEW-SECRET-77", "ibm_ica_endpoint": "https://new.example/hidden"}})
    assert r.status_code == 200
    everything = r.text + json.dumps([a.detail for a in app.state.store.audit.list()]) + (await c.get("/api/settings")).text
    for leaked in ("BRAND-NEW-SECRET-77", "new.example", "old-key", "gateway.example"):
        assert leaked not in everything, leaked
    assert Settings(_env_file=env).ibm_ica_api_key.get_secret_value() == "BRAND-NEW-SECRET-77"
    event = [a for a in app.state.store.audit.list() if a.action == "settings.changed"][-1]
    assert event.detail["secrets_changed"] == ["IBM_ICA_API_KEY", "IBM_ICA_ENDPOINT"] and "values" not in event.detail
    await c.aclose()


async def test_a_blank_secret_box_keeps_the_key(world):
    app, env = world
    c = client(app, "Root")
    r = await c.put("/api/settings", json={"values": {"ibm_ica_api_key": "", "run_budget_usd": "8"}})
    assert r.status_code == 200 and Settings(_env_file=env).ibm_ica_api_key.get_secret_value() == "old-key"
    await c.aclose()


async def test_a_value_the_app_would_not_accept_is_refused_with_the_variable_and_the_apps_sentence_and_nothing_changes(world):
    app, env = world
    before = env.read_bytes()
    c = client(app, "Root")
    r = await c.put("/api/settings", json={"values": {"run_budget_usd": "5000", "ibm_ica_api_key": "TYPED-KEY-12345"}})
    detail = r.json()["detail"]
    assert r.status_code == 422 and detail["message"].startswith("the settings were not saved") and any(p.startswith("RUN_BUDGET_USD:") for p in detail["problems"])
    assert "TYPED-KEY-12345" not in r.text and env.read_bytes() == before and not (env.parent / "bk").exists()
    assert not [a for a in app.state.store.audit.list() if a.action == "settings.changed"]
    await c.aclose()


async def test_an_unknown_setting_or_a_bad_choice_is_refused_by_name(world):
    app, env = world
    c = client(app, "Root")
    r = await c.put("/api/settings", json={"values": {"not_a_setting": "1", "app_mode": "turbo"}})
    assert r.status_code == 422 and r.json()["detail"]["problems"] == ["not_a_setting is not a setting that can be changed here", "APP_MODE must be one of replay, live"]
    await c.aclose()


async def test_nothing_different_means_nothing_saved_and_no_restart_asked_for(world):
    app, env = world
    c = client(app, "Root")
    r = await c.put("/api/settings", json={"values": {"run_budget_usd": "5.0", "ibm_ica_api_key": ""}})
    assert r.status_code == 200 and r.json()["saved"] == {"changed": [], "backup": "", "message": "Nothing was different, so nothing was saved."} and r.json()["restart_pending"] is False
    await c.aclose()


async def test_the_request_shape_is_checked_at_the_edge(world):
    app, env = world
    c = client(app, "Root")
    for body in ({}, {"values": "x"}, {"values": {}, "extra": 1}):
        assert (await c.put("/api/settings", json=body)).status_code == 422, body
    many = await c.put("/api/settings", json={"values": {str(i): "1" for i in range(101)}})
    assert many.status_code == 422 and isinstance(many.json()["detail"], list)                                     # refused at the edge by the request shape, before any setting is looked at
    few = await c.put("/api/settings", json={"values": {str(i): "1" for i in range(100)}})
    assert few.status_code == 422 and isinstance(few.json()["detail"], dict)                                        # 100 is allowed through to the saver, which then names each unknown setting
    await c.aclose()


async def test_the_restart_banner_stays_until_the_file_reads_the_same_as_the_running_app(world):
    app, env = world
    c = client(app, "Root")
    await c.put("/api/settings", json={"values": {"run_budget_usd": "9"}})
    assert (await c.get("/api/settings")).json()["restart_pending"] is True
    await c.put("/api/settings", json={"values": {"run_budget_usd": "5.0"}})                        # put it back to what the app started with
    assert (await c.get("/api/settings")).json()["restart_pending"] is False
    app.state.settings_at_start = Settings(_env_file=env).model_dump_json()
    assert (await c.get("/api/settings")).json()["restart_pending"] is False                         # what a restart does
    await c.aclose()


async def test_a_file_the_app_would_not_accept_counts_as_a_change_waiting(world):
    app, env = world
    env.write_text(SAMPLE + "RUN_BUDGET_USD=banana\n")
    c = client(app, "Root")
    assert (await c.get("/api/settings")).json()["restart_pending"] is True
    await c.aclose()


# ---- restoring ----------------------------------------------------------------------------------------------------------------------------------------

async def test_a_backup_can_be_restored_by_an_administrator_with_the_same_restart_message_and_an_audit_row(world):
    app, env = world
    c = client(app, "Root")
    first = (await c.put("/api/settings", json={"values": {"run_budget_usd": "9"}})).json()["saved"]["backup"]
    r = await c.post("/api/settings/restore", json={"name": first})
    assert r.status_code == 200 and r.json()["saved"]["changed"] == ["RUN_BUDGET_USD"] and r.json()["saved"]["message"].startswith("Saved. Restart")
    assert Settings(_env_file=env).run_budget_usd == 5.0
    assert [a.detail["restored"] for a in app.state.store.audit.list() if a.action == "settings.restored"] == [first]
    await c.aclose()


@pytest.mark.parametrize("name", ["../x.bak", "notes.txt", "env-20260101-000000-000009.bak"])
async def test_restoring_something_that_is_not_a_backup_is_refused(world, name):
    app, env = world
    before = env.read_bytes()
    c = client(app, "Root")
    r = await c.post("/api/settings/restore", json={"name": name})
    assert r.status_code == 422 and env.read_bytes() == before
    await c.aclose()


# ---- the real file ----------------------------------------------------------------------------------------------------------------------------------

def test_a_normal_test_app_cannot_write_the_real_settings_file(make_settings):
    app = create_app(make_settings())
    assert app.state.env_file is None
    import app.config as config
    assert not config.ENV_FILE.exists()


def test_the_saver_is_only_ever_given_a_path_by_the_app_and_never_names_the_real_file_itself():
    import inspect
    source = inspect.getsource(S)
    assert "ENV_FILE" not in source and "config" not in source.split("from ..config import")[0]                # it imports Settings to validate, and never the constant that points at the real file


def test_no_test_in_the_settings_files_names_the_real_env_file():
    """A guard from outside the code: the three settings test files must never point at backend/.env. They work on files in tmp_path only."""
    import pathlib
    here = pathlib.Path(__file__).parent
    for name in ("test_settings_routes.py", "test_settings_save.py", "test_settings_view.py"):
        text = (here / name).read_text(encoding="utf-8")
        assert "parent.parent / \".env\"" not in text and "backend/.env\")" not in text and "open(\".env\"" not in text, name


async def test_a_failure_while_writing_says_what_kind_of_failure_and_never_the_system_message(world, monkeypatch):
    app, env = world
    monkeypatch.setattr(S, "write_atomic", lambda *a, **k: (_ for _ in ()).throw(OSError("/Users/someone/secret/path: disk full")))
    c = client(app, "Root")
    r = await c.put("/api/settings", json={"values": {"run_budget_usd": "9"}})
    assert r.status_code == 500 and r.json()["detail"] == "the settings file could not be written: OSError" and "secret" not in r.text and "/Users" not in r.text
    r2 = await c.post("/api/settings/restore", json={"name": "env-20260101-000000-000001.bak"})
    assert r2.status_code == 422                                                                                  # no such backup: refused before anything is written
    await c.aclose()


def test_the_app_remembers_what_it_started_with_so_it_can_tell_when_the_file_has_moved_on(make_settings):
    cfg = make_settings(run_budget_usd=7)
    app = create_app(cfg)
    assert app.state.settings_at_start == cfg.model_dump_json() and "7.0" in app.state.settings_at_start


async def test_the_answer_depends_on_who_asks_so_a_read_without_a_name_says_nobody_may_edit_and_with_the_admins_name_says_yes(world):
    """The page once read the settings WITHOUT the typed name, so an Administrator was told they could only read. The server must answer by the name it is given."""
    app, env = world
    app.state.store.users.add("Ann", ["Architect"], actor="human:Root")
    anyone = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    assert (await anyone.get("/api/settings")).json()["can_edit"] is False                              # no name: the list is in force, so no one is an Administrator
    for name, may in (("Root", True), ("root", True), ("Ann", False), ("Stranger", False)):
        c = client(app, name)
        assert (await c.get("/api/settings")).json()["can_edit"] is may, name
        await c.aclose()
    await anyone.aclose()
