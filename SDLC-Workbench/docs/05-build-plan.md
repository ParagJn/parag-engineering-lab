# 05 · Build plan

Principles: thin vertical slices, backend logic first, the UI grows alongside it so there is always something to look at, and nothing starts until the previous step's tests are green and the user says go. Each step ends with a manual-check list for the user (we never run the app ourselves).

Step specs live in `docs/steps/Sxx-name.md` and are written just before each step starts, from `_TEMPLATE.md`.

Size: S ≈ under an hour of work, M ≈ a session, L ≈ a long session. Objectives (O1–O13) are in `01-objectives.md`.

## Milestone M1 · Foundations (no LLM yet)

| Step | Deliverable | Size | Objectives | Tests (unit, offline) |
|---|---|---|---|---|
| **S00** | Project scaffold: folders, `config.py`, `.env.example`, `start.sh`, pytest set up, health endpoint, frontend placeholder | S | O13 | App imports; `/health` returns ok via TestClient; config loads defaults with no `.env`; secrets never appear in `repr(settings)` |
| **S01** | SQLite layer and repositories: projects, phase runs, artefacts, versions, links, traces, audit, memory. Append-only audit | M | O8, O13 | CRUD per repo on a temp DB; version numbers increment; audit rows cannot be updated or deleted; foreign-key integrity |
| **S02** | LLM gateway core: async `complete()`, role→slot routing from `routing.yaml` with project overrides, metering and cost by served model, retry/timeout/fallback policy, per-attempt traces (schema v2), **cross-family reviewer rule**, mock provider, `gateway` block in `/api/status`. Full detail in `docs/steps/S02-gateway-core.md` | M | O2, O3, O10 | Routing resolves per role; reviewer-family violation raises at startup; cost maths from the `.env` prices; blank price → cost "unknown" (never 0) and counted as unpriced in rollups; a fallback call is priced at the model that served it; fallback fires on injected failure; a reviewer call that falls back into the author's family is flagged "same family (fallback)"; every call writes a trace |
| **S03** | ICA provider adapter over `httpx`, following the lab's existing ICA client. Four slots (sonnet, haiku, openai, gemini) sharing one endpoint and key, each with a model ID and fallback model | S | O2 | Request shape and response parsing using `httpx.MockTransport` payloads; slot resolves to the right model ID; error mapping (401, 429, 5xx, content filter); blank slot → fallback, blank fallback → clear error; key never in logs |
| **S04** | Record and replay provider: successful live replies saved one file each, keyed by a hash of (model, prompt, limits) and not by project or run id, then served offline; strict misses; optional pacing; round-trip script. Full detail in `docs/steps/S04-record-replay.md` | S–M | O12, O13, O10 | Round trip record→replay; a miss raises a clear error and never falls back; key stable and unchanged by project/run ids; secrets never written; concurrent saves safe |

**M1 exit:** gateway callable from a script with mock/replay; all tests green. *User check:* run a one-line script (provided) that makes one live call per slot (sonnet, haiku, openai, gemini) and prints model, tokens, cost. This is the first point we need real keys filled in `backend/.env`, and it settles open question D6 (whether OpenAI and Gemini need request tweaks on ICA).

## Milestone M2 · Workflow and context

| Step | Deliverable | Size | Objectives | Tests |
|---|---|---|---|---|
| **S05** | Phase definitions (one YAML file per phase, strictly validated) and the workflow engine: legal-transition state machine enforced in the repo, prerequisite and gate checks, project plan from the wizard's selection, parallel "waves" of artefacts. Full detail in `docs/steps/S05-workflow-engine.md` | M | O1, O6, O11 | Valid and invalid YAML; legal and illegal transitions; cannot start phase N+1 before N is approved; disabling an artefact removes it from the plan and changes the waves; concurrent start of one phase has exactly one winner |
| **S06** | Context store: SQLite FTS5 (BM25 with stemming) search over chunked documents (txt, md, docx, pdf), approved artefacts (current version only) and project memory, with citable source IDs and strict per-project isolation. Full detail in `docs/steps/S06-context-store.md` | M | O4, O5 | Chunk boundaries; retrieval ranks the known-relevant chunk first on a fixture corpus; re-ingested artefact becomes retrievable; memory scoped per project |
| **S07** | Agent runtime: skill files (Markdown, linted), prompt assembly that puts retrieved context in a labelled untrusted block with citable source IDs, a structured reply checked for shape and for citations that really exist, bounded retry with the error fed back, and saving an artefact version. Full detail in `docs/steps/S07-agent-runtime.md` | L | O2, O4, O11 | Skill linter catches missing sections; prompt contains retrieved chunk IDs inside an untrusted-data block; an invented citation is rejected; invalid output retried then failed with a reason; saved version records author, citations, tokens, cost |
| **S08** | Reviewer and human-in-the-loop: Sonnet review with independence label, stored as findings, and the "choose another family" picker when the reviewer is unavailable; approve / reject-with-feedback / human edit; targeted re-run; feedback to memory | M | O3, O5, O8 | Every review is labelled independent or same family (never hidden); rejection re-runs only affected artefacts and includes the feedback; edit creates a `human:` version; audit entries written |
| **S09** | Parallel execution and progress events: run a phase's artefacts concurrently, SSE stream, budget and timeout caps | M | O6, O10 | Concurrent run is faster than serial with a delayed mock; one failure doesn't corrupt others; budget cap stops the run; event order |

**M2 exit:** engine runs a fake two-phase project on mock models, with gates, review, rerun and events. *User check:* call the API with curl/script (provided) and read the event stream.

## Milestone M3 · Requirements, vertical slice with UI

| Step | Deliverable | Size | Objectives | Tests |
|---|---|---|---|---|
| **S10** | Guardrails: secret and PII scanner, wired into artefact save | S | O9 | Planted fake secrets/PII found; clean text passes; findings attach to the version; false-positive fixtures |
| **S11** | Requirements phase: skills + schemas for personas, problem statements, vision, FR/NFR, epics/features, backlog splitter; stable IDs | M | O1, O2, O8 | Replay fixtures produce schema-valid artefacts; IDs unique and well formed; derived-from references parse |
| **S12** | UI slice: app shell, new-project wizard (5 steps, simulated connectors badged), context upload/search, phase view with artefact cards, review findings, approve/reject/edit, live progress | L | O1, O5, O11, O12 | Vitest for state/reducer logic and the wizard validation; backend contract tests for each endpoint the UI uses |

S12 is built in three slices, in order, with nothing dropped (decided 2026-10-29, see `docs/steps/S12-ui-slice.md`): **S12a** shell, project list, the five-step wizard and the project overview; **S12b** documents and search, the phase view with artefact cards, versions, running a phase with live progress; **S12c** review findings with the independence label and family picker, request changes, re-run, edit and approve. Each ends in something that can be opened and has its own tests, mutation check and sign-off.

**M3 exit:** first demoable moment: brief → requirements → review → human gate → approved, in the browser. *User check:* walk through the first four rows of the run of show.

## Milestone M4 · Design and architecture

| Step | Deliverable | Size | Objectives | Tests |
|---|---|---|---|---|
| **S13** | Design phase: user journey, low-fi and hi-fi wireframes (rendered as sanitised HTML/SVG); UI viewer | M | O1, O2 | Schema checks; HTML sanitiser strips scripts/handlers; each journey step references a requirement ID |
| **S14** | Architecture phase: component overview, flow diagram, use-case diagram, HLD, LLD; diagram rendering in UI | M | O1, O8 | Mermaid/SVG output validates; every component cites ≥1 requirement ID; LLD lists endpoints and tables that Build must honour |
| **S15** | Traceability: link extraction from IDs, matrix and gap report, UI view | M | O8 | Links parsed correctly; gap detector flags an uncovered requirement; orphan detection |

## Milestone M5 · Build and test (the real-output core)

| Step | Deliverable | Size | Objectives | Tests |
|---|---|---|---|---|
| **S16** | Sandbox: per-project workspace, file tools, allow-listed command runner with timeout and no network, test runner that parses pytest output | M | O7, O9 | Path traversal blocked; disallowed command refused; timeout kills the process; pytest output parsed into pass/fail counts |
| **S17** | Build agents: database, backend, frontend, tests, with a bounded write → test → fix loop and parallel execution | L | O6, O7 | With scripted mock "developer" responses: fix loop converges; iteration cap stops runaway; results come from real test execution; per-component isolation |
| **S18** | Code review and security review (Sonnet, with the independence label), results and test report in UI; quality gate | M | O3, O7, O9 | Gate blocks on failing tests or high-severity finding; passes when clean |

## Milestone M6 · Deploy and BAU

| Step | Deliverable | Size | Objectives | Tests |
|---|---|---|---|---|
| **S19** | Deploy phase: DevOps agent produces Dockerfile, compose, Terraform, pipeline; local run + smoke test; cloud apply as labelled dry-run; security gate; release notes | L | O7, O9, O12 | Planted secret blocks deploy; smoke test hits the generated app (started in-process or subprocess); Docker and Terraform are not installed on the demo machine, so those checks report "skipped, tool not installed" (never "passed") and the IaC gets static checks only; dry-run is labelled |
| **S20** | BAU handover: runbook, SLOs/alerts, KT pack, support guide, hypercare plan, sign-off gate | M | O1 | Handover pack references real endpoints/components from the approved architecture; sign-off required to complete project |
| **S21** | Day-2 incident loop: simulate an incident, triage agent, fix through a mini lifecycle with regression test, link back into traceability | M | O1, O8 | Incident creates linked change; regression test added and run; audit trail complete |

## Milestone M7 · Demo readiness

| Step | Deliverable | Size | Objectives | Tests |
|---|---|---|---|---|
| **S22** | Observability UI: cost by phase/model, trace inspector, audit viewer, REPLAY/LIVE banner | M | O10, O12 | Rollups match the sum of traces; banner reflects mode |
| **S23** | Demo kit: seeded project, one-click reset, phase checkpoints, guided run-of-show panel | M | O12 | Reset restores the exact seed; checkpoint load/restore round trip |
| **S24** | Record the full replay set from a live run; end-to-end replay test; launcher card; README; tune routing and costs | M | O2, O12, O13 | Full run in replay finishes offline and deterministically; **opt-in** live smoke suite (`pytest -m live`) |

## Dependencies and order

```
S00 → S01 → S02 → S03 → S04 → S05 → S06 → S07 → S08 → S09 → S10 → S11 → S12
S12 → S13 → S14 → S15 → S16 → S17 → S18 → S19 → S20 → S21 → S22 → S23 → S24
```

S10 can move earlier if desired. S16 (sandbox) has no dependency on S13–S15 and could be pulled forward if we want to de-risk the hardest part (real code execution) sooner.

## Main risks

| Risk | Mitigation |
|---|---|
| Generated code doesn't pass its own tests on stage | Bounded fix loop; small app; replay set recorded from a good run; checkpoint skip-ahead |
| Model output not matching schemas | Schema + retry-with-error; Haiku/Sonnet for strict JSON; replay fixtures lock behaviour |
| Cost or latency in live mode | Budget caps, Haiku for bulk, parallelism, replay as default for demos |
| ICA behaves differently per model family (D6, user says it doesn't) | One adapter; the first live call at M1 exit confirms it, and any quirk becomes a small per-model tweak; mock and replay cover everything else |
| Scope creep | Non-goals list; each step only starts on the user's go |
| Public repo leakage | CLAUDE.md rule 10; scrub check before any commit |
