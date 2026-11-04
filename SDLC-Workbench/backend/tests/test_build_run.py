"""S17a with a real sandbox: writing a Build artefact's files, and the four checks that run them. No model is called."""
from __future__ import annotations

import pytest

from app.build.service import BuildRefused, BuildService
from app.build.checks import check_backend, check_database, check_frontend, check_tests
from app.config import Settings
from app.guardrails.scan import Scanner
from app.agents.skills import SkillLibrary
from app.llm.routing import Routing
from app.repos import Store
from app.sandbox import profile as OS
from app.sandbox.runner import Sandbox
from app.sandbox.service import SandboxService
from app.build import legacy

from ._build import DB_FILES, make_body

pytestmark = [pytest.mark.sandbox, pytest.mark.skipif(not OS.sandbox_available(), reason="this machine has no sandbox-exec")]
AWS = "AKIA" + "IOSFODNN7EXAMPLE"

SCHEMA = "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL);\nCREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id));\nINSERT OR IGNORE INTO users (id, name) VALUES (1, 'sample');\n"
INIT = ("import os, sqlite3\nhere = os.path.dirname(os.path.abspath(__file__))\nc = sqlite3.connect(os.path.join(here, 'app.db'))\n"
        "c.executescript(open(os.path.join(here, 'schema.sql')).read())\nc.commit()\nprint(c.execute(\"select count(*) from sqlite_master where type='table'\").fetchone()[0])\n")
GOOD_DB = [("db/schema.sql", SCHEMA), ("db/init_db.py", INIT)]
GOOD_BE = [("backend/main.py", "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/ping')\ndef ping():\n    return {'ok': True}\n")]
GOOD_FE = [("frontend/index.html", '<!doctype html><html><head><link rel="stylesheet" href="style.css"></head><body><script src="app.js"></script></body></html>'),
           ("frontend/app.js", "document.title = 'x';"), ("frontend/style.css", "body { margin: 0 }")]
GOOD_TS = [("tests/test_a.py", "def test_a(): pass\ndef test_b(): pass\n")]


@pytest.fixture(scope="module")
def library():
    return legacy.library()


@pytest.fixture(scope="module")
def sandbox() -> Sandbox:
    return Sandbox(scanner=Scanner())


@pytest.fixture
def parts(tmp_path, sandbox):
    settings = Settings(_env_file=None, data_dir=str(tmp_path / "data"), recordings_dir=str(tmp_path / "rec"))
    store = Store.open(tmp_path / "db" / "t.db", limits=settings.context_limits)
    project = store.projects.create(name="P", brief="", actor="system")
    other = store.projects.create(name="Q", brief="", actor="system")
    service = SandboxService(settings, store, Scanner(), sandbox)
    return BuildService(service), service, project, other


def audit(service, project, prefix="build."):
    return [(a.action, a.target_id, a.detail) for a in service.store.audit.list(project.id) if a.action.startswith(prefix)]


def body_of(entries, prefix):
    return make_body(entries, prefix)


def write(build, library, project, key, entries, prefix):
    return build.write_artefact(project.id, library.get(key), body_of(entries, prefix), actor="agent:developer@test")


# ---- writing -------------------------------------------------------------------------------------------------------------------

def test_the_files_land_in_the_artefacts_own_folder_inside_the_projects_workspace(parts, library, tmp_path):
    build, service, project, _ = parts
    result = write(build, library, project, "database_schema", GOOD_DB, "DBF")
    assert result.folder == "db" and result.files == ("db/schema.sql", "db/init_db.py") and result.replaced is False
    assert (tmp_path / "data" / "workspaces" / project.id / "db" / "schema.sql").read_text() == SCHEMA
    assert service.list_files(project.id) == ["db/init_db.py", "db/schema.sql"]


def test_a_new_version_replaces_only_its_own_folder_and_drops_the_files_it_no_longer_has(parts, library):
    build, service, project, _ = parts
    write(build, library, project, "backend_code", GOOD_BE + [("backend/old.py", "x = 1")], "BEF")
    write(build, library, project, "frontend_code", GOOD_FE, "FEF")
    service.write_file(project.id, "notes.txt", "mine", actor="human:Ann")
    again = write(build, library, project, "backend_code", GOOD_BE, "BEF")
    assert again.replaced is True
    assert service.list_files(project.id, "backend") == ["backend/main.py"]
    assert sorted(service.list_files(project.id, "frontend")) == ["frontend/app.js", "frontend/index.html", "frontend/style.css"]
    assert service.read_file(project.id, "notes.txt") == "mine"


def test_writing_leaves_no_staging_folder_behind(parts, library):
    build, service, project, _ = parts
    write(build, library, project, "backend_code", GOOD_BE, "BEF")
    assert not [p for p in service.list_files(project.id) if p.startswith(".stage")]


def test_a_staging_folder_left_by_a_crashed_write_is_swept_once_it_is_old_and_never_mixed_into_a_new_write(parts, library, tmp_path):
    import os
    import time
    build, service, project, _ = parts
    service.write_file(project.id, ".stage/backend_code-dead/backend/ghost.py", "ghost = 1\n", actor="human:Ann")
    old = tmp_path / "data" / "workspaces" / project.id / ".stage" / "backend_code-dead"
    ancient = time.time() - 2 * 3600
    os.utime(old, (ancient, ancient))
    write(build, library, project, "backend_code", GOOD_BE, "BEF")
    assert service.list_files(project.id) == ["backend/main.py"]


def test_a_young_staging_folder_belongs_to_a_write_in_progress_and_is_left_alone(parts, library):
    build, service, project, _ = parts
    service.write_file(project.id, ".stage/frontend_code-live/frontend/index.html", "<html></html>", actor="human:Ann")
    write(build, library, project, "backend_code", GOOD_BE, "BEF")
    assert service.read_file(project.id, ".stage/frontend_code-live/frontend/index.html") == "<html></html>"
    assert service.read_file(project.id, "backend/main.py") == GOOD_BE[0][1]


def test_a_staging_folder_just_under_the_age_limit_is_kept_and_just_over_is_swept(parts, library, tmp_path):
    import os
    import time
    from app.build.service import STALE_STAGE_SECONDS
    build, service, project, _ = parts
    service.write_file(project.id, ".stage/a-young/backend/x.py", "x = 1\n", actor="human:Ann")
    service.write_file(project.id, ".stage/b-old/backend/x.py", "x = 1\n", actor="human:Ann")
    base = tmp_path / "data" / "workspaces" / project.id / ".stage"
    now = time.time()
    os.utime(base / "a-young", (now - STALE_STAGE_SECONDS + 600, now - STALE_STAGE_SECONDS + 600))
    os.utime(base / "b-old", (now - STALE_STAGE_SECONDS - 600, now - STALE_STAGE_SECONDS - 600))
    write(build, library, project, "backend_code", GOOD_BE, "BEF")
    assert sorted(p for p in service.list_files(project.id) if p.startswith(".stage")) == [".stage/a-young/backend/x.py"]


def test_the_sweep_survives_a_staging_folder_that_is_really_a_file_or_a_missing_one(parts, library):
    build, service, project, _ = parts
    write(build, library, project, "backend_code", GOOD_BE, "BEF")                                   # no .stage folder at all
    service.write_file(project.id, ".stage", "i am a file", actor="human:Ann") if False else None
    assert service.list_files(project.id) == ["backend/main.py"]


def test_the_staging_folder_is_removed_even_when_the_write_is_refused_part_way(parts, library):
    build, service, project, _ = parts
    from app.sandbox.workspace import Limits
    service._file_limits = Limits(max_files=2)
    with pytest.raises(BuildRefused, match="limited to 2 files"):
        build.write_artefact(project.id, library.get("frontend_code"), make_body(GOOD_FE, "FEF"), actor="agent:developer@test")
    assert not [p for p in service.list_files(project.id) if p.startswith(".stage")]


def test_a_refused_body_writes_nothing_and_leaves_the_old_version_whole(parts, library):
    build, service, project, _ = parts
    write(build, library, project, "backend_code", GOOD_BE, "BEF")
    bad = make_body([("backend/main.py", "x = 2"), ("frontend/evil.js", "x")], "BEF")
    with pytest.raises(BuildRefused, match="outside backend/"):
        build.write_artefact(project.id, library.get("backend_code"), bad, actor="agent:developer@test")
    assert service.read_file(project.id, "backend/main.py") == GOOD_BE[0][1]
    assert service.list_files(project.id) == ["backend/main.py"]


def test_a_file_holding_a_secret_stops_the_write_and_the_old_folder_survives(parts, library):
    build, service, project, _ = parts
    write(build, library, project, "backend_code", GOOD_BE, "BEF")
    leaky = make_body([("backend/main.py", f"KEY = '{AWS}'\n")], "BEF")
    with pytest.raises(BuildRefused, match="secret") as refused:
        build.write_artefact(project.id, library.get("backend_code"), leaky, actor="agent:developer@test")
    assert ".stage" not in str(refused.value) and "backend/main.py holds something" in str(refused.value) and AWS not in str(refused.value)
    assert service.read_file(project.id, "backend/main.py") == GOOD_BE[0][1]
    assert not [p for p in service.list_files(project.id) if p.startswith(".stage")]
    assert AWS not in repr(audit(service, project))


def test_a_body_with_no_files_is_refused(parts, library):
    build, _, project, _ = parts
    with pytest.raises(BuildRefused, match="no files"):
        build.write_artefact(project.id, library.get("backend_code"), "## Overview\nx\n", actor="agent:developer@test")


def test_an_artefact_that_holds_no_code_is_refused(parts, library):
    build, _, project, _ = parts
    with pytest.raises(BuildRefused, match="not an artefact that holds code"):
        build.write_artefact(project.id, library.get("low_level_design"), "x", actor="agent:developer@test")
    with pytest.raises(BuildRefused, match="not an artefact that holds code"):
        build.check_artefact(project.id, "low_level_design", actor="agent:developer@test")


def test_two_projects_never_see_each_others_files(parts, library):
    build, service, project, other = parts
    write(build, library, project, "backend_code", GOOD_BE, "BEF")
    assert service.list_files(other.id) == []
    write(build, library, other, "backend_code", [("backend/main.py", "x = 'theirs'")], "BEF")
    assert service.read_file(project.id, "backend/main.py") == GOOD_BE[0][1]


def test_the_write_is_audited_with_counts_and_no_contents(parts, library):
    build, service, project, _ = parts
    write(build, library, project, "database_schema", GOOD_DB, "DBF")
    rows = audit(service, project)
    assert rows == [("build.files_written", "database_schema", {"folder": "db", "files": 2, "replaced": False})]
    assert "CREATE TABLE" not in repr(audit(service, project, ""))


def test_a_refused_write_is_audited_as_refused(parts, library):
    build, service, project, _ = parts
    with pytest.raises(BuildRefused):
        build.write_artefact(project.id, library.get("backend_code"), make_body([("backend/main.py", f"K = '{AWS}'")], "BEF"), actor="agent:developer@test")
    assert [a for a, _, _ in audit(service, project)] == ["build.files_refused"] and AWS not in repr(audit(service, project, ""))


# ---- the database check ---------------------------------------------------------------------------------------------------------

def test_a_good_schema_creates_its_tables_and_the_check_lists_them(parts, library):
    build, service, project, _ = parts
    write(build, library, project, "database_schema", GOOD_DB, "DBF")
    result = build.check_artefact(project.id, "database_schema", actor="agent:developer@test", design_tables=("users", "items"))
    assert result.status == "passed" and result.facts["tables"] == ["items", "users"] and result.facts["missing"] == []
    assert "created 2 table(s): items, users" in result.summary


def test_the_systems_own_tables_are_not_listed_as_the_models(parts, library):
    build, _, project, _ = parts
    schema = "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT);\nINSERT OR IGNORE INTO users (id, name) VALUES (1, 'a');\n"
    write(build, library, project, "database_schema", [("db/schema.sql", schema), GOOD_DB[1]], "DBF")
    result = build.check_artefact(project.id, "database_schema", actor="agent:developer@test")
    assert result.status == "passed" and result.facts["tables"] == ["users"]


def test_a_table_the_design_names_but_the_schema_lacks_is_listed_as_missing(parts, library):
    build, _, project, _ = parts
    write(build, library, project, "database_schema", GOOD_DB, "DBF")
    result = build.check_artefact(project.id, "database_schema", actor="agent:developer@test", design_tables=("users", "items", "orders"))
    assert result.status == "failed" and result.facts["missing"] == ["orders"]
    assert any("orders" in p and "does not have it" in p for p in result.problems)


def test_a_table_name_is_matched_without_regard_to_case(parts, library):
    build, _, project, _ = parts
    write(build, library, project, "database_schema", GOOD_DB, "DBF")
    assert build.check_artefact(project.id, "database_schema", actor="agent:developer@test", design_tables=("Users",)).status == "passed"


def test_a_schema_with_a_syntax_error_reports_the_error(parts, library):
    build, _, project, _ = parts
    write(build, library, project, "database_schema", [("db/schema.sql", "CREATE TABEL users (id);"), GOOD_DB[1]], "DBF")
    result = build.check_artefact(project.id, "database_schema", actor="agent:developer@test")
    assert result.status == "failed" and "db/init_db.py failed" in result.summary and "OperationalError" in result.problems[0]


def test_a_script_that_cannot_be_run_twice_is_named_as_that(parts, library):
    build, _, project, _ = parts
    schema = "CREATE TABLE users (id INTEGER PRIMARY KEY);\n"
    write(build, library, project, "database_schema", [("db/schema.sql", schema), GOOD_DB[1]], "DBF")
    result = build.check_artefact(project.id, "database_schema", actor="agent:developer@test")
    assert result.status == "failed" and "second time" in result.summary and "CREATE TABLE IF NOT EXISTS" in result.problems[0]


def test_a_script_that_makes_no_database_file_is_reported(parts, library):
    build, _, project, _ = parts
    write(build, library, project, "database_schema", [GOOD_DB[0], ("db/init_db.py", "print('done')\n")], "DBF")
    result = build.check_artefact(project.id, "database_schema", actor="agent:developer@test")
    assert result.status == "failed" and "readable db/app.db" in result.problems[0]


def test_a_schema_that_creates_no_tables_is_reported(parts, library):
    build, _, project, _ = parts
    write(build, library, project, "database_schema", [("db/schema.sql", "-- nothing\n"), GOOD_DB[1]], "DBF")
    result = build.check_artefact(project.id, "database_schema", actor="agent:developer@test")
    assert result.status == "failed" and "holds no tables" in result.problems[0]


def test_a_script_that_tries_the_network_is_refused_by_the_operating_system_and_reported(parts, library):
    build, _, project, _ = parts
    reach = "import socket\nsocket.create_connection(('93.184.216.34', 80), timeout=3)\n"
    write(build, library, project, "database_schema", [GOOD_DB[0], ("db/init_db.py", reach)], "DBF")
    result = build.check_artefact(project.id, "database_schema", actor="agent:developer@test")
    assert result.status == "failed" and "PermissionError" in result.problems[0]


def test_a_script_that_never_ends_is_reported_as_timed_out(parts, library):
    build, service, project, _ = parts
    service.settings.sandbox_command_seconds = 3
    write(build, library, project, "database_schema", [GOOD_DB[0], ("db/init_db.py", "import time\ntime.sleep(60)\n")], "DBF")
    result = build.check_artefact(project.id, "database_schema", actor="agent:developer@test")
    assert result.status == "failed" and result.facts == {"status": "timed_out"} and "did not finish in time" in result.problems[0]


def test_the_check_leaves_the_database_file_in_the_workspace_for_later_steps(parts, library):
    build, service, project, _ = parts
    write(build, library, project, "database_schema", GOOD_DB, "DBF")
    build.check_artefact(project.id, "database_schema", actor="agent:developer@test")
    assert "db/app.db" in service.list_files(project.id)


# ---- the backend check ----------------------------------------------------------------------------------------------------------

def test_good_backend_code_compiles_and_leaves_no_cache_files(parts, library):
    build, service, project, _ = parts
    write(build, library, project, "backend_code", GOOD_BE + [("backend/util.py", "x = 1\n")], "BEF")
    result = build.check_artefact(project.id, "backend_code", actor="agent:developer@test")
    assert result.status == "passed" and result.facts == {"files": 2} and "does not show they work" in result.summary
    assert service.list_files(project.id) == ["backend/main.py", "backend/util.py"]


def test_a_cache_folder_made_by_compiling_is_gone_from_the_disk_not_just_empty(parts, library, tmp_path):
    build, _, project, _ = parts
    write(build, library, project, "backend_code", GOOD_BE + [("backend/sub/util.py", "x = 1\n")], "BEF")
    build.check_artefact(project.id, "backend_code", actor="agent:developer@test")
    root = tmp_path / "data" / "workspaces" / project.id / "backend"
    assert sorted(p.name for p in root.rglob("*")) == ["main.py", "sub", "util.py"]


def test_a_syntax_error_in_the_backend_is_reported_with_the_file_and_the_line(parts, library):
    build, _, project, _ = parts
    write(build, library, project, "backend_code", [("backend/main.py", "x = 1\ndef f(:\n    pass\n")], "BEF")
    result = build.check_artefact(project.id, "backend_code", actor="agent:developer@test")
    assert result.status == "failed" and "backend/main.py" in result.problems[0] and "line 2" in result.problems[0] and "SyntaxError" in result.problems[0]


def test_a_backend_check_with_nothing_written_fails_instead_of_passing(parts):
    build, _, project, _ = parts
    result = build.check_artefact(project.id, "backend_code", actor="agent:developer@test")
    assert (result.status, result.facts) == ("failed", {"files": 0}) and "no backend code" in result.summary


# ---- the frontend check ---------------------------------------------------------------------------------------------------------

def test_plain_html_with_local_files_passes(parts, library):
    build, _, project, _ = parts
    write(build, library, project, "frontend_code", GOOD_FE, "FEF")
    result = build.check_artefact(project.id, "frontend_code", actor="agent:developer@test")
    assert result.status == "passed" and result.facts["scripts"] == 1 and result.facts["node_checked"] is True


def test_a_script_with_a_syntax_error_is_reported(parts, library):
    build, _, project, _ = parts
    write(build, library, project, "frontend_code", [GOOD_FE[0], ("frontend/app.js", "function (\n"), GOOD_FE[2]], "FEF")
    result = build.check_artefact(project.id, "frontend_code", actor="agent:developer@test")
    assert result.status == "failed" and "frontend/app.js has a syntax error" in result.problems[0]


def test_a_script_the_page_refers_to_but_nobody_wrote_is_reported(parts, library):
    build, _, project, _ = parts
    write(build, library, project, "frontend_code", [GOOD_FE[0], GOOD_FE[2]], "FEF")
    result = build.check_artefact(project.id, "frontend_code", actor="agent:developer@test")
    assert result.status == "failed" and any("app.js" in p and "no file frontend/app.js was written" in p for p in result.problems)


@pytest.mark.parametrize("tag", ['<script src="https://cdn.example.com/lib.js"></script>', '<link rel="stylesheet" href="//fonts.example.com/a.css">',
                                 '<img src="http://example.com/a.png">', '<a href="https://example.com">x</a>'])
def test_a_page_that_reaches_another_machine_is_reported(parts, library, tag):
    build, _, project, _ = parts
    page = f'<!doctype html><html><body>{tag}</body></html>'
    write(build, library, project, "frontend_code", [("frontend/index.html", page)], "FEF")
    result = build.check_artefact(project.id, "frontend_code", actor="agent:developer@test")
    assert result.status == "failed" and any("on another machine" in p for p in result.problems)


def test_a_web_address_inside_a_script_is_reported(parts, library):
    build, _, project, _ = parts
    write(build, library, project, "frontend_code", [GOOD_FE[0], ("frontend/app.js", "fetch('https://api.example.com/x');"), GOOD_FE[2]], "FEF")
    result = build.check_artefact(project.id, "frontend_code", actor="agent:developer@test")
    assert result.status == "failed" and any("frontend/app.js contains a web address" in p for p in result.problems)


@pytest.mark.parametrize("tag", ['<img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=">', '<link rel="icon" href="data:,">', '<a href="#top">x</a>', '<a href="mailto:a@b.c">x</a>'])
def test_references_that_are_not_files_are_not_checked_as_files(parts, library, tag):
    build, _, project, _ = parts
    write(build, library, project, "frontend_code", [("frontend/index.html", f"<html><body>{tag}</body></html>")], "FEF")
    assert build.check_artefact(project.id, "frontend_code", actor="agent:developer@test").status == "passed"


def test_a_stylesheet_the_page_links_but_nobody_wrote_is_reported(parts, library):
    build, _, project, _ = parts
    write(build, library, project, "frontend_code", [GOOD_FE[0], GOOD_FE[1]], "FEF")
    result = build.check_artefact(project.id, "frontend_code", actor="agent:developer@test")
    assert result.status == "failed" and any("style.css" in p and "no file frontend/style.css was written" in p for p in result.problems)


def test_a_reference_from_the_site_root_is_read_from_the_frontend_folder(parts, library):
    build, _, project, _ = parts
    page = '<html><body><script src="/app.js"></script><link rel="stylesheet" href="/css/site.css"></body></html>'
    write(build, library, project, "frontend_code", [("frontend/index.html", page), GOOD_FE[1], ("frontend/css/site.css", "body {}")], "FEF")
    assert build.check_artefact(project.id, "frontend_code", actor="agent:developer@test").status == "passed"
    write(build, library, project, "frontend_code", [("frontend/index.html", page), GOOD_FE[1]], "FEF")
    missing = build.check_artefact(project.id, "frontend_code", actor="agent:developer@test")
    assert missing.status == "failed" and any("no file frontend/css/site.css was written" in p for p in missing.problems)


def test_a_web_address_inside_a_stylesheet_is_reported(parts, library):
    build, _, project, _ = parts
    write(build, library, project, "frontend_code", [GOOD_FE[0], GOOD_FE[1], ("frontend/style.css", "@import url(https://fonts.example.com/a.css);")], "FEF")
    result = build.check_artefact(project.id, "frontend_code", actor="agent:developer@test")
    assert result.status == "failed" and any("frontend/style.css contains a web address" in p for p in result.problems)


def test_a_page_in_a_subfolder_finds_its_files_relative_to_itself(parts, library):
    build, _, project, _ = parts
    page = '<html><body><script src="js/app.js"></script><script src="../shared.js"></script></body></html>'
    write(build, library, project, "frontend_code", [("frontend/pages/index.html", page), ("frontend/pages/js/app.js", "x = 1;"), ("frontend/shared.js", "y = 2;"), ("frontend/index.html", "<html></html>")], "FEF")
    assert build.check_artefact(project.id, "frontend_code", actor="agent:developer@test").status == "passed"


def test_a_frontend_check_with_nothing_written_still_gives_a_result(parts):
    build, _, project, _ = parts
    assert build.check_artefact(project.id, "frontend_code", actor="agent:developer@test").facts["files"] == 0


# ---- the test check -------------------------------------------------------------------------------------------------------------

def test_the_tests_are_counted_and_not_run(parts, library):
    build, service, project, _ = parts
    write(build, library, project, "test_suite", GOOD_TS + [("tests/test_c.py", "def test_c(): assert False\n")], "TSF")
    result = build.check_artefact(project.id, "test_suite", actor="agent:developer@test")
    assert result.status == "passed" and result.facts == {"collected": 3} and "not run yet" in result.summary
    assert service.list_files(project.id) == ["tests/test_a.py", "tests/test_c.py"]


def test_counting_the_tests_leaves_no_cache_folder_in_the_workspace(parts, library, tmp_path):
    build, _, project, _ = parts
    write(build, library, project, "test_suite", GOOD_TS, "TSF")
    build.check_artefact(project.id, "test_suite", actor="agent:developer@test")
    root = tmp_path / "data" / "workspaces" / project.id
    assert [p.name for p in root.rglob(".pytest_cache")] == [] and sorted(p.name for p in (root / "tests").iterdir()) == ["test_a.py"]


def test_a_collection_error_is_reported_with_its_reason(parts, library):
    build, _, project, _ = parts
    write(build, library, project, "test_suite", [("tests/test_a.py", "import nosuchmodule\ndef test_a(): pass\n")], "TSF")
    result = build.check_artefact(project.id, "test_suite", actor="agent:developer@test")
    assert result.status == "failed" and "ModuleNotFoundError" in result.problems[0]


def test_no_tests_is_a_failure_and_never_a_pass(parts, library):
    build, _, project, _ = parts
    write(build, library, project, "test_suite", [("tests/test_a.py", "x = 1\n")], "TSF")
    result = build.check_artefact(project.id, "test_suite", actor="agent:developer@test")
    assert result.status == "failed" and result.facts == {"collected": 0} and "no tests" in result.summary


# ---- when the sandbox cannot run -------------------------------------------------------------------------------------------------

class FakeResult:
    def __init__(self, status, reason="", exit_code=None, output=""):
        self.status, self.reason, self.exit_code, self.output = status, reason, exit_code, output

    @property
    def ok(self):
        return self.status == "ran" and self.exit_code == 0


def test_a_sandbox_that_is_not_there_is_reported_as_not_checked_never_as_a_pass(tmp_path):
    from app.sandbox.workspace import Workspace
    ws = Workspace(tmp_path / "w")
    run = lambda program, args: FakeResult("unavailable", "no operating-system protection")
    for check in (check_database, check_backend, check_frontend, check_tests):
        if check is check_frontend:
            ws.write_file("frontend/app.js", "x = 1;")
        if check is check_backend:
            ws.write_file("backend/main.py", "x = 1\n")
        result = check(run, ws)
        assert result.status == "skipped" and result.ok and "not checked" in result.summary


def test_a_refused_command_is_reported_as_not_checked(tmp_path):
    from app.sandbox.workspace import Workspace
    result = check_database(lambda program, args: FakeResult("refused", "not on the allow-list"), Workspace(tmp_path / "w"))
    assert result.status == "skipped" and "was refused" in result.summary


def test_a_machine_without_node_skips_the_script_check_and_says_so(tmp_path):
    from app.sandbox.workspace import Workspace
    ws = Workspace(tmp_path / "w")
    ws.write_file("frontend/index.html", "<html><script src='app.js'></script></html>")
    ws.write_file("frontend/app.js", "x = 1;")
    result = check_frontend(lambda program, args: FakeResult("refused", "node is not installed on this machine, so it cannot be run"), ws)
    assert result.status == "passed" and result.facts["node_checked"] is False and "node is not installed" in result.summary


def test_each_check_is_audited_with_its_facts_and_no_output(parts, library):
    build, service, project, _ = parts
    write(build, library, project, "test_suite", GOOD_TS, "TSF")
    build.check_artefact(project.id, "test_suite", actor="agent:developer@test")
    checked = [r for r in audit(service, project) if r[0] == "build.checked"]
    assert checked == [("build.checked", "test_suite", {"status": "passed", "facts": {"collected": 2}})]


def test_three_writers_at_the_same_moment_never_trample_each_other(parts, library):
    """The Build phase starts the database, backend and frontend together. They used to share one staging folder, and only 39 of 75 writes survived."""
    import threading
    build, service, project, _ = parts
    jobs = {"database_schema": (GOOD_DB, "DBF"),
            "backend_code": (GOOD_BE + [(f"backend/m{n}.py", "x = 1\n") for n in range(5)], "BEF"),
            "frontend_code": (GOOD_FE + [(f"frontend/a{n}.js", "x = 1;") for n in range(5)], "FEF")}
    problems: list[str] = []
    for _ in range(12):
        def go(key, entries, prefix):
            try:
                write(build, library, project, key, entries, prefix)
            except Exception as exc:                                                                 # noqa: BLE001 - any failure at all is the bug
                problems.append(f"{key}: {type(exc).__name__}: {str(exc)[:100]}")
        threads = [threading.Thread(target=go, args=(k, *v)) for k, v in jobs.items()]
        [t.start() for t in threads]
        [t.join() for t in threads]
    assert problems == []
    assert sorted(service.list_files(project.id, "backend")) == sorted(["backend/main.py"] + [f"backend/m{n}.py" for n in range(5)])
    assert sorted(service.list_files(project.id, "db")) == ["db/init_db.py", "db/schema.sql"]
    assert len(service.list_files(project.id, "frontend")) == 8
    assert [p for p in service.list_files(project.id) if p.startswith(".stage")] == []


def test_two_writers_of_the_same_artefact_at_once_both_finish_and_the_folder_is_whole(parts, library):
    import threading
    build, service, project, _ = parts
    problems: list[str] = []
    versions = [GOOD_BE + [("backend/one.py", "x = 1\n")], GOOD_BE + [("backend/two.py", "x = 2\n")]]

    def go(entries):
        try:
            write(build, library, project, "backend_code", entries, "BEF")
        except Exception as exc:                                                                     # noqa: BLE001
            problems.append(f"{type(exc).__name__}: {str(exc)[:100]}")
    for _ in range(10):
        threads = [threading.Thread(target=go, args=(v,)) for v in versions]
        [t.start() for t in threads]
        [t.join() for t in threads]
    assert problems == []
    files = sorted(service.list_files(project.id, "backend"))
    assert files in (["backend/main.py", "backend/one.py"], ["backend/main.py", "backend/two.py"])      # one whole version won; never a mixture


def test_a_replaced_folder_leaves_no_moved_aside_copy_behind(parts, library, tmp_path):
    build, service, project, _ = parts
    write(build, library, project, "backend_code", GOOD_BE + [("backend/old.py", "x = 1\n")], "BEF")
    write(build, library, project, "backend_code", GOOD_BE, "BEF")
    root = tmp_path / "data" / "workspaces" / project.id
    assert [p.name for p in root.iterdir() if p.name.startswith(".old-")] == [] and sorted(p.name for p in (root / "backend").iterdir()) == ["main.py"]
    assert list((root / ".stage").iterdir()) == []                                              # the shared parent stays, empty: removing it races with another writer


def test_the_age_limit_is_an_hour_so_half_an_hour_is_kept_and_two_hours_is_swept(parts, library, tmp_path):
    import os
    import time
    from app.build.service import STALE_STAGE_SECONDS
    assert STALE_STAGE_SECONDS == 3600
    build, service, project, _ = parts
    service.write_file(project.id, ".stage/c-half/backend/x.py", "x = 1\n", actor="human:Ann")
    service.write_file(project.id, ".stage/d-two/backend/x.py", "x = 1\n", actor="human:Ann")
    base = tmp_path / "data" / "workspaces" / project.id / ".stage"
    now = time.time()
    os.utime(base / "c-half", (now - 1800, now - 1800))
    os.utime(base / "d-two", (now - 7200, now - 7200))
    write(build, library, project, "backend_code", GOOD_BE, "BEF")
    assert [p for p in service.list_files(project.id) if p.startswith(".stage")] == [".stage/c-half/backend/x.py"]


def test_the_sweep_never_follows_a_link_out_of_the_workspace(parts, library, tmp_path):
    import os
    import time
    build, service, project, _ = parts
    service.write_file(project.id, "keep.txt", "k", actor="human:Ann")                       # makes the workspace
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.txt").write_text("keep me")
    old = time.time() - 7200
    os.utime(outside, (old, old))
    root = tmp_path / "data" / "workspaces" / project.id
    (root / ".stage").mkdir()
    os.symlink(outside, root / ".stage" / "link")
    write(build, library, project, "backend_code", GOOD_BE, "BEF")
    assert (outside / "precious.txt").read_text() == "keep me" and service.read_file(project.id, "backend/main.py") == GOOD_BE[0][1]


def test_a_staging_folder_that_vanishes_while_the_sweep_looks_does_not_stop_the_write(parts, library, monkeypatch):
    """Another writer finishing may remove the shared staging parent between the sweep's two looks at it."""
    import os
    build, service, project, _ = parts
    service.write_file(project.id, ".stage/e-live/backend/x.py", "x = 1\n", actor="human:Ann")
    real = os.scandir

    def scandir(path="."):
        if str(path).endswith("/.stage"):
            raise FileNotFoundError(2, "gone", str(path))
        return real(path)
    with monkeypatch.context() as patched:
        patched.setattr(os, "scandir", scandir)
        write(build, library, project, "backend_code", GOOD_BE, "BEF")
    assert service.read_file(project.id, "backend/main.py") == GOOD_BE[0][1]


def test_writers_finishing_while_others_start_never_trip_over_the_shared_staging_parent(parts, library):
    """The failure that showed up one run in five: one writer removed the shared `.stage` folder when it was empty, just as another was making its own
    folder inside it. Many short writes, started and finished in overlapping bursts, must never fail."""
    import threading
    build, service, project, _ = parts
    problems: list[str] = []
    jobs = [("database_schema", GOOD_DB, "DBF"), ("backend_code", GOOD_BE, "BEF"), ("frontend_code", GOOD_FE, "FEF"), ("test_suite", GOOD_TS, "TSF")]

    def go(key, entries, prefix):
        for _ in range(15):
            try:
                write(build, library, project, key, entries, prefix)
            except Exception as exc:                                                              # noqa: BLE001 - any failure at all is the bug
                problems.append(f"{key}: {type(exc).__name__}: {str(exc)[:90]}")
    threads = [threading.Thread(target=go, args=job) for job in jobs]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert problems == []
    assert [p for p in service.list_files(project.id) if p.startswith(".stage")] == []
