"""The context store against a real temporary database: documents, search, citations, isolation."""
from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.context.store import valid_source_id
from app.context.types import DocumentRefused, Limits
from app.models import InvalidInput, NotFoundError
from app.repos import Store

from ._files import make_docx, make_pdf

POLICY = b"""# Meeting Room Policy

Staff may book a room for up to four hours at a time during office hours.

## Cancellation

A booking can be cancelled free of charge up to 24 hours before it starts.

## Equipment

Every room has a display. The Atlas room also has a video-conference camera.
"""
PERSON = "human:ann"


@pytest.fixture
def ctx(store):
    return store.context


@pytest.fixture
def doc(store, project):
    return store.context.add_document(project.id, "policy.md", POLICY, actor=PERSON)


def ids(hits) -> list[str]:
    return [h.source_id for h in hits]


# ---- search quality ------------------------------------------------------------------------------------------

def test_the_known_relevant_chunk_is_ranked_first(ctx, project, doc):
    assert ids(ctx.search(project.id, "How late can I cancel a booking?"))[0] == "DOC-001#2"
    assert ids(ctx.search(project.id, "Which room has a camera?"))[0] == "DOC-001#3"


def test_stemming_matches_other_forms_of_the_same_word(ctx, project, doc):
    assert "DOC-001#2" in ids(ctx.search(project.id, "cancellations"))   # text says 'cancelled' and 'Cancellation'
    assert "DOC-001#1" in ids(ctx.search(project.id, "booked rooms"))    # text says 'book' and 'room'


def test_search_ignores_case_and_accents(ctx, project):
    ctx.add_document(project.id, "cafe.txt", "The café opens early.".encode(), actor=PERSON)
    assert ids(ctx.search(project.id, "CAFE")) == ["DOC-001#1"]


def test_the_heading_path_is_searchable_even_when_the_body_never_says_the_word(ctx, project):
    ctx.add_document(project.id, "d.md", b"# Cancellation\n\nTwenty-four hours notice is needed.", actor=PERSON)
    assert ids(ctx.search(project.id, "cancellation"))  # the word is only in the heading


def test_more_matching_words_rank_higher(ctx, project):
    ctx.add_document(project.id, "a.txt", b"Cancel the booking.\n", actor=PERSON)
    ctx.add_document(project.id, "b.txt", b"Cancel the booking and refund the room fee promptly.\n", actor=PERSON)
    ctx.add_document(project.id, "c.txt", b"Cats and dogs and birds.\n", actor=PERSON)
    ranked = ctx.search(project.id, "cancel booking refund room fee")
    assert ids(ranked)[0] == "DOC-002#1" and "DOC-003#1" not in ids(ranked)


def test_ties_break_the_same_way_every_time(ctx, project):
    for n in range(4):
        ctx.add_document(project.id, f"d{n}.txt", f"Identical sentence about rooms. {n}\n".encode(), actor=PERSON)
    first = ids(ctx.search(project.id, "identical sentence rooms"))
    assert all(ids(ctx.search(project.id, "identical sentence rooms")) == first for _ in range(5))
    assert first == sorted(first)


@pytest.mark.parametrize("query", ["", "   ", None, "the and of", "?!", '"', "NEAR(", "*", "-"])
def test_a_question_with_nothing_searchable_returns_nothing_not_everything(ctx, project, doc, query):
    assert ctx.search(project.id, query) == []


@pytest.mark.parametrize("query", ['"unclosed', "cancel* AND NOT booking", "a:b", "'; DROP TABLE context_chunks; --", "x" * 9000])
def test_hostile_questions_do_not_break_the_search_or_the_data(ctx, project, doc, query):
    ctx.search(project.id, query)
    assert ids(ctx.search(project.id, "cancel"))  # the table is still there and still works


# ---- the numbers on a hit ----------------------------------------------------------------------------------------

def test_scores_are_positive_and_descending_and_hits_are_complete(ctx, project, doc):
    hits = ctx.search(project.id, "cancel booking hours")
    assert hits and all(h.score > 0 for h in hits)
    assert [h.score for h in hits] == sorted((h.score for h in hits), reverse=True)
    top = hits[0]
    assert (top.kind, top.title, top.relevance) == ("document", "policy.md", 1.0)
    assert top.heading_path == "Meeting Room Policy > Cancellation" and "24 hours" in top.text
    assert top.citation == "[DOC-001#2] policy.md > Meeting Room Policy > Cancellation"
    assert 0 < top.coverage <= 1 and top.phase_key is None and top.page is None


def test_the_best_hit_is_always_relevance_one_even_when_it_is_poor_which_is_why_coverage_exists(ctx, project, doc):
    hits = ctx.search(project.id, "camera helicopter submarine volcano")  # only one of four words is in the text
    assert hits[0].relevance == 1.0
    assert hits[0].coverage == pytest.approx(0.25)


def test_coverage_is_the_share_of_the_questions_words_in_the_chunk(ctx, project, doc):
    top = ctx.search(project.id, "cancel booking hours")[0]
    assert top.coverage == pytest.approx(1.0)
    partial = ctx.search(project.id, "cancel unicorn")[0]
    assert partial.coverage == pytest.approx(0.5)


def test_min_coverage_is_a_bar_applied_before_the_limit(ctx, project, doc):
    # Six words, so coverage steps in sixths. Only the chunk that mentions several of them clears 0.5.
    question = "room cancel camera booking helicopter submarine"
    everything = ctx.search(project.id, question, limit=50)
    strong = ctx.search(project.id, question, min_coverage=0.5, limit=50)
    assert len(everything) >= 3 and min(h.coverage for h in everything) < 0.5 <= max(h.coverage for h in everything)
    assert 0 < len(strong) < len(everything) and all(h.coverage >= 0.5 for h in strong)
    assert ids(strong) == [i for i in ids(everything) if i in ids(strong)]  # same order, just fewer
    # The bar is applied BEFORE the limit: limit=1 gives the best hit that clears it, even when
    # the unfiltered top hit would not have.
    only_one = ctx.search(project.id, question, min_coverage=0.5, limit=1)
    assert len(only_one) <= 1 and (not only_one or only_one[0].coverage >= 0.5)
    assert ctx.search(project.id, "helicopter submarine", min_coverage=0.5) == []


def test_the_bar_is_applied_before_the_cut_so_a_weak_top_hit_cannot_hide_a_strong_one(ctx, project):
    # Thirty filler documents each contain two of the three question words, so BM25 ranks one of them
    # FIRST. The only document containing all three words has long padding, so BM25 ranks it LAST.
    # A bar applied after the cut (limit=1) would look at the filler alone and find nothing.
    for n in range(30):
        ctx.add_document(project.id, f"f{n}.txt", b"giraffe okapi and other common animals appear here\n", actor=PERSON)
    ctx.add_document(project.id, "A-rare-repeat.txt", b"zebra zebra zebra zebra\n", actor=PERSON)
    ctx.add_document(project.id, "B-all-three.txt", ("zebra giraffe okapi " + "padding words about nothing " * 12 + "\n").encode(), actor=PERSON)
    question = "zebra giraffe okapi"

    unfiltered = ctx.search(project.id, question, limit=50)
    # The precondition, asserted so this test can never silently become vacuous if ranking changes:
    assert unfiltered[0].coverage < 0.9 and max(h.coverage for h in unfiltered) == pytest.approx(1.0)
    assert unfiltered[-1].title == "B-all-three.txt"

    covered = ctx.search(project.id, question, min_coverage=0.9, limit=1)
    assert [h.title for h in covered] == ["B-all-three.txt"] and covered[0].coverage == pytest.approx(1.0)


def test_ties_break_by_source_id_not_by_the_order_things_were_inserted(store, project, ctx):
    """Chunks with exactly equal scores, inserted in an order that DISAGREES with their source IDs.

    Without an explicit tie-break SQLite returns tied rows in insertion order (checked in the query plan),
    so this is the only kind of test that can tell a deterministic ordering from an accidental one. An
    earlier version of this test used a memory note and a document, whose scores differed slightly (the
    note's kind is indexed as its heading), so there was no tie and it proved nothing."""
    with store.db.write() as conn:
        for source in ("DOC-009#1", "DOC-002#1", "DOC-005#1"):  # inserted in this order
            conn.execute(
                "INSERT INTO context_chunks (project_id, source_id, kind, owner, ordinal, text, title)"
                " VALUES (?, ?, 'document', ?, 1, 'Identical sentence about rooms', 'x')",
                (project.id, source, source.split("#")[0]),
            )
    # The preconditions, asserted so this test can never quietly stop testing anything:
    with store.db.read() as conn:
        rows = conn.execute(
            "SELECT c.id, c.source_id, bm25(context_fts) AS rank FROM context_fts"
            " JOIN context_chunks c ON c.id = context_fts.rowid WHERE context_fts MATCH '\"identical\"'"
        ).fetchall()
    assert len({round(r["rank"], 15) for r in rows}) == 1, "the scores must be exactly tied"
    assert [r["source_id"] for r in sorted(rows, key=lambda r: r["id"])] == ["DOC-009#1", "DOC-002#1", "DOC-005#1"]

    expected = ["DOC-002#1", "DOC-005#1", "DOC-009#1"]  # by source ID, not by insertion order
    assert all(ids(ctx.search(project.id, "identical sentence rooms")) == expected for _ in range(3))


def test_stacked_diacritics_fold_too_which_the_default_tokenizer_would_not(ctx, project):
    """'remove_diacritics 2' is deliberate: plain 'unicode61' folds café but NOT letters with two marks
    such as the Pinyin 'ǖ' or the Vietnamese 'ế'. An ordinary accent test cannot tell the two apart."""
    ctx.add_document(project.id, "pinyin.txt", "The word is lǖ and the city is Huế.\n".encode(), actor=PERSON)
    assert ids(ctx.search(project.id, "lu")) == ["DOC-001#1"]
    assert ids(ctx.search(project.id, "hue")) == ["DOC-001#1"]


def test_min_relevance_filters_the_weak_tail(ctx, project, doc):
    allhits = ctx.search(project.id, "room")
    kept = ctx.search(project.id, "room", min_relevance=0.99)
    assert kept and len(kept) <= len(allhits) and all(h.relevance >= 0.99 for h in kept)


@pytest.mark.parametrize("name", ["min_relevance", "min_coverage"])
@pytest.mark.parametrize("bad", [-0.1, 1.5, "high", True])
def test_bad_quality_bars_are_rejected(ctx, project, name, bad):
    with pytest.raises(InvalidInput, match=name):
        ctx.search(project.id, "room", **{name: bad})


def test_limit_is_clamped(ctx, project):
    for n in range(60):
        ctx.add_document(project.id, f"d{n}.txt", f"Shared keyword number {n}.\n".encode(), actor=PERSON)
    assert len(ctx.search(project.id, "shared keyword", limit=1000)) == 50
    assert len(ctx.search(project.id, "shared keyword", limit=0)) == 1
    assert len(ctx.search(project.id, "shared keyword", limit=-5)) == 1
    assert len(ctx.search(project.id, "shared keyword", limit=3)) == 3


def test_kinds_filter_and_unknown_kinds(ctx, project, doc, store):
    store.memory.add(project.id, "note", "Cancel notes belong with the policy.", actor=PERSON)
    assert {h.kind for h in ctx.search(project.id, "cancel")} == {"document", "memory"}
    assert {h.kind for h in ctx.search(project.id, "cancel", kinds=["memory"])} == {"memory"}
    assert ctx.search(project.id, "cancel", kinds=[]) == []
    with pytest.raises(InvalidInput, match="unknown kind"):
        ctx.search(project.id, "cancel", kinds=["email"])


def test_search_in_an_unknown_project_is_not_found(ctx):
    with pytest.raises(NotFoundError):
        ctx.search("nope", "anything")


# ---- documents: adding ------------------------------------------------------------------------------------------

def test_adding_a_document_records_its_details_and_audits_without_content(store, project, doc):
    assert (doc.number, doc.filename, doc.kind, doc.chunk_count, doc.added_by) == (1, "policy.md", "md", 3, PERSON)
    assert doc.size_bytes == len(POLICY) and doc.already_added is False and doc.source_prefix == "DOC-001"
    event = [e for e in store.audit.list(project.id) if e.action == "document.added"][0]
    assert event.actor == PERSON and event.target_id == "DOC-001"
    assert event.detail == {"filename": "policy.md", "kind": "md", "size_bytes": len(POLICY), "chunks": 3}
    assert "Atlas" not in str(event.detail)


def test_the_same_bytes_twice_return_the_existing_document(ctx, project, doc):
    again = ctx.add_document(project.id, "renamed-copy.md", POLICY, actor="human:bob")
    assert again.number == 1 and again.already_added is True
    assert len(ctx.list_documents(project.id)) == 1 and ctx.stats(project.id)["chunks"] == 3


def test_numbers_are_per_project_and_sequential(ctx, store, project):
    other = store.projects.create(name="Other", actor="system")
    assert [ctx.add_document(project.id, f"{n}.txt", f"text {n}\n".encode(), actor=PERSON).number for n in range(3)] == [1, 2, 3]
    assert ctx.add_document(other.id, "x.txt", b"text 0\n", actor=PERSON).number == 1  # same bytes, other project


def test_word_and_pdf_documents_are_searchable_and_pdf_chunks_carry_page_numbers(ctx, project):
    ctx.add_document(project.id, "p.docx", make_docx([("h1", "Hours"), ("p", "Offices open at eight sharp.")]), actor=PERSON)
    ctx.add_document(project.id, "q.pdf", make_pdf(["First page text.", "Second page mentions refunds."]), actor=PERSON)
    assert ids(ctx.search(project.id, "offices open"))[0] == "DOC-001#1"
    hit = ctx.search(project.id, "refunds")[0]
    assert hit.source_id == "DOC-002#2" and hit.page == 2 and hit.citation.endswith(", page 2")


def test_refused_documents_leave_nothing_behind(ctx, store, project):
    for name, data in [("a.exe", b"x"), ("b.txt", b""), ("c.pdf", b"not a pdf")]:
        with pytest.raises(DocumentRefused):
            ctx.add_document(project.id, name, data, actor=PERSON)
    assert ctx.list_documents(project.id, include_removed=True) == [] and ctx.stats(project.id)["chunks"] == 0
    assert not [e for e in store.audit.list(project.id) if e.action == "document.added"]


def test_a_non_bytes_document_is_rejected(ctx, project):
    with pytest.raises(InvalidInput, match="bytes"):
        ctx.add_document(project.id, "a.txt", "a string", actor=PERSON)


def test_only_the_extracted_text_is_stored_not_the_file(store, project, ctx):
    ctx.add_document(project.id, "a.txt", b"Plain text only.\n", actor=PERSON)
    with store.db.read() as conn:
        columns = {c["name"] for c in conn.execute("PRAGMA table_info(context_documents)")}
    assert not columns & {"data", "content", "body", "blob", "bytes"}


def test_unknown_project_is_not_found_on_every_write(ctx):
    with pytest.raises(NotFoundError):
        ctx.add_document("nope", "a.txt", b"x\n", actor=PERSON)
    with pytest.raises(NotFoundError):
        ctx.list_documents("nope")


def test_limits_per_project_and_per_document(store, project):
    tight = Store.open(store.db.path, limits=Limits(max_docs_per_project=2, max_chunks_per_document=3,
                                                    chunk_target_chars=200, chunk_cap_chars=300, min_tail_chars=10))
    c = tight.context
    c.add_document(project.id, "1.txt", b"one\n", actor=PERSON)
    c.add_document(project.id, "2.txt", b"two\n", actor=PERSON)
    with pytest.raises(DocumentRefused, match="already has 2 documents; the limit is 2"):
        c.add_document(project.id, "3.txt", b"three\n", actor=PERSON)
    c.remove_document(project.id, 1, actor=PERSON)  # removing one makes room
    big = b"\n\n".join(("sentence number %d is here. " % n * 12).encode() for n in range(10))
    with pytest.raises(DocumentRefused, match=r"limit is 3"):
        c.add_document(project.id, "big.txt", big, actor=PERSON)


# ---- documents: removing and replacing -------------------------------------------------------------------------------

def test_removing_a_document_takes_its_chunks_out_of_the_index(ctx, store, project, doc):
    assert ids(ctx.search(project.id, "camera"))
    ctx.remove_document(project.id, 1, actor=PERSON)
    assert ctx.search(project.id, "camera") == [] and ctx.resolve(project.id, "DOC-001#3") is None
    assert ctx.list_documents(project.id) == [] and len(ctx.list_documents(project.id, include_removed=True)) == 1
    event = [e for e in store.audit.list(project.id) if e.action == "document.removed"][0]
    assert event.detail == {"filename": "policy.md"}


def test_removing_twice_or_a_missing_document_is_not_found(ctx, project, doc):
    ctx.remove_document(project.id, 1, actor=PERSON)
    with pytest.raises(NotFoundError):
        ctx.remove_document(project.id, 1, actor=PERSON)
    with pytest.raises(NotFoundError):
        ctx.remove_document(project.id, 99, actor=PERSON)


def test_a_removed_document_can_be_added_again_and_gets_a_new_number(ctx, project, doc):
    ctx.remove_document(project.id, 1, actor=PERSON)
    again = ctx.add_document(project.id, "policy.md", POLICY, actor=PERSON)
    assert again.number == 2 and again.already_added is False


def test_replacing_gives_a_new_number_so_the_old_citation_resolves_to_nothing(ctx, store, project, doc):
    old_citation = ctx.search(project.id, "camera")[0].source_id
    new = ctx.replace_document(project.id, 1, "policy-v2.md", POLICY + b"\nExtra rule: no food.\n", actor=PERSON)
    assert new.number == 2 and new.already_added is False
    assert ctx.resolve(project.id, old_citation) is None  # honest: it does not silently point at new text
    assert ids(ctx.search(project.id, "camera"))[0].startswith("DOC-002#")
    assert [d.number for d in ctx.list_documents(project.id)] == [2]
    assert "document.replaced" in [e.action for e in store.audit.list(project.id)]


def test_replacing_with_identical_bytes_changes_nothing(ctx, project, doc):
    same = ctx.replace_document(project.id, 1, "copy.md", POLICY, actor=PERSON)
    assert same.number == 1 and same.already_added is True and len(ctx.list_documents(project.id)) == 1


def test_a_refused_replacement_keeps_the_original(ctx, project, doc):
    with pytest.raises(DocumentRefused):
        ctx.replace_document(project.id, 1, "bad.exe", b"x", actor=PERSON)
    assert [d.number for d in ctx.list_documents(project.id)] == [1] and ids(ctx.search(project.id, "camera"))


def test_replacing_a_missing_document_is_not_found(ctx, project):
    with pytest.raises(NotFoundError):
        ctx.replace_document(project.id, 1, "a.txt", b"x\n", actor=PERSON)


# ---- memory --------------------------------------------------------------------------------------------------------------------

def test_memory_is_searchable_the_moment_it_is_recorded(ctx, store, project):
    assert ctx.search(project.id, "peak load") == []
    entry = store.memory.add(project.id, "human_feedback", "Add a peak-load requirement.", actor=PERSON, phase_key="requirements")
    hit = ctx.search(project.id, "peak load")[0]
    assert hit.source_id == f"MEM-{entry.id:03d}" and hit.kind == "memory" and hit.phase_key == "requirements"
    assert "peak-load" in hit.text and hit.title == "human_feedback"


def test_memory_filters_by_phase(ctx, store, project):
    store.memory.add(project.id, "note", "Alpha note for design.", actor=PERSON, phase_key="design")
    store.memory.add(project.id, "note", "Alpha note for requirements.", actor=PERSON, phase_key="requirements")
    assert [h.phase_key for h in ctx.search(project.id, "alpha", phase_key="design")] == ["design"]
    assert len(ctx.search(project.id, "alpha")) == 2


def test_memory_that_already_existed_before_the_context_store_is_indexed_by_the_migration(tmp_path):
    import sqlite3
    from app.db import MIGRATIONS, SCHEMA_V1, SCHEMA_V2, Database, split_statements

    path = tmp_path / "old.db"
    raw = sqlite3.connect(path)
    for script in (SCHEMA_V1, SCHEMA_V2):
        for statement in split_statements(script):
            raw.execute(statement)
    raw.execute("PRAGMA user_version = 2")
    raw.execute("INSERT INTO projects (id, name, mode, created_at, updated_at) VALUES ('p', 'Old', 'replay', 't', 't')")
    raw.execute("INSERT INTO memory (project_id, kind, text, created_at) VALUES ('p', 'note', 'Old feedback about refunds.', 't')")
    raw.commit()
    raw.close()
    assert Database(path).migrate() == len(MIGRATIONS)
    assert ids(Store.open(path).context.search("p", "refunds")) == ["MEM-001"]


# ---- citations: resolve ----------------------------------------------------------------------------------------------------

def test_every_hit_resolves_to_the_same_text(ctx, store, project, doc):
    store.memory.add(project.id, "note", "Camera feedback.", actor=PERSON)
    for hit in ctx.search(project.id, "camera cancel booking"):
        again = ctx.resolve(project.id, hit.source_id)
        assert again is not None and again.text == hit.text and again.citation == hit.citation
        assert again.score is None and again.relevance is None and again.coverage is None  # looked up, not searched


@pytest.mark.parametrize("bad", ["", "nonsense", "DOC-1#1", "DOC-001", "DOC-001#0", "DOC-001#x", "mem-001", None, 42, "DOC-001#1; DROP", "../x"])
def test_malformed_ids_resolve_to_nothing(ctx, project, doc, bad):
    assert ctx.resolve(project.id, bad) is None


def test_an_unknown_id_resolves_to_nothing(ctx, project, doc):
    assert ctx.resolve(project.id, "DOC-009#1") is None and ctx.resolve(project.id, "DOC-001#99") is None


def test_valid_source_id_recognises_the_three_shapes():
    for good in ("DOC-001#1", "DOC-1234#12", "REQ-F-012@v2#3", "SET-CHR-001@v1#1", "MEM-017"):
        assert valid_source_id(good), good
    for bad in ("DOC-001", "REQ-F-012#3", "MEM-17", "doc-001#1", "REQ-F-012@v0#1", "REQ-F-012@v1#0"):
        assert not valid_source_id(bad), bad


# ---- stats -----------------------------------------------------------------------------------------------------------------------

def test_stats_count_each_kind(ctx, store, project, doc):
    store.memory.add(project.id, "note", "A note.", actor=PERSON)
    assert ctx.stats(project.id) == {"documents": 1, "artefact_sources": 0, "memory": 1, "chunks": 4}
    with pytest.raises(NotFoundError):
        ctx.stats("nope")


# ---- isolation -------------------------------------------------------------------------------------------------------------------

def test_one_projects_text_is_invisible_to_another_through_every_entry_point(ctx, store, project):
    other = store.projects.create(name="Other", actor="system")
    ctx.add_document(project.id, "secret.md", b"# Plan\n\nThe zeppelin launch is codenamed Bluebird.\n", actor=PERSON)
    store.memory.add(project.id, "note", "Bluebird feedback only for the first project.", actor=PERSON)
    assert len(ctx.search(project.id, "bluebird")) == 2

    assert ctx.search(other.id, "bluebird") == [] and ctx.search(other.id, "zeppelin launch codenamed") == []
    assert ctx.search(other.id, "bluebird", kinds=["document", "memory", "artefact"]) == []
    assert ctx.resolve(other.id, "DOC-001#1") is None
    assert ctx.resolve(other.id, [h.source_id for h in ctx.search(project.id, "bluebird") if h.kind == "memory"][0]) is None
    assert ctx.stats(other.id) == {"documents": 0, "artefact_sources": 0, "memory": 0, "chunks": 0}
    assert ctx.list_documents(other.id) == []
    with pytest.raises(NotFoundError):
        ctx.remove_document(other.id, 1, actor=PERSON)  # the other project cannot delete it...
    with pytest.raises(NotFoundError):
        ctx.replace_document(other.id, 1, "x.txt", b"x\n", actor=PERSON)  # ...or replace it
    assert ids(ctx.search(project.id, "bluebird"))  # ...and it is untouched


def test_the_project_filter_is_in_the_sql_itself_not_applied_afterwards(store, project, ctx):
    """Even when other projects hold thousands of better matches, they must not push this project's hit
    out of a LIMITed result, which a filter applied after the query would allow."""
    other = store.projects.create(name="Noisy", actor="system")
    for n in range(60):
        ctx.add_document(other.id, f"n{n}.txt", f"zebra zebra zebra zebra number {n}\n".encode(), actor=PERSON)
    ctx.add_document(project.id, "mine.txt", b"One zebra only.\n", actor=PERSON)
    assert ids(ctx.search(project.id, "zebra", limit=1)) == ["DOC-001#1"]


# ---- concurrency ----------------------------------------------------------------------------------------------------------------

def test_ten_threads_adding_different_documents_all_land_with_unique_numbers(ctx, project):
    def add(n):
        return ctx.add_document(project.id, f"d{n}.txt", f"unique content number {n}\n".encode(), actor=PERSON).number

    with ThreadPoolExecutor(max_workers=10) as pool:
        numbers = list(pool.map(add, range(10)))
    assert sorted(numbers) == list(range(1, 11)) and ctx.stats(project.id)["documents"] == 10


def test_ten_threads_adding_the_same_bytes_make_exactly_one_document(ctx, project):
    def add(_):
        return ctx.add_document(project.id, "same.txt", b"identical bytes everywhere\n", actor=PERSON)

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(add, range(10)))
    assert {r.number for r in results} == {1} and sum(not r.already_added for r in results) == 1
    assert ctx.stats(project.id)["chunks"] == 1


def test_searching_while_documents_are_being_added_never_errors(ctx, project):
    errors: list[BaseException] = []

    def reader():
        try:
            for _ in range(60):
                ctx.search(project.id, "keyword")
        except BaseException as exc:  # noqa: BLE001 - the point is to catch anything
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(reader) for _ in range(3)]
        for n in range(15):
            ctx.add_document(project.id, f"d{n}.txt", f"keyword text {n}\n".encode(), actor=PERSON)
        for f in futures:
            f.result()
    assert errors == []


# ---- the index and the table cannot disagree ---------------------------------------------------------------------------------------

def test_the_full_text_index_follows_inserts_updates_and_deletes_of_chunks(store, project):
    with store.db.write() as conn:
        conn.execute("INSERT INTO context_chunks (project_id, source_id, kind, owner, ordinal, text) "
                     "VALUES (?, 'DOC-001#1', 'document', 'DOC-001', 1, 'original zebra text')", (project.id,))
    assert ids(store.context.search(project.id, "zebra")) == ["DOC-001#1"]
    with store.db.write() as conn:
        conn.execute("UPDATE context_chunks SET text = 'edited giraffe text' WHERE source_id = 'DOC-001#1'")
    assert store.context.search(project.id, "zebra") == [] and ids(store.context.search(project.id, "giraffe")) == ["DOC-001#1"]
    with store.db.write() as conn:
        conn.execute("DELETE FROM context_chunks WHERE source_id = 'DOC-001#1'")
    assert store.context.search(project.id, "giraffe") == []
    with store.db.read() as conn:
        assert conn.execute("INSERT INTO context_fts(context_fts, rank) VALUES('integrity-check', 1)") is not None


def test_a_source_id_can_only_exist_once_per_project(store, project):
    with store.db.write() as conn:
        conn.execute("INSERT INTO context_chunks (project_id, source_id, kind, owner, ordinal, text) "
                     "VALUES (?, 'DOC-001#1', 'document', 'DOC-001', 1, 'a')", (project.id,))
    with pytest.raises(sqlite3.IntegrityError):
        with store.db.write() as conn:
            conn.execute("INSERT INTO context_chunks (project_id, source_id, kind, owner, ordinal, text) "
                         "VALUES (?, 'DOC-001#1', 'document', 'DOC-001', 1, 'b')", (project.id,))
