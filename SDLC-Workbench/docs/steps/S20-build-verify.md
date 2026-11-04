# S20 · Build Verify: how far did the real build drift from the design?

**Milestone:** M6  **Size:** L, four slices  **Objectives:** O1, O9  **Depends on:** S15 (traceability), S19a to S19d-1 (the instruction set and the interface contract)
**Status:** SPEC WRITTEN 2026-11-05 from the user's proposal and their answers ("1. yes, local machine only. 2. only Python/FastAPI and Node.js or similar for the front end, use a smarter search for APIs and do not be hooked on exact names. 4 is fine. 5, think on this after. 6. like the highlighter view, but with visual icons and colour coding, not only text"). **ANSWERED 2026-11-05: all ten defaults ("all defaults is good to start"). BUILT 2026-11-05 while the user was away ("finish stage 20, consider all defaults"): 20a, 20b, 20c, 20d. Waiting for the user to try it on the screen.**
**What this replaces:** the old Deploy phase is NOT removed by this spec (decision 5 was "think on this after"). This step only ADDS the check; what happens to the Deploy and BAU Handover phases is its own conversation, held later.

## Goal
After this step a person can point the workbench at the **backend and frontend folders of the real build** on their own computer and get a **picture of how far the build has drifted from the design**: which designed endpoints, tables, screens and business rules were found in the code, which were not, and which things exist in the code that the design never mentioned. It is a highlighter, not a test and not a gate. It never runs the code.

## What the user said, and what it means here
- **Local machine only.** The backend that reads the folders runs on the same computer as the person (it already binds to 127.0.0.1). No upload, no cloud, no remote paths.
- **Only Python/FastAPI for the backend, and Node.js or a similar frontend.** Other stacks are named as "not understood" and are not guessed at.
- **A smarter search, not exact names.** A designed `POST /api/reservations` can be found as `POST /api/bookings`. Matching is by meaning of the path and fields, in steps (below), and every match shows HOW it was matched, so a person can overrule it.
- **Academic, a highlighter.** Real builds always deviate. The result is "how much", not "pass or fail". The wording says so.
- **Visual and colour coded.** Icons and colours first, text second (see decision 6).

## What I found before writing this (read from the code, not assumed)
1. **The design already holds exactly what a check needs.** Every endpoint has a method, a path, request and response field names and status codes in the foundation's interface contract (S19d-1, parsed by `build/contract.py`, with `parse_contract`, `norm_path`, `names_used`, `codes_in`, `nearest`). Tables and rules are design items (`TBL-`, `RUL-`); screens are `HFS-` items. No new design data is needed.
2. **A traceability engine and screen already exist** (`trace/traceability.py`, S15): items, links, chains, gaps, and a screen that shows them. The verify result is the same idea with a new link kind, **"found in the build"**. Its rule table and its gap sentences can be reused.
3. **The workbench has never read the user's own code.** Everything so far reads documents the user uploaded or artefacts the agents wrote. Reading a folder is a new kind of access and needs its own safety rules (decision 1). `CLAUDE.md` forbids reading `.env` files; that rule extends to the folders read here.
4. **FastAPI routes can be read without running them.** Decorators such as `@app.get("/api/rooms")` and `@router.post("/reservations")` with `APIRouter(prefix=...)` and `include_router(..., prefix=...)` are plain syntax. Python's own `ast` module reads them with no new package. Request and response models are Pydantic classes (field names and types are readable the same way); status codes come from `status_code=` and `raise HTTPException(status_code=...)`. Tables are SQLAlchemy classes (`__tablename__`, `Column(...)`) or `CREATE TABLE` text in `.sql` files or strings.
5. **A Node or similar frontend is harder to read exactly and easy to read roughly.** Pages and routes (React Router `path=`, file-based `pages/` or `app/` folders, Vue router), API calls (`fetch("/api/...")`, `axios.get(...)`, a client file with helper functions) and form field names can be found with careful pattern matching. A full JavaScript parser would be a new package in the shared venv (not allowed without the user's OK), so the first version uses patterns, and says "found by pattern, not parsed".
6. **Business rules are logic, not names.** A rule such as "a booking may not overlap another" has no marker in code. The honest evidence is weak: a test, a comment or an error message that names the rule's ID or quotes its words. The report says "weak evidence" in words and in the icon, never "implemented".
7. **A real build will mostly not match by name.** Engineers rename things. So an exact-name check would report most of the design as missing and be useless; that is why matching is by steps, with a visible reason.

## Decisions (each has a default; say "all defaults" or change any)
1. **Reading the folders is safe by construction.** The person gives one backend folder and one frontend folder (the frontend is optional). The workbench reads **text files under those folders only**, never follows a link out of them, never reads `.env`, `*.pem`, `*.key`, `id_*`, `.git`, `node_modules`, `venv`, `.venv`, `__pycache__`, `dist`, `build` or any file over 500,000 characters, never writes to them, and **never runs anything in them**. It reads at most 3,000 files per folder and says plainly when it stopped. The folder path is typed or pasted (a browser cannot browse a disk); it must exist on the machine the backend runs on. Secrets found in the text are not copied into the result (the existing scanner runs on what is stored). Default: exactly this.
2. **What is understood.** Backend: **Python and FastAPI** only (also reads Flask-style decorators only if cheap; not promised). Frontend: **JavaScript/TypeScript with React, Vue or plain `fetch`/`axios` calls, found by patterns**. Anything else (Java, Go, Rust, C#, PHP, Ruby) is reported as "this folder looks like <language>; this version reads Python/FastAPI and Node-style frontends only" and nothing is guessed. Default: as written.
3. **Matching is by steps, strongest first, and every match says which step found it.**
   1. *Exact:* same method and same normalised path (`norm_path`, so `{id}` equals `<id>` equals `%s`).
   2. *Same shape:* same method and the same path after ignoring the prefix and plural forms (`/api/reservations`, `/reservations`, `/api/reservation/{id}`).
   3. *Words:* the path's words compared with the design's endpoint title, the use case it serves and the field names it carries (`/api/bookings` against "reserve a room", with `room_id`, `start_time`, `end_time`). A score from 0 to 1, shown.
   4. *Optional model help (off by default):* one call that is shown the unmatched designed items and the unmatched built routes and **suggests** pairings with reasons. A suggestion is labelled as such and is never counted as a match until the person accepts it.
   Steps 1 to 3 cost nothing and are repeatable. A match below 0.5 is listed as "possible", not "found". Default: steps 1 to 3 always; step 4 only when the person presses a button, with the cost shown.
4. **What is compared** (the person asked for backend and UI "traceability style reports"): *endpoints* (method, path, request and response field names, status codes), *tables* (name, column names), *screens* (a page or route found for each `HFS-` item, and which endpoints it calls), and *business rules* (weak evidence only, as in finding 6). Each designed item gets one of five states: **found**, **found with differences** (names or codes differ), **possible**, **not found**, **weak evidence** (rules only). Each built thing the design does not mention is **built but not designed**. Default: as written.
5. **Deploy and BAU Handover are not touched by this step.** Build Verify is added as a place in the Build phase's neighbourhood; the order of phases and what happens to Deploy is decided separately (the user: "lets think on this after"). To avoid a half-change, this step adds Verify as its own screen reached from the project page, **not** as a gated phase, until that decision is made. Default: a separate screen, no change to the phase list.
6. **The picture is icons and colours first.** One card per area (Endpoints, Tables, Screens, Rules), each with a **ring** showing the share found, and under it a row of small tiles, one per designed item, **coloured by state and carrying an icon**: green tick (found), amber tick with a small mark (found with differences), blue question (possible), red cross (not found), grey eye (weak evidence, rules), purple plus (built but not designed). Colours also differ in shape, so the picture reads without colour (a colour-blind person, a black-and-white print). Hover or press a tile for its words: what was designed, what was found, which file and line, how it matched, and what differs. Text is always there for a screen reader. Default: as written.
7. **Repeated runs with history.** A person builds, checks, builds again. Each run is saved with its time, the two folder paths, the design version it compared against, and the counts; the screen shows the last run and a small trend line of the found share per area. A run never changes the design or the instructions. Default: keep every run; show the last and the trend.
8. **A different design version is not mixed.** A run records which version of each design artefact it compared with. If the design has changed since, the screen says "the design changed after this run" and offers to run again, like the existing out-of-date banner. Default: yes.
9. **Where the result lives.** A run is stored as its own record in the database (not as an artefact, because it has no author and no review), with the matches as rows (designed item, built thing, step, score, file, line). The result is readable as a download (Markdown for people, JSON for tools). Default: own tables, append-only like the rest.
10. **Order and what is left for later.** Built in four slices (below). Parked: scanning more languages, running the code or its tests, a git history comparison, a pull-request comment, a CI step that fails below a threshold, a gate on approving the phase, and writing the design back from what was built ("reverse engineering"). Default: as written.

Stated, not asked: nothing is run, imported or executed from the user's folders; the scan reads text only. No model is called in any test (the optional step 4 is scripted). The existing phases, artefacts, reviews and the instruction set are untouched. A folder path is never logged in full outside the run record, and never sent to a model; only item text and short code excerpts selected by the scan are (step 4 only). The result is clearly labelled as advice about drift, not a pass or fail.

## Design notes
- **Modules (all new):** `app/verify/readers/python_fastapi.py` (the `ast` reader: routes with prefixes, models, status codes, tables), `app/verify/readers/web.py` (patterns for routes, API calls, form fields), `app/verify/walk.py` (the safe folder walk of decision 1), `app/verify/match.py` (the steps of decision 3), `app/verify/report.py` (states, counts, the five-state result), `app/verify/service.py`, `app/routes_verify.py`, tables `verify_runs` and `verify_matches` in `db.py` with the usual append-only triggers.
- **The design side** is read from the saved artefacts through the same gather code the traceability screen uses, plus `parse_contract` for endpoints; no new design data.
- **Screen:** a `Verify` page reached from the project page (a card beside Traceability), with the two path boxes, a Run button, the four ring cards, the tile grid, the "built but not designed" list, the trend, and a download. Reuses `Notice`, the chips and the traceability colour tokens.
- **Counts that move:** a new router and tables; contract fixtures for the run list and a run; the OpenAPI/route lists pinned in tests.

## Slices
| Slice | Delivers |
|---|---|
| **20a (built)** | The safe walk and the Python/FastAPI reader: routes (with router prefixes), request/response model fields, status codes, tables and columns. Pure code, tested on small fixture projects written into temp folders. No matching yet. |
| **20b (built)** | The matching steps 1 to 3, the five-state result per designed item and the "built but not designed" list, the run record and history in the database, the route. Offline demo script on a fixture project. |
| **20c (built)** | The web reader (routes, API calls, form fields by pattern) and the screens-to-endpoints matching; the rule weak-evidence check. |
| **20d (built)** | The screen: ring cards, coloured icon tiles, detail on press, trend, downloads, the "design changed" banner; the optional model-suggestion button (step 4). |

## Out of scope
Other languages; running or importing the user's code; a gate on approval; the phase list and the Deploy and Handover phases (decision 5); reverse engineering the design; CI integration; reading remote repositories.

## Tests (must pass before each slice is done)
| Area | Proves |
|---|---|
| safe walk | files outside the folder, links leading out, `.env`, keys, `.git`, `node_modules`, venvs and oversized files are never read; the file cap stops the walk and says so; a missing or non-folder path gives a plain sentence; nothing is ever written or executed |
| fastapi routes | decorators on `app` and on routers, `prefix=` on the router and on `include_router`, path parameters, methods, async and sync functions, `status_code=`, `HTTPException` codes; a syntax error in one file is reported for that file and does not stop the scan |
| models and tables | Pydantic request and response fields (including nested and optional), SQLAlchemy classes and `CREATE TABLE` text give table and column names |
| matching | exact, same-shape and words steps each find what they should and no more; a match says which step and the score; below 0.5 is "possible"; two designed items never claim one built route; the order of files does not change the result |
| states | each designed item gets exactly one of the five states; "built but not designed" lists what was not matched; counts add up |
| differences | a matched endpoint with different field names or status codes is "found with differences" and lists them |
| web reader | React Router, Vue router, file-based pages and `fetch`/`axios` calls are found; a pattern the reader cannot read is reported, not skipped silently |
| rules | a rule named in a test or comment is "weak evidence" and never "found" |
| history | every run is kept; the design version it compared against is recorded; a later design change shows the banner; a run never changes any artefact |
| page | ring per area, a tile per designed item with the right colour AND icon, detail on press, the trend, a screen-reader text for every tile, the download |
| unchanged | every earlier phase, artefact, review and the traceability screen; `export_contract --check`; no test touches `backend/data` or a real project folder |
| break-one-thing | a mutants file per slice with the baseline guard; every survivor closed with a real test |

## Dependencies / installs
None. Python's `ast` and the standard library only. If the web reader proves too weak with patterns, a JavaScript parser would be proposed as a separate, optional install and would need the user's OK.

## Questions for the user
Say "all defaults" or change any of the ten. The ones most worth a look: (2) FastAPI-only for the backend, and patterns not a parser for the frontend; (3) step 4, the optional model suggestions, off by default; (5) a separate screen now, the phase decision later; (7) every run kept with a trend.

## Manual check for the user (we do not run the app)
After 20b: `cd backend && python -m scripts.verify_demo` (offline and free: a small FastAPI project written to a temporary folder, a design with one renamed endpoint, one missing endpoint and one extra route, and the report it gives). After 20d: restart the backend, open Verify, paste your backend folder, run, and look at the rings and tiles. I will not run it on your folder.

## Done when
- [ ] Listed tests pass; full suites green (summary lines in PROGRESS.md)
- [ ] Break-one-thing check run with the baseline guard and reported honestly
- [ ] Manual-check list handed over
- [ ] PROGRESS.md and RESUME.md updated
- [ ] **You have run it on your own build and told me what you saw**
- [ ] User confirms

## What was built, and what to know (written after the build)
- **Backend** (`app/verify/`): `walk.py` (the safe walk), `readers/python_fastapi.py` (routes with prefixes, parameters, models with inherited fields, status codes, tables, and the comments/docstrings/test names/messages that the rule check reads), `readers/web.py` (React Router and Vue router routes, file-based pages, `fetch`/`axios` calls, form fields, comments and test names, all by pattern), `design.py` (the design side from the saved artefacts; the Build set's interface contract supplies fields and status codes), `match.py` (exact, then same shape, then words; 0.5 or more is found, 0.25 to under 0.5 only possible; rules are weak evidence only; screens are matched to pages by words), `report.py` (counts, share found, Markdown), `service.py`, `routes_verify.py`, schema v8 (`verify_runs`, `verify_matches`, append-only).
- **Frontend**: `api/verify.ts` (decoders), `lib/verify.ts` (the look of each state, the ring, the trend, all as plain tested functions), `components/VerifyPanel.tsx` (rings, coloured icon tiles, legend, trend, notes, downloads), `pages/VerifyPage.tsx`, `lib/verifyPaths.ts` (the folders last used, remembered in this browser), a **Build Verify** link under Traceability in the phase rail, and the address `#/projects/<id>/verify`.
- **Not done on purpose:** the optional model step that suggests pairings (decision 3, step 4) is NOT built; it is off by default and costs money, so it waits for your word. The phase list, Deploy and BAU Handover are untouched (decision 5).
- **What it cannot do:** it never runs your code; a prefix built in code is flagged as unknown, not guessed; a frontend written in an unrecognised style gives a plain note, not a guess; rules are only ever weak evidence.
