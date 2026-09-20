"""The / commands — the shell's control surface.

*"this app will centre around me doing / commands (or similar) to switch
graph entry points, which also control the system prompt as well if needed."*

Two kinds of command, one namespace:

- **mode commands** come from ``modes.toml``: ``/graph`` enters the cycle,
  ``/chat`` returns to the default connection, and any other mode the file
  defines (``/reviewer``, ``/agent``) switches the plain connection's system
  prompt and tool surface. They are data.
- **built-ins** manage sessions and the run: ``/new``, ``/sessions``,
  ``/resume``, ``/fork``, ``/interrupt``, ``/model``, ``/effort``, ``/panel``,
  ``/show``, ``/help``, ``/quit``.

Anything else that starts with ``/`` is passed to the SDK conversation when
the focus is a chat mode — the CLI runs its own built-ins (``/compact``,
``/context``, ``/cost``) as ordinary prompts — and is refused in the graph,
which has no live conversation between turns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .config import Modes


@dataclass(frozen=True, slots=True)
class Command:
    name: str
    args: str
    raw: str


BUILTINS: Mapping[str, str] = {
    "new": "/new [name] — start a new session (and switch to it)",
    "sessions": "/sessions — list sessions",
    "resume": "/resume <name> — open a session",
    "fork": "/fork [name] — copy the current session, graph state and all, into a new one",
    "interrupt": "/interrupt — stop the turn in flight (also Esc)",
    "model": "/model [alias] — pick from the CLI's own model list, or set one directly (sonnet, opus, haiku, default, a full id)",
    "effort": "/effort [level] — pick the effort level (low, medium, high, xhigh, max)",
    "panel": "/panel [show|hide|<width>|view outline|kind|status] — the graph browser (ctrl+g toggles, ctrl+b cycles the view, ctrl+left/right resize; select a node to see it in full)",
    "copy": "/copy [last|tool|user] — the last assistant message, tool result (in full) or message of yours, to the clipboard; ctrl+c copies a mouse selection instead",
    "expand": "/expand [n] — show a tool result in full instead of its first 24 lines; n counts back from the last (ctrl+o does the last)",
    "wipe": "/wipe — clear the transcript on screen and nothing else (ctrl+l); /clear goes to the conversation instead",
    "show": "/show graph|package|budget|state | node <id> | neighbours <id> [depth] | search <text> — inspect the graph",
    "budget": "/budget [<field> <n> | reset] — the cycle's caps (per_assumption, antithesis_base, orientation_base, synthesis_points, max_assumptions …); no args lists them",
    "prices": "/prices [<class> <n> | reset] — what a tool call costs by class (survey, read, webfetch); no args lists them",
    "modes": "/modes — list the modes the / commands can switch to",
    "help": "/help — this list",
    "quit": "/quit — leave",
}

#: Passed straight through to the SDK conversation in a chat mode.
PASSTHROUGH: frozenset[str] = frozenset({"compact", "context", "cost", "usage", "clear", "status"})

#: Commands that answer out of what the shell already holds: no model turn,
#: no SDK client, no session record written. They run *beside* a turn instead
#: of queueing behind it — *"it needs to be smooth and versitile enought to
#: not interrupt workflwo."* Everything else keeps its place in the one queue
#: on the one task that owns the clients.
READ_ONLY: frozenset[str] = frozenset({"show", "panel", "sessions", "help", "modes", "copy", "expand", "wipe"})

#: These write when they are given an argument and only print without one, so
#: only the printing form takes the read-only lane.
READ_ONLY_WITHOUT_ARGS: frozenset[str] = frozenset({"budget", "prices"})


def is_read_only(command: Command) -> bool:
    """Can this command be answered beside a turn in flight?"""
    if command.name in READ_ONLY:
        return True
    return command.name in READ_ONLY_WITHOUT_ARGS and not command.args


def parse(text: str) -> Command | None:
    """A command if the message starts with ``/``; otherwise ``None``."""
    stripped = text.strip()
    if not stripped.startswith("/") or stripped.startswith("//"):
        return None
    head, _, rest = stripped[1:].partition(" ")
    if not head:
        return None
    return Command(name=head.lower(), args=rest.strip(), raw=stripped)


class CommandSet:
    """What ``/`` can be followed by in this shell."""

    def __init__(self, modes: Modes) -> None:
        self.modes = modes

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(set(BUILTINS) | set(self.modes.names()) | PASSTHROUGH))

    def suggestions(self) -> tuple[str, ...]:
        return tuple(f"/{n}" for n in self.names())

    def is_mode(self, name: str) -> bool:
        return name in self.modes

    def is_builtin(self, name: str) -> bool:
        return name in BUILTINS

    def is_passthrough(self, name: str) -> bool:
        return name in PASSTHROUGH

    def help_text(self) -> str:
        lines = ["Modes (from modes.toml):"]
        for name in self.modes.names():
            m = self.modes[name]
            extra = " — enters the provenance cycle; /graph <query> starts one, /graph alone resumes an interrupted one" if m.kind == "graph" else ""
            lines.append(f"  /{name}{extra}{(' — ' + m.description) if m.description and not extra else ''}")
        lines.append("")
        lines.append("Built-ins:")
        lines += [f"  {text}" for text in BUILTINS.values()]
        lines.append("")
        lines.append("Passed to the conversation in a chat mode: " + ", ".join(f"/{c}" for c in sorted(PASSTHROUGH)))
        lines.append("Plain text goes to the focused mode: the chat, or the synthesis conversation when the focus is the graph.")
        return "\n".join(lines)
