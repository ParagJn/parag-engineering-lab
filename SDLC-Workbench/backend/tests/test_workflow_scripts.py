from __future__ import annotations

import pytest

import scripts.render_catalogue as render_catalogue
import scripts.workflow_walkthrough as walkthrough
from app.llm.routing import Routing
from app.workflow.definitions import load_catalogue


# ---- the walkthrough ----------------------------------------------------------------------

def test_the_walkthrough_approves_all_seven_phases_and_gets_every_refusal(capsys):
    code = walkthrough.main([])
    out = capsys.readouterr().out
    assert code == 0
    assert "7/7 phases approved, 3/3 refusals correct" in out
    for phase in ("Setup", "Requirements", "Design", "Architecture", "Build & Test", "Deploy", "BAU handover"):
        assert phase in out
    assert out.count("REFUSED") == 3 and "ALLOWED" not in out


def test_the_walkthrough_prints_the_real_refusal_messages(capsys):
    walkthrough.main([])
    out = capsys.readouterr().out
    assert "Requirements cannot start yet: Setup is 'not_started' and must be approved first" in out
    assert "cannot go from 'not_started' to 'approved'" in out
    assert "required artefact(s) with no content yet: Project charter" in out


def test_the_walkthrough_shows_the_parallel_waves(capsys):
    walkthrough.main([])
    out = capsys.readouterr().out
    assert "personas+problem_statement | vision_objectives+functional_requirements+non_functional_requirements" in out


def test_the_walkthrough_uses_a_temporary_database_and_never_touches_the_real_one(make_settings, capsys):
    cfg = make_settings()
    walkthrough.main([])
    capsys.readouterr()
    assert not cfg.db_path.exists()


def test_the_walkthrough_removes_its_temporary_folder(capsys, monkeypatch):
    import tempfile
    from pathlib import Path

    made: list[Path] = []
    real = tempfile.TemporaryDirectory

    def tracking(*a, **k):
        d = real(*a, **k)
        made.append(Path(d.name))
        return d

    monkeypatch.setattr(walkthrough.tempfile, "TemporaryDirectory", tracking)
    walkthrough.main([])
    capsys.readouterr()
    assert made and not any(p.exists() for p in made)


def test_the_walkthrough_needs_no_credentials_or_env_file(monkeypatch, capsys):
    for name in ("IBM_ICA_API_KEY", "IBM_ICA_ENDPOINT", "IBM_ICA_OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert walkthrough.main([]) == 0
    capsys.readouterr()


def test_the_walkthrough_exits_one_if_a_rule_lets_something_through(capsys, monkeypatch):
    import app.workflow.gates as gates

    monkeypatch.setattr(gates, "check_can_start", lambda plan, rows, key: None)  # remove the prerequisite rule
    import app.workflow.engine as engine_module

    monkeypatch.setattr(engine_module, "check_can_start", lambda plan, rows, key: None)
    assert walkthrough.main([]) == 1
    out = capsys.readouterr().out
    assert "ALLOWED" in out and "2/3 refusals correct" in out


def test_render_rows_aligns_columns():
    text = walkthrough.render_rows([walkthrough.Row("A", "approved", "1 required of 1", "x", "next")])
    first, rule, row = text.splitlines()
    assert first.startswith("phase") and set(rule) <= {"-", " "} and row.startswith("A")


# ---- the catalogue document ----------------------------------------------------------------------

def test_the_catalogue_document_matches_the_yaml_exactly():
    """If this fails, a phase file was edited without running: python -m scripts.render_catalogue"""
    assert render_catalogue.DOC_PATH.read_text(encoding="utf-8") == render_catalogue.build()


def test_the_check_flag_reports_a_stale_document(tmp_path, monkeypatch, capsys):
    stale = tmp_path / "08.md"
    stale.write_text("out of date")
    monkeypatch.setattr(render_catalogue, "DOC_PATH", stale)
    assert render_catalogue.main(["--check"]) == 1
    assert "out of date" in capsys.readouterr().err
    assert stale.read_text() == "out of date"  # --check never writes

    assert render_catalogue.main([]) == 0
    assert stale.read_text(encoding="utf-8") == render_catalogue.build()
    assert render_catalogue.main(["--check"]) == 0


def test_the_check_flag_reports_a_missing_document(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(render_catalogue, "DOC_PATH", tmp_path / "missing.md")
    assert render_catalogue.main(["--check"]) == 1
    capsys.readouterr()


def test_the_document_lists_every_artefact_with_its_role_prefix_and_wave():
    text = render_catalogue.build()
    catalogue = load_catalogue(Routing.load().roles.keys())
    for phase in catalogue.phases:
        assert f"## {phase.order} · {phase.name}" in text
        for item in phase.artefacts:
            assert item.name in text and item.id_prefix in text and item.role in text, item.key
    assert "7 phases and 28 artefacts, 18 of them required" in text


def test_a_changed_definition_changes_the_document(tmp_path, monkeypatch):
    import shutil

    import app.workflow.definitions as definitions

    copy = tmp_path / "definitions"
    shutil.copytree(definitions.DEFINITIONS_DIR, copy)
    path = copy / "02-design.yaml"
    path.write_text(path.read_text().replace("name: User journey", "name: Journey map", 1))
    changed = render_catalogue.render(load_catalogue(Routing.load().roles.keys(), copy))
    assert "Journey map" in changed and "Journey map" not in render_catalogue.build()


def test_pipes_in_text_cannot_break_the_table():
    assert render_catalogue._row(["a|b", "c"]) == "| a\\|b | c |"
