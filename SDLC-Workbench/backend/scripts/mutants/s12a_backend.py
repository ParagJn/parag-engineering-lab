"""Deliberate breaks for S12a (the project routes, the X-Actor rule, the allowed-actions table).

Run:  cd backend && python -u -m scripts.mutation_check scripts/mutants/s12a_backend.py
Every one of these should make the test suite FAIL. One that does not is a hole in the tests.
"""
ROUTES = "app/routes_projects.py"
ACTOR = "app/actor.py"
ENGINE = "app/workflow/engine.py"
MAIN = "app/main.py"

MUTANTS = [
    # --- the X-Actor rule
    ("a missing actor is accepted", ACTOR, "    if raw is None:\n        raise HTTPException(", "    if False:\n        raise HTTPException("),
    ("a blank actor is accepted", ACTOR, "    if not name:\n        raise HTTPException(", "    if False:\n        raise HTTPException("),
    ("an oversize actor is accepted", ACTOR, "    if len(name) > MAX_NAME_CHARS:", "    if False:"),
    ("the actor limit is one too generous", ACTOR, "    if len(name) > MAX_NAME_CHARS:", "    if len(name) > MAX_NAME_CHARS + 1:"),
    ("a control character in the actor is accepted", ACTOR, "if any(ord(c) < 32 or ord(c) == 127 for c in raw) or", "if False or"),
    ("DEL is not treated as a control character", ACTOR, "ord(c) < 32 or ord(c) == 127", "ord(c) < 32"),
    ("the name 'system' can be claimed by a client", ACTOR, 'or name.lower() in ("system",) or', "or"),
    ("a client can claim an agent identity", ACTOR, '.startswith(("human:", "agent:"))', '.startswith(("human:",))'),
    ("a client can claim a human prefix", ACTOR, '.startswith(("human:", "agent:"))', '.startswith(("agent:",))'),
    ("the actor is not tidied", ACTOR, 'name = " ".join(raw.split())', "name = raw"),
    ("the actor loses its human prefix", ACTOR, 'return f"human:{name}"', "return name"),
    # --- allowed actions
    ("a not-started phase offers nothing", ENGINE, '"not_started": ("run",),', '"not_started": (),'),
    ("a running phase cannot be finished", ENGINE, '"running": ("run", "finish"),', '"running": ("run",),'),
    ("a phase under review cannot be approved", ENGINE, '"awaiting_review": ("approve", "request_changes"),', '"awaiting_review": ("request_changes",),'),
    ("a phase under review cannot be sent back", ENGINE, '"awaiting_review": ("approve", "request_changes"),', '"awaiting_review": ("approve",),'),
    ("a rejected phase cannot be re-run", ENGINE, '"rejected": ("run",),', '"rejected": (),'),
    ("an approved phase still offers actions", ENGINE, '"approved": (),', '"approved": ("run",),'),
    ("a phase with no artefacts offers actions", ENGINE, "    if not has_artefacts:\n        return ()\n", ""),
    ("a blocked phase offers to run", ENGINE, '    if status == "not_started" and blocked_by is not None:\n        return ()\n', ""),
    ("every blocked phase offers nothing", ENGINE, 'if status == "not_started" and blocked_by is not None:', "if blocked_by is not None:"),
    ("an unknown status offers something", ENGINE, "    return ACTIONS_BY_STATUS.get(status, ())", '    return ACTIONS_BY_STATUS.get(status, ("run",))'),
    ("the snapshot forgets the actions", ENGINE, "allowed_actions=allowed_actions(status, bool(phase.artefacts), self._blocked_by(plan, list(rows.values()), phase)),", "allowed_actions=(),"),
    # --- the routes
    ("the preview ignores the selection", ROUTES, "build_plan(_engine(request).catalogue, body.selection)", "build_plan(_engine(request).catalogue, {})"),
    ("a bad preview is a 500", ROUTES, "    except PlanError as exc:\n        raise HTTPException(status_code=422, detail=str(exc)) from exc\n\n\n@router.post(\"/projects\"", "    except KeyError as exc:\n        raise HTTPException(status_code=422, detail=str(exc)) from exc\n\n\n@router.post(\"/projects\""),
    ("creating a project needs no actor", ROUTES, "    actor = actor_from(request)\n    engine, store", "    actor = 'human:anyone'\n    engine, store"),
    ("a bad selection is checked after the project exists", ROUTES, "        build_plan(engine.catalogue, body.selection)   # refuse a bad selection before anything is created\n", ""),
    ("the project takes a client-chosen mode", ROUTES, "mode=request.app.state.settings.app_mode, selection=dict(body.selection), actor=actor,", "mode='live', selection=dict(body.selection), actor=actor,"),
    ("a project is created without opening its phases", ROUTES, "        engine.open_project(project.id)\n        if body.connectors:", "        if body.connectors:"),
    ("connectors are not remembered", ROUTES, "        if body.connectors:\n            # Connectors are SIMULATED", "        if False:\n            # Connectors are SIMULATED"),
    ("connectors are not marked simulated in the audit note", ROUTES, 'detail={"connectors": body.connectors, "simulated": True},', 'detail={"connectors": body.connectors},'),
    ("the detail forgets connectors are simulated", ROUTES, '"connectors": connectors, "connectors_are_simulated": True,', '"connectors": connectors,'),
    ("unknown request fields are accepted", ROUTES, "class CreateProject(BaseModel):\n    model_config = ConfigDict(extra=\"forbid\")", "class CreateProject(BaseModel):\n    model_config = ConfigDict(extra=\"ignore\")"),
    ("an unknown connector is accepted", ROUTES, "        if unknown:\n            raise ValueError(f\"unknown connector(s)", "        if False:\n            raise ValueError(f\"unknown connector(s)"),
    ("the name is not tidied", ROUTES, '        value = " ".join(value.split())\n        if not value:', "        if not value:"),
    ("projects are listed oldest first", ROUTES, "projects = list(reversed(store.projects.list()))[:MAX_PROJECTS_LISTED]", "projects = list(store.projects.list())[:MAX_PROJECTS_LISTED]"),
    ("the list is unbounded", ROUTES, "[:MAX_PROJECTS_LISTED]", ""),
    ("the summary forgets the active phase", ROUTES, 'active = next((p for p in snapshot.phases if p.status in ("running", "awaiting_review", "rejected")), None)', "active = None"),
    ("an unknown project is a 500", ROUTES, "    except (NotFoundError, InvalidInput) as exc:\n        raise _fail(exc) from exc", "    except InvalidInput as exc:\n        raise _fail(exc) from exc"),
    ("a not-found is a 422", ROUTES, "    if isinstance(exc, NotFoundError):\n        return HTTPException(status_code=404, detail=str(exc))\n    return HTTPException(status_code=422", "    return HTTPException(status_code=422"),
    ("the mode is always replay", ROUTES, 'mode = request.app.state.settings.app_mode\n    return {', 'mode = "replay"\n    return {'),
    ("the catalogue is incomplete", ROUTES, "for p in catalogue.phases\n        ]\n    }\n\n\ndef project_summary", "for p in catalogue.phases[:3]\n        ]\n    }\n\n\ndef project_summary"),
    ("the preview omits the notes", ROUTES, '        "notes": list(plan.notes),\n    }\n\n\ndef catalogue_payload', '        "notes": [],\n    }\n\n\ndef catalogue_payload'),
    ("the wave of an artefact is wrong", ROUTES, 'for n, wave in enumerate(p.waves, start=1)', 'for n, wave in enumerate(p.waves, start=2)'),
    ("the routes are not mounted", MAIN, "    app.include_router(projects_router)\n", ""),
]
