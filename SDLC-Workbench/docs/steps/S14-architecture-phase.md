# S14 · Architecture phase

**Milestone:** M4  **Size:** M as planned, closer to L with decision 1 (so decision 2 splits it)  **Objectives:** O1, O8  **Depends on:** S07, S10, S11, S12, S13 (all closed)
After S13 you can run Setup, Requirements and Design. Architecture, the fourth phase, shows five artefacts and a Run button that fails at once, because none of them has a skill. After S14 **Architecture runs end to end**: an agent turns the approved Requirements into a component overview, high-level design and low-level design, a second agent turns those into a flow diagram and a use-case diagram, and you can *see the diagrams* in the browser. Every component, interface, endpoint and table says which requirement it exists for, so Build (S16 onward) has a list to honour.

## What I found before writing this (it changes the plan)

1. **The five Architecture artefacts have no skill, which is all that is missing on the agent side.** The catalogue already defines them (`ARC-CMP`, `ARC-HLD`, `ARC-LLD`, `ARC-FLW`, `ARC-UCD`), their order (component overview, then high-level design and use-case diagram, then low-level design and flow diagram), and two roles already routed in `routing.yaml`: `solution_architect` → **Sonnet** (the first three) and `diagram_author` → **Haiku** (the two diagrams). The flow and use-case diagrams are optional in the catalogue; the other three are required. So the writing side is five skill files, in the same format as the eleven that exist.
2. **Your upstream does not fit in one Architecture prompt, and the wireframes are the reason.** I measured the latest versions in your Meeting Room Booking project: 80,931 characters in all, against the 24,000-character limit on upstream artefacts in a prompt (nothing is cut silently; over the limit, the run is refused with a sentence). The two wireframe artefacts alone are 35,776. So **Architecture does not read the wireframes**; it reads the requirements (functional 7,651; non-functional 4,883; charter 3,397) and the user journey (3,973), which carry what an architect needs: what the system must do and who does what. Component overview reading the charter and both requirement artefacts is 15,931, which fits with room. The size of the architecture artefacts themselves is not known until they are written; the later skills read them, so that is checked at the first recording.
3. **The plan says "Mermaid/SVG output validates", and neither is free.** Mermaid needs a browser package (large, executes in the page, and cannot be checked on the server: a syntax error appears only when drawn). Model-drawn SVG already has a safe viewer from S13, but the sanitiser's allow-list has **no `marker`, `defs` or `use`**, so an arrowhead must be drawn by hand as a small polygon, and Haiku placing boxes and arrows by coordinate is where drawings go wrong. Decision 1 proposes a third way that avoids both.
4. **Traceability can be checked by the machine here, as it was for Design.** The existing item machinery already does what the plan asks ("every component cites at least one requirement ID"): an item must say what it `Derives from:`, and a skill's `Covers:` line makes the server list any requirement no item serves. S14 uses it; it is not rebuilt.
5. **Build will read the low-level design, so its IDs must be stable.** The plan says the LLD "lists endpoints and tables that Build must honour". Endpoints and tables become items with their own IDs (`API-001`, `TBL-001`); a re-run keeps IDs, as every item artefact does, so a later Build step can cite them.
6. **Architecture is blocked until Design is approved.** The engine already refuses to start a phase whose predecessor is not approved. In your Meeting Room Booking project Design is still *running*, so the first manual check starts with approving it.
7. **Replay will not work for Architecture until you record it.** Same as Requirements and Design: a new recording is needed. A guess for five artefacts on Sonnet and Haiku is **a few tens of cents to about a dollar**, a guess until run (Sonnet costs more per token than the Gemini model Design used).
8. **The review label will say "same family".** Sonnet writes the first three artefacts and Haiku the diagrams; the reviewer is Sonnet, and all three are Anthropic. By the rule S08 computes, that review is "a second look, not an independent one". Nothing is wrong and nothing to build; stated so the label is not a surprise (decision 8 says how to change it).

## Decisions I need from you (defaults chosen; say if you want any changed)

1. **Diagrams are text lists, drawn by the server. (The main decision.)** The diagram author writes Markdown list items, never markup: a flow diagram is components and the calls between them (`- FLOW-001 COMP-001 -> COMP-003: sends the booking request. Derives from: FR-002`); a use-case diagram is actors and the use cases they take part in (`- UC-001 Book a room. Actors: ACT-001, ACT-002. Derives from: FR-002`). The server checks them like any item artefact **and** that every line points at things that exist (a call between two unknown components is refused with a sentence), then **draws them to SVG itself** with a fixed layout, and the artefact reader shows the picture above the text. Why: the model cannot get a layout or an arrowhead wrong because it draws neither; the check is real (unlike Mermaid); it is one implementation in Python, so no TypeScript twin to keep in step; no new package; the drawing goes through the S13 sanitiser and viewer anyway; and you can fix a diagram by editing one line. The cost is that I write the layout (left-to-right layers for the flow; actors beside a column of use cases for the use-case diagram). Layouts are plain: **readable up to about 12 nodes, cramped beyond that**, which the skill enforces (decision 6). Alternatives: **Mermaid** (new package, checked only in the browser, your call if you want its look), or **model-drawn SVG** (no new code, but the arrowhead and layout risks above).
2. **Two slices, as S12 was.** **S14a: the writing side** (component overview, high-level design, low-level design: three skills, their checks, the live run, the manual check). **S14b: the diagrams** (the two diagram skills, the text format and its check, the drawing, the reader change). You see Architecture working after S14a and close each with your yes. Default: two slices.
3. **What each skill reads** (so each fits the 24,000 limit; all checked against your real project):

   | Artefact | Reads |
   |---|---|
   | Component overview | functional requirements, non-functional requirements, charter |
   | High-level design | component overview, non-functional requirements, charter |
   | Low-level design | high-level design, component overview, functional requirements, user journey |
   | Flow diagram | high-level design, component overview |
   | Use-case diagram | component overview, personas, functional requirements |

   Each also gets a short search of the reference documents for limits, rules and constraints. No skill reads the wireframes (finding 2).
4. **Items, IDs and what must be covered.** Component overview: `COMP-001`... , each deriving from at least one `FR`/`NFR`, with `Covers: FR NFR` (a requirement no component serves is listed in a Coverage check with a reason, as the epics skill already does). High-level design: decisions `DEC-001`... and interfaces `IFC-001`..., each citing the components and requirements behind it. Low-level design: `API-001`... (endpoint: method, path, what it does, which component), `TBL-001`... (table: columns, keys, which component owns it), `RUL-001`... (a rule Build must enforce), with `Covers: FR`. Diagrams: as in decision 1; actors derive from `PER`. These prefixes are my proposal; the skill files can still change a name before you see output.
5. **Technology choices are proposals with a reason, not facts.** The high-level design may choose a database, a framework or a hosting style only as a `DEC-` item that says what it is chosen for, what else was considered, and which requirement drives it. If the charter or reference documents already fix a choice, the decision cites that source. Anything the sources leave open is also listed in Open questions. The approver (the technical lead) decides at the gate. The skills do not assume this lab's own stack.
6. **Size caps in the skills.** Components: at most 12. Flow and use-case diagrams: at most 12 nodes each (more components are grouped, or listed in Open questions). Low-level design: at most 20 endpoints and 12 tables; the rest go to Open questions. These are my numbers, chosen so a screen stays readable and a reply stays inside the output limit.
7. **Models and limits as routed.** Sonnet writes the first three, Haiku the diagrams; no change to `routing.yaml`. The output limit stays at the default; I add a per-role limit for `solution_architect` only if the live run shows a cut-off, the way S13 did for Gemini. The $5 run cap stays.
8. **Review stays a button, and the label stays "same family".** Review is never automatic (it costs money). To get an independent label for Architecture, change the reviewer in `routing.yaml` to another family (one line); I would not do it for you. Default: leave as is.
9. **One live check, with a budget.** After building, you run `architecture_demo --live --record <name>` once (or press Run on Architecture in a fresh project) to see whether the models write what the checks accept. **Budget up to $5** (the user raised it from $2 on 2026-10-31: real designs and diagrams are bigger than this sample), my estimate being less, a guess until run. The first S14a run cost about $0.35. If a model's text keeps failing the checks, I will say so and we choose: tighten the skill, switch the role to another model (one line), or accept a rougher result. I will not hide a bad result.

Stated, not asked: all server text stays text; the Run button needs no change; a human edit, a review, request changes, re-run and Reopen all work for Architecture with no new code; no new packages (decision 1 as proposed); the Build phase (S16) and the traceability matrix (S15) are not touched; the flow and use-case diagrams are optional in the catalogue, so a project can skip them and Architecture still approves.

## In scope
- **S14a:** three skills in `backend/app/phases/skills/` (`component_overview.md`, `high_level_design.md`, `low_level_design.md`), each naming exactly the inputs it needs; `scripts/architecture_demo.py` (offline demo with a scripted model, free; `--live --record NAME` for your one real run); the contract fixtures, if a field is added.
- **S14b:** two skills (`flow_diagram.md`, `usecase_diagram.md`); `backend/app/architecture/diagram.py` (parse the lists, check them, lay them out, write SVG); a diagram check wired into `check_body` so an agent's reply and a person's edit both pass it; the artefact detail gains a `rendering` field; the reader shows the picture with the text under it.

## Out of scope (later)
- The traceability matrix and coverage screen (S15); Build, Deploy and Handover (S16 onward); exporting diagrams to PNG or PDF; dragging boxes or editing a diagram visually (you edit the text); sequence, state or entity-relationship diagrams; Mermaid.

## Design notes
- **Where the checks live:** `check_body` already runs the section, citation, item and secret checks (and the S13 drawing check) for both an agent reply and a hand edit. The diagram check is one more step in that function, so the two paths cannot drift.
- **The drawing is derived, never stored:** the body holds only the list. The server draws it when the artefact is read, so an edit or a re-run can never leave a stale picture, and nothing model-written is ever drawn directly.
- **Layout (decision 1):** flow: nodes in layers by distance from the first component, left to right, straight arrows with the label above; use-case: actors in a column on the left, use cases as ellipses in a column inside a labelled system box, a line per actor-to-use-case. Arrowheads are small polygons, so the output uses only elements the S13 allow-list already has.
- **A repair, not a rejection:** a line that points at a component that does not exist is sent back to the model with the sentence, like a bad citation. After the usual three attempts the artefact is not saved.
- **Prompt size:** the figures in finding 2 are for your real project; the LLD's inputs are checked again after the first real recording, because that is when their size is known.

## Tests (must pass before each slice is done)

| Area | Proves |
|---|---|
| skills load | each loads with the existing loader; its inputs exist in the catalogue; `Items:` and `Covers:` lines are valid; the inputs of each fit the upstream limit on the recorded Requirements and Design |
| items and coverage | `COMP-`, `DEC-`, `IFC-`, `API-`, `TBL-`, `RUL-` items parse; `Derives from:` becomes links; a requirement no component serves is listed or refused per the coverage rule; a re-run keeps IDs |
| agent save | a reply with an item that derives from nothing, or cites an ID not provided, is sent back with a sentence; the repaired reply is saved; three bad replies save nothing; a clean reply saves unchanged |
| hand edit | an edit that breaks a rule is refused with every reason and saves nothing; a good one saves; it may cite the upstream items the writer was shown (the S13 follow-up fix) |
| diagram check (S14b) | a call or use case naming something that does not exist is refused with a sentence naming it; a node with no line is allowed but reported; more than 12 nodes is refused; a good list passes |
| drawing (S14b) | the same list always gives the same SVG; every node and every line appears once; arrowheads point at the target; the output passes the S13 sanitiser unchanged and stays under its size limit; an empty or malformed list draws nothing and never raises |
| viewer (S14b) | static render: the picture is shown above the text with its source one click away; a diagram with nothing to draw shows only the text; markup in a label is inert |
| phase end to end | with a scripted model, Setup, Requirements, Design and Architecture run in waves (overview first, then HLD and use-case, then LLD and flow); the phase can be reviewed, sent back, edited, reopened and approved |
| contract | fixtures for an Architecture artefact detail with a rendering; decoders unchanged except where a field is added |
| unchanged | full backend and frontend suites pass; every changed existing test is listed in PROGRESS (the skill counts in older tests will change, as they did for S13) |
| break-one-thing | a mutants file for the diagram parser, check and layout (S14b) and for the new wiring, run with the baseline guard, compile check and hung-suite rule, with timing tests that fail fast; every survivor is a test gap; unkillable breaks are named |
| build | `npm test` and `npm run build` pass |

## Dependencies / installs
None. (Your live Architecture run uses Sonnet and Haiku through ICA: tens of cents to about a dollar. No package is added; the diagram drawing is written by hand on purpose.)

## Questions for the user
Decisions 1 to 9. The ones that most change the work: **1** (text lists drawn by the server, not Mermaid and not model-drawn SVG), **2** (two slices), and **9** (the live check budget).

## Manual check for the user (we do not run the app)
**S14a**
1. Restart the backend. Open your Meeting Room Booking project and **approve Design** if it is not (Architecture is blocked until you do).
2. Open **Architecture**. The five artefacts and a Run button are there.
3. **Run this phase** (live; replay once a recording exists). Watch the rows: component overview first, then high-level design, then low-level design.
4. Open the **Component overview**: each component says which requirement it serves. Open the **Low-level design**: endpoints and tables, each with an ID and a component.
5. **Review** one artefact and **Edit by hand** one line (break a citation on purpose; it must be refused with the reason).
6. Tell me what looks wrong: missing components, invented requirements, endpoints that serve nothing. Look and feel waits.

**S14b**
7. Run the two diagram artefacts. Open the **Flow diagram**: boxes for components, arrows for calls, the list underneath. Open the **Use-case diagram**.
8. Edit one line of a diagram (rename a call, or point it at a component that does not exist). The bad one is refused; the good one redraws.

## Change after the first live run (2026-10-31)
Decision 1 stands (text lists drawn by the server), but the drawing was redone at the user's request: right-angle routing, one line per call-and-reply, numbered lines with a key, two looks (draw.io, Notion), zoom/pan/full-screen viewer. See PROGRESS S14.

## Closed
**S14 closed 2026-10-31 on the user's word.** They ran it live, reviewed it and approved the phase; their own observations are deferred to the review re-look (PROGRESS D15). Nothing else is open on this step.

## Done when (per slice)
**S14a:** built and tested 2026-10-31 (backend 2456, frontend 973, 28 hand breaks of the skills all caught); waiting for the user's live run, browser check and yes. **S14b:** built and tested 2026-10-31 (backend 2554, frontend 985, 53 diagram breaks all caught). The user will verify S14a and S14b together, with a $5 live budget (raised from $2 on 2026-10-31).

- [ ] Listed tests pass; full suite and `npm test` green (summary lines in PROGRESS.md)
- [ ] Break-one-thing check run with the baseline guard and reported honestly
- [ ] `npm run build` succeeds
- [ ] Manual-check list handed over
- [ ] PROGRESS.md updated
- [ ] **You have run it in a browser and told me what you saw**
- [ ] User confirms
