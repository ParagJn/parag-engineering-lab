"""The Design phase (S13) end to end with a scripted model: skills, the journey and screen checks, the drawing check on an agent's reply and on a
person's edit, the links Design creates, and the wave order. The sanitiser itself is tested in test_design_sanitise.py."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.agents.items import parse_items
from app.agents.skills import SkillLibrary
from app.design.sanitise import drawings_in
from app.llm.routing import Routing
from app.main import create_app
from app.workflow.definitions import load_catalogue
from scripts import design_demo as D

from . import _fakes as F

pytestmark = pytest.mark.anyio
ANN = {"X-Actor": "Ann"}
DESIGN = ("user_journey", "lowfi_wireframes", "hifi_wireframes")


@pytest.fixture(scope="module")
def library():
    catalogue = load_catalogue(Routing.load().roles.keys())
    return catalogue, SkillLibrary.load(catalogue)


# ---- the skills -----------------------------------------------------------------------------------------------------------------------

def test_the_three_design_skills_load_for_the_ux_designer_role(library):
    catalogue, skills = library
    for key in DESIGN:
        skill = skills.get(key)
        assert skill is not None and skill.artefact.role == "ux_designer" and skill.artefact.phase_key == "design"


def test_each_skill_has_the_items_and_coverage_the_spec_names(library):
    _, skills = library
    got = {k: ([(i.prefix, i.section) for i in skills.get(k).items], skills.get(k).covers) for k in DESIGN}
    assert got == {
        "user_journey": ([("JS", "Journey")], ("PER",)),
        "lowfi_wireframes": ([("LFS", "Screens")], ("JS",)),
        "hifi_wireframes": ([("HFS", "Screens")], ("LFS",)),
    }


def test_each_skill_reads_only_what_it_needs_so_it_fits_the_upstream_limit(library):
    _, skills = library
    assert skills.get("user_journey").upstream == ("personas", "functional_requirements", "epics_features")
    assert skills.get("lowfi_wireframes").upstream == ("user_journey", "functional_requirements", "epics_features")
    assert skills.get("hifi_wireframes").upstream == ("lowfi_wireframes", "user_journey")
    for key in DESIGN:
        assert "user_stories" not in skills.get(key).upstream and "non_functional_requirements" not in skills.get(key).upstream


def test_the_three_design_item_prefixes_do_not_clash_with_each_other_or_with_requirements(library):
    _, skills = library
    prefixes = [i.prefix for s in skills.keys for i in skills.get(s).items]
    assert len(prefixes) == len(set(prefixes)) and {"JS", "LFS", "HFS"} <= set(prefixes)


def test_the_skills_tell_the_model_the_same_drawing_rules_the_sanitiser_enforces():
    from app.design.sanitise import ATTRIBUTES, ELEMENTS

    for key in ("lowfi_wireframes", "hifi_wireframes"):
        text = open(f"app/phases/skills/{key}.md", encoding="utf-8").read()
        for element in ("svg", "g", "rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text", "tspan", "title", "desc"):
            assert element in ELEMENTS and f" {element}" in text or f"{element}," in text, (key, element)
        method = text.split("## Method")[1].split("## Quality bar")[0]
        listed = method.split("Use only these attributes:")[1].split(".")[0]
        said = {a.strip() for a in listed.split(",") if a.strip()}
        assert {a.lower() for a in said} <= ATTRIBUTES, (key, {a.lower() for a in said} - ATTRIBUTES)       # the skill never invites an attribute the sanitiser would strip
        for forbidden in ("script", "foreignObject"):
            assert forbidden in text.split("## Never")[1], (key, forbidden)


# ---- a whole Design phase ---------------------------------------------------------------------------------------------------------------

@pytest.fixture
def world(make_settings):
    async def build(provider=None, **settings):
        cfg = make_settings(**{**D.MODELS, "llm_retry_backoff_seconds": 0, "run_max_cost_usd": 0, **settings})
        provider = provider or D.Scripted()
        app = create_app(cfg, provider=provider)
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers=ANN)
        store, engine, runner = app.state.store, app.state.engine, app.state.runner
        from app.sample import BRIEF, FILENAME, NAME, POLICY

        project = store.projects.create(name=NAME, brief=BRIEF, actor="system")
        engine.open_project(project.id)
        store.context.add_document(project.id, FILENAME, POLICY, actor="human:demo")
        for phase in ("setup", "requirements"):
            await runner.run_phase(project.id, phase)
            engine.finish(project.id, phase, actor="system"); engine.approve(project.id, phase, actor="human:demo")
        return app, client, provider, project

    return build


async def test_design_runs_the_journey_then_the_low_fi_then_the_hi_fi_and_all_are_saved(world):
    app, client, provider, project = await world()
    provider.asked.clear()
    result = await app.state.runner.run_phase(project.id, "design")
    assert result.status == "finished" and [o.state for o in result.outcomes] == ["done", "done", "done"]
    assert provider.asked[0] == "user_journey" and provider.asked[-1] == "hifi_wireframes"                 # the dependency chain is respected
    assert provider.asked.index("lowfi_wireframes") < provider.asked.index("hifi_wireframes")
    assert result.max_in_flight == 1                                                                         # each waits for the one before it: three waves of one
    await client.aclose()


async def test_the_events_show_the_three_waves_in_order(world):
    app, client, provider, project = await world()
    result = await app.state.runner.run_phase(project.id, "design")
    events = [e for e in app.state.store.run_events.list(project.id) if e.run_id == result.run_id]
    started = [e.data["key"] for e in events if e.type == "artefact.started"]
    finished = [e.data["key"] for e in events if e.type == "artefact.finished"]
    assert started == list(DESIGN) == finished
    await client.aclose()


async def test_a_drawing_with_a_script_is_sent_back_with_a_sentence_and_the_redrawn_one_is_what_is_saved(world):
    app, client, provider, project = await world()
    result = await app.state.runner.run_phase(project.id, "design")
    art = next(a for a in app.state.store.artefacts.list(project.id, phase_key="design") if a.type == "lowfi_wireframes")
    version = app.state.store.artefacts.get_version(project.id, art.id)
    assert version.generation["attempts"] == 2 and provider.lowfi_calls == 2
    [repair] = version.generation["repair_reasons"]
    assert any("the <script> element" in p and "line" in p for p in repair["problems"])
    assert "alert(1)" not in version.body and "<script" not in version.body.lower()
    assert version.generation["guardrails"] == []                       # the redrawn, clean artefact carries no flags
    await client.aclose()


async def test_a_secret_in_a_drawing_is_caught_by_the_same_scanner_as_in_text(world):
    app, client, provider, project = await world()
    leaky = D.lowfi().replace("Room list</text>", f"Room list {F.AWS_KEY}</text>", 1)

    class Leaky(D.Scripted):
        async def complete(self, model_id, request):
            key = self._which(request)
            if key == "lowfi_wireframes":
                from app.llm.types import ProviderResponse, Usage

                self.asked.append(key)
                return ProviderResponse(leaky, Usage(2000, 1000), "stop")
            return await super().complete(model_id, request)

    app2, client2, _, project2 = await world(provider=Leaky())
    result = await app2.state.runner.run_phase(project2.id, "design")
    assert result.status == "failed"
    lowfi = next(o for o in result.outcomes if o.key == "lowfi_wireframes")
    assert lowfi.state == "failed" and F.AWS_KEY not in (lowfi.reason or "")
    assert not [a for a in app2.state.store.artefacts.list(project2.id, phase_key="design") if a.type == "lowfi_wireframes" and a.latest_version]
    await client.aclose(); await client2.aclose()


async def test_the_screens_and_steps_become_items_with_the_links_the_spec_names(world):
    app, client, provider, project = await world()
    await app.state.runner.run_phase(project.id, "design")
    pairs = {(l.from_id, l.to_id) for l in app.state.store.links.list(project.id)}
    assert {("JS-001", "PER-001"), ("JS-001", "FR-001"), ("JS-003", "PER-002")} <= pairs           # a step derives from a persona and a requirement
    assert {("LFS-001", "JS-001"), ("LFS-002", "JS-002"), ("LFS-003", "JS-003")} <= pairs           # a screen derives from the step it shows
    assert {("HFS-001", "LFS-001"), ("HFS-001", "JS-001")} <= pairs                                 # the hi-fi derives from its low-fi and the step
    await client.aclose()


async def test_every_persona_has_a_step_and_every_step_a_screen_in_the_scripted_design(world):
    app, client, provider, project = await world()
    await app.state.runner.run_phase(project.id, "design")
    pairs = {(l.from_id, l.to_id) for l in app.state.store.links.list(project.id)}
    assert all(any(f.startswith("JS-") and t == p for f, t in pairs) for p in ("PER-001", "PER-002"))
    assert all(any(f.startswith("LFS-") and t == j for f, t in pairs) for j in ("JS-001", "JS-002", "JS-003"))
    assert all(any(f.startswith("HFS-") and t == s for f, t in pairs) for s in ("LFS-001", "LFS-002", "LFS-003"))
    await client.aclose()


async def test_a_journey_that_leaves_a_persona_out_is_sent_back_by_the_coverage_rule(world):
    class Gappy(D.Scripted):
        async def complete(self, model_id, request):
            if self._which(request) == "user_journey":
                from app.llm.types import ProviderResponse, Usage

                self.asked.append("user_journey")
                gappy = D.JOURNEY.replace("PER-002, FR-002, FEAT-002", "PER-001, FR-002, FEAT-002")           # nothing derives from PER-002 any more
                assert "</artefact>" in gappy and gappy != D.JOURNEY                                           # a well-formed reply, with exactly one gap
                return ProviderResponse(gappy, Usage(1500, 600), "stop")
            return await super().complete(model_id, request)

    app, client, provider, project = await world(provider=Gappy())
    result = await app.state.runner.run_phase(project.id, "design")
    journey = next(o for o in result.outcomes if o.key == "user_journey")
    assert journey.state == "failed" and "PER-002" in (journey.reason or "")
    assert [o.state for o in result.outcomes if o.key != "user_journey"] == ["skipped", "skipped"]          # the screens wait for a journey that never arrived
    await client.aclose()


# ---- a person's edit goes through the same drawing check ---------------------------------------------------------------------------------

async def test_a_hand_edit_with_an_unsafe_drawing_is_refused_with_the_reasons_and_nothing_is_saved(world):
    app, client, provider, project = await world()
    await app.state.runner.run_phase(project.id, "design")
    art = next(a for a in app.state.store.artefacts.list(project.id, phase_key="design") if a.type == "lowfi_wireframes")
    body = app.state.store.artefacts.get_version(project.id, art.id).body
    evil = body.replace('<rect x="20" y="20"', '<rect onclick="steal()" x="20" y="20"', 1)
    assert evil != body                                                   # precondition: the edit really did add the handler
    response = await client.put(f"/api/projects/{project.id}/artefacts/{art.id}", json={"body": evil})
    assert response.status_code == 422
    problems = response.json()["detail"]["problems"]
    assert any("onclick" in p for p in problems) and not any("steal" in p for p in problems)
    assert art.latest_version == 1 and app.state.store.artefacts.get(project.id, art.id).latest_version == 1         # still the one version the agent wrote
    await client.aclose()


async def test_a_hand_edit_that_only_changes_a_label_in_a_drawing_is_saved(world):
    app, client, provider, project = await world()
    await app.state.runner.run_phase(project.id, "design")
    art = next(a for a in app.state.store.artefacts.list(project.id, phase_key="design") if a.type == "lowfi_wireframes")
    before = app.state.store.artefacts.get_version(project.id, art.id)
    edited = before.body.replace("Room A (free)", "Room 1 (free)", 1)
    assert edited != before.body
    response = await client.put(f"/api/projects/{project.id}/artefacts/{art.id}", json={"body": edited, "note": "renamed a room"})
    assert response.status_code == 200, response.text
    assert "Room 1 (free)" in app.state.store.artefacts.get_version(project.id, art.id).body
    await client.aclose()


async def test_a_drawing_cannot_be_smuggled_into_an_artefact_that_is_not_a_design_one(world):
    """The drawing check is in the shared body check, so it applies to every artefact, not only the three that are meant to hold drawings."""
    app, client, provider, project = await world()
    personas = next(a for a in app.state.store.artefacts.list(project.id) if a.type == "personas")
    # Requirements was approved by the fixture, which would refuse ANY edit for that reason. Take it back to running so the only thing that can
    # refuse this edit is the drawing check.
    app.state.store.phases.reopen(project.id, "requirements", actor="human:Ann", reason="to test the shared check")
    body = app.state.store.artefacts.get_version(project.id, personas.id).body
    clean = body + '\n\n```svg\n<svg viewBox="0 0 10 10"><rect x="1" y="1" width="2" height="2"/></svg>\n```\n'
    evil = body + '\n\n```svg\n<svg onload="x()"><rect/></svg>\n```\n'
    ok = await client.put(f"/api/projects/{project.id}/artefacts/{personas.id}", json={"body": clean})
    assert ok.status_code == 200, ok.text                                  # precondition: the same edit with a SAFE drawing is accepted, so a refusal below is about the drawing
    refused = await client.put(f"/api/projects/{project.id}/artefacts/{personas.id}", json={"body": evil})
    assert refused.status_code == 422 and any("onload" in p for p in refused.json()["detail"]["problems"])
    assert app.state.store.artefacts.get(project.id, personas.id).latest_version == 2           # only the safe edit was saved
    await client.aclose()


def test_the_check_is_in_the_shared_body_check(library):
    from app.agents.checks import check_body

    _, skills = library
    skill = skills.get("lowfi_wireframes")
    body = D.lowfi().replace("<svg ", '<svg onload="x()" ', 1)
    problems = check_body(body.split("<artefact>\n")[1].split("\n</artefact>")[0], skill, {"JS-001", "JS-002", "JS-003"}, None)
    assert any("onload" in p for p in problems)


# ---- the demo script ---------------------------------------------------------------------------------------------------------------------

def test_the_offline_demo_passes_and_says_what_it_showed(capsys):
    assert D.main([]) == 0
    out = capsys.readouterr().out
    assert "SCRIPTED FAKE MODEL" in out and "Design: finished: 3 written" in out and "was sent back" in out
    assert "a drawing with a script in it was sent back and redrawn" in out


def test_the_demo_refuses_conflicting_or_odd_flags(capsys):
    for argv in (["--record", "x"], ["--live", "--replay", "x"], ["--replay", "bad name!"]):
        with pytest.raises(SystemExit):
            D.main(argv)
    capsys.readouterr()


def test_the_demo_without_a_key_says_so_and_exits_2(capsys, make_settings):
    cfg = make_settings(ibm_ica_endpoint="", ibm_ica_api_key="")
    assert D.main(["--live"], settings=cfg) == 2
    assert "not set" in capsys.readouterr().err


def test_the_demo_never_prints_a_key_or_the_endpoint(capsys, make_settings):
    secret = F.join("sk-test-", "own-", "ica-key-9999")
    D.main([])
    assert secret not in capsys.readouterr().out
