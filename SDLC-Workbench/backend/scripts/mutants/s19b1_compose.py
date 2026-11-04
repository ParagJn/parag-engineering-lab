"""Deliberate breaks for S19b-1 (writing the instruction set in pieces: the composer, the per-piece conversation, the set-level gaps, the size limit).

Run:
  cd backend && python -u -m scripts.mutation_check scripts/mutants/s19b1_compose.py --tests tests/test_compose.py tests/test_instructions.py tests/test_agent_runtime.py
Every one of these should make the tests FAIL. One that does not is a hole in the tests.
"""
Cp = "app/build/compose.py"
In = "app/build/instructions.py"
Rt = "app/agents/runtime.py"
Rp = "app/agents/reply.py"
Ck = "app/agents/checks.py"

MUTANTS = [
    # ---- order and concurrency
    ("the foundation is not written first", Cp, "        foundation = await write(\n            I.FOUNDATION_NAME, I.FOUNDATION, _request_foundation(use_cases, design), \"\", 1, \"foundation\",\n        )", "        foundation = Piece(I.FOUNDATION_NAME, I.FOUNDATION, \"# x\", (), ())"),
    ("a use case is not shown the foundation", Cp, "return await write(name, I.SCENARIO, _request_use_case(name, uc_id, title, text), shown_foundation, index, \"use_case\")", "return await write(name, I.SCENARIO, _request_use_case(name, uc_id, title, text), \"\", index, \"use_case\")"),
    ("the concurrency limit is ignored", Cp, "sem = asyncio.Semaphore(max(1, int(self.settings.run_max_concurrency)))", "sem = asyncio.Semaphore(100)"),
    ("everything runs one at a time", Cp, "sem = asyncio.Semaphore(max(1, int(self.settings.run_max_concurrency)))", "sem = asyncio.Semaphore(1)"),
    ("acceptance sees no digest", Cp, "I.ACCEPTANCE_NAME, I.ACCEPTANCE, _request_acceptance(), digest, total, \"acceptance\"", "I.ACCEPTANCE_NAME, I.ACCEPTANCE, _request_acceptance(), \"\", total, \"acceptance\""),
    ("the digest leaves out the foundation", Cp, "done = {foundation.name: foundation.body, **{p.name: p.body for p in scenarios}}", "done = {p.name: p.body for p in scenarios}"),
    ("the digest drops a section", Cp, 'DIGEST_SECTIONS = ("What to build", "Business rules that apply", "Done when", "Traceability")', 'DIGEST_SECTIONS = ("What to build", "Business rules that apply", "Traceability")'),
    ("the digest holds whole files", Cp, "        for section in DIGEST_SECTIONS:", "        for section in I.SECTIONS[I.SCENARIO]:"),
    ("the digest is not bounded", Cp, "    if len(text) > DIGEST_MAX_CHARS:", "    if False:"),
    ("the digest is not neutralised", Cp, "lines.append(f\"### {section}\\n{neutralise(text)}\")", "lines.append(f\"### {section}\\n{text}\")"),
    ("a file is not neutralised", Cp, "f\"## {name}\\n{neutralise(text).strip()}\" for name, text in files.items()", "f\"## {name}\\n{text.strip()}\" for name, text in files.items()"),
    ("the use case text is not neutralised", Cp, "The use case, as the design states it: {neutralise(text).strip()}", "The use case, as the design states it: {text.strip()}"),
    ("the brief is not neutralised", Cp, "{neutralise(brief).strip() or '(no brief was given)'}", "{brief.strip() or '(no brief was given)'}"),
    ("the use cases are not put in order", Cp, "        return sorted(cases)", "        return cases"),
    # ---- names, titles, requests
    ("the file name comes from the wrong id", Cp, "name = I.scenario_name(uc_id, title)", "name = I.scenario_name('UC-000', title)"),
    ("the use case id is not in its request", Cp, "for the use case {uc_id} (", "for the use case ("),
    ("the traceability instruction is dropped", Cp, " The Traceability section must name {uc_id}.", ""),
    ("the foundation is not told the use cases", Cp, "    uc = \"\\n\".join(f\"- {i} {t}\" for i, t, _ in use_cases)", "    uc = \"\""),
    ("the foundation is not told the items to cover", Cp, "f\"Every design item that must be built by some file or listed under 'Not covered' as '- <ID> <reason>': endpoints (API): {_ids(design, 'API')}; \"", "f\"Every design item: endpoints (API): \""),
    ("the system prompt does not say one file", Cp, "- Write ONE file, as Markdown,", "- Write the file, as Markdown,"),
    ("the stage is wrong", Cp, 'I.FOUNDATION_NAME, I.FOUNDATION, _request_foundation(use_cases, design), "", 1, "foundation"', 'I.FOUNDATION_NAME, I.FOUNDATION, _request_foundation(use_cases, design), "", 1, "use_case"'),
    ("the total is wrong", Cp, "    total = len(use_cases) + 2", "    total = len(use_cases) + 1"),
    ("the use case index starts at the foundation", Cp, "asyncio.create_task(one(n + 2, uc_id, title, text))", "asyncio.create_task(one(n + 1, uc_id, title, text))"),
    ("a title mark is kept", In, '''    head = re.sub(r"\\s+", " ", re.sub(r"\\*\\*|__|`", "", head)).strip(" .*_")''', '''    head = re.sub(r"\\s+", " ", head).strip(" .*_")'''),
    ("a title is not cut", In, "    return head[:80].strip() or \"use case\"", "    return head.strip() or \"use case\""),
    ("an empty title stays empty", In, "    return head[:80].strip() or \"use case\"", "    return head[:80].strip()"),
    ("the derives tail stays in the title", In, "    plain = _TITLE_END.sub(\"\", text or \"\").strip()", "    plain = (text or \"\").strip()"),
    # ---- the per-file checks
    ("the file checks are skipped", Cp, "                problems += I.check_file(kind, name, body, design)", "                pass"),
    ("an unknown derive is accepted", Cp, "                    if target not in design.ids:", "                    if False:"),
    ("a citation is accepted", Cp, "                if unknown_citations(body, ()):", "                if False:"),
    ("a drawing is not checked", Cp, "                problems += drawing_problems(body)\n", ""),
    ("a secret is not checked", Cp, "                problems = list(scanner.problems(body))", "                problems = []"),
    ("a cut-off reply is not explained", Cp, "return ([CUT_OFF_BEFORE_CLOSING] if result.finish_reason in TRUNCATED_REASONS else [str(exc)]), \"\"", "return [str(exc)], \"\""),
    ("a cut-off reply with a closed tag passes", Cp, "                if result.finish_reason in TRUNCATED_REASONS:\n                    problems.append(\"the reply was cut off by the output limit; write a shorter file that still has every section\")", "                pass"),
    ("a file mark inside a file is accepted", In, "    if any(FILE_MARK.match(l) for l in body.replace(\"\\r\\n\", \"\\n\").split(\"\\n\")):", "    if False:"),
    ("a set heading inside a file is accepted", In, "    clash = sorted(h for h in RESERVED_HEADINGS if section_bodies(body, h))\n    if clash:\n        problems.append(f\"the heading", "    clash = []\n    if clash:\n        problems.append(f\"the heading"),
    ("a derives of no ID is accepted", In, "    elif not derives_of(body):", "    elif False:"),
    # ---- all or nothing
    ("a failed file does not stop the others", Cp, "        except BaseException:\n            for t in tasks:\n                t.cancel()\n            await asyncio.gather(*tasks, return_exceptions=True)\n            raise", "        except BaseException:\n            raise"),
    ("a stopped run still starts a file", Cp, "            if meter is not None and (why := meter.should_stop()) is not None:", "            if False:"),
    ("a stop is not raised", Cp, "            except RunStopped:\n                raise\n            except AgentError as exc:", "            except RunStopped:\n                pass\n            except AgentError as exc:"),
    ("calls are not counted by the meter", Cp, "            meter.add_call(result.cost_usd, result.tokens_in, result.tokens_out)\n            # as in the runner", "            # as in the runner"),
    ("a cap drops a file that needs no repair", Cp, "            return meter.should_stop() if problems else None", "            return meter.should_stop()"),
    ("a failed file is not reported", Cp, "                say(\"piece.failed\", {\"file\": name, \"reason\": clean_reason(str(exc), secrets)})", "                pass"),
    ("a failure reason is not cleaned", Cp, "{\"file\": name, \"reason\": clean_reason(str(exc), secrets)}", "{\"file\": name, \"reason\": str(exc)}"),
    ("a finished file is not reported", Cp, "            say(\"piece.finished\", {", "            (lambda *a: None)(\"piece.finished\", {"),
    ("a started file is not reported", Cp, "            say(\"piece.started\", {\"file\": name, \"stage\": stage, \"index\": index, \"of\": total})", "            pass"),
    ("the set is not checked before saving", Cp, "        problems = check_body(body, skill, (), item_ctx, None, self.runtime.scanner)\n        if problems:", "        problems = []\n        if problems:"),
    ("the final problems are not raised", Cp, "        if problems:\n            raise OutputInvalid(\n                f\"'{skill.artefact.name}' could not be put together", "        if False:\n            raise OutputInvalid(\n                f\"'{skill.artefact.name}' could not be put together"),
    # ---- use cases bounds
    ("no use cases is accepted", Cp, "        if not cases:", "        if False:"),
    ("too many use cases are accepted", Cp, "        if len(cases) > I.MAX_USE_CASES:", "        if False:"),
    ("the title is not neutralised in the request", Cp, "({neutralise(title)}).", "({title})."),
    ("the use case limit is 14", In, "MAX_USE_CASES = 15", "MAX_USE_CASES = 14"),
    ("the use case limit is 16", In, "MAX_USE_CASES = 15", "MAX_USE_CASES = 16"),
    ("the upstream size is not checked", Cp, "        self.runtime.check_upstream_size(skill, upstream)", "        pass"),
    # ---- the saved record
    ("the gaps are not recorded", Cp, "            \"gaps\": list(gaps),\n", ""),
    ("the pieces are not recorded", Cp, "            \"pieces\": [{\"file\": p.name, \"kind\": p.kind, \"attempts\": len(p.calls), \"calls\": [c.call_id for c in p.calls]} for p in pieces],\n", ""),
    ("repairs are calls minus one", Cp, "\"repairs\": len(calls) - len(pieces),", "\"repairs\": len(calls) - 1,"),
    ("a repair does not say which file", Cp, "log = [{**entry, \"file\": p.name} for p in pieces for entry in p.repair_log]", "log = [{**entry} for p in pieces for entry in p.repair_log]"),
    ("the previous items are not passed", Cp, "previous = [(item.id, item.text) for item in item_ctx.previous]", "previous = []"),
    ("the highest id is not passed", Cp, "highest=int(item_ctx.highest.get(I.ITEM_PREFIX, 0))", "highest=0"),
    ("the id prefix is wrong", Cp, "item_ctx.highest.get(I.ITEM_PREFIX, 0)", "item_ctx.highest.get('XXX', 0)"),
    # ---- gaps
    ("gaps are not computed", In, "    return [u for u in design.of(\"UC\") if u not in have] + coverage(files, design)[\"uncovered\"]", "    return []"),
    ("gaps leave out the use cases", In, "    return [u for u in design.of(\"UC\") if u not in have] + coverage(files, design)[\"uncovered\"]", "    return coverage(files, design)[\"uncovered\"]"),
    ("gaps leave out the design items", In, "    return [u for u in design.of(\"UC\") if u not in have] + coverage(files, design)[\"uncovered\"]", "    return [u for u in design.of(\"UC\") if u not in have]"),
    ("the coverage check ignores unbuilt items", In, "    unbuilt = coverage(files, design)[\"uncovered\"] if design else []", "    unbuilt = []"),
    ("the coverage check says None when gaps exist", In, "    if not uncovered and not unbuilt:\n        out.append(\"None\")", "    if True:\n        out.append(\"None\")"),
    ("acknowledged gaps are still reported", In, "        if use_case not in by_use_case and use_case not in skip:", "        if use_case not in by_use_case:"),
    ("acknowledged items are still reported", In, "    open_items = [i for i in cover[\"uncovered\"] if i not in skip]", "    open_items = list(cover[\"uncovered\"])"),
    ("every gap is taken as acknowledged", In, "    acknowledged = ids_in(\" \".join(section_bodies(head, \"Coverage check\")))", "    acknowledged = ids_in(body or \"\") + list(design.ids)"),
    ("the acknowledgement reads the whole body", In, "    head = (body or \"\").split(\"=== FILE:\", 1)[0]\n    acknowledged", "    head = (body or \"\")\n    acknowledged"),
    # ---- limits
    ("the set limit is the single-artefact limit", In, "SET_MAX_CHARS = 200_000", "SET_MAX_CHARS = 60_000"),
    ("the set limit is not used", Ck, "SET_MAX_CHARS if skill.key == INSTRUCTIONS_KEY else MAX_BODY_CHARS", "MAX_BODY_CHARS"),
    ("every artefact gets the set limit", Ck, "SET_MAX_CHARS if skill.key == INSTRUCTIONS_KEY else MAX_BODY_CHARS", "SET_MAX_CHARS"),
    ("the validate limit is ignored", Rp, "    if len(body) > max_chars:", "    if len(body) > MAX_BODY_CHARS:"),
    ("the role limit is dropped", "app/config.py", ",solution_architect=16000\"", "\""),
    ("the role limit is 8000", "app/config.py", "solution_architect=16000", "solution_architect=8000"),
    # ---- the runtime split
    ("the repair budget is ignored", Rt, "        max_attempts = self.settings.agent_max_repairs + 1\n        for attempt", "        max_attempts = 1\n        for attempt"),
    ("a label is ignored in the failure", Rt, "        what = label or skill.artefact.name", "        what = skill.artefact.name"),
    ("a stop is not raised in a conversation", Rt, "                if stop is not None:\n                    raise RunStopped(\n                        f\"'{what}'", "                if False:\n                    raise RunStopped(\n                        f\"'{what}'"),
    ("the extra generation is dropped", Rt, "            **(extra_generation or {}),\n", ""),
    ("the extra generation replaces the record", Rt, "            **(extra_generation or {}),\n        }", "        }\n        generation = extra_generation or generation"),
    ("built_on is lost when composing", Rt, "built_on=tuple((u.artefact_id, u.version) for u in upstream))\n        return self._save", "built_on=())\n        return self._save"),
]
