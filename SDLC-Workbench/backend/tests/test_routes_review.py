"""Review, request changes, re-run, stale and edit over HTTP (S12c). Every test runs the real app with a scripted model, in live mode
(a review is a model call, and replay mode cannot run one)."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.llm.errors import ContentFilterBlocked
from app.main import create_app
from app.sample import BRIEF, FILENAME, NAME, POLICY

from . import _fakes as F
from .test_run_phase import MODELS as BASE_MODELS, Scripted

pytestmark = pytest.mark.anyio
ANN = {"X-Actor": "Ann"}
MODELS = {
    **BASE_MODELS, "ibm_ica_openai_model_id": "gpt-x", "ibm_ica_openai_fallback_model_id": "m-sonnet",
    "ibm_ica_gemini_model_id": "gemini-x", "ibm_ica_gemini_fallback_model_id": "m-sonnet",
    "ibm_ica_openai_price_input_per_mtok": "2", "ibm_ica_openai_price_output_per_mtok": "10",
    "ibm_ica_gemini_price_input_per_mtok": "0.75", "ibm_ica_gemini_price_output_per_mtok": "3.75",
}
CLEAN = "<review>\nSummary: Nothing is wrong.\n</review>"
HIGH = "<review>\nSummary: One serious problem.\n- [HIGH] PER-001: Invented detail. Fix: remove it.\n- [LOW] Overview: wordy. Fix: trim.\n</review>"


@pytest.fixture
def world(make_settings):
    async def build(mode="live", delay=0.0, **settings):
        cfg = make_settings(**{**MODELS, "llm_retry_backoff_seconds": 0, "app_mode": mode, **settings})
        provider = Scripted(delay)
        app = create_app(cfg, provider=provider)
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=ANN)
        project = app.state.store.projects.create(name=NAME, brief=BRIEF, mode="live" if mode == "live" else "replay", actor="system")
        app.state.engine.open_project(project.id)
        app.state.store.context.add_document(project.id, FILENAME, POLICY, actor="human:demo")
        return app, client, provider, project

    return build


async def settle(app, pid, run_id, seconds=12):
    for _ in range(int(seconds / 0.02)):
        if app.state.store.runs.get(pid, run_id).status != "running":
            return
        await asyncio.sleep(0.02)
    raise AssertionError("the run never ended")


async def run_phase(app, client, pid, phase, **body):
    response = await client.post(f"/api/projects/{pid}/phases/{phase}/run", json=body)
    assert response.status_code == 202, response.text
    await settle(app, pid, response.json()["run_id"])


async def to_review(app, client, pid, phase="requirements"):
    """Setup approved, the phase written and handed to review."""
    await run_phase(app, client, pid, "setup")
    assert (await client.post(f"/api/projects/{pid}/phases/setup/finish")).status_code == 200
    assert (await client.post(f"/api/projects/{pid}/phases/setup/approve")).status_code == 200
    await run_phase(app, client, pid, phase)
    assert (await client.post(f"/api/projects/{pid}/phases/{phase}/finish")).status_code == 200


def personas(app, pid):
    return next(a for a in app.state.store.artefacts.list(pid) if a.type == "personas").id


# ---- reviewing one artefact --------------------------------------------------------------------------------------------------

async def test_a_review_returns_the_verdict_the_findings_and_how_independent_it_was_and_stores_them(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    provider.review_reply = HIGH
    aid = personas(app, project.id)
    response = await client.post(f"/api/projects/{project.id}/artefacts/{aid}/review", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["paused"] is False and body["artefact_id"] == aid and body["version"] == 1
    assert body["verdict"] == "revise"                                            # one HIGH finding: decided by the system, not the model
    assert [(f["severity"], f["target"]) for f in body["findings"]] == [("high", "PER-001"), ("low", "Overview")]
    assert body["independence"]["label"] == "same_family" and body["independence"]["fell_back"] is False
    assert body["cost_usd"] is not None and body["attempts"] == 1
    stored = app.state.store.artefacts.get_version(project.id, aid).review_findings
    assert stored["verdict"] == "revise" and stored["version_reviewed"] == 1
    event = next(e for e in app.state.store.audit.list(project.id) if e.action == "artefact.reviewed")
    assert event.actor == "human:Ann"
    await client.aclose()


async def test_the_artefact_detail_carries_the_stored_review_of_the_version_it_shows(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    before = (await client.get(f"/api/projects/{project.id}/artefacts/{aid}")).json()
    assert before["review"] is None
    provider.review_reply = HIGH
    await client.post(f"/api/projects/{project.id}/artefacts/{aid}/review", json={})
    after = (await client.get(f"/api/projects/{project.id}/artefacts/{aid}")).json()["review"]
    assert after["verdict"] == "revise" and after["version_reviewed"] == 1 and after["summary"] == "One serious problem."
    assert after["independence"] == {"label": "same_family", "author_family": "anthropic", "reviewer_family": "anthropic", "fell_back": False}
    assert [f["fix"] for f in after["findings"]] == ["remove it.", "trim."]
    assert "call_ids" not in json.dumps(after) and "call1" not in json.dumps(after)           # call ids stay in the database
    await client.aclose()


async def test_a_review_asked_for_a_different_family_says_independent(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    body = (await client.post(f"/api/projects/{project.id}/artefacts/{aid}/review", json={"slot": "openai"})).json()
    assert body["independence"]["label"] == "independent" and body["independence"]["reviewer_family"] == "openai"
    await client.aclose()


async def test_a_review_needs_a_name_and_an_unknown_artefact_or_project_is_a_404(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    bare = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    assert (await bare.post(f"/api/projects/{project.id}/artefacts/{aid}/review", json={})).status_code == 400
    assert (await client.post(f"/api/projects/{project.id}/artefacts/NOPE-001/review", json={})).status_code == 404
    assert (await client.post("/api/projects/nope/artefacts/X-001/review", json={})).status_code == 404
    assert (await client.post(f"/api/projects/{project.id}/artefacts/bad%20id/review", json={})).status_code == 422
    assert provider.asked.count("review") == 0                                    # none of those reached the model
    await bare.aclose(); await client.aclose()


async def test_a_review_body_with_an_unknown_field_or_a_bad_slot_is_refused(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    for body in ({"surprise": 1}, {"slot": "Bad Slot"}, {"slot": "x" * 40}, {"exclude": ["a"] * 9}):
        assert (await client.post(f"/api/projects/{project.id}/artefacts/{aid}/review", json=body)).status_code == 422, body
    assert provider.asked.count("review") == 0
    await client.aclose()


async def test_a_phase_that_is_not_running_or_awaiting_review_cannot_be_reviewed_and_the_sentence_says_why(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    assert (await client.post(f"/api/projects/{project.id}/phases/requirements/approve")).status_code == 200
    aid = personas(app, project.id)
    response = await client.post(f"/api/projects/{project.id}/artefacts/{aid}/review", json={})
    assert response.status_code == 409 and "running or awaiting review" in response.json()["detail"]
    await client.aclose()


async def test_an_archived_project_cannot_be_reviewed(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    await client.post(f"/api/projects/{project.id}/archive")
    response = await client.post(f"/api/projects/{project.id}/artefacts/{aid}/review", json={})
    assert response.status_code == 409 and response.json()["detail"] == "This project is archived; restore it first."
    assert provider.asked.count("review") == 0
    await client.aclose()


# ---- replay mode: no review can run ---------------------------------------------------------------------------------------

async def test_in_replay_mode_every_review_route_says_reviews_need_live_mode_and_calls_no_model(world):
    app, client, provider, project = await world(mode="replay")
    app.state.store.artefacts.create_and_add_version(project.id, artefact_type="personas", phase_key="requirements", title="P", prefix="REQ-PER", body="x", author="human:Ann")
    sentence = "Reviews need live mode: no review has been recorded yet, so a server answering from recordings cannot run one."
    for call in (client.post(f"/api/projects/{project.id}/artefacts/REQ-PER-001/review", json={}),
                 client.post(f"/api/projects/{project.id}/phases/requirements/review", json={})):
        response = await call
        assert response.status_code == 409 and response.json()["detail"] == sentence
    assert provider.asked == []
    await client.aclose()


async def test_the_review_state_and_the_modes_answer_say_whether_reviews_can_run(world):
    for mode, available in (("live", True), ("replay", False)):
        app, client, provider, project = await world(mode=mode)
        assert (await client.get("/api/modes")).json()["reviews_available"] is available
        state = (await client.get(f"/api/projects/{project.id}/phases/requirements/review")).json()
        assert state["reviews_available"] is available
        assert (state["replay_sentence"] is None) == available
        await client.aclose()


# ---- the reviewer cannot run: the family picker -------------------------------------------------------------------------------

async def test_an_unavailable_reviewer_returns_the_other_families_with_prices_and_stores_nothing(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    provider.review_fail = ContentFilterBlocked("blocked")
    response = await client.post(f"/api/projects/{project.id}/artefacts/{aid}/review", json={})
    assert response.status_code == 200                                              # a normal answer: the person is asked to choose
    body = response.json()
    assert body["paused"] is True and body["slot"] == "sonnet" and body["artefact_id"] == aid
    slots = [o["slot"] for o in body["options"]]
    assert "sonnet" not in slots and {"openai", "gemini"} <= set(slots)
    first = body["options"][0]
    assert first["independent"] is True and first["priced"] is True and first["price_input"] is not None      # independent families come first
    assert set(first) == {"slot", "model_id", "family", "independent", "price_input", "price_output", "priced"}
    assert app.state.store.artefacts.get_version(project.id, aid).review_findings is None                     # nothing stored, nothing switched
    await client.aclose()


async def test_choosing_a_family_runs_the_review_with_it_and_a_second_failure_returns_the_list_without_it(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    provider.review_fail = ContentFilterBlocked("blocked")
    first = (await client.post(f"/api/projects/{project.id}/artefacts/{aid}/review", json={})).json()
    pick = first["options"][0]["slot"]
    again = (await client.post(f"/api/projects/{project.id}/artefacts/{aid}/review", json={"slot": pick, "exclude": ["sonnet"]})).json()
    assert again["paused"] is True and pick not in [o["slot"] for o in again["options"]] and "sonnet" not in [o["slot"] for o in again["options"]]
    provider.review_fail = None
    done = (await client.post(f"/api/projects/{project.id}/artefacts/{aid}/review", json={"slot": pick, "exclude": ["sonnet"]})).json()
    assert done["paused"] is False and done["independence"]["label"] == "independent"
    await client.aclose()


async def test_an_option_without_a_price_shows_null_never_zero(world):
    from app.llm.types import ReviewerOption
    from app.routes_review import option_payload

    unpriced = ReviewerOption(slot="gemini", model_id="g", family="google", independent=None, price_input=0.0, price_output=0.0, priced=False)
    assert option_payload(unpriced) == {"slot": "gemini", "model_id": "g", "family": "google", "independent": None, "price_input": None, "price_output": None, "priced": False}
    priced = ReviewerOption(slot="openai", model_id="o", family="openai", independent=True, price_input=2.0, price_output=10.0, priced=True)
    assert option_payload(priced)["price_input"] == 2.0


# ---- reviewing a whole phase ------------------------------------------------------------------------------------------------

async def test_reviewing_a_phase_reviews_every_written_artefact(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/review", json={})
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 7 and all(r["paused"] is False and r["verdict"] == "ok" for r in results)
    state = (await client.get(f"/api/projects/{project.id}/phases/requirements/review")).json()
    assert {s["state"] for s in state["statuses"]} == {"reviewed"} and state["open"]["unreviewed"] == []
    await client.aclose()


async def test_a_reviewer_that_cannot_run_pauses_each_artefact_with_its_options_in_a_phase_review(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    provider.review_fail = ContentFilterBlocked("blocked")
    results = (await client.post(f"/api/projects/{project.id}/phases/requirements/review", json={})).json()["results"]
    assert len(results) == 7 and all(r["paused"] is True and r["options"] for r in results)
    await client.aclose()


# ---- where the review stands, what is stale, what is open -------------------------------------------------------------------------

async def test_the_review_state_lists_standing_per_artefact_and_what_is_open(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    provider.review_reply = HIGH
    await client.post(f"/api/projects/{project.id}/artefacts/{aid}/review", json={})
    state = (await client.get(f"/api/projects/{project.id}/phases/requirements/review")).json()
    by = {s["artefact_id"]: s for s in state["statuses"]}
    assert by[aid] == {"artefact_id": aid, "state": "reviewed", "verdict": "revise", "reviewed_version": 1, "latest_version": 1, "high_findings": 1}
    assert all(s["state"] == "unreviewed" for k, s in by.items() if k != aid)
    assert state["open"]["open_high_findings"] == 1 and aid not in state["open"]["unreviewed"] and len(state["open"]["unreviewed"]) == 6
    await client.aclose()


async def test_what_the_screen_shows_before_approving_is_exactly_what_the_audit_row_records_after(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    provider.review_reply = HIGH
    await client.post(f"/api/projects/{project.id}/artefacts/{aid}/review", json={})
    shown = (await client.get(f"/api/projects/{project.id}/phases/requirements/review")).json()["open"]
    assert (await client.post(f"/api/projects/{project.id}/phases/requirements/approve")).status_code == 200
    recorded = next(e for e in app.state.store.audit.list(project.id) if e.action == "phase.decided" and e.target_id == "requirements").detail
    assert {k: recorded[k] for k in shown} == shown
    await client.aclose()


async def test_an_unknown_phase_or_project_is_not_found_on_the_review_state(world):
    app, client, provider, project = await world()
    assert (await client.get(f"/api/projects/{project.id}/phases/nonsense/review")).status_code == 404
    assert (await client.get(f"/api/projects/{project.id}/phases/Bad/review")).status_code == 422
    assert (await client.get("/api/projects/nope/phases/requirements/review")).status_code == 404
    await client.aclose()


# ---- request changes ------------------------------------------------------------------------------------------------------------

async def test_requesting_changes_saves_the_decision_and_the_note_and_names_what_a_re_run_would_rewrite(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {aid: "Add a persona for the security team."}})
    assert response.status_code == 200
    body = response.json()
    assert (body["phase"], body["status"], body["decision"], body["decided_by"]) == ("requirements", "rejected", "reject", "human:Ann")
    assert body["artefacts_with_notes"] == [aid]
    assert "security team" in body["feedback"]
    notes = app.state.store.memory.list(project.id, phase_key="requirements")
    assert [(n.kind, n.artefact_id) for n in notes] == [("human_feedback", aid)]
    await client.aclose()


@pytest.mark.parametrize("body, fragment", [
    ({"notes": {}}, "name at least one artefact"),
    ({"notes": {"REQ-PER-001": "   "}}, "needs a note"),
    ({"notes": {"REQ-PER-001": "x" * 4001}}, "limited to"),
    ({"notes": {"REQ-PER-001": "fine"}, "include_findings": ["REQ-F-001"]}, "findings can only be passed on"),
])
async def test_a_request_the_server_cannot_accept_is_a_422_with_its_own_sentence_and_nothing_is_saved(world, body, fragment):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json=body)
    assert response.status_code == 422 and fragment in json.dumps(response.json()["detail"])
    assert app.state.store.memory.list(project.id, phase_key="requirements") == []
    assert next(p.status for p in app.state.engine.snapshot(project.id).phases if p.key == "requirements") == "awaiting_review"
    await client.aclose()


async def test_changes_can_only_be_requested_while_the_phase_is_awaiting_review(world):
    app, client, provider, project = await world()
    await run_phase(app, client, project.id, "setup")
    aid = next(a.id for a in app.state.store.artefacts.list(project.id))
    response = await client.post(f"/api/projects/{project.id}/phases/setup/request-changes", json={"notes": {aid: "redo"}})
    assert response.status_code == 409 and "awaiting_review" in response.json()["detail"]
    await client.aclose()


async def test_an_artefact_from_another_phase_cannot_be_sent_back(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    setup_id = next(a.id for a in app.state.store.artefacts.list(project.id) if a.phase_key == "setup")
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {setup_id: "redo"}})
    assert response.status_code in (404, 422)
    assert app.state.store.memory.list(project.id, phase_key="requirements") == []
    await client.aclose()


async def test_the_reviewers_findings_reach_the_writer_only_when_asked_for(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    provider.review_reply = HIGH
    await client.post(f"/api/projects/{project.id}/artefacts/{aid}/review", json={})
    await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {aid: "see the review"}, "include_findings": [aid]})
    kinds = sorted(n.kind for n in app.state.store.memory.list(project.id, phase_key="requirements"))
    assert kinds == ["human_feedback", "reviewer_feedback", "reviewer_feedback"]
    await client.aclose()


@pytest.mark.parametrize("body", [{"surprise": 1}, {"notes": "text"}, {"notes": {"bad id": "x"}}, {"include_findings": ["bad id"]}, {"overall": "x" * 4001}])
async def test_a_malformed_request_to_change_is_refused(world, body):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    assert (await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json=body)).status_code == 422
    await client.aclose()


async def test_requesting_changes_needs_a_name_and_is_refused_on_an_archived_project(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    bare = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    assert (await bare.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {aid: "x"}})).status_code == 400
    await client.post(f"/api/projects/{project.id}/archive")
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {aid: "x"}})
    assert response.status_code == 409 and response.json()["detail"] == "This project is archived; restore it first."
    await bare.aclose(); await client.aclose()


# ---- the re-run goes through the runner and rewrites only what was sent back -------------------------------------------------------------

async def test_a_re_run_rewrites_exactly_the_artefacts_with_a_note_through_the_runner_and_leaves_the_rest(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {aid: "Add a security persona."}})
    versions_before = {a.id: a.latest_version for a in app.state.store.artefacts.list(project.id, phase_key="requirements")}
    provider.asked.clear()
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/rerun")
    assert response.status_code == 202
    body = response.json()
    assert body["only"] == ["personas"] and body["status"] == "running"
    await settle(app, project.id, body["run_id"])
    assert provider.asked == ["personas"]                                           # only that artefact was sent to a model
    after = {a.id: a.latest_version for a in app.state.store.artefacts.list(project.id, phase_key="requirements")}
    assert after[aid] == versions_before[aid] + 1 and {k: v for k, v in after.items() if k != aid} == {k: v for k, v in versions_before.items() if k != aid}
    kinds = [e.type for e in app.state.store.run_events.list(project.id) if e.run_id == body["run_id"]]
    assert kinds[0] == "run.started" and "artefact.finished" in kinds and kinds[-1] == "run.finished"       # it streamed like any other run
    audit = next(e for e in app.state.store.audit.list(project.id) if e.action == "run.requested" and e.target_id == body["run_id"])
    assert audit.actor == "human:Ann" and audit.detail["rerun_of_notes"] is True and audit.detail["only"] == ["personas"]
    await client.aclose()


async def test_after_the_re_run_the_note_has_been_acted_on_and_the_phase_can_go_back_to_review(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {aid: "Add a security persona."}})
    run_id = (await client.post(f"/api/projects/{project.id}/phases/requirements/rerun")).json()["run_id"]
    await settle(app, project.id, run_id)
    assert (await client.get(f"/api/projects/{project.id}/phases/requirements/review")).json()["artefacts_with_notes"] == []
    assert (await client.post(f"/api/projects/{project.id}/phases/requirements/rerun")).status_code == 422       # nothing left to re-run
    assert (await client.post(f"/api/projects/{project.id}/phases/requirements/finish")).status_code == 200
    await client.aclose()


async def test_a_re_run_with_nothing_sent_back_is_refused_with_a_sentence_and_starts_no_run(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    before = len(app.state.store.runs.list(project.id))
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/rerun")
    assert response.status_code == 422 and "nothing to re-run" in response.json()["detail"]
    assert len(app.state.store.runs.list(project.id)) == before
    await client.aclose()


async def test_a_re_run_needs_a_name_and_is_refused_on_an_archived_project(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {aid: "x"}})
    bare = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    assert (await bare.post(f"/api/projects/{project.id}/phases/requirements/rerun")).status_code == 400
    await client.post(f"/api/projects/{project.id}/archive")
    assert (await client.post(f"/api/projects/{project.id}/phases/requirements/rerun")).json()["detail"] == "This project is archived; restore it first."
    await bare.aclose(); await client.aclose()


async def test_two_notes_on_two_artefacts_rewrite_both_in_catalogue_order(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    arts = {a.type: a.id for a in app.state.store.artefacts.list(project.id, phase_key="requirements")}
    await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes",
                      json={"notes": {arts["functional_requirements"]: "tighten", arts["personas"]: "add one"}})
    provider.asked.clear()
    body = (await client.post(f"/api/projects/{project.id}/phases/requirements/rerun")).json()
    assert body["only"] == ["personas", "functional_requirements"]                  # catalogue order, whatever order the notes came in
    await settle(app, project.id, body["run_id"])
    assert sorted(provider.asked) == ["functional_requirements", "personas"]
    await client.aclose()


# ---- built on something that changed -----------------------------------------------------------------------------------------------

async def _make_functional_stale(app, client, pid):
    """Hand-edit Personas so that Functional requirements (built on it) is now built on an old version."""
    aid = personas(app, pid)
    current = app.state.store.artefacts.get_version(pid, aid).body
    response = await client.put(f"/api/projects/{pid}/artefacts/{aid}", json={"body": current + "\n"})
    return aid, response


async def test_an_edit_upstream_marks_what_is_built_on_it_stale_and_nothing_re_runs_by_itself(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    # a version that really differs, so the artefacts built on it are behind
    aid = personas(app, project.id)
    body = app.state.store.artefacts.get_version(project.id, aid).body
    app.state.store.artefacts.add_version(project.id, aid, body=body + "\n", author="human:Ann")
    provider.asked.clear()
    state = (await client.get(f"/api/projects/{project.id}/phases/requirements/review")).json()
    assert state["stale"], "precondition: something is built on the old Personas"
    first = state["stale"][0]
    assert set(first) == {"artefact_id", "version", "built_on", "now"} and aid in first["now"]
    assert provider.asked == []                                                      # looking never re-runs anything
    await client.aclose()


async def test_re_running_the_stale_ones_is_an_explicit_call_that_rewrites_only_them(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    body = app.state.store.artefacts.get_version(project.id, aid).body
    app.state.store.artefacts.add_version(project.id, aid, body=body + "\n", author="human:Ann")
    stale_ids = {s["artefact_id"] for s in (await client.get(f"/api/projects/{project.id}/phases/requirements/review")).json()["stale"]}
    assert stale_ids and aid not in stale_ids
    provider.asked.clear()
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/rerun-stale")
    assert response.status_code == 202, response.text
    await settle(app, project.id, response.json()["run_id"])
    assert next(p.status for p in app.state.engine.snapshot(project.id).phases if p.key == "requirements") == "running"      # taken back, by the person's choice
    moved = [e for e in app.state.store.audit.list(project.id) if e.action == "phase.status" and e.target_id == "requirements" and e.detail.get("from") == "awaiting_review"]
    assert len(moved) == 1 and moved[0].actor == "human:Ann"                                                                         # attributed to them, not to the system
    types = {a.id: a.type for a in app.state.store.artefacts.list(project.id)}
    assert set(provider.asked) == {types[i] for i in stale_ids}
    audit = next(e for e in app.state.store.audit.list(project.id) if e.target_id == response.json()["run_id"])
    assert audit.detail["rerun_of_stale"] is True
    await client.aclose()


async def test_re_running_the_stale_ones_when_there_are_none_says_so(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/rerun-stale")
    assert response.status_code == 422 and "nothing in this phase was built on something that has changed" in response.json()["detail"]
    await client.aclose()


# ---- edit by hand -----------------------------------------------------------------------------------------------------------------------

async def test_a_valid_edit_saves_a_new_version_by_the_person_and_makes_the_earlier_review_out_of_date(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    await client.post(f"/api/projects/{project.id}/artefacts/{aid}/review", json={})
    body = app.state.store.artefacts.get_version(project.id, aid).body
    response = await client.put(f"/api/projects/{project.id}/artefacts/{aid}", json={"body": body + "\n", "note": "tidied the ending"})
    assert response.status_code == 200 and response.json() == {"artefact_id": aid, "version": 2}
    saved = app.state.store.artefacts.get_version(project.id, aid)
    assert saved.author == "human:Ann" and saved.generation["human_edit"] is True and saved.generation["note"] == "tidied the ending"
    detail = (await client.get(f"/api/projects/{project.id}/artefacts/{aid}")).json()
    assert detail["version"] == 2 and detail["generation"]["human_edit"] is True and detail["review"] is None
    state = (await client.get(f"/api/projects/{project.id}/phases/requirements/review")).json()
    assert next(s for s in state["statuses"] if s["artefact_id"] == aid)["state"] == "stale"
    await client.aclose()


async def test_an_edit_that_fails_a_check_saves_nothing_and_lists_every_reason(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    response = await client.put(f"/api/projects/{project.id}/artefacts/{aid}", json={"body": "## Overview\ncites [DOC-099#1] which does not exist"})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert set(detail) == {"message", "problems"} and detail["problems"] and "not saved" in detail["message"]
    assert all(isinstance(p, str) for p in detail["problems"])
    assert app.state.store.artefacts.get(project.id, aid).latest_version == 1
    await client.aclose()


async def test_an_empty_edit_is_refused(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    response = await client.put(f"/api/projects/{project.id}/artefacts/{aid}", json={"body": "   \n  "})
    assert response.status_code == 422 and response.json()["detail"]["problems"] == ["the edited text is empty"]
    await client.aclose()


async def test_an_edit_that_contains_a_secret_is_refused_without_echoing_it(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    body = app.state.store.artefacts.get_version(project.id, aid).body
    response = await client.put(f"/api/projects/{project.id}/artefacts/{aid}", json={"body": body + f"\nkey: {F.AWS_KEY}"})
    assert response.status_code == 422 and F.AWS_KEY not in response.text
    assert app.state.store.artefacts.get(project.id, aid).latest_version == 1
    await client.aclose()


async def test_an_edit_needs_a_name_and_a_running_or_reviewable_phase_and_an_unarchived_project(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    body = app.state.store.artefacts.get_version(project.id, aid).body
    bare = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    assert (await bare.put(f"/api/projects/{project.id}/artefacts/{aid}", json={"body": body})).status_code == 400
    await client.post(f"/api/projects/{project.id}/phases/requirements/approve")
    refused = await client.put(f"/api/projects/{project.id}/artefacts/{aid}", json={"body": body + "\n"})
    assert refused.status_code == 409 and "can be edited" in refused.json()["detail"]
    await client.post(f"/api/projects/{project.id}/archive")
    archived = await client.put(f"/api/projects/{project.id}/artefacts/{aid}", json={"body": body + "\n"})
    assert archived.json()["detail"] == "This project is archived; restore it first."
    await bare.aclose(); await client.aclose()


@pytest.mark.parametrize("payload", [{}, {"body": 5}, {"body": "x" * 200_001}, {"body": "x", "surprise": 1}, {"body": "x", "note": "n" * 1001}])
async def test_a_malformed_edit_request_is_refused(world, payload):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    assert (await client.put(f"/api/projects/{project.id}/artefacts/{aid}", json=payload)).status_code == 422
    await client.aclose()


async def test_an_unknown_artefact_is_a_404_on_edit(world):
    app, client, provider, project = await world()
    assert (await client.put(f"/api/projects/{project.id}/artefacts/NOPE-001", json={"body": "x"})).status_code == 404
    assert (await client.put(f"/api/projects/{project.id}/artefacts/bad%20id", json={"body": "x"})).status_code == 422
    await client.aclose()


# ---- what a response may contain ------------------------------------------------------------------------------------------------------

async def test_no_review_response_contains_a_prompt_a_key_the_endpoint_or_a_path(world):
    secret, endpoint = F.join("sk-test-", "own-", "ica-key-9999"), "https://ica.example-internal.test/api"
    app, client, provider, project = await world(ibm_ica_api_key=secret, ibm_ica_endpoint=endpoint)
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    provider.review_reply = HIGH
    texts = []
    for call in (client.post(f"/api/projects/{project.id}/artefacts/{aid}/review", json={}),
                 client.post(f"/api/projects/{project.id}/phases/requirements/review", json={}),
                 client.get(f"/api/projects/{project.id}/phases/requirements/review"),
                 client.get(f"/api/projects/{project.id}/artefacts/{aid}"),
                 client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {aid: "fix"}}),
                 client.put(f"/api/projects/{project.id}/artefacts/{aid}", json={"body": "bad"})):
        texts.append((await call).text)
    for text in texts:
        for forbidden in (secret, endpoint, "/Users", "BEGIN UNTRUSTED", "<artefact>", "<review>", ".db", "Traceback", "call1", "system prompt"):
            assert forbidden not in text, forbidden
    await client.aclose()


# ---- gaps the first S12c break-one-thing sweep found -------------------------------------------------------------------------------------
# Most were the same mistake: a request wrong in TWO ways is refused whether or not the check under test exists. Each test below sends an
# otherwise valid request with exactly one fault.

async def test_a_phase_review_needs_a_name_and_is_refused_on_an_archived_project(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    bare = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
    assert (await bare.post(f"/api/projects/{project.id}/phases/requirements/review", json={})).status_code == 400
    assert provider.asked.count("review") == 0
    await client.post(f"/api/projects/{project.id}/archive")
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/review", json={})
    assert response.status_code == 409 and response.json()["detail"] == "This project is archived; restore it first."
    assert provider.asked.count("review") == 0
    await bare.aclose(); await client.aclose()


def test_a_stored_record_that_is_not_a_review_is_not_shown_as_one():
    from app.routes_review_shape import review_payload

    assert review_payload(None) is None and review_payload("text") is None and review_payload([]) is None
    assert review_payload({"summary": "no verdict here", "findings": []}) is None            # a dict without a verdict is not a review
    assert review_payload({"verdict": "ok", "summary": "s", "findings": []})["verdict"] == "ok"


async def test_the_review_state_names_the_artefacts_a_re_run_would_rewrite(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    assert (await client.get(f"/api/projects/{project.id}/phases/requirements/review")).json()["artefacts_with_notes"] == []
    await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {aid: "add a security persona"}})
    assert (await client.get(f"/api/projects/{project.id}/phases/requirements/review")).json()["artefacts_with_notes"] == [aid]
    await client.aclose()


async def test_changes_cannot_be_requested_while_a_run_is_going_and_the_sentence_says_why(world):
    app, client, provider, project = await world(delay=0.3)
    await run_phase(app, client, project.id, "setup")
    await client.post(f"/api/projects/{project.id}/phases/setup/finish"); await client.post(f"/api/projects/{project.id}/phases/setup/approve")
    run_id = (await client.post(f"/api/projects/{project.id}/phases/requirements/run", json={})).json()["run_id"]
    for _ in range(200):
        if app.state.runner.is_active(project.id, "requirements"):
            break
        await asyncio.sleep(0.01)
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {"REQ-PER-001": "x"}})
    assert response.status_code == 409 and "being written right now" in response.json()["detail"]          # not the engine's wording about the phase state
    await settle(app, project.id, run_id)
    await client.aclose()


async def test_the_note_for_the_whole_phase_is_saved_as_phase_wide_feedback(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {aid: "fix this"}, "overall": "  Keep the tone plain.  "})
    notes = [(n.kind, n.artefact_id, n.text) for n in app.state.store.memory.list(project.id, phase_key="requirements")]
    assert ("human_feedback", None, "Keep the tone plain.") in notes and ("human_feedback", aid, "fix this") in notes
    await client.aclose()


async def test_an_artefact_id_with_odd_characters_in_include_findings_is_refused_by_the_route_not_passed_on(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {aid: "fix"}, "include_findings": ["bad id"]})
    assert response.status_code == 422 and "unexpected characters" in json.dumps(response.json()["detail"])
    assert app.state.store.memory.list(project.id, phase_key="requirements") == []
    await client.aclose()


async def test_a_valid_request_with_one_unknown_field_is_refused_and_saves_nothing(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {aid: "fix"}, "surprise": 1})
    assert response.status_code == 422 and "surprise" in json.dumps(response.json()["detail"])
    assert app.state.store.memory.list(project.id, phase_key="requirements") == []
    assert next(p.status for p in app.state.engine.snapshot(project.id).phases if p.key == "requirements") == "awaiting_review"
    await client.aclose()


async def test_a_valid_request_with_an_over_long_overall_note_is_refused_by_the_route_itself(world):
    """Two layers enforce this bound (the request model and the human-actions rule) with the same status; the wording tells them apart."""
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {aid: "fix"}, "overall": "x" * 4001})
    assert response.status_code == 422 and "at most 4000 characters" in json.dumps(response.json()["detail"])
    assert app.state.store.memory.list(project.id, phase_key="requirements") == []
    await client.aclose()


async def test_the_re_run_list_is_in_catalogue_order_not_alphabetical_either_way(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    arts = {a.type: a.id for a in app.state.store.artefacts.list(project.id, phase_key="requirements")}
    await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes",
                      json={"notes": {arts["vision_objectives"]: "sharper", arts["problem_statement"]: "shorter"}})
    body = (await client.post(f"/api/projects/{project.id}/phases/requirements/rerun")).json()
    assert body["only"] == ["problem_statement", "vision_objectives"]               # the catalogue puts the problem before the vision; neither alphabet nor note order does
    await settle(app, project.id, body["run_id"])
    await client.aclose()


async def test_an_artefact_with_no_version_is_never_named_for_a_re_run_even_when_there_is_a_phase_wide_note(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    empty = app.state.store.artefacts.create(project.id, artefact_type="extra_thing", phase_key="requirements", title="Extra", actor="system", prefix="REQ-XTR")
    body = (await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {aid: "fix"}, "overall": "a note for everything"})).json()
    assert body["artefacts_with_notes"] == [aid]                  # the phase-wide note does not select the empty one, nor any other artefact
    assert empty.id not in body["artefacts_with_notes"]
    await client.aclose()


async def test_a_phase_wide_note_never_turns_a_re_run_of_two_into_a_re_run_of_everything(world):
    """The mistake this guards against cost real money in the first draft: one overall remark selected all seven artefacts."""
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    arts = {a.type: a.id for a in app.state.store.artefacts.list(project.id, phase_key="requirements")}
    await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes",
                      json={"notes": {arts["personas"]: "add one", arts["vision_objectives"]: "sharper"}, "overall": "Use plainer words everywhere"})
    state = (await client.get(f"/api/projects/{project.id}/phases/requirements/review")).json()
    assert sorted(state["artefacts_with_notes"]) == sorted([arts["personas"], arts["vision_objectives"]])
    provider.asked.clear()
    body = (await client.post(f"/api/projects/{project.id}/phases/requirements/rerun")).json()
    assert body["only"] == ["personas", "vision_objectives"]
    await settle(app, project.id, body["run_id"])
    assert sorted(provider.asked) == ["personas", "vision_objectives"]                 # two model calls, not seven
    await client.aclose()


async def test_re_running_the_stale_ones_is_refused_on_an_archived_project(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    app.state.store.artefacts.add_version(project.id, aid, body=app.state.store.artefacts.get_version(project.id, aid).body + "\n", author="human:Ann")
    await client.post(f"/api/projects/{project.id}/archive")
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/rerun-stale")
    assert response.status_code == 409 and response.json()["detail"] == "This project is archived; restore it first."
    await client.aclose()


async def test_a_valid_edit_with_one_unknown_field_is_refused_and_saves_nothing(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    body = app.state.store.artefacts.get_version(project.id, aid).body
    response = await client.put(f"/api/projects/{project.id}/artefacts/{aid}", json={"body": body + "\n", "surprise": 1})
    assert response.status_code == 422 and "surprise" in json.dumps(response.json()["detail"])
    assert app.state.store.artefacts.get(project.id, aid).latest_version == 1
    await client.aclose()


async def test_a_valid_edit_with_a_note_over_the_limit_is_refused_and_saves_nothing(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    body = app.state.store.artefacts.get_version(project.id, aid).body
    response = await client.put(f"/api/projects/{project.id}/artefacts/{aid}", json={"body": body + "\n", "note": "n" * 1001})
    assert response.status_code == 422 and "at most 1000 characters" in json.dumps(response.json()["detail"])
    assert app.state.store.artefacts.get(project.id, aid).latest_version == 1
    await client.aclose()


async def test_an_edit_body_over_the_route_limit_is_refused_by_the_route_before_any_check_runs(world):
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    response = await client.put(f"/api/projects/{project.id}/artefacts/{aid}", json={"body": "x" * 200_001})
    assert response.status_code == 422 and "at most 200000 characters" in json.dumps(response.json()["detail"])
    assert app.state.store.artefacts.get(project.id, aid).latest_version == 1
    await client.aclose()


async def test_a_note_about_an_artefact_that_has_no_version_yet_never_makes_it_part_of_a_re_run(world):
    """Sending back an artefact that was never written is accepted (S08 does not stop it), and its note is saved. A re-run must still not
    name it: there is no draft to rewrite, and a plain run is what writes a first version."""
    app, client, provider, project = await world()
    await to_review(app, client, project.id)
    aid = personas(app, project.id)
    empty = app.state.store.artefacts.create(project.id, artefact_type="extra_thing", phase_key="requirements", title="Extra", actor="system", prefix="REQ-XTR")
    response = await client.post(f"/api/projects/{project.id}/phases/requirements/request-changes", json={"notes": {aid: "fix", empty.id: "write this one"}})
    assert response.status_code == 200
    assert len(app.state.store.memory.list(project.id, phase_key="requirements")) == 2            # both notes were saved
    assert response.json()["artefacts_with_notes"] == [aid]                                          # but only the written artefact is named for rewriting
    assert app.state.human.to_rewrite(project.id, "requirements") == [aid]
    await client.aclose()
