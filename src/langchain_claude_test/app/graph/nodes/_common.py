"""What every frame shares: how a turn continues the cycle's conversation, and
how the prices are stated."""

from __future__ import annotations

from collections.abc import Mapping

from ...config import EVIDENCE_TOOL_CLASS
from ...harness.protocol import Counts
from ..state import GraphState


def price_line(prices: Mapping[str, int]) -> str:
    """The tools the frame carries and what each costs, as one line."""
    parts = [f"{tool} costs {prices.get(klass, '?')}" for tool, klass in EVIDENCE_TOOL_CLASS.items()]
    return ", ".join(parts)


def continuation(state: GraphState) -> tuple[str, bool]:
    """The conversation a continuing frame resumes, and whether it must fork."""
    return state.conversation, state.fork_conversation


def continued(conversation: str) -> dict:
    """The delta every continuing frame returns about the conversation."""
    return {"conversation": conversation, "fork_conversation": False}


def counts(state: GraphState, cycle: int | None = None) -> Counts:
    """This cycle's record counts, so a turn continues the id sequence."""
    c = state.cycle if cycle is None else cycle
    return Counts(
        findings=sum(1 for f in state.findings if f.cycle == c),
        proposals=sum(1 for p in state.proposed if p.cycle == c),
        explicits=sum(1 for e in state.explicits if e.cycle == c),
    )
