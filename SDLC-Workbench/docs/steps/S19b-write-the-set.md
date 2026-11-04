# S19b · The Build phase writes the instruction set in pieces

**Milestone:** M5  **Size:** M, two sub-slices  **Objectives:** O7 (reworded), O9, O3  **Depends on:** S19a (closed: the checks, the one `build_instructions` artefact, the frozen generator in `app/build/legacy/`)
**Status:** ANSWERED 2026-11-04: **all ten defaults**. The user also said 'for this work, we can increase the budget to 8$ if needed': the per-run cap stays at the built-in $5 and can be raised to $8 with `RUN_MAX_COST_USD=8` in the user's own `.env` (never read by me); the built-in default changes only if the user asks. 19b-1 and 19b-2 are BUILT AND TESTED (2026-11-04); waiting for the user's UI look and a live run.
Written after the user's first live run of the 19a catalogue failed, and suggested "we might need to break this down to small md files".

## Goal
After this step, running the Build phase really produces the instruction set. It does so in **small pieces**: the foundation file, then one file per use case, then the acceptance file, each its own small model call. The system (not the model) joins the pieces into the single `build_instructions` artefact and runs the 19a checks over it.

## What I found before writing this
1. **Why the live run failed (read from the stored call record, not guessed).** The call was `solution_architect` on Sonnet, 64 seconds, `finish=length`, 0 output tokens recorded, on the general 8,000-token limit. The reply never started. My inference (not provable from here): the model spent the whole limit on hidden reasoning. The task was also too big for one reply: about seven files of up to 20,000 characters each. 19a's tests used scripted replies and could not show this; only the real run could.
2. **The runtime writes one artefact from one reply.** `AgentRuntime.run` builds one prompt from one skill and expects ONE `<artefact>` block. A set cannot go through it as it is, and one failing file would send the whole set back for repair.
3. **There is already a pattern for "the phase writes this artefact itself":** the Build hook writes `test_report` and `code_security_review` after the run (`HOOK_WRITES`), and the runner leaves those out of its model work. The set needs the same idea, with model calls inside it.
4. **The old fix-loop path would now say something false.** With the live catalogue, `BuildHooks.after_artefacts` would report "the tests were not run because backend_code ... was not written". That path must be off for a catalogue that has no code artefacts (the frozen copy in `legacy/` keeps it, so its 399 tests still run).
5. **Raising `solution_architect`'s output limit also changes the Architecture phase's calls** (the same role writes the high-level design and the component overview). A limit is a ceiling, not a spend, but it is a shared setting.
6. **The use cases already exist as items.** Each `UC-nnn` in the saved use-case diagram is one file to write; the 19a checker already refuses a file for a use case that is not there and a set that misses one.

## Decisions (each has a default; say "all defaults" or change any)
1. **Pieces, in three stages.** (a) `00-foundation.md` alone; (b) one call per use case, **in parallel** up to the existing `RUN_MAX_CONCURRENCY` (3); (c) `99-acceptance.md` alone, after the others, because it must name what they built. Default: yes.
2. **What each call is shown.** Every call sees the design artefacts the skill already names (use-case diagram, low-level and high-level design, component overview, functional and non-functional requirements, hi-fi wireframes; about 70,000 characters on the real project). A use-case call also sees the **finished foundation** (so tables and shared rules are not invented twice), and the acceptance call sees the finished files. Default: show everything in the design, not a trimmed slice. **Cost: about nine calls of roughly 20,000 input tokens each; not measured.** Trimming each call to its own use case's items is possible later but needs a rule for which items belong to a use case, which I would rather not guess at now.
3. **Reply format.** Each call writes ONE Markdown file between the usual `<artefact>` tags. Reusing the tags means a reply cut off before its closing tag is recognised and explained by the code that already does that. The file name comes from the system (`UC-001-<slug>.md`, the slug made from the use case's own title), never from the model. Default: yes.
4. **Output limit.** `AGENT_OUTPUT_TOKENS_BY_ROLE` gains `solution_architect=16000` by default. One piece is at most 20,000 characters (about 5,000 tokens), so 16,000 leaves room for hidden reasoning. If a real run still cuts a piece off, the existing plain cut-off message names the role and the setting. Default: 16,000, with the shared-role effect in finding 5 accepted.
5. **The system joins the pieces.** `assemble` (already built and mutation-checked) writes Overview, Files (INS items, IDs kept from the previous version, none reused), Coverage check and Instructions. The model never writes the set-level parts. Default: yes.
6. **Repair is per piece.** A piece that fails its checks (`check_file`, with the design's IDs as "known") is sent back alone, with the usual `AGENT_MAX_REPAIRS` (2). **If any piece still fails, nothing is saved** and the run names the file and why; a re-run redoes all pieces (finished pieces are not kept; keeping them is parked as D20 because it needs a place to store drafts). Default: all-or-nothing.
7. **Set-level gaps are saved and shown, not hidden.** After assembly the whole-set check runs (a use case with no file, an endpoint, table or rule neither built nor declared "Not covered"). If it finds gaps, the set is saved with the gaps written into its Coverage check section and a flag, and the gate (19d) blocks on them (waivable with a reason, as designed). A person's hand edit is checked the same way as any artefact. Default: save with gaps listed.
8. **Progress is visible.** The one artefact row shows its files as it works: `piece.started`, `piece.finished` (with tokens and cost) and `piece.failed` (with the reason) events from the runner, and a small list under the artefact row in the run panel (collapsed once finished). Default: events and a minimal list in 19b; the full Build screen stays in 19d.
9. **The old generator path is switched off by the catalogue, not by a flag.** The fix loop, the test report and the two reviewers run only when the catalogue being run holds the code artefacts they need. With the live catalogue they do not run and say nothing. Nothing is deleted. Default: yes.
10. **Bounds.** At most **15 use cases** per run (a larger project is refused with a plain message naming the count, instead of silently making 15+ calls); a project whose use-case diagram has no use cases fails with "the use-case diagram has no use cases to write instructions for". The existing run cost cap ($5, or $8 if the user raises it) and time cap still stop the run between pieces; a stopped run saves nothing (decision 6). Default: 15.

Stated, not asked: no model is called in any test (scripted replies, with one deliberately cut off); the saved version uses the same save path as every other artefact (versions, links from each file's `Derives from:`, guardrail flags, a generation record that lists every piece's call); the tool header from 19a is never stored (it is applied when shown or downloaded, 19d); every earlier phase is untouched.

## Slices
| Slice | Delivers |
|---|---|
| **19b-1** | The composer: use-case list from the saved diagram; the three piece briefs; the per-piece call with repair; assemble and set check; the all-or-nothing save through the shared save path; the 16,000 default. Tested end to end with a scripted gateway. No runner change. |
| **19b-2** | The runner hands the artefact to the composer (hook), the `piece.*` events, the generator path off for a catalogue without code artefacts, the small run-panel list, `scripts/instructions_demo.py` (offline, free). |

## Out of scope
The screen (tool radio button, file list, per-file download, zip, notice): 19d. The acceptance tests being executable and valid Python: 19c (19b writes the acceptance file, checked as text). Keeping finished pieces after a failure: D20. Running or verifying returned code: D19. A live run: only on the user's word.

## Tests (must pass before each slice is done)
| Area | Proves |
|---|---|
| order | foundation first; use cases only after it; acceptance only after every use case; at most `RUN_MAX_CONCURRENCY` calls at once |
| names | each file name comes from the system and the use case's title; a model that writes a different name or a file mark inside the file is refused or ignored |
| pieces | a bad piece is repaired alone; two bad replies in a row end that piece; the others are not re-asked |
| all-or-nothing | one piece failing saves nothing, names the file and the reason, and leaves any previous version untouched |
| cut off | a piece cut off before its closing tag gets the plain length message, not "tag missing" |
| assembly | the saved body equals `assemble` of the pieces; IDs kept from the previous version and never reused; links saved from each file's Derives from |
| gaps | a use case with no file or an uncovered endpoint is saved, listed in Coverage check, and flagged; nothing is silently dropped |
| bounds | 0 use cases, 16 use cases, a missing diagram: each a plain message and no model call |
| caps | once the cap says stop, no new piece starts; a piece that would need another repair call is dropped; because the save is all-or-nothing, a stopped run saves nothing and says which pieces were finished and paid for (it is reported, never raised as success) |
| wiring (19b-2) | the runner leaves `build_instructions` to the composer; events arrive in order; the old loop does not run, and does run for the frozen catalogue |
| limit | `solution_architect` defaults to 16,000; every other role unchanged; the Architecture roles' behaviour otherwise unchanged |
| unchanged | the 399 generator tests, every earlier phase, `export_contract --check`, no test touches `backend/data` |
| break-one-thing | a mutants file per sub-slice with the baseline guard; every survivor closed with a real test |

## Dependencies / installs
None.

## Questions for the user
All ten have defaults. The ones worth reading first: **6** (all-or-nothing, so one bad file in nine costs a full re-run), **2** (every call sees the whole design, about nine calls of roughly 20,000 input tokens each), and **4** (a 16,000 ceiling for the `solution_architect` role, which the Architecture phase shares).

## Manual check for the user
After 19b-2, from `backend/`: `python -m scripts.instructions_demo` (offline and free: a scripted Build phase writing the pieces for a small project, one reply deliberately cut off, one piece repaired, one use case left uncovered and shown in the Coverage check). Then restart the backend and run the Build phase once on the project that failed. **That live run costs money; I will not start it. Budget guess, unmeasured: well under the $5 cap.**

## Done when
- [ ] Listed tests pass; full suite and `npm test` green (summary lines in PROGRESS.md)
- [ ] Break-one-thing check run with the baseline guard and reported honestly
- [ ] `npm run build` succeeds
- [ ] Manual-check list handed over
- [ ] PROGRESS.md and RESUME.md updated
- [ ] **You have run it live once and told me what you saw**
- [ ] User confirms
