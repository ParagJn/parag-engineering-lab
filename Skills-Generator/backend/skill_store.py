"""
File-based skill storage.

Each skill is a folder skills/<skill_dir>/ (SKILL.md plus optional reference/,
scripts/, templates/, evals/), with its metadata in skills/.metadata.json keyed
by skill id. Anthropic and Gemini skills are mirrored into .claude/skills/ and
.gemini/skills/; Anthropic skills can also be installed to ~/.claude/skills/.
"""

import io
import json
import shutil
import stat
import threading
import uuid
import zipfile
from datetime import datetime
from pathlib import Path

import skill_spec as spec
from bundle import parse_skill_name, set_skill_name, strip_fence
from config import config
from validator import validate_bundle

_lock = threading.Lock()

_INSTALL_MARKER = ".skills-generator"  # marks personal installs this app owns
_SKIP_NAMES = {".DS_Store", _INSTALL_MARKER}


class SkillNotFound(KeyError):
    pass


class InstallConflict(RuntimeError):
    """Target folder in ~/.claude/skills exists and wasn't installed by this skill."""

    def __init__(self, path: Path):
        super().__init__(str(path))
        self.path = path


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def load_meta() -> dict:
    if config.METADATA_FILE.exists():
        return json.loads(config.METADATA_FILE.read_text())
    return {}


def save_meta(meta: dict) -> None:
    # Write to a temp file and swap so a crash never leaves half-written JSON
    tmp = config.METADATA_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(meta, indent=2))
    tmp.replace(config.METADATA_FILE)


def get_meta(meta: dict, skill_id: str) -> dict:
    if skill_id not in meta:
        raise SkillNotFound(skill_id)
    return meta[skill_id]


# Re-exported for callers that only need the fence stripper
clean_model_output = strip_fence


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def skill_root(m: dict) -> Path:
    if m.get("archived") and m.get("archive_dir"):
        return config.ARCHIVE_DIR / m["archive_dir"]
    return config.SKILLS_DIR / m["skill_dir"]


def read_bundle(m: dict) -> dict[str, str]:
    """{relative_path: content} for every text file in the skill folder, SKILL.md first."""
    root = skill_root(m)
    if not root.is_dir():
        return {}
    files = {}
    for fp in sorted(root.rglob("*")):
        if not fp.is_file() or fp.name in _SKIP_NAMES:
            continue
        rel = fp.relative_to(root).as_posix()
        try:
            files[rel] = fp.read_text()
        except UnicodeDecodeError:
            continue  # binary asset — not shown in the editor
    return dict(sorted(files.items(), key=lambda kv: (kv[0] != spec.SKILL_FILE, kv[0])))


def read_content(m: dict) -> str:
    fp = skill_root(m) / spec.SKILL_FILE
    return fp.read_text() if fp.exists() else ""


def _platform_dir(platform: str) -> Path | None:
    return config.PLATFORM_SKILL_DIRS.get(platform)


def _is_shared(meta: dict, skill_id: str, skill_dir: str, platform: str | None = None) -> bool:
    """True if another live skill uses the same directory (optionally same platform)."""
    return any(
        sid != skill_id
        and not other.get("archived")
        and other.get("skill_dir") == skill_dir
        and (platform is None or other.get("platform") == platform)
        for sid, other in meta.items()
    )


def _unique_dir_name(meta: dict, base: str, platform: str) -> str:
    """Pick a directory name no other skill (or unrelated folder) is using."""
    platform_dir = _platform_dir(platform)
    taken = {m.get("skill_dir") for m in meta.values() if not m.get("archived")}
    candidate, n = base, 2
    while (
        candidate in taken
        or (config.SKILLS_DIR / candidate).exists()
        or (platform_dir is not None and (platform_dir / candidate).exists())
    ):
        suffix = f"-{n}"
        candidate = base[: spec.MAX_NAME_LEN - len(suffix)] + suffix
        n += 1
    return candidate


def _remove_files(meta: dict, skill_id: str) -> None:
    """Remove a live skill's files, leaving anything another skill still uses."""
    m = meta[skill_id]
    skill_dir = m["skill_dir"]
    if not skill_dir:
        return
    if not _is_shared(meta, skill_id, skill_dir):
        shutil.rmtree(config.SKILLS_DIR / skill_dir, ignore_errors=True)
    platform_dir = _platform_dir(m["platform"])
    if platform_dir is not None and not _is_shared(meta, skill_id, skill_dir, m["platform"]):
        shutil.rmtree(platform_dir / skill_dir, ignore_errors=True)


def _write_tree(target: Path, files: dict[str, str]) -> None:
    """Replace target with exactly `files`; scripts are made executable."""
    shutil.rmtree(target, ignore_errors=True)
    for rel, content in files.items():
        fp = target / rel
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content)
        if spec.script_language(rel):
            fp.chmod(fp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _sync(m: dict, files: dict[str, str]) -> None:
    """Write the skill folder, its platform mirror, and the personal install (if any)."""
    _write_tree(config.SKILLS_DIR / m["skill_dir"], files)
    platform_dir = _platform_dir(m["platform"])
    if platform_dir is not None:
        _write_tree(platform_dir / m["skill_dir"], files)
    if m.get("installed_path"):
        _install_to(Path(m["installed_path"]), files, m["id"])


def to_response(m: dict, files: dict[str, str] | None = None) -> dict:
    files = read_bundle(m) if files is None else files
    return {
        **m,
        "content": files.get(spec.SKILL_FILE, ""),
        "files": [{"path": p, "content": c, "size": len(c.encode())} for p, c in files.items()],
        "usage_notes": m.get("usage_notes", ""),
        "format_version": m.get("format_version", 1),
        "validation": m.get("validation"),
        "installed_path": m.get("installed_path"),
    }


def _summary(m: dict) -> dict:
    """Lightweight list-view entry (no file contents)."""
    return {k: m.get(k) for k in (
        "id", "name", "skill_dir", "platform", "created_at", "updated_at", "installed_path",
    )} | {"format_version": m.get("format_version", 1),
          "valid": (m.get("validation") or {}).get("ok")}


# ---------------------------------------------------------------------------
# Operations
# ---------------------------------------------------------------------------

def list_skills() -> list[dict]:
    meta = load_meta()
    out = [_summary(m) for m in meta.values() if not m.get("archived")]
    return sorted(out, key=lambda x: x.get("created_at") or "", reverse=True)


def get_skill(skill_id: str) -> dict:
    return to_response(get_meta(load_meta(), skill_id))


def get_bundle(skill_id: str) -> tuple[dict, dict[str, str]]:
    m = get_meta(load_meta(), skill_id)
    return m, read_bundle(m)


def save_skill(
    files: dict[str, str],
    platform: str,
    thought: str,
    usage_notes: str = "",
    skill_id: str | None = None,
    options: dict | None = None,
    format_version: int = spec.FORMAT_VERSION,
) -> dict:
    """
    Create a skill, or replace an existing one (same id) with a new bundle.
    Old files are only removed once the new bundle is ready to be written.
    """
    files = dict(files)
    with _lock:
        meta = load_meta()
        previous = meta.get(skill_id) if skill_id else None
        if previous:
            _remove_files(meta, skill_id)
            meta[skill_id] = {**previous, "skill_dir": None}  # free its dir name

        skill_id = skill_id or uuid.uuid4().hex[:8]
        skill_dir = _unique_dir_name(meta, parse_skill_name(files.get(spec.SKILL_FILE, "")), platform)
        files[spec.SKILL_FILE] = set_skill_name(files.get(spec.SKILL_FILE, ""), skill_dir)

        now = datetime.now().isoformat()
        m = {
            **(previous or {}),
            "id": skill_id,
            "name": skill_dir,
            "skill_dir": skill_dir,
            "platform": platform,
            "thought": thought,
            "created_at": previous["created_at"] if previous else now,
            "updated_at": now,
            "archived": False,
            "usage_notes": usage_notes,
            "format_version": format_version,
            "options": options if options is not None else (previous or {}).get("options", {}),
            "validation": validate_bundle(files, platform),
        }
        m.pop("evals_last_run", None)  # results belong to the previous version
        if previous and previous.get("installed_path"):
            _move_install(m, previous, files)
        meta[skill_id] = m
        _sync(m, files)
        save_meta(meta)
        return to_response(m, files)


def update_file(skill_id: str, path: str, content: str) -> dict:
    """Save one user-edited file; if SKILL.md's name changed, the folder is renamed."""
    if not spec.is_safe_path(path):
        raise ValueError(f"Path not allowed: {path}")
    m, files = get_bundle(skill_id)
    if m.get("archived"):
        raise ValueError("Archived skills are read-only")
    files[path] = content if content.endswith("\n") else content + "\n"
    renamed = path == spec.SKILL_FILE and parse_skill_name(content) != m["skill_dir"]
    return _resave(skill_id, files, relocate=renamed)


def delete_file(skill_id: str, path: str) -> dict:
    if path == spec.SKILL_FILE:
        raise ValueError("SKILL.md can't be deleted")
    m, files = get_bundle(skill_id)
    if path not in files:
        raise SkillNotFound(path)
    del files[path]
    return _resave(skill_id, files)


def _resave(skill_id: str, files: dict[str, str], relocate: bool = False) -> dict:
    """Rewrite files in place (same folder name) and refresh validation."""
    m = get_meta(load_meta(), skill_id)
    if relocate or _is_shared(load_meta(), skill_id, m["skill_dir"]):
        # Renamed, or an older skill sharing its folder: give it its own folder
        return save_skill(files, m["platform"], m["thought"], m.get("usage_notes", ""),
                          skill_id, m.get("options"), m.get("format_version", 1))
    with _lock:
        meta = load_meta()
        m = get_meta(meta, skill_id)
        m["validation"] = validate_bundle(files, m["platform"])
        m["updated_at"] = datetime.now().isoformat()
        m.pop("evals_last_run", None)
        _sync(m, files)
        save_meta(meta)
        return to_response(m, files)


def revalidate(skill_id: str) -> dict:
    with _lock:
        meta = load_meta()
        m = get_meta(meta, skill_id)
        files = read_bundle(m)
        m["validation"] = validate_bundle(files, m["platform"])
        save_meta(meta)
        return to_response(m, files)


def set_usage_notes(skill_id: str, usage_notes: str) -> None:
    with _lock:
        meta = load_meta()
        get_meta(meta, skill_id)["usage_notes"] = usage_notes
        save_meta(meta)


def set_eval_results(skill_id: str, results: dict) -> None:
    with _lock:
        meta = load_meta()
        get_meta(meta, skill_id)["evals_last_run"] = results
        save_meta(meta)


def delete_skill(skill_id: str) -> None:
    with _lock:
        meta = load_meta()
        m = get_meta(meta, skill_id)
        _uninstall(m)
        if m.get("archived"):
            if m.get("archive_dir"):
                shutil.rmtree(config.ARCHIVE_DIR / m["archive_dir"], ignore_errors=True)
        else:
            _remove_files(meta, skill_id)
        del meta[skill_id]
        save_meta(meta)


def archive_skill(skill_id: str) -> None:
    with _lock:
        meta = load_meta()
        m = get_meta(meta, skill_id)
        if m.get("archived"):
            return
        _uninstall(m)
        archive_dir = f"{m['skill_dir']}-{skill_id}"
        src = config.SKILLS_DIR / m["skill_dir"]
        dst = config.ARCHIVE_DIR / archive_dir
        if src.is_dir():
            shutil.rmtree(dst, ignore_errors=True)
            # Copy (not move) if another live skill still uses this directory
            if _is_shared(meta, skill_id, m["skill_dir"]):
                shutil.copytree(src, dst)
            else:
                shutil.move(str(src), str(dst))
        platform_dir = _platform_dir(m["platform"])
        if platform_dir is not None and not _is_shared(meta, skill_id, m["skill_dir"], m["platform"]):
            shutil.rmtree(platform_dir / m["skill_dir"], ignore_errors=True)
        m["archived"] = True
        m["archive_dir"] = archive_dir
        save_meta(meta)


# ---------------------------------------------------------------------------
# Personal install (~/.claude/skills)
# ---------------------------------------------------------------------------

def _owned_by(path: Path, skill_id: str) -> bool:
    marker = path / _INSTALL_MARKER
    return marker.exists() and marker.read_text().strip() == skill_id


def _install_to(target: Path, files: dict[str, str], skill_id: str) -> None:
    _write_tree(target, files)
    (target / _INSTALL_MARKER).write_text(skill_id + "\n")


def _uninstall(m: dict) -> None:
    """Remove the personal copy — only if this app installed it for this skill."""
    path = m.get("installed_path")
    if path and _owned_by(Path(path), m["id"]):
        shutil.rmtree(path, ignore_errors=True)
    m.pop("installed_path", None)


def _move_install(m: dict, previous: dict, files: dict[str, str]) -> None:
    """Regenerate/rename: follow the new folder name if it's free, else stay put."""
    old = Path(previous["installed_path"])
    new = config.PERSONAL_SKILLS_DIR / m["skill_dir"]
    if new == old or (new.exists() and not _owned_by(new, m["id"])):
        m["installed_path"] = str(old)
        return
    if _owned_by(old, m["id"]):
        shutil.rmtree(old, ignore_errors=True)
    m["installed_path"] = str(new)


def install_personal(skill_id: str, overwrite: bool = False) -> dict:
    with _lock:
        meta = load_meta()
        m = get_meta(meta, skill_id)
        if m.get("archived"):
            raise ValueError("Archived skills can't be installed")
        if m["platform"] != "anthropic":
            raise ValueError("Only Claude (Anthropic) skills can be installed to ~/.claude/skills")
        target = config.PERSONAL_SKILLS_DIR / m["skill_dir"]
        if target.exists() and not _owned_by(target, skill_id) and not overwrite:
            raise InstallConflict(target)
        files = read_bundle(m)
        if m.get("installed_path") and Path(m["installed_path"]) != target:
            _uninstall(m)
        _install_to(target, files, skill_id)
        m["installed_path"] = str(target)
        save_meta(meta)
        return to_response(m, files)


def uninstall_personal(skill_id: str) -> dict:
    with _lock:
        meta = load_meta()
        m = get_meta(meta, skill_id)
        _uninstall(m)
        save_meta(meta)
        return to_response(m)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def zip_bundle(skill_id: str) -> tuple[str, bytes]:
    m, files = get_bundle(skill_id)
    if not files:
        raise SkillNotFound(skill_id)
    name = m["skill_dir"] or m.get("name") or skill_id
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel, content in files.items():
            info = zipfile.ZipInfo(f"{name}/{rel}", date_time=datetime.now().timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            mode = 0o755 if spec.script_language(rel) else 0o644
            info.external_attr = (stat.S_IFREG | mode) << 16
            zf.writestr(info, content)
    return name, buf.getvalue()
