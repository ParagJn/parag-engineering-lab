"""Break one line of the FRONTEND at a time in a scratch copy and see whether vitest notices. The frontend twin of `mutation_check.py`.

    cd backend && python -u -m scripts.frontend_mutation_check scripts/mutants/s19b2_compose_events.py

Reads FRONTEND = [(name, path under frontend/, old text, new text), ...] from the mutants file. Same safeguards as the backend harness: the unbroken copy must pass
first, a pattern that does not match EXACTLY once is SKIPPED (never counted as caught), and everything happens in a copy under the temp folder.
"""
from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"


def vitest(root: Path) -> tuple[bool, str]:
    done = subprocess.run(["npx", "vitest", "run"], cwd=root, capture_output=True, text=True, timeout=600)
    tail = [l for l in (done.stdout + done.stderr).splitlines() if "Tests " in l]
    return done.returncode == 0, (tail[-1].strip() if tail else "no result line")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mutants", type=Path)
    parser.add_argument("--only", help="run only mutants whose name contains this text")
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("mutants", args.mutants)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    mutants = [m for m in module.FRONTEND if not args.only or args.only in m[0]]
    with tempfile.TemporaryDirectory(prefix="sdlc_fe_mutation_") as tmp:
        root = Path(tmp) / "frontend"
        shutil.copytree(FRONTEND, root, ignore=shutil.ignore_patterns("node_modules", "dist", ".vite", "*.log"))
        (root / "node_modules").symlink_to(FRONTEND / "node_modules")      # the packages are read-only for the tests; copying them would take minutes
        ok, line = vitest(root)
        print(f"baseline: {'passes' if ok else 'FAILS'} ({line})", flush=True)
        if not ok:
            print("The unbroken copy fails, so no break could be told apart. Stopping.")
            return 2
        caught = survived = skipped = 0
        survivors: list[str] = []
        for name, rel, old, new in mutants:
            path = root / rel
            original = path.read_text(encoding="utf-8")
            if original.count(old) != 1:
                skipped += 1
                print(f"SKIPPED  [{name}]  pattern found {original.count(old)} times in {rel}", flush=True)
                continue
            path.write_text(original.replace(old, new), encoding="utf-8")
            try:
                passed, line = vitest(root)
            finally:
                path.write_text(original, encoding="utf-8")
            if passed:
                survived += 1
                survivors.append(name)
                print(f"SURVIVED [{name}] -> {line}", flush=True)
            else:
                caught += 1
                print(f"CAUGHT   [{name}] -> {line}", flush=True)
        print(f"CAUGHT {caught}  SURVIVED {survived}  SKIPPED {skipped}  of {len(mutants)}")
        if survivors:
            print("SURVIVORS (holes in the tests):", survivors)
        return 0 if not survived and not skipped else 1


if __name__ == "__main__":
    sys.exit(main())
