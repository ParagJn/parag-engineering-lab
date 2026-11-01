"""Numbered items inside an artefact: reading them, and checking them before anything is saved.

An artefact is one row with one ID (`REQ-F-001`). The things inside it (each requirement, each persona) get
their own IDs (`FR-012`) so that later phases can point at one of them. The model writes the IDs and this
module checks them; it never renumbers anything, because a renumbering would silently break every
reference made to the old number.

An item is one list line that starts with its ID and ends with where it comes from:

    - FR-012 The system shall refuse a booking longer than four hours. Derives from: PER-001, PRB-001 [DOC-001#1]

Reading is lenient (`parse_items` never raises: it is also used on upstream artefacts and old versions,
which this module did not check). Checking is strict (`check_items`) and returns plain sentences that are
sent back to the model.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

from .reply import section_bodies, unfenced_lines
from .skills import COVERAGE_SECTION, WITHDRAWN_SECTION, ItemSpec, normalise_heading

ID_PATTERN = r"[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d{3,}"
SNIPPET_CHARS = 60
LIST_NOUN = "numbered item"

# A top-level list line. Two or more spaces of indentation is a nested bullet (an acceptance criterion
# under a story, say) and belongs to the item above it, so it is not read as an item of its own.
_LIST_LINE = re.compile(r"^ ?(?:[-*+]|\d{1,3}[.)])[ \t]+(?P<rest>\S.*)$")
_ANY_LIST_LINE = re.compile(r"^\s*(?:[-*+]|\d{1,3}[.)])[ \t]+\S")
_LEAD_ID = re.compile(rf"^(?:\*\*|__)?(?P<id>{ID_PATTERN})(?:\*\*|__)?(?=$|[\s:.,;)–—\-])")
_DERIVES = re.compile(r"\bderives[ \t]+from[ \t]*:[ \t]*(?P<tail>.*)$", re.IGNORECASE)
_BRACKETS = re.compile(r"\[[^\[\]\n]*\]")
_ID_ANYWHERE = re.compile(rf"(?<![A-Za-z0-9-])({ID_PATTERN})(?![A-Za-z0-9-])")
# What "Derives from:" may name: an item or artefact ID, or a source written without brackets. Only the
# first kind can become a link (the links table holds item and artefact IDs), so the two are told apart.
_TARGET = re.compile(rf"(?<![A-Za-z0-9-])(DOC-\d{{3,}}#[1-9]\d*|MEM-\d{{3,}}|{ID_PATTERN}(?:@v[1-9]\d*#[1-9]\d*)?)(?![A-Za-z0-9-])")
_LINKABLE = re.compile(ID_PATTERN)
_SENTENCE_END = re.compile(r"\.(?:\s|$)")


def split_id(item_id: str) -> tuple[str, int]:
    prefix, _, number = item_id.rpartition("-")
    return prefix, int(number)


def format_id(prefix: str, number: int) -> str:
    return f"{prefix}-{number:03d}"


@dataclass(frozen=True)
class Item:
    id: str
    section: str
    text: str  # the rest of the line after the ID, as written
    derives: tuple[str, ...]  # IDs named after "Derives from:", in order, without repeats
    has_source: bool  # "Derives from:" is present and names an ID or a bracketed citation

    @property
    def prefix(self) -> str:
        return split_id(self.id)[0]

    @property
    def link_targets(self) -> tuple[str, ...]:
        """The derives-from IDs that can be saved as links: items and whole artefacts, not document chunks."""
        return tuple(t for t in self.derives if _LINKABLE.fullmatch(t) and not t.startswith(("MEM-", "DOC-")))


@dataclass(frozen=True)
class ParsedItems:
    items: tuple[Item, ...] = ()
    misplaced: tuple[tuple[str, str], ...] = ()  # (id, section) for an ID whose prefix does not belong in that section
    stray: tuple[tuple[str, str], ...] = ()  # (section, snippet) for a list entry with no ID
    withdrawn: tuple[str, ...] = ()

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(i.id for i in self.items)


def _derive_targets(tail: str) -> tuple[tuple[str, ...], bool]:
    """(IDs named, whether anything at all was named). A bracketed citation counts as naming a source."""
    tail = _SENTENCE_END.split(tail, maxsplit=1)[0]
    cited = bool(_BRACKETS.search(tail))
    stripped = _BRACKETS.sub(" ", tail)
    found: list[str] = []
    for match in _TARGET.finditer(stripped):
        if match.group(1) not in found:
            found.append(match.group(1))
    return tuple(found), bool(found) or cited


def _entries(chunk: str) -> list[str]:
    """The top-level list entries of a section, each with its wrapped continuation lines joined by a space.

    A continuation is a non-blank, non-list line straight after an entry (a model often wraps a long
    requirement onto an indented second line). A blank line, a heading or any list line, nested or not,
    ends it, so an acceptance criterion under a story never leaks into the story's own text.
    """
    entries: list[list[str]] = []
    open_entry = False
    for line in unfenced_lines(chunk):
        top = _LIST_LINE.match(line)
        if top is not None:
            entries.append([top.group("rest")])
            open_entry = True
        elif not line.strip() or line.lstrip().startswith("#") or _ANY_LIST_LINE.match(line):
            open_entry = False
        elif open_entry:
            entries[-1].append(line.strip())
    return [" ".join(parts) for parts in entries]


def parse_items(body: str, specs: Sequence[ItemSpec]) -> ParsedItems:
    """Every item the body holds under the sections the specs name. Never raises, never judges."""
    if not specs:
        return ParsedItems()
    prefixes_by_section: dict[str, list[str]] = {}
    names: dict[str, str] = {}
    for spec in specs:
        key = normalise_heading(spec.section)
        prefixes_by_section.setdefault(key, []).append(spec.prefix)
        names.setdefault(key, spec.section)

    items: list[Item] = []
    misplaced: list[tuple[str, str]] = []
    stray: list[tuple[str, str]] = []
    for key, allowed in prefixes_by_section.items():
        for chunk in section_bodies(body, names[key]):
            for rest in _entries(chunk):
                lead = _LEAD_ID.match(rest)
                if lead is None:
                    stray.append((names[key], rest[:SNIPPET_CHARS]))
                    continue
                item_id = lead.group("id")
                if split_id(item_id)[0] not in allowed:
                    misplaced.append((item_id, names[key]))
                    continue
                derived = _DERIVES.search(rest)
                targets, sourced = _derive_targets(derived.group("tail")) if derived else ((), False)
                items.append(Item(item_id, names[key], rest[lead.end():].strip(), targets, sourced))

    wanted = {spec.prefix for spec in specs}
    withdrawn: list[str] = []
    for chunk in section_bodies(body, WITHDRAWN_SECTION):
        for rest in _entries(chunk):
            lead = _LEAD_ID.match(rest)
            if lead and split_id(lead.group("id"))[0] in wanted and lead.group("id") not in withdrawn:
                withdrawn.append(lead.group("id"))
    return ParsedItems(tuple(items), tuple(misplaced), tuple(stray), tuple(withdrawn))


# ---- what an artefact's earlier versions and its upstream artefacts contribute -------------------------

@dataclass(frozen=True)
class ItemContext:
    """Everything the checks need to know that is not in the reply itself."""
    specs: tuple[ItemSpec, ...]
    covers: tuple[str, ...] = ()
    known: frozenset[str] = frozenset()  # IDs "Derives from" may name: upstream artefacts and their items
    pools: Mapping[str, tuple[str, ...]] = field(default_factory=dict)  # covered prefix -> upstream item IDs
    current: frozenset[str] = frozenset()  # item IDs in the latest earlier version
    retired: frozenset[str] = frozenset()  # IDs that appeared in some earlier version and are not current
    highest: Mapping[str, int] = field(default_factory=dict)  # prefix -> highest number ever used
    previous: tuple[Item, ...] = ()  # the items of the latest earlier version, so the model can see which ID was which

    def next_number(self, prefix: str) -> int:
        return self.highest.get(prefix, 0) + 1


@dataclass(frozen=True)
class History:
    current: frozenset[str]
    retired: frozenset[str]
    highest: Mapping[str, int]
    previous: tuple[Item, ...]


def history_of(bodies: Sequence[str], specs: Sequence[ItemSpec]) -> History:
    """What earlier versions (oldest first) say about IDs. An empty list is a first draft."""
    ever: set[str] = set()
    current: frozenset[str] = frozenset()
    previous: tuple[Item, ...] = ()
    for body in bodies:
        parsed = parse_items(body, specs)
        current, previous = frozenset(parsed.ids), parsed.items
        ever.update(parsed.ids)
        ever.update(parsed.withdrawn)
    highest: dict[str, int] = {}
    for item_id in ever:
        prefix, number = split_id(item_id)
        highest[prefix] = max(highest.get(prefix, 0), number)
    return History(current, frozenset(ever - current), highest, previous)


def upstream_pool(bodies_and_specs: Iterable[tuple[str, Sequence[ItemSpec]]]) -> dict[str, tuple[str, ...]]:
    """prefix -> every item ID of that prefix across the given upstream artefacts, in order."""
    pools: dict[str, list[str]] = {}
    for body, specs in bodies_and_specs:
        for item in parse_items(body, specs).items:
            pools.setdefault(item.prefix, [])
            if item.id not in pools[item.prefix]:
                pools[item.prefix].append(item.id)
    return {prefix: tuple(ids) for prefix, ids in pools.items()}


# ---- the strict check --------------------------------------------------------------------------------------

def _short(ids: Iterable[str], limit: int = 6) -> str:
    listed = list(ids)
    shown = ", ".join(listed[:limit])
    return shown + (f" and {len(listed) - limit} more" if len(listed) > limit else "")


def _ordered(ids: Iterable[str]) -> list[str]:
    return sorted(set(ids), key=lambda i: (split_id(i)[0], split_id(i)[1]))


def check_items(body: str, context: ItemContext) -> list[str]:
    """Every problem with the items in `body`, as sentences to send back to the model. [] means fine."""
    specs = context.specs
    parsed = parse_items(body, specs)
    problems: list[str] = []

    for item_id, section in parsed.misplaced:
        allowed = [s.prefix for s in specs if normalise_heading(s.section) == normalise_heading(section)]
        problems.append(f"{item_id} is under '{section}', where items must start with {_short(f'{p}-' for p in allowed)}")
    for section, snippet in parsed.stray:
        example = next(f"{s.prefix}-001" for s in specs if normalise_heading(s.section) == normalise_heading(section))
        problems.append(f"a list entry under '{section}' has no ID ('{snippet}'); start every item with its ID, like '- {example} ...'")

    for spec in specs:
        if not any(i.prefix == spec.prefix for i in parsed.items):
            problems.append(f"'{spec.section}' has no numbered items; write each one as '- {spec.prefix}-001 ...' with its own ID")

    seen: set[str] = set()
    for item in parsed.items:
        if item.id in seen:
            problems.append(f"{item.id} appears more than once; every item needs its own ID")
        seen.add(item.id)

    present = {i.id for i in parsed.items}
    reused = _ordered(present & context.retired)
    for item_id in reused:
        problems.append(f"{item_id} was in an earlier version and is no longer in use, so it cannot be used again; give a new item the next free number")
    for spec in specs:
        fresh = sorted(split_id(i)[1] for i in present if split_id(i)[0] == spec.prefix and i not in context.current and i not in context.retired)
        start = context.next_number(spec.prefix)
        expected = list(range(start, start + len(fresh)))
        if fresh != expected:
            found = _short(format_id(spec.prefix, n) for n in fresh)
            problems.append(
                f"new {spec.prefix} items must be numbered {format_id(spec.prefix, start)} onward without gaps; found {found}"
            )

    for item in parsed.items:
        if not item.has_source:
            problems.append(f"{item.id} has no 'Derives from:'; end the line with 'Derives from:' and the IDs it comes from, or a source in square brackets")
            continue
        for target in item.derives:
            if target == item.id:
                problems.append(f"{item.id} cannot derive from itself")
            elif target not in context.known and target not in present:
                problems.append(f"{item.id} derives from {target}, which is not in the material you were given")

    withdrawn = set(parsed.withdrawn)
    for item_id in _ordered(context.current - present - withdrawn):
        problems.append(f"{item_id} was in the previous version and is now missing; keep it, or list it under '{WITHDRAWN_SECTION}' with a reason")
    for item_id in _ordered(withdrawn & present):
        problems.append(f"{item_id} is both an item and listed under '{WITHDRAWN_SECTION}'; it can only be one")
    for item_id in _ordered(withdrawn - context.current - present - context.retired):
        problems.append(f"{item_id} is listed under '{WITHDRAWN_SECTION}' but was not in the previous version")

    if context.covers:
        problems += _coverage_problems(body, parsed, context)
    return problems


def _coverage_problems(body: str, parsed: ParsedItems, context: ItemContext) -> list[str]:
    pool = [i for prefix in context.covers for i in context.pools.get(prefix, ())]
    named = {target for item in parsed.items for target in item.derives}
    uncovered = {i for i in pool if i not in named}
    declared: set[str] = set()
    for chunk in section_bodies(body, COVERAGE_SECTION):
        for line in unfenced_lines(chunk):
            declared.update(m.group(1) for m in _ID_ANYWHERE.finditer(line))
    declared = {i for i in declared if split_id(i)[0] in context.covers}

    problems: list[str] = []
    silent = _ordered(uncovered - declared)
    if silent:
        problems.append(
            f"{_short(silent)} {'is' if len(silent) == 1 else 'are'} not named in any item's 'Derives from:', "
            f"and '{COVERAGE_SECTION}' does not list {'it' if len(silent) == 1 else 'them'}; cover "
            f"{'it' if len(silent) == 1 else 'them'}, or list {'it' if len(silent) == 1 else 'them'} under '{COVERAGE_SECTION}'"
        )
    wrong = _ordered(declared - uncovered)
    if wrong:
        problems.append(
            f"'{COVERAGE_SECTION}' lists {_short(wrong)} as not covered, but {'it is' if len(wrong) == 1 else 'they are'} "
            "covered, or not among the items you were given; list only the ones no item derives from"
        )
    return problems
