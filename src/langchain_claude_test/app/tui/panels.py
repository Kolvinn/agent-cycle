"""The side panel and the status line."""

from __future__ import annotations

from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Static, Tree

from ..harness import events as ev
from ..session import SessionRecord


class GraphPanel(Vertical):
    DEFAULT_CSS = """
    GraphPanel { width: 44; border-left: solid $panel; padding: 0 1; }
    GraphPanel Tree { height: 1fr; }
    GraphPanel .pools { height: auto; color: $text-muted; }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.graph_tree: Tree[str] = Tree("graph")
        self.pools = Static("", classes="pools")

    def compose(self):
        yield self.graph_tree
        yield self.pools

    def apply(self, snap: ev.StateSnapshot) -> None:
        tree = self.graph_tree
        tree.clear()
        tree.root.set_label(f"cycle {snap.cycle} · {snap.stage}")
        parents: dict[int, object] = {0: tree.root}
        for depth, node_id, label in snap.outline:
            parent = parents.get(depth, tree.root)
            node = parent.add(label, expand=True)
            parents[depth + 1] = node
        tree.root.expand_all()
        self.pools.update(
            Text("\n".join(f"{pool}: {spent}/{cap}" for pool, spent, cap in snap.pools) or "no pools yet")
        )


class StatusBar(Static):
    DEFAULT_CSS = """
    StatusBar { height: 1; background: $panel; color: $text; padding: 0 1; }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__("", **kwargs)
        self.session = "—"
        self.focus_name = "chat"
        self.stage = ""
        self.cycle = 0
        self.model = ""
        self.effort = ""
        self.busy = False
        self.cost = 0.0

    def set_session(self, record: SessionRecord | None) -> None:
        if record is not None:
            self.session = record.name
            self.focus_name = record.focus
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
        state = "⋯ working" if self.busy else "idle"
        cost = f"  ~${self.cost:.3f}" if self.cost else ""
        effort = f" · {self.effort}" if self.effort else ""
        self.update(Text(f"{self.session}  /{self.focus_name}{graph}  {self.model}{effort}{cost}  {state}   Esc interrupts · ctrl+g panel · /help"))
