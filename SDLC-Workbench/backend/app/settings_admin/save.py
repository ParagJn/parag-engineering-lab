"""Saving settings into the env file (S23e). The one place the app WRITES backend/.env.

Rules that make it safe:
  * only names in the catalogue can be written, and only non-hidden ones;
  * the candidate file is checked by the app's OWN Settings class before anything is written, so the limits are exactly the ones the app enforces;
  * a problem is reported as the variable's name and the app's sentence, never the value that was typed (it could be a secret);
  * a secret left blank keeps its current value (a blank box means "no change", so a key is never erased by accident); a non-secret blank means "empty";
  * the old file is copied to backend/data/env-backups/ first (a git-ignored folder, owner-only permissions, the last BACKUPS_KEPT kept) - never beside the file, where git would see it;
  * the new file is written to a temporary file in the same folder and swapped in, so a crash can never leave half a file;
  * the audit row records WHO changed WHICH variable names, and for a non-secret the old and new value; a secret's value is never recorded.
The running app keeps using the values it started with: a saved change takes effect after a restart, and `pending` says so until then.
"""
from __future__ import annotations

import io
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from dotenv import dotenv_values
from pydantic import ValidationError

from ..config import Settings
from . import envfile as E
from .catalogue import BY_KEY

BACKUPS_KEPT = 10


class SaveRefused(ValueError):
    """The save was refused. `problems` is a list of plain sentences, each naming a variable and never a value."""

    def __init__(self, message: str, problems: list[str] | None = None):
        super().__init__(message)
        self.problems = list(problems or [])


@dataclass
class Saved:
    changed: list[str] = field(default_factory=list)            # variable names, upper case
    backup: str = ""                                            # the backup's file name (no folder)
    restart: bool = True


def _text_of(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value).strip()


def plan(edits: Mapping[str, Any]) -> dict[str, str]:
    """From what was asked to the variables to write: validated names, secrets that are blank dropped, everything else as text."""
    out: dict[str, str] = {}
    problems: list[str] = []
    for key, value in edits.items():
        setting = BY_KEY.get(key)
        if setting is None or setting.hidden:
            problems.append(f"{key} is not a setting that can be changed here")
            continue
        text = _text_of(value)
        if setting.secret and text == "":
            continue                                           # blank = keep the current value
        if setting.kind == "yes_no" and text.lower() not in ("true", "false"):
            problems.append(f"{setting.env_name} must be true or false")
            continue
        if setting.kind == "choice" and text not in setting.choices:
            problems.append(f"{setting.env_name} must be one of {', '.join(setting.choices)}")
            continue
        out[setting.env_name] = text.lower() if setting.kind == "yes_no" else text
    if problems:
        raise SaveRefused("some settings cannot be saved", problems)
    return out


def check(new_text: str) -> None:
    """Load the candidate text exactly as the app would, and refuse with the variable names and the app's own sentences. The typed value is never repeated."""
    values = {k: (v or "") for k, v in dotenv_values(stream=io.StringIO(new_text)).items()}
    try:
        Settings(_env_file=None, **{k.lower(): v for k, v in values.items() if k.lower() in Settings.model_fields})
    except ValidationError as exc:
        problems = []
        for err in exc.errors(include_input=False, include_url=False, include_context=False):
            where = ".".join(str(p) for p in err["loc"]) or "settings"
            name = where.upper() if where.lower() in Settings.model_fields else where
            problems.append(f"{name}: {err['msg']}")
        raise SaveRefused("the settings were not saved because the app would not accept them", problems) from None
    except ValueError as exc:                                  # a rule written as a plain ValueError in a validator
        raise SaveRefused("the settings were not saved because the app would not accept them", [str(exc)[:300]]) from None


def backup(env_file: Path, backups: Path) -> str:
    """Copy the current file into the backups folder with owner-only permissions, keep the newest BACKUPS_KEPT, and return the backup's name."""
    backups.mkdir(parents=True, exist_ok=True)
    os.chmod(backups, 0o700)
    stamp = time.strftime("env-%Y%m%d-%H%M%S", time.gmtime())
    used = [int(p.stem.rsplit("-", 1)[-1]) for p in backups.glob(f"{stamp}-*.bak") if p.stem.rsplit("-", 1)[-1].isdigit()]
    name = f"{stamp}-{(max(used) + 1) if used else 1:06d}.bak"                         # sorts by time, and by order within the same second
    target = backups / name
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(env_file.read_bytes() if env_file.exists() else b"")
    for stale in sorted(backups.glob("env-*.bak"))[:-BACKUPS_KEPT]:
        stale.unlink()
    return name


def write_atomic(env_file: Path, text: str) -> None:
    """Write beside the file and swap it in, keeping the old file's permissions (owner-only when it had none)."""
    mode = (env_file.stat().st_mode & 0o777) if env_file.exists() else 0o600
    fd, tmp = tempfile.mkstemp(prefix=".env-", dir=str(env_file.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
        os.chmod(tmp, mode)
        os.replace(tmp, env_file)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def audit_detail(before: str, after: str, names: list[str]) -> dict[str, Any]:
    """What the audit row keeps: the variable names, and for a non-secret the old and new value. A secret's value is never kept."""
    old, new = E.parse(before), E.parse(after)
    detail: dict[str, Any] = {"variables": names}
    values: dict[str, Any] = {}
    for name in names:
        setting = BY_KEY.get(name.lower())
        if setting is None or setting.secret:
            continue
        values[name] = {"before": old.get(name, ""), "after": new.get(name, "")}
    if values:
        detail["values"] = values
    secrets = [n for n in names if BY_KEY.get(n.lower()) is not None and BY_KEY[n.lower()].secret]
    if secrets:
        detail["secrets_changed"] = secrets
    return detail


def save(env_file: Path, backups: Path, edits: Mapping[str, Any], *, record) -> Saved:
    """Validate, back up, write. `record(detail)` is called once with the audit detail after the file has been swapped in. Nothing is written if anything is refused."""
    current = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
    new_text = E.apply(current, plan(edits))
    names = E.changed_names(current, new_text)
    if not names:
        return Saved(changed=[], backup="", restart=False)
    check(new_text)
    name = backup(env_file, backups)
    write_atomic(env_file, new_text)
    record(audit_detail(current, new_text, names))
    return Saved(changed=names, backup=name, restart=True)


def restore(env_file: Path, backups: Path, name: str, *, record) -> Saved:
    """Put an earlier backup back (after backing up the file as it is now). Only a file in the backups folder, by its plain name."""
    if "/" in name or "\\" in name or not name.startswith("env-") or not name.endswith(".bak"):
        raise SaveRefused("that is not a backup of the settings file")
    source = backups / name
    if not source.is_file():
        raise SaveRefused("that backup does not exist")
    text = source.read_text(encoding="utf-8")
    check(text)
    current = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
    names = E.changed_names(current, text)
    made = backup(env_file, backups)
    write_atomic(env_file, text)
    record({**audit_detail(current, text, names), "restored": name})
    return Saved(changed=names, backup=made, restart=bool(names))


def list_backups(backups: Path) -> list[dict[str, Any]]:
    if not backups.is_dir():
        return []
    return [{"name": p.name, "size": p.stat().st_size} for p in sorted(backups.glob("env-*.bak"), reverse=True)]
