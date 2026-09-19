"""The control graph — LangGraph decides which frame runs.

Four frames, one state, a pointer the user controls::

    ┌─► orientate ──► assume ──► antithesis ──► synthesis ──► (end of run)
    │                   │                           │
    │                   └─ while open readings {    └─ you are here until you
    │                        while budget { tools } }   say otherwise
    └───────────────── /graph <query> ──────────────────┘

Ported from ``graph_v2`` and self-contained. What changed in the port:

- the antithesis frame authors **one rival per reading** in a single pass,
  funded at base + N;
- the evidence tools are the SDK's built-ins, priced by class, rather than
  in-graph copies of them;
- the state records the SDK conversation the cycle is running in, so a thread
  resumed from disk re-opens the same conversation;
- durability is a SQLite checkpointer rather than memory.

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
