from __future__ import annotations

import pytest

from app.llm.errors import RoutingConfigError
from app.llm.families import SLOT_FAMILY, SLOT_NAMES, family_of_model, fallback_env, model_env, owner_slot_name
from app.llm.pricing import cost_usd, pricing_slot
from app.llm.routing import REQUIRED_ROLES, ROUTING_FILE, Routing
from app.llm.types import Usage

ALL_SLOTS = dict(
    ibm_ica_model_id="model-sonnet", ibm_ica_haiku_model_id="model-haiku",
    ibm_ica_openai_model_id="model-openai", ibm_ica_gemini_model_id="model-gemini",
    ibm_ica_price_input_per_mtok="2", ibm_ica_price_output_per_mtok="10",
    ibm_ica_haiku_price_input_per_mtok="0.1", ibm_ica_haiku_price_output_per_mtok="0.5",
    ibm_ica_openai_price_input_per_mtok="4", ibm_ica_openai_price_output_per_mtok="20",
    ibm_ica_gemini_price_input_per_mtok="0.75", ibm_ica_gemini_price_output_per_mtok="3.75",
)


# ---- families --------------------------------------------------------------

def test_slot_families():
    assert SLOT_FAMILY == {"sonnet": "anthropic", "haiku": "anthropic", "openai": "openai", "gemini": "google"}
    assert SLOT_NAMES == ("sonnet", "haiku", "openai", "gemini")


def test_env_variable_names_match_the_dotenv_convention():
    assert model_env("sonnet") == "IBM_ICA_MODEL_ID"
    assert model_env("haiku") == "IBM_ICA_HAIKU_MODEL_ID"
    assert fallback_env("sonnet") == "IBM_ICA_FALLBACK_MODEL_ID"
    assert fallback_env("gemini") == "IBM_ICA_GEMINI_FALLBACK_MODEL_ID"


def test_family_comes_from_the_owning_slot(make_settings):
    slots = make_settings(**ALL_SLOTS).slots
    assert family_of_model("model-sonnet", slots) == "anthropic"
    assert family_of_model("model-haiku", slots) == "anthropic"
    assert family_of_model("model-openai", slots) == "openai"
    assert family_of_model("model-gemini", slots) == "google"
    assert owner_slot_name("model-gemini", slots) == "gemini"


def test_family_is_inferred_from_the_name_when_no_slot_owns_it(make_settings):
    slots = make_settings().slots
    for name, family in [
        ("claude-opus-5", "anthropic"), ("gpt-6.1-terra", "openai"), ("chatgpt-4o", "openai"),
        ("o3-mini", "openai"), ("gemini-2.5-pro", "google"), ("llama-4", "unknown"),
        ("", "unknown"), ("omega", "unknown"),
    ]:
        assert family_of_model(name, slots) == family, name


def test_a_slot_that_owns_a_model_beats_the_name(make_settings):
    # A Gemini slot pointing at a model called "claude-x" is still the Google slot's model.
    slots = make_settings(ibm_ica_gemini_model_id="claude-x").slots
    assert family_of_model("claude-x", slots) == "google"


# ---- pricing ---------------------------------------------------------------

def test_cost_maths(make_settings):
    sonnet = make_settings(**ALL_SLOTS).slots["sonnet"]
    assert cost_usd(sonnet, Usage(1000, 200)) == pytest.approx(0.004)
    assert cost_usd(sonnet, Usage(0, 0)) == 0.0


def test_unknown_cost_is_none_never_zero(make_settings):
    s = make_settings(**{**ALL_SLOTS, "ibm_ica_gemini_price_input_per_mtok": "", "ibm_ica_gemini_price_output_per_mtok": ""})
    gemini = s.slots["gemini"]
    assert cost_usd(gemini, Usage(1000, 200)) is None
    assert cost_usd(s.slots["sonnet"], None) is None  # provider reported no usage
    assert cost_usd(None, Usage(1, 1)) is None


def test_half_priced_slot_has_no_cost(make_settings):
    s = make_settings(**{**ALL_SLOTS, "ibm_ica_haiku_price_output_per_mtok": ""})
    assert cost_usd(s.slots["haiku"], Usage(10, 10)) is None


def test_price_comes_from_the_model_that_served_the_call(make_settings):
    slots = make_settings(**ALL_SLOTS).slots
    assert pricing_slot("model-sonnet", slots).name == "sonnet"
    assert pricing_slot("model-openai", slots).name == "openai"
    assert pricing_slot("some-other-model", slots) is None
    assert pricing_slot("", slots) is None


# ---- routing file ----------------------------------------------------------

def test_the_shipped_routing_file_is_valid():
    routing = Routing.load()
    assert set(routing.roles) == set(REQUIRED_ROLES)
    assert len(REQUIRED_ROLES) == 14
    assert routing.reviewer_default == "sonnet"


def test_every_slot_is_the_default_for_at_least_one_role():
    """O2: a normal run uses all four model families."""
    assert set(Routing.load().roles.values()) == set(SLOT_NAMES)


def test_known_assignments():
    roles = Routing.load().roles
    assert roles["requirements_analyst"] == "sonnet"
    assert roles["backlog_splitter"] == "haiku"
    assert roles["backend_developer"] == "openai"
    assert roles["ux_designer"] == "gemini"


def good() -> dict:
    return {
        "roles": {role: "sonnet" for role in REQUIRED_ROLES},
        "reviewer": {"default": "sonnet", "alternatives": ["gemini", "openai", "haiku"]},
    }


def test_good_data_loads():
    assert Routing.from_dict(good()).reviewer_alternatives == ("gemini", "openai", "haiku")


@pytest.mark.parametrize(
    "mutate, fragment",
    [
        (lambda d: d["roles"].update(orchestrator="mistral"), "unknown slot"),
        (lambda d: d["roles"].update(cleaner="sonnet"), "unknown role"),
        (lambda d: d["roles"].pop("orchestrator"), "missing role"),
        (lambda d: d.__setitem__("roles", ["sonnet"]), "'roles' must be a mapping"),
        (lambda d: d.pop("reviewer"), "'reviewer' must be a mapping"),
        (lambda d: d["reviewer"].update(default="nobody"), "reviewer default"),
        (lambda d: d["reviewer"].update(alternatives="gemini"), "must be a list"),
        (lambda d: d["reviewer"].update(alternatives=["gemini", "nobody"]), "reviewer alternative"),
        (lambda d: d["reviewer"].update(alternatives=["gemini", "gemini"]), "duplicate"),
        (lambda d: d["reviewer"].update(alternatives=["sonnet", "gemini"]), "also appears"),
    ],
)
def test_bad_routing_data_is_rejected_with_a_clear_message(mutate, fragment):
    data = good()
    mutate(data)
    with pytest.raises(RoutingConfigError, match=fragment):
        Routing.from_dict(data)


def test_non_mapping_and_unreadable_files_are_rejected(tmp_path):
    with pytest.raises(RoutingConfigError):
        Routing.from_dict(["not", "a", "mapping"])
    with pytest.raises(RoutingConfigError, match="cannot read"):
        Routing.load(tmp_path / "missing.yaml")
    broken = tmp_path / "broken.yaml"
    broken.write_text("roles: [unclosed")
    with pytest.raises(RoutingConfigError, match="not valid YAML"):
        Routing.load(broken)


def test_the_routing_file_sits_next_to_the_code():
    assert ROUTING_FILE.name == "routing.yaml" and ROUTING_FILE.exists()


# ---- overrides -------------------------------------------------------------

def test_override_beats_the_file_and_none_leaves_it():
    routing = Routing.load()
    assert routing.slot_for("requirements_analyst") == "sonnet"
    assert routing.slot_for("requirements_analyst", {"requirements_analyst": "gemini"}) == "gemini"
    assert routing.slot_for("requirements_analyst", {"ux_designer": "haiku"}) == "sonnet"
    assert routing.slot_for("requirements_analyst", {}) == "sonnet"
    assert routing.slot_for("requirements_analyst", None) == "sonnet"


def test_bad_overrides_and_unknown_roles_are_rejected():
    routing = Routing.load()
    with pytest.raises(RoutingConfigError, match="unknown role"):
        routing.slot_for("orchestrator", {"janitor": "sonnet"})
    with pytest.raises(RoutingConfigError, match="unknown slot"):
        routing.slot_for("orchestrator", {"orchestrator": "mistral"})
    with pytest.raises(RoutingConfigError, match="unknown role"):
        routing.slot_for("janitor")
