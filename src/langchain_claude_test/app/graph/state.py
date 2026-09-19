"""The cycle's state — the semantic context we own.

**The store is pydantic records, not a live graph.** This state is checkpointed
and forked, and a live ``DiGraph`` is neither serialisable through that path
nor meaningful to fork. The records are the store; the thought graph is a view
built on demand (``thought.py``).

**A channel either accumulates or overwrites, and which one is a design
statement.** A node cannot retract what it wrote to an accumulating channel, so
everything the ledger must never lose lives on one. Fields that hold a current
position overwrite, because a stale position is worse than none.

**The state outlives the cycle.** Every accumulating channel holds every
cycle's records. Anything that must be *this* cycle's is selected, never
assumed — the authored records carry a cycle stamp for that reason.

Nothing here holds a cap. Caps are context — see ``context.py``.
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .surface import Stage

ParkReason = Literal["denied", "unanswered"]


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
    """One reading of what the user is asking.

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
    inferred_because: str = Field(min_length=1, description="Why the agent read it this way.")
    moved_by: str = Field(min_length=1, description="The call whose result would change belief.")
    #: The orientation this was formed against.
    formed_against: str = ""


class Antithesis(BaseModel):
    """The rival reading of **one** assumption.

    One per reading, authored in a single pass across all of them — *"a single
    pass that looks at the antithesis of all assumptions looked at in the
    previous"*. Admissible on the same terms as any reading, and *"there is
    nothing to attack" is not a permitted output*.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    cycle: int = 0
    claim: str = Field(min_length=1, description="The rival reading.")
    inferred_because: str = Field(min_length=1)
    moved_by: str = Field(min_length=1)
    #: The reading it contends with.
    target: str


class Finding(BaseModel):
    """Sourced material. It is not a fact, and it never becomes one here.

    An excerpt appearing in no recorded tool result is rejected — which is what
    stops the agent being its own witness. One channel for the case's findings
    and the rivals', distinguished by ``node_id``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    #: The reading or rival this serves. Stamped by the graph where it knows
    #: (one reading per assume turn); resolved from the model's ``target``
    #: where it cannot (the antithesis and synthesis frames).
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
    #: Whether the approved call's effect has been applied to the store.
    #: False while the alteration semantics are under review.
    applied: bool = False


# ---------------------------------------------------------------------------
# The state
# ---------------------------------------------------------------------------


class GraphState(BaseModel):
    """One cycle: four frames, one ledger, and everything the ones before left.

    Field order follows the flow. Every accumulating channel is annotated;
    everything else overwrites.
    """

    model_config = ConfigDict(extra="forbid")

    # --- position ---------------------------------------------------------
    #: Incremented by the first frame, so cycle 1 is the first real one.
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
    explicits: Annotated[list[Explicit], operator.add] = Field(default_factory=list)
    parked: Annotated[list[Parked], operator.add] = Field(default_factory=list)

    # --- ① orientate ------------------------------------------------------
    orientation: str = ""
    assumptions: Annotated[list[Assumption], operator.add] = Field(default_factory=list)
    #: Reading id -> points. Graph-set, rewritten each cycle.
    allocations: dict[str, int] = Field(default_factory=dict)

    # --- ② assume ---------------------------------------------------------
    current_reading: str = ""
    reading_turns: int = 0
    assume_turns: int = 0
    #: Readings that said they had nothing further worth buying.
    budget_closed: Annotated[list[str], operator.add] = Field(default_factory=list)
    findings: Annotated[list[Finding], operator.add] = Field(default_factory=list)

    # --- ③ antithesis -----------------------------------------------------
    antitheses: Annotated[list[Antithesis], operator.add] = Field(default_factory=list)

    # --- ④ synthesis ------------------------------------------------------
    synthesis_turns: int = 0
    proposed: Annotated[list[ProposedWrite], operator.add] = Field(default_factory=list)
    decisions: Annotated[list[Decision], operator.add] = Field(default_factory=list)
    #: The agent's last reply in the conversation.
    disposition: str = ""

    # --- across every frame ------------------------------------------------
    reasoning: Annotated[list[Reasoning], operator.add] = Field(default_factory=list)
    spend: Annotated[list[SpendEntry], operator.add] = Field(default_factory=list)

    # --- selection over the accumulated record ------------------------------

    def current_assumptions(self) -> list[Assumption]:
        """This cycle's readings, in the order they were named."""
        return [a for a in self.assumptions if a.cycle == self.cycle]

    def current_antitheses(self) -> list[Antithesis]:
        """This cycle's rivals, in reading order."""
        return [x for x in self.antitheses if x.cycle == self.cycle]

    def refused(self) -> list[ProposedWrite]:
        """Alterations the user said no to, across every cycle."""
        no = {d.write_id for d in self.decisions if not d.approved}
        return [w for w in self.proposed if w.id in no]

    def approved(self) -> list[ProposedWrite]:
        yes = {d.write_id for d in self.decisions if d.approved}
        return [w for w in self.proposed if w.id in yes]

    def node_ids(self) -> set[str]:
        """Every id a finding or an alteration may point at."""
        return (
            {e.id for e in self.explicits}
            | {a.id for a in self.assumptions}
            | {x.id for x in self.antitheses}
        )


#: Every record type that may appear in a checkpoint. LangGraph serialises
#: with ormsgpack and refuses unregistered types under strict mode; listed
#: explicitly because adding a type to the checkpoint is a decision.
RECORD_TYPES: tuple[type[BaseModel], ...] = (
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
