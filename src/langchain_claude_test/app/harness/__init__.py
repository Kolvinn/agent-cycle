"""The inner layer — one model turn over the Claude Agent SDK.

The outer graph owns stage order, state, the cycle boundary, and forking. This
layer owns one turn: which tools exist for it, what each call costs, who
answers an authority-bearing call, and what shape the answer comes back in.
Nothing here knows what frame comes next; nothing in the graph knows what the
model decided inside.

Settled constraints, measured earlier and not re-litigated:

1. **Subscription billing.** ``env`` blanks the API-key variables the CLI would
   otherwise prefer.
2. **An allow-list, never a deny-list.** ``tools=[...]`` names the built-ins a
   frame carries; ``Bash`` is never among them, so a refused call has nowhere
   to route around to.
3. **The meter is a ``PreToolUse`` hook**, which fires for every call before
   any rule or mode — including reads inside the working directory, which
   self-approve and never reach ``can_use_tool``. ``can_use_tool`` is the
   human gate for the authority-bearing in-graph calls only.
4. **Structured output is a synthetic tool call** the gate never sees; it is
   never priced.
"""

from .events import EventSink, HarnessEvent, ListSink
from .protocol import (
    ApprovalRequest,
    Approver,
    FrameInterrupted,
    StageHarness,
    StageRequest,
    TurnResult,
    Verdict,
)

__all__ = [
    "ApprovalRequest",
    "Approver",
    "EventSink",
    "FrameInterrupted",
    "HarnessEvent",
    "ListSink",
    "StageHarness",
    "StageRequest",
    "TurnResult",
    "Verdict",
]
