"""Live session state — the one mutable thing the gate and runner share.

The ledger functions are pure and hand back new graphs, which is right for
testing but leaves someone holding the current one. That is this object. It
also carries the bookkeeping the gate needs to answer "how far from the user's
words is this call, and has this claim already had its evidence?"
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from ..ledger.graph import new_ledger


@dataclass
class SessionState:
    """Everything that changes as a session runs."""

    graph: nx.DiGraph = field(default_factory=new_ledger)
    turn: int = 0

    #: Raw text of every tool result, keyed by call id. The source check reads
    #: from here, which is what stops the agent being its own witness.
    tool_results: dict[str, str] = field(default_factory=dict)

    #: Evidence calls spent per implicit. The multi-hop cap is enforced against
    #: this rather than by trying to detect a second hop after the fact —
    #: depth 2 cannot arise if a claim only ever gets one look.
    evidence_used: dict[str, int] = field(default_factory=dict)

    #: Paths the user named in their own words. Reading one of these is depth 0
    #: by definition: the user handed over the target, so no inference happened.
    user_named_paths: set[str] = field(default_factory=set)

    #: The verbatim text of the turn being processed, for the quote check.
    current_message: str = ""

    def spend_evidence(self, node_id: str) -> int:
        self.evidence_used[node_id] = self.evidence_used.get(node_id, 0) + 1
        return self.evidence_used[node_id]

    def evidence_spent(self, node_id: str) -> int:
        return self.evidence_used.get(node_id, 0)

    def record_result(self, call_id: str, text: str) -> None:
        self.tool_results[call_id] = text
