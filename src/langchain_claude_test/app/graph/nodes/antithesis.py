"""③ antithesis — one pass, one rival per reading, funded at base + N.

*"change the antithesis pass to a single pass that looks at the antithesis of
all assumptions looked at in the previous"* — so this turn attacks every
reading of the cycle and authors a rival for each, in one turn. It continues
the conversation, so everything the case gathered and everything it argued is
in front of the model; the reframe is carried entirely by the brief, which is
why the brief is written in orders. A model cannot be made to stop reading its
own scrollback; where nothing else can bind, the language is the mechanism.

The two budget terms are kept apart: the base funds the hunt, and the N funds
going back over each cited locator — the one leak the reframe cannot close by
itself, because *which* excerpts were chosen was an affirming-frame decision.
"""

from __future__ import annotations

from langgraph.runtime import Runtime

from .. import budget
from ..context import ControlContext
from ..payloads import Antitheses
from ..state import Antithesis, GraphState, Reasoning
from ...harness.protocol import StageRequest
from ._common import continuation, continued, counts, price_line

NAME = "antithesis"

ANTITHESIS_BRIEF = """CREATE THE ANTITHESIS OF EACH OF THESE ASSUMPTIONS AND THEIR FINDINGS.

You built that case. You are now going to attack it, reading by reading. These
are orders.

For EACH of the {n} readings you named, YOU MUST author the rival reading — the
interpretation under which that reading is wrong, not a weaker version of it and
not a quarrel with its details. One rival per reading, in the order you named
them.

YOU MUST NOT defend anything you just said. You were asked to build a case and
you built one. That is finished. Whether you were right is not this turn's
question and you are not being marked on it.

YOU MUST NOT answer that there is nothing to attack. That is not a permitted
output for any reading. If you cannot see the hole, you have not looked hard
enough yet, and the budget below exists for exactly that.

YOU MUST name, for each rival, the call whose result would change your belief
about it. A reading nothing could land on is not a reading.

RE-READ WHAT YOU ALREADY READ. The excerpts you collected are quotable by
anyone; *which* excerpts you chose was a decision made inside the frame you are
now attacking. Part of this budget is funded for that and nothing else.

What you have:

- {pool} points: {base} to hunt with, plus one for each of the {n} readings, so
  you can go back over each of them.
- {prices}.
- Attach what you find with the attach_finding tool as you get it, with
  target set to the NUMBER of the reading the finding argues against (1 to {n}).
  The excerpt is checked against what your calls actually returned.

Give the {n} rivals in your answer, in reading order, and say what you make of
what you found.
"""


class AntithesisFailed(RuntimeError):
    """No attempt returned exactly one rival per reading."""


def rival_id(cycle: int, position: int) -> str:
    return f"x{cycle}.{position}"


def target_resolver(cycle: int, n: int):
    """The model names the reading by its position; the graph names the rival."""

    def resolve(raw: str) -> str | None:
        text = str(raw).strip().lstrip("#")
        if text.isdigit() and 1 <= int(text) <= n:
            return rival_id(cycle, int(text))
        return None

    return resolve


async def antithesis(state: GraphState, runtime: Runtime[ControlContext]) -> dict:
    ctx = runtime.context
    readings = state.current_assumptions()
    n = len(readings)
    pool_name = budget.antithesis_pool(state.cycle)
    cap = budget.antithesis_budget(n, ctx.budgets)
    conversation, fork = continuation(state)

    spent: list = []
    findings: list = []
    correction = ""
    payload = None
    brief = ANTITHESIS_BRIEF.format(
        pool=cap, base=ctx.budgets.antithesis_base, n=n, prices=price_line(ctx.prices)
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
                prior_spend=tuple(state.spend) + tuple(spent),
                said=tuple(state.said),
                node_ids=frozenset(state.node_ids()),
                finding_target=target_resolver(state.cycle, n),
                existing=counts(state, state.cycle),
            )
        )
        spent.extend(result.spend)
        findings.extend(result.findings)
        conversation = result.conversation
        payload = result.payload
        if payload is not None and len(payload.antitheses) == n:
            break
        count = 0 if payload is None else len(payload.antitheses)
        correction = f"That answer gave {count} rivals for {n} readings. Give exactly one per reading, in order."
    else:
        raise AntithesisFailed(f"{ctx.budgets.max_reauthor_attempts + 1} attempts, none giving exactly {n} rivals")

    rivals = [
        Antithesis(
            id=rival_id(state.cycle, position),
            cycle=state.cycle,
            claim=authored.claim,
            inferred_because=authored.inferred_because,
            moved_by=authored.moved_by,
            target=readings[position - 1].id,
        )
        for position, authored in enumerate(payload.antitheses, start=1)
    ]

    return {
        "stage": NAME,
        **continued(conversation),
        "antitheses": rivals,
        "findings": [f.model_copy(update={"cycle": state.cycle}) for f in findings],
        "reasoning": [Reasoning(stage=NAME, cycle=state.cycle, about=",".join(r.id for r in rivals), text=payload.reasoning)],
        "spend": spent,
    }
