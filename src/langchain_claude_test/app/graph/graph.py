"""The control graph: four frames, one state, and a pointer the user controls.

**The entry is conditional, and that is the cycle pointer.** Every message the
user sends is its own run. While the pointer reads ``synthesis`` the run
re-enters the conversation; ``/graph`` sets ``advance`` and the next run enters
at the top with the whole of the state carried.

**Nothing pauses.** No ``interrupt()`` anywhere: approval is answered inside
the live turn by the harness, so the model's conversation stays open across
the answer. Every exchange is a complete run that commits and ends, so the
conversation is checkpointed message by message and therefore forkable.

**Routing lives in the edge list**, never in a ``Command(goto=)``: a command
adds a route without removing the wired one, so a node with both runs both.
"""

from __future__ import annotations

import ast
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Literal

from langgraph.graph import END, START, StateGraph

from .context import ControlContext
from .nodes import antithesis, assume, orientate, synthesis
from .state import RECORD_TYPES, GraphState, unlisted_record_types
from .surface import STAGES

ORIENTATE = orientate.NAME
ASSUME = assume.NAME
ANTITHESIS = antithesis.NAME
SYNTHESIS = synthesis.NAME


def entry(state: GraphState) -> Literal["orientate", "synthesis"]:
    """The cycle pointer. The whole of the user's control over the loop."""
    if state.stage == SYNTHESIS and not state.advance:
        return SYNTHESIS
    return ORIENTATE


def build() -> StateGraph:
    builder: StateGraph = StateGraph(GraphState, context_schema=ControlContext)
    builder.add_node(ORIENTATE, orientate.orientate)
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

    Without it LangGraph warns once per unregistered type and, under strict
    mode, refuses to load the checkpoint at all.
    """
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    return JsonPlusSerializer(allowed_msgpack_modules=RECORD_TYPES)


def compile_cycle(checkpointer=None):
    """Compile. ``None`` is allowed only so the topology can be rendered."""
    return build().compile(checkpointer=checkpointer)


@asynccontextmanager
async def sqlite_checkpointer(path: Path) -> AsyncIterator:
    """The durable checkpointer, with this package's serialiser."""
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    async with AsyncSqliteSaver.from_conn_string(str(path)) as saver:
        saver.serde = serializer()
        yield saver


def _calls_interrupt(module) -> bool:
    tree = ast.parse(Path(module.__file__).read_text())
    return any(
        isinstance(n, ast.Call) and getattr(n.func, "id", "") == "interrupt" for n in ast.walk(tree)
    )


def check_topology() -> dict[str, tuple[str, ...]]:
    """The structural invariants, as a callable. Empty is the only correct answer."""
    from .surface import STAGE_GRAPH_TOOLS

    problems: dict[str, tuple[str, ...]] = {}
    names = set(STAGES)

    pausing = tuple(sorted(m.NAME for m in (orientate, assume, antithesis, synthesis) if _calls_interrupt(m)))
    if pausing:
        problems["frames that pause"] = pausing

    mismatch = names ^ set(STAGE_GRAPH_TOOLS)
    if mismatch:
        problems["frames missing from the tool table, or the other way round"] = tuple(sorted(mismatch))

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
    """The topology as mermaid, drawn from the compiled graph itself."""
    drawn = compile_cycle().get_graph().draw_mermaid()
    if not inner:
        return drawn
    return drawn + "\n%% inside " + ASSUME + "\n" + assume.subgraph().get_graph().draw_mermaid()
