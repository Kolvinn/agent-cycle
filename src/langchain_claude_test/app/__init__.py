"""The application — a Claude shell whose commands switch between a plain Claude
connection and the provenance cycle, over the Claude Agent SDK.

This package is the whole application. It was built to supersede three earlier
packages — *"what you do here supersedes everything else such that they can be
deleted at the end"* — and they have been deleted.

Layers, outermost first, and what each may know:

- ``tui/`` — Textual. The only place a terminal library is imported. It renders
  events and answers approvals; it knows nothing about the model.
- ``runner.py`` / ``commands.py`` / ``session.py`` — the shell: one task per
  open session that owns the SDK clients, executes commands, and routes plain
  text by the session's focus (a chat mode, or the graph).
- ``graph/`` — LangGraph. *Which frame runs*: the cycle's state, its records,
  the budget arithmetic and the four frames. Nothing here renders.
- ``harness/`` — the Agent SDK inner layer. *One model turn*: options, hooks,
  the meter, the human gate, the in-process tools, streaming to an event sink.
- ``thought`` (in ``graph/``) — the networkx view over the records: *what is
  known*, changed only through the alteration tools.
"""

from __future__ import annotations


def main() -> None:
    """Entry point registered as ``langchain-claude-test``."""
    from .tui.app import run

    run()
