"""The two modal screens a live turn can open, and the approver over them.

A screen resolves a future the harness is awaiting inside ``can_use_tool``,
which runs as a task on the same loop as the app — so the modal is pushed with
``call_later`` (safe from any task) and the transcript keeps streaming behind
it.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static, TextArea

from ..harness.protocol import ApprovalRequest, Verdict


class ApprovalScreen(ModalScreen[Verdict]):
    DEFAULT_CSS = """
    ApprovalScreen { align: center middle; }
    ApprovalScreen > Vertical { width: 90; max-height: 80%; border: thick $warning; background: $surface; padding: 1 2; }
    ApprovalScreen .title { text-style: bold; color: $warning; }
    ApprovalScreen .input { color: $text-muted; height: auto; max-height: 12; overflow-y: auto; }
    ApprovalScreen TextArea { height: 5; }
    ApprovalScreen Horizontal { height: 3; align: right middle; }
    """
    BINDINGS = [("ctrl+a", "approve", "Approve"), ("ctrl+r", "refuse", "Refuse")]

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
            yield TextArea(id="words")
            with Horizontal():
                yield Button("Approve  ctrl+a", id="approve", variant="success")
                yield Button("Refuse  ctrl+r", id="refuse", variant="error")

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
