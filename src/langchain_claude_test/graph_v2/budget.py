"""Spend arithmetic. Pure functions over the recorded ledger.

Everything here derives from :attr:`~.state.Cycle.spend` against the caps in
:class:`~.context.Budgets`. Nothing stores a remaining balance, because a stored
balance is a number a node could return, and the agent never sets its own
values. Deriving it means the only thing an agent can affect is the
record of what it already spent.

**There is deliberately no function here that moves points between pools.** Two
properties of the design come from that absence rather than from a rule:

- *Unspent budget is non-transferable across turns.* Turn 1's remainder cannot
  fund turn 2 because it is a different turn and there is no pool to return it
  to. That closes the "when they stop" half of *falsification cannot be free*: an agent cannot
  abandon a reading early to concentrate spend on a preferred one.
- *Unspent orientation allowance cannot become assumption budget.* Stages ② and
  ③ share a turn, so no turn boundary separates them — this one holds because
  the caps are graph-set and the wide pool and the deep caps are different
  pools, not one pool spent in two places.

**The interrupt-replay rule** (framework-fit §3.2, measured in
`spike_07_interrupt_replay.py`): the body of a node above an ``interrupt()``
re-runs on resume while the state update commits once. So a priced node debits
by *returning* state, never by a side effect. Every function here is pure, which
is what makes that rule cheap to keep.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from .context import UNKNOWN_CALL_PRICE, Budgets
from .state import SpendEntry

# ---------------------------------------------------------------------------
# Pool names
# ---------------------------------------------------------------------------
#
# A pool is an identity, not a number — the number is a cap in context and the
# balance is derived from the recorded spend against it.
#
# **Every pool name carries its cycle**, and that is not decoration. The spend
# channel accumulates across cycles, and a balance is derived by summing every
# entry with a matching pool name. A pool called plainly ``orientation`` would
# therefore arrive at the second cycle already spent to zero by the first, and
# the frame would be refused its first lookup with nothing in the record to say
# why. Per-reading pools were cycle-scoped already, because a reading's id is;
# these two were not, and the bug was invisible for exactly as long as no run
# reached a second cycle.


def orientation_pool(cycle: int) -> str:
    """The wide pass's pool for one cycle."""
    return f"orientation:{cycle}"


def antithesis_pool(cycle: int) -> str:
    """The rival's pool for one cycle."""
    return f"antithesis:{cycle}"


def synthesis_pool(cycle: int) -> str:
    """The synthesis conversation's pool, for one cycle.

    One pool across every exchange of the conversation rather than one per
    exchange, so looking is bounded while talking is not.
    """
    return f"synthesis:{cycle}"

# There is deliberately no pool name for fact extraction. It is no longer a
# stage of its own: it happens inside the synthesis conversation, on your words,
# and draws on that conversation's pool like everything else there.


def price_of(call: str, prices: Mapping[str, int]) -> int:
    """What one call costs.

    An unknown call class charges :data:`~.context.UNKNOWN_CALL_PRICE` rather
    than nothing. An unpriced call is the hole a budget leaks through, and
    defaulting low is how it widens.
    """
    return prices.get(call, UNKNOWN_CALL_PRICE)


def assumption_pool(assumption_id: str) -> str:
    """The pool name for one reading's allocation.

    Cycle-scoped without being told the cycle: the reading's id already carries
    it, because the graph assigns ids as ``a<cycle>.<position>``.
    """
    return f"assume:{assumption_id}"


def spent_from(spend: Iterable[SpendEntry], pool: str) -> int:
    """Total drawn from one pool."""
    return sum(e.price for e in spend if e.pool == pool)


def remaining(spend: Iterable[SpendEntry], pool: str, cap: int) -> int:
    """What is left in one pool. Never negative — a gate refuses before this."""
    return max(0, cap - spent_from(spend, pool))


def affordable(spend: Iterable[SpendEntry], pool: str, cap: int, price: int) -> bool:
    """Whether one more call of this price fits.

    This is the predicate ``can_use_tool`` answers. Exhaustion ends the stage
    (exhaustion forces a reply) rather than overdrawing it.
    """
    return price <= remaining(spend, pool, cap)


def allocate(assumption_ids: Sequence[str], budgets: Budgets) -> dict[str, int]:
    """Per-assumption allocations — the restriction is per assumption, and the
    graph sets the number, never the agent.

    Flat rather than weighted, because falsification cannot be free: cost may not be attached to
    the direction of a conclusion, and a weighting would have to come from
    somewhere — the agent's confidence being the only available signal.
    """
    return {aid: budgets.per_assumption for aid in assumption_ids}


def antithesis_budget(n_assumptions: int, budgets: Budgets) -> int:
    """``base + N``. With three assumptions and base 5, that is 8.

    The two terms answer different problems, and it is worth keeping them
    separate rather than collapsing to one number:

    - ``N`` ≈ one re-read *around* each cited locator, de-biasing the evidence
      *selection* turn 1 made — the residual leak the boundary cannot close.
    - ``base`` ≈ the working pool for hunting the misreading the whole set
      shares, which is the only thing a single antithesis node can catch.
    """
    return budgets.antithesis_base + n_assumptions


def thesis_budget(n_assumptions: int, budgets: Budgets) -> int:
    """``5N`` — the whole assumption turn's funding."""
    return budgets.per_assumption * n_assumptions


def cycle_total(n_assumptions: int, budgets: Budgets) -> int:
    """``6N + 5``. For comparison, an antithesis per assumption would be ``10N``.

    That doubling is what the design rejects — an agent cannot hold right and
    wrong in one task — and it worsens exactly as breadth grows, which is the
    breadth that going wide was meant to buy.
    """
    return thesis_budget(n_assumptions, budgets) + antithesis_budget(n_assumptions, budgets)


def asymmetry_disclosure(n_assumptions: int, budgets: Budgets) -> str:
    """The sentence stage ⑤ must include every time.

    The asymmetry is defensible — building a case is expensive, finding one hole
    is cheap — but it means the evidence set arriving at stage ⑤ is lopsided by
    construction, and a lopsided evidence set *reads* as a conclusion. Unless
    the report says so, the budget design quietly does the concluding the agent is
    forbidden from doing. Returned as text because it is part of the disposition
    and not a graph object — options are never part of the graph.
    """
    thesis = thesis_budget(n_assumptions, budgets)
    anti = antithesis_budget(n_assumptions, budgets)
    return (
        f"Budgets were asymmetric by design: {thesis} points funded the {n_assumptions} "
        f"assumption(s) and {anti} funded the single antithesis "
        f"({budgets.antithesis_base} base + {n_assumptions}). More evidence was gathered "
        f"for these readings than against them because building a case costs more than "
        f"finding one hole — not because the evidence fell that way."
    )


def report(spend: Iterable[SpendEntry], pool: str, cap: int) -> str:
    """"assumption 2 used 5 of 5" — the line that crosses the turn boundary.

    A fact about the agent's own spending, and the one kind of closing the agent
    may do: it may close an assumption's *budget*, never its truth.
    """
    return f"{pool} used {spent_from(spend, pool)} of {cap}"
