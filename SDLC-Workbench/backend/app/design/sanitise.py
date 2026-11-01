"""Make a model-drawn SVG safe to show, by keeping only what a wireframe is made of.

A wireframe is model output that the browser will DRAW, which is the one place in this product where text becomes live content. So this is an
allow-list, not a block-list: anything not named here is dropped, including things nobody has thought of yet. It never raises and never returns
more than it was given.

What survives: a fixed set of drawing elements, with a fixed set of presentation attributes whose values contain only plain characters. What
does not: scripts, event handlers, styles, links, images, embedded documents, external references (`url(...)`, `href`, `xlink:`), comments,
CDATA, processing instructions, DOCTYPE and entity tricks.

The TypeScript twin in frontend/src/lib/svg.ts implements the same rules. A shared corpus (scripts/export_contract.py writes it) is run through
both, and a test fails if they disagree on any case.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---- the allow-list -------------------------------------------------------------------------------------------------------------------

ELEMENTS = frozenset({"svg", "g", "rect", "circle", "ellipse", "line", "polyline", "polygon", "path", "text", "tspan", "title", "desc"})
# Elements whose CONTENT is text. Their text is kept (escaped); on any other element, stray text is dropped.
TEXT_ELEMENTS = frozenset({"text", "tspan", "title", "desc"})
ATTRIBUTES = frozenset({
    "x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "r", "rx", "ry", "width", "height", "points", "d", "transform", "viewbox",
    "fill", "fill-opacity", "stroke", "stroke-width", "stroke-opacity", "stroke-dasharray", "stroke-linecap", "stroke-linejoin", "opacity",
    "font-family", "font-size", "font-weight", "font-style", "text-anchor", "dominant-baseline", "class", "role", "aria-label",
    "preserveaspectratio", "xmlns",
})
# The only xmlns a drawing may declare.
SVG_NAMESPACE = "http://www.w3.org/2000/svg"

# ---- the limits -----------------------------------------------------------------------------------------------------------------------

MAX_INPUT_CHARS = 200_000
MAX_OUTPUT_CHARS = 12_000          # one screen: the limit for anything a MODEL drew
MAX_DIAGRAM_CHARS = 60_000         # the most a caller may ask for: the server's own diagrams (S14b), which carry a key and are bigger than one screen
MAX_ELEMENTS = 400
MAX_DEPTH = 12
MAX_ATTRIBUTE_CHARS = 2_000
MAX_TEXT_CHARS = 400

# A value is plain if it is made only of these characters. That excludes `(` `)` `;` `:` `\` `<` `>` `"` `'` `&` `{` `}` `/` `@` and
# so on: no function call, no url(), no scheme, no entity, no escape. A colour like #fff, a number list, a transform written with
# parentheses is the one exception, handled by `_TRANSFORM`, and a path is handled by `_PATH`.
_PLAIN = re.compile(r"^[A-Za-z0-9 .,#%\-_+]*$")
_PATH = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz0-9 .,\-+eE]*$")
_TRANSFORM = re.compile(r"^(?:\s*(?:translate|scale|rotate|skewX|skewY)\(\s*-?[0-9.]+(?:[ ,]+-?[0-9.]+){0,2}\s*\)\s*)*$")
_CLASS = re.compile(r"^[A-Za-z0-9 _\-]*$")
_LABEL = re.compile(r"^[A-Za-z0-9 .,!?'\-_:()/&]*$")        # aria-label is read aloud, never interpreted
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9:_-]*$")


@dataclass
class Report:
    """What was removed, in words fit to send back to a model. Never contains the removed text itself."""
    removed: list[str] = field(default_factory=list)

    def add(self, what: str) -> None:
        if what not in self.removed and len(self.removed) < 12:
            self.removed.append(what)


@dataclass(frozen=True)
class Result:
    svg: str
    report: Report
    ok: bool        # False if nothing usable was left (no <svg> root), or the input was too large to look at

    @property
    def changed(self) -> bool:
        return bool(self.report.removed)


# ---- a tolerant tokenizer ---------------------------------------------------------------------------------------------------------------
# Written as a single left-to-right scan, not a regular expression. The first version used one big regex with alternations, and an unclosed
# repeated tag ("<g <g <g ...") made it backtrack quadratically: 12,000 characters took a second, 24,000 took four. This same function runs in
# the browser, where that would freeze the tab, so every character here is looked at a bounded number of times.

_ATTR = re.compile(r"([^\s=/\"'<>]+)(?:\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s\"'=<>`]+))?")
_NAME_START = re.compile(r"[A-Za-z]")


def _starts_markup(text: str, i: int) -> bool:
    """Does the '<' at `i` begin a tag, comment, CDATA, DOCTYPE or processing instruction? A '<' followed by a space or a digit does not: it is a
    less-than sign in text ("a < b"), and stays in the text."""
    nxt = text[i + 1:i + 2]
    if nxt in ("!", "?"):
        return True
    if nxt == "/":
        return bool(_NAME_START.match(text[i + 2:i + 3] or " "))
    return bool(_NAME_START.match(nxt or " "))


def _scan(text: str):
    """Yield ('comment'|'open'|'close'|'text'|'lt', name, raw_attributes, self_closing) for each piece of `text`. Linear in its length."""
    n = len(text)
    i = 0
    while i < n:
        if text[i] != "<" or not _starts_markup(text, i):
            j = i + 1
            while j < n and not (text[j] == "<" and _starts_markup(text, j)):
                j += 1
            yield ("text", text[i:j], "", False)
            i = j
            continue
        if text.startswith("<!--", i):
            j = text.find("-->", i + 4)
            yield ("comment", "", "", False)
            i = n if j < 0 else j + 3
            continue
        if text.startswith("<![CDATA[", i):
            j = text.find("]]>", i + 9)
            yield ("comment", "", "", False)
            i = n if j < 0 else j + 3
            continue
        if text.startswith("<?", i) or text.startswith("<!", i):
            j = text.find(">", i + 2)
            yield ("comment", "", "", False)
            i = n if j < 0 else j + 1
            continue
        # `_starts_markup` has already checked that a name follows '<' or '</' (HTML allows no space there, so "a < b" is text, not a tag that
        # swallows what follows), so the name below always has at least one letter.
        closing = text[i + 1] == "/"
        k = i + (2 if closing else 1)
        m = k
        while m < n and text[m] not in " \t\r\n\f/>":
            m += 1
        name = text[k:m]
        # the rest of the tag, up to the first '>' that is not inside a quoted value
        q = m
        quote = ""
        while q < n:
            c = text[q]
            if quote:
                if c == quote:
                    quote = ""
            elif c in "\"'":
                quote = c
            elif c == ">":
                break
            q += 1
        if q >= n:
            # A tag that is never closed. Looking for its '>' ran to the end of the text, so no later '<' can find one either: the rest is
            # not markup. Reporting it once and stopping here is what keeps this linear; carrying on one character at a time would rescan
            # the whole tail for every '<' left, which is quadratic (12,000 characters of "<g <g <g" took a second).
            yield ("lt", "", "", False)
            return
        inner = text[m:q]
        selfclose = inner.rstrip().endswith("/")
        if closing:
            yield ("close", name, "", False)
        else:
            yield ("open", name, inner[:-1] if selfclose else inner, selfclose)
        i = q + 1


def _value_ok(name: str, value: str) -> bool:
    if len(value) > MAX_ATTRIBUTE_CHARS:
        return False
    lowered = value.lower()
    if "javascript" in lowered or "data:" in lowered or "vbscript" in lowered or "url(" in lowered or "expression" in lowered or "&" in value:
        return False
    if name == "d":
        return bool(_PATH.match(value))
    if name == "transform":
        return bool(_TRANSFORM.match(value))
    if name == "class":
        return bool(_CLASS.match(value))
    if name == "aria-label":
        return bool(_LABEL.match(value))
    if name == "xmlns":
        return value.strip() == SVG_NAMESPACE
    if name == "role":
        return value in ("img", "presentation", "group")
    return bool(_PLAIN.match(value))


_ENTITY = re.compile(r"&(amp|lt|gt|quot|apos);")
_ENTITY_CHARS = {"amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'"}


def _unescape(text: str) -> str:
    """The five named entities, decoded in ONE pass (so "&amp;lt;" becomes the text "&lt;", not "<"). Anything else, numeric entities
    included, stays as literal characters: it is shown as typed, never interpreted."""
    return _ENTITY.sub(lambda m: _ENTITY_CHARS[m.group(1)], text)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _attributes(raw: str, element: str, report: Report) -> str:
    kept: list[str] = []
    seen: set[str] = set()
    for match in _ATTR.finditer(raw):
        name = match.group(1).lower()
        value = match.group(2)
        value = "" if value is None else value[1:-1] if value[:1] in "\"'" and value[-1:] == value[:1] and len(value) >= 2 else value
        if name in seen:
            continue
        seen.add(name)
        if name.startswith("on"):
            report.add(f"the event handler '{name}' on <{element}>")
        elif name not in ATTRIBUTES:
            report.add(f"the attribute '{name}' on <{element}>")
        elif not _value_ok(name, value):
            report.add(f"an unsafe value for '{name}' on <{element}>")
        else:
            canonical = "viewBox" if name == "viewbox" else "preserveAspectRatio" if name == "preserveaspectratio" else name
            kept.append(f'{canonical}="{value.strip()}"')
    return (" " + " ".join(kept)) if kept else ""


def sanitise_svg(text: str, max_output: int = MAX_OUTPUT_CHARS) -> Result:
    """The drawing with everything not on the allow-list removed. Never raises; the output is never larger than the input.

    `max_output` is how large the cleaned drawing may be. A model's drawing always gets the default; only the server's own diagrams ask for more, and
    no caller can ask for more than MAX_DIAGRAM_CHARS. Every other rule (elements, depth, attributes, text) is the same whatever the limit."""
    limit = max(1, min(int(max_output), MAX_DIAGRAM_CHARS))
    report = Report()
    if not isinstance(text, str) or not text.strip():
        return Result("", report, False)
    if len(text) > MAX_INPUT_CHARS:
        report.add(f"the drawing is longer than {MAX_INPUT_CHARS} characters")
        return Result("", report, False)

    out: list[str] = []
    stack: list[str] = []
    count = 0
    started = False
    finished = False
    skip_depth = 0                         # inside an element we dropped: its whole subtree goes with it
    for kind, a, raw_attrs, selfclose in _scan(text):
        whole = a if kind == "text" else ""
        close_name = a if kind == "close" else None
        open_name = a if kind == "open" else None
        if kind == "comment":
            report.add("a comment, CDATA section, processing instruction or DOCTYPE")
            continue
        if open_name is not None:
            name = open_name.lower()
            if skip_depth:
                if not selfclose:
                    skip_depth += 1
                continue
            if finished:
                report.add("content after the closing </svg>")
                continue
            if not started and name != "svg":
                report.add(f"<{name}> before the <svg> element")
                if not selfclose:
                    skip_depth += 1
                continue
            if name not in ELEMENTS:
                report.add(f"the <{name}> element")
                if not selfclose:
                    skip_depth += 1
                continue
            count += 1
            if count > MAX_ELEMENTS:
                report.add(f"more than {MAX_ELEMENTS} elements")
                break
            if len(stack) >= MAX_DEPTH and not selfclose:
                report.add(f"nesting deeper than {MAX_DEPTH}")
                skip_depth += 1
                continue
            started = True
            out.append(f"<{name}{_attributes(raw_attrs, name, report)}" + (" />" if selfclose else ">"))
            if not selfclose:
                stack.append(name)
            elif not stack:
                finished = True
        elif close_name is not None:
            name = close_name.lower()
            if skip_depth:
                skip_depth -= 1
                continue
            if name in stack:
                while stack:
                    top = stack.pop()
                    out.append(f"</{top}>")
                    if top == name:
                        break
                if not stack and started:
                    finished = True
            else:
                report.add(f"a stray closing </{name}>")
        elif kind == "lt":
            report.add("a stray '<'")
        else:
            if skip_depth or finished:
                continue
            if stack and stack[-1] in TEXT_ELEMENTS:
                # whitespace folded, entities decoded, THEN cut and trimmed, THEN escaped: a second pass over the output finds exactly this text.
                content = _unescape(" ".join(whole.split()))[:MAX_TEXT_CHARS].strip()
                if content:
                    out.append(_escape(content))
            elif whole.strip():
                report.add("loose text outside a text element")

    while stack:
        out.append(f"</{stack.pop()}>")
    result = "".join(out)
    if not started or not result.startswith("<svg"):
        report.add("no <svg> element")
        return Result("", report, False)
    if len(result) > limit:
        report.add(f"a screen is limited to {limit} characters")
        return Result("", report, False)
    return Result(result, report, True)


# ---- finding drawings in a Markdown body ---------------------------------------------------------------------------------------------------

_OPEN_FENCE = re.compile(r"^(\s{0,3})(`{3,}|~{3,})[ \t]*([A-Za-z0-9_+-]*)[ \t]*$")


def drawings_in(body: str) -> list[tuple[int, int, str]]:
    """Every fenced block tagged `svg`: (first line, last line, text), 1-based. Other code blocks are not drawings."""
    lines = body.split("\n")
    found: list[tuple[int, int, str]] = []
    i = 0
    while i < len(lines):
        match = _OPEN_FENCE.match(lines[i])
        if not match:
            i += 1
            continue
        marker, language = match.group(2), match.group(3).lower()
        j = i + 1
        while j < len(lines) and not re.match(rf"^\s{{0,3}}{re.escape(marker[0])}{{{len(marker)},}}\s*$", lines[j]):
            j += 1
        if language == "svg":
            found.append((i + 1, j + 1, "\n".join(lines[i + 1:j])))
        i = j + 1
    return found


def drawing_problems(body: str) -> list[str]:
    """Plain sentences about every drawing that is not safe as written. [] means each is already exactly what the sanitiser would keep.

    A drawing is a problem if sanitising changes it or leaves nothing: the model is told what to remove and asked to redraw, instead of
    having its picture quietly altered. The sentences name the element or attribute, never the removed text."""
    problems: list[str] = []
    for first, _last, text in drawings_in(body):
        result = sanitise_svg(text)
        if not result.ok:
            why = "; ".join(result.report.removed) or "it is not a drawing"
            problems.append(f"the drawing at line {first} cannot be shown: {why}. Draw it again using only <svg>, <g>, <rect>, <circle>, <ellipse>, <line>, <polyline>, <polygon>, <path>, <text>, <tspan>, <title> and <desc>")
        elif result.changed:
            problems.append(f"the drawing at line {first} contains something not allowed in a wireframe ({'; '.join(result.report.removed)}). Remove it and keep only plain shapes and text")
    return problems[:4]
