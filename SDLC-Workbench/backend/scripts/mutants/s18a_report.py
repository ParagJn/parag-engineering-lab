"""Deliberate breaks for S18a (the test report: which loop, how it ended, the numbers, the failing tests, the endpoint claim, the hook that writes it).

Run:
  cd backend && python -u -m scripts.mutation_check scripts/mutants/s18a_report.py --tests tests/test_build_report.py tests/test_build_phase.py
Every one of these should make the tests FAIL. One that does not is a hole in the tests.
"""
Rp = "app/build/report.py"
Ph = "app/build/phase.py"
Rn = "app/run/runner.py"

MUTANTS = [
    # ---- which loop, how it ended
    ("an empty list is not recognised", Rp, "    if not rounds:\n        return ()\n    newest", "    newest"),
    ("the oldest loop is reported", Rp, "    newest = max(rounds, key=lambda r: r.id).loop_id", "    newest = min(rounds, key=lambda r: r.id).loop_id"),
    ("the rounds are not in order", Rp, "key=lambda r: r.round)", "key=lambda r: -r.round)"),
    ("every loop is mixed together", Rp, "    return tuple(sorted((r for r in rounds if r.loop_id == newest),", "    return tuple(sorted((r for r in rounds),"),
    ("the ending is the first round", Rp, '    return loop[-1].outcome if loop else "never_run"', '    return loop[0].outcome if loop else "never_run"'),
    ("a missing loop has no ending", Rp, '    return loop[-1].outcome if loop else "never_run"', '    return loop[-1].outcome'),
    # ---- the wording
    ("a cap reached reads as a pass", Rp, '"cap_reached": "The tests were still failing when the fix rounds ran out.",', '"cap_reached": "All the generated tests passed.",'),
    ("no tests reads as a pass", Rp, '"no_tests": "No tests were found. That is not a pass.",', '"no_tests": "All the generated tests passed.",'),
    ("a blocked sandbox reads as a failure of the code", Rp, '"blocked": "The tests could not be judged: the sandbox could not run anything.",', '"blocked": "The tests were failing.",'),
    ("an unknown ending is hidden", Rp, '    out += [ENDINGS.get(ending, f"The loop ended as \'{ending}\'."),', '    out += [ENDINGS.get(ending, ""),'),
    ("a passing ending is not PASSING", Rp, 'PASSING = ("passed",)', "PASSING = ()"),
    ("a stopped ending is PASSING", Rp, 'PASSING = ("passed",)', 'PASSING = ("passed", "stopped")'),
    # ---- the numbers
    ("the final run shows the first round", Rp, "        last = loop[-1]\n        out += [ENDINGS", "        last = loop[0]\n        out += [ENDINGS"),
    ("the errors are left out of the final line", Rp, "{last.failed} failed, {last.errors} errors, {last.skipped} skipped.\",\n                f\"The generated tests were run", "{last.failed} failed, {last.skipped} skipped.\",\n                f\"The generated tests were run"),
    ("the run count is wrong", Rp, "were run {len(loop)} time(s)", "were run {len(loop) + 1} time(s)"),
    ("the time is only the last round", Rp, "taking {sum(r.seconds for r in loop):.1f} seconds in all", "taking {loop[-1].seconds:.1f} seconds in all"),
    ("a round line loses its counts", Rp, "{r.passed} passed, {r.failed} failed, {r.errors} errors, {r.skipped} skipped, in {r.seconds:.1f}s.{who}", "{r.passed} passed, in {r.seconds:.1f}s.{who}"),
    ("a round line loses who was asked", Rp, '    who = f" A fix was asked of the {r.artefact.replace(\'_\', \' \')}" + (f" (saved as version {r.version})." if r.version else ".") if r.artefact else ""', '    who = ""'),
    ("a round line loses the version", Rp, '(f" (saved as version {r.version})." if r.version else ".")', '"."'),
    ("every round is not listed", Rp, "        out += [_round_line(r) for r in loop]", "        out += [_round_line(r) for r in loop[:1]]"),
    # ---- the failing tests
    ("the failures come from the first round", Rp, "list(loop[-1].failures)[:MAX_FAILURES_SHOWN] if loop else []", "list(loop[0].failures)[:MAX_FAILURES_SHOWN] if loop else []"),
    ("every failure is listed", Rp, "list(loop[-1].failures)[:MAX_FAILURES_SHOWN] if loop else []", "list(loop[-1].failures) if loop else []"),
    ("the failure limit is eleven", Rp, "MAX_FAILURES_SHOWN = 10", "MAX_FAILURES_SHOWN = 11"),
    ("a message is not cut", Rp, "str(f['message'])[:MAX_MESSAGE_CHARS]", "str(f['message'])"),
    ("the message limit is 300", Rp, "MAX_MESSAGE_CHARS = 200", "MAX_MESSAGE_CHARS = 300"),
    ("the unlisted count is not shown", Rp, "        if total > len(final_failures):", "        if False:"),
    ("the unlisted count ignores errors", Rp, "        total = loop[-1].failed + loop[-1].errors", "        total = loop[-1].failed"),
    ("a failing run with nothing recorded reads as none", Rp, '        out.append("None." if loop and ending in PASSING else "No failing test is recorded for the final run.")', '        out.append("None.")'),
    # ---- the endpoint claim
    ("a missing design is claimed as covered", Rp, "    if not design_body or not tests_body:\n        return None", "    if not tests_body:\n        return None"),
    ("a missing suite is claimed as covered", Rp, "    if not design_body or not tests_body:\n        return None", "    if not design_body:\n        return None"),
    ("a table counts as an endpoint", Rp, '    endpoints = tuple(i.id for i in parse_items(design_body, design_specs).items if i.prefix == "API")', "    endpoints = tuple(i.id for i in parse_items(design_body, design_specs).items)"),
    ("every endpoint counts as named", Rp, "    return Coverage(endpoints, tuple(e for e in endpoints if e in named))", "    return Coverage(endpoints, endpoints)"),
    ("no endpoint counts as named", Rp, "    return Coverage(endpoints, tuple(e for e in endpoints if e in named))", "    return Coverage(endpoints, ())"),
    ("the unnamed list is the named list", Rp, "        return tuple(e for e in self.endpoints if e not in self.named)", "        return tuple(e for e in self.endpoints if e in self.named)"),
    ("the claim reads as proof", Rp, "This is what the tests say about themselves; the run above is what shows whether they pass.", "This shows the endpoints are tested."),
    ("the gap is not listed", Rp, "        if cover.unnamed:", "        if False:"),
    ("the no-comparison case says nothing", Rp, '        out.append("There is no design or no test suite to compare, so nothing can be said about which endpoints the tests name.")', '        out.append("")'),
    ("the test files are not listed", Rp, "    files = [f.path for f in parse_code(tests_body)[0]] if tests_body else []", "    files = []"),
    ("the no-model sentence is dropped", Rp, "No model was asked what the tests did.", ""),
    # ---- the hook
    ("the report is not written", Ph, "        await self.write_report(project_id)\n        return BuildOutcome(True", "        return BuildOutcome(True"),
    ("the report is written before the loop", Ph, "        result: LoopResult = await self.loop.run(project_id, run_id=run_id, meter=meter, actor=\"system\", on_event=on_event)   # puts the workspace back itself\n        await self.write_report(project_id)", "        await self.write_report(project_id)\n        result: LoopResult = await self.loop.run(project_id, run_id=run_id, meter=meter, actor=\"system\", on_event=on_event)   # puts the workspace back itself"),
    ("a skipped loop still writes a report", Ph, "        missing = [k for k in NEEDED_FOR_LOOP if k not in done]\n        if missing:\n            await self._put_back(project_id)", "        missing = [k for k in NEEDED_FOR_LOOP if k not in done]\n        if missing:\n            await self.write_report(project_id)\n            await self._put_back(project_id)"),
    ("the report is attributed to a person", Rp, 'REPORT_AUTHOR = "agent:test_engineer@system"', 'REPORT_AUTHOR = "human:system"'),
    ("the report is the wrong phase", Ph, 'artefact_type="test_report", phase_key=PHASE,', 'artefact_type="test_report", phase_key="design",'),
    ("the report loses its record", Ph, 'generation={"skill": "test_report", "written_by": "system", "ending": ending_of(loop), "rounds": len(loop)},', "generation=None,"),
    ("the report reads the oldest loop", Ph, "        loop = last_loop(self.store.build_rounds.list(project_id))", "        loop = tuple(self.store.build_rounds.list(project_id))"),
    ("the hook does not say what it writes", Ph, '        return HOOK_WRITES if phase_key == PHASE else ()', "        return ()"),
    ("the hook writes in every phase", Ph, '        return HOOK_WRITES if phase_key == PHASE else ()', "        return HOOK_WRITES"),
    # ---- the runner
    ("the runner still schedules the report", Rn, "        wanted = [k for k in wanted if k not in hook_writes]", "        pass"),
    ("the runner leaves out everything", Rn, "        wanted = [k for k in wanted if k not in hook_writes]", "        wanted = []"),
    ("the runner ignores what the hook writes", Rn, "        hook_writes = set(self.build.writes(phase_key)) if self.build is not None else set()", "        hook_writes = set()"),
]
