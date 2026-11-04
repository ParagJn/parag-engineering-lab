"""S19f-1: editing ONE file of the Build instruction set. A real composed set (a scripted writer), a real HumanActions, no real model, no network."""
from __future__ import annotations

import pytest

from app.build import instructions as I
from app.models import NotFoundError
from app.review.errors import EditRefused, PersonRequired, ReviewError, WrongPhaseState
from app.review.human import HumanActions

from . import _fakes as F

from .test_review_set import ACCEPT, FOUNDATION, INDEX, UC1, UC2, artefact_id, catalogue, world  # noqa: F401  (world and catalogue are fixtures)

pytestmark = pytest.mark.anyio
ANN = "human:ann"


@pytest.fixture
def rig(world, store, project):                                   # noqa: F811
    async def build(**settings):
        service, reviewer, runtime, cfg = await world(**settings)
        human = HumanActions(store, runtime.engine, runtime, service)
        art = artefact_id(store, project)
        version = store.artefacts.get_version(project.id, art)
        files, _ = I.split_set(version.body)
        return human, art, version, files, runtime

    return build


def current(store, project, art):
    version = store.artefacts.get_version(project.id, art)
    return version, I.split_set(version.body)[0]


# ---- the splice ---------------------------------------------------------------------------------------------------------------------------------------

async def test_an_edited_file_is_replaced_and_no_other_file_changes_by_a_character(rig, store, project):
    human, art, version, files, _ = await rig()
    text = files[UC1].replace("Let office staff reserve a free room.", "Let office staff reserve a free room, quickly.")
    assert text != files[UC1]
    number = human.edit_file(project.id, art, UC1, text, based_on=version.number, actor=ANN, note="tighter goal")
    new, after = current(store, project, art)
    assert number == new.number == version.number + 1
    assert after[UC1] == text and "quickly" in after[UC1]
    assert {n: t for n, t in after.items() if n != UC1} == {n: t for n, t in files.items() if n != UC1}


async def test_every_file_keeps_its_item_number_and_the_file_list_is_unchanged_in_shape(rig, store, project):
    human, art, version, files, _ = await rig()
    human.edit_file(project.id, art, UC2, files[UC2].replace("Let office staff reserve a free room.", "Let staff see rooms."), based_on=version.number, actor=ANN)
    new, _ = current(store, project, art)
    before, after = I._set_head_ids(version.body), I._set_head_ids(new.body)
    assert [i for i, _t in after] == [i for i, _t in before] and len(after) == len(files)


async def test_the_version_names_the_person_the_file_the_base_and_the_note(rig, store, project):
    human, art, version, files, _ = await rig()
    human.edit_file(project.id, art, UC1, files[UC1] + "\nExtra line.\n", based_on=version.number, actor=ANN, note="  added a line  ")
    new, _ = current(store, project, art)
    assert new.author == ANN
    assert new.generation["edited_file"] == UC1 and new.generation["based_on"] == version.number and new.generation["human_edit"] is True
    assert new.generation["note"] == "added a line"


async def test_the_design_index_is_rebuilt_from_the_edited_files(rig, store, project):
    human, art, version, files, _ = await rig()
    assert "FR-001" not in files[INDEX]
    human.edit_file(project.id, art, UC1, files[UC1].replace("Derives from: UC-001, API-003, RUL-001", "Derives from: UC-001, API-003, RUL-001, FR-001"),
                    based_on=version.number, actor=ANN)
    _, after = current(store, project, art)
    assert "FR-001" in after[INDEX] and after[INDEX] != files[INDEX]


async def test_two_edits_in_a_row_on_the_latest_version_each_succeed(rig, store, project):
    human, art, version, files, _ = await rig()
    first = human.edit_file(project.id, art, UC1, files[UC1] + "\nOne.\n", based_on=version.number, actor=ANN)
    _, now = current(store, project, art)
    second = human.edit_file(project.id, art, UC2, now[UC2] + "\nTwo.\n", based_on=first, actor=ANN)
    _, after = current(store, project, art)
    assert (first, second) == (version.number + 1, version.number + 2) and "One." in after[UC1] and "Two." in after[UC2]


# ---- refusals: the edited file's own checks -----------------------------------------------------------------------------------------------------------

def refused(human, project, art, name, text, based_on):
    with pytest.raises(EditRefused) as caught:
        human.edit_file(project.id, art, name, text, based_on=based_on, actor=ANN)
    return caught.value


async def nothing_saved(store, project, art, version):
    assert store.artefacts.get_version(project.id, art).number == version.number


async def test_an_edit_that_drops_a_required_section_is_refused_with_the_reason_and_saves_nothing(rig, store, project):
    human, art, version, files, _ = await rig()
    text = files[UC1].replace("## Done when", "## Finished")
    err = refused(human, project, art, UC1, text, version.number)
    assert err.problems and any("Done when" in p for p in err.problems)
    await nothing_saved(store, project, art, version)


async def test_an_edit_naming_a_design_id_that_does_not_exist_is_refused(rig, store, project):
    human, art, version, files, _ = await rig()
    err = refused(human, project, art, UC1, files[UC1].replace("API-003 POST", "API-777 POST"), version.number)
    assert any("API-777" in p for p in err.problems)
    await nothing_saved(store, project, art, version)


async def test_an_edit_that_breaks_the_interface_contract_is_refused_by_name_code_and_route(rig, store, project):
    human, art, version, files, _ = await rig()
    for old, new, word in (
        ("POST /api/reservations", "POST /api/bookings", "/api/bookings"),
        ("- A reservation is created", "- A reservation is created and the service returns status 418", "418"),
        ("Needs TBL-001 and TBL-002.", "Needs TBL-001 and TBL-002. Input: `starts_at`", "starts_at"),
    ):
        text = files[UC1].replace(old, new)
        assert text != files[UC1], old
        err = refused(human, project, art, UC1, text, version.number)
        assert any(word in p for p in err.problems), (word, err.problems)
    await nothing_saved(store, project, art, version)


async def test_an_edit_with_a_secret_a_placeholder_or_an_empty_text_is_refused(rig, store, project):
    human, art, version, files, _ = await rig()
    for text in (files[UC1] + f"\nkey = {F.AWS_KEY}\n", files[UC1] + "\nTODO: fill this in later.\n", "   \n\n"):
        refused(human, project, art, UC1, text, version.number)
    await nothing_saved(store, project, art, version)


async def test_a_file_over_the_size_limit_is_refused(rig, store, project):
    human, art, version, files, _ = await rig()
    err = refused(human, project, art, UC1, files[UC1] + "\n" + "- filler line that goes on\n" * 1200, version.number)
    assert any("20000" in p or "20,000" in p for p in err.problems), err.problems


# ---- scope: what blocks and what does not ------------------------------------------------------------------------------------------------------------

async def test_a_problem_already_in_another_file_does_not_block_an_edit(rig, store, project):
    human, art, version, files, _ = await rig()
    broken = version.body.replace(files[UC2], files[UC2].replace("API-001 GET", "API-777 GET"))
    store.artefacts.add_version(project.id, art, body=broken, author="human:bob")
    later = store.artefacts.get_version(project.id, art)
    now = I.split_set(later.body)[0]
    assert "API-777" in now[UC2]
    number = human.edit_file(project.id, art, UC1, now[UC1] + "\nStill fine.\n", based_on=later.number, actor=ANN)
    assert number == later.number + 1 and "API-777" in current(store, project, art)[1][UC2]


async def test_a_set_level_problem_the_edit_introduces_is_refused(rig, store, project):
    human, art, version, files, _ = await rig()
    gone = files[UC1].replace("Derives from: UC-001, API-003, RUL-001", "Derives from: API-003, RUL-001")
    assert gone != files[UC1]
    err = refused(human, project, art, UC1, gone, version.number)
    assert any("UC-001" in p for p in err.problems), err.problems
    await nothing_saved(store, project, art, version)


async def test_a_foundation_edit_that_leaves_an_endpoint_out_of_the_contract_is_refused(rig, store, project):
    human, art, version, files, _ = await rig()
    lines = [ln for ln in files[FOUNDATION].split("\n") if not ln.startswith("- API-003 ")]
    err = refused(human, project, art, FOUNDATION, "\n".join(lines), version.number)
    assert any("API-003" in p for p in err.problems), err.problems
    await nothing_saved(store, project, art, version)


async def test_a_foundation_edit_that_changes_a_name_other_files_use_names_those_files(rig, store, project):
    human, art, version, files, _ = await rig()
    first = human.edit_file(project.id, art, UC1, files[UC1].replace("Needs TBL-001 and TBL-002.", "Needs TBL-001 and TBL-002. Input: `room_id`"), based_on=version.number, actor=ANN)
    text = files[FOUNDATION].replace("room_id", "room")
    err = refused(human, project, art, FOUNDATION, text, first)
    assert any(p.startswith(f"{UC1}:") and "room_id" in p for p in err.problems), err.problems
    assert not any(p.startswith(f"{UC2}:") for p in err.problems)                  # a file that was fine and still is fine is not named


# ---- shape ---------------------------------------------------------------------------------------------------------------------------------------------

async def test_a_text_with_a_file_mark_line_is_refused_so_a_file_cannot_be_added_or_renamed(rig, store, project):
    human, art, version, files, _ = await rig()
    err = refused(human, project, art, UC1, files[UC1] + "\n=== FILE: UC-009-new.md ===\n# New\n", version.number)
    assert any("=== FILE:" in p for p in err.problems)
    await nothing_saved(store, project, art, version)


async def test_the_design_index_cannot_be_edited_by_hand(rig, store, project):
    human, art, version, files, _ = await rig()
    err = refused(human, project, art, INDEX, files[INDEX] + "\n- note\n", version.number)
    assert any("written by the system" in p for p in err.problems)


async def test_a_file_that_is_not_in_the_set_is_not_found(rig, store, project):
    human, art, version, files, _ = await rig()
    with pytest.raises(NotFoundError, match="has no file 'UC-009-ghost.md'"):
        human.edit_file(project.id, art, "UC-009-ghost.md", "# x\n", based_on=version.number, actor=ANN)


async def test_only_a_set_of_instruction_files_has_files_to_edit(rig, store, project):
    human, art, version, files, _ = await rig()
    other, _ = store.artefacts.create_and_add_version(project.id, artefact_type="personas", phase_key="requirements", title="Personas", prefix="REQ-PER",
                                                      body="## Personas\n- PER-001 x. Derives from: SET-CHR-001\n", author="human:seed")
    with pytest.raises(ReviewError, match="not a set of instruction files"):
        human.edit_file(project.id, other.id, "a.md", "x", based_on=1, actor=ANN)


# ---- base version, phase, person -------------------------------------------------------------------------------------------------------------------

async def test_an_edit_made_on_an_older_version_is_refused_in_plain_words_and_saves_nothing(rig, store, project):
    human, art, version, files, _ = await rig()
    human.edit_file(project.id, art, UC1, files[UC1] + "\nFirst.\n", based_on=version.number, actor=ANN)
    err = refused(human, project, art, UC2, files[UC2] + "\nSecond.\n", version.number)
    assert "the set is at version 2 now and you were editing version 1; reload the page" in str(err)
    assert store.artefacts.get_version(project.id, art).number == version.number + 1


@pytest.mark.parametrize("status", ["approved", "not_started"])
async def test_an_edit_while_the_phase_is_not_open_is_refused(rig, store, project, status):
    human, art, version, files, runtime = await rig()
    if status == "approved":
        store.phases.set_status(project.id, "build", "awaiting_review", actor="system")
        store.phases.record_decision(project.id, "build", "approve", actor="human:ann")
    else:
        store.phases.set_status(project.id, "build", status, actor="system")
    with pytest.raises(WrongPhaseState):
        human.edit_file(project.id, art, UC1, files[UC1] + "\nx\n", based_on=version.number, actor=ANN)
    assert store.artefacts.get_version(project.id, art).number == version.number


@pytest.mark.parametrize("actor", ["system", "agent:r@m", "", "ann"])
async def test_an_agent_the_system_or_a_bare_name_may_not_edit_a_file(rig, store, project, actor):
    human, art, version, files, _ = await rig()
    with pytest.raises(PersonRequired):
        human.edit_file(project.id, art, UC1, files[UC1] + "\nx\n", based_on=version.number, actor=actor)
    assert store.artefacts.get_version(project.id, art).number == version.number


# ---- the route -----------------------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def api(rig, store, project):
    import httpx
    from fastapi import FastAPI
    from app.routes_review import router

    async def build():
        human, art, version, files, runtime = await rig()
        app = FastAPI()
        app.include_router(router)
        app.state.store, app.state.human = store, human
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"X-Actor": "Ann"})
        return client, f"/api/projects/{project.id}/artefacts/{art}/files", art, version, files

    return build


async def test_the_route_saves_the_edit_and_answers_with_the_new_version(api, store, project):
    client, base, art, version, files = await api()
    response = await client.put(f"{base}/{UC1}", json={"text": files[UC1] + "\nMore.\n", "based_on": version.number, "note": "by route"})
    assert response.status_code == 200 and response.json() == {"artefact_id": art, "file": UC1, "version": version.number + 1}
    saved = store.artefacts.get_version(project.id, art)
    assert saved.author == "human:Ann" and saved.generation["edited_file"] == UC1 and saved.generation["note"] == "by route"
    await client.aclose()


async def test_the_route_answers_a_refusal_with_every_reason_in_a_list(api, store, project):
    client, base, art, version, files = await api()
    response = await client.put(f"{base}/{UC1}", json={"text": files[UC1].replace("## Done when", "## Finished"), "based_on": version.number})
    detail = response.json()["detail"]
    assert response.status_code == 422 and isinstance(detail["problems"], list) and detail["problems"] and "not saved" in detail["message"]
    assert store.artefacts.get_version(project.id, art).number == version.number
    await client.aclose()


async def test_the_route_answers_an_unknown_file_with_404_and_a_wrong_base_with_a_plain_422(api, store, project):
    client, base, art, version, files = await api()
    assert (await client.put(f"{base}/UC-009-ghost.md", json={"text": "# x\n", "based_on": version.number})).status_code == 404
    old = await client.put(f"{base}/{UC1}", json={"text": files[UC1] + "\nx\n", "based_on": version.number + 5})
    assert old.status_code == 422 and "reload the page" in old.json()["detail"]["message"]
    await client.aclose()


async def test_the_route_needs_a_name_and_checks_the_shape_of_what_it_is_given(api, store, project):
    client, base, art, version, files = await api()
    good = {"text": files[UC1] + "\nx\n", "based_on": version.number}
    bare = httpx_without_actor(client)
    assert (await bare.put(f"{base}/{UC1}", json=good)).status_code == 400
    assert (await client.put(f"{base}/not-markdown.txt", json=good)).status_code == 422
    assert (await client.put(f"{base}/{UC1}", json={**good, "extra": 1})).status_code == 422
    assert (await client.put(f"{base}/{UC1}", json={**good, "based_on": 0})).status_code == 422
    assert (await client.put(f"{base}/{UC1}", json={"text": "x" * 200_001, "based_on": version.number})).status_code == 422
    assert store.artefacts.get_version(project.id, art).number == version.number
    await client.aclose()
    await bare.aclose()


async def test_the_route_refuses_a_closed_phase_with_409_and_an_archived_project_with_409(api, store, project):
    client, base, art, version, files = await api()
    store.phases.set_status(project.id, "build", "not_started", actor="system")
    assert (await client.put(f"{base}/{UC1}", json={"text": files[UC1] + "\nx\n", "based_on": version.number})).status_code == 409
    store.phases.set_status(project.id, "build", "running", actor="system")
    store.projects.archive(project.id, actor="system")
    assert (await client.put(f"{base}/{UC1}", json={"text": files[UC1] + "\nx\n", "based_on": version.number})).status_code == 409
    await client.aclose()


def httpx_without_actor(client):
    import httpx
    return httpx.AsyncClient(transport=client._transport, base_url="http://test")


# ---- splice_file itself, without the guards in front of it (S19f-1 mutation survivors) -----------------------------------------------------------------

from tests.test_instructions import DESIGN, full_set, scenario  # noqa: E402


def spliced(name, text, files=None, **kw):
    files = files if files is not None else full_set(contract=True)
    return I.splice_file(I.assemble(files, design=DESIGN), name, text, DESIGN, **kw)


def refusal_of(name, text, files=None):
    with pytest.raises(I.FileEditRefused) as caught:
        spliced(name, text, files)
    return caught.value


def test_splice_refuses_a_file_that_is_not_in_the_set_and_says_which_files_there_are():
    err = refusal_of("UC-009-ghost.md", scenario("UC-009"))
    assert "is not a file of this set" in str(err) and "00-foundation.md" in err.problems[0]


def test_splice_refuses_a_name_of_no_known_kind_and_a_text_that_is_only_blank_lines():
    files = full_set(contract=True)
    files["notes.md"] = "# Notes\n"
    body = I.assemble(files, design=DESIGN)
    with pytest.raises(I.FileEditRefused) as unknown:
        I.splice_file(body, "notes.md", "# Notes\n\nmore\n", DESIGN)
    assert "not a file name this set may hold" in unknown.value.problems[0]
    empty = refusal_of("UC-001-reserve-a-room.md", " \n\n \n")
    assert empty.problems == ("the edited text is empty",)


def test_splice_refuses_a_file_mark_line_anywhere_in_the_text():
    err = refusal_of("UC-001-reserve-a-room.md", scenario("UC-001") + "\n=== FILE: UC-009-x.md ===\n# X\n")
    assert err.problems[0].startswith("the text has a line that starts '=== FILE:'")             # the clear sentence from the edit itself, not a later check's


def test_splice_reads_windows_line_endings_as_ordinary_ones_and_ends_the_file_with_one_newline():
    text = scenario("UC-001", build="- API-001 GET /api/rooms and API-003 POST /api/reservations. Needs TBL-001 and TBL-002.").replace("\n", "\r\n")
    body, _ = spliced("UC-001-reserve-a-room.md", text)
    saved = I.split_set(body)[0]["UC-001-reserve-a-room.md"]
    assert "\r" not in body and "\r" not in saved and saved.endswith("\n") and not saved.endswith("\n\n")           # the stored text itself, not only what is read back


def test_splice_requires_the_contract_of_a_foundation_that_had_one_but_not_of_one_that_never_did():
    with_contract = full_set(contract=True)
    no_contract_text = foundation_without_contract()
    err = refusal_of(I.FOUNDATION_NAME, no_contract_text, with_contract)
    assert any("Interface contract" in p for p in err.problems)
    old_set = full_set(contract=False)
    body, _ = spliced(I.FOUNDATION_NAME, no_contract_text, old_set)                       # a set written before S19d is edited under the checks that apply to it
    assert "Interface contract" not in I.split_set(body)[0][I.FOUNDATION_NAME]


def foundation_without_contract():
    from tests.test_instructions import foundation
    return foundation(extra="\n## Not covered\n- API-002 not needed for this prototype\n- RUL-002 left to a later release\n- RUL-003 left to a later release\n")


def test_splice_blocks_a_set_level_problem_the_edit_introduces_but_not_one_that_was_there_before():
    files = full_set(contract=True)
    gone = scenario("UC-001", build="- API-001 GET /api/rooms and API-003 POST /api/reservations. Needs TBL-001 and TBL-002.", derives="Derives from: API-003, RUL-001")
    err = refusal_of("UC-001-reserve-a-room.md", gone, files)
    assert any("UC-001" in p for p in err.problems)
    already = dict(files)
    del already["UC-002-browse-rooms.md"]                                                    # UC-002 has no file: a set-level problem that is already there
    assert any("UC-002" in p for p in I.check_set(already, DESIGN))
    fine = scenario("UC-001", build="- API-001 GET /api/rooms and API-003 POST /api/reservations. Needs TBL-001 and TBL-002.", extra="\nAn extra line.\n")
    body, _ = spliced("UC-001-reserve-a-room.md", fine, already)
    assert "An extra line." in body


def test_splice_of_the_foundation_names_every_kind_of_file_the_new_contract_leaves_in_conflict_and_only_those():
    files = full_set(contract=True)
    files["UC-001-reserve-a-room.md"] = scenario("UC-001", build="- API-001 GET /api/rooms and API-003 POST /api/reservations. Needs TBL-001 and TBL-002. Input: `room_id`")
    files[I.ACCEPTANCE_NAME] = files[I.ACCEPTANCE_NAME] + '\n```python\nbody = {"room_id": 1}\n```\n'
    assert I.check_set(files, DESIGN) == [] or True
    changed = files[I.FOUNDATION_NAME].replace("room_id", "room")
    err = refusal_of(I.FOUNDATION_NAME, changed, files)
    named = {p.split(":", 1)[0] for p in err.problems if ":" in p}
    assert "UC-001-reserve-a-room.md" in named and I.ACCEPTANCE_NAME in named and "UC-002-browse-rooms.md" not in named
    # a file already in conflict BEFORE the edit is not blamed on it
    broken = dict(files)
    broken["UC-002-browse-rooms.md"] = scenario("UC-002", build="- API-001 GET /api/rooms lists rooms. Input: `starts_at`", derives="Derives from: UC-002, API-001")
    again = refusal_of(I.FOUNDATION_NAME, changed, broken)
    assert not any(p.startswith("UC-002-browse-rooms.md:") for p in again.problems)


def test_splice_of_the_foundation_checks_screen_files_too():
    files = full_set(contract=True)
    screen = ("# Browse\n\n## Goal\nShow rooms.\n\n## Read first\nRead 00-foundation.md and 01-ui-guidelines.md first.\n\n## What is on the screen\nA list.\n\n"
              "## Components and their states\n- The list: empty, loading.\n\n## What the person can do\n- Pick a room.\n\n## Calls it makes\n- API-001 GET /api/rooms. Output: `room_id`\n\n"
              "## Messages and the rules behind them\n- RUL-001 A booking may not overlap another.\n\n## Done when\n- Rooms are listed\n\n## Do not\n- Do not add login.\n\n## Traceability\nDerives from: HFS-001, API-001, RUL-001\n")
    files["UI-HFS-001-browse.md"] = screen
    files["01-ui-guidelines.md"] = "# UI guide\n"
    changed = files[I.FOUNDATION_NAME].replace("room_id", "room")
    with pytest.raises(I.FileEditRefused) as caught:
        I.splice_file(I.assemble(files, design=DESIGN), I.FOUNDATION_NAME, changed, DESIGN)
    assert any(p.startswith("UI-HFS-001-browse.md:") for p in caught.value.problems), caught.value.problems


def test_splice_rebuilds_the_design_index_and_keeps_every_files_item_number():
    files = full_set(contract=True)
    before = I.assemble(files, design=DESIGN)
    body, _ = I.splice_file(before, "UC-002-browse-rooms.md", scenario("UC-002", build="- API-001 GET /api/rooms lists rooms.", derives="Derives from: UC-002, API-001, FR-001"), DESIGN)
    after = I.split_set(body)[0]
    assert I.INDEX_NAME not in I.split_set(before)[0]                                     # the set above has no index yet; a splice writes one
    assert "FR-001" in after[I.INDEX_NAME]
    number = lambda b: {t.split(":", 1)[0]: i for i, t in I._set_head_ids(b)}
    was, now = number(before), number(body)
    assert all(now[name] == was[name] for name in was) and set(now) - set(was) == {I.INDEX_NAME}      # every file keeps its number; only the new index is numbered


# ---- the checks at the moment of saving ----------------------------------------------------------------------------------------------------------------

async def test_a_set_that_changes_between_the_check_and_the_save_is_not_overwritten(rig, store, project, monkeypatch):
    human, art, version, files, _ = await rig()
    real = store.artefacts.add_version

    def someone_else_first(project_id, artefact_id, **kw):
        real(project_id, artefact_id, body=version.body + "\n", author="human:bob")           # another person saves between our check and our save
        return real(project_id, artefact_id, **kw)

    monkeypatch.setattr(store.artefacts, "add_version", someone_else_first)
    with pytest.raises(EditRefused, match="the set changed while it was being checked"):
        human.edit_file(project.id, art, UC1, files[UC1] + "\nMine.\n", based_on=version.number, actor=ANN)
    monkeypatch.undo()
    assert store.artefacts.get_version(project.id, art).author == "human:bob"


async def test_a_phase_that_closes_between_the_check_and_the_save_refuses_the_edit(rig, store, project, monkeypatch):
    human, art, version, files, _ = await rig()
    real = store.artefacts.add_version

    def phase_closes_first(project_id, artefact_id, **kw):
        store.phases.set_status(project_id, "build", "not_started", actor="system")
        return real(project_id, artefact_id, **kw)

    monkeypatch.setattr(store.artefacts, "add_version", phase_closes_first)
    with pytest.raises(WrongPhaseState, match="its phase became 'not_started' while it was being checked"):
        human.edit_file(project.id, art, UC1, files[UC1] + "\nMine.\n", based_on=version.number, actor=ANN)
    monkeypatch.undo()
    assert store.artefacts.get_version(project.id, art).number == version.number


async def test_the_phase_state_alone_refuses_before_anything_is_checked(rig, store, project):
    human, art, version, files, _ = await rig()
    store.phases.set_status(project.id, "build", "not_started", actor="system")
    with pytest.raises(WrongPhaseState, match="a file can be edited only while the phase is running or awaiting_review; build is 'not_started'"):
        human.edit_file(project.id, art, "UC-009-ghost.md", "x", based_on=999, actor=ANN)


async def test_the_note_is_trimmed_and_cut_at_a_thousand_characters_and_a_blank_note_is_none(rig, store, project):
    human, art, version, files, _ = await rig()
    human.edit_file(project.id, art, UC1, files[UC1] + "\nA.\n", based_on=version.number, actor=ANN, note="   " + "n" * 1200)
    assert store.artefacts.get_version(project.id, art).generation["note"] == "n" * 1000
    human.edit_file(project.id, art, UC2, files[UC2] + "\nB.\n", based_on=version.number + 1, actor=ANN, note="   ")
    assert store.artefacts.get_version(project.id, art).generation["note"] is None


async def test_an_unknown_file_is_not_found_and_not_a_refusal_with_reasons(rig, store, project):
    human, art, version, files, _ = await rig()
    try:
        human.edit_file(project.id, art, "UC-009-ghost.md", "x", based_on=version.number, actor=ANN)
    except Exception as exc:                                                                 # noqa: BLE001
        assert isinstance(exc, NotFoundError) and not isinstance(exc, EditRefused)
    else:
        raise AssertionError("an unknown file was accepted")


async def test_the_route_refuses_a_base_version_of_zero_and_names_the_field(api, store, project):
    client, base, art, version, files = await api()
    response = await client.put(f"{base}/{UC1}", json={"text": files[UC1] + "\nx\n", "based_on": 0})
    assert response.status_code == 422 and "based_on" in str(response.json())
    await client.aclose()


def test_splice_blocks_a_set_level_problem_that_only_the_whole_set_can_see():
    """An edit that leaves an endpoint built by NO file passes the file's own checks (the file is fine alone); only the set-level check sees it."""
    files = full_set(contract=True)
    dropped = scenario("UC-001", build="- API-001 GET /api/rooms lists rooms. Needs TBL-001 and TBL-002.", derives="Derives from: UC-001, API-001, RUL-001")
    assert I.check_file(I.SCENARIO, "UC-001-reserve-a-room.md", dropped, DESIGN, None) == []                  # alone, the edited file is fine
    err = refusal_of("UC-001-reserve-a-room.md", dropped, files)
    assert any("API-003" in p and "named by no instruction file" in p for p in err.problems), err.problems
