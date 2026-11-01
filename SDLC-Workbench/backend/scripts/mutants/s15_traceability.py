"""Deliberate breaks for S15 (traceability: the graph, the rules, the five gaps, the chain table, the route, the CSV, the approval).

Run:  cd backend && python -u -m scripts.mutation_check scripts/mutants/s15_traceability.py --tests tests/test_traceability.py tests/test_contract_fixtures.py
Every one of these should make the tests FAIL. One that does not is a hole in the tests.
"""
T = "app/trace/traceability.py"
G = "app/trace/gather.py"
R = "app/routes_trace.py"
H = "app/review/human.py"

# Removed after the first sweep, with the code they broke:
#  * "the walk has no bound" / "...one too many": the bound is enforced inside the loop; the outer test of it could never be what stops a walk. The inner one is tested.
#  * "an artefact with no items is read": a skill with no items parses to nothing, so skipping it by hand changes no result.
#  * "the name is cut too long": names are already made at most 60 characters where they are read; the route's second cut could never act.
#  * "a phase counts as started when it is only planned": the mutant text was not valid Python. Replaced below by a break that is.
MUTANTS = [
    # --- the graph
    ("a link is read the wrong way round", T, "        up[source].append(target)\n        down[target].append(source)", "        up[target].append(source)\n        down[source].append(target)"),
    ("a self link is kept", T, "        if source == target:\n            continue\n", ""),
    ("duplicate links are kept", T, "    for source, target in dict.fromkeys(links):", "    for source, target in links:"),
    ("the walk lists an item again", T, "                if nxt not in seen:\n                    seen.add(nxt)\n                    found.add(nxt)", "                if True:\n                    found.add(nxt)"),
    ("equal-distance items follow the order the links were made", T, "        following = sorted(found, key=sort_key)", "        following = list(found)"),
    ("equal-distance items sort by number before kind", T, "def sort_key(item_id: str) -> tuple[str, int]:\n    return (prefix_of(item_id), number_of(item_id))", "def sort_key(item_id: str) -> tuple[int, str]:\n    return (number_of(item_id), prefix_of(item_id))"),
    ("a loop is not found", T, "                if state.get(child) == 1:\n                    on_loop.update(path[path.index(child):])", "                if state.get(child) == 1:\n                    pass"),
    ("a prefix keeps only its first part", T, '    return item_id.rsplit("-", 1)[0]', '    return item_id.split("-", 1)[0]'),
    # --- the columns
    ("a column is chosen from what a skill covers, not what it reads", T, "            if frontier & set(rule.reads):", "            if frontier & set(rule.covers):"),
    ("columns ignore the phase", T, "    return tuple(sorted(depth, key=lambda p: (rank.get(holder_phase.get(p, \"\"), 99), depth[p], listed.get(p, 0))))", "    return tuple(sorted(depth, key=lambda p: (depth[p], listed.get(p, 0))))"),
    ("columns ignore the distance", T, "(rank.get(holder_phase.get(p, \"\"), 99), depth[p], listed.get(p, 0))", "(rank.get(holder_phase.get(p, \"\"), 99), 0, listed.get(p, 0))"),
    ("a column nothing is built on is kept", T, "    never = {p for p in order if holders_phase.get(p) in started and chains and all(not c.layers[p] for c in chains)}", "    never = set()"),
    ("a column nothing is built on in a phase not started is dropped", T, "    never = {p for p in order if holders_phase.get(p) in started and chains and", "    never = {p for p in order if chains and"),
    # --- the five gaps
    ("an uncovered item is never reported", T, "            else:\n                add(NOT_COVERED, item, by=rule.artefact)", "            else:\n                pass"),
    ("an artefact not written yet is blamed", T, "            if prefix not in rule.covers or rule.artefact not in exists:", "            if prefix not in rule.covers:"),
    ("any item derived from counts as covering", T, "            if any(prefix_of(d) in rule.holds for d in down.get(item.id, ())):", "            if down.get(item.id):"),
    ("a reason given to one artefact excuses all", T, "            if (rule.artefact, item.id) in declared:\n                add(DECLARED, item, reason=declared[(rule.artefact, item.id)], by=rule.artefact)", "            if any(i == item.id for _, i in declared):\n                add(DECLARED, item, reason=next(r for (_, i), r in declared.items() if i == item.id), by=rule.artefact)"),
    ("a declared gap is needs attention", T, '        return "explained" if self.kind in EXPLAINED else "needs_attention"', '        return "needs_attention"'),
    ("a declared gap is not reported", T, "                add(DECLARED, item, reason=declared[(rule.artefact, item.id)], by=rule.artefact)", "                pass"),
    ("a first-layer kind is built on nothing", T, "        if prefix not in first and not up.get(item.id):", "        if not up.get(item.id):"),
    ("nothing is ever built on nothing", T, "        if prefix not in first and not up.get(item.id):\n            add(BUILT_ON_NOTHING, item)", "        if False:\n            add(BUILT_ON_NOTHING, item)"),
    ("a withdrawn target is not reported", T, "                if by_id[target].withdrawn:\n                    add(WITHDRAWN_TARGET, item, other=target)", "                if False:\n                    add(WITHDRAWN_TARGET, item, other=target)"),
    ("a missing target is not reported", T, "            elif target not in artefacts and not target.startswith((\"DOC-\", \"MEM-\")):\n                add(MISSING_TARGET, item, other=target)", "            elif False:\n                add(MISSING_TARGET, item, other=target)"),
    ("a whole artefact counts as missing", T, "            elif target not in artefacts and not target.startswith((\"DOC-\", \"MEM-\")):", "            elif not target.startswith((\"DOC-\", \"MEM-\")):"),
    ("a document counts as missing", T, "            elif target not in artefacts and not target.startswith((\"DOC-\", \"MEM-\")):", "            elif target not in artefacts:"),
    ("a withdrawn item is checked as if current", T, "    current = [i for i in items if not i.withdrawn]\n    for item in sorted(current,", "    current = list(items)\n    for item in sorted(current,"),
    ("the gap cap is off", T, "    return Trace(tuple(chains), order, tuple(gaps[:MAX_GAPS]), max(0, len(gaps) - MAX_GAPS), by_id, dict(sorted(counts.items())))", "    return Trace(tuple(chains), order, tuple(gaps), 0, by_id, dict(sorted(counts.items())))"),
    ("the gap cap is one too low", T, "MAX_GAPS = 500 ", "MAX_GAPS = 499 "),
    ("gaps are not ordered", T, "    gaps.sort(key=lambda g: (KINDS.index(g.kind), sort_key(g.item), g.other or \"\", g.by or \"\"))", "    pass"),
    ("the declared kind is listed first", T, "KINDS = (NOT_COVERED, BUILT_ON_NOTHING, WITHDRAWN_TARGET, MISSING_TARGET, DECLARED)", "KINDS = (DECLARED, NOT_COVERED, BUILT_ON_NOTHING, WITHDRAWN_TARGET, MISSING_TARGET)"),
    # --- the chain table
    ("a requirement row shows only the nearest layer", T, "        below = [d for d in walk(root.id, down) if d in by_id and not by_id[d].withdrawn]", "        below = [d for d in down.get(root.id, ()) if d in by_id and not by_id[d].withdrawn]"),
    ("a withdrawn item is listed under a requirement", T, "        below = [d for d in walk(root.id, down) if d in by_id and not by_id[d].withdrawn]", "        below = [d for d in walk(root.id, down) if d in by_id]"),
    ("a withdrawn requirement gets a row", T, "    for root in sorted((i for i in current if prefix_of(i.id) in roots), key=lambda i: sort_key(i.id)):", "    for root in sorted((i for i in items if prefix_of(i.id) in roots), key=lambda i: sort_key(i.id)):"),
    ("every empty cell is not started", T, '        states = {p: ("built" if layers[p] else ("empty" if holders_phase.get(p) in started else "not_started")) for p in order}', '        states = {p: ("built" if layers[p] else "not_started") for p in order}'),
    ("every empty cell is empty", T, '        states = {p: ("built" if layers[p] else ("empty" if holders_phase.get(p) in started else "not_started")) for p in order}', '        states = {p: ("built" if layers[p] else "empty") for p in order}'),
    ("cells are not in number order", T, "        layers = {p: tuple(sorted(by_layer.get(p, ()), key=sort_key)) for p in order}", "        layers = {p: tuple(by_layer.get(p, ())) for p in order}"),
    ("requirements are not in order", T, "    for root in sorted((i for i in current if prefix_of(i.id) in roots), key=lambda i: sort_key(i.id)):", "    for root in (i for i in current if prefix_of(i.id) in roots):"),
    ("only functional requirements get a row", G, 'roots=("FR", "NFR")', 'roots=("FR",)'),
    ("counts include withdrawn items", T, "    for item in current:\n        counts[prefix_of(item.id)] += 1", "    for item in items:\n        counts[prefix_of(item.id)] += 1"),
    # --- reading the skills and the Coverage check
    ("a rule forgets what a skill covers", G, "        out.append(Rule(key, tuple(spec.prefix for spec in skill.items), tuple(skill.covers), skill.artefact.phase_key, read))", "        out.append(Rule(key, tuple(spec.prefix for spec in skill.items), (), skill.artefact.phase_key, read))"),
    ("a rule forgets what a skill reads", G, "        out.append(Rule(key, tuple(spec.prefix for spec in skill.items), tuple(skill.covers), skill.artefact.phase_key, read))", "        out.append(Rule(key, tuple(spec.prefix for spec in skill.items), tuple(skill.covers), skill.artefact.phase_key, ()))"),
    ("the chain starts at every kind", G, "        if not any(up in holders for up in skill.upstream):", "        if True:"),
    ("the chain starts nowhere", G, "        if not any(up in holders for up in skill.upstream):", "        if False:"),
    ("a withdrawn item is not read", G, "        for withdrawn_id in parsed.withdrawn:\n            items.append(Item(withdrawn_id, artefact.id, artefact.type, version.number, withdrawn=True))", "        for withdrawn_id in parsed.withdrawn:\n            pass"),
    ("an older version is read", G, "        version = store.artefacts.get_version(project_id, artefact.id)\n        parsed", "        version = store.artefacts.get_version(project_id, artefact.id, 1)\n        parsed"),
    ("a coverage reason is not read", G, "        declared.update({(artefact.type, item_id): reason for item_id, reason in declared_reasons(version.body, covered).items()})", "        pass"),
    ("a coverage reason is given to the wrong artefact", G, "        declared.update({(artefact.type, item_id): reason", "        declared.update({('personas', item_id): reason"),
    ("a reason about a kind that cannot be covered is accepted", G, "            if match and prefix_of(match.group(1)) in covered:", "            if match:"),
    ("a reason is not cut", G, 'reason = " ".join(match.group("reason").split())[:REASON_CHARS]', 'reason = " ".join(match.group("reason").split())'),
    ("a missing reason is blank", G, 'out.setdefault(match.group(1), reason or "no reason given")', 'out.setdefault(match.group(1), reason)'),
    ("the first reason wins no more", G, 'out.setdefault(match.group(1), reason or "no reason given")', 'out[match.group(1)] = reason or "no reason given"'),
    # --- the phase of a gap
    ("a gap is given to the phase that holds the item", G, "    here = [g for g in trace.gaps if (g.by in types if g.by else g.artefact_id in ids)]", "    here = [g for g in trace.gaps if g.artefact_id in ids]"),
    ("every phase gets every gap", G, "    here = [g for g in trace.gaps if (g.by in types if g.by else g.artefact_id in ids)]", "    here = list(trace.gaps)"),
    ("a gap with no artefact is given to no phase", G, "    here = [g for g in trace.gaps if (g.by in types if g.by else g.artefact_id in ids)]", "    here = [g for g in trace.gaps if g.by in types]"),
    ("items in the approval are not capped", G, '"items": sorted({g.item for g in attention}, key=sort_key)[:50],', '"items": sorted({g.item for g in attention}, key=sort_key),'),
    ("items in the approval are not sorted", G, '"items": sorted({g.item for g in attention}, key=sort_key)[:50],', '"items": list({g.item for g in attention})[:50],'),
    ("the explained count is the needs-attention count", G, '"needs_attention": len(attention) + more, "explained": sum(1 for g in here if g.group == "explained"),', '"needs_attention": len(attention) + more, "explained": len(attention),'),
    ("the approval does not record the gaps", H, '            "traceability_gaps": gaps_for_phase(self.store, self.runtime.skills, self.engine.catalogue, project_id, phase_key),\n', ""),
    # --- the route and the CSV
    ("a spreadsheet formula is not neutralised", R, "    return \"'\" + text if text.startswith(_FORMULA) else text", "    return text"),
    ("only an equals sign is neutralised", R, '_FORMULA = ("=", "+", "-", "@", "\\t", "\\r")', '_FORMULA = ("=",)'),
    ("the dash is quoted", R, '    if text == NO_ITEMS:\n        return text', '    if False:\n        return text'),
    ("the CSV header is reordered", R, '    writer.writerow(["Requirement", "Name", *trace.layer_order])', '    writer.writerow(["Name", "Requirement", *trace.layer_order])'),
    ("an empty cell is blank in the CSV", R, 'else NO_ITEMS))', 'else ""))'),
    ("a not-started cell is a dash in the CSV", R, '("not started" if state == "not_started" else NO_ITEMS)', "NO_ITEMS"),
    ("the CSV is not named", R, '"Content-Disposition": \'attachment; filename="traceability.csv"\'', '"X-Nothing": "x"'),
    ("an item id is not checked", R, '    if not _ITEM.fullmatch(item_id):\n        raise HTTPException(status_code=422, detail="item id has unexpected characters")', "    pass"),
    ("an unknown item is not refused", R, '    if item_id not in trace.items:\n        raise HTTPException(status_code=404, detail=f"{item_id} is not an item in this project")', "    pass"),
    ("the answer holds artefact bodies", R, '        "counts": dict(trace.counts),', '        "counts": dict(trace.counts), "bodies": {i.id: i.name for i in trace.items.values()},'),
    ("an item's gaps show other items' gaps", R, '"gaps": [gap_payload(g) for g in trace.gaps if g.item == item_id or g.other == item_id]}', '"gaps": [gap_payload(g) for g in trace.gaps]}'),
    ("what an item comes from and what is built on it swap", R, 'return {"item": row(item_id), "comes_from": [row(i) for i in ancestors(item_id, links)], "built_on_it": [row(i) for i in descendants(item_id, links)],', 'return {"item": row(item_id), "comes_from": [row(i) for i in descendants(item_id, links)], "built_on_it": [row(i) for i in ancestors(item_id, links)],'),
    ("the needs-attention count includes the explained", R, '"needs_attention": sum(1 for g in gaps if g["group"] == "needs_attention"),', '"needs_attention": len(gaps),'),
    ("a phase counts as started when a planned artefact has no version", G, "        artefact_ids.append(artefact.id)\n        if artefact.latest_version is None:\n            continue", "        artefact_ids.append(artefact.id)\n        started.add(artefact.phase_key)\n        if artefact.latest_version is None:\n            continue"),
]
