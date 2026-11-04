"""Replay of an agent run, the v4 migration, settings, status, and the two scripts."""
from __future__ import annotations

import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import scripts.agent_demo as demo
import scripts.skills_report as skills_report
from app.agents.runtime import AgentRuntime
from app.agents.skills import SkillLibrary
from app.config import Settings
from app.db import MIGRATIONS, SCHEMA_V1, SCHEMA_V2, SCHEMA_V3, Database, split_statements
from app.llm.gateway import Gateway
from app.llm.providers.ica import IcaProvider
from app.llm.providers.mock import MockProvider
from app.llm.providers.recording import RecordingProvider, ReplayProvider
from app.llm.recordings import RecordingStore
from app.llm.routing import Routing
from app.llm.types import ProviderResponse, Usage
from app.main import create_app
from app.repos import Store
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine

from .test_agent_runtime import CHARTER_SECTIONS, MODELS, ok
from .test_ica_provider import ENDPOINT, KEY, reply as http_reply

pytestmark = pytest.mark.anyio


# ---- replay -------------------------------------------------------------------------------------------

def runtime_over(settings, provider, store):
    routing = Routing.load()
    catalogue = load_catalogue(routing.roles.keys())
    engine = WorkflowEngine(catalogue, store)
    runtime = AgentRuntime(settings, store, Gateway(settings, routing, provider, store), catalogue, engine, SkillLibrary.load(catalogue))
    return runtime, engine


def open_charter_project(store, engine, brief="Staff may book a room for up to four hours at a time."):
    project = store.projects.create(name="Room Booking", brief=brief, actor="system")
    engine.open_project(project.id)
    engine.start(project.id, "setup", actor="system")
    store.context.add_document(project.id, "p.md", b"# Rules\n\nStaff may book a room for up to four hours at a time.", actor="human:a")
    return project


async def test_an_agent_run_recorded_live_replays_identically_with_a_new_project_and_zero_live_calls(make_settings, tmp_path):
    settings = make_settings(**MODELS, replay_set="agents")
    folder = settings.recordings_path

    live_store = Store.open(tmp_path / "live.db", limits=settings.context_limits)
    scripted = MockProvider({"m-sonnet": [ok(CHARTER_SECTIONS, "see [DOC-001#1]", (1200, 300))]})
    runtime, engine = runtime_over(settings, RecordingProvider(scripted, RecordingStore(folder), settings), live_store)
    first = await runtime.run(open_charter_project(live_store, engine).id, "project_charter")
    assert len(scripted.calls) == 1 and len(list(folder.glob("*.json"))) == 1

    class Boom(MockProvider):
        async def complete(self, model_id, request):
            raise AssertionError("the network was used during replay")

    replay_store = Store.open(tmp_path / "replay.db", limits=settings.context_limits)
    replayed_runtime, replay_engine = runtime_over(settings, ReplayProvider(RecordingStore(folder)), replay_store)
    replay_project = open_charter_project(replay_store, replay_engine)  # a different project ID, on purpose
    second = await replayed_runtime.run(replay_project.id, "project_charter", run_id="a-different-run")

    assert (second.tokens_in, second.tokens_out, second.cost_usd, second.citations) == (first.tokens_in, first.tokens_out, first.cost_usd, first.citations)
    assert replay_store.artefacts.get_version(replay_project.id, "SET-CHR-001").body == live_store.artefacts.get_version(live_store.projects.list()[0].id, "SET-CHR-001").body


async def test_changing_the_brief_changes_the_prompt_so_replay_misses_which_is_the_intended_strictness(make_settings, tmp_path):
    settings = make_settings(**MODELS, replay_set="agents2")
    folder = settings.recordings_path
    store = Store.open(tmp_path / "a.db", limits=settings.context_limits)
    scripted = MockProvider({"m-sonnet": [ok(CHARTER_SECTIONS)]})
    runtime, engine = runtime_over(settings, RecordingProvider(scripted, RecordingStore(folder), settings), store)
    await runtime.run(open_charter_project(store, engine).id, "project_charter")

    other = Store.open(tmp_path / "b.db", limits=settings.context_limits)
    replay_runtime, replay_engine = runtime_over(settings, ReplayProvider(RecordingStore(folder)), other)
    changed = open_charter_project(other, replay_engine, brief="A completely different brief about cafeteria menus.")
    from app.llm.errors import LLMCallFailed
    with pytest.raises(LLMCallFailed, match="no recording"):
        await replay_runtime.run(changed.id, "project_charter")
    assert other.artefacts.list(changed.id) == []


async def test_the_prompt_is_identical_across_projects_which_is_what_makes_replay_possible(make_settings, tmp_path):
    settings = make_settings(**MODELS)
    seen = []
    for name in ("one", "two"):
        store = Store.open(tmp_path / f"{name}.db", limits=settings.context_limits)
        provider = MockProvider({"m-sonnet": [ok(CHARTER_SECTIONS)]})
        runtime, engine = runtime_over(settings, provider, store)
        await runtime.run(open_charter_project(store, engine).id, "project_charter")
        request = provider.calls[0].request
        seen.append((request.system, request.messages[0].content, request.max_tokens, request.temperature))
    assert seen[0] == seen[1]


# ---- the real provider, end to end over a fake network ---------------------------------------------------------

async def test_the_runtime_works_through_the_real_ica_provider_over_a_fake_network(make_settings, tmp_path):
    settings = make_settings(**MODELS, ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY)
    body = "\n".join(f"## {s}\nText for {s}." for s in CHARTER_SECTIONS)
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=http_reply(f"<artefact>\n{body}\n</artefact>", usage={"prompt_tokens": 900, "completion_tokens": 300}))

    provider = IcaProvider(settings, transport=httpx.MockTransport(handler))
    store = Store.open(tmp_path / "x.db", limits=settings.context_limits)
    runtime, engine = runtime_over(settings, provider, store)
    result = await runtime.run(open_charter_project(store, engine).id, "project_charter")
    await provider.aclose()
    assert (result.attempts, result.tokens_in, result.tokens_out) == (1, 900, 300)
    import json

    sent = json.loads(requests[0].content)
    assert sent["max_tokens"] == 8000 and "temperature" not in sent  # decision 4: no temperature unless asked for
    assert sent["messages"][0]["role"] == "system" and "<artefact>" in sent["messages"][0]["content"]


async def test_temperature_is_sent_only_when_the_setting_is_given(make_settings, tmp_path):
    settings = make_settings(**MODELS, agent_temperature=0.3)
    store = Store.open(tmp_path / "x.db", limits=settings.context_limits)
    provider = MockProvider({"m-sonnet": [ok(CHARTER_SECTIONS)]})
    runtime, engine = runtime_over(settings, provider, store)
    await runtime.run(open_charter_project(store, engine).id, "project_charter")
    assert provider.calls[0].request.temperature == 0.3
    assert make_settings().agent_temperature is None


# ---- settings -----------------------------------------------------------------------------------------------

def test_agent_setting_defaults_match_the_spec():
    s = Settings(_env_file=None)
    assert (s.agent_max_repairs, s.agent_max_output_tokens, s.agent_upstream_max_chars) == (2, 8000, 100000)      # the upstream limit was 24000 until 2026-10-31, when the Low-level design needed 32,381
    assert (s.agent_context_max_chunks, s.agent_context_max_chars, s.agent_context_min_coverage) == (6, 6000, 0.5)
    assert (s.agent_brief_queries, s.agent_temperature) == (8, None)


@pytest.mark.parametrize("field, bad", [
    ("agent_max_repairs", -1), ("agent_max_repairs", 6), ("agent_max_output_tokens", 10), ("agent_upstream_max_chars", 10),
    ("agent_context_max_chunks", -1), ("agent_context_min_coverage", 1.5), ("agent_context_min_coverage", -0.1),
    ("agent_temperature", 3), ("agent_temperature", -1), ("agent_brief_queries", 21),
])
def test_out_of_range_agent_settings_are_rejected(field, bad):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: bad})


def test_agent_settings_read_from_a_dotenv_file_and_a_blank_temperature_means_unset(tmp_path):
    path = tmp_path / "t.env"
    path.write_text("AGENT_MAX_REPAIRS=1\nAGENT_CONTEXT_MIN_COVERAGE=0.7\nAGENT_TEMPERATURE=\nAGENT_BRIEF_QUERIES=3\n")
    s = Settings(_env_file=path)
    assert (s.agent_max_repairs, s.agent_context_min_coverage, s.agent_temperature, s.agent_brief_queries) == (1, 0.7, None, 3)
    path.write_text("AGENT_TEMPERATURE=0.5\n")
    assert Settings(_env_file=path).agent_temperature == 0.5


# ---- schema v4 ----------------------------------------------------------------------------------------------------

def build_v3(path):
    raw = sqlite3.connect(path)
    for script in (SCHEMA_V1, SCHEMA_V2, SCHEMA_V3):
        for statement in split_statements(script):
            raw.execute(statement)
    raw.execute("PRAGMA user_version = 3")
    raw.execute("INSERT INTO projects (id, name, mode, created_at, updated_at) VALUES ('p1', 'Old', 'replay', 't', 't')")
    raw.execute("INSERT INTO artefacts (project_id, id, type, phase_key, title, created_at) VALUES ('p1', 'REQ-F-001', 't', 'requirements', 'T', 't')")
    raw.execute("INSERT INTO artefact_versions (project_id, artefact_id, number, body, author, created_at) VALUES ('p1', 'REQ-F-001', 1, 'old body', 'human:a', 't')")
    raw.commit()
    raw.close()


def test_a_v3_database_with_data_upgrades_and_old_versions_have_no_generation_record(tmp_path):
    path = tmp_path / "old.db"
    build_v3(path)
    assert Database(path).migrate() == len(MIGRATIONS) >= 4
    version = Store.open(path).artefacts.get_version("p1", "REQ-F-001")
    assert version.body == "old body" and version.generation is None


def test_concurrent_upgrades_of_a_v3_file_all_succeed_and_add_the_column_once(tmp_path):
    path = tmp_path / "race.db"
    build_v3(path)

    def go(_):
        return Database(path).migrate()

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert list(pool.map(go, range(8))) == [len(MIGRATIONS)] * 8
    with Database(path).read() as conn:
        assert [c["name"] for c in conn.execute("PRAGMA table_info(artefact_versions)")].count("generation") == 1


def test_the_immutability_trigger_still_blocks_every_original_column_after_the_upgrade(tmp_path):
    path = tmp_path / "old.db"
    build_v3(path)
    Database(path).migrate()
    for column, value in (("body", "x"), ("author", "human:m"), ("number", 9), ("source_chunks", "[]"), ("created_at", "z"), ("generation", "{}")):
        with pytest.raises(sqlite3.DatabaseError, match="immutable"):
            with Database(path).write() as conn:
                conn.execute(f"UPDATE artefact_versions SET {column} = ?", (value,))


def test_review_findings_can_still_be_attached_after_the_upgrade(tmp_path):
    path = tmp_path / "old.db"
    build_v3(path)
    store = Store.open(path)
    store.artefacts.set_review_findings("p1", "REQ-F-001", 1, {"verdict": "pass"}, actor="system")
    assert store.artefacts.get_version("p1", "REQ-F-001").review_findings == {"verdict": "pass"}


def test_a_generation_record_must_be_json_serialisable(store, project):
    from app.models import InvalidInput

    store.artefacts.create(project.id, artefact_type="x", phase_key="setup", title="x", actor="system", artefact_id="SET-CHR-001")
    with pytest.raises(InvalidInput, match="JSON"):
        store.artefacts.add_version(project.id, "SET-CHR-001", body="b", author="agent:r@m", generation={"x": object()})


# ---- status ---------------------------------------------------------------------------------------------------------

def test_the_skills_status_block_has_counts_and_names_but_no_paths_or_text(make_settings):
    response = TestClient(create_app(make_settings())).get("/api/status")
    block = response.json()["skills"]
    assert block == {"with_skill": 21, "artefacts": 28, "not_enabled": 5, "by_hand": 2, "keys": [       # S13 added the three Design skills (8 before), S14a three Architecture ones, S14b two diagrams; S19a replaced the four code skills with one instruction skill
        "build_instructions", "component_overview", "deployment_plan", "epics_features", "flow_diagram", "functional_requirements", "hifi_wireframes", "high_level_design", "hypercare_plan",
        "low_level_design", "lowfi_wireframes", "non_functional_requirements", "personas", "problem_statement", "project_charter", "release_notes", "runbook", "usecase_diagram", "user_journey", "user_stories",
        "vision_objectives"]}
    assert "/Users" not in response.text and "You are a" not in response.text and ".md" not in response.text


def test_a_broken_skill_file_stops_startup_and_names_the_file(make_settings, tmp_path, monkeypatch):
    import shutil

    import app.agents.skills as skills_module
    from app.agents.skills import SKILLS_DIR, SkillError

    broken = tmp_path / "skills"
    shutil.copytree(SKILLS_DIR, broken)
    text = (broken / "personas.md").read_text()
    (broken / "personas.md").write_text(text.replace("## Never", "## Nevr"))
    monkeypatch.setattr(skills_module, "SKILLS_DIR", broken)
    with pytest.raises(SkillError, match=r"personas.md: line \d+: unknown heading '## Nevr'"):
        create_app(make_settings())


def test_the_app_exposes_a_ready_runtime(make_settings):
    app = create_app(make_settings())
    assert isinstance(app.state.agents, AgentRuntime) and app.state.agents.store is app.state.store


# ---- the scripts ----------------------------------------------------------------------------------------------------

def test_skills_report_lists_every_artefact_and_the_right_counts(capsys):
    assert skills_report.main([]) == 0
    out = capsys.readouterr().out
    assert "21 of 28 artefacts have a skill; 0 required artefacts still need one; 5 not enabled; 2 done by hand" in out         # S21b: the plan and the notes have skills; the verification is a manual checklist (21c) and is still counted here
    def line_for(name: str) -> str:
        return next(l for l in out.splitlines() if f"  {name} " in l).rstrip()

    for name in ("Project charter", "Personas", "Problem statement", "Functional requirements", "Vision and objectives",
                 "Non-functional requirements", "Epics and features", "User stories", "User journey", "Low-fidelity wireframes", "High-fidelity wireframes",
                 "Component overview", "High-level design", "Low-level design", "Flow diagram", "Use-case diagram"):
        assert line_for(name).endswith("  skill"), name
    for name in ("Deployment plan", "Release notes"):
        assert line_for(name).endswith("  skill"), name
    for name in ("Runbook", "Hypercare plan"):
        assert line_for(name).endswith("  skill"), name                    # S22b
    for name in ("Infrastructure as code", "CI/CD pipeline", "Support guide", "SLOs and alerts", "Knowledge-transfer pack"):
        assert line_for(name).endswith("not enabled"), name              # switched off, so not "waiting for a skill"
    for name in ("Deployment verification", "Handover sign-off"):
        assert line_for(name).endswith("by hand"), name                  # done by a person: not waiting for a skill, and not switched off
    assert out.count("no skill yet") == 0 and out.count("not enabled") == 6 and out.count("by hand") == 3          # the summary line says "not enabled" and "by hand" once more each; 28 artefacts: 21 with a skill, 5 switched off, 2 by hand


def test_the_offline_demo_runs_the_chain_catches_the_invented_citation_and_says_it_is_scripted(capsys):
    assert demo.main([]) == 0
    out = capsys.readouterr().out
    assert "SCRIPTED FAKE MODEL" in out.splitlines()[0] and "NOT how a real model writes" in out
    assert "4/4 artefacts saved, 1 invented citation caught and repaired" in out
    assert out.count("1 attempt(s)") == 3 and out.count("2 attempt(s)") == 1
    for artefact in ("SET-CHR-001", "REQ-PRB-001", "REQ-PER-001", "REQ-F-001"):
        assert artefact in out


def test_the_offline_demo_exits_one_if_the_citation_check_does_not_fire(monkeypatch, capsys):
    import app.agents.reply as reply_module

    monkeypatch.setattr(reply_module, "unknown_citations", lambda body, allowed: [])
    assert demo.main([]) == 1
    out = capsys.readouterr().out
    assert "NOT caught" in out and "because the check did not fire" in out


def test_the_offline_demo_needs_no_credentials_uses_a_temp_database_and_cleans_up(make_settings, monkeypatch, capsys):
    import tempfile
    from pathlib import Path

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


def test_live_mode_refuses_without_credentials_and_says_which_and_makes_no_call(make_settings, capsys, monkeypatch):
    called = []
    monkeypatch.setattr(demo, "run_live", lambda *a, **k: called.append(1))
    assert demo.main(["--live"], settings=make_settings(**MODELS)) == 2
    err = capsys.readouterr().err
    assert "IBM_ICA_ENDPOINT" in err and "IBM_ICA_API_KEY" in err and called == []
    assert demo.main(["--live"], settings=make_settings(**MODELS, ibm_ica_endpoint=ENDPOINT)) == 2
    assert "IBM_ICA_API_KEY" in capsys.readouterr().err


def test_live_mode_runs_one_artefact_through_the_provider_and_never_prints_a_credential(make_settings, capsys, monkeypatch):
    body = "\n".join(f"## {s}\nText for {s}." for s in CHARTER_SECTIONS)
    user_agent = "UA-secret-1234"
    cfg = make_settings(**MODELS, ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY, ibm_ica_user_agent=user_agent)
    real_init = IcaProvider.__init__
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=http_reply(f"<artefact>\n{body}\n</artefact>"))

    monkeypatch.setattr(IcaProvider, "__init__", lambda self, settings, *, transport=None: real_init(self, settings, transport=httpx.MockTransport(handler)))
    assert demo.main(["--live"], settings=cfg) == 0
    out = capsys.readouterr()
    assert len(calls) == 1 and "REAL MODEL via IBM ICA" in out.out and "## Purpose" in out.out and "attempts = 1" in out.out
    for secret in (KEY, ENDPOINT, user_agent):
        assert secret not in out.out and secret not in out.err


def test_a_failed_live_run_reports_the_reason_and_exits_one_without_a_traceback(make_settings, capsys, monkeypatch):
    cfg = make_settings(**MODELS, ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY)
    real_init = IcaProvider.__init__
    monkeypatch.setattr(IcaProvider, "__init__", lambda self, settings, *, transport=None: real_init(
        self, settings, transport=httpx.MockTransport(lambda r: httpx.Response(401, json={"error": {"message": f"bad key {KEY}"}}))))
    assert demo.main(["--live"], settings=cfg) == 1
    err = capsys.readouterr().err
    assert "The real-model run failed" in err and KEY not in err and "Traceback" not in err


# ---- the requirements demo (S11) -------------------------------------------------------------------------------------------

import scripts.requirements_demo as req_demo  # noqa: E402


def test_the_offline_requirements_demo_runs_the_phase_catches_the_gap_and_says_it_is_scripted(capsys):
    assert req_demo.main([]) == 0
    out = capsys.readouterr().out
    assert "SCRIPTED FAKE MODEL" in out.splitlines()[0] and "NOT how a real model writes" in out
    assert "8/8 artefacts saved, 14 items, 24 links" in out and "1 coverage gap caught and repaired" in out
    assert out.count("1 attempt(s)") == 7 and out.count("2 attempt(s)") == 1
    for artefact in ("SET-CHR-001", "REQ-PER-001", "REQ-PRB-001", "REQ-VIS-001", "REQ-F-001", "REQ-NF-001", "REQ-EPC-001", "REQ-US-001"):
        assert artefact in out
    assert "backlog_splitter@demo-haiku" in out


def test_the_offline_requirements_demo_exits_one_if_the_coverage_check_does_not_fire(monkeypatch, capsys):
    import app.agents.checks as checks_module

    monkeypatch.setattr(checks_module, "check_items", lambda body, context: [])
    assert req_demo.main([]) == 1
    out = capsys.readouterr().out
    assert "NOT caught" in out and "because the coverage check did not fire" in out


def test_the_requirements_demo_refuses_live_without_credentials_and_names_which(make_settings, capsys):
    assert req_demo.main(["--live"], settings=make_settings(**MODELS)) == 2
    err = capsys.readouterr().err
    assert "IBM_ICA_ENDPOINT" in err and "IBM_ICA_API_KEY" in err


@pytest.mark.parametrize("argv", [["--record", "x"], ["--live", "--replay", "x"], ["--live", "--record", "../up"], ["--replay", "a b"]])
def test_the_requirements_demo_rejects_bad_flag_combinations(argv):
    with pytest.raises(SystemExit) as caught:
        req_demo.main(argv)
    assert caught.value.code == 2


def test_replaying_a_set_that_does_not_exist_fails_plainly_without_a_traceback(make_settings, capsys):
    assert req_demo.main(["--replay", "nothing-here"], settings=make_settings(**MODELS)) == 1
    err = capsys.readouterr().err
    assert "The replay run failed" in err and "no recording" in err and "Traceback" not in err


def test_a_live_requirements_run_records_then_replays_with_zero_live_calls(make_settings, capsys, monkeypatch):
    body = lambda sections, items=None: reply_text(sections, items)  # noqa: E731
    cfg = make_settings(**MODELS, ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY)
    real_init = IcaProvider.__init__
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        calls.append(request)
        task = json.loads(request.content)["messages"][1]["content"]
        text = scripted_reply_for(task)
        return httpx.Response(200, json=http_reply(text, usage={"prompt_tokens": 900, "completion_tokens": 300}))

    monkeypatch.setattr(IcaProvider, "__init__", lambda self, settings, *, transport=None: real_init(self, settings, transport=httpx.MockTransport(handler)))
    assert req_demo.main(["--live", "--record", "phase-t"], settings=cfg) == 0
    live_out = capsys.readouterr()
    assert len(calls) >= 8 and "REAL MODELS via IBM ICA" in live_out.out and "recording to 'phase-t'" in live_out.out
    for secret in (KEY, ENDPOINT):
        assert secret not in live_out.out and secret not in live_out.err
    made = len(calls)

    assert req_demo.main(["--replay", "phase-t"], settings=cfg) == 0
    replayed = capsys.readouterr().out
    assert len(calls) == made and "REPLAY of recording 'phase-t' (no network)" in replayed
    assert "8/8 artefacts saved" in replayed and "Functional requirements (REQ-F-001)" in replayed


def reply_text(sections, items=None):
    items = items or {}
    body = "\n".join(f"## {n}\n{items[n] if n in items else f'Text for {n}.'}" for n in sections)
    return f"<artefact>\n{body}\n</artefact>"


def scripted_reply_for(task: str) -> str:
    """Answer each artefact the runtime asks for, by the artefact named in the task line, with a valid reply."""
    import re as _re

    key = _re.search(r'\((\w+)\) for the project', task).group(1)
    return {
        "project_charter": reply_text(["Purpose", "Scope", "Out of scope", "Stakeholders", "Success measures", "Constraints and assumptions", "Open questions"]),
        "personas": reply_text(["Overview", "Personas", "How the personas differ", "Open questions"], {"Personas": "- PER-001 Staff. Derives from: SET-CHR-001"}),
        "problem_statement": reply_text(["The problem", "Who is affected", "Impact today", "Why it matters now", "Evidence and assumptions"]),
        "vision_objectives": reply_text(["Vision", "Objectives", "Measures", "Out of vision", "Open questions"], {"Objectives": "- OBJ-001 No clashes. Derives from: REQ-PRB-001"}),
        "functional_requirements": reply_text(["Overview", "Requirements", "Business rules", "Traceability notes", "Open questions"],
                                              {"Requirements": "- FR-001 The system shall refuse a clash, for PER-001. Derives from: PER-001, REQ-PRB-001"}),
        "non_functional_requirements": reply_text(["Overview", "Requirements", "Quality targets", "Open questions"], {"Requirements": "- NFR-001 Usable in office hours. Derives from: SET-CHR-001"}),
        "epics_features": reply_text(["Overview", "Epics", "Features", "Coverage check"], {
            "Epics": "- EPIC-001 Book. Derives from: PER-001", "Features": "- FEAT-001 Reserve. Derives from: EPIC-001, FR-001, NFR-001", "Coverage check": "None."}),
        "user_stories": reply_text(["Overview", "Stories", "Coverage check", "Open questions"], {"Stories": "- US-001 As staff, I want a room. Derives from: FEAT-001, PER-001", "Coverage check": "None."}),
    }[key]


def test_the_review_status_block_names_the_reviewer_and_shows_the_rubric_loaded_without_text_or_paths(make_settings):
    response = TestClient(create_app(make_settings())).get("/api/status")
    block = response.json()["review"]
    assert block == {"reviewer": "sonnet", "alternatives": ["gemini", "openai", "haiku"], "rubric_loaded": True}
    assert "/Users" not in response.text and "Review rubric" not in response.text and "rubric.md" not in response.text


def test_the_app_exposes_a_ready_review_service_and_human_actions(make_settings):
    from app.review.human import HumanActions
    from app.review.service import ReviewService

    app = create_app(make_settings())
    assert isinstance(app.state.reviews, ReviewService) and isinstance(app.state.human, HumanActions)
    assert app.state.reviews.store is app.state.store and app.state.human.reviews is app.state.reviews


def test_a_broken_rubric_stops_startup_and_names_the_file(make_settings, monkeypatch, tmp_path):
    import app.main as main_module
    from app.review.prompt import RubricError, load_rubric

    broken = tmp_path / "rubric.md"
    broken.write_text("# Review rubric\n## Purpose\nx\n")
    monkeypatch.setattr(main_module, "load_rubric", lambda: load_rubric(broken))
    with pytest.raises(RubricError, match=r"rubric.md: headings must be exactly"):
        create_app(make_settings())


# ---- the review demo (S08) -------------------------------------------------------------------------------------------------

import scripts.review_demo as review_demo  # noqa: E402


def test_the_offline_review_demo_shows_every_behaviour_and_says_it_is_scripted(capsys):
    assert review_demo.main([]) == 0
    out = capsys.readouterr().out
    assert "SCRIPTED FAKE MODEL" in out.splitlines()[0] and "NOT how a real reviewer reads" in out
    assert "same_family (author anthropic, reviewer anthropic)" in out and "independent (author openai, reviewer anthropic)" in out
    assert "you are offered: gemini (independent), openai (independent), haiku" in out and "nothing switched" in out
    assert "only REQ-PER-001 rewritten (now v2)" in out and "flagged but NOT re-run: REQ-F-001" in out
    assert "PER-002>derives>SET-CHR-001" in out and "refused with 3 reason(s), nothing saved" in out
    assert "saved as v3 by human:demo; v2 kept" in out and "'stale'" in out and "both refused" in out
    assert out.rstrip().endswith("everything behaved as specified")


def test_the_offline_review_demo_exits_one_if_a_behaviour_is_missing(monkeypatch, capsys):
    from app.review.human import HumanActions

    monkeypatch.setattr(HumanActions, "approve", lambda self, *a, **k: None)   # approval no longer checks who is asking
    assert review_demo.main([]) == 1
    out = capsys.readouterr().out
    assert "was allowed to approve" in out and "SOMETHING DID NOT BEHAVE AS SPECIFIED" in out


def test_the_offline_review_demo_needs_no_credentials_and_cleans_up(make_settings, monkeypatch, capsys):
    import tempfile
    from pathlib import Path

    for name in ("IBM_ICA_API_KEY", "IBM_ICA_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)
    made = []
    real = tempfile.TemporaryDirectory

    def tracking(*a, **k):
        d = real(*a, **k)
        made.append(Path(d.name))
        return d

    monkeypatch.setattr(review_demo.tempfile, "TemporaryDirectory", tracking)
    cfg = make_settings()
    assert review_demo.main([]) == 0
    capsys.readouterr()
    assert made and not any(p.exists() for p in made) and not cfg.db_path.exists()


def test_the_live_review_demo_refuses_without_credentials_and_names_which(make_settings, capsys):
    assert review_demo.main(["--live"], settings=make_settings(**MODELS)) == 2
    err = capsys.readouterr().err
    assert "IBM_ICA_ENDPOINT" in err and "IBM_ICA_API_KEY" in err


@pytest.mark.parametrize("argv", [["--second", "openai"], ["--live", "--second", "sonnet"], ["--live", "--second", "bogus"]])
def test_the_review_demo_rejects_bad_flags(argv):
    with pytest.raises(SystemExit) as caught:
        review_demo.main(argv)
    assert caught.value.code == 2


def _live_handler(calls, review_text):
    import json

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        payload = json.loads(request.content)
        task = payload["messages"][1]["content"]
        if "Review the artefact" in task:
            text = review_text
        else:
            text = scripted_reply_for(task)
        return httpx.Response(200, json=http_reply(text, usage={"prompt_tokens": 900, "completion_tokens": 300}))

    return handler


def test_a_live_review_run_writes_reviews_and_prints_findings_labels_and_no_secret(make_settings, capsys, monkeypatch):
    cfg = make_settings(**MODELS, ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY, ibm_ica_user_agent="UA-secret-1234")
    real_init = IcaProvider.__init__
    calls = []
    review_text = "<review>\nSummary: One problem.\n- [MEDIUM] Purpose: vague. Fix: sharpen it.\n</review>"
    monkeypatch.setattr(IcaProvider, "__init__", lambda self, settings, *, transport=None: real_init(self, settings, transport=httpx.MockTransport(_live_handler(calls, review_text))))
    assert review_demo.main(["--live"], settings=cfg) == 0
    out = capsys.readouterr()
    assert len(calls) == 2 and "REAL MODELS via IBM ICA" in out.out and "- [MEDIUM] Purpose: vague. Fix: sharpen it." in out.out
    assert "verdict: ok" in out.out and "same_family" in out.out
    for secret in (KEY, ENDPOINT, "UA-secret-1234"):
        assert secret not in out.out and secret not in out.err


def test_a_live_run_with_a_second_family_shows_both_labels(make_settings, capsys, monkeypatch):
    cfg = make_settings(**MODELS, ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY)
    real_init = IcaProvider.__init__
    calls = []
    review_text = "<review>\nSummary: Fine.\n</review>"
    monkeypatch.setattr(IcaProvider, "__init__", lambda self, settings, *, transport=None: real_init(self, settings, transport=httpx.MockTransport(_live_handler(calls, review_text))))
    assert review_demo.main(["--live", "--second", "gemini"], settings=cfg) == 0
    out = capsys.readouterr().out
    assert len(calls) == 3 and "Reviewed by the Sonnet slot" in out and "Reviewed again by the gemini slot" in out
    assert "same_family" in out and "independent (author anthropic, reviewer google)" in out


def test_a_live_run_where_the_reviewer_cannot_run_offers_the_choice_and_exits_one_without_a_traceback(make_settings, capsys, monkeypatch):
    cfg = make_settings(**MODELS, ibm_ica_endpoint=ENDPOINT, ibm_ica_api_key=KEY)
    real_init = IcaProvider.__init__

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        task = json.loads(request.content)["messages"][1]["content"]
        if "Review the artefact" in task:
            return httpx.Response(503, json={"error": {"message": "overloaded"}})
        return httpx.Response(200, json=http_reply(scripted_reply_for(task)))

    monkeypatch.setattr(IcaProvider, "__init__", lambda self, settings, *, transport=None: real_init(self, settings, transport=httpx.MockTransport(handler)))
    assert review_demo.main(["--live"], settings=cfg) == 1
    err = capsys.readouterr().err
    assert "reviewer slot 'sonnet' could not run" in err and "Nothing was switched" in err and "gemini" in err and "Traceback" not in err


# ---- the guardrails demo (S10) --------------------------------------------------------------------------------------------------

import scripts.guardrails_demo as guardrails_demo  # noqa: E402


def test_the_offline_guardrails_demo_shows_every_behaviour_without_printing_a_value(capsys):
    from . import _fakes as F

    assert guardrails_demo.main([]) == 0
    out = capsys.readouterr().out
    assert "PLANTED FAKES" in out.splitlines()[0] and "everything behaved as specified" in out
    for rule in ("private_key", "aws_key_id", "github_token", "jwt", "url_password", "credential_assignment", "email", "phone", "payment_card", "iban", "configured_credential"):
        assert rule in out
    assert "refused, nothing saved (github_token)" in out and "saved as v2, flagged (email on line" in out and "{'REQ-PER-001': {'email': 1}}" in out
    for value in (F.AWS_KEY, F.GITHUB_TOKEN, F.JWT, F.EMAIL, F.CARD, F.IBAN, F.PHONE_INTL, F.PRIVATE_KEY, F.URL_WITH_PASSWORD):
        assert value not in out


def test_the_offline_guardrails_demo_exits_one_if_the_scanner_stops_working(monkeypatch, capsys):
    from app.guardrails.scan import Scanner

    monkeypatch.setattr(Scanner, "scan", lambda self, text, *, only=None: [])
    assert guardrails_demo.main([]) == 1
    assert "SOMETHING DID NOT BEHAVE AS SPECIFIED" in capsys.readouterr().out


def test_scanning_recordings_prints_counts_only_and_exits_zero_when_clean(make_settings, capsys):
    import json

    cfg = make_settings(replay_set="g1")
    folder = cfg.recordings_path
    folder.mkdir(parents=True)
    body = "<artefact>\n## Overview\nAll fine here.\n</artefact>"
    (folder / "a.json").write_text(json.dumps({"request": {"messages": [{"role": "user", "content": 'Write the artefact "Personas" (personas) for the project'}]},
                                               "response": {"text": body}}))
    assert guardrails_demo.main(["--recordings", "g1"], settings=cfg) == 0
    out = capsys.readouterr().out
    assert "Scanned 1 recorded reply(ies)" in out and "Findings: 0" in out and "Nothing found" in out


def test_scanning_recordings_reports_file_artefact_rule_and_line_but_never_the_value_and_exits_one(make_settings, capsys):
    import json

    from . import _fakes as F

    cfg = make_settings(replay_set="g2")
    folder = cfg.recordings_path
    folder.mkdir(parents=True)
    body = f"<artefact>\n## Overview\nline\nreach {F.EMAIL} and key {F.AWS_KEY}\n</artefact>"
    (folder / "b.json").write_text(json.dumps({"request": {"messages": [{"role": "user", "content": 'Write the artefact "Personas" (personas) for the project'}]},
                                               "response": {"text": body}}))
    assert guardrails_demo.main(["--recordings", "g2"], settings=cfg) == 1
    out = capsys.readouterr().out
    assert "b.json (Personas): email [personal] line 3 under 'Overview'" in out and "aws_key_id [secret]" in out and "Findings: 2" in out
    assert F.EMAIL not in out and F.AWS_KEY not in out and "Do not close the step yet" in out


def test_scanning_a_set_that_does_not_exist_says_so_and_exits_two(make_settings, capsys):
    assert guardrails_demo.main(["--recordings", "nothing-here"], settings=make_settings()) == 2
    assert "No recordings found for 'nothing-here'" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["../up", "a b", "x" * 65, ""])
def test_a_bad_recording_name_is_refused(name):
    with pytest.raises(SystemExit) as caught:
        guardrails_demo.main(["--recordings", name])
    assert caught.value.code == 2
