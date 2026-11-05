# S23 · Configuration: users and roles, system configuration, and document templates

**Milestone:** M7 (configuration)  **Size:** L, three parts (A users and roles, B system configuration, C document templates), each in slices  **Depends on:** all seven phases (done)
**Status:** Part A CLOSED 2026-11-05 (slices 23a, 23b, 23c; the user tried every role in the UI and said it works perfectly). Part B (23d, 23e) BUILT AND VERIFIED 2026-11-05, awaiting the user's try-out; 23f (model routing) is still a plan. Part C step 1 (store templates only, one `.docx` per type per project in `data/Templates/<project>/`) is BUILT AND VERIFIED 2026-11-05; USING a template in a Word download is the next step.
**Part C (templates) added at the user's request and ANSWERED (Q12 to Q17) the same day; Q15 CONFIRMED by the user the same day (option 1).** **ANSWERED so far: Q1 and Q3.** Q1: the app always runs on the user's own computer, so there is **no sign-in and no password** ("that happens in the production world"); option (a), a typed name checked against the Users list, with the screen saying plainly that a name is a label. Q3: **the suggested role names are accepted** (list below). **Q2 and Q4 to Q11 are still open: ask for them first thing tomorrow, or take the stated defaults if the user says "all defaults".**
It replaces the parked wish **D16** (a complete configuration screen) and the "who may change them" question in it.

## What the user asked for
1. **Users and roles.** A project manager does the setup and builds the requirements, but the requirements can only be **approved** by a user with the **architect** role. Design is built by the project manager but approved by a user with the architect role, and so on. **A user can have more than one role.** This is the first piece of configuration.
2. **System configuration.** A screen where the model names, the prices, the cost and budget limits can be changed. After saving, the app **tells the user to restart it**. Basically the whole `.env` can be configuration.

3. **Templates (added later).** Each project can have templates for its documents (deployment plan, release notes and so on): upload a file, give it a category, and when someone downloads a document as Word, the app looks for a template for that category and builds the document in that layout.

## What I found in the code (read, not assumed)
- **There is no sign-in.** The screen asks for a name and sends it in the `X-Actor` header (`app/actor.py`); the server turns it into `human:<name>`. It is "a label for the audit trail, not a credential", and the code says so. **Roles that mean something need a real identity**, so the first decision is how far to go (Question 1).
- **Approval is not restricted today.** Each phase has an `approver` in its definition file, but it is only a label shown on the page ("awaiting review by the technical lead"). The engine's `approve` and `reject` take any named person. So there are two things to add: a place that says who is who, and a check at approval.
- **The labels already in the definitions** are: Setup, Requirements, Design = "business engineer"; Architecture, Build = "technical lead"; Deploy = "deployment engineer"; BAU handover = "BAU lead". These do not match the user's example (project manager, architect). The role names need agreeing (Question 3).
- **Settings come from `backend/.env`** through one class (`app/config.py`, about 80 settings, read once when the app starts, which is why a restart is needed). The real `.env` holds the keys; `.env.example` documents every variable. `CLAUDE.md` says never read or print `.env` files, and a saved key must never be shown again.
- **Model routing** (which slot each agent role uses) lives in `app/llm/routing.yaml`, separate from `.env`; the model IDs and prices are in `.env`.
- **Word files are made from scratch today** (`app/deploy/docx_writer.py`, `markdown_to_docx`): `Document()` with python-docx's blank default styles, then the Markdown is written into it. Four routes use it: the download of the deployment plan, release notes, runbook and hypercare plan, and the one-page report of the Deploy verification and the Handover sign-off. **A template is therefore a different starting document**, not a new writer. python-docx can open an existing .docx and keep its styles, page size, margins, headers and footers (a .dotx needs its content type rewritten in memory first; the build will prove that with a test).
- **File upload already exists** for project documents (`POST /projects/{id}/documents`, `app/context/extract.py`), including a check that a file really is a Word document whatever its name says. Templates can reuse that check but must be stored as the original bytes, not as extracted text.
- **The action trail already records who did what** (`human:<name>`), so roles can be checked against it.

## Where Configuration lives (decided 2026-11-05, the user's words: "at the bottom of this box and only visible on the Setup screen")
A **Configuration** entry at the bottom of the phase rail (below Traceability and Build Verify, in `PhaseRail.tsx`), **shown only while the Setup phase is selected**. It opens one Configuration page with three tabs: **Users and roles** (Part A), **System settings** (Part B) and **Templates** (Part C). New route `#/projects/<id>/configuration`. Note: Users and System settings are global to the app, Templates belong to the project; the page says which is which. The rail link is hidden on every other phase; the page itself stays reachable by its address.

## Part A · Users and roles

**ANSWERED 2026-11-05 (the user started Part A and chose):** Q2 the first Administrator is **seeded from `backend/.env`** (`ADMIN_NAME=...`, created at start-up if missing; the app never reads or prints `.env` itself beyond that one setting); Q4 roles restrict **only approve and reject**; Q11 roles are **global**; a typed name that is **not on the Users list can still use the app but cannot approve** (a plain sentence tells them to ask an Administrator). Rail placement: see "Where Configuration lives" above.
**My additions, to be confirmed when you try it:** the seeded administrator gets **every role** (so you can still approve your existing projects at once; take roles away on the Users screen to test); and **until at least one user exists, approval is not restricted**, so a missing `ADMIN_NAME` can never lock you out (the Users page says "no users yet, add ADMIN_NAME to .env").

### Proposed design
- **A user** has a name (the same name used in `X-Actor` today) and a set of **roles**. A user can hold several roles at once.
- **A role** is a short name from a fixed, editable list. The list of roles and the users are kept in the database (a new append-only-friendly table pair: `users`, `user_roles`), edited on a **Users** screen.
- **Who may approve what** is a rule per phase: "this phase can be approved by anyone holding one of these roles". Stored as configuration (a small table `phase_approvers`: phase, role), with defaults taken from the current definition files, so nothing changes until a person changes it.
- **What is checked:** approving (and rejecting) a phase requires the acting user to hold an allowed role. The refusal is a plain sentence naming the role needed ("Requirements can be approved by an architect; Ann holds project manager"). Starting or running a phase, editing and reviewing stay open to any named user, as today, unless the user wants those restricted too (Question 4).
- **Recorded:** the approval record already holds the actor; it will also hold the role used to approve ("approved as architect").
- **Sign-in:** see Question 1. The smallest honest version keeps today's name entry but **checks it against the users list**, and says plainly that a name is not a password.

### Slices
| Slice | Delivers |
|---|---|
| **23a** | Users and roles in the database (schema v11), service, routes; default roles and the default approver per phase; nothing enforced yet |
| **23b** | The approval check on approve and reject, the plain refusal sentence, the role recorded in the approval record; the page greys out the Approve button and says who can |
| **23c** | The Users screen: add a user, give and take roles, set which roles approve which phase; a "who am I" chip in the header |

## Part B · System configuration

**ANSWERED 2026-11-05 ("all defaults"):** Q5 saved **into `backend/.env`** (backup first, comments kept); Q6 **Administrators only** (Part A exists); Q7 a **"restart the app" message only**, no Restart button; Q8 secrets show **only "set" / "not set"**, never the value, even to an Administrator; Q9 A before B (done); Q10 existing projects untouched. Model routing (`routing.yaml`) is a second tab (23f).
**Found while designing (2026-11-05):** (1) git ignores only a file named exactly `.env`, so a `.env.bak` beside it would be COMMITTED with the keys in it. **Backups go to `backend/data/env-backups/`** (already git-ignored; owner-only permissions; the last 10 kept). (2) `start.sh` runs uvicorn with `--reload`, which watches `.py` files only, so a changed `.env` really does need a restart. (3) `secret_values()` already treats the **endpoint, both API keys and the user-agent string** as secrets, so those four are write-only and never echoed. (4) Validation uses **the app's own `Settings` class** on the candidate file, so the limits are exactly the ones the app enforces, and a pydantic error is reported by field name and message only (its `input` is dropped, since it could echo a secret). (5) The app is only given a settings-file path when it starts from the real `.env`; an app built in a test gets none, so **a test can never write to your `.env`**.
**Built in two slices now:** 23d (the catalogue and the read-only screen) and 23e (saving). 23f (model routing) follows.

### Proposed design
- **A Configuration screen** that shows every setting in groups: Mode and recordings; Model slots (model ID, fallback, price in, price out, for sonnet, haiku, openai and gemini); Limits and budget (run budget, run cost cap, time cap, concurrency, output limits, repairs); Documents (size and page limits); Sandbox; Build; Advanced.
- **Each setting is checked as the app checks it today** (the same limits and types from `app/config.py`), so a bad value is refused with a plain sentence before it is saved.
- **Secrets** (`IBM_ICA_API_KEY`, `IBM_ICA_OPENAI_API_KEY`, the endpoint): the screen shows only **"set" or "not set"**, never the value. A new value can be typed and saved; it is never read back, logged or put in the audit trail. Leaving the box blank keeps the current value.
- **Saving** writes the values and then shows a clear message: **"Saved. Restart the app for this to take effect."** The running app keeps using the old values until restarted (the app reads settings once, so this is honest and simple). The screen also shows **"changes waiting for a restart"** until the app has restarted.
- **Where the values are saved** (Question 5): the smallest answer is to write them into `backend/.env` itself, keeping its comments, so the file stays the one source of truth and the app and `start.sh` need no new loading code. The alternative is a separate settings file or a database table that overrides `.env`.
- **Safety:** a backup of the previous `.env` is kept (`.env.bak`, gitignored) before each save; only known setting names can be written; the audit trail records who changed which setting NAME (never the value of a secret; for other settings the old and new value).
- **Model routing** (`routing.yaml`: which slot each role uses) is offered as a second tab, because the user listed "the model names" and this is where "who uses which model" lives. Same save-and-restart rule.

### Slices
| Slice | Delivers |
|---|---|
| **23d** | The settings catalogue (name, group, type, limits, secret or not, restart needed) read from the one place `config.py` already defines them; a read-only Configuration screen showing "set / not set" and current non-secret values |
| **23e** | Saving: validation, the `.env` writer with backup, the audit row, the restart message and the "changes waiting" banner; secrets write-only |
| **23f** | Model routing tab (role to slot), and a "what did I change" view from the audit trail |

## Questions for the user (answer tomorrow; the bold one is my default)
1. **ANSWERED: (a).** *Local use only, so no password and no sign-in page; a typed name that must be on the Users list.* **How real are users?** (a) **Keep "type your name", but only names on the Users list can approve** (honest label, not security); (b) a simple password per user, stored hashed, with a sign-in page; (c) integrate a real sign-in later. *Roles are only as strong as this answer. (a) is quick and fits a prototype; (b) is a real step up and adds a login page, a session and password handling.*
2. **First user.** Who is the first administrator who can add users? **The first name typed on a fresh database becomes the administrator**, or the Users list is seeded from a line in `.env`.
3. **ANSWERED: accepted as suggested.** **Role names.** Use your words: **Project Manager, Architect, Business Engineer (kept as "approver" for Setup-Design), Technical Lead, Deployment Engineer, BAU Lead, Administrator**? Or a smaller list. And the default approver per phase: Setup, Requirements, Design = **Architect** (as you described); Architecture = Technical Lead; Build = Technical Lead; Deploy = Deployment Engineer; BAU handover = BAU Lead.
4. **What else is role-restricted?** **Only approve and reject for now**; starting a run, editing, reviewing and the Deploy/Handover checklists stay open to any named user. Or also: only a Project Manager may start a phase; only the person holding the role may answer a checklist.
5. **Where settings are saved.** **Into `backend/.env`** (with a backup and comments kept); or a separate file; or the database overriding `.env`.
6. **Who may change system configuration?** **Administrators only** (needs Part A first); or anyone with a name, as today.
7. **Restart.** **A message only** ("Restart the app"), as you asked. Optionally later: a Restart button that works with `start.sh`.
8. **Does the admin see secrets?** **No: set / not set only**, never the value, even to an administrator.
9. **Build order.** **A before B** (roles first, then configuration, since B's "who may change" depends on A), or B first because it is simpler.
10. **Existing projects.** Approvals already given stay as they are, with the person recorded then; roles apply from now on. **Yes.**

## Part C · Document templates

**ANSWERED 2026-11-05 (the user's numbering ran one ahead of the questions; mapped here):** per project only; "deployment notes" = the Deployment plan; `.docx` only; placeholders removed, **the Table of Contents is the one thing that matters, and with no ToC the existing layout is used**; a new upload **overwrites** (no versions); **Project Manager** uploads and changes templates. **Q15 confirmed: option 1 ("that's right"; the user added: the template supplies the look and feel, and the content layout is based on the ToC).**

### Design (as answered)
- **A Templates panel on the project page.** For each category: upload a `.docx`, see its name, size, who uploaded it and when, download the original, download a sample made with it, remove it. **One template per category per project.** A new upload for the same category **replaces** the old one; the audit trail records who replaced what (name and size, not the file).
- **Categories:** Deployment plan, Release notes, Runbook, Hypercare plan, Deployment verification report, Handover sign-off report. (A project may also keep an "Any document" template used when its category has none; this was in my first draft and nobody objected, so it stays unless you say otherwise.) No all-projects default: templates belong to a project.
- **Only `.docx`.** `.dotx`, `.docm` and `.dotm` are refused; the file must really be a Word package; 5 MB limit; macros, embedded objects and external links are refused or removed, and the safe copy is what is used. A template is only read for its look, never run.
- **What the Word download does:** it looks for the project's template for that category.
  - **The template has a Table of Contents:** the document is built on the template, so its styles, page setup, cover page, header and footer carry over, and our content is written after the template's ToC. The ToC is filled from our headings.
  - **The template has no Table of Contents** (or there is no template): **today's layout, unchanged.** The upload screen says so plainly: "No table of contents was found in this file, so downloads will use the standard layout."
- **No placeholders, no `{{content}}`, no fields.** Simpler than my first draft.
- **The download says what it used**: "using the project's Release notes template", or "standard layout".
- **A Word file still never holds anything the Markdown does not.**

### Q15 · CONFIRMED (option 1)
The user confirmed this reading of "only the Table of Contents is important", saying the template supplies the look and feel and the content layout is based on the ToC:
1. **CONFIRMED. A template is used only when it contains a Table of Contents.** Everything in the template up to and including its ToC is kept (cover page, header, footer, styles, page setup); anything after the ToC is dropped; our document follows the ToC. **(my default)**
2. A template always supplies its styles, page and header/footer, and the ToC is one extra that we make sure works; with no ToC in it we add one / or use our layout.
3. Something else.

### Things to know about a Table of Contents in Word
- **A ToC is a field that Word fills in.** The server cannot know page numbers, so the ToC shows after **Word updates fields**. To make it useful at once, the build pre-fills the ToC with the list of headings (no page numbers), so any viewer shows something, and Word can refresh it with page numbers (it may ask "update fields?" on first open; the build sets that up on purpose).
- **Finding the ToC in the template.** Word has two kinds (a field, or a built-in content block). The build recognises both, and a test uses a real ToC from Word.

### Slices
| Slice | Delivers |
|---|---|
| **23g** | Storage (next schema version), upload with the safety checks, one template per category per project, replace, remove, download original, ToC detection and the plain message; routes. Nothing uses a template yet |
| **23h** | The writer builds on the template when it has a ToC, fills the ToC, keeps everything up to it, drops what follows; the six download routes choose a template and say which; no template or no ToC = exactly today's file |
| **23i** | The Templates panel on the project page: upload, list, sample, remove, the plain messages; shown to the Project Manager once Part A exists, to anyone with a name until then |

### Risks specific to templates
- **Real templates are messier than test ones.** Cover pages with text boxes, content controls and unusual styles may not carry over. **Please bring one or two real templates**; I will test with them and say plainly what carries over and what does not.
- **A template can make a document look wrong** (a heading style set to white text on white). The sample download on upload is there to catch that.
- **A missing style does not break a download.** If the template lacks a style the writer needs ("List Bullet", "Table Grid"), the built-in one is added and the panel says which.
- **Word downloads only.** Not PDF, not Markdown.

## Out of scope for now
Single sign-on or a real identity provider; templates for PDF or Markdown; editing a template inside the app; templates for the Build instruction files; password reset by email; per-project roles (a role is global in this plan, see Question 11 below); approving by two people; changing settings without a restart; a Restart button; editing `routing.yaml` outside the screen.

**Question 11 (worth a thought tonight):** should a role be **global** (an architect can approve anywhere) or **per project** (an architect on project A only)? **Default: global**, which is simpler and matches "users and roles assigned to them". Per-project roles are a later addition.

## Risks I want you to know about
- **A name is not an identity.** With option (a), anyone can type another person's name. The check stops mistakes, not misuse. The screen must say so, and the audit trail still shows who was typed.
- **Writing `.env` from the app is the sensitive part.** It is the one file that holds keys. Hence: known names only, secrets write-only, backup before save, no logging of values, and tests that prove no secret ever reaches a response or a log.
- **A bad model ID or price can break every run.** The screen should validate types and ranges, and offer "restore the previous file" from the backup.
- **Locking yourself out:** an administrator must always exist; the last administrator cannot be removed.

## Tests (to write with the build)
| Area | Proves |
|---|---|
| roles | a user can hold several roles; a role can be given and taken away; the last administrator cannot be removed; an unknown role is refused |
| approval | a user without an allowed role cannot approve or reject, and the sentence names the role needed; one with any allowed role can; the role used is recorded; a person not on the list is refused; nothing else is restricted |
| defaults | with no configuration the approver per phase is the one in the definition files; existing approvals are untouched |
| settings catalogue | every setting in `config.py` is in the catalogue with its limits and a secret flag; none is missing or invented |
| saving | a valid change is written to `.env` with comments kept and a backup made; an invalid one is refused and nothing is written; an unknown name is refused; blank secret keeps the old value |
| secrets | no response, log, audit row or backup listing ever contains a secret value; the screen shows only set or not set |
| restart | after a save the response says to restart; the banner shows until the app restarts |
| page | the Users screen and Configuration screen render from the server's data; the Approve button is disabled with the reason when the user lacks the role |
| unchanged | every phase, the audit trail, `export_contract --check`; tests never touch the real `.env` or `backend/data` |
| templates: upload | only `.docx` is accepted; `.dotx`, macro files, a file that is not really a Word package, an oversize file and an unknown category are refused with a plain sentence; the original bytes are kept; a second upload for the same category replaces the first; removing works; one project's templates are never visible to another; only the Project Manager may upload once Part A exists |
| templates: use | a template with a ToC (field form and content-block form) is built on: styles, page, header/footer and the cover part are kept, what follows the ToC is dropped, our content follows, the ToC lists our headings; a template with no ToC, or no template, gives exactly today's file; a template missing a style still produces a file and the panel says which style was added |
| templates: choice | the project's template for the category is used; else the project's "Any document" template; else the standard layout; the download names which it used |
| templates: safety | the Word file made with a template holds nothing the Markdown does not; macros and embedded objects in the template do not reach the output; the response names the template used |
| break-one-thing | a mutants file per slice with the baseline guard |

## Manual check for the user (after the build)
Add two users with different roles; try to approve Requirements as the wrong one and read the sentence; approve as the right one and see the role in the record. Open Configuration, change a price and the run budget, save, read the restart message, restart with `start.sh`, and see the new value. Confirm a key is never shown. For templates: upload your own template as the release notes template, download a sample, then download a real release notes document as Word and compare the look with your template; try a document category with no template and see the plain layout.

## Done when
- [ ] Questions answered
- [ ] Listed tests pass; full suites green
- [ ] Break-one-thing check run and reported honestly
- [ ] PROGRESS.md and RESUME.md updated
- [ ] **You have tried both parts in the UI and told me what you saw**
- [ ] User confirms
