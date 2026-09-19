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

from collections.abc import Iterable, Mapping

from ..config import UNKNOWN_CALL_PRICE, Budgets
from .state import SpendEntry


def orientation_pool(cycle: int) -> str:
    return f"orientation:{cycle}"


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


def orientation_budget(budgets: Budgets) -> int:
    """The survey's pool: its own base plus the allowance of every assumption it
    may name. Flat, never weighted, and fixed before any assumption exists, so
    cost cannot attach to the direction of a conclusion."""
    return budgets.orientation_base + budgets.per_assumption * budgets.max_assumptions


def antithesis_budget(n_assumptions: int, budgets: Budgets) -> int:
    """``base + N``. With three assumptions and base 5, that is 8."""
    return budgets.antithesis_base + n_assumptions


def thesis_budget(budgets: Budgets) -> int:
    """What funded the affirming side: the whole of the orientate pool."""
    return orientation_budget(budgets)


def cycle_total(n_assumptions: int, budgets: Budgets) -> int:
    return thesis_budget(budgets) + antithesis_budget(n_assumptions, budgets) + budgets.synthesis_points


def asymmetry_disclosure(n_assumptions: int, budgets: Budgets) -> str:
    """The sentence the synthesis brief must carry every cycle.

    A lopsided evidence set reads as a conclusion; unless the report says the
    budgets were asymmetric, the budget design does the concluding.
    """
    thesis = thesis_budget(budgets)
    anti = antithesis_budget(n_assumptions, budgets)
    return (
        f"Budgets were asymmetric by design: {thesis} points funded the survey that "
        f"produced the {n_assumptions} assumption(s) and {anti} funded the {n_assumptions} "
        f"rival(s) together ({budgets.antithesis_base} base + {n_assumptions}). More was "
        f"gathered around these assumptions than against them because surveying costs "
        f"more than finding one hole — not because the evidence fell that way."
    )


def report(spend: Iterable[SpendEntry], pool: str, cap: int) -> str:
    return f"{pool} used {spent_from(spend, pool)} of {cap}"
