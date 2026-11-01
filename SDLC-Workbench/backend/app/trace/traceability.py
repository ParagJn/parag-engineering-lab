"""Traceability (S15): from the links the artefacts already declare, compute the chain from a requirement down to what was built for it, and the gaps.

A pure function: it takes plain data (the items of each artefact, the links between them, the rules from the skills) and returns plain data. It
reads no database and calls no model, so the same input always gives the same answer, and no model can claim coverage: this computes it.

The links point from the LATER thing to the EARLIER thing it derives from (a component points at the requirement it serves). So "ancestors" of
an item are what it comes from, and "descendants" are what was built on it.

What SHOULD be covered is not decided here. It comes from the skills' own `Covers:` lines (components cover FR and NFR, the flow covers IFC...),
read in both directions, so a phase that ships a skill brings its own rule and this module needs no change.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

NOT_COVERED = "not_covered"
DECLARED = "declared_uncovered"
BUILT_ON_NOTHING = "built_on_nothing"
WITHDRAWN_TARGET = "points_at_withdrawn"
MISSING_TARGET = "points_at_missing"
KINDS = (NOT_COVERED, BUILT_ON_NOTHING, WITHDRAWN_TARGET, MISSING_TARGET, DECLARED)
EXPLAINED = (DECLARED,)               # the writer admitted it, with a reason; every other kind needs attention

MAX_GAPS = 500                        # more than this and the rest are only counted
MAX_WALK = 5000                       # a walk through the graph stops here, so a corrupt graph can never hang a request


def prefix_of(item_id: str) -> str:
    """`FR-004` -> `FR`; `SET-CHR-001` -> `SET-CHR`."""
    return item_id.rsplit("-", 1)[0]


def number_of(item_id: str) -> int:
    try:
        return int(item_id.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return 0


def sort_key(item_id: str) -> tuple[str, int]:
    return (prefix_of(item_id), number_of(item_id))


@dataclass(frozen=True)
class Rule:
    """One artefact kind's duty: its items (by prefix) must between them account for every item of the `covers` prefixes."""
    artefact: str                     # the skill key, e.g. component_overview
    holds: tuple[str, ...]            # item prefixes it numbers, e.g. COMP
    covers: tuple[str, ...]           # item prefixes it must account for, e.g. FR, NFR
    phase: str                        # the phase it belongs to
    reads: tuple[str, ...] = ()       # item prefixes held by the artefacts it is given to read (what it MAY derive from, wider than what it must cover)


@dataclass(frozen=True)
class Item:
    id: str
    artefact_id: str                  # the artefact row that holds it, e.g. ARC-CMP-001
    artefact_key: str                 # its type, e.g. component_overview
    version: int
    name: str = ""                    # the short name, if it has one
    withdrawn: bool = False


@dataclass(frozen=True)
class Gap:
    kind: str
    item: str                         # the item the gap is about
    artefact_id: str                  # where it was found
    version: int
    other: str | None = None          # the item it points at (for the two "points at" kinds)
    reason: str | None = None         # the writer's own words (for a declared gap)
    sentence: str = ""
    by: str | None = None             # the artefact kind that should have accounted for it (for the two "covered" kinds)

    @property
    def group(self) -> str:
        return "explained" if self.kind in EXPLAINED else "needs_attention"


@dataclass(frozen=True)
class Chain:
    """One requirement and, by layer, what is built on it."""
    item: str
    name: str
    layers: Mapping[str, tuple[str, ...]]          # prefix -> item IDs, nearest layer first
    states: Mapping[str, str]                      # prefix -> "built" | "empty" | "not_started"


@dataclass(frozen=True)
class Trace:
    chains: tuple[Chain, ...]
    layer_order: tuple[str, ...]
    gaps: tuple[Gap, ...]
    gaps_more: int
    items: Mapping[str, Item]
    counts: Mapping[str, int]


# ---- the graph ------------------------------------------------------------------------------------------------------------------------------

def build_graph(links: Iterable[tuple[str, str]]) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """(up, down): up[x] = what x derives from, down[x] = what derives from x. Duplicates are dropped; order is stable."""
    up: dict[str, list[str]] = defaultdict(list)
    down: dict[str, list[str]] = defaultdict(list)
    for source, target in dict.fromkeys(links):
        if source == target:
            continue
        up[source].append(target)
        down[target].append(source)
    return dict(up), dict(down)


def walk(start: str, edges: Mapping[str, Sequence[str]], limit: int = MAX_WALK) -> list[str]:
    """Everything reachable from `start` along `edges`, nearest first, each once. Iterative (no recursion limit) and bounded (a loop ends).

    Items at the same distance are listed by kind and number, NOT in the order their links happened to be created: parallel artefacts are written in
    whatever order they finish, and the same project must read the same every time it is opened."""
    seen = {start}
    order: list[str] = []
    frontier = [start]
    while frontier:
        found: set[str] = set()
        for node in frontier:
            for nxt in edges.get(node, ()):
                if nxt not in seen:
                    seen.add(nxt)
                    found.add(nxt)
        following = sorted(found, key=sort_key)
        for nxt in following:
            order.append(nxt)
            if len(order) >= limit:
                return order
        frontier = following
    return order


def has_loop(links: Iterable[tuple[str, str]]) -> list[str]:
    """Items that sit on a loop in the links (there should be none: the checks refuse a loop at write time). Iterative, so it cannot overflow."""
    up, _ = build_graph(links)
    state: dict[str, int] = {}
    on_loop: set[str] = set()
    for root in list(up):
        if root in state:
            continue
        stack = [(root, iter(up.get(root, ())))]
        path = [root]
        state[root] = 1
        while stack:
            node, children = stack[-1]
            for child in children:
                if state.get(child) == 1:
                    on_loop.update(path[path.index(child):])
                elif child not in state:
                    state[child] = 1
                    path.append(child)
                    stack.append((child, iter(up.get(child, ()))))
                    break
            else:
                state[node] = 2
                path.pop()
                stack.pop()
    return sorted(on_loop, key=sort_key)


# ---- the rules ------------------------------------------------------------------------------------------------------------------------------------

def layer_order(rules: Iterable[Rule], roots: Sequence[str], phase_order: Sequence[str] = ()) -> tuple[str, ...]:
    """The kinds that may be built on the roots, in reading order: by phase, then by how many steps from the roots, then as the skills are listed.

    "May be built on" is what the skills READ, not only what they must cover: a user-journey step reads the requirements without being required to
    cover them, and it still belongs in the requirement's row."""
    rules = list(rules)
    depth: dict[str, int] = {}
    frontier = set(roots)
    seen = set(roots)
    step = 0
    while frontier:
        step += 1
        following: set[str] = set()
        for rule in rules:
            if frontier & set(rule.reads):
                for holder in rule.holds:
                    if holder not in seen:
                        seen.add(holder)
                        depth[holder] = step
                        following.add(holder)
        frontier = following
    phases = list(phase_order) or list(dict.fromkeys(r.phase for r in rules))
    rank = {phase: n for n, phase in enumerate(phases)}
    listed = {p: n for n, p in enumerate(h for r in rules for h in r.holds)}
    holder_phase = {h: r.phase for r in rules for h in r.holds}
    return tuple(sorted(depth, key=lambda p: (rank.get(holder_phase.get(p, ""), 99), depth[p], listed.get(p, 0))))


# ---- the whole computation ------------------------------------------------------------------------------------------------------------------

def compute(
    items: Sequence[Item],
    links: Iterable[tuple[str, str, str]],
    rules: Sequence[Rule],
    *,
    declared: Mapping[tuple[str, str], str] | None = None,
    written: Iterable[str] = (),
    started_phases: Iterable[str] = (),
    roots: Sequence[str] = ("FR", "NFR"),
    first_layer: Iterable[str] = (),
    artefact_ids: Iterable[str] = (),
    phase_order: Sequence[str] = (),
) -> Trace:
    """The chains and the gaps.

    items         every item of the latest version of every artefact, current or withdrawn
    links         (from item, to item, the artefact that declared it); only the first two are used here
    rules         one per skill that numbers items
    declared      (artefact kind, item ID) -> the writer's reason, from that artefact's Coverage check section
    written       artefact kinds that have at least one version; a rule is only checked against an artefact that exists
    started_phases phases that have at least one written artefact; a layer in another phase is "not started", never "empty"
    roots         the kinds the chain table has a row for
    first_layer   kinds that legitimately derive from nothing (personas, the charter): never "built on nothing"
    artefact_ids  artefact IDs that exist (a link may point at a whole artefact; that is not a missing item)
    """
    declared = declared or {}
    started = set(started_phases)
    first = set(first_layer)
    by_id = {i.id: i for i in items}
    pairs = [(a, b) for a, b, _ in links]
    up, down = build_graph(pairs)
    artefacts = set(artefact_ids)
    exists = set(written)
    holders_phase = {holder: r.phase for r in rules for holder in r.holds}
    gaps: list[Gap] = []

    def add(kind: str, item: Item, other: str | None = None, reason: str | None = None, by: str | None = None) -> None:
        gaps.append(Gap(kind, item.id, item.artefact_id, item.version, other, reason, _sentence(kind, item.id, other, reason, by), by))

    current = [i for i in items if not i.withdrawn]
    for item in sorted(current, key=lambda i: sort_key(i.id)):
        prefix = prefix_of(item.id)
        # 1/2: for every artefact that is written and is required to account for this kind of item: does one of ITS items derive from this one?
        for rule in rules:
            if prefix not in rule.covers or rule.artefact not in exists:
                continue
            if any(prefix_of(d) in rule.holds for d in down.get(item.id, ())):
                continue
            if (rule.artefact, item.id) in declared:
                add(DECLARED, item, reason=declared[(rule.artefact, item.id)], by=rule.artefact)
            else:
                add(NOT_COVERED, item, by=rule.artefact)
        # 3: an item that derives from nothing, though it is not a kind that starts the chain
        if prefix not in first and not up.get(item.id):
            add(BUILT_ON_NOTHING, item)
        # 4/5: what it points at
        for target in up.get(item.id, ()):
            if target in by_id:
                if by_id[target].withdrawn:
                    add(WITHDRAWN_TARGET, item, other=target)
            elif target not in artefacts and not target.startswith(("DOC-", "MEM-")):
                add(MISSING_TARGET, item, other=target)

    order = layer_order(rules, roots, phase_order)
    chains: list[Chain] = []
    for root in sorted((i for i in current if prefix_of(i.id) in roots), key=lambda i: sort_key(i.id)):
        below = [d for d in walk(root.id, down) if d in by_id and not by_id[d].withdrawn]
        by_layer: dict[str, list[str]] = defaultdict(list)
        for d in below:
            by_layer[prefix_of(d)].append(d)
        layers = {p: tuple(sorted(by_layer.get(p, ()), key=sort_key)) for p in order}
        states = {p: ("built" if layers[p] else ("empty" if holders_phase.get(p) in started else "not_started")) for p in order}
        chains.append(Chain(root.id, root.name, layers, states))
    # A column that is empty for EVERY requirement in a phase that has started is not a layer of this table (epics derive from personas, so the epic
    # column is a dash against every requirement). Hiding it is safe: a real hole is a gap for each requirement, and the gap list is the authority.
    never = {p for p in order if holders_phase.get(p) in started and chains and all(not c.layers[p] for c in chains)}
    if never:
        order = tuple(p for p in order if p not in never)
        chains = [Chain(c.item, c.name, {p: c.layers[p] for p in order}, {p: c.states[p] for p in order}) for c in chains]

    counts: dict[str, int] = defaultdict(int)
    for item in current:
        counts[prefix_of(item.id)] += 1
    gaps.sort(key=lambda g: (KINDS.index(g.kind), sort_key(g.item), g.other or "", g.by or ""))
    return Trace(tuple(chains), order, tuple(gaps[:MAX_GAPS]), max(0, len(gaps) - MAX_GAPS), by_id, dict(sorted(counts.items())))


def _words(artefact_key: str | None) -> str:
    return (artefact_key or "an artefact that should cover it").replace("_", " ")


def _sentence(kind: str, item: str, other: str | None, reason: str | None, by: str | None = None) -> str:
    if kind == NOT_COVERED:
        return f"{item} is not named by any item in the {_words(by)}, and its Coverage check does not explain why."
    if kind == DECLARED:
        return f"{item} is listed under Coverage check in the {_words(by)} as not covered. The writer's reason: {reason or 'none given'}"
    if kind == BUILT_ON_NOTHING:
        return f"{item} derives from nothing."
    if kind == WITHDRAWN_TARGET:
        return f"{item} derives from {other}, which was withdrawn."
    return f"{item} names {other}, which is not in any artefact."


def ancestors(item: str, links: Iterable[tuple[str, str]]) -> list[str]:
    """What `item` comes from, nearest first."""
    return walk(item, build_graph(links)[0])


def descendants(item: str, links: Iterable[tuple[str, str]]) -> list[str]:
    """What was built on `item`, nearest first."""
    return walk(item, build_graph(links)[1])
