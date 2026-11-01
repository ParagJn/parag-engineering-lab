"""Deliberate breaks for S12b (documents, search, the sample, artefacts, the two gate buttons, run listing, and the X-Actor rule on runs).

Run:  cd backend && python -u -m scripts.mutation_check scripts/mutants/s12b_backend.py
Every one of these should make the test suite FAIL. One that does not is a hole in the tests.
"""
CONTENT = "app/routes_content.py"
ART = "app/routes_artefacts.py"
RUNS = "app/routes.py"
SAMPLE = "app/sample.py"
EXPORT = "scripts/export_contract.py"

MUTANTS = [
    # --- the sample
    ("the sample name is changed", SAMPLE, 'NAME = "Meeting Room Booking"', 'NAME = "Meeting Room Booking App"'),
    ("the sample filename is changed", SAMPLE, 'FILENAME = "meeting-room-policy.md"', 'FILENAME = "policy.md"'),
    ("the sample brief loses a sentence", SAMPLE, '    "It must respect office hours of eight to six on weekdays. "\n', ""),
    ("the sample route serves a different document", CONTENT, 'return {"name": NAME, "brief": BRIEF, "document": {"filename": FILENAME, "text": POLICY.decode("utf-8")}}', 'return {"name": NAME, "brief": BRIEF, "document": {"filename": FILENAME, "text": POLICY.decode("utf-8").strip()}}'),
    # --- documents
    ("an upload needs no actor", CONTENT, "async def add_document(project_id: str, request: Request, file: UploadFile = File(...)) -> dict:\n    actor = actor_from(request)", "async def add_document(project_id: str, request: Request, file: UploadFile = File(...)) -> dict:\n    actor = 'human:anyone'"),
    ("a removal needs no actor", CONTENT, "def remove_document(project_id: str, request: Request, number: int = Path(ge=1, le=1_000_000)) -> dict:\n    actor = actor_from(request)", "def remove_document(project_id: str, request: Request, number: int = Path(ge=1, le=1_000_000)) -> dict:\n    actor = 'human:anyone'"),
    ("an unknown project's upload is not checked", CONTENT, "    try:\n        store.projects.get(project_id)\n        refuse_if_archived(request, project_id)\n    except NotFoundError as exc:\n        raise _fail(exc) from exc\n    name =", "    refuse_if_archived(request, project_id)\n    name ="),
    ("a nameless file is accepted", CONTENT, "    if not name:\n        raise HTTPException(status_code=422, detail=\"the file has no name;", "    if False:\n        raise HTTPException(status_code=422, detail=\"the file has no name;"),
    ("the size limit is not enforced", CONTENT, "    if len(data) > limit:\n        raise HTTPException(", "    if False:\n        raise HTTPException("),
    # UNKILLABLE, kept as documentation: reading one byte more than the limit allows still leaves an over-limit file over the limit, so the
    # route refuses it either way (and the store's own size check backs it up). The mutant changes nothing anyone can observe.
    ("the size limit is one byte too generous", CONTENT, "    data = await file.read(limit + 1)", "    data = await file.read(limit + 2)"),
    ("an upload does not return its flags", CONTENT, '        out["flags"] = [f.as_dict() for f in doc.findings]', '        out["flags"] = []'),
    ("the document list carries flags too", CONTENT, "def list_documents(project_id: str, request: Request) -> dict:\n    try:\n        return {\"documents\": [document_payload(d) for d in", "def list_documents(project_id: str, request: Request) -> dict:\n    try:\n        return {\"documents\": [document_payload(d, with_flags=True) for d in"),
    ("an upload does not say it was already added", CONTENT, '        out["already_added"] = doc.already_added', '        out["already_added"] = False'),
    ("a document number of zero is accepted", CONTENT, "Path(ge=1, le=1_000_000)", "Path(ge=0, le=1_000_000)"),
    ("a refusal from the store is a 500", CONTENT, "    if isinstance(exc, NotFoundError):\n        return HTTPException(status_code=404, detail=str(exc))\n    return HTTPException(status_code=422", "    if isinstance(exc, NotFoundError):\n        return HTTPException(status_code=404, detail=str(exc))\n    raise exc  # HTTPException(status_code=422"),
    ("a not-found is a 422 here", CONTENT, "    if isinstance(exc, NotFoundError):\n        return HTTPException(status_code=404, detail=str(exc))\n    return HTTPException(status_code=422", "    return HTTPException(status_code=422"),
    ("the document id shown is not the citable one", CONTENT, '"source_id": doc.source_prefix,', '"source_id": f"DOC-{doc.number}",'),
    # --- search
    ("an empty search is accepted", CONTENT, '    if not query:\n        raise HTTPException(status_code=422, detail="type a word or a question to search for")', "    if False:\n        raise HTTPException(status_code=422, detail=\"type a word or a question to search for\")"),
    ("the search is not tidied", CONTENT, '    query = " ".join(q.split())', "    query = q"),
    ("a long search is accepted", CONTENT, "    if len(query) > MAX_QUERY_CHARS:", "    if False:"),
    ("the search limit is ignored", CONTENT, "hits = _store(request).context.search(project_id, query, limit=limit)", "hits = _store(request).context.search(project_id, query)"),
    ("the search limit has no ceiling", CONTENT, "limit: int = Query(default=8, ge=1, le=MAX_SEARCH_LIMIT),", "limit: int = Query(default=8, ge=1),"),
    ("a long passage is not shortened", CONTENT, "    text = hit.text if len(hit.text) <= MAX_HIT_CHARS else hit.text[:MAX_HIT_CHARS].rstrip() + \"…\"", "    text = hit.text"),
    ("a hit loses its citation", CONTENT, '"page": hit.page, "citation": hit.citation,', '"page": hit.page, "citation": "",'),
    ("the search shows the cleaned query wrongly", CONTENT, 'return {"query": query, "hits":', 'return {"query": q, "hits":'),
    # --- artefacts
    ("the artefact list ignores its phase filter", ART, "artefacts = store.artefacts.list(project_id, phase_key=phase)", "artefacts = store.artefacts.list(project_id)"),
    ("a bad phase filter is accepted", ART, '    if phase is not None and not _valid(phase, KEY):\n        raise HTTPException(status_code=422, detail="phase must be lower-case letters, digits and underscores")\n    store = _store(request)', "    store = _store(request)"),
    ("a malformed artefact id is accepted", ART, '    if not _valid(artefact_id, ARTEFACT_ID):\n        raise HTTPException(status_code=422, detail="artefact id has unexpected characters")', "    pass"),
    ("an unwritten artefact is read as version one", ART, '        if artefact.latest_version is None:\n            raise NotFoundError(f"artefact {artefact_id!r} has not been written yet")\n', ""),
    ("the version asked for is ignored", ART, "shown = store.artefacts.get_version(project_id, artefact_id, version)", "shown = store.artefacts.get_version(project_id, artefact_id)"),
    ("an older version is called the latest", ART, '"is_latest": shown.number == artefact.latest_version,', '"is_latest": True,'),
    ("a version number of zero is accepted", ART, "ge=1, le=100000", "ge=0, le=100000"),
    ("an unavailable source still shows text", ART, '            out.append({"source_id": source_id, "available": False, "title": None, "heading_path": None, "text": None, "page": None})', '            out.append({"source_id": source_id, "available": False, "title": None, "heading_path": None, "text": "", "page": None})'),
    ("a cited source is looked up without its project", ART, "hit = store.context.resolve(project_id, source_id)", "hit = store.context.resolve(store.projects.list()[0].id, source_id)"),
    ("every cited source is shown without a limit", ART, "version.source_chunks[:MAX_SOURCES]", "version.source_chunks"),
    ("an unknown cost is shown as zero", ART, "def _money(value: Any) -> float | None:\n    return None if value is None else float(value)", "def _money(value: Any) -> float | None:\n    return 0.0 if value is None else float(value)"),
    ("the models are not listed", ART, '"models": sorted({c.get("model") for c in calls if c.get("model")}),', '"models": [],'),
    ("repair reasons are hidden", ART, '"repair_reasons": [\n            {"attempt": r.get("attempt"), "problems": [str(p) for p in (r.get("problems") or [])]}\n            for r in (generation.get("repair_reasons") or []) if isinstance(r, dict)\n        ],', '"repair_reasons": [],'),
    ("guardrail findings are hidden", ART, '"guardrails": [\n            {"rule": g.get("rule"), "class": g.get("class"), "line": g.get("line"), "heading": g.get("heading"), "length": g.get("length")}\n            for g in (generation.get("guardrails") or []) if isinstance(g, dict)\n        ],', '"guardrails": [],'),
    ("a hand edit is not marked", ART, '"human_edit": bool(generation.get("human_edit")),', '"human_edit": False,'),
    ("the flag count on a card is wrong", ART, '"flags": 0 if summary is None else len(summary["guardrails"]),', '"flags": 0,'),
    ("the item count on a card is wrong", ART, '"item_count": 0 if summary is None else len(summary["items"]),', '"item_count": 0,'),
    ("links are not split into up and down", ART, "        elif link.to_id in ids and link.from_id not in ids:\n            used_by.append", "        elif False:\n            used_by.append"),
    ("links between an artefact's own items are shown", ART, "        if link.from_id in ids and link.to_id not in ids:\n            derived_from.append", "        if link.from_id in ids:\n            derived_from.append"),
    # --- the two gate buttons
    ("finishing a phase needs no actor", ART, "def _gate(project_id: str, phase_key: str, request: Request, action: str) -> dict:\n    actor = actor_from(request)", "def _gate(project_id: str, phase_key: str, request: Request, action: str) -> dict:\n    actor = 'human:anyone'"),
    ("a bad phase key is accepted on a gate action", ART, '    if not _valid(phase_key, KEY):\n        raise HTTPException(status_code=422, detail="phase key must be lower-case letters, digits and underscores")\n    refuse_if_archived(request, project_id)', "    refuse_if_archived(request, project_id)"),
    ("a phase being written can be handed to review", ART, '        if request.app.state.runner.is_active(project_id, phase_key):\n            raise HTTPException(status_code=409,', '        if False:\n            raise HTTPException(status_code=409,'),
    ("approve is really finish", ART, "            run = human.approve(project_id, phase_key, actor=actor)", "            run = engine.finish(project_id, phase_key, actor=actor)"),
    ("finish is really approve", ART, "            run = engine.finish(project_id, phase_key, actor=actor)\n        else:", "            run = human.approve(project_id, phase_key, actor=actor)\n        else:"),
    ("approve skips the open-findings record", ART, "            run = human.approve(project_id, phase_key, actor=actor)", "            run = engine.approve(project_id, phase_key, actor=actor)"),
    ("a gate refusal is a 422", ART, "    if isinstance(exc, (PrerequisiteNotMet, GateNotMet, IllegalTransition, WrongPhaseState)):\n        return HTTPException(status_code=409, detail=str(exc))", "    if False:\n        return HTTPException(status_code=409, detail=str(exc))"),
    ("a gate answer hides who decided", ART, '"decision": run.decision, "decided_by": run.decided_by}', '"decision": run.decision, "decided_by": None}'),
    # --- run listing
    ("runs are listed oldest first", ART, '"runs": [_run_payload(r) for r in reversed(runs)][:20]', '"runs": [_run_payload(r) for r in runs][:20]'),
    ("the run list is unbounded", ART, "for r in reversed(runs)][:20]", "for r in reversed(runs)]"),
    ("the run phase filter is ignored", ART, "runs = _store(request).runs.list(project_id, phase_key=phase)", "runs = _store(request).runs.list(project_id)"),
    ("an unknown project's runs are an empty list", ART, "        _store(request).projects.get(project_id)\n        runs =", "        runs ="),
    # --- X-Actor on the run routes
    ("starting a run needs no actor", RUNS, "    actor = actor_from(request)    # starting a run can spend money: the audit trail says who asked\n", "    actor = 'human:anyone'\n"),
    ("a started run is not audited", RUNS, '    _store(request).audit.append(\n        actor=actor, action="run.requested",', '    _store(request).audit.append if False else None, dict(\n        actor=actor, action="run.requested",'),
    ("cancelling a run needs no actor", RUNS, "def cancel_run(project_id: str, run_id: str, request: Request) -> dict:\n    actor = actor_from(request)", "def cancel_run(project_id: str, run_id: str, request: Request) -> dict:\n    actor = 'human:anyone'"),
    ("a cancel is not audited", RUNS, 'action="run.cancel_requested"', 'action="run.cancel_requested_unrecorded"'),
    ("the audit of a run names the wrong phase", RUNS, 'detail={"phase": phase_key, "only": body.only,', 'detail={"phase": "setup", "only": body.only,'),
    # --- archiving (addendum 1)
    ("archived projects are not read-only", "app/archive.py", "    if project.archived_at is not None:\n        raise HTTPException(status_code=409, detail=SENTENCE)", "    if False:\n        raise HTTPException(status_code=409, detail=SENTENCE)"),
    ("the archived message is different", "app/archive.py", 'SENTENCE = "This project is archived; restore it first."', 'SENTENCE = "Not allowed."'),
    ("an unknown project is called archived", "app/archive.py", "    except NotFoundError:\n        return", "    except NotFoundError:\n        raise HTTPException(status_code=409, detail=SENTENCE)"),
    ("starting a run ignores archiving", RUNS, "    refuse_if_archived(request, project_id)\n    if not _valid(phase_key, KEY):", "    if not _valid(phase_key, KEY):"),
    ("adding a document ignores archiving", CONTENT, "        store.projects.get(project_id)\n        refuse_if_archived(request, project_id)\n", "        store.projects.get(project_id)\n"),
    ("removing a document ignores archiving", CONTENT, "    actor = actor_from(request)\n    refuse_if_archived(request, project_id)\n    try:\n        _store(request).context.remove_document", "    actor = actor_from(request)\n    try:\n        _store(request).context.remove_document"),
    ("a gate action ignores archiving", ART, "    refuse_if_archived(request, project_id)\n    engine, human", "    engine, human"),
    ("archive needs no actor", "app/routes_projects.py", 'def archive_project(project_id: str, request: Request) -> dict:\n    """Hide a project and make it read-only. Refused while a run is going on it, because that run could still be spending money."""\n    actor = actor_from(request)', 'def archive_project(project_id: str, request: Request) -> dict:\n    """Hide a project and make it read-only. Refused while a run is going on it, because that run could still be spending money."""\n    actor = "human:anyone"'),
    ("restore needs no actor", "app/routes_projects.py", "def restore_project(project_id: str, request: Request) -> dict:\n    actor = actor_from(request)", 'def restore_project(project_id: str, request: Request) -> dict:\n    actor = "human:anyone"'),
    ("a running project can be archived", "app/routes_projects.py", "            if runner.is_active(project_id, phase_key):", "            if False:"),
    ("only the first phase is checked for a run", "app/routes_projects.py", "for phase_key in _engine(request).catalogue.phase_keys:", "for phase_key in _engine(request).catalogue.phase_keys[:1]:"),
    ("the archived list shows everything", "app/repos.py", 'where = "archived_at IS NOT NULL" if archived else "archived_at IS NULL"', 'where = "1 = 1"'),
    ("the default list shows archived projects", "app/repos.py", 'where = "archived_at IS NOT NULL" if archived else "archived_at IS NULL"', 'where = "archived_at IS NOT NULL" if archived else "1 = 1"'),
    ("archiving twice audits twice", "app/repos.py", 'if (row["archived_at"] is not None) != archive:', "if True:"),
    ("restore does not clear the date", "app/repos.py", 'conn.execute("UPDATE projects SET archived_at = ? WHERE id = ?", (now if archive else None, project_id))', 'conn.execute("UPDATE projects SET archived_at = ? WHERE id = ?", (now, project_id))'),
    ("a restore is audited as an archive", "app/repos.py", '"project.archived" if archive else "project.restored"', '"project.archived"'),
    ("archive does not record who", "app/repos.py", "conn, now, actor, \"project.archived\" if archive", "conn, now, \"system\", \"project.archived\" if archive"),
    ("the summary forgets the archive date", "app/routes_projects.py", '"mode": project.mode, "created_at": project.created_at, "archived_at": project.archived_at,\n        "phases_total":', '"mode": project.mode, "created_at": project.created_at, "archived_at": None,\n        "phases_total":'),
    ("the detail forgets the archive date", "app/routes_projects.py", '"updated_at": project.updated_at, "archived_at": project.archived_at,', '"updated_at": project.updated_at, "archived_at": None,'),
    ("the archived query switch is ignored", "app/routes_projects.py", "store.projects.list(archived=archived)", "store.projects.list()"),
    # --- the contract exporter
    ("the exporter drops an event type", EXPORT, 'events.update({k: v for k, v in _events_by_type(capped).items() if k == "run.stopped"})', "pass"),
    ("the exporter leaves the artefact list unsorted", EXPORT, '        out["artefacts"]["artefacts"].sort(key=lambda card: card["type"])\n', ""),
    ("the exporter forgets to zero the timings", EXPORT, "_VARIABLE_NUMBERS = {\"elapsed_seconds\", \"serial_seconds\", \"max_in_flight\"}", "_VARIABLE_NUMBERS = set()"),
]
