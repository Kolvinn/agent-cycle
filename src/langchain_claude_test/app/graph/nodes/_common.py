"""What every frame shares: how a turn continues the cycle's conversation, how
the prices are stated, and how a frame that retries carries what the earlier
attempt already produced."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace

import networkx as nx

from ...config import EVIDENCE_TOOL_CLASS
from ...harness.protocol import TurnResult
from .. import thought
from ..state import Compression, Counts, EdgeAdded, Finding, GraphState, NodeAdded, RelationKind


def price_line(prices: Mapping[str, int]) -> str:
    """The tools the frame carries and what each costs, as one line."""
    parts = [f"{tool} costs {prices.get(klass, '?')}" for tool, klass in EVIDENCE_TOOL_CLASS.items()]
    return ", ".join(parts)


def continuation(state: GraphState) -> tuple[str, bool]:
    """The conversation a continuing frame resumes, and whether it must fork."""
    return state.conversation, state.fork_conversation


def continued(conversation: str) -> dict:
    """The delta every continuing frame returns about the conversation."""
    return {"conversation": conversation, "fork_conversation": False}


class Attempts:
    """What a frame accumulates across its attempts at one turn.

    A retry opens a new turn on the same conversation; the ids it assigns must
    continue after the first attempt's, and its view must include what the
    first attempt added. Nothing here is in the log yet — the frame appends
    everything at once when it is done, so an interrupted retry leaves nothing
    behind.
    """

    def __init__(self, view: nx.MultiDiGraph, counts: Counts, relation_kinds: Iterable[str]) -> None:
        self.view = view.copy()
        self.base = counts
        self.relation_kinds = set(relation_kinds)
        self.findings: list[Finding] = []
        self.ops: list = []
        self.spend: list = []

    def absorb(self, result: TurnResult) -> None:
        self.spend.extend(result.spend)
        self.findings.extend(result.findings)
        self.ops.extend(result.graph_ops)
        for record in (*result.findings, *result.graph_ops):
            thought.apply(self.view, record)
        self.relation_kinds |= {o.name for o in result.graph_ops if isinstance(o, RelationKind)}

    @property
    def counts(self) -> Counts:
        """The base counts plus what earlier attempts produced."""
        return replace(
            self.base,
            findings=self.base.findings + len(self.findings),
            entities=self.base.entities + sum(1 for o in self.ops if isinstance(o, NodeAdded) and o.kind == "entity"),
            claims=self.base.claims + sum(1 for o in self.ops if isinstance(o, NodeAdded) and o.kind == "claim"),
            edges=self.base.edges + sum(1 for o in self.ops if isinstance(o, EdgeAdded)),
            summaries=self.base.summaries + sum(1 for o in self.ops if isinstance(o, Compression)),
        )

    def stamped(self, cycle: int) -> list:
        """The findings with the cycle stamped, then the ops, for the log."""
        return [*(f.model_copy(update={"cycle": cycle}) for f in self.findings), *self.ops]
