"""
Skill bundle helpers: parse the model's multi-file output and edit frontmatter.

The model writes every file between delimiters instead of JSON, so scripts
need no escaping:

    <<<FILE: scripts/validate.py>>>
    ...content...
    <<<END FILE>>>
"""

import re

import yaml

from skill_spec import MAX_NAME_LEN, SKILL_FILE, is_safe_path

_FILE_BLOCK_RE = re.compile(
    r"^<<<FILE:\s*(?P<path>[^>\n]+?)\s*>>>[ \t]*\n(?P<body>.*?)^<<<END FILE>>>[ \t]*$",
    re.DOTALL | re.MULTILINE,
)
_FENCE_RE = re.compile(r"^```[a-zA-Z0-9_+-]*[ \t]*\n(.*)\n```\s*$", re.DOTALL)


class BundleError(ValueError):
    pass


def strip_fence(text: str) -> str:
    """Strip a surrounding ``` code fence if the model added one."""
    text = (text or "").strip()
    match = _FENCE_RE.match(text)
    return (match.group(1).strip() if match else text) + "\n"


def parse_bundle(text: str) -> tuple[dict[str, str], list[str]]:
    """
    Parse delimited model output into {path: content}.

    Returns (files, rejected_paths). With no delimiters at all, the whole
    output is treated as SKILL.md (single-file skills / older outputs).
    """
    files: dict[str, str] = {}
    rejected: list[str] = []
    for match in _FILE_BLOCK_RE.finditer(text or ""):
        path = match.group("path").strip().strip("`'\"")
        path = path[2:] if path.startswith("./") else path
        if not is_safe_path(path):
            rejected.append(path)
            continue
        body = match.group("body")
        # Only markdown gets fence-stripping; a script body is taken verbatim
        files[path] = strip_fence(body) if path.endswith(".md") else body.rstrip() + "\n"

    if not files and not rejected:
        files[SKILL_FILE] = strip_fence(text)
    return files, rejected


def serialize_bundle(files: dict[str, str]) -> str:
    """Inverse of parse_bundle — used when sending a bundle back for repair."""
    ordered = sorted(files, key=lambda p: (p != SKILL_FILE, p))
    return "\n".join(f"<<<FILE: {p}>>>\n{files[p].rstrip()}\n<<<END FILE>>>\n" for p in ordered)


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------

def frontmatter_bounds(content: str) -> tuple[int, int] | None:
    """(start, end) character offsets of the YAML body between the --- lines."""
    if not content.startswith("---"):
        return None
    end = content.find("\n---", 3)
    return (3, end) if end != -1 else None


def split_frontmatter(content: str) -> tuple[dict | None, str, str | None]:
    """
    Returns (frontmatter_dict, body, error). frontmatter is None if missing or
    unparseable; error explains why.
    """
    bounds = frontmatter_bounds(content)
    if not bounds:
        return None, content, "SKILL.md must start with a '---' YAML frontmatter block on line 1"
    start, end = bounds
    body = content[end + 4:].lstrip("\n")
    try:
        data = yaml.safe_load(content[start:end]) or {}
    except yaml.YAMLError as e:
        return None, body, f"Frontmatter is not valid YAML: {e}"
    if not isinstance(data, dict):
        return None, body, "Frontmatter must be a YAML mapping of key: value pairs"
    return data, body, None


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", str(name).lower()).strip("-")
    return slug[:MAX_NAME_LEN].strip("-") or "untitled-skill"


def parse_skill_name(content: str) -> str:
    data, _, _ = split_frontmatter(content)
    if data and data.get("name"):
        return slugify(data["name"])
    # Fallback for malformed YAML: find a name: line anywhere up top
    for line in content.splitlines()[:30]:
        stripped = line.strip()
        if stripped.startswith("name:"):
            return slugify(stripped.split(":", 1)[1].strip().strip("'\""))
    return "untitled-skill"


def set_skill_name(content: str, name: str) -> str:
    """Make the frontmatter `name:` match the directory name (text edit, keeps formatting)."""
    bounds = frontmatter_bounds(content)
    if not bounds:
        return content
    start, end = bounds
    region = content[start:end]
    if re.search(r"(?m)^name:", region):
        region = re.sub(r"(?m)^name:.*$", f"name: {name}", region, count=1)
    else:
        region = f"\nname: {name}" + region
    return content[:start] + region + content[end:]


def strip_fields(content: str, allowed: set[str]) -> tuple[str, list[str]]:
    """
    Drop top-level frontmatter keys that the target platform doesn't support.
    Returns (content, removed_keys). Only rewrites when something is removed.
    """
    data, body, error = split_frontmatter(content)
    if error or data is None:
        return content, []
    removed = [k for k in data if k not in allowed]
    if not removed:
        return content, []
    kept = {k: v for k, v in data.items() if k in allowed}
    dumped = yaml.safe_dump(kept, sort_keys=False, allow_unicode=True, width=1000).strip()
    return f"---\n{dumped}\n---\n\n{body}", removed
