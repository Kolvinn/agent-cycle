"""Spend arithmetic. Pure functions over the recorded ledger.

Nothing stores a remaining balance, because a stored balance is a number a node
could return, and the agent never sets its own values. Deriving it means the
only thing an agent can affect is the record of what it already spent.

There is deliberately no function that moves points between pools: unspent
budget is non-transferable across turns, which closes the "when they stop" half
of *"falsification cannot be free"*.

**Every pool name carries its cycle.** The spend channel accumulates across
cycles and a balance is derived by summing every entry with a matching pool
name, so a pool named without its cycle would arrive at the second cycle
already spent to zero by the first.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from ..config import UNKNOWN_CALL_PRICE, Budgets
from .state import SpendEntry


def orientation_pool(cycle: int) -> str:
    return f"orientation:{cycle}"


def assumption_pool(assumption_id: str) -> str:
    """Cycle-scoped already: ids are ``a<cycle>.<position>``."""
    return f"assume:{assumption_id}"


def antithesis_pool(cycle: int) -> str:
    return f"antithesis:{cycle}"


def synthesis_pool(cycle: int) -> str:
    return f"synthesis:{cycle}"


def price_of(call_class: str, prices: Mapping[str, int]) -> int:
    """An unknown class charges the most expensive rate rather than nothing."""
    return prices.get(call_class, UNKNOWN_CALL_PRICE)


def spent_from(spend: Iterable[SpendEntry], pool: str) -> int:
    return sum(e.price for e in spend if e.pool == pool)


def remaining(spend: Iterable[SpendEntry], pool: str, cap: int) -> int:
    return max(0, cap - spent_from(spend, pool))


def affordable(spend: Iterable[SpendEntry], pool: str, cap: int, price: int) -> bool:
    return price <= remaining(spend, pool, cap)


def allocate(assumption_ids: Sequence[str], budgets: Budgets) -> dict[str, int]:
    """Flat, never weighted: cost may not attach to the direction of a conclusion."""
    return {aid: budgets.per_assumption for aid in assumption_ids}


def antithesis_budget(n_assumptions: int, budgets: Budgets) -> int:
    """``base + N``. With three readings and base 5, that is 8."""
    return budgets.antithesis_base + n_assumptions


def thesis_budget(n_assumptions: int, budgets: Budgets) -> int:
    return budgets.per_assumption * n_assumptions


def cycle_total(n_assumptions: int, budgets: Budgets) -> int:
    return thesis_budget(n_assumptions, budgets) + antithesis_budget(n_assumptions, budgets)


def asymmetry_disclosure(n_assumptions: int, budgets: Budgets) -> str:
    """The sentence the synthesis brief must carry every cycle.

    A lopsided evidence set reads as a conclusion; unless the report says the
    budgets were asymmetric, the budget design does the concluding.
    """
    thesis = thesis_budget(n_assumptions, budgets)
    anti = antithesis_budget(n_assumptions, budgets)
    return (
        f"Budgets were asymmetric by design: {thesis} points funded the {n_assumptions} "
        f"reading(s) and {anti} funded the {n_assumptions} rival(s) together "
        f"({budgets.antithesis_base} base + {n_assumptions}). More evidence was gathered "
        f"for these readings than against them because building a case costs more than "
        f"finding one hole — not because the evidence fell that way."
    )


def report(spend: Iterable[SpendEntry], pool: str, cap: int) -> str:
    return f"{pool} used {spent_from(spend, pool)} of {cap}"
