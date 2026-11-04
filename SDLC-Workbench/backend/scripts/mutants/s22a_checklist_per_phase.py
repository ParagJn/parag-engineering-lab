"""Deliberate breaks for S22a (the checklist made general: a list per phase, the phase column, phase-aware service, routes, panel and wording).

Backend:  python -u -m scripts.mutation_check scripts/mutants/s22a_checklist_per_phase.py --tests tests/test_checklists.py tests/test_deploy_checklist.py
Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/s22a_checklist_per_phase.py
Run alone: a sweep beside other heavy work gives INVALID ('no output') results.
"""
Ck = "app/deploy/checks.py"
Cl = "app/deploy/checklist.py"
Rt = "app/routes_deploy.py"
Rp = "app/repos.py"
Db = "app/db.py"

MUTANTS = [
    # ---- the record keeps each phase apart
    ("the history ignores the phase", Rp, 'WHERE project_id = ? AND phase = ? ORDER BY id", (project_id, phase))', 'WHERE project_id = ? ORDER BY id", (project_id,))'),
    ("an answer is always saved as deploy", Rp, "(project_id, phase, check_id, answer, note, actor, self._clock()))", '(project_id, "deploy", check_id, answer, note, actor, self._clock()))'),
    ("a blank phase is accepted", Rp, '        phase = _text(phase, "phase")\n', ""),
    ("the repo history defaults to another phase", Rp, 'def history(self, project_id: str, phase: str = "deploy")', 'def history(self, project_id: str, phase: str = "handover")'),
    ("the repo latest defaults to another phase", Rp, 'def latest(self, project_id: str, phase: str = "deploy")', 'def latest(self, project_id: str, phase: str = "handover")'),
    ("the repo answer defaults to another phase", Rp, 'note: str = "", phase: str = "deploy") -> CheckAnswer:', 'note: str = "", phase: str = "handover") -> CheckAnswer:'),
    ("the phase column has no default", Db, "ALTER TABLE deploy_checks ADD COLUMN phase TEXT NOT NULL DEFAULT 'deploy';", "ALTER TABLE deploy_checks ADD COLUMN phase TEXT NOT NULL DEFAULT 'build';"),
    # ---- the service
    ("the checklist is built from another phase's answers", Cl, "history = store.deploy_checks.history(project_id, phase)", "history = store.deploy_checks.history(project_id)"),
    ("an answer is saved without its phase", Cl, "return store.deploy_checks.answer(project_id, check_id, value, actor=actor, note=note, phase=phase)", "return store.deploy_checks.answer(project_id, check_id, value, actor=actor, note=note)"),
    ("the phase state is read from deploy", Cl, "status = store.phases.get(project_id, phase).status", 'status = store.phases.get(project_id, "deploy").status'),
    ("the wrong phase's list is used for the check", Cl, "    spec = C.definition_of(phase)\n    if not isinstance(actor, str)", '    spec = C.definition_of("deploy")\n    if not isinstance(actor, str)'),
    ("a check from another list is accepted", Cl, "    if check_id not in spec.by_id:", "    if False:"),
    # ---- the lists
    ("an unknown phase has a list", Ck, "return LISTS[phase]", "return LISTS.get(phase, DEPLOY)"),
    ("the list does not know its phase", Ck, 'phase="deploy", title="Deployment checklist"', 'phase="other", title="Deployment checklist"'),
    ("the list loses its title", Ck, 'title="Deployment checklist"', 'title=""'),
    # ---- the routes
    ("the payload loses the phase", Rt, '"phase": spec.phase, "title": spec.title, "answer_words": spec.answer_words,', '"title": spec.title, "answer_words": spec.answer_words,'),
    ("the payload loses the title", Rt, '"phase": spec.phase, "title": spec.title, "answer_words": spec.answer_words,', '"phase": spec.phase, "answer_words": spec.answer_words,'),
    ("the payload loses the answer words", Rt, '"phase": spec.phase, "title": spec.title, "answer_words": spec.answer_words,', '"phase": spec.phase, "title": spec.title,'),
    ("a phase without a list is not refused", Rt, "    except KeyError as exc:\n        raise HTTPException(status_code=404, detail=exc.args[0]) from exc", "    except KeyError:\n        return CK.DEPLOY"),
    ("the generic read goes to deploy", Rt, "def get_phase_checklist(project_id: str, phase: str, request: Request) -> dict:\n    return _checklist(phase, project_id, request)", 'def get_phase_checklist(project_id: str, phase: str, request: Request) -> dict:\n    return _checklist("deploy", project_id, request)'),
    ("the generic report goes to deploy", Rt, "def phase_checklist_report(project_id: str, phase: str, request: Request, format: str = Query(default=\"md\")) -> Response:\n    return _report(phase,", "def phase_checklist_report(project_id: str, phase: str, request: Request, format: str = Query(default=\"md\")) -> Response:\n    return _report(\"deploy\","),
    ("the build after an answer is for deploy", Rt, "        return checklist_payload(CL.build(store, project_id, phase))", "        return checklist_payload(CL.build(store, project_id))"),
]

T = "src/api/deploy.ts"
L = "src/lib/checklist.ts"
P = "src/components/ChecklistPanel.tsx"
S = "src/state/useProjectScreen.ts"
K = "src/api/client.ts"
J = "src/pages/ProjectPage.tsx"

FRONTEND = [
    ("the phase is not read", T, "phase: str(o.phase, 'checklist.phase'),", "phase: 'deploy',"),
    ("the title is not read", T, "title: str(o.title, 'checklist.title'),", "title: 'Deployment checklist',"),
    ("the answer words are not read", T, "answer_words: decodeWords(o.answer_words, 'checklist.answer_words'),", "answer_words: { go: 'Go', no_go: 'No-go', not_applicable: 'Not applicable' },"),
    ("a word may be text of any kind", T, "go: str(o.go, `${w}.go`),", "go: o.go as string,"),
    ("a missing no-go word is accepted", T, "no_go: str(o.no_go, `${w}.no_go`),", "no_go: (o.no_go as string) ?? 'No-go',"),
    ("a missing not-applicable word is accepted", T, "not_applicable: str(o.not_applicable, `${w}.not_applicable`)", "not_applicable: (o.not_applicable as string) ?? 'Not applicable'"),
    ("the wording is Deploy's", L, "return list.answer_words[answer]", "return ANSWER_LOOK[answer].word"),
    ("the headline says No-go whatever the list calls it", L, "${wordFor(c, 'no_go')}`)", "No-go`)"),
    ("the headline's decision is Deploy's wording", L, "`overall: ${wordFor(c, c.decision)}`", "`overall: ${ANSWER_LOOK[c.decision].word}`"),
    ("the report is always Deploy's", L, "/${encodeURIComponent(phase)}/checklist/report?format=${format}`", "/deploy/checklist/report?format=${format}`"),
    ("the report phase is not encoded", L, "/${encodeURIComponent(phase)}/checklist/report?format=${format}`", "/${phase}/checklist/report?format=${format}`"),
    ("the report defaults to another phase", L, "format: 'md' | 'docx', phase = 'deploy'", "format: 'md' | 'docx', phase = 'handover'"),
    ("the panel title is Deploy's", P, 'aria-label={checklist.title}', 'aria-label="Deployment checklist"'),
    ("the heading is Deploy's", P, "<h3 className=\"text-base font-bold\">{checklist.title}</h3>", "<h3 className=\"text-base font-bold\">Deployment checklist</h3>"),
    ("the choices use Deploy's words", P, "{wordFor(list, a)}</button>", "{ANSWER_LOOK[a].word}</button>"),
    ("the standing uses Deploy's words", P, "{standing(row, list)} · {who}", "{ANSWER_LOOK[row.latest!.answer].word} · {who}"),
    ("the history uses Deploy's words", P, "{wordFor(list, h.answer)} · {h.by", "{ANSWER_LOOK[h.answer].word} · {h.by"),
    ("the help sentence is Deploy's", P, "Choose {wordFor(checklist, 'go')}, {wordFor(checklist, 'no_go')} or {wordFor(checklist, 'not_applicable')} for each", "Choose Go, No-go or Not applicable for each"),
    ("the approval sentence is Deploy's", P, "A {wordFor(checklist, 'no_go')} does not stop you approving", "A No-go does not stop you approving"),
    ("the md link ignores the phase", P, "reportPath(projectId, 'md', checklist.phase)", "reportPath(projectId, 'md')"),
    ("the docx link ignores the phase", P, "reportPath(projectId, 'docx', checklist.phase)", "reportPath(projectId, 'docx')"),
    ("the client read defaults to another phase", K, "checklist: async (projectId, phase = 'deploy')", "checklist: async (projectId, phase = 'handover')"),
    ("the client answer defaults to another phase", K, "answerCheck: async (projectId, checkId, actorName, answer, note, phase = 'deploy')", "answerCheck: async (projectId, checkId, actorName, answer, note, phase = 'handover')"),
    ("the screen loads the checklist of deploy only", S, "client.checklist(projectId, phaseKey)", "client.checklist(projectId)"),
    ("the screen asks for a checklist for every phase", S, "return checklistWanted(phaseKey) ? client.checklist", "return true ? client.checklist"),
    ("the screen's answer goes to the wrong phase", S, "answerCheckWith(client, ui, projectId, checkId, actorName, answer, note, phaseKey)", "answerCheckWith(client, ui, projectId, checkId, actorName, answer, note)"),
    # NOT TESTABLE YET (recorded, not hidden): this is the one line of hook glue that hands the shown phase to answerForPhase. Hooks cannot run outside React here, and until Handover joins CHECKLIST_PHASES (22c) the shown phase is always 'deploy', so the break changes nothing anyone can observe. Re-check when 22c adds the second phase.
    # ("the screen answers for another phase", S, "projectId, phaseKey, actorName)(checkId, answer, note)", "projectId, 'deploy', actorName)(checkId, answer, note)"),
    ("the answering function drops the phase", S, "ui.setList(await client.answerCheck(projectId, checkId, actorName, answer, note, phase))", "ui.setList(await client.answerCheck(projectId, checkId, actorName, answer, note))"),
    ("the answering function defaults to another phase", S, "answer: Answer, note: string, phase = 'deploy',", "answer: Answer, note: string, phase = 'handover',"),
    ("the checklist phases include everything", S, "CHECKLIST_PHASES.includes(phaseKey)", "true"),
    ("the checklist phases are empty", S, "export const CHECKLIST_PHASES: readonly string[] = ['deploy']", "export const CHECKLIST_PHASES: readonly string[] = []"),
]
