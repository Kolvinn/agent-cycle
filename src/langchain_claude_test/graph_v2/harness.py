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
from typing import TYPE_CHECKING, Any, Mapping, Protocol

from pydantic import BaseModel

from . import budget
from .state import SpendEntry, Stage
from .surface import GraphWrite

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
    #: The graph-writes this stage carries. Empty is legal, and is what
    #: stage ② uses.
    graph_writes: frozenset[GraphWrite] = frozenset()
    #: Pool name -> cap, and there may be several. The restriction is *per
    #: assumption* while all the readings' findings are registered in one turn,
    #: so a single turn has to debit several separate pools. That only works if
    #: every priced call names the assumption it serves — see :func:`route_call`.
    pools: Mapping[str, int] = field(default_factory=dict)
    #: Already-recorded spend, so the meter derives each balance rather than
    #: being handed one (the agent never sets its own values).
    prior_spend: tuple[SpendEntry, ...] = ()
    #: The pool a call that names no assumption draws from. Empty means such a
    #: call is refused outright, which is what a per-assumption stage wants.
    default_pool: str = ""
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
            f"{request.payload_schema.__name__} with {len(request.graph_writes)} graph "
            f"write(s) against pools {dict(request.pools)}"
        )


# ---------------------------------------------------------------------------
# The meter — where a call is priced and where a budget is enforced
# ---------------------------------------------------------------------------


class Meter:
    """Prices every call ``can_use_tool`` is consulted about, and no others.

    Availability is gated by stage, and this is the second of its two
    enforcements: the node chose *which*
    tools exist by which MCP server it opened, and this decides whether an
    individual call is affordable. Both are needed — availability without
    pricing lets one stage spend the whole cycle, pricing without availability
    lets it spend on the wrong things.

    **It routes before it prices.** A stage may hold several pools at once
    (a per-assumption restriction inside a single turn), so the
    first question about a call is not what it costs but whose budget it comes
    out of. A call that cannot be attributed is refused rather than charged to a
    default, because an unattributable call is how a per-assumption cap becomes
    a shared pool by accident.

    **It accumulates into itself, not into the state.** The node reads
    :attr:`entries` when the turn is over and returns them as a delta. If the
    node is later replayed the turn re-runs and a fresh meter recounts; nothing
    was written twice because nothing was written at all. That is the whole of
    the interrupt-replay rule, kept by construction.
    """

    def __init__(
        self,
        *,
        pools: Mapping[str, int],
        prices: Mapping[str, int],
        prior_spend: tuple[SpendEntry, ...] = (),
        default_pool: str = "",
        turn: int = 1,
        stage: Stage = "orient",
        graph_write_price: int = 0,
        route: "CallRouter | None" = None,
    ) -> None:
        self.pools = dict(pools)
        self.prices = prices
        self.default_pool = default_pool
        self.graph_write_price = graph_write_price
        self.turn = turn
        self.stage = stage
        self._prior = tuple(prior_spend)
        self._route = route or route_call
        #: Priced calls, in order. The node's delta.
        self.entries: list[SpendEntry] = []
        #: Calls refused, with the reason. Exhaustion is an outcome, not an
        #: error: it ends the stage (exhaustion forces a reply).
        self.refused: list[str] = []

    def remaining(self, pool: str) -> int:
        """What is left in one pool, derived from prior plus this turn."""
        return budget.remaining(
            list(self._prior) + self.entries, pool, self.pools.get(pool, 0)
        )

    async def can_use_tool(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        context: "ToolPermissionContext",
    ) -> "PermissionResult":
        """The gate. Attribute it, price it, then allow or refuse.

        ``StructuredOutput`` never arrives here, so it is never priced — see
        :data:`STRUCTURED_OUTPUT_TOOL`. The guard below exists anyway, because a
        measured absence is a fact about one SDK version, and a silent change
        would bill the ledger for its own bookkeeping.
        """
        from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

        if tool_name == STRUCTURED_OUTPUT_TOOL:
            return PermissionResultAllow()

        pool, call_class = self._route(tool_name, tool_input, self.default_pool)

        if not pool or pool not in self.pools:
            self.refused.append(f"{tool_name}: unattributed")
            return PermissionResultDeny(
                message=(
                    "UNATTRIBUTED_CALL: name the assumption this call serves. "
                    "Every priced call is charged to one reading's budget."
                )
            )

        # A graph-write is bookkeeping, not evidence gathering. Whether "tool
        # usage registered to point values" was meant to cover it is unsettled,
        # so the price comes from one placeholder field rather than from a
        # literal scattered through the code.
        price = (
            self.graph_write_price
            if call_class == GRAPH_WRITE_CLASS
            else budget.price_of(call_class, self.prices)
        )

        left = self.remaining(pool)
        if price > left:
            self.refused.append(f"{tool_name}: {pool} exhausted")
            return PermissionResultDeny(
                message=(
                    f"BUDGET_EXHAUSTED: {call_class} costs {price} and {pool} has {left} "
                    f"left. Stop spending on this reading and report what you have."
                )
            )

        self.entries.append(
            SpendEntry(
                pool=pool,
                call=call_class,
                price=price,
                turn=self.turn,
                stage=self.stage,
                tool_call_id=getattr(context, "tool_use_id", "") or "",
            )
        )
        return PermissionResultAllow()


#: The price class used for in-graph writes, as opposed to evidence calls.
GRAPH_WRITE_CLASS = "graph_write"


class CallRouter(Protocol):
    """Attributes a concrete call to a pool and a price class."""

    def __call__(
        self, tool_name: str, tool_input: dict[str, Any], default_pool: str
    ) -> tuple[str, str]: ...


def route_call(
    tool_name: str, tool_input: dict[str, Any], default_pool: str
) -> tuple[str, str]:
    """Which pool pays, and which price class applies.

    ⚠️ **Built in the next stage.** Both halves wait on the same thing: the
    in-graph tool surface is not settled (`surface.py` says so in its own
    docstring), and the price classes named — survey, read, webfetch — were
    given without naming the tools that fall in them. Writing the mapping now
    would be inventing prices for tools that do not exist.

    The *shape* is the architectural claim and does not wait: attribution comes
    from the call's own arguments. Every priced tool in the in-graph surface
    takes a required ``for_assumption``, which is what lets one turn hold one
    cap per reading.
    """
    raise NotImplementedError("call routing is stage 2 — tool names and price classes unsettled")


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


def build_options(request: StageRequest, *, model: str, meter: Meter, mcp_servers: Any) -> Any:
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
        # Nothing auto-approved, so the meter is consulted for every call. An
        # entry here allowing a whole tool would shadow it.
        allowed_tools=[],
        # NOT bypassPermissions — that approves before the meter is consulted.
        permission_mode="default",
        system_prompt=request.system,
        # The only structured-output mechanism the Claude Code surface has.
        # There is no tool_choice forcing and no response_format.
        output_format={"type": "json_schema", "schema": to_wire_schema(request.payload_schema)},
        can_use_tool=meter.can_use_tool,
        mcp_servers=mcp_servers,
        env=dict(SUBSCRIPTION_ENV),
    )
