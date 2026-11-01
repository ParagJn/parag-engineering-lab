from __future__ import annotations

import pytest

from app.llm.errors import (
    AuthenticationFailed,
    ContentFilterBlocked,
    LLMCallFailed,
    ReviewerUnavailable,
    TransientProviderError,
)
from app.llm.types import LLMRequest, ProviderResponse, Usage

from .test_gateway import MODELS, Rig, make_rig, ok, rig, transient  # noqa: F401  (fixtures)

pytestmark = pytest.mark.anyio


def review_req(rig: Rig) -> LLMRequest:
    return rig.req("security_reviewer", "review this artefact")


def slots_of(options) -> list[str]:
    return [o.slot for o in options]


# ---- options ---------------------------------------------------------------

def test_options_list_independent_families_first(rig):
    options = rig.gateway.review_options("model-openai")  # OpenAI author
    assert slots_of(options) == ["sonnet", "gemini", "haiku", "openai"]
    assert [o.independent for o in options] == [True, True, True, False]

    options = rig.gateway.review_options("model-sonnet")  # Anthropic author
    assert slots_of(options) == ["gemini", "openai", "sonnet", "haiku"]
    assert [o.independent for o in options] == [True, True, False, False]


def test_options_carry_family_model_and_prices(rig):
    gemini = next(o for o in rig.gateway.review_options("model-sonnet") if o.slot == "gemini")
    assert (gemini.model_id, gemini.family, gemini.independent) == ("model-gemini", "google", True)
    assert (gemini.price_input, gemini.price_output, gemini.priced) == (0.75, 3.75, True)


def test_options_drop_excluded_and_unconfigured_slots(make_rig):
    rig = make_rig(ibm_ica_gemini_model_id="")
    assert "gemini" not in slots_of(rig.gateway.review_options("model-openai"))
    rig = make_rig()
    assert "sonnet" not in slots_of(rig.gateway.review_options("model-openai", exclude=["sonnet"]))


def test_options_drop_slots_that_share_an_excluded_slots_model(make_rig):
    rig = make_rig(
        ibm_ica_haiku_model_id="model-sonnet",
        ibm_ica_haiku_price_input_per_mtok="2", ibm_ica_haiku_price_output_per_mtok="10",
    )
    assert "haiku" not in slots_of(rig.gateway.review_options("model-openai", exclude=["sonnet"]))


def test_unknown_author_family_gives_unknown_independence_and_keeps_configured_order(rig):
    options = rig.gateway.review_options("some-local-model")
    assert [o.independent for o in options] == [None] * 4
    assert slots_of(options) == ["sonnet", "gemini", "openai", "haiku"]


# ---- independence ----------------------------------------------------------

async def test_independence_depends_on_who_wrote_it(rig):
    rig.provider.default = ok()
    result = await rig.gateway.complete(rig.req("security_reviewer"))  # served by Sonnet
    verdicts = {
        author: rig.gateway.independence(author, result).verdict
        for author in ("model-openai", "model-gemini", "model-sonnet", "model-haiku", "mystery-model")
    }
    assert verdicts == {
        "model-openai": "independent", "model-gemini": "independent",
        "model-sonnet": "same_family", "model-haiku": "same_family",
        "mystery-model": "unverified",
    }


async def test_a_reviewer_that_fell_back_into_the_authors_family_is_reported_as_such(make_rig):
    rig = make_rig(ibm_ica_haiku_model_id="")
    rig.provider.queue("model-sonnet", ok())
    result = await rig.gateway.complete(rig.req("backlog_splitter"))  # Haiku slot blank -> Sonnet
    verdict = rig.gateway.independence("model-sonnet", result)
    assert (verdict.verdict, verdict.fell_back) == ("same_family", True)


async def test_the_authors_family_comes_from_the_model_that_actually_wrote_it(rig):
    # OpenAI was asked but Sonnet served it, so the artefact is Anthropic-authored.
    rig.provider.queue("model-openai", transient(), transient())
    rig.provider.queue("model-sonnet", ok())
    written = await rig.gateway.complete(rig.req("backend_developer"))
    assert written.slot == "openai" and written.served_model == "model-sonnet"

    rig.provider.queue("model-sonnet", ok("review"))
    outcome = await rig.gateway.review(review_req(rig), author_model=written.served_model)
    assert outcome.independence.verdict == "same_family"


# ---- review() --------------------------------------------------------------

async def test_sonnet_reviews_by_default(rig):
    rig.provider.queue("model-sonnet", ok("looks fine"))
    outcome = await rig.gateway.review(review_req(rig), author_model="model-openai")
    assert outcome.result.served_model == "model-sonnet" and outcome.result.text == "looks fine"
    assert outcome.independence.verdict == "independent"
    assert (outcome.independence.author_family, outcome.independence.reviewer_family) == ("openai", "anthropic")


async def test_sonnet_reviewing_sonnet_work_is_labelled_same_family_not_hidden(rig):
    rig.provider.queue("model-sonnet", ok())
    outcome = await rig.gateway.review(review_req(rig), author_model="model-sonnet")
    assert outcome.independence.verdict == "same_family"


async def test_the_users_chosen_slot_is_honoured(rig):
    rig.provider.queue("model-gemini", ok())
    outcome = await rig.gateway.review(review_req(rig), author_model="model-sonnet", slot="gemini")
    assert outcome.result.served_model == "model-gemini" and outcome.result.slot == "gemini"
    assert outcome.independence.verdict == "independent"


async def test_a_failing_reviewer_never_silently_becomes_sonnet(rig):
    rig.provider.queue("model-openai", transient(), transient())
    rig.provider.queue("model-sonnet", ok())  # would be used by an automatic fallback
    with pytest.raises(ReviewerUnavailable) as exc:
        await rig.gateway.review(review_req(rig), author_model="model-gemini", slot="openai")
    assert "model-sonnet" not in rig.provider.models
    assert exc.value.slot == "openai"
    assert "openai" not in slots_of(exc.value.options)
    assert slots_of(exc.value.options)[0] in ("sonnet", "haiku")  # independent of a Gemini author
    assert isinstance(exc.value.cause, LLMCallFailed)


@pytest.mark.parametrize("failure", [ContentFilterBlocked("blocked"), transient()])
async def test_a_default_reviewer_that_cannot_run_asks_the_user(make_rig, failure):
    rig = make_rig(llm_max_retries=0)
    rig.provider.queue("model-sonnet", failure)
    with pytest.raises(ReviewerUnavailable) as exc:
        await rig.gateway.review(review_req(rig), author_model="model-openai")
    assert exc.value.slot == "sonnet"
    options = exc.value.options
    assert "sonnet" not in slots_of(options)
    assert slots_of(options) == ["gemini", "haiku", "openai"]
    assert all(o.model_id for o in options)


async def test_a_blank_reviewer_slot_asks_the_user(make_rig):
    rig = make_rig(ibm_ica_model_id="")
    with pytest.raises(ReviewerUnavailable) as exc:
        await rig.gateway.review(review_req(rig), author_model="model-openai")
    assert exc.value.slot == "sonnet" and rig.provider.calls == []
    assert "sonnet" not in slots_of(exc.value.options)


async def test_an_auth_failure_is_not_something_another_model_can_fix(rig):
    rig.provider.queue("model-sonnet", AuthenticationFailed("401"))
    with pytest.raises(LLMCallFailed):
        await rig.gateway.review(review_req(rig), author_model="model-openai")


async def test_the_exclude_list_carries_over_between_rounds(make_rig):
    rig = make_rig(llm_max_retries=0)
    rig.provider.queue("model-sonnet", transient())
    rig.provider.queue("model-gemini", transient())
    with pytest.raises(ReviewerUnavailable) as first:
        await rig.gateway.review(review_req(rig), author_model="model-openai")
    assert slots_of(first.value.options)[0] == "gemini"

    with pytest.raises(ReviewerUnavailable) as second:
        await rig.gateway.review(
            review_req(rig), author_model="model-openai", slot="gemini", exclude=["sonnet"]
        )
    assert slots_of(second.value.options) == ["haiku", "openai"]  # neither sonnet nor gemini again


async def test_the_reviewer_still_retries_the_same_model(rig):
    rig.provider.queue("model-sonnet", transient(), ok("fine"))
    outcome = await rig.gateway.review(review_req(rig), author_model="model-openai")
    assert outcome.result.attempts == 2 and outcome.result.fallback_used is False
