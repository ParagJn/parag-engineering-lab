"""Skills: the Markdown files that brief an agent for one artefact, and the linter that keeps them honest.

A skill names a catalogue artefact. Its role and ID prefix come from the catalogue, not the skill, so the
two cannot drift apart. A skill may only depend on artefacts generated BEFORE it, which is checked here,
so a skill that waits for something built later is an error at load time and not a mystery at run time.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..workflow.definitions import ArtefactDef, Catalogue

SKILLS_DIR = Path(__file__).resolve().parent.parent / "phases" / "skills"

HEADINGS = ("Role", "Inputs", "Output", "Method", "Quality bar", "Never")
MAX_SKILL_BYTES = 20_000
MAX_SEARCHES = 5
MAX_SEARCH_CHARS = 200
MAX_REQUIRED_SECTIONS = 20
MAX_ITEM_SPECS = 4
WITHDRAWN_SECTION = "Withdrawn items"  # optional in every artefact that has items; never listed as required
COVERAGE_SECTION = "Coverage check"
# Prefixes the citation reader already gives a meaning to. An item prefix must not borrow one.
RESERVED_ITEM_PREFIXES = frozenset({"DOC", "MEM"})

_KEY = re.compile(r"[a-z][a-z0-9_]*")
_TITLE = re.compile(r"^# Skill:[ \t]*(.+?)[ \t]*$")
_HEADING = re.compile(r"^## (.+?)[ \t]*$")
_INPUT = re.compile(r"^-[ \t]+(artefact|search):[ \t]*(.+?)[ \t]*$")
_BULLET = re.compile(r"^-[ \t]+(.+?)[ \t]*$")
_ARTEFACT_LINE = re.compile(r"^Artefact:[ \t]*(\S+)[ \t]*$")
_ITEMS_LINE = re.compile(r"^Items:[ \t]*(\S+)[ \t]+in[ \t]+(.+?)[ \t]*$")
_COVERS_LINE = re.compile(r"^Covers:[ \t]*(.+?)[ \t]*$")
_ITEM_PREFIX = re.compile(r"[A-Z][A-Z0-9]*")


class SkillError(ValueError):
    """A skill file is wrong. The message names the file and, where it can, the line."""


@dataclass(frozen=True)
class ItemSpec:
    """Numbered items an artefact holds: every list line under `section` starts with an ID like `prefix-001`."""
    prefix: str
    section: str


@dataclass(frozen=True)
class Skill:
    key: str  # the catalogue artefact this briefs an agent for
    title: str
    role_text: str
    method: str
    quality_bar: str
    never: str
    required_sections: tuple[str, ...]
    upstream: tuple[str, ...]  # artefact keys whose latest text is included in full
    searches: tuple[str, ...]  # queries run against the context store
    artefact: ArtefactDef  # from the catalogue: role, id_prefix, phase
    items: tuple[ItemSpec, ...] = ()  # numbered items this artefact holds (empty: free text only)
    covers: tuple[str, ...] = ()  # upstream item prefixes that every item here must, between them, account for


def _split_sections(text: str, file: str) -> tuple[str, dict[str, tuple[int, str]]]:
    """(title, {heading: (line number, body)}). Rejects unknown, duplicate and out-of-order headings."""
    title = ""
    sections: dict[str, tuple[int, str]] = {}
    order: list[str] = []
    current: str | None = None
    body: list[str] = []
    start = 0

    def close() -> None:
        if current is not None:
            sections[current] = (start, "\n".join(body).strip())

    for number, line in enumerate(text.splitlines(), start=1):
        if number == 1 or (not title and line.strip()):
            match = _TITLE.match(line)
            if match is None:
                raise SkillError(f"{file}: line {number}: the file must start with '# Skill: <name>'")
            title = match.group(1)
            continue
        heading = _HEADING.match(line)
        if heading is not None:
            close()
            name = heading.group(1)
            if name not in HEADINGS:
                raise SkillError(f"{file}: line {number}: unknown heading '## {name}'; allowed are {list(HEADINGS)}")
            if name in sections or name == current:
                raise SkillError(f"{file}: line {number}: heading '## {name}' appears twice")
            order.append(name)
            current, body, start = name, [], number
            continue
        if line.startswith("# "):
            raise SkillError(f"{file}: line {number}: only one '# ' title is allowed; use '## ' for sections")
        if current is not None:
            body.append(line)
    close()
    if not title:
        raise SkillError(f"{file}: the file is empty")
    if order != [h for h in HEADINGS if h in order]:
        raise SkillError(f"{file}: headings must appear in this order: {', '.join(HEADINGS)}")
    missing = [h for h in HEADINGS if h not in sections]
    if missing:
        raise SkillError(f"{file}: missing heading(s) {missing}")
    for name, (line_no, content) in sections.items():
        if not content:
            raise SkillError(f"{file}: line {line_no}: section '## {name}' is empty")
    return title, sections


def _parse_inputs(body: str, file: str, line_no: int) -> tuple[list[str], list[str]]:
    upstream: list[str] = []
    searches: list[str] = []
    for offset, raw in enumerate(body.splitlines(), start=1):
        if not raw.strip():
            continue
        where = f"{file}: line {line_no + offset}"
        match = _INPUT.match(raw)
        if match is None:
            raise SkillError(f"{where}: an input must be '- artefact: <key>' or '- search: <words>', got {raw.strip()!r}")
        kind, value = match.groups()
        if kind == "artefact":
            if not _KEY.fullmatch(value):
                raise SkillError(f"{where}: {value!r} is not an artefact key")
            if value in upstream:
                raise SkillError(f"{where}: artefact input '{value}' is listed twice")
            upstream.append(value)
        else:
            if len(value) > MAX_SEARCH_CHARS:
                raise SkillError(f"{where}: a search is limited to {MAX_SEARCH_CHARS} characters")
            searches.append(value)
    if len(searches) > MAX_SEARCHES:
        raise SkillError(f"{file}: at most {MAX_SEARCHES} 'search:' inputs are allowed, found {len(searches)}")
    return upstream, searches


def _parse_output(body: str, file: str, line_no: int) -> tuple[str, list[str], list[tuple[str, str]], list[str]]:
    """(artefact key, required sections, [(item prefix, section)], covered prefixes).

    The block is `Artefact:`, then any `Items: PREFIX in Section` lines and one `Covers: PREFIX ...` line,
    then `Required sections:` and its list.
    """
    lines = [l for l in body.splitlines() if l.strip()]
    first = _ARTEFACT_LINE.match(lines[0]) if lines else None
    if first is None:
        raise SkillError(f"{file}: line {line_no + 1}: '## Output' must start with 'Artefact: <catalogue key>'")
    rest = lines[1:]
    item_specs: list[tuple[str, str]] = []
    covers: list[str] = []
    while rest and not rest[0].strip().rstrip(":").lower() == "required sections":
        raw = rest[0].strip()
        items_match, covers_match = _ITEMS_LINE.match(raw), _COVERS_LINE.match(raw)
        if items_match:
            prefix, section = items_match.group(1), items_match.group(2)
            if not _ITEM_PREFIX.fullmatch(prefix):
                raise SkillError(f"{file}: 'Items:' prefix {prefix!r} must be capital letters and digits, like FR")
            if prefix in RESERVED_ITEM_PREFIXES:
                raise SkillError(f"{file}: 'Items:' prefix {prefix!r} is reserved for source citations")
            if any(p == prefix for p, _ in item_specs):
                raise SkillError(f"{file}: 'Items:' prefix {prefix!r} is listed twice")
            item_specs.append((prefix, section))
        elif covers_match:
            if covers:
                raise SkillError(f"{file}: only one 'Covers:' line is allowed")
            covers = covers_match.group(1).split()
            bad = [c for c in covers if not _ITEM_PREFIX.fullmatch(c)]
            if bad:
                raise SkillError(f"{file}: 'Covers:' names {bad}, which are not item prefixes like FR")
            if len(set(covers)) != len(covers):
                raise SkillError(f"{file}: 'Covers:' lists a prefix twice")
        else:
            raise SkillError(
                f"{file}: line {line_no + 2}: after 'Artefact:' comes a 'Required sections:' list, optionally "
                f"preceded by 'Items: <PREFIX> in <Section>' and 'Covers: <PREFIX> ...' lines; got {raw!r}"
            )
        rest = rest[1:]
    if len(item_specs) > MAX_ITEM_SPECS:
        raise SkillError(f"{file}: at most {MAX_ITEM_SPECS} 'Items:' lines are allowed")
    if not rest:
        raise SkillError(f"{file}: line {line_no + 2}: after 'Artefact:' comes a 'Required sections:' list")
    sections: list[str] = []
    for raw in rest[1:]:
        match = _BULLET.match(raw)
        if match is None:
            raise SkillError(f"{file}: a required section must be a '- ' list item, got {raw.strip()!r}")
        sections.append(match.group(1).strip())
    if not sections:
        raise SkillError(f"{file}: '## Output' must list at least one required section")
    if len(sections) > MAX_REQUIRED_SECTIONS:
        raise SkillError(f"{file}: at most {MAX_REQUIRED_SECTIONS} required sections are allowed")
    normalised = [normalise_heading(s) for s in sections]
    if len(set(normalised)) != len(normalised):
        raise SkillError(f"{file}: the required sections contain a duplicate")
    if not all(normalised):
        raise SkillError(f"{file}: a required section name has no letters or digits")
    return first.group(1), sections, item_specs, covers


def normalise_heading(text: str) -> str:
    """Compare headings without caring about case, punctuation or spacing."""
    return " ".join(re.sub(r"[^\w]+", " ", text.lower()).split())


def upstream_keys(catalogue: Catalogue, artefact: ArtefactDef) -> set[str]:
    """Every artefact generated before this one: earlier phases, plus this phase's `after` closure."""
    allowed: set[str] = set()
    for phase in catalogue.phases:
        if phase.order < catalogue.phase(artefact.phase_key).order:
            allowed.update(a.key for a in phase.artefacts)
    phase = catalogue.phase(artefact.phase_key)
    pending = list(artefact.after)
    while pending:
        key = pending.pop()
        if key not in allowed:
            allowed.add(key)
            pending.extend(phase.artefact(key).after)
    return allowed


def parse_skill(text: str, file: str, catalogue: Catalogue) -> Skill:
    if len(text.encode("utf-8")) > MAX_SKILL_BYTES:
        raise SkillError(f"{file}: a skill is limited to {MAX_SKILL_BYTES} bytes")
    title, sections = _split_sections(text, file)
    upstream, searches = _parse_inputs(sections["Inputs"][1], file, sections["Inputs"][0])
    key, required, item_specs, covers = _parse_output(sections["Output"][1], file, sections["Output"][0])

    expected = Path(file).stem
    if key != expected:
        raise SkillError(f"{file}: it says 'Artefact: {key}' but the file is named {expected!r}; they must match")
    artefact = _find_artefact(catalogue, key, file)

    allowed = upstream_keys(catalogue, artefact)
    for dependency in upstream:
        if not _find_exists(catalogue, dependency):
            raise SkillError(f"{file}: input 'artefact: {dependency}' is not in the catalogue")
        if dependency == key:
            raise SkillError(f"{file}: a skill cannot use its own artefact as an input")
        if dependency not in allowed:
            raise SkillError(
                f"{file}: input 'artefact: {dependency}' is not generated before '{key}' "
                "(it is in a later phase, or in this phase but not listed in 'after')"
            )
    items = _check_items(item_specs, covers, required, artefact, catalogue, file)
    return Skill(
        key=key, title=title, role_text=sections["Role"][1], method=sections["Method"][1],
        quality_bar=sections["Quality bar"][1], never=sections["Never"][1],
        required_sections=tuple(required), upstream=tuple(upstream), searches=tuple(searches), artefact=artefact,
        items=items, covers=tuple(covers),
    )


def _check_items(
    specs: list[tuple[str, str]], covers: list[str], required: list[str], artefact: ArtefactDef, catalogue: Catalogue, file: str
) -> tuple[ItemSpec, ...]:
    """An item prefix must not equal any artefact's ID prefix, and its section must be one the skill requires."""
    artefact_prefixes = {a.id_prefix for p in catalogue.phases for a in p.artefacts}
    first_segments = {p.split("-")[0] for p in artefact_prefixes}
    required_names = {normalise_heading(r) for r in required}
    for prefix, section in specs:
        if prefix in artefact_prefixes or prefix in first_segments:
            raise SkillError(f"{file}: 'Items:' prefix {prefix!r} is also (the start of) an artefact ID prefix; item and artefact IDs must never be confusable")
        if normalise_heading(section) not in required_names:
            raise SkillError(f"{file}: 'Items: {prefix} in {section}' names a section that is not in 'Required sections'")
    if covers and not specs:
        raise SkillError(f"{file}: 'Covers:' needs at least one 'Items:' line, because there is nothing to do the covering")
    return tuple(ItemSpec(prefix, section) for prefix, section in specs)


def _find_exists(catalogue: Catalogue, key: str) -> bool:
    return any(a.key == key for p in catalogue.phases for a in p.artefacts)


def _find_artefact(catalogue: Catalogue, key: str, file: str) -> ArtefactDef:
    for phase in catalogue.phases:
        for item in phase.artefacts:
            if item.key == key:
                return item
    raise SkillError(f"{file}: 'Artefact: {key}' is not a key in the workflow catalogue")


def _check_item_namespace(skills: dict[str, Skill]) -> None:
    """Item IDs are unique across the whole project only if no two skills share a prefix, and a skill can only
    cover items that one of its own inputs actually holds."""
    owner: dict[str, str] = {}
    for key, skill in sorted(skills.items()):
        for spec in skill.items:
            if spec.prefix in owner:
                raise SkillError(
                    f"{key}.md: item prefix {spec.prefix!r} is already used by '{owner[spec.prefix]}'; "
                    "two artefacts must never number items with the same prefix"
                )
            owner[spec.prefix] = key
    for key, skill in sorted(skills.items()):
        for prefix in skill.covers:
            holders = [i for i in skill.upstream if i in skills and any(spec.prefix == prefix for spec in skills[i].items)]
            if not holders:
                raise SkillError(
                    f"{key}.md: 'Covers: {prefix}' but none of its input artefacts holds {prefix} items, "
                    "so there would be nothing to cover"
                )


class SkillLibrary:
    """Every skill in a folder, parsed once. Missing skills are normal: not all 33 exist yet."""

    def __init__(self, skills: dict[str, Skill]):
        self._skills = skills

    @classmethod
    def load(cls, catalogue: Catalogue, folder: str | Path | None = None) -> "SkillLibrary":
        base = Path(folder) if folder is not None else SKILLS_DIR
        if not base.is_dir():
            raise SkillError(f"skills folder {base.name!r} does not exist")
        skills: dict[str, Skill] = {}
        for path in sorted(base.glob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise SkillError(f"{path.name}: cannot be read ({type(exc).__name__})") from None
            skill = parse_skill(text, path.name, catalogue)
            skills[skill.key] = skill
        _check_item_namespace(skills)
        return cls(skills)

    def get(self, key: str) -> Skill | None:
        return self._skills.get(key)

    def has(self, key: str) -> bool:
        return key in self._skills

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(self._skills)

    def __len__(self) -> int:
        return len(self._skills)
