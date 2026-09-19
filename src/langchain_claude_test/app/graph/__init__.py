"""The control graph — LangGraph decides which frame runs.

Three frames, one state, a pointer the user controls::

    ┌─► orientate ──► antithesis ──► synthesis ──► (end of run)
    │       │                            │
    │       └─ survey, keep findings,    └─ you are here until you
    │          suggest assumptions          say otherwise
    └──────────── /graph <query> ────────────┘

What distinguishes this from the earlier design it replaced:

- the separate assume frame is gone: orientate surveys the project, keeps what
  it read as findings on the question, and suggests the assumptions, with the
  budget the assume frame used to hold folded into its pool;
- the antithesis frame authors **one rival per assumption** in a single pass,
  funded at base + N;
- the evidence tools are the SDK's built-ins, priced by class, rather than
  in-graph copies of them;
- the state records the SDK conversation the cycle is running in, so a thread
  resumed from disk re-opens the same conversation;
- durability is a SQLite checkpointer rather than memory, and the graph
  itself is a project-level op log (``store.py``) every session shares.

The compiled graph lives in ``graph.py`` and is imported lazily here: the
harness layer imports this package for the state records, and the nodes import
the harness, so an eager import of the graph would be circular.
"""

from __future__ import annotations

from .context import ControlContext
from .state import GraphState

__all__ = [
    "ControlContext",
    "GraphState",
    "build",
    "check_topology",
    "compile_cycle",
    "render",
    "serializer",
    "sqlite_checkpointer",
]

_LAZY = {"build", "check_topology", "compile_cycle", "render", "serializer", "sqlite_checkpointer"}


def __getattr__(name: str):
    if name in _LAZY:
        from . import graph as _graph

        return getattr(_graph, name)
    raise AttributeError(name)
