"""Deliberate breaks for the output-limit and failure-reason change (2026-11-03): the code roles' limits, the cut-off flag, its plain wording, the stored reasons.

Run:
  cd backend && python -u -m scripts.mutation_check scripts/mutants/s18x_failures.py --tests tests/test_output_limits.py tests/test_run_phase.py
Every one of these should make the tests FAIL. One that does not is a hole in the tests.
"""
Cf = "app/config.py"
Rt = "app/agents/runtime.py"
Er = "app/agents/errors.py"
Ev = "app/run/events.py"
Rn = "app/run/runner.py"

MUTANTS = [
    ("the frontend keeps the general limit", Cf, "frontend_developer=24000,", ""),
    ("the test engineer keeps the general limit", Cf, "test_engineer=24000,", ""),
    ("the backend developer keeps the general limit", Cf, ",backend_developer=16000", ""),
    ("the frontend limit is lower", Cf, "frontend_developer=24000", "frontend_developer=12000"),
    ("the test limit is lower", Cf, "test_engineer=24000", "test_engineer=12000"),
    ("the backend limit is 24000", Cf, "backend_developer=16000", "backend_developer=24000"),
    ("the ux limit is gone", Cf, 'agent_output_tokens_by_role: str = "ux_designer=24000,', 'agent_output_tokens_by_role: str = "'),
    ("the database engineer gets a big limit", Cf, "backend_developer=16000\"", "backend_developer=16000,database_engineer=24000\""),
    # ---- the cut-off flag
    ("a cut-off is never recorded", Rt, "cut_off=calls[-1].finish_reason in TRUNCATED_REASONS,", "cut_off=False,"),
    ("everything is called a cut-off", Rt, "cut_off=calls[-1].finish_reason in TRUNCATED_REASONS,", "cut_off=True,"),
    ("the first reply decides, not the last", Rt, "cut_off=calls[-1].finish_reason in TRUNCATED_REASONS,", "cut_off=calls[0].finish_reason in TRUNCATED_REASONS,"),
    ("the limit is not recorded", Rt, "limit=self.settings.output_tokens_for(skill.artefact.role),", "limit=None,"),
    ("the wrong limit is recorded", Rt, "limit=self.settings.output_tokens_for(skill.artefact.role),", "limit=self.settings.agent_max_output_tokens,"),
    ("the error forgets the flag", Er, "        self.cut_off = cut_off          # the last reply ended because it hit the output limit, not because it was wrong", "        self.cut_off = False"),
    ("the error forgets the limit", Er, "        self.limit = limit              # that limit, in tokens", "        self.limit = None"),
    # ---- the wording
    ("a cut-off reads like any failed check", Ev, "    if isinstance(exc, OutputInvalid) and exc.cut_off:", "    if False:"),
    ("every failure reads as a cut-off", Ev, "    if isinstance(exc, OutputInvalid) and exc.cut_off:", "    if isinstance(exc, OutputInvalid):"),
    ("the wording leaves out the limit", Ev, 'f"the reply was cut off at its {exc.limit}-token output limit on every one of {exc.attempts} attempt(s); "', 'f"the reply was cut off on every one of {exc.attempts} attempt(s); "'),
    ("the wording leaves out the attempts", Ev, "on every one of {exc.attempts} attempt(s); ", "on every attempt; "),
    ("the wording leaves out the setting", Ev, '"raise AGENT_OUTPUT_TOKENS_BY_ROLE for this role, or ask for a smaller artefact")', '"try again")'),
    # ---- the stored reasons
    ("the problems are not kept", Rn, '            outcome.why = [clean_reason(p, secrets) for p in list(getattr(exc, "problems", ()))[:MAX_STORED_PROBLEMS]]', "            outcome.why = []"),
    ("the problems are not cleaned", Rn, "outcome.why = [clean_reason(p, secrets) for p in", "outcome.why = [str(p) for p in"),
    ("every problem is kept", Rn, 'list(getattr(exc, "problems", ()))[:MAX_STORED_PROBLEMS]]', 'list(getattr(exc, "problems", ()))]'),
    ("six problems are kept", Rn, "MAX_STORED_PROBLEMS = 5 ", "MAX_STORED_PROBLEMS = 6 "),
    ("the cut-off flag is not kept", Rn, '            outcome.cut_off = bool(getattr(exc, "cut_off", False))', "            outcome.cut_off = False"),
    ("the failures are not stored", Rn, "        if failures:\n            totals[\"failures\"] = failures", "        if False:\n            totals[\"failures\"] = failures"),
    ("failures are stored even when there are none", Rn, "        if failures:\n            totals[\"failures\"] = failures", "        totals[\"failures\"] = failures"),
    ("a skipped artefact is stored as failed", Rn, 'for k, o in outcomes.items() if o.state == FAILED}', 'for k, o in outcomes.items() if o.state != DONE}'),
    ("the stored reason is dropped", Rn, '{k: {"reason": o.reason, "problems": o.why, "cut_off": o.cut_off}', '{k: {"reason": "", "problems": o.why, "cut_off": o.cut_off}'),
    ("the failure details go into the event", Rn, 'for k, v in totals.items() if k != "failures"}', 'for k, v in totals.items()}'),
]
