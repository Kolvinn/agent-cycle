"""The budgeted-flow control graph — LangGraph outside, the Agent SDK inside.

The design this implements is `docs/design/budgeted-flow-2026-09-17.md`; the
reason it is built on LangGraph rather than on Pydantic AI is
`docs/design/framework-fit-2026-09-18.md`. Neither is needed to read the code:
where a rule came from the user, the user's own words are quoted at the place
the rule is enforced, rather than cited by a code that only resolves elsewhere.

The package is separate from `session/` rather than replacing it. `session/`
runs the fixed-order pipeline this design supersedes, and it works — the tests
in `tests/` encode its contract deliberately. Deleting it before this one runs
would trade something that works for something that does not.

**Where things live, and why that split:**

- `context.py` — caps, prices and the harness. Runtime context, so a node can
  read them and no node can write them (the agent never sets its own values).
- `state.py` — the records, and which channels accumulate. The store is pydantic
  rather than a live networkx graph, because this state is checkpointed and
  forked. Every node takes the whole of it; there are no sub-views.
- `surface.py` — which tools exist in which frame, and which of them wait for
  you. Alterations are tool calls, never fields on an answer.
- `budget.py` — pure spend arithmetic, derived from the recorded ledger.
- `harness.py` — the one model call: allow-listed tools, the meter that prices
  and charges before the call runs, the gate that puts an authority-bearing call
  to you inside the live turn, the typed payload, subscription auth.
- `package.py` — the one place state becomes text: what a cycle hands the next,
  once the conversation behind it has been thrown away.
- `nodes/` — one module per frame. A frame is a stance the model is put into,
  with its own prompt, its own tool surface and its own pool.
- `graph.py` — the edge list, and nothing else. The flow *is* this object, not
  a docstring about one.
"""

from __future__ import annotations

from .context import Budgets, BudgetNotSet, ControlContext
from .graph import build, check_topology, compile_cycle, render, serializer
from .harness import (
    Approver,
    CallGate,
    NobodyApproves,
    StageHarness,
    StageRequest,
    TurnResult,
    UnbuiltHarness,
    Verdict,
)
from .state import Cycle

__all__ = [
    "Approver",
    "BudgetNotSet",
    "Budgets",
    "CallGate",
    "ControlContext",
    "Cycle",
    "NobodyApproves",
    "StageHarness",
    "StageRequest",
    "TurnResult",
    "UnbuiltHarness",
    "Verdict",
    "build",
    "check_topology",
    "compile_cycle",
    "render",
    "serializer",
]
