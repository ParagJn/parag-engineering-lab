"""Deliberate breaks for S17c-1 (writing Build artefacts at the same moment: per-write staging, the old-folder sweep, the atomic folder swap, the folder tools).

Run:
  cd backend && python -u -m scripts.mutation_check scripts/mutants/s17c1_staging.py --tests tests/test_build_run.py tests/test_sandbox_files.py tests/test_build_inner.py
Every one of these should make the tests FAIL. One that does not is a hole in the tests.
"""
Sv = "app/build/service.py"
W = "app/sandbox/workspace.py"
In = "app/build/inner.py"

MUTANTS = [
    # ---- per-write staging
    ("every write shares one staging folder", Sv, '        stage = f"{STAGE}/{skill.key}-{secrets.token_hex(5)}"', '        stage = f"{STAGE}/shared"'),
    ("two artefacts share a staging name", Sv, '        stage = f"{STAGE}/{skill.key}-{secrets.token_hex(5)}"', '        stage = f"{STAGE}/{kind.folder[:0]}x{secrets.token_hex(0)}"'),
    ("the staging folder is not removed afterwards", Sv, "            _quietly(ws.remove_folder, stage)      # only OUR folder: the shared `.stage` parent stays, because removing it races with another writer making a folder in it\n", "            pass\n"),
    ("the shared staging parent is removed when empty", Sv, "            _quietly(ws.remove_folder, stage)      # only OUR folder: the shared `.stage` parent stays, because removing it races with another writer making a folder in it\n", "            _quietly(ws.remove_folder, stage)\n            _quietly(ws.remove_folder, STAGE)\n"),
    ("the staging path shows in a refusal", Sv, 'reason = str(exc).replace(f"{stage}/", "")', "reason = str(exc)"),
    ("the staged folder is the wrong one", Sv, '        staged = f"{stage}/{kind.folder}"', '        staged = f"{stage}"'),
    # ---- the sweep
    ("the sweep never runs", Sv, "        self._sweep_stale_staging(ws)\n", ""),
    ("the sweep removes young folders", Sv, "                if entry.is_dir() and entry.stat().st_mtime < cutoff:", "                if entry.is_dir(follow_symlinks=False):"),
    ("the sweep removes nothing", Sv, "                if entry.is_dir() and entry.stat().st_mtime < cutoff:", "                if False:"),
    ("the age limit is a minute", Sv, "STALE_STAGE_SECONDS = 3600 ", "STALE_STAGE_SECONDS = 60 "),
    ("the age limit is a day", Sv, "STALE_STAGE_SECONDS = 3600 ", "STALE_STAGE_SECONDS = 86400 "),
    ("the cutoff counts the wrong way", Sv, "        cutoff = self._clock() - STALE_STAGE_SECONDS", "        cutoff = self._clock() + STALE_STAGE_SECONDS"),
    ("a missing staging parent stops the write", Sv, "        except (SandboxError, OSError):\n            return\n        cutoff", "        except (SandboxError,):\n            raise\n        cutoff"),
    # ---- the atomic swap
    ("the old folder is deleted in place", W, "            os.rename(dst, aside)\n", "            shutil.rmtree(dst)\n"),
    ("old moved-aside copies are not swept", W, "        for leftover in dst.parent.glob(f\".old-{dst.name}-*\"):\n            shutil.rmtree(leftover, ignore_errors=True)\n", ""),
    ("a missing destination is an error", W, "        except FileNotFoundError:\n            pass                                                           # nothing there yet", "        except FileNotFoundError:\n            raise                                                          # nothing there yet"),
    ("the swap gives up when the destination fills", W, "                if exc.errno not in (errno.ENOTEMPTY, errno.EEXIST) or not dst.is_dir():\n                    raise", "                raise"),
    ("the swap never retries", W, "                os.rename(dst, dst.with_name(f\".old-{dst.name}-{secrets.token_hex(4)}\"))    # another replacement got there first: it becomes the old one", "                raise"),
    ("a file destination is replaced", W, "        if dst.is_file():                                                  # ONE look at the disk: \"exists, then is not a folder\" is two, and a folder moved aside between them reads as a file\n            raise PathRefused(f\"{self.shown(dst)} is a file\")", "        if False:\n            pass"),
    ("the moved-aside name is the same for everyone", W, "        aside = dst.with_name(f\".old-{dst.name}-{secrets.token_hex(4)}\")", "        aside = dst.with_name(f\".old-{dst.name}-x\")"),
    ("the parent folders are not made", W, "        self._make_parents(dst)\n        if dst.is_file():", "        if dst.is_file():"),
    ("a parent folder that exists is an error", W, "            current.mkdir(exist_ok=True)", "            current.mkdir()"),
    # ---- the folder tools
    # ---- what a check disturbs
    ("the tests' sync touches every component", In, "sync_workspace(build, store, library, project_id, actor=actor, keys=TESTED_AGAINST)", "sync_workspace(build, store, library, project_id, actor=actor)"),
    ("the tests are synced to the database", In, 'TESTED_AGAINST = ("backend_code",)', 'TESTED_AGAINST = ("database_schema", "backend_code")'),
    ("the tests are synced to the frontend", In, 'TESTED_AGAINST = ("backend_code",)', 'TESTED_AGAINST = ("backend_code", "frontend_code")'),
    ("the tests' sync touches nothing", In, "sync_workspace(build, store, library, project_id, actor=actor, keys=TESTED_AGAINST)", "sync_workspace(build, store, library, project_id, actor=actor, keys=())"),
    ("the key filter is ignored", In, "        if skill is None or (keys is not None and key not in keys):", "        if skill is None:"),
    ("an empty key list means everything", In, "        if skill is None or (keys is not None and key not in keys):", "        if skill is None or (keys and key not in keys):"),
    ("a folder moved aside between two looks reads as a file", W, "        if dst.is_file():                                                  # ONE look at the disk:", "        if dst.exists() and not dst.is_dir():                              # ONE look at the disk:"),
]
