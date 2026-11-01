"""Output limits per agent role, the cut-off message, and the cost cap (2026-10-31, after the user's first live Design run).

What happened: Gemini's wireframe replies were cut off at the 8,000-token output limit, five times in seven calls, while the replies themselves
were far shorter than that (one wrote ~300 visible tokens and was billed 7,996). Gemini spends output tokens on reasoning it never shows.
"""
from __future__ import annotations

import pytest

from app.agents.reply import CUT_OFF_BEFORE_CLOSING, parse_reply
from app.agents.runtime import AgentRuntime
from app.config import Settings
from app.llm.types import ProviderResponse, Usage

from .test_agent_runtime import CHARTER_SECTIONS, catalogue, ok, reply, rig  # noqa: F401  (fixtures, imported by name so this file can use them)

pytestmark = pytest.mark.anyio


# ---- the setting -----------------------------------------------------------------------------------------------------------------------

def test_the_ux_designer_gets_a_larger_limit_by_default_and_everyone_else_the_general_one():
    s = Settings(_env_file=None)
    assert s.output_tokens_for("ux_designer") == 24000
    for role in ("orchestrator", "requirements_analyst", "backlog_splitter", "security_reviewer", "something_new"):
        assert s.output_tokens_for(role) == s.agent_max_output_tokens == 8000


def test_a_role_limit_can_be_changed_added_or_removed():
    assert Settings(_env_file=None, agent_output_tokens_by_role="ux_designer=30000").output_tokens_for("ux_designer") == 30000
    two = Settings(_env_file=None, agent_output_tokens_by_role="ux_designer=24000, solution_architect=16000")
    assert (two.output_tokens_for("ux_designer"), two.output_tokens_for("solution_architect"), two.output_tokens_for("orchestrator")) == (24000, 16000, 8000)
    assert Settings(_env_file=None, agent_output_tokens_by_role="").output_tokens_for("ux_designer") == 8000          # blank removes the override
    assert Settings(_env_file=None, agent_output_tokens_by_role=" , ,").output_tokens_for("ux_designer") == 8000       # stray commas are harmless


def test_changing_the_general_limit_does_not_change_a_role_with_its_own():
    s = Settings(_env_file=None, agent_max_output_tokens=4000)
    assert s.output_tokens_for("ux_designer") == 24000 and s.output_tokens_for("orchestrator") == 4000


@pytest.mark.parametrize("bad, fragment", [
    ("ux_designer", "look like"), ("ux_designer=", "look like"), ("=24000", "look like"), ("ux_designer=abc", "look like"), ("ux_designer=-5", "look like"),
    ("UX Designer=24000", "look like"), ("ux_designer=255", "between 256 and 64000"), ("ux_designer=64001", "between 256 and 64000"),
    ("ux_designer=24000,ux_designer=1000", "twice"),
])
def test_a_malformed_role_limit_stops_start_up_with_a_sentence(bad, fragment):
    with pytest.raises(ValueError, match=fragment):
        Settings(_env_file=None, agent_output_tokens_by_role=bad)


def test_the_bounds_are_inclusive():
    assert Settings(_env_file=None, agent_output_tokens_by_role="ux_designer=256").output_tokens_for("ux_designer") == 256
    assert Settings(_env_file=None, agent_output_tokens_by_role="ux_designer=64000").output_tokens_for("ux_designer") == 64000


# ---- the limit reaches the model call ----------------------------------------------------------------------------------------------------

async def test_the_request_sent_for_a_role_uses_the_general_limit_when_it_has_no_own(rig, store, project):
    runtime, provider, _ = rig(agent_max_output_tokens=7000)
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")           # the charter's role is `orchestrator`, which has no override
    assert provider.calls[0].request.max_tokens == 7000


async def test_the_request_sent_for_a_role_uses_that_roles_own_limit(rig, store, project):
    runtime, provider, _ = rig(agent_max_output_tokens=7000, agent_output_tokens_by_role="orchestrator=12000")
    provider.queue("m-sonnet", ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    assert provider.calls[0].request.max_tokens == 12000


def test_the_runtime_asks_the_settings_for_the_roles_limit_and_nothing_else():
    import inspect

    source = inspect.getsource(AgentRuntime.run)
    assert "self.settings.output_tokens_for(skill.artefact.role)" in source and "agent_max_output_tokens" not in source


# ---- a reply cut off before its closing tag ---------------------------------------------------------------------------------------------------

async def test_a_reply_cut_off_before_it_closes_is_told_the_length_limit_ended_it_not_only_that_a_tag_is_missing(rig, store, project):
    runtime, provider, _ = rig()
    cut = ProviderResponse("<artefact>\n## Purpose\nbegun", Usage(1000, 7996), "length")           # never closed, and the provider says why
    provider.queue("m-sonnet", cut, ok(CHARTER_SECTIONS))
    assert (await runtime.run(project.id, "project_charter")).attempts == 2
    sent_back = provider.calls[1].request.messages[-1].content
    assert CUT_OFF_BEFORE_CLOSING in sent_back and "output limit" in sent_back and "shorter" in sent_back
    assert "never closed" not in sent_back


async def test_a_reply_that_stops_normally_but_forgot_its_closing_tag_is_still_told_so(rig, store, project):
    runtime, provider, _ = rig()
    forgot = ProviderResponse("<artefact>\n## Purpose\nbegun", Usage(1000, 300), "stop")              # finished by itself, just never closed
    provider.queue("m-sonnet", forgot, ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    sent_back = provider.calls[1].request.messages[-1].content
    assert "never closed" in sent_back and "output limit" not in sent_back


@pytest.mark.parametrize("finish", ["length", "max_tokens"])
async def test_both_spellings_of_a_length_stop_count_as_a_cut_off(rig, store, project, finish):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", ProviderResponse("<artefact>\n## Purpose\nbegun", Usage(1000, 100), finish), ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    assert "output limit" in provider.calls[1].request.messages[-1].content


async def test_a_cut_off_reply_with_no_artefact_tag_at_all_keeps_its_own_message(rig, store, project):
    runtime, provider, _ = rig()
    provider.queue("m-sonnet", ProviderResponse("I will now write it", Usage(1000, 100), "length"), ok(CHARTER_SECTIONS))
    await runtime.run(project.id, "project_charter")
    sent_back = provider.calls[1].request.messages[-1].content
    assert "no <artefact> block was found" in sent_back or "output limit" in sent_back          # whichever the code chooses, the model is told something it can act on


def test_the_cut_off_sentence_is_plain_and_names_the_fix():
    assert CUT_OFF_BEFORE_CLOSING.startswith("the reply was cut off by the output limit")
    assert "shorter" in CUT_OFF_BEFORE_CLOSING and "</artefact>" in CUT_OFF_BEFORE_CLOSING


# ---- the cost cap -----------------------------------------------------------------------------------------------------------------------------

def test_the_default_cost_cap_for_a_run_is_five_dollars():
    assert Settings(_env_file=None).run_max_cost_usd == 5.0


def test_the_cost_cap_can_still_be_changed_or_switched_off():
    assert Settings(_env_file=None, run_max_cost_usd=12.5).run_max_cost_usd == 12.5
    assert Settings(_env_file=None, run_max_cost_usd=0).run_max_cost_usd == 0


# ---- the upstream limit (raised 2026-10-31: the Low-level design reads 32,381 characters in the user's project and was refused at 24,000) ----------------

def test_the_upstream_limit_defaults_to_one_hundred_thousand_characters_and_stays_bounded():
    assert Settings(_env_file=None).agent_upstream_max_chars == 100_000          # a literal: a changed default must be a decision, not an accident
    assert Settings(_env_file=None, agent_upstream_max_chars=400_000).agent_upstream_max_chars == 400_000
    for bad in (999, 400_001):
        with pytest.raises(ValueError):
            Settings(_env_file=None, agent_upstream_max_chars=bad)


def test_the_lowlevel_design_size_that_was_refused_before_now_fits_and_the_limit_still_refuses_something_larger():
    refused_before = 32_381
    assert refused_before > 24_000 and refused_before <= Settings(_env_file=None).agent_upstream_max_chars
    assert 100_001 > Settings(_env_file=None).agent_upstream_max_chars
