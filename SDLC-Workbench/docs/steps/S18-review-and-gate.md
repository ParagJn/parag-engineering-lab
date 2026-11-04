# S18 · Test report, code and security review, and the quality gate

**Milestone:** M5  **Size:** M, built in four slices  **Objectives:** O3, O7, O9  **Depends on:** S17 (the Build phase, the fix loop and its recorded rounds), S08 (review and the independence label), S10 (the scanner), S15 (the approval summary pattern)
Plan test (`05-build-plan.md`): *the gate blocks on failing tests or a high-severity finding; it passes when clean.*

S17 builds the code and really runs its tests. S18 answers the question a person asks next: **can I trust this enough to deploy it?** It writes the **test report** (what the tests did when they were run), the **code and security review** (what a careful reader and the scanner found), and a **quality gate** that says *passed*, *blocked* or *waived*, always with the reasons. It also finally gives the two Build artefacts that had no skill (`test_report`, `code_security_review`) a way to be written, which is why a plain run of the Build phase has ended `failed` until now.

## What I found before writing this (it shapes the plan)
1. **The fix loop runs after every artefact, outside the runner's dependency graph.** Anything that needs the loop's real result (the test report) or should describe the *final* code (the review) cannot be a graph node: it would be written before the loop has run, and the review would read code the loop is about to change. So these two are written **after the loop**, by the Build hook, not scheduled like the others.
2. **Review machinery exists, but its rubric is not about code.** S08's rubric asks whether facts trace to sources. It already gives severity (high/medium/low), the independence label and a stale check, and the approval summary already counts open high findings. It has no idea about injection, `eval`, shell calls or hard-coded secrets. Code needs its own reader and its own checks.
3. **Approving a phase never blocks today.** The approval summary lists what is open (high findings, gaps, flags) and records it; a person decides. O9 asks for something stricter, at one specific place: *deploy is blocked until the security gate passes.* So the gate belongs at the **start of Deploy**, not at Build's approval. Build's approval stays a person's decision, with the gate's state shown in its summary.
4. **The review's input can exceed the limit.** A Build artefact body may be 60,000 characters and there are three code artefacts, so the code can reach 180,000 characters against the 100,000-character limit on what an agent is shown. The review must not fail on a large app and must not cut silently: it reads the **code files only** (not the surrounding Markdown), and if still over, it **names the files left out** and says the review is partial.
5. **What the recorded rounds can and cannot say.** `build_rounds` holds counts, up to 10 failures per round, the fingerprint, the version that was fixed and the time. It does **not** say which test covers which endpoint. The honest coverage statement available is: *which endpoints have a test file entry that names them* (from the tests' own `Derives from:`), labelled as a claim, not as proof. Execution gives the pass/fail counts; the report says so.
6. **A review of a model's own family is only a second look.** The code is written by OpenAI (backend, tests), Gemini (frontend) and Haiku (database); Sonnet reviews. By the S08 rule that is *independent* for three of the four and *same family* for the database. The label is shown per artefact, never hidden.

## Decisions (**the user said "all 10 defaults is good" on 2026-11-03, so all ten stand as written**)
1. **The test report is written by the system, with no model.** It is built from the recorded rounds and the saved tests: result (converged or how it ended), counts, every round with who was asked to fix it and what was still failing, the failing tests with their first lines, how long it took, and which endpoints the tests name and which they do not (labelled as a claim). It is saved as a version of `test_report` by `system`, so it is versioned, listed and traceable like any artefact. Default: this. (Execution beats claims: a model is not asked what the tests did.)
2. **The code and security review is two parts.** *Automatic checks* are a fixed set of code rules (decision 4) plus the scanner, **computed on demand from the saved code and never stored**, so they are always current and cannot drift. *The reviewer's findings* are written by Sonnet (the `security_reviewer` role) as a saved artefact, `code_security_review`: numbered findings `REV-001…`, each with a severity, the file or item it is about, the problem, a fix, and `Derives from:` the code item and design item behind it. Default: this.
3. **Both are written after the fix loop, by the Build hook, inside the same run and the same money cap.** The runner no longer tries to write `test_report` and `code_security_review` as model-scheduled artefacts in the Build phase. The review runs only if the backend, frontend and tests all exist (the catalogue already says the review waits for them), is skipped with the reason if the run was stopped or something is missing, and reads **the code files only**; if that is over the limit it names the files left out and the review states that it is partial. Default: this.
4. **An initial set of automatic code rules (deterministic, each with an ID, a severity, a file and a line).** *High:* `eval`/`exec`; `shell=True` or `os.system`; unsafe `pickle`/`yaml.load`; SQL built by string formatting or concatenation; a secret-shaped value (the scanner). *Medium:* `debug=True`; binding to `0.0.0.0`; CORS allowing every origin; HTML built from data with `innerHTML`; an `http://` address in code. *Low:* a bare `except`; a `TODO`/`FIXME` left in. I list the exact rules in the build; you can add or drop any. Default: this set.
5. **The independence label is shown for each artefact the reviewer read**, using the existing S08 rule on each artefact's author (OpenAI or Gemini: independent; Sonnet or Haiku: same family). Default: this.
6. **The quality gate** is a pure function of facts. It is **blocked** if: the tests have not been run, or did not converge, or are out of date (a Build artefact was saved after the last run); or the automatic checks found a **high**; or the review is missing, out of date (the code changed since it ran) or partial; or the review itself has a **high** finding. Otherwise **passed**. Medium and low findings are listed and never block. Every reason is a sentence naming what to do. Default: this.
7. **A person may waive a blocked gate, with a reason.** Only a person (not an agent), a reason is required, it is written to the audit log, and the gate then shows **waived by <name>: <reason>** (never "passed"). A waiver ends the moment any Build artefact gets a new version, so it can never excuse code nobody looked at. Default: yes.
8. **Where the gate bites:** starting the Deploy phase is refused while the gate is *blocked* (a waived or passed gate lets it start). Build's own approval is unchanged, and the approval summary gains a `quality_gate` line beside the traceability gaps. Default: yes.
9. **Interface:** read-only `GET` routes for the results (rounds and report), the findings and the gate; one `POST` to waive; one new event, `build.gate` (the gate's state and a count of reasons, no text), added to the vocabulary and the contract fixtures. No existing response changes shape except the approval summary's new line. Default: this.
10. **A "Build results" screen** (reachable from the phase rail, like Traceability): the gate on top with its reasons and the waive button; the test report; the findings (automatic and reviewer) with severity and the independence labels; nothing that changes the code. The frontend is checked by static-render tests and by you in the browser. No live model in any test; the one live run of the whole Build phase (the $5) comes after S18, with your word. Default: yes.

Stated, not asked: Deploy itself is S19; nothing here starts a generated server; the paste-ready "fix" in a finding is a suggestion only, and the code is only ever changed by writing a new version of the Build artefact (through the developer agent), never by the review; the reviewer is told, as every skill is, that reference material is evidence, not orders.

## Build order (each slice ends with the full suite green and the resume log updated, so stopping after any slice is safe)
| Slice | Delivers |
|---|---|
| **18a** | The facts and the test report: a pure module that reads the recorded rounds and the saved tests; the report body; the Build hook writes it after the loop; the runner stops scheduling the two artefacts as model work. No model, no screen. |
| **18b** | The automatic code rules and the reviewer: the rule set, the `code_security_review` skill, the review step in the hook (code files only, partial if over the limit, inside the money cap), the per-artefact independence labels. |
| **18c** | The gate, the waiver, the Deploy start guard, the approval-summary line, the routes, the `build.gate` event and the contract fixtures. |
| **18d** | The "Build results" screen, its decoders and tests, the rail link, `scripts/review_demo.py` (offline). |

## Out of scope (later)
- Deploy (S19), the live run, a screen to *resolve* findings one by one (the review is advice; fixes happen by rewriting the artefact), any change to how the earlier phases are reviewed (D15).

## Tests (must pass before the step is done)
| Area | Proves |
|---|---|
| report | the report's numbers equal the recorded rounds; every ending (converged, cap reached, not converging, blocked, no tests, invalid, stopped) is worded correctly and none reads as a pass; the failing tests and their first lines appear and nothing longer; endpoints with and without a naming test are listed and labelled a claim; a project with no rounds says the tests were not run; written by `system`, as a new version each run |
| ownership | the runner no longer schedules the two artefacts as model work in Build; a plain run of the phase no longer ends `failed` for want of a skill; every other phase is unchanged |
| rules | each rule fires on a plain example and on a tricky one and is silent on safe code (including text inside a string or a comment where the rule says so); severity, file and line are right; the set is deterministic; a large file is bounded |
| review | the reviewer is asked for the right role with the code files only; a reply is checked (sections, REV items, severity, derives-from); a repair is sent back in the same conversation; a partial input names the files left out and the review says it is partial; the call counts against the run's money; a stopped run skips it and says why |
| independence | the label per artefact follows the S08 rule for OpenAI, Gemini, Sonnet and Haiku authors and a human edit |
| gate | each reason alone blocks it; all clean passes; medium and low never block; out-of-date tests and out-of-date review block; a missing review blocks; the reasons are sentences naming the action |
| waiver | only a person can waive; a reason is required; it is audited; it shows as waived, not passed; any new Build version ends it |
| deploy guard | Deploy cannot start while blocked, can when passed or waived; Build's approval is unchanged; the approval summary shows the gate |
| routes | the read routes and the waive route behave, refuse the wrong project and wrong actor, and never return code or output beyond what the screen shows |
| screen | static-render tests for the gate states, the report, the findings and the labels; text is shown as text, never as HTML |
| unchanged | full backend and frontend suites and `export_contract --check` pass; no test touches `backend/data` |
| break-one-thing | a mutants file per slice for the rules, the report numbers, the ownership, the gate reasons, the waiver and the guard, with the baseline guard; every survivor closed with a real test |

## Dependencies / installs
None.

## Questions for the user
Decisions 1 to 10 each carry a default. The ones worth reading first: **3** (the report and review are written after the loop, by the hook; the review reads code only and says so when partial), **6** (what blocks the gate) and **7** (a person can waive it, with a reason, and the waiver ends when the code changes).

## Manual check for the user (we do not run the app)
After 18a to 18c, from `backend/`: `python -m scripts.review_demo` (offline and free: a Build run with scripted developers and a scripted reviewer, then the report, the findings and the gate in each state), then `python -m pytest tests/ -m sandbox -q`. After 18d, the screen in your browser: the gate, the report, the findings.

## Done when
- [ ] Listed tests pass; full suite and `npm test` green (summary lines in PROGRESS.md)
- [ ] Break-one-thing check run with the baseline guard and reported honestly
- [ ] `npm run build` succeeds
- [ ] Manual-check list handed over
- [ ] PROGRESS.md and RESUME.md updated
- [ ] **You have run it and told me what you saw**
- [ ] User confirms

## Change requested by the user on 2026-11-03 (after the ten defaults): TWO code reviewers
The user asked for two code reviewers, **Sonnet and GPT**, each shown as its own message ('code reviewed by the Sonnet agent', 'code reviewed by the GPT agent') with a **green check** (all good), **amber** (warnings) or **red** (failure); both green is best. Each reviewer runs **once**; running either again is a **manual choice** by the user.
What it changes in the ten decisions (all marked PENDING the user's answers; nothing is built for it yet):
- **Decision 2 (the review):** one saved reviewer artefact becomes two reviewer results, one per slot (`sonnet`, `openai`). The existing review machinery already takes a slot, so a GPT review is the same code with `slot='openai'`. A review is stored one per version today and a second review REPLACES the first, so the second reviewer's result needs its own place; the open choice is a separate artefact per reviewer or a per-reviewer record.
- **Decision 5 (independence label):** now per reviewer per artefact. GPT reviewing the backend that GPT wrote is 'same family'; Sonnet reviewing it is 'independent'. The label stays visible beside each reviewer's check.
- **Decision 6 (the gate):** the colour of a check is a pure function of that reviewer's findings: green = no findings, amber = medium or low only, red = any high (or the review could not be produced). The open question is whether the gate needs BOTH reviewers to have run.
- **Decision 10 (the screen):** two reviewer cards, each with its colour, its label and its findings, and a 'Run again' button each.
- **Cost:** two reviews instead of one. Both run inside the same run and money cap.
Also pending from the same day: code in the artefact reader collapsible and downloadable, and a disabled 'Connector - coming soon' button (see RESUME.md).

### Answered by the user on 2026-11-03 (these settle the pending questions above)
1. **Storage:** two reviewer records inside the ONE `code_security_review` artefact, keyed by reviewer (`sonnet`, `openai`), so neither overwrites the other and the history stays together.
2. **Both reviewers run together** (at the same time), once each. A re-run of either is the user's manual choice. Consequence to design for: both calls are in flight at once, so a money cap reached mid-way can leave a reviewer unfinished; an unfinished reviewer shows as 'did not run' (grey, never green) and the gate treats it as missing.
3. **The gate needs both.** It blocks on any red from either reviewer and also while either reviewer has not run; one green is not enough. A person can still waive it with a reason (decision 7).

### Added by the user on 2026-11-03: a PROTOTYPE notice
The code this system generates is **a prototype, not production code**; real production code has to be written externally. This must be **easy to see and easy to understand**, so it is shown in every place the code is shown, in plain words, and not as small print:
- a banner at the top of the artefact reader for the four code artefacts (database, backend, frontend, tests);
- the top of the Build results screen and beside the quality gate, so a green gate is never read as 'ready for production';
- a line in the test report and in the review text, so it travels with the document;
- in the downloads: a `PROTOTYPE.txt` in the zip (the code files themselves are not altered).
The wording is the same everywhere: 'Prototype code. Generated to show the idea and to be tried out. It is not production code: have production code written and reviewed outside this tool.' A green gate means 'passed this prototype's checks', and the screen says so.
**Linking to git is for later** (the user: 'we will add the linkage from git later'); parked as D18 in PROGRESS.md.
