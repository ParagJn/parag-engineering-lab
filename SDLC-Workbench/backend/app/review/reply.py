"""Reading a reviewer's reply and turning it into findings the system can trust.

    <review>
    Summary: one or two sentences.
    - [HIGH] FR-004: What is wrong. Fix: what would fix it.
    - [LOW] Open questions: Another problem. Fix: its fix.
    </review>

The parser is strict about the shape and lenient about the usual mess (chatter outside the block, a code fence
around the whole reply). The VERDICT is not the reviewer's to give: it is computed here from the findings,
so a model cannot write "looks great" next to a list of serious problems.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from ..agents.reply import MAX_PROBLEMS, TRUNCATED_REASONS, ReplyFormatError, unfenced_lines
from ..agents.skills import normalise_heading

SEVERITIES = ("high", "medium", "low")
GENERAL = "General"
MAX_TEXT_CHARS = 1500           # the summary and the problem
MAX_FIX_CHARS = 3000            # a fix is the replacement text itself, so it may be a whole paragraph or a few list entries
MAX_TARGET_WORDS = 8
MAX_TARGET_IDS = 6      # one finding may name up to this many items; a longer list is left whole, fails validation and goes back to the reviewer

_OPEN = re.compile(r"^\s*<review>\s*$", re.IGNORECASE)
_CLOSE = re.compile(r"^\s*</review>\s*$", re.IGNORECASE)
_FENCE = re.compile(r"^\s{0,3}(```|~~~)")
_SUMMARY = re.compile(r"^\s*Summary\s*:\s*(?P<text>.*)$", re.IGNORECASE)
_FINDING = re.compile(r"^\s*(?:[-*+]\s*)?\[(?P<severity>[A-Za-z]+)\]\s*(?P<rest>.*)$")  # the bullet is optional
_TARGET_ID = re.compile(r"^(?P<target>[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3,})\s*[:\-–—]\s*(?P<rest>.*)$")
_FIX = re.compile(r"\bFix\s*:\s*", re.IGNORECASE)
# A file of the Build instruction set, optionally with a line: `UC-002-reserve-a-room.md` or `UC-002-reserve-a-room.md:41`. Read BEFORE the item-ID form, because a file name
# starts with an item ID (`UC-002-...`) and would otherwise be cut at its first dash.
_FILE_TARGET = re.compile(r"^[*_`'\"]*(?P<target>[A-Za-z0-9][A-Za-z0-9._-]*\.md(?::\d{1,5})?)[*_`'\"]*\s*:\s*(?P<rest>.*)$")


@dataclass(frozen=True)
class Finding:
    severity: str  # "high" | "medium" | "low"
    target: str  # an item ID, a section heading, a file (`UC-001-a.md`) or a line in one (`UC-001-a.md:41`), or "General"
    problem: str
    fix: str
    source: str = ""  # "" for the reviewer; "system" for a finding the system's own checks made (no model, no cost)

    def as_dict(self) -> dict[str, str]:
        out = {"severity": self.severity, "target": self.target, "problem": self.problem, "fix": self.fix}
        if self.source:
            out["source"] = self.source          # only when set, so every review stored before this existed reads exactly as it did
        return out


@dataclass(frozen=True)
class ParsedReview:
    summary: str
    findings: tuple[Finding, ...]


def parse_review(text: str) -> ParsedReview:
    """The summary and findings between the <review> tags. Raises ReplyFormatError, in words the model can act on."""
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    body: list[str] = []
    state = "before"  # before -> inside -> after
    fence: str | None = None
    for line in lines:
        if state == "before":
            if _OPEN.match(line):
                state = "inside"
            continue
        if state == "inside":
            fence_match = _FENCE.match(line)
            if fence_match:
                marker = fence_match.group(1)
                fence = marker if fence is None else (None if marker == fence else fence)
                body.append(line)
                continue
            if fence is None and _CLOSE.match(line):
                state = "after"
                continue
            if fence is None and _OPEN.match(line):
                raise ReplyFormatError("a second <review> tag was opened before the first was closed; write exactly one block")
            body.append(line)
            continue
        if _OPEN.match(line):
            raise ReplyFormatError("the reply contains more than one <review> block; write exactly one")
    if state == "before":
        raise ReplyFormatError("no <review> block was found; put the whole review between <review> and </review>, each tag on its own line")
    if state == "inside":
        raise ReplyFormatError("the <review> block is never closed; end it with </review> on its own line")

    summary = ""
    findings: list[Finding] = []
    in_fix: list[bool] = []         # for each finding: has its 'Fix:' started? Lines that wrap after it belong to the FIX, not the problem
    group = 1                       # how many findings the last line made (one finding about several items makes several); a wrapped line goes to all
    for raw in unfenced_lines("\n".join(body)):
        if not raw.strip():
            continue
        summary_match = _SUMMARY.match(raw)
        if summary_match and not findings and not summary:
            summary = summary_match.group("text").strip()
            continue
        finding = _FINDING.match(raw)
        if finding is None:
            if findings and raw.startswith((" ", "\t")):
                for at in range(len(findings) - group, len(findings)):      # a wrapped continuation of the finding(s) above
                    last = findings[at]
                    if in_fix[at]:
                        findings[at] = Finding(last.severity, last.target, last.problem, (last.fix + "\n" + raw.strip())[:MAX_FIX_CHARS].strip(), last.source)
                    else:
                        findings[at] = _rebuild(last, (last.problem + " " + raw.strip()))
                        in_fix[at] = bool(_FIX.search(raw))
                continue
            if summary and not findings and raw.startswith((" ", "\t")):
                summary += " " + raw.strip()  # a wrapped summary; only an INDENTED line may continue it
                continue
            raise ReplyFormatError(
                f"this line is not a finding or the summary: {raw.strip()[:80]!r}. Write 'Summary: ...' first, then one "
                "'- [HIGH|MEDIUM|LOW] <item ID or section>: <problem>. Fix: <fix>' line per finding"
            )
        severity = finding.group("severity").lower()
        if severity not in SEVERITIES:
            raise ReplyFormatError(f"severity [{finding.group('severity')}] is not one of HIGH, MEDIUM, LOW")
        target, rest = _split_target(finding.group("rest"))
        problem, fix = _split_fix(rest)
        targets = _each_target(target)     # one finding about several items is kept as one finding per item, so each item shows its own mark
        for each in targets:
            findings.append(Finding(severity, each, problem, fix))
            in_fix.append(bool(_FIX.search(rest)))
        group = len(targets)
    if not summary:
        raise ReplyFormatError("the review has no 'Summary:' line; start with 'Summary:' and one or two sentences")
    for item in findings:
        if not item.problem:
            raise ReplyFormatError(f"the [{item.severity.upper()}] finding about {item.target} says nothing about what is wrong")
    return ParsedReview(summary[:MAX_TEXT_CHARS], tuple(findings))


def _rebuild(finding: Finding, text: str) -> Finding:
    problem, fix = _split_fix(text) if _FIX.search(text) else (text, finding.fix)
    return Finding(finding.severity, finding.target, problem.strip()[:MAX_TEXT_CHARS], fix or finding.fix, finding.source)


def _split_target(rest: str) -> tuple[str, str]:
    rest = rest.strip()
    as_file = _FILE_TARGET.match(rest)
    if as_file:
        return as_file.group("target"), as_file.group("rest").strip()
    as_id = _TARGET_ID.match(rest)
    if as_id:
        return as_id.group("target"), as_id.group("rest").strip()
    head, sep, tail = rest.partition(":")
    name = head.strip().strip("*_`'\"")
    # A section heading is short and is not a sentence. "the text is odd. Fix" is a sentence that ran into "Fix:".
    if sep and name and len(name.split()) <= MAX_TARGET_WORDS and not re.search(r"[.!?]\s|[.!?]$|\bfix$", name, re.IGNORECASE):
        return name, tail.strip()
    return GENERAL, rest


_ID_ONLY = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3,}")
_TARGET_LIST = re.compile(r"\s*(?:,|;|&|\band\b)\s*", re.IGNORECASE)


def _each_target(target: str) -> list[str]:
    """"LFS-001 and LFS-003" or "LFS-001, LFS-003" is two item IDs: return both. Anything else (an ID, a heading, even a heading with a
    comma in it) is returned as it came. Split only when EVERY part is an item ID, so a section name is never cut up."""
    parts = [p for p in _TARGET_LIST.split(target.strip()) if p]
    if len(parts) > 1 and len(parts) <= MAX_TARGET_IDS and all(_ID_ONLY.fullmatch(p) for p in parts):
        return list(dict.fromkeys(parts))
    return [target]


def _split_fix(text: str) -> tuple[str, str]:
    match = _FIX.search(text)
    if match is None:
        return text.strip()[:MAX_TEXT_CHARS], ""
    return text[: match.start()].strip()[:MAX_TEXT_CHARS], text[match.end():].strip()[:MAX_FIX_CHARS]


def verdict_of(findings: Iterable[Finding]) -> str:
    """`revise` when any finding is high, otherwise `ok`. Decided here, never by the model."""
    return "revise" if any(f.severity == "high" for f in findings) else "ok"


def validate_review(
    parsed: ParsedReview, *, item_ids: Iterable[str], sections: Iterable[str], max_findings: int, finish_reason: str | None
) -> list[str]:
    """Problems with a parsed review as plain sentences for the model. [] means usable."""
    problems: list[str] = []
    if finish_reason in TRUNCATED_REASONS:
        problems.append("the reply was cut off by the output limit; write fewer, shorter findings")
    if len(parsed.findings) > max_findings:
        problems.append(f"the review has {len(parsed.findings)} findings; the limit is {max_findings}. Keep the most important")
    ids = set(item_ids)
    names = {normalise_heading(s) for s in sections}
    for finding in parsed.findings:
        if finding.target == GENERAL or finding.target in ids or normalise_heading(finding.target) in names:
            continue
        problems.append(
            f"a finding is about '{finding.target}', which is not an item ID or a section of this artefact; "
            f"name an item ID that exists, a section heading that exists, or {GENERAL}"
        )
    return problems[:MAX_PROBLEMS]


def merge_targets(findings: Sequence[Finding]) -> list[dict[str, str]]:
    return [f.as_dict() for f in findings]
