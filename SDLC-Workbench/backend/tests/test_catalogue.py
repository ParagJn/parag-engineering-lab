"""The shipped phase definitions, and the loader's refusal to accept a bad one."""
from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

from app.llm.routing import REQUIRED_ROLES, Routing
from app.workflow.definitions import (
    DEFINITIONS_DIR,
    CatalogueError,
    PhaseDef,
    build_catalogue,
    load_catalogue,
    parse_phase,
)

ROLES = tuple(Routing.load().roles)


@pytest.fixture(scope="module")
def catalogue():
    return load_catalogue(ROLES)


# ---- the shipped catalogue -----------------------------------------------------------

def test_seven_phases_in_lifecycle_order(catalogue):
    assert catalogue.phase_keys == ("setup", "requirements", "design", "architecture", "build", "deploy", "handover")
    assert [p.order for p in catalogue.phases] == list(range(7))


def test_counts_match_the_reviewed_spec(catalogue):
    assert (len(catalogue.phases), catalogue.artefact_count, catalogue.required_count, catalogue.not_enabled_count) == (7, 28, 17, 5)
    per_phase = {p.key: (len(p.artefacts), sum(a.required for a in p.artefacts)) for p in catalogue.phases}
    assert per_phase == {
        "setup": (1, 1), "requirements": (7, 6), "design": (3, 2), "architecture": (5, 3),
        "build": (1, 1), "deploy": (5, 2), "handover": (6, 2),
    }


def test_every_phase_has_a_required_artefact_a_name_and_an_approver(catalogue):
    for phase in catalogue.phases:
        assert any(a.required for a in phase.artefacts), phase.key
        assert phase.name.strip() and phase.approver.strip() and phase.summary.strip(), phase.key


def test_every_role_exists_in_routing(catalogue):
    used = {a.role for p in catalogue.phases for a in p.artefacts if not a.by_hand}                      # an artefact done by hand has no role
    assert used <= set(REQUIRED_ROLES)


def test_every_artefact_has_a_description_and_a_unique_key_across_the_catalogue(catalogue):
    keys = [a.key for p in catalogue.phases for a in p.artefacts]
    assert len(keys) == len(set(keys)) == 28
    assert all(a.description.strip() for p in catalogue.phases for a in p.artefacts)


def test_prefixes_are_unique_and_none_is_the_start_of_another(catalogue):
    prefixes = [a.id_prefix for p in catalogue.phases for a in p.artefacts]
    assert len(prefixes) == len(set(prefixes))
    for short in prefixes:
        assert not any(long != short and long.startswith(short + "-") for long in prefixes), short


def test_prefixes_work_with_the_id_allocator_from_s01(catalogue, store, project):
    # Allocate three of every prefix in one project: the numbering must stay per-prefix, never shared.
    for phase in catalogue.phases:
        for item in phase.artefacts:
            ids = [
                store.artefacts.create(
                    project.id, artefact_type=item.key, phase_key=phase.key, title=item.name,
                    actor="system", prefix=item.id_prefix,
                ).id
                for _ in range(3)
            ]
            assert ids == [f"{item.id_prefix}-00{n}" for n in (1, 2, 3)], item.key


def test_dependencies_stay_inside_their_phase_and_have_no_loops(catalogue):
    for phase in catalogue.phases:
        keys = {a.key for a in phase.artefacts}
        for item in phase.artefacts:
            assert set(item.after) <= keys and item.key not in item.after


def test_the_demo_critical_path_artefacts_are_required(catalogue):
    required = {a.key for p in catalogue.phases for a in p.artefacts if a.required}
    for key in ("project_charter", "functional_requirements", "non_functional_requirements", "user_journey",
                "high_level_design", "low_level_design", "build_instructions",
                "deployment_plan", "release_notes", "runbook", "hypercare_plan"):
        assert key in required, key
    for key in ("handover_signoff", "support_guide", "user_stories", "hifi_wireframes"):
        assert key not in required, key


def test_phase_lookup(catalogue):
    assert catalogue.phase("build").name == "Build & Test"
    assert catalogue.phase("build").artefact("build_instructions").role == "solution_architect"
    assert catalogue.has_phase("deploy") and not catalogue.has_phase("nope")
    with pytest.raises(KeyError):
        catalogue.phase("nope")
    with pytest.raises(KeyError):
        catalogue.phase("build").artefact("nope")


# ---- the loader refuses bad definitions --------------------------------------------------

def good_phase() -> dict:
    return {
        "key": "demo", "order": 0, "name": "Demo", "summary": "s", "approver": "someone",
        "artefacts": [
            {"key": "a", "name": "A", "id_prefix": "DEM-A", "role": "orchestrator", "required": True, "description": "d"},
            {"key": "b", "name": "B", "id_prefix": "DEM-B", "role": "orchestrator", "after": ["a"], "description": "d"},
        ],
    }


def parse(data) -> PhaseDef:
    return parse_phase(data, "demo.yaml", ROLES)


def test_a_good_definition_parses():
    phase = parse(good_phase())
    assert [a.key for a in phase.artefacts] == ["a", "b"] and phase.artefacts[1].after == ("a",)


@pytest.mark.parametrize(
    "mutate, fragment",
    [
        (lambda d: d.update(surprise=1), "unknown field"),
        (lambda d: d["artefacts"][0].update(surprise=1), "unknown field"),
        (lambda d: d["artefacts"][0].update(requierd=True), "unknown field"),  # the classic typo
        (lambda d: d.pop("key"), "missing 'key'"),
        (lambda d: d.pop("name"), "missing 'name'"),
        (lambda d: d.pop("approver"), "missing 'approver'"),
        (lambda d: d.update(key="Not-Snake"), "lower_snake_case"),
        (lambda d: d.update(order=-1), "whole number"),
        (lambda d: d.update(order="one"), "whole number"),
        (lambda d: d.update(order=True), "whole number"),
        (lambda d: d.update(artefacts=[]), "at least one artefact"),
        (lambda d: d.update(artefacts="a"), "at least one artefact"),
        (lambda d: d["artefacts"][0].pop("role"), "missing 'role'"),
        (lambda d: d["artefacts"][0].pop("id_prefix"), "missing 'id_prefix'"),
        (lambda d: d["artefacts"][0].update(role="not_a_role"), "not in routing.yaml"),
        (lambda d: d["artefacts"][0].update(id_prefix="lower-case"), "must look like"),
        (lambda d: d["artefacts"][0].update(id_prefix="NODASH"), "must look like"),
        (lambda d: d["artefacts"][0].update(key="Bad Key"), "lower_snake_case"),
        (lambda d: d["artefacts"][0].update(required="yes"), "true or false"),
        (lambda d: d["artefacts"][1].update(after="a"), "list of artefact keys"),
        (lambda d: d["artefacts"][1].update(after=["a", "a"]), "twice"),
        (lambda d: d["artefacts"][1].update(after=["ghost"]), "not in this phase"),
        (lambda d: d["artefacts"][1].update(after=["b"]), "after itself"),
        (lambda d: d["artefacts"][1].update(key="a", id_prefix="DEM-C"), "appears twice"),
        (lambda d: d["artefacts"][0].update(required=False), "at least one required"),
    ],
)
def test_each_rule_has_a_clear_error_naming_the_file(mutate, fragment):
    data = good_phase()
    mutate(data)
    with pytest.raises(CatalogueError, match=fragment) as exc:
        parse(data)
    assert "demo.yaml" in str(exc.value)


def test_errors_name_the_artefact():
    data = good_phase()
    data["artefacts"][1]["after"] = ["ghost"]
    with pytest.raises(CatalogueError, match="artefact 'b'"):
        parse(data)


def test_a_dependency_loop_is_named():
    data = good_phase()
    data["artefacts"][0]["after"] = ["b"]
    with pytest.raises(CatalogueError, match="loop: a -> b -> a|loop: b -> a -> b"):
        parse(data)
    data = good_phase()
    data["artefacts"].append({"key": "c", "name": "C", "id_prefix": "DEM-C", "role": "orchestrator", "after": ["b"]})
    data["artefacts"][0]["after"] = ["c"]
    with pytest.raises(CatalogueError, match="loop"):
        parse(data)


@pytest.mark.parametrize("not_a_mapping", [["a"], "text", 3, None])
def test_a_file_that_is_not_a_mapping_is_rejected(not_a_mapping):
    with pytest.raises(CatalogueError, match="expected a mapping"):
        parse(not_a_mapping)


def phase_with(order: int, key: str, prefix: str) -> PhaseDef:
    data = good_phase()
    data.update(order=order, key=key)
    data["artefacts"][0]["id_prefix"] = prefix
    data["artefacts"][1]["id_prefix"] = prefix + "X"
    return parse(data)


def test_orders_must_be_unique_and_gapless():
    for orders in ([0, 2], [1, 2], [0, 0]):
        phases = [phase_with(o, f"p{i}", f"P{i}-A") for i, o in enumerate(orders)]
        with pytest.raises(CatalogueError, match="orders must run"):
            build_catalogue(phases)
    assert build_catalogue([phase_with(1, "b", "B-A"), phase_with(0, "a", "A-A")]).phase_keys == ("a", "b")


def test_a_phase_key_used_twice_is_rejected():
    with pytest.raises(CatalogueError, match="more than one file"):
        build_catalogue([phase_with(0, "same", "A-A"), phase_with(1, "same", "B-A")])


def test_a_prefix_used_by_two_artefacts_is_rejected():
    with pytest.raises(CatalogueError, match="used by both"):
        build_catalogue([phase_with(0, "a", "SAME-A"), phase_with(1, "b", "SAME-A")])


def test_a_prefix_that_is_the_start_of_another_is_rejected():
    """REQ-F and REQ-F-X would share numbering in the ID allocator."""
    first = phase_with(0, "a", "REQ-F")
    second = parse({**good_phase(), "key": "b", "order": 1, "artefacts": [
        {"key": "c", "name": "C", "id_prefix": "REQ-F-X", "role": "orchestrator", "required": True},
    ]})
    with pytest.raises(CatalogueError, match="start of"):
        build_catalogue([first, second])


def test_an_empty_catalogue_is_rejected():
    with pytest.raises(CatalogueError, match="no phase definitions"):
        build_catalogue([])


# ---- reading the files -----------------------------------------------------------------

def write_phase(folder: Path, name: str, data) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(data if isinstance(data, str) else yaml.safe_dump(data), encoding="utf-8")


def test_loading_a_folder_end_to_end(tmp_path):
    write_phase(tmp_path, "00.yaml", {**good_phase(), "key": "p0", "order": 0})
    other = copy.deepcopy(good_phase())
    other.update(key="p1", order=1)
    other["artefacts"][0]["id_prefix"], other["artefacts"][1]["id_prefix"] = "ONE-A", "ONE-B"
    write_phase(tmp_path, "01.yaml", other)
    assert load_catalogue(ROLES, tmp_path).phase_keys == ("p0", "p1")


def test_a_duplicate_yaml_key_is_an_error_not_a_silent_overwrite(tmp_path):
    write_phase(tmp_path, "00.yaml", "key: a\nkey: b\norder: 0\nname: N\napprover: x\nartefacts: []\n")
    with pytest.raises(CatalogueError, match="appears twice") as exc:
        load_catalogue(ROLES, tmp_path)
    assert "00.yaml" in str(exc.value)


def test_invalid_yaml_names_the_file_and_line_without_echoing_content(tmp_path):
    write_phase(tmp_path, "00.yaml", "key: ok\nname: [unclosed SECRET-CONTENT\n")
    with pytest.raises(CatalogueError) as exc:
        load_catalogue(ROLES, tmp_path)
    assert "00.yaml" in str(exc.value) and "line" in str(exc.value) and "SECRET-CONTENT" not in str(exc.value)


def test_a_missing_or_empty_folder_is_an_error(tmp_path):
    with pytest.raises(CatalogueError, match="does not exist"):
        load_catalogue(ROLES, tmp_path / "nowhere")
    with pytest.raises(CatalogueError, match="no phase definitions"):
        load_catalogue(ROLES, tmp_path)


def test_other_files_in_the_folder_are_ignored(tmp_path):
    write_phase(tmp_path, "00.yaml", {**good_phase(), "key": "p0", "order": 0})
    (tmp_path / "notes.txt").write_text("not yaml: [")
    (tmp_path / "README.md").write_text("# not a phase")
    assert load_catalogue(ROLES, tmp_path).phase_keys == ("p0",)


def test_the_shipped_folder_has_exactly_the_seven_files():
    assert sorted(p.name for p in DEFINITIONS_DIR.glob("*.yaml")) == [
        "00-setup.yaml", "01-requirements.yaml", "02-design.yaml", "03-architecture.yaml",
        "04-build.yaml", "05-deploy.yaml", "06-handover.yaml",
    ]


# ---- S21a: an artefact that is part of the design but not in use ---------------------------------------------------------

def off(data, key="b", reason="Not enabled. Not wanted yet."):
    data = copy.deepcopy(data)
    item = next(a for a in data["artefacts"] if a["key"] == key)
    item["enabled"] = False
    if reason is not None:
        item["disabled_reason"] = reason
    item.pop("required", None)
    return data


def test_the_two_deploy_artefacts_that_are_not_wanted_are_switched_off_with_their_reasons(catalogue):
    deploy = catalogue.phase("deploy")
    assert [a.key for a in deploy.artefacts if not a.enabled] == ["infrastructure_as_code", "cicd_pipeline"]
    assert all(a.disabled_reason.startswith("Not enabled.") and "switched on later" in a.disabled_reason and not a.required for a in deploy.artefacts if not a.enabled)
    assert [a.key for a in deploy.artefacts if a.enabled] == ["deployment_plan", "release_notes", "deployment_verification"]
    assert all(a.enabled and a.disabled_reason == "" for p in catalogue.phases if p.key not in ("deploy", "handover") for a in p.artefacts)            # nothing else changes (the Handover phase has its own three, below)


def test_an_artefact_is_enabled_by_default_and_a_switched_off_one_keeps_its_reason():
    phase = parse(good_phase())
    assert all(a.enabled and a.disabled_reason == "" for a in phase.artefacts)
    parsed = parse(off(good_phase()))
    assert [(a.key, a.enabled, a.disabled_reason) for a in parsed.artefacts] == [("a", True, ""), ("b", False, "Not enabled. Not wanted yet.")]


@pytest.mark.parametrize("change,words", [
    (lambda d: off(d, reason=None), "needs a 'disabled_reason'"),
    (lambda d: off(d, reason="   "), "non-blank"),
    (lambda d: {**d, "artefacts": [d["artefacts"][0], {**d["artefacts"][1], "disabled_reason": "why"}]}, "only for an artefact with 'enabled: false'"),
    (lambda d: {**d, "artefacts": [d["artefacts"][0], {**d["artefacts"][1], "enabled": "no"}]}, "'enabled' must be true or false"),
    (lambda d: {**d, "artefacts": [d["artefacts"][0], {**d["artefacts"][1], "enabled": False, "disabled_reason": "x", "required": True}]}, "cannot also be 'required: true'"),
])
def test_a_badly_switched_off_artefact_is_an_error_that_names_the_artefact(change, words):
    with pytest.raises(CatalogueError, match=words) as caught:
        parse(change(good_phase()))
    assert "demo.yaml" in str(caught.value)


def test_a_phase_whose_only_required_artefact_is_switched_off_is_refused_and_so_is_waiting_for_one_that_never_runs():
    data = good_phase()
    data["artefacts"][0] = {**data["artefacts"][0], "required": False, "enabled": False, "disabled_reason": "x"}
    with pytest.raises(CatalogueError, match="needs at least one required artefact"):
        parse(data)
    waits = good_phase()
    waits["artefacts"][0] = {"key": "a", "name": "A", "id_prefix": "DEM-A", "role": "orchestrator", "enabled": False, "disabled_reason": "x", "description": "d"}
    waits["artefacts"].append({"key": "c", "name": "C", "id_prefix": "DEM-C", "role": "orchestrator", "required": True, "after": ["a"], "description": "d"})
    with pytest.raises(CatalogueError, match="which is not enabled; an enabled artefact cannot wait for one that never runs"):
        parse(waits)


def test_a_switched_off_artefact_may_wait_for_an_enabled_one():
    data = good_phase()
    data["artefacts"][1] = {**data["artefacts"][1], "enabled": False, "disabled_reason": "x", "after": ["a"]}
    assert parse(data).artefacts[1].after == ("a",)



def test_a_switched_off_artefact_may_wait_for_another_switched_off_one_but_a_working_one_may_not_wait_for_either():
    data = good_phase()
    data["artefacts"].append({"key": "c", "name": "C", "id_prefix": "DEM-C", "role": "orchestrator", "enabled": False, "disabled_reason": "x", "after": ["b"], "description": "d"})
    data["artefacts"][1] = {**data["artefacts"][1], "enabled": False, "disabled_reason": "x"}
    assert [(a.key, a.enabled, a.after) for a in parse(data).artefacts] == [("a", True, ()), ("b", False, ("a",)), ("c", False, ("b",))]
    data["artefacts"].append({"key": "d", "name": "D", "id_prefix": "DEM-D", "role": "orchestrator", "required": True, "after": ["c"], "description": "d"})
    with pytest.raises(CatalogueError, match="'d' comes after 'c', which is not enabled"):
        parse(data)


# ---- S21: an artefact a person does by hand (kind: checklist) ----------------------------------------------------------------------------------

def hand(**extra):
    data = good_phase()
    data["artefacts"].append({"key": "c", "name": "C", "id_prefix": "DEM-C", "kind": "checklist", "description": "d", **extra})
    return data


def test_an_artefact_done_by_hand_has_no_role_is_never_required_and_defaults_to_written_for_the_others():
    parsed = parse(hand())
    c = next(a for a in parsed.artefacts if a.key == "c")
    assert (c.kind, c.by_hand, c.role, c.required, c.after, c.enabled) == ("checklist", True, "", False, (), True)
    assert all(a.kind == "written" and not a.by_hand for a in parsed.artefacts if a.key != "c")


@pytest.mark.parametrize("extra,word", [
    ({"role": "orchestrator"}, "has no 'role'"), ({"required": True}, "has no 'required'"), ({"after": ["a"]}, "has no 'after'"),
    ({"enabled": False, "disabled_reason": "x"}, "has no 'disabled_reason'"),
])
def test_a_by_hand_artefact_with_a_role_a_requirement_a_wait_or_a_switch_off_is_refused_naming_the_artefact(extra, word):
    with pytest.raises(CatalogueError, match=word) as caught:
        parse(hand(**extra))
    assert "demo.yaml" in str(caught.value) and "'c'" in str(caught.value) and "done by hand" in str(caught.value)


def test_a_by_hand_artefact_cannot_be_switched_off_by_any_route():
    for extra in ({"enabled": False}, {"enabled": False, "disabled_reason": "x"}):
        with pytest.raises(CatalogueError):
            parse(hand(**extra))


def test_a_kind_other_than_written_or_checklist_is_refused_with_the_choices():
    with pytest.raises(CatalogueError, match=r"'kind' must be one of \['written', 'checklist'\], got 'other'"):
        parse(hand(kind="other"))
    with pytest.raises(CatalogueError, match="'kind' must be one of"):
        parse(hand(kind=""))


def test_nothing_can_wait_for_an_artefact_done_by_hand():
    data = hand()
    data["artefacts"].append({"key": "e", "name": "E", "id_prefix": "DEM-E", "role": "orchestrator", "required": True, "after": ["c"], "description": "d"})
    with pytest.raises(CatalogueError, match="'e' comes after 'c', which is done by hand and never runs; nothing can wait for it"):
        parse(data)


def test_a_role_is_still_needed_and_checked_for_every_artefact_that_is_written():
    data = good_phase()
    data["artefacts"][1] = {k: v for k, v in data["artefacts"][1].items() if k != "role"}
    with pytest.raises(CatalogueError, match="missing 'role'"):
        parse(data)
    data = good_phase()
    data["artefacts"][1]["role"] = "no_such_role"
    with pytest.raises(CatalogueError, match="uses role 'no_such_role', which is not in routing.yaml"):
        parse(data)


def test_the_three_handover_artefacts_that_are_parked_are_switched_off_with_their_reasons(catalogue):
    handover = catalogue.phase("handover")
    assert [a.key for a in handover.artefacts if not a.enabled] == ["support_guide", "slos_alerts", "kt_pack"]
    assert all(a.disabled_reason.startswith("Not enabled.") and "switched on later" in a.disabled_reason and not a.required and not a.after for a in handover.artefacts if not a.enabled)
    assert [(a.key, a.required, a.after) for a in handover.artefacts if a.enabled] == [("runbook", True, ()), ("hypercare_plan", True, ("runbook",)), ("handover_signoff", False, ())]
    assert [a.key for a in handover.artefacts if a.by_hand] == ["handover_signoff"] and handover.artefact("handover_signoff").role in ("", None)


def test_the_shipped_catalogue_has_exactly_two_artefacts_done_by_hand(catalogue):
    assert [(p.key, a.key) for p in catalogue.phases for a in p.artefacts if a.by_hand] == [("deploy", "deployment_verification"), ("handover", "handover_signoff")] and catalogue.by_hand_count == 2

