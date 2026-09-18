"""The cycle's state — the semantic context we own.

Two things differ from `session/state.py`, and both are deliberate.

**The store is pydantic records, not a networkx graph.** `ledger/models.py` says
*"The graph itself is the store"*, and here it cannot be: this state is
checkpointed by LangGraph and forked at a chosen checkpoint, and a live
``DiGraph`` is neither serialisable through that path nor meaningful to fork.
So the records are the store and the graph becomes a *derived view*, built on
demand by whatever needs to traverse. The checkpoint history is then the audit
trail, and there is no second copy to drift.

**A channel either accumulates or overwrites, and which one is a design
statement.** A node cannot retract what it wrote to an accumulating channel by
returning something smaller, so everything the ledger must never lose lives on
one: findings, spend, parked candidates, the affirming transcript. Fields that
hold a *current reading* rather than a record — the orientation, the stage — 
overwrite, because a stale reading is worse than no reading.

Nothing here holds a cap. Caps are context — see `context.py`.
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Closed enums
# ---------------------------------------------------------------------------

#: The five design stages. Tool availability keys off this and nothing else
#: (tool availability is gated by stage); see `surface.py`.
Stage = Literal["extract", "orient", "assume", "antithesis", "present"]

#: Why a candidate fact was not promoted. Both are parked, and both park **with
#: their reason** — `ledger/models.py:32` already carries the semantics
#: (*"asked, no answer — never self-resolves"*). If the reason does not survive
#: compaction the next cycle re-extracts and pays again, which is the first
#: purpose of pricing violated by the mechanism meant to serve it.
ParkReason = Literal["denied", "unanswered"]


# ---------------------------------------------------------------------------
# Records — turn 1
# ---------------------------------------------------------------------------


class Explicit(BaseModel):
    """The user's own words, approved. The only authority in the state.

    Frozen because an explicit that can be edited after approval is not an
    explicit — the user approved a specific string.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    quote: str = Field(min_length=1, description="Verbatim span of the user's message.")
    start: int = Field(ge=0)
    cycle: int


class Candidate(BaseModel):
    """An extraction-pass output. Carries no authority until approved.

    Selection, boundary-drawing and paraphrase are all inference, so this is an
    agent artefact no matter how literal the span looks.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    quote: str = Field(min_length=1)
    start: int = Field(ge=0)


class Parked(BaseModel):
    """A candidate that did not become explicit, and why."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate: Candidate
    reason: ParkReason
    note: str = ""
    cycle: int


class Assumption(BaseModel):
    """One of several interpretations of what the user is asking.

    Agent-authored, so it is **not** HITL: it claims no authority and is offered
    none. ``moved_by`` puts admissibility in the schema: an assumption must name
    the call whose result would change the agent's belief about it, or it is not
    somewhere information can land and must not exist at all — *"we want
    assumptions to be avenues available for information to stick. There is no
    point in assuming something unprovable."*
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    claim: str = Field(min_length=1, description="One checkable proposition.")
    grounded_in: str = Field(description="Node id of the explicit this hangs off.")
    inferred_because: str = Field(
        min_length=1,
        description="Why the agent read it this way — the edge's formation text.",
    )
    moved_by: str = Field(
        min_length=1,
        description="The call whose result would change belief about this claim.",
    )
    #: The orientation this was formed against. An assumption outliving its
    #: orientation is stale, and a later orientation contradicting this stamp is a
    #: structural signal rather than a judgement.
    formed_against: str = ""


class Finding(BaseModel):
    """Sourced material. It is not a fact, and it never becomes one here.

    Mirrors the built `Source` (`ledger/models.py:100-131`) including the
    constraint that an excerpt appearing in no recorded tool result is rejected.
    ``answers`` is the field that must not cross the turn boundary — see
    :class:`NeutralFinding`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    assumption_id: str
    locator: str = Field(min_length=1, description="e.g. 'session/runner.py:42'.")
    excerpt: str = Field(min_length=1, description="Verbatim, checked against tool results.")
    answers: str = Field(
        min_length=1,
        description="Verbatim words from the EXPLICIT this speaks to. AFFIRMING-FRAME.",
    )
    tool_call_id: str
    price: int = Field(ge=0, description="What the call that produced this cost.")

    def neutralise(self) -> NeutralFinding:
        """Drop the affirming frame, keep what is re-checkable."""
        return NeutralFinding(
            id=self.id,
            assumption_id=self.assumption_id,
            locator=self.locator,
            excerpt=self.excerpt,
        )


class NeutralFinding(BaseModel):
    """A finding with the thesis' framing removed — a *different type*, on purpose.

    ``answers`` holds the thesis explaining why the evidence mattered, which is
    the affirming frame in a single field. Enforcing its absence by projection
    rather than by convention means it is the type system that refuses, not the
    author remembering.

    What survives is what is re-checkable by anyone in any frame: where it is
    and what it literally says.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    assumption_id: str
    locator: str
    excerpt: str


class SpendEntry(BaseModel):
    """One priced call, recorded after the fact.

    An accumulating list rather than a counter, because a counter can be
    overwritten by a node returning a smaller number and a list cannot. The
    remaining budget is always derived (see `budget.py`), never stored.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pool: str = Field(description="Which pool it came out of: 'orientation', 'a3', 'antithesis'.")
    call: str = Field(description="The call's price class: survey | read | webfetch | ...")
    price: int = Field(ge=0)
    turn: int
    stage: Stage
    tool_call_id: str = ""


# ---------------------------------------------------------------------------
# Records — the turn boundary
# ---------------------------------------------------------------------------


class Crossing(BaseModel):
    """What turn 1 hands turn 2. Built by a node, so it is checkpointed evidence.

    The boundary is that context edit made into an object. Everything in
    here is in the "crosses" column of the diagram in budgeted-flow §3.4;
    everything held back is absent by construction rather than by filtering,
    because this object is *assembled* from the parts that may cross rather than
    copied from state and stripped.

    The residual leak the design names is real and is not closed by this type:
    the excerpts are re-checkable, but *which* excerpts were selected was an
    affirming-frame decision. That is what the ``N`` term in ``base + N`` is for.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    prompt: str
    explicits: tuple[Explicit, ...] = ()
    assumptions: tuple[Assumption, ...] = ()
    findings: tuple[NeutralFinding, ...] = ()
    #: "assumption 2 used 5 of 5". Spend crosses; it is a fact
    #: about the agent's own behaviour, not about the world.
    spend: tuple[SpendEntry, ...] = ()
    #: Parked candidates and their reasons cross, or the next cycle pays for
    #: dead ground again (what survives compaction is unresolved).
    parked: tuple[Parked, ...] = ()


# ---------------------------------------------------------------------------
# Records — turn 2 and turn 3
# ---------------------------------------------------------------------------


class Antithesis(BaseModel):
    """The rival reading of the *set* of assumptions (the antithesis is a node).

    One node aimed at all N, not one per assumption: only that form can catch a
    misreading the whole set shares, because a per-assumption rival is authored
    inside the frame it was meant to question.

    Admissible on the same terms as any assumption, and *"there is nothing to
    attack" is not a permitted output* — hence ``moved_by`` being required here
    too.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    claim: str = Field(min_length=1, description="The reading all N assumptions miss.")
    #: The parent edge has no obvious source: the built ledger requires an
    #: assumption's parent be an explicit, which leaves "these N readings all
    #: miss X" with nowhere to live but the edge's formation text. Held open.
    grounded_in: str
    inferred_because: str = Field(min_length=1)
    moved_by: str = Field(min_length=1)
    targets: tuple[str, ...] = Field(default=(), description="Assumption ids it contends with.")


class ProposedWrite(BaseModel):
    """A graph-write the agent wants to make, surfaced *as a call*.

    This is the type that resolves the binding problem. The agent's reading of a
    free-prose reply only takes effect as one of these, and the user approves
    the call — so approving it confirms the *binding*, not the claim. No silent
    reinterpretation is reachable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    write: str = Field(description="A member of surface.GraphWrite.")
    target_id: str = ""
    argument: str = Field(default="", description="What the call would record.")
    because: str = Field(default="", description="What in the reply the agent read this from.")


# ---------------------------------------------------------------------------
# The state
# ---------------------------------------------------------------------------


class Cycle(BaseModel):
    """One cycle: three turns, five stages, one ledger.

    Field order follows the cycle, so reading the class top to bottom is reading
    the flow. Every accumulating channel is annotated; everything else
    overwrites.
    """

    model_config = ConfigDict(extra="forbid")

    # --- position ---------------------------------------------------------
    cycle: int = 0
    turn: int = 1
    stage: Stage = "extract"

    # --- stage ① prompt + fact extraction ---------------------------------
    #: Registered verbatim. Overwrites: each cycle has exactly one prompt, and
    #: the previous one is preserved as its explicits, not as raw text.
    prompt: str = ""
    explicits: Annotated[list[Explicit], operator.add] = Field(default_factory=list)
    #: This cycle's extraction only. Overwrites — a candidate is transient; its
    #: outcome (explicit or parked) is what persists.
    candidates: list[Candidate] = Field(default_factory=list)
    parked: Annotated[list[Parked], operator.add] = Field(default_factory=list)

    # --- stage ② budget context pass --------------------------------------
    #: The current landscape reading. Overwrites, because an assumption
    #: carried across cycles hangs off a reading that no longer exists, and
    #: keeping both would hide that rather than surface it.
    orientation: str = ""
    orientation_turns: int = 0
    #: The agent's own answer to "can you now name the readings worth exploring?".
    #: Recorded rather than inferred, so the checkpoint history shows why the
    #: orientation loop exited — the agent being ready, or the pool running dry.
    orientation_ready: bool = False

    # --- stage ③ assumption pass ------------------------------------------
    assumptions: Annotated[list[Assumption], operator.add] = Field(default_factory=list)
    #: Graph-set, never agent-set (the agent never sets its own values). Assumption id -> points.
    allocations: dict[str, int] = Field(default_factory=dict)
    findings: Annotated[list[Finding], operator.add] = Field(default_factory=list)
    #: The affirming transcript. Accumulates so it is never lost, and is denied
    #: to turn 2 by projection rather than by deletion — see `views.py`.
    thesis_reasoning: Annotated[list[str], operator.add] = Field(default_factory=list)
    form_attempts: int = 0

    # --- the turn boundary ------------------------------------------------
    crossing: Crossing | None = None

    # --- stage ④ antithesis pass ------------------------------------------
    antithesis: Antithesis | None = None
    counter_findings: Annotated[list[Finding], operator.add] = Field(default_factory=list)
    antithesis_attempts: int = 0

    # --- stage ⑤ present + reconcile --------------------------------------
    #: The presented text. Not a graph object: options are never part of the
    #: graph and are not tool calls — they are prose at a stop point.
    disposition: str = ""
    #: The user's raw-text reply. Carries authority on arrival.
    reply: str = ""
    proposed: list[ProposedWrite] = Field(default_factory=list)
    approved_writes: Annotated[list[str], operator.add] = Field(default_factory=list)

    # --- spend ------------------------------------------------------------
    #: Every priced call in the cycle, in order. Remaining budget is derived
    #: from this against the context's caps, so there is no number an agent
    #: could return that would grant it more.
    spend: Annotated[list[SpendEntry], operator.add] = Field(default_factory=list)

    #: Set when a re-authoring loop runs out of attempts. Nothing in the design
    #: says what happens then, so it is recorded rather than handled.
    escalation: str = ""


# ---------------------------------------------------------------------------
# Persistence allowlist
# ---------------------------------------------------------------------------

#: Every record type that may appear in a checkpoint.
#:
#: LangGraph serialises state with ormsgpack and, by default, deserialises any
#: type it finds while logging a warning per type: *"Deserializing unregistered
#: type ... This will be blocked in a future version."* Under
#: ``LANGGRAPH_STRICT_MSGPACK=true`` it is blocked today. Measured, not read:
#: the warning fires for these models and a round-trip under strict mode
#: succeeds once they are allow-listed.
#:
#: Listed explicitly rather than gathered by reflection over this module. An
#: allowlist that admits whatever is nearby is not an allowlist, and the point
#: of the mechanism is that adding a type to the checkpoint is a decision — the
#: serialiser is a code-execution surface if anything can write to the store.
#: :func:`unlisted_record_types` keeps the explicit list honest.
RECORD_TYPES: tuple[type[BaseModel], ...] = (
    Explicit,
    Candidate,
    Parked,
    Assumption,
    Finding,
    NeutralFinding,
    SpendEntry,
    Crossing,
    Antithesis,
    ProposedWrite,
    Cycle,
)


def unlisted_record_types() -> tuple[str, ...]:
    """Models defined here that :data:`RECORD_TYPES` does not name.

    Empty is the only correct answer. A record reachable from :class:`Cycle` but
    missing from the allowlist checkpoints fine and fails to *load*, which is
    the worst possible time to find out.
    """
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
