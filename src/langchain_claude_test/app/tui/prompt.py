"""The prompt: a wrapping, multi-line input.

Enter sends. Shift+Enter (or Ctrl+J where the terminal cannot tell the two
apart) starts a new line. Tab completes a ``/`` command. The box grows with
its text up to a cap and wraps at the window's width instead of running off
the right edge.

Up and Down recall what was sent, as the Claude CLI's prompt does — but only
from the first and last line, so the same keys still move the cursor inside a
multi-line message. The recall list lives for the run, across session
switches, and is not written to disk: the alternative is one more file to
corrupt, and one that would land inside whatever project this repo is
installed into.
"""

from __future__ import annotations

from textual import events
from textual.binding import Binding
from textual.message import Message
from textual.widgets import TextArea

MAX_LINES = 10


class PromptInput(TextArea):
    DEFAULT_CSS = """
    PromptInput { height: 3; border: tall $accent; padding: 0 1; }
    PromptInput:focus { border: tall $accent; }
    """

    BINDINGS = [Binding("ctrl+a", "select_all", "Select all", show=False)]

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class HintChanged(Message):
        """The ``/`` completions that match what is typed so far."""

        def __init__(self, matches: tuple[str, ...]) -> None:
            super().__init__()
            self.matches = matches

    def __init__(self, suggestions: tuple[str, ...] = (), **kwargs) -> None:
        super().__init__(soft_wrap=True, show_line_numbers=False, tab_behavior="focus", **kwargs)
        self.suggestions = tuple(sorted(suggestions))
        self._placeholder_text = "message, or /command  (/help)  ·  shift+enter for a new line  ·  ↑ recalls"
        self.placeholder = self._placeholder_text
        #: What has been sent this run, oldest first. ``history`` is taken:
        #: it is TextArea's own undo stack.
        self.entries: list[str] = []
        #: Where ``up``/``down`` stand in ``entries``; ``None`` is "not recalling".
        self._recall: int | None = None
        #: What was typed and not sent before the recall started.
        self._draft = ""

    # --- the value, as the old single-line Input exposed it ------------------

    @property
    def value(self) -> str:
        return self.text

    @value.setter
    def value(self, text: str) -> None:
        self.load_text(text)
        self.move_cursor(self.document.end)

    # --- keys -----------------------------------------------------------------

    async def _on_key(self, event: events.Key) -> None:
        key = event.key
        if key == "enter":
            event.stop()
            event.prevent_default()
            self.submit()
            return
        if key in ("shift+enter", "ctrl+j"):
            event.stop()
            event.prevent_default()
            self.insert("\n")
            return
        if key == "tab":
            completed = self.complete()
            if completed:
                event.stop()
                event.prevent_default()
                return
        if key == "up" and self.cursor_location[0] == 0 and self.recall_previous():
            event.stop()
            event.prevent_default()
            return
        if key == "down" and self.cursor_location[0] == self.document.line_count - 1 and self.recall_next():
            event.stop()
            event.prevent_default()
            return
        await super()._on_key(event)

    # --- history --------------------------------------------------------------

    def record(self, text: str) -> None:
        """Remember what was sent. A repeat of the last entry is not a new one."""
        if text and (not self.entries or self.entries[-1] != text):
            self.entries.append(text)
        self._recall, self._draft = None, ""

    def recall_previous(self) -> bool:
        """One step back through what was sent. False leaves the key to the
        cursor, which is what happens at the oldest entry and with none."""
        if not self.entries:
            return False
        if self._recall is None:
            self._draft = self.text
            self._recall = len(self.entries)
        if self._recall == 0:
            return True  # hold at the oldest rather than fall through to the cursor
        self._recall -= 1
        self._show(self.entries[self._recall])
        return True

    def recall_next(self) -> bool:
        """One step forward, ending at the draft the recall interrupted."""
        if self._recall is None:
            return False
        self._recall += 1
        if self._recall >= len(self.entries):
            self._recall = None
            self._show(self._draft)
            self._draft = ""
        else:
            self._show(self.entries[self._recall])
        return True

    def _show(self, text: str) -> None:
        self.load_text(text)
        self.move_cursor(self.document.end)

    async def _on_paste(self, event: events.Paste) -> None:
        """A bracketed paste inserts whole and never sends — a paste is one
        event, not a run of Enter keys, so ``_on_key`` above never sees it.

        Claimed here so that the two delivery paths agree. The terminal's
        path is the app's: the driver posts ``Paste`` to the app, which
        forwards it to the focused widget (``textual/app.py:4142``). A
        ``Paste`` posted straight at this widget would otherwise be inserted
        three times — once by ``TextArea._on_paste``, again when the
        unstopped event bubbles to the app and is forwarded back, and again
        because Textual dispatches every ``_on_paste`` it finds on the MRO
        (``textual/message_pump.py:757-800``) unless the default is prevented.
        """
        event.stop()
        event.prevent_default()
        await super()._on_paste(event)

    def submit(self) -> None:
        text = self.text.strip()
        if text:
            self.post_message(self.Submitted(text))
            self.record(text)
        self.load_text("")

    # --- completion ---------------------------------------------------------------

    def matches(self) -> tuple[str, ...]:
        text = self.text
        if not text.startswith("/") or "\n" in text or " " in text:
            return ()
        return tuple(s for s in self.suggestions if s.startswith(text.lower()))

    def complete(self) -> bool:
        found = self.matches()
        if not found:
            return False
        common = _common_prefix(found)
        target = found[0] if len(found) == 1 else (common if len(common) > len(self.text) else found[0])
        if len(found) == 1:
            target += " "
        self.load_text(target)
        self.move_cursor(self.document.end)
        return True

    # --- growth ---------------------------------------------------------------------

    def _on_text_area_changed(self, event: TextArea.Changed) -> None:
        self._fit()
        self.post_message(self.HintChanged(self.matches()))

    def _on_resize(self, event: events.Resize) -> None:
        # Textual wraps the placeholder to the content width and cannot wrap to
        # zero, so the placeholder goes away whenever there is no room for it.
        self.placeholder = self._placeholder_text if self.content_size.width > 0 else ""
        self._fit()

    def _fit(self) -> None:
        lines = max(1, min(MAX_LINES, self.wrapped_document.height))
        self.styles.height = lines + 2  # the border


def _common_prefix(items: tuple[str, ...]) -> str:
    first, last = min(items), max(items)
    i = 0
    while i < len(first) and i < len(last) and first[i] == last[i]:
        i += 1
    return first[:i]
