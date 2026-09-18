"""Spike 6 — is the budgeted-flow control graph expressible declaratively?

The framework's job in this project is not to supply an agent loop. It is to be
the wrapper of control around the Agent SDK harness: stages as nodes, turns as
checkpoint boundaries, and semantic state we own. So the question is whether
the four mechanisms the design relies on are graph primitives or hand-rolled
conventions.

No model is called. Four checks:

  A. pydantic state with an accumulating channel (the ledger grows)
  B. per-node `input_schema` — a node that *cannot* see part of the state,
     which makes the turn-2 context edit a type declaration rather than an
     instruction the model is trusted to follow
  C. `interrupt()` inside a node — approval on the call, resumed by value
  D. fork from a chosen prior checkpoint — turn 2 from an edited state

Run:  .venv/bin/python scripts/spikes/spike_06_control_graph.py
"""

from __future__ import annotations

import operator
import sys
from typing import Annotated

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field

RESULTS: list[tuple[str, bool]] = []


def check(label: str, ok: bool, detail: str) -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    for line in detail.strip().splitlines():
        print(f"         {line}")
    print()
    RESULTS.append((label, ok))


class Flow(BaseModel):
    """The state we control. One channel accumulates, the rest overwrite."""

    prompt: str = ""
    #: The affirming transcript — the thing the antithesis must not inherit.
    thesis_reasoning: Annotated[list[str], operator.add] = Field(default_factory=list)
    #: What crosses the turn boundary.
    assumptions: Annotated[list[str], operator.add] = Field(default_factory=list)
    spent: int = 0
    approved: list[str] = Field(default_factory=list)


class AntithesisView(BaseModel):
    """The projection the antithesis stage is handed. No `thesis_reasoning`."""

    assumptions: list[str] = Field(default_factory=list)
    spent: int = 0


#: Recorded by the node rather than asserted inside it, so the check can quote
#: what the node genuinely received.
SEEN_BY_ANTITHESIS: dict[str, object] = {}


def assume(state: Flow) -> dict:
    return {
        "assumptions": ["A: the runner owns the order"],
        "thesis_reasoning": ["I felt confident because phases.py says so"],
        "spent": state.spent + 5,
    }


def gate(state: Flow) -> dict:
    # Approval is on the *call*, not on a message: the node names the call it
    # wants to make and waits. Nothing above the wait may cost anything —
    # see spike 7 for why.
    decision = interrupt({"call": "read", "path": "session/runner.py", "price": 2})
    return {"approved": [str(decision)], "spent": state.spent + 2}


def antithesis(state: AntithesisView) -> dict:
    SEEN_BY_ANTITHESIS["fields"] = sorted(type(state).model_fields)
    SEEN_BY_ANTITHESIS["has_thesis_reasoning"] = hasattr(state, "thesis_reasoning")
    return {"assumptions": ["X: or the order is an artefact of the harness"]}


def build():
    builder = StateGraph(Flow)
    builder.add_node("assume", assume)
    builder.add_node("gate", gate)
    builder.add_node("antithesis", antithesis, input_schema=AntithesisView)
    builder.add_edge(START, "assume")
    builder.add_edge("assume", "gate")
    builder.add_edge("gate", "antithesis")
    builder.add_edge("antithesis", END)
    return builder.compile(checkpointer=InMemorySaver())


def main() -> int:
    print("=" * 78)
    print("  Spike 6 — control-graph primitives under LangGraph")
    print("=" * 78)

    app = build()
    config = {"configurable": {"thread_id": "spike-6"}}

    paused = app.invoke({"prompt": "why is the order fixed?"}, config)
    interrupts = paused.get("__interrupt__")
    check(
        "C. interrupt() suspends mid-node and surfaces the call for approval",
        bool(interrupts) and interrupts[0].value.get("call") == "read",
        f"payload: {interrupts[0].value if interrupts else None}",
    )

    final = app.invoke(Command(resume="approved-by-user"), config)
    check(
        "C2. resume threads the decision back into the same node",
        final["approved"] == ["approved-by-user"] and final["spent"] == 7,
        f"approved={final['approved']} spent={final['spent']} (5 + 2)",
    )

    check(
        "A. pydantic state + reducer channel accumulates across nodes",
        len(final["assumptions"]) == 2,
        f"assumptions={final['assumptions']}",
    )

    check(
        "B. per-node input_schema hides state from a node structurally",
        SEEN_BY_ANTITHESIS.get("has_thesis_reasoning") is False,
        f"the antithesis node received fields {SEEN_BY_ANTITHESIS.get('fields')}\n"
        f"while the full state still carries "
        f"thesis_reasoning={final['thesis_reasoning']}",
    )

    history = list(app.get_state_history(config))
    target = next((s for s in reversed(history) if s.next == ("gate",)), None)
    if target is None:
        check("D. fork from a chosen checkpoint", False, "no checkpoint with next=('gate',)")
    else:
        # Writing to a *past* checkpoint branches rather than overwrites, which
        # is what a turn boundary needs: the same run, an edited context.
        forked = app.update_state(target.config, {"thesis_reasoning": []}, as_node="assume")
        snapshot = app.get_state(forked)
        old_id = target.config["configurable"]["checkpoint_id"]
        new_id = snapshot.config["configurable"]["checkpoint_id"]
        check(
            "D. fork a new branch from a chosen checkpoint",
            new_id != old_id,
            f"{len(history)} checkpoints; forked at next={snapshot.next}\n"
            f"branch {new_id[-12:]} from {old_id[-12:]} (compared in full)",
        )

    passed = sum(ok for _, ok in RESULTS)
    print("=" * 78)
    print(f"  {passed}/{len(RESULTS)} mechanisms confirmed")
    print("=" * 78)
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
