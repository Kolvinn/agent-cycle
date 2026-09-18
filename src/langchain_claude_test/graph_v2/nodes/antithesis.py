# ---------------------------------------------------------------------------
# ③ antithesis — one turn, funded at base + N. The rival reading of the set.
# ---------------------------------------------------------------------------
#
# **This turn continues the conversation, by your decision.** It therefore has in
# front of it every tool result the case used and every line it wrote about why
# that evidence mattered. Nothing structural withholds any of it, and nothing
# could: the only lever over what a conversation contains is whether you start
# it, and this one is not started.
#
# So the reframe is carried entirely by the prompt, which is why that prompt is
# written in orders rather than description. This is not the prompt restating
# what the tool surface already enforces — the tool surface cannot enforce any of
# it. A model cannot be made to stop reading its own scrollback. Where nothing
# else can bind, the language is the whole of the mechanism, and it is direct.

from __future__ import annotations

from langgraph.runtime import Runtime

from langchain_claude_test.graph_v2 import budget
from langchain_claude_test.graph_v2.context import ControlContext
from langchain_claude_test.graph_v2.harness import StageRequest
from langchain_claude_test.graph_v2.state import Antithesis, Cycle, Reasoning
from langchain_claude_test.graph_v2.surface import available

NAME = "antithesis"

# Named per cycle rather than held as a constant, for the same reason the wide
# pass's pool is: the spend channel accumulates across cycles, so one fixed name
# would arrive at the second cycle already spent to zero by the first.

#: The instruction wrapper. Opens with your own words for this frame.
#:
#: Orders, not description, and deliberately so — see the note at the top of this
#: file. Every "must" below is something no tool surface and no budget can bring
#: about.
ANTITHESIS_PROMPT = """CREATE THE ANTITHESIS OF THESE ASSUMPTIONS AND FINDINGS.

You built that case. You are now going to attack it. These are orders.

YOU MUST find the one reading every assumption above missed — not a weaker
version of one of them, and not a quarrel with the details of one. The blind
spot they all share.

YOU MUST NOT defend anything you just said. You were asked to build a case and
you built one. That is finished. Whether you were right is not this turn's
question and you are not being marked on it.

YOU MUST NOT answer that there is nothing to attack. That is not a permitted
output. If you cannot see the hole, you have not looked hard enough yet, and the
budget below exists for exactly that.

YOU MUST name, for your antithesis, the call whose result would change your
belief about it. A reading nothing could land on is not a reading.

RE-READ WHAT YOU ALREADY READ. The excerpts you collected are quotable by
anyone; *which* excerpts you chose was a decision made inside the frame you are
now attacking. Part of this budget is funded for that and nothing else.

What you have:

- {pool} points: {base} to hunt with, plus one for each of the {n} readings, so
  you can go back over each of them.
- {prices}.
- Attach what you find with attach_finding as you get it. The excerpt is checked
  against what your calls actually returned, so it has to be what came back.

Give the antithesis in your answer, and say what you make of what you found.
"""


def antithesis_payload():
    """The structured answer this frame must return.

    ``antithesis`` — the rival reading, carrying what the model authors: the
    claim, what it contends with, why it was read that way, and the call that
    would change belief about it. **No id**: the graph assigns those, here as in
    the first frame.

    ``reasoning`` — what it makes of what it found.

    **Exactly one, and required.** That is a count, so it belongs on the answer
    for the same reason the readings did — nothing a per-call refusal does can
    produce a rival that was not offered. Unlike the reading count, this one is
    not a run value: it is always one. So the schema carries it outright and
    there is no retry loop here. A missing or empty antithesis fails validation,
    which is the refusal of *"there is nothing to attack"* made mechanical as far
    as it can be; the rest of that refusal is in the prompt, in orders.

    **The findings are not here.** They arrive as calls: individually checkable
    against a recorded result, and unbounded in number.
    """
    ...


async def antithesis(state: Cycle, runtime: Runtime[ControlContext]) -> dict:
    """Author the reading all N miss, and spend against the case.

    **Continues the conversation.** Everything the case gathered and everything it
    argued is in front of the model. The reframe is the prompt's job alone.

    **Carries:** evidence calls and ``attach_finding``. No fact-touching call —
    the rival gathers evidence and cannot promote what it finds, exactly as the
    case could not.

    **Spends:** one pool of ``base + N``. One rival aimed at the whole set, not
    one per reading: only that form catches a misreading the set shares, and a
    per-reading rival would be authored inside the very frame it was meant to
    question. That is also why this is a single turn rather than the subgraph the
    case runs on — there is one thing to fund, so there is nothing to loop over.

    **The two terms are kept apart** rather than collapsed into one number,
    because they answer different problems: the base is the working pool for
    hunting the shared misreading, and the per-reading term funds going back over
    each cited locator, which is the one leak the reframe cannot close by itself.
    """
    ctx = runtime.context
    # This cycle's readings. ``base + N`` is funded from the count, so counting
    # every reading ever authored would fund this turn out of a previous cycle's
    # breadth — and aim it at readings that were answered two cycles ago.
    readings = state.current_assumptions()
    n = len(readings)
    pool_name = budget.antithesis_pool(state.cycle)
    cap = budget.antithesis_budget(n, ctx.budgets)
    prices = ", ".join(f"{call} costs {price}" for call, price in sorted(ctx.prices.items()))

    result = await ctx.harness.run(
        StageRequest(
            label=NAME,
            stage=NAME,
            system=ANTITHESIS_PROMPT.format(
                pool=cap, base=ctx.budgets.antithesis_base, n=n, prices=prices
            ),
            # Nothing to assemble. The readings and the evidence are already in
            # the conversation this turn continues.
            prompt="",
            payload_schema=antithesis_payload(),
            tools=available(NAME),
            pools={pool_name: cap},
            default_pool=pool_name,
            prior_spend=tuple(state.spend),
            continues=True,
            turn=2,
        )
    )
    payload = result.payload

    # The graph assigns the id, as it does for the readings. The model authored
    # the claim and was never told what it was called.
    authored = payload.antithesis
    rival = Antithesis(
        id=f"x{state.cycle}",
        cycle=state.cycle,
        claim=authored.claim,
        grounded_in=authored.grounded_in,
        inferred_because=authored.inferred_because,
        moved_by=authored.moved_by,
        targets=tuple(r.id for r in readings),
    )

    # Stamped here, not by the model. The harness returns the records its calls
    # created and does not know whose turn it is; the graph does, and the graph
    # assigns the ids.
    findings = [f.model_copy(update={"assumption_id": rival.id}) for f in result.findings]

    return {
        "stage": NAME,
        # Accumulates. The rival's findings are stamped with its id and live on
        # the same channel as the case's, so a rival that was overwritten each
        # cycle would leave them pointing at nothing.
        "antitheses": [rival],
        "findings": findings,
        "reasoning": [
            Reasoning(
                stage=NAME, cycle=state.cycle, about=rival.id, text=payload.reasoning
            )
        ],
        "spend": list(result.spend),
    }
