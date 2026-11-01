"""The scanner at every place text enters the system: an agent's reply, a person's edit, the repository, a review, a document."""
from __future__ import annotations

import json
import sqlite3

import pytest

from app.agents.errors import OutputInvalid
from app.guardrails.scan import SecretRefused
from app.review.errors import EditRefused
from app.review.human import HumanActions
from app.review.prompt import load_rubric
from app.review.service import ReviewService
from app.llm.types import ProviderResponse, Usage

from . import _fakes as F
from .test_agent_runtime import PERSONA_SECTIONS, PERSON, catalogue, chain_to_requirements, ok, reply, rig  # noqa: F401  (fixtures)
from .test_review_service import REVIEW_CLEAN, review_reply, rig as review_rig, write_personas  # noqa: F401

pytestmark = pytest.mark.anyio

OWN_KEY = F.join("sk-test-", "own-", "ica-key-9999")


def personas_with(text: str) -> dict[str, str]:
    return {"Personas": f"- PER-001 Staff member. {text} Derives from: SET-CHR-001"}


def every_text_in_the_database(store) -> str:
    """All stored text, from every table, as one string: the place a leaked value would have to be."""
    parts = []
    with store.db.read() as conn:
        for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'").fetchall():
            for row in conn.execute(f'SELECT * FROM "{name}"').fetchall():
                parts.append(" ".join(str(v) for v in tuple(row)))
    return "\n".join(parts)


# ---- an agent's reply -------------------------------------------------------------------------------------------------------

async def test_a_reply_with_a_secret_is_sent_back_with_a_reason_that_does_not_contain_it_and_the_clean_reply_is_saved(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    leaky = ok(PERSONA_SECTIONS, items=personas_with(f"Key {F.AWS_KEY}."))
    clean = ok(PERSONA_SECTIONS, items=personas_with("Key withheld."))
    provider.queue("m-sonnet", leaky, clean)
    result = await runtime.run(project.id, "personas")

    assert result.attempts == 2
    told = provider.calls[-1].request.messages[-1].content
    assert "this looks like a cloud access key (rule aws_key_id)" in told and "line 4" in told or "line 3" in told or "under 'Personas'" in told
    assert F.AWS_KEY not in told.split("Your reply could not be accepted")[1].split("Write the complete corrected")[0]   # the REASON has no value
    body = store.artefacts.get_version(project.id, result.artefact_id).body
    assert F.AWS_KEY not in body and "Key withheld." in body


async def test_a_secret_reason_comes_before_every_other_problem_so_a_long_list_cannot_cut_it_off(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    bad = reply(["Overview"], items={"Overview": f"oops {F.AWS_KEY}"})            # also missing most required sections
    provider.queue("m-sonnet", ProviderResponse(bad, Usage(10, 10), "stop"), ok(PERSONA_SECTIONS, items=PERSONA_ITEMS_CLEAN))
    await runtime.run(project.id, "personas")
    first_problem = store.artefacts.get_version(project.id, "REQ-PER-001").generation["repair_reasons"][0]["problems"][0]
    assert "(rule aws_key_id)" in first_problem


PERSONA_ITEMS_CLEAN = {"Personas": "- PER-001 Staff member. Derives from: SET-CHR-001"}


async def test_three_replies_that_all_contain_a_secret_fail_with_the_reasons_and_save_nothing(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", *[ok(PERSONA_SECTIONS, items=personas_with(F.AWS_KEY))] * 3)
    with pytest.raises(OutputInvalid, match=r"rule aws_key_id") as caught:
        await runtime.run(project.id, "personas")
    assert F.AWS_KEY not in str(caught.value) and all(F.AWS_KEY not in p for p in caught.value.problems)
    assert store.artefacts.list(project.id, phase_key="requirements") == []
    assert F.AWS_KEY not in every_text_in_the_database(store)


async def test_the_repair_reasons_kept_with_a_version_never_contain_the_value(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=personas_with(F.JWT)), ok(PERSONA_SECTIONS, items=PERSONA_ITEMS_CLEAN))
    await runtime.run(project.id, "personas")
    kept = json.dumps(store.artefacts.get_version(project.id, "REQ-PER-001").generation["repair_reasons"])
    assert "(rule jwt)" in kept and F.JWT not in kept and "eyJ" not in kept


async def test_a_configured_credential_in_a_reply_is_caught_and_repaired(make_settings, rig, store, project):
    runtime, provider, engine = rig(ibm_ica_api_key=OWN_KEY)
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=personas_with(f"Uses {OWN_KEY}.")), ok(PERSONA_SECTIONS, items=PERSONA_ITEMS_CLEAN))
    result = await runtime.run(project.id, "personas")
    assert result.attempts == 2 and OWN_KEY not in every_text_in_the_database(store).replace(OWN_KEY + "-never", "")
    assert "(rule configured_credential)" in json.dumps(store.artefacts.get_version(project.id, "REQ-PER-001").generation["repair_reasons"])


async def test_personal_data_is_saved_with_a_flag_not_refused(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=personas_with(f"Contact {F.EMAIL} or {F.PHONE_INTL}.")))
    result = await runtime.run(project.id, "personas")
    assert result.attempts == 1 and result.flags == 2
    flags = store.artefacts.get_version(project.id, result.artefact_id).generation["guardrails"]
    assert sorted(f["rule"] for f in flags) == ["email", "phone"] and {f["class"] for f in flags} == {"personal"}
    assert all(f["heading"] == "Personas" and f["line"] > 0 and set(f) == {"rule", "class", "line", "heading", "length"} for f in flags)
    assert F.EMAIL in store.artefacts.get_version(project.id, result.artefact_id).body                  # the TEXT is the person's; the flag has no value
    assert F.EMAIL not in json.dumps(flags) and F.PHONE_INTL not in json.dumps(flags)


async def test_a_clean_artefact_stores_an_empty_findings_list(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=PERSONA_ITEMS_CLEAN))
    result = await runtime.run(project.id, "personas")
    assert result.flags == 0 and store.artefacts.get_version(project.id, result.artefact_id).generation["guardrails"] == []


async def test_the_stored_findings_cannot_be_edited_afterwards(rig, store, project):
    runtime, provider, engine = rig()
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=PERSONA_ITEMS_CLEAN))
    await runtime.run(project.id, "personas")
    with pytest.raises(sqlite3.DatabaseError, match="immutable"):
        with store.db.write() as conn:
            conn.execute("UPDATE artefact_versions SET generation = '{}'")


async def test_a_disabled_personal_rule_stops_flagging_but_a_secret_is_still_refused(rig, store, project):
    runtime, provider, engine = rig(guardrails_disabled_rules="email,phone")
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=personas_with(f"Contact {F.EMAIL}.")))
    assert (await runtime.run(project.id, "personas")).flags == 0
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=personas_with(F.AWS_KEY)), ok(PERSONA_SECTIONS, items=PERSONA_ITEMS_CLEAN))
    assert (await runtime.run(project.id, "personas")).attempts == 2


# ---- a person's edit -------------------------------------------------------------------------------------------------------------------

def edit_body(extra: str) -> str:
    return reply(PERSONA_SECTIONS, items=personas_with(extra)).replace("<artefact>\n", "").replace("\n</artefact>", "")


async def human_for(rig, store, project, **settings):
    runtime, provider, engine = rig(**settings)
    await chain_to_requirements(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", ok(PERSONA_SECTIONS, items=PERSONA_ITEMS_CLEAN))
    await runtime.run(project.id, "personas")
    human = HumanActions(store, engine, runtime, ReviewService(runtime.settings, store, runtime.gateway, runtime, engine, load_rubric()))
    return human, runtime, provider, engine


async def test_a_person_cannot_save_a_secret_and_the_refusal_does_not_repeat_it(rig, store, project):
    human, *_ = await human_for(rig, store, project)
    with pytest.raises(EditRefused) as caught:
        human.edit(project.id, "REQ-PER-001", edit_body(F.GITHUB_TOKEN), actor=PERSON)
    assert "(rule github_token)" in str(caught.value) and F.GITHUB_TOKEN not in str(caught.value) and F.GITHUB_TOKEN not in " ".join(caught.value.problems)
    assert store.artefacts.get(project.id, "REQ-PER-001").latest_version == 1
    assert F.GITHUB_TOKEN not in every_text_in_the_database(store)


async def test_a_person_may_save_personal_data_and_the_flag_is_kept_with_their_version(rig, store, project):
    human, *_ = await human_for(rig, store, project)
    assert human.edit(project.id, "REQ-PER-001", edit_body(f"Ask {F.EMAIL}."), actor=PERSON) == 2
    flags = store.artefacts.get_version(project.id, "REQ-PER-001").generation["guardrails"]
    assert [f["rule"] for f in flags] == ["email"] and F.EMAIL not in json.dumps(flags)


async def test_a_persons_edit_with_a_configured_credential_is_refused(rig, store, project):
    human, *_ = await human_for(rig, store, project, ibm_ica_api_key=OWN_KEY)
    with pytest.raises(EditRefused, match="configured_credential"):
        human.edit(project.id, "REQ-PER-001", edit_body(f"key {OWN_KEY}"), actor=PERSON)


# ---- the repository: the last line ---------------------------------------------------------------------------------------------------------

def bare_artefact(store, project):
    store.artefacts.create(project.id, artefact_type="personas", phase_key="requirements", title="Personas", actor="system", prefix="REQ-PER")
    return "REQ-PER-001"


def test_the_repository_refuses_a_high_confidence_secret_whoever_calls_it_and_saves_nothing(store, project):
    from app.guardrails.scan import Scanner

    store.artefacts.backstop = Scanner(secrets=[OWN_KEY])
    art = bare_artefact(store, project)
    for name, value in (("aws", F.AWS_KEY), ("github", F.GITHUB_TOKEN), ("private key", F.PRIVATE_KEY), ("jwt", F.JWT), ("url", F.URL_WITH_PASSWORD),
                        ("configured", OWN_KEY), ("slack", F.SLACK_TOKEN), ("stripe", F.STRIPE_KEY), ("google", F.GOOGLE_KEY)):
        with pytest.raises(SecretRefused, match="was not saved") as caught:
            store.artefacts.add_version(project.id, art, body=f"text {value} text", author="human:ann")
        assert value not in str(caught.value), name
    assert store.artefacts.get(project.id, art).latest_version is None
    assert store.audit.list(project.id, action="artefact.version_added") == []


def test_the_repository_backstop_also_guards_the_atomic_create_and_add(store, project):
    from app.guardrails.scan import Scanner

    store.artefacts.backstop = Scanner()
    with pytest.raises(SecretRefused):
        store.artefacts.create_and_add_version(project.id, artefact_type="personas", phase_key="requirements", title="P", prefix="REQ-PER",
                                               body=f"x {F.AWS_KEY}", author="agent:r@m")
    assert store.artefacts.list(project.id) == [] and store.links.list(project.id) == []     # no artefact was created either


def test_the_backstop_does_not_apply_the_generic_assignment_rule_or_refuse_personal_data(store, project):
    from app.guardrails.scan import Scanner

    store.artefacts.backstop = Scanner()
    art = bare_artefact(store, project)
    store.artefacts.add_version(project.id, art, body=f"{F.ASSIGNED_SECRET}\nreach {F.EMAIL} or {F.PHONE_INTL} or {F.CARD}", author="human:ann")
    assert store.artefacts.get(project.id, art).latest_version == 1


def test_without_a_backstop_a_bare_store_saves_what_it_is_given(store, project):
    assert store.artefacts.backstop is None
    art = bare_artefact(store, project)
    store.artefacts.add_version(project.id, art, body=f"x {F.AWS_KEY}", author="human:ann")           # unit tests of other layers rely on this
    assert store.artefacts.get(project.id, art).latest_version == 1


def test_the_app_arms_the_backstop_and_the_document_scanner(make_settings):
    from app.main import create_app

    app = create_app(make_settings())
    assert app.state.store.artefacts.backstop is app.state.agents.scanner and app.state.store.context.scanner is app.state.agents.scanner


# ---- a reviewer's reply ---------------------------------------------------------------------------------------------------------------------------

async def test_a_review_that_quotes_a_secret_is_sent_back_once_and_the_clean_review_is_stored(review_rig, store, project):
    service, runtime, provider, engine = review_rig()
    written = await write_personas(runtime, provider, store, project, engine)
    leaky = f"<review>\nSummary: The persona quotes a key {F.AWS_KEY} from the source.\n- [HIGH] PER-001: contains {F.AWS_KEY}. Fix: remove it.\n</review>"
    clean = "<review>\nSummary: The persona quotes a key from the source.\n- [HIGH] PER-001: contains a key. Fix: remove it.\n</review>"
    provider.queue("m-sonnet", review_reply(leaky), review_reply(clean))
    result = await service.review(project.id, written.artefact_id)
    assert result.attempts == 2
    told = provider.calls[-1].request.messages[-1].content
    assert "(rule aws_key_id)" in told and F.AWS_KEY not in told.split("Your review could not be accepted")[1].split("Write the complete")[0]
    stored = json.dumps(store.artefacts.get_version(project.id, written.artefact_id).review_findings)
    assert F.AWS_KEY not in stored and "(rule aws_key_id)" in stored                 # the reason is kept, the value is not


async def test_a_clean_review_is_unaffected(review_rig, store, project):
    service, runtime, provider, engine = review_rig()
    written = await write_personas(runtime, provider, store, project, engine)
    provider.queue("m-sonnet", review_reply(REVIEW_CLEAN))
    assert (await service.review(project.id, written.artefact_id)).attempts == 1


# ---- documents: flagged, never blocked ----------------------------------------------------------------------------------------------------------------------

def test_a_document_with_a_secret_and_an_email_is_accepted_and_returns_both_findings(make_settings, tmp_path):
    from app.main import create_app

    app = create_app(make_settings())
    store = app.state.store
    project = store.projects.create(name="P", actor="system")
    text = f"# Notes\nKey for the build: {F.AWS_KEY}\n\n## Contacts\nAsk {F.EMAIL} about it.\n"
    info = store.context.add_document(project.id, "notes.md", text.encode(), actor="human:ann")
    assert info.number == 1 and not info.already_added                       # accepted, not blocked
    # `line` counts lines of the EXTRACTED text: blank lines are dropped and each section starts with its heading. It is
    # a pointer to where to look, not the line number in the original file (which for a PDF or Word file does not exist).
    assert [(f.rule, f.line, f.heading) for f in info.findings] == [("aws_key_id", 2, "Notes"), ("email", 4, "Notes > Contacts")]
    assert F.AWS_KEY not in repr(info.findings) and F.EMAIL not in repr(info.findings)


def test_the_document_audit_row_has_counts_and_rule_names_only(make_settings):
    from app.main import create_app

    app = create_app(make_settings())
    store = app.state.store
    project = store.projects.create(name="P", actor="system")
    store.context.add_document(project.id, "n.md", f"x {F.AWS_KEY} and {F.EMAIL} and {F.EMAIL}\n".encode(), actor="human:ann")
    [event] = [e for e in store.audit.list(project.id) if e.action == "document.added"]
    assert event.detail["guardrail_flags"] == {"aws_key_id": 1, "email": 2}
    assert F.AWS_KEY not in json.dumps(event.detail) and F.EMAIL not in json.dumps(event.detail)


def test_a_clean_document_returns_no_findings_and_adds_nothing_to_its_audit_row(make_settings):
    from app.main import create_app

    app = create_app(make_settings())
    store = app.state.store
    project = store.projects.create(name="P", actor="system")
    info = store.context.add_document(project.id, "n.md", b"# Rules\n\nStaff may book a room for up to four hours.\n", actor="human:ann")
    assert info.findings == ()
    [event] = [e for e in store.audit.list(project.id) if e.action == "document.added"]
    assert "guardrail_flags" not in event.detail


def test_the_same_document_uploaded_twice_reports_the_same_findings_both_times(make_settings):
    from app.main import create_app

    app = create_app(make_settings())
    store = app.state.store
    project = store.projects.create(name="P", actor="system")
    data = f"contact {F.EMAIL}\n".encode()
    first = store.context.add_document(project.id, "n.md", data, actor="human:ann")
    again = store.context.add_document(project.id, "n.md", data, actor="human:ann")
    assert again.already_added and again.number == first.number and again.findings == first.findings and len(first.findings) == 1


def test_replacing_a_document_scans_the_new_text(make_settings):
    from app.main import create_app

    app = create_app(make_settings())
    store = app.state.store
    project = store.projects.create(name="P", actor="system")
    old = store.context.add_document(project.id, "n.md", b"nothing here\n", actor="human:ann")
    new = store.context.replace_document(project.id, old.number, "n.md", f"now {F.AWS_KEY}\n".encode(), actor="human:ann")
    assert [f.rule for f in new.findings] == ["aws_key_id"] and old.findings == ()


def test_the_secret_stays_in_the_document_but_in_no_other_table(make_settings):
    """A flagged document is the person's own material and is stored, searched and sent to models like any other. What must
    not happen is the value being COPIED into the audit log, an event, or a finding."""
    from app.main import create_app

    app = create_app(make_settings())
    store = app.state.store
    project = store.projects.create(name="P", actor="system")
    store.context.add_document(project.id, "n.md", f"key {F.AWS_KEY}\n".encode(), actor="human:ann")
    with store.db.read() as conn:
        holders = {name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
                   for row in conn.execute(f'SELECT * FROM "{name}"').fetchall() if F.AWS_KEY in " ".join(str(v) for v in tuple(row))}
    assert holders and all(h.startswith("context_") for h in holders), holders           # only the document's own chunks and their search index
    assert "context_chunks" in holders                                                  # precondition: it really is in the document


def test_a_scanner_that_is_not_installed_scans_nothing_and_does_not_fail(store, project):
    info = store.context.add_document(project.id, "n.md", f"key {F.AWS_KEY}\n".encode(), actor="human:ann")
    assert info.findings == ()


# ---- events and the approval record ------------------------------------------------------------------------------------------------------------------------

async def test_artefact_finished_carries_a_count_of_flags_and_never_a_rule_or_a_value(make_settings):
    from tests.test_run_phase import BRIEF, MODELS, POLICY, REPLIES, Scripted
    from app.main import create_app

    cfg = make_settings(**MODELS, llm_retry_backoff_seconds=0)
    provider = Scripted()
    provider.replies = dict(REPLIES)
    provider.replies["personas"] = REPLIES["personas"].replace("Office staff member, who wants a free room quickly.", f"Office staff member, reach {F.EMAIL}.")
    app = create_app(cfg, provider=provider)
    store, runner = app.state.store, app.state.runner
    project = store.projects.create(name="P", brief=BRIEF, actor="system")
    app.state.engine.open_project(project.id)
    store.context.add_document(project.id, "policy.md", POLICY, actor="human:ann")
    await runner.run_phase(project.id, "setup")
    app.state.engine.finish(project.id, "setup", actor="system")
    app.state.engine.approve(project.id, "setup", actor="human:ann")
    await runner.run_phase(project.id, "requirements", only=["personas"])
    [finished] = [e for e in store.run_events.list(project.id) if e.type == "artefact.finished" and e.data["key"] == "personas"]
    assert finished.data["flags"] == 1 and isinstance(finished.data["flags"], int)
    published = json.dumps([e.data for e in store.run_events.list(project.id)])
    assert F.EMAIL not in published and '"email"' not in published


async def test_the_approval_record_lists_which_artefacts_carry_personal_data_flags_by_rule_and_count(rig, store, project):
    human, runtime, provider, engine = await human_for(rig, store, project)
    for key, prefix, name in (("problem_statement", "REQ-PRB", "P"), ("vision_objectives", "REQ-VIS", "V"), ("functional_requirements", "REQ-F", "F"),
                              ("non_functional_requirements", "REQ-NF", "N"), ("epics_features", "REQ-EPC", "E")):
        store.artefacts.create(project.id, artefact_type=key, phase_key="requirements", title=name, actor="system", prefix=prefix)
        store.artefacts.add_version(project.id, f"{prefix}-001", body="x", author=PERSON)
    human.edit(project.id, "REQ-PER-001", edit_body(f"Ask {F.EMAIL} or {F.EMAIL} or {F.PHONE_INTL}."), actor=PERSON)
    engine.finish(project.id, "requirements", actor="system")
    human.approve(project.id, "requirements", actor=PERSON)
    detail = store.audit.list(project.id, action="phase.decided")[-1].detail
    assert detail["guardrail_flags"] == {"REQ-PER-001": {"email": 2, "phone": 1}}
    assert F.EMAIL not in json.dumps(detail) and F.PHONE_INTL not in json.dumps(detail)


async def test_an_approval_with_nothing_flagged_says_so(rig, store, project):
    human, runtime, provider, engine = await human_for(rig, store, project)
    for key, prefix, name in (("problem_statement", "REQ-PRB", "P"), ("vision_objectives", "REQ-VIS", "V"), ("functional_requirements", "REQ-F", "F"),
                              ("non_functional_requirements", "REQ-NF", "N"), ("epics_features", "REQ-EPC", "E")):
        store.artefacts.create(project.id, artefact_type=key, phase_key="requirements", title=name, actor="system", prefix=prefix)
        store.artefacts.add_version(project.id, f"{prefix}-001", body="x", author=PERSON)
    engine.finish(project.id, "requirements", actor="system")
    human.approve(project.id, "requirements", actor=PERSON)
    assert store.audit.list(project.id, action="phase.decided")[-1].detail["guardrail_flags"] == {}


# ---- status ------------------------------------------------------------------------------------------------------------------------------------------------------

def test_the_status_block_shows_the_rule_counts_and_what_is_switched_off(make_settings):
    import httpx

    from app.main import create_app
    from fastapi.testclient import TestClient

    block = TestClient(create_app(make_settings(guardrails_disabled_rules="phone"))).get("/api/status").json()["guardrails"]
    assert block == {"rules": 14, "secret_rules": 10, "personal_rules": 4, "disabled": ["phone"], "cannot_be_disabled": ["configured_credential", "private_key"]}


def test_the_whole_database_holds_no_planted_secret_after_a_full_flow(make_settings):
    """Planted in a reply, a person's edit, a review and an upload: it may exist only where the person's own document stores it."""
    from app.main import create_app

    app = create_app(make_settings())
    store = app.state.store
    project = store.projects.create(name="P", actor="system")
    store.context.add_document(project.id, "n.md", f"key {F.AWS_KEY}\n".encode(), actor="human:ann")
    text = every_text_in_the_database(store)
    inside_document_tables = sum(text.count(F.AWS_KEY) for _ in [0])
    assert inside_document_tables >= 1                                                  # precondition: the upload put it there
    for table_holds in ("audit", "traces", "memory", "run_events", "runs", "artefact_versions", "links"):
        with store.db.read() as conn:
            rows = " ".join(str(v) for row in conn.execute(f'SELECT * FROM "{table_holds}"').fetchall() for v in tuple(row))
        assert F.AWS_KEY not in rows, table_holds


async def test_the_approval_record_lists_personal_data_flags_only_even_if_a_stored_record_holds_a_secret_class_finding(rig, store, project):
    """The filter guards STORED data: a record written by an older version, or a future code path, could hold a secret-class
    finding, and the approval record must never present it as a mere flag."""
    human, runtime, provider, engine = await human_for(rig, store, project)
    for key, prefix, name in (("problem_statement", "REQ-PRB", "P"), ("vision_objectives", "REQ-VIS", "V"), ("functional_requirements", "REQ-F", "F"),
                              ("non_functional_requirements", "REQ-NF", "N"), ("epics_features", "REQ-EPC", "E")):
        store.artefacts.create(project.id, artefact_type=key, phase_key="requirements", title=name, actor="system", prefix=prefix)
        store.artefacts.add_version(project.id, f"{prefix}-001", body="x", author=PERSON)
    record = {"guardrails": [{"rule": "email", "class": "personal", "line": 1, "heading": "", "length": 10},
                             {"rule": "aws_key_id", "class": "secret", "line": 2, "heading": "", "length": 20}]}
    store.artefacts.add_version(project.id, "REQ-PER-001", body="## Personas\n- PER-001 x. Derives from: SET-CHR-001", author=PERSON, generation=record)
    engine.finish(project.id, "requirements", actor="system")
    human.approve(project.id, "requirements", actor=PERSON)
    assert store.audit.list(project.id, action="phase.decided")[-1].detail["guardrail_flags"] == {"REQ-PER-001": {"email": 1}}
