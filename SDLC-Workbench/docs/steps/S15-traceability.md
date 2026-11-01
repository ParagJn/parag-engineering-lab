# S15 · Traceability

**Milestone:** M4  **Size:** M  **Objectives:** O8  **Depends on:** S07, S11, S13, S14 (all closed)
Plan test (`05-build-plan.md`): *links parsed correctly; the gap detector flags an uncovered requirement; orphan detection.*
After S14 you can take a project from Setup to Architecture, and every artefact says what it derives from. After S15 **you can see the whole chain at once**: pick a requirement and see the persona it serves, the story, the screens, the components, the endpoints and tables built for it; and see **what is missing**: a requirement nothing was built for, a component no requirement asks for, a screen that shows no journey step. The server computes this from the links; no model is asked, and none can claim coverage.

## What I found before writing this (it changes the plan)

1. **The links already exist and are trustworthy; S15 reads them, it does not create them.** Every artefact version saved by an agent or a person already writes its `Derives from:` lines into the `links` table, and replaces that artefact's old links when a new version is saved. I checked your real Meeting Room Booking project: **688 links, all of kind `derives`, none stale** (every link's source is an item in the latest text of its artefact, every target is an item or an artefact that exists). So the matrix can be computed from the table as it is, with no parsing step and no new column.
2. **The chain is already there, in layers.** Counting your links by what points at what: `FR → PER`, `FEAT → FR`, `US → FEAT`, `JS → FR/FEAT`, `LFS → JS`, `HFS → LFS`, `COMP → FR/NFR`, `IFC → COMP`, `DEC → COMP/NFR`, `API/TBL/RUL → FR/COMP/IFC`, `FLOW → IFC/COMP`, `UC → PER/FR`. The direction is always *later thing → earlier thing it derives from*. That is a graph with no loops, and it is the traceability graph.
3. **There are 18 kinds of item today and the later phases will add more** (code, tests, release items; Build starts in S17). So the matrix must not hard-code a list of kinds. It reads each item's kind from its ID prefix, and what *should* be covered comes from the skills' own `Covers:` lines (the rule each artefact already follows, e.g. components cover FR and NFR, flow covers IFC). That means a new phase brings its own rules by shipping a skill, with no change to S15.
4. **"Uncovered" has two honest meanings and I will not blur them.** (a) *Silent gap*: nothing derives from the item and nothing says why. (b) *Declared gap*: the artefact's own Coverage check lists it with a reason (the writer admitted it). The server already enforces (a) at write time for `Covers:` items, so on a project written by the agents today (a) should be rare; what S15 adds is showing (b) as a visible list the approver can act on, and catching (a) that appears *later*, when a person edits an artefact or an upstream item is added or withdrawn after a downstream one was written.
5. **A withdrawn item is a real case.** An item listed under "Withdrawn items" is no longer current, but things may still point at it. S15 shows those as *pointing at a withdrawn item*: a gap in the other direction.
6. **Orphans exist in this design and have a precise meaning.** An item with **no outgoing link** (it derives from nothing, only possible for a first-layer item such as a persona or charter) is not an orphan: that is where the chain starts. An *orphan* is an item that is **not a first-layer item and has no upstream** (cannot happen for agent text, which the server refuses, but can after a hand edit that the checks allowed, or for a future kind), and an item that **nothing derives from although its kind is normally built on** (a persona no journey step uses; a component no interface mentions). Orphan detection therefore needs one more piece of knowledge: *which kinds are expected to be built on*. That is the `Covers:` lines again, read in the other direction. No new rule is invented.
7. **One screen of data, not one per phase.** The API sketch in `02-architecture.md` already names `GET /projects/{id}/traceability`. One route returns everything the screen needs.

## Decisions (**the user answered 'all defaults' on 2026-10-31, so all nine stand as written**)

1. **What the view is (the main decision).** **A "Traceability" tab on the project page** (next to the phases), with three parts: **(a) Gaps** first, because that is what an approver wants to see: a count and a list, each row saying what is missing and linking to the item. **(b) A chain table**: one row per top-level requirement (every `FR` and `NFR`), with columns for the layers that build on it (stories, screens, components, endpoints and tables, rules), each cell listing the item IDs, and an empty cell shown as a clear dash, not blank. **(c) Pick one item** and see its **ancestors and descendants as an indented list** (what it comes from, what is built on it). Alternatives: a drawn graph (looks good, hard to read past about 30 items, and I would have to draw it), or just the gap list (cheapest, shows nothing of the chain). Default: the tab with the three parts, as text and tables, no graph.
2. **Which items are "expected to be built on" and which are "expected to derive from something"** comes **only** from the skills' existing `Covers:` and `Items:` lines, read in both directions (finding 3 and 6). No separate rule file. Default: that.
3. **Gap kinds, in the words a person reads.** (1) **Not covered**: "FR-004 is not named by any item that should cover it, and no Coverage check explains why." (2) **Declared uncovered**: "FR-009 is listed under Coverage check in Component overview: <the writer's reason>." (3) **Built on nothing**: "COMP-006 derives from nothing." (4) **Points at a withdrawn item**: "IFC-003 derives from DEC-002, which was withdrawn." (5) **Points at a missing item**: "FLOW-004 names COMP-009, which is not in any artefact." Each row names the artefact and version it was found in. Default: these five.
4. **Severity.** I will **not** colour gaps red, amber and blue like review findings: a gap is a fact the server computed, not a model's opinion. Two groups only: **Needs attention** (kinds 1, 3, 4, 5) and **Explained** (kind 2). Default: that.
5. **Gaps never block anything.** Approving a phase is not refused because of a gap; it is **listed with the approval** exactly as an unreviewed artefact is today (S12c: "Approve anyway" and the audit row). Default: shown and recorded, never blocking.
6. **Computed on demand, never stored.** The matrix is derived each time the tab opens, from the current links and the latest version of each artefact, so it can never be out of date, and a gap disappears the moment the cause is fixed. It costs a few queries (688 links here). Default: on demand.
7. **Phases that have not run yet.** A requirement's row shows only layers that exist; for a phase that has not started the cell says "not started" rather than "missing", so a project at Design does not show a wall of false gaps for Architecture. Default: that.
8. **Export.** A **Download as CSV** of the chain table (one row per requirement). Nothing else exports yet (Word/PDF export is a later step in the plan). Default: CSV only.
9. **Test depth and the mutation check as before.** Fixtures for the new route, static-render tests for each part, a mutants file with the baseline guard, the compile check and the hung-suite rule, fast-failing timing tests, and **a test that runs the real computation on the frozen links of a project built by the scripted demo and checks every number by hand**. Frontend still has no mutation harness; hand breaks, reported honestly.

Stated, not asked: all server text stays text; nothing new is installed; no model is called; the new route is read-only and needs no name; an archived project can still be read; links are not edited by hand (the artefact's text is the source of truth, and editing text already updates its links).

## In scope
- **Backend:** `app/trace/traceability.py` (a pure function from links + item lists + skill rules to the matrix and the gaps), `app/routes_trace.py` (`GET /api/projects/{id}/traceability` and `.../traceability/export.csv`), the approval summary gains "gaps" (read-only, from the same function).
- **Frontend:** the Traceability tab: the gap list, the chain table, the item picker with ancestors and descendants, the CSV link, the decoder and fixtures.
- **`scripts/trace_demo.py`:** runs the scripted Setup to Architecture, prints the gaps (none expected), then removes one link and shows the gap appear (offline, free).

## Out of scope (later)
- A drawn graph; editing links by hand; coverage of code and tests (their items do not exist until S17 onward, and they arrive by shipping skills with `Covers:` lines, so the matrix will pick them up with no change); impact analysis ("what breaks if I change FR-004") beyond the descendants list; exporting to Word or PDF; reviews of the matrix.

## Design notes
- **One function, two readers.** The route and the approval summary call the same function, so what the screen says and what the audit row records cannot differ (the S12c lesson).
- **Item kinds come from IDs.** `FR-004` has kind `FR`; the skill library says which kinds are produced where and which are covered by which. A kind no skill declares is shown but never flagged.
- **Latest versions only.** Gaps are computed on the latest version of each artefact. An older version's links are already gone from the table, so there is no history to confuse it.
- **Size.** The route returns item IDs and short names, never artefact bodies. For 688 links this is a few tens of kilobytes.
- **Failure.** An artefact whose text cannot be read gives a row in "Needs attention" saying so; the rest still computes.

## Tests (must pass before the step is done)

| Area | Proves |
|---|---|
| graph | links become ancestors and descendants; a diamond (two paths to one item) lists the item once; a long chain is walked without recursion limits; a loop (which the checks should prevent) terminates and is reported |
| coverage rules | the `Covers:` lines of every shipped skill are read both ways; a kind no skill declares is shown and never flagged; the rule list equals what the skills say (a test fails if a skill gains a `Covers:` and the matrix ignores it) |
| gaps | each of the five kinds is produced by one hand-made case and by no other; removing the cause removes the gap; a declared gap shows the writer's reason and is in "Explained", never "Needs attention" |
| withdrawn and missing | an item pointing at a withdrawn item, and at an ID that exists nowhere, are found and named |
| not started | a layer whose phase has not started is "not started", never "missing" |
| chain table | one row per FR and NFR in ID order; every cell lists exactly the items that derive from it, transitively where the layer is further down; an empty cell is a dash |
| real data | on the scripted demo project the numbers match a hand count (links, items by kind, gaps) |
| route | read-only, no name needed, archived readable, unknown project 404, no body text, planted secrets and paths appear nowhere; the CSV has the same rows as the table, is escaped against formula injection (`=`, `+`, `-`, `@` at the start of a cell), and has a stable column order |
| approval | the gaps listed with the approval equal the gaps on the tab; approving is never blocked |
| contract | a fixture per response; each decodes; a renamed field fails a test |
| components | static render: the tab, the gap list in both groups, the chain table with dashes, the picker, untrusted text inert |
| unchanged | full backend and frontend suites pass; every changed existing test is listed in PROGRESS |
| break-one-thing | a mutants file for the computation and the route; hung-suite rule; unkillable breaks named |
| build | `npm test` and `npm run build` pass |

## Dependencies / installs
None.

## Questions for the user
Decisions 1 to 9. The ones that most change the work: **1** (a tab of tables and lists, not a drawn graph), **4** (gaps are facts in two groups, not coloured severities), **5** (gaps are shown and recorded with approval, never blocking).

## Manual check for the user (we do not run the app)
1. Restart the backend. Open your Meeting Room Booking project and open the **Traceability** tab.
2. Read the **Gaps** list. Is every row true? Open the item it names and check.
3. In the **chain table**, find a requirement you know. Do its stories, screens, components, endpoints and rules look right?
4. **Pick an item** (a component, say) and read what it comes from and what is built on it.
5. Edit one artefact by hand and delete a `Derives from:` ID. Open the tab again: the gap is there, with the artefact named. Put it back: the gap is gone.
6. **Download the CSV** and open it in a spreadsheet.
7. Press **Approve** on a phase with a gap: it says "Approve anyway" and lists the gap.
8. Tell me what is wrong, missing or confusing in the content; look and feel waits.

## What was built, and what differed from the spec above (2026-10-31)
Built as specified, with these differences found while building:
- **A gap belongs to the artefact that should have accounted for it.** FR-003 missing from the component overview is a gap for *Architecture*, not for Requirements, so approving Architecture lists it and approving Requirements does not. The spec said "an item nothing derives from"; the per-artefact reading is what makes the sentence true ("FR-003 is not named by any item in the component overview").
- **One item can have several gaps**, one for each artefact that should have covered it (FR-003 on a project with components, epics and endpoints gives three).
- **Columns come from what each skill READS, not only what it must cover.** A journey step reads the requirements without being required to cover them, and still belongs in the requirement's row. A column that is empty against every requirement in a phase that has started (epics derive from personas, not requirements) is left out, because the gap list is the authority.
- **Order inside a chain is by kind and number**, not by the order links were created: parallel artefacts finish in any order, and the same project must read the same every time.
- **The approval lists only the gaps its own phase should have covered**, so approving Requirements is not blamed for Architecture's omissions.
- **The CSV protects every cell against spreadsheet formulas** (a leading `=`, `+`, `-`, `@`, tab or return gets an apostrophe), except our own lone dash.

## Done when
- [x] Listed tests pass; full suite and `npm test` green (backend 2681, frontend 1082)
- [x] Break-one-thing check run with the baseline guard and reported honestly (76 backend breaks: 16 survivors, 3 deleted as redundant, 13 closed; 26 frontend hand breaks, all caught)
- [x] `npm run build` succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] **You have run it in a browser and told me what you saw**
- [x] User confirms (2026-11-01: "we can close S15 and move to S16")
