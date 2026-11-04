"""Show the Build artefacts becoming files and being checked, offline and free: scripted replies, no model.

    cd backend && /Users/paragjain/dev-works/myenv/bin/python -m scripts.build_demo

Each of the four Build artefacts is written into a temporary project workspace from a scripted body, then given its one real check. After the good
run, a few bodies a model might really write are tried: a file outside its folder, a missing file, a secret, a schema that fails, a page that loads
something from another website. Everything happens in a temporary folder that is deleted afterwards: your real workspaces and database are not touched.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from app.agents.skills import SkillLibrary
from app.build.service import BuildRefused, BuildService
from app.config import Settings
from app.guardrails.scan import Scanner
from app.llm.routing import Routing
from app.repos import Store
from app.sandbox.runner import Sandbox
from app.sandbox.service import SandboxService
from app.build import legacy

WHO = "agent:developer@demo"
SCHEMA = "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, text TEXT NOT NULL);\nINSERT OR IGNORE INTO notes (id, text) VALUES (1, 'first');\n"
INIT = ("import os, sqlite3\nhere = os.path.dirname(os.path.abspath(__file__))\nc = sqlite3.connect(os.path.join(here, 'app.db'))\n"
        "c.executescript(open(os.path.join(here, 'schema.sql')).read())\nc.commit()\nprint(c.execute(\"select count(*) from sqlite_master where type='table'\").fetchone()[0])\n")
MAIN = ("from fastapi import FastAPI\napp = FastAPI()\n\n@app.get('/notes')\ndef notes():\n    return [{'id': 1, 'text': 'first'}]\n")
PAGE = '<!doctype html><html><head><link rel="stylesheet" href="style.css"></head><body><ul id="n"></ul><script src="app.js"></script></body></html>'
APP_JS = "fetch('/notes').then(r => r.json()).then(rows => { for (const r of rows) { const li = document.createElement('li'); li.textContent = r.text; document.getElementById('n').appendChild(li); } });"
TEST = ("import os, tempfile\nos.environ['APP_DB_PATH'] = os.path.join(tempfile.mkdtemp(), 'app.db')\nfrom fastapi.testclient import TestClient\nfrom backend.main import app\n\n"
        "def test_notes():\n    assert TestClient(app).get('/notes').status_code == 200\n")


def body(prefix: str, entries: list[tuple[str, str, str]]) -> str:
    lines = ["## Overview", "Scripted.", "", "## Files"]
    lines += [f"- {prefix}-{n:03d} {path}: {what}. Derives from: TBL-001" for n, (path, what, _) in enumerate(entries, start=1)]
    lines += ["", "## Code"]
    for path, _, text in entries:
        lines += [f"File: {path}", "```", text.rstrip("\n"), "```", ""]
    lines += ["## Coverage check", "None", "", "## Open questions", "None"]
    return "\n".join(lines)


def line(label: str, what: str) -> str:
    return f"  {label:<46} {what}"


def demo(workdir: Path) -> list[str]:
    settings = Settings(_env_file=None, data_dir=str(workdir / "data"), recordings_dir=str(workdir / "rec"))
    store = Store.open(workdir / "demo.db", limits=settings.context_limits)
    project = store.projects.create(name="Build demo", brief="", actor="system")
    service = SandboxService(settings, store, Scanner.from_settings(settings), Sandbox())
    build = BuildService(service)
    library = legacy.library()
    out = ["BUILD DEMO (scripted replies, no model; a temporary folder that is deleted afterwards)", ""]
    problem = service.sandbox.availability()
    out.append(line("operating-system protection", "ready" if not problem else f"NOT AVAILABLE: {problem}"))
    if problem:
        return out + ["", "Nothing can be written or run without it, which is the point."]

    def write(key: str, prefix: str, entries: list[tuple[str, str, str]]) -> str:
        try:
            result = build.write_artefact(project.id, library.get(key), body(prefix, entries), actor=WHO)
        except BuildRefused as exc:
            return f"refused: {str(exc)[:96]}"
        return f"wrote {len(result.files)} file(s) under {result.folder}/" + (" (replaced the old ones)" if result.replaced else "")

    def check(key: str, **kw) -> str:
        result = build.check_artefact(project.id, key, actor=WHO, **kw)
        return f"{result.status.upper()}: {result.summary[:90]}"

    out += ["", "The four artefacts, written and checked"]
    steps = [
        ("database_schema", "DBF", [("db/schema.sql", "the tables", SCHEMA), ("db/init_db.py", "builds the file", INIT)], {"design_tables": ("notes",)}),
        ("backend_code", "BEF", [("backend/main.py", "the API", MAIN)], {}),
        ("frontend_code", "FEF", [("frontend/index.html", "the page", PAGE), ("frontend/app.js", "its script", APP_JS), ("frontend/style.css", "its look", "body { margin: 2em }")], {}),
        ("test_suite", "TSF", [("tests/test_notes.py", "checks /notes", TEST)], {}),
    ]
    for key, prefix, entries, extra in steps:
        out.append(line(f"write {key}", write(key, prefix, entries)))
        out.append(line(f"check {key}", check(key, **extra)))

    out += ["", "Things a model might really write"]
    out.append(line("backend file written into frontend/", write("backend_code", "BEF", [("backend/main.py", "the API", MAIN), ("frontend/evil.js", "oops", "x")])))
    out.append(line("main.py missing", write("backend_code", "BEF", [("backend/util.py", "helper", "x = 1")])))
    out.append(line("a file with a fake secret", write("backend_code", "BEF", [("backend/main.py", "the API", "KEY = '" + "AKIA" + "IOSFODNN7EXAMPLE" + "'")])))
    out.append(line("the old backend is still whole", ", ".join(service.list_files(project.id, "backend"))))
    write("database_schema", "DBF", [("db/schema.sql", "the tables", "CREATE TABEL notes (id);"), ("db/init_db.py", "builds the file", INIT)])
    out.append(line("a schema with a typo", check("database_schema")))
    write("database_schema", "DBF", [("db/schema.sql", "the tables", SCHEMA), ("db/init_db.py", "builds the file", INIT)])
    out.append(line("a table the design names but the schema lacks", check("database_schema", design_tables=("notes", "users"))))
    write("backend_code", "BEF", [("backend/main.py", "the API", "def f(:\n    pass\n")])
    out.append(line("backend code with a syntax error", check("backend_code")))
    write("frontend_code", "FEF", [("frontend/index.html", "the page", '<html><script src="https://cdn.example.com/x.js"></script></html>')])
    out.append(line("a page that loads from another website", check("frontend_code")))
    write("test_suite", "TSF", [("tests/test_x.py", "broken", "import nosuchmodule\ndef test_x(): pass\n")])
    out.append(line("a test file that cannot be imported", check("test_suite")))

    rows = [a for a in store.audit.list(project.id) if a.action.startswith("build.")]
    out += ["", f"The audit trail has {len(rows)} build rows for this, none holding file contents or output."]
    return out


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sdlc_build_demo_") as folder:
        print("\n".join(demo(Path(folder))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
