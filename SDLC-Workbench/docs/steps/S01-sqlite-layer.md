# S01 · SQLite layer

**Milestone:** M1  **Size:** M  **Objectives:** O8, O13 (and the base for O5, O10)  **Depends on:** S00

## Goal
Everything the workbench remembers lives in one SQLite file behind small repositories: projects, phase runs, artefacts and their immutable versions, traceability links, LLM call traces, an append-only audit log, and project memory. No LLM, no workflow rules yet.

## In scope
- `db.py`: `Database` (connection per unit of work, foreign keys on, WAL), versioned migrations via `PRAGMA user_version`.
- `models.py`: frozen dataclasses for each row type, the allowed values, and three error types.
- `repos.py`: one repository per table group, grouped in a `Store`.
- `config.py`: `DATA_DIR` setting and `db_path`.
- `main.py`: `create_app` opens the store; `/api/status` gains a `db` block (schema version, project count) so you can see it working. The placeholder page shows it.

## Out of scope (later steps)
- Phase transition rules and gates (S05). The repo checks that a status is valid, not that the move is legal.
- Link extraction and gap detection (S15), cost rollups in the UI (S22), retrieval (S06).
- Project deletion. See decisions.

## Design decisions (veto any of these)
1. **Standard-library `sqlite3`, no ORM.** Matches the plan and adds no dependency.
2. **A new connection per operation.** Writes use `BEGIN IMMEDIATE`, so concurrent writers queue instead of corrupting each other. This is what makes parallel artefact generation (O6) safe, and it is tested with threads.
3. **Every state change writes its audit row in the same transaction.** A change cannot exist without its audit entry (tested by making the audit write fail). Mutating calls therefore take a required `actor`: `system`, `human:<name>` or `agent:<role>@<model>`.
4. **Versions are immutable.** Database triggers reject changing or deleting a version's body, author, number, sources or timestamp. The one exception is `review_findings`, because the reviewer runs after the version exists. A human edit is a new version.
5. **The audit log is append-only**, enforced by triggers (update and delete both abort), not by convention. It has no foreign key to projects, so it can outlive them.
6. **Gate decisions come from people (or `system`), never from agents.** `record_decision` refuses an `agent:` actor, and a rejection needs written feedback. `approved` and `rejected` can only be reached through `record_decision`, so a phase can't be "approved" without a recorded decision.
7. **Cost `NULL` means unknown, never zero.** Rollups count unpriced calls and report a total of `None` when nothing in a group was priced.
8. **Artefacts are keyed by `(project, id)` with ids like `REQ-F-012`.** `create(prefix="REQ-F")` allocates the next number inside the write lock, so concurrent callers never collide. Prefix `REQ` does not count `REQ-F-*` ids.
9. **Links join stable IDs, not artefact rows.** A requirement such as `REQ-F-012` is an item inside an artefact body, so links hold two ID strings plus an optional `declared_in` artefact (checked to exist). S15 will do extraction on top of this.
10. **No project deletion.** Versions and the audit log are immutable, so a delete would have to fight its own triggers. The demo reset (S23) replaces the database file instead.
11. **Timestamps are ISO-8601 UTC with milliseconds**, from an injected clock. Project ids come from an injected factory. Tests use both for deterministic output.
12. **The database file is `backend/data/sdlc_workbench.db`** (gitignored) unless `DATA_DIR` is set. Tests always use a temp directory.

## Schema (v1)

| Table | Key | Notes |
|---|---|---|
| `projects` | `id` | name, brief, mode, `selection` and `routing_overrides` (JSON), `context_id`, timestamps |
| `phase_runs` | `(project_id, phase_key)` | status, started/finished, decision, decided_by, feedback. One row per phase; history lives in audit |
| `artefacts` | `(project_id, id)` | type, phase_key, title |
| `artefact_versions` | `(project_id, artefact_id, number)` | body, author, `source_chunks` (JSON), `review_findings` (JSON), immutable |
| `links` | `id`, unique `(project, from, to, kind)` | kinds: derives, implements, verifies, deploys; no self-links |
| `traces` | `id` | agent, slot, requested vs served model, fallback flag, status, tokens, latency, `cost_usd` (nullable) |
| `audit` | `id` | actor, action, target, detail (JSON); append-only |
| `memory` | `id` | kind (`reviewer_feedback`, `human_feedback`, `note`), optional phase and artefact, text |

Later steps add columns through new migrations (the version number is checked, and a database newer than the code is refused).

## Tests (must pass before the step is done)

| Area | Proves |
|---|---|
| `db` | all tables created; migrate is idempotent and keeps data; a newer-than-code schema is refused; foreign keys on for every connection; WAL set; a failed write rolls back; parent folder created |
| foreign keys and checks | each child table rejects an unknown project; links and memory reject an unknown artefact; bad enum values rejected by the database itself |
| projects | create/get/list/count round trip; defaults; blank name and bad mode rejected; update changes only what is given, bumps `updated_at`, and can clear `context_id`; unknown project; JSON round trip; audit row written; **audit failure rolls the change back** |
| phase runs | ensure is idempotent; running sets start and clears an earlier decision; awaiting review sets finish; approved/rejected refused via `set_status`; approve and reject recorded; reject needs feedback; agents can't decide; missing phase; transitions audited |
| artefacts | id format; prefix allocation is sequential, per project, and ignores longer prefixes; exactly one of id/prefix; duplicate refused; versions number 1..n; latest version; author format; blank body refused; sources round trip; review findings change only findings; **immutability enforced by the database**; **20 concurrent creates get unique ids**; **10 concurrent versions get unique numbers**; filters; audit actor is the author |
| links | add and list; adding twice gives one row; filters; self-link, bad kind, bad id refused; `declared_in` must exist |
| traces | ok and error traces; unknown cost stays `None`; negative tokens and bad status refused; project optional; rollups by model, phase, agent and slot sum correctly and count unpriced, errors and fallbacks; rollups are per project |
| audit | append and ordered list; filters; **update and delete are blocked**; invalid actor refused; a full create-project-to-version flow leaves the expected trail |
| memory | add and list; scoped per project; filters; blank text and bad kind refused; artefact must exist |
| status / config | `DATA_DIR` respected, default under `backend/data`; `/api/status` reports schema version and project count and leaks no file path |

## Dependencies / installs
None. Standard library only.

## Manual check for the user (we do not run the app)
1. From `SDLC-Workbench/` run `./start.sh` and open `http://localhost:5270`.
2. The page should show a **Database: v1, 0 projects** pill next to the existing ones.
3. `backend/data/sdlc_workbench.db` should now exist, and `git status` should not list it.
4. Optional: `http://localhost:8090/api/status` shows a `db` block with `schema_version: 1` and no file path.
5. Restart the app; nothing should error and the schema version should stay 1.

## Done when
- [x] Listed tests pass; full suite green (`144 passed, 1 deselected`, in PROGRESS.md)
- [x] Frontend `npm run build` still succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] User confirmed 2026-10-27 (screenshot of the page: "Database: v1, 0 projects", API key set, Gemini priced)
