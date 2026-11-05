"""Deliberate breaks for S23 Part A (users and roles: the list, the rules, the approval check, the page and the Approve button).

Backend:  python -u -m scripts.mutation_check scripts/mutants/s23_users_and_roles.py --tests tests/test_users.py tests/test_approval_roles.py tests/test_decide.py
Frontend: python -u -m scripts.frontend_mutation_check scripts/mutants/s23_users_and_roles.py
Run alone: a sweep beside other heavy work gives INVALID ('no output') results.
"""
Ro = "app/access/roles.py"
De = "app/access/decide.py"
Rp = "app/repos.py"
Ru = "app/routes_users.py"
Hu = "app/review/human.py"
Mn = "app/main.py"
Ra = "app/routes_artefacts.py"
Rr = "app/routes_review.py"
Eg = "app/workflow/engine.py"
Wh = "app/access/who.py"

MUTANTS = [
    # ---- the roles and the defaults
    ("a role is missing", Ro, 'ROLES = ("Project Manager", "Architect", "Business Engineer", "Technical Lead", "Deployment Engineer", "BAU Lead", "Administrator")', 'ROLES = ("Project Manager", "Architect", "Business Engineer", "Technical Lead", "Deployment Engineer", "BAU Lead")'),
    ("the roles are in another order", Ro, 'ROLES = ("Project Manager", "Architect",', 'ROLES = ("Architect", "Project Manager",'),
    ("requirements is approved by anyone", Ro, '"requirements": ("Architect",),', '"requirements": ("Project Manager",),'),
    ("design is approved by the wrong role", Ro, '"design": ("Architect",),', '"design": ("Technical Lead",),'),
    ("setup is approved by the wrong role", Ro, '"setup": ("Architect",),', '"setup": ("BAU Lead",),'),
    ("build is approved by the wrong role", Ro, '"build": ("Technical Lead",),', '"build": ("Architect",),'),
    ("a name may be blank", Ro, '    if not name:\n        raise RoleError("a name is needed")', '    if False:\n        raise RoleError("a name is needed")'),
    ("a name may be any length", Ro, "    if len(name) > MAX_NAME:", "    if False:"),
    ("a name may hold a control character", Ro, "    if any(ord(c) < 32 or ord(c) == 127 for c in (raw or \"\")):", "    if False:"),
    ("system is an allowed name", Ro, 'RESERVED = ("system",)', "RESERVED = ()"),
    ("an actor prefix is an allowed name", Ro, 'or name.lower().startswith(("human:", "agent:")):', ":"),
    ("an unknown role is accepted", Ro, "    if unknown:\n        raise RoleError(", "    if False:\n        raise RoleError("),
    ("roles are not put in order", Ro, "    return tuple(r for r in ROLES if r in asked)", "    return tuple(asked)"),
    ("names are matched with case", Ro, '    return " ".join(a.split()).casefold() == " ".join(b.split()).casefold()', '    return " ".join(a.split()) == " ".join(b.split())'),
    # ---- the list (repo)
    ("a name is stored in its typed case for matching", Rp, "        key = name.casefold()\n        with self.db.write() as conn:\n            existing", "        key = name\n        with self.db.write() as conn:\n            existing"),
    ("a duplicate name is accepted", Rp, "            if existing is not None and existing[\"active\"]:\n                raise ConflictError(", "            if False:\n                raise ConflictError("),
    ("adding is not audited", Rp, "            write_audit(conn, self._clock(), actor, action, \"user\", name, detail={\"roles\": list(roles)})\n", ""),
    ("the person added is not recorded", Rp, "(name, key, actor, self._clock())", "(name, key, \"system\", self._clock())"),
    ("a switched-off person is not switched back on", Rp, '                conn.execute("UPDATE users SET active = 1 WHERE id = ?", (uid,))\n', ""),
    ("a returning person keeps their old roles", Rp, '                conn.execute("DELETE FROM user_roles WHERE user_id = ?", (uid,))\n                action = "user.reactivated"', '                action = "user.reactivated"'),
    ("the last administrator can lose the role", Rp, "            if ADMIN not in roles and row[\"active\"] and self._admins_left(conn, excluding=row[\"id\"]) == 0 and self._is_admin(conn, row[\"id\"]):\n                raise ConflictError(", "            if False:\n                raise ConflictError("),
    ("the last administrator can be switched off", Rp, "            if not active and row[\"active\"] and self._is_admin(conn, row[\"id\"]) and self._admins_left(conn, excluding=row[\"id\"]) == 0:\n                raise ConflictError(", "            if False:\n                raise ConflictError("),
    ("a switched-off administrator still counts", Rp, "WHERE u.active = 1 AND r.role = ? AND u.id != ?", "WHERE r.role = ? AND u.id != ?"),
    ("the administrator count includes the person being changed", Rp, "(ADMIN, -1 if excluding is None else excluding)", "(ADMIN, -1)"),
    ("a role change is not audited", Rp, '"user.roles_changed", "user", row["name"], detail={"before": sorted(before), "after": list(roles)})', '"user.roles_changed", "user", row["name"], detail={})'),
    ("roles are added, not replaced", Rp, '            conn.execute("DELETE FROM user_roles WHERE user_id = ?", (row["id"],))\n            conn.executemany("INSERT INTO user_roles (user_id, role) VALUES (?, ?)", [(row["id"], r) for r in roles])\n            write_audit(conn, self._clock(), actor, "user.roles_changed"', '            conn.executemany("INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, ?)", [(row["id"], r) for r in roles])\n            write_audit(conn, self._clock(), actor, "user.roles_changed"'),
    ("an unknown person is not reported", Rp, '            raise NotFoundError(f"{name!r} is not on the list")', '            raise NotFoundError("")'),
    ("a switched-off person is counted active", Rp, 'SELECT COUNT(*) FROM users WHERE active = 1', 'SELECT COUNT(*) FROM users'),
    ("find is case sensitive", Rp, '        key = " ".join((name or "").split()).casefold()\n        with self.db.read() as conn:', '        key = " ".join((name or "").split())\n        with self.db.read() as conn:'),
    ("the users are not in name order", Rp, 'SELECT * FROM users ORDER BY name_key', 'SELECT * FROM users ORDER BY id DESC'),
    # ---- the first administrator
    ("the first administrator lacks roles", Rp, "        return self.add(name, ROLES, actor=\"system\")", "        return self.add(name, (ADMIN,), actor=\"system\")"),
    ("seeding adds to an existing list", Rp, "            if conn.execute(\"SELECT COUNT(*) FROM users\").fetchone()[0] > 0:\n                return None", "            if False:\n                return None"),
    ("seeding ignores a blank name", Rp, '        if not (name or "").strip():\n            return None', "        if False:\n            return None"),
    # ---- who a phase says approves it (the 'business engineer' bug)
    ("the page shows the definition's label again", Eg, "approver=approver_label(phase.key, phase.phase.approver, approvers),", "approver=phase.phase.approver,"),
    ("the configured roles are not read", Eg, "        approvers = self.store.users.approvers()                     # who may approve each phase right now (S23); the definition's label is only the fallback\n", "        approvers = {}\n"),
    ("the fallback is lost", Wh, "    return approvers_in_words(roles) or fallback", "    return approvers_in_words(roles)"),
    ("another phase's roles are used", Wh, "    roles = (approvers or {}).get(phase_key) or ()", "    roles = next(iter((approvers or {}).values()), ())"),
    ("the last role is not joined with or", Wh, '    return ", ".join(words[:-1]) + " or " + words[-1]', '    return ", ".join(words)'),
    ("a single role gets an or", Wh, "    if len(words) <= 1:\n        return \"\".join(words)", "    if len(words) <= 0:\n        return \"\".join(words)"),
    ("every word is lower-cased", Wh, "w if w.isupper() else w.lower()", "w.lower()"),
    ("no word is lower-cased", Wh, "w if w.isupper() else w.lower()", "w"),
    # ---- who may approve which phase
    ("a phase may have no approving role", Rp, '        if not roles:\n            raise InvalidInput("a phase needs at least one role that may approve it")', "        if False:\n            raise InvalidInput(\"\")"),
    ("an unknown phase is accepted", Rp, "        if phase_key not in DEFAULT_APPROVERS:\n            raise NotFoundError(", "        if False:\n            raise NotFoundError("),
    ("a saved choice is ignored", Rp, "tuple(r for r in ROLES if r in saved[phase]) if saved.get(phase)", "tuple(r for r in ROLES if r in DEFAULT_APPROVERS[phase]) if saved.get(phase)"),
    ("changing one phase changes all", Rp, '            conn.execute("DELETE FROM phase_approvers WHERE phase_key = ?", (phase_key,))', '            conn.execute("DELETE FROM phase_approvers")'),
    ("an approver change is not audited", Rp, 'write_audit(conn, self._clock(), actor, "phase.approvers_changed", "phase", phase_key, detail={"before": list(before), "after": list(roles)})', "pass"),
    # ---- the decision
    ("nothing is restricted for ever", De, "    if users.count_active() == 0:\n        return None", "    if True:\n        return None"),
    ("an empty list restricts everyone", De, "    if users.count_active() == 0:\n        return None\n    allowed", "    allowed"),
    ("a phase with no rule is refused", De, "    if allowed is None:\n        return None", "    if allowed is None:\n        raise NotAllowed('no')"),
    ("a switched-off person keeps their roles", De, "    mine = me.roles if me is not None and me.active else ()", "    mine = me.roles if me is not None else ()"),
    ("any role approves", De, "    used = next((r for r in ROLES if r in allowed and r in mine), None)", "    used = next((r for r in mine), None)"),
    ("the role recorded is not in the fixed order", De, "next((r for r in ROLES if r in allowed and r in mine), None)", "next((r for r in allowed if r in mine), None)"),
    ("the sentence forgets the role needed", De, '    raise NotAllowed(f"{phase_name} can be {what} only by {needs}; {me.name} holds {held}")', '    raise NotAllowed(f"{phase_name} can be {what} only by someone else; {me.name} holds {held}")'),
    ("the sentence forgets what the person holds", De, '; {me.name} holds {held}")', '")'),
    ("a stranger is not told to ask an administrator", De, "; ask an Administrator to add you", "")
    ,("the article is always a", De, '    return f"an {role}" if role[0].lower() in "aeiou" else f"a {role}"', '    return f"a {role}"'),
    ("the verb is fixed", De, '{phase_name} can be {what} only by {needs}, and', '{phase_name} can be approved only by {needs}, and'),
    ("no held role reads as nothing", De, '    held = ", ".join(mine) if mine else "no role"', '    held = ", ".join(mine)'),
    # ---- the check is used
    ("approving is not checked", Hu, '        role = self.approving_role(actor, phase_key, "approved")\n        detail = self.open_items(project_id, phase_key)', '        role = None\n        detail = self.open_items(project_id, phase_key)'),
    ("the role is not recorded at approval", Hu, '        if role is not None:\n            detail["approved_as"] = role', "        pass"),
    ("sending back is not checked", Hu, '        role = self.approving_role(actor, phase_key, "sent back")\n        named =', '        role = None\n        named ='),
    ("the role is not recorded when sending back", Eg, 'notes=notes, detail=detail,\n        )', 'notes=notes, detail=None,\n        )'),
    ("a refusal is a 409", Ra, "    if isinstance(exc, NotAnApprover):\n        return HTTPException(status_code=403, detail=str(exc))", "    if isinstance(exc, NotAnApprover):\n        return HTTPException(status_code=409, detail=str(exc))"),
    ("a refusal when sending back is a 422", Rr, "    if isinstance(exc, NotAnApprover):\n        return HTTPException(status_code=403, detail=str(exc))", "    if isinstance(exc, NotAnApprover):\n        return HTTPException(status_code=422, detail=str(exc))"),
    # ---- the routes
    ("anyone may change the list", Ru, "    if me is None or not me.active or ADMIN not in me.roles:\n        raise HTTPException(status_code=403,", "    if False:\n        raise HTTPException(status_code=403,"),
    ("a switched-off administrator may change the list", Ru, "    if me is None or not me.active or ADMIN not in me.roles:", "    if me is None or ADMIN not in me.roles:"),
    ("an empty list is closed to everyone", Ru, "    if users.count_active() == 0:\n        return actor", "    if False:\n        return actor"),
    ("changing roles needs no administrator", Ru, 'def set_roles(name: str, body: RolesBody, request: Request) -> dict:\n    actor = _require_admin(request)', 'def set_roles(name: str, body: RolesBody, request: Request) -> dict:\n    actor = actor_from(request)'),
    ("switching off needs no administrator", Ru, 'def set_active(name: str, body: ActiveBody, request: Request) -> dict:\n    actor = _require_admin(request)', 'def set_active(name: str, body: ActiveBody, request: Request) -> dict:\n    actor = actor_from(request)'),
    ("changing approvers needs no administrator", Ru, 'def set_approvers(phase_key: str, body: RolesBody, request: Request) -> dict:\n    actor = _require_admin(request)', 'def set_approvers(phase_key: str, body: RolesBody, request: Request) -> dict:\n    actor = actor_from(request)'),
    ("a conflict is a 422", Ru, "else 409 if isinstance(exc, ConflictError)", "else 422 if isinstance(exc, ConflictError)"),
    ("a missing person is a 422", Ru, "code = 404 if isinstance(exc, NotFoundError)", "code = 422 if isinstance(exc, NotFoundError)"),
    ("an extra field is accepted", Ru, 'class NewUser(BaseModel):\n    model_config = ConfigDict(extra="forbid")', "class NewUser(BaseModel):\n    model_config = ConfigDict(extra=\"allow\")"),
    ("the note is dropped", Ru, 'NOTE = "A name is a label, not a password:', 'NOTE = "A name is:'),
    ("the empty hint forgets ADMIN_NAME", Ru, "Add ADMIN_NAME=<your name> to backend/.env and restart, or add the first person here.", "Add the first person here."),
    ("who-am-i lists a phase it may not approve", Ru, "    can = [p for p, allowed in approvers.items() if not restricted or any(r in roles for r in allowed)]", "    can = list(approvers)"),
    ("who-am-i gives no reason", Ru, "            why[phase] = str(exc)", "            pass"),
    ("who-am-i treats a switched-off person as listed", Ru, "    active = me is not None and me.active\n    roles = me.roles if active else ()", "    active = me is not None\n    roles = me.roles if me else ()"),
    ("who-am-i hides the restriction", Ru, "    restricted = store.users.count_active() > 0", "    restricted = False"),
    ("the payload shows the creator with its prefix", Ru, '"created_by": u.created_by.removeprefix("human:")', '"created_by": u.created_by'),
    # ---- start-up
    ("the administrator is not seeded", Mn, "        store.users.seed_admin(cfg.admin_name)", "        pass"),
    ("a bad admin name is ignored", Mn, '        raise SystemExit(f"ADMIN_NAME in backend/.env cannot be used: {exc}") from exc', "        pass"),
    ("the users router is not registered", Mn, "    app.include_router(users_router)\n", ""),
]

L = "src/lib/users.ts"
P = "src/components/UsersPanel.tsx"
R = "src/components/PhaseRail.tsx"
J = "src/pages/ProjectPage.tsx"
C = "src/pages/ConfigurationPage.tsx"
K = "src/api/client.ts"
U = "src/api/users.ts"
T = "src/lib/router.ts"
A = "src/App.tsx"

FRONTEND = [
    # ---- the logic
    ("a list in force is ignored", L, "  if (!me || !me.list_in_force) return null", "  if (!me) return null"),
    ("a permitted phase is blocked", L, "  return me.may_approve.includes(phaseKey) ? null :", "  return null ||"),
    ("a refused phase has no reason", L, "(me.why_not[phaseKey] ?? 'You are not allowed to approve this phase.')", "''"),
    ("the fallback reason is lost", L, "?? 'You are not allowed to approve this phase.'", "?? ''"),
    ("an unlisted name is described as listed", L, "  if (!me.on_list) return `${me.name} is not on the Users list: you can work, but not approve.`", "  if (false) return ''"),
    ("an empty list is not described", L, "  if (!me.list_in_force) return 'Nobody is on the Users list yet, so nothing is restricted.'", "  if (false) return ''"),
    ("no role is not described", L, "`${me.name} · no role`", "`${me.name}`"),
    ("a role toggled off stays", L, "const next = held.includes(role) ? held.filter((r) => r !== role) : [...held, role]", "const next = [...held, role]"),
    ("roles come back out of order", L, "  return all.filter((r) => next.includes(r))", "  return next"),
    # REMOVED (dead code: the final filter by the known roles already drops an unknown one, so the guard line was deleted): an unknown role is toggled in
    ("switched-off people come first", L, "Number(b.active) - Number(a.active) ||", "Number(a.active) - Number(b.active) ||"),
    ("people are not in name order", L, "|| a.name.localeCompare(b.name)", "|| 0"),
    ("a changed rule is not noticed", L, "  return a.length !== d.length || a.some((r, i) => r !== d[i])", "  return false"),
    ("any administrator is the last", L, "  return users.filter((u) => u.active && u.roles.includes('Administrator')).length === 1", "  return true"),
    ("a switched-off administrator counts", L, "users.filter((u) => u.active && u.roles.includes('Administrator'))", "users.filter((u) => u.roles.includes('Administrator'))"),
    ("the link shows on every phase", L, "export const showConfiguration = (selectedPhase: string): boolean => selectedPhase === 'setup'", "export const showConfiguration = (selectedPhase: string): boolean => true"),
    ("the link never shows", L, "export const showConfiguration = (selectedPhase: string): boolean => selectedPhase === 'setup'", "export const showConfiguration = (selectedPhase: string): boolean => false"),
    # ---- decoders and client
    ("the note is not decoded", U, "note: str(o.note, 'users.note')", "note: ''"),
    ("a person's active flag may be text", U, "active: bool(o.active, `${w}.active`)", "active: o.active as boolean"),
    ("the reasons are not decoded", U, "why_not: Object.fromEntries(Object.keys(why).map((k) => [k, str(why[k], `me.why_not.${k}`)])),", "why_not: {},"),
    ("the approvers are not decoded", U, "approvers: listsByKey(o.approvers, 'users.approvers'),", "approvers: {},"),
    ("the defaults are not decoded", U, "defaults: listsByKey(o.defaults, 'users.defaults'),", "defaults: {},"),
    ("adding a person is a PUT", K, "decodeUser(await post('/api/users', { name, roles }, who(actorName)))", "decodeUser(await put('/api/users', { name, roles }, who(actorName)))"),
    ("a name is not encoded in the address", K, "`/api/users/${id(name)}/roles`", "`/api/users/${name}/roles`"),
    ("changing roles goes to the wrong address", K, "`/api/users/${id(name)}/roles`", "`/api/users/${id(name)}/role`"),
    ("switching off sends the wrong flag", K, "put(`/api/users/${id(name)}/active`, { active }, who(actorName))", "put(`/api/users/${id(name)}/active`, { active: true }, who(actorName))"),
    ("who-am-i sends no name", K, "me: async (actorName) => decodeMe(await call('/api/users/me', { headers: who(actorName) })),", "me: async (actorName) => decodeMe(await call('/api/users/me')),"),
    ("changes are sent without the person's name", K, "decodeUser(await put(`/api/users/${id(name)}/roles`, { roles }, who(actorName)))", "decodeUser(await put(`/api/users/${id(name)}/roles`, { roles }))"),
    ("approvers go to the wrong address", K, "`/api/approvers/${id(phase)}`", "`/api/approver/${id(phase)}`"),
    # ---- the address and the rail
    ("the configuration address is not read", T, "    if (parts.length === 3 && parts[2] === 'configuration') return { name: 'configuration', id }\n", ""),
    ("the configuration address is built wrongly", T, "    case 'configuration': return `#/projects/${encodeURIComponent(route.id)}/configuration`", "    case 'configuration': return `#/projects/${route.id}/configuration`"),
    ("the rail link goes to the wrong place", R, "href={`#/projects/${encodeURIComponent(projectId)}/configuration`}", "href={`#/projects/${encodeURIComponent(projectId)}/verify`}"),
    ("the rail link hides on its own page", R, "{(showConfiguration(selected) || onConfiguration) && (", "{(showConfiguration(selected)) && ("),
    ("the rail link is not marked current", R, "aria-current={onConfiguration ? 'page' : undefined}\n          className={`mt-1 flex items-center gap-2 rounded-lg border-t border-slate-100 px-3 py-2 text-sm no-underline ${onConfiguration", "aria-current={undefined}\n          className={`mt-1 flex items-center gap-2 rounded-lg border-t border-slate-100 px-3 py-2 text-sm no-underline ${onConfiguration"),
    ("the rail link is above the others", R, "      {(showConfiguration(selected) || onConfiguration) && (", "      {false && ("),
    # ---- the page
    ("the tabs are missing one", C, "{ key: 'templates', label: 'Templates' }", "{ key: 'templates2', label: 'Templates' }"),
    ("the settings tab claims to work", C, "Nothing here changes them yet.", "Everything here is live."),
    ("the templates tab claims to work", C, "Nothing here uses a template yet.", "Templates are live."),
    ("an empty list cannot be started by anyone", L, "export const canEditUsers = (list: Pick<UsersList, 'empty'> | null, me: Pick<Me, 'administrator'> | null): boolean => !!list && (list.empty || !!me?.administrator)", "export const canEditUsers = (list: Pick<UsersList, 'empty'> | null, me: Pick<Me, 'administrator'> | null): boolean => !!list && !!me?.administrator"),
    ("anyone may edit", L, "boolean => !!list && (list.empty || !!me?.administrator)", "boolean => true"),
    ("a change does not reload the list", L, "try { await what(); await ui.reload() }", "try { await what() }"),
    ("a refusal is not shown", L, "ui.setError(e instanceof Error ? e.message : 'That could not be done.')", "ui.setError(null)"),
    ("the back link goes to the wrong phase", C, "buildHash({ name: 'project', id: project.id, phase: 'setup' })", "buildHash({ name: 'project', id: project.id, phase: 'build' })"),
    # ---- the Users panel
    ("a name is not tidied before adding", L, "  const clean = name.trim()\n", "  const clean = name\n"),
    ("a blank name can be added", L, "  return disabled || !clean ? null :", "  return disabled ? null :"),
    # NOT TESTABLE HERE (recorded, not hidden): clearing the typed name after Add is a state set inside a React event handler (setName / setNewRoles), and hooks cannot run in the static-render tests. The decision of WHAT is sent (newPerson) is tested. Manual check: add a person and see the box empty again.
    # ("the add form does not reset", P, "p.onAdd(made.name, made.roles); setName(''); setNewRoles([])", "p.onAdd(made.name, made.roles)"),...
    ("the last administrator can be switched off", P, "disabled={off || last} onClick", "disabled={off} onClick"),
    ("the last administrator is not explained", P, "The last Administrator: this person cannot be switched off or lose the role until someone else has it.", ""),
    ("a switched-off person's roles can be edited", P, "disabled={off || !u.active}", "disabled={off}"),
    ("the switched-off mark is missing", P, "{!u.active && <span", "{false && <span"),
    ("the read-only notice is missing", P, "{!p.canEdit && !p.list.empty && <Notice", "{false && <Notice"),
    ("the empty-list warning is missing", P, "{p.list.empty && <Notice", "{false && <Notice"),
    ("a refusal is not shown on the panel", P, "{p.error && <Notice", "{false && <Notice"),
    ("the label-not-a-password note is missing", P, "<p className=\"text-sm text-slate-600\">{p.list.note}</p>", ""),
    ("who you are is not shown", P, "{p.me && <p className=\"text-sm font-semibold\" role=\"status\">{whoLine(p.me)}</p>}", ""),
    ("the changed mark is missing", P, "{approversChanged(p.list, phase) && <span", "{false && <span"),
    ("approver boxes are never disabled", P, "label={`Roles that approve ${PHASE_NAMES[phase] ?? phase}`} disabled={off}", "label={`Roles that approve ${PHASE_NAMES[phase] ?? phase}`} disabled={false}"),
    ("a role change sends the wrong person", L, "export const rolesFor = (onRoles: (name: string, roles: string[]) => void, name: string) => (roles: string[]) => onRoles(name, roles)", "export const rolesFor = (onRoles: (name: string, roles: string[]) => void, name: string) => (roles: string[]) => onRoles('', roles)"),
    ("an approver change sends the wrong phase", L, "(roles: string[]) => onApprovers(phase, roles)", "(roles: string[]) => onApprovers('setup', roles)"),
    # ---- the Approve button
    ("approve is never greyed", J, "disabled={!s.live || !canChange || !!blocked ||", "disabled={!s.live || !canChange ||"),
    ("everything is greyed", J, "const blocked = s.action === 'approve' || s.action === 'request_changes' ? approveBlock(me, phase.key) : null", "const blocked = approveBlock(me, phase.key)"),
    ("request changes is not greyed", J, "s.action === 'approve' || s.action === 'request_changes' ? approveBlock", "s.action === 'approve' ? approveBlock"),
    ("the reason is not shown", J, "{blocked ? <span role=\"note\" className=\"font-semibold text-amber-800\">{blocked}</span> : s.hint}", "{s.hint}"),
    # NOT TESTABLE HERE (recorded, not hidden): the `me={me}` prop is one line of wiring in App.tsx. What the page does with `me` is fully tested (ProjectPage greys the buttons), and what loadMe fetches is tested. Manual check: as a person without the role, Approve is greyed with the sentence.
    # ("the person's permissions are not given to the page", A, "canChange={!!actorName} me={me}", "canChange={!!actorName}"),...
    # NOT TESTABLE HERE (recorded, not hidden): the useEffect dependency list [actorName, current.status] cannot be exercised without running React. Manual check: change the typed name, and see Approve change without a reload.
    # ("the permissions are not refetched after a phase changes", A, "}, [actorName, current.status])", "}, [actorName])"),...
    ("no name still asks for permissions", L, "return actor ? client.me(actor).catch(() => null) : Promise.resolve(null)", "return client.me(actor).catch(() => null)"),
]
