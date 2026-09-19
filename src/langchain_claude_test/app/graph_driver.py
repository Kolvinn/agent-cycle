"""Drives the compiled cycle for one session's thread.

Every user action on the graph is one run: ``/graph <query>`` sets ``prompt``
and ``advance`` and enters at the top; plain text while the pointer is at
synthesis is one exchange. The run streams node updates, so the shell can say
which frame just finished and redraw the graph as it stands, and an interrupt
leaves the thread at its last committed checkpoint.
"""

from __future__ import annotations

from typing import Any

from .config import Budgets
from .graph import ControlContext, GraphState, compile_cycle
from .graph import budget, package, thought
from .harness.events import EventSink, Notice, StageFinished, StageStarted, StateSnapshot
from .harness.protocol import FrameInterrupted, HarnessUnavailable

FRAMES = ("orientate", "assume", "antithesis", "synthesis")


def pools_of(state: GraphState, budgets: Budgets) -> tuple[tuple[str, int, int], ...]:
    """(pool, spent, cap) for this cycle's pools, in frame order."""
    if state.cycle == 0:
        return ()
    n = len(state.current_assumptions())
    rows: list[tuple[str, int, int]] = [
        (budget.orientation_pool(state.cycle), 0, budgets.orientation_points),
    ]
    for a in state.current_assumptions():
        rows.append((budget.assumption_pool(a.id), 0, state.allocations.get(a.id, 0)))
    rows.append((budget.antithesis_pool(state.cycle), 0, budget.antithesis_budget(n, budgets)))
    rows.append((budget.synthesis_pool(state.cycle), 0, budgets.synthesis_points))
    return tuple((pool, budget.spent_from(state.spend, pool), cap) for pool, _, cap in rows)


def snapshot(state: GraphState, budgets: Budgets) -> StateSnapshot:
    return StateSnapshot(
        stage=state.stage,
        cycle=state.cycle,
        question=state.question,
        outline=thought.outline(state).lines,
        pools=pools_of(state, budgets),
        conversation=state.conversation,
    )


class GraphDriver:
    def __init__(self, *, thread_id: str, checkpointer: Any, ctx: ControlContext, sink: EventSink) -> None:
        self.thread_id = thread_id
        self.ctx = ctx
        self.sink = sink
        self.graph = compile_cycle(checkpointer)

    @property
    def config(self) -> dict[str, Any]:
        return {"configurable": {"thread_id": self.thread_id}}

    async def state(self) -> GraphState | None:
        snap = await self.graph.aget_state(self.config)
        if not snap.values:
            return None
        return GraphState.model_validate(snap.values)

    async def start_cycle(self, query: str) -> GraphState | None:
        return await self._run({"prompt": query, "advance": True})

    async def exchange(self, text: str) -> GraphState | None:
        state = await self.state()
        if state is None or state.stage != "synthesis":
            self.sink.emit(Notice(text="no conversation is open; start a cycle with /graph <query>", level="warning"))
            return state
        return await self._run({"prompt": text, "advance": False})

    async def _run(self, update: dict[str, Any]) -> GraphState | None:
        try:
            async for chunk in self.graph.astream(update, self.config, context=self.ctx, stream_mode="updates"):
                for node, delta in chunk.items():
                    if node in FRAMES:
                        current = await self.state()
                        if current is not None:
                            self.sink.emit(StageFinished(stage=node, cycle=current.cycle, summary=_summary(node, delta)))
                            self.sink.emit(snapshot(current, self.ctx.budgets))
        except FrameInterrupted:
            self.sink.emit(Notice(text="interrupted — the graph stands at its last completed frame", level="warning"))
        except HarnessUnavailable as exc:
            self.sink.emit(Notice(text=str(exc), level="error"))
        return await self.state()

    async def seed(self, values: dict[str, Any], as_node: str) -> None:
        """Write a whole state into this (new) thread — how a fork starts."""
        await self.graph.aupdate_state(self.config, values, as_node=as_node)

    async def package_text(self) -> str:
        state = await self.state()
        return package.render(state) if state is not None else ""


def _summary(node: str, delta: dict[str, Any] | None) -> str:
    if not delta:
        return ""
    if node == "orientate":
        return f"{len(delta.get('assumptions', []))} reading(s) named"
    if node == "assume":
        return f"{len(delta.get('findings', []))} finding(s), {sum(e.price for e in delta.get('spend', []))} points spent"
    if node == "antithesis":
        return f"{len(delta.get('antitheses', []))} rival(s), {len(delta.get('findings', []))} finding(s)"
    if node == "synthesis":
        return f"{len(delta.get('proposed', []))} proposal(s)"
    return ""
