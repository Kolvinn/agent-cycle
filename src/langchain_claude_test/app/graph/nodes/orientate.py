"""① orientate — go wide, and name the readings worth exploring.

Opens a **fresh conversation**: the cycle boundary is where the previous
conversation is thrown away and the graph is injected in its place. Reads the
carried package and the question, and nothing else — the tools are for going
and looking at the world.

Carries evidence calls only. It is a reader: nothing it does can reach the
store except through its answer. Writing a reading opens that reading's pool at
the graph's number, so a cap cannot be set before the thing it caps exists.
"""

from __future__ import annotations

from langgraph.runtime import Runtime

from .. import budget, package
from ..context import ControlContext
from ..payloads import Orientation
from ..state import Assumption, GraphState
from ...harness.protocol import StageRequest
from ._common import counts, price_line

NAME = "orientate"

#: States facts, not prohibitions. The surface and the budget are the
#: enforcers; the numbers are here to plan against, not to warn with.
ORIENTATE_BRIEF = """Your job is to orientate yourself against the user's request as efficiently and
as accurately as you can, and then to name the distinct readings of that request
that are worth exploring. You are naming what is worth testing, not testing it.

Everything already known is above, if there is anything: the facts the user
registered, the readings taken before and what was found for them. That is the
whole of what survived the last cycle. Your tools are for going and looking at
the world, not at that.

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
    """No attempt named a usable number of readings. Nothing decides what
    happens then, so this raises rather than picking."""


async def orientate(state: GraphState, runtime: Runtime[ControlContext]) -> dict:
    ctx = runtime.context
    cycle = state.cycle + 1
    pool_name = budget.orientation_pool(cycle)
    pool = ctx.budgets.orientation_points
    ceiling = ctx.budgets.max_assumptions
    opening = package.opening(state, state.prompt)

    spent: list = []
    correction = ""
    payload = None
    conversation = ""

    for attempt in range(ctx.budgets.max_reauthor_attempts + 1):
        result = await ctx.harness.run(
            StageRequest(
                label=f"{NAME}.{attempt}",
                stage=NAME,
                cycle=cycle,
                brief=ORIENTATE_BRIEF.format(pool=pool, prices=price_line(ctx.prices), ceiling=ceiling),
                message=f"{opening}\n\n{correction}" if correction else opening,
                payload_schema=Orientation,
                # The first attempt opens a fresh conversation; a retry continues it.
                conversation=conversation,
                pools={pool_name: pool},
                default_pool=pool_name,
                prior_spend=tuple(state.spend) + tuple(spent),
                said=(state.prompt,),
                existing=counts(state, cycle),
            )
        )
        spent.extend(result.spend)
        conversation = result.conversation
        payload = result.payload
        if payload is not None and 1 <= len(payload.assumptions) <= ceiling:
            break
        count = 0 if payload is None else len(payload.assumptions)
        correction = f"That answer named {count} readings. Name between one and {ceiling}."
    else:
        raise OrientationFailed(
            f"{ctx.budgets.max_reauthor_attempts + 1} attempts, none naming between one and {ceiling} readings"
        )

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

    return {
        "cycle": cycle,
        "stage": NAME,
        "question": state.prompt,
        "said": [state.prompt],
        "advance": False,
        "conversation": conversation,
        "fork_conversation": False,
        "assume_turns": 0,
        "reading_turns": 0,
        "current_reading": "",
        "synthesis_turns": 0,
        "orientation": payload.reading,
        "assumptions": readings,
        "allocations": budget.allocate([a.id for a in readings], ctx.budgets),
        "spend": spent,
    }
