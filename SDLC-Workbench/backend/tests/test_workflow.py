"""The state machine, the gates and the engine, against a real (temporary) database."""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from itertools import product

import pytest

from app.llm.routing import Routing
from app.models import PHASE_STATUSES, PHASE_TRANSITIONS, IllegalTransition, InvalidInput, NotFoundError
from app.workflow.definitions import load_catalogue
from app.workflow.engine import WorkflowEngine
from app.workflow.gates import GateNotMet, PrerequisiteNotMet

PERSON = "human:ann"


@pytest.fixture(scope="module")
def catalogue():
    return load_catalogue(Routing.load().roles.keys())


@pytest.fixture
def engine(catalogue, store):
    return WorkflowEngine(catalogue, store)


@pytest.fixture
def started(engine, project):
    engine.open_project(project.id)
    return project


def fill(store, engine, project, phase_key: str, *, only_required: bool = True) -> None:
    """Give every (required) artefact of a phase one version, the way the agents will later."""
    plan = engine.plan_for(store.projects.get(project.id))
    for item in plan.phase(phase_key).artefacts:
        if item.required or not only_required:
            artefact = store.artefacts.create(
                project.id, artefact_type=item.key, phase_key=phase_key, title=item.name,
                actor="system", prefix=item.id_prefix,
            )
            store.artefacts.add_version(project.id, artefact.id, body=f"content of {item.key}", author="agent:t@m")


def approve_phase(store, engine, project, phase_key: str) -> None:
    engine.start(project.id, phase_key, actor="system")
    fill(store, engine, project, phase_key)
    engine.finish(project.id, phase_key, actor="system")
    engine.approve(project.id, phase_key, actor=PERSON)


# ---- the transition table, every pair --------------------------------------------------

def run_to(store, project, status: str) -> None:
    """Put a fresh phase into `status` using only legal moves."""
    store.phases.ensure(project.id, "requirements")
    path = {
        "not_started": [],
        "running": ["running"],
        "awaiting_review": ["running", "awaiting_review"],
        "approved": ["running", "awaiting_review", "approved"],
        "rejected": ["running", "awaiting_review", "rejected"],
    }[status]
    for step in path:
        if step == "approved":
            store.phases.record_decision(project.id, "requirements", "approve", actor=PERSON)
        elif step == "rejected":
            store.phases.record_decision(project.id, "requirements", "reject", actor=PERSON, feedback="redo")
        else:
            store.phases.set_status(project.id, "requirements", step, actor="system")


def attempt(store, project, wanted: str) -> None:
    if wanted == "approved":
        store.phases.record_decision(project.id, "requirements", "approve", actor=PERSON)
    elif wanted == "rejected":
        store.phases.record_decision(project.id, "requirements", "reject", actor=PERSON, feedback="redo")
    else:
        store.phases.set_status(project.id, "requirements", wanted, actor="system")


@pytest.mark.parametrize("current, wanted", list(product(PHASE_STATUSES, PHASE_STATUSES)))
def test_every_pair_of_statuses_is_allowed_or_refused_exactly_as_the_table_says(store, project, current, wanted):
    run_to(store, project, current)
    audit_before = len(store.audit.list(project.id))
    row_before = store.phases.get(project.id, "requirements")

    legal = wanted in PHASE_TRANSITIONS[current] and current != "approved"
    # An approved phase can't be moved by set_status/record_decision at all; reopen is its only way out.
    if legal:
        attempt(store, project, wanted)
        assert store.phases.get(project.id, "requirements").status == wanted
    else:
        with pytest.raises(InvalidInput):
            attempt(store, project, wanted)
        assert store.phases.get(project.id, "requirements") == row_before
        assert len(store.audit.list(project.id)) == audit_before  # a refusal leaves no trace behind


def test_the_table_covers_every_status_and_only_real_statuses():
    assert set(PHASE_TRANSITIONS) == set(PHASE_STATUSES)
    for targets in PHASE_TRANSITIONS.values():
        assert set(targets) <= set(PHASE_STATUSES)


def test_the_refusal_message_names_both_statuses_and_what_is_possible(store, project):
    run_to(store, project, "not_started")
    with pytest.raises(IllegalTransition, match=r"from 'not_started' to 'approved'.*\['running'\]"):
        attempt(store, project, "approved")


def test_an_illegal_transition_is_still_an_invalid_input_so_older_callers_work(store, project):
    run_to(store, project, "not_started")
    with pytest.raises(InvalidInput):
        attempt(store, project, "awaiting_review")
    assert issubclass(IllegalTransition, InvalidInput)


def test_approving_a_phase_that_never_ran_is_refused(store, project):
    store.phases.ensure(project.id, "requirements")
    with pytest.raises(IllegalTransition):
        store.phases.record_decision(project.id, "requirements", "approve", actor=PERSON)


def test_an_approved_phase_is_final_until_reopened(store, project):
    run_to(store, project, "approved")
    for call in (
        lambda: store.phases.set_status(project.id, "requirements", "running", actor="system"),
        lambda: store.phases.set_status(project.id, "requirements", "not_started", actor="system"),
        lambda: store.phases.record_decision(project.id, "requirements", "reject", actor=PERSON, feedback="x"),
    ):
        with pytest.raises(IllegalTransition, match="reopen"):
            call()
    assert store.phases.get(project.id, "requirements").status == "approved"


def test_a_rejected_phase_can_only_be_rerun(store, project):
    run_to(store, project, "rejected")
    with pytest.raises(IllegalTransition):
        store.phases.set_status(project.id, "requirements", "awaiting_review", actor="system")
    assert store.phases.set_status(project.id, "requirements", "running", actor="system").status == "running"


def test_gate_rules_from_s01_still_hold(store, project):
    run_to(store, project, "awaiting_review")
    with pytest.raises(InvalidInput):
        store.phases.record_decision(project.id, "requirements", "approve", actor="agent:r@m")
    with pytest.raises(InvalidInput):
        store.phases.record_decision(project.id, "requirements", "reject", actor=PERSON, feedback="  ")
    assert store.phases.get(project.id, "requirements").status == "awaiting_review"


# ---- reopen ----------------------------------------------------------------------------------

def test_reopen_returns_an_approved_phase_to_running_clearing_the_decision(store, project):
    run_to(store, project, "approved")
    run = store.phases.reopen(project.id, "requirements", actor=PERSON, reason="  Scope changed  ")
    assert (run.status, run.decision, run.decided_by, run.feedback, run.finished_at) == ("running", None, None, None, None)
    event = [e for e in store.audit.list(project.id) if e.action == "phase.reopened"][0]
    assert event.actor == PERSON and event.detail == {"reason": "Scope changed", "was_approved_by": PERSON}


@pytest.mark.parametrize("status", ["not_started", "running", "awaiting_review", "rejected"])
def test_only_an_approved_phase_can_be_reopened(store, project, status):
    run_to(store, project, status)
    with pytest.raises(IllegalTransition, match="only an approved phase"):
        store.phases.reopen(project.id, "requirements", actor=PERSON, reason="why")
    assert store.phases.get(project.id, "requirements").status == status


@pytest.mark.parametrize("actor", ["system", "agent:r@m"])
def test_reopening_needs_a_person(store, project, actor):
    run_to(store, project, "approved")
    with pytest.raises(InvalidInput, match="needs a person"):
        store.phases.reopen(project.id, "requirements", actor=actor, reason="why")
    assert store.phases.get(project.id, "requirements").status == "approved"


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_reopening_needs_a_reason(store, project, reason):
    run_to(store, project, "approved")
    with pytest.raises(InvalidInput, match="written reason"):
        store.phases.reopen(project.id, "requirements", actor=PERSON, reason=reason)


def test_reopening_a_missing_phase(store, project):
    with pytest.raises(NotFoundError):
        store.phases.reopen(project.id, "design", actor=PERSON, reason="why")


# ---- prerequisites ------------------------------------------------------------------------------

def test_setup_starts_freely_and_everything_else_waits_for_the_one_before(engine, started):
    assert engine.start(started.id, "setup", actor="system").status == "running"
    with pytest.raises(PrerequisiteNotMet, match="Requirements cannot start yet: Setup is 'running'"):
        engine.start(started.id, "requirements", actor="system")
    for later in ("design", "architecture", "build", "deploy", "handover"):
        with pytest.raises(PrerequisiteNotMet):
            engine.start(started.id, later, actor="system")


def test_the_error_names_the_nearest_blocking_phase_not_the_first_incomplete_one(engine, store, started):
    approve_phase(store, engine, started, "setup")
    with pytest.raises(PrerequisiteNotMet, match="Design cannot start yet: Requirements is 'not_started'"):
        engine.start(started.id, "design", actor="system")


def test_starting_the_next_phase_after_approval_works(engine, store, started):
    approve_phase(store, engine, started, "setup")
    assert engine.start(started.id, "requirements", actor="system").status == "running"


def test_a_phase_with_no_artefacts_in_the_plan_is_skipped_not_blocking(catalogue, store):
    from app.workflow.gates import blocking_phase
    from app.workflow.plan import PhasePlan, Plan

    full = WorkflowEngine(catalogue, store)
    project = store.projects.create(name="skip", actor="system")
    plan = full.plan_for(project)
    emptied = Plan(tuple(PhasePlan(p.phase, (), (), ()) if p.key == "design" else p for p in plan.phases))
    # Design is empty, so with Setup and Requirements approved, Architecture is not blocked by Design.
    rows = [
        type("R", (), {"phase_key": "setup", "status": "approved"})(),
        type("R", (), {"phase_key": "requirements", "status": "approved"})(),
    ]
    assert blocking_phase(emptied, rows, "architecture") is None
    assert blocking_phase(plan, rows, "architecture").key == "design"


def test_a_phase_with_no_row_counts_as_not_started(engine, started, store):
    # open_project made rows; delete the Setup row's effect by asking about a project that skipped it.
    other = store.projects.create(name="no rows", actor="system")
    with pytest.raises(PrerequisiteNotMet, match="Setup is 'not_started'"):
        engine.start(other.id, "requirements", actor="system")


def test_unknown_phases_and_projects_are_not_found(engine, started):
    with pytest.raises(NotFoundError, match="unknown phase"):
        engine.start(started.id, "launch", actor="system")
    with pytest.raises(NotFoundError):
        engine.start("nope", "setup", actor="system")


# ---- the approval gate -------------------------------------------------------------------------------

def test_a_phase_cannot_be_approved_while_a_required_artefact_has_no_content(engine, store, started):
    engine.start(started.id, "setup", actor="system")
    engine.finish(started.id, "setup", actor="system")
    with pytest.raises(GateNotMet, match="Setup cannot be approved.*Project charter"):
        engine.approve(started.id, "setup", actor=PERSON)
    assert store.phases.get(started.id, "setup").status == "awaiting_review"
    fill(store, engine, started, "setup")
    assert engine.approve(started.id, "setup", actor=PERSON).status == "approved"


def test_the_gate_lists_every_missing_required_artefact_by_name(engine, store, started):
    approve_phase(store, engine, started, "setup")
    engine.start(started.id, "requirements", actor="system")
    engine.finish(started.id, "requirements", actor="system")
    with pytest.raises(GateNotMet) as exc:
        engine.approve(started.id, "requirements", actor=PERSON)
    for name in ("Personas", "Problem statement", "Vision and objectives", "Functional requirements",
                 "Non-functional requirements", "Epics and features"):
        assert name in str(exc.value)
    assert "User stories" not in str(exc.value)  # optional artefacts never block


def test_an_artefact_with_no_versions_does_not_count_as_content(engine, store, started):
    engine.start(started.id, "setup", actor="system")
    store.artefacts.create(started.id, artefact_type="project_charter", phase_key="setup", title="x",
                           actor="system", prefix="SET-CHR")  # created, but never given a version
    engine.finish(started.id, "setup", actor="system")
    with pytest.raises(GateNotMet):
        engine.approve(started.id, "setup", actor=PERSON)


def test_content_in_the_wrong_phase_does_not_satisfy_the_gate(engine, store, started):
    engine.start(started.id, "setup", actor="system")
    other = store.artefacts.create(started.id, artefact_type="project_charter", phase_key="requirements",
                                   title="x", actor="system", prefix="SET-CHR")
    store.artefacts.add_version(started.id, other.id, body="b", author="agent:t@m")
    engine.finish(started.id, "setup", actor="system")
    with pytest.raises(GateNotMet):
        engine.approve(started.id, "setup", actor=PERSON)


def test_a_switched_off_optional_artefact_never_blocks_and_a_present_one_is_not_required(catalogue, store):
    project = store.projects.create(
        name="trim", actor="system",
        selection={"design": ["user_journey", "lowfi_wireframes"]},  # hifi switched off
    )
    engine = WorkflowEngine(catalogue, store)
    engine.open_project(project.id)
    for earlier in ("setup", "requirements"):
        approve_phase(store, engine, project, earlier)
    engine.start(project.id, "design", actor="system")
    fill(store, engine, project, "design")
    engine.finish(project.id, "design", actor="system")
    assert engine.approve(project.id, "design", actor=PERSON).status == "approved"


def test_a_refused_approval_leaves_no_audit_row_and_changes_nothing(engine, store, started):
    engine.start(started.id, "setup", actor="system")
    engine.finish(started.id, "setup", actor="system")
    before = len(store.audit.list(started.id))
    with pytest.raises(GateNotMet):
        engine.approve(started.id, "setup", actor=PERSON)
    assert len(store.audit.list(started.id)) == before


def test_rejecting_does_not_need_the_content_check(engine, store, started):
    engine.start(started.id, "setup", actor="system")
    engine.finish(started.id, "setup", actor="system")
    run = engine.reject(started.id, "setup", actor=PERSON, feedback="start again")
    assert run.status == "rejected" and run.feedback == "start again"


# ---- atomic start ---------------------------------------------------------------------------------------

def test_ten_simultaneous_starts_of_one_phase_give_exactly_one_winner(catalogue, store):
    project = store.projects.create(name="race", actor="system")
    engine = WorkflowEngine(catalogue, store)
    engine.open_project(project.id)

    def start(_):
        try:
            engine.start(project.id, "setup", actor="system")
            return "won"
        except IllegalTransition:
            return "lost"

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(start, range(10)))
    assert results.count("won") == 1 and results.count("lost") == 9
    statuses = [e for e in store.audit.list(project.id) if e.action == "phase.status"]
    assert len(statuses) == 1 and store.phases.get(project.id, "setup").status == "running"


def test_the_prerequisite_check_and_the_status_change_share_one_transaction(catalogue, store, monkeypatch):
    """If the approval of the earlier phase could slip in between check and change, this would be unsound.
    Prove the guard runs inside the write transaction by making it read through the same connection."""
    project = store.projects.create(name="txn", actor="system")
    engine = WorkflowEngine(catalogue, store)
    engine.open_project(project.id)
    seen: list[bool] = []

    import app.workflow.engine as engine_module

    real = engine_module.check_can_start

    def spy(plan, rows, phase_key):
        seen.append(True)
        return real(plan, rows, phase_key)

    monkeypatch.setattr(engine_module, "check_can_start", spy)
    engine.start(project.id, "setup", actor="system")
    assert seen == [True]


# ---- snapshot and next_action ---------------------------------------------------------------------------

def test_next_action_walks_through_a_phase_in_plain_words(engine, store, started):
    assert engine.next_action(started.id) == "Setup can start"
    engine.start(started.id, "setup", actor="system")
    assert engine.next_action(started.id) == "Setup is running (1 required artefact(s) still empty)"
    fill(store, engine, started, "setup")
    assert engine.next_action(started.id) == "Setup is running"
    engine.finish(started.id, "setup", actor="system")
    assert engine.next_action(started.id) == "Setup is awaiting review by the architect"          # S23: follows the roles that may approve Setup, not the definition's old label
    engine.reject(started.id, "setup", actor=PERSON, feedback="redo")
    assert engine.next_action(started.id) == "Setup was rejected and needs to be re-run"
    engine.start(started.id, "setup", actor="system")
    engine.finish(started.id, "setup", actor="system")
    engine.approve(started.id, "setup", actor=PERSON)
    assert engine.next_action(started.id) == "Requirements can start"


def test_next_action_when_everything_is_approved(catalogue, store):
    project = store.projects.create(name="all", actor="system")
    engine = WorkflowEngine(catalogue, store)
    engine.open_project(project.id)
    for key in catalogue.phase_keys:
        approve_phase(store, engine, project, key)
    assert engine.next_action(project.id) == "All phases are approved"
    snap = engine.snapshot(project.id)
    assert [p.status for p in snap.phases] == ["approved"] * 7 and not any(p.needs_review for p in snap.phases)


def test_the_snapshot_describes_each_phase_and_artefact(engine, store, started):
    approve_phase(store, engine, started, "setup")
    engine.start(started.id, "requirements", actor="system")
    snap = engine.snapshot(started.id)
    assert [p.key for p in snap.phases] == ["setup", "requirements", "design", "architecture", "build", "deploy", "handover"]
    setup, reqs, design = snap.phases[0], snap.phases[1], snap.phases[2]
    assert (setup.status, setup.decided_by, setup.blocked_by) == ("approved", PERSON, None)
    assert reqs.status == "running" and reqs.blocked_by is None
    assert design.status == "not_started" and design.blocked_by == "Requirements"
    personas = next(a for a in reqs.artefacts if a.key == "personas")
    functional = next(a for a in reqs.artefacts if a.key == "functional_requirements")
    assert (personas.wave, personas.required, personas.has_content, personas.waits_for) == (1, True, False, ())
    assert functional.wave == 2 and functional.waits_for == ("personas", "problem_statement")
    assert next(a for a in setup.artefacts if a.key == "project_charter").has_content is True


def test_the_snapshot_reflects_a_trimmed_plan(catalogue, store):
    project = store.projects.create(name="t", actor="system", selection={
        "requirements": [a.key for a in catalogue.phase("requirements").artefacts if a.required]})
    engine = WorkflowEngine(catalogue, store)
    engine.open_project(project.id)
    reqs = engine.snapshot(project.id).phases[1]
    assert "user_stories" not in [a.key for a in reqs.artefacts] and len(reqs.artefacts) == 6


def test_a_project_with_an_invalid_stored_selection_is_a_clear_error(catalogue, store):
    project = store.projects.create(name="bad", actor="system", selection={"requirements": ["personas"]})
    with pytest.raises(InvalidInput, match="invalid selection.*required"):
        WorkflowEngine(catalogue, store).snapshot(project.id)


def test_open_project_creates_a_row_per_phase_and_is_repeatable(engine, store, project):
    engine.open_project(project.id)
    engine.open_project(project.id)
    rows = store.phases.list(project.id)
    assert [r.phase_key for r in rows] == list(engine.catalogue.phase_keys) and {r.status for r in rows} == {"not_started"}


# ---- reopen and downstream phases ------------------------------------------------------------------------

def test_reopening_marks_later_approved_phases_as_needing_review_and_not_earlier_ones(catalogue, store):
    project = store.projects.create(name="reopen", actor="system")
    engine = WorkflowEngine(catalogue, store)
    engine.open_project(project.id)
    for key in ("setup", "requirements", "design"):
        approve_phase(store, engine, project, key)
    assert not any(p.needs_review for p in engine.snapshot(project.id).phases)

    engine.reopen(project.id, "requirements", actor=PERSON, reason="the brief changed")
    by_key = {p.key: p for p in engine.snapshot(project.id).phases}
    assert by_key["requirements"].status == "running" and not by_key["requirements"].needs_review
    assert by_key["setup"].needs_review is False       # earlier: untouched
    assert by_key["design"].needs_review is True        # later and approved: flagged
    assert by_key["architecture"].needs_review is False  # later but never approved: nothing to flag


def test_a_phase_re_approved_after_the_reopen_stops_needing_review(catalogue, store):
    project = store.projects.create(name="reapprove", actor="system")
    engine = WorkflowEngine(catalogue, store)
    engine.open_project(project.id)
    for key in ("setup", "requirements", "design"):
        approve_phase(store, engine, project, key)
    engine.reopen(project.id, "requirements", actor=PERSON, reason="changed")
    engine.finish(project.id, "requirements", actor="system")
    engine.approve(project.id, "requirements", actor=PERSON)
    engine.reopen(project.id, "design", actor=PERSON, reason="re-check")
    engine.finish(project.id, "design", actor="system")
    engine.approve(project.id, "design", actor=PERSON)
    assert not any(p.needs_review for p in engine.snapshot(project.id).phases)


def test_the_engine_refuses_to_reopen_a_phase_that_is_not_approved(engine, started):
    with pytest.raises(IllegalTransition):
        engine.reopen(started.id, "setup", actor=PERSON, reason="x")


def test_ensure_does_not_resurrect_or_reset_an_existing_phase(engine, store, started):
    approve_phase(store, engine, started, "setup")
    engine.open_project(started.id)
    assert store.phases.get(started.id, "setup").status == "approved"


# ---- S21a: an artefact switched off in its definition -------------------------------------------------------------------------------------------

def test_the_deploy_phase_can_be_approved_without_the_artefacts_that_are_not_enabled(catalogue, store, engine, started):
    for key in ("setup", "requirements", "design", "architecture", "build"):
        approve_phase(store, engine, started, key)
    engine.start(started.id, "deploy", actor="system")
    fill(store, engine, started, "deploy", only_required=False)
    names = {a.type for a in store.artefacts.list(started.id, phase_key="deploy")}
    assert names == {"deployment_plan", "release_notes"}                  # the two that are not enabled, and the one done by hand, were not even created
    engine.finish(started.id, "deploy", actor="system")
    engine.approve(started.id, "deploy", actor=PERSON)
    assert next(p for p in engine.snapshot(started.id).phases if p.key == "deploy").status == "approved"


def test_the_deploy_phase_still_needs_its_two_required_artefacts_and_never_the_one_done_by_hand(catalogue, store, engine, started):
    for key in ("setup", "requirements", "design", "architecture", "build"):
        approve_phase(store, engine, started, key)
    engine.start(started.id, "deploy", actor="system")
    plan = engine.plan_for(store.projects.get(started.id)).phase("deploy")
    first = plan.artefacts[0]
    artefact = store.artefacts.create(started.id, artefact_type=first.key, phase_key="deploy", title=first.name, actor="system", prefix=first.id_prefix)
    store.artefacts.add_version(started.id, artefact.id, body="x", author="agent:t@m")
    with pytest.raises(GateNotMet) as caught:
        engine.finish(started.id, "deploy", actor="system")
        engine.approve(started.id, "deploy", actor=PERSON)
    assert "Release notes" in str(caught.value)
    for never in ("Deployment verification", "Infrastructure as code", "CI/CD pipeline"):
        assert never not in str(caught.value), never                              # none of these can ever be what approval is waiting for


def test_the_snapshot_lists_the_artefacts_that_are_not_enabled_apart_from_those_that_run(catalogue, store, engine, started):
    deploy = next(p for p in engine.snapshot(started.id).phases if p.key == "deploy")
    assert [a.key for a in deploy.artefacts] == ["deployment_plan", "release_notes"] and [(b.key, b.name) for b in deploy.by_hand] == [("deployment_verification", "Deployment verification")]
    assert [(n.key, n.name) for n in deploy.not_enabled] == [("infrastructure_as_code", "Infrastructure as code"), ("cicd_pipeline", "CI/CD pipeline")]
    assert all(n.reason.startswith("Not enabled.") for n in deploy.not_enabled)
    assert all(p.not_enabled == () for p in engine.snapshot(started.id).phases if p.key not in ("deploy", "handover"))
    handover = next(p for p in engine.snapshot(started.id).phases if p.key == "handover")          # S22b
    assert [a.key for a in handover.artefacts] == ["runbook", "hypercare_plan"] and [b.key for b in handover.by_hand] == ["handover_signoff"]
    assert [n.key for n in handover.not_enabled] == ["support_guide", "slos_alerts", "kt_pack"]
