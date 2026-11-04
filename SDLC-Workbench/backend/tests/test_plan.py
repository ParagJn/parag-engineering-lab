"""From the wizard's selection to a plan, and from a plan to parallel waves."""
from __future__ import annotations

import json

import pytest

from app.llm.routing import Routing
from app.workflow.definitions import ArtefactDef, load_catalogue
from app.workflow.plan import PlanError, build_plan, compute_waves


@pytest.fixture(scope="module")
def catalogue():
    return load_catalogue(Routing.load().roles.keys())


def art(key: str, *after: str) -> ArtefactDef:
    return ArtefactDef(key, key.upper(), f"T-{key.upper()}", "orchestrator", False, "", tuple(after), "t")


def keys(waves) -> list[list[str]]:
    return [[a.key for a in wave] for wave in waves]


def required_of(catalogue, phase_key: str) -> list[str]:
    return [a.key for a in catalogue.phase(phase_key).artefacts if a.required]


# ---- the default plan ----------------------------------------------------------------

def test_no_selection_means_everything(catalogue):
    plan = build_plan(catalogue, None)
    assert [len(p.artefacts) for p in plan.phases] == [len([a for a in p.artefacts if a.enabled and not a.by_hand]) for p in catalogue.phases]          # an artefact switched off, or done by hand, is not in a plan
    assert plan.notes == ()
    assert build_plan(catalogue, {}).phase("build").artefacts == plan.phase("build").artefacts


def test_none_for_a_phase_means_everything_in_that_phase(catalogue):
    plan = build_plan(catalogue, {"design": None})
    assert len(plan.phase("design").artefacts) == 3


def test_a_phase_missing_from_the_selection_gets_everything(catalogue):
    plan = build_plan(catalogue, {"requirements": required_of(catalogue, "requirements")})
    assert len(plan.phase("requirements").artefacts) == 6  # user_stories left off
    assert len(plan.phase("design").artefacts) == 3  # untouched


# ---- explicit selections --------------------------------------------------------------

def test_an_explicit_list_enables_exactly_those_in_catalogue_order(catalogue):
    wanted = required_of(catalogue, "design") + ["hifi_wireframes"]
    plan = build_plan(catalogue, {"design": list(reversed(wanted))})  # given in a different order
    assert [a.key for a in plan.phase("design").artefacts] == ["user_journey", "lowfi_wireframes", "hifi_wireframes"]


def test_leaving_an_optional_artefact_off_removes_it(catalogue):
    plan = build_plan(catalogue, {"architecture": required_of(catalogue, "architecture")})
    assert [a.key for a in plan.phase("architecture").artefacts] == [
        "component_overview", "high_level_design", "low_level_design"
    ]


def test_a_required_artefact_cannot_be_switched_off_and_the_error_says_which(catalogue):
    with pytest.raises(PlanError, match="'Personas'.*required and cannot be switched off") as exc:
        build_plan(catalogue, {"requirements": [k for k in required_of(catalogue, "requirements") if k != "personas"]})
    assert "Requirements" in str(exc.value)
    with pytest.raises(PlanError, match="are required"):
        build_plan(catalogue, {"requirements": ["personas"]})  # several missing: plural wording


def test_an_empty_list_is_an_error_because_required_artefacts_always_exist(catalogue):
    with pytest.raises(PlanError, match="required"):
        build_plan(catalogue, {"design": []})


def test_unknown_phase_and_unknown_artefact_keys_are_rejected(catalogue):
    with pytest.raises(PlanError, match="unknown phase.*nope"):
        build_plan(catalogue, {"nope": ["x"]})
    with pytest.raises(PlanError, match="no artefact.*ghost"):
        build_plan(catalogue, {"design": required_of(catalogue, "design") + ["ghost"]})


@pytest.mark.parametrize("bad", ["user_journey", 5, {"a": 1}, [1, 2], [None]])
def test_a_selection_of_the_wrong_shape_is_rejected(catalogue, bad):
    with pytest.raises(PlanError, match="list of artefact keys"):
        build_plan(catalogue, {"design": bad})


def test_in_the_shipped_catalogue_every_optional_artefact_depends_only_on_required_ones(catalogue):
    """So pulling a dependency in never fires on real data; the next test proves the rule on a hand-built chain.
    If someone adds an optional-needs-optional dependency to the YAML, this test says so on purpose."""
    for phase in catalogue.phases:
        required = {a.key for a in phase.artefacts if a.required}
        for item in phase.artefacts:
            if not item.required:
                assert set(item.after) <= required, f"{phase.key}.{item.key} depends on an optional artefact"
    assert build_plan(catalogue, {"architecture": required_of(catalogue, "architecture") + ["flow_diagram"]}).notes == ()


def test_pulling_in_follows_a_chain_and_names_who_needed_it():
    from app.workflow import plan as plan_module
    from app.workflow.definitions import Catalogue, PhaseDef

    chain = (
        ArtefactDef("base", "Base", "T-BASE", "orchestrator", True, "", (), "t"),
        ArtefactDef("mid", "Mid", "T-MID", "orchestrator", False, "", ("base",), "t"),
        ArtefactDef("leaf", "Leaf", "T-LEAF", "orchestrator", False, "", ("mid",), "t"),
    )
    cat = Catalogue((PhaseDef("t", 0, "Test phase", "", "x", chain),))
    plan = plan_module.build_plan(cat, {"t": ["base", "leaf"]})  # mid was switched off but leaf needs it
    phase = plan.phase("t")
    assert [a.key for a in phase.artefacts] == ["base", "mid", "leaf"]
    assert phase.pulled_in == ("mid",)
    assert plan.notes == ("Test phase: 'Mid' was added because 'Leaf' needs it",)


def test_nothing_is_reported_when_nothing_was_pulled_in(catalogue):
    assert build_plan(catalogue, {"design": required_of(catalogue, "design")}).notes == ()


def test_a_selection_survives_a_json_round_trip_through_the_project_column(catalogue, store):
    selection = {"requirements": required_of(catalogue, "requirements") + ["user_stories"], "design": None}
    project = store.projects.create(name="P", actor="system", selection=selection)
    stored = store.projects.get(project.id).selection
    assert stored == json.loads(json.dumps(selection))
    assert build_plan(catalogue, stored).phase("requirements").has("user_stories")


# ---- waves --------------------------------------------------------------------------------

def test_artefacts_with_nothing_to_wait_for_share_wave_one():
    assert keys(compute_waves((art("a"), art("b"), art("c")))) == [["a", "b", "c"]]


def test_a_chain_gets_one_wave_per_link():
    assert keys(compute_waves((art("a"), art("b", "a"), art("c", "b")))) == [["a"], ["b"], ["c"]]


def test_a_diamond_runs_the_two_middles_together():
    waves = compute_waves((art("top"), art("left", "top"), art("right", "top"), art("bottom", "left", "right")))
    assert keys(waves) == [["top"], ["left", "right"], ["bottom"]]


def test_an_artefact_waits_for_its_slowest_dependency():
    waves = compute_waves((art("a"), art("b", "a"), art("c"), art("d", "b", "c")))
    assert keys(waves) == [["a", "c"], ["b"], ["d"]]


def test_order_inside_a_wave_follows_the_catalogue_order():
    assert keys(compute_waves((art("z"), art("m"), art("a")))) == [["z", "m", "a"]]


def test_a_dependency_on_something_not_enabled_is_ignored_by_the_wave_maths():
    assert keys(compute_waves((art("b", "a"),))) == [["b"]]  # 'a' is not in the list


def test_a_loop_in_a_hand_built_list_is_an_error_not_a_hang():
    with pytest.raises(PlanError, match="loop"):
        compute_waves((art("a", "b"), art("b", "a")))


def test_every_enabled_artefact_is_in_exactly_one_wave_and_after_its_dependencies(catalogue):
    plan = build_plan(catalogue, None)
    for phase in plan.phases:
        flat = [a.key for wave in phase.waves for a in wave]
        assert sorted(flat) == sorted(a.key for a in phase.artefacts)
        placed: dict[str, int] = {}
        for n, wave in enumerate(phase.waves):
            for a in wave:
                placed[a.key] = n
        for a in phase.artefacts:
            assert all(placed[d] < placed[a.key] for d in a.after), (phase.key, a.key)


def test_the_real_requirements_phase_has_four_waves_with_real_parallelism(catalogue):
    waves = keys(build_plan(catalogue, None).phase("requirements").waves)
    assert waves == [
        ["personas", "problem_statement"],
        ["vision_objectives", "functional_requirements", "non_functional_requirements"],
        ["epics_features"],
        ["user_stories"],
    ]


def test_switching_an_artefact_off_changes_the_waves(catalogue):
    full = keys(build_plan(catalogue, None).phase("requirements").waves)
    trimmed = keys(build_plan(catalogue, {"requirements": required_of(catalogue, "requirements")}).phase("requirements").waves)
    assert full != trimmed and trimmed == full[:-1]  # user_stories was the last wave
    assert sum(map(len, trimmed)) == sum(map(len, full)) - 1


def test_the_widest_wave_in_the_default_plan_shows_what_parallelism_buys(catalogue):
    plan = build_plan(catalogue, None)
    widest = max((len(w), p.key) for p in plan.phases for w in p.waves)
    assert widest == (3, "requirements")  # S22b: Handover now runs only the runbook and then the hypercare plan, so it is no longer the widest
    assert max(len(w) for p in plan.phases for w in p.waves) <= 3


# ---- S21a: an artefact switched off in its definition is never in a plan --------------------------------------------------

def test_a_switched_off_artefact_is_never_run_never_required_and_is_listed_apart(catalogue):
    deploy = build_plan(catalogue, None).phase("deploy")
    assert [a.key for a in deploy.artefacts] == ["deployment_plan", "release_notes"]
    assert [a.key for a in deploy.not_enabled] == ["infrastructure_as_code", "cicd_pipeline"] and [a.key for a in deploy.by_hand] == ["deployment_verification"]
    assert [a.key for a in deploy.required] == ["deployment_plan", "release_notes"]
    assert [[a.key for a in w] for w in deploy.waves] == [["deployment_plan"], ["release_notes"]]
    assert build_plan(catalogue, None).phase("build").not_enabled == ()


def test_asking_for_a_switched_off_artefact_is_refused_with_its_reason(catalogue):
    with pytest.raises(PlanError, match="'Infrastructure as code' is not enabled \\(Not enabled. The product is built and run outside this tool"):
        build_plan(catalogue, {"deploy": ["deployment_plan", "release_notes", "infrastructure_as_code"]})
    with pytest.raises(PlanError, match="not enabled"):
        build_plan(catalogue, {"deploy": ["deployment_plan", "release_notes", "cicd_pipeline"]})


def test_the_three_that_run_can_be_chosen_exactly_and_the_other_phases_are_unchanged(catalogue):
    chosen = build_plan(catalogue, {"deploy": ["deployment_plan", "release_notes"]}).phase("deploy")
    assert [a.key for a in chosen.artefacts] == ["deployment_plan", "release_notes"] and chosen.pulled_in == ()
    assert [len(p.artefacts) for p in build_plan(catalogue, None).phases] == [1, 7, 3, 5, 1, 2, 2]


def test_a_switched_off_artefact_that_waits_for_a_working_one_is_accepted_but_never_planned(tmp_path):
    from tests.test_catalogue import good_phase, write_phase, ROLES
    data = good_phase()
    data["artefacts"][1] = {**data["artefacts"][1], "enabled": False, "disabled_reason": "Not enabled. later.", "after": ["a"]}
    write_phase(tmp_path, "00.yaml", data)
    plan = build_plan(load_catalogue(ROLES, tmp_path), None).phase("demo")
    assert [a.key for a in plan.artefacts] == ["a"] and [a.key for a in plan.not_enabled] == ["b"] and plan.pulled_in == ()


def test_an_artefact_done_by_hand_cannot_be_chosen_as_something_to_produce_and_the_refusal_says_why(catalogue):
    with pytest.raises(PlanError, match="Deploy: 'Deployment verification' is done by hand and cannot be chosen as something to produce"):
        build_plan(catalogue, {"deploy": ["deployment_plan", "release_notes", "deployment_verification"]})
    chosen = build_plan(catalogue, {"deploy": ["deployment_plan", "release_notes"]}).phase("deploy")
    assert [a.key for a in chosen.by_hand] == ["deployment_verification"] and [a.key for a in chosen.artefacts] == ["deployment_plan", "release_notes"]


def test_the_by_hand_list_holds_only_the_by_hand_artefacts(catalogue):
    plan = build_plan(catalogue, None)
    assert [a.key for a in plan.phase("deploy").by_hand] == ["deployment_verification"] and [a.key for a in plan.phase("handover").by_hand] == ["handover_signoff"]
    assert all(p.by_hand == () for p in plan.phases if p.key not in ("deploy", "handover"))


def test_the_handover_plan_runs_the_runbook_then_the_hypercare_plan_and_lists_the_rest_apart(catalogue):
    handover = build_plan(catalogue, None).phase("handover")
    assert [[a.key for a in w] for w in handover.waves] == [["runbook"], ["hypercare_plan"]] and [a.key for a in handover.required] == ["runbook", "hypercare_plan"]
    assert [a.key for a in handover.not_enabled] == ["support_guide", "slos_alerts", "kt_pack"] and [a.key for a in handover.by_hand] == ["handover_signoff"]
    with pytest.raises(PlanError, match="'Support guide' is not enabled"):
        build_plan(catalogue, {"handover": ["runbook", "hypercare_plan", "support_guide"]})
    with pytest.raises(PlanError, match="Handover sign-off' is done by hand"):
        build_plan(catalogue, {"handover": ["runbook", "hypercare_plan", "handover_signoff"]})

