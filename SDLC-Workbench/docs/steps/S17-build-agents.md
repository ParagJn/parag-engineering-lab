# S17 · Build agents

**Milestone:** M5  **Size:** L, built in three slices  **Objectives:** O6, O7  **Depends on:** S11 (agent runtime), S13 to S15 (what the build reads), S16 (the sandbox)
Plan test (`05-build-plan.md`): *with scripted mock "developer" responses the fix loop converges; the iteration cap stops runaway; results come from real test execution; per-component isolation.*

Phase 4 has four artefacts a developer writes (database schema, backend code, frontend code, test suite). Until now every artefact was Markdown that a reviewer reads. These four are **code**, and code is judged by running it. S17 teaches the agent runtime to produce code, put it in the project's sandbox workspace (S16), and report what happened when it ran. The test report and the code and security review belong to S18 and are not touched here.

## Slices (each ends with the full suite green and `docs/RESUME.md` updated, so stopping after any slice is safe)
| Slice | Delivers | Model calls in its tests |
|---|---|---|
| **17a** | Four skills; the code-reply format and its checks; writing a saved artefact's files into the workspace; one real check per artefact (the schema creates its tables, code compiles, scripts parse, tests collect). No loop. | None (scripted replies) |
| **17b** | The bounded write → test → fix loop: run the tests, send real failures back to the developer agent, stop at the cap. | None |
| **17c** | Wave 1 running in parallel with per-component isolation; wave 2 waiting for the backend; the phase wired into the runner. | None |
| live run | One real run with models to see the quality. Uses the $5. Only on your word. | Real |

## What I found before writing this (it shapes the plan)
1. **The runtime already does most of the work.** An artefact is a Markdown body in `<artefact>` tags, checked by `check_body` (sections, citations, item IDs, secrets, drawings), repaired by sending problems back to the model, saved as a version, reviewed, traced and approved. If a Build artefact is also a Markdown body, **versions, review, traceability, approval and replay all work with no change**. So the code lives in the body, and a separate deterministic step turns it into files.
2. **The roles are already routed** (`routing.yaml`): database engineer on Haiku, backend developer and test engineer on OpenAI, frontend developer on Gemini. Four artefacts, four skills, no new routing.
3. **Wave 1 is parallel, so the frontend cannot wait for the backend.** The only contract both can share is the low-level design (its endpoints, tables and rules). The skills say so: the LLD is the contract, and neither side reads the other's code. The test suite waits for the backend (catalogue wave 2) and does read it.
4. **The sandbox allows what these checks need and no more.** `python -m compileall`, `python <script>`, `pytest --collect-only`, `node --check` and in-process FastAPI `TestClient` tests all run. A generated server cannot be started and probed (loopback is denied); that is S19's problem, not S17's.
5. **A model's output has a size limit.** An artefact body is capped at 60,000 characters (`reply.py`), and a long reply can be cut off by the output limit. A whole app does not fit in one reply unless the application is small. The skills cap the number of files, and the existing "cut off, write it shorter" repair applies.

## Decisions (defaults marked; "all defaults" is a fine answer)
1. **Where the code lives.** In the artefact body: a **Files** section with one numbered item per file, and a **Code** section with one fenced block per file, each introduced by a line `File: <path>`. The body is the source of truth (versioned, reviewable, replayable). The workspace is **written from it**, never edited by hand. Default: this.
2. **Item IDs.** One item per file: `DBF-001` (database), `BEF-001` (backend), `FEF-001` (frontend), `TSF-001` (tests). Each ends with `Derives from:` and the upstream IDs it implements (`TBL-001`, `API-002`, `RUL-004`), so S15's traceability links code back to the design with no new code. Backend `Covers: API`, database `Covers: TBL`; frontend and tests declare no `Covers` (a screen or a test does not have to map one-to-one, and a false gap is worse than none). Default: this.
3. **One folder per component, and an artefact may only write its own.** `db/` for the database, `backend/` for the backend, `frontend/` for the frontend, `tests/` for the tests. A file outside the artefact's folder is a **problem sent back to the model**, not a silent skip. Writing a new version replaces **only that artefact's folder**. This is the per-component isolation S17c tests in parallel. Default: this.
4. **A fixed, boring stack so every command is predictable.** Python (the shared venv's), FastAPI, the standard-library `sqlite3`, no ORM; plain HTML and JavaScript, **no CDN, no external URL, no build step, no `npm install`** (there is no network and nothing may install). `backend/main.py` exposes `app`; `db/init_db.py` builds `db/app.db` from `db/schema.sql`; tests live in `tests/test_*.py` and import `backend.main`; run with `pytest` from the workspace root. Default: this stack (it is what the architecture doc already says).
5. **The checks in 17a, each a fact from really running something.**
   - *Database:* run `python db/init_db.py` in the sandbox; the backend then reads `sqlite_master` of the file it produced (read-only, table names only) and lists **tables created** and **tables the design named that are missing**.
   - *Backend:* `python -m compileall -q backend` (syntax errors, with file and line). Importing and calling it is what the tests do in 17b; I will not pretend compiling is more than compiling.
   - *Frontend:* `node --check` on every `.js` file (reported "skipped, node not installed" if absent), and the backend's own HTML parser confirms every local `src`/`href` points at a file the artefact wrote and **no reference leaves the machine** (a CDN link would silently fail offline).
   - *Tests:* `pytest --collect-only -q`: how many tests, and any collection error. They are not run until 17b.
   Default: these four.
6. **A failing check is a problem sent back to the model**, like a missing section. The same repair loop (and its attempt cap) is used for 17a. The test-failure loop of 17b is a separate, deeper loop with its own cap. Default: yes.
7. **Where results are kept in 17a.** Returned as facts to the caller and written to the **audit log** (counts and names, never file contents or output). **No new database table in 17a**; the persistent record of each attempt arrives with the loop in 17b, where it is needed. Default: this.
8. **Limits.** At most **12 files** per artefact, **60,000 characters** per body (the existing cap), the sandbox's per-file, file-count and total-size limits. A secret in the code is refused by the scanner exactly as in any artefact. Default: these.
9. **What each skill reads.** Database: low-level design (tables and rules), high-level design, functional requirements. Backend: low-level design, the database artefact (so table and column names match), functional requirements. Frontend: high-fidelity wireframes, user journey, low-level design (the endpoint contract). Tests: backend code, low-level design, functional requirements. Default: these.
10. **Models are not called in any test.** Scripted replies only, through the mock provider. The live run is separate and spends from the $5 only after you say go. Default: yes.

Stated, not asked: the sandbox is the only place generated code runs; the backend process never imports or executes it. The one thing the backend does read is the SQLite file the sandboxed init script produced, opened read-only for table names. Nothing is exposed over HTTP in 17a; the phase is not wired into the runner until 17c.

## In scope (17a)
- Four skill files under `backend/app/phases/skills/` (`database_schema.md`, `backend_code.md`, `frontend_code.md`, `test_suite.md`) in the existing fixed format, linted by the existing skill linter.
- `backend/app/build/`: the code-reply parser (`File:` blocks, folder ownership, duplicate and count rules), the writer (artefact version → files, through `SandboxService`), the four checks, and a small `BuildService` that ties them together.
- The body checker is extended so a Build artefact's file blocks are validated as part of `check_body` (so a person's hand edit goes through the same rules).
- `scripts/build_demo.py`: offline and free; feeds scripted replies, writes the files, runs the checks, prints each result.
- A mutants file for the new code, run with the baseline guard.

## Out of scope (later)
- The write → test → fix loop (17b); parallel waves and the runner wiring (17c); the test report and code and security review (S18); running a generated server (S19); any screen (S18 shows results).

## Tests (must pass before 17a is done)
| Area | Proves |
|---|---|
| skills | all four load and lint; each names the right role, item prefix and `Covers`; none reads something generated after it |
| reply format | a good body parses to the exact file set; a missing `File:` line, a file listed but not written, a file written but not listed, a duplicate path, a path outside the artefact's folder, a bad path (`..`, absolute, `.env`), more than 12 files and an oversize body are each a distinct sentence |
| check_body | the new rules run for a Build artefact and for a hand edit; a planted secret is refused and listed first; the other artefacts' behaviour is unchanged |
| writing | files land under `workspaces/<project>/<folder>/`; a new version replaces only its own folder; another component's files, and a file the agent did not write, are untouched; a failed write leaves the old version whole |
| database check | a good schema creates its tables and reports them; a schema with a syntax error reports the error; a missing table the design named is listed; a script that tries the network is refused by the OS and reported |
| backend check | good code compiles; a syntax error is reported with file and line |
| frontend check | a bad script is reported; a missing local file and an external URL are each reported; plain HTML passes |
| test check | N tests are counted; a collection error is reported; nothing is run |
| isolation | two projects' files never meet; one component's check cannot read another project's workspace |
| audit | each write and check adds a row with no contents or output |
| unchanged | the full backend and frontend suites, and `export_contract --check`, still pass; no test touches `backend/data` |
| break-one-thing | a mutants file for the parser, folder ownership, replace-own-folder-only and each check, with the baseline guard; every survivor is closed with a real test |

## Dependencies / installs
None.

## Questions for the user
Decisions 1 to 10 each carry a default. The ones worth reading first: **1** (code lives in the artefact body, files are written from it), **3** (an artefact writes only its own folder) and **5** (the four checks, and that compiling is not called testing).

## Manual check for the user (we do not run the app)
This slice has no screen. From `backend/`: `python -m scripts.build_demo` and read each line; then `python -m pytest tests/ -q`. Tell me whether the file limits (12 per artefact) and the fixed stack feel right for the apps you want the demo to build.

## Done when
- [ ] Listed tests pass; full suite and `npm test` green (summary lines in PROGRESS.md)
- [ ] Break-one-thing check run with the baseline guard and reported honestly
- [ ] Manual-check list handed over
- [ ] PROGRESS.md and RESUME.md updated
- [ ] **You have run it and told me what you saw**
- [ ] User confirms

## What was built in 17a, and what differed (2026-11-02)
Built as specified, all ten decisions at their defaults. Found by trying, and changed the code:
- **Compiling writes files.** `python -m compileall` leaves `__pycache__/*.pyc` even with bytecode switched off. They would count against the workspace's file limit and are not the model's files, so the backend check removes them (and the folders) afterwards.
- **Opening a missing file with sqlite3 creates it.** The table listing would then have found the empty file it had just made. The check now looks for `db/app.db` first.
- **pytest exits 5 when it finds no tests.** That is its own answer ("no tests were found"), reported as that and not as a collection error.
- **A check must never pass on nothing.** `compileall` is content with a folder that is not there; the backend check now fails with "there is no backend code".
- **Table names come only from a plain first word** (lower-case with underscores, or in backticks). A design line that starts "The invoices table" is left out instead of guessed at, because a wrong name would send the model off to build a table nobody asked for.
- **Four existing tests pinned counts the new skills legitimately change** (skills shipped 16 to 20, item prefixes, the traceability rules 14 to 18, the column order, the status block, the skills report). Each now says why. The traceability matrix gains four Build columns that show as "not started" until Build runs.
- **Two checks were dropped as redundant:** the `-p no:cacheprovider` flag on `--collect-only` (collecting writes no cache) and special cases for `mailto:`, `tel:` and `javascript:` references (they have a `:` and no local file, and were never reached).
- **Not done, as stated:** the write → test → fix loop (17b); parallel waves and wiring into the runner (17c); a persistent record of each attempt (17b); any screen (S18).

## Manual check for the user (17a)
From `backend/`: `python -m scripts.build_demo` and read each line (the four artefacts written and checked, then nine things a model might really write, each refused or failed with a reason); then `python -m pytest tests/ -m sandbox -q`. Tell me whether the limits (12 files per artefact, one folder per artefact) and the fixed stack feel right for the apps you want the demo to build.

**2026-11-02, the user ran `python -m scripts.build_demo` and `pytest tests/ -m sandbox -q` (115 passed) and said the 12-file limit, one folder per artefact and the fixed stack (FastAPI, sqlite3, plain HTML and JS) suit them.** **S17a CLOSED 2026-11-02 on their word** ('lets close S17a and move towards S17b'). Nothing is committed to git until all S17 slices are done, at their request.
