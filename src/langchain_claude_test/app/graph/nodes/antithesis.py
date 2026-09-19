"""② antithesis — one pass, one rival per assumption, funded at base + N.

*"change the antithesis pass to a single pass that looks at the antithesis of
all assumptions looked at in the previous"* — so this turn follows the survey
straight away, attacks every assumption it suggested and authors a rival for
each, in one turn. It continues the conversation, so everything the survey
read and everything it said is in front of the model; the reframe is carried
entirely by the brief, which is why the brief is written in orders. A model
cannot be made to stop reading its own scrollback; where nothing else can
bind, the language is the mechanism.

The two budget terms are kept apart: the base funds the hunt, and the N funds
going back over each cited locator — the one leak the reframe cannot close by
itself, because *which* excerpts were kept was the surveying frame's decision.
"""

from __future__ import annotations

from langgraph.runtime import Runtime

from .. import budget, thought
from ..context import ControlContext
from ..payloads import Antitheses
from ..state import Antithesis, GraphState, Reasoning
from ...harness.protocol import StageRequest
from ._common import Attempts, continuation, continued, price_line

NAME = "antithesis"

ANTITHESIS_BRIEF = """CREATE THE ANTITHESIS OF EACH OF THESE ASSUMPTIONS AND THE FINDINGS BEHIND THEM.

You surveyed the ground and suggested those assumptions. You are now going to
attack them, assumption by assumption. These are orders.

For EACH of the {n} assumptions you named, YOU MUST author the counter — the
rival assumption under which that one is wrong, not a weaker version of it and
not a quarrel with its details. One rival per assumption, in the order you
named them.

YOU MUST NOT defend anything you just said. You were asked to survey and to
suggest, and you did. That is finished. Whether you were right is not this
turn's question and you are not being marked on it.

YOU MUST NOT answer that there is nothing to attack. That is not a permitted
output for any assumption. If you cannot see the hole, you have not looked hard
enough yet, and the budget below exists for exactly that.

YOU MUST name, for each rival, the call whose result would change your belief
about it. A rival nothing could land on is not a rival.

RE-READ WHAT YOU ALREADY READ. The findings you kept are quotable by anyone;
*which* excerpts you kept was a decision made inside the frame you are now
attacking. Part of this budget is funded for that and nothing else.

What you have:

- {pool} points: {base} to hunt with, plus one for each of the {n} assumptions,
  so you can go back over each of them.
- {prices}. attach_finding is free, {findings} per turn.
- Keep what you find with attach_finding as you get it: it runs one read-only
  command and keeps the output, with target set to the NUMBER of the assumption
  the finding argues against (1 to {n}). Overwrite a mistake with replace=<id>.
- A thing the survey missed is add_node(kind=entity, …), free and provisional.
  A relation is add_edge, and the user answers it at the call.

Give the {n} rivals in your answer, in assumption order, and say what you make
of what you found.
"""


class AntithesisFailed(RuntimeError):
    """No attempt returned exactly one rival per assumption."""


def rival_id(cycle: int, position: int) -> str:
    return f"x{cycle}.{position}"


def target_resolver(cycle: int, n: int):
    """The model names the assumption by its position; the graph names the rival."""

    def resolve(raw: str) -> str | None:
        text = str(raw).strip().lstrip("#")
        if text.isdigit() and 1 <= int(text) <= n:
            return rival_id(cycle, int(text))
        return None

    return resolve


async def antithesis(state: GraphState, runtime: Runtime[ControlContext]) -> dict:
    ctx = runtime.context
    ledger = ctx.store.ledger()
    assumptions = ledger.assumptions_of(state.cycle)
    n = len(assumptions)
    pool_name = budget.antithesis_pool(state.cycle)
    cap = budget.antithesis_budget(n, ctx.budgets)
    conversation, fork = continuation(state)

    attempts = Attempts(ctx.store.view(), ledger.counts(state.cycle), ledger.relation_kinds)
    correction = ""
    payload = None
    brief = ANTITHESIS_BRIEF.format(
        pool=cap, base=ctx.budgets.antithesis_base, n=n, prices=price_line(ctx.prices), findings=ctx.budgets.max_findings
    )

    for attempt in range(ctx.budgets.max_reauthor_attempts + 1):
        result = await ctx.harness.run(
            StageRequest(
                label=f"{NAME}.{attempt}",
                stage=NAME,
                cycle=state.cycle,
                brief=brief if attempt == 0 else "",
                message=correction,
                payload_schema=Antitheses,
                conversation=conversation,
                fork=fork and attempt == 0,
                pools={pool_name: cap},
                default_pool=pool_name,
                prior_spend=tuple(ledger.spend) + tuple(attempts.spend),
                said=tuple(state.said),
                node_ids=thought.live_ids(attempts.view),
                view=attempts.view,
                relation_kinds=frozenset(attempts.relation_kinds),
                finding_target=target_resolver(state.cycle, n),
                existing=attempts.counts,
            )
        )
        attempts.absorb(result)
        conversation = result.conversation
        payload = result.payload
        if payload is not None and len(payload.antitheses) == n:
            break
        count = 0 if payload is None else len(payload.antitheses)
        correction = f"That answer gave {count} rivals for {n} assumptions. Give exactly one per assumption, in order."
    else:
        raise AntithesisFailed(f"{ctx.budgets.max_reauthor_attempts + 1} attempts, none giving exactly {n} rivals")

    rivals = [
        Antithesis(
            id=rival_id(state.cycle, position),
            cycle=state.cycle,
            claim=authored.claim,
            inferred_because=authored.inferred_because,
            moved_by=authored.moved_by,
            target=assumptions[position - 1].id,
        )
        for position, authored in enumerate(payload.antitheses, start=1)
    ]

    ctx.store.append(
        ctx.session,
        [
            *attempts.stamped(state.cycle),
            *rivals,
            Reasoning(stage=NAME, cycle=state.cycle, about=",".join(r.id for r in rivals), text=payload.reasoning),
            *attempts.spend,
        ],
    )

    return {"stage": NAME, **continued(conversation)}
