"""Deliberate breaks for S09 (the scheduler, the caps, the events, the routes, schema v5).

Run:  cd backend && python -u -m scripts.mutation_check scripts/mutants/s09_run.py
Every one of these should make the test suite FAIL. One that does not is a hole in the tests.
"""
BUDGET = "app/run/budget.py"
RUNNER = "app/run/runner.py"
EVENTS = "app/run/events.py"
ROUTES = "app/routes.py"
REPOS = "app/repos.py"
RUNTIME = "app/agents/runtime.py"
DBF = "app/db.py"
MAIN = "app/main.py"

MUTANTS = [
    # --- the meter
    ("the cost cap is never reached", BUDGET, "elif self.max_cost_usd > 0 and self._cost >= self.max_cost_usd:", "elif self.max_cost_usd > 0 and self._cost > self.max_cost_usd:"),
    ("the cost cap is ignored", BUDGET, "elif self.max_cost_usd > 0 and self._cost >= self.max_cost_usd:", "elif False:"),
    ("zero no longer switches the cost cap off", BUDGET, "elif self.max_cost_usd > 0 and self._cost >= self.max_cost_usd:", "elif self._cost >= self.max_cost_usd:"),
    ("the time cap is ignored", BUDGET, "elif self.max_seconds > 0 and self.clock() - self.started >= self.max_seconds:", "elif False:"),
    ("zero no longer switches the time cap off", BUDGET, "elif self.max_seconds > 0 and self.clock() - self.started >= self.max_seconds:", "elif self.clock() - self.started >= self.max_seconds:"),
    ("a cancel is ignored", BUDGET, "            if self._cancelled:\n                reason = STOP_CANCELLED\n", "            if False:\n                reason = STOP_CANCELLED\n"),
    ("a stop can be undone", BUDGET, "            if self._stop is not None:\n                return self._stop\n", ""),
    ("cancel does not outrank a cap", BUDGET, "            if self._cancelled:\n                reason = STOP_CANCELLED\n            elif self.max_cost_usd > 0", "            if self.max_cost_usd > 0 and self._cost >= self.max_cost_usd:\n                reason = STOP_BUDGET\n            elif self._cancelled:\n                reason = STOP_CANCELLED\n            elif self.max_cost_usd > 0"),
    ("an unpriced call counts as free", BUDGET, "            if cost_usd is None:\n                self._unpriced += 1\n            else:\n                self._cost += cost_usd", "            self._cost += cost_usd or 0.0"),
    ("an unpriced call is not counted", BUDGET, "                self._unpriced += 1\n", "                pass\n"),
    ("tokens are not added up", BUDGET, "            self._tokens_in += tokens_in\n", ""),
    ("a partial cost is not flagged", BUDGET, '"cost_is_partial": self._unpriced > 0,', '"cost_is_partial": False,'),
    ("the overshoot is not reported", BUDGET, "                over = round(max(0.0, self._cost - self.max_cost_usd), 6)", "                over = 0.0"),
    ("the overshoot is reported when the budget did not stop the run", BUDGET, 'if self._stop == STOP_BUDGET and self.max_cost_usd > 0:', 'if self.max_cost_usd > 0:'),
    # --- pure scheduling
    ("an artefact starts before its dependencies finish", BUDGET, "return [k for k in order if k not in started and all(d in done for d in after.get(k, ()) if d in order)]", "return [k for k in order if k not in started]"),
    ("a started artefact is offered again", BUDGET, "return [k for k in order if k not in started and all(", "return [k for k in order if all("),
    ("a dependency outside the run blocks forever", BUDGET, "for d in after.get(k, ()) if d in order)]", "for d in after.get(k, ()))]"),
    ("a failure blocks nothing", BUDGET, "            if dep in order and dep in cause:\n                out[key] = cause[dep]", "            if False:\n                out[key] = cause[dep]"),
    ("a skip points at the skip, not the real fault", BUDGET, "                out[key] = cause[dep]\n                cause[key] = cause[dep]", "                out[key] = dep\n                cause[key] = key"),
    ("a failure blocks siblings", BUDGET, "        for dep in after.get(key, ()):\n            if dep in order and dep in cause:", "        for dep in order:\n            if dep in order and dep in cause:"),
    ("the default runs artefacts that already have a version", BUDGET, "return [k for k in plan_keys if not has_version.get(k, False)]", "return list(plan_keys)"),
    ("rewrite_all is ignored", BUDGET, "    if rewrite_all:\n        return list(plan_keys)\n", ""),
    ("only is ignored", BUDGET, "    if only is not None:\n        chosen = set(only)\n        return [k for k in plan_keys if k in chosen]\n", ""),
    # --- the runner
    ("the concurrency cap is ignored", RUNNER, "                    if len(running) >= cap:\n                        break\n", ""),
    ("the cap is one too generous", RUNNER, "                    if len(running) >= cap:", "                    if len(running) > cap:"),
    ("ready is computed over only the not-yet-started list", RUNNER, "for key in ready(wanted, after, done, started):", "for key in ready([k for k in wanted if k not in started], after, done, started):"),
    ("a failed artefact does not skip its dependants", RUNNER, "                elif outcome.state == FAILED:\n                    failed[key] = outcome.reason or \"failed\"\n                elif outcome.state == NOT_STARTED:\n                    pass", "                elif outcome.state == FAILED:\n                    pass\n                elif outcome.state == NOT_STARTED:\n                    pass"),
    ("skipped artefacts are not published", RUNNER, '                self.bus.publish(project_id, run_id, "artefact.skipped", {"key": key, "reason": reason})', "                pass"),
    ("a stop is not noticed before starting more", RUNNER, "            stop_reason = stop_reason or meter.should_stop()\n            if stop_reason is None:", "            if stop_reason is None:"),
    ("a valid reply is dropped when a cap is reached", RUNNER, "            return meter.should_stop() if problems else None", "            return meter.should_stop()"),
    ("a repair loop is never stopped by a cap", RUNNER, "            return meter.should_stop() if problems else None", "            return None"),
    ("a call's cost is not added to the meter", RUNNER, "            meter.add_call(result.cost_usd, result.tokens_in, result.tokens_out)\n            if attempt > 1", "            if attempt > 1"),
    ("a review's cost is not added to the meter", RUNNER, "        meter.add_call(result.cost_usd, result.tokens_in, result.tokens_out)\n        outcome.review", "        outcome.review"),
    ("the run row is never ended on success", RUNNER, '        self.store.runs.end(run_id, status if status != "failed" else "failed", stop_reason=stop_reason, totals=totals)', "        pass"),
    ("a stopped run is reported as finished", RUNNER, 'status = "stopped" if stop_reason else ("failed" if counts[FAILED] else "finished")', 'status = "failed" if counts[FAILED] else "finished"'),
    ("a failed artefact does not make the run failed", RUNNER, '("failed" if counts[FAILED] else "finished")', '"finished"'),
    ("the phase guard is never released", RUNNER, "            self._active.pop((project_id, phase_key), None)\n", ""),
    ("the meter is never released", RUNNER, "            self._meters.pop(run_id, None)\n", ""),
    ("a second run of the same phase is allowed", RUNNER, "        if key in self._active:\n            raise RunAlreadyActive(", "        if False:\n            raise RunAlreadyActive("),
    ("a refused request still takes the guard", RUNNER, "        self._validate(project_id, phase_key, options)\n        key = (project_id, phase_key)", "        key = (project_id, phase_key)\n        self._active[key] = 'x'\n        self._validate(project_id, phase_key, options)"),
    ("an unknown artefact key is accepted", RUNNER, "            if unknown:\n                raise UnknownArtefact(", "            if False:\n                raise UnknownArtefact("),
    ("an approved phase can be run again", RUNNER, '        if status == "approved":\n            raise RunError(', '        if False:\n            raise RunError('),
    ("a phase awaiting review can be run", RUNNER, '        if status == "awaiting_review":\n            raise RunError(', '        if False:\n            raise RunError('),
    ("an unmet prerequisite is not checked up front", RUNNER, '            check_can_start(plan, self.store.phases.list(project_id), phase_key)   # PrerequisiteNotMet, before any money is spent', "            pass"),
    ("only and rewrite_all together are accepted", RUNNER, '        if only is not None and options.get("rewrite_all"):', "        if False:"),
    ("the phase is handed to review at the end", RUNNER, "        self.store.runs.end(run_id, status", "        self.engine.finish(project_id, phase_key, actor='system')\n        self.store.runs.end(run_id, status"),
    ("a cancel request on a finished run is accepted", RUNNER, "        meter = self._meters.get(run_id)\n        if meter is None:\n            return False", "        meter = self._meters.get(run_id) or Meter(0, 0)"),
    ("an unexpected error leaves the run marked running", RUNNER, '                self.store.runs.end(run_id, "failed", totals={**meter.snapshot(), "error": reason})\n', ""),
    ("a review that fails fails the artefact", RUNNER, "        except Exception as exc:  # noqa: BLE001 - a review that fails must not fail the artefact it was reviewing", "        except ZeroDivisionError as exc:  # noqa: BLE001"),
    ("an unavailable reviewer stops the run", RUNNER, "        except ReviewerUnavailable as exc:\n            outcome.review = {\"paused\": True}", "        except ReviewerUnavailable as exc:\n            raise\n            outcome.review = {\"paused\": True}"),
    # --- events
    ("an unknown event type is accepted", EVENTS, "        if type_ not in EVENT_TYPES:\n            raise ValueError(", "        if False:\n            raise ValueError("),
    ("events are not delivered to watchers", EVENTS, "        self._deliver(event)\n        return event", "        return event"),
    ("a watcher of another project receives events", EVENTS, "if w.project_id == event.project_id and not w.state[\"dropped\"]]", "if not w.state[\"dropped\"]]"),
    ("a slow watcher blocks the run", EVENTS, "            watcher.queue.put_nowait(event)\n        except asyncio.QueueFull:", "            watcher.queue.put_nowait(event)\n        except ZeroDivisionError:"),
    ("a dropped watcher is told nothing", EVENTS, "            watcher.queue.put_nowait(None)", "            pass"),
    ("events can follow a drop marker", EVENTS, "        if watcher.state[\"dropped\"]:\n            return  # offers", "        if False:\n            return  # offers"),
    ("a dropped watcher is kept", EVENTS, "            watcher.state[\"dropped\"] = True\n            self._remove(watcher)", "            watcher.state[\"dropped\"] = True"),
    ("a reason keeps its newlines", EVENTS, 'out = " ".join(str(text).split())', "out = str(text)"),
    ("a reason keeps its URLs", EVENTS, '    out = _URL.sub("[url removed]", out)\n', ""),
    ("a reason keeps a configured secret", EVENTS, '            out = out.replace(secret, "[removed]")', "            pass"),
    ("a reason is unbounded", EVENTS, "    return out[:MAX_REASON_CHARS]", "    return out"),
    ("a failed reply is described by its text", EVENTS, "    if isinstance(exc, (OutputInvalid, ReviewOutputInvalid)):\n        return f\"the reply failed its checks after", "    if False:\n        return f\"the reply failed its checks after"),
    ("an unexpected error is described by its message", EVENTS, '    return f"unexpected error ({type(exc).__name__})"', '    return clean_reason(str(exc), secrets)'),
    ("an event can contain a bare newline", EVENTS, "data: {json.dumps({'run_id': event.run_id, 'at': event.at, **event.data}, sort_keys=True)}", "data: {event.run_id} {event.at} {event.data}"),
    # --- repositories
    ("an event for another project's run is stored", REPOS, "            if row is None or row[\"project_id\"] != project_id:\n                raise NotFoundError(f\"run {run_id!r} not found in project", "            if row is None:\n                raise NotFoundError(f\"run {run_id!r} not found in project"),
    ("after returns the event itself", REPOS, "sql, args = \"SELECT * FROM run_events WHERE project_id = ? AND id > ?\", [project_id, after]", "sql, args = \"SELECT * FROM run_events WHERE project_id = ? AND id >= ?\", [project_id, after]"),
    ("events come back newest first", REPOS, 'rows = conn.execute(sql + " ORDER BY id LIMIT ?", [*args, limit]).fetchall()', 'rows = conn.execute(sql + " ORDER BY id DESC LIMIT ?", [*args, limit]).fetchall()'),
    ("an oversize event is stored", REPOS, "    if len(payload.encode(\"utf-8\")) > MAX_EVENT_BYTES:", "    if False:"),
    ("a run can be ended twice", REPOS, "            if row[\"status\"] != \"running\":\n                raise ConflictError(", "            if False:\n                raise ConflictError("),
    ("a run can be ended as running", REPOS, "        if status not in RUN_STATUSES or status == \"running\":", "        if status not in RUN_STATUSES:"),
    ("unfinished runs are not interrupted at start-up", REPOS, "            for row in rows:\n                conn.execute(\n                    \"UPDATE runs SET status = 'interrupted'", "            for row in []:\n                conn.execute(\n                    \"UPDATE runs SET status = 'interrupted'"),
    ("an interrupted run says nothing in the log", REPOS, "                _insert_run_event(\n                    conn, now, row[\"project_id\"], row[\"id\"], \"run.stopped\",", "                (lambda *a, **k: None)(\n                    conn, now, row[\"project_id\"], row[\"id\"], \"run.stopped\","),
    ("a run is found through another project", REPOS, 'row = conn.execute("SELECT * FROM runs WHERE id = ? AND project_id = ?", (run_id, project_id)).fetchone()', 'row = conn.execute("SELECT * FROM runs WHERE id = ? AND ? IS NOT NULL", (run_id, project_id)).fetchone()'),
    # --- schema
    ("run events can be edited", DBF, "CREATE TRIGGER run_events_no_update BEFORE UPDATE ON run_events BEGIN SELECT RAISE(ABORT, 'run events are append-only'); END;\n", ""),
    ("run events can be deleted", DBF, "CREATE TRIGGER run_events_no_delete BEFORE DELETE ON run_events BEGIN SELECT RAISE(ABORT, 'run events are append-only'); END;\n", ""),
    # --- routes
    ("the run route waits for the run", ROUTES, "        run_id = _runner(request).start_phase(", "        run_id = (await _runner(request).run_phase(project_id, phase_key, only=body.only, rewrite_all=body.rewrite_all, review=body.review)).run_id\n        _ = (lambda *a, **k: 'x')("),
    ("unknown request fields are accepted", ROUTES, 'model_config = ConfigDict(extra="forbid")', 'model_config = ConfigDict(extra="ignore")'),
    ("a phase key is not validated", ROUTES, "    if not _valid(phase_key, KEY):", "    if False:"),
    ("an artefact key is not validated", ROUTES, "        if not _valid(key, KEY):\n            raise HTTPException(status_code=422, detail=f\"artefact key", "        if False:\n            raise HTTPException(status_code=422, detail=f\"artefact key"),
    ("a run id is not validated on read", ROUTES, "def get_run(project_id: str, run_id: str, request: Request) -> dict:\n    if not _valid(run_id, RUN_ID):", "def get_run(project_id: str, run_id: str, request: Request) -> dict:\n    if False:"),
    ("a conflict is a 422", ROUTES, "    if isinstance(exc, (RunAlreadyActive, ConflictError, PrerequisiteNotMet)):", "    if isinstance(exc, (RunAlreadyActive,)):"),
    ("cancelling a finished run succeeds", ROUTES, "    if not accepted:\n        raise HTTPException(status_code=409,", "    if False:\n        raise HTTPException(status_code=409,"),
    ("a stream for an unknown project opens", ROUTES, "    try:\n        store.projects.get(project_id)\n    except NotFoundError as exc:\n        raise _translate(exc) from exc\n    if after < 0:", "    if after < 0:"),
    ("a negative after is accepted", ROUTES, "    if after < 0:\n        raise HTTPException(", "    if False:\n        raise HTTPException("),
    ("Last-Event-ID is ignored", ROUTES, "        after = max(after, int(header))", "        pass"),
    ("a bad Last-Event-ID is accepted", ROUTES, "        if not header.isdigit():\n            raise HTTPException(", "        if False:\n            raise HTTPException("),
    ("the stream subscribes after reading the log", ROUTES,
     "        watcher = bus.watch(project_id)  # subscribe BEFORE reading the log, so nothing falls in the gap\n        try:\n            last = after\n            while True:  # catch up from the durable log, then go live\n                batch = await asyncio.to_thread(store.run_events.list, project_id, after=last, limit=500)\n                for event in batch:\n                    last = event.id\n                    yield format_sse(event)\n                if len(batch) < 500:\n                    break\n            yield format_comment(\"live\")\n",
     "        watcher = None\n        try:\n            last = after\n            while True:  # catch up from the durable log, then go live\n                batch = await asyncio.to_thread(store.run_events.list, project_id, after=last, limit=500)\n                for event in batch:\n                    last = event.id\n                    yield format_sse(event)\n                if len(batch) < 500:\n                    break\n            watcher = bus.watch(project_id)\n            yield format_comment(\"live\")\n"),
    ("the stream never subscribes", ROUTES, "        watcher = bus.watch(project_id)  # subscribe BEFORE reading the log, so nothing falls in the gap\n",
     "        watcher = type('W', (), {'queue': asyncio.Queue(), 'state': {'dropped': False}})()\n"),
    ("events already sent are sent again", ROUTES, "                if item.id <= last:\n                    continue  # already sent from the log\n", ""),
    ("the stream never sends a heartbeat", ROUTES, "                    yield format_comment(HEARTBEAT)\n                    continue", "                    continue"),
    ("the stream keeps its watcher after the client leaves", ROUTES, "        finally:\n            bus.unwatch(watcher)", "        finally:\n            pass"),
    # Left out on purpose: "the stream does not notice a disconnect". The server ends a stream when its client leaves (ASGI 2.3: it
    # cancels the generator; 2.4: the next write fails), so an explicit check in the route changes nothing observable and a
    # mutant there can never be caught. The check was removed instead; tests/test_run_api.py proves the stream still ends.
    ("the stream is cached", ROUTES, 'headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},', 'headers={"X-Accel-Buffering": "no", "Connection": "keep-alive"},'),
    # --- wiring
    ("start-up does not interrupt orphaned runs", MAIN, "    store.runs.interrupt_unfinished()  # runs left \"running\" by a process that no longer exists\n", ""),
    ("the run routes are not mounted", MAIN, "    app.include_router(router)\n", ""),
    ("the runtime cannot be stopped between calls", RUNTIME, "                stop = on_call(result, attempt, problems)\n                if stop is not None:\n                    raise RunStopped(", "                stop = on_call(result, attempt, problems)\n                if False:\n                    raise RunStopped("),
]
