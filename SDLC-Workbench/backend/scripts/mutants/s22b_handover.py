"""Deliberate breaks for S22b (BAU handover: the definition, the runbook and hypercare skills, the downloads, the traceability names).

Backend:  python -u -m scripts.mutation_check scripts/mutants/s22b_handover.py --tests tests/test_handover_skills.py tests/test_deploy_download.py tests/test_catalogue.py tests/test_plan.py tests/test_agent_skills.py tests/test_traceability.py
Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/s22b_handover.py
Run alone: a sweep beside other heavy work gives INVALID ('no output') results.
"""
Y = "app/phases/definitions/06-handover.yaml"
Rb = "app/phases/skills/runbook.md"
Hy = "app/phases/skills/hypercare_plan.md"
Rt = "app/routes_deploy.py"

MUTANTS = [
    # ---- the definition
    ("the runbook is optional", Y, "    id_prefix: HND-RUN\n    role: handover_author\n    required: true", "    id_prefix: HND-RUN\n    role: handover_author"),
    ("the hypercare plan is optional", Y, "    required: true\n    after: [runbook]", "    after: [runbook]"),
    ("the hypercare plan does not wait for the runbook", Y, "    required: true\n    after: [runbook]", "    required: true"),
    ("the sign-off is written by an agent", Y, "    id_prefix: HND-SGN\n    kind: checklist", "    id_prefix: HND-SGN\n    role: handover_author"),
    ("the support guide is switched on", Y, "    id_prefix: HND-SUP\n    role: handover_author\n    enabled: false", "    id_prefix: HND-SUP\n    role: handover_author\n    enabled: true"),
    ("the support guide loses its reason", Y, "Not enabled. Not needed yet; the runbook covers day-to-day problems. It can be switched on later.", ""),
    ("the alerts are switched on", Y, "    id_prefix: HND-SLO\n    role: handover_author\n    enabled: false", "    id_prefix: HND-SLO\n    role: handover_author\n    enabled: true"),
    ("the knowledge-transfer pack is switched on", Y, "    id_prefix: HND-KT\n    role: handover_author\n    enabled: false", "    id_prefix: HND-KT\n    role: handover_author\n    enabled: true"),
    ("the runbook's prefix changes", Y, "id_prefix: HND-RUN", "id_prefix: HND-RB"),
    ("the runbook uses another role", Y, "    id_prefix: HND-RUN\n    role: handover_author", "    id_prefix: HND-RUN\n    role: devops_engineer"),
    # ---- the runbook skill
    ("the runbook reads the instruction set", Rb, "- artefact: project_charter\n- artefact: deployment_plan", "- artefact: project_charter\n- artefact: build_instructions\n- artefact: deployment_plan"),
    ("the runbook does not read the deployment plan", Rb, "- artefact: deployment_plan\n", ""),
    ("the runbook does not read the release notes", Rb, "- artefact: release_notes\n", ""),
    ("the runbook does not cover components", Rb, "Items: RUN in Routine care\nCovers: COMP", "Items: RUN in Routine care"),
    ("the runbook has no recovery section", Rb, "- Recovery and rollback\n- Contacts and tools", "- Contacts and tools"),
    ("the runbook has no contacts section", Rb, "- Contacts and tools\n- Coverage check", "- Coverage check"),
    ("the runbook may invent a person", Rb, "- Invent a person, a phone number, a team name, a tool, a command or a time that no source gives.\n", ""),
    ("the runbook may name a secret", Rb, "- Write a secret, a key, a password, a token, a connection string with credentials, or a real server address.\n", ""),
    ("the runbook may claim it was run", Rb, "- Claim the product was built, run, tested or monitored.\n", ""),
    ("the runbook does not say it is from the design", Rb, "that this runbook comes from the design and the plan, not from the live product", "what it is for"),
    ("the runbook repeats the plan", Rb, "refer to its steps by their IDs and do not repeat them", "copy its steps in"),
    ("the runbook states contacts as fact", Rb, "write what the receiving team needs to supply as QUESTIONS", "write the contacts"),
    ("the runbook states its numbers as agreed", Rb, 'A frequency or a time you propose is marked "Proposed:" in the entry and listed here. Do not state it as agreed.', "State frequencies as agreed."),
    # ---- the hypercare skill
    ("the hypercare plan reads the instruction set", Hy, "- artefact: release_notes\n- artefact: runbook", "- artefact: release_notes\n- artefact: build_instructions\n- artefact: runbook"),
    ("the hypercare plan does not read the runbook", Hy, "- artefact: runbook\n", ""),
    ("the hypercare plan does not read the requirements", Hy, "- artefact: non_functional_requirements\n", ""),
    ("the hypercare plan does not cover requirements", Hy, "Items: HYP in Who is on hand\nCovers: NFR", "Items: HYP in Who is on hand"),
    ("the hypercare plan has no exit criteria", Hy, "- Exit criteria\n- Coverage check", "- Coverage check"),
    ("the hypercare plan has no escalation", Hy, "- Escalation\n- Exit criteria", "- Exit criteria"),
    ("the hypercare plan may state numbers as agreed", Hy, "- State a number of weeks, hours or minutes, or a name of a person or team, as agreed when no source gives it.\n", ""),
    ("the hypercare plan may name a person", Hy, "Name roles, never people.", "Name people."),
    ("the hypercare plan may claim it was run", Hy, "- Claim the product was built, run, tested or monitored.\n", ""),
    ("the hypercare exit is not checkable", Hy, "in words a person can check by looking", "in general terms"),
    # ---- the downloads
    ("the runbook cannot be downloaded", Rt, 'DOWNLOADABLE = ("deployment_plan", "release_notes", "runbook", "hypercare_plan")', 'DOWNLOADABLE = ("deployment_plan", "release_notes", "hypercare_plan")'),
    ("the hypercare plan cannot be downloaded", Rt, 'DOWNLOADABLE = ("deployment_plan", "release_notes", "runbook", "hypercare_plan")', 'DOWNLOADABLE = ("deployment_plan", "release_notes", "runbook")'),
    ("the sign-off can be downloaded as a document", Rt, 'DOWNLOADABLE = ("deployment_plan", "release_notes", "runbook", "hypercare_plan")', 'DOWNLOADABLE = ("deployment_plan", "release_notes", "runbook", "hypercare_plan", "handover_signoff")'),
    ("the refusal names only the deploy pair", Rt, "the deployment plan, the release notes, the runbook and the hypercare plan can", "the deployment plan and the release notes can"),
]

F = "src/lib/format.ts"
T = "src/lib/trace.ts"

FRONTEND = [
    ("the runbook is not downloadable", F, "export const DOWNLOADABLE_TYPES = ['deployment_plan', 'release_notes', 'runbook', 'hypercare_plan'] as const", "export const DOWNLOADABLE_TYPES = ['deployment_plan', 'release_notes', 'hypercare_plan'] as const"),
    ("the hypercare plan is not downloadable", F, "export const DOWNLOADABLE_TYPES = ['deployment_plan', 'release_notes', 'runbook', 'hypercare_plan'] as const", "export const DOWNLOADABLE_TYPES = ['deployment_plan', 'release_notes', 'runbook'] as const"),
    ("the sign-off is downloadable", F, "export const DOWNLOADABLE_TYPES = ['deployment_plan', 'release_notes', 'runbook', 'hypercare_plan'] as const", "export const DOWNLOADABLE_TYPES = ['deployment_plan', 'release_notes', 'runbook', 'hypercare_plan', 'handover_signoff'] as const"),
    ("the runbook column has no name", T, "RUN: 'Runbook entries', ", ""),
    ("the hypercare column has no name", T, ", HYP: 'Hypercare items',", ","),
    ("the runbook column has the wrong name", T, "RUN: 'Runbook entries'", "RUN: 'Release steps'"),
]
