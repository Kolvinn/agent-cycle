"""The application — a Claude shell whose commands switch between a plain Claude
connection and the provenance cycle, over the Claude Agent SDK.

This package is self-contained. It ports what was worth keeping from the earlier
``graph_v2``, ``session`` and ``ledger`` packages and imports none of them, so
that it can supersede them: *"what you do here supersedes everything else such
that they can be deleted at the end."*

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
