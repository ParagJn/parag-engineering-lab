"""The catalogue of phases and artefacts, loaded from YAML and checked hard.

A mistake in a definition file is an error that names the file and the artefact. Nothing is silently
ignored, because a quietly dropped artefact would mean a demo that skips a step without telling anyone.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml

DEFINITIONS_DIR = Path(__file__).resolve().parent.parent / "phases" / "definitions"

KEY_RE = re.compile(r"[a-z][a-z0-9_]*")
PREFIX_RE = re.compile(r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+")  # needs at least one dash, like REQ-F

PHASE_FIELDS = {"key", "order", "name", "summary", "approver", "artefacts"}
ARTEFACT_FIELDS = {"key", "name", "id_prefix", "role", "required", "description", "after"}


class CatalogueError(ValueError):
    """A definition file is wrong. The message names the file and, where it can, the artefact."""


@dataclass(frozen=True)
class ArtefactDef:
    key: str
    name: str
    id_prefix: str
    role: str
    required: bool
    description: str
    after: tuple[str, ...]
    phase_key: str


@dataclass(frozen=True)
class PhaseDef:
    key: str
    order: int
    name: str
    summary: str
    approver: str
    artefacts: tuple[ArtefactDef, ...]

    def artefact(self, key: str) -> ArtefactDef:
        for item in self.artefacts:
            if item.key == key:
                return item
        raise KeyError(key)


@dataclass(frozen=True)
class Catalogue:
    phases: tuple[PhaseDef, ...]  # in lifecycle order

    @property
    def phase_keys(self) -> tuple[str, ...]:
        return tuple(p.key for p in self.phases)

    def phase(self, key: str) -> PhaseDef:
        for item in self.phases:
            if item.key == key:
                return item
        raise KeyError(key)

    def has_phase(self, key: str) -> bool:
        return any(p.key == key for p in self.phases)

    @property
    def artefact_count(self) -> int:
        return sum(len(p.artefacts) for p in self.phases)

    @property
    def required_count(self) -> int:
        return sum(1 for p in self.phases for a in p.artefacts if a.required)


# ---- loading ----------------------------------------------------------------

def _text(data: Mapping[str, Any], name: str, where: str, *, required: bool = True) -> str:
    value = data.get(name)
    if value is None:
        if required:
            raise CatalogueError(f"{where}: missing '{name}'")
        return ""
    if not isinstance(value, str) or not value.strip():
        raise CatalogueError(f"{where}: '{name}' must be non-blank text")
    return value.strip()


def _reject_unknown(data: Mapping[str, Any], allowed: set[str], where: str) -> None:
    unknown = sorted(str(k) for k in data if k not in allowed)
    if unknown:
        raise CatalogueError(f"{where}: unknown field(s) {unknown}; allowed are {sorted(allowed)}")


class _UniqueKeyLoader(yaml.SafeLoader):
    """A YAML loader that refuses a repeated key instead of quietly keeping the last one."""


def _construct_mapping(loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False):
    seen: set[Any] = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"the key {key!r} appears twice", key_node.start_mark
            )
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


_UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def _parse_artefact(raw: Any, phase_key: str, file: str, index: int) -> ArtefactDef:
    where = f"{file}: artefact #{index + 1}"
    if not isinstance(raw, dict):
        raise CatalogueError(f"{where} must be a mapping")
    key = raw.get("key")
    if isinstance(key, str):
        where = f"{file}: artefact '{key}'"
    _reject_unknown(raw, ARTEFACT_FIELDS, where)
    key = _text(raw, "key", where)
    if not KEY_RE.fullmatch(key):
        raise CatalogueError(f"{where}: key must be lower_snake_case")
    prefix = _text(raw, "id_prefix", where)
    if not PREFIX_RE.fullmatch(prefix):
        raise CatalogueError(f"{where}: id_prefix {prefix!r} must look like 'REQ-F' (capitals, with a dash)")
    required = raw.get("required", False)
    if not isinstance(required, bool):
        raise CatalogueError(f"{where}: 'required' must be true or false")
    after = raw.get("after", [])
    if after is None:
        after = []
    if not isinstance(after, list) or not all(isinstance(a, str) for a in after):
        raise CatalogueError(f"{where}: 'after' must be a list of artefact keys")
    if len(set(after)) != len(after):
        raise CatalogueError(f"{where}: 'after' lists the same artefact twice")
    return ArtefactDef(
        key=key,
        name=_text(raw, "name", where),
        id_prefix=prefix,
        role=_text(raw, "role", where),
        required=required,
        description=_text(raw, "description", where, required=False),
        after=tuple(after),
        phase_key=phase_key,
    )


def _find_cycle(artefacts: Iterable[ArtefactDef]) -> list[str] | None:
    graph = {a.key: a.after for a in artefacts}
    done: set[str] = set()

    def visit(node: str, path: list[str]) -> list[str] | None:
        if node in path:
            return path[path.index(node):] + [node]
        if node in done:
            return None
        for nxt in graph[node]:
            found = visit(nxt, [*path, node])
            if found:
                return found
        done.add(node)
        return None

    for start in graph:
        found = visit(start, [])
        if found:
            return found
    return None


def parse_phase(data: Any, file: str, valid_roles: Iterable[str]) -> PhaseDef:
    if not isinstance(data, dict):
        raise CatalogueError(f"{file}: expected a mapping with phase fields")
    _reject_unknown(data, PHASE_FIELDS, file)
    key = _text(data, "key", file)
    if not KEY_RE.fullmatch(key):
        raise CatalogueError(f"{file}: key must be lower_snake_case")
    order = data.get("order")
    if isinstance(order, bool) or not isinstance(order, int) or order < 0:
        raise CatalogueError(f"{file}: 'order' must be a whole number, 0 or more")

    raw_artefacts = data.get("artefacts")
    if not isinstance(raw_artefacts, list) or not raw_artefacts:
        raise CatalogueError(f"{file}: a phase needs at least one artefact")
    artefacts = tuple(_parse_artefact(raw, key, file, i) for i, raw in enumerate(raw_artefacts))

    roles = set(valid_roles)
    seen: set[str] = set()
    for item in artefacts:
        if item.key in seen:
            raise CatalogueError(f"{file}: artefact '{item.key}' appears twice")
        seen.add(item.key)
        if item.role not in roles:
            raise CatalogueError(
                f"{file}: artefact '{item.key}' uses role '{item.role}', which is not in routing.yaml"
            )
    for item in artefacts:
        for dependency in item.after:
            if dependency == item.key:
                raise CatalogueError(f"{file}: artefact '{item.key}' cannot come after itself")
            if dependency not in seen:
                raise CatalogueError(
                    f"{file}: artefact '{item.key}' comes after '{dependency}', which is not in this phase"
                )
    cycle = _find_cycle(artefacts)
    if cycle:
        raise CatalogueError(f"{file}: the 'after' rules form a loop: {' -> '.join(cycle)}")
    if not any(a.required for a in artefacts):
        raise CatalogueError(f"{file}: a phase needs at least one required artefact, or it could be approved empty")

    return PhaseDef(
        key=key, order=order, name=_text(data, "name", file), summary=_text(data, "summary", file, required=False),
        approver=_text(data, "approver", file), artefacts=artefacts,
    )


def build_catalogue(phases: Iterable[PhaseDef]) -> Catalogue:
    """Cross-file checks: orders, keys and ID prefixes must be unique, and prefixes must not collide."""
    ordered = tuple(sorted(phases, key=lambda p: p.order))
    if not ordered:
        raise CatalogueError("no phase definitions found")
    if [p.order for p in ordered] != list(range(len(ordered))):
        raise CatalogueError(
            f"phase orders must run 0 to {len(ordered) - 1} with no gaps or repeats, "
            f"got {[p.order for p in ordered]}"
        )
    keys = [p.key for p in ordered]
    if len(set(keys)) != len(keys):
        duplicated = sorted({k for k in keys if keys.count(k) > 1})
        raise CatalogueError(f"phase key(s) used by more than one file: {duplicated}")

    owners: dict[str, str] = {}
    for phase in ordered:
        for item in phase.artefacts:
            if item.id_prefix in owners:
                raise CatalogueError(
                    f"id_prefix {item.id_prefix!r} is used by both '{owners[item.id_prefix]}' and '{item.key}'"
                )
            owners[item.id_prefix] = item.key
    prefixes = sorted(owners)
    for short in prefixes:
        for long in prefixes:
            if long != short and long.startswith(short + "-"):
                raise CatalogueError(
                    f"id_prefix {short!r} ('{owners[short]}') is the start of {long!r} ('{owners[long]}'), "
                    "so their numbers would be counted together"
                )
    return Catalogue(ordered)


def load_catalogue(valid_roles: Iterable[str], folder: str | Path | None = None) -> Catalogue:
    base = Path(folder) if folder is not None else DEFINITIONS_DIR
    if not base.is_dir():
        raise CatalogueError(f"phase definitions folder {base.name!r} does not exist")
    roles = list(valid_roles)
    phases: list[PhaseDef] = []
    for path in sorted(base.glob("*.yaml")):
        try:
            data = yaml.load(path.read_text(encoding="utf-8"), Loader=_UniqueKeyLoader)  # noqa: S506 (safe subclass)
        except OSError as exc:
            raise CatalogueError(f"{path.name}: cannot be read ({exc.strerror})") from exc
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            line = f" near line {mark.line + 1}" if mark is not None else ""
            problem = getattr(exc, "problem", None) or "not valid YAML"
            raise CatalogueError(f"{path.name}: {problem}{line}") from None
        phases.append(parse_phase(data, path.name, roles))
    return build_catalogue(phases)
