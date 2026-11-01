"""The one thing the Build agents call (S16): a project's workspace, its file tools and its command runner, with every action audited.

Each file written or deleted and each command run adds ONE audit row: who, what, how it ended. A row never holds file contents or a command's output
(those can be large and can hold things that should not be in a log), and a refused action is recorded as refused. File contents are checked for secrets
before they are written, and a command's output is redacted before it is returned.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Sequence

from ..guardrails.scan import Scanner
from .errors import SandboxError
from .pytest_report import RunReport, run_tests
from .runner import Limits, Result, Sandbox
from .workspace import Limits as FileLimits
from .workspace import Workspace

_PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class SandboxService:
    def __init__(self, settings, store, scanner: Scanner | None = None, sandbox: Sandbox | None = None):
        self.settings = settings
        self.store = store
        self.scanner = scanner if scanner is not None else Scanner.from_settings(settings)
        self.sandbox = sandbox or Sandbox(scanner=self.scanner)
        self.sandbox.scanner = self.sandbox.scanner or self.scanner
        self._file_limits = FileLimits.from_settings(settings)

    # ---- the workspace ---------------------------------------------------------------------------------------------------------

    def workspace(self, project_id: str) -> Workspace:
        """The project's workspace, made on first use. Only a project that exists gets one."""
        if not isinstance(project_id, str) or not _PROJECT_ID.match(project_id):
            from .errors import PathRefused
            raise PathRefused("a project id may hold only letters, digits, dashes and underscores")
        self.store.projects.get(project_id)                          # NotFoundError for an unknown project: no folder is made for it
        return Workspace.for_project(self.settings.workspaces_path, project_id, self._file_limits, self.scanner)

    def _audit(self, project_id: str, actor: str, action: str, target: str, detail: dict[str, Any]) -> None:
        self.store.audit.append(actor=actor, action=action, target_type="sandbox", target_id=target[:200], project_id=project_id, detail=detail)

    # ---- the file tools ---------------------------------------------------------------------------------------------------------

    def write_file(self, project_id: str, path: str, text: str, *, actor: str) -> str:
        ws = self.workspace(project_id)
        try:
            shown = ws.write_file(path, text)
        except SandboxError as exc:
            self._audit(project_id, actor, "sandbox.file_refused", _safe(path), {"op": "write", "reason": str(exc)[:200]})
            raise
        self._audit(project_id, actor, "sandbox.file_written", shown, {"bytes": len(text.encode("utf-8"))})
        return shown

    def read_file(self, project_id: str, path: str) -> str:
        return self.workspace(project_id).read_file(path)

    def list_files(self, project_id: str, path: str | None = None) -> list[str]:
        return self.workspace(project_id).list_files(path)

    def delete_file(self, project_id: str, path: str, *, actor: str) -> None:
        ws = self.workspace(project_id)
        try:
            ws.delete_file(path)
        except SandboxError as exc:
            self._audit(project_id, actor, "sandbox.file_refused", _safe(path), {"op": "delete", "reason": str(exc)[:200]})
            raise
        self._audit(project_id, actor, "sandbox.file_deleted", _safe(path), {})

    def make_dir(self, project_id: str, path: str, *, actor: str) -> str:
        ws = self.workspace(project_id)
        try:
            shown = ws.make_dir(path)
        except SandboxError as exc:
            self._audit(project_id, actor, "sandbox.file_refused", _safe(path), {"op": "make_dir", "reason": str(exc)[:200]})
            raise
        return shown

    # ---- commands --------------------------------------------------------------------------------------------------------------

    def run_command(self, project_id: str, program: str, args: Sequence[str] = (), *, actor: str) -> Result:
        ws = self.workspace(project_id)
        result = self.sandbox.run(ws, program, args, Limits.from_settings(self.settings))
        self._audit_command(project_id, actor, program, args, result)
        return result

    def run_tests(self, project_id: str, target: str | None = None, *, actor: str) -> RunReport:
        ws = self.workspace(project_id)
        report = run_tests(self.sandbox, ws, target, Limits.from_settings(self.settings, tests=True))
        self.store.audit.append(
            actor=actor, action="sandbox.tests_run", target_type="sandbox", target_id=(target or "all")[:200], project_id=project_id,
            detail={"status": report.status, "passed": report.passed, "failed": report.failed, "errors": report.errors, "skipped": report.skipped, "exit_code": report.exit_code},
        )
        return report

    def _audit_command(self, project_id: str, actor: str, program: str, args: Sequence[str], result: Result) -> None:
        shown = " ".join([str(program), *[str(a) for a in args]])[:200]
        detail: dict[str, Any] = {"status": result.status, "exit_code": result.exit_code, "seconds": result.seconds}
        if result.status in ("refused", "unavailable", "timed_out"):
            detail["reason"] = result.reason[:200]
        if result.limit:
            detail["limit"] = result.limit
        self._audit(project_id, actor, "sandbox.command_refused" if result.status == "refused" else "sandbox.command_run", shown, detail)


def _safe(path: Any) -> str:
    """A path as it goes into a log: text, short, no control characters."""
    text = str(path)[:200]
    return "".join(c if 32 <= ord(c) < 127 else "?" for c in text) or "(empty)"
