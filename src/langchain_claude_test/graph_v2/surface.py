"""Which tools exist in which frame, and which of them wait for you.

Two questions, and they are not the same one:

**What exists here.** A frame carries the tools its job needs and nothing else.
Not a restraint on a wide surface — the surface is assembled per frame.

**What waits for you.** The authority-bearing calls: registering a fact,
promoting one, closing a node, superseding, and the compaction calls that decide
what the next cycle can still see. Every one of them is answered by you *at the
call*, inside the turn that made it, and what you say comes back to the model as
the tool's result.

**Nothing is held back for later.** There is no queue. An earlier shape gathered
the authority-bearing calls and resolved them after the model had finished, which
was a way around pausing a graph mid-turn — and the pause was the problem, not
the calls. Gating at the call means the model can propose freely, because
proposing is not doing: *"since the tools are gated by hitl anyway, we dont have
to worry about premature calling."*

**Why this table can be trusted at all.** It only binds if the model cannot route
around it, and deny-listing the built-in tools *failed under test* — blocking
the read tool just made the model reach for the shell. So the surface is enforced
by handing the harness a tool server carrying exactly the set below, with no
built-in surface at all to route through. A hard dependency, not a preference.

**The names are not settled.** Some are your examples, some describe the job.
Read the table as the shape of the surface, not as a built API.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Literal, Mapping

#: The four frames. The label is the stage — there is no longer a second, coarser
#: taxonomy sitting beside the node names.
Stage = Literal["orientate", "assume", "antithesis", "synthesis"]

#: Calls that go and look. Priced, and their output returns to the model in-turn.
#:
#: **Named after the price classes, which are your words**, not the other way
#: round: *"might be -2, survey skills might mb -1 (like ls, tree, etc.),
#: webfetch = 3."* The tool names here were a guess; the classes were given. So a
#: tool is named for what it costs, and the price line in every prompt is about
#: calls that actually exist.
Evidence = Literal["read", "survey", "webfetch"]

#: Calls that change the store.
Alteration = Literal[
    # the one working write — ungated, because a finding claims no authority
    "attach_finding",
    # authority-bearing — answered by you at the call
    "propose_fact",
    "promote_fact",
    "close_node",
    "supersede",
    "compress",
    "discard",
]

Tool = Evidence | Alteration

#: Alterations that take effect the moment they are called, without asking.
UNGATED: frozenset[Alteration] = frozenset({"attach_finding"})

#: Alterations you answer, at the call. *"A fact isnt a fact until it is
#: explicitly registered via a user, so all tool calls that register
#: facts/explicits are hitl approvals."* Compaction is in here on the same
#: ground: it registers no fact, but deciding what the next cycle can still see
#: is a kind of authority — and under the shape where the graph is what carries
#: between cycles, it is the most consequential authority there is.
GATED: frozenset[Alteration] = frozenset(
    {"propose_fact", "promote_fact", "close_node", "supersede", "compress", "discard"}
)

#: The surface per frame.
#:
#: Two things in this table carry as much as the entries.
#:
#: ``assume`` holds no fact-touching call at all: a reading's turn gathers
#: evidence and cannot promote what it finds, which keeps a finding from becoming
#: a fact by enthusiasm.
#:
#: ``synthesis`` holds **everything**. It is the widest surface in the cycle, and
#: that is the point of the stage rather than a relaxation of the rules: it is a
#: conversation with you, in which the two of you decide what the graph should
#: become and what the next cycle carries. It can look things up because you may
#: ask it to, and every call that touches authority is answered by you as it is
#: made.
STAGE_TOOLS: Mapping[Stage, frozenset[Tool]] = MappingProxyType(
    {
        "orientate": frozenset({"read", "survey", "webfetch"}),
        "assume": frozenset({"read", "survey", "webfetch", "attach_finding"}),
        "antithesis": frozenset({"read", "survey", "webfetch", "attach_finding"}),
        "synthesis": frozenset(
            {
                "read",
                "survey",
                "webfetch",
                "propose_fact",
                "promote_fact",
                "close_node",
                "supersede",
                "compress",
                "discard",
            }
        ),
    }
)

#: The agent may not close a node in either direction, and may not promote a
#: finding to a fact on its own motion.
#:
#: **These live on the last frame, because that is the frame that reads your
#: words.** They used to sit on the first one for exactly the same reason, when
#: the first frame was the one handed your message. It isn't: the first frame is
#: handed a package that the last frame and you built together. So the binding
#: problem is solved where it actually arises — the agent's reading of what you
#: said only takes effect as a call you answer, and answering it confirms the
#: *binding* rather than the claim. No silent reinterpretation is reachable.
AGENT_MAY_NEVER_INITIATE: frozenset[Alteration] = frozenset(
    {"promote_fact", "close_node", "supersede"}
)

#: The ceiling on how many readings may exist is **not** enforced here. It is a
#: property of the whole set rather than of any one call, and a per-call refusal
#: could stop a fourth reading but could never produce a second — so it is bounded
#: by the shape of the answer the first frame must return, and a violation is a
#: retry. Writing a reading is therefore not a tool at all — and neither is
#: writing the rival, for the same reason: exactly one is a count, and no refusal
#: at a call can produce one that was not offered.


def available(stage: Stage) -> frozenset[Tool]:
    """The tools that exist in this frame. Everything else is absent."""
    return STAGE_TOOLS[stage]


def gated(tool: Tool) -> bool:
    """Whether this call is answered by you, or takes effect as it is made."""
    return tool in GATED


def evidence_tools(stage: Stage) -> frozenset[Tool]:
    """The priced half of a frame's surface. Empty means the frame cannot look."""
    return frozenset({t for t in STAGE_TOOLS[stage] if t in ("read", "survey", "webfetch")})
