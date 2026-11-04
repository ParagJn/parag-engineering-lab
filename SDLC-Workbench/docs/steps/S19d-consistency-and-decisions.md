# S19d · The files agree with each other, and the open questions are answered once

**Milestone:** M5  **Size:** M, two slices  **Objectives:** O7 (reworded), O9, O3  **Depends on:** S19a to S19c (closed: the set, the composer, the UI files)
**Status:** ANSWERED 2026-11-05: **all ten defaults** ("all defaults is good"). 19d-1 is being built. Spec written the same day after the user said "lets do [the consistency check] and the decision step also, i agree, good idea to answer them".
**Placement note (decided while building, not asked):** the design index is written second-to-last of the front matter, after the UI guide (so the order is foundation, UI guide, design index, use cases, screens, acceptance) because its name sorts after `01-ui-guidelines.md`. A set written before this step has neither the contract nor the index and is not refused for lacking them: the new checks start when the foundation carries an Interface contract section (or when the composer asks for one).
(The numbering moves: the acceptance tests as valid Python become 19e, and the gate and screen with the tool radio button and zip become 19f.)

## Goal
After this step an engineer (or a coding tool) who is given the instruction files finds **one name for each thing across all the files**, and finds **the questions the design left open already answered** (or clearly marked as still open, by number), instead of 46 separate "ask the person" lines.

## What I found before writing this (read from the user's real saved set and design)
1. **Names drift because nobody fixes them.** The low-level design says only "Input: date, start time, end time". Each file then invents the wire names. The real set has `start`/`end` for the availability endpoint but `start_time`/`end_time` for the reservation endpoint and the table, and `date` in one response but `reservation_date` in another. An independent reader of the real files found this, plus other drift (a bare list in one place and an object with a key in another; status codes 500 and 503 that the foundation's list does not contain). A check can find a name that was never declared; it cannot decide which of two names is right. That decision belongs in the foundation, once.
2. **The open questions are real, repeated and scattered.** The set tells the tool to "ask the person" on 46 lines in 13 files, but they are about 9 topics: sign-in and administrator status (27 lines), who may cancel, slot length and the four-hour maximum, public holidays and time zone, past slots and how far ahead, unique room names, floors and capacity, what happens to future reservations when a room is retired, accessibility and browser support, and whether availability needs sign-in. The design artefacts already carry about 107 lines under "Open questions" (13 artefacts), which is where they come from. They are in no one place, so no one can answer them once.
3. **The set names 69 design IDs and explains 12.** The files lean on `DEC-`, `COMP-`, `IFC-`, `FR-`, `JS-` and `HFS-` IDs that live only in the design. An engineer or tool given just the set cannot read most of them.
4. **The pieces to build on exist.** The foundation is written first and every later file is shown it, so a contract placed there reaches every file. A per-file check with a per-file repair already exists, so a wrong name costs one file, not the set. A person's edit goes through the same checks. The "out of date" banner and its re-run already exist for an artefact built on an upstream one that has since changed. A decisions artefact is therefore an ordinary artefact, not a new mechanism.
5. **What a check cannot do.** Two files that contradict each other in meaning (for example, whether a cancelled reservation is listed) cannot be found by looking at names. The contract and the decisions reduce those; a person still reads the files.

## Decisions (each has a default; say "all defaults" or change any)
1. **Prevent first, then check.** The foundation gets a required section **Interface contract**: for each endpoint (API ID), the method and path, the request field names with their types, the response shape with its field names (including whether a list is bare or inside a named key), and the status codes it can return. The foundation is already shown to every later file, so they use these names. Default: yes.
2. **What the mechanical check covers:** (a) field names in JSON examples, "Input" and "Output" lines and tables; (b) status codes written next to an endpoint; (c) endpoint method and path (a number in a path counts as the path parameter). It does **not** try to judge shapes or meaning. Default: those three.
3. **Where it runs:** on each file as it is written (so only that file is sent back, with the exact name to use), again on the whole set when it is saved, and on a person's edit. Default: all three.
4. **How strict:** a name, code or path the contract does not declare is a **problem sent back**, not a warning. Names that are plainly not wire names (file names such as `identity.py`, environment variables, SQL words, table names the foundation declares) are skipped. Default: strict, with that skip list.
5. **A design index written by the system, not the model:** one more file, `02-design-index.md`, listing every design ID the other files name with its one-line title from the design (69 IDs on the real project). No model call, no cost. It is shown first-class in the set and is downloadable like the others. Default: yes.
6. **The open questions become a normal artefact, `build_decisions`** (prefix `BLD-DCN`, items `DCN-001` and so on) in the Build phase, written **before** the instruction set by **one** model call that reads the design's open questions and merges the repeats into a short list. Each decision has the question, the choices, a **proposed** answer marked as proposed, an **Answer** line (blank or "Open" until a person writes one), and where it came from. Default: yes. It is required, so the Build phase goes from 1 artefact to 2.
7. **How a person answers:** with the existing "Edit by hand" on that artefact (write the answer on its Answer line); a nicer form is later. Nothing a person did not write is ever treated as an answer: a proposed answer stays proposed until they put it on the Answer line (or write "accept proposed" there). Default: yes.
8. **How the instruction files use the decisions:** a decision with an answer is stated as settled in the foundation (new section **Decisions**, with the DCN number) and the other files follow it; a decision still open is written as `Open DCN-003: do not decide; ask the person`. A file that tells the tool to ask without naming an open DCN number is sent back, and so is one that cites a DCN that does not exist. Default: yes.
9. **After answering:** the set is now built on an older version of the decisions, so the existing "out of date" banner offers to write it again (the whole set, about 14 calls, a few dollars on the real project). Rewriting only the files an answer affects is parked as D21. Default: whole set.
10. **Order of the first run:** one run writes the decisions and then the instructions straight away (the instructions will carry the open questions by number). The person then answers and rewrites. A run that **stops after the decisions** so you can answer first is parked as D22. Default: one run, answer, rewrite.

Stated, not asked: the framework's own default validation answers (FastAPI's 422 for a malformed body) differ from the 400 the files promise, and nothing warned the coding tool; the foundation's Interface contract section also records, for the chosen stack, how the framework's own errors are turned into the contract's refusal body and codes. This is added to the skill, not a decision. No model is called in any test. The check is plain code over text. Every earlier phase and the closed slices stay as they are; a set written before this step is still shown and still passes its old checks (the new checks apply to sets written after it).

## Design notes
- **Contract section.** One list entry per endpoint in a fixed shape the checker can read: `- API-002 GET /api/availability. Request: date (string YYYY-MM-DD), start_time (string HH:MM), end_time (string HH:MM). Response 200: object with rooms_free (list), rooms_reserved (list). Errors: 400, 401. Derives from: API-002.` The checker reads names, codes and the path from it. It is a new required foundation section (`SECTIONS`), checked like the others, with a non-empty rule.
- **Per-file check.** `check_file` gets the foundation text for a use case, screen or acceptance file and flags: a JSON key or an "Input"/"Output" field name not in the contract; a status code not in the contract (or the foundation's general list); a `METHOD /api/path` that matches no contract entry. The message names the exact name to use (the nearest declared one) so the repair is one step.
- **Index.** A new kind `index` with a fixed name, written by `assemble` from the design's item lines; excluded from the model-written checks; part of the set's order after the foundation.
- **Decisions.** New catalogue artefact `build_decisions` (role `solution_architect`), skill `build_decisions.md` (inputs: the design artefacts the instruction skill already reads), `Items: DCN in Decisions`, `Covers:` none. The instruction skill and the composer read it as an input; `build_instructions` waits for it (`after`). The checker for `build_instructions` takes the decisions' open numbers.
- **Counts that move** (pinned in tests and fixtures, as before): artefacts 28 to 29, required 18 to 19, the Build phase 1 to 2, skills 17 to 18, the traceability rules and columns (a new `DCN` item kind), the catalogue document, and the contract fixtures. All regenerated after reading the diff.
- **Screen.** None new in this step: the decisions artefact appears as an ordinary card with Read and Edit by hand; the run panel lists it as a row. A purpose-built answer form is later.

## Slices
| Slice | Delivers |
|---|---|
| **19d-1** | The contract section in the foundation, the mechanical check (names, codes, paths) per file and per set and on a person's edit, the system-written design index, the skill's new Method. No new artefact, no catalogue change. |
| **19d-2** | The `build_decisions` artefact and skill, its place before the instructions, the open-question rule in the checks, the foundation's Decisions section, the use of answers by every file, the stale re-run, the counts and fixtures. |

## Out of scope
A purpose-built answer form; rewriting only the affected files (D21); stopping after the decisions (D22); judging whether two files mean the same thing; the acceptance tests as valid Python (19e); the gate, tool radio button and zip (19f); running any generated code.

## Tests (must pass before each slice is done)
| Area | Proves |
|---|---|
| contract | a foundation with no Interface contract, or an entry with no method and path, or no fields, is sent back; a complete one passes; the reader returns names, codes and paths exactly |
| names | a use case, screen or acceptance file using an undeclared field name is sent back with the nearest declared name; the declared name passes; a name inside a file name, environment variable or SQL word is skipped |
| codes | a status code not in the contract is sent back; one in the contract passes; the foundation's general codes count |
| paths | a method and path that matches no contract entry is sent back; a number in a path matches the path parameter; a different method on a declared path is sent back |
| scope | the check runs per file, on the whole set at save, and on a person's edit; a set written before this step still passes the old checks |
| repair | one file with a wrong name is sent back alone and the others are not asked again |
| index | the design index lists exactly the design IDs the other files name, with titles from the design, in order; it makes no model call; a set with no design IDs gets a plain note |
| decisions | the artefact has the right items; a blank Answer is open; "accept proposed" is an answer; a proposed answer alone is not; a person's edit keeps the structure or is refused |
| usage | an answered decision appears as settled in the foundation and not as a question anywhere; an open one is written by number; an ask-line naming no open DCN, or an unknown DCN, is sent back |
| order | the decisions are written before the instructions; the instructions wait for them; editing the decisions marks the set out of date and the banner offers to rewrite it |
| unchanged | 19a to 19c behaviour for a set with no decisions; every earlier phase; the kept generator's tests; `export_contract --check`; no test touches `backend/data` |
| break-one-thing | a mutants file per slice with the baseline guard; every survivor closed with a real test |

## Dependencies / installs
None.

## Manual check for the user
After 19d-1: `cd backend && python -m scripts.instructions_demo` (offline and free: a case where one file uses a wrong field name and is sent back alone, and the design index being written). After 19d-2: the same demo with a decisions case, then on the real project: run Build (a live run, more calls than before: the decisions plus the set), answer the decisions with Edit by hand, and rewrite from the banner. I will not start a live run.

## Done when
- [ ] Listed tests pass; full suites green (summary lines in PROGRESS.md)
- [ ] Break-one-thing check run with the baseline guard and reported honestly
- [ ] Manual-check list handed over
- [ ] PROGRESS.md and RESUME.md updated
- [ ] **You have run it live once, answered the decisions, and told me what you saw**
- [ ] User confirms
