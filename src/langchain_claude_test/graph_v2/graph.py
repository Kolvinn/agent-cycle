"""The control graph: four frames, one state, and a pointer you control.

Each frame is a *stance* the model is put into, with its own prompt around it
and its own answer expected back. Anything that is not a reframing is not a
frame: it is a tool call made inside one, or arithmetic on the edge between two.

    ┌─► orientate ──► assume ──► antithesis ──► synthesis ──► (end of run)
    │                   │                           │
    │                   └─ while open readings {    └─ you are here until you
    │                        while budget { tools } }   say otherwise
    │                                                   │
    └───────────────── your advance command ────────────┘

**The entry is conditional, and that is the cycle pointer.** Every message you
send is its own run. While the pointer reads ``synthesis`` the run re-enters the
conversation; when you set ``advance`` it re-enters at the top with the whole of
the state carried. So going round is your command, not the model deciding it is
finished and not a budget running out.

**Nothing in this design pauses.** There is no ``interrupt()`` anywhere, and the
approval that used to need one is answered inside the live turn by the harness
instead. Two things follow. The model's conversation stays open across your
answer, so it can react to what you said rather than being restarted with it —
which is what makes the last stage a conversation at all. And every exchange is
a complete run that commits and ends, so the conversation is checkpointed
message by message and therefore forkable: you can go back three replies and
take it a different way.

**One state, and every node takes it whole.** Nodes are ``node(state: Cycle)``.
Each frame lives in its own module under ``nodes/``, self-contained: its prompt
container, the tools it carries and the pool it spends from all sit beside it.
This file holds only the topology, so reading the edge list is reading the flow.

There is no per-node projection. An earlier design filtered what a frame could
see through a declared sub-schema, and the guarantee was weaker than it looked:
a sub-schema naming a channel the state does not have silently receives an empty
default rather than failing. **What a frame must not read is a rule in its body,
stated where the reading happens.**

**The cycle boundary is a compaction.** Inside a cycle every frame continues one
conversation, so no prompt re-renders what the model already has. Across the
boundary the conversation is thrown away and the *graph* is injected in its
place, carrying the evidence that was registered onto its nodes and dropping the
tool output that was only scaffolding. That is the one place state becomes text,
and `package.py` is where it happens.

**Two kinds of call, and neither of them waits.** Evidence calls — read, survey,
webfetch — execute immediately and their output returns to the model inside the
turn, or it is not doing research. The authority-bearing calls execute
immediately too, once you have answered them, and you answer them at the moment
they are made. Nothing is gathered for later: an earlier shape queued them and
resolved them after the model had finished, which was a way around pausing
mid-turn, and the pause was the problem.

⚠️ **Skeleton.** The topology and the contracts are the architecture. The
harness that answers a frame's request is not built, and neither are the payload
models — see :data:`STAGE_WORK`.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Literal

from langgraph.graph import END, START, StateGraph

from .context import ControlContext
from .nodes import antithesis, assume, orientate, synthesis
from .state import RECORD_TYPES, Cycle, unlisted_record_types

ORIENTATE = orientate.NAME
ASSUME = assume.NAME
ANTITHESIS = antithesis.NAME
SYNTHESIS = synthesis.NAME

#: Every frame draws from a pool. The last one joined them when it gained
#: evidence calls: *"yes it should get evidence tools"*. A frame that can look
#: and has no pool has no restriction, which is the one thing this design is
#: about.
SPENDING = frozenset({ORIENTATE, ASSUME, ANTITHESIS, SYNTHESIS})


def entry(state: Cycle) -> Literal["orientate", "synthesis"]:
    """The cycle pointer. Which frame this run enters at.

    The whole of the control you have over the loop, in four lines. While the
    last frame is where the state was left, your messages go to it; your command
    sends the next one to the top instead, and everything the conversation built
    goes with it.

    Reads the pointer rather than a message count or a turn number, so it cannot
    drift out of step with where the state actually is.
    """
    if state.stage == SYNTHESIS and not state.advance:
        return SYNTHESIS
    return ORIENTATE


def build() -> StateGraph:
    """The uncompiled cycle. Four frames, one conditional entry, one exit.

    **The loop over readings is not in this file, and the loop over the
    conversation is not an edge at all.** Cycling over the readings is two edges
    inside the assume stage, because there are two loop conditions and they are
    different questions. Cycling the whole graph is you invoking it again, which
    is why the only thing here is where a run starts.

    Routing is by conditional edge, never by ``Command(goto=)``: a ``Command``
    adds a dynamic edge without removing the static one, so a node with both runs
    both destinations.

    Nothing is gated with ``interrupt_before`` and nothing calls ``interrupt()``.
    Approval happens at the call, inside the turn, where the model can hear the
    answer.
    """
    builder: StateGraph = StateGraph(Cycle, context_schema=ControlContext)

    builder.add_node(ORIENTATE, orientate.orientate)
    # One node from out here; two nodes and two loops on the inside. The inner
    # graph is *invoked by* this node rather than attached as one — a compiled
    # subgraph attached with ``add_node`` returns its whole state, so the parent
    # re-applies its reducers to everything already there and every accumulating
    # channel doubles. See :func:`nodes.assume.assume`.
    builder.add_node(ASSUME, assume.assume)
    builder.add_node(ANTITHESIS, antithesis.antithesis)
    builder.add_node(SYNTHESIS, synthesis.synthesis)

    builder.add_conditional_edges(START, entry, [ORIENTATE, SYNTHESIS])
    builder.add_edge(ORIENTATE, ASSUME)
    builder.add_edge(ASSUME, ANTITHESIS)
    builder.add_edge(ANTITHESIS, SYNTHESIS)
    builder.add_edge(SYNTHESIS, END)

    return builder


def serializer():
    """A serialiser admitting exactly this package's record types.

    Without it LangGraph warns once per unregistered type — *"this will be blocked
    in a future version"* — and under strict mode refuses to load the checkpoint
    at all. Measured both ways.
    """
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    return JsonPlusSerializer(allowed_msgpack_modules=RECORD_TYPES)


def compile_cycle(checkpointer=None):
    """Compile.

    A checkpointer is not optional in practice, and for a different reason than
    it used to be: nothing pauses any more, but every message is its own run, so
    without one the conversation has no memory of the message before it. ``None``
    is allowed only so the topology can be rendered without standing up storage.
    """
    return build().compile(checkpointer=checkpointer)


def _calls_interrupt(module) -> bool:
    """Whether a frame's module calls ``interrupt()`` anywhere."""
    tree = ast.parse(Path(module.__file__).read_text())
    return any(
        isinstance(n, ast.Call) and getattr(n.func, "id", "") == "interrupt"
        for n in ast.walk(tree)
    )


def check_topology() -> dict[str, tuple[str, ...]]:
    """The structural invariants, as a callable rather than a comment.

    Empty is the only correct answer.

    1. **No frame pauses.** This replaces the old rule that no frame both spent
       and paused, which is now vacuous because none of them pause: approval is
       answered at the call. The old rule existed because the body above a pause
       re-runs on resume while the update commits once, so a frame doing both
       would re-spend every time you answered. Every frame now spends, so if a
       pause ever came back the rule would be violated everywhere at once — which
       is why this checks for the pause rather than for the overlap.
    2. **Every frame in the tool table is a node, and every node is in it.**
    3. **The entry router names only real frames.**
    4. **Every record type is on the checkpoint allowlist.** One reachable from
       the state but unlisted checkpoints fine and fails to *load*.
    5. **Every node is reachable.**
    """
    from .surface import STAGE_TOOLS

    problems: dict[str, tuple[str, ...]] = {}
    names = {ORIENTATE, ASSUME, ANTITHESIS, SYNTHESIS}

    pausing = tuple(
        sorted(m.NAME for m in (orientate, assume, antithesis, synthesis) if _calls_interrupt(m))
    )
    if pausing:
        problems["frames that pause"] = pausing

    mismatch = names ^ set(STAGE_TOOLS)
    if mismatch:
        problems["frames missing from the tool table, or the other way round"] = tuple(
            sorted(mismatch)
        )

    routes = set(entry.__annotations__["return"].__args__) if hasattr(
        entry.__annotations__["return"], "__args__"
    ) else set(Literal[ORIENTATE, SYNTHESIS].__args__)
    unknown = routes - names
    if unknown:
        problems["entry router names a frame that does not exist"] = tuple(sorted(unknown))

    unlisted = unlisted_record_types()
    if unlisted:
        problems["record types missing from the checkpoint allowlist"] = unlisted

    drawn = compile_cycle().get_graph()
    reachable = {e.target for e in drawn.edges} | {START}
    orphans = (set(drawn.nodes) - {START, END, "__start__", "__end__"}) - reachable
    if orphans:
        problems["unreachable nodes"] = tuple(sorted(orphans))

    return problems


def render(*, inner: bool = False) -> str:
    """The topology as mermaid, drawn from the compiled graph itself.

    ``inner`` appends the assume stage's own two-node loop, which the outer view
    shows as a single box. It is drawn separately rather than through ``xray``,
    which only expands a subgraph *attached* as a node — and this one is invoked
    from inside its node instead, for the reason :func:`build` gives.
    """
    drawn = compile_cycle().get_graph().draw_mermaid()
    if not inner:
        return drawn
    return drawn + "\n%% inside " + ASSUME + "\n" + assume.subgraph().get_graph().draw_mermaid()


#: What is still unbuilt, listed where the code is rather than in a note
#: somewhere.
#:
#: **The harness.** Nothing opens a subprocess yet: :class:`~.harness.UnbuiltHarness`
#: refuses instead of pretending. Four things wait on it — routing a concrete
#: tool name to a price class, transforming a pydantic schema into one the CLI's
#: validator accepts, returning the records its calls created, and holding one
#: conversation open across frames *and across runs*, which is what every
#: ``continues=True`` rides on and is a harder ask than it was: the synthesis
#: conversation spans separate invocations of the graph.
#:
#: **The payload schemas.** Each frame declares the shape of the answer it
#: expects, in prose and with a body of ``...``. What they must contain is
#: settled; the models are not written.
#:
#: **Applying an approved alteration.** The store has no mutation layer, so an
#: approved ``compress`` or ``discard`` is recorded and not carried out — which
#: means the package grows rather than compacting. That is the wrong end of the
#: failure to be on, but it is the safe one.
STAGE_WORK = "see the module docstring — the harness is the next thing to build"
