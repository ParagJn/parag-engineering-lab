"""Editing the text of an env file, and nothing else (S23e). Pure functions over a string: no file, no network, no model.

The rule is "touch only the lines being changed". Comments, blank lines, the order of the lines and every other variable are kept byte for byte. A changed variable is rewritten in
place, with a note that trails it kept; one that is not in the file yet is added at the end. A value that has a space, a quote, a `#` or a leading/trailing space is written in double
quotes with the quotes and backslashes escaped, so the app's own reader gives back exactly what was typed.
"""
from __future__ import annotations

import re
from io import StringIO

from dotenv import dotenv_values

_LINE = re.compile(r"^(?P<lead>\s*(?:export\s+)?)(?P<name>[A-Za-z_][A-Za-z0-9_]*)(?P<eq>\s*=\s*)(?P<rest>.*?)(?P<nl>\r?\n?)$")
_NEEDS_QUOTES = re.compile(r"""[\s"'#\\$`]""")
MAX_VALUE_CHARS = 2000


class EnvError(ValueError):
    """A plain sentence a person can read."""


def quote(value: str) -> str:
    """A value as it is written on the right of the equals sign: bare when that is safe, otherwise double-quoted with the quotes and backslashes escaped."""
    if "\n" in value or "\r" in value or "\x00" in value:
        raise EnvError("a value cannot contain a line break")
    if len(value) > MAX_VALUE_CHARS:
        raise EnvError(f"a value is at most {MAX_VALUE_CHARS} characters")
    if value == "" or not _NEEDS_QUOTES.search(value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def parse(text: str) -> dict[str, str]:
    """The variables an env text defines, as the app's own reader sees them. A variable with no value reads as an empty string."""
    return {k: (v or "") for k, v in dotenv_values(stream=StringIO(text)).items()}


def _trailing_note(rest: str) -> str:
    """The `  # note` that follows an unquoted or quoted value on the same line, kept when the line is rewritten. Empty when there is none."""
    s = rest.strip()
    if s[:1] in ("'", '"'):
        end = s.find(s[0], 1)
        while end != -1 and s[end - 1] == "\\":
            end = s.find(s[0], end + 1)
        tail = s[end + 1:] if end != -1 else ""
    else:
        i = s.find(" #")
        tail = s[i:] if i != -1 else ""
    return tail.rstrip() if tail.strip().startswith("#") else ""


def apply(text: str, changes: dict[str, str]) -> str:
    """The text with these variables set. Unknown lines are kept as they are. If a name appears twice only the LAST line (the one that wins) is rewritten."""
    for name in changes:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
            raise EnvError(f"{name!r} is not a variable name")
    lines = text.splitlines(keepends=True)
    last: dict[str, int] = {}
    for i, line in enumerate(lines):
        m = _LINE.match(line)
        if m and m["name"] in changes:                         # a comment never matches the pattern (it needs a name first), so a commented-out variable is left alone
            last[m["name"]] = i
    for name, i in last.items():
        m = _LINE.match(lines[i])
        assert m is not None
        note = _trailing_note(m["rest"])
        lines[i] = f"{m['lead']}{name}{m['eq'].strip() or '='}{quote(changes[name])}{note}{m['nl'] or chr(10)}"
    missing = [n for n in changes if n not in last]
    if missing:
        if lines and not lines[-1].endswith(("\n", "\r\n")):
            lines[-1] += "\n"
        lines += [f"{n}={quote(changes[n])}\n" for n in missing]
    return "".join(lines)


def changed_names(before: str, after: str) -> list[str]:
    """The variables whose value differs between two texts (by the app's reader), in name order. Used for the audit row, which records names and never secret values."""
    a, b = parse(before), parse(after)
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
