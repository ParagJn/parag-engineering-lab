# S19e · A second reader for the Build instruction set

**Milestone:** M5  **Size:** M, two slices  **Objectives:** O7 (reworded), O9, O3  **Depends on:** S19a to S19d-1 (closed or built: the set, the composer, the contract check, the design index) and S13's reviewer
**Status:** ANSWERED 2026-11-05: **all defaults** ("all defaults is good"). Written the same day, after the user saw the Build page and asked "does this stage require review?" and then "lets get on with review". Not built yet.
The numbering moves again: the decisions step stays **19d-2** and is built AFTER this; the acceptance tests as valid Python become **19f**; the gate and screen with the tool radio button and zip become **19g**.

## Goal
After this step "Review" on the Build phase works on the instruction set. A second model reads **each file** of the set against the design, the contract and the other files, and reports findings that name **the file and the line** they are about. The result is one review of the artefact, shown like every other review, so the person can see where to look before approving the phase.

## What I found before writing this (read from the user's real project and the code)
1. **The review fails on this artefact, and it is a size problem, not a model problem.** The reviewer was called twice on the Build instructions (2026-11-03 and 2026-11-04). Both calls ran about 62 to 64 seconds and ended with `finish_reason=length`, no text and 0 tokens recorded, on the reviewer's 8,000-token output limit. One review call has to read the artefact AND the upstream artefacts it was built on: here the set is 137,931 characters (about 34,000 tokens in) next to the largest artefact a review has read before, 19,345 characters. It is the same failure the first Build run had, for the same reason, and the same cure.
2. **The reviewer's limit is a single setting for every artefact** (`REVIEW_MAX_OUTPUT_TOKENS`, default 8,000). A per-file review needs small replies, not a bigger limit for everything. Raising the general limit would only hide the problem for other artefacts.
3. **The Build phase still lists two retired artefacts.** `database_schema` and `backend_code` were created by the user's first live run, before the code skills were retired. They have no skill, so "Review all" fails on them first with "there is no skill for ...", and the page shows them as failed. They are harmless but wrong: nothing is meant to be reviewed there. The versions stay in the database (nothing is deleted).
4. **A finding can only point at an item ID or a section heading.** In a set the useful pointer is a file, and often a line in it. The set already lists each file as an item (`INS-nnn`), so a file can be named by its item ID; a line cannot, today.
5. **The system already knows many things the reviewer would otherwise have to find by reading.** The contract check, the open-question lines, the coverage check and the "design item named by no file" list are plain code and cost nothing. A reviewer should be told their result, not asked to rediscover it, and should spend its tokens on judgement: is it right, is it invented, does it contradict, can an engineer build from it without guessing.
6. **The pieces to build on exist.** A review is stored on the version and shown on the page with the existing panel, colour marks and "stale after an edit" rule. The phase-level "Review all" already pauses only the artefact whose reviewer could not run. The independence label (writer family against reviewer family) and the family picker already exist. Reading files out of a saved set already exists (`split_set`), and the set already has the per-file checks.

## Decisions (each has a default; **the user said "all defaults" on 2026-11-05, so all ten stand as written**)
1. **Review the set file by file.** For the artefact `build_instructions` the review is NOT one call over the whole text. Each file is reviewed in its own small call, and the findings are joined into ONE review stored on the artefact version, as today. Default: yes, one call per file. (Every other artefact is reviewed exactly as it is now.)
2. **What a file-review call is shown:** that one file; the foundation (and the interface contract in it); the design index; the file list; the names of the other files, and the **design items the file names**, with the design's own text for each (read from the saved design, so the reviewer can check a claim against what the design really says). It is NOT shown the whole design (about 74,000 characters) in every call. Default: yes, the items the file names plus the foundation. Cost: about one call per file at roughly a third of the size of a writing call; not measured.
3. **A reviewer skill and rubric of its own for instruction files** (`review_build_instructions.md`, beside the existing rubric), asking five things: is every statement traceable to a design item that was shown; is anything invented (a name, a number, a rule, a screen); does this file contradict the foundation, the contract or another file; could an engineer build from it without guessing (is a decision hiding in it); does it keep to its kind (a use case file describes behaviour and not looks; a screen file describes in words and calls only what the contract lists). Default: these five. The general rubric stays for every other artefact.
4. **A finding names a file, and a line if it has one.** The target of a finding becomes the file's name (for example `UC-002-reserve-a-room.md`) with an optional line (`UC-002-reserve-a-room.md:41`), checked against the saved set: a finding about a file or a line that does not exist is sent back. The page shows it under that file. A finding about the set as a whole is `General`. Default: file and optional line.
5. **What the system already knows is given to the reviewer, not rediscovered.** Before each file-review call the system runs the checks it already has (contract drift, names, codes, routes, open-question lines, coverage gaps for that file) and puts the results in the call as "already found by the system", so the reviewer does not repeat them. The same results are ALSO listed in the review as findings marked "found by the system", at no model cost, so a person sees everything in one place. Default: yes.
6. **The reviewer role gets a bigger output limit than before.** A new setting `REVIEW_FILE_MAX_OUTPUT_TOKENS` (default 12,000) used only for a file-review call, because the reviewer spends part of its limit thinking before it writes (this is what emptied the earlier replies). The general `REVIEW_MAX_OUTPUT_TOKENS` is unchanged. Default: 12,000. If a call is still cut off, the failure message names the setting.
7. **All or nothing, like the writer.** If one file's review cannot be produced after the usual repair attempts, nothing is stored and the message names the file; the person can run the review again. If the reviewer cannot run at all, the existing family picker appears, once, for the whole set, not once per file. A run that is stopped (cost cap or cancel) stores nothing and says which files were done. Default: yes.
8. **Retired artefacts are skipped, not failed.** "Review all" skips an artefact that has no skill and says so in plain words ("retired: no longer part of this phase"); the page shows such an artefact as retired, not failed. Nothing is deleted. Default: yes. This is the small first slice.
9. **The review is a normal review on the page:** the verdict, the independence label, the findings list, colour marks on the file text where a line is named, the "stale" rule after an edit. The only new part is that a finding shows its file and line, and that findings from the system are labelled. Default: yes. The reviewer's colours (red, amber, blue by severity) stay.
10. **Order and what is left for later.** Built in two slices (below). Checking that the **decisions were followed** is added when the decisions step (19d-2) is built, as one more rule in the rubric and one more input to the call. A purpose-built review screen for sets is parked as D23. Default: as written.

Stated, not asked: the review is advice and never a gate; approval of the phase still does not depend on it. No model is called in any test (scripted replies, with one cut off). The cost of a review is shown on the page as for any review. An edit by a person to one file makes the review "stale" for the whole set, as it does now; reviewing only the files that changed is parked as D24. Every earlier phase and the closed slices stay as they are. The reviewer for every artefact except the Build set is untouched.

## Design notes
- **Where it goes.** `ReviewService.review` stays the entry point. For `build_instructions` it hands off to a `SetReviewer` (new, `app/build/review_set.py`) that splits the set, runs the system checks, builds one prompt per file, calls the existing gateway review path for each (so independence, fallback and the family picker work as now), merges the findings and stores one record through the existing `set_review_findings`. The prompt builder and the reply parser get a small variant that accepts a file target.
- **Targets.** The reply format stays `- [HIGH] <target>: problem. Fix: ...`. The target may now be `General`, a file name, or `file:line`. The validator takes the set's file list and each file's line count.
- **System findings.** Produced by the same functions the composer uses (`check_file`, `check_set`, the contract check, the open-question lines), each turned into a finding with severity (contract drift and invented IDs are high; an open question not marked is medium) and a `source: "system"` mark. The page labels them.
- **Retired artefacts.** `ReviewService.review_phase` skips an artefact whose type has no skill and reports it as skipped with a reason; the status endpoint reports it as `retired`; the page words it. Counts that move are pinned in tests and fixtures, regenerated after reading the diff.
- **Settings and config.** `REVIEW_FILE_MAX_OUTPUT_TOKENS` is added to `.env.example` and to the test isolation list. The frontend needs no setting.

## Slices
| Slice | Delivers |
|---|---|
| **19e-1** | Retired artefacts are skipped by "Review all" and shown as retired; the contract and the status route say so; the page words it. No model call. A small, useful change on its own. |
| **19e-2** | The set reviewer: the skill and rubric, the file-and-line targets, the per-file calls with the bigger limit, the system findings, the merge and the all-or-nothing store, the page showing a finding's file and line, the offline demo (a review of a small set with one drift found by the system, one by the reviewer, and one cut-off reply). |

## Out of scope
The decisions-followed rule (added in 19d-2); a purpose-built review screen (D23); reviewing only changed files (D24); auto-fixing a finding; a gate on approval; the acceptance tests as valid Python; the tool radio button and zip.

## Tests (must pass before each slice is done)
| Area | Proves |
|---|---|
| retired | an artefact with no skill is skipped by "Review all", reported as retired with a plain reason, never as failed; the others are still reviewed; a retired artefact opened directly says why it cannot be reviewed |
| split | the set is reviewed as one call per file, in the set's order; the design index and the file list are not reviewed as files; a set of one file works |
| prompt | each call carries the file, the foundation and its contract, the index and the design text of the items the file names, and NOT the whole design; the system's findings are in it; a hostile file cannot close the fence |
| targets | `General`, a file name and `file:line` are accepted; a file or a line that does not exist is sent back; a heading or an item ID is not a target for a set |
| system | each check the system has becomes a finding with the right severity and a `system` mark, once, without a model call; a clean file produces none |
| merge | findings from all files appear in one review, in file order then severity; the verdict is the worst severity; the summary names how many files were reviewed |
| limits | a file-review call uses `REVIEW_FILE_MAX_OUTPUT_TOKENS`; a cut-off reply names that setting; the general limit is unchanged for every other artefact |
| all-or-nothing | one file that cannot be reviewed stores nothing and names the file; a stop stores nothing and says what was done; a reviewer that cannot run gives the family picker once |
| page | a finding shows its file and line; a system finding is labelled; colour marks land on the right file and line; a review of an older version is not marked; every other artefact's review looks as before |
| unchanged | every other artefact is reviewed exactly as before (prompt, limit, targets); the composer, the contract check and the earlier slices; `export_contract --check`; no test touches `backend/data` |
| break-one-thing | a mutants file per slice with the baseline guard; every survivor closed with a real test |

## Dependencies / installs
None.

## Manual check for the user
After 19e-1: restart the backend; on the Build page "Review all" no longer shows the two red rows for `database_schema` and `backend_code`; they show as retired. After 19e-2: `cd backend && python -m scripts.set_review_demo` (offline and free), then on the real project press **Review** on the Build instructions: a real review, about one call per file (14 files plus the index not reviewed), roughly the cost of a third of a writing run. I will not start it.

## Done when
- [ ] Listed tests pass; full suites green (summary lines in PROGRESS.md)
- [ ] Break-one-thing check run with the baseline guard and reported honestly
- [ ] `npm run build` succeeds
- [ ] Manual-check list handed over
- [ ] PROGRESS.md and RESUME.md updated
- [ ] **You have run a real review on the Build instructions and told me what you saw**
- [ ] User confirms
