# 04 · Demo scenario and run of show

## Sample project (proposal, D4)

**Meeting Room Booking**: staff browse rooms, book a slot, see conflicts, cancel; an admin manages rooms. Small enough to build and test in seconds, rich enough to have personas, NFRs, a data model, conflict logic worth testing, and something to monitor after go-live. Neutral domain, no client names.

Generated app: FastAPI + SQLite + plain HTML/JS. Roughly 6–8 endpoints, 3 tables.

Brief given to the workbench (about a paragraph): who uses it, what it must do, a couple of constraints (office hours only, no double booking, simple SSO placeholder), and one reference document (an invented office-policy note) uploaded to the context store.

## Run of show (15–20 min, replay mode)

| # | Moment | What the audience sees | Objectives shown |
|---|---|---|---|
| 1 | Setup wizard | Name, brief, execution mode, tick artefacts per phase, pick context, simulated connectors (badged) | O1, O11, O12 |
| 2 | Context | Upload the policy note; search it; see chunks | O4 |
| 3 | Requirements | Four artefacts generating in parallel with live progress; each shows author model and cited chunks | O1, O2, O4, O6 |
| 4 | Review with a visible independence label | Sonnet flags a gap (e.g. missing NFR for peak load); the artefact shows "independent" or "same family". Pull the reviewer offline to show the family picker | O3 |
| 5 | Human gate | Reviewer rejects with feedback; only affected artefact reruns; memory records the feedback; then approve | O5 |
| 6 | Design | User journey and wireframes rendered inline | O1, O2 |
| 7 | Architecture | Component overview and flow diagram rendered; HLD/LLD with requirement IDs | O1, O8 |
| 8 | Traceability | Matrix view; a deliberately uncovered requirement is flagged | O8 |
| 9 | Build & Test | DB, backend, frontend build in parallel; real test run output; one failing test auto-fixed in the loop | O6, O7 |
| 10 | Security gate | Planted fake secret caught by the scanner; deploy blocked, then cleared after fix | O9 |
| 11 | Deploy | IaC generated; app started locally; smoke test passes; cloud apply shown as dry-run, labelled simulated | O7, O12 |
| 12 | BAU handover | Runbook, SLOs/alerts, KT pack, hypercare plan, sign-off gate | O1 |
| 13 | Day-2 incident | Simulated incident arrives; triage agent proposes a fix; change flows back through a mini-lifecycle with a regression test | O1, O8 |
| 14 | Cost & trace | Cost by phase and model; trace inspector for one call; audit log | O10 |

## Demo safety nets

- **Replay mode:** recorded provider responses are served by the replay provider. Deterministic, free, offline. A banner always shows `REPLAY` or `LIVE`.
- **Reset:** one action restores the seeded project state in seconds.
- **Live mode** is the same code path with real providers, and may be shown for one artefact to prove it is real.
- **Skip-ahead checkpoints:** snapshots at each phase boundary so a demo can start mid-lifecycle.
- **Simulated badge** on every connector, the cloud deploy and the incident.
