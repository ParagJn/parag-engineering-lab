"""The sandbox with REAL subprocesses (S16): the network, writes outside, reads of the app's data, the timeout and the tree kill, output limits, the clean
environment, a fork bomb, the parsed pytest result, the audit trail and the service. Marked `sandbox`; they run in pytest's temporary folders only.

Every test that starts a long-lived process finishes by checking that none is left behind. They skip, loudly, if this machine has no `sandbox-exec`: the
runner refuses to run anything there, and that refusal is tested in test_sandbox_files.py."""
from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

import pytest

from app.config import Settings
from app.guardrails.scan import Scanner
from app.repos import Store
from app.sandbox import profile as OS
from app.sandbox.pytest_report import run_tests
from app.sandbox.runner import Limits, Result, Sandbox, current_processes, kill_tree
from app.sandbox.service import SandboxService
from app.sandbox.workspace import Workspace

pytestmark = [pytest.mark.sandbox, pytest.mark.skipif(not OS.sandbox_available(), reason="this machine has no sandbox-exec")]
AWS = "AKIA" + "IOSFODNN7EXAMPLE"


TEST_SECONDS = 40


@pytest.fixture(autouse=True)
def hard_time_limit():
    """Fail a test that runs far too long instead of hanging the suite. A break that removed the timeout would otherwise make a test wait for a
    120-second sleep, and a hung suite cannot be told from a slow machine, so the mutation check would have to call it invalid."""
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def stop(_signum, _frame):
        raise AssertionError(f"this test ran longer than {TEST_SECONDS} seconds and was stopped")
    previous = signal.signal(signal.SIGALRM, stop)
    signal.alarm(TEST_SECONDS)
    try:
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, previous)


@pytest.fixture(scope="module")
def sandbox() -> Sandbox:
    box = Sandbox(scanner=Scanner())
    assert box.availability() == "", box.availability()
    return box


@pytest.fixture
def ws(tmp_path) -> Workspace:
    return Workspace(tmp_path / "ws", scanner=Scanner())


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:                                                                  # a zombie is dead for our purposes
        import subprocess
        state = subprocess.run(["/bin/ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
        return bool(state) and not state.startswith("Z")
    except OSError:
        return True


def wait_gone(pid: int, seconds: float = 3.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not alive(pid):
            return True
        time.sleep(0.05)
    return not alive(pid)


# ---- it runs ----------------------------------------------------------------------------------------------------------------------------------

def test_a_script_runs_and_its_output_and_exit_code_come_back(sandbox, ws):
    ws.write_file("hello.py", "print('hello from inside')\n")
    r = sandbox.run(ws, "python", ["hello.py"])
    assert (r.status, r.exit_code, r.ok, r.truncated, r.redacted) == ("ran", 0, True, False, False) and r.output.strip() == "hello from inside" and r.seconds < 5


def test_a_failing_script_is_a_run_with_a_nonzero_exit_not_an_error(sandbox, ws):
    ws.write_file("bad.py", "import sys\nprint('about to fail', file=sys.stderr)\nsys.exit(3)\n")
    r = sandbox.run(ws, "python", ["bad.py"])
    assert (r.status, r.exit_code, r.ok) == ("ran", 3, False) and "about to fail" in r.output


def test_standard_error_is_part_of_the_output_and_an_exception_shows_its_trace_without_the_real_location(sandbox, ws, tmp_path):
    ws.write_file("boom.py", "raise ValueError('kaboom')\n")
    r = sandbox.run(ws, "python", ["boom.py"])
    assert r.exit_code == 1 and "ValueError: kaboom" in r.output and 'File "boom.py"' in r.output and str(tmp_path.resolve()) not in r.output


def test_a_command_starts_in_the_workspace_and_cannot_read_standard_input(sandbox, ws):
    ws.write_file("where.py", "import os, sys\nprint(sorted(os.listdir('.')))\nprint(repr(sys.stdin.read()))\n")
    r = sandbox.run(ws, "python", ["where.py"])
    assert "['where.py']" in r.output and "''" in r.output.splitlines()[-1]


def test_arguments_reach_the_program_as_plain_text_so_shell_characters_do_nothing(sandbox, ws):
    ws.write_file("args.py", "import sys\nprint(sys.argv[1:])\n")
    r = sandbox.run(ws, "python", ["args.py", "a;b", "&&", "$(whoami)", "`id`", "|", ">", "out.txt", "*"])
    assert r.output.strip() == "['a;b', '&&', '$(whoami)', '`id`', '|', '>', 'out.txt', '*']"
    assert not (ws.root / "out.txt").exists() and ws.list_files() == ["args.py"]


def test_the_readers_work_inside_the_workspace(sandbox, ws):
    ws.write_file("src/a.txt", "one\ntwo\nthree\n")
    assert "src" in sandbox.run(ws, "ls", []).output
    assert sandbox.run(ws, "cat", ["src/a.txt"]).output == "one\ntwo\nthree\n"
    assert sandbox.run(ws, "head", ["-n", "1", "src/a.txt"]).output == "one\n"
    assert sandbox.run(ws, "wc", ["-l", "src/a.txt"]).output.split()[0] == "3"
    assert "two" in sandbox.run(ws, "grep", ["-n", "two", "src/a.txt"]).output


def test_diff_and_find_look_at_files_and_a_dangerous_find_never_starts(sandbox, ws):
    ws.write_file("a.txt", "one\ntwo\n")
    ws.write_file("b.txt", "one\nTWO\n")
    ws.write_file("src/keep.py", "x = 1\n")
    d = sandbox.run(ws, "diff", ["a.txt", "b.txt"])
    assert d.status == "ran" and d.exit_code == 1 and "< two" in d.output and "> TWO" in d.output          # diff exits 1 when files differ: that is an answer, not a failure
    f = sandbox.run(ws, "find", [".", "-name", "*.py"])
    assert f.ok and f.output.split() == ["./src/keep.py"]
    for dangerous in (["-delete"], ["-exec", "rm", "{}", ";"], ["-fprint", "made_by_find.txt"]):
        r = sandbox.run(ws, "find", [".", *dangerous])
        assert r.status == "refused"
    assert sorted(ws.list_files()) == ["a.txt", "b.txt", "src/keep.py"]


def test_find_and_diff_cannot_look_outside_the_workspace_even_with_a_path_we_did_not_foresee(sandbox, ws):
    """The policy refuses an outside path by name. This is the second layer: even a command that reached the program is not allowed to read the app's data."""
    r = sandbox.run(ws, "find", ["/Users", "-maxdepth", "1"])
    assert r.status == "refused" and "must be a path inside the workspace" in r.reason
    r = sandbox.run(ws, "diff", ["/etc/hosts", "/etc/hosts"])
    assert r.status == "refused"


def test_node_check_reports_a_syntax_error_without_running_the_file(sandbox, ws):
    if not any(os.access(f"{d}/node", os.X_OK) for d in ("/usr/bin", "/bin", "/usr/local/bin", "/opt/homebrew/bin")):
        pytest.skip("node is not installed here")
    ws.write_file("good.js", "require('fs').writeFileSync('ran_it.txt', 'x');\n")
    ws.write_file("bad.js", "function (\n")
    ok = sandbox.run(ws, "node", ["--check", "good.js"])
    bad = sandbox.run(ws, "node", ["--check", "bad.js"])
    assert ok.status == "ran" and ok.exit_code == 0 and not (ws.root / "ran_it.txt").exists()          # a check never runs the code
    assert bad.status == "ran" and bad.exit_code != 0 and "SyntaxError" in bad.output


# ---- containment: the operating system, not our checks ------------------------------------------------------------------------------------------

def test_the_network_is_refused_by_the_operating_system(sandbox, ws):
    """Our checks cannot stop an allowed `python` opening a socket. The profile does."""
    ws.write_file("net.py", "import socket\ntry:\n    socket.create_connection(('1.1.1.1', 80), timeout=3)\n    print('REACHABLE')\nexcept PermissionError:\n    print('refused by the OS')\nexcept OSError as e:\n    print('other:', type(e).__name__)\n")
    r = sandbox.run(ws, "python", ["net.py"])
    assert r.output.strip() == "refused by the OS"


def test_every_kind_of_network_use_is_refused(sandbox, ws):
    ws.write_file("net2.py", """\
import socket, urllib.request, http.client
results = {}
def attempt(name, fn):
    try:
        fn(); results[name] = 'REACHED'
    except PermissionError: results[name] = 'refused'
    except Exception as e: results[name] = type(e).__name__
attempt('tcp', lambda: socket.create_connection(('1.1.1.1', 443), timeout=3))
attempt('udp', lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b'x', ('8.8.8.8', 53)))
attempt('dns', lambda: socket.getaddrinfo('example.com', 80))
attempt('http', lambda: urllib.request.urlopen('http://example.com', timeout=3))
attempt('localhost', lambda: socket.create_connection(('127.0.0.1', 8090), timeout=2))
attempt('listen', lambda: socket.socket().bind(('127.0.0.1', 0)))
print(results)
""")
    r = sandbox.run(ws, "python", ["net2.py"])
    assert "REACHED" not in r.output, r.output
    assert "'tcp': 'refused'" in r.output and "'udp': 'refused'" in r.output and "'localhost': 'refused'" in r.output and "'listen': 'refused'" in r.output
    assert "'dns': 'gaierror'" in r.output and "'http': 'URLError'" in r.output                      # name lookup and HTTP fail in their own way, and neither gets an answer


def test_a_child_of_a_child_is_under_the_same_rules(sandbox, ws):
    ws.write_file("deep.py", "import subprocess, sys\nsubprocess.run([sys.executable, '-c', \"import socket\\ntry:\\n    socket.create_connection(('1.1.1.1', 80), timeout=3); print('REACHABLE')\\nexcept PermissionError: print('child refused')\"])\n")
    assert sandbox.run(ws, "python", ["deep.py"]).output.strip() == "child refused"


def test_a_write_outside_the_workspace_is_refused_and_nothing_appears_there(sandbox, ws, tmp_path):
    outside = tmp_path / "outside.txt"
    ws.write_file("out.py", f"from pathlib import Path\ntry:\n    Path({str(outside)!r}).write_text('x'); print('WROTE')\nexcept PermissionError:\n    print('refused')\n")
    r = sandbox.run(ws, "python", ["out.py"])
    assert r.output.strip() == "refused" and not outside.exists()


def test_every_way_of_writing_outside_is_refused(sandbox, ws, tmp_path):
    probes = [Path("/tmp/sdlc_escape_probe.txt"), Path.home() / "should_not_be_here_in_home_xx.txt"]
    for probe in probes:                                                  # a leftover from an earlier broken run must not make this run fail, or hide that it passed
        probe.unlink(missing_ok=True)
    try:
        _every_way_of_writing_outside(sandbox, ws, tmp_path)
    finally:
        for probe in probes:                                              # if containment ever broke, the probe wrote here: never leave it behind
            probe.unlink(missing_ok=True)


def _every_way_of_writing_outside(sandbox, ws, tmp_path):
    victim = tmp_path / "victim"
    victim.mkdir()
    ws.write_file("out2.py", f"""\
import os, pathlib, shutil
v = {str(victim)!r}
results = {{}}
def attempt(name, fn):
    try:
        fn(); results[name] = 'WROTE'
    except PermissionError: results[name] = 'refused'
    except Exception as e: results[name] = type(e).__name__
attempt('write', lambda: open(v + '/a.txt', 'w').write('x'))
attempt('mkdir', lambda: os.mkdir(v + '/d'))
attempt('rename_in', lambda: (open('mine.txt', 'w').write('x'), os.rename('mine.txt', v + '/moved.txt')))
attempt('symlink', lambda: os.symlink('/etc/hosts', v + '/link'))
attempt('chmod', lambda: os.chmod(v, 0o777))
attempt('copy', lambda: shutil.copy('mine.txt', v + '/copy.txt'))
attempt('real_home', lambda: open({str(Path.home() / "should_not_be_here_in_home_xx.txt")!r}, 'w').write('x'))
attempt('tmp', lambda: open('/tmp/sdlc_escape_probe.txt', 'w').write('x'))
print(results)
""")
    r = sandbox.run(ws, "python", ["out2.py"])
    assert "WROTE" not in r.output, r.output
    assert list(victim.iterdir()) == [] and not Path("/tmp/sdlc_escape_probe.txt").exists() and not (Path.home() / "should_not_be_here_in_home_xx.txt").exists()
    assert "'real_home': 'refused'" in r.output


def test_a_write_inside_the_workspace_and_inside_its_scratch_works(sandbox, ws):
    ws.write_file("in.py", "import os\nopen('made.txt', 'w').write('inside')\nopen(os.environ['TMPDIR'] + '/t.txt', 'w').write('scratch')\nprint('ok')\n")
    r = sandbox.run(ws, "python", ["in.py"])
    assert r.output.strip() == "ok" and ws.read_file("made.txt") == "inside"


def test_the_apps_database_env_and_recordings_and_other_projects_cannot_be_read(sandbox, tmp_path):
    base = tmp_path / "workspaces"
    mine, other = Workspace.for_project(base, "mine"), Workspace.for_project(base, "other")
    other.write_file("secret.txt", "the other project's file")
    data = tmp_path / "data"
    data.mkdir()
    (data / "sdlc_workbench.db").write_text("DATABASE")
    (tmp_path / ".env").write_text("IBM_ICA_API_KEY=planted")
    (tmp_path / "recordings").mkdir()
    (tmp_path / "recordings" / "r.json").write_text("RECORDING")
    targets = [str(data / "sdlc_workbench.db"), str(tmp_path / ".env"), str(tmp_path / "recordings" / "r.json"), str(other.root / "secret.txt"), os.path.expanduser("~/.zshrc"), os.path.expanduser("~/.ssh/id_rsa")]
    mine.write_file("peek.py", f"""\
from pathlib import Path
for t in {targets!r}:
    try:
        Path(t).read_bytes(); print('READABLE', t)
    except PermissionError: print('refused')
    except FileNotFoundError: print('refused')
""")
    r = sandbox.run(mine, "python", ["peek.py"])
    assert "READABLE" not in r.output, r.output
    assert r.output.count("refused") == len(targets)


def test_the_system_and_python_remain_readable_so_programs_can_start(sandbox, ws):
    ws.write_file("sys.py", "import json, sqlite3, ssl, asyncio, subprocess, pytest, pathlib\nprint(pathlib.Path('/etc/hosts').exists(), sqlite3.sqlite_version[:1].isdigit())\n")
    assert sandbox.run(ws, "python", ["sys.py"]).output.strip() == "True True"


# ---- the environment -------------------------------------------------------------------------------------------------------------------------------------

def test_planted_secrets_in_the_parents_environment_do_not_reach_the_command(sandbox, ws, monkeypatch):
    for name, value in (("IBM_ICA_API_KEY", "sk-planted-key-123"), ("IBM_ICA_ENDPOINT", "https://planted.invalid"), ("HTTPS_PROXY", "http://proxy.invalid:1"), ("MY_SECRET", "planted-secret")):
        monkeypatch.setenv(name, value)
    ws.write_file("env.py", "import os\nprint(sorted(os.environ))\nprint(os.environ['HOME'] == os.environ['TMPDIR'])\n")
    r = sandbox.run(ws, "python", ["env.py"])
    assert "planted" not in r.output and "IBM" not in r.output and "PROXY" not in r.output and "SECRET" not in r.output and r.output.strip().endswith("True")


# ---- time limit and the tree kill ------------------------------------------------------------------------------------------------------------------------

def test_a_command_past_the_limit_is_stopped_and_says_so(sandbox, ws):
    ws.write_file("sleep.py", "import time\ntime.sleep(30)\n")
    started = time.monotonic()
    r = sandbox.run(ws, "python", ["sleep.py"], Limits(seconds=1))
    assert r.status == "timed_out" and r.exit_code is None and r.limit == "seconds" and "longer than 1 seconds" in r.reason and 0.9 < time.monotonic() - started < 6


def test_a_fast_command_is_not_stopped_by_a_long_limit_and_returns_at_once(sandbox, ws):
    ws.write_file("quick.py", "print('done')\n")
    started = time.monotonic()
    assert sandbox.run(ws, "python", ["quick.py"], Limits(seconds=60)).ok and time.monotonic() - started < 5


def test_a_timeout_leaves_no_process_behind_even_a_grandchild(sandbox, ws):
    ws.write_file("tree.py", "import os, subprocess, sys, time\nchild = subprocess.Popen([sys.executable, '-c', 'import os, subprocess, sys, time\\ngc = subprocess.Popen([sys.executable, \"-c\", \"import os, time, pathlib; pathlib.Path(\\\\\"gc.pid\\\\\").write_text(str(os.getpid())); time.sleep(120)\"])\\nopen(\"child.pid\", \"w\").write(str(os.getpid()))\\ntime.sleep(120)'])\nopen('parent.pid', 'w').write(str(os.getpid()))\ntime.sleep(120)\n")
    r = sandbox.run(ws, "python", ["tree.py"], Limits(seconds=3))
    assert r.status == "timed_out"
    pids = {}
    for name in ("parent", "child", "gc"):
        path = ws.root / f"{name}.pid"
        pids[name] = int(path.read_text()) if path.exists() else None
    started = [p for p in pids.values() if p]
    assert len(started) == 3, f"the test did not manage to start all three processes: {pids}"
    assert all(wait_gone(p) for p in started), {name: alive(p) for name, p in pids.items() if p}


def test_a_command_that_ignores_the_polite_signal_is_killed_hard(sandbox, ws):
    ws.write_file("stubborn.py", "import os, signal, time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\nopen('stubborn.pid', 'w').write(str(os.getpid()))\ntime.sleep(120)\n")
    started = time.monotonic()
    r = sandbox.run(ws, "python", ["stubborn.py"], Limits(seconds=1))
    assert r.status == "timed_out" and 2.5 < time.monotonic() - started < 10
    assert wait_gone(int((ws.root / "stubborn.pid").read_text()))


def test_a_background_process_started_by_a_command_that_finishes_normally_is_not_left_running(sandbox, ws):
    """A test that exits cleanly but left a server or worker behind: the next run must not find it still there."""
    ws.write_file("bg.py", "import subprocess, sys, os\nsubprocess.Popen([sys.executable, '-c', 'import os, time; open(\"bg.pid\", \"w\").write(str(os.getpid())); time.sleep(120)'], start_new_session=False)\nimport time; time.sleep(1)\nprint('parent done')\n")
    r = sandbox.run(ws, "python", ["bg.py"], Limits(seconds=20))
    assert r.ok and "parent done" in r.output
    pid_file = ws.root / "bg.pid"
    if pid_file.exists():
        pid = int(pid_file.read_text())
        assert wait_gone(pid, 5.0), "a background process outlived its command"


def test_a_leftover_that_ignores_the_polite_signal_is_killed_hard_when_its_command_ends_normally(sandbox, ws):
    ws.write_file("stubborn_bg.py", "import subprocess, sys, time\nsubprocess.Popen([sys.executable, '-c', 'import os, signal, time\\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\\nopen(\"sbg.pid\", \"w\").write(str(os.getpid()))\\ntime.sleep(120)'])\ntime.sleep(1)\nprint('parent done')\n")
    r = sandbox.run(ws, "python", ["stubborn_bg.py"], Limits(seconds=20))
    assert r.ok and "parent done" in r.output
    assert wait_gone(int((ws.root / "sbg.pid").read_text()), 6.0), "a leftover that ignores SIGTERM outlived its command"


def test_the_polite_signal_reaches_a_grandchild_so_it_can_clean_up_before_it_is_stopped(sandbox, ws):
    """A timeout signals the whole group politely first. A grandchild that handles SIGTERM gets the chance to write down that it did."""
    ws.write_file("polite.py", "import subprocess, sys, time\nsubprocess.Popen([sys.executable, '-c', 'import os, signal, sys, time\\ndef bye(*a):\\n    open(\"got_term.txt\", \"w\").write(\"yes\")\\n    os._exit(0)\\nsignal.signal(signal.SIGTERM, bye)\\nopen(\"gc.pid\", \"w\").write(str(os.getpid()))\\ntime.sleep(120)'])\ntime.sleep(120)\n")
    r = sandbox.run(ws, "python", ["polite.py"], Limits(seconds=2))
    assert r.status == "timed_out"
    assert wait_gone(int((ws.root / "gc.pid").read_text()))
    assert (ws.root / "got_term.txt").read_text() == "yes"


def test_the_backends_own_process_group_is_never_signalled_even_if_a_command_ends_up_in_it(sandbox, ws, monkeypatch):
    """Signalling our own group would stop the server, its test runner and its shell. If a command is ever started WITHOUT its own session by mistake, the
    runner must stop only that one process. The group signal is RECORDED here instead of sent, so a broken guard fails this test visibly rather than
    stopping the whole run."""
    import subprocess
    from app.sandbox.runner import _own_group, sweep_group
    sent = []
    monkeypatch.setattr(os, "killpg", lambda group, sig: sent.append((group, sig)))
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])               # same group as this test: no new session
    try:
        assert _own_group(os.getpgid(child.pid)) and _own_group(os.getpgrp()) and not _own_group(None) and not _own_group(os.getpgrp() + 1)
        kill_tree(child)
        assert child.poll() is not None                                                           # the command's own process was stopped, alone
        sweep_group(os.getpgrp())                                                                 # sweeping our own group does nothing at all
        assert [entry for entry in sent if entry[0] == os.getpgrp()] == [], f"the backend's own group was signalled: {sent}"
    finally:
        child.kill()
        child.wait()


def test_a_command_that_reads_standard_input_gets_end_of_input_at_once_not_the_backends_terminal(sandbox, ws):
    """pytest points file 0 at /dev/null, so an inherited stdin would look closed. Here file 0 is an OPEN pipe nobody writes to: a command that reads it
    would wait for ever if it were handed the backend's own input, and sees end-of-input straight away if it is handed nothing."""
    ws.write_file("readin.py", "import sys\nprint('got:' + repr(sys.stdin.read()))\n")
    saved = os.dup(0)
    read_end, write_end = os.pipe()
    try:
        os.dup2(read_end, 0)
        started = time.monotonic()
        r = sandbox.run(ws, "python", ["readin.py"], Limits(seconds=8))
        elapsed = time.monotonic() - started
    finally:
        os.dup2(saved, 0)
        for fd in (saved, read_end, write_end):
            os.close(fd)
    assert r.ok and "got:''" in r.output and elapsed < 6


def test_kill_tree_on_an_already_finished_process_does_nothing_and_does_not_raise(sandbox, ws):
    import subprocess
    p = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    p.wait()
    kill_tree(p)


# ---- output ------------------------------------------------------------------------------------------------------------------------------------------------------

def test_output_over_the_cap_is_cut_and_says_so_and_the_command_is_stopped(sandbox, ws):
    ws.write_file("loud.py", "import sys\nwhile True:\n    sys.stdout.write('x' * 1000 + '\\n')\n")
    started = time.monotonic()
    r = sandbox.run(ws, "python", ["loud.py"], Limits(seconds=20, output_bytes=20000))
    assert r.truncated and r.limit == "output_bytes" and len(r.output) <= 20000 and "more than 20000 bytes" in r.reason and time.monotonic() - started < 10


def test_output_exactly_at_the_cap_is_not_cut(sandbox, ws):
    ws.write_file("exact.py", "import sys\nsys.stdout.write('y' * 5000)\n")
    r = sandbox.run(ws, "python", ["exact.py"], Limits(seconds=10, output_bytes=5000))
    assert len(r.output) == 5000 and r.exit_code == 0


def test_invalid_bytes_in_output_do_not_crash_the_runner(sandbox, ws):
    ws.write_file("bytes.py", "import sys\nsys.stdout.buffer.write(b'ok \\xff\\xfe bad \\x80 end\\n')\n")
    r = sandbox.run(ws, "python", ["bytes.py"])
    assert r.ok and "ok" in r.output and "end" in r.output and "\ufffd" in r.output


def test_a_secret_in_a_commands_output_is_removed_before_it_is_returned(sandbox, ws):
    ws.write_file("leak.py", "prefix = 'AKIA'\nsuffix = 'IOSFODNN7EXAMPLE'\nprint('before')\nprint('key is ' + prefix + suffix)\nprint('after')\n")
    r = sandbox.run(ws, "python", ["leak.py"])
    assert AWS not in r.output and r.redacted and "before" in r.output and "after" in r.output and "[a line was removed" in r.output


def test_output_without_a_secret_is_returned_as_it_was(sandbox, ws):
    ws.write_file("fine.py", "print('nothing to hide: jane.doe@acme-corp.co.uk')\n")
    r = sandbox.run(ws, "python", ["fine.py"])
    assert not r.redacted and "nothing to hide" in r.output


# ---- refusals before anything starts ---------------------------------------------------------------------------------------------------------------------------

def test_a_refused_command_never_starts_anything(sandbox, ws):
    for program, args in (("curl", ["http://example.com"]), ("sh", ["-c", "touch /tmp/sdlc_should_not_exist"]), ("pip", ["install", "requests"]), ("python", ["-c", "print(1)"])):
        r = sandbox.run(ws, program, args)
        assert r.status == "refused" and r.exit_code is None and r.output == "" and r.reason and r.seconds == 0.0
    assert not Path("/tmp/sdlc_should_not_exist").exists()


def test_without_the_protection_nothing_is_run_at_all(ws):
    broken = Sandbox(sandbox_exec="/nonexistent/sandbox-exec")
    ws.write_file("hello.py", "open('proof.txt', 'w').write('it ran')\n")
    r = broken.run(ws, "python", ["hello.py"])
    assert r.status == "unavailable" and r.exit_code is None and "no command will be run" in r.reason
    assert not (ws.root / "proof.txt").exists()
    assert broken.run(ws, "python", ["hello.py"]).status == "unavailable"                  # remembered, not retried into a different answer


def test_a_protection_that_does_not_protect_runs_nothing_either(tmp_path, ws):
    fake = tmp_path / "pretend-sandbox-exec"
    fake.write_text('#!/bin/sh\nshift 2\nexec "$@"\n')
    fake.chmod(0o755)
    ws.write_file("hello.py", "open('proof.txt', 'w').write('it ran')\n")
    r = Sandbox(sandbox_exec=str(fake)).run(ws, "python", ["hello.py"])
    assert r.status == "unavailable" and "self-test failed" in r.reason and not (ws.root / "proof.txt").exists()


def test_the_self_test_is_done_once_and_not_for_every_command(ws, monkeypatch):
    calls = []
    real = OS.self_test
    monkeypatch.setattr("app.sandbox.runner.OS.self_test", lambda *a, **k: (calls.append(1), real(*a, **k))[1])
    box = Sandbox()
    ws.write_file("a.py", "print(1)\n")
    for _ in range(3):
        assert box.run(ws, "python", ["a.py"]).ok
    assert len(calls) == 1


def test_scratch_folders_are_removed_after_each_command(sandbox, ws):
    import tempfile
    before = {p.name for p in Path(tempfile.gettempdir()).glob("sdlc_scratch_*")}
    ws.write_file("a.py", "print(1)\n")
    for _ in range(3):
        sandbox.run(ws, "python", ["a.py"])
    sandbox.run(ws, "python", ["missing.py"])
    assert {p.name for p in Path(tempfile.gettempdir()).glob("sdlc_scratch_*")} - before == set()


# ---- limits on processes ------------------------------------------------------------------------------------------------------------------------------------------

def test_a_fork_bomb_is_stopped_by_the_process_ceiling_and_nothing_is_left(sandbox, ws):
    ws.write_file("bomb.py", "import os, time\nn = 0\nwhile True:\n    try:\n        pid = os.fork()\n    except OSError:\n        print('fork refused after', n); break\n    if pid == 0:\n        time.sleep(3); os._exit(0)\n    n += 1\n    if n > 600:\n        print('NOT STOPPED'); break\n")
    before = current_processes()
    r = sandbox.run(ws, "python", ["bomb.py"], Limits(seconds=20, max_processes=30))
    assert "fork refused after" in r.output and "NOT STOPPED" not in r.output, r.output
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and current_processes() > before + 5:
        time.sleep(0.2)
    assert current_processes() <= before + 5


def test_the_ceiling_is_relative_to_the_processes_the_user_already_has(sandbox, ws):
    """On a busy machine an absolute cap of 64 would stop a command starting even one child. Measured: 389 processes were running when this was written."""
    assert current_processes() > 20
    ws.write_file("spawn.py", "import subprocess, sys\nr = subprocess.run([sys.executable, '-c', 'print(1)'], capture_output=True, text=True)\nprint('child said', r.stdout.strip())\n")
    assert sandbox.run(ws, "python", ["spawn.py"], Limits(seconds=20, max_processes=64)).output.strip() == "child said 1"


# ---- the tests, read from the real run ---------------------------------------------------------------------------------------------------------------------------------

def write(ws: Workspace, **files: str) -> None:
    for name, text in files.items():
        ws.write_file(name.replace("__", "/").replace("_py", ".py") if name.endswith("_py") else name, text)


def test_a_passing_project_is_all_passed(sandbox, ws):
    ws.write_file("test_a.py", "def test_1(): assert True\ndef test_2(): assert 1 == 1\n")
    r = run_tests(sandbox, ws)
    assert (r.status, r.exit_code, r.passed, r.failed, r.errors, r.skipped) == ("ran", 0, 2, 0, 0, 0) and r.all_passed and r.total == 2 and r.seconds >= 0


def test_a_test_run_leaves_no_cache_folder_behind_to_count_against_the_workspace(sandbox, ws):
    ws.write_file("test_a.py", "def test_1(): assert False\n")                                      # a failing run is the one that would write pytest's last-failed cache
    run_tests(sandbox, ws)
    assert ws.list_files() == ["test_a.py"] and not (ws.root / ".pytest_cache").exists()


def test_a_mixed_project_has_the_counts_a_hand_count_gives(sandbox, ws):
    ws.write_file("test_m.py", 'import pytest\ndef test_ok(): pass\ndef test_ok2(): pass\ndef test_bad(): assert 1+1==3, "math"\ndef test_boom(): raise ValueError("boom")\n'
                               '@pytest.mark.skip(reason="x")\ndef test_s(): pass\n@pytest.mark.xfail\ndef test_xf(): assert False\n@pytest.mark.xfail\ndef test_xp(): pass\n'
                               '@pytest.fixture\ndef broken(): raise RuntimeError("fix")\ndef test_err(broken): pass\n')
    r = run_tests(sandbox, ws)
    assert (r.status, r.exit_code, r.passed, r.failed, r.errors, r.skipped, r.xfailed, r.xpassed) == ("ran", 1, 2, 2, 1, 1, 1, 1) and r.total == 8 and not r.all_passed
    assert sorted((f.kind, f.test, f.message) for f in r.failures) == [
        ("error", "test_m.py::test_err", "RuntimeError: fix"), ("failed", "test_m.py::test_bad", "AssertionError: math"), ("failed", "test_m.py::test_boom", "ValueError: boom")]
    assert set(r.passed_names) == {"test_m.py::test_ok", "test_m.py::test_ok2"}


def test_a_project_with_no_tests_is_not_a_pass(sandbox, ws):
    ws.write_file("helper.py", "x = 1\n")
    r = run_tests(sandbox, ws)
    assert (r.status, r.exit_code, r.total) == ("no_tests", 5, 0) and not r.all_passed


def test_an_import_error_in_a_test_file_is_a_collection_error_with_the_reason(sandbox, ws):
    ws.write_file("test_i.py", "import nonexistent_module_xyz\ndef test_a(): pass\n")
    r = run_tests(sandbox, ws)
    assert r.status == "collection_error" and r.exit_code == 2 and not r.all_passed
    assert [(f.kind, f.test, f.message) for f in r.failures] == [("error", "test_i.py", "ModuleNotFoundError: No module named 'nonexistent_module_xyz'")]


def test_a_syntax_error_is_a_collection_error_too(sandbox, ws):
    ws.write_file("test_s.py", "def test_a(:\n    pass\n")
    r = run_tests(sandbox, ws)
    assert r.status == "collection_error" and r.errors == 1 and "SyntaxError" in r.failures[0].message


def test_a_crash_of_pytest_itself_is_a_crash_not_zero_failures(sandbox, ws):
    ws.write_file("conftest.py", "import os\nos._exit(7)\n")
    ws.write_file("test_c.py", "def test_a(): pass\n")
    r = run_tests(sandbox, ws)
    assert r.status == "crashed" and r.exit_code == 7 and r.failed == 0 and not r.all_passed


def test_a_slow_test_run_times_out_and_is_reported_as_that(sandbox, ws):
    ws.write_file("test_t.py", "import time\ndef test_slow(): time.sleep(30)\n")
    r = run_tests(sandbox, ws, limits=Limits(seconds=2))
    assert r.status == "timed_out" and r.exit_code is None and r.passed == 0 and not r.all_passed


def test_a_run_that_prints_forever_is_cut_off_and_reported_as_that(sandbox, ws):
    ws.write_file("conftest.py", "import sys\ndef pytest_collection_finish(session):\n    while True:\n        sys.__stdout__.write('x' * 1000 + '\\n')\n")
    ws.write_file("test_l.py", "def test_a(): pass\n")
    r = run_tests(sandbox, ws, limits=Limits(seconds=20, output_bytes=30000))
    assert r.status == "cut_off" and not r.all_passed


def test_a_parametrised_failure_names_its_parameter(sandbox, ws):
    ws.write_file("test_p.py", "import pytest\n@pytest.mark.parametrize('n', [1, 2, 3])\ndef test_p(n): assert n != 2\n")
    r = run_tests(sandbox, ws)
    assert (r.passed, r.failed) == (2, 1) and r.failures[0].test == "test_p.py::test_p[2]"


def test_one_test_file_can_be_run_alone_and_a_path_outside_is_refused(sandbox, ws):
    ws.write_file("test_a.py", "def test_a(): pass\n")
    ws.write_file("test_b.py", "def test_b(): assert False\n")
    assert run_tests(sandbox, ws, "test_a.py").all_passed
    assert run_tests(sandbox, ws, "test_b.py").failed == 1
    from app.sandbox.errors import PathRefused
    for bad in ("../x", "/etc", "missing.py"):
        with pytest.raises(PathRefused):
            run_tests(sandbox, ws, bad)


def test_tests_that_try_the_network_fail_and_do_not_reach_it(sandbox, ws):
    ws.write_file("test_net.py", "import socket\ndef test_net():\n    socket.create_connection(('1.1.1.1', 80), timeout=3)\n")
    r = run_tests(sandbox, ws)
    assert r.failed == 1 and "PermissionError" in r.failures[0].message


def test_tests_that_import_the_workspaces_own_code_work(sandbox, ws):
    ws.write_file("src/__init__.py", "")
    ws.write_file("src/calc.py", "def add(a, b):\n    return a + b\n")
    ws.write_file("test_calc.py", "from src.calc import add\ndef test_add(): assert add(2, 3) == 5\n")
    assert run_tests(sandbox, ws).all_passed


def test_the_real_location_never_appears_in_a_failure(sandbox, ws, tmp_path):
    ws.write_file("test_f.py", "def test_f(): assert False, 'nope'\n")
    r = run_tests(sandbox, ws)
    assert str(tmp_path.resolve()) not in repr(r) and "/private/var" not in repr(r)


# ---- the service, the audit trail, two projects ----------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def service(tmp_path, sandbox):
    settings = Settings(_env_file=None, data_dir=str(tmp_path / "data"), recordings_dir=str(tmp_path / "rec"))
    store = Store.open(tmp_path / "db" / "t.db", limits=settings.context_limits)
    project = store.projects.create(name="P", brief="", actor="system")
    other = store.projects.create(name="Q", brief="", actor="system")
    return SandboxService(settings, store, Scanner(), sandbox), project, other


def audit(service, project):
    return [(a.action, a.target_id, a.detail) for a in service.store.audit.list(project.id) if a.action.startswith("sandbox.")]


def test_a_workspace_lives_under_the_data_folder_one_per_project(service, tmp_path):
    svc, project, other = service
    svc.write_file(project.id, "a.txt", "mine", actor="human:Ann")
    svc.write_file(other.id, "a.txt", "theirs", actor="human:Ann")
    assert (tmp_path / "data" / "workspaces" / project.id / "a.txt").read_text() == "mine"
    assert svc.read_file(project.id, "a.txt") == "mine" and svc.read_file(other.id, "a.txt") == "theirs"


def test_an_unknown_project_gets_no_workspace_and_no_folder(service, tmp_path):
    from app.models import NotFoundError
    from app.sandbox.errors import PathRefused
    svc, *_ = service
    with pytest.raises(NotFoundError):
        svc.write_file("nosuchproject", "a.txt", "x", actor="human:Ann")
    assert not (tmp_path / "data" / "workspaces" / "nosuchproject").exists()
    for bad in ("../x", "a/b", ""):
        with pytest.raises(PathRefused):
            svc.write_file(bad, "a.txt", "x", actor="human:Ann")


def test_each_write_and_delete_is_one_audit_row_with_no_contents(service):
    svc, project, _ = service
    svc.write_file(project.id, "src/a.py", "SECRET-LOOKING-BUT-NOT-A-SECRET contents", actor="human:Ann")
    svc.delete_file(project.id, "src/a.py", actor="human:Ann")
    rows = audit(svc, project)
    assert [(a, t) for a, t, _ in rows] == [("sandbox.file_written", "src/a.py"), ("sandbox.file_deleted", "src/a.py")]
    assert rows[0][2] == {"bytes": 40} and "contents" not in repr(rows)


def test_a_refused_write_is_audited_as_refused_with_the_reason_and_not_the_contents(service):
    from app.sandbox.errors import ContentRefused, PathRefused
    svc, project, _ = service
    with pytest.raises(PathRefused):
        svc.write_file(project.id, "../escape.py", "x", actor="human:Ann")
    with pytest.raises(ContentRefused):
        svc.write_file(project.id, "k.py", f"KEY = '{AWS}'", actor="human:Ann")
    rows = audit(svc, project)
    assert [a for a, _, _ in rows] == ["sandbox.file_refused", "sandbox.file_refused"] and AWS not in repr(rows)
    assert rows[0][2]["reason"] == "a path cannot go up with '..'" and rows[0][2]["op"] == "write"


def test_a_refused_path_with_control_characters_or_nothing_is_logged_as_plain_safe_text(service):
    from app.sandbox.errors import PathRefused
    svc, project, _ = service
    for bad in ("a\x1b[31mb.py", "line\nbreak.py", "café.py", ""):
        with pytest.raises(PathRefused):
            svc.write_file(project.id, bad, "x", actor="human:Ann")
    targets = [t for _, t, _ in audit(svc, project)]
    assert targets == ["a?[31mb.py", "line?break.py", "caf?.py", "(empty)"]


def test_each_command_is_one_audit_row_with_its_outcome_and_no_output(service):
    svc, project, _ = service
    svc.write_file(project.id, "hello.py", "print('SOME OUTPUT')\n", actor="human:Ann")
    svc.run_command(project.id, "python", ["hello.py"], actor="human:Ann")
    svc.run_command(project.id, "curl", ["http://example.com"], actor="human:Ann")
    rows = audit(svc, project)[1:]
    assert [a for a, _, _ in rows] == ["sandbox.command_run", "sandbox.command_refused"]
    assert rows[0][1] == "python hello.py" and rows[0][2]["status"] == "ran" and rows[0][2]["exit_code"] == 0 and "SOME OUTPUT" not in repr(rows)
    assert rows[1][2]["status"] == "refused" and "allow-list" in rows[1][2]["reason"]


def test_a_test_run_is_audited_with_its_counts(service):
    svc, project, _ = service
    svc.write_file(project.id, "test_a.py", "def test_a(): pass\ndef test_b(): assert False\n", actor="human:Ann")
    report = svc.run_tests(project.id, actor="human:Ann")
    [(action, target, detail)] = [r for r in audit(svc, project) if r[0] == "sandbox.tests_run"]
    assert (report.passed, report.failed) == (1, 1) and target == "all"
    assert detail == {"status": "ran", "passed": 1, "failed": 1, "errors": 0, "skipped": 0, "exit_code": 1}


def test_two_projects_commands_cannot_see_each_others_files(service):
    svc, project, other = service
    svc.write_file(other.id, "secret.txt", "the other project's", actor="human:Ann")
    svc.write_file(project.id, "peek.py", f"import glob\nprint(glob.glob('../*/*'), glob.glob('../**/secret.txt', recursive=True))\n", actor="human:Ann")
    r = svc.run_command(project.id, "python", ["peek.py"], actor="human:Ann")
    assert "secret.txt" not in r.output


def test_an_agent_cannot_name_the_actor_it_acts_as_anything_it_likes(service):
    from app.models import InvalidInput
    svc, project, _ = service
    with pytest.raises(InvalidInput):
        svc.write_file(project.id, "a.txt", "x", actor="not a valid actor")
