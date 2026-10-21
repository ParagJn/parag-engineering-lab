from __future__ import annotations

import difflib
import re
from typing import Any

# A paired line must be at least this similar to get word-level highlighting;
# otherwise it is shown as a plain removal plus a plain addition.
PAIR_THRESHOLD = 0.45
_TOKEN = re.compile(r"\s+|\w+|[^\w\s]", re.UNICODE)

Segment = list  # [text, changed]


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _word_segments(a: str, b: str) -> tuple[list[Segment], list[Segment]]:
    tokens_a, tokens_b = _TOKEN.findall(a), _TOKEN.findall(b)
    matcher = difflib.SequenceMatcher(None, tokens_a, tokens_b, autojunk=False)
    segs_a: list[Segment] = []
    segs_b: list[Segment] = []

    def push(target: list[Segment], text: str, changed: bool) -> None:
        if not text:
            return
        if target and target[-1][1] == changed:
            target[-1][0] += text
        else:
            target.append([text, changed])

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        changed = tag != "equal"
        push(segs_a, "".join(tokens_a[i1:i2]), changed)
        push(segs_b, "".join(tokens_b[j1:j2]), changed)
    return segs_a, segs_b


def _side(number: int, text: str, segments: list[Segment] | None = None) -> dict[str, Any]:
    return {"n": number, "text": text, "segs": segments}


def build_diff(text_a: str, text_b: str) -> dict[str, Any]:
    """Aligned, line-based side-by-side diff.

    Rows are {kind, a, b}; kind is equal | replace | delete | insert. A replace row pairs two
    similar lines and carries word-level `segs` ([text, changed] pairs) on each side.
    """
    a_lines, b_lines = _lines(text_a), _lines(text_b)
    matcher = difflib.SequenceMatcher(None, a_lines, b_lines, autojunk=False)
    rows: list[dict[str, Any]] = []
    changes = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for offset in range(i2 - i1):
                rows.append({"kind": "equal", "a": _side(i1 + offset + 1, a_lines[i1 + offset]), "b": _side(j1 + offset + 1, b_lines[j1 + offset])})
            continue

        changes += 1
        if tag == "delete":
            rows.extend({"kind": "delete", "a": _side(i + 1, a_lines[i]), "b": None} for i in range(i1, i2))
        elif tag == "insert":
            rows.extend({"kind": "insert", "a": None, "b": _side(j + 1, b_lines[j])} for j in range(j1, j2))
        else:
            rows.extend(_replace_rows(a_lines, b_lines, i1, i2, j1, j2))

    return {
        "rows": rows,
        "lines_a": len(a_lines),
        "lines_b": len(b_lines),
        "change_blocks": changes,
        "stats": {
            "equal": sum(r["kind"] == "equal" for r in rows),
            "replace": sum(r["kind"] == "replace" for r in rows),
            "delete": sum(r["kind"] == "delete" for r in rows),
            "insert": sum(r["kind"] == "insert" for r in rows),
        },
    }


def _replace_rows(a_lines: list[str], b_lines: list[str], i1: int, i2: int, j1: int, j2: int) -> list[dict[str, Any]]:
    """Pair lines of a replaced block in order, so the nth old line meets the best-matching new line."""
    rows: list[dict[str, Any]] = []
    i, j = i1, j1
    while i < i2 and j < j2:
        ratio = difflib.SequenceMatcher(None, a_lines[i], b_lines[j], autojunk=False).ratio()
        if ratio >= PAIR_THRESHOLD:
            segs_a, segs_b = _word_segments(a_lines[i], b_lines[j])
            rows.append({"kind": "replace", "a": _side(i + 1, a_lines[i], segs_a), "b": _side(j + 1, b_lines[j], segs_b)})
            i += 1
            j += 1
            continue
        # Not a pair: advance whichever side has more lines left, so blocks of unequal size drift into step.
        if (i2 - i) >= (j2 - j):
            rows.append({"kind": "delete", "a": _side(i + 1, a_lines[i]), "b": None})
            i += 1
        else:
            rows.append({"kind": "insert", "a": None, "b": _side(j + 1, b_lines[j])})
            j += 1
    rows.extend({"kind": "delete", "a": _side(k + 1, a_lines[k]), "b": None} for k in range(i, i2))
    rows.extend({"kind": "insert", "a": None, "b": _side(k + 1, b_lines[k])} for k in range(j, j2))
    return rows
