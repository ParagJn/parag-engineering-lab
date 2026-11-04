"""The safe walk over a folder the person named (S20a, decision 1).

The rules, all of them enforced here and nowhere else:
  * only TEXT files, only UNDER the named folder; a link (file or folder) is never followed, so nothing can lead out of it;
  * never `.env*`, keys, certificates, `.git`, `node_modules`, virtual environments, caches or build output;
  * never a file over MAX_FILE_CHARS, never more than MAX_FILES files, and when it stops early it SAYS so;
  * nothing is written, nothing is imported, nothing is executed.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

MAX_FILES = 3000
MAX_FILE_CHARS = 500_000
MAX_DEPTH = 12

SKIP_DIRS = frozenset({
    ".git", ".hg", ".svn", "node_modules", "venv", ".venv", "env", "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".idea", ".vscode",
    "dist", "build", "out", ".next", ".nuxt", ".svelte-kit", "coverage", ".cache", "site-packages", "target", "bin", "obj",
})
SKIP_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".crt", ".cer", ".der", ".jks", ".keystore", ".kdbx", ".ppk", ".sqlite", ".sqlite3", ".db")
SKIP_NAMES = frozenset({"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519", "credentials", "secrets.json", "secrets.yaml", "secrets.yml", ".netrc", ".npmrc", ".pypirc"})
TEXT_SUFFIXES = frozenset({".py", ".pyi", ".sql", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".vue", ".svelte", ".html", ".htm", ".json", ".md", ".txt", ".toml", ".cfg", ".ini", ".yaml", ".yml"})


def is_secret_name(name: str) -> bool:
    lowered = name.lower()
    return lowered.startswith(".env.") or lowered.endswith(".env") or lowered in SKIP_NAMES or lowered.startswith("id_") or lowered.endswith(SKIP_SUFFIXES)


@dataclass(frozen=True)
class SourceFile:
    path: str            # relative to the folder, with forward slashes
    text: str


@dataclass
class Walked:
    root: str
    files: list[SourceFile] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)       # plain sentences: what was left out and why (bounded)
    stopped: str | None = None                             # set when the walk ended early

    def add_skip(self, sentence: str) -> None:
        if len(self.skipped) < 50:
            self.skipped.append(sentence)


class FolderProblem(ValueError):
    """The path cannot be read. The message is a sentence for the person."""


def check_folder(path: str) -> Path:
    raw = (path or "").strip()
    if not raw or "\x00" in raw:
        raise FolderProblem("give the folder as a path on this computer, for example /Users/you/project/backend")
    folder = Path(raw).expanduser()
    if not folder.is_absolute():
        raise FolderProblem(f"'{raw[:120]}' is not an absolute path; write the whole path from the top, for example /Users/you/project/backend")
    if folder.is_symlink():
        raise FolderProblem(f"'{raw[:120]}' is a link; give the real folder it points to")
    if not folder.exists():
        raise FolderProblem(f"there is no folder at '{raw[:120]}' on the computer the backend runs on")
    if not folder.is_dir():
        raise FolderProblem(f"'{raw[:120]}' is a file, not a folder")
    return folder.resolve()


def walk(path: str, *, suffixes: frozenset[str] = TEXT_SUFFIXES, max_files: int = MAX_FILES) -> Walked:
    """Every readable text file under `path`, in a stable order (sorted by relative path), with what was skipped and whether the walk stopped early."""
    root = check_folder(path)
    out = Walked(root=str(root))
    seen = 0
    for current, dirs, names in os.walk(root, followlinks=False):
        here = Path(current)
        depth = len(here.relative_to(root).parts)
        kept = []
        for d in sorted(dirs):
            full = here / d
            if d in SKIP_DIRS or d.startswith(".") and d not in (".github",):
                out.add_skip(f"left out the folder {(full.relative_to(root)).as_posix()}/ (not source code)")
            elif full.is_symlink():
                out.add_skip(f"left out the link {(full.relative_to(root)).as_posix()} (links are never followed)")
            elif depth + 1 > MAX_DEPTH:
                out.add_skip(f"left out {(full.relative_to(root)).as_posix()}/ (more than {MAX_DEPTH} folders deep)")
            else:
                kept.append(d)
        dirs[:] = kept
        for name in sorted(names):
            full = here / name
            rel = full.relative_to(root).as_posix()
            if is_secret_name(name):
                out.add_skip(f"left out {rel} (it may hold a secret)")
                continue
            if full.is_symlink():
                out.add_skip(f"left out the link {rel} (links are never followed)")
                continue
            if full.suffix.lower() not in suffixes:
                continue
            if seen >= max_files:
                out.stopped = f"stopped after {max_files} files; the rest of the folder was not read"
                out.files.sort(key=lambda f: f.path)
                return out
            try:
                if full.stat().st_size > MAX_FILE_CHARS * 4:
                    out.add_skip(f"left out {rel} (too large)")
                    continue
                text = full.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                out.add_skip(f"could not read {rel}: {exc.strerror or 'unreadable'}")
                continue
            if len(text) > MAX_FILE_CHARS:
                out.add_skip(f"left out {rel} (over {MAX_FILE_CHARS} characters)")
                continue
            seen += 1
            out.files.append(SourceFile(rel, text))
    out.files.sort(key=lambda f: f.path)
    return out
