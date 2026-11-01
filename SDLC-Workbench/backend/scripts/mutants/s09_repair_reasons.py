"""Deliberate breaks for the S09 follow-up: the reasons for a repair are kept on the saved version and on a stored review.

Run:  cd backend && python -u -m scripts.mutation_check scripts/mutants/s09_repair_reasons.py
"""
RUNTIME = "app/agents/runtime.py"
SERVICE = "app/review/service.py"
RUNNER = "app/run/runner.py"

MUTANTS = [
    ("the writer never logs a failed attempt", RUNTIME, "            if problems:\n                repair_log.append(logged_problems(attempt, result.call_id, problems))\n", ""),
    ("the writer logs the wrong attempt number", RUNTIME, "repair_log.append(logged_problems(attempt, result.call_id, problems))", "repair_log.append(logged_problems(attempt + 1, result.call_id, problems))"),
    ("the writer logs the wrong call", RUNTIME, "repair_log.append(logged_problems(attempt, result.call_id, problems))", "repair_log.append(logged_problems(attempt, calls[0].call_id, problems))"),
    ("the writer logs a successful attempt too", RUNTIME, "            if problems:\n                repair_log.append(logged_problems(", "            if True:\n                repair_log.append(logged_problems("),
    ("the writer does not pass the log to the save", RUNTIME, "item_ctx, repair_log)", "item_ctx, [])"),
    ("the saved record forgets the reasons", RUNTIME, '            "repair_reasons": list(repair_log),\n', ""),
    ("a logged problem is unbounded", RUNTIME, "[p[:MAX_LOGGED_PROBLEM_CHARS] for p in problems]", "list(problems)"),
    ("a logged problem is cut to nothing", RUNTIME, "[p[:MAX_LOGGED_PROBLEM_CHARS] for p in problems]", "[p[:0] for p in problems]"),
    ("the reviewer never logs a failed attempt", SERVICE, "            if problems:\n                repair_log.append(logged_problems(attempt, outcome.result.call_id, problems))\n", ""),
    # (An earlier version of this mutant used calls[-1], which at that moment IS the current call: it could never differ, so it was
    # removed rather than "caught". This one uses the first call, which differs on any second failed attempt.)
    ("the reviewer logs the wrong call", SERVICE, "repair_log.append(logged_problems(attempt, outcome.result.call_id, problems))", "repair_log.append(logged_problems(attempt, calls[0].call_id, problems))"),
    ("the stored review forgets the reasons", SERVICE, '            "repair_reasons": list(repair_log),\n', ""),
    ("the reviewer does not pass the log to the store", SERVICE, "author_model, repair_log\n        )", "author_model, []\n        )"),
    ("the full problem list is published in an event", RUNNER, '"will_repair": bool(problems), "problems": len(problems),', '"will_repair": bool(problems), "problems": problems,'),
]
