"""One project's workspace: a folder where generated code is written, and the file tools that touch it (S16).

Every path an agent gives is RELATIVE to the workspace and is checked here before anything touches the disk. The checks stop a mistaken agent. They are
not the only protection: a command that runs in the workspace is also contained by the operating system (runner.py), because a check we wrote cannot
stop a program from doing something we did not think of.

What a path may be:  letters, digits, dots, dashes, underscores and slashes, no `..`, no leading slash, no hidden control names (`.env`, `.git`), at
most 200 characters and 12 levels. Symlinks are never created, and one already present is never followed out of the workspace.
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from .errors import ContentRefused, LimitExceeded, PathRefused

MAX_PATH_CHARS = 200
MAX_DEPTH = 12
_PART = re.compile(r"^[A-Za-z0-9._\-]+$")
_FORBIDDEN_NAMES = {".env", ".git", ".ssh", ".aws", ".netrc", ".npmrc", ".pypirc", ".gnupg", "id_rsa", "id_ed25519"}
_FORBIDDEN_SUFFIXES = (".pem", ".key", ".p12", ".pfx")
_PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


@dataclass(frozen=True)
class Limits:
    file_bytes: int = 1024 * 1024
    max_files: int = 500
    total_bytes: int = 50 * 1024 * 1024

    @classmethod
    def from_settings(cls, settings) -> "Limits":
        return cls(settings.sandbox_file_bytes, settings.sandbox_max_files, settings.sandbox_total_bytes)


def check_relative(path: str) -> tuple[str, ...]:
    """The parts of a good relative path, or PathRefused with the reason. Looks only at the text; `Workspace.resolve` also looks at the disk."""
    if not isinstance(path, str) or not path.strip():
        raise PathRefused("give a file path, like 'src/app.py'")
    if path != path.strip():
        raise PathRefused("a path cannot start or end with spaces")
    if len(path) > MAX_PATH_CHARS:
        raise PathRefused(f"a path is limited to {MAX_PATH_CHARS} characters")
    if any(ord(c) < 32 or ord(c) == 127 for c in path):
        raise PathRefused("a path cannot hold control characters")
    if "\\" in path:
        raise PathRefused("write paths with forward slashes, like 'src/app.py'")
    if path.startswith("/") or re.match(r"^[A-Za-z]:", path) or path.startswith("~"):
        raise PathRefused("a path is relative to the project's workspace: it cannot start with '/', '~' or a drive letter")
    parts = tuple(p for p in path.split("/") if p not in ("", "."))
    if not parts:
        raise PathRefused("that path is the workspace itself; name a file or folder inside it")
    if len(parts) > MAX_DEPTH:
        raise PathRefused(f"a path is limited to {MAX_DEPTH} levels")
    for part in parts:
        if part == "..":
            raise PathRefused("a path cannot go up with '..'")
        if not _PART.match(part):
            raise PathRefused("a path may hold only letters, digits, dots, dashes, underscores and slashes")
        if set(part) == {"."}:
            raise PathRefused("a path part cannot be only dots")
        lowered = part.lower()
        if lowered in _FORBIDDEN_NAMES or lowered.endswith(_FORBIDDEN_SUFFIXES) or lowered.startswith(".env"):
            raise PathRefused(f"'{part}' is a name reserved for credentials and cannot be written")
    return parts


class Workspace:
    """The folder for one project. All file tools are methods here."""

    def __init__(self, root: Path, limits: Limits | None = None, scanner=None):
        self.root = Path(root)
        self.limits = limits or Limits()
        self.scanner = scanner
        self.root.mkdir(parents=True, exist_ok=True)
        self._real = self.root.resolve()

    @classmethod
    def for_project(cls, base: Path, project_id: str, limits: Limits | None = None, scanner=None) -> "Workspace":
        if not isinstance(project_id, str) or not _PROJECT_ID.match(project_id):
            raise PathRefused("a project id may hold only letters, digits, dashes and underscores")
        return cls(Path(base) / project_id, limits, scanner)

    # ---- resolving ----------------------------------------------------------------------------------------------------------

    def resolve(self, path: str, *, must_exist: bool = False) -> Path:
        """The real location of a relative path, refused if any step of it is a symlink or leaves the workspace."""
        parts = check_relative(path)
        self._check_root()
        current = self._real
        for part in parts:
            current = current / part
            if current.is_symlink():
                raise PathRefused("a path cannot go through a symlink")
            if current.exists():
                real = current.resolve()
                if real != self._real and self._real not in real.parents:
                    raise PathRefused("that path leaves the workspace")
        final = self._real.joinpath(*parts)
        if must_exist and not final.exists():
            raise PathRefused(f"{'/'.join(parts)} does not exist")
        return final

    def _check_root(self) -> None:
        """The workspace folder itself must still be the real folder it was when opened. If it was swapped for a symlink (or moved) since, nothing is
        written or read: a path inside a swapped root would otherwise be checked against the OLD location and pass."""
        if self.root.is_symlink() or not self.root.is_dir() or self.root.resolve() != self._real:
            raise PathRefused("the workspace folder has been replaced or moved, so nothing can be read or written until it is opened again")

    def shown(self, path: Path) -> str:
        """A path as the agent sees it: inside the workspace, never the real location."""
        try:
            return path.resolve().relative_to(self._real).as_posix()
        except ValueError:
            return "(outside the workspace)"

    # ---- counting ----------------------------------------------------------------------------------------------------------------

    def _walk(self) -> Iterable[Path]:
        for dirpath, dirnames, filenames in os.walk(self._real, followlinks=False):
            dirnames[:] = [d for d in dirnames if not Path(dirpath, d).is_symlink()]
            for name in filenames:
                full = Path(dirpath, name)
                if not full.is_symlink():
                    yield full

    def usage(self) -> tuple[int, int]:
        """(number of files, total bytes) in the workspace."""
        self._check_root()
        count = size = 0
        for full in self._walk():
            count += 1
            try:
                size += full.stat().st_size
            except OSError:
                pass
        return count, size

    # ---- the tools -------------------------------------------------------------------------------------------------------------

    def write_file(self, path: str, text: str) -> str:
        """Write a text file, replacing any earlier one. Atomic: the old file stays whole if this fails. Returns the path as shown."""
        target = self.resolve(path)
        if not isinstance(text, str):
            raise ContentRefused("a file's content must be text")
        data = text.encode("utf-8")
        if b"\x00" in data:
            raise ContentRefused("a file's content cannot contain NUL bytes: it must be text")
        if len(data) > self.limits.file_bytes:
            raise LimitExceeded(f"a file is limited to {self.limits.file_bytes} bytes; this one is {len(data)}", "file_bytes")
        if self.scanner is not None:
            problems = self.scanner.problems(text)
            if problems:
                raise ContentRefused(f"{self.shown(target)} holds something that looks like a secret ({problems[0]}); remove it and write the file again")
        if target.is_dir():
            raise PathRefused(f"{self.shown(target)} is a folder")
        count, total = self.usage()
        existing = target.stat().st_size if target.exists() else 0
        if not target.exists() and count + 1 > self.limits.max_files:
            raise LimitExceeded(f"a workspace is limited to {self.limits.max_files} files", "max_files")
        if total - existing + len(data) > self.limits.total_bytes:
            raise LimitExceeded(f"a workspace is limited to {self.limits.total_bytes} bytes in all", "total_bytes")
        self._make_parents(target)
        handle, temp = tempfile.mkstemp(prefix=".write-", dir=str(target.parent))
        try:
            with os.fdopen(handle, "wb") as out:
                out.write(data)
            os.replace(temp, target)
        except BaseException:
            try:
                os.unlink(temp)
            except OSError:
                pass
            raise
        return self.shown(target)

    def read_file(self, path: str) -> str:
        target = self.resolve(path, must_exist=True)
        if target.is_dir():
            raise PathRefused(f"{self.shown(target)} is a folder; list it instead")
        if target.stat().st_size > self.limits.file_bytes:
            raise LimitExceeded(f"{self.shown(target)} is larger than the {self.limits.file_bytes}-byte limit", "file_bytes")
        return target.read_bytes().decode("utf-8", errors="replace")

    def list_files(self, path: str | None = None) -> list[str]:
        """Files under a folder (or the whole workspace), as shown paths, sorted. Symlinks are not followed or listed."""
        self._check_root()
        base = self._real if path in (None, "", ".") else self.resolve(path, must_exist=True)
        if base.is_file():
            return [self.shown(base)]
        found = [self.shown(p) for dirpath, _, names in os.walk(base, followlinks=False) for p in (Path(dirpath, n) for n in names) if not p.is_symlink()]
        return sorted(found)

    def delete_file(self, path: str) -> None:
        target = self.resolve(path, must_exist=True)
        if target.is_dir():
            raise PathRefused(f"{self.shown(target)} is a folder; only files can be deleted")
        target.unlink()

    def make_dir(self, path: str) -> str:
        target = self.resolve(path)
        if target.exists() and not target.is_dir():
            raise PathRefused(f"{self.shown(target)} is a file")
        self._make_parents(target / "x")
        return self.shown(target)

    def _make_parents(self, target: Path) -> None:
        """Make the folders above a file, one level at a time, checking each is still inside BEFORE going on, so a refusal leaves nothing behind.

        `resolve` has already refused a symlink anywhere in the path. A folder swapped for a link in the instant since is caught by the containment check below
        if it points outside, and is harmless if it points inside, so the symlink test is not repeated here."""
        self._check_root()
        current = self._real
        for part in target.parent.relative_to(self._real).parts:
            current = current / part
            if not current.exists():
                current.mkdir()
            real = current.resolve()
            if real != self._real and self._real not in real.parents:                      # a folder made a moment ago still has to be inside
                raise PathRefused("that path leaves the workspace")

    def reset(self) -> None:
        """Empty the workspace (used between runs by the caller that owns it)."""
        self._check_root()
        for child in list(self._real.iterdir()):
            if child.is_symlink() or child.is_file():
                child.unlink()
            else:
                shutil.rmtree(child)
