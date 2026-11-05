"""S23e: editing and saving the env file. Every test works on a file inside tmp_path; the real backend/.env is never opened, read or written."""
from __future__ import annotations

import os
import stat

import pytest

from app.config import Settings
from app.settings_admin import envfile as E
from app.settings_admin import save as S

SAMPLE = """# the settings of the app
IBM_ICA_ENDPOINT=https://gateway.example/path
IBM_ICA_API_KEY="old-key"
export APP_MODE=replay
RUN_BUDGET_USD=5.0   # per run
ADMIN_NAME='Parag Jain'

EMPTY=
REVIEW_FILE_MAX_OUTPUT_TOKENS=12000
"""


@pytest.fixture
def folder(tmp_path):
    env = tmp_path / ".env"
    env.write_text(SAMPLE, encoding="utf-8")
    os.chmod(env, 0o600)
    return env, tmp_path / "backups"


def record():
    seen: list[dict] = []
    return seen, seen.append


# ---- quoting ----------------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("value, written", [("7", "7"), ("", ""), ("https://x.example/a?b=1", "https://x.example/a?b=1"), ("two words", '"two words"'), (' lead', '" lead"'), ("a#b", '"a#b"'),
                                            ('say "hi"', '"say \\"hi\\""'), ("back\\slash", '"back\\\\slash"'), ("it's", '"it\'s"'), ("$HOME", '"$HOME"')])
def test_a_value_is_written_bare_when_safe_and_double_quoted_with_escapes_otherwise(value, written):
    assert E.quote(value) == written


@pytest.mark.parametrize("value", ["", "7", "two words", ' lead', "trail ", "a#b", 'say "hi"', "back\\slash", "it's", "$HOME", "x=y", "Zoë ü", "https://k.example/p?q=1&r=2#frag"])
def test_whatever_is_written_is_read_back_exactly_by_the_apps_own_reader(value):
    assert E.parse(E.apply("A=1\n", {"B": value}))["B"] == value


def test_a_line_break_or_a_very_long_value_is_refused():
    for bad in ("a\nb", "a\rb", "a\x00b"):
        with pytest.raises(E.EnvError, match="line break"):
            E.quote(bad)
    with pytest.raises(E.EnvError, match="at most"):
        E.quote("x" * (E.MAX_VALUE_CHARS + 1))
    assert E.quote("x" * E.MAX_VALUE_CHARS) == "x" * E.MAX_VALUE_CHARS


# ---- touching only the lines being changed ----------------------------------------------------------------------------------------------------------

def test_only_the_changed_line_differs_and_everything_else_is_kept_byte_for_byte():
    out = E.apply(SAMPLE, {"RUN_BUDGET_USD": "7.5"})
    before, after = SAMPLE.splitlines(keepends=True), out.splitlines(keepends=True)
    assert len(before) == len(after) and [i for i, (a, b) in enumerate(zip(before, after)) if a != b] == [4]
    assert after[4] == "RUN_BUDGET_USD=7.5   # per run\n" or after[4].startswith("RUN_BUDGET_USD=7.5") and after[4].endswith("# per run\n")


def test_comments_blank_lines_export_and_quotes_on_other_lines_survive():
    out = E.apply(SAMPLE, {"RUN_BUDGET_USD": "9"})
    for kept in ("# the settings of the app\n", 'IBM_ICA_API_KEY="old-key"\n', "export APP_MODE=replay\n", "ADMIN_NAME='Parag Jain'\n", "\nEMPTY=\n"):
        assert kept in out


def test_a_trailing_note_is_kept_when_its_line_is_rewritten_and_an_export_prefix_too():
    assert "# per run" in E.apply(SAMPLE, {"RUN_BUDGET_USD": "1"})
    assert "export APP_MODE=live" in E.apply(SAMPLE, {"APP_MODE": "live"})


def test_a_hash_inside_quotes_is_not_taken_for_a_note():
    out = E.apply('K="a # b"  # note\n', {"K": "c"})
    assert out == "K=c  # note\n"


def test_a_variable_not_in_the_file_is_added_at_the_end_and_a_missing_final_newline_is_supplied():
    out = E.apply("A=1", {"NEW_ONE": "x y"})
    assert out == 'A=1\nNEW_ONE="x y"\n'
    assert E.apply("", {"A": "1"}) == "A=1\n"


def test_when_a_name_appears_twice_the_last_line_the_one_that_wins_is_the_one_rewritten():
    out = E.apply("A=1\nB=2\nA=3\n", {"A": "9"})
    assert out == "A=1\nB=2\nA=9\n" and E.parse(out)["A"] == "9"


def test_a_commented_out_variable_is_left_alone_and_the_real_one_is_added():
    out = E.apply("# RUN_BUDGET_USD=5\n", {"RUN_BUDGET_USD": "8"})
    assert out == "# RUN_BUDGET_USD=5\nRUN_BUDGET_USD=8\n"


def test_windows_line_endings_are_kept_on_the_changed_line():
    out = E.apply("A=1\r\nB=2\r\n", {"A": "9"})
    assert out == "A=9\r\nB=2\r\n"


def test_a_bad_variable_name_is_refused():
    for bad in ("lower", "1BAD", "HAS SPACE", "A=B", ""):
        with pytest.raises(E.EnvError, match="not a variable name"):
            E.apply("", {bad: "1"})


def test_changed_names_lists_what_differs_by_the_apps_reader_not_by_text():
    assert E.changed_names("A=1\nB=2\n", "A=1\nB=\"2\"\n") == []                                     # the same value written differently is not a change
    assert E.changed_names("A=1\nB=2\n", "A=1\nB=3\nC=4\n") == ["B", "C"]
    assert E.changed_names("A=1\nB=2\n", "A=1\n") == ["B"]


# ---- what may be asked -----------------------------------------------------------------------------------------------------------------------------

def test_only_known_settings_can_be_changed_and_the_refusal_names_each_unknown_one():
    with pytest.raises(S.SaveRefused) as e:
        S.plan({"run_budget_usd": "7", "not_a_setting": "1", "path": "/etc/passwd"})
    assert e.value.problems == ["not_a_setting is not a setting that can be changed here", "path is not a setting that can be changed here"]


def test_a_blank_secret_means_keep_the_current_one_and_a_blank_normal_setting_means_empty():
    out = S.plan({"ibm_ica_api_key": "", "ibm_ica_endpoint": "   ", "ibm_ica_haiku_model_id": ""})
    assert out == {"IBM_ICA_HAIKU_MODEL_ID": ""}


def test_yes_no_and_choice_settings_take_only_their_values():
    assert S.plan({"record_live_calls": True, "ibm_ica_insecure_tls": "False", "app_mode": "live"}) == {"RECORD_LIVE_CALLS": "true", "IBM_ICA_INSECURE_TLS": "false", "APP_MODE": "live"}
    with pytest.raises(S.SaveRefused) as e:
        S.plan({"record_live_calls": "maybe", "app_mode": "turbo"})
    assert e.value.problems == ["RECORD_LIVE_CALLS must be true or false", "APP_MODE must be one of replay, live"]


# ---- the app's own checks ---------------------------------------------------------------------------------------------------------------------------

def test_the_candidate_is_checked_by_the_apps_own_limits():
    S.check("RUN_BUDGET_USD=7\nAPP_MODE=live\n")
    for text, name in (("RUN_BUDGET_USD=5000\n", "RUN_BUDGET_USD"), ("RUN_BUDGET_USD=abc\n", "RUN_BUDGET_USD"), ("APP_MODE=turbo\n", "APP_MODE"), ("RUN_MAX_CONCURRENCY=99\n", "RUN_MAX_CONCURRENCY"),
                       ("REPLAY_SET=../../etc\n", "REPLAY_SET"), ("IBM_ICA_PRICE_INPUT_PER_MTOK=-1\n", "IBM_ICA_PRICE_INPUT_PER_MTOK")):
        with pytest.raises(S.SaveRefused) as e:
            S.check(text)
        assert any(p.startswith(name + ":") for p in e.value.problems), (text, e.value.problems)


def test_a_refusal_never_repeats_the_value_that_was_typed():
    secret = "TYPED-SECRET-abc123"
    for text in (f"RUN_BUDGET_USD={secret}\n", f"APP_MODE={secret}\n", f"AGENT_OUTPUT_TOKENS_BY_ROLE={secret}\n", f"GUARDRAILS_DISABLED_RULES={secret}\n", f"REPLAY_SET={secret}!!\n"):
        with pytest.raises(S.SaveRefused) as e:
            S.check(text)
        assert secret not in str(e.value) and secret not in " ".join(e.value.problems), text


def test_the_app_never_puts_a_typed_value_in_the_error_for_a_role_limit_either():
    with pytest.raises(S.SaveRefused) as e:
        S.check("AGENT_OUTPUT_TOKENS_BY_ROLE=ux_designer=7\n")
    assert e.value.problems == ["AGENT_OUTPUT_TOKENS_BY_ROLE: Value error, the output limit for 'ux_designer' must be between 256 and 64000"]
    with pytest.raises(S.SaveRefused) as e2:
        S.check("AGENT_OUTPUT_TOKENS_BY_ROLE=SECRETWORD\n")
    assert e2.value.problems == ["AGENT_OUTPUT_TOKENS_BY_ROLE: Value error, AGENT_OUTPUT_TOKENS_BY_ROLE entries look like 'ux_designer=24000'"]


def test_a_rule_the_app_writes_as_a_plain_error_is_still_a_clean_refusal():
    with pytest.raises(S.SaveRefused) as e:
        S.check("AGENT_OUTPUT_TOKENS_BY_ROLE=not-a-pair\n")
    assert "AGENT_OUTPUT_TOKENS_BY_ROLE" in " ".join(e.value.problems)


# ---- saving --------------------------------------------------------------------------------------------------------------------------------------------

def test_a_valid_change_is_written_and_the_app_reads_it_back_and_everything_else_is_untouched(folder):
    env, bk = folder
    seen, rec = record()
    r = S.save(env, bk, {"run_budget_usd": "7.5", "app_mode": "live"}, record=rec)
    assert r.changed == ["APP_MODE", "RUN_BUDGET_USD"] and r.restart is True and r.backup.startswith("env-") and r.backup.endswith(".bak")
    text = env.read_text(encoding="utf-8")
    assert "# the settings of the app" in text and 'IBM_ICA_API_KEY="old-key"' in text and "# per run" in text
    loaded = Settings(_env_file=env)
    assert loaded.run_budget_usd == 7.5 and loaded.app_mode == "live" and loaded.ibm_ica_api_key.get_secret_value() == "old-key"
    assert len(seen) == 1


def test_nothing_is_written_when_nothing_changes(folder):
    env, bk = folder
    seen, rec = record()
    before = env.read_bytes()
    r = S.save(env, bk, {"run_budget_usd": "5.0", "app_mode": "replay", "ibm_ica_api_key": ""}, record=rec)
    assert r.changed == [] and r.restart is False and r.backup == "" and env.read_bytes() == before and not bk.exists() and seen == []


def test_a_refused_save_writes_nothing_backs_nothing_up_and_records_nothing(folder):
    env, bk = folder
    seen, rec = record()
    before = env.read_bytes()
    for bad in ({"run_budget_usd": "5000"}, {"app_mode": "turbo"}, {"nope": "1"}, {"run_budget_usd": "7", "run_max_concurrency": "99"}):
        with pytest.raises(S.SaveRefused):
            S.save(env, bk, bad, record=rec)
    assert env.read_bytes() == before and not bk.exists() and seen == []


def test_the_old_file_is_backed_up_first_into_a_private_folder_and_the_backup_holds_the_old_text(folder):
    env, bk = folder
    old = env.read_bytes()
    r = S.save(env, bk, {"run_budget_usd": "9"}, record=lambda d: None)
    assert (bk / r.backup).read_bytes() == old
    assert stat.S_IMODE(os.stat(bk).st_mode) == 0o700 and stat.S_IMODE(os.stat(bk / r.backup).st_mode) == 0o600


def test_the_new_file_keeps_the_old_files_permissions_and_no_temporary_file_is_left(folder):
    env, bk = folder
    S.save(env, bk, {"run_budget_usd": "9"}, record=lambda d: None)
    assert stat.S_IMODE(os.stat(env).st_mode) == 0o600 and [p.name for p in env.parent.iterdir() if p.name.startswith(".env-")] == []


def test_only_the_newest_ten_backups_are_kept(folder):
    env, bk = folder
    names = []
    for n in range(14):
        names.append(S.save(env, bk, {"run_budget_usd": str(10 + n)}, record=lambda d: None).backup)
    kept = sorted(p.name for p in bk.glob("env-*.bak"))
    assert len(kept) == S.BACKUPS_KEPT == 10 and kept == sorted(names)[-10:]


def test_a_failure_while_swapping_in_the_file_leaves_the_old_file_and_no_temporary_file(folder, monkeypatch):
    env, bk = folder
    before = env.read_bytes()
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        S.save(env, bk, {"run_budget_usd": "9"}, record=lambda d: None)
    assert env.read_bytes() == before and [p.name for p in env.parent.iterdir() if p.name.startswith(".env-")] == []


def test_a_missing_file_is_created_private_with_just_the_changes(tmp_path):
    env, bk = tmp_path / "sub.env", tmp_path / "bk"
    r = S.save(env, bk, {"run_budget_usd": "3"}, record=lambda d: None)
    assert env.read_text() == "RUN_BUDGET_USD=3\n" and stat.S_IMODE(os.stat(env).st_mode) == 0o600 and r.changed == ["RUN_BUDGET_USD"]


# ---- secrets ---------------------------------------------------------------------------------------------------------------------------------------

def test_a_new_secret_is_written_and_a_blank_one_leaves_the_old_one_in_place(folder):
    env, bk = folder
    S.save(env, bk, {"ibm_ica_api_key": "brand-new-key", "run_budget_usd": "6"}, record=lambda d: None)
    assert Settings(_env_file=env).ibm_ica_api_key.get_secret_value() == "brand-new-key"
    S.save(env, bk, {"ibm_ica_api_key": "", "run_budget_usd": "7"}, record=lambda d: None)
    assert Settings(_env_file=env).ibm_ica_api_key.get_secret_value() == "brand-new-key"


def test_the_audit_detail_names_the_variables_and_shows_old_and_new_for_normal_ones_but_never_a_secret_value(folder):
    env, bk = folder
    seen, rec = record()
    S.save(env, bk, {"run_budget_usd": "7.5", "ibm_ica_api_key": "NEW-SECRET-VALUE", "ibm_ica_endpoint": "https://new.example/secret"}, record=rec)
    [detail] = seen
    assert detail["variables"] == ["IBM_ICA_API_KEY", "IBM_ICA_ENDPOINT", "RUN_BUDGET_USD"]
    assert detail["values"] == {"RUN_BUDGET_USD": {"before": "5.0", "after": "7.5"}} and detail["secrets_changed"] == ["IBM_ICA_API_KEY", "IBM_ICA_ENDPOINT"]
    text = repr(detail)
    for leaked in ("NEW-SECRET-VALUE", "old-key", "new.example", "gateway.example"):
        assert leaked not in text


def test_a_secret_value_appears_in_no_refusal_either(folder):
    env, bk = folder
    with pytest.raises(S.SaveRefused) as e:
        S.save(env, bk, {"ibm_ica_api_key": "LEAKY-KEY-999", "run_budget_usd": "5000"}, record=lambda d: None)
    assert "LEAKY-KEY-999" not in str(e.value) and "LEAKY-KEY-999" not in " ".join(e.value.problems)


# ---- restoring a backup ------------------------------------------------------------------------------------------------------------------------

def test_a_backup_can_be_put_back_after_backing_up_the_file_as_it_is_now(folder):
    env, bk = folder
    first = S.save(env, bk, {"run_budget_usd": "9"}, record=lambda d: None)
    seen, rec = record()
    r = S.restore(env, bk, first.backup, record=rec)
    assert Settings(_env_file=env).run_budget_usd == 5.0 and r.changed == ["RUN_BUDGET_USD"] and r.backup != first.backup
    assert seen[0]["restored"] == first.backup
    assert E.parse((bk / r.backup).read_text())["RUN_BUDGET_USD"] == "9"


@pytest.mark.parametrize("name", ["../x.bak", "env-..\\x.bak", "notes.txt", "env-1.txt", "/etc/passwd", "env-20260101-000000-000000.bak"])
def test_only_a_plain_backup_name_in_the_backups_folder_can_be_restored(folder, name):
    env, bk = folder
    bk.mkdir()
    before = env.read_bytes()
    with pytest.raises(S.SaveRefused):
        S.restore(env, bk, name, record=lambda d: None)
    assert env.read_bytes() == before


def test_a_backup_the_app_would_no_longer_accept_is_not_restored(folder):
    env, bk = folder
    bk.mkdir()
    (bk / "env-20260101-000000-000001.bak").write_text("RUN_BUDGET_USD=99999\n")
    before = env.read_bytes()
    with pytest.raises(S.SaveRefused):
        S.restore(env, bk, "env-20260101-000000-000001.bak", record=lambda d: None)
    assert env.read_bytes() == before


def test_the_backups_are_listed_newest_first_and_an_empty_or_missing_folder_is_an_empty_list(folder, tmp_path):
    env, bk = folder
    assert S.list_backups(bk) == [] and S.list_backups(tmp_path / "none") == []
    a = S.save(env, bk, {"run_budget_usd": "6"}, record=lambda d: None).backup
    b = S.save(env, bk, {"run_budget_usd": "7"}, record=lambda d: None).backup
    assert [x["name"] for x in S.list_backups(bk)] == [b, a] and all(x["size"] > 0 for x in S.list_backups(bk))


# ---- the real file is never touched -----------------------------------------------------------------------------------------------------------------

def test_the_real_env_file_is_pointed_at_a_missing_path_for_every_test():
    import app.config as config
    assert not config.ENV_FILE.exists() and "no-such.env" in str(config.ENV_FILE)
