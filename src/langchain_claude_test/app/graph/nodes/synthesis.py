"""④ synthesis — a conversation the user is in. The cycle does not advance until
they say so.

Every message the user sends while the pointer is here re-enters this frame as
one exchange; the graph goes round only on ``/graph``. The whole surface is
here, gated at the call: proposing is not doing, so the agent can propose
freely — *"since the tools are gated by hitl anyway, we dont have to worry
about premature calling."*

This is where fact extraction lives: the user and the agent going through the
user's own replies together, each registration answered at the call. The
output of the stage is not the text. It is the package the next cycle opens
with.
"""

from __future__ import annotations

from langgraph.runtime import Runtime

from .. import budget
from ..context import ControlContext
from ..payloads import Exchange
from ..state import GraphState, Reasoning
from ...harness.protocol import StageRequest
from ._common import continuation, continued, counts, price_line

NAME = "synthesis"

SYNTHESIS_BRIEF = """Take the graph, the findings, the original question and the facts. Present what
is there, how it relates to the question, what is missing and what is not known.

Then work out with the user where to go next, and put it to them **as changes to
the graph**. That is what this stage is for. Not a list of things someone could
do — the specific registrations, closures, supersessions and compactions that
would leave the graph in the shape the next cycle should start from. Think hard
about it before you propose anything; a path forward is a claim about what
matters, and it is worth as much thought as the readings were.

Propose by calling. Anything that touches authority goes to the user at the
moment you call it, and their answer comes back to you as the call's result —
so propose what you actually think is right and let them answer it. A refusal
will carry their words. Read them: they are the user speaking, not a limit you
should route around, and they are usually the most valuable thing you will get
this turn.

Findings you attach here need target set to the id of the node they speak to,
exactly as it appears in the graph above (for example a1.2 or x1.1).

You have {pool} points for looking, across this whole conversation rather than
per message. {prices}. You do not have to spend them; ask the user before going
on a hunt, because they are in the room.

YOU MUST say what you did not look at. The budget ran out somewhere, or a
reading was left with points unspent. Say where, plainly.

YOU MUST NOT present your options as conclusions. They are suggestions, they may
well be wrong, and saying so is part of the answer rather than a hedge on it.

{asymmetry}

The user ends this stage when they are ready. Do not try to wrap it up.
"""


async def synthesis(state: GraphState, runtime: Runtime[ControlContext]) -> dict:
    ctx = runtime.context
    pool_name = budget.synthesis_pool(state.cycle)
    pool = ctx.budgets.synthesis_points
    opening = state.synthesis_turns == 0
    conversation, fork = continuation(state)
    known = frozenset(state.node_ids())

    result = await ctx.harness.run(
        StageRequest(
            label=f"{NAME}.{state.cycle}.{state.synthesis_turns}",
            stage=NAME,
            cycle=state.cycle,
            brief=(
                SYNTHESIS_BRIEF.format(
                    pool=pool,
                    prices=price_line(ctx.prices),
                    asymmetry=budget.asymmetry_disclosure(len(state.current_assumptions()), ctx.budgets),
                )
                if opening
                else ""
            ),
            # The opening exchange has nothing to say beyond the brief. Every
            # later one is the user's message, verbatim and unwrapped.
            message="" if opening else state.prompt,
            payload_schema=Exchange,
            conversation=conversation,
            fork=fork,
            pools={pool_name: pool},
            default_pool=pool_name,
            prior_spend=tuple(state.spend),
            said=tuple(state.said) + (() if opening else (state.prompt,)),
            node_ids=known,
            finding_target=lambda raw, known=known: str(raw).strip() if str(raw).strip() in known else None,
            existing=counts(state, state.cycle),
        )
    )
    payload = result.payload
    text = payload.text if payload is not None else result.raw_reply or "(no answer)"

    return {
        "stage": NAME,
        **continued(result.conversation),
        "synthesis_turns": state.synthesis_turns + 1,
        "said": [] if opening else [state.prompt],
        "disposition": text,
        "proposed": [w.model_copy(update={"cycle": state.cycle}) for w in result.proposals],
        "decisions": [d.model_copy(update={"cycle": state.cycle}) for d in result.decisions],
        "explicits": [e.model_copy(update={"cycle": state.cycle}) for e in result.explicits],
        "parked": [p.model_copy(update={"cycle": state.cycle}) for p in result.parked],
        "findings": [f.model_copy(update={"cycle": state.cycle}) for f in result.findings],
        "reasoning": [Reasoning(stage=NAME, cycle=state.cycle, about="", text=text)],
        "spend": list(result.spend),
    }
