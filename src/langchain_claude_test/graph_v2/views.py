"""Projections — what each node is *allowed to see*.

This is the file the framework choice was made for. A LangGraph node declared
with ``input_schema=SomeView`` receives an instance of that view, not the state:
a field the view does not name is not an attribute of the object the node
body holds. So "turn 2 must not inherit the affirming transcript" stops being an
instruction in a prompt and becomes a fact about a type — no node body can reach
it, and no prompt built inside that node can contain it.

Measured in `scripts/spikes/spike_06_control_graph.py`:

    the antithesis node received fields ['assumptions', 'spent']
    while the full state still carries thesis_reasoning=[...]

**The one rule that makes views checkable:** every field on a view must be a
field on :class:`~.state.Cycle`, spelled identically. LangGraph fills a view
from the state's channels by name, so a view field with no matching channel is a
bug that shows up at run time. :func:`fields_not_in_cycle` exists so that is a
test rather than a surprise.

**What a view does not do:** it does not stop a node *writing* to a channel it
cannot see. The returned delta is validated against the full state, not against
the view. Denial is on the read side only, which is the side that matters here —
the concern is contamination, not vandalism.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .state import (
    Antithesis,
    Assumption,
    Candidate,
    Crossing,
    Explicit,
    Finding,
    ProposedWrite,
    SpendEntry,
)


class _View(BaseModel):
    """Common config. Frozen: a node must not mutate what it was handed."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class PromptView(_View):
    """Stage ① registration. The prompt, and nothing that could colour it."""

    prompt: str = ""
    cycle: int = 0


class ExtractView(_View):
    """Stage ①'s extraction pass.

    Carries prior explicits, not prior assumptions. Where reconciling a new
    message against the existing graph belongs is undecided, and folding it in
    here is a candidate answer rather than a settled one. Prior assumptions are
    withheld so extraction cannot be anchored by the last cycle's readings while
    that stays open — widening this view is the change that would settle it.
    """

    prompt: str = ""
    explicits: list[Explicit] = Field(default_factory=list)
    cycle: int = 0


class ApprovalView(_View):
    """The stage ① HITL surface.

    Deliberately blind to spend and budget. The user is approving whether a span
    is their own words; what it would cost to act on is a different
    question and must not be in the frame when they answer this one.
    """

    prompt: str = ""
    candidates: list[Candidate] = Field(default_factory=list)
    cycle: int = 0


class OrientView(_View):
    """Stage ② — the landscape against the prompt.

    No assumptions field, because there are none yet, and no findings field,
    because this stage *forms no claim* (orientation forms no claim) and carries no graph-write
    tools at all. The stage is where going wide before deep is realised
    (go wide before going deep), and that comes from the stage boundary rather than from prices:
    per-assumption budget does not exist until assumptions do.
    """

    prompt: str = ""
    explicits: list[Explicit] = Field(default_factory=list)
    orientation: str = ""
    orientation_turns: int = 0
    spend: list[SpendEntry] = Field(default_factory=list)
    turn: int = 1


class FormView(_View):
    """Stage ③ authoring. Free — authoring a reading is not evidence gathering.

    Sees the orientation because that is what the readings are formed against
    formed against, and sees existing assumptions so a re-author can avoid repeating
    a rejected one. No findings: none exist before funding.
    """

    prompt: str = ""
    explicits: list[Explicit] = Field(default_factory=list)
    orientation: str = ""
    assumptions: list[Assumption] = Field(default_factory=list)
    form_attempts: int = 0
    cycle: int = 0


class InvestigateView(_View):
    """Stage ③ spend. One assumption's budget at a time (tool call restrictions per assumption).

    ``allocations`` is present and read-only — the node needs to know its cap to
    plan against it, and cannot change it, because a cap is context and this is
    a copy of the graph's decision (the agent never sets its own values).
    """

    prompt: str = ""
    explicits: list[Explicit] = Field(default_factory=list)
    orientation: str = ""
    assumptions: list[Assumption] = Field(default_factory=list)
    allocations: dict[str, int] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    spend: list[SpendEntry] = Field(default_factory=list)
    turn: int = 1


class AntithesisView(_View):
    """**The load-bearing projection.** Stage ④ sees the crossing and nothing else.

    Absent, and absent as a matter of type rather than of discipline:

    - ``thesis_reasoning`` — the affirming transcript. Nothing to be loyal to.
    - ``findings`` — the full records, which carry ``answers``. What is
      here instead is ``crossing.findings``, which are
      :class:`~.state.NeutralFinding` and have no such field.
    - ``explicits``/``prompt`` at top level — they arrive inside the crossing, as
      the boundary node chose to pass them, not as ambient state.

    Two independent enforcements, which is the right number for a claim this
    load-bearing: the boundary node *assembles* what may cross, and this view
    *names* what the stage may read.
    """

    crossing: Crossing | None = None
    antithesis: Antithesis | None = None
    antithesis_attempts: int = 0
    turn: int = 2


class CounterView(_View):
    """Stage ④ spend, funded at ``base + N``.

    Same denial as :class:`AntithesisView`, plus the antithesis itself, because
    the spend is in service of it.
    """

    crossing: Crossing | None = None
    antithesis: Antithesis | None = None
    counter_findings: list[Finding] = Field(default_factory=list)
    spend: list[SpendEntry] = Field(default_factory=list)
    turn: int = 2


class PresentView(_View):
    """Stage ⑤ — the widest view in the cycle, matching the widest tool surface.

    This is the one stage that *should* see both frames: its job is to report the
    contention, and it cannot do that from inside either one. It is also the
    stage that must state the budget asymmetry every time, because
    5N against 5+N produces a lopsided evidence set by construction and a
    lopsided set reads as a conclusion.

    ⚠️ This stage is exploration required. The view is wide because the
    reporting job is wide, not because its shape is settled (the report's shape is unresolved).
    """

    prompt: str = ""
    explicits: list[Explicit] = Field(default_factory=list)
    parked: list = Field(default_factory=list)
    orientation: str = ""
    assumptions: list[Assumption] = Field(default_factory=list)
    allocations: dict[str, int] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    antithesis: Antithesis | None = None
    counter_findings: list[Finding] = Field(default_factory=list)
    spend: list[SpendEntry] = Field(default_factory=list)
    turn: int = 3
    cycle: int = 0


class ReplyView(_View):
    """Reading the user's raw-text reply into proposed calls.

    Sees everything the reply might be *about*, which is the same surface as
    :class:`PresentView`, plus the reply. Whether presenting and ingesting are
    different frames deserving different turns is unresolved — it is the same
    argument that split thesis from antithesis. They are separate *nodes* here
    so that splitting them into separate turns later is an edge change rather
    than a rewrite.
    """

    prompt: str = ""
    explicits: list[Explicit] = Field(default_factory=list)
    assumptions: list[Assumption] = Field(default_factory=list)
    antithesis: Antithesis | None = None
    findings: list[Finding] = Field(default_factory=list)
    counter_findings: list[Finding] = Field(default_factory=list)
    disposition: str = ""
    reply: str = ""
    cycle: int = 0


class WriteApprovalView(_View):
    """The stage ⑤ HITL surface: the proposed calls, and what they would touch.

    Which of these calls need a human is a policy question, and it lives in
    `surface.py` rather than here — compression being the hard case, because it
    decides what the next cycle can still see. It runs on a placeholder.
    """

    proposed: list[ProposedWrite] = Field(default_factory=list)
    reply: str = ""
    cycle: int = 0


#: Every view the graph installs, for the import-time check below.
ALL_VIEWS: tuple[type[_View], ...] = (
    PromptView,
    ExtractView,
    ApprovalView,
    OrientView,
    FormView,
    InvestigateView,
    AntithesisView,
    CounterView,
    PresentView,
    ReplyView,
    WriteApprovalView,
)


def fields_not_in_cycle() -> dict[str, tuple[str, ...]]:
    """Views naming a field :class:`~.state.Cycle` does not have.

    Empty is the only correct answer. Kept here rather than in a test so the
    invariant travels with the thing it constrains; a test should call it.
    """
    from .state import Cycle

    known = set(Cycle.model_fields)
    bad = {}
    for view in ALL_VIEWS:
        missing = tuple(f for f in view.model_fields if f not in known)
        if missing:
            bad[view.__name__] = missing
    return bad
