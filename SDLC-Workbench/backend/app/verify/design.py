"""What the design says should exist (S20b, S20f): endpoints, tables and rules, as plain data read from the saved design artefacts. (Screens were removed in S20f.)

Reading only: nothing here writes, and nothing calls a model. The endpoints come from the Build foundation's interface contract when the set has one (it already holds the
method, path, field names and status codes), and from the low-level design's own endpoint lines otherwise. Tables and rules are items of the design.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ..agents.items import parse_items
from ..build import contract as K
from ..build import instructions as I

AREAS = ("endpoint", "table", "rule")
_ENDPOINT_LINE = re.compile(r"\b(GET|POST|PUT|PATCH|DELETE)\s+(/[A-Za-z0-9_\-./{}:<>%]*)")
_TABLE_COLUMNS = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*[:(]\s*(.*)$")
_WORD = re.compile(r"[a-z][a-z0-9]+")
STOP = frozenset({"page", "screen", "from", "the", "and", "for", "with", "from", "that", "this", "into", "when", "each", "every", "only", "must", "may", "not", "are", "all", "any", "can", "per", "api", "get", "post", "put", "patch", "delete"})


@dataclass(frozen=True)
class Designed:
    id: str                                  # API-002, TBL-001, RUL-001
    area: str                                # endpoint | table | rule
    title: str                               # a short name for the tile
    text: str                                # the design's own line
    method: str = ""
    path: str = ""
    fields: tuple[str, ...] = ()             # request and response field names (endpoint), column names (table)
    codes: tuple[int, ...] = ()
    artefact_id: str = ""
    version: int = 0
    derives: tuple[str, ...] = ()            # the IDs the item says it derives from (a rule and an endpoint that share one are close kin)

    @property
    def words(self) -> frozenset[str]:
        text = re.split(r"\bDerives from\b", self.text, maxsplit=1)[0]                # the citation is not part of what the item is about
        return words_of(" ".join([self.title, text, self.path.replace("/", " "), " ".join(self.fields)]))


@dataclass
class Design:
    items: list[Designed] = field(default_factory=list)
    versions: dict[str, int] = field(default_factory=dict)            # artefact id -> the version this design was read from
    notes: list[str] = field(default_factory=list)                    # plain sentences about what could not be read

    def of(self, area: str) -> list[Designed]:
        return [i for i in self.items if i.area == area]


def words_of(text: str) -> frozenset[str]:
    """The meaningful lower-case words of a text, with a trailing plural 's' removed, so 'reservations' and 'reservation' are one word."""
    out = set()
    for raw in _WORD.findall((text or "").lower().replace("_", " ")):
        word = raw[:-1] if len(raw) > 3 and raw.endswith("s") and not raw.endswith("ss") else raw
        if word not in STOP and len(word) > 2:
            out.add(word)
    return frozenset(out)


def _short(text: str) -> str:
    head = re.split(r"[:;.]| - | — ", (text or "").strip(), maxsplit=1)[0]
    head = " ".join(re.sub(r"\s*\([^)]*\)", "", head).split()) or " ".join(head.split())
    return head if len(head) <= 60 else head[:59].rstrip() + "…"


def read_design(store: Any, skills: Any, project_id: str) -> Design:
    """The latest version of the design artefacts of a project, as things to look for in the build."""
    design = Design()
    found: dict[str, tuple[str, int, str]] = {}                          # artefact type -> (artefact id, version, body)
    for artefact in store.artefacts.list(project_id):
        if artefact.latest_version is None:
            continue
        version = store.artefacts.get_version(project_id, artefact.id)
        found[artefact.type] = (artefact.id, version.number, version.body)
        design.versions[artefact.id] = version.number
    contract = _contract_from(found)
    lld = found.get("low_level_design")
    if lld is not None:
        skill = skills.get("low_level_design")
        parsed = parse_items(lld[2], skill.items) if skill is not None else None
        for item in (parsed.items if parsed else []):
            prefix = item.prefix
            if prefix == "API":
                design.items.append(_endpoint(item.id, item.text, contract, lld, item.derives))
            elif prefix == "TBL":
                design.items.append(_table(item.id, item.text, lld, item.derives))
            elif prefix == "RUL":
                design.items.append(Designed(item.id, "rule", _short(item.text), item.text, artefact_id=lld[0], version=lld[1], derives=item.derives))
    if lld is None:
        design.notes.append("the low-level design has not been written, so there are no endpoints, tables or rules to look for")
    design.items.sort(key=lambda i: (AREAS.index(i.area), i.id))
    return design


def _contract_from(found: dict[str, tuple[str, int, str]]) -> K.Contract | None:
    build = found.get(I.INSTRUCTIONS_KEY)
    if build is None:
        return None
    files, _ = I.split_set(build[2])
    return K.parse_contract(files.get(I.FOUNDATION_NAME))


def _endpoint(item_id: str, text: str, contract: K.Contract | None, source: tuple[str, int, str], derives: tuple[str, ...] = ()) -> Designed:
    line = _ENDPOINT_LINE.search(text)
    method, path = (line.group(1), line.group(2).rstrip(".,;:")) if line else ("", "")
    fields: tuple[str, ...] = ()
    codes: tuple[int, ...] = ()
    if contract is not None:
        for e in contract.endpoints:
            if e.api == item_id and e.method:
                method, path = e.method, e.path.rstrip(".,;:")
                fields = tuple(sorted(e.request | e.response))
                codes = tuple(sorted(e.codes))
                break
    return Designed(item_id, "endpoint", f"{method} {path}".strip() or _short(text), text, method=method, path=path, fields=fields, codes=codes, artefact_id=source[0], version=source[1], derives=derives)


def _table(item_id: str, text: str, source: tuple[str, int, str], derives: tuple[str, ...] = ()) -> Designed:
    head = _TABLE_COLUMNS.match(text.strip())
    columns: tuple[str, ...] = ()
    if head:
        columns = tuple(c.strip(" `.").split(" ")[0] for c in re.split(r"[,;]", head.group(2).split(" Derives from")[0]) if re.match(r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*$", c.strip(" `.").split(" ")[0] or ""))
    return Designed(item_id, "table", _short(text), text, fields=columns, artefact_id=source[0], version=source[1], derives=derives)
