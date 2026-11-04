"""Deliberate breaks for S21c (the manual deployment checklist: the list, the record, the routes, the report, the panel).

Backend:  python -u -m scripts.mutation_check scripts/mutants/s21c_checklist.py --tests tests/test_deploy_checklist.py
Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/s21c_checklist.py
Run alone: a sweep beside other heavy work gives INVALID ('no output') results.
"""
Ck = "app/deploy/checks.py"
Cl = "app/deploy/checklist.py"
Rt = "app/routes_deploy.py"
Rp = "app/repos.py"
Db = "app/db.py"
Hu = "app/review/human.py"
Df = "app/workflow/definitions.py"
Pl = "app/workflow/plan.py"
En = "app/workflow/engine.py"
Pj = "app/routes_projects.py"
Y = "app/phases/definitions/05-deploy.yaml"

MUTANTS = [
    # ---- the list
    # EQUIVALENT, not tested: an assertion at the foot of checks.py (the decision check must exist and be in the 'decision' group) stops the module importing at all with this change, so it cannot ship; nothing for a test to catch.
    # ("the decision is not the last check", Ck, 'DECISION_ID = "CHK-016"                      # the overall Go / No-go, recorded last', 'DECISION_ID = "CHK-015"                      # the overall Go / No-go, recorded last'),
    ("a check is in the wrong group", Ck, 'Check("CHK-005", "before",', 'Check("CHK-005", "ready",'),
    ("a check has no question text", Ck, 'Check("CHK-012", "after", "Nothing in the logs or on the screen looks wrong or alarming.", ""),', 'Check("CHK-012", "after", "", ""),'),
    ("the build check loses its source", Ck, '"Build Verify"),', '""),'),
    ("the groups are in another order", Ck, 'GROUPS = ("ready", "before", "after", "decision")', 'GROUPS = ("before", "ready", "after", "decision")'),
    ("a group title changes", Ck, '"before": "Before the release"', '"before": "Before"'),
    ("the answers lose one", Ck, 'ANSWERS = ("go", "no_go", "not_applicable")', 'ANSWERS = ("go", "no_go")'),
    ("an answer word changes", Ck, '"no_go": "No-go"', '"no_go": "No go"'),
    ("the note limit changes", Ck, "MAX_NOTE_CHARS = 1000", "MAX_NOTE_CHARS = 100000"),
    # ---- the record
    ("an answer may be anything", Rp, "        if answer not in CHECK_ANSWERS:", "        if False:"),
    ("the answers lose not applicable", Rp, 'CHECK_ANSWERS = ("go", "no_go", "not_applicable")', 'CHECK_ANSWERS = ("go", "no_go")'),
    ("a long note is accepted", Rp, "        if len(note) > MAX_CHECK_NOTE:", "        if False:"),
    ("the note is not trimmed", Rp, '        note = (note or "").strip()', '        note = note or ""'),
    ("a blank check id is accepted", Rp, '        check_id = _text(check_id, "check_id")', '        check_id = check_id or ""'),
    ("a non person may answer", Rp, "        check_actor(actor)\n        if answer not in CHECK_ANSWERS:", "        if answer not in CHECK_ANSWERS:"),
    ("an unknown project is accepted", Rp, "            _require_project(conn, project_id)\n            cursor = conn.execute(\"INSERT INTO deploy_checks", "            cursor = conn.execute(\"INSERT INTO deploy_checks"),
    ("the history is newest first", Rp, 'rows = conn.execute("SELECT * FROM deploy_checks WHERE project_id = ? ORDER BY id", (project_id,)).fetchall()', 'rows = conn.execute("SELECT * FROM deploy_checks WHERE project_id = ? ORDER BY id DESC", (project_id,)).fetchall()'),
    ("the history ignores the project", Rp, 'rows = conn.execute("SELECT * FROM deploy_checks WHERE project_id = ? ORDER BY id", (project_id,)).fetchall()', 'rows = conn.execute("SELECT * FROM deploy_checks ORDER BY id").fetchall()'),
    ("the first answer counts", Rp, "        for row in self.history(project_id):\n            out[row.check_id] = row", "        for row in self.history(project_id):\n            out.setdefault(row.check_id, row)"),
    ("answers can be edited", Db, "CREATE TRIGGER deploy_checks_no_update BEFORE UPDATE ON deploy_checks BEGIN SELECT RAISE(ABORT, 'deployment check answers are append-only'); END;", ""),
    ("answers can be deleted", Db, "CREATE TRIGGER deploy_checks_no_delete BEFORE DELETE ON deploy_checks BEGIN SELECT RAISE(ABORT, 'deployment check answers are append-only'); END;", ""),
    ("the database accepts any answer", Db, "CHECK (answer IN ('go', 'no_go', 'not_applicable'))", ""),
    # ---- the checklist
    ("a new checklist is complete", Cl, "        return self.unanswered == 0", "        return True"),
    ("complete ignores the decision", Cl, "        return self.unanswered == 0", "        return self.unanswered <= 1"),
    ("the decision is worked out", Cl, '        return row.latest.answer if row.latest else None', '        return "no_go" if self.no_go else "go"'),
    ("the decision is the wrong check", Cl, "row = next(r for r in self.rows if r.check.id == C.DECISION_ID)", 'row = next(r for r in self.rows if r.check.id == "CHK-001")'),
    ("the totals count history", Cl, '        return sum(1 for r in self.rows if (r.latest.answer if r.latest else None) == answer)', '        return sum(len([h for h in r.history if h.answer == answer]) for r in self.rows)'),
    ("a no go list includes go", Cl, '"no_go": [r.check.id for r in self.rows if r.latest and r.latest.answer == "no_go"],', '"no_go": [r.check.id for r in self.rows if r.latest and r.latest.answer != "not_applicable"],'),
    ("unanswered includes answered", Cl, '"unanswered": [r.check.id for r in self.rows if r.latest is None],', '"unanswered": [r.check.id for r in self.rows],'),
    ("the rows lose their history", Cl, "        rows.append(Row(check, mine[-1] if mine else None, mine))", "        rows.append(Row(check, mine[-1] if mine else None, ()))"),
    ("the latest is the first", Cl, "        rows.append(Row(check, mine[-1] if mine else None, mine))", "        rows.append(Row(check, mine[0] if mine else None, mine))"),
    ("an agent may answer", Cl, '    if not isinstance(actor, str) or not actor.startswith("human:"):', "    if False:"),
    ("an unknown check is accepted", Cl, "    if check_id not in C.BY_ID:", "    if False:"),
    ("a closed phase is accepted", Cl, "    if status not in OPEN_STATES:", "    if False:"),
    ("approved is open", Cl, 'OPEN_STATES = ("running", "awaiting_review")', 'OPEN_STATES = ("running", "awaiting_review", "approved")'),
    ("not started is open", Cl, 'OPEN_STATES = ("running", "awaiting_review")', 'OPEN_STATES = ("not_started", "running", "awaiting_review")'),
    ("awaiting review is closed", Cl, 'OPEN_STATES = ("running", "awaiting_review")', 'OPEN_STATES = ("running",)'),
    ("the wrong phase is checked", Cl, 'PHASE = "deploy"', 'PHASE = "build"'),
    # ---- the report
    ("the report hides the decision", Cl, '        f"**Overall decision:** {decision}", "",', '        "",'),
    ("the report says a decision when there is none", Cl, 'decision = C.ANSWER_WORDS[checklist.decision] if checklist.decision else "not recorded yet"', 'decision = C.ANSWER_WORDS[checklist.decision] if checklist.decision else "Go"'),
    ("the report forgets it was by hand", Cl, '        "This record was filled in by hand. No model was used.", "",', ""),
    ("the report miscounts the answered", Cl, "{checklist.total - checklist.unanswered} of {checklist.total} checks answered", "{checklist.total} of {checklist.total} checks answered"),
    ("the report leaves out a group", Cl, "    for group in C.GROUPS:\n        rows = [r for r in checklist.rows if r.check.group == group]", "    for group in C.GROUPS[:-1]:\n        rows = [r for r in checklist.rows if r.check.group == group]"),
    ("the report shows who by the raw name", Cl, 'a.actor.removeprefix("human:") if a else ""', 'a.actor if a else ""'),
    ("a pipe breaks the report table", Cl, 'c.replace("|", "\\\\|").replace("\\n", " ") for c in cells', 'c for c in cells'),
    ("a line break breaks the report table", Cl, '.replace("\\n", " ") for c in cells', ' for c in cells'),
    ("the report hides changed answers", Cl, "    if changed:\n        lines += [\"## Answers that were changed\", \"\"]", "    if False:\n        lines += [\"## Answers that were changed\", \"\"]"),
    ("changed answers lose their order", Cl, 'for h in r.history)', 'for h in reversed(r.history))'),
    # ---- the routes
    ("the checklist needs a name to read", Rt, "def get_checklist(project_id: str, request: Request) -> dict:\n    try:", "def get_checklist(project_id: str, request: Request) -> dict:\n    actor_from(request)\n    try:"),
    ("an answer needs no name", Rt, "def answer_check(project_id: str, check_id: str, body: AnswerBody, request: Request) -> dict:\n    actor = actor_from(request)", "def answer_check(project_id: str, check_id: str, body: AnswerBody, request: Request) -> dict:\n    actor = 'human:anonymous'"),
    ("a check id with odd characters is accepted", Rt, '    if not re.fullmatch(r"CHK-\\d{3}", check_id):', "    if False:"),
    ("an archived project can be answered", Rt, "    refuse_if_archived(request, project_id)\n    store = request.app.state.store\n    try:\n        CL.answer(", "    store = request.app.state.store\n    try:\n        CL.answer("),
    ("other fields are allowed", Rt, "class AnswerBody(BaseModel):\n    model_config = ConfigDict(extra=\"forbid\")", "class AnswerBody(BaseModel):\n    model_config = ConfigDict(extra=\"ignore\")"),
    # CLOSED BY A TEST of where the refusal comes from (a list from the request check, not a string from the record): the next test pins that.
    # ("the note limit is lifted", Rt, "note: str = Field(default=\"\", max_length=CK.MAX_NOTE_CHARS)", "note: str = Field(default=\"\", max_length=1000000)"),
    ("a closed phase is a 500", Rt, "    except WrongPhaseState as exc:\n        raise HTTPException(status_code=409, detail=str(exc)) from exc", "    except WrongPhaseState as exc:\n        raise HTTPException(status_code=500, detail=str(exc)) from exc"),
    ("a refusal is a 200", Rt, "    except (PersonRequired, InvalidInput) as exc:\n        raise HTTPException(status_code=422, detail=str(exc)) from exc", "    except (PersonRequired, InvalidInput) as exc:\n        return {}"),
    ("an unknown check is a 422", Rt, "        raise HTTPException(status_code=404, detail=str(exc)) from exc\n    except WrongPhaseState", "        raise HTTPException(status_code=422, detail=str(exc)) from exc\n    except WrongPhaseState"),
    ("the payload hides the history", Rt, '"latest": answer_payload(r.latest) if r.latest else None, "history": [answer_payload(h) for h in r.history]}', '"latest": answer_payload(r.latest) if r.latest else None, "history": []}'),
    ("the payload hides who answered", Rt, 'return {"answer": a.answer, "note": a.note, "by": a.actor, "at": a.at}', 'return {"answer": a.answer, "note": a.note, "by": "", "at": a.at}'),
    ("the payload hides the totals", Rt, '"totals": {"total": checklist.total, "go": checklist.go, "no_go": checklist.no_go, "not_applicable": checklist.not_applicable, "unanswered": checklist.unanswered},', '"totals": {"total": 0, "go": 0, "no_go": 0, "not_applicable": 0, "unanswered": 0},'),
    ("the payload hides the decision", Rt, '"decision": checklist.decision, "complete"', '"decision": None, "complete"'),
    ("the report format is not checked", Rt, '    if format not in ("md", "docx"):\n        raise HTTPException(status_code=422, detail="format must be \'md\' or \'docx\'")\n    store = request.app.state.store\n    try:\n        project = store.projects.get(project_id)\n        text = CL.report_markdown', '    store = request.app.state.store\n    try:\n        project = store.projects.get(project_id)\n        text = CL.report_markdown'),
    ("the report is not an attachment", Rt, "headers={\"Content-Disposition\": 'attachment; filename=\"deployment-verification.md\"'})", "headers={})"),
    ("the report word file has no title", Rt, 'title=f"Deployment verification - {project.name}", subject="Deployment verification checklist"', 'title="", subject=""'),
    ("the report is made from other text", Rt, "    data = markdown_to_docx(text, DocInfo(title=f\"Deployment verification", "    data = markdown_to_docx(text.upper(), DocInfo(title=f\"Deployment verification"),
    # ---- done by hand (a checklist artefact: no agent, no skill, never run, never required)
    ("an unknown kind is accepted", Df, '    if kind not in KINDS:', '    if False:'),
    ("a by hand artefact may have a role", Df, '("role", "role" in raw), ', ""),
    ("a by hand artefact may be required", Df, '("required", required), ', ""),
    ("a by hand artefact may wait for another", Df, '("after", bool(after)), ', ""),
    # REMOVED (redundant code): switching a by-hand artefact off needs a reason, and a reason is already refused for it, so the separate check was taken out of the loader.
    # ("a by hand artefact may be switched off", Df, '        if not enabled:\n            raise CatalogueError(f"{where}: a \'kind: checklist\' artefact cannot be switched off")', "        pass"),
    ("a by hand artefact still needs a role", Df, '    role = "" if kind == "checklist" else _text(raw, "role", where)', '    role = _text(raw, "role", where)'),
    ("a role is not checked for the others", Df, "        if not item.by_hand and item.role not in roles:", "        if False:"),
    ("something may wait for a by hand artefact", Df, '                if next(a for a in artefacts if a.key == dependency).by_hand:', "                if False:"),
    ("by hand is the default kind", Df, 'kind = raw.get("kind", "written")', 'kind = raw.get("kind", "checklist")'),
    ("a by hand artefact is planned", Pl, "    usable = {a.key for a in phase.artefacts if a.enabled and not a.by_hand}", "    usable = {a.key for a in phase.artefacts if a.enabled}"),
    ("a by hand artefact can be chosen", Pl, "    hand = [a for a in phase.artefacts if a.key in enabled and a.by_hand]\n    if hand:", "    hand = []\n    if hand:"),
    ("the by hand list is the written ones", Pl, "        return tuple(a for a in self.phase.artefacts if a.by_hand)", "        return tuple(a for a in self.phase.artefacts if not a.by_hand)"),
    ("the snapshot hides the by hand artefacts", En, "                    by_hand=tuple(ByHandState(a.key, a.name, a.description) for a in phase.by_hand),\n", ""),
    ("the project hides the by hand artefacts", Pj, '                "by_hand": [{"key": a.key, "name": a.name, "description": a.description} for a in p.by_hand],\n            }\n            for p in snapshot.phases', '                "by_hand": [],\n            }\n            for p in snapshot.phases'),
    ("the plan hides the by hand artefacts", Pj, '                "by_hand": [{"key": a.key, "name": a.name, "description": a.description} for a in p.by_hand],\n            }\n            for p in plan.phases', '                "by_hand": [],\n            }\n            for p in plan.phases'),
    ("the catalogue hides the by hand flag", Pj, '"disabled_reason": a.disabled_reason, "by_hand": a.by_hand}', '"disabled_reason": a.disabled_reason, "by_hand": False}'),
    ("the verification is written again", Y, "    kind: checklist\n", ""),
    ("the verification is required again", Y, "    kind: checklist\n    description:", "    kind: checklist\n    required: true\n    description:"),
    # ---- the open items at approval
    ("the checks are in every phase's open items", Hu, "        if phase_key == DEPLOY_PHASE:", "        if True:"),
    ("the checks are never in the open items", Hu, "        if phase_key == DEPLOY_PHASE:", "        if False:"),
]

T = "src/api/deploy.ts"
L = "src/lib/checklist.ts"
P = "src/components/ChecklistPanel.tsx"
A = "src/components/ApprovalSummary.tsx"
S = "src/state/useProjectScreen.ts"
J = "src/pages/ProjectPage.tsx"
R = "src/api/review.ts"
K = "src/api/client.ts"

FRONTEND = [
    ("a group title may be anything", T, "title: str(go.title, `${w}.title`),", "title: go.title as string,"),
    ("an unknown answer is accepted", T, "answer: oneOf(o.answer, `${w}.answer`, ANSWERS)", "answer: str(o.answer, `${w}.answer`) as never"),
    ("the history is not decoded", T, "history: arr(co.history, `${cw}.history`).map((h, k) => decodeGiven(h, `${cw}.history[${k}]`)),", "history: [],"),
    ("a total may be text", T, "total: num(t.total, 'checklist.totals.total')", "total: t.total as number"),
    ("the decision may be anything", T, "decision: nullable(o.decision, 'checklist.decision', (v, w) => oneOf(v, w, ANSWERS))", "decision: o.decision as never"),
    ("a go has no word", L, "go: { word: 'Go',", "go: { word: '',"),
    ("a no go is green", L, "no_go: { word: 'No-go', box: 'border-rose-400 bg-rose-50 text-rose-900',", "no_go: { word: 'No-go', box: 'border-emerald-400 bg-emerald-50 text-emerald-900',"),
    ("not applicable looks like go", L, "not_applicable: { word: 'Not applicable', box: 'border-slate-400 bg-slate-100 text-slate-800',", "not_applicable: { word: 'Not applicable', box: 'border-emerald-400 bg-emerald-50 text-emerald-900',"),
    ("the choices are in another order", L, "export const ANSWER_CHOICES: Answer[] = ['go', 'no_go', 'not_applicable']", "export const ANSWER_CHOICES: Answer[] = ['no_go', 'go', 'not_applicable']"),
    ("an unanswered check says nothing", L, "return row.latest ? wordFor(list, row.latest.answer) : 'Not answered'", "return row.latest ? wordFor(list, row.latest.answer) : ''"),
    ("the name keeps its mark", L, "return row.latest ? `${row.latest.by.replace(/^human:/, '')} · ${row.latest.at}` : null", "return row.latest ? `${row.latest.by} · ${row.latest.at}` : null"),
    ("one answer has a history", L, "export const hasHistory = (row: CheckRow): boolean => row.history.length > 1", "export const hasHistory = (row: CheckRow): boolean => row.history.length > 0"),
    ("the headline counts the total", L, "const answered = c.totals.total - c.totals.unanswered", "const answered = c.totals.total"),
    ("the headline hides no go", L, "if (c.totals.no_go > 0) parts.push(`${c.totals.no_go} ${wordFor(c, 'no_go')}`)", ""),
    ("the headline invents a decision", L, "parts.push(c.decision === null ? 'no overall decision yet' : `overall: ${wordFor(c, c.decision)}`)", "parts.push(`overall: Go`)"),
    ("no go is not noticed", L, "export const hasNoGo = (c: Checklist): boolean => c.totals.no_go > 0", "export const hasNoGo = (c: Checklist): boolean => false"),
    ("the report address is wrong", L, "/${encodeURIComponent(phase)}/checklist/report?format=${format}`", "/${encodeURIComponent(phase)}/checklist?format=${format}`"),
    ("the report address leaves the project unencoded", L, "`/api/projects/${encodeURIComponent(projectId)}/${encodeURIComponent(phase)}/checklist/report", "`/api/projects/${projectId}/${encodeURIComponent(phase)}/checklist/report"),
    ("a choice can be pressed without a name", P, "<button key={a} type=\"button\" disabled={!canAnswer || busy}", "<button key={a} type=\"button\" disabled={busy}"),
    ("a choice can be pressed while saving", P, "<button key={a} type=\"button\" disabled={!canAnswer || busy}", "<button key={a} type=\"button\" disabled={!canAnswer}"),
    ("the chosen answer is not marked", P, "aria-pressed={on}", "aria-pressed={false}"),
    ("a choice sends the wrong answer", P, "onClick={() => onAnswer(row.id, a, note)}", "onClick={() => onAnswer(row.id, 'go', note)}"),
    ("a choice sends the wrong check", P, "onClick={() => onAnswer(row.id, a, note)}", "onClick={() => onAnswer('CHK-001', a, note)}"),
    ("a choice drops the note", P, "onClick={() => onAnswer(row.id, a, note)}", "onClick={() => onAnswer(row.id, a, '')}"),
    ("the saved note is not the start", P, "const [note, setNote] = useState(row.latest?.note ?? '')", "const [note, setNote] = useState('')"),
    ("the note box can be used without a name", P, "placeholder=\"Note (optional)\" disabled={!canAnswer}", "placeholder=\"Note (optional)\""),
    ("who answered is not shown", P, "{who && <p className=\"mt-1 text-xs text-slate-500\">", "{false && <p className=\"mt-1 text-xs text-slate-500\">"),
    ("the history is always shown", P, "{hasHistory(row) && (", "{true && ("),
    ("the history is open", P, "<details className=\"mt-1 text-xs text-slate-600\">\n          <summary className=\"cursor-pointer font-semibold\">History", "<details open className=\"mt-1 text-xs text-slate-600\">\n          <summary className=\"cursor-pointer font-semibold\">History"),
    ("the history is out of order", P, "{row.history.map((h, i) =>", "{[...row.history].reverse().map((h, i) =>"),
    ("a no go says nothing about approval", P, "{hasNoGo(checklist) && <p className=\"text-xs text-slate-600\">A {wordFor(checklist, 'no_go')} does not stop you approving the phase, but it is recorded with your approval.</p>}", ""),
    ("the reason for a closed panel is lost", P, "{!canAnswer && <p className=\"text-xs text-slate-500\">", "{false && <p className=\"text-xs text-slate-500\">"),
    ("a failed answer is not shown", P, "{error && <Notice tone=\"error\" title=\"That answer was not saved\">{error}</Notice>}", ""),
    ("the report links show without a project", P, "      {projectId && (\n        <div aria-label=\"Download the report\"", "      {true && (\n        <div aria-label=\"Download the report\""),
    ("the report links are missing", P, "      {projectId && (\n        <div aria-label=\"Download the report\"", "      {false && (\n        <div aria-label=\"Download the report\""),
    ("the word link goes to markdown", P, "href={reportPath(projectId, 'docx', checklist.phase)}", "href={reportPath(projectId, 'md', checklist.phase)}"),
    ("the report links do not download", P, "<a href={reportPath(projectId, 'md', checklist.phase)} download className", "<a href={reportPath(projectId, 'md', checklist.phase)} className"),
    ("the checks are not counted as open", A, "const checks = open.deployment_checks ? open.deployment_checks.no_go.length + open.deployment_checks.unanswered.length : 0", "const checks = 0"),
    ("only no go counts as open", A, "open.deployment_checks.no_go.length + open.deployment_checks.unanswered.length", "open.deployment_checks.no_go.length"),
    ("only unanswered counts as open", A, "open.deployment_checks.no_go.length + open.deployment_checks.unanswered.length", "open.deployment_checks.unanswered.length"),
    ("the line is not shown", A, "{open.deployment_checks && checksLine(open.deployment_checks) && <li>", "{false && <li>"),
    ("the line hides the no go ids", A, "parts.push(`${count(checks.no_go.length, 'check')} marked No-go (${checks.no_go.join(', ')})`)", "parts.push(`${count(checks.no_go.length, 'check')} marked No-go`)"),
    ("the line hides what is unanswered", A, "if (checks.unanswered.length > 0) parts.push(", "if (false) parts.push("),
    ("the line forgets a missing decision", A, "${checks.decision === null ? ', and no overall Go / No-go recorded' : ''}", ""),
    ("the line says a missing decision when there is one", A, "${checks.decision === null ? ", "${checks.decision !== null ? "),
    ("an empty checklist still has a line", A, "return parts.length > 0 ? `Deployment checklist:", "return parts.length >= 0 ? `Deployment checklist:"),
    ("the checks block is required", R, "...('deployment_checks' in o ? { deployment_checks: decodeDeploymentChecks(o.deployment_checks, `${w}.deployment_checks`) } : {}),", "deployment_checks: decodeDeploymentChecks(o.deployment_checks, `${w}.deployment_checks`),"),
    ("the checks block is ignored", R, "...('deployment_checks' in o ? { deployment_checks: decodeDeploymentChecks(o.deployment_checks, `${w}.deployment_checks`) } : {}),", ""),
    ("the checks decision may be anything", R, "decision: nullable(o.decision, `${w}.decision`, (v, vw) => oneOf(v, vw, ['go', 'no_go', 'not_applicable'] as const)) }", "decision: o.decision as never }"),
    ("the checklist loads for every phase", S, "export const checklistWanted = (phaseKey: string): boolean => CHECKLIST_PHASES.includes(phaseKey)", "export const checklistWanted = (phaseKey: string): boolean => true"),
    ("the checklist never loads", S, "export const checklistWanted = (phaseKey: string): boolean => CHECKLIST_PHASES.includes(phaseKey)", "export const checklistWanted = (phaseKey: string): boolean => false"),
    ("the checklist loads for deploy and one more", S, "export const checklistWanted = (phaseKey: string): boolean => CHECKLIST_PHASES.includes(phaseKey)", "export const checklistWanted = (phaseKey: string): boolean => CHECKLIST_PHASES.includes(phaseKey) || phaseKey === 'build'"),
    ("a saved answer does not refresh the page", S, "    ui.setList(await client.answerCheck(projectId, checkId, actorName, answer, note, phase))\n    await ui.refresh()", "    ui.setList(await client.answerCheck(projectId, checkId, actorName, answer, note, phase))"),
    ("a saved answer is not shown", S, "    ui.setList(await client.answerCheck(projectId, checkId, actorName, answer, note, phase))\n    await ui.refresh()", "    await client.answerCheck(projectId, checkId, actorName, answer, note, phase)\n    await ui.refresh()"),
    ("a failure is hidden", S, "    ui.setError(message(e, 'That answer could not be saved.'))", "    ui.setError(null)"),
    ("busy is never cleared", S, "  } finally {\n    ui.setBusy(null)\n  }\n}\n\n/** The note about a download:", "  } finally {\n  }\n}\n\n/** The note about a download:"),
    ("an old error stays", S, "  ui.setBusy(checkId)\n  ui.setError(null)", "  ui.setBusy(checkId)"),
    ("the page shows the checklist for every phase", J, "{checklistWanted(phase.key) && screen.checklist && (", "{screen.checklist && ("),
    ("the page never shows the checklist", J, "{checklistWanted(phase.key) && screen.checklist && (", "{false && screen.checklist && ("),
    ("the page lets anyone answer", J, "canAnswer={canChange && (phase.status === 'running' || phase.status === 'awaiting_review')}", "canAnswer"),
    ("the page lets a name alone answer", J, "canAnswer={canChange && (phase.status === 'running' || phase.status === 'awaiting_review')}", "canAnswer={canChange}"),
    ("the page opens answering after approval", J, "(phase.status === 'running' || phase.status === 'awaiting_review')} busy=", "(phase.status !== 'not_started')} busy="),
    ("the by hand card is not shown", J, "              {phase.by_hand.map((b) => <ByHandCard key={b.key} name={b.name} description={b.description} progress={screen.checklist ? headline(screen.checklist) : null} />)}", ""),
    ("the by hand card never shows progress", J, "progress={screen.checklist ? headline(screen.checklist) : null} />)}", "progress={null} />)}"),
    ("the by hand count is hidden", J, "{phase.by_hand.length > 0 ? ` · ${phase.by_hand.length} done by hand` : ''}", ""),
    ("the by hand card is counted with the written ones", J, "{count(phase.artefacts.length, 'artefact')}", "{count(phase.artefacts.length + phase.by_hand.length, 'artefact')}"),
    ("the by hand card says nothing is needed", "src/components/ArtefactCard.tsx", "Use the checklist below; no model is involved.", ""),
    ("the by hand card has no badge", "src/components/ArtefactCard.tsx", "Done by hand</span>", "</span>"),
    ("the by hand card can be pressed", "src/components/ArtefactCard.tsx", "    <li aria-label={`${name}: done by hand`} className=", "    <li onClick={() => undefined} role=\"button\" aria-label={`${name}: done by hand`} className="),
    ("the by hand card is not labelled", "src/components/ArtefactCard.tsx", "aria-label={`${name}: done by hand`}", "aria-label={name}"),
    ("the wizard ticks a by hand artefact", "src/lib/wizard.ts", "p.artefacts.filter((a) => a.enabled && !a.by_hand).map((a) => a.key)])),", "p.artefacts.filter((a) => a.enabled).map((a) => a.key)])),"),
    ("the wizard toggles a by hand artefact", "src/lib/wizard.ts", "artefact.required || !artefact.enabled || artefact.by_hand", "artefact.required || !artefact.enabled"),
    ("the wizard offers a box for a by hand artefact", "src/pages/WizardPage.tsx", "{phase.artefacts.filter((a) => a.enabled && !a.by_hand).map((a) => {", "{phase.artefacts.filter((a) => a.enabled).map((a) => {"),
    ("the wizard does not list the by hand artefact", "src/pages/WizardPage.tsx", "{phase.artefacts.some((a) => a.by_hand) && (", "{false && ("),
    ("the by hand flag is not decoded", T if False else "src/api/types.ts", "by_hand: bool(o.by_hand, `${w}.by_hand`) }", "by_hand: false }"),
    ("the plan's by hand list is not decoded", "src/api/types.ts", "      by_hand: byHand(po.by_hand, `${w}.by_hand`),\n    }\n  }) }", "      by_hand: [],\n    }\n  }) }"),
    ("the project's by hand list is not decoded", "src/api/types.ts", "        by_hand: byHand(po.by_hand, `${w}.by_hand`),\n      }\n    }),", "        by_hand: [],\n      }\n    }),"),
    ("the page does not pass the project", J, "onAnswer={screen.onAnswerCheck ?? (() => {})} projectId={project.id} />", "onAnswer={screen.onAnswerCheck ?? (() => {})} />"),
    ("the checklist call goes to the wrong address", K, "`/api/projects/${id(projectId)}/${id(phase)}/checklist`)),", "`/api/projects/${id(projectId)}/deploy`)),"),
    ("an answer is a post", K, "      decodeChecklist(await call(`/api/projects/${id(projectId)}/${id(phase)}/checklist/${id(checkId)}`, {\n        method: 'PUT',", "      decodeChecklist(await call(`/api/projects/${id(projectId)}/${id(phase)}/checklist/${id(checkId)}`, {\n        method: 'POST',"),
    ("an answer drops the note", K, "body: JSON.stringify({ answer, note }),\n      })),\n    verifyRuns:", "body: JSON.stringify({ answer }),\n      })),\n    verifyRuns:"),
    ("an answer drops the name", K, "method: 'PUT', headers: { 'Content-Type': 'application/json', ...who(actorName) }, body: JSON.stringify({ answer, note }),", "method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answer, note }),"),
]
