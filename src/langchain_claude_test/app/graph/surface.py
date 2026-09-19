"""Which tools exist in which frame, and which of them wait for the user.

Two questions, and they are not the same one:

**What exists here.** A frame carries the tools its job needs and nothing
else. The surface is assembled per frame at the moment the frame's client
opens, so availability is structural: a call outside the frame's surface is a
call to a tool that does not exist.

**What waits for the user.** The authority-bearing calls. Every one is answered
at the call, inside the turn that made it, and what the user says comes back to
the model as the tool's result. *"A fact isnt a fact until it is explicitly
registered via a user, so all tool calls that register facts/explicits are hitl
approvals."*

The evidence half of every surface is the SDK's own built-in tools. They are
priced, never approved: *"I want tool usage from claude registered to point
values and not have the actual tool use gated in the way it originally was."*
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Literal, Mapping

from ..config import EVIDENCE_TOOLS

#: The three frames.
Stage = Literal["orientate", "antithesis", "synthesis"]

STAGES: tuple[Stage, ...] = ("orientate", "antithesis", "synthesis")

#: The in-process tools that change the store. The server they live on is
#: named so the wire name is ``mcp__graph__<tool>``.
GRAPH_SERVER = "graph"

#: The one ungated write: a finding claims no authority.
FINDING_TOOLS: frozenset[str] = frozenset({"attach_finding"})

#: Ungated growth: a new entity or claim is born provisional and claims
#: nothing, exactly as an assumption does. (Growth option G-2.)
GROWTH_TOOLS: frozenset[str] = frozenset({"add_node"})

#: The authority-bearing calls, answered by the user at the call: every
#: relational edge, every edit of an existing node or edge, every merge,
#: move, delete, verdict and compression.
GATED_TOOLS: frozenset[str] = frozenset(
    {
        "propose_fact",
        "add_edge",
        "update_node",
        "update_edge",
        "delete_node",
        "delete_edge",
        "merge",
        "move_evidence",
        "close_node",
        "supersede",
        "compress",
    }
)

ALTERATION_TOOLS: frozenset[str] = FINDING_TOOLS | GROWTH_TOOLS | GATED_TOOLS

#: Reading the graph is free: it is our text, already paid for (Q-8).
READ_TOOLS: frozenset[str] = frozenset({"graph_search", "graph_neighbours"})

GRAPH_TOOLS: frozenset[str] = ALTERATION_TOOLS | READ_TOOLS

#: Per frame: which built-ins exist, and which in-graph tools exist.
#:
#: ``orientate`` surveys and keeps what it read as findings on the question,
#: and names the entities it found. ``antithesis`` gathers evidence against
#: the assumptions. Neither can alter what exists. ``synthesis`` holds everything: it is a conversation
#: with the user, in which what the graph becomes is decided together.
STAGE_BUILTINS: Mapping[Stage, tuple[str, ...]] = MappingProxyType(
    {
        "orientate": EVIDENCE_TOOLS,
        "antithesis": EVIDENCE_TOOLS,
        "synthesis": EVIDENCE_TOOLS,
    }
)

STAGE_GRAPH_TOOLS: Mapping[Stage, frozenset[str]] = MappingProxyType(
    {
        # The surveying frames grow the graph (findings, entities, claims) and
        # may put a relation to the user; nothing else of theirs waits.
        "orientate": READ_TOOLS | FINDING_TOOLS | GROWTH_TOOLS | {"add_edge"},
        "antithesis": READ_TOOLS | FINDING_TOOLS | GROWTH_TOOLS | {"add_edge"},
        "synthesis": READ_TOOLS | ALTERATION_TOOLS,
    }
)


def wire_name(tool: str) -> str:
    """The name the SDK gives an in-process tool: ``mcp__<server>__<tool>``."""
    return f"mcp__{GRAPH_SERVER}__{tool}"


def bare_name(tool_name: str) -> str:
    """Strip the MCP prefix if present; built-ins come through unchanged."""
    prefix = f"mcp__{GRAPH_SERVER}__"
    return tool_name[len(prefix):] if tool_name.startswith(prefix) else tool_name


def gated(tool_name: str) -> bool:
    return bare_name(tool_name) in GATED_TOOLS


def available(stage: Stage, tool_name: str, withheld: frozenset[str] = frozenset()) -> bool:
    """Whether a call to this tool exists in this frame, on this turn.

    ``withheld`` names in-graph tools the frame has taken off the surface for
    one turn — how synthesis keeps its opening exchange to text.
    """
    bare = bare_name(tool_name)
    if bare in withheld:
        return False
    return bare in STAGE_BUILTINS[stage] or bare in STAGE_GRAPH_TOOLS[stage]
