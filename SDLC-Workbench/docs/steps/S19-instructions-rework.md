# S19 · Build becomes instructions: vibe-coding instruction files instead of generated code

**Milestone:** M5  **Size:** L, built in slices  **Objectives:** O7 (reworded), O9, O3  **Depends on:** S11 to S15 (what the instructions are built from), S16 (sandbox), S17 (build machinery), S18a/b (report, reviewers)
**Status:** ANSWERED (all ten defaults) 2026-11-04; 19a is being built. Spec written 2026-11-04 from the user's message ("lets remove the actual code and replace it with vibe coding instructions that the user is able to give to the vibe coding agents. 1 file for each scenario I suppose. so it can be multiple files and these files will be saved as .md files"). **Waiting for the user's answers. Nothing is built or removed.**
(The step number S19 is used here for the rework; the plan's old S19 Deploy is renumbered in the plan when this is agreed.)

## Goal
After this step the Build phase no longer writes an application. It writes **a set of Markdown instruction files**, one per scenario, that a person pastes or attaches into a coding agent (Copilot, Claude, GPT or Gemini) so that agent builds the application. Each file points at the same design items the earlier phases already produced, so the instructions are traceable. The system can later **check** code that comes back (acceptance tests, automatic rules, the two reviewers), but it does not write the code.

## What I found before writing this (it shapes the plan)
1. **The design already holds almost everything an instruction needs.** For the user's real project (Meeting Room Booking): 16 user stories, 16 features, 11 journey steps, **7 use cases**, 8 API endpoints, 2 tables, **18 business rules**, 8 components, 14 interfaces. Each item has an ID and a `Derives from:` link. An instruction file is mostly an assembly of these, with the right ones selected and put in a build-ready order. That is a much smaller job for a model than writing code, and it is checkable.
2. **"Scenario" has to mean one thing, and the design offers four candidates:** a user story (16), a feature (16), a journey step (11), or a **use case (7)**. A use case is a whole goal of a person ("Reserve a room") that crosses screen, endpoint, table and rules; a story is too small to be a file, and a journey step is a fragment. I recommend the use case (decision 1).
3. **A scenario cannot be built alone.** Every scenario needs the tables, the project layout and the shared rules, or three files each invent their own database. So the set needs **a foundation file that comes first** (decision 2).
4. **The generator we built (S17 and S18) is large and working:** the sandbox, the file writer, the four checks, the fix loop, the round record, the report, the code rules and the two reviewers. Removing it would discard about 9,000 lines of tested work. **Most of it is the right tool for the NEXT job, which is checking code that comes back.** I recommend **switching the generator off and keeping the code, not deleting it** (decision 4).
5. **The instruction format is untried.** Whether a given tool follows these files well is unknown until a person tries one on a real project. The spec says so on the screen (decision 8) and leaves per-tool wording small and separate (decision 5).
6. **Acceptance tests are the only part that can be run.** If the instruction files ship with executable acceptance tests (decision 6), then once code is brought back, the existing sandbox and test runner give a real pass or fail. Without them every check is an opinion.

## Decisions (**the user said "happy with defaults.. lets go" on 2026-11-04, so all ten stand as written**)
1. **One instruction file per USE CASE** (UC items from the use-case diagram). The file is named `UC-001-browse-rooms-and-availability.md`: the ID, then a readable slug. A project with 7 use cases gets 7 scenario files. Default: use case.
2. **Plus two fixed files**, so the set is complete and ordered. `00-foundation.md` (stack, folder layout, the tables and their constraints, the shared rules, how to run it, what NOT to do) is built **first**. `99-acceptance.md` (the acceptance tests and how to run them; see 6) comes last. The tool is told to read `00-foundation.md` before any scenario and to do the scenarios in the order given. Default: yes.
3. **Each file is plain Markdown with fixed sections**, so it can be checked: *Goal*, *Read first*, *What to build* (screens, endpoints, tables touched, each by its design ID), *Business rules that apply* (RUL IDs, quoted), *Done when* (checkable statements), *Do not*, *Traceability* (every `Derives from:`). A section may be written "Not applicable", never left empty. Default: these sections.
4. **The code generator is switched OFF, not deleted.** The Build phase stops producing `database_schema`, `backend_code`, `frontend_code` and `test_suite` as code. The code (sandbox, writer, checks, loop, rounds, report, rules, reviewers) stays in the repository, tested, so it can verify returned code in a later step. Nothing is removed in this step except what has to go (the four code skills are retired and replaced by the instruction skills). Default: switch off, keep the code.
5. **Which tool the instructions are for is chosen by a radio button** (Copilot, Claude, GPT, Gemini), one choice per generation. The scenario content is the same for every tool; only a **short tool-specific header and style** differs (how to attach files, how that tool likes to be told to proceed). The choice is saved with the generated set so it can be seen later. Default: one common body, a small per-tool header, to be refined after a real trial.
6. **Acceptance tests are generated with the instructions, as executable Python**, in `99-acceptance.md` and also as real test files in the set (`tests/test_acceptance_*.py`), written against the design's API items (method, path, status codes, fields) and rules. They are meant to run against whatever the coding tool builds, over HTTP, so they do not depend on the tool's internal structure. They are NOT run in this step (nothing to run them against yet); they are checked to be **valid Python, collectable by pytest and traceable** to API and RUL items. Default: yes.
7. **The set is saved as one artefact per file in the Build phase**, each a Markdown body with its own ID, version, review and trace links (`BLD-INS-001` and so on), so it is versioned, listed and approved like every other artefact. A **Download** gives each file as `.md` (the file's own name) and the whole set as a **zip** (the user asked for `.md` files; a zip of them is a convenience, and the first time I propose one is here, so it is yours to refuse). Default: per-file `.md` downloads plus an optional zip.
8. **A plain notice on every screen that shows them:** *"These are instructions for a coding tool. This system does not write the application. How well a given tool follows them is untried: try one scenario first."* Same wording everywhere, like the prototype notice. Default: yes.
9. **The gate changes meaning.** Until code is brought back, the Build gate means **"the instructions are complete, consistent and traceable"**: every use case has a file; every file has all its sections; every API, table and rule in the design is named by at least one file or listed as not covered with a reason (the S15 traceability machinery already does this for other phases); no secret, no leftover placeholder. It does **not** say anything about correctness of code. Waivable by a person with a reason, as designed in S18. Default: this meaning.
10. **Checking returned code is a LATER step** (link a repository, pull it into the sandbox, run the acceptance tests, run the code rules, ask the two reviewers; the score is split into *checked by code* and *judged by a reviewer*, never one number). It is parked as D19 and depends on D18 (git linkage). Nothing in this step touches it. Default: later.

Stated, not asked: the instruction files are model-written (this is a real model task and costs money, but far less than code: no repair loop over code, no sandbox, no fix rounds); every claim in them comes from the design, and a checker rejects an instruction that names an ID that does not exist; no model is called in any test; the rework is built in slices that each leave the suite green; the old Build tests that exercise the generator keep running against the kept code.

## Slices (each ends with the full suite green and the resume log updated)
| Slice | Delivers |
|---|---|
| **19a** | The instruction skills (one for the scenario file, one for the foundation, one for acceptance) and their checks: required sections, every ID named exists in the design, no empty section, file naming. The four code skills are retired from the catalogue's Build phase. No UI. |
| **19b** | The Build phase writes the set: foundation first, then one file per use case in parallel, then acceptance; the generator hooks are switched off; traceability gets the new item kinds. |
| **19c** | The acceptance tests: generated, checked to be valid Python and collectable, traceable to API and RUL items. |
| **19d** | The gate (decision 9) and the screen: the tool radio button, the file list, collapsible Markdown, per-file `.md` download and the zip, the notice, the instructions-complete checks. |
| **later (D19)** | Bring code back and verify it. |

## Out of scope
- Writing any application code; running generated code; the sandbox as a generator (kept for D19); deploy (the old S19, renumbered); a live trial against a real coding tool (that is the user's to do, and the first thing the user will want after 19b).

## Tests (must pass before each slice is done)
| Area | Proves |
|---|---|
| skills | each loads and lints; the scenario skill reads the use-case, story, journey, API, table, rule and component items and nothing generated later |
| sections | a file missing a section, with an empty section, or with a section written only as a placeholder is sent back; `Not applicable` is accepted where allowed |
| ids | every design ID a file names exists in the design; an invented ID is a problem sent back; every file's `Derives from:` resolves |
| naming | files are named `<ID>-<slug>.md`, unique, safe (no path, no odd characters) |
| coverage | every use case has a file; every API, table and rule is named by a file or listed with a reason |
| order | foundation first, scenarios next, acceptance last; scenarios run in parallel |
| tool | each of the four selections produces the same body and a different header; the choice is saved |
| acceptance | the tests are valid Python, collected by pytest, and each names an API or RUL item |
| gate | each reason alone blocks it; all clean passes; medium and low never block; waivable with a reason; a waiver ends when any file changes |
| download | a file downloads as its own `.md`; the zip holds exactly the set, with the folder names, and nothing else |
| unchanged | the kept generator's tests still pass; every earlier phase is untouched; full suites and `export_contract --check` pass; no test touches `backend/data` |
| break-one-thing | a mutants file per slice, with the baseline guard; every survivor closed with a real test |

## Dependencies / installs
None.

## Questions for the user
Decisions 1 to 10 each carry a default. The ones worth reading first: **1** (the scenario is a USE CASE: say if you meant stories, features or journey steps), **4** (switch the generator off but keep the code, rather than delete it) and **6** (acceptance tests that run against whatever the tool builds). Decision **7** also adds a zip you did not ask for.

## Manual check for the user
After 19b, from `backend/`: `python -m scripts.instructions_demo` (offline and free: a scripted Build phase producing the files for a small project, then the checks catching a missing section, an invented ID and an uncovered endpoint). After 19d, the screen in your browser, and then the real test: give `00-foundation.md` and one scenario file to the tool you chose and tell me what it built.

## Done when
- [ ] Listed tests pass; full suite and `npm test` green (summary lines in PROGRESS.md)
- [ ] Break-one-thing check run with the baseline guard and reported honestly
- [ ] `npm run build` succeeds
- [ ] Manual-check list handed over
- [ ] PROGRESS.md and RESUME.md updated
- [ ] **You have run it, tried one file in a real coding tool, and told me what you saw**
- [ ] User confirms

## Answered by the user on 2026-11-04: storage is OPTION A
Decision 7 said 'one artefact per file'; the system holds ONE artefact per catalogue key. The user chose **A: one artefact, `build_instructions`, whose body holds the whole set, each file introduced by a `File: <name>` line.** One version is one consistent set. Review, versioning, approval and trace work unchanged; each file is cut from the saved text for its own `.md` download. A change to one file is a new version of the set.
