"""Deliberate breaks for S13 (the SVG sanitiser, its drawing check, the finder, and the Design skills' wiring).

Run:  cd backend && python -u -m scripts.mutation_check scripts/mutants/s13_design.py
Every one of these should make the test suite FAIL. One that does not is a hole in the tests. The sanitiser is the part of this product where model
output becomes live content, so it gets the most breaks.
"""
S = "app/design/sanitise.py"
C = "app/agents/checks.py"

# UNKILLABLE BY CONSTRUCTION (named here, not counted as caught, and not in the list below):
#  * "onclick is an allowed attribute": an attribute whose name starts with "on" is dropped BEFORE the allow-list is consulted, so a stray
#    "onclick" in ATTRIBUTES is never reached. (Removing the "on" check as well is a different, killable break: "an event handler is not named as one".)
#  * "a name is not required after the less-than sign": `_starts_markup` has already guaranteed a letter follows, so no extra skipping can ever run.
MUTANTS = [
    # --- the allow-list of elements
    ("script is an allowed element", S, 'ELEMENTS = frozenset({"svg", "g", "rect",', 'ELEMENTS = frozenset({"script", "svg", "g", "rect",'),
    ("a link is an allowed element", S, 'ELEMENTS = frozenset({"svg", "g", "rect",', 'ELEMENTS = frozenset({"a", "svg", "g", "rect",'),
    ("an image is an allowed element", S, 'ELEMENTS = frozenset({"svg", "g", "rect",', 'ELEMENTS = frozenset({"image", "svg", "g", "rect",'),
    ("foreignObject is an allowed element", S, 'ELEMENTS = frozenset({"svg", "g", "rect",', 'ELEMENTS = frozenset({"foreignobject", "svg", "g", "rect",'),
    ("style is an allowed element", S, 'ELEMENTS = frozenset({"svg", "g", "rect",', 'ELEMENTS = frozenset({"style", "svg", "g", "rect",'),
    ("rect is not an allowed element", S, 'ELEMENTS = frozenset({"svg", "g", "rect", "circle",', 'ELEMENTS = frozenset({"svg", "g", "circle",'),
    ("text is not kept inside a text element", S, 'TEXT_ELEMENTS = frozenset({"text", "tspan", "title", "desc"})', 'TEXT_ELEMENTS = frozenset({"tspan", "title", "desc"})'),
    # --- the allow-list of attributes
    ("href is an allowed attribute", S, '"preserveaspectratio", "xmlns",\n})', '"preserveaspectratio", "xmlns", "href",\n})'),
    ("style is an allowed attribute", S, '"preserveaspectratio", "xmlns",\n})', '"preserveaspectratio", "xmlns", "style",\n})'),
    ("fill is not an allowed attribute", S, '"fill", "fill-opacity", "stroke",', '"fill-opacity", "stroke",'),
    ("an event handler is not named as one", S, '        if name.startswith("on"):\n            report.add(f"the event handler \'{name}\' on <{element}>")\n        elif name not in ATTRIBUTES:', '        if False:\n            report.add(f"the event handler \'{name}\' on <{element}>")\n        elif name not in ATTRIBUTES:'),
    ("duplicate attributes are all kept", S, '        if name in seen:\n            continue\n        seen.add(name)', '        seen.add(name)'),
    ("attribute names are case sensitive", S, '        name = match.group(1).lower()\n        value = match.group(2)', '        name = match.group(1)\n        value = match.group(2)'),
    # --- attribute values
    ("javascript is allowed in a value", S, 'if "javascript" in lowered or "data:" in lowered', 'if False or "data:" in lowered'),
    ("data: is allowed in a value", S, 'or "data:" in lowered or', 'or'),
    ("url() is allowed in a value", S, 'or "url(" in lowered or', 'or'),
    ("an ampersand is allowed in a value", S, 'or "expression" in lowered or "&" in value:', 'or "expression" in lowered:'),
    ("the value length limit is off", S, '    if len(value) > MAX_ATTRIBUTE_CHARS:\n        return False', '    if False:\n        return False'),
    ("any xmlns is allowed", S, '        return value.strip() == SVG_NAMESPACE', '        return True'),
    ("any role is allowed", S, '        return value in ("img", "presentation", "group")', '        return True'),
    ("a path may hold anything", S, '        return bool(_PATH.match(value))', '        return True'),
    ("a transform may hold anything", S, '        return bool(_TRANSFORM.match(value))', '        return True'),
    ("plain values may hold anything", S, '        return value in ("img", "presentation", "group")\n    return bool(_PLAIN.match(value))', '        return value in ("img", "presentation", "group")\n    return True'),
    ("values are not trimmed", S, 'kept.append(f\'{canonical}="{value.strip()}"\')', 'kept.append(f\'{canonical}="{value}"\')'),
    # --- structure
    ("a removed element's children are kept", S, '            if name not in ELEMENTS:\n                report.add(f"the <{name}> element")\n                if not selfclose:\n                    skip_depth += 1\n                continue', '            if name not in ELEMENTS:\n                report.add(f"the <{name}> element")\n                continue'),
    ("content after the closing svg is kept", S, '            if finished:\n                report.add("content after the closing </svg>")\n                continue', '            if False:\n                continue'),
    ("an element before the svg is kept", S, '            if not started and name != "svg":', '            if False:'),
    ("the element count is not limited", S, '            if count > MAX_ELEMENTS:\n                report.add(f"more than {MAX_ELEMENTS} elements")\n                break', '            if False:\n                break'),
    ("the element limit is one too generous", S, '            if count > MAX_ELEMENTS:', '            if count > MAX_ELEMENTS + 1:'),
    ("nesting is not limited", S, '            if len(stack) >= MAX_DEPTH and not selfclose:', '            if False:'),
    ("the depth limit is one too generous", S, '            if len(stack) >= MAX_DEPTH and not selfclose:', '            if len(stack) >= MAX_DEPTH + 1 and not selfclose:'),
    ("comments are kept as text", S, '        if kind == "comment":\n            report.add("a comment, CDATA section, processing instruction or DOCTYPE")\n            continue', '        if kind == "comment":\n            continue'),
    ("a stray closing tag closes something", S, '            if name in stack:', '            if True:'),
    ("unclosed elements are left open", S, '    while stack:\n        out.append(f"</{stack.pop()}>")\n    result = "".join(out)', '    result = "".join(out)'),
    ("loose text outside a text element is kept", S, '            elif whole.strip():\n                report.add("loose text outside a text element")', '            elif whole.strip():\n                out.append(_escape(whole.strip()))'),
    ("text is not escaped", S, '                    out.append(_escape(content))', '                    out.append(content)'),
    ("text is escaped twice", S, '                    out.append(_escape(content))', '                    out.append(_escape(_escape(content)))'),
    ("entities are not decoded once", S, '                content = _unescape(" ".join(whole.split()))[:MAX_TEXT_CHARS].strip()', '                content = " ".join(whole.split())[:MAX_TEXT_CHARS].strip()'),
    ("entities are decoded twice", S, '    return _ENTITY.sub(lambda m: _ENTITY_CHARS[m.group(1)], text)', '    return _ENTITY.sub(lambda m: _ENTITY_CHARS[m.group(1)], _ENTITY.sub(lambda m: _ENTITY_CHARS[m.group(1)], text))'),
    ("text length is not capped", S, '[:MAX_TEXT_CHARS].strip()', '.strip()'),
    ("text is not trimmed after the cut", S, '[:MAX_TEXT_CHARS].strip()', '[:MAX_TEXT_CHARS]'),
    # --- the scanner
    ("a less-than sign always starts a tag", S, '    if nxt in ("!", "?"):\n        return True', '    return True\n    if nxt in ("!", "?"):\n        return True'),
    ("an unclosed tag keeps scanning", S, '            yield ("lt", "", "", False)\n            return', '            yield ("lt", "", "", False)\n            i += 1\n            continue'),
    ("a quoted greater-than ends the tag", S, '            elif c in "\\"\'":\n                quote = c', '            elif False:\n                quote = c'),
    ("CDATA is read as a tag", S, '        if text.startswith("<![CDATA[", i):', '        if False:'),
    ("a comment is not skipped to its end", S, '            j = text.find("-->", i + 4)\n            yield ("comment", "", "", False)\n            i = n if j < 0 else j + 3', '            yield ("comment", "", "", False)\n            i += 4'),
    # --- limits and results
    ("the input size limit is off", S, '    if len(text) > MAX_INPUT_CHARS:\n        report.add(f"the drawing is longer than {MAX_INPUT_CHARS} characters")\n        return Result("", report, False)', '    if False:\n        return Result("", report, False)'),
    ("the output size limit is off at the end", S, '    if len(result) > MAX_OUTPUT_CHARS:\n        report.add(f"a screen is limited to {MAX_OUTPUT_CHARS} characters")\n        return Result("", report, False)\n    return Result(result, report, True)', '    return Result(result, report, True)'),
    ("a non-string is processed", S, '    if not isinstance(text, str) or not text.strip():', '    if not text.strip():'),
    ("an empty drawing is ok", S, '    if not started or not result.startswith("<svg"):\n        report.add("no <svg> element")\n        return Result("", report, False)', '    if False:\n        return Result("", report, False)'),
    ("a refused drawing still returns its text", S, '        return Result("", report, False)\n    return Result(result, report, True)', '        return Result(result, report, False)\n    return Result(result, report, True)'),
    ("the report is not bounded", S, '        if what not in self.removed and len(self.removed) < 12:', '        if what not in self.removed:'),
    ("the report repeats itself", S, '        if what not in self.removed and len(self.removed) < 12:', '        if len(self.removed) < 12:'),
    ("a changed drawing does not say it changed", S, '        return bool(self.report.removed)', '        return False'),
    # --- finding drawings
    ("every code block is a drawing", S, '        if language == "svg":\n            found.append', '        if True:\n            found.append'),
    ("an svg fence is not recognised", S, '        if language == "svg":\n            found.append', '        if language == "svgx":\n            found.append'),
    ("the language is case sensitive", S, 'marker, language = match.group(2), match.group(3).lower()', 'marker, language = match.group(2), match.group(3)'),
    ("the closing fence may be shorter", S, "{{{len(marker)},}}", "{{{1},}}"),
    # --- the drawing check
    ("a changed drawing is not a problem", S, '        elif result.changed:\n            problems.append(', '        elif False:\n            problems.append('),
    ("a refused drawing is not a problem", S, '        if not result.ok:\n            why =', '        if False:\n            why ='),
    ("the problem does not name the line", S, 'problems.append(f"the drawing at line {first} contains something', 'problems.append(f"the drawing contains something'),
    ("the problem repeats the removed text", S, "({'; '.join(result.report.removed)}). Remove it", "({text[:80]}). Remove it"),
    ("more than four problems are reported", S, '    return problems[:4]', '    return problems'),
    ("no problem is reported at all", S, '    return problems[:4]', '    return []'),
    ("the check is not part of the shared body check", C, '    problems = (problems + drawing_problems(body))[:MAX_PROBLEMS]\n', ''),
    ("the drawing problems are put before the others and drop them", C, '    problems = (problems + drawing_problems(body))[:MAX_PROBLEMS]', '    problems = drawing_problems(body)[:MAX_PROBLEMS]'),
]
