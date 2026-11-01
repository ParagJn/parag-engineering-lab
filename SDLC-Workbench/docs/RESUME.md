# Resume log

Written 2026-11-01, after S16 was closed and just before the user rebooted. Work restarts at night and carries on through the following week.
This file says where to pick up. `docs/PROGRESS.md` is the full record; read this first, then PROGRESS.md.

## Where we are
- **S00 to S16 are closed.** S16 (Sandbox) closed 2026-11-01 on the user's word, after they ran the demo and the sandbox tests.
- **Next: S17, Build agents** (database, backend, frontend, tests; a bounded write → test → fix loop; parallel execution). **Its spec is not written yet.** Plan row: `docs/05-build-plan.md`, milestone M5.
- Then S18 (code and security review, quality gate), S19 (Deploy), S20 (BAU handover), S21 (Day-2 incident), S22 to S24 (demo readiness).
- Nothing is half-done. No step is in progress, no server is running, no background job is needed.

## First thing to do when work restarts
1. Read `CLAUDE.md` (this folder), then `docs/PROGRESS.md`, then this file.
2. Write the S17 spec from `docs/steps/_TEMPLATE.md` (decisions with defaults, in the same shape as S15 and S16). Do not write code until the user has answered.
3. Check the baseline is still green before touching anything:
   - `cd backend && /Users/paragjain/dev-works/myenv/bin/python -m pytest tests/ -q -p no:cacheprovider` → expect **3012 passed, 1 deselected** (about 3 minutes).
   - `cd frontend && npm test` → expect **1082 passed**; `npm run build` OK.
   - `python -m scripts.export_contract --check` → "contract fixtures are up to date" (48).

## Last verified numbers (2026-11-01)
- Backend 3012 passed, 1 deselected. Frontend 1082 passed, build OK.
- S16 break-one-thing: 136 breaks, all caught (`backend/scripts/mutants/s16_sandbox.py`).
- The real database (`backend/data/sdlc_workbench.db`) holds 17 projects, 3 visible (the rest are archived). A dated backup sits beside it. No `data/workspaces` folder exists yet.

## Git state (2026-11-01)
- The checkpoint through S16 is **committed locally** on `inflight-Work` (`b5a85ab`, 402 files, only `SDLC-Workbench/`), followed by a merge of the remote's bot "Deploy profile site" commit (`a0ab7cc`). **It is not pushed anywhere**, so the only copy is on this Mac. Other lab apps' changes (about 20 files) are still uncommitted and were left out on purpose.
- The user tried a private repo (`ParagJn/sdlc-workbench`) for a second copy; the push failed on authentication (token needed) and they chose to leave it on `inflight-Work` for now. A local remote `sdlc` and a local branch `sdlc-workbench-only` (SDLC files only) exist from that attempt and are harmless.
- The lab repo is **public** and GitHub Pages serves its `main`, so making it private would take the site down on a free plan. Pushing `inflight-Work` to `origin` is the user's call; the `git push` was blocked for the assistant, so the user runs pushes themselves. The saved git login was cleared during the attempt, so the next push will ask for a username and a personal access token.
- Commit only when asked; end commit messages with the attribution line the harness gives. Nothing added to any README yet, by the user's choice.

## What S17 builds on (S16's surface)
- `SandboxService` (`backend/app/sandbox/service.py`): `write_file`, `read_file`, `list_files`, `delete_file`, `make_dir`, `run_command`, `run_tests(project_id, target)`. Every action is audited without contents or output. Paths are relative to the project's workspace (`backend/data/workspaces/<project id>/`).
- Results are facts: `Result.status` is one of ran, refused, unavailable, timed_out (plus truncated/limit fields); `RunReport` gives passed, failed, errors, skipped, each failure's name, file and first lines, and a distinct "no tests were run" and "crashed" result.
- Allow-list: `python`/`python3` (a file or `-m module`, never `-c`), `pytest`, `pip` (list only), `node` (a script, or `--check <file>`), `npm` (test, run, build), `ls cat head tail wc grep diff`, `find` (looking only). Nothing installs packages; nothing reaches the network. `git`, `curl`, shells stay out by the user's decision.
- Generated apps are FastAPI + SQLite + plain HTML/JS (architecture doc). FastAPI `TestClient` tests were checked to pass inside the sandbox.
- A file holding a secret-shaped string cannot be written; a command's output is redacted.

## Known limits and open items to carry
- **Loopback is blocked** (the profile denies all network, localhost included). A generated server cannot be started and probed from inside the sandbox. S19's smoke test needs a narrow, loopback-only allowance, to be decided when S19 is specced. S17 should use in-process `TestClient` tests, which work.
- macOS only. `sandbox-exec` is deprecated by Apple; if it is missing, nothing runs (by design). Memory limits are not enforced on macOS and are not claimed. Not a boundary against a determined local attacker.
- Auto edit is **parked**, not built.
- Parking list in PROGRESS.md "Still open": **D14** clean configuration (at the very end), **D15** re-look at the whole review process (after all stages), **D16** a complete configuration screen.
- The workflow catalogue (`docs/08-workflow-catalogue.md`) is provisional.

## Working agreement (how we work)
- One step at a time. Spec with decisions and defaults first; the user answers ("all defaults" or changes); then build with tests and break-one-thing checks; the user runs it and says yes to close.
- **Do not run the app, servers or the UI.** The user tests by hand. Running pytest and vitest is fine.
- Budget for model spend: the user has said **$5** is available when a step needs it (S14b used it for real model runs). S16 used none. Ask or state before any live model call.
- LLM access only through the gateway (`backend/app/llm/`), always IBM ICA. Unit tests never touch the network.
- Venv: `/Users/paragjain/dev-works/myenv` (shared; install nothing into it).
- Ports: backend 8090, frontend 5270. Do not read or print `.env` files. The repo is public: no deck text, product names or client names.
- Honest labelling: anything simulated is labelled as simulated.

## Test and harness lessons (they cost time to learn)
- Any test that builds an app uses `make_settings`; an autouse guard in `tests/conftest.py` fails any test that opens `backend/data`. Never delete real database rows.
- `tests/test_guardrails_repo.py` forbids secret-shaped strings written in full; build fake secrets from fragments (`tests/_fakes.py`).
- Mutation harness: `python -u -m scripts.mutation_check <mutants file> --tests <files>`. It has a baseline guard, treats a hung suite as INVALID, runs each mutated suite in its own session, and `--only` matches by substring (one text). To run a chosen few, write a small batch file that filters `MUTANTS` by name (see how `/tmp/s16_new.py` was built: import the full mutants module, filter `m.MUTANTS`).
- Run long mutation sweeps in batches of about six, each under ~280 seconds with `timeout`; a single command over ~10 minutes gets killed (exit 144). Killed sweeps can leave `time.sleep(120)`/`(60)` processes behind: check with `pgrep -f "sleep\((120|60)\)"` and ask before killing.
- Delete redundant code rather than test it; pin literals; one fault per test. A new survivor means write a real test, not a looser mutant.
- To look at an SVG, wrap it in HTML and render with the Swift/WebKit tool at `/tmp/shot/shot` (it may need rebuilding after a reboot; `/tmp` is cleared).

## Housekeeping after the reboot
- `/tmp` is usually cleared on reboot, so the scratch batch files (`/tmp/s16_*.py`) and `/tmp/s16w` will go. Nothing in the repo depends on them.
- Old scratch folders from killed mutation runs (`sdlc_scratch_*`, `sdlc_mutation_*`, `sdlc_probe_*`) sit under the system temp folder (`/var/folders/.../T/`). Safe to delete; they are not in the repo.
- `backend/data/` is git-ignored. Do not delete the database or its backup.
