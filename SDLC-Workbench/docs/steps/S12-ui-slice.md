# S12 · UI slice

**Milestone:** M3  **Size:** L  **Objectives:** O1, O5, O11, O12  **Depends on:** S05 to S11 (everything so far)
This is the first step you can *look at*. Everything before it was a backend you saw through scripts.

## Goal
After this step you can sit in a browser and do the whole Requirements story: create a project through a wizard, upload the policy note and search it, run a phase and watch it happen live, read what each agent wrote and what it cited, see the reviewer's findings and whether the review was independent, send named artefacts back with feedback, watch only those re-run, edit by hand, and approve. That is the "first demoable moment" (M3 exit) in the plan.

## What I found before writing this (it changes the plan)

1. **The backend has six routes, and almost none of them are what a screen needs.** Today: health, status, and S09's four (start a run, cancel, read a run, the event stream). There is no way to create or list a project, upload a document, read an artefact, review, approve, reject or edit over HTTP. S12 therefore adds about **18 routes**, which makes it as much a backend step as a UI step.
2. **The wizard's "execution mode" does nothing today.** A project stores a `mode` field, but nothing reads it; replay or live is one setting for the whole server (`APP_MODE`). I will not build a switch that looks real and isn't (rule 9, honest labelling). See decision 6.
3. **S08's re-run bypasses S09's runner.** `rerun_rejected` calls the agent runtime directly, so it has no events, no caps and no parallelism, which means a screen could not show it live. See decision 8.
4. **A replay demo needs recordings that match exactly.** The `phase1` recording is stale from the non-functional requirements onward (I changed that skill after recording it), and it only matches a project with the demo's exact name, brief and policy note. Reviews have no recordings at all, so reviewing in the browser needs live mode (cents) until S24 records the full set. See decision 10.
5. **I cannot run or look at the app** (your rule, and a good one). Everything that can be checked by code will be, but whether a screen *looks* right is only ever your eyes. Expect a feedback round after each slice. That is the main reason for decision 1.

## Decisions I need from you (defaults chosen; say if you want any changed)

1. **Build it in three slices, in order, each ending in something you can open.** Nothing in the plan is dropped; one big step becomes three that each have their own spec detail, tests, mutation check and your sign-off:
   - **S12a · shell, projects, wizard.** App shell with the REPLAY/LIVE banner, project list, the five-step new-project wizard, and a project overview showing the seven phases and their gate status. *You can create a project and see its lifecycle.* No model is called.
   - **S12b · context and running a phase.** Upload and search documents (with the guardrail flags), the phase view with artefact cards (author, model, cost, cited sources, items), version history, start a run, **live progress** and cancel. *You can run Setup and Requirements and watch them.*
   - **S12c · review and decide.** Reviewer findings with the independence label and the family picker, request changes with a note per artefact, re-run only those, edit by hand, approve (with the approval record shown). *You can reject one artefact, watch only it re-run, and approve.*
   This spec details S12a fully and sketches S12b and S12c; I write the detail of each when it starts, as for every step. The alternative is one large build and one large review, with three sessions' work between you and your first look.
2. **Stack: the sibling app's, trimmed.** Add **Tailwind 3.4.17** (pinned, as File-Compare does), **lucide-react** (icons), **react-markdown + remark-gfm** (artefacts *are* Markdown), and **Vitest** (the test runner the plan names). I am *not* adding a router library, a state library or an animation library. I cannot install packages (the shell blocks it, and the shared-environment rule), so **you run one install command** when S12a starts, and I record the versions it resolved. A note: the current `package.json` uses `latest` for everything; I will pin what I add.
3. **Look and feel: File-Compare's, so the lab apps feel like one family.** Light theme, slate greys, rounded cards, Inter or the system font, one accent colour, `REPLAY` and `LIVE` as unmistakable coloured chips, `SIMULATED` as a distinct hatched badge. Layout inside a project: a top bar, a left rail with the seven phases (each with its gate status), and the selected phase in the main area. Designed for a laptop, usable down to 320 px wide, no dark mode. Rough wireframes are below; **please react to them, because layout is taste and I cannot judge it from tests.**
4. **The screen contains no business rules.** Every rule lives in the backend and the UI shows the server's answer: the wizard asks the server what a selection *means* (`POST /api/plan/preview` returns the resolved plan, the waves, and "added because X needs it" notes); each phase comes back with an `allowed_actions` list, so the UI never re-implements the state machine; error messages are the server's own plain sentences, shown verbatim as text. The only checks in the browser are "this field is empty". That is also what makes the screen safe to change later.
5. **"Who you are" is a name, not a login.** There is no authentication (the backend listens on 127.0.0.1 only). The audit log still needs a person, so the app asks your name once, keeps it in this browser, and sends it as the actor (`human:<name>`) on every action that changes something. The screen says plainly that it is a label for the audit trail, not a sign-in. A change-your-name control sits in the top bar.
6. **Mode is shown, not chosen.** The wizard displays the server's mode as a fact ("This server is in REPLAY mode: it answers from recordings, free and offline"), copies it onto the project, and offers no switch. Switching mode per project would be a gateway feature; if you want it, it is its own step. The REPLAY/LIVE chip is in the top bar on every screen (O12).
7. **Simulated connectors are shown, badged, and do nothing.** Wizard step five lists four generic connectors (Source control, Issue tracker, CI/CD, Cloud account), each with a `SIMULATED` badge and the line "nothing is connected". Your tick is saved on the project as a note so later steps can refer to it, and changes no behaviour. Presenting them without the badge, or hiding them, would both be dishonest in opposite directions; the plan asks for them badged.
8. **The UI's re-run goes through S09's runner** (`only=` the artefacts with an unaddressed note), so it gets events, caps and live progress through the same code as every other run. `rerun_rejected` stays as it is (tested, used by scripts) and is documented as the non-streaming version. The alternative, giving it its own progress mechanism, would be a second path to keep correct.
9. **Contract fixtures, generated from the backend.** Because I cannot open a browser, the only mechanical protection against the screen and the server drifting apart is a shared contract. A script (`scripts/export_contract.py`) writes real example responses for every route the UI calls into `frontend/src/contract/*.json`; a backend test fails if they are stale (as the workflow catalogue does); Vitest decodes every fixture with the same decoders the screen uses. If a field is renamed on one side, a test fails on the other. The alternative is hand-written types alone, which compile but are not checked against reality.
10. **Replay needs two things from you, in S12b.** (a) Re-record the Requirements phase once (`requirements_demo --live --record phase2`, about **$0.20**), because the old recording is stale. (b) A "Load the sample project" button in the wizard fills in the demo's exact name, brief and policy note, so the replay keys match; without it, replay would miss on any wording difference. **Reviews cannot replay yet** (no review recordings exist until S24), so the S12c check runs a review live, which is a few cents an artefact.

Stated, not asked (say if you want any changed): artefact text is model output and is rendered as untrusted: **no raw HTML, no images, no scripts, and links carry no scripts and open in a new tab without access to this one**. Anything the server says is shown as text, never as HTML. There are no accessibility tests, only the basics (labels, keyboard use, focus), because I cannot run a checker. Projects cannot be deleted from the screen in this step (reset is S23).

## Wireframes (S12a). Text sketches, not designs.

**Project list (home)**
```
┌──────────────────────────────────────────────────────────────────────────────┐
│ SDLC Workbench                        [ REPLAY ]            you: Parag ✎     │
├──────────────────────────────────────────────────────────────────────────────┤
│  Projects                                          [ + New project ]         │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │ Meeting Room Booking          Requirements: running      3 of 7 phases │  │
│  │ created 29 Oct · next: write the Requirements artefacts                │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│  (empty state:  "No projects yet."   [ + New project ]   [ Load the sample ]) │
└──────────────────────────────────────────────────────────────────────────────┘
```
**Wizard, step 3 of 5 (what to produce)**
```
│  1 Basics ── 2 Mode ── ● 3 What to produce ── 4 Context ── 5 Connectors        │
│  Requirements                                                                  │
│   [x] Personas (required)          [x] Problem statement (required)            │
│   [x] Functional requirements (required)   [ ] User stories  (optional)        │
│   ⓘ "Epics and features" is included because it is required.                   │
│   Parallel waves:  1 Personas, Problem   2 Vision, Functional, Non-functional  │
│                                            [ Back ]   [ Next ]                 │
```
**Project overview (the seven phases)**
```
│ ◀ Projects   Meeting Room Booking                                              │
│ ┌ Phases ───────┐  Requirements   ● running                                   │
│ │ ✔ Setup       │  Next: write the Requirements artefacts       [ Run phase ]│
│ │ ● Requirements│  7 artefacts · 2 waiting on others                         │
│ │ ○ Design      │  (artefact cards arrive in S12b)                           │
│ │ ○ Architecture│                                                            │
│ └───────────────┘                                                            │
```

## S12a · In scope
- **Backend routes (new):** `POST /api/plan/preview`, `POST /api/projects`, `GET /api/projects`, `GET /api/projects/{id}` (the project plus the workflow snapshot, with `allowed_actions` per phase and the plan's notes). All validate their input strictly (unknown fields refused), check the project exists, take the actor from `X-Actor` for anything that changes state, and return plain-sentence errors with the right status (404, 409, 422).
- **Engine:** `allowed_actions` on each phase of the snapshot, computed from its status (`not_started`: run; `running`: run, send to review; `awaiting_review`: approve, request changes; `rejected`: re-run; `approved`: none), so the UI never decides.
- **Frontend:** the app shell (top bar with REPLAY/LIVE chip, name, back-end-unreachable state), a hash-based router written by hand and tested, the project list, the five-step wizard (Basics, Mode, What to produce, Context placeholder that says "documents arrive in the next slice", Connectors) ending in a review-and-create page, and the project overview with the phase rail. Empty, loading and error states for each.
- **Contract:** `scripts/export_contract.py`, the fixtures, the staleness test, and the TypeScript decoders.
- **Tooling:** Tailwind, Vitest, `npm test` and `npm run build` (which type-checks) both green.

## Out of scope (later in S12, or later steps)
- S12b: documents, search, artefact cards, versions, running and live progress, plus plain hand-to-review and approve buttons (moved here from S12c, see its spec). S12c: review findings, picker, request changes, re-run, edit, approval record.
- Design wireframes, diagrams and traceability screens (S13 to S15); cost and trace screens (S22); reset and seeded demo (S23); the launcher card (S24); deleting or renaming a project; reopening an approved phase; sign-in.

## Sketch of S12b and S12c (detailed when each starts)
- **S12b routes:** documents (add, list, remove), search, artefact list and detail (latest version, its generation record, cited sources, links in and out, version list), plus a `GET /api/sample`. **Screen:** artefact cards (author model, cost or "unknown", attempts, item count, guardrail flags); a drawer showing the Markdown with the citations resolved to their source text; the live run panel reading `/events` with `Last-Event-ID` resume, a progress list per artefact, the running cost against the cap, and Cancel.
- **S12c routes:** review one artefact, send to review, approve, request changes, edit. **Screen:** findings with severity and the independence chip; the family picker when the reviewer is unavailable; a note box per artefact; the stale-artefacts list; an editor that shows the server's refusal reasons; the approval record.

## Design notes
- **Files:** `backend/app/routes.py` is already one router; the new routes go in `app/routes_projects.py` (S12a) so no file grows past what can be read in one sitting. Frontend: `src/api/` (client and decoders), `src/state/` (pure reducers), `src/pages/`, `src/components/`, `src/lib/` (router, formatters, markdown policy). Pure logic lives apart from components so Vitest can test it without a browser.
- **No DOM test library.** Components are checked by rendering to static HTML with `react-dom/server`, which needs no browser and no extra package; logic is checked as plain functions.
- **State:** `useReducer` plus small hooks. No global store.
- **Actor header:** validated on the server with the same rule as everywhere else (`human:` and a non-blank name, bounded length, control characters refused). A missing or invalid header on a changing route is a 400 that says so.
- **Money:** an unknown price shows "unknown", never `$0.00` (the rule since S02).
- **CORS and the proxy:** the dev server already proxies `/api` to 8090, so the browser talks to one origin. The event stream through Vite's dev proxy is **unverified**; I expect it to stream, but you will be the first to see it, so the S12b check includes it explicitly.

## Tests (S12a; must pass before the slice is done)

| Area | Proves |
|---|---|
| plan preview | for a set of selections (everything, only required, an optional ticked, a required unticked, an unknown key, a dependency pulled in) the response equals `build_plan`'s result, carries the notes, and a bad selection is a 422 with the server's sentence |
| projects: create | valid creation opens all seven phases and returns the project; blank or oversize name or brief, unknown fields, a non-object selection, a bad mode: each refused with a plain 422 and nothing created |
| projects: list and get | newest first; an unknown ID is a 404; the snapshot is present and its phases are in lifecycle order |
| allowed actions | table-driven over every phase status and over blocked and unblocked: exactly the actions listed above, and none for a phase an earlier unapproved phase blocks |
| actor | a changing route without `X-Actor`, with a blank name, with control characters or over the length limit is a 400; a read route needs none; the audit row carries `human:<name>` |
| privacy | no response contains a path, a key, the endpoint, a prompt or a model reply (planted values) |
| contract | the fixtures exist for every route the UI calls, are not stale, and each decodes with the screen's decoders; a renamed field fails a test on the TypeScript side |
| router | every route parses and builds back to itself; an unknown or malformed hash falls back safely; the back button path works |
| wizard logic | step gating (cannot move on with a blank name or brief), the selection builder (ticks in, `selection` out; required items cannot be unticked), reset and review-and-create payload |
| api client | a 2xx decodes; a 4xx shows the server's sentence; a network failure says the backend is unreachable; an undecodable body is reported as a contract problem, not a crash |
| markdown safety | rendered to static HTML: a script tag, an inline handler, an image and a `javascript:` link are all inert in the output; ordinary headings, lists, tables and code render |
| formatters | unknown money is "unknown" and never zero; durations, token counts and relative times are stable; item IDs and source IDs render as given |
| actor storage | the name round-trips; a missing storage still lets the app run |
| shell states | rendered to static HTML: backend unreachable, loading, empty list, REPLAY and LIVE chips, the simulated badge |
| build | `npm run build` (type-check and bundle) and `npm test` both pass |
| unchanged | the whole existing backend suite passes; every changed existing test is listed in PROGRESS |
| break-one-thing | a mutants file for the new backend (and the engine change), run with the baseline guard, the compile check and the rule that a hung suite is inconclusive; every survivor is a test gap |

## Dependencies / installs
**You run one command** (I cannot): in `frontend/`, `npm install tailwindcss@3.4.17 postcss autoprefixer lucide-react react-markdown remark-gfm` and `npm install -D vitest`. Nothing goes into the shared Python environment (`python-multipart` is already there for S12b's uploads). I will give you the exact command when you say go on S12a, and record the versions it resolves. If Vitest is not compatible with the Vite version in your lockfile, I will tell you what it chose and why.

## Questions for the user
Decisions 1 to 10. The ones that most change the work: **1** (three slices), **2** (the installs), **3** (the look and layout, which I can't judge), and **7** (the simulated connectors).

## Manual check for the user (after S12a; we do not run the app myself, you do)
1. Run the install command, then `./start.sh` and open the page.
2. Enter your name when asked. The top bar shows it and a `REPLAY` or `LIVE` chip matching your server.
3. With no projects: the empty state, with "New project" and "Load the sample".
4. Walk the wizard: try to continue with a blank name (it should not let you); on step 3 untick an optional artefact, try to untick a required one (it should refuse), and see the "included because" note; on step 5 see the four connectors each badged `SIMULATED`.
5. Create the project. The overview lists the seven phases in order with Setup startable and the others waiting; reload the page and it is still there.
6. Stop the backend and reload: a clear "backend unreachable" state, not a blank page.
7. **Tell me what you'd change about the layout, wording and look.** That is the point of this slice.
8. `npm test` and `npm run build` in `frontend/` both pass.

## Done when (S12a)
- [x] Listed tests pass; full backend suite green and `npm test` green (1891 backend, 136 frontend)
- [x] Break-one-thing check run with the baseline guard and reported honestly (44 breaks, 3 survivors found and closed)
- [x] `npm run build` succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] User opened it in a browser and confirmed (2026-10-29; backend-unreachable check skipped by choice)
- [x] **You have opened it in a browser and told me what you saw** (S12a, S12b and S12c each, 2026-10-29 and 2026-10-30)
- [x] User confirms (S12a 2026-10-29, S12b 2026-10-29, S12c 2026-10-30). **S12 is closed.** The three slices are specified in `S12b-context-and-running.md` and `S12c-review-and-decide.md`.
