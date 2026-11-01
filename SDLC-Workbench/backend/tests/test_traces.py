from __future__ import annotations

import pytest

from app.models import InvalidInput, NotFoundError


def rec(store, project, **kw):
    kw.setdefault("agent", "requirements-analyst")
    kw.setdefault("slot", "sonnet")
    kw.setdefault("requested_model", "model-sonnet")
    kw.setdefault("served_model", "model-sonnet")
    kw.setdefault("status", "ok")
    kw.setdefault("project_id", project.id)
    kw.setdefault("phase_key", "requirements")
    return store.traces.record(**kw)


def test_ok_trace_round_trip(store, project):
    t = rec(store, project, tokens_in=1000, tokens_out=200, latency_ms=850, cost_usd=0.004, run_id="run-1")
    assert store.traces.list(project.id) == [t]
    assert (t.tokens_in, t.tokens_out, t.latency_ms, t.cost_usd, t.run_id) == (1000, 200, 850, 0.004, "run-1")
    assert t.fallback_used is False and t.error is None


def test_error_trace_keeps_the_reason(store, project):
    t = rec(store, project, status="error", error="HTTP 503")
    assert (t.status, t.error) == ("error", "HTTP 503")


def test_unknown_cost_stays_none_and_zero_stays_zero(store, project):
    unknown = rec(store, project)
    free = rec(store, project, cost_usd=0)
    assert unknown.cost_usd is None
    assert free.cost_usd == 0.0 and isinstance(free.cost_usd, float)


def test_fallback_is_recorded_with_both_models(store, project):
    t = rec(store, project, slot="gemini", requested_model="model-gemini", served_model="model-sonnet", fallback_used=True)
    assert t.fallback_used is True
    assert (t.requested_model, t.served_model) == ("model-gemini", "model-sonnet")


@pytest.mark.parametrize(
    "bad",
    [
        {"tokens_in": -1},
        {"tokens_out": -5},
        {"latency_ms": -1},
        {"tokens_in": 1.5},
        {"tokens_in": True},
        {"status": "maybe"},
        {"cost_usd": -0.01},
        {"cost_usd": float("nan")},
        {"cost_usd": float("inf")},
        {"cost_usd": "free"},
        {"agent": " "},
        {"served_model": ""},
    ],
)
def test_bad_values_are_refused(store, project, bad):
    with pytest.raises(InvalidInput):
        rec(store, project, **bad)
    assert store.traces.list(project.id) == []


def test_project_is_optional_but_must_exist_when_given(store):
    t = store.traces.record(
        agent="orchestrator", slot="sonnet", requested_model="m", served_model="m", status="ok"
    )
    assert t.project_id is None
    with pytest.raises(NotFoundError):
        store.traces.record(
            agent="a", slot="s", requested_model="m", served_model="m", status="ok", project_id="nope"
        )


def test_list_filters(store, project):
    rec(store, project, agent="a1", phase_key="requirements")
    rec(store, project, agent="a2", phase_key="design")
    rec(store, project, agent="a1", phase_key="design")
    assert len(store.traces.list(project.id)) == 3
    assert len(store.traces.list(project.id, agent="a1")) == 2
    assert len(store.traces.list(project.id, phase_key="design")) == 2
    assert len(store.traces.list(project.id, agent="a1", phase_key="design")) == 1


def test_traces_do_not_write_audit_rows(store, project):
    before = len(store.audit.list(project.id))
    rec(store, project)
    assert len(store.audit.list(project.id)) == before


# ---- rollups ---------------------------------------------------------------

def seed(store, project):
    rec(store, project, served_model="model-sonnet", tokens_in=100, tokens_out=50, cost_usd=0.10)
    rec(store, project, served_model="model-sonnet", tokens_in=200, tokens_out=100, cost_usd=0.20)
    rec(store, project, served_model="model-gemini", slot="gemini", phase_key="design",
        tokens_in=300, tokens_out=150, cost_usd=None)
    rec(store, project, served_model="model-openai", slot="openai", phase_key="design",
        status="error", error="timeout", tokens_in=0, tokens_out=0)
    rec(store, project, served_model="model-sonnet", slot="gemini", requested_model="model-gemini",
        fallback_used=True, phase_key="design", tokens_in=50, tokens_out=25, cost_usd=0.05)


def by_key(rows):
    return {r.key: r for r in rows}


def test_rollup_by_model_sums_correctly(store, project):
    seed(store, project)
    rows = by_key(store.traces.rollup(project.id, "model"))
    sonnet = rows["model-sonnet"]
    assert sonnet.calls == 3
    assert (sonnet.tokens_in, sonnet.tokens_out) == (350, 175)
    assert sonnet.cost_usd == pytest.approx(0.35)
    assert sonnet.fallbacks == 1 and sonnet.errors == 0 and sonnet.unpriced_calls == 0


def test_rollup_cost_is_none_when_nothing_was_priced(store, project):
    seed(store, project)
    gemini = by_key(store.traces.rollup(project.id, "model"))["model-gemini"]
    assert gemini.cost_usd is None
    assert gemini.unpriced_calls == 1


def test_failed_calls_are_errors_not_unpriced(store, project):
    seed(store, project)
    openai = by_key(store.traces.rollup(project.id, "model"))["model-openai"]
    assert openai.errors == 1
    assert openai.unpriced_calls == 0
    assert openai.cost_usd is None


def test_rollup_by_phase_agent_and_slot(store, project):
    seed(store, project)
    phases = by_key(store.traces.rollup(project.id, "phase"))
    assert phases["requirements"].calls == 2
    assert phases["design"].calls == 3
    assert phases["design"].cost_usd == pytest.approx(0.05)  # only the one priced design call
    assert phases["design"].unpriced_calls == 1
    assert by_key(store.traces.rollup(project.id, "agent"))["requirements-analyst"].calls == 5
    slots = by_key(store.traces.rollup(project.id, "slot"))
    assert slots["gemini"].calls == 2 and slots["sonnet"].calls == 2 and slots["openai"].calls == 1


def test_rollup_totals_equal_the_sum_of_the_traces(store, project):
    seed(store, project)
    traces = store.traces.list(project.id)
    for by in ("model", "phase", "agent", "slot"):
        rows = store.traces.rollup(project.id, by)
        assert sum(r.calls for r in rows) == len(traces)
        assert sum(r.tokens_in for r in rows) == sum(t.tokens_in for t in traces)
        assert sum(r.tokens_out for r in rows) == sum(t.tokens_out for t in traces)
        assert sum(r.cost_usd or 0 for r in rows) == pytest.approx(sum(t.cost_usd or 0 for t in traces))


def test_rollups_are_per_project(store, project):
    other = store.projects.create(name="Other", actor="system")
    rec(store, project, cost_usd=1.0)
    rec(store, other, cost_usd=5.0)
    rows = store.traces.rollup(project.id, "model")
    assert len(rows) == 1 and rows[0].cost_usd == 1.0


def test_rollup_input_checks(store, project):
    with pytest.raises(InvalidInput):
        store.traces.rollup(project.id, "colour; DROP TABLE traces")
    with pytest.raises(NotFoundError):
        store.traces.rollup("nope", "model")
    assert store.traces.rollup(project.id, "model") == []
