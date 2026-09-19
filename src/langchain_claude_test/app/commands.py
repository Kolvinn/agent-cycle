"""The / commands — the shell's control surface.

*"this app will centre around me doing / commands (or similar) to switch
graph entry points, which also control the system prompt as well if needed."*

Two kinds of command, one namespace:

- **mode commands** come from ``modes.toml``: ``/graph`` enters the cycle,
  ``/chat`` returns to the default connection, and any other mode the file
  defines (``/reviewer``, ``/agent``) switches the plain connection's system
  prompt and tool surface. They are data.
- **built-ins** manage sessions and the run: ``/new``, ``/sessions``,
  ``/resume``, ``/fork``, ``/interrupt``, ``/model``, ``/show``, ``/help``,
  ``/quit``.

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
    "model": "/model <alias> — set the model for new turns (sonnet, opus, haiku, or a full id)",
    "show": "/show graph|package|state|budget — inspect what the graph holds",
    "modes": "/modes — list the modes the / commands can switch to",
    "help": "/help — this list",
    "quit": "/quit — leave",
}

#: Passed straight through to the SDK conversation in a chat mode.
PASSTHROUGH: frozenset[str] = frozenset({"compact", "context", "cost", "usage", "clear", "status"})


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
            extra = " — enters the provenance cycle; /graph <query> starts one" if m.kind == "graph" else ""
            lines.append(f"  /{name}{extra}{(' — ' + m.description) if m.description and not extra else ''}")
        lines.append("")
        lines.append("Built-ins:")
        lines += [f"  {text}" for text in BUILTINS.values()]
        lines.append("")
        lines.append("Passed to the conversation in a chat mode: " + ", ".join(f"/{c}" for c in sorted(PASSTHROUGH)))
        lines.append("Plain text goes to the focused mode: the chat, or the synthesis conversation when the focus is the graph.")
        return "\n".join(lines)
