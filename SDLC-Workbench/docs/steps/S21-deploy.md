# S21 · Deploy: a plan, release notes, and a manual go / no-go check

**Milestone:** M6  **Size:** M, three slices  **Objectives:** O1, O7, O9  **Depends on:** S19 (the instruction set), S20 (Build Verify), the approved Requirements to Architecture artefacts
**Status:** SPEC WRITTEN 2026-11-05 from the user's direction: "We need a deployment plan, release notes and deployment verification. The verification is going to be a manual process where the user is needed to check go / no go on checks, no AI needed. The plan and release notes need to be in docx and md file format that can be downloaded. Infra as code and CI/CD pipeline: keep them disabled. We may never need them, or we can have them later." **ANSWERED 2026-11-05: all ten defaults ("all defaults is good"). 21a BUILT AND TESTED 2026-11-05; 21b next.**
(Numbering: the build plan's old S19 "Deploy" and S20 "BAU handover" are renumbered; this is **S21**, and BAU Handover follows as **S22**.)

## Goal
After this step the Deploy phase has **three working artefacts** and **two that are visibly switched off**:
- **Deployment plan**: an agent writes it from the approved design; it can be downloaded as **Markdown and as a Word file**.
- **Release notes**: an agent writes them from the approved design; downloadable the same two ways.
- **Deployment verification**: **no agent, no model.** A checklist of go / no-go checks that a person works through and signs.
- **Infrastructure as code** and **CI/CD pipeline**: shown as **Not enabled**, with a plain reason, not hidden and not failed. Nothing is deleted, so they can be switched on later.

## What I found before writing this (read from the code, not assumed)
1. **Deploy has five artefacts today, and none has an agent.** The definition file lists them and the catalogue loads them, but there is not one skill file behind any of them (`backend/app/phases/skills/` holds the Requirements, Design, Architecture and Build skills only). All five are `required: true` except the pipeline, so **the phase cannot be approved as it stands**.
2. **"Switched off" does not exist yet.** An artefact is either required or optional; there is no way to say "this is part of the design of the product but not in use". The Build phase's retired artefacts (`database_schema`, `backend_code`) are a different thing: they were removed from the catalogue and are skipped when found. A switched-off artefact needs a new, small, honest mechanism (decision 3).
3. **The DevOps role is routed to OpenAI** (`routing.yaml`: `devops_engineer: openai`), reviewed by the usual rule. The two agent-written documents will use that role unless you say otherwise (decision 8).
4. **Word files are cheap to make.** `python-docx` 1.2.0 is already in the shared venv and in `requirements.txt` (the context store reads uploaded `.docx` with it), so writing one needs **no new package**. The lab's `md-to-docx` app does the same job in the browser, but this tool should not depend on another app, and the server already holds the text. Markdown headings, paragraphs, bullet and numbered lists, tables, bold and italic, and code blocks cover everything these two documents need.
5. **The pieces for a checklist exist, but not a person-signed one.** Artefacts are written by an agent and optionally edited by a person; there is nothing yet that is *filled in by a person*. The verification therefore cannot be an ordinary artefact written by a model. It needs its own small record (decision 5) that is append-only like the rest of the audit trail.
6. **What the plan and the notes should say depends on what was built outside the tool.** The code is built elsewhere (VS Code and the like). The plan must therefore describe *how to put the built product somewhere*, in terms of the approved architecture and the instruction set, and say plainly that it did not see the code. Build Verify (S20) is the only link back to real code; the plan may cite its latest run as a fact ("last compared on <date>: 12 of 14 endpoints found") and must not claim more.

## Decisions (each has a default; say "all defaults" or change any)
1. **Three artefacts are written; the plan and the notes by an agent, the verification by a person.** Deployment plan (`deployment_plan`, prefix `DEP-PLN`), Release notes (`release_notes`, `DEP-REL`), Deployment verification (`deployment_verification`, `DEP-VER`, no agent). Default: as written.
2. **Where each comes from.** The **plan** is written from the approved Architecture (components, high-level and low-level design, flow), the non-functional requirements, and the instruction set's foundation (stack and how to run it). Sections: Overview, Environments, Order of steps, Configuration and secrets (names only, never values), Data and migrations, Rollback, Risks and open questions, Traceability. The **release notes** are written from the approved Requirements and Design: what is new, in words a business reader can follow, by feature, with known limits and the open questions the design still carried. Sections: Overview, What is new, Known limits, Upgrade notes, Traceability. Both cite design item IDs and use the existing checks (sections, order, no secrets, only IDs that exist). Default: as written.
3. **Switching an artefact off.** A new optional field in the phase definition, `enabled: false` with a mandatory `disabled_reason`, on `infrastructure_as_code` and `cicd_pipeline`. A switched-off artefact: is **not required** for approval, **is never run** (the plan shows it as "Not enabled"), shows on the phase page as a grey card with its reason and no buttons, is **never reviewed**, and is **counted separately** ("2 not enabled") so no count is quietly lower. It stays in the catalogue, its skill need not exist, and **turning it on is a one-line change** plus its skill. Default: as written. (`enabled` defaults to true everywhere else, so no other artefact changes.)
4. **The reasons shown.** Infrastructure as code: "Not enabled: the product is built and run outside this tool, so there is nothing for it to describe yet. It can be switched on later." CI/CD pipeline: "Not enabled: no automated build or release is wanted yet. It can be switched on later." Default: these two sentences.
5. **Deployment verification is a checklist a person signs, with no model.** A fixed list of go / no-go checks (decision 6). For each check the person chooses **Go**, **No-go** or **Not applicable**, writes an optional note, and the choice is saved **in their name** with the time. Every choice is kept (append-only); changing your mind adds a new line and the latest line counts, so the history shows the change. The screen shows the latest state of each check, who set it and when. Default: as written.
6. **The checks.** Written by the system, not a model, in four groups, each a single yes / no question a person can answer by looking:
   - *Ready to go*: the deployment plan has been read and agreed; the release notes have been read and agreed; the people who need to know have been told; a rollback has been agreed and the person who will do it is named.
   - *Before release*: the build has been compared with the design (a Build Verify run exists, and its date is shown beside the check, as a fact and not a pass); secrets and configuration are in place and none is in the code; a backup or a way back exists for any data that changes; the environment is the one the plan names.
   - *After release*: the product starts; the main thing the product is for works once, end to end, by hand; the endpoints or pages named in the release notes respond; nothing in the logs that should not be there; the people it is for can reach it.
   - *Decision*: an overall **Go / No-go** for the release, which the person records last.

   Each check cites the design item or plan section it comes from where there is one. **The list is fixed in code and shown as text; editing it is parked** (a person can write what they need in the note). Default: these four groups and about sixteen checks, worded in the build.
7. **What "done" means for the verification.** It is complete when every check has an answer (Go, No-go or Not applicable) and the overall decision is recorded. A **No-go anywhere is shown in red and does not block approval of the phase**, as in every phase: approval is the person's decision, and the page says what was open when they approved ("2 checks No-go, 3 unanswered"), recorded with the approval like the other open items. Default: advice, not a gate.
8. **Who writes and who reviews.** The plan and the notes use the existing `devops_engineer` role (OpenAI today), reviewed by the usual rubric and the usual independence label, with the usual "choose another family" picker. The verification has no author model and **no review** (nothing to review). Default: existing roles and review; a different role for the notes is a one-line routing change, offered, not assumed.
9. **Downloads: Markdown and Word, for the plan and the notes.** On the artefact page, next to Read it / Edit, two buttons: **Download .md** and **Download .docx**; also on the run panel row, as icons, like the instruction files. Word files are made **on the server** with `python-docx` (no new package, no model), from the saved Markdown of the version shown: real heading styles, bullet and numbered lists, tables with a header row, bold and italic, code in a monospace style, and the document title, version and date in the properties. The file name is `<artefact id>-v<n>.docx` (and `.md`). An artefact with no content has no buttons. The reader shows exactly the version being downloaded. **No Word download for the verification**: it is a record, but it has the same two buttons as a one-line Markdown and Word *report* of its latest state (who, what, when) so it can be filed. Default: as written.
10. **Order, and what is left.** Built in three slices (below). Parked: switching Infrastructure as code or the pipeline on (needs a skill each); a Word download of every artefact; custom checks; a signed PDF; an approval that waits for a Go. Default: as written.

Stated, not asked: the two written artefacts follow the existing agent, review, edit, stale-detection and traceability rules unchanged. A Word file never contains anything the Markdown does not (no hidden content, no macros, no links to the outside beyond ones already in the text, and a link whose address is not http, https or mailto is written as plain text). No test calls a model; the agent's replies are scripted. The existing phases, artefacts and the instruction set are untouched. Build Verify is not changed.

## Design notes
- **Definition** (`05-deploy.yaml`): `deployment_plan` and `release_notes` stay `required: true`; `deployment_verification` becomes a **record-kind** artefact (a new `kind: checklist`, no role); `infrastructure_as_code` and `cicd_pipeline` get `enabled: false` and `disabled_reason`. `after:` lines are kept consistent (the verification waits for the plan and the notes). The loader validates the new fields as strictly as the old ones: `enabled: false` without a reason, a reason on an enabled artefact, and a checklist with a role are all errors that name the file.
- **Catalogue and counts that move** (pinned in tests, regenerated after reading the diff): the artefact count stays, required count drops (the two switched-off ones were required), a new "not enabled" count, the plan preview, the status payload, the catalogue document and the contract fixtures.
- **Skills** (`deployment_plan.md`, `release_notes.md`): same shape as the Architecture skills (inputs, sections, items such as `DPL-001` steps and `REL-001` entries with `Derives from:`), linted by the existing skill linter.
- **Checklist storage**: a new table `deploy_checks` (project, check ID, answer, note, actor, time), append-only with the usual triggers (schema v9); the latest row per check is the current answer. The check list itself lives in code (`app/deploy/checks.py`) with stable IDs `CHK-001` and so on.
- **Word writer** (`app/deploy/docx_writer.py`): a small Markdown-to-Word converter over `markdown-it-py` (already installed, already a dependency of `rich`/others in the venv — to be confirmed in the build; if it is not in `requirements.txt` it is added there, which is the declared file, not the shared venv) and `python-docx`. Pure functions: Markdown text in, bytes out; unit-tested by reading the file back.
- **Routes**: `GET /api/projects/{id}/artefacts/{aid}/download?format=md|docx[&version=n]` (read-only, no name needed, archived projects can still be read), `GET/PUT` for the checklist (`PUT` needs a person's name and a project that is not archived, phase running or awaiting review).
- **Screens**: the grey "Not enabled" card; the Deploy phase page lists the three artefacts first; the checklist panel (four groups, a Go / No-go / N/A choice per check, a note box, who and when, the overall decision, and a count at the top); download buttons on the artefact page and the run panel.

## Slices
| Slice | Delivers |
|---|---|
| **21a** | Switching off: the `enabled` / `disabled_reason` fields, strict loading, the catalogue, the plan, approval and counts, the grey card, the two reasons. No model, no new artefact. |
| **21b** | The plan and the release notes: two skills, their checks, the run, review and edit as for any artefact; the Word writer; the downloads (md and docx) on the artefact page and run panel; an offline demo. |
| **21c** | The verification checklist: the fixed list, the record and its routes, the panel, the open-items line on approval, and the one-page report in Markdown and Word. |

## Out of scope
Infrastructure as code and the CI/CD pipeline (switched off, not built); any model in the verification; running or deploying anything; BAU Handover (S22); editing the checklist; a PDF; a Word download of other artefacts.

## Tests (must pass before each slice is done)
| Area | Proves |
|---|---|
| definition | `enabled: false` needs a reason; a reason on an enabled artefact is refused; a checklist artefact with a role is refused; every other phase loads exactly as before |
| switched off | a disabled artefact is not required, never run, never reviewed, never in a plan, listed as "not enabled" with its reason, and counted apart; approval of the phase does not wait for it; nothing is deleted |
| counts | artefact, required and not-enabled counts agree in the catalogue, the plan preview, the status payload and the fixtures |
| skills | the plan and the release notes pass the skill linter; each cites only IDs that exist; a missing section, an invented ID or a secret is sent back; scripted replies only |
| docx | the Word file reads back with the same headings, lists, tables and text as the Markdown; heading styles are real styles; links are kept only for http, https and mailto; no content in the Word file that is not in the Markdown; an empty artefact gives no file |
| downloads | the right version is downloaded; the file name follows the rule; the Markdown is byte for byte the saved text; an unknown artefact or version is a 404; an archived project can still be read |
| checklist | every check has a stable ID and a question; an answer is saved in a person's name and kept; a new answer does not erase the old one; the latest counts; an agent or the system may not answer; a closed phase refuses; the totals add up |
| decision | the overall Go / No-go is recorded last and shown; a No-go does not block approval; approval records what was open |
| report | the one-page report lists every check with its latest answer, who and when, and reads back from the Word file |
| page | the grey card with its reason; the three artefacts first; the checklist groups and choices; the download buttons; text from the server shown as text |
| unchanged | every earlier phase, the instruction set, Build Verify; `export_contract --check`; no test touches `backend/data` |
| break-one-thing | a mutants file per slice with the baseline guard; every survivor closed with a real test |

## Dependencies / installs
None. `python-docx` and the Markdown parser are already available; if the Markdown parser is not yet listed in `requirements.txt` it is added there (the declared file) and nothing is installed into the shared venv.

## Questions for the user
Say "all defaults" or change any of the ten. The ones most worth a look: (3) the new "switched off" mechanism and its two sentences; (6) the sixteen-ish checks and their four groups (you may want your own wording); (7) a No-go is advice and does not block approval; (8) OpenAI writes the plan and the notes, as the routing file says today; (9) Word files are made on the server, and the verification also gets a one-page report.

## Manual check for the user (we do not run the app)
After 21a: restart the backend; the Deploy page shows two grey "Not enabled" cards with their reasons and three working ones. After 21b: `cd backend && python -m scripts.deploy_demo` (offline and free: a plan and release notes from scripted replies, written to a temporary folder as .md and .docx so you can open them in Word), then on a real project a live run of Deploy (two model calls, a few cents). After 21c: open the checklist, answer a few checks, change one, and look at the history and the report. I will not start a live run.

## Done when
- [ ] Listed tests pass; full suites green (summary lines in PROGRESS.md)
- [ ] Break-one-thing check run with the baseline guard and reported honestly
- [ ] `npm run build` succeeds
- [ ] Manual-check list handed over
- [ ] PROGRESS.md and RESUME.md updated
- [ ] **You have opened a downloaded .docx in Word and told me what you saw**
- [ ] User confirms
