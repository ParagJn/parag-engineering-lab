# S12c · Review and decide

**Milestone:** M3  **Size:** L  **Objectives:** O1, O3, O5, O11  **Depends on:** S08, S09, S10, S12a, S12b (all closed)
The last slice of S12 (see `S12-ui-slice.md`). After S12a you can create a project; after S12b you can run Setup and Requirements and read what each agent wrote. After S12c you can **have the work reviewed by a second model, see how independent that review was, send named artefacts back with a note, watch only those be rewritten, fix a line by hand, and approve with a record of what was still open.** That finishes the Requirements story and the first demoable moment (M3).

## What I found before writing this (it changes the plan)

1. **There is a real defect in S12b's work, and S12c has to fix it first.** The runner publishes `review.paused` in **two shapes**: when the reviewer cannot run it sends `{artefact_id, slot, options}`; when the review fails for any other reason it sends `{artefact_id, reason}`. The screen's event decoder only knows the second. I confirmed it: given the first shape it throws "event review.paused.reason: expected text". In the browser that would show as "Progress could not be followed" the moment a reviewer is unavailable, which is exactly the case the family picker exists for. S12b did not catch it because the contract fixture I wrote only produced the second shape. It is fixed in S12c's first step, with a fixture for each shape and a test that fails if the runner gains a third.
2. **Review cannot run in replay mode at all.** A review is a model call whose prompt contains the artefact, and no review has ever been recorded. I ran one against your `phase2` recording: it fails with "no recording for role 'security_reviewer'". Reviews are recorded as part of S24 (the seeded demo). Until then **reviewing needs live mode**, a few cents per artefact. The screen must say that plainly when the server is in replay mode, instead of offering a Review button that cannot work.
3. **The artefact detail does not show review findings.** The findings are already stored on each version (`review_findings`), but `GET /artefacts/{id}` does not return them, and no route can ask for a review, send a phase back, re-run, or edit. S12c adds about **8 routes**. Nothing about review is visible on screen today.
4. **A re-run goes around the scheduler today.** `HumanActions.rerun_rejected` calls the agent runtime itself, one artefact at a time, with no events and no caps. Decision 8 of the S12 spec said the screen's re-run goes through the S09 runner (`only=`), so it streams like every other run. That works for the writing, but the runner's `only` rewrites **exactly the artefacts named**, while `rerun_rejected` picks "those with an unaddressed note". So the route computes the list from the notes and hands it to the runner (decision 4).
5. **The phase is `rejected`, not `running`, after you send changes back.** The runner already restarts a rejected phase on its own (`gate.changed` to running), so no extra step is needed; the phase then waits for you to hand it back to review. S12b's buttons already follow `allowed_actions`, which for `rejected` is "run".
6. **"Review before approve" is not enforced, by design (S08 decision).** Approving records what was open (unreviewed, out of date, high findings) in the audit row rather than refusing. The screen shows that same list *before* you press Approve, so it is a choice you can see, not a surprise in an audit table.

## Decisions I need from you (defaults chosen; say if you want any changed)

1. **Fix the defect first (finding 1), as step one of the slice.** Decoder for both shapes, a fixture for each, and a test that fails if the runner publishes a shape the screen does not decode. No decision needed beyond "yes".
2. **A Review button per artefact, and "Review all" for the phase, available while the phase is running or awaiting review.** It calls the reviewer through the gateway. In replay mode the buttons are replaced by one sentence: "Reviews need live mode: no review has been recorded yet." (finding 2). Review is **never automatic**: it costs money, so a person asks for it. (The run option `review=true` exists from S09; the screen offers it as an unticked "Review each artefact as it is written" box on the Run button, off by default.)
3. **How a review is shown.** On the artefact card: a chip with the verdict (`ok` / `revise`) and the independence label (**independent**, **same family**, **unverified**) in words a reader understands, e.g. "Reviewed by openai (a different model family): independent". In the reader: the summary, then findings grouped by severity (high, medium, low), each with its target (an item ID, a section or "General"), the problem and the suggested fix. A review of an older version is marked **out of date** with a sentence saying which version it covers.
4. **Request changes = a note per artefact, and only those artefacts re-run.** Each artefact in the phase gets a checkbox "Send back" and a note box; ticking it requires a note (the server refuses a blank one). A box "Also give the writer the reviewer's findings" per artefact turns reviewer findings into notes (S08: findings reach the writer only if you ask). An optional phase-wide note. The route validates with the S08 rules; the sentences come from the server. On success the phase shows as **Sent back** with the notes visible.
5. **Re-run goes through the S09 runner.** After sending back, the **Run it again** button starts a run with `only=` the artefacts that have an unaddressed note (the route works that list out; the screen does not). It streams, shows cost and can be cancelled, exactly like S12b. `rerun_rejected` stays as it is (tested, used by scripts) and is documented as the non-streaming version. A failed artefact keeps its old version and the run panel says why.
6. **Stale artefacts are shown, never re-run behind your back (S08).** A banner on a phase lists artefacts built on an upstream version that has since changed ("Functional requirements was built on Personas v1; Personas is now v2"), with a **Re-run these** button that you press. Nothing happens by itself.
7. **Edit by hand.** An **Edit** button in the reader (while the phase is running or awaiting review) opens the artefact's Markdown in a text area with an optional note. **Save** sends it to the server, which applies *every* check an agent's reply passes (structure, citations, items, secrets). A refusal shows the server's reasons as a list and **saves nothing**; the text you typed stays in the box. A saved edit is a new version by you (`human:<name>`), shown with "edited by <name>"; it replaces the links the artefact declared. An edit makes an earlier review out of date and marks artefacts built on it as stale.
8. **The family picker.** When a reviewer cannot run, the server answers with the other families that could, each with model, family, whether it is independent of the writer, and its price per million tokens ("unknown" if unpriced, never zero). The screen shows them as a list; **you pick one and press Review**, and the review runs with that choice. **Nothing is switched for you** (S08). If the choice fails too, the list comes back without it.
9. **The approval record is shown before and after.** Before you press Approve: a summary of what is open: artefacts never reviewed, reviews out of date, high findings, artefacts built on something that changed, guardrail flags. After: the same list as the server recorded it. Approving is **never blocked** by it (finding 6); the button says "Approve anyway" when anything is open. This replaces S12b's "nothing has been reviewed by a second model yet" line with the real list.
10. **Mutation check and test approach as before.** Contract fixtures for every new response and both event shapes; static-render tests for each component; a mutants file for the new backend with the baseline guard, the compile check and the hung-suite rule; a literal pinned for every sentence a person reads (the S12b lesson). Frontend still has no mutation check; I will say so again rather than imply coverage.

Stated, not asked: all server text is shown as text; new routes need `X-Actor` and are refused on an archived project with the standard sentence; the screen decides nothing about which buttons exist (it reads `allowed_actions` and the new review status); no new packages; cost of the live check is cents.

## In scope
- **Fix:** `review.paused` decoder (both shapes) and the fixtures/tests for it.
- **Backend routes** (new file `app/routes_review.py`; payloads written field by field):
  - `POST /api/projects/{id}/artefacts/{aid}/review` (body: optional `slot`, `exclude`), answers the result, or `409`-style `paused` with the options
  - `POST /api/projects/{id}/phases/{key}/review` (review every written artefact; paused ones are reported with options)
  - `GET /api/projects/{id}/phases/{key}/review` (status of each artefact's review, the stale list, and the "what is open" summary used before approving)
  - `POST /api/projects/{id}/phases/{key}/request-changes` (notes, overall note, which artefacts also pass on findings)
  - `POST /api/projects/{id}/phases/{key}/rerun` (works out the artefacts with an unaddressed note and starts an S09 run with `only=`)
  - `PUT /api/projects/{id}/artefacts/{aid}` (edit by hand; `422` with the list of reasons)
  - `GET /api/projects/{id}/artefacts/{aid}` gains `review` (the stored record for the shown version, with the independence label) and `review_status`.
  - Approve's answer gains the recorded "what was open".
- **Frontend:** review chip and findings, Review and Review-all buttons, the replay-mode sentence, the Request-changes form, stale banner, Edit view, family picker, the approval summary, and the decoders and reducers for them.

## Out of scope (later)
- Recording reviews so they replay (S24); the cost and trace screens (S22); reopening an approved phase (a reopen route exists in the engine; no screen yet); deleting or renaming projects; the Design phase and later (S13 onward).

## Design notes
- **Files:** backend `app/routes_review.py` (so no file passes what can be read in one sitting); frontend `src/components/` (`ReviewChip`, `FindingsList`, `RequestChangesForm`, `EditArtefact`, `FamilyPicker`, `ApprovalSummary`, `StaleBanner`), `src/api/review.ts` (decoders), `src/state/` for the form state.
- **Paused review shape:** `{paused: true, artefact_id, slot, options: [{slot, model_id, family, independent, price_input, price_output, priced}]}`. `independent` can be `null` (unknown family), shown as "unverified", never as independent.
- **What a response may contain:** no prompts, raw replies, keys, the endpoint or paths. Review text (summary, findings) is model output and is shown as text. The S12b privacy test is extended to every new route with planted values.
- **Mode:** the server tells the screen whether reviews can run (`GET /api/modes` gains `reviews_available`), so the replay sentence comes from one place.
- **Costs:** every review shows its cost, or "unknown"; a review adds to the run total if it ran inside a run.

## Tests (must pass before the slice is done)

| Area | Proves |
|---|---|
| the S12b defect | the screen decodes both `review.paused` shapes; a fixture for each; a test fails if the runner publishes a shape not in the fixtures |
| review routes | a review stores findings on the right version and returns the independence label (independent / same family / unverified); a human-written version counts as independent; replay mode returns the "needs live mode" answer, not a crash; an unknown artefact is 404; `X-Actor` required; archived is refused |
| paused review | an unavailable reviewer returns the options with price (unknown not zero) and independence, stores nothing, and switches nothing; choosing one runs the review with it; a second failure returns the list without the failed one |
| request changes | needs at least one artefact and a note per artefact; the phase must be awaiting review; notes and the decision are saved together; findings pass on only when asked; every refusal is the server's sentence; the phase becomes `rejected` |
| re-run | the artefacts chosen are exactly those with an unaddressed note (+ named extras); it runs through the S09 runner (events, caps, cancel); a failed artefact keeps its old version; later artefacts read earlier rewritten ones |
| stale | an upstream change marks dependants stale; nothing re-runs by itself; re-running them is an explicit call |
| edit | a valid edit saves a new `human:` version; an invalid one (bad citation, secret, wrong structure, empty) saves nothing and lists every reason; only while running or awaiting review; links are replaced; an earlier review becomes out of date |
| approval record | the summary before approving equals what the audit row records after; approving is never blocked by it |
| privacy | planted prompt, reply, key, endpoint and path text appears in no new response |
| contract | a fixture per new response and per event shape; each decodes with the screen's decoders; a renamed field fails a test |
| components | static render: review chip (every verdict and label), findings, replay sentence, request-changes form (note required), stale banner, edit view with refusals, picker (unknown price, unverified family), approval summary ("Approve anyway"); untrusted text stays inert |
| unchanged | the full backend suite passes; every changed existing test is listed in PROGRESS |
| break-one-thing | a mutants file for the new backend, run with the baseline guard, compile check and hung-suite rule; every survivor is a test gap; unkillable breaks are named, not counted |
| build | `npm test` and `npm run build` pass |

## Dependencies / installs
None. The live check costs a few cents (reviews).

## Questions for the user
Decisions 1 to 10. The ones that most change the work: **2** (review is always a button you press, never automatic, and impossible in replay), **4 and 5** (the request-changes form and the re-run through the runner), and **7** (editing in a plain text area, not a rich editor).

## Manual check for the user (we do not run the app)
1. Set `APP_MODE=live`, restart, open a project that has Requirements written (or run it live).
2. Open one artefact and press **Review**. Read the verdict, the independence label and the findings. Press **Review all** for the phase.
3. In replay mode (switch back): the review buttons are replaced by the sentence about live mode.
4. To see the picker, make the reviewer unavailable (blank its model ID in `.env`, restart) and press Review: you should get a list of other families with prices; pick one.
5. **Hand to review**, then **Request changes**: tick one artefact, write a note, send. The phase shows **Sent back**. Press **Run it again**: only that artefact re-runs, streaming; the others are untouched.
6. Open an artefact and **Edit**: break a citation on purpose and Save; read the refusal and check nothing was saved. Fix it and Save; see "edited by <you>" and the earlier review marked out of date.
7. Edit an upstream artefact and look for the stale banner on the ones built on it; press **Re-run these**.
8. Look at the approval summary, then **Approve**; compare the list afterwards.
9. Tell me what is wrong, missing or confusing in the functionality; look and feel waits.

## Done when
- [x] Listed tests pass; full suite and `npm test` green (backend 2057, frontend 431; summary lines in PROGRESS.md)
- [x] Break-one-thing check run with the baseline guard and reported honestly (76 breaks; 16 survivors found and closed, one a real defect; 12 + 14 hand breaks of the frontend)
- [x] `npm run build` succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] **You have run it in a browser and told me what you saw** (2026-10-30: live reviews, the progress gap, the un-approve question)
- [x] User confirms (2026-10-30)
