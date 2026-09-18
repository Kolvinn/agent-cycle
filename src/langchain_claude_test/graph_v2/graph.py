"""The topology — five stages, three turns, one cycle.

The whole of the control design is in :func:`build`. Reading the edge list is
reading the flow, and a change to the flow is a change to the edge list rather
than to a runner's control statements. That is the difference the framework
buys: `session/runner.py` states its order in a docstring, and here the order
*is* the object.

**Turn boundaries are nodes, not separate graphs.** One graph per cycle, with
``turn_1_close``/``turn_2_close`` as ordinary nodes, for two reasons. The
checkpoint history is then a single sequence — which is what makes a fork at a
chosen point mean "the same run, an edited context" rather than "a different
run". And the state that crosses a boundary is an object a node *built*, which
is checkpointed evidence of what crossed, where a subgraph's input would be a
transient computation.

**Nothing is gated with ``interrupt_before``.** Every pause in this design is a
node calling ``interrupt()`` itself, because the pause carries a payload: which
call is being approved, and why. ``interrupt_before`` stops *before* a node and
so has nothing to say. It would collapse the difference between a user message
and a user approval of a tool call, turning the second back into "a pause at a
step" — and that difference is what the design is built on.

**Routing is by conditional edge, never by ``Command(goto=)``.** A ``Command``
adds a dynamic edge without removing the static one, so a node with both
executes both destinations. Keeping every branch in the edge list also keeps it
visible in :func:`render`, which is the point of having a topology at all.

Conditional-edge functions receive the runtime context — verified against
LangGraph 1.2.11 rather than assumed — so a router can read a cap it must not
be able to change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from langgraph.graph import END, START, StateGraph

from . import nodes
from .context import ControlContext
from .state import RECORD_TYPES, Cycle, unlisted_record_types
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

if TYPE_CHECKING:  # pragma: no cover
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
    from langgraph.graph.state import CompiledStateGraph

# Node names. Kept as constants because they appear in three places — the node
# registration, the edge list and the routers' return types — and a typo in the
# third is a run-time error rather than an import-time one.
REGISTER = "register"
EXTRACT = "extract"
APPROVE_FACTS = "approve_facts"
ORIENT = "orient"
FORM = "form"
FUND = "fund"
INVESTIGATE = "investigate"
TURN_1_CLOSE = "turn_1_close"
ANTITHESIS = "antithesis"
COUNTER = "counter"
TURN_2_CLOSE = "turn_2_close"
PRESENT = "present"
AWAIT_REPLY = "await_reply"
READ_REPLY = "read_reply"
APPROVE_WRITES = "approve_writes"
APPLY = "apply"
ESCALATE = "escalate"

#: Nodes that pause for a human. Each one calls ``interrupt()`` with the call it
#: wants approved. None of them spends, and none of them writes above the wait —
#: that separation is the interrupt-replay rule, enforced by which nodes exist.
PAUSING = frozenset({APPROVE_FACTS, AWAIT_REPLY, APPROVE_WRITES, ESCALATE})

#: Nodes that open a priced harness turn. Disjoint from :data:`PAUSING`, and the
#: disjointness is the invariant — see :func:`check_topology`.
PRICED = frozenset({EXTRACT, ORIENT, INVESTIGATE, COUNTER, PRESENT, READ_REPLY})


def build() -> StateGraph[Cycle, ControlContext, Cycle, Cycle]:
    """The uncompiled cycle. Separate from :func:`compile_cycle` so a caller can
    inspect or extend the topology before committing to a checkpointer."""
    builder: StateGraph = StateGraph(Cycle, context_schema=ControlContext)

    # --- turn 1 · stage ① — prompt + fact extraction ----------------------
    builder.add_node(REGISTER, nodes.register_prompt, input_schema=PromptView)
    builder.add_node(EXTRACT, nodes.extract_facts, input_schema=ExtractView)
    builder.add_node(APPROVE_FACTS, nodes.approve_facts, input_schema=ApprovalView)

    # --- turn 1 · stage ② — budget context pass ---------------------------
    builder.add_node(ORIENT, nodes.orient, input_schema=OrientView)

    # --- turn 1 · stage ③ — assumption pass -------------------------------
    builder.add_node(FORM, nodes.form_assumptions, input_schema=FormView)
    # No view: funding is the graph setting values, and it needs the whole
    # assumption list to set them. It reads nothing the agent authored beyond
    # the ids.
    builder.add_node(FUND, nodes.fund_assumptions)
    builder.add_node(INVESTIGATE, nodes.investigate, input_schema=InvestigateView)

    # --- the turn boundary ------------------------------------------------
    # Deliberately no view. Assembling a projection is the one job that
    # requires seeing what is being left out.
    builder.add_node(TURN_1_CLOSE, nodes.turn_1_close)

    # --- turn 2 · stage ④ — antithesis pass · internal --------------------
    # The two views below are where the design's central claim stops being an
    # instruction: neither names `thesis_reasoning` or `findings`, so the
    # affirming frame is not an attribute of anything these nodes hold.
    builder.add_node(ANTITHESIS, nodes.antithesis, input_schema=AntithesisView)
    builder.add_node(COUNTER, nodes.counter_investigate, input_schema=CounterView)
    builder.add_node(TURN_2_CLOSE, nodes.turn_2_close)

    # --- turn 3 · stage ⑤ — present + reconcile · exploration required ----
    builder.add_node(PRESENT, nodes.present, input_schema=PresentView)
    builder.add_node(AWAIT_REPLY, nodes.await_reply)
    builder.add_node(READ_REPLY, nodes.read_reply, input_schema=ReplyView)
    builder.add_node(APPROVE_WRITES, nodes.approve_writes, input_schema=WriteApprovalView)
    builder.add_node(APPLY, nodes.apply_writes)

    builder.add_node(ESCALATE, nodes.escalate)

    # --- edges ------------------------------------------------------------
    builder.add_edge(START, REGISTER)
    builder.add_edge(REGISTER, EXTRACT)
    builder.add_edge(EXTRACT, APPROVE_FACTS)
    builder.add_edge(APPROVE_FACTS, ORIENT)

    # Stage ② loops on itself: another orientation turn while the agent cannot
    # name the readings and the pool still has points. Two exits, and both are
    # needed — the agent being ready is the intended one, the pool running dry
    # is what keeps it finite when it never is.
    builder.add_conditional_edges(ORIENT, nodes.orient_ready, [ORIENT, FORM])

    # Admissibility is enforced at formation: *"we want assumptions to be
    # avenues available for information to stick. There is no point in assuming
    # something unprovable."* A reading nothing could land on is re-authored,
    # not funded — and so is a set that exceeds the graph-owned ceiling on how
    # many readings may exist.
    builder.add_conditional_edges(FORM, nodes.admissible_route, [FORM, FUND, ESCALATE])

    builder.add_edge(FUND, INVESTIGATE)
    builder.add_edge(INVESTIGATE, TURN_1_CLOSE)
    builder.add_edge(TURN_1_CLOSE, ANTITHESIS)

    # "There is nothing to attack" is not a permitted output, so an empty or
    # unmovable antithesis routes back to authoring.
    builder.add_conditional_edges(
        ANTITHESIS, nodes.antithesis_route, [ANTITHESIS, COUNTER, ESCALATE]
    )

    builder.add_edge(COUNTER, TURN_2_CLOSE)
    builder.add_edge(TURN_2_CLOSE, PRESENT)
    builder.add_edge(PRESENT, AWAIT_REPLY)
    builder.add_edge(AWAIT_REPLY, READ_REPLY)
    builder.add_edge(READ_REPLY, APPROVE_WRITES)
    builder.add_edge(APPROVE_WRITES, APPLY)

    # The next cycle re-enters at REGISTER, never at START — START is entry-only.
    # Whether it re-enters at all is undecided: where a new user message enters
    # the flow is unplaced, so `next_cycle` currently ends.
    builder.add_conditional_edges(APPLY, nodes.next_cycle, [REGISTER, END])

    # Where an escalation rejoins the flow is undecided. Ending is the only
    # answer that decides nothing.
    builder.add_edge(ESCALATE, END)

    return builder


def serializer() -> "JsonPlusSerializer":
    """A serialiser that admits exactly this package's record types.

    Pass it to whichever checkpointer a run uses::

        InMemorySaver(serde=serializer())

    Without it LangGraph warns once per unregistered type — *"This will be
    blocked in a future version"* — and under ``LANGGRAPH_STRICT_MSGPACK=true``
    it refuses to load the checkpoint at all. Measured both ways: the warnings
    fire for :data:`~.state.RECORD_TYPES`, and a strict-mode round-trip of a
    populated :class:`~.state.Cycle` succeeds once they are allow-listed.

    This is the concrete form of the open item framework-fit §10 records as
    unverified. What is now measured is the *serialisation*; what remains
    unverified is a durable store behind it — this design pauses for a human
    between turns, so it will need one that outlives the process.
    """
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    return JsonPlusSerializer(allowed_msgpack_modules=RECORD_TYPES)


def compile_cycle(checkpointer: "BaseCheckpointSaver | None" = None) -> "CompiledStateGraph":
    """Compile the cycle.

    A checkpointer is not optional in practice: every pause in this design is an
    ``interrupt()``, and an interrupt without a checkpointer cannot resume. The
    parameter allows ``None`` only so the topology can be compiled for rendering
    and inspection without standing up storage — and a caller that passes one
    should build it with :func:`serializer`.
    """
    return build().compile(checkpointer=checkpointer)


def check_topology() -> dict[str, tuple[str, ...]]:
    """The structural invariants, as a callable rather than a comment.

    Empty is the only correct answer. A test should call this; it lives here so
    the invariants travel with the topology they constrain.

    1. **No node both spends and pauses.** The body above an ``interrupt()``
       re-runs on resume while the state update commits once, so a node that
       did both would re-spend on every resume.
    2. **Every view names only real state fields.** LangGraph fills a view from
       the state's channels by name, so a stray field is a run-time error.
    3. **Every record type is on the checkpoint allowlist.** A record that is
       reachable from the state but unlisted checkpoints fine and fails to
       *load*, which is the worst possible moment to discover it.
    4. **Every node is reachable and every edge target exists.** Compiling
       catches the second; the first needs asking.
    """
    from .views import fields_not_in_cycle

    problems: dict[str, tuple[str, ...]] = {}

    both = PRICED & PAUSING
    if both:
        problems["nodes that both spend and pause"] = tuple(sorted(both))

    unlisted = unlisted_record_types()
    if unlisted:
        problems["record types missing from the checkpoint allowlist"] = unlisted

    bad_views = fields_not_in_cycle()
    if bad_views:
        problems["views naming unknown state fields"] = tuple(
            f"{view}: {', '.join(fields)}" for view, fields in sorted(bad_views.items())
        )

    compiled = compile_cycle()
    drawn = compiled.get_graph()
    reachable = {e.target for e in drawn.edges} | {START}
    declared = set(drawn.nodes) - {START, END, "__start__", "__end__"}
    orphans = declared - reachable
    if orphans:
        problems["unreachable nodes"] = tuple(sorted(orphans))

    return problems


def render() -> str:
    """The topology as mermaid, drawn from the compiled graph itself.

    Not a hand-maintained diagram: if the edge list changes, this changes with
    it. Used to keep `diagrams/` honest rather than to replace the design
    diagrams, which say things a topology cannot.
    """
    return compile_cycle().get_graph().draw_mermaid()
