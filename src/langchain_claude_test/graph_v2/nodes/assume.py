# ---------------------------------------------------------------------------
# ② assume — the research spender. A subgraph: two nodes, two loops.
# ---------------------------------------------------------------------------
#
#   while there are open readings:          ← select
#       while this reading has budget:      ← investigate
#           do tools
#
# The outer loop moves between readings, the inner one stays on the same reading
# for as long as it can still afford to look. Both are edges, so both are in the
# rendered topology rather than in a body somewhere.
#
# **Why a subgraph rather than a self-loop on one node.** The two loops are
# different questions — "is there another reading" and "can this reading still
# buy" — and collapsing them into one router means the answer to the second has
# to be re-derived every time the first is asked. Separating them also puts a
# checkpoint at the reading boundary, which is the point anyone forking a run
# would want to fork at.
#
# **What is not a loop here.** The model's own tool calls. One entry to
# `investigate` is one harness turn, and the model may make many calls inside it;
# stepping the graph per call would open a fresh subprocess each time and throw
# away the working context between them, which is the opposite of what a turn is
# for. The inner loop is for a reading that needs *another turn*, not another
# call.

from __future__ import annotations

from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime

from langchain_claude_test.graph_v2 import budget
from langchain_claude_test.graph_v2.context import ControlContext
from langchain_claude_test.graph_v2.harness import StageRequest
from langchain_claude_test.graph_v2.state import GraphState, Reasoning
from langchain_claude_test.graph_v2.surface import available

NAME = "assume"
SELECT = "select"
INVESTIGATE = "investigate"

#: The instruction wrapper for this frame. **Sent once**, on the first reading.
#:
#: The conversation continues across every reading, so the instructions stay in
#: front of the model and re-sending them would be paying tokens to say what has
#: already been said. Each later turn sends one line instead.
ASSUME_PROMPT = """From here you investigate one reading at a time. Each gets its own turn and its
own budget, and you will be told which one and how much.

You are gathering evidence, not deciding. A finding is where you looked and what
it literally said. It is not a conclusion and it is not a fact.

How it is funded:

- {prices}.
- A reading's points are for that reading. Unspent points do not move to the
  next reading or the next turn, so leaving a point here buys nothing anywhere.
- Whatever an earlier reading already looked at is in this conversation. Reading
  it again costs again.

Attach each finding with attach_finding as you get it, rather than saving them
for the end — the excerpt is checked against what your calls actually returned,
so it has to be what came back, copied.

Every tool result ends with what is left. You do not have to keep count.

In your answer, say what you make of what you found. If there is nothing further
worth buying for this reading, say so, and the rest of its budget goes unspent.
"""

#: Sent when the outer loop moves to a reading. Named **by position**: the graph
#: assigned the ids and never told the model what they were, but the model knows
#: the order it named them in. Position is the handle both sides already share.
ASSUME_TURN = "Reading {position} of {total}. {pool} points for it, {open} still open."

#: Sent when the inner loop stays on the same reading. Deliberately almost
#: nothing — the reading has not changed and the running count is already on the
#: end of every tool result.
ASSUME_MORE = "{remaining} points left on this reading."


def spend_status(remaining: int, *, open_readings: int) -> str:
    """The line appended to every tool result.

    A budget stated once at the top of a turn is a budget the model is estimating
    by its fourth call, and an estimate is what produces a call it cannot afford.
    This comes from the meter that is actually keeping the count, at the moment
    the count changes, and rides on a message already being sent.

    It reports, and does not instruct. What to do when the number reaches zero is
    in the instructions once; repeating it on every call would be nagging.
    """
    return f"[{remaining} points remaining, {open_readings} open assumptions]"


def assume_payload():
    """The structured answer one turn must return.

    ``reasoning`` — what the model makes of what it found. The affirming
    transcript: recorded because it is the reasoning that produced the case, and
    withheld at the turn boundary for the same reason.

    ``nothing_further`` — the early exit. Safe only because unspent points move
    nowhere: a reading cannot be abandoned to concentrate spend on a favoured one.

    **The findings are not here.** They arrive as calls, one at a time, because
    each is individually checkable — the excerpt has to appear in a recorded tool
    result — and because there is no bound on how many there should be. The
    readings came back on the answer for the opposite reason: their *count* is a
    property of the whole set and nothing a per-call refusal can produce.
    """
    ...


# ---------------------------------------------------------------------------
# The two questions the loops ask. Pure arithmetic over what is recorded — no
# agent judgement reaches either of them.
# ---------------------------------------------------------------------------


def can_still_buy(state: GraphState, reading_id: str) -> bool:
    """Whether this reading has points left and has not closed itself.

    A reading leaves the queue two ways, and both are needed. It runs out, which
    is what keeps the loop finite. Or it is closed, which happens when the model
    says it has nothing further *or* when a turn bought nothing at all — see
    :func:`investigate`. Closing is the one kind of closing the agent may do: it
    may close a reading's *budget*, never its truth. It cannot be derived from
    the balance, because a reading that stops early still has points in its pool.
    """
    if reading_id in state.budget_closed:
        return False
    pool = budget.assumption_pool(reading_id)
    return budget.remaining(state.spend, pool, state.allocations.get(reading_id, 0)) > 0


def open_readings(state: GraphState) -> tuple[str, ...]:
    """Every reading of **this cycle** that could still buy something, in order.

    This cycle's, not every reading ever authored. Answering a report starts a
    new run on the same thread and the readings channel accumulates, so a loop
    over the whole channel would re-enter ground that a previous cycle already
    settled. Nothing would break — a spent reading buys nothing and an
    allocation is rewritten each cycle — which is exactly why it is worth being
    explicit rather than relying on it.
    """
    return tuple(r.id for r in state.current_assumptions() if can_still_buy(state, r.id))


# ---------------------------------------------------------------------------
# select — the outer loop's head
# ---------------------------------------------------------------------------


def select(state: GraphState, runtime: Runtime[ControlContext]) -> dict:
    """Take the next open reading. No model call, no spend.

    Its own node because the reading boundary is the place a run is worth
    checkpointing: it is where a fork means "same evidence, different reading"
    rather than "halfway through a turn". It also resets the per-reading turn
    count, which is what tells :func:`investigate` whether it is arriving at a
    reading or staying on one.
    """
    still_open = open_readings(state)
    if not still_open:  # pragma: no cover — the router does not route here then
        raise RuntimeError("select entered with no reading left to fund")
    return {"current_reading": still_open[0], "reading_turns": 0}


# ---------------------------------------------------------------------------
# investigate — the inner loop's body. One harness turn.
# ---------------------------------------------------------------------------


async def investigate(state: GraphState, runtime: Runtime[ControlContext]) -> dict:
    """Spend on the selected reading, for one turn.

    **Continues the conversation, and says as little as it can.** The full
    instructions go once, on the first reading. Arriving at a reading sends one
    line; staying on one sends less than that. The readings themselves are never
    re-sent — the model named them and they are still in front of it.

    **Carries:** evidence calls and ``attach_finding``. No fact-touching call at
    all, so a reading's turn gathers evidence and cannot promote what it finds —
    which keeps a finding from becoming a fact by enthusiasm.

    **Spends:** exactly one pool, which is why nothing here has to say which
    reading it serves. Requiring every call to name its reading was the first
    obstacle flagged for the harness; one reading per turn removes it rather than
    solving it.

    **The node stamps each finding** rather than the model naming its reading on
    every call. The graph knows whose turn it is, and it assigned the id the model
    was never given.

    **No retry.** The count of findings is unbounded — nothing says a reading must
    produce any — so there is no whole-set property to check. Each finding is
    checked as it is made instead: the excerpt has to appear in a recorded result.

    **A turn that spent nothing closes the reading, and that is what makes the
    inner loop finite.** Without it the loop is only *probably* finite: the
    condition to go round again is that points remain, so a turn that bought
    nothing — because the model declined to look, or because everything it tried
    was refused — arrives at the next turn in exactly the state it started in,
    and does so forever. With it, every turn either spends at least one point or
    ends the reading, so the number of turns a reading can take is bounded by its
    allocation. It is also the honest reading of the behaviour: a turn that chose
    to buy nothing has said what ``nothing_further`` says, by doing it.
    """
    ctx = runtime.context
    readings = state.current_assumptions()
    current = state.current_reading
    cap = state.allocations[current]
    pool = budget.assumption_pool(current)
    still_open = len(open_readings(state))
    left = budget.remaining(state.spend, pool, cap)
    position = [r.id for r in readings].index(current) + 1

    prices = ", ".join(f"{call} costs {price}" for call, price in sorted(ctx.prices.items()))

    # The instructions go once. Every later turn continues the same conversation,
    # where they are still in front of the model, so re-sending them would be
    # paying to repeat what was already said — and a model re-read its own
    # instructions is a model given a reason to think they changed.
    first_ever = state.assume_turns == 0
    arriving = state.reading_turns == 0

    result = await ctx.harness.run(
        StageRequest(
            label=f"{NAME}.{current}.{state.reading_turns}",
            stage=NAME,
            system=ASSUME_PROMPT.format(prices=prices) if first_ever else "",
            prompt=(
                ASSUME_TURN.format(
                    position=position,
                    total=len(readings),
                    pool=cap,
                    open=still_open,
                )
                if arriving
                else ASSUME_MORE.format(remaining=left)
            ),
            payload_schema=assume_payload(),
            tools=available(NAME),
            # One pool, so no call has to be attributed and none can be refused
            # as unattributable.
            pools={pool: cap},
            default_pool=pool,
            prior_spend=tuple(state.spend),
            continues=True,
            # The running count, rendered by the meter after every allowed call.
            status=lambda remaining: spend_status(remaining, open_readings=still_open),
            turn=1,
        )
    )
    payload = result.payload

    # Stamped here, not by the model. The harness returns the records its calls
    # created and does not know whose turn it is; the graph does, and the graph
    # assigns the ids.
    findings = [f.model_copy(update={"assumption_id": current}) for f in result.findings]

    return {
        "stage": NAME,
        "findings": findings,
        # Stamped with the frame and the reading, and never read back into a
        # prompt — the conversation already holds it. It is here so a case can
        # be argued with from the checkpoint rather than only from a live
        # session.
        "reasoning": [
            Reasoning(
                stage=NAME, cycle=state.cycle, about=current, text=payload.reasoning
            )
        ],
        "budget_closed": [current] if (payload.nothing_further or not result.spend) else [],
        "assume_turns": state.assume_turns + 1,
        "reading_turns": state.reading_turns + 1,
        "spend": list(result.spend),
    }


def more_to_do(state: GraphState, runtime: Runtime[ControlContext]) -> Literal["investigate", "select", "__end__"]:
    """Both loop conditions, asked in order. Inner first, then outer.

    Inner first because staying on a reading is the cheaper answer: the model is
    already framed on it and the conversation already holds what it found.
    """
    if can_still_buy(state, state.current_reading):
        return INVESTIGATE
    if open_readings(state):
        return SELECT
    return END


def build() -> StateGraph:
    """The subgraph. Two nodes, two loops, one exit."""
    builder: StateGraph = StateGraph(GraphState, context_schema=ControlContext)
    builder.add_node(SELECT, select)
    builder.add_node(INVESTIGATE, investigate)
    builder.add_edge(START, SELECT)
    builder.add_edge(SELECT, INVESTIGATE)
    builder.add_conditional_edges(INVESTIGATE, more_to_do, [INVESTIGATE, SELECT, END])
    return builder


#: Channels that accumulate. Derived from :class:`Cycle` rather than listed, so
#: a channel added later is handled without anyone remembering to come here.
ACCUMULATING: tuple[str, ...] = tuple(
    name
    for name, f in GraphState.model_fields.items()
    if any(callable(m) for m in f.metadata)
)


async def assume(state: GraphState, runtime: Runtime[ControlContext]) -> dict:
    """The frame, as the parent graph sees it: one node, and it returns a delta.

    **The subgraph is invoked from inside this node rather than attached as one,
    and that is not a style choice.** A compiled subgraph attached with
    ``add_node`` hands the parent its *whole final state*, not the part it wrote
    — so the parent applies its reducer to channels that were already full when
    the subgraph started, and every accumulating channel doubles. Measured, on
    this version: a run through this stage turned five points of orientation
    spend into ten and two readings into four, and the budget arithmetic that
    the whole design rests on was reading a pool as twice spent. An
    ``output_schema`` on the subgraph does not fix it, because the doubling
    happens for exactly the channels the subgraph legitimately writes.

    So the stage hands back what *changed*: every accumulating channel sliced at
    the length it had on entry, and every overwriting channel as it finished.
    Generic over the state rather than a list of channel names, because a list
    is a thing to forget.

    **What this costs.** The stage now commits as a single step of the parent, so
    a crash part-way through the readings loses that stage's turns rather than
    checkpointing each one. The ledger stays consistent either way — the spend is
    only committed when this returns — but the work is paid for again. Worth
    revisiting when the harness is real and a turn costs money.
    """
    finished = await _COMPILED.ainvoke(state, context=runtime.context)

    delta: dict = {}
    for name in GraphState.model_fields:
        value = finished[name]
        if name in ACCUMULATING:
            already = len(getattr(state, name))
            value = value[already:]
        delta[name] = value
    return delta


def subgraph():
    """The compiled inner graph.

    **No checkpointer argument, which is not the same as none.** Left at the
    default: this stage has no ``interrupt()`` in it, so what the setting buys
    here is checkpointing rather than pausing, and opting out with
    ``checkpointer=False`` would say something stronger than is meant. It does
    not need cross-invocation memory — each cycle starts its readings fresh — so
    it is not stateful either.
    """
    return build().compile()


_COMPILED = subgraph()
