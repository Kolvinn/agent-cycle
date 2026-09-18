"""The cycle's state — the semantic context we own.

Three things differ from `session/state.py`, and all three are deliberate.

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
one: findings, spend, parked candidates, the readings, the rivals, the
reasoning, the decisions. Fields that hold a *current position* rather than a
record — which reading is being funded, how many turns it has had — overwrite,
because a stale position is worse than none.

**One state, whole, for every node.** Nodes are ``node(state: Cycle)``. There is
no projection and no sub-view: a view naming a channel the state does not have
receives an empty default rather than failing, so the guarantee was weaker than
it looked. What a frame must not read is a rule in its body, stated where the
reading happens.

**The state outlives the cycle.** Answering a report starts a new run at the
first frame on the same thread, so every accumulating channel here holds every
cycle's records, not this one's. Anything that must be *this* cycle's is
selected, never assumed — see :meth:`Cycle.current_assumptions`. That is why the
authored records carry a cycle stamp and why pool names do too.

Nothing here holds a cap. Caps are context — see `context.py`.
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from .surface import Stage

# ---------------------------------------------------------------------------
# Closed enums
# ---------------------------------------------------------------------------

#: The stage label is :data:`surface.Stage`, imported rather than restated. It
#: used to be declared here as well, with five members from an older shape, so
#: a spend entry stamped by a node would have failed validation against the very
#: frame that wrote it. One definition, and it lives beside the tool table it
#: keys.

#: Why a candidate fact was not promoted. Both are parked, and both park **with
#: their reason** — the built ledger already carries the semantics (*"asked, no
#: answer — never self-resolves"*). If the reason does not survive compaction the
#: next cycle re-extracts and pays again, which is the first purpose of pricing
#: violated by the mechanism meant to serve it.
ParkReason = Literal["denied", "unanswered"]


# ---------------------------------------------------------------------------
# Records — the request, and what was extracted from it
# ---------------------------------------------------------------------------
#
# ⏸ Fact extraction is **parked, not cancelled**: *"I think we can put this to
# the side for now. The fact extraction has more nuance at the moment than i
# anticipated."* No frame currently produces an explicit or a candidate — the
# authority-bearing calls are commented out of the first frame's surface. These
# records stay because parked is not cancelled, and because the fields that
# point at an explicit are still in the schemas that will need them.


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


# ---------------------------------------------------------------------------
# Records — what the frames author
# ---------------------------------------------------------------------------


class Assumption(BaseModel):
    """One reading of what the user is asking.

    Agent-authored, so it is **not** HITL: it claims no authority and is offered
    none. ``moved_by`` puts admissibility in the schema: a reading must name the
    call whose result would change the agent's belief about it, or it is not
    somewhere information can land and must not exist at all — *"we want
    assumptions to be avenues available for information to stick. There is no
    point in assuming something unprovable."*

    **The id and the cycle are the graph's, never the model's.** The model
    authors the four fields below the stamp and is never told what any of them
    was called. An id the model invents is one more thing that can come back
    duplicated or drifted, and a finding stamped to the wrong reading is a
    mistake nothing downstream could detect.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    #: Which cycle authored it. Readings accumulate across cycles and the frames
    #: after orientation are funded per reading and at base-plus-count, so a
    #: frame that counted every reading ever written would fund itself out of a
    #: previous cycle's breadth. Selected explicitly rather than inferred from
    #: the id's shape.
    cycle: int = 0
    claim: str = Field(min_length=1, description="One checkable proposition.")
    grounded_in: str = Field(
        default="",
        description=(
            "Node id of the explicit this hangs off. Empty while fact extraction "
            "is parked — there are no explicits to hang off yet."
        ),
    )
    inferred_because: str = Field(
        min_length=1,
        description="Why the agent read it this way — the edge's formation text.",
    )
    moved_by: str = Field(
        min_length=1,
        description="The call whose result would change belief about this claim.",
    )
    #: The orientation this was formed against. A reading outliving its
    #: orientation is stale, and a later orientation contradicting this stamp is
    #: a structural signal rather than a judgement.
    formed_against: str = ""


class Antithesis(BaseModel):
    """The rival reading of the *set* of readings.

    One rival aimed at all N, not one per reading: only that form can catch a
    misreading the whole set shares, because a per-reading rival is authored
    inside the frame it was meant to question.

    Admissible on the same terms as any reading, and *"there is nothing to
    attack" is not a permitted output* — hence ``moved_by`` being required here
    too. Exactly one per cycle, which is a *count*, so it comes back on the
    frame's answer rather than as a call: nothing a per-call refusal does could
    produce a rival that was not offered.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    cycle: int = 0
    claim: str = Field(min_length=1, description="The reading all N readings miss.")
    #: ⚠️ **Open.** The built ledger requires a claim's parent be an explicit,
    #: which leaves "these N readings all miss X" with nowhere to live but the
    #: edge's formation text. Empty while extraction is parked, as above.
    grounded_in: str = ""
    inferred_because: str = Field(min_length=1)
    moved_by: str = Field(min_length=1)
    targets: tuple[str, ...] = Field(default=(), description="Reading ids it contends with.")


class Finding(BaseModel):
    """Sourced material. It is not a fact, and it never becomes one here.

    Mirrors the built ``Source``, including the constraint that an excerpt
    appearing in no recorded tool result is rejected — which is what stops the
    agent being its own witness.

    **One channel for the case's findings and the rival's**, distinguished by
    ``assumption_id``: a reading's id for the case, the rival's id for the
    rival. A second channel would have to be kept in step with this one by
    convention, and nothing would notice when it drifted.

    **Nothing strips this record any more.** It used to have a projected twin
    with the affirming frame removed, because the record crossed a turn boundary
    into a conversation that was not allowed to see it. Every frame now
    continues the same conversation, so there is no boundary to project across
    and no second type to keep in step.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    #: The reading this serves, stamped by the graph. The model is not asked
    #: which reading its call was for — the frame funds one reading per turn, so
    #: the graph already knows.
    assumption_id: str
    locator: str = Field(min_length=1, description="e.g. 'session/runner.py:42'.")
    excerpt: str = Field(min_length=1, description="Verbatim, checked against tool results.")
    answers: str = Field(
        default="",
        description=(
            "Verbatim words from the EXPLICIT this speaks to, checked as a "
            "substring of it. What keeps a finding relevant to what was asked "
            "rather than merely relevant to the claim. Optional only because "
            "extraction is parked and there are no explicits to quote — when it "
            "is unparked this is required again, and the substring check with it."
        ),
    )
    tool_call_id: str
    price: int = Field(ge=0, description="What the call that produced this cost.")


class Reasoning(BaseModel):
    """What a frame made of what it found. Recorded, never re-rendered.

    One channel for every frame's reasoning, stamped with which frame wrote it
    and what it was about — the same decision as the findings, for the same
    reason. It used to be named for the thesis alone and existed to be
    *withheld* from the frame that followed; there is nothing to withhold now
    that every frame continues the same conversation, so what is left is the
    record.

    Nothing reads this back into a prompt. It is here because it is the
    reasoning that produced the case, and a case whose reasoning is not in the
    checkpoint cannot be argued with later.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    stage: Stage
    cycle: int = 0
    #: The reading or rival it concerns. Empty for a frame that is not about one.
    about: str = ""
    text: str = Field(min_length=1)


class SpendEntry(BaseModel):
    """One priced call, recorded at the moment it was authorised.

    An accumulating list rather than a counter, because a counter can be
    overwritten by a node returning a smaller number and a list cannot. The
    remaining budget is always derived (see `budget.py`), never stored.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    pool: str = Field(
        description=(
            "Which pool it came out of. Cycle-scoped: 'orientation:1', "
            "'assume:a1.2', 'antithesis:1'. See budget.py."
        )
    )
    call: str = Field(description="The call's price class: read | survey | webfetch | ...")
    price: int = Field(ge=0)
    turn: int
    stage: Stage
    tool_call_id: str = ""


# ---------------------------------------------------------------------------
# Records — the approval queue
# ---------------------------------------------------------------------------


class ProposedWrite(BaseModel):
    """An alteration the agent wants to make, surfaced *as a call*.

    This is the type that resolves the binding problem. The agent's reading of
    what you said only takes effect as one of these, and you answer the call — so
    answering it confirms the *binding*, not the claim. No silent
    reinterpretation is reachable.

    **A record, not a queue.** Nothing waits here. The call was put to you at the
    moment it was made and answered there; this is what was asked for, kept
    because what the agent wanted to do is worth having even when the answer was
    no. Its answer is the :class:`Decision` beside it.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str
    cycle: int = 0
    write: str = Field(description="A member of surface.Alteration.")
    stage: Stage = "synthesis"
    target_id: str = ""
    argument: str = Field(default="", description="What the call would record.")
    because: str = Field(default="", description="What in the reply the agent read this from.")


class Decision(BaseModel):
    """Your answer to one queued call, kept whichever way it went.

    **A refusal is a record, not an absence.** Keeping only the approvals would
    mean a refused call is indistinguishable from one never asked about, so the
    next cycle would ask again and there would be nothing to say you had already
    said no. The parked candidates already work this way — they park *with their
    reason* — and this is the same rule applied to the queue.

    ``answered_by`` is not decoration. An earlier attempt in this repository
    shipped a human-in-the-loop stub that returned "Approved, execute operation."
    with no human present, and nothing in the log said so. Anything that is not
    ``human`` is meant to be visible, and it matters more here than it did
    there: this answer is given in the middle of a live turn, on a surface where
    the agent may propose anything.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    write_id: str
    approved: bool
    answered_by: Literal["human", "scripted", "auto"] = "human"
    cycle: int = 0
    #: Your own words. Authority, not the agent's reading of them — they go back
    #: to the model as the call's result and they stay here as what you said.
    words: str = ""


# ---------------------------------------------------------------------------
# The state
# ---------------------------------------------------------------------------


class Cycle(BaseModel):
    """One cycle: four frames, one ledger, and everything the ones before left.

    Field order follows the flow, so reading the class top to bottom is reading
    the graph. Every accumulating channel is annotated; everything else
    overwrites.
    """

    model_config = ConfigDict(extra="forbid")

    # --- position ---------------------------------------------------------
    #: Incremented by the first frame, so cycle 1 is the first real one. Every
    #: authored record is stamped with it.
    cycle: int = 0
    #: Which frame last ran — and, because the graph is entered conditionally,
    #: **the cycle pointer**. While it reads ``synthesis`` every message you send
    #: re-enters the conversation rather than starting a new cycle. Every frame
    #: sets it; a pointer only some frames maintained would be worse than none.
    stage: Stage = "orientate"

    #: Your command to go round again. Set by the driver on the message that
    #: should start a new cycle, and cleared by the frame that starts it.
    #:
    #: **The exit from the synthesis conversation is yours, and it is only
    #: yours.** Not the model deciding it is finished, not a budget running out,
    #: not a count of approvals. The graph does not advance until you say so.
    advance: bool = False

    # --- the request ------------------------------------------------------
    #: **What you just sent**, on this run. Overwrites, because it is an input
    #: rather than a record: the driver sets it on every invocation, and which
    #: frame reads it is decided by the pointer. A new cycle reads it as the
    #: question; an exchange of the synthesis conversation reads it as your
    #: reply. That is what makes a follow-up and a first message the same thing.
    prompt: str = ""
    #: The question **this cycle** is working on, taken from your message by the
    #: frame that opened the cycle. Kept apart from ``prompt`` so that replying
    #: to the conversation does not quietly rewrite what the cycle was about.
    question: str = ""
    explicits: Annotated[list[Explicit], operator.add] = Field(default_factory=list)
    #: This cycle's extraction only. Overwrites — a candidate is transient; its
    #: outcome (explicit or parked) is what persists.
    candidates: list[Candidate] = Field(default_factory=list)
    parked: Annotated[list[Parked], operator.add] = Field(default_factory=list)

    # --- ① orientate ------------------------------------------------------
    #: The current landscape reading. Overwrites, because a reading carried
    #: across cycles hangs off a landscape that no longer exists — and each
    #: reading keeps its own stamp of the one it was formed against, so the old
    #: text is not lost where it matters.
    orientation: str = ""
    assumptions: Annotated[list[Assumption], operator.add] = Field(default_factory=list)
    #: Reading id -> points. Graph-set, never agent-set. Overwrites, and is
    #: rewritten each cycle for that cycle's readings, so a previous cycle's
    #: reading has no allocation and can buy nothing.
    allocations: dict[str, int] = Field(default_factory=dict)

    # --- ② assume (the subgraph's two loop variables, and what it gathers) --
    #: Which reading is being funded. The outer loop sets it; overwrites.
    current_reading: str = ""
    #: Turns spent on the current reading. Zero means the turn is *arriving* at
    #: a reading rather than staying on one, which is the whole difference
    #: between the two messages the frame sends.
    reading_turns: int = 0
    #: Turns the frame has taken in total. Zero means the instructions have not
    #: been sent yet; they go once, and every later turn continues the same
    #: conversation where they are still in front of the model.
    assume_turns: int = 0
    #: Readings that said they had nothing further worth buying. **Not derivable
    #: from the spend** — a reading that stops early still has points in its
    #: pool — and it is the one kind of closing the agent may do: it may close a
    #: reading's *budget*, never its truth.
    budget_closed: Annotated[list[str], operator.add] = Field(default_factory=list)
    #: Every finding, the case's and the rival's, stamped with which it serves.
    findings: Annotated[list[Finding], operator.add] = Field(default_factory=list)

    # --- ③ antithesis -----------------------------------------------------
    #: One per cycle, accumulating rather than overwriting: the rival's findings
    #: are stamped with its id and live forever on the channel above, so an
    #: overwritten rival would leave them pointing at nothing.
    antitheses: Annotated[list[Antithesis], operator.add] = Field(default_factory=list)

    # --- ④ synthesis ------------------------------------------------------
    #: Exchanges the conversation has had this cycle. Zero means the brief has
    #: not been sent, and it is sent once — every later message continues the
    #: same conversation, where it is still in front of the model.
    synthesis_turns: int = 0
    #: Every authority-bearing call the agent made, answered or refused.
    proposed: Annotated[list[ProposedWrite], operator.add] = Field(default_factory=list)
    #: Your answers to them, one per proposal.
    decisions: Annotated[list[Decision], operator.add] = Field(default_factory=list)
    #: The agent's last reply in the conversation. Overwrites — the exchange
    #: before it is in the reasoning channel and in the conversation itself, and
    #: what carries to the next cycle is the graph, not this text.
    disposition: str = ""

    # --- across every frame ------------------------------------------------
    #: What each frame made of what it found, stamped with which frame.
    reasoning: Annotated[list[Reasoning], operator.add] = Field(default_factory=list)
    #: Every priced call in every cycle, in order. Remaining budget is derived
    #: from this against the context's caps, so there is no number an agent
    #: could return that would grant it more.
    spend: Annotated[list[SpendEntry], operator.add] = Field(default_factory=list)

    # --- selection over the accumulated record ------------------------------

    def current_assumptions(self) -> list[Assumption]:
        """This cycle's readings, in the order they were named.

        Every frame after the first must use this rather than the whole channel.
        The assume subgraph loops until no reading can still buy, the rival is
        funded at base plus the *count*, and the report's disclosure is computed
        from the same count — so a frame reading every reading ever authored
        would loop over settled ground and fund itself out of a previous cycle's
        breadth.
        """
        return [a for a in self.assumptions if a.cycle == self.cycle]

    def current_antithesis(self) -> Antithesis | None:
        """This cycle's rival, if it has been authored yet."""
        for rival in reversed(self.antitheses):
            if rival.cycle == self.cycle:
                return rival
        return None

    def refused(self) -> list[ProposedWrite]:
        """Alterations you said no to, across every cycle.

        What the next cycle should not be re-proposing. The reason you gave is
        on the :class:`Decision`, and the parked record carries it too.
        """
        no = {d.write_id for d in self.decisions if not d.approved}
        return [w for w in self.proposed if w.id in no]


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
    Antithesis,
    Finding,
    Reasoning,
    SpendEntry,
    ProposedWrite,
    Decision,
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
