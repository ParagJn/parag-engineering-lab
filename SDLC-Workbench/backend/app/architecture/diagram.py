"""Architecture diagrams as plain lists, drawn by the server (S14b).

A model never draws a diagram here. It writes a list, one line per call or per use case, and this module (1) checks that every line points at
things that exist, and (2) draws the picture itself from the list, with a fixed layout. So a model cannot get a box, an arrow or an arrowhead
wrong, a person fixes a diagram by editing one line, and the picture can never be out of step with the text: it is drawn when the artefact is
read, from the current text, and is never stored.

    Flow diagram        - FLOW-001 COMP-001 -> COMP-003: sends the booking request. Derives from: IFC-001, COMP-001, COMP-003, FR-002
    Use-case diagram    - UC-001 Reserve a room: staff pick a free slot. Derives from: PER-001, FR-001

A flow line is an arrow from one component to another. A use-case line is one use case; its actors are the personas (PER-...) named under
"Derives from:". Components and personas are real items in earlier artefacts, so a line naming one that does not exist is sent back.

The picture comes in two looks, draw.io and Notion (style.py), from one layout (layout.py): lines at right angles through lanes between the boxes,
a number on each line, and a key under the picture saying what each number is. Everything drawn is a rectangle, an ellipse, a line, a polyline, a
small triangle or text, so the result passes the S13 sanitiser unchanged (a test checks that). It never raises: a body with nothing to draw gives None.
"""
from __future__ import annotations

import re
from typing import Collection, Mapping

from ..agents.items import ID_PATTERN, Item, ItemSpec, parse_items
from ..design.sanitise import MAX_DIAGRAM_CHARS, sanitise_svg
from .layout import HEAD, NODE_H, NODE_W, PAD, Edge, UseCase, layout_flow
from .style import DEFAULT, STYLES, Style, style_of

FLOW = "flow_diagram"
USECASE = "usecase_diagram"
KINDS = (FLOW, USECASE)
SPECS = {FLOW: ItemSpec("FLOW", "Flow"), USECASE: ItemSpec("UC", "Use cases")}

MAX_NODES = 12                 # components in a flow, or actors plus use cases in a use-case diagram
MAX_LINES = 24                 # arrows in a flow, or use cases in a use-case diagram
MAX_NAME_CHARS = 40

_COMPONENT = re.compile(r"^COMP-\d{3,}$")
_PERSONA = re.compile(r"^PER-\d{3,}$")
_REQUIREMENT = re.compile(r"^(?:FR|NFR)-\d{3,}$")
_DERIVES = re.compile(r"\bderives[ \t]+from[ \t]*:", re.IGNORECASE)
_FLOW_LINE = re.compile(rf"^\s*(?P<src>{ID_PATTERN})\s*(?:->|→|—>|-->)\s*(?P<dst>{ID_PATTERN})\s*:\s*(?P<label>.*)$")


def _before_derives(text: str) -> str:
    return _DERIVES.split(text, maxsplit=1)[0].strip()


def short_name(text: str, limit: int = MAX_NAME_CHARS) -> str:
    """The first few words of an item's text, up to its first colon, comma or full stop: "Booking service: decides if..." -> "Booking service"."""
    head = re.split(r"[:;,.]| - | — ", text.strip(), maxsplit=1)[0].strip()
    head = " ".join(re.sub(r"\s*\([^)]*\)", "", head).split()) or " ".join(head.split())      # "Office staff member (floors two to four)" -> "Office staff member"
    return head if len(head) <= limit else head[: limit - 1].rstrip() + "…"


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


# ---- reading the lists ------------------------------------------------------------------------------------------------------------------

def edges_of(items: tuple[Item, ...]) -> tuple[list[Edge], list[str]]:
    """(edges, ids of lines that are not written as 'COMP-001 -> COMP-002: label')."""
    edges: list[Edge] = []
    unreadable: list[str] = []
    for item in items:
        match = _FLOW_LINE.match(_before_derives(item.text))
        if match is None or not match.group("label").strip():
            unreadable.append(item.id)
            continue
        edges.append(Edge(item.id, match.group("src"), match.group("dst"), match.group("label").strip()))
    return edges, unreadable


def usecases_of(items: tuple[Item, ...]) -> list[UseCase]:
    """A use case is named by the words before the first colon ("Reserve a room: staff pick a free slot" -> "Reserve a room")."""
    out: list[UseCase] = []
    for item in items:
        name = " ".join(_before_derives(item.text).split(":", 1)[0].split())
        out.append(UseCase(item.id, name, tuple(t for t in item.derives if _PERSONA.match(t))))
    return out


def _items(kind: str, body: str) -> tuple[Item, ...]:
    return parse_items(body, [SPECS[kind]]).items


# ---- the check ---------------------------------------------------------------------------------------------------------------------------

def diagram_problems(kind: str, body: str, known: Collection[str]) -> list[str]:
    """Plain sentences about every line that cannot be drawn. [] means the whole list can. `known` is every ID the writer was shown."""
    if kind not in KINDS:
        return []
    items = _items(kind, body)
    problems: list[str] = []
    if kind == FLOW:
        edges, unreadable = edges_of(items)
        for item_id in unreadable:
            problems.append(f"{item_id} is not written as an arrow; write it as '{item_id} COMP-001 -> COMP-002: what is sent', with the two component IDs and a few words after the colon")
        nodes: list[str] = []
        for edge in edges:
            for end in (edge.source, edge.target):
                if not _COMPONENT.match(end) or end not in known:
                    problems.append(f"{edge.item_id} names {end}, which is not a component in the component overview you were given; use only COMP IDs from it")
                elif end not in nodes:
                    nodes.append(end)
            if edge.source == edge.target:
                problems.append(f"{edge.item_id} is a call from {edge.source} to itself; a flow shows calls between two different components")
        if len(edges) > MAX_LINES:
            problems.append(f"the flow has {len(edges)} arrows; the limit is {MAX_LINES}. Keep the calls that matter most")
        if len(nodes) > MAX_NODES:
            problems.append(f"the flow touches {len(nodes)} components; the limit is {MAX_NODES}. Group related components or leave the minor ones out")
        return _unique(problems)

    cases = usecases_of(items)
    actors: list[str] = []
    for case in cases:
        if not case.name:
            problems.append(f"{case.item_id} has no name; write what the person does, then a colon, as '{case.item_id} Reserve a room: ...'")
        if not case.actors:
            problems.append(f"{case.item_id} has no actor; name at least one persona (a PER ID) under 'Derives from:'")
        for actor in case.actors:
            if actor not in known:
                problems.append(f"{case.item_id} names {actor}, which is not a persona you were given")
            elif actor not in actors:
                actors.append(actor)
    for item in items:
        if not any(_REQUIREMENT.match(t) for t in item.derives):
            problems.append(f"{item.id} names no requirement; add the FR or NFR ID it serves under 'Derives from:'")
    if len(cases) > MAX_LINES:
        problems.append(f"the diagram has {len(cases)} use cases; the limit is {MAX_LINES}. Keep the ones that matter most")
    if len(actors) + len(cases) > MAX_NODES:
        problems.append(f"the diagram has {len(actors)} actors and {len(cases)} use cases, {len(actors) + len(cases)} boxes in all; the limit is {MAX_NODES}. Merge related use cases")
    return _unique(problems)


def _unique(problems: list[str]) -> list[str]:
    seen: set[str] = set()
    return [p for p in problems if not (p in seen or seen.add(p))]


# ---- drawing -----------------------------------------------------------------------------------------------------------------------------

KEY_LABEL_CHARS = 62           # how much of a call's sentence the key under the picture shows; the whole sentence is in the list below
NAME_LINE_CHARS = 22           # a box shows a name on up to two lines of this many characters
CASE_LINE_CHARS = 26
ELLIPSE_W, ELLIPSE_H, ELLIPSE_ROW = 280, 60, 82
ACTOR_COLUMN, ACTOR_H = 150, 104


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _wrap(text: str, width: int, max_lines: int = 2) -> list[str]:
    """The text on at most `max_lines` lines of at most `width` characters, broken at spaces; what does not fit ends in an ellipsis."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        word = word if len(word) <= width else word[: width - 1] + "…"
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current += " " + word
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        last = lines[-1]
        lines[-1] = (last[: width - 1].rstrip() + "…") if len(last) >= width else last + "…"
    return lines or [""]


def _text(x: float, y: float, text: str, size: float, fill: str, st: Style, anchor: str = "start", weight: str = "normal") -> str:
    return (f'<text x="{round(x)}" y="{round(y)}" font-size="{size}" font-family="{st.font}" font-weight="{weight}" text-anchor="{anchor}" '
            f'fill="{fill}">{_esc(text)}</text>')


def _head_points(tip: tuple[int, int], back: tuple[int, int]) -> str:
    """A small filled triangle whose point is `tip`, for a line that arrives from `back`."""
    dx, dy = tip[0] - back[0], tip[1] - back[1]
    length = (dx * dx + dy * dy) ** 0.5 or 1.0
    ux, uy = dx / length, dy / length
    bx, by = tip[0] - ux * HEAD, tip[1] - uy * HEAD
    px, py = -uy * HEAD * 0.45, ux * HEAD * 0.45
    return f"{tip[0]},{tip[1]} {round(bx + px)},{round(by + py)} {round(bx - px)},{round(by - py)}"


def _frame(width: int, height: int, title: str, st: Style) -> list[str]:
    return [f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg"><title>{_esc(title)}</title>',
            f'<rect x="0" y="0" width="{width}" height="{height}" fill="{st.background}"/>']


def draw_flow(body: str, labels: Mapping[str, str], style: str = DEFAULT) -> str:
    st = style_of(style)
    edges, _ = edges_of(_items(FLOW, body))
    edges = [e for e in edges if e.source != e.target][:MAX_LINES]
    layout = layout_flow(edges, labels)
    if layout is None or len(layout.boxes) > MAX_NODES:
        return ""
    parts = _frame(layout.width, layout.height, f"Flow diagram: {len(layout.boxes)} components, {len(edges)} calls", st)
    for box in layout.boxes:
        parts.append(f'<rect x="{box.x}" y="{box.y}" width="{box.w}" height="{box.h}" rx="{st.box_radius}" fill="{st.box_fill}" '
                     f'stroke="{st.box_stroke}" stroke-width="{st.box_stroke_width}"/>')
        lines = _wrap(labels.get(box.key, ""), NAME_LINE_CHARS) if labels.get(box.key) else []
        block = 12 + 16 * len(lines)
        top = box.y + (box.h - block) / 2
        cx = box.x + box.w / 2
        parts.append(_text(cx, top + 9, box.key, 9, st.id_ink, st, "middle"))
        if not lines:
            continue
        for i, line in enumerate(lines):
            parts.append(_text(cx, top + 12 + 14 + 16 * i, line, 12.5, st.title, st, "middle", st.title_weight))
    for link in layout.links:                                    # lines after boxes, so a head is never hidden under a box edge
        points = " ".join(f"{x},{y}" for x, y in link.points)
        parts.append(f'<polyline points="{points}" fill="none" stroke="{st.line}" stroke-width="{st.line_width}" stroke-linejoin="round"/>')
        if link.head_b:
            parts.append(f'<polygon points="{_head_points(link.points[-1], link.points[-2])}" fill="{st.line}" stroke="{st.line}"/>')
        if link.head_a:
            parts.append(f'<polygon points="{_head_points(link.points[0], link.points[1])}" fill="{st.line}" stroke="{st.line}"/>')
    for link in layout.links:
        b = link.badge
        parts.append(f'<rect x="{b.x}" y="{b.y}" width="{b.w}" height="{b.h}" rx="{b.h // 2}" fill="{st.badge_fill}" stroke="{st.badge_stroke}"/>')
        parts.append(_text(b.x + b.w / 2, b.y + b.h - 4.5, b.text, 10, st.badge_ink, st, "middle", "bold"))
    parts.append(f'<line x1="{PAD}" y1="{layout.key_top - 6}" x2="{layout.width - PAD}" y2="{layout.key_top - 6}" stroke="{st.key_rule}"/>')
    parts.append(_text(PAD, layout.key_top + 14, "Calls", 12, st.key_ink, st, "start", "bold"))
    for entry in layout.key:
        width = 14 + 7 * len(str(entry.number))
        parts.append(f'<rect x="{entry.x}" y="{entry.y - 2}" width="{width}" height="16" rx="8" fill="{st.badge_fill}" stroke="{st.badge_stroke}"/>')
        parts.append(_text(entry.x + width / 2, entry.y + 9.5, str(entry.number), 10, st.badge_ink, st, "middle", "bold"))
        parts.append(_text(entry.x + width + 8, entry.y + 9.5, _clip(f"{entry.source} → {entry.target}", 58), 10.5, st.key_ink, st, "start", "bold"))
        parts.append(_text(entry.x + width + 8, entry.y + 23, _clip(entry.label, KEY_LABEL_CHARS), 10.5, st.key_muted, st))
    parts.append("</svg>")
    return "".join(parts)


def _stick_figure(cx: int, top: int, st: Style) -> list[str]:
    ink = f'stroke="{st.line}" stroke-width="1.6"'
    return [f'<circle cx="{cx}" cy="{top + 10}" r="9" fill="{st.actor_fill}" stroke="{st.actor_stroke}" stroke-width="1.6"/>',
            f'<line x1="{cx}" y1="{top + 19}" x2="{cx}" y2="{top + 42}" {ink}/>',
            f'<line x1="{cx - 15}" y1="{top + 28}" x2="{cx + 15}" y2="{top + 28}" {ink}/>',
            f'<line x1="{cx}" y1="{top + 42}" x2="{cx - 12}" y2="{top + 60}" {ink}/>',
            f'<line x1="{cx}" y1="{top + 42}" x2="{cx + 12}" y2="{top + 60}" {ink}/>']


def draw_usecases(body: str, labels: Mapping[str, str], style: str = DEFAULT) -> str:
    st = style_of(style)
    cases = [c for c in usecases_of(_items(USECASE, body)) if c.name][:MAX_LINES]
    actors: list[str] = []
    for c in cases:
        for a in c.actors:
            if a not in actors:
                actors.append(a)
    if not cases or len(actors) + len(cases) > MAX_NODES:
        return ""
    ellipse_x = PAD + ACTOR_COLUMN + 96
    top = PAD + 36
    centre = {c.item_id: top + i * ELLIPSE_ROW + ELLIPSE_H // 2 for i, c in enumerate(cases)}
    wanted = {a: sum(centre[c.item_id] for c in cases if a in c.actors) / max(1, sum(1 for c in cases if a in c.actors)) for a in actors}
    placed: dict[str, int] = {}
    floor = top - 12
    for a in sorted(actors, key=lambda a: (wanted[a], actors.index(a))):          # as close to its use cases as they allow, without touching each other
        y = max(round(wanted[a] - 30), floor)
        placed[a] = y
        floor = y + ACTOR_H
    bottom = max(top + len(cases) * ELLIPSE_ROW - (ELLIPSE_ROW - ELLIPSE_H), floor - 12) + PAD
    width = ellipse_x + ELLIPSE_W + 24 + PAD
    parts = _frame(width, bottom, f"Use-case diagram: {len(actors)} actors, {len(cases)} use cases", st)
    parts.append(f'<rect x="{ellipse_x - 24}" y="{PAD}" width="{ELLIPSE_W + 48}" height="{bottom - 2 * PAD}" rx="{st.box_radius + 4}" fill="none" '
                 f'stroke="{st.boundary}" stroke-dasharray="6 4"/>')
    parts.append(_text(ellipse_x - 10, PAD + 20, "System", 12, st.key_muted, st, "start", "bold"))
    cx = PAD + ACTOR_COLUMN // 2
    for c in cases:
        for a in c.actors:
            parts.append(f'<line x1="{cx + 15}" y1="{placed[a] + 28}" x2="{ellipse_x}" y2="{centre[c.item_id]}" stroke="{st.line}" stroke-width="{st.line_width}"/>')
    for a in actors:
        parts += _stick_figure(cx, placed[a], st)
        for i, line in enumerate(_wrap(labels.get(a) or a, 18)):
            parts.append(_text(cx, placed[a] + 76 + 13 * i, line, 11, st.title, st, "middle", st.title_weight))
    for c in cases:
        y = centre[c.item_id]
        parts.append(f'<ellipse cx="{ellipse_x + ELLIPSE_W // 2}" cy="{y}" rx="{ELLIPSE_W // 2}" ry="{ELLIPSE_H // 2}" fill="{st.case_fill}" '
                     f'stroke="{st.case_stroke}" stroke-width="{st.box_stroke_width}"/>')
        lines = _wrap(c.name, CASE_LINE_CHARS)
        for i, line in enumerate(lines):
            parts.append(_text(ellipse_x + ELLIPSE_W / 2, y + 4 - (len(lines) - 1) * 8 + 16 * i, line, 12, st.title, st, "middle", st.title_weight))
    parts.append("</svg>")
    return "".join(parts)


def _finish(svg: str) -> str | None:
    """The picture as the sanitiser would keep it, or None. A drawing the sanitiser would ALTER is not shown at all: it is not what was made."""
    if not svg:
        return None
    cleaned = sanitise_svg(svg, MAX_DIAGRAM_CHARS)
    return cleaned.svg if cleaned.ok and not cleaned.changed else None


def render_diagram(kind: str, body: str, labels: Mapping[str, str], style: str = DEFAULT) -> str | None:
    """The picture for an artefact body in one look, or None when there is nothing to draw (not a diagram artefact, no readable line, too many boxes)."""
    if kind not in KINDS or style not in STYLES:
        return None
    try:
        return _finish(draw_flow(body, labels, style) if kind == FLOW else draw_usecases(body, labels, style))
    except Exception:                                           # a picture is a convenience; the text is always there and nothing may fail to open
        return None


def render_all(kind: str, body: str, labels: Mapping[str, str]) -> dict[str, str] | None:
    """The picture in every look, or None unless every look could be drawn (the screen lets the person switch, so it needs all of them or none)."""
    pictures = {style: render_diagram(kind, body, labels, style) for style in STYLES}
    return pictures if all(pictures.values()) else None  # type: ignore[return-value]


def names_for(skills, store, project_id: str, kind: str) -> dict[str, str]:
    """The short name of every component or persona a diagram may mention, read from the latest version of the artefact that defines it.
    A diagram shows "Booking service", not "COMP-001"; if the name cannot be found the box simply shows the ID."""
    sources = {FLOW: "component_overview", USECASE: "personas"}
    key = sources.get(kind)
    skill = skills.get(key) if key else None
    if skill is None or not skill.items:
        return {}
    try:
        found = store.artefacts.list(project_id, phase_key=skill.artefact.phase_key, artefact_type=key)
        if not found or found[0].latest_version is None:
            return {}
        body = store.artefacts.get_version(project_id, found[0].id).body
        return {item.id: short_name(item.text) for item in parse_items(body, skill.items).items}
    except Exception:                                           # names are decoration: failing to find them must not stop an artefact opening
        return {}
