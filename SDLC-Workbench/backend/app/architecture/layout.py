"""Where everything goes in an Architecture diagram (S14b, second version). Pure geometry: no drawing, no text parsing.

The first version drew a straight line between boxes, so with eight components and twenty-odd calls the lines crossed boxes and each other and the
labels piled up. This one lays the boxes out in columns that follow the flow from left to right, and routes every line at right angles through
"lanes" (narrow strips between the columns, and between the rows), so that:

  * a line never passes through a box,
  * two lines never run along the same stretch,
  * a call and its reply are ONE line with a head at each end, not two lines on top of each other,
  * each line carries a small number, which is the number of its FLOW item, and a key under the picture says what each number is.

The same list always gives the same layout. Everything here is bounded by the 12-box and 24-line limits the check enforces, and nothing raises.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

NODE_W, NODE_H = 176, 64
PAD = 28
HEAD = 9                     # length of an arrow head
LANE = 20                    # distance between two vertical lanes in a gap between columns
CHANNEL_LANE = 14            # distance between two horizontal lanes in a channel between rows
MIN_GAP = 76                 # narrowest gap between two columns
MIN_CHANNEL = 44             # smallest gap between two rows
BADGE_H = 16
KEY_COL_W = 380
KEY_ROW_H = 36
KEY_TITLE_H = 26


@dataclass(frozen=True)
class Edge:
    item_id: str
    source: str
    target: str
    label: str

    @property
    def number(self) -> int:
        return int(self.item_id.rsplit("-", 1)[1])


@dataclass(frozen=True)
class UseCase:
    item_id: str
    name: str
    actors: tuple[str, ...]


@dataclass(frozen=True)
class Box:
    key: str
    x: int
    y: int
    w: int
    h: int
    col: int
    row: int


@dataclass(frozen=True)
class Badge:
    x: int
    y: int
    w: int
    h: int
    text: str


@dataclass(frozen=True)
class Link:
    numbers: tuple[int, ...]          # the FLOW numbers this one line stands for (a call and its reply share a line)
    a: str                            # the end drawn first (the earlier column, or the upper box)
    b: str
    points: tuple[tuple[int, int], ...]   # the route from a's edge to b's edge, right angles only
    head_a: bool
    head_b: bool
    badge: Badge


@dataclass(frozen=True)
class KeyEntry:
    number: int
    source: str
    target: str
    label: str
    x: int
    y: int


@dataclass(frozen=True)
class FlowLayout:
    width: int
    height: int
    boxes: tuple[Box, ...]
    links: tuple[Link, ...]
    key: tuple[KeyEntry, ...]
    key_top: int
    diagram_bottom: int


# ---- columns ----------------------------------------------------------------------------------------------------------------------------------

def columns(order: list[str], calls: list[Edge]) -> dict[str, int]:
    """The column of each component: how far it is from where the flow starts.

    A reply (a call back along a call already written) does not count, so a request and its answer sit between the same two columns. A call that
    would close a loop is not counted either. The rest is laid out by its longest path, so the flow reads from left to right."""
    seen: set[tuple[str, str]] = set()
    requests: list[tuple[str, str]] = []
    for e in calls:
        if (e.target, e.source) in seen:
            continue
        if (e.source, e.target) not in seen:
            requests.append((e.source, e.target))
        seen.add((e.source, e.target))
    out: dict[str, list[str]] = {n: [] for n in order}
    incoming = {n: 0 for n in order}
    for s, t in requests:
        out[s].append(t)
        incoming[t] += 1

    state: dict[str, int] = {}                  # 1 while on the path being explored, 2 once done
    kept: dict[str, list[str]] = {n: [] for n in order}
    finished: list[str] = []

    def visit(n: str) -> None:
        state[n] = 1
        for t in out[n]:
            if state.get(t) == 1:
                continue                         # this call closes a loop: leave it out of the layering
            kept[n].append(t)
            if t not in state:
                visit(t)
        state[n] = 2
        finished.append(n)

    for n in [x for x in order if incoming[x] == 0] + order:
        if n not in state:
            visit(n)
    layer = {n: 0 for n in order}
    for n in reversed(finished):                 # reverse finishing order is a valid order for a graph with no loops
        for t in kept[n]:
            layer[t] = max(layer[t], layer[n] + 1)
    return layer


def rows(order: list[str], col: dict[str, int], pairs: list[tuple[str, str]]) -> dict[int, list[str]]:
    """The order of the boxes inside each column, chosen to cross fewer lines: each box moves towards the average position of its neighbours."""
    cols: dict[int, list[str]] = {}
    for n in order:
        cols.setdefault(col[n], []).append(n)
    neighbours: dict[str, set[str]] = {n: set() for n in order}
    for u, v in pairs:
        neighbours[u].add(v)
        neighbours[v].add(u)
    for forward in (True, False, True):
        for c in (sorted(cols) if forward else sorted(cols, reverse=True)):
            position = {n: i for names in cols.values() for i, n in enumerate(names)}
            written = list(cols[c])

            def centre(n: str) -> float:
                refs = [position[m] for m in neighbours[n] if (col[m] < c if forward else col[m] > c)]
                return sum(refs) / len(refs) if refs else float(position[n])

            keys = {n: (centre(n), written.index(n)) for n in written}       # every key is worked out before the list changes
            cols[c].sort(key=lambda n: keys[n])
    return cols


# ---- the layout ---------------------------------------------------------------------------------------------------------------------------------

class _Link:
    def __init__(self, index: int):
        self.index = index
        self.calls: list[Edge] = []
        self.a = ""
        self.b = ""
        self.kind = ""            # adjacent | long
        self.channel = -1
        self.chan_y = 0
        self.lane: dict[str, int] = {}     # role -> x of its vertical lane


def number_text(numbers: list[int] | tuple[int, ...], groups: int = 3) -> str:
    """The numbers on one line as short text: runs are shortened ("1–5"), and more than `groups` separate groups end in "+n". The key under the
    picture always lists every call, so a short badge loses nothing."""
    ordered = sorted(set(numbers))
    runs: list[tuple[int, int]] = []
    for n in ordered:
        if runs and n == runs[-1][1] + 1:
            runs[-1] = (runs[-1][0], n)
        else:
            runs.append((n, n))
    shown = [f"{a}" if a == b else (f"{a},{b}" if b == a + 1 else f"{a}–{b}") for a, b in runs[:groups]]
    extra = sum(b - a + 1 for a, b in runs[groups:])
    return ",".join(shown) + (f" +{extra}" if extra else "")


def _badge_w(text: str) -> int:
    return 14 + 7 * len(text)


def _spread(count: int, size: int) -> list[int]:
    return [round((i + 1) * size / (count + 1)) for i in range(count)]


def _overlaps(a: tuple[int, int, int, int], b: tuple[int, int, int, int], margin: int = 2) -> bool:
    return not (a[0] + a[2] + margin <= b[0] or b[0] + b[2] + margin <= a[0] or a[1] + a[3] + margin <= b[1] or b[1] + b[3] + margin <= a[1])


def layout_flow(calls: list[Edge], names: Mapping[str, str], badge_width=None) -> FlowLayout | None:
    """The whole layout for a list of calls, or None when there is nothing to lay out."""
    order: list[str] = []
    for e in calls:
        for n in (e.source, e.target):
            if n not in order:
                order.append(n)
    if not order:
        return None
    col = columns(order, calls)

    links: list[_Link] = []
    by_pair: dict[frozenset[str], _Link] = {}
    for e in calls:
        key = frozenset((e.source, e.target))
        link = by_pair.get(key)
        if link is None:
            link = _Link(len(links))
            by_pair[key] = link
            links.append(link)
        link.calls.append(e)
    for link in links:
        link.calls.sort(key=lambda e: e.number)

    cols = rows(order, col, [(l.calls[0].source, l.calls[0].target) for l in links])
    row = {n: i for names_in in cols.values() for i, n in enumerate(names_in)}
    for link in links:
        u, v = link.calls[0].source, link.calls[0].target
        link.a, link.b = (u, v) if col[u] < col[v] else (v, u)
        # Two boxes joined by a call are never in the same column: a call puts its target one column after its source, and a call that would close a
        # loop is joined to a box in an EARLIER column. (Checked on thousands of random designs.) So a line always runs from one column to another.
        link.kind = "adjacent" if col[link.b] == col[link.a] + 1 else "long"

    n_cols = max(col.values()) + 1
    n_rows = max(len(v) for v in cols.values())

    # which side of which box each line leaves from, so a box is tall enough to give every line its own place
    right: dict[str, list[_Link]] = {n: [] for n in order}
    left: dict[str, list[_Link]] = {n: [] for n in order}
    for link in links:
        if link.kind in ("adjacent", "long"):
            right[link.a].append(link)
            left[link.b].append(link)
    places: dict[tuple[int, int], int] = {}              # (gap, row) -> how many lines need their own height on the sides facing across that gap
    for n in order:
        places[(col[n], row[n])] = places.get((col[n], row[n]), 0) + len(right[n])
        places[(col[n] - 1, row[n])] = places.get((col[n] - 1, row[n]), 0) + len(left[n])
    height = max(NODE_H, 14 * (max(places.values(), default=1) + 1))

    # which strip each line uses: a lane in a gap between columns, and for a long line a lane in a channel between rows
    gap_use: list[list[tuple[_Link, str]]] = [[] for _ in range(n_cols)]
    chan_use: list[list[_Link]] = [[] for _ in range(n_rows + 1)]
    for link in links:
        if link.kind == "adjacent":
            gap_use[col[link.a]].append((link, "adj"))
        elif link.kind == "long":
            ra, rb = row[link.a], row[link.b]
            link.channel = ra + 1 if rb > ra else ra if rb < ra else (ra + 1 if link.index % 2 == 0 else ra)
            chan_use[link.channel].append(link)
            gap_use[col[link.a]].append((link, "leave"))
            gap_use[col[link.b] - 1].append((link, "arrive"))

    gap_w: list[int] = []
    for g in range(n_cols):
        n = len(gap_use[g])
        base = 40 + (n - 1) * LANE if n else 0
        widest = max([_badge_w(number_text([e.number for e in l.calls])) for l, role in gap_use[g] if role == "adj"] + [0])      # a short line must fit its own number
        gap_w.append(max(MIN_GAP, base, widest + 36) if g < n_cols - 1 else base)
    chan_h: list[int] = []
    for k in range(n_rows + 1):
        n = len(chan_use[k])
        if k in (0, n_rows):
            chan_h.append(2 * CHANNEL_LANE + (n - 1) * CHANNEL_LANE if n else 0)
        else:
            chan_h.append(max(MIN_CHANNEL, 2 * CHANNEL_LANE + (n - 1) * CHANNEL_LANE if n else 0))

    col_x = [PAD]
    for c in range(n_cols - 1):
        col_x.append(col_x[c] + NODE_W + gap_w[c])
    chan_y0 = [PAD]
    row_y: list[int] = []
    for r in range(n_rows):
        row_y.append(chan_y0[r] + chan_h[r])
        chan_y0.append(row_y[r] + height)

    boxes = {n: Box(n, col_x[col[n]], row_y[row[n]], NODE_W, height, col[n], row[n]) for n in order}

    # each line's own place along the side of a box. The right side of a box and the left side of the next column's box face each other across one gap,
    # and a line leaving one and a line arriving at the other would run along the same stretch if they were at the same height. So the two sides of one
    # gap in one row share a single set of places, and each line takes its own.
    port: dict[tuple[int, str], int] = {}
    facing: dict[tuple[int, int], list[tuple[_Link, str]]] = {}
    for n in order:
        for link in right[n]:
            facing.setdefault((col[n], row[n]), []).append((link, n))
        for link in left[n]:
            facing.setdefault((col[n] - 1, row[n]), []).append((link, n))
    for (_gap, r), members in facing.items():
        def rank(member: tuple[_Link, str]) -> tuple[int, int, int]:
            link, n = member
            other = link.b if n == link.a else link.a
            return (row[other], col[other], link.index)
        ordered = sorted(members, key=rank)
        for (link, n), offset in zip(ordered, _spread(len(ordered), height)):
            port[(link.index, n)] = row_y[r] + offset

    # lanes: in a gap, order the vertical stretches so that lines cross as little as they can
    def lane_x(g: int, i: int) -> int:
        return col_x[g] + NODE_W + 20 + i * LANE

    for k in range(n_rows + 1):
        for i, link in enumerate(sorted(chan_use[k], key=lambda l: l.index)):
            link.chan_y = chan_y0[k] + CHANNEL_LANE + i * CHANNEL_LANE

    for g in range(n_cols):
        straight = []
        for link, role in gap_use[g]:
            if role == "adj":
                ys, ye = port[(link.index, link.a)], port[(link.index, link.b)]
            elif role == "leave":
                ys, ye = port[(link.index, link.a)], link.chan_y
            else:
                ys, ye = link.chan_y, port[(link.index, link.b)]
            straight.append((link, role, ys, ye))
        up = sorted((s for s in straight if s[3] < s[2]), key=lambda s: (s[2], s[0].index))
        flat = sorted((s for s in straight if s[3] == s[2]), key=lambda s: s[0].index)
        down = sorted((s for s in straight if s[3] > s[2]), key=lambda s: (-s[2], s[0].index))
        placed = [(s[0], s[1]) for s in (*up, *flat, *down)]
        for i, (link, role) in enumerate(placed):
            link.lane[role] = lane_x(g, i)

    # the routes
    routes: dict[int, list[tuple[int, int]]] = {}
    for link in links:
        a, b = boxes[link.a], boxes[link.b]
        if link.kind == "adjacent":
            ya, yb = port[(link.index, link.a)], port[(link.index, link.b)]
            x = link.lane["adj"]
            pts = [(a.x + a.w, ya), (x, ya), (x, yb), (b.x, yb)]
        elif link.kind == "long":
            ya, yb = port[(link.index, link.a)], port[(link.index, link.b)]
            x1, x2, cy = link.lane["leave"], link.lane["arrive"], link.chan_y
            pts = [(a.x + a.w, ya), (x1, ya), (x1, cy), (x2, cy), (x2, yb), (b.x, yb)]
        else:
            raise AssertionError(f"a line joins two boxes of one column ({link.a}, {link.b}); columns are chosen so that cannot happen")
        routes[link.index] = _tidy(pts)

    diagram_right = col_x[-1] + NODE_W + gap_w[-1] + PAD
    diagram_bottom = chan_y0[n_rows] + chan_h[n_rows] + PAD

    # a number on each line, where it does not sit on a box, on another number, or on any OTHER line (a number on a junction reads as the wrong line's)
    box_rects = [(b.x, b.y, b.w, b.h) for b in boxes.values()]
    stretches: dict[int, list[tuple[int, int, int, int]]] = {}
    for link in links:
        pts = routes[link.index]
        stretches[link.index] = [(min(p[0], q[0]) - 1, min(p[1], q[1]) - 1, abs(p[0] - q[0]) + 2, abs(p[1] - q[1]) + 2) for p, q in zip(pts, pts[1:])]
    placed_badges: list[tuple[int, int, int, int]] = []
    out_links: list[Link] = []
    for link in links:
        text = number_text([e.number for e in link.calls])
        width = badge_width(text) if badge_width else _badge_w(text)
        pts = routes[link.index]
        segments = sorted(range(len(pts) - 1), key=lambda i: -(abs(pts[i + 1][0] - pts[i][0]) + abs(pts[i + 1][1] - pts[i][1])))
        others = [r for index, rs in stretches.items() if index != link.index for r in rs]
        chosen: tuple[int, int] | None = None
        fallback: tuple[int, int] | None = None
        for strict in (True, False):                          # first try to avoid every other line; if no place is that clear, avoid boxes and numbers only
            for i in segments:
                (x1, y1), (x2, y2) = pts[i], pts[i + 1]
                for f in (0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8, 0.1, 0.9, 0.05, 0.95, 0.15, 0.85, 0.25, 0.75, 0.35, 0.65, 0.45, 0.55):
                    cx, cy = round(x1 + (x2 - x1) * f), round(y1 + (y2 - y1) * f)
                    rect = (cx - width // 2, cy - BADGE_H // 2, width, BADGE_H)
                    fallback = fallback or (rect[0], rect[1])
                    if any(_overlaps(rect, r) for r in box_rects) or any(_overlaps(rect, r) for r in placed_badges):
                        continue
                    if strict and any(_overlaps(rect, r, 0) for r in others):
                        continue
                    chosen = (rect[0], rect[1])
                    break
                if chosen:
                    break
            if chosen:
                break
        bx, by = chosen or fallback or (pts[0][0], pts[0][1])
        placed_badges.append((bx, by, width, BADGE_H))
        targets = {e.target for e in link.calls}
        out_links.append(Link(tuple(e.number for e in link.calls), link.a, link.b, tuple(routes[link.index]), link.a in targets, link.b in targets,
                              Badge(bx, by, width, BADGE_H, text)))

    # the key under the picture
    key_columns = max(1, (max(diagram_right, 2 * PAD + KEY_COL_W) - 2 * PAD) // KEY_COL_W)
    width_total = max(diagram_right, 2 * PAD + key_columns * KEY_COL_W)
    ordered_calls = sorted(calls, key=lambda e: e.number)
    per_column = math.ceil(len(ordered_calls) / key_columns)
    key_top = diagram_bottom
    key: list[KeyEntry] = []
    for i, e in enumerate(ordered_calls):
        key.append(KeyEntry(e.number, names.get(e.source) or e.source, names.get(e.target) or e.target, e.label,
                            PAD + (i // per_column) * KEY_COL_W, key_top + KEY_TITLE_H + (i % per_column) * KEY_ROW_H))
    height_total = key_top + KEY_TITLE_H + per_column * KEY_ROW_H + PAD
    return FlowLayout(width_total, height_total, tuple(boxes[n] for n in order), tuple(out_links), tuple(key), key_top, diagram_bottom)


def _tidy(pts: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Drop a point that repeats the one before it, and a point in the middle of a straight stretch."""
    out: list[tuple[int, int]] = []
    for p in pts:
        if out and out[-1] == p:
            continue
        if len(out) >= 2 and ((out[-2][0] == out[-1][0] == p[0]) or (out[-2][1] == out[-1][1] == p[1])):
            out[-1] = p
            continue
        out.append(p)
    return out
