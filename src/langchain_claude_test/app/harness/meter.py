"""The meter — where a call is priced and where a budget is enforced.

**Charges before the call runs.** Can this be afforded, and if so it is spent.
A reservation settled on return would be state in flight; a harness that dies
mid-call would leave it never settled. Charging on authorisation has nothing in
flight to lose, and it is the honest reading of what the budget prices: the
decision to spend, not the luck of the result.

**Accumulates into itself, not into graph state.** LangGraph commits a node's
update when the node returns, so the meter is the immediate ledger and the node
hands the whole of it back as a delta when the turn is over.
"""

from __future__ import annotations

from collections.abc import Mapping

from ..config import EVIDENCE_TOOL_CLASS
from ..graph import budget
from ..graph.state import SpendEntry
from ..graph.surface import ALTERATION_TOOLS, Stage, bare_name

#: The price class for a write into the store, as opposed to a call that goes
#: and looks. Priced on its own placeholder field.
GRAPH_WRITE_CLASS = "graph_write"

#: The synthetic tool call ``output_format`` arrives as. Never priced.
STRUCTURED_OUTPUT_TOOL = "StructuredOutput"


def call_class(tool_name: str) -> str | None:
    """Which price class a tool falls into. ``None`` for a tool that is neither
    evidence nor an alteration — the surface refuses those before pricing."""
    bare = bare_name(tool_name)
    if bare in ALTERATION_TOOLS:
        return GRAPH_WRITE_CLASS
    return EVIDENCE_TOOL_CLASS.get(bare)


class Meter:
    def __init__(
        self,
        *,
        stage: Stage,
        pools: Mapping[str, int],
        prices: Mapping[str, int],
        default_pool: str = "",
        prior_spend: tuple[SpendEntry, ...] = (),
        graph_write_price: int = 0,
    ) -> None:
        self.stage = stage
        self.pools = dict(pools)
        self.prices = prices
        self.default_pool = default_pool
        self.graph_write_price = graph_write_price
        self._prior = tuple(prior_spend)
        #: Charged calls, in order. The node's delta.
        self.entries: list[SpendEntry] = []
        #: Calls refused, with the reason. Exhaustion is an outcome, not an error.
        self.refused: list[str] = []

    def remaining(self, pool: str | None = None) -> int:
        pool = pool or self.default_pool
        return budget.remaining(list(self._prior) + self.entries, pool, self.pools.get(pool, 0))

    def price(self, klass: str) -> int:
        if klass == GRAPH_WRITE_CLASS:
            return self.graph_write_price
        return budget.price_of(klass, self.prices)

    def charge(self, tool_name: str, tool_use_id: str) -> tuple[str | None, int, int]:
        """Attribute, price, charge — or refuse and say why.

        Returns ``(refusal, price, remaining)``. A refusal is text the model
        reads; ``None`` means the call may run.
        """
        klass = call_class(tool_name)
        if klass is None:
            self.refused.append(f"{tool_name}: unknown class")
            return (f"NOT_AVAILABLE: {tool_name} is not a tool this frame carries.", 0, self.remaining())

        price = self.price(klass)
        if price == 0:
            return (None, 0, self.remaining())

        pool = self.default_pool
        if not pool or pool not in self.pools:
            self.refused.append(f"{tool_name}: no pool")
            return (
                "NO_BUDGET: this frame has no pool for that call, so there is nothing "
                "to charge it to and it cannot run.",
                price,
                0,
            )

        left = self.remaining(pool)
        if price > left:
            self.refused.append(f"{tool_name}: {pool} exhausted")
            return (
                f"BUDGET_EXHAUSTED: {tool_name} costs {price} and {left} is left in this "
                f"pool. Nothing further can be bought here — report what you have.",
                price,
                left,
            )

        self.entries.append(
            SpendEntry(
                pool=pool,
                call=klass,
                tool=bare_name(tool_name),
                price=price,
                stage=self.stage,
                tool_call_id=tool_use_id,
            )
        )
        return (None, price, self.remaining(pool))

    def price_paid(self, tool_use_id: str) -> int:
        for e in self.entries:
            if e.tool_call_id == tool_use_id:
                return e.price
        return 0
