"""Deliberate breaks for S17b-2 (the build_rounds table and its repository).

Run:
  cd backend && python -u -m scripts.mutation_check scripts/mutants/s17b2_rounds.py --tests tests/test_build_rounds.py tests/test_db.py
Every one of these should make the tests FAIL. One that does not is a hole in the tests.
"""
Db = "app/db.py"
Rp = "app/repos.py"

MUTANTS = [
    # ---- the schema
    ("a round can be updated", Db, "CREATE TRIGGER build_rounds_no_update BEFORE UPDATE ON build_rounds BEGIN SELECT RAISE(ABORT, 'build rounds are append-only'); END;", ""),
    ("a round can be deleted", Db, "CREATE TRIGGER build_rounds_no_delete BEFORE DELETE ON build_rounds BEGIN SELECT RAISE(ABORT, 'build rounds are append-only'); END;", ""),
    ("a negative pass count is allowed by the database", Db, "  passed      INTEGER NOT NULL DEFAULT 0 CHECK (passed >= 0),", "  passed      INTEGER NOT NULL DEFAULT 0,"),
    ("a negative failed count is allowed by the database", Db, "  failed      INTEGER NOT NULL DEFAULT 0 CHECK (failed >= 0),", "  failed      INTEGER NOT NULL DEFAULT 0,"),
    ("a negative error count is allowed by the database", Db, "  errors      INTEGER NOT NULL DEFAULT 0 CHECK (errors >= 0),", "  errors      INTEGER NOT NULL DEFAULT 0,"),
    ("a negative skipped count is allowed by the database", Db, "  skipped     INTEGER NOT NULL DEFAULT 0 CHECK (skipped >= 0),", "  skipped     INTEGER NOT NULL DEFAULT 0,"),
    ("round zero is allowed by the database", Db, "  round       INTEGER NOT NULL CHECK (round >= 1),", "  round       INTEGER NOT NULL,"),
    ("the migration is not listed", Db, "SCHEMA_V6, SCHEMA_V7]", "SCHEMA_V6]"),
    # ---- the repository
    ("the repository is not in the store", Rp, "        self.build_rounds = BuildRoundRepo(db, clock, id_factory)\n", ""),
    ("an unknown project is accepted on write", Rp, "        with self.db.write() as conn:\n            _require_project(conn, project_id)\n            cursor = conn.execute(\n                \"INSERT INTO build_rounds", "        with self.db.write() as conn:\n            cursor = conn.execute(\n                \"INSERT INTO build_rounds"),
    ("an unknown project is accepted on read", Rp, "        with self.db.read() as conn:\n            _require_project(conn, project_id)\n            rows = conn.execute(sql + \" ORDER BY id LIMIT ?\", [*args, limit]).fetchall()\n        return [_build_round(r) for r in rows]", "        with self.db.read() as conn:\n            rows = conn.execute(sql + \" ORDER BY id LIMIT ?\", [*args, limit]).fetchall()\n        return [_build_round(r) for r in rows]"),
    ("a round of zero is accepted", Rp, "        if isinstance(round_, bool) or not isinstance(round_, int) or round_ < 1:", "        if isinstance(round_, bool) or not isinstance(round_, int):"),
    ("a true round is accepted", Rp, "        if isinstance(round_, bool) or not isinstance(round_, int) or round_ < 1:", "        if not isinstance(round_, int) or round_ < 1:"),
    ("an unknown outcome is accepted", Rp, "        if outcome not in ROUND_OUTCOMES:", "        if False:"),
    ("a negative count is accepted by the repository", Rp, "        counts = [_count(n, name) for n, name in ((passed, \"passed\"), (failed, \"failed\"), (errors, \"errors\"), (skipped, \"skipped\"))]", "        counts = [passed, failed, errors, skipped]"),
    ("a negative version is accepted", Rp, "            version = _count(version, \"version\")", "            pass"),
    ("negative seconds are accepted", Rp, "        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds < 0:", "        if False:"),
    ("text seconds are accepted", Rp, "        if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds < 0:", "        if seconds < 0:"),
    ("an empty loop id is accepted", Rp, "        loop_id = _text(loop_id, \"loop_id\")\n        if isinstance(round_", "        if isinstance(round_"),
    ("every failure is kept", Rp, "            for f in list(failures)[:MAX_ROUND_FAILURES]", "            for f in list(failures)"),
    ("the failure limit is eleven", Rp, "MAX_ROUND_FAILURES = 10", "MAX_ROUND_FAILURES = 11"),
    ("a message is not cut", Rp, "\"message\": str(f.get(\"message\", \"\"))[:MAX_FAILURE_TEXT]}", "\"message\": str(f.get(\"message\", \"\"))}"),
    ("a test name is not cut", Rp, "{\"test\": str(f.get(\"test\", \"\"))[:MAX_FAILURE_TEXT],", "{\"test\": str(f.get(\"test\", \"\")),"),
    ("the message limit is 500", Rp, "MAX_FAILURE_TEXT = 400", "MAX_FAILURE_TEXT = 500"),
    ("a failure keeps everything it was given", Rp, "            {\"test\": str(f.get(\"test\", \"\"))[:MAX_FAILURE_TEXT], \"kind\": str(f.get(\"kind\", \"\"))[:40], \"message\": str(f.get(\"message\", \"\"))[:MAX_FAILURE_TEXT]}", "            dict(f)"),
    ("the fingerprint is not cut", Rp, "str(fingerprint)[:200]", "str(fingerprint)"),
    ("rounds come back newest first", Rp, "            rows = conn.execute(sql + \" ORDER BY id LIMIT ?\", [*args, limit]).fetchall()\n        return [_build_round(r) for r in rows]\n\n\n# ---- the store", "            rows = conn.execute(sql + \" ORDER BY id DESC LIMIT ?\", [*args, limit]).fetchall()\n        return [_build_round(r) for r in rows]\n\n\n# ---- the store"),
    ("the loop filter is ignored", Rp, "        if loop_id is not None:\n            sql += \" AND loop_id = ?\"\n            args.append(loop_id)\n        with self.db.read() as conn:\n            _require_project(conn, project_id)\n            rows = conn.execute(sql + \" ORDER BY id LIMIT ?\"", "        with self.db.read() as conn:\n            _require_project(conn, project_id)\n            rows = conn.execute(sql + \" ORDER BY id LIMIT ?\""),
    ("the project filter is ignored", Rp, "        sql, args = \"SELECT * FROM build_rounds WHERE project_id = ?\", [project_id]", "        sql, args = \"SELECT * FROM build_rounds WHERE project_id = ? OR 1 = 1\", [project_id]"),
    ("the limit is ignored", Rp, "            rows = conn.execute(sql + \" ORDER BY id LIMIT ?\", [*args, limit]).fetchall()\n        return [_build_round(r) for r in rows]\n\n\n# ---- the store", "            rows = conn.execute(sql + \" ORDER BY id LIMIT 100000\", args).fetchall()\n        return [_build_round(r) for r in rows]\n\n\n# ---- the store"),
    ("the version is stored as zero", Rp, "(project_id, run_id, loop_id, round_, artefact, version, outcome, *counts,", "(project_id, run_id, loop_id, round_, artefact, version or 0, outcome, *counts,"),
    ("the run id is dropped", Rp, "(project_id, run_id, loop_id, round_, artefact, version, outcome, *counts,", "(project_id, None, loop_id, round_, artefact, version, outcome, *counts,"),
]
