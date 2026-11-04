# S19c · The UI gets its own instruction files

**Milestone:** M5  **Size:** M  **Objectives:** O7 (reworded), O9, O3  **Depends on:** S19a, S19b (the set, the composer, the checks)
**Status:** ANSWERED 2026-11-04: **all defaults** ("lets do all defaults and go with it"). Not built yet.
The old 19c (acceptance tests as valid Python) becomes **19d**, and the gate and screen (old 19d) become **19e**. S19b is still open: it has not been run live with the fixes from the first live run.

## Goal
After this step the instruction set holds **the user interface as files of its own**, separate from the back-end behaviour, so a person can give the UI files to one coding tool and the back-end files to another, and each file stays small. The set gains one overall UI guide and one file for each hi-fi screen in the design.

## What I found before writing this (read from the real set the first live run produced)
1. **The UI is scattered.** In the real set each of the 7 use case files carries 10 to 14 lines about screens, buttons and layout, mixed in with its API detail, and the foundation carries 13 more. `HFS-001` is described in 4 different files. A coding tool building the front end would have to assemble each screen from several files.
2. **Nothing says how the UI should look and behave overall.** There is no shared rule for layout, navigation, loading, empty and error states, forms, wording or accessibility, so each screen would be built by guesswork.
3. **The design has what is needed.** The real project has 4 hi-fi screens (HFS-001 to HFS-004) and 4 low-fi ones, and the hi-fi wireframes artefact is 19,345 characters. The use cases already name the screens they use.
4. **A coding tool cannot see a drawing.** The wireframes are SVG pictures. The instructions must say in words what is on the screen.
5. **The composer already writes a set in pieces,** and the checks (`check_file`, `check_set`, coverage) are built so a new kind of file is an addition, not a rewrite.

## Decisions (**the user said "all defaults" on 2026-11-04, so all five stand as written**)
1. **One file per hi-fi screen**, named `UI-HFS-001-<slug>.md` (slug from the screen's own title, made by the system), plus **one overall guide `01-ui-guidelines.md`**. Components that several screens share are described once, in the guide, and the screen files refer to them by name. Default: per screen, not per component.
2. **Wireframe drawings are described in words** in each screen file (what is on the screen, top to bottom). Shipping the drawing itself as an `.svg` file beside the instructions is **offered** and is part of this step as a download only: the screen file does not depend on it. Default: yes, as an optional extra download; the instructions stand without it.
3. **Cost.** The real project has 4 screens, so a Build run goes from 9 calls to about 14 (the guide, 4 screens, plus the 9 it has now). Not measured. Default: accepted. The run cap you set (`RUN_MAX_COST_USD`) still stops a run between files.
4. **A project with no screens** (the design has no hi-fi screens): the UI files are skipped and the set says "No hi-fi screens in the design: no UI files". The checks do not ask for what is not there. Default: skipped with a plain note.
5. **No UI tests in this step.** Clicking through the screens is for later (the acceptance tests stay on the API). Default: later.

Stated, not asked: the order of the set becomes foundation, UI guidelines, use cases, screens, acceptance. The use case files keep only behaviour and **point at their screens by ID** ("the screen HFS-001") instead of describing them; a use case file that describes layout is sent back. Every screen in the design must have a file (the same coverage rule the use cases have), and a screen file may only name design IDs that exist. Each screen file names the API endpoints it calls (API IDs), the states it must handle, and the business rules (RUL IDs) behind each message it shows. The guide is written first, so each screen is shown it; the screens are written in parallel, like the use cases. No model is called in any test. The tool header (Copilot, Claude, GPT or Gemini, 19e) applies to the UI files like any other.

## Design notes
- **New kinds of file:** `ui_guide` (`01-ui-guidelines.md`, fixed name, second in the order) and `screen` (`UI-HFS-nnn-<slug>.md`). Each has fixed sections like every other kind (`SECTIONS`), a "Not applicable" list, and a code-size cap (short examples only).
- **Sections.** Guide: Goal, Layout and navigation, States (loading, empty, error), Forms and messages, Shared components, Accessibility, Do not, Traceability. Screen: Goal, Read first, What is on the screen, Components and their states, What the person can do, Calls it makes, Messages and the rules behind them, Done when, Do not, Traceability.
- **Checks added.** A screen file must be named for a hi-fi screen that exists; each screen has exactly one file; the screen file names at least one API ID it calls (unless it calls none and says so); a use case file may not carry layout sections; the set's coverage includes HFS the way it includes UC. All through the existing `check_file` / `check_set` / `gaps_of` / `assemble`.
- **Composer.** After the foundation, write the guide; then the use cases and the screens in parallel, up to the concurrency limit; then acceptance. A screen is shown the foundation and the guide, not the use cases.
- **Events and screen.** The same `piece.*` events (a new stage name for each kind), so the run panel lists them with no change except the label. The reader already folds every file; the UI files are just more files.
- **Skill.** `build_instructions.md` gets the two new kinds in its Method. Its inputs already include the hi-fi wireframes; the low-fi wireframes are added.

## Slices
| Slice | Delivers |
|---|---|
| **19c-1** | The checks: the two new kinds, their sections, names, coverage of screens, the no-layout-in-use-cases rule, `assemble` and `check_instructions` for them. No model. |
| **19c-2** | The composer writes the guide and the screens; the skill's new Method; the events; the demo shows a project with screens and one without. |

## Out of scope
UI tests; the gate and screen (19e); acceptance tests as valid Python (19d); component-level files; running or rendering anything.

## Tests (must pass before each slice is done)
| Area | Proves |
|---|---|
| names | a screen file must be named for a hi-fi screen in the design; a stray or duplicate name is refused; the guide has one fixed name |
| sections | a missing or empty section of either new kind is sent back; "Not applicable" only where allowed |
| coverage | every hi-fi screen has exactly one file; a screen with none is listed as a gap (and the gate blocks on it later) |
| separation | a use case file that describes layout is sent back; one that only names its screen by ID passes |
| ids | a screen file may name only IDs in the design; its API IDs exist |
| order | the foundation, then the guide, then use cases and screens, then acceptance; the screens and use cases run in parallel; a screen is not started before the guide has finished |
| no screens | a design with no hi-fi screens writes no UI files, says so, and is not reported as a gap |
| cost | the number of calls is guide + screens + use cases + 2; each piece's cost is counted |
| unchanged | 19a and 19b behaviour for a set with no screens is exactly as before; the kept generator's tests; every earlier phase |
| break-one-thing | a mutants file per slice with the baseline guard; every survivor closed with a real test |

## Dependencies / installs
None.

## Manual check for the user
After 19c-2, from `backend/`: `python -m scripts.instructions_demo` (offline and free: now with a project that has screens and one that has none). Then, only on your word, a live run: about 14 calls on your project.

## Done when
- [ ] Listed tests pass; full suites green
- [ ] Break-one-thing check run with the baseline guard and reported honestly
- [ ] Manual-check list handed over
- [ ] PROGRESS.md and RESUME.md updated
- [ ] **You have run it live once and told me what you saw**
- [ ] User confirms
