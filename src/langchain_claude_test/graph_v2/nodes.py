"""The stages, as nodes. One node is one harness turn, or one pure decision.

Each node appears with the two things that define it: the **view** it is handed
(what it may see) and the **payload** it must return (what it may say). Reading
a node top to bottom is reading its whole contract.

Three invariants hold across the file and are the reason it is shaped this way.

**One node is one harness turn, never one tool call.** A single turn can spend
several priced calls *and* return a typed payload — measured, in
`spike_05_tools_and_structured_output.py`. Making the graph step per tool call
would spawn a fresh subprocess mid-stage and throw away the model's working
context between calls, which is the opposite of what a stage is for.

**A priced node never interrupts, and an interrupting node never spends.** The
body above an ``interrupt()`` re-runs on resume while the state update commits
once — measured in `spike_07_interrupt_replay.py`:

    side effects, in order : ['above-the-wait', 'above-the-wait', 'below-the-wait']
    committed debits       : [2]

So spend and approval live in separate nodes. That is not only a safety rule: it puts
the difference between a user message and a user approval into the topology,
because an approval is a permission on a call rather than an input to a stage.

**A node debits by returning state.** The meter accumulates into itself and the
node hands back its entries as a delta. Replay re-runs the turn and recounts,
so nothing is ever written twice.

⚠️ **Stage 1 scope.** The bodies are real — the views, the requests, the deltas
and the routing are the architecture. What is not built is the harness that
answers a request (`harness.py`, stage 2) and the prompt text (stage 3). Where a
prompt is quoted from the design it is quoted; where it is not, it is marked.
"""

from __future__ import annotations

from typing import Literal

from langgraph.runtime import Runtime
from langgraph.types import interrupt
from pydantic import BaseModel, ConfigDict, Field

from . import budget
from .context import ControlContext
from .harness import StageRequest
from .state import (
    Antithesis,
    Assumption,
    Candidate,
    Crossing,
    Cycle,
    Explicit,
    Finding,
    Parked,
    ProposedWrite,
)
from .surface import available, needs_approval
from .views import (
    AntithesisView,
    ApprovalView,
    CounterView,
    ExtractView,
    FormView,
    InvestigateView,
    OrientView,
    PresentView,
    PromptView,
    ReplyView,
    WriteApprovalView,
)

# ---------------------------------------------------------------------------
# Prompt containers
#
# The design supplies two of these verbatim and describes a third. The rest are
# placeholders: writing them is stage 3, and a plausible-sounding prompt in a
# stage-1 scaffold is exactly the kind of thing that later gets mistaken for a
# decision someone made.
# ---------------------------------------------------------------------------

#: The user's own words for the antithesis container.
ANTITHESIS_CONTAINER = "create the antithesis of these assumptions and findings"

#: Paraphrased from the user's description of what this stage presents.
#: The list is theirs; the wording around it is not, and stage 3 replaces it.
PRESENT_CONTAINER = (
    "Take the graph, the findings, the original prompt and the facts. Present what is "
    "there, how it relates to the user's question, what is missing, what is not known, "
    "and suggestions for moving forward."
)

_TODO_PROMPT = "⚠️ stage 3 — prompt text not written"

DISCIPLINE = _TODO_PROMPT


# ---------------------------------------------------------------------------
# Payloads — what each stage is allowed to return
# ---------------------------------------------------------------------------


class _Payload(BaseModel):
    """Common config for everything crossing the SDK boundary.

    ``extra="forbid"`` closes the object on the way back in. It also emits
    ``additionalProperties: false``, which the CLI's validator accepts —
    measured, so this is not a guess about the wire format.
    """

    model_config = ConfigDict(extra="forbid")


class ExtractionPayload(_Payload):
    """Stage ① — candidate spans, and nothing resembling a conclusion."""

    candidates: list[Candidate] = Field(
        min_length=1,
        max_length=5,
        description=(
            "Verbatim spans copied character-for-character out of the user's message. "
            "One per distinct thing they asked for. Copy; do not rewrite, tidy grammar "
            "or expand abbreviations."
        ),
    )


class OrientationPayload(_Payload):
    """Stage ② — a landscape reading. Forms no claim (orientation forms no claim)."""

    reading: str = Field(
        min_length=1,
        description="What the project's shape appears to be, against what the user asked.",
    )
    can_name_readings: bool = Field(
        description=(
            "Whether you can now name the distinct scenarios worth exploring. False "
            "spends another orientation turn if budget remains."
        )
    )


class AssumptionsPayload(_Payload):
    """Stage ③ authoring. Admissibility is in the fields, not in the prompt."""

    assumptions: list[Assumption] = Field(
        min_length=1,
        description=(
            "One interpretation of what the user is asking, per entry. Each must name "
            "the call whose result would change your belief about it — an assumption "
            "nothing could land on is not admissible."
        ),
    )


class FindingsPayload(_Payload):
    """Stages ③ and ④ spend. Sourced material, never fact."""

    findings: list[Finding] = Field(
        default_factory=list,
        description="Locator plus verbatim excerpt, attributed to the reading it serves.",
    )
    reasoning: list[str] = Field(
        default_factory=list,
        description=(
            "How you read the evidence. Recorded, and held back at the turn boundary — "
            "this is the affirming transcript."
        ),
    )


class AntithesisPayload(_Payload):
    """Stage ④ authoring. *"Nothing to attack" is not a permitted output.*"""

    antithesis: Antithesis = Field(
        description=(
            "The reading all of these assumptions miss. It is admissible on the same "
            "terms as any assumption and must name the call that would move it."
        )
    )


class DispositionPayload(_Payload):
    """Stage ⑤ — ⚠️ exploration required, and its shape is unresolved."""

    text: str = Field(
        min_length=1,
        description=(
            "State, evidence, options. Close nothing in either direction. Options are "
            "suggestions you may well have wrong, and that is fine."
        ),
    )


class ProposalPayload(_Payload):
    """Reading the reply into calls — the surface that resolves the binding problem."""

    proposed: list[ProposedWrite] = Field(
        default_factory=list,
        description=(
            "Each graph-write your reading of the reply implies, as a separate call. "
            "Your reading only takes effect as one of these, and the user approves the "
            "call — so say plainly what in their words you read it from."
        ),
    )


# ---------------------------------------------------------------------------
# Turn 1 · stage ① — prompt + fact extraction
# ---------------------------------------------------------------------------


def register_prompt(state: PromptView) -> dict:
    """Admit the user's message verbatim. No inference happens here.

    A near-empty node that earns its place: it is where "the prompt's authority
    is the user's" has somewhere to be true. Nothing is derived, nothing is
    selected, and the next node cannot run without having passed through it.
    """
    return {"cycle": state.cycle + 1, "turn": 1, "stage": "extract"}


async def extract_facts(state: ExtractView, runtime: Runtime[ControlContext]) -> dict:
    """Propose candidate facts. Selection is inference, so nothing lands yet.

    ⚠️ **This stage is parked by decision, not by oversight.** The user's words:
    *"I think we can put this to the side for now. The fact extraction has more
    nuance at the moment than i anticipated, so I'd like to see a working base
    loop before extending the finer details."* So it runs on a placeholder
    budget and the simplest possible contract — one pass, candidates out — and
    the nuance is deferred until the loop turns over end to end.
    """
    ctx = runtime.context
    pool_cap = ctx.budgets.extraction_pool
    result = await ctx.harness.run(
        StageRequest(
            label="extract",
            stage="extract",
            system=DISCIPLINE,
            prompt=_TODO_PROMPT,
            payload_schema=ExtractionPayload,
            graph_writes=available("extract"),
            pools={budget.EXTRACTION: pool_cap},
            default_pool=budget.EXTRACTION,
            prior_spend=(),
            turn=1,
        )
    )
    payload: ExtractionPayload = result.payload  # type: ignore[assignment]
    return {"candidates": payload.candidates, "spend": list(result.spend)}


def approve_facts(state: ApprovalView) -> dict:
    """The approval gate: a fact is not a fact until the user registers it.

    One ``interrupt()`` per candidate, because the subject of that rule is literally
    the *tool call* — approval is per call, not per batch. The loop is safe under
    replay: on resume the node restarts and each already-answered
    ``interrupt()`` returns the value it was given, so only the unanswered one
    pauses again. That only holds because nothing in this node has a side
    effect and nothing above the waits costs anything.

    A denial parks the candidate **with its reason**. If the reason does not
    survive, the next cycle re-extracts the same candidate and pays for it
    again — the first purpose of pricing undone by the mechanism meant to serve it.
    """
    explicits: list[Explicit] = []
    parked: list[Parked] = []

    for candidate in state.candidates:
        decision = interrupt(
            {
                "call": "propose_fact",
                "candidate": candidate.model_dump(),
                "prompt": state.prompt,
                "question": "Are these your own words, as a fact to work from?",
            }
        )
        approved = bool(decision.get("approved")) if isinstance(decision, dict) else bool(decision)
        note = decision.get("note", "") if isinstance(decision, dict) else ""

        if approved:
            explicits.append(
                Explicit(
                    id=f"e{state.cycle}.{candidate.id}",
                    quote=candidate.quote,
                    start=candidate.start,
                    cycle=state.cycle,
                )
            )
        else:
            # "denied" and "unanswered" are different parkings and the design
            # keeps them apart (ledger/models.py:32 — "never self-resolves").
            answered = isinstance(decision, dict) and "approved" in decision
            reason = "denied" if answered else "unanswered"
            parked.append(
                Parked(candidate=candidate, reason=reason, note=note, cycle=state.cycle)
            )

    return {"explicits": explicits, "parked": parked, "stage": "orient"}


# ---------------------------------------------------------------------------
# Turn 1 · stage ② — budget context pass
# ---------------------------------------------------------------------------


async def orient(state: OrientView, runtime: Runtime[ControlContext]) -> dict:
    """Reconcile the user's input against the landscape of the project.

    Carries **no graph-write tools at all** — ``available("orient")`` is empty,
    which is what makes "forms no claim" enforceable rather than merely
    intended. Spends from an unattached pool, because the assumptions this will
    fund do not exist yet.

    This is where going wide before going deep is actually produced, and it is
    not produced by unit prices — an agent with ten points can spend all ten on
    one chain. It is produced by the stage boundary: per-assumption budget does
    not exist until assumptions do, and assumptions are not formable without the
    wide pass. Prices are left with one job, context hygiene, which is the job
    they are good at.
    """
    ctx = runtime.context
    # Placeholder value — the design never assigned this pool a number. See the
    # provisional list in `context.py`; it must not be read as settled.
    cap = ctx.budgets.orientation_pool
    result = await ctx.harness.run(
        StageRequest(
            label=f"orient.{state.orientation_turns}",
            stage="orient",
            system=DISCIPLINE,
            prompt=_TODO_PROMPT,
            payload_schema=OrientationPayload,
            graph_writes=available("orient"),
            pools={budget.ORIENTATION: cap},
            default_pool=budget.ORIENTATION,
            prior_spend=tuple(state.spend),
            turn=state.turn,
        )
    )
    payload: OrientationPayload = result.payload  # type: ignore[assignment]
    return {
        "orientation": payload.reading,
        "orientation_turns": state.orientation_turns + 1,
        "orientation_ready": payload.can_name_readings,
        "spend": list(result.spend),
    }


def orient_ready(state: Cycle, runtime: Runtime[ControlContext]) -> Literal["orient", "form"]:
    """Another orientation turn, or on to forming readings.

    Two independent exits, and both are needed. The agent saying it can name the
    readings is the intended one; the pool running dry is the one that keeps the
    loop finite when it cannot. Exhaustion ends the stage — it does not
    fail it.
    """
    cap = runtime.context.budgets.orientation_pool
    exhausted = budget.remaining(state.spend, budget.ORIENTATION, cap) <= 0
    return "form" if state.orientation_ready or exhausted else "orient"


# ---------------------------------------------------------------------------
# Turn 1 · stage ③ — assumption pass
# ---------------------------------------------------------------------------


async def form_assumptions(state: FormView, runtime: Runtime[ControlContext]) -> dict:
    """Author N readings. Free, and deliberately so.

    "Falsification cannot be free" governs *evidence gathering*:
    when they stop and how they approach it. Authoring a reading is not
    evidence gathering, so the authoring costs nothing and the spend that
    follows is priced at the same rates for every reading.

    Passes no pools at all, which means the meter refuses any priced call here.
    That is the point: the stage's job is to state claims, and a claim that
    needed a look was formed in the wrong stage.
    """
    ctx = runtime.context
    result = await ctx.harness.run(
        StageRequest(
            label=f"form.{state.form_attempts}",
            stage="assume",
            system=DISCIPLINE,
            prompt=_TODO_PROMPT,
            payload_schema=AssumptionsPayload,
            graph_writes=available("assume"),
            pools={},
            turn=1,
        )
    )
    payload: AssumptionsPayload = result.payload  # type: ignore[assignment]
    stamped = [
        a.model_copy(update={"formed_against": state.orientation})
        for a in payload.assumptions
    ]
    return {"assumptions": stamped, "form_attempts": state.form_attempts + 1}


def inadmissible(assumptions: list[Assumption]) -> tuple[str, ...]:
    """Ids of readings nothing could land on.

    *"we want assumptions to be avenues available for information to stick.
    There is no point in assuming something unprovable."*

    Enforced at *formation*, not after sign-off. The built pipeline already has
    a field for what a search is expected to show, but it sits after the
    approval gate, where it functions as a plan. Moved to formation, the same
    statement becomes the filter on what may exist — and it is also what defines
    the allocation.
    """
    return tuple(a.id for a in assumptions if not a.moved_by.strip())


def admissible_route(
    state: Cycle, runtime: Runtime[ControlContext]
) -> Literal["form", "fund", "escalate"]:
    """Re-author, fund, or give up and say so.

    **The ceiling on how many readings may exist is enforced here.** The agent
    is meant to choose how many scenarios are worth exploring, but the turn is
    funded at five points per reading and the next at base plus the reading
    count — so an agent choosing that count freely would be choosing its own
    budget, which the rule that *"the agent can never set their own values"*
    forbids. The ceiling is therefore graph-owned, and exceeding it routes back
    to re-authoring rather than being silently truncated. The value itself is a
    placeholder; see the provisional list in `context.py`.
    """
    caps = runtime.context.budgets
    too_many = len(state.assumptions) > caps.max_assumptions
    if not inadmissible(state.assumptions) and not too_many:
        return "fund"
    if state.form_attempts >= caps.max_reauthor_attempts:
        return "escalate"
    return "form"


def fund_assumptions(state: Cycle, runtime: Runtime[ControlContext]) -> dict:
    """Set each reading's allocation. Graph-set, never agent-set.

    Flat, because falsification cannot be free: cost may not be attached to the direction of a
    conclusion, and any weighting would have to come from somewhere — the
    agent's own confidence being the only signal on offer.
    """
    allocations = budget.allocate([a.id for a in state.assumptions], runtime.context.budgets)
    return {"allocations": allocations, "stage": "assume"}


async def investigate(state: InvestigateView, runtime: Runtime[ControlContext]) -> dict:
    """Spend each reading's budget, in one turn.

    **Why one turn holds several budgets.** The restriction is *per assumption*
    — *"I plan to solve this by having tool call restrictions per assumption"* —
    while the findings for every reading are registered *"in one turn"*. Both
    hold only if a single turn can debit several separate pools, and that
    requires every priced call to name the reading it serves. So the meter is
    handed one pool per assumption and no fallback, and a call naming none is
    refused rather than charged somewhere convenient. That is a constraint on
    how the tools are shaped, and it is the one open item the next stage hits
    first.

    ``reasoning`` comes back on the payload and goes onto
    ``thesis_reasoning``, which accumulates and is never lost — and which turn 2
    cannot see, because :class:`~.views.AntithesisView` does not name it.
    """
    ctx = runtime.context
    pools = {budget.assumption_pool(aid): cap for aid, cap in state.allocations.items()}
    result = await ctx.harness.run(
        StageRequest(
            label="investigate",
            stage="assume",
            system=DISCIPLINE,
            prompt=_TODO_PROMPT,
            payload_schema=FindingsPayload,
            graph_writes=available("assume"),
            pools=pools,
            default_pool="",  # unattributed calls are refused, not pooled
            prior_spend=tuple(state.spend),
            turn=1,
        )
    )
    payload: FindingsPayload = result.payload  # type: ignore[assignment]
    return {
        "findings": payload.findings,
        "thesis_reasoning": payload.reasoning,
        "spend": list(result.spend),
    }


# ---------------------------------------------------------------------------
# The turn boundary
# ---------------------------------------------------------------------------


def turn_1_close(state: Cycle) -> dict:
    """Assemble what crosses into turn 2.

    **The one node with full sight, on purpose.** Every other node is handed a
    view; this one takes the whole state, because assembling a projection is
    precisely the job that requires seeing what is being left out. Doing it in a
    node rather than in a filter means the result is checkpointed — what crossed
    is a recorded object, not a transient computation.

    What is held back is held back by *not being built into the crossing*:
    the reasoning transcript, confidence language, and each finding's
    ``answers`` field — the thesis explaining why the evidence mattered
    — the affirming frame in one field. :meth:`~.state.Finding.neutralise` drops
    it, and returns a different type so the omission is checkable.

    The residual leak stays open and is not closeable here: the excerpts are
    re-checkable, but *which* excerpts were selected was an affirming-frame
    decision. That is what the ``N`` term in ``base + N`` is for.
    """
    crossing = Crossing(
        prompt=state.prompt,
        explicits=tuple(state.explicits),
        assumptions=tuple(state.assumptions),
        findings=tuple(f.neutralise() for f in state.findings),
        spend=tuple(state.spend),
        parked=tuple(state.parked),
    )
    return {"crossing": crossing, "turn": 2, "stage": "antithesis"}


# ---------------------------------------------------------------------------
# Turn 2 · stage ④ — antithesis pass · internal turn
# ---------------------------------------------------------------------------


async def antithesis(state: AntithesisView, runtime: Runtime[ControlContext]) -> dict:
    """Author the reading all N assumptions miss (the antithesis is a node).

    A node, not a property of each assumption. One antithesis aimed at the
    *set* asks "what reading do all N miss?", which is the only form that can
    catch a misreading the whole set shares — a per-assumption rival is authored
    inside the very frame it was meant to question.

    Free to author, priced to pursue, same as the thesis. The container is
    the user's own words.
    """
    ctx = runtime.context
    crossing = state.crossing
    if crossing is None:  # pragma: no cover — the boundary node always runs first
        raise RuntimeError("stage ④ reached with no crossing: the turn boundary did not run")

    result = await ctx.harness.run(
        StageRequest(
            label=f"antithesis.{state.antithesis_attempts}",
            stage="antithesis",
            system=DISCIPLINE,
            prompt=ANTITHESIS_CONTAINER,
            payload_schema=AntithesisPayload,
            graph_writes=available("antithesis"),
            pools={},  # authoring is free
            turn=2,
        )
    )
    payload: AntithesisPayload = result.payload  # type: ignore[assignment]
    return {
        "antithesis": payload.antithesis,
        "antithesis_attempts": state.antithesis_attempts + 1,
    }


def antithesis_route(
    state: Cycle, runtime: Runtime[ControlContext]
) -> Literal["antithesis", "counter", "escalate"]:
    """Re-author, or fund the attack.

    *"There is nothing to attack" is not a permitted output* — for the same
    reason that falsification cannot be free rules out the agent classifying its
    own search, it does not
    get to classify the attack as unnecessary. So an empty or unmovable
    antithesis routes back to re-authoring.

    Nothing in the design says what happens when re-authoring runs out of
    attempts, so this routes to an escalation that asks rather than picking an
    answer. The attempt ceiling itself is a placeholder.
    """
    caps = runtime.context.budgets
    anti = state.antithesis
    ok = anti is not None and bool(anti.claim.strip()) and bool(anti.moved_by.strip())
    if ok:
        return "counter"
    if state.antithesis_attempts >= caps.max_reauthor_attempts:
        return "escalate"
    return "antithesis"


async def counter_investigate(state: CounterView, runtime: Runtime[ControlContext]) -> dict:
    """Spend ``base + N`` against the thesis.

    One pool, not N: the antithesis is a single node, so there is a single
    allocation and nothing to attribute between. The two terms in the formula
    answer different problems and are kept separate in `budget.py` rather than
    collapsed into one number.
    """
    ctx = runtime.context
    crossing = state.crossing
    n = len(crossing.assumptions) if crossing else 0
    cap = budget.antithesis_budget(n, ctx.budgets)
    result = await ctx.harness.run(
        StageRequest(
            label="counter",
            stage="antithesis",
            system=DISCIPLINE,
            prompt=ANTITHESIS_CONTAINER,
            payload_schema=FindingsPayload,
            graph_writes=available("antithesis"),
            pools={budget.ANTITHESIS: cap},
            default_pool=budget.ANTITHESIS,
            prior_spend=tuple(state.spend),
            turn=2,
        )
    )
    payload: FindingsPayload = result.payload  # type: ignore[assignment]
    return {"counter_findings": payload.findings, "spend": list(result.spend)}


def turn_2_close(state: Cycle) -> dict:
    """Close the internal turn.

    Turn 2 presents nothing. Exhaustion normally forces a reply, but applying
    that here would show the user turn 1's affirming findings before anything
    had challenged them — and their reaction would ratify the frame. An internal
    turn exhausts, the graph refreshes, and the next stage runs. Both are still
    mini-sessions inside the larger session; only a user turn presents.
    """
    return {"turn": 3, "stage": "present"}


# ---------------------------------------------------------------------------
# Turn 3 · stage ⑤ — present + reconcile · ⚠️ exploration required
# ---------------------------------------------------------------------------


async def present(state: PresentView, runtime: Runtime[ControlContext]) -> dict:
    """State, evidence, options — and close nothing.

    ⚠️ This stage is exploration required, and its shape is unresolved:
    flat ledger, contention-first and options-first each fail differently. The
    node exists and its inputs are settled; what it composes is not.

    **No budget, by decision.** The user's answer: *"delay for now, but no this
    is just a analyze and report stage at the moment."* So the stage opens no
    pool at all, which means the gate refuses every priced call — the stage
    cannot look anything up, and that is enforced rather than requested. It
    analyses what the cycle already gathered and reports it.

    **The budget asymmetry disclosure is appended here and nowhere else.**
    Building a case costs five points per reading while finding one hole costs
    base plus the reading count, so the evidence set is lopsided by
    construction — and a lopsided evidence set reads as a conclusion. Appended
    unconditionally rather than left to the prompt: if the model were trusted to
    mention it, the budget design would quietly do the concluding that the rule
    against the agent closing a node forbids, on every turn it forgot.
    """
    ctx = runtime.context
    result = await ctx.harness.run(
        StageRequest(
            label="present",
            stage="present",
            system=DISCIPLINE,
            prompt=PRESENT_CONTAINER,
            payload_schema=DispositionPayload,
            graph_writes=available("present"),
            pools={},  # analyse and report: no pool, so no priced call is possible
            prior_spend=tuple(state.spend),
            turn=3,
        )
    )
    payload: DispositionPayload = result.payload  # type: ignore[assignment]
    disclosure = budget.asymmetry_disclosure(len(state.assumptions), ctx.budgets)
    return {
        "disposition": f"{payload.text}\n\n{disclosure}",
        "spend": list(result.spend),
    }


def await_reply(state: Cycle) -> dict:
    """Hand off, and wait for raw text.

    A *message*, not an approval — the two surfaces are different things
    entirely. This one carries authority on arrival and adds words; the one in
    :func:`approve_writes` is a permission and adds none.

    Spends nothing and writes nothing above the wait, which is what makes it
    safe to replay. The disposition was composed in the previous node precisely
    so that it is not recomposed every time this one resumes.
    """
    reply = interrupt({"present": state.disposition, "awaiting": "reply"})
    return {"reply": reply if isinstance(reply, str) else str(reply)}


async def read_reply(state: ReplyView, runtime: Runtime[ControlContext]) -> dict:
    """Turn the reply into proposed calls — never into a silent reinterpretation.

    This is where the binding problem is closed. The risk in reading free prose
    is the agent quietly deciding what the user meant, in the worst possible
    place, because a misread reply rewrites the graph. It is unreachable here
    because a message and an approval are different surfaces and availability is
    gated by stage: the reading only takes effect as a tool call, and
    the call is what gets approved. Approving it confirms the *binding*, not the
    claim.

    Whether presenting and ingesting belong in different turns is unresolved — the
    same argument that split thesis from antithesis. They are separate nodes
    here so that splitting them later is an edge change, not a rewrite.
    """
    ctx = runtime.context
    result = await ctx.harness.run(
        StageRequest(
            label="read_reply",
            stage="present",
            system=DISCIPLINE,
            prompt=_TODO_PROMPT,
            payload_schema=ProposalPayload,
            graph_writes=available("present"),
            pools={},  # same stage, same answer: analyse and report, no lookups
            turn=3,
        )
    )
    payload: ProposalPayload = result.payload  # type: ignore[assignment]
    return {"proposed": payload.proposed, "spend": list(result.spend)}


def approve_writes(state: WriteApprovalView) -> dict:
    """Approval on the authority-changing calls.

    Registering or promoting a fact always pauses: *"A fact isnt a fact until it
    is explicitly registered via a user, so all tool calls that register
    facts/explicits are hitl approvals."*

    Compression and discard are the hard case — they register no fact, yet they
    decide what the next cycle can still see — and they run on a placeholder
    that defaults to *pause anyway*. Deferred rather than decided, and marked as
    such where the placeholder lives.
    """
    approved: list[str] = []
    for write in state.proposed:
        if not needs_approval(write.write):  # placeholder default for compress/discard
            approved.append(write.id)
            continue
        decision = interrupt(
            {
                "call": write.write,
                "argument": write.argument,
                "because": write.because,
                "target": write.target_id,
                "question": "Approve this change to the graph?",
            }
        )
        if bool(decision.get("approved")) if isinstance(decision, dict) else bool(decision):
            approved.append(write.id)
    return {"approved_writes": approved}


def apply_writes(state: Cycle) -> dict:
    """Apply what was approved. The context edit is now an approved call.

    ⚠️ **Stage 2.** What survives as graph and what is thrown away is unresolved,
    and so is the form it survives in — and the one constraint that is settled is that
    parked reasons must survive or the next cycle re-proposes dead ground and
    pays for it again. "Keep everything" is not compaction, so this is not a
    matter of defaulting to the safe option.
    """
    raise NotImplementedError(
        "applying approved writes is stage 2 — compaction policy unresolved"
    )


def next_cycle(state: Cycle) -> Literal["register", "__end__"]:
    """Another cycle, or done.

    **Where a new message enters the flow is undecided.** The reply that arrived
    at :func:`await_reply` may *be* the next cycle's prompt, or reconciling it
    against the existing graph may fold into the extraction pass — a candidate
    answer, not a settled one. Until it is settled this ends the run rather than
    looping on an assumption about where a message enters.
    """
    return "__end__"


def escalate(state: Cycle) -> dict:
    """Re-authoring ran out of attempts. Ask, rather than proceed.

    Nothing in the design says what happens here, so nothing is chosen. The
    alternatives all decide something: proceeding accepts an inadmissible node,
    skipping accepts "nothing to attack" as an output, and failing throws away a
    paid-for turn. Asking is the only one that decides nothing.
    """
    decision = interrupt(
        {
            "call": "escalate",
            "reason": "re-authoring exhausted its attempts",
            "assumptions": [a.model_dump() for a in state.assumptions],
            "antithesis": state.antithesis.model_dump() if state.antithesis else None,
            "question": "Nothing admissible was authored. How should this proceed?",
        }
    )
    return {"escalation": str(decision)}
