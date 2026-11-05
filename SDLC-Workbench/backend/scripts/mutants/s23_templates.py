"""Deliberate breaks for S23 Part C (document templates: the folder, the file checks, the table-of-contents reader, the routes, the tab).

Backend:  python -u -m scripts.mutation_check scripts/mutants/s23_templates.py --tests tests/test_templates.py
Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/s23_templates.py
Run alone: a sweep beside other heavy work gives INVALID ('no output') results. Every break works on a COPY of the code; none can reach the real backend/data/Templates.
"""
St = "app/templates/store.py"
Rt = "app/routes_templates.py"
Mn = "app/main.py"
Cf = "app/config.py"

MUTANTS = [
    # ---- the file checks
    ("an empty file is accepted", St, '    if not data:\n        raise TemplateRefused("the file is empty")', "    if False:\n        raise TemplateRefused('')"),
    ("any size is accepted", St, "    if len(data) > MAX_TEMPLATE_BYTES:", "    if False:"),
    ("the size limit is bigger", St, "MAX_TEMPLATE_BYTES = 5 * 1024 * 1024", "MAX_TEMPLATE_BYTES = 500 * 1024 * 1024"),
    ("a non-zip is accepted", St, "    if not zipfile.is_zipfile(io.BytesIO(data)):", "    if False:"),
    ("the unpacked size is not checked", St, "            if sum(i.file_size for i in infos) > MAX_UNPACKED_BYTES:", "            if False:"),
    ("the unpacked limit is bigger", St, "MAX_UNPACKED_BYTES = 50 * 1024 * 1024", "MAX_UNPACKED_BYTES = 50 * 1024 * 1024 * 1024"),
    ("the number of parts is not checked", St, "            if len(infos) > MAX_PARTS:", "            if False:"),
    ("a document with no body is accepted", St, "            if missing:", "            if False:"),
    ("the content types part is not required", St, '_REQUIRED_PARTS = ("[Content_Types].xml", "word/document.xml")', '_REQUIRED_PARTS = ("word/document.xml",)'),
    ("a macro project is accepted", St, "            if any(n.startswith(_FORBIDDEN_PREFIXES) or n in _FORBIDDEN_NAMES for n in names):", "            if False:"),
    ("an embedded object is accepted", St, '_FORBIDDEN_PREFIXES = ("word/vbaProject", "word/embeddings/", "word/activeX/", "customUI/")', '_FORBIDDEN_PREFIXES = ("word/vbaProject", "word/activeX/", "customUI/")'),
    ("an activeX part is accepted", St, '"word/embeddings/", "word/activeX/", "customUI/")', '"word/embeddings/", "customUI/")'),
    ("a custom UI part is accepted", St, '"word/activeX/", "customUI/")', '"word/activeX/")'),
    ("a macro data part is accepted", St, '_FORBIDDEN_NAMES = ("word/vbaData.xml",)', "_FORBIDDEN_NAMES = ()"),
    ("a macro-enabled content type is accepted", St, '            if b"macroEnabled" in content_types or b"vbaProject" in content_types:', "            if False:"),
    ("a template file is accepted", St, '            if b"template.main+xml" in content_types and b"document.main+xml" not in content_types:', "            if False:"),
    ("a damaged package is accepted", St, "            if archive.testzip() is not None:", "            if False:"),
    ("a damaged package crashes", St, "    except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, OSError):", "    except zipfile.BadZipFile:"),
    # ---- the table of contents
    ("a field table of contents is not recognised", St, '    for instr in root.iter(f"{_W}instrText"):\n        if re.match(r"\\s*TOC\\b", instr.text or ""):\n            return True', "    pass"),
    ("a simple-field table of contents is not recognised", St, '    for fld in root.iter(f"{_W}fldSimple"):\n        if re.match(r"\\s*TOC\\b", fld.get(f"{_W}instr", "")):\n            return True', "    pass"),
    ("a content-block table of contents is not recognised", St, '    for gallery in root.iter(f"{_W}docPartGallery"):\n        if "Table of Contents" in (gallery.get(f"{_W}val", "")):\n            return True', "    pass"),
    ("a field that only starts like TOC counts", St, 'if re.match(r"\\s*TOC\\b", instr.text or ""):', 'if re.match(r"\\s*TOC", instr.text or ""):'),
    ("every document has a table of contents", St, "    return False\n\n\ndef _info", "    return True\n\n\ndef _info"),
    ("a broken body counts as having one", St, "    except ET.ParseError:\n        return False", "    except ET.ParseError:\n        return True"),
    ("the table of contents note is wrong", St, '"It has a table of contents, so downloads of this document can use it." if toc else "No table of contents was found in this file, so downloads will use the standard layout."', '"No table of contents was found in this file, so downloads will use the standard layout." if toc else "It has a table of contents, so downloads of this document can use it."'),
    # ---- the folder
    ("a project id can point outside", St, '    if not PROJECT_ID.fullmatch(project_id or ""):', "    if False:"),
    ("a long project id is accepted", St, 'PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")', 'PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]{1,640}$")'),
    ("a slash is allowed in a project id", St, 'PROJECT_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")', 'PROJECT_ID = re.compile(r"^[A-Za-z0-9_/-]{1,64}$")'),
    ("any document type is accepted", St, "    if category not in CATEGORIES:", "    if False:"),
    ("a document type is dropped", St, '    "handover_signoff": "Handover sign-off report",\n', ""),
    ("the types are in another order", St, '    "deployment_plan": "Deployment plan",\n    "release_notes": "Release notes",', '    "release_notes": "Release notes",\n    "deployment_plan": "Deployment plan",'),
    ("the bytes are changed", St, "            handle.write(data)", "            handle.write(data[:-1])"),
    ("the folder is world readable", St, "    os.chmod(target.parent, 0o700)", "    os.chmod(target.parent, 0o755)"),
    ("the file is world readable", St, "        os.chmod(tmp, 0o600)", "        os.chmod(tmp, 0o644)"),
    ("the file is checked after it is stored", St, "    target = _path(root, project_id, category)\n    check_docx(data)\n    target.parent.mkdir(parents=True, exist_ok=True)", "    target = _path(root, project_id, category)\n    target.parent.mkdir(parents=True, exist_ok=True)"),
    ("a failed swap leaves a temporary file", St, "        if os.path.exists(tmp):\n            os.unlink(tmp)\n        raise", "        raise"),
    ("a second upload keeps both", St, "        os.replace(tmp, target)", "        os.rename(tmp, str(target) + '.new')"),
    ("the listing is not in the fixed order", St, "    return [_info(folder / f\"{c}.docx\", c) for c in CATEGORIES if (folder / f\"{c}.docx\").is_file()]", "    return sorted([_info(folder / f\"{c}.docx\", c) for c in CATEGORIES if (folder / f\"{c}.docx\").is_file()], key=lambda t: t.size)"),
    ("a missing template reads as empty", St, '    if not path.is_file():\n        raise TemplateMissing(f"there is no template for {CATEGORIES[category]} in this project")\n    return path.read_bytes()', "    if not path.is_file():\n        return b''\n    return path.read_bytes()"),
    ("removing a missing template is silent", St, '    if not path.is_file():\n        raise TemplateMissing(f"there is no template for {CATEGORIES[category]} in this project")\n    path.unlink()', "    if not path.is_file():\n        return\n    path.unlink()"),
    ("removing removes the folder", St, "    path.unlink()", "    import shutil; shutil.rmtree(path.parent)"),
    ("the payload hides the table of contents", St, '"has_toc": info.has_toc, "toc_note": info.has_toc_note}', '"has_toc": True, "toc_note": info.has_toc_note}'),
    # ---- the routes
    ("anyone may change templates", Rt, '    if not may_change(request):\n        raise HTTPException(status_code=403,', "    if False:\n        raise HTTPException(status_code=403,"),
    ("an Architect may change templates", Rt, 'ALLOWED_ROLES = ("Project Manager", "Administrator")', 'ALLOWED_ROLES = ("Project Manager", "Administrator", "Architect")'),
    ("only an Administrator may change templates", Rt, 'ALLOWED_ROLES = ("Project Manager", "Administrator")', 'ALLOWED_ROLES = ("Administrator",)'),
    ("only a Project Manager may change templates", Rt, 'ALLOWED_ROLES = ("Project Manager", "Administrator")', 'ALLOWED_ROLES = ("Project Manager",)'),
    ("a switched-off person may change templates", Rt, "    return bool(me and me.active and any(r in me.roles for r in ALLOWED_ROLES))", "    return bool(me and any(r in me.roles for r in ALLOWED_ROLES))"),
    ("an unlisted name may change templates", Rt, "    return bool(me and me.active and any(r in me.roles for r in ALLOWED_ROLES))", "    return True"),
    ("an empty list is closed", Rt, "    if users.count_active() == 0:\n        return True", "    if users.count_active() == 0:\n        return False"),
    ("removing needs no role", Rt, "def remove_template(project_id: str, category: str, request: Request) -> dict:\n    actor = _require_change(request)", "def remove_template(project_id: str, category: str, request: Request) -> dict:\n    actor = actor_from(request)"),
    ("uploading needs no role", Rt, "async def upload_template(project_id: str, category: str, request: Request, file: UploadFile = File(...)) -> dict:\n    actor = _require_change(request)", "async def upload_template(project_id: str, category: str, request: Request, file: UploadFile = File(...)) -> dict:\n    actor = actor_from(request)"),
    ("an archived project can be changed", Rt, "    _project(request, project_id)\n    refuse_if_archived(request, project_id)\n    name = (file.filename or \"\").strip()", "    _project(request, project_id)\n    name = (file.filename or \"\").strip()"),
    ("an archived project can lose a template", Rt, "    _project(request, project_id)\n    refuse_if_archived(request, project_id)\n    try:\n        T.remove(", "    _project(request, project_id)\n    try:\n        T.remove("),
    ("any file name is accepted", Rt, '    if not name.lower().endswith(".docx"):', "    if False:"),
    ("a docx-looking name is not case-insensitive", Rt, '    if not name.lower().endswith(".docx"):', '    if not name.endswith(".docx"):'),
    ("the whole upload is read", Rt, "    data = await file.read(T.MAX_TEMPLATE_BYTES + 1)", "    data = await file.read()"),
    ("an upload is not audited", Rt, '    request.app.state.store.audit.append(actor=actor, action="template.uploaded", target_type="template", target_id=f"{project_id}/{category}", project_id=project_id,\n                                         detail={"category": category, "size": info.size, "has_toc": info.has_toc})', "    pass"),
    ("a removal is not audited", Rt, '    request.app.state.store.audit.append(actor=actor, action="template.removed", target_type="template", target_id=f"{project_id}/{category}", project_id=project_id,\n                                         detail={"category": category})', "    pass"),
    ("the audit holds the file name", Rt, 'detail={"category": category, "size": info.size, "has_toc": info.has_toc})', 'detail={"category": category, "size": info.size, "has_toc": info.has_toc, "filename": name})'),
    ("a refusal is a 500", Rt, "    code = 404 if isinstance(exc, T.TemplateMissing) else 422", "    code = 500"),
    ("a missing template is a 422", Rt, "    code = 404 if isinstance(exc, T.TemplateMissing) else 422", "    code = 422"),
    ("an unknown project is not a 404", Rt, "        raise HTTPException(status_code=404, detail=str(exc)) from exc\n\n\ndef may_change", "        raise HTTPException(status_code=400, detail=str(exc)) from exc\n\n\ndef may_change"),
    ("the listing skips the project check", Rt, "def list_templates(project_id: str, request: Request) -> dict:\n    _project(request, project_id)", "def list_templates(project_id: str, request: Request) -> dict:\n    pass"),
    ("the download is not an attachment", Rt, 'headers={"Content-Disposition": f\'attachment; filename="{category}-template.docx"\'})', "headers={})"),
    ("the download has the wrong type", Rt, "DOCX = T.DOCX_TYPE", 'DOCX = "application/octet-stream"'),
    ("the answer hides who may change", Rt, '"can_change": may_change(request),', '"can_change": True,'),
    ("the answer hides the size limit", Rt, '"max_mb": T.MAX_TEMPLATE_BYTES // (1024 * 1024),', '"max_mb": 0,'),
    ("the answer drops the saved template", Rt, 'return {**_answer(request, project_id), "saved": T.payload(info)}', "return _answer(request, project_id)"),
    # ---- where templates live
    ("the folder is not beside the database", Cf, '        return self.db_path.parent / "Templates"', '        return Path(__file__).resolve().parent.parent / "data" / "Templates"'),
    ("the folder has another name", Cf, '        return self.db_path.parent / "Templates"', '        return self.db_path.parent / "templates"'),
    ("the app has no templates folder", Mn, "    app.state.templates_root = cfg.templates_path", "    app.state.templates_root = None"),
    ("the router is not registered", Mn, "    app.include_router(templates_router)\n", ""),
]

L = "src/lib/templates.ts"
P = "src/components/TemplatesPanel.tsx"
A = "src/api/templates.ts"
K = "src/api/client.ts"
C = "src/pages/ConfigurationPage.tsx"

FRONTEND = [
    # ---- the helpers
    ("any name looks like a docx", L, "export const looksLikeDocx = (name: string): boolean => /\\.docx$/i.test(name.trim())", "export const looksLikeDocx = (name: string): boolean => true"),
    ("a docx name is case sensitive", L, "/\\.docx$/i.test(name.trim())", "/\\.docx$/.test(name.trim())"),
    ("the name is not trimmed", L, "/\\.docx$/i.test(name.trim())", "/\\.docx$/i.test(name)"),
    ("a wrong file type is not noticed", L, "  if (!looksLikeDocx(file.name)) return 'A template must be a Word document with a name ending .docx.'", ""),
    ("an empty file is not noticed", L, "  if (file.size === 0) return 'That file is empty.'", ""),
    ("a big file is not noticed", L, "  if (file.size > maxMb * 1024 * 1024) return", "  if (false) return"),
    ("the limit is off by a byte", L, "file.size > maxMb * 1024 * 1024", "file.size >= maxMb * 1024 * 1024"),
    ("a kilobyte is a thousand", L, "  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`", "  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1000)} KB`"),
    ("small sizes are in kilobytes", L, "  if (bytes < 1024) return `${bytes} bytes`", "  if (bytes < 1) return `${bytes} bytes`"),
    ("a bad date is shown as invalid", L, "  if (Number.isNaN(t)) return iso", "  if (false) return iso"),
    ("the date is in local time", L, ", timeZone: 'UTC' })", " })"),
    ("a template counts as usable without a table of contents", L, "usable: have.filter((c) => c.template!.has_toc).length", "usable: have.length"),
    ("the summary forgets the empty case", L, "  if (s.have === 0) return 'No templates yet. Documents use the standard layout.'", ""),
    ("a reader may change templates", L, "export const canChange = (view: Pick<TemplatesView, 'can_change'>, busy: boolean): boolean => view.can_change && !busy", "export const canChange = (view: Pick<TemplatesView, 'can_change'>, busy: boolean): boolean => !busy"),
    ("a busy tab may be changed", L, "view.can_change && !busy", "view.can_change"),
    ("the read-only sentence is lost", L, "'Only a Project Manager or an Administrator can change templates. You can read and download them.'", "''"),
    ("the download address is not encoded", L, "`/api/projects/${encodeURIComponent(projectId)}/templates/${encodeURIComponent(category)}/download`", "`/api/projects/${projectId}/templates/${category}/download`"),
    ("the download address is wrong", L, "/templates/${encodeURIComponent(category)}/download`", "/template/${encodeURIComponent(category)}/download`"),
    ("a change is not shown busy", L, "  ui.setBusy(true); ui.setError(null)\n  try { ui.setView(await what()) }", "  ui.setError(null)\n  try { ui.setView(await what()) }"),
    ("an old error is kept", L, "  ui.setBusy(true); ui.setError(null)\n  try { ui.setView(await what()) }", "  ui.setBusy(true)\n  try { ui.setView(await what()) }"),
    ("the new view is not shown", L, "try { ui.setView(await what()) }", "try { await what() }"),
    ("a refusal is not shown", L, "catch (e) { ui.setError(e instanceof Error ? e.message : 'That could not be done.') }", "catch (e) { ui.setError(null) }"),
    ("an upload goes to the wrong project", L, "upload: (category: string, file: File | Blob, filename: string) => client.uploadTemplate(projectId, category, file, filename, actor)", "upload: (category: string, file: File | Blob, filename: string) => client.uploadTemplate('', category, file, filename, actor)"),
    ("an upload goes to the wrong type", L, "client.uploadTemplate(projectId, category, file, filename, actor)", "client.uploadTemplate(projectId, '', file, filename, actor)"),
    ("an upload sends no name", L, "client.uploadTemplate(projectId, category, file, filename, actor)", "client.uploadTemplate(projectId, category, file, filename, '')"),
    ("a removal removes the wrong type", L, "remove: (category: string) => client.removeTemplate(projectId, category, actor)", "remove: (category: string) => client.removeTemplate(projectId, '', actor)"),
    ("a removal sends no name", L, "client.removeTemplate(projectId, category, actor)", "client.removeTemplate(projectId, category, '')"),
    ("a bad file is still sent", L, "  return { problem, send: !!file && !problem }", "  return { problem, send: !!file }"),
    ("a good file is not sent", L, "  return { problem, send: !!file && !problem }", "  return { problem, send: false }"),
    ("a bad file's problem is lost", L, "  const problem = fileProblem(file, maxMb)\n  return", "  const problem = null as string | null\n  return"),
    ("an upload goes to the wrong type", L, "(file: File) => onUpload(category, file, file.name)", "(file: File) => onUpload('runbook', file, file.name)"),
    ("an upload sends the wrong file name", L, "(file: File) => onUpload(category, file, file.name)", "(file: File) => onUpload(category, file, 'x.docx')"),
    ("a removal removes the wrong type", L, "export const removeFor = (onRemove: (category: string) => void, category: string) => () => onRemove(category)", "export const removeFor = (onRemove: (category: string) => void, category: string) => () => onRemove('runbook')"),
    ("the templates are listed as nobody", L, "client.templates(projectId, actor)", "client.templates(projectId)"),
    ("the templates of another project are listed", L, "client.templates(projectId, actor)", "client.templates('x', actor)"),
    # NOT TESTABLE HERE (recorded, not hidden): the picker's change handler runs on a real file-input event and sets state with a hook; static renders cannot fire it. WHAT it decides (pick) is tested directly. Manual check: choose a .pdf and see the sentence; choose a .docx and see it stored.
    # ("the panel does not use the pick check", P, "const chosen = pick(file, maxMb)", "const chosen = { problem: null, send: true }"),...
    # NOT TESTABLE HERE (recorded, not hidden): same handler: setProblem is React state. The sentence itself (fileProblem) is tested. Manual check: choose a wrong file and read the red line.
    # ("the panel's problem is not shown", P, "setProblem(chosen.problem)", "setProblem(null)"),...
    # NOT TESTABLE HERE (recorded, not hidden): same handler. pick() says send:false for a bad file and is tested. Manual check: choose a .pdf; nothing is uploaded.
    # ("the panel sends even when told not to", P, "if (file && chosen.send) onPick(file)", "if (file) onPick(file)"),...
    # NOT TESTABLE HERE (recorded, not hidden): clearing the input after a choice is a DOM detail of the same handler. Manual check: upload a file, remove it, upload the same file again.
    # ("the panel lets the same file be chosen only once", P, "          e.target.value = ''                                                  // s...
    ("the panel's picker uploads through the wrong helper", P, "onPick={uploadFor(p.onUpload, c.category)} />\n                </div>", "onPick={(f) => p.onUpload('runbook', f, f.name)} />\n                </div>"),
    ("the panel's first picker uploads through the wrong helper", P, "<div className=\"mt-2\"><Picker label={c.label} disabled={off} maxMb={p.view.max_mb} onPick={uploadFor(p.onUpload, c.category)} /></div>", "<div className=\"mt-2\"><Picker label={c.label} disabled={off} maxMb={p.view.max_mb} onPick={(f) => p.onUpload('runbook', f, f.name)} /></div>"),
    ("the panel's remove button removes the wrong type", P, "onClick={removeFor(p.onRemove, c.category)}", "onClick={() => p.onRemove('runbook')}"),
    # NOT TESTABLE HERE (recorded, not hidden): one line of effect wiring in ConfigurationPage (the effect cannot run outside React). What loadTemplates asks for (this project, the typed name) is tested. Manual check: as a Project Manager the buttons are live; as another name they are off.
    # ("the page loads templates through the wrong helper", C, "loadTemplates(client, id, actorName).then((v) => live && setTpl(v))", "client.temp...
    # ---- the decoders and client
    ("a table of contents flag may be text", A, "has_toc: bool(o.has_toc, `${w}.has_toc`)", "has_toc: o.has_toc as boolean"),
    ("the size may be text", A, "size: num(o.size, `${w}.size`)", "size: o.size as number"),
    ("who may change is not read", A, "can_change: bool(o.can_change, 'templates.can_change')", "can_change: true"),
    ("the saved template is not read", A, "  if ('saved' in o) view.saved = decodeTemplateInfo(o.saved, 'templates.saved')", ""),
    ("an empty slot is not allowed", A, "template: nullable(co.template, `templates.categories[${i}].template`, (t, w) => decodeTemplateInfo(t, w))", "template: decodeTemplateInfo(co.template, `templates.categories[${i}].template`)"),
    ("the list is asked as nobody", K, "templates: async (projectId, actorName) => decodeTemplates(await call(`/api/projects/${id(projectId)}/templates`, actorName ? { headers: who(actorName) } : undefined)),", "templates: async (projectId, actorName) => decodeTemplates(await call(`/api/projects/${id(projectId)}/templates`)),"),
    ("an upload is a PUT", K, "{ method: 'POST', headers: who(actorName), body: form }))\n    },\n    removeTemplate", "{ method: 'PUT', headers: who(actorName), body: form }))\n    },\n    removeTemplate"),
    ("an upload sends no name header", K, "`/api/projects/${id(projectId)}/templates/${id(category)}`, { method: 'POST', headers: who(actorName), body: form }", "`/api/projects/${id(projectId)}/templates/${id(category)}`, { method: 'POST', body: form }"),
    ("an upload sets its own content type", K, "{ method: 'POST', headers: who(actorName), body: form }))\n    },\n    removeTemplate", "{ method: 'POST', headers: { 'Content-Type': 'multipart/form-data', ...who(actorName) }, body: form }))\n    },\n    removeTemplate"),
    ("the file is sent under another field", K, "      form.append('file', file, filename)     // no Content-Type: the browser sets the multipart boundary itself\n      return decodeTemplates", "      form.append('upload', file, filename)\n      return decodeTemplates"),
    ("a removal is a POST", K, "templates/${id(category)}`, { method: 'DELETE', headers: who(actorName) })),", "templates/${id(category)}`, { method: 'POST', headers: who(actorName) })),"),
    ("the type is not encoded in the address", K, "templates/${id(category)}`, { method: 'POST'", "templates/${category}`, { method: 'POST'"),
    # ---- the panel
    ("the file picker takes any file", P, 'accept=".docx"', 'accept="*"'),
    ("the file picker is always on", P, "aria-label={`Choose a Word file for ${label}`} disabled={disabled}", "aria-label={`Choose a Word file for ${label}`}"),
    ("the used mark is wrong", P, "{c.template.has_toc ? 'Will be used' : 'Will not be used'}", "{c.template.has_toc ? 'Will not be used' : 'Will be used'}"),
    ("the no-template mark is missing", P, ": <span className=\"rounded-full border border-slate-300 bg-slate-50 px-2 py-0.5 text-[11px] font-semibold text-slate-600\">No template</span>}", ": null}"),
    ("the table of contents sentence is missing", P, '<p className="mt-1 text-sm text-slate-700">{c.template.toc_note}</p>', ""),
    ("the size and date are missing", P, '<p className="mt-1 text-xs text-slate-500">{sizeWords(c.template.size)} · uploaded {whenWords(c.template.uploaded_at)}</p>', ""),
    ("the download link is missing", P, "<a href={downloadPath(p.projectId, c.category)} download", "<a hidden href={downloadPath(p.projectId, c.category)} download"),
    ("the download goes to another type", P, "href={downloadPath(p.projectId, c.category)}", "href={downloadPath(p.projectId, 'runbook')}"),
    ("removal is always on", P, "<button type=\"button\" disabled={off} aria-label={`Remove the ${c.label} template`}", "<button type=\"button\" aria-label={`Remove the ${c.label} template`}"),
    ("the replace sentence is missing", P, '<p className="mt-1 text-xs text-slate-500">Uploading again replaces this one.</p>', ""),
    ("the read-only notice is missing", P, "{notice && <Notice", "{false && <Notice"),
    ("the saved message is missing", P, "{p.view.saved && <Notice", "{false && <Notice"),
    ("a refusal is not shown on the tab", P, "{p.error && <Notice", "{false && <Notice"),
    ("the summary is missing", P, '<p role="status" className="text-sm font-semibold">{summaryWords(p.view)}</p>', ""),
    # ---- the page
    ("the templates tab shows nothing", C, "              templates ?? <Spinner label=\"Loading the templates\" />", "              null"),
]
