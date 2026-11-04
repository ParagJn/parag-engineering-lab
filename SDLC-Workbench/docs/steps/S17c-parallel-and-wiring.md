# S17c · Parallel waves, isolation, and the Build phase in the runner

**Milestone:** M5  **Size:** M  **Objectives:** O6, O7  **Depends on:** S17a (files, writer, checks), S17b (the fix loop, the round record), S09 (the phase runner), S16 (the sandbox)
Plan test (`05-build-plan.md`, S17): *per-component isolation*, and the phase-level promises: *wave 1 runs in parallel, wave 2 waits for the backend, results come from real test execution*.

17a wrote a Build artefact's files and checked them. 17b ran the generated tests and fixed failures. Both are called from Python only. 17c makes **running the Build phase** do all of it: the runner starts the database, backend and frontend artefacts together, the test suite after the backend, and then the fix loop. It builds no screen and calls no model in its tests.

## What I found before writing this (it shapes the plan)
1. **Writing two Build artefacts at the same moment is broken today.** I ran three writers together (database, backend, frontend, the way wave 1 starts them), 25 times. Only **39 of 75** writes succeeded; the rest crashed with `FileNotFoundError`, `Directory not empty` and `File exists`. The cause is 17a's single shared staging folder `.stage`: each writer clears it and refills it, so they trample each other. 17a and 17b never wrote two at once, so no test could see it. **This is the main reason 17c exists as a slice,** and it is fixed first.
2. **The runner already does the scheduling.** It starts every artefact whose `after` list is finished (up to `run_max_concurrency`, default 3), counts money through one `Meter`, and handles failure by skipping whatever depended on it. The catalogue already says wave 1 is the database, backend and frontend, wave 2 is the test suite (after the backend), wave 3 is the test report and the review. So **no new scheduler is needed**; the Build artefacts only need to be written the Build way when the runner reaches them.
3. **Isolation is mostly already true.** Each artefact owns one folder (17a decision 3), and `replace_folder` swaps only that folder. What was missing is isolation of the *staging*, which is the bug above. Once staging is per-artefact, two writers share nothing.
4. **The runner's own per-artefact step is the right place to hook in.** It calls `runtime.run(...)` with an `on_call` hook for money. For the four code artefacts it should also pass the 17b `extra_check`, so a reply that does not compile is repaired in the same conversation. The other artefacts are untouched.
5. **The test suite can only be judged once the backend is saved,** which the `after` list already guarantees. The fix loop (17b-3) is run once, **after wave 2**, against the saved versions. It is not run inside each artefact: it needs both the backend and the tests.
6. **A reviewer (the S08 review) can read code artefacts** with the same rubric, since they are Markdown bodies. S18 owns the code-specific review and the quality gate, so 17c leaves review exactly as it is.
7. **The events screen has a fixed vocabulary** (`EVENT_TYPES`, pinned in the contract fixtures). The fix loop reports rounds with `build.round`. Adding it to the vocabulary changes `events.json` and the frontend test that pins the list; that is a small, deliberate change, not a surprise.

## Decisions (**the user said "all 10 defaults is good" on 2026-11-03, so all ten stand as written**)
1. **Fix the staging race first, by giving every write its own staging folder.** `.stage/<artefact key>-<random>/`, removed when that write ends (and a sweep of folders older than an hour at the start of a write, so a crash cannot leave them for ever). Two writers then share nothing. A regression test runs three writers together many times and needs **every** write to succeed. Default: this.
2. **No new scheduler.** The Build phase runs through the existing runner and its concurrency cap, its `Meter`, its failure and skip rules and its events. Default: yes.
3. **Code artefacts are written the Build way inside the runner.** For `database_schema`, `backend_code`, `frontend_code` and `test_suite`, the runner passes the 17b `extra_check` (write the reply's files, run the artefact's real check, send problems back in the same conversation). Every other artefact is written exactly as before. Default: yes.
4. **The fix loop runs once per phase run, after the test suite is saved,** through the same `Meter`, with `build_fix_rounds` (default 3). Its result is part of the run's result and its totals; its rounds are in `build_rounds` (17b-2). It is skipped, with the reason stated, if the backend or the test suite did not reach "done" (a failed artefact cannot be tested). Default: yes.
5. **What the loop's ending does to the run.** `converged` is a finished run. Every other ending (`cap_reached`, `not_converging`, `invalid`, `no_tests`, `blocked`, `stopped`) is reported **plainly in the run's result and events, and is not an error and not an approval**: the phase stays for a person to review, exactly as it does when a reviewer finds problems. A `stopped` ending (money, time or cancel) sets the run's stop reason as any stop does. Default: yes.
6. **One new event, `build.round`**, carrying the round number, who was asked, and the counts, never output or contents. It is added to `EVENT_TYPES`, so the contract fixtures and the frontend's pinned list are regenerated and checked. Default: yes.
7. **The workspace equals the latest saved versions at the end of the run** (the 17b rule), whatever the run's result, including a stop or a crash. Default: yes.
8. **Parallelism is proven, not assumed.** A test makes the three wave-1 artefacts take a measurable time each and shows the phase takes clearly less than their sum (`max_in_flight` is already recorded by the runner). Default: yes.
9. **The Build phase must be startable by the existing API with no new route.** `POST` run on phase `build` already exists; 17c adds no endpoint and no screen. A person approves the phase as for any other. Default: yes.
10. **No live model in any test.** Scripted replies only. The live run comes next, on the $5, only with your word. A mutation sweep with the baseline guard covers the new code, in batches of three run in the background. Default: yes.

Stated, not asked: the S18 report, the code and security review screens and the quality gate are not built here; a generated server is not started (S19); the frontend gets only the regenerated contract fixtures and the one pinned list, no new component.

## Build order inside 17c (each ends green, so stopping after any piece is safe)
| Piece | Delivers |
|---|---|
| **17c-1** | The staging fix: per-write staging folders and the old-folder sweep, with the three-writers-at-once regression test. Nothing else changes. |
| **17c-2** | The runner hook: code artefacts get the `extra_check`; the fix loop runs after the test suite; the `build.round` event and its fixtures; the run result and totals carry the loop's ending. |
| **17c-3** | The end-to-end tests of a whole Build phase with scripted replies (parallel proof, wave order, failure and skip, stop, the workspace rule), the demo and the sweep. |

## Out of scope (later)
- The test report artefact, the code and security review and the quality gate (S18); any screen for rounds or results (S18); starting a generated server and the smoke test (S19); the live run.

## Tests (must pass before 17c is done)
| Area | Proves |
|---|---|
| staging | three writers at once, repeated, never fail; each writer's staging folder is its own and is gone afterwards; an old leftover folder is swept and a young one is not; a refusal still leaves nothing behind |
| the hook | a code artefact run by the runner is repaired when its files do not compile, and only the repaired version is saved; a non-code artefact is unchanged and is never given the extra check |
| wave order | the database, backend and frontend start together; the test suite starts only after the backend is saved; the fix loop starts only after the test suite is saved |
| parallel | the phase takes clearly less time than the sum of its artefacts, and `max_in_flight` is 3 |
| failure | a failed backend skips the test suite and the loop, with the reason named; a failed frontend does not stop the backend, the tests or the loop |
| the loop in the run | a scripted developer is fixed in round 2 and the run finishes; a developer who never fixes it ends the loop as `cap_reached` and the run reports it plainly without raising; the loop's calls count against the run's money; a budget stop mid-loop stops the run with its reason |
| the event | `build.round` is published once per fix round with counts only; it is in the vocabulary; the contract fixtures and the frontend list are regenerated and agree |
| the workspace | after any ending, including a stop and an unexpected error, each folder holds its latest saved version |
| isolation | one component's failure leaves another component's saved files and folder untouched; two projects never see each other's files |
| unchanged | every earlier phase runs exactly as before; the full backend and frontend suites and `export_contract --check` pass; no test touches `backend/data` |
| break-one-thing | a mutants file for the staging, the hook, the order, the loop's place in the run and the event, with the baseline guard; every survivor closed with a real test |

## Dependencies / installs
None.

## Questions for the user
Decisions 1 to 10 each carry a default. The ones worth reading first: **1** (the race I found, and the fix), **4 and 5** (when the loop runs and what each ending does to the run: reported plainly, never an approval) and **6** (the one new event).

## Manual check for the user (we do not run the app)
From `backend/`: `python -m scripts.build_phase_demo` (offline and free: a whole Build phase with scripted developers, showing the parallel start, the wave order and a fix in round 2), then `python -m pytest tests/ -m sandbox -q`.

## Done when
- [ ] Listed tests pass; full suite and `npm test` green (summary lines in PROGRESS.md)
- [ ] Break-one-thing check run with the baseline guard and reported honestly
- [ ] Manual-check list handed over
- [ ] PROGRESS.md and RESUME.md updated
- [ ] **You have run it and told me what you saw**
- [ ] User confirms

## What was built in 17c-1, and what differed (2026-11-03)
The staging race is fixed. Three writers at the same moment, repeated, now all succeed (the regression test runs 12 rounds of three). Found by trying, and changed the code:
- **The shared staging folder was only the first of three races.** Per-write staging (`.stage/<artefact>-<random>/`) fixed the first. Running the new test then showed two more: (1) two writers making the SAME parent folder at once (`mkdir` failed with "File exists"), and (2) two replacements of the SAME artefact's folder at once, where one deleted the destination while the other filled it ("Directory not empty"). `replace_folder` now moves the old folder aside in one step and swaps in the new one, so each replacement swaps whole folders and the last swap wins, never a mixture.
- **A check must not disturb a component that is being written.** Collecting the tests used to put EVERY component back to its saved version first, including a frontend that another writer was in the middle of replacing. The test suite is judged against the backend and the database it creates its tables from, and nothing else (`TESTED_AGAINST`).
- **The shared `.stage` parent is removed when empty** (a new safe tool, `remove_empty_folder`, that cannot remove anything with content), so a finished write leaves no trace.
- **Stale staging is swept** at the start of a write, but only folders older than an hour: a write in progress is never touched.
- **Existing tests changed:** the 17a test that pinned the one shared staging folder now pins the new rules (swept when old, left alone when young, boundary on both sides).
