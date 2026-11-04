"""Deliberate breaks for S17a (Build artefacts: the file rules, the writer, the four checks, the workspace folder tools).

Run:
  cd backend && python -u -m scripts.mutation_check scripts/mutants/s17a_build.py --tests tests/test_build_files.py tests/test_build_run.py tests/test_sandbox_files.py
Every one of these should make the tests FAIL. One that does not is a hole in the tests.
"""
Fi = "app/build/files.py"
Ck = "app/build/checks.py"
Sv = "app/build/service.py"
W = "app/sandbox/workspace.py"
Ag = "app/agents/checks.py"

MUTANTS = [
    # ---- reading the Code section
    ("a File line with bold is not read", Fi, r'(?:\*\*|__)?File:[ \t]*(?:\*\*|__)?', r'File:[ \t]*'),
    ("a File line with backticks is not read", Fi, r'`?([^`\s*]+)`?(?:\*\*|__)?[ \t]*$")', r'([^`\s*]+)(?:\*\*|__)?[ \t]*$")'),
    ("a block with no File line is accepted", Fi, '            if pending is None:\n                problems.append(f"the code block at line', '            if pending is None and False:\n                problems.append(f"the code block at line'),
    ("a block that is never closed is written", Fi, "            elif end >= len(lines):", "            elif False:"),
    ("a File line with no block is forgotten", Fi, '        if pending is not None and line.strip():\n            problems.append', '        if False:\n            problems.append'),
    ("a File line at the very end is forgotten", Fi, "    if pending is not None:\n        problems.append(f\"'File: {pending[0]}' is not followed by a code block; put the opening ``` line straight after the File line\")\n\n\ndef listed_paths", "    pass\n\n\ndef listed_paths"),
    ("two File lines in a row lose the first silently", Fi, "            if pending is not None:\n                problems.append(f\"'File: {pending[0]}' is not followed", "            if False:\n                problems.append(f\"'File: {pending[0]}' is not followed"),
    ("a longer fence is closed by a shorter one", Fi, "closing = re.compile(rf\"^\\s{{0,3}}{re.escape(marker[0])}{{{len(marker)},}}\\s*$\")", "closing = re.compile(rf\"^\\s{{0,3}}{re.escape(marker[0])}{{3,}}\\s*$\")"),
    # ---- the listed files
    ("a Files entry without a path is accepted", Fi, '        if "/" in token and not token.startswith(("(", "[")):', "        if True:"),
    ("a path in backticks is not read from Files", Fi, 'words = item.text.replace("`", " ").replace("*", " ").split()', "words = item.text.split()"),
    ("the trailing colon stays on the path", Fi, 'token = words[0].rstrip(":,;.") if words else ""', 'token = words[0] if words else ""'),
    # ---- paths and folders
    ("the sandbox path rules are not applied", Fi, "    try:\n        check_relative(path)\n    except PathRefused as exc:\n        return f\"the file path '{path}' is not allowed: {exc}\"\n", "    pass\n"),
    ("a path outside the folder is allowed", Fi, "    if not path.startswith(kind.folder + \"/\"):", "    if False:"),
    ("a folder prefix without the slash is allowed", Fi, 'if not path.startswith(kind.folder + "/"):', "if not path.startswith(kind.folder):"),
    ("the database may write any file", Fi, "    if kind.only and path not in kind.only:", "    if False:"),
    ("any file type is allowed", Fi, "    if not path.endswith(kind.extensions):", "    if False:"),
    ("the database folder is wrong", Fi, '"database_schema": Kind("db",', '"database_schema": Kind("database",'),
    ("the backend may write javascript", Fi, '"backend_code": Kind("backend", (".py",)', '"backend_code": Kind("backend", (".py", ".js")'),
    ("the frontend may write python", Fi, '"frontend_code": Kind("frontend", (".html", ".js", ".css")', '"frontend_code": Kind("frontend", (".html", ".js", ".css", ".py")'),
    # ---- the whole check
    ("a duplicate path is accepted", Fi, "        if file.path in seen:\n            problems.append", "        if False:\n            problems.append"),
    ("a duplicate path is judged twice", Fi, "            problems.append(f\"{file.path} is given more than once in Code; write each file once\")\n            continue", "            problems.append(f\"{file.path} is given more than once in Code; write each file once\")"),
    ("an empty file is accepted", Fi, "        elif not file.text.strip():", "        elif False:"),
    ("a NUL byte is accepted", Fi, '        elif "\\x00" in file.text:', "        elif False:"),
    ("the file limit is thirteen", Fi, "MAX_FILES = 12", "MAX_FILES = 13"),
    ("the file limit is off by one", Fi, "    if len(seen) > MAX_FILES:", "    if len(seen) >= MAX_FILES:"),
    ("a required file may be missing", Fi, "        if files and needed not in seen:", "        if False:"),
    ("a listed file with no block is accepted", Fi, "            if path not in seen and not any(f.path == path for f in files):", "            if False:"),
    ("a written file that is not listed is accepted", Fi, "        for path in sorted(seen - set(listed)):", "        for path in []:"),
    ("an unlisted entry is accepted", Fi, "    for item_id in unlisted:", "    for item_id in []:"),
    ("other artefacts are judged too", Fi, "    kind = KINDS.get(skill_key)\n    if kind is None:\n        return []\n    files, problems = parse_code(body)", "    kind = KINDS.get(skill_key) or KINDS['backend_code']\n    files, problems = parse_code(body)"),
    ("the hook in check_body is removed", Ag, "    problems = (problems + file_problems(skill.key, body, skill.items))[:MAX_PROBLEMS]", "    pass"),
    # ---- the writer
    ("a body with problems is written anyway", Sv, "        if problems:\n            raise BuildRefused(\"the files cannot be written: \"", "        if False:\n            raise BuildRefused(\"the files cannot be written: \""),
    ("a body with no files is accepted", Sv, "        if not files:\n            raise BuildRefused(\"the artefact has no files to write\")", "        if False:\n            raise BuildRefused(\"the artefact has no files to write\")"),
    ("any artefact may be written", Sv, "        if kind is None:\n            raise BuildRefused(f\"'{skill.key}' is not an artefact that holds code\")\n        problems", "        kind = kind or KINDS['backend_code']\n        problems"),
    ("the old folder is emptied before the new one is ready", Sv, "            ws.remove_folder(STAGE)\n            for file in files:", "            ws.remove_folder(kind.folder)\n            ws.remove_folder(STAGE)\n            for file in files:"),
    ("files are written straight into the folder", Sv, 'ws.write_file(f"{STAGE}/{file.path}", file.text)', "ws.write_file(file.path, file.text)"),
    ("every folder is replaced", Sv, "            ws.replace_folder(staged, kind.folder)", "            ws.replace_folder(STAGE, '.')"),
    ("the staging folder is left behind", Sv, "            _quietly(ws.remove_folder, STAGE)", "            pass"),
    ("the staging path shows in a refusal", Sv, 'reason = str(exc).replace(f"{STAGE}/", "")', "reason = str(exc)"),
    ("a leftover staging folder is not cleared first", Sv, "            ws.remove_folder(STAGE)\n            for file in files:", "            for file in files:"),
    ("a replaced folder is reported as new", Sv, "            existed = bool(_files_under(ws, kind.folder))", "            existed = False"),
    ("a write is not audited", Sv, '        self._audit(project_id, actor, "build.files_written", skill.key, {"folder": kind.folder, "files": len(paths), "replaced": existed})', "        pass"),
    ("a refused write is not audited", Sv, '            self._audit(project_id, actor, "build.files_refused", skill.key, {"reason": reason[:200]})', "            pass"),
    ("a file's contents are audited", Sv, '{"folder": kind.folder, "files": len(paths), "replaced": existed}', '{"folder": kind.folder, "files": len(paths), "replaced": existed, "text": files[0].text}'),
    ("a check is not audited", Sv, '        self._audit(project_id, actor, "build.checked", skill_key, {"status": result.status, "facts": result.facts})', "        pass"),
    ("the wrong check is run for the frontend", Sv, "        elif skill_key == \"frontend_code\":\n            result = checks.check_frontend(run, ws)", "        elif skill_key == \"frontend_code\":\n            result = checks.check_backend(run, ws)"),
    ("the design's tables are not passed to the check", Sv, "result = checks.check_database(run, ws, design_tables)", "result = checks.check_database(run, ws)"),
    # ---- the workspace folder tools
    ("a folder is removed even if it is a file", W, "        if not target.is_dir():\n            raise PathRefused(f\"{self.shown(target)} is a file; only folders can be removed this way\")", "        if False:\n            pass"),
    ("a missing folder is reported as removed", W, "        if not target.exists():\n            return False\n        if not target.is_dir():", "        if not target.exists():\n            return True\n        if not target.is_dir():"),
    ("the destination is emptied before the source is checked", W, "        src = self.resolve(source, must_exist=True)\n        dst = self.resolve(destination)", "        dst = self.resolve(destination)\n        if dst.exists() and dst.is_dir():\n            shutil.rmtree(dst)\n        src = self.resolve(source, must_exist=True)"),
    ("a folder may replace itself", W, "        if src == dst or src in dst.parents or dst in src.parents:", "        if False:"),
    ("the old files stay when a folder is replaced", W, "            shutil.rmtree(dst)\n        os.replace(src, dst)", "            pass\n        os.replace(src, dst)"),
    # ---- the checks
    ("the database script is run once", Ck, '    second = run("python", ["db/init_db.py"])\n    if not second.ok:', '    second = first\n    if not second.ok:'),
    ("a failed init is a pass", Ck, "    if not first.ok:\n        return CheckResult(name, FAILED, \"db/init_db.py failed\"", "    if False:\n        return CheckResult(name, FAILED, \"db/init_db.py failed\""),
    ("a missing database file is not noticed", Ck, '    if "db/app.db" not in _files_under(ws, "db"):', "    if False:"),
    ("no tables is a pass", Ck, "    if not created:\n        problems.append", "    if False:\n        problems.append"),
    ("a missing table is a pass", Ck, "    missing = [t for t in design_tables if t.lower() not in lower]", "    missing = []"),
    ("table names are matched with case", Ck, "    lower = {t.lower() for t in created}\n    missing = [t for t in design_tables if t.lower() not in lower]", "    lower = set(created)\n    missing = [t for t in design_tables if t not in lower]"),
    ("the listed tables include the system ones", Ck, "AND name NOT LIKE 'sqlite_%' ORDER BY name", "ORDER BY name"),
    ("a refused command is a failure of the code", Ck, 'if result.status == "refused":\n        return CheckResult(name, SKIPPED,', 'if False:\n        return CheckResult(name, SKIPPED,'),
    ("an unavailable sandbox is a pass", Ck, '    if result.status == "unavailable":\n        return CheckResult(name, SKIPPED, f"not checked: {result.reason}"', '    if result.status == "unavailable":\n        return CheckResult(name, PASSED, f"not checked: {result.reason}"'),
    ("a timeout is not a failure", Ck, '    if result.status == "timed_out":\n        return CheckResult(name, FAILED,', '    if result.status == "timed_out":\n        return CheckResult(name, PASSED,'),
    ("a compile error is a pass", Ck, '    if not result.ok:\n        return CheckResult(name, FAILED, "the code does not compile"', '    if False:\n        return CheckResult(name, FAILED, "the code does not compile"'),
    ("no backend files is a pass", Ck, "    if count == 0:                                                 # compileall", "    if False:                                                 # compileall"),
    ("compiled caches are left in the workspace", Ck, '    if _files_under(ws, "backend"):\n        _remove_caches(ws, "backend")', "    pass"),
    ("a cache folder is left empty behind", Ck, "    for directory in sorted(folders, key=len, reverse=True):\n        ws.remove_folder(directory)", "    pass"),
    ("a script syntax error is a pass", Ck, '        if not result.ok:\n            problems.append(f"{script} has a syntax error', '        if False:\n            problems.append(f"{script} has a syntax error'),
    ("a missing local file is not noticed", Ck, "                if target and target not in known:", "                if False:"),
    ("an outside address in a page is not noticed", Ck, '            if _EXTERNAL.search(" " + value) or value.lower().startswith(("http:", "https:", "//")):', "            if False:"),
    ("a protocol-relative address is not noticed", Ck, 'value.lower().startswith(("http:", "https:", "//"))', 'value.lower().startswith(("http:", "https:"))'),
    ("a stylesheet that was not written is not noticed", Ck, '_LOCAL_REFERENCE_ATTRS = {("script", "src"), ("link", "href"), ("img", "src"),', '_LOCAL_REFERENCE_ATTRS = {("script", "src"), ("img", "src"),'),
    ("a data address is looked up as a file", Ck, 'if not target or reference.startswith("data:"):', "if not target:"),
    ("a relative path is read from the wrong folder", Ck, "    base = PurePosixPath(page).parent\n", "    base = PurePosixPath('frontend')\n"),
    ("a leading slash is read from the wrong folder", Ck, '        return "frontend/" + target.lstrip("/")', '        return target.lstrip("/")'),
    ("a web address inside a script is not noticed", Ck, "        if _URL_IN_CODE.search(text):", "        if False:"),
    ("a stylesheet is not searched for web addresses", Ck, 'for path in (p for p in files if p.endswith((".js", ".css"))):', 'for path in (p for p in files if p.endswith(".js")):'),
    ("node being absent fails the check", Ck, 'if result.status in ("refused", "unavailable") and "not installed" in result.reason:\n            skipped_node = True\n            break', "if False:\n            skipped_node = True\n            break"),
    ("node being absent is not mentioned", Ck, 'note = "; scripts not syntax-checked because node is not installed" if skipped_node else ""', 'note = ""'),
    ("no tests is a pass", Ck, "    if count == 0:\n        return CheckResult(name, FAILED, \"no tests were found\"", "    if False:\n        return CheckResult(name, FAILED, \"no tests were found\""),
    ("a collection error is a pass", Ck, "    if (not result.ok and result.exit_code != 5) or errors:", "    if False:"),
    ("pytest's no-tests exit is a collection error", Ck, "    if (not result.ok and result.exit_code != 5) or errors:", "    if not result.ok or errors:"),
    ("the tests are run and not just counted", Ck, 'result = run("pytest", ["--collect-only", "-q"])', 'result = run("pytest", ["-q"])'),
    ("the design's table is read from a plain word", Ck, '        plain = re.match(r"([a-z_][a-z0-9_]*)(?=$|[\\s:,;.(])", text)', '        plain = re.match(r"([A-Za-z_][A-Za-z0-9_]*)(?=$|[\\s:,;.(])", text)'),
    ("a repeated table name is listed twice", Ck, "        if word and word.lower() not in (n.lower() for n in names):", "        if word:"),
    ("only the first table is read", Ck, '        if item.prefix != "TBL":\n            continue', '        if item.prefix != "TBL" or names:\n            continue'),
]
