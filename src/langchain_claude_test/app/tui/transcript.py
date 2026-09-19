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
    """One tool call: title carries name, input and price; body carries the result."""

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
        self._body.update(Text(reason, style="yellow"))
        self.collapsed = False

    def result(self, text: str, is_error: bool) -> None:
        lines = text.splitlines() or [""]
        shown = "\n".join(lines[:_RESULT_LINES]) + (f"\n… {len(lines) - _RESULT_LINES} more lines" if len(lines) > _RESULT_LINES else "")
        if is_error:
            self.add_class("error")
            self.collapsed = False
        self._body.update(Text(shown))


class Transcript(VerticalScroll):
    DEFAULT_CSS = """
    Transcript { padding: 0 1; }
    Transcript .user { color: $accent; margin: 1 0 0 0; text-style: bold; }
    Transcript .thinking { color: $text-muted; text-style: italic; margin: 0 0 0 2; }
    Transcript .assistant { margin: 0 0 0 0; }
    Transcript .notice { color: $text-muted; margin: 0 0 0 0; }
    Transcript .warning { color: $warning; }
    Transcript .error { color: $error; }
    Transcript .stage { color: $success; text-style: bold; margin: 1 0 0 0; }
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

    # --- what the user typed ------------------------------------------------

    def user(self, text: str) -> None:
        self._close_blocks()
        self.following = True
        self._add(Static(Text(f"› {text}"), classes="user"))

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
                self._text_block.update(Markdown(text or self._text_buf))
                self._text_block, self._text_buf = None, ""
            case ev.ToolStarted(tool_use_id=tid, name=name):
                self._close_text()
                block = ToolBlock(tid, name)
                self._tools[tid] = block
                self._add(block)
            case ev.ToolInputDelta(tool_use_id=tid, partial_json=chunk):
                if tid in self._tools:
                    self._tools[tid].add_input_delta(chunk)
            case ev.ToolCalled(tool_use_id=tid, name=name, input=inp):
                block = self._tools.get(tid)
                if block is None:
                    block = ToolBlock(tid, name)
                    self._tools[tid] = block
                    self._add(block)
                block.set_input(inp)
            case ev.ToolResult(tool_use_id=tid, text=text, is_error=is_error):
                if tid in self._tools:
                    self._tools[tid].result(text, is_error)
            case ev.Priced(tool_use_id=tid, price=price, remaining=remaining):
                if tid in self._tools:
                    self._tools[tid].priced(price, remaining)
            case ev.Refused(tool_use_id=tid, name=name, reason=reason):
                block = self._tools.get(tid)
                if block is None:
                    block = ToolBlock(tid, name)
                    self._tools[tid] = block
                    self._add(block)
                block.refused(reason)
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

    def _close_text(self) -> None:
        if self._text_block is not None and self._text_buf:
            self._text_block.update(Markdown(self._text_buf))
        self._text_block, self._text_buf = None, ""

    def _close_blocks(self) -> None:
        self._close_text()
        self._thinking_block, self._thinking_buf = None, ""
