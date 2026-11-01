# S09 · Parallel execution and progress events

**Milestone:** M2  **Size:** M  **Objectives:** O6, O10  **Depends on:** S02, S05, S07, S08
Built and tested against the mock provider, so no real model is needed to write or test it. One real run is required before the step closes (see "Real-model check").

## Goal
After this step, a whole phase can be produced with **one call**: the artefacts run in the order the plan's waves give, the ones in the same wave **run at the same time**, a run can be **stopped by a budget or a time limit**, and everything that happens is published as a **stream of events** that a script (today) and the screen (S12) can follow live. This closes milestone M2: the engine runs a project's phases with gates, review, re-run and events.

Most of the machinery exists. The plan already computes the waves (S05), the runtime already produces one artefact safely (S07), the gateway already meters every call (S02), and the review service already reviews one artefact (S08). What is new is the scheduler that ties them together, the event stream, the budget and time caps, and the first HTTP endpoints.

## Two facts you should know before choosing

1. **Parallel helps some phases a lot and Requirements only a little.** Wave widths per phase today: Setup 1, Requirements 2-3-1-1, Design 1-1-1, Architecture 1-2-2, Build and Test 3-1-2, Deploy 1-3-1, BAU Handover 2-4. The Requirements dependency chain (personas, then functional requirements, then epics, then stories) is four deep, and from your real run's output sizes I estimate parallel running makes it about **1.3 times faster** (13,400 of 17,900 output tokens on the critical path), not three times. That is a limit of the plan, not of the code. The plan's test asks for "faster than serial with a delayed mock"; I will prove that on a wide fixture, and report the Requirements figure as measured, not as promised. Wide phases (Handover, Build and Test) gain more.
2. **Parallel runs share one SQLite database and one rate-limited service.** The database already handles concurrent writers safely (S01 and S07 tests), and the runtime's saves are single transactions, so concurrent artefacts cannot corrupt each other. The service is the real constraint: running 4 calls at once to one ICA endpoint may trip its own rate limits, and your S04 run showed very high latency. So concurrency is **capped by a setting**, not unlimited.

## Decisions I need from you (defaults chosen; say if you want any changed)

1. **Concurrency is capped, default 3 calls in flight.** Setting `RUN_MAX_CONCURRENCY` (1 to 8). With 1 the run is fully serial, which is a useful fallback if the service pushes back. 3 matches the widest wave in today's plan (4 in BAU Handover is queued, not dropped). Retry and fallback inside a call are unchanged.
2. **A run has a money budget and a time limit, both on by default and both stop the run cleanly.**
   - `RUN_MAX_COST_USD` default **2.00**. My measured whole Requirements phase cost $0.21, so this is roughly 10 times that: it should never trigger on a normal run and will stop a runaway. `0` switches it off.
   - `RUN_MAX_SECONDS` default **1800** (30 minutes) for the whole run. `0` switches it off.
   - **What "stop" means:** no new artefact is started once a cap is hit; artefacts already in flight are allowed to **finish and save** (cancelling a call mid-flight would waste money already spent, and a save that has begun cannot be interrupted safely: I tested it). The run then reports `stopped: budget` or `stopped: time` with exactly what finished and what did not. The cap is checked before each artefact starts and after each call, so a run can overshoot the budget by at most the artefacts in flight at that moment, and the report says by how much.
   - **Unknown prices:** a call with no price configured has an unknown cost, not zero (the rule since S02). The budget counts only known costs and the report says how many calls were unpriced, so a budget can't be silently defeated by a missing price. Alternative (refuse to start when a slot has no price) is stricter but would block any run before you have filled in a price; say if you want it.
3. **One failure stops its dependants, not its siblings.** If an artefact fails (invalid output after its repairs, a model outage, a refusal), everything that **needs it** is marked `skipped: blocked by <artefact>` and never started; everything **independent** carries on. Nothing is half-saved: a failure writes nothing for that artefact (S07 rule), and the others keep their versions. The run's result lists each artefact as `done`, `failed` (with the plain reason), `skipped` or `not_started`. The alternative, stopping the whole run at the first failure, wastes work that was fine.
4. **A run starts a phase if needed and leaves it running.** `run_phase` starts the phase if it is not started (checking prerequisites exactly as today) and **leaves it `running`** at the end. It does not hand the phase to review: you do that (or S12's button does). This keeps a half-failed run recoverable: you can re-run just the failed ones. Only artefacts that have **no version yet** are run by default; `only=[...]` runs the ones you name (new version each); `all=True` rewrites everything. Rewriting an artefact that other artefacts were built on marks them out of date, as in S08, and does not re-run them.
5. **One run per phase at a time.** A second `run_phase` for a phase that is already being run is **refused** with a plain message, not queued. It is checked inside the process, so it protects a single backend instance; a second backend process on the same database is not guarded (and `start.sh` runs one). Runs of different phases or projects do not block each other.
6. **Events: a durable log in the database, delivered over SSE.** Every event is written to a new `run_events` table (schema **v5**, one migration, nothing existing changes) and then published to anyone watching. Why a table: a screen that connects late, or reconnects after a drop, can say "give me everything after event 41" and miss nothing; the same log is the run's history for the observability screen later (S22). The stream is `GET /api/projects/{id}/events?after=<n>` using Server-Sent Events, with `Last-Event-ID` honoured, and a heartbeat comment every 15 seconds so proxies don't close it. Events carry **IDs, names, counts, costs and plain reasons only**; never prompt text, model replies, document text or a credential (tested).
7. **Event types, kept small:** `run.started`, `artefact.started`, `artefact.attempt` (a repair or a retry happened), `artefact.finished` (with tokens, cost, version), `artefact.failed`, `artefact.skipped`, `review.started`, `review.finished`, `run.stopped` (budget, time or cancelled), `run.finished` (with totals), plus `gate.changed` for phase moves and `heartbeat` (not stored). The vocabulary is fixed in one list and tested, so S12 can rely on it.
8. **Reviews can run as part of a phase run, off by default.** `run_phase(review=True)` reviews each artefact as soon as it is saved, concurrently with the next wave, using the S08 service. A reviewer that cannot run **pauses only that review** and the run carries on; the pause is an event and the person picks a family afterwards, as in S08. Off by default because it roughly doubles cost and time, and you may want to read an artefact before paying for a review. Reviews count against the same budget and time limit.
9. **First endpoints, deliberately few.** S09 adds the first routes because the stream has to be served: `POST /api/projects/{id}/phases/{key}/run` (starts a run and returns at once with a run ID; the work happens in the background), `POST /api/projects/{id}/runs/{run_id}/cancel`, `GET /api/projects/{id}/runs/{run_id}` (current state and totals), and the events stream above. Review, approve, reject and edit routes wait for S12, which is the first thing to use them. **Security stance, stated so you can veto it:** the backend listens on 127.0.0.1 only (as `start.sh` already does) and has no sign-in, so these routes can spend your ICA money for anyone who can reach that port; in this prototype that means you. I am not adding authentication in this step. Every route checks that the project exists, refuses unknown phases and artefact keys, and takes no free text that reaches a prompt.
10. **You run a real phase before the step closes.** `python -m scripts.run_demo --live` runs the **Requirements phase** for the sample project with real models, showing the events as they happen, prints how long it took against the sum of the individual calls (so you see the real speed-up, which I expect to be modest for this phase), and the real cost. About 8 to 10 calls, around 20 cents. Offline (the default) it runs a wide scripted fixture so you can see the parallel speed-up, the budget stop and a failure that skips only its dependants, clearly labelled as scripted. `--live --serial` runs the same phase with concurrency 1 for a like-for-like comparison.

## In scope
- **Scheduler** (`backend/app/run/`): `PhaseRunner.run_phase(...)` using the plan's waves; a bounded pool of concurrent artefacts; dependants of a failure skipped; budget and time caps; cancellation; one run per phase.
- **Events**: `run_events` table and repository (schema v5), an in-process publisher with a bounded queue per watcher, the SSE endpoint, replay from `after=`, heartbeat.
- **Run record**: a `runs` table row per run (project, phase, status, started, finished, totals, stop reason) so a run's outcome survives a restart. Also schema v5.
- **Endpoints**: the four listed in decision 9; request and response models with strict validation.
- **Settings**: `RUN_MAX_CONCURRENCY` (3), `RUN_MAX_COST_USD` (2.00), `RUN_MAX_SECONDS` (1800), `RUN_EVENT_QUEUE` (200), `RUN_HEARTBEAT_SECONDS` (15).
- **Status**: a `run` block on `/api/status` (limits and whether a run is active, counts only).
- `scripts/run_demo.py`.
- **Review inside a run** (decision 8) using the S08 service unchanged.

## Out of scope (later steps)
- The screen that shows any of this (S12). Review, approve, reject and edit **routes** (S12 adds them with the UI that uses them).
- Authentication and multi-user safety. Running more than one backend process.
- Secret and PII scanning (S10).
- Cost-by-phase and trace screens (S22); this step only records the data they will use.
- Resuming a run that was interrupted by a backend restart. A run that was `running` when the process died is marked `interrupted` on the next start and its finished artefacts stand; you start a new run for the rest. (Said plainly because it will happen during demos.)

## Design notes

**Scheduling.** The plan gives waves; a wave's artefacts depend only on earlier waves. Rather than "run wave 1, wait for all, run wave 2", the scheduler starts an artefact **as soon as everything it waits for has finished**, up to the concurrency cap. That is never slower than wave-by-wave and is faster when waves are uneven (for example, functional requirements need only personas and the problem, not vision). Order among ready artefacts is the catalogue order, so a run is repeatable.

**Why this is safe with the existing code.** `AgentRuntime.run` is already a single coroutine per artefact that does its database work in short transactions and saves in one transaction; S07 has tests running several artefacts together. The scheduler adds no shared mutable state of its own beyond a counter guarded by a lock. One thing to be careful of, and tested: two artefacts reading the same upstream while a third rewrites it; a run reads upstream versions at the time each artefact starts and records them in `built_on`, as it does today.

**Budget accounting.** Each finished call adds its cost to the run's running total as it completes (from the existing `LLMResult`), in one place, under a lock. The check happens before an artefact starts and after each call returns, so a repair loop that is burning money stops at the next call rather than finishing all its repairs. If a stop happens mid-artefact, that artefact is **not saved** (it is incomplete), is reported `not_started`-with-reason `stopped`, and the money already spent on it is counted. (Choosing between "finish the artefact being repaired" and "stop at once" is a real trade: I chose stop at once because a budget that can be exceeded by a full repair cycle is not much of a cap.)

**Time limit.** One deadline for the whole run, checked at the same points, plus `asyncio.timeout` around the wait for in-flight work so the run itself always ends. A call already in flight has the gateway's own per-call timeout (180 seconds).

**Cancellation.** `cancel` sets a flag; no new artefact starts; in-flight calls are allowed to finish and save, exactly like a cap. Cancelling is a request, not a kill, and the response says so.

**Event delivery.** `publish()` writes the row then puts the event on each watcher's queue. A watcher that falls behind (queue full) is **dropped with a `dropped` marker**, never allowed to slow or block the run, and reconnects with `after=<last id>` to catch up from the table. The run never waits for a watcher. Tested with a deliberately stalled watcher.

**SSE details.** `text/event-stream`, one event per message with `id:` and `event:` lines and a JSON `data:` line, `Cache-Control: no-cache`, and `X-Accel-Buffering: no`. The generator ends when the client disconnects (tested) and never holds a database connection while waiting.

**Schema v5** adds `runs` and `run_events`; both are append-mostly and carry `project_id`. Existing tables are untouched. The migration is covered by the same upgrade tests as v2 to v4 (data survives, concurrent first-start is safe).

**Where the code goes.** New: `app/run/` (`runner.py`, `events.py`, `budget.py`, `status.py`, `errors.py`), `app/routes.py` (a router, included by `main.py`), `scripts/run_demo.py`. Edited: `db.py` (v5), `repos.py` (the two new repositories), `config.py`, `main.py`. The runtime and review service are used as they are; the one change to them is an optional `on_call` hook so the runner can see each call's cost as it completes. It defaults to nothing, so existing behaviour and tests are unchanged.

## Tests (must pass before the step is done)

| Area | Proves |
|---|---|
| scheduling order | an artefact never starts before everything it waits for has finished; ready artefacts start in catalogue order; a wave of N with cap 3 never has more than 3 in flight (measured, not assumed) |
| parallel speed-up | on a wide fixture with delayed mock calls, the run takes about the longest path, clearly less than the sum, and with concurrency 1 takes about the sum |
| no corruption | concurrent artefacts each save exactly one version with the right ID; no duplicate artefacts; links and generation records are intact; repeated runs of the same fixture give the same result |
| failure isolation | a failed artefact saves nothing; its dependants are `skipped: blocked by ...` and never call the model; independent siblings finish and save; the result lists every artefact once with a plain reason |
| budget | a cost cap stops new work; in-flight work finishes and saves; the report says the amount over; a repair loop stops at the cap; unknown prices are counted as unpriced and never as zero; `0` switches it off |
| time limit | a deadline ends a run with `stopped: time`; the run itself always ends, even if a call hangs (the gateway's timeout is shortened in the test) |
| cancellation | cancelling stops new starts, lets in-flight finish, ends with `stopped: cancelled`; cancelling a finished or unknown run is refused plainly |
| one run per phase | a second run of the same phase is refused while the first is active; a different phase or project is not blocked; the guard is released after success, failure, cancel and an unexpected exception |
| run defaults | only artefacts with no version run by default; `only` runs named ones as new versions; `all` rewrites everything; an unknown or switched-off key is refused before anything starts |
| phase handling | the phase is started if needed with prerequisites enforced, and left `running`; a phase already approved is refused; nothing is handed to review automatically |
| review in a run | with `review=True` each artefact is reviewed after it is saved and findings are stored; a reviewer that cannot run pauses only that review (an event) and the run finishes; reviews count toward budget and time |
| events: content | every event type in the fixed vocabulary is produced in the right order for a normal run, a failure, a skip, a stop; events carry no prompt, reply, document text or credential (planted markers are absent) |
| events: durability | events are stored; `after=n` returns exactly the later ones; a late joiner sees the whole run; ids are strictly increasing per project; restart marks an unfinished run `interrupted` |
| events: delivery | a watcher receives events live in order; two watchers both receive everything; a stalled watcher is dropped with a marker and does not slow the run; `Last-Event-ID` resumes with no gap or repeat |
| SSE endpoint | correct headers and framing; heartbeat is sent when idle and is not stored; the stream ends when the client disconnects and releases its queue; an unknown project is a 404, not an empty stream |
| endpoints | run, cancel, status validate their input; unknown project, phase, artefact key and run ID give plain 404/422/409 messages; the run endpoint returns before the work finishes; nothing outside the listed routes was added |
| schema v5 | a v4 database with data upgrades and keeps its data; concurrent upgrades all succeed; existing immutability and audit triggers still hold |
| settings and status | defaults match this spec; out-of-range values are rejected; the `run` status block has counts only, no paths or secrets |
| script | `run_demo` offline prints the scripted phase, the speed-up, a budget stop and a skipped dependant, says it is scripted, exits 0; `--live` refuses without credentials and names which; never prints a key or the endpoint |
| unchanged | the whole existing suite passes; every changed existing test is listed in PROGRESS |
| break-one-thing | a mutants file for S09, run with the baseline guard (and the INVALID check from S08); every survivor is a test gap to fix, reported with the count and the spread |

## Dependencies / installs
None. Server-Sent Events are written directly with FastAPI's streaming response; I am deliberately not adding the `sse-starlette` package to the shared venv.

## Questions for the user
Decisions 1 to 10 above. The ones that most change the work: **2** (the default cap of $2.00 and 30 minutes, and what "stop" means), **3** (one failure skips only its dependants), **6** (a database log for events, which is the only reason for schema v5) and **9** (first routes, no authentication).

## Manual check for the user (we do not run the app)
1. `python -m scripts.run_demo`: runs a scripted wide phase and prints (a) the events as they arrive, (b) the time taken against the serial time, (c) a run stopped by a $ cap with the amount over, (d) a failure that skips only its dependants. A banner says it is a scripted fake model.
2. `python -m scripts.run_demo --live` (about 20 cents): the real Requirements phase with events printed live. **Compare the elapsed time with the sum of the call times it prints; I expect only a modest gain for this phase (about 1.3 times) and want to know what you actually see.**
3. Optional: `./start.sh`, then in another terminal `curl -N http://127.0.0.1:8090/api/projects/<id>/events` while `run_demo` or a POST to the run route is active, to see the raw stream. The page itself does not change; the schema pill reads v5.

## Done when
- [x] Listed tests pass; full suite green (1571 passed)
- [x] Break-one-thing check run with the baseline guard and reported honestly, including anything skipped or invalid (95 of 95 caught; the first run had 6 survivors and 2 inconclusive, all resolved)
- [x] Frontend `npm run build` still succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] **Real-model run of the Requirements phase by you and its result recorded** (2026-10-29: 7 of 7, $0.20364, 77.3 s, 1.48x; the `--serial` comparison was served too fast to be real calls and is not valid)
- [x] User confirms (2026-10-29), after the repair-reason change below

## Outcome
All ten decisions at their defaults. Changes from this spec: none to the design. After the real-model run, one addition at the user's request: the problems found in each failed attempt are stored in the version's `generation` record (`repair_reasons`) and on a stored review, so a repair can be diagnosed afterwards; they are never published in an event. The `--serial` comparison in `run_demo --live --serial` is not valid (it returned in 4.9 s for calls that took 77 s in parallel, most likely replies stored by ICA for identical prompts) and should not be used to measure speed-up.
