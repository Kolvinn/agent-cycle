"""The explicit/implicit ledger: nodes, invariants, renderings, trace.

Pure and LLM-free by design. Everything in this package is deterministic, so
the rules can be tested exhaustively for free, before a model is involved at
all.
"""

from .graph import (
    apply_source,
    check_invariants,
    edges,
    form_implicit,
    grounds_edge_for,
    new_ledger,
    node,
    nodes,
    open_explicits,
    register_explicit,
    set_status,
    to_jsonable,
    unresolved_implicits,
)
from .models import (
    CallTier,
    EdgeKind,
    GraphResult,
    LedgerEdge,
    LedgerNode,
    NewExplicit,
    NewImplicit,
    NodeKind,
    NodeStatus,
    Source,
)
from .render import to_digest, to_mermaid
from .trace import Event, Trace

__all__ = [
    "CallTier",
    "EdgeKind",
    "Event",
    "GraphResult",
    "LedgerEdge",
    "LedgerNode",
    "NewExplicit",
    "NewImplicit",
    "NodeKind",
    "NodeStatus",
    "Source",
    "Trace",
    "apply_source",
    "check_invariants",
    "edges",
    "form_implicit",
    "grounds_edge_for",
    "new_ledger",
    "node",
    "nodes",
    "open_explicits",
    "register_explicit",
    "set_status",
    "to_digest",
    "to_jsonable",
    "to_mermaid",
    "unresolved_implicits",
]
