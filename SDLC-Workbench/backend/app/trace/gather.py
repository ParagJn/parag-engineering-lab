"""Collect what the traceability computation needs from the store and the skills (S15). Reading only: nothing here writes, and nothing calls a model.

The computation itself (traceability.py) takes plain data. This turns a project into that data: the items of the LATEST version of every written
artefact, the links between them, the rules from the skills, and the reasons a writer gave in a Coverage check.
"""
from __future__ import annotations

import re
from typing import Any

from ..agents.items import ID_PATTERN, parse_items
from ..agents.reply import section_bodies, unfenced_lines
from ..agents.skills import COVERAGE_SECTION, WITHDRAWN_SECTION, SkillLibrary
from .traceability import Item, Rule, Trace, compute, prefix_of, sort_key

_ID_AT_START = re.compile(rf"^\s*[-*+]?\s*\**\s*({ID_PATTERN})\b\s*[:\-–—]?\s*(?P<reason>.*)$")
REASON_CHARS = 300
# Kinds that legitimately derive from nothing (they start the chain) are read from the skills, not listed by hand: see `first_layer_prefixes`.


def rules_of(skills: SkillLibrary, catalogue) -> list[Rule]:
    """One rule per skill that numbers items. `covers` may be empty: that skill's items still belong in the chain."""
    out: list[Rule] = []
    for key in skills.keys:
        skill = skills.get(key)
        if skill is None or not skill.items:
            continue
        read = tuple(dict.fromkeys(spec.prefix for up in skill.upstream if (s := skills.get(up)) is not None for spec in s.items))
        out.append(Rule(key, tuple(spec.prefix for spec in skill.items), tuple(skill.covers), skill.artefact.phase_key, read))
    return out


def first_layer_prefixes(skills: SkillLibrary) -> set[str]:
    """Item kinds that start the chain: those held by an artefact none of whose inputs holds items (personas read only the charter, which has no items)."""
    holders = {key for key in skills.keys if (s := skills.get(key)) is not None and s.items}
    first: set[str] = set()
    for key in holders:
        skill = skills.get(key)
        if not any(up in holders for up in skill.upstream):
            first.update(spec.prefix for spec in skill.items)
    return first


def declared_reasons(body: str, covered: set[str]) -> dict[str, str]:
    """From an artefact's Coverage check section: `- FR-009 reason` -> {FR-009: reason}. Only IDs of kinds that can be covered count."""
    out: dict[str, str] = {}
    for chunk in section_bodies(body, COVERAGE_SECTION):
        for line in unfenced_lines(chunk):
            match = _ID_AT_START.match(line)
            if match and prefix_of(match.group(1)) in covered:
                reason = " ".join(match.group("reason").split())[:REASON_CHARS]
                out.setdefault(match.group(1), reason or "no reason given")
    return out


def trace_of(store: Any, skills: SkillLibrary, catalogue, project_id: str) -> Trace:
    """The traceability of one project, from the latest version of each written artefact."""
    rules = rules_of(skills, catalogue)
    covered = {p for r in rules for p in r.covers}
    items: list[Item] = []
    declared: dict[tuple[str, str], str] = {}
    written: set[str] = set()
    started: set[str] = set()
    artefact_ids: list[str] = []
    for artefact in store.artefacts.list(project_id):
        artefact_ids.append(artefact.id)
        if artefact.latest_version is None:
            continue
        started.add(artefact.phase_key)
        written.add(artefact.type)
        skill = skills.get(artefact.type)
        if skill is None:
            continue
        version = store.artefacts.get_version(project_id, artefact.id)
        parsed = parse_items(version.body, skill.items)
        for item in parsed.items:
            items.append(Item(item.id, artefact.id, artefact.type, version.number, name=_short(item.text)))
        for withdrawn_id in parsed.withdrawn:
            items.append(Item(withdrawn_id, artefact.id, artefact.type, version.number, withdrawn=True))
        declared.update({(artefact.type, item_id): reason for item_id, reason in declared_reasons(version.body, covered).items()})
    links = [(link.from_id, link.to_id, link.declared_in or "") for link in store.links.list(project_id)]
    return compute(
        items, links, rules, declared=declared, written=written, started_phases=started, roots=("FR", "NFR"),
        first_layer=first_layer_prefixes(skills), artefact_ids=artefact_ids,
        phase_order=[p.key for p in catalogue.phases],
    )


def _short(text: str) -> str:
    head = re.split(r"[:;.]| - | — ", text.strip(), maxsplit=1)[0]
    head = " ".join(re.sub(r"\s*\([^)]*\)", "", head).split()) or " ".join(head.split())
    return head if len(head) <= 60 else head[:59].rstrip() + "…"


def gaps_for_phase(store: Any, skills: SkillLibrary, catalogue, project_id: str, phase_key: str) -> dict[str, Any]:
    """The gaps that belong to one phase, in the shape the approval records: counts per group and the items concerned.

    A gap belongs to a phase when the artefact that FOUND it is there: the one that should have accounted for the item (`by`), or, for the kinds that
    have no such artefact, the one that holds the item. So approving Architecture lists "FR-004 is not named by any component", even though FR-004
    itself lives in Requirements, and approving Requirements does NOT list it: Requirements did nothing wrong. Same computation as the tab."""
    trace = trace_of(store, skills, catalogue, project_id)
    mine = store.artefacts.list(project_id, phase_key=phase_key)
    ids = {a.id for a in mine}
    types = {a.type for a in mine}
    here = [g for g in trace.gaps if (g.by in types if g.by else g.artefact_id in ids)]
    attention = [g for g in here if g.group == "needs_attention"]
    more = trace.gaps_more if here else 0
    return {
        "needs_attention": len(attention) + more, "explained": sum(1 for g in here if g.group == "explained"),
        "items": sorted({g.item for g in attention}, key=sort_key)[:50],
    }
