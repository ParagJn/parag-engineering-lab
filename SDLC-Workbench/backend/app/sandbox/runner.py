"""Run one command inside a project's sandbox (S16): checked, contained by the operating system, time-limited, output-limited, secret-redacted.

The five ways a command can end are five different results, so the Build loop (S17) can react to the right one:
    ran        the program ran and exited (any exit code, including a failing test run)
    timed_out  it ran past the limit and its WHOLE process tree was killed
    refused    our own checks said no, before anything started (a program not on the list, a path outside the workspace)
    unavailable  the operating-system protection is missing or failed its self-test: nothing was run
    (an OS refusal INSIDE a running program, such as a denied network call, is just that program failing: it shows in its own output and exit code)

No shell is ever involved: the program and its arguments are a list, so `;`, `&&`, `|` and `$()` are text. The command starts in its own session, so a
timeout can signal the whole group, and a test that leaves a background process behind does not survive the run.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

from . import profile as OS
from .errors import CommandRefused, PathRefused, SandboxError, SandboxUnavailable
from .policy import Command, check_command, clean_environment, python_executable
from .workspace import Workspace

POLITE_SECONDS = 2.0
POLL_SECONDS = 0.05


@dataclass(frozen=True)
class Result:
    status: str                       # ran | timed_out | refused | unavailable
    exit_code: int | None = None
    output: str = ""
    truncated: bool = False
    redacted: bool = False
    seconds: float = 0.0
    reason: str = ""                  # a sentence, for refused / unavailable / timed_out
    limit: str | None = None          # which limit was hit, if any

    @property
    def ok(self) -> bool:
        return self.status == "ran" and self.exit_code == 0


@dataclass
class Limits:
    seconds: int = 60
    output_bytes: int = 256 * 1024
    max_processes: int = 64
    memory_mb: int = 1024          # kept for configuration, but NOT enforced on macOS (see _limit_resources)

    @classmethod
    def from_settings(cls, settings, tests: bool = False) -> "Limits":
        return cls(settings.sandbox_test_seconds if tests else settings.sandbox_command_seconds, settings.sandbox_output_bytes,
                   settings.sandbox_max_processes, settings.sandbox_memory_mb)


class Sandbox:
    """The runner for one machine. Holds the result of the self-test so it is done once, not per command."""

    def __init__(self, sandbox_exec: str = OS.SANDBOX_EXEC, scanner=None):
        self.sandbox_exec = sandbox_exec
        self.scanner = scanner
        self._checked: str | None = None          # "" once passed, or the refusal sentence
        self._lock = threading.Lock()

    # ---- the start-up self-test -----------------------------------------------------------------------------------------------

    def availability(self) -> str:
        """"" when the protection works, otherwise the sentence saying why not. Tested once and remembered."""
        with self._lock:
            if self._checked is None:
                try:
                    OS.self_test(python_executable(), sys.prefix, sys.base_prefix, self.sandbox_exec)
                    self._checked = ""
                except SandboxUnavailable as exc:
                    self._checked = str(exc)
            return self._checked

    # ---- running ----------------------------------------------------------------------------------------------------------------------

    def run(self, workspace: Workspace, program: str, args: Sequence[str] = (), limits: Limits | None = None) -> Result:
        limits = limits or Limits()
        try:
            command = check_command(program, args)
        except CommandRefused as exc:
            return Result("refused", reason=str(exc))
        problem = self.availability()
        if problem:
            return Result("unavailable", reason=problem)
        scratch = Path(tempfile.mkdtemp(prefix="sdlc_scratch_"))
        try:
            return self._run(workspace, command, limits, scratch)
        except SandboxError as exc:
            return Result("refused", reason=str(exc))
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def _run(self, workspace: Workspace, command: Command, limits: Limits, scratch: Path) -> Result:
        cwd = workspace.root.resolve()
        profile_file = scratch / "profile.sb"
        profile_file.write_text(OS.build_profile(cwd, scratch.resolve(), sys.prefix, sys.base_prefix), encoding="utf-8")
        argv = OS.wrap(command.argv, profile_file)
        env = clean_environment(str(scratch.resolve()))
        started = time.monotonic()
        try:
            process = subprocess.Popen(
                argv, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=False,
                start_new_session=True, close_fds=True, preexec_fn=_limit_resources(limits),
            )
        except OSError as exc:
            return Result("unavailable", reason=f"the command could not be started ({type(exc).__name__}), so nothing was run")
        collected = bytearray()
        over = threading.Event()
        reader = threading.Thread(target=_read, args=(process, collected, limits.output_bytes, over), daemon=True)
        reader.start()
        timed_out = False
        while process.poll() is None:
            if time.monotonic() - started > limits.seconds:
                timed_out = True
                break
            if over.is_set():
                break
            time.sleep(POLL_SECONDS)
        group = process.pid                        # the command is its own session, so its process-group id is its process id
        if timed_out or over.is_set():
            kill_tree(process)
        else:
            sweep_group(group)                     # it ended by itself: anything it started and left running must not outlive it
        reader.join(timeout=2)
        seconds = round(time.monotonic() - started, 3)
        text = bytes(collected).decode("utf-8", errors="replace")
        text = scrub_locations(text, workspace.root, scratch)
        text, redacted = self._redact(text)
        truncated = over.is_set() or len(collected) >= limits.output_bytes
        if timed_out:
            return Result("timed_out", None, text, truncated, redacted, seconds, f"the command ran longer than {limits.seconds} seconds and was stopped, along with anything it started", "seconds")
        if over.is_set():
            return Result("ran", process.returncode, text, True, redacted, seconds, f"the command printed more than {limits.output_bytes} bytes and was stopped", "output_bytes")
        return Result("ran", process.returncode, text, truncated, redacted, seconds)

    def _redact(self, text: str) -> tuple[str, bool]:
        if self.scanner is None or not text:
            return text, False
        found = [f for f in self.scanner.scan(text) if f.klass == "secret"]
        if not found:
            return text, False
        lines = text.split("\n")
        for finding in found:
            index = finding.line - 1
            if 0 <= index < len(lines):
                lines[index] = "[a line was removed: it looked like a secret]"
        return "\n".join(lines), True


def current_processes() -> int:
    """How many processes this user owns right now. The operating system's process limit counts ALL of them, not only the command's, so a cap of 64
    would stop a command starting even one child on a busy Mac (measured: 389 were running)."""
    try:
        out = subprocess.run(["/bin/ps", "-u", str(os.getuid()), "-o", "pid="], capture_output=True, text=True, timeout=5).stdout
        return len([line for line in out.splitlines() if line.strip()])
    except (OSError, subprocess.TimeoutExpired):
        return 0


def scrub_locations(text: str, workspace: Path, scratch: Path) -> str:
    """Show paths as they are INSIDE the workspace. A program's own output (a traceback, a pytest header) names the real folder on disk; that is not
    for an agent or a screen. The workspace becomes the current folder ('test_i.py:1'), and the scratch folder becomes '<scratch>'. Both the real
    location and the one the caller used are replaced (on a Mac '/var' and '/private/var' are the same place)."""
    # Longest first, and the real location before the one the caller used: on a Mac '/var/...' and '/private/var/...' are the same folder, and replacing
    # the short form first would leave '/private' behind.
    for candidate in sorted({str(workspace.resolve()), str(workspace)}, key=len, reverse=True):
        text = text.replace(candidate + "/", "").replace(candidate, ".")
    for candidate in sorted({str(scratch.resolve()), str(scratch)}, key=len, reverse=True):
        text = text.replace(candidate, "<scratch>")
    return text


def _limit_resources(limits: Limits):
    """Applied in the child just before it starts: the most processes it may make. The OS counts every process the user owns, so the limit is what
    the user already has PLUS the command's allowance, and never above what the system permits. A fork bomb hits this ceiling and stops.

    A MEMORY limit is not applied: macOS does not enforce one (setting it fails, and a 3 GB allocation under a 1 GB limit went through when measured
    here). The time limit and the process-group kill are the backstop, and the docs say so rather than imply otherwise."""
    ceiling = current_processes() + limits.max_processes

    def apply() -> None:
        try:
            import resource
            soft, hard = resource.getrlimit(resource.RLIMIT_NPROC)
            wanted = ceiling if hard == resource.RLIM_INFINITY else min(ceiling, hard)
            resource.setrlimit(resource.RLIMIT_NPROC, (wanted, hard))
        except (ImportError, ValueError, OSError):
            pass
    return apply


def _read(process: subprocess.Popen, into: bytearray, cap: int, over: threading.Event) -> None:
    """Read the combined output in chunks, keeping at most `cap` bytes, and say so the moment there is more."""
    stream = process.stdout
    if stream is None:
        return
    while True:
        chunk = stream.read1(8192) if hasattr(stream, "read1") else stream.read(8192)
        if not chunk:
            return
        room = cap - len(into)
        if len(chunk) > room:
            into.extend(chunk[:max(room, 0)])
            over.set()
            return
        into.extend(chunk)


def _own_group(group: int | None) -> bool:
    """Is this the group the backend itself belongs to? Signalling it would stop the backend, its test runner and its shell. A command is always started in
    its own session, so this is never true in normal use; it is here because the day it is true by mistake, the damage is the whole server."""
    return group is not None and group == os.getpgrp()


def kill_tree(process: subprocess.Popen) -> None:
    """Stop the command and everything it started: polite first, hard after two seconds. The group id is the process id (the command is its own session)."""
    try:
        group = os.getpgid(process.pid)
    except (ProcessLookupError, PermissionError):
        group = None
    if _own_group(group):
        group = None                                       # never signal our own group: stop only the command's own process
    _signal(group, process, signal.SIGTERM)
    deadline = time.monotonic() + POLITE_SECONDS
    while time.monotonic() < deadline and _alive(group, process):
        time.sleep(POLL_SECONDS)
    if _alive(group, process):
        _signal(group, process, signal.SIGKILL)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def sweep_group(group: int) -> None:
    """Stop whatever is still running in a finished command's process group. A test that exits cleanly but leaves a server or a worker behind must not
    leave it for the next run to find. Polite first, hard after two seconds. (The group id is the command's process id; it is swept within moments of
    the command ending, so the chance that the number now belongs to something else is negligible, and `killpg` only ever signals a group.)"""
    if _own_group(group):
        return                                             # the command is in OUR group: there is nothing of its own to sweep, and signalling it would stop us

    def members() -> bool:
        try:
            os.killpg(group, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False
    if not members():
        return
    try:
        os.killpg(group, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        return
    deadline = time.monotonic() + POLITE_SECONDS
    while time.monotonic() < deadline and members():
        time.sleep(POLL_SECONDS)
    if members():
        try:
            os.killpg(group, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


def _signal(group: int | None, process: subprocess.Popen, sig: int) -> None:
    try:
        if group is not None:
            os.killpg(group, sig)
        else:
            process.send_signal(sig)
    except (ProcessLookupError, PermissionError):
        pass


def _alive(group: int | None, process: subprocess.Popen) -> bool:
    if group is not None:
        try:
            os.killpg(group, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False
    return process.poll() is None
