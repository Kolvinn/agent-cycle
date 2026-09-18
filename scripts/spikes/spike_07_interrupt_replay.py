"""Spike 7 — does resuming a LangGraph interrupt re-run the node from the top?

This matters more here than in most designs. If a stage debits the budget
*before* it waits for approval, and resume replays the node, the debit lands
twice and the priced-call ledger is wrong. The same class of bug already bit
`langchain-claude-cli`, whose MCP handler carries an "may be invoked twice"
comment for exactly this reason.

The answer is that the pre-`interrupt()` body **does** re-run, while state
updates commit once. So a debit belongs in a state update, never in a side
effect performed above the wait.

Costs nothing — no model is called. Run:

    .venv/bin/python scripts/spikes/spike_07_interrupt_replay.py
"""

from __future__ import annotations

import operator
import sys
from typing import Annotated

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

#: Appended to by the node, so replay is observed rather than reasoned about.
SIDE_EFFECTS: list[str] = []


class State(BaseModel):
    debits: Annotated[list[int], operator.add] = Field(default_factory=list)
    approved: list[str] = Field(default_factory=list)


def priced_call(state: State) -> dict:
    SIDE_EFFECTS.append("above-the-wait")
    decision = interrupt({"call": "read", "path": "session/runner.py", "price": 2})
    SIDE_EFFECTS.append("below-the-wait")
    return {"debits": [2], "approved": [str(decision)]}


def main() -> int:
    print("=" * 78)
    print("  Spike 7 — interrupt replay, and where a debit is safe")
    print("=" * 78)

    builder = StateGraph(State)
    builder.add_node("priced_call", priced_call)
    builder.add_edge(START, "priced_call")
    builder.add_edge("priced_call", END)
    app = builder.compile(checkpointer=InMemorySaver())

    config = {"configurable": {"thread_id": "spike-7"}}
    first = app.invoke({}, config)
    paused = first.get("__interrupt__")
    print(f"  paused with        : {paused[0].value if paused else None}")

    final = app.invoke(Command(resume="approved-by-user"), config)
    print(f"  side effects, in order : {SIDE_EFFECTS}")
    print(f"  committed debits       : {final['debits']}")
    print(f"  approval recorded      : {final['approved']}")

    replays = SIDE_EFFECTS.count("above-the-wait")
    committed_once = final["debits"] == [2]
    print()
    print(f"  [{'PASS' if replays == 2 else 'FAIL'}] the body above interrupt() ran {replays}x")
    print(f"  [{'PASS' if committed_once else 'FAIL'}] the state update committed once: {final['debits']}")
    print()
    print("  Rule: debit by returning state. Anything above interrupt() must be")
    print("  idempotent — no ledger write, no priced SDK call.")
    return 0 if (replays == 2 and committed_once) else 1


if __name__ == "__main__":
    sys.exit(main())
