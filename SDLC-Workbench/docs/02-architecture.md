# 02 · Architecture

## Shape

```
React UI (5270)  ──REST + SSE──▶  FastAPI backend (8090)
                                      │
        ┌─────────────┬───────────────┼────────────────┬──────────────┐
        ▼             ▼               ▼                ▼              ▼
   Workflow       Agent runtime   Context store    LLM gateway    Sandbox
   engine         (skills,        (ingest,         (routing,      (workspace dir,
   (phases,       tools, loop)    retrieve,        providers,     file + shell
   gates)                          re-ingest)      metering)      tools, test runner)
        └─────────────┴───────┬───────┴────────────────┴──────────────┘
                              ▼
              SQLite (projects, artefacts, versions, runs, traces, audit)
              + files on disk (artefact bodies, generated app workspace)
```

Connectors (document store, tracker, source control) are local stand-ins behind a `Connector` interface and are labelled **simulated** everywhere they appear.

## Components

| Component | Responsibility | Key rule |
|---|---|---|
| **Workflow engine** | Loads phase definitions from YAML. State machine per project and phase: `not_started → running → awaiting_review → approved \| rejected`. Runs a phase's artefacts in parallel. Enforces gates | Pure logic, no LLM calls inside, so it is fully unit-testable |
| **Agent runtime** | Runs one agent for one artefact: loads its skill (Markdown), assembles context, calls the gateway, validates output against a schema, retries on invalid output | Agents are *data* (skill + model role + output schema), not classes per agent |
| **LLM gateway** | One `complete()` interface. Resolves `agent role → slot (sonnet/haiku/openai/gemini) → model ID` from config. Meters tokens, latency, cost. Providers: `ica`, plus `mock` and `replay` | Agents never import a provider. Enforces the cross-family reviewer rule |
| **Context store** | Ingests documents and approved artefacts into chunks. Keyword retrieval (BM25) first; embeddings are an optional later upgrade. Returns chunks with source IDs for citations. Holds project memory (reviewer feedback) | Retrieval is deterministic, so tests are stable |
| **Sandbox** | Per-project workspace directory. Tools: read/write file, list, run command (allow-listed, timeout, no network), run tests | Generated code is executed here, never in the backend process |
| **Guardrails** | Secret and PII scanner over artefacts and code. Security gate before deploy | Deterministic regex/entropy checks first; an LLM pass is additive |
| **Observability** | Every gateway call writes a trace row (run, agent, model, tokens, latency, cost, status). Phase and model rollups | Cost uses per-slot prices from `.env`, labelled "estimate"; a blank price means "unknown", not zero |
| **Audit log** | Append-only record of who/what changed which artefact version and every gate decision | Never updated or deleted |

## Backend layout (`backend/app/`)

```
config.py            pydantic-settings, reads .env (never printed or logged)
main.py              FastAPI app, routers, SSE
db.py  models.py     SQLite via the standard sqlite3 module + small repository classes
llm/                 gateway.py  routing.py  metering.py  providers/{ica,mock,replay}.py
workflow/            definitions.py (YAML loader)  engine.py  gates.py
agents/              runtime.py  skills.py  tools.py  schemas.py
context/             ingest.py  chunk.py  retrieve.py  memory.py
sandbox/             workspace.py  runner.py
guardrails/          scan.py
trace/               traceability.py
connectors/          base.py  local_docs.py  local_tracker.py  local_repo.py   (all simulated)
phases/              definitions/*.yaml   skills/*.md   (the configurable part)
tests/               mirrors app/ layout; fixtures/replay/*.json
```

`frontend/` is React + Vite + TypeScript, as in sibling apps.

## Core data model

- **Project**: id, name, brief, selected phases/artefacts, routing overrides, context id, mode (`live | replay`).
- **PhaseRun**: project, phase key, status, started/finished, gate decision, decided_by.
- **Artefact**: stable id (e.g. `REQ-F-012`, `DES-UJ-001`, `ARC-HLD-001`), type, phase, title.
- **ArtefactVersion**: artefact, number, body, `author` (`agent:<role>@<model>` or `human:<name>`), source chunk IDs, review findings, created_at.
- **Link**: from artefact ID → to artefact ID, kind (`derives`, `implements`, `verifies`, `deploys`). This is the traceability graph.
- **Trace**: gateway call record. **Audit**: append-only event. **Memory**: reviewer feedback entries, scoped to project.

## Stable IDs and traceability

Every requirement, design element, component, code module, test and release item gets a stable ID in its artefact body. Agents are instructed to reference upstream IDs. A deterministic checker parses the references into `Link` rows and reports gaps (a functional requirement with no test, a component with no requirement). The LLM never "claims" coverage; the checker computes it.

## API sketch (grown step by step, not built at once)

```
POST /projects                     GET /projects/{id}
POST /projects/{id}/context/docs   GET  /projects/{id}/context/search?q=
POST /projects/{id}/phases/{key}/run
POST /projects/{id}/phases/{key}/decision      {approve|reject, feedback}
GET  /projects/{id}/artefacts      GET /artefacts/{id}/versions
PUT  /artefacts/{id}               (human edit → new version)
GET  /projects/{id}/traceability   GET /projects/{id}/cost   GET /projects/{id}/audit
GET  /projects/{id}/events         (SSE: progress, agent started/finished, gate changes)
POST /projects/{id}/incident       (simulated day-2 incident)
```

## Technology decisions

| Decision | Choice | Why |
|---|---|---|
| Orchestration | Own small asyncio engine + YAML definitions | A deep-agent framework adds an install to a shared venv and makes the state machine harder to test. Skills-as-Markdown plus a simple tool loop gives the same behaviour |
| Provider access | One ICA adapter over `httpx`, following the lab's existing ICA client. Slots (sonnet, haiku, openai, gemini) differ only by model ID and fallback; endpoint and key are shared | No SDK installs into the shared venv, and `httpx.MockTransport` makes the adapter unit-testable. A per-family request tweak (D6) is a small override in the adapter, not a new adapter |
| Persistence | SQLite + files | Matches sibling apps; zero setup |
| Retrieval | BM25 first | Deterministic and testable; embeddings add a provider dependency |
| Generated app stack | FastAPI + SQLite + plain HTML/JS frontend | Builds and tests in seconds without npm, so the Build & Test phase is reliable on stage |
| Streaming to UI | Server-sent events | One-way progress is all we need |
| Frontend tests | Vitest for logic only | UI is checked manually by the user |

## Decisions log and open questions

| ID | Question | Status |
|---|---|---|
| D1 | How do we reach the models? | **Decided: all four families through ICA**, one `.env` slot per family. See `07-model-config.md` |
| D2 | Model names and prices | **Decided:** user chooses IDs in `.env`; prices in `07-model-config.md` |
| D3 | Live keys | **Decided:** user fills them in later; replay mode until then |
| D4 | Generated app domain | **Decided:** Meeting Room Booking (`04-demo-scenario.md`) |
| D5 | Terraform / Docker locally | **Decided: not installed.** Those checks report "skipped, tool not installed" |
| D6 | Do OpenAI and Gemini behave the same as Claude on ICA's chat path? | **Decided (user): yes, ICA handles them the same way.** The first live call still confirms it, and a per-model quirk would be a small tweak in the one adapter |
