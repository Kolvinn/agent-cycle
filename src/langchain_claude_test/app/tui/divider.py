"""A drag handle between the transcript and the graph panel."""

from __future__ import annotations

from typing import Callable

from textual import events
from textual.widget import Widget


class Divider(Widget):
    DEFAULT_CSS = """
    Divider { width: 1; height: 1fr; background: $panel; color: $text-muted; }
    Divider:hover { background: $accent; }
    Divider.dragging { background: $accent; }
    Divider.hidden { display: none; }
    """

    def __init__(self, on_drag: Callable[[int], None], **kwargs) -> None:
        """``on_drag`` receives the width the panel to the right should take."""
        super().__init__(**kwargs)
        self.on_drag = on_drag
        self._dragging = False

    def render(self) -> str:
        return "\n".join("│" for _ in range(max(1, self.size.height)))

    def on_mouse_down(self, event: events.MouseDown) -> None:
        self._dragging = True
        self.add_class("dragging")
        self.capture_mouse()
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        if not self._dragging:
            return
        parent = self.parent
        assert parent is not None
        right_edge = parent.region.right
        self.on_drag(right_edge - event.screen_x - 1)
        event.stop()

    def on_mouse_up(self, event: events.MouseUp) -> None:
        if self._dragging:
            self._dragging = False
            self.remove_class("dragging")
            self.release_mouse()
            event.stop()
