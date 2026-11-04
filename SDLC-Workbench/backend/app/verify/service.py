"""Run a Build Verify check (S20b): read the design, walk the folders, read the code, match, store. Reading only; the person's folders are never changed or run."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any

from . import match as M
from . import report as R
from .design import read_design
from .readers import python_fastapi as PF
from .walk import FolderProblem, walk


def _backend_files(path: str):
    walked = walk(path)
    return walked, [(f.path, f.text) for f in walked.files]


def check(store: Any, skills: Any, project_id: str, *, backend_path: str, actor: str) -> tuple[Any, R.Report]:
    """Compare the build to the design and keep the result. Raises FolderProblem (a plain sentence) when a folder cannot be read."""
    design = read_design(store, skills, project_id)
    notes = list(design.notes)
    walked, files = _backend_files(backend_path)
    backend = PF.read_backend(files)
    notes += [f"backend: {s}" for s in walked.skipped[:10]]
    if walked.stopped:
        notes.append(f"backend: {walked.stopped}")
    notes += [f"backend: {p}" for p in backend.problems]
    if not backend.files_read:
        notes.append("backend: no Python or SQL file was found in the folder you named, so nothing could be compared")
    matched = M.match_all(design, backend)
    report = R.build_report(matched.matches, matched.extras, notes)
    rows = [{**asdict(m), "differences": list(m.differences)} for m in report.matches]
    rows += [{"designed": None, "area": e.area, "state": "extra", "built": e.built, "file": e.file, "line": e.line, "differences": []} for e in report.extras]
    run = store.verify.add_run(
        project_id, backend_path=backend_path, frontend_path=None, actor=actor, design=design.versions,
        counts=[asdict(c) for c in report.areas], notes=report.notes, matches=rows,
    )
    return run, report


__all__ = ["check", "FolderProblem"]
