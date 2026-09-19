"""Drives the compiled cycle for one session's thread.

Every user action on the graph is one run: ``/graph <query>`` sets ``prompt``
and ``advance`` and enters at the top; plain text while the pointer is at
synthesis is one exchange. The run streams node updates, so the shell can say
which frame just finished and redraw the graph as it stands, and an interrupt
leaves the thread at its last committed checkpoint.

The thread state is the working set; the graph is the project's op log, read
through the context's store. Every snapshot the driver emits is this thread's
position drawn over the whole shared graph.
"""

from __future__ import annotations

from typing import Any

from .config import Budgets
from .graph import ControlContext, GraphState, compile_cycle
from .graph import budget, package, thought
from .graph.store import Ledger
from .harness.events import EventSink, Notice, StageFinished, StateSnapshot
from .harness.protocol import FrameInterrupted, HarnessUnavailable

FRAMES = ("orientate", "antithesis", "synthesis")


def pools_of(state: GraphState, ledger: Ledger, budgets: Budgets) -> tuple[tuple[str, int, int], ...]:
    """(pool, spent, cap) for this cycle's pools, in frame order."""
    if state.cycle == 0:
        return ()
    n = len(ledger.assumptions_of(state.cycle))
    rows: list[tuple[str, int, int]] = [
        (budget.orientation_pool(state.cycle), 0, budget.orientation_budget(budgets)),
    ]
    rows.append((budget.antithesis_pool(state.cycle), 0, budget.antithesis_budget(n, budgets)))
    rows.append((budget.synthesis_pool(state.cycle), 0, budgets.synthesis_points))
    return tuple((pool, budget.spent_from(ledger.spend, pool), cap) for pool, _, cap in rows)


def snapshot(state: GraphState, ledger: Ledger, view: Any, budgets: Budgets) -> StateSnapshot:
    """The thread's position over the project's whole graph."""
    return StateSnapshot(
        stage=state.stage,
        cycle=state.cycle,
        question=state.question,
        outline=thought.outline(view).lines,
        nodes=node_rows(view),
        pools=pools_of(state, ledger, budgets),
        conversation=state.conversation,
    )


def node_rows(view: Any) -> tuple[tuple[str, str, str, str, str], ...]:
    """(id, kind, role, status, text) for every live node — the panel's browser."""
    rows = []
    for nid in thought.live_nodes(view):
        a = view.nodes[nid]
        rows.append((nid, a["kind"], a.get("role", ""), a.get("status", ""), " ".join(str(a.get("text", "")).split())[:120]))
    return tuple(rows)


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

    def ledger(self) -> Ledger:
        return self.ctx.store.ledger()

    def snapshot(self, state: GraphState) -> StateSnapshot:
        return snapshot(state, self.ledger(), self.ctx.store.view(), self.ctx.budgets)

    async def pending(self) -> tuple[str, ...]:
        """The frames a stopped run still owes — non-empty after an interrupt."""
        snap = await self.graph.aget_state(self.config)
        return tuple(snap.next or ())

    async def start_cycle(self, query: str) -> GraphState | None:
        return await self._run({"prompt": query, "advance": True})

    async def resume(self) -> GraphState | None:
        """Carry on from the last committed frame, with the numbers as they are
        now: the context is handed in per run, so a changed budget or price
        applies from the resumed frame on."""
        return await self._run(None)

    async def exchange(self, text: str) -> GraphState | None:
        state = await self.state()
        if state is None or state.stage != "synthesis":
            self.sink.emit(Notice(text="no conversation is open; start a cycle with /graph <query>", level="warning"))
            return state
        return await self._run({"prompt": text, "advance": False})

    async def _run(self, update: dict[str, Any] | None) -> GraphState | None:
        try:
            async for chunk in self.graph.astream(update, self.config, context=self.ctx, stream_mode="updates"):
                for node, delta in chunk.items():
                    if node in FRAMES:
                        current = await self.state()
                        if current is not None:
                            self.sink.emit(StageFinished(stage=node, cycle=current.cycle, summary=_summary(node, current, self.ledger())))
                            self.sink.emit(self.snapshot(current))
        except FrameInterrupted:
            self.sink.emit(Notice(text="interrupted — the graph stands at its last completed frame", level="warning"))
        except HarnessUnavailable as exc:
            self.sink.emit(Notice(text=str(exc), level="error"))
        return await self.state()

    async def seed(self, values: dict[str, Any], as_node: str) -> None:
        """Write a whole state into this (new) thread — how a fork starts."""
        await self.graph.aupdate_state(self.config, values, as_node=as_node)

    def package_text(self, state: GraphState) -> str:
        """What the next cycle would open with, from where this thread stands."""
        return package.render(self.ledger(), self.ctx.store.view(), cycle=state.cycle, hops=self.ctx.budgets.package_hops)


def _summary(node: str, state: GraphState, ledger: Ledger) -> str:
    """What the frame just left on the graph, counted from the log."""
    cycle = state.cycle
    if node == "orientate":
        kept = len(ledger.findings_on(thought.question_id(cycle)))
        spent = budget.spent_from(ledger.spend, budget.orientation_pool(cycle))
        return f"{kept} finding(s), {len(ledger.assumptions_of(cycle))} assumption(s), {spent} points spent"
    if node == "antithesis":
        rivals = ledger.antitheses_of(cycle)
        kept = sum(len(ledger.findings_on(r.id)) for r in rivals)
        return f"{len(rivals)} rival(s), {kept} finding(s)"
    if node == "synthesis":
        return f"{sum(1 for w in ledger.proposed.values() if w.cycle == cycle)} proposal(s) this cycle"
    return ""
