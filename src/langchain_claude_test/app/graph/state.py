"""The records, and the cycle's working set.

**The records are the store; the thought graph is a view.** Every record here
is one pydantic model, appended to the project's operation log
(``store.py``) by the frame that authored it and never edited in place. The
networkx view (``thought.py``) and the package (``package.py``) are built from
the log on demand, so they can never drift from what was saved.

**The thread state is the working set, not the graph.** LangGraph checkpoints
and forks :class:`GraphState`, and it holds only what one session's cycle
needs to carry between runs: the cycle number, the pointer, the conversation,
the question and what the user said this cycle. The graph itself is shared by
every session of the project, which is why it does not live here — *"such
that only the correct data is maintained across sessions"*.

**Cycles are the graph's, not the thread's.** Two sessions opening a cycle
each get their own number from the log, so every id (``a3.1``, ``f3.2``) is
unique across the project.
"""

from __future__ import annotations

import operator
from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .surface import Stage

ParkReason = Literal["denied", "unanswered"]


# ---------------------------------------------------------------------------
# Records — the cycle itself
# ---------------------------------------------------------------------------


class Cycle(BaseModel):
    """One cycle opened on the shared graph: its number, who opened it, on what.

    The number is allocated by the log under its lock, so it is the project's
    sequence and not any one thread's. The question node ``q<number>`` is this.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: int = Field(ge=1)
    session: str = ""
    question: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Records — authority
# ---------------------------------------------------------------------------


class Explicit(BaseModel):
    """The user's own words, approved. The only authority in the state.

    Frozen because an explicit that can be edited after approval is not an
    explicit — the user approved a specific string.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    quote: str = Field(min_length=1, description="Verbatim span of a user message.")
    cycle: int = 0
    #: Claims this fact grounds — ``grounds`` edges fact→claim.
    supports: tuple[str, ...] = ()


class Candidate(BaseModel):
    """An extraction-pass output. Carries no authority until approved."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    quote: str = Field(min_length=1)


class Parked(BaseModel):
    """A candidate that did not become explicit, and why."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate: Candidate
    reason: ParkReason
    note: str = ""
    cycle: int = 0


# ---------------------------------------------------------------------------
# Records — what the frames author
# ---------------------------------------------------------------------------


class Assumption(BaseModel):
    """One assumption about what the user is asking, suggested by the survey.

    Agent-authored, so it is not HITL: it claims no authority and is offered
    none. ``moved_by`` puts admissibility in the schema — *"we want assumptions
    to be avenues available for information to stick. There is no point in
    assuming something unprovable."*

    The id and the cycle are the graph's, never the model's.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    cycle: int = 0
    claim: str = Field(min_length=1, description="One checkable proposition.")
    grounded_in: str = Field(default="", description="Explicit id this hangs off, if any.")
    inferred_because: str = Field(min_length=1, description="Why the agent assumed it.")
    moved_by: str = Field(min_length=1, description="The call whose result would change belief.")
    #: Ids of the survey's findings this rests on. The findings hang off the
    #: question; this is the assumption citing them.
    evidence: tuple[str, ...] = ()
    #: The overview this was formed against.
    formed_against: str = ""


class Antithesis(BaseModel):
    """The rival of **one** assumption.

    One per assumption, authored in a single pass across all of them — *"a single
    pass that looks at the antithesis of all assumptions looked at in the
    previous"*. Admissible on the same terms as any assumption, and *"there is
    nothing to attack" is not a permitted output*.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    cycle: int = 0
    claim: str = Field(min_length=1, description="The rival claim.")
    inferred_because: str = Field(min_length=1)
    moved_by: str = Field(min_length=1)
    #: The assumption it contends with.
    target: str


class Finding(BaseModel):
    """Sourced material. It is not a fact, and it never becomes one here.

    An excerpt appearing in no recorded tool result is rejected — which is what
    stops the agent being its own witness. One channel for the case's findings
    and the rivals', distinguished by ``node_id``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    #: The node this serves: the cycle's question in orientate (stamped by the
    #: graph), a rival named by position in antithesis, a node id in synthesis.
    node_id: str
    cycle: int = 0
    locator: str = Field(min_length=1, description="e.g. 'src/app.py:42'.")
    excerpt: str = Field(min_length=1, description="Verbatim, checked against tool results.")
    tool_call_id: str = ""
    price: int = Field(ge=0, description="What the call that produced this cost.")


class Reasoning(BaseModel):
    """What a frame made of what it found. Recorded, never re-rendered."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stage: Stage
    cycle: int = 0
    about: str = ""
    text: str = Field(min_length=1)


class SpendEntry(BaseModel):
    """One priced call, recorded at the moment it was authorised.

    A list rather than a counter: a counter can be overwritten by a node
    returning a smaller number, a list cannot. Remaining budget is derived.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pool: str
    call: str = Field(description="Price class: read | survey | webfetch | graph_write")
    tool: str = Field(default="", description="The tool that was called.")
    price: int = Field(ge=0)
    stage: Stage
    tool_call_id: str = ""


# ---------------------------------------------------------------------------
# Records — the graph's operations (each a line in the log, never an edit)
# ---------------------------------------------------------------------------


class NodeAdded(BaseModel):
    """A provisional node the model added: an entity or a claim. Ungated
    growth — it claims nothing until the user reconciles it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    cycle: int = 0
    kind: str = Field(description="entity | claim")
    role: str = Field(default="", description="An entity's type or a claim's role.")
    text: str = Field(min_length=1)
    why: str = ""
    #: For a counter: the claim it contends with.
    about: str = ""


class EdgeAdded(BaseModel):
    """A relational edge, approved by the user at the call."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    cycle: int = 0
    src: str
    kind: str
    dst: str
    why: str = ""


class RelationKind(BaseModel):
    """A relation added to this project's vocabulary, by approval."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    cycle: int = 0
    because: str = ""


class NodeUpdated(BaseModel):
    """Rename, reword or reclassify. The old text stays in the log."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target: str
    cycle: int = 0
    text: str = ""
    kind: str = ""
    role: str = ""
    because: str = ""


class EdgeUpdated(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target: str = Field(description="The edge id.")
    cycle: int = 0
    kind: str = ""
    why: str = ""
    because: str = ""


class Tombstone(BaseModel):
    """A node or edge discarded. A node is only ever tombstoned bare."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target: str
    cycle: int = 0
    because: str = ""
    merged_into: str = ""


class Merge(BaseModel):
    """Every edge and every piece of evidence of ``source`` re-pointed to
    ``target``; ``source`` tombstoned with ``merged_into``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: str
    target: str
    cycle: int = 0
    because: str = ""


class EvidenceMoved(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    finding: str
    to: str
    cycle: int = 0
    because: str = ""


class Closure(BaseModel):
    """The user's verdict on a node: confirmed or refuted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target: str
    verdict: str
    cycle: int = 0
    because: str = ""


class Supersession(BaseModel):
    """``new`` replaces ``old``: old is superseded, new takes the assumption role."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    old: str
    new: str
    cycle: int = 0
    because: str = ""


class Compression(BaseModel):
    """A summary node standing in for a set. The members keep everything;
    the package renders the summary instead."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    members: tuple[str, ...] = Field(min_length=1)
    summary: str = Field(min_length=1)
    cycle: int = 0


#: The records that change the graph, applied in log order after the base.
OPERATIONS: tuple[type[BaseModel], ...] = (
    NodeAdded,
    EdgeAdded,
    RelationKind,
    NodeUpdated,
    EdgeUpdated,
    Tombstone,
    Merge,
    EvidenceMoved,
    Closure,
    Supersession,
    Compression,
)


# ---------------------------------------------------------------------------
# Records — the approval record
# ---------------------------------------------------------------------------


class ProposedWrite(BaseModel):
    """An alteration the agent asked for, surfaced as a call.

    A record, not a queue: the call was put to the user at the moment it was
    made and answered there. Kept because what the agent wanted to do is worth
    having even when the answer was no.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    cycle: int = 0
    write: str = Field(description="The tool name.")
    stage: Stage = "synthesis"
    target_id: str = ""
    argument: str = Field(default="", description="What the call would record.")
    because: str = Field(default="", description="What the agent read this from.")


class Decision(BaseModel):
    """The user's answer to one call, kept whichever way it went.

    A refusal is a record, not an absence — it is what stops the next cycle
    re-proposing closed ground. ``answered_by`` is not decoration: anything not
    ``human`` is meant to be visible.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    write_id: str
    approved: bool
    answered_by: Literal["human", "scripted", "auto"] = "human"
    cycle: int = 0
    #: The user's own words, verbatim.
    words: str = ""
    #: Whether the approved call's handler recorded its effect. False when the
    #: user said yes but the handler still refused (a stale id, for instance).
    applied: bool = False


# ---------------------------------------------------------------------------
# The state
# ---------------------------------------------------------------------------


class GraphState(BaseModel):
    """One session's working set: where its cycle stands, and what was said.

    Nothing here is a graph record. Every record a frame authors goes to the
    project's operation log the moment the frame commits; the fields below are
    the only things a thread carries, checkpoints and forks.
    """

    model_config = ConfigDict(extra="forbid")

    # --- position ---------------------------------------------------------
    #: The graph cycle this thread is working on, allocated by the log when the
    #: first frame opens it. 0 before any cycle.
    cycle: int = 0
    #: Which frame last ran — the cycle pointer. While it reads ``synthesis``
    #: every message re-enters the conversation.
    stage: Stage = "orientate"
    #: The user's command to go round again. Set by the driver, cleared by the
    #: frame that starts the cycle. The exit from synthesis is the user's only.
    advance: bool = False

    # --- the conversation this cycle runs in ---------------------------------
    #: The SDK session id every frame of this cycle continues. Recorded by the
    #: first frame; a thread resumed from disk re-opens the same conversation.
    conversation: str = ""
    #: Set by ``/fork``: the next frame must fork the SDK conversation rather
    #: than append to one another branch also continues. Cleared once done.
    fork_conversation: bool = False

    # --- the request ------------------------------------------------------
    #: What the user just sent, on this run. Overwrites.
    prompt: str = ""
    #: The question this cycle is working on, fixed by the frame that opened it.
    question: str = ""
    #: Every message the user sent this cycle, in order: the question, then
    #: each synthesis reply. What a proposed fact must be a verbatim span of.
    said: Annotated[list[str], operator.add] = Field(default_factory=list)

    # --- what the frames left in the working set ------------------------------
    #: The survey's overview, this cycle.
    orientation: str = ""
    synthesis_turns: int = 0
    #: The agent's last reply in the conversation.
    disposition: str = ""


@dataclass(frozen=True, slots=True)
class Counts:
    """How many of each record a cycle already holds, so the ids a turn
    assigns continue the sequence rather than restart it."""

    findings: int = 0
    proposals: int = 0
    explicits: int = 0
    entities: int = 0
    claims: int = 0
    edges: int = 0
    summaries: int = 0


#: Every record type that may appear in a checkpoint. LangGraph serialises
#: with ormsgpack and refuses unregistered types under strict mode; listed
#: explicitly because adding a type to the checkpoint is a decision.
RECORD_TYPES: tuple[type[BaseModel], ...] = (
    Cycle,
    Explicit,
    Candidate,
    Parked,
    Assumption,
    Antithesis,
    Finding,
    Reasoning,
    SpendEntry,
    ProposedWrite,
    Decision,
    *OPERATIONS,
    GraphState,
)


def unlisted_record_types() -> tuple[str, ...]:
    """Models defined here that :data:`RECORD_TYPES` does not name."""
    listed = {t.__name__ for t in RECORD_TYPES}
    here = {
        name
        for name, obj in globals().items()
        if isinstance(obj, type)
        and issubclass(obj, BaseModel)
        and obj is not BaseModel
        and obj.__module__ == __name__
    }
    return tuple(sorted(here - listed))
