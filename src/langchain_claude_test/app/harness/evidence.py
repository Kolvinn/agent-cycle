"""The executor behind ``attach_finding`` — one read-only command, fenced.

*"attach finding by piping a bash or read command into the tool. The tool
would match against allowed tools and read files that session and then use the
tool to extract the information and place it in the graph itself. This avoids
having the agent retype everything."*

The whole of its safety is here: an allow-list of executables, no shell (the
command is split, never interpreted), no pipes, redirects or chaining, no path
outside the working directory, a timeout, and an output cap. ``Bash`` itself
stays off every frame's surface.
"""

from __future__ import annotations

import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

#: Executable -> the class it is priced as (kept for the record; attach_finding is free).
ALLOWED: dict[str, str] = {
    "cat": "read",
    "head": "read",
    "tail": "read",
    "sed": "read",
    "grep": "survey",
    "rg": "survey",
    "ls": "survey",
    "find": "survey",
    "wc": "survey",
    "git": "read",
}

GIT_READONLY = frozenset({"log", "show", "blame", "diff", "status", "ls-files", "grep"})
FIND_FORBIDDEN = frozenset({"-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprintf", "-fls"})
_SED_PRINT = re.compile(r"^\d+(,\d+)?p$")
_META = re.compile(r"[|;&<>`$()\n]")

MAX_LINES = 80
MAX_BYTES = 6000
TIMEOUT_S = 20


@dataclass(frozen=True, slots=True)
class Plan:
    argv: tuple[str, ...]
    klass: str


@dataclass(frozen=True, slots=True)
class Output:
    text: str
    truncated: bool
    returncode: int


def plan(command: str, cwd: Path) -> Plan | str:
    """The argv to run, or the refusal to give the model."""
    if _META.search(command):
        return "REFUSED: one command only — no pipes, redirects, chaining, substitution or newlines."
    try:
        argv = shlex.split(command)
    except ValueError as exc:
        return f"REFUSED: could not parse the command ({exc})."
    if not argv:
        return "REFUSED: empty command."
    exe = Path(argv[0]).name
    if exe not in ALLOWED:
        return f"REFUSED: {exe!r} is not an allowed command. Allowed: {', '.join(sorted(ALLOWED))}."
    if exe == "git":
        if len(argv) < 2 or argv[1] not in GIT_READONLY:
            return f"REFUSED: git is read-only here: {', '.join(sorted(GIT_READONLY))}."
    if exe == "sed":
        scripts = [a for a in argv[1:] if not a.startswith("-") and _SED_PRINT.match(a)]
        if "-n" not in argv or not scripts:
            return "REFUSED: sed may only print a range: sed -n '10,40p' <file>."
        if any(a.startswith("-i") for a in argv):
            return "REFUSED: sed -i writes; only -n with a print range is allowed."
    if exe == "find" and any(a in FIND_FORBIDDEN for a in argv):
        return "REFUSED: find may not execute, delete or write."
    root = Path(cwd).resolve()
    for arg in argv[1:]:
        if arg.startswith("-"):
            continue
        candidate = (root / arg).resolve() if not arg.startswith("/") else Path(arg).resolve()
        if arg.startswith("/") or ".." in Path(arg).parts:
            if root not in candidate.parents and candidate != root:
                return f"REFUSED: {arg!r} is outside the working directory."
    return Plan(argv=tuple([exe, *argv[1:]]), klass=ALLOWED[exe])


def cap(text: str) -> tuple[str, bool]:
    lines = text.splitlines()
    truncated = False
    if len(lines) > MAX_LINES:
        dropped = len(lines) - MAX_LINES
        lines = lines[:MAX_LINES] + [f"… {dropped} more lines not kept"]
        truncated = True
    out = "\n".join(lines)
    if len(out.encode()) > MAX_BYTES:
        out = out.encode()[:MAX_BYTES].decode(errors="ignore") + "\n… output cut at 6 KB"
        truncated = True
    return out, truncated


def execute(planned: Plan, cwd: Path) -> Output:
    try:
        proc = subprocess.run(
            list(planned.argv),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=TIMEOUT_S,
            check=False,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return Output(text=f"(timed out after {TIMEOUT_S}s)", truncated=True, returncode=-1)
    except FileNotFoundError:
        return Output(text=f"({planned.argv[0]} is not installed here)", truncated=False, returncode=-1)
    text = proc.stdout if proc.stdout else proc.stderr
    kept, truncated = cap(text)
    return Output(text=kept, truncated=truncated, returncode=proc.returncode)


def run_command(command: str, cwd: Path) -> Output | str:
    """Plan and run. A refusal comes back as text; nothing ran."""
    planned = plan(command, cwd)
    if isinstance(planned, str):
        return planned
    return execute(planned, cwd)
