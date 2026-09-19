"""What the driver hands the graph for one run.

Constructed outside the graph and passed as LangGraph's runtime context. Nodes
reach it through ``runtime.context``. Caps, prices, the harness and the
approver all live here rather than in state: readable from every node,
writable from none, and never checkpointed — a live SDK connection is not
serialisable and a fork must never carry a stale one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Mapping

from ..config import DEFAULT_PRICES, Budgets

if TYPE_CHECKING:  # pragma: no cover
    from ..harness.protocol import StageHarness


@dataclass(frozen=True, slots=True)
class ControlContext:
    #: The inner Agent SDK boundary. One harness, opened per frame turn.
    harness: "StageHarness"
    budgets: Budgets = field(default_factory=Budgets)
    prices: Mapping[str, int] = DEFAULT_PRICES
