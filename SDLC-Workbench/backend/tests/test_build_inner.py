"""S17b-1: the 17a checks inside the runtime's own repair loop, and the rule that the workspace equals the latest saved version.

A real AgentRuntime, a scripted model and the real sandbox. The upstream artefacts are seeded straight into the store (the hook is what is under test, not the
workflow). No live model is called."""
from __future__ import annotations

import itertools

import pytest

from app.agents.errors import OutputInvalid
from app.agents.runtime import AgentRuntime
from app.agents.skills import SkillLibrary
from app.build.inner import design_tables_for, latest_body, make_extra_check, sync_workspace
from app.build.service import BuildService
from app.guardrails.scan import Scanner
from app.llm.gateway import Gateway
from app.llm.providers.mock import MockProvider
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.sandbox import profile as OS
from app.sandbox.runner import Sandbox
from app.sandbox.service import SandboxService
from app.build import legacy
from app.workflow.engine import WorkflowEngine

from ._build import make_body

pytestmark = [pytest.mark.anyio, pytest.mark.sandbox, pytest.mark.skipif(not OS.sandbox_available(), reason="this machine has no sandbox-exec")]
MODELS = dict(
    ibm_ica_model_id="m-sonnet", ibm_ica_fallback_model_id="m-sonnet", ibm_ica_haiku_model_id="m-haiku",
    ibm_ica_openai_model_id="m-openai", ibm_ica_gemini_model_id="m-gemini",
    ibm_ica_price_input_per_mtok="2", ibm_ica_price_output_per_mtok="10",
)
SCHEMA = "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, text TEXT NOT NULL);\n"
INIT = ("import os, sqlite3\nhere = os.path.dirname(os.path.abspath(__file__))\nc = sqlite3.connect(os.path.join(here, 'app.db'))\n"
        "c.executescript(open(os.path.join(here, 'schema.sql')).read())\nc.commit()\nprint('ok')\n")
GOOD_DB = [("db/schema.sql", SCHEMA), ("db/init_db.py", INIT)]
BAD_DB = [("db/schema.sql", "CREATE TABEL notes (id);"), ("db/init_db.py", INIT)]
GOOD_BE = [("backend/main.py", "from fastapi import FastAPI\napp = FastAPI()\n")]
BAD_BE = [("backend/main.py", "def f(:\n    pass\n")]
LLD = ("## Overview\nx\n## Endpoints\n- API-001 GET /notes lists notes. Derives from: FR-001\n## Tables\n- TBL-001 notes: id, text. Derives from: FR-001\n"
       "## Rules\n- RUL-001 A note has text. Derives from: FR-001\n## Coverage check\nNone\n## Open questions\nNone")


def wrap(entries, prefix):
    return "<artefact>\n" + make_body(entries, prefix).replace("Derives from: TBL-001", "Derives from: TBL-001, API-001") + "\n</artefact>"


def ok(entries, prefix):
    return ProviderResponse(wrap(entries, prefix), Usage(1000, 200), "stop")


@pytest.fixture(scope="module")
def catalogue():
    return legacy.catalogue()


@pytest.fixture
def rig(make_settings, store, project, catalogue):
    def build(**settings):
        cfg = make_settings(**{**MODELS, **settings})
        provider = MockProvider()
        ids = itertools.count(1)

        async def no_sleep(_):
            return None

        gateway = Gateway(cfg, Routing.load(), provider, store, sleep=no_sleep, call_id_factory=lambda: f"call{next(ids)}")
        engine = WorkflowEngine(catalogue, store)
        library = legacy.library(catalogue)
        runtime = AgentRuntime(cfg, store, gateway, catalogue, engine, library)
        engine.open_project(project.id)
        store.phases.ensure(project.id, "build", actor="system")
        store.phases.set_status(project.id, "build", "running", actor="system")
        sandbox_service = SandboxService(cfg, store, Scanner(), Sandbox(scanner=Scanner()))
        build_service = BuildService(sandbox_service)
        seed(store, project.id, library)
        return runtime, provider, library, build_service, sandbox_service

    return build


def seed(store, project_id, library):
    """The upstream artefacts the Build skills read, as plain saved versions."""
    for key in ("low_level_design", "high_level_design", "functional_requirements", "hifi_wireframes", "user_journey"):
        skill = library.get(key)
        body = LLD if key == "low_level_design" else "## Overview\nx\n"
        store.artefacts.create_and_add_version(project_id, artefact_type=key, phase_key=skill.artefact.phase_key, title=skill.artefact.name,
                                               prefix=skill.artefact.id_prefix, body=body, author="human:seed")


async def run_with_check(runtime, build, library, store, project, key, **kw):
    skill = library.get(key)
    check = make_extra_check(build, store, library, project.id, skill, actor=f"agent:{skill.artefact.role}@m")
    return await runtime.run(project.id, key, extra_check=check, **kw)


# ---- the hook itself ------------------------------------------------------------------------------------------------------------------

async def test_with_no_extra_check_the_runtime_behaves_exactly_as_before(rig, store, project):
    runtime, provider, *_ = rig()
    provider.queue("m-haiku", ok(BAD_DB, "DBF"))
    result = await runtime.run(project.id, "database_schema")              # no hook: the bad schema is saved, because only the ordinary checks ran
    assert result.attempts == 1 and result.version == 1


async def test_an_extra_check_that_finds_nothing_changes_nothing(rig, store, project):
    runtime, provider, *_ = rig()
    provider.queue("m-haiku", ok(GOOD_DB, "DBF"))

    async def none(body):
        return []
    result = await runtime.run(project.id, "database_schema", extra_check=none)
    assert result.attempts == 1 and result.version == 1


async def test_an_extra_check_is_not_called_on_a_reply_that_already_has_problems(rig, store, project):
    runtime, provider, *_ = rig()
    provider.queue("m-haiku", ProviderResponse("no artefact tags at all", Usage(10, 10), "stop"), ok(GOOD_DB, "DBF"))
    seen = []

    async def spy(body):
        seen.append(body)
        return []
    result = await runtime.run(project.id, "database_schema", extra_check=spy)
    assert result.attempts == 2 and len(seen) == 1


async def test_the_extras_problems_go_back_to_the_model_in_the_same_conversation(rig, store, project):
    runtime, provider, *_ = rig()
    provider.queue("m-haiku", ok(GOOD_DB, "DBF"), ok(GOOD_DB, "DBF"))
    answers = iter([["the thing is wrong, in a sentence"], []])

    async def extra(body):
        return next(answers)
    result = await runtime.run(project.id, "database_schema", extra_check=extra)
    assert result.attempts == 2
    second = provider.calls[1].request.messages
    assert [m.role for m in second] == ["user", "assistant", "user"] and "the thing is wrong, in a sentence" in second[2].content


async def test_an_extra_check_that_never_passes_ends_as_invalid_with_nothing_saved(rig, store, project):
    runtime, provider, *_ = rig()
    provider.queue("m-haiku", *[ok(GOOD_DB, "DBF")] * 3)

    async def never(body):
        return ["still wrong"]
    with pytest.raises(OutputInvalid, match="still wrong"):
        await runtime.run(project.id, "database_schema", extra_check=never)
    assert store.artefacts.list(project.id, artefact_type="database_schema") == []


async def test_the_extras_problems_are_logged_with_the_saved_version(rig, store, project):
    runtime, provider, *_ = rig()
    provider.queue("m-haiku", ok(GOOD_DB, "DBF"), ok(GOOD_DB, "DBF"))
    answers = iter([["first try failed"], []])

    async def extra(body):
        return next(answers)
    result = await runtime.run(project.id, "database_schema", extra_check=extra)
    generation = store.artefacts.get_version(project.id, result.artefact_id).generation
    assert generation["repairs"] == 1 and generation["repair_reasons"][0]["problems"] == ["first try failed"]


async def test_the_extras_problems_are_limited_like_any_others(rig, store, project):
    runtime, provider, *_ = rig()
    provider.queue("m-haiku", *[ok(GOOD_DB, "DBF")] * 3)

    async def many(body):
        return [f"problem {n}" for n in range(30)]
    with pytest.raises(OutputInvalid) as caught:
        await runtime.run(project.id, "database_schema", extra_check=many)
    assert len(caught.value.problems) == 8


# ---- the 17a checks as that extra ------------------------------------------------------------------------------------------------------

async def test_a_schema_that_fails_is_repaired_in_the_same_conversation_and_only_the_good_one_is_saved(rig, store, project):
    runtime, provider, library, build, service = rig()
    provider.queue("m-haiku", ok(BAD_DB, "DBF"), ok(GOOD_DB, "DBF"))
    result = await run_with_check(runtime, build, library, store, project, "database_schema")
    assert result.attempts == 2 and result.version == 1
    assert "CREATE TABLE IF NOT EXISTS" in store.artefacts.get_version(project.id, result.artefact_id).body
    assert "OperationalError" in provider.calls[1].request.messages[2].content
    assert service.read_file(project.id, "db/schema.sql") == SCHEMA


async def test_a_backend_that_does_not_compile_is_repaired_with_the_file_and_line(rig, store, project):
    runtime, provider, library, build, service = rig()
    provider.queue("m-openai", ok(BAD_BE, "BEF"), ok(GOOD_BE, "BEF"))
    result = await run_with_check(runtime, build, library, store, project, "backend_code")
    assert result.attempts == 2
    assert "backend/main.py" in provider.calls[1].request.messages[2].content and "line 1" in provider.calls[1].request.messages[2].content


async def test_a_table_the_design_names_but_the_schema_lacks_is_sent_back(rig, store, project):
    runtime, provider, library, build, _ = rig()
    other = [("db/schema.sql", "CREATE TABLE IF NOT EXISTS other (id INTEGER PRIMARY KEY);\n"), GOOD_DB[1]]
    provider.queue("m-haiku", ok(other, "DBF"), ok(GOOD_DB, "DBF"))
    result = await run_with_check(runtime, build, library, store, project, "database_schema")
    assert result.attempts == 2 and "notes" in provider.calls[1].request.messages[2].content


async def test_the_design_tables_are_read_from_the_saved_low_level_design(rig, store, project):
    _, _, library, _, _ = rig()
    assert design_tables_for(store, library, project.id) == ("notes",)


async def test_a_secret_in_a_file_is_sent_back_and_never_saved(rig, store, project):
    runtime, provider, library, build, service = rig()
    leaky = [("backend/main.py", "KEY = '" + "AKIA" + "IOSFODNN7EXAMPLE" + "'\n")]
    provider.queue("m-openai", ok(leaky, "BEF"), ok(GOOD_BE, "BEF"))
    result = await run_with_check(runtime, build, library, store, project, "backend_code")
    assert result.attempts == 2
    assert "AKIA" + "IOSFODNN7EXAMPLE" not in store.artefacts.get_version(project.id, result.artefact_id).body


# ---- the workspace equals the latest saved version -----------------------------------------------------------------------------------

async def test_after_a_loop_that_saved_nothing_the_folder_is_removed(rig, store, project):
    runtime, provider, library, build, service = rig()
    provider.queue("m-haiku", *[ok(BAD_DB, "DBF")] * 3)
    with pytest.raises(OutputInvalid):
        await run_with_check(runtime, build, library, store, project, "database_schema")
    assert service.list_files(project.id, "db") != []                       # the failed attempt is lying there until the loop cleans up
    sync_workspace(build, store, library, project.id, actor="system")
    assert service.list_files(project.id) == []


async def test_after_a_failed_new_version_the_folder_holds_the_previous_saved_one(rig, store, project):
    runtime, provider, library, build, service = rig()
    provider.queue("m-haiku", ok(GOOD_DB, "DBF"))
    await run_with_check(runtime, build, library, store, project, "database_schema")
    provider.queue("m-haiku", *[ok(BAD_DB, "DBF")] * 3)
    with pytest.raises(OutputInvalid):
        await run_with_check(runtime, build, library, store, project, "database_schema")
    assert service.read_file(project.id, "db/schema.sql") == "CREATE TABEL notes (id);\n"
    done = sync_workspace(build, store, library, project.id, actor="system")
    assert service.read_file(project.id, "db/schema.sql") == SCHEMA and done["database_schema"] == "written"


async def test_sync_leaves_no_staging_folder_and_other_components_alone(rig, store, project):
    runtime, provider, library, build, service = rig()
    provider.queue("m-haiku", ok(GOOD_DB, "DBF"))
    provider.queue("m-openai", ok(GOOD_BE, "BEF"))
    await run_with_check(runtime, build, library, store, project, "database_schema")
    await run_with_check(runtime, build, library, store, project, "backend_code")
    service.write_file(project.id, "notes.txt", "mine", actor="human:Ann")
    done = sync_workspace(build, store, library, project.id, actor="system")
    assert done == {"database_schema": "written", "backend_code": "written", "frontend_code": "none", "test_suite": "none"}
    assert sorted(service.list_files(project.id)) == ["backend/main.py", "db/init_db.py", "db/schema.sql", "notes.txt"]


async def test_syncing_does_not_add_audit_rows_for_writes(rig, store, project):
    runtime, provider, library, build, service = rig()
    provider.queue("m-haiku", ok(GOOD_DB, "DBF"))
    await run_with_check(runtime, build, library, store, project, "database_schema")
    before = len([a for a in store.audit.list(project.id) if a.action == "build.files_written"])
    sync_workspace(build, store, library, project.id, actor="system")
    assert len([a for a in store.audit.list(project.id) if a.action == "build.files_written"]) == before


async def test_a_test_suite_is_tried_against_the_saved_backend_not_an_unsaved_one(rig, store, project):
    runtime, provider, library, build, service = rig()
    provider.queue("m-openai", ok(GOOD_BE, "BEF"))
    await run_with_check(runtime, build, library, store, project, "backend_code")
    service.write_file(project.id, "backend/main.py", "broken (", actor="human:Ann")          # an unsaved attempt left in the workspace
    good_tests = [("tests/test_a.py", "from backend.main import app\ndef test_a(): assert app is not None\n")]
    provider.queue("m-openai", ok(good_tests, "TSF"))
    result = await run_with_check(runtime, build, library, store, project, "test_suite")
    assert result.attempts == 1 and service.read_file(project.id, "backend/main.py") == GOOD_BE[0][1]


async def test_the_body_of_the_latest_version_is_read_back(rig, store, project):
    runtime, provider, library, build, _ = rig()
    assert latest_body(store, project.id, library.get("database_schema")) is None
    provider.queue("m-haiku", ok(GOOD_DB, "DBF"))
    await run_with_check(runtime, build, library, store, project, "database_schema")
    assert "db/schema.sql" in latest_body(store, project.id, library.get("database_schema"))


async def test_remove_artefact_files_says_whether_there_was_anything(rig, store, project):
    _, _, library, build, service = rig()
    assert build.remove_artefact_files(project.id, "backend_code") is False
    service.write_file(project.id, "backend/main.py", "x = 1\n", actor="human:Ann")
    assert build.remove_artefact_files(project.id, "backend_code") is True and service.list_files(project.id) == []
    from app.build.service import BuildRefused
    with pytest.raises(BuildRefused, match="not an artefact that holds code"):
        build.remove_artefact_files(project.id, "low_level_design")


async def test_an_artefact_that_exists_but_has_no_saved_version_reads_as_nothing_saved(rig, store, project):
    _, _, library, build, service = rig()
    skill = library.get("database_schema")
    store.artefacts.create(project.id, artefact_type=skill.key, phase_key=skill.artefact.phase_key, title=skill.artefact.name, prefix=skill.artefact.id_prefix, actor="system")
    assert latest_body(store, project.id, skill) is None
    service.write_file(project.id, "db/schema.sql", SCHEMA, actor="human:Ann")
    assert sync_workspace(build, store, library, project.id, actor="system")["database_schema"] == "removed" and service.list_files(project.id) == []


async def test_no_saved_design_means_no_tables_are_wanted(rig, store, project, catalogue):
    _, _, library, _, _ = rig()
    fresh = store.projects.create(name="Other", brief="", actor="human:tester")
    assert design_tables_for(store, library, fresh.id) == ()


async def test_a_design_that_names_no_table_wants_no_tables(rig, store, project):
    _, _, library, _, _ = rig()
    skill = library.get("low_level_design")
    store.artefacts.create_and_add_version(project.id, artefact_type=skill.key, phase_key=skill.artefact.phase_key, title="x", prefix="ARC-LLD", body="## Tables\n- TBL-009 The notes table. Derives from: FR-001\n", author="human:seed")
    assert design_tables_for(store, library, project.id) == ()


async def test_sync_says_removed_only_when_there_was_a_folder_and_none_when_there_was_not(rig, store, project):
    _, _, library, build, service = rig()
    service.write_file(project.id, "tests/test_a.py", "def test_a(): pass\n", actor="human:Ann")
    done = sync_workspace(build, store, library, project.id, actor="system")
    assert done == {"database_schema": "none", "backend_code": "none", "frontend_code": "none", "test_suite": "removed"}


async def test_a_saved_version_that_no_longer_passes_the_rules_is_reported_and_does_not_stop_the_others(rig, store, project):
    runtime, provider, library, build, service = rig()
    provider.queue("m-haiku", ok(GOOD_DB, "DBF"))
    await run_with_check(runtime, build, library, store, project, "database_schema")
    skill = library.get("backend_code")                                    # saved by some other route, with a file outside its folder
    store.artefacts.create_and_add_version(project.id, artefact_type=skill.key, phase_key=skill.artefact.phase_key, title=skill.artefact.name,
                                           prefix=skill.artefact.id_prefix, body=make_body([("backend/main.py", "x = 1"), ("db/evil.sql", "x")], "BEF"), author="human:seed")
    done = sync_workspace(build, store, library, project.id, actor="system")
    assert done["backend_code"] == "refused" and done["database_schema"] == "written" and done["test_suite"] == "none"


async def test_a_write_the_sandbox_refuses_is_sent_back_to_the_model(rig, store, project):
    from app.sandbox.workspace import Limits
    runtime, provider, library, build, service = rig()
    service._file_limits = Limits(max_files=1)
    three = [("frontend/index.html", "<html></html>"), ("frontend/a.js", "x = 1;"), ("frontend/b.js", "y = 2;")]
    one = [("frontend/index.html", "<html></html>")]
    provider.queue("m-gemini", ok(three, "FEF"), ok(one, "FEF"))
    result = await run_with_check(runtime, build, library, store, project, "frontend_code")
    assert result.attempts == 2 and "limited to 1 files" in provider.calls[1].request.messages[2].content


async def test_a_sandbox_that_cannot_run_is_not_the_models_fault_so_nothing_is_sent_back(rig, store, project):
    runtime, provider, library, _, service = rig()
    broken = BuildService(SandboxService(service.settings, store, Scanner(), Sandbox(sandbox_exec="/nonexistent/sandbox-exec", scanner=Scanner())))
    provider.queue("m-haiku", ok(BAD_DB, "DBF"))
    result = await run_with_check(runtime, broken, library, store, project, "database_schema")
    assert result.attempts == 1                                            # unchecked, not wrong: the later loop reports it as blocked


async def test_the_check_runs_off_the_event_loop_so_a_slow_command_cannot_freeze_everything(rig, store, project, monkeypatch):
    import threading
    runtime, provider, library, build, _ = rig()
    seen = []
    real = build.check_artefact

    def spy(*args, **kwargs):
        seen.append(threading.get_ident())
        return real(*args, **kwargs)
    monkeypatch.setattr(build, "check_artefact", spy)
    provider.queue("m-haiku", ok(GOOD_DB, "DBF"))
    await run_with_check(runtime, build, library, store, project, "database_schema")
    assert seen and seen[0] != threading.get_ident()


def audit_actions(store, project, prefix="build."):
    return [(a.action, a.detail) for a in store.audit.list(project.id) if a.action.startswith(prefix)]


async def test_a_loud_write_is_audited_once_and_a_quiet_one_not_at_all(rig, store, project):
    _, _, library, build, _ = rig()
    skill = library.get("database_schema")
    build.write_artefact(project.id, skill, make_body(GOOD_DB, "DBF"), actor="system", audit=False)
    assert audit_actions(store, project) == []
    build.write_artefact(project.id, skill, make_body(GOOD_DB, "DBF"), actor="system")
    assert audit_actions(store, project) == [("build.files_written", {"folder": "db", "files": 2, "replaced": True})]


async def test_a_loud_refusal_is_audited_and_a_quiet_one_is_not(rig, store, project):
    from app.build.service import BuildRefused
    from app.sandbox.workspace import Limits
    _, _, library, build, service = rig()
    service._file_limits = Limits(max_files=1)
    skill = library.get("database_schema")
    with pytest.raises(BuildRefused):
        build.write_artefact(project.id, skill, make_body(GOOD_DB, "DBF"), actor="system", audit=False)
    assert audit_actions(store, project) == []
    with pytest.raises(BuildRefused):
        build.write_artefact(project.id, skill, make_body(GOOD_DB, "DBF"), actor="system")
    assert [a for a, _ in audit_actions(store, project)] == ["build.files_refused"]


async def test_trying_a_test_suite_puts_back_only_the_backend_and_never_touches_a_component_still_being_written(rig, store, project):
    """Wave 1 writes the database, backend and frontend together, and the test suite starts the moment the backend is saved. The database and frontend have
    NO saved version yet at that point: putting them 'back' used to delete the folder the database was being tested in."""
    runtime, provider, library, build, service = rig()
    provider.queue("m-openai", ok(GOOD_BE, "BEF"))
    await run_with_check(runtime, build, library, store, project, "backend_code")
    service.write_file(project.id, "db/schema.sql", SCHEMA, actor="human:Ann")                 # the database's attempt, being checked right now: not saved
    service.write_file(project.id, "db/init_db.py", INIT, actor="human:Ann")
    service.write_file(project.id, "frontend/index.html", "<html>being written right now</html>", actor="human:Ann")
    service.write_file(project.id, "backend/main.py", "stale (", actor="human:Ann")
    provider.queue("m-openai", ok([("tests/test_a.py", "from backend.main import app\ndef test_a(): assert app is not None\n")], "TSF"))
    result = await run_with_check(runtime, build, library, store, project, "test_suite")
    assert result.attempts == 1
    assert service.read_file(project.id, "backend/main.py") == GOOD_BE[0][1]                    # the backend IS put back
    assert service.read_file(project.id, "db/schema.sql") == SCHEMA and service.read_file(project.id, "db/init_db.py") == INIT
    assert service.read_file(project.id, "frontend/index.html") == "<html>being written right now</html>"


async def test_sync_limited_to_some_components_leaves_the_others_exactly_as_they_are(rig, store, project):
    runtime, provider, library, build, service = rig()
    provider.queue("m-haiku", ok(GOOD_DB, "DBF"))
    provider.queue("m-openai", ok(GOOD_BE, "BEF"))
    await run_with_check(runtime, build, library, store, project, "database_schema")
    await run_with_check(runtime, build, library, store, project, "backend_code")
    service.write_file(project.id, "db/schema.sql", "stale-db", actor="human:Ann")
    service.write_file(project.id, "backend/main.py", "stale-be", actor="human:Ann")
    assert sync_workspace(build, store, library, project.id, actor="system", keys=("backend_code",)) == {"backend_code": "written"}
    assert service.read_file(project.id, "backend/main.py") == GOOD_BE[0][1] and service.read_file(project.id, "db/schema.sql") == "stale-db"


async def test_sync_with_an_empty_list_of_components_touches_nothing(rig, store, project):
    runtime, provider, library, build, service = rig()
    provider.queue("m-haiku", ok(GOOD_DB, "DBF"))
    await run_with_check(runtime, build, library, store, project, "database_schema")
    service.write_file(project.id, "db/schema.sql", "stale-db", actor="human:Ann")
    assert sync_workspace(build, store, library, project.id, actor="system", keys=()) == {}
    assert service.read_file(project.id, "db/schema.sql") == "stale-db"
