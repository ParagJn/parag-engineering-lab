# S06 · Context store

**Milestone:** M2  **Size:** M  **Objectives:** O4, O5 (memory half), O13  **Depends on:** S01, S05
No model calls in this step: search is keyword ranking, so every result is deterministic and testable offline.

## Goal
Give agents something to be grounded in. A project can hold **documents** (a policy note, a brief, an old requirements file) and, as phases are approved, **its own approved artefacts**. Agents will ask the store a question in plain words and get back the most relevant **chunks**, each with a stable source ID they can cite. Everything is per project, and nothing leaks between projects.

Three kinds of thing go in, one search comes out:

| Source | Where it comes from | Searchable when |
|---|---|---|
| **Uploaded document** | txt, md, docx, pdf added to a project | as soon as it is ingested |
| **Approved artefact** | a phase gets approved (re-ingest loop, O4) | after approval; only the **current** version is searchable |
| **Project memory** | reviewer and human feedback already stored by S01 | as soon as it is recorded |

## In scope
- Text extraction for txt, md, docx, pdf (the readers already in your venv: `pypdf`, `python-docx`).
- Chunking, search (SQLite FTS5, BM25 ranking), source IDs, and citation text.
- Ingest, re-ingest, replace and remove for documents; re-ingest of an approved phase's artefacts.
- Memory search across the S01 `memory` table, merged into the same results.
- `ContextStore.search(project, query, ...)` returning ranked chunks with scores and citations.
- Schema v3 migration (two tables + the FTS index).
- A `context` block in `/api/status`; an offline demo script.

## Out of scope (later steps)
- Calling a model, embeddings, "semantic" search (see decision 1).
- Prompt assembly and putting citations into a prompt (S07). Choosing *which* queries an agent runs (S07).
- Upload endpoints and UI (S12). The store is a library in this step, like the gateway was in S02.
- OCR for scanned PDFs, images, spreadsheets, slide decks, HTML, and other formats (see "limits").
- Automatic re-ingest wiring from the approve button: this step provides `reingest_phase()` and the engine calls it, but there are no agents yet to produce real artefacts.

## Design

### Search: SQLite FTS5 with BM25
SQLite is already the database, FTS5 is compiled into your Python's SQLite (3.45.3, checked), and its `bm25()` is a standard relevance ranking. That gives ranked, deterministic, dependency-free search with the index kept in the same file and the same transaction as the data. (A hand-written BM25 in Python would be more code, slower, and have no advantage here.)

- Tokenizer: `porter unicode61 remove_diacritics 2`: case-insensitive, accent-insensitive, and **stemming** ("booking", "booked", "books" all match "book"). This matters more than it sounds: requirements text and a user's question rarely use the same word forms.
- A user's question is turned into a safe FTS query by **extracting words and joining them with OR** (more matching words rank higher under BM25). The raw text is never passed to FTS, because FTS has its own query language (`NEAR`, `"`, `*`, `-`), and an unescaped `"` or `AND` in a question would crash the search or change its meaning. Stop-words are dropped from the query only (never from the index) so "what is the booking limit" searches `booking limit`.
- Ties in score break by source, then position, so the same query always returns the same order.

### Chunking
Chunks are what get retrieved, so their size is a quality decision:
- Split on **headings and blank lines first** (a chunk should be one idea), then pack paragraphs together up to a target of **~900 characters**, never more than **1,500**; a single over-long paragraph is split at sentence boundaries, then at a hard character limit as the last resort.
- **Overlap:** none by default (decision 3). Each chunk instead carries its **heading path** ("Booking rules > Cancellation") in a separate column that is indexed too, so a chunk about "24 hours" still matches a search for "cancellation".
- Tiny trailing fragments (< 120 chars) are merged into the previous chunk.
- Each chunk records `ordinal`, `heading_path`, `text`, and where it came from (page number for PDFs, section for Word/Markdown).
- Text is normalised (line endings, runs of blank lines, zero-width and control characters, non-breaking spaces) before chunking, never changed in meaning.

### Source IDs (the citations)
Every chunk gets a stable ID agents can quote and a reviewer can check:
- Documents: `DOC-003#4` = document 3, chunk 4 (1-based).
- Approved artefacts: `REQ-F-012@v2#3` = that artefact, version 2, chunk 3. The version is in the ID so a citation stays true even after the artefact is revised.
- Memory: `MEM-017`.
`ContextStore.resolve(project, source_id)` returns the chunk text and where it came from, so S07/S08 can verify that a cited ID exists and show the passage. An ID that isn't in the project resolves to nothing, never to another project's text.

### Documents
`add_document(project, filename, data: bytes, *, actor)`:
- Detects the type from the **extension and the content** (a `.pdf` that isn't a PDF is refused, not guessed at).
- Limits (settings, with defaults): **10 MB** per file, **200 pages** per PDF, **500 documents** per project, **2,000 chunks** per document. Over a limit is a clear error naming it. A zip-bomb-style `.docx` is bounded by the same size checks after decompression.
- **Content hash:** adding the same bytes twice to a project returns the existing document ("already added") instead of a duplicate.
- Stores the **extracted text**, not the original file, so the store never holds executable or macro content, and reading never re-parses an untrusted file.
- Extraction failures (encrypted PDF, corrupt docx, a PDF with no extractable text) are **refused with a plain reason**, not stored empty: an empty document that silently matches nothing is worse than an error. A scanned PDF is the classic case, and the message says "no extractable text; scanned documents need OCR, which this prototype does not do".
- Everything is audited (`document.added`, `document.removed`), with the filename, size, and chunk count, never the content.
- `remove_document` deletes its chunks and index entries in one transaction. `replace_document` is remove + add; whether the replacement keeps the old number is decision 4.

### Approved artefacts (the re-ingest loop)
`reingest_phase(project, phase_key)` is called when a phase is approved. For each artefact of that phase with content, it indexes the **latest version** as a source `REQ-F-012@v2`. Rules:
- **Only the current version is searchable.** When an artefact gets a new version and is re-ingested, the previous version's chunks are removed from the index (they stay in the artefact history in the database). Otherwise a search would return the old text alongside the new, and an agent could cite a requirement that has since been changed.
- Idempotent: re-ingesting the same version changes nothing.
- Reopening a phase removes that phase's artefacts from the index until it is approved again, because content under review is not yet "validated, approved context" (the whole point of O4).
- The engine's `approve()` and `reopen()` call these in the same step; a failure to index is logged and recorded in the audit log, and **does not undo the approval** (decision 5).

### Memory
S01 already stores reviewer and human feedback in `memory`. `search()` includes it as source `MEM-nnn` so a rejection note ("add a peak-load NFR") shows up when an agent re-runs that artefact. Memory is scoped to the project and can be filtered by phase or artefact.

### Search API
```python
store.context.search(project_id, query, *, limit=8, kinds=None, phase_key=None, min_score=None)
  -> list[Hit(source_id, kind, title, heading_path, text, score, phase_key, citation)]
store.context.resolve(project_id, source_id) -> Hit | None
store.context.stats(project_id) -> {documents, artefact_sources, memory, chunks}
```
- `kinds` filters to any of `document`, `artefact`, `memory`. `phase_key` limits to one phase's artefacts and memory.
- Scores are shown as a positive number, higher is better (BM25 reports lower-is-better, so the sign is flipped once, in one place).
- An empty or all-stop-word query returns an empty list, not an error and not everything.
- `limit` is clamped to 1–50.

### Isolation
Every table is keyed by `project_id` and every query filters on it **inside the SQL**, including the FTS match. A test plants a distinctive word in project A and searches for it from B, through every entry point (search, resolve, stats, remove, replace).

### Schema v3
```
context_documents(id, project_id, number, filename, kind, sha256, size_bytes, chars, chunk_count, added_by, created_at)
context_chunks(rowid, project_id, source_id, kind, owner, ordinal, heading_path, text, page)   -- plus an FTS5 index over text + heading_path
```
Triggers keep the FTS index in step with the chunk table, so there is no way to change one without the other. A migration test upgrades a v2 database with data and checks nothing is lost.

### Settings (defaults need no `.env` edit)
`CONTEXT_MAX_FILE_MB` (10), `CONTEXT_MAX_PDF_PAGES` (200), `CONTEXT_MAX_DOCS_PER_PROJECT` (500), `CONTEXT_CHUNK_TARGET_CHARS` (900). The hard caps (1,500 chars per chunk, 2,000 chunks per document) are constants.

### `/api/status`, the page, and the demo script
- `context` block: supported types, limits, and nothing else. No project data (there is no project selection on the page yet).
- `scripts/context_demo.py` (offline, free, you run it): builds a throwaway project, ingests a **sample policy note** it writes itself (an invented Meeting Room Booking office policy, no real company names), approves a mini-phase so an artefact is re-ingested, adds a memory note, then runs five questions and prints the ranked hits with citations. It then shows the two behaviours that matter: a revised artefact **replaces** its old version in the results, and a second project searching the same words finds **nothing**. Ends with `5/5 questions answered from the right source, isolation OK`.

## Limits stated up front
- **Keyword search, not meaning search.** BM25 with stemming finds "cancel" for "cancellation" but not "withdraw your reservation" for "cancel". Embeddings would fix that but need a model call per chunk and a vector store, which would make this step non-deterministic and add cost. Decision 1.
- **Tables are flattened.** Word tables are read cell by cell, row by row, as lines of `a | b | c`; PDFs lose layout. Fine for policy prose, poor for spreadsheets-in-a-document.
- **No OCR, no images, no scanned PDFs.** Refused with a message, not silently empty.
- **Prompt-injection note.** Retrieved text will go into prompts in S07. A document that says "ignore your instructions" is data, not instructions; S07 must wrap retrieved chunks in a clearly-labelled block and say so. This step only stores the text and flags nothing.
- **Personal data and secrets.** Documents are stored as text in the database. The secret and personal-data scanner is S10. Until then, don't upload real client documents; the docs and the demo use invented ones.

## Tests (must pass before the step is done)

| Area | Proves |
|---|---|
| FTS | the compiled SQLite has FTS5 (the suite fails clearly on a Python without it); ranking puts the known-relevant chunk first on a fixture corpus; stemming ("booking" finds "booked"); accent and case insensitivity; heading-path text is searchable; deterministic order on ties |
| query building | FTS operators and punctuation in a question (`"`, `*`, `-`, `NEAR`, `AND`, `OR`, parentheses, `:`, `'`, very long text, only symbols, only stop-words, unicode, SQL-looking text) never raise and never change meaning; empty query → empty result; OR semantics: more matching words rank higher |
| chunking | splits on headings and blank lines; packs to the target and never exceeds the cap; an over-long paragraph splits at sentences then hard; tiny tail merged; no text lost or duplicated (joining chunks reproduces the normalised text); heading path correct for nested headings; ordinals 1..n; empty and whitespace-only input → no chunks; one giant line; Windows and old-Mac line endings; zero-width and control characters stripped; deterministic |
| extraction | txt (UTF-8, UTF-8 with BOM, Latin-1 fallback); md; docx (paragraphs, headings, tables flattened, headers/footers ignored); pdf (text per page with page numbers); wrong extension vs content refused; empty file refused; encrypted PDF refused; corrupt docx refused; scanned/no-text PDF refused with the OCR message; oversize refused; too many pages refused; a decompression bomb refused |
| documents | add → chunks + audit; same bytes twice → same document; numbering per project; remove deletes chunks and index entries in one transaction; replace keeps the number; per-project and per-document limits enforced; the stored text, not the file; audit rows never contain content |
| artefact re-ingest | approved phase's latest versions become searchable as `ID@vN`; a new version **replaces** the old (old text no longer found); re-ingest is idempotent; artefacts without content skipped; reopening removes the phase's sources; re-approval restores them; the engine's approve and reopen trigger it; **an indexing failure does not undo an approval** and is audited |
| memory | S01 memory entries searchable as `MEM-nnn`; filter by phase and artefact; new memory searchable immediately |
| source IDs / resolve | every hit's ID resolves to the same text; an ID from another project, an unknown ID and a malformed ID all resolve to nothing; citations stay valid for superseded versions' IDs (they resolve to nothing, *not* to the new text) |
| search API | `kinds` and `phase_key` filters; `limit` clamping; scores positive and descending; `min_score`; hit fields complete |
| isolation | a distinctive word in project A is invisible to B through search, resolve, stats, remove, replace, and the FTS match itself; deleting nothing in B when removing in A |
| migration | fresh database is v3; a v2 database with projects, artefacts and traces migrates to v3 with all rows intact; concurrent migrate calls still succeed; triggers keep FTS and chunk table in step on insert, update and delete |
| concurrency | 10 threads adding different documents → all land, unique numbers; 10 threads adding the same bytes → exactly one document; searches during ingestion never error |
| status | `context` block shape; no project data or paths |
| demo script | runs offline; prints 5/5 and isolation OK; temp database removed; never reads `.env`; exits 1 if a question's top hit is from the wrong source |

After the suite is green I'll run the mutation check **with the baseline guard from now on** (it aborts unless the unbroken copy passes, and I'll also print the spread of "N passed" counts so a repeated number can't hide a broken harness). Mutants: stemming off, project filter dropped from the FTS query, FTS operators passed through, old version left in the index, approval undone by an index error, missing/empty extraction accepted, duplicate document stored, chunk cap ignored, text lost during chunking, the OR query turned into AND, and so on.

## Dependencies / installs
None. `pypdf` 5.1.0, `python-docx` 1.2.0 and SQLite FTS5 are already present; I'll add `pypdf` and `python-docx` to `requirements.txt` for a fresh machine.

## Decisions for you (defaults chosen; say if you want any changed)
1. **Keyword (BM25) search now, embeddings later or never.** Deterministic, free, offline, and good enough for requirements-style text with stemming. The cost is that paraphrases won't match. If retrieval quality disappoints once real agents use it (S07 onward), adding embeddings is a contained change behind `search()`.
2. **Only the current version of an artefact is searchable.** The alternative (index every version) makes search return text that has since been changed.
3. **No chunk overlap; the heading path is indexed instead.** Overlap makes the same sentence appear in two hits and wastes the prompt budget.
4. **Replacing a document keeps its number,** so a citation `DOC-003#4` still points at "the policy document" after an update. The catch: it may now point at *different text*. Alternative: a replacement gets a new number and old citations resolve to nothing. I prefer the latter for honesty, but it means a regenerated artefact that cited the old one has a dangling citation. Your call; default below.
5. **An indexing failure after an approval is logged and audited, not rolled back.** The approval is a human decision and should not silently fail because a search index hiccuped. The cost is that the phase can be approved with a gap in the index; the page and `stats` will show it.

**Defaults I'll use if you just say go:** 1 keyword, 2 current-only, 3 no overlap, **4 new number on replace** (honest citations), 5 approval stands.

## Manual check for the user (we do not run the app)
1. Offline and free: `! cd /Users/paragjain/dev-works/parag-engineering-lab/SDLC-Workbench/backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.context_demo`. Expect five questions, each with the right source on top, then `5/5 questions answered from the right source, isolation OK`.
2. Read the five questions and top hits. **This is the check that matters:** does the ranking look sensible to a human? Ranking quality is a judgement, and the tests can only prove it on the fixture corpus.
3. `./start.sh`, open `http://localhost:5270`; nothing visible changes except the schema pill reading **v3**.

## Decisions taken (user, 2026-10-27)
All five accepted as written: keyword (BM25) search; current version of an artefact only; no chunk overlap (heading path indexed instead); a replacement document gets a new number; an indexing failure after an approval is audited and the approval stands.

## What changed from the spec while building
- **`coverage` and `min_coverage` were added.** The demo showed that `relevance` (best hit = 1.0) cannot say whether any hit is good: for "What equipment is in the Atlas room?" the second hit had relevance 0.00 yet was returned. `coverage` is the share of the question's words a chunk contains (absolute), and `min_coverage` is a bar applied before the limit. A question with no real match ("capital of France") returns nothing at a bar of 0.5.
- **`min_relevance`** is kept for ranking hits against each other.
- **The seven schema-version tests** that hard-coded "2" were rewritten to say "the latest version", so the next migration doesn't break them again.
- **Settings:** four `CONTEXT_*` values (file size, PDF pages, documents per project, chunk target) with defaults; nothing needs adding to `.env`.
- **Engine:** `approve()` now calls the indexer and `reopen()` the un-indexer, each wrapped so a failure is audited and never undoes the human decision.

## Done when
- [x] Listed tests pass; full suite green (`883 passed, 1 deselected`, in PROGRESS.md)
- [x] Mutation check run with the baseline guard and reported honestly (64 of 64 caught, 0 skipped; the first run's 4 survivors were real test gaps and are fixed)
- [x] Frontend `npm run build` still succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] User ran the demo script (2026-10-27): identical output, 5/5 and isolation OK
- [x] User's judgement on the ranking: accepted as it stands ("yes, lets close S06"), after being shown its weaknesses (weak tails; one spurious word match, "two" in "floors two to four"; the keyword-search limit from decision 1). A coverage floor of about 0.5 is carried into S07 as a setting
- [x] User confirmed: closed 2026-10-27
