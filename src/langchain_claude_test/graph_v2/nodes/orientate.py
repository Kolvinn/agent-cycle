
# ---------------------------------------------------------------------------
# ① orientate — go wide, and name the readings worth exploring
# ---------------------------------------------------------------------------

from __future__ import annotations

from langgraph.runtime import Runtime

from langchain_claude_test.graph_v2 import budget, package
from langchain_claude_test.graph_v2.context import ControlContext
from langchain_claude_test.graph_v2.harness import StageRequest
from langchain_claude_test.graph_v2.state import Assumption, GraphState
from langchain_claude_test.graph_v2.surface import available

NAME = "orientate"

# The pool this frame draws from is named per cycle — ``budget.orientation_pool``
# — and not held as a constant. A constant would be one pool for the life of the
# thread, and the spend channel accumulates across cycles, so the second cycle's
# wide pass would open already spent to zero by the first.

#: The instruction wrapper for this frame. Hand-written, and it wraps rather
#: than restates: the graph is the state and the tools are what read and change
#: it, so nothing already in the store or already in the session context is
#: re-rendered into text here. What *is* injected is the only thing the model
#: cannot reach on its own — the rules of this particular turn: what it may
#: spend, what each call costs, and how many readings it may author.
#:
#: **It states facts, not prohibitions.** The tool surface and the budget are the
#: enforcers: a call outside this frame does not exist, a reading past the ceiling
#: is refused by the tool that writes it, and an unaffordable call is refused by
#: the meter. Telling the model not to do what it structurally cannot do buys
#: nothing and reads as distrust. The numbers are here because they are needed to
#: plan against, not to warn with.
ORIENTATE_PROMPT = """Your job is to orientate yourself against the user's request as efficiently and
as accurately as you can, and then to name the distinct readings of that request
that are worth exploring. You are naming what is worth testing, not testing it.

Everything already known is above, if there is anything: the facts the user
registered, the readings taken before and what was found for them. That is the
whole of what survived the last cycle — the tool output behind it was discarded
once it had been registered, so what is not there was not kept. Your tools are
for going and looking at the world, not at that.

What this stage is for:

1. Go wide before you go deep. This is the only stage funded to survey. The
   stages after it are funded one reading at a time and can only go deep, so
   anything you fail to notice here will not be noticed later.
2. Name each distinct reading of the request, in your answer. A reading must
   name the call whose result would change your belief about it.

What you have:

- {pool} points for this stage. {prices}.
- Looking things up costs. Naming the readings does not.
- Between one and {ceiling} readings.

When the budget is gone your calls are refused. That ends the stage and is not
an error — report what you have.
"""


class OrientationFailed(RuntimeError):
    """The frame could not return a usable number of readings.

    ⚠️ **Open.** Nothing decides what happens here. The alternatives all decide
    something: truncating picks which readings survive, which is a judgement the
    graph has no basis for; proceeding on none leaves the next frame with nothing
    to fund; and the node that used to ask you was removed with the rest of the
    old shape. Raising is the only one that decides nothing, so it raises, and
    this is where the decision goes when it is made.
    """


def orientation_payload(ceiling: int):
    """The structured answer this frame must return, bounded for this run.

    ``reading`` — the landscape, against what was asked.
    ``assumptions`` — between one and ``ceiling`` readings, each carrying only
    what the model authors: the claim, what it hangs off, why it was read that
    way, and the call that would change belief about it.

    **No id.** The graph assigns those, positionally, in :func:`orientate`. An
    id the model invents is one more thing that can come back duplicated or
    drifted, and a finding stamped to the wrong reading is a mistake nothing
    downstream could detect. Position is the one handle both sides already agree
    on — so the model is never asked for an id, and never told one.

    **Built per run, because the ceiling is a context value and not a literal.**

    **Why the readings come back here rather than as calls.** Everywhere else in
    this design an alteration is a tool call, validated one at a time. The count
    is the exception, because it is a property of the whole set: a per-call
    refusal can stop a fourth reading, but nothing a tool does can produce a
    second. "Too few" is the failure the schema is for, and it is the failure
    that matters more — one reading is a conclusion wearing a plural.

    A violation is a retry, and it is the graph that retries — see
    :func:`orientate`. The harness transports one turn; how many attempts a
    mismatch is worth, and what happens when they run out, are control decisions.
    """
    ...


async def orientate(state: GraphState, runtime: Runtime[ControlContext]) -> dict:
    """Read the landscape against what was asked, and author the readings.

    **Reads:** the user's request, and nothing else. The graph is the state and
    the tools are what reach it, so the facts already registered and the ground
    already refused are not re-rendered into the message — the model goes and
    looks. What the node injects is only what the model cannot reach: this turn's
    budget, the price of each call, and the ceiling on how many readings it may
    author.

    **Carries:** evidence calls only. It is a reader — it looks, and returns what
    it read, so nothing it does can reach the store except through its answer.

    The authority-bearing calls belong on this frame and nowhere else, because it
    is the only one that reads your words: a queued call from here would be the
    agent's *reading of your reply*, offered back as a call you approve, which is
    what stops free prose becoming a silent reinterpretation. They are commented
    out of the surface for now — fact extraction is parked, so there is nothing
    for them to do yet.

    **Spends:** one pool, sized in context.

    *Authoring the readings here is your change, and it supersedes the earlier
    rule that orientation forms no claim.* Naming rival readings is not
    concluding, and going wide is the same act as producing the set worth
    exploring — splitting it into a second frame was paying for a distinction
    that per-call pricing already enforces.

    **Writing a reading opens that reading's pool** at the graph's number, and the
    same tool refuses the one that would exceed the ceiling. Authoring and
    spending now share a frame, so a cap cannot be set before the thing it caps
    exists — and this keeps the agent from naming its own.

    No self-loop and no readiness flag: the pool bounds the turn, and when it runs
    dry the turn ends with whatever it managed to survey. The short path for simple
    requests is removed for now — it is not needed to test the loop.
    """
    ctx = runtime.context

    # What the cycle opens with: the carried graph, then the question. Built
    # before the loop, because it is the same for every attempt.
    opening = package.opening(state, state.prompt)

    # The cycle this frame is opening. Computed first because the pool is named
    # after it, and every record it authors is stamped with it.
    cycle = state.cycle + 1
    pool_name = budget.orientation_pool(cycle)

    # ⚠️ Placeholder. The design never assigned this frame a number and it sits on
    # the provisional list, not the settled one.
    pool = ctx.budgets.orientation_points

    # The limit is yours: *"there should be a limit on the amount of assumptions
    # produced."* The number is not, and is still a placeholder.
    ceiling = ctx.budgets.max_assumptions

    # Registering this frame's tools is the node's real work: the surface is
    # assembled per frame and there is no built-in surface to route around it.
    # This frame is a reader — it looks, and returns what it read. It carries no
    # write at all, so nothing it does can reach the store except through the
    # answer it gives back.
    tools = available(NAME)
    prices = ", ".join(f"{call} costs {price}" for call, price in sorted(ctx.prices.items()))

    # The retry on a count mismatch. Two things make it safe to loop here:
    #
    # Nothing above it pauses, so a replay re-runs the whole loop and recounts
    # rather than double-charging — the node still debits only by returning.
    #
    # And an attempt cannot buy extra lookups. Each one is handed everything
    # spent so far, including by its own earlier attempts, so the pool is derived
    # across the loop rather than reset by it. A model that retries three times
    # has less to spend each time, not more.
    spent: list = []
    correction = ""
    payload = None

    for attempt in range(ctx.budgets.max_reauthor_attempts + 1):
        result = await ctx.harness.run(
            StageRequest(
                label=f"{NAME}.{attempt}",
                stage=NAME,
                system=ORIENTATE_PROMPT.format(
                    pool=pool, prices=prices, ceiling=ceiling
                ),
                # The carried graph and the question. This is the one place in
                # the design that renders state into a prompt, and it is the one
                # place where the conversation does not already hold it: this
                # frame starts a new conversation, deliberately, and the graph
                # is what crosses instead of the transcript.
                prompt=f"{opening}\n\n{correction}" if correction else opening,
                payload_schema=orientation_payload(ceiling),
                tools=tools,
                pools={pool_name: pool},
                default_pool=pool_name,
                prior_spend=tuple(state.spend) + tuple(spent),
                turn=1,
            )
        )
        spent.extend(result.spend)
        payload = result.payload

        if 1 <= len(payload.assumptions) <= ceiling:
            break

        # Stated as a fact, the way the prompt is. The model is not told off for
        # a count it may not have been able to reach — it is told the count it
        # gave and the range that is accepted.
        correction = (
            f"That answer named {len(payload.assumptions)} readings. "
            f"Name between one and {ceiling}."
        )
    else:
        raise OrientationFailed(
            f"{ctx.budgets.max_reauthor_attempts + 1} attempts, none naming between "
            f"one and {ceiling} readings"
        )

    # The graph assigns the ids, positionally. The model authored the claims and
    # nothing else; it is not asked to name them and is not told what they were
    # named. Each is stamped with the landscape it was formed against, so a
    # reading that outlives its orientation is visible rather than silent.
    readings = [
        Assumption(
            id=f"a{cycle}.{position}",
            cycle=cycle,
            claim=authored.claim,
            grounded_in=authored.grounded_in,
            inferred_because=authored.inferred_because,
            moved_by=authored.moved_by,
            formed_against=payload.reading,
        )
        for position, authored in enumerate(payload.assumptions, start=1)
    ]

    # The graph allocates; the agent never names its own number. The count is
    # already bounded, so what is funded here is exactly what the loop accepted.
    #
    # Flat, not weighted. Falsification cannot be free means cost may not attach
    # to the direction of a conclusion, and any weighting would have to come from
    # somewhere — the agent's own confidence being the only signal on offer.
    allocations = budget.allocate([a.id for a in readings], ctx.budgets)

    return {
        "cycle": cycle,
        "stage": NAME,
        # What this cycle is about, fixed here so that replying to the
        # conversation later cannot quietly rewrite it.
        "question": state.prompt,
        # The command has been acted on. Left standing it would restart the
        # cycle on every message.
        "advance": False,
        # Opening a cycle resets what is per-cycle. ``assume_turns`` is what
        # tells the next frame whether its instructions have been sent, and this
        # frame starts a fresh conversation (``continues`` is false here and
        # nowhere else), so a count left standing from the previous cycle would
        # mean those instructions were never sent again — in a conversation that
        # has never seen them.
        "assume_turns": 0,
        "reading_turns": 0,
        "current_reading": "",
        "synthesis_turns": 0,
        "orientation": payload.reading,
        "assumptions": readings,
        "allocations": allocations,
        # No alterations. This frame carries none: the authority-bearing calls
        # live where your words are read, which is the conversation at the end
        # rather than the guess at the start.
        #
        # Returned, never applied as a side effect. A priced node debits by
        # handing back state, so a replay recounts instead of double-charging.
        # Every attempt's spend, not just the accepted one's.
        "spend": spent,
    }

