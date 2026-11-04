"""S20a: the safe walk over a folder the person named. Every fixture project is written into a temporary folder; nothing outside it is read."""
from __future__ import annotations

import os

import pytest

from app.verify import walk as W

from . import _fakes as F


def put(root, rel, text="x = 1\n"):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def paths(walked):
    return [f.path for f in walked.files]


# ---- what is read ---------------------------------------------------------------------------------------------------------------------------------------

def test_source_files_are_read_with_paths_relative_to_the_folder_in_a_stable_order(tmp_path):
    put(tmp_path, "b.py"); put(tmp_path, "app/a.py"); put(tmp_path, "app/sub/c.sql", "-- sql"); put(tmp_path, "notes.docx", "binary")
    walked = W.walk(str(tmp_path))
    assert paths(walked) == ["app/a.py", "app/sub/c.sql", "b.py"] and walked.stopped is None
    assert walked.files[0].text == "x = 1\n"


def test_a_missing_folder_a_file_and_a_relative_path_each_get_a_plain_sentence(tmp_path):
    put(tmp_path, "a.py")
    for bad, words in (("", "give the folder as a path"), ("   ", "give the folder as a path"), ("relative/dir", "not an absolute path"), (str(tmp_path / "nope"), "there is no folder"),
                       (str(tmp_path / "a.py"), "is a file, not a folder"), ("/tmp/\x00x", "give the folder as a path")):
        with pytest.raises(W.FolderProblem, match=words):
            W.walk(bad)


def test_a_folder_that_is_itself_a_link_is_refused(tmp_path):
    real = tmp_path / "real"; real.mkdir(); put(real, "a.py")
    link = tmp_path / "link"
    os.symlink(real, link)
    with pytest.raises(W.FolderProblem, match="is a link"):
        W.walk(str(link))


# ---- what is never read -----------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", [".env", ".env.local", ".env.production", "prod.env", "server.pem", "tls.key", "cert.p12", "id_rsa", "id_ed25519", "id_custom", "secrets.json", ".netrc", "data.sqlite", "app.db"])
def test_files_that_may_hold_a_secret_are_never_read_and_the_walk_says_so(tmp_path, name):
    put(tmp_path, "ok.py"); put(tmp_path, name, F.AWS_KEY)
    walked = W.walk(str(tmp_path))
    assert paths(walked) == ["ok.py"] and all(F.AWS_KEY not in f.text for f in walked.files)
    assert any(name in s and "may hold a secret" in s for s in walked.skipped), walked.skipped


@pytest.mark.parametrize("folder", [".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build", ".next", "site-packages", ".idea"])
def test_folders_that_are_not_source_code_are_left_out(tmp_path, folder):
    put(tmp_path, "ok.py"); put(tmp_path, f"{folder}/inner.py"); put(tmp_path, f"deep/{folder}/inner.py")
    walked = W.walk(str(tmp_path))
    assert paths(walked) == ["ok.py"]
    assert any(f"{folder}/" in s for s in walked.skipped)


def test_a_link_to_a_file_or_a_folder_outside_the_folder_is_never_followed(tmp_path):
    outside = tmp_path / "outside"; outside.mkdir(); put(outside, "secret_code.py", "leak = 1\n")
    inside = tmp_path / "project"; inside.mkdir(); put(inside, "ok.py")
    os.symlink(outside, inside / "linked_dir")
    os.symlink(outside / "secret_code.py", inside / "linked_file.py")
    walked = W.walk(str(inside))
    assert paths(walked) == ["ok.py"] and all("leak" not in f.text for f in walked.files)
    assert any("linked_dir" in s and "never followed" in s for s in walked.skipped) and any("linked_file.py" in s for s in walked.skipped)


def test_a_file_over_the_size_limit_is_left_out_and_named(tmp_path):
    put(tmp_path, "ok.py"); put(tmp_path, "huge.py", "a = 1\n" * 100_000)
    walked = W.walk(str(tmp_path))
    assert paths(walked) == ["ok.py"] and any("huge.py" in s and "over 500000" in s for s in walked.skipped)


def test_a_file_that_is_not_valid_text_is_read_with_replacement_characters_and_does_not_stop_the_walk(tmp_path):
    put(tmp_path, "ok.py")
    (tmp_path / "odd.py").write_bytes(b"x = '\xff\xfe'\n")
    walked = W.walk(str(tmp_path))
    assert paths(walked) == ["odd.py", "ok.py"] and "x = '" in walked.files[0].text


def test_the_file_limit_stops_the_walk_and_says_how_many_were_read(tmp_path):
    for n in range(7):
        put(tmp_path, f"f{n}.py")
    walked = W.walk(str(tmp_path), max_files=5)
    assert len(walked.files) == 5 and walked.stopped == "stopped after 5 files; the rest of the folder was not read"


def test_a_folder_nested_deeper_than_the_limit_is_left_out(tmp_path):
    deep = "/".join(f"d{n}" for n in range(W.MAX_DEPTH + 2))
    put(tmp_path, "ok.py"); put(tmp_path, f"{deep}/too_deep.py")
    walked = W.walk(str(tmp_path))
    assert paths(walked) == ["ok.py"] and any("folders deep" in s for s in walked.skipped)


def test_the_list_of_what_was_left_out_is_bounded(tmp_path):
    for n in range(80):
        put(tmp_path, f"k{n}.pem", "x")
    assert len(W.walk(str(tmp_path)).skipped) == 50


def test_the_walk_writes_nothing_and_runs_nothing(tmp_path):
    put(tmp_path, "boom.py", "raise SystemExit('this must never run')\n"); put(tmp_path, "setup.py", "import os; os.remove('/nonexistent')\n")
    before = sorted(p.name for p in tmp_path.rglob("*"))
    walked = W.walk(str(tmp_path))
    assert sorted(p.name for p in tmp_path.rglob("*")) == before and len(walked.files) == 2


def test_hidden_folders_are_left_out_except_github(tmp_path):
    put(tmp_path, ".hidden/x.py"); put(tmp_path, ".github/workflows/ci.yml", "on: push\n"); put(tmp_path, "ok.py")
    assert paths(W.walk(str(tmp_path))) == [".github/workflows/ci.yml", "ok.py"]


# ---- the edges (S20a mutation survivors) ---------------------------------------------------------------------------------------------------------------

def test_a_file_named_with_an_env_suffix_or_prefix_is_never_read_but_a_name_that_only_contains_env_is(tmp_path):
    for name in (".env", "prod.env", ".env.local", "my.env"):
        put(tmp_path, name, "SECRET=1")
    put(tmp_path, "environment.py"); put(tmp_path, "env_config.py")
    walked = W.walk(str(tmp_path))
    assert paths(walked) == ["env_config.py", "environment.py"]


def test_the_depth_limit_reads_the_deepest_allowed_folder_and_leaves_out_the_next(tmp_path):
    ok = "/".join(f"d{n}" for n in range(W.MAX_DEPTH))
    too = "/".join(f"d{n}" for n in range(W.MAX_DEPTH + 1))
    put(tmp_path, f"{ok}/deepest_ok.py"); put(tmp_path, f"{too}/one_too_deep.py")
    assert paths(W.walk(str(tmp_path))) == [f"{ok}/deepest_ok.py"]


def test_a_file_of_exactly_the_character_limit_is_read_and_one_character_more_is_not(tmp_path):
    put(tmp_path, "exact.py", "a" * W.MAX_FILE_CHARS); put(tmp_path, "over.py", "a" * (W.MAX_FILE_CHARS + 1))
    walked = W.walk(str(tmp_path))
    assert paths(walked) == ["exact.py"] and any("over.py" in s for s in walked.skipped)


def test_a_file_far_over_the_limit_is_left_out_by_its_size_before_it_is_read(tmp_path, monkeypatch):
    put(tmp_path, "ok.py"); put(tmp_path, "huge.py", "a" * (W.MAX_FILE_CHARS * 4 + 10))
    from pathlib import Path
    reads = []
    real = Path.read_text
    monkeypatch.setattr(Path, "read_text", lambda self, *a, **k: (reads.append(self.name), real(self, *a, **k))[1])
    walked = W.walk(str(tmp_path))
    assert paths(walked) == ["ok.py"] and reads == ["ok.py"] and any("huge.py" in s and "too large" in s for s in walked.skipped)


def test_a_suffix_in_capital_letters_is_still_source(tmp_path):
    put(tmp_path, "UPPER.PY"); put(tmp_path, "Mixed.Sql", "-- x"); put(tmp_path, "image.PNG", "x")
    assert paths(W.walk(str(tmp_path))) == ["Mixed.Sql", "UPPER.PY"]


def test_when_the_walk_stops_early_the_files_it_did_read_are_still_in_path_order(tmp_path):
    for name in ("z.py", "m.py", "a/k.py", "a/l.py", "a/m.py"):                  # the top folder's files are walked first, but a/ sorts before them
        put(tmp_path, name)
    walked = W.walk(str(tmp_path), max_files=3)
    assert walked.stopped and paths(walked) == ["a/k.py", "m.py", "z.py"]


def test_a_walk_of_a_normal_folder_says_nothing_was_stopped(tmp_path):
    put(tmp_path, "a.py")
    assert W.walk(str(tmp_path)).stopped is None and W.walk(str(tmp_path), max_files=1).stopped is None
