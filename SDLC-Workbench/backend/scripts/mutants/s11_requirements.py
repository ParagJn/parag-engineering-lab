"""Deliberate breaks for S11 (item IDs, derives-from, coverage, links, the seven requirements skills).

Run:  cd backend && python -u -m scripts.mutation_check scripts/mutants/s11_requirements.py
Every one of these should make the test suite FAIL. One that does not is a hole in the tests.

Not included, on purpose: dropping `ever.update(parsed.withdrawn)` in `history_of`. An ID can only be withdrawn
if it was in the previous version, so it is always already in `ever` through that version's own items; the
line changes nothing observable and a mutant there could never be caught.
"""
ITEMS = "app/agents/items.py"
REPLY = "app/agents/reply.py"
SKILLS = "app/agents/skills.py"
PROMPT = "app/agents/prompt.py"
RUNTIME = "app/agents/runtime.py"
REPOS = "app/repos.py"
CHECKS = "app/agents/checks.py"

MUTANTS = [
    # --- reading items
    ("an ID with the wrong prefix for its section is accepted", ITEMS, "if split_id(item_id)[0] not in allowed:", "if False:"),
    ("a list entry with no ID is not reported", ITEMS, "stray.append((names[key], rest[:SNIPPET_CHARS]))", "pass"),
    ("wrapped continuation lines are dropped", ITEMS, "        elif open_entry:\n            entries[-1].append(line.strip())", "        elif open_entry:\n            pass"),
    ("a nested bullet is glued onto the item above", ITEMS,
     'elif not line.strip() or line.lstrip().startswith("#") or _ANY_LIST_LINE.match(line):',
     'elif not line.strip() or line.lstrip().startswith("#"):'),
    ("items inside code fences are read", REPLY, "        if fence is None:\n            out.append(line)", "        if True:\n            out.append(line)"),
    ("a repeated section is read only once", REPLY,
     "if normalise_heading(h.name) == wanted]", "if normalise_heading(h.name) == wanted][:1]"),
    ("derives-from reads past the end of its sentence", ITEMS, "tail = _SENTENCE_END.split(tail, maxsplit=1)[0]", "tail = tail"),
    ("bracketed text is read as derives-from targets", ITEMS, "stripped = _BRACKETS.sub(\" \", tail)", "stripped = tail"),
    ("a bracketed source does not count as a source", ITEMS, "cited = bool(_BRACKETS.search(tail))", "cited = False"),
    ("document and memory sources become links", ITEMS,
     'if _LINKABLE.fullmatch(t) and not t.startswith(("MEM-", "DOC-")))', "if _LINKABLE.fullmatch(t))"),
    ("the withdrawn section is ignored", ITEMS,
     "    for chunk in section_bodies(body, WITHDRAWN_SECTION):\n        for rest in _entries(chunk):",
     "    for chunk in []:\n        for rest in _entries(chunk):"),
    # --- checking items
    ("a section with no items is accepted", ITEMS, "if not any(i.prefix == spec.prefix for i in parsed.items):", "if False:"),
    ("duplicate IDs are accepted", ITEMS, "if item.id in seen:", "if False:"),
    ("a gap or a wrong start in the numbering is accepted", ITEMS, "if fresh != expected:", "if False:"),
    ("an item with no derives-from is accepted", ITEMS, "if not item.has_source:", "if False:"),
    ("a derives-from an unseen ID is accepted", ITEMS, "elif target not in context.known and target not in present:", "elif False:"),
    ("an item may derive from itself", ITEMS, "if target == item.id:", "if False:"),
    ("a dropped ID need not be withdrawn", ITEMS, "for item_id in _ordered(context.current - present - withdrawn):", "for item_id in []:"),
    ("an ID can be both an item and withdrawn", ITEMS, "for item_id in _ordered(withdrawn & present):", "for item_id in []:"),
    ("an unknown ID can be withdrawn", ITEMS, "for item_id in _ordered(withdrawn - context.current - present - context.retired):", "for item_id in []:"),
    ("a retired ID can be reused", ITEMS, "reused = _ordered(present & context.retired)", "reused = []"),
    ("new numbers restart at one on a regeneration", ITEMS, "return self.highest.get(prefix, 0) + 1", "return 1"),
    # --- coverage
    ("coverage is not checked", ITEMS, "    if context.covers:\n        problems += _coverage_problems(body, parsed, context)", "    if False:\n        problems += _coverage_problems(body, parsed, context)"),
    ("a silently uncovered requirement is accepted", ITEMS, "silent = _ordered(uncovered - declared)", "silent = []"),
    ("a covered requirement may be listed as uncovered", ITEMS, "wrong = _ordered(declared - uncovered)", "wrong = []"),
    # --- skills and the linter
    ("an item prefix may equal an artefact prefix", SKILLS, "if prefix in artefact_prefixes or prefix in first_segments:", "if False:"),
    ("an item section need not be a required section", SKILLS, "if normalise_heading(section) not in required_names:", "if False:"),
    ("covers without items is accepted", SKILLS, "if covers and not specs:", "if False:"),
    ("a reserved prefix may be used for items", SKILLS, "if prefix in RESERVED_ITEM_PREFIXES:", "if False:"),
    ("two skills may share an item prefix", SKILLS, "if spec.prefix in owner:", "if False:"),
    ("covering a prefix no input holds is accepted", SKILLS, "if not holders:", "if False:"),
    ("a repeated items line is accepted", SKILLS, "if any(p == prefix for p, _ in item_specs):", "if False:"),
    ("a second covers line is accepted", SKILLS, "if covers:\n                raise SkillError(f\"{file}: only one", "if False:\n                raise SkillError(f\"{file}: only one"),
    ("too many items lines are accepted", SKILLS, "if len(item_specs) > MAX_ITEM_SPECS:", "if False:"),
    ("a bad covers prefix is accepted", SKILLS, "bad = [c for c in covers if not _ITEM_PREFIX.fullmatch(c)]", "bad = []"),
    ("a repeated covers prefix is accepted", SKILLS, "if len(set(covers)) != len(covers):", "if False:"),
    ("a lower-case item prefix is accepted", SKILLS, "if not _ITEM_PREFIX.fullmatch(prefix):", "if False:"),
    # --- the prompt
    ("the item rules are not in the prompt", PROMPT, '(f"{REPLY_RULES}\\n\\n{rules}" if rules else REPLY_RULES)', "REPLY_RULES"),
    ("the numbering start is not shown", PROMPT, 'parts.append("# Numbering\\n" + starts)', "pass"),
    ("the previous version's items are not shown", PROMPT, "    if ctx.previous:", "    if False:"),
    ("upstream item IDs are not offered as sources", PROMPT, "allowed.extend(i.id for i in upstream_items)", "pass"),
    ("the coverage rule is not in the prompt", PROMPT, "    if skill.covers:\n        lines.append(", "    if False:\n        lines.append("),
    # --- the runtime and the save
    ("item checks are not run", CHECKS, "problems = (problems + check_items(body, item_ctx))[:MAX_PROBLEMS]", "pass"),
    ("derives-from links are not saved", RUNTIME, "generation=generation, guard=still_running, links=links,", "generation=generation, guard=still_running, links=[],"),
    ("earlier versions are not read on a regeneration", RUNTIME,
     "earlier = [v.body for v in self.store.artefacts.versions(project_id, own)] if own else []", "earlier = []"),
    ("sources shown to the model are not valid derives-from targets", RUNTIME,
     "item_ctx.specs, item_ctx.covers, item_ctx.known | frozenset(prompt.allowed), item_ctx.pools,", "item_ctx.specs, item_ctx.covers, item_ctx.known, item_ctx.pools,"),
    ("the covered pool ignores upstream items", RUNTIME, "pools=upstream_pool(pairs),", "pools={},"),
    ("the generation record omits the items", RUNTIME, '"items": list(parsed.ids),', '"items": [],'),
    ("saved links forget the artefact that declared them", REPOS,
     "_insert_link(conn, project_id, from_id, to_id, kind, artefact_id, actor, clock())",
     "_insert_link(conn, project_id, from_id, to_id, kind, None, actor, clock())"),
    ("a repeated link is inserted again", REPOS, "    if existing is not None:\n        return _link(existing), False", "    if False:\n        return _link(existing), False"),
]
