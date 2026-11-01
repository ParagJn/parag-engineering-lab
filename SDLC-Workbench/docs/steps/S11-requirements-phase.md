# S11 · Requirements phase

**Milestone:** M3  **Size:** L  **Objectives:** O1, O2, O8  **Depends on:** S07 (S08 to S10 are skipped for now, see decision 1)
Built and tested offline against the mock provider and replay. One real-model run of the whole phase is required before the step closes.

## Goal
After this step the **whole Requirements phase can be produced by agents**: all 7 artefacts have a skill, and the things inside them (each persona, each requirement, each epic, each story) have **stable IDs that later phases can point at**. That is the foundation for traceability (O8): a design element, a component or a test can say which requirement it serves, down to the single requirement.

Today four of the seven have a skill (personas, problem statement, functional requirements, and the charter in Setup). This step adds vision and objectives, non-functional requirements, epics and features, and user stories, and upgrades the existing three so their contents carry item IDs.

## Decisions I need from you (defaults chosen; say if you want any changed)

1. **Run S11 now, before S08 (reviewer), S09 (parallel run) and S10 (guardrails).** S11 depends only on S07, so it can go first. What you give up while those are missing: nothing reviews the Requirements output, the seven artefacts are generated one after another (a few minutes, not parallel), and no secret/PII scan runs on saves. None of that blocks the work; S08 to S10 stay in the plan, in order, right after S11. The cost of the alternative (doing S08 first) is that the reviewer would be built before there is a phase of real output to review. If you would rather keep the original order, say so and I'll write S08's spec instead.

2. **Item IDs have their own prefixes, not a sub-number of the artefact ID.** The problem from S07: an artefact is `REQ-F-001`, and always `-001`, so it cannot also name the 12th requirement inside it. The scheme I recommend:

   | Inside | Item ID | Example |
   |---|---|---|
   | Personas | `PER-nnn` | `PER-002` |
   | Vision and objectives | `OBJ-nnn` | `OBJ-001` |
   | Functional requirements | `FR-nnn` | `FR-012` |
   | Non-functional requirements | `NFR-nnn` | `NFR-003` |
   | Epics and features | `EPIC-nnn`, `FEAT-nnn` | `FEAT-007` |
   | User stories | `US-nnn` | `US-021` |

   Item IDs have the same shape as artefact IDs, so S01's link checks and the citation reader already accept them: **no change to the database or to link validation**. A test proves no item prefix ever equals an artefact prefix, so the two cannot collide. The alternative (`REQ-F-001.012`) reads as obviously "inside" its artefact but needs changes to S01's ID check, the link table checks and the citation reader, for no extra capability.

3. **IDs are written by the model and checked by the system; they are never silently renumbered.** The model writes each item as `- FR-012 The system shall ...`. The system checks: every ID is well formed and has the right prefix for that artefact, no ID appears twice, and numbers within the artefact are not skipped on a first draft. **On a regeneration**, the model is shown the previous version's IDs and told to keep them for items that survive. An ID that was in the previous version and is now gone must be listed under a closing **Withdrawn items** section with a reason, and a withdrawn ID is never reused. This is what makes the IDs stable enough to hang tests off in S15. The alternative, the system assigning IDs after parsing, breaks the moment a regeneration reorders the list, because old and new items cannot be matched reliably.

4. **"Derived from" references are written in the item and checked.** Each item names what it comes from, on the same line: `- FR-012 The system shall ... Derives from: PER-001, PRB-001`. The check: every ID named must be an item (or artefact) that appears in an **upstream artefact the agent was shown**, the same rule that already stops invented citations. An unknown reference is refused and fed back to the model for repair, like an invented citation today.

5. **Derives-from references are also saved as links in the same transaction.** They go into the existing `links` table (kind `derives`, `declared_in` the artefact). S15 will build the traceability matrix from them. Doing it now costs a few lines and means the data accumulates from the first run. The alternative is parsing the text again in S15, which works but means two readers of one format.

6. **The seven skills, and what each must produce.** The detail is in the table under "Design notes". Epics and features and User stories come from the catalogue's later waves, so they can only run after the earlier ones are approved or at least saved. User stories uses the **backlog splitter role, which routes to Haiku**, because it is a high-volume, well-shaped task; if Haiku cannot hold the format, the repair loop and then the Sonnet fallback apply as always.

7. **Please look at the Requirements part of the catalogue now.** The catalogue is provisional (you chose to move on without reviewing it at S05) and this is the step where each artefact gets its own skill, so changes become expensive from here. The seven are in the table below; the order and "waits for" columns are in `docs/08-workflow-catalogue.md`. Things worth a glance: is **Vision and objectives** wanted as a separate artefact from the problem statement; is **User stories** right as optional; should **Epics and features** be one artefact or two. If you have no view, I keep the seven as they are.

   | Artefact | Required | Waits for |
   |---|---|---|
   | Personas | yes | nothing |
   | Problem statement | yes | nothing |
   | Vision and objectives | yes | Problem statement |
   | Functional requirements | yes | Personas, Problem statement |
   | Non-functional requirements | yes | Problem statement |
   | Epics and features | yes | Functional and Non-functional requirements |
   | User stories | no | Epics and features |

8. **A real-model run of the whole phase before the step closes.** `python -m scripts.requirements_demo --live` runs all seven in order for the Meeting Room Booking sample and prints a one-line result for each plus the full text of two of them. It makes about 8 to 12 real calls (more if the repair loop fires), which I expect to cost well under a dollar; the script prints the actual total. You run it. The same run is **recorded** so that later steps and the demo can replay the whole phase with no network. The offline version of the script (the default) uses a scripted fake model, labelled as such, exactly like `agent_demo`.

## In scope
- Four new skill files: `vision_objectives`, `non_functional_requirements`, `epics_features`, `user_stories`.
- Upgrade `personas`, `problem_statement` and `functional_requirements` so items carry IDs and `Derives from`. (`problem_statement` has no list items, so it only gains a short rule that it is cited by artefact ID.)
- An **item reader** (`backend/app/agents/items.py`): finds items in a body, checks prefix, uniqueness, numbering, derives-from, withdrawn items.
- Skills declare their item prefix and whether items are required; the linter checks it (new optional skill field `Items:`).
- Runtime: shows the model the previous version's item IDs on a regeneration; extends the allowed-reference set with item IDs found in upstream artefacts; runs the item checks inside the existing repair loop; saves derives-from links in the same transaction as the version.
- `scripts/requirements_demo.py` (offline scripted by default, `--live` for the real run, `--record SET` to record it).
- Updated `scripts/skills_report.py` (7 of 33 on the Requirements phase; counts overall).
- Docs: this spec, the PROGRESS row, the catalogue note if decision 7 changes anything.

## Out of scope (later steps)
- Reviewing the output (S08), running the seven in parallel (S09), scanning for secrets (S10).
- The traceability matrix and coverage gaps (S15). S11 only stores the links.
- Any screen. The page does not change.
- Skills for Design and later phases (S13 onward).
- Judging whether a requirement is *good*. The system checks shape and references; a human or the S08 reviewer judges content.

## Design notes

**Item format.** One item per list line, ID first, `Derives from:` last, nothing else required:

```
- FR-012 The system shall refuse a booking longer than four hours. Serves PER-001. Derives from: PER-001, PRB-001 [DOC-001#1]
```

The reader finds an item as a list line (`-` or `1.`) whose first token is an ID with the artefact's declared prefix. Text after the ID is free. `Derives from:` takes a comma-separated list of IDs, to the end of the line or the next sentence marker. Citations in square brackets keep working as in S07 and are separate from derives-from.

**Checks (all run inside the existing repair loop, errors fed back in plain words):**

| Check | Message to the model (shape) |
|---|---|
| An item uses a prefix other than the artefact's | "FR-012 is in Non-functional requirements; use NFR-… here" |
| The same ID twice | "FR-004 appears twice; each requirement needs its own ID" |
| A first draft skips numbers | "FR-003 is missing between FR-002 and FR-004" |
| A derives-from ID was never shown | "FR-012 derives from PER-009, which is not in the material you were given" |
| A previous ID vanished without being withdrawn | "FR-007 was in the previous version and is gone; keep it, or list it under Withdrawn items with a reason" |
| A withdrawn ID is reused | "FR-007 was withdrawn and cannot be used again" |
| An item that is required has no items | "Functional requirements has no numbered requirements" |

**Per-artefact skill content.**

| Artefact | Items | Must contain (section headings) | Reads |
|---|---|---|---|
| Personas | `PER` | Overview, Personas, How the personas differ | charter |
| Problem statement | none | The problem, Who is affected, Impact today, Why it matters now, Evidence and assumptions | charter |
| Vision and objectives | `OBJ` | Vision, Objectives, Measures, Out of vision, Open questions | charter, problem statement |
| Functional requirements | `FR` | Overview, Requirements, Business rules, Traceability notes, Open questions, Withdrawn items | charter, personas, problem statement |
| Non-functional requirements | `NFR` | Overview, Requirements, Quality targets, Open questions, Withdrawn items | charter, problem statement |
| Epics and features | `EPIC`, `FEAT` | Overview, Epics, Features, Coverage check, Withdrawn items | FR, NFR, personas |
| User stories | `US` | Overview, Stories, Coverage check, Withdrawn items | epics and features, FR |

**Coverage check** (epics, stories): the model lists any upstream requirement it did not cover. The system also computes this itself and refuses if the model's list disagrees with it, so "every requirement is in some epic" is checked, not claimed.

**Schema.** No new tables or columns. Links use the existing `links` table; the generation record (v4) gains an `items` list (IDs found) so a version says what it contains without re-parsing.

**Withdrawn items section** is only required once a previous version exists; the first draft may omit it, so a first draft is not forced to say "none".

**Settings.** None new. `AGENT_MAX_REPAIRS` (2) applies; item-check failures use the same repairs, so a model that cannot keep IDs straight fails with a clear reason after three attempts.

**Untouched by design.** The artefact IDs (`REQ-F-001`), the citation rules for documents and memory, and the immutability guard are unchanged.

## Tests (must pass before the step is done)

| Area | Proves |
|---|---|
| item reader | finds items in `-` and `1.` lists; ignores IDs in prose, in code fences and in citations; reads `Derives from:` lists with commas, spaces and trailing full stops; one test per rule in the table above; messages name the ID |
| prefixes | no item prefix equals any catalogue artefact prefix; every item ID is accepted by the existing ID check and by the link table; artefact IDs are still allocated as before |
| skills | the 7 Requirements skills load; each names its item prefix; the linter refuses a skill that declares an item prefix colliding with an artefact prefix, or declares items on an artefact the catalogue says has none; `skills_report` shows 7 of 7 for Requirements |
| runtime | a first draft with correct IDs saves; wrong prefix, duplicates, a gap and an unknown derives-from each trigger a repair and the fixed reply saves; three bad replies fail with all reasons and save nothing |
| regeneration | the prompt carries the previous version's IDs; keeping them passes; dropping one without withdrawing is refused; withdrawing it passes; reusing a withdrawn ID is refused |
| links | derives-from references are saved as `derives` links declared in the artefact, in the same transaction as the version; a failed save leaves no links; a regeneration does not duplicate links |
| coverage | the system's own list of uncovered requirements is compared with the model's; a disagreement is refused |
| phase chain | the seven run in catalogue order against the scripted model; each sees only its declared upstream artefacts; a later artefact cannot cite an item the earlier one does not contain |
| replay | a recorded phase run replays byte-identically with a new project ID and makes zero network calls |
| script | `requirements_demo` offline prints seven results, says it is scripted, exits 0; `--live` refuses without credentials and names which; never prints a key or the endpoint |
| unchanged | the whole existing suite still passes; changed existing tests are listed in PROGRESS |
| break-one-thing | a new mutants file for S11, run with the baseline guard; every survivor is a test gap to fix, reported with the count and the spread |

## Dependencies / installs
None.

## Questions for the user
Decisions 1 to 8 above. The two that most change the work are **1** (skipping S08 to S10 for now) and **2** (the item-ID scheme). Decision 7 asks for a short look at the catalogue's Requirements part.

## Manual check for the user (we do not run the app)
1. `python -m scripts.requirements_demo`: **eight** artefacts saved (the charter plus the seven), ends with `8/8 artefacts saved, 14 items, 24 links` and `1 coverage gap caught and repaired`, under a banner that says it is a scripted fake model.
2. `python -m scripts.skills_report`: the Requirements phase shows all seven with a skill; `8 of 33 artefacts have a skill; 14 required artefacts still need one`.
3. Open `backend/app/phases/skills/non_functional_requirements.md` and `user_stories.md`. **Tell me if the Method and Never read the way you want an analyst briefed**; it is the tone for the other phases.
4. `python -m scripts.requirements_demo --live --record phase1` (costs well under a dollar; prints the real total, and saves the replies so `--replay phase1` can repeat the run free). Read the functional requirements and the user stories it prints: are the IDs sensible, does each requirement name a persona, does anything look invented?
5. The page does not change; the schema pill still reads v4.

## Done when
- [x] Listed tests pass; full suite green (1211 passed)
- [x] Break-one-thing check run with the baseline guard and reported honestly, including anything skipped (50 of 50 caught, 0 skipped)
- [x] Frontend `npm run build` still succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] **Real-model run of the whole phase done by you and its result recorded** (2026-10-28: 8 of 8 on the first attempt, $0.20570; findings in the PROGRESS row)
- [x] User confirms (2026-10-28)

## Outcome
All eight decisions at their defaults. After the real-model run one "Never" line was added to `non_functional_requirements.md` (no quality that no source mentions); it has not been re-run live. Known limits accepted: derives-from is checked for being a shown ID, not for supporting the claim; a few requirements state as "shall" a rule the sources leave open; little headroom against the upstream and output limits.
