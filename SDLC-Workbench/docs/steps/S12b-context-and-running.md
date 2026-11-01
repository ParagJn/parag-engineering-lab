# S12b · Documents, artefacts, running a phase

**Milestone:** M3  **Size:** L  **Objectives:** O1, O5, O11, O12  **Depends on:** S12a (closed), S06, S07, S09, S10
The second slice of S12 (see `S12-ui-slice.md`). After S12a you can create a project and see its seven phases; nothing can run yet. After S12b you can **run Setup and Requirements from the browser, watch them happen, and read what each agent wrote**.

## Goal
Add documents (upload, list, remove, search), the artefact cards and reader, a live run panel (start, progress, cost, cancel), and the two plain gate actions needed to get from Setup to Requirements. Replay mode must work end to end from a button, with no model and no cost.

## What I found before writing this (it changes the slice split)

1. **You cannot reach Requirements without approving Setup, and approving was planned for S12c.** The gate rule is that an earlier phase must be approved. So a browser run of Requirements needs "Hand to review" and "Approve" on Setup. I propose moving those **two plain buttons** into S12b. S12c keeps everything that needs thought: review findings, the independence label and family picker, request changes with per-artefact notes, re-run, hand edits, and the approval record. Approving in S12b is allowed with nothing reviewed; the audit row already records "unreviewed" (S08), and the screen says so.
2. **The routes for a start or cancel take no name.** S09's routes were built before S12a's `X-Actor` rule. Starting a run spends money in live mode, so I propose both now require `X-Actor` and write who asked into the audit trail. That changes the S09 route tests (they must send the header); I will list each one.
3. **Replay only answers when the prompt matches a recording exactly.** The key is a hash of model, prompt and limits, and the prompt contains the project name, brief and the policy note. A project made by hand in the wizard will not match, which is why the spec for S12 promised a **Load the sample project** button. Also `recordings/phase1` is stale from the non-functional requirements onward, so a re-record is needed (decision 7).
4. **The recording was made one artefact at a time; the UI runs them in parallel.** Prompts depend only on upstream artefacts, so they should match, but I have not proved it for a recording. I will prove it in a test (decision 8) before asking you to spend anything.
5. **Nothing in the backend lists or reads artefacts over HTTP**, or documents, or search. S12b adds about **11 routes**.
6. **The event stream through Vite's dev proxy is still unverified.** Proxies sometimes buffer streams, so progress would arrive all at once at the end. You will be the first to see it, so the manual check names it.

## Decisions I need from you (defaults chosen; say if you want any changed)

1. **Move "Hand to review" and "Approve" into S12b**, as plain buttons (finding 1). S12c keeps review, request changes, re-run, edit and the approval record. The alternative is a seeding shortcut that fakes an approved Setup, which would be dishonest.
2. **Starting and cancelling a run need `X-Actor`** and are recorded in the audit trail (finding 2). Reading runs and the event stream need nothing.
3. **Documents:** upload `.txt`, `.md`, `.docx`, `.pdf` and the other types the backend already accepts (10 MB limit, as built). The result shows guardrail flags by rule and line, never the text. Removing a document is allowed and audited. The same bytes twice say "already added" rather than adding again. No editing a document in place.
4. **Search is a plain box over the project's documents and approved artefacts**, showing the matched passage, where it came from and the ID you could cite. It is for you to check what the agents will see; it does not call a model.
5. **An artefact card shows:** name, status (not written, written, version N), author, the model that served it, cost (or "unknown", never $0.00), attempts, item count and a guardrail flag count. **Opening it shows** the Markdown (rendered under the S12 safety policy), the **sources it cited with their text**, the items it defined, what it was derived from and what is built on it, and the version list. A **"details"** disclosure shows why a first attempt was rejected (the repair reasons stored since S09), as text.
6. **Live progress:** a panel per run reading the event stream. Each artefact is a row (waiting, writing, retrying, done, failed, skipped, with the reason), the cost so far against the $2.00 cap, elapsed time, and **Cancel** (which says plainly that artefacts already being written will finish). Reloading the page rebuilds the panel from the stored run and events, so it never depends on having watched. Phase status refreshes itself when the run ends.
7. **Replay setup: you re-record once.** I give you the command: `python -m scripts.requirements_demo --live --record phase2` (about **$0.20**, Setup plus all of Requirements), then set `REPLAY_SET=phase2` in your `.env`. The Status shows which set is loaded, and the screen says so ("answering from recordings: phase2") so a miss is understandable. A replay miss shows the server's sentence (it names no prompt text). The alternative is to run live whenever you try this, which costs the same each time.
8. **Prove the recording matches before you spend:** a backend test records a scripted run one artefact at a time, then replays it through the parallel runner and checks every call is found. That checks finding 4 with no money.
9. **"Load the sample project"** button on the empty home page and in the wizard, which fills the exact name, brief and policy note the recording used (one source of truth, imported from the demo script's constants so they cannot drift) and, on create, uploads the policy note. It is a normal project afterwards.
10. **Events get a fixture too.** The contract exporter runs a scripted run and writes one real example of each event type into `frontend/src/contract/`, so the screen's event decoders are checked against the server, as for every other response.

Stated, not asked: the phase view replaces the S12a placeholder buttons with live ones driven only by `allowed_actions`; errors are the server's sentences shown as text; no new packages (`python-multipart` is already in the environment, and the frontend dependencies were installed in S12a); upload accepts one file at a time; deleting or renaming a project is still out.

## In scope
- **Backend routes** (new file `app/routes_content.py`, payloads written field by field):
  - `GET /api/projects/{id}/documents`, `POST` (multipart, `X-Actor`), `DELETE /documents/{number}` (`X-Actor`)
  - `GET /api/projects/{id}/search?q=&limit=`
  - `GET /api/projects/{id}/artefacts?phase=`, `GET /api/projects/{id}/artefacts/{artefact_id}` (latest version, generation summary, resolved sources, items, links in and out, version list), `GET .../artefacts/{artefact_id}/versions/{n}`
  - `POST /api/projects/{id}/phases/{key}/finish` and `.../approve` (`X-Actor`)
  - `GET /api/projects/{id}/runs?phase=` (so a reload can find the latest run)
  - `GET /api/sample` (the sample project's name, brief and policy text)
  - `X-Actor` now required on the existing run start and cancel (decision 2)
- **Frontend:** documents panel (upload, list, flags, remove), search, artefact cards and reader, run panel with live events and cancel, live buttons on the phase view, sample-project button, event decoders and a pure event-to-progress reducer.
- **Contract:** fixtures for the new responses and every event type; the staleness test and decoder tests extend as in S12a.

## Out of scope (later)
- S12c: review findings, family picker, request changes, re-run, hand edit, approval record. Design, diagrams and traceability screens (S13 to S15); cost and trace screens (S22); reset and seeded demo (S23); the launcher card (S24); deleting a project.

## Design notes
- **Files:** backend `app/routes_content.py` and `app/routes_artefacts.py` (two files so neither grows past one sitting); frontend `src/pages/` (`DocumentsPanel`, `ArtefactReader`, `RunPanel`), `src/state/runProgress.ts` (pure reducer over events), `src/api/events.ts` (decoders and the EventSource wrapper with a fake-able constructor).
- **What a response may carry:** no prompts, raw replies, keys, the endpoint or server paths (the S12a privacy test is extended to every new route with planted values). Document text is returned only in search hits and as cited sources, which are the same text the agents see.
- **Streaming:** `EventSource` resumes with `Last-Event-ID` on its own; the reducer is idempotent on event IDs so a replay of the same events changes nothing.
- **Untrusted text:** artefact Markdown, document names, search hits and event reasons all go through the S12 policy or are shown as plain text.

## Tests (must pass before the slice is done)

| Area | Proves |
|---|---|
| documents | upload returns the document and its flags (rule and line, no text); same bytes twice is `already_added`; an unsupported type, an empty file, an oversize file and a missing name are plain 4xx; removal works and is audited; `X-Actor` is required to change; a wrong project is 404 |
| search | hits carry passage, source and ID; an empty query is refused with a sentence; a limit is capped; nothing from another project appears |
| artefacts | list by phase; detail has the latest body, author, model, cost, attempts, items, flags, resolved sources and links; an unknown artefact or version is 404; cited text is only from this project; a superseded source shows "no longer available" instead of other text |
| gate actions | finish and approve follow `allowed_actions` exactly and refuse otherwise with the server's sentence; approve records what was open; both need `X-Actor`; a blocked phase cannot be approved |
| run routes | start and cancel need `X-Actor` and audit it; the existing S09 behaviour is unchanged; list-runs finds the latest run after a restart of the page |
| privacy | planted prompt, reply, key, endpoint and path text appears in no new response |
| replay match | a recording made serially replays through the parallel runner with no miss |
| sample | `GET /api/sample` equals the demo constants; a project built from it replays |
| event contract | one fixture per event type from a real scripted run; each decodes with the screen's decoders; a renamed field fails a test |
| run progress reducer | each event type moves a row to the right state; duplicates and out-of-order IDs change nothing; a run reloaded from stored events equals one watched live; cost against the cap; skipped shows its reason |
| components | static render of documents (empty, with flags, error), search results, artefact card (unwritten, written, failed, unknown cost), reader (untrusted Markdown stays inert, citations resolved), run panel (every row state, cancel disabled when over), phase view buttons exactly follow `allowed_actions` |
| unchanged | full backend suite green; every changed existing test is listed in PROGRESS |
| break-one-thing | a mutants file for the new backend (and the changed run routes), with the baseline guard, compile check and hung-suite rule; every survivor is a test gap |
| build | `npm test` and `npm run build` pass |

## Dependencies / installs
None. (You run one command in decision 7, which spends about $0.20 of ICA.)

## Questions for the user
Decisions 1 to 10. The ones that most change the work: **1** (approve moves into this slice), **7** (the $0.20 re-record and `REPLAY_SET`), and **9** (the sample button).

## Manual check for the user (we do not run the app)
1. Run the re-record command (decision 7), set `REPLAY_SET=phase2`, restart with `./start.sh`.
2. Home, **Load the sample project**, create. The Context step lists the policy note.
3. Documents: upload a small text file with a fake email in it; see the flag by rule and line, not the text; remove it. Search for "booking" and check the passage and ID.
4. Setup: **Run this phase**. A row appears per artefact; it finishes; open the charter and read it. **Hand to review**, then **Approve**.
5. Requirements: **Run this phase**. Watch the rows move **as they happen**, in waves, not all at the end (this is the proxy check). Open an artefact: sources with their text, items, the version.
6. Reload during a run; the panel should still be right. Press **Cancel** on another run and read what it says.
7. Open a failed or retried artefact's **details** (if any) to see why the first attempt was refused.
8. Tell me what is wrong, missing or confusing in the functionality. Look and feel waits, as you said.
9. `npm test` and `npm run build` pass.

## Done when
- [ ] Listed tests pass; full backend suite and `npm test` green (summary lines in PROGRESS.md)
- [ ] Break-one-thing check run with the baseline guard and reported honestly
- [ ] `npm run build` succeeds
- [ ] Manual-check list handed over
- [ ] PROGRESS.md updated
- [x] **You have run it in a browser and told me what you saw** (2026-10-29: replay and a live run; rows moved in waves, so the proxy streams)
- [x] User confirms (2026-10-29)

---

## Addendum 1 (2026-10-29): archive a project

Asked for by the user while checking S12b: "add a delete project option so that I can delete old projects." Chosen with the user: **archive, not erase** (answer to "what should delete do to the data?"), and a **simple confirm** (not typing the name).

**Why archive.** Artefact versions and the audit log are append-only by design (S01 triggers), and a project's runs, events and traces point at it. A real erase would need a deliberate exception to those guarantees. Archiving hides the project and keeps everything, is reversible, and weakens nothing. The cost: nothing is freed on disk. If real erasure is wanted later it is its own decision (what the audit trail keeps afterwards), not a side effect of a button.

**Behaviour**
- **Archive** hides a project from the list. **Restore** brings it back. Both need `X-Actor` and write `project.archived` / `project.restored` to the audit trail. Repeating either is harmless: the second call changes nothing and writes no second audit row.
- A project cannot be archived while a run is going on it (409, with a sentence): the run could still be spending money.
- An archived project is **read-only**: you can open and read it, but starting a run, uploading or removing a document, handing to review and approving are refused with "This project is archived; restore it first." Without this a hidden project could keep running.
- The home list shows active projects only, with a **Show archived** switch that lists the archived ones with a Restore button on each.
- One confirm step, inline on the card: "Archive 'Name'? Its documents and artefacts are kept and you can restore it." with Archive and Cancel.

**Changes**
- Schema **v6**: `projects.archived_at` (nullable text). Nothing existing changes; a v5 database upgrades keeping its data and its guards (tested, as v5 was).
- `ProjectRepo.archive / restore`; `list(archived=False)` by default. `/api/status` keeps counting all projects.
- Routes: `POST /api/projects/{id}/archive`, `POST /api/projects/{id}/restore`, `GET /api/projects?archived=true`. Project summary and detail gain `archived_at`.
- One helper refuses changes to an archived project, used by run start, document add/remove, finish and approve.
- Frontend: the project card becomes a link plus its own button (a button cannot sit inside a link), the inline confirm, the Show archived switch with Restore, and a banner on an archived project's page with its actions off. New contract fixtures (an archived list, archive and restore answers) so both sides check the new fields.

**Tests (all must pass before this is done)**
| Area | Proves |
|---|---|
| repository | archive hides from the default list and shows in the archived list; restore reverses it; both audited with the person's name; repeating either writes no second audit row; an unknown project is a 404; the project's data (artefacts, versions, documents, events) is untouched |
| routes | archive and restore need `X-Actor`; an active run blocks archiving with a sentence; `?archived=true` and the default list never overlap; summary and detail carry `archived_at` |
| read-only | each of run start, document add, document remove, finish and approve is refused on an archived project, with the same sentence, and works again after restore; reading everything still works |
| migration | a v5 database with data upgrades to v6, keeps its data and its immutability triggers, and every existing project is active |
| contract | the new fixtures decode; a renamed `archived_at` fails a test |
| components | static render: card with and without the confirm, archived list with Restore, the archived banner with actions off |
| break-one-thing | a mutants file for the above, run with the baseline guard, compile check and hung-suite rule; every survivor is a test gap |

**Not in this addendum:** erasing a project for real; archiving from inside the project page (the list is where old projects are found); renaming a project.
