# S16 · Sandbox

**Milestone:** M5  **Size:** M  **Objectives:** O7, O9  **Depends on:** S01 (nothing else; the plan notes S16 has no dependency on S13 to S15)
Plan test (`05-build-plan.md`): *path traversal blocked; a disallowed command refused; a timeout kills the process; pytest output parsed into pass/fail counts.*
Build (S17 onward) has agents write code. Before any agent may do that, there must be **one safe place** where generated code can be written, run and tested, and a way to read the **real** result of running it. S16 is that place. It builds no agent and calls no model; it is the floor the Build phase stands on. The rule from the testing strategy applies here: *execution beats claims*. A test result comes from running the code, never from a model saying it passes.

## What I found before writing this (it changes the plan)

1. **"No network" is the hard part, and the plan does not say how to do it.** A plain Python subprocess can open a socket: I checked on this Mac, and a script with no restriction reaches the internet. Filtering which *commands* are allowed does not stop an allowed `python` from opening a connection. So containment has to be done by the operating system, not by our own checks.
2. **macOS has a built-in way, and I tested it.** `sandbox-exec` is installed here. With a profile that denies the network, the same script is refused (`PermissionError`). With a profile that denies writing outside one folder, a write outside is refused and a write inside works. I tried both with harmless probes in a temporary folder and confirmed nothing was written outside. Docker, bubblewrap, firejail and `unshare` are **not** installed.
3. **`sandbox-exec` is deprecated by Apple, though it still works and is what many tools use.** If a future macOS removes it, the runner must **refuse to run anything** rather than quietly run unprotected. That is decision 2 below, and it is the most important rule in this step.
4. **The checks I can build myself are real but not enough on their own.** Path containment (a file tool cannot leave the workspace), an allow-list of programs, a time limit that kills the whole process tree, an output size limit, and a cleaned environment are all things I can do and test. They stop a *mistaken* agent. Only the operating-system layer stops a *hostile* one. I will build both, and say plainly which is which.
5. **Windows and Linux are different.** This lab runs on a Mac. The Linux and Windows equivalents are not built and not tested here. On any system where the OS-level protection is not available, the runner says so and refuses (finding 3). It does not fall back to "trust the allow-list".
6. **Test output parsing is a self-contained job.** `pytest` is installed in the shared venv. A pytest run can be asked for a machine-readable summary and I can parse the plain output too. The result I need is counts (passed, failed, errors, skipped), the names and messages of failures, and the exit code, from the real run.
7. **Secrets must not get into the workspace.** O9 asks for secret scanning on code. The existing scanner (S10) already finds secrets in text. Files an agent writes into the workspace go through it, and a file that holds a secret is refused, the same way an artefact is.

## Decisions (**the user said "assume all defaults" on 2026-11-01, so all ten stand as written**)

1. **Where workspaces live.** `backend/data/workspaces/<project id>/`, inside the git-ignored `data/` folder, **one folder per project**. A project's workspace is created on first use and is never shared. The folder path is never sent to the screen or to a model (they see paths *inside* the workspace, like `src/app.py`). Default: that.
2. **OS-level containment is required, and its absence is a refusal, not a fallback.** Every command runs under `sandbox-exec` with a profile that (a) **denies all network access**, (b) **denies writing anywhere except the project's workspace and its own scratch folder**, and (c) allows reading what a program needs to start (the Python install, system libraries) but **not** the app's database, recordings, `.env` or other projects' workspaces. If `sandbox-exec` is missing or fails a start-up self-test, `run_command` raises `SandboxUnavailable` with a sentence and runs **nothing**. Default: refuse.
3. **An allow-list of programs, by name, with fixed argument rules.** Allowed: `python` and `python3` (the shared venv's interpreter only), `pytest`, `pip` **only** in a form that cannot install from the network (`pip list`, `pip --version`), `node` and `npm` for `test`, `run` and `build` style scripts **without** `install`, `ls`, `cat`, `head`, `tail`, `wc`, `grep`. Everything else is refused with a sentence naming the program. No shell: a command is a program and a list of arguments, never one string run through `sh`, so `;`, `&&`, `|`, `$()` and backticks are text, not operators. Default: this list.
4. **Installing packages is refused.** `pip install` and `npm install` need the network, and S16 gives none. A Build that needs a package is told so plainly (it can only use what is already installed). A later step can add an "approved packages" mechanism; I will not invent one now. Default: refused, with the reason.
5. **Limits, all with defaults and all configurable in `config.py`.** Time per command: **60 seconds** (a test run: **120**); output kept: **256 KB** per command (the rest is dropped and says so); memory: **1 GB** where the OS lets us set it; processes: **64**; one file: **1 MB**; files in a workspace: **500**; workspace total: **50 MB**. Over a limit is a plain refusal, never a crash. Default: these numbers.
6. **A timeout kills the whole process tree, not just the child.** The command is started in its own process group, and on timeout the group is killed (first politely, then hard after two seconds). A test that leaves a background process behind must not survive the run. Default: that.
7. **A clean environment.** The command sees only a short list of variables (`PATH` pointing at the venv's `bin` and system `bin`, `HOME` set to the scratch folder, `LANG`, `PYTHONDONTWRITEBYTECODE`, `PYTHONHASHSEED=0`). **None** of the app's own variables reach it: no `IBM_ICA_*`, no proxy settings, nothing from `.env`. A test proves a planted variable does not arrive. Default: that.
8. **File tools** (what the Build agents will call): `write_file`, `read_file`, `list_files`, `delete_file`, `make_dir`. Paths are **relative to the workspace**, always. Refused: an absolute path, `..` anywhere, a path that resolves (through a symlink) outside the workspace, a hidden file name that is a control name (`.env`, `.git/`), a name with a control character or longer than 200 characters. Symlinks are **never created** by the tools, and a symlink already present is **never followed** out of the workspace. Writes are atomic (written beside, then moved). Default: these.
9. **A test runner that returns facts.** `run_tests(project, target=None)` runs `pytest` in the workspace under decision 2 and returns: the exit code, counts (**passed, failed, errors, skipped**), each failure's test name, file and the first lines of its message, the duration, and whether it **timed out** or was **cut for output size**. If pytest itself cannot start or collects nothing, that is a distinct result ("no tests were run"), never reported as "0 failed". Default: this shape.
10. **Every action is audited and traced, and secret-scanned.** Each file written and command run adds an audit row (who, what, result code; never file contents or full output). A file whose text holds a secret by the S10 rules is **refused** (the same sentence as an artefact). A command's output that holds a secret is **redacted** before it is stored or shown. Default: that.

Stated, not asked: no model is called; no new package is installed (`psutil` is already present, and I use only the standard library otherwise); the backend never runs generated code in its own process; nothing is exposed over HTTP yet (S17 calls this from Python, and S19's report screen will read results); the sandbox is **not** a security boundary against a determined attacker with local access to this Mac, only against code that runs inside it, and I say so in the docs rather than imply more.

## In scope
- **`backend/app/sandbox/workspace.py`**: the workspace for one project, the path rules, the file tools, the limits, the atomic write.
- **`backend/app/sandbox/policy.py`**: the allow-list, the argument rules, the clean environment.
- **`backend/app/sandbox/profile.py`**: builds the `sandbox-exec` profile for a workspace and runs the start-up self-test (a harmless child that must be refused the network and refused a write outside).
- **`backend/app/sandbox/runner.py`**: `run_command` (process group, timeout, tree kill, output cap, redaction) and `SandboxUnavailable`.
- **`backend/app/sandbox/pytest_report.py`**: `run_tests` and the parser for pytest's output.
- **`backend/app/sandbox/errors.py`**: one error type per refusal, each with the sentence a person or an agent reads.
- **`scripts/sandbox_demo.py`**: offline, free: shows a file written, a traversal refused, a program refused, the network refused, a timeout killing a child that spawned a child, and a pytest run parsed.
- **Settings** for the limits; a `sandbox` test marker already exists.

## Out of scope (later)
- Any agent or the write-test-fix loop (S17); the report screen and quality gate (S18, S19); an "approved packages" mechanism; Linux and Windows containment; running a generated *server* and probing it (that is Deploy); resource accounting beyond the limits above.

## Design notes
- **Two layers, named.** Layer 1 is our checks (paths, allow-list, limits, environment, scanning): they stop mistakes and make good error messages. Layer 2 is the OS profile: it stops a command that does something our checks did not foresee. Both run for every command. Neither is trusted alone.
- **Refuse to start unprotected.** The runner runs the self-test the first time it is used and caches the result. A failed self-test means `SandboxUnavailable` for every command until restart.
- **No shell, ever.** `subprocess` with a list, `shell=False`, `stdin` closed, a new session so signals reach the group.
- **Profile is generated, not hand-written per call.** One function turns (workspace path, scratch path, Python home) into profile text; the path values are checked to contain no quote or newline before they are placed, so a path cannot rewrite the profile.
- **Output is text, bounded, redacted.** Read in chunks to the cap, decoded with replacement, scanned, then returned.
- **Failures are facts.** A refused command, a timeout, a non-zero exit, an OS refusal and "sandbox unavailable" are five different results, each with its own field, so the Build loop (S17) can react to the right one.

## Tests (must pass before the step is done)

| Area | Proves |
|---|---|
| paths | `..`, absolute paths, a symlink out, a symlink in the workspace that points outside, names with control characters or too long, `.env` and `.git/`, an empty name, a name that normalises to the workspace root: all refused with a sentence; a good nested path works; a path is never echoed with the workspace's real location |
| file tools | write, read, list, delete, make_dir behave; a write is atomic (a failure leaves the old file whole); limits on one file, file count and total size refuse over the line and allow at it; a file holding a planted secret is refused and not left behind; a binary-looking write is refused |
| policy | every allowed program with a good argument list is allowed; every other program is refused by name; `pip install`, `npm install` and friends are refused with the reason; `sh -c`, `bash`, `python -c` with network code are refused or contained; arguments with `;`, `&&`, `|`, `$()` are passed as plain text and do nothing |
| environment | a planted `IBM_ICA_API_KEY`, `HTTPS_PROXY` and a made-up variable in the parent do not reach the child; `HOME` is the scratch folder |
| containment (real subprocess, `sandbox` marker) | the network is refused for `python`, for `curl`-like use through python, for a child of a child; a write outside the workspace is refused; a read of the app's database, `.env` and another project's workspace is refused; a write inside works |
| unavailable | with `sandbox-exec` made unavailable (a stand-in path), `run_command` raises `SandboxUnavailable`, runs nothing and says why; a self-test that fails does the same |
| timeout | a sleeping command is killed at the limit; a command that starts a child that starts a grandchild leaves **no** process behind (checked by looking for them); a command that ignores the polite signal is killed hard; the result says it timed out |
| output | output over the cap is cut and says so; output with a planted secret is redacted; invalid bytes do not crash it; a command that prints forever is stopped |
| limits | a runaway process count and memory are contained where the OS allows, and the result says which limit |
| pytest | a passing project, a failing one, one with an error at collection, one with no tests, one that times out and one that crashes pytest itself each give the right distinct result; counts equal a hand count; failure names, files and messages are right; skipped and xfail are counted separately |
| audit | each file write, delete and command adds one audit row with no contents; a refused action adds a row saying refused |
| isolation | two projects' workspaces cannot see each other's files by any tool |
| demo | the offline demo shows each refusal and prints nothing secret |
| unchanged | full backend and frontend suites pass; tests use scratch folders only (the S14b guard); nothing is written to the real `backend/data` |
| break-one-thing | a mutants file for paths, policy, environment, the profile, the timeout and the parser; hung-suite rule; unkillable breaks named; **plus a check that each containment mutant is caught by a REAL-subprocess test, not only by a unit test** |
| build | `npm test` and `npm run build` still pass (nothing changes in the frontend) |

## Dependencies / installs
None. (`psutil` and `pytest` are already in the shared venv; I do not install anything.)

## Questions for the user
Decisions 1 to 10 were answered "all defaults". The ones to look at first when you read this: **2** (no OS protection means no run, never a quiet fallback) and **4** (no package installs, because there is no network).

## Manual check for the user (we do not run the app)
This step has no screen. To see it work yourself, from `backend/`:
1. `python -m scripts.sandbox_demo` and read each line: the refusals should each say why.
2. `python -m pytest tests/ -m sandbox -q`: the real-subprocess tests.
3. Tell me if the allow-list is missing a program you expect the Build agents to need, or has one you do not want.

## What was built, and what differed from the spec above (2026-11-01)
Built as specified. These things were found by trying them, and they changed the code or the claims:
- **The memory limit does not work on macOS, so it is not claimed.** `setrlimit` for memory fails with an error here, and a program asking for 3 GB under a 1 GB limit got it. Decision 5 listed "memory: 1 GB where the OS lets us set it"; the OS does not let us, so only the time limit, the process-group kill and the process ceiling stand behind a runaway program. The setting exists and is documented as not enforced.
- **The process limit counts every process the user owns, not only the command's.** A cap of 64 stopped a command from starting even one child, because 389 processes were already running. The ceiling is now what the user already has plus the command's allowance. A fork bomb is stopped, and the processes it made are gone a few seconds later (tested).
- **A command that finishes by itself can leave a background process behind.** The spec only covered the timeout. The first real test found a worker still running after a normal exit; the runner now stops the whole process group when a command ends, politely and then hard.
- **A deny-by-default profile only works if the command starts inside the workspace.** Found by trying: the narrow profile made Python fail to start from any other folder. The runner always sets the working folder to the workspace, and a test proves it.
- **Program output named the real folder on disk** (a traceback, pytest's header). It is replaced with paths inside the workspace, longest location first, because on a Mac `/var` and `/private/var` are the same folder.
- **A file holding a secret cannot be written, so a test that needs a command to PRINT a secret builds it at run time.** The repository's own scanner caught me writing two fake secrets in full into the source; both are now built from pieces.
- **The break-one-thing sweep (128 breaks) found three holes in the tests, now closed:** stdin handed to a command, a pytest cache folder left in the workspace, and control characters in a logged path. Earlier in the sweep it found two real flaws, fixed in the code: a swapped workspace folder, and a leftover background process.
- **Allow-list widened on the user's word after their run (2026-11-01):** `diff`, `find` (read-only: the options that run programs, delete or write files are refused) and `node --check <one file>`. Eight more breaks, all caught. `git`, `curl` and anything that reaches out stay out.
- **Left for S19:** the sandbox denies loopback as well as the internet, so a generated server cannot be started and probed from inside it. S19's smoke test will need a narrow, separate loopback-only allowance; not decided yet.
- **Not built, as stated:** Linux and Windows. On any machine without `sandbox-exec` nothing runs, and the sentence says why.

## Done when
- [x] Listed tests pass; full suite and `npm test` green (summary lines in PROGRESS.md)
- [x] Break-one-thing check run with the baseline guard and reported honestly
- [x] `npm run build` succeeds
- [x] Manual-check list handed over
- [x] PROGRESS.md updated
- [x] **You have run it and told me what you saw**
- [x] User confirms (2026-11-01: 'lets close S16')
