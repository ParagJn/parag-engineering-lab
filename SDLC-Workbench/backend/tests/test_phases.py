from __future__ import annotations

import pytest

from app.models import InvalidInput, NotFoundError


@pytest.fixture
def phase(store, project):
    return store.phases.ensure(project.id, "requirements")


def test_ensure_creates_not_started_and_is_idempotent(store, project):
    first = store.phases.ensure(project.id, "requirements")
    again = store.phases.ensure(project.id, "requirements")
    assert first.status == "not_started"
    assert first == again
    assert len(store.phases.list(project.id)) == 1
    created = [e for e in store.audit.list(project.id) if e.action == "phase.created"]
    assert len(created) == 1


def test_phases_list_in_creation_order(store, project):
    for key in ("requirements", "design", "architecture"):
        store.phases.ensure(project.id, key)
    assert [p.phase_key for p in store.phases.list(project.id)] == ["requirements", "design", "architecture"]


def test_ensure_needs_a_real_project_and_a_key(store, project):
    with pytest.raises(NotFoundError):
        store.phases.ensure("nope", "requirements")
    with pytest.raises(InvalidInput):
        store.phases.ensure(project.id, "  ")


def test_running_sets_the_start_time(store, project, phase):
    run = store.phases.set_status(project.id, "requirements", "running", actor="system")
    assert run.status == "running"
    assert run.started_at is not None
    assert run.finished_at is None


def test_awaiting_review_sets_the_finish_time(store, project, phase):
    store.phases.set_status(project.id, "requirements", "running", actor="system")
    run = store.phases.set_status(project.id, "requirements", "awaiting_review", actor="system")
    assert run.status == "awaiting_review"
    assert run.finished_at is not None


def to_review(store, project, key="requirements"):
    """The legal route to a gate: not_started -> running -> awaiting_review."""
    store.phases.set_status(project.id, key, "running", actor="system")
    store.phases.set_status(project.id, key, "awaiting_review", actor="system")


def test_approve_is_recorded_with_who_decided(store, project, phase):
    to_review(store, project)  # S05: was a direct jump to awaiting_review, now refused
    run = store.phases.record_decision(project.id, "requirements", "approve", actor="human:ann")
    assert (run.status, run.decision, run.decided_by) == ("approved", "approve", "human:ann")
    assert run.feedback is None


def test_reject_is_recorded_with_feedback(store, project, phase):
    to_review(store, project)  # S05: was a direct jump to awaiting_review, now refused
    run = store.phases.record_decision(
        project.id, "requirements", "reject", actor="human:ann", feedback="  Missing an NFR for peak load  "
    )
    assert (run.status, run.decision) == ("rejected", "reject")
    assert run.feedback == "Missing an NFR for peak load"


def test_reject_needs_written_feedback(store, project, phase):
    for feedback in (None, "", "   "):
        with pytest.raises(InvalidInput):
            store.phases.record_decision(project.id, "requirements", "reject", actor="human:ann", feedback=feedback)
    assert store.phases.get(project.id, "requirements").status == "not_started"


def test_an_agent_cannot_decide_a_gate(store, project, phase):
    for decision in ("approve", "reject"):
        with pytest.raises(InvalidInput):
            store.phases.record_decision(
                project.id, "requirements", decision, actor="agent:reviewer@some-model", feedback="x"
            )
    assert store.phases.get(project.id, "requirements").status == "not_started"


def test_the_system_may_decide_for_automated_demo_paths(store, project, phase):
    to_review(store, project)  # S05: was an approval straight from not_started, now refused
    run = store.phases.record_decision(project.id, "requirements", "approve", actor="system")
    assert run.status == "approved"


def test_bad_decision_is_rejected(store, project, phase):
    with pytest.raises(InvalidInput):
        store.phases.record_decision(project.id, "requirements", "maybe", actor="human:ann")


def test_approved_and_rejected_cannot_be_set_directly(store, project, phase):
    for status in ("approved", "rejected"):
        with pytest.raises(InvalidInput):
            store.phases.set_status(project.id, "requirements", status, actor="human:ann")
    assert store.phases.get(project.id, "requirements").status == "not_started"


def test_unknown_status_is_rejected(store, project, phase):
    with pytest.raises(InvalidInput):
        store.phases.set_status(project.id, "requirements", "flying", actor="system")


def test_rerunning_after_a_rejection_forgets_the_old_decision(store, project, phase):
    to_review(store, project)  # S05: was a rejection straight from not_started, now refused
    store.phases.record_decision(project.id, "requirements", "reject", actor="human:ann", feedback="Redo")
    run = store.phases.set_status(project.id, "requirements", "running", actor="system")
    assert run.status == "running"
    assert (run.decision, run.decided_by, run.feedback) == (None, None, None)
    assert run.finished_at is None


def test_missing_phase(store, project):
    with pytest.raises(NotFoundError):
        store.phases.get(project.id, "design")
    with pytest.raises(NotFoundError):
        store.phases.set_status(project.id, "design", "running", actor="system")
    with pytest.raises(NotFoundError):
        store.phases.record_decision(project.id, "design", "approve", actor="human:ann")


def test_transitions_and_decisions_are_audited(store, project, phase):
    store.phases.set_status(project.id, "requirements", "running", actor="system")
    store.phases.set_status(project.id, "requirements", "awaiting_review", actor="system")
    store.phases.record_decision(project.id, "requirements", "approve", actor="human:ann")
    events = [e for e in store.audit.list(project.id) if e.target_type == "phase"]
    assert [e.action for e in events] == ["phase.created", "phase.status", "phase.status", "phase.decided"]
    assert events[1].detail == {"from": "not_started", "to": "running"}
    assert events[3].actor == "human:ann"
    assert events[3].detail["decision"] == "approve"
