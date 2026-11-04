"""Break one guarantee at a time in a scratch copy and see whether the test suite notices.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.mutation_check path/to/mutants.py

A "mutant" is a deliberate break: replace one piece of source text with another, run the suite, and expect it
to FAIL. A mutant the suite does not notice is a hole in the tests. This tool exists because the first
version of this check, written by hand, reported success while its own scratch copy failed a test even
with nothing broken. So it has safeguards, each added after a real mistake:

  * BASELINE FIRST. The unbroken copy must pass, or the run aborts: otherwise every mutant "fails" for
    the same unrelated reason and looks caught.
  * NOTHING SKIPPED SILENTLY. A pattern that no longer matches exactly once is reported as SKIPPED and
    counts as a failure of the run, never as caught.
  * THE SPREAD OF 'N passed' IS PRINTED. Many mutants stopping after the same number of passing tests
    means they are all stopping on the same test, which is the tell of a broken harness.
  * IT RUNS TO COMPLETION per mutant (no -x), and names the tests that failed, so a reviewer can see what
    caught each break.

A mutants file defines MUTANTS = [(name, relative_path, old_text, new_text), ...].
It works on a copy under the system temp folder and never touches the real source.
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence

BACKEND = Path(__file__).resolve().parent.parent
COPIED = ("app", "tests", "scripts")
TIMEOUT_SECONDS = 180


def load_mutants(path: Path) -> list[tuple[str, str, str, str]]:
    spec = importlib.util.spec_from_file_location("mutants_file", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return list(module.MUTANTS)


def fresh_copy(root: Path) -> Path:
    """A clean copy laid out like the real project (backend/ next to docs/), so tests that read ../docs work."""
    if root.exists():
        shutil.rmtree(root)
    work = root / "backend"
    work.mkdir(parents=True)
    for name in COPIED:
        shutil.copytree(BACKEND / name, work / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copy(BACKEND / "pytest.ini", work / "pytest.ini")
    docs = BACKEND.parent / "docs"
    if docs.is_dir():
        shutil.copytree(docs, root / "docs", ignore=shutil.ignore_patterns("steps"))
    # The rest of the project that a test may read. The guardrail self-scan reads the whole project (never a real .env), so the
    # scratch copy must look like it; the first S10 run aborted at the baseline guard because it did not. Never copy .env, the
    # recordings, the database or node_modules.
    for name in ("CLAUDE.md", "start.sh"):
        if (BACKEND.parent / name).is_file():
            shutil.copy(BACKEND.parent / name, root / name)
    for name in (".env.example", "requirements.txt", ".gitignore"):
        if (BACKEND / name).is_file():
            shutil.copy(BACKEND / name, work / name)
    frontend = BACKEND.parent / "frontend"
    if frontend.is_dir():
        shutil.copytree(frontend, root / "frontend", ignore=shutil.ignore_patterns("node_modules", "dist", ".vite", "*.log"))
    return work


def run_suite(work: Path, python: str, extra: Sequence[str] = ()) -> tuple[int, str, list[str]]:
    try:
        # Its own session: a break may make the code under test signal "its own process group" (S16 did), and with a shared group that would stop THIS harness
        # as well and the sweep would die without a word. In its own session the worst a break can do is end its own suite, which counts as caught.
        run = subprocess.run(
            [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *extra],
            cwd=work, capture_output=True, text=True, timeout=TIMEOUT_SECONDS, start_new_session=True,
        )
    except subprocess.TimeoutExpired:
        return 1, "suite hung (timed out)", []
    lines = run.stdout.strip().splitlines() or ["(no output)"]
    failed = re.findall(r"^(?:FAILED|ERROR) (\S+)", run.stdout, re.MULTILINE)
    return run.returncode, lines[-1], failed


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mutants", type=Path, help="a Python file defining MUTANTS")
    parser.add_argument("--python", default=sys.executable, help="interpreter to run the suite with")
    parser.add_argument("--only", help="run only mutants whose name contains this text")
    parser.add_argument("--tests", nargs="+", default=[], help="run only these test files/paths (a quicker re-check of survivors: a break caught by fewer tests is certainly caught by all)")
    args = parser.parse_args(argv)

    mutants = [m for m in load_mutants(args.mutants) if not args.only or args.only in m[0]]
    root = Path(tempfile.mkdtemp(prefix="sdlc_mutation_")) / "project"
    try:
        work = fresh_copy(root)
        code, last, failed_baseline = run_suite(work, args.python, args.tests)
        print(f"BASELINE (nothing broken): {last}")
        if code != 0:
            # Name the tests: an abort that does not say WHICH test failed cannot be told apart from a slow machine or a real fault.
            for name in failed_baseline[:10] or ["(the runner did not name a failing test)"]:
                print(f"  baseline failure: {name}")
            print("ABORT: the unbroken copy does not pass, so no mutation result can be trusted.")
            return 2

        caught: list[str] = []
        survived: list[str] = []
        skipped: list[str] = []
        invalid: list[str] = []
        spread: collections.Counter[str] = collections.Counter()
        for name, relative, old, new in mutants:
            work = fresh_copy(root)
            target = work / relative
            if not target.is_file():
                print(f"SKIPPED  [{name}]  {relative} does not exist")
                skipped.append(name)
                continue
            text = target.read_text(encoding="utf-8")
            if text.count(old) != 1:
                print(f"SKIPPED  [{name}]  pattern found {text.count(old)} times in {relative}")
                skipped.append(name)
                continue
            broken = text.replace(old, new)
            try:
                if relative.endswith(".py"):                  # a Markdown skill or a YAML file is not Python: compiling it would call every break of it invalid
                    compile(broken, relative, "exec")
            except SyntaxError as exc:
                # A mutant that is not valid Python "fails" the suite for the wrong reason (nothing imports), so it
                # would look caught. It tests nothing, so it is reported and counted against the run.
                print(f"INVALID  [{name}]  the mutant is not valid Python ({exc.msg}, line {exc.lineno}); NOT counted as caught")
                invalid.append(name)
                continue
            target.write_text(broken, encoding="utf-8")
            code, last, failed = run_suite(work, args.python, args.tests)
            passed = re.search(r"(\d+) passed", last)
            if code != 0 and passed:
                spread[passed.group(1)] += 1
            if code != 0 and not failed and not passed:
                # The suite failed but no test is named and no pass count exists: it did not run, which proves nothing.
                print(f"INVALID  [{name}]  the suite did not run at all ({last!r}); NOT counted as caught")
                invalid.append(name)
            elif code != 0:
                caught.append(name)
                first = failed[0].split("::")[-1][:70] if failed else last
                print(f"CAUGHT   [{name}] by {len(failed)} test(s), e.g. {first}")
            else:
                survived.append(name)
                print(f"SURVIVED [{name}] -> {last}")

        print(f"\nCAUGHT {len(caught)}  SURVIVED {len(survived)}  SKIPPED {len(skipped)}  INVALID {len(invalid)}  of {len(mutants)}")
        print("Most common 'N passed' counts among the failures (the same big number many times is a tell):",
              spread.most_common(4))
        if survived:
            print("SURVIVORS (holes in the tests):", survived)
        if skipped:
            print("SKIPPED (could not apply; NOT counted as caught):", skipped)
        if invalid:
            print("INVALID (not valid Python, or the suite did not run; NOT counted as caught):", invalid)
        return 0 if not survived and not skipped and not invalid else 1
    finally:
        shutil.rmtree(root.parent, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
