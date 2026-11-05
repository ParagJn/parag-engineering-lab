"""S23 Part C: storing a project's Word templates. Real .docx packages are built in memory; every file goes under tmp_path, and the real backend/data/Templates is never touched."""
from __future__ import annotations

import io
import os
import stat
import zipfile

import httpx
import pytest
from docx import Document

from app.main import create_app
from app.templates import store as T

pytestmark = pytest.mark.anyio


# ---- real Word files, built in memory ------------------------------------------------------------------------------------------------------------

def make_docx(*, toc_field: bool = False, toc_simple: bool = False, toc_block: bool = False, text: str = "Hello") -> bytes:
    doc = Document()
    doc.add_heading("Title", level=1)
    doc.add_paragraph(text)
    body = doc.element.body
    from docx.oxml import parse_xml
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    if toc_field:
        body.insert(0, parse_xml(f'<w:p {ns}><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> TOC \\o "1-3" \\h \\z \\u </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>Contents</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>'))
    if toc_simple:
        body.insert(0, parse_xml(f'<w:p {ns}><w:fldSimple w:instr=" TOC \\o &quot;1-3&quot; "><w:r><w:t>Contents</w:t></w:r></w:fldSimple></w:p>'))
    if toc_block:
        body.insert(0, parse_xml(f'<w:sdt {ns}><w:sdtPr><w:docPartObj><w:docPartGallery w:val="Table of Contents"/><w:docPartUnique/></w:docPartObj></w:sdtPr><w:sdtContent><w:p><w:r><w:t>Contents</w:t></w:r></w:p></w:sdtContent></w:sdt>'))
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def rezip(data: bytes, *, add: dict[str, bytes] | None = None, drop: tuple[str, ...] = (), content_types: bytes | None = None) -> bytes:
    """The same package with parts added or removed, to make a macro file, a template file, or a damaged one."""
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            if item.filename in drop:
                continue
            body = src.read(item.filename)
            if item.filename == "[Content_Types].xml" and content_types is not None:
                body = content_types
            dst.writestr(item.filename, body)
        for name, body in (add or {}).items():
            dst.writestr(name, body)
    return out.getvalue()


PLAIN = make_docx()
WITH_TOC = make_docx(toc_field=True)


# ---- what is accepted ----------------------------------------------------------------------------------------------------------------------------------

def test_a_plain_word_document_is_accepted():
    T.check_docx(PLAIN)
    T.check_docx(WITH_TOC)


@pytest.mark.parametrize("data, sentence", [
    (b"", "the file is empty"),
    (b"just some text", "it is not a Word package"),
    (b"PK\x03\x04 broken", "it is not a Word package"),
])
def test_something_that_is_not_a_zip_is_refused_with_a_sentence(data, sentence):
    with pytest.raises(T.TemplateRefused, match=sentence):
        T.check_docx(data)


def test_a_zip_whose_listing_is_readable_but_whose_contents_are_damaged_is_refused():
    data = bytearray(PLAIN)
    start = data.find(b"word/document.xml")
    assert start > 0
    for i in range(start + 60, min(start + 160, len(data))):                 # flip bytes inside the first stored file's compressed data
        data[i] ^= 0xFF
    with pytest.raises(T.TemplateRefused, match="damaged or is not a readable Word package"):
        T.check_docx(bytes(data))


def test_a_zip_that_is_not_a_word_document_is_refused():
    other = io.BytesIO()
    with zipfile.ZipFile(other, "w") as z:
        z.writestr("hello.txt", "hi")
    with pytest.raises(T.TemplateRefused, match="no document body"):
        T.check_docx(other.getvalue())
    with pytest.raises(T.TemplateRefused, match="no document body"):
        T.check_docx(rezip(PLAIN, drop=("word/document.xml",)))


def test_a_document_with_a_macro_part_an_embedded_object_or_a_macro_content_type_is_refused():
    for extra, why in ((("word/vbaProject.bin", b"x"), "macros"), (("word/embeddings/oleObject1.bin", b"x"), "macros"), (("word/activeX/activeX1.xml", b"x"), "macros"), (("customUI/customUI.xml", b"x"), "macros"), (("word/vbaData.xml", b"x"), "macros")):
        with pytest.raises(T.TemplateRefused, match=why):
            T.check_docx(rezip(PLAIN, add={extra[0]: extra[1]}))
    types = zipfile.ZipFile(io.BytesIO(PLAIN)).read("[Content_Types].xml").replace(b"document.main+xml", b"document.macroEnabled.main+xml")
    with pytest.raises(T.TemplateRefused, match="macro-enabled"):
        T.check_docx(rezip(PLAIN, content_types=types))


def test_a_dotx_template_file_is_refused_with_a_sentence_that_says_what_to_do():
    types = zipfile.ZipFile(io.BytesIO(PLAIN)).read("[Content_Types].xml").replace(b"document.main+xml", b"template.main+xml")
    with pytest.raises(T.TemplateRefused, match=r"\(\.dotx\); save it as a Word document"):
        T.check_docx(rezip(PLAIN, content_types=types))


def test_a_file_over_the_size_limit_or_one_that_expands_too_far_is_refused():
    with pytest.raises(T.TemplateRefused, match="larger than the 5 MB limit"):
        T.check_docx(PLAIN + b"\0" * T.MAX_TEMPLATE_BYTES)
    bomb = rezip(PLAIN, add={"word/big.xml": b"0" * (T.MAX_UNPACKED_BYTES + 1)})
    assert len(bomb) < T.MAX_TEMPLATE_BYTES
    with pytest.raises(T.TemplateRefused, match="expands to more than 50 MB"):
        T.check_docx(bomb)


def test_a_document_with_too_many_parts_is_refused():
    many = rezip(PLAIN, add={f"word/p{i}.xml": b"x" for i in range(T.MAX_PARTS + 1)})
    with pytest.raises(T.TemplateRefused, match="too many parts"):
        T.check_docx(many)


# ---- the table of contents ---------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["toc_field", "toc_simple", "toc_block"])
def test_each_way_word_keeps_a_table_of_contents_is_recognised(kind):
    assert T.table_of_contents(make_docx(**{kind: True})) is True


def test_a_document_without_one_has_none_and_a_word_that_only_looks_like_it_does_not_count():
    assert T.table_of_contents(PLAIN) is False
    assert T.table_of_contents(make_docx(text="TOC and Table of Contents are only words here")) is False
    assert T.table_of_contents(b"not a zip") is False
    assert T.table_of_contents(rezip(PLAIN, add={"word/document.xml": b"<broken"}, drop=("word/document.xml",))) is False


def test_a_field_whose_name_only_starts_with_toc_is_not_a_table_of_contents():
    odd = make_docx()
    z = zipfile.ZipFile(io.BytesIO(odd)).read("word/document.xml").replace(b"</w:body>", b'<w:p><w:r><w:instrText> TOCX other </w:instrText></w:r></w:p></w:body>')
    assert T.table_of_contents(rezip(odd, add={"word/document.xml": z}, drop=("word/document.xml",))) is False


# ---- the folder ------------------------------------------------------------------------------------------------------------------------------------------

def test_a_template_is_stored_as_the_original_bytes_under_the_project_and_the_category(tmp_path):
    info = T.save(tmp_path, "p1", "release_notes", WITH_TOC)
    path = tmp_path / "p1" / "release_notes.docx"
    assert path.read_bytes() == WITH_TOC and info.category == "release_notes" and info.label == "Release notes" and info.size == len(WITH_TOC) and info.has_toc is True
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600 and stat.S_IMODE(os.stat(path.parent).st_mode) == 0o700


def test_a_second_upload_for_the_same_category_replaces_the_first_and_leaves_no_temporary_file(tmp_path):
    T.save(tmp_path, "p1", "runbook", PLAIN)
    second = T.save(tmp_path, "p1", "runbook", WITH_TOC)
    assert (tmp_path / "p1" / "runbook.docx").read_bytes() == WITH_TOC and second.has_toc is True
    assert sorted(p.name for p in (tmp_path / "p1").iterdir()) == ["runbook.docx"]


def test_each_project_has_its_own_folder_and_one_projects_template_is_not_anothers(tmp_path):
    T.save(tmp_path, "p1", "runbook", PLAIN); T.save(tmp_path, "p2", "runbook", WITH_TOC)
    assert T.read(tmp_path, "p1", "runbook") == PLAIN and T.read(tmp_path, "p2", "runbook") == WITH_TOC
    assert [t.category for t in T.listing(tmp_path, "p1")] == ["runbook"] and T.listing(tmp_path, "p3") == []


def test_a_refused_upload_stores_nothing_and_leaves_an_earlier_template_alone(tmp_path):
    T.save(tmp_path, "p1", "runbook", PLAIN)
    with pytest.raises(T.TemplateRefused):
        T.save(tmp_path, "p1", "runbook", b"not a word file")
    assert T.read(tmp_path, "p1", "runbook") == PLAIN and sorted(p.name for p in (tmp_path / "p1").iterdir()) == ["runbook.docx"]
    with pytest.raises(T.TemplateRefused):
        T.save(tmp_path, "p9", "runbook", b"nope")
    assert not (tmp_path / "p9").exists()


@pytest.mark.parametrize("project_id", ["", "..", "../x", "a/b", "a\\b", ".", "x" * 65, "p 1", "p\x00", "/etc"])
def test_a_project_id_that_could_point_outside_the_templates_folder_is_refused(tmp_path, project_id):
    with pytest.raises(T.TemplateRefused, match="not a project"):
        T.save(tmp_path, project_id, "runbook", PLAIN)
    with pytest.raises(T.TemplateRefused):
        T.listing(tmp_path, project_id)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("category", ["", "..", "../runbook", "runbook.docx", "RUNBOOK", "other", "runbook/x"])
def test_a_document_type_that_is_not_one_of_the_six_is_refused_and_names_the_six(tmp_path, category):
    with pytest.raises(T.TemplateRefused, match="there is no document type.*deployment_plan.*handover_signoff"):
        T.save(tmp_path, "p1", category, PLAIN)
    with pytest.raises(T.TemplateRefused):
        T.read(tmp_path, "p1", category)
    with pytest.raises(T.TemplateRefused):
        T.remove(tmp_path, "p1", category)


def test_there_are_six_document_types_in_a_fixed_order_with_plain_labels():
    assert list(T.CATEGORIES) == ["deployment_plan", "release_notes", "runbook", "hypercare_plan", "deployment_verification", "handover_signoff"]
    assert list(T.CATEGORIES.values()) == ["Deployment plan", "Release notes", "Runbook", "Hypercare plan", "Deployment verification report", "Handover sign-off report"]


def test_the_listing_is_in_the_fixed_order_not_the_order_they_were_uploaded(tmp_path):
    T.save(tmp_path, "p1", "handover_signoff", PLAIN); T.save(tmp_path, "p1", "deployment_plan", PLAIN)
    assert [t.category for t in T.listing(tmp_path, "p1")] == ["deployment_plan", "handover_signoff"]


def test_an_info_says_whether_a_table_of_contents_was_found_in_plain_words(tmp_path):
    with_toc, without = T.save(tmp_path, "p1", "runbook", WITH_TOC), T.save(tmp_path, "p1", "release_notes", PLAIN)
    assert with_toc.has_toc_note == "It has a table of contents, so downloads of this document can use it."
    assert without.has_toc_note == "No table of contents was found in this file, so downloads will use the standard layout."
    assert T.payload(without) == {"category": "release_notes", "label": "Release notes", "size": len(PLAIN), "uploaded_at": without.uploaded_at, "has_toc": False, "toc_note": without.has_toc_note}
    assert without.uploaded_at.endswith("Z") and len(without.uploaded_at) == 20


def test_removing_a_template_removes_only_that_one_and_removing_a_missing_one_is_a_plain_error(tmp_path):
    T.save(tmp_path, "p1", "runbook", PLAIN); T.save(tmp_path, "p1", "release_notes", PLAIN)
    T.remove(tmp_path, "p1", "runbook")
    assert [t.category for t in T.listing(tmp_path, "p1")] == ["release_notes"]
    with pytest.raises(T.TemplateMissing, match="there is no template for Runbook in this project"):
        T.remove(tmp_path, "p1", "runbook")
    with pytest.raises(T.TemplateMissing, match="there is no template for Runbook in this project"):
        T.read(tmp_path, "p1", "runbook")


def test_a_failure_while_swapping_the_file_in_leaves_the_old_template_and_no_temporary_file(tmp_path, monkeypatch):
    T.save(tmp_path, "p1", "runbook", PLAIN)
    monkeypatch.setattr(os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError):
        T.save(tmp_path, "p1", "runbook", WITH_TOC)
    assert T.read(tmp_path, "p1", "runbook") == PLAIN and sorted(p.name for p in (tmp_path / "p1").iterdir()) == ["runbook.docx"]


# ---- over HTTP --------------------------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def world(make_settings, tmp_path):
    app = create_app(make_settings(admin_name="Root"))
    project = app.state.store.projects.create(name="P", actor="system")
    return app, project


def client(app, name=None):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", headers={"X-Actor": name} if name else {})


def files(data: bytes, name: str = "t.docx"):
    return {"file": (name, data, T.DOCX_TYPE)}


async def test_the_templates_folder_is_beside_the_database_so_a_test_app_never_uses_the_real_one(world, tmp_path):
    app, project = world
    assert app.state.templates_root == app.state.settings.db_path.parent / "Templates" and str(tmp_path) in str(app.state.templates_root)
    assert app.state.settings.templates_path.name == "Templates"


async def test_a_new_project_lists_the_six_types_with_no_template_and_says_what_a_template_is(world):
    app, project = world
    c = client(app, "Root")
    body = (await c.get(f"/api/projects/{project.id}/templates")).json()
    assert [x["category"] for x in body["categories"]] == list(T.CATEGORIES) and all(x["template"] is None for x in body["categories"])
    assert body["can_change"] is True and body["max_mb"] == 5 and "table of contents" in body["note"]
    await c.aclose()


async def test_reading_needs_no_name_and_an_unknown_project_is_a_404(world):
    app, project = world
    c = client(app)
    assert (await c.get(f"/api/projects/{project.id}/templates")).status_code == 200 and (await c.get(f"/api/projects/{project.id}/templates")).json()["can_change"] is False
    assert (await c.get("/api/projects/nope/templates")).status_code == 404 and (await c.get("/api/projects/nope/templates/runbook/download")).status_code == 404
    await c.aclose()


async def test_an_upload_is_stored_listed_audited_and_can_be_downloaded_byte_for_byte(world):
    app, project = world
    c = client(app, "Root")
    r = await c.post(f"/api/projects/{project.id}/templates/release_notes", files=files(WITH_TOC))
    body = r.json()
    assert r.status_code == 201 and body["saved"]["category"] == "release_notes" and body["saved"]["has_toc"] is True
    mine = next(x for x in body["categories"] if x["category"] == "release_notes")["template"]
    assert mine["size"] == len(WITH_TOC) and mine["toc_note"].startswith("It has a table of contents")
    assert (app.state.templates_root / project.id / "release_notes.docx").read_bytes() == WITH_TOC
    down = await c.get(f"/api/projects/{project.id}/templates/release_notes/download")
    assert down.status_code == 200 and down.content == WITH_TOC and down.headers["content-type"] == T.DOCX_TYPE and down.headers["content-disposition"] == 'attachment; filename="release_notes-template.docx"'
    [event] = [a for a in app.state.store.audit.list(project.id) if a.action == "template.uploaded"]
    assert event.actor == "human:Root" and event.target_id == f"{project.id}/release_notes" and event.detail == {"category": "release_notes", "size": len(WITH_TOC), "has_toc": True}
    await c.aclose()


async def test_a_second_upload_replaces_the_first(world):
    app, project = world
    c = client(app, "Root")
    await c.post(f"/api/projects/{project.id}/templates/runbook", files=files(PLAIN))
    r = await c.post(f"/api/projects/{project.id}/templates/runbook", files=files(WITH_TOC))
    assert r.json()["saved"]["has_toc"] is True and (await c.get(f"/api/projects/{project.id}/templates/runbook/download")).content == WITH_TOC
    assert len([a for a in app.state.store.audit.list(project.id) if a.action == "template.uploaded"]) == 2
    await c.aclose()


async def test_only_a_project_manager_or_an_administrator_can_change_templates_once_there_is_a_list(world):
    app, project = world
    users = app.state.store.users
    users.add("Pam", ["Project Manager"], actor="human:Root"); users.add("Ann", ["Architect", "Technical Lead"], actor="human:Root"); users.add("Off", ["Project Manager"], actor="human:Root")
    users.set_active("Off", False, actor="human:Root")
    url = f"/api/projects/{project.id}/templates/runbook"
    for who in ("Ann", "Stranger", "Off"):
        c = client(app, who)
        r = await c.post(url, files=files(PLAIN))
        assert r.status_code == 403 and "only a Project Manager or an Administrator" in r.json()["detail"], who
        assert (await c.delete(url)).status_code == 403 and (await c.get(f"/api/projects/{project.id}/templates")).json()["can_change"] is False
        await c.aclose()
    assert not (app.state.templates_root / project.id).exists()
    for who in ("Pam", "root"):
        c = client(app, who)
        assert (await c.post(url, files=files(PLAIN))).status_code == 201 and (await c.get(f"/api/projects/{project.id}/templates")).json()["can_change"] is True
        await c.aclose()


async def test_anyone_with_a_name_may_change_templates_while_nobody_is_on_the_list_but_a_missing_name_is_refused(make_settings):
    app = create_app(make_settings())
    project = app.state.store.projects.create(name="P", actor="system")
    assert app.state.store.users.count_active() == 0
    nameless = client(app)
    assert (await nameless.post(f"/api/projects/{project.id}/templates/runbook", files=files(PLAIN))).status_code == 400
    await nameless.aclose()
    c = client(app, "Anyone")
    assert (await c.post(f"/api/projects/{project.id}/templates/runbook", files=files(PLAIN))).status_code == 201
    await c.aclose()


async def test_a_refused_file_is_a_422_with_the_sentence_and_nothing_is_stored_or_audited(world):
    app, project = world
    c = client(app, "Root")
    url = f"/api/projects/{project.id}/templates/runbook"
    r = await c.post(url, files=files(b"plain text pretending", "t.docx"))
    assert r.status_code == 422 and "not a Word document" in r.json()["detail"]
    r = await c.post(url, files=files(rezip(PLAIN, add={"word/vbaProject.bin": b"x"})))
    assert r.status_code == 422 and "macros" in r.json()["detail"]
    assert not (app.state.templates_root / project.id).exists() and not [a for a in app.state.store.audit.list(project.id) if a.action == "template.uploaded"]
    await c.aclose()


@pytest.mark.parametrize("name", ["t.dotx", "t.docm", "t.doc", "t.pdf", "t", "", "t.docx.exe"])
async def test_only_a_name_ending_in_docx_is_accepted(world, name):
    app, project = world
    c = client(app, "Root")
    r = await c.post(f"/api/projects/{project.id}/templates/runbook", files=files(PLAIN, name or "x"))
    assert r.status_code == 422, name
    await c.aclose()


async def test_an_unknown_type_is_a_422_that_names_the_six_and_a_path_in_the_type_reaches_nothing(world):
    app, project = world
    c = client(app, "Root")
    r = await c.post(f"/api/projects/{project.id}/templates/other", files=files(PLAIN))
    assert r.status_code == 422 and "there is no document type 'other'" in r.json()["detail"]
    assert (await c.post(f"/api/projects/{project.id}/templates/..%2F..%2Fx", files=files(PLAIN))).status_code in (404, 422)
    assert not (app.state.templates_root / project.id).exists()
    await c.aclose()


async def test_the_size_limit_is_checked_before_the_whole_upload_is_read(world):
    app, project = world
    c = client(app, "Root")
    r = await c.post(f"/api/projects/{project.id}/templates/runbook", files=files(PLAIN + b"\0" * (T.MAX_TEMPLATE_BYTES + 10)))
    assert r.status_code == 422 and "larger than the 5 MB limit" in r.json()["detail"]
    await c.aclose()


async def test_removing_a_template_works_is_audited_and_a_second_removal_is_a_404(world):
    app, project = world
    c = client(app, "Root")
    url = f"/api/projects/{project.id}/templates/runbook"
    await c.post(url, files=files(PLAIN))
    r = await c.delete(url)
    assert r.status_code == 200 and next(x for x in r.json()["categories"] if x["category"] == "runbook")["template"] is None
    assert [a.detail for a in app.state.store.audit.list(project.id) if a.action == "template.removed"] == [{"category": "runbook"}]
    again = await c.delete(url)
    assert again.status_code == 404 and "there is no template for Runbook" in again.json()["detail"]
    assert (await c.get(f"{url}/download")).status_code == 404
    await c.aclose()


async def test_an_archived_project_can_be_read_and_downloaded_from_but_not_changed(world):
    app, project = world
    c = client(app, "Root")
    url = f"/api/projects/{project.id}/templates/runbook"
    await c.post(url, files=files(PLAIN))
    app.state.store.projects.archive(project.id, actor="system")
    assert (await c.get(f"/api/projects/{project.id}/templates")).status_code == 200 and (await c.get(f"{url}/download")).status_code == 200
    assert (await c.post(url, files=files(WITH_TOC))).status_code == 409 and (await c.delete(url)).status_code == 409
    assert T.read(app.state.templates_root, project.id, "runbook") == PLAIN
    await c.aclose()


async def test_one_projects_templates_are_not_visible_in_another_project(world):
    app, project = world
    other = app.state.store.projects.create(name="Other", actor="system")
    c = client(app, "Root")
    await c.post(f"/api/projects/{project.id}/templates/runbook", files=files(PLAIN))
    body = (await c.get(f"/api/projects/{other.id}/templates")).json()
    assert all(x["template"] is None for x in body["categories"]) and (await c.get(f"/api/projects/{other.id}/templates/runbook/download")).status_code == 404
    await c.aclose()


async def test_a_template_does_not_change_how_any_document_is_downloaded(world):
    """This step only stores. A Word download of a document is identical with and without a template in the project."""
    app, project = world
    store = app.state.store
    art = store.artefacts.create(project.id, artefact_type="release_notes", phase_key="deploy", title="Release notes", actor="system", prefix="DEP-REL")
    store.artefacts.add_version(project.id, art.id, body="# Release notes\n\n- REL-001 You can book a room.\n", author="human:seed")
    c = client(app, "Root")
    before = (await c.get(f"/api/projects/{project.id}/artefacts/{art.id}/download", params={"format": "docx"})).content
    await c.post(f"/api/projects/{project.id}/templates/release_notes", files=files(WITH_TOC))
    after = (await c.get(f"/api/projects/{project.id}/artefacts/{art.id}/download", params={"format": "docx"})).content
    assert before and Document(io.BytesIO(before)).paragraphs[0].text == Document(io.BytesIO(after)).paragraphs[0].text == "Release notes"
    assert [p.text for p in Document(io.BytesIO(before)).paragraphs] == [p.text for p in Document(io.BytesIO(after)).paragraphs]
    await c.aclose()


def test_the_real_templates_folder_is_never_used_by_a_test_app(make_settings):
    app = create_app(make_settings())
    real = os.path.join(os.path.dirname(__file__), "..", "data", "Templates")
    assert os.path.realpath(str(app.state.templates_root)) != os.path.realpath(real)


# ---- the survivors of the first sweep -------------------------------------------------------------------------------------------------------------

def test_a_package_with_no_content_types_part_is_not_a_word_document():
    with pytest.raises(T.TemplateRefused, match="no document body"):
        T.check_docx(rezip(PLAIN, drop=("[Content_Types].xml",)))


def test_the_listing_is_in_the_fixed_order_even_when_a_later_type_is_the_smaller_file(tmp_path):
    small = make_docx(text="x")
    big = make_docx(text="y" * 5000)
    assert len(big) > len(small)
    T.save(tmp_path, "p1", "deployment_plan", big); T.save(tmp_path, "p1", "handover_signoff", small)                    # the first type in the order is the BIGGER file
    assert [t.category for t in T.listing(tmp_path, "p1")] == ["deployment_plan", "handover_signoff"]


async def test_a_project_manager_alone_can_change_templates_and_an_administrator_alone_can_too(world):
    app, project = world
    users = app.state.store.users
    users.add("Pam", ["Project Manager"], actor="human:Root"); users.add("Adam", ["Administrator"], actor="human:Root")
    for who in ("Pam", "Adam"):
        c = client(app, who)
        assert (await c.get(f"/api/projects/{project.id}/templates")).json()["can_change"] is True, who
        assert (await c.post(f"/api/projects/{project.id}/templates/runbook", files=files(PLAIN))).status_code == 201, who
        await c.aclose()


@pytest.mark.parametrize("name", ["t.DOCX", "T.Docx", "Report.DocX"])
async def test_a_name_ending_docx_in_any_case_is_accepted(world, name):
    app, project = world
    c = client(app, "Root")
    assert (await c.post(f"/api/projects/{project.id}/templates/runbook", files=files(PLAIN, name))).status_code == 201, name
    await c.aclose()


async def test_an_upload_over_the_limit_is_refused_without_the_whole_file_being_read(world, monkeypatch):
    """The server asks for one byte more than the limit and stops: a huge upload is never read in full."""
    from starlette.datastructures import UploadFile as U
    asked: list[int] = []
    real = U.read

    async def spy(self, size=-1):
        asked.append(size)
        return await real(self, size)

    monkeypatch.setattr(U, "read", spy)
    app, project = world
    c = client(app, "Root")
    r = await c.post(f"/api/projects/{project.id}/templates/runbook", files=files(PLAIN + b"\0" * (T.MAX_TEMPLATE_BYTES + 10)))
    assert r.status_code == 422 and asked == [T.MAX_TEMPLATE_BYTES + 1]
    await c.aclose()
