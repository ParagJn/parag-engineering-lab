"""Match what the design says should exist to what the code has (S20b). Pure code over plain data: no model, no database, no files.

Three steps, strongest first; every match records WHICH step found it and how sure it is:
  1. exact   same method and the same path once every parameter is written `{}`;
  2. shape   same method and the same path after dropping `/api` and `/v1` and ignoring plural forms (`/api/reservations` ~ `/reservation/{id}`... only where the parameters line up);
  3. words   the words of the design's line, path and field names against the words of the code's path, function name and fields (cosine, 0 to 1).
A words match of 0.5 or more counts as FOUND; from 0.25 to under 0.5 it is only POSSIBLE; below that it is not a match.
Each built thing is claimed by at most ONE designed item (the best pair is taken first, then the next, so the order of files never changes the result).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Iterable, Sequence

from ..build.contract import norm_path
from .design import Design, Designed, words_of
from .readers.python_fastapi import Backend, Route, Table

FOUND, DIFFERENCES, POSSIBLE, NOT_FOUND, WEAK = "found", "differences", "possible", "not_found", "weak"
STATES = (FOUND, DIFFERENCES, POSSIBLE, NOT_FOUND, WEAK)
EXACT, SHAPE, WORDS = "exact", "shape", "words"
FOUND_SCORE = 0.5
POSSIBLE_SCORE = 0.25
MAX_DIFFERENCES = 8
_VERSION = re.compile(r"^v\d+$")

@dataclass(frozen=True)
class Match:
    designed: str                    # the design item ID
    area: str
    state: str
    step: str = ""                   # exact | shape | words | "" when nothing was found
    score: float = 0.0
    built: str = ""                  # what was found, as a short label: `POST /api/bookings`, `bookings`
    file: str = ""
    line: int = 0
    differences: tuple[str, ...] = ()
    note: str = ""

@dataclass(frozen=True)
class Extra:
    """Something the code has that the design never mentioned."""
    area: str
    built: str
    file: str
    line: int = 0

@dataclass
class Matched:
    matches: list[Match] = field(default_factory=list)
    extras: list[Extra] = field(default_factory=list)

# ---- text helpers ------------------------------------------------------------------------------------------------------------------------------------

def singular(word: str) -> str:
    w = word.lower()
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if w.endswith("ses") and len(w) > 4:
        return w[:-2]
    if w.endswith("s") and not w.endswith(("ss", "us", "is")) and len(w) > 3:
        return w[:-1]
    return w

def shape_of(path: str) -> tuple[str, ...]:
    """A path as its words: no `/api`, no `/v1`, every parameter `{}`, every word in the singular and lower case."""
    parts = [p for p in norm_path(path).split("/") if p]
    return tuple("{}" if p == "{}" else singular(p) for p in parts if p.lower() != "api" and not _VERSION.match(p.lower()))

def normal(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", singular(name.replace("_", "")))                # `singular` lower-cases

def cosine(a: Iterable[str], b: Iterable[str]) -> float:
    left, right = set(a), set(b)
    if not left or not right:
        return 0.0
    return len(left & right) / math.sqrt(len(left) * len(right))

def names_agree(designed: str, built: Iterable[str]) -> bool:
    """A designed field name is present in the code if some name is the same once case, underscores and plurals are ignored, or one name's words hold the other's
    (`date` in `reservation_date`)."""
    want = normal(designed)
    want_words = words_of(designed)
    for name in built:
        have = normal(name)
        if want == have:
            return True
        have_words = words_of(name)
        if want_words and have_words and (want_words <= have_words or have_words <= want_words):
            return True
    return False

def _bounded(items: Sequence[str]) -> tuple[str, ...]:
    return tuple(items[:MAX_DIFFERENCES]) + ((f"and {len(items) - MAX_DIFFERENCES} more",) if len(items) > MAX_DIFFERENCES else ())

# ---- endpoints ---------------------------------------------------------------------------------------------------------------------------------------

def _route_fields(route: Route, backend: Backend) -> set[str]:
    names = set(route.params)
    for model in (route.body_model, _model_in(route.response_model, backend)):
        if model and model in backend.models:
            names |= {f.name for f in backend.models[model].fields}
    return names

def _model_in(response_model: str, backend: Backend) -> str:
    """The model a `response_model=` expression names: `Reservation`, `list[Reservation]`, `Optional[Reservation]`."""
    for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", response_model or ""):
        if word in backend.models:
            return word
    return ""

def _route_words(route: Route, backend: Backend) -> frozenset[str]:
    return words_of(" ".join([route.path.replace("/", " "), route.function, " ".join(sorted(_route_fields(route, backend)))]))

def _route_key(route: Route) -> tuple[str, str, int, str]:
    return (route.file, route.method, route.line, route.path)

def _label(route: Route) -> str:
    return f"{route.method} {route.path}"

def _endpoint_differences(item: Designed, route: Route, backend: Backend) -> list[str]:
    out: list[str] = []
    built_fields = _route_fields(route, backend)
    if item.fields:
        missing = [f for f in item.fields if not names_agree(f, built_fields)]
        if missing and built_fields:
            out.append("the design names " + ", ".join(f"'{m}'" for m in missing) + " but the code does not use " + ("it" if len(missing) == 1 else "them"))
        elif missing and not built_fields:
            out.append("the code's handler declares no fields to compare with the design's " + ", ".join(f"'{m}'" for m in missing[:3]))
    if item.codes:
        absent = [c for c in item.codes if c >= 400 and c not in route.status_codes]
        if absent:
            out.append("the design lists status " + ", ".join(str(c) for c in absent) + " but the code never returns " + ("it" if len(absent) == 1 else "them"))
        ok = [c for c in item.codes if 200 <= c < 300]
        if ok and not any(c in route.status_codes for c in ok):
            out.append(f"the design succeeds with {ok[0]} but the code answers {route.status_codes[0] if route.status_codes else 200}")
    if route.prefix_unknown:
        out.append("the router's prefix is built in code, so the full path could not be read exactly")
    return out

def match_endpoints(design: Design, backend: Backend) -> tuple[list[Match], list[Extra]]:
    wanted = design.of("endpoint")
    routes = list(backend.routes)
    pairs: list[tuple[int, float, str, tuple, Designed, Route]] = []
    for item in wanted:
        d_words = item.words
        for route in routes:
            if item.method and route.method != item.method:
                continue
            if item.path and norm_path(item.path) == norm_path(route.path):
                pairs.append((0, 1.0, item.id, _route_key(route), item, route))
            elif item.path and shape_of(item.path) == shape_of(route.path):
                pairs.append((1, 1.0, item.id, _route_key(route), item, route))
            else:
                score = cosine(d_words, _route_words(route, backend))
                if score >= POSSIBLE_SCORE:
                    pairs.append((2, score, item.id, _route_key(route), item, route))
    # best first: the stronger step, then the higher score, then the ID and the code location, so the result never depends on the order the files came in
    pairs.sort(key=lambda p: (p[0], -p[1], p[2], p[3]))
    taken_items: dict[str, tuple[int, float, Route]] = {}
    taken_routes: set[tuple] = set()
    for rank, score, item_id, key, item, route in pairs:
        if item_id in taken_items or key in taken_routes:
            continue
        taken_items[item_id] = (rank, score, route)
        taken_routes.add(key)
    matches: list[Match] = []
    for item in wanted:
        if item.id not in taken_items:
            matches.append(Match(item.id, "endpoint", NOT_FOUND, built="", note="nothing in the code looks like this endpoint"))
            continue
        rank, score, route = taken_items[item.id]
        step = (EXACT, SHAPE, WORDS)[rank]
        if step == WORDS and score < FOUND_SCORE:
            matches.append(Match(item.id, "endpoint", POSSIBLE, step, round(score, 2), _label(route), route.file, route.line,
                                 note=f"the words of the design and of {_label(route)} overlap, but not enough to be sure"))
            continue
        diffs = _endpoint_differences(item, route, backend)
        renamed = [f"the design says {item.method} {item.path}, the code has {_label(route)}"] if step != EXACT and item.path else []
        all_diffs = [*renamed, *diffs] if step == WORDS else diffs
        matches.append(Match(item.id, "endpoint", DIFFERENCES if all_diffs else FOUND, step, round(score, 2), _label(route), route.file, route.line, _bounded(all_diffs)))
    extras = [Extra("endpoint", _label(r), r.file, r.line) for r in routes if _route_key(r) not in taken_routes]
    return matches, extras

# ---- tables ------------------------------------------------------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class _Built:
    name: str
    columns: frozenset[str]
    file: str
    line: int

def _merged_tables(tables: Sequence[Table]) -> list[_Built]:
    """A table described twice (an ORM class and a CREATE TABLE) is one table with the columns of both."""
    by_name: dict[str, list[Table]] = {}
    for t in tables:
        by_name.setdefault(t.name.lower(), []).append(t)
    out = []
    for group in by_name.values():
        first = sorted(group, key=lambda t: (t.file, t.line))[0]
        out.append(_Built(first.name, frozenset(c for t in group for c in t.columns), first.file, first.line))
    return sorted(out, key=lambda b: (b.name.lower(), b.file))

def match_tables(design: Design, backend: Backend) -> tuple[list[Match], list[Extra]]:
    wanted = design.of("table")
    built = _merged_tables(backend.tables)
    pairs: list[tuple[int, float, str, str, Designed, _Built]] = []
    for item in wanted:
        d_words = words_of(" ".join([item.title, " ".join(item.fields)]))
        for b in built:
            if item.title.lower() == b.name.lower():
                pairs.append((0, 1.0, item.id, b.name, item, b))
            elif normal(item.title) == normal(b.name):
                pairs.append((1, 1.0, item.id, b.name, item, b))
            else:
                score = cosine(d_words, words_of(" ".join([b.name, " ".join(sorted(b.columns))])))
                if score >= POSSIBLE_SCORE:
                    pairs.append((2, score, item.id, b.name, item, b))
    pairs.sort(key=lambda p: (p[0], -p[1], p[2], p[3]))
    taken_items: dict[str, tuple[int, float, _Built]] = {}
    taken_built: set[str] = set()
    for rank, score, item_id, name, item, b in pairs:
        if item_id in taken_items or name in taken_built:
            continue
        taken_items[item_id] = (rank, score, b)
        taken_built.add(name)
    matches = []
    for item in wanted:
        if item.id not in taken_items:
            matches.append(Match(item.id, "table", NOT_FOUND, note="no table in the code looks like this one"))
            continue
        rank, score, b = taken_items[item.id]
        step = (EXACT, SHAPE, WORDS)[rank]
        if step == WORDS and score < FOUND_SCORE:
            matches.append(Match(item.id, "table", POSSIBLE, step, round(score, 2), b.name, b.file, b.line, note=f"'{b.name}' shares some words with this table, not enough to be sure"))
            continue
        missing = [c for c in item.fields if not names_agree(c, b.columns)]
        diffs = []
        if step != EXACT:
            diffs.append(f"the design calls it '{item.title}', the code '{b.name}'")
        if missing and b.columns:
            diffs.append("the design has column" + ("s " if len(missing) > 1 else " ") + ", ".join(f"'{m}'" for m in missing) + " that the code's table does not")
        matches.append(Match(item.id, "table", DIFFERENCES if diffs else FOUND, step, round(score, 2), b.name, b.file, b.line, _bounded(diffs)))
    extras = [Extra("table", b.name, b.file, b.line) for b in built if b.name not in taken_built]
    return matches, extras

# ---- rules (weak evidence only) ----------------------------------------------------------------------------------------------------------------------

RULE_WORDS_NEEDED = 3                # a rule quoted by its words needs this many of its words together in one comment, test name or message
RULE_LINK_WORDS = 3                  # a rule and an endpoint with no requirement in common are kin if they share this many words
_CITED_SOURCE = ("MEM-", "DOC-")     # a chunk of an uploaded document is not a requirement two items can be said to share

@dataclass(frozen=True)
class _Link:
    endpoint: Designed
    shared_sources: tuple[str, ...]
    shared_words: tuple[str, ...]

def _requirements(item: Designed) -> frozenset[str]:
    return frozenset(d for d in item.derives if not d.startswith(_CITED_SOURCE))

def rule_link(rule: Designed, endpoints: Sequence[Designed]) -> _Link | None:
    """The endpoint a rule belongs to, or None. Kin = they derive from a requirement in common AND share at least one meaningful word, or they share RULE_LINK_WORDS words
    without a requirement in common. When several qualify the one sharing the most words wins, then the one with a shared requirement, then the lowest ID, so the
    order of the design never changes the answer."""
    best: tuple[tuple[int, int, str], _Link] | None = None
    for ep in endpoints:
        words = tuple(sorted(rule.words & ep.words))
        sources = tuple(sorted(_requirements(rule) & _requirements(ep)))
        if not ((sources and words) or len(words) >= RULE_LINK_WORDS):
            continue
        key = (-len(words), -len(sources), ep.id)
        if best is None or key < best[0]:
            best = (key, _Link(ep, sources, words))
    return best[1] if best else None

def _why(link: _Link) -> str:
    kin = (f"both come from {', '.join(link.shared_sources)} and share the word{'s' if len(link.shared_words) != 1 else ''} {', '.join(link.shared_words)}" if link.shared_sources
           else f"they share the words {', '.join(link.shared_words)}")
    return f"Linked to {link.endpoint.id} because {kin}"

def _by_label(backend: Backend | None) -> dict[str, Route]:
    return {_label(r): r for r in (backend.routes if backend else [])}

def _endpoint_hint(rule: Designed, link: _Link, found: dict[str, Match], routes: dict[str, Route]) -> Match:
    """What the rule's endpoint says about the rule. NEVER FOUND: a rule is logic, and an endpoint that exists shows only that the rule has a home."""
    ep, why = link.endpoint, _why(link)
    m = found.get(ep.id)
    if m is None or m.state not in (FOUND, DIFFERENCES):
        if m is not None and m.state == POSSIBLE:
            return Match(rule.id, "rule", NOT_FOUND, note=f"{why}, but {ep.id} was only a possible match in the build, so nothing is claimed for this rule")
        return Match(rule.id, "rule", NOT_FOUND, note=f"{why}, but {ep.id} ({ep.title}) was not found in the build, so there is nowhere the rule could be enforced")
    route = routes.get(m.built)
    wanted = tuple(c for c in ep.codes if c >= 400)
    answered = tuple(c for c in wanted if route is not None and c in route.status_codes)
    where = dict(built=m.built, file=m.file, line=m.line)
    if wanted and not answered:
        return Match(rule.id, "rule", NOT_FOUND, **where, note=f"{why}. {ep.id} is built as {m.built}, but it never answers {', '.join(map(str, wanted))}, which is how the design says a refusal looks")
    if answered:
        return Match(rule.id, "rule", WEAK, **where, note=(f"{why}. {ep.id} is built as {m.built} and answers {', '.join(map(str, answered))}, which is how the design says a refusal looks. "
                                                          "This is weak evidence: the rule has a home, but nothing shows it is enforced."))
    return Match(rule.id, "rule", WEAK, **where, note=f"{why}. {ep.id} is built as {m.built}; the design gives it no error code, so this only shows the rule has a home. This is weak evidence, not proof it is enforced.")

def match_rules(design: Design, texts: Sequence[tuple[str, str]], endpoints: Sequence[Match] = (), backend: Backend | None = None) -> list[Match]:
    """A rule is logic, not a name, so the only evidence is WEAK, and it is never FOUND. Three kinds, strongest first:
      1. its ID written in a comment, a test name or a message, or RULE_WORDS_NEEDED of its own words together in one of them (`texts`, picked out of the code by the reader);
      2. its endpoint: the endpoint it is kin to (`rule_link`), built, and answering the error code the design gives it;
      3. nothing: it is NOT FOUND, and the note says why."""
    out: list[Match] = []
    ordered = sorted(texts)
    designed_endpoints = design.of("endpoint")
    found = {m.designed: m for m in endpoints}
    routes = _by_label(backend)
    for item in design.of("rule"):
        id_re = re.compile(rf"(?<![A-Za-z0-9-]){re.escape(item.id)}(?![A-Za-z0-9])")
        hit = next(((f, t) for f, t in ordered if id_re.search(t)), None)
        how = f"{item.id} is written in a comment, a test or a message"
        if hit is None:
            rule_words = item.words
            best = max(((len(rule_words & words_of(t)), f, t) for f, t in ordered), default=(0, "", ""), key=lambda x: (x[0], -ord(x[1][:1] or " "), x[1], x[2]))
            if best[0] >= RULE_WORDS_NEEDED:
                hit, how = (best[1], best[2]), f"{best[0]} of the rule's words appear together in one comment, test or message"
        if hit is not None:
            out.append(Match(item.id, "rule", WEAK, WORDS, 0.0, "", hit[0], 0, note=how + ". This is weak evidence: it shows the rule was talked about, not that it is enforced."))
            continue
        link = rule_link(item, designed_endpoints)
        if link is None:
            out.append(Match(item.id, "rule", NOT_FOUND, note="no comment, test or message in the code mentions this rule, and no endpoint of the design is clearly where it belongs"))
        else:
            out.append(_endpoint_hint(item, link, found, routes))
    return out

def match_all(design: Design, backend: Backend) -> Matched:
    out = Matched()
    for matcher in (match_endpoints, match_tables):
        m, e = matcher(design, backend)
        out.matches += m
        out.extras += e
    out.matches += match_rules(design, list(backend_texts(backend)), [x for x in out.matches if x.area == "endpoint"], backend)
    return out

def backend_texts(backend: Backend) -> list[tuple[str, str]]:
    """Comments, docstrings, test names and messages from the Python files: `backend.texts`, filled by the reader."""
    return list(getattr(backend, "texts", []))
