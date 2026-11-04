"""Deliberate breaks for S17c-2 (the Build phase in the runner: the hook, the extra check, the loop's place, the totals, the event, the put-back).

Run:
  cd backend && python -u -m scripts.mutation_check scripts/mutants/s17c2_phase.py --tests tests/test_build_phase.py tests/test_run_events.py
Every one of these should make the tests FAIL. One that does not is a hole in the tests.
"""
Ph = "app/build/phase.py"
Rn = "app/run/runner.py"
Ev = "app/run/events.py"
Mn = "app/main.py"
Lp = "app/build/loop.py"

MUTANTS = [
    # ---- which phase and which artefacts
    ("every phase wants the hooks", Ph, "        return phase_key == PHASE", "        return True"),
    ("no phase wants the hooks", Ph, "        return phase_key == PHASE", "        return False"),
    ("the extra check is given in any phase", Ph, '        if phase_key != PHASE or artefact_key not in KINDS:\n            return None', '        if artefact_key not in KINDS:\n            return None'),
    ("the extra check is given to any artefact", Ph, '        if phase_key != PHASE or artefact_key not in KINDS:\n            return None', '        if phase_key != PHASE:\n            return None'),
    ("the extra check is never given", Ph, '        if phase_key != PHASE or artefact_key not in KINDS:\n            return None', "        return None\n        if phase_key != PHASE or artefact_key not in KINDS:\n            return None"),
    # ---- when the loop runs
    ("the loop does not need the backend", Ph, 'NEEDED_FOR_LOOP = ("backend_code", "test_suite")', 'NEEDED_FOR_LOOP = ("test_suite",)'),
    ("the loop does not need the tests", Ph, 'NEEDED_FOR_LOOP = ("backend_code", "test_suite")', 'NEEDED_FOR_LOOP = ("backend_code",)'),
    ("the loop needs the frontend too", Ph, 'NEEDED_FOR_LOOP = ("backend_code", "test_suite")', 'NEEDED_FOR_LOOP = ("backend_code", "test_suite", "frontend_code")'),
    ("a missing artefact does not skip the loop", Ph, "        if missing:\n            await self._put_back(project_id)", "        if False:\n            await self._put_back(project_id)"),
    ("the skip is not explained", Ph, '            return BuildOutcome(False, "skipped", f"the tests were not run because {why}")', '            return BuildOutcome(False, "skipped", "")'),
    ("the failure reason is dropped", Ph, "{failed.get(k) or skipped.get(k) or 'was not written in this run'}", "{'was not written in this run'}"),
    ("a stopped run still runs the loop", Ph, "        if stop_reason is not None:\n            await self._put_back(project_id)", "        if False:\n            await self._put_back(project_id)"),
    ("the stop is not explained", Ph, 'f"the tests were not run because the run was stopped ({stop_reason})"', '"the tests were not run"'),
    ("a skipped loop leaves the attempt in the workspace", Ph, "        if missing:\n            await self._put_back(project_id)\n", "        if missing:\n"),
    ("a stopped run leaves the attempt in the workspace", Ph, "        if stop_reason is not None:\n            await self._put_back(project_id)\n", "        if stop_reason is not None:\n"),
    ("the loop is run without the meter", Ph, "self.loop.run(project_id, run_id=run_id, meter=meter, actor=\"system\", on_event=on_event)", "self.loop.run(project_id, run_id=run_id, meter=None, actor=\"system\", on_event=on_event)"),
    ("the loop is run without the run id", Ph, "self.loop.run(project_id, run_id=run_id, meter=meter,", "self.loop.run(project_id, run_id=None, meter=meter,"),
    ("the loop is run without the event sink", Ph, "actor=\"system\", on_event=on_event)", "actor=\"system\", on_event=None)"),
    ("the outcome loses its rounds", Ph, "rounds=len(result.rounds), calls=result.calls", "rounds=0, calls=result.calls"),
    ("the outcome loses its calls", Ph, "rounds=len(result.rounds), calls=result.calls", "rounds=len(result.rounds), calls=0"),
    ("the outcome says ran when it did not", Ph, 'return BuildOutcome(False, "skipped", f"the tests were not run because {why}")', 'return BuildOutcome(True, "skipped", f"the tests were not run because {why}")'),
    # ---- the runner
    ("the runner ignores the hooks", Rn, "extra_check=self.build.extra_check(phase_key, key, project_id) if self.build is not None else None,", "extra_check=None,"),
    ("the runner gives the hooks the wrong phase", Rn, "self.build.extra_check(phase_key, key, project_id)", "self.build.extra_check('build', key, project_id)"),
    ("the loop never runs in the runner", Rn, "        if self.build is not None and self.build.wants(phase_key):", "        if False:"),
    ("the loop runs in every phase", Rn, "        if self.build is not None and self.build.wants(phase_key):", "        if self.build is not None:"),
    ("the loop's stop is not noticed", Rn, "            build_outcome = await self._build_loop(run_id, project_id, done, failed, skipped, meter, stop_reason)\n            stop_reason = stop_reason or meter.should_stop()", "            build_outcome = await self._build_loop(run_id, project_id, done, failed, skipped, meter, stop_reason)"),
    ("the loop's ending is not in the totals", Rn, '        if build_outcome is not None:\n            totals["build"] =', '        if False:\n            totals["build"] ='),
    ("the loop's ending is not in the result", Rn, "serial, wall, max_in_flight, build_outcome,\n        )", "serial, wall, max_in_flight, None,\n        )"),
    ("the totals lose the rounds", Rn, '"reason": clean_reason(build_outcome.reason, self.settings.secret_values()), "rounds": build_outcome.rounds}', '"reason": clean_reason(build_outcome.reason, self.settings.secret_values()), "rounds": 0}'),
    ("the totals keep an unclean reason", Rn, '"reason": clean_reason(build_outcome.reason, self.settings.secret_values()),', '"reason": build_outcome.reason,'),
    ("the stop reason is not passed to the hook", Rn, "lambda kind, data: self.bus.publish(project_id, run_id, kind, data), stop_reason,", "lambda kind, data: self.bus.publish(project_id, run_id, kind, data), None,"),
    ("the events are not published", Rn, "lambda kind, data: self.bus.publish(project_id, run_id, kind, data), stop_reason,", "lambda kind, data: None, stop_reason,"),
    ("the event goes to the wrong run", Rn, "lambda kind, data: self.bus.publish(project_id, run_id, kind, data), stop_reason,", "lambda kind, data: self.bus.publish(project_id, 'wrong-run', kind, data), stop_reason,"),
    # ---- the event and the app
    ("the event is not in the vocabulary", Ev, '    "artefact.skipped",\n    "build.round",\n', '    "artefact.skipped",\n'),
    ("the loop reports no rounds", Lp, '                emit("build.round", round_event(number, artefact, last.failed, last.errors))', "                pass"),
    ("the event names the wrong team", Lp, '    return {"round": number, "artefact": artefact, "failed": failed, "errors": errors}', '    return {"round": number, "artefact": "backend_code", "failed": failed, "errors": errors}'),
    ("the event carries no counts", Lp, '    return {"round": number, "artefact": artefact, "failed": failed, "errors": errors}', '    return {"round": number, "artefact": artefact}'),
    ("the event carries the output", Lp, '    return {"round": number, "artefact": artefact, "failed": failed, "errors": errors}', '    return {"round": number, "artefact": artefact, "failed": failed, "errors": errors, "output": "FULL OUTPUT"}'),
    ("the app builds no hooks", Mn, "app.state.runner = PhaseRunner(cfg, store, engine, app.state.agents, app.state.reviews, bus, build=app.state.build)", "app.state.runner = PhaseRunner(cfg, store, engine, app.state.agents, app.state.reviews, bus)"),
]
