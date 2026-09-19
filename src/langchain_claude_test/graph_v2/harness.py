"""The inner layer — the Agent SDK harness, opened per node.

The outer graph owns stage order, state, the turn boundary, approval and
forking. This boundary owns one model call: which tools exist for it, what each
call costs, and what shape the answer comes back in. Nothing here knows what
stage comes next, and nothing in the graph knows what the model decided inside.

Three constraints are settled and must not be re-litigated by an implementation:

1. **Subscription billing.** The transport is ``claude_agent_sdk``, which is
   what keeps the run on a subscription rather than per-token API billing. The
   raw SDK inherits the whole parent environment
   (`subprocess_cli.py:812`) and the CLI prefers an API key when it finds one,
   so :data:`SUBSCRIPTION_ENV` blanks them. Already tested; not re-tested.
2. **An allow-list, never a deny-list.** ``tools=[]`` plus an in-process MCP
   server carrying exactly the stage's surface. Deny-listing leaked under test:
   blocking ``Read`` just made the model reach for ``Bash``. Staged availability
   only binds if the built-in surface is off entirely.
3. **``permission_mode="default"``.** ``bypassPermissions`` auto-approves before
   ``can_use_tool`` is consulted and the SDK raises ``CanUseToolShadowedWarning``
   at connect time. So does an ``allowed_tools`` entry that allows a whole tool.
   A gate that looks present and always says yes is worse than no gate.

⚠️ **Stage 1 scope.** This file declares the boundary: the protocol, the request
and result shapes, the meter that prices calls, and the options builder. The
implementation that actually opens a subprocess is stage 2, and
:class:`UnbuiltHarness` is what the graph gets until then — it refuses rather
than pretending.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Literal, Mapping, Protocol

from pydantic import BaseModel

from . import budget
from .state import Decision, Explicit, Finding, Parked, ProposedWrite, SpendEntry
from .surface import GATED, UNGATED, Stage, Tool, gated

if TYPE_CHECKING:  # pragma: no cover
    from claude_agent_sdk import PermissionResult, ToolPermissionContext

#: The CLI prefers an API key over OAuth when one is present, and the SDK passes
#: the parent environment through verbatim. Blanking these is what keeps the run
#: on the subscription. Same constant, same reason, as `session/model.py:33`.
SUBSCRIPTION_ENV: Mapping[str, str] = {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": ""}

#: The synthetic tool call ``output_format`` arrives as. It appears in the
#: model's tool-use stream and is **never shown to ``can_use_tool``** (measured,
#: `spike_05_tools_and_structured_output.py`). Two consequences for a budget
#: that decrements per call:
#: price only what the gate is consulted about, and no invariant may claim that
#: every tool call passes the gate — for this one call it is false.
STRUCTURED_OUTPUT_TOOL = "StructuredOutput"


# ---------------------------------------------------------------------------
# What a node asks for, and what it gets back
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StageRequest:
    """One harness turn, as a node describes it.

    One node is one turn, not one tool call. A single turn can spend several
    priced calls *and* return a typed payload — measured, so a stage does not
    have to split into two turns for a mechanical reason. Where the design does
    split turns it is for the design's own reason, which is the right
    way round.
    """

    label: str
    stage: Stage
    system: str
    prompt: str
    #: The pydantic model the answer must validate against. Crosses the SDK
    #: boundary as a transformed wire schema; the ledger keeps this type.
    payload_schema: type[BaseModel]
    #: The tools this frame carries — evidence calls and writes both. Empty is
    #: legal, and is what the last frame uses: it reports and cannot look.
    tools: frozenset[Tool] = frozenset()
    #: Pool name -> cap. **In practice there is exactly one, or none.**
    #:
    #: It is a mapping because the restriction is *per reading*, and that once
    #: looked like one turn debiting several pools — which would have required
    #: every priced call to name the reading it served, and was flagged twice as
    #: the hardest thing this boundary had to do. The problem dissolved when the
    #: assume frame became one reading per turn: one pool is open, so there is
    #: nothing to attribute and no call that can be misattributed. The shape
    #: stays plural because the *cap* is still per reading; what went away is the
    #: need to ask the model which one it meant.
    #:
    #: Empty is legal, and is what the last frame uses: no pool means every
    #: priced call is refused before it is priced.
    pools: Mapping[str, int] = field(default_factory=dict)
    #: Already-recorded spend, so the meter derives each balance rather than
    #: being handed one (the agent never sets its own values).
    prior_spend: tuple[SpendEntry, ...] = ()
    #: The pool every priced call in this turn draws from. Empty means there is
    #: none, so a priced call is refused before it is priced — which is what the
    #: reporting frame wants, and the second enforcement of its having no budget.
    default_pool: str = ""
    #: Whether this turn continues the running conversation or opens a new one.
    #:
    #: **This is the turn boundary, made mechanical.** Continuity is why a prompt
    #: can be a thin instruction wrapper: what the model already said is already
    #: there, so nothing has to be re-rendered into text. The readings named in
    #: one turn are in the next turn's context for free, and so is everything an
    #: earlier reading looked at — which is what stops the second reading paying
    #: to read the same file.
    #:
    #: **Every frame in the cycle continues.** The rival was the one candidate
    #: for starting fresh, since a continued conversation carries the whole
    #: affirming transcript and nothing structural can withhold it. Your call was
    #: that it continues anyway and the reframe is carried by the prompt, in
    #: orders — so the turn boundary is an instruction rather than a structure.
    #: What this flag now marks is the start of a *cycle*, not a reframing.
    continues: bool = False
    #: Extra middleware wrapped around every tool call, outermost first. The
    #: budget meter is always present and is not listed here — this is for
    #: anything else a frame wants in the path: a recorder, a redactor, a cache
    #: that serves a locator already read.
    middleware: tuple["ToolMiddleware", ...] = ()
    #: Renders the line appended to every tool result, given what is left in the
    #: pool the call drew from.
    #:
    #: A budget stated once at the top of a turn is a budget the model is
    #: guessing at by its fourth call. Appending it to each result means the
    #: count comes from the meter that is actually keeping it, at the moment it
    #: changes, and costs nothing — it rides on a message already being sent.
    status: "Callable[[int], str] | None" = None
    turn: int = 1


@dataclass(frozen=True, slots=True)
class TurnResult:
    """What one harness turn produced.

    ``spend`` is returned rather than applied. The node puts it on the state
    channel, which is the whole of the interrupt-replay rule: a priced node
    debits by returning state, never by a side effect.
    """

    payload: BaseModel
    spend: tuple[SpendEntry, ...] = ()
    #: Recorded tool results, keyed by call id. A finding's excerpt is checked
    #: against these — which is what stops the agent being its own witness.
    tool_results: Mapping[str, str] = field(default_factory=dict)
    #: Calls the meter refused, with the reason. Exhaustion ends the stage
    #: (exhaustion forces a reply); it is not an error.
    refused: tuple[str, ...] = ()
    #: Records created by this turn's ``attach_finding`` calls, in call order.
    #:
    #: Findings arrive as calls rather than on the payload because each is
    #: individually checkable — the excerpt has to appear in ``tool_results`` —
    #: and because nothing bounds how many there should be. They come back
    #: **unstamped**: the harness does not know which reading is being funded, so
    #: the node sets ``assumption_id`` before returning them. The graph assigns
    #: the id, as it does everywhere else.
    findings: tuple[Finding, ...] = ()
    #: Every authority-bearing call the turn made, whether you allowed it or not.
    #: A proposal is a record in its own right: what the agent wanted to do is
    #: worth keeping even when the answer was no.
    proposals: tuple[ProposedWrite, ...] = ()
    #: Your answers to them, in call order, one per proposal.
    decisions: tuple[Decision, ...] = ()
    #: Facts registered because you allowed them. Your own words, carrying
    #: authority — which is why they are a separate channel from anything the
    #: agent authored.
    explicits: tuple[Explicit, ...] = ()
    #: Proposals you refused, parked *with your reason*, so the next cycle does
    #: not pay to re-propose ground you have already closed.
    parked: tuple[Parked, ...] = ()
    raw_reply: str = ""


class StageHarness(Protocol):
    """The seam the graph depends on.

    Narrow on purpose: the graph asks for one turn and gets a result. Anything
    wider would let stage ordering leak inward, which is the boundary this whole
    architecture exists to hold.
    """

    async def run(self, request: StageRequest) -> TurnResult:
        """Open a harness turn, price every call, return the validated payload."""
        ...


class HarnessUnavailable(RuntimeError):
    """The model could not be reached, or refused to answer."""


class UnbuiltHarness:
    """The stage-1 stand-in. Refuses, and says which stage builds it.

    Deliberately not a fake that returns plausible data: a scaffold that
    silently produces answers is the failure mode this project exists to catch.
    A scripted harness for replay tests is stage 2's job and belongs beside the
    real one, the way ``FakeModel`` sits beside ``SdkModel``.
    """

    async def run(self, request: StageRequest) -> TurnResult:
        raise NotImplementedError(
            f"harness not built (stage 2) — {request.stage}/{request.label} asked for "
            f"{request.payload_schema} with {len(request.tools)} tool(s) "
            f"against pools {dict(request.pools)}"
        )


# ---------------------------------------------------------------------------
# The meter — where a call is priced and where a budget is enforced
# ---------------------------------------------------------------------------


#: The price class for a write into the store, as opposed to a call that goes
#: and looks. Whether bookkeeping is priced at all is unsettled, so it runs on one
#: placeholder field rather than a literal scattered through the code.
GRAPH_WRITE_CLASS = "graph_write"


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One call, as the middleware chain sees it before it runs."""

    name: str
    input: Mapping[str, Any]
    id: str
    pool: str
    call_class: str
    price: int


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    """What the call produced. ``ok`` is false for an error or a timeout."""

    ok: bool
    result: str


class ToolMiddleware(Protocol):
    """Wrapped around every tool call, in two halves.

    The same shape as LangChain's tool-call middleware, which cannot be used
    here: that API attaches to a prebuilt agent, and this design has no chat
    model in it at all. The hooks are the same two questions either way — may
    this run, and what happened when it did.

    ``before`` returns ``None`` to allow, or a reason to refuse. It is where
    everything that must be decided gets decided: **a tool cannot be interrupted
    after it runs**, so anything that must not happen has to be caught here, and
    anything recorded about the decision is recorded here too.

    ``after`` cannot stop anything and is not asked to. It sees what the call
    produced and may rewrite what the model is shown.
    """

    def before(self, call: ToolCall) -> str | None: ...

    def after(self, call: ToolCall, outcome: ToolOutcome) -> ToolOutcome: ...


class Meter(ToolMiddleware):
    """The budget middleware. **Charges before the call runs.**

    Both halves of the question are answered in :meth:`before` — can this be
    afforded, and if so it is spent. :meth:`after` only reports where that left
    things.

    **Why the charge is not held until the call comes back.** It could be:
    reserve on the way in, settle or release on the way out, refunding a call
    that timed out. It is not worth what it costs. A reservation is state in
    flight, and a harness that dies mid-call leaves one that is never settled and
    never released, so the balance is silently wrong in the direction that
    matters. Charging on authorisation has nothing in flight to lose.

    It is also the more honest reading of what the budget prices. The limit is on
    *when the agent stops looking and how it approaches it* — the decision to
    spend, not the luck of the result. A call that came back empty was still a
    call it chose to make, and refunding it would make an unlucky lookup cheaper
    than a useful one.

    **It accumulates into itself, not into the graph's state.** LangGraph commits
    a node's update when the node returns, so there is no writing to graph state
    from inside a tool call. This ledger *is* the immediate one: the next call's
    affordability is answered from it, and the node hands the whole of it back as
    a delta when the turn is over. If the node is replayed the turn re-runs and a
    fresh meter recounts — nothing was written twice because nothing was written
    at all.
    """

    def __init__(
        self,
        *,
        pools: Mapping[str, int],
        prices: Mapping[str, int],
        prior_spend: tuple[SpendEntry, ...] = (),
        default_pool: str = "",
        turn: int = 1,
        stage: Stage = "orientate",
        graph_write_price: int = 0,
        route: "CallRouter | None" = None,
        status: "Callable[[int], str] | None" = None,
    ) -> None:
        self.pools = dict(pools)
        self.prices = prices
        self.default_pool = default_pool
        self.graph_write_price = graph_write_price
        self.turn = turn
        self.stage = stage
        self.status = status
        self._prior = tuple(prior_spend)
        self._route = route or route_call
        #: Charged calls, in order. The node's delta.
        self.entries: list[SpendEntry] = []
        #: Calls refused, with the reason. Exhaustion is an outcome, not an
        #: error: it ends the stage rather than failing it.
        self.refused: list[str] = []

    def remaining(self, pool: str) -> int:
        """What is left: the cap, less everything charged before and during."""
        return budget.remaining(
            list(self._prior) + self.entries, pool, self.pools.get(pool, 0)
        )

    def price(self, call_class: str) -> int:
        """What one call costs. A graph-write is bookkeeping rather than evidence
        gathering, and runs on its own placeholder rather than a literal."""
        if call_class == GRAPH_WRITE_CLASS:
            return self.graph_write_price
        return budget.price_of(call_class, self.prices)

    def describe(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        context: "ToolPermissionContext | None" = None,
    ) -> ToolCall:
        """Build the record the middleware chain is handed."""
        pool, call_class = self._route(tool_name, tool_input, self.default_pool)
        return ToolCall(
            name=tool_name,
            input=tool_input,
            id=getattr(context, "tool_use_id", "") or "",
            pool=pool,
            call_class=call_class,
            price=self.price(call_class),
        )

    def before(self, call: ToolCall) -> str | None:
        """Attribute it, price it, charge it — or refuse and say why.

        The charge lands here, so by the time the tool runs the balance already
        reflects it and the next call is answered against the real number. There
        is no window in which two calls are both told they can afford the last
        point.
        """
        if not call.pool or call.pool not in self.pools:
            self.refused.append(f"{call.name}: unattributed")
            return (
                "NO_BUDGET: this frame has no pool for that call, so there is "
                "nothing to charge it to and it cannot run."
            )

        left = self.remaining(call.pool)
        if call.price > left:
            self.refused.append(f"{call.name}: {call.pool} exhausted")
            return (
                f"BUDGET_EXHAUSTED: {call.call_class} costs {call.price} and "
                f"{left} is left. Nothing further can be bought here."
            )

        if call.price:
            self.entries.append(
                SpendEntry(
                    pool=call.pool,
                    call=call.call_class,
                    price=call.price,
                    turn=self.turn,
                    stage=self.stage,
                    tool_call_id=call.id,
                )
            )
        return None

    def after(self, call: ToolCall, outcome: ToolOutcome) -> ToolOutcome:
        """Tell the model where the charge left it. Changes no balance.

        Nothing here can stop anything — a tool cannot be interrupted once it has
        run — and nothing here is asked to. It appends the running count to what
        the model is shown, from the meter that is actually keeping it, at the
        moment it changed. That is why the count is rendered on this side: before
        the call, it would be a number about to be wrong.
        """
        if self.status is None:
            return outcome
        return ToolOutcome(
            ok=outcome.ok,
            result=outcome.result + "\n" + self.status(self.remaining(call.pool)),
        )


@dataclass(frozen=True, slots=True)
class Verdict:
    """Your answer to one gated call.

    ``words`` is the part that matters most. A refusal that says only *no*
    leaves the agent guessing at why, and leaves nothing of what you said in the
    record. Your words go back to the model as the call's result and into the
    store as *your* words — authority, rather than the agent's reading of them.

    ``answered_by`` is not decoration. An earlier attempt in this repository
    shipped a human-in-the-loop stub that returned "Approved, execute operation."
    with no human present, and nothing in the log said so. Every implementation
    sets this honestly, and anything that is not ``human`` is meant to be
    visible. It matters more here than it did there, because this gate sits in
    the middle of a live turn where the agent is free to propose anything.
    """

    approved: bool
    answered_by: Literal["human", "scripted", "auto"]
    words: str = ""


class Approver(Protocol):
    """Who answers a gated call, at the moment it is made."""

    async def answer(self, call: ToolCall) -> Verdict:
        """Put the call to whoever decides, and wait.

        Awaited inside a live turn, which is the whole point: the model's
        conversation stays open across the answer, so it can react to what you
        said and propose the next thing. The cost is that this pause is not
        durable the way a graph-level one is — if the process dies while you are
        deciding, the turn and its conversation go with it.
        """
        ...


class NoApprover(RuntimeError):
    """A gated call was made and nobody was wired up to answer it."""


class NobodyApproves:
    """The default approver. Raises, rather than deciding anything.

    Not an auto-refuser. A silent refusal would let a run finish having denied
    every proposal with nobody aware there was no human, which is the same class
    of failure as a silent approval and only differs in which direction it is
    wrong. Being the default, it means nobody configured an approver — a wiring
    mistake, so it is loud.
    """

    async def answer(self, call: ToolCall) -> Verdict:
        raise NoApprover(
            f"{call.name} is gated and no approver is configured — set one on the "
            f"control context"
        )


class CallGate:
    """Everything consulted before a tool runs, in order, behind one callback.

    The budget first, then you. That order is deliberate: a call the pool cannot
    afford is refused without anyone being asked about it, so you are not
    interrupted to answer for a call that was never going to run. With a gated
    call priced at zero — the placeholder — charging before asking costs nothing
    either way; if bookkeeping is ever priced for real, this is the line to
    revisit.
    """

    def __init__(
        self,
        *,
        meter: "Meter",
        approver: Approver,
        middleware: "tuple[ToolMiddleware, ...]" = (),
    ) -> None:
        self.meter = meter
        self.approver = approver
        #: The meter is always in the chain and always outermost — nothing else
        #: should get a say about a call that cannot be paid for.
        self.chain: tuple[ToolMiddleware, ...] = (meter,) + middleware
        #: One per gated call, in order.
        self.verdicts: list[tuple[ToolCall, Verdict]] = []

    async def can_use_tool(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        context: "ToolPermissionContext",
    ) -> "PermissionResult":
        """The SDK-facing callback. Price it, then ask.

        ``StructuredOutput`` never arrives here, so it is never priced and never
        gated — see :data:`STRUCTURED_OUTPUT_TOOL`. The guard exists anyway,
        because a measured absence is a fact about one SDK version and a silent
        change would put the model's own bookkeeping in front of you for
        approval.
        """
        from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

        if tool_name == STRUCTURED_OUTPUT_TOOL:
            return PermissionResultAllow()

        call = self.meter.describe(tool_name, tool_input, context)

        refusal = apply_middleware(self.chain, call)
        if refusal:
            return PermissionResultDeny(message=refusal)

        if not gated(call.name):
            return PermissionResultAllow()

        verdict = await self.approver.answer(call)
        self.verdicts.append((call, verdict))
        if not verdict.approved:
            return PermissionResultDeny(message=refused_by_user(verdict))
        # ⚠️ Words on an *approval* have nowhere to ride back on: the SDK's allow
        # carries no message. Getting them in front of the model is stage 2's
        # problem, on the tool-result path, and they are on the record either way.
        return PermissionResultAllow()


def refused_by_user(verdict: Verdict) -> str:
    """What the model is shown when you say no.

    Marked as coming from you, not from the machinery. A refusal the model reads
    as a system limit is one it will try to route around; a refusal it reads as
    the user speaking is one it can answer.
    """
    if not verdict.words:
        return "REFUSED BY THE USER. No reason was given."
    return f"REFUSED BY THE USER. Their words, verbatim: {verdict.words}"


def apply_middleware(
    chain: "tuple[ToolMiddleware, ...]", call: ToolCall
) -> str | None:
    """Ask every middleware, outermost first. The first refusal wins.

    Short-circuits, so a call refused for budget is never also asked about by
    whatever sits inside the meter — there is nothing to ask, the call is not
    happening.
    """
    for layer in chain:
        refusal = layer.before(call)
        if refusal:
            return refusal
    return None


def apply_after(
    chain: "tuple[ToolMiddleware, ...]", call: ToolCall, outcome: ToolOutcome
) -> ToolOutcome:
    """Unwind the chain, innermost first, each seeing what the last produced."""
    for layer in reversed(chain):
        outcome = layer.after(call, outcome)
    return outcome


class CallRouter(Protocol):
    """Attributes a concrete call to a pool and a price class."""

    def __call__(
        self, tool_name: str, tool_input: dict[str, Any], default_pool: str
    ) -> tuple[str, str]: ...


#: Every call that changes the store rather than going to look at something.
ALTERATIONS: frozenset[str] = frozenset(UNGATED | GATED)


def route_call(
    tool_name: str, tool_input: dict[str, Any], default_pool: str
) -> tuple[str, str]:
    """Which pool pays, and which price class applies.

    **Both halves are now answerable, and neither was when this was written.**

    The pool is ``default_pool``, always. This used to read a required
    ``for_assumption`` argument off the call, because one turn held one cap per
    reading and every priced call had to say which it served — the hardest thing
    this boundary had to do, flagged twice as a blocker. One reading per turn
    dissolved it: exactly one pool is open, so there is nothing to attribute and
    nothing that can be misattributed.

    The price class is the tool's own name, because the evidence tools are
    *named after their price classes* — ``read``, ``survey``, ``webfetch`` are
    the classes you gave, and naming the tools after them was the fix for prompts
    that quoted prices for tools that did not exist. An alteration is not
    evidence gathering and is priced as bookkeeping instead, on the one
    placeholder field for it.

    ⚠️ The identity holds only while every evidence tool *is* a price class. The
    moment there is a ``grep`` that costs what a survey costs, this needs a real
    mapping — and an unknown class charges the most expensive rate rather than
    nothing, which is the right direction to fail in.
    """
    if tool_name in ALTERATIONS:
        return default_pool, GRAPH_WRITE_CLASS
    return default_pool, tool_name


# ---------------------------------------------------------------------------
# The wire schema — a pydantic model's path to a CLI the model can satisfy
# ---------------------------------------------------------------------------


def to_wire_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """``model_json_schema()``, repaired for the CLI's validator.

    ⚠️ **Stage 2** — the reference implementation exists and is measured:
    ``scripts/spikes/spike_04_structured_output.py`` part C, about sixty lines.
    Porting it is mechanical; the architecture point is only that this function
    is *here*, on the boundary, and that the ledger keeps the untransformed
    pydantic type either way.

    Eight of eleven pydantic constructs pass untouched. Three need repair,
    because the CLI validates with Ajv 8 in strict mode against the draft-07
    vocabulary and ships the schema as a *tool's* ``input_schema``:

    1. **Strip ``discriminator``**, keep the ``oneOf`` beside it. Pydantic emits
       ``oneOf`` for a tagged union, and the keyword is a parsing hint — pydantic
       still applies the discriminated validator on the way back in.
    2. **Expand ``prefixItems``** into ``items`` plus ``minItems``/``maxItems``.
       A 2020-12 keyword; draft-07 does not know it. Positional typing is
       genuinely lost, so prefer keeping tuples out of wire schemas — the rule
       exists so the failure is a downgrade rather than a crash.
    3. **Rewrite a bare ``$ref`` root** into the referenced object, keeping
       ``$defs``. Recursion is fine; the bare root is not, because
       ``tools.0.custom.input_schema.type`` is required.
    """
    raise NotImplementedError("port spike_04_structured_output.py part C — stage 2")


def validate_payload(schema: type[BaseModel], structured_output: Any) -> BaseModel:
    """Validate the reply against the **untransformed** model.

    The property that matters: the transform changes the wire schema, never the
    type the ledger keeps.
    """
    return schema.model_validate(structured_output)


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------


def build_options(request: StageRequest, *, model: str, gate: CallGate, mcp_servers: Any) -> Any:
    """Assemble ``ClaudeAgentOptions`` for one stage turn.

    Every field set here is load-bearing and the reason is on the line. The
    import is local for the same reason `session/model.py` does it: the module
    should be importable, and testable, without the SDK present.
    """
    from claude_agent_sdk import ClaudeAgentOptions

    return ClaudeAgentOptions(
        model=model,
        # An allow-list. Deny-listing leaked under test, so there is no built-in
        # surface at all and every tool is in-graph.
        tools=[],
        # Nothing auto-approved, so the gate is consulted for every call. An
        # entry here allowing a whole tool would shadow it — including the
        # authority-bearing ones, which would approve them with nobody asked.
        allowed_tools=[],
        # NOT bypassPermissions — that approves before the gate is consulted.
        permission_mode="default",
        system_prompt=request.system,
        # The only structured-output mechanism the Claude Code surface has.
        # There is no tool_choice forcing and no response_format.
        output_format={"type": "json_schema", "schema": to_wire_schema(request.payload_schema)},
        # The budget and the approval, behind one callback.
        can_use_tool=gate.can_use_tool,
        mcp_servers=mcp_servers,
        env=dict(SUBSCRIPTION_ENV),
    )
