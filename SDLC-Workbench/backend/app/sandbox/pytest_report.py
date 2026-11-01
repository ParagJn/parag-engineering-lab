"""Run the generated tests and turn the real output into facts (S16).

The numbers come from running pytest inside the sandbox and reading what it printed. Nothing here asks a model, and a model's claim that tests pass is not
an input. pytest's final line ("2 failed, 1 passed, 1 skipped ... in 0.02s") is the source of the counts; the per-test lines (`PASSED file::test`,
`FAILED file::test - message`) give the names, and the failure sections give the first lines of each message.

Distinct results, never merged: a run that executed and had failures, a run that found NO tests, a run where collection itself failed, a run that timed out
or was cut for output, and a sandbox that was not available. "0 failed" is only ever said about a run that really ran tests.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

from .runner import Limits, Result, Sandbox
from .workspace import Workspace

OUTCOMES = ("passed", "failed", "errors", "skipped", "xfailed", "xpassed")
MAX_FAILURES = 50
MESSAGE_LINES = 6
MESSAGE_CHARS = 600
SECTION_LINES = 80

# pytest's last line, with or without the `===` rule around it: "2 failed, 1 passed, 1 skipped, 1 xfailed, 1 xpassed, 1 error in 0.02s (0:00:00)"
_SUMMARY = re.compile(r"^=*\s*((?:\d+ (?:passed|failed|errors?|skipped|xfailed|xpassed|warnings?|deselected|rerun)(?:, )?)+) in [0-9.]+s(?: \([0-9:]+\))?\s*=*$")
_NO_TESTS = re.compile(r"^=*\s*no tests ran in [0-9.]+s\s*=*$")
_COUNT = re.compile(r"(\d+) (passed|failed|errors?|skipped|xfailed|xpassed|warnings?|deselected|rerun)")
_LINE = re.compile(r"^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)(?: \[\d+\])? (\S.*?)(?: - (.*))?$")
_SECTION = re.compile(r"^_{3,} (?:ERROR at (?:setup|teardown) of |ERROR collecting )?(\S.*?) _{3,}$")
_E_LINE = re.compile(r"^E\s+(\S.*)$")


@dataclass(frozen=True)
class Failure:
    kind: str                         # failed | error
    test: str                         # file::name
    message: str                      # the one-line reason pytest printed
    detail: str                       # the first lines of its section, cut


@dataclass(frozen=True)
class RunReport:
    status: str                       # ran | no_tests | collection_error | timed_out | cut_off | unavailable | refused | crashed
    exit_code: int | None = None
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    xfailed: int = 0
    xpassed: int = 0
    seconds: float = 0.0
    failures: tuple[Failure, ...] = ()
    passed_names: tuple[str, ...] = ()
    reason: str = ""
    redacted: bool = False

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.errors + self.skipped + self.xfailed + self.xpassed

    @property
    def all_passed(self) -> bool:
        """True only for a run that executed at least one test and had no failure or error. A run that found nothing is NOT a pass."""
        return self.status == "ran" and self.exit_code == 0 and self.passed > 0 and self.failed == 0 and self.errors == 0


def parse(output: str, exit_code: int | None) -> RunReport:
    """Read pytest's output. Pure: text and an exit code in, a report out."""
    lines = output.splitlines()
    counts = {name: 0 for name in OUTCOMES}
    seconds = 0.0
    summary_seen = False
    for line in reversed(lines):
        text = line.strip()
        if _NO_TESTS.match(text):
            return RunReport("no_tests", exit_code, reason="pytest ran but collected no tests: there is nothing to pass or fail", seconds=_seconds(text))
        match = _SUMMARY.match(text)
        if match:
            for number, word in _COUNT.findall(match.group(1)):
                key = {"error": "errors", "errors": "errors"}.get(word, word)
                if key in counts:
                    counts[key] = int(number)
            seconds = _seconds(text)
            summary_seen = True
            break
    if not summary_seen:
        return RunReport("crashed", exit_code, reason="pytest did not print a summary, so the results cannot be read" + _tail(lines))
    sections = _sections(lines)
    failures: list[Failure] = []
    passed: list[str] = []
    for line in lines:
        match = _LINE.match(line.strip())
        if not match:
            continue
        word, test, message = match.group(1), match.group(2), (match.group(3) or "").strip()
        if word == "PASSED":
            passed.append(test)
        elif word in ("FAILED", "ERROR") and len(failures) < MAX_FAILURES:
            section = sections.get(_leaf(test), [])
            if not message:                                   # a collection error prints "ERROR file.py" with no reason; the reason is in its section
                message = _reason(section)
            failures.append(Failure("failed" if word == "FAILED" else "error", test, message[:300], _detail(section)))
    collected_nothing = counts["errors"] > 0 and counts["passed"] == 0 and counts["failed"] == 0 and any("collecting" in l.lower() or "ERROR collecting" in l for l in lines)
    status = "collection_error" if (exit_code == 2 or collected_nothing) else "ran"
    reason = "pytest could not collect the tests (an import or syntax error in a test file)" if status == "collection_error" else ""
    return RunReport(status, exit_code, counts["passed"], counts["failed"], counts["errors"], counts["skipped"], counts["xfailed"], counts["xpassed"], seconds,
                      tuple(failures), tuple(passed[:200]), reason)


def _seconds(text: str) -> float:
    found = re.search(r" in ([0-9.]+)s", text)
    return float(found.group(1)) if found else 0.0


def _leaf(test: str) -> str:
    return test.split("::")[-1].split("[")[0] if "::" in test else test


def _sections(lines: list[str]) -> dict[str, list[str]]:
    """Each failure section's lines, keyed by the test's own name, up to a cap per section."""
    out: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines:
        header = _SECTION.match(line.strip())
        if header:
            current = header.group(1).split("[")[0].strip()
            out.setdefault(current, [])
            continue
        if line.startswith("="):
            current = None
            continue
        if current is not None and line.strip() and len(out[current]) < SECTION_LINES:
            out[current].append(line.rstrip())
    return out


def _detail(section: list[str]) -> str:
    """The first few lines of a section, cut."""
    return "\n".join(section[:MESSAGE_LINES])[:MESSAGE_CHARS]


_ERROR_TYPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*(?:Error|Exception|Exit|Interrupt|Warning)\b")


def _reason(section: list[str]) -> str:
    """The reason pytest gives for a failure that has no one-line message: the exception line among the `E` lines (the last one that names an error type),
    else the first `E` line."""
    e_lines = [m.group(1) for m in (_E_LINE.match(l.strip()) for l in section) if m]
    typed = [l for l in e_lines if _ERROR_TYPE.match(l)]
    return (typed[-1] if typed else (e_lines[0] if e_lines else ""))[:300]


def _tail(lines: list[str]) -> str:
    last = [l.strip() for l in lines if l.strip()][-2:]
    return f" (it ended with: {' | '.join(last)[:200]})" if last else ""


def run_tests(sandbox: Sandbox, workspace: Workspace, target: str | None = None, limits: Limits | None = None, extra: Sequence[str] = ()) -> RunReport:
    """Run pytest in the workspace, under the sandbox, and read the real result."""
    args = ["-p", "no:cacheprovider", "-rA", "--color=no", "-q", *extra]
    if target:
        workspace.resolve(target, must_exist=True)            # the same path rules as any file tool
        args.append(target)
    result = sandbox.run(workspace, "pytest", args, limits or Limits(seconds=120))
    return report_from(result)


def report_from(result: Result) -> RunReport:
    if result.status == "refused":
        return RunReport("refused", reason=result.reason)
    if result.status == "unavailable":
        return RunReport("unavailable", reason=result.reason)
    if result.status == "timed_out":
        return RunReport("timed_out", None, reason=result.reason, seconds=result.seconds, redacted=result.redacted)
    if result.limit == "output_bytes":
        return RunReport("cut_off", result.exit_code, reason=result.reason, seconds=result.seconds, redacted=result.redacted)
    report = parse(result.output, result.exit_code)
    return RunReport(**{**report.__dict__, "redacted": result.redacted, "seconds": report.seconds or result.seconds})
