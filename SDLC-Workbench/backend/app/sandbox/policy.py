"""Which programs a command may run, with which arguments, and what environment it sees (S16).

A command is a PROGRAM and a LIST of arguments, never one string through a shell: `;`, `&&`, `|`, `$()` and backticks are ordinary text to a program, so
they cannot chain anything. The allow-list is by name. Installing packages is refused outright, because it needs the network and the sandbox has none.

This module only decides yes or no and builds the environment. It does not run anything, and it is NOT the protection against a hostile program: that
is the operating-system profile (profile.py). These checks stop a mistake early with a sentence a person or an agent can act on.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .errors import CommandRefused

MAX_ARGS = 40
MAX_ARG_CHARS = 2000

# Programs that read files and print. Their arguments are file paths inside the workspace.
READERS = ("ls", "cat", "head", "tail", "wc", "grep", "diff")
# `find` can also run programs, delete and write files; only these words do that, and each is refused (everything else it does is looking).
FIND_REFUSED = ("-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls")
PYTHON_NAMES = ("python", "python3")
NODE_SCRIPTS = ("test", "run", "build")
INSTALLERS = {"install", "i", "add", "ci", "update", "upgrade", "uninstall", "remove", "download", "wheel", "publish", "login", "config"}
_SAFE_ARG = re.compile(r"^[^\x00\n\r]*$")
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# The only variables a command sees. The app's own variables (keys, endpoints, proxies) are never among them.
ENV_ALLOWED = ("LANG", "LC_ALL", "TZ")


@dataclass(frozen=True)
class Command:
    """A checked command: the program as the caller named it, the real executable to start, and the arguments."""
    name: str
    executable: str
    args: tuple[str, ...]

    @property
    def argv(self) -> list[str]:
        return [self.executable, *self.args]


def python_executable() -> str:
    """The interpreter of the shared venv, the only Python a command may start."""
    return str(Path(sys.executable).absolute())


def venv_bin() -> str:
    return str(Path(python_executable()).parent)


def _find(name: str) -> str:
    for folder in ("/usr/bin", "/bin", "/usr/local/bin", "/opt/homebrew/bin"):
        candidate = Path(folder) / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise CommandRefused(f"'{name}' is not installed on this machine")


def check_args(args: Sequence[str]) -> tuple[str, ...]:
    if isinstance(args, str):
        raise CommandRefused("give the arguments as a list, not one string: there is no shell to split it")
    if len(args) > MAX_ARGS:
        raise CommandRefused(f"a command is limited to {MAX_ARGS} arguments")
    out = []
    for arg in args:
        if not isinstance(arg, str):
            raise CommandRefused("every argument must be text")
        if len(arg) > MAX_ARG_CHARS:
            raise CommandRefused(f"an argument is limited to {MAX_ARG_CHARS} characters")
        if not _SAFE_ARG.match(arg):
            raise CommandRefused("an argument cannot hold a NUL byte or a line break")
        out.append(arg)
    return tuple(out)


def _path_arg(arg: str, what: str) -> None:
    """A file argument must be a plain relative path inside the workspace (the OS profile enforces it again for anything we did not foresee)."""
    if arg.startswith("-"):
        return
    if arg.startswith(("/", "~")) or ".." in arg.split("/") or re.match(r"^[A-Za-z]:", arg) or "\\" in arg:
        raise CommandRefused(f"{what}: '{arg}' must be a path inside the workspace, like 'src/app.py'")


def check_command(program: str, args: Sequence[str]) -> Command:
    """The command, if it is allowed; CommandRefused with the reason if not."""
    if not isinstance(program, str) or not program.strip():
        raise CommandRefused("name the program to run")
    if "/" in program or "\\" in program or program != program.strip():
        raise CommandRefused("name a program, not a path: only the programs on the allow-list can run")  # the message is the point: the allow-list would refuse it anyway
    arguments = check_args(args)
    first = arguments[0] if arguments else ""

    if program in PYTHON_NAMES:
        _python(arguments)
        return Command(program, python_executable(), arguments)
    if program == "pytest":
        for arg in arguments:
            _path_arg(arg, "pytest")
        return Command(program, python_executable(), ("-m", "pytest", *arguments))
    if program == "pip":
        if first not in ("list", "--version", "show", "freeze") or any(a.startswith("--index") or a.startswith("--extra-index") or a in ("-i", "--find-links", "-f") for a in arguments):
            raise CommandRefused("pip can only list what is installed: installing needs the network, and the sandbox has none")
        return Command(program, python_executable(), ("-m", "pip", *arguments))
    if program in ("node", "npm"):
        return _node(program, arguments)
    if program in READERS:
        for arg in arguments:
            _path_arg(arg, program)
        return Command(program, _find(program), arguments)
    if program == "find":
        for arg in arguments:
            if arg in FIND_REFUSED:
                raise CommandRefused(f"find {arg} is not allowed: find may only look, not run programs or change files")
            _path_arg(arg, "find")
        return Command(program, _find(program), arguments)
    raise CommandRefused(f"'{program}' is not on the allow-list; allowed: python, pytest, pip (list only), node (a script, or --check), npm (test, run, build), {', '.join(READERS)}, find (look only)")


def _python(arguments: tuple[str, ...]) -> None:
    if not arguments:
        raise CommandRefused("python needs a script or '-m module' to run")
    if arguments[0] in ("-c", "-i", "-") or arguments[0].startswith("-c"):
        raise CommandRefused("python -c, -i and reading from the terminal are not allowed: write the code to a file and run the file")
    if arguments[0] == "-m":
        if len(arguments) < 2:
            raise CommandRefused("python -m needs a module name")
        if arguments[1] in ("pip", "ensurepip", "venv", "http.server", "ftplib", "smtpd", "telnetlib", "webbrowser", "idlelib", "code", "pdb", "pydoc"):
            raise CommandRefused(f"python -m {arguments[1]} is not allowed in the sandbox")
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_.]*$", arguments[1]):
            raise CommandRefused("python -m needs a plain module name")
        return
    if arguments[0].startswith("-"):
        raise CommandRefused(f"python option '{arguments[0]}' is not allowed; give a script path, or '-m module'")
    _path_arg(arguments[0], "python")


def _node(program: str, arguments: tuple[str, ...]) -> Command:
    if program == "npm":
        if not arguments or arguments[0] not in NODE_SCRIPTS:
            raise CommandRefused("npm can only run 'test', 'run <script>' or 'build': installing needs the network, and the sandbox has none")
        if arguments[0] == "run" and (len(arguments) < 2 or not re.match(r"^[A-Za-z0-9:_-]+$", arguments[1])):
            raise CommandRefused("npm run needs a plain script name")
        return Command(program, _find_node("npm"), arguments)
    if arguments[:1] in (("--check",), ("-c",)):                    # a syntax check reads one file and runs nothing
        if len(arguments) != 2 or arguments[1].startswith("-"):
            raise CommandRefused("node --check needs exactly one script path inside the workspace")
        _path_arg(arguments[1], "node")
        return Command(program, _find_node("node"), arguments)
    if not arguments or arguments[0].startswith("-"):
        raise CommandRefused("node needs a script path inside the workspace")
    _path_arg(arguments[0], "node")
    return Command(program, _find_node("node"), arguments)


def _find_node(name: str) -> str:
    try:
        return _find(name)
    except CommandRefused:
        raise CommandRefused(f"{name} is not installed on this machine, so it cannot be run")


def clean_environment(scratch: str) -> dict[str, str]:
    """What a command sees. Only these variables: nothing the app was started with (keys, endpoints, proxies) gets through."""
    env = {
        "PATH": f"{venv_bin()}:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "HOME": scratch,
        "TMPDIR": scratch,
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "PYTHONNOUSERSITE": "1",
        "PYTHONUNBUFFERED": "1",
        "PIP_NO_INDEX": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "NO_COLOR": "1",
    }
    for name in ENV_ALLOWED:
        value = os.environ.get(name)
        if value and _ENV_NAME.match(name):
            env[name] = value
    return env
