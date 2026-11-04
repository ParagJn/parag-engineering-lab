"""Deliberate breaks for S19b-2 (the runner hands the instruction set to the composer; the piece events).

Backend:
  cd backend && python -u -m scripts.mutation_check scripts/mutants/s19b2_compose_events.py --tests tests/test_compose.py tests/test_build_phase.py tests/test_run_events.py tests/test_contract_fixtures.py
Every one of these should make the tests FAIL. One that does not is a hole in the tests.

The FRONTEND breaks for this slice (the decoder, the reducer, the run panel) are in `FRONTEND` below. The harness above runs pytest only, so they are checked by
`scripts/frontend_mutation_check.py` (a scratch copy of the frontend, vitest, restore nothing because nothing real is touched).
"""
Rn = "app/run/runner.py"
Hk = "app/build/phase.py"
Ev = "app/run/events.py"
Rt = "app/agents/runtime.py"
Mn = "app/main.py"
Cp = "app/build/compose.py"

MUTANTS = [
    ("the runner never uses the composer", Rn, "            if self.build is not None and self.build.composes(phase_key, key):", "            if False:"),
    ("the runner always uses the composer", Rn, "            if self.build is not None and self.build.composes(phase_key, key):", "            if self.build is not None:"),
    ("the piece events carry no key", Rn, "lambda kind, data: self.bus.publish(project_id, run_id, kind, {\"key\": key, **data}),", "lambda kind, data: self.bus.publish(project_id, run_id, kind, data),"),
    ("the key is wrong", Rn, "{\"key\": key, **data}", "{\"key\": 'x', **data}"),
    ("the composer is not given the meter", Rn, "project_id, run_id, meter, lambda kind, data: self.bus.publish", "project_id, run_id, None, lambda kind, data: self.bus.publish"),
    ("the composer is not given the run id", Rn, "project_id, run_id, meter, lambda kind, data: self.bus.publish", "project_id, None, meter, lambda kind, data: self.bus.publish"),
    ("the fix loop runs for any catalogue", Hk, "        return phase_key == PHASE and all(self.library.get(k) is not None for k in NEEDED_FOR_LOOP)", "        return phase_key == PHASE"),
    ("the fix loop never runs", Hk, "        return phase_key == PHASE and all(self.library.get(k) is not None for k in NEEDED_FOR_LOOP)", "        return False"),
    ("the fix loop needs only one code artefact", Hk, "all(self.library.get(k) is not None for k in NEEDED_FOR_LOOP)", "any(self.library.get(k) is not None for k in NEEDED_FOR_LOOP)"),
    ("the hook writes the report for any catalogue", Hk, "        return HOOK_WRITES if self.wants(phase_key) else ()", "        return HOOK_WRITES if phase_key == PHASE else ()"),
    ("the hook never writes the report", Hk, "        return HOOK_WRITES if self.wants(phase_key) else ()", "        return ()"),
    ("any artefact is composed", Hk, "phase_key == PHASE and artefact_key == INSTRUCTIONS_KEY", "phase_key == PHASE"),
    ("any phase composes", Hk, "phase_key == PHASE and artefact_key == INSTRUCTIONS_KEY", "artefact_key == INSTRUCTIONS_KEY"),
    ("no composer is still composed", Hk, "        return self.composer is not None and phase_key == PHASE", "        return phase_key == PHASE"),
    ("the compose result is not the save", Hk, "        return composed.result", "        return composed"),
    ("the composer is not passed the meter", Hk, "await self.composer.compose(project_id, run_id=run_id, meter=meter, emit=emit)", "await self.composer.compose(project_id, run_id=run_id, meter=None, emit=emit)"),
    ("the composer is not wired in main", Mn, "                                 composer=SetComposer(app.state.agents, cfg, skills))", "                                 composer=None)"),
    ("the one-reply path writes the set", Rt, "        if artefact_key == INSTRUCTIONS_KEY:", "        if False:"),
    ("every artefact is refused the one-reply path", Rt, "        if artefact_key == INSTRUCTIONS_KEY:", "        if True:"),
    ("a piece event is missing from the vocabulary", Ev, '    "piece.started",\n', ""),
    ("the piece events are in the wrong place", Ev, '    "build.round",\n    "piece.started",\n    "piece.finished",\n    "piece.failed",\n', '    "piece.started",\n    "piece.finished",\n    "piece.failed",\n    "build.round",\n'),
    ("the started event loses its index", Cp, 'return {"file": file, "stage": stage, "index": index, "of": of}', 'return {"file": file, "stage": stage, "of": of}'),
    ("the started event loses its stage", Cp, 'return {"file": file, "stage": stage, "index": index, "of": of}', 'return {"file": file, "index": index, "of": of}'),
    ("the finished event loses its cost", Cp, '"tokens_out": tokens_out, "cost_usd": cost_usd}', '"tokens_out": tokens_out}'),
    ("the finished event loses its tokens", Cp, '"attempts": attempts, "tokens_in": tokens_in, "tokens_out": tokens_out, "cost_usd": cost_usd}', '"attempts": attempts, "cost_usd": cost_usd}'),
    ("the failed event loses its reason", Cp, 'return {"file": file, "reason": reason}', 'return {"file": file}'),
]

# (name, file under frontend/, old text, new text). Run with scripts/frontend_mutation_check.py.
FRONTEND = [
    ("the decoder accepts any stage", "src/api/events.ts", "stage: oneOf(o.stage, `${w}.stage`, PIECE_STAGES)", "stage: str(o.stage, `${w}.stage`) as never"),
    ("the decoder drops the index", "src/api/events.ts", "index: num(o.index, `${w}.index`), of: num(o.of, `${w}.of`) }", "index: 1, of: num(o.of, `${w}.of`) }"),
    ("the decoder drops the total", "src/api/events.ts", "index: num(o.index, `${w}.index`), of: num(o.of, `${w}.of`) }", "index: num(o.index, `${w}.index`), of: 1 }"),
    ("the decoder requires a cost", "src/api/events.ts", "cost_usd: nullable(o.cost_usd, `${w}.cost_usd`, num) }\n    case 'piece.failed'", "cost_usd: num(o.cost_usd, `${w}.cost_usd`) }\n    case 'piece.failed'"),
    ("the decoder drops the key", "src/api/events.ts", "return { ...base, type: 'piece.failed', key: str(o.key, `${w}.key`),", "return { ...base, type: 'piece.failed', key: 'build_instructions',"),
    ("the decoder drops the reason", "src/api/events.ts", "reason: str(o.reason, `${w}.reason`) }\n    case 'review.started'", "reason: '' }\n    case 'review.started'"),
    ("the stream does not listen for a piece event", "src/api/stream.ts", "'piece.started', 'piece.finished', 'piece.failed',", "'piece.started', 'piece.finished',"),
    ("a started file is not listed", "src/state/runProgress.ts", "state: 'writing', index: e.index, of: e.of, attempts: 0, costUsd: null, reason: null }) }))", "state: 'writing', index: e.index, of: e.of, attempts: 0, costUsd: null, reason: null }).slice(0, 0) }))"),
    ("a finished file stays writing", "src/state/runProgress.ts", "{ file: e.file, state: 'done', attempts: e.attempts,", "{ file: e.file, state: 'writing', attempts: e.attempts,"),
    ("a failed file is shown done", "src/state/runProgress.ts", "{ file: e.file, state: 'failed', reason: e.reason }", "{ file: e.file, state: 'done', reason: e.reason }"),
    ("a failed file loses its reason", "src/state/runProgress.ts", "{ file: e.file, state: 'failed', reason: e.reason }", "{ file: e.file, state: 'failed' }"),
    ("a file's cost is lost", "src/state/runProgress.ts", "attempts: e.attempts, costUsd: e.cost_usd, reason: null }", "attempts: e.attempts, costUsd: null, reason: null }"),
    ("a file's attempts are lost", "src/state/runProgress.ts", "attempts: e.attempts, costUsd: e.cost_usd, reason: null }", "attempts: 1, costUsd: e.cost_usd, reason: null }"),
    ("a restarted file is listed twice", "src/state/runProgress.ts", "  const at = pieces.findIndex((x) => x.file === change.file)\n  if (at < 0)", "  const at = -1\n  if (at < 0)"),
    ("a changed file replaces the others", "src/state/runProgress.ts", "  return pieces.map((x, n) => (n === at ? { ...x, ...change } : x))", "  return pieces.map((x) => ({ ...x, ...change }))"),
    ("an artefact that starts again keeps its files", "src/state/runProgress.ts", "attempts: Math.max(r.attempts, 1), pieces: [] }))", "attempts: Math.max(r.attempts, 1) }))"),
    ("a new row has files", "src/state/runProgress.ts", "reviewNote: null, pieces: [] })", "reviewNote: null, pieces: [{ file: 'x', state: 'writing', index: 1, of: 1, attempts: 0, costUsd: null, reason: null }] })"),
    ("a file event changes the artefact's state", "src/state/runProgress.ts", "    case 'piece.finished':\n      return withRow(next, e.key, (r) => ({ ...r, pieces:", "    case 'piece.finished':\n      return withRow(next, e.key, (r) => ({ ...r, state: 'done', pieces:"),
    ("the panel never shows the files", "src/components/RunPanel.tsx", "{r.pieces.length > 0 && <Pieces", "{false && <Pieces"),
    ("the files stay open when done", "src/components/RunPanel.tsx", "open={r.state !== 'done'}", "open"),
    ("the files stay folded while working", "src/components/RunPanel.tsx", "open={r.state !== 'done'}", "open={false}"),
    ("the file count counts all files", "src/components/RunPanel.tsx", "const done = pieces.filter((x) => x.state === 'done').length", "const done = pieces.length"),
    ("the file total is wrong", "src/components/RunPanel.tsx", "{done} of {pieces[0].of} files written", "{done} of {pieces.length} files written"),
    ("the file reason is not shown", "src/components/RunPanel.tsx", "{x.reason && <span className=\"basis-full pl-5 text-slate-600\">{x.reason}</span>}", ""),
    ("the file cost is not shown", "src/components/RunPanel.tsx", "{x.state === 'done' ? ` · ${money(x.costUsd)}` : ''}", ""),
    ("the attempts are not shown", "src/components/RunPanel.tsx", "{x.attempts > 1 ? ` · ${x.attempts} attempts` : ''}", ""),
    ("every file is shown as written", "src/components/RunPanel.tsx", "const PIECE_LABEL = { writing: 'writing', done: 'written', failed: 'failed' } as const", "const PIECE_LABEL = { writing: 'written', done: 'written', failed: 'written' } as const"),
]
