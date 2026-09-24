"""
Skill format rules (Agent Skills spec + Claude Code extensions).

Kept as plain constants so the validator, the prompts and the storage layer
all agree on the same limits.
"""

import re

# --- Frontmatter ----------------------------------------------------------

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME_LEN = 64
RESERVED_NAME_WORDS = ("anthropic", "claude")
MAX_DESCRIPTION_LEN = 1024
MAX_COMPATIBILITY_LEN = 500
XML_TAG_RE = re.compile(r"<[^>]+>")

# Portable Agent Skills spec fields (claude.ai upload, Gemini CLI, Claude Code)
SPEC_FIELDS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}

# Fields only Claude Code understands
CLAUDE_CODE_FIELDS = {
    "when_to_use",
    "argument-hint",
    "arguments",
    "disable-model-invocation",
    "user-invocable",
    "disallowed-tools",
    "model",
    "effort",
    "context",
    "agent",
    "background",
    "hooks",
    "paths",
    "shell",
}

ALLOWED_FIELDS = {
    "anthropic": SPEC_FIELDS | CLAUDE_CODE_FIELDS,
    "gemini": SPEC_FIELDS,
    "chatgpt": {"name", "description"},
}

# --- Bundle layout --------------------------------------------------------

SKILL_FILE = "SKILL.md"
EVALS_FILE = "evals/evals.json"
MAX_SKILL_LINES = 500
REFERENCE_TOC_THRESHOLD = 100
MIN_EVALS = 3

MAX_FILES = 25
MAX_FILE_BYTES = 200_000

# Top-level folders a bundle may use (plus .md files at the root)
ALLOWED_DIRS = ("reference", "references", "scripts", "templates", "assets", "examples", "evals")

TEXT_EXTENSIONS = {
    ".md", ".txt", ".json", ".yaml", ".yml", ".csv", ".html", ".css", ".xml", ".toml",
    ".py", ".sh", ".bash", ".js", ".mjs", ".cjs", ".ts", ".sql", ".j2", ".tmpl", ".tpl",
}

SCRIPT_EXTENSIONS = {
    ".py": "python",
    ".sh": "bash",
    ".bash": "bash",
    ".js": "node",
    ".mjs": "node",
    ".cjs": "node",
}

# Which platforms get a multi-file bundle (ChatGPT stays a single instructions file)
BUNDLE_PLATFORMS = {"anthropic", "gemini"}

FORMAT_VERSION = 2


def is_safe_path(path: str) -> bool:
    """Relative, forward-slash, no traversal, inside an allowed folder."""
    if not path or path.startswith("/") or "\\" in path or ":" in path:
        return False
    parts = path.split("/")
    if any(p in ("", ".", "..") or p.startswith(".") for p in parts):
        return False
    if len(parts) == 1:
        return path == SKILL_FILE or path.endswith(".md")
    if parts[0] not in ALLOWED_DIRS or len(parts) > 3:
        return False
    return any(path.endswith(ext) for ext in TEXT_EXTENSIONS)


def script_language(path: str) -> str | None:
    if not path.startswith("scripts/"):
        return None
    for ext, lang in SCRIPT_EXTENSIONS.items():
        if path.endswith(ext):
            return lang
    return None
