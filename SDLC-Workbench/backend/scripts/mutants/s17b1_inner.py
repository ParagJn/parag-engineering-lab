"""Deliberate breaks for S17b-1 (the extra check in the runtime's repair loop; the 17a checks as that extra; the workspace equals the saved version).

Run:
  cd backend && python -u -m scripts.mutation_check scripts/mutants/s17b1_inner.py --tests tests/test_build_inner.py tests/test_agent_runtime.py
Every one of these should make the tests FAIL. One that does not is a hole in the tests.
"""
Rt = "app/agents/runtime.py"
In = "app/build/inner.py"
Sv = "app/build/service.py"

MUTANTS = [
    # ---- the hook in the runtime
    ("the extra check is never called", Rt, "            if not problems and extra_check is not None:", "            if False:"),
    ("the extra check is called on a reply that already has problems", Rt, "            if not problems and extra_check is not None:", "            if extra_check is not None:"),
    ("the extra check's problems are dropped", Rt, "                problems = [str(p) for p in await extra_check(body)][:MAX_PROBLEMS]", "                await extra_check(body)"),
    ("the extra check's problems are not limited", Rt, "                problems = [str(p) for p in await extra_check(body)][:MAX_PROBLEMS]", "                problems = [str(p) for p in await extra_check(body)]"),
    ("the extra check's problems replace the ordinary ones", Rt, "            if not problems and extra_check is not None:\n                problems = [str(p) for p in await extra_check(body)][:MAX_PROBLEMS]", "            if extra_check is not None:\n                problems = [str(p) for p in await extra_check(body)][:MAX_PROBLEMS]"),
    # ---- reading what is saved
    ("the latest version is never found", In, "    if not found or found[0].latest_version is None:\n        return None", "    return None"),
    ("an artefact with no version reads as empty text", In, "    if not found or found[0].latest_version is None:\n        return None", "    if not found:\n        return None"),
    ("the design is never read", In, "    skill = library.get(DESIGN)\n    if skill is None:\n        return ()", "    return ()"),
    # ---- putting the workspace back
    ("sync does nothing", In, "    done: dict[str, str] = {}\n    for key in KINDS:", "    done: dict[str, str] = {}\n    for key in []:"),
    ("a folder with no saved version is left alone", In, '            done[key] = "removed" if build.remove_artefact_files(project_id, key) else "none"\n            continue', '            done[key] = "none"\n            continue'),
    ("a removal is reported as nothing", In, '"removed" if build.remove_artefact_files(project_id, key) else "none"', '"none" if build.remove_artefact_files(project_id, key) else "none"'),
    ("sync writes the wrong text", In, "            build.write_artefact(project_id, skill, body, actor=actor, audit=False)", "            build.write_artefact(project_id, skill, '## Code\\n', actor=actor, audit=False)"),
    ("sync audits every write", In, "            build.write_artefact(project_id, skill, body, actor=actor, audit=False)", "            build.write_artefact(project_id, skill, body, actor=actor)"),
    ("a refused saved version stops the sync", In, '        except BuildRefused:\n            done[key] = "refused"', '        except BuildRefused:\n            raise'),
    ("a refused saved version is reported as written", In, 'done[key] = "refused"', 'done[key] = "written"'),
    # ---- the extra check
    ("the files are not written before the check", In, "        try:\n            build.write_artefact(project_id, skill, body, actor=actor)\n        except BuildRefused as exc:\n            return [str(exc)]", "        pass"),
    ("a refused write is accepted", In, "        except BuildRefused as exc:\n            return [str(exc)]", "        except BuildRefused as exc:\n            return []"),
    ("the real check is not run", In, "        result = build.check_artefact(project_id, skill.key, actor=actor, design_tables=design)\n        return list(result.problems)                  # only a failed check has problems; \"skipped\" (no sandbox) is not the model's fault and the loop reports it as blocked", "        return []"),
    ("a failed check is accepted", In, "        return list(result.problems)                  # only a failed check has problems; \"skipped\" (no sandbox) is not the model's fault and the loop reports it as blocked", "        return []"),
    ("the design's tables are not passed", In, "        design = design_tables_for(store, library, project_id)           # only the database check uses it", "        design = ()"),
    ("the tests are tried against whatever is in the workspace", In, '        if skill.key == "test_suite":                                   # collecting the tests imports the backend: it must be the saved one\n            sync_workspace(build, store, library, project_id, actor=actor)', "        pass"),
    ("the check runs on the event loop", In, "        return await asyncio.to_thread(run, body)", "        return run(body)"),
    # ---- the quiet write and the removal
    ("a quiet write is still audited", Sv, '        if audit:\n            self._audit(project_id, actor, "build.files_written"', '        if True:\n            self._audit(project_id, actor, "build.files_written"'),
    ("a loud write is not audited", Sv, '        if audit:\n            self._audit(project_id, actor, "build.files_written"', '        if False:\n            self._audit(project_id, actor, "build.files_written"'),
    ("a refusal is not audited when loud", Sv, '            if audit:\n                self._audit(project_id, actor, "build.files_refused"', '            if False:\n                self._audit(project_id, actor, "build.files_refused"'),
    ("a refusal is audited when quiet", Sv, '            if audit:\n                self._audit(project_id, actor, "build.files_refused"', '            if True:\n                self._audit(project_id, actor, "build.files_refused"'),
    ("any folder may be removed", Sv, "        kind = KINDS.get(skill_key)\n        if kind is None:\n            raise BuildRefused(f\"'{skill_key}' is not an artefact that holds code\")\n        return self.sandbox.workspace(project_id).remove_folder(kind.folder)", "        kind = KINDS.get(skill_key) or KINDS['backend_code']\n        return self.sandbox.workspace(project_id).remove_folder(kind.folder)"),
    ("the wrong folder is removed", Sv, "        return self.sandbox.workspace(project_id).remove_folder(kind.folder)", "        return self.sandbox.workspace(project_id).remove_folder('backend')"),
]
