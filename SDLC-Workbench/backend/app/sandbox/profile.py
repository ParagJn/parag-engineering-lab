"""The operating-system layer of the sandbox (S16): a `sandbox-exec` profile, and a self-test that must pass before anything is run.

Our own checks (paths, allow-list, limits) stop a MISTAKEN agent. They cannot stop a program from doing something we did not think of, such as opening
a socket. Only the operating system can, so every command runs under a profile that denies, by default, everything except:

  * starting programs and the few system services Python needs,
  * READING the system, the Python install and the venv (so Python and pytest start), and the project's own workspace and scratch folder,
  * WRITING only inside the project's workspace and scratch folder (and /dev/null).

The network is denied outright. The app's database, `.env`, recordings, other projects' workspaces and the user's home are not on the read list, so they
are unreadable. If this layer is missing or its self-test fails, NOTHING IS RUN: there is no quieter fallback to "trust the allow-list".

Found by trying it (macOS 27): a profile that allows reading everything and denies only some paths WORKS but leaks; the narrow profile below works only
if the command's working directory is inside the workspace, so the runner always sets it there.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .errors import SandboxUnavailable

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
_SAFE_PATH = re.compile(r"^[A-Za-z0-9_./ \-+@=,:~]+$")

# What every command may read: enough for Python and pytest to start, nothing of the app's own data.
SYSTEM_READ = ("/usr", "/System", "/Library/Frameworks", "/private/etc", "/private/var/db", "/dev", "/bin", "/sbin", "/opt/homebrew", "/Applications/Xcode.app")


def _check_path(path: str, what: str) -> str:
    """A path goes into the profile as text. It must hold nothing that could end the string or start a new rule."""
    if not isinstance(path, str) or not _SAFE_PATH.match(path) or ".." in path.split("/") or not path.startswith("/"):
        raise SandboxUnavailable(f"the {what} has a name the sandbox cannot place in its rules safely; use a folder with a plain name")
    return path


def real(path: str | Path) -> str:
    """The real, absolute location (the profile matches real paths: /tmp is /private/tmp)."""
    return str(Path(path).resolve())


def build_profile(workspace: str | Path, scratch: str | Path, python_prefix: str | Path, python_base: str | Path | None = None) -> str:
    """The profile text for one workspace. Pure: the same inputs give the same text."""
    ws = _check_path(real(workspace), "workspace")
    sc = _check_path(real(scratch), "scratch folder")
    venv = _check_path(real(python_prefix), "Python environment")
    base = _check_path(real(python_base), "Python install") if python_base else None
    lines = [
        "(version 1)",
        "(deny default)",
        "(allow process-fork)",
        "(allow process-exec*)",
        "(allow signal (target self))",
        "(allow sysctl-read)",
        "(allow mach-lookup)",
        "(allow ipc-posix-shm)",
        "(allow file-read-metadata)",
        '(allow file-read* (literal "/"))',
    ]
    for folder in SYSTEM_READ:
        lines.append(f'(allow file-read* (subpath "{folder}"))')
    lines.append(f'(allow file-read* (subpath "{venv}"))')
    if base:
        lines.append(f'(allow file-read* (subpath "{base}"))')
    lines.append(f'(allow file-read* file-write* (subpath "{ws}") (subpath "{sc}"))')
    lines.append('(allow file-write* (literal "/dev/null") (literal "/dev/dtracehelper"))')
    lines.append("(deny network*)")
    return "\n".join(lines) + "\n"


def sandbox_available() -> bool:
    return sys.platform == "darwin" and os.access(SANDBOX_EXEC, os.X_OK)


def wrap(argv: list[str], profile_file: str | Path) -> list[str]:
    """The command line that runs `argv` under the profile."""
    return [SANDBOX_EXEC, "-f", str(profile_file), *argv]


_SELF_TEST = r"""
import pathlib, socket, sys
problems = []
try:
    socket.create_connection(("1.1.1.1", 80), timeout=2)
    problems.append("the network was reachable")
except PermissionError:
    pass
except OSError as e:
    if getattr(e, "errno", None) != 1:
        problems.append("the network was not refused by the sandbox: %s" % type(e).__name__)
try:
    pathlib.Path(sys.argv[1]).write_text("x")
    problems.append("a write outside the workspace succeeded")
except PermissionError:
    pass
except OSError:
    problems.append("a write outside the workspace failed in an unexpected way")
try:
    pathlib.Path("inside.txt").write_text("ok")
except OSError:
    problems.append("a write inside the workspace was refused")
print("PROBLEMS:" + "|".join(problems) if problems else "SELF-TEST-OK")
"""


def self_test(python: str, python_prefix: str | Path, python_base: str | Path | None = None, sandbox_exec: str = SANDBOX_EXEC) -> None:
    """Run a harmless child under a real profile and require that the network and a write outside the workspace are both refused.

    Raises SandboxUnavailable (with a sentence) if the protection is missing or does not behave. Nothing is written outside a temporary folder."""
    if sys.platform != "darwin":
        raise SandboxUnavailable(f"the sandbox needs macOS's sandbox-exec; this machine is {sys.platform}, so no command will be run")
    if not os.access(sandbox_exec, os.X_OK):
        raise SandboxUnavailable("sandbox-exec is not available on this machine, so no command will be run: without it nothing stops generated code from using the network")
    with tempfile.TemporaryDirectory(prefix="sdlc_selftest_") as tmp:
        root = Path(tmp).resolve()
        workspace, scratch, outside = root / "ws", root / "scratch", root / "outside"
        workspace.mkdir()
        scratch.mkdir()
        outside.mkdir()
        profile = root / "profile.sb"
        profile.write_text(build_profile(workspace, scratch, python_prefix, python_base), encoding="utf-8")
        target = outside / "should_not_exist.txt"
        try:
            run = subprocess.run(
                [sandbox_exec, "-f", str(profile), python, "-c", _SELF_TEST, str(target)],
                cwd=str(workspace), capture_output=True, text=True, timeout=30, env={"PATH": "/usr/bin:/bin", "HOME": str(scratch), "PYTHONDONTWRITEBYTECODE": "1"},
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SandboxUnavailable(f"the sandbox self-test could not run ({type(exc).__name__}), so no command will be run") from exc
        said = (run.stdout or "").strip().splitlines()[-1:] or [""]
        if said[0] != "SELF-TEST-OK":
            detail = said[0].removeprefix("PROBLEMS:").replace("|", "; ") if said[0].startswith("PROBLEMS:") else "the test program did not run under the sandbox"
            raise SandboxUnavailable(f"the sandbox self-test failed ({detail}), so no command will be run")
        if target.exists():
            raise SandboxUnavailable("the sandbox self-test found a file written outside the workspace, so no command will be run")
