"""③ synthesis — a conversation the user is in. The cycle does not advance until
they say so.

Every message the user sends while the pointer is here re-enters this frame as
one exchange; the graph goes round only on ``/graph``. The whole surface is
here, gated at the call — but not on the opening exchange. *"they must not
immediately raise their suggestions to the user as tool calls, it MUST go
through some sort of text discussion phase first. The tool calls should be
suggested in text, and then asked for via the approval mechanism."* So the
opening exchange withholds the gated tools: they are not on the server and the
hook refuses them, and the agent presents and suggests in text. From the
user's first reply on they exist, and a proposal is a call answered at the
call.

This is where fact extraction lives: the user and the agent going through the
user's own replies together, each registration answered at the call. The
output of the stage is not the text. It is the package the next cycle opens
with.
"""

from __future__ import annotations

from langgraph.runtime import Runtime

from .. import budget, thought
from ..context import ControlContext
from .. import vocabulary as v
from ..payloads import Exchange
from ..state import GraphState, Reasoning
from ..surface import GATED_TOOLS
from ...harness.protocol import StageRequest
from ._common import continuation, continued, price_line

NAME = "synthesis"

SYNTHESIS_BRIEF = """Take the graph, the findings, the original question and the facts. Present what
is there, how it relates to the question, what is missing and what is not known.

Then work out with the user where to go next, and put it to them **as changes to
the graph**. That is what this stage is for. Not a list of things someone could
do — the specific changes that would leave the graph in the shape the next cycle
should start from. Think hard about it before you suggest anything; a path
forward is a claim about what matters, and it is worth as much thought as the
assumptions were.

The changes you can put to the user, each a call they answer:

- propose_fact — their own words, verbatim, become a KNOWN fact (supports may
  name the claims it grounds).
- add_edge — a relation between two nodes: {relations}.
- update_node / update_edge — rename, reword, reclassify.
- merge — one node into another of the same kind; its evidence and relations
  move with it. This is how two names for one thing become one.
- move_evidence — one finding onto the node it actually speaks to.
- delete_node / delete_edge — discard. A node with evidence or relations still
  on it is refused: merge or move first, so nothing is lost.
- close_node — their verdict, confirmed or refuted; terminal.
- supersede — one claim replaces another; the loser keeps its evidence.
- compress — a summary stands in for a set in what the next cycle sees.

add_node (an entity or an observation) is free and not gated: it is provisional
and claims nothing. graph_search(text) and graph_neighbours(id) read the graph
beyond what is rendered above; they are free.

{compression}

This is a discussion first and a set of calls second, in that order:

1. On this opening turn the alteration tools do not exist. Present, and suggest
   the changes **in text**: which node, which change, and why, so the user can
   read them together and push back before anything is asked of them. A call
   you attempt now is refused.
2. From the user's first reply on, the alteration tools exist. Then propose by
   calling — and only what was discussed and what their reply bears on. A
   suggestion they did not respond to is still a suggestion; raise it again in
   text if it still matters.

Anything that touches authority goes to the user at the moment you call it, and
their answer comes back to you as the call's result — so propose what you
actually think is right and let them answer it. A refusal will carry their
words. Read them: they are the user speaking, not a limit you should route
around, and they are usually the most valuable thing you will get this turn.

Findings you attach here (attach_finding runs one read-only command and keeps
its output; free, {findings} per turn) need target set to the id of the node
they speak to, exactly as it appears in the graph above (for example a1.2 or
x1.1).

You have {pool} points for looking, across this whole conversation rather than
per message. {prices}. You do not have to spend them; ask the user before going
on a hunt, because they are in the room.

YOU MUST say what you did not look at. The budget ran out somewhere, or points
were left unspent. Say where, plainly.

YOU MUST NOT present your options as conclusions. They are suggestions, they may
well be wrong, and saying so is part of the answer rather than a hedge on it.

{asymmetry}

The user ends this stage when they are ready. Do not try to wrap it up.
"""


def compression_paragraph(candidates: list[tuple[str, str]]) -> str:
    """The brief's standing proposal: what compression is due this cycle.

    Proposed every cycle — *"cycles of growth, compression and
    reconciliation"* — so the top of the graph stays small. Suggested in
    text on the opening turn like everything else, then put as a call.
    """
    if not candidates:
        return "Nothing is due for compression this cycle."
    lines = ["Due for compression this cycle — suggest it in text now, and call compress once the user has replied:"]
    lines += [f"- {nid}: {why}" for nid, why in candidates[:12]]
    if len(candidates) > 12:
        lines.append(f"- and {len(candidates) - 12} more; graph_search finds them")
    return "\n".join(lines)


async def synthesis(state: GraphState, runtime: Runtime[ControlContext]) -> dict:
    ctx = runtime.context
    ledger = ctx.store.ledger()
    view = ctx.store.view()
    pool_name = budget.synthesis_pool(state.cycle)
    pool = ctx.budgets.synthesis_points
    opening = state.synthesis_turns == 0
    conversation, fork = continuation(state)
    known = thought.live_ids(view)

    result = await ctx.harness.run(
        StageRequest(
            label=f"{NAME}.{state.cycle}.{state.synthesis_turns}",
            stage=NAME,
            cycle=state.cycle,
            brief=(
                SYNTHESIS_BRIEF.format(
                    pool=pool,
                    prices=price_line(ctx.prices),
                    asymmetry=budget.asymmetry_disclosure(len(ledger.assumptions_of(state.cycle)), ctx.budgets),
                    findings=ctx.budgets.max_findings,
                    relations=v.vocabulary_line(frozenset(ledger.relation_kinds)),
                    compression=compression_paragraph(
                        thought.compression_candidates(view, state.cycle, ctx.budgets.stale_after)
                    ),
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
            prior_spend=tuple(ledger.spend),
            said=tuple(state.said) + (() if opening else (state.prompt,)),
            node_ids=known,
            view=view,
            relation_kinds=frozenset(ledger.relation_kinds),
            finding_target=lambda raw, known=known: str(raw).strip() if str(raw).strip() in known else None,
            existing=ledger.counts(state.cycle),
            # Text first: the opening exchange has no gated tools to call.
            withheld=GATED_TOOLS if opening else frozenset(),
        )
    )
    payload = result.payload
    text = payload.text if payload is not None else result.raw_reply or "(no answer)"

    stamp = {"cycle": state.cycle}
    ctx.store.append(
        ctx.session,
        [
            *(e.model_copy(update=stamp) for e in result.explicits),
            *(p.model_copy(update=stamp) for p in result.parked),
            *(f.model_copy(update=stamp) for f in result.findings),
            *result.graph_ops,
            *(w.model_copy(update=stamp) for w in result.proposals),
            *(d.model_copy(update=stamp) for d in result.decisions),
            Reasoning(stage=NAME, cycle=state.cycle, about="", text=text),
            *result.spend,
        ],
    )

    return {
        "stage": NAME,
        **continued(result.conversation),
        "synthesis_turns": state.synthesis_turns + 1,
        "said": [] if opening else [state.prompt],
        "disposition": text,
    }
