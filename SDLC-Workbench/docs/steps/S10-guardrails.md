# S10 · Guardrails

**Milestone:** M3  **Size:** S  **Objectives:** O9  **Depends on:** S01, S07, S08, S09
Deterministic, so no model is needed to build, test or close it. The one check I ask you to run is local and free (see decision 8).

## Goal
After this step, a secret or a piece of personal data cannot slip into a saved artefact unnoticed. A **scanner** (pure code: patterns, checksums and an entropy test, no model) reads the text of every artefact before it is saved. **Secrets are refused**, and an agent is told to take them out through the same repair loop that already handles invented citations. **Personal data is flagged**: the version is saved with the findings attached, and the approval record counts them. The scanner is a plain function, so S18 (code review) and S19 (the deploy gate, "planted fake secret blocks deploy") reuse it on generated files without change.

## Why this matters more here than in most apps
An artefact version is **immutable** (S01 triggers) and, once approved, **searchable** (S06) and **shown to later models** as upstream material. A secret that gets in can never be removed and keeps being sent to a third party. So the right moment to stop it is before the save, not after.

## Decisions I need from you (defaults chosen; say if you want any changed)

1. **Secrets block; personal data flags.** A secret-class finding stops the save: for an agent it becomes a repair problem ("line 14 looks like an AWS access key; remove it"), and if the model still writes it after its repairs the artefact is **not saved**, exactly like any other invalid reply. For a person's edit it is refused with the reason. A personal-data finding does **not** stop the save: the version is saved, the findings are stored with it, and the approval record lists the artefacts that carry any. Reason for the split: a secret is never legitimate in an artefact, while an email or phone number sometimes is (a named support contact), and blocking it would make the tool fight the person using it.
2. **Four places, one scanner.**
   - **An agent's reply and a person's edit**, through the shared `check_body` from S08 (so they cannot drift apart). This is the one that talks back to the model.
   - **A last-line refusal inside the repository**, on every new version, for the high-confidence secret rules only (not the generic-assignment rule, which can misfire). It exists so a future code path that forgets the scanner still cannot store a token. It raises a plain error and saves nothing.
   - **A reviewer's reply** (summary and findings), because a reviewer told to "quote a few words" could quote a secret out of a cited document, and a stored review is kept for good. Same rule: secrets go back through the repair loop.
   - **Uploaded documents**: scanned and **flagged, never blocked** (decision 6).
3. **What it detects.** Fourteen rules. Please veto any you don't want; the two marked * are the likeliest to misfire.

   | Rule | Class | Finds |
   |---|---|---|
   | `private_key` | secret | a `BEGIN ... PRIVATE KEY` header |
   | `configured_credential` | secret | any value in this backend's own settings (ICA key, OpenAI key, endpoint, user-agent), exact match, 4+ characters |
   | `aws_key_id` | secret | `AKIA` or `ASIA` followed by 16 letters or digits |
   | `github_token` | secret | `ghp_` `gho_` `ghu_` `ghs_` `ghr_` with 30+ characters, or `github_pat_` |
   | `slack_token` | secret | `xoxb-` `xoxp-` `xoxa-` `xoxr-` `xoxs-` and a body |
   | `stripe_key` | secret | `sk_live_` or `rk_live_` with 16+ characters |
   | `google_api_key` | secret | `AIza` followed by 35 characters |
   | `jwt` | secret | three dot-separated base64url segments, the first starting `eyJ` |
   | `url_password` | secret | `scheme://user:password@host` with a real-looking password (not `user:password@`, `<password>`, `${PASSWORD}` and similar placeholders) |
   | `credential_assignment`* | secret | `password`, `secret`, `token`, `api key` and similar, then `=` or `:`, then a single 12+ character value with high entropy and mixed character types, that is not a placeholder |
   | `email` | personal data | an address on a real-looking domain; **not** `example.com/.org/.net`, `.example`, `.invalid`, `.test`, `.localhost` |
   | `phone`* | personal data | a number starting `+` with 8 to 15 digits, or a grouped 10-digit form like `(555) 123-4567`; **not** dates, times, ID codes, version numbers or token counts |
   | `payment_card` | personal data | 13 to 19 digits that pass the Luhn check |
   | `iban` | personal data | a country code and check digits that pass the mod-97 check |

   **What it deliberately does not catch**, so you are not surprised: names and postal addresses (needs language understanding); national ID numbers (formats vary and the prototype uses no real personal data); a secret written in prose ("the password is hunter2"); a secret split across lines or encoded; a token format I have not listed. This is a **safety net for the accidental**, not a defence against someone trying to hide a secret.
4. **A finding never carries the value.** It records the rule, the class, the line number, the section heading it sits under, and the length, and nothing else, because the findings are stored (and a repair problem is stored too, since S09's follow-up) and the point is to keep the value out of every record. A test plants a value and then searches **every table in the database** for it.
   - Stored: in the version's `generation` record as `guardrails` (no schema change, so it is immutable like the rest). A person's edit and an agent's save both carry it.
   - Shown: `artefact.finished` events get a `flags` count (a number, never a rule list); the approval record gains `guardrail_flags`, the artefacts that carry personal-data findings.
5. **One setting to switch rules off, with two that cannot be.** `GUARDRAILS_DISABLED_RULES` takes a comma-separated list of rule names, for when a rule misfires on your data (most likely `phone` or `credential_assignment`). An unknown name stops start-up with a message. **`configured_credential` and `private_key` cannot be disabled**, because a switch that lets your own key into an artefact defeats the objective. Anything switched off is shown in `/api/status`, so it is never silent.
6. **Uploaded documents are flagged, not blocked; the brief and notes are out of scope.** A document is the person's own material, so blocking an upload would be paternalistic; but its text is stored, searched and sent to models, so the person should know. Adding a document returns the findings (rule, line, count) on the result, and the audit row records **counts and rule names only**. Nothing is stored in the document tables (no schema change). The project brief and the notes a person types are not scanned in this step; they are typed by the owner of the machine, and I would rather say so than imply coverage.
7. **Test data is built at runtime; the repo is scanned by its own scanner.** To prove detection you need secret-shaped text, and a public repository must not contain any (hosting services block pushes that do). So every fixture is assembled from fragments inside the test (for example `"AK" + "IA" + ...`), never written out. One test then runs the scanner over every source, doc and config file in this project (never `.env`) and fails if any secret-class finding appears, so a fixture written out by mistake cannot be committed.
8. **Your check is local, free and needs no model:** `python -m scripts.guardrails_demo --recordings phase1` scans the **real model output** already on your disk from your live runs (about 8 artefacts) and prints how many findings there are and of what kind (never the text). My expectation is zero. If it finds something, I want to know whether it is a real catch or a false positive before I close the step. The offline default (no flag) shows the scanner on planted fakes.

## In scope
- `backend/app/guardrails/` (`scan.py` the scanner and rules, `status.py`): `scan(text, *, secrets=(), disabled=())` returning findings, plus a plain description of each for a repair message.
- Wiring: `check_body` (agent reply and person's edit), the repository's last-line refusal, the reviewer's reply check, document ingest (flag only).
- Findings stored in `generation["guardrails"]`; `flags` on `artefact.finished`; `guardrail_flags` on the approval record.
- Setting `GUARDRAILS_DISABLED_RULES`; a `guardrails` block on `/api/status` (rule count, anything disabled).
- `scripts/guardrails_demo.py` (offline demo; `--recordings NAME` to scan your own recordings).

## Out of scope (later steps)
- Scanning **code and infrastructure files**: those arrive with the sandbox (S16) and the deploy gate (S19), which reuse this scanner. The "deploy is blocked until the scan passes" gate is S19.
- The Sonnet security review (S18); it adds a reading pass on top of this one, it does not replace it.
- Scanning the brief and typed notes; redacting (this step refuses or flags, it never rewrites text); names, addresses and national IDs; any screen (S12).

## Design notes

**Linear-time on purpose.** Every pattern is written to be linear in the length of the text (no nested repeats), and a test feeds hostile input (very long lines, long runs of digits and separators) and checks it finishes in well under a second. A scanner that can be made to hang by a document would be a denial-of-service on the app.

**Order and cost.** One pass over lines. A body is at most 60,000 characters (S07), so the scan is a few milliseconds; documents up to 10 MB take longer and run once at upload.

**How `credential_assignment` avoids the obvious false positives.** The value must be one contiguous 12+ character token (so a sentence after a colon is never a value), must have high character entropy (so words and ID codes like `REQ-F-001` are not), must mix at least two character types, and must not look like a placeholder (`your-key-here`, `changeme`, `xxxx`, `<token>`, `${TOKEN}`, `{{token}}`, all one repeated character, or containing `example`). It is also never applied to a line that is only an item ID, a citation or a `Derives from:` list.

**Card and IBAN checks use arithmetic, not shape.** A long number is only reported if it passes Luhn (cards) or mod-97 (IBAN), which removes almost every accidental digit run.

**Where an agent's repair message comes from.** The scanner returns findings; `check_body` turns each secret finding into one sentence ("line 14, under 'Constraints': this looks like a cloud access key (rule aws_key_id); remove it, and never write a secret, password or token into an artefact"). That sentence goes to the model and into `repair_reasons`, so it must not contain the value, and a test checks it does not.

**A secret in the repair loop.** The model's reply that contained the secret is echoed back to the same model for the repair (as for any invalid reply). It is the model's own output going back to the provider it came from, so nothing new leaves the machine; it is not stored. Recordings made with `RECORD_LIVE_CALLS` are gitignored files and would contain it, which is one more reason they stay gitignored.

## Tests (must pass before the step is done)

| Area | Proves |
|---|---|
| each rule: positive | one test per rule with a fixture assembled at runtime; the finding names the right rule, class, line and heading, and carries no value |
| each rule: negative | near misses are not flagged (a token one character too short, a card that fails Luhn, an IBAN that fails mod-97, an email on `example.com`) |
| false positives | a corpus of real-looking artefact text finds nothing: item IDs, citations, `Derives from:` lists, dates, times, version numbers, token counts, costs, commit-style hashes, UUIDs, file paths, URLs without passwords, the phrase "password policy", sentences after `password:`; plus a trimmed sample of real model output from your live runs |
| configured credentials | every value in the settings is found by exact match, in the middle of a word and across case-insensitive matches of the endpoint; values under 4 characters are ignored; a blank setting never matches everything |
| placeholders | `user:password@host`, `<token>`, `${API_KEY}`, `changeme`, `xxxxxxxxxxxx`, `your-key-here` are not secrets |
| masking | no finding, description, repair message, stored record, event or audit row contains a planted value; **every table in the database is searched** for it |
| hostile input | very long lines, long digit runs, nested brackets and a 5 MB document scan in under a second and never raise |
| agent save | a reply with a secret is sent back with a value-free reason and the corrected reply is saved; three bad replies fail with all reasons and save nothing; a reply with an email is saved with the flag attached |
| person's edit | a secret is refused with the reason and nothing is saved; an email is saved with the flag; the refusal does not echo the value |
| repository backstop | a version containing a high-confidence token is refused whatever called it; the generic-assignment rule is not applied there; nothing is saved and no link or audit row is written |
| reviewer reply | a review whose text contains a secret is sent back once; a clean review is unaffected |
| documents | an upload with a secret and an email is accepted, returns both findings (rule and line), audits counts only, and stores nothing new; a clean upload returns none; the same bytes uploaded twice behave the same |
| stored findings | `generation["guardrails"]` is present, immutable, and empty for a clean artefact; a person's edit carries its own |
| events and approval | `artefact.finished` carries `flags` as a number; the approval record lists artefacts with personal-data flags and no values |
| setting | a disabled rule stops firing; an unknown rule name stops start-up; `configured_credential` and `private_key` cannot be disabled; the status block lists what is off |
| repo self-scan | the scanner run over this project's source, docs and config (never `.env`) finds no secret-class finding |
| script | the demo prints each planted fake caught by rule and line with no value; `--recordings NAME` prints counts only and exits 0 when clean, 1 when not; it never prints text |
| unchanged | the whole existing suite passes; every changed existing test is listed in PROGRESS |
| break-one-thing | a mutants file for S10, run with the baseline guard, the compile check and the hung-suite rule; every survivor is a test gap to fix, reported with the count and the spread |

## Dependencies / installs
None. Python's standard library only.

## Questions for the user
Decisions 1 to 8 above. The ones that most change the work: **1** (secrets block, personal data flags), **3** (which rules, especially `phone` and `credential_assignment`) and **6** (documents flagged, brief and notes not scanned).

## Manual check for the user (we do not run the app)
1. `python -m scripts.guardrails_demo`: planted fakes caught, each with rule and line and no value; an agent artefact with a secret sent back and repaired; a person's edit refused; an email flagged and saved; the approval record counting the flag. A banner says the fakes are planted.
2. `python -m scripts.guardrails_demo --recordings phase1`: scans your real model output and prints counts by rule. **Tell me what it says**; zero is what I expect, and anything else I will look at with you before closing.
3. The page does not change; the schema pill still reads v5.

## Done when
- [x] Listed tests pass; full suite green (1813 passed)
- [x] Break-one-thing check run with the baseline guard and reported honestly, including anything skipped or invalid (S10 76 of 76; all six lists clean; first run's 11 survivors resolved)
- [x] Frontend `npm run build` still succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] **Your scan of your own recordings done and its result recorded** (2026-10-29: 8 replies, 0 findings; offline demo behaved as specified)
- [x] User confirms (2026-10-29)

## Outcome
All eight decisions at their defaults; no change to the design. The generic password rule ignores values that label themselves as stand-ins (test, fake, demo, secret, example), a stated trade-off found when the repo scanned itself. Brief and typed notes are not scanned. Code and deploy files are scanned from S16 and S19 using this same scanner.
