# S05 · Workflow engine

**Milestone:** M2 (first step)  **Size:** M  **Objectives:** O1, O6, O11  **Depends on:** S01
No model calls in this step. It is pure logic plus a few YAML files, so it is fully testable offline.

## Goal
Define **what the lifecycle is** and enforce **the order it may happen in**.

1. A catalogue of phases and artefacts, written as YAML files you can read and edit (objective O11: adding an artefact is a YAML edit, not a Python change).
2. A project's **plan**: which of those artefacts the wizard turned on.
3. A **state machine** that decides what a phase may do next, enforced where the status is written, so no later code can skip a gate.
4. **Waves**: which artefacts of a phase can be generated in parallel and which must wait for another (this is what S09 will execute).

## Decisions I need from you (the catalogue is yours to shape)
The deck only details Requirements → Design → Architecture → Code & Test. **Deploy and BAU Handover are my design**, and the artefact lists below are my proposal. Reading them takes two minutes and changes what the whole demo produces. Edit anything.

| Phase | Key | Artefacts (required ones in **bold**) |
|---|---|---|
| 0 Setup | `setup` | **Project charter** |
| 1 Requirements | `requirements` | **Personas · Problem statement · Vision & objectives · Functional requirements · Non-functional requirements · Epics & features** · User stories |
| 2 Design | `design` | **User journey · Low-fidelity wireframes** · High-fidelity wireframes |
| 3 Architecture | `architecture` | **Component overview · High-level design · Low-level design** · Flow diagram · Use-case diagram |
| 4 Build & Test | `build` | **Database schema · Backend code · Frontend code · Test suite** · Test report · Code and security review |
| 5 Deploy | `deploy` | **Deployment plan · Infrastructure as code · Release notes** · CI/CD pipeline · Deployment verification |
| 6 BAU Handover | `handover` | **Runbook · Support guide** · SLOs and alerts · Knowledge-transfer pack · Hypercare plan · Handover sign-off |

That is 33 artefacts: 7 phases, **21 of them required** (the demo path needs them; the rest are switchable in the wizard). "Required" means the wizard cannot turn them off.

Questions on the catalogue:
1. Is Setup a real phase with one artefact (a charter), or just project creation? I made it a phase because the deck shows "Phase 0: Setup" with an approval chip, and it gives the first gate to show.
2. Anything missing that you'd expect a client to ask for (e.g. a security threat model, a data-migration plan, a test strategy)? Each is one small YAML block to add later.
3. Is it right that **Handover sign-off** is an artefact (a document a human approves), rather than only the phase gate? I think yes: the sign-off then has a version history and an author like everything else.

## In scope
- `backend/app/phases/definitions/*.yaml`: one file per phase, loaded and **strictly validated** (a typo is an error with the file and line context, never silently ignored).
- `workflow/definitions.py` (loader + models), `workflow/plan.py` (selection → plan → waves), `workflow/engine.py` (transitions, prerequisites, gates), `workflow/gates.py` (gate checks).
- Legal-transition enforcement inside `PhaseRepo` (S01), plus a `reopen` for approved phases.
- A wizard-style `selection` format, validated against the catalogue.
- `scripts/workflow_walkthrough.py`: walks a project through all seven phases offline and prints the table.
- Docs: the catalogue goes into `docs/08-workflow-catalogue.md` so it can be reviewed without reading YAML.
- Status: `/api/status` gets a `workflow` block; the page gets a small catalogue table.

## Out of scope (later steps)
- Running agents or generating anything (S07, S09). Reviewer findings and rejection reruns (S08).
- The "artefact is approved" concept per artefact: S05 tracks **phase** gates; per-artefact approval is S08.
- Skills and output schemas, ID-prefix numbering rules per artefact beyond naming the prefix (S07, S11).
- The wizard UI (S12).

## Design

### A phase file
```yaml
key: requirements
order: 1
name: Requirements
summary: Capture who the product is for and what it must do.
approver: business engineer
artefacts:
  - key: personas
    name: Personas
    id_prefix: REQ-PER
    role: requirements_analyst        # must exist in routing.yaml (checked)
    required: true
    description: Who uses the product, and what they need.
    after: []                         # artefacts of this phase that must exist first
  - key: functional_requirements
    id_prefix: REQ-F
    role: requirements_analyst
    required: true
    after: [personas, problem_statement]
```
- `order` makes the lifecycle sequence explicit (no reliance on file names). Orders must be unique and run 0 to 6 with no gaps.
- `role` ties each artefact to an agent role from `routing.yaml`; the loader fails if the role doesn't exist, so the catalogue and the routing can't drift apart. Several artefacts share one role.
- `id_prefix` must look like `REQ-F`, be unique across the whole catalogue, and no prefix may be a dash-prefix of another (`REQ` and `REQ-F` would collide in S01's numbering), so every generated ID is unambiguous.
- `after` lists **same-phase** artefacts. It can only reference artefacts that exist, cannot point at itself, and cycles are rejected (with the cycle named).
- Unknown keys anywhere are an error. Duplicate keys are an error. A phase with zero artefacts is an error.

### The plan (from the wizard's selection)
`selection` is stored on the project (S01 already has the column): `{"requirements": ["personas", "epics_features"], "design": null, ...}`. Rules:
- `null`/missing means "the required ones plus the catalogue defaults"; an explicit list means exactly those **plus every required artefact**, which can't be switched off (asking to is an error naming the artefact, not a silent re-add).
- Unknown phase or artefact keys are errors.
- If an enabled artefact has an `after` dependency that was switched off, that dependency is **pulled in automatically** and reported ("`user_stories` needs `epics_features`, which was added"). Silently dropping the dependency would make the plan unrunnable; silently ignoring the request would surprise you; adding and reporting is the least bad option.
- The plan is a plain data object (phases, enabled artefacts, who adds what) with no database access, so it is trivially testable.

### Waves
For each phase, enabled artefacts are layered by `after`: wave 1 has nothing to wait for, wave 2 only waits for wave 1, and so on. Everything inside a wave can run at once (O6). Ordering inside a wave is the catalogue order, so output is deterministic.

### The state machine (enforced in the repo)
```
not_started ──start──▶ running ──finish──▶ awaiting_review ──approve──▶ approved
                          ▲                      │                         │
                          │                      └──reject──▶ rejected     │
                          └────── restart ◀──────────────────┘             │
                          └──────────── reopen (new, from approved) ◀──────┘
```
| From | Allowed next |
|---|---|
| `not_started` | `running` |
| `running` | `awaiting_review`, `not_started` (abandon) |
| `awaiting_review` | `approved`, `rejected`, `running` (human edits trigger a re-run) |
| `rejected` | `running` |
| `approved` | `running` via **reopen** only, which records why and who |

- Today `PhaseRepo.set_status` and `record_decision` accept any move (S01's known gap, noted in the progress log). This step makes **illegal transitions raise `IllegalTransition`** (a new `InvalidInput` subclass, so the S01 callers that catch `InvalidInput` still work). The change is in the repo, so a bug in a future caller cannot approve a phase that never ran.
- **S01 tests that relied on the loose behaviour will change**, and I'll list each one. For example, an S01 test approves a phase straight from `not_started`; that becomes an error. I'd rather break those tests on purpose than keep a back door.
- Approval needs a **person or `system`** (unchanged), and now also needs the phase to be `awaiting_review`.
- `reopen(project, phase, actor, reason)` needs a person (not an agent), a non-blank reason, writes an audit row, and clears the decision so the phase is `running` again. Later phases that were already approved are then shown as `needs_review` (a computed flag, not a stored status); see "Reopen and downstream phases" and decision 4.

### The engine (the rules that span phases)
- **Prerequisite:** a phase can start only when every earlier phase in the plan is `approved` (Setup has none). Phases with no enabled artefacts in the plan are skipped, not blocking.
- **Gate check** before `awaiting_review → approved`: every **required, enabled** artefact of the phase has at least one version. Missing ones are listed by name in the error. A phase that was reviewed with an empty required artefact cannot be waved through.
- **Atomic start:** checking prerequisites and flipping to `running` happen in one transaction, so two simultaneous starts of the same phase give exactly one winner (the other gets a clear error), the same way S01's artefact numbering is race-free.
- `engine.next_action(project)` returns a plain description of where the project is ("Requirements is awaiting review", "Design can start"), which is what the UI's progress bar will use in S12.
- `engine.snapshot(project)` returns the whole picture: every phase with status, decision, enabled artefacts, and per-artefact "has a version / required / blocked by".

### Reopen and downstream phases (decision 4)
If you reopen Requirements after Design is approved, Design was built on content that may now change. Options: (a) leave later phases approved (fast, but the lifecycle lies); (b) mark them `needs_review` so they are visible but not blocked; (c) force them back to `running`. I propose **(b)**: a derived flag in `snapshot` ("Design was approved before Requirements was reopened"), no new database status, no data lost, and the traceability work in S15 can then say exactly which artefacts are affected. It is computed from timestamps already stored, so it costs no migration.

### Where it lives
```
backend/app/phases/definitions/{00-setup,01-requirements,02-design,03-architecture,04-build,05-deploy,06-handover}.yaml
backend/app/workflow/{__init__,definitions,plan,engine,gates}.py
backend/scripts/workflow_walkthrough.py
```
The loader reads the YAML once at startup (`create_app` fails with a clear message if the catalogue is invalid, like `routing.yaml`) and exposes an immutable `Catalogue`.

### `/api/status` and the page
New `workflow` block: phase count, artefact count, required count, per-phase name and artefact counts, and `problems` (empty unless the catalogue is invalid, which would have stopped startup anyway). The page gets a "Lifecycle" table: phase, approver, artefacts (required/optional). Read-only. No project state yet.

### The walkthrough script (offline, free, you run it)
`python -m scripts.workflow_walkthrough` creates a throwaway project, then for each phase: starts it, adds a placeholder version for each required artefact (author `system`-labelled placeholders, no model), finishes, approves as `human:demo`, and prints a table of phase, status, artefacts and the next action. It then **tries three illegal things and prints the refusals**: starting Design before Requirements is approved, approving a phase that was never run, and approving with a missing required artefact. Ends with `7/7 phases approved, 3/3 refusals correct`. No network, no key, no cost.

## Tests (must pass before the step is done)

| Area | Proves |
|---|---|
| shipped catalogue | all seven files load; orders 0 to 6; 7 phases, 33 artefacts, 21 required; every role exists in `routing.yaml`; every prefix unique and no prefix is a dash-prefix of another; every `after` is in-phase and acyclic; every phase has at least one required artefact |
| loader errors | one test per rule: unknown key, duplicate artefact key, duplicate prefix, bad prefix shape, prefix-collision (`REQ` vs `REQ-F`), missing required field, `after` to a missing artefact, self-dependency, a cycle (named), unknown role, duplicate or missing order, empty phase, non-mapping file, invalid YAML. Each error names the file and the artefact, and none echoes unrelated content |
| plan | default plan; explicit selection; required artefacts always included and asking to switch one off is an error; unknown phase and artefact keys rejected; auto-pulled dependencies are reported; empty phase after selection is impossible (required artefacts remain); a selection survives a JSON round trip through the project column |
| waves | no-dependency artefacts are wave 1; chains layer correctly; diamond dependencies; catalogue order inside a wave; **switching an artefact off changes the waves**; every enabled artefact appears exactly once; no artefact appears before its dependencies |
| transitions | every row of the table, both allowed and refused, parametrised over all 5x5 pairs; refusal message names current and requested status; `IllegalTransition` is an `InvalidInput`; refused moves write no audit row and change nothing |
| decisions | approve only from `awaiting_review`; reject only from `awaiting_review`; agents still refused; rejection still needs feedback; rejected → running clears the old decision (S01 behaviour kept) |
| reopen | only from `approved`; needs a person; needs a reason; audited with the reason; clears the decision; later approved phases show `needs_review` in the snapshot; earlier phases don't |
| prerequisites | cannot start phase N before N−1 approved; skipped (empty) phases don't block; Setup starts freely; the error names the blocking phase |
| gate check | approval blocked until every required enabled artefact has a version; error lists the missing ones; optional artefacts never block; a switched-off optional artefact never blocks |
| atomicity | 10 simultaneous starts of one phase: exactly one succeeds, nine get the clear error, one `phase.status` audit row; start racing a status read never shows a half state |
| snapshot / next_action | correct for: nothing started, mid-phase, awaiting review, rejected, fully approved, reopened |
| S01 compatibility | every S01 test still passes **except** the ones that depended on the loose rules; each changed test is listed in PROGRESS.md with why |
| status block | shape and counts; an invalid catalogue stops `create_app` with the file named; no paths in the response |
| walkthrough script | runs offline; prints 7/7 and 3/3; refusals are the real error messages; temp database removed; never reads `.env`; exits 1 if any refusal unexpectedly succeeds |

After the suite is green I'll run the same break-one-thing check as before: remove each guard (a cycle check, the transition table, the prerequisite check, the required-artefact gate, the atomic start, the agent-can't-approve rule, "required can't be switched off", dependency pulling) and confirm the suite fails each time.

## Dependencies / installs
None. PyYAML is already in your venv and in `requirements.txt`.

## Manual check for the user (we do not run the app)
1. `! cd .../SDLC-Workbench/backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.workflow_walkthrough` (offline, no key, no cost). Expect the 7-row table and `7/7 phases approved, 3/3 refusals correct`.
2. Open `docs/08-workflow-catalogue.md` and read the 33 artefacts. **This is the review that matters most in this step.** Tell me what to add, rename or demote from required.
3. `./start.sh`, open `http://localhost:5270`: a **Lifecycle** table with 7 rows and the artefact counts.
4. Nothing on the page changes project state.

## Decisions taken (user, 2026-10-27)
"Lets go ahead with the build": the catalogue as proposed (33 artefacts, 21 required) and all five defaults. The user has not yet read `docs/08-workflow-catalogue.md`, so the catalogue itself is built but **not reviewed**.

## What changed from the spec while building
- **Selection semantics tightened.** The spec said required artefacts left out of an explicit list would be added back. I made leaving one out an **error** that names it, because "asked for X, silently got Y" is the thing this step exists to prevent. `null` for a phase still means everything.
- **Optional-needs-optional never happens in the shipped YAML** (every optional artefact depends only on required ones), so "pull in a dependency" is proven on a hand-built chain and a test fails if someone later adds such a dependency to the YAML on purpose.
- **Catalogue document is generated**, not hand-written: `scripts/render_catalogue.py` writes `docs/08-workflow-catalogue.md`, and a test fails when the YAML and the document disagree.
- **Guards:** the repo takes an optional `guard` that runs inside the same transaction as the status change, which is how prerequisites and the approval gate are race-free without the repo knowing about phases.
- **S01 tests changed (4), each on purpose:** `test_approve_is_recorded_with_who_decided`, `test_reject_is_recorded_with_feedback`, `test_the_system_may_decide_for_automated_demo_paths`, `test_rerunning_after_a_rejection_forgets_the_old_decision`. Each jumped a phase straight to `awaiting_review`, `approved` or `rejected` from `not_started`, which is now refused. They now take the legal route (`not_started → running → awaiting_review`). Nothing else in S01 changed.

## Done when
- [x] Listed tests pass; full suite green (`661 passed, 1 deselected`, in PROGRESS.md)
- [x] Break-one-thing check run and reported (see PROGRESS.md for the count)
- [x] Frontend `npm run build` still succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] Walkthrough script run by the user: 7/7 approved, 3/3 refusals correct (2026-10-27)
- [ ] ~~Catalogue reviewed by you~~ **Skipped by the user's choice (2026-10-27): the catalogue is provisional.** Revisit before S11
- [x] Closed on the user's instruction to move on ("treat the current catalogue as provisional")

## Decisions for you (defaults chosen; say if you want any changed)
1. **The catalogue** above, especially which 21 artefacts are required.
2. **Soft ordering:** `after` produces parallel waves inside a phase; a strict one-after-another order would make every phase serial and the demo slow.
3. **Illegal transitions raise errors in the repo,** which will break a few S01 tests on purpose. The alternative is to enforce only in the engine, leaving the back door open.
4. **Reopening an approved phase marks later approved phases `needs_review`** (a computed flag, no new status). Alternatives: leave them alone, or force them back to `running`.
5. **Dependencies the wizard switched off are pulled in and reported,** rather than silently dropped or refused.
