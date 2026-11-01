# S08 · Reviewer and human-in-the-loop

**Milestone:** M2  **Size:** M  **Objectives:** O3, O5, O8  **Depends on:** S02, S05, S07, S11
Built and tested against the mock provider, so no real model is needed to write or test it. One real run is required before the step closes (see "Real-model check").

## Goal
After this step, an artefact an agent wrote can be **reviewed by a second model**, and a person can **act on the result**: approve the phase, send named artefacts back with written feedback so that only those are rewritten, or edit an artefact by hand. Every review says plainly whether it is independent of the author's model family. Nothing is applied silently and no agent ever decides a gate.

Most of the machinery already exists and is reused, not rebuilt: the gateway's `review()` with its independence label and the "pick another family" error (S02), the `review_findings` column on a version (S01, the one field that may change after a version is written), phase approve and reject (S05), project memory (S01) and the runtime's feedback input (S07). What is new is the reviewer's prompt and reply format, the human actions on individual artefacts, and the rules that tie them together.

## Decisions I need from you (defaults chosen; say if you want any changed)

1. **A review advises; the person decides.** Findings never block an approval by themselves. (A real quality gate that blocks on failing tests or a serious finding arrives with the code in S18.) To keep this honest, an approval is recorded in the audit log with how many high-severity findings were still open and how many artefacts had never been reviewed. The alternative, blocking approval until every high finding is dealt with, would stop you demonstrating a deliberate "approve anyway", and would make a reviewer outage block the whole project.

2. **What the reviewer is shown.** The artefact under review; the skill's own quality bar and "never" list; a short generic rubric you can edit (`backend/app/phases/review/rubric.md`); the upstream artefacts it was built on, in full; and **the text of every source it cites**, fenced as untrusted data. The last item is deliberate: in S11 I told you the system checks that a cited ID was shown to the model but not that the text supports the claim. Showing the reviewer the cited text is how a second model gets to check that. It is a model's judgment, not proof. Cost: I expect about 2 to 3 cents per artefact on Sonnet (estimated from the S11 token counts, not measured) and 15 to 20 cents for the seven Requirements artefacts; the demo prints the real figure.

3. **The verdict is computed by the system, not by the model.** The reviewer lists findings, each with a severity (high, medium or low), a target (an item ID such as `FR-004`, a section name, or `General`) and a suggested fix. The system reads them, rejects a finding whose target does not exist in the artefact (sent back for repair, like a bad citation), and sets the verdict itself: any high finding means `revise`, otherwise `ok`. A model therefore cannot write "looks great" next to a list of serious problems.

4. **Rejection is targeted, feedback is kept, and nothing downstream is re-run behind your back.**
   - You reject a phase with written feedback **per artefact** (and optionally one phase-wide note). At least one artefact must be named. Only the named artefacts are rewritten; the others are not touched.
   - Every note is saved to project memory permanently (searchable, citable as `MEM-nnn`). The writer sees a note **until a newer version of that artefact exists**, then it is considered acted on. That is a change to how S07 chooses feedback (today a note is shown forever), and the existing tests for it are updated.
   - **The reviewer's findings are not sent to the writer unless you choose to.** Per artefact, you can say "include the reviewer's findings". The principle from the design docs: findings are stored, not silently applied.
   - Because artefacts build on each other, rewriting `Functional requirements` makes `Epics and features` out of date. Each version now records which versions of its upstream artefacts it was built on, and the system **flags** the ones built on something that has since changed ("built on REQ-F-001 v1, now v2"). It does not re-run them; you choose whether to include them. Re-running everything downstream by default would spend money and replace work you may have been happy with.

5. **A human edit is a new version, held to the same rules as an agent's.** It is saved as a new version authored `human:<name>`, with the earlier version kept. Before saving, the system runs the same checks as for an agent: required sections present, item IDs well formed and not reused, every `Derives from` pointing at something real, every citation resolving to a real source. A failing edit is refused with the reasons in plain words, so a hand edit cannot quietly break the IDs that later phases depend on. Editing is allowed while the phase is running or awaiting review. An earlier review of the old version is marked **stale**; it is not carried over.

6. **Fix a defect I found in S11: a new version must replace its artefact's links.** Today links are only ever added. I probed it: version 1 declared `PER-002 → SET-CHR-001`; version 2 declared `PER-002 → PER-001` instead; the table held both, so it no longer matched the text. That is harmless while each artefact is written once and wrong the moment it is rewritten, which is exactly what this step enables. The change: when a version is saved, by an agent or a person, the links that artefact had declared are replaced by the links the new version declares, in the same transaction, with an audit row for each link removed (the audit log is append-only, so the history is not lost). It touches S01's link code and S11's save. The cost of leaving it: the traceability matrix in S15 would be built on links no document states.

7. **Human-written versions count as independent.** Independence is about model families, and no model wrote a human edit, so a review of one is labelled `independent` with the author shown as `human`. Everything else about reviewers is unchanged from S02: Sonnet reviews; if it cannot run, you are shown the other families (independent ones first) and choose; I never switch for you.

8. **You run the review against a real model before the step closes.** `python -m scripts.review_demo --live` writes one project charter with a real model, then has it reviewed by Sonnet and, optionally, by a second family you name, so you see both labels. About 2 to 3 real calls, costing cents. The offline version of the script (the default) uses a scripted fake model, labelled as such, exactly like `agent_demo` and `requirements_demo`.

## In scope
- **Reviewer** (`backend/app/review/`): rubric file and its linter; prompt builder (artefact, quality bar, rubric, upstream, cited sources, all fenced as untrusted); reply parser for the `<review>` block with a bounded repair loop; findings validation (target exists, at most 20 findings, severities known); verdict computed by the system.
- **Review service**: review one artefact's latest version; review every artefact in a phase, where an unavailable reviewer pauses only that artefact and reports the options; a re-review replaces the stored findings (each one is audited); review status per artefact (`unreviewed`, `reviewed`, `stale`).
- **Findings record** stored on the version: summary, findings, verdict, reviewer slot, model and family, the independence label, the version reviewed, tokens, cost, call IDs. No schema change (the column already exists).
- **Human actions** (`backend/app/review/human.py`): request changes (targeted rejection with notes saved to memory, in one transaction with the phase decision); re-run the rejected artefacts; edit; approve with the audit record described in decision 1.
- **Stale detection**: a generation record now lists the upstream versions each artefact was built on; a report names artefacts built on something that has changed.
- **Link replacement** (decision 6) for agent and human saves.
- **Runtime change**: feedback selection (decision 4), and the deterministic checks moved into one function that both the runtime and a human edit call.
- **Settings** (all optional, with defaults): `REVIEW_MAX_OUTPUT_TOKENS` (3000), `REVIEW_MAX_REPAIRS` (1), `REVIEW_MAX_FINDINGS` (20), `REVIEW_CITED_MAX_CHARS` (8000 of cited source text per review).
- **Status**: a `review` block on `/api/status` (reviewer slot, whether the rubric loaded). No paths, no text.
- `scripts/review_demo.py`.

## Out of scope (later steps)
- **HTTP endpoints and screens.** S08 is a service layer plus a script, so the page does not change. Routes arrive with the event stream in S09 and the UI in S12, and I will say so when they land. The service is written so a route is a thin wrapper.
- Reviewing several artefacts in parallel (S09). S08 reviews them one after another.
- Secret and PII scanning (S10).
- A blocking quality gate on findings (S18).
- Skills the reviewer learns from your edits or rejections. Notes are kept in memory; nothing is trained or tuned from them.
- Reviewing code, tests or deployment files. The reviewer here reads text artefacts.

## Design notes

**Review reply format** (the same family of rule as `<artefact>`):

```
<review>
Summary: one or two sentences.
- [HIGH] FR-004: The requirement says X, but the cited policy text says Y. Fix: change X to Y.
- [LOW] Open questions: two questions are really one. Fix: merge them.
</review>
```

The parser reads `Summary:` and one bullet per finding. A target must be an item ID present in the artefact, a section heading present in it, or `General`; anything else is sent back with the reason, once (`REVIEW_MAX_REPAIRS`). No findings is allowed (`Summary:` alone) and gives verdict `ok`. A reply that is truncated, has no block, or has more than the findings limit is refused the same way an agent's reply is.

**Findings record** (stored as JSON on the version):

```
{ "version_reviewed": 2, "verdict": "revise", "summary": "...",
  "findings": [ {"severity": "high", "target": "FR-004", "problem": "...", "fix": "..."} ],
  "reviewer": {"slot": "sonnet", "model": "claude-sonnet-5-5", "family": "anthropic"},
  "independence": {"verdict": "same_family", "author_family": "anthropic", "reviewer_family": "anthropic", "fell_back": false},
  "tokens_in": 6100, "tokens_out": 900, "cost_usd": 0.0212, "call_ids": ["..."], "attempts": 1 }
```

`cost_usd` is `null` when any attempt's price is unknown, never a partial sum, as everywhere else.

**Action rules.** The state machine from S05 is unchanged; these are the rules on top of it:

| Action | Who | Phase must be | Effect |
|---|---|---|---|
| review an artefact | system or person | running or awaiting review | findings stored on the latest version |
| request changes | person | awaiting review | phase becomes `rejected`; notes saved to memory, in one transaction with the decision; at least one artefact named |
| re-run rejected | person | rejected | phase restarts; only artefacts with an unacted note are rewritten (plus any you add from the stale list); phase is left running for you to hand back to review |
| edit | person | running or awaiting review | new `human:` version after the checks in decision 5; links replaced |
| approve | person | awaiting review | S05's rules, plus the audit record in decision 1 |

An agent can do none of the "person" actions: the repository already refuses an agent as the actor of a gate, and the new actions refuse it too.

**Where the pieces go.** The two transactional pieces go in `repos.py` next to the code they extend: `PhaseRepo.reject_with_notes` (the phase decision and the memory rows commit together, so a rejection can never exist without its notes or the reverse) and link replacement inside the version-save path. The rest is new modules under `app/review/`, so nothing in the gateway changes. The only edits to existing behaviour are the three called out: feedback selection (decision 4), link replacement (decision 6), and the extra field in the generation record.

**Untrusted content.** The artefact under review was itself written by a model that read possibly hostile documents, and the cited source text is hostile-by-default, so both are fenced and neutralised exactly as in S07. The honest limit: a poisoned artefact could try to persuade the reviewer to report nothing. The verdict being computed from findings means it cannot make a serious finding disappear from a list that exists; it can still lead to an empty list. A reviewer is a second opinion, not a guarantee.

**Costs and caps.** The reviewer's upstream text has the same size limit as the writer's and is refused rather than cut; cited-source text is capped per review (`REVIEW_CITED_MAX_CHARS`) and a source that would not fit is named in the prompt as omitted, never half-shown.

## Tests (must pass before the step is done)

| Area | Proves |
|---|---|
| review reply parser | a valid block is read; one test per refusal: no block, unclosed, two blocks, unknown severity, a target that is not in the artefact, more findings than the limit, a finding with no problem text, truncation; `Summary:` alone is valid; text in code fences is ignored; the repair message names the line at fault |
| verdict | any high finding gives `revise`; medium and low only give `ok`; no findings gives `ok`; a reply that says "pass" in prose but lists a high finding is `revise` |
| reviewer prompt | the artefact, quality bar, rubric, upstream artefacts and cited source text are present; each is fenced and a hostile marker inside any of them cannot break out; identical inputs give byte-identical prompts; an over-budget upstream is refused naming the biggest; an oversize source is named as omitted, never cut |
| independence | a Sonnet-written artefact reviewed by Sonnet is `same_family`; written by the OpenAI slot, `independent`; a human version is `independent` with author `human`; an unknown family is `unverified`; a fallback model is shown as `fell_back` |
| unavailable reviewer | Sonnet failing raises the options with independent families first and the failed slot excluded; the chosen slot is used and labelled; no model is ever switched without a choice; in a phase review only the unavailable artefact pauses, the others finish |
| findings record | stored on the reviewed version only; carries the version reviewed, model, label, tokens, cost (`null` when a price is unknown); a re-review replaces it and is audited; a second version has none until reviewed; a review of an edited artefact reads `stale` |
| request changes | needs a person (an agent is refused); needs at least one named artefact; refuses outside awaiting review; decision and memory rows commit together (a forced failure leaves neither); notes are saved as `human_feedback` with the artefact ID |
| re-run | only named artefacts are rewritten; unnamed ones keep their version; the note appears in the writer's prompt, and the previous draft too; reviewer findings appear only when asked for; the phase is left running; a failing artefact leaves the others intact |
| feedback consumed | a note is shown until a newer version of that artefact exists and then no longer; it stays in memory and is searchable; a phase-wide note reaches every re-run artefact |
| stale detection | after rewriting one artefact, exactly the artefacts built on its old version are listed; none when nothing changed; older versions without the record are reported as unknown, not stale |
| human edit | a valid edit saves a `human:` version with a note and the version it was based on; each check that refuses an agent's reply refuses the edit (missing section, reused or invented ID, unknown `Derives from`, unresolvable citation) with plain reasons and saves nothing; refused when the phase is approved or not started |
| link replacement | a new version's links replace the old; a removed link leaves an audit row; an unchanged link is not rewritten; links declared by other artefacts are untouched; a failed save leaves the old links; the probe from S11 (v1 to v2) now ends with exactly v2's links |
| approval record | approval writes how many high findings were open and how many artefacts were unreviewed; an agent still cannot approve; S05's gate rules are unchanged |
| status | the `review` block has the slot and a rubric flag and contains no path or rubric text |
| script | `review_demo` offline prints each step, says it is scripted, exits 0; `--live` refuses without credentials and names which; never prints a key or the endpoint |
| unchanged | the whole existing suite passes; every changed existing test is listed in PROGRESS |
| break-one-thing | a mutants file for S08, run with the baseline guard; every survivor is a test gap to fix, reported with the count and the spread |

## Dependencies / installs
None.

## Questions for the user
Decisions 1 to 8 above. The ones that most change the work: **4** (how rejection and feedback behave; it changes S07's feedback rule), **6** (a fix to closed code in S01 and S11) and **1** (reviews are advisory).

## Manual check for the user (we do not run the app)
1. `python -m scripts.review_demo`: runs the offline walk-through and ends with a one-line result for each of: a review labelled `same_family`, one labelled `independent`, a paused review with the family picker, a targeted rejection where only one of three artefacts is rewritten, a human edit, a refused edit, and an approval record. A banner says it is a scripted fake model.
2. Open `backend/app/phases/review/rubric.md`. It is a short plain-English list of what the reviewer checks. **Tell me if it reads the way you want a reviewer briefed**; that tone carries into every later phase.
3. `python -m scripts.review_demo --live` (cents): read the real findings. Are the targets real, is each problem actually in the artefact, and does the independence label match who wrote and who reviewed? If you name a second family (`--second openai`), you should see `independent` on that one.
4. The page does not change; the schema pill still reads v4.

## Done when
- [x] Listed tests pass; full suite green (1400 passed)
- [x] Break-one-thing check run with the baseline guard and reported honestly, including anything skipped (82 of 82 caught, 0 skipped; 8 survivors found on the first run and fixed)
- [x] Frontend `npm run build` still succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] **Real-model review run by you and its result recorded** (2026-10-28: Sonnet and OpenAI reviews; labels correct; repair fired on both)
- [x] User confirms (2026-10-28, "looks good to me")
