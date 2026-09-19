"""The per-turn ledger — everything a turn records before the node commits it.

LangGraph commits a node's update when the node returns, so nothing inside a
tool call can write to graph state. This object is the immediate ledger: the
hooks, the gate and the tools write here, and the harness hands the whole of it
back as a :class:`TurnResult` when the turn is over. If the node is replayed
the turn re-runs and a fresh ledger recounts — nothing was written twice
because nothing was written at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel

import networkx as nx

from ..graph import thought
from ..graph.state import Compression, Decision, EdgeAdded, Explicit, Finding, NodeAdded, Parked, ProposedWrite
from .meter import Meter
from .protocol import StageRequest, TurnResult, Verdict

_LINE_NUMBER = re.compile(r"^\s*\d+[→:|]\s?", re.MULTILINE)


def normalise(text: str) -> str:
    """Whitespace-insensitive, line-number-insensitive text for excerpt checks."""
    return " ".join(_LINE_NUMBER.sub("", text).split())


def response_text(response: Any) -> str:
    """Every string in a tool response, so an excerpt can be looked for in it."""
    out: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            out.append(node)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v)

    walk(response)
    return "\n".join(out)


@dataclass
class TurnContext:
    request: StageRequest
    meter: Meter
    #: Tool results, keyed by tool_use_id. What an excerpt is checked against.
    records: dict[str, str] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    proposals: list[ProposedWrite] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    explicits: list[Explicit] = field(default_factory=list)
    parked: list[Parked] = field(default_factory=list)
    #: Graph operations recorded this turn (NodeAdded, EdgeAdded, ...), in order.
    graph_ops: list[Any] = field(default_factory=list)
    #: The verdict on each gated call, keyed by tool_use_id.
    verdicts: dict[str, Verdict] = field(default_factory=dict)
    conversation: str = ""
    raw_reply: str = ""
    cost_usd: float | None = None
    #: Runs one fenced read-only command for ``attach_finding``; returns the
    #: output text, or a refusal starting with ``REFUSED``. Set by the harness.
    executor: Callable[[str], str] | None = None
    #: How many findings this turn may create (overwrites do not count).
    max_findings: int = 12
    #: The turn's own copy of the view: validated against, and kept current
    #: by applying every record the turn's tools make.
    graph: nx.MultiDiGraph = field(default_factory=nx.MultiDiGraph)

    def __post_init__(self) -> None:
        if self.request.view is not None:
            self.graph = self.request.view.copy()

    #: While True a handler validates and reports but records nothing: how the
    #: gate checks a call before putting it to the user.
    dry_run: bool = False

    def keep(self, record: Any) -> None:
        """Record one graph operation and apply it to the turn's view."""
        if self.dry_run:
            return
        self.graph_ops.append(record)
        thought.apply(self.graph, record)

    def keep_explicit(self, explicit: Explicit) -> None:
        if self.dry_run:
            return
        self.explicits.append(explicit)
        thought.apply(self.graph, explicit)

    # --- ids: the graph's, never the model's -------------------------------

    def _count(self, record_type: type, **match: Any) -> int:
        return sum(1 for o in self.graph_ops if isinstance(o, record_type) and all(getattr(o, k) == v for k, v in match.items()))

    def next_node_id(self, kind: str) -> str:
        prefix, existing = ("n", self.request.existing.entities) if kind == "entity" else ("c", self.request.existing.claims)
        return f"{prefix}{self.request.cycle}.{existing + self._count(NodeAdded, kind=kind) + 1}"

    def next_edge_id(self) -> str:
        return f"r{self.request.cycle}.{self.request.existing.edges + self._count(EdgeAdded) + 1}"

    def next_summary_id(self) -> str:
        return f"s{self.request.cycle}.{self.request.existing.summaries + self._count(Compression) + 1}"

    def next_finding_id(self) -> str:
        return f"f{self.request.cycle}.{self.request.existing.findings + len(self.findings) + 1}"

    def next_proposal_id(self) -> str:
        return f"p{self.request.cycle}.{self.request.existing.proposals + len(self.proposals) + 1}"

    def next_explicit_id(self) -> str:
        return f"e{self.request.cycle}.{self.request.existing.explicits + len(self.explicits) + 1}"

    # --- records -------------------------------------------------------------

    def record(self, tool_use_id: str, text: str) -> None:
        """Keep every rendering of a result: the hook's and the stream's differ."""
        prior = self.records.get(tool_use_id)
        self.records[tool_use_id] = text if prior is None else prior + "\n" + text

    def source_of(self, excerpt: str) -> str | None:
        """The call whose result contains the excerpt, or ``None``."""
        wanted = normalise(excerpt)
        if not wanted:
            return None
        for call_id, text in self.records.items():
            if wanted in normalise(text):
                return call_id
        return None

    def result(self, payload: BaseModel | None, *, interrupted: bool = False) -> TurnResult:
        return TurnResult(
            payload=payload,
            conversation=self.conversation,
            spend=tuple(self.meter.entries),
            refused=tuple(self.meter.refused),
            findings=tuple(self.findings),
            proposals=tuple(self.proposals),
            decisions=tuple(self.decisions),
            explicits=tuple(self.explicits),
            parked=tuple(self.parked),
            graph_ops=tuple(self.graph_ops),
            tool_results=dict(self.records),
            raw_reply=self.raw_reply,
            interrupted=interrupted,
            cost_usd=self.cost_usd,
        )
