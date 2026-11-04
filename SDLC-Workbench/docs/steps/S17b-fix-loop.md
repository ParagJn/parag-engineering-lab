# S17b · The write → test → fix loop

**Milestone:** M5  **Size:** M  **Objectives:** O7  **Depends on:** S17a (files, writer, checks), S16 (sandbox and the pytest parser), S09 (the run's money and clock), S07 (agent runtime)
Plan test (`05-build-plan.md`, S17): *with scripted mock "developer" responses the fix loop converges; the iteration cap stops runaway; results come from real test execution.* Per-component isolation and parallel waves are 17c.

17a can write a Build artefact's files and check that they compile, create their tables, parse and collect. It cannot say whether the code **works**. 17b runs the generated tests for real, gives the real failures back to the developer agents, and stops at a cap. It builds no screen and calls no model in its tests.

## What I found before writing this (it shapes the plan)
1. **The runtime already repairs a reply inside one conversation.** It checks the reply, and if there are problems it sends them back (up to `agent_max_repairs`, default 2), then saves **only a valid version**. That is the cheapest place to fix a compile error or a schema typo: the model still has the whole conversation in view. So the 17a checks should run **inside** that loop, not after a version has been saved. This matches 17a decision 6 ("a failing check is a problem sent back to the model, the same repair loop").
2. **Real test failures are different.** They can only be known once the backend and the tests are both written, and the fix may belong to either artefact. That needs a second, outer loop, with its own cap, and each fix is a **new saved version** (versions are immutable), written the way a phase run writes a revision.
3. **Both loops write files before the version is saved.** A repair attempt has to be tried in the workspace to be checked, so the workspace can end up holding an attempt that was never saved. The workspace must always equal the **latest saved version** (17a said it is "written from" the body). 17b enforces that at the end of every loop, whatever the outcome.
4. **The real money cap already exists** (`run_max_cost_usd` $5.00, `run_max_seconds` 1800, the S09 `Meter`). The loop uses it, so a runaway cannot spend past it. The new cap is on *rounds*, so a loop also stops when it is not getting anywhere.
5. **`pytest` runs as `python -m pytest`** from the workspace root, so `backend.main` is importable without any `__init__.py` (checked in 17a's demo, where the generated test collected).

## Decisions (**the user said "yep, all defaults is good" on 2026-11-02, so all ten stand as written**)
1. **Two loops.** *Inner:* the 17a check for the artefact runs inside the runtime's existing repair loop (as an extra check on the reply), so a compile error, a schema that fails, a bad script or an uncollectable test file is sent back in the same conversation and **no bad version is saved**. It counts against the existing `agent_max_repairs`. *Outer:* after the files are written, the whole generated test suite is really run; failures go back as a **fix round**. Default: both.
2. **Fix rounds: 3.** One round is: run the tests; if they are not all green, one developer call (with its own inner repairs) for **one** artefact, saved as a new version; write its files; run the tests again. Setting `build_fix_rounds`, default 3, allowed 1 to 10. Worst case is 3 rounds × (1 call + 2 repairs) = 9 calls, so the cost of a stuck loop is known in advance. Default: 3.
3. **Who is asked to fix.** Errors in the tests themselves (a collection error, an import error, a broken fixture) go to the **test engineer**, because a broken test cannot say anything about the backend. Otherwise assertion failures go to the **backend developer**, because the skill tells the tests to assert what the *design* says, so a failing assertion means the code does not do it. When both kinds are present, the test errors are fixed first. One artefact per round. Default: this rule.
4. **What the model is told: real facts only.** The round number, the counts (passed, failed, errors, skipped), and up to **10** failures, each with its test id (which names its file), its kind and the first lines of its message (**400 characters** at most), already redacted by the sandbox. Never the whole output. The previous draft is included so the model improves it instead of rewriting it. Default: this.
5. **Stop conditions, each a distinct result, none an exception.**
   - `converged`: every test passed and at least one test ran;
   - `cap_reached`: still failing after the last round;
   - `not_converging`: the same set of failing tests two rounds running, so it stops one round early instead of spending the last one on a repeat;
   - `stopped`: the run's budget, time or a cancel (the S09 reasons);
   - `blocked`: the sandbox is unavailable or refuses to run, so nothing can be judged;
   - `no_tests`: nothing was collected, which is never reported as passing;
   - `invalid`: the model could not produce a valid reply even after its repairs.
   Default: these seven.
6. **Money.** Every model call goes through the S09 `Meter`, as a phase run does, so the $5 run cap and the 30-minute cap apply. The loop checks the cap before each round and after each call. Default: the existing caps.
7. **A permanent record of every round.** A new table `build_rounds` (schema step v7, append-only: no update, no delete, like `run_events`) with: project, run, artefact, round number, which artefact version was tested, outcome, counts, a fingerprint of the failing set, up to 10 failures (test id, kind, message ≤ 400 characters), seconds and time. **No file contents and no full output.** S18's report reads it. The audit log also gets one row per round with counts only. Default: this table.
8. **The workspace always equals the latest saved version.** At the end of every loop, whatever happened, each component's folder is rewritten from its latest saved version (or removed if it has none), so an attempt that was never saved cannot linger and be tested or deployed. Default: yes.
9. **Not green after the cap: nothing is approved for you.** The latest version stays, the result says plainly "N of M tests failing after R rounds", and the human gate and S18 decide. Default: yes.
10. **Tests use scripted replies only.** No live model in any test; the live run comes after 17c, on the $5, with your word. A mutation sweep with the baseline guard covers the new code. Default: yes.

Stated, not asked: one loop per project at a time (the workspace is shared; 17c adds parallelism across components); the loop is called from Python and is **not** wired into the phase runner until 17c; no screen; the inner hook is an optional argument that defaults to "none", so every existing phase behaves exactly as before, which the full suite proves.

## Build order inside 17b (each ends green, so stopping after any piece is safe)
| Piece | Delivers |
|---|---|
| **17b-1** | The optional extra check on the runtime's reply; the 17a checks wired in as that check; the workspace-equals-saved-version rule. Tests with scripted replies; mutants. |
| **17b-2** | Schema v7 `build_rounds` and its repository (append-only), with tests that no row can change. |
| **17b-3** | The outer loop: run the tests, route the failure, fix, stop conditions, the record, the demo, the sweep. |

## Out of scope (later)
- Parallel waves, per-component isolation and the runner wiring (17c); the test report and code and security review screens (S18); starting a generated server (S19); a screen for the rounds.

## Tests (must pass before 17b is done)
| Area | Proves |
|---|---|
| inner hook | a reply whose files fail the 17a check is sent back in the same conversation and only the repaired version is saved; with no hook, behaviour is exactly as before; a hook that never passes ends as `invalid` with nothing saved |
| workspace rule | after a loop that saved nothing, the folder is removed; after one that failed on its last attempt, it holds the previous saved version, not the failed attempt |
| routing | a collection or import error goes to the test engineer; an assertion failure to the backend developer; both present, tests first; never two artefacts in one round |
| what the model sees | counts, at most 10 failures, messages cut at 400 characters, no full output, no secret (a planted one is redacted) |
| converged | a scripted developer fixes the backend in round 2 and the loop ends `converged` with the real counts |
| cap | a developer that never fixes it stops at exactly `build_fix_rounds` rounds as `cap_reached` |
| not converging | the same failing set twice ends one round early as `not_converging` |
| stopped | a budget, a time limit and a cancel each end it as `stopped` with their reason, and no further call is made |
| blocked / no tests / invalid | each is its own result and none is reported as a pass |
| results are real | the counts come from really running the generated tests in the sandbox: a developer that *claims* success in its text but whose code fails is still `cap_reached` |
| record | one row per round; no row can be changed or deleted; no file contents or full output in a row or in the audit |
| unchanged | full backend and frontend suites and `export_contract --check` pass; no test touches `backend/data` |
| break-one-thing | a mutants file for the routing, the stop conditions, the fingerprint, the cap, the record and the workspace rule, with the baseline guard; every survivor closed with a real test |

## Dependencies / installs
None.

## Questions for the user
Decisions 1 to 10 each carry a default. The ones worth reading first: **1** (the 17a checks run inside the reply's own repair loop), **3** (who is asked to fix) and **8** (the workspace always equals the latest saved version).
One thing to know: this reads a different way from 17a's text in one place. 17a's spec said the checks use "the same repair loop"; they do, but the wiring is only done now, because it needs the small runtime hook above.

## Manual check for the user (we do not run the app)
From `backend/`: `python -m scripts.fix_loop_demo` (offline and free: a scripted developer that fixes a bug in round 2, one that never does, and one that repeats itself), then `python -m pytest tests/ -m sandbox -q`.

## Done when
- [ ] Listed tests pass; full suite and `npm test` green (summary lines in PROGRESS.md)
- [ ] Break-one-thing check run with the baseline guard and reported honestly
- [ ] Manual-check list handed over
- [ ] PROGRESS.md and RESUME.md updated
- [ ] **You have run it and told me what you saw**
- [ ] User confirms

## What was built, and what differed (2026-11-02 to 2026-11-03)
Built as specified, all ten decisions at their defaults. Found by trying, and changed the code or the claims:
- **"Rounds" means fixes.** The spec said 3 rounds is "3 x (1 call + 2 repairs) = 9 calls". The loop makes at most `build_fix_rounds` fixes and `build_fix_rounds + 1` runs of the tests, because the last run has to judge the last fix. Each run of the tests is one recorded round, and the final one records who was asked to fix nothing. So 3 fix rounds is up to 4 recorded rounds and still at most 9 model calls.
- **The first run of the tests is against what is SAVED.** Before round 1 the workspace is put back to the latest saved versions, so a leftover unsaved attempt cannot be judged.
- **`not_converging` needs a name to compare.** A run that timed out or crashed lists no failing test, so its fingerprint is empty; two empty fingerprints are not a repeat (a test pins this), and the loop goes on.
- **The same failing set is detected on the fingerprint of WHICH tests fail, not how many or why.** A developer who "fixes" a different test each time is making progress (until the cap); one who fails the same test twice is not.
- **A developer who claims success in words is not believed.** A test pins this: the claim is in the reply text, the code still fails, the loop does not converge.
- **A round is recorded for every ending**, including `blocked`, `no_tests`, `invalid`, `stopped` and `not_converging`, with counts and short failure lines only. A cancel before the first run records nothing, because nothing ran.
- **Not done, as stated:** parallel waves and per-component isolation, the runner wiring (17c); a screen for the rounds, and the report (S18); starting a generated server (S19). The loop is called from Python and is not yet reached from a phase run.

## Manual check for the user (17b)
From `backend/`: `python -m scripts.fix_loop_demo` (five stories: a fix in round 2, a developer who only claims success, a developer who never gets there, a broken test file going to the test engineer, a spent budget), then `python -m pytest tests/ -m sandbox -q`. Tell me whether 3 fix rounds feels right as the default.
