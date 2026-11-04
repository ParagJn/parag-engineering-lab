"""Deliberate breaks for S21a (an artefact that is part of the design but switched off).

Backend:  python -u -m scripts.mutation_check scripts/mutants/s21a_not_enabled.py --tests tests/test_catalogue.py tests/test_plan.py tests/test_workflow.py tests/test_routes_projects.py tests/test_workflow_scripts.py
Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/s21a_not_enabled.py
Run alone: a sweep beside other heavy work gives INVALID ('no output') results.
"""
Df = "app/workflow/definitions.py"
Pl = "app/workflow/plan.py"
En = "app/workflow/engine.py"
Rp = "app/routes_projects.py"
St = "app/agents/status.py"
Rc = "scripts/render_catalogue.py"
Y = "app/phases/definitions/05-deploy.yaml"

MUTANTS = [
    # ---- the definition
    ("enabled is not an allowed field", Df, 'ARTEFACT_FIELDS = {"key", "name", "id_prefix", "role", "required", "description", "after", "enabled", "disabled_reason", "kind"}', 'ARTEFACT_FIELDS = {"key", "name", "id_prefix", "role", "required", "description", "after", "kind"}'),
    ("enabled defaults to off", Df, 'enabled = raw.get("enabled", True)', 'enabled = raw.get("enabled", False)'),
    ("enabled may be any value", Df, "    if not isinstance(enabled, bool):\n        raise CatalogueError(f\"{where}: 'enabled' must be true or false\")", "    pass"),
    ("a reason is not needed", Df, "    if not enabled and not reason:", "    if False:"),
    ("a reason may sit on an enabled artefact", Df, "    if enabled and \"disabled_reason\" in raw:", "    if False:"),
    ("a switched off artefact may be required", Df, "    if not enabled and required:", "    if False:"),
    ("the reason is not kept", Df, "        disabled_reason=reason,\n        kind=kind,\n    )", "        disabled_reason=\"\",\n        kind=kind,\n    )"),
    ("the enabled flag is not kept", Df, "        enabled=enabled,\n        disabled_reason=reason,", "        enabled=True,\n        disabled_reason=reason,"),
    ("an enabled artefact may wait for one that never runs", Df, "        if item.enabled:\n            for dependency in item.after:", "        if False:\n            for dependency in item.after:"),
    ("a switched off one may not wait for anything", Df, "        if item.enabled:\n            for dependency in item.after:", "        if True:\n            for dependency in item.after:"),
    ("the not enabled count is wrong", Df, "        return sum(1 for p in self.phases for a in p.artefacts if not a.enabled)", "        return sum(1 for p in self.phases for a in p.artefacts if a.enabled)"),
    ("the default for enabled is not in the dataclass", Df, "    enabled: bool = True\n    disabled_reason: str = \"\"", "    enabled: bool = False\n    disabled_reason: str = \"\""),
    # ---- the plan
    ("a switched off artefact is in the plan", Pl, "    usable = {a.key for a in phase.artefacts if a.enabled and not a.by_hand}      # an artefact switched off, or done by hand, can never be chosen\n    if choice is None:\n        return set(usable), set()", "    usable = {a.key for a in phase.artefacts if not a.by_hand}\n    if choice is None:\n        return set(usable), set()"),
    ("a switched off artefact can be chosen", Pl, "    off = [a for a in phase.artefacts if a.key in enabled and not a.enabled]\n    if off:", "    off = []\n    if off:"),
    ("the refusal does not give the reason", Pl, "not enabled ({off[0].disabled_reason})", "not enabled"),
    ("the refusal does not name the artefact", Pl, "{', '.join(repr(a.name) for a in off)} {'is' if len(off) == 1 else 'are'} not enabled", "it is not enabled"),
    ("the plain is not singular for one", Pl, "{'is' if len(off) == 1 else 'are'} not enabled (", "are not enabled ("),
    ("not enabled lists the wrong ones", Pl, "        return tuple(a for a in self.phase.artefacts if not a.enabled)", "        return tuple(a for a in self.phase.artefacts if a.enabled)"),
    ("not enabled lists all artefacts", Pl, "        return tuple(a for a in self.phase.artefacts if not a.enabled)", "        return tuple(self.phase.artefacts)"),
    # ---- the engine and the payloads
    ("the snapshot hides the not enabled", En, "                    not_enabled=tuple(NotEnabledState(a.key, a.name, a.disabled_reason) for a in phase.not_enabled),", "                    not_enabled=(),"),
    ("the snapshot hides the reason", En, "NotEnabledState(a.key, a.name, a.disabled_reason)", "NotEnabledState(a.key, a.name, \"\")"),
    ("the plan hides the not enabled", Rp, "                \"not_enabled\": [{\"key\": a.key, \"name\": a.name, \"reason\": a.disabled_reason} for a in p.not_enabled],\n                \"by_hand\": [{\"key\": a.key, \"name\": a.name, \"description\": a.description} for a in p.by_hand],\n            }\n            for p in plan.phases", "                \"not_enabled\": [],\n                \"by_hand\": [{\"key\": a.key, \"name\": a.name, \"description\": a.description} for a in p.by_hand],\n            }\n            for p in plan.phases"),
    ("the plan hides the reason", Rp, "\"not_enabled\": [{\"key\": a.key, \"name\": a.name, \"reason\": a.disabled_reason} for a in p.not_enabled],\n                \"by_hand\"", "\"not_enabled\": [{\"key\": a.key, \"name\": a.name, \"reason\": \"\"} for a in p.not_enabled],\n                \"by_hand\""),
    ("the catalogue hides the flag", Rp, "\"enabled\": a.enabled, \"disabled_reason\": a.disabled_reason, \"by_hand\"", "\"enabled\": True, \"disabled_reason\": a.disabled_reason, \"by_hand\""),
    ("the catalogue hides the reason", Rp, "\"enabled\": a.enabled, \"disabled_reason\": a.disabled_reason, \"by_hand\"", "\"enabled\": a.enabled, \"disabled_reason\": \"\", \"by_hand\""),
    ("the project hides the not enabled", Rp, "                \"not_enabled\": [{\"key\": a.key, \"name\": a.name, \"reason\": a.reason} for a in p.not_enabled],\n                \"by_hand\"", "                \"not_enabled\": [],\n                \"by_hand\""),
    ("the project hides the reason", Rp, "\"reason\": a.reason} for a in p.not_enabled],", "\"reason\": \"\"} for a in p.not_enabled],"),
    ("the status does not count them", St, '        "not_enabled": catalogue.not_enabled_count,\n', ""),
    # ---- the document
    ("the document hides the count", Rc, 'off=f", {off} of them not enabled" if off else ""', 'off=""'),
    ("the document hides the section", Rc, "        if phase.not_enabled:", "        if False:"),
    ("the document hides the reason", Rc, "out.append(_row([item.name, item.role, item.id_prefix, item.disabled_reason]))", "out.append(_row([item.name, item.role, item.id_prefix, \"\"]))"),
    # ---- the shipped definition
    ("infrastructure is back on", Y, "    enabled: false\n    disabled_reason: Not enabled. The product is built", "    disabled_reason: Not enabled. The product is built"),
    # REMOVED (no longer meaningful, S21c): the verification is done by hand, so it has no role and is never required; the loader refuses either on a checklist (tested in test_catalogue.py)
    # ("the verification is not required", ...),
    ("release notes do not wait for the plan", Y, "    required: true\n    after: [deployment_plan]\n    description: What is in this release", "    required: true\n    description: What is in this release"),
]

T = "src/api/types.ts"
W = "src/lib/wizard.ts"
P = "src/pages/WizardPage.tsx"
A = "src/components/ArtefactCard.tsx"
J = "src/pages/ProjectPage.tsx"

FRONTEND = [
    ("the enabled flag is not decoded", T, "return { ...planArtefactFields(o, w), enabled: bool(o.enabled, `${w}.enabled`), disabled_reason: str(o.disabled_reason, `${w}.disabled_reason`), by_hand: bool(o.by_hand, `${w}.by_hand`) }", "return { ...planArtefactFields(o, w), enabled: true, disabled_reason: str(o.disabled_reason, `${w}.disabled_reason`), by_hand: bool(o.by_hand, `${w}.by_hand`) }"),
    ("the reason is not decoded", T, "enabled: bool(o.enabled, `${w}.enabled`), disabled_reason: str(o.disabled_reason, `${w}.disabled_reason`), by_hand", "enabled: bool(o.enabled, `${w}.enabled`), disabled_reason: '', by_hand"),
    ("the flag may be text", T, "enabled: bool(o.enabled, `${w}.enabled`)", "enabled: o.enabled as boolean"),
    ("the plan's not enabled list is not decoded", T, "      not_enabled: notEnabled(po.not_enabled, `${w}.not_enabled`),\n      by_hand: byHand(po.by_hand, `${w}.by_hand`),\n    }\n  }) }", "      not_enabled: [],\n      by_hand: byHand(po.by_hand, `${w}.by_hand`),\n    }\n  }) }"),
    ("a not enabled entry may lack its reason", T, "reason: str(o.reason, `${w}[${i}].reason`)", "reason: ''"),
    ("the project's not enabled list is not decoded", T, "        not_enabled: notEnabled(po.not_enabled, `${w}.not_enabled`),\n        by_hand: byHand(po.by_hand, `${w}.by_hand`),\n      }\n    }),", "        not_enabled: [],\n        by_hand: byHand(po.by_hand, `${w}.by_hand`),\n      }\n    }),"),
    ("the wizard ticks a switched off artefact", W, "p.artefacts.filter((a) => a.enabled && !a.by_hand).map((a) => a.key)])),", "p.artefacts.filter((a) => !a.by_hand).map((a) => a.key)])),"),
    ("the wizard toggles a switched off artefact", W, "  if (!artefact || artefact.required || !artefact.enabled || artefact.by_hand) return state", "  if (!artefact || artefact.required || artefact.by_hand) return state"),
    ("the selection asks for a switched off artefact", W, "    const all = phase.artefacts.filter((a) => a.enabled && !a.by_hand).map((a) => a.key)", "    const all = phase.artefacts.filter((a) => !a.by_hand).map((a) => a.key)"),
    ("the wizard offers a box for a switched off artefact", P, "{phase.artefacts.filter((a) => a.enabled && !a.by_hand).map((a) => {", "{phase.artefacts.filter((a) => !a.by_hand).map((a) => {"),
    ("the wizard does not say why", P, "<li key={a.key}><span className=\"font-semibold\">{a.name}</span>: {a.disabled_reason}</li>", "<li key={a.key}><span className=\"font-semibold\">{a.name}</span></li>"),
    ("the wizard hides the list", P, "{phase.artefacts.some((a) => !a.enabled) && (", "{false && ("),
    ("the card is not labelled", A, "aria-label={`${name}: not enabled`}", "aria-label={name}"),
    ("the card has no badge", A, "Not enabled</span>\n      </span>", "</span>\n      </span>"),
    ("the card has no reason", A, "<span className=\"mt-1 block text-xs\">{reason}</span>", ""),
    ("the card can be pressed", A, "    <li aria-label={`${name}: not enabled`} className=", "    <li onClick={() => undefined} role=\"button\" aria-label={`${name}: not enabled`} className="),
    ("the page hides the grey cards", J, "{phase.not_enabled.map((n) => <NotEnabledCard key={n.key} name={n.name} reason={n.reason} />)}", ""),
    ("the page puts the grey cards first", J, "              {phase.not_enabled.map((n) => <NotEnabledCard key={n.key} name={n.name} reason={n.reason} />)}\n            </ul>", "            </ul>"),
    ("the page hides the count", J, "{phase.not_enabled.length > 0 ? ` · ${phase.not_enabled.length} not enabled` : ''}", ""),
    ("the page counts them with the others", J, "{count(phase.artefacts.length, 'artefact')}", "{count(phase.artefacts.length + phase.not_enabled.length, 'artefact')}"),
]
