"""Show the sandbox working, offline and free: files, refusals, the network, a timeout that kills a child of a child, and a parsed pytest run.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.sandbox_demo

Nothing is called over the network and no model is used. Everything happens in a temporary folder that is deleted afterwards: your real workspaces and
database are not touched. Each line says what was tried and what the sandbox did.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Sequence

from app.config import Settings
from app.guardrails.scan import Scanner
from app.repos import Store
from app.sandbox.errors import SandboxError
from app.sandbox.runner import Limits, Sandbox
from app.sandbox.service import SandboxService


def line(label: str, what: str) -> str:
    return f"  {label:<44} {what}"


def demo(workdir: Path) -> list[str]:
    settings = Settings(_env_file=None, data_dir=str(workdir / "data"), recordings_dir=str(workdir / "rec"))
    store = Store.open(workdir / "demo.db", limits=settings.context_limits)
    project = store.projects.create(name="Sandbox demo", brief="", actor="system")
    service = SandboxService(settings, store, Scanner.from_settings(settings), Sandbox())
    who = "human:demo"
    out = ["SANDBOX DEMO (temporary folder; nothing of yours is touched)", ""]
    problem = service.sandbox.availability()
    out.append(line("operating-system protection", "ready" if not problem else f"NOT AVAILABLE: {problem}"))
    if problem:
        return out + ["", "Nothing can be run without it, which is the point."]

    out += ["", "Files"]
    out.append(line("write src/app.py", service.write_file(project.id, "src/app.py", "def add(a, b):\n    return a + b\n", actor=who)))
    for bad in ("../escape.py", "/etc/passwd", ".env", "src/../../x.py", "a" * 250):
        try:
            service.write_file(project.id, bad, "x", actor=who)
            out.append(line(f"write {bad[:30]!r}", "ALLOWED (this is a bug)"))
        except SandboxError as exc:
            out.append(line(f"write {bad[:30]!r}", f"refused: {exc}"))
    try:
        fake = "AKIA" + "IOSFODNN7" + "EXAMPLE"                       # built from pieces so this file does not itself look like a leaked key
        service.write_file(project.id, "config.py", f"KEY = '{fake}'\n", actor=who)
        out.append(line("write a file holding a fake secret", "ALLOWED (this is a bug)"))
    except SandboxError as exc:
        out.append(line("write a file holding a fake secret", f"refused: {str(exc)[:90]}"))

    out += ["", "Commands"]
    service.write_file(project.id, "net.py", "import socket\ntry:\n    socket.create_connection(('1.1.1.1', 80), timeout=3); print('NETWORK REACHABLE')\nexcept OSError as e:\n    print('the network was refused:', type(e).__name__)\n", actor=who)
    for program, args in (("python", ["net.py"]), ("curl", ["http://example.com"]), ("pip", ["install", "requests"]), ("python", ["-c", "print(1)"]), ("sh", ["-c", "ls"])):
        r = service.run_command(project.id, program, args, actor=who)
        out.append(line(f"{program} {' '.join(args)}"[:44], f"{r.status}: {(r.reason or r.output).strip()[:80]}"))

    service.write_file(project.id, "tree.py", "import subprocess, sys, time\nsubprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\ntime.sleep(60)\n", actor=who)
    started = time.monotonic()
    r = service.sandbox.run(service.workspace(project.id), "python", ["tree.py"], Limits(seconds=2))
    out.append(line("a command that starts another, run 2 seconds", f"{r.status} after {round(time.monotonic() - started, 1)}s: the whole tree was stopped"))

    out += ["", "Tests"]
    service.write_file(project.id, "test_app.py", "from src.app import add\n\ndef test_add(): assert add(2, 3) == 5\n\ndef test_wrong(): assert add(2, 3) == 6, 'five is not six'\n", actor=who)
    service.write_file(project.id, "src/__init__.py", "", actor=who)
    report = service.run_tests(project.id, actor=who)
    out.append(line("pytest, read from the real run", f"{report.status}: {report.passed} passed, {report.failed} failed, {report.errors} errors, {report.skipped} skipped"))
    for f in report.failures:
        out.append(line(f"  {f.kind}", f"{f.test}: {f.message}"))
    out.append(line("all passed?", str(report.all_passed)))

    out += ["", f"The audit trail has {len(store.audit.list(project.id))} rows for this, none holding file contents or output."]
    return out


def main(argv: Sequence[str] | None = None) -> int:
    if argv:
        print("This demo takes no options.", file=sys.stderr)
        return 2
    with tempfile.TemporaryDirectory(prefix="sdlc_sandbox_demo_") as tmp:
        print("\n".join(demo(Path(tmp))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
