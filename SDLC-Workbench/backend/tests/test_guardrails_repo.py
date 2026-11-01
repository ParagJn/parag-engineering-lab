"""The scanner run over this project itself: no source, doc or config file may contain a secret-shaped string.

Why this test exists: the repository is public, hosting services refuse a push that contains a token, and the guardrail tests
need secret-shaped data to prove detection. So every fixture is built from fragments at run time (see tests/_fakes.py). If one
is ever written out whole by mistake, this test fails and names the file and line, and never prints the value.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.guardrails.scan import SECRET, Scanner

from . import _fakes as F

ROOT = Path(__file__).resolve().parents[2]            # the SDLC-Workbench folder
SKIP_DIRS = {".git", "node_modules", "dist", "__pycache__", ".pytest_cache", ".venv", "recordings", "data"}
SKIP_NAMES = {".env"}
TEXT_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".txt", ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".sh", ".example", ""}


def project_files():
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.name in SKIP_NAMES or any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        if path.suffix in TEXT_SUFFIXES or path.name.endswith(".env.example"):
            yield path


def test_the_scan_really_covers_the_project_and_never_looks_at_a_real_env_file():
    files = list(project_files())
    names = {p.name for p in files}
    assert len(files) > 100 and "scan.py" in names and "_fakes.py" in names and "CLAUDE.md" in names      # precondition: it found the project
    assert ".env" not in names and not any("recordings" in p.parts for p in files)
    assert any(p.name == ".env.example" for p in files)                                                         # the example file IS covered


def test_no_source_doc_or_config_file_contains_a_secret_shaped_string():
    scanner = Scanner()          # every rule that needs no configuration; a configured credential cannot be known here
    problems = []
    for path in project_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for finding in scanner.scan(text):
            if finding.klass == SECRET:
                problems.append(f"{path.relative_to(ROOT)}:{finding.line} ({finding.rule})")
    assert not problems, "secret-shaped text was written out in full; build it from fragments instead:\n  " + "\n  ".join(problems)


def test_the_self_scan_would_catch_a_fixture_written_out_whole(tmp_path):
    """The self-scan is only worth anything if it fails when it should: write a real-looking value to a file and scan that."""
    (tmp_path / "leaky.py").write_text(f'KEY = "{F.AWS_KEY}"\n', encoding="utf-8")
    found = [f for f in Scanner().scan((tmp_path / "leaky.py").read_text()) if f.klass == SECRET]
    assert [f.rule for f in found] == ["aws_key_id"]


def test_the_env_example_holds_only_placeholders():
    text = (ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
    assert [f for f in Scanner().scan(text) if f.klass == SECRET] == []
    assert "IBM_ICA_API_KEY" in text
