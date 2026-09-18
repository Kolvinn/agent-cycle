# ---------------------------------------------------------------------------
# ④ synthesis — a conversation you are in. The cycle does not advance until you
#    say so.
# ---------------------------------------------------------------------------
#
# Not a report and not a bounded mini-session. Every message you send re-enters
# here; the graph goes round only on your command. Which means:
#
# - There is no pause anywhere in this design, and nothing restarts. Each
#   exchange is a complete run that commits and ends, so every message in the
#   conversation is checkpointed — and therefore forkable. You can go back three
#   replies and take it a different way, and the framework does that for free.
# - The whole surface is here, gated at the call. Proposing is not doing, so the
#   agent can propose freely: *"since the tools are gated by hitl anyway, we dont
#   have to worry about premature calling."*
# - This is where fact extraction lives. It was parked as a stage that guessed at
#   your message before anything was known. Here it is you and the agent going
#   through your own replies and the graph together, deciding what is actually a
#   fact, with each registration answered by you as it is made.
#
# The output of the stage is not the text. It is the package: the graph the next
# cycle opens with.

from __future__ import annotations

from langgraph.runtime import Runtime

from langchain_claude_test.graph_v2 import budget
from langchain_claude_test.graph_v2.context import ControlContext
from langchain_claude_test.graph_v2.harness import StageRequest
from langchain_claude_test.graph_v2.state import Cycle, Reasoning
from langchain_claude_test.graph_v2.surface import available

NAME = "synthesis"

#: The brief. **Sent once, when the stage opens.** Every later message continues
#: the same conversation, where it is still in front of the model, so re-sending
#: it would be paying to repeat what has already been said.
#:
#: It states what the stage is for and what it costs, and it does not forbid
#: anything the gate already forbids. The agent cannot close a node, promote a
#: fact or discard anything without you answering the call — so telling it not to
#: would be describing the machinery back to it, which is noise. What is left is
#: the part nothing can enforce.
SYNTHESIS_BRIEF = """Take the graph, the findings, the original question and the facts. Present what
is there, how it relates to the question, what is missing and what is not known.

Then work out with the user where to go next, and put it to them **as changes to
the graph**. That is what this stage is for. Not a list of things someone could
do — the specific registrations, closures, supersessions and compactions that
would leave the graph in the shape the next cycle should start from. Think hard
about it before you propose anything; a path forward is a claim about what
matters, and it is worth as much thought as the readings were.

Propose by calling. Anything that touches authority goes to the user at the
moment you call it, and their answer comes back to you here — so propose what
you actually think is right and let them answer it. A refusal will carry their
words. Read them: they are the user speaking, not a limit you should route
around, and they are usually the most valuable thing you will get this turn.

You have {pool} points for looking, across this whole conversation rather than
per message. {prices}. You do not have to spend them; ask the user before going
on a hunt, because they are in the room.

YOU MUST say what you did not look at. The budget ran out somewhere, or a
reading was left with points unspent. Say where, plainly.

YOU MUST NOT present your options as conclusions. They are suggestions, they may
well be wrong, and saying so is part of the answer rather than a hedge on it.

The user ends this stage when they are ready. Do not try to wrap it up.
"""


def synthesis_payload():
    """The structured answer one exchange must return.

    ``text`` — what the agent says to you this turn. Prose, at the one place in
    the cycle where prose is the point.

    **No "am I finished" field.** The stage ends when you say so and there is
    nothing for the model to report about it, so it is not asked. A field it
    could set would be a field it could set wrongly, and the only thing that
    could be done with it is ignore it.

    **The alterations are not here.** They are calls, answered as they are made
    — which is the whole shape of this stage. A payload full of proposed changes
    would be a queue again, and a queue is what the pause was for.
    """
    ...


async def synthesis(state: Cycle, runtime: Runtime[ControlContext]) -> dict:
    """One exchange of the conversation.

    **Carries the widest surface in the cycle, and that is the point of the
    stage.** Evidence calls, because you may ask it to go and look; and every
    authority-bearing call, because this is the frame that reads your words and
    therefore the frame where the binding problem actually arises. Your reading
    of a reply only takes effect as a call you answer, so answering confirms the
    binding rather than the claim.

    **Spends from one pool for the whole conversation**, not one per exchange.
    Looking is bounded, talking is not: when the pool runs dry the agent can
    still argue, still propose and still finish the package — it just cannot buy
    more evidence, and going round the cycle is what opens a fresh pool.

    **Does not pause and does not spend on your behalf.** The approval is awaited
    inside the live turn by the harness, not by the graph, so the model's
    conversation stays open across your answer and it can react to what you
    said. The trade is that this pause is not durable: if the process dies while
    you are deciding, this exchange goes with it. The exchange before it is
    committed, because each exchange is its own run.

    **Ends its run every time.** What happens next is the entry router's
    decision, made from the pointer this leaves behind — and the pointer stays
    here until you set ``advance``.
    """
    ctx = runtime.context
    pool_name = budget.synthesis_pool(state.cycle)
    pool = ctx.budgets.synthesis_points
    prices = ", ".join(f"{call} costs {price}" for call, price in sorted(ctx.prices.items()))

    opening = state.synthesis_turns == 0

    result = await ctx.harness.run(
        StageRequest(
            label=f"{NAME}.{state.cycle}.{state.synthesis_turns}",
            stage=NAME,
            system=SYNTHESIS_BRIEF.format(pool=pool, prices=prices) if opening else "",
            # The opening exchange has nothing to say beyond the brief — both
            # cases are already in the conversation. Every later one is your
            # message, verbatim and unwrapped: you are talking to it, and
            # anything the graph added around your words would be the graph
            # putting words in your mouth.
            prompt="" if opening else state.prompt,
            payload_schema=synthesis_payload(),
            tools=available(NAME),
            pools={pool_name: pool},
            default_pool=pool_name,
            prior_spend=tuple(state.spend),
            continues=True,
            turn=3,
        )
    )
    payload = result.payload

    # Appended once, on the opening exchange. It is about how this cycle's
    # evidence was funded, so repeating it every message would be noise — and
    # the graph says it rather than the model, because if the model were trusted
    # to mention it the budget design would quietly do the concluding the report
    # is forbidden from doing, on every turn it forgot.
    text = payload.text
    if opening:
        text += "\n\n" + budget.asymmetry_disclosure(
            len(state.current_assumptions()), ctx.budgets
        )

    return {
        "stage": NAME,
        "synthesis_turns": state.synthesis_turns + 1,
        "disposition": text,
        # What the agent asked to do, and what you answered. Both kept, because
        # a refusal is a record: it is what stops the next cycle re-proposing
        # ground you have already closed.
        #
        # Stamped with the cycle here, as findings are, and for the same reason:
        # the harness made the calls and does not know which cycle it is in. The
        # graph does.
        "proposed": [w.model_copy(update={"cycle": state.cycle}) for w in result.proposals],
        "decisions": [d.model_copy(update={"cycle": state.cycle}) for d in result.decisions],
        # Your own words, registered because you allowed it. The only authority
        # in the state, and the reason this stage is where extraction belongs.
        "explicits": [e.model_copy(update={"cycle": state.cycle}) for e in result.explicits],
        "parked": [p.model_copy(update={"cycle": state.cycle}) for p in result.parked],
        "findings": list(result.findings),
        "reasoning": [
            Reasoning(stage=NAME, cycle=state.cycle, about="", text=payload.text)
        ],
        "spend": list(result.spend),
    }
