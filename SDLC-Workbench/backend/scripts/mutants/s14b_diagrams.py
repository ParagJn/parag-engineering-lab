"""Deliberate breaks for S14b (the diagram parser, check, drawing and wiring).

Run:  cd backend && python -u -m scripts.mutation_check scripts/mutants/s14b_diagrams.py --tests tests/test_architecture_diagram.py tests/test_architecture_phase.py tests/test_agent_skills.py
Every one of these should make the tests FAIL. One that does not is a hole in the tests.
"""
D = "app/architecture/diagram.py"
L = "app/architecture/layout.py"
S = "app/design/sanitise.py"
C = "app/agents/checks.py"
R = "app/routes_artefacts.py"

MUTANTS = [
    # --- limits
    ("the node limit is one too generous", D, "MAX_NODES = 12 ", "MAX_NODES = 13 "),
    ("the node limit is one too strict", D, "MAX_NODES = 12 ", "MAX_NODES = 11 "),
    ("the line limit is one too generous", D, "MAX_LINES = 24 ", "MAX_LINES = 25 "),
    ("nodes are counted with a greater-or-equal", D, "        if len(nodes) > MAX_NODES:", "        if len(nodes) >= MAX_NODES:"),
    ("arrows are counted with a greater-or-equal", D, "        if len(edges) > MAX_LINES:", "        if len(edges) >= MAX_LINES:"),
    ("use-case boxes are counted without the actors", D, "    if len(actors) + len(cases) > MAX_NODES:\n        problems.append", "    if len(cases) > MAX_NODES:\n        problems.append"),
    ("a use-case diagram over the limit is still drawn", D, "    if not cases or len(actors) + len(cases) > MAX_NODES:\n        return \"\"", "    if not cases:\n        return \"\""),
    # --- reading
    ("an arrow written with a unicode arrow is not read", D, "(?:->|→|—>|-->)", "(?:->|-->)"),
    ("an arrow with no label is accepted", D, "if match is None or not match.group(\"label\").strip():", "if match is None:"),
    ("a use case is named by the whole sentence", D, '.split(":", 1)[0].split())', '.split())'),
    ("every ID after Derives from is an actor", D, "tuple(t for t in item.derives if _PERSONA.match(t))", "tuple(item.derives)"),
    ("the short name keeps the whole text", D, '    head = re.split(r"[:;,.]| - | — ", text.strip(), maxsplit=1)[0].strip()', '    head = text.strip()'),
    ("the short name is not cut", D, "    return head if len(head) <= limit else head[: limit - 1].rstrip() + \"…\"\n\n\ndef _clip", "    return head\n\n\ndef _clip"),
    # --- the check
    ("an unknown component is accepted", D, "if not _COMPONENT.match(end) or end not in known:", "if not _COMPONENT.match(end):"),
    ("a requirement is accepted as a component", D, "if not _COMPONENT.match(end) or end not in known:", "if end not in known:"),
    ("a call to itself is accepted", D, "            if edge.source == edge.target:\n                problems.append", "            if False:\n                problems.append"),
    ("an unreadable line is accepted", D, "        for item_id in unreadable:\n            problems.append", "        for item_id in []:\n            problems.append"),
    ("an unknown actor is accepted", D, "            if actor not in known:\n                problems.append", "            if False:\n                problems.append"),
    ("a use case with no actor is accepted", D, "        if not case.actors:\n            problems.append", "        if False:\n            problems.append"),
    ("a use case with no requirement is accepted", D, "        if not any(_REQUIREMENT.match(t) for t in item.derives):", "        if False:"),
    ("a requirement is only FR, not NFR", D, '_REQUIREMENT = re.compile(r"^(?:FR|NFR)-\\d{3,}$")', '_REQUIREMENT = re.compile(r"^(?:FR)-\\d{3,}$")'),
    ("a use case with no name is accepted", D, "        if not case.name:\n            problems.append", "        if False:\n            problems.append"),
    ("the same problem is reported many times", D, "    return [p for p in problems if not (p in seen or seen.add(p))]", "    return problems"),
    ("another artefact is checked as a diagram", D, "    if kind not in KINDS:\n        return []\n    items = _items(kind, body)", "    items = _items(kind, body)"),
    # --- the drawing
    ("the label text is not escaped", D, "{_esc(text)}</text>')", "{text}</text>')"),
    ("each actor is joined to every use case", D, "        for a in c.actors:\n            parts.append(f'<line", "        for a in actors:\n            parts.append(f'<line"),
    ("an error while drawing is raised", D, "    except Exception:                                           # a picture is a convenience; the text is always there and nothing may fail to open\n        return None", "    except ZeroDivisionError:\n        return None"),
    ("a name that cannot be found stops the artefact", D, "    except Exception:                                           # names are decoration: failing to find them must not stop an artefact opening\n        return {}", "    except ZeroDivisionError:\n        return {}"),
    # --- wiring
    ("the diagram check is not part of the shared body check", C, "        problems = (problems + diagram_problems(skill.key, body, item_ctx.known))[:MAX_PROBLEMS]\n", ""),
    ("the diagram check drops the other problems", C, "        problems = (problems + diagram_problems(skill.key, body, item_ctx.known))[:MAX_PROBLEMS]", "        problems = diagram_problems(skill.key, body, item_ctx.known)[:MAX_PROBLEMS]"),

    # --- limits and wording of the second version
    ("the name limit is off", D, "MAX_NAME_CHARS = 40\n", "MAX_NAME_CHARS = 90\n"),
    ("the box name wraps at the wrong width", D, "NAME_LINE_CHARS = 22 ", "NAME_LINE_CHARS = 60 "),
    ("the key sentence is not clipped", D, "KEY_LABEL_CHARS = 62 ", "KEY_LABEL_CHARS = 6000 "),
    ("a diagram over the box limit is still drawn", D, "    if layout is None or len(layout.boxes) > MAX_NODES:\n        return \"\"", "    if layout is None:\n        return \"\""),
    ("a use-case name wraps at the wrong width", D, "CASE_LINE_CHARS = 26", "CASE_LINE_CHARS = 90"),
    ("a box name is not escaped", D, "fill}\">{_esc(text)}</text>')\n\n\ndef _head_points", "fill}\">{text}</text>')\n\n\ndef _head_points"),
    ("an unknown look is drawn", D, "    if kind not in KINDS or style not in STYLES:\n        return None", "    if kind not in KINDS:\n        return None"),
    ("render_all gives some looks when one fails", D, "    return pictures if all(pictures.values()) else None", "    return {k: v for k, v in pictures.items() if v} or None"),
    ("the picture is cleaned with the one-screen limit", D, "    cleaned = sanitise_svg(svg, MAX_DIAGRAM_CHARS)", "    cleaned = sanitise_svg(svg)"),
    ("a picture the sanitiser alters is still returned", D, "    return cleaned.svg if cleaned.ok and not cleaned.changed else None\n\n\ndef render_diagram", "    return svg\n\n\ndef render_diagram"),
    ("the heads are drawn at the wrong end", D, "        if link.head_b:\n            parts.append(f'<polygon points=\"{_head_points(link.points[-1], link.points[-2])}\"", "        if link.head_a:\n            parts.append(f'<polygon points=\"{_head_points(link.points[-1], link.points[-2])}\""),
    ("a two-way line has one head", D, "        if link.head_a:\n            parts.append(f'<polygon points=\"{_head_points(link.points[0], link.points[1])}\"", "        if False:\n            parts.append(f'<polygon points=\"{_head_points(link.points[0], link.points[1])}\""),
    ("the key is not drawn", D, "    for entry in layout.key:\n", "    for entry in []:\n"),
    ("the actors are drawn on the right", D, "    cx = PAD + ACTOR_COLUMN // 2\n", "    cx = PAD + ACTOR_COLUMN // 2 + 700\n"),
    ("the system box is not drawn", D, "    parts.append(f'<rect x=\"{ellipse_x - 24}\" y=\"{PAD}\"", "    _ = (f'<rect x=\"{ellipse_x - 24}\" y=\"{PAD}\""),
    ("a single actor divides by zero", D, "wanted = {a: sum(centre[c.item_id] for c in cases if a in c.actors) / max(1, sum(1 for c in cases if a in c.actors)) for a in actors}", "wanted = {a: sum(centre[c.item_id] for c in cases if a in c.actors) / sum(1 for c in cases if a in c.actors if False) for a in actors}"),
    ("actors may overlap each other", D, "        floor = y + ACTOR_H\n", "        floor = y\n"),
    ("a stick figure has no legs", D, "            f'<line x1=\"{cx}\" y1=\"{top + 42}\" x2=\"{cx - 12}\" y2=\"{top + 60}\" {ink}/>',\n", ""),
    # --- the layout
    ("every box is in column zero", L, "    layer = {n: 0 for n in order}\n    for n in reversed(finished):", "    layer = {n: 0 for n in order}\n    for n in []:"),
    ("a reply moves its component a column on", L, "        if (e.target, e.source) in seen:\n            continue", "        if False:\n            continue"),
    ("a call that closes a loop is layered", L, "            if state.get(t) == 1:\n                continue                         # this call closes a loop: leave it out of the layering", "            if False:\n                continue"),
    ("a component goes after the shortest path", L, "            layer[t] = max(layer[t], layer[n] + 1)", "            layer[t] = layer[n] + 1"),
    ("boxes are not ordered to cross less", L, "            cols[c].sort(key=lambda n: keys[n])", "            pass"),
    ("boxes are ordered by the wrong key", L, "keys = {n: (centre(n), written.index(n)) for n in written}", "keys = {n: (-centre(n), written.index(n)) for n in written}"),
    ("ties are broken in reverse", L, "keys = {n: (centre(n), written.index(n)) for n in written}", "keys = {n: (centre(n), -written.index(n)) for n in written}"),
    ("a call and its reply are two lines", L, "        key = frozenset((e.source, e.target))", "        key = (e.source, e.target, e.item_id)"),
    ("a box is not made taller for its lines", L, "    height = max(NODE_H, 14 * (max(places.values(), default=1) + 1))", "    height = NODE_H"),
    ("the two sides of a gap do not share places", L, "            facing.setdefault((col[n] - 1, row[n]), []).append((link, n))", "            facing.setdefault((col[n] - 1, row[n], n), []).append((link, n))"),
    ("lines in a gap use one lane", L, "        return col_x[g] + NODE_W + 20 + i * LANE", "        return col_x[g] + NODE_W + 20"),
    ("a long line uses one channel lane", L, "            link.chan_y = chan_y0[k] + CHANNEL_LANE + i * CHANNEL_LANE", "            link.chan_y = chan_y0[k] + CHANNEL_LANE"),
    ("a gap is not widened for its lines", L, "        gap_w.append(max(MIN_GAP, base, widest + 36) if g < n_cols - 1 else base)", "        gap_w.append(MIN_GAP if g < n_cols - 1 else 0)"),
    ("a gap is not widened for its number", L, "        gap_w.append(max(MIN_GAP, base, widest + 36) if g < n_cols - 1 else base)", "        gap_w.append(max(MIN_GAP, base) if g < n_cols - 1 else base)"),
    ("numbers are not shortened to runs", L, "        if runs and n == runs[-1][1] + 1:", "        if False:"),
    ("the number of groups is not limited", L, "    shown = [f\"{a}\" if a == b else (f\"{a},{b}\" if b == a + 1 else f\"{a}–{b}\") for a, b in runs[:groups]]", "    shown = [f\"{a}\" if a == b else (f\"{a},{b}\" if b == a + 1 else f\"{a}–{b}\") for a, b in runs]"),
    ("a number may sit on a box", L, "                    if any(_overlaps(rect, r) for r in box_rects) or any(_overlaps(rect, r) for r in placed_badges):\n                        continue", "                    pass"),
    ("the key is in one column", L, "    key_columns = max(1, (max(diagram_right, 2 * PAD + KEY_COL_W) - 2 * PAD) // KEY_COL_W)", "    key_columns = 1"),
    ("the key is out of order", L, "    ordered_calls = sorted(calls, key=lambda e: e.number)", "    ordered_calls = list(reversed(sorted(calls, key=lambda e: e.number)))"),
    ("a line ends away from its box", L, "            pts = [(a.x + a.w, ya), (x, ya), (x, yb), (b.x, yb)]", "            pts = [(a.x + a.w + 10, ya), (x, ya), (x, yb), (b.x, yb)]"),
    # --- the larger limit
    ("the cap on the larger limit is off", S, "    limit = max(1, min(int(max_output), MAX_DIAGRAM_CHARS))", "    limit = max(1, int(max_output))"),
    ("the default limit is the larger one", S, "def sanitise_svg(text: str, max_output: int = MAX_OUTPUT_CHARS) -> Result:", "def sanitise_svg(text: str, max_output: int = MAX_DIAGRAM_CHARS) -> Result:"),
    ("the limit is ignored", S, "    if len(result) > limit:", "    if len(result) > MAX_DIAGRAM_CHARS:"),
    # --- wiring
    ("the artefact detail has no pictures", R, '        "renderings": _renderings(request, store, project_id, artefact.type, shown.body),\n', ""),
    ("the pictures are drawn from the latest text, not the shown version", R, "_renderings(request, store, project_id, artefact.type, shown.body)", "_renderings(request, store, project_id, artefact.type, store.artefacts.get_version(project_id, artefact_id).body)"),
]
