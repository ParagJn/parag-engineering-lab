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


def match_rules(design: Design, texts: Sequence[tuple[str, str]]) -> list[Match]:
    """A rule is logic, not a name, so the only evidence is WEAK: its ID written in a comment, a test name or a message, or RULE_WORDS_NEEDED of its own words together in
    one of them. It is never FOUND. `texts` are (file, text) pairs picked out of the code by the readers."""
    out: list[Match] = []
    ordered = sorted(texts)
    for item in design.of("rule"):
        id_re = re.compile(rf"(?<![A-Za-z0-9-]){re.escape(item.id)}(?![A-Za-z0-9])")
        hit = next(((f, t) for f, t in ordered if id_re.search(t)), None)
        how = f"{item.id} is written in a comment, a test or a message"
        if hit is None:
            rule_words = item.words
            best = max(((len(rule_words & words_of(t)), f, t) for f, t in ordered), default=(0, "", ""), key=lambda x: (x[0], -ord(x[1][:1] or " "), x[1], x[2]))
            if best[0] >= RULE_WORDS_NEEDED:
                hit, how = (best[1], best[2]), f"{best[0]} of the rule's words appear together in one comment, test or message"
        if hit is None:
            out.append(Match(item.id, "rule", NOT_FOUND, note="no comment, test or message in the code mentions this rule"))
        else:
            out.append(Match(item.id, "rule", WEAK, WORDS, 0.0, "", hit[0], 0, note=how + ". This is weak evidence: it shows the rule was talked about, not that it is enforced."))
    return out


# ---- screens (by the pages of the frontend) ----------------------------------------------------------------------------------------------------------

GENERIC_FOLDERS = frozenset({"src", "app", "pages", "views", "screens", "routes", "components", "lib", "web", "client", "frontend", "ui", "index", "main"})


def _page_words(name: str, file: str) -> frozenset[str]:
    """The words of a page: its route and its file path, without the extension, the folders every project has, and file-name case (`BrowseRooms` is `browse rooms`)."""
    stem = re.sub(r"\.[A-Za-z0-9]+$", "", file)
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", f"{name} {stem}")
    return frozenset(w for w in words_of(re.sub(r"[/\\._\-:\[\]]", " ", spaced)) if w not in GENERIC_FOLDERS)


def match_screens(design: Design, pages: Sequence[tuple[str, str, int]], calls: dict[str, frozenset[str]], endpoints: Sequence[Match]) -> tuple[list[Match], list[Extra]]:
    """`pages` are (route or page name, file, line); `calls` maps a file to the API paths it calls. A screen is matched to the page whose name and file share the most words with
    it. A matched screen has DIFFERENCES when the design's endpoints that the screen is about (by shared words) are built, but the page never calls any of them."""
    wanted = design.of("screen")
    pairs = []
    for item in wanted:
        for name, file, line in pages:
            score = cosine(item.words, _page_words(name, file))
            if score >= POSSIBLE_SCORE:
                pairs.append((-score, item.id, name, file, line))
    pairs.sort()
    taken: dict[str, tuple[float, str, str, int]] = {}
    used: set[tuple[str, str]] = set()
    for neg, item_id, name, file, line in pairs:
        if item_id in taken or (name, file) in used:
            continue
        taken[item_id] = (-neg, name, file, line)
        used.add((name, file))
    built = {m.designed: norm_path(m.built.split(" ", 1)[1]) for m in endpoints if m.built and " " in m.built and m.state in (FOUND, DIFFERENCES)}
    designed = {i.id: i for i in design.of("endpoint")}
    out: list[Match] = []
    for item in wanted:
        if item.id not in taken:
            out.append(Match(item.id, "screen", NOT_FOUND, note="no page in the frontend looks like this screen"))
            continue
        score, name, file, line = taken[item.id]
        if score < FOUND_SCORE:
            out.append(Match(item.id, "screen", POSSIBLE, WORDS, round(score, 2), name, file, line, note=f"'{name}' shares some words with this screen, not enough to be sure"))
            continue
        called = {norm_path(p) for p in calls.get(file, frozenset())}
        about = [api for api in built if item.words & designed[api].words]
        missing = [api for api in about if built[api] not in called]
        diffs = ()
        if about and missing and not any(built[api] in called for api in about):
            diffs = (f"the screen is about {', '.join(sorted(missing))}, but its page never calls " + ("it" if len(missing) == 1 else "them"),)
        out.append(Match(item.id, "screen", DIFFERENCES if diffs else FOUND, WORDS, round(score, 2), name, file, line, diffs, note=("calls " + ", ".join(sorted(called))) if called else ""))
    extras = [Extra("screen", name, file, line) for name, file, line in pages if (name, file) not in used]
    return out, extras


def match_all(design: Design, backend: Backend, frontend=None) -> Matched:
    out = Matched()
    for matcher in (match_endpoints, match_tables):
        m, e = matcher(design, backend)
        out.matches += m
        out.extras += e
    texts = list(backend_texts(backend))
    if frontend is not None:
        pages = [(p.name, p.file, p.line) for p in frontend.pages]
        m, e = match_screens(design, pages, frontend.calls_by_file(), [x for x in out.matches if x.area == "endpoint"])
        out.matches += m
        out.extras += e
        texts += frontend.texts
    elif design.of("screen"):
        out.matches += [Match(i.id, "screen", NOT_FOUND, note="no frontend folder was given, so this screen could not be looked for") for i in design.of("screen")]
    out.matches += match_rules(design, texts)
    return out


def backend_texts(backend: Backend) -> list[tuple[str, str]]:
    """Comments, docstrings, test names and messages from the Python files: `backend.texts`, filled by the reader."""
    return list(getattr(backend, "texts", []))
