# S19f · Edit one file of the set, and review only what changed

**Milestone:** M5  **Size:** M, two slices  **Objectives:** O7 (reworded), O9, O3  **Depends on:** S19a to S19e (the set, the composer, the contract check, the per-file review)
**Status:** SPEC WRITTEN 2026-11-05 after the user ran the first real per-file review and said: "since this artefact is so long, it is almost impossible to edit it by hand and resolve all issues... allow the files to be edited independently", then chose "1 and 3" of the four ideas offered (edit one file; review only what changed). **ANSWERED 2026-11-05: all ten defaults ("all defaults is good"). 19f-1 is being built.**
**DECISION 2026-11-05 (after the user edited one file and saw the whole set reviewed again): "lets keep it as is because i can approve it anyways". Review stays as it is (the whole set, advice only, never a gate). 19f-2 (per-file standing, partial review, Review N files, a per-file Review button) is PARKED, not built. Edit one file (19f-1) stays and is finished.**
Renumbering: the acceptance tests as valid Python become **19g**; the gate and screen with the tool radio button and zip become **19h**. The decisions step stays **19d-2**.

## Goal
After this step a person can open **one file** of the Build instruction set, change it in an edit box that holds only that file, and save it. The rest of the set is untouched. The review then covers what changed: **only the edited file is reviewed again**, and the findings about the other files stay.

## What I found before writing this (read from the user's real project and the code)
1. **The real review is big, and it all sits on one artefact.** The first per-file review of the user's set (version 2) ran 14 calls for $0.77 with no empty replies and no corrections, and found **117 findings** (18 high, 59 medium, 40 low) across all 14 files, each with a suggested fix. To act on any of them today a person edits the whole 138,000-character set in one box.
2. **An edit is a whole-set save.** `HumanActions.edit` takes the full text, runs the artefact's checks and saves a new version. For a set that means one new version for a one-line change, and every file's review becomes "out of date" at once, because a review is tied to a version number.
3. **The pieces to splice a file in already exist.** `split_set` cuts a saved set into files; `assemble` joins them back with the same item numbers, the system-written design index and the coverage check; `check_file` checks one file against its kind, the design and the interface contract. A single-file edit is "split, replace one file, assemble, check, save".
4. **A review already says which version and which files it read.** The stored review records `version_reviewed` and the files it covered. The text of every file at that version is in the database. So "has this file changed since it was reviewed?" can be answered by comparing a file's text with the same file in the version that was reviewed. **No new storage is needed, and it works on the real review that already exists.**
5. **Most of the 59 medium findings are of one kind:** "this is not in the design" about choices the foundation says it is making (Python, FastAPI, SQLite). Those belong to the decisions step (19d-2) and are not part of this slice. This slice makes the list workable; it does not shrink it.
6. **What must not happen.** An edit that breaks the interface contract, invents a design ID, drops a required section or leaves a secret must be refused for the edited file, as it would be for a writer. And an edit must not be refused because of a problem in another file that was already there.

## Decisions (each has a default; say "all defaults" or change any)
1. **Edit one file at a time.** Each file's fold gets an **Edit this file** button that opens the same edit box, holding only that file's text. The set stays ONE artefact; a save is a new version of the whole set (the version list shows "edited by <name>" and the note). Default: yes.
2. **What an edit may change:** the text of a file that is already in the set. It may NOT rename a file, add a file or remove one (a rewrite does that; the set's file list and numbers are the system's). Default: text only.
3. **What an edit is checked against:** the file's own checks (its kind's sections and order, the size limit, no secret, no leftover placeholder, only design IDs that exist, the interface contract for names, codes and routes) **plus the set-level problems the edit INTRODUCES**. A problem that was already in another file before the edit does not block it. A file that is the foundation is also checked that its contract still lists every endpoint. Default: the edited file's problems and the newly introduced set-level ones.
4. **What the system rebuilds after a save:** the design index (it lists the IDs the files name), the file list, the coverage check and the item numbers of the files (unchanged). The model is not called. Default: yes, all by `assemble`.
5. **Two people, or two tabs.** The edit says which version it was made on; if the set has changed since, the save is refused with a plain sentence and the person reloads. Default: refuse on a changed base.
6. **A file's review is current only if the file is unchanged since it was reviewed.** Compared with the same file in the reviewed version. Editing the **foundation** makes every file's review out of date, because every file was read against it; editing any other file affects only that file. Default: yes, with that one exception.
7. **Review only what changed.** "Review" on a set whose last review is partly current reviews only the files whose review is out of date or missing (or all of them, if the foundation changed), keeps the findings of the files that are current, and joins both into ONE review of the new version. The page says before it runs how many files it will read and roughly what that costs. A separate **Review every file again** button does the whole set. Default: only what changed, with the explicit full button.
8. **What happens to the old findings of an edited file:** they are about text that no longer exists, so they are not carried forward; they stay on the older version's review, which can still be opened. The edited file shows "not reviewed since you edited it". Default: dropped from the new review, kept on the old version.
9. **The whole-set edit stays,** under a smaller "Edit the whole set" link, for the rare case; it is no longer the main way. It keeps all its checks. Default: keep.
10. **Out of scope and parked:** marking a finding done or ignored (D25); applying a suggested fix with one click (D26); asking a model to rewrite one file from its findings (D27); showing the edit as a before/after difference (D28). The decisions step (19d-2) is next after this. Default: as written.

Stated, not asked: editing a file never calls a model and costs nothing; only the later review does. The edit is recorded in the audit trail with the person's name, like any edit. The phase must be running or awaiting review, as for any edit. Approval of the phase still does not depend on the review. A set written before S19d (no contract) is edited under the checks that apply to it. No test calls a model. Every other artefact is edited and reviewed exactly as before.

## Design notes
- **Where it goes.** A new method `HumanActions.edit_file(project_id, artefact_id, file_name, text, based_on, actor, note)`: split the latest set, replace the file, `assemble` (keeping every file's item number and rebuilding the design index), run `check_instructions` before and after, refuse on the edited file's problems and on set-level problems that appear only after, then save through the existing `add_version` path with the same generation record fields as `edit`, plus `"edited_file": name`. New route `PUT /api/projects/{id}/artefacts/{aid}/files/{name}` with the file text, the base version and the note.
- **A file's review standing** is computed by `ReviewService.file_standing(project_id, artefact_id)`: for the latest review, the files it covered and, for each file, whether its text equals that file in the version that was reviewed. Returned with the review state so the page does not work it out.
- **Partial review.** `_review_set` takes the list of files to read (default all). It keeps the findings of the files not read from the latest review, drops findings for any file that is no longer in the set, and stores one record whose `files` list says, for each file, whether it was read now or carried (and from which version). The verdict is recomputed from all findings. The summary says "3 files read now, 11 kept from version 2".
- **Page.** The edit box is the existing `EditArtefact` component with the file's name as its title. Each file's fold shows its review standing next to the finding count ("reviewed", "out of date", "not reviewed since your edit"). The Review button for a set shows "Review 3 files" when only some need it. Nothing on any other artefact changes.
- **Counts that move:** the status and review-state payloads gain a `files` list for a set (absent for every other artefact); the contract fixtures are regenerated after reading the diff.

## Slices
| Slice | Delivers |
|---|---|
| **19f-1** | Edit one file: the splice, the checks (the file's own plus newly introduced set-level ones), the base-version rule, the route, the edit box for one file, the audit and version note. No review change. |
| **19f-2** | A file's review standing, the partial review (carry the findings of unchanged files, read the rest), the "Review N files" button, the "Review every file again" button, the offline demo. |

## Out of scope
D25 to D28 above; renaming, adding or removing a file by hand; editing the design index (the system writes it); changing what the reviewer is asked; the decisions step; the acceptance tests as valid Python; the gate.

## Tests (must pass before each slice is done)
| Area | Proves |
|---|---|
| splice | an edited file is replaced in the set and no other file changes by a character; the item numbers of all files are kept; the design index and file list are rebuilt; the version is one higher and carries the edited file's name and the note |
| refusals | an edit that drops a section, names an unknown design ID, breaks the contract (name, code, route), leaves a secret or a placeholder, or exceeds the size is refused with the reasons and saves nothing; the text typed is not lost |
| scope | a problem already present in ANOTHER file does not block an edit; a set-level problem the edit introduces (a use case losing its own ID in Derives from) does; the foundation losing an endpoint from its contract is refused |
| shape | an edit that changes a file's name, or adds a second `=== FILE:` line, is refused; a file that is not in the set is a 404 |
| base | an edit made on an older version is refused with a plain sentence and saves nothing; two edits in a row on the latest each succeed |
| phase | an edit while the phase is approved or not started is refused; a person is required (an agent or the system may not edit) |
| standing | after an edit the edited file is out of date and the others are current; after a foundation edit every file is out of date; a file that is edited and then changed back is current again |
| partial review | only the out-of-date files are sent to the reviewer; the findings of the current files are kept unchanged; findings for a file no longer in the set are dropped; the verdict and summary are recomputed; the record says which files were read now and which were carried |
| full review | the explicit button reads every file and replaces all findings |
| cost shown | the page says how many files a review will read before it runs |
| page | an Edit button in each fold; the box holds only that file; a refusal shows every reason and keeps the text; each file shows its standing; Review says "Review 3 files" when only some need it |
| unchanged | every other artefact is edited, reviewed and shown exactly as before; the whole-set edit still works; the composer, the contract check and the earlier slices; `export_contract --check`; no test touches `backend/data` |
| break-one-thing | a mutants file per slice with the baseline guard; every survivor closed with a real test |

## Dependencies / installs
None.

## Manual check for the user
After 19f-1: restart the backend; open a file's fold on the Build instructions, press **Edit this file**, change a line and save; check the version list says you edited it; try to break the contract on purpose (rename a field) and see the file refused with the reason. After 19f-2: edit a file, press Review, and see that it offers to read one file, not fourteen; run it (a real, cheap review: one call). I will not start a review on your project.

## Done when
- [ ] Listed tests pass; full suites green (summary lines in PROGRESS.md)
- [ ] Break-one-thing check run with the baseline guard and reported honestly
- [ ] `npm run build` succeeds
- [ ] Manual-check list handed over
- [ ] PROGRESS.md and RESUME.md updated
- [ ] **You have edited a real file, reviewed only that file, and told me what you saw**
- [ ] User confirms
