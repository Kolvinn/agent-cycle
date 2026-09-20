"""The side panel — a graph browser — and the status line.

The panel draws the last snapshot three ways: the outline (questions, facts,
claims and what hangs off them), by kind, or by status. Selecting a node
asks the runner for it in full (``/show node <id>``), so the transcript shows
its edges, evidence and history.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from rich.text import Text
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Static, Tree

from ..harness import events as ev
from ..session import SessionRecord

VIEWS: tuple[str, ...] = ("outline", "kind", "status")


class GraphPanel(Vertical):
    DEFAULT_CSS = """
    GraphPanel { width: 44; border-left: solid $panel; padding: 0 1; }
    GraphPanel Tree { height: 1fr; }
    GraphPanel .pools { height: auto; color: $text-muted; }
    """

    class NodePicked(Message):
        """The user selected a node in the browser."""

        def __init__(self, node_id: str) -> None:
            super().__init__()
            self.node_id = node_id

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.graph_tree: Tree[str] = Tree("graph")
        self.pools = Static("", classes="pools")
        self.view = VIEWS[0]
        self.snapshot: ev.StateSnapshot | None = None

    def compose(self):
        yield self.graph_tree
        yield self.pools

    # --- what to draw ------------------------------------------------------------

    def set_view(self, view: str) -> bool:
        """Switch the browser's view. False if the name is not one."""
        if view not in VIEWS:
            return False
        self.view = view
        self._draw()
        return True

    def cycle_view(self) -> str:
        self.set_view(VIEWS[(VIEWS.index(self.view) + 1) % len(VIEWS)])
        return self.view

    def apply(self, snap: ev.StateSnapshot) -> None:
        self.snapshot = snap
        self._draw()
        self.pools.update(
            Text("\n".join(f"{pool}: {spent}/{cap}" for pool, spent, cap in snap.pools) or "no pools yet")
        )

    def pick(self, node_id: str) -> None:
        """Select a node as the user would — for the shell and for tests."""
        self.post_message(self.NodePicked(node_id))

    # --- drawing ---------------------------------------------------------------------

    def _draw(self) -> None:
        tree = self.graph_tree
        tree.clear()
        snap = self.snapshot
        if snap is None:
            tree.root.set_label("graph")
            return
        tree.root.set_label(f"cycle {snap.cycle} · {snap.stage} · by {self.view} (ctrl+b)")
        if self.view == "outline":
            self._draw_outline(snap)
        elif self.view == "kind":
            self._draw_grouped(snap, key=lambda row: f"{row[1]}/{row[2]}" if row[2] else row[1])
        else:
            self._draw_grouped(snap, key=lambda row: row[3] or "the user's")
        tree.root.expand_all()

    def _draw_outline(self, snap: ev.StateSnapshot) -> None:
        tree = self.graph_tree
        ids = {row[0] for row in snap.nodes}
        parents: dict[int, object] = {0: tree.root}
        for depth, node_id, label in snap.outline:
            parent = parents.get(depth, tree.root)
            node = parent.add(label, data=node_id if node_id in ids else None, expand=True)
            parents[depth + 1] = node

    def _draw_grouped(self, snap: ev.StateSnapshot, key) -> None:
        groups: dict[str, list[tuple[str, str, str, str, str]]] = defaultdict(list)
        for row in snap.nodes:
            groups[key(row)].append(row)
        for name in sorted(groups):
            rows = groups[name]
            branch = self.graph_tree.root.add(f"{name} ({len(rows)})", expand=True)
            for nid, _, _, status, text in rows:
                mark = f" [{status}]" if status and status != "provisional" else ""
                branch.add_leaf(f"[{nid}] {text[:80]}{mark}", data=nid)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        if event.node.data:
            self.pick(str(event.node.data))


class StatusBar(Static):
    DEFAULT_CSS = """
    StatusBar { height: 1; background: $panel; color: $text; padding: 0 1; }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self.session = "—"
        #: Where the model works and the executor is fenced — and, when this
        #: repo is installed into another project, which project that is.
        self.cwd = ""
        self.focus_name = "chat"
        self.stage = ""
        self.cycle = 0
        self.model = ""
        self.effort = ""
        self.busy = False
        self.cost = 0.0
        #: The pool the last priced call drew on, and what it left. `Priced`
        #: is per call, so this moves *during* a frame; the panel's pools come
        #: from `StateSnapshot`, which only arrives once the frame has ended.
        self.pool = ""
        self.pool_left = 0

    def set_session(self, record: SessionRecord | None) -> None:
        if record is not None:
            self.session = record.name
            self.focus_name = record.focus
        self.refresh_line()

    def set_cwd(self, cwd) -> None:
        self.cwd = Path(cwd).name or str(cwd)
        self.refresh_line()

    def set_settings(self, model: str, effort: str) -> None:
        self.model, self.effort = model, effort
        self.refresh_line()

    def set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.refresh_line()

    def apply(self, event: ev.HarnessEvent) -> None:
        match event:
            case ev.StateSnapshot(stage=stage, cycle=cycle):
                self.stage, self.cycle = stage, cycle
            case ev.TurnStarted(kind="graph", stage=stage, cycle=cycle):
                # the frame that is running now, not the one that last finished
                self.stage, self.cycle = stage or self.stage, cycle or self.cycle
            case ev.Priced(pool=pool, remaining=remaining):
                self.pool, self.pool_left = pool, remaining
            case ev.SessionInfo(model=model):
                self.model = model or self.model
            case ev.TurnFinished(cost_usd=cost):
                if cost:
                    self.cost += cost
            case _:
                return
        self.refresh_line()

    def refresh_line(self) -> None:
        graph = f"  cycle {self.cycle} · {self.stage}" if self.cycle else ""
        if self.pool:
            graph += f" · {self.pool} {self.pool_left} left"
        state = "⋯ working" if self.busy else "idle"
        cost = f"  ~${self.cost:.3f}" if self.cost else ""
        effort = f" · {self.effort}" if self.effort else ""
        where = f"{self.cwd}  " if self.cwd else ""
        self.update(Text(f"{where}{self.session}  /{self.focus_name}{graph}  {self.model}{effort}{cost}  {state}   Esc interrupts · ctrl+g panel · /help"))
