"""Deliberate breaks for S21b (the Word writer, the download route, the two skills, the download links).

Backend:  python -u -m scripts.mutation_check scripts/mutants/s21b_docx_and_downloads.py --tests tests/test_deploy_docx.py tests/test_deploy_download.py tests/test_deploy_skills.py
Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/s21b_docx_and_downloads.py
Run alone: a sweep beside other heavy work gives INVALID ('no output') results.
"""
Wr = "app/deploy/docx_writer.py"
Rt = "app/routes_deploy.py"
Pl = "app/phases/skills/deployment_plan.md"
Rn = "app/phases/skills/release_notes.md"

MUTANTS = [
    # ---- the writer: structure
    ("a heading level is off by one", Wr, "            level = int(t.tag[1])                                    # Markdown has h1 to h6", "            level = int(t.tag[1]) + 1                                    # Markdown has h1 to h6"),
    # REMOVED (dead code): Markdown has only h1 to h6, so a cap of 6 could never apply; the cap was taken out of the writer.
    # ("headings are not capped", Wr, "            level = min(int(t.tag[1]), MAX_HEADING)", "            level = int(t.tag[1])"),
    ("the heading text is lost", Wr, "            _inline(para, tokens[i + 1].children or [])\n            return i + 3\n        if t.type == \"paragraph_open\":", "            return i + 3\n        if t.type == \"paragraph_open\":"),
    # EQUIVALENT, not tested: after a paragraph the writer skips its closing token with `i + 3`; stepping `i + 2` reads the closing token next, which the writer ignores, so the file is the same.
    # ("a paragraph is joined to the next", Wr, "            _inline(para, inline.children or [])\n            return i + 3\n        if t.type in (\"bullet_list_open\"", "            _inline(para, inline.children or [])\n            return i + 2\n        if t.type in (\"bullet_list_open\""),
    ("a bullet list is numbered", Wr, "        base = \"List Bullet\" if kind == \"ul\" else \"List Number\"", "        base = \"List Number\" if kind == \"ul\" else \"List Bullet\""),
    ("nesting is ignored", Wr, "        return base if depth == 1 else f\"{base} {min(depth, 3)}\"", "        return base"),
    ("nesting is not capped", Wr, "f\"{base} {min(depth, 3)}\"", "f\"{base} {depth}\""),
    ("a list never ends", Wr, "            self.list_stack.pop()\n            return i + 1", "            return i + 1"),
    ("a quote is plain text", Wr, "                para = self.doc.add_paragraph(style=QUOTE_STYLE)", "                para = self.doc.add_paragraph()"),
    ("a quote never ends", Wr, "        for t in tokens[:i]:\n            if t.type == \"blockquote_open\":\n                depth += 1\n            elif t.type == \"blockquote_close\":\n                depth -= 1", "        for t in tokens[:i]:\n            if t.type == \"blockquote_open\":\n                depth += 1"),
    ("code is plain text", Wr, "                self.doc.add_paragraph(line, style=CODE_STYLE)", "                self.doc.add_paragraph(line)"),
    ("code loses its blank lines", Wr, "            for line in _clean(t.content).rstrip(\"\\n\").split(\"\\n\") or [\"\"]:", "            for line in [l for l in _clean(t.content).rstrip(\"\\n\").split(\"\\n\") if l]:"),
    ("a rule has no line", Wr, "            para._p.get_or_add_pPr().append(border)", "            pass"),
    ("a table loses its header shading", Wr, "                        _shade(cell, \"E7E6E6\")", "                        pass"),
    ("a table header does not repeat", Wr, "                    _repeat_header(table.rows[r])", "                    pass"),
    ("a table header is not bold", Wr, "                        for run in para.runs:\n                            run.bold = True", "                        pass"),
    ("a table is lost", Wr, "        if width:\n            table = self.doc.add_table(rows=len(rows), cols=width)", "        if False:\n            table = self.doc.add_table(rows=len(rows), cols=width)"),
    # EQUIVALENT, not tested: the Markdown parser pads every table row to the header's width, so `min` and `max` of the row widths are the same number.
    # ("a short row loses its cells", Wr, "        width = max((len(r) for r in rows), default=0)", "        width = min((len(r) for r in rows), default=0)"),
    ("every row is shaded", Wr, "                    if r < header_rows:\n                        for run in para.runs:", "                    if True:\n                        for run in para.runs:"),
    ("raw html is carried", Wr, "        if t.type == \"html_block\":\n            return i + 1                                      # raw HTML is never carried into the Word file", "        if t.type == \"html_block\":\n            self.doc.add_paragraph(t.content)\n            return i + 1"),
    # ---- the writer: inline
    ("bold is lost", Wr, "                run = paragraph.add_run(text)\n                run.bold, run.italic = bool(bold) or None, bool(italic) or None", "                run = paragraph.add_run(text)\n                run.bold, run.italic = None, bool(italic) or None"),
    ("italic is lost", Wr, "                run = paragraph.add_run(text)\n                run.bold, run.italic = bool(bold) or None, bool(italic) or None", "                run = paragraph.add_run(text)\n                run.bold, run.italic = bool(bold) or None, None"),
    ("bold never ends", Wr, "        elif t.type == \"strong_close\":\n            bold -= 1", "        elif t.type == \"strong_close\":\n            pass"),
    ("italic never ends", Wr, "        elif t.type == \"em_close\":\n            italic -= 1", "        elif t.type == \"em_close\":\n            pass"),
    ("inline code has no font", Wr, "            run.font.name = INLINE_CODE_FONT\n            run.bold, run.italic", "            run.bold, run.italic"),
    ("inline code loses bold", Wr, "            run = paragraph.add_run(_clean(t.content))\n            run.font.name = INLINE_CODE_FONT\n            run.bold, run.italic = bool(bold) or None, bool(italic) or None", "            run = paragraph.add_run(_clean(t.content))\n            run.font.name = INLINE_CODE_FONT"),
    ("a line break is lost", Wr, "            paragraph.add_run().add_break(WD_BREAK.LINE if t.type == \"hardbreak\" else WD_BREAK.LINE)", "            pass"),
    ("an image is embedded as text of its address", Wr, "            paragraph.add_run(_clean(t.content or t.attrGet(\"alt\") or \"\"))", "            paragraph.add_run(_clean(t.attrGet(\"src\") or \"\"))"),
    ("inline html is carried", Wr, "        elif t.type in (\"html_inline\",):\n            continue", "        elif t.type in (\"html_inline\",):\n            paragraph.add_run(t.content)"),
    # REMOVED (dead code): the writer only ever passes inline children, so a token with children inside them did not occur; the branch was taken out.
    # ("nested inline tokens are lost", Wr, "        elif t.children:\n            _inline(paragraph, t.children)", "        elif False:\n            _inline(paragraph, t.children)"),
    # ---- the writer: links and safety
    ("every link is live", Wr, "            link = href if SAFE_LINK.match(href) else None", "            link = href"),
    ("no link is live", Wr, "            link = href if SAFE_LINK.match(href) else None", "            link = None"),
    ("mailto is not a link", Wr, "SAFE_LINK = re.compile(r\"^(https?://|mailto:)\", re.IGNORECASE)", "SAFE_LINK = re.compile(r\"^(https?://)\", re.IGNORECASE)"),
    ("http is not a link", Wr, "SAFE_LINK = re.compile(r\"^(https?://|mailto:)\", re.IGNORECASE)", "SAFE_LINK = re.compile(r\"^(https://|mailto:)\", re.IGNORECASE)"),
    ("the link check is case sensitive", Wr, "SAFE_LINK = re.compile(r\"^(https?://|mailto:)\", re.IGNORECASE)", "SAFE_LINK = re.compile(r\"^(https?://|mailto:)\")"),
    # EQUIVALENT, not tested: the check uses `re.match`, which already anchors at the start, so dropping the `^` changes nothing (checked on awkward addresses such as `//evil.example/http://x`).
    # ("the link check matches anywhere", Wr, "SAFE_LINK = re.compile(r\"^(https?://|mailto:)\", re.IGNORECASE)", "SAFE_LINK = re.compile(r\"(https?://|mailto:)\", re.IGNORECASE)"),
    ("an unsafe link is dropped by the parser", Wr, "    parser.validateLink = lambda url: True", "    pass"),
    ("a link keeps its address as text", Wr, "                _hyperlink(paragraph, text, link, bool(bold), bool(italic))", "                _hyperlink(paragraph, link, link, bool(bold), bool(italic))"),
    ("a link loses bold", Wr, "    if bold:\n        props.append(OxmlElement(\"w:b\"))", "    if False:\n        props.append(OxmlElement(\"w:b\"))"),
    ("control characters are kept", Wr, "    return _XML_BAD.sub(\"\", text or \"\")", "    return text or \"\""),
    ("the control character set is too small", Wr, "_XML_BAD = re.compile(\"[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f]\")", "_XML_BAD = re.compile(\"[\\x00]\")"),
    ("the properties are not set", Wr, "    core.title, core.subject, core.author = _clean(info.title)[:255], _clean(info.subject)[:255], _clean(info.author)[:255]", "    pass"),
    ("the title is not cut", Wr, "_clean(info.title)[:255]", "_clean(info.title)"),
    ("the time is not set", Wr, "    core.created = core.modified = info.created or datetime.now(timezone.utc)", "    pass"),
    ("a comment is left", Wr, "    core.comments = \"\"", "    core.comments = info.title"),
    ("the author is a person", Wr, "    author: str = \"SDLC Workbench\"", "    author: str = \"Parag\""),
    ("tables are not read", Wr, "    tokens = parser.parse(_clean(markdown or \"\"))", "    parser = MarkdownIt(\"commonmark\")\n    tokens = parser.parse(_clean(markdown or \"\"))"),
    # ---- the route
    ("the format is not checked", Rt, "    if format not in (\"md\", \"docx\"):\n        raise HTTPException(status_code=422, detail=\"format must be 'md' or 'docx'\")\n    store = request.app.state.store\n    try:\n        project = store.projects.get(project_id)\n        artefact =", "    store = request.app.state.store\n    try:\n        project = store.projects.get(project_id)\n        artefact ="),
    ("an id with odd characters is accepted", Rt, "    if not ARTEFACT_ID.fullmatch(artefact_id):", "    if False:"),
    ("any artefact can be downloaded", Rt, "        if artefact.type not in DOWNLOADABLE:", "        if False:"),
    ("the verification can be downloaded", Rt, "DOWNLOADABLE = (\"deployment_plan\", \"release_notes\", \"runbook\", \"hypercare_plan\")", "DOWNLOADABLE = (\"deployment_plan\", \"release_notes\", \"runbook\", \"hypercare_plan\", \"deployment_verification\")"),
    ("an unwritten artefact is not refused", Rt, "        if artefact.latest_version is None:\n            raise NotFoundError(", "        if False:\n            raise NotFoundError("),
    ("the version is ignored", Rt, "        shown = store.artefacts.get_version(project_id, artefact_id, version)", "        shown = store.artefacts.get_version(project_id, artefact_id)"),
    ("version zero is accepted", Rt, "ge=1, le=100000", "ge=0, le=100000"),
    ("the file name has no version", Rt, "    name = f\"{artefact_id}-v{shown.number}\"", "    name = f\"{artefact_id}\""),
    ("the markdown is changed", Rt, "        return Response(shown.body, media_type=MD_TYPE,", "        return Response(shown.body.upper(), media_type=MD_TYPE,"),
    ("the markdown is not an attachment", Rt, "return Response(shown.body, media_type=MD_TYPE, headers={\"Content-Disposition\": f'attachment; filename=\"{name}.md\"'})", "return Response(shown.body, media_type=MD_TYPE, headers={})"),
    ("the word file is not an attachment", Rt, "created=_when(shown.created_at)))\n    return Response(data, media_type=DOCX_TYPE, headers={\"Content-Disposition\": f'attachment; filename=\"{name}.docx\"'})", "created=_when(shown.created_at)))\n    return Response(data, media_type=DOCX_TYPE, headers={})"),
    ("the word type is wrong", Rt, "DOCX_TYPE = \"application/vnd.openxmlformats-officedocument.wordprocessingml.document\"", "DOCX_TYPE = \"application/octet-stream\""),
    ("the word file title leaves out the project", Rt, "title=f\"{artefact.title} - {project.name}\"", "title=artefact.title"),
    ("the word subject leaves out the version", Rt, "subject=f\"{artefact_id} version {shown.number}\"", "subject=artefact_id"),
    ("the word file is dated now", Rt, ", created=_when(shown.created_at)))", "))"),
    ("an unknown project is not a 404", Rt, "        project = store.projects.get(project_id)\n        artefact = store.artefacts.get(project_id, artefact_id)", "        project = None\n        artefact = store.artefacts.get(project_id, artefact_id)"),
    # ---- the skills
    ("the plan reads the instruction set", Pl, "- artefact: non_functional_requirements\n- artefact: project_charter", "- artefact: non_functional_requirements\n- artefact: build_instructions\n- artefact: project_charter"),
    ("the plan may name a secret", Pl, "- Write a secret, a key, a password, a token, a connection string with credentials, or a real server address.\n", ""),
    ("the plan may claim it was built", Pl, "- Claim the product was built, tested or run.\n", ""),
    ("the plan may name a product", Pl, "- Name a hosting product, a region or a version that no source names.\n", ""),
    ("the plan does not say it is from the design", Pl, "and that this plan comes from the design and not from the code, which was built elsewhere", "and what it is for"),
    ("the plan has no rollback", Pl, "- Rollback\n- Coverage check", "- Coverage check"),
    ("the plan has no steps section", Pl, "- Environments\n- Steps\n", "- Environments\n"),
    ("the plan does not cover components", Pl, "Items: DPL in Steps\nCovers: COMP", "Items: DPL in Steps"),
    ("the notes may invent a version", Rn, "- Invent a version number, a date or a customer.\n", ""),
    ("the notes may describe what was shipped", Rn, "- Describe something the design does not promise, or say a thing was built, tested or shipped.\n", ""),
    ("the notes do not cover requirements", Rn, "Items: REL in What is new\nCovers: FR", "Items: REL in What is new"),
    ("the notes have no known limits", Rn, "- Known limits\n- Upgrade notes", "- Upgrade notes"),
    ("the notes do not read the plan", Rn, "- artefact: deployment_plan\n", ""),
]

E = "src/lib/format.ts"
Ar = "src/components/ArtefactReader.tsx"
Rp = "src/components/RunPanel.tsx"
Pp = "src/pages/ProjectPage.tsx"

FRONTEND = [
    ("the downloadable types change", E, "export const DOWNLOADABLE_TYPES = ['deployment_plan', 'release_notes', 'runbook', 'hypercare_plan'] as const", "export const DOWNLOADABLE_TYPES = ['deployment_plan', 'release_notes', 'runbook', 'hypercare_plan', 'deployment_verification'] as const"),
    ("only the plan is downloadable", E, "export const DOWNLOADABLE_TYPES = ['deployment_plan', 'release_notes', 'runbook', 'hypercare_plan'] as const", "export const DOWNLOADABLE_TYPES = ['deployment_plan'] as const"),
    ("the check accepts a lookalike", E, "(DOWNLOADABLE_TYPES as readonly string[]).includes(type)", "(DOWNLOADABLE_TYPES as readonly string[]).some((t) => type.startsWith(t))"),
    ("the format is not in the address", E, "/download?format=${format}`", "/download`"),
    ("the version is always in the address", E, "return version ? `${base}&version=${version}` : base", "return `${base}&version=${version}`"),
    ("the version is never in the address", E, "return version ? `${base}&version=${version}` : base", "return base"),
    ("the project id is not encoded", E, "`/api/projects/${encodeURIComponent(projectId)}/artefacts/${encodeURIComponent(artefactId)}/download", "`/api/projects/${projectId}/artefacts/${encodeURIComponent(artefactId)}/download"),
    ("the artefact id is not encoded", E, "artefacts/${encodeURIComponent(artefactId)}/download", "artefacts/${artefactId}/download"),
    ("the page shows the links for every artefact", Ar, "      {isDownloadable(a.type) && projectId && (", "      {projectId && ("),
    ("the page shows the links without a project", Ar, "      {isDownloadable(a.type) && projectId && (", "      {isDownloadable(a.type) && ("),
    ("the page links the wrong version", Ar, "downloadPath(projectId, a.id, 'md', a.version)", "downloadPath(projectId, a.id, 'md')"),
    ("the page's word link goes to markdown", Ar, "downloadPath(projectId, a.id, 'docx', a.version)", "downloadPath(projectId, a.id, 'md', a.version)"),
    ("the page's links do not download", Ar, "<a href={downloadPath(projectId, a.id, 'md', a.version)} download className", "<a href={downloadPath(projectId, a.id, 'md', a.version)} className"),
    ("the page does not name the version", Ar, "<span className=\"text-xs text-slate-500\">Version {a.version}:</span>", ""),
    ("the page is not labelled", Ar, "aria-label=\"Download this version\"", ""),
    ("the project page does not pass the project", Pp, "<ArtefactReader artefact={screen.open} projectId={project.id} onClose", "<ArtefactReader artefact={screen.open} onClose"),
    ("the panel shows links for every row", Rp, "                  {projectId && isDownloadable(r.key) && (", "                  {projectId && ("),
    ("the panel links the wrong version", Rp, "downloadPath(projectId, r.artefactId!, 'md', r.version)", "downloadPath(projectId, r.artefactId!, 'md')"),
    ("the panel's word link goes to markdown", Rp, "downloadPath(projectId, r.artefactId!, 'docx', r.version)", "downloadPath(projectId, r.artefactId!, 'md', r.version)"),
    ("the panel's markdown link is not named", Rp, "aria-label={`Download ${names[r.key] ?? r.key} as Markdown`}", ""),
    ("the panel's word link is not named", Rp, "aria-label={`Download ${names[r.key] ?? r.key} as Word`}", ""),
    ("the links come after Read it", Rp, "                  {projectId && isDownloadable(r.key) && (\n                    <span className=\"ml-auto inline-flex items-center gap-1\">", "                  {false && (\n                    <span className=\"ml-auto inline-flex items-center gap-1\">"),
    ("Read it loses its place", Rp, "className={`${(onDownload && r.pieces.length > 0) || (projectId && isDownloadable(r.key)) ? '' : 'ml-auto '}text-xs underline`}", "className=\"text-xs underline\""),
    ("the panel does not get the project", Pp, "downloadNote={screen.downloadNote ?? null} projectId={project.id} />", "downloadNote={screen.downloadNote ?? null} />"),
]
