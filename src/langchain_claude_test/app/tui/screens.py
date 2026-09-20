"""The two modal screens a live turn can open, and the approver over them.

A screen resolves a future the harness is awaiting inside ``can_use_tool``,
which runs as a task on the same loop as the app — so the modal is pushed with
``call_later`` (safe from any task) and the transcript keeps streaming behind
it.

**Esc.** ``escape`` is an app-level *priority* binding for interrupt, and
Textual checks priority bindings from the App down
(``reversed(screen._binding_chain)``, ``textual/app.py:3976``), so a screen's
own escape binding can never outrank it. Each modal therefore says what Esc
means to it in ``escape()``, and the app's interrupt action asks the top
screen first. Every one of these modals is a future something is blocked on,
so ``escape()`` must **resolve** it: a dismissal that answers nothing would
leave a turn waiting for ever.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from ..harness.protocol import ApprovalRequest, Verdict


class WordsArea(TextArea):
    BINDINGS = [Binding("ctrl+a", "select_all", "Select all", show=False)]


class ApprovalScreen(ModalScreen[Verdict]):
    DEFAULT_CSS = """
    ApprovalScreen { align: center middle; }
    ApprovalScreen > Vertical { width: 90; max-height: 80%; border: thick $warning; background: $surface; padding: 1 2; }
    ApprovalScreen .title { text-style: bold; color: $warning; }
    ApprovalScreen .input { color: $text-muted; height: auto; max-height: 12; overflow-y: auto; }
    ApprovalScreen TextArea { height: 5; }
    ApprovalScreen Horizontal { height: 3; align: right middle; }
    """
    #: ctrl+a is select-all in the words box, so the verdict keys are y/n —
    #: and both are **priority**, because the focused widget is a ``TextArea``
    #: and ``TextArea`` binds ctrl+y to redo (``_text_area.py:417``). A screen
    #: binding is checked from the focused widget up, so without priority the
    #: advertised approve key was swallowed by the words box and approve could
    #: only be reached with Tab and Enter.
    BINDINGS = [
        Binding("ctrl+y", "approve", "Approve", priority=True),
        Binding("ctrl+n", "refuse", "Refuse", priority=True),
    ]

    def __init__(self, request: ApprovalRequest) -> None:
        super().__init__()
        self.request = request

    def compose(self) -> ComposeResult:
        r = self.request
        what = "The agent proposes a change to the graph" if r.kind == "alteration" else "Claude wants to use a tool"
        with Vertical():
            yield Label(Text(f"{what}: {r.name}"), classes="title")
            if r.title:
                yield Static(Text(r.title))
            if r.description:
                yield Static(Text(r.description))
            yield Static(Text(json.dumps(dict(r.input), indent=1, default=str)), classes="input")
            yield Label("Your words (they go back to the model, approved or not):")
            yield WordsArea(id="words")
            with Horizontal():
                yield Button("Approve  ctrl+y", id="approve", variant="success")
                yield Button("Refuse  ctrl+n", id="refuse", variant="error")

    def on_mount(self) -> None:
        self.query_one("#words", TextArea).focus()

    def _words(self) -> str:
        return self.query_one("#words", TextArea).text.strip()

    def action_approve(self) -> None:
        self.dismiss(Verdict(approved=True, answered_by="human", words=self._words()))

    def action_refuse(self) -> None:
        self.dismiss(Verdict(approved=False, answered_by="human", words=self._words()))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "approve":
            self.action_approve()
        else:
            self.action_refuse()

    def escape(self) -> None:
        """Esc refuses, with whatever words are typed — as ctrl+n does.

        The conservative answer: nothing happens to the graph, the model is
        told, and the words ride back. It is also what the Claude CLI does at
        a permission prompt. Esc here never interrupts the turn the modal is
        blocking.
        """
        self.action_refuse()


class QuestionScreen(ModalScreen[str]):
    """One of the model's questions: pick an option, or type your own answer."""

    DEFAULT_CSS = """
    QuestionScreen { align: center middle; }
    QuestionScreen > Vertical { width: 80; max-height: 80%; border: thick $accent; background: $surface; padding: 1 2; }
    QuestionScreen .title { text-style: bold; color: $accent; }
    QuestionScreen OptionList { height: auto; max-height: 12; }
    """

    def __init__(self, question: dict[str, Any]) -> None:
        super().__init__()
        self.question = question

    def compose(self) -> ComposeResult:
        q = self.question
        options = [f"{o.get('label', '')} — {o.get('description', '')}" for o in q.get("options", [])]
        with Vertical():
            yield Label(Text(f"{q.get('header', '')}: {q.get('question', '')}"), classes="title")
            yield OptionList(*options, id="options")
            yield Label("…or type your own answer and press Enter:")
            yield Input(id="free")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        label = self.question.get("options", [])[event.option_index].get("label", "")
        self.dismiss(label)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.value.strip():
            self.dismiss(event.value.strip())

    def escape(self) -> None:
        """Esc leaves the question unanswered — an empty answer, which is what
        "I am not answering that" looks like to the frame that asked. The
        frame is awaiting this future, so Esc must resolve it."""
        self.dismiss("")


class ChoiceScreen(ModalScreen[str | None]):
    """Pick one value for a shell setting (``/model``, ``/effort``); Esc leaves it."""

    DEFAULT_CSS = """
    ChoiceScreen { align: center middle; }
    ChoiceScreen > Vertical { width: 80; max-height: 80%; border: thick $accent; background: $surface; padding: 1 2; }
    ChoiceScreen .title { text-style: bold; color: $accent; }
    ChoiceScreen OptionList { height: auto; max-height: 16; }
    ChoiceScreen .hint { color: $text-muted; }
    """
    BINDINGS = [("escape", "leave", "Leave as is")]

    def __init__(self, title: str, options: list[tuple[str, str]], current: str = "") -> None:
        super().__init__()
        self.title_text = title
        self.options = options
        self.current = current

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(Text(self.title_text), classes="title")
            yield OptionList(
                *[Option(Text(("● " if value == self.current else "  ") + label), id=f"opt-{i}") for i, (value, label) in enumerate(self.options)],
                id="options",
            )
            yield Label("Enter picks · Esc leaves it as is", classes="hint")

    def on_mount(self) -> None:
        options = self.query_one("#options", OptionList)
        for i, (value, _) in enumerate(self.options):
            if value == self.current:
                options.highlighted = i
                break
        else:
            options.highlighted = 0 if self.options else None
        options.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(self.options[event.option_index][0])

    def action_leave(self) -> None:
        self.dismiss(None)

    def escape(self) -> None:
        """Esc leaves the setting as it is. The binding above cannot fire while
        the app holds a priority ``escape``; this is the path that runs."""
        self.action_leave()


class TuiApprover:
    """The :class:`Approver` the runner uses — modals over the app."""

    def __init__(self, app) -> None:
        self.app = app

    async def approve(self, request: ApprovalRequest) -> Verdict:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Verdict] = loop.create_future()
        self.app.call_later(self.app.push_screen, ApprovalScreen(request), lambda v: future.set_result(v))
        return await future

    async def ask(self, questions: list[dict[str, Any]]) -> dict[str, Any]:
        answers: dict[str, Any] = {}
        for q in questions:
            loop = asyncio.get_running_loop()
            future: asyncio.Future[str] = loop.create_future()
            self.app.call_later(self.app.push_screen, QuestionScreen(q), lambda v, f=future: f.set_result(v))
            answers[q.get("question", "")] = await future
        return answers

    async def choose(self, title: str, options: list[tuple[str, str]], current: str = "") -> str | None:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[str | None] = loop.create_future()
        self.app.call_later(self.app.push_screen, ChoiceScreen(title, options, current), lambda v: future.set_result(v))
        return await future
