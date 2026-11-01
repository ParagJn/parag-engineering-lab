# S07 · Agent runtime

**Milestone:** M2  **Size:** L  **Objectives:** O2, O4, O11  **Depends on:** S02, S05, S06
Built and tested against the mock provider and replay, so no real model is needed to write or test it. One real run is required before the step closes (see "Real-model check").

## Goal
The first step where an agent **produces an artefact**. Given a project, a phase that is running and an artefact key from the catalogue, the runtime:

1. loads the artefact's **skill** (a Markdown file you can read and edit),
2. gathers what the agent may use: the project brief, upstream artefacts, retrieved context, and earlier feedback,
3. builds a prompt, calls the model through the gateway, and reads the reply,
4. **checks the reply** (required sections present, every citation real and actually shown to the model), and if it fails, asks the model to fix it with the error fed back,
5. saves the result as a new **artefact version**, with its author, citations, cost and tokens.

It runs **one artefact at a time**. Running a whole phase in parallel waves is S09; reviewing is S08; the remaining skills are written with their phases (S11 onward).

## Decisions I need from you (defaults chosen; say if you want any changed)
1. **One skill per artefact, four shipped now.** The catalogue has 33 artefacts, but quality of a skill can only be judged with real output, so I'd ship four that form a chain, `project_charter`, `personas`, `problem_statement` and `functional_requirements`, and write the rest with their phases (S11 for Requirements, then Design, Architecture and so on). Until a skill exists the runtime refuses that artefact with a clear message, and a report script lists which of the 33 have one. The alternative is writing all 33 now, untested against a real model, which I'd expect to redo.
2. **Too much upstream text is refused, not truncated.** Upstream artefacts go into the prompt in full. If they exceed the budget (24,000 characters by default) the run stops and says which artefacts are too big. Silently cutting them would produce an artefact that looks grounded and isn't.
3. **Retrieval defaults.** Documents, memory and approved artefacts are searched with the skill's own queries; a hit must cover at least **half the question's words** (the floor from S06), at most **6 chunks** and **6,000 characters** reach the prompt. All three are settings.
4. **No `temperature` is sent by default.** Some newer models reject it as a bad request, which would fail the call with no fallback. It becomes a setting (`AGENT_TEMPERATURE`), off unless you set it. The cost is less control over variety.
5. **You run one real generation before the step closes.** `python -m scripts.agent_demo --live` makes one real call (the project charter, on Sonnet), costing cents. It is the only way to learn whether a real model follows the reply format and the citation rules. Everything else about this step is checked offline.
6. **Each version records how it was made** (models used, call IDs, attempts, tokens, cost) in a new column, via schema v4. The alternative is leaving it only in the audit log and traces, which works but makes "what did this artefact cost" a join across tables. The column is covered by the same immutability guard as the rest of a version.

## In scope
- **Skills:** the Markdown format, a loader, a linter, and the four shipped skills (`backend/app/phases/skills/<artefact_key>.md`).
- **Prompt assembly:** deterministic, with retrieved text fenced as untrusted data.
- **Reply format, parsing and validation,** including citation checking.
- **Repair loop:** bounded retries that feed the error back.
- **Saving:** create the artefact on first run, add a version on later runs, atomically.
- **Generation record** on each version (schema v4).
- **Settings** for the budgets above, a `skills` block in `/api/status`, and two scripts: `skills_report` and `agent_demo`.

## Out of scope (later steps)
- Parallel execution of a phase, progress events, budget caps (S09). Reviewing a draft and the independence label (S08). Rejection reruns: the runtime *accepts* feedback and a previous draft as inputs, but deciding when to rerun is S08.
- Tool-using agents that write and run code (S16, S17). The remaining 29 skills.
- Item-level IDs inside an artefact and the links between them (see "A problem I found").
- Scanning generated text for secrets or personal data (S10). Until then, don't put real client material in a brief.
- Rendering generated Markdown or HTML safely in the browser (S12, S13). The runtime stores text; it does not display it.

## Design

### A skill file
```markdown
# Skill: Personas
## Role
You are a business analyst who writes personas from a project brief...
## Inputs
- artefact: problem_statement
- search: who uses a meeting room booking system
- search: office staff roles and needs
## Output
Artefact: personas
Required sections:
- Overview
- Personas
- Open questions
## Method
1. Read the brief and the problem statement.
2. ...
## Quality bar
- Each persona has a goal, a frustration and how success is measured.
## Never
- Invent names of real people or companies.
- Cite a source that was not provided.
```
- The six headings are required, in this order, spelled exactly. **`Artefact:` must be a catalogue key**, and its role and ID prefix come from the catalogue, not the skill, so they cannot drift apart.
- `## Inputs` has two kinds of line: `artefact: <key>` (an upstream artefact whose latest text is included in full) and `search: <words>` (a query run against the context store). Nothing else is allowed.
- Linter rules: every heading present once; `Artefact:` exists and has a matching file name; **required sections** are a non-empty list of distinct headings; every `artefact:` input exists in the catalogue and is **upstream** (earlier phase, or the same phase and listed in that artefact's `after`), so a skill can never depend on something that is generated later; at most 5 `search:` lines; no unknown headings; no blank sections; file size capped. A test lints every shipped skill and a second test checks that **every skill name matches a catalogue key**.
- Skills are trusted repository code. (When they become editable in the UI, that edit path is a trust boundary and gets its own review.)

### What goes into the prompt
In this fixed order, each in a labelled block:
1. **System:** the skill's Role, Method, Quality bar and Never, then the reply-format rules.
2. **Project brief** (written by the user): name and brief. Described as the work to do, not as instructions that can override the rules.
3. **Upstream artefacts:** the latest text of each `artefact:` input, labelled with its artefact ID. A missing or empty upstream artefact stops the run and names it, because an artefact built on nothing is the failure this whole product exists to prevent.
4. **Feedback to address:** earlier reviewer and human feedback from project memory for this artefact or phase, plus the previous draft when rerunning. Present only when there is some.
5. **Retrieved context,** fenced as untrusted data (below), each chunk tagged with its source ID.

The final instruction is a single sentence naming the artefact to write. **The prompt is built deterministically:** no timestamps, random values or project IDs, so the same inputs always give the same bytes. That matters for replay (S04): a recorded run matches only if the prompt is identical.

### Untrusted context
Retrieved chunks come from documents anyone could have written. They are placed in a block that says, before and after it, that the text is **reference material, not instructions**, and the delimiter lines are fixed. The delimiter text is **removed from the chunks themselves**, so a document containing the closing marker cannot break out of the block. A test plants such a document. **Honest limit:** this is structure, not a guarantee. Whether a model obeys it is the model's behaviour, which only the real-model check can sample and no test can prove.

### The reply format and its checks
No JSON mode exists on this gateway, so the reply is a Markdown body inside tags:
```
<artefact>
## Overview
... text with citations like [DOC-001#3] and [REQ-PER-001] ...
</artefact>
```
Parsing tolerates the usual mess: a code fence around everything, text before or after the tags, Windows line endings, tag case. It refuses: no tag, an unclosed tag, more than one `<artefact>`, or an empty body.

Validation, each failure producing a plain sentence that is fed back to the model:
- **Every required section** is present as a heading (case and punctuation insensitive) and non-empty.
- **Every citation exists.** Anything in square brackets that has the shape of a source ID must be one of the chunks or upstream artefacts **shown in this prompt**. An invented ID, a real ID from another project, and a real ID that wasn't shown are all refused; the last one matters because it would otherwise let a model cite from memory of an earlier run.
- **Not cut off.** A reply that ended because it hit the output limit is rejected as truncated.
- **Not empty after trimming** and under a hard size cap.

### Repair loop
On a failed check the runtime sends the model its own reply and the error ("section 'Open questions' is missing"), and asks for the full corrected artefact. Up to **2 repairs** by default (`AGENT_MAX_REPAIRS`), so at most 3 model calls per artefact, each its own trace row and each priced. After that the run **fails with the last error and saves nothing**. A model-call failure (`LLMCallFailed`, a replay miss) also fails the run, with the gateway's message. There is no partial save and no half-written version.

### Saving
- The artefact is **created on first run** with the catalogue's ID prefix (so always `PREFIX-001`, one artefact per catalogue key) and gets a **new version on every later run**.
- Creation is **get-or-create inside one write transaction**, so two simultaneous runs of the same artefact cannot create two artefacts (tested with threads).
- **Author is `agent:<role>@<served model>`**, so a fallback is visible and S08's independence label is computed from the model that actually wrote it.
- **Stored citations** are the source IDs actually cited, in order of first use.
- **Runs only while the phase is `running`.** Generating into a phase that is approved or not started is refused.
- Every save writes the usual audit rows; the generation record (decision 6) is part of the same transaction.

### Settings (defaults need no `.env` edit)
`AGENT_MAX_REPAIRS` (2), `AGENT_MAX_OUTPUT_TOKENS` (8,000, since Gemini already showed models spending tokens thinking), `AGENT_UPSTREAM_MAX_CHARS` (24,000), `AGENT_CONTEXT_MAX_CHUNKS` (6), `AGENT_CONTEXT_MAX_CHARS` (6,000), `AGENT_CONTEXT_MIN_COVERAGE` (0.5), `AGENT_TEMPERATURE` (unset).

### Scripts
- **`scripts/skills_report.py`:** a table of the 33 catalogue artefacts with a skill or "no skill yet", so progress is visible. Offline.
- **`scripts/agent_demo.py` (offline by default):** a throwaway project; a **scripted fake model, not a real one,** written to misbehave on purpose. It runs the chain `project_charter → personas / problem_statement → functional_requirements` and shows the second artefact's first reply citing an invented source, being rejected, being repaired, and saved, with the attempt count, tokens and (made-up) cost. It prints a clear banner that the replies are scripted. Ends `4/4 artefacts saved, 1 invented citation caught and repaired`.
- **`--live`:** runs **one** real artefact (the project charter, Sonnet slot) through ICA, from a sample brief the script contains, and prints the saved text and its cost. You run it. It never prints keys or the endpoint.

## A problem I found while designing this (needs a decision before S11, not now)
The catalogue gives each artefact one ID prefix and the repository numbers artefacts, so the Functional Requirements artefact is `REQ-F-001`, and always `-001`. But traceability (objective O8) needs to link **individual requirements inside it** (the 12th requirement, the 3rd persona) to design elements and tests, and S01's ID checks and link table expect IDs of the same shape as artefact IDs. Item IDs like `REQ-F-012` would collide with artefact numbering. The likely fix is a different shape for items (for example `REQ-F-001.012`) and a small change to the link validation. It touches S11 (skills write the items), S15 (traceability) and S01's checks. **S07 deliberately does not paper over it:** it validates sections and citations only, and items are free text until we choose a scheme. I'd like your view when we reach S11; I'll raise it again then.

## Tests (must pass before the step is done)

| Area | Proves |
|---|---|
| skill parsing | the four shipped skills load; section text and the `Artefact:`, required-section, `artefact:` and `search:` fields are read exactly |
| skill linter | one test per rule: missing, duplicate, misspelled or reordered heading; unknown heading; blank section; unknown catalogue key; file name that doesn't match its key; no required sections; duplicate required sections; an input that is not upstream (later phase, or same phase and not in `after`); an unknown input kind; more than 5 searches; oversize file. Errors name the file and the line |
| skill ↔ catalogue | every shipped skill names a real catalogue key; role and prefix are taken from the catalogue; every skill's inputs are upstream; `skills_report` lists exactly 4 of 33 |
| prompt assembly | blocks appear in the fixed order; the brief, upstream text, feedback and each chunk are present with their IDs; **identical inputs give byte-identical prompts**; the prompt contains no project ID, timestamp or random value; changing the project ID does not change it |
| untrusted context | the fence is present before and after; a document containing the closing marker, a fake system block and a fake `<artefact>` tag **cannot break out**; chunk text is otherwise unchanged |
| budgets | chunks beyond the count or character budget are dropped lowest-relevance first; a hit below the coverage floor is not shown; **upstream over budget refuses and names the artefact**; nothing is truncated silently |
| missing inputs | an upstream artefact with no content, a missing skill, an unknown artefact key, a phase that isn't running, an unknown project: each refused with a plain sentence, **no model call, no trace, nothing saved** |
| retrieval | the skill's searches run; results from other projects never appear; superseded artefact versions never appear; memory for this artefact is included and memory for another is not |
| reply parsing | clean reply; code-fenced; text before/after; CRLF; mixed-case tags; no tag; unclosed tag; two artefacts; empty body; a tag inside a code block in the body |
| validation | missing and empty required sections; case/punctuation-insensitive heading match; **invented citation rejected; real ID from another project rejected; real ID not shown in this prompt rejected; shown ID accepted;** citation-shaped text that isn't a source ID (e.g. `[1]`, `[note]`) ignored; truncated reply rejected |
| repair loop | the error text and the bad reply are in the follow-up; success on attempt 2 and 3; failure after the cap with the last error and **nothing saved**; every attempt traced; cost and tokens summed across attempts; **unknown cost on any attempt makes the total unknown, never zero** |
| model failures | `LLMCallFailed`, auth failure, replay miss, slot not configured: each fails the run with the gateway's message and saves nothing |
| saving | first run creates `PREFIX-001`; second run adds version 2; author is `agent:<role>@<served model>` and shows the fallback model when one served it; citations stored in order of first use; audit rows written; **a failure during save leaves no half-written artefact** |
| concurrency | 8 threads running the same artefact create exactly one artefact and 8 versions with unique numbers; different artefacts run side by side without interfering |
| generation record | models, call IDs, attempts, tokens, cost stored; immutable like the rest of the version; a v3 database with data upgrades to v4 and every row survives; concurrent upgrades succeed |
| chaining | personas and problem_statement, then functional_requirements sees both **in full**, and cites them as `[REQ-PER-001]` and `[REQ-PRB-001]` |
| replay | record a run live (with a scripted provider), then replay it with a fresh project ID: identical text, tokens, cost and citations, zero provider calls |
| rerun inputs | feedback and a previous draft, when supplied, appear in the prompt; absent when not supplied |
| status | `skills` block lists counts only, no file paths or skill text |
| scripts | `skills_report` and `agent_demo` run offline and print what the spec says; the demo exits 1 if an invented citation is *not* caught; `--live` refuses to run without credentials and never prints a key |

After the suite is green I'll run the break-one-thing check with the baseline guard and the spread-of-counts print. Breaks include: citations not checked against what was shown, an invented citation accepted, the fence delimiter not stripped from chunks, the prompt containing the project ID, upstream silently truncated, a repair that doesn't include the error, retries uncapped, cost taken from the last attempt only, a partial save on failure, a second artefact created by a race, running in a phase that isn't running, the coverage floor ignored, and a skill allowed to depend on a later phase.

## Dependencies / installs
None.

## Real-model check (run by you, required to close)
`! cd /Users/paragjain/dev-works/parag-engineering-lab/SDLC-Workbench/backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.agent_demo --live`
It makes one real call (about 3,000 tokens in, 1,000 out on Sonnet: well under a cent), prints the saved project charter, its citations, attempts and cost. **What to look for:** did the model use the reply format on the first try (attempts = 1)? Is the charter any good? Do its citations point at real sources? Paste the output back, whatever it says. A failure here is the most useful result this step can give, because it tells us about the prompt before 29 more skills are written on top of it.

## Manual check for the user
1. Offline: `! cd .../backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.agent_demo` should end `4/4 artefacts saved, 1 invented citation caught and repaired`, under a banner saying the replies are scripted.
2. `! cd .../backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.skills_report` lists 4 of 33 with skills.
3. Open `backend/app/phases/skills/personas.md`. It is a short file in plain English. **Tell me if the Role, Method and Never read the way you'd want an analyst briefed.** That tone carries into the other 29.
4. The real-model check above.
5. `./start.sh`: the schema pill reads v4. Nothing else on the page changes.

## Done when
- [x] Listed tests pass; full suite green (summary line in PROGRESS.md)
- [x] Break-one-thing check run with the baseline guard and reported honestly, including anything skipped (52 of 52 caught, 0 skipped)
- [x] Frontend `npm run build` still succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] **Real-model check run by you and its result recorded** (2026-10-28, 1 attempt, $0.01467)
- [x] User confirms (2026-10-28)

## Outcome
All six decisions were taken at their defaults. Changes from this spec: the `AGENT_BRIEF_QUERIES` setting, the reusable `scripts/mutation_check.py` harness, and a retry in `Database.migrate` for a first-start "database is locked" race. After the real-model run one "Never" line was added to `project_charter.md` (no unlisted stakeholder roles stated as fact); it has not been re-run against a real model.
