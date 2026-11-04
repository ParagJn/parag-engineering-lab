"""The sandbox's file tools and its rules, with no subprocess (S16): paths, limits, the allow-list, the environment, the profile text, the report parser.

Anything here that touches the disk does so inside pytest's temporary folder. The real-subprocess behaviour (network refused, tree kill, and so on) is in
test_sandbox_run.py under the `sandbox` marker."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from app.guardrails.scan import Scanner
from app.sandbox import policy as P
from app.sandbox import profile as OS
from app.sandbox.errors import CommandRefused, ContentRefused, LimitExceeded, PathRefused, SandboxUnavailable
from app.sandbox.pytest_report import MAX_FAILURES, RunReport, parse, report_from
from app.sandbox.runner import Result, scrub_locations
from app.sandbox.workspace import Limits, Workspace, check_relative

AWS = "AKIA" + "IOSFODNN7EXAMPLE"


@pytest.fixture
def ws(tmp_path) -> Workspace:
    return Workspace(tmp_path / "ws", Limits(file_bytes=2000, max_files=5, total_bytes=6000), Scanner())


# ---- paths: the text -------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("path, parts", [
    ("app.py", ("app.py",)), ("src/app.py", ("src", "app.py")), ("./src//app.py", ("src", "app.py")), ("a/b/c/d.txt", ("a", "b", "c", "d.txt")),
    ("tests/test_x.py", ("tests", "test_x.py")), ("my-file_2.v1.json", ("my-file_2.v1.json",)),
])
def test_a_good_relative_path_is_split_into_its_parts(path, parts):
    assert check_relative(path) == parts


@pytest.mark.parametrize("path, fragment", [
    ("", "give a file path"), ("   ", "give a file path"), (None, "give a file path"), (5, "give a file path"),
    (" a.py", "start or end with spaces"), ("a.py ", "start or end with spaces"),
    ("../x.py", "go up with '..'"), ("a/../../x.py", "go up with '..'"), ("a/..", "go up with '..'"), ("..", "go up with '..'"),
    ("/etc/passwd", "cannot start with '/'"), ("~/x", "cannot start with '/'"), ("C:/x", "cannot start with '/'"), ("c:x", "cannot start with '/'"),
    ("a\\b.py", "forward slashes"), ("a\x00b", "control characters"), ("a\nb", "control characters"), ("a\tb", "control characters"), ("a\x7fb", "control characters"),
    (".", "the workspace itself"), ("./", "the workspace itself"), ("./.", "the workspace itself"), ("//", "cannot start with '/'"),
    ("a b.py", "only letters, digits"), ("a;b", "only letters, digits"), ("a$b", "only letters, digits"), ("é.py", "only letters, digits"), ("a*.py", "only letters, digits"),
    ("...", "only dots"), ("a/.../b", "only dots"),
    (".env", "reserved for credentials"), (".env.local", "reserved for credentials"), ("src/.git/config", "reserved for credentials"), (".ssh/id_rsa", "reserved for credentials"),
    ("cert.PEM", "reserved for credentials"), ("server.key", "reserved for credentials"), ("a/.aws/credentials", "reserved for credentials"), (".NPMRC", "reserved for credentials"),
    ("x" * 201, "limited to 200 characters"), ("/".join(["d"] * 13), "limited to 12 levels"),
])
def test_a_bad_path_is_refused_with_the_reason(path, fragment):
    with pytest.raises(PathRefused, match=fragment):
        check_relative(path)


def test_the_limits_on_a_path_are_exact():
    assert check_relative("x" * 200) == ("x" * 200,)
    assert len(check_relative("/".join(["d"] * 12))) == 12


# ---- paths: the disk -------------------------------------------------------------------------------------------------------------------------------

def test_a_symlink_to_the_outside_is_never_followed(ws, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("top secret")
    os.symlink(outside, ws.root / "link")
    for op in (lambda: ws.read_file("link/secret.txt"), lambda: ws.write_file("link/new.txt", "x"), lambda: ws.list_files("link"), lambda: ws.delete_file("link/secret.txt")):
        with pytest.raises(PathRefused, match="through a symlink"):
            op()
    assert not (outside / "new.txt").exists() and (outside / "secret.txt").read_text() == "top secret"


def test_a_symlinked_file_is_refused_and_a_symlink_is_not_listed(ws, tmp_path):
    (tmp_path / "target.txt").write_text("hello")
    os.symlink(tmp_path / "target.txt", ws.root / "alias.txt")
    ws.write_file("real.txt", "ok")
    with pytest.raises(PathRefused, match="through a symlink"):
        ws.read_file("alias.txt")
    with pytest.raises(PathRefused, match="through a symlink"):
        ws.write_file("alias.txt", "overwrite")
    assert (tmp_path / "target.txt").read_text() == "hello"
    assert ws.list_files() == ["real.txt"]


def test_a_symlink_to_a_folder_inside_is_also_refused_so_a_path_has_one_meaning(ws):
    ws.write_file("a/b.txt", "x")
    os.symlink(ws.root / "a", ws.root / "alias")
    with pytest.raises(PathRefused, match="through a symlink"):
        ws.read_file("alias/b.txt")


def test_tools_never_create_a_symlink(ws):
    ws.write_file("a.txt", "x")
    ws.make_dir("d")
    assert not [p for p in ws.root.rglob("*") if p.is_symlink()]


def test_a_path_is_shown_as_it_is_inside_the_workspace_never_the_real_location(ws, tmp_path):
    shown = ws.write_file("src/app.py", "x = 1\n")
    assert shown == "src/app.py" and str(tmp_path) not in shown
    assert ws.shown(tmp_path / "elsewhere") == "(outside the workspace)"
    with pytest.raises(PathRefused) as error:
        ws.read_file("missing.txt")
    assert str(tmp_path) not in str(error.value) and "missing.txt does not exist" in str(error.value)


def test_a_project_id_is_checked_before_it_becomes_a_folder_name(tmp_path):
    for bad in ("../x", "a/b", "", "a b", "x" * 65, None, "a\x00b", ".."):
        with pytest.raises(PathRefused):
            Workspace.for_project(tmp_path, bad)
    assert Workspace.for_project(tmp_path, "good_id-1").root == tmp_path / "good_id-1"
    assert not (tmp_path / "x").exists()


def test_two_projects_cannot_see_each_others_files(tmp_path):
    a, b = Workspace.for_project(tmp_path, "pa"), Workspace.for_project(tmp_path, "pb")
    a.write_file("secret.txt", "a's")
    assert b.list_files() == [] and not (b.root / "secret.txt").exists()
    with pytest.raises(PathRefused):
        b.read_file("secret.txt")
    with pytest.raises(PathRefused):
        b.read_file("../pa/secret.txt")


# ---- the tools --------------------------------------------------------------------------------------------------------------------------------------

def test_write_read_list_delete_and_make_dir_do_what_they_say(ws):
    assert ws.write_file("src/app.py", "print('hi')\n") == "src/app.py"
    ws.write_file("README.md", "# hi\n")
    assert ws.read_file("src/app.py") == "print('hi')\n"
    assert ws.list_files() == ["README.md", "src/app.py"] and ws.list_files("src") == ["src/app.py"] and ws.list_files("src/app.py") == ["src/app.py"]
    assert ws.make_dir("empty/inner") == "empty/inner" and (ws.root / "empty" / "inner").is_dir()
    ws.delete_file("README.md")
    assert ws.list_files() == ["src/app.py"]


def test_a_write_replaces_the_old_file_whole(ws):
    ws.write_file("a.txt", "first version")
    ws.write_file("a.txt", "second")
    assert ws.read_file("a.txt") == "second"
    assert not [p for p in ws.root.iterdir() if p.name.startswith(".write-")]


def test_a_failed_write_leaves_the_old_file_whole_and_no_temporary_file(ws, monkeypatch):
    ws.write_file("a.txt", "keep me")

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        ws.write_file("a.txt", "new content")
    monkeypatch.undo()
    assert ws.read_file("a.txt") == "keep me" and not [p for p in ws.root.iterdir() if p.name.startswith(".write-")]


def test_folders_and_files_are_not_mixed_up(ws):
    ws.write_file("d/x.txt", "1")
    with pytest.raises(PathRefused, match="is a folder"):
        ws.write_file("d", "x")
    with pytest.raises(PathRefused, match="is a folder"):
        ws.read_file("d")
    with pytest.raises(PathRefused, match="only files can be deleted"):
        ws.delete_file("d")
    with pytest.raises(PathRefused, match="is a file"):
        ws.make_dir("d/x.txt")
    with pytest.raises(PathRefused, match="does not exist"):
        ws.delete_file("nothing.txt")


def test_content_must_be_text(ws):
    for bad in (b"bytes", 5, None, ["x"]):
        with pytest.raises(ContentRefused, match="must be text"):
            ws.write_file("a.txt", bad)  # type: ignore[arg-type]
    with pytest.raises(ContentRefused, match="NUL"):
        ws.write_file("a.txt", "ok\x00not ok")
    assert ws.list_files() == []


def test_unicode_text_is_stored_and_counted_in_bytes(ws):
    ws.write_file("u.txt", "héllo wörld ✓")
    assert ws.read_file("u.txt") == "héllo wörld ✓"
    with pytest.raises(LimitExceeded):
        ws.write_file("big.txt", "é" * 1001)                                   # 2,002 bytes against a 2,000-byte limit


# ---- limits ----------------------------------------------------------------------------------------------------------------------------------------------

def test_one_file_may_be_exactly_the_limit_and_not_a_byte_more(ws):
    ws.write_file("at.txt", "a" * 2000)
    with pytest.raises(LimitExceeded, match="limited to 2000 bytes; this one is 2001") as error:
        ws.write_file("over.txt", "a" * 2001)
    assert error.value.limit == "file_bytes" and not (ws.root / "over.txt").exists()


def test_the_number_of_files_may_reach_the_limit_and_not_pass_it_but_replacing_one_is_always_fine(ws):
    for n in range(5):
        ws.write_file(f"f{n}.txt", "x")
    with pytest.raises(LimitExceeded, match="limited to 5 files") as error:
        ws.write_file("one_more.txt", "x")
    assert error.value.limit == "max_files"
    ws.write_file("f0.txt", "replaced")
    assert ws.read_file("f0.txt") == "replaced" and len(ws.list_files()) == 5


def test_the_total_size_may_reach_the_limit_and_not_pass_it_and_a_replacement_counts_only_the_difference(ws):
    for n in range(3):
        ws.write_file(f"f{n}.txt", "a" * 2000)
    with pytest.raises(LimitExceeded, match="6000 bytes in all") as error:
        ws.write_file("f3.txt", "a")
    assert error.value.limit == "total_bytes"
    ws.write_file("f0.txt", "b" * 2000)                                          # same size: allowed
    ws.write_file("f0.txt", "c")                                                 # smaller: allowed, and frees room
    ws.write_file("f3.txt", "d" * 1999)
    assert ws.usage() == (4, 2 * 2000 + 1 + 1999)


def test_usage_counts_files_and_bytes_and_ignores_symlinks(ws, tmp_path):
    (tmp_path / "big.txt").write_text("z" * 100)
    os.symlink(tmp_path / "big.txt", ws.root / "alias")
    ws.write_file("a.txt", "abc")
    assert ws.usage() == (1, 3)


def test_reset_empties_the_workspace_and_leaves_what_is_outside_alone(ws, tmp_path):
    (tmp_path / "keep.txt").write_text("keep")
    os.symlink(tmp_path / "keep.txt", ws.root / "alias")
    ws.write_file("d/x.txt", "x")
    ws.reset()
    assert list(ws.root.iterdir()) == [] and (tmp_path / "keep.txt").read_text() == "keep"


# ---- secrets ---------------------------------------------------------------------------------------------------------------------------------------------

def test_a_file_holding_a_secret_is_refused_and_leaves_nothing_behind(ws):
    with pytest.raises(ContentRefused, match="looks like a secret") as error:
        ws.write_file("config.py", f"KEY = '{AWS}'\n")
    assert AWS not in str(error.value) and not (ws.root / "config.py").exists()


def test_a_private_key_is_refused_and_personal_data_is_not(ws):
    with pytest.raises(ContentRefused):
        ws.write_file("k.txt", "-----" + "BEGIN RSA PRIVATE" + " KEY-----\nabc\n-----" + "END RSA PRIVATE" + " KEY-----\n")
    ws.write_file("people.txt", "contact jane.doe@acme-corp.co.uk")               # personal data is flagged elsewhere, not a refusal here


def test_with_no_scanner_nothing_is_scanned_but_every_other_rule_still_applies(tmp_path):
    bare = Workspace(tmp_path / "w")
    bare.write_file("c.py", f"KEY = '{AWS}'\n")
    with pytest.raises(PathRefused):
        bare.write_file("../x", "y")


# ---- the allow-list ---------------------------------------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("program, args", [
    ("python", ["app.py"]), ("python3", ["src/app.py", "--flag"]), ("python", ["-m", "mypackage.main"]), ("python", ["-m", "unittest"]),
    ("pytest", []), ("pytest", ["-q", "tests/test_x.py"]), ("pytest", ["-k", "name", "-x"]),
    ("pip", ["list"]), ("pip", ["--version"]), ("pip", ["freeze"]), ("pip", ["show", "pytest"]),
    ("node", ["app.js"]), ("npm", ["test"]), ("npm", ["run", "build"]), ("npm", ["run", "test:unit"]), ("npm", ["build"]),
    ("ls", []), ("ls", ["-la", "src"]), ("cat", ["src/app.py"]), ("head", ["-n", "5", "a.txt"]), ("tail", ["a.txt"]), ("wc", ["-l", "a.txt"]), ("grep", ["-rn", "def", "src"]),
    ("diff", ["a.txt", "b.txt"]), ("diff", ["-r", "src", "old"]), ("find", []), ("find", [".", "-name", "*.py", "-type", "f"]), ("find", ["src", "-newer", "a.txt", "-print0"]),
    ("node", ["--check", "app.js"]), ("node", ["-c", "src/app.js"]),
])
def test_an_allowed_program_with_good_arguments_is_allowed(program, args):
    if program in ("node", "npm", "find", "diff") and not any(os.access(f"{d}/{program}", os.X_OK) for d in ("/usr/bin", "/bin", "/usr/local/bin", "/opt/homebrew/bin")):
        pytest.skip(f"{program} is not installed here")
    command = P.check_command(program, args)
    assert command.name == program and list(command.args)[-len(args):] == args if args else True


@pytest.mark.parametrize("program", ["curl", "wget", "sh", "bash", "zsh", "ssh", "scp", "nc", "ncat", "telnet", "rm", "mv", "cp", "chmod", "chown", "sudo", "su", "kill", "env",
                                      "xargs", "git", "docker", "make", "perl", "ruby", "php", "osascript", "open", "launchctl", "defaults", "security", "python2", "pythonw"])
def test_a_program_not_on_the_list_is_refused_by_name(program):
    with pytest.raises(CommandRefused, match=f"'{program}' is not on the allow-list"):
        P.check_command(program, [])


@pytest.mark.parametrize("program", ["/bin/ls", "/usr/bin/python3", "./python", "../x", "bin/ls", "C:\\python", "ls ", " ls"])
def test_a_program_must_be_a_plain_name_not_a_path_and_the_message_says_so(program):
    with pytest.raises(CommandRefused, match="name a program, not a path"):
        P.check_command(program, [])


@pytest.mark.parametrize("program", ["", None, "  "])
def test_an_empty_program_name_is_asked_for(program):
    with pytest.raises(CommandRefused, match="name the program to run"):
        P.check_command(program, [])  # type: ignore[arg-type]


@pytest.mark.parametrize("args", [["install", "requests"], ["install", "-r", "req.txt"], ["download", "x"], ["wheel", "x"], ["uninstall", "x"], [], ["list", "--index-url", "http://x"],
                                   ["list", "-i", "http://x"], ["list", "--extra-index-url=http://x"], ["list", "--find-links", "x"], ["list", "-f", "x"]])
def test_pip_may_only_list_and_never_with_an_index(args):
    with pytest.raises(CommandRefused, match="pip can only list"):
        P.check_command("pip", args)


@pytest.mark.parametrize("args", [["install"], ["i"], ["ci"], ["add", "x"], ["publish"], ["update"], [], ["run"], ["run", "a b"], ["run", "x;y"], ["--version"]])
def test_npm_may_only_test_run_or_build(args):
    with pytest.raises(CommandRefused):
        P.check_command("npm", args)


@pytest.mark.parametrize("args, fragment", [
    ([], "needs a script"), (["-c", "print(1)"], "python -c"), (["-cprint(1)"], "python -c"), (["-i"], "python -c"), (["-"], "python -c"),
    (["-m"], "needs a module name"), (["-m", "pip", "install", "x"], "python -m pip is not allowed"), (["-m", "http.server"], "http.server is not allowed"),
    (["-m", "ensurepip"], "ensurepip is not allowed"), (["-m", "venv", "x"], "venv is not allowed"), (["-m", "a b"], "plain module name"), (["-m", "x;y"], "plain module name"),
    (["-m", "pdb"], "pdb is not allowed"), (["-X", "dev", "a.py"], "option '-X'"), (["-W", "ignore", "a.py"], "option '-W'"),
    (["/etc/passwd"], "must be a path inside the workspace"), (["../a.py"], "must be a path inside"), (["~/a.py"], "must be a path inside"),
])
def test_python_is_limited_to_running_a_file_in_the_workspace_or_a_plain_module(args, fragment):
    with pytest.raises(CommandRefused, match=fragment):
        P.check_command("python", args)


@pytest.mark.parametrize("program", ["cat", "head", "tail", "wc", "grep", "ls", "diff", "find"])
def test_the_readers_cannot_be_pointed_outside_the_workspace(program):
    for bad in ("/etc/passwd", "../x", "~/.ssh/id_rsa", "a/../../x", "C:\\x", "a\\b"):
        with pytest.raises(CommandRefused, match="must be a path inside the workspace"):
            P.check_command(program, [bad])
    P.check_command(program, ["-n", "src/a.py"])                               # an option is not a path


@pytest.mark.parametrize("word", ["-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls"])
def test_find_may_only_look_never_run_a_program_or_delete_or_write(word):
    with pytest.raises(CommandRefused, match=f"find {word} is not allowed"):
        P.check_command("find", [".", "-name", "*.py", word, "x"])
    with pytest.raises(CommandRefused, match=f"find {word} is not allowed"):
        P.check_command("find", [word])


@pytest.mark.parametrize("args", [["--check"], ["--check", "a.js", "b.js"], ["--check", "--eval"], ["--check", "/etc/hosts"], ["--check", "../a.js"], ["-c", "~/a.js"], ["-c"]])
def test_node_check_takes_exactly_one_path_inside_the_workspace(args):
    with pytest.raises(CommandRefused):
        P.check_command("node", args)


@pytest.mark.parametrize("args", [["-e", "1"], ["--eval", "1"], ["-p", "1"], ["--print", "1"], ["--require", "x"], ["-r", "x"], ["--inspect"], ["-i"]])
def test_node_still_refuses_every_other_option(args):
    with pytest.raises(CommandRefused):
        P.check_command("node", args)


def test_pytest_arguments_are_paths_inside_the_workspace_too():
    with pytest.raises(CommandRefused, match="pytest"):
        P.check_command("pytest", ["/etc"])
    with pytest.raises(CommandRefused, match="pytest"):
        P.check_command("pytest", ["../other"])


def test_shell_characters_are_ordinary_text_because_there_is_no_shell():
    command = P.check_command("python", ["app.py", "a;b", "&&", "|", "$(whoami)", "`id`", ">", "x"])
    assert command.args[-7:] == ("a;b", "&&", "|", "$(whoami)", "`id`", ">", "x")
    assert command.executable == P.python_executable() and "sh" not in command.argv[0].split("/")[-1]


def test_a_string_instead_of_a_list_is_refused_because_nothing_would_split_it():
    with pytest.raises(CommandRefused, match="not one string"):
        P.check_command("python", "app.py --flag")  # type: ignore[arg-type]


@pytest.mark.parametrize("args, fragment", [
    ([1], "must be text"), ([None], "must be text"), (["a\x00b"], "NUL byte or a line break"), (["a\nb"], "NUL byte or a line break"), (["a\rb"], "NUL byte or a line break"),
    (["x" * 2001], "limited to 2000 characters"), (["a"] * 41, "limited to 40 arguments"),
])
def test_arguments_are_bounded_and_clean(args, fragment):
    with pytest.raises(CommandRefused, match=fragment):
        P.check_command("ls", args)


def test_the_limits_on_arguments_are_exact():
    P.check_command("ls", ["x" * 2000])
    P.check_command("ls", ["a"] * 40)


def test_python_is_always_the_venvs_own_interpreter_and_pytest_is_started_through_it():
    py = P.check_command("python3", ["a.py"])
    assert py.executable == str(Path(sys.executable).absolute())
    tests = P.check_command("pytest", ["-q"])
    assert tests.argv[:3] == [P.python_executable(), "-m", "pytest"]


# ---- the environment -------------------------------------------------------------------------------------------------------------------------------------

def test_a_command_sees_only_a_short_list_of_variables_and_none_of_the_apps(monkeypatch):
    for name, value in (("IBM_ICA_API_KEY", "sk-planted"), ("IBM_ICA_ENDPOINT", "https://planted.invalid"), ("HTTPS_PROXY", "http://p.invalid"), ("HTTP_PROXY", "http://p.invalid"),
                        ("ALL_PROXY", "x"), ("AWS_SECRET_ACCESS_KEY", "planted"), ("MY_OWN_SECRET", "planted"), ("OPENAI_API_KEY", "planted"), ("SSH_AUTH_SOCK", "/tmp/x")):
        monkeypatch.setenv(name, value)
    env = P.clean_environment("/scratch")
    assert not [k for k in env if any(s in k for s in ("IBM", "PROXY", "SECRET", "KEY", "OPENAI", "SSH", "AWS"))]
    assert "planted" not in " ".join(env.values())


def test_the_environment_points_home_and_temp_at_the_scratch_folder_and_keeps_python_quiet_and_deterministic():
    env = P.clean_environment("/scratch")
    assert env["HOME"] == "/scratch" and env["TMPDIR"] == "/scratch"
    assert env["PYTHONDONTWRITEBYTECODE"] == "1" and env["PYTHONHASHSEED"] == "0" and env["PIP_NO_INDEX"] == "1" and env["PYTHONNOUSERSITE"] == "1"
    assert env["PATH"].startswith(P.venv_bin() + ":")


def test_only_the_named_harmless_variables_are_passed_through_from_the_parent(monkeypatch):
    monkeypatch.setenv("LANG", "en_GB.UTF-8")
    monkeypatch.setenv("TZ", "Asia/Kolkata")
    monkeypatch.setenv("LC_ALL", "")
    env = P.clean_environment("/s")
    assert env["LANG"] == "en_GB.UTF-8" and env["TZ"] == "Asia/Kolkata" and "LC_ALL" not in env


# ---- the profile text ---------------------------------------------------------------------------------------------------------------------------------------

def profile(tmp_path):
    return OS.build_profile(tmp_path / "ws", tmp_path / "sc", sys.prefix, sys.base_prefix)


def test_the_profile_denies_everything_by_default_and_the_network_outright(tmp_path):
    text = profile(tmp_path)
    assert text.splitlines()[:2] == ["(version 1)", "(deny default)"] and "(deny network*)" in text
    assert "(allow default)" not in text and "(allow network" not in text


def test_the_profile_lets_a_command_write_only_in_its_workspace_and_scratch_and_devnull(tmp_path):
    text = profile(tmp_path)
    writes = [l for l in text.splitlines() if "file-write*" in l]
    assert len(writes) == 2
    assert str((tmp_path / "ws").resolve()) in writes[0] and str((tmp_path / "sc").resolve()) in writes[0] and '(literal "/dev/null")' in writes[1]
    assert not [l for l in text.splitlines() if "file-write*" in l and ("/usr" in l or "/Users" in l.replace(str(tmp_path.resolve()), ""))]


def test_the_profile_reads_the_system_and_python_but_not_the_apps_data_or_the_home(tmp_path):
    text = profile(tmp_path)
    for folder in ("/usr", "/System", "/Library/Frameworks"):
        assert f'(subpath "{folder}")' in text
    assert f'(subpath "{Path(sys.prefix).resolve()}")' in text
    for forbidden in ("/Users\")", "/Users/paragjain\")", "backend/data", ".env", "recordings", "/private/tmp\")", "(allow file-read*)"):
        assert forbidden not in text


def test_the_same_inputs_give_the_same_profile(tmp_path):
    assert profile(tmp_path) == profile(tmp_path)


@pytest.mark.parametrize("bad", ['/tmp/a"b', "/tmp/a\nb", "/tmp/a)(allow default)", "/tmp/a;b", "relative/path", "/tmp/../etc", "/tmp/a\\b", "/tmp/a$b", "/tmp/a`b"])
def test_a_path_that_could_rewrite_the_profile_is_refused_before_it_is_placed_in_it(bad):
    with pytest.raises(SandboxUnavailable, match="cannot place in its rules safely"):
        OS._check_path(bad, "workspace")


def test_a_plain_path_with_spaces_and_dashes_is_accepted():
    assert OS._check_path("/tmp/my project-1/ws_2", "workspace") == "/tmp/my project-1/ws_2"


def test_wrap_puts_the_command_under_the_profile():
    assert OS.wrap(["/bin/ls", "-l"], "/tmp/p.sb") == [OS.SANDBOX_EXEC, "-f", "/tmp/p.sb", "/bin/ls", "-l"]


# ---- the self-test, when the protection is missing -------------------------------------------------------------------------------------------------------------

def test_a_missing_sandbox_exec_is_a_refusal_with_a_sentence_not_a_fallback():
    with pytest.raises(SandboxUnavailable, match="sandbox-exec is not available on this machine, so no command will be run"):
        OS.self_test(sys.executable, sys.prefix, sys.base_prefix, sandbox_exec="/nonexistent/sandbox-exec")


def test_another_operating_system_is_refused_too(monkeypatch):
    monkeypatch.setattr(OS.sys, "platform", "linux")
    with pytest.raises(SandboxUnavailable, match="needs macOS's sandbox-exec; this machine is linux"):
        OS.self_test(sys.executable, sys.prefix, sys.base_prefix)
    assert not OS.sandbox_available()


def test_a_tool_that_does_not_actually_protect_fails_the_self_test(tmp_path):
    """A stand-in `sandbox-exec` that ignores the profile and just runs the command: the network and the outside write succeed, so the test must say no."""
    fake = tmp_path / "fake-sandbox-exec"
    fake.write_text('#!/bin/sh\nshift 2\nexec "$@"\n')
    fake.chmod(0o755)
    with pytest.raises(SandboxUnavailable, match="self-test failed"):
        OS.self_test(sys.executable, sys.prefix, sys.base_prefix, sandbox_exec=str(fake))


def test_a_tool_that_cannot_start_the_test_program_fails_the_self_test_too(tmp_path):
    fake = tmp_path / "broken-sandbox-exec"
    fake.write_text("#!/bin/sh\nexit 3\n")
    fake.chmod(0o755)
    with pytest.raises(SandboxUnavailable, match="did not run under the sandbox"):
        OS.self_test(sys.executable, sys.prefix, sys.base_prefix, sandbox_exec=str(fake))


# ---- locations in output --------------------------------------------------------------------------------------------------------------------------------------

def test_the_real_workspace_and_scratch_locations_are_replaced_in_a_programs_output(tmp_path):
    ws, sc = tmp_path / "ws", tmp_path / "sc"
    ws.mkdir()
    sc.mkdir()
    text = f'File "{ws.resolve()}/src/app.py", line 3\n{ws}/test.py:1: in x\nhome {sc.resolve()}/h\nin {ws.resolve()}\n'
    clean = scrub_locations(text, ws, sc)
    assert str(tmp_path) not in clean and 'File "src/app.py", line 3' in clean and "test.py:1: in x" in clean and "home <scratch>/h" in clean and "in ." in clean


# ---- the report parser -------------------------------------------------------------------------------------------------------------------------------------------

MIXED = """\
.FFsxXE                                                                  [100%]
==================================== ERRORS ====================================
__________________________ ERROR at setup of test_err __________________________

    @pytest.fixture
>   def broken(): raise RuntimeError("fixture failed")
E   RuntimeError: fixture failed

test_mix.py:12: RuntimeError
=================================== FAILURES ===================================
___________________________________ test_bad ___________________________________

>   def test_bad(): assert 1 + 1 == 3, "arithmetic is broken"
E   AssertionError: arithmetic is broken
E   assert (1 + 1) == 3

test_mix.py:3: AssertionError
__________________________________ test_boom ___________________________________

>   def test_boom(): raise ValueError("boom")
E   ValueError: boom

test_mix.py:4: ValueError
=========================== short test summary info ============================
PASSED test_mix.py::test_ok
SKIPPED [1] test_mix.py:5: later
XFAIL test_mix.py::test_xf
XPASS test_mix.py::test_xp
ERROR test_mix.py::test_err - RuntimeError: fixture failed
FAILED test_mix.py::test_bad - AssertionError: arithmetic is broken
FAILED test_mix.py::test_boom - ValueError: boom
==== 2 failed, 1 passed, 1 skipped, 1 xfailed, 1 xpassed, 1 error in 0.02s =====
"""


def test_a_mixed_run_gives_every_count_the_names_and_the_messages():
    r = parse(MIXED, 1)
    assert (r.status, r.exit_code, r.passed, r.failed, r.errors, r.skipped, r.xfailed, r.xpassed, r.seconds) == ("ran", 1, 1, 2, 1, 1, 1, 1, 0.02)
    assert r.total == 7 and r.passed_names == ("test_mix.py::test_ok",)
    assert [(f.kind, f.test, f.message) for f in r.failures] == [
        ("error", "test_mix.py::test_err", "RuntimeError: fixture failed"), ("failed", "test_mix.py::test_bad", "AssertionError: arithmetic is broken"),
        ("failed", "test_mix.py::test_boom", "ValueError: boom")]
    bad = next(f for f in r.failures if f.test.endswith("test_bad"))
    assert "assert (1 + 1) == 3" in bad.detail and not r.all_passed


def test_a_passing_run_is_a_pass_only_when_something_passed():
    ok = parse("..  [100%]\n==== 2 passed in 0.01s ====\n", 0)
    assert ok.all_passed and ok.passed == 2 and ok.failed == 0
    skipped = parse("s\n==== 1 skipped in 0.01s ====\n", 0)
    assert skipped.status == "ran" and skipped.passed == 0 and not skipped.all_passed             # nothing passed: not a pass
    assert not parse("..\n==== 2 passed in 0.01s ====\n", 1).all_passed                            # exit code disagrees: not a pass


def test_a_run_that_found_no_tests_is_its_own_result_never_zero_failed():
    r = parse("\n============================ no tests ran in 0.00s =============================\n", 5)
    assert r.status == "no_tests" and r.exit_code == 5 and not r.all_passed and r.total == 0 and "nothing to pass or fail" in r.reason


def test_a_collection_error_is_its_own_result_with_the_reason():
    out = ("==== ERRORS ====\n____ ERROR collecting test_i.py ____\nImportError while importing test module 'test_i.py'.\nTraceback:\ntest_i.py:1: in <module>\n"
           "    import nope\nE   ModuleNotFoundError: No module named 'nope'\n==== short test summary info ====\nERROR test_i.py\n!!!! Interrupted: 1 error during collection !!!!\n1 error in 0.05s\n")
    r = parse(out, 2)
    assert r.status == "collection_error" and r.errors == 1 and "could not collect" in r.reason
    assert [(f.kind, f.test, f.message) for f in r.failures] == [("error", "test_i.py", "ModuleNotFoundError: No module named 'nope'")] and not r.all_passed


def test_output_with_no_summary_is_a_crash_and_says_how_it_ended():
    r = parse("Traceback (most recent call last):\n  File x\nOSError: boom\n", 7)
    assert r.status == "crashed" and r.exit_code == 7 and "did not print a summary" in r.reason and "OSError: boom" in r.reason and not r.all_passed
    assert parse("", 1).status == "crashed"


def test_a_parametrised_failure_keeps_its_parameter_in_the_name():
    r = parse("=== FAILURES ===\n___ test_p[2] ___\nn = 2\nE assert 2 != 2\n=== short test summary info ===\nPASSED t.py::test_p[1]\nFAILED t.py::test_p[2] - assert 2 != 2\n=== 1 failed, 1 passed in 0.01s ===\n", 1)
    assert [f.test for f in r.failures] == ["t.py::test_p[2]"] and r.passed == 1 and "n = 2" in r.failures[0].detail


def test_only_the_first_fifty_failures_are_listed_but_the_count_is_all_of_them():
    lines = "\n".join(f"FAILED t.py::test_{n} - AssertionError" for n in range(80))
    r = parse(f"=== short test summary info ===\n{lines}\n=== 80 failed in 1.00s ===\n", 1)
    assert r.failed == 80 and len(r.failures) == MAX_FAILURES == 50


def test_the_summary_line_is_read_with_or_without_the_rule_and_with_a_clock():
    for line in ("==== 1 passed in 0.01s ====", "1 passed in 0.01s", "1 passed in 12.34s (0:00:12)", "======== 3 passed, 2 warnings in 0.50s ========"):
        r = parse(f"x\n{line}\n", 0)
        assert r.status == "ran" and r.passed in (1, 3), line
    assert parse("1 passed in 12.34s (0:00:12)\n", 0).seconds == 12.34


def test_a_line_in_a_tests_own_output_that_looks_like_a_summary_does_not_fool_the_parser():
    out = "PASSED fake.py::test_x\n99 passed in 0.01s\n=== short test summary info ===\nFAILED t.py::test_a - AssertionError\n=== 1 failed in 0.01s ===\n"
    r = parse(out, 1)
    assert r.failed == 1 and r.passed == 0                              # the LAST summary line wins


def test_a_timed_out_cut_off_refused_or_unavailable_run_is_reported_as_that_never_as_a_result_of_tests():
    assert report_from(Result("timed_out", None, "partial", reason="too long", seconds=2.0)).status == "timed_out"
    assert report_from(Result("ran", -15, "x", True, reason="printed more", limit="output_bytes")).status == "cut_off"
    assert report_from(Result("refused", reason="no")).status == "refused"
    assert report_from(Result("unavailable", reason="no sandbox")).status == "unavailable"
    for status in ("timed_out", "refused", "unavailable"):
        r = report_from(Result(status, None, "1 passed in 0.01s", reason="x"))
        assert r.passed == 0 and not r.all_passed


def test_a_run_report_carries_the_redaction_flag():
    assert report_from(Result("ran", 0, "1 passed in 0.01s", redacted=True)).redacted is True
    assert report_from(Result("ran", 0, "1 passed in 0.01s")).redacted is False


# ---- the workspace folder itself being swapped, found by the mutation check (2026-11-01) ---------------------------------------------------------------------------

def swapped(ws: Workspace, outside: Path) -> None:
    """After the workspace was opened, replace its folder with a symlink to somewhere else."""
    shutil.rmtree(ws.root)
    os.symlink(outside, ws.root)


def test_a_workspace_folder_swapped_for_a_symlink_refuses_everything_and_creates_nothing_outside(ws, tmp_path):
    ws.write_file("a.txt", "x")
    outside = tmp_path / "outside"
    outside.mkdir()
    swapped(ws, outside)
    for operation in (lambda: ws.write_file("sub/deeper/new.txt", "ESCAPED"), lambda: ws.write_file("top.txt", "ESCAPED"), lambda: ws.read_file("a.txt"),
                      lambda: ws.make_dir("newdir"), lambda: ws.list_files(), lambda: ws.delete_file("a.txt")):
        with pytest.raises(PathRefused, match="workspace folder has been replaced or moved"):
            operation()
    assert list(outside.iterdir()) == []                                              # not even an empty folder


def test_a_workspace_folder_that_vanished_or_became_a_file_is_refused_too(ws, tmp_path):
    shutil.rmtree(ws.root)
    with pytest.raises(PathRefused, match="replaced or moved"):
        ws.write_file("a.txt", "x")
    ws.root.write_text("now a file")
    with pytest.raises(PathRefused, match="replaced or moved"):
        ws.read_file("a.txt")


def test_a_refused_write_leaves_no_folder_behind_when_a_middle_folder_is_a_symlink_made_after_the_check(ws, tmp_path, monkeypatch):
    """A folder made a moment ago must be inside before the next level is made; a refusal must not leave the later levels created."""
    outside = tmp_path / "outside"
    outside.mkdir()
    ws.make_dir("a")
    shutil.rmtree(ws.root / "a")
    os.symlink(outside, ws.root / "a")
    with pytest.raises(PathRefused, match="symlink"):
        ws.write_file("a/b/c/new.txt", "ESCAPED")
    assert list(outside.iterdir()) == []


def test_folders_are_made_one_level_at_a_time_inside_the_workspace(ws):
    assert ws.write_file("a/b/c/d.txt", "x") == "a/b/c/d.txt"
    assert (ws.root / "a" / "b" / "c").is_dir() and ws.read_file("a/b/c/d.txt") == "x"
    ws.make_dir("a/b/other")
    assert (ws.root / "a" / "b" / "other").is_dir()
    ws.write_file("a/b/c/e.txt", "y")                                                  # folders that already exist are reused


def test_a_folder_that_resolves_outside_after_it_is_made_is_refused(ws, tmp_path, monkeypatch):
    """The re-check after each mkdir: simulate a folder that, once made, resolves outside (a race with something else changing the disk)."""
    outside = tmp_path / "outside"
    outside.mkdir()
    real_resolve = Path.resolve
    state = {"armed": False}

    def resolve(self, *a, **k):
        if state["armed"] and self.name == "inner":
            return outside
        return real_resolve(self, *a, **k)
    monkeypatch.setattr(Path, "resolve", resolve)
    state["armed"] = True
    with pytest.raises(PathRefused, match="leaves the workspace"):
        ws.write_file("inner/new.txt", "x")


def test_a_component_swapped_for_a_link_after_the_symlink_check_is_still_caught_by_where_it_resolves(ws, tmp_path, monkeypatch):
    """The two checks guard different moments: the first says 'this is a symlink', the second says 'this resolves outside'. If something replaces a folder with a
    link in the instant between them, only the second one can refuse. Simulated by making the first one miss it."""
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "f.txt").write_text("secret")
    os.symlink(outside, ws.root / "esc")
    real = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda self: False if self.name == "esc" else real(self))
    for operation in (lambda: ws.read_file("esc/f.txt"), lambda: ws.list_files("esc"), lambda: ws.delete_file("esc/f.txt")):
        with pytest.raises(PathRefused, match="leaves the workspace"):
            operation()
    assert (outside / "f.txt").read_text() == "secret"


def test_a_folder_made_by_a_write_that_resolves_outside_is_refused_and_the_levels_after_it_are_not_made(ws, tmp_path, monkeypatch):
    outside = tmp_path / "outside"
    outside.mkdir()
    real = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda self, *a, **k: outside if self.name == "inner" else real(self, *a, **k))
    with pytest.raises(PathRefused, match="leaves the workspace"):
        ws.write_file("inner/deeper/new.txt", "x")
    assert not (ws.root / "inner" / "deeper").exists()                                  # it stopped at the level that was wrong


def test_the_real_location_is_replaced_before_the_short_one_that_is_inside_it(tmp_path):
    """On a Mac the same folder is both /var/x and /private/var/x. If the SHORT form were replaced first, the long form would be left as '/private' plus the
    replacement. Stand-ins make the two forms differ the way they do there."""
    class Folder:
        def __init__(self, short, real):
            self._short, self._real = short, real

        def resolve(self):
            return Path(self._real)

        def __str__(self):
            return self._short
    workspace = Folder("/var/folders/zz/T/ws", "/private/var/folders/zz/T/ws")
    scratch = Folder("/var/folders/zz/T/sc", "/private/var/folders/zz/T/sc")
    text = 'File "/private/var/folders/zz/T/ws/a.py", line 1\n/var/folders/zz/T/ws/b.py:2\nhome /private/var/folders/zz/T/sc/h and /var/folders/zz/T/sc/g\n'
    clean = scrub_locations(text, workspace, scratch)  # type: ignore[arg-type]
    assert clean == 'File "a.py", line 1\nb.py:2\nhome <scratch>/h and <scratch>/g\n'
    assert "/private" not in clean and "/var/" not in clean


# ---- folder tools (S17a) -----------------------------------------------------------------------------------------------------------

def test_remove_folder_removes_a_folder_and_everything_in_it_and_says_so(ws):
    ws.write_file("a/b/c.txt", "x")
    ws.write_file("a/d.txt", "y")
    ws.write_file("keep.txt", "z")
    assert ws.remove_folder("a") is True
    assert ws.list_files() == ["keep.txt"]


def test_remove_folder_says_false_for_a_folder_that_is_not_there(ws):
    assert ws.remove_folder("nothing") is False


def test_remove_folder_refuses_a_file_and_leaves_it(ws):
    ws.write_file("a.txt", "x")
    with pytest.raises(PathRefused, match="a.txt is a file; only folders can be removed"):
        ws.remove_folder("a.txt")
    assert ws.read_file("a.txt") == "x"


def test_remove_folder_refuses_the_workspace_itself_and_a_path_that_leaves_it(ws):
    ws.write_file("a.txt", "x")
    for bad in (".", "..", "../x", "/etc"):
        with pytest.raises(PathRefused):
            ws.remove_folder(bad)
    assert ws.list_files() == ["a.txt"]


def test_remove_folder_unlinks_a_link_inside_without_following_it(ws, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "precious.txt").write_text("keep me")
    ws.write_file("a/real.txt", "x")
    os.symlink(outside, ws.root / "a" / "link")
    assert ws.remove_folder("a") is True
    assert (outside / "precious.txt").read_text() == "keep me"


def test_replace_folder_makes_the_destination_hold_exactly_the_source(ws):
    ws.write_file("stage/db/new.sql", "new")
    ws.write_file("db/old.sql", "old")
    ws.write_file("other/keep.txt", "k")
    ws.replace_folder("stage/db", "db")
    assert ws.list_files() == ["db/new.sql", "other/keep.txt"]


def test_replace_folder_creates_the_destination_when_there_is_none(ws):
    ws.write_file("stage/db/new.sql", "new")
    ws.replace_folder("stage/db", "deep/er/db")
    assert ws.read_file("deep/er/db/new.sql") == "new"


def test_replace_folder_with_a_missing_source_leaves_the_destination_whole(ws):
    ws.write_file("db/old.sql", "old")
    with pytest.raises(PathRefused, match="does not exist"):
        ws.replace_folder("stage/db", "db")
    assert ws.read_file("db/old.sql") == "old"


def test_replace_folder_with_a_file_as_source_leaves_the_destination_whole(ws):
    ws.write_file("stage.txt", "x")
    ws.write_file("db/old.sql", "old")
    with pytest.raises(PathRefused, match="only a folder can replace a folder"):
        ws.replace_folder("stage.txt", "db")
    assert ws.read_file("db/old.sql") == "old"


def test_replace_folder_refuses_a_file_as_destination(ws):
    ws.write_file("stage/x.txt", "x")
    ws.write_file("db", "i am a file")
    with pytest.raises(PathRefused, match="is a file"):
        ws.replace_folder("stage", "db")
    assert ws.read_file("db") == "i am a file"


@pytest.mark.parametrize("source, destination", [("a", "a"), ("a/b", "a"), ("a", "a/b")])
def test_a_folder_cannot_replace_itself_or_one_inside_it(ws, source, destination):
    ws.write_file("a/b/c.txt", "x")
    with pytest.raises(PathRefused, match="cannot replace itself or one inside it"):
        ws.replace_folder(source, destination)
    assert ws.read_file("a/b/c.txt") == "x"


def test_replace_folder_leaves_no_moved_aside_copy_next_to_it(ws):
    ws.write_file("stage/db/new.sql", "new")
    ws.write_file("db/old.sql", "old")
    ws.replace_folder("stage/db", "db")
    assert sorted(p.name for p in ws.root.iterdir()) == ["db", "stage"] and ws.list_files() == ["db/new.sql"]


def test_replace_folder_sweeps_a_moved_aside_copy_a_crashed_replacement_left(ws):
    ws.write_file("db/old.sql", "old")
    (ws.root / ".old-db-deadbeef").mkdir()
    (ws.root / ".old-db-deadbeef" / "junk.txt").write_text("junk")
    ws.write_file("stage/db/new.sql", "new")
    ws.replace_folder("stage/db", "db")
    assert sorted(p.name for p in ws.root.iterdir()) == ["db", "stage"]


def test_replace_folder_works_when_another_replacement_filled_the_destination_a_moment_ago(ws, monkeypatch):
    """The second of two replacements finds the folder it meant to move aside already gone, and the first one's folder in its place."""
    ws.write_file("stage/db/mine.sql", "mine")
    real_rename = os.rename
    calls = {"n": 0}

    def rename(src, dst, *a, **k):
        calls["n"] += 1
        if calls["n"] == 1:                                           # the move-aside: another writer got there first
            raise FileNotFoundError(2, "gone", str(src))
        return real_rename(src, dst, *a, **k)
    monkeypatch.setattr(os, "rename", rename)
    ws.replace_folder("stage/db", "db")
    assert ws.read_file("db/mine.sql") == "mine"


def test_replace_folder_moves_a_folder_that_appears_at_the_last_moment_aside_and_still_succeeds(ws, monkeypatch):
    ws.write_file("stage/db/mine.sql", "mine")
    real_rename = os.rename
    state = {"planted": False}

    def rename(src, dst, *a, **k):
        if str(dst).endswith("/db") and not state["planted"] and "stage" in str(src):
            state["planted"] = True
            (ws.root / "db").mkdir()
            (ws.root / "db" / "theirs.sql").write_text("theirs")           # another replacement filled it between our two steps
        return real_rename(src, dst, *a, **k)
    monkeypatch.setattr(os, "rename", rename)
    ws.replace_folder("stage/db", "db")
    assert ws.list_files() == ["db/mine.sql"] and sorted(p.name for p in ws.root.iterdir()) == ["db", "stage"]


def test_a_folder_that_another_replacement_moves_aside_between_two_looks_is_never_mistaken_for_a_file(ws, monkeypatch):
    """The failure seen one run in many: the destination "exists", then is gone by the time it is asked whether it is a folder, so it read as a file."""
    ws.write_file("stage/db/mine.sql", "mine")
    real_exists = Path.exists
    monkeypatch.setattr(Path, "exists", lambda self, *a, **k: True if self.name == "db" and "stage" not in str(self) else real_exists(self, *a, **k))
    ws.replace_folder("stage/db", "db")                                           # nothing is at db, yet exists() claims there is: the answer must not be "it is a file"
    assert ws.read_file("db/mine.sql") == "mine"


def test_a_real_file_in_the_way_is_still_refused_and_left_alone(ws):
    ws.write_file("stage/db/mine.sql", "mine")
    ws.write_file("db", "i am a file")
    with pytest.raises(PathRefused, match="db is a file"):
        ws.replace_folder("stage/db", "db")
    assert ws.read_file("db") == "i am a file" and ws.read_file("stage/db/mine.sql") == "mine"
