"""Deliberate breaks for S19e-1 (an artefact the workflow no longer has is RETIRED, not failed).

Backend:  python -u -m scripts.mutation_check scripts/mutants/s19e1_retired.py --tests tests/test_review_service.py tests/test_human_actions.py tests/test_routes_review.py
Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/s19e1_retired.py
"""
Sv = "app/review/service.py"
Hm = "app/review/human.py"
# (The open-items list needs no break of its own: a retired status has no verdict and no findings, so it falls into neither list. That is pinned by a test, not by a break.)

MUTANTS = [
    ("nothing is ever retired", Sv, "        return artefact.latest_version is not None and artefact.type not in known", "        return False"),
    ("everything with a version is retired", Sv, "        return artefact.latest_version is not None and artefact.type not in known", "        return artefact.latest_version is not None"),
    ("an artefact with no version can be retired", Sv, "        return artefact.latest_version is not None and artefact.type not in known", "        return artefact.type not in known"),
    ("retired is decided by the skill, not the catalogue", Sv, "        return artefact.latest_version is not None and artefact.type not in known", "        return artefact.latest_version is not None and self.runtime.skills.get(artefact.type) is None"),
    ("the catalogue is read from one phase only", Sv, "known = {a.key for phase in self.engine.catalogue.phases for a in phase.artefacts}", "known = {a.key for a in self.engine.catalogue.phases[0].artefacts}"),
    ("the status never says retired", Sv, "        if self.is_retired(project_id, artefact_id):\n            return ReviewStatus(artefact_id, \"retired\", latest_version=latest)", "        if False:\n            return ReviewStatus(artefact_id, \"retired\", latest_version=latest)"),
    ("the status forgets the version", Sv, "return ReviewStatus(artefact_id, \"retired\", latest_version=latest)", "return ReviewStatus(artefact_id, \"retired\")"),
    ("the status is checked after the review history", Sv, "        if self.is_retired(project_id, artefact_id):\n            return ReviewStatus(artefact_id, \"retired\", latest_version=latest)\n", ""),
    ("review all does not skip a retired artefact", Sv, "            if artefact.latest_version is None or self.is_retired(project_id, artefact.id):", "            if artefact.latest_version is None:"),
    ("review all skips everything", Sv, "            if artefact.latest_version is None or self.is_retired(project_id, artefact.id):", "            if True:"),
    ("review all skips an artefact with no version no longer", Sv, "            if artefact.latest_version is None or self.is_retired(project_id, artefact.id):", "            if self.is_retired(project_id, artefact.id):"),
    ("a retired artefact is reviewed anyway", Sv, "            if self.is_retired(project_id, artefact_id):\n                raise NothingToReview(f\"'{artefact.title}' is retired", "            if False:\n                raise NothingToReview(f\"'{artefact.title}' is retired"),
    ("a retired artefact gets the old message", Sv, "is retired: it was written by a part of this phase that no longer exists, so there is nothing to review it against. Its versions are kept", "has no skill"),
    ("a not-ready artefact is called retired", Sv, "            if self.is_retired(project_id, artefact_id):\n                raise NothingToReview(f\"'{artefact.title}' is retired", "            if True:\n                raise NothingToReview(f\"'{artefact.title}' is retired"),
    ("the retired message blames the skill", Sv, "so there is nothing to review it against. Its versions are kept\")", "so its skill is missing. Its versions are kept\")"),
]

FRONTEND = [
    ("the page does not know the state", "src/api/review.ts", "['unreviewed', 'reviewed', 'stale', 'retired']", "['unreviewed', 'reviewed', 'stale']"),
    ("the state has no label", "src/lib/format.ts", ", retired: 'Retired' }", " }"),
    ("the label is wrong", "src/lib/format.ts", "retired: 'Retired' }", "retired: 'Archived' }"),
    ("the chip treats retired as not reviewed", "src/components/ReviewChip.tsx", "  if (status !== null && status.state === 'retired') {", "  if (false) {"),
    ("the chip treats every state as retired", "src/components/ReviewChip.tsx", "  if (status !== null && status.state === 'retired') {", "  if (status !== null) {"),
    ("the chip hides why", "src/components/ReviewChip.tsx", "title=\"This part of the phase no longer exists. Its versions are kept; it is not reviewed.\" ", ""),
    ("the queue keeps retired artefacts", "src/state/useProjectScreen.ts", " && !retired.has(c.id))", ")"),
    ("the queue drops every artefact the server named", "src/state/useProjectScreen.ts", "const retired = new Set(statuses.filter((s) => s.state === 'retired').map((s) => s.artefact_id))", "const retired = new Set(statuses.map((s) => s.artefact_id))"),
    ("the queue drops stale artefacts too", "src/state/useProjectScreen.ts", "statuses.filter((s) => s.state === 'retired')", "statuses.filter((s) => s.state === 'retired' || s.state === 'stale')"),
    ("the queue forgets the phase", "src/state/useProjectScreen.ts", "c.phase_key === phaseKey && c.latest_version !== null && !retired.has(c.id)", "c.latest_version !== null && !retired.has(c.id)"),
    ("the queue includes artefacts with nothing written", "src/state/useProjectScreen.ts", "c.phase_key === phaseKey && c.latest_version !== null && !retired.has(c.id)", "c.phase_key === phaseKey && !retired.has(c.id)"),
    # UNKILLABLE BY CONSTRUCTION, dropped: whether `reviewAll` passes the loaded states to `reviewQueueOf` lives inside a React hook callback, and the project has no DOM test
    # library to press the real button. Everything the callback DECIDES is in `reviewQueueOf`, which is fully tested. That the hook calls it with the loaded states is a browser check.
]
