"""The transcript: thinking, text and tool blocks, streamed."""

from __future__ import annotations

import json

from rich.markdown import Markdown
from rich.text import Text
from textual import events
from textual.containers import VerticalScroll
from textual.widgets import Collapsible, Static

from ..harness import events as ev

_RESULT_LINES = 24


def _one_line(value: object, limit: int = 100) -> str:
    text = json.dumps(value, default=str) if not isinstance(value, str) else value
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


class ToolBlock(Collapsible):
    """One tool call: title carries name, input and price; body carries the result.

    The result is kept whole in :attr:`full_text` and only *drawn* short, so
    ``/expand`` and ``/copy tool`` can reach the rest of it. Before, the lines
    past the cut were thrown away at render time and were gone.

    Selection, checked rather than assumed: the audit read
    ``ALLOW_SELECT = False`` at ``textual/widgets/_collapsible.py:22`` as
    ``Collapsible``'s, and it is ``CollapsibleTitle``'s (``Collapsible`` is
    line 99 and sets nothing). The hit test under a mouse drag returns the
    innermost widget, which over the body is the result ``Static``, so the
    **result was always draggable**; what cannot be dragged over is the
    *title* row — the tool's name, its input and its price. ``/copy tool``
    is the path to the result that no terminal can eat (E62).
    """

    DEFAULT_CSS = """
    ToolBlock { margin: 0 0 0 2; padding: 0; border: none; }
    ToolBlock > Contents { padding: 0 0 0 2; }
    ToolBlock.error CollapsibleTitle { color: $error; }
    ToolBlock.refused CollapsibleTitle { color: $warning; }
    """

    def __init__(self, tool_use_id: str, name: str) -> None:
        self.tool_use_id = tool_use_id
        self.tool_name = name
        self._input = ""
        self._price = ""
        #: The result as it arrived, uncut. Empty until one does.
        self.full_text = ""
        self._expanded = False
        self._body = Static("…", classes="tool-result")
        super().__init__(self._body, title=self._label(), collapsed=True)

    def _label(self) -> str:
        return f"⚙ {self.tool_name}({self._input}){self._price}"

    def set_input(self, value: object) -> None:
        self._input = _one_line(value, 90)
        self.title = self._label()

    def add_input_delta(self, chunk: str) -> None:
        if not self._input.endswith("…"):
            self._input = _one_line(self._input + chunk, 90)
            self.title = self._label()

    def priced(self, price: int, remaining: int) -> None:
        self._price = f"  −{price} → {remaining} left"
        self.title = self._label()

    def refused(self, reason: str) -> None:
        self.add_class("refused")
        self._price = "  refused"
        self.title = self._label()
        self.full_text = reason
        self._body.update(Text(reason, style="yellow"))
        self.collapsed = False

    def result(self, text: str, is_error: bool) -> None:
        self.full_text = text
        if is_error:
            self.add_class("error")
            self.collapsed = False
        self._draw()

    def expand(self) -> None:
        """Show the result whole, and open the block so it can be seen."""
        self._expanded = True
        self.collapsed = False
        self._draw()

    def _draw(self) -> None:
        lines = self.full_text.splitlines() or [""]
        if self._expanded or len(lines) <= _RESULT_LINES:
            self._body.update(Text(self.full_text))
            return
        hidden = len(lines) - _RESULT_LINES
        self._body.update(Text("\n".join(lines[:_RESULT_LINES]) + f"\n… {hidden} more lines — /expand or ctrl+o"))


class Transcript(VerticalScroll):
    DEFAULT_CSS = """
    Transcript { padding: 0 1; }
    Transcript .user { color: $accent; margin: 1 0 0 0; text-style: bold; }
    Transcript .user.queued { color: $text-muted; text-style: none; }
    Transcript .thinking { color: $text-muted; text-style: italic; margin: 0 0 0 2; }
    Transcript .assistant { margin: 0 0 0 0; }
    Transcript .notice { color: $text-muted; margin: 0 0 0 0; }
    Transcript .warning { color: $warning; }
    Transcript .error { color: $error; }
    Transcript .stage { color: $success; text-style: bold; margin: 1 0 0 0; }
    Transcript .running { color: $text-muted; text-style: bold; margin: 1 0 0 0; }
    Transcript .approval { color: $warning; margin: 0 0 0 2; }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        #: Follow new content only while the reader is at the bottom. Scrolling
        #: up releases it; scrolling back to the end (or a new message) re-arms it.
        self.following = True
        self._text_block: Static | None = None
        self._text_buf = ""
        self._thinking_block: Static | None = None
        self._thinking_buf = ""
        self._tools: dict[str, ToolBlock] = {}
        #: Tool blocks in the order they appeared — ``/expand`` counts back
        #: through this, and ``/copy tool`` takes the last with a result.
        self._tool_order: list[ToolBlock] = []
        self._last_assistant = ""
        self._last_user = ""
        #: (widget, text) for the lines waiting behind a turn in flight.
        self._queued: list[tuple[Static, str]] = []

    # --- what the user typed ------------------------------------------------

    def user(self, text: str, *, command: bool = False, queued: bool = False) -> None:
        """``command`` marks a ``/`` line, which is an instruction to this
        shell rather than a message — ``/copy user`` skips them, or it would
        only ever hand back the ``/copy`` that asked for it.

        ``queued`` marks a line that is waiting behind a turn in flight, so a
        line being answered and a line still in the queue do not look the
        same. :meth:`dequeued` takes the mark off, oldest first, as the runner
        reaches each one."""
        self._close_blocks()
        self.following = True
        if not command:
            self._last_user = text
        line = Static(Text(f"› {text}" + ("   (queued)" if queued else "")), classes="user")
        if queued:
            line.add_class("queued")
            self._queued.append((line, text))
        self._add(line)

    def dequeued(self) -> None:
        """The oldest waiting line is being answered now. FIFO, because the
        queue it is waiting in is."""
        while self._queued:
            line, text = self._queued.pop(0)
            if line.is_attached:
                line.remove_class("queued")
                line.update(Text(f"› {text}"))
                return

    # --- getting text back out (E55, E62) --------------------------------------

    def last_text(self, kind: str) -> str | None:
        """The last assistant message, tool result or message of the user's,
        as text — what ``/copy`` puts on the clipboard. ``None`` when there is
        none of that kind yet."""
        if kind == "last":
            return self._last_assistant or None
        if kind == "user":
            return self._last_user or None
        if kind == "tool":
            done = [b for b in self._tool_order if b.full_text]
            return done[-1].full_text if done else None
        return None

    def expand_tool(self, nth_from_last: int = 1) -> bool:
        """Show a tool result in full. 1 is the last one. False if there is none."""
        done = [b for b in self._tool_order if b.full_text]
        if not done or nth_from_last < 1 or nth_from_last > len(done):
            return False
        done[-nth_from_last].expand()
        self._autoscroll()
        return True

    def clear_transcript(self) -> None:
        """Empty the screen, and nothing else — no SDK conversation, no
        session record, no graph. ``/clear`` is the CLI's and goes to the
        conversation (``commands.py``); this is the screen's own."""
        self.remove_children()
        self._text_block, self._text_buf = None, ""
        self._thinking_block, self._thinking_buf = None, ""
        self._tools.clear()
        self._tool_order.clear()
        self._queued.clear()
        self._last_assistant = self._last_user = ""
        self.following = True

    # --- following ------------------------------------------------------------------

    def _on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        self.following = False
        super()._on_mouse_scroll_up(event)

    def _on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        super()._on_mouse_scroll_down(event)
        self.call_after_refresh(self._rearm_if_at_end)

    def page_up(self) -> None:
        self.following = False
        self.scroll_page_up(animate=False)

    def page_down(self) -> None:
        self.scroll_page_down(animate=False)
        self.call_after_refresh(self._rearm_if_at_end)

    def follow(self) -> None:
        self.following = True
        self.scroll_end(animate=False)

    def _rearm_if_at_end(self) -> None:
        if self.scroll_y >= self.max_scroll_y - 1:
            self.following = True

    def _autoscroll(self) -> None:
        if self.following:
            self.scroll_end(animate=False)

    # --- events -------------------------------------------------------------------

    def apply(self, event: ev.HarnessEvent) -> None:
        if isinstance(event, (ev.ToolStarted, ev.ToolCalled)) and event.name == "StructuredOutput":
            return  # the synthetic call structured output arrives as; the payload is the frame's answer
        match event:
            case ev.TurnStarted(kind="graph", stage=stage, cycle=cycle):
                # Which frame is running, said when it starts rather than when
                # it ends. `StageStarted` exists in harness/events.py and is
                # emitted by nothing; this is the event the frames actually
                # send (harness/sdk.py:133, harness/scripted.py:102).
                self._close_blocks()
                self._add(Static(Text(f"── {stage} · cycle {cycle} ── running"), classes="running"))
            case ev.TurnStarted():
                self._close_blocks()
            case ev.ThinkingDelta(text=text):
                self._thinking_buf += text
                if self._thinking_block is None:
                    self._thinking_block = Static("", classes="thinking")
                    self._add(self._thinking_block)
                self._thinking_block.update(Text(self._thinking_buf))
            case ev.ThinkingDone(text=text):
                if self._thinking_block is not None:
                    self._thinking_block.update(Text(text or self._thinking_buf))
                self._thinking_block, self._thinking_buf = None, ""
            case ev.TextDelta(text=text):
                self._text_buf += text
                if self._text_block is None:
                    self._text_block = Static("", classes="assistant")
                    self._add(self._text_block)
                self._text_block.update(Text(self._text_buf))
            case ev.TextDone(text=text):
                if self._text_block is None:
                    self._text_block = Static("", classes="assistant")
                    self._add(self._text_block)
                self._last_assistant = text or self._text_buf
                self._text_block.update(Markdown(self._last_assistant))
                self._text_block, self._text_buf = None, ""
            case ev.ToolStarted(tool_use_id=tid, name=name):
                self._close_text()
                self._tool(tid, name)
            case ev.ToolInputDelta(tool_use_id=tid, partial_json=chunk):
                if tid in self._tools:
                    self._tools[tid].add_input_delta(chunk)
            case ev.ToolCalled(tool_use_id=tid, name=name, input=inp):
                self._tool(tid, name).set_input(inp)
            case ev.ToolResult(tool_use_id=tid, text=text, is_error=is_error):
                if tid in self._tools:
                    self._tools[tid].result(text, is_error)
            case ev.Priced(tool_use_id=tid, price=price, remaining=remaining):
                if tid in self._tools:
                    self._tools[tid].priced(price, remaining)
            case ev.Refused(tool_use_id=tid, name=name, reason=reason):
                self._tool(tid, name).refused(reason)
            case ev.ApprovalAsked(name=name, title=title):
                self._add(Static(Text(f"? {title or name} — waiting for you"), classes="approval"))
            case ev.ApprovalAnswered(name=name, approved=approved, words=words, answered_by=by):
                verdict = "approved" if approved else "refused"
                tail = f' — "{words}"' if words else ""
                flag = "" if by == "human" else f"  [{by}]"
                self._add(Static(Text(f"✓ {name} {verdict}{tail}{flag}"), classes="approval"))
            case ev.StageFinished(stage=stage, cycle=cycle, summary=summary):
                self._close_blocks()
                self._add(Static(Text(f"── {stage} · cycle {cycle} ── {summary}"), classes="stage"))
            case ev.Notice(text=text, level=level):
                self._close_blocks()
                self._add(Static(Text(text), classes=f"notice {level}"))
            case ev.TurnFinished(interrupted=True):
                self._close_blocks()
                self._add(Static(Text("⏹ interrupted"), classes="notice warning"))
            case _:
                return
        self._autoscroll()

    # --- internals ----------------------------------------------------------------

    def _add(self, widget) -> None:
        self.mount(widget)
        self._autoscroll()

    def _tool(self, tool_use_id: str, name: str) -> ToolBlock:
        """The block for this call, mounted the first time it is asked for.
        Three events can be the first to mention a call."""
        block = self._tools.get(tool_use_id)
        if block is None:
            block = ToolBlock(tool_use_id, name)
            self._tools[tool_use_id] = block
            self._tool_order.append(block)
            self._add(block)
        return block

    def _close_text(self) -> None:
        if self._text_block is not None and self._text_buf:
            self._last_assistant = self._text_buf
            self._text_block.update(Markdown(self._text_buf))
        self._text_block, self._text_buf = None, ""

    def _close_blocks(self) -> None:
        self._close_text()
        self._thinking_block, self._thinking_buf = None, ""
