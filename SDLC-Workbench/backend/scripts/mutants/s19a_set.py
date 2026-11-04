"""Deliberate breaks for S19a, part two: the whole set in one artefact (assemble, split_set, listed_files, check_instructions).

Run:
  cd backend && python -u -m scripts.mutation_check scripts/mutants/s19a_set.py --tests tests/test_instructions.py
Every one of these should make the tests FAIL. One that does not is a hole in the tests.
"""
In = "app/build/instructions.py"

MUTANTS = [
    ("the mark line must have no trailing blanks removed", In, r'FILE_MARK = re.compile(r"^=== FILE: (\S+) ===[ \t]*$")', r'FILE_MARK = re.compile(r"^=== FILE: (\S+) ===$")'),
    ("a mark name may hold spaces", In, r'FILE_MARK = re.compile(r"^=== FILE: (\S+) ===[ \t]*$")', r'FILE_MARK = re.compile(r"^=== FILE: (.+) ===[ \t]*$")'),
    ("files are not sorted", In, "    ordered = sorted(files, key=order_key)\n", "    ordered = list(files)\n"),
    ("a kept file gets a new id", In, "        if name in by_name:\n            ids[name] = by_name[name]", "        if False:\n            ids[name] = by_name[name]"),
    ("numbering ignores the highest ever used", In, "    ever = [highest, *(_numbered(i) for i in by_name.values())]", "    ever = [*(_numbered(i) for i in by_name.values()), 0]"),
    ("numbering ignores ids already in the set", In, "    ever = [highest, *(_numbered(i) for i in by_name.values())]", "    ever = [highest, 0]"),
    ("numbering restarts at zero", In, "    next_number = max(ever) + 1", "    next_number = 1"),
    ("the id is two digits", In, 'f"{ITEM_PREFIX}-{next_number:03d}"', 'f"{ITEM_PREFIX}-{next_number:02d}"'),
    ("the item prefix changes", In, 'ITEM_PREFIX = "INS"', 'ITEM_PREFIX = "BLD"'),
    ("the title falls back to nothing", In, "{title_of(text) or 'instructions'}", "{title_of(text)}"),
    ("derives are not listed", In, '(f" Derives from: {\', \'.join(derived)}" if derived else "")', '""'),
    ("the default overview is blank", In, 'overview.strip() or f"{len(ordered)} instruction file(s)', 'overview.strip() or f"{len(ordered)+1} instruction file(s)'),
    ("the overview is ignored", In, 'out = ["## Overview", overview.strip() or', 'out = ["## Overview", "" or'),
    ("coverage ignores the design", In, "if design else []", "if False else []"),
    ("coverage counts the foundation as a scenario", In, "for n in ordered if kind_of(n) == SCENARIO)]", "for n in ordered)]"),
    ("coverage says nothing when a use case is missing", In, '    out += [f"- {u} has no instruction file yet" for u in uncovered] or ["None"]', '    out += ["None"]'),
    ("withdrawn files are dropped", In, "    if gone:\n", "    if False:\n"),
    ("a withdrawn file is not sorted", In, "gone = sorted((n, i) for n, i in by_name.items() if n not in files)", "gone = [(n, i) for n, i in by_name.items() if n in files]"),
    ("the files come out without the mark", In, 'out += [f"=== FILE: {name} ===", files[name].strip("\\n"), ""]', 'out += [files[name].strip("\\n"), ""]'),
    ("the file text is altered", In, 'out += [f"=== FILE: {name} ===", files[name].strip("\\n"), ""]', 'out += [f"=== FILE: {name} ===", files[name].strip("\\n").upper(), ""]'),
    ("the body ends with blank lines", In, '    return "\\n".join(out).rstrip("\\n") + "\\n"\n\n\ndef split_set', '    return "\\n".join(out) + "\\n"\n\n\ndef split_set'),
    ("windows line ends are not read", In, '(body or "").replace("\\r\\n", "\\n").split("\\n")', '(body or "").split("\\n")'),
    ("a repeated file is accepted", In, "        if current in files:\n            problems.append", "        if False:\n            problems.append"),
    ("no files is not a problem", In, "    if not files:\n        problems.append", "    if False:\n        problems.append"),
    ("the last file is not closed", In, "        current, chunk = mark.group(1), []\n        if current in files:\n            problems.append(f\"{current} is given more than once; write each file once\")\n            current = None\n    close()\n", "        current, chunk = mark.group(1), []\n        if current in files:\n            problems.append(f\"{current} is given more than once; write each file once\")\n            current = None\n"),
    ("the files list reads the whole body", In, '    head = (body or "").split("=== FILE:", 1)[0]', '    head = body or ""'),
    ("the files list reads the second name", In, "names.append(m.group(2))", "names.append(m.group(1))"),
    ("the files list needs no id", In, r'_FILE_ITEM = re.compile(r"^\s*[-*]\s*(INS-\d{3,})', r'_FILE_ITEM = re.compile(r"^\s*[-*]\s*(\w+-\d{3,})?'),
    ("per-file problems carry no name", In, 'problems += [f"{name}: {p}" for p in check_file(', 'problems += [f"{p}" for p in check_file('),
    ("a file is checked as the wrong kind", In, "        kind = kind_of(name)\n        if kind is None:\n            continue ", "        kind = SCENARIO\n        if kind is None:\n            continue "),
    ("a tool header is not removed before checks", In, "check_file(kind, name, strip_tool(files[name]), design)", "check_file(kind, name, files[name], design)"),
    ("the files list is not compared", In, "    if files and sorted(listed) != sorted(files):", "    if False:"),
    ("a file missing from the list is not named", In, "        if missing:\n            problems.append", "        if False:\n            problems.append"),
    ("a listed file that is absent is not named", In, "        if extra:\n            problems.append", "        if False:\n            problems.append"),
    ("the set is not checked as a whole", In, "    problems += check_set(files, design)\n    seen", "    seen"),
    ("repeated sentences are kept", In, "        if p not in seen:\n            seen.append(p)", "        seen.append(p)"),
    ("the title ignores blank lines before it", In, "        if line.strip():\n            return line[2:].strip() if line.startswith(\"# \") else \"\"", "        if True:\n            return line[2:].strip() if line.startswith(\"# \") else \"\""),
    ("derives repeats are kept", In, "found += [i for i in ids_in(m.group(1)) if i not in found]", "found += ids_in(m.group(1))"),
    ("derives are read from the whole file", In, 'for section in section_bodies(text, "Traceability"):', "for section in [text]:"),
]
