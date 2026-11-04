"""Deliberate breaks for S19f-1 (edit ONE file of the Build instruction set).

Backend:  python -u -m scripts.mutation_check scripts/mutants/s19f1_edit_file.py --tests tests/test_edit_file.py tests/test_instructions.py
Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/s19f1_edit_file.py
Run alone: a sweep beside other heavy work gives INVALID ('no output') results.
"""
I = "app/build/instructions.py"
H = "app/review/human.py"
R = "app/routes_review.py"

MUTANTS = [
    # ---- what may be edited
    ("a file that is not in the set is spliced in", I, "    if name not in files:\n        raise FileEditRefused(", "    if False:\n        raise FileEditRefused("),
    ("the design index can be edited", I, "    if kind is None or kind == INDEX:", "    if kind is None:"),
    ("a file with an unknown kind can be edited", I, "    if kind is None or kind == INDEX:", "    if kind == INDEX:"),
    ("an empty text is accepted", I, "    if not text.strip():\n        raise FileEditRefused(\"the edited text is empty\"", "    if False:\n        raise FileEditRefused(\"the edited text is empty\""),
    ("a file mark line is accepted in the text", I, "    if any(FILE_MARK.match(line) for line in text.split(\"\\n\")):", "    if False:"),
    ("line endings from a browser are kept", I, "    text = (new_text or \"\").replace(\"\\r\\n\", \"\\n\").strip(\"\\n\")", "    text = (new_text or \"\").strip(\"\\n\")"),
    # ---- the checks
    ("the edited file is not checked", I, "    problems = [f\"{p}\" for p in check_file(kind, name, strip_tool(edited[name]), design, contract, require_contract=(kind == FOUNDATION and before_contract is not None))]", "    problems = []"),
    ("the contract is not required of an edited foundation", I, "require_contract=(kind == FOUNDATION and before_contract is not None))]", "require_contract=False)]"),
    ("the contract is required of a set that never had one", I, "require_contract=(kind == FOUNDATION and before_contract is not None))]", "require_contract=(kind == FOUNDATION))]"),
    ("set level problems the edit introduces are not looked for", I, "    introduced = [p for p in check_set(edited, design) if p not in problems_before]", "    introduced = []"),
    ("every set level problem blocks, even an old one", I, "    introduced = [p for p in check_set(edited, design) if p not in problems_before]", "    introduced = list(check_set(edited, design))"),
    ("a foundation edit does not check the other files", I, "    if kind == FOUNDATION and contract is not None:", "    if False:"),
    ("a foundation edit blames files that were already in conflict", I, "if before_contract is None or p not in K.file_problems(files[other], before_contract)]", "]"),
    ("the foundation edit skips the acceptance file", I, "            if other == name or ok not in (SCENARIO, SCREEN, ACCEPTANCE):", "            if other == name or ok not in (SCENARIO, SCREEN):"),
    ("the foundation edit skips the screens", I, "            if other == name or ok not in (SCENARIO, SCREEN, ACCEPTANCE):", "            if other == name or ok not in (SCENARIO, ACCEPTANCE):"),
    # ---- the rebuild
    ("the design index is not rebuilt", I, "    edited[INDEX_NAME] = build_index(edited, design)", "    edited[INDEX_NAME] = files.get(INDEX_NAME, \"\")"),
    ("the files lose their item numbers", I, "    return assemble(edited, previous=previous, highest=", "    return assemble(edited, previous=[], highest="),
    # EQUIVALENT, not tested: `assemble` strips and re-adds the file's trailing newline, so the saved set is the same with or without it on the edited text.
    # ("the file keeps no trailing newline", I, "    edited[name] = text + \"\\n\"", "    edited[name] = text"),
    # ---- the action
    ("a person is not required", H, "        require_person(actor, \"editing a file\")", "        pass"),
    ("any artefact can be edited file by file", H, "        if artefact.type != I.INSTRUCTIONS_KEY:\n            raise ReviewError(f\"{artefact_id} is not a set of instruction files", "        if False:\n            raise ReviewError(f\"{artefact_id} is not a set of instruction files"),
    ("the phase state is not checked", H, "        self._require_phase_state(project_id, artefact.phase_key, EDITABLE_PHASE_STATES, \"a file can be edited\")", "        pass"),
    ("an older base version is accepted", H, "        if based_on != previous.number:\n            raise EditRefused(\n                f\"the edit was not saved: the set is at version", "        if False:\n            raise EditRefused(\n                f\"the edit was not saved: the set is at version"),
    ("a newer base version is accepted but an older one is not", H, "        if based_on != previous.number:\n            raise EditRefused(\n                f\"the edit was not saved: the set is at version", "        if based_on < previous.number:\n            raise EditRefused(\n                f\"the edit was not saved: the set is at version"),
    ("an unknown file is a plain error and not a not-found", H, "            raise NotFoundError(f\"{artefact_id} version {previous.number} has no file", "            raise ReviewError(f\"{artefact_id} version {previous.number} has no file"),
    ("the artefacts own checks are skipped", H, "        problems = [p for p in check_body(body, skill, set(), item_ctx, scanner=self.runtime.scanner) if p not in already]", "        problems = []"),
    ("a problem the set already had blocks the edit", H, "        problems = [p for p in check_body(body, skill, set(), item_ctx, scanner=self.runtime.scanner) if p not in already]", "        problems = list(check_body(body, skill, set(), item_ctx, scanner=self.runtime.scanner))"),
    ("the edited file is not recorded", H, "\"human_edit\": True, \"edited_file\": file_name,", "\"human_edit\": True,"),
    ("the base version is not recorded", H, "\"edited_file\": file_name, \"based_on\": previous.number,", "\"edited_file\": file_name,"),
    ("the note is kept untrimmed", H, "\"edited_file\": file_name, \"based_on\": previous.number, \"note\": (note or \"\").strip()[:1000] or None,", "\"edited_file\": file_name, \"based_on\": previous.number, \"note\": note or None,"),
    ("the author is not the person", H, "project_id, artefact_id, body=body, author=actor, source_chunks=cited_ids(body), generation=generation, links=links, guard=still_open,\n        )\n        return saved.number\n\n    def _resolvable", "project_id, artefact_id, body=body, author=\"system\", source_chunks=cited_ids(body), generation=generation, links=links, guard=still_open,\n        )\n        return saved.number\n\n    def _resolvable"),
    ("a change made while checking is not noticed", H, "            if latest != previous.number:\n                raise EditRefused(\"the edit was not saved: the set changed while", "            if False:\n                raise EditRefused(\"the edit was not saved: the set changed while"),
    ("a phase that closes while checking is not noticed", H, "                raise WrongPhaseState(f\"the edit was not saved: its phase became '{status}' while it was being checked\")\n            latest = conn.execute(\"SELECT MAX(number) AS n FROM artefact_versions WHERE project_id = ? AND artefact_id = ?\", (project_id, artefact_id)).fetchone()[\"n\"]\n            if latest != previous.number:\n                raise EditRefused(\"the edit was not saved: the set changed", "                pass\n            latest = conn.execute(\"SELECT MAX(number) AS n FROM artefact_versions WHERE project_id = ? AND artefact_id = ?\", (project_id, artefact_id)).fetchone()[\"n\"]\n            if latest != previous.number:\n                raise EditRefused(\"the edit was not saved: the set changed"),
    # ---- the route
    ("the file name is not checked", R, "    if not FILE_NAME.match(file_name):", "    if False:"),
    ("the file name allows a path", R, "FILE_NAME = re.compile(r\"^[A-Za-z0-9][A-Za-z0-9._-]{0,78}\\.md$\")", "FILE_NAME = re.compile(r\"^.{1,200}$\")"),
    ("an archived project can be edited", R, "    refuse_if_archived(request, project_id)\n    try:\n        number = request.app.state.human.edit_file(", "    try:\n        number = request.app.state.human.edit_file("),
    ("the person is not named", R, "    actor = actor_from(request)\n    if not _valid(artefact_id, ARTEFACT_ID):\n        raise HTTPException(status_code=422, detail=\"artefact id has unexpected characters\")\n    if not FILE_NAME", "    actor = \"human:anonymous\"\n    if not _valid(artefact_id, ARTEFACT_ID):\n        raise HTTPException(status_code=422, detail=\"artefact id has unexpected characters\")\n    if not FILE_NAME"),
    ("the reasons are not listed", R, "        raise HTTPException(status_code=422, detail={\"message\": str(exc), \"problems\": list(exc.problems)}) from exc\n    except (NotFoundError, ReviewError, InvalidInput) as exc:\n        raise _fail(exc) from exc\n    return {\"artefact_id\": artefact_id, \"file\"", "        raise HTTPException(status_code=422, detail=str(exc)) from exc\n    except (NotFoundError, ReviewError, InvalidInput) as exc:\n        raise _fail(exc) from exc\n    return {\"artefact_id\": artefact_id, \"file\""),
    ("the answer drops the version", R, "return {\"artefact_id\": artefact_id, \"file\": file_name, \"version\": number}", "return {\"artefact_id\": artefact_id, \"file\": file_name}"),
    ("the body allows other fields", R, "class EditFileBody(BaseModel):\n    model_config = ConfigDict(extra=\"forbid\")", "class EditFileBody(BaseModel):\n    model_config = ConfigDict(extra=\"ignore\")"),
    ("a base version of zero is allowed", R, "    based_on: int = Field(ge=1, le=100000)", "    based_on: int = Field(ge=0, le=100000)"),
]

FE = "src"
FRONTEND = [
    ("the client sends the file to the wrong address", f"{FE}/api/client.ts", "/files/${encodeURIComponent(fileName)}`", "/files/${fileName}`"),
    ("the client sends the wrong method", f"{FE}/api/client.ts", "method: 'PUT', headers: { 'Content-Type': 'application/json', ...who(actorName) }, body: JSON.stringify({ text, note, based_on: basedOn }),", "method: 'POST', headers: { 'Content-Type': 'application/json', ...who(actorName) }, body: JSON.stringify({ text, note, based_on: basedOn }),"),
    ("the client leaves out the base version", f"{FE}/api/client.ts", "JSON.stringify({ text, note, based_on: basedOn })", "JSON.stringify({ text, note })"),
    ("the client does not name the person", f"{FE}/api/client.ts", "editFile: async (projectId, artefactId, fileName, actorName, text, note, basedOn) =>\n      decodeEditFileSaved(await call(`/api/projects/${id(projectId)}/artefacts/${id(artefactId)}/files/${encodeURIComponent(fileName)}`, {\n        method: 'PUT', headers: { 'Content-Type': 'application/json', ...who(actorName) }", "editFile: async (projectId, artefactId, fileName, actorName, text, note, basedOn) =>\n      decodeEditFileSaved(await call(`/api/projects/${id(projectId)}/artefacts/${id(artefactId)}/files/${encodeURIComponent(fileName)}`, {\n        method: 'PUT', headers: { 'Content-Type': 'application/json' }"),
    ("the answer is not checked for its version", f"{FE}/api/review.ts", "version: num(o.version, 'file edit.version') }", "version: 0 }"),
    ("the answer is not checked for its file", f"{FE}/api/review.ts", "file: str(o.file, 'file edit.file'),", "file: '',"),
    ("a save always goes to the whole artefact", f"{FE}/state/useProjectScreen.ts", "  if (editingFile !== null) await client.editFile(", "  if (false as boolean) await client.editFile("),
    ("a save always goes to a file", f"{FE}/state/useProjectScreen.ts", "  if (editingFile !== null) await client.editFile(", "  if (true as boolean) await client.editFile("),
    ("the save sends the wrong version", f"{FE}/state/useProjectScreen.ts", "actorName, text, note, version)\n  else", "actorName, text, note, version + 1)\n  else"),
    ("the box holds the whole set when a file is edited", f"{FE}/pages/ProjectPage.tsx", "initialBody={rv.editingFile ? fileText(screen.open.body, rv.editingFile) : screen.open.body}", "initialBody={screen.open.body}"),
    ("the box is not titled with the file", f"{FE}/pages/ProjectPage.tsx", "title={rv.editingFile ?? screen.open.title}", "title={screen.open.title}"),
    ("another file reuses the box text", f"{FE}/pages/ProjectPage.tsx", "<EditArtefact key={rv.editingFile ?? 'whole'}", "<EditArtefact key=\"whole\""),
    ("the file text is read from the wrong file", f"{FE}/lib/instructionSet.ts", "return splitInstructionSet(body).files.find((f) => f.name === name)?.text ?? ''", "return splitInstructionSet(body).files[0]?.text ?? ''"),
    ("the design index can be edited", f"{FE}/lib/instructionSet.ts", "  return name !== '02-design-index.md'", "  return true"),
    ("no file can be edited", f"{FE}/lib/instructionSet.ts", "  return name !== '02-design-index.md'", "  return false"),
    ("the button shows on an old version", f"{FE}/components/ArtefactReader.tsx", "onEditFile={canEdit && a.is_latest ? onEditFile : undefined}", "onEditFile={canEdit ? onEditFile : undefined}"),
    ("the button shows without the right to edit", f"{FE}/components/ArtefactReader.tsx", "onEditFile={canEdit && a.is_latest ? onEditFile : undefined}", "onEditFile={a.is_latest ? onEditFile : undefined}"),
    ("the whole-set button keeps the old name", f"{FE}/components/ArtefactReader.tsx", "{isSet ? 'Edit the whole set' : 'Edit by hand'}", "Edit by hand"),
    ("every artefact says edit the whole set", f"{FE}/components/ArtefactReader.tsx", "{isSet ? 'Edit the whole set' : 'Edit by hand'}", "Edit the whole set"),
    ("the button edits the wrong file", f"{FE}/components/InstructionFiles.tsx", "onClick={() => onEditFile(f.name)}", "onClick={() => onEditFile(files[0].name)}"),
    ("the button is not named for its file", f"{FE}/components/InstructionFiles.tsx", "aria-label={`Edit ${f.name}`}", "aria-label=\"Edit file\""),
    ("the index gets a button", f"{FE}/components/InstructionFiles.tsx", "{onEditFile && canEditFile(f.name) && (", "{onEditFile && ("),
]
