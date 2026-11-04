"""The contract fixtures the screen decodes (S12a) must be what the routes return right now."""
from __future__ import annotations

import json

from scripts import export_contract as contract


def test_the_fixtures_on_disk_are_what_the_routes_return_now():
    """If this fails, a route's response changed: run `python -m scripts.export_contract`, then `npm test` in frontend/."""
    assert contract.stale(contract.build_examples()) == []


def test_every_route_the_screen_calls_has_a_fixture():
    assert set(contract.build_examples()) == {
        "catalogue", "error_400", "error_404", "error_409", "error_422", "modes", "plan_preview", "project_created", "project_detail",
        "projects_empty", "projects_list", "status",
        # S12b
        "sample", "document_added", "documents", "search", "artefacts", "artefact_detail", "runs", "run_detail", "run_started",
        "gate_finish", "gate_approve", "events",
        # S12c
        "review_state_before", "review_result", "review_artefact_detail", "review_paused", "review_phase", "review_state_after", "error_422_edit",
        "edit_saved", "review_state_stale", "request_changes", "rerun_started", "error_409_archived", "error_409_replay_reviews",
        # S13
        "svg_corpus",
        # S14b
        "architecture_flow_detail", "architecture_usecase_detail",
        # S15
        "traceability", "traceability_item", "error_404_trace_item", "traceability_with_gaps", "review_state_with_trace_gaps",
        # reopen
        "gate_reopen", "error_422_reopen_blank", "error_409_reopen_not_approved",
        # S20
        "verify_run", "verify_list", "error_422_verify", "error_404_verify",
        # S21c
        "checklist_empty", "checklist_answered", "error_409_checklist_closed", "error_404_check", "signoff_empty", "signoff_answered",
    }


def test_the_fixtures_are_the_same_every_time_they_are_made():
    assert contract.render(contract.build_examples()) == contract.render(contract.build_examples())


def test_a_changed_missing_or_leftover_fixture_is_reported(tmp_path):
    examples = {"a": {"x": 1}, "b": {"y": 2}}
    (tmp_path / "a.json").write_text(contract.render({"x": 999}), encoding="utf-8")
    (tmp_path / "old.json").write_text("{}", encoding="utf-8")
    problems = contract.stale(examples, tmp_path)
    assert problems == ["a.json no longer matches what the backend returns", "b.json is missing", "old.json is not produced by any route any more"]
    (tmp_path / "old.json").unlink()
    (tmp_path / "a.json").write_text(contract.render(examples["a"]), encoding="utf-8")
    (tmp_path / "b.json").write_text(contract.render(examples["b"]), encoding="utf-8")
    assert contract.stale(examples, tmp_path) == []


def test_the_check_flag_writes_nothing_and_fails_on_a_stale_folder(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(contract, "FIXTURES", tmp_path / "empty")
    monkeypatch.setattr(contract.sys, "argv", ["x"])
    code = contract.main(["--check"])
    out = capsys.readouterr()
    assert code == 1 and "is missing" in out.err
    assert not (tmp_path / "empty").exists()      # --check never writes


def test_writing_then_checking_agrees(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(contract, "FIXTURES", tmp_path / "out")
    assert contract.main([]) == 0
    assert contract.main(["--check"]) == 0
    capsys.readouterr()
    written = sorted(p.name for p in (tmp_path / "out").glob("*.json"))
    assert len(written) == 58 and all(json.loads((tmp_path / "out" / n).read_text(encoding="utf-8")) is not None for n in written)


def test_a_fixture_holds_no_machine_specific_detail():
    text = "".join(p.read_text(encoding="utf-8") for p in contract.FIXTURES.glob("*.json"))
    for forbidden in ("/Users", "sk-", "Traceback", ".db"):
        assert forbidden not in text, forbidden


def test_there_is_one_example_of_every_event_type_the_runner_can_publish():
    """If the runner gains an event type, this fails until the exporter scripts a situation that publishes it and the screen decodes it."""
    import re
    from pathlib import Path

    app_dir = Path(contract.__file__).resolve().parents[1] / "app"
    source = (app_dir / "run" / "runner.py").read_text(encoding="utf-8")
    published = set(re.findall(r'publish\([^)]*?"([a-z]+\.[a-z_]+)"', source)) | set(re.findall(r'event = "([a-z]+\.[a-z_]+)"', source)) | {"run.finished", "run.stopped"}
    # The Build phase's fix loop publishes through the runner (it is handed a way to publish), so its event names are in its own file (S17c).
    published |= set(re.findall(r'emit\("([a-z]+\.[a-z_]+)"', (app_dir / "build" / "loop.py").read_text(encoding="utf-8")))
    # So does the instruction-set composer, through `say(...)` (S19b); its events are named where it calls it.
    published |= set(re.findall(r'say\("([a-z]+\.[a-z_]+)"', (app_dir / "build" / "compose.py").read_text(encoding="utf-8")))
    assert published, "precondition: found the event names in the runner"
    examples = contract.build_examples()["events"]
    assert {name.split(".", 2)[0] + "." + name.split(".", 2)[1] for name in examples} == published      # every type, however many shapes it has


def test_an_event_type_with_two_shapes_has_a_fixture_for_each():
    examples = contract.build_examples()["events"]
    assert {"options", "slot"} <= set(examples["review.paused"]) and "reason" not in examples["review.paused"]       # the reviewer could not run
    assert "reason" in examples["review.paused.reason"] and "options" not in examples["review.paused.reason"]       # the review failed another way
    assert "artefacts" in examples["run.stopped"]                                                                    # stopped early with totals
    assert "artefacts" not in examples["run.stopped.short"] and examples["run.stopped.short"]["status"] == "interrupted"   # no totals


def test_the_build_round_event_has_a_fixture_that_is_counts_and_a_name_only():
    example = contract.build_examples()["events"]["build.round"]
    assert set(example) == {"run_id", "at", "round", "artefact", "failed", "errors"}
    assert isinstance(example["round"], int) and isinstance(example["failed"], int) and isinstance(example["errors"], int) and isinstance(example["artefact"], str)
