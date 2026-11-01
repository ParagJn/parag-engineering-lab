# 06 · Testing strategy

## Rules

1. **Unit tests never touch the network or a real model.** The ICA adapter is tested with `httpx.MockTransport`; everything above the gateway uses the mock or replay provider.
2. **Every step has a "Tests" list** in its spec. The step is not done until those exist and pass **and** the whole suite is green.
3. **Test the behaviour we promise in the objectives**, not just helpers: cross-family review, gate enforcement, targeted re-run, cost maths, sandbox containment.
4. **Execution beats claims.** Anything about generated code (builds, passes tests, responds) is checked by running it in the sandbox, never by asking a model.
5. **Deterministic by construction.** Fixed clocks and ID generators injected where used; BM25 retrieval; no sleeps for ordering (use events).
6. **Report real output.** At the end of a step we paste the pytest summary line. A red or skipped test is reported, not hidden.

## Layers

| Layer | Tool | Scope | Runs |
|---|---|---|---|
| Unit | `pytest` | Pure logic: routing, cost, state machine, chunking, retrieval, schema validation, scanners, parsers | Every step |
| Adapter | `pytest` + `httpx.MockTransport` | ICA request/response shapes, slot-to-model resolution and error mapping | S03+ |
| Component | `pytest` + FastAPI `TestClient` | API endpoints with an in-memory/temp SQLite and mock provider | From S00 |
| Sandbox | `pytest` | Real subprocess execution inside a temp workspace: containment, timeouts, test-output parsing | S16+ |
| Scenario | `pytest` | Whole phases on mock/replay data, including gates, review, rerun, parallelism | M2+ |
| Frontend logic | `vitest` | Reducers, wizard validation, selectors. Not rendering | S12+ |
| Replay end-to-end | `pytest` | Full seven-phase run from the replay set, offline | S24 |
| Live smoke | `scripts/live_check.py` (a script run by the user, not pytest: the test harness deliberately hides the real `.env`) | One short real call per slot and one real artefact. **Opt-in only**, needs keys, costs money | Manually |
| Manual | the user | Browser walk-through from each step's check list | End of each step |

## Mechanics

- Layout: `backend/tests/` mirrors `backend/app/`. Shared fixtures in `conftest.py`: temp DB, temp workspace, mock gateway, frozen clock.
- Async tests use the `anyio` pytest plugin that ships with Starlette's dependencies, so S00 only needs to add `pytest` to the shared venv. If that proves insufficient, S00's spec will say so and ask before adding anything else.
- Markers: `live` (excluded by default via `addopts = -m "not live"`), `sandbox` (real subprocesses).
- Replay fixtures live in `backend/tests/fixtures/replay/` and are small. Recorded outputs are scrubbed of anything sensitive before commit.
- Coverage is not a target. The test list per step is.

## Definition of done (every step)

- [ ] Step spec existed and the user approved it before coding
- [ ] Tests in the spec written and passing
- [ ] Whole suite green; summary line captured in `docs/PROGRESS.md`
- [ ] Nothing run in the browser by us; manual-check list handed over
- [ ] Anything simulated is labelled
- [ ] No secrets, client names or source-deck material added
- [ ] `docs/PROGRESS.md` updated
