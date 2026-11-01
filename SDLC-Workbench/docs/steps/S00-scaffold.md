# S00 · Scaffold and test harness

**Milestone:** M1  **Size:** S  **Objectives:** O13 (and the base for O2/O10)  **Depends on:** nothing

## Goal
A backend that starts, loads its configuration safely from `.env`, answers `/api/health` and `/api/status`, with a pytest harness that is hermetic (never sees the real `.env`, real env vars or the network); a placeholder frontend that shows those two endpoints; and a `start.sh` that runs both. No LLM calls yet.

## In scope
- `backend/app/config.py`: `Settings` (pydantic-settings) with the four model slots, shared endpoint and key, run settings, and a `get_settings()` that is the only code that points at the real `.env`.
- `backend/app/main.py`: `create_app(settings=None)` factory with CORS, `GET /api/health`, `GET /api/status`.
- pytest harness: `pytest.ini`, `conftest.py` (hermetic environment), tests below.
- `backend/requirements.txt`, `backend/requirements-dev.txt`.
- Frontend placeholder (Vite + React + TypeScript, plain CSS): one page showing backend health, the REPLAY/LIVE mode, and a table of the four slots.
- `start.sh` (sibling pattern), project `.gitignore`.

## Out of scope (later steps)
- SQLite (S01), routing/metering/fallback logic (S02), the ICA client (S03).
- Vitest and the styling system (decided in S12 with the first real UI).
- Launcher card (S24).

## Design notes

**Config (`backend/app/config.py`)**
- Fields use the variable names already in `.env`:

  | Slot | model | fallback | price in | price out |
  |---|---|---|---|---|
  | sonnet | `IBM_ICA_MODEL_ID` | `IBM_ICA_FALLBACK_MODEL_ID` | `IBM_ICA_PRICE_INPUT_PER_MTOK` | `IBM_ICA_PRICE_OUTPUT_PER_MTOK` |
  | haiku | `IBM_ICA_HAIKU_MODEL_ID` | `IBM_ICA_HAIKU_FALLBACK_MODEL_ID` | `IBM_ICA_HAIKU_PRICE_INPUT_PER_MTOK` | `IBM_ICA_HAIKU_PRICE_OUTPUT_PER_MTOK` |
  | openai | `IBM_ICA_OPENAI_MODEL_ID` | `IBM_ICA_OPENAI_FALLBACK_MODEL_ID` | `IBM_ICA_OPENAI_PRICE_INPUT_PER_MTOK` | `IBM_ICA_OPENAI_PRICE_OUTPUT_PER_MTOK` |
  | gemini | `IBM_ICA_GEMINI_MODEL_ID` | `IBM_ICA_GEMINI_FALLBACK_MODEL_ID` | `IBM_ICA_GEMINI_PRICE_INPUT_PER_MTOK` | `IBM_ICA_GEMINI_PRICE_OUTPUT_PER_MTOK` |

  Plus `IBM_ICA_ENDPOINT`, `IBM_ICA_API_KEY` (`SecretStr`), `APP_MODE` (`replay` | `live`, default `replay`), `RUN_BUDGET_USD` (5.0), `LLM_TIMEOUT_SECONDS` (180).
- Prices are `float | None`. **A blank value in `.env` (as Gemini's is today) becomes `None`, not 0 and not an error.** A before-validator turns `""` into `None`, so this does not depend on a pydantic-settings option. Non-numeric or negative prices are rejected with the field name in the error.
- `Settings.slots` returns `{"sonnet": SlotConfig, ...}` (frozen dataclass: model_id, fallback_model_id, price_input, price_output). S02 builds routing on it.
- `get_settings()` is cached and calls `Settings(_env_file=<backend/.env>)`. The class itself has no `env_file`, so tests that build `Settings(_env_file=None)` or a temp file can never pick up the real one. `extra="ignore"` so unknown lines are harmless.
- Port lines (`BACKEND_PORT`, `FRONTEND_PORT`) come out of `.env` and `.env.example`: ports are fixed in `start.sh` and `vite.config.ts` only, so there is one source of truth. CORS origins are a constant default (`http://localhost:5270`, `http://127.0.0.1:5270`). I'll do this with a narrow edit, not a rewrite, so anything you've added to `.env` survives.

**App (`backend/app/main.py`)**
- `create_app(settings: Settings | None = None) -> FastAPI`. Importing the module has no side effects (no settings read). `start.sh` runs `uvicorn app.main:create_app --factory`.
- `GET /api/health` → `{"ok": true}`.
- `GET /api/status` → `mode`, `endpoint_set` (bool), `api_key_set` (bool), and per slot: `model_id`, `fallback_model_id`, `price_input`, `price_output`, `priced` (bool). **Never** returns the key or the endpoint URL. This is also what the placeholder UI shows, and it is how you can confirm your `.env` is wired correctly without anyone printing it.
- `/api/status` is a small addition beyond the plan's bare health endpoint. Reason: I can't run the app or read `.env`, so without it neither of us can see the config working.

**Harness**
- `backend/pytest.ini`: `testpaths = tests`, `pythonpath = .`, `addopts = -ra --strict-markers -m "not live"`, markers `live` and `sandbox`.
- `conftest.py`, autouse: removes every `IBM_ICA_*`, `APP_MODE`, `RUN_BUDGET_USD`, `LLM_TIMEOUT_SECONDS` variable from the environment, points `get_settings` at a nonexistent file, and clears its cache before and after each test. Fixtures: `make_settings(**overrides)` (builds `Settings(_env_file=None, ...)`) and `client` (TestClient around `create_app(make_settings(...))`). `anyio_backend` fixed to `asyncio`.
- Async tests use the anyio pytest plugin that comes with the `anyio` already in the venv, so no extra async plugin.

**Frontend (`frontend/`)**
- Vite + React + TypeScript, plain CSS, dependencies as `latest` with a lockfile, matching sibling apps. `vite.config.ts`: port 5270, `strictPort`, proxy `/api` → `http://localhost:8090`.
- `App.tsx` calls `/api/health` and `/api/status` and shows: backend OK/unreachable, a REPLAY or LIVE badge, endpoint/key "set / not set", and the slot table with prices (a missing price shows "unknown").

**`start.sh`**: copied from File Compare's pattern (venv at `/Users/paragjain/dev-works/myenv`, install deps if missing, free the ports, start both, Ctrl+C stops both, skips opening a browser when started by the Lab Launcher). Ports 8090 / 5270.

**Files created**
```
SDLC-Workbench/.gitignore  start.sh
backend/requirements.txt  requirements-dev.txt  pytest.ini
backend/app/__init__.py  config.py  main.py
backend/tests/conftest.py  test_config.py  test_health_status.py  test_harness.py
frontend/package.json  index.html  tsconfig.json  vite.config.ts
frontend/src/main.tsx  App.tsx  api.ts  index.css
```

## Tests (must pass before the step is done)

| Test | Proves |
|---|---|
| `config: defaults with no .env and a clean environment` | mode `replay`, budget 5.0, timeout 180, all slot IDs empty, key empty, all prices `None` |
| `config: reads a .env file` | a temp `.env` populates all four slots, endpoint and key |
| `config: sonnet uses the unprefixed variable names` | `IBM_ICA_MODEL_ID` → sonnet, `IBM_ICA_HAIKU_MODEL_ID` → haiku, no cross-talk between slots |
| `config: blank price is None` | `IBM_ICA_GEMINI_PRICE_INPUT_PER_MTOK=` in a file → `None`, the shape of your real `.env` today |
| `config: bad prices rejected` | `abc` and `-1` raise `ValidationError` naming the variable |
| `config: bad mode rejected` | `APP_MODE=foo` raises |
| `config: key never in output` | the key is absent from `repr`, `str`, `model_dump()` and `model_dump_json()` of Settings and every SlotConfig |
| `config: prices and slots round-trip as numbers` | `"2.00"` → `2.0`, shown in `slots["sonnet"]` |
| `health: returns ok` | `GET /api/health` → 200 `{"ok": true}` |
| `status: shape` | mode, `endpoint_set`, `api_key_set`, four slots with the documented fields |
| `status: no secrets` | with key `sk-TEST-SECRET` and endpoint `https://example.invalid`, neither string appears anywhere in the response body |
| `status: unpriced slot` | a slot with `None` prices has `priced: false` and null prices, not 0 |
| `status: mode follows config` | `replay` and `live` both reported |
| `cors: allowed and disallowed origin` | `http://localhost:5270` gets an allow header; `http://evil.example` does not |
| `app: import has no side effects` | importing `app.main` does not call `get_settings` |
| `harness: hermetic` | with a real-looking `IBM_ICA_API_KEY` set in the *outer* environment before the test, `get_settings()` inside the test still sees an empty key |
| `harness: async test runs` | an `@pytest.mark.anyio` test executes under the anyio plugin |
| `harness: live tests deselected` | a placeholder test marked `live` that would fail if it ever ran; it must show up as "deselected" in the summary |

## Dependencies / installs
- **Needs your OK, shared venv:** `pip install "pytest>=8"` into `/Users/paragjain/dev-works/myenv`. A dry run shows it adds only `pytest 9.1.1`, `pluggy 1.7.0`, `iniconfig 2.3.1` and upgrades or removes nothing. This is the only change to the venv.
- Already in the venv and used as-is: fastapi, uvicorn, starlette, pydantic, pydantic-settings, httpx, anyio, PyYAML.
- Frontend: `npm install` (react, react-dom, vite, @vitejs/plugin-react, typescript and type packages) into `SDLC-Workbench/frontend/node_modules`, which is gitignored.

## How I'll verify (without running the app)
1. `cd backend && /Users/paragjain/dev-works/myenv/bin/python -m pytest`, with the summary line pasted into PROGRESS.md.
2. `bash -n start.sh` (syntax only) and `chmod +x start.sh`.
3. `npm install` then `npm run build` in `frontend/` (typecheck and bundle; no dev server, no browser).
4. A scan that no file contains a key-like string or deck/client wording, and that `.env` is still ignored.

## Questions for the user
1. **OK to install pytest into the shared venv** (the three packages above)?
2. **OK to run `npm install` and `npm run build`** in `SDLC-Workbench/frontend`? It compiles only; no server and no browser. If you'd rather I skip it, the frontend stays unverified until your first `./start.sh`.
3. Anything to change about the choices above: removing the port lines from `.env`, adding `/api/status`, TypeScript with plain CSS for now?

## Manual check for the user (we do not run the app)
1. From `SDLC-Workbench/` run `./start.sh`. Both services should come up and the terminal should print `http://localhost:5270`.
2. Open `http://localhost:5270`. Expect: backend **OK**, a **REPLAY** badge, endpoint **set**, API key **not set** until you add it.
3. The slot table should list `claude-sonnet-5-5`, `claude-haiku-5-5`, `gpt-5.6-sol`, `gemini-3.7-flash`, each with fallback `claude-sonnet-5-5`; prices 2.00/10.00, 0.10/0.50, 4.00/20.00, and **unknown** for Gemini.
4. Optionally open `http://localhost:8090/api/status` and confirm no key or endpoint URL appears.
5. Ctrl+C should stop both and free ports 8090 and 5270.

## Done when
- [x] Listed tests pass; full suite green (`29 passed, 1 deselected`, in PROGRESS.md). The suite has more cases than the table above because the bad-price test is parametrised (`abc`, `-1`, `nan`, `inf`) and I added a few (zero price vs unknown, half-priced slot, `get_settings` caching, mode case tolerance, unknown `.env` lines ignored)
- [x] `bash -n start.sh` clean; frontend `npm run build` succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] Closed by the user on 2026-10-27 ("lets close S00"). The manual-check result itself was not reported back.
