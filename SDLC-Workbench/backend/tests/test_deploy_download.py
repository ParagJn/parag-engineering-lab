"""S21b: downloading the deployment plan and the release notes as Markdown and Word. The route reads saved text and makes a file; no model is called."""
from __future__ import annotations

import io

import httpx
import pytest
from docx import Document
from fastapi import FastAPI

from app.routes_deploy import router

pytestmark = pytest.mark.anyio
PLAN_V1 = "# Deployment plan\n\n## Steps\n- DPL-001 First. Derives from: COMP-001\n"
PLAN_V2 = PLAN_V1 + "- DPL-002 Second. Derives from: COMP-002\n"


@pytest.fixture
def api(store, project):
    app = FastAPI()
    app.include_router(router)
    app.state.store = store
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    def make(artefact_type="deployment_plan", prefix="DEP-PLN", phase="deploy", title="Deployment plan", bodies=(PLAN_V1, PLAN_V2)):
        art = store.artefacts.create(project.id, artefact_type=artefact_type, phase_key=phase, title=title, actor="system", prefix=prefix)
        for b in bodies:
            store.artefacts.add_version(project.id, art.id, body=b, author="agent:devops_engineer@m")
        return art

    return client, f"/api/projects/{project.id}/artefacts", make


async def test_the_markdown_is_the_saved_text_byte_for_byte_with_a_name_that_carries_the_version(api):
    client, base, make = api
    art = make()
    response = await client.get(f"{base}/{art.id}/download")
    assert response.status_code == 200 and response.content == PLAN_V2.rstrip("\n").encode("utf-8")                # the store keeps a body without its final newline; the download is that text exactly
    assert response.headers["content-type"] == "text/markdown; charset=utf-8" and response.headers["content-disposition"] == f'attachment; filename="{art.id}-v2.md"'
    await client.aclose()


async def test_the_word_file_is_made_from_that_same_text_and_named_for_the_version(api):
    client, base, make = api
    art = make()
    response = await client.get(f"{base}/{art.id}/download", params={"format": "docx"})
    assert response.status_code == 200 and response.headers["content-disposition"] == f'attachment; filename="{art.id}-v2.docx"'
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    doc = Document(io.BytesIO(response.content))
    assert [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")] == ["Deployment plan", "Steps"]
    assert [p.text for p in doc.paragraphs if p.style.name == "List Bullet"] == ["DPL-001 First. Derives from: COMP-001", "DPL-002 Second. Derives from: COMP-002"]
    assert doc.core_properties.title.startswith("Deployment plan - ") and doc.core_properties.subject == f"{art.id} version 2"
    await client.aclose()


async def test_an_earlier_version_can_be_downloaded_and_a_version_that_does_not_exist_is_not_found(api):
    client, base, make = api
    art = make()
    old = await client.get(f"{base}/{art.id}/download", params={"version": 1})
    assert old.content == PLAN_V1.rstrip("\n").encode() and 'filename="' + art.id + '-v1.md"' in old.headers["content-disposition"]
    docx = Document(io.BytesIO((await client.get(f"{base}/{art.id}/download", params={"version": 1, "format": "docx"})).content))
    assert "DPL-002" not in " ".join(p.text for p in docx.paragraphs)
    assert (await client.get(f"{base}/{art.id}/download", params={"version": 9})).status_code == 404
    assert (await client.get(f"{base}/{art.id}/download", params={"version": 0})).status_code == 422
    await client.aclose()


async def test_the_release_notes_can_be_downloaded_too_and_no_other_artefact_can(api):
    client, base, make = api
    notes = make("release_notes", "DEP-REL", title="Release notes", bodies=("# Release notes\n\n- REL-001 You can book a room.\n",))
    assert (await client.get(f"{base}/{notes.id}/download")).status_code == 200
    other = make("personas", "REQ-PER", "requirements", "Personas", bodies=("## Personas\n- PER-001 x\n",))
    refused = await client.get(f"{base}/{other.id}/download")
    assert refused.status_code == 422 and "the deployment plan, the release notes, the runbook and the hypercare plan can" in refused.json()["detail"] and "Personas" in refused.json()["detail"]
    await client.aclose()


async def test_the_verification_checklist_is_not_a_document_to_download_here(api):
    client, base, make = api
    checklist = make("deployment_verification", "DEP-VER", title="Deployment verification", bodies=("anything",))
    refused = await client.get(f"{base}/{checklist.id}/download")
    assert refused.status_code == 422 and "cannot be downloaded as a file here" in refused.json()["detail"]
    await client.aclose()


async def test_the_word_file_carries_the_time_the_version_was_saved_not_the_time_of_the_download(api, store, project):
    client, base, make = api
    art = make()
    saved = store.artefacts.get_version(project.id, art.id).created_at
    doc = Document(io.BytesIO((await client.get(f"{base}/{art.id}/download", params={"format": "docx"})).content))
    from datetime import datetime, timezone
    assert doc.core_properties.created.replace(tzinfo=timezone.utc) == datetime.fromisoformat(saved.replace("Z", "+00:00")).astimezone(timezone.utc).replace(microsecond=doc.core_properties.created.microsecond)
    assert doc.core_properties.created.year == int(saved[:4]) and doc.core_properties.created.month == int(saved[5:7])
    await client.aclose()


async def test_an_artefact_not_written_yet_unknown_ids_and_bad_formats_get_plain_answers(api, store, project):
    client, base, make = api
    empty = store.artefacts.create(project.id, artefact_type="deployment_plan", phase_key="deploy", title="Deployment plan", actor="system", prefix="DEP-PLN")
    gone = await client.get(f"{base}/{empty.id}/download")
    assert gone.status_code == 404 and "has not been written yet" in gone.json()["detail"]
    assert (await client.get(f"{base}/DEP-XXX-999/download")).status_code == 404
    assert (await client.get(f"{base}/bad%20id/download")).status_code == 422
    art = make()
    for fmt in ("pdf", "html", "", "MD"):
        assert (await client.get(f"{base}/{art.id}/download", params={"format": fmt})).status_code == 422, fmt
    assert (await client.get(f"/api/projects/nope/artefacts/{art.id}/download")).status_code == 404
    await client.aclose()


async def test_downloading_changes_nothing_and_needs_no_name_and_an_archived_project_can_still_be_read(api, store, project):
    client, base, make = api
    art = make()
    before = store.artefacts.get(project.id, art.id).latest_version
    store.projects.archive(project.id, actor="system")
    assert (await client.get(f"{base}/{art.id}/download")).status_code == 200 and (await client.get(f"{base}/{art.id}/download", params={"format": "docx"})).status_code == 200
    assert store.artefacts.get(project.id, art.id).latest_version == before
    await client.aclose()


async def test_markup_in_the_saved_text_is_not_carried_into_the_word_file(api):
    client, base, make = api
    art = make(bodies=("# Plan\n\n<script>alert(1)</script>\n\n[x](javascript:alert(1)) **ok**\n",))
    doc = Document(io.BytesIO((await client.get(f"{base}/{art.id}/download", params={"format": "docx"})).content))
    assert "script" not in doc.element.xml and "javascript" not in doc.element.xml and "alert" not in doc.element.xml
    await client.aclose()


# ---- S22b: the runbook and the hypercare plan download the same way; the sign-off and the parked ones do not -------------------------------------------------

@pytest.mark.parametrize("artefact_type, prefix, title", [("runbook", "HND-RUN", "Runbook"), ("hypercare_plan", "HND-HYP", "Hypercare plan")])
async def test_the_runbook_and_the_hypercare_plan_download_as_markdown_and_as_word(api, artefact_type, prefix, title):
    client, base, make = api
    art = make(artefact_type, prefix, "handover", title, bodies=(f"# {title}\n\n## Overview\nFrom the design.\n\n- {prefix[-3:]}-001 An entry. Proposed: weekly.\n",))
    md = await client.get(f"{base}/{art.id}/download")
    assert md.status_code == 200 and md.headers["content-disposition"] == f'attachment; filename="{art.id}-v1.md"' and md.content.decode().startswith(f"# {title}")
    word = await client.get(f"{base}/{art.id}/download", params={"format": "docx"})
    assert word.status_code == 200 and word.headers["content-disposition"] == f'attachment; filename="{art.id}-v1.docx"'
    doc = Document(io.BytesIO(word.content))
    assert [p.text for p in doc.paragraphs if p.style.name.startswith("Heading")] == [title, "Overview"] and doc.core_properties.title.startswith(f"{title} - ")
    await client.aclose()


@pytest.mark.parametrize("artefact_type, prefix", [("handover_signoff", "HND-SGN"), ("support_guide", "HND-SUP"), ("slos_alerts", "HND-SLO"), ("kt_pack", "HND-KT")])
async def test_the_signoff_and_the_three_parked_handover_artefacts_are_not_documents_to_download(api, artefact_type, prefix):
    client, base, make = api
    art = make(artefact_type, prefix, "handover", "Something", bodies=("anything",))
    refused = await client.get(f"{base}/{art.id}/download")
    assert refused.status_code == 422 and "cannot be downloaded as a file here" in refused.json()["detail"]
    await client.aclose()


def test_the_downloadable_types_are_exactly_the_four_documents_an_agent_writes_for_the_last_two_phases():
    from app.routes_deploy import DOWNLOADABLE
    assert DOWNLOADABLE == ("deployment_plan", "release_notes", "runbook", "hypercare_plan")
