"""Which graph-writes exist in which stage (tool availability is gated by stage).

> *"For the most part, the availablities of the graph tools (like write
> assumption, compress fact, etc.) are gated by the stage of the agent graph."*

Availability and volume are different mechanisms and this file is only the
first. Pricing removed the per-call approval gate on depth and severity;
staging adds that a stage simply does not carry tools outside its job. One is discretion
at the moment of the call, the other is the shape of the surface.

**The names below are not settled.** `write assumption` and `compress fact` are
the user's own examples; `compress`, `discard` and `register` come from the
description of the present stage;
the rest are the agent's guesses at what each stage needs. Read the table as the
shape of the surface, not as a built API.

Why this table can be trusted at all.** It only binds if the model cannot route
around it, and deny-listing the CLI's built-in tools *failed under test* —
blocking `Read` just made the model reach for `Bash`. So the mapping here is
enforced by handing the harness an in-process tool server carrying exactly this
set, with no built-in surface at all to route through. That is a hard dependency, not a preference.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Literal, Mapping

from .state import Stage

GraphWrite = Literal[
    # stage ①
    "register_prompt",  # verbatim, no inference — the only authority-bearing write
    "propose_fact",  # HITL, always (a fact is not a fact until the user registers it)
    # stage ③ / ④
    "write_assumption",
    "write_antithesis",
    "attach_finding",
    # stage ⑤ — the widest surface (what the present stage presents)
    "promote_fact",
    "close_node",
    "supersede",
    "compress",
    "discard",
    "reify",
]

#: The surface per stage. Stage ② is empty, and that is the point: *"it carries
#: no graph-write tools at all, which is what makes 'forms no claim'
#: enforceable rather than merely intended."* (orientation forms no claim)
STAGE_SURFACE: Mapping[Stage, frozenset[GraphWrite]] = MappingProxyType(
    {
        "extract": frozenset({"register_prompt", "propose_fact"}),
        "orient": frozenset(),
        "assume": frozenset({"write_assumption", "attach_finding"}),
        "antithesis": frozenset({"write_antithesis", "attach_finding"}),
        "present": frozenset(
            {
                "promote_fact",
                "close_node",
                "supersede",
                "compress",
                "discard",
                "reify",
            }
        ),
    }
)

#: Writes that always need a human: *"all tool calls that register
#: facts/explicits are hitl approvals."* Authority-changing calls are the clear
#: case.
HITL_ALWAYS: frozenset[GraphWrite] = frozenset(
    {"propose_fact", "promote_fact", "close_node", "supersede"}
)

#: Writes whose approval policy is not settled. Compression is the hard case:
#: it registers no fact, yet it decides what the next cycle can still see, which
#: is a kind of authority.
#:
#: These now carry a **default** rather than refusing, because the standing
#: instruction is to pick defaults and mark them: a base loop has to turn over
#: before this level of detail is worth settling. The default is *approval
#: required* — the direction whose failure mode is friction rather than silent
#: loss — and it is overridable per run, because it is a placeholder.
HITL_UNRESOLVED: frozenset[GraphWrite] = frozenset({"compress", "discard", "reify"})

#: The placeholder answer for :data:`HITL_UNRESOLVED`. Not a decision.
DEFAULT_UNRESOLVED_HITL = True

#: The agent may not close a node in either direction. ``close_node``
#: is on the surface because the *user* may close one through an approved call;
#: it is never an agent-initiated write, and the proposed exhausted-but-open
#: split is the
#: reason the name survives at all: the agent may close an assumption's
#: *budget*, never its truth.
AGENT_MAY_NEVER_INITIATE: frozenset[GraphWrite] = frozenset({"close_node", "promote_fact"})


def available(stage: Stage) -> frozenset[GraphWrite]:
    """The graph-writes that exist in this stage. Everything else is absent."""
    return STAGE_SURFACE[stage]


def needs_approval(
    write: GraphWrite, *, treat_unresolved_as_hitl: bool = DEFAULT_UNRESOLVED_HITL
) -> bool:
    """Whether this write must be approved before it applies.

    Registering or promoting a fact always needs approval — *"A fact isnt a fact
    until it is explicitly registered via a user, so all tool calls that register
    facts/explicits are hitl approvals."* Compression and discard fall to the
    placeholder above until the question is worth settling.
    """
    if write in HITL_ALWAYS:
        return True
    if write in HITL_UNRESOLVED:
        return treat_unresolved_as_hitl
    return False
