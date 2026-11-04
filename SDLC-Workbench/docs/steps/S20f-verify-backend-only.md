# S20f · Build Verify, backend only: Screens removed, Rules found through their endpoint

**Milestone:** M6  **Size:** S, one slice  **Depends on:** S20 (Build Verify)
**Status:** SPEC WRITTEN 2026-11-05 from the user's direction after a real run on the Booking-App: "how about we remove UI completely and keep rules the way you suggested, endpoint based hint?" **ANSWERED 2026-11-05: all five defaults ("all defaults is good"). BUILT, TESTED AND CLOSED 2026-11-05: the user ran it on the Booking-App and said "this is done for now".**
This replaces the parked "web reader fix". The frontend reader is not repaired; it is removed.

## Why
A real run on the Booking-App gave Endpoints 8 of 8, Tables 2 of 2, Screens 0 of 4 and Rules 0 of 18 (3 weak). The first two read the code well. Screens failed because the build's frontend is plain static pages that the pattern reader does not recognise, and a screen is the hardest thing to trace back to a design line. Rules failed because a rule is logic, not a name: the code enforces "no overlap" with a 409, but nothing in it quotes the rule.

## Decisions (all defaults taken)
1. **Screens are removed completely.** The web reader, the screen matching, the Screens card and tile type, the frontend folder box and the "built but not designed" screens go. Build Verify says it is "backend only: endpoints, tables, rules". Runs already saved keep their screen rows (history is append-only); they are simply not shown and not counted.
2. **A rule is linked to an endpoint** when both derive from a shared requirement AND share at least one meaningful word, or when they share at least three words with no requirement in common.
3. **What the link says.** If the linked endpoint was matched in the build and the design gives it an error code (409, 422 and so on), the rule shows *weak evidence*: "its endpoint `POST /api/reservations` is built and can answer 409". If the linked endpoint was not found, the rule says so. A rule is never "found". The tile shows how it was linked, so a person can overrule it.
4. **The old search stays.** A rule whose ID, or three of whose words, appear in a comment, test name or message is still weak evidence, as before. The endpoint hint is added; it replaces nothing.
5. **One slice, same discipline.** Tests and break-one-thing sweeps; no model, no new package; the user's folder is not run by me.

## What the user should expect
Rules about overlap, hours and retired rooms should turn grey on the Booking-App. Rules about what a screen checks ("the date field is required") stay "not found", and the screen says so. That is accepted.

## Out of scope
Any reading of a frontend; reading logic inside functions; a model guessing links; deleting old runs.

## Tests (must pass)
| Area | Proves |
|---|---|
| design | no screen item is read from the wireframes; rules keep the requirements they derive from |
| link | shared requirement plus a word links; a requirement alone does not; three shared words alone link; two do not; one endpoint can serve several rules; the order of items does not change the result |
| hint | a matched endpoint with an error code gives weak evidence naming that endpoint and code; an endpoint with no code gives the plain "can be reached" wording; an endpoint not found says so; a rule is never FOUND |
| old search | an ID in a comment still gives weak evidence and wins over the hint |
| run | a run takes one folder; the frontend path is not required and is stored empty; no screen row or screen count is written; the download is a three-area report |
| history | an old run with screen rows and a frontend path still opens and downloads, its screens hidden |
| page | three cards; no frontend box; the explanation line says backend only; an old run opens without error |
| unchanged | every other phase, the instruction set, Deploy, Handover; `export_contract --check` |
| break-one-thing | a mutants file with the baseline guard; every survivor closed with a real test |

## Manual check for the user
Restart the backend and run Build Verify on the Booking-App backend folder. Expect Endpoints and Tables as before, no Screens card, and Rules mostly grey eyes with the endpoint named on each.

## Done when
- [ ] Listed tests pass; full suites green
- [ ] Break-one-thing check run and reported honestly
- [ ] PROGRESS.md and RESUME.md updated
- [ ] **You have run it on the Booking-App backend and told me what you saw**
- [ ] User confirms
