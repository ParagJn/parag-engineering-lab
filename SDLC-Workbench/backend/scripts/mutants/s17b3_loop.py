"""Deliberate breaks for S17b-3 (the write -> test -> fix loop: routing, stop conditions, fingerprint, cap, the record, the workspace rule).

Run:
  cd backend && python -u -m scripts.mutation_check scripts/mutants/s17b3_loop.py --tests tests/test_build_loop.py
Every one of these should make the tests FAIL. One that does not is a hole in the tests.
"""
Lp = "app/build/loop.py"
Cf = "app/config.py"

MUTANTS = [
    # ---- fingerprint and reading a run
    ("the fingerprint depends on order", Lp, '    names = sorted({f"{f.kind}:{f.test}" for f in report.failures})', '    names = list(dict.fromkeys(f"{f.kind}:{f.test}" for f in report.failures))'),
    ("the fingerprint ignores the kind", Lp, '    names = sorted({f"{f.kind}:{f.test}" for f in report.failures})', '    names = sorted({f.test for f in report.failures})'),
    ("the fingerprint ignores the test", Lp, '    names = sorted({f"{f.kind}:{f.test}" for f in report.failures})', '    names = sorted({f.kind for f in report.failures})'),
    ("the fingerprint is never empty", Lp, '    if not names:\n        return ""', '    if False:\n        return ""'),
    ("the fingerprint is longer", Lp, ".hexdigest()[:16]", ".hexdigest()[:20]"),
    ("a collection error goes to the backend", Lp, "    if report.status in TEST_ERROR_STATUSES:\n        return TESTS", "    if False:\n        return TESTS"),
    ("a test error goes to the backend", Lp, '    if any(f.kind == "error" for f in report.failures):\n        return TESTS', "    if False:\n        return TESTS"),
    ("an assertion failure goes to the tests", Lp, "    if report.failures or report.failed or report.errors:\n        return BACKEND", "    if report.failures or report.failed or report.errors:\n        return TESTS"),
    ("a passing run is routed to somebody", Lp, "    if report.failures or report.failed or report.errors:\n        return BACKEND\n    return None", "    return BACKEND"),
    ("a count of failures without a list is not routed", Lp, "    if report.failures or report.failed or report.errors:", "    if report.failures:"),
    ("a blocked sandbox is judged", Lp, '    if report.status in ("unavailable", "refused"):\n        return "blocked"', "    if False:\n        return 'blocked'"),
    ("a refused run is not blocked", Lp, 'if report.status in ("unavailable", "refused"):', 'if report.status in ("unavailable",):'),
    ("no tests is a pass", Lp, '    if report.status == "no_tests" or (report.status == "ran" and report.total == 0):\n        return "no_tests"', "    if False:\n        return 'no_tests'"),
    ("a run of nothing is not no_tests", Lp, 'if report.status == "no_tests" or (report.status == "ran" and report.total == 0):', 'if report.status == "no_tests":'),
    ("skipped tests alone are a pass", Lp, '    if report.all_passed:\n        return "ok"', '    if report.all_passed or report.total == report.skipped:\n        return "ok"'),
    # ---- what the developer is told
    ("the round number is not told", Lp, '(round {round_number} of {rounds}). Result:', '. Result:'),
    ("the counts are not told", Lp, '    counts = f"{report.passed} passed, {report.failed} failed, {report.errors} errors, {report.skipped} skipped"', '    counts = ""'),
    ("every failure is told", Lp, "SHOWN_FAILURES = 10", "SHOWN_FAILURES = 1000"),
    ("the failure limit is eleven", Lp, "SHOWN_FAILURES = 10", "SHOWN_FAILURES = 11"),
    ("a message is not cut", Lp, "{f.message[:SHOWN_MESSAGE_CHARS]}", "{f.message}"),
    ("the message limit is 500", Lp, "SHOWN_MESSAGE_CHARS = 400", "SHOWN_MESSAGE_CHARS = 500"),
    ("a collection error is not explained", Lp, '    if report.status == "collection_error":', "    if False:"),
    ("an abnormal end is not explained", Lp, '    elif report.status in ("timed_out", "cut_off", "crashed"):', "    elif False:"),
    ("the owner is always the code", Lp, '    owner = "tests" if artefact == TESTS else "code"', '    owner = "code"'),
    ("one failure reads as several", Lp, "'failures' if len(shown) > 1 else 'failure'", "'failures'"),
    ("the record keeps every failure", Lp, "    return [{\"test\": f.test, \"kind\": f.kind, \"message\": f.message} for f in failure_lines(report)]", "    return [{\"test\": f.test, \"kind\": f.kind, \"message\": f.message} for f in report.failures]"),
    # ---- the loop
    ("the setting is ignored", Lp, "        cap = rounds if rounds is not None else self.settings.build_fix_rounds", "        cap = rounds if rounds is not None else 3"),
    ("the argument is ignored", Lp, "        cap = rounds if rounds is not None else self.settings.build_fix_rounds", "        cap = self.settings.build_fix_rounds"),
    ("the loop never reaches the cap", Lp, "                if number == cap + 1:", "                if number == cap + 100:"),
    ("the cap round is not the last", Lp, "                if number == cap + 1:", "                if number == cap:"),
    ("the saved version is not tested first", Lp, '            await asyncio.to_thread(sync_workspace, self.build, self.store, self.library, project_id, actor="system")\n            for number', "            for number"),
    ("the budget is not checked before a round", Lp, "                if meter is not None and (why := meter.should_stop()):", "                if False:"),
    ("a stop is not worded with its reason", Lp, 'final = (STOPPED, f"the run was stopped ({why}) before round {number}")', 'final = (STOPPED, "stopped")'),
    ("a passing run is reported as the cap", Lp, '"ok": (CONVERGED, f"all {last.passed} test(s) passed after {number} run(s) of the tests"),', '"ok": (CAP_REACHED, "x"),'),
    ("no tests is converged", Lp, '"no_tests": (NO_TESTS, "no tests were found, which is never reported as a pass"),', '"no_tests": (CONVERGED, "no tests were found"),'),
    ("blocked is converged", Lp, '"blocked": (BLOCKED, last.reason or "the sandbox cannot run anything, so the tests could not be judged"),', '"blocked": (CONVERGED, "blocked"),'),
    ("the repeat is not noticed", Lp, "                if shot and shot == previous_print:", "                if False:"),
    ("an empty fingerprint counts as a repeat", Lp, "                if shot and shot == previous_print:", "                if shot == previous_print:"),
    ("the repeat is judged before any fix", Lp, "                previous_print = shot\n", "                previous_print = None\n"),
    ("the repeat uses the first fingerprint always", Lp, "                previous_print = shot\n", "                previous_print = previous_print or shot\n"),
    ("no fix is asked for the wrong team", Lp, "                artefact = route(last) or BACKEND", "                artefact = BACKEND"),
    ("the previous draft is not shown", Lp, "previous_draft=self._previous(project_id, skill),", "previous_draft=None,"),
    ("the feedback is not sent", Lp, "feedback=fix_feedback(last, artefact, number, cap),", "feedback=(),"),
    ("the fix is not tried before it is saved", Lp, "                        extra_check=make_extra_check(self.build, self.store, self.library, project_id, skill, actor=f\"agent:{skill.artefact.role}@loop\"),\n", ""),
    ("an invalid reply is not an ending", Lp, "                except OutputInvalid as exc:", "                except ZeroDivisionError as exc:"),
    ("a stopped fix is not an ending", Lp, "                except RunStopped as exc:", "                except ZeroDivisionError as exc:"),
    ("an invalid ending is worded as a stop", Lp, "                    final = (INVALID, f\"the {skill.artefact.name.lower()} could not be fixed: {str(exc)[:200]}\")", "                    final = (STOPPED, 'invalid')"),
    ("the workspace is not put back", Lp, '            put_back = await asyncio.to_thread(sync_workspace, self.build, self.store, self.library, project_id, actor="system")', "            put_back = {}"),
    ("the put-back is skipped on an early end", Lp, "        finally:\n            # Whatever happened", "        except ZeroDivisionError:\n            pass\n        else:\n            # Whatever happened"),
    ("the calls are not counted", Lp, "            calls += 1\n            costs.append(result.cost_usd)", "            costs.append(result.cost_usd)"),
    ("the meter is not told", Lp, "                meter.add_call(result.cost_usd, result.tokens_in, result.tokens_out)\n", ""),
    ("a stop mid-repair is never raised", Lp, "                return meter.should_stop() if problems else None\n            return None", "                return None\n            return None"),
    ("an unknown cost reads as zero", Lp, "        cost = None if (not costs or any(c is None for c in costs)) else sum(costs)", "        cost = sum(c or 0 for c in costs)"),
    # ---- the record
    ("a round is not recorded", Lp, "        self.store.build_rounds.append(", "        return\n        self.store.build_rounds.append("),
    ("the audit row is not written", Lp, "        self.store.audit.append(\n            actor=actor, action=\"build.round\"", "        return\n        self.store.audit.append(\n            actor=actor, action=\"build.round\""),
    ("the audit row holds the failures", Lp, 'detail={"round": number, "artefact": artefact, "outcome": outcome, "passed": report.passed, "failed": report.failed, "errors": report.errors},', 'detail={"round": number, "artefact": artefact, "outcome": outcome, "passed": report.passed, "failed": report.failed, "errors": report.errors, "failures": record_failures(report)},'),
    ("the record has no failures", Lp, "failures=record_failures(report), seconds=report.seconds,", "failures=(), seconds=report.seconds,"),
    ("the record has no run id", Lp, "version=version, run_id=run_id,", "version=version, run_id=None,"),
    ("the record has no version", Lp, "outcome=outcome, version=version,", "outcome=outcome, version=None,"),
    ("the event is not sent", Lp, '                emit("build.round", {"round": number, "artefact": artefact, "failed": last.failed, "errors": last.errors})', "                pass"),
    # ---- the setting
    ("the default is two rounds", Cf, "    build_fix_rounds: int = Field(default=3, ge=1, le=10)", "    build_fix_rounds: int = Field(default=2, ge=1, le=10)"),
    ("zero rounds are allowed", Cf, "    build_fix_rounds: int = Field(default=3, ge=1, le=10)", "    build_fix_rounds: int = Field(default=3, ge=0, le=10)"),
    ("eleven rounds are allowed", Cf, "    build_fix_rounds: int = Field(default=3, ge=1, le=10)", "    build_fix_rounds: int = Field(default=3, ge=1, le=11)"),
]
