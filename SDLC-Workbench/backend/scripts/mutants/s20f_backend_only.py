"""Deliberate breaks for S20f (Build Verify backend only: screens removed, rules reached through their endpoint, old runs still readable).

Backend:  python -u -m scripts.mutation_check scripts/mutants/s20f_backend_only.py --tests tests/test_verify_rules.py tests/test_verify_match.py tests/test_verify_store.py
Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/s20f_backend_only.py
Run alone: a sweep beside other heavy work gives INVALID ('no output') results.
"""
M = "app/verify/match.py"
D = "app/verify/design.py"
R = "app/verify/report.py"
V = "app/routes_verify.py"
S = "app/verify/service.py"

MUTANTS = [
    # ---- who a rule is kin to
    ("a shared requirement alone links", M, "        if not ((sources and words) or len(words) >= RULE_LINK_WORDS):", "        if not (sources or len(words) >= RULE_LINK_WORDS):"),
    ("a shared word alone links", M, "        if not ((sources and words) or len(words) >= RULE_LINK_WORDS):", "        if not (words or len(words) >= RULE_LINK_WORDS):"),
    ("two shared words are enough", M, "RULE_LINK_WORDS = 3 ", "RULE_LINK_WORDS = 2 "),
    ("five shared words are needed", M, "RULE_LINK_WORDS = 3 ", "RULE_LINK_WORDS = 5 "),
    ("a document chunk counts as a requirement", M, '_CITED_SOURCE = ("MEM-", "DOC-")', "_CITED_SOURCE = ()"),
    ("the endpoint with fewest words wins", M, "        key = (-len(words), -len(sources), ep.id)", "        key = (len(words), -len(sources), ep.id)"),
    ("a tie goes to the highest id", M, "        key = (-len(words), -len(sources), ep.id)", "        key = (-len(words), -len(sources), tuple(-ord(c) for c in ep.id))"),
    ("a shared requirement does not break a tie", M, "        key = (-len(words), -len(sources), ep.id)", "        key = (-len(words), 0, ep.id)"),
    ("the link is not explained", M, '    return f"Linked to {link.endpoint.id} because {kin}"', '    return ""'),
    ("the shared requirement is not named", M, "both come from {', '.join(link.shared_sources)} and share", "both come from the same requirement and share"),
    # ---- what the hint says
    ("an endpoint that answers makes the rule found", M, "    if answered:\n        return Match(rule.id, \"rule\", WEAK,", "    if answered:\n        return Match(rule.id, \"rule\", FOUND,"),
    ("a rule with no error code is found", M, "    return Match(rule.id, \"rule\", WEAK, **where, note=f\"{why}. {ep.id} is built as {m.built}; the design gives it no error code", "    return Match(rule.id, \"rule\", FOUND, **where, note=f\"{why}. {ep.id} is built as {m.built}; the design gives it no error code"),
    ("a missing refusal still gives weak evidence", M, "    if wanted and not answered:\n        return Match(rule.id, \"rule\", NOT_FOUND,", "    if wanted and not answered:\n        return Match(rule.id, \"rule\", WEAK,"),
    ("a success code counts as a refusal", M, "    wanted = tuple(c for c in ep.codes if c >= 400)", "    wanted = tuple(c for c in ep.codes)"),
    ("any error code counts for any route", M, "    answered = tuple(c for c in wanted if route is not None and c in route.status_codes)", "    answered = wanted"),
    ("the hint names no code", M, "and answers {', '.join(map(str, answered))}, which is how", "and answers, which is how"),
    ("the hint forgets it is weak", M, "This is weak evidence: the rule has a home, but nothing shows it is enforced.", "The rule is enforced."),
    ("an unbuilt endpoint still gives weak evidence", M, "    if m is None or m.state not in (FOUND, DIFFERENCES):\n        if m is not None and m.state == POSSIBLE:", "    if m is None or m.state not in (FOUND, DIFFERENCES, NOT_FOUND):\n        if m is not None and m.state == POSSIBLE:"),
    ("a possible endpoint counts as built", M, "    if m is None or m.state not in (FOUND, DIFFERENCES):", "    if m is None or m.state not in (FOUND, DIFFERENCES, POSSIBLE):"),
    ("an endpoint found with differences does not count", M, "    if m is None or m.state not in (FOUND, DIFFERENCES):", "    if m is None or m.state not in (FOUND,):"),
    ("the hint does not name the built route", M, "    where = dict(built=m.built, file=m.file, line=m.line)", "    where = dict()"),
    ("the endpoint is looked up by the wrong key", M, "    route = routes.get(m.built)", "    route = routes.get(m.designed)"),
    ("no link means weak", M, "        if link is None:\n            out.append(Match(item.id, \"rule\", NOT_FOUND,", "        if link is None:\n            out.append(Match(item.id, \"rule\", WEAK,"),
    ("the comment no longer wins", M, "        if hit is not None:\n            out.append(Match(item.id, \"rule\", WEAK, WORDS, 0.0, \"\", hit[0], 0,", "        if False:\n            out.append(Match(item.id, \"rule\", WEAK, WORDS, 0.0, \"\", hit[0], 0,"),
    ("the endpoint list is not passed", M, "    out.matches += match_rules(design, list(backend_texts(backend)), [x for x in out.matches if x.area == \"endpoint\"], backend)", "    out.matches += match_rules(design, list(backend_texts(backend)))"),
    ("the routes are not passed", M, "[x for x in out.matches if x.area == \"endpoint\"], backend)", "[x for x in out.matches if x.area == \"endpoint\"], None)"),
    # ---- what the design keeps
    ("a rule forgets what it derives from", D, 'artefact_id=lld[0], version=lld[1], derives=item.derives))', 'artefact_id=lld[0], version=lld[1]))'),
    ("an endpoint forgets what it derives from", D, "design.items.append(_endpoint(item.id, item.text, contract, lld, item.derives))", "design.items.append(_endpoint(item.id, item.text, contract, lld))"),
    # EQUIVALENT, not tested: design.AREAS only orders the items it reads, and no code creates a screen item any more, so adding the word changes nothing anyone can observe (the report's AREAS, which does show, is tested below)
    # ("a screen is read again", D, ...),
    # ---- the report and the run
    ("the report has screens again", R, 'AREAS = ("endpoint", "table", "rule")\nAREA_WORDS = {"endpoint": "Endpoints", "table": "Tables", "rule": "Rules"}', 'AREAS = ("endpoint", "table", "screen", "rule")\nAREA_WORDS = {"endpoint": "Endpoints", "table": "Tables", "screen": "Screens", "rule": "Rules"}'),
    ("the advice does not say backend", R, "This shows how far the backend of the build has drifted from the design: endpoints, tables and rules.", "This shows how far the build has drifted from the design."),
    ("a frontend path is stored", S, "frontend_path=None, actor=actor,", "frontend_path='x', actor=actor,"),
    # ---- old runs
    ("an old run shows its screen counts", V, '"counts": [c for c in run.counts if c.get("area") in AREAS]', '"counts": list(run.counts)'),
    ("an old run shows its frontend notes", V, '"notes": [n for n in run.notes if not n.startswith("frontend:")]}', '"notes": list(run.notes)}'),
    ("an old run shows its screen matches", V, "    return [m for m in matches if m.area in AREAS]", "    return list(matches)"),
    ("the list shows the old frontend path", V, '"backend_path": run.backend_path, "by": run.actor,', '"backend_path": run.backend_path, "frontend_path": run.frontend_path, "by": run.actor,'),
    ("a single run shows screens", V, '"advice": R.ADVICE, "matches": [match_payload(m) for m in shown(matches)]}\n\n\n@router.get("/{run_id}/download")', '"advice": R.ADVICE, "matches": [match_payload(m) for m in matches]}\n\n\n@router.get("/{run_id}/download")'),
    # REMOVED (dead code): the filter on the new run's response could never change anything, because check() writes no screen row; the code was simplified. Old runs, which can hold screens, are tested through the other routes.
    ("the download shows screens", V, "        matches = shown(store.verify.matches(project_id, run_id))\n    except NotFoundError as exc:\n        raise HTTPException(status_code=404, detail=str(exc)) from exc\n    if format == \"json\":", "        matches = store.verify.matches(project_id, run_id)\n    except NotFoundError as exc:\n        raise HTTPException(status_code=404, detail=str(exc)) from exc\n    if format == \"json\":"),
    ("the markdown download shows frontend notes", V, 'R.build_report(designed, extras, run_payload(run)["notes"])', "R.build_report(designed, extras, run.notes)"),
    ("a frontend path is accepted by the route", V, "    backend_path: str = Field(min_length=1, max_length=MAX_PATH_CHARS)\n", "    backend_path: str = Field(min_length=1, max_length=MAX_PATH_CHARS)\n    frontend_path: str | None = None\n"),
]

A = "src/api/verify.ts"
P = "src/components/VerifyPanel.tsx"
Pg = "src/pages/VerifyPage.tsx"
K = "src/api/client.ts"
L = "src/lib/verify.ts"
Pa = "src/lib/verifyPaths.ts"

FRONTEND = [
    ("screens are an area again", A, "export const AREAS = ['endpoint', 'table', 'rule'] as const", "export const AREAS = ['endpoint', 'table', 'screen', 'rule'] as const"),
    ("an area card for screens is drawn", P, "{(['endpoint', 'table', 'rule'] as Area[]).map((area) => {", "{(['endpoint', 'table', 'screen', 'rule'] as Area[]).map((area) => {"),
    ("the words for screens come back", L, "export const AREA_WORDS: Record<Area, string> = { endpoint: 'Endpoints', table: 'Tables', rule: 'Rules' }", "export const AREA_WORDS: Record<Area, string> = { endpoint: 'Endpoints', table: 'Tables', screen: 'Screens', rule: 'Rules' }"),
    ("the client sends a frontend path", K, "body: JSON.stringify({ backend_path: backendPath }),", "body: JSON.stringify({ backend_path: backendPath, frontend_path: null }),"),
    ("the saved folder keeps a frontend", Pa, "JSON.stringify({ backend: paths.backend.slice(0, MAX) })", "JSON.stringify({ backend: paths.backend.slice(0, MAX), frontend: '' })"),
    # EQUIVALENT, not tested: the client builds the request body from the backend path alone (tested: 'send exactly the backend folder and nothing else'), so an extra argument passed from the page is dropped and changes nothing.
    # ("the run is made with a frontend", Pg, ...)
    ("the panel says it reads a frontend", P, "it does not look at a frontend.", "it also reads a frontend."),
    ("the panel does not say python only", P, "Python/FastAPI only.", ""),
    ("the panel does not name what it looks at", P, "The check looks at the endpoints, the tables and the rules of the design;", "The check looks at the design;"),
]
