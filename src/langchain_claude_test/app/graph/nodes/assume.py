"""② assume — the research spender. A subgraph: two nodes, two loops.

    while there are open readings:          ← select
        while this reading has budget:      ← investigate
            do tools

The outer loop moves between readings, the inner one stays on the same reading
for as long as it can still afford to look. Both are edges, so both are in the
rendered topology. The model's own tool calls are not a loop here: one entry to
``investigate`` is one harness turn.
"""

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from .. import budget
from ..context import ControlContext
from ..payloads import Investigation
from ..state import GraphState, Reasoning
from ...harness.protocol import StageRequest
from ._common import continuation, continued, counts, price_line

NAME = "assume"
SELECT = "select"
INVESTIGATE = "investigate"

#: Sent once, on the first reading. The conversation continues across every
#: reading, so the instructions stay in front of the model.
ASSUME_BRIEF = """From here you investigate one reading at a time. Each gets its own turn and its
own budget, and you will be told which one and how much.

You are gathering evidence, not deciding. A finding is where you looked and what
it literally said. It is not a conclusion and it is not a fact.

How it is funded:

- {prices}.
- A reading's points are for that reading. Unspent points do not move to the
  next reading or the next turn, so leaving a point here buys nothing anywhere.
- Whatever an earlier reading already looked at is in this conversation. Reading
  it again costs again.

Attach each finding with the attach_finding tool as you get it, rather than
saving them for the end — the excerpt is checked against what your calls actually
returned, so it has to be what came back, copied.

Every tool result ends with what is left. You do not have to keep count.

In your answer, say what you make of what you found. If there is nothing further
worth buying for this reading, say so, and the rest of its budget goes unspent.
"""

ASSUME_TURN = "Reading {position} of {total}. {pool} points for it, {open} still open."
ASSUME_MORE = "{remaining} points left on this reading."


def spend_status(remaining: int, *, open_readings: int) -> str:
    """The line appended after every priced call, from the meter that keeps it."""
    return f"[{remaining} points remaining, {open_readings} open readings]"


def can_still_buy(state: GraphState, reading_id: str) -> bool:
    if reading_id in state.budget_closed:
        return False
    pool = budget.assumption_pool(reading_id)
    return budget.remaining(state.spend, pool, state.allocations.get(reading_id, 0)) > 0


def open_readings(state: GraphState) -> tuple[str, ...]:
    """This cycle's readings that could still buy something, in order."""
    return tuple(r.id for r in state.current_assumptions() if can_still_buy(state, r.id))


def select(state: GraphState, runtime: Runtime[ControlContext]) -> dict:
    still_open = open_readings(state)
    if not still_open:  # pragma: no cover — the router does not route here then
        raise RuntimeError("select entered with no reading left to fund")
    return {"current_reading": still_open[0], "reading_turns": 0}


async def investigate(state: GraphState, runtime: Runtime[ControlContext]) -> dict:
    """Spend on the selected reading, for one turn.

    One pool, so no call has to say which reading it serves: the graph knows
    whose turn it is and stamps every finding. A turn that spent nothing closes
    the reading — that is what makes the inner loop finite.
    """
    ctx = runtime.context
    readings = state.current_assumptions()
    current = state.current_reading
    cap = state.allocations[current]
    pool = budget.assumption_pool(current)
    still_open = len(open_readings(state))
    left = budget.remaining(state.spend, pool, cap)
    position = [r.id for r in readings].index(current) + 1
    first_ever = state.assume_turns == 0
    arriving = state.reading_turns == 0
    conversation, fork = continuation(state)

    result = await ctx.harness.run(
        StageRequest(
            label=f"{NAME}.{current}.{state.reading_turns}",
            stage=NAME,
            cycle=state.cycle,
            brief=ASSUME_BRIEF.format(prices=price_line(ctx.prices)) if first_ever else "",
            message=(
                ASSUME_TURN.format(position=position, total=len(readings), pool=cap, open=still_open)
                if arriving
                else ASSUME_MORE.format(remaining=left)
            ),
            payload_schema=Investigation,
            conversation=conversation,
            fork=fork,
            pools={pool: cap},
            default_pool=pool,
            prior_spend=tuple(state.spend),
            said=tuple(state.said),
            node_ids=frozenset(state.node_ids()),
            # One reading per turn: whatever the model names, the finding is this reading's.
            finding_target=lambda raw, current=current: current,
            status=lambda remaining, n=still_open: spend_status(remaining, open_readings=n),
            existing=counts(state, state.cycle),
        )
    )
    payload = result.payload
    findings = [f.model_copy(update={"node_id": current, "cycle": state.cycle}) for f in result.findings]
    reasoning = payload.reasoning if payload is not None else "(no answer)"
    nothing_further = payload.nothing_further if payload is not None else True

    return {
        "stage": NAME,
        **continued(result.conversation),
        "findings": findings,
        "reasoning": [Reasoning(stage=NAME, cycle=state.cycle, about=current, text=reasoning)],
        "budget_closed": [current] if (nothing_further or not result.spend) else [],
        "assume_turns": state.assume_turns + 1,
        "reading_turns": state.reading_turns + 1,
        "spend": list(result.spend),
    }


def more_to_do(state: GraphState, runtime: Runtime[ControlContext]) -> Literal["investigate", "select", "__end__"]:
    if can_still_buy(state, state.current_reading):
        return INVESTIGATE
    if open_readings(state):
        return SELECT
    return END


def build() -> StateGraph:
    builder: StateGraph = StateGraph(GraphState, context_schema=ControlContext)
    builder.add_node(SELECT, select)
    builder.add_node(INVESTIGATE, investigate)
    builder.add_edge(START, SELECT)
    builder.add_edge(SELECT, INVESTIGATE)
    builder.add_conditional_edges(INVESTIGATE, more_to_do, [INVESTIGATE, SELECT, END])
    return builder


#: Channels that accumulate, derived from the state so a new channel is
#: handled without anyone remembering to come here.
ACCUMULATING: tuple[str, ...] = tuple(
    name for name, f in GraphState.model_fields.items() if any(callable(m) for m in f.metadata)
)


async def assume(state: GraphState, runtime: Runtime[ControlContext]) -> dict:
    """The frame as the parent sees it: one node, returning a delta.

    A compiled subgraph attached with ``add_node`` hands the parent its whole
    final state and every accumulating channel doubles — measured. So the
    subgraph is invoked here and the stage hands back what changed: every
    accumulating channel sliced at the length it had on entry.
    """
    finished = await _COMPILED.ainvoke(state, context=runtime.context)
    delta: dict = {}
    for name in GraphState.model_fields:
        value = finished[name]
        if name in ACCUMULATING:
            value = value[len(getattr(state, name)):]
        delta[name] = value
    return delta


def subgraph():
    return build().compile()


_COMPILED = subgraph()
