"""① orientate — survey the ground, relate it to the question, suggest assumptions.

Opens a **fresh conversation**: the cycle boundary is where the previous
conversation is thrown away and the graph is injected in its place. Reads the
carried package and the question, then goes and looks at the world.

This is the cycle's only survey and its only affirming spend: what used to be
a separate frame funded per assumption is folded in here, and the budget with
it. The frame makes no decisions. It builds an overview of the project's
context and surface, says how that bears on what the user asked, keeps what it
read as findings on the cycle's question, and then suggests the assumptions
worth testing. The antithesis frame follows straight after and attacks them.

The cycle number is the graph's: this frame asks the project's op log for the
next one, so two sessions never share a cycle or an id. When the turn is over
everything it authored is appended to the log in one write; the thread state
keeps only the working set.
"""

from __future__ import annotations

from langgraph.runtime import Runtime

from .. import budget, package, thought
from ..context import ControlContext
from ..payloads import Orientation
from ..state import Assumption, GraphState, Reasoning
from ...harness.protocol import StageRequest
from ._common import Attempts, price_line

NAME = "orientate"

#: States facts, not prohibitions. The surface and the budget are the
#: enforcers; the numbers are here to plan against, not to warn with.
ORIENTATE_BRIEF = """Your job is to orientate, not to decide. Build a clear overview of the project's
context and its surface as they bear on what the user asked, keep what you read,
and then suggest the assumptions worth testing. Someone else attacks them next;
the user decides what any of it means. Nothing you say here is a conclusion.

Everything already known is above, if there is anything: the facts the user
registered, the assumptions made before and what was found for them. That is the
whole of what survived the last cycle. Your tools are for going and looking at
the world, not at that.

What this stage is for, in order:

1. Survey. Go wide before you go deep: this is the only stage funded to look at
   the project, and the stage after it can only attack what you surface, so
   anything you fail to notice here will not be noticed later. Establish what
   the project is, how it is laid out, and which parts of it the request
   touches.
2. Keep what you read. The attach_finding tool runs one read-only command
   (sed -n, grep, cat, git show …) and keeps its output as the finding, so you
   read and keep in one step and never retype anything. It is free, with a
   hard limit of {findings} per turn; a mistake is overwritten in place with
   replace=<id>, and only findings you created this turn can be overwritten.
   Findings here hang off the question, not off any assumption; the target
   argument is ignored.
3. Name the things. add_node(kind=entity, …) records a thing in the project —
   a file, module, function, service, config or concept — as a provisional
   node. It is free and not gated, because a provisional node claims nothing;
   the user confirms, merges or discards it later. Name what the request
   touches, not everything you saw. Assumptions are not nodes you add: they
   go in your answer and the graph records them from there. How things
   relate (depends_on, calls,
   part_of, …) is add_edge, and every relation is a question put to the user
   at the call: name only the ones the code shows plainly, or leave them for
   the discussion.
4. Relate. Say how what you found bears on the request: which parts of the
   project it touches, what is plainly there, what is not, and what you could
   not tell.
5. Suggest assumptions. Name the distinct assumptions about the request worth
   testing. An assumption is a checkable proposition, not a finding and not an
   answer. Each must name the call whose result would change your belief about
   it, and may cite the findings it rests on by their ids.

You are not building a case for any of them. A survey that reads as an argument
for one assumption has decided, and deciding is not this stage's job.

What you have:

- {pool} points for this stage. {prices}. attach_finding and add_node are free.
- Looking with Read, Glob or Grep costs. Keeping with attach_finding, naming
  entities, and naming assumptions, do not.
- Between one and {ceiling} assumptions.

When the budget is gone your calls are refused. That ends the stage and is not
an error — report what you have.
"""


class OrientationFailed(RuntimeError):
    """No attempt named a usable number of assumptions. Nothing decides what
    happens then, so this raises rather than picking."""


async def orientate(state: GraphState, runtime: Runtime[ControlContext]) -> dict:
    ctx = runtime.context
    opening = package.opening(ctx.store.ledger(), ctx.store.view(), state.prompt, hops=ctx.budgets.package_hops)
    cycle = ctx.store.open_cycle(ctx.session, state.prompt)
    ledger = ctx.store.ledger()
    pool_name = budget.orientation_pool(cycle)
    pool = budget.orientation_budget(ctx.budgets)
    ceiling = ctx.budgets.max_assumptions
    question = thought.question_id(cycle)

    attempts = Attempts(ctx.store.view(), ledger.counts(cycle), ledger.relation_kinds)
    correction = ""
    payload = None
    conversation = ""

    for attempt in range(ctx.budgets.max_reauthor_attempts + 1):
        result = await ctx.harness.run(
            StageRequest(
                label=f"{NAME}.{attempt}",
                stage=NAME,
                cycle=cycle,
                brief=ORIENTATE_BRIEF.format(pool=pool, prices=price_line(ctx.prices), ceiling=ceiling, findings=ctx.budgets.max_findings) if attempt == 0 else "",
                message=f"{opening}\n\n{correction}" if correction else opening,
                payload_schema=Orientation,
                # The first attempt opens a fresh conversation; a retry continues it.
                conversation=conversation,
                pools={pool_name: pool},
                default_pool=pool_name,
                prior_spend=tuple(ledger.spend) + tuple(attempts.spend),
                said=(state.prompt,),
                node_ids=thought.live_ids(attempts.view),
                view=attempts.view,
                relation_kinds=frozenset(attempts.relation_kinds),
                # Every finding of the survey hangs off the question: the
                # assumptions it may support do not exist until the answer.
                finding_target=lambda raw, q=question: q,
                existing=attempts.counts,
            )
        )
        attempts.absorb(result)
        conversation = result.conversation
        payload = result.payload
        if payload is not None and 1 <= len(payload.assumptions) <= ceiling:
            break
        count = 0 if payload is None else len(payload.assumptions)
        correction = f"That answer named {count} assumptions. Name between one and {ceiling}."
    else:
        raise OrientationFailed(
            f"{ctx.budgets.max_reauthor_attempts + 1} attempts, none naming between one and {ceiling} assumptions"
        )

    kept = {f.id for f in attempts.findings}
    assumptions = [
        Assumption(
            id=f"a{cycle}.{position}",
            cycle=cycle,
            claim=authored.claim,
            grounded_in=authored.grounded_in,
            inferred_because=authored.inferred_because,
            moved_by=authored.moved_by,
            # Only findings this survey actually recorded; an id it invented is dropped.
            evidence=tuple(fid for fid in authored.evidence if fid in kept),
            formed_against=payload.overview,
        )
        for position, authored in enumerate(payload.assumptions, start=1)
    ]

    ctx.store.append(
        ctx.session,
        [
            *attempts.stamped(cycle),
            *assumptions,
            Reasoning(stage=NAME, cycle=cycle, about=question, text=payload.overview),
            *attempts.spend,
        ],
    )

    return {
        "cycle": cycle,
        "stage": NAME,
        "question": state.prompt,
        "said": [state.prompt],
        "advance": False,
        "conversation": conversation,
        "fork_conversation": False,
        "synthesis_turns": 0,
        "orientation": payload.overview,
    }
