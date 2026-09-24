"""
Deterministic checks for a skill bundle.

Scripts are syntax-checked only (python ast, `bash -n`, `node --check`) —
generated code is never executed.
"""

import ast
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import skill_spec as spec
from bundle import split_frontmatter

_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s#]+)(?:#[^)]*)?\)")
_PATH_MENTION_RE = re.compile(
    r"(?<![\w/.-])((?:%s)/[\w./-]+\.\w+)" % "|".join(spec.ALLOWED_DIRS)
)
_DYNAMIC_CONTEXT_RE = re.compile(r"!`[^`]+`|^```!", re.MULTILINE)
_TRIGGER_RE = re.compile(r"\b(use|used|invoke|trigger)\w*\b.*\b(when|for|if|whenever)\b|\bwhen\b", re.I)
_SYNTAX_TIMEOUT = 10


def _mentioned_paths(text: str) -> set[str]:
    found = set()
    for target in _MD_LINK_RE.findall(text):
        if "://" in target or target.startswith("mailto:"):
            continue
        target = target.replace("${CLAUDE_SKILL_DIR}/", "")
        found.add(target[2:] if target.startswith("./") else target)
    for target in _PATH_MENTION_RE.findall(text):
        found.add(target.rstrip(".,;:)"))
    return found


def _check_python(source: str) -> str | None:
    try:
        ast.parse(source)
    except SyntaxError as e:
        return f"line {e.lineno}: {e.msg}"
    return None


def _check_with_tool(cmd: list[str], source: str, suffix: str) -> str | None:
    """Run a syntax-only check (`bash -n`, `node --check`) on a temp copy."""
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False) as f:
        f.write(source)
        tmp = f.name
    try:
        proc = subprocess.run(cmd + [tmp], capture_output=True, text=True, timeout=_SYNTAX_TIMEOUT)
    except subprocess.TimeoutExpired:
        return "syntax check timed out"
    finally:
        Path(tmp).unlink(missing_ok=True)
    if proc.returncode != 0:
        return (proc.stderr or proc.stdout).replace(tmp, "<script>").strip()[:500]
    return None


def _check_script(path: str, source: str, lang: str, report: dict) -> None:
    if lang == "python":
        err = _check_python(source)
    elif lang == "bash":
        err = _check_with_tool(["bash", "-n"], source, ".sh")
    else:
        if not shutil.which("node"):
            report["warnings"].append(f"{path}: node not found — JavaScript syntax not checked")
            return
        err = _check_with_tool(["node", "--check"], source, Path(path).suffix)
    if err:
        report["errors"].append(f"{path}: syntax error — {err}")
    else:
        report["passed"].append(f"{path}: {lang} syntax OK (not executed)")
    if not source.startswith("#!"):
        report["warnings"].append(f"{path}: no shebang line (e.g. #!/usr/bin/env python3)")


def _check_frontmatter(data: dict, platform: str, report: dict) -> None:
    errors, warnings, passed = report["errors"], report["warnings"], report["passed"]

    name = data.get("name")
    if not name or not isinstance(name, str):
        errors.append("Frontmatter: `name` is required")
    else:
        if len(name) > spec.MAX_NAME_LEN:
            errors.append(f"Frontmatter: `name` is longer than {spec.MAX_NAME_LEN} characters")
        if not spec.NAME_RE.match(name):
            errors.append("Frontmatter: `name` must be lowercase letters, digits and hyphens")
        if any(w in name for w in spec.RESERVED_NAME_WORDS):
            errors.append("Frontmatter: `name` must not contain 'anthropic' or 'claude'")
        if spec.NAME_RE.match(name) and len(name) <= spec.MAX_NAME_LEN:
            passed.append("Frontmatter: name is valid")

    desc = data.get("description")
    if not desc or not isinstance(desc, str) or not desc.strip():
        errors.append("Frontmatter: `description` is required")
    else:
        if len(desc) > spec.MAX_DESCRIPTION_LEN:
            errors.append(f"Frontmatter: `description` is longer than {spec.MAX_DESCRIPTION_LEN} characters")
        if spec.XML_TAG_RE.search(desc):
            errors.append("Frontmatter: `description` must not contain XML tags")
        if re.match(r"^\s*(I|I'm|You|Your|My|We)\b", desc):
            warnings.append("Description should be third person (\"Generates…\", not \"I/You…\")")
        combined = desc + " " + str(data.get("when_to_use", ""))
        if not _TRIGGER_RE.search(combined):
            warnings.append("Description should say WHEN to use the skill (e.g. \"Use when…\")")
        if len(desc) <= spec.MAX_DESCRIPTION_LEN and not spec.XML_TAG_RE.search(desc):
            passed.append("Frontmatter: description is valid")

    compat = data.get("compatibility")
    if compat is not None and len(str(compat)) > spec.MAX_COMPATIBILITY_LEN:
        errors.append(f"Frontmatter: `compatibility` is longer than {spec.MAX_COMPATIBILITY_LEN} characters")

    allowed = spec.ALLOWED_FIELDS.get(platform, spec.SPEC_FIELDS)
    for key in data:
        if key not in allowed:
            if key in spec.CLAUDE_CODE_FIELDS:
                errors.append(f"Frontmatter: `{key}` is Claude Code-only and not supported on {platform}")
            else:
                warnings.append(f"Frontmatter: unknown field `{key}`")

    tools = data.get("allowed-tools")
    if tools is not None and not (
        isinstance(tools, str) or (isinstance(tools, list) and all(isinstance(t, str) for t in tools))
    ):
        errors.append("Frontmatter: `allowed-tools` must be a string or a list of strings")

    args = data.get("arguments")
    if args is not None and not isinstance(args, (str, list)):
        errors.append("Frontmatter: `arguments` must be a string or a list")

    for flag in ("disable-model-invocation", "user-invocable"):
        if flag in data and not isinstance(data[flag], bool):
            errors.append(f"Frontmatter: `{flag}` must be true or false")


def _check_evals(files: dict[str, str], report: dict) -> None:
    raw = files.get(spec.EVALS_FILE)
    if raw is None:
        report["errors"].append(f"Missing {spec.EVALS_FILE} (need at least {spec.MIN_EVALS} eval scenarios)")
        return
    try:
        evals = json.loads(raw)
    except json.JSONDecodeError as e:
        report["errors"].append(f"{spec.EVALS_FILE}: invalid JSON — {e}")
        return
    if isinstance(evals, dict):
        evals = evals.get("evals", [])
    if not isinstance(evals, list) or len(evals) < spec.MIN_EVALS:
        report["errors"].append(f"{spec.EVALS_FILE}: must be a list of at least {spec.MIN_EVALS} scenarios")
        return
    bad = [
        i for i, e in enumerate(evals, 1)
        if not isinstance(e, dict)
        or not str(e.get("query", "")).strip()
        or not isinstance(e.get("expected_behavior"), list)
        or not e["expected_behavior"]
    ]
    if bad:
        report["errors"].append(
            f"{spec.EVALS_FILE}: scenario(s) {bad} need a `query` and a non-empty `expected_behavior` list"
        )
    else:
        report["passed"].append(f"{spec.EVALS_FILE}: {len(evals)} eval scenarios")


def load_evals(files: dict[str, str]) -> list[dict]:
    try:
        evals = json.loads(files.get(spec.EVALS_FILE, "[]"))
    except json.JSONDecodeError:
        return []
    if isinstance(evals, dict):
        evals = evals.get("evals", [])
    return [e for e in evals if isinstance(e, dict) and e.get("query")] if isinstance(evals, list) else []


def validate_bundle(files: dict[str, str], platform: str) -> dict:
    report = {"errors": [], "warnings": [], "passed": []}
    errors, warnings, passed = report["errors"], report["warnings"], report["passed"]

    skill_md = files.get(spec.SKILL_FILE)
    if skill_md is None:
        errors.append("SKILL.md is missing")
        return _finish(report)

    # --- Layout ---
    if platform not in spec.BUNDLE_PLATFORMS and len(files) > 1:
        errors.append(f"{platform} skills must be a single SKILL.md file")
    if len(files) > spec.MAX_FILES:
        errors.append(f"Bundle has {len(files)} files (max {spec.MAX_FILES})")
    for path, content in files.items():
        if not spec.is_safe_path(path):
            errors.append(f"{path}: path is not allowed (use SKILL.md, *.md, or reference/, scripts/, templates/, evals/)")
        if len(content.encode()) > spec.MAX_FILE_BYTES:
            errors.append(f"{path}: file is larger than {spec.MAX_FILE_BYTES // 1000} KB")
        if "\\" in "".join(_mentioned_paths(content)):
            warnings.append(f"{path}: use forward slashes in file paths")

    # --- SKILL.md ---
    data, body, fm_error = split_frontmatter(skill_md)
    if fm_error:
        errors.append(fm_error)
    else:
        _check_frontmatter(data, platform, report)

    lines = skill_md.count("\n") + 1
    if lines > spec.MAX_SKILL_LINES:
        errors.append(f"SKILL.md is {lines} lines — keep it under {spec.MAX_SKILL_LINES} and move detail to reference files")
    else:
        passed.append(f"SKILL.md length OK ({lines} lines)")
    if len(body.strip()) < 200:
        warnings.append("SKILL.md body is very short — add a workflow and concrete instructions")

    if _DYNAMIC_CONTEXT_RE.search(skill_md):
        warnings.append("SKILL.md runs shell commands at load time (!`…`) — review them before installing")

    # --- Cross references ---
    if platform in spec.BUNDLE_PLATFORMS:
        mentioned = _mentioned_paths(skill_md)
        missing = sorted(p for p in mentioned if p not in files and spec.is_safe_path(p))
        for p in missing:
            errors.append(f"SKILL.md links to {p}, which is not in the bundle")

        # Plain-text mentions ("see examples.md") count as references too
        mentioned |= {p for p in files if p in skill_md}
        mentioned_anywhere = set(mentioned)
        for path, content in files.items():
            if path != spec.SKILL_FILE:
                mentioned_anywhere |= _mentioned_paths(content) | {p for p in files if p in content}
        for path in files:
            if path in (spec.SKILL_FILE, spec.EVALS_FILE):
                continue
            if path not in mentioned_anywhere:
                warnings.append(f"{path} is never referenced from SKILL.md, so Claude won't find it")
            elif path not in mentioned:
                warnings.append(f"{path} is only linked from another file — keep references one level deep from SKILL.md")

        for path, content in files.items():
            if not path.endswith(".md") or path == spec.SKILL_FILE:
                continue
            if content.count("\n") > spec.REFERENCE_TOC_THRESHOLD and not re.search(
                r"(?im)^#+\s*(table of )?contents\b", content
            ):
                warnings.append(f"{path} is over {spec.REFERENCE_TOC_THRESHOLD} lines — add a table of contents at the top")

        # --- Scripts ---
        for path, content in files.items():
            lang = spec.script_language(path)
            if lang:
                _check_script(path, content, lang, report)

        _check_evals(files, report)

    return _finish(report)


def _finish(report: dict) -> dict:
    report["ok"] = not report["errors"]
    return report
