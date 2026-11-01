# S13 · Design phase

**Milestone:** M4  **Size:** M  **Objectives:** O1, O2, O8  **Depends on:** S07, S10, S11, S12 (all closed)
After S12 you can run Requirements and approve it. Design, the third phase, shows three artefacts and a Run button that fails at once, because none of them has a skill. After S13 **Design runs end to end**: an agent turns the approved Requirements into a user journey, then low-fidelity wireframes, then high-fidelity wireframes, and you can *see the screens* in the browser, not just read about them.

## What I found before writing this (it changes the plan)

1. **The three Design artefacts have no skill, which is all that is missing on the agent side.** A skill is a short Markdown file (role, inputs, method, quality bar). The catalogue already defines the three artefacts, their IDs (`DES-UJ`, `DES-LF`, `DES-HF`), their order (journey, then low-fi, then hi-fi) and the role (`ux_designer`, routed to **Gemini**). So the writing side is three skill files, in the same format as the eight that exist.
2. **The Requirements do not fit in a Design prompt whole.** I measured the recorded Requirements: all seven artefacts are 35,243 characters, and a prompt may include at most 24,000 characters of upstream artefacts (nothing is cut silently; over the limit the run is refused with a sentence). The user journey needs only personas, functional requirements and epics (14,095 characters, fits). The wireframes need the journey plus the features they show. So each skill names exactly the inputs it needs, and none needs all seven. I checked the sizes against your real `phase2` recording, not an estimate.
3. **Wireframes need a drawing format, and that is the main decision (decision 1).** The pipeline stores Markdown. A wireframe is a picture. The cheapest honest way to show one is a fenced code block of **SVG or HTML inside the Markdown artefact**, which I tested: the existing item parser and reply validator skip fenced blocks, so a screen's markup does not look like a list item or a citation. The risk is the opposite one: this is model-written markup shown in your browser, so it must be treated as hostile.
4. **The screen already refuses to run model markup, so a viewer must be built, not switched on.** S12 renders artefact Markdown with raw HTML, images and scripts removed, so a wireframe in a code block today shows as *source text*. Showing it as a picture needs a deliberate, separate renderer with its own rules (decision 2). It is the one place in the product where model output becomes live content.
5. **Nothing is wired for Gemini yet in your setup.** Your `.env` has `IBM_ICA_GEMINI_MODEL_ID=gemini-3.7-flash`, so the slot exists. Whether Gemini writes well-formed SVG that passes the checks is **unknown until it is tried live**; a recording does not exist for it. That is the real risk in this step, and why decision 6 asks you to run it once.
6. **Replay will not work for Design until you record it.** Same as Requirements: a new recording is needed (`~$0.15` for three artefacts, a guess until run). The sample project then replays Design too.
7. **The Design Run button already behaves correctly once skills exist.** The server computes what you may do; nothing on the screen changes for the phase to start working. This step adds the pictures, not the plumbing.

## Decisions I need from you (defaults chosen; say if you want any changed)

1. **Wireframes are inline SVG inside the Markdown artefact.** Each screen is one `svg` block under a heading with its own ID (`SCR-001`...). SVG, not HTML: SVG is a closed set of drawing shapes (rectangles, lines, text) with no forms, no links to other pages and no scripts to speak of, and it is exactly what a wireframe is made of. The alternative, HTML, lets a model write buttons, inputs, iframes and styles that are far harder to make safe. Low-fidelity uses grey boxes and labels only; high-fidelity adds colour, type size and spacing.
2. **A purpose-built sanitiser, allow-list not block-list, applied at both ends.** A pure function `sanitise_svg(text)` that keeps only a fixed set of elements (`svg, g, rect, circle, ellipse, line, polyline, polygon, path, text, tspan, title, desc`) and a fixed set of attributes (position, size, fill, stroke, font, class), and drops everything else: scripts, event handlers (`on*`), `style` and `foreignObject`, `use`/`image`/`a` and any `href`, `xlink:`, `url(...)` or `javascript:` value, comments and CDATA. It runs **on the server before the artefact is saved** (a screen with anything refused is sent back through the repair loop with a sentence, like a bad citation) **and again in the browser before drawing**. The artefact on disk is therefore already clean, and the browser does not trust that. Output size, nesting depth and element count are capped, so a crafted drawing cannot hang the page.
3. **The viewer draws each screen in place, with the source one click away.** In the artefact reader, a fenced `svg` block under a screen is drawn (sanitised, sized to fit, with a border) instead of shown as text; a "Show source" toggle shows the markup, as text. Nothing else in the reader changes. Every other code block stays as text.
4. **The user journey is a table, not a picture.** A journey step is a row: step ID (`JS-001`...), persona, what they do, what they see, and `Derives from:` the requirement(s). It stays plain Markdown, so it is searchable, citable and checkable like every other artefact. A diagram of it adds nothing a table does not, and tables are what the traceability step (S15) will read.
5. **IDs and coverage, so Design is traceable.** Journey steps are `JS-` items, each deriving from at least one persona and one functional requirement or feature. Screens are `SCR-` items in both wireframe artefacts: a low-fi `SCR-001` and its hi-fi version share the number, so "screen 1" is one thing at two fidelities. **Coverage:** every journey step must be shown on at least one screen, and every screen must derive from a journey step; anything left out is listed in a Coverage check with a reason, as the user-stories skill already does for features.
6. **Replay and the live check.** After building, you run `design_demo --live --record phase3` once (a script like the Requirements one; my first estimate was `$0.10 to $0.30`, a guess, and **the user set the budget for this check at up to $2** on 2026-10-30, which leaves room to run it more than once), which writes the real Gemini output to disk. That output is also what I test the sanitiser and viewer against, so it is checked against what the model really draws, not what I imagine. Then `REPLAY_SET=phase3` replays Design. **If Gemini's SVG is poor or fails the checks, I will say so and we choose: tighten the skill, switch the role to Sonnet (one line in `routing.yaml`), or accept rougher pictures.** I will not hide a bad result.
7. **Review and edit work for Design with no new code.** A journey table and a screen are Markdown; the S12c review, request-changes, hand edit and the checks that a hand edit must pass all apply. A hand-edited SVG goes through the same sanitiser, so you cannot paste something unsafe either.
8. **Break-one-thing as before, with extra weight on the sanitiser.** The sanitiser is the security-critical part, so it gets its own mutants file and a corpus of hostile inputs (script tags, `onload`, `javascript:` in every attribute, entity tricks, nested and malformed markup, huge inputs), tested on both the Python and the TypeScript side with the same cases. A test fails if the two sanitisers disagree on any case in the corpus.

Stated, not asked: all server text stays text; the Design Run button needs no change; no new packages (the sanitiser is written by hand on purpose, so there is no third-party parser to trust or update); the Architecture phase (S14) is not touched; hi-fi is optional in the catalogue, so a project can skip it and Design still approves.

## In scope
- **Three skills** in `backend/app/phases/skills/`: `user_journey.md`, `lowfi_wireframes.md`, `hifi_wireframes.md`, each naming exactly the inputs it needs so it fits the 24,000-character limit.
- **`backend/app/design/sanitise.py`**: `sanitise_svg`, the allow-list, the caps, and a report of what was removed (for the repair sentence).
- **A body check for SVG** wired into `check_body` so an agent's reply and a person's edit both go through it. A refused drawing is a repair problem; the sentence says what was removed.
- **Frontend:** `src/lib/svg.ts` (the same sanitiser, in TypeScript), a `WireframeBlock` that draws a sanitised screen with a Show-source toggle, and the reader using it for fenced `svg` blocks.
- **`scripts/design_demo.py`**: offline demo with a scripted model (free), and `--live --record NAME` for your one real run.
- **Contract:** the hostile-input corpus shared by both sides, as a fixture the exporter writes and both test suites read.

## Out of scope (later)
- Diagrams for architecture (S14); the traceability matrix (S15); exporting wireframes to PNG or PDF; editing a drawing visually (you edit the text); links between screens; interactive prototypes; any HTML wireframes.

## Design notes
- **Where the check lives:** `check_body` already runs the section, citation, item and secret checks for both an agent reply and a hand edit (S08). The SVG check is one more step in that function, so the two paths cannot drift.
- **Fenced blocks are already inert to the parsers** (I tested a body with fenced HTML under list items: the item parser found only the real items, and the validator found no problems). The sanitiser only has to look *inside* fences, not around them.
- **A repair, not a rejection.** A model that writes a `style` attribute or an `href` is told which element and why, and asked to redraw. After the usual three attempts the artefact is not saved, like any invalid reply.
- **Size:** a screen is capped (default 12,000 characters of SVG), a body at most 60,000 (the existing limit), so the journey plus a few screens fit; the hi-fi skill asks for the screens the journey needs, not every possible state.
- **Gemini's family is Google, the writer of the Requirements is Anthropic**, so a Design review by Sonnet is "independent" by the label S08 computes; by the same rule a Gemini-written design reviewed by Gemini would say "same family". Nothing to build; stated so the label is not a surprise.

## Tests (must pass before the step is done)

| Area | Proves |
|---|---|
| skills load | each of the three loads with the existing loader; its inputs exist in the catalogue; `Items:` and `Covers:` lines are valid; the inputs of each fit the upstream limit on the recorded Requirements |
| sanitiser: allow-list | every allowed element and attribute survives; every disallowed one is removed; the output of a clean drawing equals its input |
| sanitiser: hostile corpus | scripts, `on*` handlers, `javascript:`/`data:`/`vbscript:` in any attribute, `style`, `foreignObject`, `use`, `image`, `a`, `href`/`xlink:href`, `url(...)`, entities and mixed case, comments, CDATA, unclosed and nested-wrong tags: none survives, and the function never raises |
| sanitiser: limits | depth, element count and total size are capped; a 5 MB input finishes in well under a second; output is never larger than input |
| both sides agree | the Python and TypeScript sanitisers give identical output for every case in the shared corpus; a case added to one side and not the other fails |
| agent save | a reply with a script in a screen is sent back with a sentence naming the element; the redrawn reply is saved; three bad replies save nothing; a clean reply saves unchanged |
| hand edit | an edit containing an unsafe drawing is refused with the reasons and saves nothing; a safe one saves |
| journey checks | each step has an ID and derives from a persona and a requirement; a step no screen shows, or a screen with no step, is listed or refused per the coverage rule |
| items and links | `JS-` and `SCR-` items parse; `Derives from:` becomes links; a re-run keeps IDs |
| viewer | static render: a clean `svg` block is drawn as an `svg` element with the right size; an unsafe one is drawn without the unsafe parts; "Show source" shows the markup as text; a non-SVG code block is still text; markup in an artefact title or note is still inert |
| Design phase end to end | with a scripted model, Setup then Requirements then Design runs, in waves (journey, low-fi, hi-fi), and the phase can be reviewed, sent back, edited and approved |
| contract | fixtures for a Design artefact detail; decoders unchanged except where a field is added |
| unchanged | full backend and frontend suites pass; every changed existing test is listed in PROGRESS |
| break-one-thing | a mutants file for the sanitiser and its wiring, run with the baseline guard, compile check and hung-suite rule; every survivor is a test gap; unkillable breaks are named |
| build | `npm test` and `npm run build` pass |

## Dependencies / installs
None. (Your live Design run uses Gemini through ICA: a few cents. The sanitiser is hand-written on purpose.)

## Questions for the user
Decisions 1 to 8. The ones that most change the work: **1** (SVG, not HTML), **2** (a hand-written allow-list sanitiser run on both sides), and **6** (one live Gemini run to see whether it draws well, with a fallback plan if it does not).

## Manual check for the user (we do not run the app)
1. Restart. Open the sample project, approve Requirements if it is not, and open **Design**. The three artefacts and a Run button are there.
2. **Run this phase** (live; or replay once `phase3` is recorded). Watch the rows: the journey first, then low-fi, then hi-fi.
3. Open the **User journey**: a table of steps, each with the requirement it derives from.
4. Open **Low-fidelity wireframes**: each screen is *drawn*, with a border and its ID. Click **Show source** on one: the markup appears as text.
5. Open **High-fidelity wireframes**: the same screens with colour and type.
6. Press **Review** on a wireframe artefact: the reviewer reads the markup and the journey.
7. **Edit by hand**: paste `<script>` or an `onclick` into a drawing and Save. It is refused, with the reason, and nothing is saved.
8. Tell me what looks wrong: layouts, labels, missing screens, anything Gemini drew badly. Look and feel waits; whether the content is *right* is the point.

## Done when
- [x] Listed tests pass; full suite and `npm test` green (backend 2430, frontend 973; summary lines in PROGRESS.md)
- [x] Break-one-thing check run with the baseline guard and reported honestly (69 sanitiser breaks: 14 survivors and 1 hang found and closed, 2 named unkillable by construction)
- [x] `npm run build` succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] **You have run it in a browser and told me what you saw** (2026-10-31: a live Gemini Design run, a hand edit that exposed the citation defect, a review that exposed the multi-item finding defect, the Reopen button; recording `phase4` made)
- [x] User confirms (2026-10-31: "You have a yes")

## What the live runs showed (from the stored versions, 2026-10-31)
- First run: User journey and Low-fidelity wireframes needed 2 attempts each; High-fidelity wireframes failed on the 8,000-token output limit (Gemini's hidden reasoning used the budget).
- After the per-role limit (24,000): Low-fidelity v2 and High-fidelity v2 each finished in **1 attempt** (about $0.068 and $0.056). The user journey was not re-run (edited by hand since).
- Not shown by these runs: a cost for a whole phase run from scratch with the 24,000 limit in force from the start. The $5 cap stays; the user will take a call on it after a few more tests.
