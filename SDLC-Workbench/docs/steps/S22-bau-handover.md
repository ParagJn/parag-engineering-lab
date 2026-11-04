# S22 · BAU handover: a runbook, a hypercare plan, and a manual sign-off

**Milestone:** M6  **Size:** M, three slices  **Objectives:** O1, O7  **Depends on:** S21 (Deploy: the by-hand checklist, the Word writer and the downloads), the approved Requirements to Architecture artefacts and the Deploy documents
**Status:** SPEC WRITTEN 2026-11-05 from the user's direction: "For BAU handover, we just need 3 things for now: runbook, hypercare plan and manual sign-off. Downloads as .docx and .md. No need for a model in the sign-off, it will be like a checklist. Other items, let's park them, as those might not be needed." **ANSWERED 2026-11-05: all ten defaults ("all defaults is good for me"). 22a BUILT AND VERIFIED 2026-11-05; 22b BUILT AND VERIFIED 2026-11-05; 22c BUILT AND VERIFIED 2026-11-05; CLOSED 2026-11-05 by the user ("we can close S22"), with one change: the sign-off panel is a collapsible fold that starts open (same fold as Deploy's; pinned by tests).**

## Goal
After this step the BAU handover phase has **two documents an agent writes** and **one record a person signs**, and nothing else:
- **Runbook**: how to operate the product day to day and what to do when it goes wrong. Downloadable as Markdown and as a Word file.
- **Hypercare plan**: the extra support in the first weeks after go-live, and when it ends. Downloadable the same two ways.
- **Handover sign-off**: **no agent, no model.** A checklist of acceptance statements that a named person answers, saved in their name. Reported on one page, as Markdown and Word.
- **Support guide, SLOs and alerts, and the knowledge-transfer pack** are shown as **Not enabled**, with a plain reason, using the mechanism Deploy already has. Nothing is deleted, so any of them can be switched on later.

## What I found before writing this (read from the code, not assumed)
1. **Handover has six artefacts today and none has an agent.** All six are routed to `handover_author`, which the routing file sends to **Haiku**. Only the runbook and the support guide are `required`, so the phase cannot be approved as it stands (the runbook has no skill, and the others cannot be run at all).
2. **Everything this needs already exists, except one thing.**
   - *Switching an artefact off* (`enabled: false` with a reason) and *done by hand* (`kind: checklist`) were built for Deploy in S21 and are in the catalogue loader, the plan, the engine, the payloads and the screens.
   - *The Word writer and the download route* (`app/deploy/docx_writer.py`, `app/routes_deploy.py`) are generic, but the route has a short list of artefact types it will serve (`DOWNLOADABLE = ("deployment_plan", "release_notes")`); the Handover documents need adding.
   - *The checklist machinery* (the record, the routes, the panel, the one-page report, the approval line) is written for **Deploy's** sixteen checks only: the table is `deploy_checks`, the phase is hard-wired to `deploy`, and the panel is shown only on the Deploy page. **This is the one real piece of work in this step:** make it a checklist for a named phase, so Handover's sign-off uses the same record with its own list of statements and its own page, with Deploy's behaviour unchanged.
3. **The sign-off in the catalogue is already the right shape.** `handover_signoff` is described as "the record that support accepts the product, with who signed and when". That is a person's decision, so it becomes `kind: checklist`, like the Deploy verification.
4. **The documents can only describe the design, not the live product.** The product is built and run outside this tool. A runbook therefore says *how the design says it should be operated and recovered*, and says plainly that the real commands, hosts, contacts and tools are not known to the design. They are written as open questions for the receiving team to fill in, never invented. The hypercare plan names *kinds* of support and a *proposed* length, marked as a proposal.
5. **The runbook's raw material is the Deploy plan and the architecture.** The plan already holds the steps, the configuration names and the rollback. The runbook can cite those steps by their IDs and add what is *operating* rather than *releasing*: routine checks, restart and recovery, what to look at when something is wrong. It must not repeat the plan.
6. **Size.** The runbook reads the architecture (component overview, high- and low-level design, non-functional requirements), the deployment plan and the release notes. The Build instruction set (about 148,000 characters) is NOT an input, for the same reason as the plan: it is over the input limit and support does not need it.

## Decisions (each has a default; say "all defaults" or change any)
1. **Three artefacts, as you said.** Runbook (`runbook`, `HND-RUN`) and hypercare plan (`hypercare_plan`, `HND-HYP`) are written by an agent. The handover sign-off (`handover_signoff`, `HND-SGN`) is done by hand. Default: as written.
2. **The other three are parked, not deleted.** `support_guide`, `slos_alerts` and `kt_pack` get `enabled: false` with a reason each ("Not enabled. Not needed yet; the runbook covers day-to-day problems. It can be switched on later."). They are shown as grey cards, never run, never required, never reviewed, and counted apart. Default: as written, with those sentences.
3. **Which are required.** Runbook: required (as today). Hypercare plan: **required**, because you listed it as one of the three things this phase is for. The sign-off is done by hand and never blocks approval. The phase is therefore approvable with the two documents written and the sign-off still open, and what was open is recorded with the approval. Default: runbook and hypercare plan required.
4. **What the runbook says.** Sections: Overview, Routine care, Starting and stopping, When something goes wrong, Recovery and rollback, Contacts and tools (as open questions), Coverage check, Open questions. Items `RUN-001` and so on, each citing the Deploy plan steps or architecture components it comes from, so every component of the architecture is covered or listed with a reason (the same coverage rule the plan has). It says plainly that it was written from the design and the plan, not from the live product. Default: these sections.
5. **What the hypercare plan says.** Sections: Overview, Who is on hand, What is watched, Escalation, Exit criteria, Coverage check, Open questions. Items `HYP-001` and so on. **Numbers the design does not give** (how many weeks, who is on call, response times) are written as a *proposal* and listed under Open questions, never stated as agreed. The exit criteria say when hypercare may end, in words a person can check. Default: these sections.
6. **Written from.** Runbook: component overview, high-level design, low-level design, non-functional requirements, project charter, **deployment plan**, **release notes**. Hypercare plan: functional and non-functional requirements, the high-level design, the **deployment plan**, the **release notes** and the **runbook**. Neither reads the Build instruction set. Default: as written.
7. **The sign-off is a short checklist a named person answers.** About eight acceptance statements in three groups, each answered **Accept**, **Not accepted** or **Not applicable**, with an optional note, saved in the person's name; changing an answer keeps the old one. Groups: *What support has been given* (the runbook has been read and is usable; the hypercare plan has been read and agreed; the support team knows who to ask), *What support can do* (they can start, stop and check the product by the runbook; they know how to reach the people who built it), *The decision* (an overall **Support accepts the product**, recorded last, plus a field for who signed and their role). **Not accepted anywhere is shown in red and does not block approval**, as with Deploy: approval is the person's decision and the page says what was open. The list is fixed in code; editing it is parked. Default: this list, worded in the build.
8. **Downloads.** The runbook and the hypercare plan each get **Download .md** and **Download .docx** (the artefact page and the run panel), the same as the Deploy plan. The sign-off gets the one-page report in both formats. Word files are made on the server from the saved Markdown with no model. Default: as written.
9. **Who writes and who reviews.** Both documents use the existing `handover_author` role. **The routing file sends it to Haiku**, the cheapest model; a runbook is a document support will rely on in a bad hour, so you may prefer Sonnet for it. Review, editing, stale detection and the "choose another family" picker are unchanged. Default: keep Haiku and say so; the change to Sonnet is one line in the routing file, offered not assumed.
10. **Order, and what is parked.** Built in three slices (below). Parked: the support guide, SLOs and alerts and the knowledge-transfer pack (as above); the day-2 incident loop from the original plan; a real alert or on-call integration; editing the sign-off list; a signed PDF. Default: as written.

Stated, not asked: nothing in this phase calls a model except writing the two documents, and no test calls a model. The two documents follow the existing agent, review, edit, stale and traceability rules unchanged. A Word file never holds anything the Markdown does not. The Deploy phase behaves exactly as it does now. Build Verify is not changed.

## Design notes
- **Definition** (`06-handover.yaml`): `runbook` and `hypercare_plan` stay written (`required: true`, `handover_author`), `hypercare_plan` after `runbook`; `handover_signoff` becomes `kind: checklist` (no role, no `after`); `support_guide`, `slos_alerts` and `kt_pack` get `enabled: false` and a reason. The existing loader rules already refuse a switched-off artefact that is required or that something enabled waits for, so `kt_pack`'s and `slos_alerts`' old `after` lines are removed.
- **Counts that move** (pinned in tests, regenerated after reading the diff): required count (the support guide and hypercare change), the not-enabled count (2 to 5), the by-hand count (1 to 2), artefacts that run in Handover (6 to 2), the plan preview, the status block, the catalogue document, the fixtures and the skills report. The traceability columns gain `RUN` and `HYP`, named in words.
- **Skills** (`runbook.md`, `hypercare_plan.md`): same shape as the Deploy plan skill (inputs, sections, items with `Derives from:`, a coverage line, "never" lines for secrets, invented numbers and claims about the live product), linted by the existing linter.
- **The checklist, generalised.** The list of checks becomes a table keyed by phase (`deploy` and `handover`), the record gains a `phase` column (schema v10, existing Deploy rows backfilled to `deploy`), and the service, routes, panel and report take the phase. The old Deploy routes keep working at the same addresses; Handover's are `/handover/checklist`. The approval's open-items line for each phase comes from its own list. A Handover answer is written only while the Handover phase is open. This is the one structural change.
- **Downloads:** `DOWNLOADABLE` gains `runbook` and `hypercare_plan`; the front-end list does the same.
- **Screens:** the Handover page lists the two written artefacts, a blue "Done by hand" card for the sign-off with its progress, and three grey "Not enabled" cards; the checklist panel (a fold that starts open) appears on the Handover page too, with its own title and groups.

## Slices
| Slice | Delivers |
|---|---|
| **22a** | The checklist made general: a list per phase, the phase column (schema v10), phase-aware service, routes, panel and report; Deploy unchanged and proven so. No new content yet. |
| **22b** | The Handover definition (two written, one by hand, three switched off), the runbook and hypercare skills, their checks, the downloads, the skills report and traceability names, an offline demo. |
| **22c** | The sign-off list and its panel and report on the Handover page, the approval line, the full set of tests and sweeps. |

## Out of scope
Support guide, SLOs and alerts, knowledge-transfer pack (parked, switched off); the day-2 incident loop; any real alerting or on-call integration; editing the sign-off list; a signed PDF; a Word download of other artefacts.

## Tests (must pass before each slice is done)
| Area | Proves |
|---|---|
| general checklist | the Deploy checklist reads and writes exactly as before through the generalised code; a Handover answer is kept apart from a Deploy answer for the same project; an answer for the wrong phase's check is refused; the old addresses still work; existing Deploy rows are read as Deploy after the migration |
| definition | Handover loads with two written, one by hand and three switched off; the old `after` lines are gone; every refusal rule of the loader still holds; nothing else changes |
| counts | artefact, required, not-enabled and by-hand counts agree in the catalogue, the plan preview, the status block, the document and the fixtures |
| skills | both skills pass the linter; each cites only IDs that exist; a missing section, an invented ID, an invented number or a secret is sent back; the hypercare plan reads the runbook; scripted replies only |
| run | a Handover run writes the runbook then the hypercare plan, fails at nothing, and writes nothing for the sign-off or the three parked ones |
| downloads | the runbook and hypercare plan download as `.md` (the saved text) and `.docx` (read back and compared); the sign-off report likewise; nothing else is downloadable |
| sign-off | every statement has a stable ID; an answer is saved in a person's name and kept; the latest counts; an agent or the system may not answer; a closed phase refuses; the decision is recorded last and never worked out |
| approval | the Handover approval records the Not-accepted and unanswered statements; no other phase's record changes; approval is never blocked by the sign-off |
| page | the grey cards with their reasons; the by-hand card with progress; the checklist fold open by default, with Handover's own title and groups; downloads on the artefact page and run panel |
| unchanged | Deploy, every earlier phase, the instruction set, Build Verify; `export_contract --check`; no test touches `backend/data` |
| break-one-thing | a mutants file per slice with the baseline guard; every survivor closed with a real test, or recorded as equivalent |

## Dependencies / installs
None. `python-docx` and `markdown-it-py` are already used by Deploy.

## Questions for the user
Say "all defaults" or change any of the ten. The ones most worth a look: (3) the hypercare plan being **required**; (5) numbers like weeks and response times being proposals and open questions, never stated; (7) the eight acceptance statements and that a Not-accepted does not block approval; (9) **Haiku** writing a runbook, with Sonnet a one-line change.

## Manual check for the user (we do not run the app)
After 22b: `cd backend && python -m scripts.handover_demo` (offline and free: a runbook and a hypercare plan from fixed sample text, written to a temporary folder as `.md` and `.docx`). After 22c: restart the backend; the Handover page shows the two documents, the blue sign-off card, three grey cards, and the checklist; answer a few statements, change one, and download the report. I will not start a live run.

## Done when
- [ ] Listed tests pass; full suites green (summary lines in PROGRESS.md)
- [ ] Break-one-thing check run with the baseline guard and reported honestly
- [ ] `npm run build` succeeds
- [ ] Manual-check list handed over
- [ ] PROGRESS.md and RESUME.md updated
- [ ] **You have opened a downloaded runbook .docx and answered some sign-off statements, and told me what you saw**
- [ ] User confirms
