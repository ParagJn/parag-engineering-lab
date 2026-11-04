"""Deliberate breaks for S22c (the handover sign-off: the list, its wording, the report, the approval record and the page).

Backend:  python -u -m scripts.mutation_check scripts/mutants/s22c_signoff.py --tests tests/test_handover_signoff.py tests/test_checklists.py tests/test_deploy_checklist.py
Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/s22c_signoff.py
Run alone: a sweep beside other heavy work gives INVALID ('no output') results.
"""
Ck = "app/deploy/checks.py"
Cl = "app/deploy/checklist.py"

MUTANTS = [
    # ---- the list
    ("a statement is in the wrong group", Ck, 'Check("SGN-004", "can",', 'Check("SGN-004", "given",'),
    ("a statement is missing", Ck, '    Check("SGN-007", "can", "The support team has the access it needs to the product, its settings and its logs.", ""),\n', ""),
    # EQUIVALENT, not tested: the list checks itself when it is made (the decision must be the one statement of the 'decision' group and the last), so this change stops the module importing at all and cannot ship
    # ("the decision is not the last statement", Ck, 'decision_id="SGN-008"', 'decision_id="SGN-007"'),
    ("the decision is worded as a go", Ck, '"Overall: accept. Support accepts the product', '"Overall: go. Support accepts the product'),
    ("a statement loses its source", Ck, '"The support team has read the runbook and finds it usable for looking after the product.", "the runbook"', '"The support team has read the runbook and finds it usable for looking after the product.", ""'),
    ("the groups are in another order", Ck, 'groups=("given", "can", "decision")', 'groups=("can", "given", "decision")'),
    ("a group title changes", Ck, '"can": "What support can do"', '"can": "What they can do"'),
    ("the title changes", Ck, 'phase="handover", title="Handover sign-off"', 'phase="handover", title="Sign-off"'),
    ("the report title changes", Ck, 'title="Handover sign-off", report_title="Handover sign-off"', 'title="Handover sign-off", report_title="Sign-off"'),
    ("accept is worded as go", Ck, 'answer_words={"go": "Accept", "no_go": "Not accepted", "not_applicable": "Not applicable"}', 'answer_words={"go": "Go", "no_go": "No-go", "not_applicable": "Not applicable"}'),
    ("not accepted is worded as not accepted yet", Ck, '"no_go": "Not accepted"', '"no_go": "Not yet"'),
    ("the open-items key is Deploy's", Ck, 'open_items_key="handover_signoff"', 'open_items_key="deployment_checks"'),
    ("the list is not registered", Ck, 'LISTS: dict = {"deploy": DEPLOY, "handover": HANDOVER}', 'LISTS: dict = {"deploy": DEPLOY}'),
    ("the list is registered under the wrong phase", Ck, '"handover": HANDOVER}', '"build": HANDOVER}'),
    ("a statement ID repeats Deploy's", Ck, 'Check("SGN-001", "given",', 'Check("CHK-001", "given",'),
    # ---- the report
    ("the report totals use Deploy's words", Cl, "{checklist.go} {words['go']}, {checklist.no_go} {words['no_go']}, {checklist.not_applicable} {words['not_applicable']}", "{checklist.go} Go, {checklist.no_go} No-go, {checklist.not_applicable} Not applicable"),
    ("the report decision uses Deploy's words", Cl, 'decision = words[checklist.decision] if checklist.decision else "not recorded yet"', 'decision = ANSWER_WORDS_FALLBACK.get(checklist.decision, "not recorded yet") if checklist.decision else "not recorded yet"'),
    ("the report leaves out the changed answers", Cl, "    if changed:\n", "    if False:\n"),
    ("the report does not say no model was used", Cl, '"This record was filled in by hand. No model was used.", "",', '"", ""'),
]

A = "src/components/ApprovalSummary.tsx"
S = "src/state/useProjectScreen.ts"
R = "src/api/review.ts"

FRONTEND = [
    ("the sign-off is not counted as open", A, "const checks = left(open.deployment_checks) + left(open.handover_signoff)", "const checks = left(open.deployment_checks)"),
    ("deploy's checks are not counted as open", A, "const checks = left(open.deployment_checks) + left(open.handover_signoff)", "const checks = left(open.handover_signoff)"),
    ("only not accepted is counted", A, "c.no_go.length + c.unanswered.length : 0)", "c.no_go.length : 0)"),
    ("only unanswered is counted", A, "c.no_go.length + c.unanswered.length : 0)", "c.unanswered.length : 0)"),
    ("the line says deployment", A, "SIGNOFF_WORDING: ChecksWording = { title: 'Handover sign-off',", "SIGNOFF_WORDING: ChecksWording = { title: 'Deployment checklist',"),
    ("the line says check", A, "noun: 'statement', no_go: 'Not accepted'", "noun: 'check', no_go: 'Not accepted'"),
    ("the line says no-go", A, "noun: 'statement', no_go: 'Not accepted', decision: 'Accept / Not accepted'", "noun: 'statement', no_go: 'No-go', decision: 'Accept / Not accepted'"),
    ("the line asks for a go decision", A, "decision: 'Accept / Not accepted' }", "decision: 'Go / No-go' }"),
    ("the line has no decision note", A, "${checks.decision === null ? `, and no overall ${wording.decision} recorded` : ''}", ""),
    ("the sign-off line is not shown", A, "{open.handover_signoff && checksLine(open.handover_signoff, SIGNOFF_WORDING) && <li>", "{false && <li>"),
    ("the sign-off line uses deploy's words", A, "{checksLine(open.handover_signoff, SIGNOFF_WORDING)} (see the sign-off on this page)", "{checksLine(open.handover_signoff)} (see the sign-off on this page)"),
    ("the sign-off line points at the wrong place", A, "(see the sign-off on this page)", "(see the checklist on this page)"),
    ("the fold starts shut", "src/components/ChecklistPanel.tsx", '<details open className="group">', '<details className="group">'),
    ("the progress leaves the summary", "src/components/ChecklistPanel.tsx", '<span role="status" className={`text-sm font-semibold ${hasNoGo(checklist) ? \'text-rose-800\' : \'text-slate-800\'}`}>{headline(checklist)}</span>\n        </summary>', '</summary><span role="status" className={`text-sm font-semibold ${hasNoGo(checklist) ? \'text-rose-800\' : \'text-slate-800\'}`}>{headline(checklist)}</span>'),
    ("handover does not load its checklist", S, "['deploy', 'handover']", "['deploy']"),
    ("the sign-off record is not decoded", R, "...('handover_signoff' in o ? { handover_signoff: decodeDeploymentChecks(o.handover_signoff, `${w}.handover_signoff`) } : {}),", ""),
    ("the sign-off record is not checked", R, "{ handover_signoff: decodeDeploymentChecks(o.handover_signoff, `${w}.handover_signoff`) }", "{ handover_signoff: o.handover_signoff as never }"),
]
