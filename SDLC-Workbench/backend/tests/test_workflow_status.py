from __future__ import annotations

import shutil

import pytest
from fastapi.testclient import TestClient

import app.workflow.definitions as definitions
from app.main import create_app
from app.workflow.definitions import DEFINITIONS_DIR, CatalogueError
from app.workflow.engine import WorkflowEngine


def block(make_settings) -> dict:
    response = TestClient(create_app(make_settings())).get("/api/status")
    return response.json()["workflow"], response.text


def test_the_workflow_block_has_the_counts_and_one_row_per_phase(make_settings):
    wf, _ = block(make_settings)
    assert (wf["phase_count"], wf["artefact_count"], wf["required_count"]) == (7, 33, 21)
    assert [p["key"] for p in wf["phases"]] == ["setup", "requirements", "design", "architecture", "build", "deploy", "handover"]
    assert all(set(p) == {"key", "order", "name", "approver", "artefacts", "required"} for p in wf["phases"])
    build = next(p for p in wf["phases"] if p["key"] == "build")
    assert (build["name"], build["artefacts"], build["required"], build["approver"]) == ("Build & Test", 6, 4, "technical lead")
    assert sum(p["artefacts"] for p in wf["phases"]) == wf["artefact_count"]
    assert sum(p["required"] for p in wf["phases"]) == wf["required_count"]


def test_the_workflow_block_leaks_no_paths_or_descriptions(make_settings):
    _, text = block(make_settings)
    assert "definitions" not in text and ".yaml" not in text and "/Users" not in text


def test_the_app_exposes_a_ready_engine(make_settings):
    app = create_app(make_settings())
    assert isinstance(app.state.engine, WorkflowEngine) and app.state.engine.store is app.state.store


def test_a_broken_definition_stops_startup_and_names_the_file(make_settings, tmp_path, monkeypatch):
    broken = tmp_path / "definitions"
    shutil.copytree(DEFINITIONS_DIR, broken)
    text = (broken / "02-design.yaml").read_text()
    (broken / "02-design.yaml").write_text(text.replace("role: ux_designer", "role: nobody", 1))
    monkeypatch.setattr(definitions, "DEFINITIONS_DIR", broken)
    with pytest.raises(CatalogueError, match="02-design.yaml.*'nobody'.*routing.yaml"):
        create_app(make_settings())


def test_a_typo_in_a_definition_is_not_silently_ignored(make_settings, tmp_path, monkeypatch):
    broken = tmp_path / "definitions"
    shutil.copytree(DEFINITIONS_DIR, broken)
    text = (broken / "04-build.yaml").read_text()
    (broken / "04-build.yaml").write_text(text.replace("required: true", "requird: true", 1))
    monkeypatch.setattr(definitions, "DEFINITIONS_DIR", broken)
    with pytest.raises(CatalogueError, match="04-build.yaml.*requird"):
        create_app(make_settings())
