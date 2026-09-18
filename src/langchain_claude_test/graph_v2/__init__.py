"""The budgeted-flow control graph — LangGraph outside, the Agent SDK inside.

The design this implements is `docs/design/budgeted-flow-2026-09-17.md`; the
reason it is built on LangGraph rather than on Pydantic AI is
`docs/design/framework-fit-2026-09-18.md`. Neither is restated here, but every
module carries the register marks — **E** explicit, **O** observed, **A**
assumption, **X** exploration required — so a reader can tell what is the
user's decision, what was read out of this repository, and what is still open.
Two new questions were raised by writing this down; they are marked **Q** and
listed in `README.md`.

The package is separate from `session/` rather than replacing it. `session/`
runs the fixed-order pipeline this design supersedes, and it works — the tests
in `tests/` encode its contract deliberately. Deleting it before this one runs
would trade something that works for something that does not.

**Where things live, and why that split:**

- `context.py` — caps, prices and the harness. Runtime context, so a node can
  read them and no node can write them (the agent never sets its own values).
- `state.py` — the records, and which channels accumulate. The store is pydantic
  rather than a live networkx graph, because this state is checkpointed and
  forked.
- `views.py` — what each node may *see*. The file the framework choice was made
  for.
- `surface.py` — which graph-writes exist in which stage (tool availability is gated by stage).
- `budget.py` — pure spend arithmetic, derived from the recorded ledger.
- `harness.py` — the one model call: allow-listed tools, the meter, the typed
  payload, subscription auth.
- `nodes.py` — the stages, each with its view and its payload.
- `graph.py` — the edge list. The flow *is* this object, not a docstring about
  one.
"""

from __future__ import annotations

from .context import Budgets, BudgetNotSet, ControlContext
from .graph import build, check_topology, compile_cycle, render, serializer
from .harness import StageHarness, StageRequest, TurnResult, UnbuiltHarness
from .state import Crossing, Cycle

__all__ = [
    "BudgetNotSet",
    "Budgets",
    "ControlContext",
    "Crossing",
    "Cycle",
    "StageHarness",
    "StageRequest",
    "TurnResult",
    "UnbuiltHarness",
    "build",
    "check_topology",
    "compile_cycle",
    "render",
    "serializer",
]
