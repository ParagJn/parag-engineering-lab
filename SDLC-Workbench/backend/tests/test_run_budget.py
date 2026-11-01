"""The run's meter and the pure scheduling decisions: no I/O, no model, no clock but the one we hand in."""
from __future__ import annotations

import pytest

from app.run.budget import STOP_BUDGET, STOP_CANCELLED, STOP_TIME, Meter, blocked_by, ready, wanted_keys


class Clock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now


def meter(cost=2.0, seconds=60.0, clock=None):
    return Meter(cost, seconds, clock or Clock())


# ---- money ---------------------------------------------------------------------------------------------------

def test_a_run_under_every_cap_is_not_stopped():
    m = meter()
    m.add_call(0.5, 1000, 200)
    assert m.should_stop() is None and m.cost_usd == 0.5


def test_reaching_the_cost_cap_stops_new_work_and_the_reason_stays():
    m = meter(cost=1.0)
    m.add_call(0.4, 1, 1)
    assert m.should_stop() is None
    m.add_call(0.6, 1, 1)                      # exactly the cap
    assert m.should_stop() == STOP_BUDGET
    assert m.should_stop() == STOP_BUDGET      # once stopped, always stopped


def test_the_cap_is_reached_not_merely_exceeded():
    m = meter(cost=1.0)
    m.add_call(0.999999, 1, 1)
    assert m.should_stop() is None
    m.add_call(0.000002, 1, 1)
    assert m.should_stop() == STOP_BUDGET


def test_zero_switches_the_cost_cap_off():
    m = meter(cost=0)
    m.add_call(1_000_000.0, 1, 1)
    assert m.should_stop() is None


def test_an_unpriced_call_is_counted_as_unpriced_and_never_as_zero_cost():
    m = meter(cost=1.0)
    m.add_call(None, 500, 100)
    m.add_call(0.25, 500, 100)
    snap = m.snapshot()
    assert snap["unpriced_calls"] == 1 and snap["calls"] == 2 and snap["cost_usd"] == 0.25 and snap["cost_is_partial"] is True


def test_a_run_with_every_price_known_is_not_marked_partial():
    m = meter()
    m.add_call(0.1, 1, 1)
    assert m.snapshot()["cost_is_partial"] is False and m.snapshot()["unpriced_calls"] == 0


def test_how_far_over_the_cap_a_run_went_is_reported_only_when_the_budget_stopped_it():
    m = meter(cost=1.0)
    m.add_call(1.4, 1, 1)
    assert m.should_stop() == STOP_BUDGET
    assert m.snapshot()["over_budget_by_usd"] == pytest.approx(0.4)
    m.add_call(0.1, 1, 1)                      # a call that was already in flight lands afterwards
    assert m.snapshot()["over_budget_by_usd"] == pytest.approx(0.5)
    assert meter().snapshot()["over_budget_by_usd"] is None


def test_tokens_and_calls_add_up():
    m = meter()
    m.add_call(0.1, 1000, 200)
    m.add_call(None, 500, 50)
    snap = m.snapshot()
    assert (snap["calls"], snap["tokens_in"], snap["tokens_out"]) == (2, 1500, 250)


# ---- time ------------------------------------------------------------------------------------------------------------

def test_the_time_cap_stops_a_run_once_the_clock_reaches_it():
    clock = Clock()
    m = meter(seconds=60, clock=clock)
    clock.now += 59.9
    assert m.should_stop() is None
    clock.now += 0.1
    assert m.should_stop() == STOP_TIME


def test_zero_switches_the_time_cap_off():
    clock = Clock()
    m = meter(seconds=0, clock=clock)
    clock.now += 10**9
    assert m.should_stop() is None


def test_elapsed_is_measured_from_the_start_of_the_run():
    clock = Clock(500.0)
    m = meter(clock=clock)
    clock.now += 12.5
    assert m.elapsed == 12.5 and m.snapshot()["elapsed_seconds"] == 12.5


# ---- cancel and precedence ---------------------------------------------------------------------------------------------

def test_cancelling_stops_new_work():
    m = meter()
    assert m.should_stop() is None
    m.cancel()
    assert m.should_stop() == STOP_CANCELLED


def test_the_first_reason_wins_and_later_ones_do_not_replace_it():
    clock = Clock()
    m = meter(cost=1.0, seconds=60, clock=clock)
    m.add_call(2.0, 1, 1)
    assert m.should_stop() == STOP_BUDGET
    m.cancel()
    clock.now += 1000
    assert m.should_stop() == STOP_BUDGET


def test_cancel_outranks_the_caps_when_it_arrives_first():
    m = meter(cost=1.0)
    m.cancel()
    m.add_call(5.0, 1, 1)
    assert m.should_stop() == STOP_CANCELLED


# ---- which artefacts are ready ------------------------------------------------------------------------------------------

ORDER = ["a", "b", "c", "d", "e"]
AFTER = {"c": ("a", "b"), "d": ("c",), "e": ("b",)}


def test_only_artefacts_with_nothing_to_wait_for_are_ready_at_the_start():
    assert ready(ORDER, AFTER, set(), set()) == ["a", "b"]


def test_an_artefact_is_ready_only_when_everything_it_waits_for_has_finished():
    assert ready(ORDER, AFTER, {"a"}, {"a", "b"}) == []                  # b is started but not finished, so c and e wait
    assert ready(ORDER, AFTER, {"a", "b"}, {"a", "b"}) == ["c", "e"]
    assert ready(ORDER, AFTER, {"a", "b", "c"}, {"a", "b", "c", "e"}) == ["d"]


def test_started_artefacts_are_never_offered_again():
    assert ready(ORDER, AFTER, {"a", "b"}, {"a", "b", "c"}) == ["e"]


def test_ready_artefacts_come_in_catalogue_order_not_dependency_order():
    assert ready(["z", "y", "x"], {}, set(), set()) == ["z", "y", "x"]


def test_a_dependency_outside_the_run_is_not_waited_for():
    assert ready(["c"], {"c": ("a", "b")}, set(), set()) == ["c"]   # a and b are not in `order`: the caller decided they exist


# ---- who is blocked by a failure ----------------------------------------------------------------------------------------------

def test_everything_that_needs_a_failed_artefact_is_blocked_by_it_and_siblings_are_not():
    assert blocked_by(ORDER, AFTER, {"a": "boom"}, {}) == {"c": "a", "d": "a"}


def test_a_chain_of_skips_all_point_back_at_the_real_fault():
    out = blocked_by(ORDER, AFTER, {"b": "boom"}, {})
    assert out == {"c": "b", "d": "b", "e": "b"}


def test_nothing_is_blocked_when_nothing_failed():
    assert blocked_by(ORDER, AFTER, {}, {}) == {}


def test_an_artefact_that_already_failed_or_was_skipped_is_not_reported_as_blocked_again():
    assert "c" not in blocked_by(ORDER, AFTER, {"a": "x", "c": "y"}, {})
    assert "d" not in blocked_by(ORDER, AFTER, {"a": "x"}, {"d": "blocked by a"})


def test_two_failures_block_what_depends_on_either():
    assert blocked_by(ORDER, AFTER, {"a": "x", "b": "y"}, {}) == {"c": "a", "d": "a", "e": "b"}


# ---- which artefacts a run produces ---------------------------------------------------------------------------------------------

def test_by_default_only_artefacts_with_no_version_are_produced():
    assert wanted_keys(ORDER, {"a": True, "b": False, "c": True}, only=None, rewrite_all=False) == ["b", "d", "e"]


def test_rewrite_all_takes_every_artefact():
    assert wanted_keys(ORDER, {"a": True}, only=None, rewrite_all=True) == ORDER


def test_only_names_exactly_the_ones_asked_for_in_plan_order():
    assert wanted_keys(ORDER, {"a": True}, only=["d", "a"], rewrite_all=False) == ["a", "d"]


def test_only_wins_over_the_default_even_for_an_artefact_that_already_has_a_version():
    assert wanted_keys(ORDER, {"a": True}, only=["a"], rewrite_all=False) == ["a"]
